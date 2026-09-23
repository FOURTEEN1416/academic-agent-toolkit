"""A2R fatal 修复回归：状态-事件一致性核查遍历全部工作流（防傀儡工作流致盲）。

修复前（敌意审计 A2R ws3 实测）：build_final_audit_report 只对"最新一个"工作流做
状态-事件一致性核查（ORDER BY created_at DESC LIMIT 1）。攻击者直改旧工作流的
步骤状态（伪造 completed、无事件），再 start 一个干净工作流（纯 CLI 合法操作），
最终审计对傀儡核查=pass、delivery=ready——篡改完全不被报告。
修复后：遍历数据库中全部 workflows 逐一核查并聚合 violations，
被篡改的非最新工作流同样必须被抓。
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit_store import build_final_audit_report, write_final_audit_report
from engine.quality_gates import QualityGate
from engine.workflow_store import WorkflowStore

PASSING_GATES = {"checks": {"literature": {"ok": True}, "review": {"ok": True},
                            "consistency": {"ok": True}, "final_audit": {"ok": True}}}
PASSING_MANIFEST = {"artifacts": [{"path": "paper/main.pdf", "sha256": "a" * 64}]}


def _make_workspace(tmp_path):
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()
    paper = workspace / "paper"
    paper.mkdir()
    (paper / "main.pdf").write_bytes(b"fake pdf bytes")
    return workspace, project_root


def _complete_with_event(db, workflow_id, step_id):
    """以引擎等价方式合法完成步骤（合法转移 + step_completed 事件）。"""
    with WorkflowStore(db) as store:
        store.transition_step(step_id, "running")
        store.transition_step_with_checkpoint(
            workflow_id, step_id, "completed",
            {"status": "completed", "manifest": PASSING_MANIFEST, "quality_gates": PASSING_GATES},
            artifacts=[{"name": "main.pdf", "path": "paper/main.pdf"}],
            event={"type": "step_completed", "quality_gates": PASSING_GATES,
                   "manifest": PASSING_MANIFEST},
        )


def test_tampered_old_workflow_caught_despite_clean_puppet(tmp_path):
    """直改【旧】工作流 + 再开干净傀儡工作流 → 最终审计必须报 violation 并 blocked。"""
    workspace, project_root = _make_workspace(tmp_path)
    db = tmp_path / "workflow.sqlite"

    # 旧工作流：step-a 合法完成；step-b 随后被直改 SQLite 伪造 completed（无事件）
    with WorkflowStore(db) as store:
        wf_old = store.create_workflow("comp_cumcm", {"workspace": str(workspace), "params": {}})
        steps_old = store.add_steps(wf_old.id, [
            {"name": "step-a", "metadata": {"output_files": []}},
            {"name": "step-b", "metadata": {"output_files": []}},
        ])
    _complete_with_event(db, wf_old.id, steps_old[0].id)
    con = sqlite3.connect(str(db))
    con.execute("UPDATE workflow_steps SET status = 'completed' WHERE id = ?", (steps_old[1].id,))
    con.commit()
    con.close()

    # 傀儡工作流：在篡改之后启动（成为"最新"），自身完全合法
    with WorkflowStore(db) as store:
        wf_new = store.create_workflow("comp_cumcm", {"workspace": str(workspace), "params": {}})
        steps_new = store.add_steps(wf_new.id, [{"name": "step-x", "metadata": {"output_files": []}}])
    _complete_with_event(db, wf_new.id, steps_new[0].id)

    report = build_final_audit_report(workspace, project_root, workflow_db=db)
    detail = report["state_event_consistency_detail"]
    assert detail.get("checked_workflows") == 2, detail
    # 时间线仍取最新工作流（傀儡），但 violations 必须点名被篡改的旧工作流
    assert report["workflow_id"] == wf_new.id
    assert detail["ok"] is False
    assert any(wf_old.id in v and "step-b" in v and "step_completed" in v
               for v in detail["violations"]), detail["violations"]
    assert report["gate_outcomes"]["state_event_consistency"] == "fail"
    assert report["delivery_decision"] == "blocked"

    write_final_audit_report(workspace, project_root, workflow_db=db)
    gate = QualityGate(workspace).check_final_audit_report()
    assert gate["ok"] is False
    assert "state_event_consistency" in gate.get("failed_gates", [])


def test_multiple_clean_workflows_still_pass(tmp_path):
    """多个全部合法的工作流不得被多工作流遍历误伤：一致性 pass、delivery ready。"""
    workspace, project_root = _make_workspace(tmp_path)
    db = tmp_path / "workflow.sqlite"

    with WorkflowStore(db) as store:
        wf_1 = store.create_workflow("comp_cumcm", {"workspace": str(workspace), "params": {}})
        steps_1 = store.add_steps(wf_1.id, [{"name": "step-1", "metadata": {"output_files": []}}])
    _complete_with_event(db, wf_1.id, steps_1[0].id)
    with WorkflowStore(db) as store:
        wf_2 = store.create_workflow("comp_cumcm", {"workspace": str(workspace), "params": {}})
        steps_2 = store.add_steps(wf_2.id, [{"name": "step-2", "metadata": {"output_files": []}}])
    _complete_with_event(db, wf_2.id, steps_2[0].id)

    report = build_final_audit_report(workspace, project_root, workflow_db=db)
    detail = report["state_event_consistency_detail"]
    assert detail.get("checked_workflows") == 2
    assert detail["ok"] is True, detail["violations"]
    assert report["gate_outcomes"]["state_event_consistency"] == "pass"
    assert report["delivery_decision"] == "ready", report["gate_outcomes"]
