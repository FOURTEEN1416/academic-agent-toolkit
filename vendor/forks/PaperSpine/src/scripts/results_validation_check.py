#!/usr/bin/env python3
"""Validate PaperSpine results_validation.md — Results-as-Validation.

Each major Results subsection must validate at least one contribution promise.
A row that reports a metric with no contribution mapping (empty
`Contribution Claim Tested`) or no evidence (empty `Result/Evidence`) is a hard
failure: such a row proves nothing about what the paper claimed.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paper_spine_utils import read_text, table_rows

# Column -> substrings that identify its header cell (case-insensitive).
CLAIM_TERMS = ("contribution claim", "claim tested", "contribution")
EVIDENCE_TERMS = ("result/evidence", "result / evidence", "evidence", "result")
UNIT_TERMS = ("results unit", "unit")
ALLOWED_TERMS = ("allowed interpretation",)
NOT_ALLOWED_TERMS = ("not allowed", "interpretation not")


@dataclass
class ResultsValidationResult:
    path: str
    ok: bool
    row_count: int
    mapped_rows: int
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PaperSpine results_validation.md.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write results_validation_check.md next to results_validation.md.",
    )
    return parser.parse_args()


def _find_column(header: list[str], terms: tuple[str, ...]) -> int:
    """Return the index of the first header cell matching any term, else -1.

    Terms are tried in order so that a more specific term (e.g. the full
    `contribution claim tested`) wins before a looser one (`contribution`).
    """
    lowered = [cell.lower() for cell in header]
    for term in terms:
        for index, cell in enumerate(lowered):
            if term in cell:
                return index
    return -1


def _cell(row: list[str], index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return row[index].strip()


def validate(results_path: Path) -> ResultsValidationResult:
    findings: list[str] = []
    warnings: list[str] = []

    if not results_path.exists():
        return ResultsValidationResult(
            str(results_path),
            False,
            0,
            0,
            ["results_validation.md does not exist — the Results-as-Validation step was skipped."],
        )

    text = read_text(results_path)
    header, rows = table_rows(text)
    if not header:
        findings.append("results_validation.md must contain a Markdown table.")
        return ResultsValidationResult(str(results_path), False, 0, 0, findings)

    claim_idx = _find_column(header, CLAIM_TERMS)
    evidence_idx = _find_column(header, EVIDENCE_TERMS)
    unit_idx = _find_column(header, UNIT_TERMS)
    allowed_idx = _find_column(header, ALLOWED_TERMS)
    not_allowed_idx = _find_column(header, NOT_ALLOWED_TERMS)

    if claim_idx < 0:
        findings.append("results_validation.md table is missing a `Contribution Claim Tested` column.")
    if evidence_idx < 0:
        findings.append("results_validation.md table is missing a `Result/Evidence` column.")

    data_rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not data_rows:
        findings.append("results_validation.md has no data rows — no Results subsection was mapped to a contribution.")
        return ResultsValidationResult(str(results_path), False, 0, 0, findings)

    mapped_rows = 0
    for number, row in enumerate(data_rows, start=1):
        label = _cell(row, unit_idx) or f"row {number}"
        claim = _cell(row, claim_idx) if claim_idx >= 0 else ""
        evidence = _cell(row, evidence_idx) if evidence_idx >= 0 else ""

        if not claim:
            findings.append(
                f"{label}: empty `Contribution Claim Tested` — a metric-only row that validates no "
                "contribution promise. Map it to a contribution (C1, C2, ...) or cut the subsection."
            )
        if not evidence:
            findings.append(
                f"{label}: empty `Result/Evidence` — a contribution claim with no result behind it."
            )
        if claim and evidence:
            mapped_rows += 1

        if allowed_idx >= 0 and not _cell(row, allowed_idx):
            warnings.append(f"{label}: empty `Allowed Interpretation` — state the strongest honest reading.")
        if not_allowed_idx >= 0 and not _cell(row, not_allowed_idx):
            warnings.append(
                f"{label}: empty `Interpretation NOT Allowed` — name the overclaim this row does not license."
            )

    return ResultsValidationResult(
        str(results_path),
        not findings,
        len(data_rows),
        mapped_rows,
        findings,
        warnings,
    )


def to_markdown(result: ResultsValidationResult) -> str:
    lines = [
        "# Results Validation Check",
        "",
        f"- Path: `{result.path}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Data rows: {result.row_count}",
        f"- Rows mapping a claim to evidence: {result.mapped_rows}",
        "",
        "## Findings",
        "",
    ]
    if result.findings:
        lines.extend(f"- {finding}" for finding in result.findings)
    else:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    results_path = output_dir / "results_validation.md"
    result = validate(results_path)
    markdown = to_markdown(result)

    if args.write:
        report_path = output_dir / "results_validation_check.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown, encoding="utf-8")

    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
