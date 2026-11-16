#!/usr/bin/env python3
"""Lightweight structural checks for generated Word .docx files."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import posixpath
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote
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
# Pandoc may split a visible figure reference into multiple Word runs and may
# use a non-breaking space for LaTeX's ``Figure~\ref{...}``.  Match the
# rendered surface rather than the source-token shape so the Word gate does
# not report a false missing-reference finding.
FIGURE_REFERENCE_PATTERN = re.compile(
    r"\b(?i:fig(?:ure)?s?)\.?[^\S\r\n]*(?:[Ss]?\d+(?:\.\d+)*[a-z]?|[A-Z])(?!\w)",
)
# Require a numbered reference, not repeated prose ("figure figure skating")
# or author names. Punctuation can separate tokens without a space: Fig.Fig.2.
REPEATED_FIGURE_MARKER_PATTERN = re.compile(
    r"(?<!\w)(?:fig(?:ure)?s?\.[^\S\r\n]*|fig(?:ure)?s?[^\S\r\n]+)"
    r"fig(?:ure)?s?\.?[^\S\r\n]*[s]?\d+(?:\.\d+)*[a-z]?(?!\w)",
    re.IGNORECASE,
)


def has_visible_figure_reference(text: str) -> bool:
    """Return whether rendered Word text contains a visible figure reference."""

    return bool(FIGURE_REFERENCE_PATTERN.search(text.replace("\u00ad", "")))


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


def author_year_citation_finding(
    docx_text: str, source_tex: str, *, citation_style: str = "auto"
) -> str | None:
    """Assess an explicit target or a known source mismatch, never a global ban.

    Auto leaves unknown venue styles unclassified. Explicit configuration takes
    precedence over a possibly older LaTeX bibliography style. These text
    heuristics do not certify CSL conformance or superscript run formatting.
    """
    if citation_style not in {"auto", "numeric", "author-year", "superscript"}:
        raise ValueError(f"Unknown citation style: {citation_style}")
    if citation_style == "auto":
        return citation_style_finding(docx_text, source_tex)
    author_year = AUTHOR_DATE_CITE_PATTERN.search(docx_text)
    numeric = NUMERIC_CITE_PATTERN.search(docx_text)
    if citation_style in {"numeric", "superscript"} and author_year and not numeric:
        return (
            f"Citation style mismatch: configured {citation_style}, but Word shows "
            f"author-year citations (e.g. '{author_year.group(0)}'). Re-export with the target CSL."
        )
    if citation_style == "author-year" and numeric and not author_year:
        return "Citation style mismatch: configured author-year, but Word shows square-bracket numeric citations."
    return None


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
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
EMU_PER_CM = 360000
# Keep Word output renderable even when pandoc omits section geometry.  These
# are the same A4/default-margin values used by submission_check.py.
A4_WIDTH_TWIPS = "11906"
A4_HEIGHT_TWIPS = "16838"
DEFAULT_MARGIN_TWIPS = "1440"
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
    visible_figure_media_count: int = 0
    unsupported_media: list[str] | None = None
    # Structural ok/font_ok do not certify the size of text inside a figure.
    figure_placements: list[dict] = field(default_factory=list)
    figure_warnings: list[str] = field(default_factory=list)
    figure_legibility_status: str = "not_assessed"


def _image_relationships(relationships_xml: bytes | None) -> dict[str, str]:
    if relationships_xml is None:
        return {}
    root = ElementTree.fromstring(relationships_xml)
    relationships = {}
    for node in root.iter(f"{{{PACKAGE_NS}}}Relationship"):
        if not node.get("Type", "").endswith("/image") or node.get("TargetMode", "").lower() == "external":
            continue
        target = unquote(node.get("Target", "")).replace("\\", "/")
        if not target or ":" in target:
            continue
        target = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "word/" + target)
        if target.startswith("../") or target == "..":
            continue
        if node.get("Id"):
            relationships[node.get("Id")] = target
    return relationships


def inspect_word_media(
    document_xml: bytes | None,
    relationships_xml: bytes | None,
    media_payloads: dict[str, bytes],
) -> tuple[list[str], list[str]]:
    """Return reader-visible PNG paths and unsupported DOCX media paths."""

    unsupported = sorted(
        name
        for name in media_payloads
        if PurePosixPath(name).suffix.lower() == ".pdf"
    )
    if document_xml is None or relationships_xml is None:
        return [], unsupported
    try:
        document_root = ElementTree.fromstring(document_xml)
        relationships = _image_relationships(relationships_xml)
    except ElementTree.ParseError:
        return [], unsupported
    relationship_attrs = {
        f"{{{R_NS}}}embed",
        f"{{{R_NS}}}id",
    }
    visible_png: list[str] = []
    for element in document_root.iter():
        for attribute in relationship_attrs:
            relationship_id = element.get(attribute)
            target = relationships.get(str(relationship_id or ""))
            if not target or target in visible_png:
                continue
            encoded = media_payloads.get(target)
            if (
                PurePosixPath(target).suffix.lower() == ".png"
                and isinstance(encoded, bytes)
                and encoded.startswith(b"\x89PNG\r\n\x1a\n")
            ):
                visible_png.append(target)
    return visible_png, unsupported


def inspect_word_figure_geometry(
    document_xml: bytes | None,
    relationships_xml: bytes | None,
    media_payloads: dict[str, bytes],
    *,
    min_dpi: float = 300.0,
    aspect_tolerance: float = 0.02,
) -> tuple[list[dict], list[str]]:
    """Inspect each main-document picture placement, without changing the DOCX.

    Measures simple DrawingML inline/anchor pictures and rectangular crops.
    Missing raster readers, VML, alternate representations, rotation and complex
    fills remain unknown. DPI thresholds are advisory, not venue requirements.
    Raster DPI (including embedded metadata) cannot establish label point sizes.
    No editable source is guessed from a filename or an unrelated figure.
    """
    if not math.isfinite(min_dpi) or min_dpi <= 0:
        raise ValueError("min_dpi must be finite and positive")
    if not math.isfinite(aspect_tolerance) or aspect_tolerance < 0:
        raise ValueError("aspect_tolerance must be finite and nonnegative")
    if document_xml is None:
        return [], ["Figure geometry unknown: Word document XML is unavailable."]
    try:
        root = ElementTree.fromstring(document_xml)
        relationships = _image_relationships(relationships_xml)
    except ElementTree.ParseError as exc:
        return [], [f"Figure geometry unknown: invalid document/relationship XML ({exc})."]
    parents = {child: parent for parent in root.iter() for child in parent}
    paragraphs = {node: i for i, node in enumerate(root.iter(_w_attr("p")), 1)}
    placements: list[dict] = []
    warnings: list[str] = []
    raster_cache: dict[str, tuple[int | None, int | None, str | None]] = {}
    try:
        from PIL import Image
    except ImportError:
        Image = None
    vml_image = "{urn:schemas-microsoft-com:vml}imagedata"
    for blip in root.iter():
        if blip.tag not in {_a_attr("blip"), vml_image}:
            continue
        ancestors = []
        parent = parents.get(blip)
        while parent is not None:
            ancestors.append(parent)
            parent = parents.get(parent)
        # Deleted revisions are not a current reader-visible figure.
        if any(node.tag in {_w_attr("del"), _w_attr("moveFrom")} for node in ancestors):
            continue
        frame = next((node for node in ancestors if node.tag in {f"{{{WP_NS}}}inline", f"{{{WP_NS}}}anchor"}), None)
        picture = next((node for node in ancestors if node.tag == f"{{{PIC_NS}}}pic"), None)
        rid = blip.get(f"{{{R_NS}}}embed") or blip.get(f"{{{R_NS}}}id") or blip.get(f"{{{R_NS}}}link", "")
        target = relationships.get(rid)
        payload = media_payloads.get(target) if target else None
        row = {
            "placement_index": len(placements) + 1,
            "paragraph_index": next((paragraphs[node] for node in ancestors if node in paragraphs), None),
            "relationship_id": rid, "media_path": target,
            "media_sha256": hashlib.sha256(payload).hexdigest() if payload is not None else None,
            "placement_kind": frame.tag.rsplit("}", 1)[-1] if frame is not None else "unsupported",
            "width_cm": None, "height_cm": None,
            "pixel_width": None, "pixel_height": None,
            "crop_fraction": None, "effective_dpi_x": None, "effective_dpi_y": None,
            "aspect_ratio_error": None, "geometry_status": "unknown",
            "min_dpi_reference": min_dpi, "pixel_density_status": "unknown",
            "label_size_status": "unknown", "min_label_pt": None,
            "label_size_reason": "No reliably matched editable source with measured label sizes; DPI is not label size.",
            "visual_review_required": True, "warnings": [],
        }
        reasons = row["warnings"]
        if payload is None:
            reasons.append("Embedded image relationship/payload unavailable; external images are not fetched.")
        else:
            if target not in raster_cache:
                if Image is None:
                    raster_cache[target] = (None, None, "Raster dimensions unknown: optional Pillow reader is unavailable.")
                else:
                    try:
                        with Image.open(io.BytesIO(payload)) as raster:
                            width_px, height_px = raster.size
                            raster.verify()
                        raster_cache[target] = (width_px, height_px, None)
                    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
                        raster_cache[target] = (None, None, f"Raster dimensions unavailable ({type(exc).__name__}).")
            row["pixel_width"], row["pixel_height"], error = raster_cache[target]
            if error:
                reasons.append(error)
        try:
            if frame is None:
                raise ValueError("No supported DrawingML inline/anchor placement (VML is not measured).")
            extent = frame.find(f"{{{WP_NS}}}extent")
            if extent is None:
                raise ValueError("Word placement extent is missing.")
            cx, cy = int(extent.get("cx", "0")), int(extent.get("cy", "0"))
            if cx <= 0 or cy <= 0:
                raise ValueError("Word placement extent must be positive.")
            row["width_cm"], row["height_cm"] = cx / EMU_PER_CM, cy / EMU_PER_CM
            if picture is None or len(list(frame.iter(f"{{{PIC_NS}}}pic"))) != 1:
                raise ValueError("Composite drawing geometry requires visual review.")
            if any(node.tag.endswith("}AlternateContent") for node in ancestors):
                raise ValueError("AlternateContent branch selection requires visual review.")
            xfrm = picture.find(f"{{{PIC_NS}}}spPr/{_a_attr('xfrm')}")
            if xfrm is not None:
                if int(xfrm.get("rot", "0")) % 21600000:
                    raise ValueError("Rotated picture geometry requires visual review.")
                local_extent = xfrm.find(_a_attr("ext"))
                if local_extent is not None and any(abs(int(local_extent.get(axis, "0")) - value) > 1 for axis, value in (("cx", cx), ("cy", cy))):
                    raise ValueError("Picture and Word frame extents differ; scale is unknown.")
            fill = picture.find(f"{{{PIC_NS}}}blipFill")
            if fill is None or fill.find(_a_attr("stretch")) is None or fill.find(_a_attr("tile")) is not None:
                raise ValueError("Unsupported image fill; effective geometry is unknown.")
            fill_rect = fill.find(f"{_a_attr('stretch')}/{_a_attr('fillRect')}")
            if fill_rect is not None and any(float(value) != 0 for value in fill_rect.attrib.values()):
                raise ValueError("Inset image fill requires visual review.")
            crop = fill.find(_a_attr("srcRect"))
            fractions = {}
            for side in ("l", "t", "r", "b"):
                value = crop.get(side, "0") if crop is not None else "0"
                fractions[side] = float(value[:-1]) / 100 if value.endswith("%") else float(value) / 100000
            if any(not math.isfinite(value) or value < 0 or value >= 1 for value in fractions.values()):
                raise ValueError("Unsupported or invalid crop rectangle.")
            retained_x, retained_y = 1 - fractions["l"] - fractions["r"], 1 - fractions["t"] - fractions["b"]
            if retained_x <= 0 or retained_y <= 0:
                raise ValueError("Crop rectangle removes the entire image.")
            row["crop_fraction"] = fractions
            if row["pixel_width"] is not None:
                px = row["pixel_width"] * retained_x
                py = row["pixel_height"] * retained_y
                dpi_x, dpi_y = px * 914400 / cx, py * 914400 / cy
                aspect_error = abs((cx / cy) / (px / py) - 1)
                row.update(effective_dpi_x=dpi_x, effective_dpi_y=dpi_y,
                           aspect_ratio_error=aspect_error, geometry_status="measured",
                           pixel_density_status="below_reference" if min(dpi_x, dpi_y) < min_dpi else "meets_reference")
                if min(dpi_x, dpi_y) < min_dpi:
                    reasons.append(f"Effective pixel density {dpi_x:.1f} x {dpi_y:.1f} DPI is below the advisory {min_dpi:g} DPI reference.")
                if aspect_error > aspect_tolerance:
                    reasons.append(f"Placement aspect ratio differs from the cropped raster by {aspect_error:.1%}; check stretching in the export source.")
        except (ValueError, TypeError, OverflowError) as exc:
            reasons.append(str(exc))
        placements.append(row)
        warnings.extend(f"Figure placement {row['placement_index']} ({target or rid or 'unresolved'}): {reason}" for reason in reasons)
    if placements:
        warnings.append("Figure label size is unknown; inspect the final Word rendering at its actual placed size. Sufficient DPI does not certify readable labels.")
    return placements, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a generated .docx file.")
    parser.add_argument("docx_path")
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument("--min-figure-dpi", type=float, default=300.0,
                        help="Advisory effective pixel density reference, not a label-size or venue acceptance rule.")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="Optional report path.")
    parser.add_argument("--tex", type=Path, help="Path to main.tex for title extraction.")
    parser.add_argument("--expected-title", help="Expected paper title (overrides --tex extraction).")
    parser.add_argument(
        "--citation-style", choices=("auto", "numeric", "author-year", "superscript"), default="auto",
        help="Explicit target citation style overrides TeX inference; auto only reports known source mismatches.",
    )
    parser.add_argument(
        "--fix-fonts",
        action="store_true",
        help="Apply --font-policy before checking; preserve is a no-op for existing venue styling.",
    )
    parser.add_argument(
        "--font-policy", choices=("preserve", "fallback"), default="preserve",
        help="Preserve template fonts by default. Explicit fallback fills only unspecified document defaults and page geometry.",
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


def font_profile(docx_path: Path, text: str, language: str = "auto", *, font_policy: str = "preserve") -> FontProfile:
    if font_policy not in {"preserve", "fallback"}:
        raise ValueError(f"Unknown font policy: {font_policy}")
    mode = detect_font_mode(docx_path, text, language)
    expected = "Document/template fonts (venue-specific font requirement not supplied)"
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
    # Font presence alone cannot establish venue compliance. Theme references
    # and custom title/body fonts are legitimate, not a reason to force TNR.
    return FontProfile(mode, not findings, expected, actual, findings)


def word_style_findings(docx_path: Path, mode: str) -> list[str]:
    findings: list[str] = []
    try:
        with zipfile.ZipFile(docx_path) as docx:
            names = set(docx.namelist())
            if "word/styles.xml" not in names or "word/document.xml" not in names:
                return findings
            ElementTree.fromstring(docx.read("word/styles.xml"))
            document_root = ElementTree.fromstring(docx.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
        return findings

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


def _subelement(parent, tag: str, attributes: dict[str, str] | None = None):
    """Create a child using its parent's XML backend (read-only ET or lxml)."""
    child = parent.makeelement(tag, attributes or {})
    parent.append(child)
    return child


