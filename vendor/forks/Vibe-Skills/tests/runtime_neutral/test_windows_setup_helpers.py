from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class WindowsSetupHelpersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_send_qmp_text_rejects_unsupported_character_cleanly(self) -> None:
        script = REPO_ROOT / "scripts" / "setup" / "send-qmp-text.py"
        completed = subprocess.run(
            [sys.executable, str(script), str(self.root / "missing.sock"), "A"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(2, completed.returncode)
        self.assertIn("unsupported character", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_send_qmp_boot_keys_rejects_negative_rounds(self) -> None:
        script = REPO_ROOT / "scripts" / "setup" / "send-qmp-boot-keys.py"
        completed = subprocess.run(
            [sys.executable, str(script), str(self.root / "missing.sock"), "esc", "-1", "50"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(2, completed.returncode)
        self.assertIn("rounds must be >= 0", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_check_windows_proof_vm_state_reports_invalid_pidfile(self) -> None:
        script = REPO_ROOT / "scripts" / "setup" / "check-windows-proof-vm-state.sh"
        vm_root = self.root / "vm-state"
        vm_root.mkdir(parents=True, exist_ok=True)
        (vm_root / "qemu.pid").write_text("abc\n", encoding="utf-8")

        completed = subprocess.run(
            ["bash", str(script), "--vm-root", str(vm_root)],
            capture_output=True,
            text=True,
        )

        self.assertEqual(2, completed.returncode)
        self.assertIn("status=invalid-pidfile", completed.stdout)

    def test_stop_windows_proof_vm_handles_empty_pidfiles(self) -> None:
        script = REPO_ROOT / "scripts" / "setup" / "stop-windows-proof-vm.sh"
        vm_root = self.root / "vm-stop"
        vm_root.mkdir(parents=True, exist_ok=True)
        (vm_root / "qemu.pid").write_text("\n", encoding="utf-8")
        (vm_root / "swtpm.pid").write_text("", encoding="utf-8")

        completed = subprocess.run(
            ["bash", str(script), "--vm-root", str(vm_root)],
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertIn("QEMU pidfile is empty or invalid", completed.stdout)
        self.assertIn("swtpm pidfile is empty or invalid", completed.stdout)
        self.assertFalse((vm_root / "qemu.pid").exists())
        self.assertFalse((vm_root / "swtpm.pid").exists())

    def test_fetch_windows11_eval_iso_rejects_directory_output_path_before_network(self) -> None:
        script = REPO_ROOT / "scripts" / "setup" / "fetch-windows11-eval-iso.sh"
        output_dir = f"{self.root / 'downloads'}/"
        completed = subprocess.run(
            ["bash", str(script), "--output", output_dir],
            capture_output=True,
            text=True,
        )

        self.assertEqual(1, completed.returncode)
        self.assertIn("--output must be a file path", completed.stderr)

    def test_show_windows_proof_media_options_prints_lab_kit_url(self) -> None:
        script = REPO_ROOT / "scripts" / "setup" / "show-windows-proof-media-options.sh"
        completed = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertIn(
            "https://www.microsoft.com/en-us/evalcenter/download-windows-11-office-365-lab-kit",
            completed.stdout,
        )


if __name__ == "__main__":
    unittest.main()
