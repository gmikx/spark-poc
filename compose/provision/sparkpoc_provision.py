"""Wspólna logika zakładania kont użytkownika w bazach i pliku z danymi połączeń.

Używana przez hub (hook przed startem sesji) i bramkę SSH (przy logowaniu), dzięki czemu
użytkownik dostaje te same dane dostępowe niezależnie od tego, którędy wszedł.
"""
import hashlib
import hmac
import json
import os
import re


def role_name(login):
    return "u" + re.sub(r"[^a-z0-9_]", "_", login)


def cassandra_credentials(login):
    role = role_name(login)
    secret = os.environ["CASSANDRA_PASSWORD_SECRET"].encode()
    return role, hmac.new(secret, role.encode(), hashlib.sha256).hexdigest()[:32]


def ensure_cassandra_account(login):
    """Rola i keyspace o nazwie u<login>, z uprawnieniami tylko do własnego keyspace'u (idempotentnie)."""
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.cluster import Cluster

    role, password = cassandra_credentials(login)
    cluster = Cluster(
        [os.environ["CASSANDRA_HOST"]],
        auth_provider=PlainTextAuthProvider(
            os.environ["CASSANDRA_ADMIN_USER"], os.environ["CASSANDRA_ADMIN_PASSWORD"]
        ),
    )
    try:
        session = cluster.connect()
        session.execute(
            f"CREATE ROLE IF NOT EXISTS \"{role}\" WITH PASSWORD = '{password}' AND LOGIN = true"
        )
        session.execute(
            f"CREATE KEYSPACE IF NOT EXISTS \"{role}\" WITH replication = "
            "{'class': 'SimpleStrategy', 'replication_factor': 1}"
        )
        session.execute(f"GRANT ALL PERMISSIONS ON KEYSPACE \"{role}\" TO \"{role}\"")
    finally:
        cluster.shutdown()
    return role, password


def connection_info(login):
    role, password = cassandra_credentials(login)
    return {
        "cassandra": {
            "hosts": [os.environ.get("CASSANDRA_HOST", "cassandra")],
            "port": 9042,
            "user": role,
            "password": password,
            "keyspace": role,
        },
        "neo4j": {
            "uri": os.environ.get("NEO4J_URI", "bolt://neo4j:7687"),
            "user": "neo4j",
            "password": os.environ["NEO4J_PASSWORD"],
            "graph_prefix": role + "_",
        },
        "note": "Dane dla skryptów uruchamianych w kontenerach i na bramce SSH. Neo4j jest wspólny: "
        "nazwy grafów projekcji GDS zaczynaj od graph_prefix.",
    }


def write_connection_file(home, uid, gid, login):
    """Zapisuje ~/.config/sparkpoc/connection.json (prawa 600) z danymi dostępu do Cassandry i Neo4j."""
    config_dir = os.path.join(home, ".config")
    target_dir = os.path.join(config_dir, "sparkpoc")
    for d in (config_dir, target_dir):
        if not os.path.isdir(d):
            os.mkdir(d, 0o700)
            try:
                os.chown(d, uid, gid)
            except OSError:
                pass
    path = os.path.join(target_dir, "connection.json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(connection_info(login), f, indent=2)
        f.write("\n")
    try:
        os.chown(path, uid, gid)
    except OSError:
        pass
    return path
