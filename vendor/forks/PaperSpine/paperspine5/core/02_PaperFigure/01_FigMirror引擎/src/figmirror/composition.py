"""Component-level routing for mixed scientific figures.

``figure_kind`` identifies the primary evidence authority.  It does not ban
data panels from schematics or verified schematic insets from data figures.
Rendering is decided per region so that text-free complex visuals can remain
bounded image assets while labels, arrows, data marks, and geometry stay
native and editable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


REGION_ROLES = {"schematic", "data", "context", "background", "annotation"}
VISUAL_KINDS = {
    "native_geometry",
    "data_plot",
    "complex_background",
    "complex_object",
    "source_image",
}
REQUESTED_ROUTES = {"auto", "native", "generated", "source"}
RESOLVED_ROUTES = {"native_vector", "native_data_plot", "generated_asset", "verified_source_asset", "blocked"}
IMAGE_ROUTES = {"generated_asset", "verified_source_asset"}


def make_composition_contract(
    *,
    figure_kind: str,
    image_generation: dict[str, Any],
    composition: dict[str, Any],
    data_evidence_available: bool,
    source_data_available: bool,
) -> dict[str, Any]:
    """Build the immutable routing rules embedded in a generation request."""

    return {
        "schema_version": "0.1",
        "primary_evidence_authority": figure_kind,
        "figure_kind_is_not_content_exclusive": True,
        "allowed_region_roles": sorted(REGION_ROLES),
        "allowed_routes": sorted(RESOLVED_ROUTES - {"blocked"}),
        "image_generation": {
            "available": bool(image_generation.get("available", False)),
            "backend": image_generation.get("backend"),
            "fallback": "native_only",
        },
        "evidence": {
            "aggregate_data_bundle_available": bool(data_evidence_available),
            "source_data_available": bool(source_data_available),
        },
        "rules": {
            "route_each_region_independently": True,
            "data_marks_must_be_native": True,
            "text_arrows_borders_legends_must_be_native": True,
            "whole_figure_image_prohibited": True,
            "image_assets_must_be_text_free": True,
            "image_assets_require_native_overlays": True,
            "max_image_region_area_ratio": float(composition["max_image_region_area_ratio"]),
            "generated_assets_are_clean_bases_not_finished_panels": True,
            "generated_assets_are_scaled_inside_declared_bbox": True,
            "img2ppt_is_not_a_fallback": True,
        },
    }


def _bbox(value: Any, label: str) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value)
    ):
        raise ValueError(f"{label} must be [x,y,width,height] in normalized coordinates")
    x, y, width, height = (float(item) for item in value)
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1.000001 or y + height > 1.000001:
        raise ValueError(f"{label} must remain inside the normalized page")
    return [x, y, width, height]


def _route_region(region: dict[str, Any], contract: dict[str, Any]) -> tuple[str, list[str]]:
    role = str(region.get("role") or "").strip()
    visual_kind = str(region.get("visual_kind") or "").strip()
    requested = str(region.get("requested_route") or "auto").strip()
    native_fallback = region.get("native_fallback", True)
    failures: list[str] = []

    if role not in REGION_ROLES:
        failures.append(f"unsupported role {role!r}")
    if visual_kind not in VISUAL_KINDS:
        failures.append(f"unsupported visual_kind {visual_kind!r}")
    if requested not in REQUESTED_ROUTES:
        failures.append(f"unsupported requested_route {requested!r}; Img2PPT is never a component route")
    if not isinstance(native_fallback, bool):
        failures.append("native_fallback must be true or false")
        native_fallback = False
    if failures:
        return "blocked", failures

    image_available = bool(contract["image_generation"]["available"])
    has_source = bool(str(region.get("asset") or "").strip())
    complex_visual = visual_kind in {"complex_background", "complex_object", "source_image"}

    if role == "data" or visual_kind == "data_plot":
        if requested in {"generated", "source"}:
            return "blocked", ["data regions must remain native data plots"]
        authority = contract["primary_evidence_authority"]
        evidence = contract["evidence"]
        if authority == "schematic" and not (
            evidence["aggregate_data_bundle_available"] or evidence["source_data_available"]
        ):
            return "blocked", ["a data inset in a schematic requires declared aggregate evidence or source data"]
        return "native_data_plot", []

    if role == "annotation" or not complex_visual:
        if requested in {"generated", "source"}:
            return "blocked", ["text, annotations, and regular geometry must remain native"]
        return "native_vector", []

    if requested == "native":
        return "native_vector", []
    if requested == "source" or (requested == "auto" and has_source):
        if not has_source:
            return ("native_vector", []) if native_fallback else ("blocked", ["source route requires asset"])
        return "verified_source_asset", []
    if requested == "generated" or requested == "auto":
        if image_available:
            return "generated_asset", []
        if native_fallback:
            return "native_vector", []
        return "blocked", ["image generation is unavailable and this region disallows native fallback"]
    return "blocked", ["region could not be routed"]


def build_component_routing_plan(
    regions: list[dict[str, Any]],
    contract: dict[str, Any],
    *,
    asset_root: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve a region inventory into auditable native/image routes."""

    if not isinstance(regions, list):
        raise ValueError("composition regions must be a list")
    resolved: list[dict[str, Any]] = []
    failures: list[str] = []
    seen: set[str] = set()
    max_area = float(contract["rules"]["max_image_region_area_ratio"])
    root = Path(asset_root).resolve() if asset_root is not None else None

    for index, raw in enumerate(regions):
        if not isinstance(raw, dict):
            failures.append(f"regions[{index}] must be an object")
            continue
        region = dict(raw)
        region_id = str(region.get("id") or "").strip()
        if not region_id or region_id in seen:
            failures.append(f"regions[{index}] requires a unique id")
            continue
        seen.add(region_id)
        try:
            bbox = _bbox(region.get("bbox"), f"region {region_id} bbox")
        except ValueError as exc:
            failures.append(str(exc))
            continue
        route, route_failures = _route_region(region, contract)
        failures.extend(f"region {region_id}: {item}" for item in route_failures)
        record = {
            "id": region_id,
            "role": str(region.get("role") or ""),
            "visual_kind": str(region.get("visual_kind") or ""),
            "bbox": bbox,
            "requested_route": str(region.get("requested_route") or "auto"),
            "resolved_route": route,
            "native_fallback": bool(region.get("native_fallback", True)),
            "scientific_source": str(region.get("scientific_source") or "").strip() or None,
            "asset": str(region.get("asset") or "").strip() or None,
            "contains_text": bool(region.get("contains_text", False)),
            "native_overlay": bool(region.get("native_overlay", route in IMAGE_ROUTES)),
            "asset_treatment": (
                "text_free_clean_base_scaled_inside_bbox" if route in IMAGE_ROUTES else None
            ),
        }
        if record["role"] == "schematic" and contract["primary_evidence_authority"] == "data" and not record["scientific_source"]:
            failures.append(f"region {region_id}: schematic inset in a data figure requires scientific_source")
        if route in IMAGE_ROUTES:
            area = bbox[2] * bbox[3]
            if area > max_area:
                failures.append(
                    f"region {region_id}: image area ratio {area:.3f} exceeds bounded limit {max_area:.3f}"
                )
            if record["contains_text"]:
                failures.append(f"region {region_id}: image assets must be text-free")
            if not record["native_overlay"]:
                failures.append(f"region {region_id}: image assets require native overlays")
            if route == "verified_source_asset" and root is not None and record["asset"]:
                asset = (root / record["asset"]).resolve()
                try:
                    asset.relative_to(root)
                except ValueError:
                    failures.append(f"region {region_id}: source asset is outside the candidate directory")
                else:
                    if not asset.is_file():
                        failures.append(f"region {region_id}: source asset is missing")
        resolved.append(record)

    modes = sorted({str(item["role"]) for item in resolved if item["role"] in {"schematic", "data"}})
    status = "BLOCKED" if failures or any(item["resolved_route"] == "blocked" for item in resolved) else "PASS"
    if not resolved:
        status = "AWAITING_DECOMPOSITION"
    return {
        "schema_version": "0.1",
        "status": status,
        "primary_evidence_authority": contract["primary_evidence_authority"],
        "evidence_modes": modes,
        "mixed_evidence_figure": modes == ["data", "schematic"],
        "regions": resolved,
        "failures": failures,
        "fallback": {
            "activated": not contract["image_generation"]["available"],
            "mode": "native_only",
            "img2ppt_used": False,
        },
    }


def validate_composition_plan(
    plan: dict[str, Any],
    contract: dict[str, Any],
    *,
    asset_root: str | Path | None = None,
) -> dict[str, Any]:
    """Recompute and verify an authored composition plan against its request."""

    if not isinstance(plan, dict):
        raise ValueError("composition_plan.json root must be an object")
    raw_regions = plan.get("regions")
    rebuilt = build_component_routing_plan(raw_regions, contract, asset_root=asset_root)
    if rebuilt["status"] != "PASS":
        raise ValueError("composition plan failed: " + "; ".join(rebuilt["failures"] or [rebuilt["status"]]))
    declared = plan.get("status")
    if declared is not None and str(declared).upper() != "PASS":
        raise ValueError("composition_plan.json status must be PASS")
    declared_routes = {
        str(item.get("id")): str(item.get("resolved_route"))
        for item in raw_regions
        if isinstance(item, dict) and item.get("resolved_route") is not None
    }
    for item in rebuilt["regions"]:
        declared_route = declared_routes.get(item["id"])
        if declared_route is not None and declared_route != item["resolved_route"]:
            raise ValueError(
                f"composition region {item['id']} declares {declared_route} but resolves to {item['resolved_route']}"
            )
    return rebuilt
