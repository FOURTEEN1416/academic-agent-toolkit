from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_powershell_wrappers_only_expose_skills_dir_install_contract() -> None:
    for script_name in ("install.ps1", "check.ps1", "update.ps1", "uninstall.ps1"):
        content = (REPO_ROOT / script_name).read_text(encoding="utf-8")

        assert "[string]$SkillsDir" in content
        assert "$HostId" not in content
        assert "$Profile" not in content
        assert "$TargetRoot" not in content
        assert "Resolve-VgoHostId" not in content


def test_powershell_wrappers_reject_old_host_arguments() -> None:
    for script_name in ("install.ps1", "check.ps1", "update.ps1", "uninstall.ps1"):
        result = subprocess.run(
            [
                "pwsh",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                f"./{script_name}",
                "-HostId",
                "codex",
                "-Profile",
                "minimal",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "HostId" in (result.stdout + result.stderr)
