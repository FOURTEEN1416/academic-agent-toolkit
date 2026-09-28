#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: bash ./scripts/setup/install-local-vm-host.sh

Install the minimum local host dependencies needed to run a Windows proof VM
on Ubuntu. This script is honest about KVM availability and does not claim any
guest-side proof completion.
EOF
  exit 0
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "[ERROR] apt-get is required on this host." >&2
  exit 1
fi

if [[ "${EUID}" -eq 0 ]]; then
  SUDO=()
elif sudo -n true >/dev/null 2>&1; then
  SUDO=(sudo)
else
  echo "[ERROR] sudo without an interactive password prompt is required." >&2
  exit 1
fi

PACKAGES=(
  qemu-system-x86
  qemu-utils
  ovmf
  swtpm
  genisoimage
)

echo "[INFO] Installing VM host dependencies: ${PACKAGES[*]}"
"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y "${PACKAGES[@]}"

echo
echo "[INFO] Host capability summary"
if [[ -e /dev/kvm ]]; then
  echo "[OK] /dev/kvm detected; hardware acceleration may be available."
else
  echo "[WARN] /dev/kvm not detected; Windows guests will use slower TCG emulation."
fi

echo "[OK] qemu-system-x86_64: $(qemu-system-x86_64 --version | head -n 1)"
echo "[OK] qemu-img: $(qemu-img --version | head -n 1)"
echo "[OK] swtpm: $(swtpm --version | head -n 1)"

for candidate in \
  /usr/share/OVMF/OVMF_CODE_4M.ms.fd \
  /usr/share/OVMF/OVMF_CODE_4M.fd \
  /usr/share/OVMF/OVMF_CODE.ms.fd \
  /usr/share/OVMF/OVMF_CODE.fd
do
  if [[ -f "${candidate}" ]]; then
    echo "[OK] OVMF code firmware: ${candidate}"
    break
  fi
done

echo "[OK] Local VM host dependencies are installed."
