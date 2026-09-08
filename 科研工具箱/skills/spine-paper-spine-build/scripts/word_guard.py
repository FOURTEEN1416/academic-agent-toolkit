#!/usr/bin/env python3
"""Lightweight structural checks for generated Word .docx files."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

PLACEHOLDER_PATTERNS = (
    r"\bTODO\b",
    r"\bTBD\b",
    r"\bFIXME\b",
    r"\?\?",
    r"\[\[",
    r"\]\]",
)

# LaTeX control sequences that should never survive into a finished .docx.
# Their presence means pandoc emitted the raw source instead of rendered output.
LATEX_COMMAND_PATTERN = re.compile(
    r"\\(?:cite[a-zA-Z]*|ref|eqref|autoref|cref|Cref|label|textbf|textit|emph|"
    r"section|subsection|subsubsection|begin|end|includegraphics|caption|"
    r"footnote|item|hline|toprule|midrule|bottomrule|"
    r"textsubscript|textsuperscript|textasciitilde|textbackslash|"
    r"AA|aa|AE|ae|OE|oe|O|o|L|l|SS|ss"  # common LaTeX symbol / accent commands
    r")\b"
)
# LaTeX single-char escapes that indicate raw source leakage.
# \% \$ \& \# \_ \{ \} — these should be rendered, not appear literally.
LATEX_SINGLE_CHAR_ESCAPE = re.compile(r"\\(?:%|\$|&|#|_|\{|\})")
# Any LaTeX macro applied to an argument, e.g. \foo{...} — catches custom macros
# (\newcommand) that pandoc could not expand, not just the curated list above.
# Requiring a trailing brace keeps backslashed file paths from matching.
GENERIC_LATEX_MACRO_PATTERN = re.compile(r"\\[a-zA-Z]+\s*\{")
# pandoc citeproc leftovers, e.g. [@smith2020] — citations were never resolved.
CITEPROC_LEFTOVER_PATTERN = re.compile(r"\[@[\w:.\-]+(?:\s*;\s*@[\w:.\-]+)*\]")
# Inline math left as raw LaTeX. Either a `$...$` span with a backslash macro,
# or a tight `$...$` subscript/superscript with no spaces (e.g. $x_i$, $x^2$).
# Currency like "$5 ... file_name ... $10" needs spaces, so it is not matched.
RAW_MATH_PATTERN = re.compile(
    r"\$[^$\n]*\\[a-zA-Z]+[^$\n]*\$|\$[^$\n\s]*[_^][^$\n\s]*\$"
)
# pandoc-crossref renders unresolved \ref/\eqref as a literal "[?]".
BROKEN_CROSSREF = "[?]"

# Raw Markdown emphasis markers that should never survive into a finished .docx.
# **text**  — bold markers; double asterisks wrapping content are always Markdown.
MARKDOWN_BOLD_PATTERN = re.compile(r"\*\*[^*\n]+\*\*")
# *text* — italic markers when the asterisks hug word content, excluding scientific notation.
# (?<!\w) prevents matching p<0.05* (digit before asterisk is a word char).
# (?!\w) prevents matching *p<0.05 (digit after asterisk is a word char).
# Content must start/end with a letter so multiplication (a * b) and bullets (* item) are excluded.
MARKDOWN_ITALIC_PATTERN = re.compile(r"(?<![a-zA-Z0-9_])\*[a-zA-Z][^*\n]*[a-zA-Z]\*(?![a-zA-Z0-9_])")

# LaTeX bibliography styles that produce numbered [1] citations. If the source
# uses one of these but the docx rendered author-date (citeproc's default), the
# Word citations silently diverge from the compiled PDF.
NUMERIC_BIB_STYLES = frozenset({
    "plain", "unsrt", "abbrv", "ieeetr", "ieee", "ieeetran", "acm", "siam", "vancouver",
})
# Styles that legitimately render (Author, Year). When the source declares one of
# these, author-year citations in the Word output are correct and must not be flagged.
AUTHOR_DATE_BIB_STYLES = frozenset({
    "plainnat", "abbrvnat", "unsrtnat", "agsm", "apa", "apalike", "apacite",
    "chicago", "authordate", "harvard", "dinat", "kluwer", "nature",
})
BIBSTYLE_PATTERN = re.compile(r"\\bibliographystyle\{([^}]+)\}")
NUMERIC_CITE_PATTERN = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]")
AUTHOR_DATE_CITE_PATTERN = re.compile(r"\([A-Z][A-Za-z'’.-]+(?:\s+et al\.?)?,?\s+\d{4}[a-z]?\)")


def citation_style_finding(docx_text: str, source_tex: str) -> str | None:
    """Warn when a numeric \\bibliographystyle renders as author-date in Word.

    citeproc defaults to author-date, so a numeric LaTeX style needs an explicit
    numeric CSL (e.g. --csl=ieee.csl) or the docx citations will not match the
    PDF's [1] style. Conservative: only fires when the source is numeric AND the
    docx clearly shows author-date citations with no numbered ones.
    """
    if not source_tex:
        return None
    match = BIBSTYLE_PATTERN.search(source_tex)
    if not match or match.group(1).strip().lower() not in NUMERIC_BIB_STYLES:
        return None
    if AUTHOR_DATE_CITE_PATTERN.search(docx_text) and not NUMERIC_CITE_PATTERN.search(docx_text):
        return (
            f"Citation style mismatch: source uses numeric \\bibliographystyle{{{match.group(1).strip()}}} "
            "but the Word citations render author-date. Pass a numeric CSL "
            "(e.g. --csl=ieee.csl) so Word matches the PDF's [1] style."
        )
    return None


def author_year_citation_finding(docx_text: str, source_tex: str) -> str | None:
    """Flag author-year citations in the Word output unless the source is author-date.

    PaperSpine's default rule (SKILL.md / references/latex.md) is plain numeric
    [1] citations. word_guard previously only caught author-year when a numeric
    \\bibliographystyle was supplied, so a docx rendered without any source tex
    passed silently. This fires whenever (Author, Year) citations appear and the
    source is NOT a known author-date style. Numeric-style sources are left to
    citation_style_finding, which carries a more specific message.
    """
    match = AUTHOR_DATE_CITE_PATTERN.search(docx_text)
    if not match:
        return None
    style = ""
    if source_tex:
        bib = BIBSTYLE_PATTERN.search(source_tex)
        if bib:
            style = bib.group(1).strip().lower()
    if style in AUTHOR_DATE_BIB_STYLES:
        return None  # author-date is legitimate here
    if style in NUMERIC_BIB_STYLES:
        return None  # citation_style_finding owns this case
    return (
        f"Author-year citation found in the Word output (e.g. '{match.group(0)}'). "
        "PaperSpine's default rule is plain square-bracket numeric citations, e.g. [1]. "
        "Render with a numeric CSL (e.g. --csl=ieee.csl) or pass --tex so an author-date "
        "\\bibliographystyle can be recognized; otherwise convert the citations to numeric form."
    )


GLUED_HEADING_NUMBER_PATTERN = re.compile(
    r"^\s*(?:[1-9]\d?)(?:\.\d+)*[A-Z][A-Za-z][A-Za-z0-9:,'’()&/\- ]{2,}$"
)
COMMON_HEADING_STARTS = (
    "introduction",
    "background",
    "method",
    "methods",
    "materials",
    "results",
    "discussion",
    "conclusion",
    "references",
    "appendix",
    "the ",
    "a ",
    "an ",
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
FONT_STYLE_IDS = (
    "Normal",
    "BodyText",
    "FirstParagraph",
    "Title",
    "Subtitle",
    "Heading1",
    "Heading2",
    "Heading3",
    "Abstract",
    "AbstractTitle",
    "Author",
    "Date",
    "TableCaption",
    "Compact",
)


@dataclass
class FontProfile:
    mode: str
    ok: bool
    expected: str
    actual: list[str]
    findings: list[str]


ElementTree.register_namespace("w", W_NS)
ElementTree.register_namespace("a", A_NS)


def _w_attr(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def _a_attr(name: str) -> str:
    return f"{{{A_NS}}}{name}"


@dataclass
class WordGuardResult:
    path: str
    ok: bool
    text_length: int
    paragraph_count: int
    findings: list[str]
    title_ok: bool = True
    expected_title: str = ""
    first_paragraph: str = ""
    font_ok: bool = True
    expected_font: str = ""
    actual_fonts: list[str] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a generated .docx file.")
    parser.add_argument("docx_path")
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="Optional report path.")
    parser.add_argument("--tex", type=Path, help="Path to main.tex for title extraction.")
    parser.add_argument("--expected-title", help="Expected paper title (overrides --tex extraction).")
    parser.add_argument(
        "--fix-fonts",
        action="store_true",
        help="Rewrite docx styles/theme fonts before checking: Times New Roman for English, SimSun for Chinese.",
    )
    parser.add_argument(
        "--language",
        choices=("auto", "en", "zh"),
        default="auto",
        help="Language used for font policy. auto uses .zh.docx/name or Chinese text detection.",
    )
    return parser.parse_args()


def extract_text(document_xml: bytes) -> tuple[str, int]:
    root = ElementTree.fromstring(document_xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        text = _paragraph_text(paragraph).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs), len(paragraphs)


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{{{W_NS}}}t":
            parts.append(node.text or "")
        elif node.tag == f"{{{W_NS}}}tab":
            parts.append(" ")
        elif node.tag == f"{{{W_NS}}}br":
            parts.append("\n")
    return "".join(parts)


def extract_paragraphs_ordered(document_xml: bytes) -> list[str]:
    """Return non-empty paragraph texts in document order."""
    root = ElementTree.fromstring(document_xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    result: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        text = _paragraph_text(paragraph).strip()
        if text:
            result.append(text)
    return result


TITLE_FORBIDDEN_STARTS = [
    "abstract",
    "keywords",
    "introduction",
    "method",
    "methods",
    "materials",
    "results",
    "discussion",
    "conclusion",
    "acknowledgment",
    "acknowledgements",
    "acknowledgment",
    "references",
    "appendix",
    "supplementary",
    "摘要",
    "关键词",
    "引言",
    "绪论",
    "介绍",
    "导论",
    "方法",
    "材料",
    "结果",
    "讨论",
    "结论",
    "致谢",
    "参考文献",
    "附录",
    "补充材料",
    "完整中文翻译",
    "full chinese translation",
    "1. 引言",
    "1.引言",
    "1 引言",
    "1.  introduction",
    "1. introduction",
    "i. introduction",
]


def check_title_in_front(paragraphs: list[str], expected_title: str | None = None) -> tuple[str | None, str]:
    """Return (finding, first_paragraph) — finding is None when the title is acceptable.

    Checks the first 5 non-empty paragraphs for an acceptable paper title.
    Rejects wrapper headings and short text. When expected_title is given, also
    verifies it appears in the front paragraphs.
    """
    first_para = paragraphs[0] if paragraphs else ""
    if not paragraphs:
        return "Docx has no non-empty paragraphs — title is missing.", first_para

    front = paragraphs[:5]

    # If the expected title is known and present in the front paragraphs, the
    # title is satisfied regardless of ordering.
    if expected_title:
        front_text = re.sub(r"\s+", " ", " ".join(front)).lower()
        expected_norm = re.sub(r"\s+", " ", expected_title).strip().lower()
        if expected_norm in front_text:
            return None, first_para

    # The Word output must OPEN with the paper title. If the very first paragraph
    # is itself a short section/wrapper heading (Abstract, Keywords, Introduction,
    # 摘要…) there is no title in front and we flag it. The length bound keeps a
    # legitimate title that merely starts with a section-like word
    # (e.g. "Introduction to Spectral Methods for Graph Learning") from being
    # falsely rejected.
    first_lower = first_para.strip().lower()
    if any(first_lower.startswith(f) for f in TITLE_FORBIDDEN_STARTS) and len(first_para.strip()) <= 40:
        return (
            f"Word output begins with '{first_para.strip()[:60]}', a section/wrapper "
            "heading, not the paper title. The paper title must appear on the first "
            "page before Abstract/Keywords/Introduction."
        ), first_para

    # Advance past any leading wrapper/forbidden paragraphs to find the candidate title.
    candidate_idx = 0
    for i, para in enumerate(front):
        lower = para.strip().lower()
        is_forbidden = any(lower.startswith(f) for f in TITLE_FORBIDDEN_STARTS)
        if not is_forbidden:
            candidate_idx = i
            break
    else:
        # All first 5 paragraphs are forbidden wrapper headings.
        return (
            f"First {len(front)} paragraphs are all section headers or wrapper headings "
            f"(e.g. '{paragraphs[0][:60]}'). The paper title must appear before "
            "Abstract/Keywords/Introduction."
        ), first_para

    candidate = front[candidate_idx].strip()

    # Candidate must be long enough to be a real title.
    if len(candidate) < 15:
        return (
            f"Title candidate is too short to be a paper title ({len(candidate)} chars): "
            f"'{candidate[:80]}'"
        ), first_para

    # An expected title was provided but not found in the front paragraphs above.
    if expected_title:
        return (
            f"Expected title '{expected_title[:80]}' not found in first 5 paragraphs. "
            f"First non-wrapper paragraph: '{candidate[:80]}'"
        ), first_para

    return None, first_para


def _normalize_tex_title(raw: str) -> str:
    """Collapse LaTeX line breaks (``\\``, ``\\*``, ``\\[2mm]``) and ``\\thanks``
    footnotes in a ``\\title{...}`` body, then squeeze whitespace. pandoc renders
    ``\\`` as a paragraph break in the .docx, so the extracted expected title must
    drop it to match the rendered title paragraphs."""
    title = re.sub(r"\\\\\*?(?:\s*\[[^\]]*\])?", " ", raw)
    title = re.sub(r"\\thanks\s*\{[^{}]*\}", "", title)
    return re.sub(r"\s+", " ", title).strip()


def extract_title_from_tex(tex_path: Path) -> str | None:
    """Extract the title text from \\title{...} in a .tex file."""
    if not tex_path.exists():
        return None
    try:
        tex = tex_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = re.search(r"\\title\{([^{}]+)\}", tex)
    if not m:
        return None
    return _normalize_tex_title(m.group(1)) or None


def extract_title_from_chinese_translation(docx_path: Path) -> str | None:
    """Extract the Chinese title from translation_zh/full_paper_translation.zh.md.

    Looks in several locations relative to the docx path, covering both the
    standard (final_paper inside paper_rewriting_output) and legacy layouts.
    Returns the first H1 heading found, or None.
    """
    candidates = [
        docx_path.parent.parent / "translation_zh" / "full_paper_translation.zh.md",
        docx_path.parent.parent / "paper_rewriting_output" / "translation_zh" / "full_paper_translation.zh.md",
    ]
    for cand in candidates:
        if not cand.exists():
            continue
        try:
            content = cand.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def detect_font_mode(docx_path: Path, text: str, language: str = "auto") -> str:
    if language in {"en", "zh"}:
        return language
    if docx_path.name.endswith(".zh.docx") or docx_path.stem.endswith(".zh"):
        return "zh"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return "en"


def _font_values_from_rfonts(rfonts: ElementTree.Element | None) -> list[str]:
    if rfonts is None:
        return []
    values: list[str] = []
    for _key, value in rfonts.attrib.items():
        if not value:
            continue
        values.append(value)
    return values


def _collect_style_fonts(styles_root: ElementTree.Element) -> list[str]:
    fonts: list[str] = []
    for rfonts in styles_root.findall(".//w:rFonts", {"w": W_NS}):
        fonts.extend(_font_values_from_rfonts(rfonts))
    return fonts


def _collect_theme_fonts(theme_root: ElementTree.Element | None) -> list[str]:
    if theme_root is None:
        return []
    fonts: list[str] = []
    for tag in ("majorFont", "minorFont"):
        node = theme_root.find(f".//a:{tag}", {"a": A_NS})
        if node is None:
            continue
        for child_name in ("latin", "ea", "cs"):
            child = node.find(f"a:{child_name}", {"a": A_NS})
            if child is not None and child.attrib.get("typeface"):
                fonts.append(child.attrib["typeface"])
    return fonts


def _theme_tokens(fonts: list[str]) -> list[str]:
    return sorted({f for f in fonts if "theme" in f.lower() or f in {"minorHAnsi", "majorHAnsi", "minorEastAsia", "majorEastAsia", "minorBidi", "majorBidi"}})


def font_profile(docx_path: Path, text: str, language: str = "auto") -> FontProfile:
    mode = detect_font_mode(docx_path, text, language)
    expected = "SimSun / 宋体" if mode == "zh" else "Times New Roman"
    findings: list[str] = []
    actual: list[str] = []
    try:
        with zipfile.ZipFile(docx_path) as docx:
            names = set(docx.namelist())
            styles_root = ElementTree.fromstring(docx.read("word/styles.xml")) if "word/styles.xml" in names else None
            theme_root = ElementTree.fromstring(docx.read("word/theme/theme1.xml")) if "word/theme/theme1.xml" in names else None
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
        return FontProfile(mode, True, expected, [], [])

    if styles_root is None:
        return FontProfile(mode, True, expected, [], [])

    style_fonts = _collect_style_fonts(styles_root)
    theme_fonts = _collect_theme_fonts(theme_root)
    actual = sorted(set(style_fonts + theme_fonts))
    joined = " | ".join(actual).lower()
    theme_refs = _theme_tokens(style_fonts)

    if mode == "en":
        has_expected = "times new roman" in joined
        if not has_expected or theme_refs:
            findings.append(
                "Word font policy failed: English Word must use Times New Roman in default/body/title styles. "
                f"Actual fonts/theme refs: {', '.join(actual or theme_refs or ['(none)'])}."
            )
    else:
        has_zh = "simsun" in joined or "宋体" in joined
        has_en = "times new roman" in joined
        if not has_zh or not has_en or theme_refs:
            findings.append(
                "Word font policy failed: Chinese Word must use SimSun/宋体 for East Asian text "
                "and Times New Roman for Latin text. "
                f"Actual fonts/theme refs: {', '.join(actual or theme_refs or ['(none)'])}."
            )
    return FontProfile(mode, not findings, expected, actual, findings)


def word_style_findings(docx_path: Path, mode: str) -> list[str]:
    findings: list[str] = []
    try:
        with zipfile.ZipFile(docx_path) as docx:
            names = set(docx.namelist())
            if "word/styles.xml" not in names or "word/document.xml" not in names:
                return findings
            styles_root = ElementTree.fromstring(docx.read("word/styles.xml"))
            document_root = ElementTree.fromstring(docx.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
        return findings

    for style_id in ("Heading1", "Heading2"):
        style = styles_root.find(f".//w:style[@w:styleId='{style_id}']", {"w": W_NS})
        if style is None:
            continue
        color = style.find(".//w:color", {"w": W_NS})
        value = (color.attrib.get(_w_attr("val"), "") if color is not None else "").lower()
        if value and value not in {"000000", "000", "auto"}:
            findings.append(
                f"{style_id} font color is not black (found #{value.upper()}). "
                "Set level-1 and level-2 heading styles to black."
            )

    texts = [_paragraph_full_text(p) for p in document_root.findall(".//w:body/w:p", {"w": W_NS})]
    has_reference_heading = any(text.lower() == "references" or text == "参考文献" for text in texts)
    if not has_reference_heading:
        for index, text in enumerate(texts):
            if not re.fullmatch(r"\d{1,3}", text):
                continue
            following = [t for t in texts[index + 1 : index + 6] if t]
            looks_like_bibliography = sum(
                1
                for item in following
                if re.search(r"\b(19|20)\d{2}\b", item)
                or "doi" in item.lower()
                or "http" in item.lower()
                or re.search(r"\bet al\.?\b", item, re.IGNORECASE)
            )
            if looks_like_bibliography >= 2:
                expected = "参考文献" if mode == "zh" else "References"
                findings.append(
                    f"Reference heading is missing before the bibliography. "
                    f"Replace the orphan bibliography label '{text}' with '{expected}'."
                )
                break
    return findings


def _ensure_child(parent: ElementTree.Element, tag: str) -> ElementTree.Element:
    child = parent.find(tag, {"w": W_NS, "a": A_NS})
    if child is None:
        child = ElementTree.SubElement(parent, tag.replace("w:", f"{{{W_NS}}}").replace("a:", f"{{{A_NS}}}"))
    return child


def _style_by_id(styles_root: ElementTree.Element, style_id: str) -> ElementTree.Element:
    style = styles_root.find(f".//w:style[@w:styleId='{style_id}']", {"w": W_NS})
    if style is not None:
        return style
    style = ElementTree.SubElement(styles_root, f"{{{W_NS}}}style", {_w_attr("type"): "paragraph", _w_attr("styleId"): style_id})
    ElementTree.SubElement(style, f"{{{W_NS}}}name", {_w_attr("val"): style_id})
    return style


def _set_rfonts(rpr: ElementTree.Element, mode: str) -> None:
    rfonts = rpr.find("w:rFonts", {"w": W_NS})
    if rfonts is None:
        rfonts = ElementTree.SubElement(rpr, f"{{{W_NS}}}rFonts")
    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "csTheme", "cstheme"):
        rfonts.attrib.pop(_w_attr(attr), None)
    if mode == "zh":
        rfonts.set(_w_attr("ascii"), "Times New Roman")
        rfonts.set(_w_attr("hAnsi"), "Times New Roman")
        rfonts.set(_w_attr("eastAsia"), "SimSun")
        rfonts.set(_w_attr("cs"), "Times New Roman")
    else:
        rfonts.set(_w_attr("ascii"), "Times New Roman")
        rfonts.set(_w_attr("hAnsi"), "Times New Roman")
        rfonts.set(_w_attr("eastAsia"), "Times New Roman")
        rfonts.set(_w_attr("cs"), "Times New Roman")


def _set_run_color(rpr: ElementTree.Element, color_value: str = "000000") -> None:
    color = rpr.find("w:color", {"w": W_NS})
    if color is None:
        color = ElementTree.SubElement(rpr, f"{{{W_NS}}}color")
    color.set(_w_attr("val"), color_value)


def _force_heading_style_black(styles_root: ElementTree.Element) -> None:
    for style_id in ("Heading1", "Heading2", "Heading3"):
        style = _style_by_id(styles_root, style_id)
        rpr = style.find("w:rPr", {"w": W_NS})
        if rpr is None:
            rpr = ElementTree.SubElement(style, f"{{{W_NS}}}rPr")
        _set_run_color(rpr, "000000")


def _set_theme_fonts(theme_root: ElementTree.Element | None, mode: str) -> None:
    if theme_root is None:
        return
    latin_font = "Times New Roman"
    east_asia_font = "SimSun" if mode == "zh" else "Times New Roman"
    for tag in ("majorFont", "minorFont"):
        node = theme_root.find(f".//a:{tag}", {"a": A_NS})
        if node is None:
            continue
        for child_name, typeface in (("latin", latin_font), ("ea", east_asia_font), ("cs", latin_font)):
            child = node.find(f"a:{child_name}", {"a": A_NS})
            if child is None:
                child = ElementTree.SubElement(node, f"{{{A_NS}}}{child_name}")
            child.set("typeface", typeface)


def _paragraph_full_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{{{W_NS}}}t":
            parts.append(node.text or "")
        elif node.tag == f"{{{W_NS}}}tab":
            parts.append(" ")
    return "".join(parts).strip()


def _set_paragraph_text(paragraph: ElementTree.Element, text: str) -> None:
    for child in list(paragraph):
        paragraph.remove(child)
    run = ElementTree.SubElement(paragraph, f"{{{W_NS}}}r")
    text_node = ElementTree.SubElement(run, f"{{{W_NS}}}t")
    text_node.text = text


def _ensure_reference_heading(document_root: ElementTree.Element, mode: str) -> bool:
    paragraphs = document_root.findall(".//w:body/w:p", {"w": W_NS})
    if not paragraphs:
        return False
    texts = [_paragraph_full_text(p) for p in paragraphs]
    if any(text.lower() == "references" or text == "参考文献" for text in texts):
        return False

    for index, text in enumerate(texts):
        if not re.fullmatch(r"\d{1,3}", text):
            continue
        following = [t for t in texts[index + 1 : index + 6] if t]
        if len(following) < 2:
            continue
        looks_like_bibliography = sum(
            1
            for item in following
            if re.search(r"\b(19|20)\d{2}\b", item)
            or "doi" in item.lower()
            or "http" in item.lower()
            or re.search(r"\bet al\.?\b", item, re.IGNORECASE)
        )
        if looks_like_bibliography < 2:
            continue
        heading = "参考文献" if mode == "zh" else "References"
        _set_paragraph_text(paragraphs[index], heading)
        ppr = paragraphs[index].find("w:pPr", {"w": W_NS})
        if ppr is None:
            ppr = ElementTree.Element(f"{{{W_NS}}}pPr")
            paragraphs[index].insert(0, ppr)
        pstyle = ppr.find("w:pStyle", {"w": W_NS})
        if pstyle is None:
            pstyle = ElementTree.SubElement(ppr, f"{{{W_NS}}}pStyle")
        pstyle.set(_w_attr("val"), "Heading1")
        return True
    return False


def fix_docx_fonts(docx_path: Path, mode: str) -> bool:
    if not docx_path.exists():
        return False
    changed = False
    backup_path = docx_path.with_suffix(docx_path.suffix + ".bak_fonts")
    if not backup_path.exists():
        shutil.copy2(docx_path, backup_path)
    with zipfile.ZipFile(docx_path, "r") as zin:
        entries = [(item, zin.read(item.filename)) for item in zin.infolist()]
    names = {item.filename for item, _ in entries}
    if "word/styles.xml" not in names:
        return False
    document_xml = next(data for item, data in entries if item.filename == "word/document.xml")
    document_root = ElementTree.fromstring(document_xml)
    styles_xml = next(data for item, data in entries if item.filename == "word/styles.xml")
    styles_root = ElementTree.fromstring(styles_xml)
    theme_root = None
    if "word/theme/theme1.xml" in names:
        theme_xml = next(data for item, data in entries if item.filename == "word/theme/theme1.xml")
        theme_root = ElementTree.fromstring(theme_xml)

    doc_defaults = styles_root.find(".//w:docDefaults", {"w": W_NS})
    if doc_defaults is None:
        doc_defaults = ElementTree.SubElement(styles_root, f"{{{W_NS}}}docDefaults")
    rpr_default = doc_defaults.find("w:rPrDefault", {"w": W_NS})
    if rpr_default is None:
        rpr_default = ElementTree.SubElement(doc_defaults, f"{{{W_NS}}}rPrDefault")
    rpr = rpr_default.find("w:rPr", {"w": W_NS})
    if rpr is None:
        rpr = ElementTree.SubElement(rpr_default, f"{{{W_NS}}}rPr")
    _set_rfonts(rpr, mode)

    for style_id in FONT_STYLE_IDS:
        style = _style_by_id(styles_root, style_id)
        rpr = style.find("w:rPr", {"w": W_NS})
        if rpr is None:
            rpr = ElementTree.SubElement(style, f"{{{W_NS}}}rPr")
        _set_rfonts(rpr, mode)

    for rpr in styles_root.findall(".//w:rPr", {"w": W_NS}):
        _set_rfonts(rpr, mode)

    _force_heading_style_black(styles_root)
    reference_heading_changed = _ensure_reference_heading(document_root, mode)

    _set_theme_fonts(theme_root, mode)
    new_document = ElementTree.tostring(document_root, encoding="utf-8", xml_declaration=True)
    new_styles = ElementTree.tostring(styles_root, encoding="utf-8", xml_declaration=True)
    new_theme = ElementTree.tostring(theme_root, encoding="utf-8", xml_declaration=True) if theme_root is not None else None
    # Create the temp in the SAME directory as the target so the atomic replace
    # stays on one filesystem — os.replace fails across drives on Windows (WinError 17).
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".docx", dir=str(docx_path.parent))
    os.close(tmp_fd)
    tmp = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item, data in entries:
                if item.filename == "word/styles.xml":
                    data = new_styles
                    changed = True
                elif item.filename == "word/document.xml" and reference_heading_changed:
                    data = new_document
                    changed = True
                elif item.filename == "word/theme/theme1.xml" and new_theme is not None:
                    data = new_theme
                    changed = True
                zout.writestr(item, data)
        tmp.replace(docx_path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return changed


def check_parenthesized_numeric_citations(text: str) -> list[str]:
    """Return findings for citations like ([1]); required style is plain [1]."""
    findings: list[str] = []
    for match in re.finditer(r"\(\[\d+(?:\s*[,–-]\s*\d+)*\]\)", text):
        findings.append(
            f"Citation '{match.group(0)}' uses extra parentheses. Use plain square-bracket numeric style, e.g. [1]."
        )
    return findings


def check_glued_heading_numbers(paragraphs: list[str]) -> list[str]:
    """Return findings for headings rendered as `1Introduction`."""
    findings: list[str] = []
    for para in paragraphs[:80]:
        candidate = para.strip()
        if not candidate or len(candidate) > 140:
            continue
        if re.match(r"^\d+(?:\.\d+)*\s+[A-Z]", candidate):
            continue
        if not GLUED_HEADING_NUMBER_PATTERN.match(candidate):
            continue
        title_part = re.sub(r"^\s*\d+(?:\.\d+)*", "", candidate, count=1)
        title_lower = title_part.lower()
        if title_lower.startswith(COMMON_HEADING_STARTS) or not re.search(r"[.!?]\s*$", candidate):
            findings.append(
                f"Heading number is glued to the English title: '{candidate[:80]}'. "
                "Use a space after the section number, e.g. '1 Introduction'."
            )
    return findings


def check_docx(
    path: Path,
    min_chars: int,
    source_tex: str = "",
    expected_title: str = "",
    language: str = "auto",
) -> WordGuardResult:
    findings: list[str] = []
    text = ""
    paragraph_count = 0
    paragraphs_ordered: list[str] = []
    document_xml: bytes | None = None
    title_ok = True
    first_paragraph = ""

    if not path.exists():
        return WordGuardResult(str(path), False, 0, 0, ["file does not exist"])
    if path.suffix.lower() != ".docx":
        findings.append("file extension is not .docx")

    names: set[str] = set()
    try:
        with zipfile.ZipFile(path) as docx:
            names = set(docx.namelist())
            for required in ("[Content_Types].xml", "word/document.xml"):
                if required not in names:
                    findings.append(f"missing {required}")
            if "word/document.xml" in names:
                document_xml = docx.read("word/document.xml")
                text, paragraph_count = extract_text(document_xml)
                paragraphs_ordered = extract_paragraphs_ordered(document_xml)
    except zipfile.BadZipFile:
        return WordGuardResult(str(path), False, 0, 0, ["not a valid zip/docx file"])
    except ElementTree.ParseError as exc:
        findings.append(f"word/document.xml parse error: {exc}")

    if len(text) < min_chars:
        findings.append(f"text is too short: {len(text)} chars < {min_chars}")
    if paragraph_count == 0:
        findings.append("no non-empty paragraphs found — docx may be empty or corrupted")
        # Check if images exist but text was lost (broken image conversion)
        has_images = any(name.startswith("word/media/") for name in names)
        if has_images:
            findings.append(
                "Images found in docx but no text — pandoc image conversion likely failed. "
                "Verify: (1) images are PNG/JPG format, (2) `--resource-path` and `--extract-media` flags used, "
                "(3) pandoc ran from the `final_paper/` directory so relative paths resolve."
            )
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            findings.append(f"unresolved placeholder pattern found: {pattern}")

    # Formatting correctness: raw LaTeX must not leak into the rendered docx.
    latex_tokens: set[str] = {m.group(0) for m in LATEX_COMMAND_PATTERN.finditer(text)}
    latex_tokens.update(m.group(0).rstrip("{").strip() for m in GENERIC_LATEX_MACRO_PATTERN.finditer(text))
    latex_tokens.update(m.group(0) for m in LATEX_SINGLE_CHAR_ESCAPE.finditer(text))
    if latex_tokens:
        sample = ", ".join(sorted(latex_tokens)[:6])
        findings.append(
            f"Unrendered LaTeX commands in text (e.g. {sample}) — pandoc emitted raw source "
            "instead of rendered output. Flatten \\input/\\include and expand custom macros "
            "(\\newcommand) before conversion."
        )
    if BROKEN_CROSSREF in text:
        findings.append(
            "Broken cross-references '[?]' — \\ref/\\eqref did not resolve. "
            "Add `--filter pandoc-crossref` (and matching \\label definitions)."
        )
    citeproc_hits = CITEPROC_LEFTOVER_PATTERN.findall(text)
    if citeproc_hits:
        findings.append(
            f"Unresolved citation markers found ({len(citeproc_hits)}, e.g. {citeproc_hits[0]}). "
            "Run pandoc with --citeproc and --bibliography=references.bib so citations render."
        )
    if RAW_MATH_PATTERN.search(text):
        findings.append(
            "Raw inline LaTeX math (e.g. `$\\alpha$`) survived into the docx — math was not "
            "converted to Word equations. Verify the source compiles and pandoc handled the math."
        )

    # Raw Markdown emphasis: **bold** and *italic* markers must not survive into Word.
    markdown_bold_hits = MARKDOWN_BOLD_PATTERN.findall(text)
    if markdown_bold_hits:
        sample = ", ".join(h[:60] for h in markdown_bold_hits[:4])
        findings.append(
            f"Raw Markdown emphasis markers found ({len(markdown_bold_hits)} bold, e.g. {sample}). "
            "Bold markers (**...**) are Markdown source formatting, not rendered Word content. "
            "Convert Markdown to actual Word bold formatting or remove the markers."
        )
    markdown_italic_hits = MARKDOWN_ITALIC_PATTERN.findall(text)
    if markdown_italic_hits:
        sample = ", ".join(h[:60] for h in markdown_italic_hits[:4])
        findings.append(
            f"Raw Markdown emphasis markers found ({len(markdown_italic_hits)} italic, e.g. {sample}). "
            "Italic markers (*text*) are Markdown source formatting, not rendered Word content. "
            "Convert Markdown to actual Word italic formatting or remove the markers."
        )

    # Chinese encoding checks: detect garbled text / mojibake
    has_chinese = bool(re.search(r"[一-鿿]", text))
    if has_chinese:
        garbled = re.findall(r"[\x80-\xff]{4,}", text)
        if garbled:
            findings.append(f"Possible garbled Chinese text: {len(garbled)} suspicious byte sequences. Re-export with UTF-8 encoding.")
        # Check for common encoding corruption patterns
        corruption = re.findall(r"鍚堛[劧渚佃繚閫嗘]", text)  # common gbk-decoded-as-utf8 pattern
        if corruption:
            findings.append("Chinese encoding corruption detected: GBK text decoded as UTF-8. Re-export with proper encoding.")

    style_finding = citation_style_finding(text, source_tex)
    if style_finding:
        findings.append(style_finding)

    author_year_finding = author_year_citation_finding(text, source_tex)
    if author_year_finding:
        findings.append(author_year_finding)

    fonts = font_profile(path, text, language)
    findings.extend(fonts.findings)
    findings.extend(word_style_findings(path, fonts.mode))

    # --- Title check (unified) ---
    # Resolve expected title: explicit arg > --tex extraction > sibling main.tex > parent final_paper/main.tex
    resolved_expected = expected_title
    if not resolved_expected:
        # Try the --tex path would be passed from main(); here we use the auto-detection as fallback
        resolved_expected = extract_title_from_tex(path.parent / "main.tex") or (
            extract_title_from_tex(path.parent.parent / "final_paper" / "main.tex")
        ) or ""

    title_finding, first_paragraph = check_title_in_front(paragraphs_ordered, resolved_expected or None)
    if title_finding:
        findings.append(title_finding)
        title_ok = False
    else:
        title_ok = True

    # Citation display check: plain [1] is required; ([1]) is not.
    findings.extend(check_parenthesized_numeric_citations(text))
    findings.extend(check_glued_heading_numbers(paragraphs_ordered))

    return WordGuardResult(
        str(path), not findings, len(text), paragraph_count, findings,
        title_ok=title_ok,
        expected_title=resolved_expected,
        first_paragraph=first_paragraph,
        font_ok=fonts.ok,
        expected_font=fonts.expected,
        actual_fonts=fonts.actual,
    )


def to_markdown(result: WordGuardResult) -> str:
    lines = [
        "# Word Guard Report",
        "",
        f"- Path: `{result.path}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Text length: {result.text_length}",
        f"- Paragraph count: {result.paragraph_count}",
        "",
        "## Title Check",
        "",
        f"- Status: {'PASS' if result.title_ok else 'FAIL'}",
        f"- Expected title: {result.expected_title or '(none)'}",
        f"- First non-empty paragraph: {result.first_paragraph[:120] or '(none)'}",
        "",
        "## Font Check",
        "",
        f"- Status: {'PASS' if result.font_ok else 'FAIL'}",
        f"- Expected font: {result.expected_font or '(not checked)'}",
        f"- Actual fonts/theme refs: {', '.join(result.actual_fonts or []) or '(none detected)'}",
        "",
        "## Findings",
        "",
    ]
    if result.findings:
        lines.extend(f"- {finding}" for finding in result.findings)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    docx_path = Path(args.docx_path)

    # Resolve source_tex for citation style checking.
    source_tex = ""
    tex_path = args.tex
    if not tex_path:
        sibling_tex = docx_path.parent / "main.tex"
        if sibling_tex.exists():
            tex_path = sibling_tex
    if tex_path and tex_path.exists():
        source_tex = tex_path.read_text(encoding="utf-8", errors="ignore")

    # Resolve expected title: --expected-title > Chinese translation (for .zh.docx) > --tex extraction.
    expected_title = args.expected_title or ""
    if not expected_title and docx_path.stem.endswith(".zh"):
        expected_title = extract_title_from_chinese_translation(docx_path) or ""
    if not expected_title and tex_path:
        expected_title = extract_title_from_tex(tex_path) or ""

    if args.fix_fonts:
        mode = args.language
        if mode == "auto":
            mode = "zh" if docx_path.name.endswith(".zh.docx") or docx_path.stem.endswith(".zh") else "en"
        fix_docx_fonts(docx_path, mode)

    result = check_docx(docx_path, args.min_chars, source_tex, expected_title, args.language)
    markdown = to_markdown(result)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")

    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
