#!/usr/bin/env bash
set -euo pipefail

DEFAULT_VM_ROOT="${HOME}/.cache/vibeskills-vm/windows-proof"
VM_ROOT="${DEFAULT_VM_ROOT}"
ISO_PATH=""
DISK_IMAGE_PATH=""
VM_NAME="vibeskills-windows-proof"
DISK_GB="80"
MEMORY_MB="8192"
CPUS="4"
CPU_MODEL="max"
MACHINE_TYPE="q35"
FIRMWARE_MODE="uefi"
VNC_DISPLAY="5"
RUN_IN_FOREGROUND="0"
WITH_TPM="0"
DRY_RUN="0"
REQUIRE_KVM="0"
BOOT_KEY=""
BOOT_KEY_ROUNDS="0"
BOOT_KEY_INTERVAL_MS="1000"
USE_LEGACY_IDE="0"

usage() {
  cat <<'EOF'
Usage: bash ./scripts/setup/run-windows-proof-vm.sh --iso /absolute/path/Windows.iso [options]

Options:
  --iso PATH           Absolute path to a Windows installation ISO
  --disk-image PATH    Existing Windows disk image (.qcow2, .img, .raw, .vhdx, .vmdk)
  --vm-root PATH       VM state directory (default: ~/.cache/vibeskills-vm/windows-proof)
  --name NAME          VM name
  --disk-gb N          qcow2 system disk size in GB (default: 80)
  --memory-mb N        guest memory in MB (default: 8192)
  --cpus N             guest vCPU count (default: 4)
  --cpu-model NAME     QEMU CPU model (default: max)
  --machine-type NAME  QEMU machine type (default: q35)
  --firmware MODE      Guest firmware mode: uefi or bios (default: uefi)
  --bios               Shortcut for --firmware bios
  --vnc-display N      QEMU VNC display number (default: 5 -> tcp 5905)
  --boot-key KEY[,KEY] Repeatedly inject one or more QMP qcode keys after cold boot
                       (examples: ret, spc, ret,spc)
  --boot-key-rounds N  Number of repeated key injection rounds (default: 0; disabled)
  --boot-key-interval-ms N
                       Delay between key injection rounds in milliseconds (default: 1000)
  --legacy-ide         Use legacy IDE drive wiring instead of q35 AHCI
  --with-tpm           Start a local swtpm instance and attach TPM 2.0
  --require-kvm        Fail instead of silently falling back to TCG when /dev/kvm is unavailable
  --foreground         Keep QEMU attached to the current terminal
  --dry-run            Print the resolved launch command and exit
  --help               Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iso)
      ISO_PATH="${2:-}"
      shift 2
      ;;
    --disk-image)
      DISK_IMAGE_PATH="${2:-}"
      shift 2
      ;;
    --vm-root)
      VM_ROOT="${2:-}"
      shift 2
      ;;
    --name)
      VM_NAME="${2:-}"
      shift 2
      ;;
    --disk-gb)
      DISK_GB="${2:-}"
      shift 2
      ;;
    --memory-mb)
      MEMORY_MB="${2:-}"
      shift 2
      ;;
    --cpus)
      CPUS="${2:-}"
      shift 2
      ;;
    --cpu-model)
      CPU_MODEL="${2:-}"
      shift 2
      ;;
    --machine-type)
      MACHINE_TYPE="${2:-}"
      shift 2
      ;;
    --firmware)
      FIRMWARE_MODE="${2:-}"
      shift 2
      ;;
    --bios)
      FIRMWARE_MODE="bios"
      shift
      ;;
    --vnc-display)
      VNC_DISPLAY="${2:-}"
      shift 2
      ;;
    --boot-key)
      BOOT_KEY="${2:-}"
      shift 2
      ;;
    --boot-key-rounds)
      BOOT_KEY_ROUNDS="${2:-}"
      shift 2
      ;;
    --boot-key-interval-ms)
      BOOT_KEY_INTERVAL_MS="${2:-}"
      shift 2
      ;;
    --legacy-ide)
      USE_LEGACY_IDE="1"
      shift
      ;;
    --with-tpm)
      WITH_TPM="1"
      shift
      ;;
    --require-kvm)
      REQUIRE_KVM="1"
      shift
      ;;
    --foreground)
      RUN_IN_FOREGROUND="1"
      shift
      ;;
    --dry-run)
      DRY_RUN="1"
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

