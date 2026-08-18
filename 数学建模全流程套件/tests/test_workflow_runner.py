"""Agent-in-the-loop 工作流测试"""
import json
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.opencode_bridge import StepAction, StepResult
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
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-prob-analysis", "primary_output": "PROB_ANALYSIS.md", "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": False}]}}
    skills = tmp_path / "skills" / "comp-prob-analysis" / "SKILL.md"
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
        assert result.action.skill_name == "comp-prob-analysis"
        assert result.action.primary_output == "PROB_ANALYSIS.md"
        assert result.action.skill_path.name == "SKILL.md"


def test_runner_complete_step_advances_to_next(tmp_path):
    catalog = {"demo": {"sub_steps": [
        {"skill_name": "comp-prob-analysis", "primary_output": "PROB_ANALYSIS.md", "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": False},
        {"skill_name": "comp-modeling", "primary_output": "MODEL.md", "output_files": ["MODEL.md"], "has_checkpoint": False},
    ]}}
    skills = tmp_path / "skills"
    for name in ["comp-prob-analysis", "comp-modeling"]:
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
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-prob-analysis", "primary_output": "PROB_ANALYSIS.md", "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": True, "checkpoint_type": "approve"}]}}
    skills = tmp_path / "skills" / "comp-prob-analysis" / "SKILL.md"
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
        # 用户批准
        checkpoint = store.resume_candidates()[0].checkpoint
        r2 = runner.approve_checkpoint(checkpoint.id, {"approved": True})
        assert r2.status == "completed", f"expected completed, got {r2.status}"


def test_runner_fails_on_step_error(tmp_path):
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-prob-analysis", "primary_output": "PROB_ANALYSIS.md", "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": False}]}}
    skills = tmp_path / "skills" / "comp-prob-analysis" / "SKILL.md"
    skills.parent.mkdir(parents=True)
    skills.write_text("skill", encoding="utf-8")
    db = tmp_path / "workflow.sqlite"
    workspace = tmp_path / "workspace"
    with WorkflowStore(db) as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", workspace, {})
        # 模拟执行失败
        action_result = runner.next_action(workflow.id)
        step_result = StepResult(ok=False, stderr="error: model not found")
        r2 = runner.complete_step(workflow.id, step_result)
        assert r2.status == "failed"
        assert "error" in r2.message


def test_runner_rejects_success_without_desktop_execution_evidence(tmp_path):
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-prob-analysis", "has_checkpoint": False}]}}
    skill = tmp_path / "skills" / "comp-prob-analysis" / "SKILL.md"
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
    catalog = {"demo": {"sub_steps": [{"skill_name": "comp-prob-analysis", "primary_output": "PROB_ANALYSIS.md", "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": False}]}}
    skills = tmp_path / "skills" / "comp-prob-analysis" / "SKILL.md"
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
