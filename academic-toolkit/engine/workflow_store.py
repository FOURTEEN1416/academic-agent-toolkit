"""SQLite-backed persistence for resumable workflows."""

from __future__ import annotations

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
        self._connection = sqlite3.connect(target, uri=read_only, timeout=30, check_same_thread=False)
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
            """
        )
        # Additive migration: existing workspace databases and their history stay intact.
        columns = {row[1] for row in self._connection.execute("PRAGMA table_info(workflow_steps)")}
        if "revision" not in columns:
            self._connection.execute("ALTER TABLE workflow_steps ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
        if "attempt_id" not in columns:
            self._connection.execute("ALTER TABLE workflow_steps ADD COLUMN attempt_id TEXT NOT NULL DEFAULT ''")
        self._connection.commit()

    def create_workflow(self, name: str, metadata: Mapping[str, Any] | None = None) -> Workflow:
        workflow_id, timestamp = str(uuid4()), _now()
        self._connection.execute(
            "INSERT INTO workflows VALUES (?, ?, ?, ?, ?, ?)",
            (workflow_id, name, "active", _json(dict(metadata or {})), timestamp, timestamp),
        )
        self._connection.commit()
        return Workflow(workflow_id, name, "active", dict(metadata or {}), timestamp, timestamp)

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
    ) -> Checkpoint:
        checkpoint_id, timestamp = str(uuid4()), _now()
        self._connection.execute("INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?)", (checkpoint_id, workflow_id, step_id, _json(dict(state)), timestamp))
        for artifact in artifacts or []:
            self._connection.execute(
                "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid4()), workflow_id, checkpoint_id, str(artifact["name"]), str(artifact["path"]), _json(dict(artifact.get("metadata", {})))),
            )
        if event:
            event_type = str(event.get("type", "checkpoint_created"))
            payload = dict(event)
            self._connection.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)", (str(uuid4()), workflow_id, checkpoint_id, event_type, _json(payload), timestamp))
        self._connection.commit()
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
    ) -> tuple[WorkflowStep, Checkpoint]:
        """Atomically transition a versioned step and persist its checkpoint evidence."""
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
            changed = self._connection.execute(
                "UPDATE execution_operations SET status=?, payload=?, updated_at=? WHERE id=? AND status='running'",
                (status, _json(dict(payload)), _now(), operation_id))
            self._connection.commit()
            if changed.rowcount != 1:
                raise ValueError("execution operation is absent or already finalized")

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

    def resume_candidates(self) -> list[ResumeCandidate]:
        rows = self._connection.execute(
            """SELECT c.* FROM checkpoints c JOIN workflow_steps s ON s.id = c.step_id
               JOIN workflows w ON w.id = c.workflow_id
               WHERE s.status != 'completed' AND w.status != 'completed'
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
    def _step_from_row(row: sqlite3.Row) -> WorkflowStep:
        return WorkflowStep(
            row["id"], row["workflow_id"], row["name"], row["position"],
            StepStatus(row["status"]), _load(row["metadata"]), row["updated_at"],
            row["revision"], row["attempt_id"]
        )
