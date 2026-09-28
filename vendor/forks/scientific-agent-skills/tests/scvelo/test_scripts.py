"""Tests for the scVelo RNA velocity workflow.

`run_velocity_analysis` is one long pipeline, so the tests split it in two by
what can go wrong:

* The preprocessing and estimation steps run for real, on a synthetic AnnData of
  60 cells x 40 genes built here rather than downloaded. That is what caught the
  bug this suite now guards: scVelo 0.3 removed `n_top_genes` from
  `filter_and_normalize()`, so the shipped call raised TypeError on the first
  step of every run. Selecting 15 of 40 genes is checked by construction.
* The step ordering is checked with recording stubs in place of `scv.tl.*`,
  because which steps run is the script's own decision: the dynamical model must
  recover dynamics *before* estimating velocity, latent time and the driver-gene
  heatmap belong to that mode alone, and gene ranking is conditional on the
  grouping column existing. The stubs also fix the confidence values, so the
  printed summary statistics are checked against hand-computed numbers.

`mode="deterministic"` drives the real run: with scvelo 0.3.4, `mode="stochastic"`
fails inside the generalized least-squares solver on NumPy >= 2 and the dynamical
model fails inside `pandas.unique` on pandas >= 3, both upstream. The plotting
calls are stubbed for the same reason -- `scv.pl.scatter` on a numeric `.obs`
column raises under pandas 3 -- and stubbing them lets the tests assert which
figures the workflow asks for, which is the part the skill owns.

`load_from_loom` is not covered: it needs a velocyto `.loom` file plus loompy,
and its second branch needs leidenalg, none of which this environment carries.
Neither the `--help` nor the demo contract applies -- the script parses no
arguments, and its `__main__` block downloads the pancreas dataset.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "scvelo"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

matplotlib = pytest.importorskip("matplotlib", reason="scvelo workflow plots")
matplotlib.use("Agg")  # never open a window, even if a real plot slips through

np = pytest.importorskip("numpy", reason="scvelo workflow needs numpy")
pytest.importorskip("scvelo", reason="scvelo skill needs scvelo")
pytest.importorskip("scanpy", reason="scvelo workflow needs scanpy")

import anndata as ad  # noqa: E402
import scvelo as scv  # noqa: E402

import rna_velocity_workflow as workflow  # noqa: E402

N_OBS = 60
N_VARS = 40
#: Cells with a velocity confidence above this are counted in the summary.
HIGH_CONFIDENCE = 0.7


def synthetic(n_obs: int = N_OBS, n_vars: int = N_VARS, seed: int = 0):
    """A minimal AnnData shaped like velocyto output: counts in both layers.

    Counts are drawn high enough (Poisson 8 spliced, 4 unspliced) that no gene
    is dropped by the workflow's `min_shared_counts=20` filter, so the gene
    count after preprocessing is decided by `n_top_genes` alone.
    """
    rng = np.random.default_rng(seed)
    spliced = rng.poisson(8, size=(n_obs, n_vars)).astype("float32")
    unspliced = rng.poisson(4, size=(n_obs, n_vars)).astype("float32")

    adata = ad.AnnData(spliced.copy())
    adata.layers["spliced"] = spliced
    adata.layers["unspliced"] = unspliced
    adata.obs_names = [f"cell{index}" for index in range(n_obs)]
    adata.var_names = [f"Gene{index}" for index in range(n_vars)]
    half = n_obs // 2
    adata.obs["clusters"] = (["alpha"] * half + ["beta"] * (n_obs - half))
    adata.obs["clusters"] = adata.obs["clusters"].astype("category")
    adata.obsm["X_umap"] = rng.normal(size=(n_obs, 2))
    return adata


class FigureRecorder:
    """Replacement for the `scv.pl` functions: records instead of rendering."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def stub(self, name: str):
        def record(adata=None, *args, **kwargs):
            self.calls.append((name, kwargs))

        return record

    def install(self, test: unittest.TestCase) -> None:
        for name in (
            "velocity_embedding_stream",
            "velocity_embedding",
            "scatter",
            "heatmap",
        ):
            patcher = mock.patch.object(scv.pl, name, self.stub(name))
            patcher.start()
            test.addCleanup(patcher.stop)

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    @property
    def saved(self) -> list[str]:
        return [kwargs["save"] for _, kwargs in self.calls if "save" in kwargs]

    def kwargs_for(self, name: str) -> dict:
        for recorded, kwargs in self.calls:
            if recorded == name:
                return kwargs
        raise AssertionError(f"{name} was never called")


