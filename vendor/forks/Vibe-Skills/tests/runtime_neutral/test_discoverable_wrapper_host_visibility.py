from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RETIRED_DISCOVERABLE_ENTRIES = ("vibe-what-do-i-want", "vibe-how-do-we-do", "vibe-do-it")


def _install_skills_dir(skills_dir: Path) -> None:
    command = [
        "bash",
        str(REPO_ROOT / "install.sh"),
        "--skills-dir",
        str(skills_dir),
    ]
    subprocess.run(command, capture_output=True, text=True, check=True)


class DiscoverableWrapperHostVisibilityTests(unittest.TestCase):
    def _require_bash(self) -> None:
        if shutil.which("bash") is None:
            self.skipTest("bash not available")

    def test_install_receipt_exposes_only_the_vibe_skill_install(self) -> None:
        self._require_bash()
        with tempfile.TemporaryDirectory() as tempdir:
            skills_dir = Path(tempdir) / "skills"
            _install_skills_dir(skills_dir)

            receipt_path = skills_dir / "vibe" / ".vibeskills" / "install-receipt.json"
            self.assertTrue(receipt_path.exists())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

            self.assertEqual("vibe-skill-install", receipt["receipt_kind"])
            self.assertEqual("vibe", receipt["skill_id"])
            self.assertEqual(str((skills_dir / "vibe").resolve()), receipt["install_root"])
            self.assertFalse((skills_dir / "vibe-upgrade" / "SKILL.md").exists())
            self.assertFalse((skills_dir / "commands" / "vibe-upgrade.md").exists())

    def test_shell_check_accepts_simplified_skills_dir_install(self) -> None:
        self._require_bash()
        with tempfile.TemporaryDirectory() as tempdir:
            skills_dir = Path(tempdir) / "skills"
            _install_skills_dir(skills_dir)

            result = subprocess.run(
                [
                    "bash",
                    str(REPO_ROOT / "check.sh"),
                    "--skills-dir",
                    str(skills_dir),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertNotIn("specialist wrapper launcher", result.stdout)

    def test_install_prunes_retired_discoverable_wrapper_files_from_host_surfaces(self) -> None:
        self._require_bash()
        with tempfile.TemporaryDirectory() as tempdir:
            skills_dir = Path(tempdir) / "skills"
            _install_skills_dir(skills_dir)

            for entry_id in RETIRED_DISCOVERABLE_ENTRIES:
                self.assertFalse((skills_dir / "vibe" / "commands" / f"{entry_id}.md").exists(), entry_id)
                self.assertFalse((skills_dir / "vibe" / "command" / f"{entry_id}.md").exists(), entry_id)
                self.assertFalse((skills_dir / entry_id).exists(), entry_id)


if __name__ == "__main__":
    unittest.main()
