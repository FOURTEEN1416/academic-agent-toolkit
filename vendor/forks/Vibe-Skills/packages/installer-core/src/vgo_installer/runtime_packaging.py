from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

try:
    from ._bootstrap import ensure_contracts_src_on_path
except ImportError:  # pragma: no cover - standalone module loading in file-based tests
    bootstrap_path = Path(__file__).with_name('_bootstrap.py')
    bootstrap_spec = importlib.util.spec_from_file_location('vgo_installer_runtime_packaging_bootstrap', bootstrap_path)
    if bootstrap_spec is None or bootstrap_spec.loader is None:
        raise
    bootstrap_module = importlib.util.module_from_spec(bootstrap_spec)
    sys.modules.setdefault(bootstrap_spec.name, bootstrap_module)
    bootstrap_spec.loader.exec_module(bootstrap_module)
    ensure_contracts_src_on_path = bootstrap_module.ensure_contracts_src_on_path

ensure_contracts_src_on_path()

from vgo_contracts.discoverable_entry_surface import load_discoverable_entry_surface

try:
    from ._io import load_json
except ImportError:  # pragma: no cover - standalone module loading in file-based tests
    io_path = Path(__file__).with_name('_io.py')
    spec = importlib.util.spec_from_file_location('vgo_installer_runtime_packaging_io', io_path)
    if spec is None or spec.loader is None:
        raise
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    load_json = module.load_json

try:
    from .profile_inventory import allowlisted_bundled_skill_names
except ImportError:  # pragma: no cover - standalone module loading in file-based tests
    profile_inventory_path = Path(__file__).with_name('profile_inventory.py')
    profile_inventory_spec = importlib.util.spec_from_file_location(
        'vgo_installer_runtime_packaging_profile_inventory',
        profile_inventory_path,
    )
    if profile_inventory_spec is None or profile_inventory_spec.loader is None:
        raise
    profile_inventory_module = importlib.util.module_from_spec(profile_inventory_spec)
    sys.modules.setdefault(profile_inventory_spec.name, profile_inventory_module)
    profile_inventory_spec.loader.exec_module(profile_inventory_module)
    allowlisted_bundled_skill_names = profile_inventory_module.allowlisted_bundled_skill_names


RUNTIME_CORE_BASE_MANIFEST = Path('config/runtime-core-packaging.json')


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = {key: _deep_merge(value, overlay[key]) if key in overlay else value for key, value in base.items()}
        for key, value in overlay.items():
            if key not in merged:
                merged[key] = value
        return merged
    return overlay


def load_runtime_core_packaging_base(repo_root: Path) -> dict[str, Any]:
    return load_json((repo_root / RUNTIME_CORE_BASE_MANIFEST).resolve())


def public_skill_projection_names(packaging: dict[str, Any]) -> list[str]:
    surface = packaging.get('public_skill_surface') or {}
    discoverable_surface = str(surface.get('discoverable_entry_surface') or '').strip()
    if discoverable_surface:
        repo_root = Path(packaging.get('_repo_root') or '').resolve() if packaging.get('_repo_root') else None
        if repo_root is not None:
            try:
                return load_discoverable_entry_surface(repo_root).projected_skill_names
            except RuntimeError:
                pass
    names = surface.get('projected_skill_names') or []
    seen: set[str] = set()
    result: list[str] = []
    for raw in names:
        name = str(raw).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def internal_skill_corpus_target_relpath(packaging: dict[str, Any]) -> str:
    corpus = packaging.get('internal_skill_corpus') or {}
    target = str(corpus.get('target_relpath') or '').strip()
    return target


def resolve_runtime_core_projection_path(repo_root: Path, profile: str) -> Path:
    base = load_runtime_core_packaging_base(repo_root)
    manifest_map = base.get('profile_manifests') or {}
    manifest_rel = str(manifest_map.get(profile) or '').strip()
    if manifest_rel:
        return (repo_root / manifest_rel).resolve()
    return (repo_root / RUNTIME_CORE_BASE_MANIFEST).resolve()


def resolve_runtime_core_packaging(repo_root: Path, profile: str) -> dict[str, Any]:
    base = load_runtime_core_packaging_base(repo_root)
    profiles = base.get('profiles') or {}
    profile_overlay = profiles.get(profile)
    if isinstance(profile_overlay, dict):
        merged = dict(base)
        merged.pop('profiles', None)
        merged.pop('default_profile', None)
        merged = _deep_merge(merged, profile_overlay)
        merged.setdefault('profile', profile)
        merged['_repo_root'] = str(repo_root)
        merged.setdefault('public_skill_surface', {})
        merged.setdefault('internal_skill_corpus', {})
        merged.setdefault('compatibility_skill_projections', {'projection_mode': 'explicit_projection_only', 'projected_skill_names': []})
        discoverable_surface = str((merged.get('public_skill_surface') or {}).get('discoverable_entry_surface') or '').strip()
        if discoverable_surface:
            try:
                merged['public_skill_surface']['projected_skill_names'] = load_discoverable_entry_surface(repo_root).projected_skill_names
            except RuntimeError:
                pass
        return merged

    projection_path = resolve_runtime_core_projection_path(repo_root, profile)
    packaging = load_json(projection_path)
    packaging.setdefault('profile', profile)
    packaging['_repo_root'] = str(repo_root)
    packaging.setdefault('public_skill_surface', {})
    packaging.setdefault('internal_skill_corpus', {})
    packaging.setdefault('compatibility_skill_projections', {'projection_mode': 'explicit_projection_only', 'projected_skill_names': []})
    discoverable_surface = str((packaging.get('public_skill_surface') or {}).get('discoverable_entry_surface') or '').strip()
    if discoverable_surface:
        try:
            packaging['public_skill_surface']['projected_skill_names'] = load_discoverable_entry_surface(repo_root).projected_skill_names
        except RuntimeError:
            pass
    return packaging
