"""Panel-aware, preservation-first selection for publication figures."""

from __future__ import annotations

import re
from typing import Any


SCHEMA_VERSION = "1.0"
PANEL_ACTIONS = {"keep", "repair", "redraw", "promote", "demote", "omit"}
CANDIDATE_FAMILIES = {
    "preserved_original",
    "minimally_repaired_hybrid",
    "exemplar_mechanism_redesign",
    "alternative_evidence_architecture",
    "full_redraw",
}
SCORE_DIMENSIONS = (
    "scientific_fidelity",
    "information_retention",
    "conclusion_speed",
    "readability",
    "hierarchy_scan_path",
    "publication_fit",
    "aesthetic_coherence",
)
PANEL_SCORE_DIMENSIONS = (
    "scientific_fidelity",
    "information_retention",
    "conclusion_speed",
    "readability",
    "publication_fit",
    "aesthetic_coherence",
)
CRITICAL_DIMENSIONS = SCORE_DIMENSIONS[:-1]
WEIGHTS = {
    "scientific_fidelity": 0.22,
    "information_retention": 0.18,
    "conclusion_speed": 0.15,
    "readability": 0.17,
    "hierarchy_scan_path": 0.12,
    "publication_fit": 0.10,
    "aesthetic_coherence": 0.06,
}
MINIMUM_CRITICAL_SCORE = 70.0
PANEL_MINIMUMS = {
    "scientific_fidelity": 75.0,
    "information_retention": 65.0,
    "conclusion_speed": 55.0,
    "readability": 55.0,
    "publication_fit": 55.0,
}
PANEL_WEIGHTS = {
    "scientific_fidelity": 0.25,
    "information_retention": 0.20,
    "conclusion_speed": 0.16,
    "readability": 0.18,
    "publication_fit": 0.13,
    "aesthetic_coherence": 0.08,
}
STRICT_TOTAL_DELTA = 2.0
_SHA256 = re.compile(r"^[0-9A-Fa-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_INTERVENTION_RANK = {
    "preserved_original": 0,
    "minimally_repaired_hybrid": 1,
    "exemplar_mechanism_redesign": 2,
    "alternative_evidence_architecture": 2,
    "full_redraw": 3,
}


class PanelSelectionError(ValueError):
    """Raised when a panel-selection receipt is incomplete or inconsistent."""


def _identifier(value: Any, label: str) -> str:
    text = str(value or "")
    if not _IDENTIFIER.fullmatch(text):
        raise PanelSelectionError(f"{label} must be a safe non-empty identifier")
    return text


def _score_map(raw: Any, label: str) -> dict[str, float]:
    if not isinstance(raw, dict) or set(raw) != set(SCORE_DIMENSIONS):
        raise PanelSelectionError(
            f"{label}.scores must contain exactly: {', '.join(SCORE_DIMENSIONS)}"
        )
    scores: dict[str, float] = {}
    for dimension in SCORE_DIMENSIONS:
        value = raw[dimension]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PanelSelectionError(f"{label}.scores.{dimension} must be numeric")
        number = float(value)
        if not 0.0 <= number <= 100.0:
            raise PanelSelectionError(f"{label}.scores.{dimension} must be between 0 and 100")
        scores[dimension] = number
    return scores


def _panel_score_map(raw: Any, label: str) -> dict[str, float]:
    if not isinstance(raw, dict) or set(raw) != set(PANEL_SCORE_DIMENSIONS):
        raise PanelSelectionError(
            f"{label}.scores must contain exactly: {', '.join(PANEL_SCORE_DIMENSIONS)}"
        )
    scores: dict[str, float] = {}
    for dimension in PANEL_SCORE_DIMENSIONS:
        value = raw[dimension]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PanelSelectionError(f"{label}.scores.{dimension} must be numeric")
        number = float(value)
        if not 0.0 <= number <= 100.0:
            raise PanelSelectionError(f"{label}.scores.{dimension} must be between 0 and 100")
        scores[dimension] = number
    return scores


