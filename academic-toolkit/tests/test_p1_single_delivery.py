"""P1 技能正文单次投递（裁决 6.1 门控前提，出厂关闭）的行为锁定。

覆盖：
- 出厂配置 = 关闭：同一 attempt 重复 context() 仍全量投递、账本全是 delivered=full，
  返回给模型的视图与 P0 现状一致（默认路径不变）；
- 开关打开：首次投递正文，第二次只投续接说明（声明首条消息的正文仍有效、本次不重发），
  不再重复读取技能文件；账本按 delivered=full / continuation 两通道分别计数；
- 续接只限同一 attempt：retry 换 attempt 后重新全量投递；
- finish 推进到下一步骤时（新步骤/新 attempt）首投仍是全量正文；
- 配置损坏/缺失一律回落出厂关闭（不静默打开未验证行为）。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import _paths, delivery_ledger
from engine.telemetry import context_delivery
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import StepStatus, WorkflowStore
from execution.presentation import user_view
from execution.session import ExecutionSession


def _write_skills(root: Path, names) -> Path:
    skills = root / "skills"
    for name in names:
        path = skills / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"Real task instructions for {name}.", encoding="utf-8")
    return skills


def _runner(tmp_path: Path, steps, skill_names):
    skills = _write_skills(tmp_path, skill_names)
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, {"demo": {"sub_steps": steps}}, skills, audit_root=tmp_path)
    return store, runner


def _demo_step(name: str, output: str) -> dict:
    return {"skill_name": name, "output_files": [output], "primary_output": output,
            "has_checkpoint": False,
            "metadata": {"skill_binding": {"main_required": True, "mandatory": ["extra"]}}}


def _enable(monkeypatch, tmp_path: Path, single_delivery: bool = True) -> Path:
    policy = tmp_path / "context_delivery.json"
    policy.write_text(json.dumps({"version": 1, "single_delivery": single_delivery}),
                      encoding="utf-8")
    monkeypatch.setattr(context_delivery, "POLICY_PATH", policy)
    return policy


def _ledger_rows(store, workflow_id, step_id, attempt_id):
    return store._connection.execute(
        "SELECT name, channel, delivered, bytes, sha256, delivery_ordinal "
        "FROM context_deliveries WHERE workflow_id=? AND step_id=? AND attempt_id=? "
        "ORDER BY rowid", (workflow_id, step_id, attempt_id)).fetchall()


def _resource_reads(store, step_id, attempt_id):
    return [row for row in store.execution_operations(step_id, attempt_id)
            if row["kind"] == "resource"]


def test_shipped_default_is_disabled_and_context_redelivers_full(tmp_path, monkeypatch):
    # 出厂配置：文件在 checkers/ 子目录（不进 modex-core 根下 glob 哈希面），值为关闭。
    assert context_delivery.POLICY_PATH.parent.name == "checkers"
    assert context_delivery.POLICY_PATH == _paths.MODEX_CORE / "checkers" / "context_delivery.json"
    shipped = context_delivery.load_policy()
    assert shipped["status"] == "ok"
    assert shipped["single_delivery"] is False
    assert context_delivery.single_delivery_enabled() is False

    store, runner = _runner(tmp_path, [_demo_step("demo", "result.txt")], ["demo", "extra"])
    workflow = runner.start("demo", tmp_path / "ws", {})
    session = ExecutionSession(runner, workflow.id)
    first, second = session.context(), session.context()

    # 默认路径不变：两次都拿到完整正文，视图逐字段一致。
    assert [doc["content"] for doc in first["documents"]] == [
        "Real task instructions for demo.", "Real task instructions for extra."]
    assert [doc["read_ordinal"] for doc in first["documents"]] == [1, 1]
    assert [doc["read_ordinal"] for doc in second["documents"]] == [2, 2]
    assert [doc["sha256"] for doc in second["documents"]] == \
        [doc["sha256"] for doc in first["documents"]]
    assert user_view(first)["documents"] == user_view(second)["documents"]
    assert not any("content_omitted" in doc for doc in second["documents"])
    assert context_delivery.CONTINUATION_PREFIX not in second["documents"][0]["content"]

    # 账本：两次 context × 2 技能 = 4 行，全部 full，第几次投递递增。
    rows = _ledger_rows(store, workflow.id, session.action.step_id, session.action.attempt_id)
    assert len(rows) == 4
    assert {row["delivered"] for row in rows} == {"full"}
    assert {row["channel"] for row in rows} == {"context"}
    ordinals = {}
    for row in rows:
        ordinals.setdefault(row["name"], []).append(row["delivery_ordinal"])
    assert ordinals == {"demo": [1, 2], "extra": [1, 2]}
    assert len(_resource_reads(store, session.action.step_id, session.action.attempt_id)) == 4
    store.close()


def test_enabled_second_context_sends_continuation_notice(tmp_path, monkeypatch):
    _enable(monkeypatch, tmp_path)
    store, runner = _runner(tmp_path, [_demo_step("demo", "result.txt")], ["demo", "extra"])
    workflow = runner.start("demo", tmp_path / "ws", {})
    session = ExecutionSession(runner, workflow.id)

    first = session.context()
    assert [doc["content"] for doc in first["documents"]] == [
        "Real task instructions for demo.", "Real task instructions for extra."]
    assert len(_resource_reads(store, session.action.step_id, session.action.attempt_id)) == 2

    second = session.context()
    for document in second["documents"]:
        content = document["content"]
        assert content.startswith(context_delivery.CONTINUATION_PREFIX)
        assert f"`{document['name']}`" in content
        assert "仍然有效" in content and "不再重复投递" in content
        assert "Real task instructions for" not in content
        assert document["content_omitted"] is True
        assert document["observation"] == "content_omitted_continuation"
        assert document["read_ordinal"] is None
    # 正文身份由首次 full 投递保留（sha/bytes 不变），不是续接说明自己的摘要。
    assert [doc["sha256"] for doc in second["documents"]] == \
        [doc["sha256"] for doc in first["documents"]]
    assert [doc["bytes"] for doc in second["documents"]] == [doc["bytes"] for doc in first["documents"]]
    # 续接不重读技能：resource 操作仍只有首投的 2 条。
    assert len(_resource_reads(store, session.action.step_id, session.action.attempt_id)) == 2
    # 模型视图同样不含正文，只含续接说明。
    viewed = user_view(second)["documents"]
    assert all("Real task instructions for" not in item["content"] for item in viewed)
    assert all(item["content"].startswith(context_delivery.CONTINUATION_PREFIX) for item in viewed)

    # 账本两通道分别可数：full=2（首投）+ continuation=2（续接）。
    rows = _ledger_rows(store, workflow.id, session.action.step_id, session.action.attempt_id)
    assert len(rows) == 4
    by_delivered = {}
    for row in rows:
        by_delivered.setdefault(row["delivered"], []).append(row)
    assert {key: len(value) for key, value in by_delivered.items()} == {"full": 2, "continuation": 2}
    # continuation 行：bytes=说明文本字节，sha256 保留正文身份，序号继续递增。
    skill_bytes = {doc["name"]: doc["bytes"] for doc in first["documents"]}
    for row in by_delivered["continuation"]:
        expected = context_delivery.continuation_notice(
            row["name"], row["sha256"], skill_bytes[row["name"]])
        assert row["bytes"] == len(expected.encode("utf-8"))
        assert len(row["sha256"]) == 64
    assert by_delivered["continuation"][0]["sha256"] == by_delivered["full"][0]["sha256"]
    ordinals = {}
    for row in rows:
        ordinals.setdefault(row["name"], []).append(row["delivery_ordinal"])
    assert ordinals == {"demo": [1, 2], "extra": [1, 2]}
    store.close()


def test_single_delivery_is_scoped_to_attempt(tmp_path, monkeypatch):
    _enable(monkeypatch, tmp_path)
    store, runner = _runner(tmp_path, [_demo_step("demo", "result.txt")], ["demo", "extra"])
    workflow = runner.start("demo", tmp_path / "ws", {})
    session = ExecutionSession(runner, workflow.id)
    first = session.context()
    session.context()
    assert session.context()["documents"][0]["content_omitted"] is True

    # retry 换 attempt：旧 attempt 的投递不跨 attempt 复用，首投重新给全文。
    store.transition_step(session.action.step_id, StepStatus.FAILED)
    store.transition_step(session.action.step_id, StepStatus.RUNNING)
    retried = ExecutionSession(runner, workflow.id)
    assert retried.action.attempt_id != session.action.attempt_id
    redelivered = retried.context()
    assert [doc["content"] for doc in redelivered["documents"]] == [
        "Real task instructions for demo.", "Real task instructions for extra."]
    assert not any(doc.get("content_omitted") for doc in redelivered["documents"])
    assert [doc["sha256"] for doc in redelivered["documents"]] == \
        [doc["sha256"] for doc in first["documents"]]
    rows = _ledger_rows(store, workflow.id, retried.action.step_id, retried.action.attempt_id)
    assert {row["delivered"] for row in rows} == {"full"}
    assert [row["delivery_ordinal"] for row in rows] == [1, 1]
    store.close()


def test_finish_next_step_still_gets_full_body(tmp_path, monkeypatch):
    _enable(monkeypatch, tmp_path)
    store, runner = _runner(tmp_path, [
        {"skill_name": "demo", "output_files": ["result.txt"], "primary_output": "result.txt",
         "has_checkpoint": False, "metadata": {"skill_binding": {"main_required": True}}},
        {"skill_name": "extra", "output_files": ["result2.txt"], "primary_output": "result2.txt",
         "has_checkpoint": False, "metadata": {"skill_binding": {"main_required": True}}},
    ], ["demo", "extra"])
    workflow = runner.start("demo", tmp_path / "ws", {})
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.write("result.txt", "real result")
    payload = session.finish()
    assert payload["status"] == "advanced"
    # 下一步骤是新 attempt：finish_next 首投仍是全量正文，不是续接说明。
    assert payload["next"]["documents"][0]["name"] == "extra"
    assert payload["next"]["documents"][0]["content"] == "Real task instructions for extra."
    assert "content_omitted" not in payload["next"]["documents"][0]
    finish_rows = store._connection.execute(
        "SELECT channel, delivered FROM context_deliveries WHERE channel='finish_next'").fetchall()
    assert [(row["channel"], row["delivered"]) for row in finish_rows] == [("finish_next", "full")]
    store.close()


def test_invalid_or_missing_policy_falls_back_to_full_delivery(tmp_path, monkeypatch):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(context_delivery, "POLICY_PATH", broken)
    assert context_delivery.load_policy()["status"] == "invalid"
    assert context_delivery.single_delivery_enabled() is False

    monkeypatch.setattr(context_delivery, "POLICY_PATH", tmp_path / "absent.json")
    assert context_delivery.load_policy()["status"] == "missing"
    assert context_delivery.single_delivery_enabled() is False

    wrong_type = tmp_path / "wrong.json"
    wrong_type.write_text('{"version": 1, "single_delivery": "true"}', encoding="utf-8")
    monkeypatch.setattr(context_delivery, "POLICY_PATH", wrong_type)
    assert context_delivery.load_policy()["status"] == "invalid"
    assert context_delivery.single_delivery_enabled() is False

    # 关闭态下重复 context() 仍全量投递（配置问题不得把未验证行为静默打开）。
    store, runner = _runner(tmp_path, [_demo_step("demo", "result.txt")], ["demo", "extra"])
    workflow = runner.start("demo", tmp_path / "ws", {})
    session = ExecutionSession(runner, workflow.id)
    assert session.context()["documents"][0]["content"] == "Real task instructions for demo."
    assert session.context()["documents"][0]["content"] == "Real task instructions for demo."
    assert len(_resource_reads(store, session.action.step_id, session.action.attempt_id)) == 4
    store.close()
