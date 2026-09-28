from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SRC = REPO_ROOT / 'packages' / 'contracts' / 'src'
INSTALLER_CORE_SRC = REPO_ROOT / 'packages' / 'installer-core' / 'src'
PREVIEW_FILE = 'settings.vibe.preview.json'


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


def run_package_install(*, host: str, target_root: Path, profile: str = "full") -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(CONTRACTS_SRC), str(INSTALLER_CORE_SRC), env.get("PYTHONPATH", "")]).strip(os.pathsep)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vgo_installer.install_runtime",
            "--repo-root",
            str(REPO_ROOT),
            "--target-root",
            str(target_root),
            "--host",
            host,
            "--profile",
            profile,
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return result, json.loads(result.stdout)


class ClaudePreviewScaffoldTests(unittest.TestCase):
    EXPECTED_WRAPPER_SKILLS = ("vibe",)

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.target_root = self.root / 'target'
        self.target_root.mkdir(parents=True, exist_ok=True)
        self.existing_settings = {
            'env': {
                'ANTHROPIC_BASE_URL': 'https://api.example.com/v1',
                'ANTHROPIC_AUTH_TOKEN': 'secret-token',
            },
            'model': 'existing-model',
        }
        (self.target_root / 'settings.json').write_text(
            json.dumps(self.existing_settings, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_shell_scaffold_preserves_existing_settings_and_writes_preview_file(self) -> None:
        cmd = [
            'bash',
            str(REPO_ROOT / 'scripts' / 'bootstrap' / 'scaffold-claude-preview.sh'),
            '--repo-root',
            str(REPO_ROOT),
            '--target-root',
            str(self.target_root),
            '--force',
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout)

        settings_path = self.target_root / 'settings.json'
        preview_path = self.target_root / PREVIEW_FILE
        self.assertEqual(self.existing_settings, json.loads(settings_path.read_text(encoding='utf-8')))
        self.assertFalse(preview_path.exists())
        self.assertIsNone(payload['preview_settings_path'])
        self.assertIsNone(payload['hooks_root'])
        self.assertIn('temporarily frozen', payload['message'])

    def test_powershell_scaffold_preserves_existing_settings_and_writes_preview_file(self) -> None:
        powershell = resolve_powershell()
        if powershell is None:
            self.skipTest('PowerShell executable not available in PATH')
        cmd = [
            powershell,
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            str(REPO_ROOT / 'scripts' / 'bootstrap' / 'scaffold-claude-preview.ps1'),
            '-RepoRoot',
            str(REPO_ROOT),
            '-TargetRoot',
            str(self.target_root),
            '-Force',
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout)

        settings_path = self.target_root / 'settings.json'
        preview_path = self.target_root / PREVIEW_FILE
        self.assertEqual(self.existing_settings, json.loads(settings_path.read_text(encoding='utf-8')))
        self.assertFalse(preview_path.exists())
        self.assertIsNone(payload['preview_settings_path'])
        self.assertIsNone(payload['hooks_root'])
        self.assertIn('temporarily frozen', payload['message'])

    def test_package_installer_preserves_existing_settings_and_writes_preview_file(self) -> None:
        _, payload = run_package_install(host='claude-code', target_root=self.target_root, profile='full')

        settings_path = self.target_root / 'settings.json'
        closure_path = self.target_root / '.vibeskills' / 'host-closure.json'
        host_settings_path = self.target_root / '.vibeskills' / 'host-settings.json'
        bootstrap_receipt_path = Path(str(payload['global_instruction_bootstrap_receipt']))
        settings = json.loads(settings_path.read_text(encoding='utf-8'))
        closure = json.loads(closure_path.read_text(encoding='utf-8'))
        host_settings = json.loads(host_settings_path.read_text(encoding='utf-8'))
        self.assertEqual(self.existing_settings['env'], settings['env'])
        self.assertEqual(self.existing_settings['model'], settings['model'])
        self.assertEqual('claude-code', settings['vibeskills']['host_id'])
        self.assertTrue(settings['vibeskills']['managed'])
        self.assertEqual(str(self.target_root.resolve()), settings['vibeskills']['runtime_root'])
        self.assertEqual(str(self.target_root.resolve()), settings['vibeskills']['host_bridge_root'])
        self.assertEqual(payload['desired_shared_runtime_root'], settings['vibeskills']['desired_shared_runtime_root'])
        self.assertEqual('legacy-host-root-override', settings['vibeskills']['runtime_layout_mode'])
        self.assertEqual(str((self.target_root / 'skills').resolve()), settings['vibeskills']['skills_root'])
        self.assertTrue(closure_path.exists())
        self.assertTrue(host_settings_path.exists())
        self.assertTrue(bootstrap_receipt_path.exists())
        self.assertEqual(str(self.target_root.resolve()), closure['runtime_root'])
        self.assertEqual(str(self.target_root.resolve()), closure['host_bridge_root'])
        self.assertEqual(payload['desired_shared_runtime_root'], closure['desired_shared_runtime_root'])
        self.assertEqual('legacy-host-root-override', closure['runtime_layout_mode'])
        self.assertEqual(str(self.target_root.resolve()), host_settings['runtime_root'])
        self.assertEqual(str(self.target_root.resolve()), host_settings['host_bridge_root'])
        self.assertEqual(payload['desired_shared_runtime_root'], host_settings['desired_shared_runtime_root'])
        self.assertEqual('legacy-host-root-override', host_settings['runtime_layout_mode'])
        self.assertEqual(str(self.target_root.resolve()), payload['runtime_root'])
        self.assertEqual(str(self.target_root.resolve()), payload['host_bridge_root'])
        self.assertNotEqual(str(self.target_root.resolve()), payload['desired_shared_runtime_root'])
        self.assertEqual('legacy-host-root-override', payload['runtime_layout_mode'])
        for name in self.EXPECTED_WRAPPER_SKILLS:
            self.assertTrue((self.target_root / 'skills' / name / 'SKILL.md').exists())
        self.assertFalse((self.target_root / 'commands').exists())
        self.assertEqual('preview-guidance', payload['install_mode'])
        self.assertEqual(str(closure_path), payload['host_closure_path'])

    def test_shell_install_rejects_legacy_claude_host_root_options_without_touching_real_settings(self) -> None:
        install_cmd = [
            'bash',
            str(REPO_ROOT / 'install.sh'),
            '--host',
            'claude-code',
            '--target-root',
            str(self.target_root),
            '--profile',
            'full',
        ]
        result = subprocess.run(install_cmd, capture_output=True, text=True)

        self.assertNotEqual(0, result.returncode)
        self.assertIn('unrecognized arguments', result.stderr)
        self.assertIn('--host claude-code', result.stderr)
        self.assertIn('--target-root', result.stderr)
        settings = json.loads((self.target_root / 'settings.json').read_text(encoding='utf-8'))
        self.assertEqual(self.existing_settings['env'], settings['env'])
        self.assertEqual(self.existing_settings['model'], settings['model'])

    def test_powershell_install_rejects_legacy_claude_host_root_options_without_touching_real_settings(self) -> None:
        powershell = resolve_powershell()
        if powershell is None:
            self.skipTest('PowerShell executable not available in PATH')

        install_cmd = [
            powershell,
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            str(REPO_ROOT / 'install.ps1'),
            '-HostId',
            'claude-code',
            '-TargetRoot',
            str(self.target_root),
            '-Profile',
            'full',
        ]
        result = subprocess.run(install_cmd, capture_output=True, text=True)

        self.assertNotEqual(0, result.returncode)
        self.assertIn('parameter', result.stderr.lower())
        self.assertIn('HostId', result.stderr)
        settings = json.loads((self.target_root / 'settings.json').read_text(encoding='utf-8'))
        self.assertEqual(self.existing_settings['env'], settings['env'])
        self.assertEqual(self.existing_settings['model'], settings['model'])


if __name__ == '__main__':
    unittest.main()
