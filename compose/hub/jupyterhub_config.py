import os

c = get_config()  # noqa: F821

c.JupyterHub.bind_url = "http://:8000"
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.hub_connect_ip = "jupyterhub"
c.JupyterHub.cookie_secret_file = "/srv/jupyterhub/cookie_secret"
c.JupyterHub.db_url = "sqlite:////srv/jupyterhub/jupyterhub.sqlite"

AUTH_MODE = os.environ.get("AUTH_MODE", "dummy")

if AUTH_MODE == "ldap":
    from ldapauthenticator import LDAPAuthenticator

    import sys

    sys.path.insert(0, "/etc/jupyterhub")
    from spark_provision import group_members

    ACCESS_GROUP = os.environ.get("ACCESS_GROUP", "sparkusers")
    GROUP_FILE = os.environ.get("ACCESS_GROUP_FILE", "/host-etc/group")

    class LocalAuthzLDAPAuthenticator(LDAPAuthenticator):
        """LDAP służy tylko do uwierzytelnienia (login i hasło). O dostępie decyduje grupa
        ACCESS_GROUP na serwerze (plik group hosta, czytany przy każdym logowaniu), więc
        zmiana członkostwa (np. usermod -aG) działa bez restartu huba.
        Administratorzy są dopuszczeni zawsze."""

        async def check_allowed(self, username, auth_model):
            if username in self.admin_users or username in group_members(GROUP_FILE, ACCESS_GROUP):
                return True
            self.log.info("Logowanie %s odrzucone: brak w grupie %s", username, ACCESS_GROUP)
            return False

    import ssl
    from urllib.parse import urlparse

    base_dn = os.environ["LDAP_BASE_DN"]
    LDAP_URI = urlparse(os.environ["LDAP_URI"])
    LDAP_TLS = LDAP_URI.scheme == "ldaps"
    LDAP_PORT = LDAP_URI.port or (636 if LDAP_TLS else 389)
    # puste LDAP_USER_SEARCH_BASE: DN użytkownika z szablonu (uid=<login>,ou=people,<base>), jak w symulacji;
    # ustawione: DN jest wyszukiwany (użytkownicy w wielu gałęziach, np. o=Stud, o=Staff)
    USER_SEARCH_BASE = os.environ.get("LDAP_USER_SEARCH_BASE", "")
    TLS_REQCERT = os.environ.get("LDAP_TLS_REQCERT", "demand")
    LDAP_CA_FILE = "/etc/jupyterhub/ldap-ca.pem" if os.environ.get("LDAP_CA_FILE") else None

    def tls_kwargs():
        if TLS_REQCERT in ("allow", "never"):
            return {"validate": ssl.CERT_NONE}
        return {"validate": ssl.CERT_REQUIRED, "ca_certs_file": LDAP_CA_FILE} if LDAP_CA_FILE else {}

    c.JupyterHub.authenticator_class = LocalAuthzLDAPAuthenticator
    c.LDAPAuthenticator.server_address = LDAP_URI.hostname
    c.LDAPAuthenticator.server_port = LDAP_PORT
    c.LDAPAuthenticator.valid_username_regex = r"^[a-z0-9][.a-z0-9_-]*$"
    c.LDAPAuthenticator.tls_strategy = "on_connect" if LDAP_TLS else "insecure"
    c.LDAPAuthenticator.tls_kwargs = tls_kwargs()
    if USER_SEARCH_BASE:
        c.LDAPAuthenticator.lookup_dn = True
        c.LDAPAuthenticator.user_search_base = USER_SEARCH_BASE
        c.LDAPAuthenticator.user_attribute = "uid"
        c.LDAPAuthenticator.lookup_dn_user_dn_attribute = "uid"
        c.LDAPAuthenticator.lookup_dn_search_user = os.environ.get("LDAP_BIND_DN", "")
        c.LDAPAuthenticator.lookup_dn_search_password = os.environ.get("LDAP_BIND_PASSWORD", "")
    else:
        c.LDAPAuthenticator.bind_dn_template = [f"uid={{username}},ou=people,{base_dn}"]
    c.Authenticator.admin_users = set(os.environ["HUB_ADMINS"].split(","))
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
c.DockerSpawner.name_template = "spark-user-{username}"
c.DockerSpawner.cmd = [
    "bash", "-c",
    "export SPARK_LOCAL_HOSTNAME=$(hostname -i | awk '{print $1}'); exec jupyterhub-singleuser \"$@\"", "--",
]
c.DockerSpawner.notebook_dir = "/home/jovyan/work"
c.DockerSpawner.volumes = {
    "spark-home-{username}": "/home/jovyan/work",
    "spark_shared-data": {"bind": "/home/jovyan/shared", "mode": "ro"},
}
c.DockerSpawner.mem_limit = os.environ["USER_MEM_LIMIT"]
c.DockerSpawner.cpu_limit = float(os.environ["USER_CPU_LIMIT"])
c.DockerSpawner.environment = {
    "CASSANDRA_HOST": "cassandra",
    "NEO4J_URI": "bolt://neo4j:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD", "pocpassword"),
}


def ldap_identity_hook(spawner):
    from ldap3 import Connection, Server, Tls
    from ldap3.utils.conv import escape_filter_chars

    bind_dn = os.environ.get("LDAP_BIND_DN") or None
    conn = Connection(
        Server(
            LDAP_URI.hostname,
            port=LDAP_PORT,
            use_ssl=LDAP_TLS,
            tls=Tls(**tls_kwargs()) if LDAP_TLS else None,
        ),
        user=bind_dn,
        password=os.environ.get("LDAP_BIND_PASSWORD") if bind_dn else None,
        auto_bind=True,
    )
    conn.search(
        USER_SEARCH_BASE or f"ou=people,{os.environ['LDAP_BASE_DN']}",
        f"(uid={escape_filter_chars(spawner.user.name)})",
        attributes=["uidNumber", "gidNumber", "homeDirectory", "loginShell"],
    )
    entry = conn.entries[0]
    uid, gid, home = int(entry.uidNumber.value), int(entry.gidNumber.value), entry.homeDirectory.value
    if not os.path.isdir(home):
        try:
            os.makedirs(home)
            os.chmod(home, 0o755)
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


def account_hook(spawner):
    import sys

    sys.path.insert(0, "/etc/jupyterhub")
    import spark_provision as prov

    role, password = prov.ensure_cassandra_account(spawner.user.name)
    uid, gid = (int(x) for x in spawner.extra_create_kwargs["user"].split(":"))
    prov.write_connection_file(spawner.environment["HOME"], uid, gid, spawner.user.name)

    spawner.environment = {
        **spawner.environment,
        "CASSANDRA_USER": role,
        "CASSANDRA_PASSWORD": password,
        "CASSANDRA_KEYSPACE": role,
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": os.environ["NEO4J_PASSWORD"],
        "NEO4J_GRAPH_PREFIX": role + "_",
    }


def pre_spawn(spawner):
    ldap_identity_hook(spawner)
    account_hook(spawner)


if AUTH_MODE == "ldap":
    c.DockerSpawner.volumes = {
        os.environ.get("HOMES_VOLUME", "spark_homes"): "/home",
        "spark_nss": {"bind": "/nss", "mode": "ro"},
        "spark_shared-data": {"bind": "/shared", "mode": "ro"},
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
