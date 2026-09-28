#!/usr/bin/env bash
# PaperSpine V4 installer (macOS / Linux). Thin wrapper that delegates all file
# work to the Python sync, which generates dist/ from src/ and installs the
# single `paper-spine` skill into Claude Code, Codex, OpenClaw, and Hermes.
# Usage: bash install.sh [--clean-legacy]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SYNC="$ROOT/src/scripts/sync_local_installs.py"

if [ ! -f "$SYNC" ]; then
    echo "PaperSpine sync script not found: $SYNC" >&2
    exit 1
fi

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then PYTHON="$candidate"; break; fi
done
if [ -z "$PYTHON" ]; then
    echo "Python 3 not found on PATH. Install Python and retry." >&2
    exit 1
fi

ARGS=("$SYNC")
[ "${1:-}" = "--clean-legacy" ] && ARGS+=("--clean-legacy")

echo "Installing PaperSpine V4 (single skill, 4 hosts) via $PYTHON ..."
"$PYTHON" "${ARGS[@]}"
echo "PaperSpine V4 installed. In Claude Code or Codex, run /paperspine to start."
