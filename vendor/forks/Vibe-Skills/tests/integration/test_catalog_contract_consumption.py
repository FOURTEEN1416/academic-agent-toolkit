from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SRC = ROOT / 'packages' / 'contracts' / 'src'
INSTALLER_SRC = ROOT / 'packages' / 'installer-core' / 'src'
CATALOG_SRC = ROOT / 'packages' / 'skill-catalog' / 'src'
for src in (CONTRACTS_SRC, INSTALLER_SRC, CATALOG_SRC):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

from vgo_catalog.exporter import export_catalog_descriptor
from vgo_installer.install_plan import build_install_plan


def test_catalog_exports_descriptor_without_runtime_imports(tmp_path) -> None:
    descriptor = export_catalog_descriptor(tmp_path, profile='minimal')
    profiles_manifest = Path(descriptor['profiles_manifest']).as_posix()
    groups_manifest = Path(descriptor['groups_manifest']).as_posix()
    skill_source_root = Path(descriptor['skill_source_root']).as_posix()

    assert 'runtime' not in descriptor['owner']
    assert descriptor['owner'] == 'skill-catalog'
    assert profiles_manifest.endswith('catalog/profiles/index.json')
    assert groups_manifest.endswith('catalog/groups/index.json')
    assert skill_source_root.endswith('catalog/skills')
    assert 'bundled/skills' not in skill_source_root
    assert not (tmp_path / 'catalog' / 'skills' / 'systematic-debugging' / 'SKILL.md').exists()
    assert not (tmp_path / 'catalog' / 'skills' / 'brainstorming').exists()
    assert not (tmp_path / 'catalog' / 'skills' / 'scikit-learn').exists()


def test_catalog_full_profile_exports_extra_workflow_helpers(tmp_path) -> None:
    descriptor = export_catalog_descriptor(tmp_path, profile='full')

    assert Path(descriptor['skill_source_root']).as_posix().endswith('catalog/skills')
    assert not (tmp_path / 'catalog' / 'skills' / 'verification-before-completion' / 'SKILL.md').exists()
    assert not (tmp_path / 'catalog' / 'skills' / 'brainstorming').exists()
    assert not (tmp_path / 'catalog' / 'skills' / 'scikit-learn').exists()


def test_catalog_profiles_point_to_runtime_core_projections_instead_of_copying_skill_lists() -> None:
    minimal_profile = json.loads((ROOT / 'packages' / 'skill-catalog' / 'catalog' / 'profiles' / 'minimal.json').read_text(encoding='utf-8'))
    full_profile = json.loads((ROOT / 'packages' / 'skill-catalog' / 'catalog' / 'profiles' / 'full.json').read_text(encoding='utf-8'))

    assert minimal_profile['selection_mode'] == 'runtime_core_projection'
    assert minimal_profile['runtime_core_profile'] == 'minimal'
    assert 'skill_ids' not in minimal_profile

    assert full_profile['selection_mode'] == 'runtime_core_projection'
    assert full_profile['runtime_core_profile'] == 'full'
    assert 'exclude_skill_ids' not in full_profile


def test_skill_catalog_uses_local_bootstrap_helper_for_contract_path_setup() -> None:
    bootstrap = (ROOT / 'packages' / 'skill-catalog' / 'src' / 'vgo_catalog' / '_bootstrap.py').read_text(encoding='utf-8')
    exporter = (ROOT / 'packages' / 'skill-catalog' / 'src' / 'vgo_catalog' / 'exporter.py').read_text(encoding='utf-8')

    assert 'def ensure_contracts_src_on_path' in bootstrap
    assert 'from ._bootstrap import ensure_contracts_src_on_path' in exporter
    assert 'CONTRACTS_SRC =' not in exporter


def test_installer_plan_stays_decoupled_from_catalog_descriptor_metadata(tmp_path) -> None:
    descriptor = export_catalog_descriptor(tmp_path, profile='minimal')
    plan = build_install_plan(
        profile='minimal',
        host_id='codex',
        target_root=tmp_path,
        managed_skill_names=['vibe', 'brainstorming'],
    )

    assert plan.internal_skill_target_relpath == ''
    assert descriptor['owner'] == 'skill-catalog'
    assert 'bundled/skills' not in str(descriptor['catalog_root'])
    assert 'bundled/skills' not in str(descriptor['skill_source_root'])
