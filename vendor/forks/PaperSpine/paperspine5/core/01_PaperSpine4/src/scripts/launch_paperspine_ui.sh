#!/usr/bin/env bash
# Start or reuse the PaperSpine5 loopback Web workspace. No terminal UI is used.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$SCRIPT_DIR/paperspine5_web.py"

case "${1:-}" in
    -h|--help)
        cat <<'EOF'
PaperSpine5 Product Web launcher

Usage:
  launch_paperspine_ui.sh [profile-directory]
  launch_paperspine_ui.sh -h | --help

The default reuses the remembered public profile. Help never starts or
reuses a Product Web process and never writes files.
EOF
        exit 0
        ;;
esac

PROFILE_ARGS=()
if [ -n "${1:-}" ]; then
    PROFILE_ARGS=(--profile-root "$1")
fi

if [ ! -f "$LAUNCHER" ]; then
    echo "PaperSpine5 Web launcher not found: $LAUNCHER" >&2
    exit 1
fi

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Python 3 not found. Install Python and retry." >&2
    exit 1
fi

export PYTHONDONTWRITEBYTECODE=1
exec "$PYTHON" -B "$LAUNCHER" launch "${PROFILE_ARGS[@]}"
