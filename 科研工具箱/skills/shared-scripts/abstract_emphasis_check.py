#!/usr/bin/env python
"""Validate restrained emphasis in competition abstracts and summary sheets.

The checker intentionally verifies structure, not model semantics.  It accepts
LaTeX ``\\textbf{...}`` and Markdown ``**...**`` and only becomes active when
the located abstract contains per-problem paragraphs.  This keeps the shared
``writing_check.sh`` safe for ordinary academic papers that do not use the
competition-paper abstract pattern.
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import active_sources
from typing import NamedTuple


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROBLEM_RE = re.compile(
    r"(?:针对\s*)?问题\s*[一二三四五六七八九十百0-9]+"
    r"|(?:for\s+)?(?:sub-?)?problem\s*[A-Z0-9]+",
    re.IGNORECASE,
)
NAV_ONLY_RE = re.compile(
    r"^(?:针对\s*)?(?:问题\s*[一二三四五六七八九十百0-9]+"
    r"|(?:for\s+)?(?:sub-?)?problem\s*[A-Z0-9]+)[：:]?$",
    re.IGNORECASE,
)
KEYWORD_RE = re.compile(
    r"^(?:\\?keywords?|key\s+words?|关键词|关键字)\s*[：:]",
    re.IGNORECASE,
)
CHINESE_TOKEN_RE = re.compile(
    r"[\u3400-\u9fff]|[，。；：、！？（）“”《》—…]|"
    r"[A-Za-z]+(?:[-–][A-Za-z0-9]+)*|\d+(?:\.\d+)?%?"
)
STANDARD_FULLNESS_TARGET = (680, 760)
ENGLISH_FULLNESS_TARGET = (330, 380)
STANDARD_MIN_RENDERED_FILL = 0.80
STATS_MIN_RENDERED_FILL = 0.72
ENGLISH_MIN_RENDERED_FILL = 0.80
ABSTRACT_FILE_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Za-z0-9_.-]+[/\\])*[A-Za-z0-9_.-]+\."
    r"(?:xlsx?|csv|json|py|m|md|tex|pdf|docx?|png|jpe?g|drawio)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)


class PdfWord(NamedTuple):
    text: str
    y0: float
    y1: float


class PdfPageLayout(NamedTuple):
    height: float
    words: tuple[PdfWord, ...]


def _balanced_latex_spans(text: str) -> list[str]:
    marker = r"\textbf{"
    spans: list[str] = []
    start = 0
    while True:
        pos = text.find(marker, start)
        if pos < 0:
            return spans
        i = pos + len(marker)
        depth = 1
        while i < len(text) and depth:
            if text[i] == "{" and (i == 0 or text[i - 1] != "\\"):
                depth += 1
            elif text[i] == "}" and (i == 0 or text[i - 1] != "\\"):
                depth -= 1
            i += 1
        if depth == 0:
            spans.append(text[pos + len(marker) : i - 1].strip())
            start = i
        else:
            # Malformed LaTeX will be caught by compilation; avoid looping here.
            return spans


def _markdown_spans(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"(?<!\*)\*\*([^*\n]+?)\*\*(?!\*)", text)]


def emphasis_spans(text: str, kind: str) -> list[str]:
    return _balanced_latex_spans(text) if kind == "latex" else _markdown_spans(text)


def _extract_latex_abstract(text: str) -> str | None:
    begin = r"\begin{abstract}"
    end = r"\end{abstract}"
    i0 = text.find(begin)
    i1 = text.find(end, i0 + len(begin)) if i0 >= 0 else -1
    if 0 <= i0 < i1:
        return text[i0 + len(begin) : i1]
    return None


def _extract_markdown_abstract(text: str) -> str | None:
    heading = re.search(r"(?mi)^#{1,3}\s*(?:摘要|abstract|summary(?:\s+sheet)?)\s*$", text)
    if not heading:
        return None
    tail = text[heading.end() :]
    next_heading = re.search(r"(?m)^#{1,3}\s+", tail)
    return tail[: next_heading.start()] if next_heading else tail


def _expand_latex_inputs(text: str, paper_dir: Path, depth: int = 0) -> str:
    if depth >= 3:
        return text
    root = paper_dir.resolve()

    def replace(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        candidate = (paper_dir / raw).with_suffix(".tex") if not Path(raw).suffix else paper_dir / raw
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root)
            payload = resolved.read_text(encoding="utf-8", errors="ignore")
        except (OSError, ValueError):
            return match.group(0)
        return _expand_latex_inputs(payload, paper_dir, depth + 1)

    return re.sub(r"\\input\{([^{}]+)\}", replace, text)


def locate_abstract(paper_dir: Path) -> tuple[str, str, Path] | None:
    main_tex = paper_dir / "main.tex"
    active = active_sources(paper_dir)
    if main_tex.is_file():
        text = main_tex.read_text(encoding="utf-8", errors="ignore")
        abstract = _extract_latex_abstract(text)
        if abstract is not None:
            return _expand_latex_inputs(abstract, paper_dir), "latex", main_tex

        for path in active:
            if path == main_tex.resolve():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            abstract = _extract_latex_abstract(text)
            if abstract is not None:
                return _expand_latex_inputs(abstract, paper_dir), "latex", path

    for pattern in ("sections/0_*.tex", "sections/*abstract*.tex", "sections/*summary*.tex"):
        for path in sorted(paper_dir.glob(pattern)):
            if main_tex.is_file() and path.resolve() not in active:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            abstract = _extract_latex_abstract(text) or text
            if PROBLEM_RE.search(abstract):
                return abstract, "latex", path

    main_md = paper_dir / "main.md"
    if main_md.is_file():
        text = main_md.read_text(encoding="utf-8", errors="ignore")
        abstract = _extract_markdown_abstract(text)
        if abstract is not None:
            return abstract, "markdown", main_md
    return None


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\r?\n\s*\r?\n", text) if p.strip()]


def _without_keywords(text: str) -> str:
    return re.split(
        r"(?im)^\s*(?:\\keywords\b|\\noindent\s*\\textbf\{\s*关键词|"
        r"\*\*关键词\*\*\s*[：:]|关键词\s*[：:]|"
        r"\*{0,2}(?:keywords?|key\s+words)\*{0,2}\s*[：:])",
        text,
        maxsplit=1,
    )[0]


def visible_units(text: str) -> int:
    """Approximate Word-style Chinese abstract length without counting TeX syntax."""
    body = _without_keywords(text)
    body = re.sub(r"(?m)(?<!\\)%.*$", "", body)
    body = re.sub(r"\\(?:begin|end)\{[^{}]+\}", " ", body)
    body = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", body)
    body = body.replace("**", " ").replace("{", " ").replace("}", " ")
    return len(CHINESE_TOKEN_RE.findall(body))


def _source_profile(source: str) -> str:
    """Return the competition template profile, never the paper's method type.

    A CUMCM paper may legitimately contain phrases such as ``统计建模`` or
    ``statistical model``.  Treating those method descriptions as the separate
    National Statistical Modeling Competition silently weakened CUMCM's
    600--800-character contract.  Only an explicit template marker or the full
    competition name selects the statistics profile.
    """
    if re.search(
        r"MODEX_ABSTRACT_PROFILE\s*=\s*stats|"
        r"全国大学生统计建模大赛|"
        r"national\s+(?:college|university)\s+student\s+statistical\s+modeling\s+competition",
        source,
        re.IGNORECASE,
    ):
        return "stats"
    return "standard"


def validate_length(text: str, source: str = "") -> list[str]:
    """Validate the shared competition-summary length contract."""
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
    if cjk_count >= 40:
        count = visible_units(text)
        profile = _source_profile(source)
        lower, upper = {
            "standard": (600, 800),
            "stats": (500, 700),
        }[profile]
        if not lower <= count <= upper:
            return [
                f"中文摘要约 {count} 字，不符合 {profile} 模式 {lower}--{upper} 字要求"
            ]
        return []

    words = re.findall(r"\b[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*\b", _without_keywords(text))
    if not 300 <= len(words) <= 400:
        return [f"English summary has about {len(words)} words; expected 300--400"]
    return []


def validate_fullness_target(text: str, source: str = "") -> list[str]:
    """Require a source-only draft to target a visually full summary page.

    The official compatibility range remains 600--800 Chinese units.  This
    narrower target is used before Word pagination is available.  A compiled
    PDF is instead judged by real geometry so a template that genuinely fills
    a page with fewer characters is not rejected merely by character count.
    """
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
    if cjk_count >= 40:
        if _source_profile(source) != "standard":
            return []
        count = visible_units(text)
        lower, upper = STANDARD_FULLNESS_TARGET
        if not lower <= count <= upper:
            return [
                f"中文摘要约 {count} 字；Word/未渲染源稿应优先控制在 {lower}--{upper} 字，"
                "以兼顾接近满页和绝不跨页"
            ]
        return []

    words = re.findall(r"\b[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*\b", _without_keywords(text))
    lower, upper = ENGLISH_FULLNESS_TARGET
    if not lower <= len(words) <= upper:
        return [
            f"English source-only summary has about {len(words)} words; "
            f"aim for {lower}--{upper} before rendering"
        ]
    return []


def validate_page_stable_content(text: str, kind: str) -> list[str]:
    """Keep summary pagination stable across LaTeX and Word renderers."""
    if kind == "latex":
        block_tokens = (
            r"\begin{equation", r"\begin{align", r"\begin{figure",
            r"\begin{table", r"\[", r"\]",
        )
        has_block = any(token in text for token in block_tokens) or "$$" in text
    else:
        has_block = bool(
            "$$" in text
            or re.search(r"(?m)^\s*!\[[^]]*\]\([^)]*\)\s*$", text)
            or re.search(r"(?m)^\s*\|.+\|\s*$", text)
            or re.search(r"(?m)^\s*```", text)
        )
    if has_block:
        return ["摘要不得包含独立公式、图、表或代码块；请改成行内表达并把展开内容放回正文"]
    return []


def validate_problem_openers(text: str) -> list[str]:
    """Keep per-problem summary paragraphs immediately scannable."""
    errors: list[str] = []
    paragraphs = [
        paragraph for paragraph in _paragraphs(text)
        if not KEYWORD_RE.search(re.sub(r"[\\*{}]", "", paragraph).strip())
    ]
    for index, paragraph in enumerate(paragraphs, 1):
        matches = list(PROBLEM_RE.finditer(paragraph))
        if not matches:
            continue
        cleaned = re.sub(r"^(?:\\noindent|\\par)\s*", "", paragraph.lstrip())
        is_chinese_problem = bool(re.search(
            r"(?:针对\s*)?问题\s*[一二三四五六七八九十百0-9]+", paragraph
        ))
        if is_chinese_problem:
            opener = re.compile(
                r"^针对\s*问题\s*[一二三四五六七八九十百0-9]+(?=[，,：:\s])"
            )
            expected = "针对问题一/二/三……"
        else:
            opener = re.compile(
                r"^For\s+(?:Sub-?)?Problem\s*[A-Z0-9]+(?=[,.:：\s])",
                re.IGNORECASE,
            )
            expected = "For Problem 1/2/3 ..."
        if not opener.search(cleaned):
            errors.append(f"段 {index} 的子问题叙述必须以“{expected}”开头")
        if len(matches) > 1:
            errors.append(f"段 {index} 同时叙述了 {len(matches)} 个子问题；每个问题必须独占一段")
    return errors


def validate_problem_balance(text: str) -> list[str]:
    """Keep background short and make per-problem method/result paragraphs substantive."""
    body = _without_keywords(text)
    # This budget is the Chinese competition-paper contract.  English Summary
    # Sheets use word counts and a different paragraph budget.
    if len(re.findall(r"[\u3400-\u9fff]", body)) < 40:
        return []
    paragraphs = _paragraphs(body)
    problem_indexes = [index for index, paragraph in enumerate(paragraphs) if PROBLEM_RE.search(paragraph)]
    if not problem_indexes:
        return []
    errors: list[str] = []
    total = visible_units(body)
    first, last = problem_indexes[0], problem_indexes[-1]
    opening = sum(visible_units(paragraph) for paragraph in paragraphs[:first])
    conclusion = sum(visible_units(paragraph) for paragraph in paragraphs[last + 1:])
    problem_lengths = [visible_units(paragraphs[index]) for index in problem_indexes]
    problem_total = sum(problem_lengths)
    if total and opening / total > 0.15 + 1e-9:
        errors.append(
            f"摘要开头约 {opening} 字，占正文 {opening / total:.1%}；不得超过 15%，应把篇幅让给各问题的方法与结果"
        )
    if opening > 90:
        errors.append(f"摘要开头约 {opening} 字，明显长于 45--75 字常用范围；删去宏观背景和重复结论")
    if total and problem_total / total < 0.75 - 1e-9:
        errors.append(
            f"各问题段合计只占摘要正文 {problem_total / total:.1%}；应至少占 75%"
        )
    if conclusion > 60:
        errors.append(f"摘要结尾约 {conclusion} 字；没有新的跨问题结论时应删除，通常不超过 40 字")
    n = len(problem_lengths)
    soft_floor = {2: 180, 3: 130, 4: 100, 5: 82}.get(n, 70)
    method_re = re.compile(r"建立|构建|采用|利用|基于|通过|定义|推导|求解|拟合|优化|判定|搜索|递推")
    result_re = re.compile(
        r"\d+(?:\.\d+)?%?|得到|确定|求得|表明|发现|说明|证明|不存在|无法|可行|相切|"
        r"单调|不变|最短|最长|最大|最小|终止时刻"
    )
    for ordinal, (index, length) in enumerate(zip(problem_indexes, problem_lengths), 1):
        paragraph = paragraphs[index]
        if length < soft_floor:
            errors.append(
                f"第 {ordinal} 个问题段约 {length} 字，低于当前 {n} 问摘要的实质内容下限 {soft_floor} 字；"
                "补足题意到数学对象、关键关系、求解路线和结果"
            )
        if not method_re.search(paragraph):
            errors.append(f"第 {ordinal} 个问题段未说明具体建模或求解动作")
        if not result_re.search(paragraph):
            errors.append(f"第 {ordinal} 个问题段未给出量化结果或明确的定性结论")
    filenames = ABSTRACT_FILE_RE.findall(body)
    if filenames:
        errors.append("摘要出现交付文件名；只写模型、方法和结果，不罗列工作簿、脚本或内部产物")
    return errors


def _page_texts(pdf_path: Path) -> list[str]:
    pypdf_pages: list[str] = []
    try:
        from pypdf import PdfReader

        pypdf_pages = [page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages]
        # Some CJK PDFs return replacement/mojibake text without raising.  Do
        # not accept that as a successful extraction for the physical-page
        # gate; try Poppler/MiKTeX before falling back to the unusable text.
        if any(re.search(r"[\u3400-\u9fff]", page) for page in pypdf_pages):
            return pypdf_pages
    except Exception as pypdf_error:  # pragma: no cover - depends on host packages
        pypdf_pages = []
        pypdf_failure = pypdf_error
    else:
        pypdf_failure = RuntimeError("pypdf did not expose usable CJK text")

    candidates: list[str] = []
    xelatex = shutil.which("xelatex")
    if xelatex:
        sibling = Path(xelatex).with_name("pdftotext.exe")
        if sibling.is_file():
            candidates.append(str(sibling))
    executable = shutil.which("pdftotext")
    if executable and executable not in candidates:
        candidates.append(executable)
    for executable in candidates:
        result = subprocess.run(
            [executable, "-layout", str(pdf_path), "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode == 0:
            pages = result.stdout.decode("utf-8", errors="replace").split("\f")
            while pages and not pages[-1].strip():
                pages.pop()
            # Git for Windows also bundles a pdftotext binary, but on some
            # CJK PDFs it returns page separators with no Chinese text.
            if pages and any(re.search(r"[\u3400-\u9fff]", page) for page in pages):
                return pages
    if pypdf_pages:
        return pypdf_pages
    raise RuntimeError(
        "无法读取已编译 PDF（需要 pypdf 或可正确提取中文的 pdftotext）: "
        f"{pypdf_failure}"
    ) from pypdf_failure


def _pdf_layout_with_fitz(pdf_path: Path) -> list[PdfPageLayout] | None:
    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        pages: list[PdfPageLayout] = []
        try:
            for page in doc:
                words = tuple(
                    PdfWord(str(item[4]), float(item[1]), float(item[3]))
                    for item in page.get_text("words")
                    if len(item) >= 5 and str(item[4]).strip()
                )
                pages.append(PdfPageLayout(float(page.rect.height), words))
        finally:
            doc.close()
        return pages or None
    except Exception:
        return None


def _pdftotext_candidates() -> list[str]:
    candidates: list[str] = []
    xelatex = shutil.which("xelatex")
    if xelatex:
        sibling = Path(xelatex).with_name("pdftotext.exe")
        if sibling.is_file():
            candidates.append(str(sibling))
    executable = shutil.which("pdftotext")
    if executable and executable not in candidates:
        candidates.append(executable)
    return candidates


def _pdf_layout_with_pdftotext(pdf_path: Path) -> list[PdfPageLayout] | None:
    for executable in _pdftotext_candidates():
        result = subprocess.run(
            [executable, "-bbox-layout", str(pdf_path), "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            continue
        raw = result.stdout.decode("utf-8", errors="replace")
        # MiKTeX pdftotext may emit XML 1.0-invalid control chars from math glyphs.
        raw = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", raw)
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            continue
        pages: list[PdfPageLayout] = []
        for page in root.iter():
            if not page.tag.endswith("page"):
                continue
            try:
                height = float(page.attrib["height"])
            except (KeyError, ValueError):
                continue
            words: list[PdfWord] = []
            for word in page.iter():
                if not word.tag.endswith("word"):
                    continue
                try:
                    words.append(PdfWord(
                        html.unescape("".join(word.itertext())).strip(),
                        float(word.attrib["yMin"]),
                        float(word.attrib["yMax"]),
                    ))
                except (KeyError, ValueError):
                    continue
            pages.append(PdfPageLayout(height, tuple(words)))
        if pages:
            return pages
    return None


def _pdf_layout(pdf_path: Path) -> list[PdfPageLayout]:
    pages = _pdf_layout_with_fitz(pdf_path) or _pdf_layout_with_pdftotext(pdf_path)
    if not pages:
        raise RuntimeError("无法读取 PDF 文字坐标，不能验证摘要版面丰满度")
    return pages


def _normalised_chars(text: str) -> str:
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z0-9]+", text)).lower()


def _anchor(text: str, *, tail: bool, size: int = 16) -> str:
    chars = _normalised_chars(text)
    if len(chars) <= size:
        return chars
    return chars[-size:] if tail else chars[:size]


def _word_span_for_anchor(words: tuple[PdfWord, ...], anchor: str) -> tuple[float, float] | None:
    if not anchor:
        return None
    joined: list[str] = []
    owners: list[int] = []
    for index, word in enumerate(words):
        normalised = _normalised_chars(word.text)
        joined.append(normalised)
        owners.extend([index] * len(normalised))
    haystack = "".join(joined)
    pos = haystack.find(anchor)
    if pos < 0 or not owners:
        return None
    first = owners[pos]
    last = owners[min(pos + len(anchor) - 1, len(owners) - 1)]
    selected = words[first:last + 1]
    return min(word.y0 for word in selected), max(word.y1 for word in selected)


def _keyword_line_bottom(words: tuple[PdfWord, ...]) -> float | None:
    labels = ("关键词", "关键字", "keyword", "keywords")
    for index, word in enumerate(words):
        token = _normalised_chars(word.text)
        if not any(label in token for label in labels):
            continue
        baseline = word.y0
        line_words = [candidate for candidate in words if abs(candidate.y0 - baseline) <= 3.0]
        return max((candidate.y1 for candidate in line_words), default=word.y1)
    return None


def validate_compiled_fullness(
    text: str,
    kind: str,
    paper_dir: Path,
    pdf_path: Path | None = None,
) -> list[str]:
    """Check real rendered vertical use, without changing fonts or margins."""
    target = Path(pdf_path) if pdf_path is not None else paper_dir / "main.pdf"
    if not target.is_file():
        return [f"未找到 {target.name}，无法验证摘要版面丰满度"]
    body = _without_keywords(text)
    start_anchors = _anchor_candidates(body, tail=False)
    end_anchors = _anchor_candidates(body, tail=True)
    if not start_anchors or not end_anchors:
        return ["摘要正文过短，无法定位首尾并测量版面"]
    try:
        layouts = _pdf_layout(target)
    except RuntimeError as exc:
        return [str(exc)]

    start_match: tuple[int, tuple[float, float]] | None = None
    end_match: tuple[int, tuple[float, float]] | None = None
    for index, page in enumerate(layouts):
        if start_match is None:
            for anchor in start_anchors:
                span = _word_span_for_anchor(page.words, anchor)
                if span is not None:
                    start_match = (index, span)
                    break
        if start_match is not None and end_match is None:
            for anchor in end_anchors:
                span = _word_span_for_anchor(page.words, anchor)
                if span is not None and (index > start_match[0] or span[1] >= start_match[1][0]):
                    end_match = (index, span)
                    break
        if start_match is not None and end_match is not None:
            break  # later repeated conclusions are outside the abstract
    if start_match is None or end_match is None:
        return ["无法从 PDF 文字坐标定位摘要首尾，不能确认版面丰满度"]
    if start_match[0] != end_match[0]:
        return []  # The physical-page validator reports the clearer spill error.

    page_index = start_match[0]
    page = layouts[page_index]
    keyword_bottom = _keyword_line_bottom(page.words)
    if keyword_bottom is None:
        # A missing keyword line is a real submission defect, and also makes
        # "abstract page" fullness ambiguous.
        other_pages = [
            i for i, candidate in enumerate(layouts)
            if _keyword_line_bottom(candidate.words) is not None
        ]
        if other_pages:
            return [
                f"摘要正文在第 {page_index + 1} 页，但关键词位于第 {other_pages[0] + 1} 页；"
                "摘要与关键词必须同页"
            ]
        return ["未在最终 PDF 中找到关键词行，不能确认摘要单页排版"]

    first_y = start_match[1][0]
    last_y = max(end_match[1][1], keyword_bottom)
    safe_bottom = page.height * 0.90
    usable = safe_bottom - first_y
    if usable <= 0:
        return ["摘要正文起始位置异常，无法测量版面丰满度"]
    fill = max(0.0, min(1.0, (last_y - first_y) / usable))
    cjk = len(re.findall(r"[\u3400-\u9fff]", text)) >= 40
    if cjk:
        source_files = [paper_dir / "main.tex", paper_dir / "main.md"]
        source = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in source_files if path.is_file()
        )
        minimum = (
            STATS_MIN_RENDERED_FILL
            if _source_profile(source) == "stats"
            else STANDARD_MIN_RENDERED_FILL
        )
    else:
        minimum = ENGLISH_MIN_RENDERED_FILL
    if fill + 1e-9 < minimum:
        return [
            f"摘要正文至关键词仅使用约 {fill:.1%} 的安全可排版高度，目标至少 {minimum:.0%}；"
            "请补充具名方法的适用理由、关键条件、带单位结果或误差/对比证据，"
            "不得缩小字号、行距或页边距"
        ]
    return []


def _cjk_anchor(text: str, *, tail: bool) -> str:
    chars = re.findall(r"[\u3400-\u9fff]", _without_keywords(text))
    chosen = chars[-12:] if tail else chars[:12]
    return "".join(chosen)


def _anchor_candidates(text: str, *, tail: bool) -> tuple[str, ...]:
    """Return stable anchors for both normal and fragmented CJK extraction."""
    candidates = [_anchor(text, tail=tail)]
    if len(re.findall(r"[\u3400-\u9fff]", text)) >= 12:
        candidates.append(_cjk_anchor(text, tail=tail))
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))


def validate_compiled_page(
    text: str,
    kind: str,
    paper_dir: Path,
    pdf_path: Path | None = None,
) -> list[str]:
    """Verify that an abstract begins and ends on one rendered PDF page.

    The 600--800 character gate prevents an under-filled summary.  This physical-page
    check catches the opposite failure: the abstract silently spilling to page two.
    """
    target = Path(pdf_path) if pdf_path is not None else paper_dir / "main.pdf"
    if not target.is_file():
        return ["未找到 main.pdf，无法验证摘要是否恰好占一页"]
    source_files = ([paper_dir / "main.md"] if kind in ("md", "markdown") else active_sources(paper_dir))
    newest_source = max(
        (path.stat().st_mtime_ns for path in source_files if path.is_file()),
        default=0,
    )
    if newest_source and target.stat().st_mtime_ns < newest_source:
        return ["main.pdf 早于论文源文件，必须重新编译后再验证摘要物理页"]
    try:
        pages = [_normalised_chars(page) for page in _page_texts(target)]
    except RuntimeError as exc:
        return [str(exc)]
    body = _without_keywords(text)
    start_anchors = _anchor_candidates(body, tail=False)
    end_anchors = _anchor_candidates(body, tail=True)
    start_pages = [
        i for i, page in enumerate(pages)
        if any(anchor in page for anchor in start_anchors)
    ]
    if not start_pages:
        return ["无法在 PDF 中定位摘要首尾文本，不能确认摘要单页排版"]
    start = start_pages[0]
    start_pos = min(pages[start].find(a) for a in start_anchors if a in pages[start])
    end = None
    for index in range(start, len(pages)):
        page = pages[index]
        offset = start_pos if index == start else 0
        keyword = re.search(r"关键词|keywords", page[offset:], re.I)
        boundary = offset + keyword.start() if keyword else len(page)
        if any(page.find(a, offset, boundary) >= 0 for a in end_anchors):
            end = index
            break
        if keyword:
            break  # never match the abstract tail in the body after keywords
    if end is None:
        return ["无法在 PDF 中定位摘要首尾文本，不能确认摘要单页排版"]
    if start != end:
        return [
            f"摘要从 PDF 第 {start + 1} 页延续到第 {end + 1} 页，"
            "中文竞赛摘要必须收在同一页"
        ]
    return []


def validate(text: str, kind: str) -> list[str]:
    paragraphs = _paragraphs(text)
    problem_paragraphs = [p for p in paragraphs if PROBLEM_RE.search(p)]
    if not problem_paragraphs:
        spans = [
            span
            for paragraph in paragraphs
            if not KEYWORD_RE.search(re.sub(r"[\\*{}]", "", paragraph).strip())
            for span in emphasis_spans(paragraph, kind)
        ]
        errors: list[str] = []
        if not 2 <= len(spans) <= 8:
            errors.append(f"非分问题摘要应有 2--8 处方法/结果加粗，实际 {len(spans)} 处")
        for span in spans:
            if len(re.sub(r"\\[A-Za-z]+|[{}$]", "", span).strip()) > 48:
                errors.append("非分问题摘要存在疑似整句加粗（超过 48 字符）")
        return errors

    errors: list[str] = validate_problem_openers(text)
    # Short snippets are used by the editor and by focused unit checks before
    # the abstract has reached submission length.  Length validation already
    # rejects them at the quality gate; applying whole-page percentage budgets
    # here would turn a useful structural diagnostic into several misleading
    # secondary errors.  The complete abstract is always long enough to enter
    # the balance check during writing/compile validation.
    if visible_units(text) >= 500:
        errors.extend(validate_problem_balance(text))
    all_spans: list[str] = []
    for index, paragraph in enumerate(paragraphs, 1):
        if KEYWORD_RE.search(re.sub(r"[\\*{}]", "", paragraph).strip()):
            continue
        spans = emphasis_spans(paragraph, kind)
        all_spans.extend(spans)
        if not PROBLEM_RE.search(paragraph):
            if len(spans) > 1:
                errors.append(f"段 {index} 不是子问题段，却有 {len(spans)} 处加粗（开头/结尾最多 1 处）")
            continue
        if not 1 <= len(spans) <= 3:
            errors.append(f"段 {index} 是子问题段，应有 1--3 处加粗，实际 {len(spans)} 处")
            continue
        navigation_spans = [
            s for s in spans
            if NAV_ONLY_RE.fullmatch(re.sub(r"[\\{}]", "", s).strip())
        ]
        content_spans = [s for s in spans if s not in navigation_spans]
        if navigation_spans:
            errors.append(f"段 {index} 不应加粗“问题N/Problem N”导航词")
        if not content_spans:
            errors.append(f"段 {index} 只加粗了“问题N”导航词，未突出模型/方法或关键结果")
        for span in spans:
            if len(re.sub(r"\\[A-Za-z]+|[{}$]", "", span).strip()) > 48:
                errors.append(f"段 {index} 存在疑似整句加粗（超过 48 字符）")

    if not all_spans:
        errors.append("摘要没有任何内容加粗")
    elif len(all_spans) > 12:
        errors.append(f"摘要共有 {len(all_spans)} 处加粗，超过 12 处上限")
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_dir", nargs="?", default="paper")
    parser.add_argument("--compiled", action="store_true")
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--require-fullness-target", action="store_true")
    args = parser.parse_args(argv[1:])
    paper_dir = Path(args.paper_dir)
    located = locate_abstract(paper_dir)
    if located is None:
        if args.compiled:
            print("  FAIL: 未定位到摘要；最终编译产物不得跳过摘要质量门")
            return 1
        print("  (未定位到摘要，草稿阶段跳过摘要重点检查)")
        return 0
    text, kind, path = located
    source = path.read_text(encoding="utf-8", errors="ignore")
    errors = validate(text, kind) + validate_length(text, source)
    errors += validate_page_stable_content(text, kind)
    if args.require_fullness_target:
        errors += validate_fullness_target(text, source)
    if args.compiled:
        errors += validate_compiled_page(text, kind, paper_dir, args.pdf)
        errors += validate_compiled_fullness(text, kind, paper_dir, args.pdf)
    if errors:
        print(f"  FAIL: 摘要重点层级不合规 ({path})")
        for error in errors:
            print(f"    - {error}")
        return 1
    count = len(emphasis_spans(text, kind))
    detail = "子问题段各 1--3 处" if PROBLEM_RE.search(text) else "通用方法/结果重点 2--8 处"
    print(f"  OK: 摘要长度与重点层级合规（约 {visible_units(text)} 字，{count} 处加粗，{detail}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
