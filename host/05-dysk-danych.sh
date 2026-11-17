#!/usr/bin/env bash
# Przygotowuje drugi dysk na dane użytkowników i baz: partycja, ext4 (z obsługą limitów projektowych),
# wpis w fstab po UUID, katalogi dla stosu oraz zależność Dockera od zamontowania.
# Uruchom: sudo ~/scripts/05-dysk-danych.sh
# Dysk wybierany jest automatycznie (bez partycji i systemu plików, >100 GB, niezamontowany); skrypt pyta o potwierdzenie.
# Zmienne: MNT (domyślnie /srv/spark-data), DISK (wymusza urządzenie, np. /dev/sdb).
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Uruchom przez sudo: sudo $0"; exit 1; }
MNT=${MNT:-/srv/spark-data}

if mountpoint -q "$MNT"; then echo "$MNT jest już zamontowany:"; findmnt "$MNT"; DISK_DONE=1; fi

if [ -z "${DISK_DONE:-}" ]; then
  DISK=${DISK:-}
  if [ -z "$DISK" ]; then
    for d in $(lsblk -dnbo NAME,TYPE,SIZE | awk '$2=="disk" && $3>100*1024^3 {print $1}'); do
      [ -z "$(lsblk -nro FSTYPE,MOUNTPOINT /dev/$d | tr -d ' \n')" ] && [ "$(lsblk -nro NAME /dev/$d | wc -l)" = 1 ] && DISK=/dev/$d
    done
  fi
  [ -n "$DISK" ] || { echo "Nie znaleziono pustego dysku >100 GB. Podaj DISK=/dev/sdX."; exit 1; }
  lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT "$DISK"
  [ "$(lsblk -nro NAME "$DISK" | wc -l)" = 1 ] || { echo "$DISK ma partycje, przerywam."; exit 1; }
  [ -z "$(lsblk -nro FSTYPE,MOUNTPOINT "$DISK" | tr -d ' \n')" ] || { echo "$DISK ma system plików, przerywam."; exit 1; }
  read -r -p "Utworzyć partycję i ext4 na $DISK (WSZYSTKO TAM ZOSTANIE USUNIĘTE)? wpisz tak: " a
  [ "$a" = tak ] || { echo "Anulowano."; exit 1; }
  echo 'type=0FC63DAF-8483-4772-8E79-3D69D8477DE4' | sfdisk --label gpt "$DISK"
  udevadm settle
  PART=$(lsblk -nlo PATH,TYPE "$DISK" | awk '$2=="part"{print $1; exit}')
  mkfs.ext4 -L spark-data -O project,quota "$PART"
  UUID=$(blkid -s UUID -o value "$PART")
  mkdir -p "$MNT"
  grep -q "$UUID" /etc/fstab || echo "UUID=$UUID $MNT ext4 defaults,nofail,prjquota 0 2" >> /etc/fstab
  systemctl daemon-reload
  mount "$MNT"
fi

mkdir -p "$MNT"/{homes,cassandra-data,neo4j-data,spark-local-master,spark-local-worker,spark-local-worker2,shared-data}
mkdir -p /etc/systemd/system/docker.service.d
printf '[Unit]\nRequiresMountsFor=%s\n' "$MNT" > /etc/systemd/system/docker.service.d/spark-data.conf
systemctl daemon-reload
echo; findmnt "$MNT"; df -h "$MNT" | tail -1; grep spark-data /etc/fstab
echo
echo "Gotowe. Daj znać agentowi: przeniesie dane (stack.sh stop, kopia wolumenów, stack.sh up)."
