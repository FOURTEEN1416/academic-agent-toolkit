"""Fail-closed W5--W6 publication-stage service.

The service composes the existing canonical-artifact and readiness contracts.
It is deliberately detached from ProductRunner and ProductKernel handler
registration: the authoritative Runner calls one method inside its own CAS
command and records the returned artifact descriptors atomically.

No method learns or embeds domain, venue, or target rules.  Every semantic
operation requires an exact, frozen W4 authority projection.  A structurally
valid response is candidate evidence only and never grants external action.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping, Sequence

from .quality_readiness import (
    QualityContractError,
    QualitySubject,
    ReadinessCompiler,
    TruthStatus,
    canonical_sha256,
    dependency_closure,
)
from .figure_correction import (
    FigureCorrectionError,
    validate_figure_correction_receipt,
    validate_target_size_legibility_receipt,
)
from .figure_reference_mapping import (
    FigureReferenceMappingError,
    project_figure_plan_for_user,
    validate_figure_reference_plan,
)
from .research_argument_service import validate_frozen_authority_projection


PIPELINE_CONTRACT_VERSION = "1.0"
AUTHORITY_IDS = ("direction_authority", "target_authority", "claim_evidence")
FIGURE_MODES = {"zero", "keep", "redesign", "create", "mixed"}
REQUIRED_SURFACES = {"pdf", "word"}
REQUESTED_SCOPES = {"manuscript", "local_delivery", "submission_package"}
SUBMISSION_ONLY_BLOCKER_CODES = {
    "AUTHOR_ONLY_TARGET_MAPPING_INCOMPLETE",
    "AUTHOR_CLOSE_INCOMPLETE",
    "NON_COMPENSATORY_READINESS_BLOCKED",
}
LOCAL_DELIVERY_ONLY_BLOCKER_CODES = {
    "TARGET_OBLIGATIONS_MISSING",
    "TARGET_OBLIGATIONS_INVALID",
    "TARGET_OBLIGATION_FINDINGS_INVALID",
    "TARGET_OBLIGATION_EVIDENCE_MISSING",
    "TARGET_OBLIGATION_UNSATISFIED",
    "TARGET_PACKAGE_MAPPING_INCOMPLETE",
    "TARGET_PACKAGE_MANIFEST_INVALID",
    *SUBMISSION_ONLY_BLOCKER_CODES,
}
TARGET_OBLIGATION_SCOPES = {"local_delivery", "author_only_submission"}
AUTHOR_FACT_KEYS = {
    "author_identity",
    "affiliation",
    "orcid",
    "funding",
    "conflict_of_interest",
    "data_availability",
    "code_availability",
    "author_contributions",
    "corresponding_author",
}
REQUIRED_PREDICATE_IDS = {
    "canonical_artifacts_bound",
    "final_claim_inventory_valid",
    "evidence_verification_valid",
    "independent_review_valid",
    "quality_objections_closed",
    "final_render_bound",
    "surface_semantics_valid",
    "visual_accessibility_valid",
    "target_research_valid",
    "target_compliance_valid",
    "target_bundle_fresh",
    "author_items_closed",
    "author_confirmed_current_revision",
}


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finding(code: str, message: str, path: str = "") -> dict[str, str]:
    finding = {"code": code, "message": message}
    if path:
        finding["path"] = path
    return finding


def _hashed(payload: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(payload))
    result.pop(field, None)
    result[field] = canonical_sha256(result)
    return result


def _validate_hashed(
    payload: Any,
    hash_field: str,
    code: str,
    path: str,
) -> list[dict[str, str]]:
    if not isinstance(payload, Mapping):
        return [_finding(code, "receipt must be an object", path)]
    supplied = payload.get(hash_field)
    unsigned = {key: value for key, value in payload.items() if key != hash_field}
    if not _is_sha256(supplied) or supplied != canonical_sha256(unsigned):
        return [_finding(code, f"{hash_field} does not bind the exact receipt", path)]
    return []


def _validate_target_obligations(
    value: Any,
    target_authority_sha256: str | None,
) -> tuple[
    list[Mapping[str, Any]],
    set[str],
    set[str],
    list[dict[str, str]],
]:
    findings: list[dict[str, str]] = []
    if not isinstance(value, Mapping):
        return (
            [],
            set(),
            set(),
            [
                _finding(
                    "TARGET_OBLIGATIONS_MISSING",
                    "frozen target obligation ledger is required",
                    "target_obligations",
                )
            ],
        )
    items = value.get("obligations")
    obligation_items = items if isinstance(items, list) else []
    ledger_valid = (
        value.get("contract") == "paperspine5.target-obligation-ledger"
        and value.get("contract_version") == "1.0"
        and value.get("status") == "PASS"
        and value.get("frozen") is True
        and value.get("target_authority_sha256") == target_authority_sha256
        and value.get("external_action_authorized") is False
        and bool(obligation_items)
        and not _validate_hashed(value, "ledger_sha256", "", "")
    )
    local_ids: set[str] = set()
    author_only_ids: set[str] = set()
    seen_ids: set[str] = set()
    for index, item in enumerate(obligation_items):
        path = f"target_obligations.obligations[{index}]"
        if not isinstance(item, Mapping):
            findings.append(
                _finding(
                    "TARGET_OBLIGATION_CLASSIFICATION_INVALID",
                    "every target obligation must be a typed object",
                    path,
                )
            )
            continue
        obligation_id = str(item.get("obligation_id") or "").strip()
        scope = str(item.get("readiness_scope") or "").strip()
        binding = item.get("authority_binding")
        classification_valid = (
            bool(obligation_id)
            and obligation_id not in seen_ids
            and isinstance(item.get("hard"), bool)
            and scope in TARGET_OBLIGATION_SCOPES
            and _nonempty(item.get("authority_rule_id"))
            and isinstance(binding, Mapping)
            and binding.get("artifact_id") == "target_authority"
            and binding.get("sha256") == target_authority_sha256
            and _nonempty(item.get("evidence_locator"))
        )
        if scope == "author_only_submission":
            classification_valid = classification_valid and (
                item.get("author_fact_key") in AUTHOR_FACT_KEYS
            )
        else:
            classification_valid = classification_valid and (
                "author_fact_key" not in item
            )
        if not classification_valid:
            findings.append(
                _finding(
                    "TARGET_OBLIGATION_CLASSIFICATION_INVALID",
                    "obligation scope must be evidence-bound; only typed author facts may be submission-only",
                    path,
                )
            )
            continue
        seen_ids.add(obligation_id)
        if item.get("hard") is True:
            if scope == "local_delivery":
                local_ids.add(obligation_id)
            else:
                author_only_ids.add(obligation_id)
    if not local_ids:
        findings.append(
            _finding(
                "TARGET_OBLIGATION_CLASSIFICATION_INVALID",
                "at least one hard non-author target-adaptation obligation must apply to local delivery",
                "target_obligations.obligations",
            )
        )
    if not ledger_valid or findings:
        findings.append(
            _finding(
                "TARGET_OBLIGATIONS_INVALID",
                "obligations must be frozen, hash-bound, and typed from current target authority",
                "target_obligations",
            )
        )
    return obligation_items, local_ids, author_only_ids, findings


def _validate_target_obligation_findings(
    review: Any,
    *,
    target_authority_sha256: str | None,
    path: str,
) -> tuple[list[Mapping[str, Any]], list[dict[str, str]]]:
    if not isinstance(review, Mapping):
        return [], []
    raw = review.get("target_obligation_findings")
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], [
            _finding(
                "TARGET_OBLIGATION_FINDINGS_INVALID",
                "independent target findings must be an array",
                f"{path}.target_obligation_findings",
            )
        ]
    findings: list[Mapping[str, Any]] = []
    blockers: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        item_path = f"{path}.target_obligation_findings[{index}]"
        obligation_id = str(item.get("obligation_id") or "") if isinstance(item, Mapping) else ""
        valid = (
            isinstance(item, Mapping)
            and item.get("contract") == "paperspine5.target-obligation-finding"
            and item.get("contract_version") == "1.0"
            and bool(obligation_id)
            and obligation_id not in seen
            and _nonempty(item.get("authority_rule_id"))
            and item.get("target_authority_sha256") == target_authority_sha256
            and item.get("status") in {"satisfied", "unsatisfied"}
            and _nonempty(item.get("artifact_id"))
            and _is_sha256(item.get("artifact_sha256"))
            and _nonempty(item.get("evidence_locator"))
            and item.get("external_action_authorized") is False
            and not _validate_hashed(item, "finding_sha256", "", "")
        )
        if not valid:
            blockers.append(
                _finding(
                    "TARGET_OBLIGATION_FINDINGS_INVALID",
                    "each independent target finding must bind the current authority, artifact, and typed satisfaction verdict",
                    item_path,
                )
            )
            continue
        seen.add(obligation_id)
        findings.append(item)
    return findings, blockers


def _mapping_covers(
    obligation_ids: set[str],
    obligations: Mapping[str, Mapping[str, Any]],
    mapped: Mapping[str, Mapping[str, Any]],
    current: Mapping[str, str],
    review_closure: Mapping[str, Any] | None,
    target_authority_sha256: str | None,
    *,
    require_independent_finding: bool = True,
) -> tuple[bool, list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    review_findings = {
        str(item.get("obligation_id") or ""): item
        for item in (review_closure or {}).get("target_obligation_findings", [])
        if isinstance(item, Mapping)
    }
    for obligation_id in obligation_ids:
        item = mapped.get(obligation_id, {})
        obligation = obligations.get(obligation_id, {})
        finding = review_findings.get(obligation_id, {})
        artifact_id = str(item.get("artifact_id") or "")
        mapping_valid = (
            item.get("status") is not True
            or current.get(artifact_id) != item.get("artifact_sha256")
        )
        if mapping_valid:
            blockers.append(
                _finding(
                    "TARGET_PACKAGE_MAPPING_INCOMPLETE",
                    "target mapping must bind an exact current artifact",
                    f"package_mapping.{obligation_id}",
                )
            )
            continue
        if not require_independent_finding:
            continue
        finding_valid = (
            finding.get("authority_rule_id") == obligation.get("authority_rule_id")
            and finding.get("target_authority_sha256") == target_authority_sha256
            and finding.get("artifact_id") == artifact_id
            and finding.get("artifact_sha256") == item.get("artifact_sha256")
            and not _validate_hashed(finding, "finding_sha256", "", "")
        )
        if not finding_valid:
            blockers.append(
                _finding(
                    "TARGET_OBLIGATION_EVIDENCE_MISSING",
                    "producer mapping requires a matching current independent target finding",
                    f"review_closure.target_obligation_findings.{obligation_id}",
                )
            )
        elif finding.get("status") != "satisfied":
            blockers.append(
                _finding(
                    "TARGET_OBLIGATION_UNSATISFIED",
                    "a hard target rule remains unsatisfied in independent current review",
                    f"review_closure.target_obligation_findings.{obligation_id}",
                )
            )
    return bool(obligation_ids) and not blockers, blockers


def _validate_subject(value: Any) -> tuple[QualitySubject | None, list[dict[str, str]]]:
    try:
        return QualitySubject.from_mapping(value), []
    except (QualityContractError, TypeError, ValueError) as exc:
        return None, [_finding("PUBLICATION_SUBJECT_INVALID", str(exc), "subject")]


def _same_subject(value: Any, subject: QualitySubject) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        other = QualitySubject.from_mapping(value)
    except (QualityContractError, TypeError, ValueError):
        return False
    return other.as_dict() == subject.as_dict()


def _artifact_descriptor(
    artifact_id: str,
    artifact_type: str,
    payload: Mapping[str, Any],
    subject: QualitySubject,
    *,
    status: str = "PASS",
) -> dict[str, Any]:
    canonical = copy.deepcopy(dict(payload))
    return {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "task_id": subject.task_id,
        "revision_id": subject.revision_id,
        "sha256": canonical_sha256(canonical),
        "status": status,
        "payload": canonical,
        "external_action_authorized": False,
    }


def _response(
    operation: str,
    raw_subject: Any,
    blockers: Sequence[Mapping[str, str]],
    *,
    next_stage: str,
    descriptors: Sequence[Mapping[str, Any]] = (),
    invalidated: Iterable[str] = (),
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    subject = dict(raw_subject) if isinstance(raw_subject, Mapping) else {}
    payload = {
        "contract": "paperspine5.publication-stage-response",
        "contract_version": PIPELINE_CONTRACT_VERSION,
        "operation": operation,
        "task_id": str(subject.get("task_id") or ""),
        "revision_id": str(subject.get("revision_id") or ""),
        "status": "BLOCKED" if blockers else "PASS",
        "blockers": [dict(item) for item in blockers],
        "artifact_descriptors": [copy.deepcopy(dict(item)) for item in descriptors],
        "invalidated_artifacts": sorted({str(item) for item in invalidated}),
        "next_stage": next_stage,
        "details": copy.deepcopy(dict(details or {})),
        "external_action_authorized": False,
    }
    return _hashed(payload, "response_sha256")


def _validate_authority(
    value: Any,
    subject: QualitySubject,
    trusted_artifacts: Any,
) -> tuple[dict[str, Mapping[str, Any]], list[dict[str, str]]]:
    if not isinstance(value, Mapping):
        return {}, [
            _finding(
                "W4_AUTHORITY_MISSING",
                "a frozen W4 direction/target/claim-evidence authority is required",
                "frozen_authority",
            )
        ]
    trusted = (
        {str(key): str(item) for key, item in trusted_artifacts.items()}
        if isinstance(trusted_artifacts, Mapping)
        else {}
    )
    blockers = validate_frozen_authority_projection(
        value,
        trusted_artifacts=trusted,
        task_id=subject.task_id,
        revision_id=subject.revision_id,
    )
    raw_authorities = value.get("authorities")
    authorities = raw_authorities if isinstance(raw_authorities, Mapping) else {}
    normalized: dict[str, Mapping[str, Any]] = {}
    for artifact_id in AUTHORITY_IDS:
        item = authorities.get(artifact_id)
        if not isinstance(item, Mapping):
            continue
        sha256 = item.get("sha256")
        if subject.input_hashes.get(artifact_id) != sha256:
            blockers.append(
                _finding(
                    "W4_AUTHORITY_ITEM_STALE",
                    f"{artifact_id} is absent or changed in the publication subject",
                    f"subject.input_hashes.{artifact_id}",
                )
            )
        role = "direction" if artifact_id == "direction_authority" else (
            "target" if artifact_id == "target_authority" else "claim_evidence"
        )
        normalized[role] = item
    return normalized, blockers


def _validate_asset(
    value: Any,
    subject: QualitySubject,
    path: str,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    if not isinstance(value, Mapping):
        return None, [_finding("FIGURE_ASSET_INVALID", "asset must be an object", path)]
    artifact_id = str(value.get("artifact_id") or "")
    sha256 = value.get("sha256")
    if not artifact_id or not _is_sha256(sha256):
        return None, [
            _finding(
                "FIGURE_ASSET_UNBOUND",
                "asset requires artifact_id and lowercase SHA-256",
                path,
            )
        ]
    if str(value.get("revision_id") or "") != subject.revision_id:
        return None, [_finding("FIGURE_ASSET_STALE", "asset revision is stale", path)]
    if subject.input_hashes.get(artifact_id) != sha256:
        return None, [
            _finding(
                "FIGURE_ASSET_NOT_IN_SUBJECT",
                "asset hash is absent or changed in the immutable subject",
                path,
            )
        ]
    return {
        "artifact_id": artifact_id,
        "sha256": sha256,
        "revision_id": subject.revision_id,
    }, []


def evaluate_figure_intent(request: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate zero/keep/redesign/create without manufacturing a winner."""

    raw_subject = request.get("subject") if isinstance(request, Mapping) else None
    subject, blockers = _validate_subject(raw_subject)
    if subject is None:
        return _response(
            "evaluate_figure_intent",
            raw_subject,
            blockers,
            next_stage="awaiting_w4_authority",
        )
    authorities, authority_blockers = _validate_authority(
        request.get("frozen_authority"),
        subject,
        request.get("trusted_artifacts"),
    )
    blockers.extend(authority_blockers)
    raw_intent = request.get("intent")
    intent = raw_intent if isinstance(raw_intent, Mapping) else {}
    mode = intent.get("mode")
    producer_id = str(intent.get("producer_id") or "")
    if mode not in FIGURE_MODES:
        blockers.append(_finding("FIGURE_MODE_INVALID", "mode must be zero, keep, redesign, create, or mixed", "intent.mode"))
    if not producer_id:
        blockers.append(_finding("FIGURE_PRODUCER_MISSING", "producer_id is required", "intent.producer_id"))
    basis = intent.get("decision_basis_artifact_ids")
    basis_ids = {str(item) for item in basis} if isinstance(basis, list) else set()
    authority_ids = {str(item.get("artifact_id")) for item in authorities.values()}
    if not basis_ids or not basis_ids.issubset(authority_ids):
        blockers.append(
            _finding(
                "FIGURE_DECISION_BASIS_INVALID",
                "figure necessity must cite only frozen W4 authority artifacts",
                "intent.decision_basis_artifact_ids",
            )
        )
    raw_figures = intent.get("figures")
    figures = raw_figures if isinstance(raw_figures, list) else []
    raw_quality_evidence = request.get("figure_quality_evidence")
    figure_quality_evidence = (
        raw_quality_evidence if isinstance(raw_quality_evidence, Mapping) else {}
    )
    raw_reference_plans = request.get("reference_plans")
    reference_plans = (
        raw_reference_plans if isinstance(raw_reference_plans, Mapping) else {}
    )
    trusted_figure_master_receipt = request.get(
        "trusted_figure_master_receipt"
    )
    if mode == "zero" and figures:
        blockers.append(_finding("ZERO_FIGURE_HAS_ASSETS", "zero mode cannot carry figure assets", "intent.figures"))
    if mode in {"keep", "redesign", "create", "mixed"} and not figures:
        blockers.append(_finding("FIGURE_SET_EMPTY", f"{mode} requires at least one figure", "intent.figures"))

    material_coverage = intent.get("material_coverage")
    if material_coverage is not None:
        if not isinstance(material_coverage, Mapping):
            blockers.append(
                _finding(
                    "FIGURE_MATERIAL_COVERAGE_INVALID",
                    "material coverage must be a host-verified object",
                    "intent.material_coverage",
                )
            )
        else:
            dispositions = material_coverage.get("figure_dispositions")
            disposition_ids = [
                str(item.get("source_id") or "")
                for item in dispositions
                if isinstance(item, Mapping)
            ] if isinstance(dispositions, list) else []
            if (
                not _nonempty(material_coverage.get("primary_manuscript_source_id"))
                or material_coverage.get("status") != "PASS"
                or material_coverage.get("external_action_authorized") is not False
                or not _is_sha256(material_coverage.get("profile_sha256"))
                or not disposition_ids
                or any(not item for item in disposition_ids)
                or len(disposition_ids) != len(set(disposition_ids))
            ):
                blockers.append(
                    _finding(
                        "FIGURE_MATERIAL_COVERAGE_INCOMPLETE",
                        "host-verified material coverage must bind one primary manuscript and unique figure dispositions",
                        "intent.material_coverage",
                    )
                )

    normalized_figures: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_figure in enumerate(figures):
        path = f"intent.figures[{index}]"
        if not isinstance(raw_figure, Mapping):
            blockers.append(_finding("FIGURE_INTENT_INVALID", "figure must be an object", path))
            continue
        figure_mode = raw_figure.get("mode") if mode == "mixed" else mode
        if figure_mode not in {"keep", "redesign", "create"}:
            blockers.append(_finding("FIGURE_ITEM_MODE_INVALID", "mixed intents require each figure to declare keep, redesign, or create", f"{path}.mode"))
            figure_mode = "keep"
        figure_id = str(raw_figure.get("figure_id") or "")
        if not figure_id or figure_id in seen_ids:
            blockers.append(_finding("FIGURE_ID_INVALID", "figure_id must be non-empty and unique", path))
            continue
        seen_ids.add(figure_id)
        panels_raw = raw_figure.get("panels")
        panels = panels_raw if isinstance(panels_raw, list) else []
        panel_ids = [str(item.get("panel_id") or "") for item in panels if isinstance(item, Mapping)]
        if not panel_ids or any(not item for item in panel_ids) or len(panel_ids) != len(set(panel_ids)):
            blockers.append(_finding("FIGURE_PANELS_INVALID", "each figure needs unique non-empty panel IDs", f"{path}.panels"))
        reference_plan_binding, plan_binding_issues = _validate_asset(
            raw_figure.get("reference_plan"),
            subject,
            f"{path}.reference_plan",
        )
        blockers.extend(plan_binding_issues)
        reference_plan_projection: dict[str, Any] | None = None
        if reference_plan_binding is not None:
            reference_plan = reference_plans.get(
                reference_plan_binding["artifact_id"]
            )
            if not isinstance(reference_plan, Mapping):
                blockers.append(
                    _finding(
                        "FIGURE_REFERENCE_PLAN_MISSING",
                        "the exact bound Master-frozen reference plan is unavailable",
                        f"{path}.reference_plan",
                    )
                )
            else:
                raw_plan_subject = reference_plan.get("subject")
                plan_revision = (
                    raw_plan_subject.get("runner_revision")
                    if isinstance(raw_plan_subject, Mapping)
                    else None
                )
                try:
                    validated_plan = validate_figure_reference_plan(
                        reference_plan,
                        expected_subject={
                            "task_id": subject.task_id,
                            "revision_id": plan_revision,
                            "material_snapshot_sha256": subject.input_hashes.get(
                                "materials.source-ledger"
                            ),
                        },
                        expected_figure={
                            **dict(raw_figure),
                            "producer_id": producer_id,
                        },
                        registered_artifacts=subject.input_hashes,
                        trusted_actor_receipt=(
                            trusted_figure_master_receipt
                            if isinstance(trusted_figure_master_receipt, Mapping)
                            else None
                        ),
                    )
                except FigureReferenceMappingError as exc:
                    blockers.append(
                        _finding(
                            "FIGURE_REFERENCE_PLAN_INVALID",
                            str(exc),
                            f"{path}.reference_plan",
                        )
                    )
                else:
                    if (
                        reference_plan_binding["sha256"]
                        != validated_plan["plan_sha256"]
                    ):
                        blockers.append(
                            _finding(
                                "FIGURE_REFERENCE_PLAN_STALE",
                                "reference_plan does not bind the exact frozen plan hash",
                                f"{path}.reference_plan.sha256",
                            )
                        )
                    else:
                        reference_plan_projection = project_figure_plan_for_user(
                            validated_plan,
                            trusted_actor_receipt=(
                                trusted_figure_master_receipt
                                if isinstance(trusted_figure_master_receipt, Mapping)
                                else None
                            ),
                        )
        current: dict[str, Any] | None = None
        candidates: list[dict[str, Any]] = []
        if figure_mode in {"keep", "redesign"}:
            current, issues = _validate_asset(raw_figure.get("current_asset"), subject, f"{path}.current_asset")
            blockers.extend(issues)
        raw_candidates = raw_figure.get("candidate_assets")
        for candidate_index, raw_candidate in enumerate(raw_candidates if isinstance(raw_candidates, list) else []):
            candidate, issues = _validate_asset(
                raw_candidate,
                subject,
                f"{path}.candidate_assets[{candidate_index}]",
            )
            blockers.extend(issues)
            if candidate:
                candidates.append(candidate)
        selected = current
        outcome = "kept" if figure_mode == "keep" else figure_mode
        comparison = raw_figure.get("independent_comparison")
        if figure_mode in {"redesign", "create"}:
            if not candidates:
                blockers.append(_finding("FIGURE_CANDIDATES_EMPTY", f"{figure_mode} requires candidates", f"{path}.candidate_assets"))
            if not isinstance(comparison, Mapping):
                blockers.append(_finding("FIGURE_COMPARISON_MISSING", "independent comparison is required", f"{path}.independent_comparison"))
            else:
                reviewer = str(comparison.get("reviewer_id") or "")
                producers = {producer_id, *[str(item) for item in comparison.get("producer_ids", []) if _nonempty(item)]}
                if not reviewer or reviewer in producers:
                    blockers.append(_finding("FIGURE_COMPARISON_NOT_INDEPENDENT", "comparison reviewer aliases a producer", f"{path}.independent_comparison.reviewer_id"))
                if comparison.get("status") != "PASS":
                    blockers.append(_finding("FIGURE_COMPARISON_BLOCKED", "comparison must explicitly PASS", f"{path}.independent_comparison.status"))
                reviewed = {str(item) for item in comparison.get("reviewed_asset_hashes", []) if _is_sha256(item)}
                required = {item["sha256"] for item in candidates}
                if current:
                    required.add(current["sha256"])
                if reviewed != required:
                    blockers.append(_finding("FIGURE_COMPARISON_SCOPE_MISMATCH", "comparison must cover every exact current/candidate asset", f"{path}.independent_comparison.reviewed_asset_hashes"))
                decision = comparison.get("decision")
                selected_hash = comparison.get("selected_sha256")
                if figure_mode == "redesign":
                    if decision == "redesign_wins":
                        selected = next((item for item in candidates if item["sha256"] == selected_hash), None)
                        if selected is None:
                            blockers.append(_finding("REDESIGN_WINNER_INVALID", "selected redesign is not a reviewed candidate", f"{path}.independent_comparison.selected_sha256"))
                        outcome = "redesign_selected"
                    elif decision in {"keep_original", "no_clear_winner"}:
                        if not current or selected_hash != current["sha256"]:
                            blockers.append(_finding("REDESIGN_FALLBACK_INVALID", "a non-winning redesign must select the exact original", f"{path}.independent_comparison.selected_sha256"))
                        selected = current
                        outcome = "fallback_original"
                    else:
                        blockers.append(_finding("REDESIGN_DECISION_INVALID", "redesign decision is invalid", f"{path}.independent_comparison.decision"))
                else:
                    selected = next((item for item in candidates if item["sha256"] == selected_hash), None)
                    if decision != "candidate_wins" or selected is None:
                        blockers.append(_finding("CREATE_WINNER_INVALID", "create requires an independently selected candidate winner", f"{path}.independent_comparison"))
                    outcome = "created"
        correction_receipt_id = str(
            raw_figure.get("correction_receipt_artifact_id") or ""
        )
        legibility_receipt_id = str(
            raw_figure.get("target_size_legibility_artifact_id") or ""
        )
        if figure_quality_evidence:
            legibility_payload = figure_quality_evidence.get(legibility_receipt_id)
            if not legibility_receipt_id or not isinstance(
                legibility_payload, Mapping
            ):
                blockers.append(
                    _finding(
                        "TARGET_SIZE_LEGIBILITY_RECEIPT_MISSING",
                        "every selected delivery figure requires a current PaperSpine target-size receipt",
                        f"{path}.target_size_legibility_artifact_id",
                    )
                )
            elif not isinstance(selected, Mapping):
                blockers.append(
                    _finding(
                        "TARGET_SIZE_LEGIBILITY_ASSET_MISSING",
                        "target-size evidence requires one selected figure asset",
                        path,
                    )
                )
            else:
                try:
                    validate_target_size_legibility_receipt(
                        dict(legibility_payload),
                        figure_id=figure_id,
                        figure_sha256=str(selected.get("sha256") or ""),
                        require_pass=True,
                    )
                except FigureCorrectionError as exc:
                    blockers.append(
                        _finding(
                            "TARGET_SIZE_LEGIBILITY_BLOCKED",
                            str(exc),
                            f"{path}.target_size_legibility_artifact_id",
                        )
                    )
            if correction_receipt_id:
                correction_payload = figure_quality_evidence.get(
                    correction_receipt_id
                )
                if not isinstance(correction_payload, Mapping):
                    blockers.append(
                        _finding(
                            "FIGURE_CORRECTION_RECEIPT_MISSING",
                            "the selected corrected figure lacks its current typed correction receipt",
                            f"{path}.correction_receipt_artifact_id",
                        )
                    )
                else:
                    try:
                        validated_correction = validate_figure_correction_receipt(
                            dict(correction_payload)
                        )
                    except FigureCorrectionError as exc:
                        blockers.append(
                            _finding(
                                "FIGURE_CORRECTION_RECEIPT_INVALID",
                                str(exc),
                                f"{path}.correction_receipt_artifact_id",
                            )
                        )
                    else:
                        if (
                            validated_correction["figure_id"] != figure_id
                            or not isinstance(current, Mapping)
                            or validated_correction["source"]["sha256"]
                            != current.get("sha256")
                            or not isinstance(selected, Mapping)
                            or validated_correction["output"]["sha256"]
                            != selected.get("sha256")
                        ):
                            blockers.append(
                                _finding(
                                    "FIGURE_CORRECTION_RECEIPT_STALE",
                                    "correction receipt does not bind the exact current and selected figure bytes",
                                    f"{path}.correction_receipt_artifact_id",
                                )
                            )
        normalized_figures.append(
            {
                "figure_id": figure_id,
                "mode": figure_mode,
                "panels": sorted(set(panel_ids)),
                "reference_plan_binding": reference_plan_binding,
                "reference_plan": reference_plan_projection,
                "selected_asset": selected,
                "outcome": outcome,
                "comparison_sha256": canonical_sha256(comparison) if isinstance(comparison, Mapping) else None,
                "correction_receipt_artifact_id": correction_receipt_id or None,
                "target_size_legibility_artifact_id": (
                    legibility_receipt_id or None
                ),
            }
        )

    receipt = {
        "contract": "paperspine5.figure-intent",
        "contract_version": PIPELINE_CONTRACT_VERSION,
        "subject": subject.as_dict(),
        "mode": mode,
        "decision_basis_artifact_ids": sorted(basis_ids),
        "figures": normalized_figures,
        "producer_id": producer_id,
        "material_coverage": copy.deepcopy(material_coverage),
        "status": "BLOCKED" if blockers else "PASS",
        "external_action_authorized": False,
    }
    receipt = _hashed(receipt, "receipt_sha256")
    descriptor = _artifact_descriptor(
        "publication.figure-intent",
        "quality.figure-intent",
        receipt,
        subject,
        status=receipt["status"],
    )
    return _response(
        "evaluate_figure_intent",
        raw_subject,
        blockers,
        next_stage="awaiting_figure_intent" if blockers else "canonical_binding",
        descriptors=[descriptor],
        details={"figure_intent": receipt},
    )


