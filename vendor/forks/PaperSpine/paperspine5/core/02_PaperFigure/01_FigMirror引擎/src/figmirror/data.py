"""Matplotlib helpers for editable, publication-oriented data figures."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .svg import audit_svg

PUBLICATION_RC: dict[str, Any] = {
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#26343d",
    "axes.labelcolor": "#172027",
    "axes.linewidth": 0.8,
    "axes.titleweight": 600,
    "axes.titlesize": 10,
    "axes.labelsize": 8.5,
    "xtick.color": "#42515b",
    "ytick.color": "#42515b",
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "grid.color": "#dce3e6",
    "grid.linewidth": 0.55,
    "grid.alpha": 0.72,
    "legend.frameon": False,
    "legend.fontsize": 7.5,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "Microsoft YaHei"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.04,
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_records(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            raise FileNotFoundError(path)
        records.append({"path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    if not records:
        raise ValueError("data figures require at least one source file")
    return records


def save_editable_figure(fig: Any, output_stem: str | Path, *, dpi: int = 300) -> dict[str, str]:
    """Export SVG/PDF/PNG while keeping SVG text as editable text."""

    stem = Path(output_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    svg = stem.with_suffix(".svg")
    pdf = stem.with_suffix(".pdf")
    png = stem.with_suffix(".png")
    fig.savefig(svg, format="svg")
    fig.savefig(pdf, format="pdf")
    fig.savefig(png, format="png", dpi=dpi)
    audit = audit_svg(svg, allow_raster=False, require_text=True)
    if audit.status != "PASS":
        raise ValueError(f"Matplotlib SVG failed editability audit: {audit.failures}")
    return {"svg": str(svg), "pdf": str(pdf), "png": str(png)}

