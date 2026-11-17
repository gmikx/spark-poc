#!/bin/sh
# Bez własnego certyfikatu (/certs/tls.crt i tls.key) generuje tymczasowy, samopodpisany.
set -e
mkdir -p /certs
if [ ! -s /certs/tls.crt ] || [ ! -s /certs/tls.key ]; then
  echo "Brak /certs/tls.crt, generuję certyfikat samopodpisany (tylko do testów)"
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 -subj "/CN=spark" \
    -keyout /certs/tls.key -out /certs/tls.crt 2>/dev/null
fi
