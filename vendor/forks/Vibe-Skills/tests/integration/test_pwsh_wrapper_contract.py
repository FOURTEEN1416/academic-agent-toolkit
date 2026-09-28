from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_powershell_wrappers_delegate_to_matching_vgo_cli_commands() -> None:
    for script_name, command_name in {
        "install.ps1": "install",
        "check.ps1": "check",
        "update.ps1": "update",
        "uninstall.ps1": "uninstall",
    }.items():
        content = (REPO_ROOT / script_name).read_text(encoding="utf-8")

        assert "[CmdletBinding()]" in content
        assert "[string]$SkillsDir" in content
        assert "vgo_cli.main" in content
        assert f"'{command_name}'" in content
        assert "--skills-dir" in content


def test_powershell_wrappers_do_not_call_legacy_adapter_scripts() -> None:
    combined = "\n".join(
        (REPO_ROOT / script_name).read_text(encoding="utf-8")
        for script_name in ("install.ps1", "check.ps1", "update.ps1", "uninstall.ps1")
    )

    assert "scripts\\install\\Install-VgoAdapter.ps1" not in combined
    assert "scripts\\check\\Check-VgoAdapter.ps1" not in combined
    assert "scripts\\uninstall\\Uninstall-VgoAdapter.ps1" not in combined


def test_powershell_wrappers_define_explicit_help_path() -> None:
    for script_name in ("install.ps1", "check.ps1", "update.ps1", "uninstall.ps1"):
        content = (REPO_ROOT / script_name).read_text(encoding="utf-8")

        assert "[Alias('?')]" in content
        assert "Show-WrapperUsage" in content
        assert "if ($Help)" in content
