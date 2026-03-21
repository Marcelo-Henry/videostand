#!/usr/bin/env bash
set -euo pipefail

STRICT=0
if [ "${1:-}" = "--strict" ]; then
  STRICT=1
fi

missing_required=0

check_cmd() {
  local name="$1"
  local required="$2"
  if command -v "$name" >/dev/null 2>&1; then
    echo "[ok]   $name"
  else
    if [ "$required" = "1" ]; then
      echo "[miss] $name"
      missing_required=1
    else
      echo "[warn] $name (optional)"
    fi
  fi
}

echo "VideoStand Skill Doctor"
echo

echo "Commands:"
check_cmd python3 1
check_cmd ffmpeg 1
check_cmd ffprobe 1
check_cmd yt-dlp 0

echo
if command -v python3 >/dev/null 2>&1; then
  if python3 -c "import faster_whisper" >/dev/null 2>&1; then
    echo "[ok]   faster-whisper Python package"
  else
    echo "[warn] faster-whisper Python package (optional for visual-only summary)"
  fi
else
  echo "[warn] faster-whisper check skipped (python3 missing)"
fi

echo
if [ "$missing_required" -eq 0 ]; then
  echo "[ok] Required dependencies are present."
  exit 0
fi

echo "[warn] Required dependencies are missing."
if [ "$STRICT" -eq 1 ]; then
  exit 1
fi

exit 0
