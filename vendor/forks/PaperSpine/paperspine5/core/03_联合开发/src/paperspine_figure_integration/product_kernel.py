"""Transactional product kernel for PaperSpine5 tasks.

SQLite is the only mutation authority.  JSON files under a task run are
recoverable projections/compatibility artifacts, never competing state heads.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import threading
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from uuid import uuid4

from .filesystem_paths import native_path
from .contracts import ContractError, load_json, write_json_atomic
from .product_contracts import (
    PRODUCT_SCHEMA_VERSION,
    TASK_STATUSES,
    validate_artifact_receipt,
    validate_command_envelope,
    validate_product_manifest,
)


class TaskNotFoundError(ContractError):
    """The requested task is not present in this user-data registry."""


class RevisionConflictError(ContractError):
    """A command was based on a stale task revision."""


class WriterLeaseError(ContractError):
    """Another writer owns the task lease."""


class IdempotencyConflictError(ContractError):
    """A command id was reused with different bytes or a different task."""


class RepositoryCompatibilityError(ContractError):
    """The database cannot be safely written by this ProductKernel build."""


RegisteredCommandHandler = Callable[
    [dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_description(value: str | None, title: str, *, legacy: bool = False) -> str:
    if value is None:
        return f"迁移的历史任务：{title}" if legacy else f"围绕“{title}”的 PaperSpine 论文任务"
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 1000:
        raise ContractError("description must be a non-empty string of at most 1000 characters")
    return value.strip()


def _same_task_request(stored: str, current: str) -> bool:
    # Additive identity metadata must not break a lost-ACK replay from an old install.
    left, right = json.loads(stored), json.loads(current)
    for request in (left, right):
        if "description" not in request:
            request["description"] = _task_description(None, request["title"],
                legacy=request["contract"] == "paperspine5.import-legacy-job-request")
    return left == right


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with native_path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_link_or_reparse(path: Path) -> bool:
    """Detect POSIX links and Windows junction/reparse points without following them."""
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        status = os.lstat(path)
    except OSError:
        return False
    return bool(getattr(status, "st_file_attributes", 0) & 0x400)


def _filesystem_identity(path: Path) -> dict[str, int]:
    status = os.stat(path, follow_symlinks=False)
    return {
        "st_dev": int(status.st_dev),
        "st_ino": int(status.st_ino),
        "st_mode": int(status.st_mode),
    }


def _resolve_material_root(value: str | Path) -> tuple[Path, Path, dict[str, int]]:
    if isinstance(value, str) and not value.strip():
        raise ContractError("materials root must be a non-empty directory path")
    supplied = Path(value)
    if not supplied.is_absolute():
        supplied = supplied.absolute()
    if _is_link_or_reparse(supplied):
        raise ContractError(f"materials root cannot be a symlink, junction, or reparse point: {supplied}")
    try:
        canonical = supplied.resolve(strict=True)
    except OSError as exc:
        raise ContractError(f"materials root does not exist: {supplied}") from exc
    if not canonical.is_dir():
        raise ContractError(f"materials root is not a directory: {canonical}")
    return supplied, canonical, _filesystem_identity(supplied)


def _validate_grant_root(grant: dict[str, Any]) -> Path:
    root_text = grant.get("root")
    canonical_text = grant.get("canonical_target")
    stored_identity = grant.get("filesystem_identity")
    if not isinstance(root_text, str) or not isinstance(canonical_text, str):
        raise ContractError("material capability grant must freeze root and canonical_target")
    if not isinstance(stored_identity, dict):
        raise ContractError("material capability grant must freeze filesystem_identity")
    root = Path(root_text)
    if not root.is_absolute() or _is_link_or_reparse(root):
        raise ContractError("material capability root drifted or became a link/reparse point; regrant required")
    try:
        current_target = root.resolve(strict=True)
    except OSError as exc:
        raise ContractError("material capability root is unavailable; regrant required") from exc
    canonical = Path(canonical_text)
    if current_target != canonical or not canonical.is_dir():
        raise ContractError("material capability canonical target drifted; regrant required")
    if _filesystem_identity(root) != stored_identity:
        raise ContractError("material capability filesystem identity drifted; regrant required")
    return canonical


def _build_material_grant(path: str | Path, index: int, created_at: str) -> dict[str, Any]:
    root, canonical, identity = _resolve_material_root(path)
    return {
        "contract": "paperspine5.capability-grant",
        "schema_version": "1.1",
        "grant_id": (
            f"material-{index}-{hashlib.sha256(str(canonical).encode('utf-8')).hexdigest()[:12]}"
        ),
        "capability": "materials.read",
        "root": str(root),
        "canonical_target": str(canonical),
        "filesystem_identity": identity,
        "permissions": ["enumerate", "read"],
        "read_only": True,
        "created_at": created_at,
        "revoked_at": None,
    }


def _contains_external_authorization(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            (key == "external_action_authorized" and item is True)
            or _contains_external_authorization(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_external_authorization(item) for item in value)
    return False


def _validate_readiness_payload(
    payload: Any,
    subject_mapping: dict[str, Any],
    trusted_current_artifacts: dict[str, str],
) -> tuple[bool, list[str]]:
    """Delegate readiness authenticity to the quality authority without creating a DB dependency."""
    from .quality_readiness import QualitySubject, validate_readiness_verdict_payload

    try:
        subject = QualitySubject.from_mapping(subject_mapping)
        result = validate_readiness_verdict_payload(
            payload,
            subject,
            trusted_current_artifacts=trusted_current_artifacts,
        )
    except (TypeError, ValueError) as exc:
        return False, [str(exc)]
    return result.ok, [str(item.get("code") or item) for item in result.blockers]


def _verified_receipt_authority_hash(
    receipt: dict[str, Any], artifact_bytes: bytes
) -> str:
    """Return the verified hash a receipt contributes to an authority subject.

    The default is the digest of the recorded bytes. Explicit contract-specific
    projections are accepted only after recomputation from those same bytes.
    A semantic hash does not grant authority: Runner still validates identities,
    frozen figure Master plans, and current subject bindings independently.
    """

    byte_hash = hashlib.sha256(artifact_bytes).hexdigest()
    metadata = receipt.get("metadata")
    # File-byte evidence receipts are JSON manifests whose authority is the
    # separately recorded file digest, not the digest of the manifest itself.
    # Promote that digest only after validating the manifest identity and both
    # redundant byte-hash fields. This keeps the ledger bound to the actual
    # manuscript bytes used by J9/J10 target mappings.
    if not isinstance(metadata, dict) or "semantic_hash_kind" not in metadata:
        try:
            payload = json.loads(artifact_bytes.decode("utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError):
            payload = None
        if (
            isinstance(payload, dict)
            and payload.get("contract") == "paperspine5.local-file-byte-evidence"
            and payload.get("artifact_id") == receipt.get("artifact_id")
            and isinstance(payload.get("sha256"), str)
            and payload.get("sha256") == payload.get("source_bytes_sha256")
            and len(payload["sha256"]) == 64
            and all(character in "0123456789abcdef" for character in payload["sha256"])
        ):
            return payload["sha256"]
        if (
            isinstance(payload, dict)
            and payload.get("contract") == "paperspine5.local-package-archive"
            and payload.get("artifact_id") == receipt.get("artifact_id")
            and isinstance(payload.get("sha256"), str)
            and len(payload["sha256"]) == 64
            and all(character in "0123456789abcdef" for character in payload["sha256"])
        ):
            return payload["sha256"]
    if not isinstance(metadata, dict) or "semantic_hash_kind" not in metadata:
        return byte_hash
    try:
        payload = json.loads(artifact_bytes.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("semantic identity receipt must contain UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ContractError("semantic receipt payload must be an object")
    semantic_kind = metadata.get("semantic_hash_kind")
    if semantic_kind == "identity-provenance-v1":
        from .quality_readiness import identity_provenance_sha256

        semantic_hash = identity_provenance_sha256(payload)
        valid = (
            payload.get("attestation_input_id") == receipt.get("artifact_id")
            and payload.get("provenance_sha256") == semantic_hash
        )
    elif semantic_kind == "figure-reference-plan-v1":
        from .figure_reference_mapping import canonical_sha256

        # Match validate_figure_reference_plan's exact preimage. This projection
        # is not a replacement for its out-of-band Master authority checks.
        semantic_hash = canonical_sha256(
            {key: value for key, value in payload.items() if key != "plan_sha256"}
        )
        valid = (
            payload.get("contract") == "paperspine5.figure-reference-plan"
            and payload.get("schema_version") == "1.0"
            and payload.get("external_action_authorized") is False
            and payload.get("plan_sha256") == semantic_hash
        )
    elif semantic_kind == "figure-candidate-input-manifest-v1":
        from .figure_reference_mapping import canonical_sha256

        semantic_hash = canonical_sha256(payload)
        candidate_id = payload.get("artifact_id", "")
        valid = (
            receipt.get("artifact_type") == "runner.academic-base-input"
            and payload.get("contract") == "paperspine5.figure-candidate-asset"
            and payload.get("schema_version") == "1.0"
            and payload.get("external_action_authorized") is False
            and isinstance(candidate_id, str) and candidate_id.startswith("figure-candidate.")
            and metadata.get("semantic_artifact_id") == candidate_id
            and receipt.get("artifact_id") == "figure-candidate-input."
            + hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:32]
        )
    elif semantic_kind == "figure-final-mapping-v1":
        from .figure_final_mapping import validate_envelope

        validated = validate_envelope(payload)
        semantic_hash = validated["mapping"]["mapping_sha256"]
        valid = (
            receipt.get("artifact_type") == "figure.final-mapping"
            and metadata.get("consumption_sha256") == validated["consumption_sha256"]
            and str(receipt.get("subject", {}).get("revision_id"))
            == validated["consumption_subject"]["revision_id"]
            and receipt.get("subject", {}).get("task_id") == validated["consumption_subject"]["task_id"]
            and metadata.get("product_build_id") == validated["validation_build_id"]
        )
    elif semantic_kind == "readiness-obligation-manifest-v1":
        from .quality_readiness import canonical_sha256

        semantic_hash = canonical_sha256(
            {key: value for key, value in payload.items() if key != "manifest_sha256"}
        )
        valid = (
            receipt.get("artifact_id") == "readiness_obligations"
            and payload.get("contract")
            == "paperspine5.readiness-obligation-manifest"
            and payload.get("manifest_sha256") == semantic_hash
        )
    elif semantic_kind == "material-ledger-snapshot-v1":
        entries = payload.get("entries")
        if not isinstance(entries, list) or any(
            not isinstance(item, dict) for item in entries
        ):
            raise ContractError("material ledger semantic receipt entries are invalid")
        stable_entries = sorted(
            (
                {
                    "source_id": item.get("source_id"),
                    "grant_id": item.get("grant_id"),
                    "relative_path": item.get("relative_path"),
                    "sha256": item.get("sha256"),
                    "size_bytes": item.get("size_bytes"),
                }
                for item in entries
            ),
            key=lambda item: (str(item["grant_id"]), str(item["relative_path"])),
        )
        semantic_hash = hashlib.sha256(
            (_canonical_json(stable_entries) + "\n").encode("utf-8")
        ).hexdigest()
        valid = (
            receipt.get("artifact_id") == "materials.source-ledger"
            and payload.get("contract") == "paperspine5.material-source-ledger"
            and payload.get("snapshot_sha256") == semantic_hash
        )
    elif semantic_kind == "run-contract-authority-v1":
        stable_contract = {
            "contract": payload.get("contract"),
            "schema_version": payload.get("schema_version"),
            "product_build_id": payload.get("product_build_id"),
            "material_snapshot_sha256": payload.get("material_snapshot_sha256"),
            "configuration": payload.get("configuration"),
            "external_action_authorized": payload.get("external_action_authorized"),
        }
        semantic_hash = hashlib.sha256(
            (_canonical_json(stable_contract) + "\n").encode("utf-8")
        ).hexdigest()
        valid = (
            receipt.get("artifact_id") == "runner.run-contract"
            and payload.get("contract") == "paperspine5.run-contract"
            and payload.get("external_action_authorized") is False
        )
    else:
        raise ContractError("artifact receipt declares an unsupported semantic hash kind")
    if not valid or metadata.get("semantic_sha256") != semantic_hash:
        raise ContractError("semantic receipt does not recompute from recorded bytes")
    return semantic_hash


def _candidate_readiness_authority(trusted: dict[str, str], verified: list[tuple[dict[str, Any], bytes]], *, strict: bool = True) -> None:
    """Resolve candidate JSON authority only with its exact independently read PNG.

    The normal artifact list retains binary hashes. Academic/quality subjects
    consume the candidate input manifest, not a claim that PNG bytes equal JSON.
    """
    binaries = {r["artifact_id"]: (r, data) for r, data in verified if r["artifact_type"] == "figure.candidate-image"}
    for receipt, content in verified:
        metadata = receipt.get("metadata", {})
        if metadata.get("semantic_hash_kind") != "figure-candidate-input-manifest-v1":
            continue
        semantic = _verified_receipt_authority_hash(receipt, content)
        manifest = json.loads(content)
        candidate_id = manifest["artifact_id"]
        binary, binary_bytes = binaries.get(candidate_id, (None, b""))
        manifest_plan = manifest.get("reference_plan") if isinstance(manifest, dict) else None
        binary_metadata = binary.get("metadata", {}) if isinstance(binary, dict) else {}
        semantic_alias_ok = (
            binary is not None
            and isinstance(manifest, dict)
            and isinstance(manifest_plan, dict)
            and manifest.get("external_action_authorized") is False
            and binary_metadata.get("figure_id") == manifest.get("figure_id")
            and binary_metadata.get("reference_plan_artifact_id") == manifest_plan.get("artifact_id")
            and binary_metadata.get("reference_plan_sha256") == manifest_plan.get("sha256")
            and binary_metadata.get("material_snapshot_sha256") == manifest.get("material_snapshot_sha256")
        )
        if (binary is None
                or binary["subject"]["task_id"] != receipt["subject"]["task_id"]
                or binary["subject"]["revision_id"] != receipt["subject"]["revision_id"]
                or binary["sha256"] != manifest.get("sha256")
                or hashlib.sha256(binary_bytes).hexdigest() != binary["sha256"]
                or len(binary_bytes) != binary["size_bytes"]
                or binary["size_bytes"] != manifest.get("size_bytes")
                or (
                    binary_metadata.get("input_artifact_sha256") != semantic
                    and not semantic_alias_ok
                )
                or binary.get("metadata", {}).get("media_type") != manifest.get("media_type")):
            if strict:
                raise ContractError(
                    "candidate readiness authority requires exact manifest/binary evidence: "
                    + str(candidate_id)
                )
            # Preserve an already-recorded alias for historical candidates.
            # The current candidate remains subject to the strict checks above;
            # this fallback only prevents an old retry from erasing a valid
            # subject binding used by the package readiness receipt.
            trusted.setdefault(candidate_id, semantic)
            continue
        trusted[candidate_id] = semantic


def _verified_receipt_authority_projections(
    receipt: dict[str, Any], artifact_bytes: bytes
) -> dict[str, str]:
    """Project strictly known semantic IDs from one verified receipt payload."""

    projections = {
        str(receipt["artifact_id"]): _verified_receipt_authority_hash(
            receipt, artifact_bytes
        )
    }
    try:
        payload = json.loads(artifact_bytes.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError):
        return projections
    if not isinstance(payload, dict):
        return projections
    from .quality_readiness import canonical_sha256

    artifact_id = receipt.get("artifact_id")

    def add(projection_id: str, value: Any) -> None:
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ContractError(
                f"verified receipt projection {projection_id} is not a SHA-256 digest"
            )
        previous = projections.get(projection_id)
        if previous is not None and previous != value:
            raise ContractError(
                f"verified receipt projection {projection_id} conflicts within one receipt"
            )
        projections[projection_id] = value

    if artifact_id == "materials.source-ledger":
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise ContractError("verified material ledger entries are invalid")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(
                entry.get("source_id"), str
            ):
                raise ContractError("verified material ledger source identity is invalid")
            add(f"source:{entry['source_id']}", entry.get("sha256"))

    if artifact_id in {"direction_authority", "target_authority"}:
        if artifact_id == "direction_authority":
            add("research_scope", payload.get("research_scope_sha256"))
        add("target_research_snapshot", payload.get("research_snapshot_sha256"))
    elif artifact_id == "publication.manuscript-head":
        add("canonical_head", payload.get("head_sha256"))
    elif artifact_id == "publication.review-closure":
        add("final_claim_index", payload.get("final_claim_index_sha256"))
        add("review_closure", payload.get("closure_sha256"))
    elif artifact_id == "publication.target-package":
        add("target_package", payload.get("manifest_sha256"))
    elif artifact_id in {"surface_pdf", "surface_word"}:
        supplied = payload.get("receipt_sha256")
        expected = canonical_sha256(
            {key: value for key, value in payload.items() if key != "receipt_sha256"}
        )
        if supplied != expected:
            raise ContractError("surface receipt semantic hash does not recompute")
        projections[str(artifact_id)] = expected
    elif artifact_id == "target_obligations":
        supplied = payload.get("ledger_sha256")
        expected = canonical_sha256(
            {key: value for key, value in payload.items() if key != "ledger_sha256"}
        )
        if supplied != expected:
            raise ContractError("target obligation semantic hash does not recompute")
        projections["target_obligations"] = expected
    elif artifact_id == "author_close":
        items = payload.get("items")
        expected = canonical_sha256(items)
        if not isinstance(items, list) or payload.get("author_close_sha256") != expected:
            raise ContractError("author close semantic hash does not recompute")
        projections["author_close"] = expected
    elif payload.get("contract") == "paperspine5.figure-correction-receipt":
        from .figure_correction import (
            FigureCorrectionError,
            validate_figure_correction_receipt,
        )

        try:
            validated = validate_figure_correction_receipt(payload)
        except FigureCorrectionError as exc:
            raise ContractError(
                "figure correction receipt semantic hash does not recompute"
            ) from exc
        projections[str(artifact_id)] = str(validated["receipt_sha256"])
        add(
            f"figure-output.{validated['figure_id']}",
            validated["output"]["sha256"],
        )
    elif payload.get("contract") == "paperspine5.target-size-legibility-receipt":
        from .figure_correction import (
            FigureCorrectionError,
            validate_target_size_legibility_receipt,
        )

        try:
            validated = validate_target_size_legibility_receipt(
                payload, require_pass=True
            )
        except FigureCorrectionError as exc:
            raise ContractError(
                "target-size legibility receipt semantic hash does not recompute"
            ) from exc
        projections[str(artifact_id)] = str(validated["receipt_sha256"])
    return projections


def _assert_separate_roots(core_root: Path, user_data_root: Path, materials_roots: list[Path]) -> None:
    roots = [("core_root", core_root), ("user_data_root", user_data_root)] + [
        (f"materials_roots[{index}]", root) for index, root in enumerate(materials_roots)
    ]
    for index, (left_name, left) in enumerate(roots):
        for right_name, right in roots[index + 1 :]:
            if left == right or _is_relative_to(left, right) or _is_relative_to(right, left):
                raise ContractError(f"{left_name} and {right_name} must be non-overlapping capability roots")


class SQLiteProductStore:
    """Low-level SQLite/WAL repository shared by task and state facades."""

    PRODUCT_ID = "paperspine5"
    SCHEMA_VERSION = "1.2"
    MIN_READER_VERSION = "1.2"
    MAX_READER_VERSION = "1.2"
    WRITER_VERSION = "1.2"

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            existing_tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
            if existing_tables and "schema_meta" not in existing_tables:
                raise RepositoryCompatibilityError(
                    "unversioned repository contains tables; pre-migration snapshot is required before opening"
                )
            if "schema_meta" in existing_tables:
                try:
                    preflight = connection.execute("SELECT * FROM schema_meta WHERE singleton=1").fetchone()
                except sqlite3.DatabaseError as exc:
                    raise RepositoryCompatibilityError("repository schema metadata is unreadable") from exc
                if preflight is None:
                    raise RepositoryCompatibilityError("repository schema metadata row is missing")
                if (
                    preflight["product_id"] != self.PRODUCT_ID
                    or preflight["writer_version"] != self.WRITER_VERSION
                    or preflight["schema_version"] != self.SCHEMA_VERSION
                    or not (
                        preflight["min_reader_version"]
                        <= self.SCHEMA_VERSION
                        <= preflight["max_reader_version"]
                    )
                ):
                    raise RepositoryCompatibilityError("repository metadata is incompatible with this writer")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS schema_meta (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    product_id TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    min_reader_version TEXT NOT NULL,
                    max_reader_version TEXT NOT NULL,
                    writer_version TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            try:
                metadata = connection.execute("SELECT * FROM schema_meta WHERE singleton=1").fetchone()
            except sqlite3.DatabaseError as exc:
                raise RepositoryCompatibilityError("repository schema metadata is unreadable") from exc
            if metadata is None:
                connection.execute(
                    "INSERT INTO schema_meta VALUES(1,?,?,?,?,?,?)",
                    (
                        self.PRODUCT_ID,
                        self.SCHEMA_VERSION,
                        self.MIN_READER_VERSION,
                        self.MAX_READER_VERSION,
                        self.WRITER_VERSION,
                        _now(),
                    ),
                )
            else:
                if metadata["product_id"] != self.PRODUCT_ID:
                    raise RepositoryCompatibilityError("repository product_id is not paperspine5")
                if metadata["writer_version"] != self.WRITER_VERSION:
                    raise RepositoryCompatibilityError(
                        f"repository writer_version {metadata['writer_version']} is incompatible with writer {self.WRITER_VERSION}"
                    )
                if metadata["schema_version"] != self.SCHEMA_VERSION:
                    raise RepositoryCompatibilityError(
                        f"repository schema_version {metadata['schema_version']} is unsupported"
                    )
                if not (
                    metadata["min_reader_version"] <= self.SCHEMA_VERSION <= metadata["max_reader_version"]
                ):
                    raise RepositoryCompatibilityError("repository reader compatibility excludes this kernel")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    host TEXT NOT NULL,
                    status TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK(revision >= 0),
                    active_run_id TEXT NOT NULL,
                    core_root TEXT NOT NULL,
                    workspace_root TEXT NOT NULL UNIQUE,
                    run_root TEXT NOT NULL UNIQUE,
                    material_grants_json TEXT NOT NULL,
                    product_manifest_json TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    legacy_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS commands (
                    command_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
                    envelope_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL,
                    revision INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    command_id TEXT,
                    payload_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    task_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    projection_json TEXT NOT NULL,
                    delivered_at TEXT,
                    last_error TEXT,
                    PRIMARY KEY(task_id, sequence),
                    FOREIGN KEY(task_id, sequence) REFERENCES events(task_id, sequence) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    receipt_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
                    subject_revision INTEGER NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(task_id, subject_revision, artifact_id)
                );
                CREATE TABLE IF NOT EXISTS leases (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(task_id) ON DELETE CASCADE,
                    writer_id TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL,
                    expires_at REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS migrations (
                    migration_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
                    receipt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_by_task ON events(task_id, sequence);
                CREATE INDEX IF NOT EXISTS artifacts_by_task ON artifacts(task_id, artifact_type, subject_revision);
                """
            )
            connection.execute("BEGIN IMMEDIATE")
            try:
                task_columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
                if "description" not in task_columns:
                    connection.execute("ALTER TABLE tasks ADD COLUMN description TEXT NOT NULL DEFAULT ''")
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @contextmanager
    def write_transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()


