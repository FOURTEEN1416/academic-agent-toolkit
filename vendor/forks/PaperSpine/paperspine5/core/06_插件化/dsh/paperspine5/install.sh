#!/usr/bin/env sh
set -eu
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="$SOURCE/core/runtime_vendor/python/bin/python3"
if [ ! -x "$PYTHON" ]; then
  if [ -f "$SOURCE/core/suite-manifest.json" ]; then
    echo "Wrong platform bundle or non-executable bundled Python. Check ZIP extraction permissions." >&2
    exit 1
  fi
  PYTHON=$(command -v python3 || command -v python)
fi
# Preserve the original positional profile and target environment options.
if [ "$#" -gt 0 ]; then
  case "$1" in -*) ;; *) PROFILE=$1; shift; set -- --profile "$PROFILE" "$@" ;; esac
fi
if [ -n "${PAPERSPINE5_DSH_TARGET:-}" ]; then
  set -- "$@" --target "$PAPERSPINE5_DSH_TARGET"
fi
exec "$PYTHON" -B -X utf8 "$SOURCE/install_bundle.py" "$@"
