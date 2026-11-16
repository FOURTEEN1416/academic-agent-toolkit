"""Explicit review presentation metadata; no I/O or task-state transitions.

The application retains reviewer authentication and command/event authority.
Legacy zero-finding reviews deliberately remain without a decision or report.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping


def review_event_metadata(payload: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    """Validate optional v1.1 fields and freeze their association for an event.

    The caller maps ValueError to its existing validation_failed domain error.
    Call for v1.1 submissions only; the older event schema remains unchanged.
    """
    metadata: dict[str, Any] = {}
    if "decision" in payload:
        if payload["decision"] not in ("pass", "block"):
            raise ValueError("Review decision must be pass or block.")
        metadata["decision"] = payload["decision"]
    if "report_artifact_id" in payload:
        report_id = payload["report_artifact_id"]
        if not isinstance(report_id, str) or not report_id:
            raise ValueError("Review report must name a published artifact in this task.")
        report = next((a for a in current.get("artifacts", []) if a.get("artifact_id") == report_id), None)
        if not report or report.get("stale") or report.get("historical") or report.get("freshness") in ("stale", "historical"):
            raise ValueError("Review report must reference a current published artifact in this task.")
        digest = report.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Review report has no recorded SHA-256 version.")
        metadata.update(report_artifact_id=report_id, report_sha256=digest)
    reviewed_ids = set(payload.get("reviewed_artifact_ids", []))
    artifacts = {a['artifact_id']: a for a in current.get('artifacts', [])}
    invalid = sorted(aid for aid in reviewed_ids if aid not in artifacts
        or artifacts[aid].get('stale') or artifacts[aid].get('historical')
        or artifacts[aid].get('freshness') in ('stale', 'historical')
        or not isinstance(artifacts[aid].get('sha256'), str)
        or not re.fullmatch(r'[a-f0-9]{64}', artifacts[aid]['sha256']))
    if invalid:
        raise ValueError('Review requires current published artifact hashes: ' + ', '.join(invalid))
    hashes = {aid: artifacts[aid]['sha256'] for aid in sorted(reviewed_ids)}
    if 'reviewed_hashes' in payload and payload['reviewed_hashes'] != hashes:
        supplied = payload['reviewed_hashes']
        mismatched = sorted(aid for aid in reviewed_ids
                            if not isinstance(supplied, Mapping) or supplied.get(aid) != hashes[aid])
        raise ValueError('Reviewed hashes must match exactly the listed current artifacts: '
                         + ', '.join(mismatched or sorted(reviewed_ids))
                         + '. Inspect their current bytes and retry in this task.')
    metadata['reviewed_hashes'] = hashes
    version = current.get("task_version")
    if type(version) is int and version >= 0:
        metadata["reviewed_task_version"] = version
    return metadata


def project_review_record(event: Mapping[str, Any], artifacts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Project an accepted review event, preserving only explicit new metadata.

    This replaces the existing review-dictionary construction in apply_event.
    New events freeze hashes at acceptance. Legacy events without hashes use
    the artifacts visible immediately before that event, never a later head.
    It never infers PASS, reads a report, or creates a missing report association.
    """
    payload = event["payload"]
    reviewed_ids = list(payload.get("reviewed_artifact_ids", []))
    record = {
        "review_id": payload["review_id"],
        "reviewed_artifact_ids": reviewed_ids,
        "reviewer_id": payload.get("reviewer_id"),
        "finding_ids": list(payload["finding_ids"]),
        "reviewed_hashes": (dict(payload['reviewed_hashes']) if 'reviewed_hashes' in payload else
                            {a["artifact_id"]: a["sha256"] for a in artifacts if a["artifact_id"] in reviewed_ids}),
    }
    for key in ("decision", "report_artifact_id", "report_sha256", "reviewed_task_version"):
        if key in payload:
            record[key] = payload[key]
    if event.get("occurred_at"):
        record["submitted_at"] = event["occurred_at"]
    return record
