#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
Windows proof media options for the current repository

Current repo-supported media inputs:
- ISO installer media via:
  bash ./scripts/setup/run-windows-proof-vm.sh --iso /absolute/path/Windows.iso
- Prepared virtual disk images via:
  bash ./scripts/setup/run-windows-proof-vm.sh --disk-image /absolute/path/Windows.vhdx

Official Microsoft sources tracked by this repo:

1. Windows 11 Enterprise Evaluation ISO
   https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise

   Current repo helper:
   bash ./scripts/setup/fetch-windows11-eval-iso.sh --download-dir ~/Downloads

2. Windows developer virtual machines
   https://developer.microsoft.com/en-us/windows/downloads/virtual-machines/

   Truth snapshot:
   - Microsoft packages these developer VMs for Hyper-V (Gen2), Parallels, VirtualBox, and VMware
   - Microsoft noted that downloads were temporarily unavailable as of October 23, 2024
   - If Microsoft re-enables that lane, the repository can already boot a prepared disk image through --disk-image

3. Windows 11 and Microsoft 365 Deployment Lab Kit
   https://www.microsoft.com/en-us/evalcenter/download-windows-11-office-365-lab-kit

   Truth snapshot:
   - Microsoft publishes this as a separate official lab-kit download in Evaluation Center
   - This is a fallback research lead, not yet a repo-proven cold-start path

Current recommendation on this host:
- If you only have the ISO path, expect the current no-KVM TCG Windows 11 blocker to remain in play
- If Microsoft reopens developer VM downloads, prefer an official VM image over repeating the ISO installer path on this host
EOF
