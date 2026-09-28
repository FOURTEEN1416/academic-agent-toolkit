"""Artifact index and overwrite/delete helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import (
    ARTIFACT_ROLES,
    FORBIDDEN_TARGET_IMAGE_EXTS,
    FORBIDDEN_TARGET_IMAGE_KINDS,
    PENDING_CANONICAL_OUTPUTS,
    TARGET_RASTER_IMAGE_EXTS,
    TARGET_RASTER_IMAGE_STEPS,
    TARGET_RASTER_REFERENCE_ROLES,
)
from .errors import StateError
from .paths import normalize_relative_path, safe_join, sha256_file, utc_now
from .state_schema import current_step_epoch, step_attempt_id
from .runtime_config import validate_image_generation_route

INACTIVE_ARTIFACT_STATUSES = {
    "deleted",
    "unavailable",
    "unavailable_after_step_rewind_cleanup",
    "superseded",
    "stale",
    "missing",
}

def find_artifact(state: dict[str, Any], artifact_id: str) -> dict[str, Any] | None:
    for artifact in state.get("artifacts", []):
        if artifact.get("artifact_id") == artifact_id:
            return artifact
    return None

def is_protected_support_reference(relative_path: str | None) -> bool:
    """Compatibility hook: current workflow has no immutable support images."""
    return False

def upsert_list_record(records: list[dict[str, Any]], key: str, value: str, payload: dict[str, Any]) -> None:
    for record in records:
        if record.get(key) == value:
            created_at = record.get("created_at")
            record.clear()
            record.update(payload)
            if created_at:
                record["created_at"] = created_at
            return
    records.append(payload)

def upsert_artifact_record(state: dict[str, Any], payload: dict[str, Any]) -> None:
    artifact_id = payload["artifact_id"]
    existing = find_artifact(state, artifact_id)
    if existing is None:
        state.setdefault("artifacts", []).append(payload)
    else:
        created_at = existing.get("created_at")
        existing.clear()
        existing.update(payload)
        if created_at:
            existing["created_at"] = created_at
    refresh_active_artifact_roles(state)

def artifact_role_for_path(step: str | None, relative_path: str | None) -> str | None:
    if not step or not relative_path:
        return None
    rel_path = normalize_relative_path(relative_path)
    for role_id, role in ARTIFACT_ROLES.items():
        if role.get("step") == step and role.get("relative_path") == rel_path:
            return role_id
    return None

def target_image_record_requires_provenance(step: str | None, kind: str, suffix: str) -> bool:
    return bool(step in TARGET_RASTER_IMAGE_STEPS and kind == "image" and suffix in TARGET_RASTER_IMAGE_EXTS)


def find_generation_event(state: dict[str, Any], event_id: str | None) -> dict[str, Any] | None:
    if not event_id:
        return None
    for event in state.get("image_generation_events", []):
        if event.get("event_id") == event_id:
            return event
    return None


def runtime_environment_from_state(state: dict[str, Any] | None) -> str:
    runtime = (state or {}).get("runtime_environment", {})
    if isinstance(runtime, dict):
        return runtime.get("environment") or "unknown"
    return "unknown"

def is_active_artifact(state: dict[str, Any], artifact: dict[str, Any]) -> bool:
    status = str(artifact.get("status") or "")
    if status in INACTIVE_ARTIFACT_STATUSES:
        return False
    if artifact.get("availability") == "file_deleted":
        return False
    step = artifact.get("step")
    if step and artifact.get("step_epoch") is not None:
        try:
            if int(artifact.get("step_epoch") or 0) < current_step_epoch(state, step):
                return False
        except (TypeError, ValueError):
            return False
    return True

def refresh_active_artifact_roles(state: dict[str, Any]) -> None:
    active_roles: dict[str, str] = {}
    for artifact in state.get("artifacts", []):
        role_id = artifact.get("artifact_role") or artifact_role_for_path(
            artifact.get("step"), artifact.get("relative_path")
        )
        if role_id and is_active_artifact(state, artifact):
            active_roles[role_id] = artifact.get("artifact_id", "")
    state["active_artifact_roles"] = {role: artifact_id for role, artifact_id in active_roles.items() if artifact_id}

def artifact_record(
    args: Any,
    run_dir: Path,
    existing: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rel_path = normalize_relative_path(args.path)
    abs_path = safe_join(run_dir, rel_path)
    now = utc_now()
    artifact_role = (
        getattr(args, "artifact_role", None)
        or (existing or {}).get("artifact_role")
        or artifact_role_for_path(args.step, rel_path)
    )
    suffix = Path(rel_path).suffix.lower()
    kind = str(args.kind or "").lower()
    if artifact_role in TARGET_RASTER_REFERENCE_ROLES:
        if kind != "image" or suffix not in TARGET_RASTER_IMAGE_EXTS:
            raise StateError(
                f"{artifact_role} must be a generated raster image artifact "
                f"({', '.join(sorted(TARGET_RASTER_IMAGE_EXTS))}); got kind={args.kind!r}, path={rel_path!r}"
            )
    if args.step in TARGET_RASTER_IMAGE_STEPS:
        if kind in FORBIDDEN_TARGET_IMAGE_KINDS or suffix in FORBIDDEN_TARGET_IMAGE_EXTS:
            raise StateError(
                f"{args.step} target-paper images must be generated raster images; "
                "SVG/HTML/Mermaid/canvas/PPT/PDF/code-drawn and programmatic-raster substitutes are invalid."
            )
    source_roles = sorted(set(getattr(args, "source_artifact_role", []) or []))
    generation_event_id = getattr(args, "generation_event_id", None) or (existing or {}).get("image_generation_event_id")
    if state is not None and target_image_record_requires_provenance(args.step, kind, suffix):
        if not source_roles:
            event = find_generation_event(state, generation_event_id)
            if event is None:
                raise StateError(
                    f"{args.step} target-paper image artifacts require image-generation provenance. "
                    "Use record-image-generation with the environment-locked route first, then pass --generation-event-id; "
                    "or, for registered image mirroring only, cite a registered source artifact role."
                )
            validate_image_generation_route(
                environment=event.get("environment") or runtime_environment_from_state(state),
                generator=event.get("generator"),
                approved_api_name=event.get("approved_api_name"),
                route_unavailable_reason=event.get("route_unavailable_reason"),
            )
    step_epoch = (existing or {}).get("step_epoch")
    if state is not None:
        step_epoch = current_step_epoch(state, args.step)
    if step_epoch is None:
        step_epoch = 0
    record = dict(existing or {})
    record.update(
        {
            "artifact_id": args.artifact_id,
            "step": args.step,
            "kind": args.kind,
            "relative_path": rel_path,
            "artifact_role": artifact_role,
            "step_epoch": int(step_epoch),
            "attempt_id": step_attempt_id(args.step, int(step_epoch)),
            "summary": args.summary or "",
            "tags": sorted(set(args.tag or [])),
            "status": args.status,
            "updated_at": now,
            "content_hash": sha256_file(abs_path),
            "source_user_request": args.source_user_request or "",
        }
    )
    if generation_event_id:
        record["image_generation_event_id"] = generation_event_id
    if source_roles:
        record["source_artifact_roles"] = source_roles
    elif "source_artifact_roles" not in record:
        record["source_artifact_roles"] = []
    record.setdefault("created_at", now)
    return record

def refresh_pending_outputs(state: dict[str, Any]) -> None:
    active_paths = {
        artifact.get("relative_path")
        for artifact in state.get("artifacts", [])
        if is_active_artifact(state, artifact)
    }
    state["pending_outputs"] = [row for row in PENDING_CANONICAL_OUTPUTS if row["relative_path"] not in active_paths]
    refresh_active_artifact_roles(state)




