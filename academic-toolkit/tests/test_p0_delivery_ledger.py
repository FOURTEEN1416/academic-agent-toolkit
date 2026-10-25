"""P0 投递账本行为锁定：零判定变更埋点 + 旧库迁移 + 只读审计。

覆盖台账批次一 P0-1..P0-6 的行为级验收：
- 三通道投递记录（next/context/finish_next）与「第几次投递」递增；
- read_ordinal / first_read_in_attempt（同一 attempt 3 次读取 1/2/3，retry 后重计）；
- context() 连续 3 次仍全量重读（skill 类操作 2/4/6 条），返回给模型的视图逐字段不变，
  账本写入失败不改变 context() 输出（零判定变更）；
- finish 推进后自动注入走 finish_next；needs_work 连续 4 次 → rounds 1..4、
  fingerprint/codes 稳定、状态仍 RUNNING（不改判定）；
- 7 列旧 schema 库打开后仅新增两表（+ 其约束自带的 autoindex），旧行不变；
  只读打开不迁移；
- 审计工具以 mode=ro 打开（mtime 前后不变），fixture 上 retry_then_context 归因正确。
"""
import ast
import json
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import delivery_ledger, workflow_cli
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import StepStatus, WorkflowStore
from execution.presentation import user_view
from execution.session import ExecutionSession
from tools.context_delivery_audit import audit


# 改造前 context() 的顶层结构（session.py 返回字典键集合），账本不得新增键。
CONTEXT_KEYS = {
    "session", "task", "review_scope", "parameters", "outputs",
    "quality_requirements", "contract_tier", "delivery_candidate_id",
    "documents", "resources", "contest_profile", "in_step_resume",
    "execution_policy", "instructions",
}


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


