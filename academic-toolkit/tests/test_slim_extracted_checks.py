"""W-SLIM 外提脚本自测（批3.3）：五个从 comp-paper-zh SKILL.md 内嵌块外提的检查器。

每个脚本构造最小正/反例各一，验证退出码语义（0 过 / 1 违约 / 2 SKIP）。
脚本经 skills/_utils/ 直跑（与 SKILL.md 调用同路径），双副本一致性由
test_dual_copy_consistency.py 守护，此处不重复。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "skills" / "_utils"


def _run(script: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(UTILS / script), *args],
        cwd=cwd, capture_output=True, text=True, timeout=60,
    )


# ---------------------------------------------------------------------------
# template_integrity_check
# ---------------------------------------------------------------------------

GOOD_MAIN = "\\documentclass[12pt]{cumcmthesis}\n\\begin{document}\n\\input{sections/1}\n\\begin{thebibliography}{99}\\end{thebibliography}\n\\begin{appendices}\\end{appendices}\n\\def\\@cite#1#2{#1}\n\\end{document}\n"


def _seed_paper(tmp: Path, main_text: str) -> Path:
    paper = tmp / "paper"
    paper.mkdir(parents=True)
    (paper / "main.tex").write_text(main_text, encoding="utf-8")
    return tmp


def test_template_integrity_full_pass_and_fail(tmp_path):
    good = _seed_paper(tmp_path / "good", GOOD_MAIN)
    r = _run("template_integrity_check.py", ["--full"], good)
    assert r.returncode == 0, r.stdout + r.stderr

    bad = _seed_paper(tmp_path / "bad", "\\documentclass{article}\n\\begin{document}\\end{document}\n")
    r = _run("template_integrity_check.py", ["--full"], bad)
    assert r.returncode == 1
    assert "sections input" in r.stdout


def test_template_integrity_fingerprint_detects_rewrite(tmp_path):
    tpl_base = tmp_path / "_templates" / "cumcm"
    tpl_base.mkdir(parents=True)
    tpl_main = "\\documentclass{cumcmthesis}\n" + "\n".join(f"% preamble line {i}" for i in range(19)) + "\n"
    (tpl_base / "main.tex").write_text(tpl_main, encoding="utf-8")
    ws = tmp_path / "ws"
    paper = ws / "paper"
    paper.mkdir(parents=True)
    (paper / "main.tex").write_text(tpl_main, encoding="utf-8")
    r = _run("template_integrity_check.py", ["--fingerprint", "--template-base", str(tmp_path / "_templates")], ws)
    assert r.returncode == 0, r.stdout + r.stderr

    # 重写 preamble（>10 行差异）必须被抓到
    rewritten = "\\documentclass{cumcmthesis}\n" + "\n".join(f"% totally different {i}" for i in range(19)) + "\n"
    (paper / "main.tex").write_text(rewritten, encoding="utf-8")
    r = _run("template_integrity_check.py", ["--fingerprint", "--template-base", str(tmp_path / "_templates")], ws)
    assert r.returncode == 1
    assert "差异过大" in r.stdout


# ---------------------------------------------------------------------------
# figure_layout_check
# ---------------------------------------------------------------------------

def test_figure_layout_embed_and_manifest(tmp_path):
    ws = tmp_path
    (ws / "figures").mkdir()
    (ws / "figures" / "fig_a.pdf").write_bytes(b"%PDF-1.4 a")
    (ws / "figures" / "fig_b.pdf").write_bytes(b"%PDF-1.4 b")
    paper = ws / "paper" / "sections"
    paper.mkdir(parents=True)
    (paper.parent / "main.tex").write_text("\\input{sections/1}\n", encoding="utf-8")

    # 反例：fig_b 未嵌入
    (paper / "1_x.tex").write_text("如图~\\ref{fig:a}，见 fig_a.pdf。\n", encoding="utf-8")
    r = _run("figure_layout_check.py", ["paper"], ws)
    assert r.returncode == 1
    assert "fig_b.pdf 未嵌入" in r.stdout

    # 正例：两图都嵌入
    (paper / "1_x.tex").write_text("见图 fig_a.pdf 与 fig_b.pdf。\n", encoding="utf-8")
    r = _run("figure_layout_check.py", ["paper"], ws)
    assert r.returncode == 0, r.stdout + r.stderr


def test_figure_layout_extensionless_includegraphics_not_a_violation(tmp_path):
    """验收修复回归：\\includegraphics{../figures/fig_x}（无扩展名，LaTeX 合法）
    不得报"未嵌入/未引用"（冻结稿实测 28/31 图此形态，曾致 59 条违约中大多假阳）。"""
    ws = tmp_path
    (ws / "figures").mkdir()
    (ws / "figures" / "fig_q1_bisection.pdf").write_bytes(b"%PDF")
    (ws / "figures" / "fig_q1.pdf").write_bytes(b"%PDF")
    paper = ws / "paper" / "sections"
    paper.mkdir(parents=True)
    (ws / "paper" / "main.tex").write_text("main\n", encoding="utf-8")
    (paper / "5_problem1.tex").write_text(
        "\\includegraphics[width=0.92\\textwidth]{../figures/fig_q1_bisection}\n"
        "\\includegraphics[width=0.9\\textwidth]{../figures/fig_q10_x}\n",  # 前缀歧义探针
        encoding="utf-8")
    r = _run("figure_layout_check.py", ["paper"], ws)
    assert r.returncode == 1, r.stdout  # fig_q10_x 无产出文件，仍须违约
    assert "fig_q1_bisection.pdf 未嵌入" not in r.stdout
    # fig_q1 不得因 fig_q10_x 的出现而被误判已引用
    assert "fig_q1.pdf 未嵌入" in r.stdout


def test_figure_layout_svg_output_matches_engine_contract(tmp_path):
    """复核批回归：svg 产出/引用形态与引擎 output_contracts 口径一致（pdf/png/svg）。"""
    ws = tmp_path
    (ws / "figures").mkdir()
    (ws / "figures" / "fig_only_svg.svg").write_bytes(b"<svg/>")
    paper = ws / "paper" / "sections"
    paper.mkdir(parents=True)
    (ws / "paper" / "main.tex").write_text("main\n", encoding="utf-8")
    (paper / "1_x.tex").write_text("见图 fig_only_svg。\n", encoding="utf-8")
    (ws / "PROBLEM_ANALYSIS.md").write_text(
        "<!-- BEGIN FIGURE_MANIFEST -->\n- fig_only_svg\n<!-- END FIGURE_MANIFEST -->\n",
        encoding="utf-8")
    r = _run("figure_layout_check.py", ["paper"], ws)
    assert r.returncode == 0, r.stdout  # 仅 svg 产出+引用不得报违约


def test_figure_layout_manifest_and_stacking(tmp_path):
    ws = tmp_path
    (ws / "figures").mkdir()
    (ws / "figures" / "fig_roadmap.pdf").write_bytes(b"%PDF")
    (ws / "figures" / "fig_flow_q1.pdf").write_bytes(b"%PDF")
    (ws / "figures" / "fig_flow_q2.pdf").write_bytes(b"%PDF")
    paper = ws / "paper" / "sections"
    paper.mkdir(parents=True)
    (ws / "paper" / "main.tex").write_text("main\n", encoding="utf-8")
    (paper / "2_analysis.tex").write_text("见图 fig_flow_q1.pdf 与 fig_flow_q2.pdf 堆叠。\n", encoding="utf-8")
    (ws / "PROBLEM_ANALYSIS.md").write_text(
        "<!-- BEGIN FIGURE_MANIFEST -->\n- fig_roadmap\n- fig_flow_q1\n- fig_flow_q2\n<!-- END FIGURE_MANIFEST -->\n",
        encoding="utf-8")
    r = _run("figure_layout_check.py", ["paper"], ws)
    assert r.returncode == 1
    assert "堆叠" in r.stdout and "fig_roadmap.pdf 未嵌入" in r.stdout


# ---------------------------------------------------------------------------
# page_precheck
# ---------------------------------------------------------------------------

def test_page_precheck_cap_overrun_and_code_in_body(tmp_path):
    ws = tmp_path
    sections = ws / "paper" / "sections"
    sections.mkdir(parents=True)
    (sections / "1_a.tex").write_text("正" * 2000, encoding="utf-8")  # est ~3 页
    (ws / ".engine").mkdir()
    (ws / ".engine" / "contest_env").write_text(
        "CONTEST_ID=comp_huawei\nPAGE_CAP=2\nPAGE_SCOPE=body\nPAGE_CAP_STATUS=official_verified\n",
        encoding="utf-8")
    r = _run("page_precheck.py", ["--workspace", "."], ws)
    assert r.returncode == 1
    assert "超上限" in r.stdout

    # 反例→正例：低于上限
    (sections / "1_a.tex").write_text("正" * 500, encoding="utf-8")
    r = _run("page_precheck.py", ["--workspace", "."], ws)
    assert r.returncode == 0, r.stdout + r.stderr

    # 代码块入正文 → 违约
    (sections / "1_a.tex").write_text("\\begin{lstlisting}\nx=1\n\\end{lstlisting}\n", encoding="utf-8")
    r = _run("page_precheck.py", ["--workspace", "."], ws)
    assert r.returncode == 1
    assert "代码块" in r.stdout


def test_page_precheck_missing_cap_is_unknown_not_default(tmp_path):
    ws = tmp_path
    sections = ws / "paper" / "sections"
    sections.mkdir(parents=True)
    (sections / "1_a.tex").write_text("正" * 100, encoding="utf-8")
    r = _run("page_precheck.py", ["--workspace", "."], ws)
    assert r.returncode == 0
    assert "待核实" in r.stdout and "禁止编默认值" in r.stdout


# ---------------------------------------------------------------------------
# summarize_results
# ---------------------------------------------------------------------------

def test_summarize_results_compresses_lists_keeps_scalars(tmp_path):
    figs = tmp_path / "figures"
    figs.mkdir()
    (figs / "x_results.json").write_text(
        '{"fitness": 0.917, "curve": [1, 2, 3, 4, 5]}', encoding="utf-8")
    r = _run("summarize_results.py", ["figures"], tmp_path)
    assert r.returncode == 0
    assert "0.917" in r.stdout and "range=[1,5]" in r.stdout

    empty = tmp_path / "empty-nothing"
    empty.mkdir()
    r = _run("summarize_results.py", ["figures"], empty)
    assert r.returncode == 2


# ---------------------------------------------------------------------------
# abstract_paragraph_check
# ---------------------------------------------------------------------------

def _abstract_ws(tmp_path: Path, inner: str) -> Path:
    ws = tmp_path
    paper = ws / "paper"
    paper.mkdir(parents=True)
    (paper / "main.tex").write_text(
        "\\begin{abstract}\n" + inner + "\n\\end{abstract}\n", encoding="utf-8")
    return ws


def test_abstract_paragraph_squeezed_vs_split(tmp_path):
    squeezed = ("针对问题一，建立模型，结果 0.9。针对问题二，建立模型，结果 1.2。\n\n"
                "本文方法有效。")
    r = _run("abstract_paragraph_check.py", [], _abstract_ws(tmp_path / "bad", squeezed))
    assert r.returncode == 1
    assert "挤了多个" in r.stdout

    split = ("本文针对某问题开展研究。\n\n"
             "针对问题一，建立模型，结果 0.9。\n\n"
             "针对问题二，建立模型，结果 1.2。\n\n"
             "模型评价良好。")
    r = _run("abstract_paragraph_check.py", [], _abstract_ws(tmp_path / "good", split))
    assert r.returncode == 0, r.stdout + r.stderr


def test_abstract_paragraph_skip_when_absent(tmp_path):
    ws = tmp_path
    (ws / "paper").mkdir()
    (ws / "paper" / "main.tex").write_text("no abstract yet", encoding="utf-8")
    r = _run("abstract_paragraph_check.py", [], ws)
    # 2026-10-05 对抗扫描批：SKIP 不冒充通过——缺席语义统一 exit 2
    assert r.returncode == 2
    assert "SKIP" in r.stdout


def test_template_integrity_cumcm_inline_skeleton_not_failed(tmp_path):
    # 2026-10-05 格式批：cumcm 骨架本体全内联（无 \input{sections/}）——
    # 老实复制骨架曾被 --full 误判 FAIL（逼写手重写 main.tex）。
    # comp_cumcm 免 sections-input；其他赛事缺 \input 仍 FAIL。
    inline = "\\documentclass[12pt]{cumcmthesis}\n\\begin{document}\n\\begin{thebibliography}{99}\\end{thebibliography}\n\\begin{appendices}\\end{appendices}\n\\def\\@cite#1#2{#1}\n\\end{document}\n"
    cumcm = _seed_paper(tmp_path / "cumcm", inline)
    r = _run("template_integrity_check.py", ["--full", "--contest", "comp_cumcm"], cumcm)
    assert r.returncode == 0, r.stdout + r.stderr
    other = _seed_paper(tmp_path / "other", inline)
    r = _run("template_integrity_check.py", ["--full", "--contest", "comp_huawei"], other)
    assert r.returncode == 1 and "sections input" in r.stdout, r.stdout
