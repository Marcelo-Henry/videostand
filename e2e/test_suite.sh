#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_error() { echo -e "${RED}[ERRO]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VS_BIN="$SCRIPT_DIR/../bin/videostand.js"
SANDBOX="$SCRIPT_DIR/sandbox_suite_$$"

# Setup Sandbox
mkdir -p "$SANDBOX"
cd "$SANDBOX"
export HOME="$SANDBOX"

cleanup() {
  rm -rf "$SANDBOX"
}
trap cleanup EXIT

# ---------------------------------------------------------
# Test Modules
# ---------------------------------------------------------

test_doctor() {
  log_info "Running: Doctor Tests..."
  find . -mindepth 1 -delete
  OUTPUT=$(node "$VS_BIN" doctor codex 2>&1 || true --agent)
  if ! echo "$OUTPUT" | grep -q "VideoStand Doctor"; then
    log_error "doctor output did not contain 'VideoStand Doctor'."
    exit 1
  fi
  OUTPUT_JSON=$(node "$VS_BIN" doctor codex --json --agent)
  if ! echo "$OUTPUT_JSON" | grep -q '"doctor": "videostand"'; then
    log_error "doctor --json output is invalid."
    exit 1
  fi
  log_success "Doctor tests passed."
}

test_init() {
  log_info "Running: Init Tests..."
  find . -mindepth 1 -delete
  node "$VS_BIN" init codex --agent
  [ -d ".codex/skills/videostand" ] || { log_error "Init codex failed"; exit 1; }
  
  # Test force
  set +e
  node "$VS_BIN" init codex --agent > /dev/null 2>&1
  [ $? -ne 0 ] || { log_error "Init without force should fail"; exit 1; }
  set -e
  
  node "$VS_BIN" init codex --force --agent
  log_success "Init tests passed."
}

test_where() {
  log_info "Running: Where Tests..."
  find . -mindepth 1 -delete
  mkdir -p .cline
  node "$VS_BIN" init cline --agent
  OUTPUT=$(node "$VS_BIN" where cline --agent)
  echo "$OUTPUT" | grep -q ".cline/skills/videostand" || { log_error "Where output invalid: $OUTPUT"; exit 1; }
  log_success "Where tests passed."
}

test_remove() {
  log_info "Running: Remove Tests..."
  find . -mindepth 1 -delete
  mkdir -p .codex
  node "$VS_BIN" init codex --agent
  node "$VS_BIN" remove codex --agent
  [ ! -d ".codex/skills/videostand" ] || { log_error "Remove failed"; exit 1; }
  log_success "Remove tests passed."
}

test_status_sync() {
  log_info "Running: Status & Sync Tests (Anti-Regression)..."
  find . -mindepth 1 -delete
  mkdir -p .codex
  mkdir -p .cursor
  node "$VS_BIN" init codex --agent
  
  # Outdated test
  echo "OLD" > .codex/skills/videostand/SKILL.md
  node "$VS_BIN" status --agent | grep -q "UPDATE" || { log_error "Status did not detect outdated file"; exit 1; }
  
  # Sync test (bug regression)
  node "$VS_BIN" sync all --agent
  [ ! -d ".cursor/skills/videostand" ] || { log_error "Sync bug: installed skill to empty cursor root!"; exit 1; }
  node "$VS_BIN" status --agent | grep -q "✔" || { log_error "Sync did not update files"; exit 1; }
  
  log_success "Status & Sync tests passed."
}

test_explain() {
  log_info "Running: Explain Tests..."
  find . -mindepth 1 -delete
  node "$VS_BIN" run --explain --agent | grep -q "Explain: run" || { log_error "Explain run failed"; exit 1; }
  node "$VS_BIN" doctor --explain --agent | grep -q "Explain: doctor" || { log_error "Explain doctor failed"; exit 1; }
  log_success "Explain tests passed."
}

test_global() {
  log_info "Running: Global Tests..."
  # Clean Home for global testing
  rm -rf "$HOME/.codex"
  mkdir -p "$HOME/.codex"
  node "$VS_BIN" init codex --global --agent
  [ -d "$HOME/.codex/skills/videostand" ] || { log_error "Global init failed"; exit 1; }
  
  OUTPUT=$(node "$VS_BIN" where codex --global --agent)
  echo "$OUTPUT" | grep -q "$HOME/.codex/skills/videostand" || { log_error "Global where failed"; exit 1; }
  
  node "$VS_BIN" remove codex --global --agent
  [ ! -d "$HOME/.codex/skills/videostand" ] || { log_error "Global remove failed"; exit 1; }
  log_success "Global tests passed."
}

# ---------------------------------------------------------
# Main Execution
# ---------------------------------------------------------

log_info "=== Starting Unified VideoStand Test Suite ==="

test_doctor
test_init
test_where
test_explain
test_status_sync
test_remove
test_global

log_info "=========================================="
log_success "ALL TESTS PASSED SUCCESSFULLY! 🚀"
log_info "=========================================="
