"""Dual-path blueprint vectorization for FigMirror schematics.

The native path preserves visual geometry (Recraft V3 Vector when configured,
VTracer as an offline fallback). The semantic path remains authoritative for
scientific text, arrows, module IDs, and source-verified dimensions.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from .svg import SVG_NS, XLINK_NS, audit_svg


RECRAFT_ENDPOINT = "https://external.api.recraft.ai/v1/images/vectorize"


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    values = (root.get("viewBox") or "").replace(",", " ").split()
    if len(values) != 4:
        raise ValueError("SVG must have a four-number viewBox")
    box = tuple(float(value) for value in values)
    if box[2] <= 0 or box[3] <= 0:
        raise ValueError("SVG viewBox dimensions must be positive")
    return box  # type: ignore[return-value]


def _recraft_vectorize(blueprint: Path, output: Path, *, prompt: str, strength: float) -> None:
    # Recraft's vectorize endpoint traces an uploaded raster directly. Prompt
    # and strength are retained in this private signature for compatibility
    # with older FigMirror callers, but are intentionally not sent to the API.
    del prompt, strength
    token = os.environ.get("RECRAFT_API_TOKEN")
    if not token:
        raise ValueError("RECRAFT_API_TOKEN is not configured")
    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise ValueError("requests is required for the Recraft backend") from exc
    with blueprint.open("rb") as handle:
        response = requests.post(
            RECRAFT_ENDPOINT,
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (blueprint.name, handle, "image/png")},
            data={
                "response_format": "b64_json",
                "svg_compression": "off",
                "limit_num_shapes": "on",
                "max_num_shapes": "512",
            },
            timeout=180,
        )
    if response.status_code >= 400:
        raise ValueError(f"Recraft vectorization failed with HTTP {response.status_code}: {response.text[:300]}")
    payload = response.json()
    records = payload.get("data")
    record = records[0] if isinstance(records, list) and records else payload.get("image") or payload
    encoded = record.get("b64_json") if isinstance(record, dict) else None
    if encoded:
        output.write_bytes(base64.b64decode(encoded))
        return
    url = record.get("url") if isinstance(record, dict) else None
    if not url or urlparse(str(url)).scheme not in {"http", "https"}:
        raise ValueError("Recraft response did not contain SVG data or a download URL")
    download = requests.get(str(url), timeout=120)
    download.raise_for_status()
    output.write_bytes(download.content)


def _vtracer_vectorize(job: Path, blueprint: Path, output: Path) -> None:
    vendor = job / "vendor" / "vtracer"
    if vendor.is_dir() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    try:
        import vtracer
    except ImportError as exc:
        raise ValueError("VTracer is unavailable; install it in <job>/vendor/vtracer") from exc
    vtracer.convert_image_to_svg_py(
        str(blueprint),
        str(output),
        colormode="color",
        hierarchical="stacked",
        mode="spline",
        filter_speckle=4,
        color_precision=6,
        layer_difference=16,
        corner_threshold=60,
        length_threshold=4.0,
        max_iterations=10,
        splice_threshold=45,
        path_precision=3,
    )


def _ensure_viewbox(path: Path) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    if root.get("viewBox"):
        return
    width_match = re.match(r"[0-9.]+", str(root.get("width") or ""))
    height_match = re.match(r"[0-9.]+", str(root.get("height") or ""))
    if not width_match or not height_match:
        raise ValueError(f"native SVG has neither viewBox nor numeric width/height: {path}")
    root.set("viewBox", f"0 0 {width_match.group(0)} {height_match.group(0)}")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _prefix_ids(root: ET.Element, prefix: str) -> None:
    mapping: dict[str, str] = {}
    for element in root.iter():
        element_id = element.get("id")
        if element_id:
            mapping[element_id] = f"{prefix}{element_id}"
            element.set("id", mapping[element_id])
    for element in root.iter():
        for key, value in tuple(element.attrib.items()):
            rewritten = value
            for old, new in mapping.items():
                rewritten = rewritten.replace(f"url(#{old})", f"url(#{new})")
                if rewritten == f"#{old}":
                    rewritten = f"#{new}"
            if rewritten != value:
                element.set(key, rewritten)


def _build_layered_hybrid(native_svg: Path, semantic_svg: Path, output: Path, metadata: dict[str, Any]) -> None:
    semantic_root = ET.parse(semantic_svg).getroot()
    native_root = ET.parse(native_svg).getroot()
    native_box = _viewbox(native_root)
    semantic_box = _viewbox(semantic_root)
    _prefix_ids(native_root, "native-")
    metadata_node = ET.Element(f"{{{SVG_NS}}}metadata", {"id": "figmirror-dual-path-metadata"})
    metadata_node.text = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
    semantic_root.insert(0, metadata_node)
    native_layer = ET.Element(
        f"{{{SVG_NS}}}g",
        {
            "id": "figmirror-native-visual-layer",
            "style": "display:none",
            "data-editable": "true",
            "data-default-visible": "false",
            "data-purpose": "visual-source-layer; enable only for approved native zones",
        },
    )
    sx = semantic_box[2] / native_box[2]
    sy = semantic_box[3] / native_box[3]
    transform = ET.SubElement(native_layer, f"{{{SVG_NS}}}g", {"transform": f"scale({sx:g} {sy:g})"})
    for child in list(native_root):
        transform.append(copy.deepcopy(child))
    semantic_root.append(native_layer)
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(semantic_root).write(output, encoding="utf-8", xml_declaration=True)


def _render_png(svg: Path, output: Path) -> None:
    try:
        import cairosvg
    except ImportError as exc:  # pragma: no cover
        raise ValueError("CairoSVG is required to preview vectorization outputs") from exc
    cairosvg.svg2png(url=str(svg), write_to=str(output), output_width=1800)


def _render_pdf(svg: Path, output: Path) -> None:
    try:
        import cairosvg
    except ImportError as exc:  # pragma: no cover
        raise ValueError("CairoSVG is required to export hybrid PDF files") from exc
    cairosvg.svg2pdf(url=str(svg), write_to=str(output))


def _fit(image: Any, size: tuple[int, int]) -> Any:
    from PIL import Image

    result = image.convert("RGB")
    result.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(result, ((size[0] - result.width) // 2, (size[1] - result.height) // 2))
    return canvas


def _build_review_sheet(native_png: Path, semantic_png: Path, hybrid_png: Path, output: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    size = (1000, 680)
    paths = (native_png, semantic_png, hybrid_png)
    labels = ("NATIVE VISUAL VECTOR", "SEMANTIC VECTOR", "LAYERED HYBRID")
    images = []
    for path in paths:
        with Image.open(path) as raw:
            images.append(_fit(raw, size))
    gap, header = 18, 66
    sheet = Image.new("RGB", (size[0] * 3 + gap * 4, size[1] + header + gap), "#e9eef0")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=20)
    for index, (label, image) in enumerate(zip(labels, images, strict=True)):
        x = gap + index * (size[0] + gap)
        draw.text((x, 20), label, fill="#18323a", font=font)
        sheet.paste(image, (x, header))
    sheet.save(output, format="PNG", optimize=True)


def build_dual_path_vector(
    job_dir: str | Path,
    figure_id: str,
    candidate_id: str,
    *,
    provider: str = "auto",
    strength: float = 0.18,
) -> dict[str, Any]:
    """Generate native and semantic paths, then package an editable hybrid SVG.

    Native geometry is retained as a hidden source layer until explicit zones
    pass scientific and editability gates. This prevents outlined AI text from
    silently replacing live semantic labels.
    """

    if not 0 <= strength <= 1:
        raise ValueError("strength must be between 0 and 1")
    job = Path(job_dir).resolve()
    candidate = job / "candidates" / figure_id / candidate_id
    manifest_path = candidate / "candidate.json"
    manifest = _read_object(manifest_path)
    blueprint = candidate / Path(str(manifest.get("blueprint") or "blueprint-v3.png")).name
    semantic_svg = candidate / "figure.svg"
    if not blueprint.is_file() or not semantic_svg.is_file():
        raise ValueError("candidate requires both a blueprint image and figure.svg")

    resolved_provider = provider
    if provider == "auto":
        resolved_provider = "recraft" if os.environ.get("RECRAFT_API_TOKEN") else "vtracer"
    if resolved_provider not in {"recraft", "vtracer"}:
        raise ValueError("provider must be auto, recraft, or vtracer")

    native_svg = candidate / "native-vector.svg"
    native_png = candidate / "native-vector.png"
    semantic_png = candidate / "semantic-vector.png"
    hybrid_svg = candidate / "hybrid-vector.svg"
    hybrid_png = candidate / "hybrid-vector.png"
    hybrid_pdf = candidate / "hybrid-vector.pdf"
    review_png = candidate / "dual-path-review.png"
    prompt = (
        "Preserve the blueprint composition, panel hierarchy, module silhouettes, colors, and arrow reading order. "
        "Return clean editable vector geometry. Do not invent scientific labels or dimensions; text will be replaced "
        "from a separate source-verified semantic layer."
    )
    if resolved_provider == "recraft":
        _recraft_vectorize(blueprint, native_svg, prompt=prompt, strength=strength)
    else:
        _vtracer_vectorize(job, blueprint, native_svg)

    _ensure_viewbox(native_svg)

    native_audit = audit_svg(native_svg, allow_raster=False)
    semantic_audit = audit_svg(semantic_svg, allow_raster=False, require_text=True)
    if native_audit.status != "PASS":
        raise ValueError(f"native vector failed SVG audit: {native_audit.failures}")
    if semantic_audit.status != "PASS":
        raise ValueError(f"semantic vector failed SVG audit: {semantic_audit.failures}")

    fusion_metadata = {
        "schema_version": "0.1",
        "provider": resolved_provider,
        "native_layer_default": "hidden",
        "semantic_layer": "authoritative",
        "approved_native_zones": [],
        "reason": "No native zone may replace source-verified text or arrows before module-level approval.",
    }
    _build_layered_hybrid(native_svg, semantic_svg, hybrid_svg, fusion_metadata)
    hybrid_audit = audit_svg(hybrid_svg, allow_raster=False, require_text=True)
    if hybrid_audit.status != "PASS":
        raise ValueError(f"hybrid vector failed SVG audit: {hybrid_audit.failures}")
    _render_png(native_svg, native_png)
    _render_png(semantic_svg, semantic_png)
    _render_png(hybrid_svg, hybrid_png)
    _render_pdf(hybrid_svg, hybrid_pdf)
    _build_review_sheet(native_png, semantic_png, hybrid_png, review_png)

    result = {
        "schema_version": "0.1",
        "status": "PASS",
        "figure_id": figure_id,
        "candidate_id": candidate_id,
        "requested_provider": provider,
        "resolved_provider": resolved_provider,
        "prompt": prompt if resolved_provider == "recraft" else None,
        "strength": strength if resolved_provider == "recraft" else None,
        "native": {
            "svg": native_svg.name,
            "preview": native_png.name,
            "sha256": _sha256(native_svg),
            "audit": native_audit.to_dict(),
            "role": "visual geometry candidate; scientific text is not trusted",
        },
        "semantic": {
            "svg": semantic_svg.name,
            "preview": semantic_png.name,
            "sha256": _sha256(semantic_svg),
            "audit": semantic_audit.to_dict(),
            "role": "source-verified text, arrows, dimensions, and module IDs",
        },
        "hybrid": {
            "svg": hybrid_svg.name,
            "preview": hybrid_png.name,
            "pdf": hybrid_pdf.name,
            "sha256": _sha256(hybrid_svg),
            "audit": hybrid_audit.to_dict(),
            "visible_native_zones": [],
            "selection": "semantic_authoritative_native_retained_as_editable_source_layer",
        },
        "review": review_png.name,
        "gates": {
            "native_has_no_raster": native_audit.raster_image_count == 0,
            "semantic_has_live_text": semantic_audit.text_count > 0,
            "hybrid_has_live_text": hybrid_audit.text_count > 0,
            "native_scientific_semantics": "UNTRUSTED",
            "automatic_promotion": "BLOCKED_UNTIL_MODULE_LEVEL_APPROVAL",
        },
    }
    (candidate / "dual_path_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest["dual_path_manifest"] = "dual_path_manifest.json"
    manifest["native_vector"] = native_svg.name
    manifest["hybrid_vector"] = hybrid_svg.name
    manifest["hybrid_preview"] = hybrid_png.name
    manifest["hybrid_pdf"] = hybrid_pdf.name
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def build_selective_vector_assets(
    job_dir: str | Path,
    figure_id: str,
    candidate_id: str,
    region_manifest: str | Path,
    *,
    provider: str = "auto",
) -> dict[str, Any]:
    """Vectorize only approved organic regions as reusable SVG assets.

    Text, boxes, and connectors remain native FigureSpec primitives. This
    fallback is deliberately asset-only: it writes a suggested FigureSpec
    patch but never mutates semantic IR or promotes a traced label/arrow.
    """

    job = Path(job_dir).resolve()
    candidate = job / "candidates" / figure_id / candidate_id
    region_path = Path(region_manifest)
    if not region_path.is_absolute():
        region_path = candidate / region_path
    regions_payload = _read_object(region_path)
    regions = regions_payload.get("regions")
    maximum_regions = 20
    request_path = candidate / "generation_request.json"
    if request_path.is_file():
        request = _read_object(request_path)
        maximum_regions = int(request.get("architecture_contract", {}).get("selective_vectorization_max_regions", 20))
    if not isinstance(regions, list) or not regions or len(regions) > maximum_regions:
        raise ValueError(f"region manifest requires 1–{maximum_regions} regions")

    source_raw = str(regions_payload.get("source") or "").strip()
    if source_raw:
        source = Path(source_raw)
        if not source.is_absolute():
            source = candidate / source
    else:
        source = next(
            (candidate / name for name in ("blueprint_preview.png", "blueprint.png", "blueprint-v3.png") if (candidate / name).is_file()),
            candidate / "blueprint_preview.png",
        )
    if not source.is_file():
        raise ValueError(f"selective vectorization source image does not exist: {source}")

    resolved_provider = provider
    if provider == "auto":
        resolved_provider = "recraft" if os.environ.get("RECRAFT_API_TOKEN") else "vtracer"
    if resolved_provider not in {"recraft", "vtracer"}:
        raise ValueError("provider must be auto, recraft, or vtracer")

    from PIL import Image

    output_root = candidate / "vector_assets" / "selective"
    output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    assets_patch: list[dict[str, str]] = []
    node_patch: list[dict[str, str]] = []
    used_ids: set[str] = set()
    with Image.open(source) as image:
        image_width, image_height = image.size
        for index, raw_region in enumerate(regions):
            if not isinstance(raw_region, dict):
                raise ValueError(f"regions[{index}] must be an object")
            region_id = re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(raw_region.get("id") or "").strip()).strip("-")
            if not region_id or region_id in used_ids:
                raise ValueError("region ids must be unique, non-empty SVG-safe identifiers")
            used_ids.add(region_id)
            bbox = raw_region.get("bbox")
            if (
                not isinstance(bbox, list)
                or len(bbox) != 4
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in bbox)
            ):
                raise ValueError(f"region {region_id} bbox must be [x, y, width, height]")
            x, y, width, height = (int(round(float(value))) for value in bbox)
            if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > image_width or y + height > image_height:
                raise ValueError(f"region {region_id} bbox lies outside the source image")
            role = str(raw_region.get("role") or "visual_only")
            if role != "visual_only":
                raise ValueError(f"region {region_id} role must remain visual_only")

            region_dir = output_root / region_id
            region_dir.mkdir(parents=True, exist_ok=True)
            crop_path = region_dir / "source-crop.png"
            svg_path = region_dir / f"{region_id}.svg"
            image.crop((x, y, x + width, y + height)).save(crop_path, format="PNG")
            if resolved_provider == "recraft":
                _recraft_vectorize(crop_path, svg_path, prompt="", strength=0.0)
            else:
                _vtracer_vectorize(job, crop_path, svg_path)
            _ensure_viewbox(svg_path)
            svg_audit = audit_svg(svg_path, allow_raster=False)
            if svg_audit.status != "PASS":
                raise ValueError(f"selective vector asset {region_id} failed SVG audit: {svg_audit.failures}")

            relative_svg = svg_path.relative_to(candidate).as_posix()
            label = str(raw_region.get("label") or region_id)
            target_node = str(raw_region.get("target_node") or "").strip()
            assets_patch.append({"id": region_id, "path": relative_svg, "label": label})
            if target_node:
                node_patch.append({"node_id": target_node, "visual_asset": region_id})
            records.append(
                {
                    "id": region_id,
                    "role": role,
                    "bbox": [x, y, width, height],
                    "target_node": target_node or None,
                    "crop": crop_path.relative_to(candidate).as_posix(),
                    "svg": relative_svg,
                    "svg_sha256": _sha256(svg_path),
                    "audit": svg_audit.to_dict(),
                }
            )

    patch = {
        "schema_version": "0.1",
        "instruction": "Merge assets into blueprint_ir.assets and apply node visual_asset mappings only after review.",
        "assets": assets_patch,
        "nodes": node_patch,
    }
    (candidate / "figure_spec_asset_patch.json").write_text(
        json.dumps(patch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    result = {
        "schema_version": "0.1",
        "status": "PASS",
        "figure_id": figure_id,
        "candidate_id": candidate_id,
        "source": str(source.resolve()),
        "source_role": "visual_reference_only",
        "provider": resolved_provider,
        "region_count": len(records),
        "semantic_text_and_connectors_traced": False,
        "assets": records,
        "figure_spec_patch": "figure_spec_asset_patch.json",
    }
    (candidate / "selective_vector_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result
