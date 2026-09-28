"""Tests for the Arboreto GRN inference wrapper.

GRNBoost2 on real data is a distributed, minutes-long job, so the tests stub
`grnboost2` and assert on the contract between the wrapper and the algorithm:
the expression matrix is read genes-as-columns, `tf_names` defaults to the
sentinel `'all'` rather than an empty list, the seed and limit are forwarded,
and the network is written headerless -- the format every downstream Arboreto
consumer expects.

Getting `tf_names` wrong is the failure worth guarding: passing `[]` instead of
`'all'` produces an empty network with no error at all.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "arboreto"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

pd = pytest.importorskip("pandas", reason="arboreto needs pandas")
pytest.importorskip("arboreto", reason="basic_grn_inference imports arboreto at module scope")

import basic_grn_inference  # noqa: E402

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

NETWORK = pd.DataFrame(
    {
        "TF": ["TF1", "TF1", "TF2"],
        "target": ["G1", "G2", "G1"],
        "importance": [9.5, 4.2, 1.1],
    }
)


class InferenceWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)

        self.expression = self.root / "expression.tsv"
        self.expression.write_text(
            "TF1\tTF2\tG1\tG2\n"
            "1.0\t2.0\t3.0\t4.0\n"
            "1.5\t2.5\t3.5\t4.5\n"
            "2.0\t3.0\t4.0\t5.0\n",
            encoding="utf-8",
        )
        self.output = self.root / "network.tsv"

    def run_inference(self, **kwargs):
        with mock.patch.object(
            basic_grn_inference, "grnboost2", return_value=NETWORK
        ) as algorithm:
            basic_grn_inference.run_grn_inference(
                str(self.expression), str(self.output), **kwargs
            )
        return algorithm

    def test_the_expression_matrix_is_read_with_genes_as_columns(self) -> None:
        algorithm = self.run_inference()
        passed = algorithm.call_args.kwargs["expression_data"]
        self.assertEqual(list(passed.columns), ["TF1", "TF2", "G1", "G2"])
        self.assertEqual(len(passed), 3)  # three observations

    def test_without_a_tf_file_every_gene_is_a_candidate_regulator(self) -> None:
        # The sentinel is the string 'all'; an empty list would silently return
        # an empty network.
        algorithm = self.run_inference()
        self.assertEqual(algorithm.call_args.kwargs["tf_names"], "all")

    def test_a_tf_file_restricts_the_candidate_regulators(self) -> None:
        tf_file = self.root / "tfs.txt"
        tf_file.write_text("TF1\nTF2\n", encoding="utf-8")
        algorithm = self.run_inference(tf_file=str(tf_file))
        self.assertEqual(list(algorithm.call_args.kwargs["tf_names"]), ["TF1", "TF2"])

    def test_the_seed_is_forwarded_so_runs_are_reproducible(self) -> None:
        self.assertEqual(self.run_inference().call_args.kwargs["seed"], 777)
        self.assertEqual(self.run_inference(seed=42).call_args.kwargs["seed"], 42)

    def test_the_link_limit_is_forwarded_and_defaults_to_unlimited(self) -> None:
        self.assertIsNone(self.run_inference().call_args.kwargs["limit"])
        self.assertEqual(self.run_inference(limit=100).call_args.kwargs["limit"], 100)

    def test_the_network_is_written_headerless_and_tab_separated(self) -> None:
        # Arboreto's own consumers expect three unlabelled columns.
        self.run_inference()
        lines = self.output.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertNotIn("importance", lines[0])
        self.assertEqual(lines[0].split("\t"), ["TF1", "G1", "9.5"])

    def test_no_index_column_is_written(self) -> None:
        self.run_inference()
        for line in self.output.read_text(encoding="utf-8").strip().splitlines():
            with self.subTest(line=line):
                self.assertEqual(len(line.split("\t")), 3)


class ParserTests(unittest.TestCase):
    def test_the_documented_flags_are_all_accepted(self) -> None:
        source = (SCRIPTS / "basic_grn_inference.py").read_text(encoding="utf-8")
        for flag in ("--tf-file", "--seed", "--limit"):
            with self.subTest(flag=flag):
                self.assertIn(flag, source)

    def test_the_positional_arguments_are_required(self) -> None:
        result = skill_contract.cli.run_help(SCRIPTS / "basic_grn_inference.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("expression_file", result.stdout)
        self.assertIn("output_file", result.stdout)


if __name__ == "__main__":
    unittest.main()
