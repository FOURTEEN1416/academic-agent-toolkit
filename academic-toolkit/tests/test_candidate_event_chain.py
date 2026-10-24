"""G2 candidate event hash-chain (tamper-evidence) regression.

The chain is detection, not prevention: a malicious local process with the same
OS user can still rewrite SQLite directly, but it can no longer alter/insert a
candidate event without breaking the recomputable SHA-256 links.  These tests
cover the normal append path, payload tampering, readiness/report blocking and
the additive migration of legacy databases that lack the chain columns.
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.approvals import CandidateApprovalError, assert_candidate_approval_allowed
from engine.audit_store import build_final_audit_report, candidate_readiness
from engine.workflow_store import WorkflowStore


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _event_digest(candidate_id: str, event_type: str, payload, created_at: str,
                  prev_sha256: str) -> str:
    """Independent implementation of the documented digest contract."""
    material = json.dumps({
        "candidate_id": candidate_id,
        "event_type": event_type,
        "payload": payload,
        "created_at": created_at,
        "prev_sha256": prev_sha256,
    }, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _setup(tmp_path: Path) -> SimpleNamespace:
    """Candidate-bound delivery workflow with two real candidate events."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    root_file = workspace / "result.txt"
    root_file.write_text("chain root", encoding="utf-8")
    root_sha = _sha(root_file.read_bytes())
    (workspace / ".engine").mkdir()
    approvers = workspace / ".engine" / "approvers.json"
    approvers.write_text(
        json.dumps({"approvers": ["operator"], "require_human": True}), encoding="utf-8")
    acceptance = {
        "delivery_steps": [],
        "required_reviews": [],
        "reproduction_targets": [],
        "approval_policy": {"approvers": ["operator"], "require_human": True,
                            "config_sha256": _sha(approvers.read_bytes())},
    }
    db_path = tmp_path / "workflow.sqlite"
    store = WorkflowStore(db_path)
    source = store.create_workflow("explore", {"workspace": str(workspace)})
    source_step = store.add_steps(source.id, [{"name": "solve"}])[0]
    candidate = store.create_candidate(
        source_workflow_id=source.id, source_step_id=source_step.id,
        source_attempt_id="attempt-1",
        roots=[{"path": "result.txt", "sha256": root_sha}],
        inputs={},
        frozen_versions={"result.txt": root_sha},
        lineage={"producer_operations": {}, "external_inputs": {}, "unknown_inputs": []},
        recipe={},
        acceptance=acceptance, acceptance_sha256=_canonical_sha(acceptance),
        created_by="tester")
    delivery = store.create_workflow("delivery", {
        "workspace": str(workspace),
        "execution_contract": {"tier": "delivery", "version": 1},
        "delivery_candidate": {"candidate_id": candidate.id,
                               "source_workflow_id": source.id},
    }, candidate_id=candidate.id)
    step = store.add_steps(delivery.id, [{"name": "comp-final-audit"}])[0]
    store.transition_step(step.id, "running")
    checkpoint = store.create_checkpoint(delivery.id, step.id, {"status": "running"})
    store._record_candidate_event(
        candidate.id, checkpoint.id, step.id, "candidate_approval_degraded",
        {"reason": "L1 unavailable", "seq": 1})
    store._record_candidate_event(
        candidate.id, checkpoint.id, step.id, "candidate_approval_rejected",
        {"reason": "self approval", "seq": 2})
    return SimpleNamespace(store=store, workspace=workspace, db_path=db_path,
                           candidate=candidate, delivery=delivery, step=step,
                           checkpoint=checkpoint)


def _rows(store: WorkflowStore, candidate_id: str) -> list[sqlite3.Row]:
    return store._connection.execute(
        "SELECT * FROM candidate_events WHERE candidate_id=? ORDER BY created_at, rowid",
        (candidate_id,)).fetchall()


def _tamper_first_payload(store: WorkflowStore, candidate_id: str) -> str:
    row = _rows(store, candidate_id)[0]
    payload = json.loads(row["payload"])
    payload["forged_after_the_fact"] = True
    store._connection.execute(
        "UPDATE candidate_events SET payload=? WHERE id=?",
        (json.dumps(payload, ensure_ascii=True, sort_keys=True), row["id"]))
    store._connection.commit()
    return str(row["id"])


