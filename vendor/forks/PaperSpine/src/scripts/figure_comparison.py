#!/usr/bin/env python3
"""Place existing figure views in a local PDF; no drawing, analysis or approval.

Uses PyMuPDF, already used by PaperSpine's PDF tools. PDF/SVG content is placed
as vector PDF content. Raster inputs retain their source pixels, not new detail.
Page numbers are one based; label each view's real role and published locator.
Optional clips use (x0, y0, x1, y1) points (1/72 inch), with origin at the
displayed page's top left after PDF rotation / CropBox, x right, y down.
Clips and exported views are keyed by one-based --view order, not page number.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from contextlib import ExitStack
from pathlib import Path


def _wrap(text: str, width: float, font, size: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for word in paragraph.split():
            proposed = f"{current} {word}".strip()
            if font.text_length(proposed, fontsize=size) <= width:
                current = proposed
                continue
            if current:
                lines.append(current)
                current = ""
            # Long unbroken file names must not escape their column.
            for char in word:
                if current and font.text_length(current + char, fontsize=size) > width:
                    lines.append(current)
                    current = ""
                current += char
        lines.append(current)
    return lines


def _finite_number(value) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _view_options(options, count: int, name: str) -> dict:
    options = dict(options or {})
    if any(type(i) is not int or not 1 <= i <= count for i in options):
        raise ValueError(f"{name} indices must be integers from 1 to {count}")
    return options


def _output_path(value: Path) -> Path:
    path = Path(value)
    if path.is_symlink() or path.exists():
        raise FileExistsError(f"Choose a new output path: {path}")
    path = path.resolve()
    if path.suffix.lower() != ".pdf":
        raise ValueError("Comparison and view outputs must be PDFs")
    if any(p.exists() and not p.is_dir() for p in path.parents):
        raise ValueError(f"Output parent is not a directory: {path}")
    return path


def _write_new(outputs: dict[Path, bytes]) -> None:
    # All documents are already built. Reserve every destination exclusively
    # before writing bytes; on an I/O race/failure remove only files we created.
    created = []
    try:
        with ExitStack() as stack:
            handles = []
            for path, content in outputs.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                handle = stack.enter_context(path.open("xb"))
                created.append((path, os.fstat(handle.fileno())))
                handles.append((handle, content))
            for handle, content in handles:
                handle.write(content)
    except BaseException:
        for path, identity in reversed(created):
            try:
                current = path.lstat()
                if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                    path.unlink()
            except OSError:
                pass
        raise


def build_comparison(output: Path, views: list[tuple[str, Path, int]], *,
                     view_width_mm: float = 160,
                     clips: dict[int, tuple[float, float, float, float]] | None = None,
                     export_views: dict[int, Path] | None = None) -> dict:
    """Place views; optional clips / export_views use one-based view indices.

    Clipping is a display operation, not redaction. Exported PDFs reuse the
    exact labelled view placed in the comparison, including its source locator.
    All validation and PDF construction precede any filesystem output.
    """
    import fitz

    if len(views) < 2:
        raise ValueError("Supply at least two explicitly labelled views")
    if not _finite_number(view_width_mm) or view_width_mm <= 0:
        raise ValueError("view_width_mm must be finite and positive")
    clips = _view_options(clips, len(views), "Clip")
    export_views = _view_options(export_views, len(views), "Export")
    output = _output_path(output)
    export_views = {i: _output_path(path) for i, path in export_views.items()}
    destinations = [output, *export_views.values()]
    if len(set(destinations)) != len(destinations):
        raise ValueError("Duplicate output paths")
    if any(a in b.parents for a in destinations for b in destinations):
        raise ValueError("An output cannot be another output's parent")
    width = view_width_mm * 72 / 25.4
    if not math.isfinite(width) or not 0 < width < fitz.FZ_MAX_INF_RECT:
        raise ValueError("View width exceeds the PDF coordinate range")
    margin, gap, font_size, line_height = 18.0, 18.0, 11.0, 16.0
    # A built-in Unicode font keeps Chinese source labels searchable too.
    font = fitz.Font("cjk")
    with ExitStack() as stack:
        loaded = []
        for index, (label, source, page_number) in enumerate(views, 1):
            source = Path(source).resolve(strict=True)
            if not label.strip() or not source.is_file():
                raise ValueError("Each view needs a label and an existing file")
            if source in destinations:
                raise ValueError("Output cannot replace an input")
            if type(page_number) is not int or page_number < 1:
                raise ValueError("View pages are one based positive integers")
            document = stack.enter_context(fitz.open(stream=source.read_bytes(),
                                                      filetype=source.suffix[1:] or None))
            if document.needs_pass:
                raise ValueError(f"Encrypted source needs a readable local export: {source}")
            if page_number > document.page_count:
                raise ValueError(f"Page {page_number} is absent from {source.name}")
            if not document.is_pdf:
                document = stack.enter_context(fitz.open("pdf", document.convert_to_pdf()))
            page = document[page_number - 1]
            page_rect = fitz.Rect(page.rect)
            if page_rect.is_empty or page_rect.is_infinite:
                raise ValueError(f"Invalid page dimensions: {source.name}")
            coords = clips.get(index, tuple(page_rect))
            if (not isinstance(coords, (tuple, list)) or len(coords) != 4
                    or any(not _finite_number(v) for v in coords)):
                raise ValueError("Clip must contain four finite numbers")
            x0, y0, x1, y1 = coords
            if not (page_rect.x0 <= x0 < x1 <= page_rect.x1
                    and page_rect.y0 <= y0 < y1 <= page_rect.y1):
                raise ValueError(f"Clip for view {index} must be inside displayed page {list(page_rect)}")
            clip = fitz.Rect(coords)
            if clip.is_empty or clip.is_infinite:
                raise ValueError("Clip cannot be represented as a nonempty PDF rectangle")
            rotation = page.rotation
            source_clip = clip * page.derotation_matrix
            # show_pdf_page expects unrotated source coordinates. Only this
            # in-memory document changes; reverse rotation preserves appearance.
            page.set_rotation(0)
            label_lines = _wrap(label, width, font, font_size)
            locator = f"{source.name} | page {page_number}"
            if index in clips:
                locator += " | clip pt: " + ", ".join(f"{v:g}" for v in coords)
            locator_lines = _wrap(locator, width, font, 8)
            loaded.append((source, document, page_number, clip, label_lines,
                           locator_lines, source_clip, rotation, page_rect))
        header = max(len(v[4]) * line_height + len(v[5]) * 12 for v in loaded) + 12
        heights = [width * v[3].height / v[3].width for v in loaded]
        dimensions = [width, 2 * margin + len(views) * width + (len(views)-1) * gap,
                      2 * margin + header + max(heights)]
        if any(not math.isfinite(v) or not 0 < v < fitz.FZ_MAX_INF_RECT for v in dimensions):
            raise ValueError("Output dimensions exceed the PDF coordinate range")
        pdf = stack.enter_context(fitz.open())
        page = pdf.new_page(width=2 * margin + len(views) * width + (len(views)-1) * gap,
                            height=2 * margin + header + max(heights))
        records = []
        pending = {}
        for index, (source, document, number, rect, labels, locators,
                    source_clip, rotation, page_rect) in enumerate(loaded):
            x = margin + index * (width + gap)
            view = stack.enter_context(fitz.open())
            view_page = view.new_page(width=2 * margin + width,
                                      height=2 * margin + header + heights[index])
            writer = fitz.TextWriter(view_page.rect)
            y = margin + font_size
            for line in labels:
                writer.append((margin, y), line, font=font, fontsize=font_size)
                y += line_height
            for line in locators:
                writer.append((margin, y), line, font=font, fontsize=8)
                y += 12
            target = fitz.Rect(x, margin + header, x + width,
                               margin + header + heights[index])
            local_target = fitz.Rect(margin, margin + header, margin + width,
                                     margin + header + heights[index])
            view_page.show_pdf_page(local_target, document, number-1,
                                    clip=source_clip, rotate=-rotation, keep_proportion=True)
            writer.write_text(view_page, color=(0.1, 0.15, 0.2))
            record = {"label": views[index][0], "source": str(source), "page": number,
                      "placed_rect_pt": list(target), "source_page_rect_pt": list(page_rect),
                      "clip_rect_pt": list(rect) if index + 1 in clips else None,
                      "source_rotation": rotation,
                      "coordinate_system": "displayed page; top-left origin; x right, y down; pt=1/72 inch",
                      "export_file": str(export_views[index+1]) if index+1 in export_views else None}
            view.set_metadata({"title": views[index][0], "subject": json.dumps(record, ensure_ascii=False)})
            # Reuse the same labelled page for both destinations, at identical scale.
            inner = fitz.Rect(margin, margin, margin + width, margin + header + heights[index])
            page.show_pdf_page(fitz.Rect(x, margin, x + width, inner.y1), view, 0, clip=inner)
            if index + 1 in export_views:
                pending[export_views[index+1]] = view.tobytes(garbage=4, deflate=True)
            records.append(record)
        pdf.set_metadata({"title": "Figure comparison", "subject":
                          json.dumps({"views": records, "review": "Not performed"}, ensure_ascii=False)})
        content = pdf.tobytes(garbage=4, deflate=True)
    _write_new({output: content, **pending})
    return {"status": "created", "output": str(output), "views": records,
            "view_width_mm": view_width_mm,
            "review": "Not performed by this helper; inspect the PDF and original views"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--view", nargs=3, action="append", required=True,
                        metavar=("ROLE_LABEL", "FILE", "PAGE"))
    parser.add_argument("--view-width-mm", type=float, default=160)
    parser.add_argument("--clip", nargs=5, action="append", default=[],
                        metavar=("VIEW", "X0", "Y0", "X1", "Y1"),
                        help="One-based view index; displayed-page points, top-left origin")
    parser.add_argument("--export-view", nargs=2, action="append", default=[],
                        metavar=("VIEW", "PDF"), help="Export the same labelled view as a standalone PDF")
    args = parser.parse_args()
    try:
        views = [(label, Path(file), int(page)) for label, file, page in args.view]
        clips, exports = {}, {}
        for index, *coords in args.clip:
            index = int(index)
            if index in clips:
                raise ValueError(f"Duplicate clip for view {index}")
            clips[index] = tuple(float(v) for v in coords)
        for index, path in args.export_view:
            index = int(index)
            if index in exports:
                raise ValueError(f"Duplicate export for view {index}")
            exports[index] = Path(path)
        result = build_comparison(args.output, views, view_width_mm=args.view_width_mm,
                                  clips=clips, export_views=exports)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"Cannot build comparison: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
