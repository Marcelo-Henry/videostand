#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_HOME="$(mktemp -d)"
TMP_PROJECT="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME" "$TMP_PROJECT"' EXIT

export HOME="$TMP_HOME"

cd "$TMP_PROJECT"

# ── Bin alias check (package metadata) ──
BIN_ALIAS_PATH="$(node -p "require('$ROOT_DIR/package.json').bin.vs")"
if [[ "$BIN_ALIAS_PATH" != "./bin/videostand.js" ]]; then
  echo "ERROR: bin alias 'vs' is not mapped to ./bin/videostand.js"
  exit 1
fi

# ── Doctor command smoke checks ──
node "$ROOT_DIR/bin/videostand.js" doctor >/dev/null
node "$ROOT_DIR/bin/videostand.js" doctor codex >/dev/null
node "$ROOT_DIR/bin/videostand.js" doctor all --json >/dev/null

WHERE_ALL_OUTPUT="$(node "$ROOT_DIR/bin/videostand.js" where all)"
if [[ "$WHERE_ALL_OUTPUT" != *"codex:"* ]] || [[ "$WHERE_ALL_OUTPUT" != *"kiro:"* ]] || [[ "$WHERE_ALL_OUTPUT" != *"claude:"* ]]; then
  echo "ERROR: where all output does not include all targets"
  exit 1
fi

if [[ ! -x "$ROOT_DIR/assets/skills/videostand/scripts/doctor.sh" ]]; then
  echo "ERROR: skill doctor script missing or not executable"
  exit 1
fi
"$ROOT_DIR/assets/skills/videostand/scripts/doctor.sh" >/dev/null

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

# ── Claude local install ──
node "$ROOT_DIR/bin/videostand.js" init claude

LOCAL_CLAUDE_SKILL="$TMP_PROJECT/.claude/skills/videostand/SKILL.md"
if [[ ! -f "$LOCAL_CLAUDE_SKILL" ]]; then
  echo "ERROR: local claude skill file not found at $LOCAL_CLAUDE_SKILL"
  exit 1
fi

if [[ -f "$HOME/.claude/skills/videostand/SKILL.md" ]]; then
  echo "ERROR: global claude skill should not exist after local install"
  exit 1
fi

# claude local without --force should fail
if node "$ROOT_DIR/bin/videostand.js" init claude; then
  echo "ERROR: expected second local claude install without --force to fail"
  exit 1
fi

node "$ROOT_DIR/bin/videostand.js" init claude --force

# ── Claude global install ──
node "$ROOT_DIR/bin/videostand.js" -g init claude

GLOBAL_CLAUDE_SKILL="$HOME/.claude/skills/videostand/SKILL.md"
if [[ ! -f "$GLOBAL_CLAUDE_SKILL" ]]; then
  echo "ERROR: global claude skill file not found at $GLOBAL_CLAUDE_SKILL"
  exit 1
fi

# ── Init all (global, force) ──
node "$ROOT_DIR/bin/videostand.js" -g init all --force >/dev/null

# ── Cross-target isolation ──
# Installing claude should not have affected codex or kiro (already installed above)
if [[ ! -f "$LOCAL_CODEX_SKILL" ]]; then
  echo "ERROR: codex local skill disappeared after claude install"
  exit 1
fi

if [[ ! -f "$GLOBAL_CODEX_SKILL" ]]; then
  echo "ERROR: codex global skill disappeared after claude install"
  exit 1
fi

if [[ ! -f "$LOCAL_KIRO_SKILL" ]]; then
  echo "ERROR: kiro local skill disappeared after claude install"
  exit 1
fi

if [[ ! -f "$GLOBAL_KIRO_SKILL" ]]; then
  echo "ERROR: kiro global skill disappeared after claude install"
  exit 1
fi

echo "E2E passed: codex + kiro + claude local/global init + force + isolation ok"
