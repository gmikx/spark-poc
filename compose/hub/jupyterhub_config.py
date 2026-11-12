import os

c = get_config()  # noqa: F821

c.JupyterHub.bind_url = "http://:8000"
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.hub_connect_ip = "jupyterhub"
c.JupyterHub.cookie_secret_file = "/srv/jupyterhub/cookie_secret"
c.JupyterHub.db_url = "sqlite:////srv/jupyterhub/jupyterhub.sqlite"

AUTH_MODE = os.environ.get("AUTH_MODE", "dummy")

if AUTH_MODE == "ldap":
    base_dn = os.environ["LDAP_BASE_DN"]
    c.JupyterHub.authenticator_class = "ldap"
    c.LDAPAuthenticator.server_address = os.environ["LDAP_HOST"]
    c.LDAPAuthenticator.valid_username_regex = r"^[a-z0-9][.a-z0-9_-]*$"
    c.LDAPAuthenticator.use_ssl = False
    c.LDAPAuthenticator.tls_strategy = "insecure"
    c.LDAPAuthenticator.bind_dn_template = [f"uid={{username}},ou=people,{base_dn}"]
    c.LDAPAuthenticator.allowed_groups = [os.environ["LDAP_ALLOWED_GROUP"]]
    c.Authenticator.admin_users = set(os.environ["LDAP_ADMINS"].split(","))
else:
    c.JupyterHub.authenticator_class = "dummy"
    c.DummyAuthenticator.password = os.environ["POC_PASSWORD"]
    c.Authenticator.allowed_users = set(os.environ["POC_USERS"].split(","))
    c.Authenticator.admin_users = set(os.environ["POC_ADMINS"].split(","))

c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"
c.DockerSpawner.image = os.environ["SINGLEUSER_IMAGE"]
c.DockerSpawner.network_name = os.environ["DOCKER_NETWORK"]
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.remove = True
c.DockerSpawner.name_template = "sparkpoc-user-{username}"
c.DockerSpawner.cmd = [
    "bash", "-c",
    "export SPARK_LOCAL_HOSTNAME=$(hostname -i | awk '{print $1}'); exec jupyterhub-singleuser \"$@\"", "--",
]
c.DockerSpawner.notebook_dir = "/home/jovyan/work"
c.DockerSpawner.volumes = {
    "sparkpoc-home-{username}": "/home/jovyan/work",
    "sparkpoc_shared-data": {"bind": "/home/jovyan/shared", "mode": "ro"},
}
c.DockerSpawner.mem_limit = os.environ["USER_MEM_LIMIT"]
c.DockerSpawner.cpu_limit = float(os.environ["USER_CPU_LIMIT"])
c.DockerSpawner.environment = {
    "CASSANDRA_HOST": "cassandra",
    "NEO4J_URI": "bolt://neo4j:7687",
}


def ldap_identity_hook(spawner):
    from ldap3 import Server, Connection

    conn = Connection(
        Server(os.environ["LDAP_HOST"]),
        user=os.environ["LDAP_BIND_DN"],
        password=os.environ["LDAP_BIND_PASSWORD"],
        auto_bind=True,
    )
    conn.search(
        f"ou=people,{os.environ['LDAP_BASE_DN']}",
        f"(uid={spawner.user.name})",
        attributes=["uidNumber", "gidNumber", "homeDirectory", "loginShell"],
    )
    entry = conn.entries[0]
    uid, gid, home = int(entry.uidNumber.value), int(entry.gidNumber.value), entry.homeDirectory.value
    if not os.path.isdir(home):
        try:
            os.makedirs(home)
            os.chown(home, uid, gid)
        except OSError as e:
            raise RuntimeError(
                f"Katalog domowy {home} nie istnieje i nie mozna go utworzyc: {e}"
            ) from e
    shell = entry.loginShell.value if "loginShell" in entry else "/bin/bash"
    passwd_file = f"/nss/{spawner.user.name}.passwd"
    group_file = f"/nss/{spawner.user.name}.group"
    with open(passwd_file, "w") as f:
        f.write(f"{spawner.user.name}:x:{uid}:{gid}::{home}:{shell}\n")
    with open(group_file, "w") as f:
        f.write(f"g{gid}:x:{gid}:\n")
    spawner.extra_create_kwargs = {"user": f"{uid}:{gid}", "working_dir": home}
    spawner.notebook_dir = home
    spawner.environment = {
        **spawner.environment,
        "HOME": home,
        "USER": spawner.user.name,
        "LD_PRELOAD": "libnss_wrapper.so",
        "NSS_WRAPPER_PASSWD": passwd_file,
        "NSS_WRAPPER_GROUP": group_file,
        "SPARK_LOCAL_DIRS": "/tmp",
    }


