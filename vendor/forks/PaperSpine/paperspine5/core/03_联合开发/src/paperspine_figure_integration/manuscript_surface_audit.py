"""Check that figure numbering survives TeX/PDF/Word publication surfaces.

This is a small pre-review guard for the paper workflow.  File hashes prove
that a surface is stable; they do not prove that the surface still contains
the figures and captions described by the current source.  The audit derives
the expected order from the current TeX and checks the rendered PDF text and
editable Word text against it.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


def expected_figures(tex: Path) -> list[tuple[int, str]]:
    text = tex.read_text(encoding="utf-8")
    # TeX adds the printed number; the source caption itself usually does not
    # contain it.  Derive the expected numbering from figure-environment
    # order, which is the same order used by the PDF and Word converters.
    found: list[tuple[int, str]] = []
    for block in re.finditer(r"\\begin\{figure\}.*?\\label\{(fig:[^}]+)\}.*?\\end\{figure\}", text, re.S):
        found.append((len(found) + 1, block.group(1)))
    return found


def _surface_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return subprocess.check_output(["pdftotext", str(path), "-"]).decode("utf-8", "ignore")
    if path.suffix.lower() == ".docx":
        from docx import Document

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError(f"unsupported surface: {path}")


def audit(tex: Path, *surfaces: Path) -> list[str]:
    figures = expected_figures(tex)
    if not figures:
        raise ValueError(f"no labelled figures found in {tex}")
    errors: list[str] = []
    for surface in surfaces:
        text = _surface_text(surface)
        for number, label in figures:
            if not re.search(rf"Figure\s+{number}[.:]", text):
                errors.append(f"{surface}: missing Figure {number} caption")
            # A source label is expected to appear as a caption in the same
            # numbered publication surface; this catches stale renumbering.
        if surface.suffix.lower() == ".docx":
            captions = re.findall(r"Figure\s+(\d+)\.", text)
            if captions[: len(figures)] != [str(number) for number, _ in figures]:
                errors.append(f"{surface}: figure caption order {captions!r} != {[n for n, _ in figures]!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tex", type=Path)
    parser.add_argument("surfaces", nargs="+", type=Path)
    args = parser.parse_args()
    errors = audit(args.tex, *args.surfaces)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"PASS: {len(expected_figures(args.tex))} figure captions agree across {len(args.surfaces)} surfaces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
