"""Generic cumulative checkpoint policy helpers for v3.2.9.

This module is intentionally paper-agnostic. It discovers cumulative restore
assets from project roots/state/registries and validates the written archive.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Iterable

DEFAULT_STATIC_ROOTS = ("state", "inputs")
EXCLUDED_PREFIXES = ("checkpoints/",)
EXCLUDED_PARTS = {"__pycache__"}
EXCLUDED_SUFFIXES = {".pyc"}
RASTER_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def normalize_rel(value: str | Path) -> str:
    rel = Path(value).as_posix().lstrip("/")
    parts = []
    for part in rel.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError(f"unsafe relative path: {value!r}")
        parts.append(part)
    return "/".join(parts)


def should_include(rel: str, roots: Iterable[str]) -> bool:
    rel = normalize_rel(rel)
    if any(rel == p[:-1] or rel.startswith(p) for p in EXCLUDED_PREFIXES):
        return False
    if any(part in EXCLUDED_PARTS for part in rel.split("/")):
        return False
    if Path(rel).suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    norm_roots = [normalize_rel(r) for r in roots]
    return any(rel == root or rel.startswith(root + "/") for root in norm_roots)


def output_roots_through_current_stage(state: dict[str, Any]) -> list[str]:
    roots = []
    plan = state.get("workflow_plan") if isinstance(state, dict) else None
    if isinstance(plan, list):
        for row in plan:
            if isinstance(row, dict) and row.get("output_dir"):
                roots.append(normalize_rel(row["output_dir"]))
            status = row.get("status") if isinstance(row, dict) else None
            if status in {"in_progress", "current"}:
                break
    return roots


def included_roots_for_checkpoint(state: dict[str, Any], current_stage: str | None = None) -> list[str]:
    roots = list(DEFAULT_STATIC_ROOTS)
    plan = state.get("workflow_plan") if isinstance(state, dict) else None
    if isinstance(plan, list):
        for row in plan:
            if not isinstance(row, dict):
                continue
            out = row.get("output_dir")
            if out:
                roots.append(normalize_rel(out))
            if current_stage and row.get("step") == current_stage:
                break
            if not current_stage and row.get("status") in {"in_progress", "current"}:
                break
    else:
        roots.extend(output_roots_through_current_stage(state))
    # preserve order, drop duplicates
    result=[]
    for root in roots:
        if root and root not in result:
            result.append(root)
    return result


def iter_existing_assets(run_dir: str | Path, roots: Iterable[str]) -> list[str]:
    run = Path(run_dir)
    assets=[]
    for path in run.rglob("*"):
        if not path.is_file():
            continue
        rel = normalize_rel(path.relative_to(run))
        if should_include(rel, roots):
            assets.append(rel)
    return sorted(set(assets))


def iter_registered_raster_paths(state: dict[str, Any]) -> list[str]:
    found=[]
    def walk(value: Any):
        if isinstance(value, str):
            if Path(value).suffix.lower() in RASTER_EXTS:
                try:
                    found.append(normalize_rel(value))
                except ValueError:
                    pass
        elif isinstance(value, dict):
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(state)
    return sorted(set(found))


def required_existing_assets(run_dir: str | Path, state: dict[str, Any], current_stage: str | None = None) -> list[str]:
    roots = included_roots_for_checkpoint(state, current_stage)
    assets = set(iter_existing_assets(run_dir, roots))
    run = Path(run_dir)
    for rel in iter_registered_raster_paths(state):
        if should_include(rel, roots) and (run / rel).is_file():
            assets.add(rel)
    return sorted(assets)


def validate_checkpoint_zip(zip_paths: str | Path | Iterable[str | Path], required_files: Iterable[str]) -> tuple[bool, list[str]]:
    if isinstance(zip_paths, (str, Path)):
        paths = [zip_paths]
    else:
        paths = list(zip_paths)
    members=set()
    for path in paths:
        zp=Path(path)
        if not zp.is_file():
            continue
        with zipfile.ZipFile(zp, 'r') as archive:
            members.update(archive.namelist())
    missing=[normalize_rel(f) for f in required_files if normalize_rel(f) not in members]
    return (not missing), missing


def write_missing_assets_manifest(path: str | Path, missing: Iterable[str]) -> None:
    rows = [
        {
            "relative_path": normalize_rel(m),
            "status": "missing_from_checkpoint_zip_after_write",
            "required_for_complete_restore": True,
        }
        for m in missing
    ]
    Path(path).write_text(
        json.dumps({"missing_assets": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )



def stage_coverage_from_workflow(state: dict[str, Any], included_roots: Iterable[str]) -> list[dict[str, str]]:
    """Derive covered stages from state.workflow_plan and included roots.

    The result is intentionally generic: it uses only declared workflow rows and
    output directories, never paper-specific terms, candidate ids, or image counts.
    """
    norm_roots = {normalize_rel(root) for root in included_roots}
    coverage: list[dict[str, str]] = []
    plan = state.get("workflow_plan") if isinstance(state, dict) else None
    if isinstance(plan, list):
        for row in plan:
            if not isinstance(row, dict):
                continue
            out = row.get("output_dir")
            step = row.get("step")
            if isinstance(out, str) and isinstance(step, str) and normalize_rel(out) in norm_roots:
                coverage.append({
                    "step": step,
                    "output_dir": normalize_rel(out),
                    "status": str(row.get("status", "")),
                })
    return coverage


def checkpoint_member_union(zip_paths: str | Path | Iterable[str | Path]) -> set[str]:
    if isinstance(zip_paths, (str, Path)):
        paths = [zip_paths]
    else:
        paths = list(zip_paths)
    members: set[str] = set()
    for path in paths:
        zp = Path(path)
        if not zp.is_file():
            continue
        with zipfile.ZipFile(zp, "r") as archive:
            members.update(archive.namelist())
    return members


def cumulative_checkpoint_guard_report(
    run_dir: str | Path,
    state: dict[str, Any],
    zip_paths: str | Path | Iterable[str | Path],
    current_stage: str | None = None,
) -> dict[str, Any]:
    """Validate a checkpoint against cumulative run inventory.

    Use this from any checkpoint-producing substage/page to prevent
    current-stage-only or current-substage-only bundles from being advertised as
    complete restore checkpoints.
    """
    roots = included_roots_for_checkpoint(state, current_stage)
    required = required_existing_assets(run_dir, state, current_stage)
    members = checkpoint_member_union(zip_paths)
    missing = [rel for rel in required if rel not in members]
    coverage = stage_coverage_from_workflow(state, roots)
    return {
        "schema_version": 1,
        "guard": "cumulative_checkpoint_integrity_guard",
        "current_stage": current_stage,
        "cumulative_required": True,
        "included_roots": roots,
        "stage_coverage": coverage,
        "required_existing_asset_count": len(required),
        "archive_member_count": len(members),
        "missing_existing_asset_count": len(missing),
        "missing_existing_assets": missing,
        "status": "PASS" if not missing else "FAIL",
        "non_hardcoding_statement": "Derived from workflow state, included roots, and existing files only; no paper, project, candidate, image-count, or filename hardcoding.",
    }
