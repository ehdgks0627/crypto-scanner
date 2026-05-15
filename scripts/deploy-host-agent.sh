#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSH_TARGET=""
SSH_PORT="22"
BACKEND_URL=""
BOOTSTRAP_TOKEN=""
AGENT_HOSTNAME=""
AGENT_URL=""
AGENT_LISTEN="0.0.0.0:9100"
AGENT_CAPABILITIES="agent.cert_store,agent.pkg_keyring,agent.ssh_userkey,agent.ssh_config,agent.keystore,agent.app_cert_files,agent.private_key_files,agent.app_config"
INSTALL_DIR="/opt/pqc-host-agent"
ENV_FILE="/etc/pqc-host-agent.env"
SERVICE_NAME="pqc-host-agent"
DRY_RUN="0"

usage() {
  cat <<'USAGE'
Usage:
  scripts/deploy-host-agent.sh --host user@example.com --backend-url http://backend:8000 --bootstrap-token TOKEN --agent-hostname web.example.com [options]

Options:
  --host USER@HOST            SSH target for deployment.
  --ssh-port PORT             SSH port. Default: 22.
  --backend-url URL           Backend base URL reachable from the host agent.
  --bootstrap-token TOKEN     Agent bootstrap token configured on the backend.
  --agent-hostname NAME       Hostname to register in the backend.
  --agent-url URL             Public URL workers use to call the agent. Default: http://AGENT_HOSTNAME:9100.
  --listen HOST:PORT          Agent listen address. Default: 0.0.0.0:9100.
  --capabilities LIST         Comma-separated Host Agent capabilities.
  --install-dir PATH          Remote install directory. Default: /opt/pqc-host-agent.
  --env-file PATH             Remote environment file. Default: /etc/pqc-host-agent.env.
  --service-name NAME         systemd service name. Default: pqc-host-agent.
  --dry-run                   Validate arguments and print the deployment plan only.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      SSH_TARGET="${2:-}"
      shift 2
      ;;
    --ssh-port)
      SSH_PORT="${2:-}"
      shift 2
      ;;
    --backend-url)
      BACKEND_URL="${2:-}"
      shift 2
      ;;
    --bootstrap-token)
      BOOTSTRAP_TOKEN="${2:-}"
      shift 2
      ;;
    --agent-hostname)
      AGENT_HOSTNAME="${2:-}"
      shift 2
      ;;
    --agent-url)
      AGENT_URL="${2:-}"
      shift 2
      ;;
    --listen)
      AGENT_LISTEN="${2:-}"
      shift 2
      ;;
    --capabilities)
      AGENT_CAPABILITIES="${2:-}"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="${2:-}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --service-name)
      SERVICE_NAME="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_arg() {
  local name="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    echo "Missing required option: $name" >&2
    usage >&2
    exit 2
  fi
}

shell_quote() {
  printf "%q" "$1"
}

require_arg "--host" "$SSH_TARGET"
require_arg "--backend-url" "$BACKEND_URL"
require_arg "--bootstrap-token" "$BOOTSTRAP_TOKEN"
require_arg "--agent-hostname" "$AGENT_HOSTNAME"

if [[ -z "$AGENT_URL" ]]; then
  AGENT_URL="http://${AGENT_HOSTNAME}:9100"
fi

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<PLAN
Host Agent deployment plan
  ssh_target:      ${SSH_TARGET}
  ssh_port:        ${SSH_PORT}
  backend_url:     ${BACKEND_URL}
  agent_hostname:  ${AGENT_HOSTNAME}
  agent_url:       ${AGENT_URL}
  listen:          ${AGENT_LISTEN}
  capabilities:    ${AGENT_CAPABILITIES}
  install_dir:     ${INSTALL_DIR}
  env_file:        ${ENV_FILE}
  service_name:    ${SERVICE_NAME}
PLAN
  exit 0
fi

archive="$(mktemp)"
trap 'rm -f "$archive"' EXIT

tar \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  -C "$ROOT_DIR/testbed/agent" \
  -czf "$archive" \
  mock_agent.py discovery host_scanners

remote_archive="/tmp/pqc-host-agent-${USER:-deploy}-$$.tgz"
scp -P "$SSH_PORT" "$archive" "${SSH_TARGET}:${remote_archive}"

