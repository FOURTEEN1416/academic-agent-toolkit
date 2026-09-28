#!/usr/bin/env python3
"""Tests for the waypoint-bio skill's bundled scripts.

The conversion tests run against synthetic MetaPhlAn / Kraken2 / QIIME 2
fixtures and need only pandas. The coverage tests use a stub tokenizer, so no
model download and no Hugging Face access is required.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "waypoint-bio"
SCRIPTS_DIR = SKILL_ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(SCRIPTS_DIR))

import skill_contract  # noqa: E402

pd = None
try:
    import pandas as pd  # noqa: E402
except ImportError:  # pragma: no cover - environment dependent
    pd = None

if pd is not None:
    import profiler_to_waypoint as converter  # noqa: E402
    import vocab_coverage  # noqa: E402


CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

requires_pandas = unittest.skipIf(pd is None, "pandas not installed")


def run_script(name: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / name), *arguments],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=120,
    )


LACTOBACILLUS = (
    "k__Bacteria; p__Firmicutes; c__Bacilli; o__Lactobacillales; "
    "f__Lactobacillaceae; g__Lactobacillus"
)
BACTEROIDES = (
    "k__Bacteria; p__Bacteroidota; c__Bacteroidia; o__Bacteroidales; "
    "f__Bacteroidaceae; g__Bacteroides"
)


class LineageNormalisationTests(unittest.TestCase):
    """The tokenizer only reads k__/p__/c__/o__/f__/g__/s__ segments split on ';'."""

    @requires_pandas
    def test_pipe_separator_becomes_semicolon(self) -> None:
        self.assertEqual(
            converter.normalise_lineage("k__Bacteria|p__Firmicutes|g__Lactobacillus"),
            "k__Bacteria; p__Firmicutes; g__Lactobacillus",
        )

    @requires_pandas
    def test_domain_prefix_is_rewritten_to_kingdom(self) -> None:
        # SILVA/Greengenes2 write d__; the tokenizer would skip it entirely.
        self.assertEqual(
            converter.normalise_lineage("d__Bacteria; p__Firmicutes"),
            "k__Bacteria; p__Firmicutes",
        )

    @requires_pandas
    def test_strain_and_empty_segments_are_dropped(self) -> None:
        self.assertEqual(
            converter.normalise_lineage("k__Bacteria; g__Lactobacillus; s__; t__SGB1"),
            "k__Bacteria; g__Lactobacillus",
        )

    @requires_pandas
    def test_deepest_rank(self) -> None:
        self.assertEqual(converter.deepest_rank(LACTOBACILLUS), "genus")
        self.assertEqual(
            converter.deepest_rank(LACTOBACILLUS + "; s__Lactobacillus gasseri"),
            "species",
        )
        self.assertIsNone(converter.deepest_rank("root; cellular organisms"))


class MetaphlanConversionTests(unittest.TestCase):
    @requires_pandas
    def test_species_rows_only_and_renormalised(self) -> None:
        matrix = converter.parse_metaphlan(
            FIXTURES / "metaphlan_merged.tsv", rank="species"
        )
        # The cumulative parent rows must not be double counted.
        self.assertEqual(len(matrix.columns), 2)
        self.assertEqual(sorted(matrix.index), ["sampleA", "sampleB"])

        frame = converter.matrix_to_waypoint(matrix)
        self.assertAlmostEqual(sum(frame.loc["sampleA", "Relative Abundances"]), 1.0)
        self.assertAlmostEqual(sum(frame.loc["sampleB", "Relative Abundances"]), 1.0)

        taxa = frame.loc["sampleA", "Taxa"]
        abundances = dict(zip(taxa, frame.loc["sampleA", "Relative Abundances"]))
        gasseri = LACTOBACILLUS + "; s__Lactobacillus_gasseri"
        self.assertIn(gasseri, abundances)
        self.assertAlmostEqual(abundances[gasseri], 0.6)
        self.assertTrue(all("|" not in t for t in taxa))

    @requires_pandas
    def test_genus_rank_selection(self) -> None:
        matrix = converter.parse_metaphlan(
            FIXTURES / "metaphlan_merged.tsv", rank="genus"
        )
        self.assertIn(LACTOBACILLUS, matrix.columns)
        self.assertIn(BACTEROIDES, matrix.columns)


class KrakenConversionTests(unittest.TestCase):
    @requires_pandas
    def test_lineage_rebuilt_from_indentation(self) -> None:
        matrix = converter.parse_kraken(
            [FIXTURES / "sampleA.kreport", FIXTURES / "sampleB.kreport"],
            rank="species",
        )
        self.assertEqual(sorted(matrix.index), ["sampleA", "sampleB"])
        gasseri = LACTOBACILLUS + "; s__Lactobacillus gasseri"
        uniformis = BACTEROIDES + "; s__Bacteroides uniformis"
        self.assertIn(gasseri, matrix.columns)
        self.assertIn(uniformis, matrix.columns)

    @requires_pandas
    def test_subranks_and_unclassified_excluded(self) -> None:
        series = converter.parse_kraken_report(
            FIXTURES / "sampleA.kreport", rank="species"
        )
        # S1 strain row and the U unclassified row must not appear.
        self.assertTrue(all("strain X" not in name for name in series.index))
        self.assertTrue(all("unclassified" not in name for name in series.index))
        self.assertEqual(len(series), 2)

    @requires_pandas
    def test_counts_normalise_to_relative_abundance(self) -> None:
        matrix = converter.parse_kraken(
            [FIXTURES / "sampleB.kreport"], rank="species"
        )
        frame = converter.matrix_to_waypoint(matrix)
        abundances = dict(
            zip(frame.loc["sampleB", "Taxa"], frame.loc["sampleB", "Relative Abundances"])
        )
        uniformis = BACTEROIDES + "; s__Bacteroides uniformis"
        self.assertAlmostEqual(abundances[uniformis], 6000 / 8000)


class QiimeConversionTests(unittest.TestCase):
    @requires_pandas
    def test_biom_banner_taxonomy_column_and_unassigned(self) -> None:
        matrix = converter.parse_table(
            FIXTURES / "qiime2_table.tsv",
            taxonomy_column="taxonomy",
            orientation="auto",
        )
        self.assertEqual(sorted(matrix.index), ["sampleA", "sampleB"])
        self.assertIn(LACTOBACILLUS, matrix.columns)
        self.assertIn(BACTEROIDES, matrix.columns)
        # "Unassigned" has no rank prefix, so it normalises to an empty string
        # and is dropped rather than becoming a bogus token.
        self.assertNotIn("Unassigned", matrix.columns)

        frame = converter.matrix_to_waypoint(matrix)
        abundances = dict(
            zip(frame.loc["sampleA", "Taxa"], frame.loc["sampleA", "Relative Abundances"])
        )
        self.assertAlmostEqual(abundances[LACTOBACILLUS], 0.6)


class WaypointFormatTests(unittest.TestCase):
    @requires_pandas
    def test_duplicate_lineages_are_summed(self) -> None:
        matrix = pd.DataFrame(
            [[1.0, 2.0, 1.0]],
            index=pd.Index(["s1"], name="sample_id"),
            columns=[LACTOBACILLUS, BACTEROIDES, LACTOBACILLUS],
        )
        frame = converter.matrix_to_waypoint(matrix)
        abundances = dict(
            zip(frame.loc["s1", "Taxa"], frame.loc["s1", "Relative Abundances"])
        )
        self.assertEqual(len(abundances), 2)
        self.assertAlmostEqual(abundances[LACTOBACILLUS], 0.5)

    @requires_pandas
    def test_zero_total_sample_is_rejected(self) -> None:
        matrix = pd.DataFrame(
            [[0.0, 0.0]], index=["s1"], columns=[LACTOBACILLUS, BACTEROIDES]
        )
        with self.assertRaises(ValueError):
            converter.matrix_to_waypoint(matrix)

    @requires_pandas
    def test_min_abundance_filter(self) -> None:
        matrix = pd.DataFrame(
            [[0.99999, 0.00001]], index=["s1"], columns=[LACTOBACILLUS, BACTEROIDES]
        )
        frame = converter.matrix_to_waypoint(matrix, min_abundance=1e-4)
        self.assertEqual(frame.loc["s1", "Taxa"], [LACTOBACILLUS])


class ConverterCliTests(unittest.TestCase):
    @requires_pandas
    def test_metaphlan_end_to_end_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dataset.csv"
            result = run_script(
                "profiler_to_waypoint.py",
                "--input", str(FIXTURES / "metaphlan_merged.tsv"),
                "--format", "metaphlan",
                "--metadata", str(FIXTURES / "labels.csv"),
                "--output", str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.exists())

            frame = vocab_coverage.load_dataframe(output)
            self.assertIn("Group", frame.columns)
            self.assertEqual(sorted(frame["Group"]), ["Case", "Control"])
            self.assertEqual(len(frame.loc[0, "Taxa"]), 2)

    @requires_pandas
    def test_kraken_end_to_end_parquet(self) -> None:
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            self.skipTest("pyarrow not installed")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dataset.parquet"
            result = run_script(
                "profiler_to_waypoint.py",
                "--input",
                str(FIXTURES / "sampleA.kreport"),
                str(FIXTURES / "sampleB.kreport"),
                "--format", "kraken",
                "--output", str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            frame = pd.read_parquet(output)
            self.assertEqual(sorted(frame.index), ["sampleA", "sampleB"])
            self.assertIn("Taxa", frame.columns)

    def test_missing_input_is_an_error(self) -> None:
        result = run_script(
            "profiler_to_waypoint.py",
            "--input", "does_not_exist.tsv",
            "--format", "metaphlan",
            "--output", "out.parquet",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("input not found", result.stderr)


class StubTokenizer:
    """Minimal stand-in for TaxonomicTokenizer: genus tokens only, no fallback."""

    unk_token_id = 1

    def __init__(self, known: set[str]) -> None:
        self._vocab = {"<pad>": 0, "<unk>": 1}
        for index, token in enumerate(sorted(known), start=2):
            self._vocab[token] = index

    def get_vocab(self) -> dict[str, int]:
        return dict(self._vocab)

    def convert_tokens_to_ids(self, token: str) -> int:
        genus = next(
            (
                segment.strip()
                for segment in str(token).split(";")
                if segment.strip().startswith("g__")
            ),
            None,
        )
        return self._vocab.get(genus, self.unk_token_id)


class VocabCoverageTests(unittest.TestCase):
    @requires_pandas
    def test_coverage_weights_by_abundance(self) -> None:
        frame = pd.DataFrame(
            {
                "Taxa": [[LACTOBACILLUS, BACTEROIDES]],
                "Relative Abundances": [[0.9, 0.1]],
            },
            index=pd.Index(["s1"], name="sample_id"),
        )
        tokenizer = StubTokenizer({"g__Lactobacillus"})
        report, missing = vocab_coverage.coverage_report(frame, tokenizer)

        # Half the taxa are known, but they carry 90% of the abundance.
        self.assertAlmostEqual(report.loc["s1", "taxon_coverage"], 0.5)
        self.assertAlmostEqual(report.loc["s1", "abundance_coverage"], 0.9)
        self.assertEqual(missing[BACTEROIDES], 1)

    @requires_pandas
    def test_sample_with_no_known_taxa(self) -> None:
        frame = pd.DataFrame(
            {"Taxa": [[BACTEROIDES]], "Relative Abundances": [[1.0]]},
            index=pd.Index(["s1"], name="sample_id"),
        )
        report, _ = vocab_coverage.coverage_report(frame, StubTokenizer(set()))
        self.assertEqual(report.loc["s1", "n_in_vocab"], 0)
        self.assertAlmostEqual(report.loc["s1", "abundance_coverage"], 0.0)

    @requires_pandas
    def test_non_waypoint_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text("a,b\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                vocab_coverage.load_dataframe(path)


if __name__ == "__main__":
    unittest.main()
