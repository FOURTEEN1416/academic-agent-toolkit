from __future__ import annotations

import os
from pathlib import Path


CONTRACTS_SRC = Path(__file__).resolve().parents[4] / "packages" / "contracts" / "src"
if CONTRACTS_SRC.is_dir() and str(CONTRACTS_SRC) not in os.sys.path:
    os.sys.path.insert(0, str(CONTRACTS_SRC))

from vgo_contracts.discoverable_entry_surface import (
    DISCOVERABLE_ENTRY_SURFACE_RELPATH,
    DiscoverableEntry,
    load_discoverable_entry_surface,
    resolve_discoverable_entry_surface_path,
)


ROUTE_SURFACE_ROOT = str(DISCOVERABLE_ENTRY_SURFACE_RELPATH).replace("\\", "/")
ROUTE_SURFACE_KIND = "runtime_surface"
ROUTE_SURFACE_PRIORITY = 0
ROUTE_SURFACE_PATH_CONTRACT = "runtime_surface_relative"


def _entry_description(entry: DiscoverableEntry, *, canonical_runtime_skill: str) -> str:
    if entry.id == canonical_runtime_skill:
        return "General work orchestration entry for the full work loop."
    if "upgrade" in entry.id:
        return "Upgrade or refresh the local vibe installation."
    if entry.requested_stage_stop == "requirement_doc":
        return "Clarify the task, shape requirements, and reduce ambiguity."
    if entry.requested_stage_stop == "xl_plan":
        return "Turn a task into an implementation plan or execution design."
    return "Execute the work, make changes, run reviews, or finish the task."


def _entry_when_to_use(entry: DiscoverableEntry, *, canonical_runtime_skill: str) -> list[str]:
    if entry.id == canonical_runtime_skill:
        return ["general task orchestration", "full workflow", "default work loop"]
    if "upgrade" in entry.id:
        return ["upgrade runtime", "refresh installation", "install update"]
    if entry.requested_stage_stop == "requirement_doc":
        return ["requirements", "clarify goal", "scope the task", "reduce ambiguity"]
    if entry.requested_stage_stop == "xl_plan":
        return ["plan the work", "architecture design", "implementation plan", "execution design"]
    return ["implement", "execute", "fix", "review", "finish the task"]


def _entry_not_for(entry: DiscoverableEntry, *, canonical_runtime_skill: str) -> list[str]:
    if entry.id == canonical_runtime_skill:
        return []
    if "upgrade" in entry.id:
        return ["normal task execution"]
    if entry.requested_stage_stop == "requirement_doc":
        return ["final execution"]
    if entry.requested_stage_stop == "xl_plan":
        return ["final execution only"]
    return ["early requirement discovery"]


def _entry_tags(entry: DiscoverableEntry, *, canonical_runtime_skill: str) -> list[str]:
    if entry.id == canonical_runtime_skill:
        return ["general", "planning", "execution", "workflow"]
    if "upgrade" in entry.id:
        return ["upgrade", "install", "runtime"]
    if entry.requested_stage_stop == "requirement_doc":
        return ["clarify", "requirements", "planning"]
    if entry.requested_stage_stop == "xl_plan":
        return ["plan", "planning", "design", "architecture"]
    return ["execution", "coding", "review", "debug"]


def _entry_priority(entry: DiscoverableEntry, *, canonical_runtime_skill: str) -> int:
    if entry.id == canonical_runtime_skill:
        return 40
    if "upgrade" in entry.id:
        return 80
    if entry.requested_stage_stop == "requirement_doc":
        return 55
    if entry.requested_stage_stop == "xl_plan":
        return 60
    return 65


def _route_index_row(
    entry: DiscoverableEntry,
    *,
    canonical_runtime_skill: str,
    source_order: int,
    surface_path: Path,
) -> dict[str, object]:
    repo_root = surface_path.parents[1]
    return {
        "id": entry.id,
        "name": entry.display_name,
        "description": _entry_description(entry, canonical_runtime_skill=canonical_runtime_skill),
        "when_to_use": _entry_when_to_use(entry, canonical_runtime_skill=canonical_runtime_skill),
        "not_for": _entry_not_for(entry, canonical_runtime_skill=canonical_runtime_skill),
        "tags": _entry_tags(entry, canonical_runtime_skill=canonical_runtime_skill),
        "enabled": True,
        "publicly_exposed": entry.publicly_exposed,
        "priority": _entry_priority(entry, canonical_runtime_skill=canonical_runtime_skill),
        "source_kind": ROUTE_SURFACE_KIND,
        "source_root": ROUTE_SURFACE_ROOT,
        "resolved_source_root": str(surface_path),
        "source_priority": ROUTE_SURFACE_PRIORITY,
        "source_order": source_order,
        "resolved_root_dir": str(surface_path.parent),
        "resolved_skill_file": str(surface_path),
        "path_contract": ROUTE_SURFACE_PATH_CONTRACT,
        "path_base": str(repo_root),
    }


def load_runtime_route_index() -> dict[str, object]:
    surface_path = resolve_discoverable_entry_surface_path(Path(__file__))
    surface = load_discoverable_entry_surface(surface_path)
    return {
        "version": 1,
        "generated_at": "discoverable-entry-surface-projection",
        "roots": [ROUTE_SURFACE_ROOT],
        "skills": [
            _route_index_row(
                entry,
                canonical_runtime_skill=surface.canonical_runtime_skill,
                source_order=index,
                surface_path=surface_path,
            )
            for index, entry in enumerate(surface.entries)
        ],
    }
