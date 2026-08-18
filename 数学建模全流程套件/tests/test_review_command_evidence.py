"""P1 增强测试：审核步骤的 commands 必须含真实工具调用（防 "echo done" 伪造）。

背景（LESSONS P1 表）：evidence 的 commands 校验可被 "echo done" 绕过——
审核步骤声称执行了审稿/视觉检查，实际只跑了 echo。requires_subagent 步骤
除要求 subagent_session 外，commands 必须含真实工具调用（tools/ 下的脚本）。
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.opencode_bridge import StepResult
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


def _make_skill(tmp_path, name="comp-review"):
    skill = tmp_path / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("skill", encoding="utf-8")
    return skill


def _evidence(action, commands, subagent="ses_test"):
    return {
        "schema_version": 1,
        "agent": "OpenCode Desktop",
        "step_id": action.step_id,
        "skill_name": action.skill_name,
        "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
        "commands": commands,
        "inputs": [],
        "outputs": action.output_files,
        "subagent_session": subagent,
    }


def _run_step(tmp_path, commands, subagent="ses_test"):
    catalog = {"demo": {"sub_steps": [{
        "skill_name": "comp-review",
        "primary_output": "COMP_REVIEW.md",
        "output_files": ["COMP_REVIEW.md"],
        "has_checkpoint": False,
        "requires_subagent": True,
    }]}}
    _make_skill(tmp_path)
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", tmp_path / "workspace", {})
        result = runner.next_action(workflow.id)
        action = result.action
        for output in action.output_files:
            p = action.workspace / output
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x" * 2000, encoding="utf-8")
        # M1: 审核步骤自动跑 review gate → 需要审稿文件（solo 模式：COMP_REVIEW.md + VERDICT）
        ws = action.workspace
        (ws / "COMP_REVIEW.md").write_text("审查报告内容占位。" * 10, encoding="utf-8")
        (ws / "COMP_REVIEW_VERDICT.json").write_text(
            '{"verdict": "PASS", "fatal_count": 0, "findings": []}', encoding="utf-8"
        )
        step_result = StepResult(
            ok=True, artifacts=action.output_files,
            metadata={"execution_evidence": _evidence(action, commands, subagent)},
        )
        return runner.complete_step(workflow.id, step_result)


def test_review_step_echo_command_is_rejected(tmp_path):
    """审核步骤用 echo 伪命令（无真实工具调用）→ 必须失败。"""
    result = _run_step(tmp_path, [{"command": "echo review complete", "returncode": 0, "cwd": "."}])
    assert result.status == "failed", f"echo 伪命令应被拒绝，实际 {result.status}: {result.message}"
    assert "tool" in result.message.lower() or "命令" in result.message, f"应提及真实工具: {result.message}"


def test_review_step_with_actual_tool_passes(tmp_path):
    """审核步骤含真实工具调用（tools/ 下脚本）→ 通过。"""
    result = _run_step(tmp_path, [{
        "command": "python tools/reviewer_client.py --prompt 审查报告",
        "returncode": 0, "cwd": ".",
    }])
    assert result.status == "completed", f"真实工具调用应通过，实际 {result.status}: {result.message}"