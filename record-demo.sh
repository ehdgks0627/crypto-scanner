#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/demo-lib.sh
source "$ROOT_DIR/scripts/demo-lib.sh"

DEMO_RECORD_SECONDS="${DEMO_RECORD_SECONDS:-300}"
DEMO_RECORD_DIR="${DEMO_RECORD_DIR:-$ROOT_DIR/demo-recordings}"
DEMO_RECORD_FILE="${DEMO_RECORD_FILE:-$DEMO_RECORD_DIR/demo-$(date +%Y%m%d-%H%M%S).mp4}"
DEMO_RECORD_FRAMERATE="${DEMO_RECORD_FRAMERATE:-30}"
DEMO_RECORD_GEOMETRY="${DEMO_RECORD_GEOMETRY:-}"
url="$(demo_dashboard_url)"

mkdir -p "$DEMO_RECORD_DIR"
demo_log "recording $url for ${DEMO_RECORD_SECONDS}s"
demo_log "output: $DEMO_RECORD_FILE"

if command -v wf-recorder >/dev/null 2>&1 && [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
  wf-recorder -t -d "$DEMO_RECORD_SECONDS" -f "$DEMO_RECORD_FILE"
  exit 0
fi

if command -v ffmpeg >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  if [[ -z "$DEMO_RECORD_GEOMETRY" ]]; then
    if command -v xdpyinfo >/dev/null 2>&1; then
      DEMO_RECORD_GEOMETRY="$(xdpyinfo | awk '/dimensions:/{print $2; exit}')"
    else
      DEMO_RECORD_GEOMETRY="1920x1080"
    fi
  fi
  ffmpeg -y \
    -video_size "$DEMO_RECORD_GEOMETRY" \
    -framerate "$DEMO_RECORD_FRAMERATE" \
    -f x11grab \
    -i "$DISPLAY" \
    -t "$DEMO_RECORD_SECONDS" \
    -pix_fmt yuv420p \
    "$DEMO_RECORD_FILE"
  exit 0
fi

demo_fail "no supported screen recorder found. Install wf-recorder on Wayland or ffmpeg with DISPLAY on X11."
