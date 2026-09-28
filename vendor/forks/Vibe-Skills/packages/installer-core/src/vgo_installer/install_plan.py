from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ledger_service import derive_managed_skill_names_from_ledger, sanitize_managed_skill_names


@dataclass(frozen=True, slots=True)
class InstallPlan:
    profile: str
    host_id: str
    target_root: Path
    runtime_root: Path
    host_bridge_root: Path
    desired_shared_runtime_root: Path
    runtime_layout_mode: str
    install_mode: str
    canonical_vibe_rel: str
    managed_skill_names: tuple[str, ...]
    previous_managed_skill_names: tuple[str, ...]
    internal_skill_target_relpath: str = ''


def build_install_plan(
    *,
    profile: str,
    host_id: str,
    target_root: Path | str,
    runtime_root: Path | str | None = None,
    host_bridge_root: Path | str | None = None,
    desired_shared_runtime_root: Path | str | None = None,
    runtime_layout_mode: str = 'co-located',
    install_mode: str = 'governed',
    canonical_vibe_rel: str = 'skills/vibe',
    managed_skill_names: list[str] | tuple[str, ...] | set[str] | None = None,
    existing_install_ledger: dict | None = None,
    internal_skill_target_relpath: str = '',
) -> InstallPlan:
    target_root_path = Path(target_root).resolve()
    runtime_root_path = Path(runtime_root).resolve() if runtime_root is not None else target_root_path
    host_bridge_root_path = Path(host_bridge_root).resolve() if host_bridge_root is not None else target_root_path
    desired_shared_runtime_root_path = (
        Path(desired_shared_runtime_root).resolve()
        if desired_shared_runtime_root is not None
        else runtime_root_path
    )
    normalized_rel = canonical_vibe_rel.replace('\\', '/').strip('/') or 'skills/vibe'
    safe_managed_skill_names = tuple(sanitize_managed_skill_names(managed_skill_names))
    previous_managed_skill_names = tuple(
        sorted(derive_managed_skill_names_from_ledger(target_root_path, existing_install_ledger))
    )

    return InstallPlan(
        profile=profile,
        host_id=host_id,
        target_root=target_root_path,
        runtime_root=runtime_root_path,
        host_bridge_root=host_bridge_root_path,
        desired_shared_runtime_root=desired_shared_runtime_root_path,
        runtime_layout_mode=str(runtime_layout_mode or 'co-located'),
        install_mode=install_mode,
        canonical_vibe_rel=normalized_rel,
        managed_skill_names=safe_managed_skill_names,
        previous_managed_skill_names=previous_managed_skill_names,
        internal_skill_target_relpath=str(internal_skill_target_relpath or ''),
    )
