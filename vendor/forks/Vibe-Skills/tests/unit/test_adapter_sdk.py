from pathlib import Path
import json
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
ADAPTER_SDK_SRC = ROOT / 'packages' / 'adapter-sdk' / 'src'
CONTRACTS_SRC = ROOT / 'packages' / 'contracts' / 'src'
for src in (ADAPTER_SDK_SRC, CONTRACTS_SRC):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

from vgo_adapters.descriptor_loader import load_descriptor
from vgo_adapters.target_root_resolver import resolve_default_target_root


REGISTRY = json.loads((ROOT / 'config' / 'adapter-registry.json').read_text(encoding='utf-8'))


def test_adapter_sdk_descriptors_match_registry_default_target_roots() -> None:
    for adapter in REGISTRY['adapters']:
        descriptor = load_descriptor(adapter['id'])
        assert descriptor.id == adapter['id']
        assert descriptor.default_target_root == adapter['default_target_root']['rel']
        assert descriptor.default_target_root_env == adapter['default_target_root']['env']
        assert descriptor.default_target_root_kind == adapter['default_target_root']['kind']


def test_descriptor_loader_supports_registry_aliases() -> None:
    descriptor = load_descriptor('claude')
    assert descriptor.id == 'claude-code'
    assert descriptor.default_target_root == '.agents'
    assert descriptor.default_target_root_env == 'VIBE_AGENTS_HOME'
    assert descriptor.default_target_root_kind == 'shared-home'


def test_target_root_resolver_uses_env_when_available() -> None:
    descriptor = load_descriptor('codex')
    resolved = resolve_default_target_root(descriptor, env={'VIBE_AGENTS_HOME': '/tmp/agents-home'}, home='/home/tester')
    assert resolved == '/tmp/agents-home'


def test_target_root_resolver_preserves_windows_home_separators() -> None:
    descriptor = load_descriptor('codex')
    resolved = resolve_default_target_root(descriptor, env={}, home=r'C:\Users\tester')
    assert resolved == r'C:\Users\tester\.agents'


def test_target_root_resolver_returns_absolute_default_exactly() -> None:
    descriptor = SimpleNamespace(
        id='demo',
        default_target_root='/opt/vgo-demo',
        default_target_root_env='',
        default_target_root_kind='fixed',
    )

    resolved = resolve_default_target_root(descriptor, env={}, home=r'C:\Users\tester')

    assert resolved == '/opt/vgo-demo'


def test_target_root_resolver_defaults_codex_to_real_home_root() -> None:
    descriptor = load_descriptor('codex')
    resolved = resolve_default_target_root(descriptor, env={}, home='/home/tester')
    assert resolved == '/home/tester/.agents'


def test_target_root_resolver_defaults_claude_code_to_real_home_root() -> None:
    descriptor = load_descriptor('claude-code')
    resolved = resolve_default_target_root(descriptor, env={}, home='/home/tester')
    assert resolved == '/home/tester/.agents'


def test_target_root_resolver_defaults_cursor_to_real_home_root() -> None:
    descriptor = load_descriptor('cursor')
    resolved = resolve_default_target_root(descriptor, env={}, home='/home/tester')
    assert resolved == '/home/tester/.agents'


def test_target_root_resolver_defaults_windsurf_to_real_home_root() -> None:
    descriptor = load_descriptor('windsurf')
    resolved = resolve_default_target_root(descriptor, env={}, home='/home/tester')
    assert resolved == '/home/tester/.agents'


def test_target_root_resolver_defaults_openclaw_to_real_home_root() -> None:
    descriptor = load_descriptor('openclaw')
    resolved = resolve_default_target_root(descriptor, env={}, home='/home/tester')
    assert resolved == '/home/tester/.agents'


def test_target_root_resolver_defaults_opencode_to_real_home_root() -> None:
    descriptor = load_descriptor('opencode')
    resolved = resolve_default_target_root(descriptor, env={}, home='/home/tester')
    assert resolved == '/home/tester/.agents'
