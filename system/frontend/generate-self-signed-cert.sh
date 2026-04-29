#!/bin/sh
set -eu

cert_dir=${TLS_CERT_DIR:-/etc/nginx/certs}
cert_file=${TLS_CERT_FILE:-$cert_dir/server.crt}
key_file=${TLS_CERT_KEY_FILE:-$cert_dir/server.key}
cert_cn=${TLS_CERT_CN:-localhost}
cert_san=${TLS_CERT_SAN:-DNS:localhost,IP:127.0.0.1}
cert_days=${TLS_CERT_DAYS:-365}

if [ -f "$cert_file" ] && [ -f "$key_file" ]; then
  exit 0
fi

mkdir -p "$cert_dir"
openssl req \
  -x509 \
  -nodes \
  -newkey rsa:2048 \
  -days "$cert_days" \
  -keyout "$key_file" \
  -out "$cert_file" \
  -subj "/CN=$cert_cn" \
  -addext "subjectAltName=$cert_san"

chmod 600 "$key_file"
chmod 644 "$cert_file"
