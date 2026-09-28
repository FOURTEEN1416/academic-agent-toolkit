from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_bootstrap_entrypoints_are_retired_legacy_install_surface() -> None:
    shell_content = (REPO_ROOT / 'scripts' / 'bootstrap' / 'one-shot-setup.sh').read_text(encoding='utf-8')
    powershell_content = (REPO_ROOT / 'scripts' / 'bootstrap' / 'one-shot-setup.ps1').read_text(encoding='utf-8')

    assert 'retired' in shell_content.lower()
    assert 'retired' in powershell_content.lower()
    assert '--skills-dir' in shell_content
    assert '--skills-dir' in powershell_content
    assert 'adapter_registry_query.py' not in shell_content
    assert 'Get-VgoBootstrapHostChoices' not in powershell_content
