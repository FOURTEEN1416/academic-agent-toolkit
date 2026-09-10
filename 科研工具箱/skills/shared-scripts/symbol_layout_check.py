#!/usr/bin/env python3
"""Validate the compact layout contract of notation sections.

Mathematical-modeling papers use the notation section as an index, not as a
second modeling chapter. The accepted shape is: heading, one short lead
sentence, and one complete notation table. This prevents constraint prose or
transition paragraphs from being stranded after a multipage longtable.
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


SYMBOL_HEADING_RE = re.compile(
    r"\\(?:section|section\*)\s*\{[^}]*(?:符号|记号|symbols?|notations?|nomenclature)[^}]*\}",
    re.IGNORECASE,
)
NEXT_SECTION_RE = re.compile(r"\\(?:section|section\*)\s*\{")
TABLE_BEGIN_RE = re.compile(r"\\begin\{(longtable|table\*?|tabularx|tabular)\}", re.IGNORECASE)
VISIBLE_RE = re.compile(r"[\u3400-\u9fff]|[A-Za-z]+(?:[-'][A-Za-z]+)*|\d+(?:\.\d+)?")


@dataclass(frozen=True)
class LayoutIssue:
    path: Path
    message: str


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
    source = re.sub(r"\\(?:label|ref|autoref|pageref|cite)\{[^}]*\}", " ", source)
    source = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", source)
    source = re.sub(r"[{}$&_^~\\]", " ", source)
    return len(VISIBLE_RE.findall(source))


def _table_end(segment: str, begin: re.Match[str]) -> int | None:
    environment = begin.group(1)
    end = re.search(
        rf"\\end\{{{re.escape(environment)}\}}",
        segment[begin.end():],
        re.IGNORECASE,
    )
    if not end:
        return None
    return begin.end() + end.end()


def check_segment(path: Path, segment: str, heading_end: int) -> list[LayoutIssue]:
    issues: list[LayoutIssue] = []
    table = TABLE_BEGIN_RE.search(segment, heading_end)
    if not table:
        return [LayoutIssue(path, "符号说明缺少完整符号表")]
    end = _table_end(segment, table)
    if end is None:
        return [LayoutIssue(path, "符号表环境没有正确闭合")]

    intro = segment[heading_end:table.start()]
    intro_units = visible_units(intro)
    if intro_units < 4:
        issues.append(LayoutIssue(path, "符号说明表前缺少一句简短引导"))
    elif intro_units > 80 or len(re.findall(r"[。！？.!?]", _strip_comments(intro))) > 2:
        issues.append(LayoutIssue(path, "符号说明引导过长；只保留一句说明表格收录范围"))

    trailing = segment[end:]
    if visible_units(trailing) > 3:
        issues.append(LayoutIssue(path, "符号表后存在正文；约束、总结和过渡应移回对应模型章节"))
    return issues


def check_paper(paper_dir: Path) -> list[LayoutIssue]:
    issues: list[LayoutIssue] = []
    for document in expanded_documents(paper_dir):
        active_source = document.text
        for heading in SYMBOL_HEADING_RE.finditer(active_source):
            next_section = NEXT_SECTION_RE.search(active_source, heading.end())
            stop = next_section.start() if next_section else len(active_source)
            segment = active_source[heading.start():stop]
            relative_heading_end = heading.end() - heading.start()
            issues.extend(check_segment(Path(document.location(heading.start(), paper_dir)), segment, relative_heading_end))
    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_dir", type=Path)
    args = parser.parse_args(argv[1:])
    paper_dir = args.paper_dir.resolve()
    issues = check_paper(paper_dir)
    if issues:
        for issue in issues:
            print(f"FAIL: {issue.path}: {issue.message}")
        return 1
    print("OK: 符号说明均为‘一句引导 + 完整符号表’，表后无冗余正文")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
