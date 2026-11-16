#!/usr/bin/env python3
"""Prepare and validate rendered-page plus figure-semantic visual receipts.

Direct --inspect-pdf mode reads page pixels without receipts or task mutations.
It reports layout signals, never scientific or visual approval.

The legacy receipt mode renders deterministically when Poppler is available. A multimodal
agent or human must then inspect every rendered page and figure and replace each
`pending` check in visual_audit_manifest.json with `pass` or `fail` plus notes.
The validator binds those receipts to current file hashes so stale inspection
cannot pass after the paper changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

PAGE_CHECKS = ("title_author_header_bounds", "media_crop_box", "clipping", "blank_or_float_only", "readability")
FIGURE_CHECKS = (
    "method_names",
    "panel_labels",
    "baselines",
    "metrics",
    "datasets",
    "caption_text_alignment",
    "story_claim_alignment",
    "panel_role_alignment",
    "claim_boundary_respected",
)
INCLUDE_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
FIGURE_ENV_RE = re.compile(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", re.S)
CAPTION_RE = re.compile(r"\\caption\{(.*?)\}", re.S)
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")


@dataclass
class VisualResult:
    manifest: str
    ok: bool
    page_count: int
    figure_count: int
    findings: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare or validate PaperSpine visual audit receipts.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--prepare", action="store_true", help="Render the final PDF/figures and create a pending audit manifest.")
    parser.add_argument("--inspect-pdf", type=Path, help="Read PDF pixels directly; no manifest or task state required.")
    parser.add_argument("--columns", type=int, choices=(1, 2), default=1,
                        help="Expected manuscript columns for direct PDF inspection (default: 1).")
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()



def _layout_region(pixmap, bbox: tuple[float, float, float, float]) -> dict:
    """Measure occupied rows, not text extraction (plots/scans count as ink)."""
    width, height = pixmap.width, pixmap.height
    x0, y0, x1, y1 = bbox
    left, right = int(x0 * width), max(int(x0 * width) + 1, int(x1 * width))
    top, bottom = int(y0 * height), max(int(y0 * height) + 1, int(y1 * height))
    samples = pixmap.samples
    occupied = []
    # Ignore isolated antialiasing dots, not meaningful light-gray graphics.
    minimum_ink = max(2, (right - left) * 0.006)
    for row in range(top, bottom):
        offset = row * pixmap.stride
        occupied.append(sum(value < 225 for value in samples[offset + left:offset + right]) >= minimum_ink)
    longest = start = run = 0
    for index, active in enumerate(occupied):
        run = 0 if active else run + 1
        if run > longest:
            longest, start = run, index - run + 1
    return {
        "bbox_normalized": list(bbox),
        "occupied_row_fraction": round(sum(occupied) / len(occupied), 4),
        "largest_void_fraction": round(longest / len(occupied), 4),
        "largest_void_y_normalized": [round((top + start) / height, 4),
                                       round((top + start + longest) / height, 4)],
    }


def inspect_pdf_layout(pdf_path: Path, *, columns: int = 1) -> dict:
    """Read a bounded PDF snapshot; heuristic signals require contextual review.

    No receipts, notes, file counts or stored approvals are consulted. Page
    geometry is rendered at <=72 dpi, bounded to 1600px on the longest edge.
    This is intentionally NOT a proof of reading, content parity or quality.
    """
    pdf_path = Path(pdf_path).resolve()
    result = {
        "pdf": str(pdf_path), "sha256": "", "status": "analysis_incomplete",
        "expected_columns": columns, "page_count": 0, "pages_analyzed": 0,
        "pages": [], "findings": [], "errors": [],
        "limitations": [
            "Pixel occupancy is a heuristic, not scientific or visual approval; inspect every rendered page.",
            "Title pages, reference tails and intentional figure pages may be sparse; review in context.",
            "The outer 8% is excluded; clipping, white-on-white text and reading order require visual inspection.",
            "A PDF hash identifies inspected bytes, not source/output synchronization or an independent review.",
        ],
    }
    if columns not in (1, 2):
        result["errors"].append("Expected columns must be 1 or 2.")
        return result
    try:
        import fitz
    except ImportError:
        result["errors"].append("PyMuPDF is unavailable. Use an existing PDF-capable runtime or render and inspect manually; do not mark this check passed.")
        return result
    try:
        with pdf_path.open("rb") as handle:
            data = handle.read(128 * 1024 * 1024 + 1)
        if len(data) > 128 * 1024 * 1024:
            raise ValueError("PDF exceeds the 128 MiB inspection bound; inspect manually or use a bounded derivative.")
        result["sha256"] = hashlib.sha256(data).hexdigest()
        with fitz.open(stream=data, filetype="pdf") as document:
            if document.needs_pass:
                raise ValueError("PDF is encrypted; inspect an authorized decrypted local copy.")
            result["page_count"] = len(document)
            if not len(document):
                raise ValueError("PDF contains no pages.")
            for page_index in range(len(document)):
                try:
                    page = document[page_index]
                    scale = min(1.0, 1600 / max(page.rect.width, page.rect.height))
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
                    regions = {"body": _layout_region(pixmap, (0.08, 0.08, 0.92, 0.92))}
                    if columns == 2:
                        regions.update({"left_column": _layout_region(pixmap, (0.08, 0.08, 0.48, 0.92)),
                                        "right_column": _layout_region(pixmap, (0.52, 0.08, 0.92, 0.92))})
                    context = "first_page" if page_index == 0 else "last_page" if page_index == len(document) - 1 else "interior_page"
                    result["pages"].append({"page": page_index + 1, "context": context, "regions": regions})
                    result["pages_analyzed"] += 1
                    for name, metrics in regions.items():
                        occupancy = metrics["occupied_row_fraction"]
                        # Thin chart strokes or generous line spacing can have low
                        # ink occupancy while filling the page. Require a real gap.
                        gap = metrics["largest_void_fraction"]
                        if occupancy < 0.025:
                            code = "nearly_empty_region"
                        elif gap > 0.20:
                            code = "large_vertical_void"
                        elif occupancy < 0.28 and gap > 0.12:
                            code = "sparse_region"
                        else:
                            code = None
                        if code is None:
                            continue
                        result["findings"].append({
                            "page": page_index + 1, "region": name, "context": context,
                            "code": code, **metrics,
                            "repair_hint": "Inspect this region beside adjacent pages and the target format. If the gap is unintended, repair float sizing/placement, column flow or page/section breaks in the producing source; rebuild affected PDF and requested Word proof, then inspect again. Do not delete valid content or shrink type to game occupancy. If intentional, explain that page-specific reason in existing notes; the signal is not an automatic failure.",
                        })
                except Exception as exc:
                    result["errors"].append(f"Page {page_index + 1} could not be inspected: {exc}")
    except Exception as exc:
        result["errors"].append(f"PDF inspection could not complete: {exc}")
    if not result["errors"]:
        result["status"] = "review_required" if result["findings"] else "no_layout_signals"
    return result


def layout_markdown(result: dict) -> str:
    lines = ["# Direct PDF layout inspection", "", f"- PDF: `{result['pdf']}`",
             f"- SHA-256: `{result['sha256']}`", f"- Diagnostic status: {result['status']}",
             f"- Pages analyzed: {result['pages_analyzed']}/{result['page_count']}",
             "", "## Regions to inspect", ""]
    for item in result["findings"]:
        lines.extend([f"- Page {item['page']}, {item['region']} ({item['context']}): {item['code']}; "
                      f"occupied rows {item['occupied_row_fraction']:.1%}, longest void {item['largest_void_fraction']:.1%}.",
                      f"  {item['repair_hint']}"])
    if not result["findings"]:
        lines.append("- No layout signals recorded; this is not visual approval.")
    lines.extend(["", "## Errors", *[f"- {item}" for item in result["errors"]],
                  "", "## Limits", *[f"- {item}" for item in result["limitations"]], ""])
    return "\n".join(lines)


def _run(command: list[str]) -> tuple[int, str]:
    process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return process.returncode, (process.stdout + process.stderr).strip()


def _resolve_asset(final_dir: Path, raw: str) -> Path | None:
    candidate = (final_dir / raw).resolve()
    if candidate.suffix and candidate.is_file():
        return candidate
    for suffix in (".pdf", ".png", ".jpg", ".jpeg", ".svg"):
        with_suffix = Path(str(candidate) + suffix)
        if with_suffix.is_file():
            return with_suffix
    return None


def figure_inventory(tex_path: Path) -> list[dict]:
    if not tex_path.is_file():
        return []
    text = tex_path.read_text(encoding="utf-8", errors="ignore")
    figures: list[dict] = []
    covered: set[str] = set()
    for index, env in enumerate(FIGURE_ENV_RE.findall(text), 1):
        includes = INCLUDE_RE.findall(env)
        caption_match = CAPTION_RE.search(env)
        label_match = LABEL_RE.search(env)
        for raw in includes:
            asset = _resolve_asset(tex_path.parent, raw)
            asset_key = str(asset) if asset else raw
            covered.add(raw)
            figures.append({
                "figure_id": label_match.group(1) if label_match else f"figure-{index:03d}",
                "asset_raw": raw,
                "asset_path": str(asset) if asset else "",
                "caption": " ".join((caption_match.group(1) if caption_match else "").split()),
                "asset_key": asset_key,
            })
    for raw in INCLUDE_RE.findall(text):
        if raw in covered:
            continue
        asset = _resolve_asset(tex_path.parent, raw)
        figures.append({
            "figure_id": f"unscoped-{len(figures) + 1:03d}",
            "asset_raw": raw,
            "asset_path": str(asset) if asset else "",
            "caption": "",
            "asset_key": str(asset) if asset else raw,
        })
    return figures


def _figure_stories(output_dir: Path) -> dict[str, dict]:
    request_path = output_dir / "figure_requests.json"
    if not request_path.is_file():
        return {}
    try:
        data = json.loads(request_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    stories: dict[str, dict] = {}
    for item in data.get("figures", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        figure_id = str(item.get("figure_id") or "").strip()
        label = str(item.get("label") or f"fig:{figure_id}").strip()
        if label:
            stories[label] = {
                key: item.get(key)
                for key in (
                    "claim",
                    "scientific_question",
                    "intended_conclusion",
                    "claim_boundary",
                    "results_units",
                    "hero_panel",
                    "panels",
                )
                if key in item
            }
    return stories


def _final_background_specs(output_dir: Path) -> dict[str, dict]:
    """Load final-mapping background regions without trusting paths outside the job."""
    request_path = output_dir / "figure_requests.json"
    try:
        data = json.loads(request_path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    specs: dict[str, dict] = {}
    root = output_dir.resolve()
    for item in data.get("figures", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        binding = item.get("final_mapping")
        if not isinstance(binding, dict) or not isinstance(binding.get("path"), str):
            continue
        mapping_path = (output_dir / binding["path"]).resolve()
        if not mapping_path.is_relative_to(root) or not mapping_path.is_file():
            continue
        try:
            mapping = json.loads(mapping_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(mapping, dict) or mapping.get("mapping_sha256") != binding.get("sha256"):
            continue
        unsigned = {key: value for key, value in mapping.items() if key != "mapping_sha256"}
        canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != binding.get("sha256"):
            continue
        background = mapping.get("background")
        if not isinstance(background, dict):
            continue
        figure_id = str(item.get("figure_id") or "").strip()
        label = str(item.get("label") or f"fig:{figure_id}").strip()
        for key in {figure_id, label} - {""}:
            specs[key] = {
                "asset_sha256": background.get("asset_sha256"),
                "declared_probe_render_sha256": background.get("probe_render_sha256"),
                "canvas": background.get("canvas"),
                "axes": background.get("axes", []),
                "panels": background.get("panels", []),
            }
    return specs


def _probe_neutral_background(render_path: Path, spec: dict | None) -> dict:
    """Inspect actual pixels at the canvas and declared region edges.

    Semantic marks may cross a boundary, so a narrow edge band may contain up
    to three percent non-background pixels. Every accepted background pixel is
    still exact: alpha zero or RGB 255/255/255 by default. A region may instead
    declare a justified, exact nonwhite design color. This checks pixels against
    that bound design; readability and scientific meaning still need visual review.
    """
    receipt: dict = {
        "probe_version": "paperspine-neutral-background/1.0",
        "render_sha256": sha256(render_path) if render_path.is_file() else "",
        "pixel_buffer_sha256": "",
        "status": "BLOCKED",
        "acceptance_basis": "neutral_default",
        "regions": [],
        "finding": "",
    }
    if not isinstance(spec, dict):
        receipt["finding"] = "final figure mapping has no bound background specification"
        return receipt
    if not render_path.is_file():
        receipt["finding"] = "final figure render is unavailable for pixel probing"
        return receipt
    try:
        from PIL import Image

        with Image.open(render_path) as opened:
            rgba = opened.convert("RGBA")
    except (ImportError, OSError) as exc:
        receipt["finding"] = f"final figure render could not be decoded for pixel probing: {exc}"
        return receipt

    width, height = rgba.size
    receipt["pixel_buffer_sha256"] = hashlib.sha256(rgba.tobytes()).hexdigest()
    raw_regions = [spec.get("canvas"), *spec.get("axes", []), *spec.get("panels", [])]
    regions: list[dict] = []
    for index, raw in enumerate(raw_regions):
        if not isinstance(raw, dict):
            continue
        bbox = raw.get("bbox_normalized")
        if (
            not isinstance(bbox, list)
            or len(bbox) != 4
            or any(not isinstance(value, (int, float)) for value in bbox)
        ):
            regions.append({
                "region_id": str(raw.get("region_id") or f"region-{index}"),
                "bbox_normalized": bbox,
                "status": "BLOCKED",
                "finding": "invalid normalized region",
            })
            continue
        x, y, region_width, region_height = (float(value) for value in bbox)
        left = max(0, min(width - 1, round(x * width)))
        top = max(0, min(height - 1, round(y * height)))
        right = max(left + 1, min(width, round((x + region_width) * width)))
        bottom = max(top + 1, min(height, round((y + region_height) * height)))
        crop = rgba.crop((left, top, right, bottom))
        crop_width, crop_height = crop.size
        band = max(1, round(min(crop_width, crop_height) * 0.025))
        pixels = list(crop.get_flattened_data()) if hasattr(crop, "get_flattened_data") else list(crop.getdata())
        edge: list[tuple[int, int, int, int]] = []
        for py in range(crop_height):
            row = py * crop_width
            for px in range(crop_width):
                if px < band or px >= crop_width - band or py < band or py >= crop_height - band:
                    edge.append(pixels[row + px])
        transparent = sum(1 for red, green, blue, alpha in edge if alpha == 0)
        pure_white = sum(1 for red, green, blue, alpha in edge if alpha > 0 and red == green == blue == 255)
        neutral = transparent + pure_white
        total = len(edge)
        neutral_ratio = neutral / total if total else 0.0
        detected = "pure_white" if pure_white and not transparent else (
            "transparent" if transparent and not pure_white else "mixed_neutral"
        )
        is_canvas = str(raw.get("region_id") or "") == "canvas" or index == 0
        status = "PASS" if neutral_ratio >= 0.97 and (not is_canvas or detected == "pure_white") else "FAIL"
        exception = raw.get("design_exception")
        exception_result: dict = {}
        if exception is not None:
            rgb = exception.get("expected_rgb") if isinstance(exception, dict) else None
            justified = (
                isinstance(exception, dict)
                and exception.get("basis") in {"scientific_encoding", "venue_requirement", "user_preference"}
                and isinstance(exception.get("reason"), str)
                and bool(exception["reason"].strip())
                and isinstance(rgb, list) and len(rgb) == 3
                and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 255 for v in rgb)
                and rgb != [255, 255, 255]
            )
            matching = sum(1 for pixel in edge if justified and tuple(pixel) == (*rgb, 255))
            design_ratio = matching / total if total else 0.0
            status = "PASS" if justified and design_ratio >= 0.97 else "FAIL"
            detected = "declared_nonwhite" if justified and design_ratio >= 0.97 else "design_mismatch"
            exception_result = {
                "design_exception": exception,
                "design_color_ratio": round(design_ratio, 6),
                "acceptance_basis": "justified_design_exception" if justified else "invalid_design_exception",
            }
            receipt["acceptance_basis"] = "region_design_specifications"
        regions.append({
            "region_id": str(raw.get("region_id") or f"region-{index}"),
            "bbox_normalized": bbox,
            "edge_pixel_count": total,
            "exact_neutral_pixel_count": neutral,
            "neutral_ratio": round(neutral_ratio, 6),
            "detected_background": detected,
            "status": status,
            **exception_result,
            "finding": "" if status == "PASS" else "edge band does not match the neutral default or a justified declared nonwhite design",
        })
    receipt["regions"] = regions
    if not regions:
        receipt["finding"] = "no background regions were declared in the final mapping"
    elif all(region.get("status") == "PASS" for region in regions):
        receipt["status"] = "PASS"
    else:
        receipt["status"] = "FAIL"
        receipt["finding"] = "one or more canvas/axes/panel regions failed the declared background probe"
    return receipt


def _render_pdf(pdf_path: Path, prefix: Path, dpi: int, single: bool = False) -> tuple[list[Path], str]:
    renderer = shutil.which("pdftoppm")
    if not renderer:
        return [], "pdftoppm not found"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    command = [renderer, "-png", "-r", str(dpi)]
    if single:
        command.append("-singlefile")
    command.extend([str(pdf_path), str(prefix)])
    rc, output = _run(command)
    if rc != 0:
        return [], output or f"pdftoppm exit {rc}"
    rendered = sorted(prefix.parent.glob(prefix.name + "*.png"))
    return rendered, ""


def _design_exception_is_current(output_dir: Path, figure: dict, render_path: Path) -> bool:
    """Recheck an exception against the signed mapping and actual current pixels."""
    probe = figure.get("background_probe") or {}
    regions = probe.get("regions") or []
    if probe.get("acceptance_basis") != "region_design_specifications" and not any(
        isinstance(region, dict) and "design_exception" in region for region in regions
    ):
        return True
    spec = _final_background_specs(output_dir).get(str(figure.get("figure_id") or ""))
    asset = output_dir / str(figure.get("asset_path") or "")
    if not spec or not asset.is_file() or spec.get("asset_sha256") != sha256(asset):
        return False
    current = _probe_neutral_background(render_path, spec)
    return (
        current.get("status") == "PASS"
        and spec.get("declared_probe_render_sha256") == current.get("pixel_buffer_sha256")
        and current == probe
    )


def _existing_prepare_is_reusable(output_dir: Path, dpi: int) -> bool:
    """Return True only when the complete prepared visual snapshot is exact.

    Reuse preserves completed human/multimodal inspection receipts. Older
    manifests without the new render/story hashes deliberately miss once and
    are rebuilt under the stronger contract.
    """
    manifest_path = output_dir / "visual_audit_manifest.json"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict) or data.get("schema_version") != "1.1":
        return False

    final_dir = output_dir / "final_paper"
    pdf_path = final_dir / "paper.pdf"
    tex_path = final_dir / "main.tex"
    if not pdf_path.is_file() or not tex_path.is_file():
        return False
    renderer = data.get("renderer")
    if not isinstance(renderer, dict) or renderer.get("dpi") != dpi:
        return False
    if data.get("paper_pdf_sha256") != sha256(pdf_path):
        return False
    if data.get("main_tex_sha256") != sha256(tex_path):
        return False
    request_path = output_dir / "figure_requests.json"
    current_request_hash = sha256(request_path) if request_path.is_file() else ""
    if data.get("figure_requests_sha256", "") != current_request_hash:
        return False

    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        return False
    for page in pages:
        if not isinstance(page, dict):
            return False
        render_path = output_dir / str(page.get("render_path") or "")
        if not render_path.is_file() or page.get("render_sha256") != sha256(render_path):
            return False

    inventory = figure_inventory(tex_path)
    figures = data.get("figures")
    if not isinstance(figures, list) or len(figures) != len(inventory):
        return False
    for prepared, current in zip(figures, inventory, strict=True):
        if not isinstance(prepared, dict) or prepared.get("figure_id") != current.get("figure_id"):
            return False
        asset = Path(str(current.get("asset_path") or ""))
        if not asset.is_file() or prepared.get("asset_sha256") != sha256(asset):
            return False
        render_path = output_dir / str(prepared.get("render_path") or "")
        if not render_path.is_file() or prepared.get("render_sha256") != sha256(render_path):
            return False
        probe = prepared.get("background_probe")
        if (
            not isinstance(probe, dict)
            or probe.get("status") != "PASS"
            or probe.get("render_sha256") != sha256(render_path)
        ):
            return False
        if not _design_exception_is_current(output_dir, prepared, render_path):
            return False
    return True


def prepare(output_dir: Path, dpi: int) -> tuple[Path, list[str]]:
    findings: list[str] = []
    manifest_path = output_dir / "visual_audit_manifest.json"
    if _existing_prepare_is_reusable(output_dir, dpi):
        return manifest_path, findings

    final_dir = output_dir / "final_paper"
    pdf_path = final_dir / "paper.pdf"
    tex_path = final_dir / "main.tex"
    audit_dir = output_dir / "visual_audit"
    page_dir = audit_dir / "pages"
    figure_dir = audit_dir / "figures"
    page_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    pages: list[dict] = []
    renderer_status = "pass"
    renderer_note = ""
    box_probe_status = "blocked"
    box_probe_note = "pdfinfo not run"
    if not pdf_path.is_file():
        renderer_status = "blocked"
        renderer_note = "final_paper/paper.pdf does not exist"
        findings.append(renderer_note)
    else:
        pdfinfo = shutil.which("pdfinfo")
        if pdfinfo:
            box_rc, box_output = _run([pdfinfo, "-box", str(pdf_path)])
            box_probe_status = "pass" if box_rc == 0 else "blocked"
            box_probe_note = box_output
            if box_rc != 0:
                findings.append(box_output or f"pdfinfo exit {box_rc}")
        else:
            box_probe_note = "pdfinfo not found"
            findings.append(box_probe_note)
        rendered, error = _render_pdf(pdf_path, page_dir / "page", dpi)
        if error or not rendered:
            renderer_status = "blocked"
            renderer_note = error or "no PDF pages were rendered"
            findings.append(renderer_note)
        for index, path in enumerate(rendered, 1):
            pages.append({
                "page": index,
                "render_path": str(path.relative_to(output_dir)),
                "render_sha256": sha256(path),
                "checks": {name: {"status": "pending", "note": ""} for name in PAGE_CHECKS},
                "status": "pending",
                "issues": [],
            })

    figures: list[dict] = []
    stories = _figure_stories(output_dir)
    background_specs = _final_background_specs(output_dir)
    for index, item in enumerate(figure_inventory(tex_path), 1):
        asset = Path(item["asset_path"]) if item["asset_path"] else None
        render_path = ""
        render_error = ""
        if asset is None or not asset.is_file():
            render_error = f"figure asset not found: {item['asset_raw']}"
        elif asset.suffix.lower() == ".pdf":
            rendered, render_error = _render_pdf(asset, figure_dir / f"figure-{index:03d}", dpi, single=True)
            if rendered:
                render_path = str(rendered[0].relative_to(output_dir))
        elif asset.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            render_path = str(asset.relative_to(output_dir)) if asset.is_relative_to(output_dir) else str(asset)
        elif asset.suffix.lower() == ".svg":
            render_error = "SVG requires a host visual renderer; inspect the asset directly or render it to PNG before validation"
        resolved_render = output_dir / render_path if render_path else Path()
        background_spec = background_specs.get(item["figure_id"])
        background_probe = _probe_neutral_background(resolved_render, background_spec) if render_path else {
            "probe_version": "paperspine-neutral-background/1.0",
            "render_sha256": "",
            "pixel_buffer_sha256": "",
            "status": "BLOCKED",
            "regions": [],
            "finding": "final figure render is unavailable for pixel probing",
        }
        if background_spec and background_spec.get("asset_sha256") != (sha256(asset) if asset and asset.is_file() else ""):
            background_probe["status"] = "FAIL"
            background_probe["finding"] = "final mapping background receipt is not bound to the current publication asset"
        if background_spec and background_spec.get("declared_probe_render_sha256") != background_probe.get("pixel_buffer_sha256"):
            background_probe["status"] = "FAIL"
            background_probe["finding"] = "final mapping background receipt is not bound to this actual decoded pixel buffer"
        figures.append({
            "figure_id": item["figure_id"],
            "asset_path": str(asset.relative_to(output_dir)) if asset and asset.is_relative_to(output_dir) else (str(asset) if asset else ""),
            "asset_sha256": sha256(asset) if asset and asset.is_file() else "",
            "render_path": render_path,
            "render_sha256": sha256(output_dir / render_path) if render_path else "",
            "caption": item["caption"],
            "story_contract": stories.get(item["figure_id"], {}),
            "render_status": "pass" if render_path else "blocked",
            "render_note": render_error,
            "background_probe": background_probe,
            "checks": {name: {"status": "pending", "note": ""} for name in FIGURE_CHECKS},
            "panels": [],
            "status": "pending",
            "issues": [],
        })
        if render_error:
            findings.append(render_error)
        if background_probe.get("status") != "PASS":
            findings.append(f"figure {item['figure_id']} background probe: {background_probe.get('finding')}")

    manifest = {
        "schema_version": "1.1",
        "paper_pdf": str(pdf_path.relative_to(output_dir)) if pdf_path.is_file() else "final_paper/paper.pdf",
        "paper_pdf_sha256": sha256(pdf_path) if pdf_path.is_file() else "",
        "main_tex_sha256": sha256(tex_path) if tex_path.is_file() else "",
        "figure_requests_sha256": sha256(output_dir / "figure_requests.json") if (output_dir / "figure_requests.json").is_file() else "",
        "renderer": {
            "status": renderer_status,
            "note": renderer_note,
            "dpi": dpi,
            "box_probe_status": box_probe_status,
            "box_probe_note": box_probe_note,
        },
        "review": {"reviewer": "", "reviewer_type": "", "reviewed_at": "", "status": "pending"},
        "pages": pages,
        "figures": figures,
        "unresolved_conflicts": [],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path, findings


def _check_receipt(name: str, checks: object, required: tuple[str, ...], findings: list[str]) -> None:
    if not isinstance(checks, dict):
        findings.append(f"{name} checks must be an object")
        return
    for check_name in required:
        value = checks.get(check_name)
        if not isinstance(value, dict) or str(value.get("status", "")).lower() != "pass":
            findings.append(f"{name}.{check_name} is not PASS")


def validate(output_dir: Path) -> VisualResult:
    path = output_dir / "visual_audit_manifest.json"
    findings: list[str] = []
    if not path.is_file():
        return VisualResult(str(path), False, 0, 0, ["visual_audit_manifest.json does not exist; run --prepare after final PDF compilation"])
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return VisualResult(str(path), False, 0, 0, [f"invalid JSON: {exc}"])

    pdf_path = output_dir / str(data.get("paper_pdf") or "final_paper/paper.pdf")
    if not pdf_path.is_file():
        findings.append("bound paper PDF is missing")
    elif sha256(pdf_path) != str(data.get("paper_pdf_sha256") or ""):
        findings.append("paper PDF changed after visual inspection; prepare and inspect again")
    tex_path = output_dir / "final_paper" / "main.tex"
    if tex_path.is_file() and sha256(tex_path) != str(data.get("main_tex_sha256") or ""):
        findings.append("main.tex changed after visual inspection; prepare and inspect again")
    request_path = output_dir / "figure_requests.json"
    current_request_hash = sha256(request_path) if request_path.is_file() else ""
    if current_request_hash != str(data.get("figure_requests_sha256") or ""):
        findings.append("figure_requests.json changed after visual inspection; prepare and inspect again")

    renderer = data.get("renderer", {})
    if not isinstance(renderer, dict) or str(renderer.get("status", "")).lower() != "pass":
        findings.append("full-page PDF rendering did not pass")
    elif str(renderer.get("box_probe_status", "")).lower() != "pass":
        findings.append("PDF MediaBox/CropBox probe did not pass")
    review = data.get("review", {})
    if not isinstance(review, dict) or str(review.get("status", "")).lower() != "pass":
        findings.append("overall visual review receipt is not PASS")
    elif not str(review.get("reviewer", "")).strip() or not str(review.get("reviewed_at", "")).strip():
        findings.append("visual review must record reviewer and reviewed_at")

    pages = data.get("pages", []) if isinstance(data.get("pages"), list) else []
    if not pages:
        findings.append("no rendered PDF pages are recorded")
    for page in pages:
        name = f"page {page.get('page', '?')}"
        render_path = output_dir / str(page.get("render_path") or "")
        if not render_path.is_file():
            findings.append(f"{name} render is missing")
        elif sha256(render_path) != str(page.get("render_sha256") or ""):
            findings.append(f"{name} render hash changed")
        _check_receipt(name, page.get("checks"), PAGE_CHECKS, findings)
        if str(page.get("status", "")).lower() != "pass":
            findings.append(f"{name} overall status is not PASS")
        if page.get("issues"):
            findings.append(f"{name} has unresolved issues")

    figures = data.get("figures", []) if isinstance(data.get("figures"), list) else []
    current_inventory = figure_inventory(tex_path)
    if len(figures) != len(current_inventory):
        findings.append(f"figure coverage mismatch: manifest has {len(figures)}, current TeX has {len(current_inventory)}")
    for figure in figures:
        name = f"figure {figure.get('figure_id', '?')}"
        asset_path = output_dir / str(figure.get("asset_path") or "")
        if not asset_path.is_file():
            findings.append(f"{name} asset is missing")
        elif not asset_path.resolve().is_relative_to(output_dir.resolve()):
            findings.append(f"{name} asset is outside paper_rewriting_output and is not portable")
        elif sha256(asset_path) != str(figure.get("asset_sha256") or ""):
            findings.append(f"{name} asset changed after inspection")
        if str(figure.get("render_status", "")).lower() != "pass":
            findings.append(f"{name} was not rendered for inspection")
        render_path = output_dir / str(figure.get("render_path") or "")
        if not render_path.is_file():
            findings.append(f"{name} inspection render is missing")
        elif not str(figure.get("render_sha256") or ""):
            findings.append(f"{name} inspection render has no hash receipt")
        elif sha256(render_path) != str(figure.get("render_sha256") or ""):
            findings.append(f"{name} inspection render hash changed")
        probe = figure.get("background_probe")
        if not isinstance(probe, dict) or probe.get("status") != "PASS":
            findings.append(f"{name} actual canvas/axes/panel background probe is not PASS")
        elif render_path.is_file() and probe.get("render_sha256") != sha256(render_path):
            findings.append(f"{name} background probe is stale for the current inspection render")
        elif render_path.is_file() and not _design_exception_is_current(output_dir, figure, render_path):
            findings.append(f"{name} design exception is not bound to the current mapping/asset/pixels")
        _check_receipt(name, figure.get("checks"), FIGURE_CHECKS, findings)
        if figure.get("story_contract"):
            panels = figure.get("panels")
            expected_panels = figure["story_contract"].get("panels", [])
            if expected_panels and not panels:
                findings.append(f"{name} has a story contract but no inspected panel receipts")
        if str(figure.get("status", "")).lower() != "pass":
            findings.append(f"{name} overall status is not PASS")
        if figure.get("issues"):
            findings.append(f"{name} has unresolved issues")

    conflicts = data.get("unresolved_conflicts", [])
    if conflicts:
        findings.append(f"{len(conflicts)} unresolved visual/semantic conflict(s) remain")
    return VisualResult(str(path), not findings, len(pages), len(figures), findings)


def to_markdown(result: VisualResult) -> str:
    lines = [
        "# Visual Readiness Check",
        "",
        f"- Manifest: `{result.manifest}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Page receipts checked (not proof of viewing): {result.page_count}",
        f"- Figure receipts checked (not quality approval): {result.figure_count}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in result.findings) if result.findings else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if args.inspect_pdf:
        if args.prepare or args.write:
            raise SystemExit("--inspect-pdf is read-only and cannot be combined with --prepare or --write; redirect stdout to retain diagnostics.")
        result = inspect_pdf_layout(args.inspect_pdf, columns=args.columns)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.markdown or not args.json:
            print(layout_markdown(result))
        return 3 if result["errors"] else 2 if result["findings"] else 0
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prepare_findings: list[str] = []
    if args.prepare:
        _manifest, prepare_findings = prepare(output_dir, args.dpi)
    result = validate(output_dir)
    if prepare_findings:
        result.findings[:0] = prepare_findings
        result.ok = False
    markdown = to_markdown(result)
    if args.write:
        (output_dir / "visual_readiness_check.md").write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
