#!/bin/bash
set -euo pipefail

mkdir -p /export /data/home /var/lib/nfs/v4recovery
mountpoint -q /proc/fs/nfsd || mount -t nfsd nfsd /proc/fs/nfsd

# Korzeń NFSv4 (fsid=0) nie może leżeć na overlayfs, więc jest tmpfs. Dane (wolumen) podpinamy pod /export/home.
mountpoint -q /export || mount -t tmpfs tmpfs /export
mkdir -p /export/home
mountpoint -q /export/home || mount --bind /data/home /export/home

for spec in ${SEED_HOMES:-}; do
  IFS=: read -r rel uid gid <<<"$spec"
  parent="/export/home/$(dirname "$rel")"
  mkdir -p "$parent"
  chmod 755 "$parent"
  if [ ! -d "/export/home/$rel" ]; then
    mkdir -p "/export/home/$rel"
    chown "$uid:$gid" "/export/home/$rel"
    chmod 755 "/export/home/$rel"
  fi
done

cat > /etc/exports <<EXPORTS
/export ${NFS_CLIENTS}(ro,fsid=0,no_subtree_check,crossmnt)
/export/home ${NFS_CLIENTS}(rw,sync,no_subtree_check,root_squash,fsid=1)
EXPORTS

rpc.nfsd -N 3 -V 4 -V 4.1 -V 4.2 8
exportfs -rav
exec rpc.mountd -F -N 3 -V 4
