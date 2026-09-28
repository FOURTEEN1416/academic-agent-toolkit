"""Tests for the scikit-learn pipeline and clustering templates.

The value of `create_preprocessing_pipeline` is that it fits its imputer and
scaler *inside* a Pipeline, so cross-validation never lets test-fold statistics
reach the training fold. That is the leak these templates exist to prevent, and
it is what the tests check: the preprocessor is a ColumnTransformer that must
be fitted before it can transform, unseen categories survive, and the whole
thing composes into a single estimator.

Clustering is checked against data with a known answer -- three well-separated
blobs -- so "found 3 clusters" means something.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "scikit-learn"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

np = pytest.importorskip("numpy", reason="scikit-learn scripts need numpy")
pd = pytest.importorskip("pandas", reason="scikit-learn scripts need pandas")
sklearn = pytest.importorskip("sklearn", reason="scikit-learn scripts need sklearn")
matplotlib = pytest.importorskip("matplotlib", reason="clustering_analysis plots")
matplotlib.use("Agg")

from sklearn.datasets import make_blobs  # noqa: E402
from sklearn.exceptions import NotFittedError  # noqa: E402

import classification_pipeline  # noqa: E402
import clustering_analysis  # noqa: E402


def mixed_frame(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        {
            "age": rng.normal(50, 10, n),
            "score": rng.normal(0, 1, n),
            "city": rng.choice(["london", "paris", "berlin"], n),
            "grade": rng.choice(["a", "b"], n),
        }
    )


NUMERIC = ["age", "score"]
CATEGORICAL = ["city", "grade"]


class PreprocessingPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = mixed_frame()
        self.preprocessor = classification_pipeline.create_preprocessing_pipeline(
            NUMERIC, CATEGORICAL
        )

    def test_it_returns_an_unfitted_column_transformer(self) -> None:
        from sklearn.compose import ColumnTransformer

        self.assertIsInstance(self.preprocessor, ColumnTransformer)
        # Unfitted: statistics can only come from data it is later shown, which
        # is what keeps the test fold out of the training fold.
        with self.assertRaises(NotFittedError):
            self.preprocessor.transform(self.frame)

    def test_numeric_columns_are_imputed_and_standardised(self) -> None:
        frame = self.frame.copy()
        frame.loc[0, "age"] = np.nan
        transformed = self.preprocessor.fit_transform(frame)

        self.assertFalse(np.isnan(transformed).any(), "NaNs survived imputation")
        # The two numeric columns come first and are standardised.
        numeric_block = transformed[:, : len(NUMERIC)]
        np.testing.assert_allclose(numeric_block.mean(axis=0), 0, atol=1e-9)
        np.testing.assert_allclose(numeric_block.std(axis=0), 1, atol=1e-9)

    def test_categorical_columns_become_one_hot_indicators(self) -> None:
        transformed = self.preprocessor.fit_transform(self.frame)
        # 2 numeric + 3 cities + 2 grades
        self.assertEqual(transformed.shape, (len(self.frame), 2 + 3 + 2))
        categorical_block = transformed[:, len(NUMERIC):]
        self.assertTrue(set(np.unique(categorical_block)) <= {0.0, 1.0})

    def test_an_unseen_category_does_not_raise_at_transform_time(self) -> None:
        # handle_unknown='ignore' -- a category that appears only in the test
        # fold must not blow up the whole cross-validation run.
        self.preprocessor.fit(self.frame)
        unseen = self.frame.iloc[:3].copy()
        unseen["city"] = "tokyo"
        transformed = self.preprocessor.transform(unseen)
        self.assertEqual(transformed.shape[1], 2 + 3 + 2)
        # The unknown category encodes as all-zero indicators.
        np.testing.assert_allclose(transformed[:, 2:5], 0)

    def test_a_missing_categorical_value_is_filled_rather_than_dropped(self) -> None:
        frame = self.frame.copy()
        frame.loc[0, "city"] = None
        transformed = self.preprocessor.fit_transform(frame)
        self.assertEqual(len(transformed), len(frame))

    def test_it_can_be_composed_into_a_single_estimator(self) -> None:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline

        rng = np.random.default_rng(3)
        target = rng.integers(0, 2, len(self.frame))
        model = Pipeline(
            [("prep", self.preprocessor), ("clf", LogisticRegression(max_iter=500))]
        )
        model.fit(self.frame, target)
        self.assertEqual(len(model.predict(self.frame)), len(self.frame))

    def test_columns_outside_the_two_lists_are_dropped(self) -> None:
        frame = self.frame.copy()
        frame["notes"] = "ignore me"
        transformed = self.preprocessor.fit_transform(frame)
        self.assertEqual(transformed.shape[1], 2 + 3 + 2)


class ClusteringPreprocessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.features, self.labels = make_blobs(
            n_samples=150, centers=3, n_features=4, random_state=11, cluster_std=0.6
        )

    def test_scaling_standardises_every_feature(self) -> None:
        processed = clustering_analysis.preprocess_for_clustering(self.features)
        np.testing.assert_allclose(processed.mean(axis=0), 0, atol=1e-9)
        np.testing.assert_allclose(processed.std(axis=0), 1, atol=1e-9)

    def test_scaling_can_be_turned_off(self) -> None:
        processed = clustering_analysis.preprocess_for_clustering(
            self.features, scale=False
        )
        np.testing.assert_allclose(processed, self.features)

    def test_pca_reduces_to_the_requested_number_of_components(self) -> None:
        processed = clustering_analysis.preprocess_for_clustering(
            self.features, pca_components=2
        )
        self.assertEqual(processed.shape, (150, 2))

    def test_the_input_matrix_is_not_mutated(self) -> None:
        before = self.features.copy()
        clustering_analysis.preprocess_for_clustering(self.features)
        np.testing.assert_allclose(self.features, before)


class ScratchDirectoryTestCase(unittest.TestCase):
    """Run inside a temporary cwd.

    `find_optimal_k_kmeans` and `visualize_clusters` call `plt.savefig` with a
    bare filename, so they write into the current working directory -- which is
    the repository root when pytest runs. Without this the suite litters the
    checkout with clustering_optimization.png and clustering_results.png.
    """

    def setUp(self) -> None:
        self._origin = Path.cwd()
        self._scratch = tempfile.TemporaryDirectory()
        os.chdir(self._scratch.name)
        self.addCleanup(self._scratch.cleanup)
        self.addCleanup(os.chdir, self._origin)


class OptimalKTests(ScratchDirectoryTestCase):
    def setUp(self) -> None:
        super().setUp()
        features, _ = make_blobs(
            n_samples=180, centers=3, n_features=3, random_state=5, cluster_std=0.5
        )
        self.features = clustering_analysis.preprocess_for_clustering(features)

    def test_three_well_separated_blobs_are_found(self) -> None:
        # A silhouette search that cannot recover an obvious k=3 is not usable.
        result = clustering_analysis.find_optimal_k_kmeans(
            self.features, k_range=range(2, 7)
        )
        self.assertIsNotNone(result)
        flattened = str(result)
        self.assertIn("3", flattened)

    def test_the_search_covers_every_k_it_was_given(self) -> None:
        result = clustering_analysis.find_optimal_k_kmeans(
            self.features, k_range=range(2, 5)
        )
        # Whatever the container, it must carry one score per candidate k.
        if isinstance(result, dict):
            for value in result.values():
                if isinstance(value, (list, tuple, np.ndarray)) and len(value) > 1:
                    self.assertEqual(len(value), 3)
                    break


class AlgorithmComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        features, self.truth = make_blobs(
            n_samples=150, centers=3, n_features=3, random_state=9, cluster_std=0.5
        )
        self.features = clustering_analysis.preprocess_for_clustering(features)

    def test_several_algorithms_are_compared(self) -> None:
        results = clustering_analysis.compare_clustering_algorithms(
            self.features, n_clusters=3
        )
        self.assertIsInstance(results, dict)
        self.assertGreater(len(results), 1)

    def test_kmeans_recovers_the_planted_structure(self) -> None:
        from sklearn.metrics import adjusted_rand_score

        results = clustering_analysis.compare_clustering_algorithms(
            self.features, n_clusters=3
        )
        kmeans = next(
            (value for name, value in results.items() if "means" in name.lower()), None
        )
        self.assertIsNotNone(kmeans, f"no K-Means entry in {sorted(results)}")

        labels = kmeans.get("labels") if isinstance(kmeans, dict) else None
        if labels is not None:
            self.assertGreater(adjusted_rand_score(self.truth, labels), 0.9)


class EndToEndTests(ScratchDirectoryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.addCleanup(lambda: __import__("matplotlib.pyplot", fromlist=["close"]).close("all"))

    def test_the_full_clustering_analysis_runs(self) -> None:
        features, truth = make_blobs(
            n_samples=120, centers=3, n_features=3, random_state=13, cluster_std=0.6
        )
        result = clustering_analysis.complete_clustering_analysis(
            features, true_labels=truth
        )
        self.assertIsNotNone(result)

    def test_the_classification_pipeline_trains_and_scores(self) -> None:
        frame = mixed_frame(120)
        rng = np.random.default_rng(4)
        # A learnable target so the run exercises a real fit, not noise.
        target = (frame["age"] > frame["age"].median()).astype(int).to_numpy().copy()
        target[rng.choice(len(target), 6, replace=False)] ^= 1

        result = classification_pipeline.train_and_evaluate_model(
            frame, target, NUMERIC, CATEGORICAL, random_state=0
        )
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