def _panel_reviews(raw: Any, panel_ids: set[str], label: str) -> dict[str, dict[str, Any]]:
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise PanelSelectionError(f"{label}.panel_reviews must be an array")
    reviews: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw):
        item_label = f"{label}.panel_reviews[{index}]"
        if not isinstance(item, dict):
            raise PanelSelectionError(f"{item_label} must be an object")
        panel_id = _identifier(item.get("panel_id"), f"{item_label}.panel_id")
        if panel_id not in panel_ids:
            raise PanelSelectionError(f"{item_label}.panel_id is not a baseline panel")
        if panel_id in reviews:
            raise PanelSelectionError(f"{label}.panel_reviews repeats panel {panel_id}")
        digest = str(item.get("final_size_render_sha256") or "")
        if not _SHA256.fullmatch(digest):
            raise PanelSelectionError(f"{item_label}.final_size_render_sha256 must be SHA-256")
        blockers = item.get("blockers")
        if not isinstance(blockers, list) or any(not isinstance(value, str) for value in blockers):
            raise PanelSelectionError(f"{item_label}.blockers must be an array of strings")
        reviews[panel_id] = {
            "panel_id": panel_id,
            "final_size_render_sha256": digest.upper(),
            "scores": _panel_score_map(item.get("scores"), item_label),
            "blockers": list(blockers),
        }
        reviews[panel_id]["weighted_score"] = _weighted_panel_score(
            reviews[panel_id]["scores"]
        )
    return reviews