def cassandra_account_hook(spawner):
    import hashlib
    import hmac
    import re

    from cassandra.auth import PlainTextAuthProvider
    from cassandra.cluster import Cluster

    role = "u" + re.sub(r"[^a-z0-9_]", "_", spawner.user.name)
    secret = os.environ["CASSANDRA_PASSWORD_SECRET"].encode()
    password = hmac.new(secret, role.encode(), hashlib.sha256).hexdigest()[:32]

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

    spawner.environment = {
        **spawner.environment,
        "CASSANDRA_USER": role,
        "CASSANDRA_PASSWORD": password,
        "CASSANDRA_KEYSPACE": role,
    }


def pre_spawn(spawner):
    ldap_identity_hook(spawner)
    cassandra_account_hook(spawner)


if AUTH_MODE == "ldap":
    c.DockerSpawner.volumes = {
        os.environ.get("HOMES_VOLUME", "sparkpoc_homes"): "/home",
        "sparkpoc_nss": {"bind": "/nss", "mode": "ro"},
        "sparkpoc_shared-data": {"bind": "/shared", "mode": "ro"},
    }
    c.Spawner.pre_spawn_hook = pre_spawn

c.Spawner.default_url = "/lab"
c.Spawner.start_timeout = 120
c.Spawner.http_timeout = 120

IDLE_TIMEOUT = os.environ.get("USER_IDLE_TIMEOUT", "3600")
KERNEL_IDLE_TIMEOUT = os.environ.get("KERNEL_IDLE_TIMEOUT", "1800")

c.Spawner.args = [
    f"--MappingKernelManager.cull_idle_timeout={KERNEL_IDLE_TIMEOUT}",
    "--MappingKernelManager.cull_interval=120",
    "--MappingKernelManager.cull_connected=True",
]

c.JupyterHub.services = [
    {
        "name": "idle-culler",
        "command": ["python3", "-m", "jupyterhub_idle_culler", f"--timeout={IDLE_TIMEOUT}", "--cull-every=120"],
    }
]
c.JupyterHub.load_roles = [
    {
        "name": "idle-culler",
        "scopes": ["list:users", "read:users:activity", "read:servers", "delete:servers"],
        "services": ["idle-culler"],
    }
]


# Ostatnie wylogowanie użytkownika zatrzymuje jego serwer. Wylogowanie z jednej z kilku
# przeglądarek go nie rusza: "inne sesje" to niewygasłe tokeny sesji OAuth tego użytkownika
# (powstają przy wejściu na serwer notebooka i są kasowane przy wylogowaniu danej sesji).
# Gdy serwer jest w trakcie startu, jest zatrzymywany zaraz po jego zakończeniu.
import asyncio  # noqa: E402
from datetime import datetime  # noqa: E402

from jupyterhub import orm  # noqa: E402
from jupyterhub.handlers.login import LogoutHandler  # noqa: E402


async def _stop_after_logout(handler, user, name, spawner):
    try:
        if spawner.pending == "spawn" and getattr(spawner, "_spawn_future", None):
            try:
                await spawner._spawn_future
            except Exception:
                pass
        if spawner.active and not spawner.pending:
            await handler.stop_single_user(user, name)
    except Exception:
        handler.log.exception("Nie udalo sie zatrzymac serwera %s po wylogowaniu", user.name)


async def _handle_logout(self):
    user = self.current_user
    if not user:
        return
    now = datetime.utcnow()
    others = (
        self.db.query(orm.APIToken)
        .filter(orm.APIToken.user_id == user.id, orm.APIToken.session_id.isnot(None))
        .filter((orm.APIToken.expires_at.is_(None)) | (orm.APIToken.expires_at > now))
        .count()
    )
    if others:
        self.log.info("Wylogowanie %s: zostaly inne sesje (%s), serwer dziala dalej", user.name, others)
        return
    for name, spawner in user.spawners.items():
        if spawner.active:
            self.log.info("Ostatnie wylogowanie %s: zatrzymuje serwer", user.name)
            asyncio.ensure_future(_stop_after_logout(self, user, name, spawner))


LogoutHandler.handle_logout = _handle_logout
