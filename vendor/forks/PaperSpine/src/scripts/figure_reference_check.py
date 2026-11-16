#!/usr/bin/env python3
"""Fail-closed local gate for pre-execution reference plans and final mappings."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FigureReferenceResult:
    phase: str
    ok: bool
    figure_count: int
    findings: list[str]


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        (
            json.dumps(
                dict(value),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _safe_path(root: Path, value: Any, label: str, findings: list[str]) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        findings.append(f"{label}.path is required")
        return None
    target = (root / value).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        findings.append(f"{label}.path escapes the output directory")
        return None
    if not target.is_file():
        findings.append(f"{label}.path is missing: {value}")
        return None
    return target


def _load_json_binding(
    root: Path,
    binding: Any,
    *,
    self_hash_field: str,
    label: str,
    findings: list[str],
) -> dict[str, Any] | None:
    if not isinstance(binding, Mapping):
        findings.append(f"{label} binding is required")
        return None
    target = _safe_path(root, binding.get("path"), label, findings)
    if target is None:
        return None
    try:
        value = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"{label} is invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        findings.append(f"{label} must contain one JSON object")
        return None
    supplied = value.get(self_hash_field)
    unsigned = {key: item for key, item in value.items() if key != self_hash_field}
    if supplied != _canonical_sha256(unsigned):
        findings.append(f"{label}.{self_hash_field} does not recompute")
    if binding.get("sha256") != supplied:
        findings.append(f"{label} binding does not match {self_hash_field}")
    return value


def _asset_ledger(root: Path, raw: Mapping[str, Any], findings: list[str]) -> dict[str, dict[str, Any]]:
    locator = raw.get("figure_reference_asset_ledger")
    if locator is None:
        return {}
    target = _safe_path(root, locator, "figure_reference_asset_ledger", findings)
    if target is None:
        return {}
    try:
        ledger = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"figure reference asset ledger is invalid JSON: {exc}")
        return {}
    artifacts = ledger.get("artifacts") if isinstance(ledger, dict) else None
    if not isinstance(artifacts, list):
        findings.append("figure reference asset ledger artifacts must be a list")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(artifacts):
        label = f"figure_reference_asset_ledger.artifacts[{index}]"
        if not isinstance(item, dict) or not isinstance(item.get("artifact_id"), str):
            findings.append(f"{label} requires artifact_id")
            continue
        artifact_id = item["artifact_id"]
        if artifact_id in result:
            findings.append(f"{label} duplicates artifact_id {artifact_id}")
            continue
        target = _safe_path(root, item.get("path"), label, findings)
        if target is None:
            continue
        measured = _file_sha256(target)
        if item.get("sha256") != measured:
            findings.append(f"{label}.sha256 does not match actual bytes")
            continue
        result[artifact_id] = item
    return result


def _bbox(value: Any, label: str, findings: list[str]) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(not isinstance(item, (int, float)) for item in value)
    ):
        findings.append(f"{label} must be [x,y,width,height]")
        return
    x, y, width, height = (float(item) for item in value)
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        findings.append(f"{label} escapes the normalized canvas")


def _authority(value: Any, label: str, findings: list[str]) -> None:
    if not isinstance(value, Mapping) or value.get("authority_kind") != "paperspine_master":
        findings.append(f"{label} must be a paperspine_master authority")
        return
    signed = {
        key: value.get(key)
        for key in (
            "authority_kind",
            "principal_id",
            "session_id",
            "run_id",
            "attestation_input_id",
        )
    }
    if any(not isinstance(item, str) or not item for item in signed.values()):
        findings.append(f"{label} identity fields are incomplete")
    if value.get("provenance_sha256") != _canonical_sha256(signed):
        findings.append(f"{label}.provenance_sha256 does not recompute")


def _validate_plan(
    plan: Mapping[str, Any],
    request: Mapping[str, Any],
    ledger: Mapping[str, Mapping[str, Any]],
    label: str,
    findings: list[str],
) -> None:
    if (
        plan.get("contract") != "paperspine5.figure-reference-plan"
        or plan.get("schema_version") != "1.0"
        or plan.get("authority_table_version")
        not in {"paper-spine/references/figure-reference-mapping.md#1.0",
                "PAPERSPINE_VERA_FIGURE_MAPPING.md#MASTER_FROZEN_V1",
                "PAPERSPINE_VERA_FIGURE_MAPPING.md#MASTER_FROZEN_V3"}
        or plan.get("external_action_authorized") is not False
    ):
        findings.append(f"{label} contract/version/authority table/external boundary is invalid")
    _authority(plan.get("mapping_authority"), f"{label}.mapping_authority", findings)
    figure = plan.get("figure")
    request_panels = {
        str(item.get("panel_id"))
        for item in request.get("panels", [])
        if isinstance(item, Mapping)
    }
    if not isinstance(figure, Mapping):
        findings.append(f"{label}.figure is required")
        return
    plan_panels = set(figure.get("panel_ids", [])) if isinstance(figure.get("panel_ids"), list) else set()
    if figure.get("figure_id") != request.get("figure_id") or plan_panels != request_panels:
        findings.append(f"{label}.figure does not match the figure request and panel set")
    story = plan.get("scientific_story")
    if not isinstance(story, Mapping):
        findings.append(f"{label}.scientific_story is required")
    else:
        expected = {
            "question": request.get("scientific_question"),
            "claim_boundary": request.get("claim_boundary"),
            "intended_conclusion": request.get("intended_conclusion"),
            "hero_panel_id": request.get("hero_panel"),
        }
        if any(story.get(key) != value for key, value in expected.items()):
            findings.append(f"{label}.scientific_story changed the request story")

    provenance = plan.get("design_provenance")
    references = plan.get("reference_assets")
    if not isinstance(references, list):
        findings.append(f"{label}.reference_assets must be a list")
        references = []
    if provenance == "reference_guided" and not references:
        findings.append(f"{label} reference_guided requires actual reference assets")
    elif provenance == "original_no_reference":
        if references or not isinstance(plan.get("original_design_rationale"), str):
            findings.append(f"{label} original_no_reference requires an empty reference set and rationale")
    else:
        findings.append(f"{label}.design_provenance is invalid")

    reference_panels: set[tuple[str, str]] = set()
    reference_ids: set[str] = set()
    for index, reference in enumerate(references):
        item_label = f"{label}.reference_assets[{index}]"
        if not isinstance(reference, Mapping):
            findings.append(f"{item_label} must be an object")
            continue
        reference_id = str(reference.get("reference_id") or "")
        if not reference_id or reference_id in reference_ids:
            findings.append(f"{item_label}.reference_id must be unique")
        reference_ids.add(reference_id)
        for artifact_key, hash_key in (
            ("source_id", "source_content_sha256"),
            ("asset_id", "asset_sha256"),
            ("preview_artifact_id", "preview_sha256"),
        ):
            artifact_id = reference.get(artifact_key)
            artifact = ledger.get(str(artifact_id))
            if artifact is None or artifact.get("sha256") != reference.get(hash_key):
                findings.append(f"{item_label}.{artifact_key} is absent or stale in the byte ledger")
        panels = reference.get("panels")
        if not isinstance(panels, list) or not panels:
            findings.append(f"{item_label}.panels must be non-empty")
            continue
        for panel_index, panel in enumerate(panels):
            panel_label = f"{item_label}.panels[{panel_index}]"
            if not isinstance(panel, Mapping):
                findings.append(f"{panel_label} must be an object")
                continue
            panel_id = str(panel.get("panel_id") or "")
            reference_panels.add((reference_id, panel_id))
            _bbox(panel.get("bbox_normalized"), f"{panel_label}.bbox_normalized", findings)
            for field in (
                "layout_role",
                "mark_type",
                "encodings",
                "visual_hierarchy",
                "reading_order",
                "transferable_features",
                "prohibited_transfer",
            ):
                if panel.get(field) in (None, "", []):
                    findings.append(f"{panel_label}.{field} is required")
            prohibited = set(panel.get("prohibited_transfer", []))
            if not {"data", "values", "labels", "claims", "wording"}.issubset(prohibited):
                findings.append(f"{panel_label}.prohibited_transfer is incomplete")

    rows = plan.get("domain_mappings")
    mapped: set[str] = set()
    used_references: set[str] = set()
    if not isinstance(rows, list) or not rows:
        findings.append(f"{label}.domain_mappings must be non-empty")
        rows = []
    for index, row in enumerate(rows):
        row_label = f"{label}.domain_mappings[{index}]"
        if not isinstance(row, Mapping):
            findings.append(f"{row_label} must be an object")
            continue
        panel_id = str(row.get("current_panel_id") or "")
        if panel_id not in request_panels:
            findings.append(f"{row_label}.current_panel_id is unknown")
        mapped.add(panel_id)
        if row.get("source_kind") == "reference_panel":
            key = (str(row.get("reference_id") or ""), str(row.get("reference_panel_id") or ""))
            if key not in reference_panels:
                findings.append(f"{row_label} points to an unknown reference panel")
            used_references.add(key[0])
        elif row.get("source_kind") != "original_component":
            findings.append(f"{row_label}.source_kind is invalid")
        for field in ("evidence_anchor_ids", "data_bindings", "semantic_transform", "retained_differences"):
            if row.get(field) in (None, "", []):
                findings.append(f"{row_label}.{field} is required")
    if mapped != request_panels:
        findings.append(f"{label} must map every current panel exactly")
    if provenance == "reference_guided" and used_references != reference_ids:
        findings.append(f"{label} must use every declared reference asset")


def _validate_final_mapping(
    mapping: Mapping[str, Any],
    plan: Mapping[str, Any],
    request: Mapping[str, Any],
    ledger: Mapping[str, Mapping[str, Any]],
    body: Mapping[str, Any] | None,
    label: str,
    findings: list[str],
) -> None:
    if (
        mapping.get("contract") != "paperspine5.figure-reference-mapping"
        or mapping.get("schema_version") != "1.0"
        or mapping.get("external_action_authorized") is not False
    ):
        findings.append(f"{label} contract/version/external boundary is invalid")
    plan_binding = mapping.get("plan_binding")
    if not isinstance(plan_binding, Mapping) or plan_binding.get("sha256") != plan.get("plan_sha256"):
        findings.append(f"{label}.plan_binding does not bind the frozen plan")
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
    ):
        if mapping.get(key) != plan.get(key):
            findings.append(f"{label} changed frozen plan field {key}")

    assets = mapping.get("assets")
    publication_sha = None
    required_asset_hashes: set[str] = set()
    if not isinstance(assets, Mapping):
        findings.append(f"{label}.assets is required")
    else:
        current = assets.get("current")
        candidates = assets.get("candidates") if isinstance(assets.get("candidates"), list) else []
        selected = assets.get("selected")
        publication = assets.get("publication")
        publication_sha = publication.get("sha256") if isinstance(publication, Mapping) else None
        if not isinstance(selected, Mapping) or selected.get("sha256") != publication_sha:
            findings.append(f"{label} publication asset does not equal selected winner")
        selectable = {
            binding.get("sha256")
            for binding in [current, *candidates]
            if isinstance(binding, Mapping)
        }
        if not isinstance(selected, Mapping) or selected.get("sha256") not in selectable:
            findings.append(f"{label} selected asset is neither current nor a declared candidate")
        bindings = [current, *candidates, selected, publication, assets.get("editable_source")]
        for asset_index, binding in enumerate(bindings):
            if not isinstance(binding, Mapping):
                if asset_index != 0:
                    findings.append(f"{label}.assets contains a missing required binding")
                continue
            artifact = ledger.get(str(binding.get("artifact_id"))) if isinstance(binding, Mapping) else None
            if artifact is None or artifact.get("sha256") != binding.get("sha256"):
                findings.append(f"{label}.assets binding is absent or stale in the byte ledger")
            if _is_sha256(binding.get("sha256")):
                required_asset_hashes.add(str(binding["sha256"]))
    if body is None or not isinstance(body.get("publication_asset"), Mapping) or body["publication_asset"].get("sha256") != publication_sha:
        findings.append(f"{label} publication hash does not equal figure_body_contract")

    panel_ids = set(mapping.get("figure", {}).get("panel_ids", [])) if isinstance(mapping.get("figure"), Mapping) else set()
    background = mapping.get("background")
    if not isinstance(background, Mapping):
        findings.append(f"{label}.background is required")
    else:
        if (
            background.get("asset_sha256") != publication_sha
            or background.get("probe_version") != "paperspine-neutral-background/1.0"
            or not _is_sha256(background.get("probe_render_sha256"))
            or background.get("final_surface_status") != "PASS"
        ):
            findings.append(f"{label}.background is stale, unprobed, or not PASS")
        unsigned_background = {
            key: value for key, value in background.items() if key != "receipt_sha256"
        }
        if background.get("receipt_sha256") != _canonical_sha256(unsigned_background):
            findings.append(f"{label}.background receipt hash does not recompute")
        regions = [background.get("canvas"), *background.get("axes", []), *background.get("panels", [])]
        for region in regions:
            if not isinstance(region, Mapping) or region.get("detected_background") not in {"transparent", "pure_white"} or region.get("status") != "PASS":
                findings.append(f"{label}.background contains a colored or unverified region")
                break
            _bbox(region.get("bbox_normalized"), f"{label}.background region", findings)
        covered = {str(item.get("region_id")) for item in background.get("panels", []) if isinstance(item, Mapping)}
        if covered != panel_ids:
            findings.append(f"{label}.background does not cover every current panel")

    review = mapping.get("independent_review")
    reference_hashes = {
        str(item.get("asset_sha256"))
        for item in mapping.get("reference_assets", [])
        if isinstance(item, Mapping) and _is_sha256(item.get("asset_sha256"))
    }
    if not isinstance(review, Mapping):
        findings.append(f"{label}.independent_review is required")
    else:
        producers = set(review.get("producer_ids", [])) if isinstance(review.get("producer_ids"), list) else set()
        producer_id = mapping.get("figure", {}).get("producer_id") if isinstance(mapping.get("figure"), Mapping) else None
        if producer_id not in producers or review.get("reviewer_id") in producers:
            findings.append(f"{label}.independent_review does not separate reviewer from all producers")
        if set(review.get("reviewed_reference_hashes", [])) != reference_hashes:
            findings.append(f"{label}.independent_review does not cover every exact reference asset")
        if set(review.get("reviewed_asset_hashes", [])) != required_asset_hashes:
            findings.append(f"{label}.independent_review does not cover current/candidates/selected/publication/editable assets")
        selected_sha = assets.get("selected", {}).get("sha256") if isinstance(assets, Mapping) and isinstance(assets.get("selected"), Mapping) else None
        if review.get("selected_sha256") != selected_sha or review.get("status") != "PASS":
            findings.append(f"{label}.independent_review winner or status is inconsistent")

    side = mapping.get("side_by_side")
    if not isinstance(side, Mapping) or side.get("layout") != "side_by_side" or side.get("status") != "PASS":
        findings.append(f"{label}.side_by_side is missing or not PASS")
    else:
        right = side.get("right", {}).get("preview", {}) if isinstance(side.get("right"), Mapping) else {}
        if right.get("source_asset_sha256") != publication_sha:
            findings.append(f"{label}.side_by_side right side is not the publication asset")
        preview_bindings = [right]
        left = side.get("left")
        provenance = mapping.get("design_provenance")
        if provenance == "reference_guided":
            references = {
                str(item.get("reference_id")): item
                for item in mapping.get("reference_assets", [])
                if isinstance(item, Mapping)
            }
            reference = references.get(str(left.get("reference_id"))) if isinstance(left, Mapping) else None
            left_preview = left.get("preview") if isinstance(left, Mapping) else None
            if (
                not isinstance(left, Mapping)
                or left.get("kind") != "reference_asset"
                or not isinstance(reference, Mapping)
                or not isinstance(left_preview, Mapping)
                or left_preview.get("source_asset_sha256") != reference.get("asset_sha256")
            ):
                findings.append(f"{label}.side_by_side left side is not the declared reference asset")
        elif isinstance(left, Mapping) and left.get("kind") == "original_asset":
            current = assets.get("current") if isinstance(assets, Mapping) else None
            preview = left.get("preview")
            if not isinstance(current, Mapping) or not isinstance(preview, Mapping) or preview.get("source_asset_sha256") != current.get("sha256"):
                findings.append(f"{label}.side_by_side original does not bind assets.current")
        elif not isinstance(left, Mapping) or left.get("kind") != "original_no_reference":
            findings.append(f"{label}.side_by_side left side has no valid original/reference sentinel")
        if isinstance(left, Mapping) and isinstance(left.get("preview"), Mapping):
            preview_bindings.append(left["preview"])
        for preview in preview_bindings:
            artifact = ledger.get(str(preview.get("preview_artifact_id")))
            if artifact is None or artifact.get("sha256") != preview.get("preview_sha256"):
                findings.append(f"{label}.side_by_side preview is absent or stale")
        surface = ledger.get(str(side.get("surface_artifact_id")))
        if surface is None or surface.get("sha256") != side.get("surface_sha256"):
            findings.append(f"{label}.side_by_side surface is absent or stale")

    verification = mapping.get("verification")
    required_verification = (
        "mapping_complete",
        "asset_hashes_match",
        "background_compliant",
        "story_aligned",
        "final_render_inspected",
    )
    if (
        not isinstance(verification, Mapping)
        or verification.get("status") != "PASS"
        or any(verification.get(key) is not True for key in required_verification)
    ):
        findings.append(f"{label}.verification is incomplete or not PASS")


def validate_figure_references(output_dir: Path, phase: str = "planning") -> FigureReferenceResult:
    request_path = output_dir / "figure_requests.json"
    findings: list[str] = []
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        return FigureReferenceResult(phase, False, 0, [f"figure_requests.json is unavailable: {exc}"])
    figures = raw.get("figures") if isinstance(raw, dict) else None
    if not isinstance(figures, list) or not figures:
        return FigureReferenceResult(phase, False, 0, ["figures must be a non-empty list"])
    ledger = _asset_ledger(output_dir, raw, findings)
    body_figures: dict[str, Mapping[str, Any]] = {}
    if phase == "final":
        try:
            body = json.loads((output_dir / "figure_body_contract.json").read_text(encoding="utf-8-sig"))
            body_figures = {
                str(item.get("figure_id")): item
                for item in body.get("figures", [])
                if isinstance(item, Mapping)
            }
        except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError) as exc:
            findings.append(f"figure_body_contract.json is unavailable for mapping closure: {exc}")
    for index, request in enumerate(figures):
        if not isinstance(request, Mapping):
            continue
        label = f"figures[{index}]"
        plan = _load_json_binding(
            output_dir,
            request.get("reference_plan"),
            self_hash_field="plan_sha256",
            label=f"{label}.reference_plan",
            findings=findings,
        )
        if plan is None:
            continue
        _validate_plan(plan, request, ledger, f"{label}.reference_plan", findings)
        if phase == "final":
            mapping = _load_json_binding(
                output_dir,
                request.get("final_mapping"),
                self_hash_field="mapping_sha256",
                label=f"{label}.final_mapping",
                findings=findings,
            )
            if mapping is not None:
                _validate_final_mapping(
                    mapping,
                    plan,
                    request,
                    ledger,
                    body_figures.get(str(request.get("figure_id"))),
                    f"{label}.final_mapping",
                    findings,
                )
    return FigureReferenceResult(phase, not findings, len(figures), findings)


def _markdown(result: FigureReferenceResult) -> str:
    lines = [
        "# Figure Reference Check",
        "",
        f"- Phase: `{result.phase}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Figures: {result.figure_count}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {item}" for item in result.findings) if result.findings else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--phase", choices=("planning", "final"), default="planning")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    result = validate_figure_references(output_dir, args.phase)
    report = _markdown(result)
    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "figure_reference_check.md").write_text(report, encoding="utf-8")
    print(report)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
