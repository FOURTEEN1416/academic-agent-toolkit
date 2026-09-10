"""A7-F1 回归测试：第 11 步（comp-visual-review）review 闸死锁修复。

敌意审计 A7 实测（复现工作区 C:/Users/FOUR/AppData/Local/Temp/audits/A7/ws_e2e2/）：
comp-visual-review 在 VISUAL_REVIEW_VERDICT{status:pass} + 合规 evidence 下仍被
complete_step 拒绝——旧 check_review_evidence(auto) 见到 VISUAL_REVIEW.md 即切 full，
强制要求 EDITOR_CHANGELOG.md / FINAL_REVIEW.md / FINAL_REVIEW_VERDICT.json /
REVIEW_EXECUTION_EVIDENCE.json（这些是第 12/13 步产物，顺序上不可能存在）。

修复：auto→full 的升级只由 full 专属产物触发；comp-visual-review 经 run_all 走
mode="visual"（校验视觉对 + 已启动的 COMP 对）。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.opencode_bridge import StepResult
from engine.quality_gates import QualityGate
from engine.step_manifest import write_manifest
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


def _make_skill(tmp_path, name):
    skill = tmp_path / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("skill", encoding="utf-8")


def _evidence(action, extra=None):
    ev = {
        "schema_version": 1,
        "agent": "OpenCode Desktop",
        "step_id": action.step_id,
        "skill_name": action.skill_name,
        "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
        "commands": [{"command": "python tools/data_fig_vision_check.py figures/fig_q1.png --review",
                      "returncode": 0, "cwd": "."}],
        "inputs": [],
        "outputs": action.output_files,
    }
    if extra:
        ev.update(extra)
    return ev


def _finish_step(runner, workflow_id, action, workspace, files):
    """按审核步骤要求产出文件 + manifest + evidence，提交 complete_step。"""
    for name, content in files.items():
        p = workspace / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    write_manifest(
        workspace=workspace,
        step_name=action.skill_name,
        config={},
        outputs=[workspace / f for f in action.output_files],
        backend="test-backend 1.0",
        commands=[{"command": "python tools/data_fig_vision_check.py figures/fig_q1.png --review", "exitCode": 0}],
        dependencies={},
    )
    step_result = StepResult(
        ok=True, artifacts=action.output_files,
        metadata={"execution_evidence": _evidence(action, {"subagent_session": f"ses_visual_{action.skill_name}"})},
    )
    return runner.complete_step(workflow_id, step_result)


def test_step11_visual_review_completes_without_later_step_artifacts(tmp_path):
    """端到端：第 10 步 comp-review 完成后，第 11 步 comp-visual-review 仅凭
    VISUAL_REVIEW 对（status=pass）+ 合规 evidence 必须能通过 review 闸完成。"""
    catalog = {"demo": {"sub_steps": [
        {
            "skill_name": "comp-review",
            "primary_output": "COMP_REVIEW.md",
            "output_files": ["COMP_REVIEW.md", "COMP_REVIEW_VERDICT.json"],
            "has_checkpoint": False,
            "requires_subagent": True,
            "required_checks": ["review"],
        },
        {
            "skill_name": "comp-visual-review",
            "primary_output": "VISUAL_REVIEW.md",
            "output_files": ["VISUAL_REVIEW.md", "VISUAL_REVIEW_VERDICT.json"],
            "has_checkpoint": False,
            "requires_subagent": True,
            "required_checks": ["review"],
        },
    ]}}
    for name in ("comp-review", "comp-visual-review"):
        _make_skill(tmp_path, name)

    workspace = tmp_path / "workspace"
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, tmp_path / "skills")
        workflow = runner.start("demo", workspace, {})

        # ── 第 10 步：comp-review ──
        r1 = runner.next_action(workflow.id)
        assert r1.status == "action" or r1.action is not None
        action1 = r1.action
        r1c = _finish_step(runner, workflow.id, action1, workspace, {
            "COMP_REVIEW.md": "审查报告内容占位。" * 10,
            "COMP_REVIEW_VERDICT.json": json.dumps({"findings": [], "fatal_count": 0}),
        })
        assert r1c.status in ("completed", "advanced"), \
            f"comp-review 应完成，实际 {r1c.status}: {r1c.message}"

        # ── 第 11 步：comp-visual-review（旧代码在此必然死于 review 闸 full 模式）──
        r2 = runner.next_action(workflow.id)
        action2 = r2.action
        assert action2.skill_name == "comp-visual-review"
        r2c = _finish_step(runner, workflow.id, action2, workspace, {
            "VISUAL_REVIEW.md": "视觉审查报告。" * 10,
            "VISUAL_REVIEW_VERDICT.json": json.dumps({"findings": [], "fatal_count": 0, "status": "pass"}),
        })
        assert r2c.status == "completed", (
            "第 11 步 comp-visual-review 应在仅有视觉对（status=pass）+ 合规 evidence 时完成，"
            f"实际 {r2c.status}: {r2c.message}")

        # 复核持久化事件里的 review 闸明细：ok=True 且模式为 visual
        timeline = store.workflow_timeline(workflow.id)
        step_completed = [e for e in timeline["events"] if e["type"] == "step_completed"]
        assert len(step_completed) == 2
        gate = step_completed[-1]["payload"]["quality_gates"]["checks"]["review"]
        assert gate["ok"] is True, f"第 11 步 review 闸应放行: {gate}"
        assert gate["mode"] == "visual"


def test_auto_mode_resolves_visual_pair_to_visual_not_full(tmp_path):
    """auto 模式：COMP 对 + 完整 VISUAL 对、无 editor/final 产物 → visual 模式放行
    （这正是 A7 复现工作区 ws_e2e2 的第 11 步状态）。"""
    ws = tmp_path
    (ws / "COMP_REVIEW.md").write_text("# Review", encoding="utf-8")
    (ws / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (ws / "VISUAL_REVIEW.md").write_text("# Visual", encoding="utf-8")
    (ws / "VISUAL_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0, "status": "pass"}', encoding="utf-8")

    result = QualityGate(ws).check_review_evidence("auto")
    assert result["ok"] is True, f"第 11 步时序应放行: {result}"
    assert result["mode"] == "visual"


def test_visual_mode_rejects_visual_verdict_without_status(tmp_path):
    """visual 模式：视觉裁定缺 status 字段必须拦（禁止伪装通过）。"""
    ws = tmp_path
    (ws / "COMP_REVIEW.md").write_text("# Review", encoding="utf-8")
    (ws / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (ws / "VISUAL_REVIEW.md").write_text("# Visual", encoding="utf-8")
    (ws / "VISUAL_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")

    result = QualityGate(ws).check_review_evidence("visual")
    assert result["ok"] is False
    assert "status" in result["reason"]


def test_visual_mode_strict_when_later_step_artifacts_already_exist(tmp_path):
    """visual 模式：editor/final 专属产物已存在属时序异常 → 按 full 硬校验（缺件不放行）。"""
    ws = tmp_path
    (ws / "COMP_REVIEW.md").write_text("# Review", encoding="utf-8")
    (ws / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (ws / "VISUAL_REVIEW.md").write_text("# Visual", encoding="utf-8")
    (ws / "VISUAL_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0, "status": "pass"}', encoding="utf-8")
    (ws / "EDITOR_CHANGELOG.md").write_text("# Changelog", encoding="utf-8")

    result = QualityGate(ws).check_review_evidence("visual")
    assert result["ok"] is False
    assert "FINAL_REVIEW.md" in result.get("missing", [])


def test_run_all_visual_review_skill_uses_visual_mode(tmp_path):
    """run_all 对 comp-visual-review 应使用 visual 模式（与模板 required_checks 无关）。"""
    ws = tmp_path
    (ws / "COMP_REVIEW.md").write_text("# Review", encoding="utf-8")
    (ws / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (ws / "VISUAL_REVIEW.md").write_text("# Visual", encoding="utf-8")
    (ws / "VISUAL_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0, "status": "pass"}', encoding="utf-8")

    result = QualityGate(ws).run_all("comp-visual-review")
    assert result["ok"] is True, f"run_all 应整体放行: {json.dumps(result['checks'], ensure_ascii=False)}"
    assert result["checks"]["review"]["mode"] == "visual"
