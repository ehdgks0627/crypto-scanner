#!/usr/bin/env bash
set -Eeuo pipefail

log() {
  printf '[issue-agent] %s\n' "$*" >&2
}

die() {
  log "ERROR: $*"
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

REPO="${REPO:-ehdgks0627/crypto-scanner}"
BASE_BRANCH="${BASE_BRANCH:-main}"
WORK_ROOT="${WORK_ROOT:-/workspace}"
ISSUE_LIMIT="${ISSUE_LIMIT:-1}"
RUN_ONCE="${RUN_ONCE:-0}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-300}"
DRY_RUN="${DRY_RUN:-0}"
DRY_RUN_LIMIT="${DRY_RUN_LIMIT:-10}"
ISSUE_LABEL_IN_PROGRESS="${ISSUE_LABEL_IN_PROGRESS:-ai-in-progress}"
ISSUE_LABEL_FAILED="${ISSUE_LABEL_FAILED:-ai-failed}"
ISSUE_LABEL_DONE="${ISSUE_LABEL_DONE:-ai-fixed}"
ISSUE_SEARCH="${ISSUE_SEARCH:-is:issue is:open -label:${ISSUE_LABEL_IN_PROGRESS} -label:${ISSUE_LABEL_FAILED} sort:created-asc}"
PUSH_MODE="${PUSH_MODE:-direct}"
AUTO_PUSH="${AUTO_PUSH:-1}"
AUTO_CLOSE="${AUTO_CLOSE:-1}"
AUTO_CLOSE_ON_BRANCH="${AUTO_CLOSE_ON_BRANCH:-0}"
CREATE_PR="${CREATE_PR:-0}"
ALLOW_FALLBACK_COMMIT="${ALLOW_FALLBACK_COMMIT:-1}"
COMMENT_ON_START="${COMMENT_ON_START:-0}"
POST_FAILURE_COMMENT="${POST_FAILURE_COMMENT:-1}"
GIT_USER_NAME="${GIT_USER_NAME:-crypto-scanner-issue-agent}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-issue-agent@users.noreply.github.com}"
CODEX_MODEL="${CODEX_MODEL:-}"
CODEX_REASONING_EFFORT="${CODEX_REASONING_EFFORT:-xhigh}"
VERIFY_COMMAND="${VERIFY_COMMAND:-}"
AUTO_DEPLOY="${AUTO_DEPLOY:-1}"
SSH_DEPLOY_HOST="${SSH_DEPLOY_HOST:-pqc}"
HOST_SSH_DIR="${HOST_SSH_DIR:-/host-ssh}"
HOST_CODEX_DIR="${HOST_CODEX_DIR:-/host-codex}"
REMOTE_REPO_DIR="${REMOTE_REPO_DIR:-/opt/crypto-scanner}"
REMOTE_DEPLOY_COMMAND="${REMOTE_DEPLOY_COMMAND:-${SSH_DEPLOY_COMMAND:-${DEPLOY_COMMAND:-git pull --ff-only && sudo -n docker compose -f system/docker-compose.yml up -d --build}}}"
SSH_OPTIONS="${SSH_OPTIONS:--o BatchMode=yes -o StrictHostKeyChecking=accept-new}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%d%H%M%S)}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_FILE="${AGENT_OUTPUT_SCHEMA:-${SCRIPT_DIR}/agent-output.schema.json}"
ISSUE_NUMBER="${ISSUE_NUMBER:-}"
ACTIVE_ISSUE_NUMBER=""
RUN_DIR=""
REPO_DIR=""
AGENT_OUTPUT=""
BASE_SHA=""
PUSHED_SHA=""
DEPLOY_STATUS="skipped"

on_error() {
  local line="$1"
  local exit_code="$2"
  trap - ERR

  log "Failed at line ${line} with exit code ${exit_code}"
  if [[ -n "$ACTIVE_ISSUE_NUMBER" && "$POST_FAILURE_COMMENT" == "1" ]]; then
    gh issue edit "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
      --remove-label "$ISSUE_LABEL_IN_PROGRESS" >/dev/null 2>&1 || true
    gh issue edit "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
      --add-label "$ISSUE_LABEL_FAILED" >/dev/null 2>&1 || true
    gh issue comment "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
      --body "Automated issue agent failed before completing this issue. Run id: \`${RUN_ID}\`. Check the runner logs for details." \
      >/dev/null 2>&1 || true
  fi

  exit "$exit_code"
}

trap 'on_error "$LINENO" "$?"' ERR

require_cmd gh
require_cmd git
require_cmd jq
require_cmd ssh

setup_github_auth() {
  if [[ -n "${GITHUB_TOKEN:-}" && -z "${GH_TOKEN:-}" ]]; then
    export GH_TOKEN="$GITHUB_TOKEN"
  fi

  [[ -n "${GH_TOKEN:-}" ]] \
    || die "Set GH_TOKEN in automation/issue-agent/.env before running non-dry-run mode"
  gh auth status >/dev/null
  gh auth setup-git >/dev/null 2>&1 || true
}

setup_ssh_credentials() {
  mkdir -p "$HOME/.ssh"

  if [[ -f "$HOST_SSH_DIR/config" ]]; then
    cp -L "$HOST_SSH_DIR/config" "$HOME/.ssh/config"
  fi

  if [[ -f "$HOST_SSH_DIR/known_hosts" ]]; then
    cp -L "$HOST_SSH_DIR/known_hosts" "$HOME/.ssh/known_hosts"
  fi

  if [[ -f "$HOST_SSH_DIR/deploy_key" ]]; then
    cp -L "$HOST_SSH_DIR/deploy_key" "$HOME/.ssh/deploy_key"
    if [[ -f "$HOME/.ssh/config" ]]; then
      sed -i '/^[[:space:]]*IdentityFile[[:space:]]/d' "$HOME/.ssh/config"
    fi
    SSH_OPTIONS="${SSH_OPTIONS} -o IdentityFile=${HOME}/.ssh/deploy_key -o IdentitiesOnly=yes"
  fi

  chmod 700 "$HOME/.ssh" 2>/dev/null || true
  find "$HOME/.ssh" -maxdepth 1 -type f -exec chmod 600 {} \; 2>/dev/null || true

  if [[ -n "${SSH_PRIVATE_KEY:-}" ]]; then
    printf '%s\n' "$SSH_PRIVATE_KEY" > "$HOME/.ssh/issue_agent_key"
    chmod 600 "$HOME/.ssh/issue_agent_key"
    SSH_OPTIONS="${SSH_OPTIONS} -i ${HOME}/.ssh/issue_agent_key"
  fi

  if [[ -n "${SSH_KNOWN_HOSTS:-}" ]]; then
    printf '%s\n' "$SSH_KNOWN_HOSTS" >> "$HOME/.ssh/known_hosts"
    chmod 600 "$HOME/.ssh/known_hosts" 2>/dev/null || true
  fi
}

setup_codex_credentials() {
  if [[ -n "${LLM_COMMAND:-}" ]]; then
    return
  fi

  mkdir -p "$HOME/.codex"

  if [[ -f "$HOST_CODEX_DIR/auth.json" ]]; then
    cp -L "$HOST_CODEX_DIR/auth.json" "$HOME/.codex/auth.json"
  fi

  chmod 700 "$HOME/.codex" 2>/dev/null || true
  chmod 600 "$HOME/.codex/auth.json" 2>/dev/null || true

  [[ -f "$HOME/.codex/auth.json" ]] \
    || die "Mount Codex CLI auth.json with CODEX_AUTH_SOURCE, or set LLM_COMMAND to a custom agent"
}

ensure_label() {
  local name="$1"
  local color="$2"
  local description="$3"

  gh label create "$name" -R "$REPO" \
    --color "$color" \
    --description "$description" >/dev/null 2>&1 || true
}

select_issue() {
  if [[ -n "$ISSUE_NUMBER" ]]; then
    gh issue view "$ISSUE_NUMBER" -R "$REPO" --json state \
      | jq -r --arg number "$ISSUE_NUMBER" 'if .state == "OPEN" then $number else empty end'
    return
  fi

  gh issue list -R "$REPO" \
    --state open \
    --limit "$ISSUE_LIMIT" \
    --search "$ISSUE_SEARCH" \
    --json number,title,url,labels,createdAt,updatedAt \
    | jq -r '.[0].number // empty'
}

print_pending_issues() {
  printf '[issue-agent] DRY_RUN=1: listing pending issues only. No labels, clone, LLM, push, close, or deploy will run.\n' >&2

  if [[ -n "${GITHUB_TOKEN:-}" && -z "${GH_TOKEN:-}" ]]; then
    export GH_TOKEN="$GITHUB_TOKEN"
  fi

  if [[ -z "${GH_TOKEN:-}" ]]; then
    print_pending_issues_public_api
    return
  fi

  if [[ -n "$ISSUE_NUMBER" ]]; then
    gh issue view "$ISSUE_NUMBER" -R "$REPO" \
      --json number,title,url,state,labels,createdAt,updatedAt \
      | jq -r '
        def label_names:
          (.labels // [] | map(.name) | join(", ")) as $labels
          | if $labels == "" then "-" else $labels end;

        if .state == "OPEN" then
          "Would handle issue #\(.number): \(.title)\n  url: \(.url)\n  state: \(.state)\n  labels: \(label_names)\n  updated: \(.updatedAt)"
        else
          "Issue #\(.number) is \(.state); it would not be handled.\n  url: \(.url)\n  labels: \(label_names)\n  updated: \(.updatedAt)"
        end
      '
    return
  fi

  gh issue list -R "$REPO" \
    --state open \
    --limit "$DRY_RUN_LIMIT" \
    --search "$ISSUE_SEARCH" \
    --json number,title,url,labels,createdAt,updatedAt \
    | jq -r '
      def label_names:
        (.labels // [] | map(.name) | join(", ")) as $labels
        | if $labels == "" then "-" else $labels end;

      if length == 0 then
        "No pending open issues matched the query."
      else
        "Pending open issues matching query:",
        (.[] | "- #\(.number): \(.title)\n  url: \(.url)\n  labels: \(label_names)\n  updated: \(.updatedAt)")
      end
    '
}

print_pending_issues_public_api() {
  local api_url
  api_url="https://api.github.com/repos/${REPO}/issues"

  if [[ -n "$ISSUE_NUMBER" ]]; then
    curl -fsSL "${api_url}/${ISSUE_NUMBER}" \
      | jq -r '
        def label_names:
          (.labels // [] | map(.name) | join(", ")) as $labels
          | if $labels == "" then "-" else $labels end;

        if .state == "open" and (.pull_request | not) then
          "Would handle issue #\(.number): \(.title)\n  url: \(.html_url)\n  state: \(.state)\n  labels: \(label_names)\n  updated: \(.updated_at)"
        else
          "Issue #\(.number) is not an open issue candidate.\n  url: \(.html_url)\n  state: \(.state)\n  labels: \(label_names)\n  updated: \(.updated_at)"
        end
      '
    return
  fi

  curl -fsSL "${api_url}?state=open&sort=created&direction=asc&per_page=${DRY_RUN_LIMIT}" \
    | jq -r --arg in_progress "$ISSUE_LABEL_IN_PROGRESS" --arg failed "$ISSUE_LABEL_FAILED" '
      def label_names:
        (.labels // [] | map(.name) | join(", ")) as $labels
        | if $labels == "" then "-" else $labels end;

      map(select(.pull_request | not))
      | map(select((.labels // [] | map(.name) | index($in_progress)) | not))
      | map(select((.labels // [] | map(.name) | index($failed)) | not))
      | if length == 0 then
          "No pending open issues matched the query."
        else
          "Pending open issues matching query:",
          (.[] | "- #\(.number): \(.title)\n  url: \(.html_url)\n  labels: \(label_names)\n  updated: \(.updated_at)")
        end
    '
}

json_array_to_lines() {
  jq -r '
    if type == "array" and length > 0 then
      map("- " + tostring) | join("\n")
    else
      "- Not reported"
    end
  ' "$1"
}

write_fallback_output() {
  local status="$1"
  local summary="$2"
  local output_file="$3"

  jq -n \
    --arg status "$status" \
    --arg summary "$summary" \
    '{
      status: $status,
      summary: $summary,
      tests: [],
      files_changed: [],
      close_issue: false,
      notes: "Generated by the orchestrator because the LLM output was missing or invalid."
    }' > "$output_file"
}

build_prompt() {
  local issue_file="$1"
  local prompt_file="$2"

  cat > "$prompt_file" <<PROMPT
You are an autonomous coding agent running inside a Docker container on a fresh clone of ${REPO}.

Goal:
- Implement the GitHub issue described below.
- Make the smallest coherent code change that resolves the issue.
- Run the relevant checks or tests you can reasonably run in this container.
- Commit your changes locally before you finish.
- Do not push, close the issue, deploy, or modify this automation unless the issue explicitly asks for it.

Repository rules:
- Preserve unrelated work.
- Prefer existing project patterns.
- Do not invent broad rewrites for a narrow issue.
- If the issue is unclear or unsafe to implement automatically, leave the repository clean and report status "blocked".

Final response:
- Return JSON only.
- Match the schema at ${SCHEMA_FILE}.
- Use status "implemented" only when the fix is committed.
- Include every check you ran in "tests".
- Set "close_issue" to true only when the issue should be closed after push and deploy.

Issue JSON:
PROMPT

  jq . "$issue_file" >> "$prompt_file"
}

run_llm() {
  local prompt_file="$1"
  local output_file="$2"

  if [[ -n "${LLM_COMMAND:-}" ]]; then
    log "Running custom LLM command"
    AGENT_PROMPT_FILE="$prompt_file" \
      AGENT_OUTPUT_FILE="$output_file" \
      AGENT_OUTPUT_SCHEMA="$SCHEMA_FILE" \
      ISSUE_NUMBER="$ACTIVE_ISSUE_NUMBER" \
      REPO_DIR="$REPO_DIR" \
      bash -lc "$LLM_COMMAND"
    return
  fi

  require_cmd codex

  local codex_args=(
    exec
    --cd "$REPO_DIR"
    --full-auto
    -c "model_reasoning_effort=\"${CODEX_REASONING_EFFORT}\""
    --output-schema "$SCHEMA_FILE"
    --output-last-message "$output_file"
  )

  if [[ -n "$CODEX_MODEL" ]]; then
    codex_args+=(--model "$CODEX_MODEL")
  fi

  log "Running Codex on issue #${ACTIVE_ISSUE_NUMBER}"
  codex "${codex_args[@]}" - < "$prompt_file"
}

commit_dirty_fallback() {
  local status
  status="$(git status --short)"
  if [[ -z "$status" ]]; then
    return
  fi

  if [[ "$ALLOW_FALLBACK_COMMIT" != "1" ]]; then
    die "LLM left uncommitted changes and ALLOW_FALLBACK_COMMIT is disabled"
  fi

  log "LLM left uncommitted changes; creating fallback commit"
  git add -A
  git commit -m "Fix issue #${ACTIVE_ISSUE_NUMBER}"
}

run_verify_command() {
  if [[ -z "$VERIFY_COMMAND" ]]; then
    return
  fi

  log "Running post-agent verify command"
  (cd "$REPO_DIR" && bash -lc "$VERIFY_COMMAND")
}

push_changes() {
  if [[ "$AUTO_PUSH" != "1" ]]; then
    log "AUTO_PUSH is disabled; skipping push"
    return
  fi

  case "$PUSH_MODE" in
    direct)
      log "Pushing commit(s) to ${BASE_BRANCH}"
      git fetch origin "$BASE_BRANCH"
      git rebase "origin/${BASE_BRANCH}"
      git push origin "HEAD:${BASE_BRANCH}"
      PUSHED_SHA="$(git rev-parse HEAD)"
      ;;
    branch)
      log "Pushing commit(s) to ${ISSUE_BRANCH}"
      git push -u origin "$ISSUE_BRANCH"
      PUSHED_SHA="$(git rev-parse HEAD)"
      if [[ "$CREATE_PR" == "1" ]]; then
        gh pr create -R "$REPO" \
          --base "$BASE_BRANCH" \
          --head "$ISSUE_BRANCH" \
          --title "Fix issue #${ACTIVE_ISSUE_NUMBER}" \
          --body "Automated fix for #${ACTIVE_ISSUE_NUMBER}." >/dev/null
      fi
      ;;
    none)
      log "PUSH_MODE=none; skipping push"
      ;;
    *)
      die "Unsupported PUSH_MODE: ${PUSH_MODE}"
      ;;
  esac
}

deploy_changes() {
  if [[ "$AUTO_DEPLOY" != "1" ]]; then
    DEPLOY_STATUS="skipped"
    log "AUTO_DEPLOY is disabled; skipping deploy"
    return
  fi

  if [[ "$AUTO_PUSH" != "1" || "$PUSH_MODE" == "none" ]]; then
    DEPLOY_STATUS="skipped"
    log "Push is disabled; skipping deploy"
    return
  fi

  if [[ -z "$REMOTE_DEPLOY_COMMAND" ]]; then
    DEPLOY_STATUS="skipped"
    log "REMOTE_DEPLOY_COMMAND is not set; skipping deploy"
    return
  fi

  log "Deploying over SSH to ${SSH_DEPLOY_HOST}"
  ssh ${SSH_OPTIONS} "$SSH_DEPLOY_HOST" \
    "cd ${REMOTE_REPO_DIR} && ${REMOTE_DEPLOY_COMMAND}"
  DEPLOY_STATUS="succeeded"
}

build_comment() {
  local output_file="$1"
  local comment_file="$2"
  local status summary notes tests files commit_url

  status="$(jq -r '.status // "unknown"' "$output_file")"
  summary="$(jq -r '.summary // "No summary reported."' "$output_file")"
  notes="$(jq -r '.notes // empty' "$output_file")"
  tests="$(jq '.tests // []' "$output_file" | json_array_to_lines /dev/stdin)"
  files="$(jq '.files_changed // []' "$output_file" | json_array_to_lines /dev/stdin)"

  if [[ -n "$PUSHED_SHA" ]]; then
    commit_url="https://github.com/${REPO}/commit/${PUSHED_SHA}"
  else
    commit_url="Not pushed"
  fi

  cat > "$comment_file" <<COMMENT
Automated issue agent completed this issue.

Status: \`${status}\`

Summary:
${summary}

Commit:
${commit_url}

Tests:
${tests}

Files changed:
${files}

Deploy:
${DEPLOY_STATUS}
COMMENT

  if [[ -n "$notes" ]]; then
    {
      printf '\nNotes:\n'
      printf '%s\n' "$notes"
    } >> "$comment_file"
  fi
}

complete_issue() {
  local output_file="$1"
  local comment_file="$2"
  local status close_issue

  status="$(jq -r '.status // "blocked"' "$output_file")"
  close_issue="$(jq -r '.close_issue // false' "$output_file")"

  gh issue edit "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
    --remove-label "$ISSUE_LABEL_IN_PROGRESS" >/dev/null 2>&1 || true
  gh issue edit "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
    --remove-label "$ISSUE_LABEL_FAILED" >/dev/null 2>&1 || true

  if [[ "$status" == "implemented" ]]; then
    gh issue edit "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
      --add-label "$ISSUE_LABEL_DONE" >/dev/null 2>&1 || true
  else
    gh issue edit "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
      --add-label "$ISSUE_LABEL_FAILED" >/dev/null 2>&1 || true
  fi

  if [[ "$AUTO_CLOSE" == "1" && "$close_issue" == "true" && "$status" == "implemented" ]]; then
    if [[ "$PUSH_MODE" == "branch" && "$AUTO_CLOSE_ON_BRANCH" != "1" ]]; then
      gh issue comment "$ACTIVE_ISSUE_NUMBER" -R "$REPO" --body-file "$comment_file"
      log "Leaving issue open because PUSH_MODE=branch and AUTO_CLOSE_ON_BRANCH is disabled"
      return
    fi

    gh issue close "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
      --reason completed \
      --comment "$(cat "$comment_file")"
    return
  fi

  gh issue comment "$ACTIVE_ISSUE_NUMBER" -R "$REPO" --body-file "$comment_file"
}

run_once() {
  ensure_label "$ISSUE_LABEL_IN_PROGRESS" "fbca04" "Issue is being handled by the automated LLM agent."
  ensure_label "$ISSUE_LABEL_FAILED" "d73a4a" "Automated LLM agent failed while handling this issue."
  ensure_label "$ISSUE_LABEL_DONE" "0e8a16" "Issue was fixed by the automated LLM agent."

  ACTIVE_ISSUE_NUMBER="$(select_issue)"
  if [[ -z "$ACTIVE_ISSUE_NUMBER" ]]; then
    log "No matching open issue found"
    return
  fi

  log "Selected issue #${ACTIVE_ISSUE_NUMBER}"
  gh issue edit "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
    --add-label "$ISSUE_LABEL_IN_PROGRESS" >/dev/null

  if [[ "$COMMENT_ON_START" == "1" ]]; then
    gh issue comment "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
      --body "Automated issue agent started work on this issue. Run id: \`${RUN_ID}\`." \
      >/dev/null
  fi

  RUN_DIR="${WORK_ROOT}/issue-${ACTIVE_ISSUE_NUMBER}-${RUN_ID}"
  REPO_DIR="${RUN_DIR}/repo"
  AGENT_OUTPUT="${RUN_DIR}/agent-output.json"
  local issue_file="${RUN_DIR}/issue.json"
  local prompt_file="${RUN_DIR}/prompt.md"
  local comment_file="${RUN_DIR}/issue-comment.md"

  mkdir -p "$RUN_DIR"
  gh issue view "$ACTIVE_ISSUE_NUMBER" -R "$REPO" \
    --comments \
    --json number,title,body,comments,labels,author,url,state,createdAt,updatedAt \
    > "$issue_file"

  log "Cloning ${REPO}@${BASE_BRANCH}"
  gh repo clone "$REPO" "$REPO_DIR"

  cd "$REPO_DIR"
  git config user.name "$GIT_USER_NAME"
  git config user.email "$GIT_USER_EMAIL"
  git fetch origin "$BASE_BRANCH"
  git switch "$BASE_BRANCH" 2>/dev/null || git switch -c "$BASE_BRANCH" --track "origin/${BASE_BRANCH}"
  git pull --ff-only origin "$BASE_BRANCH"
  git switch -c "ai/issue-${ACTIVE_ISSUE_NUMBER}-${RUN_ID}"
  ISSUE_BRANCH="$(git branch --show-current)"
  BASE_SHA="$(git rev-parse HEAD)"

  build_prompt "$issue_file" "$prompt_file"
  run_llm "$prompt_file" "$AGENT_OUTPUT"

  if ! jq empty "$AGENT_OUTPUT" >/dev/null 2>&1; then
    log "LLM did not return valid JSON metadata"
    AGENT_OUTPUT="${RUN_DIR}/agent-output-fallback.json"
    write_fallback_output "blocked" "The LLM did not return valid JSON metadata." "$AGENT_OUTPUT"
  fi

  commit_dirty_fallback

  if [[ "$(git rev-list --count "${BASE_SHA}..HEAD")" == "0" ]]; then
    AGENT_OUTPUT="${RUN_DIR}/agent-output-no-changes.json"
    write_fallback_output "no_changes" "The agent finished without creating a commit." "$AGENT_OUTPUT"
  fi

  run_verify_command
  commit_dirty_fallback
  push_changes
  deploy_changes
  build_comment "$AGENT_OUTPUT" "$comment_file"
  complete_issue "$AGENT_OUTPUT" "$comment_file"

  log "Done"
}

main() {
  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ "$RUN_ONCE" == "1" ]]; then
      print_pending_issues
      return
    fi

    while true; do
      print_pending_issues
      log "Sleeping for ${POLL_INTERVAL_SECONDS}s"
      sleep "$POLL_INTERVAL_SECONDS"
    done

    return
  fi

  setup_github_auth
  setup_ssh_credentials
  setup_codex_credentials

  if [[ "$RUN_ONCE" == "1" ]]; then
    run_once
    return
  fi

  while true; do
    run_once
    log "Sleeping for ${POLL_INTERVAL_SECONDS}s"
    sleep "$POLL_INTERVAL_SECONDS"
  done
}

main "$@"
