"""P3 闸门下沉：六个重灾区技能的命名闸门 → 引擎检查器（active/blocking）。

覆盖：
  ① 注册表完整性：(template, step) 键与 templates.json 对得上、实现存在、档位一致、
     active 必须 blocking、fix_hint/单跑命令/遗留人工项在位；
  ② 每个新检查器的正/反用例（paper_final_gate / result_sanity_check /
     figure_plan_reconciliation / modeling_machine_contract / paper_write_gate）；
  ③ run_all 按 (template, step) 自动挂载，且经 finish 时 blocking 生效；
  ④ CLI 单跑退出码 0/1/3 与注册名解析。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.agent_bridge import StepResult  # noqa: E402
from engine.quality_gates import (  # noqa: E402
    QualityGate,
    auto_checks_for,
    find_checker,
    load_checker_registry,
    resolve_check_severity,
    validate_checker_registry,
)
from engine.workflow_runner import WorkflowRunner  # noqa: E402
from engine.workflow_store import WorkflowStore  # noqa: E402

REGISTRY = load_checker_registry()
ENTRIES = {entry["name"]: entry for entry in REGISTRY["checkers"]}
EXPECTED_CHECKERS = {
    "paper_final_gate", "result_sanity_check", "figure_plan_reconciliation",
    "modeling_machine_contract", "paper_write_gate", "paper_scoring_contract",
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


# ---------------------------------------------------------------
# ① 注册表完整性
# ---------------------------------------------------------------

def test_registry_has_five_active_blocking_checkers_with_pair_keys():
    assert set(ENTRIES) == EXPECTED_CHECKERS
    assert validate_checker_registry(REGISTRY, implementations=set(dir(QualityGate))) == []
    for name, entry in ENTRIES.items():
        assert entry["severity"] == "blocking", name
        assert entry["stage"] == "active", name
        assert resolve_check_severity(name) == "blocking", name
        assert entry["fix_hint"].strip(), name
        assert entry["single_run"].strip(), name
        assert entry["manual_items"], name
        for rule in entry["applies_to"]:
            # (template, step) 键，不允许 per-skill 通配
            assert set(rule) == {"template", "step"}, (name, rule)


def test_registry_source_refs_resolve_to_existing_sections():
    """source_ref 用章节锚点而非行号：技能正文裁剪后必须仍能定位到真实章节。"""
    for name, entry in ENTRIES.items():
        refs = [part.strip() for part in entry["source_ref"].split(";") if part.strip()]
        assert refs, name
        for ref in refs:
            path_text, _, anchor = ref.partition(" § ")
            assert anchor.strip(), f"{name}: source_ref 缺章节锚点 {ref}"
            skill_file = ROOT / path_text.strip()
            assert skill_file.is_file(), f"{name}: source_ref 文件不存在 {path_text}"
            assert anchor.strip() in skill_file.read_text(encoding="utf-8"), (
                f"{name}: source_ref 章节锚点不在 {path_text} 中: {anchor}")


def test_registry_applies_to_matches_real_templates_and_steps():
    templates = json.loads((ROOT / "engine/modex-core/templates.json").read_text(encoding="utf-8"))
    for name, entry in ENTRIES.items():
        for rule in entry["applies_to"]:
            template, step = rule["template"], rule["step"]
            assert template in templates, f"{name}: 未知模板 {template}"
            steps = {s.get("skill_name") for s in templates[template].get("sub_steps", [])}
            assert step in steps, f"{name}: {template} 没有步骤 {step}"


def test_registry_covers_every_template_using_the_six_skills():
    """反向对账：模板里出现的六个重灾区步骤都必须有引擎检查器挂载，防静默漏挂。"""
    primary = {
        "paper-compile": "paper_final_gate",
        "paper-analysis": "result_sanity_check",
        "paper-figure-drawio": "figure_plan_reconciliation",
        "paper-write-zh": "paper_write_gate",
        "comp-modeling": "modeling_machine_contract",
        "comp-paper-zh": "result_sanity_check",
    }
    templates = json.loads((ROOT / "engine/modex-core/templates.json").read_text(encoding="utf-8"))
    holes = []
    for template, spec in templates.items():
        for step in spec.get("sub_steps", []):
            skill = step.get("skill_name")
            checker = primary.get(skill)
            if not checker:
                continue
            if checker not in {e["name"] for e in auto_checks_for(template, skill)}:
                holes.append(f"{template}/{skill} → {checker}")
    assert not holes, f"未挂载引擎检查器的步骤: {holes}"


def test_registry_guard_rejects_broken_entries():
    registry = json.loads(json.dumps(REGISTRY))
    registry["checkers"][0]["implementation"] = "check_does_not_exist"
    registry["checkers"][0]["severity"] = "blocking"
    registry["checkers"][0]["stage"] = "shadow"  # shadow 不得阻断
    registry["checkers"][0]["applies_to"] = ["paper-compile"]
    registry["checkers"][0]["manual_items"] = []
    problems = validate_checker_registry(
        registry, implementations=set(dir(QualityGate)))
    assert any("实现" in p and "不存在" in p for p in problems), problems
    assert any("shadow" in p for p in problems), problems
    assert any("(template, step)" in p for p in problems), problems
    assert any("遗留人工项" in p for p in problems), problems
    # active 却登记 advisory = 静默降级，同样拒绝
    downgraded = json.loads(json.dumps(REGISTRY))
    downgraded["checkers"][0]["severity"] = "advisory"
    downgraded["checkers"][0]["stage"] = "active"
    problems = validate_checker_registry(
        downgraded, implementations=set(dir(QualityGate)))
    assert any("active" in p and "blocking" in p for p in problems), problems


def test_registry_missing_file_is_empty_not_crash(tmp_path):
    assert load_checker_registry(tmp_path / "absent.json")["checkers"] == []


def test_auto_checks_for_uses_template_step_pair():
    assert [e["name"] for e in auto_checks_for("paper_writing", "paper-compile")] == ["paper_final_gate"]
    assert [e["name"] for e in auto_checks_for("comp_cumcm", "comp-paper-zh")] == [
        "result_sanity_check", "paper_scoring_contract"]
    assert [e["name"] for e in auto_checks_for("comp_cumcm", "comp-modeling")] == ["modeling_machine_contract"]
    assert {e["name"] for e in auto_checks_for("paper_writing_zh", "paper-write-zh")} == {
        "figure_plan_reconciliation", "paper_write_gate"}
    assert [e["name"] for e in auto_checks_for("comp_cumcm", "paper-figure-drawio")] == ["figure_plan_reconciliation"]
    # 同名步骤在未登记模板下不挂载（防止 per-skill 通配折叠模板差异）
    assert auto_checks_for("demo", "paper-compile") == []
    assert auto_checks_for("paper_writing", "comp-modeling") == []
    assert find_checker("check_result_sanity_check")["name"] == "result_sanity_check"
    assert find_checker("not_registered") is None


# ---------------------------------------------------------------
# ②a paper_final_gate（paper-compile Step 7）
# ---------------------------------------------------------------

def _clean_paper_workspace(ws: Path) -> None:
    _write(ws / "paper/main.tex",
           "\\documentclass{article}\n\\begin{document}\n\\cite{demo}\n"
           "\\includegraphics{fig_a.pdf}\n\\end{document}\n")
    _write_bytes(ws / "paper/main.pdf", b"%PDF-1.4\n" + b"0" * 60000)
    _write(ws / "paper/main.log", "This is pdfTeX\nOutput written on main.pdf (1 page).\n")
    _write(ws / "paper/main.bbl",
           "\\begin{thebibliography}{1}\n\\bibitem{demo} Demo entry.\n\\end{thebibliography}\n")
    _write(ws / "paper/sections/1_intro.tex",
           ("本文给出一个可复现的建模与求解过程，结果见图 fig_a.pdf。\n" * 40))
    _write_bytes(ws / "figures/fig_a.pdf", b"%PDF-1.4\n")
    _write(ws / "RESULTS.md", "# 结果\n\n## 合理性审查\n\n结果与物理约束一致。\n")


def test_paper_final_gate_positive(tmp_path):
    _clean_paper_workspace(tmp_path)
    result = QualityGate(tmp_path).check_paper_final_gate()
    assert result["status"] == "pass", result["reason"]
    assert result["ok"] is True
    assert result["violations"] == []


def test_paper_final_gate_negative_collects_each_gate_item(tmp_path):
    _clean_paper_workspace(tmp_path)
    # 未嵌入图 / 占位符 / itemize / 数学错误 / bib 为空
    _write_bytes(tmp_path / "figures/fig_orphan.pdf", b"%PDF-1.4\n")
    _write(tmp_path / "paper/sections/2_body.tex",
           "PLACEHOLDER\n\\begin{itemize}\\item x\\end{itemize}\n")
    _write(tmp_path / "paper/main.log",
           "! Missing $ inserted\nOverfull \\vbox (12.0pt too high)\n")
    (tmp_path / "paper/main.bbl").unlink()
    result = QualityGate(tmp_path).check_paper_final_gate()
    joined = " ".join(result["violations"])
    assert result["status"] == "fail" and result["ok"] is False
    assert "unembedded" in joined and "fig_orphan.pdf" in joined
    assert "placeholders" in joined
    assert "itemize" in joined
    assert "math errors" in joined
    assert "Bib empty" in joined
    # 不可程序化的项必须进 manual_items，而不是硬造判据
    assert any("视觉" in item for item in ENTRIES["paper_final_gate"]["manual_items"])


def test_paper_final_gate_unembedded_figure_then_embedded_passes(tmp_path):
    # P3-3 验收口径：故意留一张未嵌入图 → fail；补 includegraphics 后同命令 pass
    _clean_paper_workspace(tmp_path)
    _write_bytes(tmp_path / "figures/fig_late.pdf", b"%PDF-1.4\n")
    first = QualityGate(tmp_path).check_paper_final_gate()
    assert first["status"] == "fail"
    assert any("fig_late.pdf" in item for item in first["violations"])
    _write(tmp_path / "paper/sections/1_intro.tex",
           ("正文见图 fig_a.pdf。\n" * 40) + "\\includegraphics{fig_late.pdf}\n")
    second = QualityGate(tmp_path).check_paper_final_gate()
    assert second["status"] == "pass", second["reason"]


def test_paper_final_gate_missing_log_is_unknown_not_pass(tmp_path):
    _clean_paper_workspace(tmp_path)
    (tmp_path / "paper/main.log").unlink()
    result = QualityGate(tmp_path).check_paper_final_gate()
    assert result["status"] == "unknown" and result["ok"] is False
    assert any("main.log" in item for item in result["unverified"])


def test_paper_final_gate_numeric_and_claims(tmp_path):
    _clean_paper_workspace(tmp_path)
    _write(tmp_path / "figures/all_results.json",
           json.dumps({"model": {"accuracy": 0.9321, "rmse": 0.1234, "f1": 0.8877,
                                 "auc": 0.9012, "precision": 0.8654, "recall": 0.8432}}))
    _write(tmp_path / "PAPER_PLAN.md",
           "| Claim | Evidence |\n|---|---|\n"
           "| 本文提出注意力融合框架用于长序列预测 | fig_a |\n")
    result = QualityGate(tmp_path).check_paper_final_gate()
    assert any("key values not found" in v for v in result["violations"])
    assert any("planned claims not covered" in v for v in result["violations"])
    # 补上数值与 claims 关键词后通过
    _write(tmp_path / "paper/sections/1_intro.tex",
           ("准确率 0.9321，RMSE 0.1234，F1 0.8877，AUC 0.9012，precision 0.8654，"
            "recall 0.8432；本文提出注意力融合框架用于长序列预测。\n" * 30)
           + "\\includegraphics{fig_a.pdf}\n")
    fixed = QualityGate(tmp_path).check_paper_final_gate()
    assert fixed["status"] == "pass", fixed["reason"]


# ---------------------------------------------------------------
# ②b result_sanity_check（paper-analysis Step 6 / 结果约束审计）
# ---------------------------------------------------------------

def test_result_sanity_check_positive(tmp_path):
    _write(tmp_path / "figures/all_results.json",
           json.dumps({"model": {"accuracy": 0.93, "rmse": 0.12}}))
    _write(tmp_path / "RESULTS.md",
           "# 结果\n\n<!-- AUDIT_OK source=results.json rechecked_at=2026-10-25T10:00:00 "
           "n_constraints=3 -->\n")
    result = QualityGate(tmp_path).check_result_sanity_check()
    assert result["status"] == "pass", result["reason"]
    assert result["checked_files"] == 1


def test_result_sanity_check_negative_hard_errors(tmp_path):
    _write(tmp_path / "figures/all_results.json", json.dumps({
        "model": {"rmse": -0.1, "r2": 0.2, "p_value": 1.5}}))
    _write(tmp_path / "RESULTS.md", "# 结果\n\n没有审计凭证。\n")
    result = QualityGate(tmp_path).check_result_sanity_check()
    joined = " ".join(result["errors"])
    assert result["status"] == "fail"
    assert "误差不应为负" in joined
    assert "R² < 0.5" in joined
    assert "p 值 > 1" in joined
    assert "AUDIT_OK" in joined


def test_result_sanity_check_detects_nan_and_stale_versions(tmp_path):
    _write(tmp_path / "figures/all_results.json", '{"model": {"accuracy": NaN}}')
    _write(tmp_path / "RESULTS.md",
           "<!-- AUDIT_OK source=x.json rechecked_at=now -->\n")
    _write(tmp_path / "results_old.json", "{}")
    result = QualityGate(tmp_path).check_result_sanity_check()
    assert any("NaN/Inf" in error for error in result["errors"])
    assert "results_old.json" in result["stale_files"]


def test_result_sanity_check_no_inputs_is_unknown(tmp_path):
    result = QualityGate(tmp_path).check_result_sanity_check()
    assert result["status"] == "unknown" and result["ok"] is False


# ---------------------------------------------------------------
# ②c figure_plan_reconciliation（paper-figure-drawio Step 6 / FIGURE_MANIFEST）
# ---------------------------------------------------------------

MANIFEST = """<!-- BEGIN FIGURE_MANIFEST -->
**数据图**
- fig_curve
**架构流程图（DrawIO）**
- fig_flow
**TikZ 几何图**
- tikz_geom
<!-- END FIGURE_MANIFEST -->
"""


def test_figure_plan_reconciliation_positive_and_skip(tmp_path):
    # 无规划合同 → 跳过（不硬造判据）
    skipped = QualityGate(tmp_path).check_figure_plan_reconciliation()
    assert skipped["ok"] is True and skipped.get("skipped") is True
    _write(tmp_path / "PAPER_PLAN.md", "# 规划\n\n" + MANIFEST)
    _write_bytes(tmp_path / "figures/fig_curve.pdf", b"%PDF-1.4\n")
    _write_bytes(tmp_path / "figures/fig_flow.pdf", b"%PDF-1.4\n")
    _write(tmp_path / "figures/fig_flow.drawio", "<mxGraphModel/>\n")
    _write_bytes(tmp_path / "figures/tikz_geom.pdf", b"%PDF-1.4\n")
    _write(tmp_path / "figures/tikz_geom.tex", "\\begin{tikzpicture}\\end{tikzpicture}\n")
    _write(tmp_path / "paper/sections/1_intro.tex",
           "\\includegraphics{fig_curve.pdf}\\includegraphics{fig_flow.pdf}"
           "\\includegraphics{tikz_geom.pdf}\n")
    result = QualityGate(tmp_path).check_figure_plan_reconciliation()
    assert result["status"] == "pass", result["reason"]
    assert result["planned"] == 3


def test_figure_plan_reconciliation_negative(tmp_path):
    _write(tmp_path / "PAPER_PLAN.md", "# 规划\n\n" + MANIFEST)
    _write_bytes(tmp_path / "figures/fig_curve.pdf", b"%PDF-1.4\n")
    _write_bytes(tmp_path / "figures/fig_flow.pdf", b"%PDF-1.4\n")  # 缺 .drawio
    _write_bytes(tmp_path / "figures/tikz_geom.pdf", b"%PDF-1.4\n")
    _write(tmp_path / "figures/tikz_geom.tex", "x")
    _write(tmp_path / "paper/sections/1_intro.tex", "no refs\n")
    result = QualityGate(tmp_path).check_figure_plan_reconciliation()
    joined = " ".join([result["reason"]])
    assert result["status"] == "fail"
    assert result["missing_sources"] == ["fig_flow"]
    assert set(result["unembedded"]) == {"fig_curve", "fig_flow", "tikz_geom"}
    assert "未嵌入正文" in joined


def test_figure_plan_reconciliation_drawio_marker_fallback(tmp_path):
    # 无 FIGURE_MANIFEST 时按 DrawIO-N 规划行兼容（paper-figure-drawio Step 6 原口径）
    _write(tmp_path / "PROBLEM_ANALYSIS.md", "- DrawIO-1: 技术路线图 fig_roadmap\n")
    missing = QualityGate(tmp_path).check_figure_plan_reconciliation()
    assert missing["status"] == "fail"
    assert missing["missing_files"] == ["fig_roadmap"]
    _write_bytes(tmp_path / "figures/fig_roadmap.pdf", b"%PDF-1.4\n")
    _write(tmp_path / "figures/fig_roadmap.drawio", "<mxGraphModel/>\n")
    _write(tmp_path / "paper/sections/1_intro.tex", "\\includegraphics{fig_roadmap.pdf}\n")
    fixed = QualityGate(tmp_path).check_figure_plan_reconciliation()
    assert fixed["status"] == "pass", fixed["reason"]


# ---------------------------------------------------------------
# ②d modeling_machine_contract（comp-modeling Step 5.5）
# ---------------------------------------------------------------

def test_modeling_machine_contract_positive(tmp_path):
    _write(tmp_path / "MODELING_REPORT.md", """# 建模报告

