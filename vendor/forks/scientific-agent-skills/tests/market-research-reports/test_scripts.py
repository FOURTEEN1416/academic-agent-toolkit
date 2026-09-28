"""Synthetic, dependency-free tests for the bundled local CLIs."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "market-research-reports"
SCRIPTS = SKILL_ROOT / "scripts"
ASSETS = SKILL_ROOT / "assets"
sys.path.insert(0, str(SCRIPTS))

from _common import ValidationError, read_csv_records  # noqa: E402
from audit_claim_citations import (  # noqa: E402
    CLAIM_FIELDS,
    _load_sources,
    audit,
)
from calculate_market_sizing import calculate  # noqa: E402
from check_unit_consistency import (  # noqa: E402
    REQUIRED_FIELDS as CONSISTENCY_FIELDS,
    check,
)
from forecast_sensitivity import forecast  # noqa: E402
from generate_report_scaffold import (  # noqa: E402
    generate,
    validate_manifest,
)
from validate_competitor_matrix import (  # noqa: E402
    REQUIRED_FIELDS as COMPETITOR_FIELDS,
    validate as validate_competitors,
)
from validate_evidence_ledger import _load_records, validate_records  # noqa: E402

import skill_contract


def load_json(name: str) -> dict:
    with (ASSETS / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


class EvidenceLedgerTests(unittest.TestCase):
    def test_synthetic_source_ledger_is_valid(self) -> None:
        report = validate_records(
            _load_records(ASSETS / "source_ledger_template.csv")
        )
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["source_count"], 3)

    def test_duplicate_source_id_fails(self) -> None:
        records = _load_records(ASSETS / "source_ledger_template.csv")
        records.append(copy.deepcopy(records[0]))
        report = validate_records(records)
        self.assertFalse(report["valid"])
        self.assertTrue(any("duplicate" in error for error in report["errors"]))

    def test_not_stated_publication_date_warns_without_crashing(self) -> None:
        records = _load_records(ASSETS / "source_ledger_template.csv")
        records[0]["publication_date"] = "not-stated"
        report = validate_records(records)
        self.assertTrue(report["valid"], report["errors"])
        self.assertTrue(
            any("publication date is not stated" in warning
                for warning in report["warnings"])
        )

    def test_retrieval_before_publication_fails(self) -> None:
        records = _load_records(ASSETS / "source_ledger_template.csv")
        records[0]["publication_date"] = "2026-07-30"
        records[0]["retrieval_date"] = "2026-07-01"
        report = validate_records(records)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("retrieval_date precedes publication_date" in error
                for error in report["errors"])
        )


class MarketSizingTests(unittest.TestCase):
    def test_synthetic_sizing_reconciles_and_returns_scenarios(self) -> None:
        result = calculate(load_json("market_sizing_scenarios_template.json"))
        self.assertEqual(result["method_estimates"]["top_down_tam"], 100_000_000)
        self.assertEqual(result["method_estimates"]["bottom_up_tam"], 84_000_000)
        self.assertEqual(len(result["scenario_results"]), 3)
        self.assertTrue(result["reconciliation"]["within_tolerance"])

    def test_duplicate_coverage_key_is_rejected(self) -> None:
        payload = load_json("market_sizing_scenarios_template.json")
        payload["top_down"]["components"][1]["coverage_key"] = (
            payload["top_down"]["components"][0]["coverage_key"]
        )
        with self.assertRaisesRegex(ValidationError, "duplicate"):
            calculate(payload)

    def test_inconsistent_denominator_is_rejected(self) -> None:
        payload = load_json("market_sizing_scenarios_template.json")
        payload["bottom_up"]["components"][0]["denominator_id"] = "other-denominator"
        with self.assertRaisesRegex(ValidationError, "denominator"):
            calculate(payload)


class ForecastTests(unittest.TestCase):
    def test_synthetic_forecast_returns_range_and_sensitivity(self) -> None:
        result = forecast(load_json("forecast_sensitivity_template.json"))
        self.assertEqual(len(result["scenarios"]), 3)
        self.assertEqual(len(result["scenario_range_by_year"]), 6)
        upside = next(
            item for item in result["scenarios"] if item["scenario_id"] == "upside"
        )
        self.assertAlmostEqual(upside["endpoint"], 146_932_807.68, places=2)
        self.assertEqual(len(result["sensitivity"]["results"]), 5)

    def test_unvalidated_probability_is_rejected(self) -> None:
        payload = load_json("forecast_sensitivity_template.json")
        payload["scenarios"][0]["probability"] = 0.2
        with self.assertRaisesRegex(ValidationError, "probability"):
            forecast(payload)

    def test_horizon_rejects_float_string_and_boolean_values(self) -> None:
        for invalid in (5.0, "5", True):
            with self.subTest(invalid=invalid):
                payload = load_json("forecast_sensitivity_template.json")
                payload["horizon_years"] = invalid
                with self.assertRaisesRegex(ValidationError, "integer"):
                    forecast(payload)


class CompetitorMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = read_csv_records(
            ASSETS / "competitor_feature_matrix_template.csv",
            required_fields=COMPETITOR_FIELDS,
        )
        self.source_ids = {
            record["source_id"]
            for record in _load_records(ASSETS / "source_ledger_template.csv")
        }

    def test_complete_synthetic_matrix_is_valid(self) -> None:
        report = validate_competitors(self.rows, self.source_ids)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["expected_pair_count"], 4)

    def test_incomplete_matrix_fails(self) -> None:
        report = validate_competitors(self.rows[:-1], self.source_ids)
        self.assertFalse(report["valid"])
        self.assertTrue(any("incomplete" in error for error in report["errors"]))


class ClaimAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.claims = read_csv_records(
            ASSETS / "claims_ledger_template.csv", required_fields=CLAIM_FIELDS
        )
        self.sources = _load_sources(ASSETS / "source_ledger_template.csv")

    def test_synthetic_claims_are_fully_mapped(self) -> None:
        report = audit(self.claims, self.sources)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["uncited_claim_ids"], [])

    def test_uncited_forecast_fails(self) -> None:
        claims = copy.deepcopy(self.claims)
        claims[2]["source_ids"] = ""
        report = audit(claims, self.sources)
        self.assertFalse(report["valid"])
        self.assertIn("C-003", report["uncited_claim_ids"])


class ConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = read_csv_records(
            ASSETS / "consistency_check_template.csv",
            required_fields=CONSISTENCY_FIELDS,
        )

    def test_synthetic_comparison_group_is_consistent(self) -> None:
        report = check(self.rows)
        self.assertTrue(report["valid"], report["errors"])

    def test_mixed_currency_fails(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows[1]["currency"] = "EUR"
        report = check(rows)
        self.assertFalse(report["valid"])
        self.assertIn("annual-market-spend", report["mismatches"])


class ScaffoldTests(unittest.TestCase):
    def test_scaffold_creates_only_expected_local_files(self) -> None:
        manifest = validate_manifest(load_json("report_manifest_template.json"))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report-workspace"
            result = generate(manifest, output)
            self.assertTrue(result["created"])
            self.assertTrue((output / "report.md").is_file())
            self.assertTrue((output / "data" / "source_ledger.csv").is_file())
            self.assertTrue(
                (output / "analysis" / "market_sizing.json").is_file()
            )
            with self.assertRaisesRegex(ValidationError, "already exists"):
                generate(manifest, output)


# The shared --help contract: every argparse CLI this skill ships answers --help
# without doing any work. It skips when the skill's packages are absent and runs
# for real under `python tests/run_all.py --isolated`.
CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

if __name__ == "__main__":
    unittest.main()
