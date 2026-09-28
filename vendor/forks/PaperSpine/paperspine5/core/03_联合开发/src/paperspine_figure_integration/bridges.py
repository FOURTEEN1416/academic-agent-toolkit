"""File and CLI bridges to the unchanged PaperSpine4 and FigMirror implementations."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .contracts import ContractError, load_json, validate_figure_requests, write_json_atomic


class BridgeError(RuntimeError):
    """Raised when an external project boundary rejects an operation."""


def _run_json(
    command: list[str], *, cwd: Path, accept_json_failure: bool = False
) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env=environment,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise BridgeError(detail) from exc
        raise BridgeError(f"boundary command did not return JSON: {' '.join(command)}") from exc
    if not isinstance(payload, dict):
        raise BridgeError("boundary command returned a non-object JSON value")
    if result.returncode != 0 and not accept_json_failure:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise BridgeError(detail)
    return payload


class PublicationCycleBridge:
    """Stable JSON bridge to PaperSpine's local-only publication cycle."""

    OPERATIONS = {
        "profile_check",
        "assemble",
        "rebuttal_check",
        "rebuttal_render",
        "transfer_plan",
    }

    def __init__(self, job: dict[str, Any]) -> None:
        self.job = job
        self.script = Path(job["publication"]["script"])
        self.invocation_dir = Path(job["publication"]["invocation_dir"])
        self._descriptor: dict[str, Any] | None = None

    def describe(self) -> dict[str, Any]:
        if self._descriptor is None:
            payload = _run_json(
                [sys.executable, str(self.script), "describe"],
                cwd=Path(self.job["project_root"]),
            )
            if payload.get("contract") != "paperspine.publication-cycle.interface":
                raise BridgeError("publication-cycle descriptor contract is unsupported")
            if payload.get("interface_version") != "1.0":
                raise BridgeError("publication-cycle interface_version must be 1.0")
            operations = {
                item.get("id")
                for item in payload.get("operations", [])
                if isinstance(item, dict)
            }
            if operations != self.OPERATIONS:
                raise BridgeError("publication-cycle descriptor does not expose the five stable operations")
            self._descriptor = payload
        return self._descriptor

    def invoke(self, request_path: Path) -> dict[str, Any]:
        payload = _run_json(
            [sys.executable, str(self.script), "invoke", str(request_path)],
            cwd=request_path.parent,
            accept_json_failure=True,
        )
        if payload.get("contract") != "paperspine.publication-cycle.result":
            raise BridgeError("publication-cycle result contract is unsupported")
        if payload.get("interface_version") != "1.0":
            raise BridgeError("publication-cycle result interface_version must be 1.0")
        if payload.get("operation") not in self.OPERATIONS:
            raise BridgeError("publication-cycle result operation is unsupported")
        signals = payload.get("signals")
        authority = payload.get("authority_boundary")
        if not isinstance(signals, dict) or signals.get("external_action_authorized") is not False:
            raise BridgeError("publication-cycle result crossed the external-action authority boundary")
        if not isinstance(authority, dict) or authority.get("external_action_authorized") is not False:
            raise BridgeError("publication-cycle authority boundary is missing or unsafe")
        if not isinstance(payload.get("ok"), bool):
            raise BridgeError("publication-cycle result ok must be boolean")
        return payload


