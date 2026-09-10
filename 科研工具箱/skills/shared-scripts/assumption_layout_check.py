#!/usr/bin/env python3
"""Validate model-assumption sections for concise, paper-facing prose.

An assumptions section records uncertain real-world simplifications used by the
model.  It is not a parameter dump, a solver description, a result paragraph,
or an internal engineering report.  Keeping those responsibilities separate
also prevents long labels and dense list items from overflowing the page.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import expanded_documents, strip_comments


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ASSUMPTION_HEADING_RE = re.compile(
    r"\\(?:section|section\*)\s*\{[^}]*(?:模型假设|基本假设|model assumptions?|assumptions?)[^}]*\}",
    re.IGNORECASE,
)
NEXT_SECTION_RE = re.compile(r"\\(?:section|section\*)\s*\{")
ITEM_RE = re.compile(r"\\item(?:\s*\[[^]]*\])?")
PLAIN_ITEM_RE = re.compile(
    r"(?m)^\s*(?:\\noindent\s*)?(?:[（(]\s*(?:\d+|[一二三四五六七八九十]+)\s*[）)]|"
    r"(?:\d+|[一二三四五六七八九十]+)[、．.]|假设\s*[A-Za-z]?\d+\s*[:：])"
)
VISIBLE_RE = re.compile(r"[\u3400-\u9fff]|[A-Za-z]+(?:[-'][A-Za-z]+)*|\d+(?:\.\d+)?")
INTERNAL_RE = re.compile(
    r"可切换参数|对应开关|程序中的|求解程序|无需重写|证伪触发|"
    r"质量门|审计(?:规则|状态|报告)?|validate[_A-Za-z]*|ok\s*=\s*true|"
    r"toggle|feature\s+flag|solver\s+switch|quality\s+gate|audit\s+status",
    re.IGNORECASE,
)
METHOD_RE = re.compile(
    r"Pareto|加权标量化|ε[-—–]?约束|\\varepsilon[-—–]?约束|"
    r"求解器|遗传算法|模拟退火|分支切割|块坐标下降|"
    r"weighted\s+sum|epsilon[- ]constraint|genetic\s+algorithm|solver",
    re.IGNORECASE,
)
LONG_LABEL_RE = re.compile(
    r"label\s*=\s*[^,\]]*(?:假设\s*[A-Za-z]|Assumption\s*[A-Za-z])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AssumptionIssue:
    path: Path
    message: str
    severity: str = "error"


def _strip_comments(source: str) -> str:
    lines: list[str] = []
    for line in source.splitlines():
        active: list[str] = []
        for index, char in enumerate(line):
            if char == "%" and (index == 0 or line[index - 1] != "\\"):
                break
            active.append(char)
        lines.append("".join(active))
    return "\n".join(lines)


def visible_units(source: str) -> int:
    source = _strip_comments(source)
    source = re.sub(r"\\(?:begin|end)\{[^}]+\}", " ", source)
    source = re.sub(r"\\(?:label|ref|eqref|cite)\{[^}]*\}", " ", source)
    source = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", source)
    source = re.sub(r"[{}$&_^~\\]", " ", source)
    return len(VISIBLE_RE.findall(source))


def _items(segment: str) -> list[str]:
    matches = list(ITEM_RE.finditer(segment)) or list(PLAIN_ITEM_RE.finditer(segment))
    result: list[str] = []
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(segment)
        item = segment[match.end():stop]
        item = re.split(r"\\end\{(?:enumerate|description|itemize)\}", item, maxsplit=1)[0]
        result.append(item)
    return result


def check_segment(path: Path, segment: str) -> list[AssumptionIssue]:
    issues: list[AssumptionIssue] = []
    items = _items(segment)
    if not items:
        body = ASSUMPTION_HEADING_RE.sub("", segment)
        if not visible_units(body):
            return [AssumptionIssue(path, "模型假设章节为空")]
        issues.append(AssumptionIssue(path, "模型假设使用连续叙述；建议按必要假设分条，不要求固定数量", "warning"))
    if LONG_LABEL_RE.search(segment):
        issues.append(AssumptionIssue(path, "假设列表使用了过长的字母标签；建议检查最终排版是否挤压正文", "warning"))
    if INTERNAL_RE.search(segment):
        # These literal control/report tokens are actionable. Ordinary terms
        # such as “求解程序/审计” may describe the modeled domain.
        internal = re.search(r"质量门|证伪触发|ok\s*=\s*true|feature\s+flag|quality\s+gate|audit\s+status|对应开关|可切换参数", segment, re.I)
        issues.append(AssumptionIssue(path, "模型假设含程序开关、审计或质量门等内部工程表述", "error" if internal else "warning"))
    if METHOD_RE.search(segment):
        issues.append(AssumptionIssue(path, "模型假设出现求解方法；请区分算法适用前提与求解步骤，不凭关键词判错", "warning"))
    for index, item in enumerate(items, start=1):
        units = visible_units(item)
        sentences = len(re.findall(r"[。！？!?]|(?<!\d)\.(?!\d)", _strip_comments(item)))
        if not units:
            issues.append(AssumptionIssue(path, f"第 {index} 条假设为空"))
        if units > 135 or sentences > 2:
            issues.append(AssumptionIssue(path, f"第 {index} 条假设较长；建议核对是否包含可移至模型章节的内容", "warning"))
    return issues


def check_paper(paper_dir: Path) -> list[AssumptionIssue]:
    issues: list[AssumptionIssue] = []
    for document in expanded_documents(paper_dir):
        source = document.text
        for heading in ASSUMPTION_HEADING_RE.finditer(source):
            next_section = NEXT_SECTION_RE.search(source, heading.end())
            stop = next_section.start() if next_section else len(source)
            segment = source[heading.start():stop]
            issues.extend(check_segment(Path(document.location(heading.start(), paper_dir)), segment))
    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_dir", type=Path)
    args = parser.parse_args(argv[1:])
    issues = check_paper(args.paper_dir.resolve())
    for issue in issues:
        print(f"{'FAIL' if issue.severity == 'error' else 'WARN'}: {issue.path}: {issue.message}")
    if any(issue.severity == "error" for issue in issues):
        return 1
    print("OK: 模型假设无确定性缺陷；数量、长度和方法关键词仅作写作建议")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
