"""SQLite-backed persistence for resumable workflows."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping
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
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA busy_timeout = 30000")
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
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(id),
                checkpoint_id TEXT NOT NULL REFERENCES checkpoints(id), event_type TEXT NOT NULL,
                payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            """
        )
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
                "INSERT INTO workflow_steps VALUES (?, ?, ?, ?, ?, ?, ?)",
                (step_id, workflow_id, str(spec["name"]), position, StepStatus.PENDING.value, _json(metadata), timestamp),
            )
            result.append(WorkflowStep(step_id, workflow_id, str(spec["name"]), position, StepStatus.PENDING, metadata, timestamp))
        self._connection.commit()
        return result

    def transition_step(self, step_id: str, status: StepStatus | str) -> WorkflowStep:
        row = self._connection.execute("SELECT * FROM workflow_steps WHERE id = ?", (step_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown step: {step_id}")
        target = StepStatus(status)
        current = StepStatus(row["status"])
        if target not in _TRANSITIONS[current]:
            raise ValueError(f"invalid step transition: {current.value} -> {target.value}")
        timestamp = _now()
        self._connection.execute("UPDATE workflow_steps SET status = ?, updated_at = ? WHERE id = ?", (target.value, timestamp, step_id))
        self._connection.commit()
        return WorkflowStep(row["id"], row["workflow_id"], row["name"], row["position"], target, _load(row["metadata"]), timestamp)

    def complete_workflow(self, workflow_id: str) -> None:
        """Record terminal workflow completion after every step is completed."""
        timestamp = _now()
        updated = self._connection.execute(
            "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ? AND status = 'active'",
            ("completed", timestamp, workflow_id),
        )
        if updated.rowcount != 1:
            raise KeyError(f"active workflow not found: {workflow_id}")
        self._connection.commit()

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
    ) -> tuple[WorkflowStep, Checkpoint]:
        """Atomically transition a step and persist its checkpoint evidence."""
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
                self._connection.execute(
                    "UPDATE workflow_steps SET status = ?, updated_at = ? WHERE id = ?",
                    (target.value, timestamp, step_id),
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
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        step = WorkflowStep(row["id"], row["workflow_id"], row["name"], row["position"],
                            target, _load(row["metadata"]), timestamp)
        checkpoint = Checkpoint(checkpoint_id, workflow_id, step_id, dict(state), timestamp)
        return step, checkpoint

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
            "SELECT * FROM checkpoints WHERE workflow_id = ? ORDER BY created_at, id", (workflow_id,)
        ).fetchall()
        events = self._connection.execute(
            "SELECT * FROM events WHERE workflow_id = ? ORDER BY created_at, id", (workflow_id,)
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
            StepStatus(row["status"]), _load(row["metadata"]), row["updated_at"]
        )
