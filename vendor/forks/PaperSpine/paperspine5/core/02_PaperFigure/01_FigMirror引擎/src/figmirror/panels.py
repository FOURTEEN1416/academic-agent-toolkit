"""Export semantic figure panels to editable SVG, PNG, and PDF."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .svg import SVG_NS, audit_svg

SUPPORTED_FORMATS = {"svg", "png", "pdf"}


def _read_manifest(value: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    path = Path(value)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid panel manifest JSON in {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("panel manifest root must be an object")
    return manifest


def _viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    raw = (root.get("viewBox") or "").replace(",", " ").split()
    if len(raw) != 4:
        raise ValueError("source SVG must have a four-number viewBox")
    try:
        x, y, width, height = (float(item) for item in raw)
    except ValueError as exc:
        raise ValueError("source SVG viewBox contains non-numeric values") from exc
    if width <= 0 or height <= 0:
        raise ValueError("source SVG viewBox width and height must be positive")
    return x, y, width, height


def _bbox(panel: dict[str, Any], source_box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    raw = panel.get("bbox")
    if not isinstance(raw, list) or len(raw) != 4:
        raise ValueError(f"panel {panel.get('panel_id')} bbox must be [x, y, width, height]")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in raw):
        raise ValueError(f"panel {panel.get('panel_id')} bbox must contain only numbers")
    x, y, width, height = (float(item) for item in raw)
    if width <= 0 or height <= 0:
        raise ValueError(f"panel {panel.get('panel_id')} bbox width and height must be positive")
    source_x, source_y, source_width, source_height = source_box
    tolerance = 1e-6
    if (
        x < source_x - tolerance
        or y < source_y - tolerance
        or x + width > source_x + source_width + tolerance
        or y + height > source_y + source_height + tolerance
    ):
        raise ValueError(f"panel {panel.get('panel_id')} bbox extends outside the source SVG viewBox")
    return x, y, width, height


def _panel_svg(root: ET.Element, panel: dict[str, Any], box: tuple[float, float, float, float]) -> bytes:
    panel_root = copy.deepcopy(root)
    x, y, width, height = box
    panel_id = str(panel["panel_id"])
    panel_root.set("viewBox", f"{x:g} {y:g} {width:g} {height:g}")
    panel_root.set("width", f"{width:g}")
    panel_root.set("height", f"{height:g}")
    panel_root.set("data-figmirror-panel-id", panel_id)
    title = ET.Element(f"{{{SVG_NS}}}title", {"id": f"{panel_id}-title"})
    title.text = str(panel.get("label") or panel_id)
    panel_root.insert(0, title)
    panel_root.set("aria-labelledby", f"{panel_id}-title")
    return ET.tostring(panel_root, encoding="utf-8", xml_declaration=True)


def export_panels(
    source_svg: str | Path,
    manifest: str | Path | dict[str, Any],
    output_dir: str | Path,
    *,
    formats: Iterable[str] = ("svg", "png", "pdf"),
    dpi: int = 300,
    allow_raster: bool = False,
) -> dict[str, Any]:
    """Crop 2–4 declared panels from one SVG and export consistent formats."""

    source = Path(source_svg)
    source_audit = audit_svg(source, allow_raster=allow_raster)
    if source_audit.status != "PASS":
        raise ValueError(f"source SVG failed editability audit: {source_audit.failures}")
    root = ET.parse(source).getroot()
    source_box = _viewbox(root)
    panel_manifest = _read_manifest(manifest)
    panels = panel_manifest.get("panels")
    if not isinstance(panels, list) or not 2 <= len(panels) <= 4:
        raise ValueError("panel manifest must contain between 2 and 4 panels")

    requested_formats = tuple(dict.fromkeys(str(item).lower() for item in formats))
    unsupported = set(requested_formats) - SUPPORTED_FORMATS
    if unsupported:
        raise ValueError(f"unsupported panel export format(s): {sorted(unsupported)}")
    if not requested_formats:
        raise ValueError("at least one panel export format is required")
    if dpi <= 0:
        raise ValueError("dpi must be positive")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for raw_panel in panels:
        if not isinstance(raw_panel, dict):
            raise ValueError("each panel manifest entry must be an object")
        panel_id = str(raw_panel.get("panel_id") or "").strip()
        if not panel_id:
            raise ValueError("each panel requires panel_id")
        if panel_id in seen:
            raise ValueError(f"duplicate panel_id: {panel_id}")
        seen.add(panel_id)
        box = _bbox(raw_panel, source_box)
        svg_bytes = _panel_svg(root, raw_panel, box)
        exports: dict[str, str] = {}
        svg_path = output / f"{panel_id}.svg"
        if "svg" in requested_formats or {"png", "pdf"} & set(requested_formats):
            svg_path.write_bytes(svg_bytes)
            svg_audit = audit_svg(svg_path, allow_raster=allow_raster)
            if svg_audit.status != "PASS":
                raise ValueError(f"exported {panel_id} SVG failed audit: {svg_audit.failures}")
            if "svg" in requested_formats:
                exports["svg"] = str(svg_path.resolve())
        if "png" in requested_formats or "pdf" in requested_formats:
            try:
                import cairosvg
            except ImportError as exc:  # pragma: no cover - dependency error depends on host
                raise RuntimeError("CairoSVG is required for PNG/PDF panel exports") from exc
            if "png" in requested_formats:
                png_path = output / f"{panel_id}.png"
                cairosvg.svg2png(bytestring=svg_bytes, write_to=str(png_path), scale=dpi / 96)
                exports["png"] = str(png_path.resolve())
            if "pdf" in requested_formats:
                pdf_path = output / f"{panel_id}.pdf"
                cairosvg.svg2pdf(bytestring=svg_bytes, write_to=str(pdf_path))
                exports["pdf"] = str(pdf_path.resolve())
        records.append(
            {
                "panel_id": panel_id,
                "label": str(raw_panel.get("label") or panel_id),
                "bbox": list(box),
                "exports": exports,
            }
        )

    result = {
        "schema_version": "0.1",
        "status": "PASS",
        "source_svg": str(source.resolve()),
        "panel_count": len(records),
        "panels": records,
    }
    (output / "panel_exports.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
