from __future__ import annotations

from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_check(skills_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_check_ps1_reports_missing_receipt_for_empty_skills_dir(tmp_path: Path) -> None:
    result = _run_check(tmp_path / "skills")

    assert result.returncode == 1
    assert "missing_receipt" in result.stdout


def test_check_ps1_accepts_simplified_installed_vibe_root(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    install = subprocess.run(
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
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr + install.stdout

    result = _run_check(skills_dir)

    assert result.returncode == 0, result.stderr + result.stdout
    assert '"ok": true' in result.stdout
