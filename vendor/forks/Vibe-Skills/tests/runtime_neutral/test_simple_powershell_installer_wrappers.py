from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def _run_pwsh(script_name: str, skills_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / script_name),
            "-SkillsDir",
            str(skills_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_powershell_wrappers_use_the_simplified_skills_dir_contract(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"

    install = _run_pwsh("install.ps1", skills_dir)
    assert install.returncode == 0, install.stderr + install.stdout
    assert (skills_dir / "vibe" / ".vibeskills" / "install-receipt.json").is_file()

    check = _run_pwsh("check.ps1", skills_dir)
    assert check.returncode == 0, check.stderr + check.stdout
    assert '"ok": true' in check.stdout

    update = _run_pwsh("update.ps1", skills_dir)
    assert update.returncode == 0, update.stderr + update.stdout

    uninstall = _run_pwsh("uninstall.ps1", skills_dir)
    assert uninstall.returncode == 0, uninstall.stderr + uninstall.stdout
    assert not (skills_dir / "vibe").exists()
