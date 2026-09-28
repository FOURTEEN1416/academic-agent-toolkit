"""Tests for the PyDESeq2 analysis driver.

Everything expensive in this script happens inside PyDESeq2; what the script
itself owns is the data handling around it, and each piece of that is a way to
get a plausible-looking but wrong answer:

* orientation -- the counts file is genes x samples and DESeq2 wants samples x
  genes, so a transposition mistake silently analyses genes as if they were
  samples;
* alignment -- counts and metadata must end up on the same index in the same
  order, or every sample is compared against another sample's condition;
* the shrinkage coefficient -- `condition[T.treated]` is a formulaic naming
  convention, and the test below checks it against a design matrix PyDESeq2
  actually built rather than against the string the script composes;
* thresholds -- gene filtering is `>=` and significance is a strict `<`, both
  pinned at the boundary here.

One end-to-end fit runs on a synthetic dataset with a known 8-fold change, so
the pipeline is checked against log2(8) = 3 rather than against itself.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "pydeseq2"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

np = pytest.importorskip("numpy", reason="pydeseq2 scripts need numpy")
pd = pytest.importorskip("pandas", reason="pydeseq2 scripts need pandas")
pytest.importorskip("pydeseq2", reason="pydeseq2 skill needs pydeseq2")
anndata = pytest.importorskip("anndata", reason="save_results writes an .h5ad")
matplotlib = pytest.importorskip("matplotlib", reason="create_plots needs matplotlib")

matplotlib.use("Agg")  # never open a window; must precede pyplot import
import matplotlib.pyplot as plt  # noqa: E402

import run_deseq2_analysis as driver  # noqa: E402

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


class TemporaryDirectoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)

    def write_csv(self, name: str, frame: pd.DataFrame) -> Path:
        path = self.root / name
        frame.to_csv(path)
        return path


class LoadAndValidateTests(TemporaryDirectoryTestCase):
    """The counts file is genes x samples; DESeq2 needs samples x genes."""

    def setUp(self) -> None:
        super().setUp()
        # Two genes, three samples. GENE1 in s3 is 6 -- a unique value, so the
        # orientation of the result can be checked by where it lands.
        self.counts = pd.DataFrame(
            {"s1": [1, 10], "s2": [2, 20], "s3": [6, 30]},
            index=["GENE1", "GENE2"],
        )
        self.metadata = pd.DataFrame(
            {"condition": ["control", "control", "treated"]},
            index=["s1", "s2", "s3"],
        )
        self.counts_path = self.write_csv("counts.csv", self.counts)
        self.metadata_path = self.write_csv("metadata.csv", self.metadata)

    def test_the_counts_matrix_is_transposed_by_default(self) -> None:
        counts, metadata = driver.load_and_validate_data(
            self.counts_path, self.metadata_path
        )
        self.assertEqual(list(counts.index), ["s1", "s2", "s3"])
        self.assertEqual(list(counts.columns), ["GENE1", "GENE2"])
        # The value that was at (GENE1, s3) must now be at (s3, GENE1).
        self.assertEqual(counts.loc["s3", "GENE1"], 6)
        self.assertEqual(list(metadata.index), ["s1", "s2", "s3"])

    def test_an_already_oriented_matrix_is_left_alone(self) -> None:
        path = self.write_csv("oriented.csv", self.counts.T)
        counts, _ = driver.load_and_validate_data(
            path, self.metadata_path, transpose_counts=False
        )
        self.assertEqual(list(counts.index), ["s1", "s2", "s3"])
        self.assertEqual(counts.loc["s3", "GENE1"], 6)

    def test_negative_counts_are_rejected(self) -> None:
        # DESeq2's negative-binomial model has no meaning for negative counts;
        # they indicate the file holds normalised or logged values.
        broken = self.counts.copy()
        broken.loc["GENE1", "s2"] = -5
        with self.assertRaisesRegex(ValueError, "negative values"):
            driver.load_and_validate_data(
                self.write_csv("negative.csv", broken), self.metadata_path
            )

    def test_zero_counts_are_accepted(self) -> None:
        # Zero is a legitimate observation -- only negatives are invalid.
        zeroed = self.counts.copy()
        zeroed.loc["GENE1", "s2"] = 0
        counts, _ = driver.load_and_validate_data(
            self.write_csv("zeroed.csv", zeroed), self.metadata_path
        )
        self.assertEqual(counts.loc["s2", "GENE1"], 0)

    def test_extra_metadata_samples_are_dropped_to_the_intersection(self) -> None:
        # Unequal lengths: element-wise index comparison raises here, so this
        # is the case the intersection fallback exists for.
        extra = pd.DataFrame(
            {"condition": ["control", "control", "treated", "treated"]},
            index=["s1", "s2", "s3", "s4"],
        )
        counts, metadata = driver.load_and_validate_data(
            self.counts_path, self.write_csv("extra.csv", extra)
        )
        self.assertEqual(list(counts.index), ["s1", "s2", "s3"])
        self.assertEqual(list(metadata.index), ["s1", "s2", "s3"])

    def test_extra_count_samples_are_dropped_to_the_intersection(self) -> None:
        wider = self.counts.copy()
        wider["s4"] = [7, 40]
        counts, metadata = driver.load_and_validate_data(
            self.write_csv("wider.csv", wider), self.metadata_path
        )
        self.assertEqual(list(counts.index), ["s1", "s2", "s3"])
        self.assertTrue(counts.index.equals(metadata.index))

    def test_a_reordered_metadata_index_is_realigned_not_left_shuffled(self) -> None:
        # Same samples, different order. If the two frames were handed to
        # DESeq2 as-is, every sample would carry another sample's condition.
        shuffled = self.metadata.loc[["s3", "s1", "s2"]]
        counts, metadata = driver.load_and_validate_data(
            self.counts_path, self.write_csv("shuffled.csv", shuffled)
        )
        self.assertTrue(counts.index.equals(metadata.index))
        self.assertEqual(metadata.loc["s3", "condition"], "treated")

    def test_a_matching_pair_survives_untouched(self) -> None:
        counts, metadata = driver.load_and_validate_data(
            self.counts_path, self.metadata_path
        )
        self.assertEqual(counts.shape, (3, 2))
        self.assertEqual(metadata.shape, (3, 1))


class FilterDataTests(unittest.TestCase):
    def setUp(self) -> None:
        # Column totals: KEEP 30, EDGE 10, DROP 9.
        self.counts = pd.DataFrame(
            {"KEEP": [10, 10, 10], "EDGE": [5, 5, 0], "DROP": [3, 3, 3]},
            index=["s1", "s2", "s3"],
        )
        self.metadata = pd.DataFrame(
            {"condition": ["control", "treated", "treated"]},
            index=["s1", "s2", "s3"],
        )

    def test_genes_below_the_total_count_threshold_are_removed(self) -> None:
        counts, _ = driver.filter_data(self.counts, self.metadata, min_counts=10)
        self.assertEqual(list(counts.columns), ["KEEP", "EDGE"])

    def test_the_threshold_is_inclusive_at_the_boundary(self) -> None:
        # EDGE totals exactly 10; `>=` keeps it and `>` would not.
        counts, _ = driver.filter_data(self.counts, self.metadata, min_counts=10)
        self.assertIn("EDGE", counts.columns)
        counts, _ = driver.filter_data(self.counts, self.metadata, min_counts=11)
        self.assertNotIn("EDGE", counts.columns)

    def test_a_zero_threshold_keeps_every_gene(self) -> None:
        counts, _ = driver.filter_data(self.counts, self.metadata, min_counts=0)
        self.assertEqual(list(counts.columns), ["KEEP", "EDGE", "DROP"])

    def test_samples_with_no_condition_are_dropped_from_both_frames(self) -> None:
        metadata = self.metadata.copy()
        metadata.loc["s2", "condition"] = np.nan
        counts, filtered = driver.filter_data(
            self.counts, metadata, min_counts=0, condition_col="condition"
        )
        self.assertEqual(list(counts.index), ["s1", "s3"])
        self.assertEqual(list(filtered.index), ["s1", "s3"])

    def test_no_samples_are_dropped_when_the_column_is_absent(self) -> None:
        counts, metadata = driver.filter_data(
            self.counts, self.metadata, min_counts=0, condition_col="batch"
        )
        self.assertEqual(len(counts.index), 3)
        self.assertEqual(len(metadata.index), 3)

    def test_gene_filtering_does_not_disturb_the_sample_axis(self) -> None:
        counts, metadata = driver.filter_data(
            self.counts, self.metadata, min_counts=10, condition_col="condition"
        )
        self.assertTrue(counts.index.equals(metadata.index))


class ShrinkageCoefficientTests(unittest.TestCase):
    """`condition[T.treated]` is formulaic's name for the contrast column."""

    class FakeDataSet:
        def __init__(self, columns: list[str]) -> None:
            self.obsm = {"design_matrix": pd.DataFrame(columns=columns)}

    def test_the_coefficient_name_follows_the_design_matrix(self) -> None:
        dds = self.FakeDataSet(["Intercept", "condition[T.treated]"])
        self.assertEqual(
            driver.infer_shrink_coeff(dds, ["condition", "treated", "control"]),
            "condition[T.treated]",
        )

    def test_an_absent_coefficient_raises_and_names_the_alternatives(self) -> None:
        # Reference level as the test level is the classic mistake; the error
        # has to show what the design actually offers.
        dds = self.FakeDataSet(["Intercept", "condition[T.treated]"])
        with self.assertRaises(ValueError) as raised:
            driver.infer_shrink_coeff(dds, ["condition", "control", "treated"])
        message = str(raised.exception)
        self.assertIn("condition[T.control]", message)
        self.assertIn("condition[T.treated]", message)
        self.assertIn("--no-shrink", message)

    def test_a_multi_factor_design_resolves_the_requested_variable_only(self) -> None:
        dds = self.FakeDataSet(
            ["Intercept", "batch[T.b2]", "condition[T.treated]"]
        )
        self.assertEqual(
            driver.infer_shrink_coeff(dds, ["condition", "treated", "control"]),
            "condition[T.treated]",
        )