def _ensure_child(parent: ElementTree.Element, tag: str) -> ElementTree.Element:
    child = parent.find(tag, {"w": W_NS, "a": A_NS})
    if child is None:
        child = _subelement(parent, tag.replace("w:", f"{{{W_NS}}}").replace("a:", f"{{{A_NS}}}"))
    return child


def _style_by_id(styles_root: ElementTree.Element, style_id: str) -> ElementTree.Element:
    style = styles_root.find(f".//w:style[@w:styleId='{style_id}']", {"w": W_NS})
    if style is not None:
        return style
    style = _subelement(styles_root, f"{{{W_NS}}}style", {_w_attr("type"): "paragraph", _w_attr("styleId"): style_id})
    _subelement(style, f"{{{W_NS}}}name", {_w_attr("val"): style_id})
    return style


def _set_rfonts(rpr: ElementTree.Element, mode: str) -> None:
    rfonts = rpr.find("w:rFonts", {"w": W_NS})
    if rfonts is None:
        rfonts = _subelement(rpr, f"{{{W_NS}}}rFonts")
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
        color = _subelement(rpr, f"{{{W_NS}}}color")
    color.set(_w_attr("val"), color_value)


def _force_heading_style_black(styles_root: ElementTree.Element) -> None:
    for style_id in ("Heading1", "Heading2", "Heading3"):
        style = _style_by_id(styles_root, style_id)
        rpr = style.find("w:rPr", {"w": W_NS})
        if rpr is None:
            rpr = _subelement(style, f"{{{W_NS}}}rPr")
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
                child = _subelement(node, f"{{{A_NS}}}{child_name}")
            child.set("typeface", typeface)


