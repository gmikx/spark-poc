#!/usr/bin/env bash
# Startuje node obliczeniowy (tunel + worker Spark) na tej maszynie.
# Użycie: ./start-node.sh [plik-env]   (domyślnie .env.node; dla kolejnego node'a np. .env.node2
# z innym NODE_IP i TUN_ID). Działa na pierwszym planie; po ^C zatrzymuje i usuwa kontenery.
cd "$(dirname "$0")" || exit 1
ENV_FILE=${1:-.env.node}
[ -f "$ENV_FILE" ] || { echo "Brak pliku $ENV_FILE"; exit 1; }
PROJECT="sparkpoc-node-$(basename "$ENV_FILE" | sed 's/^\.env\.//; s/[^a-z0-9]/-/g')"
COMPOSE=(docker compose -p "$PROJECT" -f compose.node.yaml --env-file "$ENV_FILE")

trap ':' INT TERM
"${COMPOSE[@]}" up --build --abort-on-container-failure
echo "Zatrzymuję node ($PROJECT)…"
"${COMPOSE[@]}" down
