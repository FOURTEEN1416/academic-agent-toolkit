#!/usr/bin/env python3
"""Writing-stage structure plus bounded advisories, using active sources only."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import active_sources, strip_comments
from compile_source_check import check_sources


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper", type=Path)
    args = parser.parse_args()
    paper = args.paper.resolve()
    sources = active_sources(paper)
    # Markdown/DOCX is checked by its dedicated document contract. TeX leftovers
    # are not inferred from every file in the workspace.
    if not sources:
        print("INFO: no active TeX source; document-mode checks remain separate")
        return 0
    errors, warnings = check_sources(paper, compiled=False)
    joined = "\n".join(strip_comments(p.read_text(encoding="utf-8")) for p in sources)
    # Sentence style, caption length and list count do not prove bad content.
    for match in re.finditer(r"\\caption\*?\s*(?:\[[^]]*\])?\s*\{", joined):
        start = pos = match.end()
        depth = 1
        while pos < len(joined) and depth:
            if joined[pos] == "{" and (pos == 0 or joined[pos-1] != "\\"):
                depth += 1
            elif joined[pos] == "}" and (pos == 0 or joined[pos-1] != "\\"):
                depth -= 1
            pos += 1
        content = joined[start:pos-1]
        if len(re.findall(r"[\u4e00-\u9fff]", content)) > 20 or len(re.findall(r"\b[A-Za-z]+\b", content)) > 14:
            warnings.append("题注较长：建议精简重复结论，但保留必要的变量、面板与不确定性说明；以最终排版为准")
    if len(re.findall(r"\\begin\{(?:itemize|enumerate)\}", joined)) > 3:
        warnings.append("列表较多，检查是否适合改为连贯论述；算法步骤与假设列表不因数量自动失败")
    if re.search(r"(?im)^\s*(?:图|表|Figure|Table)\s*(?:\\ref|\d)", joined):
        warnings.append("图表起句可适当变化；不因使用正常的图表引用句式而返修")
    # Verify only the bibliography files selected by the current manuscript.
    unavailable = False
    bibs = set()
    for group in re.findall(r"\\(?:bibliography|addbibresource)\s*(?:\[[^]]*\])?\{([^{}]+)\}", joined):
        for name in group.split(","):
            rel = Path(name.strip())
            if not rel.suffix:
                rel = rel.with_suffix(".bib")
            for base in [paper, paper.parent, *(p.parent for p in sources)]:
                candidate = (base / rel).resolve()
                if candidate.is_file():
                    bibs.add(candidate)
                    break
    for bib in sorted(bibs):
        try:
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("bib_authenticity_check.py")), "--bib", str(bib)], timeout=90, check=False)
            if result.returncode == 1:
                errors.append(f"{bib.name}: 文献核验发现明确错误，见上方证据")
            elif result.returncode not in (0, 2):
                unavailable = True
        except (OSError, subprocess.TimeoutExpired):
            unavailable = True
    for warning in dict.fromkeys(warnings):
        print("WARN: " + warning)
    for error in errors:
        print("FAIL: " + error)
    if unavailable:
        print("[CHECK_UNAVAILABLE] 文献检查未完成，不得自动重写论文")
        return 3
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
