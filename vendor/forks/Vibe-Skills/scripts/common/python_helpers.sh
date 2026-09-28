#!/usr/bin/env bash

if [[ -z "${PYTHON_MIN_MAJOR+x}" ]]; then
  PYTHON_MIN_MAJOR=3
fi
if [[ -z "${PYTHON_MIN_MINOR+x}" ]]; then
  PYTHON_MIN_MINOR=10
fi

python_version_of() {
  local candidate="$1"
  "${candidate}" - <<'PY'
import sys
print(f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}")
PY
}

python_meets_minimum() {
  local candidate="$1"
  local version major minor patch
  version="$(python_version_of "${candidate}" 2>/dev/null || true)"
  [[ -n "${version}" ]] || return 1
  IFS='.' read -r major minor patch <<EOF
${version}
EOF
  [[ -n "${major}" && -n "${minor}" ]] || return 1
  if (( major > PYTHON_MIN_MAJOR )); then
    return 0
  fi
  if (( major == PYTHON_MIN_MAJOR && minor >= PYTHON_MIN_MINOR )); then
    return 0
  fi
  return 1
}

pick_supported_python() {
  local candidate resolved=""
  for candidate in python3 python; do
    if ! resolved="$(command -v "${candidate}" 2>/dev/null)"; then
      continue
    fi
    if [[ -n "${resolved}" ]] && python_meets_minimum "${resolved}"; then
      printf '%s' "${resolved}"
      return 0
    fi
  done
  return 1
}

print_python_requirement_error() {
  local context="$1"
  local candidate resolved version found_any="false"
  echo "[FAIL] ${context} requires Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+." >&2
  for candidate in python3 python; do
    if resolved="$(command -v "${candidate}" 2>/dev/null)"; then
      found_any="true"
      version="$(python_version_of "${resolved}" 2>/dev/null || echo unknown)"
      echo "[FAIL] Detected ${candidate} -> ${resolved} (${version})" >&2
    fi
  done
  if [[ "${found_any}" != "true" ]]; then
    echo "[FAIL] No usable python3/python executable was found in PATH." >&2
  fi
  if [[ "$(uname -s 2>/dev/null)" == "Darwin" ]]; then
    echo "[FAIL] macOS often provides zsh plus an old/missing system Python. Install a modern Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ and ensure 'python3 --version' reports >= ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR} before rerunning." >&2
  else
    echo "[FAIL] Install a modern Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ and ensure 'python3 --version' reports >= ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR} before rerunning." >&2
  fi
}

main() {
  local command="${1:-}"
  local context="${2:-Python entrypoint}"
  local python_bin=""

  case "${command}" in
    --print-supported-python)
      python_bin="$(pick_supported_python || true)"
      if [[ -z "${python_bin}" ]]; then
        print_python_requirement_error "${context}"
        return 1
      fi
      printf '%s\n' "${python_bin}"
      return 0
      ;;
    "")
      echo "Usage: $0 --print-supported-python [context]" >&2
      return 2
      ;;
    *)
      echo "Unknown command: ${command}" >&2
      echo "Usage: $0 --print-supported-python [context]" >&2
      return 2
      ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
