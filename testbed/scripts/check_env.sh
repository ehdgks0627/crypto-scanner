#!/bin/sh
set -eu

check_required_secret() {
  name="$1"
  value="$(eval "printf '%s' \"\${$name:-}\"")"
  if [ -z "$value" ]; then
    printf '%s\n' "$name is required." >&2
    exit 1
  fi
  case "$value" in
    replace-with-*|dev-bootstrap-token|testbed-psk|pqc)
      printf '%s\n' "$name must be changed from the example/default value." >&2
      exit 1
      ;;
  esac
}

check_required_secret BOOTSTRAP_TOKEN
check_required_secret POSTGRES_PASSWORD
check_required_secret IPSEC_PSK
