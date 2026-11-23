"""Wspólna logika zakładania kont użytkownika w bazach i pliku z danymi połączeń.

Używana przez hub (hook przed startem sesji) i bramkę SSH (przy logowaniu), dzięki czemu
użytkownik dostaje te same dane dostępowe niezależnie od tego, którędy wszedł.
"""
import hashlib
import hmac
import json
import os
import re


def group_members(group_file, group_name):
    """Członkowie grupy z pliku w formacie /etc/group (puste, gdy pliku lub grupy brak)."""
    try:
        with open(group_file) as f:
            for line in f:
                parts = line.rstrip("\n").split(":")
                if len(parts) >= 4 and parts[0] == group_name:
                    return {m.strip() for m in parts[3].split(",") if m.strip()}
    except OSError:
        pass
    return set()


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


def _webhdfs(op, path, **params):
    """Wywołanie WebHDFS jako superużytkownik (jego nazwa jest tajna, zna ją tylko hub i bramka)."""
    import urllib.parse
    import urllib.request

    query = urllib.parse.urlencode({"op": op, "user.name": os.environ["HDFS_ADMIN_USER"], **params})
    url = f"{os.environ['HDFS_WEBHDFS']}/webhdfs/v1{urllib.parse.quote(path)}?{query}"
    method = "GET" if op in ("GETFILESTATUS",) else "PUT"
    with urllib.request.urlopen(urllib.request.Request(url, method=method), timeout=20) as r:
        return r.read()


def ensure_hdfs_home(login):
    """Katalog /user/<login> (właściciel: użytkownik) oraz katalogi wspólne. Idempotentne; bez HDFS nic nie robi."""
    if not os.environ.get("HDFS_WEBHDFS"):
        return None
    for path, mode in (("/user", "755"), ("/tmp", "1777"), ("/warehouse", "1777"), ("/shared", "755")):
        _webhdfs("MKDIRS", path, permission=mode)
        _webhdfs("SETPERMISSION", path, permission=mode)
    home = "/user/" + login
    _webhdfs("MKDIRS", home, permission="755")
    _webhdfs("SETOWNER", home, owner=login, group=login)
    return home


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
        "hdfs": {"namenode": "hdfs://namenode:8020", "webhdfs": "http://namenode:9870", "home": "/user/" + login}
        if os.environ.get("HDFS_WEBHDFS") else None,
        "note": "Dane dla skryptów uruchamianych w kontenerach i na bramce SSH. Neo4j jest wspólny: "
        "nazwy grafów projekcji GDS zaczynaj od graph_prefix.",
    }


def write_connection_file(home, uid, gid, login):
    """Zapisuje ~/.config/spark/connection.json (prawa 600) z danymi dostępu do Cassandry i Neo4j."""
    config_dir = os.path.join(home, ".config")
    target_dir = os.path.join(config_dir, "spark")
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
