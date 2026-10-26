"""P2b 返修预算行为锁定（裁决 6.5-A）。

覆盖台账批次三的行为级验收：

- 预算按 (workflow, step) **跨 attempt** 计数（retry 换 attempt 不清零）；
- 超预算 → FAILED + failure_kind="repair_budget_exhausted" + override_required，
  **不复用 BLOCKED**（next_action 不回「等待批准/UUID」）；
- retry 在 override_required 时必须 --by + --override-reason，成功写
  repair_override 审计事件并重置预算（不是批准）；
- needs_work 只回传 blocking + fixable 问题清单，advisory 不回传；
- fixable 只占 1 轮 / 同指纹 3 轮（纯函数口径，注入策略）；
- 出厂配置 enforce=true：安全上限内在出厂策略下即可达 FAILED（6.5 不再只存在于注入策略）。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import repair_budget as rb  # noqa: E402
from engine import workflow_cli  # noqa: E402
from engine.agent_bridge import StepResult  # noqa: E402
from engine.quality_gates import QualityGate, resolve_check_severity  # noqa: E402
from engine.workflow_runner import WorkflowRunner  # noqa: E402
from engine.workflow_store import StepStatus, WorkflowStore  # noqa: E402
from execution.session import ExecutionSession  # noqa: E402


ENFORCED_POLICY = {
    "version": 1,
    "enforce": True,
    "limits": {"blocking": 3, "fixable": 1, "unknown": 2, "same_fingerprint": 3},
}


def _skills(root: Path, names) -> Path:
    skills = root / "skills"
    for name in names:
        path = skills / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"Task instructions for {name}.", encoding="utf-8")
    return skills


def _catalog(required_checks=None) -> dict:
    return {"demo": {"sub_steps": [{
        "skill_name": "demo", "output_files": ["result.txt"],
        "primary_output": "result.txt", "has_checkpoint": False,
        "required_checks": list(required_checks or []),
        "metadata": {"skill_binding": {"main_required": True},
                     "output_specs": {"result.txt": {"min_bytes": 100}}},
    }]}}


def _setup(tmp_path: Path, *, policy=None, required_checks=None):
    skills = _skills(tmp_path, ["demo"])
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, _catalog(required_checks), skills, audit_root=tmp_path,
                            repair_budget_policy=policy)
    workflow = runner.start("demo", tmp_path / "ws", {})
    return store, runner, workflow


def _session(runner, workflow_id, content="too short") -> ExecutionSession:
    session = ExecutionSession(runner, workflow_id)
    session.context()
    session.files.write("result.txt", content)
    return session


# ---------------------------------------------------------------
# ① 预算跨 attempt 计数 → 耗尽转 FAILED（不走 BLOCKED）
# ---------------------------------------------------------------

def test_budget_counts_across_attempts_and_exhausts_to_failed(tmp_path):
    store, runner, workflow = _setup(tmp_path, policy=ENFORCED_POLICY)
    session = _session(runner, workflow.id)
    assert [session.finish()["status"] for _ in range(2)] == ["needs_work", "needs_work"]
    step_id = session.action.step_id
    first_attempt = session.action.attempt_id

    # 非预算原因失败 → retry 开新 attempt（无 override_required，不受门控）
    store.transition_step(step_id, StepStatus.FAILED)
    retried = runner.retry_last_failed(workflow.id, by="tester")
    assert retried.status == "advanced", retried.message
    session2 = _session(runner, workflow.id, content="still short")
    assert session2.action.attempt_id != first_attempt

    # 第 3 轮允许，第 4 轮（跨 attempt 合计）耗尽
    assert session2.finish()["status"] == "needs_work"
    exhausted = session2.finish()
    assert exhausted["status"] == "failed", exhausted["message"]
    diagnostics = exhausted["diagnostics"]
    assert diagnostics["failure_kind"] == "repair_budget_exhausted"
    assert diagnostics["override_required"] is True
    assert diagnostics["repair_budget"]["enforced"] is True
    assert diagnostics["repair_budget"]["total"] == 4
    assert diagnostics["repair_budget"]["reasons"]

    step = store.get_step(step_id)
    assert step.status == StepStatus.FAILED
    state = store.latest_checkpoint_state(step_id)
    assert state["failure_kind"] == "repair_budget_exhausted"
    assert state["override_required"] is True

    # 轮次事实：round 1..4 跨两个 attempt 连续分配（retry 不清零）
    rounds = store.validation_rounds(workflow.id, step_id)
    assert [row["round"] for row in rounds] == [1, 2, 3, 4]
    assert {row["attempt_id"] for row in rounds[:2]} == {first_attempt}
    assert len({row["attempt_id"] for row in rounds}) == 2

    # 与 BLOCKED 死路区分：next 回 failed + override 指引，不带 checkpoint UUID
    following = runner.next_action(workflow.id)
    assert following.status == "failed"
    assert following.checkpoint_id is None
    assert "批准" not in following.message and "UUID" not in following.message
    assert diagnostics["failure_kind"] in (following.message or "")
    assert following.diagnostics["override_required"] is True

    # 事件面：step_failed 带 failure_kind（可审计，不靠响应猜）
    failed_events = store._connection.execute(
        "SELECT payload FROM events WHERE workflow_id=? AND event_type='step_failed' "
        "ORDER BY created_at DESC, rowid DESC LIMIT 1", (workflow.id,)).fetchall()
    assert len(failed_events) == 1
    payload = json.loads(failed_events[0]["payload"])
    assert payload["failure_kind"] == "repair_budget_exhausted"
    assert payload["override_required"] is True
    store.close()


# ---------------------------------------------------------------
# ② retry override 门控 + repair_override 事件落库 + 预算重置
# ---------------------------------------------------------------

def _exhaust(tmp_path):
    store, runner, workflow = _setup(tmp_path, policy=ENFORCED_POLICY)
    session = _session(runner, workflow.id)
    for _ in range(2):
        assert session.finish()["status"] == "needs_work"
    step_id = session.action.step_id
    store.transition_step(step_id, StepStatus.FAILED)
    assert runner.retry_last_failed(workflow.id, by="tester").status == "advanced"
    session2 = _session(runner, workflow.id, content="still short")
    assert session2.finish()["status"] == "needs_work"
    assert session2.finish()["status"] == "failed"
    return store, runner, workflow, step_id


def test_budget_override_retry_requires_reason_and_records_event(tmp_path):
    store, runner, workflow, step_id = _exhaust(tmp_path)

    # 不带 override 参数 → 拒绝，且步骤保持 FAILED（不得静默复位）
    refused = runner.retry_last_failed(workflow.id, by="tester")
    assert refused.status == "failed"
    assert "--override-reason" in refused.message and "--by" in refused.message
    assert store.get_step(step_id).status == StepStatus.FAILED

    # 只有理由没有操作者 → 同样拒绝（override 必须可归责）
    refused_by = runner.retry_last_failed(workflow.id, override_reason="人工确认可重试")
    assert refused_by.status == "failed"
    assert "--by" in refused_by.message
    assert store.get_step(step_id).status == StepStatus.FAILED

    overridden = runner.retry_last_failed(
        workflow.id, by="tester", override_reason="已人工确认真实阻塞，授权再给一轮")
    assert overridden.status == "advanced", overridden.message
    assert overridden.action is not None

    rows = store._connection.execute(
        "SELECT event_type, payload FROM events WHERE workflow_id=? "
        "ORDER BY created_at, rowid", (workflow.id,)).fetchall()
    overrides = [json.loads(row["payload"]) for row in rows
                 if row["event_type"] == "repair_override"]
    assert len(overrides) == 1
    payload = overrides[0]
    assert payload["step_id"] == step_id
    assert payload["by"] == "tester"
    assert payload["reason"] == "已人工确认真实阻塞，授权再给一轮"
    assert payload["failure_kind"] == "repair_budget_exhausted"
    assert payload["prior_attempt_id"]

    # override 是预算重置（时间边界），不是删历史：历史轮次仍在，since 之后为零
    assert store.count_rounds(workflow.id, step_id) == 4
    override_mark = store.last_repair_override(workflow.id, step_id)
    assert override_mark is not None
    assert store.count_rounds(workflow.id, step_id, since=override_mark["created_at"]) == 0

    # 重置后新一轮失败重新计数，不因历史 4 轮立刻转 FAILED
    session = _session(runner, workflow.id, content="after override")
    result = session.finish()
    assert result["status"] == "needs_work", result["message"]
    assert result["diagnostics"]["repair_budget"]["total"] == 1
    store.close()


def test_retry_cli_override_reason_is_wired_and_enforced(tmp_path, monkeypatch, capsys):
    store, runner, workflow, step_id = _exhaust(tmp_path)
    database = store.db_path
    store.close()
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", tmp_path / "workflow-index.json")

    def run_cli(*args):
        monkeypatch.setattr(sys, "argv", ["workflow_cli", *args])
        code = workflow_cli.main()
        out = capsys.readouterr().out
        return code, (json.loads(out) if out.strip() else {})

    code, refused = run_cli("retry", "--wf", workflow.id, "--db", str(database),
                            "--by", "cli-tester")
    assert code == 1 and refused["status"] == "failed"
    assert "--override-reason" in refused["message"]

    code, accepted = run_cli("retry", "--wf", workflow.id, "--db", str(database),
                             "--by", "cli-tester",
                             "--override-reason", "CLI 显式覆盖留痕")
    assert code == 0, json.dumps(accepted, ensure_ascii=False)
    assert accepted["status"] == "advanced"

    with WorkflowStore(database) as store2:
        payloads = [json.loads(row["payload"]) for row in store2._connection.execute(
            "SELECT payload FROM events WHERE event_type='repair_override'").fetchall()]
        assert len(payloads) == 1
        assert payloads[0]["by"] == "cli-tester"
        assert payloads[0]["reason"] == "CLI 显式覆盖留痕"


# ---------------------------------------------------------------
# ③ needs_work 只回传 blocking+fixable（advisory 不回传）
# ---------------------------------------------------------------

def test_needs_work_echoes_only_blocking_and_fixable_issues(tmp_path, monkeypatch):
    monkeypatch.setattr(QualityGate, "check_ai_flavor",
                        lambda self: {"ok": False, "reason": "AI 痕迹 4 处，超阈"})
    store, runner, workflow = _setup(tmp_path, required_checks=["ai_flavor"])
    session = _session(runner, workflow.id)
    result = session.finish()
    assert result["status"] == "needs_work", result["message"]

    diagnostics = result["diagnostics"]
    assert "quality:ai_flavor" in diagnostics["advisories"]
    issue_names = [issue["check"] for issue in diagnostics["repair_issues"]]
    assert "output_spec:result.txt" in issue_names
    # advisory 不进待修清单，也不进回传消息
    assert "quality:ai_flavor" not in issue_names
    assert set(issue_names).isdisjoint(diagnostics["advisories"])
    assert all(issue["severity"] in {"blocking", "fixable"} for issue in diagnostics["repair_issues"])
    assert "ai_flavor" not in result["message"]
    store.close()


# ---------------------------------------------------------------
# ④ 预算口径：fixable 1 轮 / 同指纹 3 轮 / failure_kind 三态
# ---------------------------------------------------------------

def _rounds(*entries):
    return [{"round": index + 1, "fingerprint": fingerprint, "codes": codes}
            for index, (fingerprint, codes) in enumerate(entries)]


def test_fixable_rounds_are_limited_to_one():
    policy = rb.policy_from_mapping(ENFORCED_POLICY)
    first = rb.summarize(_rounds(("fp-a", ["consistency"])), policy,
                         severity_of=resolve_check_severity)
    assert first["severity"] == "fixable"
    assert first["exhausted"] is False
    second = rb.summarize(_rounds(("fp-a", ["consistency"]), ("fp-b", ["consistency"])), policy,
                          severity_of=resolve_check_severity)
    assert second["by_severity"]["fixable"] == 2
    assert second["exhausted"] is True
    assert any("fixable" in reason for reason in second["reasons"])


def test_same_fingerprint_limit_is_three_rounds():
    policy = rb.policy_from_mapping({
        "enforce": True,
        "limits": {"blocking": 10, "fixable": 10, "unknown": 10, "same_fingerprint": 3},
    })
    three = rb.summarize(_rounds(("same", ["protocol"]), ("same", ["protocol"]),
                                 ("same", ["protocol"])), policy,
                         severity_of=resolve_check_severity)
    assert three["exhausted"] is False
    four = rb.summarize(_rounds(*[("same", ["protocol"])] * 4), policy,
                        severity_of=resolve_check_severity)
    assert four["exhausted"] is True
    assert any("指纹" in reason for reason in four["reasons"])


def test_failure_kind_distinguishes_product_and_checker_failures(tmp_path):
    assert WorkflowRunner._failure_kind(
        {"checks": {"x": {"status": "unknown"}}}) == "checker_error"
    assert WorkflowRunner._failure_kind(
        {"checks": {"x": {"status": "unknown"}, "y": {"status": "fail"}}}) == "validation_failed"

    # 产物不合格（legacy 失败路径）也带 failure_kind=validation_failed
    store, runner, workflow = _setup(tmp_path)
    action = runner.next_action(workflow.id).action
    failed = runner.complete_step(workflow.id, StepResult(
        ok=False, stderr="boom", step_id=action.step_id,
        attempt_id=action.attempt_id, expected_revision=action.expected_revision))
    assert failed.status == "failed"
    assert failed.diagnostics["failure_kind"] == "validation_failed"
    assert store.latest_checkpoint_state(action.step_id)["failure_kind"] == "validation_failed"
    store.close()


# ---------------------------------------------------------------
# ⑤ 配置：出厂启用安全上限 + 默认策略同样可达 FAILED
# ---------------------------------------------------------------

def test_budget_config_ships_enforced_safe_caps(tmp_path):
    policy = rb.load_policy()
    assert policy["enforce"] is True
    assert policy["limits"] == {"blocking": 5, "fixable": 3, "unknown": 2, "same_fingerprint": 4}
    assert policy["source"].endswith("repair_budget.json")
    # registry 必须留在 checkers/ 子目录（modex-core 根 glob("*.json") 会进合同哈希）
    assert rb.POLICY_PATH.parent.name == "checkers"
    bad = rb.POLICY_PATH.parent / "_bad_budget.json"
    bad.write_text("{not json", encoding="utf-8")
    try:
        with pytest.raises(rb.RepairBudgetConfigError, match="不是合法 JSON"):
            rb.load_policy(bad)
    finally:
        bad.unlink()
    # 缺文件不得静默关闭预算：按同一套上限 fail-closed
    missing = rb.load_policy(tmp_path / "_missing_budget.json")
    assert missing["enforce"] is True
    assert missing["limits"] == {"blocking": 5, "fixable": 3, "unknown": 2, "same_fingerprint": 4}


def test_default_policy_exhausts_at_safe_caps(tmp_path):
    """出厂配置（不注入策略）下连续同指纹失败：第 5 轮转 FAILED（6.5 生产可达）。"""
    store, runner, workflow = _setup(tmp_path)  # 不注入策略 → 读出厂 repair_budget.json
    session = _session(runner, workflow.id)
    statuses = [session.finish()["status"] for _ in range(4)]
    assert statuses == ["needs_work"] * 4
    exhausted = session.finish()
    assert exhausted["status"] == "failed", exhausted["message"]
    diagnostics = exhausted["diagnostics"]
    budget = diagnostics["repair_budget"]
    assert budget["enforced"] is True
    assert budget["total"] == 5
    assert budget["would_exhaust"] is True
    assert budget["exhausted"] is True
    assert diagnostics["failure_kind"] == "repair_budget_exhausted"
    assert diagnostics["override_required"] is True
    assert store.get_step(session.action.step_id).status == StepStatus.FAILED
    store.close()


def test_default_policy_fixable_failure_enters_needs_work_and_budget(tmp_path, monkeypatch):
    """fixable-only 失败不再「只登记」：finish 路径把它交给 P2b 预算计数。"""
    monkeypatch.setattr(QualityGate, "check_consistency_evidence",
                        lambda self: {"ok": False, "reason": "一致性报告未通过"})
    store, runner, workflow = _setup(tmp_path, required_checks=["consistency"])
    # P2b-2：fixable 降级必须有显式接收者。本用例验证「有接收者」路径（预算计数），
    # 以交付报告的人工签署 open_item 声明接收者（不再依赖 finish 路径的隐式接收）。
    (tmp_path / "ws" / "DELIVERY_REPORT.json").write_text(json.dumps({
        "open_items": [{"check": "quality:consistency", "signed": True,
                        "signed_by": "fixture-reviewer"}]}), encoding="utf-8")
    session = _session(runner, workflow.id, content="substantive output " * 20)
    result = session.finish()
    assert result["status"] == "needs_work", result["message"]
    diagnostics = result["diagnostics"]
    assert "quality:consistency" in diagnostics["fixable"]
    assert "quality:consistency" in diagnostics["fixable_open"]
    assert diagnostics["repair_budget"]["total"] == 1
    assert diagnostics["repair_budget"]["enforced"] is True
    assert "quality:consistency" in result["message"]
    issue = next(item for item in diagnostics["repair_issues"]
                 if item["check"] == "quality:consistency")
    assert issue["reason"] == "一致性报告未通过"
    store.close()
