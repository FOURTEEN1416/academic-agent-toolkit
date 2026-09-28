from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MINIMAL_MANIFEST = REPO_ROOT / 'config' / 'runtime-core-packaging.minimal.json'
FULL_MANIFEST = REPO_ROOT / 'config' / 'runtime-core-packaging.full.json'
MODULE_PATH = REPO_ROOT / 'packages' / 'installer-core' / 'src' / 'vgo_installer' / 'profile_inventory.py'


def _load_profile_inventory_module():
    spec = importlib.util.spec_from_file_location('installer_profile_inventory', MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'unable to load module from {MODULE_PATH}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_profile_inventory_loader_reads_manifest_owned_skill_groups() -> None:
    module = _load_profile_inventory_module()
    minimal_manifest = _load(MINIMAL_MANIFEST)
    full_manifest = _load(FULL_MANIFEST)
    minimal = module.load_managed_skill_inventory(minimal_manifest)
    full = module.load_managed_skill_inventory(full_manifest)
    resident = module.internal_corpus_resident_skill_names(full_manifest)

    assert minimal.public_entry_skills == ('vibe',)
    assert minimal.starter_skill_names == ()
    assert minimal.optional_skill_names == ()
    assert full.optional_skill_names == ()
    assert resident == ()
    assert set(minimal.default_managed_skill_names).issubset(set(full.desired_managed_skill_names))
