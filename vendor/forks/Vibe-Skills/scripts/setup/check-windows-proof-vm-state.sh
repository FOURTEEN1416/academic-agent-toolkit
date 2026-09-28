#!/usr/bin/env bash
set -euo pipefail

VM_ROOT="${HOME}/.cache/vibeskills-vm/windows-proof"

usage() {
  cat <<'EOF'
Usage: bash ./scripts/setup/check-windows-proof-vm-state.sh [--vm-root PATH]
EOF
}

is_valid_pid() {
  local value="$1"
  [[ "${value}" =~ ^[0-9]+$ ]] && (( value > 0 ))
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vm-root)
      VM_ROOT="${2:-}"
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

if [[ -z "${VM_ROOT}" ]]; then
  echo "[ERROR] --vm-root must not be empty." >&2
  exit 1
fi

PIDFILE="${VM_ROOT}/qemu.pid"
MONITOR_SOCKET="${VM_ROOT}/monitor.sock"
QMP_SOCKET="${VM_ROOT}/qmp.sock"
SERIAL_LOG="${VM_ROOT}/serial.log"
TPM_PIDFILE="${VM_ROOT}/swtpm.pid"

echo "vm_root=${VM_ROOT}"

if [[ ! -f "${PIDFILE}" ]]; then
  echo "status=stopped"
  exit 1
fi

QEMU_PID="$(tr -d '[:space:]' < "${PIDFILE}" 2>/dev/null || true)"
if ! is_valid_pid "${QEMU_PID}"; then
  echo "status=invalid-pidfile"
  exit 2
fi
echo "qemu_pid=${QEMU_PID}"

if ! kill -0 "${QEMU_PID}" >/dev/null 2>&1; then
  echo "status=stale-pidfile"
  exit 3
fi

echo "status=running"
echo "monitor_socket=$( [[ -S "${MONITOR_SOCKET}" ]] && echo present || echo missing )"
echo "qmp_socket=$( [[ -S "${QMP_SOCKET}" ]] && echo present || echo missing )"
echo "serial_log=$( [[ -f "${SERIAL_LOG}" ]] && echo present || echo missing )"

if [[ -f "${TPM_PIDFILE}" ]]; then
  TPM_PID="$(tr -d '[:space:]' < "${TPM_PIDFILE}" 2>/dev/null || true)"
  if is_valid_pid "${TPM_PID}" && kill -0 "${TPM_PID}" >/dev/null 2>&1; then
    echo "tpm=status-running pid=${TPM_PID}"
  elif is_valid_pid "${TPM_PID}"; then
    echo "tpm=status-stale-pidfile pid=${TPM_PID}"
  else
    echo "tpm=status-invalid-pidfile"
  fi
else
  echo "tpm=status-absent"
fi

PORT_LINES="$(ss -ltnp 2>/dev/null | awk -v pid="${QEMU_PID}" '$0 ~ ("pid=" pid "([, )]|$)") {print}')"
if [[ -n "${PORT_LINES}" ]]; then
  echo "ports_begin"
  printf '%s\n' "${PORT_LINES}"
  echo "ports_end"
fi
