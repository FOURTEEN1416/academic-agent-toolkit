#!/usr/bin/env python3
"""Template integrity checks for comp-paper-zh (extracted from SKILL.md inline blocks).

Two modes (both read-only; they never modify paper/):

``--fingerprint``  Compare the preamble (first 20 lines) of paper/main.tex against
the template original under --template-base to prove the skeleton was copied, not
rewritten.  A diff over --max-diff-lines forces a recopy verdict.

``--full``  Post-writing integrity audit: documentclass / sections input /
bibliography / appendix / superscript-cite markers must survive, plus
per-contest checks keyed on the dispatched CONTEST_ID (wuyi pledge page,
MathorCup/APMCM document class and team fields, huazhong class, huawei title
constraints -- no ``\\\\`` linebreak, no AI-styled invented titles).

Exit codes: 0 = pass, 1 = failure (fix before continuing), 2 = skip (no
paper/main.tex -- not an error for optional callers).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _documentclass_line(text: str) -> str:
    for line in text.splitlines():
        if "documentclass" in line:
            return line.strip()
    return ""


def run_fingerprint(paper: Path, template_base: Path, max_diff: int) -> int:
    main_tex = paper / "main.tex"
    if not main_tex.is_file():
        print("❌ CRITICAL: paper/main.tex 不存在！模板复制失败")
        return 1
    paper_cls = _documentclass_line(_read(main_tex))
    template_main = ""
    if template_base.is_dir():
        for d in sorted(template_base.iterdir()):
            cand = d / "main.tex"
            if not cand.is_file():
                continue
            if _documentclass_line(_read(cand)) == paper_cls and paper_cls:
                template_main = str(cand)
                break
    if not template_main:
        print("⚠ 未找到匹配的模板原文，跳过指纹校验")
        return 0
    print(f"模板原文: {template_main}")
    import difflib

    a = _read(Path(template_main)).splitlines()[:20]
    b = _read(main_tex).splitlines()[:20]
    diff = [l for l in difflib.unified_diff(a, b, lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    diff_count = len(diff)
    if diff_count > max_diff:
        print(f"❌ CRITICAL: paper/main.tex 的 preamble 和模板差异过大（{diff_count} 行不同）— 可能被重写了！")
        print("⛔ 从模板重新复制 skeleton，再只替换占位符（旧文件可备份为 main.tex.broken）")
        return 1
    print(f"✅ 模板指纹校验通过（preamble 差异 {diff_count} 行，在允许范围内）")
    return 0


def _huawei_title_checks(main_text: str, paper: Path) -> list[str]:
    problems: list[str] = []
    m = re.search(r"\\title\{([^}]*)\}", main_text)
    title_line = f"\\title{{{m.group(1)}}}" if m else ""
    print(f"[华为杯] Title: {title_line or '(未找到 \\title)'}")
    if m and "\\\\" in m.group(1):
        problems.append("\\title{} 含 \\\\ 强制换行 — 改成单行让 cls 自动换行（v1.5.0+ 支持按宽度换行）")
    if m and re.search(r"(基于.*的|.*的研究|.*的应用|.*的探索|.*：一种)", m.group(1)):
        problems.append("标题含 AI 风格修饰词 — 华为杯必须严格使用赛题官方标题（从 user_data/*_extracted.txt 抄，不改一个字）")
    extracted = sorted(paper.parent.glob("user_data/*_extracted.txt"))
    if extracted:
        head = _read(extracted[0]).splitlines()[:5]
        print("[华为杯] 赛题文件前 5 行（请确认 \\title{} 与赛题官方标题一致）:")
        for line in head:
            print(f"  {line}")
    return problems


def run_full(paper: Path, contest_id: str) -> int:
    main_tex = paper / "main.tex"
    if not main_tex.is_file():
        print("❌ paper/main.tex 不存在（正文未成文或模板未复制）")
        return 2
    text = _read(main_tex)
    ok = fail = 0

    def check(label: str, cond: bool) -> None:
        nonlocal ok, fail
        if cond:
            print(f"✅ {label}")
            ok += 1
        else:
            print(f"❌ {label}")
            fail += 1

    check("documentclass", "documentclass" in text)
    # comp_cumcm 骨架本体为全内联设计（无 \input{sections/}）；老实复制骨架
    # 曾被本检查误判 FAIL，逼着写手重写 main.tex 反而违反"不要重写 main.tex"。
    # 本检查对 comp_cumcm 不要求 sections-input（写手内联或拆 sections 均放行）。
    if contest_id == "comp_cumcm":
        check("cumcm 骨架完整（内联设计，免 sections-input）", "documentclass" in text)
    else:
        check("sections input", "\\input{sections/" in text)
    check("参考文献结构", ("thebibliography" in text) or ("bibliography{" in text))
    check("附录结构", ("appendices" in text) or ("\\appendix" in text))
    check("上标引用定义", ("superscript" in text) or ("\\@cite" in text) or re.search(r"setcitestyle.*super", text))
    if contest_id == "comp_wuyi":
        check("五一杯承诺书页", "承诺书" in text)
        check("五一杯封面logo", "image2" in text)
        check("五一杯关键词", "关键词" in text)
    elif contest_id in ("comp_mathorcup", "comp_apmcm_zh"):
        check(f"{contest_id} cls=MathorCupmodeling", "MathorCupmodeling" in text)
        check(f"{contest_id} 队伍信息", bool(re.search(r"\\bianhao|\\tihao|\\timu", text)))
    elif contest_id == "comp_huazhong":
        check("华中杯 cls=cumcmthesis", "cumcmthesis" in text)
    elif contest_id == "comp_huawei":
        for problem in _huawei_title_checks(text, paper):
            print(f"⛔ [华为杯] {problem}")
            fail += 1
    print(f"模板检查: {ok} 通过, {fail} 失败")
    if fail:
        print("⛔ 必须修复所有失败项！可能是 main.tex 被意外重写了，请从模板重新复制并只替换占位符。")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--paper", type=Path, default=Path("paper"), help="paper 目录（默认 paper/）")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fingerprint", action="store_true", help="Step1：preamble 指纹比对")
    mode.add_argument("--full", action="store_true", help="Step6：结构完整性 + 赛事专属检查")
    parser.add_argument("--template-base", type=Path, default=None, help="模板库目录（fingerprint 模式）")
    parser.add_argument("--max-diff-lines", type=int, default=10, help="preamble 允许差异行数（默认 10）")
    parser.add_argument("--contest", default="", help="规范 comp_* ID；缺省读环境 CONTEST_ID")
    args = parser.parse_args()
    contest = args.contest or os.environ.get("CONTEST_ID", "")
    paper = args.paper.resolve()
    if args.fingerprint:
        base = args.template_base
        if base is None:
            base = Path("_templates")
            if not base.is_dir():
                base = Path("templates")
        return run_fingerprint(paper, base.resolve(), args.max_diff_lines)
    return run_full(paper, contest)


if __name__ == "__main__":
    sys.exit(main())
