"""Tests for submission_check.py (V4 single-skill feature script).

Exercises the real subprocess so the actual CLI contract is covered:
  * an English-only package must PASS without demanding any .zh deliverables;
  * a missing highlights file must FAIL;
  * plain pandoc docx (no Times New Roman font) must not be failed solely on
    fonts — font/geometry policy is advisory in V4.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "scripts" / "submission_check.py"

COVER_EN = (
    "Dear Editor,\n\n"
    "We are pleased to submit our manuscript for consideration in your journal. "
    "This work is entirely original and has not been previously published in any "
    "form, in whole or in part. The manuscript is not under consideration at any "
    "other journal, and it has not been submitted elsewhere for review. All listed "
    "authors have read and approved the final version and agree to the submission. "
    "The study presents a lightweight method for improving document conversion "
    "fidelity, together with a reproducible evaluation pipeline and a compact, "
    "well documented configuration that other groups can adopt with little effort. "
    "We believe the results will be of interest to your readership because they "
    "address a recurring practical problem with a simple and inexpensive solution. "
    "We confirm that there are no conflicts of interest to declare, and that the "
    "data and materials needed to reproduce our findings will be made available "
    "upon reasonable request. We have followed the formatting and ethical "
    "guidelines described in the author instructions, and we have taken care to "
    "ensure that every claim in the manuscript is supported by the evidence we "
    "report. Thank you very much for considering our submission. We look forward "
    "to your editorial decision and to the comments of the reviewers, which we are "
    "confident will help us strengthen the final paper.\n\n"
    "Sincerely,\nThe Authors\n"
)

HIGHLIGHTS_EN = (
    "# Highlights\n\n"
    "- We propose a lightweight method for document conversion fidelity.\n"
    "- The approach improves accuracy on held-out benchmark documents.\n"
    "- Our pipeline is fully reproducible and inexpensive to run.\n"
    "- The configuration is compact and easy for other groups to adopt.\n"
)

CONFIG_EN = {
    "output_language": "en",
    "translation_package": "none",
}


def make_docx(path: Path, paragraphs: list[str]) -> None:
    """Write a minimal, structurally valid docx with no font/geometry hints.

    This mirrors what plain ``pandoc`` produces before ``word_guard
    --fix-fonts`` runs: valid parts and readable text, but no rFonts/sectPr.
    """
    body = "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    types = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>'
    with zipfile.ZipFile(path, "w") as docx:
        docx.writestr("[Content_Types].xml", types)
        docx.writestr("word/document.xml", document)


def write_en_package(directory: Path) -> Path:
    pkg = directory / "submission_package"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "paper_spine_config.json").write_text(
        json.dumps(CONFIG_EN), encoding="utf-8"
    )
    (pkg / "highlights.en.md").write_text(HIGHLIGHTS_EN, encoding="utf-8")
    (pkg / "cover_letter.en.md").write_text(COVER_EN, encoding="utf-8")
    make_docx(
        pkg / "cover_letter.en.docx",
        ["Dear Editor, this manuscript is original and not under consideration "
         "elsewhere. " * 6],
    )
    make_docx(
        pkg / "highlights.en.docx",
        ["We propose a lightweight method for document conversion fidelity. " * 6],
    )
    return pkg


def run(pkg: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(pkg), "--json"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )


class SubmissionCheckTests(unittest.TestCase):
    def test_en_only_package_passes_without_zh_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = write_en_package(Path(tmp))
            result = run(pkg)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            # No finding may mention a .zh deliverable for an EN-only run.
            for finding in payload["findings"]:
                self.assertNotIn(".zh", finding, f"unexpected zh demand: {finding}")
            self.assertEqual(payload["language"], "en")

    def test_missing_highlights_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = write_en_package(Path(tmp))
            (pkg / "highlights.en.md").unlink()
            result = run(pkg)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(
                any("highlights.en.md" in f and "missing" in f.lower()
                    for f in payload["findings"]),
                payload["findings"],
            )

    def test_plain_pandoc_docx_not_failed_on_fonts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = write_en_package(Path(tmp))
            result = run(pkg)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            # Font mismatch must never appear as a blocking finding.
            for finding in payload["findings"]:
                self.assertNotIn("Times New Roman", finding)
            # It is acceptable (and expected) as an advisory warning instead.
            self.assertTrue(
                any("Times New Roman" in w for w in payload["warnings"]),
                "expected an advisory font warning for plain pandoc docx",
            )


if __name__ == "__main__":
    unittest.main()
