#!/usr/bin/env python3
"""Validate PaperSpine citation_support_bank.md."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paper_spine_utils import markdown_tables, year_from_row

CURRENT_YEAR = 2026
DEFAULT_TARGET_COUNT = 20
DEFAULT_MULTIPLIER = 3
DEFAULT_RECENT_RATIO = 0.80


@dataclass
class CitationBankResult:
    path: str
    ok: bool
    target_count: int
    required_candidates: int
    row_count: int
    unique_source_count: int
    recent_count: int
    unique_recent_source_count: int
    required_recent_count: int
    duplicated_source_uses: int
    findings: list[str]
    scope: str = "open_literature"
    warnings: list[str] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PaperSpine citation support bank.")
    parser.add_argument("path", nargs="?", default="paper_rewriting_output/citation_support_bank.md")
    parser.add_argument("--target-count", type=int, default=DEFAULT_TARGET_COUNT)
    parser.add_argument("--multiplier", type=int, default=DEFAULT_MULTIPLIER)
    parser.add_argument("--recent-years", type=int, default=3)
    parser.add_argument("--recent-ratio", type=float, default=DEFAULT_RECENT_RATIO)
    parser.add_argument(
        "--scope",
        choices=("open_literature", "closed_corpus"),
        default="open_literature",
        help="Use closed_corpus for evidence-bounded rewrites that may not add literature.",
    )
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write citation_bank_check.md next to citation_support_bank.md.",
    )
    return parser.parse_args()


def has_claim_sentence(row: list[str]) -> bool:
    joined = " ".join(row).strip()
    if len(joined) < 80:
        return False
    return bool(re.search(r"[.!?。！？]", joined))


def has_reference_format(row: list[str]) -> bool:
    joined = " ".join(row).lower()
    return any(token in joined for token in ("@", "doi", "http", "arxiv", "proceedings", "journal"))


def find_citation_table(text: str) -> tuple[list[str], list[list[str]]]:
    for table in markdown_tables(text):
        if not table:
            continue
        header = table[0]
        header_text = " ".join(cell.lower() for cell in header)
        has_reference = any(term in header_text for term in ("citation", "reference", "bibtex"))
        has_claim = "claim" in header_text
        has_sentence = "sentence" in header_text
        if has_reference and has_claim and has_sentence:
            return header, table[1:]
    return [], []


def _column_index(header: list[str], *needles: str) -> int | None:
    for index, cell in enumerate(header):
        normalized = " ".join(cell.lower().split())
        if any(needle in normalized for needle in needles):
            return index
    return None


def source_identity(header: list[str], row: list[str]) -> str:
    """Return a stable, quota-safe identity for one bibliographic source.

    Claim-use rows may legitimately repeat a paper, but repeated uses must never
    inflate source coverage or recency quotas. Prefer explicit Source ID, DOI,
    arXiv ID, BibTeX key, then URL; only then fall back to normalized reference
    text.
    """
    source_id_index = _column_index(header, "source id")
    if source_id_index is not None and source_id_index < len(row):
        value = row[source_id_index].strip().lower()
        if value and value not in {"-", "n/a", "na", "unknown"}:
            return f"source:{value}"

    reference_index = _column_index(header, "reference", "bibtex", "citation")
    reference = row[reference_index] if reference_index is not None and reference_index < len(row) else " ".join(row)
    lowered = reference.lower()

    doi = re.search(r"\b10\.\d{4,9}/[-._;()/:a-z0-9]+", lowered)
    if doi:
        return f"doi:{doi.group(0).rstrip('.,;)}]')}"
    arxiv = re.search(r"(?:arxiv\s*:\s*|arxiv\.org/(?:abs|pdf)/)([a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?", lowered)
    if arxiv:
        return f"arxiv:{arxiv.group(1)}"
    bibtex = re.search(r"@\w+\s*\{\s*([^,\s]+)", reference)
    if bibtex:
        return f"bib:{bibtex.group(1).strip().lower()}"
    url = re.search(r"https?://[^\s|}]+", lowered)
    if url:
        return f"url:{url.group(0).rstrip('.,;)}]')}"

    normalized = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", lowered)).strip()
    return f"text:{normalized}"


def validate(
    path: Path,
    target_count: int,
    multiplier: int,
    recent_years: int,
    recent_ratio: float,
    scope: str = "open_literature",
) -> CitationBankResult:
    closed_corpus = scope == "closed_corpus"
    required_candidates = target_count if closed_corpus else target_count * multiplier
    required_recent_count = int(required_candidates * recent_ratio + 0.999)
    findings: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return CitationBankResult(
            str(path), False, target_count, required_candidates, 0, 0, 0, 0,
            required_recent_count, 0, ["file does not exist"], scope, warnings,
        )

    text = path.read_text(encoding="utf-8", errors="ignore")
    header, rows = find_citation_table(text)
    if not header:
        findings.append("citation_support_bank.md must contain a Markdown table.")
    header_text = " ".join(cell.lower() for cell in header)
    if not any(term in header_text for term in ("citation", "reference", "bibtex")):
        findings.append("citation_support_bank.md table should include a `reference` or `citation` column.")
    for required in ("claim", "sentence"):
        if required not in header_text:
            findings.append(f"citation_support_bank.md table should include a `{required}` column.")

    nonempty_rows = [row for row in rows if any(cell.strip() for cell in row)]
    identities = [source_identity(header, row) for row in nonempty_rows]
    source_counts = Counter(identities)
    unique_source_count = len(source_counts)
    duplicated_source_uses = sum(count - 1 for count in source_counts.values())

    exhaustive_marker = "CLOSED_CORPUS_EXHAUSTIVE" in text
    if len(nonempty_rows) < required_candidates and not (closed_corpus and exhaustive_marker):
        findings.append(
            f"citation_support_bank.md has {len(nonempty_rows)} claim-use rows; expected at least {required_candidates} for target_count={target_count} and multiplier={multiplier}."
        )
    if unique_source_count < required_candidates and not (closed_corpus and exhaustive_marker):
        findings.append(
            f"citation_support_bank.md has only {unique_source_count} unique sources across {len(nonempty_rows)} claim-use rows; expected at least {required_candidates} unique sources. Repeated uses of one paper do not satisfy source coverage."
        )

    threshold = CURRENT_YEAR - recent_years
    recent_rows = [row for row in nonempty_rows if (year_from_row(row) or 0) >= threshold]
    unique_recent_sources = {
        source_identity(header, row)
        for row in recent_rows
    }
    if len(unique_recent_sources) < required_recent_count:
        message = (
            f"citation_support_bank.md has {len(unique_recent_sources)} unique recent sources since {threshold}; expected at least {required_recent_count}. Repeated claim uses count once for recency."
        )
        (warnings if closed_corpus else findings).append(message)

    if closed_corpus:
        warnings.append(
            "Closed-corpus mode: recency and 3x discovery breadth are advisory; source truth, deduplication, and claim support remain blocking."
        )
        if exhaustive_marker and unique_source_count < target_count:
            warnings.append(
                f"Closed corpus declares exhaustive coverage with {unique_source_count} unique sources below the final target of {target_count}."
            )

    weak_rows = []
    for index, row in enumerate(nonempty_rows[:required_candidates], start=1):
        if not has_claim_sentence(row) or not has_reference_format(row):
            weak_rows.append(index)
    if weak_rows:
        sample = ", ".join(str(value) for value in weak_rows[:8])
        findings.append(
            f"citation_support_bank.md rows need a reference format plus one or two usable claim-support sentences; weak rows include: {sample}."
        )

    return CitationBankResult(
        str(path),
        not findings,
        target_count,
        required_candidates,
        len(nonempty_rows),
        unique_source_count,
        len(recent_rows),
        len(unique_recent_sources),
        required_recent_count,
        duplicated_source_uses,
        findings,
        scope,
        warnings,
    )


def to_markdown(result: CitationBankResult) -> str:
    lines = [
        "# Citation Bank Check",
        "",
        f"- Path: `{result.path}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Literature scope: {result.scope}",
        f"- Target citation count: {result.target_count}",
        f"- Required unique sources: {result.required_candidates}",
        f"- Claim-use rows: {result.row_count}",
        f"- Unique sources: {result.unique_source_count}",
        f"- Repeated source uses: {result.duplicated_source_uses}",
        f"- Required unique recent sources: {result.required_recent_count}",
        f"- Recent claim-use rows: {result.recent_count}",
        f"- Unique recent sources: {result.unique_recent_source_count}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in result.findings) if result.findings else lines.append("- None")
    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    result = validate(
        path, args.target_count, args.multiplier, args.recent_years,
        args.recent_ratio, args.scope,
    )
    markdown = to_markdown(result)
    if args.write:
        report_path = path.parent / "citation_bank_check.md"
        report_path.write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