def _ensure_page_geometry(document_root: ElementTree.Element) -> bool:
    """Fill missing page geometry only under explicitly requested fallback."""
    body = document_root.find(f"{{{W_NS}}}body")
    if body is None:
        return False
    sectpr = body.find(f"{{{W_NS}}}sectPr")
    if sectpr is None:
        sectpr = _subelement(body, f"{{{W_NS}}}sectPr")
        changed = True
    else:
        changed = False

    pg_sz = sectpr.find(f"{{{W_NS}}}pgSz")
    if pg_sz is None:
        pg_sz = sectpr.makeelement(f"{{{W_NS}}}pgSz", {})
        sectpr.insert(0, pg_sz)
        changed = True
    for attr, value in (("w", A4_WIDTH_TWIPS), ("h", A4_HEIGHT_TWIPS)):
        key = _w_attr(attr)
        if not pg_sz.get(key):
            pg_sz.set(key, value)
            changed = True

    pg_mar = sectpr.find(f"{{{W_NS}}}pgMar")
    if pg_mar is None:
        pg_mar = sectpr.makeelement(f"{{{W_NS}}}pgMar", {})
        # Keep section children in the conventional order before footnotes.
        insert_at = 1 if len(sectpr) else 0
        sectpr.insert(insert_at, pg_mar)
        changed = True
    margins = {
        "top": DEFAULT_MARGIN_TWIPS,
        "right": DEFAULT_MARGIN_TWIPS,
        "bottom": DEFAULT_MARGIN_TWIPS,
        "left": DEFAULT_MARGIN_TWIPS,
        "header": "720",
        "footer": "720",
        "gutter": "0",
    }
    for attr, value in margins.items():
        key = _w_attr(attr)
        if not pg_mar.get(key):
            pg_mar.set(key, value)
            changed = True
    return changed


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
    run = _subelement(paragraph, f"{{{W_NS}}}r")
    text_node = _subelement(run, f"{{{W_NS}}}t")
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
            ppr = paragraphs[index].makeelement(f"{{{W_NS}}}pPr", {})
            paragraphs[index].insert(0, ppr)
        pstyle = ppr.find("w:pStyle", {"w": W_NS})
        if pstyle is None:
            pstyle = _subelement(ppr, f"{{{W_NS}}}pStyle")
        pstyle.set(_w_attr("val"), "Heading1")
        return True
    return False


