"""SQLite-backed persistence for resumable workflows."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _load(value: str) -> Any:
    return json.loads(value)


def _candidate_event_sha256(candidate_id: str, event_type: str, payload: Any,
                            created_at: str, prev_sha256: str) -> str:
    """Canonical digest for one candidate event (append-only hash chain).

    ``payload`` may be the stored JSON text or an in-memory mapping; the digest
    is always computed over the canonical JSON form of the payload object so
    whitespace/key order cannot create a second valid encoding.
    """
    if isinstance(payload, str):
        try:
            payload_value: Any = json.loads(payload)
        except (TypeError, ValueError):
            payload_value = payload
    elif isinstance(payload, Mapping):
        payload_value = dict(payload)
    else:
        payload_value = payload
    material = _json({
        "candidate_id": str(candidate_id),
        "event_type": str(event_type),
        "payload": payload_value,
        "created_at": str(created_at),
        "prev_sha256": str(prev_sha256),
    })
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


_LEGACY_CANDIDATE_EVENT_INSERT = "INSERT INTO CANDIDATE_EVENTS VALUES (?, ?, ?, ?, ?, ?, ?)"
_CANDIDATE_EVENT_INSERT = (
    "INSERT INTO candidate_events (id, candidate_id, checkpoint_id, step_id, event_type, "
    "payload, created_at, prev_sha256, event_sha256) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


class _WorkflowConnection(sqlite3.Connection):
    """SQLite connection that keeps pre-chain raw inserts chain-consistent.

    Older engine code (and regression fixtures) used
    ``INSERT INTO candidate_events VALUES (?, ...7 values)``.  A plain SQLite
    INSERT cannot omit the two additive chain columns, so this compatibility
    shim upgrades exactly that legacy statement shape and computes the digest
    through the same helper as the store's normal insert path.  Direct
    ``sqlite3.connect`` writes still bypass the engine entirely (documented
    malicious-local-process residual).
    """

    def execute(self, sql: str, parameters: Any = (), /) -> sqlite3.Cursor:
        upgraded = _upgrade_legacy_candidate_event_insert(self, sql, parameters)
        if upgraded is not None:
            return super().execute(_CANDIDATE_EVENT_INSERT, upgraded)
        return super().execute(sql, parameters)


def _upgrade_legacy_candidate_event_insert(connection: sqlite3.Connection, sql: str,
                                           parameters: Any) -> tuple[Any, ...] | None:
    text = " ".join(str(sql or "").split()).rstrip(";")
    if text.upper() != _LEGACY_CANDIDATE_EVENT_INSERT:
        return None
    try:
        values = tuple(parameters)
    except TypeError:
        return None
    if len(values) != 7:
        return None
    event_id, candidate_id, checkpoint_id, step_id, event_type, payload, created_at = values
    payload_text = payload if isinstance(payload, str) else _json(payload)
    try:
        row = connection.execute(
            "SELECT event_sha256 FROM candidate_events WHERE candidate_id=? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (candidate_id,)).fetchone()
    except sqlite3.Error:
        return None
    prev_sha256 = str(row[0] or "") if row is not None else ""
    digest = _candidate_event_sha256(candidate_id, event_type, payload_text, created_at, prev_sha256)
    return (event_id, candidate_id, checkpoint_id, step_id, event_type, payload_text,
            created_at, prev_sha256, digest)


def _normalize_candidate_event(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Accept both {event_type,...} and {type,...} candidate event spellings."""
    if value is None:
        return None
    data = dict(value)
    data["event_type"] = str(data.get("event_type") or data.get("type") or "")
    if not isinstance(data.get("payload"), Mapping):
        data["payload"] = {}
    return data


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Workflow:
    id: str
    name: str
    status: str
    metadata: dict[str, Any]
    created_at: str
    updated_at: str
    steps: list[WorkflowStep] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    workflow_id: str
    name: str
    position: int
    status: StepStatus
    metadata: dict[str, Any]
    updated_at: str
    revision: int = 0
    attempt_id: str = ""


@dataclass(frozen=True)
class Checkpoint:
    id: str
    workflow_id: str
    step_id: str
    state: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class Artifact:
    id: str
    workflow_id: str
    checkpoint_id: str
    name: str
    path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    id: str
    workflow_id: str
    checkpoint_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class ResumeCandidate:
    workflow_id: str
    step_id: str
    checkpoint: Checkpoint
    artifacts: list[Artifact]
    events: list[Event]


CANDIDATE_STATUSES = ("not_ready", "in_delivery", "ready", "superseded", "abandoned")

_CANDIDATE_TRANSITIONS = {
    "not_ready": {"in_delivery", "superseded", "abandoned"},
    "in_delivery": {"ready", "superseded", "abandoned"},
    "ready": {"superseded"},
    "superseded": set(),
    "abandoned": set(),
}


@dataclass(frozen=True)
class DeliveryCandidate:
    """Frozen promotion record; roots/inputs/acceptance never change after insert."""

    id: str
    source_workflow_id: str
    source_step_id: str
    source_attempt_id: str
    delivery_workflow_id: str
    status: str
    logical_target: str
    roots: list[dict[str, Any]]
    inputs: dict[str, Any]
    frozen_versions: dict[str, str]
    lineage: dict[str, Any]
    recipe: dict[str, Any]
    acceptance: dict[str, Any]
    acceptance_sha256: str
    release_id: str
    release_report_path: str
    missing: list[str]
    created_by: str
    created_at: str
    updated_at: str

    @property
    def candidate_id(self) -> str:
        """Alias used by readiness/report callers."""
        return self.id


@dataclass(frozen=True)
class CandidateEvent:
    id: str
    candidate_id: str
    checkpoint_id: str
    step_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: str


_TRANSITIONS = {
    StepStatus.PENDING: {StepStatus.RUNNING, StepStatus.BLOCKED},
    StepStatus.RUNNING: {StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.BLOCKED},
    StepStatus.FAILED: {StepStatus.RUNNING},
    StepStatus.BLOCKED: {StepStatus.RUNNING, StepStatus.COMPLETED},  # M3: 检查点批准后原子转 COMPLETED
    StepStatus.COMPLETED: set(),
}


