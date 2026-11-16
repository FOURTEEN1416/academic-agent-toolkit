"""PaperSpine authority for constrained figure correction and target-size QA."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


SHA256 = re.compile(r"^[0-9a-f]{64}$")
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


class FigureCorrectionError(ValueError):
    """Raised when a correction cannot prove its scientific/visual boundary."""


def canonical_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
    ).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _element_by_id(root: ET.Element, element_id: str) -> ET.Element:
    matches = [item for item in root.iter() if item.attrib.get("id") == element_id]
    if len(matches) != 1:
        raise FigureCorrectionError(f"SVG element id must resolve exactly once: {element_id}")
    return matches[0]


def _element_sha(element: ET.Element) -> str:
    return hashlib.sha256(ET.tostring(element, encoding="utf-8")).hexdigest()


def svg_element_sha256(path: str | Path, element_id: str) -> str:
    root = ET.fromstring(Path(path).read_bytes())
    return _element_sha(_element_by_id(root, element_id))


def _render_pdf(path: Path, width: int):
    try:
        import fitz
        import numpy as np
    except ImportError as exc:  # pragma: no cover - dependency gate.
        raise FigureCorrectionError(
            "PDF figure correction requires PyMuPDF and NumPy"
        ) from exc
    document = fitz.open(path)
    try:
        if document.page_count != 1:
            raise FigureCorrectionError(
                "PDF figure correction requires exactly one page"
            )
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


def pdf_render_region_sha256(
    path: str | Path,
    region: dict[str, Any],
    *,
    render_width_px: int,
) -> str:
    """Hash one PDF render crop for panel/data invariance binding."""

    image, canvas = _render_pdf(Path(path), render_width_px)
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
        raise FigureCorrectionError("PDF render invariant region is empty")
    return hashlib.sha256(image[top:bottom, left:right].tobytes()).hexdigest()


def build_pdf_text_overlay(
    source_pdf: str | Path,
    changes: list[dict[str, Any]],
    output_svg: str | Path,
) -> dict[str, Any]:
    """Build the exact PaperSpine-authorized mask/text layer for one PDF page."""

    try:
        import cairocffi as cairo
        import fitz
    except ImportError as exc:  # pragma: no cover - dependency gate.
        raise FigureCorrectionError(
            "PDF overlay construction requires PyMuPDF and Cairo"
        ) from exc
    source = Path(source_pdf)
    document = fitz.open(source)
    try:
        if document.page_count != 1:
            raise FigureCorrectionError("PDF overlay requires exactly one source page")
        width = float(document[0].rect.width)
        height = float(document[0].rect.height)
    finally:
        document.close()
    namespace = "http://www.w3.org/2000/svg"
    ET.register_namespace("", namespace)
    root = ET.Element(
        f"{{{namespace}}}svg",
        {
            "viewBox": f"0 0 {width:.6f} {height:.6f}",
            "width": f"{width:.6f}",
            "height": f"{height:.6f}",
            "role": "img",
            "data-paperspine-overlay": "typed-pdf-correction-v1",
        },
    )
    mask_group = ET.SubElement(root, f"{{{namespace}}}g", {"id": "authorized-masks"})
    text_group = ET.SubElement(root, f"{{{namespace}}}g", {"id": "authorized-text"})
    seen_changes: set[str] = set()
    for change in changes:
        change_id = str(change.get("change_id") or "")
        if not change_id or change_id in seen_changes:
            raise FigureCorrectionError(
                "PDF overlay change IDs must be non-empty and unique"
            )
        seen_changes.add(change_id)
        region = change["region"]
        text_spec = change.get("overlay_text")
        if not isinstance(text_spec, dict):
            raise FigureCorrectionError(
                f"PDF overlay text placement is missing: {change_id}"
            )
        text = str(text_spec.get("text") or "")
        from_token = str(change.get("from_token") or "")
        to_token = str(change.get("to_token") or "")
        if text.count(to_token) != 1 or from_token in text:
            raise FigureCorrectionError(
                f"PDF overlay text must contain exactly the authorized target token: {change_id}"
            )
        ET.SubElement(
            mask_group,
            f"{{{namespace}}}rect",
            {
                "id": str(change["mask_element_id"]),
                "x": str(region["x"]),
                "y": str(region["y"]),
                "width": str(region["width"]),
                "height": str(region["height"]),
                "fill": "#ffffff",
                "stroke": "none",
            },
        )
        family = str(text_spec["font_family"])
        font_size = float(text_spec["font_size"])
        text_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
        text_context = cairo.Context(text_surface)
        text_context.select_font_face(family)
        text_context.set_font_size(font_size)
        extents = text_context.text_extents(text)
        x_bearing, _y_bearing, text_width, _text_height, x_advance, _y_advance = (
            tuple(extents)
        )
        natural_length = max(
            float(x_advance),
            float(x_bearing + text_width),
        )
        if natural_length <= 0:
            raise FigureCorrectionError(
                f"PDF overlay text has no measurable advance: {change_id}"
            )
        rotation = float(text_spec["rotation_degrees"])
        if abs(rotation) == 90:
            available_length = float(text_spec["y"]) - float(region["y"]) - 0.5
        else:
            available_length = (
                float(region["x"])
                + float(region["width"])
                - float(text_spec["x"])
                - 0.5
            )
        if available_length <= 0:
            raise FigureCorrectionError(
                f"PDF overlay text placement escapes its authorized mask: {change_id}"
            )
        horizontal_scale = min(1.0, available_length / natural_length)
        anchor_x = float(text_spec["x"])
        anchor_y = float(text_spec["y"])
        transform = (
            f"translate({anchor_x:g} {anchor_y:g}) "
            + (f"rotate({rotation:g}) " if rotation else "")
            + f"scale({horizontal_scale:.9f} 1)"
        )
        attributes = {
            "id": str(change["element_id"]),
            "x": "0",
            "y": "0",
            "font-family": family,
            "font-size": str(font_size),
            "fill": str(text_spec["fill"]),
            "transform": transform,
            "data-paperspine-anchor-x": f"{anchor_x:.9f}",
            "data-paperspine-anchor-y": f"{anchor_y:.9f}",
            "data-paperspine-horizontal-scale": f"{horizontal_scale:.9f}",
        }
        element = ET.SubElement(text_group, f"{{{namespace}}}text", attributes)
        element.text = text
    encoded = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    output = Path(output_svg)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    return {
        "path": str(output),
        "media_type": "image/svg+xml",
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _schema(name: str) -> dict[str, Any]:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def _validate_schema(name: str, value: dict[str, Any]) -> None:
    registry = Registry()
    target_size_schema = _schema("target-size-legibility.schema.json")
    registry = registry.with_resource(
        target_size_schema["$id"], Resource.from_contents(target_size_schema)
    )
    errors = sorted(
        Draft202012Validator(_schema(name), registry=registry).iter_errors(value),
        key=lambda item: list(item.path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(item) for item in first.path) or "$"
        raise FigureCorrectionError(f"{name} {location}: {first.message}")


def _validate_independent_review(
    review: dict[str, Any],
    *,
    expected_subject: dict[str, Any],
) -> None:
    checks = review.get("checks") or {}
    reviewer = review.get("reviewer") or {}
    review_hash = review.get("review_sha256")
    unsigned_review = deepcopy(review)
    unsigned_review.pop("review_sha256", None)
    reviewer_core = {
        key: reviewer.get(key)
        for key in (
            "principal_id",
            "session_id",
            "run_id",
            "independence_group",
            "attestation_input_id",
            "actor_kind",
        )
    }
    producer_ids = review.get("producer_ids") or []
    if (
        review.get("contract") != "paperspine5.figure-correction-review"
        or review.get("contract_version") != "1.0"
        or review.get("subject") != expected_subject
        or review.get("reviewer_type") != "independent_multimodal"
        or review.get("reviewer_id") != reviewer.get("principal_id")
        or reviewer.get("actor_kind") != "host_independent_multimodal"
        or reviewer.get("provenance_sha256") != canonical_sha256(reviewer_core)
        or set(producer_ids) != {"paper-spine", "figmirror"}
        or any(
            reviewer.get(field) in set(producer_ids)
            for field in ("principal_id", "session_id", "run_id", "independence_group")
        )
        or review.get("producer_actor") != "figmirror"
        or review.get("status") != "pass"
        or set(checks)
        != {
            "allowed_tokens_only",
            "mask_scope_valid",
            "scientific_invariants_valid",
            "target_size_legible",
        }
        or not all(value is True for value in checks.values())
        or review.get("external_action_authorized") is not False
        or review_hash != canonical_sha256(unsigned_review)
    ):
        raise FigureCorrectionError("independent final review is missing, stale, or not PASS")


def validate_figure_correction_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Validate the closed receipt, nested review, self-hash, and bindings."""

    value = deepcopy(receipt)
    _validate_schema("figure-correction-receipt.schema.json", value)
    supplied_hash = value.pop("receipt_sha256")
    if supplied_hash != canonical_sha256(value):
        raise FigureCorrectionError("figure correction receipt_sha256 does not recompute")
    review = value["independent_final_review"]
    _validate_independent_review(
        review,
        expected_subject={
            **value["subject"],
            "operation_id": value["operation_id"],
            "operation_sha256": value["operation_sha256"],
            "source_sha256": value["source"]["sha256"],
            "overlay_sha256": (
                value["overlay"]["sha256"]
                if isinstance(value.get("overlay"), dict)
                else None
            ),
            "output_sha256": value["output"]["sha256"],
            "pixel_diff_sha256": canonical_sha256(value["pixel_diff"]),
            "scientific_invariants_sha256": canonical_sha256(
                value["scientific_invariants"]
            ),
            "target_size_legibility_sha256": value[
                "target_size_legibility"
            ]["receipt_sha256"],
        },
    )
    return deepcopy(receipt)


