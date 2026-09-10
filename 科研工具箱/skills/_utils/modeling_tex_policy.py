#!/usr/bin/env python3
"""Normalize and verify structural rules for mathematical-modeling papers."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import active_sources, strip_comments


FORBIDDEN = ("tableofcontents", "listoftables", "listoffigures")
COMMAND_RE = re.compile(r"\\(" + "|".join(FORBIDDEN) + r")\b(?:\s*\{\s*\})?")
MARKDOWN_DIRECTORY_RE = re.compile(
    r"^\s*(?:\[TOC\]|#{1,6}\s*(?:目录|插图目录|表格目录|"
    r"table\s+of\s+contents|contents|list\s+of\s+figures|list\s+of\s+tables)\s*)$",
    re.IGNORECASE,
)
UNNUMBERED_ENV_RE = re.compile(
    r"\\begin\s*\{\s*(equation|align|gather|multline|flalign|alignat)\*\s*\}",
    re.IGNORECASE,
)
DISPLAYMATH_ENV_RE = re.compile(r"\\begin\s*\{\s*displaymath\s*\}", re.IGNORECASE)
# Match the display-math opener ``\[`` but not the line-break spacing syntax
# ``\\[2pt]`` commonly used inside TikZ nodes and tables.
BRACKET_DISPLAY_RE = re.compile(r"(?<!\\)\\\[")
DOUBLE_DOLLAR_RE = re.compile(r"(?<!\\)\$\$")
PAGE_BREAK_LINE_RE = re.compile(r"^\s*\\(newpage|clearpage)\s*$", re.IGNORECASE)
SECTION_INPUT_RE = re.compile(r"\\input\s*\{\s*sections/([^}]+)\}", re.IGNORECASE)
SPECIAL_SECTION_RE = re.compile(
    r"abstract|summary|摘要|appendix|appendices|附录|reference|references|"
    r"bibliography|参考文献",
    re.IGNORECASE,
)
SPECIAL_BOUNDARY_RE = re.compile(
    r"\\(?:input|include)\s*\{[^}]*(?:appendix|reference|bibliograph|附录|参考文献)[^}]*\}"
    r"|\\begin\s*\{(?:appendices|thebibliography|landscape|sidewaysfigure|sidewaystable)\}"
    r"|\\end\s*\{(?:landscape|sidewaysfigure|sidewaystable)\}"
    r"|\\(?:printbibliography|bibliography)\b"
    r"|\\(?:section|section\*)\s*\{[^}]*(?:附录|参考文献|Appendix|References)[^}]*\}",
    re.IGNORECASE,
)
MODELING_CLASS_RE = re.compile(
    r"\\documentclass(?:\[[^\]]*\])?\{(?:cumcmthesis|gmcmthesis|"
    r"MathorCupmodeling|JXUSTmodeling|yrdmcm|neepumcm|nemcmthesis|"
    r"mcmthesis|apmcmthesis)\}",
    re.IGNORECASE,
)


def _split_comment(line: str) -> tuple[str, str]:
    """Split a TeX line at its first unescaped percent sign."""
    for pos, char in enumerate(line):
        if char != "%":
            continue
        slash_count = 0
        cursor = pos - 1
        while cursor >= 0 and line[cursor] == "\\":
            slash_count += 1
            cursor -= 1
        if slash_count % 2 == 0:
            return line[:pos], line[pos:]
    return line, ""


def is_modeling_paper(paper_dir: Path, source: str) -> bool:
    root = paper_dir.parent
    markers = (
        root / "PROBLEM_ANALYSIS.md",
        root / "MODELING_REPORT.md",
        root / "PROBLEM_FACTS.json",
    )
    if any(marker.exists() for marker in markers):
        return True
    if MODELING_CLASS_RE.search(source):
        return True
    claude = root / "CLAUDE.md"
    if claude.exists():
        text = claude.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"数学建模|mathematical\s+model", text, re.IGNORECASE):
            return True
    return False


def active_commands(source: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for number, line in enumerate(source.splitlines(), start=1):
        active, _comment = _split_comment(line)
        found.extend((number, match.group(1)) for match in COMMAND_RE.finditer(active))
    return found


def markdown_directory_markers(source: str) -> list[tuple[int, str]]:
    """Return explicit Markdown TOC/list headings and ``[TOC]`` directives."""
    return [
        (number, line.strip())
        for number, line in enumerate(source.splitlines(), start=1)
        if MARKDOWN_DIRECTORY_RE.fullmatch(line)
    ]


def normalize(source: str) -> tuple[str, int]:
    changed = 0
    output: list[str] = []
    for line in source.splitlines(keepends=True):
        active, comment = _split_comment(line)
        active, count = COMMAND_RE.subn("", active)
        changed += count
        output.append(active + comment)
    return "".join(output), changed


def active_unnumbered_displays(source: str) -> list[tuple[int, str]]:
    """Return active unnumbered display-math openings, ignoring TeX comments."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(source.splitlines(), start=1):
        active, _comment = _split_comment(line)
        for match in UNNUMBERED_ENV_RE.finditer(active):
            found.append((number, f"{match.group(1)}*"))
        if DISPLAYMATH_ENV_RE.search(active):
            found.append((number, "displaymath"))
        if BRACKET_DISPLAY_RE.search(active):
            found.append((number, r"\["))
        if DOUBLE_DOLLAR_RE.search(active):
            found.append((number, "$$"))
    return found


