from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def count_files(root: Path) -> int:
    return sum(1 for candidate in root.rglob("*") if candidate.is_file())


class InstallProfileDifferentiationTests(unittest.TestCase):
    def install_to(self, skills_dir: Path) -> dict[str, object]:
        result = subprocess.run(
            [
                "bash",
                str(REPO_ROOT / "install.sh"),
                "--skills-dir",
                str(skills_dir),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertIsInstance(payload, dict)
        return payload

    def test_shell_install_writes_single_vibe_package_under_skills_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            skills_dir = Path(tempdir) / "skills"

            receipt = self.install_to(skills_dir)

            install_root = skills_dir / "vibe"
            self.assertEqual("vibe-skill-install", receipt["receipt_kind"])
            self.assertEqual("vibe", receipt["skill_id"])
            self.assertEqual(str(skills_dir.resolve()), receipt["skills_dir"])
            self.assertEqual(str(install_root.resolve()), receipt["install_root"])
            self.assertTrue((install_root / "SKILL.md").is_file())
            self.assertTrue((install_root / "config" / "version-governance.json").is_file())
            self.assertTrue((install_root / ".vibeskills" / "install-receipt.json").is_file())
            self.assertFalse((skills_dir / "vibe-upgrade").exists())
            self.assertFalse((install_root / "bundled" / "skills").exists())
            self.assertFalse((skills_dir.parent / ".vibeskills" / "install-ledger.json").exists())
            self.assertEqual(count_files(install_root) - 1, len(receipt["files"]))

    def test_shell_install_rejects_legacy_profile_options(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            result = subprocess.run(
                [
                    "bash",
                    str(REPO_ROOT / "install.sh"),
                    "--profile",
                    "minimal",
                    "--target-root",
                    str(Path(tempdir) / "target"),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("unrecognized arguments", result.stderr)

    def test_shell_install_preserves_foreign_host_content(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            skills_dir = Path(tempdir) / "skills"
            foreign_skill = skills_dir / "foreign-user-skill" / "SKILL.md"
            foreign_note = skills_dir.parent / "host-notes.txt"
            foreign_skill.parent.mkdir(parents=True, exist_ok=True)
            foreign_skill.write_text("---\nname: foreign-user-skill\ndescription: user skill\n---\n", encoding="utf-8")
            foreign_note.write_text("user content\n", encoding="utf-8")

            receipt = self.install_to(skills_dir)

            self.assertTrue(foreign_skill.is_file())
            self.assertTrue(foreign_note.is_file())
            self.assertFalse((skills_dir / "vibe" / "bundled" / "skills" / "foreign-user-skill").exists())
            self.assertNotIn("foreign-user-skill", {entry["path"] for entry in receipt["files"]})


if __name__ == "__main__":
    unittest.main()
