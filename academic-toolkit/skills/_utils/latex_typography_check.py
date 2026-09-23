#!/usr/bin/env python3
"""Reject accidental underlines and CJK font substitution in competition TeX.

Usage: python latex_typography_check.py paper/
Exit codes: 0=pass, 1=release blocker, 2=no TeX source.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import active_sources, strip_comments, source_label


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


VERBATIM_ENV = re.compile(
    r"\\begin\{(?P<env>lstlisting|verbatim|minted)\}.*?"
    r"\\end\{(?P=env)\}",
    re.DOTALL,
)
UNDERLINE = re.compile(r"\\(?:underline|uline|uuline|uwave|sout|xout)\s*\{")
EMPH = re.compile(r"\\emph\s*\{")
BARE_ULEM = re.compile(r"\\(?:RequirePackage|usepackage)\s*\{ulem\}")


def _strip_tex_comments(text: str) -> str:
    text = VERBATIM_ENV.sub("", text)
    active: list[str] = []
    for line in text.splitlines():
        cut = len(line)
        for match in re.finditer("%", line):
            idx = match.start()
            slashes = 0
            j = idx - 1
            while j >= 0 and line[j] == "\\":
                slashes += 1
                j -= 1
            if slashes % 2 == 0:
                cut = idx
                break
        active.append(line[:cut])
    return "\n".join(active)


def _source_files(root: Path) -> list[Path]:
    files = active_sources(root)
    if not (root / "main.tex").is_file():
        files.extend(sorted(root.glob("*.cls")))
        files.extend(sorted(root.glob("*.sty")))
    for source in files:
        text = strip_comments(source.read_text(encoding="utf-8", errors="replace"))
        for command, names in re.findall(r"\\(documentclass|LoadClass|usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}", text):
            for name in names.split(","):
                candidate = (root / (name.strip() + (".cls" if command in {"documentclass", "LoadClass"} else ".sty"))).resolve()
                if candidate.is_relative_to(root.resolve()) and candidate.is_file() and candidate not in files:
                    files.append(candidate)
    return files


def check(root: Path) -> list[str]:
    # active_sources resolves paths (including Windows 8.3 aliases). Keep the
    # base canonical too, otherwise relative_to raises before any check runs.
    root = root.resolve()
    files = _source_files(root)
    if not files:
        return ["NO_TEX_SOURCE"]

    active: dict[Path, str] = {}
    for path in files:
        active[path] = _strip_tex_comments(
            path.read_text(encoding="utf-8", errors="replace")
        )

    is_chinese_paper = any(re.search(r"[\u3400-\u9fff]", text) for text in active.values())
    problems: list[str] = []

    for path, text in active.items():
        rel = source_label(path, root).as_posix()
        if path.suffix.lower() in {".cls", ".sty"} and BARE_ULEM.search(text):
            problems.append(
                f"{rel}: ulem 未使用 normalem，会把 \\emph 静默改成下划线"
            )
        if path.suffix.lower() == ".tex":
            if UNDERLINE.search(text):
                problems.append(f"{rel}: 正文含直接下划线/删除线命令")
            if is_chinese_paper and EMPH.search(text):
                problems.append(
                    f"{rel}: 中文正文使用 \\emph，易造成字体或强调样式不一致；改用普通文字或克制的 \\textbf"
                )

    log_path = root / "main.log"
    if log_path.is_file():
        log = log_path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?i)(font[^\n]{0,100}not found|cannot find font)", log):
            problems.append("main.log: 存在找不到字体的错误")
        # TeX may wrap the warning over multiple lines, so inspect a bounded
        # span after "Font shape" rather than one physical log line.
        for match in re.finditer(
            r"LaTeX Font Warning:\s*Font shape\s*`([^']+)'[^\n]{0,240}?undefined",
            log,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            shape = match.group(1)
            if re.search(r"(?i)(simsun|simhei|kaiti|fang|song|hei|kai|cjk)", shape):
                problems.append(f"main.log: 中文字体形状未定义并被替代：{shape}")
        # Font substitution and synthetic size warnings are visible layout
        # changes.  Treat every LaTeX font warning as a release blocker rather
        # than trying to maintain a fragile allow-list of supposedly harmless
        # substitutions across TeX distributions.
        font_warnings = re.findall(r"(?mi)^LaTeX Font Warning:\s*(.+)$", log)
        for warning in dict.fromkeys(item.strip() for item in font_warnings if item.strip()):
            problems.append(f"main.log: LaTeX 字体警告：{warning[:180]}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_dir", nargs="?", default="paper")
    args = parser.parse_args()
    root = Path(args.paper_dir)
    if not root.is_dir():
        print(f"FAIL: paper directory not found: {root}")
        return 2
    problems = check(root)
    if problems == ["NO_TEX_SOURCE"]:
        print("SKIP: no TeX source (DOCX/Markdown workflow)")
        return 0
    if problems:
        print("FAIL: typography consistency check")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("PASS: no accidental underline or CJK font substitution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
