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


def test_files_forbidden_blocks_skeleton_delivery(tmp_path):
    # 2026-10-02 内容级合同：forbidden 查骨架占位残留（min_bytes 挡不住骨架原样交付）
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.tex").write_text(
        "\baominghao{[参赛队号]}\n针对问题一，求得最优解 3.14（创新点：分层解耦）。\n" + "x" * 6000,
        encoding="utf-8")
    contract = {"files": [{"path": "paper/main.tex", "min_bytes": 5120,
                           "contains": ["针对问题", "创新点"],
                           "forbidden": ["[参赛队号]", "[中文摘要内容"]}]}
    report = check_output_contract(tmp_path, contract)
    assert not report["ok"]
    assert any("未完成占位" in e and "[参赛队号]" in e for e in report["errors"])
    # 占位替换后同合同通过（contains 满足 + forbidden 清零）
    (paper / "main.tex").write_text(
        "\baominghao{D26000010001}\n针对问题一，求得最优解 3.14（创新点：分层解耦）。\n" + "x" * 6000,
        encoding="utf-8")
    report = check_output_contract(tmp_path, contract)
    assert report["ok"], report["errors"]


def test_pipeline_paper_contracts_are_content_level():
    # 生产合同真身：两大数模模板写作步必须已升级为内容级（摘要导航词+占位残留），
    # 防止合同退化回 min_bytes 空转（2026-10-02 前窗移交项落地锚）
    import json
    from pathlib import Path
    tpl = json.loads((Path(__file__).resolve().parent.parent / "engine/modex-core/templates.json")
                     .read_text(encoding="utf-8"))
    expect = {
        "comp_huawei": {"针对问题", "创新点"},
        "comp_cumcm": {"针对问题"},
    }
    for tid, words in expect.items():
        step = next(s for s in tpl[tid]["sub_steps"] if s["skill_name"] == "comp-paper-zh")
        files = step["metadata"]["output_contract"]["files"][0]
        assert words <= set(files.get("contains", [])), (tid, files)
        assert files.get("forbidden"), (tid, "forbidden 缺失")


# ---------------------------------------------------------------------------
# W-ABSTRACT3（2026-10-02 三骨架摘要专项核验窗）：wuyi / dongsansheng / default。
# 骨架实测：wuyi 与 default 的摘要都是 main.tex 内联手动排版段（非 \begin{abstract}
# 环境但有稳定占位符），contains 挂 $primary 不误拦；dongsansheng 摘要在骨架声明死的
# sections/abstract.tex（写作技能自检 glob *abstract*.tex 兜底同路径），contains 挂
# main.tex 必误拦 → 合同钉显式路径。default 族骨架 3027B，合规成文 main.tex≈4.8KB，
# 5120 下限处于合规区间内（临界误拦）→ 降至 3584（仍高于骨架原样 3027B）。
# ---------------------------------------------------------------------------

_WABS3_TEMPLATES_DIR = ROOT / "skills/comp-paper-zh/_templates"
# (模板id, 骨架目录, 摘要占位特征)
_WABS3_INLINE = [
    ("comp_wuyi", "wuyi", "[中文摘要内容"),
    ("comp_teddy", "default", "[摘要内容"),
    ("comp_certcup", "default", "[摘要内容"),
    ("comp_zhongqing", "default", "[摘要内容"),
    ("comp_tianfu", "default", "[摘要内容"),
    ("comp_shenzhen", "default", "[摘要内容"),
    ("comp_huadong", "default", "[摘要内容"),
]

_WABS3_GOOD_ABSTRACT = (
    "针对问题一，基于层次分析法与TOPSIS建立综合评价模型，从投人产出效率、服务质量、运营成本三个"
    "准则层共选取12项指标构建评价体系，对5个备选方案全排序，求得最优方案为方案3，加权贴近度0.782；"
    "灵敏度分析显示指标权重在±5%区间扰动时前两位排序保持稳定，结论可靠。\n"
    "针对问题二，以成本最小化与交付及时率为双重目标建立多目标规划模型，采用NSGA-II算法求解，"
    "种群规模200、迭代500代后得到含42个非支配解的Pareto前沿；与基准方案相比，推荐折中解使总成本"
    "下降13.6%、平均交付周期缩短2.3天，验证了模型在多目标权衡上的有效性。\n"
    "针对问题三，构建ARIMA-LSTM组合预测模型，以线性部分捕捉趋势、非线性部分修正残差，"
    "滚动回测显示组合模型平均相对误差4.8%，优于单一ARIMA模型的9.1%与单一LSTM模型的6.3%；"
    "据此给出未来三期的预测区间与相应的资源配置建议。\n"
    "针对问题四，设计滚动时域动态调度策略应对需求波动，蒙特卡洛仿真1000次显示设备平均利用率"
    "提升6.2个百分点，违约订单占比由7.4%降至2.1%，表明该策略在不确定环境下具有良好鲁棒性。\n"
)


def _wabs3_paper_contract(tid):
    import json
    tpl = json.loads((ROOT / "engine/modex-core/templates.json").read_text(encoding="utf-8"))
    step = next(s for s in tpl[tid]["sub_steps"] if s["skill_name"] == "comp-paper-zh")
    return step["metadata"]["output_contract"]


