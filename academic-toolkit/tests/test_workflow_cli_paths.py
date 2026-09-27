import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))
from engine.contest_profile import resolve_profile  # noqa: E402
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


def test_preflight_fallback_has_no_registry_or_audit_writes(tmp_path, monkeypatch, capsys):
    from engine.workflow_runner import WorkflowRunner
    ws = tmp_path / "workspace"
    registry = tmp_path / "absent-index.json"
    with WorkflowStore(tmp_path / "state.sqlite") as store:
        runner = WorkflowRunner(store, {"demo": {"sub_steps": [{"skill_name": "demo", "output_files": ["out.txt"]}]}}, tmp_path / "skills")
        wf = runner.start("demo", ws, {})
        action = runner.next_action(wf.id).action
        before = store.workflow_timeline(wf.id)
        files = {p: p.read_bytes() for p in ws.rglob("*") if p.is_file()}
        monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", registry)
        monkeypatch.setattr(workflow_cli, "_probe_workflow_db", lambda _: Path(store.db_path))
        def no_write(*args, **kwargs):
            raise AssertionError("preflight attempted a write")
        monkeypatch.setattr(workflow_cli, "register_workflow_database", no_write)
        monkeypatch.setattr(workflow_cli, "_attach_run_logger", no_write)
        monkeypatch.setattr(sys, "argv", ["workflow_cli", "preflight", "--wf", wf.id,
            "--artifacts", "out.txt", "--evidence", json.dumps({"step_id": action.step_id})])
        assert workflow_cli.main() == 1
        report = json.loads(capsys.readouterr().out)
        assert not report["ok"]
        assert not registry.exists()
        assert before == store.workflow_timeline(wf.id)
        assert files == {p: p.read_bytes() for p in ws.rglob("*") if p.is_file()}


def test_final_audit_cli_accepts_bound_candidate_without_committing_it(tmp_path, monkeypatch, capsys):
    from engine.workflow_runner import WorkflowRunner
    from engine.audit_store import AuditStore
    from test_workflow_runner import _reported
    suite = tmp_path / "suite"
    skills = suite / "skills"
    for name in ("solve", "comp-final-audit"):
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_text("fixture skill", encoding="utf-8")
    catalog = {"demo": {"sub_steps": [
        {"skill_name": "solve", "output_files": ["paper.txt"]},
        {"skill_name": "comp-final-audit", "output_files": ["AUDIT_REPORT.json"]}]}}
    config = suite / "engine/modex-core/templates.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(catalog), encoding="utf-8")
    ws = tmp_path / "workspace"
    db = tmp_path / "state.sqlite"
    with WorkflowStore(db) as store:
        runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
        wf = runner.start("demo", ws, {})
        assert runner.complete_step(wf.id, _reported(runner.next_action(wf.id).action)).status == "advanced"
        final = runner.next_action(wf.id).action
        evidence = _reported(final).metadata["execution_evidence"]
        command = f'python tools/verify.py "{ws}"'
        evidence["commands"] = [{"command": command, "returncode": 0, "cwd": "."}]
        evidence["attempt_id"] = final.attempt_id
        evidence["expected_revision"] = final.expected_revision
        ev_path = tmp_path / "candidate.json"
        ev_path.write_text(json.dumps(evidence), encoding="utf-8")
        AuditStore(tmp_path).record({"type": "tool_call", "tool": "bash", "detail": {"command": command}})
        before = store.workflow_timeline(wf.id)
        monkeypatch.setattr(workflow_cli, "ROOT", suite)
        monkeypatch.setattr(sys, "argv", ["workflow_cli", "final-audit", "--workspace", str(ws),
            "--db", str(db), "--wf", wf.id, "--evidence-file", str(ev_path)])
        # Exercise the actual pre-use hook parser/writer, not only handcrafted L1.
        import os
        import subprocess
        control = f'python -m engine.workflow_cli final-audit --workspace "{ws}" --db "{db}" --wf {wf.id} --evidence-file "{ev_path}"'
        hook = subprocess.run([sys.executable, str(ROOT / "hooks/zcode_audit_l1.py"), "pre"],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": control}}),
            text=True, capture_output=True, encoding="utf-8",
            env={**os.environ, "ZCODE_PROJECT_DIR": str(tmp_path)}, check=False)
        assert hook.returncode == 0, hook.stderr
        assert workflow_cli.main() == 0
        capsys.readouterr()
        report = json.loads((ws / "AUDIT_REPORT.json").read_text(encoding="utf-8"))
        assert report["delivery_decision"] == "eligible"
        assert before == store.workflow_timeline(wf.id)
        assert report["candidate_evidence_scope"]["attempt_id"] == final.attempt_id
        assert report["operation_audit_detail"]["workflow_control_calls"][0]["command"] == control
        saved = (ws / "AUDIT_REPORT.json").read_bytes()
        for field, value in (("skill_sha256", "bad"), ("attempt_id", "old-attempt"), ("outputs", 42)):
            ev_path.write_text(json.dumps({**evidence, field: value}), encoding="utf-8")
            assert workflow_cli.main() == 2
            error = json.loads(capsys.readouterr().out)
            assert error["status"] == "error" and "候选预审证据无效" in error["message"]
            assert (ws / "AUDIT_REPORT.json").read_bytes() == saved
            assert before == store.workflow_timeline(wf.id)
        ev_path.write_text(json.dumps(evidence), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["workflow_cli", "backfill", "--wf", wf.id,
            "--db", str(db), "--step", "comp-final-audit", "--artifact", "AUDIT_REPORT.json",
            "--evidence-file", str(ev_path), "--by", "operator"])
        assert workflow_cli.main() == 0
        assert json.loads(capsys.readouterr().out)["status"] == "advanced"  # 保留旧补录 CLI 返回语义
        assert store.get_workflow(wf.id).status == "completed"
        assert json.loads((ws / "DELIVERY_REPORT.json").read_text(encoding="utf-8"))["delivery_decision"] == "ready"


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
        # v2：补 bound 快照（无快照即 pending_binding → unknown → blocked，不冒充）
        meta = workflow.metadata
        meta["contest_profile_snapshot"] = resolve_profile(
            "comp_cumcm", {"contest": {"edition": "2026", "submission_form": "electronic"}}).to_snapshot()
        store._connection.execute("UPDATE workflows SET metadata = ? WHERE id = ?",
                                  (json.dumps(meta), workflow.id))
        store._connection.commit()
        step = store.add_steps(workflow.id, [{"name": "comp-final-audit", "metadata": {}}])[0]
        store.transition_step(step.id, "running")
        payload = {
            "type": "step_completed",
            "quality_gates": {"checks": {"final_audit": {"ok": True}}},
            "manifest": {"artifacts": [{"path": "paper/main.pdf", "sha256": __import__("hashlib").sha256(b"pdf").hexdigest()}]},
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
    saved = json.loads((workspace / "DELIVERY_REPORT.json").read_text(encoding="utf-8"))
    assert saved["delivery_decision"] == "ready"
    assert saved["gate_outcomes"]["final_audit"] == "pass"
