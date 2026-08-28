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
