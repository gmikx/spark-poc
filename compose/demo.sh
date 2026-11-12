#!/usr/bin/env bash
# Jedna komenda: stawia cały PoC lokalnie (JupyterHub + LDAP + Spark + Cassandra + Neo4j + dashboard).
#   ./demo.sh            start (pierwszy raz buduje obrazy: kilka-kilkanaście minut)
#   ./demo.sh --nfs      to samo + symulowany filer NFS (wymaga Docker Desktop lub Linuksa z modułem nfsd)
#   ./demo.sh --no-node  bez dodatkowego node'a obliczeniowego (domyślnie startuje drugi node, patrz niżej)
#
# Dodatkowy node to osobny kontener w osobnej sieci Dockera, który łączy się z klastrem tak jak
# zdalna maszyna: przez tunel L3 (wss -> ssh -w) i dopiero tam dostaje adres 10.77.0.200.
#   ./demo.sh down       zatrzymanie i usunięcie kontenerów (dane zostają)
#   ./demo.sh clean      jak down + usunięcie danych (wolumeny)
#   ./demo.sh status     stan usług
set -euo pipefail
cd "$(dirname "$0")"

ACTION=up; NFS=0; NODE=1
for a in "$@"; do
  case "$a" in
    --nfs) NFS=1 ;;
    --no-node) NODE=0 ;;
    up|down|clean|status|logs) ACTION=$a ;;
    *) echo "Nieznany argument: $a"; exit 1 ;;
  esac
done

command -v docker >/dev/null || { echo "Brak Dockera. Zainstaluj Docker Desktop lub Docker Engine."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Brak wtyczki 'docker compose' (v2)."; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker nie jest uruchomiony. Włącz Docker Desktop / demona."; exit 1; }

FILES=(-f compose.yaml -f compose.ldap.yaml)
[ "$NFS" = 1 ] && FILES+=(-f compose.nfs.yaml)
[ "$NODE" = 1 ] && FILES+=(-f compose.cluster.yaml)
export LOCAL_NODE_NAME="${LOCAL_NODE_NAME:-$(hostname -s)}"
export NODE_NAMES="10.77.0.200=dodatkowy-node"
export WAN_AUTHORIZED_KEYS=./wan/demo/authorized_keys
DC=(docker compose "${FILES[@]}")
NODE_ENV=.env.node.demo
node_dc() {
  if [ -f "$NODE_ENV" ]; then
    docker compose -p sparkpoc-node -f compose.node.yaml --env-file "$NODE_ENV" "$@"
  else
    NODE_IP=x WAN_URL=x WAN_PATH_SECRET=x docker compose -p sparkpoc-node -f compose.node.yaml "$@"
  fi
}

case "$ACTION" in
  status) "${DC[@]}" ps; exit ;;
  logs)   "${DC[@]}" logs -f --tail=50; exit ;;
  down)   node_dc down --remove-orphans; "${DC[@]}" down --remove-orphans; docker rm -f $(docker ps -aq --filter name=sparkpoc-user-) 2>/dev/null || true; exit ;;
  clean)  node_dc down -v --remove-orphans; rm -rf wan/demo "$NODE_ENV"; "${DC[@]}" down -v --remove-orphans; docker rm -f $(docker ps -aq --filter name=sparkpoc-user-) 2>/dev/null || true
          docker volume rm $(docker volume ls -q --filter name=sparkpoc-home-) 2>/dev/null || true; exit ;;
esac

[ -f .env ] || cp .env.example .env
grep -q '^WAN_PATH_SECRET=' .env || printf 'WAN_PATH_SECRET=%s\n' "$(head -c16 /dev/urandom | od -An -tx1 | tr -d ' \n')" >> .env

mem=$(docker info --format '{{.MemTotal}}')
if [ "$mem" -lt 6000000000 ]; then
  echo "UWAGA: Docker ma tylko $((mem / 1000000000)) GB RAM, zalecane jest min. 6 GB (Docker Desktop: Settings > Resources)."
fi

ensure_keys() {
  [ -f wan/demo/id_ed25519 ] && return 0
  mkdir -p wan/demo
  docker compose "${FILES[@]}" build wan-gw >/dev/null
  docker run --rm -v "$PWD/wan/demo:/k" --entrypoint sh sparkpoc/wan:latest -c \
    "ssh-keygen -q -t ed25519 -N '' -C demo-node -f /k/id_ed25519 && cp /k/id_ed25519.pub /k/authorized_keys && chown -R $(id -u):$(id -g) /k && chmod 600 /k/id_ed25519"
}

start_node() {
  local secret; secret=$(sed -n 's/^WAN_PATH_SECRET=//p' .env | tail -1)
  cat > "$NODE_ENV" <<ENV
NODE_IP=10.77.0.200
TUN_ID=0
WAN_URL=ws://host.docker.internal:8443
WAN_PATH_SECRET=$secret
WAN_KEY_FILE=./wan/demo/id_ed25519
ENV
  node_dc up -d --build --wait --wait-timeout 300 || return 1
  local i
  for i in $(seq 40); do
    [ "$(curl -s localhost:8080/json/ | grep -o '"state" *: *"ALIVE"' | wc -l)" -ge 2 ] && return 0
    sleep 3
  done
  return 1
}

[ "$NODE" = 1 ] && ensure_keys
echo "Budowanie i start (pierwszy raz potrwa kilka-kilkanaście minut)..."
if [ "$NFS" = 1 ]; then
  "${DC[@]}" up -d --build nfs
fi
"${DC[@]}" up -d --build --wait --wait-timeout 900

if [ "$NODE" = 1 ]; then
  echo "Start dodatkowego node'a (osobny kontener, połączenie przez tunel L3)..."
  if start_node; then
    echo "Dodatkowy node jest podpięty do klastra."
  else
    echo "UWAGA: dodatkowy node nie podłączył się (reszta działa). Szczegóły: docker logs sparkpoc-node-tunnel-1"
  fi
fi

cat <<MSG

Gotowe. Wejdź w przeglądarce:

  JupyterHub          http://localhost:8000
      4alice / alice123   (administrator)
      4bob   / bob123     (zwykły użytkownik)
  Dashboard topologii http://localhost:8088
  Spark Master UI     http://localhost:8080 (z dodatkowym node'em widać tu dwóch workerów)
  Neo4j Browser       http://localhost:7474   (neo4j / pocpassword)

Pierwsze zalogowanie tworzy kontener studenta (kilka sekund). Notebooki Pythona i Scali
mają gotowe połączenie ze Sparkiem. Zatrzymanie: ./demo.sh down
MSG
