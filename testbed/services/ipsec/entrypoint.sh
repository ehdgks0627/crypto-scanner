#!/bin/sh
set -eu

: "${IPSEC_PSK:?IPSEC_PSK is required}"

escape_sed() {
  printf '%s' "$1" | sed 's/[\/&]/\\&/g'
}

sed "s/__IPSEC_PSK__/$(escape_sed "$IPSEC_PSK")/g" \
  /etc/swanctl/swanctl.conf.template > /etc/swanctl/swanctl.conf
chmod 600 /etc/swanctl/swanctl.conf

(
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if swanctl --load-all; then
      exit 0
    fi
    sleep 1
  done
  exit 1
) &

exec ipsec start --nofork
