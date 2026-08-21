#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# dev.sh — Start the local backend and frontend development servers.
#
# Backend: starts from port 6185 and uses the next available port.
# Frontend: starts from port 3007 and proxies API requests to the selected backend.
#
# Usage:
#   ./scripts/dev.sh
#   SKIP_INSTALL=1 ./scripts/dev.sh
#   DEV_BACKEND_PORT=7000 DEV_FRONTEND_PORT=4000 ./scripts/dev.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_DIR="$PROJECT_ROOT/dashboard"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { printf "%b[dev]%b %s\n" "$CYAN" "$NC" "$*"; }
ok()   { printf "%b[dev]%b %s\n" "$GREEN" "$NC" "$*"; }
err()  { printf "%b[dev]%b %s\n" "$RED" "$NC" "$*" >&2; }

# Backend output filter: credential lines (Username / password) are shown in
# green, error lines in red; everything else only goes to the log file.
CREDENTIAL_RE='[Uu]sername|[Pp]assword'
BACKEND_ERROR_RE='ERROR|CRITICAL|Traceback|error:'
BACKEND_LOG="$PROJECT_ROOT/logs/dev-backend.log"

filter_backend_output() {
  local line
  while IFS= read -r line; do
    printf '%s\n' "$line" >>"$BACKEND_LOG"
    if [[ "$line" =~ $CREDENTIAL_RE ]]; then
      printf '%b%s%b\n' "$GREEN" "$line" "$NC"
    elif [[ "$line" =~ $BACKEND_ERROR_RE ]]; then
      printf '%b%s%b\n' "$RED" "$line" "$NC" >&2
    fi
  done
}

cd "$PROJECT_ROOT"

# Validate executables even when dependency installation is skipped so failures
# are reported before either development server starts.
if ! command -v uv >/dev/null 2>&1 || ! uv --version >/dev/null 2>&1; then
  err "uv is unavailable. Install the standalone binary and ensure it precedes pyenv shims in PATH:"
  err "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  err '  export PATH="$HOME/.local/bin:$PATH"'
  exit 1
fi
if ! command -v pnpm >/dev/null 2>&1 || ! pnpm --version >/dev/null 2>&1; then
  err "pnpm is unavailable. Install it with: npm install -g pnpm@10"
  exit 1
fi

# Install dependencies on the first run. Set SKIP_INSTALL=1 to skip this step.
if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
    log "Backend dependencies are missing; running uv sync..."
    uv sync
  fi
  if [[ ! -d "$DASHBOARD_DIR/node_modules" ]]; then
    log "Frontend dependencies are missing; running pnpm install..."
    (cd "$DASHBOARD_DIR" && pnpm install)
  fi
fi

BACKEND_BASE_PORT="${DEV_BACKEND_PORT:-6185}"
FRONTEND_BASE_PORT="${DEV_FRONTEND_PORT:-3007}"

if [[ ! "$BACKEND_BASE_PORT" =~ ^[0-9]+$ ]] \
  || ((BACKEND_BASE_PORT < 1 || BACKEND_BASE_PORT > 65535)); then
  err "Invalid backend port: $BACKEND_BASE_PORT"
  exit 1
fi
if [[ ! "$FRONTEND_BASE_PORT" =~ ^[0-9]+$ ]] \
  || ((FRONTEND_BASE_PORT < 1 || FRONTEND_BASE_PORT > 65535)); then
  err "Invalid frontend port: $FRONTEND_BASE_PORT"
  exit 1
fi

# Select both ports in one process and keep each socket open until selection is
# complete, preventing custom overlapping ranges from choosing the same port.
PORT_SELECTION="$(uv run python - "$BACKEND_BASE_PORT" "$FRONTEND_BASE_PORT" <<'PY'
import socket
import sys

selected_ports = []
reserved_sockets = []
for raw_port in sys.argv[1:]:
    port = int(raw_port)
    while port <= 65535:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            sock.close()
            port += 1
            continue
        reserved_sockets.append(sock)
        selected_ports.append(port)
        break
    else:
        raise SystemExit(f"No free port found at or above {raw_port}")

print(*selected_ports)
PY
)"
read -r BACKEND_PORT FRONTEND_PORT <<<"$PORT_SELECTION"

BACKEND_PID=""
FRONTEND_PID=""
CLEANED_UP=0

mkdir -p "$PROJECT_ROOT/logs"
: >"$BACKEND_LOG"

cleanup() {
  if [[ "$CLEANED_UP" == "1" ]]; then
    return
  fi
  CLEANED_UP=1

  log "Stopping development servers..."
  if [[ -n "$FRONTEND_PID" ]]; then
    pkill -TERM -P "$FRONTEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]]; then
    pkill -TERM -P "$BACKEND_PID" 2>/dev/null || true
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  [[ -n "$FRONTEND_PID" ]] && wait "$FRONTEND_PID" 2>/dev/null || true
  [[ -n "$BACKEND_PID" ]] && wait "$BACKEND_PID" 2>/dev/null || true
  ok "Development servers stopped."
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Start the backend. Console output is filtered (credentials and errors only);
# the full log is written to logs/dev-backend.log.
DASHBOARD_PORT="$BACKEND_PORT" uv run main.py > >(filter_backend_output) 2>&1 &
BACKEND_PID=$!

# Start the frontend.
(
  cd "$DASHBOARD_DIR"
  LIBSCLAW_DEV_BACKEND_PORT="$BACKEND_PORT" \
    LIBSCLAW_DEV_FRONTEND_PORT="$FRONTEND_PORT" \
    exec pnpm dev
) &
FRONTEND_PID=$!

printf "  Backend full log: %s (console shows credentials/errors only)\n" "$BACKEND_LOG"
printf "  Press Ctrl+C to stop both.\n\n"

# Stop both servers if either process exits. This loop works with macOS Bash 3.2,
# which does not provide `wait -n`.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

EXIT_STATUS=0
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  wait "$BACKEND_PID" || EXIT_STATUS=$?
  err "Backend exited with status $EXIT_STATUS; stopping the frontend."
else
  wait "$FRONTEND_PID" || EXIT_STATUS=$?
  err "Frontend exited with status $EXIT_STATUS; stopping the backend."
fi
exit "$EXIT_STATUS"
