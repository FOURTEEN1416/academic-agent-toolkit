"""Agent-in-the-loop 工作流测试"""
import hashlib
import json
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.agent_bridge import StepResult
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


def execute_action(runner, wf_id, fake_ok=True, fake_stderr="", output_text="x" * 3000):
    """Agent 执行一个动作的模拟：调用 next_action，执行，然后 complete_step。"""
    result = runner.next_action(wf_id)
    if result.status != "advanced":
        return result
    action = result.action
    # 模拟执行：创建产出文件
    for output in action.output_files:
        path = action.workspace / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output_text, encoding="utf-8")
    # S1 FIX: 强制创建 STEP_MANIFEST.json（新门禁要求）
    from engine.step_manifest import write_manifest
    write_manifest(
        workspace=action.workspace,
        step_name=action.skill_name,
        config={},
        outputs=[action.workspace / f for f in action.output_files],
        backend="test-backend 1.0",
        commands=[{"command": "test", "exitCode": 0}],
        dependencies={},
    )
    # 回报结果
    step_result = StepResult(
        ok=fake_ok,
        stdout=output_text,
        stderr=fake_stderr,
        artifacts=action.output_files,
        metadata={"execution_evidence": {
            "schema_version": 1,
            "agent": "OpenCode Desktop",
            "step_id": action.step_id,
            "skill_name": action.skill_name,
            "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
            "commands": [{"command": "test", "returncode": 0, "cwd": "."}],
            "inputs": [],
            "outputs": action.output_files,
        }},
    )
    return runner.complete_step(wf_id, step_result)


def test_runner_next_action_returns_step_action(tmp_path):
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-problem-analysis", "primary_output": "PROB_ANALYSIS.md", "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": False}]}}
    skills = tmp_path / "skills" / "comp-problem-analysis" / "SKILL.md"
    skills.parent.mkdir(parents=True)
    skills.write_text("skill", encoding="utf-8")
    db = tmp_path / "workflow.sqlite"
    workspace = tmp_path / "workspace"
    with WorkflowStore(db) as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", workspace, {})
        result = runner.next_action(workflow.id)
        assert result.status == "advanced"
        assert result.action is not None
        assert result.action.skill_name == "comp-problem-analysis"
        assert result.action.primary_output == "PROB_ANALYSIS.md"
        assert result.action.skill_path.name == "SKILL.md"


def test_runner_complete_step_advances_to_next(tmp_path):
    catalog = {"demo": {"sub_steps": [
        {"skill_name": "comp-problem-analysis", "primary_output": "PROB_ANALYSIS.md", "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": False},
        {"skill_name": "comp-modeling", "primary_output": "MODEL.md", "output_files": ["MODEL.md"], "has_checkpoint": False},
    ]}}
    skills = tmp_path / "skills"
    for name in ["comp-problem-analysis", "comp-modeling"]:
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_text("skill", encoding="utf-8")
    db = tmp_path / "workflow.sqlite"
    workspace = tmp_path / "workspace"
    with WorkflowStore(db) as store:
        runner = WorkflowRunner(store, catalog, skills)
        workflow = runner.start("demo", workspace, {})
        # 执行第 1 步
        r1 = execute_action(runner, workflow.id)
        assert r1.status == "advanced", f"step 1: {r1.status} {r1.message}"
        # 执行第 2 步
        r2 = execute_action(runner, workflow.id)
        assert r2.status == "completed", f"step 2: {r2.status} {r2.message}"
        # 验证产物
        assert (workspace / "PROB_ANALYSIS.md").exists()
        assert (workspace / "MODEL.md").exists()


def test_runner_uses_step_primary_output_for_quality_gate(tmp_path):
    catalog = {"demo": {"sub_steps": [{
        "skill_name": "comp-code",
        "output_files": ["code/main.py", "RESULTS.md", "figures/all_results.json"],
        "primary_output": "RESULTS.md",
        "has_checkpoint": False,
    }]}}
    skill = tmp_path / "skills" / "comp-code" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("skill", encoding="utf-8")
    workspace = tmp_path / "workspace"
    (workspace / "code").mkdir(parents=True)
    (workspace / "code" / "main.py").write_text("x" * 600, encoding="utf-8")
    (workspace / "RESULTS.md").write_text("x" * 1200, encoding="utf-8")
    (workspace / "figures").mkdir()
    (workspace / "figures" / "all_results.json").write_text("{}", encoding="utf-8")

    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", workspace, {})
        action = runner.next_action(workflow.id).action
        assert action is not None
        # S1 FIX: 创建 STEP_MANIFEST（新门禁强制要求）
        from engine.step_manifest import write_manifest
        write_manifest(
            workspace=workspace,
            step_name=action.skill_name,
            config={},
            outputs=[workspace / f for f in action.output_files],
            backend="test-backend 1.0",
            commands=[{"command": "test", "exitCode": 0}],
            dependencies={},
        )
        result = runner.complete_step(
            workflow.id,
            StepResult(ok=True, artifacts=action.output_files, metadata={"execution_evidence": {
                "schema_version": 1,
                "agent": "OpenCode Desktop",
                "step_id": action.step_id,
                "skill_name": action.skill_name,
                "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
                "commands": [{"command": "test", "returncode": 0, "cwd": "."}],
                "inputs": [],
                "outputs": action.output_files,
            }}),
        )

    assert result.status == "completed"


