"""Typed, fail-closed quality contracts for PaperSpine5 W4--W6.

This module is intentionally pure: it does not read or write the task registry,
does not perform external actions, and does not promote the product maturity
level.  Callers bind every receipt to one immutable task revision and persist
the returned dictionaries through the transactional product kernel.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


SHA256_LENGTH = 64
QUALITY_CONTRACT_VERSION = "1.0"


class QualityContractError(ValueError):
    """Raised when a quality payload cannot be interpreted safely."""


class TruthStatus(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    STALE = "stale"


class ReadinessTier(str, Enum):
    CANONICAL = "canonical"
    INDEPENDENT_QUALITY = "independent_quality"
    FINAL_RENDER = "final_render"
    TARGET_PACKAGE = "target_package"
    AUTHOR_CLOSE = "author_close"


TIER_ORDER = tuple(ReadinessTier)
REQUESTED_SCOPES = (
    "manuscript",
    "local_delivery",
    "submission_package",
)
READINESS_LAYER_KEYS = (*REQUESTED_SCOPES, "external_action")
AUTHOR_ONLY_TARGET_FACT_KEYS = frozenset(
    {
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
)
REQUIRED_PREDICATES: dict[ReadinessTier, frozenset[str]] = {
    ReadinessTier.CANONICAL: frozenset(
        {
            "canonical_artifacts_bound",
            "final_claim_inventory_valid",
            "evidence_verification_valid",
        }
    ),
    ReadinessTier.INDEPENDENT_QUALITY: frozenset(
        {"independent_review_valid", "quality_objections_closed"}
    ),
    ReadinessTier.FINAL_RENDER: frozenset(
        {"final_render_bound", "surface_semantics_valid", "visual_accessibility_valid"}
    ),
    ReadinessTier.TARGET_PACKAGE: frozenset(
        {"target_research_valid", "target_compliance_valid", "target_bundle_fresh"}
    ),
    ReadinessTier.AUTHOR_CLOSE: frozenset(
        {"author_items_closed", "author_confirmed_current_revision"}
    ),
}


def _dedupe_findings(findings: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in findings:
        normalized = dict(finding)
        token = canonical_sha256(normalized)
        if token not in seen:
            seen.add(token)
            result.append(normalized)
    return result


def _normalize_layer_blockers(
    value: Mapping[str, Sequence[Mapping[str, Any]]] | None,
) -> dict[str, list[dict[str, Any]]]:
    source = value if isinstance(value, Mapping) else {}
    return {
        layer: _dedupe_findings(
            item for item in source.get(layer, []) if isinstance(item, Mapping)
        )
        for layer in READINESS_LAYER_KEYS
    }


def _finding_applies_to_layer(finding: Mapping[str, Any], layer: str) -> bool:
    path = str(finding.get("path") or "")
    if not path.startswith("tiers."):
        return True
    parts = path.split(".")
    tier = parts[1] if len(parts) > 1 else ""
    predicate_id = parts[2] if len(parts) > 2 else ""
    if layer == "manuscript":
        return tier in {"canonical", "independent_quality", "final_render"}
    if layer == "local_delivery":
        return tier in {"canonical", "independent_quality", "final_render"} or (
            tier == "target_package"
            and predicate_id
            in {
                "target_research_valid",
                "target_compliance_valid",
                "target_bundle_fresh",
            }
        )
    return True


def build_obligation_manifest(
    required_predicates_by_tier: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    """Build the hash-bound manifest that licenses the complete hard set."""

    declared = required_predicates_by_tier or {
        tier.value: sorted(required) for tier, required in REQUIRED_PREDICATES.items()
    }
    base = {
        "contract": "paperspine5.readiness-obligation-manifest",
        "contract_version": QUALITY_CONTRACT_VERSION,
        "required_predicates_by_tier": {
            tier.value: sorted({str(item) for item in declared.get(tier.value, [])})
            for tier in TIER_ORDER
        },
    }
    return {**base, "manifest_sha256": canonical_sha256(base)}


def _validate_obligation_manifest(
    manifest: Any, subject: QualitySubject
) -> tuple[dict[ReadinessTier, set[str]], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    required = {tier: set(REQUIRED_PREDICATES[tier]) for tier in TIER_ORDER}
    if not isinstance(manifest, Mapping):
        return required, [
            _finding(
                "OBLIGATION_MANIFEST_MISSING",
                "a hash-bound readiness obligation manifest is required",
                "obligation_manifest",
            )
        ]
    if manifest.get("contract") != "paperspine5.readiness-obligation-manifest" or manifest.get(
        "contract_version"
    ) != QUALITY_CONTRACT_VERSION:
        findings.append(
            _finding(
                "OBLIGATION_MANIFEST_CONTRACT_INVALID",
                "obligation manifest contract/version is invalid",
                "obligation_manifest",
            )
        )
    unsigned = {
        key: value for key, value in manifest.items() if key != "manifest_sha256"
    }
    manifest_hash = manifest.get("manifest_sha256")
    if not _is_sha256(manifest_hash) or manifest_hash != canonical_sha256(unsigned):
        findings.append(
            _finding(
                "OBLIGATION_MANIFEST_HASH_INVALID",
                "manifest_sha256 does not bind the exact obligation manifest",
                "obligation_manifest.manifest_sha256",
            )
        )
    subject_hash = subject.input_hashes.get("readiness_obligations")
    if subject_hash is None:
        findings.append(
            _finding(
                "OBLIGATION_MANIFEST_NOT_IN_SUBJECT",
                "readiness obligations are absent from the immutable quality subject",
                "subject.input_hashes.readiness_obligations",
            )
        )
    elif subject_hash != manifest_hash:
        findings.append(
            _finding(
                "OBLIGATION_MANIFEST_STALE",
                "obligation manifest differs from the revision-bound target authority",
                "obligation_manifest.manifest_sha256",
            )
        )
    declared = manifest.get("required_predicates_by_tier")
    if not isinstance(declared, Mapping) or set(declared) != {
        tier.value for tier in TIER_ORDER
    }:
        findings.append(
            _finding(
                "OBLIGATION_TIERS_INVALID",
                "manifest must enumerate exactly the five readiness tiers",
                "obligation_manifest.required_predicates_by_tier",
            )
        )
        return required, findings
    for tier in TIER_ORDER:
        values = declared.get(tier.value)
        if not isinstance(values, list) or any(not _nonempty(item) for item in values):
            findings.append(
                _finding(
                    "OBLIGATION_SET_INVALID",
                    f"{tier.value} obligations must be a list of non-empty predicate IDs",
                    f"obligation_manifest.required_predicates_by_tier.{tier.value}",
                )
            )
            continue
        if len(values) != len(set(values)):
            findings.append(
                _finding(
                    "OBLIGATION_SET_DUPLICATE",
                    f"{tier.value} obligation IDs must be unique",
                    f"obligation_manifest.required_predicates_by_tier.{tier.value}",
                )
            )
        declared_set = {str(item) for item in values}
        missing_fixed = sorted(REQUIRED_PREDICATES[tier] - declared_set)
        if missing_fixed:
            findings.append(
                _finding(
                    "FIXED_OBLIGATION_OMITTED",
                    f"{tier.value} omits fixed obligations: {missing_fixed}",
                    f"obligation_manifest.required_predicates_by_tier.{tier.value}",
                )
            )
        required[tier] = declared_set | set(REQUIRED_PREDICATES[tier])
    return required, findings


def canonical_sha256(value: Any) -> str:
    """Return the deterministic SHA-256 of a JSON-compatible value."""

    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != SHA256_LENGTH:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value.lower() == value


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_iso_date(value: Any) -> bool:
    if not _nonempty(value):
        return False
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item.strip() for item in value if _nonempty(item)}


@dataclass(frozen=True)
class QualitySubject:
    """The immutable content revision against which quality was evaluated."""

    task_id: str
    revision_id: str
    input_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        if not _nonempty(self.task_id) or not _nonempty(self.revision_id):
            raise QualityContractError("task_id and revision_id must be non-empty strings")
        if not isinstance(self.input_hashes, Mapping) or not self.input_hashes:
            raise QualityContractError("input_hashes must be a non-empty mapping")
        invalid = [key for key, value in self.input_hashes.items() if not _nonempty(key) or not _is_sha256(value)]
        if invalid:
            raise QualityContractError(f"input_hashes contain invalid SHA-256 values: {invalid}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QualitySubject":
        if not isinstance(value, Mapping):
            raise QualityContractError("subject must be an object")
        hashes = value.get("input_hashes")
        if not isinstance(hashes, Mapping):
            raise QualityContractError("subject.input_hashes must be an object")
        return cls(
            task_id=str(value.get("task_id") or ""),
            revision_id=str(value.get("revision_id") or ""),
            input_hashes={str(key): str(item) for key, item in hashes.items()},
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "revision_id": self.revision_id,
            "input_hashes": dict(sorted(self.input_hashes.items())),
        }


@dataclass
class CheckResult:
    contract: str
    subject: QualitySubject
    status: TruthStatus
    blockers: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    consumed_hashes: dict[str, str] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status is TruthStatus.TRUE

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "contract": self.contract,
            "contract_version": QUALITY_CONTRACT_VERSION,
            "subject": self.subject.as_dict(),
            "status": self.status.value,
            "ok": self.ok,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "consumed_hashes": dict(sorted(self.consumed_hashes.items())),
            "details": self.details,
        }
        payload["receipt_sha256"] = canonical_sha256(payload)
        return payload


def _finding(code: str, message: str, path: str = "") -> dict[str, str]:
    result = {"code": code, "message": message}
    if path:
        result["path"] = path
    return result


def _bound_subject(
    payload: Mapping[str, Any], expected: QualitySubject
) -> tuple[bool, dict[str, str]]:
    try:
        observed = QualitySubject.from_mapping(payload.get("subject", {}))
    except QualityContractError as exc:
        return False, _finding("SUBJECT_INVALID", str(exc), "subject")
    if observed != expected:
        return False, _finding(
            "SUBJECT_STALE",
            "receipt task/revision/input hashes do not match the current quality subject",
            "subject",
        )
    return True, {}


def _identity_core(identity: Mapping[str, Any]) -> dict[str, str]:
    keys = ("principal_id", "session_id", "run_id", "independence_group")
    return {key: str(identity.get(key) or "").strip() for key in keys}


def identity_provenance_sha256(identity: Mapping[str, Any]) -> str:
    """Hash the immutable identity fields used for independence checks."""

    return canonical_sha256(_identity_core(identity))


def _identity_findings(
    identity: Any,
    path: str,
    subject: QualitySubject | None = None,
    trusted_attestations: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    if not isinstance(identity, Mapping):
        return [_finding("IDENTITY_INVALID", "identity must be an object", path)]
    core = _identity_core(identity)
    missing = [key for key, value in core.items() if not value]
    if missing:
        return [
            _finding(
                "IDENTITY_INCOMPLETE",
                f"identity is missing immutable provenance fields: {missing}",
                path,
            )
        ]
    supplied = identity.get("provenance_sha256")
    expected = identity_provenance_sha256(identity)
    if supplied != expected:
        return [
            _finding(
                "IDENTITY_PROVENANCE_INVALID",
                "provenance_sha256 does not match the immutable identity fields",
                path,
            )
        ]
    if subject is not None:
        attestation_input_id = identity.get("attestation_input_id")
        if not _nonempty(attestation_input_id):
            return [
                _finding(
                    "IDENTITY_ATTESTATION_MISSING",
                    "identity must name its revision-bound provenance attestation input",
                    path,
                )
            ]
        bound_hash = subject.input_hashes.get(str(attestation_input_id))
        if bound_hash is None:
            return [
                _finding(
                    "IDENTITY_NOT_ATTESTED",
                    "identity provenance is not part of the immutable quality subject",
                    path,
                )
            ]
        if bound_hash != supplied:
            return [
                _finding(
                    "IDENTITY_ATTESTATION_STALE",
                    "identity provenance differs from the revision-bound attestation",
                    path,
                )
            ]
        if trusted_attestations is None:
            return [
                _finding(
                    "IDENTITY_TRUST_ROOT_UNAVAILABLE",
                    "kernel-issued actor/session attestations are required for independence",
                    path,
                )
            ]
        if trusted_attestations.get(str(attestation_input_id)) != supplied:
            return [
                _finding(
                    "IDENTITY_ATTESTATION_UNTRUSTED",
                    "identity attestation is absent or different in the trusted actor/session ledger",
                    path,
                )
            ]
    return []


def _independence_findings(
    reviewer: Any,
    producers: Sequence[Any],
    path: str,
    subject: QualitySubject | None = None,
    trusted_attestations: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    findings = _identity_findings(
        reviewer, path, subject, trusted_attestations
    )
    if findings:
        return findings
    reviewer_core = _identity_core(reviewer)
    reviewer_hash = reviewer.get("provenance_sha256")
    for index, producer in enumerate(producers):
        producer_path = f"{path}.subject_producers[{index}]"
        identity_errors = _identity_findings(
            producer, producer_path, subject, trusted_attestations
        )
        findings.extend(identity_errors)
        if identity_errors:
            continue
        producer_core = _identity_core(producer)
        shared = [
            field
            for field in ("principal_id", "session_id", "run_id", "independence_group")
            if reviewer_core[field] == producer_core[field]
        ]
        if reviewer_hash == producer.get("provenance_sha256"):
            shared.append("provenance_sha256")
        if shared:
            findings.append(
                _finding(
                    "REVIEW_NOT_INDEPENDENT",
                    "reviewer reuses producer provenance; renaming an agent is not independence "
                    f"(shared: {sorted(set(shared))})",
                    path,
                )
            )
    return findings


def validate_target_research(
    payload: Mapping[str, Any],
    subject: QualitySubject,
    *,
    trusted_attestations: Mapping[str, str] | None = None,
) -> CheckResult:
    """Validate official-hard and exemplar/style-advisory target research lanes."""

    bound, issue = _bound_subject(payload, subject)
    if not bound:
        return CheckResult(
            "paperspine5.target-research-check", subject, TruthStatus.STALE, [issue]
        )

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    sources = payload.get("sources")
    rules = payload.get("rules")
    if not isinstance(sources, list) or not sources:
        blockers.append(_finding("SOURCE_RECEIPTS_MISSING", "sources must contain SourceReceipts", "sources"))
        sources = []
    if not isinstance(rules, list) or not rules:
        blockers.append(_finding("TARGET_RULES_MISSING", "rules must contain extracted target obligations", "rules"))
        rules = []

    source_by_id: dict[str, Mapping[str, Any]] = {}
    official_hard_count = 0
    official_hard_rule_count = 0
    consumed: dict[str, str] = {}
    for index, source in enumerate(sources):
        path = f"sources[{index}]"
        if not isinstance(source, Mapping):
            blockers.append(_finding("SOURCE_RECEIPT_INVALID", "source receipt must be an object", path))
            continue
        source_id = str(source.get("source_id") or "").strip()
        lane = source.get("lane")
        authority = source.get("authority")
        if not source_id or source_id in source_by_id:
            blockers.append(_finding("SOURCE_ID_INVALID", "source_id must be non-empty and unique", path))
            continue
        source_by_id[source_id] = source
        if lane not in {"official", "exemplar_style"}:
            blockers.append(_finding("SOURCE_LANE_INVALID", "lane must be official or exemplar_style", path))
        if authority not in {"official_hard", "advisory"}:
            blockers.append(_finding("SOURCE_AUTHORITY_INVALID", "authority must be official_hard or advisory", path))
        if lane == "exemplar_style" and authority != "advisory":
            blockers.append(_finding("ADVISORY_ESCALATED", "exemplar/style sources can never acquire hard authority", path))
        if authority == "official_hard":
            official_hard_count += 1
            if lane != "official" or source.get("officiality_verified") is not True:
                blockers.append(_finding("OFFICIAL_UNSUPPORTED", "official_hard requires the official lane and verified officiality", path))
        for field_name in ("locator", "retrieved_at", "effective_date"):
            if not _nonempty(source.get(field_name)):
                blockers.append(_finding("SOURCE_PROVENANCE_INCOMPLETE", f"{field_name} is required", f"{path}.{field_name}"))
        if not _is_iso_date(source.get("effective_date")):
            blockers.append(
                _finding(
                    "SOURCE_EFFECTIVE_DATE_INVALID",
                    "effective_date must be an ISO calendar date",
                    f"{path}.effective_date",
                )
            )
        content_hash = source.get("content_sha256")
        if not _is_sha256(content_hash):
            blockers.append(_finding("SOURCE_CONTENT_UNBOUND", "content_sha256 must bind the frozen source content", f"{path}.content_sha256"))
        else:
            consumed[f"source:{source_id}"] = str(content_hash)
            subject_hash = subject.input_hashes.get(f"source:{source_id}")
            if subject_hash is None:
                blockers.append(
                    _finding(
                        "SOURCE_NOT_IN_REVISION",
                        "the source content hash is not part of the immutable quality subject",
                        f"{path}.content_sha256",
                    )
                )
            elif subject_hash != content_hash:
                return CheckResult(
                    "paperspine5.target-research-check",
                    subject,
                    TruthStatus.STALE,
                    [
                        _finding(
                            "SOURCE_STALE",
                            f"{source_id} changed after this target-research receipt",
                            f"{path}.content_sha256",
                        )
                    ],
                )
        spans = source.get("supported_spans")
        if not isinstance(spans, list) or not spans or any(
            not isinstance(span, Mapping)
            or not _nonempty(span.get("quote_sha256"))
            or not _is_sha256(span.get("quote_sha256"))
            or not _nonempty(span.get("locator"))
            for span in spans
        ):
            blockers.append(_finding("SOURCE_SPAN_MISSING", "a hard or advisory extraction needs content-bound supported spans", f"{path}.supported_spans"))

    rule_ids: set[str] = set()
    for index, rule in enumerate(rules):
        path = f"rules[{index}]"
        if not isinstance(rule, Mapping):
            blockers.append(_finding("TARGET_RULE_INVALID", "rule must be an object", path))
            continue
        rule_id = str(rule.get("rule_id") or "").strip()
        if not rule_id or rule_id in rule_ids:
            blockers.append(_finding("TARGET_RULE_ID_INVALID", "rule_id must be non-empty and unique", path))
            continue
        rule_ids.add(rule_id)
        kind = rule.get("kind")
        enforcement = rule.get("enforcement")
        rule_sources = _string_set(rule.get("source_ids"))
        if kind not in {"hard", "advisory"} or enforcement not in {"hard", "advisory"}:
            blockers.append(_finding("TARGET_RULE_AUTHORITY_INVALID", "kind/enforcement must be hard or advisory", path))
        if kind == "advisory" and enforcement == "hard":
            blockers.append(_finding("ADVISORY_ESCALATED", "advisory target learning cannot be enforced as a hard rule", path))
        if not _nonempty(rule.get("statement")) or not _is_iso_date(rule.get("effective_date")):
            blockers.append(_finding("TARGET_RULE_INCOMPLETE", "statement and effective_date are required", path))
        if not rule_sources:
            blockers.append(_finding("TARGET_RULE_UNSUPPORTED", "rule must cite at least one SourceReceipt", path))
        missing_sources = sorted(rule_sources - set(source_by_id))
        if missing_sources:
            blockers.append(_finding("TARGET_RULE_UNSUPPORTED", f"rule cites missing sources: {missing_sources}", path))
        if kind == "hard":
            readiness_scope = rule.get("readiness_scope")
            if readiness_scope not in {
                "local_delivery",
                "author_only_submission",
            }:
                blockers.append(
                    _finding(
                        "TARGET_RULE_READINESS_SCOPE_INVALID",
                        "every hard target rule needs a typed readiness_scope",
                        path,
                    )
                )
            author_fact_key = rule.get("author_fact_key")
            if readiness_scope == "author_only_submission":
                if author_fact_key not in AUTHOR_ONLY_TARGET_FACT_KEYS:
                    blockers.append(
                        _finding(
                            "TARGET_RULE_AUTHOR_FACT_INVALID",
                            "author-only target rules need a fixed author_fact_key",
                            path,
                        )
                    )
            elif author_fact_key is not None:
                blockers.append(
                    _finding(
                        "TARGET_RULE_AUTHOR_FACT_INVALID",
                        "local-delivery target rules cannot carry author_fact_key",
                        path,
                    )
                )
            if not _nonempty(rule.get("evidence_locator")):
                blockers.append(
                    _finding(
                        "TARGET_RULE_EVIDENCE_LOCATOR_MISSING",
                        "hard target rules must locate their frozen source evidence",
                        path,
                    )
                )
            unsupported = [
                source_id
                for source_id in rule_sources
                if source_by_id.get(source_id, {}).get("authority") != "official_hard"
            ]
            if unsupported:
                blockers.append(_finding("HARD_RULE_NOT_OFFICIAL", f"hard rule depends on non-official/advisory sources: {unsupported}", path))
            if enforcement == "hard" and not unsupported and rule_sources:
                official_hard_rule_count += 1

    coverage = payload.get("coverage")
    if not isinstance(coverage, Mapping):
        blockers.append(_finding("COVERAGE_RECEIPT_MISSING", "coverage receipt is required", "coverage"))
    else:
        required_topics = _string_set(coverage.get("required_topics"))
        covered_topics = _string_set(coverage.get("covered_topics"))
        if not required_topics:
            blockers.append(_finding("COVERAGE_SCOPE_UNKNOWN", "required_topics must be declared before coverage can pass", "coverage.required_topics"))
        uncovered = sorted(required_topics - covered_topics)
        if uncovered:
            blockers.append(_finding("TARGET_COVERAGE_INCOMPLETE", f"required target topics are uncovered: {uncovered}", "coverage"))
        if not _string_set(coverage.get("source_ids")):
            blockers.append(_finding("COVERAGE_SOURCELESS", "coverage must bind the sources inspected", "coverage.source_ids"))
        else:
            missing_coverage_sources = sorted(
                _string_set(coverage.get("source_ids")) - set(source_by_id)
            )
            if missing_coverage_sources:
                blockers.append(
                    _finding(
                        "COVERAGE_SOURCE_UNKNOWN",
                        f"coverage cites missing SourceReceipts: {missing_coverage_sources}",
                        "coverage.source_ids",
                    )
                )

    producer = payload.get("producer")
    blockers.extend(
        _identity_findings(producer, "producer", subject, trusted_attestations)
    )
    challenger = payload.get("challenger")
    if not isinstance(challenger, Mapping):
        blockers.append(_finding("CHALLENGER_RECEIPT_MISSING", "an independent coverage challenger is required", "challenger"))
    else:
        blockers.extend(
            _independence_findings(
                challenger.get("reviewer"),
                [producer],
                "challenger.reviewer",
                subject,
                trusted_attestations,
            )
        )
        if challenger.get("research_snapshot_sha256") != payload.get("research_snapshot_sha256") or not _is_sha256(challenger.get("research_snapshot_sha256")):
            blockers.append(_finding("CHALLENGER_STALE", "challenger must inspect the exact frozen research snapshot", "challenger.research_snapshot_sha256"))
        if challenger.get("status") not in {"pass", "blocked"}:
            blockers.append(_finding("CHALLENGER_STATUS_UNKNOWN", "challenger status must be pass or blocked", "challenger.status"))
        if challenger.get("status") == "blocked":
            blockers.append(_finding("CHALLENGER_BLOCKED", "independent challenger left target-research objections unresolved", "challenger"))
        objections = challenger.get("objections", [])
        if not isinstance(objections, list) or any(
            not isinstance(item, Mapping) or item.get("status") != "resolved"
            for item in objections
        ):
            blockers.append(
                _finding(
                    "CHALLENGER_OBJECTION_OPEN",
                    "all challenger objections must be explicitly resolved",
                    "challenger.objections",
                )
            )

    conflicts = payload.get("conflicts", [])
    if not isinstance(conflicts, list):
        blockers.append(_finding("CONFLICT_REGISTER_INVALID", "conflicts must be a list", "conflicts"))
    else:
        for index, conflict in enumerate(conflicts):
            if not isinstance(conflict, Mapping) or conflict.get("status") != "resolved" or not _nonempty(conflict.get("resolution")):
                blockers.append(_finding("TARGET_CONFLICT_UNRESOLVED", "every detected target-rule conflict must be explicitly resolved", f"conflicts[{index}]"))

    research_hash = payload.get("research_snapshot_sha256")
    if not _is_sha256(research_hash):
        blockers.append(_finding("RESEARCH_SNAPSHOT_UNBOUND", "research_snapshot_sha256 is required", "research_snapshot_sha256"))
    else:
        consumed["target_research_snapshot"] = str(research_hash)
        subject_hash = subject.input_hashes.get("target_research_snapshot")
        if subject_hash is None:
            blockers.append(
                _finding(
                    "RESEARCH_SNAPSHOT_NOT_IN_REVISION",
                    "target_research_snapshot is absent from the immutable quality subject",
                    "research_snapshot_sha256",
                )
            )
        elif subject_hash != research_hash:
            return CheckResult(
                "paperspine5.target-research-check",
                subject,
                TruthStatus.STALE,
                [
                    _finding(
                        "RESEARCH_SNAPSHOT_STALE",
                        "target research snapshot changed after this receipt",
                        "research_snapshot_sha256",
                    )
                ],
            )

    if official_hard_count == 0:
        blockers.append(_finding("OFFICIAL_AUTHORITY_UNKNOWN", "no official-hard source was established; target hard rules remain unknown"))
    if official_hard_rule_count == 0:
        blockers.append(
            _finding(
                "OFFICIAL_HARD_RULE_UNKNOWN",
                "no hard target obligation is supported by an official-hard source; target requirements remain unknown",
                "rules",
            )
        )
    unknown_codes = {"OFFICIAL_AUTHORITY_UNKNOWN", "OFFICIAL_HARD_RULE_UNKNOWN"}
    blocker_codes = {str(item.get("code") or "") for item in blockers}
    status = (
        TruthStatus.TRUE
        if not blockers
        else TruthStatus.UNKNOWN
        if blocker_codes <= unknown_codes
        else TruthStatus.FALSE
    )
    return CheckResult(
        "paperspine5.target-research-check",
        subject,
        status,
        blockers,
        warnings,
        consumed,
        {
            "official_hard_sources": official_hard_count,
            "official_hard_rules": official_hard_rule_count,
            "rule_count": len(rule_ids),
        },
    )


def validate_claim_inventory(
    payload: Mapping[str, Any],
    subject: QualitySubject,
    *,
    trusted_attestations: Mapping[str, str] | None = None,
) -> CheckResult:
    """Validate the independently extracted, reader-facing final claim index."""

    bound, issue = _bound_subject(payload, subject)
    if not bound:
        return CheckResult(
            "paperspine5.final-claim-inventory-check", subject, TruthStatus.STALE, [issue]
        )
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    consumed: dict[str, str] = {}

    manuscript_hash = payload.get("manuscript_sha256")
    if not _is_sha256(manuscript_hash):
        blockers.append(_finding("MANUSCRIPT_UNBOUND", "manuscript_sha256 is required", "manuscript_sha256"))
    elif subject.input_hashes.get("manuscript") != manuscript_hash:
        return CheckResult(
            "paperspine5.final-claim-inventory-check",
            subject,
            TruthStatus.STALE,
            [_finding("MANUSCRIPT_STALE", "claim inventory is not for the current manuscript", "manuscript_sha256")],
        )
    else:
        consumed["manuscript"] = str(manuscript_hash)

    producer = payload.get("producer")
    blockers.extend(
        _identity_findings(producer, "producer", subject, trusted_attestations)
    )
    source_graph_hash = payload.get("source_claim_graph_sha256")
    if not _is_sha256(source_graph_hash):
        blockers.append(
            _finding(
                "SOURCE_CLAIM_GRAPH_UNBOUND",
                "source_claim_graph_sha256 is required",
                "source_claim_graph_sha256",
            )
        )
    else:
        current_graph_hash = subject.input_hashes.get("source_claim_graph")
        if current_graph_hash is None:
            blockers.append(
                _finding(
                    "SOURCE_CLAIM_GRAPH_NOT_IN_REVISION",
                    "source claim graph is absent from the immutable quality subject",
                    "source_claim_graph_sha256",
                )
            )
        elif current_graph_hash != source_graph_hash:
            return CheckResult(
                "paperspine5.final-claim-inventory-check",
                subject,
                TruthStatus.STALE,
                [
                    _finding(
                        "SOURCE_CLAIM_GRAPH_STALE",
                        "source claim scope changed after this inventory",
                        "source_claim_graph_sha256",
                    )
                ],
            )
        else:
            consumed["source_claim_graph"] = str(source_graph_hash)

    scope = payload.get("scope_receipt")
    if not isinstance(scope, Mapping):
        blockers.append(
            _finding(
                "CLAIM_SCOPE_RECEIPT_MISSING",
                "an independent source-claim scope/retention receipt is required",
                "scope_receipt",
            )
        )
        scope = {}
    else:
        blockers.extend(
            _independence_findings(
                scope.get("reviewer"),
                [producer],
                "scope_receipt.reviewer",
                subject,
                trusted_attestations,
            )
        )
        if scope.get("source_claim_graph_sha256") != source_graph_hash:
            blockers.append(
                _finding(
                    "CLAIM_SCOPE_STALE",
                    "scope receipt must bind the current source claim graph",
                    "scope_receipt.source_claim_graph_sha256",
                )
            )
        if scope.get("complete_scope") is not True:
            blockers.append(
                _finding(
                    "CLAIM_SCOPE_INCOMPLETE",
                    "producer-selected core claims cannot replace a complete independent source scope",
                    "scope_receipt.complete_scope",
                )
            )
    extraction = payload.get("extraction_receipt")
    if not isinstance(extraction, Mapping):
        blockers.append(_finding("EXTRACTION_RECEIPT_MISSING", "independent final-reader extraction receipt is required", "extraction_receipt"))
        extraction = {}
    else:
        blockers.extend(
            _independence_findings(
                extraction.get("extractor"),
                [producer],
                "extraction_receipt.extractor",
                subject,
                trusted_attestations,
            )
        )
        if extraction.get("manuscript_sha256") != manuscript_hash:
            blockers.append(_finding("EXTRACTION_STALE", "extractor did not inspect the current manuscript", "extraction_receipt.manuscript_sha256"))
        if extraction.get("complete_scan") is not True:
            blockers.append(_finding("EXTRACTION_INCOMPLETE", "producer-selected core claims cannot substitute for a complete final-reader scan", "extraction_receipt.complete_scan"))

    registered_raw = payload.get("registered_claims")
    inventory_raw = payload.get("reader_inventory")
    registered = registered_raw if isinstance(registered_raw, list) else []
    inventory = inventory_raw if isinstance(inventory_raw, list) else []
    if not registered:
        blockers.append(_finding("CLAIM_REGISTER_EMPTY", "registered_claims must not be empty", "registered_claims"))
    if not inventory:
        blockers.append(_finding("READER_INVENTORY_EMPTY", "reader_inventory must not be empty", "reader_inventory"))

    claim_by_id: dict[str, Mapping[str, Any]] = {}
    retained_reader_claims: set[str] = set()
    for index, claim in enumerate(registered):
        path = f"registered_claims[{index}]"
        if not isinstance(claim, Mapping):
            blockers.append(_finding("CLAIM_INVALID", "claim must be an object", path))
            continue
        claim_id = str(claim.get("claim_id") or "").strip()
        if not claim_id or claim_id in claim_by_id:
            blockers.append(_finding("CLAIM_ID_INVALID", "claim_id must be non-empty and unique", path))
            continue
        claim_by_id[claim_id] = claim
        disposition = claim.get("disposition")
        if disposition not in {"retained", "omitted"}:
            blockers.append(_finding("CLAIM_DISPOSITION_INVALID", "disposition must be retained or omitted", path))
        if disposition == "retained":
            if not _string_set(claim.get("evidence_ids")):
                blockers.append(_finding("RETAINED_CLAIM_UNSUPPORTED", "retained claims need positive evidence_ids", path))
            if claim.get("reader_facing_expected") is True:
                retained_reader_claims.add(claim_id)
        if disposition == "omitted":
            if not _nonempty(claim.get("omission_reason")) or not _nonempty(claim.get("omission_receipt_id")):
                blockers.append(_finding("OMISSION_UNACCOUNTED", "omitted claims require a reason and omission receipt", path))

    scoped_claims = _string_set(scope.get("source_claim_ids"))
    required_reader_claims = _string_set(scope.get("required_reader_claim_ids"))
    allowed_omissions = _string_set(scope.get("allowed_omission_ids"))
    independently_required_surfaces = _string_set(scope.get("required_surfaces"))
    if not scoped_claims:
        blockers.append(
            _finding(
                "SOURCE_CLAIM_SCOPE_UNKNOWN",
                "scope receipt must enumerate all source claim IDs",
                "scope_receipt.source_claim_ids",
            )
        )
    missing_registered = sorted(scoped_claims - set(claim_by_id))
    if missing_registered:
        blockers.append(
            _finding(
                "SOURCE_CLAIM_UNREGISTERED",
                f"source claims are absent from the producer register: {missing_registered}",
                "registered_claims",
            )
        )
    unscoped_registered = sorted(set(claim_by_id) - scoped_claims)
    if unscoped_registered:
        blockers.append(
            _finding(
                "REGISTERED_CLAIM_OUTSIDE_SCOPE",
                f"registered claims are absent from the independent source scope: {unscoped_registered}",
                "registered_claims",
            )
        )
    impossible_required = sorted(required_reader_claims - scoped_claims)
    if impossible_required:
        blockers.append(
            _finding(
                "REQUIRED_CLAIM_OUTSIDE_SCOPE",
                f"required reader claims are outside the frozen source scope: {impossible_required}",
                "scope_receipt.required_reader_claim_ids",
            )
        )
    for claim_id in scoped_claims & set(claim_by_id):
        claim = claim_by_id[claim_id]
        disposition = claim.get("disposition")
        if claim_id in required_reader_claims and disposition != "retained":
            blockers.append(
                _finding(
                    "REQUIRED_CLAIM_OMITTED",
                    f"independently required reader claim {claim_id} was not retained",
                    "registered_claims",
                )
            )
        if disposition == "omitted" and claim_id not in allowed_omissions:
            blockers.append(
                _finding(
                    "UNAUTHORIZED_CLAIM_OMISSION",
                    f"claim {claim_id} was omitted without independent scope authorization",
                    "registered_claims",
                )
            )
    retained_reader_claims.update(required_reader_claims)

    inventory_by_id: dict[str, Mapping[str, Any]] = {}
    mapped_claims: set[str] = set()
    inventory_by_surface: dict[str, set[str]] = {}
    for index, item in enumerate(inventory):
        path = f"reader_inventory[{index}]"
        if not isinstance(item, Mapping):
            blockers.append(_finding("READER_CLAIM_INVALID", "reader inventory item must be an object", path))
            continue
        inventory_id = str(item.get("inventory_id") or "").strip()
        surface = str(item.get("surface") or "").strip()
        text = str(item.get("text") or "")
        if not inventory_id or inventory_id in inventory_by_id:
            blockers.append(_finding("INVENTORY_ID_INVALID", "inventory_id must be non-empty and unique", path))
            continue
        inventory_by_id[inventory_id] = item
        inventory_by_surface.setdefault(surface, set()).add(inventory_id)
        if surface not in {"title", "abstract", "conclusion", "caption", "body"}:
            blockers.append(_finding("READER_SURFACE_INVALID", "unsupported reader-facing surface", f"{path}.surface"))
        if not _nonempty(item.get("span")):
            blockers.append(_finding("READER_SPAN_MISSING", "reader claim must identify its exact final span", path))
        if not _nonempty(text) or item.get("text_sha256") != text_sha256(text):
            blockers.append(_finding("READER_TEXT_UNBOUND", "text_sha256 must bind the exact reader-visible claim text", path))
        mapped = _string_set(item.get("claim_ids"))
        if not mapped:
            blockers.append(_finding("READER_CLAIM_UNMAPPED", "every reader-facing claim must map back to registered claims", path))
        missing = sorted(mapped - set(claim_by_id))
        if missing:
            blockers.append(_finding("READER_CLAIM_UNKNOWN", f"reader claim maps to unknown claim IDs: {missing}", path))
        mapped_omissions = sorted(
            claim_id
            for claim_id in mapped
            if claim_by_id.get(claim_id, {}).get("disposition") == "omitted"
        )
        if mapped_omissions:
            blockers.append(
                _finding(
                    "OMITTED_CLAIM_STILL_VISIBLE",
                    f"reader-facing text maps to claims declared omitted: {mapped_omissions}",
                    path,
                )
            )
        mapped_claims.update(mapped)

    declared_extracted = _string_set(extraction.get("inventory_ids"))
    if declared_extracted != set(inventory_by_id):
        blockers.append(_finding("EXTRACTED_SET_MISMATCH", "extraction receipt must enumerate the complete reader inventory", "extraction_receipt.inventory_ids"))

    required_surfaces = _string_set(payload.get("required_surfaces"))
    if not required_surfaces:
        blockers.append(_finding("REQUIRED_SURFACES_UNKNOWN", "required_surfaces must be declared for this manuscript/target", "required_surfaces"))
    if required_surfaces != independently_required_surfaces:
        blockers.append(
            _finding(
                "REQUIRED_SURFACE_SCOPE_MISMATCH",
                "required_surfaces must exactly match the independent scope receipt",
                "required_surfaces",
            )
        )
    surface_receipts = payload.get("surface_receipts")
    surface_receipts = surface_receipts if isinstance(surface_receipts, list) else []
    receipts_by_surface: dict[str, Mapping[str, Any]] = {}
    for index, receipt in enumerate(surface_receipts):
        path = f"surface_receipts[{index}]"
        if not isinstance(receipt, Mapping):
            blockers.append(_finding("SURFACE_RECEIPT_INVALID", "surface receipt must be an object", path))
            continue
        surface = str(receipt.get("surface") or "")
        receipts_by_surface[surface] = receipt
        if receipt.get("complete_scan") is not True:
            blockers.append(_finding("SURFACE_SCAN_INCOMPLETE", "surface scan must be complete", path))
        if not _is_sha256(receipt.get("surface_sha256")):
            blockers.append(_finding("SURFACE_UNBOUND", "surface_sha256 is required", path))
        else:
            subject_hash = subject.input_hashes.get(f"surface:{surface}")
            if subject_hash is None:
                blockers.append(
                    _finding(
                        "SURFACE_NOT_IN_REVISION",
                        f"{surface} hash is absent from the immutable quality subject",
                        path,
                    )
                )
            elif subject_hash != receipt.get("surface_sha256"):
                return CheckResult(
                    "paperspine5.final-claim-inventory-check",
                    subject,
                    TruthStatus.STALE,
                    [_finding("SURFACE_STALE", f"{surface} receipt is stale", path)],
                )
        if _string_set(receipt.get("inventory_ids")) != inventory_by_surface.get(surface, set()):
            blockers.append(_finding("SURFACE_INVENTORY_MISMATCH", "surface receipt does not enumerate its exact extracted claims", path))
    missing_surfaces = sorted(required_surfaces - set(receipts_by_surface))
    if missing_surfaces:
        blockers.append(_finding("SURFACE_RECEIPTS_MISSING", f"required surfaces lack receipts: {missing_surfaces}", "surface_receipts"))
    for surface in required_surfaces:
        if not inventory_by_surface.get(surface):
            warnings.append(_finding("SURFACE_HAS_NO_ASSERTION", f"{surface} contains no extracted assertion; reviewer should confirm this is intentional"))

    omitted_from_final = sorted(retained_reader_claims - mapped_claims)
    if omitted_from_final:
        blockers.append(_finding("FINAL_CLAIM_OMISSION", f"retained reader-facing claims are absent from the final-reader inventory: {omitted_from_final}"))

    status = TruthStatus.FALSE if blockers else TruthStatus.TRUE
    return CheckResult(
        "paperspine5.final-claim-inventory-check",
        subject,
        status,
        blockers,
        warnings,
        consumed,
        {
            "registered_claim_count": len(claim_by_id),
            "reader_claim_count": len(inventory_by_id),
            "required_surfaces": sorted(required_surfaces),
        },
    )


def validate_evidence_registry(
    payload: Mapping[str, Any],
    subject: QualitySubject,
    *,
    trusted_attestations: Mapping[str, str] | None = None,
) -> CheckResult:
    """Validate typed evidence verification; a connected ledger is not enough."""

    bound, issue = _bound_subject(payload, subject)
    if not bound:
        return CheckResult(
            "paperspine5.evidence-registry-check", subject, TruthStatus.STALE, [issue]
        )
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    consumed: dict[str, str] = {}
    producers_raw = payload.get("subject_producers")
    producers = producers_raw if isinstance(producers_raw, list) else []
    if not producers:
        blockers.append(
            _finding(
                "PRODUCER_PROVENANCE_MISSING",
                "subject_producers must identify the evidence producers",
                "subject_producers",
            )
        )
    for index, producer in enumerate(producers):
        blockers.extend(
            _identity_findings(
                producer,
                f"subject_producers[{index}]",
                subject,
                trusted_attestations,
            )
        )
    claim_inventory_hash = payload.get("claim_inventory_sha256")
    if not _is_sha256(claim_inventory_hash):
        blockers.append(
            _finding(
                "EVIDENCE_SCOPE_UNBOUND",
                "claim_inventory_sha256 is required to freeze the evidence scope",
                "claim_inventory_sha256",
            )
        )
    else:
        current_claim_inventory = subject.input_hashes.get("claim_inventory")
        if current_claim_inventory is None:
            blockers.append(
                _finding(
                    "EVIDENCE_SCOPE_NOT_IN_REVISION",
                    "claim inventory is absent from the immutable quality subject",
                    "claim_inventory_sha256",
                )
            )
        elif current_claim_inventory != claim_inventory_hash:
            return CheckResult(
                "paperspine5.evidence-registry-check",
                subject,
                TruthStatus.STALE,
                [
                    _finding(
                        "EVIDENCE_SCOPE_STALE",
                        "claim inventory changed after the evidence scope was frozen",
                        "claim_inventory_sha256",
                    )
                ],
            )
        else:
            consumed["claim_inventory"] = str(claim_inventory_hash)
    evidence_scope = payload.get("scope_receipt")
    if not isinstance(evidence_scope, Mapping):
        blockers.append(
            _finding(
                "EVIDENCE_SCOPE_RECEIPT_MISSING",
                "an independent evidence-scope receipt is required",
                "scope_receipt",
            )
        )
        evidence_scope = {}
    else:
        blockers.extend(
            _independence_findings(
                evidence_scope.get("reviewer"),
                producers,
                "scope_receipt.reviewer",
                subject,
                trusted_attestations,
            )
        )
        if evidence_scope.get("claim_inventory_sha256") != claim_inventory_hash:
            blockers.append(
                _finding(
                    "EVIDENCE_SCOPE_STALE",
                    "evidence scope receipt must bind the current claim inventory",
                    "scope_receipt.claim_inventory_sha256",
                )
            )
        if evidence_scope.get("complete_scope") is not True:
            blockers.append(
                _finding(
                    "EVIDENCE_SCOPE_INCOMPLETE",
                    "producer-selected evidence cannot replace an independent complete scope",
                    "scope_receipt.complete_scope",
                )
            )
    adapters_raw = payload.get("adapters")
    evidence_raw = payload.get("evidence")
    adapters = adapters_raw if isinstance(adapters_raw, list) else []
    evidence = evidence_raw if isinstance(evidence_raw, list) else []
    if not adapters:
        blockers.append(_finding("EVIDENCE_ADAPTERS_MISSING", "typed verifier adapters are required", "adapters"))
    if not evidence:
        blockers.append(_finding("EVIDENCE_RECEIPTS_MISSING", "evidence receipts are required", "evidence"))

    adapter_by_id: dict[str, Mapping[str, Any]] = {}
    for index, adapter in enumerate(adapters):
        path = f"adapters[{index}]"
        if not isinstance(adapter, Mapping):
            blockers.append(_finding("ADAPTER_INVALID", "adapter must be an object", path))
            continue
        adapter_id = str(adapter.get("adapter_id") or "").strip()
        if not adapter_id or adapter_id in adapter_by_id:
            blockers.append(_finding("ADAPTER_ID_INVALID", "adapter_id must be non-empty and unique", path))
            continue
        adapter_by_id[adapter_id] = adapter
        supported = _string_set(adapter.get("evidence_types"))
        if not supported or not supported.issubset({"data", "code", "statistics", "qualitative", "theoretical"}):
            blockers.append(_finding("ADAPTER_TYPES_INVALID", "adapter must declare supported evidence types", path))
        if adapter.get("status") != "active" or adapter.get("fail_closed") is not True:
            blockers.append(_finding("ADAPTER_NOT_FAIL_CLOSED", "adapter must be active and fail_closed", path))
        if not _is_sha256(adapter.get("protocol_sha256")):
            blockers.append(_finding("ADAPTER_PROTOCOL_UNBOUND", "adapter protocol_sha256 is required", path))

    required_ids = _string_set(payload.get("required_evidence_ids"))
    scoped_required_ids = _string_set(evidence_scope.get("required_evidence_ids"))
    if required_ids != scoped_required_ids:
        blockers.append(
            _finding(
                "REQUIRED_EVIDENCE_SCOPE_MISMATCH",
                "required_evidence_ids must exactly match the independent scope receipt",
                "required_evidence_ids",
            )
        )
    observed_ids: set[str] = set()
    unknown_ids: list[str] = []
    for index, receipt in enumerate(evidence):
        path = f"evidence[{index}]"
        if not isinstance(receipt, Mapping):
            blockers.append(_finding("EVIDENCE_RECEIPT_INVALID", "evidence receipt must be an object", path))
            continue
        evidence_id = str(receipt.get("evidence_id") or "").strip()
        evidence_type = receipt.get("evidence_type")
        adapter_id = str(receipt.get("adapter_id") or "").strip()
        if not evidence_id or evidence_id in observed_ids:
            blockers.append(_finding("EVIDENCE_ID_INVALID", "evidence_id must be non-empty and unique", path))
            continue
        observed_ids.add(evidence_id)
        if evidence_type not in {"data", "code", "statistics", "qualitative", "theoretical"}:
            blockers.append(_finding("EVIDENCE_TYPE_INVALID", "unsupported evidence type", path))
        adapter = adapter_by_id.get(adapter_id)
        if adapter is None or evidence_type not in _string_set(adapter.get("evidence_types")):
            blockers.append(_finding("EVIDENCE_ADAPTER_MISMATCH", "receipt lacks a compatible registered adapter", path))
        receipt_inputs = receipt.get("input_hashes")
        if not isinstance(receipt_inputs, Mapping) or not receipt_inputs or any(not _is_sha256(value) for value in receipt_inputs.values()):
            blockers.append(_finding("EVIDENCE_INPUTS_UNBOUND", "input_hashes must bind every verifier input", path))
        else:
            for key, value in receipt_inputs.items():
                current = subject.input_hashes.get(str(key))
                if current is None:
                    blockers.append(
                        _finding(
                            "EVIDENCE_INPUT_NOT_IN_REVISION",
                            f"{evidence_id} consumed input {key} that is absent from the quality subject",
                            path,
                        )
                    )
                elif current != value:
                    return CheckResult(
                        "paperspine5.evidence-registry-check",
                        subject,
                        TruthStatus.STALE,
                        [_finding("EVIDENCE_STALE", f"{evidence_id} consumed stale input {key}", path)],
                    )
                consumed[f"evidence:{evidence_id}:{key}"] = str(value)
        if not _is_sha256(receipt.get("output_sha256")):
            blockers.append(_finding("EVIDENCE_OUTPUT_UNBOUND", "output_sha256 is required", path))

        verification = receipt.get("verification")
        if not isinstance(verification, Mapping):
            blockers.append(_finding("VERIFICATION_RECEIPT_MISSING", "typed verification receipt is required", path))
            continue
        status = verification.get("status")
        if status not in {item.value for item in TruthStatus}:
            blockers.append(_finding("VERIFICATION_STATUS_INVALID", "verification status must be true/false/unknown/stale", path))
            continue
        if verification.get("adapter_id") != adapter_id or verification.get("output_sha256") != receipt.get("output_sha256"):
            blockers.append(_finding("VERIFICATION_NOT_CONTENT_BOUND", "verification must bind the same adapter and output", path))
        blockers.extend(
            _independence_findings(
                verification.get("verifier"),
                producers,
                f"{path}.verification.verifier",
                subject,
                trusted_attestations,
            )
        )
        if not _is_sha256(verification.get("receipt_sha256")) or not _nonempty(verification.get("protocol")):
            blockers.append(_finding("VERIFICATION_PROVENANCE_INCOMPLETE", "verification protocol and receipt_sha256 are required", path))
        if status == TruthStatus.FALSE.value:
            blockers.append(_finding("EVIDENCE_VERIFICATION_FALSE", f"{evidence_id} failed typed verification", path))
        elif status == TruthStatus.STALE.value:
            return CheckResult(
                "paperspine5.evidence-registry-check",
                subject,
                TruthStatus.STALE,
                [_finding("EVIDENCE_VERIFICATION_STALE", f"{evidence_id} verification is stale", path)],
            )
        elif status == TruthStatus.UNKNOWN.value:
            unknown_ids.append(evidence_id)
            blockers.append(_finding("EVIDENCE_VERIFICATION_UNKNOWN", f"{evidence_id} is UNKNOWN and therefore fail-closed", path))

        if evidence_type in {"data", "code", "statistics"}:
            recomputation = receipt.get("recomputation")
            if not isinstance(recomputation, Mapping) or recomputation.get("recomputed") is not True:
                blockers.append(_finding("RECOMPUTATION_MISSING", f"{evidence_type} evidence requires a recomputation receipt", path))
            elif (
                recomputation.get("output_sha256") != receipt.get("output_sha256")
                or not _is_sha256(recomputation.get("receipt_sha256"))
                or not _nonempty(recomputation.get("protocol"))
            ):
                blockers.append(_finding("RECOMPUTATION_UNBOUND", "recomputation must bind protocol, receipt, and exact output", path))
        else:
            adapter_outcome = receipt.get("adapter_outcome")
            if not isinstance(adapter_outcome, Mapping) or adapter_outcome.get("status") != status:
                blockers.append(_finding("QUALITATIVE_THEORETICAL_ADAPTER_MISSING", "qualitative/theoretical evidence needs an explicit adapter outcome, including UNKNOWN", path))

    missing_required = sorted(required_ids - observed_ids)
    if missing_required:
        blockers.append(_finding("REQUIRED_EVIDENCE_MISSING", f"required evidence receipts are absent: {missing_required}"))
    if not required_ids:
        blockers.append(_finding("REQUIRED_EVIDENCE_SCOPE_UNKNOWN", "required_evidence_ids must be frozen before verification"))

    status = TruthStatus.FALSE if blockers else TruthStatus.TRUE
    return CheckResult(
        "paperspine5.evidence-registry-check",
        subject,
        status,
        blockers,
        warnings,
        consumed,
        {"evidence_count": len(observed_ids), "unknown_evidence_ids": unknown_ids},
    )


def validate_review_receipt(
    payload: Mapping[str, Any],
    subject: QualitySubject,
    *,
    trusted_attestations: Mapping[str, str] | None = None,
) -> CheckResult:
    """Validate review provenance, frozen inputs, independence, and closure."""

    bound, issue = _bound_subject(payload, subject)
    if not bound:
        return CheckResult(
            "paperspine5.review-receipt-check", subject, TruthStatus.STALE, [issue]
        )
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    reviewer = payload.get("reviewer")
    producers = payload.get("subject_producers")
    producers = producers if isinstance(producers, list) else []
    if not producers:
        blockers.append(_finding("PRODUCER_PROVENANCE_MISSING", "subject_producers must identify every producer", "subject_producers"))
    blockers.extend(
        _independence_findings(
            reviewer, producers, "reviewer", subject, trusted_attestations
        )
    )

    reviewed_hashes = payload.get("reviewed_input_hashes")
    if not isinstance(reviewed_hashes, Mapping) or dict(reviewed_hashes) != dict(subject.input_hashes):
        return CheckResult(
            "paperspine5.review-receipt-check",
            subject,
            TruthStatus.STALE,
            [_finding("REVIEW_INPUT_STALE", "review must bind the exact current input hashes", "reviewed_input_hashes")],
        )
    if payload.get("reviewed_revision_id") != subject.revision_id:
        return CheckResult(
            "paperspine5.review-receipt-check",
            subject,
            TruthStatus.STALE,
            [_finding("REVIEW_REVISION_STALE", "reviewed_revision_id is not current", "reviewed_revision_id")],
        )
    if not _is_sha256(payload.get("rubric_sha256")) or not _is_sha256(payload.get("review_content_sha256")):
        blockers.append(_finding("REVIEW_CONTENT_UNBOUND", "rubric and review content hashes are required"))
    if payload.get("final_decision") not in {"pass", "blocked"}:
        blockers.append(_finding("REVIEW_DECISION_UNKNOWN", "final_decision must be pass or blocked", "final_decision"))
    elif payload.get("final_decision") == "blocked":
        blockers.append(
            _finding(
                "INDEPENDENT_REVIEW_BLOCKED",
                "the independent review did not grant a passing quality decision",
                "final_decision",
            )
        )
    if payload.get("self_signed_final") is not False:
        blockers.append(_finding("SELF_SIGNED_FINAL", "review receipts may not self-sign final readiness", "self_signed_final"))

    objections_raw = payload.get("objections")
    objections = objections_raw if isinstance(objections_raw, list) else []
    for index, objection in enumerate(objections):
        path = f"objections[{index}]"
        if not isinstance(objection, Mapping) or not _nonempty(objection.get("objection_id")):
            blockers.append(_finding("REVIEW_OBJECTION_INVALID", "objection needs a stable ID", path))
            continue
        severity = objection.get("severity")
        if severity not in {"hard", "major", "minor"}:
            blockers.append(_finding("REVIEW_SEVERITY_INVALID", "severity must be hard, major, or minor", path))
        if objection.get("status") not in {"open", "closed", "accepted_risk"}:
            blockers.append(_finding("REVIEW_OBJECTION_STATUS_INVALID", "objection status is invalid", path))
        if severity in {"hard", "major"} and objection.get("status") != "closed":
            blockers.append(_finding("REVIEW_OBJECTION_OPEN", "hard/major objections must be closed by evidence-bearing revision", path))
        if objection.get("status") == "closed" and (
            not _nonempty(objection.get("revision_diff_sha256"))
            or not _is_sha256(objection.get("revision_diff_sha256"))
            or not _nonempty(objection.get("closure_evidence"))
        ):
            blockers.append(_finding("OBJECTION_CLOSURE_UNBOUND", "closed objections need a revision diff hash and closure evidence", path))
    if payload.get("final_decision") == "pass" and any(
        item.get("severity") in {"hard", "major"} and item.get("status") != "closed"
        for item in objections
        if isinstance(item, Mapping)
    ):
        blockers.append(_finding("REVIEW_PASS_WITH_BLOCKER", "review cannot pass with open hard/major objections"))

    status = TruthStatus.FALSE if blockers else TruthStatus.TRUE
    return CheckResult(
        "paperspine5.review-receipt-check",
        subject,
        status,
        blockers,
        warnings,
        dict(subject.input_hashes),
        {"objection_count": len(objections)},
    )


def dependency_closure(
    graph: Mapping[str, Iterable[str]], changed_artifact_ids: Iterable[str]
) -> set[str]:
    """Return changed artifacts plus every transitive dependent artifact."""

    reverse: dict[str, set[str]] = {}
    for dependent, dependencies in graph.items():
        for dependency in dependencies:
            reverse.setdefault(str(dependency), set()).add(str(dependent))
    closure = {str(item) for item in changed_artifact_ids}
    pending = list(closure)
    while pending:
        changed = pending.pop()
        for dependent in reverse.get(changed, set()):
            if dependent not in closure:
                closure.add(dependent)
                pending.append(dependent)
    return closure


def _status_from(value: Any) -> TruthStatus | None:
    try:
        return TruthStatus(str(value))
    except ValueError:
        return None


def _tier_status(statuses: Sequence[TruthStatus]) -> TruthStatus:
    """Non-compensatory status reduction; FALSE has strongest precedence."""

    if any(status is TruthStatus.FALSE for status in statuses):
        return TruthStatus.FALSE
    if any(status is TruthStatus.STALE for status in statuses):
        return TruthStatus.STALE
    if any(status is TruthStatus.UNKNOWN for status in statuses):
        return TruthStatus.UNKNOWN
    return TruthStatus.TRUE


class ReadinessCompiler:
    """Compile typed predicates into a pure, non-compensatory verdict."""

    contract = "paperspine5.readiness-verdict"

    @classmethod
    def compile(
        cls,
        subject: QualitySubject,
        predicates: Sequence[Mapping[str, Any]],
        current_artifacts: Mapping[str, str],
        *,
        obligation_manifest: Mapping[str, Any] | None = None,
        dependency_graph: Mapping[str, Iterable[str]] | None = None,
        changed_artifact_ids: Iterable[str] = (),
        requested_scope: str = "submission_package",
        blockers_by_layer: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        blockers: list[dict[str, str]] = []
        normalized_scope = str(requested_scope or "").strip()
        if normalized_scope not in REQUESTED_SCOPES:
            blockers.append(
                _finding(
                    "REQUESTED_SCOPE_INVALID",
                    f"requested_scope must be one of {list(REQUESTED_SCOPES)}",
                    "requested_scope",
                )
            )
            normalized_scope = "submission_package"
        supplied_layer_blockers = _normalize_layer_blockers(blockers_by_layer)
        manifest_required, manifest_findings = _validate_obligation_manifest(
            obligation_manifest, subject
        )
        blockers.extend(manifest_findings)
        predicate_by_id: dict[str, Mapping[str, Any]] = {}
        invalidated = dependency_closure(dependency_graph or {}, changed_artifact_ids)

        for index, predicate in enumerate(predicates):
            path = f"predicates[{index}]"
            if not isinstance(predicate, Mapping):
                blockers.append(_finding("PREDICATE_INVALID", "predicate must be an object", path))
                continue
            predicate_id = str(predicate.get("predicate_id") or "").strip()
            if not predicate_id or predicate_id in predicate_by_id:
                blockers.append(_finding("PREDICATE_ID_INVALID", "predicate_id must be non-empty and unique", path))
                continue
            predicate_by_id[predicate_id] = predicate

        known_tiers = {
            predicate_id: tier
            for tier, required in REQUIRED_PREDICATES.items()
            for predicate_id in required
        }
        manifest_ids = {
            predicate_id
            for required in manifest_required.values()
            for predicate_id in required
        }
        for predicate_id, predicate in predicate_by_id.items():
            declared_tier = predicate.get("tier")
            expected_tier = known_tiers.get(predicate_id)
            if predicate_id not in manifest_ids:
                blockers.append(
                    _finding(
                        "PREDICATE_NOT_IN_OBLIGATION_MANIFEST",
                        f"{predicate_id} is absent from the frozen target-obligation manifest",
                        f"predicates.{predicate_id}",
                    )
                )
            if expected_tier is not None and declared_tier != expected_tier.value:
                blockers.append(
                    _finding(
                        "PREDICATE_TIER_MISMATCH",
                        f"{predicate_id} must belong to {expected_tier.value}",
                        f"predicates.{predicate_id}.tier",
                    )
                )
            elif expected_tier is None and declared_tier not in {
                tier.value for tier in TIER_ORDER
            }:
                blockers.append(
                    _finding(
                        "PREDICATE_TIER_UNKNOWN",
                        f"dynamic hard predicate {predicate_id} must declare a readiness tier",
                        f"predicates.{predicate_id}.tier",
                    )
                )

        tier_outputs: list[dict[str, Any]] = []
        previous_status = TruthStatus.TRUE
        all_hard_true = True
        for tier in TIER_ORDER:
            required = manifest_required[tier]
            declared_for_tier = {
                predicate_id
                for predicate_id, predicate in predicate_by_id.items()
                if predicate.get("tier") == tier.value
            }
            predicate_ids = required | declared_for_tier
            predicate_outputs: list[dict[str, Any]] = []
            statuses: list[TruthStatus] = []
            for predicate_id in sorted(predicate_ids):
                predicate = predicate_by_id.get(predicate_id)
                status = TruthStatus.UNKNOWN
                reasons: list[str] = []
                if predicate is None:
                    reasons.append("required predicate is missing")
                else:
                    bound, _subject_issue = _bound_subject(predicate, subject)
                    if not bound:
                        status = TruthStatus.STALE
                        reasons.append("predicate subject is stale")
                    else:
                        parsed = _status_from(predicate.get("status"))
                        if parsed is None:
                            status = TruthStatus.UNKNOWN
                            reasons.append("predicate status is invalid")
                        else:
                            status = parsed
                        if predicate.get("hard_blocker") is not True:
                            status = TruthStatus.FALSE
                            reasons.append("required predicate must be explicitly non-compensatory")
                        inputs = predicate.get("artifact_inputs")
                        if not isinstance(inputs, Mapping) or not inputs:
                            status = TruthStatus.UNKNOWN
                            reasons.append("predicate artifact inputs are unbound")
                        else:
                            for artifact_id, expected_hash in inputs.items():
                                artifact_id = str(artifact_id)
                                if artifact_id in invalidated:
                                    status = TruthStatus.STALE
                                    reasons.append(f"dependency invalidated: {artifact_id}")
                                actual_hash = current_artifacts.get(artifact_id)
                                if not _is_sha256(expected_hash) or actual_hash != expected_hash:
                                    status = TruthStatus.STALE
                                    reasons.append(f"artifact hash changed or disappeared: {artifact_id}")
                    if _nonempty(predicate.get("reason")):
                        reasons.append(str(predicate.get("reason")).strip())
                if status is not TruthStatus.TRUE:
                    all_hard_true = False
                    blockers.append(
                        _finding(
                            f"PREDICATE_{status.value.upper()}",
                            f"{predicate_id}: {'; '.join(reasons) or status.value}",
                            f"tiers.{tier.value}.{predicate_id}",
                        )
                    )
                statuses.append(status)
                predicate_outputs.append(
                    {
                        "predicate_id": predicate_id,
                        "status": status.value,
                        "hard_blocker": True,
                        "artifact_inputs": (
                            dict(sorted(predicate.get("artifact_inputs", {}).items()))
                            if isinstance(predicate, Mapping)
                            and isinstance(predicate.get("artifact_inputs"), Mapping)
                            else {}
                        ),
                        "reasons": reasons,
                    }
                )
            tier_status = _tier_status([previous_status, *statuses])
            previous_status = tier_status
            tier_outputs.append(
                {
                    "tier": tier.value,
                    "status": tier_status.value,
                    "ready": tier_status is TruthStatus.TRUE,
                    "predicates": predicate_outputs,
                }
            )

        final_status = previous_status
        predicate_statuses = {
            str(predicate.get("predicate_id")): str(predicate.get("status"))
            for tier in tier_outputs
            for predicate in tier["predicates"]
        }
        compiler_blockers = _dedupe_findings(blockers)
        manuscript_blockers = _dedupe_findings(
            [
                *(
                    finding
                    for finding in compiler_blockers
                    if _finding_applies_to_layer(finding, "manuscript")
                ),
                *supplied_layer_blockers["manuscript"],
            ]
        )
        local_delivery_blockers = _dedupe_findings(
            [
                *(
                    finding
                    for finding in compiler_blockers
                    if _finding_applies_to_layer(finding, "local_delivery")
                ),
                *supplied_layer_blockers["local_delivery"],
            ]
        )
        submission_blockers = _dedupe_findings(
            [*compiler_blockers, *supplied_layer_blockers["submission_package"]]
        )
        external_blockers = _dedupe_findings(
            [
                *submission_blockers,
                *supplied_layer_blockers["external_action"],
                _finding(
                    "EXTERNAL_ACTION_NOT_AUTHORIZED",
                    "readiness never grants upload, submission, publication, or another external action",
                    "external_action_authorized",
                ),
            ]
        )
        tier_ready = {str(item["tier"]): bool(item["ready"]) for item in tier_outputs}
        manuscript_ready = (
            all(
                tier_ready.get(tier, False)
                for tier in ("canonical", "independent_quality", "final_render")
            )
            and not manuscript_blockers
        )
        delivery_ready = (
            manuscript_ready
            and predicate_statuses.get("target_research_valid") == TruthStatus.TRUE.value
            and predicate_statuses.get("target_compliance_valid")
            == TruthStatus.TRUE.value
            and predicate_statuses.get("target_bundle_fresh") == TruthStatus.TRUE.value
            and not local_delivery_blockers
        )
        submission_ready = (
            all_hard_true
            and final_status is TruthStatus.TRUE
            and not submission_blockers
        )
        scoped_complete = {
            "manuscript": manuscript_ready,
            "local_delivery": delivery_ready,
            "submission_package": submission_ready,
        }[normalized_scope]
        if submission_ready:
            overall_status = "ready"
        elif final_status is TruthStatus.FALSE:
            overall_status = "blocked"
        elif final_status is TruthStatus.STALE:
            overall_status = "stale"
        else:
            overall_status = "unknown"
        result = {
            "contract": cls.contract,
            "contract_version": QUALITY_CONTRACT_VERSION,
            "subject": subject.as_dict(),
            "obligation_manifest": dict(obligation_manifest or {}),
            "tiers": tier_outputs,
            "overall_status": overall_status,
            "ready": submission_ready,
            "requested_scope": normalized_scope,
            "manuscript_ready": manuscript_ready,
            "delivery_ready": delivery_ready,
            "submission_ready": submission_ready,
            "is_complete_for_requested_scope": scoped_complete,
            "blockers_by_layer": {
                "manuscript": manuscript_blockers,
                "local_delivery": local_delivery_blockers,
                "submission_package": submission_blockers,
                "external_action": external_blockers,
            },
            "blockers": submission_blockers,
            "invalidated_artifacts": sorted(invalidated),
            "current_artifacts": dict(sorted(current_artifacts.items())),
            "external_action_authorized": False,
        }
        result["verdict_sha256"] = canonical_sha256(result)
        return result


def validate_readiness_verdict_payload(
    payload: Mapping[str, Any],
    subject: QualitySubject,
    *,
    trusted_current_artifacts: Mapping[str, str] | None = None,
) -> CheckResult:
    """Validate an untrusted serialized ReadinessCompiler verdict.

    The function validates both shape and semantics.  A valid BLOCKED verdict
    returns ``CheckResult.ok=True`` with ``details.compiled_ready=False``;
    ``ok`` means the receipt is authentic to the contract, not that the paper
    is ready.
    """

    bound, issue = _bound_subject(payload, subject)
    if not bound:
        return CheckResult(
            "paperspine5.readiness-verdict-check",
            subject,
            TruthStatus.STALE,
            [issue],
        )
    blockers: list[dict[str, str]] = []
    if trusted_current_artifacts is None:
        trusted_current_artifacts = {}
        blockers.append(
            _finding(
                "READINESS_TRUST_ROOT_UNAVAILABLE",
                "kernel-verified current artifact hashes are required",
                "trusted_current_artifacts",
            )
        )
    for artifact_id, artifact_hash in subject.input_hashes.items():
        if trusted_current_artifacts.get(artifact_id) != artifact_hash:
            blockers.append(
                _finding(
                    "READINESS_SUBJECT_NOT_IN_LEDGER",
                    f"quality subject input {artifact_id} is not current in the trusted artifact ledger",
                    "subject.input_hashes",
                )
            )
    manifest_required, manifest_findings = _validate_obligation_manifest(
        payload.get("obligation_manifest"), subject
    )
    blockers.extend(manifest_findings)
    if payload.get("contract") != ReadinessCompiler.contract:
        blockers.append(
            _finding(
                "READINESS_CONTRACT_INVALID",
                "contract must be paperspine5.readiness-verdict",
                "contract",
            )
        )
    if payload.get("contract_version") != QUALITY_CONTRACT_VERSION:
        blockers.append(
            _finding(
                "READINESS_VERSION_INVALID",
                f"contract_version must be {QUALITY_CONTRACT_VERSION}",
                "contract_version",
            )
        )
    if payload.get("external_action_authorized") is not False:
        blockers.append(
            _finding(
                "READINESS_EXTERNAL_AUTHORITY_FORBIDDEN",
                "a readiness verdict can never grant external-action authority",
                "external_action_authorized",
            )
        )

    supplied_hash = payload.get("verdict_sha256")
    unsigned = {key: value for key, value in payload.items() if key != "verdict_sha256"}
    if not _is_sha256(supplied_hash) or supplied_hash != canonical_sha256(unsigned):
        blockers.append(
            _finding(
                "READINESS_VERDICT_HASH_INVALID",
                "verdict_sha256 does not bind the exact serialized verdict",
                "verdict_sha256",
            )
        )

    current_artifacts = payload.get("current_artifacts")
    if not isinstance(current_artifacts, Mapping) or not current_artifacts:
        blockers.append(
            _finding(
                "READINESS_ARTIFACTS_MISSING",
                "current_artifacts must be a non-empty hash mapping",
                "current_artifacts",
            )
        )
        current_artifacts = {}
    else:
        for artifact_id, artifact_hash in current_artifacts.items():
            if not _nonempty(artifact_id) or not _is_sha256(artifact_hash):
                blockers.append(
                    _finding(
                        "READINESS_ARTIFACT_INVALID",
                        f"current artifact {artifact_id!r} is not content-bound",
                        "current_artifacts",
                    )
                )
            elif trusted_current_artifacts.get(str(artifact_id)) != artifact_hash:
                blockers.append(
                    _finding(
                        "READINESS_ARTIFACT_NOT_TRUSTED",
                        f"current artifact {artifact_id} is absent or different in the trusted kernel ledger",
                        "current_artifacts",
                    )
                )

    invalidated_raw = payload.get("invalidated_artifacts")
    if not isinstance(invalidated_raw, list) or any(
        not _nonempty(item) for item in invalidated_raw
    ):
        blockers.append(
            _finding(
                "READINESS_INVALIDATION_INVALID",
                "invalidated_artifacts must be a list of artifact IDs",
                "invalidated_artifacts",
            )
        )
        invalidated: set[str] = set()
    else:
        invalidated = {str(item) for item in invalidated_raw}

    tiers_raw = payload.get("tiers")
    tiers = tiers_raw if isinstance(tiers_raw, list) else []
    if len(tiers) != len(TIER_ORDER):
        blockers.append(
            _finding(
                "READINESS_TIERS_INVALID",
                "verdict must contain exactly the five ordered readiness tiers",
                "tiers",
            )
        )

    previous_status = TruthStatus.TRUE
    all_predicate_ids: set[str] = set()
    all_hard_true = True
    predicate_statuses: dict[str, TruthStatus] = {}
    tier_ready: dict[str, bool] = {}
    for index, expected_tier in enumerate(TIER_ORDER):
        if index >= len(tiers) or not isinstance(tiers[index], Mapping):
            blockers.append(
                _finding(
                    "READINESS_TIER_MISSING",
                    f"tier {expected_tier.value} is missing",
                    f"tiers[{index}]",
                )
            )
            previous_status = TruthStatus.UNKNOWN
            all_hard_true = False
            continue
        tier = tiers[index]
        if tier.get("tier") != expected_tier.value:
            blockers.append(
                _finding(
                    "READINESS_TIER_ORDER_INVALID",
                    f"expected tier {expected_tier.value}",
                    f"tiers[{index}].tier",
                )
            )
        predicates_raw = tier.get("predicates")
        predicates = predicates_raw if isinstance(predicates_raw, list) else []
        statuses: list[TruthStatus] = []
        tier_ids: set[str] = set()
        for predicate_index, predicate in enumerate(predicates):
            path = f"tiers[{index}].predicates[{predicate_index}]"
            if not isinstance(predicate, Mapping):
                blockers.append(
                    _finding("READINESS_PREDICATE_INVALID", "predicate must be an object", path)
                )
                statuses.append(TruthStatus.UNKNOWN)
                all_hard_true = False
                continue
            predicate_id = str(predicate.get("predicate_id") or "").strip()
            if not predicate_id or predicate_id in all_predicate_ids:
                blockers.append(
                    _finding(
                        "READINESS_PREDICATE_ID_INVALID",
                        "predicate_id must be non-empty and globally unique",
                        path,
                    )
                )
            else:
                all_predicate_ids.add(predicate_id)
                tier_ids.add(predicate_id)
            status = _status_from(predicate.get("status"))
            if status is None:
                status = TruthStatus.UNKNOWN
                blockers.append(
                    _finding(
                        "READINESS_PREDICATE_STATUS_INVALID",
                        f"{predicate_id or path} has an invalid truth status",
                        path,
                    )
                )
            statuses.append(status)
            if predicate_id:
                predicate_statuses[predicate_id] = status
            if status is not TruthStatus.TRUE:
                all_hard_true = False
            if predicate.get("hard_blocker") is not True:
                blockers.append(
                    _finding(
                        "READINESS_PREDICATE_COMPENSATORY",
                        f"{predicate_id or path} is not explicitly hard/non-compensatory",
                        path,
                    )
                )
                all_hard_true = False
            inputs = predicate.get("artifact_inputs")
            if not isinstance(inputs, Mapping) or not inputs:
                blockers.append(
                    _finding(
                        "READINESS_PREDICATE_INPUTS_MISSING",
                        f"{predicate_id or path} has no artifact inputs",
                        path,
                    )
                )
                all_hard_true = False
            else:
                for artifact_id, expected_hash in inputs.items():
                    if not _is_sha256(expected_hash) or current_artifacts.get(artifact_id) != expected_hash:
                        blockers.append(
                            _finding(
                                "READINESS_PREDICATE_INPUT_STALE",
                                f"{predicate_id or path} is not bound to current artifact {artifact_id}",
                                path,
                            )
                        )
                    if artifact_id in invalidated and status is not TruthStatus.STALE:
                        blockers.append(
                            _finding(
                                "READINESS_INVALIDATION_IGNORED",
                                f"{predicate_id or path} consumes invalidated artifact {artifact_id} but is not stale",
                                path,
                            )
                        )
        missing_required = sorted(manifest_required[expected_tier] - tier_ids)
        if missing_required:
            blockers.append(
                _finding(
                    "READINESS_REQUIRED_PREDICATE_MISSING",
                    f"{expected_tier.value} lacks required predicates: {missing_required}",
                    f"tiers[{index}].predicates",
                )
            )
            statuses.extend(TruthStatus.UNKNOWN for _ in missing_required)
            all_hard_true = False
        unlicensed = sorted(tier_ids - manifest_required[expected_tier])
        if unlicensed:
            blockers.append(
                _finding(
                    "READINESS_UNLICENSED_PREDICATE",
                    f"{expected_tier.value} includes predicates absent from the frozen obligation manifest: {unlicensed}",
                    f"tiers[{index}].predicates",
                )
            )
        derived_status = _tier_status([previous_status, *statuses])
        if tier.get("status") != derived_status.value or tier.get("ready") is not (
            derived_status is TruthStatus.TRUE
        ):
            blockers.append(
                _finding(
                    "READINESS_TIER_DERIVATION_INVALID",
                    f"{expected_tier.value} status/ready does not match its hard predicates",
                    f"tiers[{index}]",
                )
            )
        previous_status = derived_status
        tier_ready[expected_tier.value] = derived_status is TruthStatus.TRUE

    requested_scope = payload.get("requested_scope")
    if requested_scope not in REQUESTED_SCOPES:
        blockers.append(
            _finding(
                "READINESS_REQUESTED_SCOPE_INVALID",
                f"requested_scope must be one of {list(REQUESTED_SCOPES)}",
                "requested_scope",
            )
        )
        requested_scope = "submission_package"
    raw_layer_blockers = payload.get("blockers_by_layer")
    layer_blockers: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(raw_layer_blockers, Mapping) or set(raw_layer_blockers) != set(
        READINESS_LAYER_KEYS
    ):
        blockers.append(
            _finding(
                "READINESS_LAYER_BLOCKERS_INVALID",
                f"blockers_by_layer must contain exactly {list(READINESS_LAYER_KEYS)}",
                "blockers_by_layer",
            )
        )
        layer_blockers = {key: [] for key in READINESS_LAYER_KEYS}
    else:
        for layer in READINESS_LAYER_KEYS:
            items = raw_layer_blockers.get(layer)
            if not isinstance(items, list) or any(
                not isinstance(item, Mapping)
                or not _nonempty(item.get("code"))
                or not _nonempty(item.get("message"))
                for item in items
            ):
                blockers.append(
                    _finding(
                        "READINESS_LAYER_BLOCKER_ITEMS_INVALID",
                        f"{layer} blockers must be typed code/message objects",
                        f"blockers_by_layer.{layer}",
                    )
                )
                layer_blockers[layer] = []
            else:
                layer_blockers[layer] = [dict(item) for item in items]

    derived_manuscript_ready = (
        all(
            tier_ready.get(tier, False)
            for tier in ("canonical", "independent_quality", "final_render")
        )
        and not layer_blockers["manuscript"]
    )
    derived_delivery_ready = (
        derived_manuscript_ready
        and predicate_statuses.get("target_research_valid") is TruthStatus.TRUE
        and predicate_statuses.get("target_compliance_valid") is TruthStatus.TRUE
        and predicate_statuses.get("target_bundle_fresh") is TruthStatus.TRUE
        and not layer_blockers["local_delivery"]
    )
    derived_submission_ready = (
        all_hard_true
        and previous_status is TruthStatus.TRUE
        and not layer_blockers["submission_package"]
    )
    derived_scoped_complete = {
        "manuscript": derived_manuscript_ready,
        "local_delivery": derived_delivery_ready,
        "submission_package": derived_submission_ready,
    }[requested_scope]
    expected_signals = {
        "manuscript_ready": derived_manuscript_ready,
        "delivery_ready": derived_delivery_ready,
        "submission_ready": derived_submission_ready,
        "is_complete_for_requested_scope": derived_scoped_complete,
    }
    for field_name, expected in expected_signals.items():
        if payload.get(field_name) is not expected:
            blockers.append(
                _finding(
                    "READINESS_LAYER_DERIVATION_INVALID",
                    f"{field_name} does not match the typed tier and scope blockers",
                    field_name,
                )
            )

    if derived_submission_ready:
        derived_overall = "ready"
    elif previous_status is TruthStatus.FALSE:
        derived_overall = "blocked"
    elif previous_status is TruthStatus.STALE:
        derived_overall = "stale"
    else:
        derived_overall = "unknown"
    if payload.get("ready") is not derived_submission_ready or payload.get("overall_status") != derived_overall:
        blockers.append(
            _finding(
                "READINESS_OVERALL_DERIVATION_INVALID",
                "ready/overall_status does not match submission readiness across the five non-compensatory tiers",
            )
        )
    semantic_blockers = payload.get("blockers")
    if not isinstance(semantic_blockers, list) or (
        derived_submission_ready and semantic_blockers
    ) or (not derived_submission_ready and not semantic_blockers):
        blockers.append(
            _finding(
                "READINESS_BLOCKER_REGISTER_INVALID",
                "blocker register must be empty only for READY and non-empty otherwise",
                "blockers",
            )
        )

    return CheckResult(
        "paperspine5.readiness-verdict-check",
        subject,
        TruthStatus.FALSE if blockers else TruthStatus.TRUE,
        blockers,
        consumed_hashes={
            str(key): str(value) for key, value in current_artifacts.items()
        },
        details={
            "compiled_ready": derived_submission_ready,
            "overall_status": derived_overall,
            "requested_scope": requested_scope,
            **expected_signals,
            "external_action_authorized": False,
        },
    )


def predicate_receipt(
    predicate_id: str,
    subject: QualitySubject,
    status: TruthStatus,
    artifact_inputs: Mapping[str, str],
    *,
    reason: str = "",
) -> dict[str, Any]:
    """Build a typed predicate receipt suitable for kernel artifact storage."""

    tier = next(
        (
            candidate.value
            for candidate, required in REQUIRED_PREDICATES.items()
            if predicate_id in required
        ),
        None,
    )
    return {
        "contract": "paperspine5.readiness-predicate",
        "contract_version": QUALITY_CONTRACT_VERSION,
        "predicate_id": predicate_id,
        "tier": tier,
        "subject": subject.as_dict(),
        "status": status.value,
        "hard_blocker": True,
        "artifact_inputs": dict(sorted(artifact_inputs.items())),
        "reason": reason,
    }


def all_required_predicate_ids() -> tuple[str, ...]:
    return tuple(
        sorted({predicate for required in REQUIRED_PREDICATES.values() for predicate in required})
    )
