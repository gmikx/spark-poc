"""Bramka logowania do paneli administracyjnych (nginx auth_request).

Logowanie: login i hasło z LDAP-a (Basic). Dostęp mają tylko administratorzy: konta z HUB_ADMINS albo członkowie
grupy ADMIN_GROUP na serwerze (plik group hosta, czytany przy każdym żądaniu, więc usermod -aG działa bez restartu).
Po sukcesie zwraca X-WEBAUTH-USER (Grafana loguje się z tego nagłówka).
"""
import base64
import hashlib
import os
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from ldap3 import Connection, Server, Tls
from ldap3.utils.conv import escape_filter_chars

LDAP_URI = urlparse(os.environ["LDAP_URI"])
USE_SSL = LDAP_URI.scheme == "ldaps"
PORT = LDAP_URI.port or (636 if USE_SSL else 389)
SEARCH_BASE = os.environ.get("LDAP_USER_SEARCH_BASE") or f"ou=people,{os.environ['LDAP_BASE_DN']}"
BIND_DN = os.environ.get("LDAP_BIND_DN") or None
BIND_PW = os.environ.get("LDAP_BIND_PASSWORD") or None
VERIFY = os.environ.get("LDAP_TLS_REQCERT", "demand") not in ("allow", "never")
GROUP_FILE = os.environ.get("ACCESS_GROUP_FILE", "/host-etc/group")
ADMIN_GROUP = os.environ.get("ADMIN_GROUP", "sparkadmins")
STATIC_ADMINS = {a.strip() for a in os.environ.get("HUB_ADMINS", "").split(",") if a.strip()}
MAX_FAILS, WINDOW, CACHE_TTL = 5, 300, 60

fails = {}
cache = {}


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%S"), msg, flush=True)


def admins():
    members = set()
    try:
        with open(GROUP_FILE) as f:
            for line in f:
                p = line.rstrip("\n").split(":")
                if len(p) >= 4 and p[0] == ADMIN_GROUP:
                    members = {m.strip() for m in p[3].split(",") if m.strip()}
    except OSError:
        pass
    return STATIC_ADMINS | members


def server():
    tls = Tls(validate=ssl.CERT_REQUIRED if VERIFY else ssl.CERT_NONE) if USE_SSL else None
    return Server(LDAP_URI.hostname, port=PORT, use_ssl=USE_SSL, tls=tls, connect_timeout=8)


def ldap_ok(login, password):
    conn = Connection(server(), user=BIND_DN, password=BIND_PW if BIND_DN else None, auto_bind=True, receive_timeout=10)
    conn.search(SEARCH_BASE, f"(uid={escape_filter_chars(login)})", attributes=["uid"])
    if len(conn.entries) != 1:
        return False
    dn = conn.entries[0].entry_dn
    conn.unbind()
    try:
        return Connection(server(), user=dn, password=password, auto_bind=True, receive_timeout=10).bound
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, headers=()):
        self.send_response(code)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        ip = self.headers.get("X-Real-IP", self.client_address[0])
        challenge = [("WWW-Authenticate", 'Basic realm="Spark admin"')]
        try:
            kind, _, raw = (self.headers.get("Authorization") or "").partition(" ")
            login, _, password = base64.b64decode(raw).decode().partition(":") if kind.lower() == "basic" else ("", "", "")
        except Exception:
            login = password = ""
        if not login or not password:
            return self.reply(401, challenge)
        key = (ip, login)
        now = time.time()
        recent = [t for t in fails.get(key, []) if now - t < WINDOW]
        if len(recent) >= MAX_FAILS:
            log(f"BLOKADA {login} z {ip}: za duzo nieudanych prob")
            return self.reply(403)
        if login not in admins():
            fails[key] = recent + [now]
            log(f"ODMOWA {login} z {ip}: nie jest administratorem")
            return self.reply(403)
        token = hashlib.sha256(f"{login}\0{password}".encode()).hexdigest()
        cached = cache.get(login)
        if cached and cached[0] == token and now < cached[1]:
            return self.reply(200, [("X-WEBAUTH-USER", login)])
        try:
            ok = ldap_ok(login, password)
        except Exception as e:
            log(f"BLAD LDAP: {type(e).__name__}: {e}")
            return self.reply(503)
        if not ok:
            fails[key] = recent + [now]
            log(f"BLEDNE HASLO {login} z {ip}")
            return self.reply(401, challenge)
        fails.pop(key, None)
        cache[login] = (token, now + CACHE_TTL)
        log(f"OK {login} z {ip}")
        self.reply(200, [("X-WEBAUTH-USER", login)])

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
