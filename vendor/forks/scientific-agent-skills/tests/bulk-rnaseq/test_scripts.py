"""Tests for the bulk RNA-seq samplesheet validator and counts-matrix builder.

`validate_samplesheet` is the gate in front of an expensive pipeline run, and
the distinction it draws between an error and a warning is the whole product:
a duplicated FASTQ is fatal, the same sample across lanes is not. Every test
here asserts on that split, not merely that "something was reported".

The design checks matter just as much. A group with one replicate cannot
estimate variance, and a batch nested inside condition cannot be separated
from the biology -- both are silent disasters downstream, so both are pinned.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "bulk-rnaseq"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

pd = pytest.importorskip("pandas", reason="bulk-rnaseq needs pandas")

import build_counts_matrix  # noqa: E402
import validate_samplesheet  # noqa: E402

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

GOOD_SHEET = """\
sample,fastq_1,fastq_2,strandedness
ctrl_1,ctrl_1_R1.fastq.gz,ctrl_1_R2.fastq.gz,auto
ctrl_2,ctrl_2_R1.fastq.gz,ctrl_2_R2.fastq.gz,auto
treat_1,treat_1_R1.fastq.gz,treat_1_R2.fastq.gz,auto
treat_2,treat_2_R1.fastq.gz,treat_2_R2.fastq.gz,auto
"""

GOOD_METADATA = """\
sample,condition,batch
ctrl_1,control,b1
ctrl_2,control,b2
treat_1,treated,b1
treat_2,treated,b2
"""


class SamplesheetTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.report = validate_samplesheet.Report()

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def validate(self, text: str, check_files: bool = False):
        return validate_samplesheet.validate_samplesheet(
            self.write("samplesheet.csv", text), check_files, self.report
        )


class SamplesheetShapeTests(SamplesheetTestCase):
    def test_a_well_formed_sheet_passes_cleanly(self) -> None:
        sheet = self.validate(GOOD_SHEET)
        self.assertIsNotNone(sheet)
        self.assertEqual(self.report.errors, [])
        self.assertEqual(self.report.warnings, [])
        self.assertEqual(len(sheet), 4)

    def test_a_missing_file_is_an_error_not_a_crash(self) -> None:
        result = validate_samplesheet.validate_samplesheet(
            self.root / "absent.csv", False, self.report
        )
        self.assertIsNone(result)
        self.assertTrue(any("not found" in e for e in self.report.errors))

    def test_the_required_columns_are_sample_and_fastq_1(self) -> None:
        self.validate("sample,reads\nctrl_1,x.fastq.gz\n")
        self.assertTrue(
            any("must have at least" in e for e in self.report.errors)
        )

    def test_whitespace_around_headers_and_values_is_stripped(self) -> None:
        sheet = self.validate(
            " sample , fastq_1 \n ctrl_1 , ctrl_1_R1.fastq.gz \n"
        )
        self.assertEqual(list(sheet.columns), ["sample", "fastq_1"])
        self.assertEqual(sheet.loc[0, "sample"], "ctrl_1")
        self.assertEqual(self.report.errors, [])

    def test_a_missing_strandedness_column_is_only_advisory(self) -> None:
        self.validate("sample,fastq_1\nctrl_1,a.fastq.gz\n")
        self.assertEqual(self.report.errors, [])
        self.assertTrue(any("strandedness" in w for w in self.report.warnings))


class SamplesheetContentTests(SamplesheetTestCase):
    def test_empty_sample_or_read_cells_are_errors_with_a_row_number(self) -> None:
        self.validate("sample,fastq_1\n,a.fastq.gz\nctrl_2,\n")
        self.assertTrue(any("row 2" in e and "'sample'" in e for e in self.report.errors))
        self.assertTrue(any("row 3" in e and "'fastq_1'" in e for e in self.report.errors))

    def test_the_same_file_in_both_read_columns_is_an_error(self) -> None:
        # A copy-paste that would silently halve the library.
        self.validate("sample,fastq_1,fastq_2\nctrl_1,same.fastq.gz,same.fastq.gz\n")
        self.assertTrue(any("the same file" in e for e in self.report.errors))

    def test_a_reused_read_one_file_is_an_error(self) -> None:
        self.validate(
            "sample,fastq_1\nctrl_1,shared.fastq.gz\nctrl_2,shared.fastq.gz\n"
        )
        self.assertTrue(any("appears 2 times" in e for e in self.report.errors))

    def test_unknown_strandedness_values_are_rejected(self) -> None:
        self.validate("sample,fastq_1,strandedness\nctrl_1,a.fastq.gz,sideways\n")
        self.assertTrue(any("strandedness 'sideways'" in e for e in self.report.errors))

    def test_every_documented_strandedness_value_is_accepted(self) -> None:
        rows = "\n".join(
            f"s{i},r{i}.fastq.gz,{value}"
            for i, value in enumerate(sorted(validate_samplesheet.VALID_STRANDEDNESS))
        )
        self.validate(f"sample,fastq_1,strandedness\n{rows}\n")
        self.assertEqual(self.report.errors, [])

    def test_strandedness_is_matched_case_insensitively(self) -> None:
        self.validate("sample,fastq_1,strandedness\nctrl_1,a.fastq.gz,REVERSE\n")
        self.assertEqual(self.report.errors, [])

    def test_one_sample_across_lanes_warns_but_does_not_fail(self) -> None:
        # nf-core merges lanes, so this is normal -- it must stay a warning.
        self.validate(
            "sample,fastq_1,fastq_2\n"
            "ctrl_1,L1_R1.fastq.gz,L1_R2.fastq.gz\n"
            "ctrl_1,L2_R1.fastq.gz,L2_R2.fastq.gz\n"
        )
        self.assertEqual(self.report.errors, [])
        self.assertTrue(any("lane-merged" in w for w in self.report.warnings))

    def test_mixing_paired_and_single_rows_for_one_sample_is_an_error(self) -> None:
        self.validate(
            "sample,fastq_1,fastq_2\n"
            "ctrl_1,L1_R1.fastq.gz,L1_R2.fastq.gz\n"
            "ctrl_1,L2_R1.fastq.gz,\n"
        )
        self.assertTrue(
            any("mixes paired-end and single-end" in e for e in self.report.errors)
        )


class FileExistenceTests(SamplesheetTestCase):
    def test_absent_local_reads_are_errors_when_checking_is_on(self) -> None:
        self.validate("sample,fastq_1\nctrl_1,missing.fastq.gz\n", check_files=True)
        self.assertTrue(any("fastq_1 not found" in e for e in self.report.errors))

    def test_present_local_reads_pass(self) -> None:
        (self.root / "real.fastq.gz").write_bytes(b"")
        self.validate(
            f"sample,fastq_1\nctrl_1,{self.root / 'real.fastq.gz'}\n", check_files=True
        )
        self.assertEqual(self.report.errors, [])

    def test_an_unusual_extension_on_an_existing_file_is_only_a_warning(self) -> None:
        (self.root / "reads.txt").write_bytes(b"")
        self.validate(
            f"sample,fastq_1\nctrl_1,{self.root / 'reads.txt'}\n", check_files=True
        )
        self.assertEqual(self.report.errors, [])
        self.assertTrue(any("unusual extension" in w for w in self.report.warnings))

    def test_remote_urls_are_skipped_rather_than_reported_missing(self) -> None:
        for prefix in validate_samplesheet.REMOTE_PREFIXES:
            with self.subTest(prefix=prefix):
                report = validate_samplesheet.Report()
                path = self.write(
                    "remote.csv", f"sample,fastq_1\nctrl_1,{prefix}bucket/r1.fastq.gz\n"
                )
                validate_samplesheet.validate_samplesheet(path, True, report)
                self.assertEqual(report.errors, [])
                self.assertTrue(any("remote" in w for w in report.warnings))

    def test_nothing_is_checked_when_file_checking_is_off(self) -> None:
        self.validate("sample,fastq_1\nctrl_1,missing.fastq.gz\n", check_files=False)
        self.assertEqual(self.report.errors, [])


class MetadataTests(SamplesheetTestCase):
    def _validate_metadata(self, metadata: str, sheet_text: str = GOOD_SHEET,
                           condition_col: str = "condition", min_rep: int = 3):
        sheet = validate_samplesheet.validate_samplesheet(
            self.write("sheet.csv", sheet_text), False, validate_samplesheet.Report()
        )
        validate_samplesheet.validate_metadata(
            self.write("meta.csv", metadata), sheet, condition_col, min_rep, self.report
        )
        return sheet

    def test_a_matching_design_passes_apart_from_the_replicate_advisory(self) -> None:
        self._validate_metadata(GOOD_METADATA)
        self.assertEqual(self.report.errors, [])

    def test_a_missing_condition_column_names_the_columns_it_found(self) -> None:
        self._validate_metadata("sample,group\nctrl_1,control\n")
        self.assertTrue(any("no 'condition' column" in e for e in self.report.errors))
        self.assertTrue(any("group" in e for e in self.report.errors))

    def test_samples_missing_from_the_metadata_are_an_error(self) -> None:
        self._validate_metadata("sample,condition\nctrl_1,control\nctrl_2,control\n")
        self.assertTrue(
            any("missing from metadata" in e for e in self.report.errors)
        )

    def test_extra_metadata_samples_are_only_a_warning(self) -> None:
        self._validate_metadata(GOOD_METADATA + "spare,control,b3\n")
        self.assertEqual(self.report.errors, [])
        self.assertTrue(
            any("not in samplesheet" in w for w in self.report.warnings)
        )

    def test_a_singleton_group_cannot_estimate_variance_and_is_fatal(self) -> None:
        sheet_text = (
            "sample,fastq_1\n"
            "ctrl_1,c1.fastq.gz\nctrl_2,c2.fastq.gz\ntreat_1,t1.fastq.gz\n"
        )
        self._validate_metadata(
            "sample,condition\nctrl_1,control\nctrl_2,control\ntreat_1,treated\n",
            sheet_text=sheet_text,
        )
        self.assertTrue(
            any("need >=2 to estimate variance" in e for e in self.report.errors)
        )

    def test_two_replicates_pass_but_warn_below_the_recommended_minimum(self) -> None:
        self._validate_metadata(GOOD_METADATA, min_rep=3)
        self.assertEqual(self.report.errors, [])
        self.assertTrue(any("recommended" in w for w in self.report.warnings))

    def test_an_entirely_empty_condition_column_is_fatal(self) -> None:
        self._validate_metadata(
            "sample,condition\nctrl_1,\nctrl_2,\ntreat_1,\ntreat_2,\n"
        )
        self.assertTrue(any("is empty for all samples" in e for e in self.report.errors))

    def test_batch_fully_nested_in_condition_is_flagged_as_confounded(self) -> None:
        # Each batch holding a single condition means the batch effect and the
        # biology cannot be told apart -- the most expensive silent mistake here.
        self._validate_metadata(
            "sample,condition,batch\n"
            "ctrl_1,control,b1\nctrl_2,control,b1\n"
            "treat_1,treated,b2\ntreat_2,treated,b2\n"
        )
        self.assertTrue(any("confounded" in w for w in self.report.warnings))

    def test_a_crossed_batch_design_is_not_flagged(self) -> None:
        self._validate_metadata(GOOD_METADATA)
        self.assertFalse(any("confounded" in w for w in self.report.warnings))


class ReportTests(unittest.TestCase):
    def test_errors_fail_the_run_and_warnings_do_not(self) -> None:
        clean = validate_samplesheet.Report()
        self.assertEqual(clean.summarize(), 0)

        warned = validate_samplesheet.Report()
        warned.warn("advisory")
        self.assertEqual(warned.summarize(), 0)

        failed = validate_samplesheet.Report()
        failed.error("fatal")
        self.assertEqual(failed.summarize(), 1)


class SampleNameTests(unittest.TestCase):
    def test_common_quantifier_suffixes_are_stripped(self) -> None:
        clean = build_counts_matrix._clean_sample_name
        for raw in ("ctrl_1", "ctrl_1.bam", "ctrl_1_S1_L001"):
            with self.subTest(raw=raw):
                self.assertTrue(clean(raw).startswith("ctrl_1"))

    def test_cleaning_is_idempotent(self) -> None:
        clean = build_counts_matrix._clean_sample_name
        once = clean("ctrl_1.bam")
        self.assertEqual(clean(once), once)

    def test_the_star_strand_columns_match_the_documented_layout(self) -> None:
        # STAR's ReadsPerGene.out.tab puts unstranded/forward/reverse in
        # columns 1-3; picking the wrong one silently halves the counts.
        self.assertEqual(
            build_counts_matrix.STAR_STRAND_COL,
            {"unstranded": 1, "forward": 2, "reverse": 3},
        )


class CountsMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)

    def _star_table(self, sample: str, rows: str) -> None:
        # STAR tables sit flat in the directory, named <sample>.ReadsPerGene.out.tab.
        (self.root / f"{sample}.ReadsPerGene.out.tab").write_text(
            "N_unmapped\t1\t1\t1\n"
            "N_multimapping\t2\t2\t2\n"
            "N_noFeature\t3\t3\t3\n"
            "N_ambiguous\t4\t4\t4\n" + rows,
            encoding="utf-8",
        )

    def test_star_counts_are_assembled_from_per_sample_tables(self) -> None:
        self._star_table("ctrl_1", "GENE1\t10\t0\t0\nGENE2\t20\t0\t0\n")
        self._star_table("treat_1", "GENE1\t30\t0\t0\nGENE2\t40\t0\t0\n")

        counts = build_counts_matrix.build_from_star(self.root, "unstranded")
        self.assertEqual(sorted(counts.index), ["GENE1", "GENE2"])
        self.assertEqual(set(counts.columns), {"ctrl_1", "treat_1"})
        self.assertEqual(counts.loc["GENE1", "ctrl_1"], 10)
        self.assertEqual(counts.loc["GENE2", "treat_1"], 40)

    def test_star_summary_rows_are_excluded_from_the_gene_matrix(self) -> None:
        # The first four rows are alignment statistics, not genes; counting
        # them would inflate the library size for every sample.
        self._star_table("s1", "GENE1\t5\t0\t0\n")
        counts = build_counts_matrix.build_from_star(self.root, "unstranded")
        self.assertEqual(list(counts.index), ["GENE1"])

    def test_genes_absent_from_one_sample_become_zero_not_nan(self) -> None:
        self._star_table("s1", "GENE1\t5\t0\t0\nGENE2\t7\t0\t0\n")
        self._star_table("s2", "GENE1\t9\t0\t0\n")
        counts = build_counts_matrix.build_from_star(self.root, "unstranded")
        self.assertEqual(counts.loc["GENE2", "s2"], 0)
        self.assertEqual(str(counts.dtypes.unique()[0]), "int64")

    def test_the_strand_choice_selects_a_different_column(self) -> None:
        self._star_table("s1", "GENE1\t100\t60\t40\n")
        for strand, expected in (("unstranded", 100), ("forward", 60), ("reverse", 40)):
            with self.subTest(strand=strand):
                counts = build_counts_matrix.build_from_star(self.root, strand)
                self.assertEqual(counts.loc["GENE1", "s1"], expected)

    def test_an_empty_directory_exits_with_a_message(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            build_counts_matrix.build_from_star(self.root, "unstranded")
        self.assertIn("ReadsPerGene.out.tab", str(raised.exception))

    def test_featurecounts_output_is_reduced_to_genes_by_samples(self) -> None:
        path = self.root / "counts.txt"
        path.write_text(
            "# Program:featureCounts\n"
            "Geneid\tChr\tStart\tEnd\tStrand\tLength\tctrl_1.bam\ttreat_1.bam\n"
            "GENE1\tchr1\t1\t100\t+\t100\t10\t30\n"
            "GENE2\tchr1\t200\t300\t+\t100\t20\t40\n",
            encoding="utf-8",
        )
        counts = build_counts_matrix.build_from_featurecounts(path)
        self.assertEqual(list(counts.index), ["GENE1", "GENE2"])
        self.assertEqual(len(counts.columns), 2)
        self.assertEqual(counts.iloc[0, 0], 10)
        # The annotation columns must not survive as samples.
        self.assertFalse({"Chr", "Start", "End", "Strand", "Length"} & set(counts.columns))

    def test_outputs_are_written_where_downstream_steps_expect_them(self) -> None:
        counts = pd.DataFrame(
            {"ctrl_1": [10, 20], "treat_1": [30, 40]}, index=["GENE1", "GENE2"]
        )
        output = self.root / "out"
        build_counts_matrix.write_outputs(counts, output)
        written = sorted(path.name for path in output.iterdir())
        self.assertTrue(written, "write_outputs produced nothing")
        for name in written:
            with self.subTest(file=name):
                self.assertGreater((output / name).stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