def _parse_font_xml(data: bytes, xml_backend):
    # ElementTree drops namespace declarations referenced only by attribute
    # VALUES such as mc:Ignorable="w14 w15". Word rejects that serialization.
    # lxml preserves each element's namespace scope, including unused aliases.
    parser = xml_backend.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    root = xml_backend.fromstring(data, parser=parser)
    if root.getroottree().docinfo.doctype:
        raise ValueError("Word font repair does not accept DTD-bearing XML")
    mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    qname_lists = {f"{{{mc}}}{name}" for name in (
        "Ignorable", "MustUnderstand", "ProcessContent", "PreserveAttributes", "PreserveElements"
    )}
    for node in root.iter():
        for attribute, value in node.attrib.items():
            if attribute in qname_lists or (node.tag == f"{{{mc}}}Choice" and attribute == "Requires"):
                for token in value.split():
                    prefix = token.split(":", 1)[0]
                    if prefix != "xml" and prefix not in node.nsmap:
                        raise ValueError(f"Word font repair found unbound compatibility prefix: {prefix}")
    return root


def fix_docx_fonts(docx_path: Path, mode: str, *, font_policy: str = "preserve") -> bool:
    """Preserve venue styling; explicit fallback supplies missing defaults only.

    The two-argument API remains supported and now safely preserves the input.
    Fallback does not rewrite named styles, theme fonts, direct run formatting,
    heading colors or bibliography text.
    """
    if font_policy not in {"preserve", "fallback"}:
        raise ValueError(f"Unknown font policy: {font_policy}")
    if font_policy == "preserve":
        return False
    if mode not in {"en", "zh"}:
        raise ValueError("Fallback font mode must be en or zh")
    if not docx_path.exists():
        return False
    changed = False
    backup_path = docx_path.with_suffix(docx_path.suffix + ".bak_fonts")
    with zipfile.ZipFile(docx_path, "r") as zin:
        entries = [(item, zin.read(item.filename)) for item in zin.infolist()]
    names = {item.filename for item, _ in entries}
    if "word/styles.xml" not in names:
        return False
    try:
        from lxml import etree as namespace_xml
    except ImportError as exc:
        raise RuntimeError("--fix-fonts requires lxml (also used by python-docx); input was not modified") from exc
    document_xml = next(data for item, data in entries if item.filename == "word/document.xml")
    document_root = _parse_font_xml(document_xml, namespace_xml)
    styles_xml = next(data for item, data in entries if item.filename == "word/styles.xml")
    styles_root = _parse_font_xml(styles_xml, namespace_xml)
    theme_root = None
    if "word/theme/theme1.xml" in names:
        theme_xml = next(data for item, data in entries if item.filename == "word/theme/theme1.xml")
        theme_root = _parse_font_xml(theme_xml, namespace_xml)

    doc_defaults = styles_root.find(".//w:docDefaults", {"w": W_NS})
    if doc_defaults is None:
        doc_defaults = _subelement(styles_root, f"{{{W_NS}}}docDefaults")
    rpr_default = doc_defaults.find("w:rPrDefault", {"w": W_NS})
    if rpr_default is None:
        rpr_default = _subelement(doc_defaults, f"{{{W_NS}}}rPrDefault")
    rpr = rpr_default.find("w:rPr", {"w": W_NS})
    if rpr is None:
        rpr = _subelement(rpr_default, f"{{{W_NS}}}rPr")
    before_defaults = namespace_xml.tostring(styles_root)
    rfonts = rpr.find("w:rFonts", {"w": W_NS})
    if rfonts is None:
        rfonts = _subelement(rpr, f"{{{W_NS}}}rFonts")
    for slot, themes in (
        ("ascii", ("asciiTheme",)), ("hAnsi", ("hAnsiTheme",)),
        ("eastAsia", ("eastAsiaTheme",)), ("cs", ("csTheme", "cstheme")),
    ):
        if not rfonts.get(_w_attr(slot)) and not any(rfonts.get(_w_attr(theme)) for theme in themes):
            rfonts.set(_w_attr(slot), "SimSun" if slot == "eastAsia" and mode == "zh" else "Times New Roman")
    styles_changed = namespace_xml.tostring(styles_root) != before_defaults
    geometry_changed = _ensure_page_geometry(document_root)
    if not styles_changed and not geometry_changed:
        return False
    new_document = namespace_xml.tostring(document_root, encoding="utf-8", xml_declaration=True)
    new_styles = namespace_xml.tostring(styles_root, encoding="utf-8", xml_declaration=True)
    new_theme = namespace_xml.tostring(theme_root, encoding="utf-8", xml_declaration=True) if theme_root is not None else None
    for encoded in (new_document, new_styles, new_theme):
        if encoded is not None:
            _parse_font_xml(encoded, namespace_xml)
    if not backup_path.exists():
        shutil.copy2(docx_path, backup_path)
    # Create the temp in the SAME directory as the target so the atomic replace
    # stays on one filesystem — os.replace fails across drives on Windows (WinError 17).
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".docx", dir=str(docx_path.parent))
    os.close(tmp_fd)
    tmp = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item, data in entries:
                if item.filename == "word/styles.xml" and styles_changed:
                    data = new_styles
                    changed = True
                elif item.filename == "word/document.xml" and geometry_changed:
                    data = new_document
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


