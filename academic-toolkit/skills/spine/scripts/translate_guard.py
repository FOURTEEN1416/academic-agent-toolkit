#!/usr/bin/env python3
"""PaperSpine Translation Guard — verify translation_zh/ completeness and quality.

Checks file existence, structural preservation (table row counts for large
artifacts), content density (stricter 50% threshold), full-paper coverage,
and manifest cross-validation.  Produces a teaching-oriented report that
says *what* is missing and *how* to fix it.

Pattern: follows the writing_rationale_matrix philosophy — every finding teaches.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paper_spine_utils import table_rows

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

TRANSLATION_DIR = "translation_zh"

TRANSLATION_COMMON = [
    "manifest.md",
    "translation_coverage.md",
    "paper_spine_config.zh.md",
    "source_map.zh.md",
    "reference_materials/source_index.zh.md",
    "research_dossier.zh.md",
    "exemplar_learning_dossier.zh.md",
    "style_profile.zh.md",
    "sota_gap_map.zh.md",
    "motivation_options_after_research.zh.md",
    "confirmed_motivation.zh.md",
    "section_blueprints.zh.md",
    "writing_rationale_matrix.zh.md",
    "citation_support_bank.zh.md",
    "final_structure.zh.md",
    "final_paper.zh.md",
    "full_paper_translation.zh.md",
    "latex_report.zh.md",
    "final_artifact_manifest.zh.md",
    "artifact_check.zh.md",
]

TRANSLATION_REWRITE = [
    "original_logic_map.zh.md",
    "rewrite_matrix.zh.md",
    "logic_transfer_audit.zh.md",
]

TRANSLATION_BUILD = [
    "source_inventory.zh.md",
    "evidence_bank.zh.md",
    "figure_asset_map.zh.md",
    "claim_register.zh.md",
]

# source -> target mapping for density checks
TRANSLATION_SOURCE: dict[str, str] = {}
for _t in TRANSLATION_COMMON + TRANSLATION_REWRITE + TRANSLATION_BUILD:
    _en = _t.replace(".zh.md", ".md")
    TRANSLATION_SOURCE[_t] = _en

# files that must preserve table structure (row-by-row, no summaries)
LARGE_TABULAR = {
    "writing_rationale_matrix.zh.md",
    "citation_support_bank.zh.md",
    "section_blueprints.zh.md",
    "research_dossier.zh.md",
    "exemplar_learning_dossier.zh.md",
    "sota_gap_map.zh.md",
    "original_logic_map.zh.md",
    "rewrite_matrix.zh.md",
    "source_inventory.zh.md",
    "evidence_bank.zh.md",
    "claim_register.zh.md",
}

# full paper required sections
FULL_PAPER_SECTIONS = [
    "title", "abstract", "introduction", "method", "experiment",
    "result", "discussion", "conclusion", "figure", "table",
    "caption", "limitation", "acknowledgement", "appendix",
]

# A section counts as covered if any of its synonyms (English OR Chinese) appears
# in the translation. Without this, a complete natural Chinese translation matches
# none of the English keywords and is wrongly reported as missing every section.
SECTION_SYNONYMS: dict[str, list[str]] = {
    "title": ["title", "标题", "题目"],
    "abstract": ["abstract", "摘要"],
    "introduction": ["introduction", "引言", "绪论", "导论", "介绍"],
    "method": ["method", "approach", "方法", "模型", "算法"],
    "experiment": ["experiment", "实验", "评测", "评估"],
    "result": ["result", "结果", "性能"],
    "discussion": ["discussion", "讨论", "分析"],
    "conclusion": ["conclusion", "结论", "总结"],
    "figure": ["figure", "fig.", "图"],
    "table": ["table", "表"],
    "caption": ["caption", "图注", "表注", "图 ", "表 "],
    "limitation": ["limitation", "局限", "不足", "限制"],
    "acknowledgement": ["acknowledgement", "acknowledgment", "致谢", "鸣谢"],
    "appendix": ["appendix", "附录"],
}

MIN_DENSITY_RATIO = 0.50  # Chinese translation must be at least 50% of English source chars

# ---------------------------------------------------------------------------
# data types
# ---------------------------------------------------------------------------

@dataclass
class TranslationFinding:
    id: str
    severity: str          # BLOCKER | WARNING | INFO
    what: str
    fix: str
    teaching: str = ""


@dataclass
class TranslationGuardReport:
    output_dir: str
    workflow: str
    findings: list[TranslationFinding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.severity == "BLOCKER" for f in self.findings)

    @property
    def total_findings(self) -> int:
        return len(self.findings)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify PaperSpine translation_zh/ completeness and quality.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write translate_guard_report.md")
    return parser.parse_args()


def load_config(out_dir: Path) -> dict:
    config_path = out_dir / "paper_spine_config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


# ---------------------------------------------------------------------------
# Check 1 — File Completeness
# ---------------------------------------------------------------------------

def check_file_completeness(trans_dir: Path, out_dir: Path, config: dict) -> list[TranslationFinding]:
    workflow = config.get("workflow", "rewrite_existing")
    required = list(TRANSLATION_COMMON)
    if workflow == "rewrite_existing":
        required.extend(TRANSLATION_REWRITE)
    else:
        required.extend(TRANSLATION_BUILD)

    findings: list[TranslationFinding] = []
    missing = [f for f in required if not (trans_dir / f).exists()]
    present = [f for f in required if (trans_dir / f).exists()]

    for f in missing:
        en_name = TRANSLATION_SOURCE.get(f, f)
        findings.append(TranslationFinding(
            id=f"FILE-{len(findings)+1:03d}",
            severity="BLOCKER",
            what=f"Missing translation: `translation_zh/{f}`",
            fix=f"Translate `{en_name}` into `translation_zh/{f}`. "
                f"Use `paper-spine-translate` to produce this file.",
            teaching=f"Every intermediate artifact needs a Chinese counterpart. "
                      f"`{en_name}` is a required PaperSpine artifact — its translation "
                      f"is not optional.",
        ))

    if not findings and present:
        findings.append(TranslationFinding(
            id="FILE-000", severity="INFO",
            what=f"All {len(required)} required translation files present",
            fix="", teaching="",
        ))
    return findings


# ---------------------------------------------------------------------------
# Check 2 — Structural Preservation (table rows for large tabular artifacts)
# ---------------------------------------------------------------------------

def check_structural_preservation(trans_dir: Path, out_dir: Path) -> list[TranslationFinding]:
    findings: list[TranslationFinding] = []
    for zh_name in sorted(LARGE_TABULAR):
        zh_path = trans_dir / zh_name
        if not zh_path.exists():
            continue
        en_name = TRANSLATION_SOURCE.get(zh_name, "")
        en_path = out_dir / en_name
        if not en_path.exists():
            continue

        zh_text = zh_path.read_text(encoding="utf-8", errors="ignore")
        en_text = en_path.read_text(encoding="utf-8", errors="ignore")

        if "|" in en_text:
            _, en_rows = table_rows(en_text)
            _, zh_rows = table_rows(zh_text)
            en_count = len(en_rows)
            zh_count = len(zh_rows)

            if zh_count < en_count:
                findings.append(TranslationFinding(
                    id=f"STRUCT-{len(findings)+1:03d}",
                    severity="BLOCKER",
                    what=f"`{zh_name}` has {zh_count} table rows vs {en_count} in source — "
                          f"missing {en_count - zh_count} rows",
                    fix=f"Translate every row of `{en_name}` into `{zh_name}`. "
                        f"Row-by-row translation is mandatory for this file — "
                        f"a shortened summary table is a failed output.",
                    teaching="Large tabular artifacts must preserve their row structure in translation. "
                            "Each row represents a unit of reasoning or a citation candidate — "
                            "losing rows means losing information the reader needs.",
                ))

    if not findings:
        tabular_present = [f for f in LARGE_TABULAR if (trans_dir / f).exists()]
        if tabular_present:
            findings.append(TranslationFinding(
                id="STRUCT-000", severity="INFO",
                what=f"Table structure preserved in all {len(tabular_present)} checked tabular files",
                fix="", teaching="",
            ))
    return findings


# ---------------------------------------------------------------------------
# Check 3 — Content Density
# ---------------------------------------------------------------------------

def check_content_density(trans_dir: Path, out_dir: Path) -> list[TranslationFinding]:
    findings: list[TranslationFinding] = []
    for zh_name, en_name in sorted(TRANSLATION_SOURCE.items()):
        zh_path = trans_dir / zh_name
        en_path = out_dir / en_name
        if not zh_path.exists() or not en_path.exists():
            continue

        en_len = len(en_path.read_text(encoding="utf-8", errors="ignore"))
        zh_len = len(zh_path.read_text(encoding="utf-8", errors="ignore"))

        if en_len < 300:
            continue  # too short to meaningfully check

        ratio = zh_len / en_len if en_len > 0 else 0
        if ratio < MIN_DENSITY_RATIO:
            findings.append(TranslationFinding(
                id=f"DENS-{len(findings)+1:03d}",
                severity="BLOCKER" if ratio < 0.25 else "WARNING",
                what=f"`{zh_name}` is {zh_len} chars vs {en_len} in source — "
                      f"density ratio {ratio:.0%} (minimum: {MIN_DENSITY_RATIO:.0%})",
                fix=f"Expand the translation of `{zh_name}` to cover all content from `{en_name}`. "
                    f"Chinese translations typically reach 40-70% of English character count. "
                    f"At {ratio:.0%}, this file appears to be a summary, not a translation.",
                teaching="A translation should convey the same information as the source. "
                        "When a translated file is dramatically shorter than the original, "
                        "content has been lost — usually because the translator summarized instead of translating.",
            ))

    if not findings:
        checked = sum(1 for zh, en in TRANSLATION_SOURCE.items()
                      if (trans_dir / zh).exists() and (out_dir / en).exists()
                      and len((out_dir / en).read_text(encoding="utf-8", errors="ignore")) >= 300)
        findings.append(TranslationFinding(
            id="DENS-000", severity="INFO",
            what=f"Content density adequate in all {checked} checked files",
            fix="", teaching="",
        ))
    return findings


# ---------------------------------------------------------------------------
# Check 4 — Full Paper Translation Coverage
# ---------------------------------------------------------------------------

SECTION_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)", re.MULTILINE)

def check_full_paper_coverage(trans_dir: Path, out_dir: Path) -> list[TranslationFinding]:
    findings: list[TranslationFinding] = []
    fp_path = trans_dir / "full_paper_translation.zh.md"
    if not fp_path.exists():
        findings.append(TranslationFinding(
            id="FULL-001", severity="BLOCKER",
            what="full_paper_translation.zh.md is missing — the most important translation file",
            fix="Translate the complete final paper (title, abstract, all sections, figure/table captions, "
                "conclusion, acknowledgements) into full_paper_translation.zh.md. "
                "This is mandatory — do not skip or summarize.",
            teaching="full_paper_translation.zh.md is the Chinese reader's primary entry point. "
                    "Without it, the translation package fails its purpose: making the paper "
                    "accessible to Chinese readers.",
        ))
        return findings

    text = fp_path.read_text(encoding="utf-8", errors="ignore")
    headings = set(m.strip().lower() for m in SECTION_HEADING_RE.findall(text))
    heading_text = " ".join(headings)
    text_lower = text.lower()

    covered = []
    missing_sections = []
    for section in FULL_PAPER_SECTIONS:
        synonyms = SECTION_SYNONYMS.get(section, [section])
        # The title is normally the document's H1 rather than a literal "title"
        # heading, so any heading at all satisfies it.
        if section == "title" and headings:
            covered.append(section)
            continue
        if any(s in heading_text or s in text_lower for s in synonyms):
            covered.append(section)
        else:
            missing_sections.append(section)

    if missing_sections:
        findings.append(TranslationFinding(
            id="FULL-002",
            severity="WARNING" if len(missing_sections) <= 3 else "BLOCKER",
            what=f"full_paper_translation.zh.md may be missing sections: {', '.join(missing_sections)}",
            fix=f"Check that the full paper translation covers: {', '.join(missing_sections)}. "
                f"The translation must include every section of the final paper.",
            teaching="A complete paper translation must cover all reader-facing sections. "
                    "Missing sections mean the Chinese reader cannot fully understand the paper.",
        ))

    if len(text) < 1000:
        findings.append(TranslationFinding(
            id="FULL-003", severity="BLOCKER",
            what=f"full_paper_translation.zh.md is only {len(text)} chars — far too short for a full paper",
            fix="Expand the full paper translation to cover all sections. "
                "A conference paper translation should be at least 3000+ characters.",
            teaching="A full paper translation that is shorter than the abstract "
                    "is not a translation — it's a note saying 'I was supposed to translate this.'",
        ))

    if not findings:
        findings.append(TranslationFinding(
            id="FULL-000", severity="INFO",
            what=f"Full paper translation covers {len(covered)}/{len(FULL_PAPER_SECTIONS)} expected section types",
            fix="", teaching="",
        ))
    return findings


# ---------------------------------------------------------------------------
# Check 5 — Manifest Cross-Validation
# ---------------------------------------------------------------------------

def check_manifest(trans_dir: Path, config: dict) -> list[TranslationFinding]:
    findings: list[TranslationFinding] = []
    manifest_path = trans_dir / "manifest.md"
    if not manifest_path.exists():
        findings.append(TranslationFinding(
            id="MANIFEST-001", severity="BLOCKER",
            what="translation_zh/manifest.md is missing",
            fix="Create manifest.md listing every translation file with its status (translated/missing/partial).",
            teaching="The manifest is the translation package's table of contents. "
                    "Without it, there's no way to quickly assess translation coverage.",
        ))
        return findings

    manifest_text = manifest_path.read_text(encoding="utf-8", errors="ignore")

    # Check manifest references actual files
    workflow = config.get("workflow", "rewrite_existing")
    required = list(TRANSLATION_COMMON)
    if workflow == "rewrite_existing":
        required.extend(TRANSLATION_REWRITE)
    else:
        required.extend(TRANSLATION_BUILD)

    manifest_mentions = []
    for f in required:
        filename = Path(f).name
        if filename in manifest_text or f in manifest_text:
            manifest_mentions.append(f)

    missing_from_manifest = [f for f in required if f not in manifest_mentions]
    if missing_from_manifest:
        findings.append(TranslationFinding(
            id="MANIFEST-002", severity="WARNING",
            what=f"Manifest does not reference {len(missing_from_manifest)} required files: "
                  f"{', '.join(missing_from_manifest[:5])}",
            fix="Add entries for every required translation file to manifest.md with status.",
            teaching="The manifest should be a complete inventory. "
                    "Missing entries mean the manifest is out of sync with the file system.",
        ))

    # Check manifest flags partial/missing
    if re.search(r"(missing|partial|not translated|缺失|未翻译|部分翻译)", manifest_text, re.IGNORECASE):
        findings.append(TranslationFinding(
            id="MANIFEST-003", severity="BLOCKER",
            what="Manifest reports files as missing or partially translated",
            fix="Complete the translation for all files marked as missing or partial, "
                "then update the manifest to reflect 'translated' status.",
            teaching="A translation package with self-reported gaps is incomplete. "
                    "The manifest should show all files as translated before the package passes audit.",
        ))

    if not findings:
        findings.append(TranslationFinding(
            id="MANIFEST-000", severity="INFO",
            what="Manifest is present and references all required files",
            fix="", teaching="",
        ))
    return findings


def word_output_requested(config: dict) -> bool:
    value = config.get("word_output", "docx")
    if value is False:
        return False
    return str(value).strip().lower() not in {"none", "false", "no", "0"}


def check_chinese_word_delivery(trans_dir: Path, out_dir: Path, config: dict) -> list[TranslationFinding]:
    findings: list[TranslationFinding] = []
    if not word_output_requested(config):
        return findings

    full_translation = trans_dir / "full_paper_translation.zh.md"
    zh_docx = out_dir / "final_paper" / "paper.zh.docx"
    zh_report = out_dir / "word_report.zh.md"

    if full_translation.exists() and not zh_docx.exists():
        findings.append(TranslationFinding(
            id="DOCX-001",
            severity="BLOCKER",
            what="translation_zh/full_paper_translation.zh.md exists but final_paper/paper.zh.docx is missing",
            fix="Use pandoc to convert full_paper_translation.zh.md into final_paper/paper.zh.docx, then run word_guard.py and write word_report.zh.md.",
            teaching="translation_zh/ is the Chinese translation audit package. The user-facing Chinese deliverable must be one Word document: final_paper/paper.zh.docx.",
        ))

    if zh_docx.exists() and not zh_report.exists():
        findings.append(TranslationFinding(
            id="DOCX-002",
            severity="BLOCKER",
            what="final_paper/paper.zh.docx exists but word_report.zh.md is missing",
            fix="Run word_guard.py on final_paper/paper.zh.docx and write the report to word_report.zh.md.",
            teaching="A Chinese Word file is not complete until the Word guard verifies that it is readable and not corrupted.",
        ))

    if zh_docx.exists() and zh_report.exists():
        findings.append(TranslationFinding(
            id="DOCX-000",
            severity="INFO",
            what="User-facing Chinese Word document exists: final_paper/paper.zh.docx",
            fix="",
            teaching="translation_zh/ remains the audit package; paper.zh.docx is the single file users open.",
        ))
    return findings


# ---------------------------------------------------------------------------
# Check 6 — Chinese Content Quality
# ---------------------------------------------------------------------------

MARKDOWN_BOLD_RE = re.compile(r"\*\*[^*\n]+\*\*")
MARKDOWN_ITALIC_RE = re.compile(r"(?<![a-zA-Z0-9_])\*[a-zA-Z][^*\n]*[a-zA-Z]\*(?![a-zA-Z0-9_])")
CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
ENGLISH_WORD_RE = re.compile(r"[a-zA-Z]{3,}")


def visible_docx_text(path: Path) -> str:
    """Extract visible paragraph text from a docx using only the standard library."""
    if not path.exists() or path.suffix.lower() != ".docx":
        return ""
    try:
        with zipfile.ZipFile(path) as docx:
            if "word/document.xml" not in docx.namelist():
                return ""
            root = ElementTree.fromstring(docx.read("word/document.xml"))
    except (zipfile.BadZipFile, ElementTree.ParseError, OSError):
        return ""
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def chinese_ratio(text: str) -> tuple[float, int, int]:
    chinese_chars = len(CHINESE_CHAR_RE.findall(text))
    english_words = len(ENGLISH_WORD_RE.findall(text))
    total = chinese_chars + english_words
    return (chinese_chars / total if total else 0.0), chinese_chars, english_words


def markdown_marker_finding(text: str, location: str, finding_id: str, severity: str = "BLOCKER") -> TranslationFinding | None:
    bold_hits = MARKDOWN_BOLD_RE.findall(text)
    italic_hits = MARKDOWN_ITALIC_RE.findall(text)
    if not bold_hits and not italic_hits:
        return None
    parts: list[str] = []
    if bold_hits:
        parts.append(f"{len(bold_hits)} bold (e.g. {', '.join(h[:50] for h in bold_hits[:3])})")
    if italic_hits:
        parts.append(f"{len(italic_hits)} italic (e.g. {', '.join(h[:50] for h in italic_hits[:3])})")
    return TranslationFinding(
        id=finding_id,
        severity=severity,
        what=f"Raw Markdown emphasis markers found in {location}: {', '.join(parts)}",
        fix="Remove all **...** and *...* Markdown emphasis markers, or render them as real Word formatting before delivery.",
        teaching="Visible asterisks are source Markdown syntax, not polished Word output. They make the translation look like unrendered intermediate text.",
    )


def check_chinese_content_quality(trans_dir: Path, out_dir: Path, config: dict) -> list[TranslationFinding]:
    findings: list[TranslationFinding] = []

    package = str(config.get("translation_package") or "").lower()
    language = str(config.get("output_language") or "").lower()
    if package != "zh" and language != "zh":
        return findings

    # Check full_paper_translation.zh.md for Chinese content ratio
    fp_path = trans_dir / "full_paper_translation.zh.md"
    if fp_path.exists():
        try:
            text = fp_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return findings

        ratio, chinese_chars, english_words = chinese_ratio(text)
        total = chinese_chars + english_words
        if total > 100:
            if ratio < 0.30:
                findings.append(TranslationFinding(
                    id="ZH-RATIO-001",
                    severity="BLOCKER",
                    what=f"full_paper_translation.zh.md appears mostly English "
                         f"({ratio:.0%} Chinese characters, {chinese_chars} Chinese chars / {english_words} English words). "
                         "The Chinese Word must contain Chinese content, not English content under a Chinese title.",
                    fix="Translate the full paper body into Chinese. "
                        "Do not produce a Chinese-formatted wrapper around English prose.",
                    teaching="paper.zh.docx is the reader-facing Chinese Word deliverable. "
                            "It must contain predominantly Chinese text so Chinese readers can read the paper.",
                ))

        marker_finding = markdown_marker_finding(text, "full_paper_translation.zh.md", "ZH-MARKDOWN-001")
        if marker_finding:
            findings.append(marker_finding)

    # Check the final user-facing Chinese Word itself. This catches cases where
    # the Markdown translation is correct but paper.zh.docx was built from the
    # English source or from unrendered Markdown.
    zh_docx = out_dir / "final_paper" / "paper.zh.docx"
    docx_text = visible_docx_text(zh_docx)
    if docx_text:
        ratio, chinese_chars, english_words = chinese_ratio(docx_text)
        total = chinese_chars + english_words
        if total > 100 and ratio < 0.30:
            findings.append(TranslationFinding(
                id="ZH-DOCX-RATIO-001",
                severity="BLOCKER",
                what=f"final_paper/paper.zh.docx appears mostly English "
                     f"({ratio:.0%} Chinese characters, {chinese_chars} Chinese chars / {english_words} English words).",
                fix="Regenerate paper.zh.docx from the full Chinese translation, not from the English paper source.",
                teaching="When translation_package=zh, paper.zh.docx is the Chinese reader-facing Word file. "
                         "It must be a translation of the English paper, not English prose under a Chinese title.",
            ))
        marker_finding = markdown_marker_finding(docx_text, "final_paper/paper.zh.docx", "ZH-DOCX-MARKDOWN-001")
        if marker_finding:
            findings.append(marker_finding)

    # Check word_report.zh.md for Markdown emphasis markers
    zh_report = out_dir / "word_report.zh.md"
    if zh_report.exists():
        try:
            report_text = zh_report.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            report_text = ""
        if MARKDOWN_BOLD_RE.search(report_text) or MARKDOWN_ITALIC_RE.search(report_text):
            findings.append(TranslationFinding(
                id="ZH-MARKDOWN-002",
                severity="WARNING",
                what="Raw Markdown emphasis markers found in word_report.zh.md",
                fix="Check the Chinese Word output for visible **...** asterisks. "
                    "If present, re-convert with proper Markdown-to-Word processing.",
                teaching="A Word report that still contains Markdown markers means the docx itself likely does too.",
            ))

    if not findings:
        findings.append(TranslationFinding(
            id="ZH-QUALITY-000",
            severity="INFO",
            what="Chinese content quality checks passed",
            fix="",
            teaching="",
        ))
    return findings


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def to_markdown(report: TranslationGuardReport) -> str:
    lines = [
        "# Translation Guard Report",
        "",
        f"- Output directory: `{report.output_dir}`",
        f"- Workflow: {report.workflow}",
        f"- Total findings: {report.total_findings}",
        f"- Status: {'BLOCKED' if report.blocked else 'PASS'}",
        "",
        "> Each finding explains *what* is missing and *how* to fix it. "
        "Translation is not optional — it's a required deliverable.",
        "",
    ]

    for f in report.findings:
        if f.severity == "INFO":
            lines.append(f"**{f.id}** PASSED: {f.what}")
            lines.append("")
            continue
        icon = "BLOCKED" if f.severity == "BLOCKER" else "WARNING"
        lines.append(f"### {f.id} — {icon}")
        lines.append("")
        lines.append(f"**What:** {f.what}")
        lines.append("")
        lines.append(f"**Fix:** {f.fix}")
        lines.append("")
        if f.teaching:
            lines.append(f"> {f.teaching}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    trans_dir = out_dir / TRANSLATION_DIR

    if not out_dir.is_dir():
        print(f"Output directory not found: {out_dir}", file=sys.stderr)
        return 2

    config = load_config(out_dir)
    trans_dir.mkdir(parents=True, exist_ok=True)

    all_findings: list[TranslationFinding] = []
    all_findings.extend(check_file_completeness(trans_dir, out_dir, config))
    all_findings.extend(check_structural_preservation(trans_dir, out_dir))
    all_findings.extend(check_content_density(trans_dir, out_dir))
    all_findings.extend(check_full_paper_coverage(trans_dir, out_dir))
    all_findings.extend(check_manifest(trans_dir, config))
    all_findings.extend(check_chinese_word_delivery(trans_dir, out_dir, config))
    all_findings.extend(check_chinese_content_quality(trans_dir, out_dir, config))

    report = TranslationGuardReport(str(out_dir), config.get("workflow", "rewrite_existing"), all_findings)

    if args.json:
        print(json.dumps({
            "output_dir": str(out_dir), "blocked": report.blocked,
            "total_findings": report.total_findings,
            "findings": [{"id": f.id, "severity": f.severity, "what": f.what, "fix": f.fix} for f in all_findings],
        }, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(to_markdown(report))

    if args.write:
        report_path = trans_dir / "translate_guard_report.md"
        report_path.write_text(to_markdown(report), encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    return 1 if report.blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
