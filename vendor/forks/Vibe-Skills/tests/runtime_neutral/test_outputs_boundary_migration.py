from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "config" / "outputs-boundary-policy.json"
MIGRATION_MAP_PATH = REPO_ROOT / "references" / "fixtures" / "migration-map.json"
RETIRED_FAMILIES = {
    "routing-stability": {
        "retired_outputs": {
            "outputs/verify/vibe-routing-stability-gate.json",
            "outputs/verify/vibe-routing-stability-gate.md",
        },
        "canonical_fixtures": {
            "references/fixtures/verify/routing-stability/vibe-routing-stability-gate.json",
            "references/fixtures/verify/routing-stability/vibe-routing-stability-gate.md",
        },
        "retired_allowlist_id": "verify-routing-stability-legacy-snapshot",
        "migration_map": {
            "outputs/verify/vibe-routing-stability-gate.json": "references/fixtures/verify/routing-stability/vibe-routing-stability-gate.json",
            "outputs/verify/vibe-routing-stability-gate.md": "references/fixtures/verify/routing-stability/vibe-routing-stability-gate.md",
        },
    },
    "retro-safety-gate": {
        "retired_outputs": {
            "outputs/retro/compare/safety-gate/baseline-cer.json",
            "outputs/retro/compare/safety-gate/current-cer.json",
            "outputs/retro/compare/safety-gate/delta.json",
            "outputs/retro/compare/safety-gate/delta.md",
        },
        "canonical_fixtures": {
            "references/fixtures/retro-compare/safety-gate/baseline-cer.json",
            "references/fixtures/retro-compare/safety-gate/current-cer.json",
            "references/fixtures/retro-compare/safety-gate/delta.json",
            "references/fixtures/retro-compare/safety-gate/delta.md",
        },
        "retired_allowlist_id": "retro-compare-safety-baselines",
        "migration_map": {
            "outputs/retro/compare/safety-gate/baseline-cer.json": "references/fixtures/retro-compare/safety-gate/baseline-cer.json",
            "outputs/retro/compare/safety-gate/current-cer.json": "references/fixtures/retro-compare/safety-gate/current-cer.json",
            "outputs/retro/compare/safety-gate/delta.json": "references/fixtures/retro-compare/safety-gate/delta.json",
            "outputs/retro/compare/safety-gate/delta.md": "references/fixtures/retro-compare/safety-gate/delta.md",
        },
    },
    "retro-sample-run": {
        "retired_outputs": {
            "outputs/retro/compare/sample-run/baseline-cer.json",
            "outputs/retro/compare/sample-run/current-cer.json",
            "outputs/retro/compare/sample-run/delta.json",
            "outputs/retro/compare/sample-run/delta.md",
        },
        "canonical_fixtures": {
            "references/fixtures/retro-compare/sample-run/baseline-cer.json",
            "references/fixtures/retro-compare/sample-run/current-cer.json",
            "references/fixtures/retro-compare/sample-run/delta.json",
            "references/fixtures/retro-compare/sample-run/delta.md",
        },
        "retired_allowlist_id": "retro-compare-sample-baselines",
        "migration_map": {
            "outputs/retro/compare/sample-run/baseline-cer.json": "references/fixtures/retro-compare/sample-run/baseline-cer.json",
            "outputs/retro/compare/sample-run/current-cer.json": "references/fixtures/retro-compare/sample-run/current-cer.json",
            "outputs/retro/compare/sample-run/delta.json": "references/fixtures/retro-compare/sample-run/delta.json",
            "outputs/retro/compare/sample-run/delta.md": "references/fixtures/retro-compare/sample-run/delta.md",
        },
    },
    "retro-smoke": {
        "retired_outputs": {
            "outputs/retro/compare/smoke-temp/baseline-smoke.json",
            "outputs/retro/compare/smoke-temp/current-smoke.json",
            "outputs/retro/compare/smoke-temp/delta-smoke.json",
            "outputs/retro/compare/smoke-temp/delta-smoke.md",
        },
        "canonical_fixtures": {
            "references/fixtures/retro-compare/smoke/baseline-smoke.json",
            "references/fixtures/retro-compare/smoke/current-smoke.json",
            "references/fixtures/retro-compare/smoke/delta-smoke.json",
            "references/fixtures/retro-compare/smoke/delta-smoke.md",
        },
        "retired_allowlist_id": "retro-compare-smoke-legacy",
        "migration_map": {
            "outputs/retro/compare/smoke-temp/baseline-smoke.json": "references/fixtures/retro-compare/smoke/baseline-smoke.json",
            "outputs/retro/compare/smoke-temp/current-smoke.json": "references/fixtures/retro-compare/smoke/current-smoke.json",
            "outputs/retro/compare/smoke-temp/delta-smoke.json": "references/fixtures/retro-compare/smoke/delta-smoke.json",
            "outputs/retro/compare/smoke-temp/delta-smoke.md": "references/fixtures/retro-compare/smoke/delta-smoke.md",
        },
    },
    "external-corpus": {
        "retired_outputs": {
            "outputs/external-corpus/external-corpus-gate.json",
            "outputs/external-corpus/external-corpus-gate.md",
            "outputs/external-corpus/prompt-signals.json",
            "outputs/external-corpus/skill-keyword-index.backup.json",
            "outputs/external-corpus/skill-keyword-index.candidate.json",
            "outputs/external-corpus/vco-suggestions.json",
            "outputs/external-corpus/vco-suggestions.md",
        },
        "canonical_fixtures": {
            "references/fixtures/external-corpus/external-corpus-gate.json",
            "references/fixtures/external-corpus/external-corpus-gate.md",
            "references/fixtures/external-corpus/prompt-signals.json",
            "references/fixtures/external-corpus/skill-keyword-index.backup.json",
            "references/fixtures/external-corpus/skill-keyword-index.candidate.json",
            "references/fixtures/external-corpus/vco-suggestions.json",
            "references/fixtures/external-corpus/vco-suggestions.md",
        },
        "retired_allowlist_id": "external-corpus-legacy-artifacts",
        "migration_map": {
            "outputs/external-corpus/external-corpus-gate.json": "references/fixtures/external-corpus/external-corpus-gate.json",
            "outputs/external-corpus/external-corpus-gate.md": "references/fixtures/external-corpus/external-corpus-gate.md",
            "outputs/external-corpus/prompt-signals.json": "references/fixtures/external-corpus/prompt-signals.json",
            "outputs/external-corpus/skill-keyword-index.backup.json": "references/fixtures/external-corpus/skill-keyword-index.backup.json",
            "outputs/external-corpus/skill-keyword-index.candidate.json": "references/fixtures/external-corpus/skill-keyword-index.candidate.json",
            "outputs/external-corpus/vco-suggestions.json": "references/fixtures/external-corpus/vco-suggestions.json",
            "outputs/external-corpus/vco-suggestions.md": "references/fixtures/external-corpus/vco-suggestions.md",
        },
    },
}


