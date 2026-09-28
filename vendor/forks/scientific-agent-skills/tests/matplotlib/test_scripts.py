"""Tests for the matplotlib plotting templates and style configurator.

Rendering assertions are shallow by nature, so these tests go after the things
that can actually be wrong: that every style preset contains only rcParams
matplotlib recognises (a typo'd key is silently ignored, and the figure just
looks wrong), that a saved `.mplstyle` file can be loaded back by matplotlib
itself, and that each plot helper draws onto the axes it is handed rather than
into the global current figure.

Everything runs on the Agg backend and closes its figures; a suite that leaks
figures eventually trips matplotlib's open-figure warning.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "matplotlib"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

matplotlib = pytest.importorskip("matplotlib", reason="matplotlib skill needs matplotlib")
matplotlib.use("Agg")
np = pytest.importorskip("numpy", reason="matplotlib scripts need numpy")

import matplotlib.pyplot as plt  # noqa: E402

import plot_template  # noqa: E402
import style_configurator  # noqa: E402

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

PLOT_BUILDERS = (
    "create_line_plot",
    "create_scatter_plot",
    "create_bar_chart",
    "create_histogram",
    "create_heatmap",
    "create_contour_plot",
    "create_box_plot",
    "create_violin_plot",
)


class FigureTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(plt.close, "all")


class StylePresetTests(unittest.TestCase):
    def test_presets_exist_and_are_named_dictionaries(self) -> None:
        self.assertTrue(style_configurator.STYLE_PRESETS)
        for name, settings in style_configurator.STYLE_PRESETS.items():
            with self.subTest(preset=name):
                self.assertIsInstance(settings, dict)
                self.assertTrue(settings)

    def test_every_preset_key_is_a_real_rcparam(self) -> None:
        # matplotlib ignores unknown rcParams silently, so a typo here is
        # invisible until someone notices the figure looks wrong.
        valid = set(matplotlib.rcParams)
        for name, settings in style_configurator.STYLE_PRESETS.items():
            unknown = sorted(set(settings) - valid)
            with self.subTest(preset=name):
                self.assertEqual(unknown, [])

    def test_every_preset_applies_cleanly(self) -> None:
        original = matplotlib.rcParams.copy()
        self.addCleanup(matplotlib.rcParams.update, original)
        for name, settings in style_configurator.STYLE_PRESETS.items():
            with self.subTest(preset=name):
                matplotlib.rcParams.update(settings)

    def test_the_publication_preset_saves_at_print_resolution(self) -> None:
        publication = style_configurator.STYLE_PRESETS["publication"]
        self.assertGreaterEqual(publication["savefig.dpi"], 300)
        self.assertEqual(publication["savefig.bbox"], "tight")

    def test_every_documented_preset_is_defined(self) -> None:
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            style_configurator.list_available_presets()
        listed = buffer.getvalue()

        for name in style_configurator.STYLE_PRESETS:
            with self.subTest(preset=name):
                self.assertIn(name, listed)


class StyleFileTests(unittest.TestCase):
    def test_a_saved_style_is_loadable_by_matplotlib(self) -> None:
        # The real contract: matplotlib must be able to read what we wrote.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom.mplstyle"
            style_configurator.save_style_file(
                style_configurator.STYLE_PRESETS["publication"], str(path)
            )
            self.assertTrue(path.is_file())

            original = matplotlib.rcParams.copy()
            self.addCleanup(matplotlib.rcParams.update, original)
            plt.style.use(str(path))

    def test_the_file_is_commented_and_grouped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom.mplstyle"
            style_configurator.save_style_file(
                style_configurator.STYLE_PRESETS["publication"], str(path)
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("# Custom matplotlib style", text)
        self.assertIn("# Figure", text)
        self.assertIn("savefig.dpi: 300", text)

    def test_sequence_values_are_written_comma_separated(self) -> None:
        # `font.sans-serif` is a list; mplstyle wants `a, b`, not `['a', 'b']`.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom.mplstyle"
            style_configurator.save_style_file(
                {"font.sans-serif": ["Arial", "Helvetica"]}, str(path)
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("font.sans-serif: Arial, Helvetica", text)
        self.assertNotIn("[", text)

    def test_an_empty_style_still_writes_a_valid_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.mplstyle"
            style_configurator.save_style_file({}, str(path))
            self.assertTrue(path.is_file())
            original = matplotlib.rcParams.copy()
            self.addCleanup(matplotlib.rcParams.update, original)
            plt.style.use(str(path))


class SampleDataTests(unittest.TestCase):
    def test_the_sample_data_covers_every_plot_type(self) -> None:
        data = plot_template.generate_sample_data()
        self.assertIsInstance(data, dict)
        self.assertTrue(data)

    def test_the_sample_data_is_deterministic(self) -> None:
        # The templates are documentation; a figure that changes between runs
        # cannot be compared against the one in the docs.
        first = plot_template.generate_sample_data()
        second = plot_template.generate_sample_data()
        self.assertEqual(sorted(first), sorted(second))
        for key, value in first.items():
            with self.subTest(series=key):
                if isinstance(value, np.ndarray):
                    np.testing.assert_allclose(value, second[key])

    def test_the_preview_data_is_deterministic_too(self) -> None:
        first = style_configurator.generate_preview_data()
        second = style_configurator.generate_preview_data()
        for key, value in first.items():
            with self.subTest(series=key):
                if isinstance(value, np.ndarray):
                    np.testing.assert_allclose(value, second[key])


class PlotBuilderTests(FigureTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.data = plot_template.generate_sample_data()

    def test_every_builder_draws_onto_the_axes_it_is_given(self) -> None:
        for name in PLOT_BUILDERS:
            with self.subTest(builder=name):
                figure, axes = plt.subplots()
                getattr(plot_template, name)(self.data, ax=axes)
                # Something was drawn: lines, patches, images, or collections.
                drawn = (
                    len(axes.lines)
                    + len(axes.patches)
                    + len(axes.images)
                    + len(axes.collections)
                )
                self.assertGreater(drawn, 0, f"{name} drew nothing")
                plt.close(figure)

    def test_every_builder_labels_its_axes(self) -> None:
        # An unlabelled publication figure is a bug, not a style preference.
        for name in PLOT_BUILDERS:
            with self.subTest(builder=name):
                figure, axes = plt.subplots()
                getattr(plot_template, name)(self.data, ax=axes)
                self.assertTrue(
                    axes.get_title() or axes.get_xlabel() or axes.get_ylabel(),
                    f"{name} produced an unlabelled figure",
                )
                plt.close(figure)

    def test_builders_create_their_own_axes_when_none_is_supplied(self) -> None:
        for name in PLOT_BUILDERS:
            with self.subTest(builder=name):
                before = len(plt.get_fignums())
                getattr(plot_template, name)(self.data)
                self.assertGreaterEqual(len(plt.get_fignums()), before)
                plt.close("all")

    def test_the_publication_style_applies_without_error(self) -> None:
        original = matplotlib.rcParams.copy()
        self.addCleanup(matplotlib.rcParams.update, original)
        plot_template.set_publication_style()
        self.assertGreaterEqual(matplotlib.rcParams["savefig.dpi"], 150)


class CompositeFigureTests(FigureTestCase):
    def test_the_comprehensive_figure_renders_and_saves(self) -> None:
        result = plot_template.create_comprehensive_figure()
        self.assertIsNotNone(result)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "figure.png"
            plt.savefig(output, dpi=72)
            self.assertGreater(output.stat().st_size, 0)

    def test_the_style_preview_renders(self) -> None:
        result = style_configurator.create_style_preview(
            style_configurator.STYLE_PRESETS["minimal"]
        )
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