def paper_unnumbered_displays(paper_dir: Path) -> list[tuple[Path, int, str]]:
    found: list[tuple[Path, int, str]] = []
    for tex_file in active_sources(paper_dir):
        source = tex_file.read_text(encoding="utf-8", errors="ignore")
        found.extend(
            (Path(os.path.relpath(tex_file, paper_dir)), line, token)
            for line, token in active_unnumbered_displays(source)
        )
    return found


def _body_start_line(source: str) -> int | None:
    """Locate the first real body section input, excluding abstract/summary files."""
    for number, line in enumerate(source.splitlines(), start=1):
        active, _comment = _split_comment(line)
        if r"\label{mh:body-start}" in active:
            return number
        match = SECTION_INPUT_RE.search(active)
        if match and not re.search(r"abstract|summary|摘要", match.group(1), re.IGNORECASE):
            return number
    return None


def active_page_breaks(source: str, *, start_line: int = 1) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for number, line in enumerate(source.splitlines(), start=1):
        if number < start_line:
            continue
        active, _comment = _split_comment(line)
        match = PAGE_BREAK_LINE_RE.fullmatch(active)
        if match:
            found.append((number, match.group(1)))
    return found


def structural_page_breaks(source: str, *, start_line: int = 1) -> list[tuple[int, str]]:
    """Return unsafe manual body breaks while preserving explicit special boundaries.

    Appendix, bibliography and landscape boundaries sometimes require a real page flush.
    Those are not the source of the stranded-line defect and must remain untouched.
    """
    active_lines = [_split_comment(line)[0].strip() for line in source.splitlines()]
    found: list[tuple[int, str]] = []
    for number, token in active_page_breaks(source, start_line=start_line):
        index = number - 1
        previous = next((active_lines[i] for i in range(index - 1, -1, -1) if active_lines[i]), "")
        following = next((active_lines[i] for i in range(index + 1, len(active_lines)) if active_lines[i]), "")
        if SPECIAL_BOUNDARY_RE.search(previous) or SPECIAL_BOUNDARY_RE.search(following):
            continue
        found.append((number, token))
    return found


def _remove_page_breaks(source: str, *, line_numbers: set[int]) -> tuple[str, int]:
    output: list[str] = []
    changed = 0
    for number, line in enumerate(source.splitlines(keepends=True), start=1):
        active, comment = _split_comment(line.rstrip("\r\n"))
        ending = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
        if number in line_numbers and PAGE_BREAK_LINE_RE.fullmatch(active):
            changed += 1
            output.append((comment if comment else "") + ending)
        else:
            output.append(line)
    return "".join(output), changed


