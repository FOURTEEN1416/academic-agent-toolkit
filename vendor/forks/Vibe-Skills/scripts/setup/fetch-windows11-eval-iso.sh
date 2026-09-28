#!/usr/bin/env bash
set -euo pipefail

SOURCE_URL="https://aka.ms/Win11E-ISO-25H2-en-us"
DOWNLOAD_DIR="${HOME}/Downloads"
OUTPUT_PATH=""
PRINT_ONLY="0"

usage() {
  cat <<'EOF'
Usage: bash ./scripts/setup/fetch-windows11-eval-iso.sh [options]

Options:
  --output PATH        Exact output path for the ISO
  --download-dir PATH  Download directory when --output is omitted
  --print-only         Resolve and print the final Microsoft download URL
  --help               Show this help
EOF
}

require_nonempty_path_arg() {
  local label="$1"
  local value="$2"
  if [[ -z "${value}" ]]; then
    echo "[ERROR] ${label} must not be empty." >&2
    exit 1
  fi
}

sanitize_filename() {
  local raw="$1"
  raw="$(printf '%s' "${raw}" | tr -d '\r\n')"
  raw="${raw##*/}"
  raw="${raw##*\\}"
  if [[ -z "${raw}" || "${raw}" == "." || "${raw}" == ".." ]]; then
    return 1
  fi
  printf '%s' "${raw}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
      ;;
    --download-dir)
      DOWNLOAD_DIR="${2:-}"
      shift 2
      ;;
    --print-only)
      PRINT_ONLY="1"
      shift
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

if [[ -n "${OUTPUT_PATH}" ]]; then
  require_nonempty_path_arg "--output" "${OUTPUT_PATH}"
  if [[ -d "${OUTPUT_PATH}" || "${OUTPUT_PATH}" == */ ]]; then
    echo "[ERROR] --output must be a file path, not a directory: ${OUTPUT_PATH}" >&2
    exit 1
  fi
else
  require_nonempty_path_arg "--download-dir" "${DOWNLOAD_DIR}"
  if [[ -e "${DOWNLOAD_DIR}" && ! -d "${DOWNLOAD_DIR}" ]]; then
    echo "[ERROR] --download-dir must point to a directory: ${DOWNLOAD_DIR}" >&2
    exit 1
  fi
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[ERROR] curl is required." >&2
  exit 1
fi

HEADERS="$(mktemp)"
trap 'rm -f "${HEADERS}"' EXIT

curl -I -L -D "${HEADERS}" -o /dev/null "${SOURCE_URL}" >/dev/null 2>&1

FINAL_URL="$(awk '/^Location: /{sub(/\r$/,"",$2); print $2}' "${HEADERS}" | tail -n 1)"
CONTENT_DISPOSITION="$(awk '/^Content-Disposition: /{sub(/\r$/,""); print}' "${HEADERS}" | tail -n 1)"
CONTENT_LENGTH="$(awk '/^Content-Length: /{sub(/\r$/,"",$2); print $2}' "${HEADERS}" | tail -n 1)"
FILENAME="$(python3 - "${CONTENT_DISPOSITION}" <<'PY'
import re
import sys
line = sys.argv[1]
match = re.search(r"filename\\*=UTF-8''([^;]+)", line)
if match:
    print(match.group(1))
    raise SystemExit(0)
match = re.search(r'filename="?([^";]+)"?', line)
if match:
    print(match.group(1))
PY
)"

if [[ -z "${FINAL_URL}" ]]; then
  FINAL_URL="${SOURCE_URL}"
fi

if [[ -z "${FILENAME}" ]]; then
  FILENAME="$(basename "${FINAL_URL%%\?*}")"
fi

if [[ "${PRINT_ONLY}" == "1" ]]; then
  printf 'source_url=%s\n' "${SOURCE_URL}"
  printf 'final_url=%s\n' "${FINAL_URL}"
  printf 'filename=%s\n' "${FILENAME}"
  printf 'content_length=%s\n' "${CONTENT_LENGTH}"
  exit 0
fi

if [[ -z "${OUTPUT_PATH}" ]]; then
  mkdir -p "${DOWNLOAD_DIR}"
  SAFE_FILENAME="$(sanitize_filename "${FILENAME}")" || {
    echo "[ERROR] Resolved filename is unsafe: ${FILENAME}" >&2
    exit 1
  }
  OUTPUT_PATH="${DOWNLOAD_DIR}/${SAFE_FILENAME}"
else
  mkdir -p "$(dirname "${OUTPUT_PATH}")"
fi

PARTIAL_PATH="${OUTPUT_PATH}.part"

echo "[INFO] Official source: ${SOURCE_URL}"
echo "[INFO] Resolved filename: ${FILENAME}"
if [[ -n "${CONTENT_LENGTH}" ]]; then
  echo "[INFO] Expected bytes: ${CONTENT_LENGTH}"
fi
echo "[INFO] Output path: ${OUTPUT_PATH}"
echo "[INFO] Partial path: ${PARTIAL_PATH}"

if [[ -f "${OUTPUT_PATH}" && ! -f "${PARTIAL_PATH}" ]]; then
  if [[ -n "${CONTENT_LENGTH}" ]]; then
    ACTUAL_SIZE="$(python3 - "${OUTPUT_PATH}" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).stat().st_size)
PY
)"
    if [[ "${ACTUAL_SIZE}" == "${CONTENT_LENGTH}" ]]; then
      echo "[OK] Final ISO already exists at ${OUTPUT_PATH}"
      exit 0
    fi
    echo "[WARN] Final ISO exists but size does not match expected bytes; resuming through partial path."
  fi
  mv "${OUTPUT_PATH}" "${PARTIAL_PATH}"
fi

curl -L --fail --progress-bar -C - -o "${PARTIAL_PATH}" "${FINAL_URL}"
mv "${PARTIAL_PATH}" "${OUTPUT_PATH}"
echo "[OK] Downloaded ISO to ${OUTPUT_PATH}"
