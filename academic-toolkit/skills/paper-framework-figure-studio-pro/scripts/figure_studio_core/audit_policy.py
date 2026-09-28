"""Generic issue-ledger helpers for v3.2.15f.

S3 may review S2 exploration images before selecting a direction. S5 has no
assistant-side audit; after S5 image generation, remaining choices are made by
humans.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable

VALID_SEVERITIES = {"minor", "moderate", "major", "blocker"}
VALID_REVISION_FEASIBILITY = {"easy", "moderate", "hard", "not_actionable", "unknown"}


@dataclass
class CandidateIssue:
    issue_id: str
    severity: str
    category: str
    description: str
    evidence_basis: str = "candidate image + source/figure contract"
    revision_feasibility: str = "unknown"
    should_inform_later_prompting: bool = False
    downstream_use: str = "inform_human_selection_or_next_prompt_constraints"
    blocker_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        if row["severity"] not in VALID_SEVERITIES:
            row["severity"] = "moderate"
        if row["revision_feasibility"] not in VALID_REVISION_FEASIBILITY:
            row["revision_feasibility"] = "unknown"
        if row["severity"] == "blocker" and not row.get("blocker_code"):
            row["blocker_code"] = "BLOCKER_ISSUE"
        return row


def make_issue(
    issue_id: str,
    severity: str,
    category: str,
    description: str,
    *,
    evidence_basis: str = "candidate image + source/figure contract",
    revision_feasibility: str = "unknown",
    should_inform_later_prompting: bool = False,
    downstream_use: str = "inform_human_selection_or_next_prompt_constraints",
    blocker_code: str | None = None,
) -> dict[str, Any]:
    return CandidateIssue(
        issue_id=issue_id,
        severity=severity,
        category=category,
        description=description,
        evidence_basis=evidence_basis,
        revision_feasibility=revision_feasibility,
        should_inform_later_prompting=should_inform_later_prompting,
        downstream_use=downstream_use,
        blocker_code=blocker_code,
    ).to_dict()


def build_issue_ledger(
    *,
    candidate_id: str,
    candidate_image_path: str,
    issues: Iterable[dict[str, Any]] | None = None,
    caption_alignment_issues: list[str] | None = None,
    caption_burden: str = "unknown",
    safe_caption_only_items: list[str] | None = None,
    must_be_visible_not_caption_only: list[str] | None = None,
    legend_or_caption_needed_for: list[str] | None = None,
    caption_risk_notes: list[str] | None = None,
    human_selection_implication: str | None = None,
) -> dict[str, Any]:
    issue_rows = list(issues or [])
    return {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "candidate_image_path": candidate_image_path,
        "audit_mode": "issue_inventory",
        "selection_verdict_policy": "No default winner is chosen by the assistant. S3 uses S3 review of S2 outputs to select a direction; S5 output is terminal for assistant work.",
        "issues": issue_rows,
        "has_blocker_issue": any((row.get("severity") == "blocker") or row.get("blocker_code") == "BLOCKER_ISSUE" for row in issue_rows),
        "caption_alignment_issues": caption_alignment_issues or [],
        "caption_burden": caption_burden,
        "safe_caption_only_items": safe_caption_only_items or [],
        "must_be_visible_not_caption_only": must_be_visible_not_caption_only or [],
        "legend_or_caption_needed_for": legend_or_caption_needed_for or [],
        "caption_risk_notes": caption_risk_notes or [],
        "human_selection_implication": human_selection_implication or "S3 uses S3 review of S2 outputs for direction choice. After S5, humans decide selection, edits, or manuscript use.",
    }


def audit_candidate(candidate_image_path: str, paper_contract: dict[str, Any] | None = None, *, candidate_id: str = "candidate") -> dict[str, Any]:
    # This helper does not perform visual analysis. It returns an empty ledger
    # template that callers fill from human/vision observations.
    return build_issue_ledger(candidate_id=candidate_id, candidate_image_path=candidate_image_path)
