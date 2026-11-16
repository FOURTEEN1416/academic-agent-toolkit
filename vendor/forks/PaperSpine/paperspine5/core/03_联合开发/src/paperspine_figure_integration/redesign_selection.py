"""Consume FigMirror independent redesign comparison receipts fail-safely."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .contracts import ContractError, IDENTIFIER, load_json, resolve_within


COMPARISON_CONTRACT_VERSION = "figmirror.redesign-comparison.v1"
FINAL_SIZE_COMPARISON_CONTRACT_VERSION = "figmirror.redesign-comparison.v2"
COMPARISON_CONTRACT_VERSIONS = {
    COMPARISON_CONTRACT_VERSION,
    FINAL_SIZE_COMPARISON_CONTRACT_VERSION,
}
REDESIGN_DECISIONS = {"redesign", "improve"}
RUBRIC_DIMENSIONS = {
    "scientific_story",
    "data_truthfulness",
    "readability",
    "publication_fit",
    "editability_lineage",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _canonical_sha(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def bind_current_figure_sha(request: dict[str, Any], project_root: Path) -> None:
    """Bind or verify one keep/redesign/improve original at the 03 boundary."""
    if request.get("decision") not in {"keep", *REDESIGN_DECISIONS}:
        return
    current = resolve_within(
        project_root,
        request.get("current_figure", ""),
        f"{request.get('figure_id')}.current_figure",
        must_exist=True,
    )
    actual = _sha256(current)
    declared = request.get("current_figure_sha256")
    if declared is not None and str(declared).upper() != actual:
        raise ContractError(f"{request.get('figure_id')} current_figure SHA-256 changed after request binding")
    request["current_figure"] = str(current)
    request["current_figure_sha256"] = actual


def _receipt_path(job: dict[str, Any], figure_id: str, declared: Any) -> Path:
    expected = (
        Path(job["figure"]["job_dir"]) / "review" / "comparisons" / figure_id / "comparison_receipt.json"
    ).resolve()
    if declared in (None, ""):
        return expected
    candidate = Path(str(declared))
    if not candidate.is_absolute():
        candidate = Path(job["figure"]["job_dir"]) / candidate
    candidate = candidate.resolve()
    if candidate != expected:
        raise ContractError(f"{figure_id} comparison_receipt must be the frozen FigMirror receipt")
    return candidate


def _strict_comparison_is_consistent(comparison: Any) -> bool:
    if not isinstance(comparison, dict) or comparison.get("conclusion") != "strictly_better":
        return False
    if comparison.get("failures"):
        return False
    dimensions = comparison.get("dimensions")
    if not isinstance(dimensions, dict) or set(dimensions) != RUBRIC_DIMENSIONS:
        return False
    improved = False
    for value in dimensions.values():
        if not isinstance(value, dict) or value.get("threshold_met") is not True:
            return False
        current = value.get("current_score")
        candidate = value.get("candidate_score")
        verdict = value.get("verdict")
        if (
            isinstance(current, bool)
            or isinstance(candidate, bool)
            or not isinstance(current, (int, float))
            or not isinstance(candidate, (int, float))
            or not 0 <= float(current) <= 100
            or not 75 <= float(candidate) <= 100
        ):
            return False
        if verdict == "candidate_better" and candidate > current:
            improved = True
        elif verdict == "tie" and candidate == current:
            continue
        else:
            return False
    return improved


def _comparison_receipt_audit(
    job: dict[str, Any], request: dict[str, Any], selected_candidate: str, declared_receipt: Any
) -> dict[str, Any]:
    figure_id = request["figure_id"]
    try:
        receipt_path = _receipt_path(job, figure_id, declared_receipt)
    except ContractError as exc:
        return {"valid": False, "reason": str(exc), "receipt": None}
    directory = receipt_path.parent
    request_path = directory / "comparison_request.json"
    private_path = directory / "comparison_private_map.json"
    if not receipt_path.is_file() or not request_path.is_file() or not private_path.is_file():
        return {
            "valid": False,
            "reason": "independent_comparison_receipt_or_inputs_missing",
            "receipt": str(receipt_path) if receipt_path.is_file() else None,
        }
    try:
        receipt = load_json(receipt_path)
        comparison_request = load_json(request_path)
        private_map = load_json(private_path)
        receipt_payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if receipt.get("receipt_sha256") != _canonical_sha(receipt_payload):
            raise ContractError("comparison_receipt_sha256_mismatch")
        fixed_request = {key: value for key, value in comparison_request.items() if key != "input_digest"}
        if comparison_request.get("input_digest") != _canonical_sha(fixed_request):
            raise ContractError("comparison_request_digest_mismatch")
        if private_map.get("input_digest") != comparison_request.get("input_digest"):
            raise ContractError("comparison_private_map_digest_mismatch")
        if receipt.get("input_digest") != comparison_request.get("input_digest"):
            raise ContractError("comparison_receipt_input_digest_mismatch")
        contract_version = receipt.get("contract_version")
        if contract_version not in COMPARISON_CONTRACT_VERSIONS:
            raise ContractError("comparison_contract_version_unsupported")
        if (
            comparison_request.get("contract_version") != contract_version
            or private_map.get("contract_version") != contract_version
        ):
            raise ContractError("comparison_input_contract_version_unsupported")
        if receipt.get("figure_id") != figure_id or receipt.get("mode") != request.get("decision"):
            raise ContractError("comparison_receipt_identity_mismatch")
        if (
            comparison_request.get("figure_id") != figure_id
            or comparison_request.get("mode") != request.get("decision")
            or private_map.get("figure_id") != figure_id
        ):
            raise ContractError("comparison_input_identity_mismatch")
        reviewer = receipt.get("reviewer") or {}
        reviewer_identity = str(reviewer.get("identity") or "").strip()
        if reviewer.get("role") != "independent_reviewer_agent" or not reviewer_identity:
            raise ContractError("independent_reviewer_identity_missing")
        validation = receipt.get("validation") or {}
        if not all(
            validation.get(name) is True
            for name in ("identity_separated", "input_hashes_unchanged", "candidate_suite_complete")
        ):
            raise ContractError("comparison_validation_identity_or_inputs_invalid")
        expected_final_size = request.get("final_size_context")
        if expected_final_size is not None:
            if contract_version != FINAL_SIZE_COMPARISON_CONTRACT_VERSION:
                raise ContractError("final_size_comparison_contract_required")
            if (
                comparison_request.get("final_size_context") != expected_final_size
                or private_map.get("final_size_context") != expected_final_size
                or comparison_request.get("final_size_context_sha256")
                != _canonical_sha(expected_final_size)
                or validation.get("final_size_context_bound") is not True
            ):
                raise ContractError("final_size_context_does_not_match_placement")
        elif contract_version == FINAL_SIZE_COMPARISON_CONTRACT_VERSION:
            raise ContractError("unexpected_final_size_comparison_context")

        variants = private_map.get("variants") or {}
        producer_identities = {
            str(value.get("producer_identity") or "").strip()
            for value in variants.values()
            if isinstance(value, dict)
        }
        if not producer_identities or "UNASSIGNED" in producer_identities or "" in producer_identities:
            raise ContractError("comparison producer identity is unverified")
        if reviewer_identity.casefold() in {value.casefold() for value in producer_identities}:
            raise ContractError("comparison reviewer is a candidate producer")
        producer_hashes = sorted(_canonical_sha(value.casefold()) for value in producer_identities)
        if receipt.get("producer_identity_hashes") != producer_hashes:
            raise ContractError("comparison producer identity hashes mismatch")

        project_root = Path(job["project_root"]).resolve()
        current = resolve_within(
            project_root,
            request["current_figure"],
            f"{figure_id}.current_figure",
            must_exist=True,
        )
        current_sha = _sha256(current)
        baseline = private_map.get("baseline") or {}
        input_hashes = receipt.get("input_hashes") or {}
        public_baseline = comparison_request.get("baseline") or {}
        baseline_source = resolve_within(
            project_root,
            baseline.get("source_path", ""),
            f"{figure_id}.comparison_baseline",
            must_exist=True,
        )
        if baseline_source != current:
            raise ContractError("comparison baseline source does not match current_figure")
        if any(
            str(value or "").upper() != current_sha
            for value in (
                request.get("current_figure_sha256"),
                baseline.get("sha256"),
                public_baseline.get("sha256"),
                input_hashes.get("baseline_sha256"),
            )
        ):
            raise ContractError("comparison baseline hash drifted")
        if expected_final_size is not None:
            baseline_render = resolve_within(
                project_root,
                baseline.get("final_size_render_path", ""),
                f"{figure_id}.comparison_baseline_final_size_render",
                must_exist=True,
            )
            baseline_render_sha = _sha256(baseline_render)
            if any(
                str(value or "").upper() != baseline_render_sha
                for value in (
                    baseline.get("final_size_render_sha256"),
                    public_baseline.get("final_size_render_sha256"),
                    input_hashes.get("baseline_final_size_render_sha256"),
                )
            ):
                raise ContractError("comparison baseline final-size render hash drifted")

        receipt_variant_hashes = input_hashes.get("variant_sha256") or {}
        public_variants = {
            str(value.get("artifact_id")): value
            for value in comparison_request.get("variants", [])
            if isinstance(value, dict) and value.get("artifact_id")
        }
        verified_variants: dict[str, tuple[Path, str]] = {}
        if set(receipt_variant_hashes) != set(variants) or set(public_variants) != set(variants):
            raise ContractError("comparison candidate hash coverage mismatch")
        for artifact, variant_value in variants.items():
            if not isinstance(variant_value, dict):
                raise ContractError("comparison candidate mapping is invalid")
            variant_candidate = str(variant_value.get("candidate_id") or "")
            if not IDENTIFIER.fullmatch(variant_candidate):
                raise ContractError("comparison candidate ID is unsafe")
            candidate_root = (
                Path(job["figure"]["job_dir"]) / "candidates" / figure_id / variant_candidate
            ).resolve()
            variant_source = resolve_within(
                project_root,
                variant_value.get("source_path", ""),
                f"{figure_id}.comparison_variant",
                must_exist=True,
            )
            try:
                variant_source.relative_to(candidate_root)
            except ValueError as exc:
                raise ContractError("comparison source escapes its candidate directory") from exc
            variant_sha = _sha256(variant_source)
            if any(
                str(value or "").upper() != variant_sha
                for value in (
                    variant_value.get("sha256"),
                    public_variants[artifact].get("sha256"),
                    receipt_variant_hashes.get(artifact),
                )
            ):
                raise ContractError("comparison candidate input hash drifted")
            if expected_final_size is not None:
                variant_render = resolve_within(
                    project_root,
                    variant_value.get("final_size_render_path", ""),
                    f"{figure_id}.comparison_variant_final_size_render",
                    must_exist=True,
                )
                variant_render_sha = _sha256(variant_render)
                receipt_render_hashes = input_hashes.get(
                    "variant_final_size_render_sha256"
                ) or {}
                if any(
                    str(value or "").upper() != variant_render_sha
                    for value in (
                        variant_value.get("final_size_render_sha256"),
                        public_variants[artifact].get("final_size_render_sha256"),
                        receipt_render_hashes.get(artifact),
                    )
                ):
                    raise ContractError("comparison candidate final-size render hash drifted")
            verified_variants[str(artifact)] = (variant_source, variant_sha)

        comparisons = receipt.get("comparisons")
        if not isinstance(comparisons, dict) or set(comparisons) != set(variants):
            raise ContractError("comparison receipt does not cover the frozen candidate suite")

        winner = receipt.get("winner") or {}
        receipt_selects_original = (
            winner.get("role") == "current_figure"
            and winner.get("artifact_id") == "baseline"
            and winner.get("candidate_id") == "existing"
            and receipt.get("automatic_selection") == "existing"
            and bool(receipt.get("fallback_reason"))
            and validation.get("strict_superiority") is False
            and receipt.get("suite_conclusion") != "strictly_better"
        )
        if selected_candidate == "existing" and not receipt_selects_original:
            raise ContractError("comparison receipt does not select the original fail-safe")
        if receipt_selects_original:
            return {
                "valid": selected_candidate == "existing",
                "receipt_valid": True,
                "reason": receipt.get("fallback_reason"),
                "receipt": str(receipt_path),
                "receipt_sha256": receipt["receipt_sha256"],
                "reviewer_role": "independent_reviewer_agent",
                "winner_candidate": "existing",
                "winner_source": str(current),
                "winner_sha256": current_sha,
            }

        if (
            validation.get("strict_superiority") is not True
            or validation.get("failures")
            or receipt.get("fallback_reason") is not None
            or receipt.get("suite_conclusion") != "strictly_better"
        ):
            raise ContractError("candidate_not_strictly_better")
        artifact_id = winner.get("artifact_id")
        if (
            winner.get("role") != "candidate"
            or winner.get("candidate_id") != selected_candidate
            or receipt.get("automatic_selection") != selected_candidate
            or not isinstance(artifact_id, str)
        ):
            raise ContractError("comparison_winner_does_not_match_selected_candidate")
        variant = variants.get(artifact_id)
        if not isinstance(variant, dict) or variant.get("candidate_id") != selected_candidate:
            raise ContractError("comparison_private_winner_mapping_missing")
        if not IDENTIFIER.fullmatch(selected_candidate):
            raise ContractError("comparison winner candidate ID is unsafe")
        if not _strict_comparison_is_consistent(comparisons.get(artifact_id)):
            raise ContractError("comparison winner dimensions do not prove strict superiority")
        source, variant_sha = verified_variants[artifact_id]
        if source.suffix.lower() not in {".pdf", ".svg", ".png"}:
            raise ContractError("comparison winner is not a PaperSpine publication format")
    except (ContractError, OSError, ValueError) as exc:
        return {"valid": False, "reason": str(exc), "receipt": str(receipt_path)}
    return {
        "valid": True,
        "reason": None,
        "receipt": str(receipt_path),
        "receipt_sha256": receipt["receipt_sha256"],
        "reviewer_role": "independent_reviewer_agent",
        "winner_candidate": selected_candidate,
        "winner_source": str(source),
        "winner_sha256": variant_sha,
    }


def resolve_redesign_decisions(
    job: dict[str, Any], requests: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    """Return a decision whose redesign branches are safe for final assembly."""
    normalized = deepcopy(decision)
    request_by_id = {item["figure_id"]: item for item in requests["figures"]}
    for selected in normalized["figures"]:
        request = request_by_id[selected["figure_id"]]
        if request.get("publication_role", "main") == "omit":
            selected.update(
                {
                    "selected_candidate": "omitted",
                    "panel_count": 0,
                    "panel_decisions": [],
                    "selection_authority": "editorial_disposition",
                    "comparison_receipt": None,
                    "comparison_validation": None,
                    "fallback_reason": None,
                }
            )
            continue
        if request.get("decision") in {"keep", *REDESIGN_DECISIONS}:
            project_root = Path(job["project_root"]).resolve()
            bind_current_figure_sha(request, project_root)
        if request.get("decision") not in REDESIGN_DECISIONS:
            continue
        candidate_id = selected["selected_candidate"]
        if candidate_id == "existing":
            audit = _comparison_receipt_audit(
                job, request, "existing", selected.get("comparison_receipt")
            )
            selected["selection_authority"] = selected.get("selection_authority") or (
                "independent_fail_safe_original" if audit.get("valid") else "human_or_fail_safe_original"
            )
            selected["fallback_reason"] = selected.get("fallback_reason") or (
                audit.get("reason") if audit.get("valid") else "explicit_original_selection"
            )
            selected["comparison_receipt"] = audit.get("receipt")
            selected["comparison_validation"] = audit
            selected["panel_count"] = 0
            selected["layout"] = "existing"
            selected["panel_decisions"] = []
            continue
        audit = _comparison_receipt_audit(
            job, request, candidate_id, selected.get("comparison_receipt")
        )
        if audit["valid"]:
            selected["selection_authority"] = "independent_strict_superiority"
            selected["comparison_receipt"] = audit["receipt"]
            selected["comparison_validation"] = audit
            continue
        selected.update(
            {
                "selected_candidate": "existing",
                "panel_count": 0,
                "layout": "existing",
                "panel_decisions": [],
                "selection_authority": "independent_comparison_fail_safe",
                "comparison_receipt": audit.get("receipt"),
                "comparison_validation": audit,
                "fallback_reason": audit["reason"],
            }
        )
        if audit.get("receipt_valid"):
            selected["selection_authority"] = "independent_fail_safe_original"
    return normalized
