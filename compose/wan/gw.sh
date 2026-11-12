#!/bin/bash
# Strona serwera: sshd przyjmujący tunel L3 (ssh -w) od dołączanych node'ów.
set -e
mkdir -p /etc/ssh/hostkeys
[ -f /etc/ssh/hostkeys/ed25519 ] || ssh-keygen -q -t ed25519 -N "" -f /etc/ssh/hostkeys/ed25519
cat > /etc/ssh/sshd_config <<CFG
Port 22
HostKey /etc/ssh/hostkeys/ed25519
PermitRootLogin prohibit-password
PasswordAuthentication no
StrictModes no
PermitTunnel point-to-point
AllowTcpForwarding no
AuthorizedKeysFile /etc/ssh/authorized_keys
ClientAliveInterval 15
ClientAliveCountMax 3
CFG
exec /usr/sbin/sshd -D -e
