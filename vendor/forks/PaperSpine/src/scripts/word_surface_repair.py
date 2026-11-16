#!/usr/bin/env python3
"""Repair reader-visible Word surfaces that contain raw Pandoc TeX math.

The canonical LaTeX source remains unchanged.  This utility renders each raw
display-math paragraph already present in a DOCX into a real equation image,
embeds the image in place, and unwraps unresolved internal hyperlinks while
preserving their visible text.  External hyperlinks remain intact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches

RAW_DISPLAY_MATH = re.compile(r"^\s*\$\$(?P<body>.+)\$\$\s*$", re.DOTALL)
RAW_TEX_MARKUP = re.compile(
    r"\\(?:begin|end)\s*\{(?:equation|align|aligned|gather|multline)\*?\}|\$\$",
    re.IGNORECASE,
)
DISPLAY_ENVIRONMENT = re.compile(
    r"\\begin\{(?P<environment>equation\*?|align\*?|gather\*?|multline\*?)\}"
    r".*?\\end\{(?P=environment)\}",
    re.DOTALL,
)
LINEAR_MATH_REPLACEMENTS = str.maketrans(
    {
        "∈": " in ",
        "≥": ">=",
        "≤": "<=",
        "×": " x ",
        "−": "-",
        "σ": "sigma",
        "⊙": " elementwise-product ",
        "α": "alpha",
        "β": "beta",
        "γ": "gamma",
        "ε": "epsilon",
        "Δ": "Delta",
        "δ": "delta",
        "λ": "lambda",
        "μ": "mu",
        "ρ": "rho",
        "ℓ": "ell",
    }
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _equation_document(raw_body: str) -> str:
    body = re.sub(r"\\label\{[^{}]+\}", "", raw_body).strip()
    body = re.sub(r"\n\s*\n", "\n", body)
    if re.match(
        r"^\\begin\{(?:equation|align|gather|multline)\*?\}", body
    ):
        display = body
    else:
        display = "\\begin{equation*}\n" + body + "\n\\end{equation*}"
    return (
        "\\documentclass{article}\n"
        "\\usepackage{amsmath,amssymb,bm,mathtools}\n"
        "\\usepackage[active,tightpage]{preview}\n"
        "\\setlength\\PreviewBorder{8pt}\n"
        "\\PreviewEnvironment{equation}\n"
        "\\PreviewEnvironment{equation*}\n"
        "\\PreviewEnvironment{align}\n"
        "\\PreviewEnvironment{align*}\n"
        "\\PreviewEnvironment{gather}\n"
        "\\PreviewEnvironment{gather*}\n"
        "\\PreviewEnvironment{multline}\n"
        "\\PreviewEnvironment{multline*}\n"
        "\\begin{document}\n"
        + display
        + "\n\\end{document}\n"
    )


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        detail = (completed.stdout + "\n" + completed.stderr).strip()[-3000:]
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{detail}"
        )
    return completed


def render_equation(raw_body: str, output_png: Path, *, work_dir: Path) -> None:
    engine = shutil.which("pdflatex")
    converter = shutil.which("pdftoppm")
    if not engine or not converter:
        raise RuntimeError("pdflatex and pdftoppm are required for equation repair")
    snippet = work_dir / "equation.tex"
    snippet.write_text(_equation_document(raw_body), encoding="utf-8")
    _run(
        [
            engine,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-output-directory",
            str(work_dir),
            str(snippet),
        ],
        cwd=work_dir,
    )
    rendered_pdf = work_dir / "equation.pdf"
    _run(
        [
            converter,
            "-png",
            "-r",
            "300",
            "-singlefile",
            str(rendered_pdf),
            str(output_png.with_suffix("")),
        ],
        cwd=work_dir,
    )
    if not output_png.is_file() or output_png.stat().st_size < 100:
        raise RuntimeError(f"equation render was not created: {output_png}")


def _clear_paragraph(paragraph: Any) -> None:
    element = paragraph._p
    if element.xpath(".//w:hyperlink"):
        raise ValueError("Cannot replace linked equation content without losing its destination; repair the semantic source.")
    for child in list(element):
        if child.tag not in {qn("w:pPr"), qn("w:bookmarkStart"), qn("w:bookmarkEnd")}:
            element.remove(child)


def _display_math_paragraphs(document: Any) -> list[Any]:
    return [
        paragraph
        for paragraph in document.paragraphs
        if paragraph._p.xpath(".//m:oMathPara")
        or (not paragraph.text.strip() and paragraph._p.xpath(".//m:oMath"))
    ]


def _linearize_inline_office_math(document: Any) -> int:
    math_tag = qn("m:oMath")
    math_text_tag = qn("m:t")
    count = 0
    for math in list(document.element.iter(math_tag)):
        visible = "".join(node.text or "" for node in math.iter(math_text_tag)).strip()
        if not visible:
            visible = "equation"
        visible = re.sub(r"\s+", " ", visible.translate(LINEAR_MATH_REPLACEMENTS))
        run = OxmlElement("w:r")
        properties = OxmlElement("w:rPr")
        properties.append(OxmlElement("w:i"))
        run.append(properties)
        text = OxmlElement("w:t")
        text.set(qn("xml:space"), "preserve")
        text.text = f" {visible} "
        run.append(text)
        parent = math.getparent()
        index = parent.index(math)
        parent.remove(math)
        parent.insert(index, run)
        count += 1
    return count


def _constrain_inline_shapes(document: Any) -> int:
    max_width = Inches(5.3)
    max_height = Inches(5.3)
    changed = 0
    for shape in document.inline_shapes:
        width = int(shape.width)
        height = int(shape.height)
        scale = min(float(max_width) / width, float(max_height) / height, 1.0)
        if scale < 1.0:
            shape.width = int(width * scale)
            shape.height = int(height * scale)
            changed += 1
    return changed


def _unwrap_internal_hyperlinks(document: Any, repairs: list[dict[str, str]] | None = None) -> int:
    """Remove only locally anchored links whose target is demonstrably absent.

    Relationship links can address another document; their anchors need not exist
    here. Inspect other connected Word XML parts too before declaring an anchor
    absent. A retained name is not proof that its bookmark range is well formed.
    """
    hyperlink_tag = qn("w:hyperlink")
    anchor_attr = qn("w:anchor")
    bookmark_names = {node.get(qn("w:name")) for node in document.element.iter(qn("w:bookmarkStart"))}
    for part in document.part.package.parts:
        if part is document.part or not str(part.partname).startswith("/word/") or not str(part.partname).endswith(".xml"):
            continue
        root = ElementTree.fromstring(part.blob)
        bookmark_names.update(node.get(qn("w:name")) for node in root.iter(qn("w:bookmarkStart")))
    count = 0
    for hyperlink in list(document.element.iter(hyperlink_tag)):
        anchor = hyperlink.get(anchor_attr)
        if not anchor or hyperlink.get(qn("r:id")) or anchor.lower() == "_top" or anchor in bookmark_names:
            continue
        if repairs is not None:
            repairs.append({
                "anchor": anchor,
                "visible_text": "".join(node.text or "" for node in hyperlink.iter(qn("w:t"))),
                "action": "Removed dangling navigation; retained visible content and run formatting.",
                "reference_status": "UNRESOLVED: recover the intended destination from the semantic source.",
            })
        parent = hyperlink.getparent()
        index = parent.index(hyperlink)
        for child in list(hyperlink):
            hyperlink.remove(child)
            parent.insert(index, child)
            index += 1
        parent.remove(hyperlink)
        count += 1
    return count


def repair_word_surface(
    *, docx_path: Path, tex_path: Path, output_path: Path, render_dir: Path
) -> dict[str, Any]:
    if not docx_path.is_file() or not tex_path.is_file():
        raise FileNotFoundError("both --docx and --tex must name existing files")
    source_docx_sha256 = sha256_file(docx_path)
    render_dir.mkdir(parents=True, exist_ok=True)
    document = Document(str(docx_path))
    repair_targets: list[tuple[Any, str]] = []
    for paragraph in document.paragraphs:
        matched = RAW_DISPLAY_MATH.match(paragraph.text)
        if matched:
            repair_targets.append((paragraph, matched.group("body").strip()))

    if not repair_targets:
        display_paragraphs = _display_math_paragraphs(document)
        canonical_tex = tex_path.read_text(encoding="utf-8")
        source_blocks = [
            matched.group(0)
            for matched in DISPLAY_ENVIRONMENT.finditer(canonical_tex)
        ]
        if display_paragraphs and len(display_paragraphs) != len(source_blocks):
            raise RuntimeError(
                "cannot bind Office display math to canonical LaTeX equations "
                f"({len(display_paragraphs)}/{len(source_blocks)})"
            )
        repair_targets = list(zip(display_paragraphs, source_blocks, strict=True))

    for index, (paragraph, body) in enumerate(repair_targets, start=1):
        image_path = render_dir / f"equation-{index:03d}.png"
        work_dir = render_dir / f".build-{index:03d}-{uuid.uuid4().hex}"
        work_dir.mkdir()
        render_equation(body, image_path, work_dir=work_dir)
        _clear_paragraph(paragraph)
        run = paragraph.add_run()
        run.add_picture(str(image_path), width=Inches(5.8))
        # Keep a bookmark enclosing the equation enclosing the replacement too.
        end = paragraph._p.find(qn("w:bookmarkEnd"))
        if end is not None:
            end.addprevious(run._r)

    inline_math_linearized = _linearize_inline_office_math(document)
    internal_link_repairs: list[dict[str, str]] = []
    internal_links_unwrapped = _unwrap_internal_hyperlinks(document, internal_link_repairs)
    oversized_images_constrained = _constrain_inline_shapes(document)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    changed = bool(repair_targets or inline_math_linearized or internal_links_unwrapped or oversized_images_constrained)
    if changed:
        document.save(str(output_path))
    elif docx_path.resolve() != output_path.resolve():
        shutil.copy2(docx_path, output_path)
    reopened = Document(str(output_path))
    visible_text = "\n".join(paragraph.text for paragraph in reopened.paragraphs)
    if RAW_TEX_MARKUP.search(visible_text):
        raise RuntimeError("raw TeX display math remains after Word surface repair")
    if reopened.element.xpath(".//m:oMath") or reopened.element.xpath(".//m:oMathPara"):
        raise RuntimeError("Office math remains after Word surface repair")
    return {
        "contract": "paper-spine.word-surface-repair-receipt",
        "schema_version": "1.0",
        "source_docx_sha256": source_docx_sha256,
        "canonical_tex_sha256": sha256_file(tex_path),
        "output_docx_sha256": sha256_file(output_path),
        "display_equations_rendered": len(repair_targets),
        "inline_math_linearized": inline_math_linearized,
        "internal_hyperlinks_unwrapped": internal_links_unwrapped,
        "internal_hyperlink_repairs": internal_link_repairs,
        "changed": changed,
        "oversized_images_constrained": oversized_images_constrained,
        "render_dir": str(render_dir.resolve()),
        "output": str(output_path.resolve()),
        "status": "NEEDS_REVIEW" if internal_link_repairs else "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render raw Pandoc TeX equations into a Word surface"
    )
    parser.add_argument("--docx", required=True, type=Path)
    parser.add_argument("--tex", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--render-dir", type=Path)
    args = parser.parse_args()
    tex_hash = sha256_file(args.tex)
    render_dir = args.render_dir or (
        args.output.parent / f"word-equations-{tex_hash[:12]}"
    )
    receipt = repair_word_surface(
        docx_path=args.docx.resolve(),
        tex_path=args.tex.resolve(),
        output_path=args.output.resolve(),
        render_dir=render_dir.resolve(),
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
