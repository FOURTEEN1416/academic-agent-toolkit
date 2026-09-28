#!/usr/bin/env python3
"""Validate research-figure PDFs, raster exports, and provenance manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
from PIL import Image
from pypdf import PdfReader


def locate_pdftoppm(requested: str | None) -> str | None:
    return requested or shutil.which("pdftoppm")


def image_stats(path: Path) -> dict:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        gray = np.asarray(rgb.convert("L"), dtype=np.float32)
        return {
            "path": str(path.resolve()),
            "width": rgb.width,
            "height": rgb.height,
            "bytes": path.stat().st_size,
            "gray_std": float(gray.std()),
            "gray_min": int(gray.min()),
            "gray_max": int(gray.max()),
        }


def manifest_paths(manifest: dict) -> list[tuple[str, Path]]:
    paths = []
    for figure in manifest.get("figures", []):
        fid = figure.get("id", "unknown")
        for key in ("existing_figures", "plotting_sources", "data_inputs"):
            for value in figure.get(key, []):
                paths.append((f"{fid}.{key}", Path(value)))
        for reference in figure.get("references", []):
            if reference.get("path"):
                paths.append((f"{fid}.references", Path(reference["path"])))
        for panel in figure.get("panels", []):
            if panel.get("source"):
                paths.append((f"{fid}.panel.{panel.get('id', '?')}", Path(panel["source"])))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--image-dir", type=Path)
    parser.add_argument("--render-dir", type=Path)
    parser.add_argument("--expected-pages", type=int)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--required-text", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--pdftoppm")
    parser.add_argument("--dpi", type=int, default=110)
    parser.add_argument("--min-width", type=int, default=800)
    parser.add_argument("--min-height", type=int, default=600)
    args = parser.parse_args()

    if args.pdf is None and args.image_dir is None:
        raise SystemExit("Provide --pdf and/or --image-dir")

    failures: list[str] = []
    warnings: list[str] = []
    page_count = 0
    pdf_text = ""
    rendered: list[Path] = []

    if args.pdf:
        if not args.pdf.is_file() or args.pdf.stat().st_size == 0:
            failures.append("PDF is missing or empty")
        else:
            reader = PdfReader(str(args.pdf))
            page_count = len(reader.pages)
            pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if args.expected_pages is not None and page_count != args.expected_pages:
                failures.append(f"Expected {args.expected_pages} pages, found {page_count}")

            if args.render_dir:
                args.render_dir.mkdir(parents=True, exist_ok=True)
                tool = locate_pdftoppm(args.pdftoppm)
                if not tool:
                    warnings.append("pdftoppm not found; PDF render check skipped")
                else:
                    prefix = args.render_dir / "page"
                    process = subprocess.run(
                        [tool, "-png", "-r", str(args.dpi), str(args.pdf), str(prefix)],
                        capture_output=True,
                        text=True,
                    )
                    if process.returncode:
                        failures.append(f"pdftoppm failed: {process.stderr.strip()}")
                    rendered = sorted(args.render_dir.glob("page-*.png"))
                    if len(rendered) != page_count:
                        failures.append(f"Rendered {len(rendered)} PNGs for {page_count} PDF pages")

    if args.required_text:
        for line in args.required_text.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if re.search(line, pdf_text, re.I) is None:
                failures.append(f"Required PDF text not found: {line}")

    raster_paths = list(rendered)
    if args.image_dir:
        if not args.image_dir.is_dir():
            failures.append(f"Image directory not found: {args.image_dir}")
        else:
            raster_paths.extend(sorted(
                path for path in args.image_dir.iterdir()
                if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
            ))

    stats = []
    seen = set()
    for path in raster_paths:
        if path.resolve() in seen:
            continue
        seen.add(path.resolve())
        try:
            stat = image_stats(path)
            stats.append(stat)
            if stat["bytes"] < 1000 or stat["gray_std"] < 1.0:
                failures.append(f"Blank or suspicious raster: {path}")
            if stat["width"] < args.min_width or stat["height"] < args.min_height:
                warnings.append(
                    f"Raster below recommended dimensions: {path} "
                    f"({stat['width']}x{stat['height']})"
                )
        except Exception as exc:
            failures.append(f"Could not inspect raster {path}: {exc}")

    manifest_result = {"checked": False, "missing_paths": []}
    if args.manifest:
        if not args.manifest.is_file():
            failures.append(f"Manifest not found: {args.manifest}")
        else:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            missing = [
                {"field": field, "path": str(path)}
                for field, path in manifest_paths(manifest)
                if not path.exists()
            ]
            manifest_result = {"checked": True, "missing_paths": missing}
            if missing:
                failures.append(f"Manifest contains {len(missing)} missing source paths")

    report = {
        "status": "FAIL" if failures else "PASS",
        "pdf": str(args.pdf.resolve()) if args.pdf else None,
        "page_count": page_count,
        "pdf_bytes": args.pdf.stat().st_size if args.pdf and args.pdf.exists() else 0,
        "text_characters": len(pdf_text),
        "raster_checks": stats,
        "manifest": manifest_result,
        "failures": failures,
        "warnings": warnings,
        "visual_review_required": True,
        "scientific_value_check_required": True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.report.resolve())
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
