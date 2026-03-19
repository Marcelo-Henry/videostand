#!/usr/bin/env bash
set -euo pipefail

PY_BIN="${PY_BIN:-python3}"

echo "[info] Installing/upgrading faster-whisper for local ASR..."
"$PY_BIN" -m pip install --upgrade faster-whisper
echo "[ok] Local ASR dependency installed."
