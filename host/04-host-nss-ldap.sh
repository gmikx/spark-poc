#!/usr/bin/env bash
# Uczy system hosta znać użytkowników z LDAP (ten sam serwer, którego używa stos), żeby grupą dostępu
# można było zarządzać zwykłymi komendami (usermod -aG, gpasswd), a ls -l pokazywał nazwy zamiast UID-ów.
# Parametry czyta z compose/.env: LDAP_URI, LDAP_BASE_DN, LDAP_USER_SEARCH_BASE, LDAP_BIND_DN, LDAP_BIND_PASSWORD,
# LDAP_TLS_REQCERT, LDAP_CA_FILE (te same co w stosie; bez nich działa symulowany LDAP z 127.0.0.1).
# Uruchom: sudo ./host/04-host-nss-ldap.sh    (na serwerze: sudo ~/scripts/04-host-nss-ldap.sh)
#
# Zmiany: pakiety libnss-ldapd i nslcd, /etc/nslcd.conf, wpis "ldap" w /etc/nsswitch.conf (passwd i group)
# oraz grupa dostępu. Kopia nsswitch: /etc/nsswitch.conf.bak-sparkpoc.
# Wycofanie: cp /etc/nsswitch.conf.bak-sparkpoc /etc/nsswitch.conf && systemctl stop nslcd
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Uruchom przez sudo: sudo $0"; exit 1; }
ENV_FILE=${ENV_FILE:-/opt/sparkpoc/compose/.env}
[ -r "$ENV_FILE" ] || { echo "Brak $ENV_FILE"; exit 1; }
getv() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -1 | sed -e 's/^"//' -e 's/"$//'; }
isset() { grep -q "^$1=" "$ENV_FILE"; }

URI=$(getv LDAP_URI); URI=${URI:-ldap://127.0.0.1}
BASE_DN=$(getv LDAP_BASE_DN); BASE_DN=${BASE_DN:-dc=poc,dc=local}
USER_BASE=$(getv LDAP_USER_SEARCH_BASE); USER_BASE=${USER_BASE:-ou=people,$BASE_DN}
REQCERT=$(getv LDAP_TLS_REQCERT); REQCERT=${REQCERT:-demand}
CA_FILE=$(getv LDAP_CA_FILE)
GROUP=$(getv ACCESS_GROUP); GROUP=${GROUP:-sparkusers}
if isset LDAP_BIND_DN; then
  BIND_DN=$(getv LDAP_BIND_DN); BIND_PW=$(getv LDAP_BIND_PASSWORD)
else  # symulacja: konto administratora z .env
  BIND_DN="cn=admin,$BASE_DN"; BIND_PW=$(getv LDAP_ADMIN_PASSWORD)
fi
# symulowany LDAP w kontenerze nasłuchuje tylko na hoście; ze stosu używa nazwy "openldap"
case "$URI" in ldap://openldap*) URI=ldap://127.0.0.1;; esac

DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libnss-ldapd nslcd

umask 077
{
  echo "uid nslcd"; echo "gid nslcd"
  echo "uri $URI"; echo "base $BASE_DN"
  if [ -n "$BIND_DN" ]; then echo "binddn $BIND_DN"; echo "bindpw $BIND_PW"; fi
  echo "tls_reqcert $([ "$REQCERT" = demand ] && echo demand || echo allow)"
  [ -z "$CA_FILE" ] || echo "tls_cacertfile $CA_FILE"
  echo "bind_timelimit 3"; echo "timelimit 5"
  echo "nss_initgroups_ignoreusers ALLLOCAL"
  echo "base passwd $USER_BASE"; echo "filter passwd (objectClass=posixAccount)"
  echo "base group $BASE_DN"; echo "filter group (objectClass=posixGroup)"
} > /etc/nslcd.conf
chown root:nslcd /etc/nslcd.conf
chmod 640 /etc/nslcd.conf
umask 022

[ -f /etc/nsswitch.conf.bak-sparkpoc ] || cp /etc/nsswitch.conf /etc/nsswitch.conf.bak-sparkpoc
for db in passwd group; do
  grep -Eq "^$db:.*\bldap\b" /etc/nsswitch.conf || sed -i -E "s/^($db:.*)$/\1 ldap/" /etc/nsswitch.conf
done

systemctl enable nslcd
systemctl restart nslcd
getent group "$GROUP" >/dev/null || groupadd "$GROUP"

echo
grep -E "^(passwd|group):" /etc/nsswitch.conf
echo "Test: getent passwd 4giza"
getent passwd 4giza || echo "(brak wpisu: sprawdź adres LDAP i dostępność serwera)"
echo
echo "Dalej:"
echo "  1. w compose/.env ustaw HOST_ETC_DIR=/etc i ACCESS_GROUP=$GROUP"
echo "  2. sudo usermod -aG $GROUP <login>        # kto ma dostęp"
echo "  3. ./stack.sh up                          # hub i bramka SSH czytają /etc hosta"