class TaskRegistry:
    """Task identity/read facade; mutation remains owned by ProductKernel."""

    def __init__(self, store: SQLiteProductStore) -> None:
        self.store = store

    def get(self, task_id: str) -> dict[str, Any]:
        with self.store.read_connection() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFoundError(f"task does not exist: {task_id}")
        return _task_record(row)

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is not None and status not in TASK_STATUSES:
            raise ContractError(f"unsupported task status: {status}")
        query = "SELECT * FROM tasks"
        params: tuple[Any, ...] = ()
        if status is not None:
            query += " WHERE status=?"
            params = (status,)
        query += " ORDER BY updated_at DESC, task_id"
        with self.store.read_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_task_record(row) for row in rows]


class StateRepository:
    """Read facade for the monotonic task/event state."""

    def __init__(self, store: SQLiteProductStore) -> None:
        self.store = store

    def read_events(self, task_id: str, *, after_sequence: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        if isinstance(after_sequence, bool) or not isinstance(after_sequence, int) or after_sequence < 0:
            raise ContractError("after_sequence must be a non-negative integer")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ContractError("limit must be between 1 and 1000")
        with self.store.read_connection() as connection:
            exists = connection.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if exists is None:
                raise TaskNotFoundError(f"task does not exist: {task_id}")
            rows = connection.execute(
                "SELECT * FROM events WHERE task_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                (task_id, after_sequence, limit),
            ).fetchall()
        return [_event_record(row) for row in rows]


def _task_record(row: sqlite3.Row) -> dict[str, Any]:
    run_root = Path(row["run_root"])
    return {
        "contract": "paperspine5.task-record",
        "schema_version": PRODUCT_SCHEMA_VERSION,
        "task_id": row["task_id"],
        "title": row["title"],
        "description": row["description"] or f"围绕“{row['title']}”的 PaperSpine 论文任务",
        "host": row["host"],
        "status": row["status"],
        "revision": row["revision"],
        "active_run_id": row["active_run_id"],
        "core_root": row["core_root"],
        "workspace_root": row["workspace_root"],
        "run_root": row["run_root"],
        "material_grants": json.loads(row["material_grants_json"]),
        "product_manifest": json.loads(row["product_manifest_json"]),
        "state": json.loads(row["state_json"]),
        "legacy": json.loads(row["legacy_json"]) if row["legacy_json"] else None,
        "migration_status": (
            json.loads(row["legacy_json"]).get("migration_status", "registered_read_only")
            if row["legacy_json"]
            else "not_applicable"
        ),
        "job_path": str(run_root / "integration_job.json"),
        "state_path": str(run_root / "integration_state.json"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _event_record(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "contract": "paperspine5.product-event",
        "schema_version": PRODUCT_SCHEMA_VERSION,
        "task_id": row["task_id"],
        "sequence": row["sequence"],
        "revision": row["revision"],
        "event_type": row["event_type"],
        "command_id": row["command_id"],
        "payload": json.loads(row["payload_json"]),
        "occurred_at": row["occurred_at"],
    }


class ProductKernel:
    """Public task/command/artifact API consumed by Web, MCP, CLI and Skills."""

    SUPPORTED_COMMANDS = {"task.rename", "task.set_status", "task.configure"}

    def __init__(
        self,
        user_data_root: str | Path,
        *,
        core_root: str | Path,
        product_manifest: dict[str, Any] | None = None,
        lease_seconds: float = 30.0,
        recover_on_startup: bool = True,
    ) -> None:
        self.user_data_root = Path(user_data_root).resolve()
        self.core_root = Path(core_root).resolve()
        if not self.core_root.is_dir():
            raise ContractError(f"core_root does not exist: {self.core_root}")
        if self.user_data_root == self.core_root or _is_relative_to(self.user_data_root, self.core_root) or _is_relative_to(self.core_root, self.user_data_root):
            raise ContractError("core_root and user_data_root must be separate non-overlapping roots")
        self.user_data_root.mkdir(parents=True, exist_ok=True)
        if lease_seconds <= 0:
            raise ContractError("lease_seconds must be positive")
        self.lease_seconds = float(lease_seconds)
        raw_manifest = product_manifest or {
            "contract": "paperspine5.product-manifest",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "product_id": "paperspine5",
            "product_version": "0.4.0-alpha.1-dev",
            "channel": "development",
            "build_id": "local-dev-unverified",
            "core_root": str(self.core_root),
            "component_versions": {"product_kernel": "0.1.0", "product_runner": "0.2.0"},
            "compatibility": {
                "integration_job_reader": ["1.0", "1.1"],
                "integration_state_reader": ["1.0", "1.1", "1.2", "1.3"],
                "integration_state_writer": "1.3",
                "product_repository_writer": "1.2",
                "artifact_identity": "stable-artifact-id.v1",
                "product_runner_protocol": "1.0",
                "capability_grant_writer": "1.1",
            },
        }
        self.product_manifest = validate_product_manifest(raw_manifest, core_root=self.core_root)
        self.store = SQLiteProductStore(self.user_data_root / "registry" / "product-kernel.sqlite3")
        self.registry = TaskRegistry(self.store)
        self.state_repository = StateRepository(self.store)
        self._registered_command_handlers: dict[
            str, tuple[str, str, RegisteredCommandHandler, str]
        ] = {}
        self._projection_lock = threading.Lock()
        self._closed = False
        if recover_on_startup:
            self.recover_outbox()

    def close(self, *, flush: bool = True) -> None:
        """Flush by default; a pure MCP read can close without outbox effects.

        The store keeps no persistent SQLite handle. Only a process that never
        began normal application initialization uses flush=False.
        """
        if self._closed:
            return
        if flush:
            self.recover_outbox()
        self._closed = True

    def __enter__(self) -> "ProductKernel":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def create_task(
        self,
        *,
        command_id: str,
        materials_roots: list[str | Path] | tuple[str | Path, ...] = (),
        title: str | None = None,
        description: str | None = None,
        host: str = "codex",
        task_id: str | None = None,
    ) -> dict[str, Any]:
        if (
            not isinstance(command_id, str)
            or not command_id
            or len(command_id) > 128
            or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-" for character in command_id)
        ):
            raise ContractError("command_id must be a safe identifier")
        requested_task_id = task_id
        if task_id is not None and (
            not isinstance(task_id, str)
            or not task_id
            or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in task_id)
        ):
            raise ContractError("task_id must use letters, numbers, dots, underscores, or hyphens")
        if title is not None and not isinstance(title, str):
            raise ContractError("title must be a string")
        title = (title or "Untitled PaperSpine5 task").strip()
        if not title:
            raise ContractError("title must be non-empty")
        description = _task_description(description, title)
        if host not in {"codex", "claude-code", "dsh", "standalone-skill"}:
            raise ContractError("host is unsupported")
        resolved_materials: list[Path] = []
        for value in materials_roots:
            _root, canonical, _identity = _resolve_material_root(value)
            if canonical not in resolved_materials:
                resolved_materials.append(canonical)
        _assert_separate_roots(self.core_root, self.user_data_root, resolved_materials)
        create_request = {
            "contract": "paperspine5.create-task-request",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "command_id": command_id,
            "requested_task_id": requested_task_id,
            "title": title,
            "description": description,
            "host": host,
            "materials_roots": [str(path) for path in resolved_materials],
            "product_build_id": self.product_manifest["build_id"],
        }
        canonical_request = _canonical_json(create_request)
        with self.store.read_connection() as connection:
            replay = connection.execute(
                "SELECT task_id,envelope_json FROM commands WHERE command_id=?", (command_id,)
            ).fetchone()
        if replay is not None:
            if not _same_task_request(replay["envelope_json"], canonical_request):
                raise IdempotencyConflictError("create command_id was already used with different inputs")
            return self.get_task(replay["task_id"])

        task_id = task_id or f"task-{uuid4().hex}"
        workspace_root = (self.user_data_root / "tasks" / task_id).resolve()
        run_id = f"run-{uuid4().hex}"
        run_root = workspace_root / "runs" / run_id
        created_at = _now()
        grants = [
            _build_material_grant(path, index + 1, created_at)
            for index, path in enumerate(resolved_materials)
        ]
        state = {"configuration": {}, "last_command": None}
        with self.store.write_transaction() as connection:
            replay = connection.execute(
                "SELECT task_id,envelope_json FROM commands WHERE command_id=?", (command_id,)
            ).fetchone()
            if replay is not None:
                if not _same_task_request(replay["envelope_json"], canonical_request):
                    raise IdempotencyConflictError("create command_id was already used with different inputs")
                replay_task_id = replay["task_id"]
                sequence = None
            else:
                replay_task_id = None
                try:
                    connection.execute(
                        """INSERT INTO tasks (
                        task_id,title,description,host,status,revision,active_run_id,core_root,workspace_root,run_root,
                        material_grants_json,product_manifest_json,state_json,legacy_json,created_at,updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            task_id,
                            title,
                            description,
                            host,
                            "created",
                            0,
                            run_id,
                            str(self.core_root),
                            str(workspace_root),
                            str(run_root),
                            _canonical_json(grants),
                            _canonical_json(self.product_manifest),
                            _canonical_json(state),
                            None,
                            created_at,
                            created_at,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise IdempotencyConflictError("task_id or task paths already exist in the registry") from exc
                sequence = self._append_event(
                    connection,
                    task_id=task_id,
                    revision=0,
                    event_type="task.created",
                    command_id=command_id,
                    payload={"title": title, "description": description, "host": host, "active_run_id": run_id},
                    projections=["bootstrap", "task_record"],
                )
                result = {
                    "contract": "paperspine5.command-result",
                    "schema_version": PRODUCT_SCHEMA_VERSION,
                    "task_id": task_id,
                    "command_id": command_id,
                    "status": "accepted",
                    "previous_revision": None,
                    "resulting_revision": 0,
                    "event_sequence": sequence,
                    "replayed": False,
                }
                connection.execute(
                    "INSERT INTO commands(command_id,task_id,envelope_json,result_json,created_at) VALUES(?,?,?,?,?)",
                    (command_id, task_id, canonical_request, _canonical_json(result), created_at),
                )
        if replay_task_id is not None:
            return self.get_task(replay_task_id)
        assert sequence is not None
        self._drain_outbox(task_id=task_id, up_to_sequence=sequence)
        return self.get_task(task_id)

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        return self.registry.list(status)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.registry.get(task_id)

    def get_command(self, task_id: str, command_id: str) -> dict[str, Any] | None:
        """Read one committed command for adapter/runner lost-ACK recovery."""
        with self.store.read_connection() as connection:
            row = connection.execute(
                "SELECT task_id,envelope_json,result_json,created_at FROM commands WHERE command_id=?",
                (command_id,),
            ).fetchone()
        if row is None:
            return None
        if row["task_id"] != task_id:
            raise IdempotencyConflictError("command_id belongs to another task")
        stored_envelope = json.loads(row["envelope_json"])
        registered_record = (
            stored_envelope
            if stored_envelope.get("contract") == "paperspine5.registered-command-record"
            else None
        )
        return {
            "task_id": task_id,
            "command_id": command_id,
            "envelope": (
                registered_record["command"] if registered_record is not None else stored_envelope
            ),
            "registered_handler": (
                {
                    "handler_id": registered_record["handler_id"],
                    "handler_build_id": registered_record["handler_build_id"],
                    "prepared_sha256": registered_record["prepared_sha256"],
                }
                if registered_record is not None
                else None
            ),
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }

    def list_commands(self, task_id: str) -> list[dict[str, Any]]:
        """Return committed command identities without replaying chat or handlers."""

        self.get_task(task_id)
        with self.store.read_connection() as connection:
            rows = connection.execute(
                "SELECT command_id FROM commands WHERE task_id=? ORDER BY rowid",
                (task_id,),
            ).fetchall()
        commands: list[dict[str, Any]] = []
        for row in rows:
            command = self.get_command(task_id, row["command_id"])
            if command is not None:
                commands.append(command)
        return commands

    def get_migration_receipt(
        self, task_id: str, migration_id: str
    ) -> dict[str, Any] | None:
        """Read one committed migration receipt for audit/lost-ACK recovery."""

        with self.store.read_connection() as connection:
            row = connection.execute(
                "SELECT task_id,receipt_json FROM migrations WHERE migration_id=?",
                (migration_id,),
            ).fetchone()
        if row is None:
            return None
        if row["task_id"] != task_id:
            raise IdempotencyConflictError("migration_id belongs to another task")
        value = json.loads(row["receipt_json"])
        if not isinstance(value, dict):
            raise RepositoryCompatibilityError("migration receipt is unreadable")
        return value

    def resolve_material_path(self, task_id: str, grant_id: str, relative_path: str | Path) -> Path:
        """Resolve a read-only material path without granting broader filesystem access."""
        value = Path(relative_path)
        if value.is_absolute() or ".." in value.parts:
            raise ContractError("material path must be relative and cannot contain parent traversal")
        task = self.get_task(task_id)
        grant = next((item for item in task["material_grants"] if item["grant_id"] == grant_id), None)
        if grant is None or grant.get("revoked_at") is not None or grant.get("read_only") is not True:
            raise ContractError("material capability grant is missing, revoked, or not read-only")
        root = _validate_grant_root(grant)
        resolved = (root / value).resolve()
        if not _is_relative_to(resolved, root):
            raise ContractError("material path escapes the granted root")
        if not resolved.exists() or _is_link_or_reparse(resolved):
            raise ContractError(f"material path does not exist: {resolved}")
        return resolved

    def acquire_writer_lease(self, task_id: str, writer_id: str) -> dict[str, Any]:
        if not writer_id:
            raise ContractError("writer_id must be non-empty")
        with self.store.write_transaction() as connection:
            if connection.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone() is None:
                raise TaskNotFoundError(f"task does not exist: {task_id}")
            token, expires_at = self._acquire_lease(connection, task_id, writer_id)
        return {"task_id": task_id, "writer_id": writer_id, "fencing_token": token, "expires_at": expires_at}

    def release_writer_lease(self, task_id: str, writer_id: str) -> bool:
        with self.store.write_transaction() as connection:
            cursor = connection.execute("DELETE FROM leases WHERE task_id=? AND writer_id=?", (task_id, writer_id))
        return cursor.rowcount == 1

    def register_command_handler(
        self,
        command_type: str,
        *,
        handler_id: str,
        product_build_id: str,
        handler: RegisteredCommandHandler,
    ) -> str:
        """Register one version/build-locked in-process business handler.

        Registration is deliberately ephemeral.  A restarted process must load
        the exact runner implementation again before a ``runner.*`` command can
        mutate state; persisted command names alone never become executable.
        """
        probe = {
            "contract": "paperspine5.command-envelope",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "command_id": "handler-registration-probe",
            "task_id": "handler-registration-probe",
            "expected_revision": 0,
            "writer_id": "handler-registration-probe",
            "command_type": command_type,
            "payload": {},
            "actor": {"actor_id": "product-kernel", "surface": "system"},
        }
        validate_command_envelope(probe)
        if command_type in self.SUPPORTED_COMMANDS:
            raise ContractError(f"built-in command handler cannot be replaced: {command_type}")
        if not isinstance(handler_id, str) or not handler_id.strip():
            raise ContractError("handler_id must be non-empty")
        if product_build_id != self.product_manifest["build_id"]:
            raise RepositoryCompatibilityError(
                "registered handler build does not match the active ProductKernel build"
            )
        if not callable(handler):
            raise ContractError("registered command handler must be callable")
        previous = self._registered_command_handlers.get(command_type)
        if previous is not None:
            raise ContractError(
                f"command_type registration is sealed and cannot be replaced: {command_type}"
            )
        registration = secrets.token_urlsafe(48)
        self._registered_command_handlers[command_type] = (
            handler_id,
            product_build_id,
            handler,
            registration,
        )
        return registration

    def submit_command(self, task_id: str, envelope: dict[str, Any]) -> dict[str, Any]:
        """Submit a public built-in command; registered business commands are engine-owned."""
        return self._submit_command(
            task_id,
            envelope,
            registration=None,
            prepared={},
        )

    def _submit_registered_command(
        self,
        task_id: str,
        envelope: dict[str, Any],
        *,
        registration: str,
        prepared: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one sealed in-process handler with derived data kept out of public payloads."""
        if not isinstance(registration, str) or not registration:
            raise ContractError("registered command requires an opaque engine registration")
        if not isinstance(prepared, dict):
            raise ContractError("registered command prepared data must be an object")
        return self._submit_command(
            task_id,
            envelope,
            registration=registration,
            prepared=prepared,
        )

    def _submit_command(
        self,
        task_id: str,
        envelope: dict[str, Any],
        *,
        registration: str | None,
        prepared: dict[str, Any],
    ) -> dict[str, Any]:
        command = validate_command_envelope(envelope, task_id=task_id)
        registered = self._registered_command_handlers.get(command["command_type"])
        if command["command_type"] not in self.SUPPORTED_COMMANDS and registered is None:
            raise ContractError(
                f"unsupported product command_type: {command['command_type']}; a registered W3 handler is required"
            )
        if registered is not None:
            if registration is None:
                raise ContractError(
                    "registered ProductRunner commands are engine-owned; use the ProductRunner facade"
                )
            handler_id, handler_build_id, _handler, expected_registration = registered
            if not secrets.compare_digest(registration, expected_registration):
                raise ContractError("registered command engine authority does not match")
            stored_command: dict[str, Any] = {
                "contract": "paperspine5.registered-command-record",
                "schema_version": PRODUCT_SCHEMA_VERSION,
                "handler_id": handler_id,
                "handler_build_id": handler_build_id,
                "command": command,
                "prepared_sha256": hashlib.sha256(
                    _canonical_json(prepared).encode("utf-8")
                ).hexdigest(),
            }
        else:
            if registration is not None or prepared:
                raise ContractError("built-in commands cannot carry registered engine authority")
            stored_command = command
        canonical = _canonical_json(stored_command)
        with self.store.write_transaction() as connection:
            replay = connection.execute("SELECT task_id,envelope_json,result_json FROM commands WHERE command_id=?", (command["command_id"],)).fetchone()
            if replay is not None:
                if replay["task_id"] != task_id or replay["envelope_json"] != canonical:
                    raise IdempotencyConflictError("command_id was already used for a different command")
                result = json.loads(replay["result_json"])
                return {**result, "replayed": True}
            row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFoundError(f"task does not exist: {task_id}")
            current_revision = row["revision"]
            if command["expected_revision"] != current_revision:
                raise RevisionConflictError(
                    f"expected_revision {command['expected_revision']} does not match current revision {current_revision}"
                )
            fencing_token, _ = self._acquire_lease(connection, task_id, command["writer_id"])
            state = json.loads(row["state_json"])
            next_title = row["title"]
            next_status = row["status"]
            next_material_grants = json.loads(row["material_grants_json"])
            next_core_root = row["core_root"]
            next_product_manifest = json.loads(row["product_manifest_json"])
            affects_revision = True
            transition_artifacts: list[dict[str, Any]] = []
            transition_result: dict[str, Any] = {}
            transition_event_payload: dict[str, Any] = {}
            transition_migration_receipt: dict[str, Any] | None = None
            handler_id: str | None = None
            if command["command_type"] == "task.rename":
                next_title = command["payload"].get("title")
                if not isinstance(next_title, str) or not next_title.strip():
                    raise ContractError("task.rename payload.title must be non-empty")
                next_title = next_title.strip()
            elif command["command_type"] == "task.set_status":
                next_status = command["payload"].get("status")
                if next_status not in TASK_STATUSES:
                    raise ContractError("task.set_status payload.status is unsupported")
                if next_status == "completed":
                    raise ContractError(
                        "task completed is reserved for a registered W3 completion handler with fresh readiness evidence"
                    )
            elif command["command_type"] == "task.configure":
                configuration = command["payload"].get("configuration")
                if not isinstance(configuration, dict):
                    raise ContractError("task.configure payload.configuration must be an object")
                state["configuration"] = configuration
            else:
                assert registered is not None
                handler_id, handler_build_id, handler, _registration = registered
                task_manifest = json.loads(row["product_manifest_json"])
                successor_resume = command["command_type"] == "runner.successor.resume"
                if handler_build_id != self.product_manifest["build_id"] or (
                    not successor_resume
                    and task_manifest.get("build_id") != handler_build_id
                ):
                    raise RepositoryCompatibilityError(
                        "registered command handler is not locked to this task product build"
                    )
                if successor_resume and task_manifest.get("build_id") == handler_build_id:
                    raise RepositoryCompatibilityError(
                        "successor resume requires a distinct predecessor task build"
                    )
                transition = handler(_task_record(row), command, prepared)
                if not isinstance(transition, dict):
                    raise ContractError("registered handler must return a transition object")
                allowed_transition_fields = {
                    "state",
                    "status",
                    "material_grants",
                    "artifacts",
                    "event_payload",
                    "result",
                }
                if successor_resume:
                    allowed_transition_fields = {
                        "state",
                        "product_manifest",
                        "core_root",
                        "artifacts",
                        "migration_receipt",
                        "event_payload",
                        "result",
                    }
                unknown_fields = set(transition) - allowed_transition_fields
                if unknown_fields:
                    raise ContractError(
                        "registered handler returned unsupported transition fields: "
                        + ", ".join(sorted(unknown_fields))
                    )
                if "state" in transition:
                    if not isinstance(transition["state"], dict):
                        raise ContractError("registered handler transition.state must be an object")
                    state = transition["state"]
                if "status" in transition:
                    next_status = transition["status"]
                    if next_status not in TASK_STATUSES:
                        raise ContractError(
                            "registered handler returned an unsupported task status"
                        )
                if "material_grants" in transition:
                    next_material_grants = self._validate_material_grants(
                        transition["material_grants"]
                    )
                transition_artifacts = transition.get("artifacts", [])
                if not isinstance(transition_artifacts, list):
                    raise ContractError("registered handler transition.artifacts must be an array")
                transition_result = transition.get("result", {})
                transition_event_payload = transition.get("event_payload", {})
                if not isinstance(transition_result, dict) or not isinstance(
                    transition_event_payload, dict
                ):
                    raise ContractError("registered handler result and event_payload must be objects")
                if successor_resume:
                    next_product_manifest = transition.get("product_manifest")
                    next_core_root = transition.get("core_root")
                    transition_migration_receipt = transition.get(
                        "migration_receipt"
                    )
                    self._validate_successor_transition(
                        connection,
                        row=row,
                        command=command,
                        prepared=prepared,
                        state=state,
                        product_manifest=next_product_manifest,
                        core_root=next_core_root,
                        artifacts=transition_artifacts,
                        migration_receipt=transition_migration_receipt,
                    )
                    affects_revision = False
            next_revision = current_revision + 1 if affects_revision else current_revision
            normalized_artifacts = self._validate_transition_artifacts(
                connection,
                row=row,
                task_id=task_id,
                revision=next_revision,
                artifacts=transition_artifacts,
                build_id_override=(
                    next_product_manifest.get("build_id")
                    if command["command_type"] == "runner.successor.resume"
                    else None
                ),
            )
            if registered is not None and next_status == "completed":
                if command["command_type"] == "runner.successor.resume":
                    # The sealed transition above preserves status, revision,
                    # stage and accepted evidence. Re-read the existing verdict;
                    # a runtime upgrade is not a new scholarly completion.
                    readiness = self.get_readiness(task_id, revision=current_revision)
                    if (
                        row["status"] != "completed"
                        or readiness.get("status") != "fresh"
                        or readiness.get("is_complete_for_requested_scope") is not True
                    ):
                        raise ContractError(
                            "completed successor requires preserved fresh readiness"
                        )
                    completion_verdict = readiness["payload"]
                else:
                    readiness_receipts = [
                        item
                        for item in normalized_artifacts
                        if item["artifact_type"] == "quality.readiness-verdict"
                    ]
                    if len(readiness_receipts) != 1:
                        raise ContractError(
                            "registered completion requires exactly one fresh readiness verdict"
                        )
                    try:
                        completion_verdict = json.loads(
                            Path(readiness_receipts[0]["path"]).read_text(
                                encoding="utf-8-sig"
                            )
                        )
                    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                        raise ContractError(
                            "registered completion readiness verdict is unreadable"
                        ) from exc
                requested_scope = completion_verdict.get("requested_scope")
                layer_blockers = completion_verdict.get("blockers_by_layer")
                scoped_blockers = (
                    layer_blockers.get(requested_scope)
                    if isinstance(layer_blockers, dict)
                    and isinstance(requested_scope, str)
                    else None
                )
                if (
                    completion_verdict.get("is_complete_for_requested_scope")
                    is not True
                    or scoped_blockers != []
                ):
                    raise ContractError(
                        "registered completion requires a fresh verdict complete for the requested scope"
                    )
            if command["command_type"] == "runner.successor.resume":
                if state.get("last_command") != {
                    "command_id": command["command_id"],
                    "command_type": command["command_type"],
                    "recorded_at": prepared.get("recorded_at"),
                }:
                    raise ContractError(
                        "successor state does not carry the exact committed command marker"
                    )
            else:
                state["last_command"] = {
                    "command_id": command["command_id"],
                    "command_type": command["command_type"],
                    "recorded_at": _now(),
                }
            updated_at = _now()
            connection.execute(
                """UPDATE tasks SET title=?,status=?,revision=?,core_root=?,
                   material_grants_json=?,product_manifest_json=?,state_json=?,updated_at=?
                   WHERE task_id=?""",
                (
                    next_title,
                    next_status,
                    next_revision,
                    str(next_core_root),
                    _canonical_json(next_material_grants),
                    _canonical_json(next_product_manifest),
                    _canonical_json(state),
                    updated_at,
                    task_id,
                ),
            )
            for artifact in normalized_artifacts:
                connection.execute(
                    """INSERT INTO artifacts(
                       receipt_id,task_id,subject_revision,artifact_id,artifact_type,path,
                       sha256,receipt_json,recorded_at
                       ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        artifact["receipt_id"],
                        task_id,
                        next_revision,
                        artifact["artifact_id"],
                        artifact["artifact_type"],
                        artifact["path"],
                        artifact["sha256"],
                        _canonical_json(artifact),
                        artifact["recorded_at"],
                    ),
                )
            if transition_migration_receipt is not None:
                connection.execute(
                    "INSERT INTO migrations(migration_id,task_id,receipt_json,created_at) "
                    "VALUES(?,?,?,?)",
                    (
                        transition_migration_receipt["migration_id"],
                        task_id,
                        _canonical_json(transition_migration_receipt),
                        transition_migration_receipt["recorded_at"],
                    ),
                )
            sequence = self._append_event(
                connection,
                task_id=task_id,
                revision=next_revision,
                event_type=command["command_type"],
                command_id=command["command_id"],
                payload={
                    "payload": command["payload"],
                    "actor": command["actor"],
                    "fencing_token": fencing_token,
                    "handler_id": handler_id,
                    "artifacts": [
                        {
                            "receipt_id": item["receipt_id"],
                            "artifact_id": item["artifact_id"],
                            "artifact_type": item["artifact_type"],
                            "sha256": item["sha256"],
                        }
                        for item in normalized_artifacts
                    ],
                    **transition_event_payload,
                },
                projections=["task_record"],
            )
            result = {
                "contract": "paperspine5.command-result",
                "schema_version": PRODUCT_SCHEMA_VERSION,
                "task_id": task_id,
                "command_id": command["command_id"],
                "status": "accepted",
                "previous_revision": current_revision,
                "resulting_revision": next_revision,
                "event_sequence": sequence,
                "fencing_token": fencing_token,
                "output": transition_result,
                "replayed": False,
            }
            connection.execute(
                "INSERT INTO commands(command_id,task_id,envelope_json,result_json,created_at) VALUES(?,?,?,?,?)",
                (command["command_id"], task_id, canonical, _canonical_json(result), updated_at),
            )
        pending = self._drain_outbox(task_id=task_id, up_to_sequence=sequence)
        return {**result, "projection_pending": pending > 0}

    def _validate_material_grants(self, grants: Any) -> list[dict[str, Any]]:
        if not isinstance(grants, list):
            raise ContractError("material_grants must be an array")
        normalized: list[dict[str, Any]] = []
        roots: list[Path] = []
        grant_ids: set[str] = set()
        for grant in grants:
            if not isinstance(grant, dict):
                raise ContractError("each material capability grant must be an object")
            grant_id = grant.get("grant_id")
            if not isinstance(grant_id, str) or not grant_id or grant_id in grant_ids:
                raise ContractError("material capability grant_id must be unique and non-empty")
            root = _validate_grant_root(grant)
            if (
                grant.get("contract") != "paperspine5.capability-grant"
                or grant.get("schema_version") != "1.1"
                or grant.get("capability") != "materials.read"
                or grant.get("permissions") != ["enumerate", "read"]
                or grant.get("read_only") is not True
            ):
                raise ContractError("material capability grant is not a read-only materials.read grant")
            grant_ids.add(grant_id)
            roots.append(root)
            normalized.append(dict(grant))
        _assert_separate_roots(self.core_root, self.user_data_root, roots)
        return normalized

    @staticmethod
    def _successor_json_sha256(value: Any) -> str:
        return hashlib.sha256((_canonical_json(value) + "\n").encode("utf-8")).hexdigest()

    def _successor_ledger_identity(
        self, connection: sqlite3.Connection, task_id: str
    ) -> dict[str, Any]:
        artifact_rows = connection.execute(
            "SELECT receipt_json FROM artifacts WHERE task_id=?", (task_id,)
        ).fetchall()
        artifacts = []
        for row in artifact_rows:
            receipt = json.loads(row["receipt_json"])
            artifacts.append(
                {
                    "receipt_id": receipt.get("receipt_id"),
                    "artifact_id": receipt.get("artifact_id"),
                    "artifact_type": receipt.get("artifact_type"),
                    "revision_id": receipt.get("subject", {}).get("revision_id"),
                    "sha256": receipt.get("sha256"),
                }
            )
        artifacts.sort(
            key=lambda item: (
                str(item["revision_id"]),
                str(item["artifact_id"]),
                str(item["receipt_id"]),
            )
        )
        command_rows = connection.execute(
            "SELECT command_id,envelope_json,result_json FROM commands WHERE task_id=?",
            (task_id,),
        ).fetchall()
        commands = []
        for row in command_rows:
            stored = json.loads(row["envelope_json"])
            envelope = (
                stored.get("command")
                if stored.get("contract") == "paperspine5.registered-command-record"
                else stored
            )
            result = json.loads(row["result_json"])
            commands.append(
                {
                    "command_id": row["command_id"],
                    "command_type": envelope.get("command_type", "task.create"),
                    "expected_revision": envelope.get("expected_revision"),
                    "previous_revision": result.get("previous_revision"),
                    "resulting_revision": result.get("resulting_revision"),
                    "status": result.get("status"),
                }
            )
        commands.sort(key=lambda item: str(item["command_id"]))
        return {
            "artifact_count": len(artifacts),
            "artifact_set_sha256": self._successor_json_sha256(artifacts),
            "command_count": len(commands),
            "command_set_sha256": self._successor_json_sha256(commands),
        }

    def _validate_successor_transition(
        self,
        connection: sqlite3.Connection,
        *,
        row: sqlite3.Row,
        command: dict[str, Any],
        prepared: dict[str, Any],
        state: Any,
        product_manifest: Any,
        core_root: Any,
        artifacts: Any,
        migration_receipt: Any,
    ) -> None:
        """Seal the only allowed old-build -> active-build, same-revision write."""

        if command.get("command_type") != "runner.successor.resume":
            raise ContractError("successor transition validator received another command")
        if not all(
            isinstance(value, dict)
            for value in (state, product_manifest, migration_receipt)
        ) or not isinstance(artifacts, list):
            raise ContractError("successor transition payload is incomplete")
        resolved_core = Path(str(core_root)).resolve()
        if resolved_core != self.core_root:
            raise ContractError("successor transition targets another core root")
        normalized_manifest = validate_product_manifest(
            product_manifest, core_root=resolved_core
        )
        if normalized_manifest != self.product_manifest:
            raise ContractError("successor transition target manifest is not the active kernel")

        source_manifest = json.loads(row["product_manifest_json"])
        source_state = json.loads(row["state_json"])
        source_runner = source_state.get("runner")
        target_runner = state.get("runner")
        if not isinstance(source_runner, dict) or not isinstance(target_runner, dict):
            raise ContractError("successor transition requires readable runner states")
        ledger = self._successor_ledger_identity(connection, row["task_id"])
        source_identity = {
            "task_id": row["task_id"],
            "title": row["title"],
            "host": row["host"],
            "status": row["status"],
            "revision": row["revision"],
            "active_run_id": row["active_run_id"],
            "workspace_root": row["workspace_root"],
            "run_root": row["run_root"],
            "material_grants_sha256": self._successor_json_sha256(
                json.loads(row["material_grants_json"])
            ),
            "product_manifest_sha256": self._successor_json_sha256(source_manifest),
            "task_state_sha256": self._successor_json_sha256(source_state),
            "runner_state_sha256": self._successor_json_sha256(source_runner),
            "material_snapshot_sha256": (
                source_runner.get("material_inventory") or {}
            ).get("snapshot_sha256"),
            "run_contract_sha256": (
                source_runner.get("run_contract") or {}
            ).get("sha256"),
            "academic_inputs_sha256": (
                source_runner.get("academic_inputs") or {}
            ).get("sha256"),
            **ledger,
        }
        source_identity["identity_sha256"] = self._successor_json_sha256(
            source_identity
        )
        if prepared.get("source_identity") != source_identity:
            raise ContractError("successor source task/snapshot/ledger identity drifted")

        source_build_id = source_manifest.get("build_id")
        target_build_id = normalized_manifest.get("build_id")
        if not isinstance(source_build_id, str) or source_build_id == target_build_id:
            raise ContractError("successor transition is not a forward cross-build rebind")
        if (
            target_runner.get("contract") != "paperspine5.runner-state"
            or target_runner.get("schema_version") != PRODUCT_SCHEMA_VERSION
            or target_runner.get("product_build_id") != target_build_id
            or target_runner.get("runner_version")
            != normalized_manifest.get("component_versions", {}).get("product_runner")
            or target_runner.get("external_action_authorized") is not False
        ):
            raise ContractError("successor target runner state binding is invalid")
        source_comparable = {
            key: value
            for key, value in source_runner.items()
            if key
            not in {
                "product_build_id",
                "runner_version",
                "updated_at",
                "academic_inputs",
                "successor_migration",
            }
        }
        target_comparable = {
            key: value
            for key, value in target_runner.items()
            if key
            not in {
                "product_build_id",
                "runner_version",
                "updated_at",
                "academic_inputs",
                "successor_migration",
            }
        }
        if source_comparable != target_comparable:
            raise ContractError("successor transition changed stage, issues, evidence, or authority")
        source_top = {
            key: value for key, value in source_state.items() if key not in {"runner", "last_command"}
        }
        target_top = {
            key: value for key, value in state.items() if key not in {"runner", "last_command"}
        }
        if source_top != target_top:
            raise ContractError("successor transition changed non-runner task state")

        if set(migration_receipt) != {
            "contract",
            "schema_version",
            "migration_id",
            "command_id",
            "task_id",
            "active_run_id",
            "revision",
            "source",
            "target",
            "installed_suite_authority",
            "academic_rebind",
            "preservation",
            "recovery",
            "recorded_at",
            "external_action_authorized",
            "receipt_sha256",
        }:
            raise ContractError("successor migration receipt fields are not exact")
        unsigned_receipt = {
            key: value
            for key, value in migration_receipt.items()
            if key != "receipt_sha256"
        }
        if migration_receipt.get("receipt_sha256") != self._successor_json_sha256(
            unsigned_receipt
        ):
            raise ContractError("successor migration receipt hash is invalid")
        authority = migration_receipt.get("installed_suite_authority")
        preservation = migration_receipt.get("preservation")
        recovery = migration_receipt.get("recovery")
        command_payload = command.get("payload")
        if (
            migration_receipt.get("contract")
            != "paperspine5.runner-successor-migration-receipt"
            or migration_receipt.get("schema_version") != "1.0"
            or migration_receipt.get("command_id") != command["command_id"]
            or migration_receipt.get("task_id") != row["task_id"]
            or migration_receipt.get("active_run_id") != row["active_run_id"]
            or migration_receipt.get("revision") != row["revision"]
            or migration_receipt.get("external_action_authorized") is not False
            or not isinstance(authority, dict)
            or not isinstance(command_payload, dict)
            or command_payload.get("authority_sha256")
            != authority.get("authority_sha256")
            or command_payload.get("receipt_sha256")
            != migration_receipt.get("receipt_sha256")
            or command_payload.get("source_identity_sha256")
            != source_identity["identity_sha256"]
            or command_payload.get("material_snapshot_sha256")
            != source_identity["material_snapshot_sha256"]
            or command_payload.get("source_build_id") != source_build_id
            or command_payload.get("target_build_id") != target_build_id
        ):
            raise ContractError("successor command/receipt/task binding is invalid")
        if migration_receipt.get("source", {}).get("identity") != source_identity:
            raise ContractError("successor receipt does not bind the exact predecessor ledger")
        if (
            migration_receipt.get("source", {}).get("build_id") != source_build_id
            or migration_receipt.get("target", {}).get("build_id") != target_build_id
            or migration_receipt.get("target", {}).get("core_root")
            != str(self.core_root)
            or migration_receipt.get("target", {}).get("product_manifest_sha256")
            != self._successor_json_sha256(normalized_manifest)
            or migration_receipt.get("target", {}).get("task_state_sha256")
            != self._successor_json_sha256(state)
        ):
            raise ContractError("successor receipt target identity is invalid")
        expected_preservation = {
            "same_task_id": True,
            "same_active_run_id": True,
            "same_workspace_root": True,
            "same_run_root": True,
            "same_revision": True,
            "same_stage": True,
            "same_material_snapshot_sha256": True,
            "predecessor_artifacts_retained": True,
            "predecessor_commands_retained": True,
            "new_task_created": False,
            "material_snapshot_copied": False,
        }
        if preservation != expected_preservation:
            raise ContractError("successor preservation claim is incomplete")
        if (
            not isinstance(recovery, dict)
            or recovery.get("transaction")
            != "sqlite-begin-immediate-atomic-rollback"
            or recovery.get("pre_product_manifest_sha256")
            != source_identity["product_manifest_sha256"]
            or recovery.get("pre_task_state_sha256")
            != source_identity["task_state_sha256"]
            or recovery.get("pre_artifact_set_sha256")
            != source_identity["artifact_set_sha256"]
            or recovery.get("pre_command_set_sha256")
            != source_identity["command_set_sha256"]
        ):
            raise ContractError("successor recovery binding is invalid")
        existing = connection.execute(
            "SELECT 1 FROM migrations WHERE migration_id=?",
            (migration_receipt["migration_id"],),
        ).fetchone()
        if existing is not None:
            raise IdempotencyConflictError("successor migration identity was already committed")

        academic_receipts = [
            item
            for item in artifacts
            if isinstance(item, dict)
            and item.get("artifact_type") == "runner.successor-academic-inputs"
        ]
        if len(artifacts) != len(academic_receipts) or len(academic_receipts) > 1:
            raise ContractError("successor transition carries an unsupported derived artifact")
        if academic_receipts:
            academic = academic_receipts[0]
            target_pointer = target_runner.get("academic_inputs")
            rebind = migration_receipt.get("academic_rebind")
            if (
                not isinstance(target_pointer, dict)
                or target_pointer.get("artifact_id") != academic.get("artifact_id")
                or target_pointer.get("sha256") != academic.get("sha256")
                or not isinstance(rebind, dict)
                or rebind.get("source_sha256")
                != (source_runner.get("academic_inputs") or {}).get("sha256")
                or rebind.get("target_sha256") != academic.get("sha256")
                or rebind.get("scientific_stage_inputs_unchanged") is not True
                or not isinstance(
                    rebind.get("source_scientific_stage_inputs_sha256"), str
                )
                or len(rebind["source_scientific_stage_inputs_sha256"]) != 64
                or rebind.get("source_scientific_stage_inputs_sha256")
                != rebind.get("target_scientific_stage_inputs_sha256")
            ):
                raise ContractError("successor academic runtime rebind is invalid")
        elif (
            target_runner.get("academic_inputs") != source_runner.get("academic_inputs")
            or migration_receipt.get("academic_rebind") is not None
        ):
            raise ContractError("successor transition changed academic inputs without a receipt")

    def _validate_transition_artifacts(
        self,
        connection: sqlite3.Connection,
        *,
        row: sqlite3.Row,
        task_id: str,
        revision: int,
        artifacts: list[dict[str, Any]],
        build_id_override: str | None = None,
    ) -> list[dict[str, Any]]:
        run_root = Path(row["run_root"]).resolve()
        build_id = build_id_override or json.loads(row["product_manifest_json"])["build_id"]
        normalized: list[dict[str, Any]] = []
        for raw in artifacts:
            receipt = validate_artifact_receipt(raw, task_id=task_id, revision=revision)
            if receipt["metadata"].get("product_build_id") != build_id:
                raise ContractError("registered handler artifact is not bound to the task build")
            artifact_path = Path(receipt["path"])
            if not artifact_path.is_absolute():
                artifact_path = run_root / artifact_path
            artifact_path = artifact_path.resolve()
            if not _is_relative_to(artifact_path, run_root) or not native_path(artifact_path).is_file():
                raise ContractError(
                    "registered handler artifact path must be a file within the active run_root"
                )
            if _sha256(artifact_path) != receipt["sha256"] or native_path(artifact_path).stat().st_size != receipt["size_bytes"]:
                raise ContractError("registered handler artifact hash or size does not match bytes")
            receipt["path"] = str(artifact_path)
            receipt["recorded_at"] = _now()
            normalized.append(receipt)
        receipt_ids = [item["receipt_id"] for item in normalized]
        artifact_ids = [item["artifact_id"] for item in normalized]
        if len(receipt_ids) != len(set(receipt_ids)) or len(artifact_ids) != len(set(artifact_ids)):
            raise ContractError("registered transition artifact identities must be unique")
        self._validate_atomic_quality_artifacts(
            connection,
            task_id=task_id,
            revision=revision,
            receipts=normalized,
        )
        for receipt_id in receipt_ids:
            if connection.execute(
                "SELECT 1 FROM artifacts WHERE receipt_id=?", (receipt_id,)
            ).fetchone():
                raise IdempotencyConflictError("registered transition artifact receipt_id is reused")
        return normalized

    def _validate_atomic_quality_artifacts(
        self,
        connection: sqlite3.Connection,
        *,
        task_id: str,
        revision: int,
        receipts: list[dict[str, Any]],
    ) -> None:
        """Verify known quality artifacts against the complete atomic transition.

        Registered handlers may not self-assert a quality result.  A readiness
        verdict is accepted only when its real bytes validate and every input
        hash is backed by another fresh artifact in this same transaction (or
        an already-recorded artifact for the same revision).
        """

        quality_receipts = [
            item
            for item in receipts
            if item["artifact_type"] == "quality.readiness-verdict"
        ]
        if not quality_receipts:
            return
        trusted = self._trusted_artifact_mapping(
            task_id,
            revision,
            connection=connection,
        )
        verified = []
        for item in receipts:
            artifact_bytes = native_path(item["path"]).read_bytes()
            verified.append((item, artifact_bytes))
            projections = _verified_receipt_authority_projections(
                item, artifact_bytes
            )
            for artifact_id, artifact_hash in projections.items():
                previous = trusted.get(artifact_id)
                if previous is not None and previous != artifact_hash:
                    raise ContractError(
                        f"atomic artifact authority projection conflicts: {artifact_id}"
                    )
                trusted[artifact_id] = artifact_hash
        # Package validation may include superseded candidate manifests from
        # earlier same-task figure retries.  Keep their already-recorded
        # semantic aliases available to the publication subject, while still
        # applying strict byte/semantic checks to the current selected
        # candidates.  A historical duplicate is provenance, not a new
        # publication input, and must not block J10 delivery.
        _candidate_readiness_authority(trusted, verified, strict=False)
        for receipt in quality_receipts:
            artifact_path = Path(receipt["path"])
            try:
                payload = json.loads(artifact_path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ContractError(
                    "quality readiness artifact must contain valid UTF-8 JSON"
                ) from exc
            if _contains_external_authorization(payload):
                raise ContractError("quality artifacts cannot authorize external actions")
            valid, blockers = _validate_readiness_payload(
                payload,
                receipt["subject"],
                trusted,
            )
            if not valid:
                raise ContractError(
                    "invalid readiness verdict payload: " + ", ".join(blockers)
                )
            unbound = {
                artifact_id: expected_hash
                for artifact_id, expected_hash in receipt["subject"]["input_hashes"].items()
                if trusted.get(artifact_id) != expected_hash
            }
            if unbound:
                raise ContractError(
                    "readiness subject is not backed by fresh same-revision transition artifacts: "
                    + ", ".join(sorted(unbound))
                )

    def record_artifact(
        self,
        task_id: str,
        receipt: dict[str, Any],
        *,
        expected_revision: int,
        command_id: str,
        writer_id: str,
        runner_registration: str | None = None,
    ) -> dict[str, Any]:
        normalized = validate_artifact_receipt(receipt, task_id=task_id, revision=expected_revision)
        if (normalized.get("artifact_type") == "figure.final-mapping"
                or normalized.get("metadata", {}).get("semantic_hash_kind") == "figure-final-mapping-v1"):
            registered = self._registered_command_handlers.get("runner.issue.answer")
            if not registered or not isinstance(runner_registration, str) or not secrets.compare_digest(registered[3], runner_registration):
                raise ContractError("final mappings require the registered typed ProductRunner facade")
        envelope = {
            "contract": "paperspine5.command-envelope",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "command_id": command_id,
            "task_id": task_id,
            "expected_revision": expected_revision,
            "writer_id": writer_id,
            "command_type": "artifact.record",
            "payload": {
                "receipt_id": normalized["receipt_id"],
                "artifact_id": normalized["artifact_id"],
                "artifact_type": normalized["artifact_type"],
            },
            "actor": {"actor_id": normalized["authority"]["producer_id"], "surface": "system"},
        }
        command = validate_command_envelope(envelope, task_id=task_id)
        canonical = _canonical_json({**command, "artifact_receipt": normalized})
        with self.store.write_transaction() as connection:
            replay = connection.execute("SELECT task_id,envelope_json,result_json FROM commands WHERE command_id=?", (command_id,)).fetchone()
            if replay is not None:
                if replay["task_id"] != task_id or replay["envelope_json"] != canonical:
                    raise IdempotencyConflictError("command_id was already used for a different command")
                return {**json.loads(replay["result_json"]), "replayed": True}
            row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFoundError(f"task does not exist: {task_id}")
            if row["revision"] != expected_revision:
                raise RevisionConflictError(
                    f"expected_revision {expected_revision} does not match current revision {row['revision']}"
                )
            artifact_path = Path(normalized["path"])
            if not artifact_path.is_absolute():
                artifact_path = Path(row["run_root"]) / artifact_path
            artifact_path = artifact_path.resolve()
            run_root = Path(row["run_root"]).resolve()
            if not _is_relative_to(artifact_path, run_root):
                raise ContractError("artifact_receipt.path must resolve within the active run_root")
            if not native_path(artifact_path).is_file():
                raise ContractError(f"artifact_receipt.path does not exist: {artifact_path}")
            actual_hash = _sha256(artifact_path)
            actual_size = native_path(artifact_path).stat().st_size
            if actual_hash != normalized["sha256"] or actual_size != normalized["size_bytes"]:
                raise ContractError("artifact_receipt hash or size does not match the artifact bytes")
            if normalized.get("artifact_type") == "figure.final-mapping":
                if normalized.get("metadata", {}).get("product_build_id") != self.product_manifest["build_id"]:
                    raise ContractError("final mapping validation build is not current")
                _verified_receipt_authority_hash(normalized, native_path(artifact_path).read_bytes())
            if normalized["artifact_type"].startswith("quality.") and artifact_path.suffix.lower() == ".json":
                try:
                    quality_payload = json.loads(artifact_path.read_text(encoding="utf-8-sig"))
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise ContractError("quality JSON artifact must contain valid UTF-8 JSON") from exc
                if _contains_external_authorization(quality_payload):
                    raise ContractError("quality artifacts cannot authorize external actions")
                if normalized["artifact_type"] == "quality.readiness-verdict":
                    trusted = self._trusted_artifact_mapping(
                        task_id, expected_revision, connection=connection
                    )
                    valid, blockers = _validate_readiness_payload(
                        quality_payload, normalized["subject"], trusted
                    )
                    if not valid:
                        raise ContractError(
                            "invalid readiness verdict payload: " + ", ".join(blockers)
                        )
                    unbound = {
                        artifact_id: expected_hash
                        for artifact_id, expected_hash in normalized["subject"]["input_hashes"].items()
                        if trusted.get(artifact_id) != expected_hash
                    }
                    if unbound:
                        raise ContractError(
                            "readiness subject is not backed by fresh same-revision artifact receipts: "
                            + ", ".join(sorted(unbound))
                        )
            normalized["path"] = str(artifact_path)
            normalized["recorded_at"] = _now()
            fencing_token, _ = self._acquire_lease(connection, task_id, writer_id)
            try:
                connection.execute(
                    "INSERT INTO artifacts(receipt_id,task_id,subject_revision,artifact_id,artifact_type,path,sha256,receipt_json,recorded_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        normalized["receipt_id"],
                        task_id,
                        expected_revision,
                        normalized["artifact_id"],
                        normalized["artifact_type"],
                        str(artifact_path),
                        actual_hash,
                        _canonical_json(normalized),
                        normalized["recorded_at"],
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise IdempotencyConflictError("artifact receipt_id was already used") from exc
            sequence = self._append_event(
                connection,
                task_id=task_id,
                revision=expected_revision,
                event_type="artifact.recorded",
                command_id=command_id,
                payload={
                    "receipt_id": normalized["receipt_id"],
                    "artifact_id": normalized["artifact_id"],
                    "artifact_type": normalized["artifact_type"],
                    "sha256": actual_hash,
                    "subject": normalized["subject"],
                    "fencing_token": fencing_token,
                },
                projections=["task_record"],
            )
            result = {
                "contract": "paperspine5.command-result",
                "schema_version": PRODUCT_SCHEMA_VERSION,
                "task_id": task_id,
                "command_id": command_id,
                "status": "accepted",
                "previous_revision": expected_revision,
                "resulting_revision": expected_revision,
                "event_sequence": sequence,
                "fencing_token": fencing_token,
                "receipt": normalized,
                "replayed": False,
            }
            connection.execute(
                "INSERT INTO commands(command_id,task_id,envelope_json,result_json,created_at) VALUES(?,?,?,?,?)",
                (command_id, task_id, canonical, _canonical_json(result), normalized["recorded_at"]),
            )
        pending = self._drain_outbox(task_id=task_id, up_to_sequence=sequence)
        return {**result, "projection_pending": pending > 0}

    def read_events(self, task_id: str, *, after_sequence: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return self.state_repository.read_events(task_id, after_sequence=after_sequence, limit=limit)

    def list_artifacts(
        self,
        task_id: str,
        *,
        artifact_type: str | None = None,
        subject_revision: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return verified read projections; mutated/missing bytes are never exposed as fresh payloads."""
        task = self.get_task(task_id)
        query = "SELECT rowid,* FROM artifacts WHERE task_id=?"
        params: list[Any] = [task_id]
        if artifact_type is not None:
            query += " AND artifact_type=?"
            params.append(artifact_type)
        if subject_revision is not None:
            if isinstance(subject_revision, bool) or not isinstance(subject_revision, int) or subject_revision < 0:
                raise ContractError("subject_revision must be a non-negative integer")
            query += " AND subject_revision=?"
            params.append(subject_revision)
        query += " ORDER BY recorded_at DESC,rowid DESC"
        with self.store.read_connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        reference_revision = task["revision"] if subject_revision is None else subject_revision
        views: list[dict[str, Any]] = []
        for row in rows:
            receipt = json.loads(row["receipt_json"])
            path = Path(row["path"])
            payload: Any = None
            freshness = "missing"
            if native_path(path).is_file():
                try:
                    artifact_bytes = native_path(path).read_bytes()
                except OSError:
                    freshness = "missing"
                else:
                    bytes_fresh = (
                        hashlib.sha256(artifact_bytes).hexdigest() == row["sha256"]
                        and len(artifact_bytes) == receipt["size_bytes"]
                    )
                    revision_fresh = row["subject_revision"] == reference_revision
                    freshness = "fresh" if bytes_fresh and revision_fresh else "stale"
                    if freshness == "fresh" and path.suffix.lower() == ".json":
                        try:
                            payload = json.loads(artifact_bytes.decode("utf-8-sig"))
                        except (UnicodeError, json.JSONDecodeError):
                            freshness = "stale"
                            payload = None
                        if (
                            freshness == "fresh"
                            and row["artifact_type"] == "quality.readiness-verdict"
                        ):
                            with self.store.read_connection() as ledger_connection:
                                trusted = self._trusted_artifact_mapping(
                                    task_id,
                                    row["subject_revision"],
                                    connection=ledger_connection,
                                )
                            valid, _blockers = _validate_readiness_payload(
                                payload, receipt["subject"], trusted
                            )
                            if not valid:
                                freshness = "stale"
                                payload = None
                            else:
                                if any(
                                    trusted.get(artifact_id) != expected_hash
                                    for artifact_id, expected_hash in receipt["subject"]["input_hashes"].items()
                                ):
                                    freshness = "stale"
                                    payload = None
            views.append(
                {
                    "contract": "paperspine5.artifact-view",
                    "schema_version": PRODUCT_SCHEMA_VERSION,
                    "task_id": task_id,
                    "current_revision": task["revision"],
                    "reference_revision": reference_revision,
                    "freshness": freshness,
                    "receipt": receipt,
                    "payload": payload,
                }
            )
        return views

    def _trusted_artifact_mapping(
        self,
        task_id: str,
        revision: int,
        *,
        connection: sqlite3.Connection,
    ) -> dict[str, str]:
        task = connection.execute("SELECT run_root FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if task is None:
            raise TaskNotFoundError(f"task does not exist: {task_id}")
        run_root = Path(task["run_root"]).resolve()
        rows = connection.execute(
            """SELECT * FROM artifacts
               WHERE task_id=? AND subject_revision=? AND artifact_type!='quality.readiness-verdict'
               ORDER BY recorded_at,rowid""",
            (task_id, revision),
        ).fetchall()
        trusted: dict[str, str] = {}
        verified = []
        for row in rows:
            path = Path(row["path"]).resolve()
            if not _is_relative_to(path, run_root) or not native_path(path).is_file():
                continue
            try:
                artifact_bytes = native_path(path).read_bytes()
            except OSError:
                continue
            receipt = json.loads(row["receipt_json"])
            if (
                hashlib.sha256(artifact_bytes).hexdigest() == row["sha256"]
                and len(artifact_bytes) == receipt["size_bytes"]
            ):
                try:
                    projections = _verified_receipt_authority_projections(
                        receipt, artifact_bytes
                    )
                except ContractError:
                    continue
                verified.append((receipt, artifact_bytes))
                for artifact_id, artifact_hash in projections.items():
                    previous = trusted.get(artifact_id)
                    if previous is None or previous == artifact_hash:
                        trusted[artifact_id] = artifact_hash
        _candidate_readiness_authority(trusted, verified, strict=False)
        return trusted

    def get_readiness(self, task_id: str, *, revision: int | None = None) -> dict[str, Any]:
        """Project the latest verified readiness receipt without deriving readiness in the Kernel."""
        task = self.get_task(task_id)
        reference_revision = task["revision"] if revision is None else revision
        views = self.list_artifacts(
            task_id,
            artifact_type="quality.readiness-verdict",
            subject_revision=reference_revision,
        )
        if not views:
            return {
                "contract": "paperspine5.readiness-view",
                "schema_version": PRODUCT_SCHEMA_VERSION,
                "task_id": task_id,
                "revision": reference_revision,
                "status": "unknown",
                "ready": False,
                "requested_scope": None,
                "manuscript_ready": False,
                "delivery_ready": False,
                "submission_ready": False,
                "is_complete_for_requested_scope": False,
                "receipt": None,
                "payload": None,
                "external_action_authorized": False,
            }
        latest = views[0]
        payload = latest["payload"] if latest["freshness"] == "fresh" else None
        return {
            "contract": "paperspine5.readiness-view",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "task_id": task_id,
            "revision": reference_revision,
            "status": latest["freshness"],
            "ready": bool(
                payload and payload.get("is_complete_for_requested_scope") is True
            ),
            "requested_scope": payload.get("requested_scope") if payload else None,
            "manuscript_ready": bool(payload and payload.get("manuscript_ready") is True),
            "delivery_ready": bool(payload and payload.get("delivery_ready") is True),
            "submission_ready": bool(payload and payload.get("submission_ready") is True),
            "is_complete_for_requested_scope": bool(
                payload and payload.get("is_complete_for_requested_scope") is True
            ),
            "receipt": latest["receipt"],
            "payload": payload,
            "external_action_authorized": False,
        }

    def import_legacy_job(
        self,
        job_path: str | Path,
        *,
        command_id: str,
        title: str | None = None,
        description: str | None = None,
        task_id: str | None = None,
        host: str = "codex",
    ) -> dict[str, Any]:
        if (
            not isinstance(command_id, str)
            or not command_id
            or len(command_id) > 128
            or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-" for character in command_id)
        ):
            raise ContractError("command_id must be a safe identifier")
        requested_task_id = task_id
        if task_id is not None and (
            not task_id
            or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in task_id)
        ):
            raise ContractError("task_id must use letters, numbers, dots, underscores, or hyphens")
        if host not in {"codex", "claude-code", "dsh", "standalone-skill"}:
            raise ContractError("host is unsupported")
        source_job = Path(job_path).resolve()
        raw_job = load_json(source_job)
        if raw_job.get("schema_version") not in {"1.0", "1.1"}:
            raise ContractError("legacy integration job schema must be 1.0 or 1.1")
        source_state = source_job.with_name("integration_state.json")
        raw_state = load_json(source_state) if source_state.is_file() else None
        if raw_state is not None and raw_state.get("schema_version") not in {"1.0", "1.1", "1.2", "1.3"}:
            raise ContractError("legacy integration state schema is unsupported")
        before = {
            "job": {"path": str(source_job), "sha256": _sha256(source_job), "schema_version": raw_job.get("schema_version")},
            "state": (
                {"path": str(source_state), "sha256": _sha256(source_state), "schema_version": raw_state.get("schema_version")}
                if raw_state is not None
                else None
            ),
        }
        raw_legacy_root = raw_job.get("project_root")
        legacy_root: Path | None = None
        if isinstance(raw_legacy_root, str) and raw_legacy_root.strip():
            candidate = Path(raw_legacy_root.strip())
            legacy_root = (
                (source_job.parent / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
            )
        legacy_material_grants: list[dict[str, Any]] = []
        grant_blocker: str | None = None
        if legacy_root is None or not legacy_root.is_dir():
            grant_blocker = "legacy project_root is missing or not a readable directory"
        else:
            try:
                _assert_separate_roots(self.core_root, self.user_data_root, [legacy_root])
            except ContractError as exc:
                grant_blocker = str(exc)
            else:
                try:
                    legacy_grant = _build_material_grant(legacy_root, 1, _now())
                except ContractError as exc:
                    grant_blocker = str(exc)
                else:
                    legacy_grant["grant_id"] = (
                        "legacy-material-"
                        + hashlib.sha256(str(legacy_root).encode("utf-8")).hexdigest()[:12]
                    )
                    legacy_material_grants = [legacy_grant]
        before["project_root"] = {
            "path": str(legacy_root) if legacy_root is not None else None,
            "grant_status": "granted_read_only" if legacy_material_grants else "blocked",
            "blocker": grant_blocker,
        }
        title = (title or f"Imported {raw_job.get('job_id', 'legacy job')}").strip()
        description = _task_description(description, title, legacy=True)
        import_request = {
            "contract": "paperspine5.import-legacy-job-request",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "command_id": command_id,
            "requested_task_id": requested_task_id,
            "title": title,
            "description": description,
            "host": host,
            "source": before,
            "product_build_id": self.product_manifest["build_id"],
        }
        canonical_request = _canonical_json(import_request)
        with self.store.read_connection() as connection:
            replay = connection.execute(
                "SELECT task_id,envelope_json FROM commands WHERE command_id=?", (command_id,)
            ).fetchone()
        if replay is not None:
            if not _same_task_request(replay["envelope_json"], canonical_request):
                raise IdempotencyConflictError("legacy import command_id was already used with different inputs")
            replay_task = self.get_task(replay["task_id"])
            return {
                "task": replay_task,
                "migration_receipt": load_json(replay_task["legacy"]["migration_receipt"]),
            }

        task_id = task_id or f"task-{uuid4().hex}"
        run_id = f"run-{uuid4().hex}"
        workspace_root = (self.user_data_root / "tasks" / task_id).resolve()
        run_root = workspace_root / "runs" / run_id
        migration_id = f"migration-{uuid4().hex}"
        staging_root = self.user_data_root / "registry" / "import-staging" / migration_id
        staged_snapshot = staging_root / "pre-migration"
        snapshot_root = run_root / "migrations" / migration_id / "pre-migration"
        try:
            staged_snapshot.mkdir(parents=True, exist_ok=False)
            shutil.copy2(source_job, staged_snapshot / "integration_job.json")
            if source_state.is_file():
                shutil.copy2(source_state, staged_snapshot / "integration_state.json")
            if _sha256(staged_snapshot / "integration_job.json") != before["job"]["sha256"]:
                raise ContractError("staged legacy job snapshot hash does not match the source")
            if before["state"] is not None and _sha256(staged_snapshot / "integration_state.json") != before["state"]["sha256"]:
                raise ContractError("staged legacy state snapshot hash does not match the source")
            if _sha256(source_job) != before["job"]["sha256"] or (
                before["state"] is not None and _sha256(source_state) != before["state"]["sha256"]
            ):
                raise ContractError("legacy source changed while staging the pre-migration snapshot")

            provisional_task = {
                "task_id": task_id,
                "revision": 0,
                "host": host,
                "core_root": str(self.core_root),
                "workspace_root": str(workspace_root),
                "run_root": str(run_root),
                "job_path": str(run_root / "integration_job.json"),
                "state_path": str(run_root / "integration_state.json"),
            }
            self._materialize_bootstrap(provisional_task)
            compatibility_state = load_json(provisional_task["state_path"])
            compatibility_state.setdefault("context", {}).setdefault("product_task", {})[
                "legacy_ingestion_required"
            ] = {
                "code": "legacy_ingestion_required",
                "migration_status": "registered_read_only",
                "source_project_root": str(legacy_root) if legacy_root is not None else None,
                "capability_grant_id": (
                    legacy_material_grants[0]["grant_id"] if legacy_material_grants else None
                ),
                "blocker": grant_blocker,
                "next_action": "Run the W3 copy-on-write legacy ingestion command before resuming product execution.",
            }
            write_json_atomic(provisional_task["state_path"], compatibility_state)
            snapshot_root.parent.mkdir(parents=True, exist_ok=False)
            shutil.move(str(staged_snapshot), str(snapshot_root))
        except BaseException:
            shutil.rmtree(staging_root, ignore_errors=True)
            shutil.rmtree(run_root, ignore_errors=True)
            raise
        receipt = {
            "contract": "paperspine5.migration-receipt",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "migration_id": migration_id,
            "task_id": task_id,
            "source": before,
            "snapshot_root": str(snapshot_root),
            "target": {
                "product_task_schema": PRODUCT_SCHEMA_VERSION,
                "integration_job_schema": "1.1",
                "integration_state_schema": "1.3",
                "content_ingested": False,
                "migration_status": "registered_read_only",
            },
            "source_mutated": False,
            "created_at": _now(),
        }
        receipt_path = snapshot_root.parent / "migration-receipt.json"
        write_json_atomic(receipt_path, receipt)
        legacy = {
            "source": before,
            "migration_receipt": str(receipt_path),
            "migration_status": "registered_read_only",
        }
        created_at = _now()
        state = {
            "configuration": {},
            "last_command": None,
            "legacy_state_schema": (raw_state or {}).get("schema_version"),
            "issues": [
                {
                    "contract": "paperspine5.kernel-issue",
                    "schema_version": PRODUCT_SCHEMA_VERSION,
                    "code": "legacy_ingestion_required",
                    "status": "open",
                    "migration_status": "registered_read_only",
                    "source_project_root": str(legacy_root) if legacy_root is not None else None,
                    "capability_grant_id": (
                        legacy_material_grants[0]["grant_id"] if legacy_material_grants else None
                    ),
                    "blocker": grant_blocker,
                    "next_action": "Run the W3 copy-on-write legacy ingestion command before resuming product execution.",
                }
            ],
        }
        try:
            with self.store.write_transaction() as connection:
                replay = connection.execute(
                    "SELECT task_id,envelope_json FROM commands WHERE command_id=?", (command_id,)
                ).fetchone()
                if replay is not None:
                    if not _same_task_request(replay["envelope_json"], canonical_request):
                        raise IdempotencyConflictError(
                            "legacy import command_id raced with different inputs"
                        )
                    race_replay_task_id = replay["task_id"]
                    sequence = None
                else:
                    race_replay_task_id = None
                    connection.execute(
                    """INSERT INTO tasks (
                        task_id,title,description,host,status,revision,active_run_id,core_root,workspace_root,run_root,
                        material_grants_json,product_manifest_json,state_json,legacy_json,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        task_id,
                        title,
                        description,
                        host,
                        "created",
                        0,
                        run_id,
                        str(self.core_root),
                        str(workspace_root),
                        str(run_root),
                        _canonical_json(legacy_material_grants),
                        _canonical_json(self.product_manifest),
                        _canonical_json(state),
                        _canonical_json(legacy),
                        created_at,
                        created_at,
                    ),
                )
                    connection.execute(
                        "INSERT INTO migrations(migration_id,task_id,receipt_json,created_at) VALUES(?,?,?,?)",
                        (migration_id, task_id, _canonical_json(receipt), receipt["created_at"]),
                    )
                    sequence = self._append_event(
                        connection,
                        task_id=task_id,
                        revision=0,
                        event_type="legacy.imported",
                        command_id=command_id,
                        payload={
                            "migration_id": migration_id,
                            "receipt_path": str(receipt_path),
                            "migration_status": "registered_read_only",
                        },
                        projections=["task_record"],
                    )
                    result = {
                        "contract": "paperspine5.command-result",
                        "schema_version": PRODUCT_SCHEMA_VERSION,
                        "task_id": task_id,
                        "command_id": command_id,
                        "status": "accepted",
                        "previous_revision": None,
                        "resulting_revision": 0,
                        "event_sequence": sequence,
                        "replayed": False,
                    }
                    connection.execute(
                        "INSERT INTO commands(command_id,task_id,envelope_json,result_json,created_at) VALUES(?,?,?,?,?)",
                        (command_id, task_id, canonical_request, _canonical_json(result), created_at),
                    )
        except BaseException:
            shutil.rmtree(run_root, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)
        if race_replay_task_id is not None:
            shutil.rmtree(run_root, ignore_errors=True)
            replay_task = self.get_task(race_replay_task_id)
            return {
                "task": replay_task,
                "migration_receipt": load_json(replay_task["legacy"]["migration_receipt"]),
            }
        assert sequence is not None
        self._drain_outbox(task_id=task_id, up_to_sequence=sequence)
        return {"task": self.get_task(task_id), "migration_receipt": receipt}

    def recover_outbox(self) -> int:
        return self._drain_outbox()

    def _acquire_lease(self, connection: sqlite3.Connection, task_id: str, writer_id: str) -> tuple[int, float]:
        now = time.time()
        row = connection.execute("SELECT * FROM leases WHERE task_id=?", (task_id,)).fetchone()
        if row is not None and row["writer_id"] != writer_id and row["expires_at"] > now:
            raise WriterLeaseError(
                f"task writer lease is held by {row['writer_id']} until {row['expires_at']}"
            )
        token = (row["fencing_token"] + 1) if row is not None else 1
        expires_at = now + self.lease_seconds
        connection.execute(
            """INSERT INTO leases(task_id,writer_id,fencing_token,expires_at,updated_at) VALUES(?,?,?,?,?)
               ON CONFLICT(task_id) DO UPDATE SET writer_id=excluded.writer_id,
               fencing_token=excluded.fencing_token,expires_at=excluded.expires_at,updated_at=excluded.updated_at""",
            (task_id, writer_id, token, expires_at, _now()),
        )
        return token, expires_at

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        task_id: str,
        revision: int,
        event_type: str,
        command_id: str | None,
        payload: dict[str, Any],
        projections: list[str],
    ) -> int:
        row = connection.execute("SELECT COALESCE(MAX(sequence),0)+1 AS next_sequence FROM events WHERE task_id=?", (task_id,)).fetchone()
        sequence = int(row["next_sequence"])
        connection.execute(
            "INSERT INTO events(task_id,sequence,revision,event_type,command_id,payload_json,occurred_at) VALUES(?,?,?,?,?,?,?)",
            (task_id, sequence, revision, event_type, command_id, _canonical_json(payload), _now()),
        )
        connection.execute(
            "INSERT INTO outbox(task_id,sequence,projection_json) VALUES(?,?,?)",
            (task_id, sequence, _canonical_json({"projections": projections})),
        )
        return sequence

    def _drain_outbox(self, *, task_id: str | None = None, up_to_sequence: int | None = None) -> int:
        with self._projection_lock:
            with self.store.read_connection() as connection:
                query = "SELECT * FROM outbox WHERE delivered_at IS NULL"
                params: list[Any] = []
                if task_id is not None:
                    query += " AND task_id=?"
                    params.append(task_id)
                if up_to_sequence is not None:
                    query += " AND sequence<=?"
                    params.append(up_to_sequence)
                query += " ORDER BY task_id,sequence"
                rows = connection.execute(query, tuple(params)).fetchall()
            for row in rows:
                try:
                    task = self.get_task(row["task_id"])
                    projections = json.loads(row["projection_json"])["projections"]
                    if "bootstrap" in projections:
                        self._materialize_bootstrap(task)
                    if "task_record" in projections:
                        self._materialize_task_record(task)
                    with self.store.write_transaction() as connection:
                        connection.execute(
                            "UPDATE outbox SET delivered_at=?,last_error=NULL WHERE task_id=? AND sequence=?",
                            (_now(), row["task_id"], row["sequence"]),
                        )
                except Exception as exc:
                    with self.store.write_transaction() as connection:
                        connection.execute(
                            "UPDATE outbox SET last_error=? WHERE task_id=? AND sequence=?",
                            (str(exc), row["task_id"], row["sequence"]),
                        )
            with self.store.read_connection() as connection:
                query = "SELECT COUNT(*) AS count FROM outbox WHERE delivered_at IS NULL"
                params = ()
                if task_id is not None:
                    query += " AND task_id=?"
                    params = (task_id,)
                return int(connection.execute(query, params).fetchone()["count"])

    def _materialize_task_record(self, task: dict[str, Any]) -> None:
        write_json_atomic(Path(task["workspace_root"]) / "task_record.json", task)

    def _materialize_bootstrap(self, task: dict[str, Any]) -> None:
        run_root = Path(task["run_root"])
        (run_root / "paper").mkdir(parents=True, exist_ok=True)
        (run_root / "figures").mkdir(parents=True, exist_ok=True)
        job_path = Path(task["job_path"])
        state_path = Path(task["state_path"])
        if not job_path.exists():
            job = {
                "schema_version": "1.1",
                "job_id": task["task_id"],
                "host": task["host"],
                "project_root": str(run_root),
                "core_root": task["core_root"],
                "paper": {
                    "output_dir": "paper",
                    "progress_script": "01_PaperSpine4/src/scripts/progress_check.py",
                    "figure_requests": "figure_requests.json",
                },
                "figure": {
                    "job_dir": "figures",
                    "figmirror_cli": "02_PaperFigure/01_FigMirror引擎/src/scripts/figmirror.py",
                    "candidate_count": 2,
                    "review_mode": "manual",
                    "review_points": "blueprint_and_final",
                    "preferred_format": "pdf",
                    "fallback_formats": ["svg", "png"],
                    "quality_profile": "publication",
                    "require_candidate_lineage": True,
                },
                "publication": {
                    "script": "01_PaperSpine4/src/scripts/publication_cycle.py",
                    "invocation_dir": "paper/publication_cycle/invocations",
                    "enabled": True,
                },
                "workflow": {"allow_auto_selection": False},
            }
            write_json_atomic(job_path, job)
        if not state_path.exists():
            state = {
                "schema_version": "1.3",
                "job_id": task["task_id"],
                "stage": "initialized",
                "next_action": "Configure the paper task and authorize the next bounded action.",
                "events": [],
                "signals": [],
                "issues": [],
                "context": {
                    "product_task": {
                        "task_id": task["task_id"],
                        "revision": task["revision"],
                        "host": task["host"],
                        "registry_authority": str(self.store.database_path),
                    }
                },
                "updated_at": _now(),
            }
            write_json_atomic(state_path, state)
