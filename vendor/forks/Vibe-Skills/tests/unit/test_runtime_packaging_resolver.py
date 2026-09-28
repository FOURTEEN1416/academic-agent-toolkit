from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_CORE_SRC = REPO_ROOT / 'packages' / 'installer-core' / 'src'
MODULE_PATH = REPO_ROOT / 'packages' / 'installer-core' / 'src' / 'vgo_installer' / 'runtime_packaging.py'
if str(INSTALLER_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(INSTALLER_CORE_SRC))
def _load_module():
    spec = importlib.util.spec_from_file_location('runtime_packaging_unit', MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'unable to load module from {MODULE_PATH}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_packaging_resolver_loads_profile_projection_from_authoritative_base() -> None:
    module = _load_module()
    minimal = module.resolve_runtime_core_packaging(REPO_ROOT, 'minimal')
    full = module.resolve_runtime_core_packaging(REPO_ROOT, 'full')

    assert minimal['profile'] == 'minimal'
    assert full['profile'] == 'full'
    assert 'copy_bundled_skills' not in minimal
    assert 'copy_bundled_skills' not in full
    assert minimal['canonical_vibe_payload']['target_relpath'] == 'skills/vibe'
    assert full['canonical_vibe_payload']['target_relpath'] == 'skills/vibe'
    assert 'surface_contracts' not in minimal['payload_roles']
    assert 'surface_contracts' not in full['payload_roles']
    assert minimal['compatibility_skill_projections']['projected_skill_names'] == []
    assert full['compatibility_skill_projections']['projected_skill_names'] == []
    assert minimal['public_skill_surface']['mode'] == 'discoverable_wrapper_projection'
    assert full['public_skill_surface']['mode'] == 'discoverable_wrapper_projection'
    assert minimal['public_skill_surface']['discoverable_entry_surface'] == 'config/vibe-entry-surfaces.json'
    assert full['public_skill_surface']['discoverable_entry_surface'] == 'config/vibe-entry-surfaces.json'
    assert minimal['public_skill_surface']['projected_skill_names'] == ['vibe']
    assert full['public_skill_surface']['projected_skill_names'] == ['vibe']
    assert 'skills_allowlist' not in minimal
    assert 'skills_allowlist' not in full


def test_resolve_bundled_skills_root_normalizes_relative_packaging_sources_against_repo_root(monkeypatch) -> None:
    from vgo_installer import materializer as module

    with tempfile.TemporaryDirectory() as tempdir:
        repo_root = Path(tempdir) / 'repo'
        catalog_root = repo_root / 'catalog'
        (catalog_root / 'skills').mkdir(parents=True)
        workdir = Path(tempdir) / 'cwd'
        workdir.mkdir(parents=True)
        monkeypatch.chdir(workdir)
        packaging = {
            'bundled_skills_source': 'bundled/skills',
            'skill_source_root': 'catalog/skills',
            'catalog_root': 'catalog',
        }

        try:
            resolved = module.resolve_bundled_skills_root(repo_root, packaging)
        finally:
            monkeypatch.chdir(REPO_ROOT)

    assert resolved == (repo_root / 'catalog' / 'skills').resolve()
