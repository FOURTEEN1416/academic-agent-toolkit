from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "scripts"))

from figure_story_check import validate_figure_story  # noqa: E402


def valid_request() -> dict:
    return {
        "schema_version": "1.1",
        "paper_id": "story-test",
        "figures": [
            {
                "figure_id": "figure-01",
                "figure_kind": "data",
                "decision": "redesign",
                "figure_role": "primary-result",
                "scientific_question": "Does the main comparison support the contribution?",
                "claim": "The primary comparison is supported by measured project evidence.",
                "intended_conclusion": "The declared condition improves the primary measured outcome.",
                "claim_boundary": "The comparison does not establish external generalization.",
                "results_units": ["R2: Primary comparison"],
                "hero_panel": "B",
                "panels": [
                    {
                        "panel_id": "A",
                        "question": "What data enter the comparison?",
                        "role": "setup",
                        "evidence_anchor": "FACT-01",
                        "intended_reading": "The declared groups and units are visible.",
                    },
                    {
                        "panel_id": "B",
                        "question": "Does the primary outcome differ?",
                        "role": "primary result",
                        "evidence_anchor": "FACT-02",
                        "intended_reading": "The primary outcome favors the declared condition.",
                    },
                ],
                "caption": "Primary measured comparison.",
                "label": "fig:primary",
                "source_data": ["data.csv"],
            }
        ],
    }


def canonical_sha256(value: dict) -> str:
    return hashlib.sha256(
        (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    ).hexdigest()


def write_request_with_plan(output: Path, request: dict | None = None) -> tuple[dict, dict]:
    request = copy.deepcopy(request or valid_request())
    figure = request["figures"][0]
    authority = {
        "authority_kind": "paperspine_master",
        "principal_id": "master-user",
        "session_id": "master-session",
        "run_id": "master-run",
        "attestation_input_id": "master-attestation",
    }
    authority["provenance_sha256"] = canonical_sha256(authority)
    plan = {
        "contract": "paperspine5.figure-reference-plan",
        "schema_version": "1.0",
        "mapping_id": "mapping-figure-01",
        "authority_table_version": "paper-spine/references/figure-reference-mapping.md#1.0",
        "mapping_authority": authority,
        "subject": {
            "task_id": "story-test",
            "material_snapshot_sha256": hashlib.sha256(b"materials").hexdigest(),
            "runner_revision": "1",
        },
        "figure": {
            "figure_id": figure["figure_id"],
            "figure_kind": "data",
            "publication_role": "main",
            "panel_ids": [item["panel_id"] for item in figure["panels"]],
            "producer_id": "figure-producer",
        },
        "design_provenance": "original_no_reference",
        "original_design_rationale": "No lawful reference figure was supplied for this local unit test.",
        "reference_assets": [],
        "scientific_story": {
            "question": figure["scientific_question"],
            "claim_ids": ["claim-primary"],
            "claim_boundary": figure["claim_boundary"],
            "results_unit_ids": ["result-primary"],
            "intended_conclusion": figure["intended_conclusion"],
            "hero_panel_id": figure["hero_panel"],
        },
        "domain_mappings": [
            {
                "mapping_row_id": f"mapping-{panel['panel_id']}",
                "source_kind": "original_component",
                "current_panel_id": panel["panel_id"],
                "evidence_anchor_ids": [panel["evidence_anchor"]],
                "data_bindings": [
                    {
                        "current_field": f"analysis.{panel['panel_id'].lower()}",
                        "visual_role": panel["role"],
                        "unit": "declared in source",
                        "transform": "identity",
                    }
                ],
                "semantic_transform": "Render only the current project evidence for this panel.",
                "retained_differences": ["current cohort", "current endpoint"],
            }
            for panel in figure["panels"]
        ],
        "grammar_reuse_justification": None,
        "external_action_authorized": False,
    }
    plan["plan_sha256"] = canonical_sha256(plan)
    plans = output / "figure_reference_plans"
    plans.mkdir(parents=True, exist_ok=True)
    plan_path = plans / "figure-01.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    figure["reference_plan"] = {
        "path": "figure_reference_plans/figure-01.json",
        "sha256": plan["plan_sha256"],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "figure_requests.json").write_text(json.dumps(request), encoding="utf-8")
    return request, plan


def write_body_contract(
    output: Path, *, request: dict | None = None, include_reference: bool = True
) -> None:
    request = (request or valid_request())["figures"][0]
    asset = output / "final_paper" / "figures" / "figure-01.svg"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    contract = {
        "schema_version": "1.0",
        "contract_type": "paperspine.figure.body",
        "status": "PASS",
        "job_id": "story-test",
        "paper_id": "story-test",
        "authority": {},
        "figures": [
            {
                **request,
                "figure_role": request.get("figure_role", "primary-result"),
                "publication_asset": {
                    "path": "final_paper/figures/figure-01.svg",
                    "format": "svg",
                    "sha256": digest,
                    "candidate_id": "A",
                },
                "editable_source": None,
                "latex": {},
                "prose_contract": {},
            }
        ],
        "artifacts": {},
    }
    (output / "figure_body_contract.json").write_text(json.dumps(contract), encoding="utf-8")
    reference = "Figure~\\ref{fig:primary} supports the primary comparison.\n" if include_reference else "No figure reference.\n"
    (output / "final_paper" / "main.tex").write_text(reference, encoding="utf-8")
    (output / "final_paper" / "figure_includes.tex").write_text(
        "\\begin{figure}\\label{fig:primary}\\end{figure}\n", encoding="utf-8"
    )


