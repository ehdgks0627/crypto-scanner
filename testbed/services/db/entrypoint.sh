#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="/var/lib/postgresql/testbed-certs"
mkdir -p "$CERT_DIR"

if [[ -f /etc/testbed/db-certs/server.crt && -f /etc/testbed/db-certs/server.key ]]; then
  cp /etc/testbed/db-certs/server.crt "$CERT_DIR/server.crt"
  cp /etc/testbed/db-certs/server.key "$CERT_DIR/server.key"
  chown postgres:postgres "$CERT_DIR/server.crt" "$CERT_DIR/server.key"
  chmod 600 "$CERT_DIR/server.key"
fi
if [[ -f /etc/testbed/db-certs/keystore.p12 ]]; then
  cp /etc/testbed/db-certs/keystore.p12 /var/lib/postgresql/keystore.p12
  chown postgres:postgres /var/lib/postgresql/keystore.p12
  chmod 600 /var/lib/postgresql/keystore.p12
fi

python3 /opt/testbed-agent/mock_agent.py &

exec docker-entrypoint.sh "$@" \
  -c config_file=/etc/testbed/postgresql.conf \
  -c hba_file=/etc/testbed/pg_hba.conf \
  -c ssl=on \
  -c ssl_cert_file="$CERT_DIR/server.crt" \
  -c ssl_key_file="$CERT_DIR/server.key"
