"""Compose existing J10 inputs from accepted artifacts; never perform a review.

This is a preparation adapter, not a second readiness compiler. The normal
publication compiler still checks/rebinds every input and decides readiness.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .quality_readiness import (
    REQUIRED_PREDICATES,
    build_obligation_manifest,
    canonical_sha256,
)
from .research_argument_service import compute_claim_graph_snapshot


def _hashed(value: Any, field: str) -> bool:
    return isinstance(value, dict) and value.get(field) == canonical_sha256(
        {key: item for key, item in value.items() if key != field}
    )


def _accepted_surface_review(surface: dict) -> bool:
    review = surface.get("review")
    if not isinstance(review, dict) or not review.get(
        "reviewer_id", review.get("agent_id")
    ):
        return False
    if review.get("schema") != "paperspine5.independent-reader-surface-review/1.0":
        return review.get("final_decision", review.get("decision")) == "pass"
    # Native PDF reuse and fresh Word reports use different optional summaries.
    # Complete exact-page checks are authoritative; do not invent a missing
    # summary, override an explicit negative, or claim reuse was fresh viewing.
    if any(
        field in review and review[field] is not True
        for field in (
            "all_pages_have_verified_visual_review",
            "all_pages_individually_viewed",
        )
    ) or any(
        field in review and review[field] != "pass"
        for field in ("final_decision", "decision")
    ):
        return False
    items = review.get("items")
    pages = surface.get("pages")
    count = surface.get("page_count")
    if not (
        review.get("status") == "PASS"
        and review.get("issues") == []
        and review.get("external_action_authorized") is False
        and type(count) is int
        and count > 0
        and type(review.get("page_count")) is int
        and review["page_count"] == count
        and isinstance(pages, list)
        and isinstance(items, list)
        and len(items) == len(pages) == count
        and all(
            isinstance(item, dict) and type(item.get("page")) is int
            for item in [*pages, *items]
        )
    ):
        return False
    expected_pages = set(range(1, count + 1))
    if any(
        {item["page"] for item in values} != expected_pages for values in (pages, items)
    ):
        return False
    page_hashes = {page["page"]: page.get("sha256") for page in pages}
    return all(
        isinstance(item.get("sha256"), str)
        and len(item["sha256"]) == 64
        and all(char in "0123456789abcdef" for char in item["sha256"])
        and item["sha256"] == page_hashes[item["page"]]
        and isinstance(item.get("checks"), dict)
        and all(
            item["checks"].get(key) is True
            for key in (
                "background",
                "clipping",
                "figure_placement",
                "overlap",
                "readability",
            )
        )
        for item in items
    )


def prepare_local_package_inputs(
    *,
    head: dict,
    bundle: dict,
    review: dict,
    graph: dict | None,
    obligations: dict,
    target_sha256: str,
) -> dict:
    """Preserve accepted E6/J8/J9 scope, with unknowns rather than inferred PASS.

    Callers must obtain these objects from the current Runner pointer ledger,
    not producer input. Byte verification and ZIP creation belong to the host.
    """
    subject = head.get("subject")
    if (
        not _hashed(head, "head_sha256")
        or head.get("status") != "PASS"
        or not _hashed(bundle, "bundle_sha256")
        or bundle.get("status") != "PASS"
        or bundle.get("subject") != subject
        or head.get("canonical_bundle_sha256") != bundle.get("bundle_sha256")
        or not _hashed(review, "closure_sha256")
        or review.get("status") != "PASS"
        or review.get("subject") != subject
        or review.get("manuscript_head_sha256") != head.get("head_sha256")
        or any(
            item.get("external_action_authorized") is not False
            for item in (head, bundle, review)
        )
    ):
        raise ValueError(
            "J10 preparation requires the exact accepted head, canonical bundle and J9 closure"
        )
    claims = bundle.get("final_claim_index", {})
    claim_ok = (
        _hashed(claims, "receipt_sha256")
        and claims.get("status") == "PASS"
        and review.get("final_claim_index_sha256") == claims.get("receipt_sha256")
    )
    # E6 licenses only its frozen claim graph. It is not a bibliography audit,
    # clinical validation, or proof that all conceivable claims were extracted.
    evidence_ok = False
    if (
        isinstance(graph, dict)
        and graph.get("contract") == "paperspine5.claim-evidence-argument-graph"
    ):
        nodes = graph.get("nodes", [])
        claim_ids = {
            item.get("claim_id")
            for item in claims.get("claims", [])
            if item.get("disposition") != "omitted"
        }
        graph_claim_ids = {
            item.get("node_id")
            for item in nodes
            if item.get("node_type") == "claim" and item.get("status") == "verified"
        }
        evidence_ok = (
            bool(claim_ids)
            and claim_ids.issubset(graph_claim_ids)
            and compute_claim_graph_snapshot(graph)
            == graph.get("graph_snapshot_sha256")
            and graph.get("challenger", {}).get("status") == "pass"
            and graph.get("challenger", {}).get("objections") == []
            and graph.get("external_action_authorized") is False
            and all(
                item.get("status") in {"verified", "none_found"}
                and subject["input_hashes"].get(item.get("source_artifact_id"))
                == item.get("source_sha256")
                for item in nodes
            )
        )
    surfaces = bundle.get("surface_receipts", [])
    surface_ok = (
        len(surfaces) == 2
        and {item.get("surface_kind") for item in surfaces} == {"pdf", "word"}
        and all(
            _hashed(item, "receipt_sha256")
            and item.get("status") == "PASS"
            and item.get("task_id") == subject["task_id"]
            and str(item.get("revision_id")) == subject["revision_id"]
            and item.get("page_count") == len(item.get("pages", []))
            and bool(item.get("pages"))
            and item.get("source", {}).get("sha256")
            == head.get(item["surface_kind"] + "_sha256")
            for item in surfaces
        )
    )
    visual_ok = surface_ok and all(_accepted_surface_review(item) for item in surfaces)
    current = {
        **subject["input_hashes"],
        **{
            f"surface_{item['surface_kind']}": item["receipt_sha256"]
            for item in surfaces
        },
    }
    findings = {
        item.get("obligation_id"): item
        for item in review.get("target_obligation_findings", [])
    }
    mapping = []
    for obligation in obligations.get("obligations", []):
        finding = findings.get(obligation.get("obligation_id"))
        if finding is None:
            continue  # Missing / author-only facts remain unclosed.
        exact = (
            _hashed(finding, "finding_sha256")
            and finding.get("authority_rule_id") == obligation.get("authority_rule_id")
            and finding.get("target_authority_sha256") == target_sha256
            and current.get(finding.get("artifact_id"))
            == finding.get("artifact_sha256")
        )
        if not exact:
            raise ValueError(
                "J10 accepted target finding does not bind the current authority/artifact"
            )
        mapping.append(
            {
                "obligation_id": obligation["obligation_id"],
                "artifact_id": finding["artifact_id"],
                "artifact_sha256": finding["artifact_sha256"],
                "status": finding.get("status") == "satisfied",
                "evidence_locator": finding.get("evidence_locator"),
            }
        )
    local_ids = {
        item["obligation_id"]
        for item in obligations.get("obligations", [])
        if item.get("readiness_scope") == "local_delivery"
    }
    covered = {item["obligation_id"] for item in mapping if item["status"] is True}
    states = {
        "canonical_artifacts_bound": (
            True,
            "Exact accepted canonical head; host independently checks its file bytes.",
        ),
        "final_claim_inventory_valid": (
            claim_ok,
            "Only the exact retained/omitted claim inventory accepted at J8 and bound by J9.",
        ),
        "evidence_verification_valid": (
            evidence_ok,
            "Only accepted E6 frozen claim/evidence scope; not a new citation audit or external scientific verification.",
        ),
        "independent_review_valid": (
            True,
            "Existing accepted J9 closure only; its original independent review scope is not expanded.",
        ),
        "quality_objections_closed": (
            review.get("objection_ids") == []
            or review.get("closed_by_revision") is True,
            "Only objections closed by the accepted J9 review/re-review.",
        ),
        "final_render_bound": (
            surface_ok,
            "Exact accepted PDF/Word page receipts; not inferred from file existence.",
        ),
        "surface_semantics_valid": (
            visual_ok,
            "Only semantics covered by accepted independent J8 surface review.",
        ),
        "visual_accessibility_valid": (
            visual_ok,
            "Only legibility covered by accepted independent J8 surface review; no new viewing claimed.",
        ),
        "target_research_valid": (
            True,
            "Existing frozen target authority, not new or exhaustive current journal research.",
        ),
        "target_compliance_valid": (
            bool(local_ids) and local_ids.issubset(covered),
            "Only exact local-delivery target findings from the accepted independent review; author-only rules remain open.",
        ),
        "target_bundle_fresh": (
            False,
            "Pending real ZIP byte/CRC verification by the host.",
        ),
        "author_items_closed": (
            False,
            "Unknown: no author facts supplied or inferred.",
        ),
        "author_confirmed_current_revision": (
            False,
            "Unknown: no current real-author confirmation supplied.",
        ),
    }
    predicates = [
        {
            "contract": "paperspine5.readiness-predicate",
            "contract_version": "1.0",
            "predicate_id": name,
            "tier": tier.value,
            "subject": deepcopy(subject),
            "status": "true" if states[name][0] else "unknown",
            "hard_blocker": True,
            "artifact_inputs": {"canonical_head": head["head_sha256"]},
            "reason": states[name][1],
        }
        for tier, names in REQUIRED_PREDICATES.items()
        for name in sorted(names)
    ]
    return {
        "requested_scope": "local_delivery",
        "surface_receipts": deepcopy(surfaces),
        "target_obligations": deepcopy(obligations),
        "package_mapping": mapping,
        "author_close": [],
        "predicates": predicates,
        "readiness_obligation_manifest": build_obligation_manifest(),
        "cycle": {
            "kind": "initial",
            "changed_artifact_ids": [],
            "refreshed_artifact_ids": [],
        },
        "package_manifest": {
            "contract": "paperspine5.target-package-manifest",
            "contract_version": "1.0",
            "status": "BLOCKED",
            "external_action_authorized": False,
        },
    }
