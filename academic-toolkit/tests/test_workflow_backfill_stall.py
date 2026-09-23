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

def make_catalog(first_checkpoint=False, binding=False):
    first = {"skill_name": "comp-problem-analysis", "primary_output": "REPORT.md",
             "output_files": ["REPORT.md"], "has_checkpoint": first_checkpoint,
             "checkpoint_type": "approve" if first_checkpoint else None}
    if binding:
        # P4 资产激活批次 B：模拟真实模板步骤的三重申报-痕迹义务
        # （skill_binding 主技能痕迹 + companion 申报 + assets 申报）
        first["metadata"] = {
            "skill_binding": {"main_required": True},
            "companion_skills": ["citation-check"],
            "assets": [{"name": "题目数据", "path": "data/problem.csv",
                        "note": "题面附件"}],
        }
    return {"demo": {"sub_steps": [
        first,
        {"skill_name": "comp-modeling", "primary_output": "MODEL.md",
         "output_files": ["MODEL.md"], "has_checkpoint": False},
    ]}}


def setup_runner(tmp_path, first_checkpoint=False, binding=False):
    skills = tmp_path / "skills"
    for name in ("comp-problem-analysis", "comp-modeling"):
        skill = skills / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("skill", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, make_catalog(first_checkpoint, binding), skills)
    workflow = runner.start("demo", tmp_path / "workspace", {})
    return store, runner, workflow.id


def _step_id(store, wf_id, name):
    row = store._connection.execute(
        "SELECT id FROM workflow_steps WHERE workflow_id = ? AND name = ?",
        (wf_id, name)).fetchone()
    return row["id"]


def _valid_backfill_evidence(runner_skills_root, store, wf_id, step_name, outputs):
    """构造与 complete_step 同构、能通过全套校验的补录证据（demo 绑定模板专用）。"""
    import hashlib as _hl
    skill_md = runner_skills_root / step_name / "SKILL.md"
    return {
        "schema_version": 1,
        "agent": "backfill-tester",
        "step_id": _step_id(store, wf_id, step_name),
        "skill_name": step_name,
        "skill_sha256": _hl.sha256(skill_md.read_bytes()).hexdigest(),
        # 命令含技能名（'-'→'_' 归一后命中 main 痕迹）——真实补录应记 consult 命令
        "commands": [{"command": f"python scripts/run_{step_name}.py --offline",
                      "returncode": 0, "cwd": "."}],
        "inputs": [],
        "outputs": list(outputs),
        "companion_skills": {"used": [], "skipped": [
            {"skill": "citation-check", "reason": "补录场景仅产物对账，未咨询引用检查"}]},
        "assets": {"used": [], "skipped": [
            {"name": "题目数据", "reason": "题面数据断链期未使用"}]},
    }


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
    _age_step(tmp_path / "workflow.sqlite", "comp-problem-analysis", hours=48.0)
    report = runner.detect_stalled(wf, stall_hours=12.0)
    assert report["alert"] is True
    assert len(report["stalled"]) == 1
    hit = report["stalled"][0]
    assert hit["skill_name"] == "comp-problem-analysis"
    assert hit["kind"] == "running_stalled"
    assert hit["stalled_hours"] >= 12.0


