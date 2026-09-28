"""Configuration contract for FigMirror VNext jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIGURE_KINDS = {"data", "schematic"}
REVIEW_MODES = {"auto", "manual"}
REVIEW_POINTS = {"final_only", "blueprint_and_final"}
GENERATION_MODES = {"agent_native", "template_assisted"}
PANEL_COUNTS = {"auto", 2, 3, 4}
DATA_BACKENDS = {"matplotlib"}
SCHEMATIC_BACKENDS = {"figure_spec", "semantic_svg", "pptx", "canvas", "image_bootstrap"}
SCHEMATIC_PIPELINES = {"image_blueprint", "direct_vector", "high_resolution_raster", "img2ppt_hybrid"}
SHARED_FIGURE_KEYS = (
    "panel_count",
    "svg_required",
    "editable_text",
    "allow_raster_in_svg",
    "data_backend",
    "schematic_backend",
    "schematic_pipeline",
    "raster_schematic",
    "img2ppt",
    "auto_accept",
    "reference_guard",
    "quality_profile",
    "complexity_gate",
    "schematic_conversion",
)
QUALITY_PROFILES = {"prototype", "publication"}
SCHEMATIC_VECTORIZATION_MODES = {"module_locked", "free_redraw"}
SCHEMATIC_REVIEW_VIEWS = {
    "reference",
    "blueprint",
    "canvas-vector",
    "region-review",
    "ppt-modules",
    "native",
    "vector",
    "hybrid",
    "dual-review",
    "overlay",
    "raster-stitch",
    "raster-annotations",
    "raster-final",
    "img2ppt-source",
    "img2ppt-reconstruction",
    "img2ppt-replacements",
    "img2ppt-final",
}


class ConfigError(ValueError):
    """Raised when a FigMirror configuration violates the public contract."""


def _require_text(config: dict[str, Any], key: str, minimum: int = 1) -> None:
    value = config.get(key)
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise ConfigError(f"{key} must be text with at least {minimum} character(s)")


def _score(value: Any, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{key} must be a number")
    number = float(value)
    if not 0 <= number <= 100:
        raise ConfigError(f"{key} must be between 0 and 100")
    return number


def _normalize_shared(config: dict[str, Any]) -> dict[str, Any]:
    shared = dict(config)
    shared.setdefault("panel_count", "auto")
    shared.setdefault("schematic_pipeline", "img2ppt_hybrid")
    shared.setdefault("svg_required", shared["schematic_pipeline"] not in {"high_resolution_raster", "img2ppt_hybrid"})
    shared.setdefault("editable_text", shared["schematic_pipeline"] != "high_resolution_raster")
    shared.setdefault("allow_raster_in_svg", False)
    shared.setdefault("data_backend", "matplotlib")
    shared.setdefault("schematic_backend", "figure_spec")
    shared["raster_schematic"] = _normalize_raster_schematic(shared)
    shared["img2ppt"] = _normalize_img2ppt(shared)
    shared.setdefault("auto_accept", {})
    shared.setdefault("reference_guard", {})
    shared.setdefault("quality_profile", "publication")
    shared.setdefault("complexity_gate", {})
    if shared.get("panel_count") not in PANEL_COUNTS:
        raise ConfigError("panel_count must be auto, 2, 3, or 4")
    if shared.get("data_backend") not in DATA_BACKENDS:
        raise ConfigError("unsupported data_backend")
    if shared.get("schematic_backend") not in SCHEMATIC_BACKENDS:
        raise ConfigError("unsupported schematic_backend")
    if shared.get("schematic_pipeline") not in SCHEMATIC_PIPELINES:
        raise ConfigError(
            "schematic_pipeline must be image_blueprint, direct_vector, high_resolution_raster, or img2ppt_hybrid"
        )
    if shared.get("quality_profile") not in QUALITY_PROFILES:
        raise ConfigError("quality_profile must be prototype or publication")
    for key in ("svg_required", "editable_text", "allow_raster_in_svg"):
        if not isinstance(shared.get(key), bool):
            raise ConfigError(f"{key} must be true or false")

    auto_accept = shared["auto_accept"]
    if not isinstance(auto_accept, dict):
        raise ConfigError("auto_accept must be an object")
    auto_accept = dict(auto_accept)
    auto_accept.setdefault("minimum_score", 82)
    auto_accept.setdefault("minimum_margin", 4)
    auto_accept.setdefault("require_visual_judge", True)
    _score(auto_accept["minimum_score"], "auto_accept.minimum_score")
    _score(auto_accept["minimum_margin"], "auto_accept.minimum_margin")
    if not isinstance(auto_accept["require_visual_judge"], bool):
        raise ConfigError("auto_accept.require_visual_judge must be true or false")
    shared["auto_accept"] = auto_accept

    reference_guard = shared["reference_guard"]
    if not isinstance(reference_guard, dict):
        raise ConfigError("reference_guard must be an object")
    reference_guard = dict(reference_guard)
    reference_guard.setdefault("mechanisms_only", True)
    reference_guard.setdefault("maximum_similarity", 88)
    _score(reference_guard["maximum_similarity"], "reference_guard.maximum_similarity")
    if reference_guard["mechanisms_only"] is not True:
        raise ConfigError("reference_guard.mechanisms_only must remain true")
    shared["reference_guard"] = reference_guard

    complexity_gate = shared["complexity_gate"]
    if not isinstance(complexity_gate, dict):
        raise ConfigError("complexity_gate must be an object")
    complexity_gate = dict(complexity_gate)
    complexity_gate.setdefault("minimum_ratio", 0.80)
    complexity_gate.setdefault("require_reference_deconstruction", shared["quality_profile"] == "publication")
    complexity_gate.setdefault("require_visual_comparison", shared["quality_profile"] == "publication")
    complexity_gate.setdefault("allow_nested_subviews", True)
    ratio = complexity_gate["minimum_ratio"]
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 <= float(ratio) <= 1:
        raise ConfigError("complexity_gate.minimum_ratio must be between 0 and 1")
    for key in ("require_reference_deconstruction", "require_visual_comparison", "allow_nested_subviews"):
        if not isinstance(complexity_gate.get(key), bool):
            raise ConfigError(f"complexity_gate.{key} must be true or false")
    shared["complexity_gate"] = complexity_gate
    return shared


def _normalize_raster_schematic(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize the publication-raster contract used by schematic jobs."""

    raw = config.get("raster_schematic", {})
    if not isinstance(raw, dict):
        raise ConfigError("raster_schematic must be an object")
    raster = dict(raw)
    raster.setdefault("target_width_px", 5000)
    raster.setdefault("target_height_px", 3250)
    raster.setdefault("intended_width_cm", 18.0)
    raster.setdefault("target_ppi", 300)
    raster.setdefault("minimum_ppi", 72)
    raster.setdefault("generation_strategy", "auto")
    raster.setdefault("tile_threshold_px", 6000)
    raster.setdefault("tile_overlap_ratio", 0.12)
    raster.setdefault("tile_render_long_edge_px", 3072)
    raster.setdefault("maximum_upscale_factor", 1.6)
    raster.setdefault("maximum_overlap_mae", 0.22)
    raster.setdefault("master_composition_required", True)
    raster.setdefault("programmatic_annotations", True)
    raster.setdefault("ai_text_prohibited", True)
    raster.setdefault("preserve_tile_sources", True)

    for key in ("target_width_px", "target_height_px"):
        value = raster[key]
        if isinstance(value, bool) or not isinstance(value, int) or not 512 <= value <= 20000:
            raise ConfigError(f"raster_schematic.{key} must be an integer from 512 to 20000")
    target_ppi = raster["target_ppi"]
    minimum_ppi = raster["minimum_ppi"]
    for key, value in (("target_ppi", target_ppi), ("minimum_ppi", minimum_ppi)):
        if isinstance(value, bool) or not isinstance(value, int) or not 36 <= value <= 1200:
            raise ConfigError(f"raster_schematic.{key} must be an integer from 36 to 1200")
    if minimum_ppi > target_ppi:
        raise ConfigError("raster_schematic.minimum_ppi cannot exceed target_ppi")
    intended_width = raster["intended_width_cm"]
    if isinstance(intended_width, bool) or not isinstance(intended_width, (int, float)) or not 2 <= float(intended_width) <= 200:
        raise ConfigError("raster_schematic.intended_width_cm must be between 2 and 200")
    if raster["generation_strategy"] not in {"auto", "single_pass", "tiled_2x2"}:
        raise ConfigError("raster_schematic.generation_strategy must be auto, single_pass, or tiled_2x2")
    threshold = raster["tile_threshold_px"]
    if isinstance(threshold, bool) or not isinstance(threshold, int) or not 2048 <= threshold <= 20000:
        raise ConfigError("raster_schematic.tile_threshold_px must be an integer from 2048 to 20000")
    tile_edge = raster["tile_render_long_edge_px"]
    if isinstance(tile_edge, bool) or not isinstance(tile_edge, int) or not 1024 <= tile_edge <= 8192:
        raise ConfigError("raster_schematic.tile_render_long_edge_px must be an integer from 1024 to 8192")
    overlap = raster["tile_overlap_ratio"]
    if isinstance(overlap, bool) or not isinstance(overlap, (int, float)) or not 0.08 <= float(overlap) <= 0.25:
        raise ConfigError("raster_schematic.tile_overlap_ratio must be between 0.08 and 0.25")
    upscale = raster["maximum_upscale_factor"]
    if isinstance(upscale, bool) or not isinstance(upscale, (int, float)) or not 1.0 <= float(upscale) <= 4.0:
        raise ConfigError("raster_schematic.maximum_upscale_factor must be between 1.0 and 4.0")
    seam = raster["maximum_overlap_mae"]
    if isinstance(seam, bool) or not isinstance(seam, (int, float)) or not 0 <= float(seam) <= 1:
        raise ConfigError("raster_schematic.maximum_overlap_mae must be between 0 and 1")
    for key in (
        "master_composition_required",
        "programmatic_annotations",
        "ai_text_prohibited",
        "preserve_tile_sources",
    ):
        if not isinstance(raster[key], bool):
            raise ConfigError(f"raster_schematic.{key} must be true or false")
    if raster["programmatic_annotations"] is not True or raster["ai_text_prohibited"] is not True:
        raise ConfigError("publication raster schematics require programmatic annotations and prohibit AI text")
    return raster


