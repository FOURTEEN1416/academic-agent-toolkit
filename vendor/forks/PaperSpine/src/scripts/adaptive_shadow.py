#!/usr/bin/env python3
"""Deterministic, domain-neutral adaptive audit shadow for one claim surface.

This module deliberately cannot grant manuscript, delivery, submission, or
external-action readiness.  It validates receipts and a closed obligation IR,
then emits only ``CLAIM_SURFACE_AUDITED`` or ``BLOCKED``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REQUEST_CONTRACT = "paperspine.adaptive-shadow.request"
RESULT_CONTRACT = "paperspine.adaptive-shadow.result"
INTERFACE_VERSION = "0.1-shadow"
HARD_FORCES = {"mandatory", "prohibited"}
NORMATIVE_FORCES = HARD_FORCES | {"advisory", "quality_hypothesis"}
PREDICATE_OPERATORS = {"exists", "absent", "truthy", "equals", "in_set"}
HARD_VERIFICATION_KINDS = {
    "machine_parsed_official_structure",
    "independent_verifier_receipt",
}
HARD_AUTHORITY_CLASSES = {"official", "qualified_human_or_institution", "user_authority"}
AUTHORITY_CLASSES = HARD_AUTHORITY_CLASSES | {"peer_reviewed_primary", "scholarly_exemplar"}
INDEPENDENT_REVIEW_KINDS = {"independent_model_or_provider", "qualified_human"}
CORE_FIGURE_ROLES = {"hero", "mechanism", "model", "core"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MISSING = object()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _is_nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value.lower()))


def _unknown_fields(value: dict[str, Any], allowed: set[str], label: str) -> list[str]:
    unknown = sorted(set(value) - allowed)
    return [f"{label} contains unknown fields: {unknown}"] if unknown else []


def _valid_timestamp(value: object) -> bool:
    if not _is_nonempty(value):
        return False
    candidate = str(value).strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _resolve_project_file(project_root: Path, raw_path: object) -> Path | None:
    if not _is_nonempty(raw_path):
        return None
    candidate = Path(str(raw_path))
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.resolve()
    return resolved if _inside(project_root, resolved) else None


def _lookup(data: object, dotted_path: str) -> object:
    current = data
    for token in dotted_path.split("."):
        if isinstance(current, dict) and token in current:
            current = current[token]
        else:
            return MISSING
    return current


def _predicate_satisfied(predicate: dict[str, Any], facts: dict[str, Any]) -> bool:
    operator = predicate.get("operator")
    value = _lookup(facts, str(predicate.get("path") or ""))
    if operator == "exists":
        return value is not MISSING
    if operator == "absent":
        return value is MISSING
    if operator == "truthy":
        return value is not MISSING and bool(value)
    if operator == "equals":
        return value is not MISSING and value == predicate.get("value")
    if operator == "in_set":
        choices = predicate.get("value")
        return isinstance(choices, list) and value is not MISSING and value in choices
    return False


def _coverage_findings(
    coverage: object,
    source_ids: set[str],
) -> list[str]:
    findings: list[str] = []
    if not isinstance(coverage, dict):
        return ["coverage_receipt must be an object."]
    findings.extend(
        _unknown_fields(coverage, {"target_policy", "direction_search"}, "coverage_receipt")
    )
    for lane in ("target_policy", "direction_search"):
        item = coverage.get(lane)
        label = f"coverage_receipt.{lane}"
        if not isinstance(item, dict):
            findings.append(f"{label} is required.")
            continue
        findings.extend(
            _unknown_fields(
                item,
                {
                    "queries",
                    "source_classes",
                    "included_source_ids",
                    "stopping_reason",
                    "residual_risk",
                    "coverage_challenger",
                    "direct_competitors_considered",
                    "omission_challenge",
                },
                label,
            )
        )
        for key in ("queries", "source_classes", "included_source_ids"):
            value = item.get(key)
            if not isinstance(value, list) or not value or not all(_is_nonempty(v) for v in value):
                findings.append(f"{label}.{key} must be a non-empty string list.")
        included = item.get("included_source_ids")
        if isinstance(included, list):
            unknown = sorted(str(value) for value in included if str(value) not in source_ids)
            if unknown:
                findings.append(f"{label}.included_source_ids contains unknown sources: {unknown}")
        if item.get("stopping_reason") not in {
            "frontier_saturated",
            "authoritative_sources_exhausted",
            "budget_exhausted",
            "user_bounded",
        }:
            findings.append(f"{label}.stopping_reason is invalid.")
        if not _is_nonempty(item.get("residual_risk")):
            findings.append(f"{label}.residual_risk must be explicit.")
        challenger = item.get("coverage_challenger")
        if not isinstance(challenger, dict):
            findings.append(f"{label}.coverage_challenger is required.")
        else:
            findings.extend(
                _unknown_fields(
                    challenger,
                    {
                        "independence_kind",
                        "producer_id",
                        "challenger_id",
                        "outcome",
                        "unresolved_gaps",
                    },
                    f"{label}.coverage_challenger",
                )
            )
            kind = challenger.get("independence_kind")
            if kind not in INDEPENDENT_REVIEW_KINDS | {"deterministic_frontier_check"}:
                findings.append(f"{label}.coverage_challenger.independence_kind is invalid.")
            producer = challenger.get("producer_id")
            challenger_id = challenger.get("challenger_id")
            if not _is_nonempty(producer) or not _is_nonempty(challenger_id):
                findings.append(
                    f"{label}.coverage_challenger requires producer_id and challenger_id."
                )
            elif kind != "deterministic_frontier_check" and str(producer) == str(challenger_id):
                findings.append(f"{label}.coverage_challenger is not independent of the producer.")
            if challenger.get("outcome") != "PASS":
                findings.append(f"{label}.coverage_challenger.outcome must be PASS.")
            gaps = challenger.get("unresolved_gaps")
            if not isinstance(gaps, list) or gaps:
                findings.append(
                    f"{label}.coverage_challenger.unresolved_gaps must be an empty list."
                )
        if lane == "direction_search":
            competitors = item.get("direct_competitors_considered")
            if not isinstance(competitors, list) or not competitors or not all(
                _is_nonempty(value) for value in competitors
            ):
                findings.append(
                    f"{label}.direct_competitors_considered must be a non-empty string list."
                )
            challenge = item.get("omission_challenge")
            if not isinstance(challenge, dict):
                findings.append(f"{label}.omission_challenge is required.")
            else:
                findings.extend(
                    _unknown_fields(
                        challenge,
                        {
                            "independence_kind",
                            "producer_id",
                            "challenger_id",
                            "outcome",
                            "unresolved_omissions",
                        },
                        f"{label}.omission_challenge",
                    )
                )
                producer = challenge.get("producer_id")
                challenger_id = challenge.get("challenger_id")
                if challenge.get("independence_kind") not in INDEPENDENT_REVIEW_KINDS:
                    findings.append(f"{label}.omission_challenge.independence_kind is invalid.")
                if not _is_nonempty(producer) or not _is_nonempty(challenger_id):
                    findings.append(
                        f"{label}.omission_challenge requires producer_id and challenger_id."
                    )
                elif str(producer) == str(challenger_id):
                    findings.append(f"{label}.omission_challenge is not independent of the producer.")
                if challenge.get("outcome") != "PASS":
                    findings.append(f"{label}.omission_challenge.outcome must be PASS.")
                omitted = challenge.get("unresolved_omissions")
                if not isinstance(omitted, list) or omitted:
                    findings.append(
                        f"{label}.omission_challenge.unresolved_omissions must be an empty list."
                    )
    return findings


def _source_findings(receipts: object) -> tuple[list[str], dict[str, dict[str, Any]]]:
    findings: list[str] = []
    indexed: dict[str, dict[str, Any]] = {}
    if not isinstance(receipts, list) or not receipts:
        return ["source_receipts must contain at least one receipt."], indexed
    for index, receipt in enumerate(receipts):
        label = f"source_receipts[{index}]"
        if not isinstance(receipt, dict):
            findings.append(f"{label} must be an object.")
            continue
        findings.extend(
            _unknown_fields(
                receipt,
                {
                    "source_id",
                    "authority_class",
                    "canonical_identity",
                    "locator",
                    "retrieved_at",
                    "as_of",
                    "content_sha256",
                    "extraction_verification",
                },
                label,
            )
        )
        source_id = receipt.get("source_id")
        if not _is_nonempty(source_id) or not SAFE_ID.fullmatch(str(source_id)):
            findings.append(f"{label}.source_id is invalid.")
            continue
        source_id = str(source_id)
        if source_id in indexed:
            findings.append(f"Duplicate source_id: {source_id}")
            continue
        indexed[source_id] = receipt
        for field in ("authority_class", "canonical_identity", "locator"):
            if not _is_nonempty(receipt.get(field)):
                findings.append(f"{label}.{field} is required.")
        if receipt.get("authority_class") not in AUTHORITY_CLASSES:
            findings.append(f"{label}.authority_class is outside the closed authority vocabulary.")
        for field in ("retrieved_at", "as_of"):
            if not _valid_timestamp(receipt.get(field)):
                findings.append(f"{label}.{field} must be an ISO date or datetime.")
        if not _is_hex64(receipt.get("content_sha256")):
            findings.append(f"{label}.content_sha256 must be 64 lowercase hex characters.")
        verification = receipt.get("extraction_verification")
        if not isinstance(verification, dict) or not _is_nonempty(verification.get("kind")):
            findings.append(f"{label}.extraction_verification.kind is required.")
        else:
            findings.extend(
                _unknown_fields(
                    verification,
                    {"kind", "producer_id", "verifier_id", "receipt_sha256"},
                    f"{label}.extraction_verification",
                )
            )
            producer_id = verification.get("producer_id")
            verifier_id = verification.get("verifier_id")
            if not _is_nonempty(producer_id) or not _is_nonempty(verifier_id):
                findings.append(
                    f"{label}.extraction_verification requires producer_id and verifier_id."
                )
            elif (
                verification.get("kind") == "independent_verifier_receipt"
                and str(producer_id).strip() == str(verifier_id).strip()
            ):
                findings.append(f"{label}.extraction verifier is not independent of the producer.")
            if verification.get("kind") not in HARD_VERIFICATION_KINDS | {
                "same_model_context_separation"
            }:
                findings.append(f"{label}.extraction_verification.kind is invalid.")
            receipt_hash = verification.get("receipt_sha256")
            if receipt_hash is not None and not _is_hex64(receipt_hash):
                findings.append(
                    f"{label}.extraction_verification.receipt_sha256 must be 64 hex characters."
                )
    return findings, indexed


def _obligation_findings(
    obligations: object,
    sources: dict[str, dict[str, Any]],
    facts: dict[str, Any],
) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    advisory: list[str] = []
    if not isinstance(obligations, list) or not obligations:
        return ["obligations must contain at least one closed-IR obligation."], advisory
    seen: set[str] = set()
    for index, obligation in enumerate(obligations):
        label = f"obligations[{index}]"
        if not isinstance(obligation, dict):
            findings.append(f"{label} must be an object.")
            continue
        findings.extend(
            _unknown_fields(
                obligation,
                {"obligation_id", "source_id", "normative_force", "predicate"},
                label,
            )
        )
        obligation_id = str(obligation.get("obligation_id") or "")
        if not SAFE_ID.fullmatch(obligation_id):
            findings.append(f"{label}.obligation_id is invalid.")
        elif obligation_id in seen:
            findings.append(f"Duplicate obligation_id: {obligation_id}")
        seen.add(obligation_id)
        source_id = str(obligation.get("source_id") or "")
        source = sources.get(source_id)
        if source is None:
            findings.append(f"{label}.source_id is unknown: {source_id or '<missing>'}")
        force = obligation.get("normative_force")
        if force not in NORMATIVE_FORCES:
            findings.append(f"{label}.normative_force is invalid.")
            continue
        predicate = obligation.get("predicate")
        if not isinstance(predicate, dict):
            findings.append(f"{label}.predicate must be an object.")
            continue
        findings.extend(
            _unknown_fields(predicate, {"operator", "path", "value"}, f"{label}.predicate")
        )
        operator = predicate.get("operator")
        if operator not in PREDICATE_OPERATORS:
            findings.append(f"{label}.predicate.operator is outside closed Obligation IR v0.")
            continue
        if not _is_nonempty(predicate.get("path")):
            findings.append(f"{label}.predicate.path is required.")
            continue
        if force in HARD_FORCES and source is not None:
            verification = source.get("extraction_verification")
            kind = verification.get("kind") if isinstance(verification, dict) else None
            if kind not in HARD_VERIFICATION_KINDS:
                findings.append(
                    f"{label} is hard but its source lacks an independent/official extraction receipt."
                )
            if source.get("authority_class") not in HARD_AUTHORITY_CLASSES:
                findings.append(
                    f"{label} is hard but its source authority cannot create a mandatory/prohibited rule."
                )
            if kind == "machine_parsed_official_structure" and source.get("authority_class") != "official":
                findings.append(
                    f"{label} claims official machine parsing but the source authority is not official."
                )
        satisfied = _predicate_satisfied(predicate, facts)
        violated = not satisfied if force != "prohibited" else satisfied
        if violated:
            message = f"{label} predicate is not satisfied ({operator} {predicate.get('path')})."
            if force in HARD_FORCES:
                findings.append(message)
            else:
                advisory.append(message)
    return findings, advisory


def _surface_findings(
    surface: object,
    project_root: Path,
    source_ids: set[str],
) -> tuple[list[str], str | None, dict[str, Any]]:
    findings: list[str] = []
    if not isinstance(surface, dict):
        return ["claim_surface must be an object."], None, {}
    findings.extend(
        _unknown_fields(
            surface,
            {"claim_id", "surface_id", "artifact", "support_source_ids", "facts"},
            "claim_surface",
        )
    )
    for field in ("claim_id", "surface_id"):
        value = str(surface.get(field) or "")
        if not SAFE_ID.fullmatch(value):
            findings.append(f"claim_surface.{field} is invalid.")
    artifact = surface.get("artifact")
    current_hash: str | None = None
    if not isinstance(artifact, dict):
        findings.append("claim_surface.artifact must be an object.")
    else:
        findings.extend(_unknown_fields(artifact, {"path", "sha256"}, "claim_surface.artifact"))
        artifact_path = _resolve_project_file(project_root, artifact.get("path"))
        if artifact_path is None:
            findings.append("claim_surface.artifact.path must remain inside project_root.")
        elif not artifact_path.is_file():
            findings.append(f"claim_surface.artifact is missing: {artifact_path}")
        else:
            current_hash = sha256_file(artifact_path)
            if str(artifact.get("sha256") or "").lower() != current_hash:
                findings.append("claim_surface.artifact.sha256 is stale or incorrect.")
    support_ids = surface.get("support_source_ids")
    if not isinstance(support_ids, list) or not support_ids:
        findings.append("claim_surface.support_source_ids must be non-empty.")
    else:
        unknown = sorted(str(value) for value in support_ids if str(value) not in source_ids)
        if unknown:
            findings.append(f"claim_surface.support_source_ids contains unknown sources: {unknown}")
    facts = surface.get("facts")
    if not isinstance(facts, dict):
        findings.append("claim_surface.facts must be an object.")
        facts = {}
    return findings, current_hash, facts


def _review_findings(review: object, current_hash: str | None) -> list[str]:
    if not isinstance(review, dict):
        return ["independent_review_receipt must be an object."]
    findings: list[str] = []
    findings.extend(
        _unknown_fields(
            review,
            {
                "review_mode",
                "independence_kind",
                "producer_id",
                "reviewer_id",
                "input_sha256",
                "outcome",
                "major_restructure_required",
                "unresolved_blockers",
            },
            "independent_review_receipt",
        )
    )
    if review.get("review_mode") != "zero_context_primary_surface":
        findings.append(
            "independent_review_receipt.review_mode must be zero_context_primary_surface."
        )
    if review.get("independence_kind") not in INDEPENDENT_REVIEW_KINDS:
        findings.append(
            "independent_review_receipt.independence_kind must be independent_model_or_provider "
            "or qualified_human."
        )
    if not _is_nonempty(review.get("reviewer_id")):
        findings.append("independent_review_receipt.reviewer_id is required.")
    if not _is_nonempty(review.get("producer_id")):
        findings.append("independent_review_receipt.producer_id is required.")
    elif str(review.get("producer_id")).strip() == str(review.get("reviewer_id") or "").strip():
        findings.append("independent_review_receipt reviewer is not independent of the producer.")
    if current_hash is None or str(review.get("input_sha256") or "").lower() != current_hash:
        findings.append("independent_review_receipt.input_sha256 must match the current claim surface.")
    if review.get("outcome") != "PASS":
        findings.append("independent_review_receipt.outcome must be PASS.")
    if review.get("major_restructure_required") is not False:
        findings.append("Independent review still requires major restructuring.")
    blockers = review.get("unresolved_blockers")
    if not isinstance(blockers, list) or blockers:
        findings.append("independent_review_receipt.unresolved_blockers must be an empty list.")
    return findings


def _retention_findings(retention: object) -> list[str]:
    if not isinstance(retention, dict):
        return ["retention_receipt must be an object."]
    findings: list[str] = []
    findings.extend(
        _unknown_fields(
            retention,
            {"expected_atom_ids", "retained_atom_ids", "omitted_atoms"},
            "retention_receipt",
        )
    )
    expected = retention.get("expected_atom_ids")
    retained = retention.get("retained_atom_ids")
    omitted = retention.get("omitted_atoms")
    if not isinstance(expected, list) or not expected or not all(_is_nonempty(v) for v in expected):
        findings.append("retention_receipt.expected_atom_ids must be a non-empty string list.")
        expected_set: set[str] = set()
    else:
        expected_set = {str(value) for value in expected}
        if len(expected_set) != len(expected):
            findings.append("retention_receipt.expected_atom_ids contains duplicates.")
    if not isinstance(retained, list) or not all(_is_nonempty(v) for v in retained):
        findings.append("retention_receipt.retained_atom_ids must be a string list.")
        retained_set: set[str] = set()
    else:
        retained_set = {str(value) for value in retained}
        if len(retained_set) != len(retained):
            findings.append("retention_receipt.retained_atom_ids contains duplicates.")
    omitted_set: set[str] = set()
    if not isinstance(omitted, list):
        findings.append("retention_receipt.omitted_atoms must be a list.")
    else:
        for index, item in enumerate(omitted):
            label = f"retention_receipt.omitted_atoms[{index}]"
            if not isinstance(item, dict):
                findings.append(f"{label} must be an object.")
                continue
            findings.extend(
                _unknown_fields(
                    item,
                    {"atom_id", "reason", "decision_owner"},
                    label,
                )
            )
            atom_id = str(item.get("atom_id") or "")
            if not atom_id:
                findings.append(f"{label}.atom_id is required.")
            elif atom_id in omitted_set:
                findings.append(f"Duplicate omitted atom_id: {atom_id}")
            omitted_set.add(atom_id)
            if not _is_nonempty(item.get("reason")) or not _is_nonempty(item.get("decision_owner")):
                findings.append(f"{label} requires reason and decision_owner.")
    overlap = retained_set & omitted_set
    if overlap:
        findings.append(f"Retention atoms cannot be both retained and omitted: {sorted(overlap)}")
    missing = expected_set - retained_set - omitted_set
    extra = (retained_set | omitted_set) - expected_set
    if missing:
        findings.append(f"Retention receipt has unexplained omissions: {sorted(missing)}")
    if extra:
        findings.append(f"Retention receipt references unexpected atoms: {sorted(extra)}")
    return findings


def _asset_inventory_findings(inventory: object, project_root: Path) -> tuple[list[str], set[str]]:
    if not isinstance(inventory, dict):
        return ["asset_inventory must be an object."], set()
    findings: list[str] = []
    findings.extend(
        _unknown_fields(
            inventory,
            {
                "applicable",
                "not_applicable_reason",
                "candidates",
                "selected_asset_ids",
                "explicit_user_selection_id",
            },
            "asset_inventory",
        )
    )
    if inventory.get("applicable") is False:
        if not _is_nonempty(inventory.get("not_applicable_reason")):
            findings.append("asset_inventory.not_applicable_reason is required when not applicable.")
        return findings, set()
    if inventory.get("applicable") is not True:
        return ["asset_inventory.applicable must be true or false."], set()
    candidates = inventory.get("candidates")
    selected = inventory.get("selected_asset_ids")
    if not isinstance(candidates, list) or not candidates:
        return ["asset_inventory.candidates must be non-empty when applicable."], set()
    selected_ids = {str(value) for value in selected} if isinstance(selected, list) else set()
    if not selected_ids:
        findings.append("asset_inventory.selected_asset_ids must be non-empty when applicable.")
    records: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(candidates):
        label = f"asset_inventory.candidates[{index}]"
        if not isinstance(candidate, dict):
            findings.append(f"{label} must be an object.")
            continue
        findings.extend(
            _unknown_fields(
                candidate,
                {"asset_id", "path", "sha256", "mtime_ns", "identity_match"},
                label,
            )
        )
        asset_id = str(candidate.get("asset_id") or "")
        if not SAFE_ID.fullmatch(asset_id):
            findings.append(f"{label}.asset_id is invalid.")
            continue
        if asset_id in records:
            findings.append(f"Duplicate asset_id: {asset_id}")
            continue
        records[asset_id] = candidate
        path = _resolve_project_file(project_root, candidate.get("path"))
        if path is None or not path.is_file():
            findings.append(f"{label}.path is missing or outside project_root.")
            continue
        stat = path.stat()
        mtime_ns = candidate.get("mtime_ns")
        if not isinstance(mtime_ns, int) or isinstance(mtime_ns, bool):
            findings.append(f"{label}.mtime_ns must be an integer.")
        elif mtime_ns != stat.st_mtime_ns:
            findings.append(f"{label}.mtime_ns is stale or incorrect.")
        if str(candidate.get("sha256") or "").lower() != sha256_file(path):
            findings.append(f"{label}.sha256 is stale or incorrect.")
        if not isinstance(candidate.get("identity_match"), bool):
            findings.append(f"{label}.identity_match must be boolean.")
    unknown_selected = selected_ids - set(records)
    if unknown_selected:
        findings.append(f"asset_inventory selected unknown assets: {sorted(unknown_selected)}")
    # Modification time proves which file was inventoried, not scientific fit.
    # Selection may retain an older candidate; every selected asset must still
    # match the scientific identity and the current hash/timestamp above.
    for asset_id in selected_ids & set(records):
        if records[asset_id].get("identity_match") is not True:
            findings.append(f"asset_inventory selected asset {asset_id} fails the scientific identity gate.")
    explicit = str(inventory.get("explicit_user_selection_id") or "")
    if explicit:
        if explicit not in selected_ids:
            findings.append("asset_inventory explicit_user_selection_id must be selected.")
        explicit_candidate = records.get(explicit)
        if explicit_candidate is not None and explicit_candidate.get("identity_match") is not True:
            findings.append(
                "asset_inventory explicit user selection cannot override the scientific identity gate."
            )
    return findings, selected_ids


def _quality_revision_findings(receipt: object) -> list[str]:
    if not isinstance(receipt, dict):
        return ["quality_revision_receipt must be an object."]
    rounds = receipt.get("automatic_rounds")
    findings: list[str] = []
    findings.extend(
        _unknown_fields(
            receipt,
            {"automatic_rounds", "stop_reason", "changes"},
            "quality_revision_receipt",
        )
    )
    if not isinstance(rounds, int) or isinstance(rounds, bool) or not 0 <= rounds <= 1:
        findings.append("quality_revision_receipt.automatic_rounds must be 0 or 1 in alpha.1.")
    if not _is_nonempty(receipt.get("stop_reason")):
        findings.append("quality_revision_receipt.stop_reason is required.")
    changes = receipt.get("changes")
    if not isinstance(changes, list):
        findings.append("quality_revision_receipt.changes must be a list.")
    elif rounds == 1 and not changes:
        findings.append("quality_revision_receipt.changes must record the automatic revision.")
    elif rounds == 0 and changes:
        findings.append("quality_revision_receipt.changes must be empty when no automatic round ran.")
    return findings


def _legacy_findings(receipt: object) -> tuple[list[str], str]:
    if not isinstance(receipt, dict):
        return ["legacy_receipt must be an object for v1/v2 dual-read."], "MISSING"
    findings: list[str] = []
    findings.extend(
        _unknown_fields(
            receipt,
            {"interface", "status", "artifact_sha256"},
            "legacy_receipt",
        )
    )
    if receipt.get("interface") != "v1":
        findings.append("legacy_receipt.interface must be v1.")
    status = str(receipt.get("status") or "UNKNOWN").upper()
    if status not in {"PASS", "FAIL", "BLOCKED", "UNKNOWN", "NOT_RUN"}:
        findings.append("legacy_receipt.status is invalid.")
    if status in {"FAIL", "BLOCKED"}:
        findings.append(f"Legacy {status} is preserved and cannot be overridden by the v2 shadow.")
    artifact_hash = receipt.get("artifact_sha256")
    if artifact_hash is not None and not _is_hex64(artifact_hash):
        findings.append("legacy_receipt.artifact_sha256 must be 64 hex characters when supplied.")
    return findings, status


def _figure_findings(figures: object, project_root: Path, source_ids: set[str]) -> list[str]:
    if figures is None:
        return []
    if not isinstance(figures, list):
        return ["figures must be a list when supplied."]
    findings: list[str] = []
    for index, figure in enumerate(figures):
        label = f"figures[{index}]"
        if not isinstance(figure, dict):
            findings.append(f"{label} must be an object.")
            continue
        findings.extend(
            _unknown_fields(
                figure,
                {"figure_id", "role", "decision", "artifact", "competitive_delta"},
                label,
            )
        )
        role = str(figure.get("role") or "").strip().lower()
        if not _is_nonempty(figure.get("figure_id")):
            findings.append(f"{label}.figure_id is required.")
        if not role:
            findings.append(f"{label}.role is required.")
        decision = figure.get("decision")
        if decision not in {"keep", "redesign", "replace", "demote"}:
            findings.append(f"{label}.decision is invalid.")
        artifact = figure.get("artifact")
        if isinstance(artifact, dict):
            findings.extend(_unknown_fields(artifact, {"path", "sha256"}, f"{label}.artifact"))
            path = _resolve_project_file(project_root, artifact.get("path"))
            if path is None or not path.is_file():
                findings.append(f"{label}.artifact is missing or outside project_root.")
            elif str(artifact.get("sha256") or "").lower() != sha256_file(path):
                findings.append(f"{label}.artifact.sha256 is stale or incorrect.")
        else:
            findings.append(f"{label}.artifact must be an object.")
        # A figure's role does not itself make a competitive superiority claim.
        # When a delta is supplied, its baseline and evidence must be meaningful
        # for any role; absent deltas do not invent a redesign obligation.
        if "competitive_delta" in figure:
            delta = figure.get("competitive_delta")
            if not isinstance(delta, dict):
                findings.append(f"{label}.competitive_delta must be an object when supplied.")
                continue
            findings.extend(
                _unknown_fields(
                    delta,
                    {"baseline", "delta", "evidence_source_ids"},
                    f"{label}.competitive_delta",
                )
            )
            for field in ("baseline", "delta"):
                if not _is_nonempty(delta.get(field)):
                    findings.append(f"{label}.competitive_delta.{field} is required.")
            evidence = delta.get("evidence_source_ids")
            if not isinstance(evidence, list) or not evidence:
                findings.append(f"{label}.competitive_delta.evidence_source_ids must be non-empty.")
            elif any(str(value) not in source_ids for value in evidence):
                findings.append(f"{label}.competitive_delta references an unknown source.")
    return findings


def audit_request(request: object, project_root: Path) -> dict[str, Any]:
    """Validate one request without mutating the project."""
    base_findings: list[str] = []
    advisory: list[str] = []
    if not isinstance(request, dict):
        request = {}
        base_findings.append("Request must be a JSON object.")
    base_findings.extend(
        _unknown_fields(
            request,
            {
                "contract",
                "interface_version",
                "mode",
                "revision_id",
                "context",
                "source_receipts",
                "coverage_receipt",
                "obligations",
                "claim_surface",
                "independent_review_receipt",
                "retention_receipt",
                "asset_inventory",
                "quality_revision_receipt",
                "legacy_receipt",
                "figures",
            },
            "request",
        )
    )
    if request.get("contract") != REQUEST_CONTRACT:
        base_findings.append(f"contract must be {REQUEST_CONTRACT}.")
    if request.get("interface_version") != INTERFACE_VERSION:
        base_findings.append(f"interface_version must be {INTERFACE_VERSION}.")
    if request.get("mode") != "shadow":
        base_findings.append("mode must be shadow.")
    revision_id = str(request.get("revision_id") or "")
    if not SAFE_ID.fullmatch(revision_id):
        base_findings.append("revision_id is invalid.")

    context = request.get("context")
    if not isinstance(context, dict):
        base_findings.append("context must be an object.")
    else:
        base_findings.extend(
            _unknown_fields(
                context,
                {
                    "context_id",
                    "object_kind",
                    "destination_channel",
                    "as_of",
                    "venue",
                    "year",
                    "track",
                    "article_type",
                    "stage_id",
                },
                "context",
            )
        )
        for field in ("context_id", "object_kind", "destination_channel"):
            if not _is_nonempty(context.get(field)):
                base_findings.append(f"context.{field} is required.")
        if not _valid_timestamp(context.get("as_of")):
            base_findings.append("context.as_of must be an ISO date or datetime.")

    source_findings, sources = _source_findings(request.get("source_receipts"))
    coverage_findings = _coverage_findings(request.get("coverage_receipt"), set(sources))
    surface_findings, current_hash, facts = _surface_findings(
        request.get("claim_surface"), project_root, set(sources)
    )
    obligation_findings, obligation_advisory = _obligation_findings(
        request.get("obligations"), sources, facts
    )
    advisory.extend(obligation_advisory)
    review_findings = _review_findings(request.get("independent_review_receipt"), current_hash)
    retention_findings = _retention_findings(request.get("retention_receipt"))
    asset_findings, selected_asset_ids = _asset_inventory_findings(
        request.get("asset_inventory"), project_root
    )
    figure_findings = _figure_findings(request.get("figures"), project_root, set(sources))
    revision_findings = _quality_revision_findings(request.get("quality_revision_receipt"))
    legacy_findings, legacy_status = _legacy_findings(request.get("legacy_receipt"))
    figures = request.get("figures")
    asset_inventory = request.get("asset_inventory")
    if isinstance(figures, list) and any(
        isinstance(figure, dict)
        and str(figure.get("role") or "").strip().lower() in CORE_FIGURE_ROLES
        and figure.get("decision") == "keep"
        for figure in figures
    ):
        if not isinstance(asset_inventory, dict) or asset_inventory.get("applicable") is not True:
            asset_findings.append("A kept core figure requires an applicable asset_inventory.")
    if selected_asset_ids and isinstance(figures, list):
        selected_paths = {
            str(item.get("path"))
            for item in request.get("asset_inventory", {}).get("candidates", [])
            if isinstance(item, dict) and str(item.get("asset_id")) in selected_asset_ids
        }
        for index, figure in enumerate(figures):
            if (
                isinstance(figure, dict)
                and str(figure.get("role") or "").strip().lower() in CORE_FIGURE_ROLES
                and figure.get("decision") == "keep"
            ):
                artifact = figure.get("artifact")
                figure_path = str(artifact.get("path")) if isinstance(artifact, dict) else ""
                if figure_path not in selected_paths:
                    asset_findings.append(
                        f"figures[{index}] kept core artifact is not selected by asset_inventory."
                    )
    findings = (
        base_findings
        + source_findings
        + coverage_findings
        + surface_findings
        + obligation_findings
        + review_findings
        + retention_findings
        + asset_findings
        + figure_findings
        + revision_findings
        + legacy_findings
    )

    truth_pass = not source_findings and not any(
        "support_source_ids" in item or "source authority" in item or "extraction receipt" in item
        for item in surface_findings + obligation_findings
    )
    process_pass = not (base_findings or coverage_findings or surface_findings)
    quality_pass = not (
        obligation_findings
        or review_findings
        or retention_findings
        or asset_findings
        or figure_findings
        or revision_findings
        or legacy_findings
    )
    ok = not findings
    claim_id = None
    if isinstance(request.get("claim_surface"), dict):
        claim_id = request["claim_surface"].get("claim_id")
    return {
        "contract": RESULT_CONTRACT,
        "interface_version": INTERFACE_VERSION,
        "request_sha256": sha256_bytes(canonical_json_bytes(request)),
        "revision_id": revision_id or None,
        "ok": ok,
        "outcome": "CLAIM_SURFACE_AUDITED" if ok else "BLOCKED",
        "stage": "claim_surface_audited" if ok else "adaptive_shadow_blocked",
        "claim_id": claim_id,
        "findings": findings,
        "advisory_findings": advisory,
        "coverage_status": "SUFFICIENT_FOR_SHADOW" if not coverage_findings else "INSUFFICIENT",
        "legacy_status_observed": legacy_status,
        "legacy_pass_tainted": legacy_status == "PASS",
        "assurance_vector": {
            "truth_authority_permission": "PASS" if truth_pass else "FAIL",
            "process_assurance": "PASS" if process_pass else "FAIL",
            "quality_optimization": "PASS" if quality_pass else "FAIL",
            "noncompensatory": True,
        },
        "signals": {
            "shadow_only": True,
            "legacy_authority_unchanged": True,
            "claim_surface_audited": ok,
            "manuscript_ready": False,
            "delivery_ready": False,
            "submission_ready": False,
            "external_action_authorized": False,
        },
        "authority_boundary": (
            "This shadow receipt covers one hash-bound claim surface only. It never grants whole-"
            "manuscript READY, delivery/submission readiness, or external-action authority."
        ),
    }


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    temp.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    os.replace(temp, path)


def commit_revision(
    store_root: Path,
    project_root: Path,
    request: dict[str, Any],
    result: dict[str, Any],
    expected_current: str,
) -> dict[str, str]:
    """Append an immutable revision and atomically move CURRENT with CAS semantics."""
    store = store_root.resolve()
    if not _inside(project_root, store):
        raise ValueError("revision store must remain inside project_root")
    revision_id = str(result.get("revision_id") or "")
    if not SAFE_ID.fullmatch(revision_id):
        raise ValueError("revision_id is invalid")
    current_path = store / "CURRENT"
    actual_current = current_path.read_text(encoding="utf-8").strip() if current_path.is_file() else "NONE"
    if actual_current != expected_current:
        raise ValueError(
            f"CURRENT compare-and-swap mismatch: expected {expected_current}, actual {actual_current}"
        )
    revision_dir = store / "revisions" / revision_id
    if revision_dir.exists():
        raise ValueError(f"immutable revision already exists: {revision_id}")
    revisions_root = store / "revisions"
    revisions_root.mkdir(parents=True, exist_ok=True)
    staging_dir = revisions_root / f".{revision_id}.{os.getpid()}.tmp"
    if staging_dir.exists():
        raise ValueError(f"revision staging path already exists: {staging_dir.name}")
    staging_dir.mkdir()
    request_path = staging_dir / "request.json"
    result_path = staging_dir / "result.json"
    _write_json_atomic(request_path, request)
    _write_json_atomic(result_path, result)
    pointer = {
        "revision_id": revision_id,
        "request_sha256": sha256_file(request_path),
        "result_sha256": sha256_file(result_path),
    }
    _write_json_atomic(staging_dir / "receipt.json", pointer)
    os.replace(staging_dir, revision_dir)
    current_temp = store / f".CURRENT.{os.getpid()}.tmp"
    current_temp.parent.mkdir(parents=True, exist_ok=True)
    current_temp.write_text(revision_id + "\n", encoding="utf-8")
    os.replace(current_temp, current_path)
    return {key: str(value) for key, value in pointer.items()}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate one domain-neutral PaperSpine adaptive shadow request."
    )
    parser.add_argument("request", type=Path, help="Path to the shadow request JSON.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Root used for artifact containment and hashes. Default: request directory.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional result JSON path.")
    parser.add_argument("--store", type=Path, default=None, help="Optional immutable revision store.")
    parser.add_argument(
        "--expected-current",
        default=None,
        help="Required with --store; use NONE for the first revision.",
    )
    args = parser.parse_args(argv)
    if args.store is not None and args.expected_current is None:
        parser.error("--store requires --expected-current for compare-and-swap safety.")
    if args.store is None and args.expected_current is not None:
        parser.error("--expected-current requires --store.")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    request_path = args.request.resolve()
    project_root = (args.project_root or request_path.parent).resolve()
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "outcome": "BLOCKED", "findings": [str(exc)]}))
        return 1
    result = audit_request(request, project_root)
    output: Path | None = None
    if args.output is not None:
        output = args.output if args.output.is_absolute() else project_root / args.output
        if not _inside(project_root, output):
            result["ok"] = False
            result["outcome"] = "BLOCKED"
            result["stage"] = "adaptive_shadow_blocked"
            result["findings"].append("output path must remain inside project_root.")
            output = None
    if args.store is not None:
        try:
            receipt = commit_revision(
                args.store if args.store.is_absolute() else project_root / args.store,
                project_root,
                request,
                result,
                args.expected_current,
            )
            result["revision_receipt"] = receipt
        except (OSError, ValueError) as exc:
            result["ok"] = False
            result["outcome"] = "BLOCKED"
            result["stage"] = "adaptive_shadow_blocked"
            result["signals"]["claim_surface_audited"] = False
            result["assurance_vector"]["process_assurance"] = "FAIL"
            result["findings"].append(str(exc))
    if output is not None:
        _write_json_atomic(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
