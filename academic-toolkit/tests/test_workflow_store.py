import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.workflow_store import (  # noqa: E402
    StepStatus,
    WorkflowStore,
)


def test_store_persists_workflow_steps_and_supporting_records(tmp_path):
    db_path = tmp_path / "workflow.sqlite3"

    with WorkflowStore(db_path) as store:
        workflow = store.create_workflow("modeling", metadata={"team": "A"})
        steps = store.add_steps(
            workflow.id,
            [
                {"name": "collect", "position": 1},
                {"name": "solve", "position": 2},
            ],
        )
        checkpoint = store.create_checkpoint(
            workflow.id,
            step_id=steps[0].id,
            state={"rows": 12},
            artifacts=[{"name": "data.csv", "path": "outputs/data.csv"}],
            event={"type": "checkpoint_created"},
        )

    with WorkflowStore(db_path) as reopened:
        candidates = reopened.resume_candidates()

    assert workflow.name == "modeling"
    assert workflow.metadata == {"team": "A"}
    assert [step.name for step in steps] == ["collect", "solve"]
    assert checkpoint.state == {"rows": 12}
    assert candidates[0].workflow_id == workflow.id
    assert candidates[0].step_id == steps[0].id
    assert candidates[0].artifacts[0].name == "data.csv"
    assert candidates[0].events[0].payload["type"] == "checkpoint_created"


def test_transition_step_allows_valid_transitions_and_rejects_invalid(tmp_path):
    with WorkflowStore(tmp_path / "workflow.sqlite3") as store:
        workflow = store.create_workflow("pipeline")
        step = store.add_steps(workflow.id, [{"name": "run"}])[0]

        transitioned = store.transition_step(step.id, StepStatus.RUNNING)
        completed = store.transition_step(step.id, StepStatus.COMPLETED)

        assert transitioned.status is StepStatus.RUNNING
        assert completed.status is StepStatus.COMPLETED
        with pytest.raises(ValueError, match="invalid step transition"):
            store.transition_step(step.id, StepStatus.RUNNING)


def test_resume_candidates_only_include_incomplete_workflows(tmp_path):
    with WorkflowStore(tmp_path / "workflow.sqlite3") as store:
        incomplete = store.create_workflow("incomplete")
        completed = store.create_workflow("completed")
        incomplete_step = store.add_steps(incomplete.id, [{"name": "run"}])[0]
        completed_step = store.add_steps(completed.id, [{"name": "run"}])[0]
        store.create_checkpoint(incomplete.id, incomplete_step.id, {"ok": True})
        store.transition_step(completed_step.id, StepStatus.RUNNING)
        store.transition_step(completed_step.id, StepStatus.COMPLETED)

        candidates = store.resume_candidates()

    assert [candidate.workflow_id for candidate in candidates] == [incomplete.id]


def test_revision_cas_rejects_stale_completion_without_checkpoint(tmp_path):
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        wf = store.create_workflow("demo")
        step = store.add_steps(wf.id, [{"name": "solve"}])[0]
        running = store.transition_step(step.id, StepStatus.RUNNING)
        assert running.attempt_id and running.revision == 1
        with pytest.raises(ValueError, match="stale step revision"):
            store.transition_step_with_checkpoint(wf.id, step.id, StepStatus.COMPLETED, {}, expected_revision=0)
        assert store.get_step(step.id).status == StepStatus.RUNNING
        assert store.workflow_timeline(wf.id)["checkpoints"] == []
        with pytest.raises(ValueError, match="incomplete"):
            store.complete_workflow(wf.id)


def test_receipt_failure_rolls_back_state_event_and_workflow(tmp_path):
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        wf = store.create_workflow("demo")
        step = store.add_steps(wf.id, [{"name": "solve"}])[0]
        running = store.transition_step(step.id, StepStatus.RUNNING)
        with pytest.raises(KeyError):
            store.transition_step_with_checkpoint(wf.id, step.id, StepStatus.COMPLETED, {},
                event={"type": "step_completed"}, expected_revision=running.revision,
                receipt={"response": {"status": "completed"}})
        assert store.get_step(step.id).status == StepStatus.RUNNING
        timeline = store.workflow_timeline(wf.id)
        assert not timeline["events"] and not timeline["checkpoints"]
        assert timeline["workflow"]["status"] == "active"


