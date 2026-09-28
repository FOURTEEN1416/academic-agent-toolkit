"""Tests for respond_check.py (V4 single-skill feature script).

Key behaviours covered against the real subprocess:
  * an unanswered C1 must FAIL even when C10/C11 are present — word-boundary
    matching must not treat "C1" as satisfied by the substring inside "C10";
  * a complete response package PASSes;
  * an empty Response Draft / Status cell FAILs.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "scripts" / "respond_check.py"

MATRIX_HEADER = (
    "| Comment ID | Reviewer | Original Comment | Issue Type | Required Action "
    "| Manuscript Change | Evidence | Response Draft | Status |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def _matrix_row(cid: str, status: str = "final", response: str | None = None) -> str:
    resp = response if response is not None else (
        f"In response to {cid} we revised the relevant passage accordingly"
    )
    return (
        f"| {cid} | R1 | The reviewer raised a concern | clarity "
        f"| revise the text | We rewrote the relevant section | Sec 1 "
        f"| {resp} | {status} |\n"
    )


def _letter(cids: list[str]) -> str:
    refs = " ".join(
        f"Regarding comment {c}, we have carefully revised the manuscript and "
        f"added the clarification the reviewer requested." for c in cids
    )
    return (
        "Dear Editor and Reviewers,\n\n"
        "We thank you for the detailed and constructive feedback on our "
        "manuscript. We have addressed every comment in turn and summarise the "
        "main changes below. " + refs + " We believe these revisions have "
        "substantially strengthened the paper, improving both its clarity and "
        "the rigour of the supporting evidence. We have also re-read the entire "
        "manuscript to ensure the changes integrate smoothly with the "
        "surrounding text and that no new inconsistencies were introduced. "
        "In addition, we revised the abstract and the conclusion so that they "
        "accurately reflect the updated experiments, and we double checked every "
        "table and figure caption against the revised numbers reported in the "
        "main body of the manuscript. Where the reviewers asked for additional "
        "experiments, we ran them on the held out evaluation set and added the "
        "corresponding rows to the results section, along with a short "
        "discussion of what the new measurements imply for our central claims. "
        "Thank you again for the time and care you devoted to our submission.\n\n"
        "Sincerely,\nThe Authors\n"
    )


def write_package(
    directory: Path,
    *,
    extracted_ids: list[str],
    matrix_rows: list[str],
    letter_ids: list[str],
) -> Path:
    pkg = directory / "review_response"
    pkg.mkdir(parents=True, exist_ok=True)

    extracted = "# Extracted Reviewer Comments\n\n" + "\n".join(
        f"- {cid}: the reviewer raised a specific concern about the work."
        for cid in extracted_ids
    ) + "\n"
    (pkg / "reviewer_comments_extracted.md").write_text(extracted, encoding="utf-8")

    matrix = "# Response Matrix\n\n" + MATRIX_HEADER + "".join(matrix_rows)
    (pkg / "response_matrix.md").write_text(matrix, encoding="utf-8")

    (pkg / "response_letter.md").write_text(_letter(letter_ids), encoding="utf-8")

    (pkg / "revision_change_log.md").write_text(
        "# Revision Change Log\n\n"
        "All revisions described above were applied directly to "
        "final_paper/main.tex.\n",
        encoding="utf-8",
    )
    return pkg


def run(pkg: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(pkg), "--json"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )


class RespondCheckTests(unittest.TestCase):
    def test_unanswered_c1_with_c10_c11_present_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = write_package(
                Path(tmp),
                extracted_ids=["C1", "C10", "C11"],
                matrix_rows=[_matrix_row("C10"), _matrix_row("C11")],
                letter_ids=["C10", "C11"],
            )
            result = run(pkg)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            # C1 must be reported missing; C10/C11 must NOT be (no substring
            # false-positive where "C10"/"C11" satisfy "C1").
            self.assertIn("C1", payload["missing_comments"])
            self.assertNotIn("C10", payload["missing_comments"])
            self.assertNotIn("C11", payload["missing_comments"])

    def test_complete_response_package_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = write_package(
                Path(tmp),
                extracted_ids=["C1", "C2"],
                matrix_rows=[_matrix_row("C1"), _matrix_row("C2")],
                letter_ids=["C1", "C2"],
            )
            result = run(pkg)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload["findings"])
            self.assertEqual(payload["missing_comments"], [])
            self.assertEqual(payload["comment_count"], 2)

    def test_empty_status_cell_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = write_package(
                Path(tmp),
                extracted_ids=["C1"],
                matrix_rows=[_matrix_row("C1", status=" ")],
                letter_ids=["C1"],
            )
            result = run(pkg)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(
                any("empty Status cell" in f for f in payload["findings"]),
                payload["findings"],
            )

    def test_empty_response_cell_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = write_package(
                Path(tmp),
                extracted_ids=["C1"],
                matrix_rows=[_matrix_row("C1", response="  ")],
                letter_ids=["C1"],
            )
            result = run(pkg)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(
                any("empty Response Draft cell" in f for f in payload["findings"]),
                payload["findings"],
            )


if __name__ == "__main__":
    unittest.main()
