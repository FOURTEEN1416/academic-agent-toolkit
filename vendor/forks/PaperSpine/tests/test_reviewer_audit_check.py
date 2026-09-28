"""Tests for reviewer_audit_check.py (reviewer-aware audit gate)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "scripts" / "reviewer_audit_check.py"


VALUE_MAP = """## Reviewer Value Map

| Reviewer criterion | What reviewers want | Our evidence | Current weakness | Revision action |
|---|---|---|---|---|
| Novelty | Defensible delta vs closest prior work. | Sec. 1 bullets | Implied not stated | Add one delta sentence. |
| Significance | Evidence the gain matters. | Sec. 4 effect size | Asserted not quantified | Quantify the stakes. |
| Technical soundness | Correct, justified methods. | Sec. 3 derivation | One assumption undefended | Justify each assumption. |
| Evidence sufficiency | Enough ablations/baselines. | Tables 2-3 | Missing one baseline | Add the baseline. |
| Clarity | Readable in one pass. | Section flow | Claim split across sections | Consolidate the claim. |
| Venue fit | Matches the venue. | Target-venue analysis | Framing off-community | Reframe the intro. |
"""

OBJECTION = """## Reviewer Objection Register

| Likely objection | Where triggered | Severity | What the reviewer may say | Preemptive fix | Status |
|---|---|---|---|---|---|
| Contribution overlaps prior work | Sec. 1 | CRITICAL | "This is incremental." | Add delta sentence + Table 1 row. | OPEN |
| Missing baseline | Sec. 4 | MAJOR | "Why no comparison?" | Add the baseline or scope it out. | OPEN |
"""

EDITORIAL = """## Editorial Fit Map

- Venue fit: Targets venue Y; scope and methods match its typical papers.
- Editor-facing value: A serving-cost reduction an editor can defend to the board.
- Desk-reject risks: Length within limit (resolved); ethics section present (resolved).
"""


def _doc(*parts: str) -> str:
    return "# Reviewer Audit\n\n" + "\n".join(parts)


def _write_audit(text: str | None) -> Path:
    tmp = Path(tempfile.mkdtemp())
    if text is not None:
        (tmp / "reviewer_audit.md").write_text(text, encoding="utf-8")
    return tmp


def _run(out_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(out_dir), "--markdown"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class ReviewerAuditCheckTests(unittest.TestCase):
    def test_complete_audit_passes(self) -> None:
        out = _write_audit(_doc(VALUE_MAP, OBJECTION, EDITORIAL))
        res = _run(out)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("Status: PASS", res.stdout)

    def test_missing_file_fails(self) -> None:
        out = _write_audit(None)
        res = _run(out)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("does not exist", res.stdout)

    def test_missing_editorial_section_fails(self) -> None:
        out = _write_audit(_doc(VALUE_MAP, OBJECTION))
        res = _run(out)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("Editorial Fit Map", res.stdout)

    def test_value_map_missing_criterion_fails(self) -> None:
        # Drop the "Venue fit" row -> only five of six criteria present.
        five_row_map = "\n".join(
            ln for ln in VALUE_MAP.splitlines() if not ln.startswith("| Venue fit")
        ) + "\n"
        out = _write_audit(_doc(five_row_map, OBJECTION, EDITORIAL))
        res = _run(out)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("venue fit", res.stdout.lower())

    def test_objection_without_severity_and_fix_fails(self) -> None:
        # Objection register present but the row carries neither Severity nor fix.
        bad_objection = (
            "## Reviewer Objection Register\n\n"
            "| Likely objection | Where triggered | Severity | Preemptive fix |\n"
            "|---|---|---|---|\n"
            "| Some objection | Sec. 1 |  |  |\n"
        )
        out = _write_audit(_doc(VALUE_MAP, bad_objection, EDITORIAL))
        res = _run(out)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