def test_runner_pauses_at_checkpoint_and_resumes(tmp_path):
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-problem-analysis", "primary_output": "PROB_ANALYSIS.md", "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": True, "checkpoint_type": "approve"}]}}
    skills = tmp_path / "skills" / "comp-problem-analysis" / "SKILL.md"
    skills.parent.mkdir(parents=True)
    skills.write_text("skill", encoding="utf-8")
    db = tmp_path / "workflow.sqlite"
    workspace = tmp_path / "workspace"
    with WorkflowStore(db) as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", workspace, {})
        # 执行
        r1 = execute_action(runner, workflow.id)
        assert r1.status == "waiting_checkpoint", f"expected waiting_checkpoint, got {r1.status}"
        assert store.resume_candidates()
        # 用户批准（2026-09-22 人类署名红线：approve 须人类署名）
        checkpoint = store.resume_candidates()[0].checkpoint
        r2 = runner.approve_checkpoint(checkpoint.id, {"approved": True, "approved_by": "默默"})
        assert r2.status == "completed", f"expected completed, got {r2.status}"


def test_runner_blocks_next_action_at_pending_checkpoint(tmp_path):
    """2026-09-09 独立审计 P1-2 回归：waiting_checkpoint 后未 approve 时，
    next_action 必须返回 blocked 且不得放行后续步骤动作；approve 后才恢复推进。"""
    catalog = {"demo": {"sub_steps": [
        {"skill_name": "comp-problem-analysis", "primary_output": "PROB_ANALYSIS.md",
         "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": True, "checkpoint_type": "approve"},
        {"skill_name": "comp-modeling", "primary_output": "MODEL.md",
         "output_files": ["MODEL.md"], "has_checkpoint": False},
    ]}}
    for name in ("comp-problem-analysis", "comp-modeling"):
        p = tmp_path / "skills" / name / "SKILL.md"
        p.parent.mkdir(parents=True)
        p.write_text("skill", encoding="utf-8")
    workspace = tmp_path / "workspace"
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", workspace, {})
        r1 = execute_action(runner, workflow.id)
        assert r1.status == "waiting_checkpoint", f"step1: {r1.status} {r1.message}"
        # ⛔ 核心断言：未 approve 时 next 被 checkpoint 挡住，不得吐出后续步骤动作
        r2 = runner.next_action(workflow.id)
        assert r2.status == "blocked", f"expected blocked, got {r2.status} {r2.message}"
        assert r2.action is None, "checkpoint 未批准时不得返回下一步动作"
        # 批准后恢复推进：第 2 步可正常开始
        checkpoint = store.resume_candidates()[0].checkpoint
        runner.approve_checkpoint(checkpoint.id, {"approved": True, "approved_by": "默默"})
        r3 = runner.next_action(workflow.id)
        assert r3.status == "advanced", f"after approve: {r3.status} {r3.message}"
        assert r3.action.skill_name == "comp-modeling"


def test_runner_fails_on_step_error(tmp_path):
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-problem-analysis", "primary_output": "PROB_ANALYSIS.md", "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": False}]}}
    skills = tmp_path / "skills" / "comp-problem-analysis" / "SKILL.md"
    skills.parent.mkdir(parents=True)
    skills.write_text("skill", encoding="utf-8")
    db = tmp_path / "workflow.sqlite"
    workspace = tmp_path / "workspace"
    with WorkflowStore(db) as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", workspace, {})
        # 模拟执行失败
        action_result = runner.next_action(workflow.id)
        step_result = StepResult(ok=False, stderr="error: model not found",
                                 step_id=action_result.action.step_id,
                                 attempt_id=action_result.action.attempt_id,
                                 expected_revision=action_result.action.expected_revision)
        r2 = runner.complete_step(workflow.id, step_result)
        assert r2.status == "failed"
        assert "error" in r2.message


def test_runner_rejects_success_without_desktop_execution_evidence(tmp_path):
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-problem-analysis", "has_checkpoint": False}]}}
    skill = tmp_path / "skills" / "comp-problem-analysis" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("skill", encoding="utf-8")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", tmp_path / "workspace", {})
        runner.next_action(workflow.id)
        result = runner.complete_step(workflow.id, StepResult(ok=True))
        assert result.status == "failed"
        assert "execution evidence" in result.message


