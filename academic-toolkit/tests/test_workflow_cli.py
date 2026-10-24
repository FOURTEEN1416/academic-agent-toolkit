import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import workflow_cli
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from execution.session import ExecutionSession


def _session_workspace(tmp_path, monkeypatch, step_name="demo"):
    """最小可驱动工作区：真实 runner 起一步 + context 同构 ticket。"""
    suite = tmp_path / "suite"
    skills = suite / "skills" / step_name
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("fixture skill", encoding="utf-8")
    catalog = {"demo": {"sub_steps": [{"skill_name": step_name, "output_files": ["out.txt"]}]}}
    config = suite / "engine/modex-core/templates.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setattr(workflow_cli, "ROOT", suite)
    db = tmp_path / "state.sqlite"
    store = WorkflowStore(db)
    runner = WorkflowRunner(store, catalog, suite / "skills", audit_root=tmp_path)
    workflow = runner.start("demo", tmp_path / "ws", {})
    action = runner.next_action(workflow.id).action
    ticket = tmp_path / "ws" / ".engine" / "sessions" / f"{action.attempt_id}.json"
    ticket.parent.mkdir(parents=True, exist_ok=True)
    ticket.write_text(json.dumps({
        "database": str(db.resolve()), "workflow_id": workflow.id,
        "step_id": action.step_id, "attempt_id": action.attempt_id,
        "revision": action.expected_revision, "audit_root": str(tmp_path)}), encoding="utf-8")
    return store, runner, workflow, action, ticket, db


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_caps_reports_independent_runtime_capabilities(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "caps"])

    assert workflow_cli.main() == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] in {"suite_runtime", "PATH"}
    assert "guidance" in payload


def test_report_writes_persisted_sqlite_timeline(tmp_path, monkeypatch, capsys):
    db = tmp_path / "workflow.sqlite"
    with WorkflowStore(db) as store:
        workflow = store.create_workflow("demo")
        step = store.add_steps(workflow.id, [{"name": "demo"}])[0]
        store.create_checkpoint(workflow.id, step.id, {"status": "completed"}, event={"type": "step_completed"})
    output = tmp_path / "timeline.json"
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "report", "--wf", workflow.id, "--db", str(db), "--out", str(output)])

    assert workflow_cli.main() == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["workflow"]["id"] == workflow.id
    assert payload["events"][0]["type"] == "step_completed"
    assert capsys.readouterr().out


def test_preflight_session_reads_ticket_without_writing_state(tmp_path, monkeypatch, capsys):
    """preflight --session：引擎取证只读验收，不写证据/清单/工作流状态。"""
    store, _runner, workflow, action, ticket, db = _session_workspace(tmp_path, monkeypatch)
    workspace = Path(workflow.metadata["workspace"])
    before_timeline = store.workflow_timeline(workflow.id)
    before_files = _snapshot(workspace)
    before_db = db.read_bytes()
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "preflight", "--session", str(ticket)])

    assert workflow_cli.main() == 1

    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False, "没有真实操作不得验收通过"
    assert "execution collection" in json.dumps(report, ensure_ascii=False)
    assert store.get_step(action.step_id).status.value == "running"
    assert store.workflow_timeline(workflow.id) == before_timeline
    assert _snapshot(workspace) == before_files
    assert db.read_bytes() == before_db
    store.close()


def test_complete_session_keeps_step_running_when_recorded_work_missing(tmp_path, monkeypatch, capsys):
    """complete --session 走唯一提交路径；取证不足时保持当前步骤可编辑，不写证据。"""
    store, _runner, workflow, action, ticket, _db = _session_workspace(tmp_path, monkeypatch)
    workspace = Path(workflow.metadata["workspace"])
    before_timeline = store.workflow_timeline(workflow.id)
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "complete", "--session", str(ticket)])

    assert workflow_cli.main() == 1

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "needs_work"
    assert store.get_step(action.step_id).status.value == "running"
    assert store.workflow_timeline(workflow.id) == before_timeline
    assert not (workspace / ".engine/evidence").exists()
    assert not (workspace / ".engine/manifests").exists()
    store.close()


