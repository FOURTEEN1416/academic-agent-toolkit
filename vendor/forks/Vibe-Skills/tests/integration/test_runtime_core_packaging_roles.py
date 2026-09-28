from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_MANIFEST = REPO_ROOT / "config" / "runtime-core-packaging.json"
MINIMAL_MANIFEST = REPO_ROOT / "config" / "runtime-core-packaging.minimal.json"
FULL_MANIFEST = REPO_ROOT / "config" / "runtime-core-packaging.full.json"
MODULE_PATH = REPO_ROOT / 'packages' / 'installer-core' / 'src' / 'vgo_installer' / 'runtime_packaging.py'
def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_runtime_packaging_module():
    spec = importlib.util.spec_from_file_location('runtime_packaging_contract', MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'unable to load module from {MODULE_PATH}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _flatten_entry_groups(groups: dict[str, list[dict]]) -> list[tuple]:
    items: list[tuple] = []
    for values in groups.values():
        for value in values:
            items.append(tuple(sorted(value.items())))
    return items


def _supports_surface_split(manifest: dict) -> bool:
    required = {
        'public_skill_surface',
        'internal_skill_corpus',
        'compatibility_skill_projections',
    }
    return required.issubset(set(manifest))


def _resolve_canonical_vibe_target(surface: dict) -> str | None:
    if not isinstance(surface, dict):
        return None
    for key in ('canonical_vibe_target_relpath', 'canonical_entrypoint_relpath'):
        value = surface.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_resolved_projection(payload: dict) -> dict:
    normalized = dict(payload)
    normalized.pop('_repo_root', None)
    return normalized


def test_base_runtime_core_packaging_owns_shared_fields_and_profile_overlays() -> None:
    payload = _load(BASE_MANIFEST)
    roles = payload['payload_roles']

    assert payload['default_profile'] == 'minimal'
    assert set(payload['profiles']) == {'minimal', 'full'}
    assert 'copy_directories' not in payload
    assert set(payload['directories']) == {'skills', 'commands', 'config'}

    target_dirs = []
    for values in roles['target_directories'].values():
        target_dirs.extend(values)
    assert set(target_dirs) == set(payload['directories'])
    assert len(target_dirs) == len(set(target_dirs))

    grouped_copy_files = _flatten_entry_groups(roles['copy_files'])
    assert set(grouped_copy_files) == {tuple(sorted(item.items())) for item in payload['copy_files']}
    assert roles['notes']['flat_projection_contract']
    assert 'surface_contracts' not in roles
    assert 'surface_contracts' not in payload['profiles']['minimal']['payload_roles']
    assert 'surface_contracts' not in payload['profiles']['full']['payload_roles']


def test_profile_runtime_core_packaging_projections_match_base_overlay_resolution() -> None:
    runtime_packaging = _load_runtime_packaging_module()
    minimal_projection = _load(MINIMAL_MANIFEST)
    full_projection = _load(FULL_MANIFEST)

    resolved_minimal = _normalize_resolved_projection(runtime_packaging.resolve_runtime_core_packaging(REPO_ROOT, 'minimal'))
    resolved_full = _normalize_resolved_projection(runtime_packaging.resolve_runtime_core_packaging(REPO_ROOT, 'full'))

    if _supports_surface_split(resolved_full):
        assert resolved_minimal['profile'] == 'minimal'
        assert resolved_full['profile'] == 'full'
        assert _resolve_canonical_vibe_target(resolved_minimal['public_skill_surface']) == 'skills/vibe'
        assert _resolve_canonical_vibe_target(resolved_full['public_skill_surface']) == 'skills/vibe'
        assert resolved_minimal['internal_skill_corpus']['enabled'] is False
        assert resolved_full['internal_skill_corpus']['enabled'] is False
        assert resolved_minimal == minimal_projection
        assert resolved_full == full_projection
    else:
        assert minimal_projection == resolved_minimal
        assert full_projection == resolved_full


def test_committed_profile_runtime_core_packaging_does_not_embed_repo_root() -> None:
    assert "_repo_root" not in _load(MINIMAL_MANIFEST)
    assert "_repo_root" not in _load(FULL_MANIFEST)


def test_profile_runtime_core_packaging_roles_keep_surface_truth_top_level() -> None:
    minimal = _load(MINIMAL_MANIFEST)
    full = _load(FULL_MANIFEST)

    assert minimal['canonical_vibe_payload']['target_relpath'] == 'skills/vibe'
    assert full['canonical_vibe_payload']['target_relpath'] == 'skills/vibe'
    assert 'surface_contracts' not in minimal['payload_roles']
    assert 'surface_contracts' not in full['payload_roles']
    if _supports_surface_split(minimal):
        assert minimal['compatibility_skill_projections']['projected_skill_names'] == []
        assert minimal['internal_skill_corpus']['enabled'] is False
        assert minimal['internal_skill_corpus']['resident_skill_names'] == []
        assert minimal['public_skill_surface']['mode'] == 'discoverable_wrapper_projection'
        assert minimal['public_skill_surface']['discoverable_entry_surface'] == 'config/vibe-entry-surfaces.json'
        assert minimal['public_skill_surface']['projected_skill_names'] == ['vibe']
    if _supports_surface_split(full):
        assert full['compatibility_skill_projections']['projected_skill_names'] == []
        assert full['internal_skill_corpus']['enabled'] is False
        assert full['internal_skill_corpus']['resident_skill_names'] == []
        assert full['public_skill_surface']['mode'] == 'discoverable_wrapper_projection'
        assert full['public_skill_surface']['discoverable_entry_surface'] == 'config/vibe-entry-surfaces.json'
        assert full['public_skill_surface']['projected_skill_names'] == ['vibe']


def test_profile_runtime_core_packaging_role_sources_match_copy_projection() -> None:
    minimal = _load(MINIMAL_MANIFEST)
    full = _load(FULL_MANIFEST)

    minimal_sources = {tuple(sorted(item.items())) for item in minimal['payload_roles']['copy_directories']['active_sources']}
    full_sources = {tuple(sorted(item.items())) for item in full['payload_roles']['copy_directories']['active_sources']}

    assert minimal_sources == {tuple(sorted(item.items())) for item in minimal['copy_directories']}
    assert full_sources == {tuple(sorted(item.items())) for item in full['copy_directories']}
    assert all(dict(entry)['source'] == 'commands' for entry in minimal_sources)
    if _supports_surface_split(full):
        assert not any(
            dict(entry).get('source') == 'bundled/skills' and dict(entry).get('target') == 'skills'
            for entry in full_sources
        )
    else:
        assert any(dict(entry)['source'] == 'bundled/skills' for entry in full_sources)


def test_profile_managed_skill_inventory_is_manifest_owned() -> None:
    runtime_packaging = _load_runtime_packaging_module()
    minimal = _load(MINIMAL_MANIFEST)
    full = _load(FULL_MANIFEST)
    resolved_minimal = runtime_packaging.resolve_runtime_core_packaging(REPO_ROOT, 'minimal')
    resolved_full = runtime_packaging.resolve_runtime_core_packaging(REPO_ROOT, 'full')

    minimal_inventory = minimal['managed_skill_inventory']
    full_inventory = full['managed_skill_inventory']

    minimal_public_entries = set(minimal_inventory['public_entry_skills'])
    minimal_starter_skills = set(minimal_inventory['starter_skill_names'])
    full_public_entries = set(full_inventory['public_entry_skills'])
    full_starter_skills = set(full_inventory['starter_skill_names'])
    full_optional_skills = set(full_inventory['optional_skill_names'])

    assert minimal_public_entries == {'vibe'}
    assert minimal_public_entries == full_public_entries
    assert minimal_starter_skills == full_starter_skills
    assert full_optional_skills == set()
    assert not (minimal_public_entries & minimal_starter_skills)
    assert not (full_public_entries & full_optional_skills)
    assert not (full_starter_skills & full_optional_skills)
    assert 'skills_allowlist' not in minimal
    assert 'skills_allowlist' not in full
    assert 'skills_allowlist' not in resolved_minimal
    assert 'skills_allowlist' not in resolved_full
    assert minimal['internal_skill_corpus']['resident_skill_names'] == []
    assert full['internal_skill_corpus']['resident_skill_names'] == []


def test_surface_split_semantics_are_declared_when_available() -> None:
    base = _load(BASE_MANIFEST)
    full = _load(FULL_MANIFEST)
    required = {
        'public_skill_surface',
        'internal_skill_corpus',
        'compatibility_skill_projections',
    }
    if not required.issubset(set(base)) and not required.issubset(set(full)):
        pytest.skip('surface split semantics are not available in this branch yet')

    container = full if required.issubset(set(full)) else base
    assert required.issubset(set(container))
    assert isinstance(container['public_skill_surface'], (dict, list))
    assert isinstance(container['internal_skill_corpus'], (dict, list))
    assert isinstance(container['compatibility_skill_projections'], (dict, list))

    serialized_public = json.dumps(container['public_skill_surface'], ensure_ascii=True)
    serialized_internal = json.dumps(container['internal_skill_corpus'], ensure_ascii=True)
    assert 'skills/vibe' in serialized_public or 'skills/vibe' in serialized_internal


def test_full_profile_defaults_to_no_top_level_bundled_skill_fanout_when_split_semantics_available() -> None:
    full = _load(FULL_MANIFEST)
    if not _supports_surface_split(full):
        pytest.skip('full profile still uses legacy top-level bundled skill projection')

    legacy_flatten = any(
        entry.get('source') == 'bundled/skills' and entry.get('target') == 'skills'
        for entry in full.get('copy_directories') or []
        if isinstance(entry, dict)
    )
    assert not legacy_flatten
