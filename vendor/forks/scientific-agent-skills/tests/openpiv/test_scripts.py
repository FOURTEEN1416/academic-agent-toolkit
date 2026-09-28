"""Tests for the OpenPIV processing and post-processing scripts.

A PIV pipeline can be wired up wrongly and still produce a plausible-looking
vector field, so the substantive tests here are built on fields whose answer is
known before the code runs. `run_openpiv` is driven with synthetic particle
image pairs displaced by an exact integer number of pixels, and the recovered
vectors have to reproduce that displacement -- in magnitude, in direction, and
in the sign convention `transform_coordinates` imposes -- plus the documented
`dt` and pixels-per-unit scaling. `PIVAnalyzer`'s derivatives are checked against
analytic flows (solid-body rotation, pure shear, uniform extension) whose
vorticity and strain rate are textbook constants, which is also what pins the
axis orientation: the saved `y` decreases with the row index, so an unsigned
`np.gradient` would flip `du/dy` and report zero vorticity for a rotating flow.

The window-geometry guards are proved in both directions -- a legal combination
runs, an illegal one is refused before any image is read.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "openpiv"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

np = pytest.importorskip("numpy", reason="openpiv skill needs numpy")
pytest.importorskip("openpiv", reason="openpiv skill needs openpiv")
matplotlib = pytest.importorskip("matplotlib", reason="openpiv skill needs matplotlib")
# runner.py selects Agg itself; set it here too so importing analyze's plotting
# path in this process can never try to open a window.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

import analyze  # noqa: E402
import run_example  # noqa: E402
import runner  # noqa: E402

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

#: Synthetic image geometry. 160 px with a 32 px window and 16 px overlap steps
#: by 16, giving (160 - 32) / 16 + 1 = 9 vectors per axis.
IMAGE_SIZE = 160
WINDOW = 32
OVERLAP = 16
EXPECTED_GRID = 9


def particle_image(rows: np.ndarray, columns: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """A uint8 frame of 3x3 particles at (rows + dy, columns + dx)."""
    frame = np.zeros((IMAGE_SIZE, IMAGE_SIZE), dtype=np.float64)
    for row, column in zip(rows + dy, columns + dx):
        frame[row - 1 : row + 2, column - 1 : column + 2] += 200.0
    return np.clip(frame, 0, 255).astype(np.uint8)


class DisplacementRecoveryTests(unittest.TestCase):
    """Whole-pipeline correctness: a known shift must come back out."""

    @classmethod
    def setUpClass(cls) -> None:
        # A fixed seed keeps the particle pattern -- and therefore the
        # correlation quality -- identical from run to run.
        generator = np.random.default_rng(20260727)
        margin = 12
        cls.rows = generator.integers(margin, IMAGE_SIZE - margin, 900)
        cls.columns = generator.integers(margin, IMAGE_SIZE - margin, 900)

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.addCleanup(plt.close, "all")
        self.root = Path(self._temporary.name)

    def pair(self, dy: int, dx: int) -> tuple[Path, Path]:
        import imageio.v3 as iio

        first = self.root / "a.png"
        second = self.root / "b.png"
        iio.imwrite(first, particle_image(self.rows, self.columns, 0, 0))
        iio.imwrite(second, particle_image(self.rows, self.columns, dy, dx))
        return first, second

    def field(self, dy: int, dx: int, **overrides) -> dict:
        first, second = self.pair(dy, dx)
        settings = dict(
            output_dir=str(self.root / "out"),
            window_size=WINDOW,
            overlap=OVERLAP,
            search_area=WINDOW,
            dt=1.0,
            scaling_factor=1.0,
            threshold=1.05,
        )
        settings.update(overrides)
        output = runner.run_openpiv(str(first), str(second), **settings)
        with np.load(output / "params.npz") as data:
            return {key: data[key] for key in ("x", "y", "u", "v", "flags")}

    def test_a_rightward_shift_is_recovered_as_a_positive_u(self) -> None:
        # Particles move exactly +4 px in x, so with dt = 1 s and 1 px per unit
        # every valid vector must read u = 4 and v = 0.
        field = self.field(dy=0, dx=4)
        valid = ~field["flags"]
        self.assertTrue(valid.any(), "the correlation flagged every vector as spurious")
        np.testing.assert_allclose(field["u"][valid], 4.0, atol=0.3)
        np.testing.assert_allclose(field["v"][valid], 0.0, atol=0.3)

    def test_a_leftward_shift_is_recovered_as_a_negative_u(self) -> None:
        field = self.field(dy=0, dx=-4)
        valid = ~field["flags"]
        np.testing.assert_allclose(field["u"][valid], -4.0, atol=0.3)

    def test_a_downward_shift_is_recovered_as_a_negative_v(self) -> None:
        # transform_coordinates() puts the field in a right-handed y-up frame,
        # so motion towards higher row indices -- down the image -- is negative
        # v. Getting this backwards mirrors every reported flow.
        field = self.field(dy=5, dx=0)
        valid = ~field["flags"]
        np.testing.assert_allclose(field["v"][valid], -5.0, atol=0.3)
        np.testing.assert_allclose(field["u"][valid], 0.0, atol=0.3)

    def test_identical_frames_recover_no_motion(self) -> None:
        field = self.field(dy=0, dx=0)
        valid = ~field["flags"]
        np.testing.assert_allclose(field["u"][valid], 0.0, atol=0.3)
        np.testing.assert_allclose(field["v"][valid], 0.0, atol=0.3)

    def test_the_grid_geometry_follows_the_window_and_overlap(self) -> None:
        field = self.field(dy=0, dx=4)
        self.assertEqual(field["u"].shape, (EXPECTED_GRID, EXPECTED_GRID))
        # First window centre is at window_size / 2, then one step of
        # window_size - overlap per vector.
        self.assertAlmostEqual(float(field["x"][0, 0]), WINDOW / 2)
        self.assertAlmostEqual(
            float(field["x"][0, -1]), WINDOW / 2 + (EXPECTED_GRID - 1) * OVERLAP
        )
        # y is the flipped axis: it runs downwards through the array.
        self.assertGreater(float(field["y"][0, 0]), float(field["y"][-1, 0]))

    def test_dt_converts_the_displacement_into_a_velocity(self) -> None:
        # 4 px over 0.5 s is 8 px/s.
        field = self.field(dy=0, dx=4, dt=0.5)
        np.testing.assert_allclose(field["u"][~field["flags"]], 8.0, atol=0.6)

    def test_the_scaling_factor_is_pixels_per_physical_unit(self) -> None:
        # 4 px at 2 px/mm is 2 mm/s, so u must be divided by the factor, not
        # multiplied by it.
        field = self.field(dy=0, dx=4, scaling_factor=2.0)
        np.testing.assert_allclose(field["u"][~field["flags"]], 2.0, atol=0.2)
        # The coordinates are rescaled too: the first centre is 16 px = 8 mm.
        self.assertAlmostEqual(float(field["x"][0, 0]), WINDOW / 2 / 2.0)

    def test_a_larger_search_area_still_recovers_the_shift(self) -> None:
        # search_area > window_size switches the correlation to "linear"; the
        # answer must not change.
        field = self.field(dy=0, dx=4, search_area=WINDOW + 6)
        np.testing.assert_allclose(field["u"][~field["flags"]], 4.0, atol=0.4)

    def test_every_documented_output_file_is_written(self) -> None:
        first, second = self.pair(0, 4)
        output = runner.run_openpiv(
            str(first),
            str(second),
            output_dir=str(self.root / "files"),
            window_size=WINDOW,
            overlap=OVERLAP,
            search_area=WINDOW,
            dt=1.0,
            scaling_factor=1.0,
        )
        for name in ("vectors.txt", "params.npz", "vector_field.png"):
            with self.subTest(name=name):
                self.assertTrue((output / name).is_file())

    def test_dropping_invalid_vectors_leaves_holes_where_they_were_flagged(self) -> None:
        # By default a flagged vector is replaced by the local mean, so the
        # field has no holes; --drop_invalid must NaN out exactly the flagged
        # positions and leave every other vector untouched.
        kept = self.field(dy=0, dx=4, output_dir=str(self.root / "kept"))
        flags = kept["flags"]
        self.assertTrue(flags.any(), "nothing was flagged, so the branch is untested")
        self.assertFalse(np.isnan(kept["u"]).any())

        dropped = self.field(
            dy=0, dx=4, output_dir=str(self.root / "dropped"), drop_invalid=True
        )
        np.testing.assert_array_equal(np.isnan(dropped["u"]), flags)
        np.testing.assert_array_equal(np.isnan(dropped["v"]), flags)
        np.testing.assert_allclose(dropped["u"][~flags], kept["u"][~flags])

    def test_a_uniform_translation_has_no_vorticity(self) -> None:
        # End to end: rigid translation carries no rotation, so the derived
        # vorticity must stay at the noise level rather than pick up a bias.
        first, second = self.pair(0, 4)
        output = runner.run_openpiv(
            str(first),
            str(second),
            output_dir=str(self.root / "vort"),
            window_size=WINDOW,
            overlap=OVERLAP,
            search_area=WINDOW,
            dt=1.0,
            scaling_factor=1.0,
        )
        analyzer = analyze.PIVAnalyzer(output / "params.npz")
        self.assertLess(float(np.nanmax(np.abs(analyzer.compute_vorticity()))), 0.05)


class WindowGeometryTests(unittest.TestCase):
    """The window/overlap/search-area guards, before any image is touched."""

    def test_a_search_area_smaller_than_the_window_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, r"search_area \(16\) must be >="):
            runner.run_openpiv("a.png", "b.png", window_size=32, search_area=16)

    def test_an_overlap_at_or_above_the_window_is_refused(self) -> None:
        # overlap == window_size would give a zero step and an infinite grid.
        for overlap in (32, 40):
            with self.subTest(overlap=overlap):
                with self.assertRaisesRegex(ValueError, "must be <"):
                    runner.run_openpiv(
                        "a.png", "b.png", window_size=32, overlap=overlap, search_area=32
                    )

    def test_the_guards_fire_before_the_images_are_opened(self) -> None:
        # Both paths below do not exist; a FileNotFoundError instead of a
        # ValueError would mean the geometry check runs too late to be useful.
        with self.assertRaises(ValueError):
            runner.run_openpiv("no-such-a.png", "no-such-b.png", search_area=1)

    def test_the_shipped_defaults_satisfy_their_own_guards(self) -> None:
        # window 32 / overlap 12 / search 38 is a legal combination, so the
        # documented defaults must reach the image read rather than be refused.
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                runner.run_openpiv(
                    "no-such-a.png", "no-such-b.png", output_dir=directory
                )


class CliArgumentTests(unittest.TestCase):
    def test_exactly_two_images_are_required(self) -> None:
        for images in ([], ["one.png"], ["a.png", "b.png", "c.png"]):
            with self.subTest(images=images):
                argv = ["runner.py"]
                for image in images:
                    argv += ["--image", image]
                original = sys.argv
                sys.argv = argv
                try:
                    with self.assertRaises(SystemExit) as raised:
                        runner.main()
                finally:
                    sys.argv = original
                self.assertEqual(raised.exception.code, 2)


class AnalyzerFixtureCase(unittest.TestCase):
    """Base class only: builds a `params.npz` from arrays and loads it back.

    Ships no tests of its own, so pytest collects it once per real subclass.
    """

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self._written = 0

    def analyzer(
        self,
        u: np.ndarray,
        v: np.ndarray,
        x: np.ndarray,
        y: np.ndarray,
        flags: np.ndarray | None = None,
    ) -> analyze.PIVAnalyzer:
        self._written += 1
        path = self.root / f"params{self._written}.npz"
        np.savez(
            path,
            x=x,
            y=y,
            u=u,
            v=v,
            flags=np.zeros(u.shape, dtype=bool) if flags is None else flags,
        )
        return analyze.PIVAnalyzer(path)


class GridSpacingTests(AnalyzerFixtureCase):
    def test_the_spacing_is_read_off_the_coordinates_not_assumed(self) -> None:
        x = np.tile(np.arange(5) * 2.5, (4, 1))
        y = np.tile((np.arange(4) * 1.5)[:, None], (1, 5))
        analyzer = self.analyzer(np.zeros((4, 5)), np.zeros((4, 5)), x, y)
        self.assertEqual(analyzer.grid_spacing, (2.5, 1.5))

    def test_the_spacing_is_positive_even_when_a_coordinate_runs_backwards(self) -> None:
        # runner.py writes y decreasing; the reported spacing is a magnitude.
        x = np.tile(np.arange(5) * 2.0, (4, 1))
        y = np.tile((np.arange(4)[::-1] * 3.0)[:, None], (1, 5))
        analyzer = self.analyzer(np.zeros((4, 5)), np.zeros((4, 5)), x, y)
        self.assertEqual(analyzer.grid_spacing, (2.0, 3.0))
        self.assertEqual(analyzer.axis_signs, (1.0, -1.0))

    def test_a_degenerate_axis_falls_back_to_one(self) -> None:
        # A single-column field has no spacing to infer; 1.0 keeps the
        # derivative per grid cell instead of dividing by zero.
        x = np.zeros((3, 1))
        y = np.array([[0.0], [2.0], [4.0]])
        analyzer = self.analyzer(np.zeros((3, 1)), np.zeros((3, 1)), x, y)
        self.assertEqual(analyzer.grid_spacing, (1.0, 2.0))
        self.assertEqual(analyzer.axis_signs, (1.0, 1.0))


class AnalyticFlowTests(AnalyzerFixtureCase):
    """Vorticity and strain rate against flows with closed-form answers."""

    SIDE = 7
    STEP = 2.0

    def grid(self, descending_y: bool) -> tuple[np.ndarray, np.ndarray]:
        indices = np.arange(self.SIDE)
        x = np.tile(indices * self.STEP, (self.SIDE, 1))
        rows = indices[::-1] if descending_y else indices
        y = np.tile((rows * self.STEP)[:, None], (1, self.SIDE))
        return x, y

    def test_solid_body_rotation_has_vorticity_twice_the_rate(self) -> None:
        # u = -omega*y, v = omega*x is rigid rotation at omega; its vorticity
        # dv/dx - du/dy is exactly 2*omega everywhere, including at the edges,
        # because the field is linear and np.gradient is exact for linear data.
        omega = 0.5
        for descending_y in (True, False):
            with self.subTest(descending_y=descending_y):
                x, y = self.grid(descending_y)
                analyzer = self.analyzer(-omega * y, omega * x, x, y)
                np.testing.assert_allclose(
                    analyzer.compute_vorticity(), 2 * omega, atol=1e-12
                )

    def test_rotation_carries_no_strain(self) -> None:
        omega = 0.5
        x, y = self.grid(descending_y=True)
        analyzer = self.analyzer(-omega * y, omega * x, x, y)
        exx, eyy, exy = analyzer.compute_strain()
        for name, component in (("exx", exx), ("eyy", eyy), ("exy", exy)):
            with self.subTest(component=name):
                np.testing.assert_allclose(component, 0.0, atol=1e-12)

    def test_pure_shear_splits_between_vorticity_and_shear_strain(self) -> None:
        # u = k*y, v = 0: dv/dx - du/dy = -k, and exy = 0.5*(du/dy + dv/dx) = k/2.
        rate = 0.4
        x, y = self.grid(descending_y=True)
        analyzer = self.analyzer(rate * y, np.zeros_like(y), x, y)
        np.testing.assert_allclose(analyzer.compute_vorticity(), -rate, atol=1e-12)
        exx, eyy, exy = analyzer.compute_strain()
        np.testing.assert_allclose(exy, rate / 2, atol=1e-12)
        np.testing.assert_allclose(exx, 0.0, atol=1e-12)
        np.testing.assert_allclose(eyy, 0.0, atol=1e-12)

    def test_incompressible_extension_gives_opposite_normal_strains(self) -> None:
        # u = a*x, v = -a*y is divergence free, so exx = a and eyy = -a.
        rate = 0.3
        x, y = self.grid(descending_y=True)
        analyzer = self.analyzer(rate * x, -rate * y, x, y)
        exx, eyy, exy = analyzer.compute_strain()
        np.testing.assert_allclose(exx, rate, atol=1e-12)
        np.testing.assert_allclose(eyy, -rate, atol=1e-12)
        np.testing.assert_allclose(exy, 0.0, atol=1e-12)
        np.testing.assert_allclose(exx + eyy, 0.0, atol=1e-12)

    def test_a_supplied_spacing_overrides_the_inferred_one(self) -> None:
        # The gradients are per unit length, so halving the assumed spacing
        # doubles every derivative.
        omega = 0.5
        x, y = self.grid(descending_y=True)
        analyzer = self.analyzer(-omega * y, omega * x, x, y)
        np.testing.assert_allclose(
            analyzer.compute_vorticity(dx=self.STEP / 2, dy=self.STEP / 2),
            4 * omega,
            atol=1e-12,
        )

    def test_a_uniform_flow_has_neither_vorticity_nor_strain(self) -> None:
        x, y = self.grid(descending_y=True)
        analyzer = self.analyzer(np.full_like(x, 3.0), np.full_like(x, -2.0), x, y)
        np.testing.assert_allclose(analyzer.compute_vorticity(), 0.0, atol=1e-12)
        for component in analyzer.compute_strain():
            np.testing.assert_allclose(component, 0.0, atol=1e-12)


class VelocityMagnitudeTests(AnalyzerFixtureCase):
    def test_the_magnitude_is_the_euclidean_norm(self) -> None:
        x = np.tile(np.arange(2) * 1.0, (1, 1))
        u = np.array([[3.0, -3.0]])
        v = np.array([[4.0, 4.0]])
        analyzer = self.analyzer(u, v, x, np.zeros_like(x))
        np.testing.assert_allclose(analyzer.get_velocity_magnitude(), [[5.0, 5.0]])


class StatisticsTests(AnalyzerFixtureCase):
    def field(self, u: np.ndarray, v: np.ndarray) -> analyze.PIVAnalyzer:
        x = np.tile(np.arange(u.shape[1]) * 1.0, (u.shape[0], 1))
        y = np.tile((np.arange(u.shape[0]) * 1.0)[:, None], (1, u.shape[1]))
        return self.analyzer(u, v, x, y)

    def test_a_uniform_field_has_zero_fluctuation_and_zero_energy(self) -> None:
        stats = self.field(np.full((4, 4), 2.0), np.full((4, 4), -1.0)).compute_statistics()
        self.assertAlmostEqual(stats["u_mean"], 2.0)
        self.assertAlmostEqual(stats["v_mean"], -1.0)
        self.assertAlmostEqual(stats["rms_u"], 0.0)
        self.assertAlmostEqual(stats["rms_v"], 0.0)
        self.assertAlmostEqual(stats["tke"], 0.0)

    def test_the_rms_is_the_population_standard_deviation(self) -> None:
        # [-2, -2, 2, 2] has mean 0 and population variance 4, so sd = 2 exactly
        # -- the sample (n-1) convention would give 2.309 instead.
        u = np.array([[-2.0, -2.0, 2.0, 2.0]])
        stats = self.field(u, np.zeros_like(u)).compute_statistics()
        self.assertAlmostEqual(stats["u_mean"], 0.0)
        self.assertAlmostEqual(stats["rms_u"], 2.0)
        # tke = 0.5 * (rms_u^2 + rms_v^2) = 0.5 * 4 = 2.
        self.assertAlmostEqual(stats["tke"], 2.0)

    def test_subtracting_the_mean_makes_the_rms_offset_invariant(self) -> None:
        # The fluctuation statistics describe the spread, so adding a uniform
        # 100 to every vector must move only the means.
        u = np.array([[-2.0, -2.0, 2.0, 2.0]])
        base = self.field(u, np.zeros_like(u)).compute_statistics()
        shifted = self.field(u + 100.0, np.zeros_like(u)).compute_statistics()
        self.assertAlmostEqual(shifted["u_mean"], base["u_mean"] + 100.0)
        self.assertAlmostEqual(shifted["rms_u"], base["rms_u"])
        self.assertAlmostEqual(shifted["tke"], base["tke"])

    def test_holes_left_by_drop_invalid_are_ignored_not_propagated(self) -> None:
        # --drop_invalid writes NaN where a vector was rejected; the statistics
        # must describe the surviving vectors instead of returning NaN.
        u = np.array([[2.0, np.nan, 2.0, np.nan]])
        stats = self.field(u, np.zeros_like(u)).compute_statistics()
        self.assertAlmostEqual(stats["u_mean"], 2.0)
        self.assertAlmostEqual(stats["rms_u"], 0.0)


class FlagsTests(AnalyzerFixtureCase):
    def test_flags_are_loaded_as_a_boolean_mask(self) -> None:
        # runner.py saves them as bool, but a float or int array from an older
        # run must still index correctly rather than be read as positions.
        u = np.arange(4.0).reshape(1, 4)
        x = np.tile(np.arange(4) * 1.0, (1, 1))
        analyzer = self.analyzer(
            u, np.zeros_like(u), x, np.zeros_like(x), flags=np.array([[0, 1, 0, 1]])
        )
        self.assertEqual(analyzer.flags.dtype, np.dtype(bool))
        np.testing.assert_array_equal(analyzer.u[~analyzer.flags], [0.0, 2.0])

    def test_the_quiver_plot_draws_only_the_valid_vectors(self) -> None:
        u = np.arange(4.0).reshape(1, 4)
        x = np.tile(np.arange(4) * 1.0, (1, 1))
        analyzer = self.analyzer(
            u, np.zeros_like(u), x, np.zeros_like(x), flags=np.array([[0, 1, 0, 1]])
        )
        self.addCleanup(plt.close, "all")
        target = self.root / "quiver.png"
        figure = analyzer.plot_vector_field(save_path=str(target))
        self.assertTrue(target.is_file())
        quivers = figure.axes[0].collections
        self.assertEqual(len(quivers), 1)
        self.assertEqual(len(quivers[0].get_offsets()), 2)


class BundledExampleTests(unittest.TestCase):
    def test_the_example_pair_ships_inside_the_installed_openpiv(self) -> None:
        # run_example.py's whole premise is that no external data is needed, so
        # if upstream drops these files the script is broken.
        first, second = run_example.bundled_image_pair()
        self.assertTrue(first.is_file())
        self.assertTrue(second.is_file())
        self.assertEqual(first.name, "exp1_001_a.bmp")
        self.assertEqual(second.name, "exp1_001_b.bmp")


if __name__ == "__main__":
    unittest.main()
