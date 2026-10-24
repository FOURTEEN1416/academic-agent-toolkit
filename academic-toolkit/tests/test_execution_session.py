"""执行侧实事实例：不靠模型填哈希/返回码，不为修字段反复重置步骤。"""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.agent_bridge import StepResult
from engine.execution_protocol import collect_execution_evidence
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from execution.session import ExecutionSession


def make_session(tmp_path, *, checkpoint=False, metadata=None):
    skills = tmp_path / "suite/skills"
    for name in ("demo", "extra"):
        folder = skills / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("Real task instructions: calculate the result.", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    catalog = {"demo": {"sub_steps": [{"skill_name": "demo", "output_files": ["result.txt"],
        "primary_output": "result.txt", "has_checkpoint": checkpoint,
        "metadata": {"skill_binding": {"main_required": True}, **(metadata or {})}}]}}
    runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
    wf = runner.start("demo", tmp_path / "work", {})
    session = ExecutionSession(runner, wf.id)
    session.context()
    return store, runner, wf.id, session


def command(session, factor=2):
    session.files.write("input.txt", "7")
    session.files.write("solve.py", f"from pathlib import Path\np=Path('input.txt')\nPath('result.txt').write_text(str(int(p.read_text())*{factor}))\n")
    return {"id": "solve", "argv": [sys.executable, "solve.py"],
            "inputs": ["input.txt", "solve.py"], "outputs": ["result.txt"],
            "pure": True, "complete_inputs": True}


def test_real_command_cache_and_automatic_finish(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    spec = command(session)
    assert session.commands.execute(spec)["status"] == "succeeded"
    assert session.commands.execute(spec)["status"] == "reused"
    (session.workspace / "result.txt").write_text("tampered")
    assert session.commands.execute(spec)["status"] == "succeeded"
    assert session.commands.execute(spec)["status"] == "reused"
    assert (session.workspace / "result.txt").read_text() == "14"
    evidence = collect_execution_evidence(store, store.get_workflow(wf), session.action)
    assert evidence["commands"][0]["returncode"] == 0
    assert evidence["resource_reads"][0]["name"] == "demo"
    assert evidence["commands"][0]["reused_from"]
    result = session.finish()
    assert result["status"] == "completed", result
    assert session.finish()["replayed"] is True
    store.close()


def test_changed_inputs_invalidate_and_cannot_finish_old_result(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    spec = command(session)
    session.commands.execute(spec)
    session.files.write("input.txt", "9")
    refused = session.finish()
    assert refused["status"] == "needs_work"
    assert store.get_step(session.action.step_id).status.value == "running"
    assert session.commands.execute(spec)["status"] == "succeeded"
    assert (session.workspace / "result.txt").read_text() == "18"
    assert session.finish()["status"] == "completed"
    store.close()


def test_quality_failure_keeps_identity_and_accepts_repair(tmp_path):
    store, runner, wf, session = make_session(tmp_path,
        metadata={"output_specs": {"result.txt": {"min_bytes": 100}}})
    session.files.write("result.txt", "too short")
    before = store.get_step(session.action.step_id)
    refused = session.finish()
    after = store.get_step(session.action.step_id)
    assert refused["status"] == "needs_work"
    assert before == after
    session.files.write("result.txt", "substantive output " * 20)
    assert session.finish()["status"] == "completed"
    store.close()


def test_forged_collection_and_changed_resource_are_rejected(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("result.txt", "task result")
    evidence = collect_execution_evidence(store, store.get_workflow(wf), session.action)
    evidence["resource_reads"][0]["sha256"] = "0" * 64
    result = runner.complete_step(wf, StepResult(ok=True, artifacts=["result.txt"],
        metadata={"execution_evidence": evidence}), keep_running_on_validation_error=True)
    assert result.status == "needs_work"
    session.action.skill_path.write_text("changed skill", encoding="utf-8")
    assert session.finish()["status"] == "needs_work"
    store.close()


def test_failed_command_not_hidden_and_same_output_retry_recovers(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    spec = command(session)
    bad = {**spec, "argv": [sys.executable, "-c", "raise SystemExit(3)"]}
    assert session.commands.execute(bad)["status"] == "failed"
    with pytest.raises(ValueError, match="失败/中断"):
        session.finish()
    assert session.commands.execute(spec)["status"] == "succeeded"
    assert session.finish()["status"] == "completed"
    store.close()


def test_checkpoint_still_requires_human_approval(tmp_path):
    store, runner, wf, session = make_session(tmp_path, checkpoint=True)
    session.files.write("result.txt", "real task result")
    result = session.finish()
    assert result["status"] == "waiting_checkpoint"
    assert session.finish()["status"] == "blocked"
    assert runner._approve_checkpoint(result["checkpoint_id"], {"approved": True, "approved_by": "operator"}).status == "completed"
    store.close()


def test_plan_cycle_and_overlapping_producers_rejected_before_execution(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    spec = command(session)
    with pytest.raises(ValueError, match="循环"):
        session.commands.run_plan({"nodes": [{**spec, "depends_on": ["solve"]}]})
    with pytest.raises(ValueError, match="多重写入"):
        session.commands.run_plan({"nodes": [spec, {**spec, "id": "another"}]})
    assert not (session.workspace / "result.txt").exists()
    with pytest.raises(ValueError, match="多重写入"):
        session.commands.run_plan({"nodes": [{**spec, "outputs": ["figures"]},
                                    {**spec, "id": "child", "outputs": ["figures/one.png"]}]})
    store.close()


def test_collected_output_requires_actual_producer(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("notes.txt", "some unrelated notes")
    (session.workspace / "result.txt").write_text("pre-existing unobserved result")
    result = session.finish()
    assert result["status"] == "needs_work"
    assert "no collected producer" in str(result["diagnostics"])
    store.close()


def test_downstream_stale_result_is_not_hidden_by_new_upstream(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("input.txt", "2")
    first = {"id": "up", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('middle.txt').write_text(Path('input.txt').read_text())"],
        "inputs": ["input.txt"], "outputs": ["middle.txt"], "pure": True, "complete_inputs": True}
    second = {"id": "down", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('result.txt').write_text(Path('middle.txt').read_text())"],
        "inputs": ["middle.txt"], "outputs": ["result.txt"], "pure": True, "complete_inputs": True}
    plan = {"nodes": [second, first]}
    assert session.commands.run_plan(plan)["executed"] == 2
    session.files.write("input.txt", "3")
    session.commands.execute(first)
    result = session.finish()
    assert result["status"] == "needs_work"
    assert "dependency changed" in str(result["diagnostics"])
    repeated = session.commands.run_plan(plan)
    assert repeated["executed"] == 1 and repeated["reused"] == 1
    assert session.finish()["status"] == "completed"
    store.close()


def test_session_cli_dispatch_and_exact_audit_scope(tmp_path):
    import subprocess
    from engine.audit_store import _workflow_control_call
    store, runner, wf, session = make_session(tmp_path)
    ticket = session.context()["session"]
    scope = {"database": store.db_path, "workflow_id": wf, "checkpoint_ids": set()}
    command = f'python -m engine.workflow_cli session finish --session "{ticket}"'
    assert _workflow_control_call(command, session.workspace, scope) == "session:finish"
    assert _workflow_control_call(command + " && python steal.py", session.workspace, scope) is None
    assert _workflow_control_call(command, session.workspace, {**scope, "workflow_id": "wrong"}) is None
    from engine.audit_store import verify_skill_bindings
    session.files.write("result.txt", "real result")
    assert session.finish()["status"] == "completed"
    bindings = verify_skill_bindings(session.workspace, tmp_path, workflow_db=Path(store.db_path))
    assert bindings["verdict"] == "ok"
    assert bindings["verification_source"] == "persisted_execution_resource_reads_not_host_L1"
    result = subprocess.run([sys.executable, "-m", "engine.workflow_cli", "session", "--help"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0 and "context" in result.stdout and "finish" in result.stdout
    from execution.presentation import user_view
    view = user_view({"workflow_id": wf, "status": "completed", "diagnostics": {"checks": {"hash": {"ok": True}}}})
    assert view["issues"] == [] and "diagnostics" not in view
    store.close()


def test_real_final_audit_is_not_automated_by_skill_name(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    skill = runner.skills_root / "comp-final-audit"
    skill.mkdir()
    (skill / "SKILL.md").write_text("Check citations and compliance before final delivery.")
    store.add_steps(wf, [{"name": "comp-final-audit", "position": 1, "metadata": {
        "output_files": ["AUDIT_REPORT.json"], "required_checks": ["final_audit"],
        "skill_binding": {"main_required": True}}}])
    session.files.write("result.txt", "real output")
    result = session.finish()
    assert "machine_audit" not in result
    final = ExecutionSession(runner, wf)
    with pytest.raises(ValueError, match="not task execution"):
        final.finish()
    store.close()


def test_workspace_read_exact_edit_and_writing_dependency(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("source.txt", "observed evidence")
    assert session.files.read_file("source.txt")["content"] == "observed evidence"
    session.files.write("result.txt", "supported result, initial wording", inputs=["source.txt"])
    session.files.edit("result.txt", "initial wording", "revised wording", inputs=["source.txt"])
    assert (session.workspace / "result.txt").read_text() == "supported result, revised wording"
    with pytest.raises(ValueError, match="唯一匹配"):
        session.files.edit("result.txt", "not present", "replacement")
    (session.workspace / "source.txt").write_text("changed evidence")
    assert session.finish()["status"] == "needs_work"
    session.files.read_file("source.txt")
    session.files.write("source.txt", "changed evidence")
    session.files.write("result.txt", "revised result with current evidence", inputs=["source.txt"])
    assert session.finish()["status"] == "completed"
    store.close()


def test_unrelated_read_does_not_create_write_dependency(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    (session.workspace / "notes.txt").write_text("unrelated notes")
    observed = session.files.read_file("notes.txt")
    result = session.files.write("result.txt", "independent result")
    assert "notes.txt" not in result["inputs_snapshot"]
    assert result["trace_only_observations"]["notes.txt"] == observed["sha256"]
    assert result["declared_inputs"] == []
    assert result["dependency_policy"] == "explicit-declared-inputs-v1"
    (session.workspace / "notes.txt").write_text("changed unrelated notes")
    assert session.finish()["status"] == "completed"
    store.close()


def test_declared_input_must_be_observed(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    with pytest.raises(ValueError, match="显式输入必须先读取"):
        session.files.write("result.txt", "unsupported", inputs=["never_read.txt"])
    assert not (session.workspace / "result.txt").exists()
    operations = store.current_operations(session.action.step_id, session.action.attempt_id)
    assert not [row for row in operations if row["kind"] == "write"]
    store.close()


def test_declared_input_cannot_be_write_target(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("self.txt", "draft")
    session.files.read_file("self.txt")
    with pytest.raises(ValueError, match="写入目标自身"):
        session.files.edit("self.txt", "draft", "revised", inputs=["self.txt"])
    assert (session.workspace / "self.txt").read_text() == "draft"
    store.close()


def test_changed_declared_input_blocks_before_write(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("source.txt", "observed evidence")
    session.files.read_file("source.txt")
    (session.workspace / "source.txt").write_text("changed evidence")
    with pytest.raises(ValueError, match="已阅读的依据文件发生变化"):
        session.files.write("result.txt", "result", inputs=["source.txt"])
    assert not (session.workspace / "result.txt").exists()
    store.close()


def test_declared_input_keeps_transitive_lineage(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("input.txt", "7")
    up = {"id": "up", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('mid.txt').write_text(Path('input.txt').read_text())"],
        "inputs": ["input.txt"], "outputs": ["mid.txt"], "pure": True, "complete_inputs": True}
    assert session.commands.execute(up)["status"] == "succeeded"
    mid = session.files.read_file("mid.txt")
    result = session.files.write("report.txt", "report over mid", inputs=["mid.txt"])
    assert result["declared_inputs"] == ["mid.txt"]
    assert result["inputs_snapshot"]["mid.txt"] == mid["sha256"]
    assert "input.txt" in result["inputs_snapshot"]
    store.close()


def test_trace_only_observations_not_in_evidence_inputs(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    (session.workspace / "notes.txt").write_text("unrelated notes")
    (session.workspace / "source.txt").write_text("declared source")
    observed = session.files.read_file("notes.txt")
    session.files.read_file("source.txt")
    session.files.write("result.txt", "independent result", inputs=["source.txt"])
    evidence = collect_execution_evidence(store, store.get_workflow(wf), session.action)
    assert evidence["inputs"] == ["source.txt"]
    observations = {entry["path"]: entry for entry in evidence["workspace_observations"]}
    assert observations["notes.txt"]["edge"] is False
    assert observations["notes.txt"]["sha256"] == observed["sha256"]
    assert observations["notes.txt"]["operation_id"]
    rows = store.current_operations(session.action.step_id, session.action.attempt_id)
    written = next(row for row in rows
                   if row["kind"] == "write" and row["payload"]["path"] == "result.txt")
    assert written["payload"]["trace_only_observations"]["notes.txt"] == observed["sha256"]
    assert written["payload"]["dependency_policy"] == "explicit-declared-inputs-v1"
    assert written["payload"]["declared_inputs"] == ["source.txt"]
    store.close()


def test_observation_role_neutral_until_declared(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("data.txt", "v1")
    first = session.files.read_file("data.txt")
    assert first["observation_role"] == "trace_only"
    assert "edge_eligible" not in first
    result = session.files.write("result.txt", "from data", inputs=["data.txt"])
    assert result["inputs_snapshot"]["data.txt"] == first["sha256"]
    second = session.files.read_file("data.txt")
    observations = [row for row in store.current_operations(
        session.action.step_id, session.action.attempt_id)
        if row["kind"] == "observation" and row["payload"]["path"] == "data.txt"]
    assert len(observations) == 1
    assert observations[0]["payload"]["observation_role"] == "trace_only"
    assert "edge_eligible" not in observations[0]["payload"]
    assert observations[0]["payload"]["sha256"] == second["sha256"]
    store.close()


def test_in_place_revision_records_before_after_and_never_reuses(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("result.txt", "draft")
    spec = {"id": "revise", "argv": [sys.executable, "-c",
        "from pathlib import Path;p=Path('result.txt');p.write_text(p.read_text()+' revised')"],
        "inputs": ["result.txt"], "outputs": ["result.txt"], "mutates": ["result.txt"],
        "pure": True, "complete_inputs": True}
    first = session.commands.execute(spec)
    second = session.commands.execute(spec)
    assert first["status"] == second["status"] == "succeeded"
    assert first["inputs_snapshot"] != first["outputs_snapshot"]
    assert first["cacheable"] is False
    assert session.finish()["status"] == "completed"
    store.close()


def test_outputless_checks_are_real_and_invalidated_after_edit(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("result.txt", "correct statement")
    check = {"id": "content-check", "mode": "check", "argv": [sys.executable, "-c",
        "from pathlib import Path;assert 'correct' in Path('result.txt').read_text()"],
        "inputs": ["result.txt"], "outputs": [], "pure": True, "complete_inputs": True}
    assert session.commands.execute(check)["cacheable"] is False
    session.files.edit("result.txt", "statement", "revised statement")
    assert session.finish()["status"] == "needs_work"
    assert session.commands.execute(check)["status"] == "succeeded"
    assert session.finish()["status"] == "completed"
    store.close()


def test_check_does_not_create_producer_or_hide_failed_verification(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    (session.workspace / "result.txt").write_text("unobserved")
    check = {"id": "inspection", "mode": "check", "argv": [sys.executable, "-c", "pass"],
             "inputs": ["result.txt"], "outputs": []}
    session.commands.execute(check)
    assert session.finish()["status"] == "needs_work"
    session.files.write("result.txt", "observed")
    failed = {**check, "argv": [sys.executable, "-c", "raise SystemExit(7)"]}
    assert session.commands.execute(failed)["status"] == "failed"
    with pytest.raises(ValueError, match="失败/中断"):
        session.finish()
    store.close()


def test_interrupted_operation_requires_explicit_recovery(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    payload = {"argv": [sys.executable], "declared_outputs": ["result.txt"]}
    op = session.operations.begin("command", "command:interrupted", payload)
    with pytest.raises(ValueError, match="already running"):
        session.files.write("result.txt", "must not run while another writer is active")
    store.interrupt_operation(op, "operator confirmed the process has exited")
    assert store.execution_operations(session.action.step_id, session.action.attempt_id)[-1]["status"] == "failed"
    store.close()
