#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$ROOT_DIR/.venv-e2e}"
PYTHON="$VENV/bin/python"
EARS_SERVER_BIN="${EARS_SERVER_BIN:-$VENV/bin/ears-server}"
PORT="${EARS_PORT:-8769}"
HOST="${EARS_HOST:-127.0.0.1}"
LOG_DIR="${EARS_LOG_DIR:-$ROOT_DIR/logs}"
LOG_FILE="$LOG_DIR/e2e_ws.log"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing venv at $VENV. Set VENV or create the environment first." >&2
  exit 1
fi

if [[ ! -x "$EARS_SERVER_BIN" ]]; then
  echo "Missing ears-server at $EARS_SERVER_BIN. Ensure the venv has the package installed." >&2
  exit 1
fi

mkdir -p "$LOG_DIR"

export EARS_BACKEND="${EARS_BACKEND:-faster_whisper}"
export EARS_MODEL="${EARS_MODEL:-tiny}"
export EARS_DEVICE="${EARS_DEVICE:-cpu}"
export STT_DISABLE_PUNCTUATION="${STT_DISABLE_PUNCTUATION:-1}"
export MATILDA_E2E_WS_URL="ws://$HOST:$PORT"

"$EARS_SERVER_BIN" --host "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
SERVER_PID=$!

cleanup() {
  if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT

ready=false
for _ in {1..200}; do
  if "$PYTHON" -c $'import asyncio, os, websockets\nasync def main():\n    async with websockets.connect(os.environ["MATILDA_E2E_WS_URL"]) as ws:\n        await asyncio.wait_for(ws.recv(), timeout=2)\nasyncio.run(main())' >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 0.1
done

if [[ "$ready" != "true" ]]; then
  echo "Server not ready; last log lines:" >&2
  tail -n 20 "$LOG_FILE" >&2 || true
  exit 1
fi

"$PYTHON" -m pytest "$ROOT_DIR/tests/integration/test_streaming_e2e.py"
