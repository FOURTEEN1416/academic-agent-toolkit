"""D1 断链告警（stall）与手工补录（backfill）回归测试。

背景（2026-09-12 engine_step.log 教训，原仓库缺陷修复建议 D1）：
14 步 runner 推进到 step 3 等待 checkpoint 批准后即停，step 4–14 全部
绕开 runner 手工完成——引擎无告警、事件库零记录，溯源断档。本文件覆盖：

- detect_stalled：RUNNING 超时 / checkpoint 等批悬置 / 新工作流静默；
- backfill_step：PENDING/BLOCKED/RUNNING 三态补录、产物缺失拒绝、
  COMPLETED 拒绝、事件 step_backfilled 落账、全补录后工作流收尾；
- CLI：stall / backfill 冒烟（真实模板 comp_cumcm 端到端）。
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


# ── 共享脚手架（与 test_workflow_retry_cli 同款两步小模板） ─────────────

def make_catalog(first_checkpoint=False):
    return {"demo": {"sub_steps": [
        {"skill_name": "comp-prob-analysis", "primary_output": "REPORT.md",
         "output_files": ["REPORT.md"], "has_checkpoint": first_checkpoint,
         "checkpoint_type": "approve" if first_checkpoint else None},
        {"skill_name": "comp-modeling", "primary_output": "MODEL.md",
         "output_files": ["MODEL.md"], "has_checkpoint": False},
    ]}}


def setup_runner(tmp_path, first_checkpoint=False):
    skills = tmp_path / "skills"
    for name in ("comp-prob-analysis", "comp-modeling"):
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


def _age_step(db_path, skill_name, hours=48.0):
    """把指定步骤 updated_at 拨回 hours 小时前（制造停滞现场）。"""
    from datetime import datetime, timedelta, timezone
    stamp = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    connection = sqlite3.connect(db_path)
    connection.execute("UPDATE workflow_steps SET updated_at = ? WHERE name = ?",
                       (stamp, skill_name))
    connection.commit()
    connection.close()


def _events(store, wf_id, event_type):
    rows = store._connection.execute(
        "SELECT payload FROM events WHERE workflow_id = ? AND event_type = ? "
        "ORDER BY created_at",
        (wf_id, event_type),
    ).fetchall()
    return [json.loads(r["payload"]) for r in rows]


# ── detect_stalled：断链告警 ─────────────────────────────────────────────

def test_stall_detects_running_timeout(tmp_path):
    """步骤 RUNNING 后超阈值未回报 → running_stalled 告警。"""
    store, runner, wf = setup_runner(tmp_path)
    runner.next_action(wf)  # 第一步 → RUNNING
    _age_step(tmp_path / "workflow.sqlite", "comp-prob-analysis", hours=48.0)
    report = runner.detect_stalled(wf, stall_hours=12.0)
    assert report["alert"] is True
    assert len(report["stalled"]) == 1
    hit = report["stalled"][0]
    assert hit["skill_name"] == "comp-prob-analysis"
    assert hit["kind"] == "running_stalled"
    assert hit["stalled_hours"] >= 12.0


def test_stall_detects_checkpoint_pending(tmp_path):
    """BLOCKED 等待批准超阈值 → checkpoint_pending 告警。"""
    store, runner, wf = setup_runner(tmp_path, first_checkpoint=True)
    result = complete_ok(runner, wf)
    assert result.status == "waiting_checkpoint"
    _age_step(tmp_path / "workflow.sqlite", "comp-prob-analysis", hours=30.0)
    report = runner.detect_stalled(wf, stall_hours=12.0)
    assert report["alert"] is True
    assert report["stalled"][0]["kind"] == "checkpoint_pending"


def test_stall_quiet_on_fresh_workflow(tmp_path):
    """新工作流（RUNNING 刚启动、无停滞）不告警。"""
    _store, runner, wf = setup_runner(tmp_path)
    runner.next_action(wf)  # RUNNING 但 updated_at 是现在
    report = runner.detect_stalled(wf, stall_hours=12.0)
    assert report["alert"] is False
    assert report["stalled"] == []


def test_stall_alert_lands_in_audit_store(tmp_path):
    """告警写入引擎侧操作审计（step_stall_alert），恢复行为可复盘。"""
    import tempfile
    store, runner, wf = setup_runner(tmp_path)
    runner.next_action(wf)
    _age_step(tmp_path / "workflow.sqlite", "comp-prob-analysis", hours=48.0)
    audit_root = Path(tempfile.mkdtemp())
    from engine.audit_store import AuditStore
    runner._audit = AuditStore(audit_root)
    report = runner.detect_stalled(wf, stall_hours=12.0)
    assert report["alert"] is True
    entries = [e for e in AuditStore(audit_root).events()
               if e.get("event") == "step_stall_alert"]
    assert entries, "step_stall_alert 必须落入引擎侧操作审计"
    assert entries[-1].get("stalled")


# ── backfill_step：手工补录 ──────────────────────────────────────────────

def test_backfill_completes_pending_step_with_manifest(tmp_path):
    """PENDING 步骤补录：状态 COMPLETED + STEP_MANIFEST + 事件/产物哈希落账。"""
    store, runner, wf = setup_runner(tmp_path)
    ws = tmp_path / "workspace"
    (ws / "REPORT.md").write_text("# 赛题分析\n" + "内容。" * 500, encoding="utf-8")

    result = runner.backfill_step(wf, "comp-prob-analysis", ["REPORT.md"],
                                  commands=["python tools/analysis.py --offline"],
                                  note="断链期间手工完成，补录产物", by="tester")
    assert result.status == "advanced", result.message

    # 步骤状态 COMPLETED
    row = store._connection.execute(
        "SELECT status FROM workflow_steps WHERE workflow_id = ? AND name = ?",
        (wf, "comp-prob-analysis")).fetchone()
    assert row["status"] == "completed"

    # STEP_MANIFEST 落盘且带补录标记与产物哈希
    manifest = json.loads((ws / "STEP_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["stepName"] == "comp-prob-analysis"
    assert manifest["backend"] == "manual-backfill"
    assert manifest["config"]["backfill"] is True
    assert manifest["outputFiles"], "manifest 必须含产物记录"

    # 事件 step_backfilled 落账（区别于 step_completed，by/note 可复盘）
    events = _events(store, wf, "step_backfilled")
    assert len(events) == 1
    assert events[0]["by"] == "tester"
    assert events[0]["note"] == "断链期间手工完成，补录产物"
    assert events[0]["commands"] == ["python tools/analysis.py --offline"]

    # artifacts 表有 sha256（复审可直接对账文件）
    rows = store._connection.execute(
        "SELECT a.name, a.metadata FROM artifacts a WHERE a.workflow_id = ?",
        (wf,)).fetchall()
    assert any(json.loads(r["metadata"]).get("sha256") for r in rows)


def test_backfill_all_steps_completes_workflow(tmp_path):
    """全部步骤补录后工作流自动收尾（completed），与在环路径一致。"""
    store, runner, wf = setup_runner(tmp_path)
    ws = tmp_path / "workspace"
    for name in ("REPORT.md", "MODEL.md"):
        (ws / name).write_text("x" * 3000, encoding="utf-8")
    runner.backfill_step(wf, "comp-prob-analysis", ["REPORT.md"], by="tester")
    runner.backfill_step(wf, "comp-modeling", ["MODEL.md"], by="tester")
    row = store._connection.execute(
        "SELECT status FROM workflows WHERE id = ?", (wf,)).fetchone()
    assert row["status"] == "completed"


def test_backfill_blocked_step_allowed(tmp_path):
    """BLOCKED（等批悬置）步骤可补录——对应'批准后 agent 绕开 runner'场景。"""
    store, runner, wf = setup_runner(tmp_path, first_checkpoint=True)
    complete_ok(runner, wf)  # 第一步 BLOCKED（waiting_checkpoint）
    (tmp_path / "workspace" / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    result = runner.backfill_step(wf, "comp-prob-analysis", ["REPORT.md"], by="tester")
    assert result.status == "advanced", result.message
    row = store._connection.execute(
        "SELECT status FROM workflow_steps WHERE name = 'comp-prob-analysis'").fetchone()
    assert row["status"] == "completed"


def test_backfill_rejects_missing_artifact(tmp_path):
    """产物不存在 → 拒绝补录且步骤状态不变（防伪造溯源）。"""
    store, runner, wf = setup_runner(tmp_path)
    result = runner.backfill_step(wf, "comp-prob-analysis", ["不存在的产物.md"], by="tester")
    assert result.status == "failed"
    assert "不存在" in result.message
    row = store._connection.execute(
        "SELECT status FROM workflow_steps WHERE name = 'comp-prob-analysis'").fetchone()
    assert row["status"] == "pending"
    assert not _events(store, wf, "step_backfilled")


def test_backfill_rejects_empty_artifacts(tmp_path):
    """零产物空补录 → 拒绝（防空补录洗白断链）。"""
    _store, runner, wf = setup_runner(tmp_path)
    result = runner.backfill_step(wf, "comp-prob-analysis", [], by="tester")
    assert result.status == "failed"
    assert "至少需要" in result.message


def test_backfill_rejects_completed_step(tmp_path):
    """已 COMPLETED 步骤 → 拒绝重复补录。"""
    store, runner, wf = setup_runner(tmp_path)
    complete_ok(runner, wf)
    (tmp_path / "workspace" / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    result = runner.backfill_step(wf, "comp-prob-analysis", ["REPORT.md"], by="tester")
    assert result.status == "failed"
    assert "已 COMPLETED" in result.message


def test_backfill_unknown_step(tmp_path):
    _store, runner, wf = setup_runner(tmp_path)
    result = runner.backfill_step(wf, "comp-not-exist", ["x.md"], by="tester")
    assert result.status == "failed"
    assert "未知步骤" in result.message


# ── CLI 层：stall / backfill 冒烟（真实模板 comp_cumcm） ────────────────

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


def test_cli_backfill_end_to_end(cli_env, monkeypatch, capsys):
    """真实模板端到端：start → backfill 第一步 → rc 0 + 事件落账。"""
    ws = cli_env / "ws"
    db = cli_env / "workflow.sqlite"
    rc, started = _run_cli(monkeypatch, capsys, "start", "--template", "comp_cumcm",
                           "--workspace", str(ws), "--db", str(db))
    assert rc == 0
    wf = started["workflow_id"]

    (ws / "PROBLEM_ANALYSIS.md").write_text("# 赛题分析\n" + "内容。" * 1000,
                                            encoding="utf-8")
    rc, done = _run_cli(monkeypatch, capsys, "backfill", "--wf", wf,
                        "--step", "comp-prob-analysis", "--artifact", "PROBLEM_ANALYSIS.md",
                        "--command", "python code/analyze.py --offline",
                        "--note", "断链补录演练", "--by", "cli-tester", "--db", str(db))
    assert rc == 0, json.dumps(done, ensure_ascii=False)
    assert done["status"] == "advanced"

    connection = sqlite3.connect(db)
    rows = connection.execute(
        "SELECT payload FROM events WHERE event_type = 'step_backfilled'").fetchall()
    connection.close()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])
    assert payload["by"] == "cli-tester"
    assert payload["skill_name"] == "comp-prob-analysis"


def test_cli_stall_quiet_exit_zero(cli_env, monkeypatch, capsys):
    """fresh 工作流 stall 无告警 → 输出 alert=false 且退出码 0。"""
    db = cli_env / "workflow.sqlite"
    rc, started = _run_cli(monkeypatch, capsys, "start", "--template", "comp_cumcm",
                           "--workspace", str(cli_env / "ws"), "--db", str(db))
    assert rc == 0
    wf = started["workflow_id"]
    rc, report = _run_cli(monkeypatch, capsys, "stall", "--wf", wf,
                          "--hours", "12", "--db", str(db))
    assert rc == 0
    assert report["alert"] is False
