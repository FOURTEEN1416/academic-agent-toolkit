#!/usr/bin/env python3
r"""Figure embedding & layout checks for comp-paper-zh (extracted from SKILL.md).

Covers the embedding-side checks that no engine gate owns today
(figure_narrative checks embedded-but-unnarrated floats; output_contract
figure_outputs checks manifest files exist -- neither checks "every produced
figure / manifest figure is actually referenced by the paper"):

1. embed completeness -- every figures/*.pdf must be referenced in
   paper/main.tex or paper/sections/*.tex (with or without extension: LaTeX
   ``\includegraphics{../figures/fig_x}`` is legal and common);
2. FIGURE_MANIFEST reconciliation -- every ``- fig_x`` / ``- tikz_x`` entry in
   the manifest block (PROBLEM_ANALYSIS.md / PAPER_PLAN.md / MODELING_REPORT.md)
   must exist in figures/ AND be referenced by the paper;
3. flow-figure stacking -- the problem-analysis chapter (2_*.tex) must hold at
   most one distinct ``fig_flow_qN``; the rest belong to the per-problem
   chapters.

Exit codes: 0 = pass, 1 = violations (fix before finishing), 2 = skip
(no paper text or no figures at all).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MANIFEST_PLAN_FILES = ("PROBLEM_ANALYSIS.md", "PAPER_PLAN.md", "MODELING_REPORT.md")


def _referenced(name: str, text: str) -> bool:
    """正文引用判定：fig_x.pdf / fig_x.png / 无扩展名形态（LaTeX includegraphics
    合法省略扩展名，实测冻结稿 28/31 图无扩展名引用）均算已引用；
    否定先行防前缀误配（fig_q1 不得匹配 fig_q10）。"""
    return bool(re.search(rf"{re.escape(name)}(?:\.(?:pdf|png))?(?![A-Za-z0-9_])", text))


def _paper_text(paper: Path) -> str:
    parts = []
    main = paper / "main.tex"
    if main.is_file():
        parts.append(main.read_text(encoding="utf-8", errors="ignore"))
    sections = paper / "sections"
    if sections.is_dir():
        for f in sorted(sections.glob("*.tex")):
            parts.append(f.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _manifest_entries(workspace: Path) -> tuple[str, list[str]] | None:
    for name in MANIFEST_PLAN_FILES:
        plan = workspace / name
        if not plan.is_file():
            continue
        text = plan.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"<!-- BEGIN FIGURE_MANIFEST -->(.*?)<!-- END FIGURE_MANIFEST -->", text, re.S)
        if not m:
            continue
        names = re.findall(r"^\s*-\s+((?:fig|tikz)_[A-Za-z0-9_]+)", m.group(1), re.M)
        return name, names
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paper", type=Path, nargs="?", default=Path("paper"), help="paper 目录（默认 paper/）")
    parser.add_argument("--workspace", type=Path, default=Path("."), help="工作区根（figures/ 与 manifest 所在，默认 .）")
    args = parser.parse_args()
    paper = args.paper.resolve()
    workspace = args.workspace.resolve()

    text = _paper_text(paper)
    if not text.strip():
        print("[SKIP] 未找到 paper/main.tex 或 sections/*.tex（正文未成文）")
        return 2
    figures_dir = workspace / "figures"
    pdfs = sorted(figures_dir.glob("*.pdf")) if figures_dir.is_dir() else []
    if not pdfs:
        print("[SKIP] figures/ 无 PDF 图表")
        return 2

    failures: list[str] = []

    print("=== 图表嵌入完整性 ===")
    for pdf in pdfs:
        stem = pdf.stem
        if _referenced(stem, text):
            print(f"✅ {pdf.name} 已嵌入")
        else:
            print(f"❌ {pdf.name} 未嵌入任何章节")
            failures.append(f"未嵌入: {pdf.name}")

    print("=== FIGURE_MANIFEST 对账 ===")
    manifest = _manifest_entries(workspace)
    if manifest is None:
        print("(没有 FIGURE_MANIFEST, 跳过对账)")
    else:
        plan_name, names = manifest
        for name in names:
            produced = any((figures_dir / f"{name}.{ext}").is_file() for ext in ("pdf", "png"))
            referenced = _referenced(name, text)
            if not produced:
                print(f"❌ MANIFEST: {name} 文件不存在（{plan_name}）")
                failures.append(f"MANIFEST 未产出: {name}")
            elif not referenced:
                print(f"❌ MANIFEST: {name} 文件存在但论文未引用")
                failures.append(f"MANIFEST 未引用: {name}")
            else:
                print(f"✅ MANIFEST: {name} 已产出并嵌入")

    print("=== 流程图堆叠检查 ===")
    analysis_texs = sorted((paper / "sections").glob("2_*.tex")) if (paper / "sections").is_dir() else []
    if analysis_texs:
        analysis_text = analysis_texs[0].read_text(encoding="utf-8", errors="ignore")
        flows = sorted(set(re.findall(r"fig_flow_q[0-9]+", analysis_text)))
        if len(flows) >= 2:
            print(f"❌ 问题分析章节含 {len(flows)} 张子问题流程图（{', '.join(flows)}）— 违反铁律！")
            print("   必须把 fig_flow_qN 分散到各自问题章节，分析章节最多留 fig_roadmap 一张。")
            failures.append(f"流程图堆叠: {len(flows)} 张在 {analysis_texs[0].name}")
        else:
            print("✅ 流程图未堆叠在问题分析章节")

    if failures:
        print(f"⛔ 共 {len(failures)} 处图表布局违约 — 必须立即修复后再继续。")
        return 1
    print("✅ 图表布局检查全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
