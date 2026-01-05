#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$ROOT_DIR/.venv-e2e}"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Missing $PYTHON_BIN. Install Python 3.11 first." >&2
  exit 1
fi

"$PYTHON_BIN" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV/bin/python" -m pip install --no-deps -e "$ROOT_DIR"
"$VENV/bin/python" -m pip install \
  "websockets<14" \
  numpy \
  opuslib \
  pytest \
  pytest-asyncio \
  faster-whisper \
  rich \
  intervaltree \
  pyparsing \
  aiohttp \
  PyJWT \
  "cryptography<44"

echo "E2E venv ready at $VENV"