针对能力 P1-C1 事件抽取，采用序列标注模型。

<!-- METHOD_CLAIMS_MACHINE
M1 | must: LpInteger, cat=.Integer | forbid: linprog
-->

```json
{"LOGIC_CONTRACT_MACHINE": {"bounds": [{"quantity": "x", "is": "upper"}]}}
```
""")
    _write(tmp_path / "CAPABILITY_CHECKLIST.json",
           json.dumps({"capabilities": [{"id": "P1-C1", "name": "事件抽取"}]}))
    result = QualityGate(tmp_path).check_modeling_machine_contract()
    assert result["status"] == "pass", result["reason"]
    assert result["capability_missing"] == []


def test_modeling_machine_contract_negative(tmp_path):
    _write(tmp_path / "MODELING_REPORT.md", "# 建模报告\n\n没有机器合同块。\n")
    _write(tmp_path / "CAPABILITY_CHECKLIST.json",
           json.dumps({"capabilities": [{"id": "P2-C9", "name": "缺失能力"}]}))
    result = QualityGate(tmp_path).check_modeling_machine_contract()
    joined = " ".join(result["violations"])
    assert result["status"] == "fail"
    assert "METHOD_CLAIMS_MACHINE" in joined
    assert "LOGIC_CONTRACT_MACHINE" in joined
    assert result["capability_missing"] == ["P2-C9"]


def test_modeling_machine_contract_requires_must_signature(tmp_path):
    _write(tmp_path / "MODELING_REPORT.md", """# 建模

