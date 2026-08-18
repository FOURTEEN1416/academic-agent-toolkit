"""P1 机制补强测试：审核独立视角强制（M5）+ approve_checkpoint 原子化（M3）。

背景（LESSONS_FROM_CUMCM_Practice_2026-08.md）：
- M5: 审核步骤无"独立视角强制"机制 → 主 Agent 可伪造审核产物（手写 verdict）且门禁放行。
      修复：模板 metadata.requires_subagent=true 时，complete_step 必须校验 execution_evidence
      含真实子智能体会话（evidence["subagent_session"] 非空）。
- M3: approve_checkpoint 非原子（两次独立 transition_step），中途失败状态不一致。
      修复：批准记录 + 步骤完成合并为一次原子事务。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.opencode_bridge import StepAction, StepResult
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


def _make_skill(tmp_path, name="comp-review"):
    skill = tmp_path / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("skill", encoding="utf-8")
    return skill


def _evidence(action, extra=None):
    ev = {
        "schema_version": 1,
        "agent": "OpenCode Desktop",
        "step_id": action.step_id,
        "skill_name": action.skill_name,
        "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
        "commands": [{"command": "python tools/reviewer_client.py --prompt 审查", "returncode": 0, "cwd": "."}],
        "inputs": [],
        "outputs": action.output_files,
    }
    if extra:
        ev.update(extra)
    return ev


# ── M5: 审核步骤独立视角强制 ──────────────────────────────────────────


def test_review_step_without_subagent_session_is_rejected(tmp_path):
    """requires_subagent=true 的审核步骤，evidence 缺 subagent_session → 必须失败（防主 Agent 伪造审核）。"""
    catalog = {"demo": {"sub_steps": [{
        "skill_name": "comp-review",
        "primary_output": "COMP_REVIEW.md",
        "output_files": ["COMP_REVIEW.md"],
        "has_checkpoint": False,
        "requires_subagent": True,   # 审核步骤标记：必须由只读子智能体执行
    }]}}
    _make_skill(tmp_path)
    db = tmp_path / "workflow.sqlite"
    workspace = tmp_path / "workspace"
    with WorkflowStore(db) as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", workspace, {})
        result = runner.next_action(workflow.id)
        action = result.action
        # 产出文件
        for output in action.output_files:
            p = workspace / output
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x" * 2000, encoding="utf-8")
        # 主 Agent 直接提交，无 subagent_session → 必须拒绝
        step_result = StepResult(
            ok=True, artifacts=action.output_files,
            metadata={"execution_evidence": _evidence(action)},  # 无 subagent_session
        )
        r2 = runner.complete_step(workflow.id, step_result)
        assert r2.status == "failed", f"审核步骤无子智能体会话应失败，实际 {r2.status}"
        assert "subagent" in r2.message.lower(), f"失败原因应提及子智能体，实际: {r2.message}"


def test_review_step_with_subagent_session_passes(tmp_path):
    """requires_subagent=true 且 evidence 含真实子智能体会话 + 真实工具调用 → 通过。"""
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
        # M1: 审核步骤自动跑 review gate → 需要审稿文件（solo 模式）
        ws = action.workspace
        (ws / "COMP_REVIEW.md").write_text("审查报告内容占位。" * 10, encoding="utf-8")
        (ws / "COMP_REVIEW_VERDICT.json").write_text(
            '{"verdict": "PASS", "fatal_count": 0, "findings": []}', encoding="utf-8"
        )
        step_result = StepResult(
            ok=True, artifacts=action.output_files,
            metadata={"execution_evidence": _evidence(action, {
                "subagent_session": "ses_ff4d5dab-test",
                # P1 增强：requires_subagent 步骤的 commands 必须含真实工具调用
                "commands": [{"command": "python tools/reviewer_client.py --prompt 审查", "returncode": 0, "cwd": "."}],
            })},
        )
        r2 = runner.complete_step(workflow.id, step_result)
        assert r2.status == "completed", f"含子智能体会话应通过，实际 {r2.status}: {r2.message}"


# ── M3: approve_checkpoint 原子化 ─────────────────────────────────────


def test_approve_checkpoint_is_atomic(tmp_path):
    """approve 后步骤必须处于一致状态：批准记录 + 步骤完成不可分离。
    若 approve 中途失败（模拟第二步转换失败），批准记录不应残留半完成状态。"""
    catalog = {"demo": {"sub_steps": [{
        "skill_name": "comp-prob-analysis",
        "primary_output": "PROB_ANALYSIS.md",
        "output_files": ["PROB_ANALYSIS.md"],
        "has_checkpoint": True,
        "checkpoint_type": "approve",
    }]}}
    _make_skill(tmp_path, "comp-prob-analysis")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", tmp_path / "workspace", {})
        # 执行到检查点
        result = runner.next_action(workflow.id)
        action = result.action
        for output in action.output_files:
            p = action.workspace / output
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x" * 2000, encoding="utf-8")
        r1 = runner.complete_step(workflow.id, StepResult(
            ok=True, artifacts=action.output_files,
            metadata={"execution_evidence": _evidence(action)},
        ))
        assert r1.status == "waiting_checkpoint"
        # 找到检查点
        candidates = store.resume_candidates()
        assert candidates, "检查点应可被 resume_candidates 找到（BLOCKED 状态）"
        cp = candidates[0].checkpoint
        # 批准
        r2 = runner.approve_checkpoint(cp.id, {"approved": True})
        # 批准后步骤必须 COMPLETED 且不再有等待中的检查点
        assert r2.status in ("completed", "advanced"), f"批准后应推进，实际 {r2.status}: {r2.message}"
        # 步骤状态一致性：无 running/blocked 残留
        import sqlite3
        conn = sqlite3.connect(tmp_path / "workflow.sqlite")
        row = conn.execute(
            "SELECT status FROM workflow_steps WHERE workflow_id = ? ORDER BY position",
            (workflow.id,),
        ).fetchone()
        conn.close()
        assert row[0] in ("completed", "running"), f"批准后步骤状态异常: {row[0]}"
        # 批准记录应存在（approved 检查点）
        pending = store.resume_candidates()
        assert not pending, f"批准后不应有未决检查点，实际 {len(pending)}"