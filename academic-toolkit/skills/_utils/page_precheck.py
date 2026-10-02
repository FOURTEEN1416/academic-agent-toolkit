#!/usr/bin/env python3
"""Writing-stage page pre-check for comp-paper-zh (extracted from SKILL.md).

The authoritative page gate at finish is the engine's quick_gates (PDF-based,
contest contract).  While writing there is no PDF yet, so this script gives the
same contract-aware character estimate:

1. code-in-body -- sections/*.tex must not carry lstlisting/verbatim/minted/
   python/matlab blocks (code belongs in paper/appendix/; it inflates the
   estimate while the real body stays thin);
2. body estimate -- paper/sections/*.tex characters / 900 = estimated pages,
   checked against PAGE_CAP with PAGE_SCOPE semantics:
   - ``body``  (e.g. comp_cumcm / comp_huawei): sections only; appendix counted
     separately, never against the cap;
   - ``total`` (e.g. comp_mcm): sections + appendix + main.tex (whole-book
     estimate -- a body-only estimate would silently understate);
3. cap status -- PAGE_CAP/PAGE_SCOPE/PAGE_CAP_STATUS come from the environment
   or workspace/.engine/contest_env (engine-injected, single source).  A
   missing cap is reported as unknown (待核实) and never defaulted; unknown
   status never fabricates a hard limit.

Exit codes: 0 = ok (or cap unknown), 1 = violation (code in body / estimate
over cap), 2 = skip (no sections yet).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

CODE_ENV_RE = re.compile(r"\\begin\{(lstlisting|verbatim|minted|python|matlab)\}")


def _load_contest_env(workspace: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = workspace / ".engine" / "contest_env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    for key in ("CONTEST_ID", "PAGE_CAP", "PAGE_SCOPE", "PAGE_CAP_STATUS"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def _chars(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", type=Path, default=Path("."), help="工作区根（默认 .）")
    parser.add_argument("--chars-per-page", type=int, default=900, help="中文 LaTeX 每页字符估计（默认 900）")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    paper = workspace / "paper"
    sections = paper / "sections"
    if not sections.is_dir() or not list(sections.glob("*.tex")):
        print("[SKIP] paper/sections/ 无章节文件（尚未开写）")
        return 2

    env = _load_contest_env(workspace)
    page_cap = env.get("PAGE_CAP", "").strip()
    page_scope = env.get("PAGE_SCOPE", "").strip() or "body"
    cap_status = env.get("PAGE_CAP_STATUS", "").strip()

    print("=== 正文页数预检（口径以 contest_env / 引擎下发为准）===")

    code_in_body = 0
    for f in sorted(sections.glob("*.tex")):
        if CODE_ENV_RE.search(f.read_text(encoding="utf-8", errors="ignore")):
            code_in_body += 1
            print(f"  ⚠️ {f.name} 含代码块 — 代码必须放 paper/appendix/，不能放正文")
    if code_in_body:
        print(f"⛔ CRITICAL: {code_in_body} 个正文章节含代码块，必须移到 paper/appendix/（代码块行多密度低，会让估页虚高而实际正文单薄）")

    total_chars = sum(_chars(f) for f in sections.glob("*.tex"))
    appendix_chars = 0
    appendix_dir = paper / "appendix"
    if appendix_dir.is_dir():
        appendix_chars = sum(_chars(f) for f in appendix_dir.glob("*.tex"))

    if page_scope == "total":
        whole_chars = total_chars + appendix_chars + _chars(paper / "main.tex")
        est_pages = whole_chars // args.chars_per_page
        scope_note = "total（整本估算：sections+appendix+main.tex）"
    else:
        est_pages = total_chars // args.chars_per_page
        scope_note = "body（只计 sections/，附录另计不计入上限）"
    appendix_pages = appendix_chars // args.chars_per_page

    if not page_cap:
        print(f"⛔ PAGE_CAP 缺失：该赛事无 operative 页数合同（或历史裁决不继承）——页数上限未知（待核实），禁止编默认值。")
        status_line = f"正文字符: {total_chars} (est ~{est_pages} 页); 口径: {page_scope}; 性质: {cap_status or '未上报'}"
        print(status_line)
    else:
        cap = int(page_cap)
        print(f"正文字符: {total_chars} (est ~{est_pages} 页); 上限: <= {cap} 页, 口径: {page_scope}, 性质: {cap_status or '未上报'}")
        if est_pages > cap:
            print(f"⛔ 超上限：est {est_pages} 页 > PAGE_CAP {cap} 页（{scope_note}）——精简或压缩，禁止删必要论证凑页数")
            if not code_in_body:
                return 1
        else:
            print(f"✅ 页数预检通过（est {est_pages} <= {cap}，{scope_note}）")
    if appendix_chars:
        print(f"（附录字符: {appendix_chars}, 估算 ~{appendix_pages} 页，不计入页数上限检查）")
    return 1 if code_in_body else 0


if __name__ == "__main__":
    sys.exit(main())
