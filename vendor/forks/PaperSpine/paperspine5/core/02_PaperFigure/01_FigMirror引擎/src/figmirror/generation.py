"""Agent-native candidate planning and source-to-artifact finalization."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .config import load_config
from .data import sha256_file
from .evidence_bridge import materialize_schematic_evidence, validate_materialized_evidence_svg
from .figure_spec import render_figure_spec, validate_figure_spec
from .img2ppt_pipeline import finalize_img2ppt_candidate
from .panels import export_panels
from .raster_schematic import finalize_raster_candidate
from .svg import audit_svg, render_scene
from .vector_blueprint import write_vector_lineage

CANDIDATE_STRATEGIES: dict[str, tuple[dict[str, str], ...]] = {
    "schematic": (
        {
            "candidate_id": "A",
            "strategy": "direct-reading-path",
            "brief": "Prioritize the shortest defensible reading path from input through mechanism to outcome.",
        },
        {
            "candidate_id": "B",
            "strategy": "layered-mechanism",
            "brief": "Expose hierarchy, internal computation, and the relationship between layers or stages.",
        },
        {
            "candidate_id": "C",
            "strategy": "hero-plus-evidence",
            "brief": "Give the central mechanism visual priority and use supporting panels to explain or validate it.",
        },
    ),
    "data": (
        {
            "candidate_id": "A",
            "strategy": "direct-comparison",
            "brief": "Make the primary measured comparison and its uncertainty immediately readable.",
        },
        {
            "candidate_id": "B",
            "strategy": "distribution-and-pairing",
            "brief": "Preserve full distributions, pairing, grouping, and variation where the data supports them.",
        },
        {
            "candidate_id": "C",
            "strategy": "ranked-context-and-diagnostics",
            "brief": "Show the main result in ranked context and add only diagnostics that bound the claim.",
        },
    ),
}


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _asset_records(job: Path, paths: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            path = job / path
        record: dict[str, Any] = {"declared_path": raw, "resolved_path": str(path.resolve()), "status": "missing"}
        if path.is_file():
            record.update({"status": "available", "sha256": sha256_file(path), "bytes": path.stat().st_size})
        records.append(record)
    return records


def _candidate_reference_records(job: Path, figure: dict[str, Any], candidate_id: str) -> list[dict[str, Any]]:
    candidate_map = figure.get("candidate_reference_assets")
    raw_items: Any = candidate_map.get(candidate_id) if isinstance(candidate_map, dict) else None
    if not isinstance(raw_items, list) or not raw_items:
        raw_items = figure.get("reference_assets", [])
    records: list[dict[str, Any]] = []
    for raw_item in raw_items:
        payload = {"path": raw_item} if isinstance(raw_item, str) else dict(raw_item) if isinstance(raw_item, dict) else {}
        raw_path = str(payload.get("path") or "")
        if not raw_path:
            continue
        record = _asset_records(job, [raw_path])[0]
        record.update({key: value for key, value in payload.items() if key != "path"})
        records.append(record)
    return records


def _candidate_contract(
    figure: dict[str, Any],
    strategy: dict[str, str],
    references: list[dict[str, Any]],
    data_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    schematic = figure["figure_kind"] == "schematic"
    publication = figure["quality_profile"] == "publication"
    pipeline = str(figure["schematic_pipeline"])
    process_files = ["reference_deconstruction.json", "complexity_audit.json"] if publication else []
    if publication and not schematic:
        process_files.extend(["data_profile.json", "FIGURE_QA.json"])
    if publication and schematic:
        process_files.extend(["architecture_manifest.json", "architecture_guide.json"])
        if data_evidence:
            process_files.extend(["data_evidence_bundle.json", "schematic_evidence_binding.json"])
        if pipeline == "direct_vector":
            process_files.extend(["vector_blueprint_manifest.json", "visual_feedback_review.json"])
        elif pipeline == "img2ppt_hybrid":
            process_files.extend(
                [
                    "pre_conversion_review.json",
                    "reconstruction_spec.json",
                    "replacement_manifest.json",
                    "img2ppt_manifest.json",
                    "img2ppt_qa.json",
                    "post_conversion_review.json",
                ]
            )
        elif pipeline == "high_resolution_raster":
            process_files.extend(
                ["raster_schematic_manifest.json", "raster_qa.json", "raster_visual_feedback_review.json"]
            )
        else:
            process_files.extend(["blueprint_manifest.json", "overlay_review.json"])
    if schematic and pipeline == "direct_vector":
        schematic_instructions = [
            "For schematics, first write architecture_guide.json from verified sources; it defines the whole story, required modules, reading order, information budget, and prohibited inventions without fixing coordinates.",
            "Author blueprint_ir.json directly as the semantic FigureSpec: every module has a stable id, every label comes from verified sources, and every connector declares source and target.",
            "Run prepare-vector-blueprint so FigMirror deterministically creates blueprint.svg and blueprint_preview.png; the PNG is review evidence only and must never become the source of the final figure.",
            "Compare the reference with blueprint_preview.png using a multimodal model, return only allowlisted visual patches, and run apply-vector-feedback for at most the configured number of rounds.",
            "Keep scientific labels and edge topology locked during visual correction; use selective region vectorization only for approved organic assets that the semantic renderer cannot express cleanly.",
        ]
    elif schematic and pipeline == "img2ppt_hybrid":
        schematic_instructions = [
            "Generate source_image.png as the complete visual draft, then stop: no Image-to-PPT conversion may begin until pre_conversion_review.json passes scientific content, object inventory, topology, labels, reference transfer, AI text, source resolution, and replacement inventory.",
            "Write reconstruction_spec.json as the semantic object map. Rebuild all text, arrows, connectors, borders, frames, regular nodes, legends, and data callouts as native editable PowerPoint objects.",
            "Classify complex organic or textured objects that lose fidelity in native geometry. Crop or supply approved, candidate-local, text-free source assets and declare each asset, placement, provenance, and SHA-256 in replacement_manifest.json.",
            "After semantic reconstruction, genuinely replace every declared complex object with its real image asset. Never embed the full source image, never use a near-full-slide picture, and never rasterize text or directional annotations.",
            "Run assemble-img2ppt to audit editable text, native connectors, picture bounds, embedded asset hashes, and full-slide-image prohibition. Then inspect the rendered slide at page scale and close scale.",
            "post_conversion_review.json must pass scientific structure, editability, real replacement, crop correctness, image/text occlusion, placeholder absence, and final legibility before finalization.",
            "Retain source_image.png, reconstruction_spec.json, replacement_manifest.json, every replacement asset, figure.pptx, figure.png, machine QA, both reviews, and lineage_img2ppt_v1.json.",
        ]
    elif schematic and pipeline == "high_resolution_raster":
        schematic_instructions = [
            "For schematics, first write architecture_guide.json from verified sources; it defines the story, required objects, reading order, information budget, and prohibited inventions without fixing decorative details.",
            "Run prepare-raster-schematic to lock final pixel dimensions, physical-width PPI, the global composition contract, and the optional 2x2 overlap plan before generating image assets.",
            "Generate master_composition.png as a complete, text-free global layout. Learn object positions, hierarchy, reading order, and visual grammar from the reference, but redraw project-specific objects instead of copying the reference content.",
            "Use single_pass for ordinary schematics. Use tiled_2x2 only when organic or microscopic detail needs it; redraw all four master crops with the declared overlap and shared boundary context before stitching. Mechanically cutting an existing image never counts as added detail.",
            "Author every label, arrow, border, frame, legend, and aggregate-data callout in annotation_layout.json. Never ask the image model to render text or directional annotations.",
            "Run assemble-raster-schematic, inspect raster_qa.json, then review the final at page scale and 100% detail. raster_visual_feedback_review.json must explicitly pass AI-text absence, seam cleanliness, annotation legibility, and scientific structure.",
            "Retain the master, every tile, the editable annotation JSON, the stitched base, the annotation layer, prompts/provenance, and lineage_raster_v1.json. The publication artifact is PNG/TIFF; no final SVG is required.",
        ]
    else:
        schematic_instructions = [
            "For schematics, first write architecture_guide.json from verified sources; it defines the whole story, required modules, reading order, information budget, and prohibited inventions without fixing coordinates.",
            "Generate a complete candidate-specific blueprint.png from the architecture guide and this candidate's reference mechanisms; do not generate disconnected icon fragments.",
            "Record blueprint generation, coverage, arrow-direction, compactness, density, and reference-transfer evidence in blueprint_manifest.json; automatically compare candidates unless blueprint review was explicitly enabled.",
            "After structure freeze, reconstruct the blueprint module by module as editable vectors and author figure_spec.json with semantic groups, ports, edges, and panels.",
            "Run an overlay comparison between frozen blueprint and vector output; overlay_review.json must record structural drift and the automatic correction history.",
        ] if schematic else []
    if schematic and pipeline == "direct_vector" and figure["allow_raster_in_svg"]:
        schematic_instructions.extend(
            [
                "Hybrid mode is explicit: AI-generated raster assets may represent only declared non-text scientific illustrations whose texture or organic geometry materially benefits from image generation.",
                "Keep every label, arrow, border, frame, network node, legend, and data chart as live SVG; never ask the image generator to render them and never use a full-figure raster blueprint.",
                "Declare each permitted PNG/JPEG in FigureSpec assets with kind=raster and a scientific-illustration role; retain the source file, provenance, and node mapping for audit.",
            ]
        )
    story_contract = {
        key: figure[key]
        for key in (
            "decision",
            "figure_role",
            "scientific_question",
            "intended_conclusion",
            "claim_boundary",
            "results_units",
            "hero_panel",
            "panels",
        )
        if key in figure
    }
    return {
        "candidate_id": strategy["candidate_id"],
        "strategy": strategy["strategy"],
        "strategy_brief": strategy["brief"],
        "figure_id": figure["figure_id"],
        "figure_kind": figure["figure_kind"],
        "claim": figure["claim"],
        "story_contract": story_contract,
        "panel_count": figure["panel_count"],
        "authoring_contract": {
            "canonical_source": (
                "blueprint_ir.json (FigureSpec; preferred), figure_spec.json, scene.json, or source.py"
                if schematic and pipeline == "direct_vector"
                else "source_image.png + reconstruction_spec.json + replacement_manifest.json"
                if schematic and pipeline == "img2ppt_hybrid"
                else "master_composition.png + optional tiles/*.png + annotation_layout.json"
                if schematic and pipeline == "high_resolution_raster"
                else "figure_spec.json (preferred), scene.json, or source.py"
                if schematic
                else "source.py"
            ),
            "required_companion": (
                "raster_generation_plan.json + annotation_layout.json + panel_manifest.json"
                if schematic and pipeline == "high_resolution_raster"
                else "pre_conversion_review.json + post_conversion_review.json + img2ppt_qa.json"
                if schematic and pipeline == "img2ppt_hybrid"
                else "layout_report.json + panel_manifest.json"
                if schematic
                else "data_binding.json + panel_manifest.json"
            ),
            "required_outputs": (
                ["figure.png", "figure.tiff", "preview.png", "raster_qa.json"]
                if schematic and pipeline == "high_resolution_raster"
                else ["figure.pptx", "figure.png", "img2ppt_qa.json"]
                if schematic and pipeline == "img2ppt_hybrid"
                else ["figure.svg", "figure.pdf", "preview.png", *(["layout_report.json"] if schematic else [])]
            ),
            "editable_svg": pipeline not in {"high_resolution_raster", "img2ppt_hybrid"},
            "editable_pptx": pipeline == "img2ppt_hybrid",
            "editable_text": bool(figure["editable_text"]),
            "raster_in_svg": bool(figure["allow_raster_in_svg"]),
            "editable_annotation_source": pipeline == "high_resolution_raster",
            "final_vector_required": pipeline not in {"high_resolution_raster", "img2ppt_hybrid"},
            "hybrid_asset_policy": (
                {
                    "raster_scope": "declared non-text scientific illustration assets only",
                    "vector_required": ["text", "arrows", "borders", "frames", "network nodes", "legends", "data charts"],
                    "full_figure_raster_blueprint": False,
                }
                if figure["allow_raster_in_svg"]
                else None
            ),
            "required_process_files": process_files,
        },
        "reference_contract": {
            "one_to_one": bool(references),
            "assets": references,
            "required_deconstruction": bool(figure["complexity_gate"]["require_reference_deconstruction"]),
            "transfer_policy": "persuasion-mechanism-and-visual-grammar; never copy scientific values",
        },
        "complexity_contract": {
            "quality_profile": figure["quality_profile"],
            "minimum_ratio": float(figure["complexity_gate"]["minimum_ratio"]),
            "exportable_panel_range": [2, 4],
            "nested_subviews_allowed": bool(figure["complexity_gate"]["allow_nested_subviews"]),
            "dimensions": [
                "distinct_scientific_questions",
                "visual_grammars",
                "hierarchy_levels",
                "annotation_types",
                "linked_evidence_modes",
            ],
            "required_visual_comparison": bool(figure["complexity_gate"]["require_visual_comparison"]),
            "rule": "Match the reference's earned evidence density and hierarchy, not its decoration or raw panel count.",
        },
        "architecture_contract": (
            {
                "required_manifest": publication,
                "must_read_model_source": True,
                "pipeline": pipeline,
                "architecture_guide": "architecture_guide.json",
                "whole_figure_blueprint": (
                    "blueprint.svg"
                    if pipeline == "direct_vector"
                    else "source_image.png"
                    if pipeline == "img2ppt_hybrid"
                    else "master_composition.png"
                    if pipeline == "high_resolution_raster"
                    else "blueprint.png"
                ),
                "blueprint_ir": "blueprint_ir.json" if pipeline == "direct_vector" else None,
                "blueprint_preview": "blueprint_preview.png" if pipeline == "direct_vector" else None,
                "blueprint_manifest": (
                    "vector_blueprint_manifest.json"
                    if pipeline == "direct_vector"
                    else "img2ppt_manifest.json"
                    if pipeline == "img2ppt_hybrid"
                    else "raster_schematic_manifest.json"
                    if pipeline == "high_resolution_raster"
                    else "blueprint_manifest.json"
                ),
                "visual_feedback_review": (
                    "visual_feedback_review.json"
                    if pipeline == "direct_vector"
                    else "post_conversion_review.json"
                    if pipeline == "img2ppt_hybrid"
                    else "raster_visual_feedback_review.json"
                    if pipeline == "high_resolution_raster"
                    else None
                ),
                "overlay_review": "overlay_review.json" if pipeline == "image_blueprint" else None,
                "preview_role": (
                    "derived_from_hybrid_svg"
                    if pipeline == "direct_vector" and figure["allow_raster_in_svg"]
                    else "derived_from_svg_only"
                    if pipeline == "direct_vector"
                    else "rendered_from_editable_pptx_after_real_asset_replacement"
                    if pipeline == "img2ppt_hybrid"
                    else "locked_master_then_optional_overlap_redraw"
                    if pipeline == "high_resolution_raster"
                    else "raster_source"
                ),
                "max_visual_feedback_rounds": int(
                    figure.get("schematic_conversion", {}).get("max_visual_feedback_rounds", 2)
                ),
                "selective_vectorization_max_regions": int(
                    figure.get("schematic_conversion", {}).get("selective_vectorization_max_regions", 8)
                ),
                "human_pause": "blueprint" if figure.get("review_points") == "blueprint_and_final" else "none_before_final",
                "minimum_content": [
                    "verified input channels and shapes",
                    "actual computational modules and repeat counts",
                    "branches, fusion, residual or gating paths",
                    "output heads and training objectives when central",
                    "at least one evidence link when supported by project results",
                ],
            }
            if schematic
            else None
        ),
        "raster_contract": figure["raster_schematic"] if schematic and pipeline == "high_resolution_raster" else None,
        "img2ppt_contract": figure["img2ppt"] if schematic and pipeline == "img2ppt_hybrid" else None,
        "data_analysis_contract": (
            {
                "required_profile": publication,
                "profile_file": "data_profile.json",
                "binding_file": "data_binding.json",
                "required_disclosures": [
                    "statistical unit and repeated-measure status",
                    "source units or an explicit statement that units are unavailable",
                    "missing-data and filtering rules",
                    "grouping, pairing, and uncertainty definitions",
                    "statistical tests, effect sizes, and multiple-comparison handling",
                    "source file path, SHA-256, and aggregate-only privacy behavior when applicable",
                ],
                "rule": "Never infer clinical thresholds or units that are absent from the source.",
            }
            if not schematic
            else None
        ),
        "data_evidence_consumer_contract": (
            {
                "optional": True,
                "available": bool(data_evidence),
                "assets": data_evidence,
                "bundle_file": "data_evidence_bundle.json",
                "binding_file": "schematic_evidence_binding.json",
                "producer_command": "export-data-evidence",
                "consumer_command": "bind-schematic-evidence",
                "aggregate_only": True,
                "raw_row_access": False,
                "materialization": (
                    "exact display_text into programmatic annotation JSON"
                    if pipeline == "high_resolution_raster"
                    else "exact display_text into native editable PowerPoint text"
                    if pipeline == "img2ppt_hybrid"
                    else "exact display_text into live SVG label/detail fields"
                ),
                "visibility_gate": True,
                "rule": "Bind schematic nodes to published fact IDs; render the published display_text without paraphrasing; never recompute data-study statistics inside the schematic pipeline.",
            }
            if schematic
            else None
        ),
        "agent_instructions": [
            "Open the candidate-specific reference at page scale and close scale before selecting a visual grammar.",
            "Write reference_deconstruction.json before drawing: panel story, hero hierarchy, reading order, marks, annotations, transferable mechanisms, and rejected reference-specific content.",
            "Treat this strategy as a hypothesis, not a compulsory chart or layout template.",
            "Transfer the reference's persuasion mechanism; do not copy its labels or scientific content.",
            "Use two to four exportable panels, but allow scientifically earned nested subviews inside a panel when needed to match the reference's evidence density.",
            "Do not submit a cleaner but materially simpler figure: complexity_audit.json must meet the declared minimum ratio and record the visual comparison verdict.",
            "Keep every measured value bound to a declared source; clearly identify schematic content.",
            "When a schematic uses data-study results, consume only an aggregate schematic_evidence.json bundle through bind-schematic-evidence; map each evidence node to stable fact IDs, materialize the published display_text into the pipeline's programmatic text source, and preserve the bundle's scientific limits.",
            "For data figures, profile the source before choosing a chart; preserve the statistical unit, missingness, groups, pairing, units, uncertainty, tests, effect sizes, and multiple-comparison policy in data_binding.json and data_profile.json.",
            "When units, reference intervals, repeated-person identity, or clinical thresholds are absent, disclose the limitation instead of inventing metadata or cutoffs.",
            "For architecture figures, read the actual model source and record verified modules, connections, shapes, branches, repeats, heads, and objectives in architecture_manifest.json.",
            *schematic_instructions,
            "Do not hand-score composition before the pipeline QA passes; vector modes use layout_report.json, high-resolution raster mode uses pixel/seam gates, and Img2PPT uses pre-review, native-object, real-replacement, and post-review gates.",
            "Write the candidate-specific source into this directory and retain it with all exports.",
        ],
    }


def plan_agent_generation(job_dir: str | Path, *, write: bool = True) -> dict[str, Any]:
    """Create the configured number of authoring requests without a drawing repository."""

    job = Path(job_dir)
    config = load_config(job / "figmirror.config.json")
    candidate_ids = tuple("ABC"[: int(config["candidate_count"])])
    figures: list[dict[str, Any]] = []
    for figure in config["figures"]:
        candidate_requests: list[dict[str, Any]] = []
        for strategy in CANDIDATE_STRATEGIES[str(figure["figure_kind"])][: int(config["candidate_count"])]:
            references = _candidate_reference_records(job, figure, strategy["candidate_id"])
            data_evidence = _asset_records(job, figure["data_evidence"])
            request = _candidate_contract(figure, strategy, references, data_evidence)
            candidate_dir = job / "candidates" / str(figure["figure_id"]) / strategy["candidate_id"]
            request["candidate_dir"] = str(candidate_dir.resolve())
            if write:
                candidate_dir.mkdir(parents=True, exist_ok=True)
                (candidate_dir / "generation_request.json").write_text(
                    json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            candidate_requests.append(request)
        figures.append(
            {
                "figure_id": figure["figure_id"],
                "figure_kind": figure["figure_kind"],
                "claim": figure["claim"],
                "story_contract": {
                    key: figure[key]
                    for key in (
                        "decision",
                        "figure_role",
                        "scientific_question",
                        "intended_conclusion",
                        "claim_boundary",
                        "results_units",
                        "hero_panel",
                        "panels",
                    )
                    if key in figure
                },
                "references": _asset_records(job, figure["reference_assets"]),
                "candidate_references": {
                    candidate_id: _candidate_reference_records(job, figure, candidate_id)
                    for candidate_id in candidate_ids
                },
                "source_data": _asset_records(job, figure["source_data"]),
                "data_evidence": _asset_records(job, figure["data_evidence"]),
                "candidates": candidate_requests,
            }
        )
    result = {
        "schema_version": "0.4",
        "status": "READY",
        "project_id": config["project_id"],
        "generation_mode": config["generation_mode"],
        "candidate_count": config["candidate_count"],
        "review_points": config["review_points"],
        "automation_policy": {
            "architecture_direction": "automatic",
            "blueprint_selection": "human" if config["review_points"] == "blueprint_and_final" else "automatic",
            "vector_reconstruction": "automatic",
            "final_selection": "human",
            "exception_escalation": "human_on_hard_failure_or_unresolved_uncertainty",
        },
        "drawing_repository_required": False,
        "dependency_policy": {
            "external_repository": "optional-reference-only",
            "candidate_source": "required-and-retained",
            "stable_core": ["planning", "figure-spec", "layout", "routing", "rendering", "provenance", "audit", "export", "ranking"],
        },
        "figures": figures,
    }
    if write:
        (job / "generation_plan.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return result


def _write_full_exports(
    svg_path: Path,
    candidate_dir: Path,
    formats: tuple[str, ...],
    dpi: int,
    *,
    prefer_existing: bool = False,
) -> dict[str, str]:
    exports: dict[str, str] = {}
    if "svg" in formats:
        exports["svg"] = str(svg_path.resolve())
    png_path = candidate_dir / "preview.png"
    pdf_path = candidate_dir / "figure.pdf"
    needs_conversion = (
        ("png" in formats and not (prefer_existing and png_path.is_file() and png_path.stat().st_size > 0))
        or ("pdf" in formats and not (prefer_existing and pdf_path.is_file() and pdf_path.stat().st_size > 0))
    )
    if needs_conversion:
        try:
            import cairosvg
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("CairoSVG is required for PNG/PDF candidate exports") from exc
        svg_bytes = svg_path.read_bytes()
        if "png" in formats and not (prefer_existing and png_path.is_file() and png_path.stat().st_size > 0):
            cairosvg.svg2png(bytestring=svg_bytes, write_to=str(png_path), scale=dpi / 96)
        if "pdf" in formats and not (prefer_existing and pdf_path.is_file() and pdf_path.stat().st_size > 0):
            cairosvg.svg2pdf(bytestring=svg_bytes, write_to=str(pdf_path))
    if "png" in formats:
        exports["png"] = str(png_path.resolve())
    if "pdf" in formats:
        exports["pdf"] = str(pdf_path.resolve())
    return exports


def _process_artifacts(candidate: Path, request: dict[str, Any]) -> list[Path]:
    required = request.get("authoring_contract", {}).get("required_process_files", [])
    if not isinstance(required, list):
        raise ValueError("authoring_contract.required_process_files must be a list")
    paths: list[Path] = []
    records: dict[str, dict[str, Any]] = {}
    for name in required:
        path = candidate / str(name)
        if not path.is_file():
            raise ValueError(f"publication candidate requires {name}")
        records[str(name)] = _read_object(path)
        paths.append(path)

    deconstruction = records.get("reference_deconstruction.json")
    if deconstruction is not None:
        required_lists = ("reading_order", "panels", "transferable_mechanisms", "rejected_elements")
        if not str(deconstruction.get("claim") or "").strip() or not str(deconstruction.get("hero") or "").strip():
            raise ValueError("reference_deconstruction.json requires claim and hero")
        for key in required_lists:
            if not isinstance(deconstruction.get(key), list) or not deconstruction[key]:
                raise ValueError(f"reference_deconstruction.json requires a non-empty {key} list")

    complexity = records.get("complexity_audit.json")
    if complexity is not None:
        if str(complexity.get("status") or "").strip().lower() != "pass":
            raise ValueError("complexity_audit.json status must be PASS")
        ratio = complexity.get("overall_ratio")
        minimum = float(request.get("complexity_contract", {}).get("minimum_ratio", 0.0))
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 <= float(ratio) <= 1:
            raise ValueError("complexity_audit.json overall_ratio must be between 0 and 1")
        if float(ratio) < minimum:
            raise ValueError(f"candidate complexity ratio {float(ratio):.2f} is below the required {minimum:.2f}")
        if request.get("complexity_contract", {}).get("required_visual_comparison"):
            if str(complexity.get("visual_comparison_status") or "").strip().lower() != "pass":
                raise ValueError("complexity_audit.json visual_comparison_status must be PASS")
        for side in ("reference", "candidate"):
            profile = complexity.get(side)
            if not isinstance(profile, dict):
                raise ValueError(f"complexity_audit.json requires a {side} profile")
            for key in ("scientific_questions", "visual_grammars", "annotation_types"):
                if not isinstance(profile.get(key), list) or not profile[key]:
                    raise ValueError(f"complexity_audit.json {side}.{key} must be a non-empty list")

    architecture = records.get("architecture_manifest.json")
    if architecture is not None:
        if architecture.get("verified_against_source") is not True:
            raise ValueError("architecture_manifest.json must be verified_against_source")
        for key in ("source_files", "modules", "connections"):
            if not isinstance(architecture.get(key), list) or not architecture[key]:
                raise ValueError(f"architecture_manifest.json requires a non-empty {key} list")
    data_profile = records.get("data_profile.json")
    if data_profile is not None:
        rows = data_profile.get("rows")
        if isinstance(rows, bool) or not isinstance(rows, int) or rows <= 0:
            raise ValueError("data_profile.json requires a positive rows count")
        if not str(data_profile.get("statistical_unit") or "").strip():
            raise ValueError("data_profile.json requires statistical_unit")
        if not isinstance(data_profile.get("metrics"), list) or not data_profile["metrics"]:
            raise ValueError("data_profile.json requires a non-empty metrics list")
        source = data_profile.get("source")
        if not isinstance(source, dict) or not str(source.get("sha256") or "").strip():
            raise ValueError("data_profile.json requires a hashed source record")
    figure_qa = records.get("FIGURE_QA.json")
    if figure_qa is not None:
        if not str(figure_qa.get("status") or "").upper().startswith("PASS"):
            raise ValueError("FIGURE_QA.json must pass programmatic and scientific gates")
        for section in ("programmatic", "scientific", "visual"):
            if not isinstance(figure_qa.get(section), dict):
                raise ValueError(f"FIGURE_QA.json requires a {section} section")
    vector_blueprint = records.get("vector_blueprint_manifest.json")
    if vector_blueprint is not None:
        if str(vector_blueprint.get("pipeline") or "") != "direct_vector":
            raise ValueError("vector_blueprint_manifest.json pipeline must be direct_vector")
        if str(vector_blueprint.get("status") or "").strip().lower() != "pass":
            raise ValueError("vector_blueprint_manifest.json status must be PASS")
        if vector_blueprint.get("ai_raster_blueprint_used") is not False:
            raise ValueError("direct-vector candidates must not use an AI raster blueprint")
        gates = vector_blueprint.get("hard_gates")
        if not isinstance(gates, dict) or not gates or any(value is not True for value in gates.values()):
            raise ValueError("vector_blueprint_manifest.json hard_gates must all pass")
    visual_feedback = records.get("visual_feedback_review.json")
    if visual_feedback is not None:
        if str(visual_feedback.get("status") or "").strip().lower() != "pass":
            raise ValueError("visual_feedback_review.json status must be PASS")
        if visual_feedback.get("semantic_fields_locked") is not True:
            raise ValueError("visual_feedback_review.json must confirm semantic_fields_locked")
        if not isinstance(visual_feedback.get("rounds"), list) or not visual_feedback["rounds"]:
            raise ValueError("visual_feedback_review.json requires at least one completed feedback round")
    raster_manifest = records.get("raster_schematic_manifest.json")
    if raster_manifest is not None:
        if raster_manifest.get("pipeline") != "high_resolution_raster":
            raise ValueError("raster_schematic_manifest.json pipeline must be high_resolution_raster")
        if str(raster_manifest.get("status") or "").upper() != "PASS":
            raise ValueError("raster_schematic_manifest.json status must be PASS")
        gates = raster_manifest.get("hard_gates")
        if not isinstance(gates, dict) or not gates or any(value is not True for value in gates.values()):
            raise ValueError("raster_schematic_manifest.json hard_gates must all pass")
    raster_qa = records.get("raster_qa.json")
    if raster_qa is not None:
        if str(raster_qa.get("status") or "").upper() != "PASS":
            raise ValueError("raster_qa.json status must be PASS")
        gates = raster_qa.get("hard_gates")
        if not isinstance(gates, dict) or not gates or any(value is not True for value in gates.values()):
            raise ValueError("raster_qa.json hard_gates must all pass")
    raster_feedback = records.get("raster_visual_feedback_review.json")
    if raster_feedback is not None:
        if str(raster_feedback.get("status") or "").upper() != "PASS":
            raise ValueError("raster_visual_feedback_review.json status must be PASS")
        for key in ("ai_text_absent", "seams_clean", "annotations_legible", "scientific_structure_preserved"):
            if raster_feedback.get(key) is not True:
                raise ValueError(f"raster_visual_feedback_review.json must confirm {key}")
        if not isinstance(raster_feedback.get("rounds"), list) or not raster_feedback["rounds"]:
            raise ValueError("raster_visual_feedback_review.json requires at least one completed review round")
    return paths


def finalize_agent_candidate(
    candidate_dir: str | Path,
    *,
    formats: Iterable[str] | None = None,
    dpi: int = 300,
) -> dict[str, Any]:
    """Validate an agent-authored source and materialize editable exports.

    Data plotting code is deliberately not executed here. The agent runs and
    inspects its own source in the normal task sandbox; this step verifies the
    retained code, data binding, SVG, panel declarations, and final exports.
    """

    candidate = Path(candidate_dir)
    request = _read_object(candidate / "generation_request.json")
    figure_kind = str(request.get("figure_kind"))
    pipeline = str(request.get("architecture_contract", {}).get("pipeline") or "")
    allow_raster = bool(request.get("authoring_contract", {}).get("raster_in_svg", False))
    default_formats = (
        ("png", "tiff", "pdf")
        if figure_kind == "schematic" and pipeline == "high_resolution_raster"
        else ("pptx", "png")
        if figure_kind == "schematic" and pipeline == "img2ppt_hybrid"
        else ("svg", "png", "pdf")
    )
    requested_formats = tuple(dict.fromkeys(str(item).lower() for item in (formats or default_formats)))
    if dpi <= 0:
        raise ValueError("dpi must be positive")

    process_paths = _process_artifacts(candidate, request)
    if figure_kind == "schematic" and pipeline == "high_resolution_raster":
        return finalize_raster_candidate(candidate, request, process_paths, formats=requested_formats)
    if figure_kind == "schematic" and pipeline == "img2ppt_hybrid":
        return finalize_img2ppt_candidate(candidate, request, process_paths, formats=requested_formats)
    if not requested_formats or set(requested_formats) - {"svg", "png", "pdf"}:
        raise ValueError("formats must be a non-empty subset of svg,png,pdf")

    svg_path = candidate / "figure.svg"
    source_paths: list[Path]
    layout_result: dict[str, Any] | None = None
    data_evidence: dict[str, Any] | None = None
    if figure_kind == "schematic":
        refined_ir_path = candidate / "blueprint_ir.refined.json"
        blueprint_ir_path = candidate / "blueprint_ir.json"
        figure_spec_path = candidate / "figure_spec.json"
        scene_path = candidate / "scene.json"
        source_path = candidate / "source.py"
        evidence_ir_path = candidate / "blueprint_ir.evidence.json"
        semantic_ir_path = next(
            (path for path in (refined_ir_path, blueprint_ir_path, figure_spec_path, evidence_ir_path) if path.is_file()),
            None,
        )
        if semantic_ir_path is not None:
            authored_spec = validate_figure_spec(_read_object(semantic_ir_path))
            figure_spec, data_evidence = materialize_schematic_evidence(candidate, authored_spec)
            figure_spec = validate_figure_spec(figure_spec)
            render_source = semantic_ir_path
            evidence_paths: list[Path] = []
            if data_evidence["used"]:
                render_source = evidence_ir_path
                render_source.write_text(
                    json.dumps(figure_spec, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                evidence_paths = [
                    candidate / data_evidence["binding_file"],
                    candidate / data_evidence["bundle_snapshot"],
                ]
            layout_result = render_figure_spec(
                figure_spec,
                svg_path,
                layout_report=candidate / "layout_report.json",
                panel_manifest=candidate / "panel_manifest.json",
                asset_root=candidate,
                allow_raster=allow_raster,
            )
            evidence_svg = validate_materialized_evidence_svg(svg_path, data_evidence)
            data_evidence["svg_visibility"] = evidence_svg
            if not evidence_svg["verified"]:
                raise ValueError(f"materialized aggregate evidence is not fully visible in SVG: {evidence_svg['failures']}")
            source_paths = [
                semantic_ir_path,
                *([] if render_source == semantic_ir_path else [render_source]),
                *evidence_paths,
                *(Path(path) for path in layout_result.get("vector_assets", {}).values()),
                *(Path(path) for path in layout_result.get("raster_assets", {}).values()),
                *process_paths,
            ]
        elif scene_path.is_file():
            if (candidate / "schematic_evidence_binding.json").is_file():
                raise ValueError("schematic evidence bindings require a FigureSpec semantic IR")
            scene = _read_object(scene_path)
            render_scene(scene, svg_path)
            source_paths = [scene_path, *process_paths]
        elif source_path.is_file():
            if (candidate / "schematic_evidence_binding.json").is_file():
                raise ValueError("schematic evidence bindings require a FigureSpec semantic IR")
            if not svg_path.is_file():
                raise ValueError("run and inspect source.py before finalization; figure.svg is missing")
            source_paths = [source_path, *process_paths]
        else:
            raise ValueError("schematic candidate requires retained blueprint_ir.json, figure_spec.json, scene.json, or source.py")
    elif figure_kind == "data":
        source_path = candidate / "source.py"
        binding_path = candidate / "data_binding.json"
        if not source_path.is_file():
            raise ValueError("data candidate requires retained source.py")
        binding = _read_object(binding_path)
        if not isinstance(binding.get("source_files"), list) or not binding["source_files"]:
            raise ValueError("data_binding.json requires a non-empty source_files list")
        if not str(binding.get("statistical_unit") or "").strip():
            raise ValueError("data_binding.json requires statistical_unit")
        if not isinstance(binding.get("transformations"), list) or not binding["transformations"]:
            raise ValueError("data_binding.json requires a non-empty transformations list")
        if not str(binding.get("units") or "").strip():
            raise ValueError("data_binding.json requires units or an explicit unavailable statement")
        bound_sources: list[Path] = []
        for raw_source in binding["source_files"]:
            if not isinstance(raw_source, str) or not raw_source.strip():
                raise ValueError("data_binding.json source_files entries must be non-empty paths")
            bound = Path(raw_source)
            if not bound.is_absolute():
                bound = candidate / bound
            if not bound.is_file():
                raise ValueError(f"bound data source does not exist: {raw_source}")
            bound_sources.append(bound)
        if not svg_path.is_file():
            raise ValueError("run and inspect source.py before finalization; figure.svg is missing")
        source_paths = [source_path, binding_path, *bound_sources, *process_paths]
    else:
        raise ValueError(f"unsupported figure_kind in generation request: {figure_kind!r}")

    svg_audit = audit_svg(
        svg_path,
        allow_raster=allow_raster,
        require_text=bool(request.get("authoring_contract", {}).get("editable_text", True)),
    )
    if svg_audit.status != "PASS":
        raise ValueError(f"candidate SVG failed audit: {svg_audit.failures}")
    panel_result = export_panels(
        svg_path,
        candidate / "panel_manifest.json",
        candidate / "panels",
        formats=requested_formats,
        dpi=dpi,
        allow_raster=allow_raster,
    )
    full_exports = _write_full_exports(
        svg_path,
        candidate,
        requested_formats,
        dpi,
        prefer_existing=figure_kind == "data",
    )
    lineage: dict[str, Any] | None = None
    if (
        figure_kind == "schematic"
        and request.get("architecture_contract", {}).get("pipeline") == "direct_vector"
        and (candidate / "blueprint.svg").is_file()
        and (candidate / "visual_feedback_review.json").is_file()
    ):
        feedback_review = _read_object(candidate / "visual_feedback_review.json")
        if str(feedback_review.get("status") or "").strip().lower() == "pass":
            lineage = write_vector_lineage(candidate, final_svg=svg_path.resolve())
    result = {
        "schema_version": "0.3",
        "status": "PASS",
        "candidate_id": request.get("candidate_id"),
        "figure_id": request.get("figure_id"),
        "figure_kind": figure_kind,
        "generation_mode": "agent_native",
        "rendering_mode": "hybrid-raster-vector" if svg_audit.raster_image_count else "vector",
        "source_records": [
            {"path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in source_paths
        ],
        "svg_audit": svg_audit.to_dict(),
        "layout_audit": layout_result["layout_audit"] if layout_result else None,
        "data_evidence": data_evidence,
        "exports": full_exports,
        "panels": panel_result,
        "lineage": "lineage_vector_v1.json" if lineage else None,
        "next_gate": "scientific and visual QA, then candidate.json scoring",
    }
    (candidate / "authoring_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result
