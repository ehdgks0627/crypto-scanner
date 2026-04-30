#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/crypto-scanner}"
DEPLOY_REMOTE="${DEPLOY_REMOTE:-origin}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
POLL_SECONDS="${POLL_SECONDS:-60}"
FAIL_RETRY_SECONDS="${FAIL_RETRY_SECONDS:-300}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-https://pqc.sprout.kr/api/health}"
STATE_DIR="${STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/crypto-scanner-deploy}"
DEPLOY_SCRIPT="${DEPLOY_SCRIPT:-scripts/deploy-production.sh}"
LAST_SUCCESS_FILE="$STATE_DIR/last-success-sha"
LAST_FAILED_FILE="$STATE_DIR/last-failed-sha"
LAST_FAILED_AT_FILE="$STATE_DIR/last-failed-at"
LOCK_DIR="$STATE_DIR/deploy.lock"
LOG_FILE="${LOG_FILE:-$STATE_DIR/deploy-watch.log}"

log() {
  printf '[deploy-watch] %s %s\n' "$(date -Is)" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

latest_remote_sha() {
  GIT_TERMINAL_PROMPT=0 git ls-remote "$DEPLOY_REMOTE" "refs/heads/$DEPLOY_BRANCH" | awk '{print $1}'
}

current_sha() {
  git rev-parse HEAD 2>/dev/null || true
}

seconds_since_failed_attempt() {
  local failed_at now

  [[ -f "$LAST_FAILED_AT_FILE" ]] || {
    echo "$FAIL_RETRY_SECONDS"
    return
  }

  failed_at="$(cat "$LAST_FAILED_AT_FILE" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  if [[ "$failed_at" =~ ^[0-9]+$ ]]; then
    echo $((now - failed_at))
  else
    echo "$FAIL_RETRY_SECONDS"
  fi
}

should_retry_failed_sha() {
  local latest failed_sha elapsed

  latest="$1"
  [[ -f "$LAST_FAILED_FILE" ]] || return 0

  failed_sha="$(cat "$LAST_FAILED_FILE" 2>/dev/null || true)"
  [[ "$failed_sha" == "$latest" ]] || return 0

  elapsed="$(seconds_since_failed_attempt)"
  [[ "$elapsed" -ge "$FAIL_RETRY_SECONDS" ]]
}

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    trap 'rm -rf "$LOCK_DIR"' EXIT
    return 0
  fi

  log "deployment already running; skipping this cycle"
  return 1
}

release_lock() {
  rm -rf "$LOCK_DIR"
  trap - EXIT
}

deploy_sha() {
  local latest

  latest="$1"
  acquire_lock || return 0

  log "deploying $latest"
  if DEPLOY_SHA="$latest" HEALTHCHECK_URL="$HEALTHCHECK_URL" bash "$DEPLOY_SCRIPT"; then
    printf '%s\n' "$latest" > "$LAST_SUCCESS_FILE"
    rm -f "$LAST_FAILED_FILE" "$LAST_FAILED_AT_FILE"
    log "deployment succeeded: $latest"
  else
    printf '%s\n' "$latest" > "$LAST_FAILED_FILE"
    date +%s > "$LAST_FAILED_AT_FILE"
    log "deployment failed: $latest"
  fi

  release_lock
}

run_cycle() {
  local latest current

  cd "$APP_DIR"
  latest="$(latest_remote_sha)"
  [[ -n "$latest" ]] || {
    log "could not resolve $DEPLOY_REMOTE/$DEPLOY_BRANCH"
    return 0
  }

  current="$(current_sha)"
  if [[ "$current" == "$latest" ]]; then
    log "already up to date: $latest"
    return 0
  fi

  if ! should_retry_failed_sha "$latest"; then
    log "previous deployment failed for $latest; retry delayed for ${FAIL_RETRY_SECONDS}s"
    return 0
  fi

  log "new commit detected: current=${current:-unknown} latest=$latest"
  deploy_sha "$latest"
}

main() {
  require_command awk
  require_command bash
  require_command date
  require_command git
  require_command mkdir
  require_command sleep

  mkdir -p "$STATE_DIR"
  touch "$LOG_FILE"
  exec > >(tee -a "$LOG_FILE") 2>&1

  [[ -d "$APP_DIR/.git" ]] || fail "$APP_DIR is not a git checkout"
  [[ -f "$APP_DIR/$DEPLOY_SCRIPT" ]] || fail "$APP_DIR/$DEPLOY_SCRIPT does not exist"

  log "watching $DEPLOY_REMOTE/$DEPLOY_BRANCH every ${POLL_SECONDS}s from $APP_DIR"
  while true; do
    run_cycle
    sleep "$POLL_SECONDS"
  done
}

main "$@"
