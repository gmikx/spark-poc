#!/usr/bin/env bash
# Tworzy grupę systemową sparkadmins (panele administracyjne: Grafana, Prometheus, Spark UI).
# Członków dodaje się potem bez restartu: sudo usermod -aG sparkadmins <login>
# Uruchom: sudo ~/scripts/06-grupa-adminow.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Uruchom przez sudo: sudo $0"; exit 1; }
getent group sparkadmins >/dev/null || groupadd sparkadmins
getent group sparkadmins
