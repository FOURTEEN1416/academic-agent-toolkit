#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash ./scripts/setup/check-kvm-host-readiness.sh

Report whether the current machine is a truthful target for KVM-backed Windows proof reruns.
This script does not claim that Windows or Claude proof has completed.
EOF
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

QEMU_BIN="$(command -v qemu-system-x86_64 || true)"
VIRSH_BIN="$(command -v virsh || true)"
VIRT_HOST_VALIDATE_BIN="$(command -v virt-host-validate || true)"
SYSTEMD_DETECT_VIRT_BIN="$(command -v systemd-detect-virt || true)"
CPU_FLAGS_LINE="$(grep -m1 '^flags' /proc/cpuinfo 2>/dev/null || true)"
LSCPU_OUTPUT="$(lscpu 2>/dev/null || true)"
HYPERVISOR_VENDOR="$(printf '%s\n' "${LSCPU_OUTPUT}" | awk -F: '/Hypervisor vendor/ {gsub(/^[ \t]+/,"",$2); print $2; exit}')"
VIRTUALIZATION_TYPE="$(printf '%s\n' "${LSCPU_OUTPUT}" | awk -F: '/Virtualization type/ {gsub(/^[ \t]+/,"",$2); print $2; exit}')"
if [[ -z "${HYPERVISOR_VENDOR}" ]]; then
  HYPERVISOR_VENDOR="$(printf '%s\n' "${LSCPU_OUTPUT}" | awk -F: '/超管理器厂商/ {gsub(/^[ \t]+/,"",$2); print $2; exit}')"
fi
if [[ -z "${VIRTUALIZATION_TYPE}" ]]; then
  VIRTUALIZATION_TYPE="$(printf '%s\n' "${LSCPU_OUTPUT}" | awk -F: '/虚拟化类型/ {gsub(/^[ \t]+/,"",$2); print $2; exit}')"
fi
SYSTEM_VIRT_KIND=""
if [[ -n "${SYSTEMD_DETECT_VIRT_BIN}" ]]; then
  SYSTEM_VIRT_KIND="$("${SYSTEMD_DETECT_VIRT_BIN}" 2>/dev/null || true)"
fi

DEV_KVM_STATUS="absent"
if [[ -e /dev/kvm ]]; then
  if [[ -r /dev/kvm && -w /dev/kvm ]]; then
    DEV_KVM_STATUS="rw"
  elif [[ -r /dev/kvm ]]; then
    DEV_KVM_STATUS="ro"
  else
    DEV_KVM_STATUS="present-no-access"
  fi
fi

CPU_VIRT_EXT="missing"
if grep -Eq '\b(vmx|svm)\b' <<< "${CPU_FLAGS_LINE}"; then
  CPU_VIRT_EXT="present"
fi

STATUS="not-ready"
REASON="unknown"

if [[ -z "${QEMU_BIN}" ]]; then
  STATUS="not-ready"
  REASON="missing-qemu"
elif [[ "${DEV_KVM_STATUS}" == "rw" ]]; then
  STATUS="ready"
  REASON="kvm-available"
elif [[ -n "${HYPERVISOR_VENDOR}" ]]; then
  STATUS="not-ready"
  REASON="nested-guest-without-kvm-passthrough"
elif [[ -n "${SYSTEM_VIRT_KIND}" ]]; then
  STATUS="not-ready"
  REASON="virtualized-guest-without-kvm-passthrough"
elif [[ "${DEV_KVM_STATUS}" == "present-no-access" || "${DEV_KVM_STATUS}" == "ro" ]]; then
  STATUS="not-ready"
  REASON="kvm-device-permission"
else
  STATUS="not-ready"
  REASON="kvm-device-absent"
fi

echo "status=${STATUS}"
echo "reason=${REASON}"
echo "qemu=${QEMU_BIN:-missing}"
echo "virsh=${VIRSH_BIN:-missing}"
echo "virt_host_validate=${VIRT_HOST_VALIDATE_BIN:-missing}"
echo "systemd_detect_virt=${SYSTEMD_DETECT_VIRT_BIN:-missing}"
echo "dev_kvm=${DEV_KVM_STATUS}"
echo "cpu_virtualization_extensions=${CPU_VIRT_EXT}"
echo "hypervisor_vendor=${HYPERVISOR_VENDOR:-none}"
echo "virtualization_type=${VIRTUALIZATION_TYPE:-none}"
echo "detected_virtualization=${SYSTEM_VIRT_KIND:-none}"

if [[ -n "${HYPERVISOR_VENDOR}" || -n "${SYSTEM_VIRT_KIND}" ]]; then
  echo "truth=This environment is itself virtualized. A host switch cannot be completed from inside this guest unless nested KVM is passed through."
fi

if [[ "${STATUS}" == "ready" ]]; then
  echo "next_step=bash ./scripts/setup/run-windows-proof-vm.sh --require-kvm --iso /absolute/path/Windows.iso"
  exit 0
fi

echo "next_step=Move this repo and ISO to a host where /dev/kvm is readable and writable, then re-run the existing ISO route with --require-kvm."
exit 1
