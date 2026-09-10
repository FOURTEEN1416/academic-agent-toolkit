#!/usr/bin/env python3
"""High-confidence structural checks for academic TikZ diagrams.

This is deliberately a source-level gate, not an aesthetic oracle.  It reports
soft warnings for conditions that need visual review and exits non-zero only
for patterns that are very likely to make the final paper unreadable.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


STRUCTURED_STYLE_RE = re.compile(
    r"\b(?:main|sub|stage|process|decision|block|focus|role\w*|step|phase|"
    r"component|external|data|state|lane)/\.style\s*=",
    re.IGNORECASE,
)
GEOMETRY_RE = re.compile(
    r"topology\s*:\s*[^\n]*(?:geometry|geometric|coordinate)|"
    r"\\usetikzlibrary\{[^}]*\b(?:angles|intersections|through)\b|"
    r"\\pic\b[^;]*\bangle\s*=|"
    r"\\(?:draw|path)\b[^;]*(?:\barc\s*\(|\bplot\s*\[)",
    re.IGNORECASE | re.DOTALL,
)
NODE_RE = re.compile(
    r"\\node(?:\[[^\]]*\])?\s*(?:\([^)]*\)\s*)?(?:at\s*\([^)]*\)\s*)?"
    r"\{((?:[^{}]|\{[^{}]*\})*)\}",
    re.DOTALL,
)
ABS_NODE_RE = re.compile(
    r"\\node(?:\[[^\]]*\])?\s*(?:\([^)]*\)\s*)?at\s*"
    r"\(\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*\)",
    re.DOTALL,
)
SCALE_RE = re.compile(r"(?:^|[,\[])\s*scale\s*=\s*(0?\.\d+|\d+(?:\.\d+)?)")
CODE_IDENTIFIER_RE = re.compile(
    r"(?<!\\)\b(?:[A-Za-z]{3,}_[A-Za-z][A-Za-z0-9_]*|[a-z]+[A-Z][A-Za-z0-9]*)\b"
)


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str


def _plain_length(text: str) -> int:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\(?:textbf|textit|mathrm|mathbf|operatorname)\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", "", text)
    text = re.sub(r"[$^_{}&~]", "", text)
    return len(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text))


def inspect_source(source: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    structured = bool(STRUCTURED_STYLE_RE.search(source))
    geometry = bool(GEOMETRY_RE.search(source))
    nodes = list(NODE_RE.finditer(source))
    abs_nodes = len(ABS_NODE_RE.findall(source))

    scales = [float(value) for value in SCALE_RE.findall(source)]

    automatic_graph_layout = re.search(
        r"\\usegdlibrary\b|\\graph\s*(?:\[[^\]]*layered\s+layout[^\]]*\])",
        source,
        re.IGNORECASE | re.DOTALL,
    )
    if automatic_graph_layout and "MH-TIKZ-LUALATEX-OK" not in source:
        out.append(Diagnostic(
            "ERROR",
            "graphdrawing-engine",
            "检测到依赖 LuaTeX 的自动 graph drawing，但当前论文管线默认使用 XeLaTeX；"
            "请改用 positioning/matrix、拆图，或在确认 LuaLaTeX 编译路径后添加 "
            "MH-TIKZ-LUALATEX-OK 说明",
        ))

    if scales and min(scales) < 0.67:
        severity = "ERROR" if "transform shape" in source or "every node/.style={scale" in source else "WARNING"
        out.append(Diagnostic(
            severity,
            "final-scale",
            f"整体 scale 最小为 {min(scales):.2f}；不要靠极限缩放塞入页面，先重排或拆图，并检查最终有效字号",
        ))

    if structured and not geometry and len(nodes) >= 15:
        ratio = abs_nodes / max(1, len(nodes))
        if ratio >= 0.70 and "MH-TIKZ-ABSOLUTE-OK" not in source:
            out.append(Diagnostic(
                "ERROR",
                "dense-absolute-layout",
                f"结构图共有 {len(nodes)} 个节点，其中 {abs_nodes} 个使用绝对坐标；"
                "请改用 positioning/matrix/layered layout，或拆成总览与局部图",
            ))

    long_nodes: list[int] = []
    for index, match in enumerate(nodes, start=1):
        length = _plain_length(match.group(1))
        if length > 80:
            long_nodes.append(index)
    if long_nodes:
        out.append(Diagnostic(
            "ERROR",
            "node-overloaded",
            f"节点 {', '.join(map(str, long_nodes[:6]))} 文本超过 80 个可见字符；"
            "节点只保留动作/对象/短公式，解释移到正文或图注",
        ))

    small_labels = len(re.findall(r"\\(?:tiny|scriptsize)\b", source))
    if structured and small_labels:
        severity = "ERROR" if small_labels >= 6 else "WARNING"
        out.append(Diagnostic(
            severity,
            "small-semantic-text",
            f"结构图有 {small_labels} 处 tiny/scriptsize；主要语义在最终论文尺寸下应约 8pt 以上",
        ))

    if structured and re.search(r"\bdiamond\b", source, re.IGNORECASE):
        branch_labels = re.findall(r"\{\s*(?:是|否|通过|不通过|满足|不满足|yes|no|true|false)\s*\}", source, re.IGNORECASE)
        if len(branch_labels) < 2:
            out.append(Diagnostic(
                "WARNING",
                "decision-labels",
                "检测到判断菱形但没有成对的分支条件；确认每个出口都有靠近起点的明确标签",
            ))

    identifiers: set[str] = set()
    for match in nodes:
        identifiers.update(CODE_IDENTIFIER_RE.findall(match.group(1)))
    identifiers = {item for item in identifiers if not item.startswith("fig_")}
    if identifiers:
        sample = ", ".join(sorted(identifiers)[:5])
        out.append(Diagnostic(
            "WARNING",
            "internal-identifiers",
            f"节点疑似含程序内部标识符（{sample}）；成品应改为正文已定义的术语或数学符号",
        ))

    if structured and len(nodes) > 12 and not re.search(
        r"\\usetikzlibrary\{[^}]*\b(?:positioning|matrix|graphdrawing)\b|matrix of nodes|layered layout",
        source,
        re.IGNORECASE,
    ):
        out.append(Diagnostic(
            "WARNING",
            "layout-engine",
            "节点超过 12 个但未发现 positioning/matrix/graphdrawing；人工坐标容易遮挡，需重点视觉复查",
        ))

    if structured and re.search(r"\\(?:resizebox|scalebox)\b", source):
        out.append(Diagnostic(
            "WARNING",
            "box-scaling",
            "结构图使用 resizebox/scalebox；请检查字体、箭头和线宽的最终有效尺寸，优先改布局或拆图",
        ))

    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tikz_file", type=Path)
    args = parser.parse_args(argv[1:])
    source = args.tikz_file.read_text(encoding="utf-8", errors="ignore")
    diagnostics = inspect_source(source)
    for diagnostic in diagnostics:
        print(f"{diagnostic.severity}: [{diagnostic.code}] {diagnostic.message}")
    if not diagnostics:
        print("OK: TikZ 结构、密度与最终尺寸静态检查通过")
    return 1 if any(item.severity == "ERROR" for item in diagnostics) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