def internal_reference_findings(document_xml: bytes) -> list[str]:
    """Check actual Word destinations without unwrapping valid bibliography links."""
    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as exc:
        return [f"Word reference XML parse error: {exc}"]
    ns = {"w": W_NS}
    names = [node.get(_w_attr("name"), "") for node in root.findall(".//w:bookmarkStart", ns)]
    bookmarks = set(names)
    findings = [f"Duplicate Word bookmark destination: {name}" for name in bookmarks if names.count(name) > 1]
    findings.extend(duplicate_figure_reference_findings(document_xml))
    for node in root.findall(".//w:hyperlink", ns):
        anchor = node.get(_w_attr("anchor"))
        # r:id addresses a relationship (possibly a different document); an
        # accompanying anchor is not necessarily a local bookmark. _top is built in.
        if anchor and not node.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id") and anchor.lower() != "_top" and anchor not in bookmarks:
            findings.append(f"Internal Word hyperlink has missing destination: {anchor}")
    for paragraph in root.findall(".//w:p", ns):
        preceding = ""
        instructions = []
        # Simple fields and complex fields are both emitted by real Word tools.
        for node in paragraph.iter():
            if node.tag == _w_attr("t"):
                preceding += node.text or ""
            if node.tag == _w_attr("fldSimple"):
                instructions.append((node.get(_w_attr("instr"), ""), preceding))
        complex_instruction = "".join(node.text or "" for node in paragraph.findall(".//w:instrText", ns))
        instructions.append((complex_instruction, ""))
        for instruction, prefix in instructions:
            for match in re.finditer(r'\b(?:REF|PAGEREF)\s+"?([^\s"\\]+)', instruction, re.IGNORECASE):
                anchor = match.group(1)
                if anchor not in bookmarks:
                    findings.append(f"Word REF field has missing destination: {anchor}")
                kind = re.search(r"\b(Figure|Table)\s*$", prefix)
                if kind and anchor.startswith("ps_"):
                    expected = "ps_fig_" if kind.group(1) == "Figure" else "ps_tbl_"
                    if not anchor.startswith(expected):
                        findings.append(f"Word {kind.group(1)} REF points to wrong-kind destination: {anchor}")
    return findings


