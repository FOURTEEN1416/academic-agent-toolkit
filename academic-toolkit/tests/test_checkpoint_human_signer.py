"""检查点人类署名红线棘轮（2026-09-22，G3 实跑暴露的治理缺口收口）。

before：workflow_runner.approve_checkpoint 只查 response["approved"] is True，
不核 approved_by 署名——子代理可自批人类确认检查点（G3 实跑发生 4 起 agent 代批：
"G3-runner-subagent(批次G3预授权代批)" ×3 + "G3-continuation-subagent(批次G3续跑)" ×1）。
A7R-F1 防伪造红线（quality_gates._agent_self_reference_hit）此前只覆盖
VISUAL_REVIEW_MANUAL_CHECK.md 一个文件。
after：通用 approve checkpoint 与 A7R-F1 同源——approved_by 缺失/为空或命中
agent 自指词 → blocked 硬拦，不转步骤状态、不写 checkpoint_approved 事件。
回退成"事件存在即过"会直接打破本文件。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore

CATALOG = {"demo": {"sub_steps": [
    {"skill_name": "comp-prob-analysis", "primary_output": "PROB_ANALYSIS.md",
     "output_files": ["PROB_ANALYSIS.md"], "has_checkpoint": True,
     "checkpoint_type": "approve"},
]}}


def _make_waiting_checkpoint(tmp_path):
    """造一个 waiting_checkpoint + blocked 步骤（口径同 test_workflow_retry_cli 脚手架）。"""
    db = tmp_path / "workflow.sqlite"
    store = WorkflowStore(db)  # 同一连接读己写；测试结束随进程回收
    runner = WorkflowRunner(store, CATALOG, ROOT / "skills")
    workflow = store.create_workflow("demo", {"workspace": str(tmp_path)})
    step = store.add_steps(workflow.id, [dict(CATALOG["demo"]["sub_steps"][0],
                                              name="comp-prob-analysis")])[0]
    store.transition_step(step.id, "blocked")
    checkpoint = store.create_checkpoint(
        workflow.id, step.id, {"status": "waiting_checkpoint", "type": "approve"})
    return store, runner, workflow.id, checkpoint.id, step.id


def _approved_events(store):
    rows = store._connection.execute(
        "SELECT payload FROM events WHERE event_type = 'checkpoint_approved'").fetchall()
    return [__import__("json").loads(r[0]) for r in rows]


def _step_status(store, step_id):
    row = store._connection.execute(
        "SELECT status FROM workflow_steps WHERE id = ?", (step_id,)).fetchone()
    return row["status"]


def test_approve_signed_by_agent_is_blocked(tmp_path):
    """agent 自指署名（英文词）批准 → blocked，无状态转移、无批准事件。"""
    store, runner, wf_id, cp_id, step_id = _make_waiting_checkpoint(tmp_path)
    r = runner.approve_checkpoint(cp_id, {"approved": True,
                                          "approved_by": "G3-runner-subagent(批次G3预授权代批)"})
    assert r.status == "blocked", f"agent 署名竟被放行: {r.status} {r.message}"
    assert _approved_events(store) == []
    assert _step_status(store, step_id) != "completed"


def test_approve_signed_with_cjk_agent_word_is_blocked(tmp_path):
    """中文自指词（智能体/机器人/自动）同样硬拦——与 A7R-F1 词表同源。"""
    store, runner, wf_id, cp_id, step_id = _make_waiting_checkpoint(tmp_path)
    r = runner.approve_checkpoint(cp_id, {"approved": True, "approved_by": "数模智能体"})
    assert r.status == "blocked", f"中文自指署名竟被放行: {r.status}"
    assert _approved_events(store) == []


def test_approve_without_signer_is_blocked(tmp_path):
    """approved_by 缺失/空白一律拒——禁止无痕批准（CLI 已锁 --by 必填，此处封引擎直调旁路）。"""
    store, runner, wf_id, cp_id, step_id = _make_waiting_checkpoint(tmp_path)
    r = runner.approve_checkpoint(cp_id, {"approved": True})
    assert r.status == "blocked", "无署名批准竟被放行"
    r2 = runner.approve_checkpoint(cp_id, {"approved": True, "approved_by": "   "})
    assert r2.status == "blocked"
    assert _approved_events(store) == []


def test_approve_with_human_signer_still_completes(tmp_path):
    """人类署名路径行为不变：批准事件在位、工作流推进（防红线误伤正常路径）。"""
    store, runner, wf_id, cp_id, step_id = _make_waiting_checkpoint(tmp_path)
    r = runner.approve_checkpoint(cp_id, {"approved": True, "approved_by": "默默"})
    assert r.status in ("completed", "advanced"), f"人类署名被误伤: {r.status} {r.message}"
    events = _approved_events(store)
    assert len(events) == 1 and events[0]["approved_by"] == "默默"
