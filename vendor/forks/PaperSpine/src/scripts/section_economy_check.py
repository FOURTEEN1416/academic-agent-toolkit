#!/usr/bin/env python3
"""Section-economy guidance for PaperSpine manuscripts.

Applied journal/conference papers run roughly 4-6 top-level sections. Emitting
one section per idea can make a paper feel fragmented, but section count is not
editorial quality. The default run therefore reports an advisory and leaves the
architecture to the Agent. Explicit strict review may opt into enforcement.

Standard library only. Exit code 1 is used only with ``--enforce``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_MAX_SECTIONS = 6
STUB_UNITS = 120  # ~1-2 paragraphs of content (CJK chars + Latin words)


@dataclass
class SectionFinding:
    severity: str
    message: str


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def find_main_tex(target: Path) -> Path | None:
    if target.is_file():
        return target
    for rel in ("final_paper/main.tex", "main.tex"):
        candidate = target / rel
        if candidate.exists():
            return candidate
    return None


def numbered_sections(text: str) -> list[tuple[str, str]]:
    """Return (title, body) for each non-starred top-level \\section in the body."""
    doc_start = text.find("\\begin{document}")
    body = text[doc_start:] if doc_start != -1 else text
    cut = re.search(r"\\begin\{thebibliography\}|\\bibliography\b|\\end\{document\}", body)
    region = body[: cut.start()] if cut else body

    matches = list(re.finditer(r"\\section(\*)?\s*\{([^{}]*)\}", region))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        if match.group(1):  # starred section: abstract/keywords/acknowledgements
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(region)
        sections.append((match.group(2).strip(), region[start:end]))
    return sections


def content_units(body: str) -> int:
    stripped = re.sub(r"\\[a-zA-Z@]+\*?", " ", body)
    stripped = re.sub(r"[{}\[\]]", " ", stripped)
    cjk = len(re.findall(r"[一-鿿]", stripped))
    words = len(re.findall(r"[A-Za-z]+", stripped))
    return cjk + words


def check(text: str, max_sections: int, enforce: bool = False) -> tuple[int, list[SectionFinding]]:
    sections = numbered_sections(text)
    count = len(sections)
    findings: list[SectionFinding] = []

    if count > max_sections:
        titles = ", ".join(title or "(untitled)" for title, _ in sections)
        findings.append(SectionFinding(
            "error" if enforce else "advisory",
            f"{count} top-level sections exceeds the orientation value of {max_sections}. "
            "Review whether the architecture is fragmented, but keep additional sections when "
            "they perform distinct venue-appropriate intellectual jobs. "
            f"Sections: {titles}.",
        ))

    sized = [(content_units(body), title) for title, body in sections]
    for index, (size, title) in enumerate(sized):
        is_last = index == len(sized) - 1
        if not is_last and size < STUB_UNITS:
            findings.append(SectionFinding(
                "warning",
                f"Section '{title or '(untitled)'}' has only ~{size} content units "
                "(about 1-2 paragraphs); consider merging it into an adjacent section.",
            ))
    return count, findings


def render_markdown(
    path: Path, count: int, max_sections: int, findings: list[SectionFinding], enforce: bool = False
) -> str:
    errors = [f for f in findings if f.severity == "error"]
    lines = [
        "# Section Economy Check",
        "",
        f"- Manuscript: `{path}`",
        f"- Top-level sections: {count}",
        f"- Orientation value (max): {max_sections}",
        f"- Enforcement: {'strict' if enforce else 'advisory'}",
        f"- Status: {'FAIL' if errors else 'PASS_WITH_ADVISORIES' if findings else 'PASS'}",
        "",
    ]
    if findings:
        lines.append("| Severity | Message |")
        lines.append("|---|---|")
        for item in findings:
            lines.append(f"| {item.severity} | {item.message.replace('|', chr(92) + '|')} |")
    else:
        lines.append("No section-economy advisory.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check top-level section economy of a manuscript.")
    parser.add_argument("target", type=Path, help="main.tex or an output directory containing final_paper/main.tex")
    parser.add_argument("--max-sections", type=int, default=DEFAULT_MAX_SECTIONS)
    parser.add_argument("--enforce", action="store_true", help="Fail when the orientation value is exceeded.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)

    tex_path = find_main_tex(args.target)
    if tex_path is None:
        print(f"main.tex not found at: {args.target}", file=sys.stderr)
        return 2

    text = read_text(tex_path)
    count, findings = check(text, args.max_sections, enforce=args.enforce)

    if args.json:
        print(json.dumps(
            {
                "manuscript": str(tex_path),
                "section_count": count,
                "max_sections": args.max_sections,
                "ok": not any(f.severity == "error" for f in findings),
                "findings": [asdict(f) for f in findings],
            },
            ensure_ascii=False,
            indent=2,
        ))
    if args.markdown or not args.json:
        print(render_markdown(tex_path, count, args.max_sections, findings, enforce=args.enforce))

    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
