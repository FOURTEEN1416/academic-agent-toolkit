"""Vector-first blueprint workflow with render-in-the-loop feedback.

The multimodal Agent authors a semantic ``blueprint_ir.json`` (the existing
FigureSpec contract). FigMirror deterministically renders real SVG and a PNG
preview, then accepts only visual patches that cannot rewrite scientific
labels or connector topology. The PNG is therefore evidence for review, never
the source of the final figure.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .evidence_bridge import (
    materialize_schematic_evidence,
    validate_materialized_evidence_svg,
)
from .figure_spec import render_figure_spec, validate_figure_spec
from .svg import audit_svg


VECTOR_BLUEPRINT_VERSION = "0.1"
REQUIRED_FEEDBACK_CHECKS = ("structure", "labels", "arrows", "layout", "editability")
LAYOUT_PATCH_FIELDS = {
    "margin",
    "header_height",
    "rank_gap",
    "max_rank_gap",
    "node_gap",
    "lane_gap",
    "lane_padding",
    "min_extent_occupancy",
    "min_packing_ratio",
    "max_edge_crossings",
    "font_size",
}
NODE_PATCH_FIELDS = {"width", "height", "emphasis"}
EDGE_PATCH_FIELDS = {"source_port", "target_port"}
CANVAS_PATCH_FIELDS = {"width", "height"}


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _write_object(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _is_pass(value: Any) -> bool:
    return str(value or "").strip().lower() in {"pass", "passed", "verified", "true", "yes"}


def _resolve_ir(candidate: Path, value: str | Path | None = None) -> Path:
    if value is not None:
        path = Path(value)
        if not path.is_absolute():
            path = candidate / path
        if not path.is_file():
            raise ValueError(f"blueprint IR does not exist: {path}")
        return path
    for name in ("blueprint_ir.refined.json", "blueprint_ir.json", "figure_spec.json"):
        path = candidate / name
        if path.is_file():
            return path
    raise ValueError("direct-vector candidate requires blueprint_ir.json or figure_spec.json")


def _resolve_render_ir(candidate: Path) -> Path:
    for name in ("blueprint_ir.refined.json", "blueprint_ir.evidence.json", "blueprint_ir.json", "figure_spec.json"):
        path = candidate / name
        if path.is_file():
            return path
    raise ValueError("direct-vector candidate requires blueprint_ir.json or figure_spec.json")


def _request(candidate: Path) -> dict[str, Any]:
    request = _read_object(candidate / "generation_request.json")
    if request.get("figure_kind") != "schematic":
        raise ValueError("vector blueprints are only valid for schematic candidates")
    architecture = request.get("architecture_contract")
    if not isinstance(architecture, dict) or architecture.get("pipeline") != "direct_vector":
        raise ValueError("generation_request.json is not configured for the direct_vector pipeline")
    return request


def _render_preview(svg_path: Path, preview_path: Path, width: int) -> None:
    if not 640 <= width <= 4096:
        raise ValueError("preview_width must be between 640 and 4096")
    try:
        import cairosvg
    except ImportError as exc:  # pragma: no cover
        raise ValueError("CairoSVG is required to render vector blueprint previews") from exc
    cairosvg.svg2png(url=str(svg_path), write_to=str(preview_path), output_width=width)


def _feedback_history(candidate: Path) -> list[dict[str, Any]]:
    path = candidate / "visual_feedback_review.json"
    if not path.is_file():
        return []
    value = _read_object(path).get("rounds", [])
    return list(value) if isinstance(value, list) else []


def _reference_inputs(request: dict[str, Any]) -> list[str]:
    contract = request.get("reference_contract", {})
    assets = contract.get("assets", []) if isinstance(contract, dict) else []
    return [
        str(item.get("resolved_path"))
        for item in assets
        if isinstance(item, dict) and item.get("status") == "available" and item.get("resolved_path")
    ]


def build_vector_blueprint(
    candidate_dir: str | Path,
    *,
    ir: str | Path | None = None,
    preview_width: int = 1800,
) -> dict[str, Any]:
    """Render semantic IR as the authoritative editable blueprint.

    This operation never invokes a full-figure raster blueprint generator.
    When the candidate contract explicitly allows raster-in-SVG, isolated
    non-text scientific illustration assets may be embedded while semantic
    text, arrows, borders, and node structure remain live SVG.
    """

    candidate = Path(candidate_dir).resolve()
    request = _request(candidate)
    allow_raster = bool(request.get("authoring_contract", {}).get("raster_in_svg", False))
    source_ir = _resolve_ir(candidate, ir)
    source_spec = validate_figure_spec(_read_object(source_ir))
    spec, data_evidence = materialize_schematic_evidence(candidate, source_spec)
    spec = validate_figure_spec(spec)

    canonical_ir = candidate / "blueprint_ir.json"
    if not canonical_ir.is_file():
        _write_object(canonical_ir, source_spec)
    render_ir = source_ir
    if data_evidence["used"]:
        render_ir = candidate / "blueprint_ir.evidence.json"
        _write_object(render_ir, spec)

    svg_path = candidate / "blueprint.svg"
    preview_path = candidate / "blueprint_preview.png"
    layout_report = candidate / "blueprint_layout_report.json"
    panel_manifest = candidate / "blueprint_panel_manifest.json"
    render_result = render_figure_spec(
        spec,
        svg_path,
        layout_report=layout_report,
        panel_manifest=panel_manifest,
        asset_root=candidate,
        allow_raster=allow_raster,
    )
    evidence_svg = validate_materialized_evidence_svg(svg_path, data_evidence)
    data_evidence["svg_visibility"] = evidence_svg
    _render_preview(svg_path, preview_path, preview_width)
    svg_audit = audit_svg(
        svg_path,
        allow_raster=allow_raster,
        require_text=True,
        require_named_groups=True,
        require_connector_metadata=True,
    )
    hard_gates = {
        "xml_and_svg_audit": svg_audit.status == "PASS",
        "raster_asset_policy": (
            svg_audit.raster_image_count == len(render_result.get("raster_assets", {}))
            and (allow_raster or svg_audit.raster_image_count == 0)
        ),
        "live_editable_text": svg_audit.text_count > 0,
        "stable_named_groups": svg_audit.named_group_count > 0,
        "connector_metadata_complete": (
            svg_audit.connector_count > 0
            and svg_audit.connector_count == svg_audit.connector_metadata_count
        ),
        "preview_is_derived_from_svg": True,
        "aggregate_data_evidence_valid": data_evidence["status"] in {"PASS", "NOT_APPLICABLE"},
        "aggregate_data_evidence_materialized": (
            not data_evidence["used"]
            or data_evidence.get("materialization_count") == data_evidence.get("binding_count")
        ),
        "aggregate_data_evidence_visible_in_svg": evidence_svg["verified"],
    }
    status = "PASS" if all(hard_gates.values()) else "FAIL"
    manifest = {
        "schema_version": VECTOR_BLUEPRINT_VERSION,
        "status": status,
        "candidate_id": request.get("candidate_id"),
        "figure_id": request.get("figure_id"),
        "pipeline": "direct_vector",
        "authoritative_source": source_ir.name,
        "render_source": render_ir.name,
        "canonical_ir": canonical_ir.name,
        "svg": svg_path.name,
        "preview": preview_path.name,
        "preview_role": "derived_visual_feedback_only",
        "ai_raster_blueprint_used": False,
        "ai_raster_asset_count": svg_audit.raster_image_count,
        "rendering_mode": "hybrid-raster-vector" if svg_audit.raster_image_count else "vector",
        "sha256": {
            "ir": _sha256(source_ir),
            "render_ir": _sha256(render_ir),
            "svg": _sha256(svg_path),
            "preview": _sha256(preview_path),
        },
        "hard_gates": hard_gates,
        "svg_audit": svg_audit.to_dict(),
        "layout_audit": render_result["layout_audit"],
        "data_evidence": data_evidence,
    }
    _write_object(candidate / "vector_blueprint_manifest.json", manifest)

    locked_semantics = {
        "claim": spec["story"]["claim"],
        "labels": {node["id"]: {"label": node["label"], "detail": node["detail"]} for node in spec["nodes"]},
        "connectors": {
            edge["id"]: {"source": edge["source"], "target": edge["target"], "kind": edge["kind"]}
            for edge in spec["edges"]
        },
        "data_evidence_bindings": data_evidence.get("bindings", []),
    }
    feedback_request = {
        "schema_version": VECTOR_BLUEPRINT_VERSION,
        "task": "compare_reference_and_rendered_vector_blueprint",
        "candidate_id": request.get("candidate_id"),
        "reference_images": _reference_inputs(request),
        "rendered_preview": str(preview_path),
        "vector_source": str(render_ir),
        "locked_semantics": locked_semantics,
        "aggregate_data_evidence": {
            "used": data_evidence["used"],
            "facts": data_evidence.get("selected_facts", []),
            "scientific_limits": data_evidence.get("scientific_limits", []),
        },
        "instructions": [
            "Judge the reference mechanism and visual hierarchy, not literal pixel identity.",
            "Do not change labels, scientific dimensions, node identity, or edge source/target topology.",
            "Use patches only for canvas size, layout spacing, node size/emphasis, and connector ports.",
            "Return PASS only when structure, labels, arrow direction, layout, and editability all pass.",
        ],
        "response_contract": {
            "status": "PASS or REVISE",
            "checks": {key: "PASS or REVISE" for key in REQUIRED_FEEDBACK_CHECKS},
            "observations": ["short evidence-backed visual observation"],
            "patches": [
                {
                    "target_type": "layout|canvas|node|edge",
                    "id": "required for node/edge",
                    "changes": "allowlisted visual fields only",
                }
            ],
        },
    }
    _write_object(candidate / "visual_feedback_request.json", feedback_request)

    review_path = candidate / "visual_feedback_review.json"
    if not review_path.is_file():
        _write_object(
            review_path,
            {
                "schema_version": VECTOR_BLUEPRINT_VERSION,
                "status": "PENDING",
                "candidate_id": request.get("candidate_id"),
                "latest_preview": preview_path.name,
                "rounds": [],
            },
        )
    if status != "PASS":
        raise ValueError(f"vector blueprint failed hard gates: {svg_audit.failures}")
    return manifest


def _patch_target(items: list[dict[str, Any]], identifier: str, kind: str) -> dict[str, Any]:
    for item in items:
        if item.get("id") == identifier:
            return item
    raise ValueError(f"visual patch references unknown {kind}: {identifier}")


def _apply_patch(spec: dict[str, Any], patch: dict[str, Any]) -> None:
    target_type = str(patch.get("target_type") or "").strip()
    changes = patch.get("changes")
    if not isinstance(changes, dict) or not changes:
        raise ValueError("each visual patch requires a non-empty changes object")
    if target_type == "layout":
        target = spec.setdefault("layout", {})
        allowed = LAYOUT_PATCH_FIELDS
    elif target_type == "canvas":
        target = spec
        allowed = CANVAS_PATCH_FIELDS
    elif target_type == "node":
        identifier = str(patch.get("id") or "").strip()
        target = _patch_target(spec["nodes"], identifier, "node")
        allowed = NODE_PATCH_FIELDS
    elif target_type == "edge":
        identifier = str(patch.get("id") or "").strip()
        target = _patch_target(spec["edges"], identifier, "edge")
        allowed = EDGE_PATCH_FIELDS
    else:
        raise ValueError(f"unsupported visual patch target_type: {target_type!r}")
    forbidden = sorted(set(changes) - allowed)
    if forbidden:
        raise ValueError(
            f"visual patch cannot change scientific semantics; forbidden {target_type} fields: {', '.join(forbidden)}"
        )
    target.update(changes)


def apply_vector_feedback(candidate_dir: str | Path, feedback: str | Path) -> dict[str, Any]:
    """Apply a model's visual feedback without permitting semantic drift."""

    candidate = Path(candidate_dir).resolve()
    request = _request(candidate)
    feedback_path = Path(feedback)
    if not feedback_path.is_absolute():
        feedback_path = candidate / feedback_path
    response = _read_object(feedback_path)
    status = str(response.get("status") or "").strip().upper()
    if status not in {"PASS", "REVISE"}:
        raise ValueError("visual feedback status must be PASS or REVISE")
    checks = response.get("checks")
    if not isinstance(checks, dict):
        raise ValueError("visual feedback requires a checks object")
    missing_checks = [key for key in REQUIRED_FEEDBACK_CHECKS if key not in checks]
    if missing_checks:
        raise ValueError(f"visual feedback is missing checks: {', '.join(missing_checks)}")
    if status == "PASS" and any(not _is_pass(checks[key]) for key in REQUIRED_FEEDBACK_CHECKS):
        raise ValueError("visual feedback cannot be PASS while a required check is not PASS")

    patches = response.get("patches", [])
    if not isinstance(patches, list) or len(patches) > 50 or any(not isinstance(item, dict) for item in patches):
        raise ValueError("visual feedback patches must be a list of at most 50 objects")
    if status == "REVISE" and not patches:
        raise ValueError("REVISE feedback must contain at least one safe visual patch")

    history = _feedback_history(candidate)
    maximum_rounds = int(request.get("architecture_contract", {}).get("max_visual_feedback_rounds", 2))
    round_number = len(history) + 1
    if round_number > maximum_rounds:
        raise ValueError(f"visual feedback exceeds configured maximum of {maximum_rounds} rounds")

    source_ir = _resolve_render_ir(candidate)
    spec = deepcopy(_read_object(source_ir))
    for patch in patches:
        _apply_patch(spec, patch)
    refined = validate_figure_spec(spec)
    refined_path = candidate / "blueprint_ir.refined.json"
    _write_object(refined_path, refined)

    round_dir = candidate / "vector_feedback"
    _write_object(round_dir / f"round-{round_number:02d}-ir.json", refined)
    _write_object(round_dir / f"round-{round_number:02d}-response.json", response)
    manifest = build_vector_blueprint(candidate, ir=refined_path)

    round_record = {
        "round": round_number,
        "status": status,
        "checks": {key: str(checks[key]).upper() for key in REQUIRED_FEEDBACK_CHECKS},
        "observations": response.get("observations", []),
        "patch_count": len(patches),
        "ir": refined_path.name,
        "ir_sha256": _sha256(refined_path),
        "svg_sha256": manifest["sha256"]["svg"],
        "preview_sha256": manifest["sha256"]["preview"],
    }
    history.append(round_record)
    review = {
        "schema_version": VECTOR_BLUEPRINT_VERSION,
        "status": status,
        "candidate_id": request.get("candidate_id"),
        "latest_preview": manifest["preview"],
        "semantic_fields_locked": True,
        "rounds": history,
    }
    _write_object(candidate / "visual_feedback_review.json", review)
    return review


