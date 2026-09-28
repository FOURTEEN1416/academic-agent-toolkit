from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.bash_test_support import capture_text_kwargs, to_bash_path


REPO_ROOT = Path(__file__).resolve().parents[2]


class BootstrapShellTargetRootGuardTests(unittest.TestCase):
    def test_bootstrap_sh_refuses_legacy_one_shot_install_path(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            target_root = Path(tempdir) / '.cursor'
            result = subprocess.run(
                [
                    'bash',
                    to_bash_path(REPO_ROOT / 'scripts' / 'bootstrap' / 'one-shot-setup.sh'),
                    '--host', 'codex',
                    '--profile', 'minimal',
                    '--skip-external-install',
                    '--target-root', to_bash_path(target_root),
                ],
                cwd=REPO_ROOT,
                **capture_text_kwargs(),
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn('retired', result.stderr)
        self.assertIn('--skills-dir', result.stderr)


if __name__ == '__main__':
    unittest.main()
