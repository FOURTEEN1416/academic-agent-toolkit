#!/usr/bin/env python3
"""Fail when LaTeX figures/tables are pasted without substantive prose.

Usage: python figure_narrative_check.py paper/

Two criteria, both zero-tolerance (orphan-figure iron rule):
1. zero-reference orphan: the float carries a label but the full paper never
   \\refs it. Prose next to the float does not excuse a missing citation --
   "as shown below" style narration is not a reference.
2. no narrative: the float is referenced but has no readable prose around it.

The check is deliberately content-oriented rather than line-oriented: LaTeX
paragraphs are often one physical line.  It measures readable characters before
and after each float, bounded by nearby floats or section headings.

Skip semantics: when no TeX body is found the script prints SKIP and exits 2
(skip must never masquerade as a pass; the engine wrapper treats 2 the same).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import expanded_documents, strip_comments


FLOAT_RE = re.compile(
    r"\\begin\{(?P<kind>figure|table)\*?\}[\s\S]*?"
    r"\\end\{(?P=kind)\*?\}",
    re.IGNORECASE,
)
BOUNDARY_RE = re.compile(
    r"\\(?:part|chapter|section|subsection|subsubsection)\*?\s*(?:\[[^\]]*\])?\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
    re.IGNORECASE,
)


def _readable_length(text: str) -> int:
    text = re.sub(r"(?m)(?<!\\)%.*$", "", text)
    text = re.sub(r"\\(?:label|ref|pageref|cite|upcite)\*?\{[^{}]*\}", "", text)
    text = re.sub(r"\\(?:begin|end|input|include|bibliography)\s*\{[^{}]*\}", "", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", "", text)
    text = re.sub(r"[{}$&_~^\\\s]", "", text)
    return len(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text))


def check_text(text: str, location, references: set[str] | None = None) -> list[str]:
    floats = list(FLOAT_RE.finditer(text))
    outside = FLOAT_RE.sub("", text)
    if references is None:
        references = {name.strip() for group in re.findall(
            r"\\(?:ref|autoref|cref|Cref|pageref)\s*\{([^{}]+)\}", outside
        ) for name in group.split(",")}
    issues: list[str] = []
    for index, match in enumerate(floats):
        kind = match.group("kind").lower()
        if kind == "table":
            headings_before = list(BOUNDARY_RE.finditer(text, 0, match.start()))
            section_start = headings_before[-1].start() if headings_before else 0
            context = text[max(section_start, match.start() - 800) : match.start()]
            if re.search(r"符号说明|主要符号|notation|symbol", context, re.IGNORECASE):
                continue  # notation tables define vocabulary; they do not need result analysis

        head = text[: match.start()]
        previous_float_end = floats[index - 1].end() if index else 0
        headings = list(BOUNDARY_RE.finditer(head, previous_float_end))
        previous_heading_end = headings[-1].end() if headings else 0
        lead_start = max(previous_float_end, previous_heading_end)
        lead = text[lead_start : match.start()]
        lead_readable = _readable_length(lead)

        tail = text[match.end() :]
        next_float = floats[index + 1].start() - match.end() if index + 1 < len(floats) else None
        next_heading_match = BOUNDARY_RE.search(tail)
        next_heading = next_heading_match.start() if next_heading_match else None
        stops = [value for value in (next_float, next_heading) if value is not None]
        stop = min(stops) if stops else len(tail)
        prose = tail[:stop]
        readable = _readable_length(prose)
        # One explanation may introduce a group of floats, or reference them
        # elsewhere. Do not require a paragraph on both sides of every float.
        labels = re.findall(r"\\label\s*\{([^{}]+)\}", match.group())
        referenced = any(label in references for label in labels)
        if not referenced:
            issues.append(
                f"{location(match.start())} {match.group('kind')} 零引用孤儿：全文无 \\ref 引用该浮动体的"
                " label（旁有叙述不豁免，「如下图所示」不算引用）——补 \\ref 引用句或删图"
            )
        elif readable == 0 and lead_readable == 0:
            issues.append(
                f"{location(match.start())} {match.group('kind')} 被引用但前后无解读文字"
                "（不要求两侧各写一段）"
            )
    return issues


def check_file(path: Path) -> list[str]:
    text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    return check_text(text, lambda offset: f"{path.name}:{text.count(chr(10), 0, offset) + 1}")


def collect_references(documents) -> set[str]:
    refs: set[str] = set()
    for document in documents:
        outside = FLOAT_RE.sub("", document.text)
        for group in re.findall(r"\\(?:ref|autoref|cref|Cref|pageref)\s*\{([^{}]+)\}", outside):
            refs.update(name.strip() for name in group.split(","))
    return refs


def check_paper(paper_dir: Path):
    documents = expanded_documents(paper_dir)
    if not documents:
        return None
    references = collect_references(documents)
    return [issue for document in documents
            for issue in check_text(document.text,
                                    lambda offset, doc=document: doc.location(offset, paper_dir),
                                    references=references)]


def main() -> int:
    paper_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "paper")
    if not paper_dir.is_dir():
        print(f"  SKIP: 未找到论文目录 {paper_dir}（SKIP 不冒充通过，exit 2）")
        return 2
    issues = check_paper(paper_dir)
    if issues is None:
        print(f"  SKIP: {paper_dir} 下未找到 TeX 正文（SKIP 不冒充通过，exit 2）")
        return 2
    if issues:
        for issue in issues:
            print(f"  FAIL {issue}")
        return 1
    print("  OK: 每个图/表均被正文引用且有叙述")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
