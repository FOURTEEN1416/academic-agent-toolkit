from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install" / "install_vgo_adapter.py"
RESOLVER = REPO_ROOT / "scripts" / "common" / "resolve_vgo_adapter.py"


class OpenCodePreviewParityTests(unittest.TestCase):
    def test_adapter_registry_exposes_real_host_root_default_for_opencode(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(RESOLVER),
                "--repo-root",
                str(REPO_ROOT),
                "--host",
                "opencode",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual("opencode", payload["id"])
        self.assertEqual(".agents", payload["default_target_root"]["rel"])
        self.assertEqual("shared-home", payload["default_target_root"]["kind"])

    def test_python_installer_materializes_opencode_preview_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            target_root = Path(tempdir)
            result = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--repo-root",
                    str(REPO_ROOT),
                    "--target-root",
                    str(target_root),
                    "--host",
                    "opencode",
                    "--profile",
                    "full",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)

            self.assertEqual("opencode", payload["host_id"])
            self.assertEqual("preview-guidance", payload["install_mode"])
            self.assertTrue((target_root / "commands" / "vibe.md").exists())
            self.assertTrue((target_root / "command" / "vibe.md").exists())
            self.assertTrue((target_root / "agents" / "vibe-plan.md").exists())
            self.assertTrue((target_root / "agent" / "vibe-plan.md").exists())
            self.assertTrue((target_root / "opencode.json.example").exists())
            self.assertFalse((target_root / "opencode.json").exists())

    def test_powershell_install_and_check_use_skills_dir_without_opencode_wrappers(self) -> None:
        if shutil.which("pwsh") is None:
            self.skipTest("pwsh not available")

        with tempfile.TemporaryDirectory() as tempdir:
            target_root = Path(tempdir)
            skills_dir = target_root / "skills"

            install_result = subprocess.run(
                [
                    "pwsh",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(REPO_ROOT / "install.ps1"),
                    "-SkillsDir",
                    str(skills_dir),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            install_payload = json.loads(install_result.stdout)
            self.assertEqual("vibe-skill-install", install_payload["receipt_kind"])

            check_result = subprocess.run(
                [
                    "pwsh",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(REPO_ROOT / "check.ps1"),
                    "-SkillsDir",
                    str(skills_dir),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            check_payload = json.loads(check_result.stdout)
            self.assertTrue(check_payload["ok"])
            self.assertTrue((skills_dir / "vibe" / "SKILL.md").exists())
            self.assertFalse((target_root / "commands").exists())
            self.assertFalse((target_root / "command").exists())
            self.assertFalse((target_root / "agents").exists())
            self.assertFalse((target_root / "agent").exists())
            self.assertFalse((target_root / "opencode.json.example").exists())


if __name__ == "__main__":
    unittest.main()