class PaperSpineBridge:
    def __init__(self, job: dict[str, Any]) -> None:
        self.job = job
        self.output_dir = Path(job["paper"]["output_dir"])
        self.progress_script = Path(job["paper"]["progress_script"])

    @property
    def request_path(self) -> Path:
        return self.output_dir / self.job["paper"]["figure_requests"]

    def progress_snapshot(self) -> dict[str, Any]:
        return _run_json(
            [sys.executable, str(self.progress_script), str(self.output_dir), "--json"],
            cwd=Path(self.job["project_root"]),
        )

    def validate_handoff(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self.output_dir.is_dir():
            raise ContractError(f"PaperSpine output directory does not exist: {self.output_dir}")
        missing = [name for name in self.job["paper"]["required_artifacts"] if not (self.output_dir / name).is_file()]
        if missing:
            raise ContractError(f"PaperSpine figure handoff is too early; missing artifacts: {missing}")
        requests = validate_figure_requests(load_json(self.request_path))
        project_root = Path(self.job["project_root"]).resolve()
        for figure in requests["figures"]:
            for field in (
                "source_data",
                "data_evidence",
                "reference_assets",
                "candidate_reference_assets",
            ):
                resolved_assets: list[str] = []
                for declared in figure.get(field, []):
                    candidate = Path(declared)
                    if not candidate.is_absolute():
                        candidate = project_root / candidate
                    candidate = candidate.resolve()
                    try:
                        candidate.relative_to(project_root)
                    except ValueError as exc:
                        raise ContractError(f"{figure['figure_id']} {field} escapes project_root: {candidate}") from exc
                    if not candidate.is_file():
                        raise ContractError(f"{figure['figure_id']} {field} does not exist: {candidate}")
                    resolved_assets.append(str(candidate))
                figure[field] = resolved_assets
            if figure.get("current_figure"):
                current = Path(figure["current_figure"])
                if not current.is_absolute():
                    current = project_root / current
                current = current.resolve()
                try:
                    current.relative_to(project_root)
                except ValueError as exc:
                    raise ContractError(
                        f"{figure['figure_id']} current_figure escapes project_root: {current}"
                    ) from exc
                if not current.is_file():
                    raise ContractError(
                        f"{figure['figure_id']} current_figure does not exist: {current}"
                    )
                figure["current_figure"] = str(current)
        return requests, self.progress_snapshot()


class FigMirrorBridge:
    def __init__(self, job: dict[str, Any]) -> None:
        self.job = job
        self.job_dir = Path(job["figure"]["job_dir"])
        self.cli = Path(job["figure"]["figmirror_cli"])

    def _command(self, *parts: str) -> dict[str, Any]:
        return _run_json([sys.executable, str(self.cli), *parts], cwd=Path(self.job["project_root"]))

    def prepare(self, requests: dict[str, Any]) -> dict[str, Any]:
        self.job_dir.mkdir(parents=True, exist_ok=True)
        figure_settings = self.job["figure"]
        schematic_pipeline = (
            "direct_vector" if figure_settings.get("preferred_format") == "svg" else "img2ppt_hybrid"
        )
        figures: list[dict[str, Any]] = []
        for item in requests["figures"]:
            record = {
                "figure_id": item["figure_id"],
                "figure_kind": item["figure_kind"],
                "claim": item["claim"],
                "source_data": item.get("source_data", []),
                "data_evidence": item.get("data_evidence", []),
                "reference_assets": item.get("reference_assets", []),
            }
            for optional in (
                "candidate_reference_assets",
                "current_figure",
                "current_figure_metadata",
                "panel_count",
                "decision",
                "figure_role",
                "scientific_question",
                "intended_conclusion",
                "claim_boundary",
                "results_units",
                "hero_panel",
                "panels",
            ):
                if optional in item:
                    record[optional] = item[optional]
            figures.append(record)
        config = {
            "schema_version": "0.5",
            "project_id": requests["paper_id"],
            "generation_mode": "agent_native",
            "review_mode": figure_settings["review_mode"],
            "review_points": figure_settings["review_points"],
            "review_scope": "all_figures",
            "candidate_count": figure_settings["candidate_count"],
            "quality_profile": figure_settings["quality_profile"],
            "panel_count": "auto",
            "svg_required": schematic_pipeline not in {"high_resolution_raster", "img2ppt_hybrid"},
            "editable_text": schematic_pipeline != "high_resolution_raster",
            "allow_raster_in_svg": False,
            "data_backend": "matplotlib",
            "schematic_backend": "pptx" if schematic_pipeline == "img2ppt_hybrid" else "figure_spec",
            "schematic_pipeline": schematic_pipeline,
            "auto_accept": figure_settings.get(
                "auto_accept", {"minimum_score": 82, "minimum_margin": 4, "require_visual_judge": True}
            ),
            "reference_guard": {"mechanisms_only": True, "maximum_similarity": 88},
            "schematic_conversion": {
                "reference_isolation": "single_reference_per_candidate",
                "allow_prior_blueprint_image_input": False,
                "require_candidate_lineage": figure_settings["require_candidate_lineage"],
                "require_geometry_ir": schematic_pipeline != "high_resolution_raster",
                "vectorization_mode": "module_locked",
                "require_svg_module_ids": schematic_pipeline not in {"high_resolution_raster", "img2ppt_hybrid"},
                "required_review_views": (
                    ["reference", "blueprint", "vector"]
                    if schematic_pipeline == "direct_vector"
                    else ["img2ppt-source", "img2ppt-reconstruction", "img2ppt-replacements", "img2ppt-final"]
                    if schematic_pipeline == "img2ppt_hybrid"
                    else ["reference", "blueprint", "raster-final"]
                ),
            },
            "img2ppt": {
                "source_image_min_width_px": 1536,
                "source_image_min_height_px": 864,
                "require_pre_conversion_review": True,
                "require_text_authority_map": True,
                "require_topology_review": True,
                "require_replacement_manifest": True,
                "require_real_asset_replacement": True,
                "minimum_real_replacements": 1,
                "prohibit_full_slide_image": True,
                "require_editable_text": True,
                "require_editable_connectors": True,
                "require_post_conversion_review": True,
            },
            "raster_schematic": {
                "target_width_px": 5000,
                "target_height_px": 3250,
                "intended_width_cm": 18.0,
                "target_ppi": 300,
                "minimum_ppi": 72,
                "generation_strategy": "auto",
                "tile_threshold_px": 6000,
                "tile_overlap_ratio": 0.12,
                "tile_render_long_edge_px": 3072,
            },
            "figures": figures,
        }
        write_json_atomic(self.job_dir / "figmirror.config.json", config)
        normalized = self._command("validate-config", str(self.job_dir / "figmirror.config.json"))
        plan = self._command("plan-agent", str(self.job_dir))
        return {"normalized_config": normalized, "generation_plan": plan}

    def candidates_ready(self, requests: dict[str, Any]) -> tuple[bool, list[str]]:
        missing: list[str] = []
        count = int(self.job["figure"]["candidate_count"])
        config_path = self.job_dir / "figmirror.config.json"
        config = load_json(config_path) if config_path.is_file() else {}
        configured_figures = {
            str(item.get("figure_id")): item
            for item in config.get("figures", [])
            if isinstance(item, dict) and item.get("figure_id")
        }
        for figure in requests["figures"]:
            configured = configured_figures.get(figure["figure_id"], {})
            raster_first = (
                figure["figure_kind"] == "schematic"
                and configured.get("schematic_pipeline", config.get("schematic_pipeline")) == "high_resolution_raster"
            )
            img2ppt = (
                figure["figure_kind"] == "schematic"
                and configured.get("schematic_pipeline", config.get("schematic_pipeline")) == "img2ppt_hybrid"
            )
            final_artifacts = ("figure.png", "figure.pptx") if img2ppt else ("figure.png",) if raster_first else ("figure.svg",)
            for candidate_id in "ABC"[:count]:
                candidate = self.job_dir / "candidates" / figure["figure_id"] / candidate_id
                for name in ("candidate.json", "authoring_report.json", *final_artifacts, "panel_manifest.json"):
                    if not (candidate / name).is_file():
                        missing.append(str((candidate / name).relative_to(self.job_dir)).replace("\\", "/"))
        return not missing, missing

    def rank_and_build_review(self) -> dict[str, Any]:
        ranking = self._command("rank", str(self.job_dir))
        review = self._command("build-review", str(self.job_dir))
        return {"ranking": ranking, "review": review}

    @property
    def decision_path(self) -> Path:
        return self.job_dir / "review" / "review_decision.json"

    def review_data(self) -> dict[str, Any] | None:
        path = self.job_dir / "review" / "review-data.json"
        return load_json(path) if path.is_file() else None

    def write_auto_decision(self, requests: dict[str, Any], ranking: dict[str, Any]) -> dict[str, Any]:
        selected = ranking.get("selected_candidates", {})
        figures: list[dict[str, Any]] = []
        for request in requests["figures"]:
            figure_id = request["figure_id"]
            if request.get("decision") == "keep":
                figures.append(
                    {
                        "figure_id": figure_id,
                        "selected_candidate": "existing",
                        "panel_count": len(request.get("panels", [])),
                        "panel_decisions": [
                            {"panel_id": panel["panel_id"], "action": "keep"}
                            for panel in request.get("panels", [])
                        ],
                        "confirmed": True,
                        "notes": "Existing publication-ready figure retained by the PaperSpine story decision.",
                    }
                )
                continue
            candidate_id = selected.get(figure_id)
            if candidate_id not in {"A", "B", "C"}:
                raise BridgeError(f"ranking did not select a candidate for {figure_id}")
            manifest = load_json(self.job_dir / "candidates" / figure_id / candidate_id / "panel_manifest.json")
            panels = manifest.get("panels", [])
            figures.append(
                {
                    "figure_id": figure_id,
                    "selected_candidate": candidate_id,
                    "panel_count": len(panels),
                    "panel_decisions": [
                        {"panel_id": panel.get("panel_id"), "action": "keep"}
                        for panel in panels
                    ],
                    "confirmed": True,
                    "notes": "Automatically selected after all configured FigMirror gates passed.",
                }
            )
        decision = {
            "schema_version": "1.0",
            "project_id": requests["paper_id"],
            "review_scope": "all_figures",
            "status": "confirmed",
            "figures": figures,
        }
        write_json_atomic(self.decision_path, decision)
        return decision