def _normalize_img2ppt(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize the strict image-to-editable-PowerPoint hybrid contract."""

    raw = config.get("img2ppt", {})
    if not isinstance(raw, dict):
        raise ConfigError("img2ppt must be an object")
    contract = dict(raw)
    contract.setdefault("source_image_min_width_px", 1536)
    contract.setdefault("source_image_min_height_px", 864)
    contract.setdefault("require_pre_conversion_review", True)
    contract.setdefault("require_text_authority_map", True)
    contract.setdefault("require_topology_review", True)
    contract.setdefault("require_replacement_manifest", True)
    contract.setdefault("require_real_asset_replacement", True)
    contract.setdefault("minimum_real_replacements", 1)
    contract.setdefault("prohibit_full_slide_image", True)
    contract.setdefault("require_editable_text", True)
    contract.setdefault("require_editable_connectors", True)
    contract.setdefault("require_post_conversion_review", True)
    for key in ("source_image_min_width_px", "source_image_min_height_px"):
        value = contract[key]
        if isinstance(value, bool) or not isinstance(value, int) or not 512 <= value <= 20000:
            raise ConfigError(f"img2ppt.{key} must be an integer from 512 to 20000")
    count = contract["minimum_real_replacements"]
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 50:
        raise ConfigError("img2ppt.minimum_real_replacements must be between 0 and 50")
    for key in (
        "require_pre_conversion_review",
        "require_text_authority_map",
        "require_topology_review",
        "require_replacement_manifest",
        "require_real_asset_replacement",
        "prohibit_full_slide_image",
        "require_editable_text",
        "require_editable_connectors",
        "require_post_conversion_review",
    ):
        if not isinstance(contract[key], bool):
            raise ConfigError(f"img2ppt.{key} must be true or false")
    if contract["require_real_asset_replacement"] and count < 1:
        raise ConfigError("img2ppt.minimum_real_replacements must be at least 1 when replacement is required")
    if not all(contract[key] for key in (
        "require_pre_conversion_review",
        "require_replacement_manifest",
        "prohibit_full_slide_image",
        "require_editable_text",
        "require_editable_connectors",
        "require_post_conversion_review",
    )):
        raise ConfigError("publication Img2PPT safety and editability gates cannot be disabled")
    return contract


def _normalize_schematic_conversion(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize the blueprint-to-vector contract.

    Publication schematic candidates must remain isolated: one candidate may
    learn visual grammar from exactly one reference image, and no previous
    blueprint may silently enter the next image-generation request.
    """

    raw = config.get("schematic_conversion", {})
    if not isinstance(raw, dict):
        raise ConfigError("schematic_conversion must be an object")
    conversion = dict(raw)
    pipeline = str(config.get("schematic_pipeline") or "img2ppt_hybrid")
    direct_vector = pipeline == "direct_vector"
    raster_first = pipeline == "high_resolution_raster"
    img2ppt = pipeline == "img2ppt_hybrid"
    conversion.setdefault("reference_isolation", "single_reference_per_candidate")
    conversion.setdefault("allow_prior_blueprint_image_input", False)
    conversion.setdefault("require_candidate_lineage", True)
    conversion.setdefault("require_geometry_ir", not raster_first)
    conversion.setdefault("vectorization_mode", "module_locked")
    conversion.setdefault("require_svg_module_ids", not (raster_first or img2ppt))
    conversion.setdefault("direct_vector_ir", "blueprint_ir.json")
    conversion.setdefault("require_visual_feedback", True)
    conversion.setdefault("max_visual_feedback_rounds", 2)
    conversion.setdefault("selective_vectorization_max_regions", 8)
    conversion.setdefault(
        "required_review_views",
        ["reference", "blueprint", "vector"]
        if direct_vector
        else ["img2ppt-source", "img2ppt-reconstruction", "img2ppt-replacements", "img2ppt-final"]
        if img2ppt
        else ["reference", "blueprint", "raster-final"]
        if raster_first
        else ["reference", "blueprint", "vector", "overlay"],
    )
    if conversion["reference_isolation"] != "single_reference_per_candidate":
        raise ConfigError("schematic_conversion.reference_isolation must be single_reference_per_candidate")
    for key in (
        "allow_prior_blueprint_image_input",
        "require_candidate_lineage",
        "require_geometry_ir",
        "require_svg_module_ids",
        "require_visual_feedback",
    ):
        if not isinstance(conversion.get(key), bool):
            raise ConfigError(f"schematic_conversion.{key} must be true or false")
    if conversion["allow_prior_blueprint_image_input"]:
        raise ConfigError("schematic_conversion.allow_prior_blueprint_image_input must remain false")
    if conversion["vectorization_mode"] not in SCHEMATIC_VECTORIZATION_MODES:
        raise ConfigError("unsupported schematic_conversion.vectorization_mode")
    if conversion["direct_vector_ir"] != "blueprint_ir.json":
        raise ConfigError("schematic_conversion.direct_vector_ir must be blueprint_ir.json")
    feedback_rounds = conversion["max_visual_feedback_rounds"]
    if isinstance(feedback_rounds, bool) or not isinstance(feedback_rounds, int) or not 1 <= feedback_rounds <= 5:
        raise ConfigError("schematic_conversion.max_visual_feedback_rounds must be between 1 and 5")
    region_limit = conversion["selective_vectorization_max_regions"]
    if isinstance(region_limit, bool) or not isinstance(region_limit, int) or not 1 <= region_limit <= 20:
        raise ConfigError("schematic_conversion.selective_vectorization_max_regions must be between 1 and 20")
    views = conversion["required_review_views"]
    if (
        not isinstance(views, list)
        or len(views) != len(set(views))
        or any(item not in SCHEMATIC_REVIEW_VIEWS for item in views)
    ):
        raise ConfigError("schematic_conversion.required_review_views contains unsupported or duplicate views")
    conversion["required_review_views"] = list(views)
    return conversion


def _normalize_figure(raw: dict[str, Any], shared: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ConfigError(f"figures[{index}] must be an object")
    figure = {key: shared[key] for key in SHARED_FIGURE_KEYS}
    figure.update(raw)
    figure = _normalize_shared(figure)
    figure["schematic_conversion"] = _normalize_schematic_conversion(figure)
    _require_text(figure, "figure_id")
    _require_text(figure, "claim", minimum=12)
    if figure.get("figure_kind") not in FIGURE_KINDS:
        raise ConfigError(f"figures[{index}].figure_kind must be data or schematic")
    if figure["figure_kind"] == "data":
        if "svg_required" not in raw:
            figure["svg_required"] = True
        if "editable_text" not in raw:
            figure["editable_text"] = True
    elif figure["schematic_pipeline"] == "high_resolution_raster":
        if "svg_required" not in raw:
            figure["svg_required"] = False
        if "editable_text" not in raw:
            figure["editable_text"] = False
    elif figure["schematic_pipeline"] == "img2ppt_hybrid":
        if "schematic_backend" not in raw:
            figure["schematic_backend"] = "pptx"
        if "svg_required" not in raw:
            figure["svg_required"] = False
        if "editable_text" not in raw:
            figure["editable_text"] = True
    paths = figure.get("reference_assets", [])
    if not isinstance(paths, list) or any(not isinstance(item, str) for item in paths):
        raise ConfigError(f"figures[{index}].reference_assets must be a list of paths")
    source_data = figure.get("source_data", [])
    if not isinstance(source_data, list) or any(not isinstance(item, str) for item in source_data):
        raise ConfigError(f"figures[{index}].source_data must be a list of paths")
    if figure["figure_kind"] == "data" and not source_data:
        raise ConfigError(f"figures[{index}] is a data figure and requires source_data")
    data_evidence = figure.get("data_evidence", [])
    if not isinstance(data_evidence, list) or any(not isinstance(item, str) for item in data_evidence):
        raise ConfigError(f"figures[{index}].data_evidence must be a list of paths")
    if figure["figure_kind"] != "schematic" and data_evidence:
        raise ConfigError(f"figures[{index}].data_evidence is only valid for schematic figures")
    figure["reference_assets"] = paths
    figure["source_data"] = source_data
    figure["data_evidence"] = data_evidence
    return figure


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a batch-first FigMirror config.

    Legacy single-figure configs are accepted and normalized into a one-item
    ``figures`` list. New jobs should always use the batch form.
    """

    if not isinstance(config, dict):
        raise ConfigError("config root must be an object")
    normalized = dict(config)
    normalized.setdefault("schema_version", "0.4")
    normalized.setdefault("candidate_count", 2)
    normalized.setdefault("review_points", "final_only")
    normalized.setdefault("review_scope", "all_figures")
    normalized.setdefault("generation_mode", "agent_native")
    normalized["schematic_conversion"] = _normalize_schematic_conversion(normalized)
    if normalized.get("review_mode") not in REVIEW_MODES:
        raise ConfigError("review_mode must be auto or manual")
    if normalized.get("review_scope") != "all_figures":
        raise ConfigError("review_scope must be all_figures")
    candidate_count = normalized.get("candidate_count")
    if isinstance(candidate_count, bool) or candidate_count not in {2, 3}:
        raise ConfigError("candidate_count must be 2 or 3")
    if normalized.get("review_points") not in REVIEW_POINTS:
        raise ConfigError("review_points must be final_only or blueprint_and_final")
    if normalized.get("generation_mode") not in GENERATION_MODES:
        raise ConfigError("generation_mode must be agent_native or template_assisted")

    shared = _normalize_shared(normalized)
    raw_figures = normalized.get("figures")
    if raw_figures is None:
        raw_figures = [
            {
                key: normalized.get(key)
                for key in (
                    "figure_id",
                    "figure_kind",
                    "claim",
                    "panel_count",
                    "reference_assets",
                    "candidate_reference_assets",
                    "source_data",
                    "data_evidence",
                    "current_figure",
                    "current_figure_metadata",
                )
                if key in normalized
            }
        ]
    if not isinstance(raw_figures, list) or not raw_figures:
        raise ConfigError("figures must be a non-empty list")
    figures = [_normalize_figure(item, shared, index) for index, item in enumerate(raw_figures)]
    for figure in figures:
        figure["review_points"] = normalized["review_points"]
        figure["candidate_count"] = normalized["candidate_count"]
    ids = [str(figure["figure_id"]) for figure in figures]
    if len(ids) != len(set(ids)):
        raise ConfigError("figure_id values must be unique within a review batch")

    normalized.update({key: shared[key] for key in SHARED_FIGURE_KEYS})
    normalized["project_id"] = str(normalized.get("project_id") or ids[0])
    normalized["figures"] = figures
    return normalized


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {config_path}: {exc}") from exc
    return validate_config(raw)
