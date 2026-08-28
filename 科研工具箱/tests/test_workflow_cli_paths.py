import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import workflow_cli
from engine.audit_store import generate_audit_report
from engine.workflow_store import WorkflowStore


def test_workspace_default_database_is_local_to_workspace(tmp_path):
    workspace = tmp_path / "workspace"

    assert workflow_cli.default_workflow_db(workspace) == workspace / ".engine" / "workflow.sqlite"


def test_workflow_database_registry_resolves_id_without_db_flag(tmp_path, monkeypatch):
    registry = tmp_path / "workflow-index.json"
    database = tmp_path / "workspace" / ".engine" / "workflow.sqlite"
    database.parent.mkdir(parents=True)
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", registry)

    workflow_cli.register_workflow_database("wf-1", database)

    assert workflow_cli.resolve_workflow_db("wf-1") == database.resolve()


def test_checkpoint_database_resolution_searches_registered_databases(tmp_path, monkeypatch):
    registry = tmp_path / "workflow-index.json"
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", registry)
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"
    for path, checkpoint in ((first, "cp-1"), (second, "cp-2")):
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE checkpoints (id TEXT)")
        connection.execute("INSERT INTO checkpoints VALUES (?)", (checkpoint,))
        connection.commit()
        connection.close()
    workflow_cli.register_workflow_database("wf-1", first)
    workflow_cli.register_workflow_database("wf-2", second)

    assert workflow_cli.resolve_checkpoint_db("cp-2") == second.resolve()


def test_audit_report_reads_explicit_workflow_database(tmp_path):
    project_root = tmp_path / "project"
    workspace = tmp_path / "workspace"
    database = tmp_path / "state" / "workflow.sqlite"
    project_root.mkdir()
    workspace.mkdir()
    database.parent.mkdir()
    connection = sqlite3.connect(database)
    connection.executescript(
        "CREATE TABLE events (event_type TEXT, created_at TEXT, payload TEXT);"
        "CREATE TABLE workflow_steps (name TEXT, position INTEGER, status TEXT, updated_at TEXT);"
    )
    connection.execute(
        "INSERT INTO events VALUES (?, ?, ?)",
        ("workflow_started", "2026-08-11T00:00:00Z", json.dumps({"id": "wf-1"})),
    )
    connection.execute(
        "INSERT INTO workflow_steps VALUES (?, ?, ?, ?)",
        ("comp-code", 1, "completed", "2026-08-11T00:00:01Z"),
    )
    connection.commit()
    connection.close()

    report = generate_audit_report(workspace, project_root, workflow_db=database)

    assert report["workflow_database"] == str(database)
    assert report["workflow_events"][0]["type"] == "workflow_started"
    assert report["workflow_steps"][0]["name"] == "comp-code"


def test_final_audit_cli_uses_workspace_default_database(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = workspace / ".engine" / "workflow.sqlite"
    database.parent.mkdir(parents=True)
    paper = workspace / "paper"
    paper.mkdir()
    (paper / "main.pdf").write_bytes(b"pdf")

    with WorkflowStore(database) as store:
        workflow = store.create_workflow("comp_cumcm", {"workspace": str(workspace), "params": {}})
        step = store.add_steps(workflow.id, [{"name": "comp-final-audit", "metadata": {}}])[0]
        store.transition_step(step.id, "running")
        payload = {
            "type": "step_completed",
            "quality_gates": {"checks": {"final_audit": {"ok": True}}},
            "manifest": {"artifacts": [{"path": "paper/main.pdf", "sha256": "b" * 64}]},
        }
        store.transition_step_with_checkpoint(
            workflow.id,
            step.id,
            "completed",
            {"status": "completed", "manifest": payload["manifest"], "quality_gates": payload["quality_gates"]},
            event=payload,
        )

    monkeypatch.setattr(sys, "argv", ["workflow_cli", "final-audit", "--workspace", str(workspace)])

    rc = workflow_cli.main()

    assert rc == 0
    saved = json.loads((workspace / "AUDIT_REPORT.json").read_text(encoding="utf-8"))
    assert saved["delivery_decision"] == "ready"
    assert saved["gate_outcomes"]["final_audit"] == "pass"