@pytest.mark.parametrize("pending_other", [False, True])
def test_finalize_with_checkpoint_is_atomic_and_requires_all_steps(tmp_path, pending_other):
    import sqlite3
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        wf = store.create_workflow("demo")
        step = store.add_steps(wf.id, [{"name": "solve"}])[0]
        if pending_other:
            store.add_steps(wf.id, [{"name": "later", "position": 2}])
        running = store.transition_step(step.id, StepStatus.RUNNING)
        store._connection.execute(
            "CREATE TRIGGER reject_finalization BEFORE UPDATE ON workflows "
            "BEGIN SELECT RAISE(ABORT, 'injected finalization failure'); END")
        store._connection.commit()
        if not pending_other:
            before = store.workflow_timeline(wf.id)
            with pytest.raises(sqlite3.IntegrityError, match="finalization failure"):
                store.transition_step_with_checkpoint(wf.id, step.id, StepStatus.COMPLETED, {},
                    event={"type": "step_backfilled"}, expected_revision=running.revision,
                    finalize_if_complete=True)
            assert store.workflow_timeline(wf.id) == before
            assert store.get_step(step.id).status == StepStatus.RUNNING
        store._connection.execute("DROP TRIGGER reject_finalization")
        store._connection.commit()
        store.transition_step_with_checkpoint(wf.id, step.id, StepStatus.COMPLETED, {},
            event={"type": "step_backfilled"}, expected_revision=running.revision,
            finalize_if_complete=True)
        assert store.workflow_timeline(wf.id)["workflow"]["status"] == (
            "active" if pending_other else "completed")


def test_timeline_same_timestamp_uses_commit_order_not_random_identifiers(tmp_path, monkeypatch):
    import engine.workflow_store as module
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        wf = store.create_workflow("demo")
        step = store.add_steps(wf.id, [{"name": "run"}])[0]
        ids = iter(["z-checkpoint", "z-event", "a-checkpoint", "a-event"])
        monkeypatch.setattr(module, "uuid4", lambda: next(ids))
        first = store.create_checkpoint(wf.id, step.id, {}, event={"type": "first"})
        second = store.create_checkpoint(wf.id, step.id, {}, event={"type": "second"})
        store._connection.execute("UPDATE checkpoints SET created_at = 'same'")
        store._connection.execute("UPDATE events SET created_at = 'same'")
        store._connection.commit()
        timeline = store.workflow_timeline(wf.id)
        assert [c["id"] for c in timeline["checkpoints"]] == [first.id, second.id]
        assert [e["type"] for e in timeline["events"]] == ["first", "second"]


def test_store_enables_wal_and_busy_timeout(tmp_path):
    with WorkflowStore(tmp_path / "workflow.sqlite3") as store:
        journal_mode = store._connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = store._connection.execute("PRAGMA busy_timeout").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert busy_timeout >= 5000


def test_transition_with_checkpoint_is_atomic_on_artifact_failure(tmp_path):
    with WorkflowStore(tmp_path / "workflow.sqlite3") as store:
        workflow = store.create_workflow("pipeline")
        step = store.add_steps(workflow.id, [{"name": "run"}])[0]
        store.transition_step(step.id, StepStatus.RUNNING)

        with pytest.raises(KeyError):
            store.transition_step_with_checkpoint(
                workflow.id,
                step.id,
                StepStatus.COMPLETED,
                {"status": "completed"},
                artifacts=[{"path": "missing-name.txt"}],
                event={"type": "step_completed"},
            )

        status = store._connection.execute(
            "SELECT status FROM workflow_steps WHERE id = ?", (step.id,)
        ).fetchone()[0]
        checkpoints = store._connection.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE step_id = ?", (step.id,)
        ).fetchone()[0]

    assert status == StepStatus.RUNNING.value
    assert checkpoints == 0


def _candidate_payload(store, workflow, step):
    return dict(
        source_workflow_id=workflow.id,
        source_step_id=step.id,
        source_attempt_id="attempt-1",
        roots=[{"path": "paper/main.pdf", "sha256": "a" * 64}],
        inputs={"raw.csv": {"sha256": "b" * 64, "producer_operation_id": None,
                            "kind": "external", "depth": 1}},
        frozen_versions={"paper/main.pdf": "a" * 64, "raw.csv": "b" * 64},
        lineage={"producer_operations": {}, "external_inputs": {"raw.csv": "b" * 64}},
        recipe={"recipe-1": {"argv": ["python", "solve.py"], "cwd": ".",
                             "inputs": ["raw.csv"], "outputs": ["paper/main.pdf"],
                             "mutates": []}},
        acceptance={"delivery_steps": [], "required_reviews": [],
                    "approval_policy": {"approvers": ["operator"], "require_human": True}},
        acceptance_sha256="c" * 64,
        missing=["reproduction", "review", "approval"],
        created_by="tester",
    )


