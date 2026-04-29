# Dockerized GitHub Issue Agent

This runner polls open GitHub issues, gives one issue to an LLM coding agent, pushes the resulting commit, deploys over `ssh pqc` with Docker compose, comments on the issue, and closes it.

The runner always clones a fresh copy of the repository into `/workspace`, so it does not touch a developer's local working tree.

## Flow

1. Find one open issue with `gh issue list`.
2. Add the `ai-in-progress` label as a lightweight lock.
3. Clone `REPO` at `BASE_BRANCH`.
4. Give the issue JSON and comments to the LLM.
5. Expect the LLM to edit, test, commit, and return JSON metadata.
6. Push the commit.
7. Run the remote Docker deployment over SSH.
8. Comment with summary, tests, files, and commit URL.
9. Close the issue when the LLM reports `close_issue: true`.

## Local Docker Run

```sh
cd /path/to/crypto-scanner
docker build -t crypto-scanner-issue-agent ./automation/issue-agent
docker run -d --restart unless-stopped \
  --env-file ./automation/issue-agent/.env \
  -v "$HOME/.ssh/config:/host-ssh/config:ro" \
  -v "$HOME/.ssh/crypto_scanner_issue_agent_ed25519:/host-ssh/deploy_key:ro" \
  -v "$HOME/.ssh/known_hosts:/host-ssh/known_hosts:ro" \
  crypto-scanner-issue-agent
```

If you want the container to use your existing `ssh pqc` alias, mount only the needed SSH files. The runner copies them into the container with root ownership before using SSH.

```sh
docker run --rm \
  --env-file ./automation/issue-agent/.env \
  -v "$HOME/.ssh/config:/host-ssh/config:ro" \
  -v "$HOME/.ssh/crypto_scanner_issue_agent_ed25519:/host-ssh/deploy_key:ro" \
  -v "$HOME/.ssh/known_hosts:/host-ssh/known_hosts:ro" \
  crypto-scanner-issue-agent
```

Create the env file from `.env.example` and set at least:

- `GH_TOKEN`: GitHub token with issue and content write permission.
- `CODEX_AUTH_SOURCE`: Codex CLI login file. Defaults to `~/.codex/auth.json`.
- `REPO`: defaults to `ehdgks0627/crypto-scanner`.

To force a single issue:

```sh
docker run --rm \
  --env-file ./automation/issue-agent/.env \
  -e RUN_ONCE=1 \
  -e ISSUE_NUMBER=123 \
  crypto-scanner-issue-agent
```

To dry-run without invoking the LLM or changing anything:

```sh
docker run --rm \
  --env-file ./automation/issue-agent/.env \
  -e DRY_RUN=1 \
  -e RUN_ONCE=1 \
  crypto-scanner-issue-agent
```

This only prints pending open issues matching `ISSUE_SEARCH`. Add `-e ISSUE_NUMBER=123` to check one issue.

To keep a dry-run monitor alive:

```sh
docker run -d --restart unless-stopped \
  --env-file ./automation/issue-agent/.env \
  -e DRY_RUN=1 \
  -e RUN_ONCE=0 \
  crypto-scanner-issue-agent
```

The default mode keeps the container polling. Set the interval with:

```sh
POLL_INTERVAL_SECONDS=300
```

Or run it with the included compose file:

```sh
cd automation/issue-agent
docker compose -f compose.yml up -d --build
```

If you must run compose through `sudo`, preserve the SSH source path:

```sh
SSH_CONFIG_SOURCE="$HOME/.ssh/config" \
SSH_KEY_SOURCE="$HOME/.ssh/crypto_scanner_issue_agent_ed25519" \
SSH_KNOWN_HOSTS_SOURCE="$HOME/.ssh/known_hosts" \
CODEX_AUTH_SOURCE="$HOME/.codex/auth.json" \
sudo -E docker compose -f compose.yml up -d --build
```

## SSH Docker Deploy

The default deployment is equivalent to:

```sh
ssh pqc 'cd /opt/crypto-scanner && git pull --ff-only && sudo -n docker compose -f system/docker-compose.yml up -d --build'
```

Configure it with:

```sh
SSH_DEPLOY_HOST=pqc
REMOTE_REPO_DIR=/opt/crypto-scanner
REMOTE_DEPLOY_COMMAND=if [ ! -d .git ]; then git init; fi && (git remote get-url origin >/dev/null 2>&1 || git remote add origin https://github.com/ehdgks0627/crypto-scanner.git) && git fetch origin main && git reset --hard origin/main && sudo -n docker compose -f system/docker-compose.yml up -d --build
```

Use `AUTO_DEPLOY=0` to skip deployment.

When you cannot mount `~/.ssh`, provide credentials with environment variables:

```sh
SSH_PRIVATE_KEY="$(cat ~/.ssh/id_ed25519)"
SSH_KNOWN_HOSTS="$(ssh-keyscan -H 15.164.213.165)"
```

## Safer Push Modes

Default mode is direct push to `BASE_BRANCH`, because this matches the requested close-and-deploy pipeline.

For a PR-based variant:

```sh
PUSH_MODE=branch
CREATE_PR=1
AUTO_CLOSE=0
```

## Custom LLM Command

By default the runner uses:

```sh
codex exec --full-auto -c 'model_reasoning_effort="xhigh"'
```

To use another agent, set `LLM_COMMAND`. The command receives:

- `AGENT_PROMPT_FILE`: prompt markdown file.
- `AGENT_OUTPUT_FILE`: path where JSON metadata must be written.
- `AGENT_OUTPUT_SCHEMA`: schema path.
- `REPO_DIR`: cloned repository path.
- `ISSUE_NUMBER`: selected issue number.

Example:

```sh
LLM_COMMAND='claude -p "$(cat "$AGENT_PROMPT_FILE")" > "$AGENT_OUTPUT_FILE"'
```

## Useful Controls

- `ISSUE_SEARCH`: GitHub issue search query.
- `ISSUE_NUMBER`: bypass search and handle a specific issue.
- `DRY_RUN=1`: print pending issue candidates and exit without mutation.
- `DRY_RUN_LIMIT`: max issues printed in dry-run mode.
- `RUN_ONCE=0`: keep polling instead of exiting after one pass. This is the default.
- `RUN_ONCE=1`: process one polling pass and exit.
- `POLL_INTERVAL_SECONDS`: sleep duration between polling attempts.
- `VERIFY_COMMAND`: shell command run after the LLM commits and before push.
- `AUTO_PUSH=0`: run without pushing.
- `AUTO_DEPLOY=0`: run without deploying.
- `AUTO_CLOSE=0`: comment but leave the issue open.
- `COMMENT_ON_START=1`: add a start comment before LLM work begins.
