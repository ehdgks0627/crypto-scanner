#!/bin/sh
set -eu

mkdir -p /etc/nginx/ssl
if [ -f /etc/testbed/certs/web/legacy-rsa1024.key ] && [ -f /etc/testbed/certs/web/legacy-rsa1024.crt ]; then
  cat /etc/testbed/certs/web/legacy-rsa1024.key /etc/testbed/certs/web/legacy-rsa1024.crt > /etc/nginx/ssl/legacy-rsa1024.pem
  chmod 600 /etc/nginx/ssl/legacy-rsa1024.pem
fi

python3 /opt/testbed-agent/mock_agent.py &
exec nginx -g 'daemon off;'
