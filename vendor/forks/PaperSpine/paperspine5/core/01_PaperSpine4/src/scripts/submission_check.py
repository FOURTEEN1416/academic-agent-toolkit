#!/usr/bin/env python3
"""Check PaperSpine submission package highlights and cover letter."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

CITATION_PATTERNS = (
    re.compile(r"\\cite[a-zA-Z]*\s*\{"),
    re.compile(r"\[@[\w:.\-]+(?:\s*;\s*@[\w:.\-]+)*\]"),
    # Numbered citations such as [1], [12], [1,2], [1-3]. Reference indices are
    # at most three digits in practice; restricting the width keeps bracketed
    # four-digit years like [2024] from being misread as citation markers.
    re.compile(r"\[\d{1,3}(?:\s*[,;\-]\s*\d{1,3})*\]"),
)
PLACEHOLDER_PATTERN = re.compile(r"\[[A-Z][A-Z0-9 /._-]{2,}\]")
TODO_PATTERN = re.compile(r"\bTODO\b|\[\[|\]\]", re.IGNORECASE)
WORD_PATTERN = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)?")
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
ORIGINALITY_PATTERNS = (
    re.compile(r"\boriginal(?:ity)?\b", re.IGNORECASE),
    re.compile(r"\bhas\s+not\s+been\s+(?:previously\s+)?published\b", re.IGNORECASE),
    re.compile(r"\bnot\s+been\s+(?:previously\s+)?published\b", re.IGNORECASE),
    re.compile(r"\bpreviously\s+unpublished\b", re.IGNORECASE),
    re.compile(r"\bunpublished\s+(?:work|manuscript|material|results?)\b", re.IGNORECASE),
    re.compile(r"原创"),
    re.compile(r"未(?:曾|经)?(?:公开)?发表"),
)
NOT_UNDER_CONSIDERATION_PATTERNS = (
    re.compile(r"not\s+(?:currently\s+)?(?:being\s+)?(?:under|in)\s+(?:active\s+)?(?:consideration|review)", re.IGNORECASE),
    re.compile(r"not\s+being\s+considered\b", re.IGNORECASE),
    re.compile(
        r"(?:will\s+not\s+be|(?:has\s+|have\s+)?not\s+(?:been\s+)?)"
        r"(?:concurrently\s+|simultaneously\s+)?submitted\s+"
        r"(?:to\s+|for\s+)?(?:any\s+)?(?:other|another|elsewhere)",
        re.IGNORECASE,
    ),
    re.compile(r"\bno\s+(?:simultaneous|concurrent|duplicate)\s+submission", re.IGNORECASE),
    re.compile(r"\bexclusively\s+(?:submitted|to)\b", re.IGNORECASE),
    re.compile(r"\bsolely\s+(?:submitted|to)\b", re.IGNORECASE),
    re.compile(r"未一稿多投"),
    re.compile(r"未同时投稿"),
    re.compile(r"未投他刊"),
    re.compile(r"未在其他期刊"),
    re.compile(r"未(?:同时)?(?:向|在)?其他?(?:刊物|期刊|杂志)(?:投稿|发表)?"),
)
REQUIRED_DOCX = (
    "cover_letter.en.docx",
    "cover_letter.zh.docx",
    "highlights.en.docx",
    "highlights.zh.docx",
)
LATIN_FONT = "Times New Roman"
EAST_ASIA_FONT = "SimSun"
A4_WIDTH_TWIPS = "11906"
A4_HEIGHT_TWIPS = "16838"
DEFAULT_MARGIN_TWIPS = "1440"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
HIGHLIGHT_SOURCE_CANDIDATES = ("highlights.en.md", "highlights.md")
COVER_SOURCE_CANDIDATES = ("cover_letter.en.md", "cover_letter.md")


@dataclass
class SubmissionCheckResult:
    output_dir: str
    language: str
    highlights_required: bool
    highlight_count: int
    cover_word_count: int
    zh_highlight_count: int
    zh_cover_word_count: int
    docx_files: list[str]
    findings: list[str]
    warnings: list[str]
    pending_items: list[str]

    @property
    def ok(self) -> bool:
        return not self.findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a PaperSpine submission package.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output/submission_package")
    parser.add_argument("--min", dest="min_highlights", type=int, default=3)
    parser.add_argument("--max", dest="max_highlights", type=int, default=5)
    parser.add_argument("--max-chars", type=int, default=85)
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write submission_check.md into the package directory.")
    parser.add_argument(
        "--fix-fonts",
        action="store_true",
        help="Rewrite required docx files so fonts and page geometry match the submission format.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def first_existing(output_dir: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = output_dir / name
        if path.exists():
            return path
    return None


def read_config(output_dir: Path) -> dict[str, object]:
    for candidate in (output_dir / "paper_spine_config.json", output_dir.parent / "paper_spine_config.json"):
        if not candidate.exists():
            continue
        try:
            return json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def output_language(config: dict[str, object]) -> str:
    return str(config.get("output_language") or "en").lower()


def extract_highlights(text: str) -> tuple[list[str], list[str]]:
    highlights: list[str] = []
    rationale_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(">"):
            continue
        if stripped.lower().startswith("rationale:"):
            rationale_lines.append(stripped)
            continue
        if stripped.lower().startswith("rationale "):
            rationale_lines.append(stripped)
            continue
        match = re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)(.+)$", stripped)
        if not match:
            continue
        item = match.group(1).strip()
        if item.lower().startswith("rationale:"):
            rationale_lines.append(item)
            continue
        highlights.append(item)
    return highlights, rationale_lines


def has_citation(text: str) -> bool:
    return any(pattern.search(text) for pattern in CITATION_PATTERNS)


def check_highlights(
    output_dir: Path,
    source_name: str,
    min_highlights: int,
    max_highlights: int,
    max_chars: int,
) -> tuple[int, list[str]]:
    findings: list[str] = []
    path = output_dir / source_name
    if not path.exists():
        findings.append(f"{source_name} is missing.")
        return 0, findings

    text = read_text(path)
    highlights, rationale_lines = extract_highlights(text)
    count = len(highlights)
    if count < min_highlights or count > max_highlights:
        findings.append(f"{path.name} has {count} highlights; expected {min_highlights}-{max_highlights}.")
    if rationale_lines:
        findings.append(f"{path.name} contains rationale lines; final highlights should contain only submission-facing bullets.")
    for index, item in enumerate(highlights, start=1):
        if len(item) > max_chars:
            findings.append(
                f"highlight {index} is too long: {len(item)} chars > {max_chars}."
            )
        if has_citation(item):
            findings.append(f"highlight {index} contains a citation marker.")
        if TODO_PATTERN.search(item):
            findings.append(f"highlight {index} contains TODO or double-bracket placeholder text.")
    if has_citation(text):
        findings.append(f"{path.name} contains citation markers; highlights must not include citations.")
    if TODO_PATTERN.search(text):
        findings.append(f"{path.name} contains TODO or double-bracket placeholder text.")
    return count, dedupe(findings)


def cover_word_count(text: str) -> int:
    words = len(WORD_PATTERN.findall(text))
    cjk_chars = len(CJK_PATTERN.findall(text))
    if cjk_chars and words < 50:
        return max(words, cjk_chars // 2)
    return words


def contains_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def extract_pending_items(text: str) -> list[str]:
    return sorted(set(PLACEHOLDER_PATTERN.findall(text)))


def check_cover_letter(output_dir: Path, source_name: str) -> tuple[int, list[str], list[str], list[str]]:
    findings: list[str] = []
    warnings: list[str] = []
    path = output_dir / source_name
    if not path.exists():
        return 0, [f"{source_name} is missing."], warnings, []

    text = read_text(path)
    words = cover_word_count(text)
    # Cover letters are normally 250-400 words (see references/submission.md). Treat
    # length as advisory: only a clearly broken letter (empty or runaway) blocks.
    if words and (words < 250 or words > 400):
        warnings.append(f"{path.name} word count is {words}; cover letters are normally 250-400 words.")
    if words < 60:
        findings.append(f"{path.name} word count is {words}; the cover letter looks empty or truncated.")

    if not contains_any(text, ORIGINALITY_PATTERNS):
        findings.append(f"{path.name} must include an originality statement.")
    if not contains_any(text, NOT_UNDER_CONSIDERATION_PATTERNS):
        findings.append(f"{path.name} must include a not-under-consideration / no simultaneous submission statement.")

    pending_items = extract_pending_items(text)
    if pending_items:
        warnings.append(
            f"{path.name} still contains explicit placeholders; complete the pending items before journal submission."
        )
    return words, findings, warnings, pending_items


def font_values(root: ElementTree.Element) -> set[str]:
    ns = {"w": W_NS}
    values: set[str] = set()
    for rfonts in root.findall(".//w:rFonts", ns):
        values.update(value for value in rfonts.attrib.values() if value)
    return values


def set_docx_fonts(path: Path) -> bool:
    """Set body run fonts and page geometry in a docx."""
    if not path.exists() or path.suffix.lower() != ".docx":
        return False

    with zipfile.ZipFile(path) as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}
        if "word/document.xml" not in entries:
            return False
        root = ElementTree.fromstring(entries["word/document.xml"])

    ElementTree.register_namespace("w", W_NS)
    changed = False
    for run in root.findall(f".//{W}r"):
        rpr = run.find(f"{W}rPr")
        if rpr is None:
            rpr = ElementTree.Element(f"{W}rPr")
            run.insert(0, rpr)
            changed = True
        rfonts = rpr.find(f"{W}rFonts")
        if rfonts is None:
            rfonts = ElementTree.Element(f"{W}rFonts")
            rpr.insert(0, rfonts)
            changed = True
        desired = {
            f"{W}ascii": LATIN_FONT,
            f"{W}hAnsi": LATIN_FONT,
            f"{W}cs": LATIN_FONT,
            f"{W}eastAsia": EAST_ASIA_FONT,
        }
        for attr, value in desired.items():
            if rfonts.get(attr) != value:
                rfonts.set(attr, value)
                changed = True

    sectpr = root.find(f".//{W}sectPr")
    if sectpr is None:
        body = root.find(f"{W}body")
        if body is None:
            return changed
        sectpr = ElementTree.Element(f"{W}sectPr")
        body.append(sectpr)
        changed = True

    pg_sz = sectpr.find(f"{W}pgSz")
    if pg_sz is None:
        pg_sz = ElementTree.Element(f"{W}pgSz")
        sectpr.insert(0, pg_sz)
        changed = True
    for attr, value in ((f"{W}w", A4_WIDTH_TWIPS), (f"{W}h", A4_HEIGHT_TWIPS)):
        if pg_sz.get(attr) != value:
            pg_sz.set(attr, value)
            changed = True

    pg_mar = sectpr.find(f"{W}pgMar")
    if pg_mar is None:
        pg_mar = ElementTree.Element(f"{W}pgMar")
        sectpr.insert(1, pg_mar)
        changed = True
    margins = {
        f"{W}top": DEFAULT_MARGIN_TWIPS,
        f"{W}right": DEFAULT_MARGIN_TWIPS,
        f"{W}bottom": DEFAULT_MARGIN_TWIPS,
        f"{W}left": DEFAULT_MARGIN_TWIPS,
        f"{W}header": "720",
        f"{W}footer": "720",
        f"{W}gutter": "0",
    }
    for attr, value in margins.items():
        if pg_mar.get(attr) != value:
            pg_mar.set(attr, value)
            changed = True

    if not changed:
        return False

    entries["word/document.xml"] = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx", dir=str(path.parent)) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for name, data in entries.items():
                target.writestr(name, data)
        shutil.move(str(tmp_path), path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return True


def fix_docx_fonts(output_dir: Path) -> list[str]:
    fixed: list[str] = []
    for name in REQUIRED_DOCX:
        path = output_dir / name
        try:
            if set_docx_fonts(path):
                fixed.append(name)
        except (OSError, zipfile.BadZipFile, ElementTree.ParseError):
            continue
    return fixed


def validate_docx(path: Path) -> tuple[list[str], list[str]]:
    """Return (blocking issues, advisory warnings) for a single docx.

    Blocking issues cover genuinely broken files (not a zip, missing core parts,
    no readable text). Font policy and page geometry are advisory: plain pandoc
    output is structurally valid even before `word_guard --fix-fonts` is run, so
    those mismatches must not force a FAIL.
    """
    issues: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return [f"{path.name} is missing."], warnings
    if path.suffix.lower() != ".docx":
        return [f"{path.name} is not a .docx file."], warnings
    try:
        with zipfile.ZipFile(path) as docx:
            names = set(docx.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                return [f"{path.name} is missing required docx parts."], warnings
            root = ElementTree.fromstring(docx.read("word/document.xml"))
    except zipfile.BadZipFile:
        return [f"{path.name} is not a valid zip/docx file."], warnings
    except ElementTree.ParseError as exc:
        return [f"{path.name} word/document.xml parse error: {exc}."], warnings
    ns = {"w": W_NS}
    text = "".join(node.text or "" for node in root.findall(".//w:t", ns)).strip()
    if not text:
        issues.append(f"{path.name} has no readable text.")
    fonts = font_values(root)
    is_zh = path.name.endswith(".zh.docx") or path.stem.endswith(".zh")
    if is_zh:
        if EAST_ASIA_FONT not in fonts:
            warnings.append(
                f"{path.name} does not set East Asian text to {EAST_ASIA_FONT} "
                "(advisory; run word_guard --fix-fonts to polish fonts)."
            )
    elif LATIN_FONT not in fonts:
        warnings.append(
            f"{path.name} does not set Latin text to {LATIN_FONT} "
            "(advisory; run word_guard --fix-fonts to polish fonts)."
        )
    sectpr = root.find(".//w:sectPr", ns)
    if sectpr is None:
        warnings.append(f"{path.name} does not set page section properties (advisory).")
    else:
        if sectpr.find("w:pgSz", ns) is None:
            warnings.append(f"{path.name} does not set page size (advisory).")
        if sectpr.find("w:pgMar", ns) is None:
            warnings.append(f"{path.name} does not set page margins (advisory).")
    return issues, warnings


def check_docx_outputs(
    output_dir: Path, required_docx: tuple[str, ...]
) -> tuple[list[str], list[str], list[str]]:
    findings: list[str] = []
    warnings: list[str] = []
    present: list[str] = []
    # Always validate any docx that is present, but only require the ones that
    # belong to the configured output language(s).
    names = list(required_docx)
    for name in REQUIRED_DOCX:
        if name not in names and (output_dir / name).exists():
            names.append(name)
    for name in names:
        path = output_dir / name
        if not path.exists():
            if name in required_docx:
                findings.append(f"{name} is missing.")
            continue
        issues, file_warnings = validate_docx(path)
        warnings.extend(file_warnings)
        if issues:
            findings.extend(issues)
        else:
            present.append(name)
    return present, findings, warnings


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def check_submission(
    output_dir: Path,
    min_highlights: int,
    max_highlights: int,
    max_chars: int,
) -> SubmissionCheckResult:
    findings: list[str] = []
    warnings: list[str] = []
    highlight_count = 0
    cover_words = 0
    zh_highlight_count = 0
    zh_cover_words = 0
    docx_files: list[str] = []
    pending_items: list[str] = []

    config = read_config(output_dir)
    language = output_language(config)
    translation = str(config.get("translation_package") or "none").lower()
    # English deliverables are required unless the run is Chinese-only; Chinese
    # deliverables are required only when the output language is Chinese or a
    # Chinese translation package was requested. For an EN-only run the .zh
    # markdown and .zh docx must not be demanded.
    en_required = language != "zh"
    zh_required = language == "zh" or translation == "zh"
    highlights_required = en_required or zh_required

    if not output_dir.exists():
        findings.append(f"submission package directory does not exist: {output_dir}")
    else:
        if en_required or (output_dir / "highlights.en.md").exists():
            highlight_count, highlight_findings = check_highlights(
                output_dir,
                "highlights.en.md",
                min_highlights,
                max_highlights,
                max_chars,
            )
            findings.extend(highlight_findings)
        if zh_required or (output_dir / "highlights.zh.md").exists():
            zh_highlight_count, zh_highlight_findings = check_highlights(
                output_dir,
                "highlights.zh.md",
                min_highlights,
                max_highlights,
                max_chars,
            )
            findings.extend(zh_highlight_findings)
        if en_required or (output_dir / "cover_letter.en.md").exists():
            cover_words, cover_findings, cover_warnings, pending_items = check_cover_letter(output_dir, "cover_letter.en.md")
            findings.extend(cover_findings)
            warnings.extend(cover_warnings)
        if zh_required or (output_dir / "cover_letter.zh.md").exists():
            zh_cover_words, zh_cover_findings, zh_cover_warnings, zh_pending_items = check_cover_letter(output_dir, "cover_letter.zh.md")
            findings.extend(zh_cover_findings)
            warnings.extend(zh_cover_warnings)
            pending_items = sorted(set(pending_items + zh_pending_items))

        required_docx: list[str] = []
        if en_required:
            required_docx.extend(("cover_letter.en.docx", "highlights.en.docx"))
        if zh_required:
            required_docx.extend(("cover_letter.zh.docx", "highlights.zh.docx"))
        docx_files, docx_findings, docx_warnings = check_docx_outputs(output_dir, tuple(required_docx))
        findings.extend(docx_findings)
        warnings.extend(docx_warnings)

    return SubmissionCheckResult(
        output_dir=str(output_dir),
        language=language,
        highlights_required=highlights_required,
        highlight_count=highlight_count,
        cover_word_count=cover_words,
        zh_highlight_count=zh_highlight_count,
        zh_cover_word_count=zh_cover_words,
        docx_files=docx_files,
        findings=dedupe(findings),
        warnings=dedupe(warnings),
        pending_items=pending_items,
    )


def to_markdown(result: SubmissionCheckResult) -> str:
    lines = [
        "# Submission Check Report",
        "",
        f"- Output directory: `{result.output_dir}`",
        f"- Output language: `{result.language}`",
        f"- Highlights required: {'yes' if result.highlights_required else 'no'}",
        f"- Highlight count: {result.highlight_count}",
        f"- Cover letter word count: {result.cover_word_count}",
        f"- Chinese highlight count: {result.zh_highlight_count}",
        f"- Chinese cover letter word count: {result.zh_cover_word_count}",
        f"- Valid Word files present: {len(result.docx_files)}",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        "",
        "## Findings",
        "",
    ]
    if result.findings:
        lines.extend(f"- {finding}" for finding in result.findings)
    else:
        lines.append("- None")

    lines.extend(["", "## Warnings", ""])
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- None")

    lines.extend(["", "## 待填清单", ""])
    if result.pending_items:
        lines.extend(f"- {item}" for item in result.pending_items)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Chinese headers survive Windows cp936 console
    args = parse_args()
    output_dir = Path(args.output_dir)
    if args.fix_fonts and output_dir.exists():
        fix_docx_fonts(output_dir)
    result = check_submission(output_dir, args.min_highlights, args.max_highlights, args.max_chars)
    markdown = to_markdown(result)

    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "submission_check.md").write_text(markdown, encoding="utf-8")

    if args.json:
        print(json.dumps(result.__dict__ | {"ok": result.ok}, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
