#!/usr/bin/env python3
"""Reject interior PDF pages that are visually almost empty.

The check combines extracted text with a low-resolution grayscale render.  A
page with very little text is allowed when a figure or other visual actually
occupies the page; a page containing only a stranded line and page number is
not.  Cover and final pages are excluded because their sparse layouts can be
intentional.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PAGE_NUMBER_RE = re.compile(r"^\s*(?:第\s*)?\d+(?:\s*页)?\s*$", re.IGNORECASE)
TOKEN_RE = re.compile(r"[\u3400-\u9fff]|[A-Za-z]+(?:[-'][A-Za-z]+)*|\d+(?:\.\d+)?")


@dataclass(frozen=True)
class SparsePage:
    page_number: int
    visible_units: int
    ink_coverage: float | None
    preview: str


def visible_units(text: str) -> int:
    lines = [line for line in text.splitlines() if not PAGE_NUMBER_RE.fullmatch(line)]
    return len(TOKEN_RE.findall("\n".join(lines)))


def _preview(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    body = " ".join(line for line in lines if line and not PAGE_NUMBER_RE.fullmatch(line))
    return body[:80] or "(无正文文本)"


def _extract_pages_with_pdftotext(pdf_path: Path) -> list[str] | None:
    candidates: list[str] = []
    # Prefer the Poppler binary on PATH.  Some MiKTeX distributions ship a
    # pdftotext wrapper that writes UTF-16 on Windows; older code decoded that
    # as UTF-8 and mistook low bytes for dozens of phantom page breaks.
    executable = shutil.which("pdftotext")
    if executable:
        candidates.append(executable)
    xelatex = shutil.which("xelatex")
    if xelatex:
        sibling = Path(xelatex).with_name("pdftotext.exe")
        if sibling.is_file() and str(sibling) not in candidates:
            candidates.append(str(sibling))
    for executable in candidates:
        result = subprocess.run(
            [executable, "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            continue
        raw = result.stdout
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = raw.decode("utf-16", errors="replace")
        elif raw and raw.count(b"\x00") / len(raw) > 0.08:
            # Defensive fallback for wrappers that ignore ``-enc UTF-8``.
            text = raw.decode("utf-16-le", errors="replace")
        else:
            text = raw.decode("utf-8", errors="replace")
        pages = text.split("\f")
        while pages and not pages[-1].strip():
            pages.pop()
        if pages and any(TOKEN_RE.search(page) for page in pages):
            return pages
    return None


def _extract_pages_with_pypdf(pdf_path: Path) -> list[str] | None:
    try:
        from pypdf import PdfReader

        return [page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages]
    except Exception:
        return None


def extract_pages(pdf_path: Path) -> list[str]:
    poppler_pages = _extract_pages_with_pdftotext(pdf_path)
    pypdf_pages = _extract_pages_with_pypdf(pdf_path)
    # A decoder/wrapper bug must never invent physical pages.  pypdf reads the
    # PDF page tree directly, so prefer its count whenever the two disagree.
    pages = (pypdf_pages if poppler_pages and pypdf_pages
             and len(poppler_pages) != len(pypdf_pages)
             else poppler_pages or pypdf_pages)
    if not pages:
        raise RuntimeError("无法提取 PDF 分页文本（需要 pdftotext 或 pypdf）")
    return pages


def _pgm_ink_coverage(path: Path) -> float:
    data = path.read_bytes()
    position = 0

    def token() -> bytes:
        nonlocal position
        while position < len(data):
            if data[position:position + 1] == b"#":
                position = data.find(b"\n", position)
                if position < 0:
                    raise ValueError("invalid PGM comment")
            elif data[position] in b" \t\r\n":
                position += 1
            else:
                break
        start = position
        while position < len(data) and data[position] not in b" \t\r\n#":
            position += 1
        return data[start:position]

    magic = token()
    width, height, max_value = int(token()), int(token()), int(token())
    while position < len(data) and data[position] in b" \t\r\n":
        position += 1
    if magic == b"P5":
        pixels = data[position:position + width * height]
        if max_value > 255:
            raise ValueError("16-bit PGM is unsupported")
        dark = sum(value < 245 for value in pixels)
        return dark / max(1, len(pixels))
    if magic == b"P2":
        values = [int(value) for value in data[position:].split()]
        dark = sum(value < max_value * 0.96 for value in values)
        return dark / max(1, len(values))
    raise ValueError(f"unsupported PGM format: {magic!r}")


def render_ink_coverage(pdf_path: Path, page_number: int) -> float | None:
    executable = shutil.which("pdftoppm")
    if not executable:
        return None
    with tempfile.TemporaryDirectory(prefix="modex-page-density-") as tmp:
        prefix = Path(tmp) / "page"
        result = subprocess.run(
            [
                executable, "-f", str(page_number), "-l", str(page_number),
                "-r", "24", "-gray", "-singlefile", str(pdf_path), str(prefix),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        pgm = prefix.with_suffix(".pgm")
        if result.returncode != 0 or not pgm.is_file():
            return None
        try:
            return _pgm_ink_coverage(pgm)
        except (OSError, ValueError):
            return None


def find_sparse_pages(
    pages: list[str],
    coverage_for_page: Callable[[int], float | None],
    *,
    minimum_units: int = 35,
    maximum_sparse_ink: float = 0.008,
) -> list[SparsePage]:
    sparse: list[SparsePage] = []
    # The first page may be a cover.  The final page may legitimately contain
    # only the tail of an appendix/reference list.  All interior pages are gated.
    for index, text in enumerate(pages, start=1):
        if index == 1 or index == len(pages):
            continue
        units = visible_units(text)
        if units >= minimum_units:
            continue
        coverage = coverage_for_page(index)
        if coverage is None:
            # Without rendering, do not mistake a full-page graphic for a blank
            # page.  Only the strongest text-only signal remains a hard failure.
            is_sparse = units <= 5
        else:
            is_sparse = coverage < maximum_sparse_ink
        if is_sparse:
            sparse.append(SparsePage(index, units, coverage, _preview(text)))
    return sparse


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args(argv[1:])
    pdf_path = args.pdf.resolve()
    if not pdf_path.is_file():
        print(f"FAIL: PDF 不存在: {pdf_path}")
        return 1
    try:
        pages = extract_pages(pdf_path)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1
    sparse = find_sparse_pages(
        pages,
        lambda page_number: render_ink_coverage(pdf_path, page_number),
    )
    if sparse:
        print("FAIL: 检测到正文内部大面积空白页")
        for item in sparse:
            coverage = "不可用" if item.ink_coverage is None else f"{item.ink_coverage:.3%}"
            print(
                f"  - 第 {item.page_number} 页: 文本单位 {item.visible_units}, "
                f"页面墨迹覆盖 {coverage}, 内容: {item.preview}"
            )
        print("  请移除正文章节间的 \\clearpage/\\newpage，或修复被单独遗留的表后尾段。")
        return 1
    print(f"OK: {len(pages)} 页中未发现正文内部大面积空白页")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
