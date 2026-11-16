from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "src" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from evidence_grounded_review import (  # noqa: E402
    aggregate_calibrations,
    build_review_plan,
    calibrate_reviews,
    validate_contract,
    write_review_plan,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract(manuscript: Path) -> dict:
    digest = _sha(manuscript)
    receipts = []
    reviewers = []
    for role in ("methods", "contribution", "clarity"):
        receipt_id = f"receipt-{role}"
        receipts.append({
            "receipt_id": receipt_id,
            "action": "manuscript_read",
            "status": "completed",
            "target_locator": "page 1, lines 1-20",
            "usage": {"input_tokens": 100, "output_tokens": 50, "wall_seconds": 2.5},
        })
        reviewers.append({
            "reviewer_id": f"reviewer-{role}",
            "persona_id": role,
            "role": role,
            "independent_pass": True,
            "receipt_id": receipt_id,
        })
    return {
        "schema_version": "1.0",
        "review_id": "review-001",
        "policy": "strict",
        "literature_scope": "closed_corpus",
        "manuscript": {"path": str(manuscript), "sha256": digest},
        "reviewers": reviewers,
        "tool_receipts": receipts,
        "findings": [{
            "finding_id": "MET-001",
            "reviewer_id": "reviewer-methods",
            "criterion": "methods",
            "severity": "MAJOR",
            "summary": "The sampling rule is not fully specified.",
            "recommendation": "Define the sampling rule and stopping condition.",
            "confidence": 0.9,
            "disposition": "resolved",
            "paper_evidence": [{
                "kind": "quote",
                "locator": "page 1, lines 4-7",
                "quote": "We sample observations until convergence.",
                "source_sha256": digest,
            }],
            "external_evidence": [],
            "tool_receipt_ids": ["receipt-methods"],
        }],
        "synthesis": {"status": "PASS", "blocker_finding_ids": []},
    }


class EvidenceGroundedReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manuscript = self.root / "main.tex"
        self.manuscript.write_text(
            "\\section{Methods}\nWe sample observations until convergence.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_valid_strict_contract_is_hash_bound_and_costed(self) -> None:
        result = validate_contract(_contract(self.manuscript), manuscript_path=self.manuscript)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.grounded_finding_count, 1)
        self.assertEqual(result.input_tokens, 300)
        self.assertEqual(result.output_tokens, 150)
        self.assertEqual(result.wall_seconds, 7.5)

    def test_unlocated_comment_cannot_pass(self) -> None:
        contract = _contract(self.manuscript)
        contract["findings"][0]["paper_evidence"][0]["locator"] = "Methods section"
        result = validate_contract(contract)
        self.assertFalse(result.ok)
        self.assertTrue(any("locator must include" in item for item in result.errors))

    def test_provider_failure_cannot_support_major_novelty_blocker(self) -> None:
        contract = _contract(self.manuscript)
        contract["literature_scope"] = "open_literature"
        finding = contract["findings"][0]
        finding["criterion"] = "novelty"
        finding["external_evidence"] = [{
            "provider": "Semantic Scholar",
            "query": "closest method",
            "status": "provider_failure",
            "error": "timeout",
        }]
        result = validate_contract(contract)
        self.assertFalse(result.ok)
        self.assertTrue(any("cannot hard-block" in item for item in result.errors))

    def test_no_hit_requires_zero_results_and_is_not_provider_failure(self) -> None:
        contract = _contract(self.manuscript)
        contract["tool_receipts"].append({
            "receipt_id": "search-1",
            "action": "paper_search",
            "status": "no_hit",
            "provider": "arXiv",
            "query": "rare baseline",
            "result_count": 2,
            "usage": {"input_tokens": 0, "output_tokens": 0, "wall_seconds": 1},
        })
        result = validate_contract(contract)
        self.assertFalse(result.ok)
        self.assertTrue(any("result_count=0" in item for item in result.errors))

    def test_unavailable_telemetry_is_disclosed_not_counted_as_measured(self) -> None:
        contract = _contract(self.manuscript)
        contract["tool_receipts"][0]["usage"]["telemetry_status"] = "unavailable"
        result = validate_contract(contract)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.telemetry_unavailable_count, 1)
        self.assertTrue(any("not measured cost" in item for item in result.warnings))

    def test_strict_plan_selects_open_literature_lanes_and_cost_ceiling(self) -> None:
        config = {
            "review_policy": "strict",
            "literature_scope": "open_literature",
            "special_requirements": [
                "verify first-of-its-kind claim, historical trajectory, and closest baseline"
            ],
            "review_budget": {"max_search_queries": 7},
        }
        plan = build_review_plan(config)
        roles = {item["role"] for item in plan["selected_personas"]}
        self.assertTrue({"editor", "methods", "contribution", "clarity"}.issubset(roles))
        self.assertTrue({"literature", "historian", "baseline_scout", "fact_checker"}.issubset(roles))
        self.assertNotIn("judge", roles)
        self.assertEqual(plan["budget_ceiling"]["max_search_queries"], 7)

    def test_plan_written_with_real_manuscript_hash(self) -> None:
        output = self.root / "output"
        target = write_review_plan(output, self.manuscript, {"review_policy": "balanced"})
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["manuscript"]["sha256"], _sha(self.manuscript))
        self.assertTrue(payload["budget_ceiling"]["max_input_tokens"] > 0)

    def test_human_calibration_reports_hits_misses_false_alarms_without_mutation(self) -> None:
        ai = _contract(self.manuscript)
        ai["findings"].append({
            **ai["findings"][0],
            "finding_id": "CLR-EXTRA",
            "reviewer_id": "reviewer-clarity",
            "criterion": "clarity",
            "summary": "A minor transition is abrupt.",
        })
        human = {
            "review_id": "human-001",
            "findings": [
                {
                    "finding_id": "H-1",
                    "criterion": "methods",
                    "severity": "MAJOR",
                    "summary": "The sampling rule is not fully specified.",
                    "recommendation": "Define the sampling rule and stopping condition.",
                    "matching_ai_ids": ["MET-001"],
                    "expected_persona": "methods",
                },
                {
                    "finding_id": "H-2",
                    "criterion": "baseline",
                    "severity": "CRITICAL",
                    "summary": "A required baseline is missing.",
                    "recommendation": "Add the baseline.",
                    "expected_persona": "baseline_scout",
                },
            ],
        }
        delta = calibrate_reviews(ai, human)
        self.assertEqual(delta["metrics"]["n_hits"], 1)
        self.assertEqual(delta["metrics"]["n_misses"], 1)
        self.assertEqual(delta["metrics"]["n_false_alarms"], 1)
        self.assertFalse(delta["automatic_registry_mutation"])
        self.assertEqual(delta["miss_attributions"][0]["failure_mode"], "selection_failure")

    def test_aggregation_requires_cross_paper_support(self) -> None:
        suggestion = {
            "type": "selection_policy_adjustment",
            "target_persona": "baseline_scout",
            "criterion": "baseline",
        }
        payload = aggregate_calibrations([
            {"paper_id": "p1", "suggestions": [suggestion]},
            {"paper_id": "p2", "suggestions": [suggestion]},
            {"paper_id": "p2", "suggestions": [suggestion]},
        ], min_support=2)
        self.assertEqual(len(payload["recommendations"]), 1)
        self.assertEqual(payload["recommendations"][0]["support"], 2)
        self.assertFalse(payload["automatic_registry_mutation"])


if __name__ == "__main__":
    unittest.main()
