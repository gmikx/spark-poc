#!/usr/bin/env bash
# Jedna komenda: stawia cały PoC lokalnie (JupyterHub + LDAP + Spark + Cassandra + Neo4j + dashboard).
#   ./demo.sh            start (pierwszy raz buduje obrazy: kilka-kilkanaście minut)
#   ./demo.sh --nfs      to samo + symulowany filer NFS (wymaga Docker Desktop lub Linuksa z modułem nfsd)
#   ./demo.sh down       zatrzymanie i usunięcie kontenerów (dane zostają)
#   ./demo.sh clean      jak down + usunięcie danych (wolumeny)
#   ./demo.sh status     stan usług
set -euo pipefail
cd "$(dirname "$0")"

ACTION=up; NFS=0
for a in "$@"; do
  case "$a" in
    --nfs) NFS=1 ;;
    up|down|clean|status|logs) ACTION=$a ;;
    *) echo "Nieznany argument: $a"; exit 1 ;;
  esac
done

command -v docker >/dev/null || { echo "Brak Dockera. Zainstaluj Docker Desktop lub Docker Engine."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Brak wtyczki 'docker compose' (v2)."; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker nie jest uruchomiony. Włącz Docker Desktop / demona."; exit 1; }

FILES=(-f compose.yaml -f compose.ldap.yaml)
[ "$NFS" = 1 ] && FILES+=(-f compose.nfs.yaml)
export LOCAL_NODE_NAME="${LOCAL_NODE_NAME:-$(hostname -s)}"
DC=(docker compose "${FILES[@]}")

case "$ACTION" in
  status) "${DC[@]}" ps; exit ;;
  logs)   "${DC[@]}" logs -f --tail=50; exit ;;
  down)   "${DC[@]}" down --remove-orphans; docker rm -f $(docker ps -aq --filter name=sparkpoc-user-) 2>/dev/null || true; exit ;;
  clean)  "${DC[@]}" down -v --remove-orphans; docker rm -f $(docker ps -aq --filter name=sparkpoc-user-) 2>/dev/null || true
          docker volume rm $(docker volume ls -q --filter name=sparkpoc-home-) 2>/dev/null || true; exit ;;
esac

[ -f .env ] || cp .env.example .env

mem=$(docker info --format '{{.MemTotal}}')
if [ "$mem" -lt 6000000000 ]; then
  echo "UWAGA: Docker ma tylko $((mem / 1000000000)) GB RAM, zalecane jest min. 6 GB (Docker Desktop: Settings > Resources)."
fi

echo "Budowanie i start (pierwszy raz potrwa kilka-kilkanaście minut)..."
if [ "$NFS" = 1 ]; then
  "${DC[@]}" up -d --build nfs
fi
"${DC[@]}" up -d --build --wait --wait-timeout 900

cat <<MSG

Gotowe. Wejdź w przeglądarce:

  JupyterHub          http://localhost:8000
      4alice / alice123   (administrator)
      4bob   / bob123     (zwykły użytkownik)
  Dashboard topologii http://localhost:8088
  Spark Master UI     http://localhost:8080
  Neo4j Browser       http://localhost:7474   (neo4j / pocpassword)

Pierwsze zalogowanie tworzy kontener studenta (kilka sekund). Notebooki Pythona i Scali
mają gotowe połączenie ze Sparkiem. Zatrzymanie: ./demo.sh down
MSG
