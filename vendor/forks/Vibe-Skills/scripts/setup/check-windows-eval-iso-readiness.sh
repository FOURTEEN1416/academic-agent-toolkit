#!/usr/bin/env bash
set -euo pipefail

ISO_PATH="${HOME}/Downloads/windows11-eval.iso"
SOURCE_URL="https://aka.ms/Win11E-ISO-25H2-en-us"

usage() {
  cat <<'EOF'
Usage: bash ./scripts/setup/check-windows-eval-iso-readiness.sh [--iso PATH]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iso)
      ISO_PATH="${2:-}"
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

PART_PATH="${ISO_PATH}.part"

HEADERS="$(mktemp)"
trap 'rm -f "${HEADERS}"' EXIT

if curl -I -L --max-time 30 -D "${HEADERS}" -o /dev/null "${SOURCE_URL}" >/dev/null 2>&1; then
  EXPECTED_BYTES="$(awk '/^Content-Length: /{sub(/\r$/,"",$2); print $2}' "${HEADERS}" | tail -n 1)"
else
  EXPECTED_BYTES=""
  echo "iso_path=${ISO_PATH}"
  echo "part_path=${PART_PATH}"
  echo "expected_bytes="
  echo "status=probe-failed"
  exit 5
fi

echo "iso_path=${ISO_PATH}"
echo "part_path=${PART_PATH}"
echo "expected_bytes=${EXPECTED_BYTES}"

if [[ -f "${PART_PATH}" ]]; then
  ACTUAL_PART="$(python3 - "${PART_PATH}" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).stat().st_size)
PY
)"

  PART_WRITER_OPEN="0"
  if command -v lsof >/dev/null 2>&1; then
    if lsof "${PART_PATH}" 2>/dev/null | awk 'NR > 1 && $4 ~ /w/ { found=1 } END { exit(found ? 0 : 1) }'; then
      PART_WRITER_OPEN="1"
    fi
  fi

  if [[ -n "${EXPECTED_BYTES}" && "${ACTUAL_PART}" == "${EXPECTED_BYTES}" && "${PART_WRITER_OPEN}" == "0" ]]; then
    mv "${PART_PATH}" "${ISO_PATH}"
    echo "status=ready"
    echo "current_bytes=${ACTUAL_PART}"
    exit 0
  fi

  echo "status=downloading"
  echo "current_bytes=${ACTUAL_PART}"
  exit 2
fi

if [[ ! -f "${ISO_PATH}" ]]; then
  echo "status=missing"
  exit 1
fi

ACTUAL_BYTES="$(python3 - "${ISO_PATH}" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).stat().st_size)
PY
)"
echo "current_bytes=${ACTUAL_BYTES}"

if [[ -n "${EXPECTED_BYTES}" && "${ACTUAL_BYTES}" != "${EXPECTED_BYTES}" ]]; then
  echo "status=size-mismatch"
  exit 3
fi

if command -v lsof >/dev/null 2>&1; then
  if lsof "${ISO_PATH}" 2>/dev/null | awk 'NR > 1 && $4 ~ /w/ { found=1 } END { exit(found ? 0 : 1) }'; then
    echo "status=writer-open"
    exit 4
  fi
fi

echo "status=ready"
