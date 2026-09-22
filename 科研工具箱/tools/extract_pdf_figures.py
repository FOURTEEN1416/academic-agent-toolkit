#!/usr/bin/env python3
"""extract_pdf_figures -- figure-level (not page-level) figure extraction
from a paper PDF. Host-neutral port, 2026-09.

Source (vendor fork, read-only, kept in place):
  vendor/forks/Auto-claude-code-research-in-sleep/skills/paper-poster-html/
      scripts/extract_pdf_figures.py
Its only cross-module dependency was ``_posterly.textutil.ascii_safe``
(a 1-line escaper); it is inlined below so this tool has no package deps
beyond PyMuPDF + Pillow.

Ported changes vs upstream:
  * CLI is flag-based and host-neutral: ``--pdf`` / ``--outdir`` (upstream
    used a positional pdf + ``--out`` with a poster-specific manifest-in-
    parent-dir convention; the manifest now lives INSIDE --outdir as
    ``figures_manifest.json``).
  * Added ``extract`` subcommand: auto-detect + crop in one pass, writing
    figure-level PNGs + manifest + human-readable stats. This is the
    batch entry point for the figure-style corpus (P5) — upstream ``auto``
    only proposed bboxes and required a manual ``crop`` per figure.
  * Detection logic (vector clusters / embedded rasters / text-gap voids,
    greedy overlap merge, area floor) is preserved verbatim.

Subcommands:
  contact-sheet  Render every page at a modest dpi with a labelled PDF-point
                 coordinate grid, so a human can read crop bboxes off it.
  auto           Detect candidate figure regions per page from three cheap
                 signals -- vector drawings (page.get_drawings), embedded
                 raster rects (page.get_images/get_image_rects), and large
                 vertical gaps between text blocks -- merge overlaps, print
                 a (page, bbox, w x h, kind-guess) table. Writes nothing.
  crop           Render one page clipped to --bbox at --dpi into
                 OUTDIR/<name>.png and upsert figures_manifest.json.
  extract        auto + crop for every candidate in one pass.

All bboxes are PDF points (72 dpi, fitz top-left origin), so a grid value
read off a contact-sheet can be fed verbatim to ``crop --bbox``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1
CONTACT_DPI = 110          # contact-sheet render dpi (readable, small files)
GRID_STEP_PT = 50          # gridline spacing in PDF points
PT_PER_INCH = 72.0
DEFAULT_MIN_AREA_PT2 = 10000.0   # ~100x100pt; filters rules/borders
DEFAULT_MIN_GAP_PT = 60.0


def ascii_safe(s: object) -> str:
    r"""Backslash-escape any non-ASCII char (inlined from upstream
    _posterly.textutil so console output is cp936-safe on Windows).

    ``ascii_safe("1.30×")`` -> ``"1.30\\xd7"``.
    """
    return str(s).encode("ascii", "backslashreplace").decode("ascii")


def _eprint(*args: object, **kw: object) -> None:
    print(*args, file=sys.stderr, **kw)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Lazy dependency loaders (so --help works in a stripped environment and a
# missing dep yields a readable hint instead of an import traceback).
# --------------------------------------------------------------------------
def _load_fitz():
    try:
        import fitz  # type: ignore
        return fitz
    except ImportError:
        _eprint(
            "ERROR: PyMuPDF (fitz) not installed -- required for all "
            "extract_pdf_figures subcommands. Install with:\n"
            "  python -m pip install pymupdf"
        )
        raise SystemExit(2)


def _load_pil():
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        return Image, ImageDraw, ImageFont
    except ImportError:
        _eprint(
            "ERROR: Pillow (PIL) not installed -- required for "
            "contact-sheet / crop rendering. Install with:\n"
            "  python -m pip install pillow"
        )
        raise SystemExit(2)


# --------------------------------------------------------------------------
# Shared helpers.
# --------------------------------------------------------------------------
def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pix_to_pil(pix, Image):
    """Convert a fitz Pixmap to a PIL RGB image without a temp file."""
    mode = "RGB"
    if pix.n == 1:
        mode = "L"
    elif pix.n == 4:
        mode = "RGBA"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    return img.convert("RGB")


def _open_doc(fitz, pdf_path: Path):
    try:
        return fitz.open(str(pdf_path))
    except Exception as exc:
        _eprint(f"ERROR: could not open PDF {ascii_safe(pdf_path)}: "
                f"{ascii_safe(exc)}")
        raise SystemExit(2)


def _resolve_pdf(args: argparse.Namespace) -> Path:
    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        _eprint(f"ERROR: PDF not found: {ascii_safe(pdf_path)}")
        raise SystemExit(2)
    return pdf_path


# --------------------------------------------------------------------------
# contact-sheet
# --------------------------------------------------------------------------
def cmd_contact_sheet(args: argparse.Namespace) -> int:
    """Render each page to a gridded PNG so bboxes can be read by eye."""
    fitz = _load_fitz()
    Image, ImageDraw, ImageFont = _load_pil()

    pdf_path = _resolve_pdf(args)
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = _open_doc(fitz, pdf_path)
    scale = CONTACT_DPI / PT_PER_INCH
    matrix = fitz.Matrix(scale, scale)
    font = ImageFont.load_default()

    written: list[str] = []
    for pno in range(doc.page_count):
        page = doc[pno]
        pix = page.get_pixmap(matrix=matrix)
        img = _pix_to_pil(pix, Image)
        draw = ImageDraw.Draw(img)

        rect = page.rect
        w_pt, h_pt = rect.width, rect.height

        grid_rgb = (170, 200, 230)
        label_rgb = (40, 90, 150)
        x = 0.0
        while x <= w_pt + 0.1:
            px = x * scale
            draw.line([(px, 0), (px, img.height)], fill=grid_rgb, width=1)
            draw.text((px + 2, 2), str(int(x)), fill=label_rgb, font=font)
            x += GRID_STEP_PT
        y = 0.0
        while y <= h_pt + 0.1:
            py = y * scale
            draw.line([(0, py), (img.width, py)], fill=grid_rgb, width=1)
            draw.text((2, py + 2), str(int(y)), fill=label_rgb, font=font)
            y += GRID_STEP_PT

        caption = (f"page {pno + 1}/{doc.page_count}  "
                   f"size={int(round(w_pt))}x{int(round(h_pt))}pt  "
                   f"grid={GRID_STEP_PT}pt")
        draw.rectangle([0, 0, max(2, len(caption) * 7), 14],
                       fill=(255, 255, 255))
        draw.text((2, 1), caption, fill=label_rgb, font=font)

        out_path = out_dir / f"contact_sheet_p{pno + 1:02d}.png"
        img.save(out_path)
        written.append(str(out_path))
        print(f"[contact-sheet] page {pno + 1}: "
              f"{int(round(w_pt))}x{int(round(h_pt))}pt -> "
              f"{ascii_safe(out_path)}")

    doc.close()
    if not written:
        _eprint("ERROR: PDF has no pages.")
        return 1
    print(f"[contact-sheet] wrote {len(written)} sheet(s) to "
          f"{ascii_safe(out_dir)} at {CONTACT_DPI} dpi.")
    return 0


# --------------------------------------------------------------------------
# Detection primitives (verbatim from upstream).
# --------------------------------------------------------------------------
def _rects_overlap(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _union_rect(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]),
            max(a[2], b[2]), max(a[3], b[3]))


def _merge_candidates(cands: list[dict]) -> list[dict]:
    """Greedily merge overlapping candidate rects (vector/raster/gap signals
    often describe the SAME figure). ``kind`` is concatenated."""
    merged: list[dict] = []
    for c in sorted(cands, key=lambda d: (d["page"], d["bbox"][1])):
        placed = False
        for m in merged:
            if m["page"] == c["page"] and _rects_overlap(m["bbox"], c["bbox"]):
                m["bbox"] = _union_rect(m["bbox"], c["bbox"])
                kinds = set(m["kind"].split("+")) | set(c["kind"].split("+"))
                m["kind"] = "+".join(sorted(kinds))
                placed = True
                break
        if not placed:
            merged.append(dict(c))
    return merged


def _text_gap_candidates(page, min_gap_pt: float) -> list[dict]:
    """Figure regions inferred from big vertical voids between text blocks."""
    rect = page.rect
    blocks = [b for b in page.get_text("blocks") if (b[4] or "").strip()]
    if not blocks:
        return []
    blocks.sort(key=lambda b: b[1])
    col_x0 = min(b[0] for b in blocks)
    col_x1 = max(b[2] for b in blocks)
    out: list[dict] = []
    for prev, cur in zip(blocks, blocks[1:]):
        gap_top = prev[3]
        gap_bot = cur[1]
        if gap_bot - gap_top >= min_gap_pt:
            out.append({
                "page": page.number + 1,
                "bbox": (round(col_x0, 1), round(gap_top, 1),
                         round(col_x1, 1), round(gap_bot, 1)),
                "kind": "gap",
            })
    top_lead = blocks[0][1] - rect.y0
    if top_lead >= min_gap_pt:
        out.append({
            "page": page.number + 1,
            "bbox": (round(col_x0, 1), round(rect.y0, 1),
                     round(col_x1, 1), round(blocks[0][1], 1)),
            "kind": "gap",
        })
    return out


def _vector_candidates(page, min_area_pt2: float) -> list[dict]:
    """Cluster overlapping vector drawings; keep clusters above an area floor."""
    draws = page.get_drawings()
    rects = []
    for d in draws:
        r = d.get("rect")
        if r is None:
            continue
        if r.width <= 0 or r.height <= 0:
            continue
        rects.append((r.x0, r.y0, r.x1, r.y1))
    if not rects:
        return []
    clusters: list[list[float]] = []
    for r in sorted(rects, key=lambda t: t[1]):
        placed = False
        for c in clusters:
            if _rects_overlap(c, r):
                c[0], c[1] = min(c[0], r[0]), min(c[1], r[1])
                c[2], c[3] = max(c[2], r[2]), max(c[3], r[3])
                placed = True
                break
        if not placed:
            clusters.append(list(r))
    out = []
    for c in clusters:
        area = (c[2] - c[0]) * (c[3] - c[1])
        if area >= min_area_pt2:
            out.append({
                "page": page.number + 1,
                "bbox": (round(c[0], 1), round(c[1], 1),
                         round(c[2], 1), round(c[3], 1)),
                "kind": "vector",
            })
    return out


def _image_candidates(page) -> list[dict]:
    """Embedded-raster bboxes via get_image_rects (placed location)."""
    out = []
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            for r in page.get_image_rects(xref):
                if r.width <= 0 or r.height <= 0:
                    continue
                out.append({
                    "page": page.number + 1,
                    "bbox": (round(r.x0, 1), round(r.y0, 1),
                             round(r.x1, 1), round(r.y1, 1)),
                    "kind": "image",
                })
        except Exception:
            continue
    return out


def _guess_kind(kind: str, bbox) -> str:
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    if kind == "gap":
        if h > 0 and (w / h) >= 3.0:
            return "table?"
        return "region?"
    return kind


def detect_candidates(doc, min_area_pt2: float,
                      min_gap_pt: float) -> list[dict]:
    """All-page candidate detection -> merged, area-filtered, sorted list of
    {page, bbox(x0,y0,x1,y1 pt), kind}. Shared by ``auto`` and ``extract``."""
    all_cands: list[dict] = []
    for pno in range(doc.page_count):
        page = doc[pno]
        all_cands += _vector_candidates(page, min_area_pt2)
        all_cands += _image_candidates(page)
        all_cands += _text_gap_candidates(page, min_gap_pt)

    merged = _merge_candidates(all_cands)
    merged = [m for m in merged
              if (m["bbox"][2] - m["bbox"][0]) * (m["bbox"][3] - m["bbox"][1])
              >= min_area_pt2]
    merged.sort(key=lambda m: (m["page"], m["bbox"][1]))
    return merged


def cmd_auto(args: argparse.Namespace) -> int:
    """Detect + print candidate figure regions; write nothing."""
    fitz = _load_fitz()
    pdf_path = _resolve_pdf(args)
    doc = _open_doc(fitz, pdf_path)
    merged = detect_candidates(doc, args.min_area, args.min_gap)
    doc.close()

    print(f"# candidate figure regions for {ascii_safe(pdf_path.name)} "
          f"(units: PDF points; bbox = x0,y0,x1,y1)")
    print(f"{'page':>4}  {'bbox (x0,y0,x1,y1)':<30}  "
          f"{'w x h':<16}  kind-guess")
    print("-" * 70)
    if not merged:
        print("(no candidates >= min-area; lower --min-area or use "
              "contact-sheet to pick a bbox by hand)")
    for m in merged:
        b = m["bbox"]
        w = b[2] - b[0]
        h = b[3] - b[1]
        bbox_s = f"{b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f}"
        wh_s = f"{w:.0f} x {h:.0f}"
        kind = _guess_kind(m["kind"], b)
        print(f"{m['page']:>4}  {bbox_s:<30}  {wh_s:<16}  {kind}")
    print("-" * 70)
    print(f"# {len(merged)} candidate(s). Extract all with:\n"
          f"#   python extract_pdf_figures.py --pdf FILE --outdir DIR extract")
    return 0


# --------------------------------------------------------------------------
# crop / extract -- render region(s) + manifest
# --------------------------------------------------------------------------
def _parse_bbox(s: str) -> tuple[float, float, float, float]:
    parts = s.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"--bbox must be 'x0,y0,x1,y1' (4 numbers), got {s!r}")
    try:
        x0, y0, x1, y1 = (float(p) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--bbox values must be numbers, got {s!r}")
    if x1 <= x0 or y1 <= y0:
        raise argparse.ArgumentTypeError(
            f"--bbox must have x1>x0 and y1>y0, got {s!r}")
    return (x0, y0, x1, y1)


def _manifest_path_for(out_dir: Path) -> Path:
    """Host-neutral: manifest lives INSIDE the output dir (upstream put it
    at the parent per a poster-html convention)."""
    return out_dir.resolve() / "figures_manifest.json"


def _rel_file_path(manifest_path: Path, png_path: Path) -> str:
    try:
        return str(png_path.resolve().relative_to(manifest_path.parent))
    except ValueError:
        return str(png_path.resolve())


def _load_manifest(manifest_path: Path, pdf_path: Path,
                   pdf_sha: str) -> dict:
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            _eprint(f"ERROR: existing manifest is unreadable: "
                    f"{ascii_safe(exc)}")
            raise SystemExit(1)
        data.setdefault("schema_version", SCHEMA_VERSION)
        data.setdefault("figures", [])
        src = data.get("source_pdf") or {}
        if src.get("sha256") != pdf_sha:
            data["source_pdf"] = {"path": str(pdf_path), "sha256": pdf_sha}
        return data
    return {
        "schema_version": SCHEMA_VERSION,
        "source_pdf": {"path": str(pdf_path), "sha256": pdf_sha},
        "figures": [],
    }


def _upsert_figure(manifest: dict, entry: dict) -> None:
    figs = manifest["figures"]
    for i, f in enumerate(figs):
        if f.get("asset_id") == entry["asset_id"]:
            figs[i] = entry
            return
    figs.append(entry)


def _crop_page(fitz, Image, page, clip_pt, dpi: float):
    """Render one page clipped to a point bbox; returns (PIL image, clamped
    fitz.Rect). Warns when the bbox was clamped to page bounds."""
    page_rect = page.rect
    clip = fitz.Rect(*clip_pt)
    clamped = clip & page_rect
    if clamped.is_empty:
        return None, None
    if (abs(clamped.x0 - clip.x0) > 0.5 or abs(clamped.y0 - clip.y0) > 0.5
            or abs(clamped.x1 - clip.x1) > 0.5 or abs(clamped.y1 - clip.y1) > 0.5):
        _eprint(f"[crop] WARN: bbox clamped to page bounds: "
                f"{clamped.x0:.0f},{clamped.y0:.0f},"
                f"{clamped.x1:.0f},{clamped.y1:.0f}")
    scale = dpi / PT_PER_INCH
    matrix = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix, clip=clamped)
    return _pix_to_pil(pix, Image), clamped


def cmd_crop(args: argparse.Namespace) -> int:
    """Render one page clipped to --bbox at --dpi, upsert the manifest."""
    fitz = _load_fitz()
    Image, _ImageDraw, _ImageFont = _load_pil()

    pdf_path = _resolve_pdf(args)
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = _open_doc(fitz, pdf_path)
    page_idx = args.page - 1
    if page_idx < 0 or page_idx >= doc.page_count:
        _eprint(f"ERROR: --page {args.page} out of range "
                f"(PDF has {doc.page_count} page(s)).")
        doc.close()
        return 2
    page = doc[page_idx]

    img, clip = _crop_page(fitz, Image, page, args.bbox, args.dpi)
    if img is None:
        _eprint(f"ERROR: --bbox {args.bbox} does not intersect page "
                f"{args.page} (size {page.rect.width:.0f}x"
                f"{page.rect.height:.0f}pt).")
        doc.close()
        return 2

    name = args.name
    if not name.lower().endswith(".png"):
        png_path = out_dir / f"{name}.png"
    else:
        png_path = out_dir / name
        name = name[:-4]
    img.save(png_path)
    natural_px = [img.width, img.height]
    crop_sha = _sha256_file(png_path)
    pdf_sha = _sha256_file(pdf_path)

    manifest_path = _manifest_path_for(out_dir)
    manifest = _load_manifest(manifest_path, pdf_path, pdf_sha)
    _upsert_figure(manifest, {
        "asset_id": name,
        "file": _rel_file_path(manifest_path, png_path),
        "from_paper": True,
        "page": args.page,
        "bbox": [round(clip.x0, 1), round(clip.y0, 1),
                 round(clip.x1, 1), round(clip.y1, 1)],
        "dpi": args.dpi,
        "sha256": crop_sha,
        "natural_px": natural_px,
        "caption_hint": args.caption_hint or "",
    })
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    doc.close()
    print(f"[crop] page {args.page} bbox=({clip.x0:.0f},{clip.y0:.0f},"
          f"{clip.x1:.0f},{clip.y1:.0f})pt @ {args.dpi}dpi -> "
          f"{ascii_safe(png_path)} ({natural_px[0]}x{natural_px[1]}px)")
    print(f"[crop] manifest upserted: {ascii_safe(manifest_path)} "
          f"(asset_id={name})")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """Batch mode: detect candidates (auto) then crop every one into OUTDIR,
    writing figure-level PNGs + figures_manifest.json + stats.

    This is the P5 figure-corpus entry point: one invocation per paper."""
    fitz = _load_fitz()
    Image, _ImageDraw, _ImageFont = _load_pil()

    pdf_path = _resolve_pdf(args)
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = _open_doc(fitz, pdf_path)
    page_count = doc.page_count
    cands = detect_candidates(doc, args.min_area, args.min_gap)
    if args.max_per_page > 0:
        per_page: dict[int, int] = {}
        capped = []
        for c in cands:
            n = per_page.get(c["page"], 0)
            if n < args.max_per_page:
                capped.append(c)
                per_page[c["page"]] = n + 1
        cands = capped

    pdf_sha = _sha256_file(pdf_path)
    manifest_path = _manifest_path_for(out_dir)
    manifest = _load_manifest(manifest_path, pdf_path, pdf_sha)

    stem = pdf_path.stem
    written = 0
    skipped = 0
    for idx, c in enumerate(cands, start=1):
        page_idx = c["page"] - 1
        page = doc[page_idx]
        img, clip = _crop_page(fitz, Image, page, c["bbox"], args.dpi)
        if img is None or clip.is_empty:
            skipped += 1
            continue
        name = f"{stem}_p{c['page']:02d}_fig{idx:02d}"
        png_path = out_dir / f"{name}.png"
        img.save(png_path)
        _upsert_figure(manifest, {
            "asset_id": name,
            "file": _rel_file_path(manifest_path, png_path),
            "from_paper": True,
            "page": c["page"],
            "bbox": [round(clip.x0, 1), round(clip.y0, 1),
                     round(clip.x1, 1), round(clip.y1, 1)],
            "dpi": args.dpi,
            "sha256": _sha256_file(png_path),
            "natural_px": [img.width, img.height],
            "kind": c["kind"],
            "kind_guess": _guess_kind(c["kind"], c["bbox"]),
            "caption_hint": "",
        })
        written += 1
        print(f"[extract] {ascii_safe(png_path.name)}  page {c['page']}  "
              f"{img.width}x{img.height}px  kind={c['kind']}")

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    pages_with_figs = len({c["page"] for c in cands})
    doc.close()
    print("-" * 70)
    print(f"[extract] pdf={ascii_safe(pdf_path.name)} "
          f"pages={page_count} candidates={len(cands)} "
          f"written={written} skipped={skipped} "
          f"pages_with_figures={pages_with_figs}")
    print(f"[extract] manifest: {ascii_safe(manifest_path)}")
    return 0 if written or not cands else 1


# --------------------------------------------------------------------------
# argument parser
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="extract_pdf_figures",
        description="Extract figure-level images from a paper PDF "
                    "(contact-sheet / auto / crop / extract). "
                    "bbox units = PDF points.",
    )
    p.add_argument("--pdf", required=True, help="source paper PDF")
    p.add_argument("--outdir", default="figures_out",
                   help="output directory for PNGs + figures_manifest.json "
                        "(unused by 'auto', which writes nothing)")
    p.add_argument("--dpi", type=float, default=200.0,
                   help="crop/extract render dpi (default 200; "
                        "contact-sheet uses its own fixed dpi)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser(
        "contact-sheet",
        help="render every page with a labelled PDF-point grid overlay",
    )
    pc.set_defaults(func=cmd_contact_sheet)

    pa = sub.add_parser(
        "auto",
        help="detect + print candidate figure regions (writes nothing)",
    )
    pa.add_argument("--min-area", dest="min_area", type=float,
                    default=DEFAULT_MIN_AREA_PT2,
                    help="ignore candidates below this area in pt^2 "
                         f"(default {DEFAULT_MIN_AREA_PT2:.0f}, ~100x100pt)")
    pa.add_argument("--min-gap", dest="min_gap", type=float,
                    default=DEFAULT_MIN_GAP_PT,
                    help="min vertical text void (pt) to flag as a "
                         f"candidate (default {DEFAULT_MIN_GAP_PT:.0f})")
    pa.set_defaults(func=cmd_auto)

    pcr = sub.add_parser(
        "crop",
        help="render page clipped to --bbox and upsert the manifest",
    )
    pcr.add_argument("--page", type=int, required=True,
                     help="1-based page number")
    pcr.add_argument("--bbox", type=_parse_bbox, required=True,
                     help="crop bbox in PDF points: x0,y0,x1,y1")
    pcr.add_argument("--name", required=True,
                     help="asset_id / output PNG stem (e.g. fig_method)")
    pcr.add_argument("--caption-hint", dest="caption_hint", default=None,
                     help="optional caption hint stored in the manifest")
    pcr.set_defaults(func=cmd_crop)

    pe = sub.add_parser(
        "extract",
        help="auto-detect + crop every candidate in one batch pass",
    )
    pe.add_argument("--min-area", dest="min_area", type=float,
                    default=DEFAULT_MIN_AREA_PT2)
    pe.add_argument("--min-gap", dest="min_gap", type=float,
                    default=DEFAULT_MIN_GAP_PT)
    pe.add_argument("--max-per-page", dest="max_per_page", type=int,
                    default=0,
                    help="cap crops per page (0 = no cap)")
    pe.set_defaults(func=cmd_extract)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
