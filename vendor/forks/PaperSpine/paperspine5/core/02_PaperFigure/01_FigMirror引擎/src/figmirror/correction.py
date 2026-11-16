"""Execute PaperSpine-authorized, mask-bounded figure corrections.

FigMirror is deliberately an executor here.  It accepts no free-form prompt and
does not decide which scientific label may change.
"""

from __future__ import annotations

import hashlib
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: dict[str, Any]) -> str:
    return _sha_bytes(
        (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
    )


def _element_by_id(root: ET.Element, element_id: str) -> ET.Element:
    matches = [item for item in root.iter() if item.attrib.get("id") == element_id]
    if len(matches) != 1:
        raise ValueError(f"SVG element id must resolve exactly once: {element_id}")
    return matches[0]


def _view_box(root: ET.Element) -> tuple[float, float, float, float]:
    raw = root.attrib.get("viewBox")
    if not isinstance(raw, str):
        raise ValueError("SVG correction requires a numeric viewBox")
    try:
        values = tuple(float(item) for item in raw.replace(",", " ").split())
    except ValueError as exc:
        raise ValueError("SVG viewBox is invalid") from exc
    if len(values) != 4 or values[2] <= 0 or values[3] <= 0:
        raise ValueError("SVG viewBox must contain positive width and height")
    return values


def _render(svg_bytes: bytes, width: int):
    try:
        import cairosvg
        import numpy as np
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - runtime dependency gate.
        raise RuntimeError("SVG correction requires CairoSVG, Pillow, and NumPy") from exc
    png = cairosvg.svg2png(bytestring=svg_bytes, output_width=width)
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    return np.asarray(image)


def _render_pdf(pdf_bytes: bytes, width: int):
    try:
        import fitz
        import numpy as np
    except ImportError as exc:  # pragma: no cover - runtime dependency gate.
        raise RuntimeError("PDF correction requires PyMuPDF and NumPy") from exc
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if document.page_count != 1:
            raise ValueError("PDF correction supports exactly one figure page")
        page = document[0]
        scale = width / float(page.rect.width)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=True)
        array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        if pixmap.n == 3:
            alpha = np.full((pixmap.height, pixmap.width, 1), 255, dtype=np.uint8)
            array = np.concatenate((array, alpha), axis=2)
        return array.copy(), (0.0, 0.0, float(page.rect.width), float(page.rect.height))
    finally:
        document.close()


def _render_artifact(value: bytes, media_type: str, width: int):
    if media_type == "image/svg+xml":
        root = ET.fromstring(value)
        return _render(value, width), _view_box(root)
    if media_type == "application/pdf":
        return _render_pdf(value, width)
    raise ValueError(f"unsupported correction media type: {media_type}")


def _pixel_diff(
    source_bytes: bytes,
    output_bytes: bytes,
    root: ET.Element,
    changes: list[dict[str, Any]],
    bounds: dict[str, Any],
) -> dict[str, Any]:
    import numpy as np

    width = int(bounds["render_width_px"])
    before = _render(source_bytes, width)
    after = _render(output_bytes, width)
    if before.shape != after.shape:
        raise ValueError("correction changed the rendered canvas size")
    changed = np.any(before != after, axis=2)
    mask = np.zeros(changed.shape, dtype=bool)
    min_x, min_y, box_width, box_height = _view_box(root)
    scale_x = changed.shape[1] / box_width
    scale_y = changed.shape[0] / box_height
    for change in changes:
        region = change["region"]
        # Vector mask edges can antialias across the immediately adjacent
        # raster pixel.  Include exactly that one boundary pixel; all farther
        # changes remain outside the PaperSpine-authorized physical region.
        left = max(0, int((float(region["x"]) - min_x) * scale_x) - 1)
        top = max(0, int((float(region["y"]) - min_y) * scale_y) - 1)
        right = min(
            changed.shape[1],
            int((float(region["x"]) + float(region["width"]) - min_x) * scale_x + 1),
        )
        bottom = min(
            changed.shape[0],
            int((float(region["y"]) + float(region["height"]) - min_y) * scale_y + 1),
        )
        if left >= right or top >= bottom:
            raise ValueError(f"correction mask is empty: {change['change_id']}")
        mask[top:bottom, left:right] = True
    changed_count = int(changed.sum())
    outside = changed & ~mask
    outside_count = int(outside.sum())
    fraction = changed_count / float(changed.size)
    within = (
        fraction <= float(bounds["maximum_changed_pixel_fraction"])
        and outside_count <= int(bounds["maximum_outside_mask_changed_pixels"])
    )
    return {
        "render_width_px": int(changed.shape[1]),
        "render_height_px": int(changed.shape[0]),
        "changed_pixels": changed_count,
        "changed_pixel_fraction": fraction,
        "outside_mask_changed_pixels": outside_count,
        "within_bounds": within,
    }


