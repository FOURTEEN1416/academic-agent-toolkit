"""Tests for the phylogenetics pipeline script.

The pipeline is a thin shell around MAFFT, IQ-TREE 2, and FastTree, none of
which are Python packages and none of which are installed here. What can still
be wrong -- and would only show up as a wasted multi-hour run -- is the *command
line* the script hands to them: MAFFT's accuracy/speed strategy is chosen from
the sequence count, and FastTree's substitution model must match the sequence
type (`-gtr` is nucleotide-only, `-lg` protein-only). Those commands are
therefore asserted argument by argument with `subprocess.run` replaced by a
recorder, so no external binary is ever invoked.

`count_sequences` and the ETE3 tree summary are checked against a FASTA and a
Newick string whose answers are known by construction; the summary's branch
lengths hold because rerooting relocates the root along an existing branch and
so preserves the tree's total length.
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "phylogenetics"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

# The script imports nothing heavier than the standard library at module scope
# -- ete3 is imported lazily inside the two visualisation helpers -- so there is
# no module-level package to guard. The ete3-dependent tests skip individually.
import phylogenetic_analysis as pipeline  # noqa: E402

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

#: Four taxa, total branch length 8 (1+1+1+1+2+2); the six non-zero branches
#: give a mean of 8/6 and a maximum of 2.
FOUR_TAXA = "((A:1,B:1):1,(C:2,D:2):1);"


class Recorder:
    """Stands in for `subprocess.run`: records argv, launches nothing."""

    def __init__(self, returncode: int = 0, stderr: str = "", failing: str | None = None):
        self.calls: list[list[str]] = []
        self._returncode = returncode
        self._stderr = stderr
        self._failing = failing

    def __call__(self, command, **kwargs) -> subprocess.CompletedProcess:
        self.calls.append(list(command))
        returncode = self._returncode
        if self._failing is not None:
            returncode = 1 if self._failing in command else 0
        return subprocess.CompletedProcess(
            list(command), returncode, stdout="", stderr=self._stderr
        )

    @property
    def command(self) -> list[str]:
        self.assert_called()
        return self.calls[-1]

    def assert_called(self) -> None:
        if not self.calls:
            raise AssertionError("subprocess.run was never called")


@contextlib.contextmanager
def recorded(recorder: Recorder):
    with mock.patch.object(pipeline.subprocess, "run", recorder):
        yield recorder


class ScratchCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)

    def fasta(self, count: int, name: str | None = None) -> Path:
        path = self.root / (name or f"seqs{count}.fasta")
        path.write_text(
            "".join(f">seq{index}\nACGTACGT\n" for index in range(count)),
            encoding="utf-8",
        )
        return path

    def newick(self, text: str = FOUR_TAXA, name: str = "tree.nwk") -> Path:
        path = self.root / name
        path.write_text(text + "\n", encoding="utf-8")
        return path


class SequenceCountTests(ScratchCase):
    def test_headers_are_counted_not_lines(self) -> None:
        self.assertEqual(pipeline.count_sequences(str(self.fasta(3))), 3)

    def test_an_empty_file_has_no_sequences(self) -> None:
        # 0 must come back as 0 rather than raise: run_mafft divides the world
        # into size bands on this number.
        self.assertEqual(pipeline.count_sequences(str(self.fasta(0))), 0)

    def test_a_wrapped_sequence_counts_once(self) -> None:
        path = self.root / "wrapped.fasta"
        path.write_text(">only\nACGT\nACGT\nACGT\n", encoding="utf-8")
        self.assertEqual(pipeline.count_sequences(str(path)), 1)

    def test_an_angle_bracket_that_does_not_start_a_line_is_not_a_header(self) -> None:
        # Indented or mid-line ">" appears in quality lines and comments; only a
        # line-initial one opens a FASTA record.
        path = self.root / "odd.fasta"
        path.write_text(">real\nACGT\n  >indented\nAC>GT\n", encoding="utf-8")
        self.assertEqual(pipeline.count_sequences(str(path)), 1)

    def test_a_missing_file_raises_rather_than_reporting_zero(self) -> None:
        with self.assertRaises(FileNotFoundError):
            pipeline.count_sequences(str(self.root / "absent.fasta"))


class MafftCommandTests(ScratchCase):
    """`--mafft-method auto` trades accuracy for speed as the dataset grows."""

    def align(self, sequences: int, **kwargs) -> list[str]:
        source = self.fasta(sequences)
        with recorded(Recorder()) as recorder:
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.run_mafft(
                    str(source), str(self.root / "aligned.fasta"), **kwargs
                )
        return recorder.command

    def test_small_datasets_get_the_accurate_pairwise_strategy(self) -> None:
        command = self.align(10)
        self.assertEqual(command[0], "mafft")
        self.assertIn("--localpair", command)
        self.assertEqual(command[command.index("--maxiterate") + 1], "1000")

    def test_the_two_hundred_sequence_boundary_is_inclusive(self) -> None:
        # `n_seqs <= 200` -- 200 still gets --localpair, 201 drops to --auto.
        self.assertIn("--localpair", self.align(200))
        self.assertNotIn("--localpair", self.align(201))
        self.assertIn("--auto", self.align(201))

    def test_the_thousand_sequence_boundary_is_inclusive(self) -> None:
        # `n_seqs <= 1000` -- above it MAFFT must drop to the FFT-NS heuristic,
        # because --auto on a large alignment can run for days.
        self.assertIn("--auto", self.align(1000))
        self.assertNotIn("--auto", self.align(1001))
        self.assertIn("--fftns", self.align(1001))

    def test_an_explicit_method_overrides_the_size_bands(self) -> None:
        command = self.align(10, method="fftns")
        self.assertIn("--fftns", command)
        self.assertNotIn("--localpair", command)

    def test_the_thread_count_reaches_mafft_as_a_string(self) -> None:
        for sequences in (10, 500, 2000):
            with self.subTest(sequences=sequences):
                command = self.align(sequences, n_threads=7)
                self.assertEqual(command[command.index("--thread") + 1], "7")

    def test_the_input_order_is_preserved_and_the_file_comes_last(self) -> None:
        # Without --inputorder MAFFT reorders the alignment, which silently
        # breaks any downstream code that pairs it with a metadata table.
        source = self.fasta(10, "in.fasta")
        with recorded(Recorder()) as recorder:
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.run_mafft(str(source), str(self.root / "out.fasta"))
        self.assertIn("--inputorder", recorder.command)
        self.assertEqual(recorder.command[-1], str(source))

    def test_the_alignment_is_written_to_the_requested_path(self) -> None:
        destination = self.root / "aligned.fasta"
        with recorded(Recorder()):
            with contextlib.redirect_stdout(io.StringIO()):
                returned = pipeline.run_mafft(str(self.fasta(5)), str(destination))
        self.assertEqual(returned, str(destination))
        self.assertTrue(destination.exists())

    def test_a_mafft_failure_is_raised_not_swallowed(self) -> None:
        # Continuing with a truncated alignment would produce a tree from
        # nothing, so a non-zero exit has to stop the pipeline.
        with recorded(Recorder(returncode=1, stderr="mafft: bad input")):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "MAFFT failed"):
                    pipeline.run_mafft(
                        str(self.fasta(5)), str(self.root / "aligned.fasta")
                    )


class IqTreeCommandTests(ScratchCase):
    def build(self, **kwargs) -> tuple[list[str], str, str]:
        alignment = self.root / "aligned.fasta"
        alignment.write_text(">a\nACGT\n", encoding="utf-8")
        prefix = str(self.root / "run")
        buffer = io.StringIO()
        with recorded(Recorder()) as recorder:
            with contextlib.redirect_stdout(buffer):
                tree_file = pipeline.run_iqtree(str(alignment), prefix, **kwargs)
        return recorder.command, tree_file, buffer.getvalue()

    def test_the_command_carries_the_documented_flags(self) -> None:
        command, _, _ = self.build(bootstrap=1000, n_threads=4)
        self.assertEqual(command[0], "iqtree2")
        pairs = {
            "-s": str(self.root / "aligned.fasta"),
            "--prefix": str(self.root / "run"),
            # TEST selects the substitution model instead of assuming one.
            "-m": "TEST",
            "-B": "1000",
            "-T": "4",
            # SH-aLRT is a second branch test alongside ultrafast bootstrap.
            "-alrt": "1000",
        }
        for flag, value in pairs.items():
            with self.subTest(flag=flag):
                self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn("--redo", command)

    def test_the_bootstrap_and_thread_counts_are_not_hardcoded(self) -> None:
        command, _, _ = self.build(bootstrap=5000, n_threads=16)
        self.assertEqual(command[command.index("-B") + 1], "5000")
        self.assertEqual(command[command.index("-T") + 1], "16")

    def test_an_outgroup_is_passed_only_when_one_is_given(self) -> None:
        command, _, _ = self.build()
        self.assertNotIn("-o", command)
        command, _, _ = self.build(outgroup="Escherichia_coli")
        self.assertEqual(command[command.index("-o") + 1], "Escherichia_coli")

    def test_the_returned_path_is_iqtrees_treefile(self) -> None:
        _, tree_file, _ = self.build()
        self.assertEqual(tree_file, str(self.root / "run.treefile"))

    def test_the_selected_model_is_echoed_from_the_log(self) -> None:
        # The chosen model is the one result a reader needs to report, and it
        # only exists in IQ-TREE's log file.
        (self.root / "run.log").write_text(
            "Reading alignment\nBest-fit model: GTR+F+I+G4 chosen according to BIC\n",
            encoding="utf-8",
        )
        _, _, output = self.build()
        self.assertIn("Best-fit model: GTR+F+I+G4", output)

    def test_a_missing_log_is_not_an_error(self) -> None:
        _, tree_file, output = self.build()
        self.assertTrue(tree_file)
        self.assertNotIn("Best-fit model", output)

    def test_an_iqtree_failure_is_raised(self) -> None:
        alignment = self.root / "aligned.fasta"
        alignment.write_text(">a\nACGT\n", encoding="utf-8")
        with recorded(Recorder(returncode=2, stderr="ERROR: too few sites")):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "IQ-TREE failed"):
                    pipeline.run_iqtree(str(alignment), str(self.root / "run"))


class FastTreeCommandTests(ScratchCase):
    def build(self, seq_type: str) -> list[str]:
        alignment = self.root / "aligned.fasta"
        alignment.write_text(">a\nACGT\n", encoding="utf-8")
        with recorded(Recorder()) as recorder:
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.run_fasttree(
                    str(alignment), str(self.root / "out.tree"), seq_type=seq_type
                )
        return recorder.command

    def test_nucleotides_get_the_nucleotide_model(self) -> None:
        # -nt switches FastTree out of its protein default, and GTR is only
        # defined for nucleotides.
        command = self.build("nt")
        self.assertEqual(command[:4], ["FastTree", "-nt", "-gtr", "-gamma"])

    def test_amino_acids_get_a_protein_model_and_no_nucleotide_flag(self) -> None:
        # Passing -nt on protein data makes FastTree read every residue as an
        # ambiguous base, so the flag must be absent here.
        command = self.build("aa")
        self.assertEqual(command[:3], ["FastTree", "-lg", "-gamma"])
        self.assertNotIn("-nt", command)
        self.assertNotIn("-gtr", command)

    def test_the_alignment_is_the_final_argument(self) -> None:
        for seq_type in ("nt", "aa"):
            with self.subTest(seq_type=seq_type):
                self.assertEqual(
                    self.build(seq_type)[-1], str(self.root / "aligned.fasta")
                )

    def test_the_tree_path_is_returned_and_created(self) -> None:
        alignment = self.root / "aligned.fasta"
        alignment.write_text(">a\nACGT\n", encoding="utf-8")
        destination = self.root / "out.tree"
        with recorded(Recorder()):
            with contextlib.redirect_stdout(io.StringIO()):
                returned = pipeline.run_fasttree(str(alignment), str(destination))
        self.assertEqual(returned, str(destination))
        self.assertTrue(destination.exists())

    def test_a_fasttree_failure_is_raised(self) -> None:
        alignment = self.root / "aligned.fasta"
        alignment.write_text(">a\nACGT\n", encoding="utf-8")
        with recorded(Recorder(returncode=1, stderr="FastTree: no sequences")):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "FastTree failed"):
                    pipeline.run_fasttree(str(alignment), str(self.root / "out.tree"))


class DependencyCheckTests(unittest.TestCase):
    def test_a_complete_toolchain_reports_success_and_returns(self) -> None:
        buffer = io.StringIO()
        with recorded(Recorder(returncode=0)) as recorder:
            with contextlib.redirect_stdout(buffer):
                pipeline.check_dependencies()
        self.assertIn("All dependencies found", buffer.getvalue())
        # Both binaries are probed, not just the first.
        self.assertEqual(
            [call[1] for call in recorder.calls], ["mafft", "iqtree2"]
        )

    def test_a_missing_tool_exits_with_its_install_command(self) -> None:
        buffer = io.StringIO()
        with recorded(Recorder(failing="iqtree2")):
            with contextlib.redirect_stdout(buffer):
                with self.assertRaises(SystemExit) as raised:
                    pipeline.check_dependencies()
        self.assertEqual(raised.exception.code, 1)
        report = buffer.getvalue()
        self.assertIn("Missing dependencies", report)
        self.assertIn("conda install -c bioconda iqtree", report)
        # mafft was present, so it must not be listed as missing.
        self.assertNotIn("bioconda mafft", report)

    def test_every_tool_is_probed_by_name_on_the_path(self) -> None:
        with recorded(Recorder(returncode=0)) as recorder:
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.check_dependencies()
        for call in recorder.calls:
            self.assertEqual(call[0], "which")


class TreeSummaryTests(ScratchCase):
    def test_the_summary_matches_the_newick_string(self) -> None:
        pytest.importorskip("ete3", reason="tree summaries need ete3")
        with contextlib.redirect_stdout(io.StringIO()):
            stats = pipeline.tree_summary(str(self.newick()))
        self.assertEqual(stats["n_taxa"], 4)
        # Midpoint rooting relocates the root along an existing branch, splitting
        # it in two, so the total length is unchanged at 1+1+1+1+2+2 = 8.
        self.assertAlmostEqual(stats["total_branch_length"], 8.0)
        self.assertAlmostEqual(stats["max_branch_length"], 2.0)
        # Six non-zero branches survive rerooting, so the mean is 8/6.
        self.assertAlmostEqual(stats["mean_branch_length"], 8 / 6)

    def test_the_mean_is_consistent_with_the_total(self) -> None:
        pytest.importorskip("ete3", reason="tree summaries need ete3")
        with contextlib.redirect_stdout(io.StringIO()):
            stats = pipeline.tree_summary(str(self.newick("(A:0.5,(B:0.5,C:1.5):0.5);")))
        self.assertEqual(stats["n_taxa"], 3)
        self.assertAlmostEqual(stats["total_branch_length"], 3.0)
        self.assertLessEqual(stats["mean_branch_length"], stats["max_branch_length"])

    def test_an_unreadable_tree_returns_an_empty_summary(self) -> None:
        # tree_summary is called for its report, so a bad tree file must not
        # abort a pipeline that has already produced its outputs.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(pipeline.tree_summary(str(self.root / "absent.nwk")), {})
        self.assertIn("Could not compute tree stats", buffer.getvalue())

    def test_malformed_newick_returns_an_empty_summary(self) -> None:
        malformed = self.root / "bad.nwk"
        malformed.write_text("((A:1,B:1)\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.tree_summary(str(malformed)), {})


class VisualisationTests(ScratchCase):
    def test_the_rooting_choice_is_reported(self) -> None:
        ete3 = pytest.importorskip("ete3", reason="visualisation needs ete3")
        if not hasattr(ete3, "TreeStyle"):
            self.skipTest("ete3's Qt treeview is unavailable, so rooting is not reached")
        for outgroup, expected in (("A", "Rooted at outgroup: A"), ("Z", "midpoint")):
            with self.subTest(outgroup=outgroup):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    pipeline.visualize_tree(
                        str(self.newick()),
                        str(self.root / f"{outgroup}.png"),
                        outgroup=outgroup,
                    )
                self.assertIn(expected, buffer.getvalue())

    def test_a_missing_qt_backend_names_the_package_it_needs(self) -> None:
        ete3 = pytest.importorskip("ete3", reason="visualisation needs ete3")
        if hasattr(ete3, "TreeStyle"):
            self.skipTest("ete3's Qt treeview is installed, so the hint is not reached")
        # ete3 imports fine without PyQt5 but cannot render, so the diagnostic
        # has to name PyQt5 rather than tell the user to install ete3 again.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertIsNone(
                pipeline.visualize_tree(str(self.newick()), str(self.root / "t.png"))
            )
        report = buffer.getvalue()
        self.assertIn("PyQt5", report)
        self.assertIn("Skipping visualization", report)


class PipelineWiringTests(ScratchCase):
    """`main` end to end with every external tool replaced by a recorder."""

    def run_pipeline(self, extra: list[str] | None = None) -> tuple[Recorder, mock.Mock]:
        source = self.fasta(5, "in.fasta")
        output_dir = self.root / "results"
        argv = [
            "phylogenetic_analysis.py",
            str(source),
            "--output-dir",
            str(output_dir),
            *(extra or []),
        ]
        recorder = Recorder()
        with mock.patch.object(pipeline.subprocess, "run", recorder), mock.patch.object(
            pipeline, "visualize_tree"
        ) as visualise, mock.patch.object(
            pipeline, "tree_summary", return_value={}
        ), mock.patch.object(sys, "argv", argv):
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.main()
        self.assertTrue(output_dir.is_dir())
        return recorder, visualise

    def test_the_default_run_is_align_then_iqtree(self) -> None:
        recorder, visualise = self.run_pipeline()
        self.assertEqual([call[0] for call in recorder.calls], ["mafft", "iqtree2"])
        # IQ-TREE must be handed MAFFT's *output*, not the unaligned input.
        aligned = str(self.root / "results" / "in_aligned.fasta")
        iqtree = recorder.calls[1]
        self.assertEqual(iqtree[iqtree.index("-s") + 1], aligned)
        visualise.assert_called_once()
        self.assertEqual(
            visualise.call_args.args,
            (
                str(self.root / "results" / "in.treefile"),
                str(self.root / "results" / "in_tree.png"),
            ),
        )

    def test_fasttree_replaces_iqtree_rather_than_running_alongside_it(self) -> None:
        recorder, _ = self.run_pipeline(["--fasttree"])
        self.assertEqual([call[0] for call in recorder.calls], ["mafft", "FastTree"])

    def test_the_sequence_type_reaches_fasttrees_model_choice(self) -> None:
        recorder, _ = self.run_pipeline(["--fasttree", "--type", "aa"])
        self.assertIn("-lg", recorder.calls[1])
        self.assertNotIn("-nt", recorder.calls[1])

    def test_the_outgroup_reaches_both_iqtree_and_the_visualisation(self) -> None:
        recorder, visualise = self.run_pipeline(["--outgroup", "Outgroup_sp"])
        iqtree = recorder.calls[1]
        self.assertEqual(iqtree[iqtree.index("-o") + 1], "Outgroup_sp")
        self.assertEqual(visualise.call_args.kwargs["outgroup"], "Outgroup_sp")

    def test_an_unsupported_sequence_type_is_refused_before_any_tool_runs(self) -> None:
        recorder = Recorder()
        argv = ["phylogenetic_analysis.py", str(self.fasta(5, "in.fasta")), "--type", "protein"]
        with mock.patch.object(pipeline.subprocess, "run", recorder), mock.patch.object(
            sys, "argv", argv
        ):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    pipeline.main()
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(recorder.calls, [])

    def test_an_unsupported_mafft_method_is_refused(self) -> None:
        # An unknown method would otherwise be interpolated straight into
        # `--{method}` and reach MAFFT as an invalid flag.
        recorder = Recorder()
        argv = [
            "phylogenetic_analysis.py",
            str(self.fasta(5, "in.fasta")),
            "--mafft-method",
            "hmmalign",
        ]
        with mock.patch.object(pipeline.subprocess, "run", recorder), mock.patch.object(
            sys, "argv", argv
        ):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    pipeline.main()
        self.assertEqual(recorder.calls, [])


if __name__ == "__main__":
    unittest.main()
