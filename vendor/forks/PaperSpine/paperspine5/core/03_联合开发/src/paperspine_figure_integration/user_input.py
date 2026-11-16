"""Persistent, host-neutral needs-user-input issue helpers."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ContractError, resolve_within, write_json_atomic


ISSUE_ACTIONS = {"answer", "acknowledge", "provide_material", "retry"}
ISSUE_SOURCES = {"codex", "claude-code", "dsh", "standalone-skill", "ui", "user"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def issue_fingerprint(
    *, question: str, details: str, missing_fields: list[str], missing_materials: list[str], blocked_stage: str
) -> str:
    encoded = json.dumps(
        {
            "question": question,
            "details": details,
            "missing_fields": missing_fields,
            "missing_materials": missing_materials,
            "blocked_stage": blocked_stage,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_issue(
    *,
    issue_id: str,
    question: str,
    details: str,
    missing_fields: list[str],
    missing_materials: list[str],
    allowed_actions: list[str],
    blocked_stage: str,
    resume_state: dict[str, Any],
) -> dict[str, Any]:
    if not question.strip() or not details.strip():
        raise ContractError("needs_user_input question and details must be non-empty")
    if not allowed_actions or any(action not in ISSUE_ACTIONS for action in allowed_actions):
        raise ContractError("needs_user_input allowed_actions contains an unsupported action")
    if not missing_fields and not missing_materials and "acknowledge" not in allowed_actions:
        raise ContractError("needs_user_input must declare missing input or permit acknowledgement")
    return {
        "contract": "paperspine5.needs_user_input",
        "version": "1.0",
        "issue_id": issue_id,
        "status": "open",
        "question": question.strip(),
        "details": details.strip(),
        "missing_fields": list(missing_fields),
        "missing_materials": list(missing_materials),
        "allowed_actions": list(dict.fromkeys(allowed_actions)),
        "blocked_stage": blocked_stage,
        "resume": {
            "token": secrets.token_urlsafe(24),
            "state": resume_state,
        },
        "fingerprint": issue_fingerprint(
            question=question,
            details=details,
            missing_fields=missing_fields,
            missing_materials=missing_materials,
            blocked_stage=blocked_stage,
        ),
        "created_at": now(),
    }


def validate_resolution(
    issue: dict[str, Any], raw: dict[str, Any], project_root: Path
) -> dict[str, Any]:
    token = raw.get("resume_token")
    if not isinstance(token, str) or not secrets.compare_digest(token, str(issue.get("resume", {}).get("token", ""))):
        raise ContractError("resume_token is invalid for this issue")
    action = raw.get("action")
    if action not in issue.get("allowed_actions", []):
        raise ContractError("resolution action is not allowed for this issue")
    source = raw.get("source", "user")
    if source not in ISSUE_SOURCES:
        raise ContractError("resolution source is unsupported")
    answer = raw.get("answer", "")
    if not isinstance(answer, str):
        raise ContractError("resolution answer must be text")
    raw_materials = raw.get("materials", [])
    if not isinstance(raw_materials, list) or any(not isinstance(item, str) or not item.strip() for item in raw_materials):
        raise ContractError("resolution materials must be a list of non-empty paths")
    materials: list[str] = []
    for value in raw_materials:
        path = resolve_within(project_root, value.strip(), "resolution.materials", must_exist=True)
        materials.append(str(path))
    if action == "answer" and not answer.strip():
        raise ContractError("answer resolution requires non-empty answer text")
    if action == "provide_material" and not materials:
        raise ContractError("provide_material resolution requires at least one existing project path")
    if action == "acknowledge" and (issue.get("missing_fields") or issue.get("missing_materials")):
        raise ContractError("acknowledgement alone cannot resolve missing fields or materials")
    return {
        "action": action,
        "source": source,
        "answer": answer.strip(),
        "materials": materials,
    }


def write_resolution_receipt(output_dir: Path, issue: dict[str, Any]) -> Path:
    path = output_dir / "user_input" / "issues" / f"{issue['issue_id']}.resolved.json"
    write_json_atomic(path, issue)
    return path
