#!/usr/bin/env bash
# --dest=~/skills must expand ~ to $HOME (the shell does not do it after "--dest=").
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/home" "$TMP_DIR/cwd"
cd "$TMP_DIR/cwd"

HOME="$TMP_DIR/home" bash "$REPO_ROOT/scripts/update-codex-skills.sh" \
  '--dest=~/skills' >"$TMP_DIR/stdout" 2>"$TMP_DIR/stderr"

if [ -e "$TMP_DIR/cwd/~" ]; then
  echo "A literal '~' directory was created in the working directory." >&2
  exit 1
fi
if [ ! -d "$TMP_DIR/home/skills/nature-figure" ]; then
  echo "Skills were not installed under \$HOME/skills." >&2
  cat "$TMP_DIR/stdout" "$TMP_DIR/stderr" >&2
  exit 1
fi

echo "update-codex-skills --dest=~ expansion test: PASS"
