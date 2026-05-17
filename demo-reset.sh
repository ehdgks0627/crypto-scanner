#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/demo-lib.sh
source "$ROOT_DIR/scripts/demo-lib.sh"

DEMO_FLUSH_DB="${DEMO_FLUSH_DB:-0}"
OPEN_DEMO="${OPEN_DEMO:-0}"

if demo_is_truthy "$DEMO_FLUSH_DB"; then
  demo_log "flushing database before demo seed"
  demo_run_manage flush --noinput
fi

demo_log "running database migrations"
demo_run_manage migrate --noinput

demo_log "seeding deterministic testbed demo data"
demo_run_manage seed_testbed_demo --reset

demo_log "seeding final-demo host labels"
demo_run_manage seed_demo_labels

url="$(demo_dashboard_url)"
demo_log "demo reset complete"
demo_log "dashboard: $url"

if demo_is_truthy "$OPEN_DEMO"; then
  demo_open_url "$url"
fi