def test_normal_flow_chain_is_complete(tmp_path):
    setup = _setup(tmp_path)
    try:
        result = setup.store.verify_candidate_event_chain(setup.candidate.id)
        assert result == {"ok": True, "broken_at": None, "events": 2}

        rows = _rows(setup.store, setup.candidate.id)
        assert len(rows) == 2
        previous = ""
        for row in rows:
            assert row["prev_sha256"] == previous
            assert row["event_sha256"] == _event_digest(
                setup.candidate.id, row["event_type"], json.loads(row["payload"]),
                row["created_at"], previous)
            previous = row["event_sha256"]
        assert setup.store.candidate_event_chain_root(setup.candidate.id) == previous
    finally:
        setup.store.close()


def test_payload_tamper_breaks_chain(tmp_path):
    setup = _setup(tmp_path)
    try:
        assert setup.store.verify_candidate_event_chain(setup.candidate.id)["ok"] is True
        broken_id = _tamper_first_payload(setup.store, setup.candidate.id)

        result = setup.store.verify_candidate_event_chain(setup.candidate.id)
        assert result == {"ok": False, "broken_at": broken_id, "events": 2}
    finally:
        setup.store.close()


def test_broken_chain_fails_candidate_readiness_and_report(tmp_path):
    setup = _setup(tmp_path)
    try:
        broken_id = _tamper_first_payload(setup.store, setup.candidate.id)
        chain_root = setup.store.candidate_event_chain_root(setup.candidate.id)

        readiness = candidate_readiness(
            setup.workspace, tmp_path, setup.db_path, setup.candidate.id)
        gate = readiness["gates"]["candidate_event_chain"]
        assert gate["ok"] is False
        assert gate["broken_at"] == broken_id
        assert broken_id in gate["reason"]
        assert readiness["ok"] is False
        assert "candidate_event_chain" in readiness["missing"]
        assert readiness["candidate_chain_root"] == chain_root
        assert readiness["candidate_event_chain"]["ok"] is False

        report = build_final_audit_report(
            setup.workspace, tmp_path, workflow_db=setup.db_path)
        assert report["delivery_decision"] == "blocked"
        assert report["gate_outcomes"]["candidate_event_chain"] == "fail"
        assert report["candidate_chain_root"] == chain_root
        assert report["candidate"]["chain_root"] == chain_root
        assert report["candidate_event_chain"]["broken_at"] == broken_id
    finally:
        setup.store.close()


def test_approval_guard_rejects_broken_chain(tmp_path):
    setup = _setup(tmp_path)
    try:
        broken_id = _tamper_first_payload(setup.store, setup.candidate.id)
        before = len(_rows(setup.store, setup.candidate.id))

        with pytest.raises(CandidateApprovalError) as excinfo:
            assert_candidate_approval_allowed(
                setup.store,
                workflow_id=setup.delivery.id, step_id=setup.step.id,
                approval_checkpoint_id=setup.checkpoint.id,
                transition_checkpoint_id="00000000-0000-0000-0000-000000000000",
                candidate_id=setup.candidate.id, approved_by="operator",
                event_type="candidate_approved",
                event_payload={"payload": {"approved_by": "operator"}})
        message = str(excinfo.value)
        assert "哈希链" in message and broken_id in message
        assert len(_rows(setup.store, setup.candidate.id)) == before
    finally:
        setup.store.close()


def test_legacy_database_without_chain_columns_is_migrated(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    legacy = sqlite3.connect(db_path)
    legacy.executescript(
        """
        CREATE TABLE candidate_events (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            checkpoint_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(candidate_id, checkpoint_id, event_type)
        );
        """)
    legacy.execute(
        "INSERT INTO candidate_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("legacy-event", "cand-legacy", "cp-legacy", "step-legacy",
         "candidate_approval_degraded", '{"reason": "legacy"}',
         "2026-01-01T00:00:00+00:00"))
    legacy.commit()
    legacy.close()

    with WorkflowStore(db_path) as store:
        columns = {row[1] for row in
                   store._connection.execute("PRAGMA table_info(candidate_events)")}
        assert {"prev_sha256", "event_sha256"} <= columns
        assert store.verify_candidate_event_chain("cand-legacy") == {
            "ok": True, "broken_at": None, "events": 1}
        row = store._connection.execute(
            "SELECT * FROM candidate_events WHERE id='legacy-event'").fetchone()
        assert row["prev_sha256"] == ""
        assert row["event_sha256"] == _event_digest(
            "cand-legacy", "candidate_approval_degraded", {"reason": "legacy"},
            "2026-01-01T00:00:00+00:00", "")