def duplicate_figure_reference_findings(document_xml: bytes) -> list[str]:
    """Diagnose a repeated rendered marker across runs/links; never delete text.

    Numbered references only. Field instructions, deleted/hidden runs and
    paragraph boundaries are not concatenated into apparent reader text.
    """
    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError:
        return []  # The structural/reference checker owns XML parse diagnostics.

    def visible_text(node: ElementTree.Element, *, outer: bool = False) -> str:
        if node.tag in {_w_attr("del"), _w_attr("moveFrom"), _w_attr("instrText")}:
            return ""
        if node.tag == _w_attr("p") and not outer:
            return ""  # Nested text-box paragraphs are checked separately.
        if node.tag == _w_attr("r"):
            vanish = node.find(f"{_w_attr('rPr')}/{_w_attr('vanish')}")
            if vanish is not None and vanish.get(_w_attr("val"), "true").lower() not in {"0", "false", "off"}:
                return ""
        if node.tag == _w_attr("t"):
            return node.text or ""
        if node.tag == _w_attr("tab"):
            return " "
        if node.tag in {_w_attr("br"), _w_attr("cr")}:
            return "\n"
        return "".join(visible_text(child) for child in node)

    parents = {child: node for node in root.iter() for child in node}
    findings = []
    for index, paragraph in enumerate(root.iter(_w_attr("p")), 1):
        ancestor = parents.get(paragraph)
        deleted = False
        while ancestor is not None:
            deleted |= ancestor.tag in {_w_attr("del"), _w_attr("moveFrom")}
            ancestor = parents.get(ancestor)
        if deleted:
            continue
        text = visible_text(paragraph, outer=True).replace("\u00ad", "")
        for match in REPEATED_FIGURE_MARKER_PATTERN.finditer(text):
            findings.append(
                f"Repeated figure marker in Word paragraph {index}: '{match.group(0)}'. "
                "Check the source reference prefix and the cross-reference/link label; "
                "make the producing source/export render the marker once and regenerate Word. "
                "Do not delete scientific text or unwrap valid links in the DOCX."
            )
    return findings


