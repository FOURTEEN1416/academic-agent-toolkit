"""Pure W4/J4--J6 authority and scientific-argument stage services.

The service deliberately has no filesystem, database, network, or runner side
effects.  Runtime research agents supply frozen, content-bound receipts; the
caller persists the returned canonical artifact descriptors through
``ProductKernel`` in the same task revision and CAS command that advances the
runner.  No discipline, journal, or conference preference lives here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .product_contracts import task_scoped_artifact_receipt_id
from .quality_readiness import (
    QualityContractError,
    QualitySubject,
    TruthStatus,
    canonical_sha256,
    identity_provenance_sha256,
    validate_target_research,
)


CONTRACT_VERSION = "1.0"
DEFAULT_PRODUCER_ID = "paperspine5.research-argument-service.1.0"
FROZEN_AUTHORITY_IDS = ("direction_authority", "target_authority", "claim_evidence")
_SHA256_LENGTH = 64

# This is the single executable J6 edge vocabulary.  The public schemas,
# ProductRunner preflight, and semantic compiler all project this mapping; do
# not accept aliases that would be silently ignored by one layer.
CLAIM_RELATION_SIGNATURES: dict[str, tuple[str, str]] = {
    "supported_by": ("claim", "evidence"),
    "supports": ("evidence", "claim"),
    "grounded_in": ("claim", "result"),
    "grounds": ("result", "claim"),
    "cited_support": ("claim", "citation"),
    "cited_context": ("claim", "citation"),
    "supports_context": ("citation", "claim"),
    "limited_by": ("claim", "limitation"),
    "limits": ("limitation", "claim"),
    "warranted_by": ("claim", "warrant"),
    "warrants": ("warrant", "claim"),
    "bounded_by": ("claim", "boundary"),
    "bounds": ("boundary", "claim"),
    "challenged_by": ("claim", "counterevidence"),
    "challenges": ("counterevidence", "claim"),
}
CLAIM_FORWARD_RELATIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "evidence": (("supported_by",), "supports"),
    "result": (("grounded_in",), "grounds"),
    "citation": (("cited_context", "cited_support"), "supports_context"),
    "limitation": (("limited_by",), "limits"),
    "warrant": (("warranted_by",), "warrants"),
    "boundary": (("bounded_by",), "bounds"),
    "counterevidence": (("challenged_by",), "challenges"),
}
CLAIM_NODE_TYPES = frozenset(
    {
        "claim",
        "evidence",
        "result",
        "citation",
        "limitation",
        "warrant",
        "boundary",
        "counterevidence",
    }
)
CLAIM_NODE_STATUSES = frozenset({"verified", "unsupported", "unknown", "none_found"})


class ResearchArgumentContractError(ValueError):
    """Raised when a stage input is not safely interpretable."""


class StageStatus(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    STALE = "stale"


def canonical_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return the only byte representation licensed by an artifact descriptor."""

    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != _SHA256_LENGTH:
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