def validate_target_size_legibility_receipt(
    receipt: dict[str, Any],
    *,
    figure_id: str | None = None,
    figure_sha256: str | None = None,
    require_pass: bool = False,
) -> dict[str, Any]:
    """Validate one self-hashed target-size receipt and its current figure binding."""

    value = deepcopy(receipt)
    _validate_schema("target-size-legibility.schema.json", value)
    supplied_hash = value.pop("receipt_sha256")
    if supplied_hash != canonical_sha256(value):
        raise FigureCorrectionError(
            "target-size legibility receipt_sha256 does not recompute"
        )
    if figure_id is not None and value["figure_id"] != figure_id:
        raise FigureCorrectionError("target-size legibility figure_id is stale")
    if figure_sha256 is not None and value["figure_sha256"] != figure_sha256:
        raise FigureCorrectionError("target-size legibility figure hash is stale")
    if (
        value["status"] == "PASS"
        and (
            value["target_size_legible"] is not True
            or value["all_text_minimum_passed"] is not True
            or value["blocking_label_ids"]
            or not all(item["readable"] is True for item in value["critical_labels"])
        )
    ):
        raise FigureCorrectionError(
            "target-size PASS contradicts the measured text or critical labels"
        )
    if require_pass and value["status"] != "PASS":
        raise FigureCorrectionError(
            "target-size legibility is BLOCKED for the selected delivery asset"
        )
    return deepcopy(receipt)