def test_runner_rejects_claimed_artifact_that_is_not_declared_output(tmp_path):
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-review", "output_files": ["COMP_REVIEW.md"], "primary_output": "COMP_REVIEW.md", "has_checkpoint": False}]}}
    skill = tmp_path / "skills" / "comp-review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("skill", encoding="utf-8")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", tmp_path / "workspace", {})
        action = runner.next_action(workflow.id).action
        assert action is not None
        result = runner.complete_step(
            workflow.id,
            StepResult(ok=True, artifacts=["invented.md"], metadata={"execution_evidence": {
                "schema_version": 1,
                "agent": "OpenCode Desktop",
                "step_id": action.step_id,
                "skill_name": action.skill_name,
                "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
                "commands": [{"command": "test", "returncode": 0, "cwd": "."}],
                "inputs": [],
                "outputs": ["invented.md"],
            }}),
        )
        assert result.status == "failed"
        assert "declared outputs" in result.message


def test_runner_persists_completed_evidence_and_single_manifest_checkpoint(tmp_path):
    catalog = {"demo": {"sub_steps": [{"skill_name": "demo", "output_files": ["one.txt", "two.txt"], "has_checkpoint": False}]}}
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("skill", encoding="utf-8")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", tmp_path / "workspace", {})
        result = execute_action(runner, workflow.id, output_text="x" * 20)
        assert result.status == "completed"
        timeline = store.workflow_timeline(workflow.id)

    assert len(timeline["checkpoints"]) == 1
    assert timeline["events"][0]["type"] == "step_completed"
    evidence_path = timeline["events"][0]["payload"]["evidence_path"]
    assert (tmp_path / "workspace" / evidence_path).is_file()
    assert len(timeline["checkpoints"][0]["state"]["manifest"]["artifacts"]) == 2


def test_runner_next_action_returns_none_when_completed(tmp_path):
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-problem-analysis", "primary_output": "PROB_ANALYSIS.md", "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": False}]}}
    skills = tmp_path / "skills" / "comp-problem-analysis" / "SKILL.md"
    skills.parent.mkdir(parents=True)
    skills.write_text("skill", encoding="utf-8")
    db = tmp_path / "workflow.sqlite"
    workspace = tmp_path / "workspace"
    with WorkflowStore(db) as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", workspace, {})
        execute_action(runner, workflow.id)
        # 工作流已完成，next_action 应返回 completed
        final = runner.next_action(workflow.id)
        assert final.status == "completed"


def test_runner_reuses_running_action_instead_of_starting_another_step(tmp_path):
    catalog = {"demo": {"sub_steps": [
        {"skill_name": "first", "output_files": ["first.md"], "primary_output": "first.md"},
        {"skill_name": "second", "output_files": ["second.md"], "primary_output": "second.md"},
    ]}}
    skills = tmp_path / "skills"
    for name in ("first", "second"):
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_text("skill", encoding="utf-8")

    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills)
        workflow = runner.start("demo", tmp_path / "workspace", {})
        first = runner.next_action(workflow.id)
        repeated = runner.next_action(workflow.id)

        assert first.action is not None
        assert repeated.action is not None
        assert repeated.action.step_id == first.action.step_id


def test_runner_marks_workflow_completed_after_last_step(tmp_path):
    catalog = {"demo": {"sub_steps": [
        {"skill_name": "only", "output_files": ["out.md"], "primary_output": "out.md"},
    ]}}
    skills = tmp_path / "skills" / "only"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("skill", encoding="utf-8")

    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", tmp_path / "workspace", {})
        result = execute_action(runner, workflow.id)
        timeline = store.workflow_timeline(workflow.id)

        assert result.status == "completed"
        assert timeline["workflow"]["status"] == "completed"


# Regression contracts: these assert repaired behavior, not reproduction of a bug.
def _small_runner(tmp_path, *, checkpoint=False, metadata=None, steps=2):
    skills = tmp_path / "skills"
    specs = []
    for index in range(steps):
        name = f"demo-{index}"
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_text("fixture skill", encoding="utf-8")
        specs.append({"skill_name": name, "output_files": [f"out-{index}.txt"],
                      "primary_output": f"out-{index}.txt", "has_checkpoint": checkpoint,
                      "metadata": metadata or {}})
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, {"demo": {"sub_steps": specs}}, skills)
    wf = runner.start("demo", tmp_path / "workspace", {})
    return store, runner, wf.id


def _reported(action, *, ok=True):
    for output in action.output_files:
        (action.workspace / output).write_text("fixture result\n" * 20, encoding="utf-8")
    return StepResult(ok=ok, stderr="execution failed" if not ok else "",
        artifacts=list(action.output_files), step_id=action.step_id,
        attempt_id=action.attempt_id, expected_revision=action.expected_revision,
        metadata={"execution_evidence": {
            "schema_version": 1, "agent": "test-runner", "step_id": action.step_id,
            "skill_name": action.skill_name, "skill_sha256": action.skill_sha256,
            "commands": [{"command": "python generate.py", "returncode": 0, "cwd": "."}],
            "inputs": [], "outputs": list(action.output_files),
        }})


