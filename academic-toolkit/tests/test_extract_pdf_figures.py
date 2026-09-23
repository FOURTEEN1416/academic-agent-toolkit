"""Smoke tests for tools/extract_pdf_figures.py (figure-level PDF extractor).

Runs without any external corpus: a minimal 2-page PDF with 2 embedded
raster figures is synthesized in-process via PyMuPDF (skipped when fitz or
PIL are unavailable). Detection logic is exercised through the ``extract``
batch subcommand and the pure helpers.
"""
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "extract_pdf_figures.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "extract_pdf_figures_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_minimal_pdf(path: Path, pages: int = 2, figs_per_page: int = 2):
    """Synthesize a PDF: each page gets N non-overlapping embedded PNGs."""
    fitz = pytest.importorskip("fitz")
    pytest.importorskip("PIL")
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 150), (20, 60, 180)).save(buf, format="PNG")
    png_bytes = buf.getvalue()

    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=595, height=842)
        for k in range(figs_per_page):
            y0 = 80 + k * 250
            page.insert_image(fitz.Rect(60, y0, 260, y0 + 150),
                              stream=png_bytes)
    doc.save(str(path))
    doc.close()


# --------------------------------------------------------------------------
# dependency-free helper units
# --------------------------------------------------------------------------
def test_ascii_safe_escapes_non_ascii():
    module = load_module()
    assert module.ascii_safe("1.30×") == "1.30\\xd7"
    assert module.ascii_safe("plain") == "plain"


def test_parse_bbox_valid_and_invalid():
    module = load_module()
    assert module._parse_bbox("0,10,20,30") == (0.0, 10.0, 20.0, 30.0)
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        module._parse_bbox("1,2,3")
    with pytest.raises(argparse.ArgumentTypeError):
        module._parse_bbox("20,30,0,10")  # x1 <= x0


def test_merge_candidates_collapses_overlap():
    module = load_module()
    cands = [
        {"page": 1, "bbox": (0.0, 0.0, 100.0, 100.0), "kind": "vector"},
        {"page": 1, "bbox": (50.0, 50.0, 150.0, 150.0), "kind": "image"},
        {"page": 1, "bbox": (300.0, 300.0, 400.0, 400.0), "kind": "gap"},
        {"page": 2, "bbox": (0.0, 0.0, 100.0, 100.0), "kind": "image"},
    ]
    merged = module._merge_candidates(cands)
    assert len(merged) == 3
    joined = next(m for m in merged if m["kind"] != "gap" and m["page"] == 1)
    assert joined["kind"] == "image+vector"
    assert joined["bbox"] == (0.0, 0.0, 150.0, 150.0)


# --------------------------------------------------------------------------
# CLI smoke
# --------------------------------------------------------------------------
def test_help_exits_zero():
    module = load_module()
    with pytest.raises(SystemExit) as exc:
        module.main(["--help"])
    assert exc.value.code == 0


def test_missing_pdf_exits_two(tmp_path):
    module = load_module()
    pytest.importorskip("fitz")
    with pytest.raises(SystemExit) as exc:
        module.main(["--pdf", str(tmp_path / "nope.pdf"),
                     "--outdir", str(tmp_path / "out"), "auto"])
    assert exc.value.code == 2


# --------------------------------------------------------------------------
# end-to-end on a synthesized minimal PDF
# --------------------------------------------------------------------------
def test_extract_detects_figure_level_regions(tmp_path, capsys):
    module = load_module()
    pytest.importorskip("fitz")
    pdf = tmp_path / "mini.pdf"
    make_minimal_pdf(pdf, pages=2, figs_per_page=2)
    out = tmp_path / "figs"

    rc = module.main(["--pdf", str(pdf), "--dpi", "100",
                      "--outdir", str(out), "extract"])
    assert rc == 0
    pngs = sorted(out.glob("*.png"))
    assert len(pngs) == 4  # 2 pages x 2 figures, figure-level not page-level
    manifest = json.loads((out / "figures_manifest.json").read_text(
        encoding="utf-8"))
    assert len(manifest["figures"]) == 4
    assert all(f["kind"] == "image" for f in manifest["figures"])
    # crops are smaller than the page at the same dpi -> real figure boxes
    from PIL import Image
    w, h = Image.open(pngs[0]).size
    assert w < 595 * 100 / 72 and h < 842 * 100 / 72
    stats = capsys.readouterr().out
    assert "pages=2" in stats and "written=4" in stats


def test_crop_single_region(tmp_path):
    module = load_module()
    pytest.importorskip("fitz")
    pdf = tmp_path / "mini.pdf"
    make_minimal_pdf(pdf, pages=1, figs_per_page=1)
    out = tmp_path / "figs"

    rc = module.main(["--pdf", str(pdf), "--dpi", "100",
                      "--outdir", str(out), "crop",
                      "--page", "1", "--bbox", "60,80,260,230",
                      "--name", "fig_test"])
    assert rc == 0
    assert (out / "fig_test.png").exists()
    manifest = json.loads((out / "figures_manifest.json").read_text(
        encoding="utf-8"))
    assert manifest["figures"][0]["asset_id"] == "fig_test"
