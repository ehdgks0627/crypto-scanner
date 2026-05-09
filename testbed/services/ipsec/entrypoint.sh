#!/bin/sh
set -eu

: "${IPSEC_PSK:?IPSEC_PSK is required}"

escape_sed() {
  printf '%s' "$1" | sed 's/[\/&]/\\&/g'
}

sed "s/__IPSEC_PSK__/$(escape_sed "$IPSEC_PSK")/g" \
  /etc/swanctl/swanctl.conf.template > /etc/swanctl/swanctl.conf
chmod 600 /etc/swanctl/swanctl.conf

/charon --debug-dmn 1 &
charon_pid="$!"

cleanup() {
  kill "$charon_pid" 2>/dev/null || true
  wait "$charon_pid" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

loaded=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if swanctl --load-all; then
    loaded=1
    break
  fi
  sleep 1
done

if [ "$loaded" != "1" ]; then
  exit 1
fi

wait "$charon_pid"