if [[ -z "${ISO_PATH}" && -z "${DISK_IMAGE_PATH}" ]]; then
  echo "[ERROR] Either --iso or --disk-image is required." >&2
  echo "[INFO] Official Windows ISO entry: https://www.microsoft.com/en-us/software-download/windows10iso" >&2
  exit 1
fi

if [[ -n "${ISO_PATH}" && ! -f "${ISO_PATH}" ]]; then
  echo "[ERROR] ISO not found: ${ISO_PATH}" >&2
  exit 1
fi

if [[ -n "${ISO_PATH}" ]]; then
  if [[ -f "${ISO_PATH}.part" ]]; then
    echo "[ERROR] ISO partial download detected: ${ISO_PATH}.part" >&2
    echo "[INFO] Wait for the download to complete before launching the VM." >&2
    exit 1
  fi

  if command -v lsof >/dev/null 2>&1; then
    if lsof "${ISO_PATH}" 2>/dev/null | awk 'NR > 1 && $4 ~ /w/ { found=1 } END { exit(found ? 0 : 1) }'; then
      echo "[ERROR] ISO is currently open for writing: ${ISO_PATH}" >&2
      echo "[INFO] Wait for the writer to finish before launching the VM." >&2
      exit 1
    fi
  fi
fi

if [[ -n "${DISK_IMAGE_PATH}" && ! -f "${DISK_IMAGE_PATH}" ]]; then
  echo "[ERROR] Disk image not found: ${DISK_IMAGE_PATH}" >&2
  exit 1
fi

if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
  echo "[ERROR] qemu-system-x86_64 is missing. Run install-local-vm-host.sh first." >&2
  exit 1
fi

if [[ "${FIRMWARE_MODE}" != "uefi" && "${FIRMWARE_MODE}" != "bios" ]]; then
  echo "[ERROR] Unsupported firmware mode: ${FIRMWARE_MODE}" >&2
  exit 1
fi

OVMF_CODE=""
OVMF_VARS_TEMPLATE=""
SEABIOS_BIN=""

if [[ "${FIRMWARE_MODE}" == "uefi" ]]; then
  for candidate in \
    /usr/share/OVMF/OVMF_CODE_4M.fd \
    /usr/share/OVMF/OVMF_CODE.fd \
    /usr/share/OVMF/OVMF_CODE_4M.ms.fd \
    /usr/share/OVMF/OVMF_CODE.ms.fd
  do
    if [[ -f "${candidate}" ]]; then
      OVMF_CODE="${candidate}"
      break
    fi
  done

  if [[ -z "${OVMF_CODE}" ]]; then
    echo "[ERROR] Unable to locate OVMF code firmware." >&2
    exit 1
  fi

  for candidate in \
    /usr/share/OVMF/OVMF_VARS_4M.fd \
    /usr/share/OVMF/OVMF_VARS.fd \
    /usr/share/OVMF/OVMF_VARS_4M.ms.fd \
    /usr/share/OVMF/OVMF_VARS.ms.fd
  do
    if [[ -f "${candidate}" ]]; then
      OVMF_VARS_TEMPLATE="${candidate}"
      break
    fi
  done

  if [[ -z "${OVMF_VARS_TEMPLATE}" ]]; then
    echo "[ERROR] Unable to locate OVMF vars firmware." >&2
    exit 1
  fi
else
  for candidate in \
    /usr/share/seabios/bios.bin \
    /usr/share/seabios/bios-256k.bin \
    /usr/share/qemu/bios.bin
  do
    if [[ -f "${candidate}" ]]; then
      SEABIOS_BIN="${candidate}"
      break
    fi
  done

  if [[ -z "${SEABIOS_BIN}" ]]; then
    echo "[ERROR] Unable to locate SeaBIOS firmware." >&2
    exit 1
  fi
fi

