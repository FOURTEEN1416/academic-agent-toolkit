"""Tests for the xlsx skill's recalculation helper.

The shared `office/` tree is covered by the contract. What is specific here is
`recalc`, which drives LibreOffice to recompute formulas -- and the safety
check in front of it.

That check is the interesting part. Recalculating a workbook whose formulas
point at *other* workbooks, when those workbooks are unavailable, replaces
cached values with errors: the recalculation destroys the only copy of the
numbers. `external_links_at_risk` is what stops that, so the tests build real
workbooks with openpyxl and assert on exactly which cells it names.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "xlsx"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

openpyxl = pytest.importorskip("openpyxl", reason="xlsx scripts need openpyxl")

import recalc  # noqa: E402

OfficeTests = skill_contract.office.office_test_case(SKILL_ROOT)


class CommandLineTests(unittest.TestCase):
    """`recalc.py` reads `sys.argv` directly, so it has no argparse `--help`."""

    def _run(self, *args: str):
        import os
        import subprocess

        return subprocess.run(
            [sys.executable, str(SCRIPTS / "recalc.py"), *args],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_no_arguments_prints_usage(self) -> None:
        result = self._run()
        self.assertIn("Usage: python recalc.py", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_the_usage_text_documents_the_force_flag(self) -> None:
        # --force is the escape hatch past the external-link guard; it has to
        # be discoverable or people will not know the guard can be overridden.
        self.assertIn("--force", self._run().stdout)


class ExternalReferencePatternTests(unittest.TestCase):
    """`EXTERNAL_REF_RE` decides which formulas count as reaching outside."""

    def test_bracketed_workbook_references_match(self) -> None:
        for formula in (
            "=[1]Sheet1!A1",
            "='[1]Some Sheet'!A1",
            "=SUM([2]Data!A1:A9)",
        ):
            with self.subTest(formula=formula):
                self.assertTrue(recalc.EXTERNAL_REF_RE.search(formula), formula)

    def test_ordinary_local_formulas_do_not_match(self) -> None:
        for formula in (
            "=A1+B2",
            "=SUM(Sheet2!A1:A9)",
            "=IF(A1>0,1,0)",
            '=CONCATENATE("[1]",A1)',
            "=INDEX(Table1[Column],1)",
        ):
            with self.subTest(formula=formula):
                self.assertIsNone(recalc.EXTERNAL_REF_RE.search(formula), formula)

    def test_the_reported_location_cap_is_positive(self) -> None:
        self.assertGreater(recalc.MAX_LOCATIONS, 0)


class WorkbookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)

    def workbook(self, name: str = "book.xlsx", **cells) -> Path:
        book = openpyxl.Workbook()
        sheet = book.active
        sheet.title = "Data"
        for coordinate, value in cells.items():
            sheet[coordinate] = value
        path = self.root / name
        book.save(path)
        book.close()
        return path


class ExternalLinkRiskTests(WorkbookTestCase):
    def test_a_workbook_with_no_external_links_is_never_at_risk(self) -> None:
        path = self.workbook(A1=1, A2=2, A3="=SUM(A1:A2)")
        self.assertEqual(recalc.external_links_at_risk(path), [])

    def test_a_non_workbook_file_is_reported_as_no_risk_rather_than_raising(self) -> None:
        path = self.root / "not-a-workbook.xlsx"
        path.write_bytes(b"definitely not a zip")
        self.assertEqual(recalc.external_links_at_risk(path), [])

    def test_a_missing_file_is_reported_as_no_risk(self) -> None:
        self.assertEqual(
            recalc.external_links_at_risk(self.root / "absent.xlsx"), []
        )

    def test_the_check_reads_the_package_without_modifying_it(self) -> None:
        path = self.workbook(A1=1, A2="=A1*2")
        before = path.read_bytes()
        recalc.external_links_at_risk(path)
        self.assertEqual(path.read_bytes(), before)

    def test_a_workbook_without_the_external_links_part_short_circuits(self) -> None:
        # The function returns early unless xl/externalLinks/ exists, so the
        # common case never pays for two full workbook loads.
        path = self.workbook(A1=1)
        with zipfile.ZipFile(path) as archive:
            self.assertFalse(
                any(name.startswith("xl/externalLinks/") for name in archive.namelist())
            )
        self.assertEqual(recalc.external_links_at_risk(path), [])


class MacroSetupTests(WorkbookTestCase):
    def test_the_macro_module_is_written_into_the_profile(self) -> None:
        profile = self.root / "profile"
        recalc.setup_libreoffice_macro(profile)
        module = profile / "user" / "basic" / "Standard" / recalc.MACRO_FILENAME
        self.assertTrue(module.is_file(), "macro module was not written")
        self.assertIn("Recalculate", module.read_text(encoding="utf-8"))

    def test_the_macro_xml_is_well_formed(self) -> None:
        import defusedxml.ElementTree as ElementTree

        ElementTree.fromstring(recalc.RECALCULATE_MACRO)

    def test_setup_is_idempotent(self) -> None:
        profile = self.root / "profile"
        recalc.setup_libreoffice_macro(profile)
        first = (profile / "user" / "basic" / "Standard" / recalc.MACRO_FILENAME).read_bytes()
        recalc.setup_libreoffice_macro(profile)
        second = (profile / "user" / "basic" / "Standard" / recalc.MACRO_FILENAME).read_bytes()
        self.assertEqual(first, second)


class RecalcGuardTests(WorkbookTestCase):
    def test_a_missing_soffice_is_reported_clearly(self) -> None:
        import shutil

        if shutil.which("soffice"):
            self.skipTest("LibreOffice is installed; this asserts the absent path")
        path = self.workbook(A1=1, A2="=A1*2")
        result = recalc.recalc(path)
        self.assertIn("soffice", str(result).lower())

    def test_the_missing_soffice_message_names_libreoffice(self) -> None:
        self.assertIn("LibreOffice", recalc.SOFFICE_MISSING)

    def test_the_timestamp_helper_reports_a_files_mtime(self) -> None:
        path = self.workbook(A1=1)
        self.assertEqual(recalc._stamp(path), recalc._stamp(path))
        self.assertIsNotNone(recalc._stamp(path))

    def test_the_timeout_helper_answers_without_raising(self) -> None:
        self.assertIn(recalc.has_gtimeout(), (True, False))


if __name__ == "__main__":
    unittest.main()