def _contains_external_authorization(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "external_action_authorized" and item is not False:
                return True
            if _contains_external_authorization(item):
                return True
    elif isinstance(value, list):
        return any(_contains_external_authorization(item) for item in value)
    return False


def _status(blockers: Sequence[Mapping[str, Any]]) -> StageStatus:
    codes = {str(item.get("code") or "") for item in blockers}
    if any("STALE" in code or code.endswith("_CHANGED") for code in codes):
        return StageStatus.STALE
    unknown_prefixes = (
        "OFFLINE_",
        "PAYWALL_",
        "SOURCE_UNAVAILABLE",
        "SOURCE_AVAILABILITY_UNKNOWN",
        "SOURCE_EXPIRY_UNKNOWN",
        "OFFICIAL_AUTHORITY_UNKNOWN",
        "OFFICIAL_HARD_RULE_UNKNOWN",
        "COVERAGE_SCOPE_UNKNOWN",
        "DIRECTION_UNKNOWN",
        "TARGET_UNKNOWN",
        "TARGET_SELECTION_UNKNOWN",
    )
    if any(code.startswith(unknown_prefixes) for code in codes):
        return StageStatus.UNKNOWN
    return StageStatus.FALSE if blockers else StageStatus.TRUE


def _subject(value: QualitySubject | Mapping[str, Any]) -> QualitySubject:
    if isinstance(value, QualitySubject):
        return value
    try:
        return QualitySubject.from_mapping(value)
    except QualityContractError as exc:
        raise ResearchArgumentContractError(str(exc)) from exc


def _sorted_objects(values: Any, key: str) -> list[Any]:
    if not isinstance(values, list):
        return []
    return sorted(
        (dict(item) if isinstance(item, Mapping) else item for item in values),
        key=lambda item: str(item.get(key) or "") if isinstance(item, Mapping) else "",
    )


def _normalized_research_core(payload: Mapping[str, Any]) -> dict[str, Any]:
    coverage = payload.get("coverage")
    normalized_coverage = dict(coverage) if isinstance(coverage, Mapping) else coverage
    if isinstance(normalized_coverage, dict):
        for key in ("required_topics", "covered_topics", "source_ids"):
            if isinstance(normalized_coverage.get(key), list):
                normalized_coverage[key] = sorted(normalized_coverage[key])
    return {
        "direction": payload.get("direction"),
        "target": payload.get("target"),
        "network_status": payload.get("network_status"),
        "research_scope_sha256": payload.get("research_scope_sha256"),
        "producer": payload.get("producer"),
        "sources": _sorted_objects(payload.get("sources"), "source_id"),
        "rules": _sorted_objects(payload.get("rules"), "rule_id"),
        "coverage": normalized_coverage,
        "conflicts": _sorted_objects(payload.get("conflicts", []), "conflict_id"),
    }


def compute_research_snapshot(payload: Mapping[str, Any]) -> str:
    """Hash the order-insensitive frozen research body inspected by a challenger."""

    return canonical_sha256(_normalized_research_core(payload))


def compute_research_scope(
    direction_questions: Sequence[str],
    target: Mapping[str, Any],
    required_topics: Sequence[str],
) -> str:
    return canonical_sha256(
        {
            "direction_questions": sorted(str(item) for item in direction_questions),
            "target": dict(target),
            "required_topics": sorted(str(item) for item in required_topics),
        }
    )


def _normalized_graph_core(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contribution_decision": payload.get("contribution_decision"),
        "nodes": _sorted_objects(payload.get("nodes"), "node_id"),
        "edges": sorted(
            (dict(item) if isinstance(item, Mapping) else item for item in payload.get("edges", [])),
            key=lambda item: (
                str(item.get("from") or "") if isinstance(item, Mapping) else "",
                str(item.get("relation") or "") if isinstance(item, Mapping) else "",
                str(item.get("to") or "") if isinstance(item, Mapping) else "",
            ),
        ),
        "producer": payload.get("producer"),
    }


def compute_claim_graph_snapshot(payload: Mapping[str, Any]) -> str:
    return canonical_sha256(_normalized_graph_core(payload))


def _parse_claim_graph_edges(
    nodes: Mapping[str, Mapping[str, Any]], edges_raw: Any
) -> tuple[set[tuple[str, str, str]], list[dict[str, str]]]:
    """Parse only the exact public J6 edge object and relation vocabulary."""

    findings: list[dict[str, str]] = []
    parsed: set[tuple[str, str, str]] = set()
    if not isinstance(edges_raw, list) or not edges_raw:
        return parsed, [
            _finding(
                "CLAIM_GRAPH_EDGES_MISSING",
                "argument graph edges must be a non-empty array",
                "edges",
            )
        ]
    required_fields = {"from", "relation", "to"}
    licensed_relations = ", ".join(sorted(CLAIM_RELATION_SIGNATURES))
    for index, edge in enumerate(edges_raw):
        path = f"edges[{index}]"
        if not isinstance(edge, Mapping):
            findings.append(_finding("CLAIM_EDGE_INVALID", "edge must be an object", path))
            continue
        observed_fields = set(edge)
        if observed_fields != required_fields:
            missing = sorted(required_fields - observed_fields)
            extra = sorted(observed_fields - required_fields)
            findings.append(
                _finding(
                    "CLAIM_EDGE_FIELDS_INVALID",
                    "edge must contain exactly from, relation, and to; aliases such as "
                    "from_node_id, edge_type, and to_node_id are not accepted "
                    f"(missing={missing}, extra={extra})",
                    path,
                )
            )
            continue
        source = str(edge.get("from") or "")
        relation = str(edge.get("relation") or "")
        target = str(edge.get("to") or "")
        if not source or not target or source not in nodes or target not in nodes:
            findings.append(
                _finding(
                    "CLAIM_EDGE_ENDPOINT_INVALID",
                    "from and to must name existing node_id values",
                    path,
                )
            )
            continue
        signature = CLAIM_RELATION_SIGNATURES.get(relation)
        if signature is None:
            findings.append(
                _finding(
                    "CLAIM_EDGE_RELATION_INVALID",
                    f"relation must be one of: {licensed_relations}",
                    path,
                )
            )
            continue
        actual_signature = (
            str(nodes[source].get("node_type") or ""),
            str(nodes[target].get("node_type") or ""),
        )
        if actual_signature != signature:
            findings.append(
                _finding(
                    "CLAIM_EDGE_DIRECTION_INVALID",
                    f"relation {relation!r} requires {signature[0]} -> {signature[1]}, "
                    f"observed {actual_signature[0] or '<missing>'} -> "
                    f"{actual_signature[1] or '<missing>'}",
                    path,
                )
            )
            continue
        triplet = (source, relation, target)
        if triplet in parsed:
            findings.append(_finding("CLAIM_EDGE_DUPLICATE", "edge must be unique", path))
            continue
        parsed.add(triplet)
    return parsed, findings


def _claim_graph_node_contract_findings(nodes_raw: Any) -> list[dict[str, str]]:
    if not isinstance(nodes_raw, list) or not nodes_raw:
        return [
            _finding(
                "CLAIM_GRAPH_NODES_MISSING",
                "argument graph nodes must be a non-empty array",
                "nodes",
            )
        ]
    required_fields = {
        "node_id",
        "node_type",
        "statement_sha256",
        "source_artifact_id",
        "source_sha256",
        "locator",
        "status",
        "core",
    }
    allowed_fields = required_fields | {"contribution_candidate_id"}
    findings: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, node in enumerate(nodes_raw):
        path = f"nodes[{index}]"
        if not isinstance(node, Mapping):
            findings.append(_finding("CLAIM_NODE_INVALID", "node must be an object", path))
            continue
        observed_fields = set(node)
        missing = sorted(required_fields - observed_fields)
        extra = sorted(observed_fields - allowed_fields)
        if missing or extra:
            findings.append(
                _finding(
                    "CLAIM_NODE_FIELDS_INVALID",
                    "node requires exactly node_id, node_type, statement_sha256, "
                    "source_artifact_id, source_sha256, locator, status, and core; "
                    "contribution_candidate_id is the only optional field "
                    f"(missing={missing}, extra={extra})",
                    path,
                )
            )
            continue
        node_id = str(node.get("node_id") or "")
        if not _nonempty(node_id):
            findings.append(_finding("CLAIM_NODE_ID_INVALID", "node_id is required", path))
        elif node_id in seen:
            findings.append(_finding("CLAIM_NODE_DUPLICATE", "node_id must be unique", path))
        else:
            seen.add(node_id)
        if node.get("node_type") not in CLAIM_NODE_TYPES:
            findings.append(
                _finding("CLAIM_NODE_TYPE_INVALID", "node_type is not licensed", path)
            )
        if not _is_sha256(node.get("statement_sha256")) or not _nonempty(
            node.get("locator")
        ):
            findings.append(
                _finding(
                    "CLAIM_NODE_UNBOUND",
                    "statement_sha256 must be lowercase 64-hex and locator is required",
                    path,
                )
            )
        if not _nonempty(node.get("source_artifact_id")) or not _is_sha256(
            node.get("source_sha256")
        ):
            findings.append(
                _finding(
                    "CLAIM_NODE_SOURCE_BINDING_INVALID",
                    "source_artifact_id and lowercase 64-hex source_sha256 are required",
                    path,
                )
            )
        if node.get("status") not in CLAIM_NODE_STATUSES:
            findings.append(
                _finding("CLAIM_NODE_STATUS_INVALID", "node status is invalid", path)
            )
        if not isinstance(node.get("core"), bool):
            findings.append(
                _finding("CLAIM_NODE_CORE_INVALID", "core must be a boolean", path)
            )
    return findings


def validate_claim_graph_edge_contract(nodes_raw: Any, edges_raw: Any) -> list[dict[str, str]]:
    """Validate the J6 node/edge wire shape before a Runner transaction."""

    findings = _claim_graph_node_contract_findings(nodes_raw)
    if not isinstance(nodes_raw, list):
        return findings
    nodes = {
        str(node.get("node_id")): node
        for node in nodes_raw
        if isinstance(node, Mapping) and _nonempty(node.get("node_id"))
    }
    findings.extend(_parse_claim_graph_edges(nodes, edges_raw)[1])
    return findings


def _identity_findings(
    identity: Any,
    path: str,
    subject: QualitySubject,
    trusted_attestations: Mapping[str, str],
) -> list[dict[str, str]]:
    if not isinstance(identity, Mapping):
        return [_finding("IDENTITY_INVALID", "identity must be an object", path)]
    required = ("principal_id", "session_id", "run_id", "independence_group")
    if any(not _nonempty(identity.get(key)) for key in required):
        return [_finding("IDENTITY_INCOMPLETE", "identity provenance fields are incomplete", path)]
    expected = identity_provenance_sha256(identity)
    if identity.get("provenance_sha256") != expected:
        return [_finding("IDENTITY_PROVENANCE_INVALID", "provenance hash does not recompute", path)]
    attestation = identity.get("attestation_input_id")
    if not _nonempty(attestation):
        return [_finding("IDENTITY_ATTESTATION_MISSING", "attestation_input_id is required", path)]
    if subject.input_hashes.get(str(attestation)) != expected:
        return [_finding("IDENTITY_NOT_ATTESTED", "identity is not bound to this revision", path)]
    if trusted_attestations.get(str(attestation)) != expected:
        return [_finding("IDENTITY_ATTESTATION_UNTRUSTED", "kernel identity attestation is missing", path)]
    return []


def _independence_findings(reviewer: Any, producer: Any, path: str) -> list[dict[str, str]]:
    if not isinstance(reviewer, Mapping) or not isinstance(producer, Mapping):
        return []
    shared = [
        key
        for key in ("principal_id", "session_id", "run_id", "independence_group")
        if reviewer.get(key) == producer.get(key)
    ]
    if reviewer.get("provenance_sha256") == producer.get("provenance_sha256"):
        shared.append("provenance_sha256")
    if shared:
        return [
            _finding(
                "REVIEW_NOT_INDEPENDENT",
                f"reviewer shares immutable producer provenance: {sorted(set(shared))}",
                path,
            )
        ]
    return []


def _trusted_hash_findings(
    subject: QualitySubject,
    trusted_artifacts: Mapping[str, str],
    artifact_ids: Iterable[str],
    path: str,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for artifact_id in sorted(set(artifact_ids)):
        expected = subject.input_hashes.get(artifact_id)
        if expected is None:
            findings.append(
                _finding("ARTIFACT_NOT_IN_SUBJECT", f"{artifact_id} is not revision-bound", path)
            )
        elif trusted_artifacts.get(artifact_id) != expected:
            findings.append(
                _finding(
                    "ARTIFACT_LEDGER_MISMATCH",
                    f"{artifact_id} is absent or different in the same-revision kernel ledger",
                    path,
                )
            )
    return findings


def _descriptor(
    *,
    artifact_id: str,
    artifact_type: str,
    subject: QualitySubject,
    payload: Mapping[str, Any],
    product_build_id: str,
    stage: str,
    producer_id: str,
) -> dict[str, Any]:
    if _contains_external_authorization(payload):
        raise ResearchArgumentContractError("stage payload cannot authorize external actions")
    data = canonical_payload_bytes(payload)
    return {
        "contract": "paperspine5.stage-artifact-descriptor",
        "schema_version": CONTRACT_VERSION,
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "subject": subject.as_dict(),
        "payload": dict(payload),
        "payload_sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "authority": {"kind": "research-argument-service", "producer_id": producer_id},
        "metadata": {
            "product_build_id": product_build_id,
            "stage": stage,
            "encoding": "canonical-json-newline.v1",
            "service_version": CONTRACT_VERSION,
        },
        "external_action_authorized": False,
    }


def validate_stage_artifact_descriptor(
    descriptor: Mapping[str, Any],
    *,
    expected_subject: QualitySubject | Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Validate an in-memory descriptor before its bytes are materialized."""

    findings: list[dict[str, str]] = []
    if descriptor.get("contract") != "paperspine5.stage-artifact-descriptor" or descriptor.get(
        "schema_version"
    ) != CONTRACT_VERSION:
        findings.append(_finding("DESCRIPTOR_CONTRACT_INVALID", "descriptor contract/version is invalid"))
    try:
        observed = QualitySubject.from_mapping(descriptor.get("subject", {}))
    except QualityContractError as exc:
        findings.append(_finding("DESCRIPTOR_SUBJECT_INVALID", str(exc), "subject"))
        return findings
    if expected_subject is not None and observed != _subject(expected_subject):
        findings.append(_finding("DESCRIPTOR_SUBJECT_STALE", "descriptor subject is not current", "subject"))
    payload = descriptor.get("payload")
    if not isinstance(payload, Mapping):
        findings.append(_finding("DESCRIPTOR_PAYLOAD_INVALID", "payload must be an object", "payload"))
        return findings
    data = canonical_payload_bytes(payload)
    if descriptor.get("payload_sha256") != hashlib.sha256(data).hexdigest():
        findings.append(_finding("DESCRIPTOR_HASH_INVALID", "payload_sha256 does not bind payload", "payload_sha256"))
    if descriptor.get("size_bytes") != len(data):
        findings.append(_finding("DESCRIPTOR_SIZE_INVALID", "size_bytes does not bind payload", "size_bytes"))
    if descriptor.get("external_action_authorized") is not False or _contains_external_authorization(payload):
        findings.append(_finding("EXTERNAL_ACTION_FORBIDDEN", "stage artifacts cannot authorize external actions"))
    return findings


def receipt_for_descriptor(
    descriptor: Mapping[str, Any],
    *,
    path: str,
    receipt_id: str | None = None,
) -> dict[str, Any]:
    """Project a validated descriptor into a ProductKernel ArtifactReceipt."""

    findings = validate_stage_artifact_descriptor(descriptor)
    if findings:
        raise ResearchArgumentContractError(
            "invalid stage artifact descriptor: " + ", ".join(item["code"] for item in findings)
        )
    artifact_id = str(descriptor["artifact_id"])
    subject = descriptor["subject"]
    default_receipt_id = task_scoped_artifact_receipt_id(
        task_id=str(subject["task_id"]),
        revision_id=str(subject["revision_id"]),
        artifact_id=artifact_id,
        artifact_type=str(descriptor["artifact_type"]),
        content_sha256=str(descriptor["payload_sha256"]),
    )
    return {
        "contract": "paperspine5.artifact-receipt",
        "schema_version": "1.0",
        "receipt_id": receipt_id or default_receipt_id,
        "artifact_id": artifact_id,
        "artifact_type": descriptor["artifact_type"],
        "path": path,
        "sha256": descriptor["payload_sha256"],
        "size_bytes": descriptor["size_bytes"],
        "subject": descriptor["subject"],
        "authority": descriptor["authority"],
        "metadata": descriptor["metadata"],
        "external_action_authorized": False,
    }


def _result(
    *,
    stage: str,
    subject: QualitySubject,
    blockers: Sequence[Mapping[str, str]],
    warnings: Sequence[Mapping[str, str]],
    artifacts: Sequence[Mapping[str, Any]],
    next_stage: str,
    invalidated_artifacts: Sequence[str] = (),
    frozen_authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract": "paperspine5.stage-service-result",
        "schema_version": CONTRACT_VERSION,
        "stage": stage,
        "status": _status(blockers).value,
        "task_id": subject.task_id,
        "revision_id": subject.revision_id,
        "subject": subject.as_dict(),
        "blockers": list(blockers),
        "warnings": list(warnings),
        "artifacts": list(artifacts),
        "next_stage": next_stage,
        "invalidated_artifacts": sorted(set(invalidated_artifacts)),
        "frozen_authority": dict(frozen_authority) if frozen_authority else None,
        "external_action_authorized": False,
    }
    payload["result_sha256"] = canonical_sha256(payload)
    return payload


@dataclass(frozen=True)
class ResearchArgumentStageService:
    """No-I/O service boundary consumed by ProductRunner's future J4--J6 handlers."""

    product_build_id: str
    producer_id: str = DEFAULT_PRODUCER_ID

    def __post_init__(self) -> None:
        if not _nonempty(self.product_build_id) or not _nonempty(self.producer_id):
            raise ResearchArgumentContractError("product_build_id and producer_id are required")

    def accept_frozen_research(
        self,
        subject: QualitySubject | Mapping[str, Any],
        frozen_research: Mapping[str, Any],
        *,
        as_of_date: str,
        trusted_artifacts: Mapping[str, str],
        trusted_attestations: Mapping[str, str],
    ) -> dict[str, Any]:
        """J4: accept runtime research only after authority and freshness checks."""

        current = _subject(subject)
        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        if frozen_research.get("contract") != "paperspine5.runtime-research-bundle" or frozen_research.get(
            "schema_version"
        ) != CONTRACT_VERSION:
            blockers.append(_finding("RESEARCH_CONTRACT_INVALID", "runtime research contract/version is invalid"))
        if frozen_research.get("subject") != current.as_dict():
            blockers.append(_finding("RESEARCH_SUBJECT_STALE", "research subject is not current", "subject"))
        try:
            as_of = date.fromisoformat(as_of_date)
        except (TypeError, ValueError):
            blockers.append(_finding("AS_OF_DATE_INVALID", "as_of_date must be an ISO calendar date", "as_of_date"))
            as_of = None

        direction = frozen_research.get("direction")
        if not isinstance(direction, Mapping) or not _nonempty(direction.get("statement")):
            blockers.append(_finding("DIRECTION_UNKNOWN", "direction statement is required", "direction"))
        questions = direction.get("questions", []) if isinstance(direction, Mapping) else []
        boundaries = direction.get("boundaries", []) if isinstance(direction, Mapping) else []
        if not isinstance(questions, list) or not questions or any(not _nonempty(item) for item in questions):
            blockers.append(_finding("DIRECTION_SCOPE_UNKNOWN", "direction questions must be explicit", "direction.questions"))
            questions = []
        if not isinstance(boundaries, list) or not boundaries or any(
            not _nonempty(item) for item in boundaries
        ):
            blockers.append(_finding("DIRECTION_BOUNDARY_UNKNOWN", "direction boundaries must be explicit", "direction.boundaries"))
        target = frozen_research.get("target")
        coverage = frozen_research.get("coverage")
        required_topics = coverage.get("required_topics", []) if isinstance(coverage, Mapping) else []
        if not isinstance(target, Mapping):
            blockers.append(_finding("TARGET_UNKNOWN", "target profile must be explicit, including unknown state", "target"))
            target = {}
        elif target.get("status") == "unknown":
            blockers.append(_finding("TARGET_SELECTION_UNKNOWN", "a target has not yet been selected", "target.status"))
        elif target.get("status") != "known":
            blockers.append(_finding("TARGET_STATUS_INVALID", "target.status must be known or unknown", "target.status"))
        if frozen_research.get("network_status") not in {"online", "offline"}:
            blockers.append(_finding("NETWORK_STATUS_UNKNOWN", "network_status must be online or offline", "network_status"))
        scope_hash = compute_research_scope(questions, target, required_topics)
        if frozen_research.get("research_scope_sha256") != scope_hash:
            blockers.append(_finding("RESEARCH_SCOPE_HASH_INVALID", "research scope hash does not recompute", "research_scope_sha256"))
        if current.input_hashes.get("research_scope") != scope_hash:
            blockers.append(_finding("RESEARCH_SCOPE_STALE", "research scope is not bound to this revision", "research_scope_sha256"))

        snapshot = compute_research_snapshot(frozen_research)
        if frozen_research.get("research_snapshot_sha256") != snapshot:
            blockers.append(_finding("RESEARCH_SNAPSHOT_HASH_INVALID", "research snapshot does not recompute", "research_snapshot_sha256"))

        source_ids: list[str] = []
        sources = frozen_research.get("sources")
        if isinstance(sources, list):
            for index, source in enumerate(sources):
                if not isinstance(source, Mapping):
                    continue
                source_id = str(source.get("source_id") or "")
                if source_id:
                    source_ids.append(f"source:{source_id}")
                availability = source.get("availability")
                access_basis = source.get("access_basis")
                path = f"sources[{index}]"
                if source.get("lane") == "exemplar_style" and source.get("authority") != "advisory":
                    blockers.append(_finding("ADVISORY_ESCALATED", "exemplars can only be advisory", path))
                if availability in {"paywalled", "unavailable"}:
                    blockers.append(
                        _finding(
                            "PAYWALL_SOURCE_UNAVAILABLE" if availability == "paywalled" else "SOURCE_UNAVAILABLE",
                            "source bytes were not lawfully frozen; authority remains unknown",
                            path,
                        )
                    )
                elif availability == "lawful_frozen_cache":
                    if access_basis not in {"user_provided", "lawful_cache"}:
                        blockers.append(_finding("SOURCE_ACCESS_BASIS_INVALID", "frozen cache requires a lawful access basis", path))
                    else:
                        warnings.append(_finding("SOURCE_FROM_FROZEN_CACHE", "authority uses a lawful frozen snapshot", path))
                elif availability != "accessible":
                    blockers.append(_finding("SOURCE_AVAILABILITY_UNKNOWN", "source availability must be explicit", path))
                if as_of is not None:
                    try:
                        effective = date.fromisoformat(str(source.get("effective_date")))
                    except ValueError:
                        effective = None
                    if effective is not None and effective > as_of:
                        blockers.append(_finding("SOURCE_NOT_YET_EFFECTIVE", "source is not effective as of this run", path))
                    valid_until_raw = source.get("valid_until")
                    if source.get("authority") == "official_hard" and not _nonempty(valid_until_raw):
                        blockers.append(_finding("SOURCE_EXPIRY_UNKNOWN", "official-hard source requires valid_until", path))
                    elif _nonempty(valid_until_raw):
                        try:
                            valid_until = date.fromisoformat(str(valid_until_raw))
                        except ValueError:
                            blockers.append(_finding("SOURCE_EXPIRY_INVALID", "valid_until must be an ISO date", path))
                        else:
                            if as_of > valid_until:
                                blockers.append(_finding("SOURCE_STALE", "source snapshot expired before as_of_date", path))
                if frozen_research.get("network_status") == "offline" and availability not in {
                    "accessible",
                    "lawful_frozen_cache",
                }:
                    blockers.append(_finding("OFFLINE_SOURCE_UNAVAILABLE", "offline run lacks a lawful frozen source", path))
        blockers.extend(_trusted_hash_findings(current, trusted_artifacts, source_ids, "sources"))

        quality = validate_target_research(
            frozen_research,
            current,
            trusted_attestations=trusted_attestations,
        )
        blockers.extend(quality.blockers)
        warnings.extend(quality.warnings)
        if quality.status is TruthStatus.STALE and not any("STALE" in item["code"] for item in blockers):
            blockers.append(_finding("RESEARCH_SUBJECT_STALE", "quality validator found a stale subject"))
        if frozen_research.get("external_action_authorized") is not False or _contains_external_authorization(
            frozen_research
        ):
            blockers.append(_finding("EXTERNAL_ACTION_FORBIDDEN", "research cannot authorize external actions"))
        if blockers:
            return _result(
                stage="J4",
                subject=current,
                blockers=blockers,
                warnings=warnings,
                artifacts=[],
                next_stage="J4",
            )

        direction_payload = {
            "contract": "paperspine5.direction-authority",
            "schema_version": CONTRACT_VERSION,
            "subject": current.as_dict(),
            "direction": direction,
            "research_scope_sha256": scope_hash,
            "research_snapshot_sha256": snapshot,
            "source_ids": sorted(source_ids),
            "external_action_authorized": False,
        }
        target_payload = {
            "contract": "paperspine5.target-authority",
            "schema_version": CONTRACT_VERSION,
            "subject": current.as_dict(),
            "target": target,
            "as_of_date": as_of_date,
            "official_hard_rules": [
                item
                for item in frozen_research.get("rules", [])
                if item.get("kind") == "hard" and item.get("enforcement") == "hard"
            ],
            "advisory_rules": [item for item in frozen_research.get("rules", []) if item.get("kind") == "advisory"],
            "coverage": coverage,
            "research_snapshot_sha256": snapshot,
            "external_action_authorized": False,
        }
        descriptors = [
            _descriptor(
                artifact_id="direction_authority",
                artifact_type="authority.direction-receipt",
                subject=current,
                payload=direction_payload,
                product_build_id=self.product_build_id,
                stage="J4",
                producer_id=self.producer_id,
            ),
            _descriptor(
                artifact_id="target_authority",
                artifact_type="authority.target-receipt",
                subject=current,
                payload=target_payload,
                product_build_id=self.product_build_id,
                stage="J4",
                producer_id=self.producer_id,
            ),
        ]
        return _result(
            stage="J4",
            subject=current,
            blockers=[],
            warnings=warnings,
            artifacts=descriptors,
            next_stage="J5",
        )

    def decide_contribution(
        self,
        subject: QualitySubject | Mapping[str, Any],
        decision: Mapping[str, Any],
        *,
        trusted_artifacts: Mapping[str, str],
        trusted_attestations: Mapping[str, str],
        trusted_delegation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """J5: use author confirmation or a host-verified local delegation grant."""

        current = _subject(subject)
        blockers: list[dict[str, str]] = []
        if decision.get("contract") != "paperspine5.contribution-boundary-decision" or decision.get(
            "schema_version"
        ) != CONTRACT_VERSION:
            blockers.append(_finding("CONTRIBUTION_CONTRACT_INVALID", "decision contract/version is invalid"))
        if decision.get("subject") != current.as_dict():
            blockers.append(_finding("CONTRIBUTION_SUBJECT_STALE", "decision subject is not current", "subject"))
        required_inputs = ["direction_authority", "target_authority", "materials.source-ledger"]
        blockers.extend(_trusted_hash_findings(current, trusted_artifacts, required_inputs, "authority"))
        bindings = decision.get("authority_bindings")
        if not isinstance(bindings, Mapping):
            blockers.append(_finding("AUTHORITY_BINDINGS_MISSING", "direction, target, and material authority bindings are required"))
        else:
            for artifact_id in required_inputs:
                if bindings.get(artifact_id) != current.input_hashes.get(artifact_id):
                    blockers.append(_finding("AUTHORITY_BINDING_STALE", f"{artifact_id} binding is stale", "authority_bindings"))
        delegated = isinstance(trusted_delegation, Mapping)
        if delegated:
            if (
                trusted_delegation.get("contract")
                != "paperspine5.verified-local-delegation"
                or trusted_delegation.get("task_id") != current.task_id
                or trusted_delegation.get("run_contract_sha256")
                != current.input_hashes.get("runner.run-contract")
                or trusted_delegation.get("material_snapshot_sha256")
                != current.input_hashes.get("materials.source-ledger")
                or decision.get("author_identity") is not None
            ):
                blockers.append(
                    _finding(
                        "LOCAL_DELEGATION_UNTRUSTED",
                        "delegated contribution must be host-bound to the current run contract and material snapshot",
                    )
                )
        else:
            blockers.extend(
                _identity_findings(
                    decision.get("author_identity"),
                    "author_identity",
                    current,
                    trusted_attestations,
                )
            )
        if decision.get("override_blockers") is True:
            blockers.append(_finding("AUTHOR_OVERRIDE_FORBIDDEN", "authors cannot override factual, policy, or evidence blockers"))

        candidates = decision.get("candidates")
        choices = decision.get("decisions")
        if not isinstance(candidates, list) or not candidates:
            blockers.append(_finding("CONTRIBUTION_CANDIDATES_MISSING", "candidate contributions/boundaries are required"))
            candidates = []
        if not isinstance(choices, list):
            blockers.append(_finding("CONTRIBUTION_DECISIONS_MISSING", "every candidate needs one decision"))
            choices = []
        candidate_by_id: dict[str, Mapping[str, Any]] = {}
        for index, candidate in enumerate(candidates):
            path = f"candidates[{index}]"
            if not isinstance(candidate, Mapping) or not _nonempty(candidate.get("candidate_id")):
                blockers.append(_finding("CANDIDATE_ID_INVALID", "candidate_id is required", path))
                continue
            candidate_id = str(candidate["candidate_id"])
            if candidate_id in candidate_by_id:
                blockers.append(_finding("CANDIDATE_ID_DUPLICATE", "candidate_id must be unique", path))
                continue
            candidate_by_id[candidate_id] = candidate
            if candidate.get("kind") not in {"contribution", "motivation", "boundary", "limitation"}:
                blockers.append(_finding("CANDIDATE_KIND_INVALID", "candidate kind is invalid", path))
            if not _nonempty(candidate.get("statement")):
                blockers.append(_finding("CANDIDATE_STATEMENT_MISSING", "candidate statement is required", path))
            if candidate.get("author_authority") not in {
                "project_fact",
                "author_intent",
                "external_fact",
                "target_policy",
                "scientific_truth",
            }:
                blockers.append(_finding("CANDIDATE_AUTHORITY_INVALID", "author_authority is invalid", path))
            artifact_ids = (
                set(candidate.get("supporting_artifact_ids", []))
                | set(candidate.get("counterevidence_artifact_ids", []))
                | set(candidate.get("direct_competitor_source_ids", []))
            )
            blockers.extend(_trusted_hash_findings(current, trusted_artifacts, artifact_ids, path))
            if candidate.get("kind") in {"contribution", "motivation"}:
                required_argument_fields = [
                    "supporting_artifact_ids",
                    "counterevidence_artifact_ids",
                    "limitation_ids",
                ]
                # Descriptive project facts and authorial writing intent do not
                # become comparative claims merely because they pass through
                # J5.  Keep the old fail-closed behavior unless the candidate
                # explicitly declares that it makes no comparative claim.
                if candidate.get("comparative_claim") is not False:
                    required_argument_fields.append("direct_competitor_source_ids")
                for field in required_argument_fields:
                    if not isinstance(candidate.get(field), list) or not candidate.get(field):
                        blockers.append(_finding("CONTRIBUTION_ARGUMENT_INCOMPLETE", f"{field} is required", f"{path}.{field}"))
                if not _nonempty(candidate.get("boundary_statement")):
                    blockers.append(_finding("CONTRIBUTION_BOUNDARY_MISSING", "a falsifiable boundary is required", path))
        seen: set[str] = set()
        accepted: list[dict[str, Any]] = []
        for candidate_id, candidate in candidate_by_id.items():
            if candidate.get("kind") not in {"contribution", "motivation"}:
                continue
            for limitation_id in candidate.get("limitation_ids", []):
                limitation = candidate_by_id.get(str(limitation_id))
                if limitation is None:
                    if trusted_artifacts.get(str(limitation_id)) != current.input_hashes.get(
                        str(limitation_id)
                    ):
                        blockers.append(
                            _finding(
                                "CONTRIBUTION_LIMITATION_UNBOUND",
                                f"{candidate_id} cites an absent limitation: {limitation_id}",
                                "candidates",
                            )
                        )
                elif limitation.get("kind") != "limitation":
                    blockers.append(
                        _finding(
                            "CONTRIBUTION_LIMITATION_INVALID",
                            f"{limitation_id} is not a limitation candidate",
                            "candidates",
                        )
                    )
        for index, choice in enumerate(choices):
            path = f"decisions[{index}]"
            if not isinstance(choice, Mapping):
                blockers.append(_finding("CONTRIBUTION_DECISION_INVALID", "decision must be an object", path))
                continue
            candidate_id = str(choice.get("candidate_id") or "")
            candidate = candidate_by_id.get(candidate_id)
            if not candidate or candidate_id in seen:
                blockers.append(_finding("CONTRIBUTION_DECISION_INVALID", "decision candidate is missing or duplicated", path))
                continue
            seen.add(candidate_id)
            selected = choice.get("choice")
            if selected not in {"accept", "revise", "reject"}:
                blockers.append(_finding("CONTRIBUTION_CHOICE_INVALID", "choice must be accept, revise, or reject", path))
                continue
            if not _nonempty(choice.get("reason")):
                blockers.append(_finding("CONTRIBUTION_REASON_MISSING", "decision reason is required", path))
            if selected in {"accept", "revise"}:
                allowed_authorities = {"project_fact"} if delegated else {
                    "project_fact",
                    "author_intent",
                }
                if candidate.get("author_authority") not in allowed_authorities:
                    blockers.append(
                        _finding(
                            "AUTHOR_AUTHORITY_EXCEEDED",
                            (
                                "local delegation may select only evidence-backed project facts"
                                if delegated
                                else "authors may confirm project facts or intent, not external truth or target policy"
                            ),
                            path,
                        )
                    )
                statement = choice.get("revised_statement") if selected == "revise" else candidate.get("statement")
                if not _nonempty(statement):
                    blockers.append(_finding("CONTRIBUTION_STATEMENT_MISSING", "accepted statement is empty", path))
                else:
                    accepted.append({"candidate_id": candidate_id, "statement": statement, "choice": selected})
        missing = sorted(set(candidate_by_id) - seen)
        if missing:
            blockers.append(_finding("CONTRIBUTION_DECISION_INCOMPLETE", f"undecided candidates: {missing}"))
        if not accepted and not blockers:
            blockers.append(_finding("CONTRIBUTION_NOT_CONFIRMED", "no bounded project contribution was confirmed"))
        if not _nonempty(decision.get("confirmed_at")):
            blockers.append(_finding("CONTRIBUTION_CONFIRMATION_TIME_MISSING", "confirmed_at is required"))
        if decision.get("external_action_authorized") is not False or _contains_external_authorization(
            decision
        ):
            blockers.append(_finding("EXTERNAL_ACTION_FORBIDDEN", "contribution decision cannot authorize external actions"))
        if blockers:
            return _result(
                stage="J5", subject=current, blockers=blockers, warnings=[], artifacts=[], next_stage="J5"
            )
        payload = {
            **dict(decision),
            "accepted": accepted,
            "decision_snapshot_sha256": canonical_sha256(
                {"candidates": candidates, "decisions": choices, "authority_bindings": bindings}
            ),
            "external_action_authorized": False,
        }
        descriptor = _descriptor(
            artifact_id="contribution_boundary_decision",
            artifact_type="authority.contribution-boundary-decision",
            subject=current,
            payload=payload,
            product_build_id=self.product_build_id,
            stage="J5",
            producer_id=self.producer_id,
        )
        return _result(
            stage="J5", subject=current, blockers=[], warnings=[], artifacts=[descriptor], next_stage="J6"
        )

    def prepare_contribution_candidates(
        self,
        subject: QualitySubject | Mapping[str, Any],
        preparation: Mapping[str, Any],
        *,
        trusted_artifacts: Mapping[str, str],
    ) -> dict[str, Any]:
        """J5 phase 1: validate host candidates without accepting a user decision.

        The returned descriptor is safe to show in Product Web.  It deliberately
        contains no ``decisions``, ``author_identity`` or ``confirmed_at``; those
        values exist only after the authenticated browser confirmation phase.
        """

        current = _subject(subject)
        blockers: list[dict[str, str]] = []
        if preparation.get(
            "contract"
        ) != "paperspine5.contribution-candidate-preparation" or preparation.get(
            "schema_version"
        ) != CONTRACT_VERSION:
            blockers.append(
                _finding(
                    "CONTRIBUTION_PREPARATION_CONTRACT_INVALID",
                    "candidate preparation contract/version is invalid",
                )
            )
        if preparation.get("subject") != current.as_dict():
            blockers.append(
                _finding(
                    "CONTRIBUTION_PREPARATION_SUBJECT_STALE",
                    "candidate preparation subject is not current",
                    "subject",
                )
            )
        forbidden = sorted(
            set(preparation)
            & {"decisions", "author_identity", "confirmed_at", "override_blockers"}
        )
        if forbidden:
            blockers.append(
                _finding(
                    "CONTRIBUTION_PREPARATION_IMPERSONATES_CONFIRMATION",
                    f"phase-1 candidate preparation cannot carry: {forbidden}",
                )
            )
        required_inputs = [
            "direction_authority",
            "target_authority",
            "materials.source-ledger",
        ]
        blockers.extend(
            _trusted_hash_findings(
                current, trusted_artifacts, required_inputs, "authority_bindings"
            )
        )
        bindings = preparation.get("authority_bindings")
        if not isinstance(bindings, Mapping):
            blockers.append(
                _finding(
                    "AUTHORITY_BINDINGS_MISSING",
                    "direction, target, and material authority bindings are required",
                )
            )
        else:
            for artifact_id in required_inputs:
                if bindings.get(artifact_id) != current.input_hashes.get(artifact_id):
                    blockers.append(
                        _finding(
                            "AUTHORITY_BINDING_STALE",
                            f"{artifact_id} binding is stale",
                            "authority_bindings",
                        )
                    )

        candidates = preparation.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            blockers.append(
                _finding(
                    "CONTRIBUTION_CANDIDATES_MISSING",
                    "candidate contributions/boundaries are required",
                )
            )
            candidates = []
        candidate_by_id: dict[str, Mapping[str, Any]] = {}
        for index, candidate in enumerate(candidates):
            path = f"candidates[{index}]"
            if not isinstance(candidate, Mapping) or not _nonempty(
                candidate.get("candidate_id")
            ):
                blockers.append(
                    _finding("CANDIDATE_ID_INVALID", "candidate_id is required", path)
                )
                continue
            candidate_id = str(candidate["candidate_id"])
            if candidate_id in candidate_by_id:
                blockers.append(
                    _finding(
                        "CANDIDATE_ID_DUPLICATE",
                        "candidate_id must be unique",
                        path,
                    )
                )
                continue
            candidate_by_id[candidate_id] = candidate
            if candidate.get("kind") not in {
                "contribution",
                "motivation",
                "boundary",
                "limitation",
            }:
                blockers.append(
                    _finding("CANDIDATE_KIND_INVALID", "candidate kind is invalid", path)
                )
            if not _nonempty(candidate.get("statement")):
                blockers.append(
                    _finding(
                        "CANDIDATE_STATEMENT_MISSING",
                        "candidate statement is required",
                        path,
                    )
                )
            if candidate.get("author_authority") not in {
                "project_fact",
                "author_intent",
                "external_fact",
                "target_policy",
                "scientific_truth",
            }:
                blockers.append(
                    _finding(
                        "CANDIDATE_AUTHORITY_INVALID",
                        "candidate author authority is invalid",
                        path,
                    )
                )
            artifact_ids = (
                set(candidate.get("supporting_artifact_ids", []))
                | set(candidate.get("counterevidence_artifact_ids", []))
                | set(candidate.get("direct_competitor_source_ids", []))
            )
            blockers.extend(
                _trusted_hash_findings(current, trusted_artifacts, artifact_ids, path)
            )
            if candidate.get("kind") in {"contribution", "motivation"}:
                required_argument_fields = [
                    "supporting_artifact_ids",
                    "counterevidence_artifact_ids",
                    "limitation_ids",
                ]
                if candidate.get("comparative_claim") is not False:
                    required_argument_fields.append("direct_competitor_source_ids")
                for field in required_argument_fields:
                    if not isinstance(candidate.get(field), list) or not candidate.get(
                        field
                    ):
                        blockers.append(
                            _finding(
                                "CONTRIBUTION_ARGUMENT_INCOMPLETE",
                                f"{field} is required",
                                f"{path}.{field}",
                            )
                        )
                if not _nonempty(candidate.get("boundary_statement")):
                    blockers.append(
                        _finding(
                            "CONTRIBUTION_BOUNDARY_MISSING",
                            "a falsifiable boundary is required",
                            path,
                        )
                    )
        for candidate_id, candidate in candidate_by_id.items():
            if candidate.get("kind") not in {"contribution", "motivation"}:
                continue
            for limitation_id in candidate.get("limitation_ids", []):
                limitation = candidate_by_id.get(str(limitation_id))
                if limitation is None:
                    if trusted_artifacts.get(str(limitation_id)) != current.input_hashes.get(
                        str(limitation_id)
                    ):
                        blockers.append(
                            _finding(
                                "CONTRIBUTION_LIMITATION_UNBOUND",
                                f"{candidate_id} cites an absent limitation: {limitation_id}",
                                "candidates",
                            )
                        )
                elif limitation.get("kind") != "limitation":
                    blockers.append(
                        _finding(
                            "CONTRIBUTION_LIMITATION_INVALID",
                            f"{limitation_id} is not a limitation candidate",
                            "candidates",
                        )
                    )
        if preparation.get(
            "external_action_authorized"
        ) is not False or _contains_external_authorization(preparation):
            blockers.append(
                _finding(
                    "EXTERNAL_ACTION_FORBIDDEN",
                    "candidate preparation cannot authorize external actions",
                )
            )
        if blockers:
            return _result(
                stage="J5",
                subject=current,
                blockers=blockers,
                warnings=[],
                artifacts=[],
                next_stage="J5",
            )
        stable_preparation = {
            "contract": "paperspine5.contribution-candidate-preparation",
            "schema_version": CONTRACT_VERSION,
            "subject": current.as_dict(),
            "authority_bindings": dict(bindings),
            "candidates": [dict(item) for item in candidates],
            "external_action_authorized": False,
        }
        stable_preparation["preparation_sha256"] = canonical_sha256(
            {
                "authority_bindings": stable_preparation["authority_bindings"],
                "candidates": stable_preparation["candidates"],
            }
        )
        descriptor = _descriptor(
            artifact_id="contribution_candidate_preparation",
            artifact_type="authority.contribution-candidate-preparation",
            subject=current,
            payload=stable_preparation,
            product_build_id=self.product_build_id,
            stage="J5",
            producer_id=self.producer_id,
        )
        return _result(
            stage="J5",
            subject=current,
            blockers=[],
            warnings=[],
            artifacts=[descriptor],
            next_stage="J5",
        )

    def compile_claim_graph(
        self,
        subject: QualitySubject | Mapping[str, Any],
        graph: Mapping[str, Any],
        *,
        trusted_artifacts: Mapping[str, str],
        trusted_attestations: Mapping[str, str],
        changed_artifact_ids: Iterable[str] = (),
    ) -> dict[str, Any]:
        """J6: compile a bidirectional, mutation-aware Claim--Evidence graph."""

        current = _subject(subject)
        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        if graph.get("contract") != "paperspine5.claim-evidence-argument-graph" or graph.get(
            "schema_version"
        ) != CONTRACT_VERSION:
            blockers.append(_finding("CLAIM_GRAPH_CONTRACT_INVALID", "graph contract/version is invalid"))
        if graph.get("subject") != current.as_dict():
            blockers.append(_finding("CLAIM_GRAPH_SUBJECT_STALE", "graph subject is not current", "subject"))
        required_inputs = ["direction_authority", "target_authority", "contribution_boundary_decision"]
        blockers.extend(_trusted_hash_findings(current, trusted_artifacts, required_inputs, "subject"))
        contribution = graph.get("contribution_decision")
        if not isinstance(contribution, Mapping) or contribution.get("artifact_id") != "contribution_boundary_decision" or contribution.get(
            "sha256"
        ) != current.input_hashes.get("contribution_boundary_decision"):
            blockers.append(_finding("CONTRIBUTION_DECISION_STALE", "graph does not bind the current contribution decision"))

        nodes_raw = graph.get("nodes")
        edges_raw = graph.get("edges")
        nodes: dict[str, Mapping[str, Any]] = {}
        if not isinstance(nodes_raw, list):
            nodes_raw = []
        blockers.extend(_claim_graph_node_contract_findings(nodes_raw))
        source_ids: set[str] = set()
        source_to_nodes: dict[str, set[str]] = {}
        core_claim_count = 0
        for index, node in enumerate(nodes_raw):
            path = f"nodes[{index}]"
            if not isinstance(node, Mapping) or not _nonempty(node.get("node_id")):
                blockers.append(_finding("CLAIM_NODE_INVALID", "node_id is required", path))
                continue
            node_id = str(node["node_id"])
            if node_id in nodes:
                continue
            nodes[node_id] = node
            if node.get("node_type") == "claim" and node.get("core") is True:
                core_claim_count += 1
            artifact_id = str(node.get("source_artifact_id") or "")
            source_hash = node.get("source_sha256")
            if not artifact_id or current.input_hashes.get(artifact_id) != source_hash:
                blockers.append(_finding("CLAIM_NODE_SOURCE_STALE", "node source is not revision-bound", path))
            else:
                source_ids.add(artifact_id)
                source_to_nodes.setdefault(artifact_id, set()).add(node_id)
        blockers.extend(_trusted_hash_findings(current, trusted_artifacts, source_ids, "nodes"))
        if core_claim_count == 0:
            blockers.append(_finding("CORE_CLAIM_MISSING", "at least one core claim must be explicit"))

        edges, edge_findings = _parse_claim_graph_edges(nodes, edges_raw)
        blockers.extend(edge_findings)

        for claim_id, claim in nodes.items():
            if claim.get("node_type") != "claim" or claim.get("core") is not True:
                continue
            if claim.get("status") != "verified":
                blockers.append(_finding("CORE_CLAIM_UNVERIFIED", "core claim is not verified", claim_id))
            for target_type, (relations, inverse_relation) in CLAIM_FORWARD_RELATIONS.items():
                linked = [
                    (relation, target)
                    for source, relation, target in edges
                    if source == claim_id and relation in relations
                ]
                valid = [
                    (relation, target)
                    for relation, target in linked
                    if nodes.get(target, {}).get("node_type") == target_type
                ]
                if not valid:
                    forward_label = "|".join(relations)
                    blockers.append(
                        _finding(
                            "CLAIM_SUPPORTSET_INCOMPLETE",
                            f"core claim {claim_id!r} requires from={claim_id!r}, "
                            f"relation={forward_label!r}, to=<verified {target_type} node>, "
                            f"plus inverse relation={inverse_relation!r}",
                            claim_id,
                        )
                    )
                    continue
                for relation, target in valid:
                    inverse = (target, inverse_relation, claim_id)
                    if inverse not in edges:
                        blockers.append(_finding("CLAIM_EDGE_NOT_BIDIRECTIONAL", f"missing inverse edge {inverse}", claim_id))
                    status = nodes[target].get("status")
                    if target_type == "counterevidence":
                        if status not in {"verified", "none_found"}:
                            blockers.append(_finding("COUNTEREVIDENCE_UNKNOWN", "counterevidence review is unresolved", target))
                    elif status != "verified":
                        blockers.append(_finding("CLAIM_SUPPORT_UNVERIFIED", f"{target_type} support is not verified", target))

        snapshot = compute_claim_graph_snapshot(graph)
        if graph.get("graph_snapshot_sha256") != snapshot:
            blockers.append(_finding("CLAIM_GRAPH_HASH_INVALID", "graph snapshot does not recompute", "graph_snapshot_sha256"))
        producer = graph.get("producer")
        challenger = graph.get("challenger")
        blockers.extend(_identity_findings(producer, "producer", current, trusted_attestations))
        if not isinstance(challenger, Mapping):
            blockers.append(_finding("CLAIM_GRAPH_CHALLENGER_MISSING", "independent graph challenger is required"))
        else:
            reviewer = challenger.get("reviewer")
            blockers.extend(_identity_findings(reviewer, "challenger.reviewer", current, trusted_attestations))
            blockers.extend(_independence_findings(reviewer, producer, "challenger.reviewer"))
            if challenger.get("graph_snapshot_sha256") != snapshot:
                blockers.append(_finding("CLAIM_GRAPH_CHALLENGER_STALE", "challenger did not inspect this graph snapshot"))
            if challenger.get("status") != "pass":
                blockers.append(_finding("CLAIM_GRAPH_CHALLENGER_BLOCKED", "graph challenger did not pass"))
            objections = challenger.get("objections", [])
            if not isinstance(objections, list) or any(
                not isinstance(item, Mapping) or item.get("status") != "resolved" for item in objections
            ):
                blockers.append(_finding("CLAIM_GRAPH_OBJECTION_OPEN", "all challenger objections must be resolved"))

        changed = set(str(item) for item in changed_artifact_ids)
        invalid_nodes = set().union(*(source_to_nodes.get(item, set()) for item in changed)) if changed else set()
        invalid_claims = {
            source
            for source, _, target in edges
            if target in invalid_nodes and nodes.get(source, {}).get("node_type") == "claim"
        }
        invalidated: list[str] = []
        if invalid_nodes or invalid_claims:
            invalidated = sorted(
                invalid_nodes
                | invalid_claims
                | {
                    "claim_evidence",
                    "final_claim_inventory",
                    "evidence_verification_registry",
                    "canonical_manuscript",
                    "independent_review",
                    "final_render",
                    "target_bundle",
                    "readiness_verdict",
                }
            )
            blockers.append(_finding("CLAIM_GRAPH_INPUT_CHANGED", "changed inputs invalidate the graph and all downstream publication artifacts"))
        elif changed:
            warnings.append(_finding("CHANGED_INPUT_NOT_REFERENCED", "changed artifact is not referenced by this graph"))
        if graph.get("external_action_authorized") is not False or _contains_external_authorization(
            graph
        ):
            blockers.append(_finding("EXTERNAL_ACTION_FORBIDDEN", "claim graph cannot authorize external actions"))
        if blockers:
            return _result(
                stage="J6",
                subject=current,
                blockers=blockers,
                warnings=warnings,
                artifacts=[],
                next_stage="J6",
                invalidated_artifacts=invalidated,
            )
        graph_payload = {**dict(graph), "external_action_authorized": False}
        descriptor = _descriptor(
            artifact_id="claim_evidence",
            artifact_type="authority.claim-evidence-graph",
            subject=current,
            payload=graph_payload,
            product_build_id=self.product_build_id,
            stage="J6",
            producer_id=self.producer_id,
        )
        projection_subject = current.as_dict()
        projection_subject["input_hashes"] = {
            **projection_subject["input_hashes"],
            "claim_evidence": descriptor["payload_sha256"],
        }
        projection = {
            "contract": "paperspine5.frozen-authority-projection",
            "schema_version": CONTRACT_VERSION,
            "status": "PASS",
            "frozen": True,
            "subject": projection_subject,
            "authorities": {
                artifact_id: {
                    "artifact_id": artifact_id,
                    "sha256": projection_subject["input_hashes"][artifact_id],
                }
                for artifact_id in FROZEN_AUTHORITY_IDS
            },
            "external_action_authorized": False,
        }
        projection["projection_sha256"] = canonical_sha256(projection)
        return _result(
            stage="J6",
            subject=current,
            blockers=[],
            warnings=warnings,
            artifacts=[descriptor],
            next_stage="J7",
            frozen_authority=projection,
        )


def validate_frozen_authority_projection(
    projection: Mapping[str, Any],
    *,
    trusted_artifacts: Mapping[str, str],
    task_id: str | None = None,
    revision_id: str | None = None,
) -> list[dict[str, str]]:
    """Validate W5/W6's exact three-authority, same-revision projection.

    Call only after the J6 descriptor has been recorded.  A self-consistent but
    unrecorded projection is rejected because every hash is checked against the
    kernel's trusted artifact ledger.
    """

    findings: list[dict[str, str]] = []
    unsigned = {key: value for key, value in projection.items() if key != "projection_sha256"}
    if projection.get("contract") != "paperspine5.frozen-authority-projection" or projection.get(
        "schema_version"
    ) != CONTRACT_VERSION:
        findings.append(_finding("FROZEN_AUTHORITY_CONTRACT_INVALID", "projection contract/version is invalid"))
    if projection.get("status") != "PASS" or projection.get("frozen") is not True:
        findings.append(_finding("FROZEN_AUTHORITY_NOT_PASS", "projection is not frozen PASS"))
    if projection.get("external_action_authorized") is not False or _contains_external_authorization(projection):
        findings.append(_finding("EXTERNAL_ACTION_FORBIDDEN", "authority projection cannot authorize external actions"))
    if projection.get("projection_sha256") != canonical_sha256(unsigned):
        findings.append(_finding("FROZEN_AUTHORITY_HASH_INVALID", "projection hash does not recompute"))
    try:
        subject = QualitySubject.from_mapping(projection.get("subject", {}))
    except QualityContractError as exc:
        findings.append(_finding("FROZEN_AUTHORITY_SUBJECT_INVALID", str(exc), "subject"))
        return findings
    if task_id is not None and subject.task_id != task_id:
        findings.append(_finding("FROZEN_AUTHORITY_TASK_STALE", "projection task differs from selected task"))
    if revision_id is not None and subject.revision_id != str(revision_id):
        findings.append(_finding("FROZEN_AUTHORITY_REVISION_STALE", "projection revision is stale"))
    authorities = projection.get("authorities")
    if not isinstance(authorities, Mapping) or set(authorities) != set(FROZEN_AUTHORITY_IDS):
        findings.append(_finding("FROZEN_AUTHORITY_SET_INVALID", "exact direction, target, and claim_evidence authorities are required"))
        return findings
    for artifact_id in FROZEN_AUTHORITY_IDS:
        binding = authorities.get(artifact_id)
        if not isinstance(binding, Mapping) or binding.get("artifact_id") != artifact_id:
            findings.append(_finding("FROZEN_AUTHORITY_BINDING_INVALID", f"{artifact_id} binding is invalid"))
            continue
        digest = binding.get("sha256")
        if not _is_sha256(digest) or subject.input_hashes.get(artifact_id) != digest:
            findings.append(_finding("FROZEN_AUTHORITY_SUBJECT_MISMATCH", f"{artifact_id} is not individually subject-bound"))
        if trusted_artifacts.get(artifact_id) != digest:
            findings.append(_finding("FROZEN_AUTHORITY_LEDGER_MISMATCH", f"{artifact_id} is absent or different in the same-revision ledger"))
    return findings
