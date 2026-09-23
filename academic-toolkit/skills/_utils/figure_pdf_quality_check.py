#!/usr/bin/env python3
"""Inspect final vector figures for print size, fonts, clashes and text contrast."""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import active_sources, strip_comments


MIN_FINAL_FONT_PT = 8.0
TEXTWIDTH_IN = 6.5
TEXTHEIGHT_IN = 9.7
HEIGHT_CAP = 0.80
MIN_TEXT_CONTRAST = 4.5
MIN_LARGE_TEXT_CONTRAST = 3.0
PAGE_BOUNDS_TOLERANCE_PT = 1.5
MAX_INTERNAL_BLANK_BAND_RATIO = 0.25
INCLUDE_RE = re.compile(r"\\includegraphics\*?\s*(?:\[([^]]*)\])?\s*\{([^{}]+)\}", re.I)
TEX_DIM_RE = re.compile(r"\*\s*\\(textwidth|textheight)=([0-9.]+)pt", re.I)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _weighted_percentile(items: list[tuple[float, int]], q: float) -> float | None:
    values = sorted((value, max(1, weight)) for value, weight in items if value > 0 and weight > 0)
    if not values:
        return None
    target = max(1, math.ceil(sum(weight for _, weight in values) * q))
    seen = 0
    for value, weight in values:
        seen += weight
        if seen >= target:
            return value
    return values[-1][0]


def _span_box(span: dict, direction=(1.0, 0.0)) -> tuple:
    """Correct inflated Type3 font metrics without changing PDF/global state.

    Some CJK Type3 fonts report a 2.856-em height for a 1-em glyph. Those
    boxes overlap separate lines and even extend outside an intact page.
    Normalize only these anomalous metrics, retaining the advance extent.
    """
    box = tuple(span.get('bbox', (0, 0, 0, 0)))
    try:
        size = float(span['size'])
        a, d = float(span['ascender']), float(span['descender'])
        ox, oy = span['origin']
        ux, uy = direction
        if not (size > 0 and a > 0 > d and a - d > 1.65):
            return box
        vx, vy = -uy, ux
        advance = [(x - ox) * ux + (y - oy) * uy
                   for x in (box[0], box[2]) for y in (box[1], box[3])]
        top, bottom = -size * a / (a - d), -size * d / (a - d)
        points = [(ox + u * ux + v * vx, oy + u * uy + v * vy)
                  for u in (min(advance), max(advance)) for v in (top, bottom)]
        return (min(p[0] for p in points), min(p[1] for p in points),
                max(p[0] for p in points), max(p[1] for p in points))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return box


def _line_box(line: dict) -> tuple:
    boxes = [_span_box(s, line.get('dir', (1, 0))) for s in line.get('spans', [])
             if str(s.get('text', '')).strip()]
    if not boxes:
        return tuple(line.get('bbox', (0, 0, 0, 0)))
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _source_metrics(path: Path) -> tuple[float, float, float | None, list[str]]:
    try:
        import fitz

        doc = fitz.open(str(path))
        if doc.page_count < 1:
            raise RuntimeError("PDF 没有页面")
        widths: list[float] = []
        heights: list[float] = []
        weighted: list[tuple[float, int]] = []
        page_lines: list[tuple[int, list[tuple[tuple[float, float, float, float], str]]]] = []
        try:
            for page_index, page in enumerate(doc):
                widths.append(float(page.rect.width))
                heights.append(float(page.rect.height))
                lines: list[tuple[tuple[float, float, float, float], str]] = []
                for block in page.get_text("dict").get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        text = "".join(str(span.get("text", "")) for span in line.get("spans", [])).strip()
                        bbox = _line_box(line)
                        for span in line.get("spans", []):
                            payload = str(span.get("text", "")).strip()
                            size = float(span.get("size", 0) or 0)
                            if payload and size > 0:
                                weighted.append((size, len(payload)))
                        if len(re.sub(r"\s", "", text)) >= 2 and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                            lines.append((bbox, text[:40]))
                page_lines.append((page_index + 1, lines))
        finally:
            doc.close()
    except Exception as exc:
        raise RuntimeError(f"无法解析图 PDF：{exc}") from exc
    clashes: list[str] = []
    for page_number, lines in page_lines:
        for index, (a, ta) in enumerate(lines):
            for b, tb in lines[index + 1:]:
                iw = min(a[2], b[2]) - max(a[0], b[0])
                ih = min(a[3], b[3]) - max(a[1], b[1])
                if iw <= 0.5 or ih <= 0.5:
                    continue
                area = iw * ih
                smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
                if smaller > 0 and area / smaller >= 0.35:
                    clashes.append(f"第 {page_number} 页：“{ta}” × “{tb}”")
                    if len(clashes) >= 5:
                        break
            if len(clashes) >= 5:
                break
        if len(clashes) >= 5:
            break
    # A multi-page source is unusual for one figure, but inspecting only page 1
    # lets later pages bypass font/overlap checks.  Use the largest page as a
    # conservative placement canvas and aggregate text from every page.
    return max(widths), max(heights), _weighted_percentile(weighted, 0.10), clashes


