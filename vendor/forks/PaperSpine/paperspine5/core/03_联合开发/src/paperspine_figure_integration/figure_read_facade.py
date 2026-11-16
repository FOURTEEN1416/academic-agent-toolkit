"""Read-only projection of the legacy figure-reference workspace.

This adapter deliberately never mutates runner state and never infers quality PASS.
It exposes plans, current mappings and freshness so a thin UI can compare real data.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable
import hashlib
import re


def project_figure_read_workspace(
    task_id: str, projector: Callable[..., Any], *, actor: str
) -> dict[str, Any]:
    """Return a safe, JSON-shaped read projection from the legacy projector."""
    raw = projector(task_id, actor=actor)
    if not isinstance(raw, dict):
        raise ValueError("legacy figure workspace is not an object")
    plans = raw.get("plans") if isinstance(raw.get("plans"), list) else []
    mappings = raw.get("final_mappings") if isinstance(raw.get("final_mappings"), list) else []
    out_plans = []
    for item in plans:
        if not isinstance(item, dict):
            continue
        plan = item.get("plan")
        if not isinstance(plan, dict):
            continue
        out_plans.append({
            "artifact_id": item.get("artifact_id"),
            "sha256": item.get("sha256"),
            "revision_id": item.get("revision_id"),
            "plan": deepcopy(plan),
        })
    out_mappings = []
    for item in mappings:
        if not isinstance(item, dict) or not isinstance(item.get("mapping"), dict):
            continue
        out_mappings.append({
            "artifact_id": item.get("artifact_id"),
            "mapping": deepcopy(item["mapping"]),
        })
    return {
        "task_id": task_id,
        "revision": raw.get("revision"),
        "plans": out_plans,
        "final_mappings": out_mappings,
        "external_action_authorized": False,
        "read_only": True,
    }


def resolve_reference_content(
    task_id: str, descriptor_id: str, reader: Callable[..., Any], *, actor: dict[str, Any] | None
) -> dict[str, Any]:
    """Resolve one legacy reference descriptor without exposing filesystem paths."""
    if not isinstance(descriptor_id, str) or re.fullmatch(r"[0-9a-f]{64}", descriptor_id) is None:
        raise ValueError("invalid reference descriptor")
    preview = reader(task_id, descriptor_id, actor=actor)
    if not isinstance(preview, dict) or not isinstance(preview.get("content"), (bytes, bytearray)):
        raise FileNotFoundError("reference preview unavailable")
    body = bytes(preview["content"])
    actual = hashlib.sha256(body).hexdigest()
    declared = preview.get("sha256")
    if declared and actual != declared:
        raise ValueError("reference preview hash mismatch")
    media_type = str(preview.get("media_type") or "application/octet-stream")
    if media_type not in {"image/png", "image/jpeg", "image/svg+xml"}:
        raise ValueError("unsupported reference preview media type")
    return {"descriptor_id": descriptor_id, "sha256": actual, "media_type": media_type,
            "body": body, "bytes_verified": True, "read_only": True}
