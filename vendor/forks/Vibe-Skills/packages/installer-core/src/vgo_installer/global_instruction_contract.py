from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class GlobalInstructionSurface:
    relpath: str
    documented_path: str
    format: str
    managed_block_id: str
    merge_policy: str
    overwrite_policy: str
    trigger_tokens: tuple[str, ...]
    authority_owner: str
    bootstrap_only: bool
    template_relpath: str
    template_version: int

    @property
    def target_relpath(self) -> str:
        return self.relpath

    def target_path(self, target_root: Path) -> Path:
        return (target_root / self.relpath).resolve(strict=False)

    def template_path(self, repo_root: Path) -> Path:
        return (repo_root / self.template_relpath).resolve(strict=False)


def _expect_text(mapping: dict[str, Any], key: str) -> str:
    value = str(mapping.get(key) or "").strip()
    if not value:
        raise ValueError(f"missing global_instruction_surface.{key}")
    return value


def _expect_string_list(mapping: dict[str, Any], key: str) -> tuple[str, ...]:
    raw = mapping.get(key)
    if not isinstance(raw, list):
        raise ValueError(f"missing global_instruction_surface.{key}")
    values = tuple(str(item).strip() for item in raw if str(item).strip())
    if not values:
        raise ValueError(f"missing global_instruction_surface.{key}")
    return values


def resolve_global_instruction_surface(adapter: dict[str, Any]) -> GlobalInstructionSurface | None:
    raw = adapter.get("host_profile_json") if isinstance(adapter.get("host_profile_json"), dict) else adapter
    if not isinstance(raw, dict):
        return None
    surface = raw.get("global_instruction_surface")
    if surface is None:
        return None
    if not isinstance(surface, dict):
        raise ValueError("global_instruction_surface must be a JSON object")
    version = int(surface.get("template_version") or 1)
    return GlobalInstructionSurface(
        relpath=_expect_text(surface, "relpath"),
        documented_path=_expect_text(surface, "documented_path"),
        format=_expect_text(surface, "format"),
        managed_block_id=_expect_text(surface, "managed_block_id"),
        merge_policy=_expect_text(surface, "merge_policy"),
        overwrite_policy=_expect_text(surface, "overwrite_policy"),
        trigger_tokens=_expect_string_list(surface, "trigger_tokens"),
        authority_owner=_expect_text(surface, "authority_owner"),
        bootstrap_only=bool(surface.get("bootstrap_only", True)),
        template_relpath=_expect_text(surface, "template_relpath"),
        template_version=version,
    )
