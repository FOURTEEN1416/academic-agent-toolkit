from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import shutil

from ._bootstrap import ensure_contracts_src_on_path

ensure_contracts_src_on_path()

from vgo_contracts.catalog_descriptor import CatalogDescriptor


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parents[1]
CATALOG_ROOT = PACKAGE_ROOT / 'catalog'
SKILL_SOURCE_ROOT = REPO_ROOT / 'bundled' / 'skills'
PROFILES_ROOT = CATALOG_ROOT / 'profiles'
RUNTIME_CORE_CONFIG_ROOT = REPO_ROOT / 'config'


def _build_descriptor(catalog_root: Path, skill_source_root: Path) -> dict[str, object]:
    descriptor = CatalogDescriptor(
        catalog_root=str(catalog_root),
        skill_source_root=str(skill_source_root),
        profiles_manifest=str(catalog_root / 'profiles' / 'index.json'),
        groups_manifest=str(catalog_root / 'groups' / 'index.json'),
        metadata_manifest=str(catalog_root / 'metadata' / 'index.json'),
        owner='skill-catalog',
        owners=['skill-catalog'],
    )
    return asdict(descriptor)


def _load_profile(profile: str) -> dict[str, object]:
    path = PROFILES_ROOT / f'{profile}.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'catalog profile must be a JSON object: {path}')
    return payload


def _load_runtime_core_projection(profile: str) -> dict[str, object]:
    path = RUNTIME_CORE_CONFIG_ROOT / f'runtime-core-packaging.{profile}.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'runtime-core packaging projection must be a JSON object: {path}')
    return payload


def _selected_skill_ids_from_runtime_core_projection(profile: str) -> list[str]:
    payload = _load_runtime_core_projection(profile)
    excluded = {
        str(skill_id).strip()
        for skill_id in payload.get('exclude_bundled_skill_names') or []
        if str(skill_id).strip()
    }

    if bool(payload.get('copy_bundled_skills')):
        return sorted(
            skill_dir.name
            for skill_dir in SKILL_SOURCE_ROOT.iterdir()
            if skill_dir.is_dir() and skill_dir.name not in excluded
        )

    inventory = payload.get('managed_skill_inventory') or {}
    selected_skill_ids: list[str] = []
    seen: set[str] = set()
    for group in (
        inventory.get('public_entry_skills') or [],
        inventory.get('starter_skill_names') or [],
        inventory.get('optional_skill_names') or [],
    ):
        for raw_skill_id in group:
            skill_id = str(raw_skill_id).strip()
            if not skill_id or skill_id == 'vibe' or skill_id in excluded or skill_id in seen:
                continue
            seen.add(skill_id)
            selected_skill_ids.append(skill_id)

    return sorted(
        selected_skill_ids
    )


def _selected_skill_ids(profile: str) -> list[str] | None:
    payload = _load_profile(profile)
    mode = str(payload.get('selection_mode') or '').strip()
    if mode == 'runtime_core_projection':
        runtime_core_profile = str(payload.get('runtime_core_profile') or profile).strip() or profile
        return _selected_skill_ids_from_runtime_core_projection(runtime_core_profile)
    raise ValueError(f'unsupported skill catalog selection mode for profile {profile!r}: {mode!r}')


def _export_profiled_skills(target_root: Path, profile: str) -> Path:
    exported_skill_root = target_root / 'skills'
    selected_skill_ids = _selected_skill_ids(profile)
    if exported_skill_root.exists():
        shutil.rmtree(exported_skill_root)
    exported_skill_root.mkdir(parents=True, exist_ok=True)
    for skill_id in selected_skill_ids or []:
        source = SKILL_SOURCE_ROOT / skill_id
        if not source.is_dir():
            raise FileNotFoundError(f'missing catalog skill source for profile {profile!r}: {source}')
        shutil.copytree(source, exported_skill_root / skill_id)
    return exported_skill_root


def describe_local_catalog() -> dict[str, object]:
    return _build_descriptor(CATALOG_ROOT.resolve(), SKILL_SOURCE_ROOT.resolve())


def export_catalog_descriptor(output_root: Path | str, profile: str = 'minimal') -> dict[str, object]:
    target_root = Path(output_root).resolve()
    exported_catalog_root = target_root / 'catalog'
    if exported_catalog_root.exists():
        shutil.rmtree(exported_catalog_root)
    shutil.copytree(CATALOG_ROOT, exported_catalog_root)
    exported_skill_root = _export_profiled_skills(exported_catalog_root, profile)
    return _build_descriptor(exported_catalog_root, exported_skill_root)
