"""Behavior tests for dependency-free scientific-writing scripts."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "skills" / "scientific-writing"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_claims
import check_consistency
import check_references
import lint_manuscript
import scaffold_manuscript
import select_reporting_guidelines
import validate_authorship
import validate_manifest
from _common import InputError, read_json
from synthetic_manuscript import (
    valid_authorship_manifest,
    valid_claim_csv,
    valid_consistency_manifest,
    valid_manuscript_manifest,
    valid_source_manifest,
)

import skill_contract


class ScriptTests(unittest.TestCase):
    def write_json(self, directory: Path, name: str, value: object) -> Path:
        path = directory / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_valid_manuscript_and_source_manifests(self) -> None:
        self.assertEqual(
            validate_manifest.validate_manuscript_manifest(valid_manuscript_manifest()),
            [],
        )
        self.assertEqual(
            validate_manifest.validate_source_manifest(
                valid_source_manifest(),
                require_verified=True,
            ),
            [],
        )

    def test_json_reader_rejects_nonfinite_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            path.write_text('{"value": NaN}', encoding="utf-8")
            with self.assertRaises(InputError):
                read_json(path)

    def test_source_template_fails_closed(self) -> None:
        template = json.loads(
            (ROOT / "assets" / "source_manifest_template.json").read_text(
                encoding="utf-8"
            )
        )
        issues = validate_manifest.validate_source_manifest(
            template,
            require_verified=True,
        )
        self.assertTrue(any(item.severity == "error" for item in issues))

    def test_reporting_selector_and_non_scoring_coverage(self) -> None:
        registry = select_reporting_guidelines.load_registry()
        args = argparse.Namespace(
            study_design="randomized_trial",
            protocol=False,
            ai=False,
            llm=False,
            routinely_collected=False,
            qualitative_component=False,
        )
        primary, extensions, issues = select_reporting_guidelines.select_guidelines(
            registry, args
        )
        self.assertIn("consort-2025", primary)
        self.assertEqual(extensions, [])
        self.assertEqual(issues, [])

        guideline = registry["consort-2025"]
        coverage = {
            "schema_version": "1.0",
            "guideline_id": "consort-2025",
            "items": [
                {
                    "topic_id": topic["id"],
                    "status": "addressed",
                    "locations": ["Methods"],
                    "rationale": "",
                }
                for topic in guideline["coverage_topics"]
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_json(Path(temporary), "coverage.json", coverage)
            coverage_issues, summary = select_reporting_guidelines.check_coverage(
                registry,
                str(path),
            )
        self.assertEqual(coverage_issues, [])
        self.assertIn("non-scoring", summary["disclaimer"])

    def test_claim_audit_accepts_verified_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            sources_path = self.write_json(
                directory,
                "sources.json",
                valid_source_manifest(),
            )
            claims_path = directory / "claims.csv"
            claims_path.write_text(valid_claim_csv(), encoding="utf-8")
            manuscript = "Verified test statement [claim:C001] [evidence:E001]\n"
            sources = audit_claims.load_sources(str(sources_path))
            claims, claim_issues = audit_claims.load_claims(str(claims_path), sources)
            markdown_issues, used = audit_claims.audit_markdown(
                manuscript,
                claims,
                sources,
            )
        self.assertEqual(claim_issues, [])
        self.assertEqual(markdown_issues, [])
        self.assertEqual(used, {"C001"})

    def test_claim_audit_flags_untagged_number(self) -> None:
        issues, _ = audit_claims.audit_markdown(
            "An unsupported value is 7.\n",
            {},
            {},
        )
        self.assertTrue(any(item.code == "UNTAGGED_NUMERIC_CONTENT" for item in issues))

    def test_consistency_checks_methods_results_and_numbers(self) -> None:
        data = valid_consistency_manifest()
        fact_issues, fact_count = check_consistency.validate_numeric_facts(data)
        method_issues, method_count, result_count = (
            check_consistency.validate_methods_results(data)
        )
        self.assertEqual(fact_issues, [])
        self.assertEqual(method_issues, [])
        self.assertEqual((fact_count, method_count, result_count), (2, 1, 1))

        data["numeric_facts"][1]["value"] = 3
        mismatch, _ = check_consistency.validate_numeric_facts(data)
        self.assertTrue(
            any(item.code == "CROSS_SECTION_VALUE_MISMATCH" for item in mismatch)
        )
        data["numeric_facts"][1]["value"] = 2
        data["numeric_facts"][1]["sample_size"] = 3
        mismatch, _ = check_consistency.validate_numeric_facts(data)
        self.assertTrue(
            any(item.code == "CROSS_SECTION_SAMPLE_SIZE_MISMATCH" for item in mismatch)
        )

    def test_reference_checker_is_offline_and_detects_duplicate(self) -> None:
        data = valid_source_manifest()
        issues, count = check_references.check_sources(data)
        self.assertEqual(issues, [])
        self.assertEqual(count, 1)

        duplicate = dict(data["sources"][0])
        duplicate["evidence_id"] = "E002"
        data["sources"].append(duplicate)
        issues, _ = check_references.check_sources(data)
        self.assertTrue(any(item.code == "DUPLICATE_DOI" for item in issues))

    def test_authorship_validator_requires_human_accountability(self) -> None:
        data = valid_authorship_manifest()
        issues, author_ids = validate_authorship.validate_people(data)
        issues.extend(validate_authorship.validate_accountability(data, author_ids))
        ai_issues, _ = validate_authorship.validate_ai_disclosure(data)
        issues.extend(ai_issues)
        issues.extend(validate_authorship.validate_declarations(data))
        self.assertEqual(issues, [])

        data["authors"][0]["is_human"] = False
        issues, _ = validate_authorship.validate_people(data)
        self.assertTrue(
            any(item.code == "NONHUMAN_AUTHOR_PROHIBITED" for item in issues)
        )

    def test_lint_flags_placeholders_without_echoing_text(self) -> None:
        manifest = valid_manuscript_manifest()
        clean = lint_manuscript.lint_text("Verified prose without a claim.\n", manifest)
        self.assertEqual(clean, [])
        findings = lint_manuscript.lint_text("[[TODO: unresolved]]\n", manifest)
        self.assertTrue(any(item.code == "UNRESOLVED_PLACEHOLDER" for item in findings))
        self.assertTrue(all("[[TODO" not in str(item.to_dict()) for item in findings))

    def test_scaffold_is_local_and_not_submission_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "workspace"
            files = scaffold_manuscript.generate(
                output,
                document_id="test-draft",
                study_design="randomized_trial",
                guidelines=["consort-2025"],
            )
            manifest = json.loads(
                (output / "manuscript_manifest.json").read_text(encoding="utf-8")
            )
            self.assertFalse(manifest["submission_ready"])
            self.assertIn("manuscript.md", files)
            self.assertTrue((output / "claims.csv").is_file())


# The shared --help contract: every argparse CLI this skill ships answers --help
# without doing any work. It skips when the skill's packages are absent and runs
# for real under `python tests/run_all.py --isolated`.
CliHelpTests = skill_contract.cli.help_test_case(ROOT)

if __name__ == "__main__":
    unittest.main()