def _panel_actions(raw: Any, panel_ids: set[str], label: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise PanelSelectionError(f"{label}.panel_actions must be an array")
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise PanelSelectionError(f"{label}.panel_actions[{index}] must be an object")
        panel_id = _identifier(item.get("panel_id"), f"{label}.panel_actions[{index}].panel_id")
        if panel_id in seen:
            raise PanelSelectionError(f"{label}.panel_actions repeats panel {panel_id}")
        seen.add(panel_id)
        action = str(item.get("panel_action") or "")
        if action not in PANEL_ACTIONS:
            raise PanelSelectionError(
                f"{label}.panel_actions[{index}].panel_action must be one of {sorted(PANEL_ACTIONS)}"
            )
        rationale = str(item.get("rationale") or "").strip()
        if len(rationale) < 8:
            raise PanelSelectionError(f"{label}.panel_actions[{index}].rationale is too short")
        claim_ids = item.get("claim_ids")
        if not isinstance(claim_ids, list) or not claim_ids or any(
            not isinstance(value, str) or not value.strip() for value in claim_ids
        ):
            raise PanelSelectionError(
                f"{label}.panel_actions[{index}].claim_ids must contain at least one claim"
            )
        actions.append(
            {
                "panel_id": panel_id,
                "panel_action": action,
                "claim_ids": list(claim_ids),
                "rationale": rationale,
            }
        )
    if seen != panel_ids:
        missing = sorted(panel_ids - seen)
        unknown = sorted(seen - panel_ids)
        raise PanelSelectionError(
            f"{label}.panel_actions must cover every baseline panel exactly once; "
            f"missing={missing}, unknown={unknown}"
        )
    return actions


def _weighted_score(scores: dict[str, float]) -> float:
    return round(sum(scores[name] * WEIGHTS[name] for name in SCORE_DIMENSIONS), 4)


def _weighted_panel_score(scores: dict[str, float]) -> float:
    return round(sum(scores[name] * PANEL_WEIGHTS[name] for name in PANEL_SCORE_DIMENSIONS), 4)


def select_panel_aware_candidate(receipt: dict[str, Any]) -> dict[str, Any]:
    """Choose the least-invasive strict winner from final-size review evidence.

    The current figure is represented by exactly one ``preserved_original``
    candidate. A replacement must clear every critical threshold, avoid any
    critical regression against that baseline, improve a non-aesthetic
    dimension, and exceed the weighted baseline by two points. Ties favor less
    intervention. A blocked scientific identity is never selectable.
    """

    if not isinstance(receipt, dict):
        raise PanelSelectionError("receipt must be an object")
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise PanelSelectionError(f"schema_version must be {SCHEMA_VERSION}")
    if receipt.get("preservation_prior") is not True:
        raise PanelSelectionError("preservation_prior must be true")
    figure_id = _identifier(receipt.get("figure_id"), "figure_id")
    context = receipt.get("final_size_context")
    if not isinstance(context, dict):
        raise PanelSelectionError("final_size_context is required")
    for key in ("column_span", "physical_width_mm", "render_dpi"):
        if key not in context:
            raise PanelSelectionError(f"final_size_context.{key} is required")

    raw_panels = receipt.get("panels")
    if not isinstance(raw_panels, list) or not raw_panels:
        raise PanelSelectionError("panels must contain at least one baseline panel")
    panel_ids: set[str] = set()
    for index, panel in enumerate(raw_panels):
        if not isinstance(panel, dict):
            raise PanelSelectionError(f"panels[{index}] must be an object")
        panel_id = _identifier(panel.get("panel_id"), f"panels[{index}].panel_id")
        if panel_id in panel_ids:
            raise PanelSelectionError(f"panels repeats {panel_id}")
        panel_ids.add(panel_id)
        if not str(panel.get("claim_role") or "").strip():
            raise PanelSelectionError(f"panels[{index}].claim_role is required")
        if not str(panel.get("evidence_anchor") or "").strip():
            raise PanelSelectionError(f"panels[{index}].evidence_anchor is required")

    raw_candidates = receipt.get("candidates")
    if not isinstance(raw_candidates, list) or len(raw_candidates) < 2:
        raise PanelSelectionError("candidates must include the original and at least one alternative")
    candidates: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    for index, raw in enumerate(raw_candidates):
        if not isinstance(raw, dict):
            raise PanelSelectionError(f"candidates[{index}] must be an object")
        candidate_id = _identifier(raw.get("candidate_id"), f"candidates[{index}].candidate_id")
        if candidate_id in candidate_ids:
            raise PanelSelectionError(f"candidates repeats {candidate_id}")
        candidate_ids.add(candidate_id)
        family = str(raw.get("candidate_family") or "")
        if family not in CANDIDATE_FAMILIES:
            raise PanelSelectionError(
                f"candidates[{index}].candidate_family must be one of {sorted(CANDIDATE_FAMILIES)}"
            )
        digest = str(raw.get("final_size_render_sha256") or "")
        if not _SHA256.fullmatch(digest):
            raise PanelSelectionError(
                f"candidates[{index}].final_size_render_sha256 must be SHA-256"
            )
        identity_status = str(raw.get("identity_status") or "")
        if identity_status not in {"verified", "blocked"}:
            raise PanelSelectionError(
                f"candidates[{index}].identity_status must be verified or blocked"
            )
        blockers = raw.get("blockers")
        if not isinstance(blockers, list) or any(not isinstance(value, str) for value in blockers):
            raise PanelSelectionError(f"candidates[{index}].blockers must be an array of strings")
        scores = _score_map(raw.get("scores"), f"candidates[{index}]")
        actions = _panel_actions(raw.get("panel_actions"), panel_ids, f"candidates[{index}]")
        panel_reviews = _panel_reviews(
            raw.get("panel_reviews"), panel_ids, f"candidates[{index}]"
        )
        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_family": family,
                "final_size_render_sha256": digest.upper(),
                "identity_status": identity_status,
                "blockers": list(blockers),
                "scores": scores,
                "panel_actions": actions,
                "panel_reviews": panel_reviews,
                "weighted_score": _weighted_score(scores),
            }
        )

    baselines = [item for item in candidates if item["candidate_family"] == "preserved_original"]
    if len(baselines) != 1:
        raise PanelSelectionError("exactly one preserved_original candidate is required")
    baseline = baselines[0]
    baseline_scores = baseline["scores"]
    panel_review_mode = any(item["panel_reviews"] for item in candidates)
    baseline_panel_blockers = {
        panel_id: list(review["blockers"])
        for panel_id, review in baseline["panel_reviews"].items()
        if review["blockers"]
    }
    evaluations: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for candidate in candidates:
        reasons: list[str] = []
        panel_review_results: list[dict[str, Any]] = []
        if candidate["identity_status"] != "verified":
            reasons.append("scientific_identity_blocked")
        reasons.extend(candidate["blockers"])
        if panel_review_mode:
            for action in candidate["panel_actions"]:
                panel_id = action["panel_id"]
                panel_action = action["panel_action"]
                review = candidate["panel_reviews"].get(panel_id)
                panel_reasons: list[str] = []
                if panel_action == "keep":
                    panel_reasons.extend(baseline_panel_blockers.get(panel_id, []))
                elif review is None:
                    panel_reasons.append("modified_panel_missing_final_size_review")
                else:
                    panel_reasons.extend(review["blockers"])
                    below = [
                        name
                        for name, minimum in PANEL_MINIMUMS.items()
                        if review["scores"][name] < minimum
                    ]
                    if below:
                        panel_reasons.append("panel_dimension_below_minimum:" + ",".join(below))
                    baseline_review = baseline["panel_reviews"].get(panel_id)
                    if baseline_review is not None and not baseline_review["blockers"]:
                        regressed = [
                            name
                            for name in PANEL_MINIMUMS
                            if review["scores"][name] < baseline_review["scores"][name]
                        ]
                        improved = [
                            name
                            for name in PANEL_MINIMUMS
                            if review["scores"][name] > baseline_review["scores"][name]
                        ]
                        if regressed:
                            panel_reasons.append(
                                "panel_critical_regression_vs_original:" + ",".join(regressed)
                            )
                        if not improved:
                            panel_reasons.append(
                                "panel_aesthetic_only_or_no_material_improvement"
                            )
                        if (
                            review["weighted_score"]
                            < baseline_review["weighted_score"] + STRICT_TOTAL_DELTA
                        ):
                            panel_reasons.append("panel_weighted_delta_below_2")
                if panel_reasons:
                    reasons.extend(f"panel_{panel_id}:{reason}" for reason in panel_reasons)
                panel_review_results.append(
                    {
                        "panel_id": panel_id,
                        "panel_action": panel_action,
                        "reviewed": review is not None,
                        "eligible": not panel_reasons,
                        "rejection_reasons": panel_reasons,
                    }
                )
        baseline_valid = not (
            baseline["identity_status"] != "verified"
            or baseline["blockers"]
            or baseline_panel_blockers
        )
        if candidate is not baseline and not panel_review_mode:
            below = [
                name
                for name in CRITICAL_DIMENSIONS
                if candidate["scores"][name] < MINIMUM_CRITICAL_SCORE
            ]
            if below:
                reasons.append("critical_dimension_below_70:" + ",".join(below))
        if candidate is not baseline and baseline_valid:
            regressed = [
                name
                for name in CRITICAL_DIMENSIONS
                if candidate["scores"][name] < baseline_scores[name]
            ]
            improved = [
                name
                for name in CRITICAL_DIMENSIONS
                if candidate["scores"][name] > baseline_scores[name]
            ]
            if regressed:
                reasons.append("critical_regression_vs_original:" + ",".join(regressed))
            if not improved:
                reasons.append("aesthetic_only_or_no_material_improvement")
            if candidate["weighted_score"] < baseline["weighted_score"] + STRICT_TOTAL_DELTA:
                reasons.append("weighted_delta_below_2")
        is_eligible = not reasons
        reviewed_scores = [
            review["weighted_score"] for review in candidate["panel_reviews"].values()
        ]
        selection_score = (
            round(sum(reviewed_scores) / len(reviewed_scores), 4)
            if panel_review_mode and reviewed_scores
            else candidate["weighted_score"]
        )
        candidate["selection_score"] = selection_score
        if is_eligible:
            eligible.append(candidate)
        evaluations.append(
            {
                "candidate_id": candidate["candidate_id"],
                "candidate_family": candidate["candidate_family"],
                "weighted_score": candidate["weighted_score"],
                "selection_score": selection_score,
                "eligible": is_eligible,
                "rejection_reasons": reasons,
                "panel_review_results": panel_review_results,
            }
        )

    if baseline not in eligible:
        verified_alternatives = [item for item in eligible if item is not baseline]
        if not verified_alternatives:
            raise PanelSelectionError("no scientifically eligible candidate is available")
        eligible = verified_alternatives

    winner = max(
        eligible,
        key=lambda item: (
            item["selection_score"],
            -_INTERVENTION_RANK[item["candidate_family"]],
            item["candidate_id"],
        ),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "figure_id": figure_id,
        "selection": winner["candidate_id"],
        "winner_family": winner["candidate_family"],
        "fallback_to_original": winner is baseline,
        "preservation_prior_applied": True,
        "aesthetic_only_selection_forbidden": True,
        "panel_review_mode": panel_review_mode,
        "final_size_context": context,
        "winner_weighted_score": winner["weighted_score"],
        "winner_selection_score": winner["selection_score"],
        "baseline_weighted_score": baseline["weighted_score"],
        "evaluations": evaluations,
        "panel_actions": winner["panel_actions"],
    }


__all__ = [
    "CANDIDATE_FAMILIES",
    "CRITICAL_DIMENSIONS",
    "PANEL_ACTIONS",
    "PANEL_SCORE_DIMENSIONS",
    "PanelSelectionError",
    "SCORE_DIMENSIONS",
    "select_panel_aware_candidate",
]
