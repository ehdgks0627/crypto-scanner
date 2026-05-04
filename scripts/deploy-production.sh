#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/crypto-scanner}"
DEPLOY_REMOTE="${DEPLOY_REMOTE:-origin}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
DEPLOY_SHA="${DEPLOY_SHA:-}"
COMPOSE_PROJECT_DIR="${COMPOSE_PROJECT_DIR:-$APP_DIR/system}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-$COMPOSE_PROJECT_DIR/.env}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-https://pqc.sprout.kr/api/health}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-30}"
HEALTHCHECK_DELAY_SECONDS="${HEALTHCHECK_DELAY_SECONDS:-2}"
DEPLOY_STATE_DIR="${DEPLOY_STATE_DIR:-$HOME/.local/state/crypto-scanner-deploy}"
SEED_TESTBED_DEMO_ON_DEPLOY="${SEED_TESTBED_DEMO_ON_DEPLOY:-1}"
SEED_TESTBED_DEMO_FORCE="${SEED_TESTBED_DEMO_FORCE:-0}"
SEED_TESTBED_DEMO_RESET_DB="${SEED_TESTBED_DEMO_RESET_DB:-1}"
SEED_TESTBED_DEMO_VERSION="${SEED_TESTBED_DEMO_VERSION:-20260504-production-testbed-reset}"

SAFE_UNTRACKED=()
DOCKER_PREFIX=()

log() {
  printf '[deploy] %s\n' "$*"
}

fail() {
  printf '[deploy] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

is_truthy() {
  case "$1" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

path_matches_target() {
  local path="$1"

  [[ -e "$path" ]] || return 1
  git cat-file -e "$DEPLOY_SHA:$path" 2>/dev/null || return 1
  cmp -s "$path" <(git show "$DEPLOY_SHA:$path")
}

guard_worktree() {
  local status line code path unsafe

  status="$(git status --porcelain --untracked-files=all)"
  [[ -n "$status" ]] || return 0

  unsafe=0
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    code="${line:0:2}"
    path="${line:3}"

    if [[ "$line" == *" -> "* ]]; then
      log "unsafe renamed path: $line"
      unsafe=1
      continue
    fi

    if path_matches_target "$path"; then
      if [[ "$code" == "??" ]]; then
        SAFE_UNTRACKED+=("$path")
        log "untracked file already matches target commit: $path"
      else
        log "local change already matches target commit: $path"
      fi
      continue
    fi

    log "unsafe local worktree entry: $line"
    unsafe=1
  done <<< "$status"

  if [[ "$unsafe" -ne 0 ]]; then
    git status --short
    fail "deployment aborted because the production checkout has local changes not present in $DEPLOY_SHA"
  fi
}

prepare_docker() {
  if docker ps >/dev/null 2>&1; then
    DOCKER_PREFIX=()
    return
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n docker ps >/dev/null 2>&1; then
    DOCKER_PREFIX=(sudo)
    return
  fi

  fail "docker is not accessible by $(id -un); configure docker group access or passwordless sudo for docker"
}

compose() {
  "${DOCKER_PREFIX[@]}" docker compose --env-file "$COMPOSE_ENV_FILE" "$@"
}

healthcheck() {
  local attempt

  for attempt in $(seq 1 "$HEALTHCHECK_RETRIES"); do
    if curl -fsS "$HEALTHCHECK_URL" >/dev/null; then
      log "health check passed: $HEALTHCHECK_URL"
      return 0
    fi
    log "health check not ready ($attempt/$HEALTHCHECK_RETRIES)"
    sleep "$HEALTHCHECK_DELAY_SECONDS"
  done

  compose ps || true
  compose logs --tail=100 backend frontend >&2 || true
  fail "health check failed: $HEALTHCHECK_URL"
}

seed_testbed_demo_if_needed() {
  local marker

  if ! is_truthy "$SEED_TESTBED_DEMO_ON_DEPLOY"; then
    log "production testbed demo seed skipped: SEED_TESTBED_DEMO_ON_DEPLOY=$SEED_TESTBED_DEMO_ON_DEPLOY"
    return
  fi

  mkdir -p "$DEPLOY_STATE_DIR"
  marker="$DEPLOY_STATE_DIR/testbed-demo-seed-$SEED_TESTBED_DEMO_VERSION.done"
  if [[ -f "$marker" ]] && ! is_truthy "$SEED_TESTBED_DEMO_FORCE"; then
    log "production testbed demo seed already applied: $SEED_TESTBED_DEMO_VERSION"
    return
  fi

  if is_truthy "$SEED_TESTBED_DEMO_RESET_DB"; then
    log "flushing database before production testbed demo seed"
    compose run --rm --entrypoint python backend manage.py flush --noinput
  fi

  log "seeding production testbed demo data: $SEED_TESTBED_DEMO_VERSION"
  compose run --rm --entrypoint python backend manage.py seed_testbed_demo --reset
  {
    printf 'version=%s\n' "$SEED_TESTBED_DEMO_VERSION"
    printf 'sha=%s\n' "$DEPLOY_SHA"
    date -u '+applied_at=%Y-%m-%dT%H:%M:%SZ'
  } > "$marker"
}

main() {
  [[ -n "$DEPLOY_SHA" ]] || fail "DEPLOY_SHA is required"

  require_command git
  require_command docker
  require_command curl
  require_command cmp
  require_command seq

  cd "$APP_DIR"
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "$APP_DIR is not a git checkout"

  log "fetching $DEPLOY_REMOTE/$DEPLOY_BRANCH"
  git fetch --prune "$DEPLOY_REMOTE" "+refs/heads/$DEPLOY_BRANCH:refs/remotes/$DEPLOY_REMOTE/$DEPLOY_BRANCH"
  git cat-file -e "$DEPLOY_SHA^{commit}" 2>/dev/null || fail "target commit is not available: $DEPLOY_SHA"
  git merge-base --is-ancestor "$DEPLOY_SHA" "$DEPLOY_REMOTE/$DEPLOY_BRANCH" \
    || fail "$DEPLOY_SHA is not reachable from $DEPLOY_REMOTE/$DEPLOY_BRANCH"

  guard_worktree

  for path in "${SAFE_UNTRACKED[@]}"; do
    rm -f -- "$path"
  done

  log "checking out $DEPLOY_SHA"
  git checkout --force --detach "$DEPLOY_SHA"

  if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
    git status --short
    fail "deployment checkout is not clean after checkout"
  fi

  [[ -f "$COMPOSE_ENV_FILE" ]] || fail "compose env file not found: $COMPOSE_ENV_FILE"
  prepare_docker

  cd "$COMPOSE_PROJECT_DIR"
  log "building docker images"
  compose build

  log "running django migrations"
  compose run --rm --entrypoint python backend manage.py migrate --noinput

  seed_testbed_demo_if_needed

  log "starting services"
  compose up -d --remove-orphans

  healthcheck
  log "deployment completed for $DEPLOY_SHA"
}

main "$@"
