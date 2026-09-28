"""Tests for the statistical-analysis assumption checks.

These functions decide whether a parametric test is defensible, so the
assertions are constructed against data whose answer is known by construction:
a normal sample must pass Shapiro-Wilk, a lognormal one must fail; groups drawn
with equal variance must pass Levene, groups with a 10x spread must fail. A
check that quietly returns "assumption met" for skewed data is worse than no
check at all.

Most of these functions default to `plot=True` and draw with matplotlib, so the
suite forces the Agg backend and passes `plot=False` where the parameter exists
(`check_linearity` and `comprehensive_assumption_check` do not take one). These
are numeric assertions, not rendering ones.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "statistical-analysis"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

np = pytest.importorskip("numpy", reason="statistical-analysis needs numpy")
pd = pytest.importorskip("pandas", reason="statistical-analysis needs pandas")
pytest.importorskip("scipy", reason="statistical-analysis needs scipy")
matplotlib = pytest.importorskip("matplotlib", reason="assumption_checks imports matplotlib")
matplotlib.use("Agg")

import assumption_checks  # noqa: E402

RNG = np.random.default_rng(20260727)
NORMAL = RNG.normal(0, 1, 300)
SKEWED = RNG.lognormal(0, 1, 300)


class NormalityTests(unittest.TestCase):
    def test_a_normal_sample_is_reported_as_normal(self) -> None:
        result = assumption_checks.check_normality(NORMAL, plot=False)
        self.assertTrue(result["is_normal"])
        self.assertGreater(result["p_value"], 0.05)

    def test_a_lognormal_sample_is_reported_as_non_normal(self) -> None:
        result = assumption_checks.check_normality(SKEWED, plot=False)
        self.assertFalse(result["is_normal"])
        self.assertLess(result["p_value"], 0.05)

    def test_the_verdict_follows_the_supplied_alpha(self) -> None:
        # Same data, stricter threshold: the decision must move with alpha
        # rather than being hardcoded at .05.
        borderline = RNG.normal(0, 1, 300)
        lenient = assumption_checks.check_normality(borderline, alpha=1e-9, plot=False)
        self.assertTrue(lenient["is_normal"])
        strict = assumption_checks.check_normality(borderline, alpha=0.999, plot=False)
        self.assertFalse(strict["is_normal"])

    def test_the_result_carries_the_test_name_and_a_recommendation(self) -> None:
        normal = assumption_checks.check_normality(NORMAL, plot=False)
        self.assertEqual(normal["test"], "Shapiro-Wilk")
        self.assertEqual(normal["n"], len(NORMAL))
        self.assertIn("parametric", normal["recommendation"])

        skewed = assumption_checks.check_normality(SKEWED, plot=False)
        self.assertIn("non-parametric", skewed["recommendation"])

    def test_lists_and_series_are_accepted_as_well_as_arrays(self) -> None:
        for data in (list(NORMAL), pd.Series(NORMAL), NORMAL):
            with self.subTest(kind=type(data).__name__):
                self.assertTrue(
                    assumption_checks.check_normality(data, plot=False)["is_normal"]
                )


class PerGroupNormalityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            {
                "value": np.concatenate([RNG.normal(0, 1, 200), RNG.lognormal(0, 1, 200)]),
                "group": ["normal"] * 200 + ["skewed"] * 200,
            }
        )

    def test_each_group_gets_its_own_verdict(self) -> None:
        result = assumption_checks.check_normality_per_group(
            self.frame, "value", "group", plot=False
        )
        self.assertEqual(len(result), 2)
        verdicts = dict(zip(result["Group"], result["Normal"]))
        self.assertEqual(verdicts["normal"], "Yes")
        self.assertEqual(verdicts["skewed"], "No")

    def test_the_result_is_a_frame_with_one_row_and_an_n_per_group(self) -> None:
        result = assumption_checks.check_normality_per_group(
            self.frame, "value", "group", plot=False
        )
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(set(result["Group"]), {"normal", "skewed"})
        self.assertEqual(list(result["N"]), [200, 200])


class VarianceTests(unittest.TestCase):
    def _frame(self, spread: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "value": np.concatenate(
                    [RNG.normal(0, 1, 200), RNG.normal(0, spread, 200)]
                ),
                "group": ["a"] * 200 + ["b"] * 200,
            }
        )

    def test_equal_variances_pass_levene(self) -> None:
        result = assumption_checks.check_homogeneity_of_variance(
            self._frame(1.0), "value", "group", plot=False
        )
        self.assertTrue(result["is_homogeneous"])

    def test_a_tenfold_spread_difference_fails_levene(self) -> None:
        result = assumption_checks.check_homogeneity_of_variance(
            self._frame(10.0), "value", "group", plot=False
        )
        self.assertFalse(result["is_homogeneous"])
        self.assertLess(result["p_value"], 0.05)

    def test_more_than_two_groups_are_supported(self) -> None:
        frame = pd.DataFrame(
            {
                "value": np.concatenate([RNG.normal(0, 1, 100) for _ in range(3)]),
                "group": ["a"] * 100 + ["b"] * 100 + ["c"] * 100,
            }
        )
        result = assumption_checks.check_homogeneity_of_variance(
            frame, "value", "group", plot=False
        )
        self.assertTrue(result["is_homogeneous"])


class OutlierTests(unittest.TestCase):
    def test_the_iqr_method_finds_a_planted_extreme_value(self) -> None:
        data = np.concatenate([RNG.normal(0, 1, 200), [50.0]])
        result = assumption_checks.detect_outliers(data, method="iqr", plot=False)
        self.assertGreaterEqual(result["n_outliers"], 1)

    def test_the_zscore_method_finds_the_same_value(self) -> None:
        data = np.concatenate([RNG.normal(0, 1, 200), [50.0]])
        result = assumption_checks.detect_outliers(data, method="zscore", plot=False)
        self.assertGreaterEqual(result["n_outliers"], 1)

    def test_a_higher_threshold_flags_fewer_points(self) -> None:
        data = np.concatenate([RNG.normal(0, 1, 300), [6.0, 8.0, 12.0]])
        mild = assumption_checks.detect_outliers(
            data, method="iqr", threshold=1.5, plot=False
        )
        extreme = assumption_checks.detect_outliers(
            data, method="iqr", threshold=3.0, plot=False
        )
        self.assertGreaterEqual(mild["n_outliers"], extreme["n_outliers"])

    def test_clean_data_yields_no_extreme_outliers(self) -> None:
        result = assumption_checks.detect_outliers(
            RNG.normal(0, 1, 200), method="zscore", threshold=5.0, plot=False
        )
        self.assertEqual(result["n_outliers"], 0)

    def test_the_reported_percentage_matches_the_count(self) -> None:
        data = np.concatenate([RNG.normal(0, 1, 99), [50.0]])
        result = assumption_checks.detect_outliers(data, method="zscore", plot=False)
        self.assertAlmostEqual(
            result["pct_outliers"], 100 * result["n_outliers"] / len(data), places=6
        )


class LinearityTests(unittest.TestCase):
    def test_a_straight_line_relationship_is_reported_as_linear(self) -> None:
        x = np.linspace(0, 10, 200)
        y = 3 * x + RNG.normal(0, 0.1, 200)
        result = assumption_checks.check_linearity(x, y)
        self.assertGreater(abs(result["r"]), 0.99)

    def test_a_quadratic_relationship_is_distinguished_from_a_linear_one(self) -> None:
        x = np.linspace(-5, 5, 200)
        linear = assumption_checks.check_linearity(
            x, 2 * x + RNG.normal(0, 0.1, 200)
        )
        curved = assumption_checks.check_linearity(
            x, x**2 + RNG.normal(0, 0.1, 200)
        )
        self.assertGreater(abs(linear["r"]), abs(curved["r"]))


class ComprehensiveCheckTests(unittest.TestCase):
    def test_the_combined_check_reports_on_every_assumption(self) -> None:
        frame = pd.DataFrame(
            {
                "value": np.concatenate([RNG.normal(0, 1, 100), RNG.normal(1, 1, 100)]),
                "group": ["a"] * 100 + ["b"] * 100,
            }
        )
        result = assumption_checks.comprehensive_assumption_check(
            frame, "value", "group"
        )
        self.assertIsInstance(result, dict)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
