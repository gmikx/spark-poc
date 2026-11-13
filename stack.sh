#!/usr/bin/env bash
# Zarządzanie stosem na serwerze (odpowiednik demo.sh dla instalacji "na stałe"):
# JupyterHub + LDAP + NFS + Spark + Cassandra + Neo4j + dashboard.
#
#   ./stack.sh up          zbuduj obrazy i uruchom stos (pierwsze uruchomienie, po zmianie kodu)
#   ./stack.sh start       uruchom zatrzymany stos (bez budowania)
#   ./stack.sh stop        zatrzymaj stos i sesje studentów; dane (wolumeny) zostają
#   ./stack.sh restart     stop + start
#   ./stack.sh status      stan kontenerów, workerów Sparka i sesji studentów
#   ./stack.sh logs [usługa]   logi (na żywo)
#   ./stack.sh down        usuń kontenery i sieć (wolumeny z danymi zostają)
#
# Zestaw plików compose można zmienić w .env: STACK_FILES="compose.yaml compose.ldap.yaml compose.nfs.yaml"
# (dodaj compose.cluster.yaml, żeby przyjmować dodatkowe node'y; usuń compose.nfs.yaml, żeby pominąć NFS).
set -euo pipefail
cd "$(dirname "$0")/compose"
umask 002

[ -f .env ] || { echo "Brak pliku .env (skopiuj .env.example i ustaw własne hasła)."; exit 1; }
STACK_FILES=$(sed -n 's/^STACK_FILES=//p' .env | tail -1 | tr -d '"')
STACK_FILES=${STACK_FILES:-compose.yaml compose.ldap.yaml compose.nfs.yaml}
FILES=(); for f in $STACK_FILES; do FILES+=(-f "$f"); done
DC=(docker compose "${FILES[@]}")
HAS_NFS=0; case " $STACK_FILES " in *" compose.nfs.yaml "*) HAS_NFS=1 ;; esac

remove_sessions() {
  local ids; ids=$(docker ps -aq --filter name=sparkpoc-user- || true)
  [ -z "$ids" ] || docker rm -f $ids >/dev/null
}

bring_up() {
  # Wolumen NFS montuje demon Dockera przy tworzeniu kontenera, więc serwer NFS musi działać wcześniej.
  [ "$HAS_NFS" = 1 ] && "${DC[@]}" up -d nfs "$@" && sleep 5
  "${DC[@]}" up -d --wait --wait-timeout 600 "$@"
}

CMD=${1:-status}; shift || true
case "$CMD" in
  up)      [ "$HAS_NFS" = 1 ] && "${DC[@]}" up -d --build nfs && sleep 5
           "${DC[@]}" up -d --build --wait --wait-timeout 900 ;;
  start)   bring_up ;;
  stop)    remove_sessions; "${DC[@]}" stop ;;
  restart) remove_sessions; "${DC[@]}" stop; bring_up ;;
  down)    remove_sessions; "${DC[@]}" down --remove-orphans ;;
  logs)    "${DC[@]}" logs -f --tail=100 "$@" ;;
  status)
    "${DC[@]}" ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
    echo
    users=$(docker ps --filter name=sparkpoc-user- --format '{{.Names}}' | sed 's/sparkpoc-user-//' | paste -sd, -)
    echo "Sesje studentów: ${users:-brak}"
    if workers=$(curl -fsS -m 5 localhost:8080/json/ 2>/dev/null); then
      echo "$workers" | python3 -c 'import sys, json
d = json.load(sys.stdin)
print("Spark master:", d["status"], "| rdzenie %s/%s" % (d["coresused"], d["cores"]))
for w in d["workers"]:
    print("  worker %s %s, rdzenie %s/%s" % (w["host"], w["state"], w["coresused"], w["cores"]))'
    else
      echo "Spark master: niedostępny"
    fi
    for p in 8000:JupyterHub 8088:dashboard; do
      code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 "localhost:${p%%:*}/" || true)
      echo "${p#*:}: HTTP $code"
    done ;;
  *) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
