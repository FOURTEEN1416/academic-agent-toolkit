"""A2 补丁 1/2 回归测试：状态-事件一致性硬校验 + 防绕过检测接入交付判定。

敌意审计 A2 实测（复现工作区 <home>/AppData/Local/Temp/audits/A2/ws1/）：
直改 sqlite 把步骤置 completed 后引擎完全接受、final-audit 照样 ready；
L1 在位检测到未申报操作也仅 warning、不接入交付判定。
修复：build_final_audit_report 内联运行一致性核查与防绕过检测，违规 →
gate_outcomes 对应 named check fail + delivery_decision=blocked；
check_final_audit_report 增加对应 named check 输出教学性原因。
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit_store import (
    AuditStore,
    build_final_audit_report,
    write_final_audit_report,
)
from engine.quality_gates import QualityGate
from engine.workflow_store import WorkflowStore

PASSING_GATES = {"checks": {"literature": {"ok": True}, "review": {"ok": True},
                            "consistency": {"ok": True}, "final_audit": {"ok": True}}}
PASSING_MANIFEST = {"artifacts": [{"path": "paper/main.pdf", "sha256": "a" * 64}]}


def _make_workflow(tmp_path, steps_metadata):
    """建工作区 + 工作流（含 main.pdf 交付物），返回 (workspace, project_root, db, ids)。"""
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()
    paper = workspace / "paper"
    paper.mkdir()
    (paper / "main.pdf").write_bytes(b"fake pdf bytes")

    db = tmp_path / "workflow.sqlite"
    ids = []
    with WorkflowStore(db) as store:
        workflow = store.create_workflow("comp_cumcm", {"workspace": str(workspace), "params": {}})
        steps = store.add_steps(workflow.id, [
            {"name": name, "metadata": metadata} for name, metadata in steps_metadata
        ])
        ids.append(workflow.id)
        ids.extend(s.id for s in steps)
    return workspace, project_root, db, ids


def _complete_with_event(db, workflow_id, step_id, event_type="step_completed",
                         state_status="completed"):
    """以引擎等价方式完成步骤（合法转移 + 落事件）。"""
    with WorkflowStore(db) as store:
        store.transition_step(step_id, "running")
        store.transition_step_with_checkpoint(
            workflow_id, step_id, "completed",
            {"status": state_status, "manifest": PASSING_MANIFEST, "quality_gates": PASSING_GATES},
            artifacts=[{"name": "main.pdf", "path": "paper/main.pdf"}],
            event={"type": event_type, "quality_gates": PASSING_GATES, "manifest": PASSING_MANIFEST},
        )


def test_direct_db_completion_without_event_fails_final_audit(tmp_path):
    """直改 sqlite 置 completed（不产生事件）→ 一致性 check fail + delivery blocked。"""
    workspace, project_root, db, ids = _make_workflow(
        tmp_path, [("step-a", {"output_files": []}), ("step-b", {"output_files": []})])
    workflow_id, step_a, step_b = ids[0], ids[1], ids[2]
    _complete_with_event(db, workflow_id, step_a)

    # 敌意篡改：绕过引擎直改数据库
    con = sqlite3.connect(str(db))
    con.execute("UPDATE workflow_steps SET status = 'completed' WHERE id = ?", (step_b,))
    con.commit()
    con.close()

    report = build_final_audit_report(workspace, project_root, workflow_db=db)
    assert report["gate_outcomes"]["state_event_consistency"] == "fail"
    assert report["delivery_decision"] == "blocked"
    violations = report["state_event_consistency_detail"]["violations"]
    assert any("step-b" in v and "step_completed" in v for v in violations), violations

    # 交付判定接入质量门禁：AUDIT_REPORT.json 的 final_audit named check 必须拦
    out = write_final_audit_report(workspace, project_root, workflow_db=db)
    gate = QualityGate(workspace).check_final_audit_report()
    assert gate["ok"] is False, f"AUDIT_REPORT 写盘后 gate 应拦: {json.dumps(report, ensure_ascii=False)}"
    assert "state_event_consistency" in gate.get("failed_gates", [])
    assert out.exists()


def test_blocked_release_without_checkpoint_approved_fails(tmp_path):
    """blocked 解除（进入过检查点等待态）必须有 checkpoint_approved 事件。"""
    workspace, project_root, db, ids = _make_workflow(
        tmp_path, [("step-ckpt", {"has_checkpoint": True, "checkpoint_type": "approve"})])
    workflow_id, step_id = ids[0], ids[1]

    with WorkflowStore(db) as store:
        store.transition_step(step_id, "running")
        # 引擎等价的 BLOCKED 进入：waiting_checkpoint 检查点 + step_completed 事件
        store.transition_step_with_checkpoint(
            workflow_id, step_id, "blocked",
            {"status": "waiting_checkpoint", "type": "approve"},
            event={"type": "step_completed", "quality_gates": PASSING_GATES},
        )
    # 敌意篡改：不经 approve 直接置 completed
    con = sqlite3.connect(str(db))
    con.execute("UPDATE workflow_steps SET status = 'completed' WHERE id = ?", (step_id,))
    con.commit()
    con.close()

    report = build_final_audit_report(workspace, project_root, workflow_db=db)
    assert report["gate_outcomes"]["state_event_consistency"] == "fail"
    violations = report["state_event_consistency_detail"]["violations"]
    assert any("checkpoint_approved" in v for v in violations), violations
    assert report["delivery_decision"] == "blocked"


def test_approved_checkpoint_release_passes_consistency(tmp_path):
    """经 approve 的检查点解除（checkpoint_approved 事件在位）→ 一致性通过。"""
    workspace, project_root, db, ids = _make_workflow(
        tmp_path, [("step-ckpt", {"has_checkpoint": True, "checkpoint_type": "approve"})])
    workflow_id, step_id = ids[0], ids[1]

    with WorkflowStore(db) as store:
        store.transition_step(step_id, "running")
        store.transition_step_with_checkpoint(
            workflow_id, step_id, "blocked",
            {"status": "waiting_checkpoint", "type": "approve"},
            event={"type": "step_completed", "quality_gates": PASSING_GATES},
        )
        # 引擎等价的批准解除（approve_checkpoint 同款：COMPLETED + checkpoint_approved）
        store.transition_step_with_checkpoint(
            workflow_id, step_id, "completed",
            {"status": "approved", "response": {"approved": True, "approved_by": "默默"}},
            event={"type": "checkpoint_approved", "approved_by": "默默"},
        )

    report = build_final_audit_report(workspace, project_root, workflow_db=db)
    assert report["gate_outcomes"]["state_event_consistency"] == "pass", \
        report["state_event_consistency_detail"]


def test_unreported_workspace_bash_blocks_delivery(tmp_path):
    """伪造未申报 bash（命令引用工作区路径）→ operation_audit fail + blocked。"""
    workspace, project_root, db, ids = _make_workflow(
        tmp_path, [("step-a", {"output_files": []})])
    workflow_id, step_id = ids[0], ids[1]
    _complete_with_event(db, workflow_id, step_id)

    # 未申报的 bash：直改工作区工作流库（A2 E1 同款篡改命令形态）
    AuditStore(project_root).record({
        "type": "tool_call", "event": "before", "tool": "bash", "sessionID": "rogue",
        "detail": {"command": f'python -c "import sqlite3" {workspace / ".engine" / "workflow.sqlite"}'},
    })

    report = build_final_audit_report(workspace, project_root, workflow_db=db)
    assert report["gate_outcomes"]["operation_audit"] == "fail"
    assert report["operation_audit_detail"]["unreported_bash"], "工作区归属的未申报 bash 必须进入 blocking 列表"
    assert report["delivery_decision"] == "blocked"

    write_final_audit_report(workspace, project_root, workflow_db=db)
    gate = QualityGate(workspace).check_final_audit_report()
    assert gate["ok"] is False
    assert gate.get("failed_gates") == ["operation_audit"]
    assert "未申报" in gate["reason"]


def test_repo_level_noise_does_not_block_delivery(tmp_path):
    """仓库级/跨会话噪声（命令不引用工作区）不触发 blocked——
    防绕过拦截不得制造 A7-F1 同款'永远过不了的闸'。"""
    workspace, project_root, db, ids = _make_workflow(
        tmp_path, [("step-a", {"output_files": []})])
    workflow_id, step_id = ids[0], ids[1]
    _complete_with_event(db, workflow_id, step_id)

    # 其他会话的仓库级操作（与本工作区无关）
    store = AuditStore(project_root)
    store.record({"type": "tool_call", "event": "before", "tool": "bash", "sessionID": "dev",
                  "detail": {"command": "python -m pytest -q"}})
    store.record({"type": "tool_call", "event": "before", "tool": "edit", "sessionID": "dev",
                  "detail": {"filePath": "D:/somewhere/else/LOG.md", "oldLen": 1, "newLen": 2}})

    report = build_final_audit_report(workspace, project_root, workflow_db=db)
    assert report["gate_outcomes"]["operation_audit"] == "pass", report["operation_audit_detail"]
    assert report["delivery_decision"] == "ready"


def test_clean_report_has_named_checks_and_ready(tmp_path):
    """干净工作区：两个 named check 必须在报告里且为 pass，交付 ready。"""
    workspace, project_root, db, ids = _make_workflow(
        tmp_path, [("step-a", {"output_files": []})])
    workflow_id, step_id = ids[0], ids[1]
    _complete_with_event(db, workflow_id, step_id)

    report = build_final_audit_report(workspace, project_root, workflow_db=db)
    assert report["gate_outcomes"]["state_event_consistency"] == "pass"
    assert report["gate_outcomes"]["operation_audit"] == "pass"
    assert report["delivery_decision"] == "ready"

    write_final_audit_report(workspace, project_root, workflow_db=db)
    gate = QualityGate(workspace).check_final_audit_report()
    assert gate["ok"] is True, gate["reason"]


def test_unreadable_workflow_db_fail_closed_state_consistency(tmp_path):
    """MED fix: SQLite 打不开/损坏时 state_consistency.ok 必须为 False，交付 blocked。"""
    workspace, project_root, db, ids = _make_workflow(
        tmp_path, [("step-a", {"output_files": []})])
    workflow_id, step_id = ids[0], ids[1]
    _complete_with_event(db, workflow_id, step_id)

    # 损坏数据库：写入非法内容 → WorkflowStore 查询必抛异常
    Path(db).write_bytes(b"NOT-A-SQLITE-FILE")

    report = build_final_audit_report(workspace, project_root, workflow_db=db)
    detail = report["state_event_consistency_detail"]
    assert detail["ok"] is False, detail
    assert report["gate_outcomes"]["state_event_consistency"] == "fail"
    assert report["delivery_decision"] == "blocked"
    joined = json.dumps(detail, ensure_ascii=False)
    assert "unreadable" in joined or "DB" in joined or "未核验" in joined
