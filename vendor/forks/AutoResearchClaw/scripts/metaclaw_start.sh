#!/bin/bash
# Start MetaClaw proxy for AutoResearchClaw integration.
#
# Usage:
#   ./scripts/metaclaw_start.sh              # skills_only mode (default)
#   ./scripts/metaclaw_start.sh madmax       # madmax mode (with RL training)
#   ./scripts/metaclaw_start.sh skills_only  # skills_only mode (explicit)

set -e

MODE="${1:-skills_only}"
PORT="${2:-30000}"

# Prefer a pip-installed `metaclaw` on PATH (see README: `pip install metaclaw`).
# Otherwise fall back to a local checkout; override its location with METACLAW_DIR.
if command -v metaclaw >/dev/null 2>&1; then
    echo "Starting MetaClaw in ${MODE} mode on port ${PORT}..."
    exec metaclaw start --mode "$MODE" --port "$PORT"
fi

METACLAW_DIR="${METACLAW_DIR:-$HOME/MetaClaw}"
VENV="$METACLAW_DIR/.venv"

if [ ! -d "$VENV" ]; then
    echo "ERROR: 'metaclaw' not on PATH and no venv found at $VENV"
    echo "Either: pip install metaclaw"
    echo "Or set METACLAW_DIR to your checkout and create its venv:"
    echo "  cd \"\$METACLAW_DIR\" && python -m venv .venv && source .venv/bin/activate && pip install -e '.[evolve,embedding]'"
    exit 1
fi

echo "Starting MetaClaw in ${MODE} mode on port ${PORT}..."
source "$VENV/bin/activate"
exec metaclaw start --mode "$MODE" --port "$PORT"
