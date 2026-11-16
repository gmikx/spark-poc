#!/bin/bash
set -euo pipefail

# Dane dla skryptów PAM (uruchamianych przez sshd bez środowiska kontenera).
umask 077
{
  for v in CASSANDRA_HOST CASSANDRA_ADMIN_USER CASSANDRA_ADMIN_PASSWORD CASSANDRA_PASSWORD_SECRET NEO4J_URI NEO4J_PASSWORD; do
    echo "$v=${!v:-}"
  done
} > /etc/sparkpoc/env
echo "${LDAP_ADMINS:-}" | tr ',' '\n' > /etc/sparkpoc/admins
echo "${ACCESS_GROUP:-sparkusers}" > /etc/sparkpoc/access_group
# katalog z plikami hosta jest niedostępny dla zwykłych użytkowników sesji SSH (czyta go tylko root)
chmod 700 /run/sparkpoc-host
umask 022

# nslcd: użytkownicy z LDAP widziani jako konta systemowe (NSS) i uwierzytelnianie (PAM)
USER_BASE=${LDAP_USER_SEARCH_BASE:-ou=people,${LDAP_BASE_DN}}
{
  echo "uid nslcd"
  echo "gid nslcd"
  echo "uri ${LDAP_URI}"
  echo "base ${LDAP_BASE_DN}"
  if [ -n "${LDAP_BIND_DN:-}" ]; then
    echo "binddn ${LDAP_BIND_DN}"
    echo "bindpw ${LDAP_BIND_PASSWORD:-}"
  fi
  # allow: bez weryfikacji certyfikatu (jak ldap_tls_reqcert=allow w sssd); demand: weryfikacja wg LDAP_CA_FILE
  echo "tls_reqcert $([ "${LDAP_TLS_REQCERT:-demand}" = demand ] && echo demand || echo allow)"
  [ -z "${LDAP_CA_FILE:-}" ] || echo "tls_cacertfile /etc/ssl/ldap-ca.pem"
  echo "base passwd ${USER_BASE}"
  echo "filter passwd (objectClass=posixAccount)"
  echo "base group ${LDAP_BASE_DN}"
  echo "filter group (objectClass=posixGroup)"
} > /etc/nslcd.conf
chmod 600 /etc/nslcd.conf
mkdir -p /run/nslcd && chown nslcd:nslcd /run/nslcd
# nslcd przy starcie zamyka wszystkie możliwe deskryptory; w kontenerze limit jest ogromny, więc bez tego się zawiesza
( ulimit -n 1024; nslcd )

mkdir -p /etc/ssh/hostkeys
[ -f /etc/ssh/hostkeys/ssh_host_ed25519_key ] || ssh-keygen -q -t ed25519 -N "" -f /etc/ssh/hostkeys/ssh_host_ed25519_key
cat > /etc/ssh/sshd_config <<'CONF'
Port 22
HostKey /etc/ssh/hostkeys/ssh_host_ed25519_key
UsePAM yes
PasswordAuthentication yes
PubkeyAuthentication yes
PermitRootLogin no
KbdInteractiveAuthentication no
X11Forwarding no
AllowTcpForwarding no
PrintMotd no
Subsystem sftp /usr/lib/openssh/sftp-server
ClientAliveInterval 60
ClientAliveCountMax 5
AuthorizedKeysFile .ssh/authorized_keys
CONF
exec /usr/sbin/sshd -D -e
