from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.bash_test_support import capture_text_kwargs, to_bash_path


REPO_ROOT = Path(__file__).resolve().parents[2]


class CheckShellTargetRootGuardTests(unittest.TestCase):
    def test_check_sh_rejects_cursor_root_for_codex(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            target_root = Path(tempdir) / '.cursor'
            result = subprocess.run(
                [
                    'bash',
                    to_bash_path(REPO_ROOT / 'check.sh'),
                    '--host', 'codex',
                    '--profile', 'minimal',
                    '--skip-runtime-freshness-gate',
                    '--target-root', to_bash_path(target_root),
                ],
                cwd=REPO_ROOT,
                **capture_text_kwargs(),
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn('unrecognized arguments', result.stderr)
        self.assertIn('--host codex', result.stderr)
        self.assertIn('--target-root', result.stderr)

    def test_check_sh_rejects_opencode_repo_local_root_for_codex(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            target_root = Path(tempdir) / '.opencode'
            result = subprocess.run(
                [
                    'bash',
                    to_bash_path(REPO_ROOT / 'check.sh'),
                    '--host', 'codex',
                    '--profile', 'minimal',
                    '--skip-runtime-freshness-gate',
                    '--target-root', to_bash_path(target_root),
                ],
                cwd=REPO_ROOT,
                **capture_text_kwargs(),
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn('unrecognized arguments', result.stderr)
        self.assertIn('--host codex', result.stderr)
        self.assertIn('--target-root', result.stderr)


if __name__ == '__main__':
    unittest.main()