class WorkflowStore:
    def __init__(self, db_path: str | Path, *, read_only: bool = False):
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        target = Path(db_path).resolve().as_uri() + "?mode=ro" if read_only else self.db_path
        self._connection = sqlite3.connect(target, uri=read_only, timeout=30,
                                           check_same_thread=False, factory=_WorkflowConnection)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA busy_timeout = 30000")
        if read_only:
            self._connection.execute("BEGIN")  # A consistent snapshot, no migrations or writes.
        else:
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._initialize()

    def __enter__(self) -> "WorkflowStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def _initialize(self) -> None:
        self._connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL,
                metadata TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workflow_steps (
                id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(id),
                name TEXT NOT NULL, position INTEGER NOT NULL, status TEXT NOT NULL,
                metadata TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(id),
                step_id TEXT NOT NULL REFERENCES workflow_steps(id), state TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(id),
                checkpoint_id TEXT NOT NULL REFERENCES checkpoints(id), name TEXT NOT NULL,
                path TEXT NOT NULL, metadata TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS completion_receipts (
                workflow_id TEXT NOT NULL REFERENCES workflows(id), request_id TEXT NOT NULL,
                step_id TEXT NOT NULL REFERENCES workflow_steps(id), payload_hash TEXT NOT NULL,
                response TEXT NOT NULL, PRIMARY KEY(workflow_id, request_id)
            );
            CREATE TABLE IF NOT EXISTS execution_operations (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL REFERENCES workflows(id),
                step_id TEXT NOT NULL REFERENCES workflow_steps(id),
                attempt_id TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
                node_key TEXT NOT NULL, cache_key TEXT NOT NULL,
                payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS execution_cache_lookup
                ON execution_operations(cache_key, status);
            CREATE INDEX IF NOT EXISTS execution_attempt_lookup
                ON execution_operations(step_id, attempt_id);
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(id),
                checkpoint_id TEXT NOT NULL REFERENCES checkpoints(id), event_type TEXT NOT NULL,
                payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS delivery_candidates (
                id TEXT PRIMARY KEY,
                source_workflow_id TEXT NOT NULL REFERENCES workflows(id),
                source_step_id TEXT NOT NULL REFERENCES workflow_steps(id),
                source_attempt_id TEXT NOT NULL,
                delivery_workflow_id TEXT,
                status TEXT NOT NULL,
                logical_target TEXT NOT NULL,
                roots_json TEXT NOT NULL,
                inputs_json TEXT NOT NULL,
                frozen_versions_json TEXT NOT NULL,
                lineage_json TEXT NOT NULL,
                recipe_json TEXT NOT NULL,
                acceptance_json TEXT NOT NULL,
                acceptance_sha256 TEXT NOT NULL,
                release_id TEXT NOT NULL DEFAULT '',
                release_report_path TEXT NOT NULL DEFAULT '',
                missing_json TEXT NOT NULL DEFAULT '[]',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS delivery_candidate_source
                ON delivery_candidates(source_workflow_id, logical_target, status);
            CREATE TABLE IF NOT EXISTS candidate_events (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL REFERENCES delivery_candidates(id),
                checkpoint_id TEXT NOT NULL REFERENCES checkpoints(id),
                step_id TEXT NOT NULL REFERENCES workflow_steps(id),
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                prev_sha256 TEXT NOT NULL DEFAULT '',
                event_sha256 TEXT NOT NULL DEFAULT '',
                UNIQUE(candidate_id, checkpoint_id, event_type)
            );
            CREATE INDEX IF NOT EXISTS candidate_approval_binding
                ON candidate_events(candidate_id, checkpoint_id, step_id, event_type);
            """
        )
        # Additive migration: existing workspace databases and their history stay intact.
        columns = {row[1] for row in self._connection.execute("PRAGMA table_info(workflow_steps)")}
        if "revision" not in columns:
            self._connection.execute("ALTER TABLE workflow_steps ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
        if "attempt_id" not in columns:
            self._connection.execute("ALTER TABLE workflow_steps ADD COLUMN attempt_id TEXT NOT NULL DEFAULT ''")
        # Additive hash-chain migration: legacy databases gain the two columns and
        # a one-time baseline chain over their existing candidate events.  The
        # backfill runs only when a column was just added, so later blank hashes
        # are never silently repaired (they are tamper evidence).
        candidate_columns = {row[1] for row in
                             self._connection.execute("PRAGMA table_info(candidate_events)")}
        chain_columns_added = False
        for column in ("prev_sha256", "event_sha256"):
            if column not in candidate_columns:
                self._connection.execute(
                    f"ALTER TABLE candidate_events ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
                chain_columns_added = True
        if chain_columns_added:
            self._backfill_candidate_event_chain()
        self._connection.commit()

    def _backfill_candidate_event_chain(self) -> None:
        """Anchor legacy rows into a baseline chain during additive migration."""
        candidate_ids = [row[0] for row in self._connection.execute(
            "SELECT DISTINCT candidate_id FROM candidate_events")]
        for candidate_id in candidate_ids:
            previous = ""
            rows = self._connection.execute(
                "SELECT id, event_type, payload, created_at FROM candidate_events "
                "WHERE candidate_id=? ORDER BY created_at, rowid", (candidate_id,)).fetchall()
            for row in rows:
                digest = _candidate_event_sha256(
                    candidate_id, row["event_type"], row["payload"], row["created_at"], previous)
                self._connection.execute(
                    "UPDATE candidate_events SET prev_sha256=?, event_sha256=? WHERE id=?",
                    (previous, digest, row["id"]))
                previous = digest

    def create_workflow(self, name: str, metadata: Mapping[str, Any] | None = None,
                        *, candidate_id: str = "") -> Workflow:
        """Create a workflow; candidate binding and status transition are atomic.

        A candidate-bound delivery workflow is created and the candidate moves
        ``not_ready -> in_delivery`` in one ``BEGIN IMMEDIATE`` transaction, so a
        crash cannot produce a half-bound workflow or a half-bound candidate.
        """
        workflow_id, timestamp = str(uuid4()), _now()
        payload = dict(metadata or {})
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                if candidate_id:
                    candidate = self._connection.execute(
                        "SELECT status, delivery_workflow_id FROM delivery_candidates WHERE id=?",
                        (candidate_id,)).fetchone()
                    if candidate is None:
                        raise KeyError(f"unknown delivery candidate: {candidate_id}")
                    if candidate["status"] != "not_ready" or candidate["delivery_workflow_id"]:
                        raise ValueError("delivery candidate is not available for binding")
                self._connection.execute(
                    "INSERT INTO workflows VALUES (?, ?, ?, ?, ?, ?)",
                    (workflow_id, name, "active", _json(payload), timestamp, timestamp),
                )
                if candidate_id:
                    updated = self._connection.execute(
                        "UPDATE delivery_candidates SET status='in_delivery', delivery_workflow_id=?, "
                        "updated_at=? WHERE id=? AND status='not_ready' "
                        "AND (delivery_workflow_id IS NULL OR delivery_workflow_id='')",
                        (workflow_id, timestamp, candidate_id))
                    if updated.rowcount != 1:
                        raise ValueError("delivery candidate status changed during binding")
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return Workflow(workflow_id, name, "active", payload, timestamp, timestamp)

    def add_steps(self, workflow_id: str, steps: Iterable[Mapping[str, Any]]) -> list[WorkflowStep]:
        result = []
        for index, spec in enumerate(steps):
            step_id, timestamp = str(uuid4()), _now()
            position = int(spec.get("position", index))
            metadata = dict(spec.get("metadata", {}))
            self._connection.execute(
                "INSERT INTO workflow_steps (id, workflow_id, name, position, status, metadata, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (step_id, workflow_id, str(spec["name"]), position, StepStatus.PENDING.value, _json(metadata), timestamp),
            )
            result.append(WorkflowStep(step_id, workflow_id, str(spec["name"]), position, StepStatus.PENDING, metadata, timestamp))
        self._connection.commit()
        return result

    def transition_step(self, step_id: str, status: StepStatus | str) -> WorkflowStep:
        """Claim/change a step under the same writer lock as checkpoint commits."""
        target = StepStatus(status)
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = self._connection.execute("SELECT * FROM workflow_steps WHERE id = ?", (step_id,)).fetchone()
                if row is None:
                    raise KeyError(f"unknown step: {step_id}")
                current = StepStatus(row["status"])
                if target not in _TRANSITIONS[current]:
                    raise ValueError(f"invalid step transition: {current.value} -> {target.value}")
                attempt_id = str(uuid4()) if target == StepStatus.RUNNING else row["attempt_id"]
                self._connection.execute(
                    "UPDATE workflow_steps SET status = ?, updated_at = ?, revision = revision + 1, attempt_id = ? WHERE id = ?",
                    (target.value, _now(), attempt_id, step_id),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return self.get_step(step_id)

    def get_workflow(self, workflow_id: str) -> Workflow:
        row = self._connection.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown workflow: {workflow_id}")
        return Workflow(row["id"], row["name"], row["status"], _load(row["metadata"]),
                        row["created_at"], row["updated_at"])

    def get_step(self, step_id: str) -> WorkflowStep:
        row = self._connection.execute("SELECT * FROM workflow_steps WHERE id = ?", (step_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown step: {step_id}")
        return self._step_from_row(row)

    def complete_workflow(self, workflow_id: str) -> None:
        """Record terminal workflow completion after every step is completed."""
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                remaining = self._connection.execute(
                    "SELECT COUNT(*) FROM workflow_steps WHERE workflow_id = ? AND status != 'completed'",
                    (workflow_id,),
                ).fetchone()[0]
                if remaining:
                    raise ValueError(f"workflow has {remaining} incomplete steps")
                updated = self._connection.execute(
                    "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ? AND status = 'active'",
                    ("completed", _now(), workflow_id),
                )
                if updated.rowcount != 1:
                    row = self._connection.execute("SELECT status FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
                    if row is None or row[0] != "completed":
                        raise KeyError(f"active workflow not found: {workflow_id}")
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def create_checkpoint(
        self,
        workflow_id: str,
        step_id: str,
        state: Mapping[str, Any],
        artifacts: Iterable[Mapping[str, Any]] | None = None,
        event: Mapping[str, Any] | None = None,
        *,
        approval_checkpoint_id: str = "",
        candidate_event: Mapping[str, Any] | None = None,
    ) -> Checkpoint:
        """Create a checkpoint; candidate approvals run through the store guard.

        ``candidate_event`` is never a bypass: a ``candidate_approved`` event may
        only be written by the approval guard through the private recorder.
        """
        checkpoint_id, timestamp = str(uuid4()), _now()
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                workflow_row = self._connection.execute(
                    "SELECT metadata FROM workflows WHERE id=?", (workflow_id,)).fetchone()
                if workflow_row is None:
                    raise KeyError(f"unknown workflow: {workflow_id}")
                workflow_metadata = _load(workflow_row["metadata"])
                candidate_id = self._candidate_id_from_metadata(workflow_metadata)
                event_payload = dict(event) if event else None
                candidate_payload = _normalize_candidate_event(candidate_event)
                if candidate_payload is not None:
                    if not candidate_id:
                        raise ValueError("candidate events require a candidate-bound workflow")
                    if candidate_payload.get("event_type") == "candidate_approved":
                        raise ValueError("candidate_approved must be written by the approval guard")
                needs_guard = bool(candidate_payload) or bool(
                    event_payload and event_payload.get("type") == "checkpoint_approved"
                    and candidate_id)
                if needs_guard:
                    self._assert_candidate_approval_allowed(
                        workflow_id=workflow_id, step_id=step_id,
                        approval_checkpoint_id=approval_checkpoint_id,
                        transition_checkpoint_id=checkpoint_id,
                        candidate_id=str((candidate_payload or {}).get("candidate_id") or candidate_id),
                        approved_by=str((candidate_payload or {}).get("approved_by")
                                        or ((candidate_payload or {}).get("payload") or {}).get("approved_by")
                                        or (event_payload or {}).get("approved_by") or ""),
                        event_type=str((candidate_payload or {}).get("event_type")
                                       or (event_payload or {}).get("type") or ""),
                        event_payload=candidate_payload or event_payload or {})
                self._connection.execute(
                    "INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?)",
                    (checkpoint_id, workflow_id, step_id, _json(dict(state)), timestamp))
                for artifact in artifacts or []:
                    self._connection.execute(
                        "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid4()), workflow_id, checkpoint_id, str(artifact["name"]),
                         str(artifact["path"]), _json(dict(artifact.get("metadata", {})))))
                if event_payload:
                    self._connection.execute(
                        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid4()), workflow_id, checkpoint_id,
                         str(event_payload.get("type", "checkpoint_created")),
                         _json(event_payload), timestamp))
                if candidate_payload:
                    self._insert_candidate_event(
                        candidate_id=str(candidate_payload.get("candidate_id") or candidate_id),
                        checkpoint_id=approval_checkpoint_id or checkpoint_id,
                        step_id=step_id,
                        event_type=str(candidate_payload["event_type"]),
                        payload=candidate_payload.get("payload", {}),
                        timestamp=timestamp,
                    )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return Checkpoint(checkpoint_id, workflow_id, step_id, dict(state), timestamp)

    def transition_step_with_checkpoint(
        self,
        workflow_id: str,
        step_id: str,
        status: StepStatus | str,
        state: Mapping[str, Any],
        artifacts: Iterable[Mapping[str, Any]] | None = None,
        event: Mapping[str, Any] | None = None,
        *,
        expected_revision: int | None = None,
        expected_checkpoint_id: str | None = None,
        receipt: Mapping[str, Any] | None = None,
        prepare_evidence: Callable[[], None] | None = None,
        finalize_if_complete: bool = False,
        approval_checkpoint_id: str = "",
        candidate_event: Mapping[str, Any] | None = None,
    ) -> tuple[WorkflowStep, Checkpoint]:
        """Atomically transition a versioned step and persist its checkpoint evidence.

        Candidate approvals are validated by ``approvals.assert_candidate_approval_allowed``
        inside this same transaction; the new transition checkpoint is linked to the
        old blocked checkpoint through ``approved_checkpoint_id`` in the event payload.
        """
        target = StepStatus(status)
        checkpoint_id, timestamp = str(uuid4()), _now()
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = self._connection.execute(
                    "SELECT * FROM workflow_steps WHERE id = ? AND workflow_id = ?",
                    (step_id, workflow_id),
                ).fetchone()
                if row is None:
                    raise KeyError(f"unknown step: {step_id}")
                workflow_row = self._connection.execute(
                    "SELECT metadata FROM workflows WHERE id=?", (workflow_id,)).fetchone()
                if workflow_row is None:
                    raise KeyError(f"unknown workflow: {workflow_id}")
                workflow_metadata = _load(workflow_row["metadata"])
                candidate_id = self._candidate_id_from_metadata(workflow_metadata)
                event_payload = dict(event) if event else None
                candidate_payload = _normalize_candidate_event(candidate_event)
                if candidate_payload is not None:
                    if not candidate_id:
                        raise ValueError("candidate events require a candidate-bound workflow")
                    # candidate_approved is accepted here only after the approval
                    # guard below has validated the old checkpoint / L1 evidence.
                needs_guard = bool(candidate_payload) or bool(
                    event_payload and event_payload.get("type") == "checkpoint_approved"
                    and candidate_id)
                if needs_guard:
                    if event_payload and event_payload.get("type") == "checkpoint_approved":
                        bound = str(event_payload.get("approved_checkpoint_id") or "")
                        if bound != approval_checkpoint_id:
                            raise ValueError(
                                "checkpoint_approved payload must bind the old blocked checkpoint")
                    self._assert_candidate_approval_allowed(
                        workflow_id=workflow_id, step_id=step_id,
                        approval_checkpoint_id=approval_checkpoint_id,
                        transition_checkpoint_id=checkpoint_id,
                        candidate_id=str((candidate_payload or {}).get("candidate_id") or candidate_id),
                        approved_by=str((candidate_payload or {}).get("approved_by")
                                        or ((candidate_payload or {}).get("payload") or {}).get("approved_by")
                                        or (event_payload or {}).get("approved_by") or ""),
                        event_type=str((candidate_payload or {}).get("event_type")
                                       or (event_payload or {}).get("type") or ""),
                        event_payload=candidate_payload or event_payload or {})
                current = StepStatus(row["status"])
                if target not in _TRANSITIONS[current]:
                    raise ValueError(f"invalid step transition: {current.value} -> {target.value}")
                if expected_revision is not None and row["revision"] != expected_revision:
                    raise ValueError("stale step revision")
                if expected_checkpoint_id is not None:
                    latest = self._connection.execute(
                        "SELECT id, state FROM checkpoints WHERE step_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                        (step_id,),
                    ).fetchone()
                    if (current != StepStatus.BLOCKED or latest is None
                            or latest["id"] != expected_checkpoint_id
                            or _load(latest["state"]).get("status") != "waiting_checkpoint"):
                        raise ValueError("stale or non-waiting checkpoint")
                if receipt and self.completion_receipt(workflow_id, str(receipt["request_id"]), str(receipt["payload_hash"])) is not None:
                    raise ValueError("completion already committed")
                # External evidence is prepared only after the CAS/receipt checks,
                # while this DB writer lock excludes competing engine submissions.
                # Unique immutable paths make crash leftovers non-authoritative.
                if prepare_evidence is not None:
                    prepare_evidence()
                attempt_id = str(uuid4()) if target == StepStatus.RUNNING else row["attempt_id"]
                self._connection.execute(
                    "UPDATE workflow_steps SET status = ?, updated_at = ?, revision = revision + 1, attempt_id = ? WHERE id = ?",
                    (target.value, timestamp, attempt_id, step_id),
                )
                self._connection.execute(
                    "INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?)",
                    (checkpoint_id, workflow_id, step_id, _json(dict(state)), timestamp),
                )
                for artifact in artifacts or []:
                    self._connection.execute(
                        "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid4()), workflow_id, checkpoint_id, str(artifact["name"]),
                         str(artifact["path"]), _json(dict(artifact.get("metadata", {})))),
                    )
                if event:
                    payload = dict(event)
                    self._connection.execute(
                        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid4()), workflow_id, checkpoint_id,
                         str(payload.get("type", "checkpoint_created")), _json(payload), timestamp),
                    )
                if candidate_payload:
                    self._insert_candidate_event(
                        candidate_id=str(candidate_payload.get("candidate_id") or candidate_id),
                        checkpoint_id=approval_checkpoint_id or checkpoint_id,
                        step_id=step_id,
                        event_type=str(candidate_payload["event_type"]),
                        payload=candidate_payload.get("payload", {}),
                        timestamp=timestamp,
                    )
                if receipt:
                    response = dict(receipt["response"])
                    if response.get("status") == "completed":
                        remaining = self._connection.execute(
                            "SELECT COUNT(*) FROM workflow_steps WHERE workflow_id = ? AND status != 'completed'",
                            (workflow_id,),
                        ).fetchone()[0]
                        if remaining:
                            raise ValueError("cannot complete workflow with incomplete steps")
                        self._connection.execute(
                            "UPDATE workflows SET status = 'completed', updated_at = ? WHERE id = ?",
                            (timestamp, workflow_id),
                        )
                    response["checkpoint_id"] = checkpoint_id
                    self._connection.execute(
                        "INSERT INTO completion_receipts VALUES (?, ?, ?, ?, ?)",
                        (workflow_id, receipt["request_id"], step_id, receipt["payload_hash"], _json(response)),
                    )
                if finalize_if_complete and target == StepStatus.COMPLETED:
                    self._connection.execute(
                        "UPDATE workflows SET status = 'completed', updated_at = ? "
                        "WHERE id = ? AND status = 'active' AND NOT EXISTS ("
                        "SELECT 1 FROM workflow_steps WHERE workflow_id = ? AND status != 'completed')",
                        (timestamp, workflow_id, workflow_id),
                    )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        step = WorkflowStep(row["id"], row["workflow_id"], row["name"], row["position"],
                            target, _load(row["metadata"]), timestamp, row["revision"] + 1, attempt_id)
        checkpoint = Checkpoint(checkpoint_id, workflow_id, step_id, dict(state), timestamp)
        return step, checkpoint

    def completion_receipt(self, workflow_id: str, request_id: str, payload_hash: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT payload_hash, response FROM completion_receipts WHERE workflow_id = ? AND request_id = ?",
            (workflow_id, request_id),
        ).fetchone()
        if row is None:
            return None
        if row["payload_hash"] != payload_hash:
            raise ValueError("request_id reused with a different payload")
        return _load(row["response"])

    def begin_operation(self, workflow_id: str, step_id: str, attempt_id: str,
                        revision: int, kind: str, node_key: str,
                        payload: Mapping[str, Any], cache_key: str = "") -> str:
        """在真实操作前持久化意图；崩溃后的 running 记录绝不作为成功证据。"""
        operation_id, timestamp = str(uuid4()), _now()
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                workflow_status = self._connection.execute(
                    "SELECT status FROM workflows WHERE id=?", (workflow_id,)).fetchone()
                if workflow_status is None or workflow_status["status"] != "active":
                    raise ValueError("stale execution operation target")
                step = self.get_step(step_id)
                if (step.workflow_id != workflow_id or step.status != StepStatus.RUNNING
                        or step.attempt_id != attempt_id or step.revision != revision):
                    raise ValueError("stale execution operation target")
                if kind in {"command", "write", "review"}:
                    active = self._connection.execute(
                        "SELECT 1 FROM execution_operations WHERE workflow_id=? AND kind IN ('command','write','review') "
                        "AND status='running' LIMIT 1", (workflow_id,)).fetchone()
                    if active:
                        raise ValueError("execution already running; inspect interruption before retry")
                self._connection.execute(
                    "INSERT INTO execution_operations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (operation_id, workflow_id, step_id, attempt_id, kind, "running", node_key,
                     cache_key, _json(dict(payload)), timestamp, timestamp))
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return operation_id

    def finish_operation(self, operation_id: str, status: str, payload: Mapping[str, Any]) -> None:
        if status not in {"succeeded", "failed", "reused"}:
            raise ValueError("invalid execution operation outcome")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = self._connection.execute(
                    "SELECT o.status AS operation_status, w.status AS workflow_status "
                    "FROM execution_operations o JOIN workflows w ON w.id = o.workflow_id "
                    "WHERE o.id=?", (operation_id,)).fetchone()
                if row is None or row["operation_status"] != "running":
                    raise ValueError("execution operation is absent or already finalized")
                # After abandon/completion an operation may still be closed as failed
                # (interruption recovery), but it can never become a new success fact.
                if status in {"succeeded", "reused"} and row["workflow_status"] != "active":
                    raise ValueError("workflow is no longer active; operation cannot succeed")
                changed = self._connection.execute(
                    "UPDATE execution_operations SET status=?, payload=?, updated_at=? "
                    "WHERE id=? AND status='running'",
                    (status, _json(dict(payload)), _now(), operation_id))
                if changed.rowcount != 1:
                    raise ValueError("execution operation is absent or already finalized")
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def execution_operations(self, step_id: str, attempt_id: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            "SELECT * FROM execution_operations WHERE step_id=? AND attempt_id=? ORDER BY rowid",
            (step_id, attempt_id)).fetchall()
        return [{**dict(row), "payload": _load(row["payload"])} for row in rows]

    def current_operations(self, step_id: str, attempt_id: str) -> list[dict[str, Any]]:
        """按逻辑操作折叠到本次尝试最新事实，保留最后发生顺序；历史行不删。"""
        latest = {}
        for row in self.execution_operations(step_id, attempt_id):
            latest.pop(row["node_key"], None)
            latest[row["node_key"]] = row
        return list(latest.values())

    def interrupt_operation(self, operation_id: str, reason: str) -> None:
        """显式确认进程已停后的恢复标记；不伪造退出码或成功。"""
        if not reason.strip():
            raise ValueError("interruption recovery requires a reason")
        row = self._connection.execute("SELECT payload FROM execution_operations WHERE id=? AND status='running'",
                                       (operation_id,)).fetchone()
        if row is None:
            raise ValueError("running operation not found")
        self.finish_operation(operation_id, "failed", {**_load(row["payload"]),
            "error": "explicitly_recovered_interruption", "recovery_reason": reason})

    def reusable_operations(self, cache_key: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            "SELECT * FROM execution_operations WHERE cache_key=? AND kind='command' "
            "AND status='succeeded' ORDER BY rowid DESC LIMIT 10", (cache_key,)).fetchall()
        return [{**dict(row), "payload": _load(row["payload"])} for row in rows]

    # ---------- delivery candidates（G2 promotion / delivery） ----------
    def create_candidate(
        self,
        source_workflow_id: str,
        source_step_id: str,
        source_attempt_id: str,
        roots: Iterable[Mapping[str, Any]],
        inputs: Mapping[str, Any],
        frozen_versions: Mapping[str, str],
        lineage: Mapping[str, Any],
        recipe: Mapping[str, Any],
        acceptance: Mapping[str, Any],
        acceptance_sha256: str,
        *,
        missing: Iterable[str] = (),
        created_by: str = "",
        logical_target: str = "",
        status: str = "not_ready",
    ) -> DeliveryCandidate:
        """Insert a frozen candidate and supersede older candidates of the same target.

        Candidate content columns are insert-only; only status/release fields can
        change through :meth:`set_candidate_status`.
        """
        import hashlib

        if status not in CANDIDATE_STATUSES:
            raise ValueError(f"unknown delivery candidate status: {status}")
        roots_list = [dict(root) for root in roots]
        if not roots_list:
            raise ValueError("delivery candidate requires at least one root")
        logical = logical_target or hashlib.sha256(
            _json(sorted(str(root.get("path", "")) for root in roots_list)).encode("utf-8")).hexdigest()
        candidate_id, timestamp = str(uuid4()), _now()
        missing_list = [str(item) for item in missing]
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                if self._connection.execute(
                        "SELECT 1 FROM workflows WHERE id=?", (source_workflow_id,)).fetchone() is None:
                    raise KeyError(f"unknown source workflow: {source_workflow_id}")
                if self._connection.execute(
                        "SELECT 1 FROM workflow_steps WHERE id=? AND workflow_id=?",
                        (source_step_id, source_workflow_id)).fetchone() is None:
                    raise KeyError(f"unknown source step: {source_step_id}")
                self._connection.execute(
                    "UPDATE delivery_candidates SET status='superseded', updated_at=? "
                    "WHERE source_workflow_id=? AND logical_target=? "
                    "AND status IN ('not_ready','in_delivery','ready')",
                    (timestamp, source_workflow_id, logical))
                self._connection.execute(
                    "INSERT INTO delivery_candidates VALUES "
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (candidate_id, source_workflow_id, source_step_id, source_attempt_id,
                     None, status, logical, _json(roots_list), _json(dict(inputs)),
                     _json(dict(frozen_versions)), _json(dict(lineage)), _json(dict(recipe)),
                     _json(dict(acceptance)), str(acceptance_sha256), "", "",
                     _json(missing_list), str(created_by), timestamp, timestamp))
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return self.get_candidate(candidate_id)

    def get_candidate(self, candidate_id: str) -> DeliveryCandidate:
        row = self._connection.execute(
            "SELECT * FROM delivery_candidates WHERE id=?", (candidate_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown delivery candidate: {candidate_id}")
        return self._candidate_from_row(row)

    def candidates_for_workflow(self, workflow_id: str,
                                *, statuses: Iterable[str] | None = None) -> list[DeliveryCandidate]:
        query = ("SELECT * FROM delivery_candidates WHERE (source_workflow_id=? OR delivery_workflow_id=?)")
        params: list[Any] = [workflow_id, workflow_id]
        if statuses is not None:
            wanted = [str(value) for value in statuses]
            if wanted:
                query += " AND status IN (" + ",".join("?" for _ in wanted) + ")"
                params.extend(wanted)
        query += " ORDER BY created_at, rowid"
        return [self._candidate_from_row(row) for row in
                self._connection.execute(query, params).fetchall()]

    def bind_candidate_workflow(self, candidate_id: str, workflow_id: str) -> DeliveryCandidate:
        """Bind an unbound candidate to an existing delivery workflow (CAS)."""
        timestamp = _now()
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                if self._connection.execute(
                        "SELECT 1 FROM workflows WHERE id=?", (workflow_id,)).fetchone() is None:
                    raise KeyError(f"unknown workflow: {workflow_id}")
                updated = self._connection.execute(
                    "UPDATE delivery_candidates SET status='in_delivery', delivery_workflow_id=?, updated_at=? "
                    "WHERE id=? AND status='not_ready' "
                    "AND (delivery_workflow_id IS NULL OR delivery_workflow_id='')",
                    (workflow_id, timestamp, candidate_id))
                if updated.rowcount != 1:
                    raise ValueError("delivery candidate is not available for binding")
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return self.get_candidate(candidate_id)

    def set_candidate_status(self, candidate_id: str, expected_status: str, new_status: str, *,
                             release_id: str | None = None,
                             release_report_path: str | None = None) -> bool:
        """Compare-and-set candidate status; content columns remain immutable."""
        if expected_status not in CANDIDATE_STATUSES or new_status not in CANDIDATE_STATUSES:
            raise ValueError("unknown delivery candidate status")
        if new_status not in _CANDIDATE_TRANSITIONS[expected_status]:
            raise ValueError(f"invalid candidate transition: {expected_status} -> {new_status}")
        assignments = ["status=?", "updated_at=?"]
        params: list[Any] = [new_status, _now()]
        if release_id is not None:
            assignments.append("release_id=?")
            params.append(str(release_id))
        if release_report_path is not None:
            assignments.append("release_report_path=?")
            params.append(str(release_report_path))
        params.extend([candidate_id, expected_status])
        with self._lock:
            changed = self._connection.execute(
                "UPDATE delivery_candidates SET " + ", ".join(assignments) +
                " WHERE id=? AND status=?", params)
            self._connection.commit()
            return changed.rowcount == 1

    def _record_candidate_event(self, candidate_id: str, checkpoint_id: str, step_id: str,
                                event_type: str, payload: Mapping[str, Any], *,
                                internal_guard: bool = False) -> str:
        """Private recorder; caller owns the SQLite transaction.

        ``candidate_approved`` is only accepted from the approval guard
        (``internal_guard=True``); rejected/degraded events may be recorded by
        engine paths, but still require both checkpoint and step identity.
        """
        if event_type == "candidate_approved" and not internal_guard:
            raise ValueError("candidate_approved must be written by the approval guard")
        if not checkpoint_id or not step_id:
            raise ValueError("candidate events require checkpoint_id and step_id")
        if not self._connection.in_transaction:
            with self._lock:
                try:
                    self._connection.execute("BEGIN IMMEDIATE")
                    event_id = self._insert_candidate_event(
                        candidate_id, checkpoint_id, step_id, event_type, payload, _now())
                    self._connection.commit()
                    return event_id
                except Exception:
                    self._connection.rollback()
                    raise
        return self._insert_candidate_event(candidate_id, checkpoint_id, step_id,
                                           event_type, payload, _now())

    def _insert_candidate_event(self, candidate_id: str, checkpoint_id: str, step_id: str,
                                event_type: str, payload: Mapping[str, Any],
                                timestamp: str | None = None) -> str:
        """Insert without committing; used inside guarded transactions."""
        candidate = self._connection.execute(
            "SELECT delivery_workflow_id FROM delivery_candidates WHERE id=?",
            (candidate_id,)).fetchone()
        if candidate is None:
            raise KeyError(f"unknown delivery candidate: {candidate_id}")
        checkpoint = self._connection.execute(
            "SELECT workflow_id, step_id FROM checkpoints WHERE id=?", (checkpoint_id,)).fetchone()
        if checkpoint is None:
            raise KeyError(f"unknown checkpoint: {checkpoint_id}")
        if checkpoint["step_id"] != step_id:
            raise ValueError("candidate event checkpoint does not belong to the step")
        if candidate["delivery_workflow_id"] and candidate["delivery_workflow_id"] != checkpoint["workflow_id"]:
            raise ValueError("candidate event checkpoint does not belong to the delivery workflow")
        event_id = str(uuid4())
        created_at = timestamp or _now()
        payload_json = _json(dict(payload))
        previous = self._connection.execute(
            "SELECT event_sha256 FROM candidate_events WHERE candidate_id=? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (candidate_id,)).fetchone()
        prev_sha256 = str(previous["event_sha256"] or "") if previous is not None else ""
        event_sha256 = _candidate_event_sha256(
            candidate_id, event_type, payload_json, created_at, prev_sha256)
        self._connection.execute(
            _CANDIDATE_EVENT_INSERT,
            (event_id, candidate_id, checkpoint_id, step_id, event_type,
             payload_json, created_at, prev_sha256, event_sha256))
        return event_id

    def candidate_events(self, candidate_id: str, *, cross_validate: bool = True) -> list[dict[str, Any]]:
        """Return candidate events; optionally mark orphan approvals.

        An orphan ``candidate_approved`` is a candidate event whose
        ``checkpoint_id`` (the old blocked checkpoint) has no matching workflow
        ``checkpoint_approved`` event carrying
        ``payload.approved_checkpoint_id``. The workflow event row itself is
        attached to the new transition checkpoint, so row ids intentionally differ.
        """
        rows = self._connection.execute(
            "SELECT * FROM candidate_events WHERE candidate_id=? ORDER BY created_at, rowid",
            (candidate_id,)).fetchall()
        events = [{"id": row["id"], "candidate_id": row["candidate_id"],
                   "checkpoint_id": row["checkpoint_id"], "step_id": row["step_id"],
                   "event_type": row["event_type"], "payload": _load(row["payload"]),
                   "created_at": row["created_at"],
                   "prev_sha256": row["prev_sha256"], "event_sha256": row["event_sha256"]}
                  for row in rows]
        if cross_validate:
            for event in events:
                event["orphan"] = False
                event["checkpoint_approved_payload"] = None
                if event["event_type"] != "candidate_approved":
                    continue
                matched = False
                for workflow_event in self._connection.execute(
                        "SELECT payload FROM events WHERE workflow_id=? AND event_type='checkpoint_approved'",
                        (self._connection.execute(
                            "SELECT workflow_id FROM checkpoints WHERE id=?",
                            (event["checkpoint_id"],)).fetchone()["workflow_id"],)).fetchall():
                    try:
                        payload = _load(workflow_event["payload"])
                    except (TypeError, ValueError):
                        continue
                    if str(payload.get("approved_checkpoint_id") or "") == event["checkpoint_id"]:
                        matched = True
                        event["checkpoint_approved_payload"] = payload
                        break
                event["orphan"] = not matched
        return events

    def verify_candidate_event_chain(self, candidate_id: str) -> dict[str, Any]:
        """Verify the append-only SHA-256 chain of one candidate's events.

        Rows are linked in ``(created_at, rowid)`` order — the same order used by
        the insert path and :meth:`candidate_events`.  The first row must carry
        ``prev_sha256 == ""``; every later row must point at the previous
        ``event_sha256`` and its own digest must recompute exactly.

        Returns ``{"ok": bool, "broken_at": str | None, "events": int}`` where
        ``broken_at`` is the id of the first non-matching row and ``events`` is
        the total number of events inspected.  A legacy read-only database whose
        chain columns were never migrated fails closed (``broken_at`` names the
        schema problem) instead of pretending the chain is intact.  Tail
        truncation is not detectable from the chain alone; the delivery report
        records :meth:`candidate_event_chain_root` as an external anchor.
        """
        try:
            rows = self._connection.execute(
                "SELECT id, candidate_id, event_type, payload, created_at, "
                "prev_sha256, event_sha256 FROM candidate_events "
                "WHERE candidate_id=? ORDER BY created_at, rowid", (candidate_id,)).fetchall()
        except sqlite3.OperationalError as exc:
            return {"ok": False, "broken_at": f"schema:chain_columns_missing:{exc}",
                    "events": 0}
        expected_prev = ""
        for row in rows:
            stored_prev = str(row["prev_sha256"] or "")
            stored_sha = str(row["event_sha256"] or "")
            if stored_prev != expected_prev:
                return {"ok": False, "broken_at": str(row["id"]), "events": len(rows)}
            recomputed = _candidate_event_sha256(
                str(row["candidate_id"]), str(row["event_type"]), row["payload"],
                str(row["created_at"]), expected_prev)
            if not stored_sha or stored_sha != recomputed:
                return {"ok": False, "broken_at": str(row["id"]), "events": len(rows)}
            expected_prev = stored_sha
        return {"ok": True, "broken_at": None, "events": len(rows)}

    def candidate_event_chain_root(self, candidate_id: str) -> str:
        """Return the last ``event_sha256`` for a candidate ("" when no events)."""
        try:
            row = self._connection.execute(
                "SELECT event_sha256 FROM candidate_events WHERE candidate_id=? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1", (candidate_id,)).fetchone()
        except sqlite3.OperationalError:
            return ""
        return str(row["event_sha256"] or "") if row is not None else ""

    def abandon_workflow(self, workflow_id: str, reason: str, by: str = "") -> Workflow:
        """Abandon a workflow without deleting any execution fact.

        The engine runner restricts this to explore workflows; the store enforces
        non-empty reason and terminal-state safety so old tickets cannot continue.
        """
        if not str(reason).strip():
            raise ValueError("abandon requires a reason")
        timestamp = _now()
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                workflow_row = self._connection.execute(
                    "SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
                if workflow_row is None:
                    raise KeyError(f"unknown workflow: {workflow_id}")
                if workflow_row["status"] != "active":
                    raise ValueError("only an active workflow can be abandoned")
                step = self._connection.execute(
                    "SELECT * FROM workflow_steps WHERE workflow_id=? "
                    "ORDER BY CASE status WHEN 'running' THEN 0 ELSE 1 END, position DESC LIMIT 1",
                    (workflow_id,)).fetchone()
                if step is None:
                    raise ValueError("workflow has no step to anchor the abandonment event")
                operation_count = self._connection.execute(
                    "SELECT COUNT(*) FROM execution_operations WHERE workflow_id=?",
                    (workflow_id,)).fetchone()[0]
                checkpoint_id = str(uuid4())
                state = {"status": "abandoned", "reason": str(reason), "by": str(by)}
                event_payload = {"type": "workflow_abandoned", "reason": str(reason),
                                 "by": str(by), "operation_count": operation_count,
                                 "step": step["name"]}
                self._connection.execute(
                    "UPDATE workflows SET status='abandoned', updated_at=? WHERE id=?",
                    (timestamp, workflow_id))
                self._connection.execute(
                    "INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?)",
                    (checkpoint_id, workflow_id, step["id"], _json(state), timestamp))
                self._connection.execute(
                    "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid4()), workflow_id, checkpoint_id, "workflow_abandoned",
                     _json(event_payload), timestamp))
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return self.get_workflow(workflow_id)

    def resume_candidates(self) -> list[ResumeCandidate]:
        rows = self._connection.execute(
            """SELECT c.* FROM checkpoints c JOIN workflow_steps s ON s.id = c.step_id
               JOIN workflows w ON w.id = c.workflow_id
               WHERE s.status != 'completed' AND w.status NOT IN ('completed','abandoned')
               ORDER BY c.created_at DESC"""
        ).fetchall()
        candidates = []
        for row in rows:
            checkpoint = Checkpoint(row["id"], row["workflow_id"], row["step_id"], _load(row["state"]), row["created_at"])
            artifacts = [Artifact(r["id"], r["workflow_id"], r["checkpoint_id"], r["name"], r["path"], _load(r["metadata"])) for r in self._connection.execute("SELECT * FROM artifacts WHERE checkpoint_id = ?", (row["id"],))]
            events = [Event(r["id"], r["workflow_id"], r["checkpoint_id"], r["event_type"], _load(r["payload"]), r["created_at"]) for r in self._connection.execute("SELECT * FROM events WHERE checkpoint_id = ?", (row["id"],))]
            candidates.append(ResumeCandidate(row["workflow_id"], row["step_id"], checkpoint, artifacts, events))
        return candidates

    def workflow_timeline(self, workflow_id: str) -> dict[str, Any]:
        """Return persisted workflow audit records in chronological order."""
        workflow = self._connection.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        if workflow is None:
            raise KeyError(f"unknown workflow: {workflow_id}")
        checkpoints = self._connection.execute(
            "SELECT * FROM checkpoints WHERE workflow_id = ? ORDER BY created_at, rowid", (workflow_id,)
        ).fetchall()
        events = self._connection.execute(
            "SELECT * FROM events WHERE workflow_id = ? ORDER BY created_at, rowid", (workflow_id,)
        ).fetchall()
        return {
            "workflow": {
                "id": workflow["id"], "name": workflow["name"], "status": workflow["status"],
                "metadata": _load(workflow["metadata"]), "created_at": workflow["created_at"],
                "updated_at": workflow["updated_at"],
            },
            "checkpoints": [
                {"id": row["id"], "step_id": row["step_id"], "state": _load(row["state"]), "created_at": row["created_at"]}
                for row in checkpoints
            ],
            "events": [
                {"id": row["id"], "checkpoint_id": row["checkpoint_id"], "type": row["event_type"],
                 "payload": _load(row["payload"]), "created_at": row["created_at"]}
                for row in events
            ],
        }

    @staticmethod
    def _candidate_id_from_metadata(metadata: Mapping[str, Any] | None) -> str:
        if not isinstance(metadata, Mapping):
            return ""
        candidate = metadata.get("delivery_candidate")
        return str(candidate.get("candidate_id") or "") if isinstance(candidate, Mapping) else ""

    @staticmethod
    def _candidate_from_row(row: sqlite3.Row) -> DeliveryCandidate:
        return DeliveryCandidate(
            id=row["id"], source_workflow_id=row["source_workflow_id"],
            source_step_id=row["source_step_id"], source_attempt_id=row["source_attempt_id"],
            delivery_workflow_id=row["delivery_workflow_id"] or "",
            status=row["status"], logical_target=row["logical_target"],
            roots=_load(row["roots_json"]), inputs=_load(row["inputs_json"]),
            frozen_versions=_load(row["frozen_versions_json"]),
            lineage=_load(row["lineage_json"]), recipe=_load(row["recipe_json"]),
            acceptance=_load(row["acceptance_json"]),
            acceptance_sha256=row["acceptance_sha256"],
            release_id=row["release_id"], release_report_path=row["release_report_path"],
            missing=_load(row["missing_json"]), created_by=row["created_by"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def _assert_candidate_approval_allowed(self, **kwargs: Any) -> None:
        """Delegate to the single approval guard without creating a store import cycle."""
        try:
            from . import approvals
        except ImportError as exc:  # fail-closed: no guard means no candidate approval
            raise ValueError("candidate approval guard is unavailable") from exc
        approvals.assert_candidate_approval_allowed(self, **kwargs)

    @staticmethod
    def _step_from_row(row: sqlite3.Row) -> WorkflowStep:
        return WorkflowStep(
            row["id"], row["workflow_id"], row["name"], row["position"],
            StepStatus(row["status"]), _load(row["metadata"]), row["updated_at"],
            row["revision"], row["attempt_id"]
        )