def test_stall_detects_checkpoint_pending(tmp_path):
    """BLOCKED 等待批准超阈值 → checkpoint_pending 告警。"""
    store, runner, wf = setup_runner(tmp_path, first_checkpoint=True)
    result = complete_ok(runner, wf)
    assert result.status == "waiting_checkpoint"
    _age_step(tmp_path / "workflow.sqlite", "comp-problem-analysis", hours=30.0)
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
    _age_step(tmp_path / "workflow.sqlite", "comp-problem-analysis", hours=48.0)
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

    result = runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"],
                                  commands=["python tools/analysis.py --offline"],
                                  note="断链期间手工完成，补录产物", by="tester")
    assert result.status == "advanced", result.message

    # 步骤状态 COMPLETED
    row = store._connection.execute(
        "SELECT status FROM workflow_steps WHERE workflow_id = ? AND name = ?",
        (wf, "comp-problem-analysis")).fetchone()
    assert row["status"] == "completed"

    # STEP_MANIFEST 落盘且带补录标记与产物哈希
    manifest = json.loads((ws / "STEP_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["stepName"] == "comp-problem-analysis"
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
    runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"], by="tester")
    runner.backfill_step(wf, "comp-modeling", ["MODEL.md"], by="tester")
    row = store._connection.execute(
        "SELECT status FROM workflows WHERE id = ?", (wf,)).fetchone()
    assert row["status"] == "completed"


def test_backfill_blocked_step_allowed(tmp_path):
    """BLOCKED（等批悬置）步骤可补录——对应'批准后 agent 绕开 runner'场景。"""
    store, runner, wf = setup_runner(tmp_path, first_checkpoint=True)
    complete_ok(runner, wf)  # 第一步 BLOCKED（waiting_checkpoint）
    (tmp_path / "workspace" / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    result = runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"], by="tester")
    assert result.status == "advanced", result.message
    row = store._connection.execute(
        "SELECT status FROM workflow_steps WHERE name = 'comp-problem-analysis'").fetchone()
    assert row["status"] == "completed"


def test_backfill_rejects_missing_artifact(tmp_path):
    """产物不存在 → 拒绝补录且步骤状态不变（防伪造溯源）。"""
    store, runner, wf = setup_runner(tmp_path)
    result = runner.backfill_step(wf, "comp-problem-analysis", ["不存在的产物.md"], by="tester")
    assert result.status == "failed"
    assert "不存在" in result.message
    row = store._connection.execute(
        "SELECT status FROM workflow_steps WHERE name = 'comp-problem-analysis'").fetchone()
    assert row["status"] == "pending"
    assert not _events(store, wf, "step_backfilled")


def test_backfill_rejects_empty_artifacts(tmp_path):
    """零产物空补录 → 拒绝（防空补录洗白断链）。"""
    _store, runner, wf = setup_runner(tmp_path)
    result = runner.backfill_step(wf, "comp-problem-analysis", [], by="tester")
    assert result.status == "failed"
    assert "至少需要" in result.message


def test_backfill_rejects_completed_step(tmp_path):
    """已 COMPLETED 步骤 → 拒绝重复补录。"""
    store, runner, wf = setup_runner(tmp_path)
    complete_ok(runner, wf)
    (tmp_path / "workspace" / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    result = runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"], by="tester")
    assert result.status == "failed"
    assert "已 COMPLETED" in result.message


def test_backfill_unknown_step(tmp_path):
    _store, runner, wf = setup_runner(tmp_path)
    result = runner.backfill_step(wf, "comp-not-exist", ["x.md"], by="tester")
    assert result.status == "failed"
    assert "未知步骤" in result.message


# ── P4 资产激活批次 B：绑定旁路封堵 ──────────────────────────────────────

def _status_of(store, name):
    row = store._connection.execute(
        "SELECT status FROM workflow_steps WHERE name = ?", (name,)).fetchone()
    return row["status"]


def test_backfill_binding_step_requires_evidence_or_waiver(tmp_path):
    """声明绑定的步骤裸补录 → 拒绝且零状态副作用（禁止静默旁路）。"""
    store, runner, wf = setup_runner(tmp_path, binding=True)
    (tmp_path / "workspace" / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    result = runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"], by="tester")
    assert result.status == "failed"
    assert "禁止静默旁路" in result.message
    assert "--evidence" in result.message and "--waive-binding" in result.message
    assert _status_of(store, "comp-problem-analysis") == "pending"
    assert not _events(store, wf, "step_backfilled")


def test_backfill_waive_requires_reason(tmp_path):
    """豁免必须带非空理由——无理由豁免 = 静默旁路的变体，拒绝。"""
    store, runner, wf = setup_runner(tmp_path, binding=True)
    (tmp_path / "workspace" / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    result = runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"], by="tester",
                                  waive_binding=True, waive_reason="   ")
    assert result.status == "failed"
    assert "waive-reason" in result.message
    assert _status_of(store, "comp-problem-analysis") == "pending"


def test_backfill_waive_passes_and_lands_audit_trail(tmp_path):
    """显式豁免：补录放行，但事件 payload / 引擎审计 / 运行日志三处留痕。"""
    import tempfile
    from engine.audit_store import AuditStore
    store, runner, wf = setup_runner(tmp_path, binding=True)
    audit_root = Path(tempfile.mkdtemp())
    runner._audit = AuditStore(audit_root)
    (tmp_path / "workspace" / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    result = runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"], by="tester",
                                  waive_binding=True, waive_reason="断链期纯手工，证据不可复原")
    assert result.status == "advanced", result.message
    events = _events(store, wf, "step_backfilled")
    assert events[0]["binding_check"] == "waived"
    assert "断链期纯手工" in events[0]["waive_reason"]
    waived = [e for e in AuditStore(audit_root).events() if e.get("event") == "backfill_binding_waived"]
    assert waived, "豁免必须产生独立可检索的审计事件"
    assert waived[-1]["reason"] == "断链期纯手工，证据不可复原"
    assert waived[-1]["obligations"] == ["companion_skills", "skill_binding", "assets"]


def test_backfill_full_evidence_verified_path(tmp_path):
    """同构 evidence 补录：走 validate_execution_evidence + C1/P4/C2 三道闸，
    通过后证据落盘 .engine/evidence/，事件记 binding_check=verified。"""
    store, runner, wf = setup_runner(tmp_path, binding=True)
    ws = tmp_path / "workspace"
    (ws / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    evidence = _valid_backfill_evidence(
        ws.parent / "skills", store, wf, "comp-problem-analysis", ["REPORT.md"])
    result = runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"], by="tester",
                                  evidence=evidence)
    assert result.status == "advanced", result.message
    assert _status_of(store, "comp-problem-analysis") == "completed"
    events = _events(store, wf, "step_backfilled")
    assert events[0]["binding_check"] == "verified"
    ev_file = ws / ".engine" / "evidence" / f"{_step_id(store, wf, 'comp-problem-analysis')}.json"
    assert ev_file.is_file(), "verified 补录必须与 complete_step 同构落证据文件"
    # STEP_MANIFEST 的命令在缺 --command 时从证据回退（不丢溯源）
    manifest = json.loads((ws / "STEP_MANIFEST.json").read_text(encoding="utf-8"))
    assert any("comp_problem_analysis" in c.get("command", "").replace("-", "_")
               for c in manifest["commands"] or [])


def test_backfill_forged_evidence_rejected(tmp_path):
    """伪造绑定签名（skill_sha256 与 SKILL.md 不符）→ 拒绝，且步骤状态不变。"""
    store, runner, wf = setup_runner(tmp_path, binding=True)
    (tmp_path / "workspace" / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    evidence = _valid_backfill_evidence(
        tmp_path / "skills", store, wf, "comp-problem-analysis", ["REPORT.md"])
    evidence["skill_sha256"] = "0" * 64
    result = runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"], by="tester",
                                  evidence=evidence)
    assert result.status == "failed"
    assert "invalid backfill execution evidence" in result.message
    assert _status_of(store, "comp-problem-analysis") == "pending"


def test_backfill_evidence_gate_violation_rejected(tmp_path):
    """哈希真实但缺 companion 申报 → C1 闸拒绝（与 complete_step 同等强度）。"""
    store, runner, wf = setup_runner(tmp_path, binding=True)
    (tmp_path / "workspace" / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    evidence = _valid_backfill_evidence(
        tmp_path / "skills", store, wf, "comp-problem-analysis", ["REPORT.md"])
    evidence.pop("companion_skills")
    result = runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"], by="tester",
                                  evidence=evidence)
    assert result.status == "failed"
    assert "辅助技能申报不合规" in result.message
    assert _status_of(store, "comp-problem-analysis") == "pending"


def test_backfill_no_binding_step_unaffected(tmp_path):
    """未声明任何义务的步骤补录行为不变（向后兼容，记 no_binding）。"""
    store, runner, wf = setup_runner(tmp_path)
    (tmp_path / "workspace" / "REPORT.md").write_text("x" * 3000, encoding="utf-8")
    result = runner.backfill_step(wf, "comp-problem-analysis", ["REPORT.md"], by="tester")
    assert result.status == "advanced", result.message
    assert _events(store, wf, "step_backfilled")[0]["binding_check"] == "no_binding"


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
    """真实模板端到端：start → 裸补录被拒（P4 批次 B 旁路封堵）→
    --waive-binding --waive-reason 显式豁免成功且事件/审计落账。"""
    ws = cli_env / "ws"
    db = cli_env / "workflow.sqlite"
    rc, started = _run_cli(monkeypatch, capsys, "start", "--template", "comp_cumcm",
                           "--workspace", str(ws), "--db", str(db))
    assert rc == 0
    wf = started["workflow_id"]

    (ws / "PROBLEM_ANALYSIS.md").write_text("# 赛题分析\n" + "内容。" * 1000,
                                            encoding="utf-8")
    # ① comp_cumcm 每一步都声明 skill_binding（2026-09-19 P4）——裸补录必须被拒
    rc, blocked = _run_cli(monkeypatch, capsys, "backfill", "--wf", wf,
                           "--step", "comp-problem-analysis", "--artifact", "PROBLEM_ANALYSIS.md",
                           "--by", "cli-tester", "--db", str(db))
    assert rc == 1
    assert "禁止静默旁路" in blocked["message"]

    # ② 无理由豁免也被拒
    rc, nofile = _run_cli(monkeypatch, capsys, "backfill", "--wf", wf,
                          "--step", "comp-problem-analysis", "--artifact", "PROBLEM_ANALYSIS.md",
                          "--waive-binding", "--by", "cli-tester", "--db", str(db))
    assert rc == 1
    assert "waive-reason" in nofile["message"]

    # ③ 显式豁免 + 理由 → 放行，step_backfilled payload 记 waived
    rc, done = _run_cli(monkeypatch, capsys, "backfill", "--wf", wf,
                        "--step", "comp-problem-analysis", "--artifact", "PROBLEM_ANALYSIS.md",
                        "--command", "python code/analyze.py --offline",
                        "--note", "断链补录演练", "--by", "cli-tester",
                        "--waive-binding", "--waive-reason", "断链期纯手工完成，命令级证据不可复原",
                        "--db", str(db))
    assert rc == 0, json.dumps(done, ensure_ascii=False)
    assert done["status"] == "advanced"

    connection = sqlite3.connect(db)
    rows = connection.execute(
        "SELECT payload FROM events WHERE event_type = 'step_backfilled'").fetchall()
    connection.close()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])
    assert payload["by"] == "cli-tester"
    assert payload["skill_name"] == "comp-problem-analysis"
    assert payload["binding_check"] == "waived"
    assert "断链期纯手工完成" in payload["waive_reason"]


def test_cli_backfill_evidence_invalid_json_rejected(cli_env, monkeypatch, capsys):
    """--evidence 非法 JSON → JSON 错误契约（不炸 traceback），退出码 1。"""
    ws = cli_env / "ws"
    db = cli_env / "workflow.sqlite"
    rc, started = _run_cli(monkeypatch, capsys, "start", "--template", "comp_cumcm",
                           "--workspace", str(ws), "--db", str(db))
    assert rc == 0
    (ws / "PROBLEM_ANALYSIS.md").write_text("x" * 3000, encoding="utf-8")
    rc, out = _run_cli(monkeypatch, capsys, "backfill", "--wf", started["workflow_id"],
                       "--step", "comp-problem-analysis", "--artifact", "PROBLEM_ANALYSIS.md",
                       "--evidence", "{不是JSON", "--by", "cli-tester", "--db", str(db))
    assert rc == 1
    assert "不是合法 JSON" in out["message"]


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
