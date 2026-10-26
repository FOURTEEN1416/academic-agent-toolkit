"""P2b-1 / P2b-2 行为锁定：终审 severity 汇总 + 显式接收者判定。

覆盖台账批次三的两个任务：

- P2b-1：终审 ``gate_outcomes`` 消费 severity（advisory 记 advisory、有接收者的
  fixable 未解决记 fixable_open、blocking 失败仍 fail），并新增分档/状态占比汇总
  与未签署 open_items；delivery 判定不因 advisory fail 而 blocked，blocking fail
  仍 blocked。
- P2b-2：``receiver_of`` 只依据静态链结构 + 交付报告判定接收者。paper_writing
  链（auto-paper-improvement-loop 收尾）无接收者 → fixable 保持 blocking；
  comp_cumcm 链有 final_audit 步骤 → 接收者成立；finish 路径不再把 fixable
  一律当 needs_work。
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit.audit_store import build_final_audit_report  # noqa: E402
from engine.contracts.template_resolver import resolve_template  # noqa: E402
from engine.quality_gates import QualityGate, resolve_check_severity  # noqa: E402
from engine.storage.workflow_store import WorkflowStore  # noqa: E402
from engine.validation_policy import receiver_of  # noqa: E402
from engine.workflow_runner import WorkflowRunner  # noqa: E402
from execution.session import ExecutionSession  # noqa: E402


CATALOG = json.loads((ROOT / "engine/modex-core/templates.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------
# P2b-1：终审报告 severity 消费 / 汇总 / open_items
# ---------------------------------------------------------------

def _steps(receiver: bool) -> list[dict]:
    steps = [{"name": "solve", "metadata": {
        "required_checks": [], "output_files": ["paper/main.pdf"]}}]
    if receiver:
        steps.append({"name": "comp-final-audit", "metadata": {
            "required_checks": ["final_audit"],
            "output_files": ["AUDIT_REPORT.json"],
            "has_checkpoint": True, "checkpoint_type": "approve"}})
    return steps


def _build_report(tmp_path: Path, checks: dict, *, receiver: bool = True,
                  workflow_name: str = "demo_tpl", signed_open_items=None,
                  root: Path | None = None):
    base = Path(root) if root is not None else tmp_path
    base.mkdir(parents=True, exist_ok=True)
    project_root = base / "project"
    project_root.mkdir()
    workspace = base / "ws"
    paper = workspace / "paper"
    paper.mkdir(parents=True)
    payload = b"fake pdf bytes"
    (paper / "main.pdf").write_bytes(payload)
    manifest = {"artifacts": [{
        "path": "paper/main.pdf",
        "sha256": hashlib.sha256(payload).hexdigest()}]}
    db = base / "workflow.sqlite"
    with WorkflowStore(db) as store:
        workflow = store.create_workflow(
            workflow_name, {"workspace": str(workspace), "params": {}})
        created = store.add_steps(workflow.id, _steps(receiver))
        first = created[0]
        store.transition_step(first.id, "running")
        store.transition_step_with_checkpoint(
            workflow.id, first.id, "completed",
            {"status": "completed", "manifest": manifest},
            event={"type": "step_completed", "manifest": manifest,
                   "quality_gates": {"checks": checks}})
        for step in created[1:]:
            store.transition_step(step.id, "running")
            store.transition_step_with_checkpoint(
                workflow.id, step.id, "completed",
                {"status": "completed", "manifest": manifest},
                event={"type": "step_completed", "manifest": manifest,
                       "quality_gates": {"checks": {
                           "final_audit": {"ok": True, "status": "pass",
                                           "severity": "blocking"}}}})
    if signed_open_items is not None:
        (workspace / "DELIVERY_REPORT.json").write_text(json.dumps({
            "open_items": signed_open_items}), encoding="utf-8")
    report = build_final_audit_report(workspace, project_root, db)
    return report, workspace


def test_gate_outcomes_record_advisory_and_do_not_block_delivery(tmp_path):
    report, _ = _build_report(tmp_path, {
        "blocking_ok": {"ok": True, "status": "pass", "severity": "blocking"},
        "advisory_style": {"ok": False, "status": "fail", "severity": "advisory",
                           "reason": "风格提示不阻断"},
    })
    assert report["gate_outcomes"]["advisory_style"] == "advisory"
    assert report["gate_outcomes"]["blocking_ok"] == "pass"
    # advisory 失败不得把交付判定拖成 blocked（P2b-1 验收）
    assert report["delivery_decision"] == "ready", report["gate_outcomes"]
    detail = report["gate_outcome_details"]["advisory_style"]
    assert detail == {"severity": "advisory", "status": "fail", "outcome": "advisory"}
    summary = report["gate_outcome_summary"]
    assert summary["by_outcome"]["advisory"] == 1
    assert summary["by_severity"]["advisory"] == 1
    assert summary["severity_shares"]["advisory"] > 0
    assert report["open_items"] == []


def test_gate_outcomes_record_fixable_open_and_require_signature(tmp_path):
    checks = {
        "blocking_ok": {"ok": True, "status": "pass", "severity": "blocking"},
        "advisory_style": {"ok": False, "status": "fail", "severity": "advisory"},
        "fixable_body": {"ok": False, "status": "fail", "severity": "fixable",
                         "reason": "正文某段需返修"},
    }
    report, workspace = _build_report(tmp_path, checks)
    assert report["gate_outcomes"]["fixable_body"] == "fixable_open"
    assert report["gate_outcomes"]["advisory_style"] == "advisory"
    assert report["receiver"]["has_receiver"] is True
    assert "final_audit:" in report["receiver"]["receivers"][0]
    # 未签署 open item → 不可 ready（台账：无未签署 open item）
    assert report["delivery_decision"] == "blocked"
    item = next(item for item in report["open_items"]
                if item["check"] == "fixable_body")
    assert item["signed"] is False and item["outcome"] == "fixable_open"
    summary = report["gate_outcome_summary"]
    assert summary["by_outcome"]["fixable_open"] == 1
    assert summary["by_severity"]["fixable"] == 1

    # 人工签署 open item 后重算 delivery_ready（P2b-4 的签署数据面在此只做读取）
    signed_report, _ = _build_report(
        tmp_path, checks,
        signed_open_items=[{"check": "fixable_body", "signed": True,
                            "signed_by": "reviewer-A",
                            "signed_at": "2026-10-26T00:00:00+00:00"}],
        root=tmp_path / "signed")
    assert signed_report["delivery_decision"] == "ready", signed_report["open_items"]
    signed_item = next(item for item in signed_report["open_items"]
                       if item["check"] == "fixable_body")
    assert signed_item["signed"] is True
    assert signed_item["signed_by"] == "reviewer-A"


def test_gate_outcomes_blocking_failure_still_blocks_delivery(tmp_path):
    report, _ = _build_report(tmp_path, {
        "blocking_ok": {"ok": True, "status": "pass", "severity": "blocking"},
        "blocking_bad": {"ok": False, "status": "fail", "severity": "blocking",
                         "reason": "证据缺失"},
    })
    assert report["gate_outcomes"]["blocking_bad"] == "fail"
    assert report["delivery_decision"] == "blocked"


def test_gate_outcomes_fixable_without_receiver_stays_fail(tmp_path):
    report, _ = _build_report(
        tmp_path,
        {"fixable_body": {"ok": False, "status": "fail", "severity": "fixable"}},
        receiver=False, workflow_name="paper_writing")
    assert report["gate_outcomes"]["fixable_body"] == "fail"
    assert report["receiver"]["has_receiver"] is False
    assert report["open_items"] == []
    assert report["delivery_decision"] == "blocked"


def test_gate_outcome_summary_counts_unknown_separately(tmp_path):
    report, _ = _build_report(tmp_path, {
        "blocking_ok": {"ok": True, "status": "pass", "severity": "blocking"},
        # 检查器没跑成 = unknown（不得冒充 fail 档的产物不合格）
        "checker_unknown": {"ok": False, "status": "unknown", "severity": "blocking"},
        # 历史事件（P2a 之前）没有 severity 标注
        "legacy_check": {"ok": False},
    })
    summary = report["gate_outcome_summary"]
    assert summary["by_status"]["unknown"] == 1
    assert summary["by_severity"]["unknown"] == 1
    assert summary["status_shares"]["unknown"] > 0
    assert summary["unknown_share"] > 0
    assert summary["total"] == len(report["gate_outcome_details"])
    assert report["gate_outcomes"]["checker_unknown"] == "fail"
    assert report["gate_outcomes"]["legacy_check"] == "fail"
    assert report["delivery_decision"] == "blocked"


# ---------------------------------------------------------------
# P2b-2：接收者判定（静态链 + 交付报告）
# ---------------------------------------------------------------

def test_receiver_of_paper_writing_chain_has_no_receiver(tmp_path):
    steps = resolve_template("paper_writing", {}, CATALOG)
    workflow = {"name": "paper_writing", "metadata": {"params": {}}}
    for step in steps:
        verdict = receiver_of(workflow, step, steps=steps, workspace=tmp_path)
        assert verdict["has_receiver"] is False, step["skill_name"]
        assert verdict["final_audit"]["ok"] is False
        assert verdict["final_review_full_gate"]["ok"] is False
        assert "无接收者" in verdict["reason"]


def test_receiver_of_comp_cumcm_chain_has_final_audit_receiver(tmp_path):
    steps = resolve_template("comp_cumcm", {}, CATALOG)
    workflow = {"name": "comp_cumcm", "metadata": {"params": {}}}
    for step in steps:
        verdict = receiver_of(workflow, step, steps=steps, workspace=tmp_path)
        assert verdict["has_receiver"] is True, step["skill_name"]
        assert verdict["final_audit"]["ok"] is True
    first = receiver_of(workflow, steps[0], steps=steps, workspace=tmp_path)
    assert any(item.startswith("final_audit:") for item in first["receivers"])
    # 终审步骤自身也消费本步 fixable（当前步骤含 final_audit 检查）
    last = receiver_of(workflow, steps[-1], steps=steps, workspace=tmp_path)
    assert last["final_audit"]["ok"] is True


def test_receiver_of_final_review_full_gate_counts(tmp_path):
    steps = [{"name": "solve", "position": 0,
              "metadata": {"required_checks": []}},
             {"name": "comp-final-review", "position": 1,
              "metadata": {"required_checks": ["review"]}}]
    verdict = receiver_of({"name": "custom", "metadata": {}}, "solve",
                          steps=steps, workspace=tmp_path)
    assert verdict["has_receiver"] is True
    assert verdict["final_review_full_gate"]["ok"] is True
    assert any(item.startswith("final_review_full_gate:") for item in verdict["receivers"])


def test_receiver_of_signed_open_items_counts_without_final_audit(tmp_path):
    steps = resolve_template("paper_writing", {}, CATALOG)
    (tmp_path / "DELIVERY_REPORT.json").write_text(json.dumps({
        "open_items": [{"check": "consistency", "signed": True, "signed_by": "reviewer"}]}),
        encoding="utf-8")
    verdict = receiver_of({"name": "paper_writing", "metadata": {}},
                          steps[-1], steps=steps, workspace=tmp_path)
    assert verdict["has_receiver"] is True
    assert verdict["signed_open_items"] == {
        "ok": True, "count": 1, "checks": ["consistency"]}


# ---------------------------------------------------------------
# P2b-2：finish 判定（无接收者 fixable → FAILED；有接收者 → needs_work）
# ---------------------------------------------------------------

def _skill(root: Path, name: str) -> None:
    path = root / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"Task instructions for {name}.", encoding="utf-8")


def _chain_catalog(receiver: bool) -> dict:
    steps = [{
        "skill_name": "solve", "output_files": ["out.txt"],
        "primary_output": "out.txt", "has_checkpoint": False,
        "required_checks": ["consistency"],
        "metadata": {"skill_binding": {"main_required": True},
                     "output_specs": {"out.txt": {"min_bytes": 10}}},
    }]
    if receiver:
        steps.append({
            "skill_name": "comp-final-audit", "output_files": ["AUDIT_REPORT.json"],
            "primary_output": "AUDIT_REPORT.json", "has_checkpoint": False,
            "required_checks": ["final_audit"],
            "metadata": {"required_checks": ["final_audit"],
                         "output_files": ["AUDIT_REPORT.json"]},
        })
    return {"demo": {"sub_steps": steps}}


def _runner_fixture(tmp_path: Path, *, receiver: bool):
    root = tmp_path / "toolbox"
    _skill(root, "solve")
    if receiver:
        _skill(root, "comp-final-audit")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, _chain_catalog(receiver), root / "skills",
                            audit_root=tmp_path)
    workflow = runner.start("demo", tmp_path / "ws", {})
    return store, runner, workflow


def _finish_consistency_failure(tmp_path: Path, *, receiver: bool):
    store, runner, workflow = _runner_fixture(tmp_path, receiver=receiver)
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.write("out.txt", "substantive output " * 20)
    return store, session.finish()


def test_finish_fixable_without_receiver_fails_not_needs_work(tmp_path, monkeypatch):
    monkeypatch.setattr(QualityGate, "check_consistency_evidence",
                        lambda self: {"ok": False, "reason": "一致性报告未通过"})
    store, result = _finish_consistency_failure(tmp_path, receiver=False)
    assert result["status"] == "failed", result["message"]
    diagnostics = result["diagnostics"]
    assert diagnostics["receiver"]["has_receiver"] is False
    assert "quality:consistency" in diagnostics["fixable"]
    assert "quality:consistency" in diagnostics["fixable_blocked"]
    assert diagnostics["fixable_open"] == []
    # 无接收者的 fixable 不进返修轮次/预算（没环节会消费）
    assert store.count_rounds(result["workflow_id"], result["step_id"]) == 0
    assert "一致性报告未通过" in result["message"]
    store.close()


def test_finish_fixable_with_receiver_enters_needs_work(tmp_path, monkeypatch):
    monkeypatch.setattr(QualityGate, "check_consistency_evidence",
                        lambda self: {"ok": False, "reason": "一致性报告未通过"})
    store, result = _finish_consistency_failure(tmp_path, receiver=True)
    assert result["status"] == "needs_work", result["message"]
    diagnostics = result["diagnostics"]
    assert diagnostics["receiver"]["has_receiver"] is True
    assert "quality:consistency" in diagnostics["fixable_open"]
    assert diagnostics["fixable_blocked"] == []
    assert diagnostics["repair_budget"]["total"] == 1
    assert store.count_rounds(result["workflow_id"], result["step_id"]) == 1
    store.close()


def test_finish_mixed_blocking_and_unreceived_fixable_keeps_blocking_repair(tmp_path, monkeypatch):
    """混合失败：原生 blocking 仍可返修；无接收者 fixable 不计入返修预算。"""
    monkeypatch.setattr(QualityGate, "check_consistency_evidence",
                        lambda self: {"ok": False, "reason": "一致性报告未通过"})
    store, runner, workflow = _runner_fixture(tmp_path, receiver=False)
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.write("out.txt", "tiny")  # 低于 output_spec min_bytes → blocking
    result = session.finish()
    assert result["status"] == "needs_work", result["message"]
    diagnostics = result["diagnostics"]
    assert "quality:consistency" in diagnostics["fixable_blocked"]
    assert any(name.startswith("output_spec:") for name in diagnostics["blocking_failures"])
    budget = diagnostics["repair_budget"]
    assert budget["total"] == 1
    # fixable 只在有接收者时计入预算：无接收者时该轮只按 blocking 归档。
    assert budget["by_severity"]["blocking"] == 1
    assert budget["by_severity"]["fixable"] == 0
    store.close()


# ---------------------------------------------------------------
# severity 注册表口径复核（P2b-1 依赖 P2a-7）
# ---------------------------------------------------------------

def test_registry_severity_used_by_audit_matches_runner():
    # advisory / fixable / blocking 三类在终审与 runner 使用同一注册表口径。
    assert resolve_check_severity("ai_flavor") == "advisory"
    assert resolve_check_severity("consistency") == "fixable"
    assert resolve_check_severity("final_audit") == "blocking"
    assert resolve_check_severity("output_spec:main.md") == "blocking"
