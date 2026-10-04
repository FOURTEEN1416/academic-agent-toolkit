#!/usr/bin/env python3
"""Abstract per-problem paragraph check for comp-paper-zh (extracted from SKILL.md).

Rule: every "针对问题 X" must own its own paragraph (separated by a LaTeX blank
line).  Two or more in one paragraph means the reviewer cannot locate each
sub-problem's contribution at a glance -- the single most common abstract
structure failure.

Abstract location order (mirrors the writing templates):
1. paper/main.tex abstract environment (cumcm / huazhong / MathorCup family);
2. paper/main.tex manually typeset block (from the 摘…要 marker, tolerating
   quad/hspace/full-width spaces, up to \\section or 关键词);
3. paper/sections/0_*.tex or *abstract*.tex fallback.

Exit codes: 0 = pass or abstract not written yet, 1 = squeezed paragraphs
found (fix: insert a blank line before each 针对问题 X and rerun).
"""
from __future__ import annotations

import glob
import os
import re
import sys

BS = chr(92)  # 反斜杠经脚本传输易被折叠，统一 chr(92) 构造


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def locate_abstract() -> tuple[str | None, str | None]:
    mt = "paper/main.tex"
    if os.path.isfile(mt):
        s = _read(mt)
        beg, end = BS + "begin{abstract}", BS + "end{abstract}"
        i0, i1 = s.find(beg), s.find(end)
        if i0 != -1 and i1 > i0:
            inner = s[i0 + len(beg): i1]
            if "针对问题" in inner:
                return inner, "paper/main.tex 的 abstract 环境"
        m = re.search("摘[^要]{0,16}要", s)
        if m:
            tail = s[m.end():]
            stops = [x for x in (tail.find(BS + "section"), tail.find("关键词")) if x != -1]
            seg = tail[: min(stops)] if stops else tail[:4000]
            if "针对问题" in seg:
                return seg, "paper/main.tex 的手动排版摘要段"
    for pat in ("paper/sections/0_*.tex", "paper/sections/*abstract*.tex"):
        for f in sorted(glob.glob(pat)):
            s = _read(f)
            if "针对问题" in s:
                return s, f
    return None, None


def main() -> int:
    text, where = locate_abstract()
    if text is None:
        print("⚠ SKIP: 未定位到含'针对问题'的摘要文本（可能尚未写摘要）；SKIP 不冒充通过，exit 2")
        return 2
    bad = []
    for i, para in enumerate(re.split(r"\n\s*\n", text), 1):
        if len(re.findall(r"针对问题", para)) > 1:
            bad.append((i, para.strip()[:80]))
    if bad:
        print(f"❌ 摘要（{where}）中 {len(bad)} 个段落挤了多个'针对问题' — 必须每个独立成段（段间空一行）：")
        for i, snip in bad:
            print(f"  段 {i}: {snip}...")
        return 1
    print(f"✓ 摘要按问题分段正确（{where}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