def write_final_mapping(output: Path, request: dict, plan: dict) -> None:
    figure = request["figures"][0]
    publication = output / "final_paper" / "figures" / "figure-01.svg"
    publication_sha = hashlib.sha256(publication.read_bytes()).hexdigest()
    surface = output / "visual_audit" / "figure-01-side-by-side.svg"
    surface.parent.mkdir(parents=True, exist_ok=True)
    surface.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    surface_sha = hashlib.sha256(surface.read_bytes()).hexdigest()
    request["figure_reference_asset_ledger"] = "figure_reference_assets.json"
    ledger = {
        "artifacts": [
            {
                "artifact_id": "figure-final",
                "path": "final_paper/figures/figure-01.svg",
                "sha256": publication_sha,
                "media_type": "image/svg+xml",
            },
            {
                "artifact_id": "comparison-surface",
                "path": "visual_audit/figure-01-side-by-side.svg",
                "sha256": surface_sha,
                "media_type": "image/svg+xml",
            },
        ]
    }
    (output / "figure_reference_assets.json").write_text(json.dumps(ledger), encoding="utf-8")
    background = {
        "policy": "transparent_master_white_publication",
        "probe_method": "svg_structure_and_pixel_probe",
        "probe_version": "paperspine-neutral-background/1.0",
        "probe_render_sha256": hashlib.sha256(b"probe-render").hexdigest(),
        "asset_sha256": publication_sha,
        "canvas": {
            "region_id": "canvas",
            "bbox_normalized": [0, 0, 1, 1],
            "detected_background": "pure_white",
            "status": "PASS",
        },
        "axes_inventory": {"status": "complete"},
        "axes": [],
        "panels": [
            {
                "region_id": panel["panel_id"],
                "bbox_normalized": [0, 0, 1, 1],
                "detected_background": "pure_white",
                "status": "PASS",
            }
            for panel in figure["panels"]
        ],
        "semantic_fill_allowed": True,
        "final_surface_status": "PASS",
    }
    background["receipt_sha256"] = canonical_sha256(background)
    mapping = {
        "contract": "paperspine5.figure-reference-mapping",
        "schema_version": "1.0",
        **{
            key: copy.deepcopy(plan[key])
            for key in (
                "mapping_id",
                "mapping_authority",
                "subject",
                "figure",
                "design_provenance",
                "original_design_rationale",
                "reference_assets",
                "scientific_story",
                "domain_mappings",
                "grammar_reuse_justification",
            )
        },
        "plan_binding": {
            "artifact_id": "reference-plan",
            "sha256": plan["plan_sha256"],
            "revision_id": "1",
        },
        "assets": {
            "current": {
                "artifact_id": "figure-final",
                "sha256": publication_sha,
                "revision_id": "1",
            },
            "candidates": [],
            "selected": {
                "artifact_id": "figure-final",
                "sha256": publication_sha,
                "revision_id": "1",
            },
            "publication": {
                "artifact_id": "figure-final",
                "sha256": publication_sha,
                "revision_id": "1",
            },
            "editable_source": {
                "artifact_id": "figure-final",
                "sha256": publication_sha,
                "revision_id": "1",
            },
        },
        "background": background,
        "independent_review": {
            "reviewer_id": "independent-reviewer",
            "producer_ids": ["figure-producer"],
            "status": "PASS",
            "reviewed_reference_hashes": [],
            "reviewed_asset_hashes": [publication_sha],
            "decision": "keep_original",
            "selected_sha256": publication_sha,
            "rationale": "The current figure preserves the frozen story and passes review.",
        },
        "side_by_side": {
            "layout": "side_by_side",
            "left": {
                "kind": "original_no_reference",
                "message": "Original design; no reference imitation is claimed.",
            },
            "right": {
                "kind": "final_publication_asset",
                "preview": {
                    "source_asset_sha256": publication_sha,
                    "preview_artifact_id": "figure-final",
                    "preview_sha256": publication_sha,
                },
            },
            "surface_artifact_id": "comparison-surface",
            "surface_sha256": surface_sha,
            "status": "PASS",
        },
        "verification": {
            "mapping_complete": True,
            "asset_hashes_match": True,
            "background_compliant": True,
            "story_aligned": True,
            "final_render_inspected": True,
            "status": "PASS",
        },
        "external_action_authorized": False,
    }
    mapping["mapping_sha256"] = canonical_sha256(mapping)
    mapping_path = output / "figure_reference_plans" / "figure-01-final.json"
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    figure["final_mapping"] = {
        "path": "figure_reference_plans/figure-01-final.json",
        "sha256": mapping["mapping_sha256"],
    }
    (output / "figure_requests.json").write_text(json.dumps(request), encoding="utf-8")