def _validate_canonical_bundle(
    bundle: Any, subject: QualitySubject
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if not isinstance(bundle, Mapping):
        return [_finding("CANONICAL_BUNDLE_MISSING", "canonical artifact bundle is required", "canonical_bundle")]
    if bundle.get("contract") != "paperspine5.canonical-artifact-bundle" or bundle.get("status") != "PASS":
        blockers.append(_finding("CANONICAL_BUNDLE_BLOCKED", "canonical bundle must be PASS", "canonical_bundle"))
    if not _same_subject(bundle.get("subject"), subject):
        blockers.append(_finding("CANONICAL_BUNDLE_STALE", "canonical bundle subject changed", "canonical_bundle.subject"))
    blockers.extend(_validate_hashed(bundle, "bundle_sha256", "CANONICAL_BUNDLE_HASH_INVALID", "canonical_bundle.bundle_sha256"))
    if bundle.get("external_action_authorized") is not False:
        blockers.append(_finding("CANONICAL_EXTERNAL_ACTION_FORBIDDEN", "canonical bundle cannot authorize actions", "canonical_bundle"))
    material_coverage = bundle.get("material_coverage")
    if not isinstance(material_coverage, Mapping):
        blockers.append(
            _finding(
                "MATERIAL_COVERAGE_MISSING",
                "a host-verified material coverage receipt is required",
                "canonical_bundle.material_coverage",
            )
        )
    else:
        if (
            material_coverage.get("contract")
            != "paperspine5.material-coverage-receipt"
            or material_coverage.get("status") != "PASS"
            or material_coverage.get("external_action_authorized") is not False
            or not _same_subject(material_coverage.get("subject"), subject)
            or not _is_sha256(material_coverage.get("profile_sha256"))
            or not _is_sha256(material_coverage.get("canonical_source_sha256"))
            or material_coverage.get("readiness_contradictions") != []
        ):
            blockers.append(
                _finding(
                    "MATERIAL_COVERAGE_INVALID",
                    "material coverage must bind the current source, profile, subject, and an empty contradiction set",
                    "canonical_bundle.material_coverage",
                )
            )
        blockers.extend(
            _validate_hashed(
                material_coverage,
                "receipt_sha256",
                "MATERIAL_COVERAGE_HASH_INVALID",
                "canonical_bundle.material_coverage.receipt_sha256",
            )
        )
        primary_source_id = material_coverage.get("primary_manuscript_source_id")
        ratio = material_coverage.get("source_word_coverage_ratio")
        if primary_source_id is not None and (
            not _nonempty(primary_source_id)
            or isinstance(ratio, bool)
            or not isinstance(ratio, (int, float))
            or ratio < 0.25
        ):
            blockers.append(
                _finding(
                    "PRIMARY_MANUSCRIPT_COVERAGE_INSUFFICIENT",
                    "a populated primary manuscript cannot be silently collapsed below the host coverage floor",
                    "canonical_bundle.material_coverage.source_word_coverage_ratio",
                )
            )
    final_claim = bundle.get("final_claim_index")
    if not isinstance(final_claim, Mapping) or final_claim.get("status") != "PASS":
        blockers.append(_finding("FINAL_CLAIM_INDEX_BLOCKED", "PASS FinalClaimIndex is required", "canonical_bundle.final_claim_index"))
    else:
        blockers.extend(_validate_hashed(final_claim, "receipt_sha256", "FINAL_CLAIM_INDEX_HASH_INVALID", "canonical_bundle.final_claim_index.receipt_sha256"))
        claims = final_claim.get("claims")
        retention = final_claim.get("retention_omission")
        if not isinstance(claims, list) or not isinstance(retention, list) or len(claims) != len(retention):
            blockers.append(_finding("FINAL_CLAIM_RETENTION_INCOMPLETE", "every final claim needs one retention/omission record", "canonical_bundle.final_claim_index"))
        else:
            claim_ids = {str(item.get("claim_id")) for item in claims if isinstance(item, Mapping)}
            retained_ids = {str(item.get("claim_id")) for item in retention if isinstance(item, Mapping)}
            if claim_ids != retained_ids or any(
                item.get("disposition") == "omitted"
                and (item.get("omission_allowed") is not True or not _nonempty(item.get("omission_reason")))
                for item in retention
                if isinstance(item, Mapping)
            ):
                blockers.append(_finding("FINAL_CLAIM_OMISSION_INVALID", "retention/omission does not preserve the independent claim scope", "canonical_bundle.final_claim_index.retention_omission"))
    return blockers


def _validate_figure_bindings(
    bundle: Any, intent: Any
) -> list[dict[str, str]]:
    """Recheck the canonical compiler's panel/result/argument receipts."""

    if not isinstance(bundle, Mapping) or not isinstance(intent, Mapping):
        return []
    blockers: list[dict[str, str]] = []
    receipts_raw = bundle.get("figure_intent_receipts")
    receipts = receipts_raw if isinstance(receipts_raw, list) else []
    intent_figures = (
        intent.get("figures") if isinstance(intent.get("figures"), list) else []
    )
    expected = {
        str(item.get("figure_id")): set(item.get("panels", []))
        for item in intent_figures
        if isinstance(item, Mapping) and _nonempty(item.get("figure_id"))
    }
    if intent.get("mode") == "zero":
        if receipts:
            blockers.append(
                _finding(
                    "ZERO_FIGURE_CANONICAL_BINDING_FORBIDDEN",
                    "zero-figure intent cannot acquire canonical panel bindings",
                    "canonical_bundle.figure_intent_receipts",
                )
            )
        return blockers
    observed: dict[str, set[str]] = {}
    for index, receipt in enumerate(receipts):
        path = f"canonical_bundle.figure_intent_receipts[{index}]"
        if not isinstance(receipt, Mapping) or receipt.get("status") != "PASS":
            blockers.append(
                _finding(
                    "PANEL_BINDING_RECEIPT_BLOCKED",
                    "each figure binding receipt must PASS",
                    path,
                )
            )
            continue
        blockers.extend(
            _validate_hashed(
                receipt,
                "receipt_sha256",
                "PANEL_BINDING_RECEIPT_HASH_INVALID",
                path,
            )
        )
        figure_id = str(receipt.get("figure_id") or "")
        panels_raw = receipt.get("panels")
        panels = panels_raw if isinstance(panels_raw, list) else []
        panel_ids: set[str] = set()
        for panel_index, panel in enumerate(panels):
            panel_path = f"{path}.panels[{panel_index}]"
            if not isinstance(panel, Mapping):
                blockers.append(
                    _finding(
                        "PANEL_BINDING_INVALID",
                        "panel binding must be an object",
                        panel_path,
                    )
                )
                continue
            panel_id = str(panel.get("panel_id") or "")
            panel_ids.add(panel_id)
            if (
                not _nonempty(panel.get("binding_id"))
                or not _nonempty(panel.get("argument_role"))
                or any(
                    not isinstance(panel.get(field), Mapping)
                    for field in (
                        "result_span",
                        "argument_span",
                        "evidence_phrase_span",
                        "reference_span",
                    )
                )
            ):
                blockers.append(
                    _finding(
                        "PANEL_ARGUMENT_BINDING_INCOMPLETE",
                        "panel must bind exact result, evidence-bearing argument span, and reference",
                        panel_path,
                    )
                )
        observed[figure_id] = panel_ids
    if observed != expected:
        blockers.append(
            _finding(
                "PANEL_BINDING_COVERAGE_MISMATCH",
                "canonical bindings must cover every selected figure panel exactly",
                "canonical_bundle.figure_intent_receipts",
            )
        )
    return blockers


def _validate_word_figure_media(
    bundle: Any,
    intent: Any,
    subject: QualitySubject,
    final_mapping_consumption: Any = None,
) -> tuple[list[dict[str, str]], str | None]:
    """Validate the typed Word-media proof for every selected scientific figure."""

    if not isinstance(bundle, Mapping) or not isinstance(intent, Mapping):
        return [], None
    figures_raw = intent.get("figures")
    figures = figures_raw if isinstance(figures_raw, list) else []
    if intent.get("mode") == "zero" or not figures:
        return [], None
    blockers: list[dict[str, str]] = []
    surfaces_raw = bundle.get("surface_receipts")
    surfaces = surfaces_raw if isinstance(surfaces_raw, list) else []
    word_surface = next(
        (
            item
            for item in surfaces
            if isinstance(item, Mapping) and item.get("surface_kind") == "word"
        ),
        None,
    )
    if not isinstance(word_surface, Mapping):
        return [
            _finding(
                "WORD_FIGURE_MEDIA_RECEIPT_MISSING",
                "a Word figure-media receipt is required for figure-active manuscripts",
                "canonical_bundle.surface_receipts.word",
            )
        ], None
    blockers.extend(
        _validate_hashed(
            word_surface,
            "receipt_sha256",
            "WORD_SURFACE_RECEIPT_HASH_INVALID",
            "canonical_bundle.surface_receipts.word.receipt_sha256",
        )
    )
    media = word_surface.get("figure_media")
    path = "canonical_bundle.surface_receipts.word.figure_media"
    if not isinstance(media, Mapping):
        return blockers + [
            _finding(
                "WORD_FIGURE_MEDIA_RECEIPT_MISSING",
                "figure-active Word delivery needs hash-bound visible media evidence",
                path,
            )
        ], None
    if (
        media.get("contract") != "paperspine5.word-figure-media-receipt"
        or media.get("contract_version") != "1.0"
        or media.get("status") != "PASS"
        or media.get("external_action_authorized") is not False
        or str(media.get("task_id") or "") != subject.task_id
        or str(media.get("revision_id") or "") != subject.revision_id
        or media.get("unsupported_media") != []
    ):
        blockers.append(
            _finding(
                "WORD_FIGURE_MEDIA_RECEIPT_INVALID",
                "Word figure media must be current, PASS, local-only, and contain no unsupported objects",
                path,
            )
        )
    blockers.extend(
        _validate_hashed(
            media,
            "receipt_sha256",
            "WORD_FIGURE_MEDIA_HASH_INVALID",
            f"{path}.receipt_sha256",
        )
    )
    expected: dict[str, Mapping[str, Any]] = {}
    for figure in figures:
        if not isinstance(figure, Mapping):
            continue
        figure_id = str(figure.get("figure_id") or "")
        selected = figure.get("selected_asset")
        if figure_id and isinstance(selected, Mapping):
            expected[figure_id] = selected
    mapping_bindings: dict[str, Mapping[str, Any]] = {}
    mapping_bindings_valid = final_mapping_consumption is None
    if isinstance(final_mapping_consumption, Mapping):
        bindings_raw = final_mapping_consumption.get("bindings")
        bindings = bindings_raw if isinstance(bindings_raw, list) else []
        mapping_bindings = {
            str(binding.get("figure_id") or ""): binding
            for binding in bindings
            if isinstance(binding, Mapping)
            and _nonempty(binding.get("figure_id"))
        }
        mapping_bindings_valid = (
            final_mapping_consumption.get("policy")
            == "required-for-every-new-j8"
            and _nonempty(final_mapping_consumption.get("build_id"))
            and len(mapping_bindings) == len(bindings)
            and set(mapping_bindings) == set(expected)
        )
    mappings_raw = media.get("mappings")
    mappings = mappings_raw if isinstance(mappings_raw, list) else []
    observed: dict[str, Mapping[str, Any]] = {}
    media_paths: set[str] = set()
    for index, mapping in enumerate(mappings):
        item_path = f"{path}.mappings[{index}]"
        if not isinstance(mapping, Mapping):
            blockers.append(
                _finding(
                    "WORD_FIGURE_MEDIA_MAPPING_INVALID",
                    "each Word figure mapping must be an object",
                    item_path,
                )
            )
            continue
        figure_id = str(mapping.get("figure_id") or "")
        source = mapping.get("source_artifact")
        word_media = mapping.get("word_media")
        conversion = mapping.get("conversion")
        expected_source = expected.get(figure_id)
        expected_source_sha256 = (
            expected_source.get("sha256")
            if isinstance(expected_source, Mapping)
            else None
        )
        if final_mapping_consumption is not None:
            binding = mapping_bindings.get(figure_id)
            if (
                not mapping_bindings_valid
                or not isinstance(binding, Mapping)
                or binding.get("accepted_candidate_manifest_sha256")
                != expected_source_sha256
            ):
                expected_source_sha256 = None
            else:
                expected_source_sha256 = binding.get("publication_binary_sha256")
        media_path = str(word_media.get("path") or "") if isinstance(word_media, Mapping) else ""
        if (
            figure_id in observed
            or media_path in media_paths
            or not isinstance(source, Mapping)
            or not isinstance(word_media, Mapping)
            or not isinstance(conversion, Mapping)
            or not isinstance(expected_source, Mapping)
            or source.get("artifact_id") != expected_source.get("artifact_id")
            or not _is_sha256(expected_source_sha256)
            or source.get("sha256") != expected_source_sha256
            or not media_path.startswith("word/media/")
            or not media_path.lower().endswith(".png")
            or word_media.get("media_type") != "image/png"
            or not _is_sha256(word_media.get("sha256"))
            or not isinstance(word_media.get("size_bytes"), int)
            or word_media.get("size_bytes") <= 8
            or conversion.get("method") not in {"pdf-to-png", "source-to-png"}
            or conversion.get("scope") != "word-delivery-surface-only"
            or conversion.get("canonical_source_preserved") is not True
        ):
            blockers.append(
                _finding(
                    "WORD_FIGURE_MEDIA_MAPPING_INVALID",
                    "each selected figure must map one-to-one to visible PNG media while preserving the canonical source",
                    item_path,
                )
            )
            continue
        observed[figure_id] = mapping
        media_paths.add(media_path)
    if (
        set(observed) != set(expected)
        or len(mappings) != len(expected)
        or media.get("selected_figure_count") != len(expected)
        or media.get("visible_supported_media_count") != len(expected)
    ):
        blockers.append(
            _finding(
                "WORD_FIGURE_MEDIA_COVERAGE_INCOMPLETE",
                "Word visible media must cover every selected scientific figure exactly once",
                path,
            )
        )
    render = media.get("render_evidence")
    expected_pages = [
        {"page": item.get("page"), "sha256": item.get("sha256")}
        for item in word_surface.get("pages", [])
        if isinstance(item, Mapping)
    ]
    observed_pages = [
        {"page": item.get("page"), "sha256": item.get("sha256")}
        for item in (render.get("pages", []) if isinstance(render, Mapping) else [])
        if isinstance(item, Mapping)
    ]
    if (
        not isinstance(render, Mapping)
        or render.get("surface_kind") != "word"
        or render.get("page_count") != word_surface.get("page_count")
        or observed_pages != expected_pages
    ):
        blockers.append(
            _finding(
                "WORD_FIGURE_RENDER_EVIDENCE_STALE",
                "Word media proof must bind the same page-complete portable render",
                f"{path}.render_evidence",
            )
        )
    receipt_sha = media.get("receipt_sha256")
    return blockers, str(receipt_sha) if _is_sha256(receipt_sha) else None


def _valid_lkg(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("contract") == "paperspine5.manuscript-head"
        and value.get("status") == "PASS"
        and _is_sha256(value.get("head_sha256"))
        and value.get("external_action_authorized") is False
    )


def bind_canonical(request: Mapping[str, Any]) -> dict[str, Any]:
    """Bind source/PDF/Word to one revision while preserving last-known-good."""

    raw_subject = request.get("subject") if isinstance(request, Mapping) else None
    subject, blockers = _validate_subject(raw_subject)
    if subject is None:
        return _response("bind_canonical", raw_subject, blockers, next_stage="awaiting_w4_authority")
    _, authority_blockers = _validate_authority(
        request.get("frozen_authority"), subject, request.get("trusted_artifacts")
    )
    blockers.extend(authority_blockers)
    bundle = request.get("canonical_bundle")
    blockers.extend(_validate_canonical_bundle(bundle, subject))
    intent = request.get("figure_intent")
    word_media_sha256: str | None = None
    if not isinstance(intent, Mapping) or intent.get("status") != "PASS" or not _same_subject(intent.get("subject"), subject):
        blockers.append(_finding("FIGURE_INTENT_NOT_CURRENT", "current PASS FigureIntent is required", "figure_intent"))
    else:
        blockers.extend(_validate_hashed(intent, "receipt_sha256", "FIGURE_INTENT_HASH_INVALID", "figure_intent.receipt_sha256"))
        blockers.extend(_validate_figure_bindings(bundle, intent))
        word_media_blockers, word_media_sha256 = _validate_word_figure_media(
            bundle, intent, subject, request.get("final_mapping_consumption")
        )
        blockers.extend(word_media_blockers)

    revision = request.get("manuscript_revision")
    artifacts: dict[str, Mapping[str, Any]] = {}
    if not isinstance(revision, Mapping):
        blockers.append(_finding("MANUSCRIPT_REVISION_MISSING", "canonical manuscript revision is required", "manuscript_revision"))
    else:
        if revision.get("contract") != "paperspine5.canonical-manuscript-revision" or revision.get("status") != "PASS":
            blockers.append(_finding("MANUSCRIPT_BUILD_BLOCKED", "current manuscript source/PDF/Word build is not PASS", "manuscript_revision"))
        if not _same_subject(revision.get("subject"), subject):
            blockers.append(_finding("MANUSCRIPT_REVISION_STALE", "manuscript revision changed task/revision/hash subject", "manuscript_revision.subject"))
        blockers.extend(_validate_hashed(revision, "revision_sha256", "MANUSCRIPT_REVISION_HASH_INVALID", "manuscript_revision.revision_sha256"))
        raw_artifacts = revision.get("artifacts")
        artifacts = raw_artifacts if isinstance(raw_artifacts, Mapping) else {}
        if set(artifacts) != {"source", "pdf", "word"}:
            blockers.append(_finding("MANUSCRIPT_SURFACES_INCOMPLETE", "source, PDF, and Word are all required", "manuscript_revision.artifacts"))
        for role in ("source", "pdf", "word"):
            item = artifacts.get(role)
            path = f"manuscript_revision.artifacts.{role}"
            if (
                not isinstance(item, Mapping)
                or not _nonempty(item.get("artifact_id"))
                or not _is_sha256(item.get("sha256"))
                or str(item.get("revision_id") or "") != subject.revision_id
                or item.get("build_status") != "PASS"
            ):
                blockers.append(_finding("MANUSCRIPT_SURFACE_INVALID", f"{role} is not a current PASS artifact", path))
                continue
            if subject.input_hashes.get(str(item.get("artifact_id"))) != item.get("sha256"):
                blockers.append(_finding("MANUSCRIPT_SURFACE_STALE", f"{role} hash changed or is absent from the subject", path))
        surface_receipts = bundle.get("surface_receipts", []) if isinstance(bundle, Mapping) else []
        by_kind = {
            str(item.get("surface_kind")): item
            for item in surface_receipts
            if isinstance(item, Mapping) and item.get("status") == "PASS"
        }
        if set(by_kind) != REQUIRED_SURFACES:
            blockers.append(_finding("MANUSCRIPT_SURFACE_QA_INCOMPLETE", "real page-complete PDF and Word receipts are required", "canonical_bundle.surface_receipts"))
        else:
            for role in REQUIRED_SURFACES:
                item = artifacts.get(role)
                receipt = by_kind[role]
                if isinstance(item, Mapping) and receipt.get("source", {}).get("sha256") != item.get("sha256"):
                    blockers.append(_finding("MANUSCRIPT_SURFACE_QA_STALE", f"{role} QA receipt does not bind current bytes", f"canonical_bundle.surface_receipts.{role}"))

    current_head: dict[str, Any] | None = None
    if not blockers and isinstance(revision, Mapping):
        current_head = _hashed(
            {
                "contract": "paperspine5.manuscript-head",
                "contract_version": PIPELINE_CONTRACT_VERSION,
                "subject": subject.as_dict(),
                "source_sha256": artifacts["source"]["sha256"],
                "pdf_sha256": artifacts["pdf"]["sha256"],
                "word_sha256": artifacts["word"]["sha256"],
                "word_figure_media_receipt_sha256": word_media_sha256,
                "canonical_bundle_sha256": bundle.get("bundle_sha256"),
                **({"final_mapping_consumption_sha256": canonical_sha256(request["final_mapping_consumption"])}
                   if isinstance(request.get("final_mapping_consumption"), Mapping) else {}),
                "status": "PASS",
                "last_known_good": False,
                "external_action_authorized": False,
            },
            "head_sha256",
        )
    active_head = current_head
    lkg = request.get("last_known_good")
    if blockers and _valid_lkg(lkg):
        active_head = copy.deepcopy(dict(lkg))
    descriptors = []
    if active_head:
        descriptors.append(
            _artifact_descriptor(
                "publication.manuscript-head",
                "canonical.manuscript-head",
                active_head,
                subject,
                status="BLOCKED" if blockers else "PASS",
            )
        )
    return _response(
        "bind_canonical",
        raw_subject,
        blockers,
        next_stage="canonical_repair" if blockers else "independent_review",
        descriptors=descriptors,
        invalidated=("independent_review", "final_render", "target_package", "readiness") if blockers else (),
        details={"active_manuscript_head": active_head, "using_last_known_good": bool(blockers and active_head)},
    )


def _review_independence(
    review: Any, producer_ids: set[str], path: str
) -> list[dict[str, str]]:
    if not isinstance(review, Mapping):
        return [_finding("INDEPENDENT_REVIEW_MISSING", "independent review receipt is required", path)]
    reviewer = str(review.get("reviewer_id") or "")
    if not reviewer or reviewer in producer_ids:
        return [_finding("INDEPENDENT_REVIEW_SELF_SIGNED", "reviewer aliases a producer", f"{path}.reviewer_id")]
    return []


def review_revision(request: Mapping[str, Any]) -> dict[str, Any]:
    """Require objection -> exact diff -> independent re-review closure."""

    raw_subject = request.get("subject") if isinstance(request, Mapping) else None
    subject, blockers = _validate_subject(raw_subject)
    if subject is None:
        return _response("review_revision", raw_subject, blockers, next_stage="awaiting_w4_authority")
    _, authority_blockers = _validate_authority(
        request.get("frozen_authority"), subject, request.get("trusted_artifacts")
    )
    blockers.extend(authority_blockers)
    head = request.get("manuscript_head")
    if not isinstance(head, Mapping) or head.get("status") != "PASS" or not _same_subject(head.get("subject"), subject):
        blockers.append(_finding("MANUSCRIPT_HEAD_NOT_CURRENT", "current PASS manuscript head is required", "manuscript_head"))
    else:
        blockers.extend(_validate_hashed(head, "head_sha256", "MANUSCRIPT_HEAD_HASH_INVALID", "manuscript_head.head_sha256"))
    bundle = request.get("canonical_bundle")
    blockers.extend(_validate_canonical_bundle(bundle, subject))
    producer_ids = {str(item) for item in request.get("producer_ids", []) if _nonempty(item)}
    if not producer_ids:
        blockers.append(_finding("REVIEW_PRODUCERS_MISSING", "producer_ids are required", "producer_ids"))
    initial = request.get("initial_review")
    diff = request.get("revision_diff")
    re_review = request.get("re_review")
    blockers.extend(_review_independence(initial, producer_ids, "initial_review"))
    initial_target_authority = subject.input_hashes.get("target_authority")
    if isinstance(diff, Mapping) and isinstance(initial, Mapping):
        # Historical findings bind the authority at the reviewed revision, not
        # a later cumulative replay's newly hashed authority descriptor.
        historical_subject = initial.get("subject")
        historical_hashes = historical_subject.get("input_hashes") if isinstance(historical_subject, Mapping) else None
        initial_target_authority = historical_hashes.get("target_authority") if isinstance(historical_hashes, Mapping) else None
    initial_target_findings, initial_target_blockers = _validate_target_obligation_findings(
        initial,
        target_authority_sha256=initial_target_authority,
        path="initial_review",
    )
    blockers.extend(initial_target_blockers)
    objections: list[Mapping[str, Any]] = []
    if isinstance(initial, Mapping):
        if initial.get("contract") != "paperspine5.publication-review" or initial.get("status") not in {"PASS", "REVISION_REQUIRED"}:
            blockers.append(_finding("INITIAL_REVIEW_BLOCKED", "initial independent review must be a completed inspection", "initial_review"))
        blockers.extend(_validate_hashed(initial, "review_sha256", "INITIAL_REVIEW_HASH_INVALID", "initial_review.review_sha256"))
        raw_objections = initial.get("objections")
        objections = raw_objections if isinstance(raw_objections, list) else []
    objection_ids = [str(item.get("objection_id") or "") for item in objections if isinstance(item, Mapping)]
    if any(not item for item in objection_ids) or len(objection_ids) != len(set(objection_ids)):
        blockers.append(_finding("REVIEW_OBJECTIONS_INVALID", "objection IDs must be non-empty and unique", "initial_review.objections"))
    open_objections = [item for item in objections if isinstance(item, Mapping) and item.get("status") != "closed"]
    if isinstance(initial, Mapping) and initial.get("status") == "REVISION_REQUIRED" and (initial.get("final_decision") != "revise" or not open_objections):
        blockers.append(_finding("INITIAL_REVIEW_DECISION_BLOCKED", "REVISION_REQUIRED inspection must retain open objections and decision=revise", "initial_review"))
    closed_by_revision = False
    revision_required_review = None
    current_reviewer_id = str((initial or {}).get("reviewer_id") or "") if isinstance(initial, Mapping) else ""
    current_target_findings = initial_target_findings
    if open_objections:
        if not isinstance(diff, Mapping):
            if not _same_subject(initial.get("subject"), subject) or initial.get("manuscript_head_sha256") != (head or {}).get("head_sha256"):
                blockers.append(_finding("INITIAL_REVIEW_STALE", "initial objections must bind the exact current manuscript head", "initial_review"))
            blockers.append(_finding("QUALITY_REVISION_REQUIRED", "open objections require an exact revision diff", "revision_diff"))
            revision_required_review = copy.deepcopy(initial)
        else:
            if (
                diff.get("contract") != "paperspine5.revision-diff"
                or diff.get("to_revision_id") != subject.revision_id
                or diff.get("to_head_sha256") != (head or {}).get("head_sha256")
                or not _is_sha256(diff.get("from_head_sha256"))
            ):
                blockers.append(_finding("REVISION_DIFF_STALE", "revision diff does not bind previous and current manuscript heads", "revision_diff"))
            blockers.extend(_validate_hashed(diff, "diff_sha256", "REVISION_DIFF_HASH_INVALID", "revision_diff.diff_sha256"))
            addressed = {str(item) for item in diff.get("addressed_objection_ids", []) if _nonempty(item)}
            if addressed != set(objection_ids):
                blockers.append(_finding("REVISION_DIFF_INCOMPLETE", "revision diff must account for every objection", "revision_diff.addressed_objection_ids"))
            changes = diff.get("changes")
            change_ids = [
                str(item.get("objection_id") or "")
                for item in changes if isinstance(item, Mapping)
            ] if isinstance(changes, list) else []
            if (
                len(change_ids) != len(objection_ids)
                or set(change_ids) != set(objection_ids)
                or any(
                    not isinstance(item, Mapping)
                    or not _nonempty(item.get("evidence_locator"))
                    or not _nonempty(item.get("change_summary"))
                    for item in (changes or [])
                )
            ):
                blockers.append(_finding("REVISION_DIFF_CHANGES_INVALID", "each objection requires an exact located revision response", "revision_diff.changes"))
            initial_subject_raw = initial.get("subject") if isinstance(initial, Mapping) else None
            try:
                initial_subject = QualitySubject.from_mapping(initial_subject_raw)
            except (QualityContractError, TypeError, ValueError):
                initial_subject = None
            if (
                initial_subject is None
                or initial_subject.task_id != subject.task_id
                or initial_subject.revision_id != str(diff.get("from_revision_id") or "")
                or initial.get("manuscript_head_sha256") != diff.get("from_head_sha256")
            ):
                blockers.append(
                    _finding(
                        "INITIAL_REVIEW_STALE",
                        "initial review must bind the exact pre-diff manuscript revision",
                        "initial_review",
                    )
                )
            artifact_changes = diff.get("artifact_changes")
            roles = [item.get("role") for item in artifact_changes if isinstance(item, Mapping)] if isinstance(artifact_changes, list) else []
            if len(roles) != 3 or set(roles) != {"source", "pdf", "word"} or any(
                not isinstance(item, Mapping)
                or initial_subject is None
                or initial_subject.input_hashes.get(str(item.get("from_artifact_id") or "")) != item.get("from_sha256")
                or subject.input_hashes.get(str(item.get("to_artifact_id") or "")) != item.get("to_sha256")
                or (head or {}).get(f"{item.get('role')}_sha256") != item.get("to_sha256")
                or item.get("from_sha256") == item.get("to_sha256")
                for item in (artifact_changes or [])
            ):
                blockers.append(_finding("REVISION_ARTIFACT_DIFF_INVALID", "revision must bind changed source/PDF/Word hashes in both exact subjects", "revision_diff.artifact_changes"))
        if isinstance(diff, Mapping):
            blockers.extend(_review_independence(re_review, producer_ids, "re_review"))
            re_review_target_findings, re_review_target_blockers = _validate_target_obligation_findings(
                re_review,
                target_authority_sha256=subject.input_hashes.get("target_authority"),
                path="re_review",
            )
            blockers.extend(re_review_target_blockers)
        if isinstance(diff, Mapping) and isinstance(re_review, Mapping):
            current_reviewer_id = str(re_review.get("reviewer_id") or "")
            current_target_findings = re_review_target_findings
            if (
                re_review.get("contract") != "paperspine5.publication-re-review"
                or re_review.get("status") not in {"PASS", "REVISION_REQUIRED"}
                or re_review.get("final_decision") not in {"pass", "revise"}
                or re_review.get("manuscript_head_sha256") != (head or {}).get("head_sha256")
                or re_review.get("revision_diff_sha256") != (diff or {}).get("diff_sha256")
                or not _same_subject(re_review.get("subject"), subject)
            ):
                blockers.append(_finding("RE_REVIEW_BLOCKED", "re-review must independently pass the exact current head and diff", "re_review"))
            blockers.extend(_validate_hashed(re_review, "review_sha256", "RE_REVIEW_HASH_INVALID", "re_review.review_sha256"))
            if re_review.get("status") == "REVISION_REQUIRED" and re_review.get("final_decision") == "revise":
                next_objections = re_review.get("objections")
                if not isinstance(next_objections, list) or not next_objections:
                    blockers.append(_finding("RE_REVIEW_OBJECTIONS_INVALID", "blocked re-review must retain its open objections", "re_review.objections"))
                else:
                    blockers.append(_finding("QUALITY_REVISION_REQUIRED", "independent re-review requires another canonical revision", "re_review"))
                    revision_required_review = _hashed(
                        {
                            **{key: copy.deepcopy(value) for key, value in re_review.items() if key not in {"review_sha256", "resolved_objection_ids", "revision_diff_sha256"}},
                            "contract": "paperspine5.publication-review",
                            "prior_review_sha256": re_review.get("review_sha256"),
                        },
                        "review_sha256",
                    )
            else:
                if re_review.get("status") != "PASS" or re_review.get("final_decision") != "pass":
                    blockers.append(_finding("RE_REVIEW_BLOCKED", "re-review status and decision disagree", "re_review"))
                resolved = {str(item) for item in re_review.get("resolved_objection_ids", []) if _nonempty(item)}
                if resolved != set(objection_ids):
                    blockers.append(_finding("RE_REVIEW_OBJECTIONS_OPEN", "re-review must close every original objection", "re_review.resolved_objection_ids"))
                closed_by_revision = resolved == set(objection_ids) and not blockers
    elif isinstance(initial, Mapping):
        if (
            not _same_subject(initial.get("subject"), subject)
            or initial.get("manuscript_head_sha256") != (head or {}).get("head_sha256")
        ):
            blockers.append(
                _finding(
                    "INITIAL_REVIEW_STALE",
                    "objection-free review must bind the current manuscript head",
                    "initial_review",
                )
            )
        if initial.get("final_decision") != "pass" or initial.get("status") != "PASS":
            blockers.append(_finding("INITIAL_REVIEW_DECISION_BLOCKED", "review without objections must explicitly pass", "initial_review.final_decision"))

    receipt = _hashed(
        {
            "contract": "paperspine5.publication-review-closure",
            "contract_version": PIPELINE_CONTRACT_VERSION,
            "subject": subject.as_dict(),
            "manuscript_head_sha256": (head or {}).get("head_sha256"),
            "initial_review_sha256": (initial or {}).get("review_sha256"),
            "revision_diff_sha256": (diff or {}).get("diff_sha256") if isinstance(diff, Mapping) else None,
            "re_review_sha256": (re_review or {}).get("review_sha256") if isinstance(re_review, Mapping) else None,
            "reviewer_id": current_reviewer_id,
            "objection_ids": objection_ids,
            "closed_by_revision": closed_by_revision,
            "target_obligation_findings": copy.deepcopy(current_target_findings),
            "final_claim_index_sha256": (bundle or {}).get("final_claim_index", {}).get("receipt_sha256") if isinstance(bundle, Mapping) else None,
            "status": "BLOCKED" if blockers else "PASS",
            "external_action_authorized": False,
        },
        "closure_sha256",
    )
    descriptor = _artifact_descriptor(
        "publication.review-closure",
        "quality.publication-review-closure",
        receipt,
        subject,
        status=receipt["status"],
    )
    return _response(
        "review_revision",
        raw_subject,
        blockers,
        next_stage="quality_revision_required" if blockers else "final_surface_qa",
        descriptors=[descriptor],
        invalidated=("final_render", "target_package", "readiness") if blockers else (),
        details={"review_closure": receipt, "revision_required_review": revision_required_review},
    )


def _override_predicate(
    predicates: list[dict[str, Any]],
    predicate_id: str,
    subject: QualitySubject,
    status: TruthStatus,
    reason: str,
    artifact_inputs: Mapping[str, str],
) -> None:
    found = next((item for item in predicates if item.get("predicate_id") == predicate_id), None)
    if found is None:
        found = {"predicate_id": predicate_id}
        predicates.append(found)
    tier_by_id = {
        "canonical_artifacts_bound": "canonical",
        "final_claim_inventory_valid": "canonical",
        "evidence_verification_valid": "canonical",
        "independent_review_valid": "independent_quality",
        "quality_objections_closed": "independent_quality",
        "final_render_bound": "final_render",
        "surface_semantics_valid": "final_render",
        "visual_accessibility_valid": "final_render",
        "target_research_valid": "target_package",
        "target_compliance_valid": "target_package",
        "target_bundle_fresh": "target_package",
        "author_items_closed": "author_close",
        "author_confirmed_current_revision": "author_close",
    }
    found.update(
        {
            "contract": "paperspine5.readiness-predicate",
            "contract_version": "1.0",
            "predicate_id": predicate_id,
            "tier": tier_by_id[predicate_id],
            "subject": subject.as_dict(),
            "status": status.value,
            "hard_blocker": True,
            "artifact_inputs": dict(sorted(artifact_inputs.items())),
            "reason": reason,
        }
    )


def _cycle_invalidation(cycle: Any) -> tuple[set[str], list[dict[str, str]]]:
    if cycle is None:
        return set(), []
    if not isinstance(cycle, Mapping):
        return set(), [_finding("PUBLICATION_CYCLE_INVALID", "cycle must be an object", "cycle")]
    kind = cycle.get("kind")
    if kind not in {"initial", "revision", "rebuttal", "transfer"}:
        return set(), [_finding("PUBLICATION_CYCLE_KIND_INVALID", "cycle kind is invalid", "cycle.kind")]
    changed = {str(item) for item in cycle.get("changed_artifact_ids", []) if _nonempty(item)}
    required_changed = {
        "revision": {"canonical_head"},
        "rebuttal": {"review_round"},
        "transfer": {"target_authority"},
    }.get(str(kind), set())
    blockers: list[dict[str, str]] = []
    if not required_changed.issubset(changed):
        blockers.append(_finding("PUBLICATION_CYCLE_CHANGESET_INCOMPLETE", f"{kind} must invalidate {sorted(required_changed)}", "cycle.changed_artifact_ids"))
    if kind == "transfer" and cycle.get("destination_confirmed") is not True:
        blockers.append(_finding("TRANSFER_DESTINATION_UNCONFIRMED", "transfer requires explicit destination confirmation", "cycle.destination_confirmed"))
    if kind == "rebuttal":
        objections = cycle.get("objections")
        if not isinstance(objections, list) or not objections or any(
            not isinstance(item, Mapping)
            or not _nonempty(item.get("objection_id"))
            or item.get("status") != "closed"
            or not _nonempty(item.get("response"))
            or not _is_sha256(item.get("evidence_sha256"))
            for item in objections
        ):
            blockers.append(_finding("REBUTTAL_OBJECTIONS_OPEN", "every rebuttal objection needs a closed evidence-bound response", "cycle.objections"))
    graph = {
        "final_claim_index": {"canonical_head"},
        "independent_review": {"canonical_head", "review_round"},
        "final_render": {"canonical_head"},
        "target_obligations": {"target_authority"},
        "target_package": {"canonical_head", "target_authority", "review_round", "final_render"},
        "readiness": {"final_claim_index", "independent_review", "final_render", "target_obligations", "target_package"},
    }
    invalidated = dependency_closure(graph, changed)
    refreshed = {str(item) for item in cycle.get("refreshed_artifact_ids", []) if _nonempty(item)}
    unrefreshed = invalidated - refreshed
    if kind != "initial" and unrefreshed:
        blockers.append(_finding("PUBLICATION_INVALIDATION_OPEN", f"downstream artifacts were not refreshed: {sorted(unrefreshed)}", "cycle.refreshed_artifact_ids"))
    return invalidated, blockers


def compile_package(request: Mapping[str, Any]) -> dict[str, Any]:
    """Compile one local package and layered, non-compensatory readiness."""

    raw_subject = request.get("subject") if isinstance(request, Mapping) else None
    subject, blockers = _validate_subject(raw_subject)
    if subject is None:
        return _response("compile_package", raw_subject, blockers, next_stage="awaiting_w4_authority")
    requested_scope = str(request.get("requested_scope") or "submission_package").strip()
    if requested_scope not in REQUESTED_SCOPES:
        blockers.append(
            _finding(
                "REQUESTED_SCOPE_INVALID",
                f"requested_scope must be one of {sorted(REQUESTED_SCOPES)}",
                "requested_scope",
            )
        )
        requested_scope = "submission_package"
    authorities, authority_blockers = _validate_authority(
        request.get("frozen_authority"), subject, request.get("trusted_artifacts")
    )
    blockers.extend(authority_blockers)
    target_hash = authorities.get("target", {}).get("sha256")
    current_raw = request.get("current_artifacts")
    current = {str(key): str(value) for key, value in current_raw.items()} if isinstance(current_raw, Mapping) else {}
    if not current or any(not _nonempty(key) or not _is_sha256(value) for key, value in current.items()):
        blockers.append(_finding("PACKAGE_CURRENT_ARTIFACTS_INVALID", "current_artifacts must be a non-empty SHA-256 map", "current_artifacts"))

    head = request.get("manuscript_head")
    review = request.get("review_closure")
    head_ok = isinstance(head, Mapping) and head.get("status") == "PASS" and _same_subject(head.get("subject"), subject) and not _validate_hashed(head, "head_sha256", "", "")
    _review_target_findings, review_target_blockers = _validate_target_obligation_findings(
        review,
        target_authority_sha256=target_hash,
        path="review_closure",
    )
    blockers.extend(review_target_blockers)
    review_ok = (
        isinstance(review, Mapping)
        and review.get("status") == "PASS"
        and _same_subject(review.get("subject"), subject)
        and not _validate_hashed(review, "closure_sha256", "", "")
        and not review_target_blockers
    )
    if not head_ok:
        blockers.append(_finding("PACKAGE_MANUSCRIPT_HEAD_INVALID", "package requires current PASS manuscript head", "manuscript_head"))
    if not review_ok:
        blockers.append(_finding("PACKAGE_REVIEW_INVALID", "package requires closed independent review", "review_closure"))

    surfaces_raw = request.get("surface_receipts")
    surfaces = surfaces_raw if isinstance(surfaces_raw, list) else []
    surface_kinds = {
        str(item.get("surface_kind"))
        for item in surfaces
        if isinstance(item, Mapping)
        and item.get("status") == "PASS"
        and str(item.get("revision_id")) == subject.revision_id
        and str(item.get("task_id")) == subject.task_id
        and item.get("external_action_authorized") is False
        and not _validate_hashed(item, "receipt_sha256", "", "")
        and isinstance(item.get("pages"), list)
        and bool(item.get("pages"))
        and item.get("page_count") == len(item.get("pages"))
    }
    surfaces_ok = surface_kinds == REQUIRED_SURFACES
    word_surface = next(
        (
            item
            for item in surfaces
            if isinstance(item, Mapping) and item.get("surface_kind") == "word"
        ),
        None,
    )
    head_word_media_sha = (
        head.get("word_figure_media_receipt_sha256")
        if isinstance(head, Mapping)
        else None
    )
    if head_word_media_sha is not None:
        current_word_media = (
            word_surface.get("figure_media")
            if isinstance(word_surface, Mapping)
            else None
        )
        if (
            not isinstance(current_word_media, Mapping)
            or current_word_media.get("receipt_sha256") != head_word_media_sha
            or _validate_hashed(current_word_media, "receipt_sha256", "", "")
        ):
            surfaces_ok = False
            blockers.append(
                _finding(
                    "PACKAGE_WORD_FIGURE_MEDIA_STALE",
                    "local delivery must retain the canonical Word visible-media receipt",
                    "surface_receipts.word.figure_media",
                )
            )
    if not surfaces_ok:
        blockers.append(_finding("PACKAGE_SURFACES_INCOMPLETE", "current page-complete PDF and Word receipts are required", "surface_receipts"))

    obligations = request.get("target_obligations")
    (
        obligation_items,
        local_obligation_ids,
        author_only_obligation_ids,
        obligation_blockers,
    ) = _validate_target_obligations(obligations, target_hash)
    blockers.extend(obligation_blockers)
    obligations_ok = not obligation_blockers
    obligations_by_id = {
        str(item.get("obligation_id") or ""): item
        for item in obligation_items
        if isinstance(item, Mapping)
    }

    mapping_raw = request.get("package_mapping")
    mapping = mapping_raw if isinstance(mapping_raw, list) else []
    mapped_items = [item for item in mapping if isinstance(item, Mapping)]
    mapped = {str(item.get("obligation_id") or ""): item for item in mapped_items}
    known_obligation_ids = local_obligation_ids | author_only_obligation_ids
    mapping_shape_ok = (
        len(mapped_items) == len(mapped)
        and set(mapped).issubset(known_obligation_ids)
        and "" not in mapped
    )
    local_evidence_ok, local_evidence_blockers = _mapping_covers(
        local_obligation_ids,
        obligations_by_id,
        mapped,
        current,
        review if isinstance(review, Mapping) else None,
        target_hash,
    )
    blockers.extend(local_evidence_blockers)
    local_mapping_ok = obligations_ok and mapping_shape_ok and local_evidence_ok
    if author_only_obligation_ids:
        author_only_evidence_ok, _author_only_evidence_blockers = _mapping_covers(
            author_only_obligation_ids,
            obligations_by_id,
            mapped,
            current,
            review if isinstance(review, Mapping) else None,
            target_hash,
            require_independent_finding=False,
        )
    else:
        author_only_evidence_ok = True
    author_only_mapping_ok = (
        obligations_ok and mapping_shape_ok and author_only_evidence_ok
    )
    if not local_mapping_ok:
        blockers.append(
            _finding(
                "TARGET_PACKAGE_MAPPING_INCOMPLETE",
                "every hard non-author target-adaptation obligation needs an exact current artifact mapping",
                "package_mapping",
            )
        )
    if not author_only_mapping_ok:
        blockers.append(
            _finding(
                "AUTHOR_ONLY_TARGET_MAPPING_INCOMPLETE",
                "unclosed typed author-only target obligations remain for submission",
                "package_mapping",
            )
        )

    author_raw = request.get("author_close")
    author = author_raw if isinstance(author_raw, list) else []
    author_ok = bool(author) and all(
        isinstance(item, Mapping)
        and _nonempty(item.get("item_id"))
        and item.get("status") is True
        and item.get("confirmed_revision_id") == subject.revision_id
        and _nonempty(item.get("confirmed_by"))
        and item.get("synthetic") is False
        and item.get("confirmation_scope") == "real_author_fact"
        and _is_sha256(item.get("user_confirmation_sha256"))
        for item in author
    )
    if not author_ok:
        blockers.append(_finding("AUTHOR_CLOSE_INCOMPLETE", "all author-only facts must be real, explicitly user-confirmed, non-synthetic, and closed for the current revision", "author_close"))

    package = request.get("package_manifest")
    package_ok = False
    if isinstance(package, Mapping):
        entries = package.get("entries")
        entries_ok = isinstance(entries, list) and bool(entries) and all(
            isinstance(item, Mapping)
            and current.get(str(item.get("artifact_id") or "")) == item.get("sha256")
            and item.get("revision_id") == subject.revision_id
            for item in entries
        )
        package_ok = (
            package.get("contract") == "paperspine5.target-package-manifest"
            and package.get("status") == "PASS"
            and _same_subject(package.get("subject"), subject)
            and package.get("target_authority_sha256") == target_hash
            and entries_ok
            and not _validate_hashed(package, "manifest_sha256", "", "")
            and _nonempty(package.get("archive_artifact_id"))
            and _is_sha256(package.get("archive_sha256"))
            and current.get(str(package.get("archive_artifact_id")))
            == package.get("archive_sha256")
        )
    if not package_ok:
        blockers.append(_finding("TARGET_PACKAGE_MANIFEST_INVALID", "package manifest must bind current revision, target, and every entry", "package_manifest"))

    invalidated, cycle_blockers = _cycle_invalidation(request.get("cycle"))
    blockers.extend(cycle_blockers)
    raw_predicates = request.get("predicates")
    predicates = [copy.deepcopy(dict(item)) for item in raw_predicates if isinstance(item, Mapping)] if isinstance(raw_predicates, list) else []
    predicate_ids = {str(item.get("predicate_id")) for item in predicates}
    if predicate_ids != REQUIRED_PREDICATE_IDS:
        blockers.append(_finding("READINESS_PREDICATE_SET_INCOMPLETE", "exactly all fixed readiness predicates are required", "predicates"))
    structural_inputs = {
        key: value
        for key, value in current.items()
        if key in {"canonical_head", "final_claim_index", "evidence_registry", "review_closure", "surface_pdf", "surface_word", "target_authority", "target_obligations", "target_package", "author_close"}
    }
    if not structural_inputs:
        structural_inputs = current
    overrides = {
        "canonical_artifacts_bound": head_ok,
        "final_claim_inventory_valid": review_ok,
        "independent_review_valid": review_ok,
        "quality_objections_closed": review_ok,
        "final_render_bound": surfaces_ok,
        "surface_semantics_valid": surfaces_ok,
        "visual_accessibility_valid": surfaces_ok,
        "target_research_valid": bool(authorities.get("target")),
        "target_compliance_valid": obligations_ok and local_mapping_ok,
        "target_bundle_fresh": package_ok and not cycle_blockers,
        "author_items_closed": author_ok,
        "author_confirmed_current_revision": author_ok,
    }
    for predicate_id, ok in overrides.items():
        if not ok:
            _override_predicate(
                predicates,
                predicate_id,
                subject,
                TruthStatus.FALSE,
                "publication pipeline structural authority check failed",
                structural_inputs,
            )
    pipeline_blockers = [dict(item) for item in blockers]
    predicate_statuses = {
        str(item.get("predicate_id")): str(item.get("status"))
        for item in predicates
        if isinstance(item, Mapping)
    }
    submission_would_block = bool(pipeline_blockers) or any(
        predicate_statuses.get(predicate_id) != TruthStatus.TRUE.value
        for predicate_id in REQUIRED_PREDICATE_IDS
    )
    if submission_would_block:
        pipeline_blockers.append(
            _finding(
                "NON_COMPENSATORY_READINESS_BLOCKED",
                "submission readiness requires all five hard readiness tiers to be true and current",
                "readiness.submission_package",
            )
        )
    layer_blockers = {
        "manuscript": [
            item
            for item in pipeline_blockers
            if item.get("code") not in LOCAL_DELIVERY_ONLY_BLOCKER_CODES
        ],
        "local_delivery": [
            item
            for item in pipeline_blockers
            if item.get("code") not in SUBMISSION_ONLY_BLOCKER_CODES
        ],
        "submission_package": pipeline_blockers,
        "external_action": pipeline_blockers,
    }
    try:
        verdict = ReadinessCompiler.compile(
            subject,
            predicates,
            current,
            obligation_manifest=request.get("readiness_obligation_manifest"),
            dependency_graph=request.get("dependency_graph") if isinstance(request.get("dependency_graph"), Mapping) else {},
            changed_artifact_ids=request.get("changed_artifact_ids", []),
            requested_scope=requested_scope,
            blockers_by_layer=layer_blockers,
        )
    except (QualityContractError, TypeError, ValueError) as exc:
        verdict = {}
        blockers.append(_finding("READINESS_COMPILATION_FAILED", str(exc), "predicates"))
    scoped_blockers = (
        list(verdict.get("blockers_by_layer", {}).get(requested_scope, []))
        if isinstance(verdict, Mapping)
        else list(blockers)
    )
    if not verdict.get("is_complete_for_requested_scope") and not scoped_blockers:
        scoped_blockers.append(
            _finding(
                "REQUESTED_SCOPE_READINESS_BLOCKED",
                "the requested manuscript or delivery scope is not complete",
                f"readiness.{requested_scope}",
            )
        )

    descriptors: list[dict[str, Any]] = []
    for surface in surfaces:
        if isinstance(surface, Mapping) and surface.get("surface_kind") in REQUIRED_SURFACES:
            descriptors.append(
                _artifact_descriptor(
                    f"surface_{surface['surface_kind']}",
                    "publication.surface-receipt",
                    surface,
                    subject,
                    status="PASS" if surfaces_ok else "BLOCKED",
                )
            )
    if isinstance(obligations, Mapping):
        descriptors.append(
            _artifact_descriptor(
                "target_obligations",
                "authority.target-obligation-ledger",
                obligations,
                subject,
                status="PASS" if obligations_ok else "BLOCKED",
            )
        )
    if author:
        author_receipt = {
            "contract": "paperspine5.author-close-receipt",
            "contract_version": "1.0",
            "subject": subject.as_dict(),
            "items": copy.deepcopy(author),
            "author_close_sha256": canonical_sha256(author),
            "status": "PASS" if author_ok else "BLOCKED",
            "external_action_authorized": False,
        }
        descriptors.append(
            _artifact_descriptor(
                "author_close",
                "authority.author-close-receipt",
                author_receipt,
                subject,
                status="PASS" if author_ok else "BLOCKED",
            )
        )
    if isinstance(package, Mapping):
        descriptors.append(_artifact_descriptor("publication.target-package", "publication.target-package-manifest", package, subject, status="PASS" if package_ok else "BLOCKED"))
    if verdict:
        descriptors.append(_artifact_descriptor("publication.readiness", "quality.readiness-verdict", verdict, subject, status="PASS"))
    return _response(
        "compile_package",
        raw_subject,
        scoped_blockers,
        next_stage="author_or_package_remediation" if scoped_blockers else "target_package_ready",
        descriptors=descriptors,
        invalidated=invalidated,
        details={
            "readiness_verdict": verdict,
            "requested_scope": requested_scope,
            "manuscript_ready": bool(verdict.get("manuscript_ready")),
            "delivery_ready": bool(verdict.get("delivery_ready")),
            "submission_ready": bool(verdict.get("submission_ready")),
            "is_complete_for_requested_scope": bool(
                verdict.get("is_complete_for_requested_scope")
            ),
            "target_package_ready": bool(verdict.get("delivery_ready")),
            "higher_layer_blockers": {
                layer: copy.deepcopy(items)
                for layer, items in verdict.get("blockers_by_layer", {}).items()
                if layer != requested_scope and items
            },
            "external_action_authorized": False,
        },
    )


class PublicationPipelineService:
    """Small stateless facade for Runner-owned W5--W6 CAS commands."""

    evaluate_figure_intent = staticmethod(evaluate_figure_intent)
    bind_canonical = staticmethod(bind_canonical)
    review_revision = staticmethod(review_revision)
    compile_package = staticmethod(compile_package)