def _pixel_diff_artifacts(
    source_bytes: bytes,
    output_bytes: bytes,
    *,
    media_type: str,
    changes: list[dict[str, Any]],
    bounds: dict[str, Any],
) -> tuple[dict[str, Any], Any, Any, tuple[float, float, float, float]]:
    import numpy as np

    width = int(bounds["render_width_px"])
    before, canvas = _render_artifact(source_bytes, media_type, width)
    after, output_canvas = _render_artifact(output_bytes, media_type, width)
    if before.shape != after.shape or canvas != output_canvas:
        raise ValueError("correction changed the rendered canvas size")
    changed = np.any(before != after, axis=2)
    mask = np.zeros(changed.shape, dtype=bool)
    min_x, min_y, box_width, box_height = canvas
    scale_x = changed.shape[1] / box_width
    scale_y = changed.shape[0] / box_height
    for change in changes:
        region = change["region"]
        # Match the vector renderer's one-pixel antialias boundary without
        # turning the physical region into a free-form tolerance band.
        left = max(0, int((float(region["x"]) - min_x) * scale_x) - 1)
        top = max(0, int((float(region["y"]) - min_y) * scale_y) - 1)
        right = min(
            changed.shape[1],
            int((float(region["x"]) + float(region["width"]) - min_x) * scale_x + 1),
        )
        bottom = min(
            changed.shape[0],
            int((float(region["y"]) + float(region["height"]) - min_y) * scale_y + 1),
        )
        if left >= right or top >= bottom:
            raise ValueError(f"correction mask is empty: {change['change_id']}")
        mask[top:bottom, left:right] = True
    changed_count = int(changed.sum())
    outside = changed & ~mask
    outside_count = int(outside.sum())
    fraction = changed_count / float(changed.size)
    within = (
        fraction <= float(bounds["maximum_changed_pixel_fraction"])
        and outside_count <= int(bounds["maximum_outside_mask_changed_pixels"])
    )
    diff_receipt = {
        "render_width_px": int(changed.shape[1]),
        "render_height_px": int(changed.shape[0]),
        "changed_pixels": changed_count,
        "changed_pixel_fraction": fraction,
        "outside_mask_changed_pixels": outside_count,
        "within_bounds": within,
    }
    if outside_count:
        coordinates = np.argwhere(outside)
        diff_receipt["outside_mask_render_bounds"] = {
            "left": int(coordinates[:, 1].min()),
            "top": int(coordinates[:, 0].min()),
            "right": int(coordinates[:, 1].max()),
            "bottom": int(coordinates[:, 0].max()),
        }
        by_change: dict[str, dict[str, int]] = {}
        region_bounds = []
        for change in changes:
            region = change["region"]
            region_bounds.append(
                (
                    str(change["change_id"]),
                    (float(region["x"]) - min_x) * scale_x,
                    (float(region["y"]) - min_y) * scale_y,
                    (float(region["x"]) + float(region["width"]) - min_x)
                    * scale_x,
                    (float(region["y"]) + float(region["height"]) - min_y)
                    * scale_y,
                )
            )
        for row, column in coordinates:
            nearest = min(
                region_bounds,
                key=lambda item: (
                    max(item[1] - column, 0, column - item[3]) ** 2
                    + max(item[2] - row, 0, row - item[4]) ** 2
                ),
            )[0]
            summary = by_change.setdefault(
                nearest,
                {
                    "count": 0,
                    "left": int(column),
                    "top": int(row),
                    "right": int(column),
                    "bottom": int(row),
                },
            )
            summary["count"] += 1
            summary["left"] = min(summary["left"], int(column))
            summary["top"] = min(summary["top"], int(row))
            summary["right"] = max(summary["right"], int(column))
            summary["bottom"] = max(summary["bottom"], int(row))
        diff_receipt["outside_mask_by_change"] = by_change
    return (
        diff_receipt,
        before,
        after,
        canvas,
    )


