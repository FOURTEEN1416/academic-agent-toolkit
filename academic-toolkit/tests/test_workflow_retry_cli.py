"""retry 带内恢复 / approve --by 批准人 / checkpoint_id 输出 回归测试。

覆盖（A2/A5 敌意审计修复清单）：
- P0-1 retry：complete 失败→next 阻断→retry→重新 complete 成功，事件库有 step_retry；
- P0-3 checkpoint_id：complete(waiting_checkpoint) 与 next(blocked) 输出直接携带 UUID；
- P0-4 approve --by：缺失/空 → 报错教学；带 --by → 批准事件写入 approved_by；
- 小修 6b：next 输出手册口径步号 step_number_manual（position+1）。
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import workflow_cli
from engine.opencode_bridge import StepResult
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


# ── 共享 fixture：两步小模板（第 1 步可失败/可完成，第 2 步验证继续推进） ────

def make_catalog(first_checkpoint=False):
    return {"demo": {"sub_steps": [
        {"skill_name": "comp-problem-analysis", "primary_output": "REPORT.md",
         "output_files": ["REPORT.md"], "has_checkpoint": first_checkpoint,
         "checkpoint_type": "approve" if first_checkpoint else None},
        {"skill_name": "comp-modeling", "primary_output": "MODEL.md",
         "output_files": ["MODEL.md"], "has_checkpoint": False},
    ]}}


def setup_runner(tmp_path, first_checkpoint=False):
    skills = tmp_path / "skills"
    for name in ("comp-problem-analysis", "comp-modeling"):
        skill = skills / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("skill", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, make_catalog(first_checkpoint), skills)
    workflow = runner.start("demo", tmp_path / "workspace", {})
    return store, runner, workflow.id


def complete_ok(runner, wf_id):
    action = runner.next_action(wf_id).action
    assert action is not None
    for output in action.output_files:
        path = action.workspace / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * 3000, encoding="utf-8")
    return runner.complete_step(wf_id, StepResult(
        ok=True, artifacts=list(action.output_files),
        metadata={"execution_evidence": {
            "schema_version": 1, "agent": "OpenCode Desktop",
            "step_id": action.step_id, "skill_name": action.skill_name,
            "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
            "commands": [{"command": "python code/gen_report.py", "returncode": 0, "cwd": "."}],
            "inputs": [], "outputs": list(action.output_files),
        }},
    ))


def step_retry_events(store, wf_id):
    rows = store._connection.execute(
        "SELECT event_type, payload FROM events WHERE workflow_id = ? ORDER BY created_at",
        (wf_id,),
    ).fetchall()
    return [(r["event_type"], json.loads(r["payload"])) for r in rows
            if r["event_type"] == "step_retry"]


# ── P0-1 retry：带内恢复全链 ─────────────────────────────────────────────

def test_retry_after_failure_then_complete_succeeds(tmp_path):
    """complete 失败→next 阻断→retry→重新 complete 成功，事件库有 step_retry 记录。"""
    store, runner, wf = setup_runner(tmp_path)
    # 1. 步骤失败
    runner.next_action(wf)
    fail = runner.complete_step(wf, StepResult(ok=False, stderr="error: model not found"))
    assert fail.status == "failed"
    # 2. next 被永久阻断（修复前的死锁态）
    blocked = runner.next_action(wf)
    assert blocked.status == "failed"
    assert "已失败" in blocked.message
    # 3. retry 带内恢复：FAILED→RUNNING，返回与 next 一致的重跑动作
    retry = runner.retry_last_failed(wf, by="tester-momo")
    assert retry.status == "advanced", retry.message
    assert retry.action is not None
    assert retry.action.skill_name == "comp-problem-analysis"
    # 4. 重新 complete 成功
    again = complete_ok(runner, wf)
    assert again.status in ("advanced", "completed"), again.message
    # 5. 事件库有 step_retry（含 step_id、by）
    retries = step_retry_events(store, wf)
    assert len(retries) == 1
    event_type, payload = retries[0]
    assert event_type == "step_retry"
    assert payload["step_id"] == retry.step_id
    assert payload["by"] == "tester-momo"


def test_retry_without_failed_step_reports_failure(tmp_path):
    _store, runner, wf = setup_runner(tmp_path)
    result = runner.retry_last_failed(wf)
    assert result.status == "failed"
    assert "没有 FAILED 步骤" in result.message


def test_retry_records_audit_engine_event(tmp_path):
    """step_retry 也写入引擎侧操作审计（恢复行为纳入审计链）。"""
    import tempfile
    _store, runner, wf = setup_runner(tmp_path)
    runner.next_action(wf)
    runner.complete_step(wf, StepResult(ok=False, stderr="boom"))
    audit_root = Path(tempfile.mkdtemp())
    from engine.audit_store import AuditStore
    runner._audit = AuditStore(audit_root)
    runner.retry_last_failed(wf, by="auditor")
    entries = [e for e in AuditStore(audit_root).events()
               if e.get("event") == "step_retry"]
    assert entries, "step_retry 必须落入引擎侧操作审计"
    assert entries[-1].get("by") == "auditor"


# ── P0-3 checkpoint_id 输出 ─────────────────────────────────────────────

def test_runner_complete_waiting_checkpoint_carries_checkpoint_id(tmp_path):
    store, runner, wf = setup_runner(tmp_path, first_checkpoint=True)
    result = complete_ok(runner, wf)
    assert result.status == "waiting_checkpoint"
    assert result.checkpoint_id
    # 与事件库对得上
    candidates = store.resume_candidates()
    assert candidates[0].checkpoint.id == result.checkpoint_id


def test_runner_next_blocked_carries_checkpoint_id(tmp_path):
    store, runner, wf = setup_runner(tmp_path, first_checkpoint=True)
    complete_ok(runner, wf)
    blocked = runner.next_action(wf)
    assert blocked.status == "blocked"
    assert blocked.checkpoint_id
    assert blocked.checkpoint_id == store.resume_candidates()[0].checkpoint.id


# ── CLI 层：retry / approve --by / 输出字段 ──────────────────────────────

@pytest.fixture()
def cli_env(tmp_path, monkeypatch):
    """隔离 WORKFLOW_INDEX 到 tmp，避免污染仓库 .engine 索引。"""
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", tmp_path / "workflow-index.json")
    return tmp_path


def _run_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["workflow_cli", *args])
    rc = workflow_cli.main()
    out = capsys.readouterr().out
    return rc, (json.loads(out) if out.strip() else {})


def test_cli_retry_end_to_end_with_step_retry_event(cli_env, monkeypatch, capsys):
    """真实模板 comp_cumcm 端到端：start→next→complete 失败→next 阻断→retry。"""
    ws = cli_env / "ws"
    db = cli_env / "workflow.sqlite"
    rc, started = _run_cli(monkeypatch, capsys, "start", "--template", "comp_cumcm",
                           "--workspace", str(ws), "--db", str(db))
    assert rc == 0
    wf = started["workflow_id"]

    rc, nxt = _run_cli(monkeypatch, capsys, "next", "--wf", wf, "--db", str(db))
    assert rc == 0 and nxt["status"] == "advanced"
    # 小修 6b：手册口径步号 = position + 1
    assert nxt["action"]["position"] == 0
    assert nxt["action"]["step_number_manual"] == 1

    rc, failed = _run_cli(monkeypatch, capsys, "complete", "--wf", wf,
                          "--ok", "false", "--stderr", "boom", "--db", str(db))
    assert rc == 1 and failed["status"] == "failed"

    rc, blocked = _run_cli(monkeypatch, capsys, "next", "--wf", wf, "--db", str(db))
    assert rc == 1 and blocked["status"] == "failed"

    rc, retried = _run_cli(monkeypatch, capsys, "retry", "--wf", wf,
                           "--by", "cli-tester", "--db", str(db))
    assert rc == 0, json.dumps(retried, ensure_ascii=False)
    assert retried["status"] == "advanced"
    assert retried["action"]["skill_name"] == "comp-problem-analysis"
    assert retried["action"]["step_number_manual"] == 1

    # 事件库核实 step_retry（含 step_id、by）
    connection = sqlite3.connect(db)
    rows = connection.execute(
        "SELECT payload FROM events WHERE event_type = 'step_retry'"
    ).fetchall()
    connection.close()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])
    assert payload["step_id"] == retried["step_id"]
    assert payload["by"] == "cli-tester"


def _make_blocked_checkpoint(db_path):
    """直接用 store 造一个 blocked 步骤 + 待批 checkpoint（approve 测试脚手架）。"""
    with WorkflowStore(db_path) as store:
        workflow = store.create_workflow("demo", {"workspace": "."})
        step = store.add_steps(workflow.id, [
            {"name": "comp-problem-analysis", "metadata": {"has_checkpoint": True}}])[0]
        store.transition_step(step.id, "blocked")  # PENDING→BLOCKED 合法转移
        checkpoint = store.create_checkpoint(
            workflow.id, step.id, {"status": "waiting_checkpoint", "type": "approve"})
    return workflow.id, checkpoint.id


def test_cli_approve_without_by_is_rejected_with_teaching(cli_env, monkeypatch, capsys):
    db = cli_env / "workflow.sqlite"
    _wf, checkpoint_id = _make_blocked_checkpoint(db)
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "approve",
                                      "--checkpoint", checkpoint_id, "--db", str(db)])
    with pytest.raises(SystemExit) as excinfo:
        workflow_cli.main()
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "--by" in err
    assert "批准人" in err


def test_cli_approve_with_by_records_approved_by(cli_env, monkeypatch, capsys):
    db = cli_env / "workflow.sqlite"
    wf_id, checkpoint_id = _make_blocked_checkpoint(db)
    rc, result = _run_cli(monkeypatch, capsys, "approve", "--checkpoint", checkpoint_id,
                          "--db", str(db), "--by", "默默")
    assert rc == 0, json.dumps(result, ensure_ascii=False)
    assert result["status"] in ("advanced", "completed", "blocked")

    connection = sqlite3.connect(db)
    rows = connection.execute(
        "SELECT payload FROM events WHERE event_type = 'checkpoint_approved'"
    ).fetchall()
    # approve 原子转移会新建一条 approved checkpoint（state.response 含批准人）
    states = connection.execute(
        "SELECT c.state FROM checkpoints c JOIN workflow_steps s ON s.id = c.step_id "
        "JOIN events e ON e.checkpoint_id = c.id "
        "WHERE e.event_type = 'checkpoint_approved'"
    ).fetchall()
    connection.close()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])
    assert payload["approved_by"] == "默默"
    # checkpoint 记录（state.response）同样写入批准人
    assert states, "批准必须产生 approved checkpoint 记录"
    state = json.loads(states[0][0])
    assert state["response"]["approved_by"] == "默默"


def test_cli_next_blocked_output_contains_checkpoint_id(cli_env, monkeypatch, capsys):
    db = cli_env / "workflow.sqlite"
    _wf, checkpoint_id = _make_blocked_checkpoint(db)
    # next 需要 workflow 数据库解析：显式 --db
    connection = sqlite3.connect(db)
    wf_id = connection.execute("SELECT workflow_id FROM checkpoints WHERE id = ?",
                               (checkpoint_id,)).fetchone()[0]
    connection.close()
    rc, output = _run_cli(monkeypatch, capsys, "next", "--wf", wf_id, "--db", str(db))
    assert rc == 1 and output["status"] == "blocked"
    # P0-3：blocked 输出直接携带待批 checkpoint UUID
    assert output.get("checkpoint_id") == checkpoint_id


def test_cli_complete_waiting_checkpoint_output_contains_checkpoint_id(cli_env, monkeypatch, capsys):
    """真实模板第 1 步（has_checkpoint）complete 成功后输出 checkpoint_id。"""
    ws = cli_env / "ws"
    db = cli_env / "workflow.sqlite"
    rc, started = _run_cli(monkeypatch, capsys, "start", "--template", "comp_cumcm",
                           "--workspace", str(ws), "--db", str(db))
    assert rc == 0
    wf = started["workflow_id"]

    rc, nxt = _run_cli(monkeypatch, capsys, "next", "--wf", wf, "--db", str(db))
    assert rc == 0
    action = nxt["action"]
    assert action["has_checkpoint"] is True
    output_file = action["output_files"][0]
    path = ws / output_file
    path.parent.mkdir(parents=True, exist_ok=True)
    # P5 退出判据（2026-09-19）：step1 的 PROBLEM_ANALYSIS.md 现声明 output_specs
    # （min_bytes 4000 + require_any 假设/模型/求解/问题）——测试正文须含实质特征词，
    # 否则会被"目录级薄产物"拦截。这里按真实产物的形态写。
    body = (
        "# 赛题分析\n\n## 一、问题重述与拆解\n本题共 4 个子问题，需分别给出**假设**、"
        "**模型**与**求解**路径。\n\n## 二、模型假设\n1. 假设物料各向同性且热物性随含水率变化。\n"
        "2. 假设干燥介质温度在腔体内均匀。\n\n## 三、建模与求解思路\n问题1建立一维传热**模型**，"
        "问题2引入对流边界，问题3把边界条件改为连续事件的**求解**，问题4做参数灵敏度分析。\n"
    )
    path.write_text(body * 12, encoding="utf-8")
    skill_sha = hashlib.sha256(Path(action["skill_path"]).read_bytes()).hexdigest()
    evidence = {
        "schema_version": 1, "agent": "OpenCode Desktop",
        "step_id": action["step_id"], "skill_name": action["skill_name"],
        "skill_sha256": skill_sha,
        # P4 技能绑定（2026-09-19）：真实模板步骤默认声明 main_required=true，
        # 主技能契约必须留真实读取痕迹——咨询命令随本测试显式给出（这正是新闸要的形态：
        # 不是"应该读了"，而是 evidence 里有一条读技能的命）。
        "commands": [{"command": "python code/gen_report.py", "returncode": 0, "cwd": "."},
                     {"command": f"cat {action['skill_path']}", "returncode": 0, "cwd": "."}]
                    # mandatory 资产的真实读取痕迹（W2：used 申报须有命令级痕迹）
                    + [{"command": f"cat {a['path']}", "returncode": 0, "cwd": "."}
                       for a in action.get("assets", []) if a.get("mandatory")],
        "inputs": [], "outputs": [output_file],
        # 真实模板第 1 步（2026-09-12 修剪后推荐清单为空）：链路验证级按 next 输出动态如实申报。
        # 清单为空时 C1 闸不激活，字段可省略；此处仍随 action 输出以保持契约演练覆盖。
        "companion_skills": {"used": [],
                             "skipped": [{"skill": s, "reason": "链路验证级测试不加载辅助技能"}
                                         for s in action.get("companion_skills", [])]},
        # 真实模板第 1 步 assets（2026-09-12 C2 资产机制；2026-09-23 W2 mandatory 档起）：
        # mandatory 资产（历年真题索引）不接受 skipped——如实申报 used 并在下述命令留读取痕迹；
        # 其余资产仍按链路验证级 skipped。清单从 next 输出动态取，模板演进时自维护。
        "assets": {"used": [a["name"] for a in action.get("assets", []) if a.get("mandatory")],
                   "skipped": [{"name": a["name"], "reason": "链路验证级测试不消费资产"}
                               for a in action.get("assets", []) if not a.get("mandatory")]},
    }
    rc, done = _run_cli(monkeypatch, capsys, "complete", "--wf", wf, "--ok", "true",
                        "--artifacts", output_file,
                        "--evidence", json.dumps(evidence), "--db", str(db))
    assert rc == 0, json.dumps(done, ensure_ascii=False)
    assert done["status"] == "waiting_checkpoint"
    # P0-3：complete 输出直接携带 checkpoint UUID
    assert done.get("checkpoint_id")
