"""端到端测试：agent-in-the-loop 模式"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.artifact_manifest import ArtifactManifest
from engine.opencode_bridge import StepResult
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from engine.quality_gates import QualityGate
from engine.run_logger import RunLogger
from engine.step_manifest import write_manifest


def execute_action(runner, wf_id, output_text="x"):
    """Agent 执行一个动作的模拟。"""
    result = runner.next_action(wf_id)
    if result.status != "advanced":
        return result
    action = result.action
    for output in action.output_files:
        path = action.workspace / output
        path.parent.mkdir(parents=True, exist_ok=True)
        # 写 16000 字节以满足所有技能的最小大小门禁（comp-paper-zh 需 ≥10000）
        path.write_text(output_text * 16000, encoding="utf-8")
    # S1 FIX: 强制创建 STEP_MANIFEST
    write_manifest(
        workspace=action.workspace,
        step_name=action.skill_name,
        config={},
        outputs=[action.workspace / f for f in action.output_files],
        backend="test-backend 1.0",
        commands=[{"command": "test", "exitCode": 0}],
        dependencies={},
    )
    step_result = StepResult(
        ok=True,
        artifacts=action.output_files,
        stdout=output_text,
        metadata={"execution_evidence": {
            "schema_version": 1,
            "agent": "OpenCode Desktop test harness",
            "step_id": action.step_id,
            "skill_name": action.skill_name,
            "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
            "commands": [{"command": "pytest simulated agent execution", "returncode": 0, "cwd": "."}],
            "inputs": [],
            "outputs": action.output_files,
        }},
    )
    return runner.complete_step(wf_id, step_result)


def test_offline_workflow_creates_declared_artifacts(tmp_path):
    skills_root = tmp_path / "skills"
    steps = []
    for name, output in (("comp-prob-analysis", "PROB_ANALYSIS.md"), ("comp-modeling", "MODEL.md"), ("comp-paper-zh", "PAPER.md")):
        skill = skills_root / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("skill", encoding="utf-8")
        steps.append({"skill_name": name, "output_files": [output], "primary_output": output, "has_checkpoint": False})
    catalog = {"offline": {"sub_steps": steps}}
    workspace = tmp_path / "workspace"
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills_root)
        workflow = runner.start("offline", workspace, {})
        while True:
            r = execute_action(runner, workflow.id)
            if r.status in ("completed", "failed"):
                break
        assert r.status == "completed", f"工作流应完成，实际 {r.status}: {r.message}"
        validation = ArtifactManifest.validate(workspace, ["PROB_ANALYSIS.md", "MODEL.md", "PAPER.md"])
        assert validation["ok"] is True


def test_offline_workflow_with_quality_gates(tmp_path):
    skills_root = tmp_path / "skills"
    step = {"skill_name": "comp-prob-analysis", "output_files": ["PROB_ANALYSIS.md"], "primary_output": "PROB_ANALYSIS.md", "has_checkpoint": False}
    skill = skills_root / "comp-prob-analysis" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("skill", encoding="utf-8")
    catalog = {"test": {"sub_steps": [step]}}
    workspace = tmp_path / "workspace"
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills_root)
        workflow = runner.start("test", workspace, {})
        r = execute_action(runner, workflow.id)
        assert r.status == "completed", f"got {r.status}"
        gate = QualityGate(workspace)
        gates_result = gate.run_all("comp-prob-analysis", declared_outputs=["PROB_ANALYSIS.md"])
        assert gates_result["ok"] is True
        assert gates_result["checks"]["min_size"]["ok"] is True


def test_offline_workflow_with_run_log(tmp_path):
    skills_root = tmp_path / "skills"
    step = {"skill_name": "comp-prob-analysis", "output_files": ["PROB_ANALYSIS.md"], "primary_output": "PROB_ANALYSIS.md", "has_checkpoint": False}
    skill = skills_root / "comp-prob-analysis" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("skill", encoding="utf-8")
    catalog = {"test": {"sub_steps": [step]}}
    workspace = tmp_path / "workspace"
    logger = RunLogger(tmp_path / "logs")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills_root)
        workflow = runner.start("test", workspace, {})
        logger.log(workflow.id, None, None, "started", "工作流启动")
        r = execute_action(runner, workflow.id)
        logger.log(workflow.id, r.step_id, None, r.status, r.message)
        report = logger.generate_report(workflow.id, "测试工作流")
        assert report["steps_completed"] >= 1
        assert report["total_events"] >= 2
        log_path = logger.save(workflow.id)
        assert log_path.exists()


def test_real_template_resolves_cumcm():
    """真实模板（comp_cumcm）可解析，所有引用的技能都存在。"""
    import json
    catalog = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    from engine.template_resolver import resolve_template
    steps = resolve_template("comp_cumcm", {}, catalog)
    assert len(steps) >= 5, f"comp_cumcm 模板步骤不足 ({len(steps)})"
    skills_root = ROOT / "skills"
    missing = [s["skill_name"] for s in steps if not (skills_root / s["skill_name"]).is_dir()]
    assert not missing, f"模板引用不存在的技能: {missing}"


def test_runner_writes_run_log_with_monotonic_timestamps(tmp_path):
    """RunLogger 自动接入 Runner：工作流完成后日志文件存在、条目时间戳单调递增、step_id 正确。"""
    skills_root = tmp_path / "skills"
    step = {"skill_name": "comp-prob-analysis", "output_files": ["PROB_ANALYSIS.md"], "primary_output": "PROB_ANALYSIS.md", "has_checkpoint": False}
    skill = skills_root / "comp-prob-analysis" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("skill", encoding="utf-8")
    catalog = {"test": {"sub_steps": [step]}}
    workspace = tmp_path / "workspace"
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills_root)  # 不显式传 logger → 自动创建
        workflow = runner.start("test", workspace, {})
        assert runner.logger is not None, "runner 必须自动创建 RunLogger"
        r = execute_action(runner, workflow.id)
        assert r.status == "completed", f"got {r.status}"

        log_file = workspace / ".engine" / "logs" / f"run_{workflow.id}.json"
        assert log_file.exists(), "工作流完成后必须保存 run log"
        entries = json.loads(log_file.read_text(encoding="utf-8"))
        assert len(entries) >= 3  # started + step started + step completed
        timestamps = [e["timestamp"] for e in entries]
        assert timestamps == sorted(timestamps), "日志时间戳必须单调递增"
        step_ids = [e["step_id"] for e in entries if e["step_name"] == "comp-prob-analysis"]
        assert all(sid == r.step_id for sid in step_ids), "日志 step_id 必须与真实步骤一致"


def test_runner_logs_real_step_ids_not_last_step(tmp_path):
    """多步骤工作流：日志中每步 step_id 必须与对应步骤匹配（回归上轮回填 bug）。"""
    skills_root = tmp_path / "skills"
    steps = []
    for name, output in (("comp-prob-analysis", "A.md"), ("comp-modeling", "B.md")):
        skill = skills_root / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("skill", encoding="utf-8")
        steps.append({"skill_name": name, "output_files": [output], "primary_output": output, "has_checkpoint": False})
    catalog = {"multi": {"sub_steps": steps}}
    workspace = tmp_path / "workspace"
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills_root)
        workflow = runner.start("multi", workspace, {})
        while True:
            r = execute_action(runner, workflow.id)
            if r.status in ("completed", "failed"):
                break
        assert r.status == "completed", f"工作流应完成，实际 {r.status}: {r.message}"
        log_file = workspace / ".engine" / "logs" / f"run_{workflow.id}.json"
        entries = json.loads(log_file.read_text(encoding="utf-8"))
        # 每步的 started/completed 必须带该步自己的 step_id，且不同步骤 id 不同
        prob_ids = [e["step_id"] for e in entries if e["step_name"] == "comp-prob-analysis" and e["event"] == "completed"]
        model_ids = [e["step_id"] for e in entries if e["step_name"] == "comp-modeling" and e["event"] == "completed"]
        assert prob_ids and model_ids
        assert prob_ids[0] != model_ids[0], "不同步骤的 step_id 必须不同"
        assert all(e["step_id"] != model_ids[0] for e in entries if e["step_name"] == "comp-prob-analysis"), "步骤 step_id 错位"


def test_runner_rejects_descriptive_fake_command_evidence(tmp_path):
    """Runner 必须拒绝描述性伪命令 evidence（回归 comp-modeling 伪命令问题）。"""
    skills_root = tmp_path / "skills"
    step = {"skill_name": "comp-prob-analysis", "output_files": ["PROB_ANALYSIS.md"], "primary_output": "PROB_ANALYSIS.md", "has_checkpoint": False}
    skill = skills_root / "comp-prob-analysis" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("skill", encoding="utf-8")
    catalog = {"test": {"sub_steps": [step]}}
    workspace = tmp_path / "workspace"
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills_root)
        workflow = runner.start("test", workspace, {})
        action = runner.next_action(workflow.id).action
        (workspace / "PROB_ANALYSIS.md").write_text("x" * 5000, encoding="utf-8")
        step_result = StepResult(
            ok=True,
            artifacts=["PROB_ANALYSIS.md"],
            metadata={"execution_evidence": {
                "schema_version": 1,
                "agent": "test",
                "step_id": action.step_id,
                "skill_name": action.skill_name,
                "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
                "commands": [{"command": "python modeling capability coverage check", "returncode": 0, "cwd": "."}],
                "inputs": [],
                "outputs": ["PROB_ANALYSIS.md"],
            }},
        )
        r = runner.complete_step(workflow.id, step_result)
        assert r.status == "failed", "伪命令 evidence 必须被拒绝"
        assert "descriptive text" in r.message or "execution evidence" in r.message


def test_failed_step_blocks_subsequent_steps(tmp_path):
    """任何步骤失败后，next_action 必须阻断后续步骤（不允许带错推进）。"""
    skills_root = tmp_path / "skills"
    steps = []
    for name, output in (("comp-prob-analysis", "A.md"), ("comp-modeling", "B.md")):
        skill = skills_root / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("skill", encoding="utf-8")
        steps.append({"skill_name": name, "output_files": [output], "primary_output": output, "has_checkpoint": False})
    catalog = {"multi": {"sub_steps": steps}}
    workspace = tmp_path / "workspace"
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills_root)
        workflow = runner.start("multi", workspace, {})

        # 第一步：伪命令 → 失败
        action = runner.next_action(workflow.id).action
        (workspace / "A.md").write_text("x" * 5000, encoding="utf-8")
        step_result = StepResult(
            ok=True,
            artifacts=["A.md"],
            metadata={"execution_evidence": {
                "schema_version": 1,
                "agent": "test",
                "step_id": action.step_id,
                "skill_name": action.skill_name,
                "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
                "commands": [{"command": "python capability coverage check", "returncode": 0, "cwd": "."}],
                "inputs": [],
                "outputs": ["A.md"],
            }},
        )
        r = runner.complete_step(workflow.id, step_result)
        assert r.status == "failed"

        # 第二步：next_action 必须被阻断，不能推进 comp-modeling
        r2 = runner.next_action(workflow.id)
        assert r2.status == "failed", "失败后必须阻断后续步骤"
        assert "comp-prob-analysis" in r2.message