def _srgb_luminance(rgb: tuple[float, float, float]) -> float:
    def convert(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (convert(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(foreground: tuple[float, float, float], background: tuple[float, float, float]) -> float:
    a, b = sorted((_srgb_luminance(foreground), _srgb_luminance(background)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _int_rgb(value: int) -> tuple[float, float, float]:
    return (((value >> 16) & 255) / 255.0, ((value >> 8) & 255) / 255.0, (value & 255) / 255.0)


def _rect_overlap_ratio(inner, outer) -> float:
    iw = min(inner.x1, outer.x1) - max(inner.x0, outer.x0)
    ih = min(inner.y1, outer.y1) - max(inner.y0, outer.y0)
    if iw <= 0 or ih <= 0:
        return 0.0
    area = max((inner.x1 - inner.x0) * (inner.y1 - inner.y0), 1e-6)
    return (iw * ih) / area


def _source_contrast_issues(path: Path, diagnostics: list[str] | None = None) -> list[str]:
    """Return obvious text/background contrast failures from the rendered PDF.

    Read the composited pixels, not path bounding rectangles: an irregular
    polygon's bounding box is not its fill, and opacity, paint order and raster
    heatmaps all change the real background. Only a dominant local background
    yields a hard verdict; complex backgrounds need visual review.
    """
    try:
        import fitz
        import numpy as np

        document = fitz.open(str(path))
    except Exception as exc:
        raise RuntimeError(f"无法读取图中文字颜色：{exc}") from exc

    issues: list[str] = []
    try:
        for page_number, page in enumerate(document, 1):
            # Bounded memory, once per page, including alpha-composited images.
            scale = min(2.5, math.sqrt(4_000_000 / max(1, page.rect.get_area())))
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
            pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            spans: list[dict] = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans.extend(dict(s, bbox=_span_box(s, line.get('dir', (1, 0))))
                                 for s in line.get("spans", []))

            for span in spans:
                text = str(span.get("text", "")).strip()
                size = float(span.get("size", 0) or 0)
                bbox_values = span.get("bbox")
                if not text or size <= 0 or not bbox_values:
                    continue
                box = fitz.Rect(bbox_values)
                x0, y0 = max(0, math.floor(box.x0 * scale - pix.x)), max(0, math.floor(box.y0 * scale - pix.y))
                x1, y1 = min(pix.width, math.ceil(box.x1 * scale - pix.x)), min(pix.height, math.ceil(box.y1 * scale - pix.y))
                if x1 <= x0 or y1 <= y0:
                    continue  # outside-page text is handled by the boundary check
                sample = pixels[y0:y1, x0:x1].reshape(-1, 3)
                if not len(sample):
                    continue
                quantized = sample.astype(np.int32) // 16
                keys = quantized[:, 0] * 256 + quantized[:, 1] * 16 + quantized[:, 2]
                counts = np.bincount(keys, minlength=4096)
                dominant = int(counts.argmax())
                if counts[dominant] / len(sample) < 0.55:
                    if diagnostics is not None and len(diagnostics) < 8:
                        diagnostics.append(f'第 {page_number} 页“{text[:24]}”背景复杂，对比度需视觉复核')
                    continue
                background = tuple(np.median(sample[keys == dominant], axis=0) / 255.0)
                foreground = _int_rgb(int(span.get("color", 0) or 0))
                ratio = _contrast_ratio(foreground, background)
                # Source-space 14pt may be shrunk to 6pt in the paper; do not
                # relax contrast merely because the source canvas is large.
                required = MIN_TEXT_CONTRAST
                if ratio + 1e-6 < required:
                    clean = re.sub(r"\s+", " ", text)[:32]
                    issues.append(
                        f"第 {page_number} 页“{clean}”文字对比度仅 {ratio:.2f}:1（要求 ≥{required:.1f}:1）"
                    )
                    if len(issues) >= 8:
                        return issues
    finally:
        document.close()
    return issues


def _source_boundary_issues(path: Path, tolerance: float = PAGE_BOUNDS_TOLERANCE_PT) -> list[str]:
    """Return text that is materially clipped by the PDF page boundary.

    A small tolerance is intentional: font bounding boxes can extend roughly
    one point beyond a tight Matplotlib media box even when every glyph remains
    visible.  Larger excursions usually mean a ylabel, panel title or callout
    was exported outside the canvas and will be clipped in the paper.
    """
    try:
        import fitz

        document = fitz.open(str(path))
    except Exception as exc:
        raise RuntimeError(f"无法读取图中文字边界：{exc}") from exc

    issues: list[str] = []
    try:
        for page_number, page in enumerate(document, 1):
            bounds = page.rect
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    text = "".join(str(span.get("text", "")) for span in line.get("spans", [])).strip()
                    bbox = _line_box(line)
                    if not text or not bbox or len(bbox) != 4:
                        continue
                    box = fitz.Rect(bbox)
                    overflow = max(
                        float(bounds.x0 - box.x0), float(bounds.y0 - box.y0),
                        float(box.x1 - bounds.x1), float(box.y1 - bounds.y1),
                    )
                    if overflow > tolerance:
                        clean = re.sub(r"\s+", " ", text)[:36]
                        issues.append(
                            f"第 {page_number} 页“{clean}”超出页面边界 {overflow:.1f} pt"
                        )
                        if len(issues) >= 8:
                            return issues
    finally:
        document.close()
    return issues


def _source_layout_issues(path: Path) -> list[str]:
    """Detect a large blank band *inside* the occupied figure region.

    This is aimed at a specific export failure: one annotation remains near the
    top while the actual chart is squeezed into the bottom half, yielding a
    mostly blank page.  Ordinary outer margins are ignored, as are small gaps
    between a title, legend and axes.  The check is raster based so it evaluates
    the PDF users actually see rather than the pre-layout Matplotlib objects.
    """
    try:
        import fitz
        import numpy as np

        document = fitz.open(str(path))
    except Exception as exc:
        raise RuntimeError(f"无法读取图页面布局：{exc}") from exc

    issues: list[str] = []
    try:
        for page_number, page in enumerate(document, 1):
            pix = page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), colorspace=fitz.csGRAY, alpha=False)
            pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
            # Ignore near-white anti-aliasing.  A row counts as occupied only
            # when more than a couple of isolated pixels carry visible ink.
            occupied = (pixels < 245).mean(axis=1) >= 0.0025
            indices = np.flatnonzero(occupied)
            if indices.size < 12:
                continue
            first, last = int(indices[0]), int(indices[-1])
            if last - first < max(30, int(pix.height * 0.25)):
                continue

            # Close tiny inter-line holes so a line-height gap is never mistaken
            # for a structural blank band.
            segment = occupied[first:last + 1].copy()
            start = None
            for index, value in enumerate(segment):
                if not value and start is None:
                    start = index
                if value and start is not None:
                    if index - start <= 3:
                        segment[start:index] = True
                    start = None

            best_start = best_end = 0
            run_start = None
            for index, value in enumerate(segment):
                if not value and run_start is None:
                    run_start = index
                if value and run_start is not None:
                    if index - run_start > best_end - best_start:
                        best_start, best_end = run_start, index
                    run_start = None
            if run_start is not None and len(segment) - run_start > best_end - best_start:
                best_start, best_end = run_start, len(segment)

            gap = best_end - best_start
            if gap / max(pix.height, 1) <= MAX_INTERNAL_BLANK_BAND_RATIO:
                continue
            # There must be real content on both sides.  This excludes an outer
            # margin that survived because of one anti-aliased speck.
            above = int(segment[:best_start].sum())
            below = int(segment[best_end:].sum())
            if above < 5 or below < 5:
                continue
            issues.append(
                f"第 {page_number} 页内容区内部存在约 {gap / pix.height:.0%} 页高的连续空白带，"
                "疑似游离标注把主体图形挤开"
            )
            if len(issues) >= 4:
                return issues
    finally:
        document.close()
    return issues


def _pdffonts_unembedded(path: Path) -> list[str] | None:
    executable = shutil.which("pdffonts")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    bad: list[str] = []
    for line in result.stdout.splitlines()[2:]:
        match = re.search(r"^(.+?)\s{2,}.+?\s{2,}.+?\s{2,}(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$", line, re.I)
        if match and match.group(2).lower() != "yes":
            bad.append(match.group(1).strip())
    return bad


def _default_width(aspect: float) -> float:
    if aspect <= 0.80:
        return 0.90
    if aspect <= 1.20:
        return 0.80
    if aspect <= 1.60:
        return 0.60
    return 0.46


def _include_key(raw_path: str) -> str:
    parts = [part for part in raw_path.replace("\\", "/").split("/") if part not in ("", ".")]
    lowered = [part.casefold() for part in parts]
    if "figures" in lowered:
        index = len(lowered) - 1 - lowered[::-1].index("figures")
        parts = parts[index + 1:]
    while parts and parts[0] == "..":
        parts.pop(0)
    return "/".join(parts).casefold()


def _include_widths(paper_dir: Path | None) -> dict[str, list[tuple[float, float]]]:
    result: dict[str, list[tuple[float, float]]] = {}
    if paper_dir is None or not paper_dir.is_dir():
        return result
    sources = active_sources(paper_dir)
    area_width, area_height = _paper_text_area_inches(paper_dir)

    def dimension(options: str, key: str) -> float:
        match = re.search(r"(?:^|,)\s*" + key + r"\s*=\s*([^,]+)", options)
        if not match:
            return math.inf  # no cap; TeX keeps the source's native dimension
        value = match.group(1).strip()
        target = area_width if key == "width" else area_height
        relative = re.fullmatch(r"([0-9]*\.?[0-9]+)?\s*\\(textwidth|textheight)", value)
        if relative:
            basis = area_width if relative.group(2) == "textwidth" else area_height
            coefficient = float(relative.group(1) or 1)
            return coefficient if basis == target else coefficient * basis / target
        absolute = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*(in|cm|mm|pt|bp)", value)
        if absolute:
            inches = float(absolute.group(1)) * {"in": 1, "cm": 1/2.54, "mm": 1/25.4, "pt": 1/72.27, "bp": 1/72}[absolute.group(2)]
            return inches / target
        # linewidth in a nested minipage, custom macros, etc. need rendered
        # evidence; guessing the full page width can both hide and invent errors.
        return math.nan
    latex_include = paper_dir.parent / "figures" / "latex_includes.tex"
    if not (paper_dir / "main.tex").is_file() and latex_include.is_file():
        sources.append(latex_include)
    for source in sources:
        if not source.is_file():
            continue
        text = strip_comments(source.read_text(encoding="utf-8", errors="ignore"))
        for options, raw_path in INCLUDE_RE.findall(text):
            if any(character in raw_path for character in ("\\", "#", "$")):
                result.setdefault("__dynamic__", []).append((math.nan, math.nan))
                continue
            if Path(raw_path).suffix.casefold() not in ("", ".pdf"):
                continue
            if not Path(raw_path).suffix:
                raw_path += ".pdf"
            width = dimension(options or "", "width")
            height = dimension(options or "", "height")
            if re.search(r"\b(?:scale|angle|trim|viewport)\s*=", options or ""):
                width = math.nan  # transformations require final-placement evidence
            key = _include_key(raw_path)
            if key:
                result.setdefault(key, []).append((width, height))
    return result


def _paper_text_area_inches(paper_dir: Path | None) -> tuple[float, float]:
    """Read the dimensions TeX actually used, falling back conservatively.

    Geometry writes authoritative ``* \\textwidth=...pt`` and
    ``* \\textheight=...pt`` lines to ``main.log``.  Using the historical
    6.5-inch constant overestimated the final figure size for CUMCM's 25 mm
    margins (about 6.30 inches), allowing sub-8 pt labels to pass.
    """
    width, height = TEXTWIDTH_IN, TEXTHEIGHT_IN
    if paper_dir is None:
        return width, height
    log_path = paper_dir / "main.log"
    if not log_path.is_file():
        return width, height
    try:
        values = {
            name.casefold(): float(raw) / 72.27
            for name, raw in TEX_DIM_RE.findall(log_path.read_text(encoding="utf-8", errors="ignore"))
        }
    except (OSError, ValueError):
        return width, height
    parsed_width = values.get("textwidth")
    parsed_height = values.get("textheight")
    if parsed_width and 2.0 <= parsed_width <= 20.0:
        width = parsed_width
    if parsed_height and 2.0 <= parsed_height <= 30.0:
        height = parsed_height
    return width, height


def _selection_key(value: str | Path) -> str:
    raw = str(value).replace("\\", "/").strip().casefold()
    if raw.startswith("figures/"):
        raw = raw[len("figures/"):]
    return raw


def _load_overrides(fig_dir: Path, override_arg: str | None) -> dict:
    """Load per-figure threshold exemptions (D4: kill 'wolf-crying' FAIL noise).

    Resolves a ``gates_override.json`` from, in order: the explicit ``--override``
    argument, ``<fig_dir>/../gates_override.json``, or ``<fig_dir>/gates_override.json``.
    Expected shape (all keys optional)::

        {
          "figure_pdf_quality": {
            "fig_validation_summary.pdf": {"threshold": 6.5, "rationale": "对齐图1视觉字号，官方无规定"},
            "palette_preview.pdf":     {"threshold": 7.5, "rationale": "不入论文的诊断图板"}
          }
        }

    ``label`` matching is casefolded and compared against the figure path relative
    to ``fig_dir`` (e.g. ``fig_validation_summary.pdf``). A hit lowers the failure
    threshold for that figure only; other checks (font embedding, contrast, overlap,
    boundary, whitespace) are unaffected. Malformed or missing files degrade to no
    overrides and never crash the gate.
    """
    candidates: list[Path] = []
    if override_arg:
        candidates.append(Path(override_arg))
    candidates.append(fig_dir.parent / "gates_override.json")
    candidates.append(fig_dir / "gates_override.json")
    for cand in candidates:
        try:
            if cand.is_file():
                data = json.load(open(cand, encoding="utf-8"))
                block = data.get("figure_pdf_quality") if isinstance(data, dict) else None
                if isinstance(block, dict):
                    return {str(k).casefold(): v for k, v in block.items()}
        except (OSError, ValueError):
            continue
    return {}


def _preview_color_notes(pdf: Path) -> list[str]:
    """Spot obvious PDF/PNG color loss, not an aesthetic or color-count gate.

    A neutral-only figure is legitimate. Different per-format print profiles
    may also be intentional, so this is diagnostic only and never starts a
    model repair loop. Inspect only a same-stem preview and a tiny RGB render.
    """
    png = pdf.with_suffix('.png')
    if not png.is_file():
        return []
    try:
        import fitz
        from PIL import Image

        def fraction(image):
            image = image.convert('RGB')
            image.thumbnail((256, 256))
            get_pixels = getattr(image, 'get_flattened_data', None)
            pixels = list(get_pixels() if get_pixels else image.getdata())
            return sum(max(p) - min(p) >= 20 for p in pixels) / max(1, len(pixels))

        with fitz.open(pdf) as doc:
            if len(doc) != 1:
                return []
            page = doc[0]
            scale = min(1.0, 256 / max(page.rect.width, page.rect.height))
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
            pdf_fraction = fraction(Image.frombytes('RGB', (pix.width, pix.height), pix.samples))
        with Image.open(png) as preview:
            preview.load()
            if preview.mode in ('RGBA', 'LA') or 'transparency' in preview.info:
                rgba = preview.convert('RGBA')
                background = Image.new('RGBA', rgba.size, 'white')
                preview = Image.alpha_composite(background, rgba)
            png_fraction = fraction(preview)
        if max(pdf_fraction, png_fraction) >= .005 and min(pdf_fraction, png_fraction) <= .0001:
            return ['同名 PDF 与 PNG 存在明显彩色/灰度差异；核对导出色彩空间及预览版本，不要把流程图黑白设置应用到数据图']
    except Exception as exc:
        return [f'无法核对同名 PNG 的颜色一致性（{type(exc).__name__}），需检查预览文件']
    return []


def check_directory(
    fig_dir: Path,
    paper_dir: Path | None = None,
    only: list[str] | None = None,
    referenced_only: bool = False,
    overrides: dict | None = None,
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    overrides = overrides or {}
    includes = _include_widths(paper_dir)
    textwidth_in, textheight_in = _paper_text_area_inches(paper_dir)
    paths = sorted(fig_dir.rglob("*.pdf"))
    if referenced_only and paper_dir is not None and (paper_dir / "main.tex").is_file():
        if "__dynamic__" in includes:
            warnings.append("存在动态图片路径，无法精确选择引用图，保留全图检查范围")
        else:
            paths = [p for p in paths if _include_key(p.relative_to(fig_dir).as_posix()) in includes]
    requested = {_selection_key(item) for item in (only or []) if str(item).strip()}
    if requested:
        selected: list[Path] = []
        matched: set[str] = set()
        for path in paths:
            relative = _selection_key(path.relative_to(fig_dir).as_posix())
            candidates = {relative, _selection_key(path.name), _selection_key(path.stem)}
            hits = requested & candidates
            if hits:
                selected.append(path)
                matched.update(hits)
        missing = sorted(requested - matched)
        failures.extend(f"指定图 PDF 未找到：{item}" for item in missing)
        paths = selected
    for path in paths:
        label = path.relative_to(fig_dir).as_posix()
        warnings.extend(f'{label}：{note}' for note in _preview_color_notes(path))
        try:
            width_pt, height_pt, p10, clashes = _source_metrics(path)
        except RuntimeError as exc:
            failures.append(f"{label}：{exc}")
            continue
        fonts = _pdffonts_unembedded(path)
        if fonts is None:
            failures.append(f"{label}：无法运行 pdffonts，不能确认字体嵌入")
        elif fonts:
            failures.append(f"{label}：存在未嵌入字体 {', '.join(fonts[:4])}")
        if clashes:
            failures.append(f"{label}：检测到高重叠文字块 {clashes[0]}")
        try:
            contrast_notes: list[str] = []
            contrast_issues = _source_contrast_issues(path, diagnostics=contrast_notes)
            warnings.extend(f'{label}：{note}' for note in contrast_notes)
        except RuntimeError as exc:
            failures.append(f"{label}：{exc}")
            contrast_issues = []
        if contrast_issues:
            failures.append(f"{label}：检测到低对比度文字；{contrast_issues[0]}")
        try:
            boundary_issues = _source_boundary_issues(path)
        except RuntimeError as exc:
            failures.append(f"{label}：{exc}")
            boundary_issues = []
        if boundary_issues:
            failures.append(f"{label}：检测到文字出界；{boundary_issues[0]}")
        try:
            layout_issues = _source_layout_issues(path)
        except RuntimeError as exc:
            failures.append(f"{label}：{exc}")
            layout_issues = []
        if layout_issues:
            failures.append(f"{label}：检测到异常留白；{layout_issues[0]}")
        aspect = height_pt / width_pt
        relative_key = path.relative_to(fig_dir).as_posix().casefold()
        placements = includes.get(relative_key)
        if placements is None and "/" not in relative_key:
            placements = includes.get(path.name.casefold())
        placements = placements or [(_default_width(aspect), HEIGHT_CAP)]
        display_widths = []
        for width_coef, height_coef in placements:
            if math.isnan(width_coef) or math.isnan(height_coef):
                warnings.append(f"{label}：动态尺寸或变换无法静态确定，印刷字号需在最终 PDF 核实，不能按默认系数判失败或宣称通过")
                continue
            displayed = min(width_coef * textwidth_in, height_coef * textheight_in / aspect)
            display_widths.append(displayed if math.isfinite(displayed) else width_pt / 72.0)
        if p10 is None:
            warnings.append(f"{label}：未提取到矢量文字，字号需由源脚本或视觉检查确认")
            continue
        if not display_widths:
            continue
        final_p10 = p10 * min(display_widths) * 72.0 / width_pt
        if final_p10 + 1e-6 < MIN_FINAL_FONT_PT:
            ov = overrides.get(label.casefold())
            if isinstance(ov, dict):
                thr = ov.get("threshold")
                try:
                    thr = float(thr) if thr is not None else None
                except (TypeError, ValueError):
                    thr = None
                if thr is not None and final_p10 + 1e-6 >= thr:
                    rationale = ov.get("rationale", "已登记豁免")
                    warnings.append(
                        f"{label}：10% 分位文字 {final_p10:.1f} pt 低于默认 {MIN_FINAL_FONT_PT:.0f} pt，"
                        f"已按 gates_override 豁免（阈值 {thr:g} pt；{rationale}）"
                    )
                    continue
            failures.append(
                f"{label}：按论文实际插入尺寸估算，10% 分位文字仅 {final_p10:.1f} pt；"
                f"最低要求 {MIN_FINAL_FONT_PT:.0f} pt，请收窄原生画布、增大字号或重排信息"
            )
    return failures, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fig_dir", nargs="?", default="figures", type=Path)
    parser.add_argument("--paper", type=Path, default=Path("paper"))
    parser.add_argument("--referenced-only", action="store_true", help="最终编译仅检查活跃源码实际引用的图")
    parser.add_argument(
        "--only", action="append", default=[],
        help="只检查指定 PDF（可重复；接受文件名、相对 figures 路径或不带 .pdf 的 stem）",
    )
    parser.add_argument(
        "--override", type=str, default=None,
        help="阈值豁免文件路径（默认自动探测 <fig_dir>/../gates_override.json 或 <fig_dir>/gates_override.json）",
    )
    args = parser.parse_args(argv)
    if not args.fig_dir.is_dir():
        print("  (未找到 figures 目录，跳过图 PDF 终检)")
        return 0
    overrides = _load_overrides(args.fig_dir, args.override)
    failures, warnings = check_directory(args.fig_dir, args.paper, only=args.only, referenced_only=args.referenced_only, overrides=overrides)
    for item in warnings[:12]:
        print("  WARN: " + item)
    if failures:
        print(f"  FAIL: 图 PDF 终检发现 {len(failures)} 项")
        for item in failures[:16]:
            print("    - " + item)
        return 1
    if warnings:
        print(f"  OK: 可确定的图 PDF 检查通过；另有 {len(warnings)} 项需复核，不能视为全部视觉合格")
    else:
        print("  OK: 图 PDF 字体嵌入、最终印刷字号、文字边界、留白和对比度检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
