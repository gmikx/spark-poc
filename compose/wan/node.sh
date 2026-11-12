#!/bin/bash
# Strona dołączanego node'a: tunel wss (wstunnel) -> ssh -w (tun L3) -> adres NODE_IP w sieci klastra.
set -u
ID=${TUN_ID:-0}
: "${NODE_IP:?}" "${WAN_URL:?}" "${WAN_PATH_SECRET:?}"
KEY=/run/wan/id_ed25519
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -p 2223"

ip addr add "$NODE_IP/32" dev lo 2>/dev/null || true
while true; do
  wstunnel client -L "tcp://127.0.0.1:2223:wan-gw:22" -P "$WAN_PATH_SECRET" "$WAN_URL" &
  WS=$!
  sleep 3
  (
    for _ in $(seq 30); do ip link show "tun$ID" >/dev/null 2>&1 && break; sleep 1; done
    ip addr add "10.254.$ID.2" peer "10.254.$ID.1" dev "tun$ID"
    ip link set "tun$ID" up
    ip route replace "${CLUSTER_SUBNET:-10.77.0.0/24}" dev "tun$ID" src "$NODE_IP"
  ) &
  sleep infinity | $SSH -w "$ID:$ID" root@127.0.0.1 \
    "ip addr add 10.254.$ID.1 peer 10.254.$ID.2 dev tun$ID && ip link set tun$ID up && ip route replace $NODE_IP/32 dev tun$ID && exec cat >/dev/null"
  echo "tunel rozlaczony, ponawiam za 5 s" >&2
  kill $WS 2>/dev/null; wait 2>/dev/null
  sleep 5
done
