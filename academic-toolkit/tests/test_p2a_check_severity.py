"""P2a 检查分级（裁决 6.3-A）：severity 注册表 + 独立 status + 交付档按档位判定。

覆盖：
  ① 15 个唯一检查名全部可解析、十项永不降级受守护；
  ② status(pass/fail/unknown) 与 ok 恒等（ok == status=="pass"），工具缺失/检查异常=unknown；
  ③ 交付档判定矩阵：blocking 挡 / fixable 进 needs_work（legacy 无接收者则 FAILED）/
     fixable+unknown 按 blocking fail-closed / advisory 放行且不回传失败消息；
     explore 档既有 advisory 集合不变。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import quality_gates as qg  # noqa: E402
from engine.agent_bridge import StepResult  # noqa: E402
from engine.quality_gates import (  # noqa: E402
    CHECK_SEVERITY_REGISTRY,
    NEVER_DOWNGRADE_CHECKS,
    TEMPLATE_CHECK_NAMES,
    QualityGate,
    annotate_check_result,
    resolve_check_severity,
    unregistered_check_names,
)
from engine.workflow_runner import WorkflowRunner  # noqa: E402
from engine.workflow_store import WorkflowStore  # noqa: E402


# ---------------------------------------------------------------
# ① 注册表：15 个唯一检查名 + 十项永不降级守护
# ---------------------------------------------------------------

def _template_check_names() -> set[str]:
    catalog = json.loads((ROOT / "engine/modex-core/templates.json").read_text(encoding="utf-8"))
    names: set[str] = set()
    for template in catalog.values():
        for step in template.get("sub_steps") or []:
            names |= set(step.get("required_checks") or [])
            names |= set((step.get("metadata") or {}).get("required_checks") or [])
    return names


def test_registry_covers_all_15_template_check_names():
    names = _template_check_names()
    # 47 模板实测并集：15 个唯一检查名（口径见整改台账 P2a-1）
    assert len(names) == 15, sorted(names)
    assert names == set(TEMPLATE_CHECK_NAMES), sorted(names ^ set(TEMPLATE_CHECK_NAMES))
    # 每个名字都能解析出档位（不是静默默认）
    assert unregistered_check_names(names) == []
    for name in names:
        assert resolve_check_severity(name) in qg.CHECK_SEVERITIES


def test_ten_never_downgrade_checks_are_blocking():
    expected = {
        "protocol", "binding", "review", "final_audit", "step_manifest",
        "assets_usage", "independent_review", "citation_integrity",
        "figure_provenance", "compilation_log",
    }
    assert set(NEVER_DOWNGRADE_CHECKS) == expected
    assert all(CHECK_SEVERITY_REGISTRY[name] == "blocking" for name in NEVER_DOWNGRADE_CHECKS)


def test_guard_rejects_downgraded_never_downgrade(monkeypatch):
    monkeypatch.setitem(qg.CHECK_SEVERITY_REGISTRY, "binding", "advisory")
    with pytest.raises(RuntimeError, match="永不降级"):
        qg._assert_severity_registry()


def test_guard_rejects_missing_template_check_and_invalid_severity(monkeypatch):
    registry = dict(qg.CHECK_SEVERITY_REGISTRY)
    registry.pop("step_manifest")
    monkeypatch.setattr(qg, "CHECK_SEVERITY_REGISTRY", registry)
    with pytest.raises(RuntimeError, match="缺少模板检查名"):
        qg._assert_severity_registry()

    registry = dict(CHECK_SEVERITY_REGISTRY)
    registry["ai_flavor"] = "whatever"
    monkeypatch.setattr(qg, "CHECK_SEVERITY_REGISTRY", registry)
    with pytest.raises(RuntimeError, match="非法档位"):
        qg._assert_severity_registry()


def test_resolve_handles_exact_prefix_families_and_unknown():
    assert resolve_check_severity("step_manifest") == "blocking"
    assert resolve_check_severity("consistency") == "fixable"
    assert resolve_check_severity("ai_flavor") == "advisory"
    # 前缀族：动态产物名与 quality: 归一化
    assert resolve_check_severity("output_spec:main.md") == "blocking"
    assert resolve_check_severity("quality:ai_flavor") == "advisory"
    assert resolve_check_severity("quality:consistency") == "fixable"
    assert resolve_check_severity("quality:never_registered") == "blocking"
    # 未登记 → 默认 blocking，且必须能被列名（不得静默兜底）
    assert resolve_check_severity("never_registered") == "blocking"
    assert unregistered_check_names(
        ["quality:ai_flavor", "output_spec:x.md", "never_registered"]) == ["never_registered"]


# ---------------------------------------------------------------
# ② status 与 ok 恒等；工具缺失/检查异常 = unknown
# ---------------------------------------------------------------

def test_annotate_status_matches_ok_strictly():
    assert annotate_check_result("ai_flavor", {"ok": True})["status"] == "pass"
    failed = annotate_check_result("ai_flavor", {"ok": False})
    assert failed["status"] == "fail" and failed["ok"] is False
    unknown = annotate_check_result("figure_provenance", {"ok": False, "status": "unknown"})
    assert unknown["status"] == "unknown" and unknown["ok"] is False
    assert unknown["action"] == "fix_tool"
    # ok 缺失/非布尔 → unknown（fail-closed，不冒充通过）
    missing = annotate_check_result("protocol", {"reason": "no verdict"})
    assert missing["status"] == "unknown" and missing["ok"] is False
    # 历史非规范 status（评审轮次里的工作流状态）不得被误当 pass/fail
    legacy = annotate_check_result("review_rounds", {"ok": True, "status": "completed"})
    assert legacy["status"] == "unknown" and legacy["ok"] is False
    assert legacy["status_detail"] == "completed"


def test_run_all_annotates_every_check_and_keeps_ok_invariant(tmp_path):
    report = QualityGate(tmp_path).run_all("demo-skill")
    assert report["checks"]
    for name, check in report["checks"].items():
        assert check["status"] in qg.CHECK_STATUSES, name
        assert check["severity"] in qg.CHECK_SEVERITIES, name
        assert check["ok"] == (check["status"] == "pass"), name


def test_pillow_missing_makes_figure_health_unknown(tmp_path, monkeypatch):
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "a.png").write_bytes(b"not actually an image")
    monkeypatch.setitem(sys.modules, "PIL", None)  # 模拟工具缺席
    check = QualityGate(tmp_path).run_all("demo", requires_figures=True)["checks"]["figures"]
    assert check["status"] == "unknown"
    assert check["ok"] is False
    assert check["action"] == "fix_tool"


def test_checker_exception_becomes_unknown_not_product_failure(tmp_path, monkeypatch):
    def boom(self):
        raise TypeError("tool exploded")

    monkeypatch.setattr(QualityGate, "check_step_manifest", boom)
    report = QualityGate(tmp_path).run_all("demo", required_checks=["step_manifest"])
    check = report["checks"]["step_manifest"]
    assert check["status"] == "unknown"
    assert check["ok"] is False
    assert check["action"] == "fix_tool"
    assert "unknown" in check["reason"]


def test_ai_flavor_tool_missing_is_unknown(tmp_path, monkeypatch):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.tex").write_text("正文内容。" * 200, encoding="utf-8")
    monkeypatch.setattr(qg, "PROJECT_ROOT", tmp_path / "no-such-root")
    check = QualityGate(tmp_path).check_ai_flavor()
    assert check["status"] == "unknown" and check["ok"] is False


# ---------------------------------------------------------------
# ③ 交付档判定矩阵 / explore 现状保留
# ---------------------------------------------------------------

def _catalog(required_checks, output_specs=None):
    return {"demo": {"sub_steps": [{
        "skill_name": "solve", "output_files": ["out.txt"], "primary_output": "out.txt",
        "has_checkpoint": False, "required_checks": list(required_checks),
        "output_specs": output_specs or {},
    }]}}


def _skills(tmp_path):
    skill = tmp_path / "skills" / "solve"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("fixture skill", encoding="utf-8")
    return tmp_path / "skills"


def _report(action):
    for output in action.output_files:
        path = action.workspace / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture result\n" * 200, encoding="utf-8")
    from engine.step_manifest import write_manifest
    write_manifest(
        workspace=action.workspace, step_name=action.skill_name, config={},
        outputs=[action.workspace / name for name in action.output_files],
        backend="test-backend 1.0",
        commands=[{"command": "python generate.py", "exitCode": 0}],
        dependencies={},
    )
    return StepResult(
        ok=True, artifacts=list(action.output_files), step_id=action.step_id,
        attempt_id=action.attempt_id, expected_revision=action.expected_revision,
        metadata={"execution_evidence": {
            "schema_version": 1, "agent": "test-runner", "step_id": action.step_id,
            "skill_name": action.skill_name, "skill_sha256": action.skill_sha256,
            "commands": [{"command": "python generate.py", "returncode": 0, "cwd": "."}],
            "inputs": [], "outputs": list(action.output_files),
        }})


def _complete_delivery(tmp_path, required_checks):
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, _catalog(required_checks), _skills(tmp_path))
        workflow = runner.start("demo", tmp_path / "workspace", {})
        action = runner.next_action(workflow.id).action
        return runner.complete_step(workflow.id, _report(action))


def test_delivery_advisory_failure_passes_and_is_not_echoed(tmp_path, monkeypatch):
    monkeypatch.setattr(QualityGate, "check_ai_flavor",
                        lambda self: {"ok": False, "reason": "AI 痕迹超阈值"})
    result = _complete_delivery(tmp_path, ["ai_flavor"])
    assert result.status == "completed", result.message
    diagnostics = result.diagnostics
    assert "quality:ai_flavor" in diagnostics["advisories"]
    assert diagnostics["checks"]["quality:ai_flavor"]["severity"] == "advisory"
    assert diagnostics["checks"]["quality:ai_flavor"]["status"] == "fail"
    # advisory 不回传失败消息
    assert "AI 痕迹超阈值" not in result.message


def test_delivery_fixable_failure_blocks_without_receiver(tmp_path, monkeypatch):
    """fixable 失败必须进不了 completed：legacy complete 没有 P2b 接收者 → FAILED。"""
    monkeypatch.setattr(QualityGate, "check_consistency_evidence",
                        lambda self: {"ok": False, "reason": "一致性报告未通过"})
    result = _complete_delivery(tmp_path, ["consistency"])
    assert result.status == "failed", result.message
    assert "quality:consistency" in result.diagnostics["fixable"]
    assert result.diagnostics["checks"]["quality:consistency"]["severity"] == "fixable"
    assert result.diagnostics["failure_kind"] == "validation_failed"
    # fixable 已阻断本步：理由必须回传，不能静默失败
    assert "一致性报告未通过" in result.message


def test_delivery_fixable_unknown_fails_closed(tmp_path, monkeypatch):
    """反向用例：可返修判据的检查器抛异常（unknown）不得当「可返修」放行。"""
    def boom(self):
        raise TypeError("溯源工具不可用")

    monkeypatch.setattr(QualityGate, "check_consistency_evidence", boom)
    result = _complete_delivery(tmp_path, ["consistency"])
    assert result.status == "failed", result.message
    check = result.diagnostics["checks"]["quality:consistency"]
    assert check["status"] == "unknown" and check["ok"] is False
    assert check["action"] == "fix_tool"
    assert "quality:consistency" in result.diagnostics["blocking_failures"]
    assert "quality:consistency" not in result.diagnostics["fixable"]


def test_delivery_blocking_failure_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(QualityGate, "check_citation_integrity",
                        lambda self: {"ok": False, "reason": "bib 条目缺失"})
    result = _complete_delivery(tmp_path, ["citation_integrity"])
    assert result.status == "failed"
    assert "quality:citation_integrity" in result.diagnostics["blocking_failures"]
    assert "bib 条目缺失" in result.message


def test_delivery_blocking_unknown_fails_closed(tmp_path, monkeypatch):
    def boom(self):
        raise TypeError("溯源工具不可用")

    monkeypatch.setattr(QualityGate, "check_figure_provenance", boom)
    result = _complete_delivery(tmp_path, ["figure_provenance"])
    assert result.status == "failed"
    check = result.diagnostics["checks"]["quality:figure_provenance"]
    assert check["status"] == "unknown" and check["ok"] is False
    assert "unknown" in result.message


def test_delivery_advisory_unknown_does_not_block(tmp_path, monkeypatch):
    def boom(self):
        raise TypeError("叙述工具不可用")

    monkeypatch.setattr(QualityGate, "check_figure_narrative", boom)
    result = _complete_delivery(tmp_path, ["figure_narrative"])
    assert result.status == "completed", result.message
    assert result.diagnostics["checks"]["quality:figure_narrative"]["status"] == "unknown"


def test_explore_advisory_set_is_unchanged(tmp_path):
    # explore 档现状保留：output_spec 失败仍只留痕，advisories 集合与改造前一致
    catalog = _catalog([], {"out.txt": {"min_bytes": 10_000_000, "rationale": "advisory fixture"}})
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, _skills(tmp_path))
        workflow = runner.start("demo", tmp_path / "workspace", {}, mode="explore")
        action = runner.next_action(workflow.id).action
        result = runner.complete_step(workflow.id, _report(action))
    assert result.status == "completed", result.message
    assert result.diagnostics["advisories"] == ["output_spec:out.txt"]
    assert result.diagnostics["fixable"] == []


def test_explore_binding_failure_stays_hard(tmp_path):
    """NEVER_DOWNGRADE 项在 explore 路径也不得降级为 advisory（空声明/无痕即失败）。"""
    catalog = {"demo": {"sub_steps": [{
        "skill_name": "solve", "output_files": ["out.txt"], "primary_output": "out.txt",
        "has_checkpoint": False, "required_checks": [],
        "metadata": {"skill_binding": {"main_required": True, "main": "solve"}},
    }]}}
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, _skills(tmp_path))
        workflow = runner.start("demo", tmp_path / "workspace", {}, mode="explore")
        action = runner.next_action(workflow.id).action
        result = runner.complete_step(workflow.id, _report(action))
    assert result.status == "failed", result.message
    check = result.diagnostics["checks"]["binding"]
    assert check["severity"] == "blocking"
    assert "binding" in result.diagnostics["blocking_failures"]
    assert "binding" not in result.diagnostics["advisories"]
