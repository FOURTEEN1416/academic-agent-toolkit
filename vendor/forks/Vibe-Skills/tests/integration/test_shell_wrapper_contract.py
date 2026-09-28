from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_shell_wrappers_delegate_to_matching_vgo_cli_commands() -> None:
    for script_name, command_name in {
        "install.sh": "install",
        "check.sh": "check",
        "update.sh": "update",
        "uninstall.sh": "uninstall",
    }.items():
        content = (REPO_ROOT / script_name).read_text(encoding="utf-8")

        assert "vgo_cli.main" in content
        assert f"vgo_cli.main {command_name}" in content
        assert "scripts/install/install_vgo_adapter.py" not in content
        assert "scripts/uninstall/uninstall_vgo_adapter.py" not in content
