from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"
CHECK_SCRIPT = REPO_ROOT / "check.sh"
UNINSTALL_SCRIPT = REPO_ROOT / "uninstall.sh"


def _shell_path(path: Path) -> str:
    return str(path).replace("\\", "/")


class HostGlobalBootstrapShellLifecycleTests(unittest.TestCase):
    def _run_shell(self, script: Path, skills_dir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(script), "--skills-dir", _shell_path(skills_dir)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

    def test_shell_lifecycle_keeps_user_instruction_and_settings_files_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            host_root = Path(tempdir)
            skills_dir = host_root / "skills"
            user_files = {
                "AGENTS.md": "# Personal agent rules\n\n- keep this line\n",
                "CLAUDE.md": "# Personal Claude rules\n\n- keep this line\n",
                "settings.json": json.dumps({"env": {"ANTHROPIC_API_KEY": "secret"}}, indent=2) + "\n",
                "opencode.json": json.dumps({"provider": {"default": "openai"}}, indent=2) + "\n",
            }

            for relative_path, content in user_files.items():
                path = host_root / relative_path
                path.write_text(content, encoding="utf-8")

            self._run_shell(INSTALL_SCRIPT, skills_dir)
            self.assertTrue((skills_dir / "vibe" / ".vibeskills" / "install-receipt.json").is_file())

            check = self._run_shell(CHECK_SCRIPT, skills_dir)
            self.assertIn('"ok": true', check.stdout)

            self._run_shell(INSTALL_SCRIPT, skills_dir)
            self._run_shell(UNINSTALL_SCRIPT, skills_dir)
            self.assertFalse((skills_dir / "vibe").exists())

            for relative_path, content in user_files.items():
                self.assertEqual(content, (host_root / relative_path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
