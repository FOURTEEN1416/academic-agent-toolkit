"""A窗专项：真实文件/命令验证操作采集、产物来源链、缓存边界与恢复。

每个用例对应任务书点名的验证场景；不使用mock返回码，全部走真实子进程与文件字节。
"""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from execution.session import ExecutionSession


def make_session(tmp_path, *, metadata=None, skill_name="demo"):
    skills = tmp_path / f"suite/skills/{skill_name}"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("Real task instructions for the step.", encoding="utf-8")
    rules = tmp_path / "suite/engine/modex-core"
    rules.mkdir(parents=True)
    (rules / "comp_rules.json").write_text("{}", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    catalog = {skill_name: {"sub_steps": [{"skill_name": skill_name, "output_files": ["result.txt"],
        "primary_output": "result.txt",
        "metadata": {"skill_binding": {"main_required": True}, **(metadata or {})}}]}}
    runner = WorkflowRunner(store, catalog, tmp_path / "suite/skills", audit_root=tmp_path)
    wf = runner.start(skill_name, tmp_path / "work", {})
    session = ExecutionSession(runner, wf.id)
    session.context()
    return store, runner, wf, session


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_spec(session, script, inputs, outputs, *, node_id="solve", **extra):
    spec = {"id": node_id, "argv": [sys.executable, "-c", script],
            "inputs": inputs, "outputs": outputs, "pure": True, "complete_inputs": True}
    spec.update(extra)
    return session.commands.execute(spec)


def test_new_production_reuse_and_retained_output_are_distinguished(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("input.txt", "7")
    producer = run_spec(session,
        "from pathlib import Path;Path('mid.txt').write_text(Path('input.txt').read_text())",
        ["input.txt"], ["mid.txt"], node_id="up", env_keys=["A_WINDOW_TEST"])
    assert producer["status"] == "succeeded"
    assert "retained_from" not in producer  # 新生产：本命令真实写出了产物
    # 同键无变化再次执行：有效复用，不重跑进程
    again = session.commands.execute({"id": "up", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('mid.txt').write_text(Path('input.txt').read_text())"],
        "inputs": ["input.txt"], "outputs": ["mid.txt"], "pure": True, "complete_inputs": True,
        "env_keys": ["A_WINDOW_TEST"]})
    assert again["status"] == "reused" and again["reused_from"] == producer["operation_id"]
    # 真写 result.txt 但未触碰 mid.txt：mid 保留既有产物来源，不得被本命令冒领
    mixed = run_spec(session,
        "from pathlib import Path;Path('result.txt').write_text('summary over mid')",
        [], ["result.txt", "mid.txt"], node_id="combine")
    assert mixed["status"] == "succeeded"
    assert mixed["retained_from"] == {"mid.txt": producer["operation_id"]}
    rows = store.current_operations(session.action.step_id, session.action.attempt_id)
    assert {r["status"] for r in rows} == {"succeeded", "reused"}
    store.close()


def test_prestaged_output_and_empty_command_cannot_be_claimed(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    (session.workspace / "result.txt").write_text("prestaged without any operation")
    empty = {"id": "empty", "argv": [sys.executable, "-c", "print('does nothing')"],
             "inputs": [], "outputs": ["result.txt"]}
    with pytest.raises(ValueError, match="未产生声明输出"):
        session.commands.execute(empty)
    # 预置文件 + 无操作命令不得生成成功证据；工作区字节保持原样
    assert (session.workspace / "result.txt").read_text() == "prestaged without any operation"
    store.close()


def test_window_attribution_ignores_stat_recovery(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    (session.workspace / "result.txt").write_text("A" * 64)
    # 真实子进程写入后恢复 mtime：归属依据是执行窗口+字节，stat 不作数 → 新生产
    rewritten = run_spec(session, """
import os
from pathlib import Path
p = Path('result.txt')
st = p.stat()
p.write_text('B' * st.st_size)
os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
""", [], ["result.txt"], node_id="rewrite")
    assert rewritten["status"] == "succeeded"
    assert rewritten["outputs_snapshot"]["result.txt"] == sha("B" * 64)
    assert "retained_from" not in rewritten
    # 内容未变+仅动 mtime+返回0：原地修订语义下保留原来源，不算新生产
    touched = run_spec(session, """
import os
from pathlib import Path
p = Path('result.txt')
st = p.stat()
os.utime(p, ns=(st.st_atime_ns + 1_000_000, st.st_mtime_ns + 1_000_000))
""", ["result.txt"], ["result.txt"], mutates=["result.txt"], node_id="touch")
    assert touched["status"] == "succeeded"
    assert touched["retained_from"] == {"result.txt": rewritten["operation_id"]}
    store.close()


def test_network_commands_are_never_cacheable(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("seed.txt", "local input")
    spec = {"id": "fetch", "argv": [sys.executable, "-c",
             "from pathlib import Path;Path('result.txt').write_text('fetched')",
             "https://example.com/data"], "inputs": ["seed.txt"], "outputs": ["result.txt"],
             "pure": True, "complete_inputs": True}
    first = session.commands.execute(spec)
    assert first["status"] == "succeeded" and first["cacheable"] is False
    second = session.commands.execute(spec)
    assert second["status"] == "succeeded", "网络命令每次真实重跑，不得复用"
    store.close()


def test_review_step_banned_from_cache_runs_inherited_environment(tmp_path):
    """真实反例：满足纯计算与env_keys条件，但步骤性质禁止缓存。

    禁缓存的命令必须继承完整环境真实运行：子进程能读到继承环境中的
    无敏感测试变量，记录为inherited，重复执行不得reused。
    """
    store, runner, wf, session = make_session(tmp_path, skill_name="comp-review-helper")
    session.files.write("input.txt", "seed")
    spec = {"id": "review-prep", "argv": [sys.executable, "-c",
        "import os;from pathlib import Path;"
        "value = 'V=' + os.environ.get('A_WINDOW_INHERITED', 'absent');"
        "Path('result.txt').write_text(value);print(value)"],
        "inputs": ["input.txt"], "outputs": ["result.txt"], "pure": True,
        "complete_inputs": True, "env_keys": ["A_WINDOW_UNRELATED"]}
    os.environ["A_WINDOW_INHERITED"] = "plain-value"
    try:
        first = session.commands.execute(dict(spec))
        assert first["status"] == "succeeded" and first["cacheable"] is False
        assert first["environment_mode"] == "inherited; not reusable"
        assert "V=plain-value" in first["stdout"], \
            "禁缓存命令继承环境：子进程必须能读到未声明的无敏感测试变量"
        second = session.commands.execute(dict(spec))
        assert second["status"] == "succeeded" and second["cacheable"] is False
        assert "reused_from" not in second, "步骤禁缓存：重复执行必须真实重跑"
        rows = store.execution_operations(session.action.step_id, session.action.attempt_id)
        assert [r["status"] for r in rows if r["kind"] == "command"] == ["succeeded", "succeeded"]
    finally:
        os.environ.pop("A_WINDOW_INHERITED", None)
    store.close()


def test_undeclared_env_vars_are_invisible_to_cacheable_runs(tmp_path):
    """真实反例：声明了部分键、命令实际读取未声明变量。

    受控环境下未声明变量对子进程不可见——变量外部变化不影响复用合法性，
    依赖未声明变量的命令真实失败而不是带着错误环境假复用历史成功。
    """
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("input.txt", "seed")
    reader = {"id": "reader", "argv": [sys.executable, "-c",
        "import os;from pathlib import Path;"
        "Path('out.txt').write_text('B=' + os.environ.get('B_UNDECLARED', 'absent'))"],
        "inputs": ["input.txt"], "outputs": ["out.txt"], "pure": True,
        "complete_inputs": True, "env_keys": ["A_DECLARED"]}
    os.environ["B_UNDECLARED"] = "v1"
    try:
        first = session.commands.execute(dict(reader))
        assert first["status"] == "succeeded"
        assert (session.workspace / "out.txt").read_text(encoding="utf-8") == "B=absent", \
            "受控环境必须剥离未声明变量，子进程读不到继承环境里的 B_UNDECLARED"
        os.environ["B_UNDECLARED"] = "v2"
        second = session.commands.execute(dict(reader))
        assert second["status"] == "reused", "实际执行环境与指纹同源（都不含B）：变化不影响复用"
        assert (session.workspace / "out.txt").read_text(encoding="utf-8") == "B=absent"
    finally:
        os.environ.pop("B_UNDECLARED", None)
    strict = {"id": "strict", "argv": [sys.executable, "-c",
        "import os,sys;sys.exit(0 if os.environ.get('B_UNDECLARED') == 'needed' else 3)"],
        "inputs": ["input.txt"], "outputs": ["out.txt"], "pure": True,
        "complete_inputs": True, "env_keys": ["A_DECLARED"]}
    assert session.commands.execute(strict)["status"] == "failed", \
        "依赖未声明变量的命令在受控环境下真实失败，不是假成功"
    os.environ["B_UNDECLARED"] = "needed"
    still_failed = session.commands.execute(strict)
    assert still_failed["status"] == "failed", "环境里有值但未声明：受控执行仍不可见，不假复用成功"
    declared = dict(strict, id="strict2", env_keys=["A_DECLARED", "B_UNDECLARED"])
    ok = session.commands.execute(declared)
    assert ok["status"] == "succeeded", "显式声明后程序受控传入，命令可用"
    os.environ.pop("B_UNDECLARED", None)
    store.close()


def test_cache_uses_controlled_environment_with_or_without_declarations(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("input.txt", "7")
    base = {"id": "up", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('mid.txt').write_text(Path('input.txt').read_text())"],
        "inputs": ["input.txt"], "outputs": ["mid.txt"], "pure": True, "complete_inputs": True}
    # 未声明 env_keys：同样运行于受控白名单环境（子进程可见环境=controlled_env
    # 且 digest 入键，指纹同源），环境真值完整 → 可复用；继承噪声不影响命中。
    os.environ["A_WINDOW_UNDECLARED_NOISE"] = uuid.uuid4().hex
    try:
        undeclared = session.commands.execute(dict(base))
        assert undeclared["status"] == "succeeded" and undeclared["cacheable"] is True
        again = session.commands.execute(dict(base))
    finally:
        os.environ.pop("A_WINDOW_UNDECLARED_NOISE", None)
    assert again["status"] == "reused"
    # 声明键未在环境中存在时与未声明版指纹同源 → 合法复用；设值后才构成新指纹
    declared = dict(base, id="up2", env_keys=["A_WINDOW_DECLARED"])
    assert session.commands.execute(dict(declared))["status"] == "reused"
    os.environ["A_WINDOW_DECLARED"] = "stable"
    assert session.commands.execute(dict(declared))["status"] == "succeeded"
    # 声明键稳定、无关噪声变化 → 有效复用
    os.environ["A_WINDOW_IRRELEVANT_NOISE"] = uuid.uuid4().hex
    try:
        reused = session.commands.execute(dict(declared))
    finally:
        os.environ.pop("A_WINDOW_IRRELEVANT_NOISE", None)
        os.environ.pop("A_WINDOW_DECLARED", None)
    assert reused["status"] == "reused"
    store.close()


def test_unrelated_rule_change_does_not_force_recompute(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("input.txt", "7")
    spec = {"id": "up", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('mid.txt').write_text(Path('input.txt').read_text())"],
        "inputs": ["input.txt"], "outputs": ["mid.txt"], "pure": True, "complete_inputs": True,
        "env_keys": ["A_WINDOW_TEST"]}
    assert session.commands.execute(spec)["status"] == "succeeded"
    rules = tmp_path / "suite/engine/modex-core/comp_rules.json"
    rules.write_text('{"changed_for_other_contest": true}', encoding="utf-8")
    reused = session.commands.execute(spec)
    assert reused["status"] == "reused", "无关赛种规则变化不得成为纯计算命令的重算理由"
    store.close()


def test_upstream_change_cannot_be_whitewashed_by_downstream_edit(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("input.txt", "7")
    up = {"id": "up", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('mid.txt').write_text(Path('input.txt').read_text())"],
        "inputs": ["input.txt"], "outputs": ["mid.txt"], "pure": True, "complete_inputs": True}
    session.commands.execute(up)
    session.files.read_file("mid.txt")
    session.files.write("result.txt", "conclusion drawn from mid version one")
    (session.workspace / "input.txt").write_text("9")
    with pytest.raises(ValueError, match="上游输入已变化"):
        session.files.edit("result.txt", "conclusion", "revised conclusion")
    # 正路：重算上游 -> 重新阅读 -> 重新写作，谱系按当前有效版本接续
    session.commands.execute(up)
    session.files.read_file("mid.txt")
    session.files.write("result.txt", "conclusion drawn from mid version two")
    assert (session.workspace / "result.txt").read_text().endswith("two")
    store.close()


def test_adopt_cannot_rewrite_transitive_dependencies(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("input.txt", "v1")
    up = {"id": "up", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('mid.txt').write_text(Path('input.txt').read_text())"],
        "inputs": ["input.txt"], "outputs": ["mid.txt"], "pure": True, "complete_inputs": True}
    session.commands.execute(up)
    session.files.read_file("mid.txt")
    session.files.write("report.txt", "findings based on mid v1")
    (session.workspace / "input.txt").write_text("v2")
    # 场景A：不重算中间结果，只重读原始输入 v2 后修订 → 阻断，且不产生改写记录
    session.files.read_file("input.txt")
    with pytest.raises(ValueError, match="上游输入已变化"):
        session.files.edit("report.txt", "findings", "revised findings")
    reports = [r["payload"]["outputs_snapshot"]["report.txt"] for r in
               store.current_operations(session.action.step_id, session.action.attempt_id)
               if r["kind"] == "write" and r["payload"]["path"] == "report.txt"]
    assert reports == [sha("findings based on mid v1")], "被阻断的修订不得留下改记谱系的写入行"
    # 场景B：连中间结果一起重读（仍是未重算的 v1）→ 同样阻断
    session.files.read_file("mid.txt")
    with pytest.raises(ValueError, match="上游输入已变化"):
        session.files.write("report.txt", "findings from mid v1 with new input v2")
    # 正路：重算上游 → 重新阅读 → 更新报告；新谱系按新链如实记录
    session.commands.execute(up)
    session.files.read_file("mid.txt")
    result = session.files.write("report.txt", "findings based on mid v2")
    assert result["inputs_snapshot"]["mid.txt"] == sha("v2")
    assert result["inputs_snapshot"]["input.txt"] == sha("v2")
    store.close()


def test_lineage_across_completed_steps(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("input.txt", "v1")
    up = {"id": "up", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('mid.txt').write_text(Path('input.txt').read_text())"],
        "inputs": ["input.txt"], "outputs": ["mid.txt"], "pure": True, "complete_inputs": True}
    session.commands.execute(up)
    store.transition_step(session.action.step_id, "completed")
    (step2,) = store.add_steps(wf.id, [{"name": "demo", "position": 2, "metadata": {
        "output_files": ["report.txt"], "skill_binding": {"main_required": True}}}])
    store.transition_step(step2.id, "running")
    session2 = ExecutionSession(runner, wf.id)
    session2.context()
    session2.files.read_file("mid.txt")
    session2.files.write("report.txt", "findings from step2")
    (session2.workspace / "input.txt").write_text("v2")
    # 已完成步骤里的上游生产者仍在来源链上：上游变化阻断新步骤的下游修订
    with pytest.raises(ValueError, match="上游输入已变化"):
        session2.files.edit("report.txt", "findings", "revised findings")
    # 正路跨步骤同样成立：本步骤重算 → 重读 → 更新
    session2.commands.execute(up)
    session2.files.read_file("mid.txt")
    session2.files.write("report.txt", "findings from step2 v2")
    assert (session2.workspace / "report.txt").read_text(encoding="utf-8").endswith("v2")
    store.close()


def test_mutates_chain_keeps_original_lineage_and_blocks_stale_upstream(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("input.txt", "7")
    session.commands.execute({"id": "up", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('mid.txt').write_text(Path('input.txt').read_text())"],
        "inputs": ["input.txt"], "outputs": ["mid.txt"], "pure": True, "complete_inputs": True})
    revise = {"id": "revise", "argv": [sys.executable, "-c",
        "from pathlib import Path;p=Path('mid.txt');p.write_text(p.read_text()+' revised')"],
        "inputs": ["mid.txt"], "outputs": ["mid.txt"], "mutates": ["mid.txt"],
        "pure": True, "complete_inputs": True}
    first = session.commands.execute(revise)
    assert first["status"] == "succeeded" and first["cacheable"] is False
    assert first["inputs_snapshot"] != first["outputs_snapshot"]  # before/after 都在
    assert first["lineage_inputs"]["input.txt"] == sha("7")  # 最初输入不因修订丢失
    (session.workspace / "input.txt").write_text("9")
    with pytest.raises(ValueError, match="上游输入已变化"):
        session.commands.execute(revise)
    store.close()


def test_attempt_isolation_and_running_operation_exclusive_window(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    spec = {"id": "work", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('result.txt').write_text('ok')"],
        "inputs": [], "outputs": ["result.txt"]}
    stuck = session.operations.begin("write", "write:stuck", {"path": "result.txt"})
    with pytest.raises(ValueError, match="already running"):
        session.commands.execute(spec)
    store.interrupt_operation(stuck, "operator confirmed the process has exited")
    assert session.commands.execute(spec)["status"] == "succeeded"
    step = store.get_step(session.action.step_id)
    old_attempt = step.attempt_id
    store.transition_step(step.id, "failed")
    store.transition_step(step.id, "running")
    assert store.get_step(step.id).attempt_id != old_attempt
    assert store.current_operations(step.id, store.get_step(step.id).attempt_id) == []
    assert store.execution_operations(step.id, old_attempt), "历史attempt行保留不删"
    store.close()


def test_timeout_records_failure_and_same_node_recovers(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    slow = {"id": "slow", "argv": [sys.executable, "-c",
        "import time; time.sleep(5); from pathlib import Path; Path('result.txt').write_text('late')"],
        "inputs": [], "outputs": ["result.txt"], "timeout": 1}
    with pytest.raises(subprocess.TimeoutExpired):
        session.commands.execute(slow)
    rows = store.execution_operations(session.action.step_id, session.action.attempt_id)
    timed_out = next(r for r in rows if r["kind"] == "command" and r["status"] == "failed")
    assert timed_out["payload"]["error"] == "TimeoutExpired"
    fast = {"id": "fast", "argv": [sys.executable, "-c",
        "from pathlib import Path;Path('result.txt').write_text('ok')"],
        "inputs": [], "outputs": ["result.txt"]}
    assert session.commands.execute(fast)["status"] == "succeeded"
    store.close()


def test_text_only_edit_and_check_invalidation(tmp_path):
    store, runner, wf, session = make_session(tmp_path)
    session.files.write("result.txt", "correct statement")
    check = {"id": "content-check", "mode": "check", "argv": [sys.executable, "-c",
        "from pathlib import Path;assert 'correct' in Path('result.txt').read_text()"],
        "inputs": ["result.txt"], "outputs": []}
    assert session.commands.execute(check)["cacheable"] is False
    session.files.edit("result.txt", "statement", "wording")
    assert (session.workspace / "result.txt").read_text() == "correct wording"
    assert session.finish()["status"] == "needs_work", "内容改变后旧核查结论必须失效"
    assert session.commands.execute(check)["status"] == "succeeded"
    assert session.finish()["status"] == "completed"
    store.close()


def test_atomic_publish_retries_transient_windows_lock(tmp_path, monkeypatch):
    from engine import step_manifest
    real_replace = os.replace
    calls = {"count": 0}

    def flaky(src, dst):
        calls["count"] += 1
        if calls["count"] == 1:
            raise PermissionError(13, "Access is denied (transient)")
        return real_replace(src, dst)

    staged = tmp_path / ".staged.tmp"
    staged.write_text("payload", encoding="utf-8")
    target = tmp_path / "published.txt"
    monkeypatch.setattr(step_manifest.os, "replace", flaky)
    step_manifest.durable_replace(staged, target)
    assert calls["count"] == 2 and target.read_text(encoding="utf-8") == "payload"

    store, runner, wf, session = make_session(tmp_path / "suite-run")
    session.files.write("result.txt", "durable content")
    assert (session.workspace / "result.txt").read_text(encoding="utf-8") == "durable content"
    store.close()
