#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
read -r -a DOCKER_CMD <<< "${DOCKER_CMD:-docker}"

BACKEND_PORT="${BACKEND_PORT:-18000}"
BOOTSTRAP_TOKEN="${BOOTSTRAP_TOKEN:-dev-bootstrap-token}"
RESET_SYSTEM_DB="${RESET_SYSTEM_DB:-1}"
SYSTEM_WEB_PORT="${SYSTEM_WEB_PORT:-8088}"
SYSTEM_WEB_HTTPS_PORT="${SYSTEM_WEB_HTTPS_PORT:-8444}"

run_compose() {
  "${DOCKER_CMD[@]}" compose "$@"
}

run_compose_env() {
  local -a env_args=()
  while [[ "$#" -gt 0 && "$1" == *=* ]]; do
    env_args+=("$1")
    shift
  done

  if [[ "${DOCKER_CMD[0]}" == "sudo" ]]; then
    local -a sudo_args=()
    local docker_bin="docker"
    for token in "${DOCKER_CMD[@]}"; do
      if [[ "$token" == "docker" ]]; then
        docker_bin="docker"
      else
        sudo_args+=("$token")
      fi
    done
    "${sudo_args[@]}" env "${env_args[@]}" "$docker_bin" compose "$@"
    return
  fi

  env "${env_args[@]}" "${DOCKER_CMD[@]}" compose "$@"
}

if [[ "$RESET_SYSTEM_DB" == "1" ]]; then
  run_compose \
    -f "$ROOT_DIR/system/docker-compose.yml" \
    -f "$ROOT_DIR/system/docker-compose.minimal.yml" \
    down -v --remove-orphans
fi

run_compose_env \
  BACKEND_PORT="$BACKEND_PORT" \
  BOOTSTRAP_TOKEN="$BOOTSTRAP_TOKEN" \
  SYSTEM_WEB_PORT="$SYSTEM_WEB_PORT" \
  SYSTEM_WEB_HTTPS_PORT="$SYSTEM_WEB_HTTPS_PORT" \
  -f "$ROOT_DIR/system/docker-compose.yml" \
  -f "$ROOT_DIR/system/docker-compose.minimal.yml" \
  up -d --build

run_compose_env \
  BACKEND_URL="http://host.docker.internal:$BACKEND_PORT" \
  BOOTSTRAP_TOKEN="$BOOTSTRAP_TOKEN" \
  TESTBED_BIND_ADDR="${TESTBED_BIND_ADDR:-0.0.0.0}" \
  AGENT_PUBLIC_HOST="${AGENT_PUBLIC_HOST:-host.docker.internal}" \
  -f "$ROOT_DIR/testbed/docker-compose.minimal.yml" \
  down --remove-orphans

run_compose_env \
  BACKEND_URL="http://host.docker.internal:$BACKEND_PORT" \
  BOOTSTRAP_TOKEN="$BOOTSTRAP_TOKEN" \
  TESTBED_BIND_ADDR="${TESTBED_BIND_ADDR:-0.0.0.0}" \
  AGENT_PUBLIC_HOST="${AGENT_PUBLIC_HOST:-host.docker.internal}" \
  -f "$ROOT_DIR/testbed/docker-compose.minimal.yml" \
  up -d --build --remove-orphans

run_compose -f "$ROOT_DIR/system/docker-compose.yml" -f "$ROOT_DIR/system/docker-compose.minimal.yml" ps
run_compose -f "$ROOT_DIR/testbed/docker-compose.minimal.yml" ps
