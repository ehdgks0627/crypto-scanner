#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/.."

if [[ -f testbed/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source testbed/.env
  set +a
fi

: "${BOOTSTRAP_TOKEN:=testbed-validation-bootstrap-token}"
: "${POSTGRES_PASSWORD:=testbed-validation-postgres-password}"
: "${IPSEC_PSK:=testbed-validation-ipsec-psk}"
export BOOTSTRAP_TOKEN POSTGRES_PASSWORD IPSEC_PSK

testbed/scripts/check_env.sh
bash -n \
  testbed/scripts/check_env.sh \
  testbed/certs/generate.sh \
  testbed/services/web/entrypoint.sh \
  testbed/services/ssh/entrypoint.sh \
  testbed/services/ipsec/entrypoint.sh \
  testbed/services/db/entrypoint.sh
python3 -m compileall -q testbed/agent
python3 -m py_compile testbed/services/mail/mail_fixture.py
python3 -m unittest discover -s testbed/agent/tests
python3 -m json.tool testbed/expected_assets.json >/dev/null
python3 -m json.tool system/backend/fixtures/initial_targets.json >/dev/null
testbed/certs/generate.sh
docker compose -f testbed/docker-compose.yml config >/dev/null
docker compose --dry-run -f testbed/docker-compose.yml build >/dev/null 2>&1

echo "testbed compose validation passed"