def text_without_linked_citations(document_xml: bytes) -> str:
    """Exclude valid linked CSL text from the legacy unlinked citation heuristic."""
    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError:
        return ""
    ns = {"w": W_NS}
    bookmarks = {node.get(_w_attr("name")) for node in root.findall(".//w:bookmarkStart", ns)}
    def visit(node):
        anchor = node.get(_w_attr("anchor"), "")
        if node.tag == _w_attr("hyperlink") and anchor.startswith("ref-") and anchor in bookmarks:
            return " "
        return (node.text or "") + "".join(visit(child) for child in node)
    return "\n".join(visit(paragraph) for paragraph in root.findall(".//w:p", ns))


def check_docx(
    path: Path,
    min_chars: int,
    source_tex: str = "",
    expected_title: str = "",
    language: str = "auto",
    *,
    font_policy: str = "preserve",
    citation_style: str = "auto",
    min_figure_dpi: float = 300.0,
) -> WordGuardResult:
    findings: list[str] = []
    text = ""
    paragraph_count = 0
    paragraphs_ordered: list[str] = []
    document_xml: bytes | None = None
    relationships_xml: bytes | None = None
    media_payloads: dict[str, bytes] = {}
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
            if "word/_rels/document.xml.rels" in names:
                relationships_xml = docx.read("word/_rels/document.xml.rels")
            media_payloads = {
                name: docx.read(name)
                for name in names
                if name.startswith("word/media/") and not name.endswith("/")
            }
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
    visible_png, unsupported_media = inspect_word_media(
        document_xml, relationships_xml, media_payloads
    )
    figure_placements, figure_warnings = inspect_word_figure_geometry(
        document_xml, relationships_xml, media_payloads, min_dpi=min_figure_dpi
    )
    if unsupported_media:
        findings.append(
            "Unsupported PDF objects are embedded in word/media and may render as blank "
            "frames in Microsoft Word: " + ", ".join(unsupported_media)
        )
    expected_figure_count = len(
        re.findall(
            r"\\includegraphics(?:\[[^\]]*\])?\s*\{[^{}]+\}",
            source_tex,
            flags=re.IGNORECASE,
        )
    )
    if expected_figure_count and len(visible_png) < expected_figure_count:
        findings.append(
            "Word image-complete gate failed: "
            f"{len(visible_png)}/{expected_figure_count} reader-visible PNG figure media "
            "objects are present. Convert canonical PDF figures only for the Word surface "
            "and preserve source/output SHA-256 provenance."
        )
    if expected_figure_count and not has_visible_figure_reference(text):
        findings.append(
            "Word figure-reference gate failed: the rendered text contains no visible "
            "'Figure <number>' reference even though the source includes a figure. "
            "Preserve the body reference when converting LaTeX/Pandoc output; source "
            "tokens such as \\ref are not required in the DOCX surface."
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

    if document_xml is not None:
        findings.extend(internal_reference_findings(document_xml))
        citation_text = text_without_linked_citations(document_xml)
    else:
        citation_text = text
    author_year_finding = author_year_citation_finding(citation_text, source_tex, citation_style=citation_style)
    if author_year_finding:
        findings.append(author_year_finding)

    fonts = font_profile(path, text, language, font_policy=font_policy)
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

    # Numeric targets do not specify punctuation. The historical square-bracket
    # checker remains available to callers with an explicit punctuation rule.
    findings.extend(check_glued_heading_numbers(paragraphs_ordered))

    return WordGuardResult(
        str(path), not findings, len(text), paragraph_count, findings,
        title_ok=title_ok,
        expected_title=resolved_expected,
        first_paragraph=first_paragraph,
        font_ok=fonts.ok,
        expected_font=fonts.expected,
        actual_fonts=fonts.actual,
        visible_figure_media_count=len(visible_png),
        unsupported_media=unsupported_media,
        figure_placements=figure_placements,
        figure_warnings=figure_warnings,
        figure_legibility_status="unknown" if figure_placements or figure_warnings else "not_assessed",
    )


def to_markdown(result: WordGuardResult) -> str:
    lines = [
        "# Word Guard Report",
        "",
        f"- Path: `{result.path}`",
        f"- Structural status: {'PASS' if result.ok else 'FAIL'} (not a visual or scientific acceptance)",
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
        "## Figure Media Check",
        "",
        f"- Visible PNG figure media: {result.visible_figure_media_count}",
        f"- Unsupported media: {', '.join(result.unsupported_media or []) or '(none)'}",
        f"- Figure label legibility: {result.figure_legibility_status}",
        "- Scope: main-document placements; headers/footers and faithful page rendering are not assessed.",
        "",
    ]
    if result.figure_placements:
        lines.extend([
            "| Placement / paragraph | Media | Word size (cm) | Pixels | Effective DPI (x / y) | Label size |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        def number(value):
            return f"{value:.2f}" if value is not None else "unknown"
        for item in result.figure_placements:
            media = str(item["media_path"] or "unresolved").replace("|", "\\|")
            lines.append(
                f"| {item['placement_index']} / {item['paragraph_index']} | {media} | "
                f"{number(item['width_cm'])} × {number(item['height_cm'])} | "
                f"{item['pixel_width']} × {item['pixel_height']} | "
                f"{number(item['effective_dpi_x'])} / {number(item['effective_dpi_y'])} | unknown; visual review required |"
            )
        lines.append("")
    lines.extend(f"- {warning}" for warning in result.figure_warnings)
    lines.extend(["", "## Findings", ""])
    if result.findings:
        lines.extend(f"- {finding}" for finding in result.findings)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    # Keep machine-readable guard output stable across Windows code pages.
    # The test and host callers consume UTF-8 text; without an explicit
    # reconfiguration, Chinese findings can make subprocess text readers
    # fail before they receive the actual PASS/FAIL report.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
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
        try:
            fix_docx_fonts(docx_path, mode, font_policy=args.font_policy)
        except (RuntimeError, ValueError) as exc:
            print(f"Word font repair FAIL: {exc}")
            return 1

    result = check_docx(
        docx_path, args.min_chars, source_tex, expected_title, args.language,
        font_policy=args.font_policy, citation_style=args.citation_style,
        min_figure_dpi=args.min_figure_dpi,
    )
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
