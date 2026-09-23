#!/usr/bin/env python3
"""Structural checks on active TeX sources; no size/row-count proxies."""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import active_sources, strip_comments


def check_sources(paper: Path, *, compiled: bool = True) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    sources = active_sources(paper)
    texts = [(p, strip_comments(p.read_text(encoding="utf-8", errors="replace"))) for p in sources]
    joined = "\n".join(text for _, text in texts)
    labels = Counter(re.findall(r"\\label\s*\{([^{}]+)\}", joined))
    errors.extend(f"重复 label：{key} ({count} 次)" for key, count in labels.items() if count > 1)
    for source, text in texts:
        graphic_dirs = [paper, source.parent, paper.parent, paper.parent / "figures"]
        for group in re.findall(r"\\graphicspath\s*\{((?:\s*\{[^{}]*\})+)\s*\}", joined):
            graphic_dirs.extend(paper / x for x in re.findall(r"\{([^{}]*)\}", group))
        for match in re.finditer(r"\\includegraphics\*?\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}", text):
            name = match.group(1).strip()
            if any(c in name for c in ("\\", "#", "$")):
                warnings.append(f"{source.name}: 动态图片路径需由 TeX 编译核对")
                continue
            rel = Path(name)
            candidates = [base / rel for base in graphic_dirs]
            if not rel.suffix:
                candidates = [p.with_suffix(ext) for p in candidates for ext in (".pdf", ".png", ".jpg", ".jpeg", ".eps")]
            if not any(p.is_file() for p in candidates):
                errors.append(f"{source.name}:{text.count(chr(10),0,match.start())+1}: 引用图片不存在：{name}")
        # No blanket rejection of custom float content: explicit empty/caption
        # only environments are clear, unknown macros need rendered evidence.
        for match in re.finditer(r"\\begin\{(figure|table)\*?\}(?:\[[^\]]*\])?([\s\S]*?)\\end\{\1\*?\}", text):
            content = re.sub(r"\\(?:caption|label)\s*\{[^{}]*\}|\\centering", "", match.group(2))
            if not content.strip():
                errors.append(f"{source.name}: {match.group(1)} 环境只有题注或为空")
    cites = re.findall(r"\\(?:cite\w*|upcite)\*?\s*(?:\[[^\]]*\]\s*)*\{([^{}]+)\}", joined)
    if not cites:
        errors.append("正文没有文献引用")
    inline = bool(re.search(r"\\begin\{thebibliography\}", joined))
    bibs = re.findall(r"\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\])?\{([^{}]+)\}", joined)
    if inline:
        if not re.search(r"\\bibitem\s*(?:\[[^\]]*\])?\{", joined):
            errors.append("参考文献环境为空")
    elif bibs:
        for names in bibs:
            for name in names.split(","):
                rel = Path(name.strip())
                if not rel.suffix:
                    rel = rel.with_suffix(".bib")
                if not any((base / rel).is_file() for base in [paper, paper.parent, *(p.parent for p in sources)]):
                    errors.append(f"指定文献库不存在：{rel}")
        bbl = paper / "main.bbl"
        if compiled and (not bbl.is_file() or not re.search(r"\\(?:bibitem|entry)\b", bbl.read_text(encoding="utf-8", errors="replace"))):
            errors.append("最终文献尚未编译或为空，请运行模板对应的 BibTeX/Biber")
    else:
        errors.append("实际引用的源码中未找到参考文献区或文献库声明")
    return errors, warnings


def check_pdf(pdf: Path) -> list[str]:
    if not pdf.is_file():
        return ["main.pdf 不存在"]
    try:
        import fitz
        with fitz.open(pdf) as doc:
            if doc.needs_pass or len(doc) == 0:
                return ["最终 PDF 加密或没有页面"]
            for page in doc:
                page.get_text()  # force page parsing; byte count is not validity
    except ImportError:
        return ["[CHECK_UNAVAILABLE] 缺少 PyMuPDF，无法验证 PDF 完整性"]
    except Exception as exc:
        return [f"最终 PDF 无法解析：{type(exc).__name__}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper", type=Path)
    args = parser.parse_args()
    try:
        errors, warnings = check_sources(args.paper.resolve())
    except (OSError, ValueError, RecursionError) as exc:
        print(f"[CHECK_UNAVAILABLE] 无法解析当前源码：{type(exc).__name__}")
        return 3
    errors.extend(check_pdf(args.paper / "main.pdf"))
    for warning in warnings:
        print("WARN: " + warning)
    for error in errors:
        print("FAIL: " + error)
    if not errors:
        print("OK: 活跃源码引用、图片、文献和 PDF 结构通过")
    return 3 if any("[CHECK_UNAVAILABLE]" in x for x in errors) else int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
