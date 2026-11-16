"""Pure cumulative J4--J11 adapter for a future ProductRunner handler.

This module owns no writer, task state, filesystem, database, network, or UI.
It rebuilds every trust projection from actual base artifact payloads, replays
all completed upstream gates at one requested revision, and normalizes the two
stage-service descriptor dialects.  ProductRunner remains the sole CAS owner.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from .publication_pipeline import PublicationPipelineService
from .contracts import ContractError
from .figure_correction import (
    FigureCorrectionError,
    validate_figure_correction_receipt,
    validate_target_size_legibility_receipt,
)
from .figure_reference_mapping import (
    FigureReferenceMappingError,
    canonical_sha256 as figure_reference_sha256,
    figure_authority_table_sha256,
    validate_trusted_figure_master_receipt,
    validate_figure_reference_plan,
)
from .product_runner_contracts import (
    validate_local_delegation_context,
    validate_run_configuration,
)
from .quality_readiness import (
    AUTHOR_ONLY_TARGET_FACT_KEYS,
    QualitySubject,
    canonical_sha256,
    identity_provenance_sha256,
)
from .research_argument_service import (
    ResearchArgumentStageService,
    canonical_payload_bytes,
    compute_claim_graph_snapshot,
    compute_research_scope,
    compute_research_snapshot,
    validate_claim_graph_edge_contract,
    validate_stage_artifact_descriptor,
)


CONTRACT_VERSION = "1.0"
STAGES = (
    "awaiting_research",
    "awaiting_contribution",
    "awaiting_claim_graph",
    "awaiting_figure_intent",
    "awaiting_canonical",
    "awaiting_review",
    "awaiting_package",
    "target_package_ready",
)
ACTIVE_STAGES = STAGES[:-1]
NEXT_STAGE = {stage: STAGES[index + 1] for index, stage in enumerate(ACTIVE_STAGES)}
STAGE_CODES = {
    "awaiting_research": "J4",
    "awaiting_contribution": "J5",
    "awaiting_claim_graph": "J6",
    "awaiting_figure_intent": "J7",
    "awaiting_canonical": "J8",
    "awaiting_review": "J9",
    "awaiting_package": "J10-J11",
}
FORBIDDEN_REQUEST_KEYS = {
    "subject",
    "trusted_artifacts",
    "frozen_authority",
    "artifact_descriptors",
}
SELF_HASH_FIELDS = (
    "receipt_sha256",
    "bundle_sha256",
    "revision_sha256",
    "head_sha256",
    "review_sha256",
    "finding_sha256",
    "diff_sha256",
    "closure_sha256",
    "ledger_sha256",
    "manifest_sha256",
)
INVALIDATE_ALL = (
    "direction_authority",
    "target_authority",
    "contribution_boundary_decision",
    "claim_evidence",
    "publication.figure-intent",
    "publication.manuscript-head",
    "publication.review-closure",
    "publication.target-package",
    "publication.readiness",
    "canonical_manuscript",
    "final_render",
    "target_bundle",
    "readiness_verdict",
)
STAGE_MUTABLE_BASE_ARTIFACTS = {
    # ProductRunner may replace the initially BLOCKED host-derived figure set at
    # the same J4 issue only after it validates a typed semantic-fragment request
    # against unchanged ledger bytes.  The material snapshot and every source
    # hash remain fixed; this exception cannot authorize caller-supplied assets.
    "awaiting_research": frozenset({"materials.figure-set"}),
    # These are J8 build outputs registered as actual Runner inputs before the
    # academic adapter validates the canonical answer.  A failed visual or
    # contract review must be able to replace them at the same J8 issue;
    # treating that legitimate revision as upstream material drift would make
    # review feedback impossible to close.  No research/material/authority
    # artifact is included in this narrow exception.
    "awaiting_canonical": frozenset(
        {"manuscript_source", "manuscript_pdf", "manuscript_word"}
    ),
    # The archive is the J10 delivery output.  Rebuilding it after an
    # independent review must not be mistaken for upstream scientific drift.
    "awaiting_package": frozenset({"bundle_archive_delivery"}),
}
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


_CONTRACT_ROOT = __file__.replace("\\", "/").rsplit("/", 3)[0]
with open(  # noqa: PTH123 - avoids a new Atlas dependency for one module-local load.
    f"{_CONTRACT_ROOT}/contracts/academic-stage-answer.schema.json",
    encoding="utf-8",
) as _academic_stage_schema_stream:
    _PUBLIC_ACADEMIC_STAGE_ANSWER_SCHEMA = json.load(_academic_stage_schema_stream)
with open(  # noqa: PTH123 - public browser confirmation contract is source-owned.
    f"{_CONTRACT_ROOT}/contracts/contribution-confirmation.schema.json",
    encoding="utf-8",
) as _contribution_confirmation_schema_stream:
    _PUBLIC_CONTRIBUTION_CONFIRMATION_SCHEMA = json.load(
        _contribution_confirmation_schema_stream
    )
_STAGE_PAYLOAD_DEFS = {
    "awaiting_research": "research_payload",
    "awaiting_contribution": "contribution_payload",
    "awaiting_claim_graph": "claim_graph_payload",
    "awaiting_figure_intent": "figure_intent_payload",
    "awaiting_canonical": "canonical_payload",
    "awaiting_review": "review_payload",
    "awaiting_package": "package_payload",
}


def public_academic_stage_answer_schema(
    *,
    stage: str | None = None,
    task_id: str | None = None,
    revision: int | None = None,
    issue_id: str | None = None,
) -> dict[str, Any]:
    """Return the MCP schema or a task/issue/stage-specialized projection."""

    schema = copy.deepcopy(_PUBLIC_ACADEMIC_STAGE_ANSWER_SCHEMA)
    if stage is None:
        return schema
    if stage not in _STAGE_PAYLOAD_DEFS:
        raise AcademicStageContractError(f"unsupported public academic stage: {stage}")
    schema.pop("allOf", None)
    schema["title"] = f"PaperSpine5 {STAGE_CODES[stage]} issue-bound answer"
    schema["properties"]["stage"] = {"const": stage}
    schema["properties"]["payload"] = {
        "$ref": f"#/$defs/{_STAGE_PAYLOAD_DEFS[stage]}"
    }
    for field, value in (
        ("task_id", task_id),
        ("expected_revision", revision),
        ("issue_id", issue_id),
    ):
        if value is not None:
            schema["properties"][field] = {"const": value}
    return schema


def public_contribution_confirmation_schema(
    *, task_id: str, revision: int, issue_id: str, preparation_sha256: str
) -> dict[str, Any]:
    """Return the phase-2 contract specialized to one persisted Web issue."""

    schema = copy.deepcopy(_PUBLIC_CONTRIBUTION_CONFIRMATION_SCHEMA)
    for field, value in (
        ("task_id", task_id),
        ("expected_revision", revision),
        ("issue_id", issue_id),
        ("preparation_sha256", preparation_sha256),
    ):
        schema["properties"][field] = {"const": value}
    return schema


def public_contribution_confirmation_example(
    *,
    task_id: str,
    revision: int,
    issue_id: str,
    preparation_sha256: str,
    candidate_ids: Sequence[str],
) -> dict[str, Any]:
    """Return an issue-bound browser intent example without identity impersonation."""

    return {
        "contract": "paperspine5.contribution-confirmation",
        "schema_version": CONTRACT_VERSION,
        "confirmation_id": f"example:{revision}:contribution-confirmation",
        "issue_id": issue_id,
        "task_id": task_id,
        "expected_revision": revision,
        "preparation_sha256": preparation_sha256,
        "decisions": [
            {
                "candidate_id": candidate_id,
                "choice": "accept",
                "reason": "Replace with the user's reason.",
            }
            for candidate_id in candidate_ids
        ],
        "external_action_authorized": False,
    }


def public_academic_stage_answer_example(
    *, task_id: str, revision: int, issue_id: str, stage: str
) -> dict[str, Any]:
    """Return a schema-valid public example with internally bound J7 assets."""

    zero = "0" * 64
    figure_candidate_example = {
        "contract": "paperspine5.figure-candidate-example",
        "schema_version": "1.0",
        "description": "Replace this illustrative candidate with the current immutable figure candidate.",
        "external_action_authorized": False,
    }
    figure_candidate_sha256 = hashlib.sha256(
        canonical_payload_bytes(figure_candidate_example)
    ).hexdigest()
    mapping_authority = {
        "authority_kind": "paperspine_master",
        "principal_id": "replace-figure-plan-master",
        "session_id": "replace-figure-plan-session",
        "run_id": "replace-figure-plan-run",
        "attestation_input_id": "identity:figure-plan-master",
        "authority_table_sha256": figure_authority_table_sha256(),
    }
    mapping_authority["provenance_sha256"] = figure_reference_sha256(
        mapping_authority
    )
    figure_reference_plan = {
        "contract": "paperspine5.figure-reference-plan",
        "schema_version": "1.0",
        "mapping_id": "replace-figure-1-reference-plan",
        "authority_table_version": (
            "paper-spine/references/figure-reference-mapping.md#1.0"
        ),
        "mapping_authority": mapping_authority,
        "subject": {
            "task_id": task_id,
            "material_snapshot_sha256": zero,
            "runner_revision": str(revision),
        },
        "figure": {
            "figure_id": "replace-figure-1",
            "figure_kind": "data",
            "publication_role": "main",
            "panel_ids": ["whole-figure"],
            "producer_id": "replace-figure-producer",
        },
        "design_provenance": "original_no_reference",
        "original_design_rationale": (
            "No lawful reference asset is attached to this illustrative example."
        ),
        "reference_assets": [],
        "scientific_story": {
            "question": "What bounded result should this figure make visible?",
            "claim_ids": ["replace-claim"],
            "claim_boundary": "Do not infer beyond the supplied project evidence.",
            "results_unit_ids": ["replace-result"],
            "intended_conclusion": (
                "The selected visual should expose one evidence-bounded result."
            ),
            "hero_panel_id": "whole-figure",
        },
        "domain_mappings": [
            {
                "mapping_row_id": "replace-whole-figure-mapping",
                "source_kind": "original_component",
                "current_panel_id": "whole-figure",
                "evidence_anchor_ids": ["replace-result"],
                "data_bindings": [
                    {
                        "current_field": "replace.result",
                        "visual_role": "primary result",
                        "unit": None,
                        "transform": "identity",
                    }
                ],
                "semantic_transform": (
                    "Use only the current evidence and preserve its stated boundary."
                ),
                "retained_differences": ["original evidence semantics"],
            }
        ],
        "grammar_reuse_justification": None,
        "external_action_authorized": False,
    }
    figure_reference_plan["plan_sha256"] = figure_reference_sha256(
        figure_reference_plan
    )

    def identity(label: str) -> dict[str, str]:
        value = {
            "principal_id": f"replace-{label}",
            "session_id": f"replace-{label}-session",
            "run_id": f"replace-{label}-run",
            "independence_group": f"replace-{label}-group",
            "attestation_input_id": f"identity:{label}",
        }
        value["provenance_sha256"] = identity_provenance_sha256(value)
        return value

    claim_node_sources = {
        "claim": "contribution_boundary_decision",
        "evidence": "replace-evidence",
        "result": "replace-result",
        "citation": "replace-citation",
        "limitation": "contribution_boundary_decision",
        "warrant": "contribution_boundary_decision",
        "boundary": "contribution_boundary_decision",
        "counterevidence": "replace-counterevidence",
    }
    claim_nodes = [
        {
            "node_id": f"{node_type}-1",
            "node_type": node_type,
            "statement_sha256": zero,
            "source_artifact_id": source_artifact_id,
            "source_sha256": zero,
            "locator": f"replace-with-{node_type}-locator",
            "status": "verified",
            "core": node_type == "claim",
            **(
                {"contribution_candidate_id": "replace-contribution"}
                if node_type == "claim"
                else {}
            ),
        }
        for node_type, source_artifact_id in claim_node_sources.items()
    ]
    claim_relation_pairs = (
        ("supported_by", "evidence", "supports"),
        ("grounded_in", "result", "grounds"),
        ("cited_context", "citation", "supports_context"),
        ("limited_by", "limitation", "limits"),
        ("warranted_by", "warrant", "warrants"),
        ("bounded_by", "boundary", "bounds"),
        ("challenged_by", "counterevidence", "challenges"),
    )
    claim_edges = [
        edge
        for forward, node_type, inverse in claim_relation_pairs
        for edge in (
            {"from": "claim-1", "relation": forward, "to": f"{node_type}-1"},
            {"from": f"{node_type}-1", "relation": inverse, "to": "claim-1"},
        )
    ]

    payloads: dict[str, dict[str, Any]] = {
        "awaiting_research": {
            "contract": "paperspine5.runtime-research-bundle",
            "schema_version": "1.0",
            "as_of_date": "2026-01-01",
            "direction": {
                "statement": "Replace with the evidence-bounded direction.",
                "questions": ["Replace with one researched question."],
                "boundaries": ["Replace with one explicit boundary."],
            },
            "target": {"status": "unknown", "name": None},
            "network_status": "offline",
            "research_scope_sha256": zero,
            "research_snapshot_sha256": zero,
            "producer": identity("research-producer"),
            "sources": [
                {
                    "source_id": "official",
                    "lane": "official",
                    "authority": "official_hard",
                    "locator": "replace-with-stable-locator",
                    "content_sha256": canonical_input_sha256(
                        {"content": "Replace with frozen source content."}
                    ),
                    "retrieved_at": "2026-01-01T00:00:00Z",
                    "effective_date": "2026-01-01",
                    "valid_until": "2026-12-31",
                    "officiality_verified": True,
                    "supported_spans": [
                        {"locator": "replace-with-span", "quote_sha256": zero}
                    ],
                    "availability": "accessible",
                    "access_basis": "public",
                }
            ],
            "rules": [
                {
                    "rule_id": "replace-rule",
                    "kind": "hard",
                    "enforcement": "hard",
                    "readiness_scope": "local_delivery",
                    "evidence_locator": "replace-with-rule-evidence",
                    "statement": "Replace with the verified rule.",
                    "effective_date": "2026-01-01",
                    "source_ids": ["official"],
                }
            ],
            "coverage": {
                "required_topics": ["replace-topic"],
                "covered_topics": ["replace-topic"],
                "source_ids": ["official"],
            },
            "challenger": {
                "reviewer": identity("research-challenger"),
                "research_snapshot_sha256": zero,
                "status": "pass",
                "objections": [],
            },
            "conflicts": [],
            "input_artifacts": {
                "source:official": {"content": "Replace with frozen source content."},
                "identity:research-producer": identity("research-producer"),
                "identity:research-challenger": identity("research-challenger"),
            },
            "external_action_authorized": False,
        },
        "awaiting_contribution": {
            "contract": "paperspine5.contribution-candidate-preparation",
            "schema_version": "1.0",
            "authority_bindings": {
                "direction_authority": zero,
                "target_authority": zero,
                "materials.source-ledger": zero,
            },
            "candidates": [
                {
                    "candidate_id": "replace-contribution",
                    "kind": "contribution",
                    "statement": "Replace with one evidence-bounded candidate.",
                    "author_authority": "project_fact",
                    "supporting_artifact_ids": ["replace-support"],
                    "direct_competitor_source_ids": ["replace-competitor"],
                    "counterevidence_artifact_ids": ["replace-counterevidence"],
                    "limitation_ids": ["replace-limitation"],
                    "boundary_statement": "Replace with a falsifiable boundary.",
                }
            ],
            "input_artifacts": {},
            "external_action_authorized": False,
        },
        "awaiting_claim_graph": {
            "contract": "paperspine5.claim-evidence-argument-graph",
            "schema_version": "1.0",
            "contribution_decision": {
                "artifact_id": "contribution_boundary_decision",
                "sha256": zero,
            },
            "nodes": claim_nodes,
            "edges": claim_edges,
            "producer": identity("claim-producer"),
            "challenger": {
                "reviewer": identity("claim-challenger"),
                "graph_snapshot_sha256": zero,
                "status": "pass",
                "objections": [],
            },
            "graph_snapshot_sha256": zero,
            "input_artifacts": {
                "replace-evidence": {"replace": "with actual evidence object"},
                "replace-result": {"replace": "with actual result object"},
                "replace-citation": {"replace": "with actual citation object"},
                "replace-counterevidence": {
                    "replace": "with actual counterevidence review object"
                },
                "identity:claim-producer": identity("claim-producer"),
                "identity:claim-challenger": identity("claim-challenger"),
            },
            "external_action_authorized": False,
        },
        "awaiting_figure_intent": {
            "intent": {
                "mode": "create",
                "producer_id": "replace-figure-producer",
                "decision_basis_artifact_ids": [
                    "direction_authority",
                    "claim_evidence",
                ],
                "figures": [
                    {
                        "figure_id": "replace-figure-1",
                        "panels": [{"panel_id": "whole-figure"}],
                        "reference_plan": {
                            "artifact_id": "replace-figure-reference-plan",
                            "sha256": figure_reference_plan["plan_sha256"],
                            "revision_id": str(revision),
                        },
                        "candidate_assets": [
                            {
                                "artifact_id": "replace-candidate-artifact",
                                "sha256": figure_candidate_sha256,
                                "revision_id": str(revision),
                            }
                        ],
                        "independent_comparison": {
                            "reviewer_id": "replace-independent-figure-reviewer",
                            "producer_ids": ["replace-figure-producer"],
                            "status": "PASS",
                            "reviewed_asset_hashes": [figure_candidate_sha256],
                            "decision": "candidate_wins",
                            "selected_sha256": figure_candidate_sha256,
                        },
                    }
                ],
            },
            "input_artifacts": {
                "replace-candidate-artifact": figure_candidate_example,
                "replace-figure-reference-plan": figure_reference_plan,
            },
        },
        "awaiting_canonical": {
            "canonical_bundle": {},
            "manuscript_revision": {},
            "input_artifacts": {},
        },
        "awaiting_review": {
            "producer_ids": ["replace-manuscript-producer"],
            "initial_review": {},
            "input_artifacts": {},
        },
        "awaiting_package": {
            "surface_receipts": [{}],
            "target_obligations": {},
            "package_mapping": [{}],
            "author_close": [],
            "package_manifest": {},
            "predicates": [{}],
            "readiness_obligation_manifest": {},
            "cycle": {},
            "input_artifacts": {},
        },
    }
    if stage not in payloads:
        raise AcademicStageContractError(f"unsupported public academic stage: {stage}")
    return {
        "contract": "paperspine5.academic-stage-answer",
        "schema_version": "1.0",
        "answer_id": f"example:{revision}:{stage}",
        "issue_id": issue_id,
        "task_id": task_id,
        "expected_revision": revision,
        "stage": stage,
        "payload": payloads[stage],
        "external_action_authorized": False,
    }


class AcademicStageContractError(ValueError):
    """Raised only for programmer-level construction errors."""


def _finding(code: str, message: str, path: str = "") -> dict[str, str]:
    value = {"code": code, "message": message}
    if path:
        value["path"] = path
    return value


def _safe_evidence_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    if not token:
        raise AcademicStageContractError(
            "figure_id cannot form a safe evidence artifact ID"
        )
    return token[:80]


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


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


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def canonical_input_sha256(payload: Mapping[str, Any]) -> str:
    """Hash actual persisted payload bytes in the adapter's canonical encoding."""

    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _validated_material_figure_set(
    raw_profile: Any,
    material_ledger: Any,
    *,
    task_id: str,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Validate the host-derived active manuscript figure set against the ledger."""

    if not isinstance(material_ledger, Mapping) or material_ledger.get(
        "contract"
    ) != "paperspine5.material-source-ledger":
        return None, []
    if not isinstance(raw_profile, Mapping):
        return None, [
            _finding(
                "MATERIAL_FIGURE_SET_MISSING",
                "the ProductRunner host must derive the active manuscript figure set",
            )
        ]
    profile = copy.deepcopy(dict(raw_profile))
    expected_hash = canonical_sha256(
        {key: value for key, value in profile.items() if key != "profile_sha256"}
    )
    findings: list[dict[str, str]] = []
    if (
        profile.get("contract") != "paperspine5.material-figure-set"
        or profile.get("schema_version") != CONTRACT_VERSION
        or profile.get("task_id") != task_id
        or profile.get("material_snapshot_sha256")
        != material_ledger.get("snapshot_sha256")
        or profile.get("profile_sha256") != expected_hash
        or profile.get("external_action_authorized") is not False
    ):
        findings.append(
            _finding(
                "MATERIAL_FIGURE_SET_INVALID",
                "material figure set identity/hash does not bind the current task ledger",
            )
        )
    ledger_by_id = {
        str(item.get("source_id") or ""): item
        for item in material_ledger.get("entries", [])
        if isinstance(item, Mapping) and _nonempty(item.get("source_id"))
    }
    primary_id = profile.get("primary_manuscript_source_id")
    if primary_id is not None:
        primary = ledger_by_id.get(str(primary_id))
        if (
            primary is None
            or profile.get("primary_manuscript_relative_path")
            != primary.get("relative_path")
            or profile.get("primary_manuscript_sha256") != primary.get("sha256")
        ):
            findings.append(
                _finding(
                    "MATERIAL_FIGURE_PRIMARY_STALE",
                    "primary manuscript identity differs from the current material ledger",
                )
            )
    primary_candidates = profile.get("primary_candidates")
    if not isinstance(primary_candidates, list):
        findings.append(
            _finding(
                "MATERIAL_PRIMARY_CANDIDATES_INVALID",
                "primary manuscript candidate evidence must be an array",
            )
        )
        primary_candidates = []
    selected_primary_ids: list[str] = []
    for index, candidate in enumerate(primary_candidates):
        candidate_map = candidate if isinstance(candidate, Mapping) else {}
        source_id = str(candidate_map.get("source_id") or "")
        ledger_entry = ledger_by_id.get(source_id)
        if (
            not isinstance(candidate, Mapping)
            or ledger_entry is None
            or candidate.get("relative_path") != ledger_entry.get("relative_path")
            or candidate.get("sha256") != ledger_entry.get("sha256")
            or candidate.get("selection_status") not in {"selected", "rejected"}
            or not isinstance(candidate.get("scientific_signals"), list)
        ):
            findings.append(
                _finding(
                    "MATERIAL_PRIMARY_CANDIDATE_STALE",
                    "primary manuscript candidate evidence differs from the ledger",
                    f"primary_candidates[{index}]",
                )
            )
        if isinstance(candidate, Mapping) and candidate.get("selection_status") == "selected":
            selected_primary_ids.append(source_id)
    if selected_primary_ids != ([] if primary_id is None else [str(primary_id)]):
        findings.append(
            _finding(
                "MATERIAL_PRIMARY_SELECTION_INVALID",
                "primary selection evidence does not identify exactly the bound manuscript",
            )
        )

    fragment_candidates = profile.get("fragment_candidates")
    if not isinstance(fragment_candidates, list):
        findings.append(
            _finding(
                "MATERIAL_FRAGMENT_CANDIDATES_INVALID",
                "semantic fragment candidates must be an array",
            )
        )
        fragment_candidates = []
    candidate_fragment_ids: set[str] = set()
    for index, candidate in enumerate(fragment_candidates):
        candidate_map = candidate if isinstance(candidate, Mapping) else {}
        source_id = str(candidate_map.get("source_id") or "")
        ledger_entry = ledger_by_id.get(source_id)
        figure_ids = candidate_map.get("resolved_figure_source_ids")
        if (
            not isinstance(candidate, Mapping)
            or not source_id
            or source_id in candidate_fragment_ids
            or ledger_entry is None
            or candidate.get("relative_path") != ledger_entry.get("relative_path")
            or candidate.get("sha256") != ledger_entry.get("sha256")
            or candidate.get("detected_role")
            != "unlinked_scientific_manuscript_fragment"
            or not isinstance(figure_ids, list)
            or not figure_ids
            or any(str(figure_id) not in ledger_by_id for figure_id in figure_ids)
        ):
            findings.append(
                _finding(
                    "MATERIAL_FRAGMENT_CANDIDATE_STALE",
                    "semantic fragment evidence differs from the current material ledger",
                    f"fragment_candidates[{index}]",
                )
            )
        candidate_fragment_ids.add(source_id)

    main_fragment_ids = profile.get("main_text_fragment_source_ids")
    resolutions = profile.get("semantic_resolutions")
    if not isinstance(main_fragment_ids, list) or not isinstance(resolutions, list):
        findings.append(
            _finding(
                "MATERIAL_SEMANTIC_RESOLUTIONS_INVALID",
                "main-text fragment IDs and semantic resolutions must be arrays",
            )
        )
        main_fragment_ids = []
        resolutions = []
    resolved_ids: list[str] = []
    for index, resolution in enumerate(resolutions):
        if not isinstance(resolution, Mapping):
            findings.append(
                _finding(
                    "MATERIAL_SEMANTIC_RESOLUTION_INVALID",
                    "semantic resolution must be an object",
                    f"semantic_resolutions[{index}]",
                )
            )
            continue
        source_id = str(resolution.get("source_id") or "")
        ledger_entry = ledger_by_id.get(source_id)
        request = resolution.get("request")
        request_hash = (
            canonical_sha256(
                {key: value for key, value in request.items() if key != "request_sha256"}
            )
            if isinstance(request, Mapping)
            else None
        )
        resolution_hash = canonical_sha256(
            {
                key: value
                for key, value in resolution.items()
                if key != "resolution_sha256"
            }
        )
        if (
            not source_id
            or source_id in resolved_ids
            or source_id not in candidate_fragment_ids
            or ledger_entry is None
            or resolution.get("relative_path") != ledger_entry.get("relative_path")
            or resolution.get("source_sha256") != ledger_entry.get("sha256")
            or resolution.get("task_id") != task_id
            or resolution.get("material_snapshot_sha256")
            != material_ledger.get("snapshot_sha256")
            or resolution.get("resolved_role") != "main_text_fragment"
            or resolution.get("external_action_authorized") is not False
            or resolution.get("resolution_sha256") != resolution_hash
            or not isinstance(request, Mapping)
            or request.get("request_sha256") != request_hash
            or resolution.get("request_sha256") != request_hash
            or request.get("source_id") != source_id
            or request.get("source_sha256") != ledger_entry.get("sha256")
            or request.get("material_snapshot_sha256")
            != material_ledger.get("snapshot_sha256")
        ):
            findings.append(
                _finding(
                    "MATERIAL_SEMANTIC_RESOLUTION_STALE",
                    "semantic resolution is forged or does not bind the current ledger",
                    f"semantic_resolutions[{index}]",
                )
            )
        resolved_ids.append(source_id)
    if sorted(str(item) for item in main_fragment_ids) != sorted(resolved_ids):
        findings.append(
            _finding(
                "MATERIAL_MAIN_FRAGMENT_SET_INVALID",
                "main-text fragment IDs do not equal the accepted semantic resolutions",
            )
        )
    figures = profile.get("figure_sources")
    if not isinstance(figures, list):
        findings.append(
            _finding(
                "MATERIAL_FIGURE_SOURCES_INVALID",
                "material figure sources must be an array",
            )
        )
        figures = []
    seen: set[str] = set()
    for index, figure in enumerate(figures):
        if not isinstance(figure, Mapping):
            findings.append(
                _finding(
                    "MATERIAL_FIGURE_SOURCE_INVALID",
                    "material figure source must be an object",
                    f"figure_sources[{index}]",
                )
            )
            continue
        source_id = str(figure.get("source_id") or "")
        ledger_entry = ledger_by_id.get(source_id)
        if (
            not source_id
            or source_id in seen
            or ledger_entry is None
            or figure.get("artifact_id") != f"source:{source_id}"
            or figure.get("relative_path") != ledger_entry.get("relative_path")
            or figure.get("sha256") != ledger_entry.get("sha256")
            or figure.get("size_bytes") != ledger_entry.get("size_bytes")
            or not isinstance(figure.get("include_locators"), list)
            or not figure.get("include_locators")
        ):
            findings.append(
                _finding(
                    "MATERIAL_FIGURE_SOURCE_STALE",
                    "active manuscript figure source differs from the current material ledger",
                    f"figure_sources[{index}]",
                )
            )
        seen.add(source_id)
    if profile.get("figure_count") != len(figures):
        findings.append(
            _finding(
                "MATERIAL_FIGURE_COUNT_INVALID",
                "material figure count does not match its source set",
            )
        )
    if profile.get("status") == "BLOCKED" or profile.get("blockers"):
        findings.append(
            _finding(
                "MATERIAL_FIGURE_SET_BLOCKED",
                "active manuscript figure dependencies are unresolved",
            )
        )
    return profile, findings


def _verified_local_delegation(
    base_artifacts: Mapping[str, Mapping[str, Any]],
    *,
    task_id: str,
    run_contract_sha256: str | None,
    evaluation_time: str | None,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    run_contract = base_artifacts.get("runner.run-contract")
    if not isinstance(run_contract, Mapping):
        return None, []
    material_ledger = base_artifacts.get("materials.source-ledger")
    if not isinstance(material_ledger, Mapping):
        return None, [
            _finding(
                "LOCAL_DELEGATION_MATERIAL_LEDGER_MISSING",
                "delegated local decisions require the current material ledger",
            )
        ]
    try:
        configuration = validate_run_configuration(dict(run_contract.get("configuration") or {}))
        validate_local_delegation_context(
            configuration,
            dict(material_ledger),
            evaluation_time=evaluation_time,
        )
    except ContractError as exc:
        return None, [_finding("LOCAL_DELEGATION_INVALID", str(exc))]
    interaction = configuration["interaction"]
    if interaction["mode"] != "delegated_local_test":
        return None, []
    grant = interaction["grant"]
    if grant["task_id"] != task_id or not _is_sha256(run_contract_sha256):
        return None, [
            _finding(
                "LOCAL_DELEGATION_SUBJECT_STALE",
                "delegation does not bind the current task/run contract",
            )
        ]
    return {
        "contract": "paperspine5.verified-local-delegation",
        "schema_version": CONTRACT_VERSION,
        "task_id": task_id,
        "requested_scope": configuration["requested_scope"],
        "material_snapshot_sha256": grant["material_snapshot_sha256"],
        "run_contract_sha256": run_contract_sha256,
        "grant_id": grant["grant_id"],
        "grant_sha256": grant["grant_sha256"],
        "decision_classes": frozenset(grant["decision_classes"]),
        "reversible": True,
        "external_action_authorized": False,
    }, []


def _delegation_blocker(
    delegation: Mapping[str, Any] | None,
    decision_class: str,
    *,
    stage: str,
) -> list[dict[str, str]]:
    if delegation is None:
        return []
    if decision_class not in delegation.get("decision_classes", ()):
        return [
            _finding(
                "LOCAL_DELEGATION_CLASS_NOT_GRANTED",
                f"{stage} requires an explicit {decision_class} grant",
            )
        ]
    return []


def _delegated_decision_descriptor(
    *,
    delegation: Mapping[str, Any],
    decision_class: str,
    stage: str,
    action_id: str,
    subject: QualitySubject,
    choice: Mapping[str, Any],
    evidence_bindings: Mapping[str, str],
) -> dict[str, Any]:
    safe_action = re.sub(r"[^A-Za-z0-9._-]+", "-", action_id).strip("-") or "choice"
    payload = {
        "contract": "paperspine5.delegated-decision-receipt",
        "contract_version": CONTRACT_VERSION,
        "task_id": subject.task_id,
        "revision_id": subject.revision_id,
        "stage": STAGE_CODES[stage],
        "decision_class": decision_class,
        "action_id": action_id,
        "requested_scope": delegation["requested_scope"],
        "material_snapshot_sha256": delegation["material_snapshot_sha256"],
        "run_contract_sha256": delegation["run_contract_sha256"],
        "grant_id": delegation["grant_id"],
        "grant_sha256": delegation["grant_sha256"],
        "choice_sha256": canonical_sha256(choice),
        "evidence_bindings": dict(sorted(evidence_bindings.items())),
        "reversible": True,
        "external_action_authorized": False,
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    return {
        "artifact_id": f"delegated-decision.{STAGE_CODES[stage]}.{decision_class}.{safe_action}",
        "artifact_type": "authority.delegated-decision-receipt",
        "payload": payload,
    }


def _logical_artifact_hash(
    payload: Mapping[str, Any],
    *,
    trusted_figure_master_receipt: Mapping[str, Any] | None = None,
) -> str:
    """Validate semantic self-hashes, then bind authority to the actual bytes.

    Contract self-hashes remain useful internal integrity checks, but a ProductKernel
    artifact receipt can only attest the digest of bytes it actually records.  The
    cumulative authority snapshot therefore always uses the canonical payload-byte
    digest so a later readiness verdict can be atomically reconciled to receipts.
    """

    # Figure-quality receipts deliberately use the source-owned canonical JSON
    # encoding (including its terminal newline).  Validate those typed contracts
    # in their own hash namespace before applying the generic PaperSpine receipt
    # convention below.  This keeps the base-artifact gate strict without
    # rejecting a valid receipt merely because another contract family omits the
    # newline from its canonical serialization.
    contract = payload.get("contract")
    try:
        if contract == "paperspine5.local-package-archive":
            # The JSON descriptor is the ledger payload, while ``sha256``
            # binds the actual ZIP bytes at its declared path.  Package
            # readiness and the download endpoint must compare the latter;
            # hashing the descriptor JSON here would make a valid archive
            # impossible to bind consistently.
            archive_sha = payload.get("sha256")
            if not _is_sha256(archive_sha) or payload.get("external_action_authorized") is not False:
                raise AcademicStageContractError("local package archive descriptor is invalid")
            return str(archive_sha)
        if contract == "paperspine5.figure-correction-receipt":
            validate_figure_correction_receipt(dict(payload))
            return canonical_input_sha256(payload)
        if contract == "paperspine5.target-size-legibility-receipt":
            validate_target_size_legibility_receipt(dict(payload))
            return canonical_input_sha256(payload)
        if contract == "paperspine5.figure-reference-plan":
            return str(
                validate_figure_reference_plan(
                    payload,
                    trusted_actor_receipt=trusted_figure_master_receipt,
                )["plan_sha256"]
            )
        if contract == "paperspine5.figure-master-authority-receipt":
            validate_trusted_figure_master_receipt(payload)
            # Runner records this authority receipt without a semantic alias;
            # its subject binding must therefore use the recorded byte hash.
            return canonical_input_sha256(payload)
    except FigureCorrectionError as exc:
        raise AcademicStageContractError(str(exc)) from exc
    except FigureReferenceMappingError as exc:
        raise AcademicStageContractError(str(exc)) from exc

    present = [field for field in SELF_HASH_FIELDS if field in payload]
    if not present:
        return canonical_input_sha256(payload)
    for field in present:
        supplied = payload.get(field)
        unsigned = {key: value for key, value in payload.items() if key != field}
        expected = canonical_sha256(unsigned)
        if not _is_sha256(supplied) or supplied != expected:
            raise AcademicStageContractError(f"{field} does not bind the actual artifact payload")
    return canonical_input_sha256(payload)


def _rehash_contract(value: Any) -> Any:
    """Recompute nested contract self-hashes after a revision-only rebind."""

    if isinstance(value, list):
        return [_rehash_contract(item) for item in value]
    if not isinstance(value, Mapping):
        return copy.deepcopy(value)
    result = {key: _rehash_contract(item) for key, item in value.items()}
    for field in SELF_HASH_FIELDS:
        if field in result:
            unsigned = {key: item for key, item in result.items() if key != field}
            result[field] = canonical_sha256(unsigned)
    return result


def rebind_canonical_bundle_to_head(
    bundle: Mapping[str, Any], head: Mapping[str, Any]
) -> dict[str, Any]:
    """Recover a legacy persisted J8 input only if its exact replay matches head.

    This is not a hash-check bypass: all nested revision bindings and surface
    source hashes are deterministically rebound, then the result must equal the
    already persisted canonical head's bundle hash.
    """

    subject = QualitySubject.from_mapping(head.get("subject"))
    rebound = _rebind_current(bundle, subject)
    for surface in rebound.get("surface_receipts", []):
        if isinstance(surface, dict):
            kind = str(surface.get("surface_kind") or "")
            surface["source"] = {"sha256": head.get(f"{kind}_sha256")}
    rebound = _rehash_contract(rebound)
    if rebound.get("bundle_sha256") != head.get("canonical_bundle_sha256"):
        raise AcademicStageContractError("canonical bundle differs from the current head")
    return rebound


def _derive_target_obligation_ledger(
    target_authority: Mapping[str, Any], target_authority_sha256: str
) -> dict[str, Any]:
    if (
        target_authority.get("contract") != "paperspine5.target-authority"
        or target_authority.get("schema_version") != CONTRACT_VERSION
        or not _is_sha256(target_authority_sha256)
    ):
        raise AcademicStageContractError("target authority is invalid")
    rules = target_authority.get("official_hard_rules")
    if not isinstance(rules, list) or not rules:
        raise AcademicStageContractError("target authority has no hard rules")
    obligations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, Mapping):
            raise AcademicStageContractError("target hard rule is invalid")
        rule_id = str(rule.get("rule_id") or "").strip()
        if not rule_id or rule_id in seen:
            raise AcademicStageContractError("target hard rule ID is invalid")
        seen.add(rule_id)
        scope = rule.get("readiness_scope")
        locator = str(rule.get("evidence_locator") or "").strip()
        if scope not in {"local_delivery", "author_only_submission"} or not locator:
            raise AcademicStageContractError("target hard rule layer/evidence is invalid")
        author_fact_key = rule.get("author_fact_key")
        if scope == "author_only_submission":
            if author_fact_key not in AUTHOR_ONLY_TARGET_FACT_KEYS:
                raise AcademicStageContractError("target author-only fact key is invalid")
        elif author_fact_key is not None:
            raise AcademicStageContractError("local target rule carries an author fact key")
        item: dict[str, Any] = {
            "obligation_id": f"target-rule:{rule_id}",
            "authority_rule_id": rule_id,
            "hard": True,
            "readiness_scope": scope,
            "authority_binding": {
                "artifact_id": "target_authority",
                "sha256": target_authority_sha256,
            },
            "evidence_locator": locator,
        }
        if scope == "author_only_submission":
            item["author_fact_key"] = author_fact_key
        obligations.append(item)
    return _rehash_contract(
        {
            "contract": "paperspine5.target-obligation-ledger",
            "contract_version": CONTRACT_VERSION,
            "status": "PASS",
            "frozen": True,
            "target_authority_sha256": target_authority_sha256,
            "obligations": sorted(obligations, key=lambda item: item["obligation_id"]),
            "external_action_authorized": False,
            "ledger_sha256": "0" * 64,
        }
    )


def _rebind_current(value: Any, subject: QualitySubject) -> Any:
    """Replace non-authoritative current-revision projections, then rehash them."""

    if isinstance(value, list):
        return [_rebind_current(item, subject) for item in value]
    if not isinstance(value, Mapping):
        return copy.deepcopy(value)
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key == "subject" and isinstance(item, Mapping):
            result[key] = subject.as_dict()
        else:
            result[key] = _rebind_current(item, subject)
    if "task_id" in result:
        result["task_id"] = subject.task_id
    if "revision_id" in result:
        result["revision_id"] = subject.revision_id
    for field in SELF_HASH_FIELDS:
        if field in result:
            unsigned = {key: item for key, item in result.items() if key != field}
            result[field] = canonical_sha256(unsigned)
    return result


def _cumulative_empty(task_id: str, build_id: str, snapshot: Mapping[str, str]) -> dict[str, Any]:
    return {
        "contract": "paperspine5.academic-cumulative-inputs",
        "schema_version": CONTRACT_VERSION,
        "task_id": task_id,
        "product_build_id": build_id,
        "base_snapshot": dict(sorted(snapshot.items())),
        "stage_inputs": {},
        "external_action_authorized": False,
    }


def validate_academic_stage_answer(
    answer: Mapping[str, Any],
    *,
    task_id: str | None = None,
    revision: int | str | None = None,
    current_stage: str | None = None,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not isinstance(answer, Mapping):
        return [_finding("ACADEMIC_ANSWER_INVALID", "answer must be an object")]
    if answer.get("contract") != "paperspine5.academic-stage-answer" or answer.get(
        "schema_version"
    ) != CONTRACT_VERSION:
        findings.append(_finding("ACADEMIC_ANSWER_CONTRACT_INVALID", "answer contract/version is invalid"))
    for field in ("answer_id", "issue_id", "task_id", "stage"):
        if not _nonempty(answer.get(field)):
            findings.append(_finding("ACADEMIC_ANSWER_FIELD_MISSING", f"{field} is required", field))
    if _nonempty(answer.get("answer_id")) and not _SAFE_ID.fullmatch(str(answer["answer_id"])):
        findings.append(_finding("ACADEMIC_ANSWER_ID_INVALID", "answer_id is not portable", "answer_id"))
    if answer.get("stage") not in ACTIVE_STAGES:
        findings.append(_finding("ACADEMIC_STAGE_INVALID", "answer stage is not an active academic gate", "stage"))
    expected_revision = answer.get("expected_revision")
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, (int, str)) or not str(
        expected_revision
    ).isdigit():
        findings.append(_finding("ACADEMIC_REVISION_INVALID", "expected_revision must be non-negative", "expected_revision"))
    payload = answer.get("payload")
    if not isinstance(payload, Mapping):
        findings.append(_finding("ACADEMIC_PAYLOAD_INVALID", "payload must be an object", "payload"))
    else:
        forged = sorted(FORBIDDEN_REQUEST_KEYS & set(payload))
        if forged:
            findings.append(
                _finding(
                    "ACADEMIC_TRUST_INPUT_FORGED",
                    f"client payload cannot provide trust controls: {forged}",
                    "payload",
                )
            )
        if _contains_external_authorization(payload):
            findings.append(_finding("EXTERNAL_ACTION_FORBIDDEN", "answer payload cannot authorize actions"))
        if answer.get("stage") == "awaiting_claim_graph":
            findings.extend(
                validate_claim_graph_edge_contract(
                    payload.get("nodes"), payload.get("edges")
                )
            )
        if answer.get("stage") == "awaiting_figure_intent":
            findings.extend(validate_figure_intent_input_contract(payload))
        if answer.get("stage") == "awaiting_review":
            for error in Draft202012Validator(_PUBLIC_ACADEMIC_STAGE_ANSWER_SCHEMA).iter_errors(answer):
                findings.append(_finding("REVIEW_ANSWER_SCHEMA_INVALID", error.message, ".".join(str(item) for item in error.absolute_path)))
            if set(payload) - {"producer_ids", "initial_review", "revision_diff", "re_review", "closure_revisions", "input_artifacts"}:
                findings.append(_finding("REVIEW_PAYLOAD_FIELDS_INVALID", "J9 payload contains unsupported fields", "payload"))
            if "closure_revisions" in payload and payload["closure_revisions"] != []:
                findings.append(_finding("REVIEW_CLOSURE_ALIAS_UNSUPPORTED", "use top-level revision_diff and re_review, not closure_revisions", "payload.closure_revisions"))
            if ("revision_diff" in payload) != ("re_review" in payload):
                findings.append(_finding("REVIEW_REVISION_PAIR_REQUIRED", "revision_diff and re_review must be supplied together", "payload"))
    if answer.get("external_action_authorized") is not False or _contains_external_authorization(answer):
        findings.append(_finding("EXTERNAL_ACTION_FORBIDDEN", "answer cannot authorize external actions"))
    if task_id is not None and answer.get("task_id") != task_id:
        findings.append(_finding("ACADEMIC_TASK_MISMATCH", "answer task does not match selected task"))
    if revision is not None and str(answer.get("expected_revision")) != str(revision):
        findings.append(_finding("ACADEMIC_REVISION_MISMATCH", "answer revision is stale"))
    if current_stage is not None and answer.get("stage") != current_stage:
        findings.append(_finding("ACADEMIC_STAGE_SKIP_FORBIDDEN", "answer cannot skip or rewind the current gate"))
    if task_id is not None and revision is not None and current_stage is not None:
        expected_issue = f"academic:{task_id}:{revision}:{current_stage}"
        if answer.get("issue_id") != expected_issue:
            findings.append(_finding("ACADEMIC_ISSUE_MISMATCH", "answer is not bound to the current issue"))
    return findings


def validate_figure_intent_input_contract(
    payload: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Validate the public J7 wire shape before a Runner revision can mutate."""

    findings: list[dict[str, str]] = []
    if set(payload) - {"intent", "input_artifacts"}:
        findings.append(
            _finding(
                "FIGURE_INTENT_PAYLOAD_FIELDS_INVALID",
                "J7 payload accepts only intent and optional input_artifacts",
                "payload",
            )
        )
    intent = payload.get("intent")
    if not isinstance(intent, Mapping):
        return findings + [
            _finding("FIGURE_INTENT_INVALID", "intent must be an object", "payload.intent")
        ]
    intent_fields = {"mode", "producer_id", "decision_basis_artifact_ids", "figures"}
    if set(intent) != intent_fields:
        findings.append(
            _finding(
                "FIGURE_INTENT_FIELDS_INVALID",
                "intent requires exactly mode, producer_id, decision_basis_artifact_ids, and figures",
                "payload.intent",
            )
        )
    mode = intent.get("mode")
    figures = intent.get("figures")
    if mode not in {"zero", "keep", "redesign", "create", "mixed"}:
        findings.append(
            _finding("FIGURE_MODE_INVALID", "mode must be zero, keep, redesign, create, or mixed", "payload.intent.mode")
        )
    if not _nonempty(intent.get("producer_id")):
        findings.append(
            _finding("FIGURE_PRODUCER_MISSING", "producer_id is required", "payload.intent.producer_id")
        )
    basis = intent.get("decision_basis_artifact_ids")
    if (
        not isinstance(basis, list)
        or not basis
        or len(basis) != len(set(str(item) for item in basis))
        or any(item not in {"direction_authority", "target_authority", "claim_evidence"} for item in basis)
    ):
        findings.append(
            _finding(
                "FIGURE_DECISION_BASIS_INVALID",
                "decision_basis_artifact_ids must be a unique non-empty subset of frozen W4 authority IDs",
                "payload.intent.decision_basis_artifact_ids",
            )
        )
    if not isinstance(figures, list):
        return findings + [
            _finding("FIGURE_SET_INVALID", "figures must be an array", "payload.intent.figures")
        ]
    if mode == "zero" and figures:
        findings.append(
            _finding("ZERO_FIGURE_HAS_ASSETS", "zero mode requires an empty figures array", "payload.intent.figures")
        )
    if mode in {"keep", "redesign", "create", "mixed"} and not figures:
        findings.append(
            _finding("FIGURE_SET_EMPTY", f"{mode} requires at least one figure", "payload.intent.figures")
        )

    item_fields = {
        "figure_id",
        "mode",
        "panels",
        "reference_plan",
        "current_asset",
        "candidate_assets",
        "independent_comparison",
        "correction_request",
        "target_size_profile",
        "correction_receipt_artifact_id",
        "target_size_legibility_artifact_id",
    }
    asset_fields = {"artifact_id", "sha256", "revision_id"}
    comparison_fields = {
        "reviewer_id",
        "producer_ids",
        "status",
        "reviewed_asset_hashes",
        "decision",
        "selected_sha256",
    }

    def validate_asset(value: Any, path: str) -> None:
        if not isinstance(value, Mapping) or set(value) != asset_fields:
            findings.append(
                _finding(
                    "FIGURE_ASSET_FIELDS_INVALID",
                    "asset requires exactly artifact_id, sha256, and revision_id",
                    path,
                )
            )
            return
        if not _nonempty(value.get("artifact_id")) or not _is_sha256(value.get("sha256")):
            findings.append(
                _finding("FIGURE_ASSET_UNBOUND", "asset ID/hash binding is invalid", path)
            )
        revision_id = value.get("revision_id")
        if isinstance(revision_id, bool) or not isinstance(revision_id, (int, str)) or not str(revision_id).isdigit():
            findings.append(
                _finding("FIGURE_ASSET_REVISION_INVALID", "asset revision_id is invalid", path)
            )

    for index, figure in enumerate(figures):
        path = f"payload.intent.figures[{index}]"
        if not isinstance(figure, Mapping):
            findings.append(_finding("FIGURE_INTENT_INVALID", "figure must be an object", path))
            continue
        unknown = sorted(set(figure) - item_fields)
        if unknown:
            findings.append(
                _finding(
                    "FIGURE_ITEM_FIELDS_INVALID",
                    f"unsupported figure fields: {unknown}",
                    path,
                )
            )
        figure_mode = figure.get("mode") if mode == "mixed" else mode
        if figure_mode not in {"keep", "redesign", "create"}:
            findings.append(
                _finding(
                    "FIGURE_ITEM_MODE_INVALID",
                    "mixed intents require each figure to declare keep, redesign, or create",
                    f"{path}.mode",
                )
            )
            figure_mode = "keep"
        if not _nonempty(figure.get("figure_id")):
            findings.append(_finding("FIGURE_ID_INVALID", "figure_id is required", path))
        panels = figure.get("panels")
        if (
            not isinstance(panels, list)
            or not panels
            or any(not isinstance(panel, Mapping) or set(panel) != {"panel_id"} or not _nonempty(panel.get("panel_id")) for panel in panels)
        ):
            findings.append(
                _finding("FIGURE_PANELS_INVALID", "panels require one or more exact panel_id objects", f"{path}.panels")
            )
        validate_asset(figure.get("reference_plan"), f"{path}.reference_plan")
        if figure_mode in {"keep", "redesign"}:
            validate_asset(figure.get("current_asset"), f"{path}.current_asset")
        candidates = figure.get("candidate_assets")
        if figure_mode in {"redesign", "create"}:
            if not isinstance(candidates, list) or not candidates:
                findings.append(
                    _finding("FIGURE_CANDIDATES_EMPTY", f"{figure_mode} requires candidate_assets", f"{path}.candidate_assets")
                )
            else:
                for candidate_index, candidate in enumerate(candidates):
                    validate_asset(candidate, f"{path}.candidate_assets[{candidate_index}]")
            comparison = figure.get("independent_comparison")
            if not isinstance(comparison, Mapping) or set(comparison) != comparison_fields:
                findings.append(
                    _finding(
                        "FIGURE_COMPARISON_FIELDS_INVALID",
                        "independent_comparison requires exact reviewer, producer, status, reviewed-hash, decision, and selected-hash fields",
                        f"{path}.independent_comparison",
                    )
                )
            else:
                if (
                    not _nonempty(comparison.get("reviewer_id"))
                    or not isinstance(comparison.get("producer_ids"), list)
                    or not comparison.get("producer_ids")
                    or comparison.get("status") != "PASS"
                    or comparison.get("decision")
                    not in {"keep_original", "no_clear_winner", "redesign_wins", "candidate_wins"}
                    or not _is_sha256(comparison.get("selected_sha256"))
                    or not isinstance(comparison.get("reviewed_asset_hashes"), list)
                    or not comparison.get("reviewed_asset_hashes")
                    or any(not _is_sha256(item) for item in comparison.get("reviewed_asset_hashes", []))
                ):
                    findings.append(
                        _finding(
                            "FIGURE_COMPARISON_INVALID",
                            "independent comparison values are incomplete or invalid",
                            f"{path}.independent_comparison",
                        )
                    )
    return findings


def validate_contribution_confirmation(
    confirmation: Mapping[str, Any],
    *,
    task_id: str | None = None,
    revision: int | str | None = None,
    issue_id: str | None = None,
    preparation_sha256: str | None = None,
) -> list[dict[str, str]]:
    """Validate the browser's phase-2 intent before any Runner transaction."""

    findings: list[dict[str, str]] = []
    if not isinstance(confirmation, Mapping):
        return [_finding("CONTRIBUTION_CONFIRMATION_INVALID", "confirmation must be an object")]
    allowed = {
        "contract",
        "schema_version",
        "confirmation_id",
        "issue_id",
        "task_id",
        "expected_revision",
        "preparation_sha256",
        "decisions",
        "external_action_authorized",
    }
    extras = sorted(set(confirmation) - allowed)
    if extras:
        findings.append(
            _finding(
                "CONTRIBUTION_CONFIRMATION_FIELDS_INVALID",
                f"browser confirmation contains unsupported fields: {extras}",
            )
        )
    if confirmation.get("contract") != "paperspine5.contribution-confirmation" or confirmation.get(
        "schema_version"
    ) != CONTRACT_VERSION:
        findings.append(
            _finding(
                "CONTRIBUTION_CONFIRMATION_CONTRACT_INVALID",
                "confirmation contract/version is invalid",
            )
        )
    confirmation_id = confirmation.get("confirmation_id")
    if not _nonempty(confirmation_id) or not _SAFE_ID.fullmatch(str(confirmation_id)):
        findings.append(
            _finding(
                "CONTRIBUTION_CONFIRMATION_ID_INVALID",
                "confirmation_id is missing or not portable",
                "confirmation_id",
            )
        )
    decisions = confirmation.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        findings.append(
            _finding(
                "CONTRIBUTION_DECISIONS_MISSING",
                "every prepared candidate needs one decision",
                "decisions",
            )
        )
    else:
        for index, decision in enumerate(decisions):
            path = f"decisions[{index}]"
            if not isinstance(decision, Mapping):
                findings.append(
                    _finding("CONTRIBUTION_DECISION_INVALID", "decision must be an object", path)
                )
                continue
            allowed_decision = {"candidate_id", "choice", "reason", "revised_statement"}
            if set(decision) - allowed_decision:
                findings.append(
                    _finding(
                        "CONTRIBUTION_DECISION_INVALID",
                        "decision contains unsupported fields",
                        path,
                    )
                )
            if not _nonempty(decision.get("candidate_id")):
                findings.append(
                    _finding("CANDIDATE_ID_INVALID", "candidate_id is required", path)
                )
            choice = decision.get("choice")
            if choice not in {"accept", "revise", "reject"}:
                findings.append(
                    _finding(
                        "CONTRIBUTION_CHOICE_INVALID",
                        "choice must be accept, revise, or reject",
                        path,
                    )
                )
            if not _nonempty(decision.get("reason")):
                findings.append(
                    _finding(
                        "CONTRIBUTION_REASON_MISSING",
                        "decision reason is required",
                        path,
                    )
                )
            if choice == "revise" and not _nonempty(decision.get("revised_statement")):
                findings.append(
                    _finding(
                        "CONTRIBUTION_STATEMENT_MISSING",
                        "revised_statement is required for revise",
                        path,
                    )
                )
    expected_revision = confirmation.get("expected_revision")
    if isinstance(expected_revision, bool) or not isinstance(
        expected_revision, (int, str)
    ) or not str(expected_revision).isdigit():
        findings.append(
            _finding(
                "CONTRIBUTION_CONFIRMATION_REVISION_INVALID",
                "expected_revision must be non-negative",
            )
        )
    if not _is_sha256(confirmation.get("preparation_sha256")):
        findings.append(
            _finding(
                "CONTRIBUTION_PREPARATION_HASH_INVALID",
                "preparation_sha256 must be lowercase 64-hex",
            )
        )
    if confirmation.get("external_action_authorized") is not False or _contains_external_authorization(
        confirmation
    ):
        findings.append(
            _finding(
                "EXTERNAL_ACTION_FORBIDDEN",
                "contribution confirmation cannot authorize external actions",
            )
        )
    for field, observed, expected in (
        ("task_id", confirmation.get("task_id"), task_id),
        ("issue_id", confirmation.get("issue_id"), issue_id),
        ("expected_revision", str(expected_revision), None if revision is None else str(revision)),
        ("preparation_sha256", confirmation.get("preparation_sha256"), preparation_sha256),
    ):
        if expected is not None and observed != expected:
            findings.append(
                _finding(
                    f"CONTRIBUTION_CONFIRMATION_{field.upper()}_MISMATCH",
                    f"confirmation {field} is stale or belongs to another issue",
                    field,
                )
            )
    return findings


def _normalize_descriptor(
    raw: Mapping[str, Any],
    *,
    subject: QualitySubject,
    stage: str,
    product_build_id: str,
    producer_id: str,
    source_service: str,
) -> dict[str, Any]:
    payload = raw.get("payload")
    if not isinstance(payload, Mapping):
        raise AcademicStageContractError("stage service descriptor payload must be an object")
    rebound = _rebind_current(payload, subject)
    data = canonical_payload_bytes(rebound)
    artifact_type = str(raw.get("artifact_type") or "")
    return {
        "contract": "paperspine5.stage-artifact-descriptor",
        "schema_version": CONTRACT_VERSION,
        "artifact_id": str(raw.get("artifact_id") or ""),
        "artifact_type": artifact_type,
        "subject": subject.as_dict(),
        "payload": rebound,
        "payload_sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "authority": {"kind": "academic-stage-orchestrator", "producer_id": producer_id},
        "metadata": {
            "product_build_id": product_build_id,
            "stage": STAGE_CODES[stage],
            "encoding": "canonical-json-newline.v1",
            "service_version": CONTRACT_VERSION,
            "source_service": source_service,
        },
        "requires_quality_recording": artifact_type == "quality.readiness-verdict",
        "external_action_authorized": False,
    }


def _result(
    *,
    task_id: str,
    revision: int | str,
    build_id: str,
    stage: str,
    status: str,
    blockers: Sequence[Mapping[str, str]],
    warnings: Sequence[Mapping[str, str]],
    descriptors: Sequence[Mapping[str, Any]],
    next_stage: str,
    invalidations: Sequence[str],
    cumulative_inputs: Mapping[str, Any],
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "contract": "paperspine5.academic-stage-result",
        "schema_version": CONTRACT_VERSION,
        "task_id": task_id,
        "revision_id": str(revision),
        "product_build_id": build_id,
        "stage": stage,
        "status": status,
        "blockers": [dict(item) for item in blockers],
        "warnings": [dict(item) for item in warnings],
        "descriptors": [copy.deepcopy(dict(item)) for item in descriptors],
        "next_stage": next_stage,
        "invalidated_artifacts": sorted(set(invalidations)),
        "cumulative_inputs": copy.deepcopy(dict(cumulative_inputs)),
        "external_action_authorized": False,
    }
    value["result_sha256"] = canonical_sha256(value)
    return value


def validate_academic_stage_result(result: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if result.get("contract") != "paperspine5.academic-stage-result" or result.get(
        "schema_version"
    ) != CONTRACT_VERSION:
        findings.append(_finding("ACADEMIC_RESULT_CONTRACT_INVALID", "result contract/version is invalid"))
    unsigned = {key: value for key, value in result.items() if key != "result_sha256"}
    if result.get("result_sha256") != canonical_sha256(unsigned):
        findings.append(_finding("ACADEMIC_RESULT_HASH_INVALID", "result_sha256 does not recompute"))
    if result.get("status") not in {"PASS", "BLOCKED"}:
        findings.append(_finding("ACADEMIC_RESULT_STATUS_INVALID", "result status is invalid"))
    if result.get("stage") not in ACTIVE_STAGES or result.get("next_stage") not in STAGES:
        findings.append(_finding("ACADEMIC_RESULT_STAGE_INVALID", "result stage transition is invalid"))
    descriptors = result.get("descriptors")
    if not isinstance(descriptors, list):
        findings.append(_finding("ACADEMIC_RESULT_DESCRIPTORS_INVALID", "descriptors must be a list"))
    else:
        for index, descriptor in enumerate(descriptors):
            if not isinstance(descriptor, Mapping):
                findings.append(_finding("ACADEMIC_DESCRIPTOR_INVALID", "descriptor must be an object", f"descriptors[{index}]"))
                continue
            findings.extend(validate_stage_artifact_descriptor(descriptor))
            required = descriptor.get("requires_quality_recording")
            expected = descriptor.get("artifact_type") == "quality.readiness-verdict"
            if required is not expected:
                findings.append(_finding("QUALITY_RECORDING_ROUTE_INVALID", "quality routing flag is wrong", f"descriptors[{index}]"))
    if result.get("external_action_authorized") is not False or _contains_external_authorization(result):
        findings.append(_finding("EXTERNAL_ACTION_FORBIDDEN", "result cannot authorize external actions"))
    return findings


@dataclass(frozen=True)
class AcademicStageOrchestrator:
    """Compose J4--J11 pure services for one future Runner CAS transition."""

    product_build_id: str
    producer_id: str = "paperspine5.academic-stage-orchestrator.1.0"

    def __post_init__(self) -> None:
        if not _nonempty(self.product_build_id) or not _nonempty(self.producer_id):
            raise AcademicStageContractError("product_build_id and producer_id are required")

    def _blocked(
        self,
        *,
        task_id: str,
        revision: int | str,
        stage: str,
        blockers: Sequence[Mapping[str, str]],
        cumulative: Mapping[str, Any],
        next_stage: str | None = None,
        invalidations: Sequence[str] = (),
        warnings: Sequence[Mapping[str, str]] = (),
        descriptors: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        return _result(
            task_id=task_id,
            revision=revision,
            build_id=self.product_build_id,
            stage=stage,
            status="BLOCKED",
            blockers=blockers,
            warnings=warnings,
            descriptors=descriptors,
            next_stage=next_stage or stage,
            invalidations=invalidations,
            cumulative_inputs=cumulative,
        )

    def advance(
        self,
        *,
        task_id: str,
        revision: int | str,
        answer_revision: int | str | None = None,
        current_stage: str,
        cumulative_inputs: Mapping[str, Any],
        answer: Mapping[str, Any],
        base_artifacts: Mapping[str, Mapping[str, Any]],
        registered_artifacts: Mapping[str, str] | None = None,
        trusted_figure_master_receipt: Mapping[str, Any] | None = None,
        registered_final_mapping_context: Mapping[str, Any] | None = None,
        retained_reference_plans: Mapping[str, str] | None = None,
        evaluation_time: str | None = None,
    ) -> dict[str, Any]:
        """Replay J4 through the answered gate without accepting caller trust maps."""

        if not _nonempty(task_id) or isinstance(revision, bool) or not str(revision).isdigit():
            raise AcademicStageContractError("task_id and non-negative revision are required")
        if current_stage not in ACTIVE_STAGES:
            raise AcademicStageContractError("current_stage is not an active academic gate")
        answer_subject_revision = revision if answer_revision is None else answer_revision
        if isinstance(answer_subject_revision, bool) or not str(
            answer_subject_revision
        ).isdigit():
            raise AcademicStageContractError("answer_revision must be non-negative")
        answer_findings = validate_academic_stage_answer(
            answer,
            task_id=task_id,
            revision=answer_subject_revision,
            current_stage=current_stage,
        )
        empty = _cumulative_empty(task_id, self.product_build_id, {})
        if answer_findings:
            return self._blocked(
                task_id=task_id,
                revision=revision,
                stage=current_stage,
                blockers=answer_findings,
                cumulative=empty,
            )

        base_hashes: dict[str, str] = {}
        material_registered_hashes: dict[str, str] = {}
        reference_plans: dict[str, dict[str, Any]] = {}
        trusted_attestations: dict[str, str] = {}
        base_findings: list[dict[str, str]] = []
        if not isinstance(base_artifacts, Mapping) or not base_artifacts:
            base_findings.append(_finding("BASE_ARTIFACTS_MISSING", "actual base artifact payloads are required"))
        else:
            for artifact_id, payload in sorted(base_artifacts.items()):
                path = f"base_artifacts.{artifact_id}"
                if not _nonempty(artifact_id) or not _SAFE_ID.fullmatch(str(artifact_id)):
                    base_findings.append(_finding("BASE_ARTIFACT_ID_INVALID", "artifact ID is invalid", path))
                    continue
                if not isinstance(payload, Mapping):
                    base_findings.append(_finding("BASE_ARTIFACT_PAYLOAD_INVALID", "actual artifact payload must be an object", path))
                    continue
                if _contains_external_authorization(payload):
                    base_findings.append(_finding("EXTERNAL_ACTION_FORBIDDEN", "base artifact cannot authorize actions", path))
                    continue
                try:
                    base_hashes[str(artifact_id)] = _logical_artifact_hash(
                        payload,
                        trusted_figure_master_receipt=trusted_figure_master_receipt,
                    )
                except AcademicStageContractError as exc:
                    base_findings.append(_finding("BASE_ARTIFACT_HASH_INVALID", str(exc), path))
                    continue
                if payload.get("contract") == "paperspine5.figure-reference-plan":
                    reference_plans[str(artifact_id)] = copy.deepcopy(dict(payload))
                if (
                    artifact_id == "materials.source-ledger"
                    and _is_sha256(payload.get("snapshot_sha256"))
                ):
                    base_hashes[str(artifact_id)] = str(payload["snapshot_sha256"])
                    for entry in payload.get("entries", []):
                        if (
                            isinstance(entry, Mapping)
                            and _nonempty(entry.get("source_id"))
                            and _is_sha256(entry.get("sha256"))
                        ):
                            base_hashes[f"source:{entry['source_id']}"] = str(
                                entry["sha256"]
                            )
                            material_registered_hashes[
                                str(entry["source_id"])
                            ] = str(entry["sha256"])
                            material_registered_hashes[
                                f"source:{entry['source_id']}"
                            ] = str(entry["sha256"])
                elif artifact_id == "runner.run-contract":
                    base_hashes[str(artifact_id)] = canonical_input_sha256(
                        {
                            "contract": payload.get("contract"),
                            "schema_version": payload.get("schema_version"),
                            "product_build_id": payload.get("product_build_id"),
                            "material_snapshot_sha256": payload.get(
                                "material_snapshot_sha256"
                            ),
                            "configuration": payload.get("configuration"),
                            "external_action_authorized": payload.get(
                                "external_action_authorized"
                            ),
                        }
                    )
                elif (
                    artifact_id == "readiness_obligations"
                    and payload.get("contract")
                    == "paperspine5.readiness-obligation-manifest"
                ):
                    base_hashes[str(artifact_id)] = str(payload["manifest_sha256"])
                elif payload.get("contract") == "paperspine5.figure-correction-receipt":
                    try:
                        validated = validate_figure_correction_receipt(dict(payload))
                    except FigureCorrectionError as exc:
                        base_findings.append(
                            _finding(
                                "FIGURE_CORRECTION_RECEIPT_INVALID",
                                str(exc),
                                path,
                            )
                        )
                    else:
                        base_hashes[str(artifact_id)] = str(
                            validated["receipt_sha256"]
                        )
                        output_id = f"figure-output.{_safe_evidence_token(str(validated['figure_id']))}"
                        base_hashes[output_id] = str(validated["output"]["sha256"])
                elif payload.get("contract") == "paperspine5.target-size-legibility-receipt":
                    try:
                        validated = validate_target_size_legibility_receipt(
                            dict(payload), require_pass=True
                        )
                    except FigureCorrectionError as exc:
                        base_findings.append(
                            _finding(
                                "TARGET_SIZE_LEGIBILITY_RECEIPT_INVALID",
                                str(exc),
                                path,
                            )
                        )
                    else:
                        base_hashes[str(artifact_id)] = str(
                            validated["receipt_sha256"]
                        )
                attestation_id = payload.get("attestation_input_id")
                if attestation_id == artifact_id and all(
                    _nonempty(payload.get(key))
                    for key in ("principal_id", "session_id", "run_id", "independence_group")
                ):
                    provenance = identity_provenance_sha256(payload)
                    if payload.get("provenance_sha256") != provenance:
                        base_findings.append(_finding("BASE_IDENTITY_PROVENANCE_INVALID", "identity provenance does not recompute", path))
                    else:
                        base_hashes[str(artifact_id)] = provenance
                        trusted_attestations[str(artifact_id)] = provenance
        registered_hashes = {
            str(artifact_id): str(sha256)
            for artifact_id, sha256 in (registered_artifacts or {}).items()
            if _nonempty(artifact_id) and _is_sha256(sha256)
        }
        registered_hashes.update(material_registered_hashes)
        # Frozen public style sources are immutable academic base inputs, not
        # material-ledger rows.  Include their canonical payload hashes in the
        # subject registry so a reference-guided J7 plan can be revalidated on
        # the same task after a zero-figure-to-create revision.
        for artifact_id, artifact_payload in base_artifacts.items():
            if (
                isinstance(artifact_id, str)
                and isinstance(artifact_payload, Mapping)
                and artifact_payload.get("contract") == "paperspine5.public-source-freeze"
            ):
                registered_hashes.setdefault(
                    artifact_id,
                    canonical_input_sha256(dict(artifact_payload)),
                )
        for artifact_id, plan in reference_plans.items():
            plan_subject = plan.get("subject")
            plan_revision = (
                plan_subject.get("runner_revision")
                if isinstance(plan_subject, Mapping)
                else None
            )
            expected_plan_subject = {
                "task_id": task_id,
                "revision_id": plan_revision,
                "material_snapshot_sha256": base_hashes.get(
                    "materials.source-ledger"
                ),
            }
            try:
                validated_plan = validate_figure_reference_plan(
                    plan,
                    expected_subject=expected_plan_subject,
                    registered_artifacts=registered_hashes,
                    trusted_actor_receipt=trusted_figure_master_receipt,
                )
                if (
                    current_stage == "awaiting_figure_intent"
                    and str(plan_revision) != str(answer_subject_revision)
                    and (retained_reference_plans or {}).get(artifact_id) != validated_plan["plan_sha256"]
                ):
                    raise FigureReferenceMappingError(
                        "reference plan was not frozen at the current pre-execution revision"
                    )
            except FigureReferenceMappingError as exc:
                base_findings.append(
                    _finding(
                        "BASE_FIGURE_REFERENCE_PLAN_INVALID",
                        str(exc),
                        f"base_artifacts.{artifact_id}",
                    )
                )
                continue
            base_hashes[artifact_id] = str(validated_plan["plan_sha256"])
            registered_hashes[artifact_id] = str(validated_plan["plan_sha256"])
            for reference in validated_plan["reference_assets"]:
                for identifier, hash_field in (
                    (reference["source_id"], "source_content_sha256"),
                    (reference["asset_id"], "asset_sha256"),
                    (reference["preview_artifact_id"], "preview_sha256"),
                ):
                    base_hashes[str(identifier)] = str(reference[hash_field])

        empty = _cumulative_empty(task_id, self.product_build_id, base_hashes)
        if base_findings:
            return self._blocked(
                task_id=task_id,
                revision=revision,
                stage=current_stage,
                blockers=base_findings,
                cumulative=empty,
            )
        delegation, delegation_findings = _verified_local_delegation(
            base_artifacts,
            task_id=task_id,
            run_contract_sha256=base_hashes.get("runner.run-contract"),
            evaluation_time=evaluation_time,
        )
        if delegation_findings:
            return self._blocked(
                task_id=task_id,
                revision=revision,
                stage=current_stage,
                blockers=delegation_findings,
                cumulative=empty,
            )
        material_figure_set, material_figure_findings = _validated_material_figure_set(
            base_artifacts.get("materials.figure-set"),
            base_artifacts.get("materials.source-ledger"),
            task_id=task_id,
        )

        cumulative_findings: list[dict[str, str]] = []
        if cumulative_inputs:
            if cumulative_inputs.get("contract") != "paperspine5.academic-cumulative-inputs" or cumulative_inputs.get(
                "schema_version"
            ) != CONTRACT_VERSION:
                cumulative_findings.append(_finding("CUMULATIVE_CONTRACT_INVALID", "cumulative inputs contract/version is invalid"))
            if cumulative_inputs.get("task_id") != task_id:
                cumulative_findings.append(_finding("CUMULATIVE_TASK_MISMATCH", "cumulative inputs belong to another task"))
            if cumulative_inputs.get("product_build_id") != self.product_build_id:
                cumulative_findings.append(_finding("CUMULATIVE_BUILD_MISMATCH", "cumulative inputs were produced by another build"))
            if cumulative_inputs.get("external_action_authorized") is not False or _contains_external_authorization(
                cumulative_inputs
            ):
                cumulative_findings.append(_finding("EXTERNAL_ACTION_FORBIDDEN", "cumulative inputs cannot authorize actions"))
            previous_snapshot = cumulative_inputs.get("base_snapshot")
            if isinstance(previous_snapshot, Mapping):
                changed = sorted(
                    {
                        key
                        for key in set(previous_snapshot)
                        if previous_snapshot.get(key) != base_hashes.get(key)
                    }
                )
                allowed_mutations = STAGE_MUTABLE_BASE_ARTIFACTS.get(
                    current_stage, frozenset()
                )
                blocking_changes = sorted(set(changed) - set(allowed_mutations))
                # J8 owns the concrete manuscript build outputs.  Their
                # semantic IDs commonly carry a revision suffix (for example
                # ``manuscript_source_r57``), so the narrow exception must be
                # prefix based rather than tied to one fixture's ID spelling.
                if current_stage == "awaiting_canonical":
                    blocking_changes = [
                        key
                        for key in blocking_changes
                        if not key.startswith(("manuscript_source", "manuscript_pdf", "manuscript_word"))
                    ]
                if current_stage == "awaiting_package":
                    blocking_changes = [
                        key
                        for key in blocking_changes
                        if not key.startswith(("bundle_archive", "bundle_archive_delivery"))
                    ]
            else:
                changed = []
                blocking_changes = []
            if blocking_changes:
                return self._blocked(
                    task_id=task_id,
                    revision=revision,
                    stage=current_stage,
                    blockers=[
                        _finding(
                            "BASE_ARTIFACT_MUTATION_REQUIRES_RESEARCH",
                            f"actual base artifacts changed; restart J4: {blocking_changes}",
                            "base_artifacts",
                        )
                    ],
                    cumulative=empty,
                    next_stage="awaiting_research",
                    invalidations=INVALIDATE_ALL,
                )
            raw_stage_inputs = cumulative_inputs.get("stage_inputs")
            stage_inputs = copy.deepcopy(dict(raw_stage_inputs)) if isinstance(raw_stage_inputs, Mapping) else {}
        else:
            stage_inputs = {}
        if cumulative_findings:
            return self._blocked(
                task_id=task_id,
                revision=revision,
                stage=current_stage,
                blockers=cumulative_findings,
                cumulative=empty,
            )

        current_index = ACTIVE_STAGES.index(current_stage)
        if material_figure_findings:
            return self._blocked(
                task_id=task_id,
                revision=revision,
                stage=current_stage,
                blockers=material_figure_findings,
                cumulative=empty,
                next_stage="awaiting_research",
                invalidations=INVALIDATE_ALL,
            )
        unknown = sorted(set(stage_inputs) - set(ACTIVE_STAGES))
        missing = [stage for stage in ACTIVE_STAGES[:current_index] if stage not in stage_inputs]
        future = [stage for stage in ACTIVE_STAGES[current_index + 1 :] if stage in stage_inputs]
        # A same-task J7 re-entry after an older J8 attempt legitimately leaves
        # the superseded canonical input in the cumulative record.  Invalidate
        # that future stage before replaying the selected figure intent; do not
        # treat it as a caller stage skip.  Other future-stage shapes remain a
        # hard blocker.
        if (
            current_stage == "awaiting_figure_intent"
            and future == ["awaiting_canonical"]
            and isinstance(stage_inputs.get("awaiting_canonical"), Mapping)
            and isinstance(stage_inputs["awaiting_canonical"].get("canonical_bundle"), Mapping)
        ):
            stage_inputs.pop("awaiting_canonical", None)
            future = []
        forged_stages = [
            stage
            for stage, payload in stage_inputs.items()
            if isinstance(payload, Mapping) and FORBIDDEN_REQUEST_KEYS & set(payload)
        ]
        if unknown or missing or future or forged_stages:
            blockers = []
            if unknown:
                blockers.append(_finding("CUMULATIVE_STAGE_UNKNOWN", f"unknown stage inputs: {unknown}"))
            if missing:
                blockers.append(_finding("CUMULATIVE_STAGE_GAP", f"missing completed stage inputs: {missing}"))
            if future:
                blockers.append(_finding("CUMULATIVE_STAGE_SKIP", f"future stage inputs are not licensed: {future}"))
            if forged_stages:
                blockers.append(
                    _finding(
                        "CUMULATIVE_TRUST_INPUT_FORGED",
                        f"persisted stage inputs contain caller trust controls: {sorted(forged_stages)}",
                    )
                )
            return self._blocked(
                task_id=task_id,
                revision=revision,
                stage=current_stage,
                blockers=blockers,
                cumulative=empty,
            )
        stage_inputs[current_stage] = copy.deepcopy(dict(answer["payload"]))
        cumulative = _cumulative_empty(task_id, self.product_build_id, base_hashes)
        cumulative["stage_inputs"] = stage_inputs
        revision_context = cumulative_inputs.get("revision_context")
        if isinstance(revision_context, Mapping):
            prior_review = revision_context.get("initial_review")
            prior_head = revision_context.get("manuscript_head")
            if (
                revision_context.get("contract") != "paperspine5.publication-revision-context"
                or not isinstance(prior_review, Mapping)
                or not isinstance(prior_head, Mapping)
                or not isinstance(prior_review.get("subject"), Mapping)
                or prior_review.get("subject", {}).get("task_id") != task_id
                or prior_review.get("manuscript_head_sha256") != prior_head.get("head_sha256")
                or _rehash_contract(prior_review) != prior_review
                or _rehash_contract(prior_head) != prior_head
            ):
                return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                    blockers=[_finding("REVISION_CONTEXT_INVALID", "persisted revision review/head is invalid")], cumulative=cumulative)
            cumulative["revision_context"] = copy.deepcopy(dict(revision_context))

        descriptors: list[dict[str, Any]] = []
        warnings: list[dict[str, str]] = []
        invalidations: set[str] = set()
        trusted: dict[str, str] = dict(base_hashes)
        research_service = ResearchArgumentStageService(
            self.product_build_id, producer_id=self.producer_id
        )

        research = copy.deepcopy(dict(stage_inputs["awaiting_research"]))
        source_ids: list[str] = []
        for index, source in enumerate(research.get("sources", [])):
            if not isinstance(source, dict):
                continue
            artifact_id = f"source:{source.get('source_id')}"
            source_ids.append(artifact_id)
            if source.get("content_sha256") != base_hashes.get(artifact_id):
                return self._blocked(
                    task_id=task_id,
                    revision=revision,
                    stage=current_stage,
                    blockers=[_finding("SOURCE_PAYLOAD_HASH_FORGED", "source hash differs from actual base payload", f"sources[{index}]")],
                    cumulative=empty,
                    next_stage="awaiting_research",
                    invalidations=INVALIDATE_ALL,
                )
        direction = research.get("direction") if isinstance(research.get("direction"), Mapping) else {}
        coverage = research.get("coverage") if isinstance(research.get("coverage"), Mapping) else {}
        target = research.get("target") if isinstance(research.get("target"), Mapping) else {}
        research["research_scope_sha256"] = compute_research_scope(
            direction.get("questions", []), target, coverage.get("required_topics", [])
        )
        research["research_snapshot_sha256"] = compute_research_snapshot(research)
        if isinstance(research.get("challenger"), dict):
            research["challenger"]["research_snapshot_sha256"] = research[
                "research_snapshot_sha256"
            ]
        research_hashes = {
            **base_hashes,
            "research_scope": research["research_scope_sha256"],
            "target_research_snapshot": research["research_snapshot_sha256"],
        }
        subject = QualitySubject(task_id, str(revision), research_hashes)
        research["subject"] = subject.as_dict()
        response = research_service.accept_frozen_research(
            subject,
            research,
            as_of_date=str(research.get("as_of_date") or ""),
            trusted_artifacts={key: trusted[key] for key in source_ids if key in trusted},
            trusted_attestations=trusted_attestations,
        )
        if response["status"] != "true":
            cumulative["stage_inputs"] = {}
            return self._blocked(
                task_id=task_id,
                revision=revision,
                stage=current_stage,
                blockers=response["blockers"],
                warnings=response["warnings"],
                cumulative=cumulative,
                next_stage="awaiting_research",
                invalidations=response["invalidated_artifacts"],
            )
        for raw in response["artifacts"]:
            descriptor = _normalize_descriptor(
                raw,
                subject=subject,
                stage="awaiting_research",
                product_build_id=self.product_build_id,
                producer_id=self.producer_id,
                source_service="research-argument-service",
            )
            descriptors.append(descriptor)
            trusted[descriptor["artifact_id"]] = descriptor["payload_sha256"]
        target_authority_payload = next(
            descriptor["payload"]
            for descriptor in descriptors
            if descriptor["artifact_id"] == "target_authority"
        )
        host_target_obligations = _derive_target_obligation_ledger(
            target_authority_payload,
            trusted["target_authority"],
        )
        warnings.extend(response["warnings"])
        if current_stage == "awaiting_research":
            return _result(
                task_id=task_id,
                revision=revision,
                build_id=self.product_build_id,
                stage=current_stage,
                status="PASS",
                blockers=[],
                warnings=warnings,
                descriptors=descriptors,
                next_stage=NEXT_STAGE[current_stage],
                invalidations=sorted(invalidations),
                cumulative_inputs=cumulative,
            )

        contribution = copy.deepcopy(dict(stage_inputs["awaiting_contribution"]))
        contribution_hashes = {
            **research_hashes,
            "direction_authority": trusted["direction_authority"],
            "target_authority": trusted["target_authority"],
        }
        subject = QualitySubject(task_id, str(revision), contribution_hashes)
        if (
            current_stage == "awaiting_contribution"
            and contribution.get("contract")
            == "paperspine5.contribution-candidate-preparation"
        ):
            preparation = copy.deepcopy(contribution)
            preparation["subject"] = subject.as_dict()
            preparation["authority_bindings"] = {
                artifact_id: contribution_hashes[artifact_id]
                for artifact_id in (
                    "direction_authority",
                    "target_authority",
                    "materials.source-ledger",
                )
                if artifact_id in contribution_hashes
            }
            response = research_service.prepare_contribution_candidates(
                subject,
                preparation,
                trusted_artifacts=trusted,
            )
            # J5 is not complete until Product Web records a real user choice.
            # Keep the cumulative completed-stage ledger at J4 while persisting
            # the candidate descriptor as a recoverable, separately confirmed
            # phase-1 artifact.
            cumulative["stage_inputs"] = {
                key: value
                for key, value in stage_inputs.items()
                if ACTIVE_STAGES.index(key) < 1
            }
            if response["status"] != "true":
                return self._blocked(
                    task_id=task_id,
                    revision=revision,
                    stage=current_stage,
                    blockers=response["blockers"],
                    cumulative=cumulative,
                    next_stage="awaiting_contribution",
                )
            raw = response["artifacts"][0]
            descriptor = _normalize_descriptor(
                raw,
                subject=subject,
                stage="awaiting_contribution",
                product_build_id=self.product_build_id,
                producer_id=self.producer_id,
                source_service="research-argument-service",
            )
            return _result(
                task_id=task_id,
                revision=revision,
                build_id=self.product_build_id,
                stage=current_stage,
                status="PASS",
                blockers=[],
                warnings=warnings,
                descriptors=[descriptor],
                next_stage="awaiting_contribution",
                invalidations=[],
                cumulative_inputs=cumulative,
            )
        contribution["subject"] = subject.as_dict()
        contribution["authority_bindings"] = {
            artifact_id: contribution_hashes[artifact_id]
            for artifact_id in (
                "direction_authority",
                "target_authority",
                "materials.source-ledger",
            )
            if artifact_id in contribution_hashes
        }
        delegated_kinds: dict[str, list[str]] = {
            "contribution_selection": [],
            "motivation_selection": [],
        }
        delegated_contribution = (
            delegation is not None and contribution.get("author_identity") is None
        )
        if delegated_contribution:
            candidate_kinds = {
                str(item.get("candidate_id")): str(item.get("kind"))
                for item in contribution.get("candidates", [])
                if isinstance(item, Mapping)
            }
            for choice in contribution.get("decisions", []):
                if not isinstance(choice, Mapping) or choice.get("choice") not in {
                    "accept",
                    "revise",
                }:
                    continue
                candidate_id = str(choice.get("candidate_id") or "")
                kind = candidate_kinds.get(candidate_id)
                if kind == "motivation":
                    delegated_kinds["motivation_selection"].append(candidate_id)
                elif kind in {"contribution", "limitation", "boundary"}:
                    delegated_kinds["contribution_selection"].append(candidate_id)
            delegation_blockers = [
                blocker
                for decision_class, candidate_ids in delegated_kinds.items()
                if candidate_ids
                for blocker in _delegation_blocker(
                    delegation, decision_class, stage="awaiting_contribution"
                )
            ]
            if delegation_blockers:
                return self._blocked(
                    task_id=task_id,
                    revision=revision,
                    stage=current_stage,
                    blockers=delegation_blockers,
                    cumulative=cumulative,
                    next_stage="awaiting_contribution",
                )
            contribution.pop("author_identity", None)
        response = research_service.decide_contribution(
            subject,
            contribution,
            trusted_artifacts=trusted,
            trusted_attestations=trusted_attestations,
            trusted_delegation=delegation if delegated_contribution else None,
        )
        if response["status"] != "true":
            cumulative["stage_inputs"] = {
                key: value for key, value in stage_inputs.items() if ACTIVE_STAGES.index(key) < 1
            }
            return self._blocked(
                task_id=task_id,
                revision=revision,
                stage=current_stage,
                blockers=response["blockers"],
                cumulative=cumulative,
                next_stage="awaiting_contribution",
            )
        raw = response["artifacts"][0]
        descriptor = _normalize_descriptor(
            raw,
            subject=subject,
            stage="awaiting_contribution",
            product_build_id=self.product_build_id,
            producer_id=self.producer_id,
            source_service="research-argument-service",
        )
        descriptors.append(descriptor)
        trusted[descriptor["artifact_id"]] = descriptor["payload_sha256"]
        if delegated_contribution:
            for decision_class, candidate_ids in delegated_kinds.items():
                if not candidate_ids:
                    continue
                selected = set(candidate_ids)
                raw_receipt = _delegated_decision_descriptor(
                    delegation=delegation,
                    decision_class=decision_class,
                    stage="awaiting_contribution",
                    action_id="selection",
                    subject=subject,
                    choice={
                        "candidates": [
                            item
                            for item in contribution.get("candidates", [])
                            if isinstance(item, Mapping)
                            and str(item.get("candidate_id")) in selected
                        ],
                        "decisions": [
                            item
                            for item in contribution.get("decisions", [])
                            if isinstance(item, Mapping)
                            and str(item.get("candidate_id")) in selected
                        ],
                    },
                    evidence_bindings=contribution_hashes,
                )
                descriptors.append(
                    _normalize_descriptor(
                        raw_receipt,
                        subject=subject,
                        stage="awaiting_contribution",
                        product_build_id=self.product_build_id,
                        producer_id=self.producer_id,
                        source_service="academic-stage-orchestrator",
                    )
                )
        if current_stage == "awaiting_contribution":
            return _result(
                task_id=task_id,
                revision=revision,
                build_id=self.product_build_id,
                stage=current_stage,
                status="PASS",
                blockers=[],
                warnings=warnings,
                descriptors=descriptors,
                next_stage=NEXT_STAGE[current_stage],
                invalidations=sorted(invalidations),
                cumulative_inputs=cumulative,
            )

        graph = copy.deepcopy(dict(stage_inputs["awaiting_claim_graph"]))
        graph_hashes = {
            **contribution_hashes,
            "contribution_boundary_decision": trusted["contribution_boundary_decision"],
        }
        subject = QualitySubject(task_id, str(revision), graph_hashes)
        graph["subject"] = subject.as_dict()
        graph["contribution_decision"] = {
            "artifact_id": "contribution_boundary_decision",
            "sha256": graph_hashes["contribution_boundary_decision"],
        }
        derived_sources = {
            "direction_authority",
            "target_authority",
            "contribution_boundary_decision",
        }
        for index, node in enumerate(graph.get("nodes", [])):
            if not isinstance(node, dict):
                continue
            artifact_id = str(node.get("source_artifact_id") or "")
            expected = graph_hashes.get(artifact_id)
            if artifact_id in derived_sources:
                node["source_sha256"] = expected
            elif node.get("source_sha256") != expected:
                cumulative["stage_inputs"] = {
                    key: value for key, value in stage_inputs.items() if ACTIVE_STAGES.index(key) < 2
                }
                return self._blocked(
                    task_id=task_id,
                    revision=revision,
                    stage=current_stage,
                    blockers=[_finding("CLAIM_SOURCE_HASH_FORGED", "claim node hash differs from actual base payload", f"nodes[{index}]")],
                    cumulative=cumulative,
                    next_stage="awaiting_claim_graph",
                    invalidations=INVALIDATE_ALL[3:],
                )
        graph["graph_snapshot_sha256"] = compute_claim_graph_snapshot(graph)
        if isinstance(graph.get("challenger"), dict):
            graph["challenger"]["graph_snapshot_sha256"] = graph[
                "graph_snapshot_sha256"
            ]
        response = research_service.compile_claim_graph(
            subject,
            graph,
            trusted_artifacts=trusted,
            trusted_attestations=trusted_attestations,
        )
        if response["status"] != "true":
            cumulative["stage_inputs"] = {
                key: value for key, value in stage_inputs.items() if ACTIVE_STAGES.index(key) < 2
            }
            return self._blocked(
                task_id=task_id,
                revision=revision,
                stage=current_stage,
                blockers=response["blockers"],
                cumulative=cumulative,
                next_stage="awaiting_claim_graph",
                invalidations=response["invalidated_artifacts"],
            )
        raw = response["artifacts"][0]
        descriptor = _normalize_descriptor(
            raw,
            subject=subject,
            stage="awaiting_claim_graph",
            product_build_id=self.product_build_id,
            producer_id=self.producer_id,
            source_service="research-argument-service",
        )
        descriptors.append(descriptor)
        trusted["claim_evidence"] = descriptor["payload_sha256"]
        frozen = copy.deepcopy(response["frozen_authority"])
        frozen["subject"]["input_hashes"]["claim_evidence"] = trusted["claim_evidence"]
        frozen["authorities"]["claim_evidence"]["sha256"] = trusted["claim_evidence"]
        frozen["projection_sha256"] = canonical_sha256(
            {key: value for key, value in frozen.items() if key != "projection_sha256"}
        )
        publication_subject = QualitySubject.from_mapping(frozen["subject"])
        # The package readiness contract is part of the immutable publication
        # subject.  Earlier canonical heads were created before this binding
        # was threaded through, which made a real package fail at J10 even
        # though the manuscript/review surfaces were current.  Bind the
        # existing host-owned manifest before J8/J9/J10 are replayed.
        readiness_hash = base_hashes.get("readiness_obligations")
        if _is_sha256(readiness_hash) and "readiness_obligations" not in publication_subject.input_hashes:
            publication_subject = QualitySubject(
                publication_subject.task_id,
                publication_subject.revision_id,
                {**publication_subject.input_hashes, "readiness_obligations": readiness_hash},
            )
        # Canonical J8 introduces the three concrete manuscript surfaces as
        # immutable base inputs.  Bind their byte hashes into the publication
        # subject before the pipeline rebinds the canonical payload; otherwise
        # a valid new TeX/PDF/DOCX set is silently rebound to a missing hash.
        manuscript_hashes = {
            str(artifact_id): str(payload.get("sha256"))
            for artifact_id, payload in base_artifacts.items()
            if str(artifact_id) in {"manuscript_source", "manuscript_pdf", "manuscript_word"}
            and isinstance(payload, Mapping)
            and _is_sha256(payload.get("sha256"))
        }
        if manuscript_hashes:
            publication_subject = QualitySubject(
                publication_subject.task_id,
                publication_subject.revision_id,
                {**publication_subject.input_hashes, **manuscript_hashes},
            )
        figure_quality_evidence = {
            str(artifact_id): copy.deepcopy(dict(payload))
            for artifact_id, payload in base_artifacts.items()
            if isinstance(payload, Mapping)
            and payload.get("contract")
            in {
                "paperspine5.figure-correction-receipt",
                "paperspine5.target-size-legibility-receipt",
            }
        }
        if figure_quality_evidence:
            quality_hashes = dict(publication_subject.input_hashes)
            for artifact_id, payload in figure_quality_evidence.items():
                quality_hashes[artifact_id] = str(payload["receipt_sha256"])
                if payload.get("contract") == "paperspine5.figure-correction-receipt":
                    output_id = (
                        f"figure-output.{_safe_evidence_token(str(payload['figure_id']))}"
                    )
                    quality_hashes[output_id] = str(payload["output"]["sha256"])
            publication_subject = QualitySubject(
                publication_subject.task_id,
                publication_subject.revision_id,
                quality_hashes,
            )
        if current_stage == "awaiting_claim_graph":
            return _result(
                task_id=task_id,
                revision=revision,
                build_id=self.product_build_id,
                stage=current_stage,
                status="PASS",
                blockers=[],
                warnings=warnings,
                descriptors=descriptors,
                next_stage=NEXT_STAGE[current_stage],
                invalidations=sorted(invalidations),
                cumulative_inputs=cumulative,
            )

        publication_service = PublicationPipelineService()
        outputs: dict[str, Any] = {}
        publication_stages = ACTIVE_STAGES[3 : current_index + 1]
        for stage in publication_stages:
            delegated_stage_receipts: list[dict[str, Any]] = []
            business = copy.deepcopy(dict(stage_inputs[stage]))
            request = {
                **business,
                "subject": publication_subject.as_dict(),
                "frozen_authority": frozen,
                "trusted_artifacts": {
                    artifact_id: trusted[artifact_id]
                    for artifact_id in ("direction_authority", "target_authority", "claim_evidence")
                },
            }
            if stage == "awaiting_figure_intent":
                request["figure_quality_evidence"] = figure_quality_evidence
                request["reference_plans"] = copy.deepcopy(reference_plans)
                request["trusted_figure_master_receipt"] = copy.deepcopy(
                    trusted_figure_master_receipt
                )
                request["registered_artifacts"] = dict(
                    publication_subject.input_hashes
                )
                intent = request.get("intent")
                if isinstance(intent, Mapping):
                    intent = copy.deepcopy(dict(intent))
                    active_sources = (
                        material_figure_set.get("figure_sources", [])
                        if isinstance(material_figure_set, Mapping)
                        else []
                    )
                    if (
                        isinstance(material_figure_set, Mapping)
                        and material_figure_set.get("status") == "PASS"
                    ):
                        intent["material_coverage"] = {
                            "primary_manuscript_source_id": material_figure_set.get(
                                "primary_manuscript_source_id"
                            ),
                            "profile_sha256": material_figure_set.get("profile_sha256"),
                            "figure_dispositions": [
                                {
                                    "source_id": item["source_id"],
                                    "artifact_id": item["artifact_id"],
                                    "relative_path": item["relative_path"],
                                    "sha256": item["sha256"],
                                    "disposition": "kept_or_reversibly_transformed",
                                }
                                for item in active_sources
                            ],
                            "status": material_figure_set.get("status"),
                            "external_action_authorized": False,
                        }
                    mode = str(intent.get("mode") or "")
                    expected_current_assets = {
                        str(item.get("artifact_id") or ""): str(
                            item.get("sha256") or ""
                        )
                        for item in active_sources
                        if isinstance(item, Mapping)
                    }
                    if expected_current_assets:
                        if mode == "zero":
                            return self._blocked(
                                task_id=task_id,
                                revision=revision,
                                stage=current_stage,
                                blockers=[
                                    _finding(
                                        "ZERO_FIGURE_CONTRADICTS_ACTIVE_MANUSCRIPT",
                                        "zero-figure mode cannot erase active main-manuscript figures",
                                    )
                                ],
                                cumulative=cumulative,
                                next_stage=stage,
                            )
                        if mode not in {"keep", "redesign", "mixed"}:
                            return self._blocked(
                                task_id=task_id,
                                revision=revision,
                                stage=current_stage,
                                blockers=[
                                    _finding(
                                        "ACTIVE_MANUSCRIPT_FIGURE_DECISION_MISSING",
                                        "active main-manuscript figures require keep or redesign coverage",
                                    )
                                ],
                                cumulative=cumulative,
                                next_stage=stage,
                            )
                        actual_current_assets = {
                            str(asset.get("artifact_id") or ""): str(
                                asset.get("sha256") or ""
                            )
                            for figure in intent.get("figures", [])
                            if isinstance(figure, Mapping)
                            for asset in [figure.get("current_asset")]
                            if isinstance(asset, Mapping)
                        }
                        if actual_current_assets != expected_current_assets:
                            return self._blocked(
                                task_id=task_id,
                                revision=revision,
                                stage=current_stage,
                                blockers=[
                                    _finding(
                                        "ACTIVE_MANUSCRIPT_FIGURE_COVERAGE_INCOMPLETE",
                                        "figure intent must cover every active ledger-bound manuscript figure exactly once",
                                    )
                                ],
                                cumulative=cumulative,
                                next_stage=stage,
                            )
                    if delegation is not None:
                        figure_modes = {
                            str(item.get("mode"))
                            for item in intent.get("figures", [])
                            if isinstance(item, Mapping)
                        }
                        decision_class = (
                            "figure_supplement"
                            if mode == "create" or "create" in figure_modes
                            else "figure_keep_or_transform"
                        )
                        class_blockers = _delegation_blocker(
                            delegation, decision_class, stage=stage
                        )
                        if class_blockers:
                            return self._blocked(
                                task_id=task_id,
                                revision=revision,
                                stage=current_stage,
                                blockers=class_blockers,
                                cumulative=cumulative,
                                next_stage=stage,
                            )
                        figures = [
                            item
                            for item in intent.get("figures", [])
                            if isinstance(item, Mapping)
                        ]
                        if mode == "zero":
                            delegated_stage_receipts.append(
                                _delegated_decision_descriptor(
                                    delegation=delegation,
                                    decision_class=decision_class,
                                    stage=stage,
                                    action_id="zero",
                                    subject=publication_subject,
                                    choice={
                                        "mode": "zero",
                                        "active_manuscript_figure_source_ids": [],
                                    },
                                    evidence_bindings={
                                        "materials.source-ledger": publication_subject.input_hashes[
                                            "materials.source-ledger"
                                        ],
                                        **(
                                            {
                                                "materials.figure-set": publication_subject.input_hashes[
                                                    "materials.figure-set"
                                                ]
                                            }
                                            if "materials.figure-set"
                                            in publication_subject.input_hashes
                                            else {}
                                        ),
                                        "direction_authority": trusted[
                                            "direction_authority"
                                        ],
                                        "claim_evidence": trusted["claim_evidence"],
                                    },
                                )
                            )
                        else:
                            for figure in figures:
                                figure_id = str(figure.get("figure_id") or "")
                                current_asset = figure.get("current_asset")
                                figure_mode = figure.get("mode") if mode == "mixed" else mode
                                if figure_mode == "redesign" and not isinstance(
                                    current_asset, Mapping
                                ):
                                    return self._blocked(
                                        task_id=task_id,
                                        revision=revision,
                                        stage=current_stage,
                                        blockers=[
                                            _finding(
                                                "DELEGATED_FIGURE_ORIGINAL_MISSING",
                                                "delegated transforms must preserve the original asset provenance",
                                            )
                                        ],
                                        cumulative=cumulative,
                                        next_stage=stage,
                                    )
                                bindings = {
                                    artifact_id: publication_subject.input_hashes[
                                        artifact_id
                                    ]
                                    for artifact_id in {
                                        str((current_asset or {}).get("artifact_id") or ""),
                                        *{
                                            str(item.get("artifact_id") or "")
                                            for item in figure.get(
                                                "candidate_assets", []
                                            )
                                            if isinstance(item, Mapping)
                                        },
                                    }
                                    if artifact_id
                                    and artifact_id
                                    in publication_subject.input_hashes
                                }
                                if "materials.figure-set" in publication_subject.input_hashes:
                                    bindings["materials.figure-set"] = publication_subject.input_hashes[
                                        "materials.figure-set"
                                    ]
                                delegated_stage_receipts.append(
                                    _delegated_decision_descriptor(
                                        delegation=delegation,
                                        decision_class=decision_class,
                                        stage=stage,
                                        action_id=figure_id,
                                        subject=publication_subject,
                                        choice={
                                            "mode": mode,
                                            "figure_id": figure_id,
                                            "current_asset": current_asset,
                                            "candidate_assets": figure.get(
                                                "candidate_assets", []
                                            ),
                                        },
                                        evidence_bindings=bindings,
                                    )
                                )
                    for figure in intent.get("figures", []):
                        if not isinstance(figure, dict):
                            continue
                        plan_binding = figure.get("reference_plan")
                        plan_artifact_id = str(
                            plan_binding.get("artifact_id")
                            if isinstance(plan_binding, Mapping)
                            else ""
                        )
                        plan = reference_plans.get(plan_artifact_id)
                        if not isinstance(plan_binding, dict) or not isinstance(
                            plan, Mapping
                        ):
                            return self._blocked(
                                task_id=task_id,
                                revision=revision,
                                stage=current_stage,
                                blockers=[
                                    _finding(
                                        "FIGURE_REFERENCE_PLAN_MISSING",
                                        "every non-zero J7 figure must bind one current Master-frozen reference plan",
                                        f"figures.{figure.get('figure_id')}.reference_plan",
                                    )
                                ],
                                cumulative=cumulative,
                                next_stage=stage,
                            )
                        plan_subject = plan.get("subject")
                        frozen_plan_revision = (
                            plan_subject.get("runner_revision")
                            if isinstance(plan_subject, Mapping)
                            else None
                        )
                        retained_plan = (
                            (retained_reference_plans or {}).get(plan_artifact_id)
                            == plan.get("plan_sha256")
                        )
                        try:
                            validated_plan = validate_figure_reference_plan(
                                plan,
                                expected_subject={
                                    "task_id": task_id,
                                    "revision_id": frozen_plan_revision,
                                    "material_snapshot_sha256": publication_subject.input_hashes.get(
                                        "materials.source-ledger"
                                    ),
                                },
                                expected_figure={
                                    **figure,
                                    "producer_id": intent.get("producer_id"),
                                },
                                registered_artifacts=publication_subject.input_hashes,
                                trusted_actor_receipt=trusted_figure_master_receipt,
                            )
                        except FigureReferenceMappingError as exc:
                            return self._blocked(
                                task_id=task_id,
                                revision=revision,
                                stage=current_stage,
                                blockers=[
                                    _finding(
                                        "FIGURE_REFERENCE_PLAN_INVALID",
                                        str(exc),
                                        f"figures.{figure.get('figure_id')}.reference_plan",
                                    )
                                ],
                                cumulative=cumulative,
                                next_stage=stage,
                            )
                        if (
                            plan_binding.get("sha256")
                            != validated_plan["plan_sha256"]
                            or (
                                str(plan_binding.get("revision_id"))
                                != str(validated_plan["subject"]["runner_revision"])
                                and not (
                                    retained_plan
                                    and str(plan_binding.get("revision_id"))
                                    == str(answer_subject_revision)
                                )
                                and not (
                                    # The immutable plan hash is the scientific
                                    # identity.  A same-task J7 replay may bind
                                    # it at a later Runner revision than the
                                    # plan's original publication revision.
                                    str(plan_binding.get("revision_id", "")).isdigit()
                                    and str(validated_plan["subject"].get("runner_revision", "")).isdigit()
                                    and int(plan_binding["revision_id"])
                                    >= int(validated_plan["subject"]["runner_revision"])
                                )
                            )
                        ):
                            return self._blocked(
                                task_id=task_id,
                                revision=revision,
                                stage=current_stage,
                                blockers=[
                                    _finding(
                                        "FIGURE_REFERENCE_PLAN_STALE",
                                        "J7 reference_plan does not bind the exact frozen plan revision and hash",
                                        f"figures.{figure.get('figure_id')}.reference_plan",
                                    )
                                ],
                                cumulative=cumulative,
                                next_stage=stage,
                            )
                        figure["reference_plan"]["revision_id"] = str(revision)
                        for field in ("current_asset",):
                            asset = figure.get(field)
                            if isinstance(asset, dict):
                                artifact_id = str(asset.get("artifact_id") or "")
                                if asset.get("sha256") != publication_subject.input_hashes.get(artifact_id):
                                    return self._blocked(
                                        task_id=task_id,
                                        revision=revision,
                                        stage=current_stage,
                                        blockers=[_finding("FIGURE_ASSET_HASH_FORGED", "figure asset hash differs from actual payload")],
                                        cumulative=cumulative,
                                        next_stage=stage,
                                    )
                                asset["revision_id"] = str(revision)
                        for asset in figure.get("candidate_assets", []):
                            if isinstance(asset, dict):
                                artifact_id = str(asset.get("artifact_id") or "")
                                if asset.get("sha256") != publication_subject.input_hashes.get(artifact_id):
                                    return self._blocked(
                                        task_id=task_id,
                                        revision=revision,
                                        stage=current_stage,
                                        blockers=[_finding("FIGURE_ASSET_HASH_FORGED", "figure candidate hash differs from actual payload")],
                                        cumulative=cumulative,
                                        next_stage=stage,
                                    )
                                asset["revision_id"] = str(revision)
                    request["intent"] = intent
                publication_response = publication_service.evaluate_figure_intent(request)
                outputs["figure_intent"] = publication_response.get("details", {}).get("figure_intent")
            elif stage == "awaiting_canonical":
                request["figure_intent"] = outputs["figure_intent"]
                # Only ProductRunner supplies this context from typed, freshly
                # revalidated ledger receipts; answer payloads never supply it.
                # Stateless legacy service/fixture replay is not a Runner task.
                if registered_final_mapping_context is not None:
                    mapping_bindings = registered_final_mapping_context.get("bindings", [])
                    by_figure = {v.get("figure_id"): v for v in mapping_bindings if isinstance(v, Mapping)}
                    figures = (outputs["figure_intent"] or {}).get("figures", [])
                    missing = [v.get("figure_id") for v in figures
                        if v.get("figure_id") not in by_figure
                        or by_figure[v["figure_id"]].get("accepted_candidate_manifest_sha256") != (v.get("selected_asset") or {}).get("sha256")
                        or by_figure[v["figure_id"]].get("frozen_plan", {}).get("sha256") != (v.get("reference_plan_binding") or {}).get("sha256")]
                    if (registered_final_mapping_context.get("policy") != "required-for-every-new-j8"
                            or registered_final_mapping_context.get("build_id") != self.product_build_id
                            or len(by_figure) != len(mapping_bindings) or missing):
                        return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                            blockers=[_finding("FINAL_FIGURE_MAPPING_REQUIRED", "Every selected figure requires a current typed final mapping: " + ", ".join(map(str, missing)))], cumulative=cumulative)
                    request["final_mapping_consumption"] = copy.deepcopy(dict(registered_final_mapping_context))
                    preserved = registered_final_mapping_context.get("accepted_consumption")
                    if preserved is not None:
                        preserved_bindings = preserved.get("bindings", []) if isinstance(preserved, Mapping) else []
                        if (current_stage == "awaiting_canonical"
                                or not isinstance(preserved, Mapping)
                                or set(preserved) != {"policy", "build_id", "bindings"}
                                or preserved.get("policy") != "required-for-every-new-j8"
                                or not isinstance(preserved.get("build_id"), str)
                                or len(preserved_bindings) != len(mapping_bindings)
                                or {v.get("figure_id"): v for v in preserved_bindings if isinstance(v, Mapping)} != by_figure):
                            return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                                blockers=[_finding("FINAL_FIGURE_MAPPING_REQUIRED", "successor revalidation changed frozen canonical consumption")], cumulative=cumulative)
                        # Current-build validation is the outer Runner context;
                        # migration alone does not rewrite the accepted scientific
                        # consumption digest already bound into the manuscript head.
                        request["final_mapping_consumption"] = copy.deepcopy(dict(preserved))
                if current_stage == "awaiting_canonical":
                    source_artifact = (request.get("manuscript_revision") or {}).get("artifacts", {}).get("source", {})
                    source_manifest = base_artifacts.get(str(source_artifact.get("artifact_id") or ""), {})
                    if (
                        not str(source_manifest.get("path") or "").lower().endswith(".tex")
                        or source_manifest.get("media_type") != "application/x-tex"
                    ):
                        return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                            blockers=[_finding("CANONICAL_LATEX_SOURCE_REQUIRED", "new J8 canonical source must be a bound .tex application/x-tex artifact")], cumulative=cumulative)
                    source_artifact["path"] = source_manifest["path"]
                    source_artifact["media_type"] = source_manifest["media_type"]
                    if isinstance(revision_context, Mapping) and revision_context.get("status") == "revision_required":
                        expected_ids = {str(item.get("objection_id")) for item in revision_context["initial_review"].get("objections", []) if isinstance(item, Mapping)}
                        response = request.get("revision_response")
                        response_ids = [str(item.get("objection_id")) for item in response if isinstance(item, Mapping)] if isinstance(response, list) else []
                        if len(response_ids) != len(expected_ids) or set(response_ids) != expected_ids or any(not isinstance(item, Mapping) or not _nonempty(item.get("evidence_locator")) or not _nonempty(item.get("change_summary")) for item in (response or [])):
                            return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                                blockers=[_finding("CANONICAL_REVISION_RESPONSE_REQUIRED", "J8 must locate a real revision response for every persisted objection")], cumulative=cumulative)
                        prior_scope = revision_context["initial_review"].get("review_scope")
                        prior_files = prior_scope.get("files", {}) if isinstance(prior_scope, Mapping) else {}
                        prior_files = prior_files if isinstance(prior_files, Mapping) else {}
                        unchanged = []
                        for role in ("source", "pdf", "word"):
                            artifact = (request.get("manuscript_revision") or {}).get("artifacts", {}).get(role, {})
                            artifact_id = str(artifact.get("artifact_id") or "")
                            manifest = base_artifacts.get(artifact_id, {})
                            prior_binary = (prior_files.get(role) or {}).get("binary_sha256")
                            prior_path = (prior_files.get(role) or {}).get("path")
                            if prior_path and str(manifest.get("path") or "").replace("\\", "/") == str(prior_path).replace("\\", "/"):
                                return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                                    blockers=[_finding("CANONICAL_REVISION_PATH_REUSED", f"{role} revision must preserve the reviewed file at its old path")], cumulative=cumulative)
                            if (prior_binary and manifest.get("sha256") == prior_binary) or (not prior_binary and base_hashes.get(artifact_id) == revision_context["manuscript_head"].get(f"{role}_sha256")):
                                unchanged.append(role)
                        if unchanged:
                            return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                                blockers=[_finding("CANONICAL_REVISION_UNCHANGED", f"J8 revision must rebuild source/PDF/Word: {unchanged}")], cumulative=cumulative)
                request["canonical_bundle"] = _rebind_current(
                    request.get("canonical_bundle"), publication_subject
                )
                request["manuscript_revision"] = _rebind_current(
                    request.get("manuscript_revision"), publication_subject
                )
                revision_payload = request.get("manuscript_revision")
                if isinstance(revision_payload, dict):
                    for artifact in revision_payload.get("artifacts", {}).values():
                        if isinstance(artifact, dict):
                            artifact_id = str(artifact.get("artifact_id") or "")
                            artifact["sha256"] = publication_subject.input_hashes.get(artifact_id)
                            artifact["revision_id"] = str(revision)
                    request["manuscript_revision"] = _rehash_contract(revision_payload)
                bundle = request.get("canonical_bundle")
                if isinstance(bundle, dict) and isinstance(revision_payload, Mapping):
                    for surface in bundle.get("surface_receipts", []):
                        if isinstance(surface, dict):
                            kind = str(surface.get("surface_kind") or "")
                            artifact = revision_payload.get("artifacts", {}).get(kind, {})
                            surface["source"] = {"sha256": artifact.get("sha256")}
                    request["canonical_bundle"] = _rehash_contract(bundle)
                publication_response = publication_service.bind_canonical(request)
                outputs["canonical_bundle"] = request.get("canonical_bundle")
                outputs["manuscript_head"] = publication_response.get("details", {}).get(
                    "active_manuscript_head"
                )
                if publication_response.get("status") == "PASS":
                    # Persist the normalized objects used to produce the head,
                    # not the producer's earlier revision/hash placeholders.
                    stage_inputs[stage]["canonical_bundle"] = copy.deepcopy(request["canonical_bundle"])
                    stage_inputs[stage]["manuscript_revision"] = copy.deepcopy(request["manuscript_revision"])
            elif stage == "awaiting_review":
                request["manuscript_head"] = outputs["manuscript_head"]
                request["canonical_bundle"] = outputs["canonical_bundle"]
                if isinstance(revision_context, Mapping) and revision_context.get("status") == "revision_required" and not isinstance(request.get("revision_diff"), Mapping):
                    return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                        blockers=[_finding("REVIEW_REVISION_CLOSURE_REQUIRED", "a persisted revision request requires initial_review, revision_diff and re_review")], cumulative=cumulative, next_stage=stage)
                raw_initial = request.get("initial_review")
                # The review's top-level self-hash is the immutable receipt
                # boundary.  Nested finding hashes may be rebound below when
                # the host refreshes the current authority/artifact bytes;
                # requiring the entire nested object to be byte-identical
                # before that rebind falsely rejects an otherwise valid J9
                # review (and strands the user at the review gate).
                raw_initial_valid = (
                    isinstance(raw_initial, Mapping)
                    and _is_sha256(raw_initial.get("review_sha256"))
                    and raw_initial.get("review_sha256")
                    in {
                        hashlib.sha256(
                            json.dumps(
                                {key: value for key, value in raw_initial.items() if key != "review_sha256"},
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode("utf-8")
                        ).hexdigest(),
                        hashlib.sha256(
                            (
                                json.dumps(
                                    {key: value for key, value in raw_initial.items() if key != "review_sha256"},
                                    ensure_ascii=False,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                )
                                + "\n"
                            ).encode("utf-8")
                        ).hexdigest(),
                    }
                )
                if not raw_initial_valid:
                    return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                        blockers=[_finding("INITIAL_REVIEW_HASH_INVALID", f"initial review hash must verify before host rebinding (type={type(raw_initial).__name__}, hash_ok={raw_initial_valid})")], cumulative=cumulative, next_stage=stage)
                surface_hashes = {
                    f"surface_{surface.get('surface_kind')}": str(
                        surface.get("receipt_sha256") or ""
                    )
                    for surface in (outputs["canonical_bundle"] or {}).get(
                        "surface_receipts", []
                    )
                    if isinstance(surface, Mapping)
                }

                def rebind_target_findings(review: Any) -> Any:
                    if not isinstance(review, dict):
                        return review
                    findings = review.get("target_obligation_findings")
                    if not isinstance(findings, list):
                        return review
                    rebound: list[Any] = []
                    for finding in findings:
                        if not isinstance(finding, dict):
                            rebound.append(finding)
                            continue
                        finding["target_authority_sha256"] = trusted[
                            "target_authority"
                        ]
                        artifact_id = str(finding.get("artifact_id") or "")
                        if artifact_id in surface_hashes:
                            finding["artifact_sha256"] = surface_hashes[artifact_id]
                        rebound.append(_rehash_contract(finding))
                    review["target_obligation_findings"] = rebound
                    return _rehash_contract(review)

                if not isinstance(request.get("revision_diff"), Mapping):
                    initial_review = _rebind_current(
                        request.get("initial_review"), publication_subject
                    )
                    if isinstance(initial_review, dict):
                        initial_review["manuscript_head_sha256"] = (
                            outputs["manuscript_head"] or {}
                        ).get("head_sha256")
                        if isinstance(initial_review.get("review_scope"), dict):
                            initial_review["review_scope"]["canonical_bundle_sha256"] = (outputs["canonical_bundle"] or {}).get("bundle_sha256")
                        initial_review = rebind_target_findings(initial_review)
                    request["initial_review"] = initial_review
                else:
                    initial_review = request.get("initial_review")
                    if isinstance(revision_context, Mapping) and initial_review != revision_context.get("initial_review"):
                        return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                            blockers=[_finding("INITIAL_REVIEW_CONTEXT_MISMATCH", "revision closure must preserve the exact persisted independent review")], cumulative=cumulative, next_stage=stage)
                    diff = copy.deepcopy(request["revision_diff"])
                    canonical_response = stage_inputs.get("awaiting_canonical", {}).get("revision_response")
                    if isinstance(revision_context, Mapping) and diff.get("changes") != canonical_response:
                        return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                            blockers=[_finding("REVISION_RESPONSE_DRIFT", "revision diff must retain the exact J8 revision response")], cumulative=cumulative, next_stage=stage)
                    current_head_sha256 = (outputs["manuscript_head"] or {}).get("head_sha256")
                    raw_re_review = request.get("re_review")
                    if _rehash_contract(diff) != diff or not isinstance(raw_re_review, Mapping) or _rehash_contract(raw_re_review) != raw_re_review:
                        return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                            blockers=[_finding("REVISION_REVIEW_HASH_INVALID", "revision diff and re-review hashes must verify before rebinding")], cumulative=cumulative, next_stage=stage)
                    if current_stage == "awaiting_review" and (
                        str(diff.get("to_revision_id")) not in {"0", str(revision)}
                        or diff.get("to_head_sha256") not in {"0" * 64, current_head_sha256}
                        or raw_re_review.get("manuscript_head_sha256") not in {"0" * 64, current_head_sha256}
                        or raw_re_review.get("revision_diff_sha256") not in {"0" * 64, diff.get("diff_sha256")}
                    ):
                        return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                            blockers=[_finding("REVISION_DIFF_STALE", "nonzero revision target differs from the current replayed head")], cumulative=cumulative, next_stage=stage)
                    diff["to_revision_id"] = str(revision)
                    diff["to_head_sha256"] = current_head_sha256
                    request["revision_diff"] = _rehash_contract(diff)
                    request["re_review"] = rebind_target_findings(
                        _rebind_current(
                            request.get("re_review"), publication_subject
                        )
                    )
                    if isinstance(request["re_review"], dict):
                        request["re_review"]["manuscript_head_sha256"] = current_head_sha256
                        request["re_review"]["revision_diff_sha256"] = request["revision_diff"]["diff_sha256"]
                        if isinstance(request["re_review"].get("review_scope"), dict):
                            request["re_review"]["review_scope"]["canonical_bundle_sha256"] = (outputs["canonical_bundle"] or {}).get("bundle_sha256")
                        request["re_review"] = _rehash_contract(request["re_review"])
                    if isinstance(revision_context, Mapping):
                        request["producer_ids"] = sorted(set(request.get("producer_ids", [])) | set(revision_context.get("producer_ids", [])))
                current_review = (
                    request.get("re_review")
                    if isinstance(request.get("revision_diff"), Mapping)
                    else request.get("initial_review")
                )
                expected_target_findings = {
                    (
                        str(item.get("obligation_id") or ""),
                        str(item.get("authority_rule_id") or ""),
                    )
                    for item in host_target_obligations.get("obligations", [])
                    if isinstance(item, Mapping)
                    and item.get("readiness_scope") == "local_delivery"
                }
                actual_target_findings = {
                    (
                        str(item.get("obligation_id") or ""),
                        str(item.get("authority_rule_id") or ""),
                    )
                    for item in (
                        current_review.get("target_obligation_findings", [])
                        if isinstance(current_review, Mapping)
                        else []
                    )
                    if isinstance(item, Mapping)
                }
                if actual_target_findings != expected_target_findings:
                    return self._blocked(
                        task_id=task_id,
                        revision=revision,
                        stage=current_stage,
                        blockers=[
                            _finding(
                                "TARGET_OBLIGATION_FINDING_COVERAGE_MISMATCH",
                                "J9 findings must cover exactly the host-derived local target rules",
                            )
                        ],
                        cumulative=cumulative,
                        next_stage=stage,
                    )
                publication_response = publication_service.review_revision(request)
                outputs["review_closure"] = publication_response.get("details", {}).get(
                    "review_closure"
                )
                if publication_response.get("status") == "PASS":
                    stage_inputs[stage] = {key: copy.deepcopy(request[key]) for key in ("producer_ids", "initial_review", "revision_diff", "re_review") if key in request}
                    if isinstance(cumulative.get("revision_context"), dict):
                        cumulative["revision_context"]["status"] = "closed"
            else:
                request["manuscript_head"] = outputs["manuscript_head"]
                request["review_closure"] = outputs["review_closure"]
                # Rebind target findings to the current canonical source artifact.
                # Older J9 reviews may have used a semantic source id (for example
                # manuscript_source_r26); package validation must compare the
                # finding against the current r57 source bound by the head.
                closure = request.get("review_closure")
                head_for_closure = outputs.get("manuscript_head") or {}
                input_hashes = ((head_for_closure.get("subject") or {}).get("input_hashes")
                                if isinstance(head_for_closure, Mapping) else {})
                current_source_id = next(
                    (str(k) for k, v in (input_hashes or {}).items()
                     if str(k).startswith("manuscript_source_")
                     and v == head_for_closure.get("source_sha256")),
                    None,
                )
                if isinstance(closure, dict) and current_source_id:
                    findings = closure.get("target_obligation_findings")
                    if isinstance(findings, list):
                        rebound_findings = []
                        for finding in findings:
                            item = copy.deepcopy(finding) if isinstance(finding, dict) else finding
                            if isinstance(item, dict) and str(item.get("artifact_id") or "").startswith("manuscript_source_"):
                                item["artifact_id"] = current_source_id
                                item["artifact_sha256"] = head_for_closure.get("source_sha256")
                                item = _rehash_contract(item)
                            rebound_findings.append(item)
                        closure["target_obligation_findings"] = rebound_findings
                        request["review_closure"] = _rehash_contract(closure)
                request["surface_receipts"] = _rebind_current(
                    (outputs.get("canonical_bundle") or {}).get(
                        "surface_receipts", []
                    ),
                    publication_subject,
                )
                obligations = _rebind_current(
                    host_target_obligations, publication_subject
                )
                if isinstance(obligations, dict):
                    obligations["target_authority_sha256"] = trusted["target_authority"]
                    for obligation in obligations.get("obligations", []):
                        if not isinstance(obligation, dict):
                            continue
                        binding = obligation.get("authority_binding")
                        if isinstance(binding, dict):
                            binding["artifact_id"] = "target_authority"
                            binding["sha256"] = trusted["target_authority"]
                    obligations = _rehash_contract(obligations)
                request["target_obligations"] = obligations
                author = copy.deepcopy(request.get("author_close"))
                if isinstance(author, list):
                    for item in author:
                        if isinstance(item, dict):
                            item["confirmed_revision_id"] = str(revision)
                request["author_close"] = author
                package = _rebind_current(request.get("package_manifest"), publication_subject)
                current = dict(base_hashes)
                head = outputs["manuscript_head"] or {}
                closure = outputs["review_closure"] or {}
                current["canonical_head"] = str(head.get("head_sha256") or "")
                # Target-package mappings bind the actual manuscript files
                # reviewed in J9.  The base-artifact registry stores receipt
                # hashes for these semantic IDs, which are intentionally
                # different from the binary/source hashes in manuscript_head.
                # Rebind the three delivery-facing IDs to the exact bytes
                # that the independent review and archive descriptor cover.
                for artifact_id, field in (
                    ("manuscript_source", "source_sha256"),
                    ("manuscript_pdf", "pdf_sha256"),
                    ("manuscript_word", "word_sha256"),
                ):
                    value = head.get(field)
                    if isinstance(value, str) and value:
                        current[artifact_id] = value
                bundle = outputs["canonical_bundle"] or {}
                bundle_input = base_artifacts.get("bundle_archive")
                if (
                    isinstance(bundle_input, Mapping)
                    and bundle_input.get("contract") == "paperspine5.local-package-archive"
                    and isinstance(bundle_input.get("sha256"), str)
                ):
                    # The base receipt is a JSON descriptor; package freshness
                    # must bind the actual ZIP bytes named by that descriptor.
                    current["bundle_archive"] = str(bundle_input["sha256"])
                current["final_claim_index"] = str(
                    bundle.get("final_claim_index", {}).get("receipt_sha256") or ""
                )
                current["review_closure"] = str(closure.get("closure_sha256") or "")
                current["target_authority"] = trusted["target_authority"]
                current["claim_evidence"] = trusted["claim_evidence"]
                if isinstance(obligations, Mapping):
                    current["target_obligations"] = str(obligations.get("ledger_sha256") or "")
                for surface in request.get("surface_receipts", []):
                    if isinstance(surface, Mapping):
                        current[f"surface_{surface.get('surface_kind')}"] = str(
                            surface.get("receipt_sha256") or ""
                        )
                if isinstance(author, list) and author:
                    current["author_close"] = canonical_sha256(author)
                if isinstance(package, dict):
                    archive_id = str(package.get("archive_artifact_id") or "")
                    if package.get("archive_sha256") != base_hashes.get(archive_id):
                        return self._blocked(
                            task_id=task_id,
                            revision=revision,
                            stage=current_stage,
                            blockers=[_finding("PACKAGE_ARCHIVE_HASH_FORGED", "archive hash differs from actual base artifact")],
                            cumulative=cumulative,
                            next_stage=stage,
                        )
                    package["target_authority_sha256"] = trusted["target_authority"]
                    for entry in package.get("entries", []):
                        if isinstance(entry, dict):
                            artifact_id = str(entry.get("artifact_id") or "")
                            entry["sha256"] = current.get(artifact_id)
                            entry["revision_id"] = str(revision)
                    package = _rehash_contract(package)
                    current["target_package"] = str(package.get("manifest_sha256") or "")
                request["package_manifest"] = package
                mappings = copy.deepcopy(request.get("package_mapping"))
                if isinstance(mappings, list):
                    for item in mappings:
                        if isinstance(item, dict):
                            item["artifact_sha256"] = current.get(str(item.get("artifact_id") or ""))
                request["package_mapping"] = mappings
                predicates = copy.deepcopy(request.get("predicates"))
                if isinstance(predicates, list):
                    for predicate in predicates:
                        if not isinstance(predicate, dict):
                            continue
                        predicate["subject"] = publication_subject.as_dict()
                        inputs = predicate.get("artifact_inputs")
                        if isinstance(inputs, Mapping):
                            predicate["artifact_inputs"] = {
                                str(key): current.get(str(key)) for key in inputs
                            }
                request["predicates"] = predicates
                request["current_artifacts"] = current
                if delegation is not None:
                    requested_scope = request.get("requested_scope")
                    if requested_scope != delegation["requested_scope"]:
                        return self._blocked(
                            task_id=task_id,
                            revision=revision,
                            stage=current_stage,
                            blockers=[
                                _finding(
                                    "LOCAL_DELEGATION_SCOPE_DRIFT",
                                    "package scope differs from the initial local delegation grant",
                                )
                            ],
                            cumulative=cumulative,
                            next_stage=stage,
                        )
                    class_blockers = _delegation_blocker(
                        delegation,
                        "non_author_local_target_adaptation",
                        stage=stage,
                    )
                    if class_blockers:
                        return self._blocked(
                            task_id=task_id,
                            revision=revision,
                            stage=current_stage,
                            blockers=class_blockers,
                            cumulative=cumulative,
                            next_stage=stage,
                        )
                    delegated_stage_receipts.append(
                        _delegated_decision_descriptor(
                            delegation=delegation,
                            decision_class="non_author_local_target_adaptation",
                            stage=stage,
                            action_id="package-mapping",
                            subject=publication_subject,
                            choice={
                                "requested_scope": requested_scope,
                                "package_mapping": mappings,
                            },
                            evidence_bindings={
                                "target_authority": trusted["target_authority"],
                                "publication.review-closure": str(
                                    closure.get("closure_sha256") or ""
                                ),
                                "target_obligations": str(
                                    (obligations or {}).get("ledger_sha256") or ""
                                ),
                            },
                        )
                    )
                publication_response = publication_service.compile_package(request)

            invalidations.update(publication_response.get("invalidated_artifacts", []))
            if publication_response.get("status") != "PASS":
                review_blockers = publication_response.get("blockers", [])
                if stage == "awaiting_review" and review_blockers and {item.get("code") for item in review_blockers} == {"QUALITY_REVISION_REQUIRED"}:
                    prior_review = publication_response.get("details", {}).get("revision_required_review")
                    cumulative["revision_context"] = {
                        "contract": "paperspine5.publication-revision-context",
                        "schema_version": CONTRACT_VERSION,
                        "initial_review": copy.deepcopy(prior_review),
                        "manuscript_head": copy.deepcopy(outputs["manuscript_head"]),
                        "producer_ids": copy.deepcopy(request.get("producer_ids", [])),
                        "status": "revision_required",
                        "external_action_authorized": False,
                    }
                    cumulative["stage_inputs"] = {key: value for key, value in stage_inputs.items() if ACTIVE_STAGES.index(key) < ACTIVE_STAGES.index("awaiting_canonical")}
                    for raw in publication_response.get("artifact_descriptors", []):
                        descriptors.append(_normalize_descriptor(raw, subject=publication_subject, stage=stage, product_build_id=self.product_build_id, producer_id=self.producer_id, source_service="publication-pipeline-service"))
                    return self._blocked(task_id=task_id, revision=revision, stage=current_stage,
                        blockers=review_blockers, cumulative=cumulative, next_stage="awaiting_canonical",
                        invalidations=sorted(invalidations), warnings=warnings, descriptors=descriptors)
                stage_index = ACTIVE_STAGES.index(stage)
                cumulative["stage_inputs"] = {
                    key: value
                    for key, value in stage_inputs.items()
                    if ACTIVE_STAGES.index(key) < stage_index
                }
                return self._blocked(
                    task_id=task_id,
                    revision=revision,
                    stage=current_stage,
                    blockers=publication_response.get("blockers", []),
                    cumulative=cumulative,
                    next_stage=stage,
                    invalidations=sorted(invalidations),
                    warnings=warnings,
                )
            for raw in publication_response.get("artifact_descriptors", []):
                descriptor = _normalize_descriptor(
                    raw,
                    subject=publication_subject,
                    stage=stage,
                    product_build_id=self.product_build_id,
                    producer_id=self.producer_id,
                    source_service="publication-pipeline-service",
                )
                descriptors.append(descriptor)
                trusted[descriptor["artifact_id"]] = descriptor["payload_sha256"]
            for raw in delegated_stage_receipts:
                descriptors.append(
                    _normalize_descriptor(
                        raw,
                        subject=publication_subject,
                        stage=stage,
                        product_build_id=self.product_build_id,
                        producer_id=self.producer_id,
                        source_service="academic-stage-orchestrator",
                    )
                )

        return _result(
            task_id=task_id,
            revision=revision,
            build_id=self.product_build_id,
            stage=current_stage,
            status="PASS",
            blockers=[],
            warnings=warnings,
            descriptors=descriptors,
            next_stage=NEXT_STAGE[current_stage],
            invalidations=sorted(invalidations),
            cumulative_inputs=cumulative,
        )