def test_open_output_contract_accepts_declared_artifact_and_rejects_empty(tmp_path):
    store, runner, wf = _small_runner(tmp_path, metadata={"output_files": [], "primary_output": ""}, steps=1)
    action = runner.next_action(wf).action
    assert action.output_files == []
    result = _reported(action)
    assert not runner.validate_step(wf, result)["ok"], "无产物仍然不能通过"
    output = action.workspace / "requested.txt"
    output.write_text("requested deliverable\n" * 100, encoding="utf-8")
    result.artifacts.append(output.name)
    result.metadata["execution_evidence"]["outputs"] = [output.name]
    assert runner.validate_step(wf, result)["ok"]
    complete = runner.complete_step(wf, result)
    assert complete.status == "completed", complete.message
    checkpoint = store.workflow_timeline(wf)["checkpoints"][-1]
    assert checkpoint["state"]["manifest"]["artifacts"][0]["path"] == output.name


def test_completion_replay_cannot_fail_next_step(tmp_path):
    store, runner, wf = _small_runner(tmp_path)
    action = runner.next_action(wf).action
    result = _reported(action)
    first = runner.complete_step(wf, result)
    nxt = runner.next_action(wf).action
    count = len(store.workflow_timeline(wf)["events"])
    replay = runner.complete_step(wf, result)
    assert replay.replayed and replay.checkpoint_id == first.checkpoint_id
    assert store.get_step(nxt.step_id).status.value == "running"
    assert len(store.workflow_timeline(wf)["events"]) == count


def test_old_failure_or_missing_target_has_no_side_effect(tmp_path):
    store, runner, wf = _small_runner(tmp_path)
    first = runner.next_action(wf).action
    runner.complete_step(wf, _reported(first))
    second = runner.next_action(wf).action
    before = store.workflow_timeline(wf)
    for result in [StepResult(ok=False, stderr="late failure", step_id=first.step_id), StepResult(ok=False)]:
        assert runner.complete_step(wf, result).status == "failed"
    assert store.get_step(second.step_id).status.value == "running"
    assert store.workflow_timeline(wf) == before


def test_retry_rejects_old_attempt_and_old_failed_checkpoint(tmp_path):
    store, runner, wf = _small_runner(tmp_path, checkpoint=True)
    old = runner.next_action(wf).action
    failed = runner.complete_step(wf, _reported(old, ok=False))
    new = runner.retry_last_failed(wf).action
    assert new.attempt_id != old.attempt_id
    stale = _reported(old)
    assert runner.complete_step(wf, stale).status == "failed"
    assert store.get_step(old.step_id).status.value == "running"
    assert runner.approve_checkpoint(failed.checkpoint_id, {"approved": True, "approved_by": "operator"}).status == "blocked"
    assert runner.complete_step(wf, _reported(new)).status == "waiting_checkpoint"


def test_approval_rechecks_bytes_even_with_same_size_and_mtime(tmp_path):
    import os
    store, runner, wf = _small_runner(tmp_path, checkpoint=True, steps=1)
    action = runner.next_action(wf).action
    complete = runner.complete_step(wf, _reported(action))
    path = action.workspace / action.output_files[0]
    before = path.stat()
    path.write_bytes(b"x" * before.st_size)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    blocked = runner.approve_checkpoint(complete.checkpoint_id, {"approved": True, "approved_by": "operator"})
    assert blocked.status == "blocked"
    assert store.get_step(action.step_id).status.value == "blocked"


def test_preflight_batches_errors_without_writes(tmp_path):
    metadata = {"companion_skills": ["extra"], "skill_binding": {"main_required": True},
                "assets": [{"name": "data", "path": "data.json"}]}
    store, runner, wf = _small_runner(tmp_path, metadata=metadata)
    action = runner.next_action(wf).action
    result = _reported(action)
    result.metadata["execution_evidence"]["skill_sha256"] = "invalid"
    before = store.workflow_timeline(wf)
    files = {str(p): p.read_bytes() for p in action.workspace.rglob("*") if p.is_file()}
    report = runner.validate_step(wf, result)
    assert not report["ok"]
    assert all(not report["checks"][key]["ok"] for key in ("protocol", "companion", "binding", "assets_usage"))
    assert before == store.workflow_timeline(wf)
    assert files == {str(p): p.read_bytes() for p in action.workspace.rglob("*") if p.is_file()}


