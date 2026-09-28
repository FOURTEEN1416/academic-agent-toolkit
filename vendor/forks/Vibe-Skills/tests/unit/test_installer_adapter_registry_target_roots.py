from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_CORE_SRC = REPO_ROOT / 'packages' / 'installer-core' / 'src'
CONTRACTS_SRC = REPO_ROOT / 'packages' / 'contracts' / 'src'
for src in (INSTALLER_CORE_SRC, CONTRACTS_SRC):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

import vgo_installer.adapter_registry as adapter_registry_module
from vgo_installer.adapter_registry import (
    resolve_canonical_vibe_contract,
    resolve_default_target_root,
    resolve_default_target_root_text,
    resolve_matching_target_root_hosts,
    resolve_target_root_owner,
    resolve_target_root_spec,
)


def test_resolve_target_root_spec_projects_registry_target_root_semantics() -> None:
    normalized, spec = resolve_target_root_spec(REPO_ROOT, 'windsurf')

    assert normalized == 'windsurf'
    assert spec['env'] == 'VIBE_AGENTS_HOME'
    assert spec['rel'] == '.agents'
    assert spec['kind'] == 'shared-home'
    assert spec['install_mode'] == 'runtime-core'


def test_resolve_target_root_spec_projects_codex_to_real_host_root() -> None:
    normalized, spec = resolve_target_root_spec(REPO_ROOT, 'codex')

    assert normalized == 'codex'
    assert spec['env'] == 'VIBE_AGENTS_HOME'
    assert spec['rel'] == '.agents'
    assert spec['kind'] == 'shared-home'
    assert spec['install_mode'] == 'governed'


def test_resolve_target_root_spec_projects_claude_code_to_real_host_root() -> None:
    normalized, spec = resolve_target_root_spec(REPO_ROOT, 'claude-code')

    assert normalized == 'claude-code'
    assert spec['env'] == 'VIBE_AGENTS_HOME'
    assert spec['rel'] == '.agents'
    assert spec['kind'] == 'shared-home'
    assert spec['install_mode'] == 'preview-guidance'


def test_resolve_target_root_spec_projects_cursor_to_real_host_root() -> None:
    normalized, spec = resolve_target_root_spec(REPO_ROOT, 'cursor')

    assert normalized == 'cursor'
    assert spec['env'] == 'VIBE_AGENTS_HOME'
    assert spec['rel'] == '.agents'
    assert spec['kind'] == 'shared-home'
    assert spec['install_mode'] == 'preview-guidance'


def test_resolve_target_root_spec_projects_openclaw_to_real_host_root() -> None:
    normalized, spec = resolve_target_root_spec(REPO_ROOT, 'openclaw')

    assert normalized == 'openclaw'
    assert spec['env'] == 'VIBE_AGENTS_HOME'
    assert spec['rel'] == '.agents'
    assert spec['kind'] == 'shared-home'
    assert spec['install_mode'] == 'runtime-core'


def test_resolve_target_root_spec_projects_opencode_to_real_host_root() -> None:
    normalized, spec = resolve_target_root_spec(REPO_ROOT, 'opencode')

    assert normalized == 'opencode'
    assert spec['env'] == 'VIBE_AGENTS_HOME'
    assert spec['rel'] == '.agents'
    assert spec['kind'] == 'shared-home'
    assert spec['install_mode'] == 'preview-guidance'


def test_resolve_canonical_vibe_contract_projects_supported_hosts() -> None:
    codex = resolve_canonical_vibe_contract(REPO_ROOT, 'codex')
    claude = resolve_canonical_vibe_contract(REPO_ROOT, 'claude-code')
    opencode = resolve_canonical_vibe_contract(REPO_ROOT, 'opencode')

    assert codex['entry_mode'] == 'direct_runtime'
    assert codex['launcher_kind'] == 'native_command'
    assert codex['fallback_policy'] == 'blocked'
    assert codex['allow_skill_doc_fallback'] is False
    assert codex['proof_required'] is True
    assert codex['supports_bounded_stop'] is True
    assert claude['entry_mode'] == 'bridged_runtime'
    assert claude['launcher_kind'] == 'managed_bridge'
    assert opencode['entry_mode'] == 'bridged_runtime'
    assert opencode['launcher_kind'] == 'managed_bridge'


