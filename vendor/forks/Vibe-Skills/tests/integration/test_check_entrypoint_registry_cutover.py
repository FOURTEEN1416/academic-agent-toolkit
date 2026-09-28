from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_check_entrypoints_use_simplified_skills_dir_contract() -> None:
    shell_content = (REPO_ROOT / 'check.sh').read_text(encoding='utf-8')
    powershell_content = (REPO_ROOT / 'check.ps1').read_text(encoding='utf-8')

    assert 'vgo_cli.main check' in shell_content
    assert '--skills-dir' in powershell_content
    assert '-SkillsDir' in powershell_content
    assert 'scripts/common/adapter_registry_query.py' not in shell_content
    assert 'Resolve-VgoAdapterEntry' not in powershell_content
    assert r'config\adapter-registry.json' not in powershell_content
    assert r'adapters\index.json' not in powershell_content


def test_check_powershell_avoids_array_index_probe_for_optional_nested_bundled_target() -> None:
    powershell_content = (REPO_ROOT / 'check.ps1').read_text(encoding='utf-8')

    assert "@($topology.targets | Where-Object { [string]$_.id -eq 'nested_bundled' } | Select-Object -First 1)[0]" not in powershell_content



def test_check_shell_guard_does_not_probe_host_roots() -> None:
    shell_content = (REPO_ROOT / 'check.sh').read_text(encoding='utf-8')

    assert 'target_root_owner_for_path()' not in shell_content
    assert "looks like a non-Codex host root" not in shell_content
    assert 'is_cursor_root=' not in shell_content
