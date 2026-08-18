#!/usr/bin/env python3
"""评分脚本：comp-paper-zh P0 基准。读取工作区 paper/main.tex 并按章节结构评分。"""
import json
import re
import sys
from pathlib import Path


SECTION_PATTERNS = [
    # 摘要：\section{摘要} 或注释 % ===== 摘要 =====
    r"(?:\\section\*?\{?\s*摘要|%+\s*={3,}\s*摘要)",
    r"\\section\*?\{?\s*问题重述",
    r"\\section\*?\{?\s*问题分析",
    r"\\section\*?\{?\s*模型假设",
    r"\\section\*?\{?\s*符号说明",
    # 模型建立与求解：兼容 "问题一的建模与求解" 等变体
    r"\\section\*?\{?\s*(?:模型建立|问题.的建模|模型建立与求解)",
    # 模型检验：兼容 "灵敏度分析与模型检验" 等变体
    r"\\section\*?\{?\s*(?:模型检验|灵敏度分析与模型检验)",
    r"\\section\*?\{?\s*模型评价",
    # 参考文献：\section 或注释
    r"(?:\\section\*?\{?\s*参考文献|%+\s*={3,}\s*参考文献)",
    # 附录：\section 或注释
    r"(?:\\section\*?\{?\s*附录|%+\s*={3,}\s*附录)",
]

REQUIRED_MIN = 8


def score(workspace: Path) -> dict:
    results = {}
    tex = workspace / "paper" / "main.tex"
    if not tex.exists():
        results["file_paper_main_tex"] = False
        results.update({
            "structure_count": 0, "structure_ok": False,
            "has_abstract": False, "has_references": False, "has_appendix": False,
            "size_bytes": 0, "size_ok": False, "all_pass": False,
        })
        return results
    results["file_paper_main_tex"] = True
    content = tex.read_text(encoding="utf-8", errors="ignore")
    results["size_bytes"] = len(content.encode("utf-8"))
    results["size_ok"] = results["size_bytes"] >= 10000

    # 章节命中
    hits = {}
    for pattern in SECTION_PATTERNS:
        hits[pattern] = bool(re.search(pattern, content, re.MULTILINE))
    results["structure_count"] = sum(hits.values())
    results["structure_ok"] = results["structure_count"] >= REQUIRED_MIN
    results["has_abstract"] = hits[SECTION_PATTERNS[0]]
    results["has_references"] = hits[SECTION_PATTERNS[8]]
    results["has_appendix"] = hits[SECTION_PATTERNS[9]]

    results["all_pass"] = all([
        results["file_paper_main_tex"],
        results["structure_ok"],
        results["has_abstract"],
        results["has_references"],
        results["has_appendix"],
        results["size_ok"],
    ])
    results["required_checks"] = [
        "file_paper_main_tex", "structure_ok", "has_abstract",
        "has_references", "has_appendix", "size_ok",
    ]
    return results


if __name__ == "__main__":
    ws = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    r = score(ws)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r.get("all_pass") else 1)