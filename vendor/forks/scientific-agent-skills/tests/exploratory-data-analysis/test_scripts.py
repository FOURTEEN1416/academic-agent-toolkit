#!/usr/bin/env python3
"""Synthetic, network-free behavior tests for the bounded EDA tools."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "exploratory-data-analysis"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _capabilities  # noqa: E402
import _common  # noqa: E402
import _structured  # noqa: E402
import _tabular  # noqa: E402
import capability_manifest  # noqa: E402
import eda_analyzer  # noqa: E402
import image_inspector  # noqa: E402
import report_scaffold  # noqa: E402
import sequence_inspector  # noqa: E402


class LocalSafetyTests(unittest.TestCase):
    def test_url_traversal_symlink_and_special_file_are_rejected(self) -> None:
        with self.assertRaises(_common.CliError):
            _common.checked_input_file("https://example.invalid/data.csv")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.csv"
            data.write_text("x\n1\n", encoding="utf-8")
            with self.assertRaises(_common.CliError):
                _common.checked_input_file("../data.csv", root=root)
            link = root / "link.csv"
            try:
                link.symlink_to(data)
            except OSError:
                self.skipTest("symlinks unavailable")
            with self.assertRaises(_common.CliError):
                _common.checked_input_file("link.csv", root=root)
            hardlink = root / "hardlink.csv"
            try:
                os.link(data, hardlink)
            except OSError:
                hardlink = None
            if hardlink is not None:
                with self.assertRaises(_common.CliError):
                    _common.checked_input_file("hardlink.csv", root=root)
            if hasattr(os, "mkfifo"):
                fifo = root / "special.csv"
                os.mkfifo(fifo)
                with self.assertRaises(_common.CliError):
                    _common.checked_input_file("special.csv", root=root)

    def test_private_atomic_output_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "report.json"
            _common.emit_json({"ok": True}, output="report.json", root=root)
            self.assertEqual(json.loads(output.read_text()), {"ok": True})
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            with self.assertRaises(_common.CliError):
                _common.emit_json({"ok": False}, output="report.json", root=root)

    def test_unknown_format_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unknown.bin"
            path.write_bytes(b"not guessed")
            with self.assertRaises(_common.CliError):
                _capabilities.capability_for_path(path)

    def test_size_and_npz_bomb_preflights(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.csv"
            data.write_bytes(b"x\n1\n")
            with self.assertRaises(_common.CliError):
                _common.checked_input_file(data, root=root, max_bytes=1)

            ratio_bomb = root / "ratio.npz"
            with zipfile.ZipFile(
                ratio_bomb,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.writestr("array.npy", b"\0" * 200_000)
            with self.assertRaises(_common.CliError):
                _capabilities.preflight_npz(ratio_bomb)

            traversal = root / "traversal.npz"
            with zipfile.ZipFile(traversal, "w") as archive:
                archive.writestr("../array.npy", b"not-an-array")
            with self.assertRaises(_common.CliError):
                _capabilities.preflight_npz(traversal)

    def test_capability_matrix_separates_reference_only(self) -> None:
        matrix = capability_manifest.capability_matrix()
        automated = {row["suffix"] for row in matrix["automated"]}
        reference_only = {row["suffix"] for row in matrix["reference_only"]}
        self.assertIn(".csv", automated)
        self.assertIn(".ome.tiff", automated)
        self.assertIn(".pdb", reference_only)
        self.assertIn(".mzml", reference_only)
        self.assertFalse(automated & reference_only)
        for row in [*matrix["automated"], *matrix["reference_only"]]:
            self.assertTrue((SKILL_ROOT / row["reference"]).is_file())

    def test_text_manifest_does_not_claim_a_signature_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.csv"
            path.write_text("x\n1\n", encoding="utf-8")
            report = capability_manifest.inspect_manifest(
                path,
                max_bytes=_common.DEFAULT_MAX_FILE_BYTES,
            )
        self.assertFalse(report["inspection"]["format_signature_checked"])


class TabularTests(unittest.TestCase):
    def _write_table(self, root: Path) -> Path:
        path = root / "study.csv"
        path.write_text(
            "private_subject,private_group,private_split,private_time,"
            "private_measurement,private_aux\n"
            "subject-secret-1,group-secret-a,train,2026-01-01T00:00:00,1,\n"
            "subject-secret-1,group-secret-a,test,2026-01-01T00:00:00,1,\n"
            "subject-secret-2,group-secret-b,test,2026-01-02T00:00:00,2,4\n"
            "subject-secret-3,group-secret-b,test,2026-01-03T00:00:00,100,NA\n",
            encoding="utf-8",
        )
        return path

    def test_profile_is_bounded_aggregate_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_table(Path(directory))
            report = _tabular.profile_table(
                path,
                max_rows=3,
                missing_tokens=["NA"],
            )
        serialized = json.dumps(report, sort_keys=True)
        self.assertEqual(report["rows_scanned"], 3)
        self.assertTrue(report["row_limit_reached"])
        self.assertNotIn("private_subject", serialized)
        self.assertNotIn("subject-secret", serialized)
        self.assertNotIn("group-secret", serialized)
        self.assertFalse(report["raw_values_emitted"])

    def test_missingness_and_leakage_flags_overlap_without_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_table(Path(directory))
            report = _tabular.audit_missingness_and_leakage(
                path,
                missing_tokens=["NA"],
                group_column="private_group",
                entity_column="private_subject",
                split_column="private_split",
                time_column="private_time",
            )
        leakage = report["leakage_audit"]
        self.assertEqual(leakage["entity_tokens_in_multiple_splits"], 1)
        self.assertEqual(leakage["group_tokens_in_multiple_splits"], 1)
        self.assertEqual(leakage["identical_row_hashes_in_multiple_splits"], 1)
        self.assertEqual(leakage["status"], "potential_leakage_detected")
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("subject-secret", serialized)
        self.assertNotIn("group-secret", serialized)

    def test_distribution_report_flags_outlier_but_changes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_table(Path(directory))
            report = _tabular.audit_distributions(
                path,
                columns=["private_measurement"],
            )
        self.assertEqual(report["numeric_columns_reported"], 1)
        sensitivity = report["columns"][0]["outlier_sensitivity"]
        self.assertEqual(sensitivity["outside_iqr_fence_count_in_sample"], 1)
        self.assertTrue(sensitivity["values_were_not_deleted_or_modified"])
        self.assertFalse(report["raw_values_emitted"])


class StructuredFormatTests(unittest.TestCase):
    def test_strict_json_rejects_duplicates_and_nonfinite_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"x": 1, "x": 2}', encoding="utf-8")
            nonfinite = root / "nonfinite.json"
            nonfinite.write_text('{"x": NaN}', encoding="utf-8")
            with self.assertRaises(_common.CliError):
                _structured.inspect_json(duplicate)
            with self.assertRaises(_common.CliError):
                _structured.inspect_json(nonfinite)

    def test_json_profile_emits_structure_not_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text(
                '{"secret_field": [{"value": "secret-value"}, null]}',
                encoding="utf-8",
            )
            report = _structured.inspect_json(path)
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("secret_field", serialized)
        self.assertNotIn("secret-value", serialized)
        self.assertEqual(report["type_counts"]["object"], 2)

    def test_numpy_npy_npz_and_object_rejection_when_available(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("NumPy not installed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            npy = root / "array.npy"
            np.save(npy, np.arange(12, dtype=np.float64).reshape(3, 4))
            report = _structured.inspect_numpy(npy, suffix=".npy")
            self.assertEqual(report["array"]["shape"], [3, 4])
            self.assertFalse(report["pickle_allowed"])

            npz = root / "arrays.npz"
            np.savez_compressed(npz, secret_name=np.arange(4))
            archive = _structured.inspect_numpy(npz, suffix=".npz")
            self.assertEqual(archive["archive_preflight"]["member_count"], 1)
            self.assertNotIn("secret_name", json.dumps(archive))

            unsafe = root / "object.npy"
            np.save(unsafe, np.array([{"unsafe": True}], dtype=object))
            with self.assertRaises(_common.CliError):
                _structured.inspect_numpy(unsafe, suffix=".npy")

    def test_hdf5_external_link_is_not_followed_when_available(self) -> None:
        try:
            import h5py
        except ImportError:
            self.skipTest("h5py not installed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / "external.h5"
            with h5py.File(external, "w") as handle:
                handle.create_dataset("secret_external", data=[1, 2, 3])
            source = root / "source.h5"
            with h5py.File(source, "w") as handle:
                handle.create_dataset("local_secret", data=[1, 2])
                handle["external_secret"] = h5py.ExternalLink(
                    "external.h5",
                    "/secret_external",
                )
            report = _structured.inspect_hdf5(source)
        self.assertEqual(report["links"]["external_not_followed"], 1)
        self.assertFalse(report["external_links_followed"])
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("external.h5", serialized)
        self.assertNotIn("local_secret", serialized)


class SequenceAndImageTests(unittest.TestCase):
    def test_fasta_and_fastq_are_aggregate_only_when_available(self) -> None:
        try:
            import Bio  # noqa: F401
        except ImportError:
            self.skipTest("Biopython not installed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fasta = root / "reads.fasta"
            fasta.write_text(
                ">private-sequence-id\nACGTNN\n>another-private-id\nGGCC\n",
                encoding="ascii",
            )
            report = sequence_inspector.inspect_sequence_file(
                fasta,
                suffix=".fasta",
            )
            self.assertEqual(report["records_inspected"], 2)
            self.assertNotIn("private-sequence-id", json.dumps(report))
            self.assertFalse(report["sequence_values_emitted"])

            fastq = root / "reads.fastq"
            fastq.write_text(
                "@private-read\nACGT\n+\nIIII\n",
                encoding="ascii",
            )
            quality = sequence_inspector.inspect_sequence_file(
                fastq,
                suffix=".fastq",
            )
            self.assertEqual(quality["quality_aggregates"]["mean"], 40.0)

    def test_png_metadata_does_not_decode_pixels_when_available(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            Image.new("L", (8, 4), 7).save(path)
            report = image_inspector.inspect_image_file(path, suffix=".png")
        self.assertEqual(report["width_pixels"], 8)
        self.assertEqual(report["height_pixels"], 4)
        self.assertFalse(report["pixels_decoded"])

    def test_tiff_metadata_when_available(self) -> None:
        try:
            import numpy as np
            import tifffile
        except ImportError:
            self.skipTest("NumPy/tifffile not installed")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.ome.tiff"
            tifffile.imwrite(
                path,
                np.zeros((4, 4), dtype=np.uint8),
                metadata={"axes": "YX"},
                ome=True,
            )
            report = image_inspector.inspect_image_file(
                path,
                suffix=".ome.tiff",
            )
        self.assertTrue(report["is_ome_tiff"])
        self.assertFalse(report["pixels_decoded"])
        self.assertFalse(report["ome_xml_emitted"])


class AnalyzerAndScaffoldTests(unittest.TestCase):
    def test_analyzer_report_is_redacted_and_rigorous(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "private-name.csv"
            path.write_text(
                "private-column\nsecret-cell-value\n",
                encoding="utf-8",
            )
            checked = _common.checked_input_file(
                path,
                root=root,
                suffixes={".csv"},
            )
            report = eda_analyzer.build_report(
                checked,
                max_bytes=_common.DEFAULT_MAX_FILE_BYTES,
            )
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("private-name", serialized)
        self.assertNotIn("private-column", serialized)
        self.assertNotIn("secret-cell-value", serialized)
        self.assertFalse(report["eda_guardrails"]["automatic_imputation"])
        self.assertFalse(report["eda_guardrails"]["causal_claims"])

    def test_reference_only_analyzer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "structure.pdb"
            path.write_text("HEADER\n", encoding="ascii")
            with self.assertRaises(_common.CliError):
                eda_analyzer.build_report(
                    path,
                    max_bytes=_common.DEFAULT_MAX_FILE_BYTES,
                )

    def test_report_scaffold_has_no_full_path_or_unfilled_manifest_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "private.csv"
            path.write_text("x\n1\n", encoding="utf-8")
            manifest = capability_manifest.inspect_manifest(
                path,
                max_bytes=_common.DEFAULT_MAX_FILE_BYTES,
            )
            report = report_scaffold.render_scaffold(
                analysis_date="2026-07-23",
                manifest=manifest,
            )
        self.assertNotIn(str(path), report)
        self.assertNotIn("private.csv", report)
        self.assertNotIn("{FILE_ID}", report)
        self.assertIn("Exploratory / hypothesis-generating", report)


if __name__ == "__main__":
    unittest.main()
