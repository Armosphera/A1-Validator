#!/usr/bin/env bash
# scripts/spawn-worker.sh — Spawn a validator-porting worker for A1-Validator.
#
# Pattern from armosphera/A1-AI-ERP-SBOS-MSTUDIO-sovereign/.orchestration/
# but simplified for the single-task pattern of A1-Validator.
#
# Usage:
#   bash scripts/spawn-worker.sh <validator-name>
#   bash scripts/spawn-worker.sh <validator-name> --no-worktree
#
# What it does:
#   1. Reads .orchestration/program.md as the agent charter
#   2. Reads .orchestration/validator-port-queue.md to find the next port
#   3. Creates a worktree (unless --no-worktree)
#   4. Touches .orchestration/port-<N>-ready (so the agent knows where to start)
#   5. Logs the spawn event to .orchestration/spawn.log

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ORCH_DIR="$REPO_ROOT/.orchestration"
LOG="$ORCH_DIR/spawn.log"
NAME="${1:-}"
NO_WORKTREE=false

if [ -z "$NAME" ]; then
  echo "Usage: $0 <validator-name> [--no-worktree]"
  echo
  echo "Available names:"
  grep -oE '\| `[^`]+` \|' "$ORCH_DIR/validator-port-queue.md" 2>/dev/null \
    | sed 's/| `//; s/` |//' | head -25 || true
  exit 1
fi

if [ "${2:-}" = "--no-worktree" ]; then
  NO_WORKTREE=true
fi

mkdir -p "$ORCH_DIR"
touch "$LOG"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "spawn: validator=$NAME worktree=$( [ "$NO_WORKTREE" = true ] && echo no || echo yes )"

# 1. Find the queue row for this validator
row=$(grep -n "| \`$NAME\`" "$ORCH_DIR/validator-port-queue.md" 2>/dev/null | head -1 | cut -d: -f1 || true)
if [ -z "$row" ]; then
  log "ERROR: validator '$NAME' not found in validator-port-queue.md"
  exit 1
fi
log "queue row: $row"

# 2. Determine port number from the queue row's leading "| N |" column.
queue_n=$(sed -n "${row}p" "$ORCH_DIR/validator-port-queue.md" \
  | sed -nE 's/^\|[[:space:]]*([0-9]+)[[:space:]]*\|.*/\1/p')
if [ -z "$queue_n" ]; then
  log "ERROR: could not parse queue number from row $row"
  exit 1
fi
log "queue number: $queue_n"

# Barrier is a relative path under the worktree root.
barrier=".orchestration/port-${queue_n}-ready"
worktree="$REPO_ROOT/.worktrees/port-$queue_n-$NAME"
branch="orch/port-$queue_n-$NAME"

if [ -d "$worktree" ]; then
  log "worktree already exists at $worktree — skipping creation"
else
  log "creating worktree at $worktree on branch $branch"
  git -C "$REPO_ROOT" worktree add -b "$branch" "$worktree" main
fi

# 3. Touch the ready barrier inside the worktree (relative path from worktree root).
touch "$worktree/$barrier"
log "touched $worktree/$barrier"

log "spawn complete — agent should now read $ORCH_DIR/program.md and execute the loop"