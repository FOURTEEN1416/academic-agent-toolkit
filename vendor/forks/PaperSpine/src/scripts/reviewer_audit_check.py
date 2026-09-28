#!/usr/bin/env python3
"""Validate PaperSpine reviewer_audit.md (the reviewer-aware differentiator).

Checks that paper_rewriting_output/reviewer_audit.md exists and that its three
sections are present and non-empty:

1. Reviewer Value Map — must carry all six fixed criterion rows
   (Novelty, Significance, Technical soundness, Evidence sufficiency, Clarity,
   Venue fit).
2. Reviewer Objection Register — must have >=1 data row that carries both a
   Severity and a Preemptive fix.
3. Editorial Fit Map — must be present with non-empty body content.

word_guard-style CLI: output_dir positional + --json/--markdown/--write,
to_markdown(), exit 0 on PASS / 1 on FAIL. Reuses _paper_spine_utils for table
parsing instead of re-implementing it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paper_spine_utils import table_rows

# The six criteria are fixed because they are the axes nearly every venue's
# review form scores. The audit is incomplete if any are missing.
REQUIRED_CRITERIA = (
    "novelty",
    "significance",
    "technical soundness",
    "evidence sufficiency",
    "clarity",
    "venue fit",
)

# Headings that anchor each of the three sections. Matched case-insensitively on
# the heading text so authors can use any markdown level (##, ###).
VALUE_MAP_HEADING = "reviewer value map"
OBJECTION_HEADING = "reviewer objection register"
EDITORIAL_HEADING = "editorial fit map"


@dataclass
class ReviewerAuditResult:
    path: str
    ok: bool
    value_map_ok: bool = False
    objection_register_ok: bool = False
    editorial_fit_ok: bool = False
    found_criteria: list[str] = field(default_factory=list)
    missing_criteria: list[str] = field(default_factory=list)
    objection_row_count: int = 0
    findings: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate PaperSpine reviewer_audit.md (reviewer-aware audit)."
    )
    parser.add_argument(
        "output_dir", nargs="?",
        default="paper_rewriting_output",
        help="Directory containing reviewer_audit.md (default: paper_rewriting_output).",
    )
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true",
                        help="Write reviewer_audit_check.md next to reviewer_audit.md.")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# section slicing
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")


def section_body(text: str, heading_substring: str) -> str | None:
    """Return the body text under the first heading containing *heading_substring*.

    The body runs from just after the matched heading line up to (but not
    including) the next heading of the same-or-shallower level. Returns None when
    no matching heading exists.
    """
    lines = text.splitlines()
    start_idx: int | None = None
    start_level = 0
    target = heading_substring.lower()
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if not m:
            continue
        if target in m.group(1).strip().lower():
            start_idx = i
            start_level = _heading_level(line)
            break
    if start_idx is None:
        return None
    body: list[str] = []
    for line in lines[start_idx + 1:]:
        m = HEADING_RE.match(line)
        if m and _heading_level(line) <= start_level:
            break
        body.append(line)
    return "\n".join(body)


def _heading_level(line: str) -> int:
    stripped = line.lstrip()
    count = 0
    for ch in stripped:
        if ch == "#":
            count += 1
        else:
            break
    return count


def _table_data_rows(body: str) -> list[list[str]]:
    """Return non-empty markdown table data rows from *body*."""
    _, rows = table_rows(body)
    return [r for r in rows if any(cell.strip() for cell in r)]


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def check_value_map(body: str | None, result: ReviewerAuditResult) -> None:
    if body is None:
        result.findings.append(
            "Missing 'Reviewer Value Map' section. The audit must score the six "
            "reviewer criteria (Novelty, Significance, Technical soundness, "
            "Evidence sufficiency, Clarity, Venue fit)."
        )
        result.missing_criteria = list(REQUIRED_CRITERIA)
        return
    rows = _table_data_rows(body)
    if not rows:
        result.findings.append("Reviewer Value Map section has no table rows.")
        result.missing_criteria = list(REQUIRED_CRITERIA)
        return
    # First-column text of every row, lowercased, for criterion matching.
    first_cells = " \n ".join(row[0].lower() for row in rows if row)
    found: list[str] = []
    missing: list[str] = []
    for criterion in REQUIRED_CRITERIA:
        if criterion in first_cells:
            found.append(criterion)
        else:
            missing.append(criterion)
    result.found_criteria = found
    result.missing_criteria = missing
    if missing:
        result.findings.append(
            "Reviewer Value Map is missing required criterion rows: "
            + ", ".join(missing)
            + ". All six criteria must each have a row."
        )
    else:
        result.value_map_ok = True


def check_objection_register(body: str | None, result: ReviewerAuditResult) -> None:
    if body is None:
        result.findings.append(
            "Missing 'Reviewer Objection Register' section. List the likely "
            "reviewer objections with a Severity and a Preemptive fix for each."
        )
        return
    header, rows = table_rows(body)
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    result.objection_row_count = len(rows)
    if not rows:
        result.findings.append(
            "Reviewer Objection Register has no objection rows. Add at least one "
            "row with a Severity and a Preemptive fix."
        )
        return
    header_lower = [c.lower() for c in header]
    sev_idx = next((i for i, c in enumerate(header_lower) if "severity" in c), None)
    fix_idx = next(
        (i for i, c in enumerate(header_lower) if "fix" in c or "preemptive" in c),
        None,
    )
    if sev_idx is None:
        result.findings.append(
            "Reviewer Objection Register table needs a 'Severity' column."
        )
    if fix_idx is None:
        result.findings.append(
            "Reviewer Objection Register table needs a 'Preemptive fix' column."
        )
    if sev_idx is None or fix_idx is None:
        return
    usable = 0
    for row in rows:
        if sev_idx < len(row) and fix_idx < len(row):
            if row[sev_idx].strip() and row[fix_idx].strip():
                usable += 1
    if usable == 0:
        result.findings.append(
            "Reviewer Objection Register has rows but none carry BOTH a Severity "
            "and a Preemptive fix. At least one complete row is required."
        )
        return
    result.objection_register_ok = True


def check_editorial_fit(body: str | None, result: ReviewerAuditResult) -> None:
    if body is None:
        result.findings.append(
            "Missing 'Editorial Fit Map' section. Cover venue fit, editor-facing "
            "value, and desk-reject risks."
        )
        return
    # Non-empty means it has real content beyond whitespace and the table/heading
    # scaffolding — at least one line of prose or a bullet.
    meaningful = [
        ln.strip() for ln in body.splitlines()
        if ln.strip() and not set(ln.strip()) <= {"-", ":", "|", " "}
    ]
    if not meaningful:
        result.findings.append(
            "Editorial Fit Map section is empty. Add venue fit, editor-facing "
            "value, and desk-reject risks."
        )
        return
    result.editorial_fit_ok = True


def validate(output_dir: Path) -> ReviewerAuditResult:
    path = output_dir / "reviewer_audit.md"
    result = ReviewerAuditResult(path=str(path), ok=False)
    if not path.exists():
        result.findings.append(f"file does not exist: {path}")
        result.missing_criteria = list(REQUIRED_CRITERIA)
        return result

    text = path.read_text(encoding="utf-8", errors="ignore")

    check_value_map(section_body(text, VALUE_MAP_HEADING), result)
    check_objection_register(section_body(text, OBJECTION_HEADING), result)
    check_editorial_fit(section_body(text, EDITORIAL_HEADING), result)

    result.ok = (
        result.value_map_ok
        and result.objection_register_ok
        and result.editorial_fit_ok
        and not result.findings
    )
    return result


def to_markdown(result: ReviewerAuditResult) -> str:
    lines = [
        "# Reviewer Audit Check",
        "",
        f"- Path: `{result.path}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Reviewer Value Map: {'PASS' if result.value_map_ok else 'FAIL'}",
        f"- Reviewer Objection Register: {'PASS' if result.objection_register_ok else 'FAIL'}",
        f"- Editorial Fit Map: {'PASS' if result.editorial_fit_ok else 'FAIL'}",
        f"- Criteria found: {', '.join(result.found_criteria) or '(none)'}",
        f"- Criteria missing: {', '.join(result.missing_criteria) or '(none)'}",
        f"- Objection rows: {result.objection_row_count}",
        "",
        "## Findings",
        "",
    ]
    if result.findings:
        lines.extend(f"- {finding}" for finding in result.findings)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    result = validate(output_dir)
    markdown = to_markdown(result)

    if args.write:
        report_path = output_dir / "reviewer_audit_check.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown, encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
