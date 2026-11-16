#!/usr/bin/env bash
# autoupdate-skills.sh --dest=~/skills must hand the installer an expanded $HOME path.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/bin" "$TMP_DIR/home" "$TMP_DIR/state" "$TMP_DIR/repo/scripts"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'case " $* " in' \
  '  *" rev-parse HEAD "*) printf "test-revision\\n" ;;' \
  'esac' \
  'exit 0' >"$TMP_DIR/bin/git"
chmod +x "$TMP_DIR/bin/git"

cp "$REPO_ROOT/scripts/autoupdate-skills.sh" "$TMP_DIR/repo/scripts/autoupdate-skills.sh"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'printf "%s\\n" "$*" >>"$AUTOUPDATE_TEST_CALLS"' \
  'exit 0' >"$TMP_DIR/repo/scripts/update-codex-skills.sh"
chmod +x "$TMP_DIR/repo/scripts/update-codex-skills.sh"

cd "$TMP_DIR"
AUTOUPDATE_TEST_CALLS="$TMP_DIR/calls" \
HOME="$TMP_DIR/home" \
XDG_STATE_HOME="$TMP_DIR/state" \
PATH="$TMP_DIR/bin:$PATH" \
  bash "$TMP_DIR/repo/scripts/autoupdate-skills.sh" '--dest=~/skills' --force

if [ ! -s "$TMP_DIR/calls" ]; then
  echo "The installer was not invoked." >&2
  exit 1
fi
if grep -q '~' "$TMP_DIR/calls"; then
  echo "A literal '~' reached the installer:" >&2
  cat "$TMP_DIR/calls" >&2
  exit 1
fi
if ! grep -q -- "$TMP_DIR/home/skills" "$TMP_DIR/calls"; then
  echo "The installer did not receive \$HOME/skills:" >&2
  cat "$TMP_DIR/calls" >&2
  exit 1
fi

echo "autoupdate-skills --dest=~ expansion test: PASS"