def test_completion_reads_each_output_once_and_retains_execution_facts(tmp_path, monkeypatch):
    import json
    from engine.step_manifest import write_manifest
    store, runner, wf = _small_runner(tmp_path, steps=1)
    action = runner.next_action(wf).action
    result = _reported(action)
    source = action.workspace / "input.txt"
    source.write_text("source", encoding="utf-8")
    write_manifest(action.workspace, action.skill_name, config={"seed": 42},
        inputs=[source], outputs=[action.workspace / action.output_files[0]],
        backend="real-solver", commands=[{"command": ["python", "generate.py"], "exitCode": 0}],
        dependencies={"python": "3.13"})
    original = (action.workspace / "STEP_MANIFEST.json").read_bytes()
    read_count = 0
    original_open = Path.open
    target = action.workspace / action.output_files[0]
    def tracked(path, mode="r", *args, **kwargs):
        nonlocal read_count
        if path == target and "b" in mode and "r" in mode:
            read_count += 1
        return original_open(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", tracked)
    assert runner.complete_step(wf, result).status == "completed"
    assert read_count == 1
    assert (action.workspace / "STEP_MANIFEST.json").read_bytes() == original
    manifest = json.loads(original)
    assert manifest["config"]["seed"] == 42 and manifest["backend"] == "real-solver"
    assert manifest["inputFiles"] and manifest["dependencies"]


def test_explicit_bridge_manifest_keeps_original_producer_facts(tmp_path):
    from engine.step_manifest import write_manifest
    store, runner, wf = _small_runner(tmp_path, steps=1)
    action = runner.next_action(wf).action
    result = _reported(action)
    (action.workspace / "UPSTREAM.md").write_text(
        "# solver test fixture\n\n"
        "Upstream: local deterministic test fixture; not an external solver\n"
        "Pinned commit: not applicable (test fixture version 1.0)\n"
        "License: repository test license\n"
        "Modifications: synthetic manifest producer used only for this regression\n",
        encoding="utf-8",
    )
    log = action.workspace / "solver.log"
    log.write_text("fixture solver finished", encoding="utf-8")
    path = write_manifest(action.workspace, "solver-bridge", config={"seed": 17},
        outputs=[action.workspace / action.output_files[0], log], backend="real-solver", dependencies={"solver": "1.0"})
    original = path.read_bytes()
    result.metadata["execution_evidence"]["execution_manifest"] = "STEP_MANIFEST.json"
    complete = runner.complete_step(wf, result)
    assert complete.status == "completed", complete.message
    assert path.read_bytes() == original
    checkpoint = store.workflow_timeline(wf)["checkpoints"][-1]
    saved = json.loads((action.workspace / checkpoint["state"]["execution_manifest"]).read_text(encoding="utf-8"))
    assert saved["stepName"] == "solver-bridge" and saved["config"]["seed"] == 17
    assert saved["backend"] == "real-solver" and saved["dependencies"] == {"solver": "1.0"}
    assert {o["path"] for o in saved["outputFiles"]} == {action.output_files[0], "solver.log"}


def test_explicit_bridge_rejects_changed_extra_log(tmp_path):
    from engine.step_manifest import write_manifest
    store, runner, wf = _small_runner(tmp_path, steps=1)
    action = runner.next_action(wf).action
    result = _reported(action)
    log = action.workspace / "latex_bridge.log"
    receipt = action.workspace / "latex_bridge_result.json"
    log.write_text("real fixture log", encoding="utf-8")
    receipt.write_text('{"ok": true}', encoding="utf-8")
    write_manifest(action.workspace, "latex-bridge", config={},
        outputs=[receipt, log, action.workspace / action.output_files[0]], backend="fixture")
    result.metadata["execution_evidence"]["execution_manifest"] = "STEP_MANIFEST.json"
    assert runner.validate_step(wf, result)["ok"]
    log.write_text("changed after manifest", encoding="utf-8")
    assert not runner.validate_step(wf, result)["ok"]


def test_conflicting_request_id_is_rejected(tmp_path):
    from dataclasses import replace
    store, runner, wf = _small_runner(tmp_path)
    result = replace(_reported(runner.next_action(wf).action), request_id="stable-request")
    first = runner.complete_step(wf, result)
    before = store.workflow_timeline(wf)
    conflict = runner.complete_step(wf, replace(result, stderr="different payload"))
    assert conflict.status == "failed" and "different payload" in conflict.message
    assert before == store.workflow_timeline(wf)
    assert first.checkpoint_id


def test_retry_ignores_old_generated_view_but_not_explicit_stale_manifest(tmp_path):
    store, runner, wf = _small_runner(tmp_path, checkpoint=True, steps=1)
    old = runner.next_action(wf).action
    assert runner.complete_step(wf, _reported(old)).status == "waiting_checkpoint"
    new = runner.retry_last_failed(wf, by="operator").action
    result = _reported(new)
    (new.workspace / new.output_files[0]).write_text("changed result" * 30, encoding="utf-8")
    result.metadata["execution_evidence"]["execution_manifest"] = "STEP_MANIFEST.json"
    assert not runner.validate_step(wf, result)["ok"], "显式旧清单仍须按旧哈希拒绝"
    result.metadata["execution_evidence"].pop("execution_manifest")
    assert runner.validate_step(wf, result)["ok"]
    assert runner.complete_step(wf, result).status == "waiting_checkpoint"
    assert json.loads((new.workspace / "STEP_MANIFEST.json").read_text())["attemptId"] == new.attempt_id


def test_revalidating_editor_enforces_current_page_limit(tmp_path, monkeypatch):
    from engine.artifact_manifest import FingerprintSession
    from engine import contest_profile as cp_mod
    fixture = tmp_path / "comp_rules.json"
    fixture.write_text(json.dumps(
        {"comp_fx": {"name": "FX", "max_pages": 2}}), encoding="utf-8")
    monkeypatch.setattr(cp_mod, "RULES_FILE", fixture)
    cp_mod._RULES_CACHE.clear()
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text("fixture skill", encoding="utf-8")
    store = WorkflowStore(tmp_path / "wf.sqlite")
    catalog = {"demo": {"sub_steps": [{"skill_name": "demo", "output_files": ["out-0.txt"],
        "primary_output": "out-0.txt", "has_checkpoint": False,
        "metadata": {"revalidate_paper_pages": True}}]}}
    runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
    wf = runner.start("demo", tmp_path / "workspace", {"contest": {"id": "comp_fx"}})
    step = store.get_step(runner.next_action(wf.id).action.step_id)
    result = _reported(runner.next_action(wf.id).action)
    import pymupdf
    pdf = tmp_path / "workspace/paper/main.pdf"
    pdf.parent.mkdir()
    with pymupdf.open() as document:
        for _ in range(3):
            document.new_page().insert_text((72, 72), "PDF page-limit regression fixture")
        pdf.write_bytes(document.tobytes())
    check = runner._validate_step(wf, step, result, FingerprintSession(tmp_path / "workspace"))[0]
    pages = check["checks"]["quality:paper_pages"]
    assert not check["ok"] and not pages["ok"]
    assert pages["pages"] == 3 and pages["max"] == 2
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Shortened fixture")
        pdf.write_bytes(document.tobytes())
    assert runner._validate_step(wf, step, result, FingerprintSession(tmp_path / "workspace"))[0]["checks"]["quality:paper_pages"]["ok"]


def test_action_exposes_complete_machine_contract(tmp_path):
    from engine.workflow_cli import _action_payload
    store, runner, wf = _small_runner(tmp_path, metadata={
        "requires_subagent": True, "required_checks": ["consistency"],
        "output_specs": {"out-0.txt": {"min_bytes": 100}}, "skill_binding": {"main_required": True}})
    action = runner.next_action(wf).action
    payload = _action_payload(action)
    assert payload["attempt_id"] and payload["expected_revision"] == 1
    assert payload["required_checks"] == ["consistency", "step_manifest"]
    assert payload["output_specs"] and payload["requires_subagent"] and payload["skill_binding"]
    assert len(payload["skill_sha256"]) == 64


def test_blocked_retry_revalidates_changed_output_and_expires_old_checkpoint(tmp_path):
    from engine.step_manifest import write_manifest
    store, runner, wf = _small_runner(tmp_path, checkpoint=True, steps=1)
    old = runner.next_action(wf).action
    first = runner.complete_step(wf, _reported(old))
    new = runner.retry_last_failed(wf, by="operator").action
    result = _reported(new)
    (new.workspace / new.output_files[0]).write_text("new result" * 30, encoding="utf-8")
    write_manifest(new.workspace, new.skill_name, config={}, outputs=[new.workspace / new.output_files[0]],
                   backend="fixture", commands=[{"command": "python generate.py", "exitCode": 0}])
    assert runner.approve_checkpoint(first.checkpoint_id, {"approved": True, "approved_by": "operator"}).status == "blocked"
    current = runner.complete_step(wf, result)
    assert current.status == "waiting_checkpoint", current.message
    assert runner.approve_checkpoint(current.checkpoint_id, {"approved": True, "approved_by": "operator"}).status == "completed"


@pytest.mark.parametrize("with_l1", [False, True])
@pytest.mark.parametrize("via_backfill", [False, True])
def test_final_audit_real_completion_approval_delivery_cycle(tmp_path, with_l1, via_backfill):
    import json
    from engine.audit_store import write_final_audit_report
    from engine.quality_gates import QualityGate
    skills = tmp_path / "skills"
    for name in ("solve", "comp-final-audit"):
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_text("fixture skill", encoding="utf-8")
    catalog = {"demo": {"sub_steps": [
        {"skill_name": "solve", "output_files": ["paper.txt"]},
        {"skill_name": "comp-final-audit", "output_files": ["AUDIT_REPORT.json"],
         "has_checkpoint": True, "metadata": {"required_checks": ["final_audit"]}},
    ]}}
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
        wf = runner.start("demo", tmp_path / "workspace", {})
        solve = runner.next_action(wf.id).action
        assert runner.complete_step(wf.id, _reported(solve)).status == "advanced"
        if via_backfill:
            pending_timeline = store.workflow_timeline(wf.id)
            refused = runner.backfill_step(wf.id, "comp-final-audit", ["AUDIT_REPORT.json"], evidence={})
            assert refused.status == "blocked" and "先 next" in refused.message
            assert store.workflow_timeline(wf.id) == pending_timeline
        final = runner.next_action(wf.id).action
        result = _reported(final)
        candidate = None
        if with_l1:
            from engine.audit_store import AuditStore, build_final_audit_report
            command = f'python tools/final_check.py "{final.workspace}"'
            result.metadata["execution_evidence"]["commands"] = [{"command": command, "returncode": 0, "cwd": "."}]
            audit = AuditStore(tmp_path)
            audit.record({"type": "tool_call", "tool": "bash", "detail": {"command": command}})
            audit.record({"type": "tool_call", "tool": "write", "detail": {"filePath": str(final.workspace / "AUDIT_REPORT.json")}})
            # Host PreToolUse records orchestration before it can finish. These
            # calls are not completed scientific execution and have no fake rc=0.
            for operation, options in (
                ("final-audit", f'--workspace "{final.workspace}" --wf {wf.id}'),
                ("backfill" if via_backfill else "complete", f'--wf {wf.id} --evidence-file "{tmp_path / "candidate.json"}"'),
            ):
                audit.record({"type": "tool_call", "tool": "bash", "detail": {
                    "command": f'python -m engine.workflow_cli {operation} {options} --db "{store.db_path}"'}})
            assert build_final_audit_report(final.workspace, tmp_path, Path(store.db_path))["delivery_decision"] == "blocked"
            raw = result.metadata["execution_evidence"]
            candidate = runner.final_audit_candidate(wf.id, raw)
            from copy import deepcopy
            stale = deepcopy(candidate)
            stale["action"]["attempt_id"] = "old-attempt"
            with pytest.raises(ValueError, match="current RUNNING"):
                build_final_audit_report(final.workspace, tmp_path, Path(store.db_path), candidate=stale)
            with pytest.raises(ValueError, match="skill_sha256"):
                runner.final_audit_candidate(wf.id, {**raw, "skill_sha256": "bad"})
        report_path = write_final_audit_report(final.workspace, tmp_path, workflow_db=Path(store.db_path),
                                               workflow_id=wf.id, candidate=candidate)
        before = report_path.read_bytes()
        assert json.loads(before)["delivery_decision"] == "eligible"
        files = {p: p.read_bytes() for p in final.workspace.rglob("*") if p.is_file()}
        timeline = store.workflow_timeline(wf.id)
        preflight = runner.validate_step(wf.id, result)
        assert preflight["ok"], preflight
        assert timeline == store.workflow_timeline(wf.id)
        assert files == {p: p.read_bytes() for p in final.workspace.rglob("*") if p.is_file()}
        complete = (runner.backfill_step(wf.id, final.skill_name, result.artifacts,
                    by="operator", evidence=result.metadata["execution_evidence"])
                    if via_backfill else runner.complete_step(wf.id, result))
        assert complete.status == "waiting_checkpoint", complete.message
        assert not QualityGate(final.workspace).check_final_audit_report()["ok"]
        if with_l1:
            audit.record({"type": "tool_call", "tool": "bash", "detail": {
                "command": f'python -m engine.workflow_cli approve --checkpoint {complete.checkpoint_id} --by operator --db "{store.db_path}"'}})
        approved = runner.approve_checkpoint(complete.checkpoint_id, {"approved": True, "approved_by": "operator"})
        assert approved.status == "completed", approved.message
        assert report_path.read_bytes() == before
        delivery = json.loads((final.workspace / "DELIVERY_REPORT.json").read_text(encoding="utf-8"))
        assert delivery["delivery_decision"] == "ready", delivery
        assert delivery["workflow_id"] == wf.id
        if with_l1:
            controls = delivery["operation_audit_detail"]["workflow_control_calls"]
            assert {c["operation"] for c in controls} == {"final-audit", "backfill" if via_backfill else "complete", "approve"}
            assert all(c["execution_status"] == "not_attested" for c in controls)
        assert QualityGate(final.workspace).check_final_audit_report()["ok"]
        # Re-generating a delivery report never overwrites accepted AUDIT_REPORT.
        assert write_final_audit_report(final.workspace, tmp_path, workflow_db=Path(store.db_path)).name == "DELIVERY_REPORT.json"
        assert report_path.read_bytes() == before


def test_losing_completion_does_not_overwrite_accepted_evidence(tmp_path, monkeypatch):
    from dataclasses import replace
    store, runner, wf = _small_runner(tmp_path, steps=1)
    result = _reported(runner.next_action(wf).action)
    original_commit = store.transition_step_with_checkpoint
    winning = {}
    def race(*args, **kwargs):
        monkeypatch.setattr(store, "transition_step_with_checkpoint", original_commit)
        winner = replace(result, metadata={"execution_evidence": {
            **result.metadata["execution_evidence"],
            "commands": [{"command": "python winning.py", "returncode": 0, "cwd": "."}]}})
        winning["response"] = runner.complete_step(wf, winner)
        winning["files"] = {p: p.read_bytes() for p in
            (tmp_path / "workspace/.engine/evidence").glob("*.json")}
        return original_commit(*args, **kwargs)
    monkeypatch.setattr(store, "transition_step_with_checkpoint", race)
    assert runner.complete_step(wf, result).status == "failed"
    assert winning["response"].status == "completed"
    assert winning["files"] == {p: p.read_bytes() for p in (tmp_path / "workspace/.engine/evidence").glob("*.json")}
    assert len(store.workflow_timeline(wf)["events"]) == 1


def test_approval_rejects_change_before_transaction(tmp_path, monkeypatch):
    store, runner, wf = _small_runner(tmp_path, checkpoint=True, steps=1)
    action = runner.next_action(wf).action
    complete = runner.complete_step(wf, _reported(action))
    commit = store.transition_step_with_checkpoint
    def mutate_then_commit(*args, **kwargs):
        (action.workspace / action.output_files[0]).write_text("changed", encoding="utf-8")
        return commit(*args, **kwargs)
    monkeypatch.setattr(store, "transition_step_with_checkpoint", mutate_then_commit)
    before = store.workflow_timeline(wf)
    result = runner.approve_checkpoint(complete.checkpoint_id, {"approved": True, "approved_by": "operator"})
    assert result.status == "blocked" and "changed during validation" in result.message
    assert store.workflow_timeline(wf) == before


def test_delivery_write_failure_is_recoverable_on_completion_replay(tmp_path, monkeypatch):
    import engine.audit_store as audit
    store, runner, wf = _small_runner(tmp_path, steps=1)
    action = runner.next_action(wf).action
    result = _reported(action)
    (action.workspace / "AUDIT_REPORT.json").write_text("{}", encoding="utf-8")
    original = audit.write_final_audit_report
    def fail(*args, **kwargs):
        raise OSError("injected report failure")
    monkeypatch.setattr(audit, "write_final_audit_report", fail)
    first = runner.complete_step(wf, result)
    assert first.status == "completed"
    assert first.diagnostics["delivery"]["decision"] == "pending"
    count = len(store.workflow_timeline(wf)["events"])
    monkeypatch.setattr(audit, "write_final_audit_report", original)
    replay = runner.complete_step(wf, result)
    assert replay.replayed and replay.diagnostics["delivery"]["decision"] == "ready"
    assert (action.workspace / "DELIVERY_REPORT.json").is_file()
    assert len(store.workflow_timeline(wf)["events"]) == count


def test_database_failure_cannot_publish_root_manifest_or_success_evidence(tmp_path):
    from engine.audit_store import _evidence_files
    store, runner, wf = _small_runner(tmp_path, steps=1)
    action = runner.next_action(wf).action
    result = _reported(action)
    root = action.workspace / "STEP_MANIFEST.json"
    root.write_text('{"stepName": "previous"}', encoding="utf-8")
    before = root.read_bytes()
    timeline = store.workflow_timeline(wf)
    store._connection.execute("CREATE TRIGGER fail_commit BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'injected database failure'); END")
    failed = runner.complete_step(wf, result)
    assert failed.status == "failed" and "database failure" in failed.message
    assert root.read_bytes() == before
    assert store.workflow_timeline(wf) == timeline
    assert _evidence_files(action.workspace, set()) == []
    store._connection.execute("DROP TRIGGER fail_commit")
    assert runner.complete_step(wf, result).status == "completed"


def test_directory_output_trailing_slash_preserves_tool_manifest(tmp_path):
    from engine.step_manifest import write_manifest
    store, runner, wf = _small_runner(tmp_path, steps=1)
    action = runner.next_action(wf).action
    result = _reported(action)
    metadata = {"output_files": ["figures/"], "primary_output": ""}
    store._connection.execute("UPDATE workflow_steps SET metadata = ? WHERE id = ?",
                              (json.dumps(metadata), action.step_id))
    store._connection.commit()
    directory = action.workspace / "figures"
    directory.mkdir()
    (directory / "plot.txt").write_text("real figure data", encoding="utf-8")
    manifest_path = write_manifest(action.workspace, action.skill_name,
        outputs=[directory], config={"seed": 42}, backend="real-tool")
    original = manifest_path.read_bytes()
    result.artifacts[:] = ["figures/"]
    result.metadata["execution_evidence"]["outputs"] = ["figures/"]
    completed = runner.complete_step(wf, result)
    assert completed.status == "completed", completed.message
    assert manifest_path.read_bytes() == original
    accepted = store.workflow_timeline(wf)["events"][-1]["payload"]["manifest"]["artifacts"][0]
    assert accepted["members"] == {"figures/plot.txt": hashlib.sha256(b"real figure data").hexdigest()}
