"""High-resolution raster schematic workflow with optional 2x2 redraw stitching.

The AI-authored layer is deliberately text-free. Scientific labels, arrows,
frames, and aggregate-data callouts remain in an editable JSON annotation
source and are rasterized only at the declared final pixel dimensions.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .data import sha256_file
from .evidence_bridge import materialize_schematic_evidence

RASTER_PIPELINE = "high_resolution_raster"
TILE_IDS = ("TL", "TR", "BL", "BR")


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _write_object(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _record(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _raster_request(candidate: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    request = _read_object(candidate / "generation_request.json")
    architecture = request.get("architecture_contract", {})
    if request.get("figure_kind") != "schematic" or not isinstance(architecture, dict):
        raise ValueError("high-resolution raster preparation requires a schematic generation request")
    if architecture.get("pipeline") != RASTER_PIPELINE:
        raise ValueError("generation_request.json is not configured for high_resolution_raster")
    contract = request.get("raster_contract")
    if not isinstance(contract, dict):
        raise ValueError("generation_request.json requires raster_contract")
    return request, contract


def _resolved_strategy(contract: dict[str, Any]) -> str:
    strategy = str(contract.get("generation_strategy") or "auto")
    if strategy == "auto":
        threshold = int(contract["tile_threshold_px"])
        return "tiled_2x2" if max(int(contract["target_width_px"]), int(contract["target_height_px"])) > threshold else "single_pass"
    return strategy


def _build_tiles(width: int, height: int, overlap_ratio: float) -> list[dict[str, Any]]:
    mid_x = width // 2
    mid_y = height // 2
    overlap_x = max(2, int(round((width / 2) * overlap_ratio)))
    overlap_y = max(2, int(round((height / 2) * overlap_ratio)))
    x_left_end = min(width, mid_x + math.ceil(overlap_x / 2))
    x_right_start = max(0, mid_x - math.floor(overlap_x / 2))
    y_top_end = min(height, mid_y + math.ceil(overlap_y / 2))
    y_bottom_start = max(0, mid_y - math.floor(overlap_y / 2))
    bounds = {
        "TL": [0, 0, x_left_end, y_top_end],
        "TR": [x_right_start, 0, width, y_top_end],
        "BL": [0, y_bottom_start, x_left_end, height],
        "BR": [x_right_start, y_bottom_start, width, height],
    }
    return [
        {
            "tile_id": tile_id,
            "path": f"tiles/{tile_id}.png",
            "bbox": bbox,
            "target_size": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
            "prompt_rule": "Redraw this crop from the locked master composition; preserve boundary objects and generate no text, arrows, labels, or frames.",
        }
        for tile_id, bbox in bounds.items()
    ]


def prepare_raster_schematic(candidate_dir: str | Path) -> dict[str, Any]:
    """Create the deterministic pixel, tiling, annotation, and review plan."""

    candidate = Path(candidate_dir).resolve()
    request, contract = _raster_request(candidate)
    width = int(contract["target_width_px"])
    height = int(contract["target_height_px"])
    intended_width_cm = float(contract["intended_width_cm"])
    effective_ppi = width / (intended_width_cm / 2.54)
    strategy = _resolved_strategy(contract)
    tiles = _build_tiles(width, height, float(contract["tile_overlap_ratio"])) if strategy == "tiled_2x2" else []
    plan = {
        "schema_version": "0.1",
        "status": "READY",
        "pipeline": RASTER_PIPELINE,
        "candidate_id": request.get("candidate_id"),
        "figure_id": request.get("figure_id"),
        "strategy": strategy,
        "target": {
            "width_px": width,
            "height_px": height,
            "intended_width_cm": intended_width_cm,
            "target_ppi": int(contract["target_ppi"]),
            "minimum_ppi": int(contract["minimum_ppi"]),
            "effective_ppi": round(effective_ppi, 2),
        },
        "master_composition": {
            "path": "master_composition.png",
            "required": bool(contract["master_composition_required"]),
            "role": "locked global layout and object-position guide; AI layer must contain no text",
        },
        "tile_policy": {
            "mechanical_split_adds_detail": False,
            "tile_generation_required_before_stitching": strategy == "tiled_2x2",
            "overlap_ratio": float(contract["tile_overlap_ratio"]),
            "render_long_edge_px": int(contract["tile_render_long_edge_px"]),
            "preserve_sources": bool(contract["preserve_tile_sources"]),
            "tiles": tiles,
        },
        "annotation_policy": {
            "source": "annotation_layout.json",
            "resolved_evidence_source": "annotation_layout.evidence.json",
            "programmatic": True,
            "ai_text_prohibited": True,
            "allowed_types": ["text", "box", "arrow", "line", "image"],
            "final_vector_required": False,
        },
        "quality_gates": {
            "maximum_upscale_factor": float(contract["maximum_upscale_factor"]),
            "maximum_overlap_mae": float(contract["maximum_overlap_mae"]),
            "require_visual_seam_review": True,
            "require_ai_text_absence_review": True,
            "require_annotation_legibility_review": True,
        },
        "outputs": ["stitched_base.png", "annotation_layer.png", "figure.png", "figure.tiff", "preview.png"],
    }
    _write_object(candidate / "raster_generation_plan.json", plan)
    annotation_path = candidate / "annotation_layout.json"
    if not annotation_path.is_file():
        _write_object(
            annotation_path,
            {
                "schema_version": "0.1",
                "coordinate_space": "pixels",
                "canvas": {"width": width, "height": height},
                "annotations": [],
                "rule": "All text, arrows, frames, legends, and data callouts are authored here; the AI image layers remain text-free.",
            },
        )
    panel_template = candidate / "panel_manifest.example.json"
    if not panel_template.is_file():
        _write_object(
            panel_template,
            {
                "schema_version": "0.1",
                "coordinate_space": "pixels",
                "panels": [
                    {"panel_id": "P1", "label": "Primary schematic", "bbox": [0, 0, width // 2, height]},
                    {"panel_id": "P2", "label": "Supporting evidence", "bbox": [width // 2, 0, width - width // 2, height]},
                ],
                "instruction": "Copy to panel_manifest.json and replace the example crops with the authored scientific panel regions.",
            },
        )
    return plan


def _open_rgb(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except OSError as exc:
        raise ValueError(f"cannot read raster source {path}: {exc}") from exc


def _upscale_factor(source: Image.Image, target: tuple[int, int]) -> float:
    return max(target[0] / source.width, target[1] / source.height)


def _tile_weight(tile: dict[str, Any], width: int, height: int, overlap_x: int, overlap_y: int) -> np.ndarray:
    x0, y0, x1, y1 = [int(item) for item in tile["bbox"]]
    tile_width = x1 - x0
    tile_height = y1 - y0
    wx = np.ones(tile_width, dtype=np.float32)
    wy = np.ones(tile_height, dtype=np.float32)
    if x0 > 0:
        ramp = min(overlap_x, tile_width)
        wx[:ramp] = np.linspace(0.0, 1.0, ramp, dtype=np.float32)
    if x1 < width:
        ramp = min(overlap_x, tile_width)
        wx[-ramp:] = np.minimum(wx[-ramp:], np.linspace(1.0, 0.0, ramp, dtype=np.float32))
    if y0 > 0:
        ramp = min(overlap_y, tile_height)
        wy[:ramp] = np.linspace(0.0, 1.0, ramp, dtype=np.float32)
    if y1 < height:
        ramp = min(overlap_y, tile_height)
        wy[-ramp:] = np.minimum(wy[-ramp:], np.linspace(1.0, 0.0, ramp, dtype=np.float32))
    return wy[:, None] * wx[None, :]


def _overlap_mae(tiles: list[tuple[dict[str, Any], Image.Image]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, (left_meta, left_image) in enumerate(tiles):
        lx0, ly0, lx1, ly1 = [int(item) for item in left_meta["bbox"]]
        left_array = np.asarray(left_image, dtype=np.float32)
        for right_meta, right_image in tiles[index + 1 :]:
            rx0, ry0, rx1, ry1 = [int(item) for item in right_meta["bbox"]]
            ox0, oy0, ox1, oy1 = max(lx0, rx0), max(ly0, ry0), min(lx1, rx1), min(ly1, ry1)
            if ox1 <= ox0 or oy1 <= oy0:
                continue
            right_array = np.asarray(right_image, dtype=np.float32)
            left_crop = left_array[oy0 - ly0 : oy1 - ly0, ox0 - lx0 : ox1 - lx0]
            right_crop = right_array[oy0 - ry0 : oy1 - ry0, ox0 - rx0 : ox1 - rx0]
            mae = float(np.mean(np.abs(left_crop - right_crop)) / 255.0)
            results.append(
                {
                    "tiles": [left_meta["tile_id"], right_meta["tile_id"]],
                    "overlap_bbox": [ox0, oy0, ox1, oy1],
                    "normalized_mae": round(mae, 6),
                }
            )
    return results


def _stitch_tiles(candidate: Path, plan: dict[str, Any]) -> tuple[Image.Image, list[dict[str, Any]], list[dict[str, Any]]]:
    width = int(plan["target"]["width_px"])
    height = int(plan["target"]["height_px"])
    tile_records: list[dict[str, Any]] = []
    tiles: list[tuple[dict[str, Any], Image.Image]] = []
    maximum_upscale = float(plan["quality_gates"]["maximum_upscale_factor"])
    for tile in plan["tile_policy"]["tiles"]:
        path = candidate / str(tile["path"])
        if not path.is_file():
            raise ValueError(f"tiled_2x2 assembly requires {path}")
        source = _open_rgb(path)
        target = tuple(int(item) for item in tile["target_size"])
        factor = _upscale_factor(source, target)
        resized = source.resize(target, Image.Resampling.LANCZOS)
        tiles.append((tile, resized))
        tile_records.append({**_record(path), "tile_id": tile["tile_id"], "source_size": list(source.size), "target_size": list(target), "upscale_factor": round(factor, 4), "resolution_gate": factor <= maximum_upscale})
    overlap_records = _overlap_mae(tiles)
    overlap_x = max(2, int(round((width / 2) * float(plan["tile_policy"]["overlap_ratio"]))))
    overlap_y = max(2, int(round((height / 2) * float(plan["tile_policy"]["overlap_ratio"]))))
    accumulator = np.zeros((height, width, 3), dtype=np.float32)
    weights = np.zeros((height, width), dtype=np.float32)
    for tile, image in tiles:
        x0, y0, x1, y1 = [int(item) for item in tile["bbox"]]
        weight = _tile_weight(tile, width, height, overlap_x, overlap_y)
        accumulator[y0:y1, x0:x1] += np.asarray(image, dtype=np.float32) * weight[:, :, None]
        weights[y0:y1, x0:x1] += weight
    if np.any(weights <= 0):
        raise ValueError("tile feathering left uncovered pixels")
    stitched = np.clip(accumulator / weights[:, :, None], 0, 255).astype(np.uint8)
    return Image.fromarray(stitched, mode="RGB"), tile_records, overlap_records


def _font(size: int, bold: bool = False, explicit: str | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        explicit,
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for raw in candidates:
        if not raw:
            continue
        try:
            return ImageFont.truetype(raw, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _color(value: Any, default: str) -> str | tuple[int, int, int, int]:
    return str(value) if isinstance(value, str) and value.strip() else default


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: float | None) -> list[str]:
    explicit_lines = text.splitlines() or [""]
    if not max_width:
        return explicit_lines
    lines: list[str] = []
    for paragraph in explicit_lines:
        if not paragraph:
            lines.append("")
            continue
        tokens = paragraph.split(" ") if " " in paragraph else list(paragraph)
        separator = " " if " " in paragraph else ""
        current = ""
        for token in tokens:
            trial = token if not current else f"{current}{separator}{token}"
            if current and draw.textlength(trial, font=font) > max_width:
                lines.append(current)
                current = token
            else:
                current = trial
        lines.append(current)
    return lines


def _scale_value(value: Any, extent: int, normalized: bool) -> float:
    number = float(value)
    return number * extent if normalized else number


def _annotation_text(item: dict[str, Any]) -> str:
    for key in ("text", "label", "detail"):
        value = str(item.get(key) or "")
        if value:
            return value
    return ""


def _render_annotations(candidate: Path, layout: dict[str, Any], width: int, height: int) -> tuple[Image.Image, list[dict[str, Any]], list[str]]:
    annotations = layout.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("annotation_layout.json annotations must be a list")
    ids = [str(item.get("id") or "") for item in annotations if isinstance(item, dict)]
    if any(not item for item in ids) or len(ids) != len(set(ids)) or len(ids) != len(annotations):
        raise ValueError("annotation_layout.json annotations require unique non-empty ids")
    normalized = layout.get("coordinate_space") == "normalized"
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for item in annotations:
        kind = str(item.get("type") or "")
        item_id = str(item["id"])
        bbox: tuple[float, float, float, float] | None = None
        if kind == "text":
            text = _annotation_text(item)
            if not text:
                failures.append(f"{item_id}: text annotation is empty")
                continue
            x = _scale_value(item.get("x", 0), width, normalized)
            y = _scale_value(item.get("y", 0), height, normalized)
            size = int(round(_scale_value(item.get("font_size", 54), height, normalized)))
            font = _font(max(8, size), bool(item.get("bold", False)), str(item.get("font_path") or "") or None)
            max_width = item.get("max_width")
            max_width_px = _scale_value(max_width, width, normalized) if max_width is not None else None
            lines = _wrap_text(draw, text, font, max_width_px)
            spacing = int(item.get("line_spacing", max(4, round(size * 0.22))))
            rendered = "\n".join(lines)
            anchor = str(item.get("anchor") or "la")
            align = str(item.get("align") or "left")
            draw.multiline_text((x, y), rendered, font=font, fill=_color(item.get("color"), "#172027"), spacing=spacing, anchor=anchor, align=align)
            bbox = tuple(float(value) for value in draw.multiline_textbbox((x, y), rendered, font=font, spacing=spacing, anchor=anchor, align=align))
        elif kind == "box":
            x = _scale_value(item.get("x", 0), width, normalized)
            y = _scale_value(item.get("y", 0), height, normalized)
            w = _scale_value(item.get("width", 0), width, normalized)
            h = _scale_value(item.get("height", 0), height, normalized)
            stroke_width = max(1, int(round(_scale_value(item.get("stroke_width", 4), width, normalized))))
            radius = max(0, int(round(_scale_value(item.get("radius", 0), min(width, height), normalized))))
            bbox = (x, y, x + w, y + h)
            draw.rounded_rectangle(bbox, radius=radius, fill=item.get("fill"), outline=_color(item.get("stroke"), "#26343D"), width=stroke_width)
        elif kind in {"arrow", "line"}:
            x1 = _scale_value(item.get("x1", 0), width, normalized)
            y1 = _scale_value(item.get("y1", 0), height, normalized)
            x2 = _scale_value(item.get("x2", 0), width, normalized)
            y2 = _scale_value(item.get("y2", 0), height, normalized)
            stroke_width = max(1, int(round(_scale_value(item.get("stroke_width", 6), width, normalized))))
            color = _color(item.get("stroke"), "#26343D")
            draw.line((x1, y1, x2, y2), fill=color, width=stroke_width)
            head = 0.0
            if kind == "arrow":
                head = _scale_value(item.get("head_size", max(14, stroke_width * 3)), width, normalized)
                angle = math.atan2(y2 - y1, x2 - x1)
                left = (x2 - head * math.cos(angle - math.pi / 6), y2 - head * math.sin(angle - math.pi / 6))
                right = (x2 - head * math.cos(angle + math.pi / 6), y2 - head * math.sin(angle + math.pi / 6))
                draw.polygon([(x2, y2), left, right], fill=color)
            bbox = (min(x1, x2) - head, min(y1, y2) - head, max(x1, x2) + head, max(y1, y2) + head)
        elif kind == "image":
            raw_path = str(item.get("path") or "")
            asset = (candidate / raw_path).resolve()
            try:
                asset.relative_to(candidate)
            except ValueError as exc:
                raise ValueError(f"{item_id}: image annotation must stay inside the candidate directory") from exc
            if not asset.is_file():
                raise ValueError(f"{item_id}: image annotation asset is missing: {raw_path}")
            x = _scale_value(item.get("x", 0), width, normalized)
            y = _scale_value(item.get("y", 0), height, normalized)
            w = int(round(_scale_value(item.get("width", 0), width, normalized)))
            h = int(round(_scale_value(item.get("height", 0), height, normalized)))
            overlay = _open_rgb(asset).resize((w, h), Image.Resampling.LANCZOS).convert("RGBA")
            layer.alpha_composite(overlay, (int(round(x)), int(round(y))))
            bbox = (x, y, x + w, y + h)
        else:
            failures.append(f"{item_id}: unsupported annotation type {kind!r}")
            continue
        if bbox is None:
            continue
        in_bounds = bbox[0] >= 0 and bbox[1] >= 0 and bbox[2] <= width and bbox[3] <= height
        if not in_bounds:
            failures.append(f"{item_id}: annotation bbox is out of bounds")
        records.append({"id": item_id, "type": kind, "bbox": [round(value, 2) for value in bbox], "in_bounds": in_bounds, "text": _annotation_text(item) if kind == "text" else None})
    return layer, records, failures


def _materialize_annotation_evidence(candidate: Path, layout: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    pseudo_spec = {"nodes": deepcopy(layout.get("annotations", []))}
    resolved_spec, evidence = materialize_schematic_evidence(candidate, pseudo_spec)
    resolved = deepcopy(layout)
    resolved["annotations"] = resolved_spec["nodes"]
    if evidence["used"]:
        _write_object(candidate / "annotation_layout.evidence.json", resolved)
    return resolved, evidence


def assemble_raster_schematic(candidate_dir: str | Path) -> dict[str, Any]:
    """Assemble the AI base, optional overlap tiles, and programmatic annotations."""

    candidate = Path(candidate_dir).resolve()
    request, contract = _raster_request(candidate)
    plan_path = candidate / "raster_generation_plan.json"
    plan = _read_object(plan_path) if plan_path.is_file() else prepare_raster_schematic(candidate)
    width = int(plan["target"]["width_px"])
    height = int(plan["target"]["height_px"])
    master_path = candidate / str(plan["master_composition"]["path"])
    if not master_path.is_file():
        raise ValueError(f"master composition is missing: {master_path}")
    master = _open_rgb(master_path)
    strategy = str(plan["strategy"])
    source_records: list[dict[str, Any]] = [{**_record(master_path), "role": "master_composition", "source_size": list(master.size)}]
    overlap_records: list[dict[str, Any]] = []
    if strategy == "tiled_2x2":
        base, tile_records, overlap_records = _stitch_tiles(candidate, plan)
        source_records.extend(tile_records)
        resolution_gate = all(record["resolution_gate"] for record in tile_records)
    else:
        factor = _upscale_factor(master, (width, height))
        base = master.resize((width, height), Image.Resampling.LANCZOS)
        source_records[0]["target_size"] = [width, height]
        source_records[0]["upscale_factor"] = round(factor, 4)
        source_records[0]["resolution_gate"] = factor <= float(contract["maximum_upscale_factor"])
        resolution_gate = bool(source_records[0]["resolution_gate"])
    stitched_path = candidate / "stitched_base.png"
    base.save(stitched_path, format="PNG")

    layout_path = candidate / "annotation_layout.json"
    layout = _read_object(layout_path)
    canvas = layout.get("canvas", {})
    if not isinstance(canvas, dict) or int(canvas.get("width", width)) != width or int(canvas.get("height", height)) != height:
        raise ValueError("annotation_layout.json canvas must match the raster target dimensions")
    resolved_layout, evidence = _materialize_annotation_evidence(candidate, layout)
    annotation_layer, annotations, annotation_failures = _render_annotations(candidate, resolved_layout, width, height)
    annotation_path = candidate / "annotation_layer.png"
    annotation_layer.save(annotation_path, format="PNG")
    final = Image.alpha_composite(base.convert("RGBA"), annotation_layer).convert("RGB")
    effective_ppi = float(plan["target"]["effective_ppi"])
    embedded_ppi = max(1, int(round(effective_ppi)))
    final_png = candidate / "figure.png"
    final_tiff = candidate / "figure.tiff"
    preview = candidate / "preview.png"
    final.save(final_png, format="PNG", dpi=(embedded_ppi, embedded_ppi))
    final.save(final_tiff, format="TIFF", compression="tiff_lzw", dpi=(embedded_ppi, embedded_ppi))
    preview_width = min(1800, width)
    preview_height = max(1, round(height * preview_width / width))
    final.resize((preview_width, preview_height), Image.Resampling.LANCZOS).save(preview, format="PNG")

    maximum_mae = max((item["normalized_mae"] for item in overlap_records), default=0.0)
    seam_gate = maximum_mae <= float(contract["maximum_overlap_mae"])
    hard_gates = {
        "target_dimensions_exact": final.size == (width, height),
        "effective_ppi_at_least_target": effective_ppi >= int(contract["target_ppi"]),
        "effective_ppi_at_least_minimum": effective_ppi >= int(contract["minimum_ppi"]),
        "source_resolution_sufficient": resolution_gate,
        "tile_overlap_consistent": seam_gate,
        "annotation_source_retained": layout_path.is_file(),
        "programmatic_annotations_in_bounds": not annotation_failures,
        "ai_text_prohibited_by_contract": bool(contract["ai_text_prohibited"]),
        "final_vector_not_required": request.get("authoring_contract", {}).get("final_vector_required") is False,
    }
    status = "PASS" if all(hard_gates.values()) else "FAIL"
    qa = {
        "schema_version": "0.1",
        "status": status,
        "pipeline": RASTER_PIPELINE,
        "strategy": strategy,
        "target": plan["target"],
        "actual": {"width_px": final.width, "height_px": final.height, "embedded_ppi": embedded_ppi},
        "source_records": source_records,
        "tile_overlap_comparisons": overlap_records,
        "maximum_overlap_mae": maximum_mae,
        "annotation_records": annotations,
        "annotation_failures": annotation_failures,
        "aggregate_data_evidence": evidence,
        "hard_gates": hard_gates,
        "visual_review_required": ["AI layers contain no text", "no visible seams", "annotations are legible", "reference layout grammar is preserved without copying content"],
    }
    _write_object(candidate / "raster_qa.json", qa)

    references = request.get("reference_contract", {}).get("assets", [])
    lineage_references = [record for record in references if isinstance(record, dict) and record.get("status") == "available"]
    lineage = {
        "schema_version": "0.1",
        "pipeline": RASTER_PIPELINE,
        "candidate_id": request.get("candidate_id"),
        "artifact_chain": ["reference", "master_composition", "tile_refinement", "programmatic_annotations", "raster_final"],
        "reference": lineage_references[0] if lineage_references else None,
        "references": lineage_references,
        "master_composition": _record(master_path),
        "tile_refinement": {"strategy": strategy, "assets": [record for record in source_records if record.get("tile_id")], "stitched_base": _record(stitched_path)},
        "programmatic_annotations": {"source": _record(layout_path), "resolved_source": _record(candidate / "annotation_layout.evidence.json") if (candidate / "annotation_layout.evidence.json").is_file() else None, "layer": _record(annotation_path), "count": len(annotations)},
        "raster_final": {"png": _record(final_png), "tiff": _record(final_tiff), "preview": _record(preview)},
        "ai_text_prohibited": True,
        "programmatic_annotations_required": True,
        "vector_final_required": False,
        "prior_blueprint_image_input": False,
    }
    _write_object(candidate / "lineage_raster_v1.json", lineage)
    manifest = {
        "schema_version": "0.1",
        "status": status,
        "pipeline": RASTER_PIPELINE,
        "strategy": strategy,
        "final": {"png": _record(final_png), "tiff": _record(final_tiff), "preview": _record(preview)},
        "annotation_source": layout_path.name,
        "annotation_count": len(annotations),
        "aggregate_data_evidence": evidence,
        "effective_ppi": effective_ppi,
        "hard_gates": hard_gates,
        "lineage": "lineage_raster_v1.json",
    }
    _write_object(candidate / "raster_schematic_manifest.json", manifest)
    feedback_request = {
        "schema_version": "0.1",
        "task": "review_high_resolution_raster_schematic",
        "reference_assets": references,
        "master_composition": str(master_path),
        "tile_assets": [record["path"] for record in source_records if record.get("tile_id")],
        "stitched_base": str(stitched_path),
        "annotation_layer": str(annotation_path),
        "final": str(final_png),
        "checks": ["scientific structure", "reference layout grammar", "AI text absence", "tile seams", "annotation legibility", "object consistency", "page-view hierarchy"],
        "instruction": "Review at page scale and 100% detail. Do not approve until AI layers contain no text and no tile boundary is visible.",
    }
    _write_object(candidate / "raster_visual_feedback_request.json", feedback_request)
    review_path = candidate / "raster_visual_feedback_review.json"
    if not review_path.is_file():
        _write_object(
            review_path,
            {
                "schema_version": "0.1",
                "status": "PENDING",
                "ai_text_absent": None,
                "seams_clean": None,
                "annotations_legible": None,
                "scientific_structure_preserved": None,
                "rounds": [],
            },
        )
    return manifest


def _save_pdf(image: Image.Image, path: Path, ppi: int) -> None:
    image.convert("RGB").save(path, format="PDF", resolution=ppi)


def export_raster_panels(candidate: Path, image: Image.Image, formats: Iterable[str], ppi: int) -> dict[str, Any]:
    manifest_path = candidate / "panel_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("raster candidate requires panel_manifest.json; use panel_manifest.example.json as a starting point")
    manifest = _read_object(manifest_path)
    panels = manifest.get("panels")
    if not isinstance(panels, list) or not 2 <= len(panels) <= 4:
        raise ValueError("panel_manifest.json must declare 2-4 raster panels")
    output = candidate / "panels"
    output.mkdir(exist_ok=True)
    records: list[dict[str, Any]] = []
    wanted = set(formats)
    for panel in panels:
        if not isinstance(panel, dict) or not str(panel.get("panel_id") or ""):
            raise ValueError("every raster panel requires panel_id")
        panel_id = str(panel["panel_id"])
        bbox = panel.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"raster panel {panel_id} requires bbox=[x,y,width,height]")
        x, y, width, height = [int(round(float(value))) for value in bbox]
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > image.width or y + height > image.height:
            raise ValueError(f"raster panel {panel_id} bbox is outside the final image")
        crop = image.crop((x, y, x + width, y + height))
        paths: dict[str, str] = {}
        png = output / f"{panel_id}.png"
        crop.save(png, format="PNG", dpi=(ppi, ppi))
        paths["png"] = str(png.resolve())
        if "tiff" in wanted:
            tiff = output / f"{panel_id}.tiff"
            crop.save(tiff, format="TIFF", compression="tiff_lzw", dpi=(ppi, ppi))
            paths["tiff"] = str(tiff.resolve())
        if "pdf" in wanted:
            pdf = output / f"{panel_id}.pdf"
            _save_pdf(crop, pdf, ppi)
            paths["pdf"] = str(pdf.resolve())
        records.append({"panel_id": panel_id, "label": str(panel.get("label") or panel_id), "bbox": [x, y, width, height], "exports": paths})
    result = {"schema_version": "0.1", "status": "PASS", "source_raster": str((candidate / "figure.png").resolve()), "panels": records}
    _write_object(output / "panel_exports.json", result)
    return result


def finalize_raster_candidate(
    candidate_dir: str | Path,
    request: dict[str, Any],
    process_paths: list[Path],
    *,
    formats: Iterable[str],
) -> dict[str, Any]:
    candidate = Path(candidate_dir).resolve()
    wanted = tuple(dict.fromkeys(str(item).lower() for item in formats))
    if not wanted or set(wanted) - {"png", "tiff", "pdf"}:
        raise ValueError("high_resolution_raster formats must be a non-empty subset of png,tiff,pdf")
    manifest = _read_object(candidate / "raster_schematic_manifest.json")
    qa = _read_object(candidate / "raster_qa.json")
    review = _read_object(candidate / "raster_visual_feedback_review.json")
    if manifest.get("status") != "PASS" or qa.get("status") != "PASS":
        raise ValueError("raster schematic machine QA has not passed")
    required_review = ("ai_text_absent", "seams_clean", "annotations_legible", "scientific_structure_preserved")
    if str(review.get("status") or "").upper() != "PASS" or any(review.get(key) is not True for key in required_review):
        raise ValueError("raster_visual_feedback_review.json must pass AI-text, seam, annotation, and scientific-structure checks")
    if not isinstance(review.get("rounds"), list) or not review["rounds"]:
        raise ValueError("raster_visual_feedback_review.json requires at least one completed review round")
    final_png = candidate / "figure.png"
    if not final_png.is_file() or manifest.get("final", {}).get("png", {}).get("sha256") != sha256_file(final_png):
        raise ValueError("final raster PNG is missing or changed after assembly")
    image = _open_rgb(final_png)
    ppi = max(1, int(round(float(manifest["effective_ppi"]))))
    exports: dict[str, str] = {}
    if "png" in wanted:
        exports["png"] = str(final_png.resolve())
    if "tiff" in wanted:
        tiff = candidate / "figure.tiff"
        if not tiff.is_file():
            image.save(tiff, format="TIFF", compression="tiff_lzw", dpi=(ppi, ppi))
        exports["tiff"] = str(tiff.resolve())
    if "pdf" in wanted:
        pdf = candidate / "figure.pdf"
        _save_pdf(image, pdf, ppi)
        exports["pdf"] = str(pdf.resolve())
    panels = export_raster_panels(candidate, image, wanted, ppi)
    lineage = _read_object(candidate / "lineage_raster_v1.json")
    source_paths = [
        candidate / "raster_generation_plan.json",
        candidate / "annotation_layout.json",
        candidate / "stitched_base.png",
        candidate / "annotation_layer.png",
        candidate / "lineage_raster_v1.json",
        *process_paths,
    ]
    if (candidate / "annotation_layout.evidence.json").is_file():
        source_paths.append(candidate / "annotation_layout.evidence.json")
    source_paths.extend(Path(record["path"]) for record in qa.get("source_records", []) if isinstance(record, dict) and record.get("path"))
    unique_sources = list(dict.fromkeys(path.resolve() for path in source_paths if path.is_file()))
    result = {
        "schema_version": "0.4",
        "status": "PASS",
        "candidate_id": request.get("candidate_id"),
        "figure_id": request.get("figure_id"),
        "figure_kind": "schematic",
        "generation_mode": "agent_native",
        "rendering_mode": "high-resolution-raster",
        "source_records": [_record(path) for path in unique_sources],
        "raster_qa": qa,
        "data_evidence": manifest.get("aggregate_data_evidence"),
        "exports": exports,
        "panels": panels,
        "lineage": "lineage_raster_v1.json",
        "vector_final_required": False,
        "editable_source": "annotation_layout.json",
        "next_gate": "candidate.json scoring and configured human selection",
    }
    _write_object(candidate / "authoring_report.json", result)
    if lineage.get("vector_final_required") is not False:
        raise ValueError("raster lineage must explicitly disable vector-final requirements")
    return result
