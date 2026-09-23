#!/usr/bin/env python3
"""Check structured TikZ diagrams for maintainable, semantic color usage.

The policy intentionally does *not* prescribe a palette, hue or saturation.  A
high-chroma accent, monochrome drawing and domain-specific colors can all be
correct.  What we can reliably reject in source is bypassing semantic styles
with a collection of unrelated raw xcolor values.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROLE_STYLE_NAMES = (
    r"main|sub|stage|process|decision|block|focus|role\w*|step|phase|"
    r"component|external|data|state|lane"
)
ARCH_STYLE_RE = re.compile(rf"\b(?:{ROLE_STYLE_NAMES})/\.style\s*=", re.IGNORECASE)
RAW_ARCH_COLOR_RE = re.compile(
    r"(?:draw|fill|color)\s*=\s*"
    r"(?:blue|teal|cyan|violet|purple|orange|red|green|brown|indigo|olive|magenta)"
    r"(?:!\d+(?:!\w+)?)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PaletteIssue:
    message: str


def _iter_role_style_bodies(source: str):
    """Yield balanced style bodies instead of scanning unrelated drawing code."""
    for match in ARCH_STYLE_RE.finditer(source):
        index = match.end()
        while index < len(source) and source[index].isspace():
            index += 1
        if index >= len(source) or source[index] != "{":
            # Unbraced style definitions are rare; limit inspection to the line.
            yield source[index:source.find("\n", index) if "\n" in source[index:] else len(source)]
            continue
        depth = 0
        start = index + 1
        for cursor in range(index, len(source)):
            char = source[cursor]
            if char == "{" and (cursor == 0 or source[cursor - 1] != "\\"):
                depth += 1
            elif char == "}" and (cursor == 0 or source[cursor - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    yield source[start:cursor]
                    break


def check_source(source: str) -> list[PaletteIssue]:
    issues: list[PaletteIssue] = []
    if ARCH_STYLE_RE.search(source) and "MH-TIKZ-COLOR-OK" not in source:
        raw = [
            color
            for body in _iter_role_style_bodies(source)
            for color in RAW_ARCH_COLOR_RE.findall(body)
        ]
        if raw:
            issues.append(PaletteIssue(
                f"架构/流程框图的角色样式有 {len(raw)} 处直接写 xcolor 色名；"
                "请先定义本论文自己的语义颜色令牌，再由角色样式引用。"
                "令牌颜色不固定，黑白、高饱和强调色或领域配色均可，但必须说明语义并统一管理"
            ))
    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tikz_file", type=Path)
    args = parser.parse_args(argv[1:])
    source = args.tikz_file.read_text(encoding="utf-8", errors="ignore")
    issues = check_source(source)
    if issues:
        for issue in issues:
            print(f"CRITICAL: {issue.message}")
        return 1
    print("OK: 配色策略未被固定；结构图颜色通过语义令牌集中管理")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
