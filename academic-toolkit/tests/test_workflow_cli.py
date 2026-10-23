import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import workflow_cli
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


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