def test_wabstract3_production_contracts_anchor():
    # 生产合同防退化锚：八模板摘要内容级 + min_bytes 可达性一并钉死
    for tid, _, token in _WABS3_INLINE:
        files = _wabs3_paper_contract(tid)["files"]
        assert files[0]["path"] == "$primary"
        assert "针对问题" in files[0]["contains"], (tid, files)
        assert files[0]["forbidden"] == [token], (tid, files)
    # default 族六模板：下限必须低于合规成文区间（骨架3027B+最短合规摘要），高于骨架原样
    for tid, _, _ in _WABS3_INLINE[1:]:
        assert _wabs3_paper_contract(tid)["files"][0]["min_bytes"] == 3584, tid
    # wuyi 骨架含承诺书页 5456B，5120 保留可达；骨架原样交付由 forbidden 拦
    assert _wabs3_paper_contract("comp_wuyi")["files"][0]["min_bytes"] == 5120
    # dongsansheng：main.tex 下限可达（骨架 1271B）+ 摘要条目钉骨架声明显式路径
    files = _wabs3_paper_contract("comp_liaoning")["files"]
    assert files[0]["path"] == "$primary" and files[0]["min_bytes"] == 1024
    assert "contains" not in files[0], "contains 挂 main.tex 会误拦（摘要在 sections/abstract.tex）"
    assert files[1]["path"] == "paper/sections/abstract.tex"
    assert files[1]["min_bytes"] == 1200
    assert "针对问题" in files[1]["contains"] and files[1]["forbidden"]


@pytest.mark.parametrize("tid,skeleton_name,token", _WABS3_INLINE)
def test_wabstract3_inline_abstract_three_judgments(tmp_path, tid, skeleton_name, token):
    # 用真实骨架文件对生产合同三判（不是合成文本）
    import re
    contract = _wabs3_paper_contract(tid)
    skeleton = (_WABS3_TEMPLATES_DIR / skeleton_name / "main.tex").read_text(encoding="utf-8")
    paper = tmp_path / "paper"
    paper.mkdir()

    # 判1：骨架原样交付 → 违约。wuyi 骨架含承诺书页 5456B 过 min_bytes，由 forbidden 拦；
    # default 族骨架 3027B 由 min_bytes 拦（require_file 低于下限即短路，不再评 contains/forbidden）
    (paper / "main.tex").write_text(skeleton, encoding="utf-8")
    report = check_output_contract(tmp_path, contract, primary_output="paper/main.tex")
    assert not report["ok"], (tid, report["errors"])
    if tid == "comp_wuyi":
        assert any("未完成占位" in e and token in e for e in report["errors"]), report["errors"]
    else:
        assert any("低于实际合同下限" in e for e in report["errors"]), report["errors"]

    # 判2：规范成文（占位替换+导航词写入原位）→ 通过
    written = re.sub(r"\[" + re.escape(token[1:]) + r"[^\]]*\]", _WABS3_GOOD_ABSTRACT, skeleton)
    assert token not in written and "针对问题" in written
    (paper / "main.tex").write_text(written, encoding="utf-8")
    report = check_output_contract(tmp_path, contract, primary_output="paper/main.tex")
    assert report["ok"], (tid, report["errors"])

    # 判3：占位残留 → 精确拦截
    (paper / "main.tex").write_text(written + token + "：残留\n", encoding="utf-8")
    report = check_output_contract(tmp_path, contract, primary_output="paper/main.tex")
    assert not report["ok"]
    assert any("未完成占位" in e and token in e for e in report["errors"])


def test_wabstract3_liaoning_abstract_in_sections(tmp_path):
    # 东三省骨架：main.tex 仅 \input{sections/abstract}，摘要在骨架声明的显式路径
    contract = _wabs3_paper_contract("comp_liaoning")
    skeleton = (_WABS3_TEMPLATES_DIR / "dongsansheng" / "main.tex").read_text(encoding="utf-8")
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.tex").write_text(skeleton, encoding="utf-8")

    # 判1：骨架原样交付 → abstract.tex 缺文件违约（main.tex 1271B 过 1024 下限不误拦）
    report = check_output_contract(tmp_path, contract, primary_output="paper/main.tex")
    assert not report["ok"]
    assert any("abstract.tex" in e and "缺文件" in e for e in report["errors"]), report["errors"]
    assert not any(e.startswith("paper/main.tex") for e in report["errors"]), report["errors"]

    # 判2：规范成文（sections/abstract.tex 导航词成文）→ 通过
    secdir = paper / "sections"
    secdir.mkdir()
    good = _WABS3_GOOD_ABSTRACT + "关键词：层次分析法；NSGA-II；组合预测\n"
    (secdir / "abstract.tex").write_text(good, encoding="utf-8")
    report = check_output_contract(tmp_path, contract, primary_output="paper/main.tex")
    assert report["ok"], report["errors"]

    # 判2b：摘要成文但缺导航词 → contains 拦（作用点=abstract.tex 而非 main.tex）
    (secdir / "abstract.tex").write_text(
        "本文建立了三个模型并求解，结果良好，误差较小，方法稳定可靠。" + "字" * 1200,
        encoding="utf-8")
    report = check_output_contract(tmp_path, contract, primary_output="paper/main.tex")
    assert not report["ok"]
    assert any("abstract.tex" in e and "缺内容结构" in e for e in report["errors"]), report["errors"]

    # 判3：占位残留 → 精确拦截
    (secdir / "abstract.tex").write_text(good + "[摘要内容：残留]", encoding="utf-8")
    report = check_output_contract(tmp_path, contract, primary_output="paper/main.tex")
    assert not report["ok"]
    assert any("未完成占位" in e and "[摘要内容" in e for e in report["errors"])