def paper_body_page_breaks(paper_dir: Path) -> list[tuple[Path, int, str]]:
    found: list[tuple[Path, int, str]] = []
    main_tex = paper_dir / "main.tex"
    if main_tex.is_file():
        source = main_tex.read_text(encoding="utf-8", errors="ignore")
        start = _body_start_line(source)
        if start is not None:
            found.extend((Path("main.tex"), line, token) for line, token in structural_page_breaks(source, start_line=start + 1))
    sections = paper_dir / "sections"
    if sections.is_dir():
        for tex_file in active_sources(paper_dir):
            if tex_file.resolve() == main_tex.resolve() or not tex_file.is_relative_to(sections.resolve()):
                continue
            if SPECIAL_SECTION_RE.search(tex_file.stem):
                continue
            source = tex_file.read_text(encoding="utf-8", errors="ignore")
            found.extend(
                (tex_file.relative_to(paper_dir), line, token)
                for line, token in structural_page_breaks(source)
            )
    return found


def normalize_body_page_breaks(paper_dir: Path) -> int:
    changed = 0
    main_tex = paper_dir / "main.tex"
    if main_tex.is_file():
        source = main_tex.read_text(encoding="utf-8", errors="ignore")
        start = _body_start_line(source)
        if start is not None:
            unsafe = structural_page_breaks(source, start_line=start + 1)
            normalized, count = _remove_page_breaks(
                source, line_numbers={line for line, _token in unsafe}
            )
            if count:
                main_tex.write_text(normalized, encoding="utf-8", newline="")
                changed += count
    sections = paper_dir / "sections"
    if sections.is_dir():
        for tex_file in active_sources(paper_dir):
            if tex_file.resolve() == main_tex.resolve() or not tex_file.is_relative_to(sections.resolve()):
                continue
            if SPECIAL_SECTION_RE.search(tex_file.stem):
                continue
            source = tex_file.read_text(encoding="utf-8", errors="ignore")
            unsafe = structural_page_breaks(source)
            normalized, count = _remove_page_breaks(
                source, line_numbers={line for line, _token in unsafe}
            )
            if count:
                tex_file.write_text(normalized, encoding="utf-8", newline="")
                changed += count
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("normalize", "check"))
    parser.add_argument("paper_dir", type=Path)
    args = parser.parse_args()

    paper_dir = args.paper_dir.resolve()
    main_tex = paper_dir / "main.tex"
    main_md = paper_dir / "main.md"
    if not main_tex.exists() and not main_md.exists():
        print(f"SKIP: neither {main_tex} nor {main_md} exists")
        return 0

    source_path = main_tex if main_tex.exists() else main_md
    source = source_path.read_text(encoding="utf-8", errors="ignore")
    if not is_modeling_paper(paper_dir, source):
        print("SKIP: non-modeling paper")
        return 0

    if source_path == main_md:
        markers = markdown_directory_markers(source)
        if markers:
            for line, marker in markers:
                print(f"FAIL: Markdown directory marker {marker!r} at main.md:{line}")
            return 1
        print("OK: Markdown modeling paper has no body/figure/table directory")
        return 0

    if args.mode == "normalize":
        normalized, count = normalize(source)
        if count:
            main_tex.write_text(normalized, encoding="utf-8", newline="")
            for suffix in ("toc", "lof", "lot"):
                stale = paper_dir / f"main.{suffix}"
                if stale.exists():
                    stale.unlink()
        page_break_count = normalize_body_page_breaks(paper_dir)
        print(
            "OK: modeling structural policy normalized "
            f"({count} directory command(s), {page_break_count} body page break(s) removed)"
        )
        return 0

    directory_commands = active_commands(source)
    unnumbered_displays = paper_unnumbered_displays(paper_dir)
    body_page_breaks = paper_body_page_breaks(paper_dir)
    if directory_commands or unnumbered_displays or body_page_breaks:
        for line, command in directory_commands:
            print(f"FAIL: active \\{command} at main.tex:{line}")
        for tex_file, line, token in unnumbered_displays:
            print(f"FAIL: unnumbered display math {token} at {tex_file}:{line}")
        for tex_file, line, token in body_page_breaks:
            print(f"FAIL: forced body page break \\{token} at {tex_file}:{line}")
        return 1
    print("OK: no directories/forced body page breaks; all display formulas are numbered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
