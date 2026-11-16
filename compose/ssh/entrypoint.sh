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
cat > /etc/nslcd.conf <<CONF
uid nslcd
gid nslcd
uri ldap://${LDAP_HOST}
base ${LDAP_BASE_DN}
binddn ${LDAP_BIND_DN}
bindpw ${LDAP_BIND_PASSWORD}
base passwd ou=people,${LDAP_BASE_DN}
filter passwd (objectClass=posixAccount)
base group ou=groups,${LDAP_BASE_DN}
filter group (objectClass=posixGroup)
CONF
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