class LayerRequirementTests(unittest.TestCase):
    """Velocity is impossible without both layers, so the guard fires early."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.output = str(Path(self._temporary.name) / "out")

    def run_on(self, adata):
        with contextlib.redirect_stdout(io.StringIO()):
            workflow.run_velocity_analysis(adata, output_dir=self.output)

    def test_a_missing_spliced_layer_is_refused_before_any_work(self) -> None:
        adata = synthetic()
        del adata.layers["spliced"]
        with self.assertRaisesRegex(AssertionError, "spliced"):
            self.run_on(adata)

    def test_a_missing_unspliced_layer_is_refused(self) -> None:
        adata = synthetic()
        del adata.layers["unspliced"]
        with self.assertRaisesRegex(AssertionError, "unspliced"):
            self.run_on(adata)

    def test_the_message_names_the_tool_that_produces_the_layers(self) -> None:
        adata = synthetic()
        del adata.layers["spliced"]
        with self.assertRaisesRegex(AssertionError, "velocyto"):
            self.run_on(adata)


class VelocityRunTests(unittest.TestCase):
    """One real run of the pipeline, inspected from several angles."""

    N_TOP_GENES = 15

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._temporary.cleanup)
        # A nested path the workflow has to create itself.
        cls.output = Path(cls._temporary.name) / "results" / "velocity"

        cls.figures = FigureRecorder()
        cls._patchers = [
            mock.patch.object(scv.pl, name, cls.figures.stub(name))
            for name in (
                "velocity_embedding_stream",
                "velocity_embedding",
                "scatter",
                "heatmap",
            )
        ]
        for patcher in cls._patchers:
            patcher.start()
        cls.addClassCleanup(
            lambda: [patcher.stop() for patcher in cls._patchers]
        )

        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            cls.input = synthetic()
            cls.adata = workflow.run_velocity_analysis(
                cls.input,
                groupby="clusters",
                n_top_genes=cls.N_TOP_GENES,
                n_neighbors=15,
                mode="deterministic",
                output_dir=str(cls.output),
            )
        cls.printed = stream.getvalue()

    def test_the_input_object_is_annotated_in_place(self) -> None:
        self.assertIs(self.adata, self.input)

    def test_the_gene_set_is_narrowed_to_the_requested_top_genes(self) -> None:
        # 40 genes in, 15 requested: the count is decided by the HVG step, which
        # is exactly what the scVelo 0.3 preprocessing change moved to Scanpy.
        self.assertEqual(self.adata.n_vars, self.N_TOP_GENES)
        self.assertEqual(self.adata.n_obs, N_OBS)

    def test_the_moments_and_velocity_layers_are_added(self) -> None:
        for layer in ("Ms", "Mu", "velocity"):
            with self.subTest(layer=layer):
                self.assertIn(layer, self.adata.layers)

    def test_at_least_one_gene_has_a_usable_velocity(self) -> None:
        # Genes scVelo rejects are left as NaN; an all-NaN layer would mean the
        # run produced nothing to plot or rank.
        velocity = np.asarray(self.adata.layers["velocity"])
        self.assertTrue(np.isfinite(velocity).any())

    def test_the_downstream_per_cell_annotations_are_present(self) -> None:
        for column in ("velocity_confidence", "velocity_pseudotime", "velocity_length"):
            with self.subTest(column=column):
                self.assertIn(column, self.adata.obs)

    def test_the_confidences_stay_inside_their_definition(self) -> None:
        # velocity_confidence is a cosine correlation, so it cannot leave [-1, 1].
        confidence = self.adata.obs["velocity_confidence"].to_numpy()
        self.assertGreaterEqual(np.nanmin(confidence), -1.0)
        self.assertLessEqual(np.nanmax(confidence), 1.0)

    def test_driver_genes_are_ranked_because_the_grouping_column_exists(self) -> None:
        self.assertIn("rank_velocity_genes", self.adata.uns)

    def test_a_non_dynamical_run_skips_the_dynamical_only_results(self) -> None:
        self.assertNotIn("latent_time", self.adata.obs)
        self.assertNotIn("fit_likelihood", self.adata.var)

    def test_the_annotated_object_round_trips_through_the_saved_h5ad(self) -> None:
        saved = self.output / "adata_velocity.h5ad"
        self.assertTrue(saved.is_file())
        reloaded = ad.read_h5ad(saved)
        self.assertEqual(reloaded.shape, self.adata.shape)
        self.assertIn("velocity", reloaded.layers)
        self.assertIn("velocity_pseudotime", reloaded.obs)

    def test_the_four_always_on_figures_are_requested(self) -> None:
        # Stream plot, arrow plot, pseudotime, and the speed/coherence pair.
        self.assertEqual(
            self.figures.names,
            [
                "velocity_embedding_stream",
                "velocity_embedding",
                "scatter",
                "scatter",
            ],
        )

    def test_the_embedding_figures_use_the_umap_basis_and_the_grouping(self) -> None:
        stream = self.figures.kwargs_for("velocity_embedding_stream")
        self.assertEqual(stream["basis"], "umap")
        self.assertEqual(stream["color"], "clusters")

    def test_every_figure_is_written_inside_the_output_directory(self) -> None:
        self.assertEqual(len(self.figures.saved), 4)
        for path in self.figures.saved:
            with self.subTest(path=path):
                self.assertTrue(path.startswith(str(self.output)))

    def test_the_summary_reports_the_cell_and_gene_counts_it_finished_with(self) -> None:
        self.assertIn(f"Cells: {N_OBS}", self.printed)
        self.assertIn(f"Velocity genes: {self.N_TOP_GENES}", self.printed)
        self.assertIn("Velocity model: deterministic", self.printed)


class StepOrderTests(unittest.TestCase):
    """Which scVelo steps run, in what order, is the script's own logic."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.output = Path(self._temporary.name) / "out"

        self.figures = FigureRecorder()
        self.figures.install(self)
        self.steps: list[str] = []

        def record(name, effect=None):
            def stub(adata, *args, **kwargs):
                self.steps.append(name)
                if effect is not None:
                    effect(adata)

            return stub

        def add_velocity(adata):
            adata.layers["velocity"] = np.zeros(adata.shape, dtype="float32")

        def add_confidence(adata):
            # Half the cells at 0.9 and half at 0.5: mean 0.700, and exactly
            # half above the 0.7 high-confidence cut used by the summary.
            half = adata.n_obs // 2
            adata.obs["velocity_confidence"] = [0.9] * half + [0.5] * (
                adata.n_obs - half
            )
            adata.obs["velocity_length"] = np.ones(adata.n_obs)

        def add_fits(adata):
            adata.var["fit_likelihood"] = np.linspace(0.05, 0.95, adata.n_vars)

        def add_pseudotime(adata):
            adata.obs["velocity_pseudotime"] = np.linspace(0, 1, adata.n_obs)

        def add_latent_time(adata):
            adata.obs["latent_time"] = np.linspace(0, 1, adata.n_obs)

        for name, effect in (
            ("recover_dynamics", add_fits),
            ("velocity", add_velocity),
            ("velocity_graph", None),
            ("velocity_confidence", add_confidence),
            ("velocity_pseudotime", add_pseudotime),
            ("latent_time", add_latent_time),
            ("rank_velocity_genes", None),
        ):
            patcher = mock.patch.object(scv.tl, name, record(name, effect))
            patcher.start()
            self.addCleanup(patcher.stop)

    def analyse(self, **kwargs) -> str:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            workflow.run_velocity_analysis(
                synthetic(),
                n_top_genes=15,
                n_neighbors=15,
                output_dir=str(self.output),
                **kwargs,
            )
        return stream.getvalue()

    def test_the_dynamical_model_recovers_dynamics_before_estimating(self) -> None:
        # Reversed, `velocity(mode="dynamical")` has no fitted parameters to use.
        self.analyse(groupby="clusters", mode="dynamical")
        self.assertLess(
            self.steps.index("recover_dynamics"), self.steps.index("velocity")
        )

    def test_the_dynamical_model_adds_latent_time_and_the_driver_heatmap(self) -> None:
        self.analyse(groupby="clusters", mode="dynamical")
        self.assertIn("latent_time", self.steps)
        self.assertIn("heatmap", self.figures.names)
        self.assertTrue(
            any("latent_time" in path for path in self.figures.saved),
            "the latent-time figure was not requested",
        )

    def test_a_stochastic_run_skips_the_dynamical_only_steps(self) -> None:
        self.analyse(groupby="clusters", mode="stochastic")
        # Fitting dynamics is the expensive part; the fast mode must not pay it.
        self.assertNotIn("recover_dynamics", self.steps)
        self.assertNotIn("latent_time", self.steps)
        self.assertNotIn("heatmap", self.figures.names)

    def test_gene_ranking_needs_the_grouping_column(self) -> None:
        self.analyse(groupby="clusters", mode="stochastic")
        self.assertIn("rank_velocity_genes", self.steps)

    def test_an_absent_grouping_column_skips_ranking_instead_of_failing(self) -> None:
        self.analyse(groupby="cell_type_not_present", mode="stochastic")
        self.assertNotIn("rank_velocity_genes", self.steps)

    def test_the_summary_statistics_are_computed_over_the_confidences(self) -> None:
        printed = self.analyse(groupby="clusters", mode="stochastic")
        # 30 cells at 0.9 and 30 at 0.5: mean 0.700, half above 0.7.
        self.assertIn("Mean velocity confidence: 0.700", printed)
        self.assertIn(
            f"High-confidence cells (>{HIGH_CONFIDENCE}): {N_OBS // 2} (50.0%)",
            printed,
        )

    def test_the_output_directory_is_created_before_anything_is_written(self) -> None:
        self.assertFalse(self.output.exists())
        self.analyse(groupby="clusters", mode="stochastic")
        self.assertTrue((self.output / "adata_velocity.h5ad").is_file())


class ModeValidationTests(unittest.TestCase):
    def test_an_unknown_mode_is_rejected_by_scvelo(self) -> None:
        # The script forwards `mode` verbatim, so a typo must surface as an
        # error naming the allowed estimators rather than as silent nonsense.
        adata = synthetic()
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, "deterministic"):
                    workflow.run_velocity_analysis(
                        adata,
                        groupby="clusters",
                        n_top_genes=15,
                        n_neighbors=15,
                        mode="stochastik",
                        output_dir=directory,
                    )


if __name__ == "__main__":
    unittest.main()