def test_delivery_candidate_lifecycle_and_cas(tmp_path):
    with WorkflowStore(tmp_path / "workflow.sqlite3") as store:
        source = store.create_workflow("explore")
        source_step = store.add_steps(source.id, [{"name": "solve"}])[0]

        candidate = store.create_candidate(**_candidate_payload(store, source, source_step))
        assert candidate.status == "not_ready"
        assert candidate.delivery_workflow_id == ""
        assert candidate.frozen_versions == {"paper/main.pdf": "a" * 64, "raw.csv": "b" * 64}

        delivery = store.create_workflow("delivery", {"workspace": "ws"}, candidate_id=candidate.id)
        bound = store.get_candidate(candidate.id)
        assert bound.status == "in_delivery"
        assert bound.delivery_workflow_id == delivery.id

        assert store.set_candidate_status(candidate.id, "in_delivery", "ready",
                                          release_id="rel-1", release_report_path="releases/rel-1") is True
        ready = store.get_candidate(candidate.id)
        assert ready.status == "ready" and ready.release_id == "rel-1"
        assert ready.roots == candidate.roots and ready.frozen_versions == candidate.frozen_versions
        # Stale CAS can never move an already-ready candidate.
        assert store.set_candidate_status(candidate.id, "in_delivery", "ready") is False
        with pytest.raises(ValueError, match="invalid candidate transition"):
            store.set_candidate_status(candidate.id, "ready", "abandoned")


def test_candidate_binding_is_atomic_and_single_use(tmp_path):
    with WorkflowStore(tmp_path / "workflow.sqlite3") as store:
        source = store.create_workflow("explore")
        source_step = store.add_steps(source.id, [{"name": "solve"}])[0]
        candidate = store.create_candidate(**_candidate_payload(store, source, source_step))
        store.create_workflow("delivery", {}, candidate_id=candidate.id)
        before = store._connection.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
        with pytest.raises(ValueError, match="not available"):
            store.create_workflow("delivery-2", {}, candidate_id=candidate.id)
        after = store._connection.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
        assert after == before
        assert store.get_candidate(candidate.id).status == "in_delivery"


def test_abandon_workflow_excluded_from_resume_and_invalidates_operations(tmp_path):
    with WorkflowStore(tmp_path / "workflow.sqlite3") as store:
        workflow = store.create_workflow("explore", {"execution_contract": {"tier": "explore"}})
        step = store.add_steps(workflow.id, [{"name": "solve"}])[0]
        running = store.transition_step(step.id, StepStatus.RUNNING)
        store.create_checkpoint(workflow.id, step.id, {"status": "running"})
        operation_id = store.begin_operation(
            workflow.id, step.id, running.attempt_id, running.revision,
            "command", "node-1", {"command_record": {"command": "python solve.py"}})
        assert store.resume_candidates()

        abandoned = store.abandon_workflow(workflow.id, "探索方向放弃", by="operator")
        assert abandoned.status == "abandoned"
        assert store.resume_candidates() == []
        assert store._connection.execute(
            "SELECT COUNT(*) FROM execution_operations WHERE workflow_id=?",
            (workflow.id,)).fetchone()[0] == 1
        with pytest.raises(ValueError, match="stale execution operation target"):
            store.begin_operation(workflow.id, step.id, running.attempt_id, running.revision,
                                  "write", "node-2", {})
        with pytest.raises(ValueError, match="no longer active"):
            store.finish_operation(operation_id, "succeeded", {"ok": True})
        # Failed is still allowed so interruption recovery can close the row.
        store.finish_operation(operation_id, "failed", {"error": "abandoned"})
        events = store.workflow_timeline(workflow.id)["events"]
        assert any(event["type"] == "workflow_abandoned" for event in events)
        assert store._connection.execute(
            "SELECT COUNT(*) FROM execution_operations WHERE workflow_id=?",
            (workflow.id,)).fetchone()[0] == 1
