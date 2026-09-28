from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_powershell() -> str | None:
    candidates = [
        shutil.which("pwsh"),
        shutil.which("pwsh.exe"),
        r"C:\Program Files\PowerShell\7\pwsh.exe",
        r"C:\Program Files\PowerShell\7-preview\pwsh.exe",
        shutil.which("powershell"),
        shutil.which("powershell.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


class PowerShellEntrypointHelpTests(unittest.TestCase):
    def test_install_help_exits_without_mutating_target_root(self) -> None:
        powershell = resolve_powershell()
        if powershell is None:
            self.skipTest("PowerShell executable not available in PATH")

        with tempfile.TemporaryDirectory() as tempdir:
            skills_dir = Path(tempdir) / "install-help-skills"
            result = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(REPO_ROOT / "install.ps1"),
                    "-?",
                    "-SkillsDir",
                    str(skills_dir),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode)
            self.assertIn("install.ps1", result.stdout)
            self.assertIn("SkillsDir", result.stdout)
            self.assertNotIn("TargetRoot", result.stdout)
            self.assertNotIn("Installation complete.", result.stdout)
            self.assertFalse(skills_dir.exists())

    def test_check_help_exits_without_running_health_check(self) -> None:
        powershell = resolve_powershell()
        if powershell is None:
            self.skipTest("PowerShell executable not available in PATH")

        with tempfile.TemporaryDirectory() as tempdir:
            skills_dir = Path(tempdir) / "check-help-skills"
            result = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(REPO_ROOT / "check.ps1"),
                    "-?",
                    "-SkillsDir",
                    str(skills_dir),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode)
            self.assertIn("check.ps1", result.stdout)
            self.assertIn("SkillsDir", result.stdout)
            self.assertNotIn("TargetRoot", result.stdout)
            self.assertNotIn("=== VCO Adapter Health Check ===", result.stdout)
            self.assertFalse(skills_dir.exists())


if __name__ == "__main__":
    unittest.main()