def git_ls_files(*paths: str) -> set[str]:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", *paths],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return set(filter(None, completed.stdout.splitlines()))


class OutputsBoundaryMigrationTests(unittest.TestCase):
    def test_retired_output_families_are_removed_from_tracked_outputs_and_policy(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        tracked_outputs = git_ls_files("outputs")
        allowlisted_patterns = {
            pattern
            for allowlisted_set in policy["allowlisted_sets"]
            for pattern in allowlisted_set["patterns"]
        }
        allowlisted_ids = {entry["id"] for entry in policy["allowlisted_sets"]}
        retired_outputs = set().union(*(family["retired_outputs"] for family in RETIRED_FAMILIES.values()))

        self.assertEqual(0, policy["expected_tracked_output_count"])
        self.assertEqual([], policy["allowlisted_sets"])
        self.assertTrue(bool(policy["enforcement"]["strict_requires_zero_tracked_outputs"]))
        self.assertEqual(0, len(tracked_outputs))
        self.assertTrue(retired_outputs.isdisjoint(tracked_outputs))
        self.assertTrue(retired_outputs.isdisjoint(allowlisted_patterns))
        for family in RETIRED_FAMILIES.values():
            self.assertNotIn(family["retired_allowlist_id"], allowlisted_ids)

    def test_retired_output_family_fixture_roots_remain_canonical(self) -> None:
        migration_map = json.loads(MIGRATION_MAP_PATH.read_text(encoding="utf-8"))
        mapping_index = {entry["source"]: entry["destination"] for entry in migration_map["mappings"]}

        for family in RETIRED_FAMILIES.values():
            self.assertEqual(family["migration_map"], {key: mapping_index[key] for key in family["migration_map"]})
            self.assertEqual(
                family["canonical_fixtures"],
                git_ls_files(*sorted(family["canonical_fixtures"])),
            )
            for destination in family["migration_map"].values():
                self.assertTrue((REPO_ROOT / destination).exists(), destination)


if __name__ == "__main__":
    unittest.main()