def test_resolve_canonical_vibe_contract_preserves_host_defaults_when_adapter_overrides_are_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        adapter_registry_module,
        "resolve_host_canonical_vibe_contract",
        lambda repo_root, host_id: {
            "host_id": "codex",
            "entry_mode": "direct_runtime",
            "launcher_kind": "native_command",
            "fallback_policy": "blocked",
            "allow_skill_doc_fallback": False,
            "proof_required": True,
            "supports_bounded_stop": True,
            "bootstrap_mode": "managed_bootstrap",
            "discoverable_entries": {"vibe": {"requested_stage_stop": "phase_cleanup"}},
        },
    )
    monkeypatch.setattr(
        adapter_registry_module,
        "resolve_adapter",
        lambda repo_root, host_id: {
            "id": "codex",
            "bootstrap_mode": "",
            "discoverable_entries": {},
        },
    )

    contract = resolve_canonical_vibe_contract(REPO_ROOT, "codex")

    assert contract["bootstrap_mode"] == "managed_bootstrap"
    assert contract["discoverable_entries"] == {"vibe": {"requested_stage_stop": "phase_cleanup"}}


def test_resolve_default_target_root_text_preserves_env_projection() -> None:
    resolved = resolve_default_target_root_text(
        REPO_ROOT,
        'windsurf',
        env={'VIBE_AGENTS_HOME': '/tmp/agents-home'},
        home='/home/tester',
    )

    assert resolved == '/tmp/agents-home'


def test_resolve_default_target_root_text_honors_explicit_empty_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('VIBE_AGENTS_HOME', '/tmp/process-agents-home')

    resolved = resolve_default_target_root_text(
        REPO_ROOT,
        'windsurf',
        env={},
        home='/home/tester',
    )

    assert resolved == '/home/tester/.agents'


def test_resolve_default_target_root_text_preserves_posix_home_projection() -> None:
    resolved = resolve_default_target_root_text(
        REPO_ROOT,
        'opencode',
        env={},
        home='/home/tester',
    )

    assert resolved == '/home/tester/.agents'


def test_resolve_default_target_root_uses_env_projection() -> None:
    resolved = resolve_default_target_root(
        REPO_ROOT,
        'windsurf',
        env={'VIBE_AGENTS_HOME': '/tmp/agents-home'},
        home='/home/tester',
    )

    assert resolved == Path('/tmp/agents-home').resolve()


def test_resolve_default_target_root_defaults_codex_to_real_home_root() -> None:
    resolved = resolve_default_target_root(
        REPO_ROOT,
        'codex',
        env={},
        home='/home/tester',
    )

    assert resolved == Path('/home/tester/.agents').resolve()


def test_resolve_default_target_root_defaults_claude_code_to_real_home_root() -> None:
    resolved = resolve_default_target_root(
        REPO_ROOT,
        'claude-code',
        env={},
        home='/home/tester',
    )

    assert resolved == Path('/home/tester/.agents').resolve()


def test_resolve_default_target_root_defaults_cursor_to_real_home_root() -> None:
    resolved = resolve_default_target_root(
        REPO_ROOT,
        'cursor',
        env={},
        home='/home/tester',
    )

    assert resolved == Path('/home/tester/.agents').resolve()


def test_resolve_default_target_root_defaults_windsurf_to_real_home_root() -> None:
    resolved = resolve_default_target_root(
        REPO_ROOT,
        'windsurf',
        env={},
        home='/home/tester',
    )

    assert resolved == Path('/home/tester/.agents').resolve()


def test_resolve_default_target_root_defaults_openclaw_to_real_home_root() -> None:
    resolved = resolve_default_target_root(
        REPO_ROOT,
        'openclaw',
        env={},
        home='/home/tester',
    )

    assert resolved == Path('/home/tester/.agents').resolve()


def test_resolve_default_target_root_defaults_opencode_to_real_home_root() -> None:
    resolved = resolve_default_target_root(
        REPO_ROOT,
        'opencode',
        env={},
        home='/home/tester',
    )

    assert resolved == Path('/home/tester/.agents').resolve()


def test_resolve_matching_target_root_hosts_preserves_opencode_compatibility_signature(tmp_path: Path) -> None:
    matches = resolve_matching_target_root_hosts(REPO_ROOT, str(tmp_path / '.opencode'))

    assert matches == ['opencode']


def test_resolve_target_root_owner_recognizes_cursor_home_signature(tmp_path: Path) -> None:
    owner = resolve_target_root_owner(REPO_ROOT, str(tmp_path / '.cursor'))

    assert owner == 'cursor'
