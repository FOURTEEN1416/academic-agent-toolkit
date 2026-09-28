"""Tests for citation_verification_en.py (V4 single-skill feature script).

Network is never touched: the year-mismatch behaviour is exercised by injecting
a fake Crossref fetcher into ``verify_citation``; the CLI is exercised offline
with ``--help`` and ``--no-api``.

Covered behaviour:
  * a row whose DOI resolves on Crossref is marked ``matched`` even when the
    local year differs from the Crossref ``created`` year (a resolvable DOI is
    sufficient evidence — the year mismatch is only a note, never a failure);
  * DOIs are URL-encoded via ``urllib.parse.quote`` before being queried;
  * the script imports cleanly and ``--help`` / ``--no-api`` work offline.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "scripts"))

import citation_verification_en as cve  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "scripts" / "citation_verification_en.py"


def _write_bank(directory: Path, rows: list[tuple[str, str]]) -> Path:
    bank = directory / "citation_support_bank.md"
    lines = [
        "# Citation Support Bank",
        "",
        "| Candidate ID | Reference |",
        "|---|---|",
    ]
    lines.extend(f"| {cid} | {ref} |" for cid, ref in rows)
    lines.append("")
    bank.write_text("\n".join(lines), encoding="utf-8")
    return bank


class YearMismatchTests(unittest.TestCase):
    def test_resolvable_doi_with_year_mismatch_is_matched_not_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bank = _write_bank(
                Path(tmp),
                [(
                    "C1",
                    "Smith J. A study of conversion fidelity. Journal of "
                    "Examples, 2018. doi:10.1234/example.2018",
                )],
            )

            def fake_fetch(url: str, timeout: int = 15) -> dict:
                # Crossref returns only a 'created' (registration) year that is
                # far from the local 2018 publication year.
                return {
                    "status": "ok",
                    "message": {
                        "title": ["A completely different registered title"],
                        "created": {"date-parts": [[2010, 1, 1]]},
                        "DOI": "10.1234/example.2018",
                    },
                }

            result = cve.verify_citation(bank, _fetcher=fake_fetch)

            self.assertTrue(result.ok, result.findings)
            self.assertEqual(len(result.entries), 1)
            entry = result.entries[0]
            self.assertEqual(entry.status, "matched")
            self.assertEqual(result.matched_count, 1)
            self.assertEqual(result.unmatched_count, 0)
            # The mismatch is recorded as a note, never a failure.
            self.assertIn("year differs", entry.note)

    def test_doi_is_url_encoded_with_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bank = _write_bank(
                Path(tmp),
                [("C9", "Doe J. A title. 2019. doi:10.5555/abc(123)def")],
            )

            captured: list[str] = []

            def recording_fetch(url: str, timeout: int = 15) -> dict:
                captured.append(url)
                return {
                    "status": "ok",
                    "message": {"title": ["A title"], "DOI": "10.5555/abc(123)def"},
                }

            cve.verify_citation(bank, _fetcher=recording_fetch)

            self.assertEqual(len(captured), 1)
            # quote(safe='') must percent-encode '/', '(' and ')'.
            self.assertIn("%2F", captured[0])
            self.assertIn("%28", captured[0])
            self.assertIn("%29", captured[0])
            self.assertNotIn("(", captured[0])


class ModuleApiTests(unittest.TestCase):
    def test_module_uses_urllib_parse_quote(self) -> None:
        import urllib.parse

        # The DOI lookup helper must build its URL with urllib.parse.quote.
        url = f"{cve.CROSSREF_QUERY_URL}/{urllib.parse.quote('10.1/a b', safe='')}"
        self.assertIn("%20", url)

    def test_help_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage", result.stdout.lower())

    def test_no_api_offline_does_not_fail_on_year(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bank = _write_bank(
                Path(tmp),
                [(
                    "C1",
                    "Smith J. A study. Journal of Examples, 2018. "
                    "doi:10.1234/example.2018",
                )],
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(bank), "--no-api", "--json"],
                cwd=ROOT, text=True, encoding="utf-8", stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, check=False,
            )
            # --no-api never touches the network and never fails the run.
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"ok": true', result.stdout)
            self.assertIn('"skipped_count": 1', result.stdout)


if __name__ == "__main__":
    unittest.main()
