#!/usr/bin/env bash

demo_root_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

DEMO_ROOT_DIR="${DEMO_ROOT_DIR:-$(demo_root_dir)}"
DEMO_RUNNER="${DEMO_RUNNER:-auto}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-$DEMO_ROOT_DIR/system/.env}"
DEMO_COMPOSE_MINIMAL="${DEMO_COMPOSE_MINIMAL:-1}"
read -r -a DOCKER_CMD <<< "${DOCKER_CMD:-docker}"

demo_log() {
  printf '[demo] %s\n' "$*"
}

demo_fail() {
  printf '[demo] ERROR: %s\n' "$*" >&2
  exit 1
}

demo_is_truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

demo_compose_args() {
  local -a args=()
  if [[ -f "$COMPOSE_ENV_FILE" ]]; then
    args+=(--env-file "$COMPOSE_ENV_FILE")
  fi
  args+=(-f "$DEMO_ROOT_DIR/system/docker-compose.yml")
  if [[ "$DEMO_COMPOSE_MINIMAL" == "1" && -f "$DEMO_ROOT_DIR/system/docker-compose.minimal.yml" ]]; then
    args+=(-f "$DEMO_ROOT_DIR/system/docker-compose.minimal.yml")
  fi
  printf '%s\0' "${args[@]}"
}

demo_compose() {
  local -a args=()
  while IFS= read -r -d '' arg; do
    args+=("$arg")
  done < <(demo_compose_args)
  "${DOCKER_CMD[@]}" compose "${args[@]}" "$@"
}

demo_can_use_compose() {
  command -v "${DOCKER_CMD[0]}" >/dev/null 2>&1 || return 1
  demo_compose config >/dev/null 2>&1
}

demo_run_manage_compose() {
  demo_compose run --rm --entrypoint python backend manage.py "$@"
}

demo_run_manage_local() {
  local python_bin="${DEMO_PYTHON:-}"
  if [[ -z "$python_bin" ]]; then
    if [[ -x "$DEMO_ROOT_DIR/system/backend/.venv/bin/python" ]]; then
      python_bin="$DEMO_ROOT_DIR/system/backend/.venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
      python_bin="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
      python_bin="$(command -v python)"
    else
      demo_fail "python interpreter not found; set DEMO_PYTHON or use DEMO_RUNNER=compose"
    fi
  fi
  (
    cd "$DEMO_ROOT_DIR/system/backend"
    "$python_bin" manage.py "$@"
  )
}

demo_run_manage() {
  case "$DEMO_RUNNER" in
    compose)
      demo_run_manage_compose "$@"
      ;;
    local)
      demo_run_manage_local "$@"
      ;;
    auto)
      if demo_can_use_compose; then
        demo_run_manage_compose "$@"
      else
        demo_run_manage_local "$@"
      fi
      ;;
    *)
      demo_fail "unsupported DEMO_RUNNER=$DEMO_RUNNER (expected auto, compose, or local)"
      ;;
  esac
}

demo_dashboard_url() {
  if [[ -n "${DEMO_URL:-}" ]]; then
    printf '%s\n' "$DEMO_URL"
    return
  fi
  printf 'http://localhost:%s/\n' "${SYSTEM_WEB_PORT:-8088}"
}

demo_open_url() {
  local url="$1"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
  elif command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 &
  else
    demo_log "browser opener not found; open manually: $url"
  fi
}