remote_env=(
  "BACKEND_URL=$(shell_quote "$BACKEND_URL")"
  "BOOTSTRAP_TOKEN=$(shell_quote "$BOOTSTRAP_TOKEN")"
  "AGENT_HOSTNAME=$(shell_quote "$AGENT_HOSTNAME")"
  "AGENT_URL=$(shell_quote "$AGENT_URL")"
  "AGENT_LISTEN=$(shell_quote "$AGENT_LISTEN")"
  "AGENT_CAPABILITIES=$(shell_quote "$AGENT_CAPABILITIES")"
  "INSTALL_DIR=$(shell_quote "$INSTALL_DIR")"
  "ENV_FILE=$(shell_quote "$ENV_FILE")"
  "SERVICE_NAME=$(shell_quote "$SERVICE_NAME")"
  "REMOTE_ARCHIVE=$(shell_quote "$remote_archive")"
)

ssh -p "$SSH_PORT" "$SSH_TARGET" "${remote_env[*]} bash -s" <<'REMOTE'
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

install_package() {
  local package="$1"
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update
    $SUDO apt-get install -y "$package"
  elif command -v apk >/dev/null 2>&1; then
    $SUDO apk add --no-cache "$package"
  elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y "$package"
  elif command -v yum >/dev/null 2>&1; then
    $SUDO yum install -y "$package"
  else
    echo "Package manager not found. Install ${package} manually." >&2
    return 1
  fi
}

if ! command -v python3 >/dev/null 2>&1; then
  install_package python3
fi

if ! command -v openssl >/dev/null 2>&1; then
  install_package openssl
fi

$SUDO mkdir -p "$INSTALL_DIR" /var/lib/pqc-host-agent
$SUDO tar -xzf "$REMOTE_ARCHIVE" -C "$INSTALL_DIR"
$SUDO rm -f "$REMOTE_ARCHIVE"

quote_env() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//\$/\\\$}"
  value="${value//\`/\\\`}"
  printf '"%s"' "$value"
}

tmp_env="$(mktemp)"
{
  printf "BACKEND_URL=%s\n" "$(quote_env "$BACKEND_URL")"
  printf "BOOTSTRAP_TOKEN=%s\n" "$(quote_env "$BOOTSTRAP_TOKEN")"
  printf "AGENT_ROLE='host'\n"
  printf "AGENT_HOSTNAME=%s\n" "$(quote_env "$AGENT_HOSTNAME")"
  printf "AGENT_URL=%s\n" "$(quote_env "$AGENT_URL")"
  printf "AGENT_LISTEN=%s\n" "$(quote_env "$AGENT_LISTEN")"
  printf "AGENT_CAPABILITIES=%s\n" "$(quote_env "$AGENT_CAPABILITIES")"
  printf "AGENT_OS_DISTRIBUTION=%s\n" "$(quote_env "$(uname -srm)")"
} > "$tmp_env"
$SUDO install -m 0600 "$tmp_env" "$ENV_FILE"
rm -f "$tmp_env"

tmp_unit="$(mktemp)"
cat > "$tmp_unit" <<UNIT
[Unit]
Description=PQC Host Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=${ENV_FILE}
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/env python3 ${INSTALL_DIR}/mock_agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

if command -v systemctl >/dev/null 2>&1; then
  $SUDO install -m 0644 "$tmp_unit" "/etc/systemd/system/${SERVICE_NAME}.service"
  rm -f "$tmp_unit"
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable --now "${SERVICE_NAME}.service"
  $SUDO systemctl --no-pager --full status "${SERVICE_NAME}.service" || true
else
  rm -f "$tmp_unit"
  $SUDO sh -c "cd '$INSTALL_DIR' && set -a && . '$ENV_FILE' && set +a && nohup python3 '$INSTALL_DIR/mock_agent.py' >/var/log/${SERVICE_NAME}.log 2>&1 &"
  echo "systemctl not found. Started ${SERVICE_NAME} with nohup; logs: /var/log/${SERVICE_NAME}.log"
fi
REMOTE

echo "Host Agent deployed to ${SSH_TARGET} as ${SERVICE_NAME}."