def _compare_svg_semantics(
    source_path: Path,
    output_path: Path,
    changes: list[dict[str, Any]],
) -> None:
    source_root = ET.fromstring(source_path.read_bytes())
    output_root = ET.fromstring(output_path.read_bytes())
    source_elements = list(source_root.iter())
    output_elements = list(output_root.iter())
    if len(source_elements) != len(output_elements):
        raise FigureCorrectionError("correction changed SVG element count")
    changes_by_id = {item["element_id"]: item for item in changes}
    if len(changes_by_id) != len(changes):
        raise FigureCorrectionError("correction element ids must be unique")
    for before, after in zip(source_elements, output_elements, strict=True):
        if (
            before.tag != after.tag
            or before.attrib != after.attrib
            or before.tail != after.tail
            or len(before) != len(after)
        ):
            element_id = before.attrib.get("id", "<unidentified>")
            raise FigureCorrectionError(
                f"correction changed non-text SVG structure or data curve: {element_id}"
            )
        element_id = before.attrib.get("id")
        change = changes_by_id.get(element_id or "")
        if change is None:
            if before.text != after.text:
                raise FigureCorrectionError(
                    f"correction changed an unauthorized token or data value: {element_id}"
                )
        elif before.text != change["from_token"] or after.text != change["to_token"]:
            raise FigureCorrectionError(f"correction token drift: {element_id}")


