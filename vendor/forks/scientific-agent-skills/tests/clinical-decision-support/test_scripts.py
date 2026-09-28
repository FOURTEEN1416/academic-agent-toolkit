"""Synthetic tests for the research-only clinical-decision-support helpers."""

from __future__ import annotations

import ast
import copy
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2] / "skills" / "clinical-decision-support"
SCRIPTS = ROOT / "scripts"
ASSETS = ROOT / "assets"
sys.path.insert(0, str(SCRIPTS))

import _common  # noqa: E402
import cohort_table_generator  # noqa: E402
import decision_logic_traceability  # noqa: E402
import deidentification_checklist  # noqa: E402
import evidence_profile_check  # noqa: E402
import model_biomarker_evaluation  # noqa: E402
import survival_plan_validator  # noqa: E402
import validate_cds_artifact  # noqa: E402

import skill_contract


def load_asset(filename: str) -> dict:
    return json.loads((ASSETS / filename).read_text(encoding="utf-8"))


def resolve_placeholders(value):
    if isinstance(value, dict):
        return {key: resolve_placeholders(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [resolve_placeholders(nested) for nested in value]
    if isinstance(value, str):
        if "YYYY-MM-DD" in value:
            return "2026-07-23"
        if "REPLACE_" in value or "REQUIRES_" in value:
            return "Synthetic completed human entry."
    return value


class StaticSafetyTests(unittest.TestCase):
    def test_scripts_have_no_network_secret_or_dynamic_code_imports(self) -> None:
        banned_import_roots = {
            "aiohttp",
            "httpx",
            "openai",
            "pickle",
            "requests",
            "socket",
            "urllib",
        }
        banned_calls = {"eval", "exec"}
        for path in sorted(SCRIPTS.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".")[0] for alias in node.names}
                    self.assertFalse(
                        roots & banned_import_roots,
                        f"{path.name} imports a prohibited module",
                    )
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(
                        node.module.split(".")[0],
                        banned_import_roots,
                        f"{path.name} imports a prohibited module",
                    )
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(
                        node.func.id,
                        banned_calls,
                        f"{path.name} uses dynamic code execution",
                    )
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("os.environ", source)
            self.assertNotIn("getenv(", source)
            self.assertNotIn("API_KEY", source)

    def test_assets_declare_safety_fields(self) -> None:
        for path in sorted(ASSETS.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("intended_use", document, path.name)
            self.assertIn("limitations", document, path.name)
            self.assertIn("human_review", document, path.name)
            self.assertIn("prohibited_uses", document, path.name)

    def test_url_like_input_path_is_rejected(self) -> None:
        with self.assertRaises(_common.InputError):
            _common.local_input_path("https://example.invalid/data.json")

    def test_skill_is_progressively_disclosed_and_versioned(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLess(len(text.splitlines()), 500)
        self.assertRegex(text, r'\n  version: "\d+\.\d+"\n')
        self.assertIn("license: MIT", text)
        self.assertIn("metadata:\n  version:", text)


class ArtifactValidatorTests(unittest.TestCase):
    def test_unresolved_artifact_template_fails_closed(self) -> None:
        document = load_asset("artifact_intended_use_template.json")
        result = validate_cds_artifact.validate_artifact(document)
        self.assertFalse(result.ok)
        self.assertTrue(
            any("placeholders" in error for error in result.errors), result.errors
        )

    def test_completed_safe_artifact_passes_structural_checks(self) -> None:
        document = copy.deepcopy(load_asset("artifact_intended_use_template.json"))
        document["artifact"].update(
            {
                "id": "SYNTHETIC-ARTIFACT-001",
                "owner": "research governance owner",
                "date": "2026-07-23",
            }
        )
        document["data_governance"]["data_cut_date"] = "2026-07-23"
        document["validation"].update(
            {
                "external_validation": "Planned before transportability claims.",
                "calibration": "Aggregate calibration review planned.",
                "subgroup_fairness": "Prespecified subgroup review planned.",
                "uncertainty": "Intervals and limitations will be reported.",
                "human_factors": "Not evaluated; live use is outside scope.",
            }
        )
        document["sources"][0].update(
            {
                "citation": "Synthetic governance source, version 1.",
                "url": "not_applicable_for_local_synthetic_source",
                "accessed": "2026-07-23",
            }
        )
        result = validate_cds_artifact.validate_artifact(document)
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(result.warnings)


class EvidenceProfileTests(unittest.TestCase):
    def test_unresolved_template_requires_human_judgments(self) -> None:
        document = load_asset("evidence_profile_template.json")
        result, _ = evidence_profile_check.check_profile(document)
        self.assertFalse(result.ok)
        self.assertTrue(
            any("human judgment" in error for error in result.errors),
            result.errors,
        )

    def test_complete_human_profile_passes_without_auto_grading(self) -> None:
        document = resolve_placeholders(
            copy.deepcopy(load_asset("evidence_profile_template.json"))
        )
        outcome = document["outcomes"][0]
        for domain in outcome["domains"].values():
            domain["judgment"] = "not_serious"
            domain["rationale"] = "Human reviewers found no serious concern and cited the source."
            domain["reviewer_role"] = "systematic-review methodologist"
        for item in outcome["upgrading"].values():
            item["judgment"] = "not_applicable"
            item["rationale"] = "Human reviewers judged the consideration not applicable."
        outcome["certainty"].update(
            {
                "human_judgment": True,
                "level": "moderate",
                "rationale": "Human panel rationale after explicit domain review.",
                "reviewer_role": "GRADE panel chair",
                "judgment_date": "2026-07-23",
            }
        )
        document["profile_review"]["completed"] = True
        result, summaries = evidence_profile_check.check_profile(document)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(summaries[0]["human_entered_certainty"], "moderate")
        self.assertFalse(document["auto_grade"])


class AggregateEvaluationTests(unittest.TestCase):
    def test_model_evaluation_is_aggregate_and_bounded(self) -> None:
        document = load_asset("aggregate_model_evaluation_template.json")
        log, report = model_biomarker_evaluation.evaluate(document, minimum=11)
        self.assertTrue(log.ok, log.errors)
        self.assertFalse(report["individual_output_generated"])
        self.assertFalse(report["clinical_classification_generated"])
        self.assertFalse(report["recommendation_generated"])
        self.assertEqual(len(report["groups"]), 2)
        self.assertFalse(report["groups"][0]["suppressed"])
        self.assertIn("sensitivity", report["groups"][0]["metrics"])

    def test_cohort_table_applies_complementary_suppression(self) -> None:
        document = load_asset("aggregate_cohort_table_template.json")
        log, _, rows, notes = cohort_table_generator._build_table(document, 11)
        self.assertTrue(log.ok, log.errors)
        self.assertEqual(rows[-1][1], "SUPP")
        self.assertEqual(rows[-1][2], "SUPP-C")
        self.assertTrue(any("Complementary suppression" in note for note in notes))


class PlanAndTraceabilityTests(unittest.TestCase):
    def test_survival_plan_passes_with_recorded_review_warning(self) -> None:
        document = load_asset("survival_analysis_plan_template.json")
        result = survival_plan_validator.validate_plan(document)
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(any("Human review" in warning for warning in result.warnings))

    def test_traceability_matrix_is_non_executable(self) -> None:
        document = load_asset("decision_logic_traceability_template.json")
        result, rows = decision_logic_traceability.validate_matrix(document)
        self.assertTrue(result.ok, result.errors)
        self.assertFalse(document["metadata"]["executable_logic"])
        self.assertEqual(len(rows), 3)
        allowed = decision_logic_traceability.ALLOWED_OUTPUT_KINDS
        self.assertTrue(all(row["output_kind"] in allowed for row in rows))


class PrivacyChecklistTests(unittest.TestCase):
    def test_unresolved_template_fails_closed(self) -> None:
        document = load_asset("deidentification_checklist_template.json")
        result, summary = deidentification_checklist.check_documentation(document)
        self.assertFalse(result.ok)
        self.assertFalse(summary["documentation_complete"])
        self.assertFalse(summary["hipaa_compliance_determined"])

    def test_complete_safe_harbor_documentation_is_not_compliance_claim(self) -> None:
        document = resolve_placeholders(
            copy.deepcopy(load_asset("deidentification_checklist_template.json"))
        )
        document["method"] = "safe_harbor"
        for entry in document["identifier_categories"]:
            entry["status"] = "not_present"
            entry["evidence"] = (
                "Qualified reviewer documented the category as absent in the inventory."
            )
        document["safe_harbor_review"]["completed"] = True
        document["residual_risk_review"]["completed"] = True
        document["human_review"]["completed"] = True
        result, summary = deidentification_checklist.check_documentation(document)
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(summary["documentation_complete"])
        self.assertFalse(summary["deidentification_determined"])
        self.assertFalse(summary["hipaa_compliance_determined"])


# The shared --help contract: every argparse CLI this skill ships answers --help
# without doing any work. It skips when the skill's packages are absent and runs
# for real under `python tests/run_all.py --isolated`.
CliHelpTests = skill_contract.cli.help_test_case(ROOT)

if __name__ == "__main__":
    unittest.main()
