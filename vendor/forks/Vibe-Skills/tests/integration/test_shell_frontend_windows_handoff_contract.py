from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_bootstrap_shell_no_longer_hands_off_to_legacy_powershell_one_shot() -> None:
    bootstrap_shell = (REPO_ROOT / "scripts" / "bootstrap" / "one-shot-setup.sh").read_text(encoding="utf-8")

    assert "retired" in bootstrap_shell.lower()
    assert "Windows shell frontend detected; switching to PowerShell-first supported path." not in bootstrap_shell
    assert "handoff_to_windows_powershell_frontend" not in bootstrap_shell


def test_check_shell_uses_portable_simple_cli_wrapper() -> None:
    check_shell = (REPO_ROOT / "check.sh").read_text(encoding="utf-8")

    assert "vgo_cli.main check" in check_shell
    assert "Windows shell frontend detected; switching to PowerShell-first supported path." not in check_shell
    assert "handoff_to_windows_powershell_frontend" not in check_shell