class FakeStats:
    """A `DeseqStats` stand-in exposing only `results_df`."""

    def __init__(self, results: pd.DataFrame) -> None:
        self.results_df = results


class FakeDataSet:
    """A `DeseqDataSet` stand-in whose h5ad export is a real AnnData."""

    def __init__(self, samples: int = 2, genes: int = 3) -> None:
        self._adata = anndata.AnnData(
            X=np.arange(samples * genes, dtype="float32").reshape(samples, genes)
        )

    def to_picklable_anndata(self):
        return self._adata


def results_frame() -> pd.DataFrame:
    """Four genes spanning the significance boundary, plus a filtered-out gene."""
    return pd.DataFrame(
        {
            "baseMean": [500.0, 100.0, 80.0, 60.0],
            "log2FoldChange": [3.0, -2.0, 0.1, 0.5],
            "pvalue": [1e-30, 1e-10, 0.4, np.nan],
            # 0.05 exactly must NOT count as significant: the test is `< 0.05`.
            "padj": [1e-28, 0.01, 0.05, np.nan],
        },
        index=["UP", "DOWN", "BORDERLINE", "FILTERED"],
    )


class SaveResultsTests(TemporaryDirectoryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.results = results_frame()
        self.output = self.root / "results"
        driver.save_results(FakeStats(self.results), FakeDataSet(), self.output)

    def test_the_four_documented_artefacts_are_written(self) -> None:
        written = {path.name for path in self.output.iterdir()}
        self.assertEqual(
            written,
            {
                "deseq2_results.csv",
                "significant_genes.csv",
                "results_sorted_by_padj.csv",
                "deseq_dataset.h5ad",
            },
        )

    def test_every_gene_is_kept_in_the_full_table(self) -> None:
        full = pd.read_csv(self.output / "deseq2_results.csv", index_col=0)
        self.assertEqual(list(full.index), ["UP", "DOWN", "BORDERLINE", "FILTERED"])

    def test_only_genes_strictly_below_the_fdr_cutoff_are_significant(self) -> None:
        significant = pd.read_csv(self.output / "significant_genes.csv", index_col=0)
        # BORDERLINE sits exactly at 0.05 and FILTERED has no padj at all.
        self.assertEqual(sorted(significant.index), ["DOWN", "UP"])

    def test_the_sorted_table_puts_the_strongest_evidence_first(self) -> None:
        sorted_results = pd.read_csv(
            self.output / "results_sorted_by_padj.csv", index_col=0
        )
        self.assertEqual(list(sorted_results.index)[:2], ["UP", "DOWN"])
        # A gene with no adjusted p-value must sort last, not first.
        self.assertEqual(list(sorted_results.index)[-1], "FILTERED")

    def test_the_dataset_is_exported_as_readable_h5ad_not_a_pickle(self) -> None:
        # Pickles execute arbitrary code on load; h5ad does not.
        loaded = anndata.read_h5ad(self.output / "deseq_dataset.h5ad")
        self.assertEqual(loaded.shape, (2, 3))

    def test_a_missing_output_directory_is_created(self) -> None:
        nested = self.root / "a" / "b" / "c"
        driver.save_results(FakeStats(self.results), FakeDataSet(), nested)
        self.assertTrue((nested / "deseq2_results.csv").is_file())

    def test_no_significant_genes_still_writes_every_file(self) -> None:
        # An empty result set is a valid outcome, not an error.
        nothing = self.results.copy()
        nothing["padj"] = 0.9
        output = self.root / "none"
        driver.save_results(FakeStats(nothing), FakeDataSet(), output)
        significant = pd.read_csv(output / "significant_genes.csv", index_col=0)
        self.assertEqual(len(significant), 0)


class PlotTests(TemporaryDirectoryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.addCleanup(plt.close, "all")
        self.results = results_frame()

    def test_both_plots_are_written_as_non_empty_files(self) -> None:
        driver.create_plots(FakeStats(self.results), self.root)
        for name in ("volcano_plot.png", "ma_plot.png"):
            with self.subTest(name=name):
                path = self.root / name
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 0)

    def test_plotting_does_not_mutate_the_results_table(self) -> None:
        # The volcano plot adds a -log10 column; leaking it into results_df
        # would put a derived column into every file written afterwards.
        stats = FakeStats(self.results)
        driver.create_plots(stats, self.root)
        self.assertEqual(list(stats.results_df.columns), list(results_frame().columns))

    def test_genes_filtered_out_by_deseq2_do_not_break_the_plots(self) -> None:
        # padj is NaN for independent-filtered genes; -log10(NaN) would be NaN
        # and matplotlib would silently drop the point, so the script fills 1.
        only_nan = self.results.copy()
        only_nan["padj"] = np.nan
        driver.create_plots(FakeStats(only_nan), self.root)
        self.assertTrue((self.root / "volcano_plot.png").is_file())


class EndToEndFitTests(unittest.TestCase):
    """One real fit, checked against a fold change that is true by construction."""

    @classmethod
    def setUpClass(cls) -> None:
        rng = np.random.default_rng(0)
        samples = [f"s{i}" for i in range(6)]
        genes = [f"G{j}" for j in range(40)]
        counts = rng.poisson(100, size=(6, 40))
        counts[3:, 0] *= 8  # G0 is exactly 8-fold higher in the treated group
        cls.counts = pd.DataFrame(counts, index=samples, columns=genes)
        cls.metadata = pd.DataFrame(
            {"condition": ["control"] * 3 + ["treated"] * 3}, index=samples
        )
        cls.dds, cls.inference = driver.run_deseq2(
            cls.counts, cls.metadata, "~condition", n_cpus=1
        )
        cls.stats = driver.run_statistical_tests(
            cls.dds,
            contrast=["condition", "treated", "control"],
            alpha=0.05,
            shrink_lfc=True,
            inference=cls.inference,
        )

    def test_the_inferred_coefficient_matches_the_real_design_matrix(self) -> None:
        # The whole point of infer_shrink_coeff: the composed name must exist
        # in the matrix PyDESeq2 built, not merely look plausible.
        self.assertIn(
            driver.infer_shrink_coeff(self.dds, ["condition", "treated", "control"]),
            list(self.dds.obsm["design_matrix"].columns),
        )

    def test_the_planted_eight_fold_change_is_recovered(self) -> None:
        # log2(8) == 3. Shrinkage pulls the estimate in slightly, so allow
        # half a log2 unit -- but the sign and magnitude must be right.
        lfc = self.stats.results_df.loc["G0", "log2FoldChange"]
        self.assertAlmostEqual(lfc, 3.0, delta=0.5)

    def test_the_planted_gene_is_the_only_significant_one(self) -> None:
        significant = self.stats.results_df[self.stats.results_df.padj < 0.05]
        self.assertEqual(list(significant.index), ["G0"])

    def test_every_tested_gene_gets_a_row(self) -> None:
        self.assertEqual(len(self.stats.results_df), 40)


if __name__ == "__main__":
    unittest.main()
