#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_HOME="$(mktemp -d)"
TMP_PROJECT="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME" "$TMP_PROJECT"' EXIT

export HOME="$TMP_HOME"

cd "$TMP_PROJECT"

# ── Codex local install ──
node "$ROOT_DIR/bin/videostand.js" init codex

LOCAL_CODEX_SKILL="$TMP_PROJECT/.codex/skills/videostand/SKILL.md"
if [[ ! -f "$LOCAL_CODEX_SKILL" ]]; then
  echo "ERROR: local codex skill file not found at $LOCAL_CODEX_SKILL"
  exit 1
fi

if [[ -f "$HOME/.codex/skills/videostand/SKILL.md" ]]; then
  echo "ERROR: global codex skill should not exist after local install"
  exit 1
fi

# codex local without --force should fail
if node "$ROOT_DIR/bin/videostand.js" init codex; then
  echo "ERROR: expected second local codex install without --force to fail"
  exit 1
fi

node "$ROOT_DIR/bin/videostand.js" init codex --force

# ── Codex global install ──
node "$ROOT_DIR/bin/videostand.js" -g init codex

GLOBAL_CODEX_SKILL="$HOME/.codex/skills/videostand/SKILL.md"
if [[ ! -f "$GLOBAL_CODEX_SKILL" ]]; then
  echo "ERROR: global codex skill file not found at $GLOBAL_CODEX_SKILL"
  exit 1
fi

# ── Kiro local install ──
node "$ROOT_DIR/bin/videostand.js" init kiro

LOCAL_KIRO_SKILL="$TMP_PROJECT/.kiro/skills/videostand/SKILL.md"
if [[ ! -f "$LOCAL_KIRO_SKILL" ]]; then
  echo "ERROR: local kiro skill file not found at $LOCAL_KIRO_SKILL"
  exit 1
fi

if [[ -f "$HOME/.kiro/skills/videostand/SKILL.md" ]]; then
  echo "ERROR: global kiro skill should not exist after local install"
  exit 1
fi

# kiro local without --force should fail
if node "$ROOT_DIR/bin/videostand.js" init kiro; then
  echo "ERROR: expected second local kiro install without --force to fail"
  exit 1
fi

node "$ROOT_DIR/bin/videostand.js" init kiro --force

# ── Kiro global install ──
node "$ROOT_DIR/bin/videostand.js" -g init kiro

GLOBAL_KIRO_SKILL="$HOME/.kiro/skills/videostand/SKILL.md"
if [[ ! -f "$GLOBAL_KIRO_SKILL" ]]; then
  echo "ERROR: global kiro skill file not found at $GLOBAL_KIRO_SKILL"
  exit 1
fi

# ── Cross-target isolation ──
# Installing kiro should not have affected codex (already installed above)
if [[ ! -f "$LOCAL_CODEX_SKILL" ]]; then
  echo "ERROR: codex local skill disappeared after kiro install"
  exit 1
fi

if [[ ! -f "$GLOBAL_CODEX_SKILL" ]]; then
  echo "ERROR: codex global skill disappeared after kiro install"
  exit 1
fi

echo "E2E passed: codex + kiro local/global init + force + isolation ok"