def test_delivery_ledger_records_channels_and_read_ordinal(tmp_path):
    # ---- P0-1 模块级：三通道各记 1 条，channel 各异，「第几次投递」递增 ----
    store = WorkflowStore(tmp_path / "ledger.sqlite")
    workflow = store.create_workflow("demo", {"workspace": str(tmp_path / "ws")})
    workflow_step = store.add_steps(workflow.id, [{"name": "demo"}])[0]
    for channel in ("next", "context", "finish_next"):
        delivery_ledger.record_delivery(
            store, workflow.id, workflow_step.id, "attempt-a", channel,
            "demo", "a" * 64, 120, "full", "operation-1")
    rows = store._connection.execute(
        "SELECT channel, delivery_ordinal, bytes FROM context_deliveries "
        "ORDER BY delivery_ordinal").fetchall()
    assert [row["channel"] for row in rows] == ["next", "context", "finish_next"]
    assert [row["delivery_ordinal"] for row in rows] == [1, 2, 3]
    assert all(row["bytes"] == 120 for row in rows)
    with pytest.raises(ValueError, match="unknown delivery channel"):
        delivery_ledger.record_delivery(store, workflow.id, workflow_step.id, "attempt-a",
                                        "bogus", "demo", "", 0, "full", "operation-x")
    store.close()
    # 模块不 import workflow_runner（无判定耦合）：AST 核对导入面 + 独立进程导入核对。
    tree = ast.parse(Path(delivery_ledger.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not any("workflow_runner" in name for name in imported), imported
    probe = subprocess.run(
        [sys.executable, "-c",
         "import engine.delivery_ledger, sys; "
         "print('engine.workflow_runner' in sys.modules)"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert probe.returncode == 0 and probe.stdout.strip() == "False", probe.stderr

    # ---- P0-3：同一 attempt 连续 3 次读取同一技能 → 1/2/3，内容逐字段不变 ----
    store2, runner = _runner(tmp_path / "ord", [{
        "skill_name": "demo", "output_files": ["result.txt"],
        "primary_output": "result.txt", "has_checkpoint": False,
        "metadata": {"skill_binding": {"main_required": True}},
    }], ["demo"])
    workflow2 = runner.start("demo", tmp_path / "ord" / "work", {})
    session = ExecutionSession(runner, workflow2.id)
    reads = [session.resources.read_resource("demo") for _ in range(3)]
    assert [item["read_ordinal"] for item in reads] == [1, 2, 3]
    assert [item["first_read_in_attempt"] for item in reads] == [True, False, False]
    assert reads[0]["content"] == reads[1]["content"] == reads[2]["content"]
    assert len({item["sha256"] for item in reads}) == 1
    assert len({item["bytes"] for item in reads}) == 1
    operations = [row for row in store2.execution_operations(
        session.action.step_id, session.action.attempt_id) if row["kind"] == "resource"]
    assert len(operations) == 3  # 第 3 次仍产生新操作：未偷偷去重
    assert [row["payload"]["read_ordinal"] for row in operations] == [1, 2, 3]
    # attempt 切换（retry）后从 1 重计
    store2.transition_step(session.action.step_id, StepStatus.FAILED)
    store2.transition_step(session.action.step_id, StepStatus.RUNNING)
    retried = ExecutionSession(runner, workflow2.id)
    assert retried.action.attempt_id != session.action.attempt_id
    assert retried.resources.read_resource("demo")["read_ordinal"] == 1
    store2.close()


def test_context_deliveries_increment_and_model_view_unchanged(tmp_path, monkeypatch):
    store, runner = _runner(tmp_path, [{
        "skill_name": "demo", "output_files": ["result.txt"],
        "primary_output": "result.txt", "has_checkpoint": False,
        "metadata": {"skill_binding": {"main_required": True, "mandatory": ["extra"]}},
    }], ["demo", "extra"])
    workflow = runner.start("demo", tmp_path / "work", {})
    session = ExecutionSession(runner, workflow.id)

    views, operation_counts = [], []
    for _ in range(3):
        result = session.context()
        views.append(user_view(result))
        operation_counts.append(len([row for row in store.execution_operations(
            session.action.step_id, session.action.attempt_id)
            if row["kind"] == "resource"]))
    # 零判定变更：每次 context() 仍全量重读主技能 + 1 mandatory（2/4/6 条操作）。
    assert operation_counts == [2, 4, 6]
    rows = store._connection.execute(
        "SELECT name, channel, delivery_ordinal FROM context_deliveries "
        "WHERE workflow_id=? AND step_id=? AND attempt_id=? ORDER BY rowid",
        (workflow.id, session.action.step_id, session.action.attempt_id)).fetchall()
    assert len(rows) == 6  # 3 次 context × (主技能 + 1 mandatory)
    assert {row["channel"] for row in rows} == {"context"}
    ordinals = {}
    for row in rows:
        ordinals.setdefault(row["name"], []).append(row["delivery_ordinal"])
    assert ordinals == {"demo": [1, 2, 3], "extra": [1, 2, 3]}

    # 返回给模型的上下文内容不变：视图只剩 name+content 且正文完整、三次一致。
    assert views[0]["documents"] == [
        {"name": "demo", "content": "Real task instructions for demo."},
        {"name": "extra", "content": "Real task instructions for extra."},
    ]
    assert views[0] == views[1] == views[2]
    assert set(views[0]) == CONTEXT_KEYS

    # 账本故障不改判定、不击穿主链路：埋点抛错时 context() 仍返回完整正文。
    monkeypatch.setattr(delivery_ledger, "record_delivery",
                        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ledger down")))
    fallback = session.context()
    assert [doc["name"] for doc in fallback["documents"]] == ["demo", "extra"]
    assert fallback["documents"][0]["content"] == "Real task instructions for demo."
    assert set(fallback) == CONTEXT_KEYS
    monkeypatch.undo()
    assert store._connection.execute(
        "SELECT COUNT(*) FROM context_deliveries").fetchone()[0] == 6  # 故障那次未记
    store.close()


def test_next_and_finish_next_channels(tmp_path, monkeypatch, capsys):
    # ---- channel=next：workflow_cli next 注入（CLI 固定读 ROOT/skills，用真实技能） ----
    store, runner = _runner(tmp_path / "cli", [{
        "skill_name": "comp-problem-analysis", "output_files": ["REPORT.md"],
        "primary_output": "REPORT.md", "has_checkpoint": False,
    }], ["comp-problem-analysis"])
    workflow = runner.start("demo", tmp_path / "cli" / "ws", {})
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", tmp_path / "index.json")
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "next", "--wf", workflow.id,
                                      "--db", str(store.db_path)])
    assert workflow_cli.main() == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "advanced"
    assert printed["execution"]["documents"][0]["name"] == "comp-problem-analysis"
    next_rows = store._connection.execute(
        "SELECT channel, name, bytes, delivery_ordinal FROM context_deliveries").fetchall()
    assert [(row["channel"], row["name"]) for row in next_rows] == [
        ("next", "comp-problem-analysis")]
    assert next_rows[0]["bytes"] > 0 and next_rows[0]["delivery_ordinal"] == 1
    store.close()

    # ---- channel=finish_next：finish 推进后自动注入下一步 ----
    store2, runner2 = _runner(tmp_path / "fin", [
        {"skill_name": "demo", "output_files": ["result.txt"],
         "primary_output": "result.txt", "has_checkpoint": False,
         "metadata": {"skill_binding": {"main_required": True}}},
        {"skill_name": "extra", "output_files": ["result2.txt"],
         "primary_output": "result2.txt", "has_checkpoint": False,
         "metadata": {"skill_binding": {"main_required": True}}},
    ], ["demo", "extra"])
    workflow2 = runner2.start("demo", tmp_path / "fin" / "ws", {})
    session = ExecutionSession(runner2, workflow2.id)
    session.context()
    session.files.write("result.txt", "real result")
    payload = session.finish()
    assert payload["status"] == "advanced"
    assert payload["next"]["documents"][0]["name"] == "extra"
    assert payload["next"]["documents"][0]["content"]
    finish_rows = store2._connection.execute(
        "SELECT channel, name, sha256 FROM context_deliveries WHERE channel='finish_next'").fetchall()
    assert [(row["channel"], row["name"]) for row in finish_rows] == [("finish_next", "extra")]
    assert len(finish_rows[0]["sha256"]) == 64
    # finish 返回 payload 未新增账本字段（零判定变更）。
    assert "delivery_ledger" not in payload and "context_deliveries" not in payload
    store2.close()


def test_validation_rounds_needs_work_and_concurrency(tmp_path):
    store, runner = _runner(tmp_path / "rounds", [{
        "skill_name": "demo", "output_files": ["result.txt"],
        "primary_output": "result.txt", "has_checkpoint": False,
        "metadata": {"skill_binding": {"main_required": True},
                     "output_specs": {"result.txt": {"min_bytes": 100}}},
    }], ["demo"])
    workflow = runner.start("demo", tmp_path / "rounds" / "ws", {})
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.write("result.txt", "too short")
    statuses = []
    for _ in range(4):
        result = session.finish()
        statuses.append(result["status"])
        # 响应与改造前同形：RunResult 字段集合未新增账本字段。
        assert set(result) == {"workflow_id", "status", "step_id", "message",
                               "action", "checkpoint_id", "diagnostics", "replayed"}
    assert statuses == ["needs_work"] * 4
    step = store.get_step(session.action.step_id)
    assert step.status == StepStatus.RUNNING  # 只计数：不推进 attempt / 不改状态
    assert step.attempt_id == session.action.attempt_id
    rows = store._connection.execute(
        "SELECT attempt_id, round, fingerprint, codes_json FROM step_validation_rounds "
        "WHERE workflow_id=? AND step_id=? ORDER BY round", (workflow.id, step.id)).fetchall()
    assert [row["round"] for row in rows] == [1, 2, 3, 4]
    assert len({row["fingerprint"] for row in rows}) == 1
    assert len({row["codes_json"] for row in rows}) == 1
    assert {row["attempt_id"] for row in rows} == {step.attempt_id}
    assert "output_spec:result.txt" in json.loads(rows[0]["codes_json"])
    store.close()

    # 并发分配：两个连接同时写 → BEGIN IMMEDIATE 串行化，round 无重号无丢失。
    database = tmp_path / "rounds" / "workflow.sqlite"
    parallel_stores = [WorkflowStore(database), WorkflowStore(database)]
    barrier = threading.Barrier(4)
    errors = []

    def worker(index):
        try:
            barrier.wait(timeout=10)
            delivery_ledger.record_validation_round(
                parallel_stores[index % 2], workflow.id, step.id, "attempt-concurrent",
                {"checks": {}})
        except Exception as exc:  # 失败由下面的断言暴露
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    rounds = [row[0] for row in parallel_stores[0]._connection.execute(
        "SELECT round FROM step_validation_rounds WHERE workflow_id=? AND step_id=? "
        "ORDER BY round", (workflow.id, step.id)).fetchall()]
    assert rounds == [1, 2, 3, 4, 5, 6, 7, 8]
    for item in parallel_stores:
        item.close()


def _build_legacy_database(path: Path) -> None:
    """构造 P0 之前的库形态：全量 schema 退回（workflow_steps 仅 7 列、无两新表）。"""
    WorkflowStore(path).close()
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        for table in ("candidate_events", "delivery_candidates", "execution_operations",
                      "events", "artifacts", "checkpoints", "workflow_steps", "workflows"):
            connection.execute(f'DELETE FROM "{table}"')
        connection.execute("DROP TABLE context_deliveries")
        connection.execute("DROP TABLE step_validation_rounds")
        connection.execute("DROP TABLE workflow_steps")
        connection.execute(
            "CREATE TABLE workflow_steps ("
            "id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(id), "
            "name TEXT NOT NULL, position INTEGER NOT NULL, status TEXT NOT NULL, "
            "metadata TEXT NOT NULL, updated_at TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO workflows VALUES ('wf-legacy', 'legacy-template', 'active', '{}', 't0', 't0')")
        connection.execute(
            "INSERT INTO workflow_steps VALUES ('step-a', 'wf-legacy', 'demo', 0, 'pending', '{}', 't0')")
        connection.execute(
            "INSERT INTO workflow_steps VALUES ('step-b', 'wf-legacy', 'demo', 1, 'pending', '{}', 't0')")
        connection.commit()
    finally:
        connection.close()


def _schema_snapshot(path: Path) -> dict:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        objects = {row["name"]: row["type"] for row in connection.execute(
            "SELECT name, type FROM sqlite_master")}
        columns = [row[1] for row in connection.execute("PRAGMA table_info(workflow_steps)")]
        counts = {name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                  for name, kind in objects.items() if kind == "table"}
        return {"objects": objects, "columns": columns, "counts": counts}
    finally:
        connection.close()


def test_old_schema_migration_and_readonly_audit_tool(tmp_path):
    # ---- P0-2 旧库打开：除既有迁移（revision/attempt_id）外只新增两表，旧行不变 ----
    legacy_db = tmp_path / "legacy" / "workflow.sqlite"
    legacy_db.parent.mkdir(parents=True)
    _build_legacy_database(legacy_db)
    before = _schema_snapshot(legacy_db)
    assert before["columns"] == ["id", "workflow_id", "name", "position", "status",
                                 "metadata", "updated_at"]
    with WorkflowStore(legacy_db):
        pass
    after = _schema_snapshot(legacy_db)
    assert after["columns"] == before["columns"] + ["revision", "attempt_id"]
    new_objects = set(after["objects"]) - set(before["objects"])
    assert {name for name in new_objects if after["objects"][name] == "table"} == {
        "context_deliveries", "step_validation_rounds"}
    assert all(after["objects"][name] == "index" and name.startswith("sqlite_autoindex_")
               and any(table in name for table in ("context_deliveries",
                                                   "step_validation_rounds"))
               for name in new_objects if after["objects"][name] != "table")
    assert {name: after["counts"][name] for name in before["counts"]} == before["counts"]
    assert after["counts"]["workflows"] == 1 and after["counts"]["workflow_steps"] == 2
    assert after["counts"]["context_deliveries"] == 0
    assert after["counts"]["step_validation_rounds"] == 0

    # 只读打开不迁移（preflight 路径），schema 原样。
    legacy_ro = tmp_path / "legacy_ro" / "workflow.sqlite"
    legacy_ro.parent.mkdir(parents=True)
    _build_legacy_database(legacy_ro)
    ro_before = _schema_snapshot(legacy_ro)
    with WorkflowStore(legacy_ro, read_only=True):
        pass
    assert _schema_snapshot(legacy_ro)["objects"] == ro_before["objects"]

    # ---- P0-6 只读审计：step_retry + 该 attempt 首 2 条技能读取 → retry_then_context=2 ----
    store, runner = _runner(tmp_path / "audit", [{
        "skill_name": "demo", "output_files": ["result.txt"],
        "primary_output": "result.txt", "has_checkpoint": False,
    }], ["demo"])
    workflow = runner.start("demo", tmp_path / "audit" / "ws", {})
    step_id = store._connection.execute(
        "SELECT id FROM workflow_steps WHERE workflow_id=?", (workflow.id,)).fetchone()[0]
    # events.checkpoint_id 非空且有外键：step_retry 事件必须挂在真实 checkpoint 上。
    store.create_checkpoint(workflow.id, step_id, {"status": "retry"},
                            event={"type": "step_retry", "step_id": step_id, "by": "fixture"})
    session = ExecutionSession(runner, workflow.id)
    session.resources.read_resource("demo")
    session.resources.read_resource("demo")
    store.close()

    database = tmp_path / "audit" / "workflow.sqlite"
    mtime_before = database.stat().st_mtime_ns
    report = audit(database)
    assert database.stat().st_mtime_ns == mtime_before  # mode=ro：运行前后 DB 未变
    assert report["skill_reads"] == 2
    assert report["unique_skills"] == 1
    assert report["max_per_attempt"] == 2
    assert report["channel_distribution"] == {"retry_then_context": 2}
    assert report["attempts"][0]["channels"] == {"retry_then_context": 2}
    assert report["attempts"][0]["attribution"] == "retry_then_context"
    assert report["attempts"][0]["skills"] == ["demo"]
    # 同一 (attempt, skill, sha) 两次读取去重后只剩 1 条、字节按单次计。
    assert report["dedup_projection"] == {"reads": 1,
                                          "bytes": report["bytes"] // report["skill_reads"]}
    # 旧库（无 context_deliveries 表）也能只读审计：不抛异常、输出 proxy 投影。
    legacy_report = audit(legacy_db)
    assert legacy_report["skill_reads"] == 0
    assert legacy_report["channel_distribution"] == {}
