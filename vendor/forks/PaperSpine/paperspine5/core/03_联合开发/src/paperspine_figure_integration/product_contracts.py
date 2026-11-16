"""Product-kernel contracts shared by every PaperSpine5 host surface.

The product contracts deliberately sit beside, rather than replace, the legacy
figure-integration contracts.  A task may point at a legacy 1.0 job, but hosts
must use these contracts for new mutations.
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .contracts import ContractError


PRODUCT_SCHEMA_VERSION = "1.0"
PRODUCT_ID = "paperspine5"
TASK_STATUSES = {
    "created",
    "active",
    "blocked",
    "completed",
    "archived",
}
HOST_SURFACES = {"codex", "claude-code", "dsh", "standalone-skill", "web", "mcp", "cli", "system"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
COMMAND_TYPE = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{field} must be an object")
    return deepcopy(value)


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")
    return value.strip()


def _safe_id(value: Any, field: str) -> str:
    result = _required_text(value, field)
    if not SAFE_ID.fullmatch(result):
        raise ContractError(f"{field} must be a safe identifier")
    return result


def task_scoped_artifact_receipt_id(
    *,
    task_id: str,
    revision_id: int | str,
    artifact_id: str,
    artifact_type: str,
    content_sha256: str,
) -> str:
    """Build a deterministic globally unique receipt identity for one task.

    The artifact ledger is shared by all tasks and keys receipts globally.  A
    receipt therefore cannot be named only by artifact/revision/content: two
    tasks may intentionally register the same bytes at the same local
    revision.  The opaque hashes keep the identifier within the 128-character
    public contract while binding its full task and artifact authority.
    """

    normalized_task_id = _safe_id(task_id, "artifact_receipt.task_scope")
    normalized_artifact_id = _safe_id(
        artifact_id, "artifact_receipt.artifact_scope"
    )
    normalized_artifact_type = _required_text(
        artifact_type, "artifact_receipt.artifact_type_scope"
    )
    if not COMMAND_TYPE.fullmatch(normalized_artifact_type):
        raise ContractError(
            "artifact_receipt.artifact_type_scope must be a lower-case "
            "namespaced identifier"
        )
    normalized_revision = str(revision_id)
    if not normalized_revision.isdigit():
        raise ContractError(
            "artifact_receipt.revision_scope must be a non-negative integer"
        )
    normalized_digest = _required_text(
        content_sha256, "artifact_receipt.content_sha256_scope"
    ).lower()
    if not SHA256.fullmatch(normalized_digest):
        raise ContractError(
            "artifact_receipt.content_sha256_scope must be a lower-case SHA-256 digest"
        )
    task_scope = hashlib.sha256(normalized_task_id.encode("utf-8")).hexdigest()[:20]
    semantic_identity = hashlib.sha256(
        "\x00".join(
            (
                "paperspine5.task-scoped-artifact-receipt.v1",
                normalized_task_id,
                normalized_revision,
                normalized_artifact_id,
                normalized_artifact_type,
                normalized_digest,
            )
        ).encode("utf-8")
    ).hexdigest()
    return f"artifact-t{task_scope}-{semantic_identity}"


def validate_product_manifest(raw: dict[str, Any], *, core_root: Path | None = None) -> dict[str, Any]:
    value = _object(raw, "product_manifest")
    if value.get("contract") != "paperspine5.product-manifest":
        raise ContractError("product_manifest.contract must be paperspine5.product-manifest")
    if value.get("schema_version") != PRODUCT_SCHEMA_VERSION:
        raise ContractError(f"product_manifest.schema_version must be {PRODUCT_SCHEMA_VERSION}")
    if value.get("product_id") != PRODUCT_ID:
        raise ContractError(f"product_manifest.product_id must be {PRODUCT_ID}")
    product_version = _required_text(value.get("product_version"), "product_manifest.product_version")
    channel = _required_text(value.get("channel"), "product_manifest.channel")
    build_id = _safe_id(value.get("build_id"), "product_manifest.build_id")
    declared_root = Path(_required_text(value.get("core_root"), "product_manifest.core_root")).resolve()
    if not declared_root.is_dir():
        raise ContractError(f"product_manifest.core_root does not exist: {declared_root}")
    if core_root is not None and declared_root != core_root.resolve():
        raise ContractError("product_manifest.core_root does not match ProductKernel core_root")
    components = _object(value.get("component_versions", {}), "product_manifest.component_versions")
    if any(not isinstance(key, str) or not key or not isinstance(item, str) or not item for key, item in components.items()):
        raise ContractError("product_manifest.component_versions must map non-empty strings to non-empty strings")
    compatibility = _object(value.get("compatibility", {}), "product_manifest.compatibility")
    return {
        **value,
        "contract": "paperspine5.product-manifest",
        "schema_version": PRODUCT_SCHEMA_VERSION,
        "product_id": PRODUCT_ID,
        "product_version": product_version,
        "channel": channel,
        "build_id": build_id,
        "core_root": str(declared_root),
        "component_versions": components,
        "compatibility": compatibility,
    }


def validate_command_envelope(raw: dict[str, Any], *, task_id: str | None = None) -> dict[str, Any]:
    value = _object(raw, "command")
    if value.get("contract") != "paperspine5.command-envelope":
        raise ContractError("command.contract must be paperspine5.command-envelope")
    if value.get("schema_version") != PRODUCT_SCHEMA_VERSION:
        raise ContractError(f"command.schema_version must be {PRODUCT_SCHEMA_VERSION}")
    command_id = _safe_id(value.get("command_id"), "command.command_id")
    declared_task = _safe_id(value.get("task_id", task_id), "command.task_id")
    if task_id is not None and declared_task != task_id:
        raise ContractError("command.task_id does not match the selected task")
    expected_revision = value.get("expected_revision")
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
        raise ContractError("command.expected_revision must be a non-negative integer")
    writer_id = _safe_id(value.get("writer_id"), "command.writer_id")
    command_type = _required_text(value.get("command_type"), "command.command_type")
    if not COMMAND_TYPE.fullmatch(command_type):
        raise ContractError("command.command_type must be a lower-case namespaced identifier")
    payload = _object(value.get("payload", {}), "command.payload")
    actor = _object(value.get("actor"), "command.actor")
    actor_id = _safe_id(actor.get("actor_id"), "command.actor.actor_id")
    surface = actor.get("surface")
    if surface not in HOST_SURFACES:
        raise ContractError(f"command.actor.surface must be one of {sorted(HOST_SURFACES)}")
    return {
        **value,
        "contract": "paperspine5.command-envelope",
        "schema_version": PRODUCT_SCHEMA_VERSION,
        "command_id": command_id,
        "task_id": declared_task,
        "expected_revision": expected_revision,
        "writer_id": writer_id,
        "command_type": command_type,
        "payload": payload,
        "actor": {**actor, "actor_id": actor_id, "surface": surface},
    }


def validate_artifact_receipt(raw: dict[str, Any], *, task_id: str, revision: int) -> dict[str, Any]:
    value = _object(raw, "artifact_receipt")
    if value.get("contract") != "paperspine5.artifact-receipt":
        raise ContractError("artifact_receipt.contract must be paperspine5.artifact-receipt")
    if value.get("schema_version") != PRODUCT_SCHEMA_VERSION:
        raise ContractError(f"artifact_receipt.schema_version must be {PRODUCT_SCHEMA_VERSION}")
    receipt_id = _safe_id(value.get("receipt_id"), "artifact_receipt.receipt_id")
    artifact_id = _safe_id(value.get("artifact_id"), "artifact_receipt.artifact_id")
    artifact_type = _required_text(value.get("artifact_type"), "artifact_receipt.artifact_type")
    if not COMMAND_TYPE.fullmatch(artifact_type):
        raise ContractError("artifact_receipt.artifact_type must be a lower-case namespaced identifier")
    path = _required_text(value.get("path"), "artifact_receipt.path")
    digest = _required_text(value.get("sha256"), "artifact_receipt.sha256").lower()
    if not SHA256.fullmatch(digest):
        raise ContractError("artifact_receipt.sha256 must be a lower-case SHA-256 digest")
    size_bytes = value.get("size_bytes")
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        raise ContractError("artifact_receipt.size_bytes must be a non-negative integer")
    subject = _object(value.get("subject"), "artifact_receipt.subject")
    if subject.get("task_id") != task_id:
        raise ContractError("artifact_receipt.subject.task_id does not match the selected task")
    revision_id = subject.get("revision_id")
    if str(revision_id) != str(revision):
        raise ContractError("artifact_receipt.subject.revision_id does not match expected_revision")
    input_hashes = subject.get("input_hashes")
    if (
        not isinstance(input_hashes, dict)
        or not input_hashes
        or any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(item, str)
            or not SHA256.fullmatch(item.lower())
            for key, item in input_hashes.items()
        )
    ):
        raise ContractError(
            "artifact_receipt.subject.input_hashes must be a non-empty artifact-id to SHA-256 mapping"
        )
    authority = _object(value.get("authority"), "artifact_receipt.authority")
    if not authority.get("kind") or not authority.get("producer_id"):
        raise ContractError("artifact_receipt.authority requires kind and producer_id")
    if artifact_type.startswith("quality.") and value.get("external_action_authorized") is True:
        raise ContractError("quality receipts cannot authorize external actions")
    metadata = _object(value.get("metadata", {}), "artifact_receipt.metadata")
    return {
        **value,
        "contract": "paperspine5.artifact-receipt",
        "schema_version": PRODUCT_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "path": path,
        "sha256": digest,
        "size_bytes": size_bytes,
        "subject": {
            **subject,
            "task_id": task_id,
            "revision_id": str(revision_id),
            "input_hashes": {key: item.lower() for key, item in input_hashes.items()},
        },
        "authority": authority,
        "metadata": metadata,
    }
