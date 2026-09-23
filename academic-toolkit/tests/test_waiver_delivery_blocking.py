"""A2R fatal 修复回归：skip_ 豁免只留痕、不放行（waiver 硬闸）。

修复前（敌意审计 A2R 实测）：start 参数 skip_review=true 在 resolve 时静默删除
全部 4 个审核步骤，final audit 对 waivers 仅 informational 记录——
delivery_ready 公式不含 waivers，工作流走完后 delivery_decision 照常 ready，
审核防线"合法"消失且不留任何阻断。
修复后：build_final_audit_report 中 waivers 非空 → gate_outcomes 新增
waiver_review=fail、delivery_decision 强制 blocked，报告注记 waiver_detail
（保留 waivers 字段本身作留痕）；check_final_audit_report 对应硬拦并教学解除方式。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit_store import build_final_audit_report, write_final_audit_report
from engine.opencode_bridge import StepResult
from engine.quality_gates import QualityGate
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


def _catalog(with_review_step: bool):
    steps = [{
        "skill_name": "comp-prob-analysis",
        "primary_output": "REPORT.md",
        "output_files": ["REPORT.md"],
        "has_checkpoint": False,
    }]
    if with_review_step:
        steps.append({
            "skill_name": "comp-review",
            "primary_output": "REVIEW.md",
            "output_files": ["REVIEW.md"],
            "has_checkpoint": False,
        })
    return {"demo": {"sub_steps": steps}}


def _setup(tmp_path, params, with_review_step):
    """runner.start（含 skip 参数）+ 逐完成剩余步骤（合法路径，带完整执行证据）。"""
    skill = tmp_path / "skills" / "comp-prob-analysis" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("skill", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, _catalog(with_review_step), tmp_path / "skills")
    workflow = runner.start("demo", tmp_path / "workspace", params)

    while True:
        result = runner.next_action(workflow.id)
        if result.action is None:
            break  # completed
        action = result.action
        for output in action.output_files:
            path = action.workspace / output
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x" * 3000, encoding="utf-8")
        evidence = {
            "schema_version": 1,
            "agent": "OpenCode Desktop",
            "step_id": action.step_id,
            "skill_name": action.skill_name,
            "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
            "commands": [{"command": f"python gen.py --out {action.primary_output}",
                          "returncode": 0, "cwd": "."}],
            "inputs": [],
            "outputs": list(action.output_files),
        }
        completion = runner.complete_step(workflow.id, StepResult(
            ok=True, artifacts=list(action.output_files),
            metadata={"execution_evidence": evidence}))
        assert completion.status in ("advanced", "completed"), completion.message
    return store, runner, workflow.id


def _workspace_with_paper(tmp_path):
    """build_final_audit_report 需要 (workspace, project_root)；交付物走事件 manifest。"""
    return tmp_path / "workspace", tmp_path / "project"


def test_skip_review_workflow_completes_but_delivery_blocked(tmp_path):
    """skip_review=true 启动的工作流即使全部步骤合法走完，final audit 也必须 blocked。"""
    for directory in ("workspace", "project"):
        (tmp_path / directory).mkdir()
    store, runner, wf_id = _setup(tmp_path, params={"skip_review": True}, with_review_step=True)
    # 审核步骤确实被静默删除（防线从未运行）——这正是必须 blocked 的原因
    rows = store._connection.execute(
        "SELECT name FROM workflow_steps WHERE workflow_id = ?", (wf_id,)).fetchall()
    assert [r["name"] for r in rows] == ["comp-prob-analysis"], "skip_review 应删除审核步骤"
    assert runner.next_action(wf_id).action is None, "工作流应已全部完成"

    workspace, project_root = _workspace_with_paper(tmp_path)
    report = build_final_audit_report(workspace, project_root,
                                      workflow_db=tmp_path / "workflow.sqlite")
    # waivers 字段保留作留痕
    assert report["waivers"] == ["skip_review"]
    assert report["waiver_detail"]["hit_params"] == ["skip_review"]
    # 但豁免不再放行：waiver_review fail + delivery blocked
    assert report["gate_outcomes"]["waiver_review"] == "fail"
    assert report["delivery_decision"] == "blocked", json.dumps(report, ensure_ascii=False)

    # 交付门禁同步硬拦，且教学解除方式
    write_final_audit_report(workspace, project_root, workflow_db=tmp_path / "workflow.sqlite")
    gate = QualityGate(workspace).check_final_audit_report()
    assert gate["ok"] is False
    assert gate.get("failed_gates") == ["waiver_review"]
    assert "豁免" in gate["reason"]
    assert "skip_review" in gate["reason"]


def test_workflow_without_waivers_still_ready(tmp_path):
    """无豁免参数的干净工作流不受影响：waiver_review=pass、delivery ready（防误伤）。"""
    for directory in ("workspace", "project"):
        (tmp_path / directory).mkdir()
    _setup(tmp_path, params={}, with_review_step=False)

    workspace, project_root = _workspace_with_paper(tmp_path)
    report = build_final_audit_report(workspace, project_root,
                                      workflow_db=tmp_path / "workflow.sqlite")
    assert report["waivers"] == []
    assert report["gate_outcomes"]["waiver_review"] == "pass"
    assert report["delivery_decision"] == "ready", json.dumps(report, ensure_ascii=False)

    write_final_audit_report(workspace, project_root, workflow_db=tmp_path / "workflow.sqlite")
    gate = QualityGate(workspace).check_final_audit_report()
    assert gate["ok"] is True, gate["reason"]
