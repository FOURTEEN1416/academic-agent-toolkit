"""独立评审收发链：版本绑定、一次性接收、裁定不可改写、新版本重评可恢复。

B窗 2026-09-26：此前评审链零专项覆盖（重点1-4/重点2 的固化）。
记录程序可观察事实；不声称认证宿主身份——信任边界在断言中显式核对。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from execution.session import ExecutionSession


def make_session(tmp_path: Path, *, metadata=None):
    skills = tmp_path / "suite/skills"
    for name in ("demo", "extra"):
        folder = skills / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text("Real task instructions: calculate the result.", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    catalog = {"demo": {"sub_steps": [{"skill_name": "demo",
        "output_files": ["result.txt", "REVIEW_RESULT.md"], "primary_output": "result.txt",
        "has_checkpoint": False,
        "metadata": {"skill_binding": {"main_required": True}, "requires_subagent": True,
                     **(metadata or {})}}]}}
    runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
    wf = runner.start("demo", tmp_path / "work", {"agent": "executor-agent"})
    session = ExecutionSession(runner, wf.id)
    session.context()
    return store, runner, wf.id, session


def produce(session, value="7"):
    session.files.write("input.txt", value)
    session.files.write("solve.py",
        "from pathlib import Path\nPath('result.txt').write_text(str(int(Path('input.txt').read_text()) * 2))\n")
    return {"id": "solve", "argv": [sys.executable, "solve.py"],
            "inputs": ["input.txt", "solve.py"], "outputs": ["result.txt"],
            "pure": True, "complete_inputs": True}


def put(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_request_binds_versions_and_rejects_invalid_targets(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("result.txt", "draft result")
    with pytest.raises(ValueError, match="真实输入"):
        session.review.request(inputs=[], output="REVIEW_RESULT.md", rubric="  ")
    with pytest.raises(ValueError, match="合同产物"):
        session.review.request(inputs=["result.txt"], output="OTHER.md", rubric="r")
    with pytest.raises(ValueError, match="覆盖受审输入"):
        session.review.request(inputs=["result.txt"], output="result.txt", rubric="r")
    req = session.review.request(inputs=["result.txt"], output="REVIEW_RESULT.md", rubric="检查正确性")
    task = json.loads(Path(req["review_task"]).read_text(encoding="utf-8"))
    assert task["status"] == "awaiting_independent_context"
    assert task["host_attested"] is False
    assert set(task["inputs"]) == {"result.txt"} and len(task["inputs"]["result.txt"]) == 64
    assert task["revision"] == session.action.expected_revision
    store.close()


def test_executor_cannot_self_review_and_receive_requires_identity(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.commands.execute(produce(session))
    req = session.review.request(inputs=["result.txt"], output="REVIEW_RESULT.md", rubric="r")
    task_file = req["review_task"]
    response = put(session.workspace / "inbox" / "resp.md", "REVIEW: result 14 is correct. No fatal issues.")
    with pytest.raises(ValueError, match="实际评审者"):
        session.review.receive(task_file, str(response), reviewer="  ", host_call_id="call-1")
    with pytest.raises(ValueError, match="执行者不能把自己声明为独立评审者"):
        session.review.receive(task_file, str(response), reviewer="executor-agent", host_call_id="call-1")
    store.close()


def test_receive_stores_verbatim_and_records_trust_boundary(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.commands.execute(produce(session))
    req = session.review.request(inputs=["result.txt"], output="REVIEW_RESULT.md", rubric="r")
    original = "INDEPENDENT REVIEW: method sound, result 14 correct. No fatal issues."
    response = put(session.workspace / "inbox" / "resp.md", original)
    result = session.review.receive(req["review_task"], str(response),
                                    reviewer="independent-reviewer", host_call_id="host-call-xyz")
    assert result["status"] == "succeeded"
    stored = (session.workspace / "REVIEW_RESULT.md").read_text(encoding="utf-8")
    assert stored == original, "评审原文必须逐字落盘，不允许执行侧改写"
    op = [o for o in store.execution_operations(session.action.step_id, session.action.attempt_id)
          if o["kind"] == "review"][-1]
    assert op["payload"]["host_call_id"] == "host-call-xyz"
    assert "not independently authenticated" in op["payload"]["verification_level"], \
        "信任边界必须如实记录：宿主身份未经独立认证"
    store.close()


def test_received_task_cannot_be_received_again(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.commands.execute(produce(session))
    req = session.review.request(inputs=["result.txt"], output="REVIEW_RESULT.md", rubric="r")
    first = put(session.workspace / "inbox" / "r1.md", "FIRST VERDICT: no fatal issues found here.")
    session.review.receive(req["review_task"], str(first), reviewer="a", host_call_id="c1")
    second = put(session.workspace / "inbox" / "r2.md", "OVERWRITE ATTEMPT: approve everything now please.")
    with pytest.raises(ValueError, match="不能覆盖"):
        session.review.receive(req["review_task"], str(second), reviewer="b", host_call_id="c2")
    assert (session.workspace / "REVIEW_RESULT.md").read_text(encoding="utf-8") == \
        "FIRST VERDICT: no fatal issues found here."
    store.close()


def test_tampered_verdict_fails_acceptance(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.commands.execute(produce(session))
    req = session.review.request(inputs=["result.txt"], output="REVIEW_RESULT.md", rubric="r")
    response = put(session.workspace / "inbox" / "r1.md", "HONEST REVIEW: one fatal issue: direction reversed.")
    session.review.receive(req["review_task"], str(response), reviewer="a", host_call_id="c1")
    (session.workspace / "REVIEW_RESULT.md").write_text(
        "FORGED VERDICT: no issues at all, approved.", encoding="utf-8")
    result = session.finish()
    assert result["status"] == "needs_work"
    assert "独立评审原文被后续操作覆盖" in str(result["diagnostics"])
    store.close()


def test_stale_task_rejected_after_input_changes_and_rereview_recoverable(tmp_path):
    store, runner, wf, session = make_session(tmp_path,
        metadata={"output_specs": {"result.txt": {"min_bytes": 200}}})
    session.commands.execute(produce(session))
    req1 = session.review.request(inputs=["result.txt"], output="REVIEW_RESULT.md", rubric="r")
    r1 = put(session.workspace / "inbox" / "r1.md",
             "ATTEMPT-1 REVIEW: too thin, fatal: insufficient substance for delivery.")
    session.review.receive(req1["review_task"], str(r1), reviewer="a", host_call_id="c1")
    first = session.finish()
    assert first["status"] == "needs_work", "未达标版本必须返修"
    # 返修产物 → 旧评审任务的输入版本失效
    session.files.write("result.txt", "substantive revised result content " * 30)
    stale = put(session.workspace / "inbox" / "stale.md",
                "STALE VERDICT: attempt-1 conclusion still stands, nothing to add.")
    with pytest.raises(ValueError):
        session.review.receive(req1["review_task"], str(stale), reviewer="a", host_call_id="c2")
    # 当前版本重新评审 → 恢复并通过
    req2 = session.review.request(inputs=["result.txt"], output="REVIEW_RESULT.md", rubric="r")
    assert Path(req2["review_task"]) != Path(req1["review_task"])
    r2 = put(session.workspace / "inbox" / "r2.md",
             "ATTEMPT-1B RE-REVIEW: revised substance verified. Zero fatal issues.")
    session.review.receive(req2["review_task"], str(r2), reviewer="a", host_call_id="c3")
    second = session.finish()
    assert second["status"] == "completed", f"新版本重评后应通过: {second.get('diagnostics')}"
    store.close()


def test_receive_rejects_missing_or_tiny_response(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.commands.execute(produce(session))
    req = session.review.request(inputs=["result.txt"], output="REVIEW_RESULT.md", rubric="r")
    tiny = put(session.workspace / "inbox" / "tiny.md", "ok")
    with pytest.raises(ValueError, match="缺失或不完整"):
        session.review.receive(req["review_task"], str(tiny), reviewer="a", host_call_id="c1")
    with pytest.raises(ValueError):
        session.review.receive(req["review_task"], str(session.workspace / "inbox" / "absent.md"),
                               reviewer="a", host_call_id="c1")
    store.close()


def test_round_numbers_derived_from_engine_operations(tmp_path):
    """轮次号由引擎操作记录推导，不经模型填报；与业务层轮次记录可对账。"""
    store, runner, wf, session = make_session(tmp_path)
    session.commands.execute(produce(session))
    req1 = session.review.request(inputs=["result.txt"], output="REVIEW_RESULT.md", rubric="r")
    assert req1["round"] == 1
    v1 = put(session.workspace / "inbox" / "v1.md", "ROUND-1: not ready, fatal issues remain here.")
    got = session.review.receive(req1["review_task"], str(v1), reviewer="a", host_call_id="c1")
    assert got.get("round") == 1
    session.files.write("result.txt", "revised result content " * 30)
    req2 = session.review.request(inputs=["result.txt"], output="REVIEW_RESULT.md", rubric="r")
    assert req2["round"] == 2, "第二次请求轮次自动递增"
    v2 = put(session.workspace / "inbox" / "v2.md",
             "ROUND-2 REVIEW: ready. Revised manuscript addresses all fatal issues from round one.")
    got2 = session.review.receive(req2["review_task"], str(v2), reviewer="a", host_call_id="c2")
    assert got2.get("round") == 2
    op = [o for o in store.execution_operations(session.action.step_id, session.action.attempt_id)
          if o["kind"] == "review" and o["status"] == "succeeded"][-1]
    assert op["payload"].get("round") == 2, "轮次随真实返回记录闭合存档"
    store.close()


def _write_round(workspace: Path, i: int, verdict="ready. minor issues only listed below. score 7/10"):
    tasks = workspace / "review_tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    (tasks / f"round_{i}.task.md").write_text(f"# Review Task — Round {i}\nInput: manuscript v{i}\n", encoding="utf-8")
    (tasks / f"round_{i}.verdict.md").write_text(f"Score: 7/10\nVerdict: {verdict}\n", encoding="utf-8")


def test_review_rounds_reconciliation(tmp_path):
    from engine.quality_gates import QualityGate
    gate = QualityGate(tmp_path)

    # 无状态文件 → 不启用对账（不误拒无轮机制的用法）
    assert gate.check_review_rounds()["skipped"] is True

    # 声称3轮 + 3轮真实任务卡与评审原文 → 通过（MAX_ROUNDS=4 内提前/做满均合法）
    for i in (1, 2, 3):
        _write_round(tmp_path, i, verdict="not ready, fix listed" if i < 3 else "ready, score 7/10")
    (tmp_path / "REVIEW_STATE.json").write_text(
        '{"round": 3, "status": "completed", "review_driver": "independent"}', encoding="utf-8")
    report = gate.check_review_rounds()
    assert report["ok"] and report["claimed_rounds"] == 3 and report["verified_rounds"] == 3, report

    # 1轮即 positive 收官 → 合法提前结束，不误拒
    fresh = tmp_path / "early"
    fresh.mkdir()
    _write_round(fresh, 1, verdict="ready, score 8/10")
    (fresh / "REVIEW_STATE.json").write_text('{"round": 1, "status": "completed"}', encoding="utf-8")
    assert QualityGate(fresh).check_review_rounds()["ok"] is True

    # 声称4轮但只有1轮真实记录 → 违规（没有真实评审不能声称完成多轮）
    lying = tmp_path / "lying"
    lying.mkdir()
    _write_round(lying, 1)
    (lying / "REVIEW_STATE.json").write_text('{"round": 4, "status": "completed"}', encoding="utf-8")
    report = QualityGate(lying).check_review_rounds()
    assert not report["ok"] and any("缺" in p for p in report["problems"])

    # verdict 占位（无裁定标记）→ 不计入真实轮次
    hollow = tmp_path / "hollow"
    hollow.mkdir()
    _write_round(hollow, 1, verdict="（待评审占位内容，稍后补充完整意见）")
    (hollow / "REVIEW_STATE.json").write_text('{"round": 1, "status": "completed"}', encoding="utf-8")
    report = QualityGate(hollow).check_review_rounds()
    assert not report["ok"] and any("疑似占位" in p for p in report["problems"])

    # 声称轮数超过 max_rounds 上限 → 违规
    over = tmp_path / "over"
    over.mkdir()
    _write_round(over, 1)
    (over / "REVIEW_STATE.json").write_text('{"round": 6, "max_rounds": 4, "status": "completed"}', encoding="utf-8")
    assert not QualityGate(over).check_review_rounds()["ok"]


def test_in_step_resume_reconciliation(tmp_path):
    """技能状态文件仅是业务上下文：恢复判定以引擎状态与成果版本为权威，不自动重开。"""
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("result.txt", "current deliverable content")
    # 无状态文件 → 空对账，不干扰
    ctx = session.context()
    assert ctx["in_step_resume"]["state_files"] == []
    assert ctx["in_step_resume"]["authority"] == "engine_workflow_store"

    # in_progress → 正常续作判定
    (session.workspace / "REVIEW_STATE.json").write_text(
        '{"round": 2, "status": "in_progress"}', encoding="utf-8")
    ctx = session.context()
    entry = ctx["in_step_resume"]["state_files"][0]
    assert entry["verdict"] == "resume" and entry["recorded_progress"] == 2

    # 状态文件声称 completed 而引擎步骤未验收 → 冲突：不得当完成交付，也不得静默重开
    (session.workspace / "REVIEW_STATE.json").write_text(
        '{"round": 3, "status": "completed"}', encoding="utf-8")
    ctx = session.context()
    entry = ctx["in_step_resume"]["state_files"][0]
    assert entry["verdict"] == "conflict_engine_not_accepted"
    assert "不得当作已完成交付" in entry["guidance"] and "不得静默重开" in entry["guidance"]

    # 引擎成果版本随真实产物记录（独立于状态文件）
    assert "result.txt" in ctx["in_step_resume"]["engine"]["outputs_version"]
    # 坏状态文件不炸 context，降级为 context_only
    (session.workspace / "REVIEW_STATE.json").write_text("{broken", encoding="utf-8")
    ctx = session.context()
    assert ctx["in_step_resume"]["state_files"][0]["verdict"] == "context_only"
    store.close()


def test_legacy_contract_records_still_accepted_without_rerun(tmp_path):
    """收口1：历史 scope1 全量合同记录按 legacy 口径对账通过，不回写、不要求重跑。"""
    skills = tmp_path / "suite/skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text("Real task instructions: calculate the result.", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    catalog = {"demo": {"sub_steps": [{"skill_name": "demo", "output_files": ["result.txt"],
        "primary_output": "result.txt", "has_checkpoint": False,
        "metadata": {"skill_binding": {"main_required": True}}}]}}
    runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
    wf = runner.start("demo", tmp_path / "work", {"agent": "executor-agent"})
    session = ExecutionSession(runner, wf.id)
    session.context()
    session.files.write("solve.py",
        "from pathlib import Path\nPath('result.txt').write_text('legacy ok ' + 'x'*80)\n")
    session.commands.execute({"id": "solve", "argv": [sys.executable, "solve.py"],
        "inputs": ["solve.py"], "outputs": ["result.txt"], "pure": True, "complete_inputs": True})
    cmd_row = [o for o in store.execution_operations(session.action.step_id, session.action.attempt_id)
               if o["kind"] == "command"][-1]
    from engine.execution_protocol import execution_contract, legacy_execution_contract
    rules = session.action.skill_path.parents[2] / "engine/modex-core"
    legacy = legacy_execution_contract(session.action, store.get_step(session.action.step_id).metadata,
                                       {"agent": "executor-agent"}, rules)
    assert legacy != execution_contract(session.action, store.get_step(session.action.step_id).metadata,
                                        {"agent": "executor-agent"}, rules)
    payload = dict(cmd_row["payload"])
    payload["contract"] = legacy
    store._connection.execute("UPDATE execution_operations SET payload=? WHERE id=?",
        (json.dumps(payload, ensure_ascii=False), cmd_row["id"]))
    store._connection.commit()
    result = session.finish()
    assert result["status"] == "completed", str(result.get("diagnostics"))
    store.close()


def test_role_actual_call_capture_gap_is_explicit_not_silent(tmp_path):
    """收口4：sidecar 缺席时缺口显式 warning（不模拟通过）；sidecar 存在时交叉硬拦仍在。"""
    import hashlib
    ws = tmp_path / "roles_ws"
    ws.mkdir()
    verdict = json.dumps({"findings": [], "fatal_count": 0}, ensure_ascii=False)
    bodies = {"COMP_REVIEW.md": "r", "VISUAL_REVIEW.md": "v", "EDITOR_CHANGELOG.md": "e",
              "FINAL_REVIEW.md": "f", "COMP_REVIEW_VERDICT.json": verdict,
              "VISUAL_REVIEW_VERDICT.json": json.dumps({"findings": [], "fatal_count": 0, "status": "pass"}),
              "FINAL_REVIEW_VERDICT.json": verdict}
    roles = {}
    for name, content in bodies.items():
        (ws / name).write_text(content, encoding="utf-8")
    for role, name in (("reviewer", "COMP_REVIEW.md"), ("visual_reviewer", "VISUAL_REVIEW.md"),
                       ("editor", "EDITOR_CHANGELOG.md"), ("final_reviewer", "FINAL_REVIEW.md")):
        roles[role] = {"session_id": f"s-{role}", "model": "claimed-model", "output_file": name,
                       "completed_at": "2026-09-27T00:00:00",
                       "output_sha256": hashlib.sha256(bodies[name].encode()).hexdigest()}
    (ws / "REVIEW_EXECUTION_EVIDENCE.json").write_text(json.dumps({"roles": roles}), encoding="utf-8")
    from engine.quality_gates import QualityGate
    result = QualityGate(ws).check_review_evidence(mode="full")
    assert result["ok"] is True
    assert result.get("actual_call_capture") == "absent", "采集缺口必须显式可见"
    (ws / ".engine").mkdir()
    (ws / ".engine" / "role_calls_actual.json").write_text(json.dumps({"roles": {
        "reviewer": {"model": "actually-different-model", "base_url": "x"}}}), encoding="utf-8")
    blocked = QualityGate(ws).check_review_evidence(mode="full")
    assert blocked["ok"] is False and "未申报通道" in blocked.get("reason", "")
    assert blocked.get("actual_call_capture") == "captured"