mkdir -p "${VM_ROOT}"
OVMF_VARS="${VM_ROOT}/OVMF_VARS.fd"
PIDFILE="${VM_ROOT}/qemu.pid"
MONITOR_SOCKET="${VM_ROOT}/monitor.sock"
QMP_SOCKET="${VM_ROOT}/qmp.sock"
SERIAL_LOG="${VM_ROOT}/serial.log"
TPM_DIR="${VM_ROOT}/tpm"
TPM_SOCKET="${VM_ROOT}/swtpm.sock"
TPM_PIDFILE="${VM_ROOT}/swtpm.pid"
BOOT_KEY_LOG="${VM_ROOT}/boot-key-sender.log"
BOOT_KEY_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/send-qmp-boot-keys.py"

SYSTEM_DRIVE_PATH=""
SYSTEM_DRIVE_FORMAT=""

if [[ -n "${DISK_IMAGE_PATH}" ]]; then
  DISK_INFO="$(qemu-img info --output=json "${DISK_IMAGE_PATH}")"
  SYSTEM_DRIVE_FORMAT="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("format",""))' <<< "${DISK_INFO}")"
  if [[ -z "${SYSTEM_DRIVE_FORMAT}" ]]; then
    echo "[ERROR] Unable to determine disk image format for ${DISK_IMAGE_PATH}" >&2
    exit 1
  fi
  SYSTEM_DRIVE_PATH="${DISK_IMAGE_PATH}"
else
  SYSTEM_DRIVE_PATH="${VM_ROOT}/windows-system.qcow2"
  SYSTEM_DRIVE_FORMAT="qcow2"
  if [[ ! -f "${SYSTEM_DRIVE_PATH}" ]]; then
    qemu-img create -f qcow2 "${SYSTEM_DRIVE_PATH}" "${DISK_GB}G" >/dev/null
  fi
fi

if [[ "${FIRMWARE_MODE}" == "uefi" && ! -f "${OVMF_VARS}" ]]; then
  cp "${OVMF_VARS_TEMPLATE}" "${OVMF_VARS}"
fi