<!-- METHOD_CLAIMS_MACHINE
M1 | forbid: linprog
-->

```json
{"LOGIC_CONTRACT_MACHINE": {"bounds": []}}
```
""")
    result = QualityGate(tmp_path).check_modeling_machine_contract()
    assert result["status"] == "fail"
    assert any("must" in v for v in result["violations"])


# ---------------------------------------------------------------
# ②e paper_write_gate（paper-write-zh 完成铁律 / 摘要 / 页数）
# ---------------------------------------------------------------

def test_paper_write_gate_positive_pdf(tmp_path):
    _write(tmp_path / "paper/main.tex", "\\documentclass{article}\n" + "% 模板\n" * 800)
    _write(tmp_path / "paper/references.bib", "@article{demo, title={Demo}, author={A}}\n")
    _write(tmp_path / "paper/sections/0_abstract.tex", "摘要：准确率 0.95，误差 0.12。" + "内容" * 300)
    _write(tmp_path / "paper/sections/1_intro.tex", "正文准确率 0.95，误差 0.12。" + "内容" * 300)
    _write(tmp_path / ".env_skill", "MAX_PAGES=1\n")
    result = QualityGate(tmp_path).check_paper_write_gate()
    assert result["status"] == "pass", result["reason"]
    assert result["mode"] == "pdf"
    assert result["counts"]["abstract_numbers_unverified"] == 0


def test_paper_write_gate_negative_fabricated_abstract_number(tmp_path):
    _write(tmp_path / "paper/main.tex", "\\documentclass{article}\n" + "% 模板\n" * 800)
    _write(tmp_path / "paper/references.bib", "@article{demo, title={Demo}, author={A}}\n")
    _write(tmp_path / "paper/sections/0_abstract.tex", "摘要：准确率 0.95，提升 9.87。" + "内容" * 200)
    _write(tmp_path / "paper/sections/1_intro.tex", "正文准确率 0.95。" + "内容" * 300)
    result = QualityGate(tmp_path).check_paper_write_gate()
    joined = " ".join(result["violations"])
    assert result["status"] == "fail"
    assert "9.87@0_abstract.tex" in joined


def test_paper_write_gate_docx_mode(tmp_path):
    _write(tmp_path / "paper/main.md", "# 论文\n" + "正文内容。" * 1200)
    result = QualityGate(tmp_path).check_paper_write_gate()
    assert result["status"] == "pass" and result["mode"] == "docx"


# ---------------------------------------------------------------
# ②f paper_scoring_contract（true 链九维评分件解析）
# ---------------------------------------------------------------

def test_paper_scoring_contract_positive_and_negative(tmp_path):
    _write(tmp_path / "PAPER_SCORING.json", json.dumps({
        "scores": {f"dim_{index}": {"score": 4, "evidence": f"§{index}"}
                   for index in range(9)},
        "weighted_total": 4.0,
        "fatal_dimensions": [],
        "selfcheck_failures": [],
    }, ensure_ascii=False))
    passed = QualityGate(tmp_path).check_paper_scoring_contract()
    assert passed["status"] == "pass" and passed["dimension_count"] == 9

    _write(tmp_path / "PAPER_SCORING.json", "{}")
    empty = QualityGate(tmp_path).check_paper_scoring_contract()
    assert empty["status"] == "fail"
    assert any("scores" in v for v in empty["violations"])

    _write(tmp_path / "PAPER_SCORING.json", "{not json")
    malformed = QualityGate(tmp_path).check_paper_scoring_contract()
    assert malformed["status"] == "fail" and "不可解析" in malformed["reason"]

    (tmp_path / "PAPER_SCORING.json").unlink()
    missing = QualityGate(tmp_path).check_paper_scoring_contract()
    assert missing["status"] == "fail" and "缺失" in missing["reason"]


# ---------------------------------------------------------------
# ③ run_all 自动挂载 + finish 只留痕不阻断
# ---------------------------------------------------------------

def test_run_all_auto_mounts_checker_for_template_step_pair(tmp_path):
    _clean_paper_workspace(tmp_path)
    report = QualityGate(tmp_path).run_all("paper-compile", template_name="paper_writing")
    check = report["checks"]["paper_final_gate"]
    assert check["severity"] == "blocking"
    assert check["status"] in {"pass", "fail", "unknown"}
    assert check["fix_hint"] and check["single_run"]
    assert "paper_final_gate" not in QualityGate(tmp_path).run_all(
        "paper-compile", template_name="demo")["checks"]


def test_missing_checker_registry_blocks_delivery(tmp_path, monkeypatch):
    """注册表文件缺失 = 安装损坏：不得静默返回空表让 P3 检查器整体消失。"""
    import engine.quality_gates as qg
    monkeypatch.setattr(qg, "CHECKER_REGISTRY_PATH", tmp_path / "absent-registry.json")
    report = QualityGate(tmp_path).run_all("paper-compile", template_name="paper_writing")
    check = report["checks"]["checker_registry"]
    assert check["severity"] == "blocking"
    assert check["status"] == "unknown" and check["ok"] is False
    assert check["action"] == "fix_tool"
    assert "absent-registry.json" in check["reason"]


def _catalog(template_name: str) -> dict:
    return {template_name: {"sub_steps": [{
        "skill_name": "paper-compile", "output_files": ["out.txt"],
        "primary_output": "out.txt", "has_checkpoint": False,
        "required_checks": [],
    }]}}


def _skills(tmp_path: Path) -> Path:
    skill = tmp_path / "skills" / "paper-compile"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("fixture skill", encoding="utf-8")
    return tmp_path / "skills"


def _report(action) -> StepResult:
    for output in action.output_files:
        path = action.workspace / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture result\n" * 2000, encoding="utf-8")
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


def test_finish_blocks_on_paper_final_gate_failure(tmp_path):
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, _catalog("paper_writing"), _skills(tmp_path))
        workflow = runner.start("paper_writing", tmp_path / "workspace", {})
        action = runner.next_action(workflow.id).action
        result = runner.complete_step(workflow.id, _report(action))
    assert result.status == "failed", result.message
    check = result.diagnostics["checks"]["quality:paper_final_gate"]
    assert check["severity"] == "blocking"
    assert check["status"] == "fail"  # 空工作区：PDF 缺失等
    assert "quality:paper_final_gate" in result.diagnostics["blocking_failures"]
    assert "quality:paper_final_gate" not in result.diagnostics["advisories"]


# ---------------------------------------------------------------
# ④ CLI 单跑（fix_hint 里的单跑命令真实可执行）
# ---------------------------------------------------------------

def _cli(workspace: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "engine" / "quality_gates.py"), "gate",
         str(workspace), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def test_cli_single_run_exit_codes(tmp_path):
    _write(tmp_path / "figures/all_results.json",
           json.dumps({"model": {"accuracy": 0.93}}))
    _write(tmp_path / "RESULTS.md",
           "<!-- AUDIT_OK source=results.json rechecked_at=now -->\n")
    passed = _cli(tmp_path, "--check", "result_sanity_check")
    assert passed.returncode == 0, passed.stdout + passed.stderr
    assert json.loads(passed.stdout)["status"] == "pass"

    _write(tmp_path / "figures/all_results.json", json.dumps({"model": {"rmse": -1.0}}))
    failed = _cli(tmp_path, "--check", "check_result_sanity_check")
    assert failed.returncode == 1, failed.stdout + failed.stderr

    unknown = _cli(tmp_path, "--check", "not_a_checker")
    assert unknown.returncode == 3
    assert json.loads(unknown.stdout)["status"] == "unknown"