class FigureCorrectionService:
    """Authorize, execute, independently verify, and receipt one correction."""

    def __init__(self, *, executor: Callable[[dict[str, Any], str | Path], dict[str, Any]]):
        self.executor = executor

    def execute(
        self,
        operation: dict[str, Any],
        output_path: str | Path,
        *,
        target_size_profile: dict[str, Any],
        review_bindings: dict[str, Any],
        reviewer: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        request = deepcopy(operation)
        _validate_schema("figure-correction-operation.schema.json", request)
        supplied_hash = request["operation_sha256"]
        unsigned = deepcopy(request)
        unsigned.pop("operation_sha256")
        if supplied_hash != canonical_sha256(unsigned):
            raise FigureCorrectionError("operation_sha256 does not bind the operation")
        if request["authority"] != "paper-spine" or request["executor"] != "figmirror":
            raise FigureCorrectionError("PaperSpine must own decisions and FigMirror only execution")
        source = Path(request["source"]["path"])
        if _sha(source) != request["source"]["sha256"]:
            raise FigureCorrectionError("source hash does not match the correction operation")
        output = Path(output_path)
        if source.resolve() == output.resolve():
            raise FigureCorrectionError("correction output must differ from the immutable source")
        operation_kind = request["operation_kind"]
        invariant_ids = {
            *request["scientific_invariants"].get(
                "data_curve_element_sha256", {}
            ),
            *request["scientific_invariants"].get(
                "data_value_element_sha256", {}
            ),
        }
        changed_ids = {item["element_id"] for item in request["allowed_text_changes"]}
        overlap = invariant_ids & changed_ids
        if overlap:
            raise FigureCorrectionError(
                "allowed text changes cannot include data curve/value invariants: "
                + ", ".join(sorted(overlap))
            )

        output.parent.mkdir(parents=True, exist_ok=True)
        staging = output.with_name(
            f".{output.name}.{uuid.uuid4().hex}.paperspine-correction-stage"
        )
        try:
            execution = self.executor(request, staging)
            if execution.get("operation_sha256") != supplied_hash:
                raise FigureCorrectionError("executor operation hash mismatch")
            if execution.get("source_sha256") != request["source"]["sha256"]:
                raise FigureCorrectionError("executor source hash mismatch")
            expected_overlay_hash = (
                request["overlay"]["sha256"]
                if isinstance(request.get("overlay"), dict)
                else None
            )
            if execution.get("overlay_sha256") != expected_overlay_hash:
                raise FigureCorrectionError("executor overlay hash mismatch")
            if not staging.is_file() or execution.get("output_sha256") != _sha(staging):
                raise FigureCorrectionError("executor output hash does not match the actual output")
            if execution.get("changes_applied") != [
                {
                    "change_id": item["change_id"],
                    "element_id": item["element_id"],
                    "from_token": item["from_token"],
                    "to_token": item["to_token"],
                }
                for item in request["allowed_text_changes"]
            ]:
                raise FigureCorrectionError("executor token change list differs from the operation")
            pixel_diff = execution.get("pixel_diff") or {}
            if execution.get("status") != "PASS" or pixel_diff.get("within_bounds") is not True:
                raise FigureCorrectionError(
                    "correction pixel diff escaped the authorized mask/bounds "
                    f"(changed_fraction={pixel_diff.get('changed_pixel_fraction')}, "
                    f"outside_mask={pixel_diff.get('outside_mask_changed_pixels')}, "
                    f"outside_bounds={pixel_diff.get('outside_mask_render_bounds')}, "
                    f"by_change={pixel_diff.get('outside_mask_by_change')})"
                )
            if operation_kind == "svg_text_correction":
                _compare_svg_semantics(
                    source, staging, request["allowed_text_changes"]
                )
                output_root = ET.fromstring(staging.read_bytes())
                for category in (
                    "data_curve_element_sha256",
                    "data_value_element_sha256",
                ):
                    for element_id, expected in request["scientific_invariants"][
                        category
                    ].items():
                        actual = _element_sha(
                            _element_by_id(output_root, element_id)
                        )
                        if actual != expected:
                            label = (
                                "data curve"
                                if category.startswith("data_curve")
                                else "data value"
                            )
                            raise FigureCorrectionError(
                                f"correction changed {label}: {element_id}"
                            )
                for panel_id in request["scientific_invariants"]["panel_ids"]:
                    _element_by_id(output_root, panel_id)
            else:
                render_invariants = execution.get("render_invariants")
                if not isinstance(render_invariants, list):
                    raise FigureCorrectionError(
                        "PDF executor omitted render invariant evidence"
                    )
                expected_invariants = {
                    item["invariant_id"]: item
                    for item in request["scientific_invariants"][
                        "render_invariant_regions"
                    ]
                }
                actual_invariants = {
                    str(item.get("invariant_id") or ""): item
                    for item in render_invariants
                    if isinstance(item, dict)
                }
                required_kinds = {"panel", "data_curve", "data_value"}
                if (
                    set(actual_invariants) != set(expected_invariants)
                    or {
                        str(item.get("kind") or "")
                        for item in actual_invariants.values()
                    }
                    != required_kinds
                    or any(
                        item.get("preserved") is not True
                        for item in actual_invariants.values()
                    )
                ):
                    raise FigureCorrectionError(
                        "PDF panel/data-curve/data-value render invariants are incomplete or changed"
                    )
            invariants = {
                "panels_preserved": True,
                "data_curves_preserved": True,
                "data_values_preserved": True,
            }
            staged_hash = _sha(staging)
            legibility = review_target_size_legibility(staging, target_size_profile)
            validate_target_size_legibility_receipt(
                legibility,
                figure_id=request["figure_id"],
                figure_sha256=staged_hash,
                require_pass=True,
            )
            if set(review_bindings) != {
                "task_id",
                "revision",
                "material_snapshot_sha256",
            }:
                raise FigureCorrectionError(
                    "independent review bindings must be the exact current task/revision/material subject"
                )
            expected_subject = {
                "task_id": review_bindings["task_id"],
                "revision": review_bindings["revision"],
                "material_snapshot_sha256": review_bindings[
                    "material_snapshot_sha256"
                ],
                "operation_id": request["operation_id"],
                "operation_sha256": supplied_hash,
                "source_sha256": request["source"]["sha256"],
                "overlay_sha256": expected_overlay_hash,
                "output_sha256": staged_hash,
                "pixel_diff_sha256": canonical_sha256(pixel_diff),
                "scientific_invariants_sha256": canonical_sha256(invariants),
                "target_size_legibility_sha256": legibility["receipt_sha256"],
            }
            review_context = {
                "contract": "paperspine5.figure-correction-review-context",
                "contract_version": "1.0",
                "subject": deepcopy(expected_subject),
                "artifacts": {
                    "source": deepcopy(request["source"]),
                    "overlay": deepcopy(request.get("overlay")),
                    "output": {
                        "path": str(staging),
                        "media_type": (
                            "application/pdf"
                            if operation_kind == "pdf_overlay_composition"
                            else "image/svg+xml"
                        ),
                        "sha256": staged_hash,
                    },
                },
                "pixel_diff": deepcopy(pixel_diff),
                "scientific_invariants": deepcopy(invariants),
                "target_size_legibility": deepcopy(legibility),
                "producer_ids": ["paper-spine", "figmirror"],
                "external_action_authorized": False,
            }
            final_review = reviewer(deepcopy(review_context))
            if not isinstance(final_review, dict):
                raise FigureCorrectionError("independent reviewer did not return a typed result")
            _validate_independent_review(
                final_review,
                expected_subject=expected_subject,
            )

            receipt = {
                "contract": "paperspine5.figure-correction-receipt",
                "contract_version": "1.0",
                "operation_kind": operation_kind,
                "operation_id": request["operation_id"],
                "operation_sha256": supplied_hash,
                "figure_id": request["figure_id"],
                "subject": {
                    "task_id": review_bindings["task_id"],
                    "revision": review_bindings["revision"],
                    "material_snapshot_sha256": review_bindings[
                        "material_snapshot_sha256"
                    ],
                },
                "authority": "paper-spine",
                "executor": "figmirror",
                "source": deepcopy(request["source"]),
                "overlay": deepcopy(request.get("overlay")),
                "output": {
                    "path": str(output),
                    "media_type": (
                        "application/pdf"
                        if operation_kind == "pdf_overlay_composition"
                        else "image/svg+xml"
                    ),
                    "sha256": staged_hash,
                },
                "changes_applied": execution["changes_applied"],
                "authorized_regions": [
                    {
                        "change_id": item["change_id"],
                        "region": deepcopy(item["region"]),
                        "mask": deepcopy(item["mask"]),
                    }
                    for item in request["allowed_text_changes"]
                ],
                "pixel_diff": deepcopy(pixel_diff),
                "scientific_invariants": invariants,
                "target_size_legibility": deepcopy(legibility),
                "independent_final_review": deepcopy(final_review),
                "status": "PASS",
                "external_action_authorized": False,
            }
            receipt["receipt_sha256"] = canonical_sha256(receipt)
            validate_figure_correction_receipt(receipt)
            staging.replace(output)
            if _sha(output) != staged_hash:  # pragma: no cover - filesystem corruption gate.
                raise FigureCorrectionError("atomic correction placement hash mismatch")
            return receipt
        finally:
            if staging.exists():
                staging.unlink()


def review_target_size_legibility(
    figure_path: str | Path, profile: dict[str, Any]
) -> dict[str, Any]:
    """Measure text at declared publication size; producer PASS cannot override it."""

    source = Path(figure_path)
    request = deepcopy(profile)
    if request.get("contract") != "paperspine5.target-size-legibility-profile":
        raise FigureCorrectionError("target-size legibility profile contract is invalid")
    if request.get("target_class") not in {"single_column", "double_column", "full_page"}:
        raise FigureCorrectionError("target_class must be single_column/double_column/full_page")
    width_mm = request.get("physical_width_mm")
    height_mm = request.get("physical_height_mm")
    if (
        isinstance(width_mm, bool)
        or not isinstance(width_mm, (int, float))
        or width_mm <= 0
        or isinstance(height_mm, bool)
        or not isinstance(height_mm, (int, float))
        or height_mm <= 0
    ):
        raise FigureCorrectionError("target physical size must be positive millimetres")
    minimum = float(request["minimum_font_pt"])
    critical_minimum = float(request["critical_label_minimum_font_pt"])
    measurements: list[dict[str, Any]] = []
    blocking: set[str] = set()
    all_text_measurements: list[dict[str, Any]] = []
    source_bytes = source.read_bytes()
    if source_bytes.startswith(b"%PDF"):
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - dependency gate.
            raise FigureCorrectionError(
                "PDF target-size review requires PyMuPDF"
            ) from exc
        document = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            if document.page_count != 1:
                raise FigureCorrectionError(
                    "target-size review requires one figure page"
                )
            page = document[0]
            view_width = float(page.rect.width)
            view_height = float(page.rect.height)
            width_scale = float(width_mm) / 25.4 * 72.0 / view_width
            height_scale = float(height_mm) / 25.4 * 72.0 / view_height
            points_per_user_unit = min(width_scale, height_scale)
            spans = [
                span
                for block in page.get_text("dict").get("blocks", [])
                if isinstance(block, dict)
                for line in block.get("lines", [])
                if isinstance(line, dict)
                for span in line.get("spans", [])
                if isinstance(span, dict) and str(span.get("text") or "").strip()
            ]
        finally:
            document.close()
        for index, span in enumerate(spans):
            text = str(span["text"]).strip()
            source_font_size = float(span["size"])
            token = hashlib.sha256(
                (
                    text
                    + "|"
                    + json.dumps(span.get("bbox"), separators=(",", ":"))
                ).encode("utf-8")
            ).hexdigest()[:16]
            element_id = f"pdf-span-{index + 1}-{token}"
            effective_font_size = source_font_size * points_per_user_unit
            readable = effective_font_size >= minimum
            if not readable:
                blocking.add(element_id)
            all_text_measurements.append(
                {
                    "element_id": element_id,
                    "effective_font_pt": effective_font_size,
                    "threshold_font_pt": minimum,
                    "readable": readable,
                }
            )
        if not all_text_measurements:
            raise FigureCorrectionError(
                "target-size review requires extractable PDF text spans"
            )
        for label in request.get("critical_labels") or []:
            matches = [
                span
                for span in spans
                if str(span.get("text") or "").strip() == label["expected_text"]
            ]
            if len(matches) != 1:
                raise FigureCorrectionError(
                    f"critical PDF label must resolve exactly once: {label['element_id']}"
                )
            font_size = float(matches[0]["size"])
            effective = font_size * points_per_user_unit
            passed = effective >= max(minimum, critical_minimum)
            if not passed:
                blocking.add(label["element_id"])
            measurements.append(
                {
                    "element_id": label["element_id"],
                    "text": label["expected_text"],
                    "source_font_user_units": font_size,
                    "effective_font_pt": effective,
                    "threshold_font_pt": max(minimum, critical_minimum),
                    "readable": passed,
                }
            )
    else:
        root = ET.fromstring(source_bytes)
        raw_view_box = root.attrib.get("viewBox", "").replace(",", " ").split()
        if len(raw_view_box) != 4:
            raise FigureCorrectionError("target-size review requires an SVG viewBox")
        view_width = float(raw_view_box[2])
        if view_width <= 0:
            raise FigureCorrectionError("SVG viewBox width must be positive")
        view_height = float(raw_view_box[3])
        if view_height <= 0:
            raise FigureCorrectionError("SVG viewBox height must be positive")
        width_scale = float(width_mm) / 25.4 * 72.0 / view_width
        height_scale = float(height_mm) / 25.4 * 72.0 / view_height
        points_per_user_unit = min(width_scale, height_scale)
        for index, element in enumerate(
            item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "text"
        ):
            element_id = element.attrib.get("id") or f"unidentified-text-{index + 1}"
            try:
                source_font_size = float(element.attrib["font-size"])
            except (KeyError, ValueError) as exc:
                raise FigureCorrectionError(
                    f"text element lacks a numeric font-size: {element_id}"
                ) from exc
            effective_font_size = source_font_size * points_per_user_unit
            readable = effective_font_size >= minimum
            if not readable:
                blocking.add(element_id)
            all_text_measurements.append(
                {
                    "element_id": element_id,
                    "effective_font_pt": effective_font_size,
                    "threshold_font_pt": minimum,
                    "readable": readable,
                }
            )
        if not all_text_measurements:
            raise FigureCorrectionError("target-size review requires SVG text elements")
        for label in request.get("critical_labels") or []:
            element = _element_by_id(root, label["element_id"])
            if (element.text or "").strip() != label["expected_text"]:
                raise FigureCorrectionError(
                    f"critical label text drift: {label['element_id']}"
                )
            try:
                font_size = float(element.attrib["font-size"])
            except (KeyError, ValueError) as exc:
                raise FigureCorrectionError(
                    f"critical label lacks a numeric font-size: {label['element_id']}"
                ) from exc
            effective = font_size * points_per_user_unit
            passed = effective >= max(minimum, critical_minimum)
            if not passed:
                blocking.add(label["element_id"])
            measurements.append(
                {
                    "element_id": label["element_id"],
                    "text": label["expected_text"],
                    "source_font_user_units": font_size,
                    "effective_font_pt": effective,
                    "threshold_font_pt": max(minimum, critical_minimum),
                    "readable": passed,
                }
            )
    if not measurements:
        raise FigureCorrectionError("target-size review requires critical labels")
    normalized_profile = deepcopy(request)
    normalized_profile["physical_width_mm"] = float(width_mm)
    normalized_profile["physical_height_mm"] = float(height_mm)
    result = {
        "contract": "paperspine5.target-size-legibility-receipt",
        "contract_version": "1.0",
        "figure_id": request["figure_id"],
        "figure_sha256": _sha(source),
        "profile": normalized_profile,
        "all_text_labels": all_text_measurements,
        "minimum_font_pt_observed": min(
            item["effective_font_pt"] for item in all_text_measurements
        ),
        "all_text_minimum_passed": all(
            item["readable"] for item in all_text_measurements
        ),
        "critical_labels": measurements,
        "blocking_label_ids": sorted(blocking),
        "target_size_legible": not blocking,
        "status": "PASS" if not blocking else "BLOCKED",
        "producer_status_accepted": request.get("producer_status") == "PASS" and not blocking,
        "external_action_authorized": False,
    }
    result["receipt_sha256"] = canonical_sha256(result)
    _validate_schema("target-size-legibility.schema.json", result)
    return result
