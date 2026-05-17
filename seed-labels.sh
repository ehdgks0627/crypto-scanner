#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/demo-lib.sh
source "$ROOT_DIR/scripts/demo-lib.sh"

demo_log "seeding final-demo host labels"
demo_run_manage seed_demo_labels "$@"
