"""声明式业务产出合同：结构化返回问题，不打印PASS冒充通过。

B窗 2026-09-26：重点4固化——技能删去的shell验证语义须在合同检查中等价可得；
含新增 min_data_figures（数据图硬底线，承接原 comp-problem-analysis shell 检查）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.output_contracts import check_output_contract


MANIFEST = """<!-- BEGIN FIGURE_MANIFEST -->
**数据图**
- fig_q1_trend
- fig_q2_fit
- fig_q3_compare

**流程图（DrawIO）**
- tikz_flow_overall

**总数：ALL=4**
<!-- END FIGURE_MANIFEST -->
"""


def test_files_min_bytes_and_contains(tmp_path):
    (tmp_path / "RESULTS.md").write_text("# Results\n关键数字 42\n" + "x" * 1200, encoding="utf-8")
    report = check_output_contract(tmp_path, {"files": [
        {"path": "RESULTS.md", "min_bytes": 1024, "contains": ["# Results"]},
        {"path": "$primary", "min_bytes": 10},
    ]}, primary_output="RESULTS.md")
    assert report["ok"], report["errors"]
    (tmp_path / "RESULTS.md").write_text("short", encoding="utf-8")
    report = check_output_contract(tmp_path, {"files": [
        {"path": "RESULTS.md", "min_bytes": 1024, "contains": ["# Results"]}]})
    assert not report["ok"]
    assert any("低于实际合同下限" in e for e in report["errors"])
    (tmp_path / "RESULTS.md").write_text("x" * 1200, encoding="utf-8")
    report = check_output_contract(tmp_path, {"files": [
        {"path": "RESULTS.md", "min_bytes": 1024, "contains": ["# Results"]}]})
    assert not report["ok"]
    assert any("缺内容结构" in e for e in report["errors"])


def test_any_glob_min_count(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "a.json").write_text("{}", encoding="utf-8")
    report = check_output_contract(tmp_path, {"any_glob": [{"patterns": ["figures/*.json"], "min_count": 1}]})
    assert report["ok"]
    report = check_output_contract(tmp_path, {"any_glob": [{"patterns": ["figures/*.json"], "min_count": 2}]})
    assert not report["ok"] and any("缺少产物集合" in e for e in report["errors"])


def test_figure_manifest_prefix_all_and_missing_block(tmp_path):
    (tmp_path / "PROBLEM_ANALYSIS.md").write_text(MANIFEST, encoding="utf-8")
    report = check_output_contract(tmp_path, {"figure_manifest": "PROBLEM_ANALYSIS.md"})
    assert report["ok"], report["errors"]

    bad = MANIFEST.replace("fig_q2_fit", "image2").replace("ALL=4", "ALL=9")
    (tmp_path / "PROBLEM_ANALYSIS.md").write_text(bad, encoding="utf-8")
    report = check_output_contract(tmp_path, {"figure_manifest": "PROBLEM_ANALYSIS.md"})
    assert not report["ok"]
    assert any("前缀" in e or "下游识别规则" in e for e in report["errors"])
    assert any("ALL与实际条目数" in e for e in report["errors"])

    (tmp_path / "PROBLEM_ANALYSIS.md").write_text("no manifest block", encoding="utf-8")
    report = check_output_contract(tmp_path, {"figure_manifest": "PROBLEM_ANALYSIS.md"})
    assert not report["ok"] and any("缺完整FIGURE_MANIFEST" in e for e in report["errors"])


def test_min_data_figures_floor(tmp_path):
    """承接原技能 shell 硬底线：数据图 < 3 即工作不完整（流程图章节不计入）。"""
    (tmp_path / "PROBLEM_ANALYSIS.md").write_text(MANIFEST, encoding="utf-8")
    report = check_output_contract(tmp_path, {"figure_manifest": "PROBLEM_ANALYSIS.md",
                                              "min_data_figures": 3})
    assert report["ok"], report["errors"]
    report = check_output_contract(tmp_path, {"figure_manifest": "PROBLEM_ANALYSIS.md",
                                              "min_data_figures": 4})
    assert not report["ok"]
    assert any("低于合同硬底线" in e for e in report["errors"])
    # 只有流程图的数据规划同样不达底线
    diagram_only = MANIFEST.replace("- fig_q1_trend\n- fig_q2_fit\n- fig_q3_compare\n", "")
    (tmp_path / "PROBLEM_ANALYSIS.md").write_text(diagram_only.replace("ALL=4", "ALL=1"), encoding="utf-8")
    report = check_output_contract(tmp_path, {"figure_manifest": "PROBLEM_ANALYSIS.md",
                                              "min_data_figures": 3})
    assert not report["ok"] and any("规划数据图 0 张" in e for e in report["errors"])


def test_subproblem_outputs_counted_from_report(tmp_path):
    (tmp_path / "MODELING_REPORT.md").write_text(
        "# 建模\n## 问题一\nx\n## 问题二\ny\n", encoding="utf-8")
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "problem1.py").write_text("print(1)", encoding="utf-8")
    report = check_output_contract(tmp_path, {"subproblem_outputs": True})
    assert not report["ok"]
    assert any("problem*.py" in e and "不足" in e for e in report["errors"])
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "problem_1_results.json").write_text("{}", encoding="utf-8")
    report = check_output_contract(tmp_path, {"subproblem_outputs": True})
    assert not report["ok"] and any("problem_*_results.json" in e for e in report["errors"])
    (tmp_path / "code" / "problem2.py").write_text("print(2)", encoding="utf-8")
    (tmp_path / "figures" / "problem_2_results.json").write_text("{}", encoding="utf-8")
    assert check_output_contract(tmp_path, {"subproblem_outputs": True})["ok"]


def test_figure_outputs_data_requires_planned_or_real(tmp_path):
    (tmp_path / "PAPER_PLAN.md").write_text(
        "<!-- BEGIN FIGURE_MANIFEST -->\n**数据图**\n- fig_missing_one\n<!-- END FIGURE_MANIFEST -->\n",
        encoding="utf-8")
    report = check_output_contract(tmp_path, {"figure_outputs": "data"})
    assert not report["ok"] and any("规划产物未生成" in e for e in report["errors"])
    figdir = tmp_path / "figures"
    figdir.mkdir()
    (figdir / "fig_missing_one.png").write_bytes(bytes(range(128, 160)))
    assert check_output_contract(tmp_path, {"figure_outputs": "data"})["ok"]


def test_path_escape_rejected(tmp_path):
    with pytest.raises(ValueError, match="escapes workspace"):
        check_output_contract(tmp_path, {"files": [{"path": "../outside.md"}]})


def test_markdown_deliverable_docx_mode(tmp_path):
    """docx 模式产出合同：阈值原样（≥5120B）、LaTeX 结构命令残留、禁产 .tex 产物。"""
    paper = tmp_path / "paper"
    paper.mkdir()
    good = ("# 论文\n\n正文内容足够长。" * 300
            + "\n\n$$x_{ij}=\\begin{cases} 1 & \\text{如果选择} \\\\ 0 & \\text{否则}\\end{cases}$$\n"
            + "\n正文正常提及 figures/latex_includes.tex 仅作 caption 参考。\n")
    (paper / "main.md").write_text(good, encoding="utf-8")
    contract = {"markdown_deliverable": {"path": "paper/main.md", "min_bytes": 5120,
                                         "latex_residue": True,
                                         "no_tex_artifacts": ["paper/*.tex", "paper/sections/*.tex"]}}
    report = check_output_contract(tmp_path, contract)
    assert report["ok"], report["errors"]

    # LaTeX 文档结构命令残留 → 违规；数学环境命令与 .tex 字样提及不违规
    (paper / "main.md").write_text("x" * 6000 + "\n\\section{模型}\\input{01_a}\n", encoding="utf-8")
    report = check_output_contract(tmp_path, contract)
    assert not report["ok"]
    residue_errors = [e for e in report["errors"] if "残留文档结构类LaTeX命令" in e]
    assert residue_errors and "\\section{" in residue_errors[0]
    assert all("cases" not in e for e in report["errors"]), "数学公式语法不得被误判"

    # docx 模式产出 .tex 产物文件 → 违规；figures/latex_includes.tex 豁免
    (paper / "main.md").write_text(good, encoding="utf-8")
    (paper / "main.tex").write_text("\\documentclass{article}", encoding="utf-8")
    report = check_output_contract(tmp_path, contract)
    assert not report["ok"] and any("禁产.tex产物" in e for e in report["errors"])
    (paper / "main.tex").unlink()
    figdir = tmp_path / "figures"
    figdir.mkdir()
    (figdir / "latex_includes.tex").write_text("caption refs", encoding="utf-8")
    assert check_output_contract(tmp_path, contract)["ok"]

    # 低于现行 5120B 下限 → 违规（阈值不降低）
    (paper / "main.md").write_text("too short", encoding="utf-8")
    report = check_output_contract(tmp_path, contract)
    assert not report["ok"] and any("低于现行下限5120B" in e for e in report["errors"])


def test_errors_are_structured_not_pass_impression(tmp_path):
    report = check_output_contract(tmp_path, {"files": [{"path": "ghost.md", "min_bytes": 100}]})
    assert report["ok"] is False
    assert report["checks"] >= 1
    assert report["errors"] and "ghost.md" in report["reason"]