def test_final_step_rejects_handbuilt_evidence_without_collection(tmp_path, monkeypatch, capsys):
    """终审复审：手拼 evidence 没有 collection 时拒绝，指向 --session。"""
    store, _runner, workflow, action, _ticket, db = _session_workspace(
        tmp_path, monkeypatch, step_name="comp-final-review")
    evidence = tmp_path / "candidate.json"
    evidence.write_text(json.dumps({
        "schema_version": 1, "step_id": action.step_id,
        "commands": [{"command": "python check.py", "returncode": 0, "cwd": "."}],
        "inputs": [], "outputs": ["out.txt"]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "complete", "--wf", workflow.id,
        "--db", str(db), "--step-id", action.step_id, "--evidence-file", str(evidence)])

    assert workflow_cli.main() == 2

    error = json.loads(capsys.readouterr().out)
    assert error["status"] == "error"
    assert "comp-final-review" in error["message"] and "--session" in error["message"]
    assert store.get_step(action.step_id).status.value == "running"
    store.close()


def test_ordinary_step_keeps_legacy_evidence_path(tmp_path, monkeypatch, capsys):
    """其他步骤保留 legacy 兼容：手拼证据仍进入 runner 验收（不被 CLI 拦截）。"""
    store, _runner, workflow, action, _ticket, db = _session_workspace(tmp_path, monkeypatch)
    evidence = tmp_path / "candidate.json"
    evidence.write_text(json.dumps({
        "schema_version": 1, "step_id": action.step_id,
        "commands": [{"command": "python solve.py", "returncode": 0, "cwd": "."}],
        "inputs": [], "outputs": ["out.txt"]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "complete", "--wf", workflow.id,
        "--db", str(db), "--step-id", action.step_id, "--evidence-file", str(evidence)])

    assert workflow_cli.main() == 1

    output = json.loads(capsys.readouterr().out)
    assert output["status"] != "error", "普通步骤的手拼证据不得被 CLI 层拒绝"
    assert output["status"] in {"failed", "needs_work"}
    store.close()


def test_action_payload_exposes_contract_tier(tmp_path, monkeypatch):
    store, runner, workflow, action, _ticket, _db = _session_workspace(tmp_path, monkeypatch)
    payload = workflow_cli._action_payload(action, contract_tier="explore",
                                           requires_collection=True)
    assert payload["contract_tier"] == "explore"
    assert payload["requires_collection"] is True
    payload = workflow_cli._action_payload(action)
    assert payload["contract_tier"] == "delivery"
    assert payload["requires_collection"] is False
    store.close()


def test_start_parser_has_mode_and_candidate_but_no_approvers():
    parser = workflow_cli._build_parser()
    start_help = next(action for action in parser._actions
                      if getattr(action, "dest", "") == "command").choices["start"].format_help()
    assert "--mode" in start_help and "--candidate" in start_help
    assert "--approvers" not in start_help
    assert "promote-approve" not in parser.format_help()


def test_cli_start_explore_and_abandon(tmp_path, monkeypatch, capsys):
    suite = tmp_path / "suite"
    skills = suite / "skills"
    for name in ("solve", "comp-final-audit"):
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_text("fixture skill", encoding="utf-8")
    catalog = {"demo": {"sub_steps": [
        {"skill_name": "solve", "output_files": ["out.txt"], "has_checkpoint": True,
         "checkpoint_type": "approve"},
        {"skill_name": "comp-final-audit", "output_files": ["AUDIT_REPORT.json"],
         "has_checkpoint": True, "checkpoint_type": "approve",
         "required_checks": ["final_audit"]},
    ]}}
    config = suite / "engine/modex-core/templates.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setattr(workflow_cli, "ROOT", suite)
    workspace = tmp_path / "ws"
    db = tmp_path / "state.sqlite"
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "start", "--template", "demo",
        "--workspace", str(workspace), "--db", str(db), "--mode", "explore"])
    assert workflow_cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    workflow_id = payload["workflow_id"]
    assert payload["execution_contract"]["tier"] == "explore"
    with WorkflowStore(db) as store:
        workflow = store.get_workflow(workflow_id)
        rows = store._connection.execute(
            "SELECT name FROM workflow_steps WHERE workflow_id=? ORDER BY position",
            (workflow_id,)).fetchall()
        assert [row["name"] for row in rows] == ["solve"]
        assert workflow.metadata["execution_contract"]["excluded_steps"] == ["comp-final-audit"]

    monkeypatch.setattr(sys, "argv", ["workflow_cli", "abandon", "--wf", workflow_id,
        "--db", str(db), "--reason", "direction changed", "--by", "operator"])
    assert workflow_cli.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "abandoned"
    with WorkflowStore(db) as store:
        assert store.get_workflow(workflow_id).status == "abandoned"


def test_session_cli_write_edit_accepts_repeated_input(tmp_path, monkeypatch, capsys):
    """G4：session write/edit CLI 的 --input 必须落进 declared_inputs（可重复）。"""
    store, runner, workflow, action, ticket, _db = _session_workspace(tmp_path, monkeypatch)
    workspace = Path(workflow.metadata["workspace"])
    (workspace / "source.txt").write_text("source body", encoding="utf-8")
    (workspace / "second.txt").write_text("second body", encoding="utf-8")
    session = ExecutionSession(runner, workflow.id, action)
    session.files.read_file("source.txt")
    session.files.read_file("second.txt")

    monkeypatch.setattr(sys, "argv", ["workflow_cli", "session", "write", "--session", str(ticket),
        "--path", "result.txt", "--stdin", "--input", "source.txt", "--input", "second.txt"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("result body"))
    assert workflow_cli.main() == 0
    capsys.readouterr()
    rows = store.current_operations(action.step_id, action.attempt_id)
    written = next(row for row in rows
                   if row["kind"] == "write" and row["payload"]["path"] == "result.txt")
    assert written["payload"]["declared_inputs"] == ["source.txt", "second.txt"]
    assert set(written["payload"]["inputs_snapshot"]) >= {"source.txt", "second.txt"}

    change = tmp_path / "change.json"
    change.write_text(json.dumps({"old": "result", "new": "revised result"}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "session", "edit", "--session", str(ticket),
        "--path", "result.txt", "--changes-file", str(change), "--input", "source.txt"])
    assert workflow_cli.main() == 0
    capsys.readouterr()
    rows = store.current_operations(action.step_id, action.attempt_id)
    edited = next(row for row in rows
                  if row["kind"] == "write" and row["payload"]["operation"] == "edit")
    assert edited["payload"]["declared_inputs"] == ["source.txt"]
    assert (workspace / "result.txt").read_text(encoding="utf-8") == "revised result body"
    store.close()