class FigureStoryCheckTests(unittest.TestCase):
    def test_missing_reference_plan_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "figure_requests.json").write_text(
                json.dumps(valid_request()), encoding="utf-8"
            )
            result = validate_figure_story(output)
            self.assertFalse(result.ok)
            self.assertTrue(any("reference_plan binding is required" in item for item in result.findings))

    def test_valid_planning_contract_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            write_request_with_plan(output)
            result = validate_figure_story(output)
            self.assertTrue(result.ok, result.findings)

    def test_reference_plan_cannot_be_backfilled_after_signing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            request, _plan = write_request_with_plan(output)
            plan_path = output / request["figures"][0]["reference_plan"]["path"]
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["domain_mappings"][0]["semantic_transform"] = "Backfilled after generation."
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            result = validate_figure_story(output)
            self.assertFalse(result.ok)
            self.assertTrue(any("plan_sha256 does not recompute" in item for item in result.findings))

    def test_missing_panel_job_and_invalid_hero_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            request = valid_request()
            request["figures"][0]["hero_panel"] = "Z"
            request["figures"][0]["panels"][0]["role"] = ""
            write_request_with_plan(output, request)
            result = validate_figure_story(output)
            self.assertFalse(result.ok)
            self.assertTrue(any("hero_panel" in item for item in result.findings))
            self.assertTrue(any("role" in item for item in result.findings))

    def test_final_contract_requires_visual_coverage_by_latex_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            request, plan = write_request_with_plan(output)
            write_body_contract(output, request=request)
            write_final_mapping(output, request, plan)
            (output / "visual_audit_manifest.json").write_text(
                json.dumps({"figures": [{"figure_id": "fig:different"}]}), encoding="utf-8"
            )
            result = validate_figure_story(output, "final")
            self.assertFalse(result.ok)
            self.assertTrue(any("fig:primary" in item for item in result.findings))

    def test_final_requires_mapping_and_rejects_colored_background_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            request, plan = write_request_with_plan(output)
            write_body_contract(output, request=request)
            missing = validate_figure_story(output, "final")
            self.assertFalse(missing.ok)
            self.assertTrue(any("final_mapping binding is required" in item for item in missing.findings))

            write_final_mapping(output, request, plan)
            binding = request["figures"][0]["final_mapping"]
            mapping_path = output / binding["path"]
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
            mapping["background"]["canvas"]["detected_background"] = "beige"
            mapping["background"]["receipt_sha256"] = canonical_sha256(
                {
                    key: value
                    for key, value in mapping["background"].items()
                    if key != "receipt_sha256"
                }
            )
            mapping["mapping_sha256"] = canonical_sha256(
                {key: value for key, value in mapping.items() if key != "mapping_sha256"}
            )
            binding["sha256"] = mapping["mapping_sha256"]
            mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
            (output / "figure_requests.json").write_text(json.dumps(request), encoding="utf-8")
            blocked = validate_figure_story(output, "final")
            self.assertFalse(blocked.ok)
            self.assertTrue(any("colored or unverified" in item for item in blocked.findings))

    def test_final_contract_passes_with_hash_bound_asset_and_body_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            request, plan = write_request_with_plan(output)
            write_body_contract(output, request=request)
            write_final_mapping(output, request, plan)
            (output / "visual_audit_manifest.json").write_text(
                json.dumps({"figures": [{"figure_id": "fig:primary"}]}), encoding="utf-8"
            )
            result = validate_figure_story(output, "final")
            self.assertTrue(result.ok, result.findings)

    def test_final_contract_rejects_producer_as_independent_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            request, plan = write_request_with_plan(output)
            write_body_contract(output, request=request)
            write_final_mapping(output, request, plan)
            binding = request["figures"][0]["final_mapping"]
            mapping_path = output / binding["path"]
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
            mapping["independent_review"]["reviewer_id"] = "figure-producer"
            mapping["mapping_sha256"] = canonical_sha256(
                {key: value for key, value in mapping.items() if key != "mapping_sha256"}
            )
            binding["sha256"] = mapping["mapping_sha256"]
            mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
            (output / "figure_requests.json").write_text(json.dumps(request), encoding="utf-8")

            result = validate_figure_story(output, "final")

            self.assertFalse(result.ok)
            self.assertTrue(any("does not separate reviewer" in item for item in result.findings))

    def test_final_contract_rejects_figure_not_referenced_by_manuscript_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            request, plan = write_request_with_plan(output)
            write_body_contract(output, request=request, include_reference=False)
            write_final_mapping(output, request, plan)
            (output / "visual_audit_manifest.json").write_text(
                json.dumps({"figures": [{"figure_id": "fig:primary"}]}), encoding="utf-8"
            )
            result = validate_figure_story(output, "final")
            self.assertFalse(result.ok)
            self.assertTrue(any("does not reference" in item for item in result.findings))


if __name__ == "__main__":
    unittest.main()