def _region_pixels_sha256(
    image: Any,
    canvas: tuple[float, float, float, float],
    region: dict[str, Any],
) -> str:
    min_x, min_y, box_width, box_height = canvas
    scale_x = image.shape[1] / box_width
    scale_y = image.shape[0] / box_height
    left = max(0, int((float(region["x"]) - min_x) * scale_x))
    top = max(0, int((float(region["y"]) - min_y) * scale_y))
    right = min(
        image.shape[1],
        int((float(region["x"]) + float(region["width"]) - min_x) * scale_x + 1),
    )
    bottom = min(
        image.shape[0],
        int((float(region["y"]) + float(region["height"]) - min_y) * scale_y + 1),
    )
    if left >= right or top >= bottom:
        raise ValueError("render invariant region is empty")
    return _sha_bytes(image[top:bottom, left:right].tobytes())


def _compose_pdf_overlay(source_bytes: bytes, overlay_bytes: bytes, overlay_type: str) -> bytes:
    try:
        import cairosvg
        from pypdf import PdfReader, PdfWriter, Transformation
    except ImportError as exc:  # pragma: no cover - runtime dependency gate.
        raise RuntimeError("PDF overlay correction requires CairoSVG and pypdf") from exc
    if overlay_type == "image/svg+xml":
        overlay_pdf = cairosvg.svg2pdf(bytestring=overlay_bytes)
    elif overlay_type == "application/pdf":
        overlay_pdf = overlay_bytes
    else:
        raise ValueError("PDF overlay must be SVG or PDF")
    source_reader = PdfReader(io.BytesIO(source_bytes))
    overlay_reader = PdfReader(io.BytesIO(overlay_pdf))
    if len(source_reader.pages) != 1 or len(overlay_reader.pages) != 1:
        raise ValueError("PDF overlay correction supports exactly one source and overlay page")
    source_page = source_reader.pages[0]
    overlay_page = overlay_reader.pages[0]
    source_width = float(source_page.mediabox.width)
    source_height = float(source_page.mediabox.height)
    overlay_width = float(overlay_page.mediabox.width)
    overlay_height = float(overlay_page.mediabox.height)
    if min(source_width, source_height, overlay_width, overlay_height) <= 0:
        raise ValueError("PDF source/overlay page size is invalid")
    source_page.merge_transformed_page(
        overlay_page,
        Transformation().scale(
            source_width / overlay_width,
            source_height / overlay_height,
        ),
        over=True,
    )
    writer = PdfWriter()
    writer.add_page(source_page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _validate_pdf_overlay(
    overlay_bytes: bytes, changes: list[dict[str, Any]]
) -> None:
    root = ET.fromstring(overlay_bytes)
    visible_text = [
        item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "text"
    ]
    if len(visible_text) != len(changes):
        raise ValueError("PDF overlay must contain exactly one text element per change")
    expected_text_ids = {str(item["element_id"]) for item in changes}
    observed_text_ids = {str(item.attrib.get("id") or "") for item in visible_text}
    if observed_text_ids != expected_text_ids:
        raise ValueError("PDF overlay text element IDs differ from the authorized changes")
    expected_mask_ids = {str(item.get("mask_element_id") or "") for item in changes}
    observed_mask_ids = {
        str(item.attrib.get("id") or "")
        for item in root.iter()
        if item.tag.rsplit("}", 1)[-1] == "rect"
    }
    if "" in expected_mask_ids or observed_mask_ids != expected_mask_ids:
        raise ValueError("PDF overlay mask element IDs differ from the authorized regions")
    for change in changes:
        element = _element_by_id(root, str(change["element_id"]))
        text = "".join(element.itertext())
        source_token = str(change["from_token"])
        target_token = str(change["to_token"])
        if text.count(target_token) != 1 or source_token in text:
            raise ValueError(
                f"PDF overlay token content differs from the authorized replacement: {change['element_id']}"
            )
        text_spec = change["overlay_text"]
        if (
            element.attrib.get("x") != "0"
            or element.attrib.get("y") != "0"
            or abs(float(element.attrib.get("font-size", "nan")) - float(text_spec["font_size"])) > 1e-6
            or abs(
                float(element.attrib.get("data-paperspine-anchor-x", "nan"))
                - float(text_spec["x"])
            )
            > 1e-6
            or abs(
                float(element.attrib.get("data-paperspine-anchor-y", "nan"))
                - float(text_spec["y"])
            )
            > 1e-6
        ):
            raise ValueError(
                f"PDF overlay text placement differs from the authorized operation: {change['change_id']}"
            )
        horizontal_scale = float(
            element.attrib.get("data-paperspine-horizontal-scale", "nan")
        )
        if not 0 < horizontal_scale <= 1:
            raise ValueError(
                f"PDF overlay text scale is invalid: {change['change_id']}"
            )
        if (
            element.attrib.get("font-family") != str(text_spec["font_family"])
            or element.attrib.get("fill") != str(text_spec["fill"])
        ):
            raise ValueError(
                f"PDF overlay text styling differs from the authorized operation: {change['change_id']}"
            )
        rotation = float(text_spec["rotation_degrees"])
        expected_transform = (
            f"translate({float(text_spec['x']):g} {float(text_spec['y']):g}) "
            + (f"rotate({rotation:g}) " if rotation else "")
            + f"scale({horizontal_scale:.9f} 1)"
        )
        if element.attrib.get("transform") != expected_transform:
            raise ValueError(
                f"PDF overlay text rotation differs from the authorized operation: {change['change_id']}"
            )
        mask = _element_by_id(root, str(change["mask_element_id"]))
        region = change["region"]
        for field in ("x", "y", "width", "height"):
            if abs(float(mask.attrib[field]) - float(region[field])) > 0.2:
                raise ValueError(
                    f"PDF overlay mask geometry differs from the authorized region: {change['change_id']}"
                )


def apply_figure_correction(
    operation: dict[str, Any], output_path: str | Path
) -> dict[str, Any]:
    """Apply only the exact SVG or PDF-overlay change authorized by PaperSpine."""

    if operation.get("authority") != "paper-spine" or operation.get("executor") != "figmirror":
        raise ValueError("correction authority/executor boundary is invalid")
    supplied_operation_hash = operation.get("operation_sha256")
    unsigned = dict(operation)
    unsigned.pop("operation_sha256", None)
    if supplied_operation_hash != _canonical_sha256(unsigned):
        raise ValueError("correction operation hash does not recompute")
    source = Path(str((operation.get("source") or {}).get("path")))
    source_bytes = source.read_bytes()
    if _sha_bytes(source_bytes) != (operation.get("source") or {}).get("sha256"):
        raise ValueError("correction source hash does not match")
    changes = operation.get("allowed_text_changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("correction requires at least one allowed text change")
    operation_kind = operation.get("operation_kind")
    seen_ids: set[str] = set()
    applied = [
        {
            "change_id": change["change_id"],
            "element_id": str(change.get("element_id") or ""),
            "from_token": change.get("from_token"),
            "to_token": change.get("to_token"),
        }
        for change in changes
    ]
    for item in applied:
        element_id = item["element_id"]
        if not element_id or element_id in seen_ids:
            raise ValueError("correction element ids must be non-empty and unique")
        seen_ids.add(element_id)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if operation_kind == "svg_text_correction":
        root = ET.fromstring(source_bytes)
        for change in changes:
            element_id = str(change["element_id"])
            element = _element_by_id(root, element_id)
            source_token = change.get("from_token")
            target_token = change.get("to_token")
            if (
                element.text != source_token
                or not isinstance(target_token, str)
                or not target_token
            ):
                raise ValueError(f"correction source token mismatch: {element_id}")
            element.text = target_token
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        output_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        media_type = "image/svg+xml"
    elif operation_kind == "pdf_overlay_composition":
        overlay = operation.get("overlay")
        if not isinstance(overlay, dict):
            raise ValueError("PDF correction requires one hash-bound overlay")
        overlay_path = Path(str(overlay.get("path") or ""))
        overlay_bytes = overlay_path.read_bytes()
        if _sha_bytes(overlay_bytes) != overlay.get("sha256"):
            raise ValueError("PDF overlay hash does not match")
        if overlay.get("media_type") != "image/svg+xml":
            raise ValueError("typed PDF correction currently requires an editable SVG overlay")
        _validate_pdf_overlay(overlay_bytes, changes)
        output_bytes = _compose_pdf_overlay(
            source_bytes, overlay_bytes, str(overlay["media_type"])
        )
        media_type = "application/pdf"
    else:
        raise ValueError("unsupported figure correction operation_kind")
    output.write_bytes(output_bytes)
    pixel_diff, before, after, canvas = _pixel_diff_artifacts(
        source_bytes,
        output_bytes,
        media_type=media_type,
        changes=changes,
        bounds=operation["pixel_diff_bounds"],
    )
    blockers = (
        []
        if pixel_diff["within_bounds"]
        else ["PIXEL_DIFF_OUTSIDE_AUTHORIZED_MASK"]
    )
    render_invariants: list[dict[str, Any]] = []
    if operation_kind == "pdf_overlay_composition":
        for invariant in operation["scientific_invariants"][
            "render_invariant_regions"
        ]:
            source_hash = _region_pixels_sha256(before, canvas, invariant["region"])
            output_hash = _region_pixels_sha256(after, canvas, invariant["region"])
            preserved = (
                source_hash == invariant["source_pixels_sha256"] == output_hash
            )
            render_invariants.append(
                {
                    "invariant_id": invariant["invariant_id"],
                    "kind": invariant["kind"],
                    "source_pixels_sha256": source_hash,
                    "output_pixels_sha256": output_hash,
                    "preserved": preserved,
                }
            )
            if not preserved:
                blockers.append(
                    f"RENDER_INVARIANT_CHANGED:{invariant['invariant_id']}"
                )
    return {
        "contract": "figmirror.correction-execution",
        "contract_version": "1.0",
        "operation_id": operation["operation_id"],
        "operation_sha256": supplied_operation_hash,
        "source_sha256": _sha_bytes(source_bytes),
        "overlay_sha256": (
            (operation.get("overlay") or {}).get("sha256")
            if operation_kind == "pdf_overlay_composition"
            else None
        ),
        "output_sha256": _sha_bytes(output_bytes),
        "changes_applied": applied,
        "pixel_diff": pixel_diff,
        "render_invariants": render_invariants,
        "status": "PASS" if not blockers else "BLOCKED",
        "blockers": blockers,
        "decision_authority_exercised": False,
        "external_action_authorized": False,
    }


def apply_svg_text_correction(
    operation: dict[str, Any], output_path: str | Path
) -> dict[str, Any]:
    """Backward-compatible name for the now typed multi-media executor."""

    return apply_figure_correction(operation, output_path)
