"""Candidate hard-gate validation and conservative automatic selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_config
from .img2ppt_pipeline import audit_img2ppt_pptx
from .svg import audit_svg

DIMENSION_WEIGHTS = {
    "scientific_integrity": 0.22,
    "legibility": 0.13,
    "editability": 0.12,
    "composition": 0.13,
    "aesthetics": 0.10,
    "reference_learning": 0.10,
    "reference_complexity": 0.12,
    "consistency": 0.08,
}


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _pass(value: Any) -> bool:
    return str(value or "").strip().lower() in {"pass", "passed", "verified", "true", "yes"}


def _dimension_scores(manifest: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    raw = manifest.get("scores", {})
    failures: list[str] = []
    scores: dict[str, float] = {}
    if not isinstance(raw, dict):
        return scores, ["scores must be an object"]
    for key in DIMENSION_WEIGHTS:
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 100:
            failures.append(f"missing or invalid score: {key}")
        else:
            scores[key] = float(value)
    return scores, failures


def _publication_process_failures(candidate_dir: Path, config: dict[str, Any]) -> list[str]:
    if config.get("quality_profile") != "publication":
        return []
    failures: list[str] = []
    required = ["reference_deconstruction.json", "complexity_audit.json"]
    if config.get("figure_kind") == "schematic":
        required.extend(["architecture_manifest.json", "architecture_guide.json"])
        if config.get("schematic_pipeline") == "direct_vector":
            required.extend(["vector_blueprint_manifest.json", "visual_feedback_review.json"])
        elif config.get("schematic_pipeline") == "img2ppt_hybrid":
            required.extend(
                [
                    "pre_conversion_review.json",
                    "reconstruction_spec.json",
                    "replacement_manifest.json",
                    "img2ppt_manifest.json",
                    "img2ppt_qa.json",
                    "post_conversion_review.json",
                ]
            )
        elif config.get("schematic_pipeline") == "high_resolution_raster":
            required.extend(
                ["raster_schematic_manifest.json", "raster_qa.json", "raster_visual_feedback_review.json"]
            )
        else:
            required.extend(["blueprint_manifest.json", "overlay_review.json"])
    records: dict[str, dict[str, Any]] = {}
    for name in required:
        path = candidate_dir / name
        if not path.is_file():
            failures.append(f"publication process artifact is missing: {name}")
            continue
        try:
            records[name] = _read_object(path)
        except ValueError as exc:
            failures.append(str(exc))

    complexity = records.get("complexity_audit.json")
    if complexity is not None:
        ratio = complexity.get("overall_ratio")
        minimum = float(config.get("complexity_gate", {}).get("minimum_ratio", 0.8))
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)):
            failures.append("complexity_audit.json overall_ratio is missing")
        elif float(ratio) < minimum:
            failures.append(f"reference complexity ratio {float(ratio):.2f} is below {minimum:.2f}")
        if config.get("complexity_gate", {}).get("require_visual_comparison") and not _pass(
            complexity.get("visual_comparison_status")
        ):
            failures.append("reference-vs-candidate visual comparison is not PASS")
    architecture = records.get("architecture_manifest.json")
    if architecture is not None and architecture.get("verified_against_source") is not True:
        failures.append("architecture manifest is not verified against model source")
    blueprint = records.get("blueprint_manifest.json")
    if blueprint is not None and not _pass(blueprint.get("status")):
        failures.append("whole-figure blueprint review is not PASS")
    overlay = records.get("overlay_review.json")
    if overlay is not None and not _pass(overlay.get("status")):
        failures.append("blueprint-to-vector overlay review is not PASS")
    vector_blueprint = records.get("vector_blueprint_manifest.json")
    if vector_blueprint is not None:
        if not _pass(vector_blueprint.get("status")):
            failures.append("direct-vector blueprint review is not PASS")
        if vector_blueprint.get("ai_raster_blueprint_used") is not False:
            failures.append("direct-vector candidate used an AI raster blueprint")
        gates = vector_blueprint.get("hard_gates")
        if not isinstance(gates, dict) or not gates or any(value is not True for value in gates.values()):
            failures.append("direct-vector blueprint hard gates are incomplete")
    visual_feedback = records.get("visual_feedback_review.json")
    if visual_feedback is not None:
        if not _pass(visual_feedback.get("status")):
            failures.append("rendered-vector visual feedback review is not PASS")
        if visual_feedback.get("semantic_fields_locked") is not True:
            failures.append("rendered-vector review did not lock semantic fields")
    for review_name in ("pre_conversion_review.json", "post_conversion_review.json"):
        review = records.get(review_name)
        if review is not None and not _pass(review.get("status")):
            failures.append(f"{review_name} is not PASS")
    img2ppt_manifest = records.get("img2ppt_manifest.json")
    if img2ppt_manifest is not None and not _pass(img2ppt_manifest.get("status")):
        failures.append("Img2PPT manifest is not PASS")
    img2ppt_qa = records.get("img2ppt_qa.json")
    if img2ppt_qa is not None and not _pass(img2ppt_qa.get("status")):
        failures.append("Img2PPT machine QA is not PASS")
    raster_manifest = records.get("raster_schematic_manifest.json")
    if raster_manifest is not None:
        if not _pass(raster_manifest.get("status")):
            failures.append("high-resolution raster manifest is not PASS")
        gates = raster_manifest.get("hard_gates")
        if not isinstance(gates, dict) or not gates or any(value is not True for value in gates.values()):
            failures.append("high-resolution raster hard gates are incomplete")
    raster_qa = records.get("raster_qa.json")
    if raster_qa is not None and not _pass(raster_qa.get("status")):
        failures.append("high-resolution raster QA is not PASS")
    raster_feedback = records.get("raster_visual_feedback_review.json")
    if raster_feedback is not None:
        if not _pass(raster_feedback.get("status")):
            failures.append("high-resolution raster visual review is not PASS")
        for key in ("ai_text_absent", "seams_clean", "annotations_legible", "scientific_structure_preserved"):
            if raster_feedback.get(key) is not True:
                failures.append(f"high-resolution raster review did not confirm {key}")
    return failures


def evaluate_candidate(candidate_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    candidate_path = candidate_dir / "candidate.json"
    failures: list[str] = []
    warnings: list[str] = []
    if not candidate_path.is_file():
        return {"candidate_id": candidate_dir.name, "status": "FAIL", "score": 0.0, "failures": ["candidate.json is missing"], "warnings": []}
    manifest = _read_object(candidate_path)
    candidate_id = str(manifest.get("candidate_id") or candidate_dir.name)
    raster_pipeline = config.get("figure_kind") == "schematic" and config.get("schematic_pipeline") == "high_resolution_raster"
    img2ppt_pipeline = config.get("figure_kind") == "schematic" and config.get("schematic_pipeline") == "img2ppt_hybrid"
    raster_audit: dict[str, Any] | None = None
    img2ppt_audit: dict[str, Any] | None = None
    svg_audit = None
    if raster_pipeline:
        raster_path = candidate_dir / str(manifest.get("png") or "figure.png")
        raster_manifest_path = candidate_dir / "raster_schematic_manifest.json"
        if not raster_path.is_file():
            failures.append("high-resolution raster candidate has no figure.png")
        if not raster_manifest_path.is_file():
            failures.append("high-resolution raster candidate has no raster_schematic_manifest.json")
        else:
            raster_audit = _read_object(raster_manifest_path)
            if not _pass(raster_audit.get("status")):
                failures.append("high-resolution raster manifest is not PASS")
            gates = raster_audit.get("hard_gates")
            if not isinstance(gates, dict) or not gates or any(value is not True for value in gates.values()):
                failures.append("high-resolution raster manifest hard gates are incomplete")
    elif img2ppt_pipeline:
        pptx_path = candidate_dir / str(manifest.get("pptx") or "figure.pptx")
        img2ppt_qa_path = candidate_dir / "img2ppt_qa.json"
        if not pptx_path.is_file():
            failures.append("Img2PPT candidate has no figure.pptx")
        else:
            img2ppt_audit = audit_img2ppt_pptx(pptx_path)
            failures.extend(img2ppt_audit["failures"])
        if not img2ppt_qa_path.is_file() or not _pass(_read_object(img2ppt_qa_path).get("status")):
            failures.append("Img2PPT machine QA is missing or not PASS")
    else:
        svg_raw = manifest.get("svg", "figure.svg")
        svg_path = candidate_dir / str(svg_raw)
        svg_audit = audit_svg(
            svg_path,
            allow_raster=bool(config.get("allow_raster_in_svg", False)),
            require_text=bool(config.get("editable_text", True)),
        )
        failures.extend(svg_audit.failures)
        warnings.extend(svg_audit.warnings)

    verification = manifest.get("verification", {})
    if not isinstance(verification, dict):
        failures.append("verification must be an object")
        verification = {}
    for key in ("scientific_status", "programmatic_status"):
        if not _pass(verification.get(key)):
            failures.append(f"{key} is not PASS")
    if config["figure_kind"] == "data" and not manifest.get("data_binding"):
        failures.append("data candidate has no data_binding evidence")
    figure_spec_source = (
        manifest.get("blueprint_ir")
        or manifest.get("figure_spec")
        or ("blueprint_ir.refined.json" if (candidate_dir / "blueprint_ir.refined.json").is_file() else None)
        or ("blueprint_ir.json" if (candidate_dir / "blueprint_ir.json").is_file() else None)
        or ("figure_spec.json" if (candidate_dir / "figure_spec.json").is_file() else None)
    )
    raster_source = manifest.get("annotation_source") or ("annotation_layout.json" if (candidate_dir / "annotation_layout.json").is_file() else None)
    if config["figure_kind"] == "schematic" and not (
        figure_spec_source or raster_source or manifest.get("scene_source") or manifest.get("source")
    ):
        failures.append("schematic candidate has no retained figure_spec, scene_source, or source")
    failures.extend(_publication_process_failures(candidate_dir, config))

    similarity = manifest.get("reference_similarity")
    if isinstance(similarity, bool) or not isinstance(similarity, (int, float)):
        failures.append("reference_similarity score is missing")
    elif float(similarity) > float(config["reference_guard"]["maximum_similarity"]):
        failures.append("candidate exceeds the maximum reference similarity")

    scores, score_failures = _dimension_scores(manifest)
    failures.extend(score_failures)
    layout_audit: dict[str, Any] | None = None
    if figure_spec_source and not raster_pipeline and not img2ppt_pipeline:
        layout_path = candidate_dir / "layout_report.json"
        if not layout_path.is_file():
            failures.append("FigureSpec candidate has no layout_report.json")
        else:
            layout_audit = _read_object(layout_path)
            if not _pass(layout_audit.get("status")):
                failures.extend(str(item) for item in layout_audit.get("failures", []) if str(item))
                if not layout_audit.get("failures"):
                    failures.append("FigureSpec layout audit is not PASS")
            warnings.extend(str(item) for item in layout_audit.get("warnings", []) if str(item))
            metrics = layout_audit.get("metrics", {})
            computed = metrics.get("computed_layout_score") if isinstance(metrics, dict) else None
            if isinstance(computed, (int, float)) and not isinstance(computed, bool):
                for dimension in ("legibility", "composition"):
                    if dimension in scores:
                        scores[dimension] = min(scores[dimension], float(computed))
    visual_judge = manifest.get("visual_judge")
    if config["auto_accept"]["require_visual_judge"] and not isinstance(visual_judge, dict):
        failures.append("visual_judge evidence is required for automatic selection")
    elif isinstance(visual_judge, dict) and not _pass(visual_judge.get("status")):
        failures.append("visual_judge status is not PASS")

    total = sum(scores.get(key, 0.0) * weight for key, weight in DIMENSION_WEIGHTS.items())
    return {
        "candidate_id": candidate_id,
        "status": "FAIL" if failures else "PASS",
        "score": round(total, 2),
        "scores": scores,
        "failures": failures,
        "warnings": warnings,
        "svg_audit": svg_audit.to_dict() if svg_audit is not None else None,
        "raster_audit": raster_audit,
        "img2ppt_audit": img2ppt_audit,
        "layout_audit": layout_audit,
    }


def _rank_figure(candidate_root: Path, config: dict[str, Any], review_mode: str) -> dict[str, Any]:
    candidate_ids = tuple("ABC"[: int(config["candidate_count"])])
    evaluations = [evaluate_candidate(candidate_root / name, config) for name in candidate_ids]
    passing = sorted((item for item in evaluations if item["status"] == "PASS"), key=lambda item: item["score"], reverse=True)
    selected: str | None = None
    reason = "manual review was requested"
    if review_mode == "auto":
        if not passing:
            reason = "no candidate passed all hard gates"
        else:
            first = passing[0]
            second_score = passing[1]["score"] if len(passing) > 1 else 0.0
            margin = first["score"] - second_score
            if first["score"] < float(config["auto_accept"]["minimum_score"]):
                reason = "top candidate is below the automatic acceptance score"
            elif margin < float(config["auto_accept"]["minimum_margin"]):
                reason = "top candidates are too close for a reliable automatic choice"
            else:
                selected = str(first["candidate_id"])
                reason = "top candidate passed all gates, score, and margin thresholds"
    return {
        "figure_id": config["figure_id"],
        "decision": "selected" if selected else "manual_review_required",
        "selected_candidate": selected,
        "reason": reason,
        "candidates": evaluations,
    }


def rank_job(job_dir: str | Path, *, write: bool = True) -> dict[str, Any]:
    job = Path(job_dir)
    config = load_config(job / "figmirror.config.json")
    candidates_root = job / "candidates"
    figure_results: list[dict[str, Any]] = []
    for figure in config["figures"]:
        figure_root = candidates_root / str(figure["figure_id"])
        if len(config["figures"]) == 1 and not figure_root.is_dir():
            figure_root = candidates_root
        figure_results.append(_rank_figure(figure_root, figure, str(config["review_mode"])))

    all_selected = all(item["decision"] == "selected" for item in figure_results)
    result: dict[str, Any] = {
        "schema_version": "0.2",
        "project_id": config["project_id"],
        "review_scope": "all_figures",
        "review_mode": config["review_mode"],
        "candidate_count": config["candidate_count"],
        "review_points": config["review_points"],
        "figure_count": len(figure_results),
        "decision": "selected" if all_selected else "manual_review_required",
        "selected_candidates": {item["figure_id"]: item["selected_candidate"] for item in figure_results},
        "figures": figure_results,
    }
    if len(figure_results) == 1:
        single = figure_results[0]
        result.update(
            {
                "figure_id": single["figure_id"],
                "selected_candidate": single["selected_candidate"],
                "reason": single["reason"],
                "candidates": single["candidates"],
            }
        )
    if write:
        (job / "ranking.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