ACCEL="tcg"
if [[ -e /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
  ACCEL="kvm"
fi

if [[ "${REQUIRE_KVM}" == "1" && "${ACCEL}" != "kvm" ]]; then
  echo "[ERROR] --require-kvm was set, but /dev/kvm is not available for read/write access on this host." >&2
  echo "[INFO] Re-run on a real KVM-capable host or guest with nested KVM passthrough enabled." >&2
  exit 1
fi

TPM_ARGS=()
if [[ "${WITH_TPM}" == "1" ]]; then
  if ! command -v swtpm >/dev/null 2>&1; then
    echo "[ERROR] swtpm is missing. Run install-local-vm-host.sh first." >&2
    exit 1
  fi
  mkdir -p "${TPM_DIR}"
  rm -f "${TPM_SOCKET}" "${TPM_PIDFILE}"
  swtpm socket \
    --tpm2 \
    --tpmstate "dir=${TPM_DIR}" \
    --ctrl "type=unixio,path=${TPM_SOCKET}" \
    --daemon \
    --pid "file=${TPM_PIDFILE}"
  TPM_ARGS=(
    -chardev "socket,id=chrtpm,path=${TPM_SOCKET}"
    -tpmdev "emulator,id=tpm0,chardev=chrtpm"
    -device "tpm-tis,tpmdev=tpm0"
  )
fi

rm -f "${PIDFILE}" "${MONITOR_SOCKET}" "${QMP_SOCKET}"

QEMU_ARGS=(
  -name "${VM_NAME}"
  -machine "${MACHINE_TYPE},accel=${ACCEL}"
  -cpu "${CPU_MODEL}"
  -smp "${CPUS}"
  -m "${MEMORY_MB}"
  -rtc base=localtime,clock=host
  -boot "order=dc,menu=on"
  -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:33890-:3389,hostfwd=tcp:127.0.0.1:22220-:22"
  -device "e1000,netdev=net0"
  -monitor "unix:${MONITOR_SOCKET},server,nowait"
  -qmp "unix:${QMP_SOCKET},server,nowait"
  -serial "file:${SERIAL_LOG}"
  -display none
  -vnc "127.0.0.1:${VNC_DISPLAY}"
)

if [[ "${FIRMWARE_MODE}" == "uefi" ]]; then
  QEMU_ARGS+=(
    -drive "if=pflash,format=raw,readonly=on,file=${OVMF_CODE}"
    -drive "if=pflash,format=raw,file=${OVMF_VARS}"
  )
else
  QEMU_ARGS+=(
    -bios "${SEABIOS_BIN}"
  )
fi

if [[ "${USE_LEGACY_IDE}" == "1" ]]; then
  QEMU_ARGS+=(
    -drive "file=${SYSTEM_DRIVE_PATH},format=${SYSTEM_DRIVE_FORMAT},if=ide,index=0"
  )
  if [[ -n "${ISO_PATH}" ]]; then
    QEMU_ARGS+=(
      -drive "file=${ISO_PATH},media=cdrom,if=ide,index=1"
    )
  fi
else
  QEMU_ARGS+=(
    -device ich9-ahci,id=ahci
    -drive "id=system,if=none,file=${SYSTEM_DRIVE_PATH},format=${SYSTEM_DRIVE_FORMAT}"
    -device "ide-hd,drive=system,bus=ahci.0"
  )
fi

if [[ -n "${ISO_PATH}" && "${USE_LEGACY_IDE}" != "1" ]]; then
  QEMU_ARGS+=(
    -drive "id=installer,if=none,media=cdrom,file=${ISO_PATH}"
    -device "ide-cd,drive=installer,bus=ahci.1"
  )
fi

if [[ "${RUN_IN_FOREGROUND}" == "0" ]]; then
  QEMU_ARGS+=(-daemonize -pidfile "${PIDFILE}")
fi

if [[ "${#TPM_ARGS[@]}" -gt 0 ]]; then
  QEMU_ARGS+=("${TPM_ARGS[@]}")
fi

run_boot_key_sender() {
  if [[ -z "${BOOT_KEY}" ]]; then
    return 0
  fi

  if ! [[ "${BOOT_KEY_ROUNDS}" =~ ^[0-9]+$ ]] || [[ "${BOOT_KEY_ROUNDS}" == "0" ]]; then
    echo "[WARN] --boot-key was set but --boot-key-rounds is 0; skipping key injection." >&2
    return 0
  fi

  rm -f "${BOOT_KEY_LOG}"
  nohup python3 "${BOOT_KEY_SCRIPT}" "${QMP_SOCKET}" "${BOOT_KEY}" "${BOOT_KEY_ROUNDS}" "${BOOT_KEY_INTERVAL_MS}" >"${BOOT_KEY_LOG}" 2>&1 &
}

echo "[INFO] VM root: ${VM_ROOT}"
echo "[INFO] Acceleration: ${ACCEL}"
echo "[INFO] Firmware mode: ${FIRMWARE_MODE}"
echo "[INFO] CPU model: ${CPU_MODEL}"
echo "[INFO] Machine type: ${MACHINE_TYPE}"
echo "[INFO] Require KVM: ${REQUIRE_KVM}"
echo "[INFO] Storage path: $( [[ "${USE_LEGACY_IDE}" == "1" ]] && echo legacy-ide || echo ahci )"
echo "[INFO] System drive: ${SYSTEM_DRIVE_PATH} (${SYSTEM_DRIVE_FORMAT})"
if [[ -n "${ISO_PATH}" ]]; then
  echo "[INFO] Installer ISO: ${ISO_PATH}"
fi
if [[ -n "${BOOT_KEY}" ]]; then
  echo "[INFO] Boot key injection: key=${BOOT_KEY} rounds=${BOOT_KEY_ROUNDS} interval_ms=${BOOT_KEY_INTERVAL_MS}"
  echo "[INFO] Boot key sender log: ${BOOT_KEY_LOG}"
fi
echo "[INFO] VNC endpoint: 127.0.0.1:$((5900 + VNC_DISPLAY))"
echo "[INFO] RDP forward (after guest setup): 127.0.0.1:33890"
echo "[INFO] SSH forward (after guest setup): 127.0.0.1:22220"

if [[ "${DRY_RUN}" == "1" ]]; then
  printf '[DRY-RUN] qemu-system-x86_64'
  printf ' %q' "${QEMU_ARGS[@]}"
  printf '\n'
  exit 0
fi

run_boot_key_sender
qemu-system-x86_64 "${QEMU_ARGS[@]}"

if [[ "${RUN_IN_FOREGROUND}" == "0" ]]; then
  echo "[OK] Windows VM started in the background."
  if [[ -f "${PIDFILE}" ]]; then
    echo "[OK] QEMU pid: $(cat "${PIDFILE}")"
  fi
fi