def write_vector_lineage(candidate_dir: str | Path, *, final_svg: str | Path = "figure.svg") -> dict[str, Any]:
    """Write the direct-vector provenance chain after final rendering."""

    candidate = Path(candidate_dir).resolve()
    request = _request(candidate)
    ir_path = _resolve_render_ir(candidate)
    spec = validate_figure_spec(_read_object(ir_path))
    resolved_spec, data_evidence = materialize_schematic_evidence(candidate, spec)
    if data_evidence["used"] and resolved_spec != spec:
        raise ValueError("authoritative schematic IR is not synchronized with its aggregate evidence binding")
    blueprint_svg = candidate / "blueprint.svg"
    feedback_path = candidate / "visual_feedback_review.json"
    final_path = Path(final_svg)
    if not final_path.is_absolute():
        final_path = candidate / final_path
    for name, path in (
        ("vector blueprint", blueprint_svg),
        ("visual feedback review", feedback_path),
        ("final vector", final_path),
    ):
        if not path.is_file():
            raise ValueError(f"cannot write vector lineage; {name} is missing: {path}")

    references: list[dict[str, Any]] = []
    for raw in request.get("reference_contract", {}).get("assets", []):
        if not isinstance(raw, dict) or raw.get("status") != "available" or not raw.get("resolved_path"):
            continue
        path = Path(str(raw["resolved_path"]))
        if path.is_file():
            references.append({"path": str(path.resolve()), "sha256": _sha256(path), "role": "visual_reference_only"})
    lineage = {
        "schema_version": VECTOR_BLUEPRINT_VERSION,
        "pipeline": "direct_vector",
        "candidate_id": request.get("candidate_id"),
        "artifact_chain": [
            "reference",
            *(["aggregate_data_evidence"] if data_evidence["used"] else []),
            "blueprint_ir",
            "vector_blueprint",
            "render_feedback",
            "vector_final",
        ],
        "references": references,
        "reference": references[0] if references else None,
        "blueprint_ir": {"path": ir_path.name, "sha256": _sha256(ir_path), "role": "authoritative_semantic_source"},
        "vector_blueprint": {"path": blueprint_svg.name, "sha256": _sha256(blueprint_svg)},
        "render_feedback": {"path": feedback_path.name, "sha256": _sha256(feedback_path)},
        "vector_final": {"path": final_path.name, "sha256": _sha256(final_path)},
        "blueprint_image_inputs": [],
        "prior_blueprint_image_input": False,
        "preview_role": "derived_from_vector_blueprint",
        "semantic_fields_locked": True,
        "aggregate_data_evidence": (
            {
                "binding": data_evidence["binding_file"],
                "bundle_snapshot": data_evidence["bundle_snapshot"],
                "bundle_sha256": data_evidence["bundle_sha256"],
                "selected_fact_count": data_evidence["selected_fact_count"],
                "aggregate_only": True,
            }
            if data_evidence["used"]
            else None
        ),
    }
    _write_object(candidate / "lineage_vector_v1.json", lineage)
    return lineage
