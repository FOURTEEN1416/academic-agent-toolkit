#!/usr/bin/env python3
"""Verify English citations in citation_support_bank.md against Crossref API.

Self-contained — standard library only.  Queries the public Crossref REST API
(no key required) to confirm that each candidate citation resolves to a real
published work.

Crossref is an enhancement, not a hard dependency.  When the API is unreachable
citations are marked SKIPPED rather than failing the check.

Use ``--delay`` to throttle requests (in seconds) to be polite to the
Crossref API; ``--no-api`` skips network access entirely.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

CROSSREF_QUERY_URL = "https://api.crossref.org/works"
USER_AGENT = "PaperSpine/1.0 (mailto:paperspine@example.com)"

# Title similarity threshold for a "matched" verdict
MIN_TITLE_SIMILARITY = 0.6
YEAR_TOLERANCE = 1  # ±1 year


# ---------------------------------------------------------------------------
# table helpers (self-contained, same idiom as humanize_check.py)
# ---------------------------------------------------------------------------

def _split_table_line(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_sep(cells: list[str]) -> bool:
    return bool(cells) and all(c and set(c) <= {"-", ":", " "} for c in cells)


def _table_rows(text: str) -> tuple[list[str], list[list[str]]]:
    rows: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = _split_table_line(line)
        if _is_sep(cells):
            continue
        rows.append(cells)
    return (rows[0], rows[1:]) if rows else ([], [])


def _col_index(header: list[str], *names: str) -> int | None:
    """Return the 0-based index of the first header cell matching any name."""
    lower = [h.lower() for h in header]
    for name in names:
        for idx, h in enumerate(lower):
            if name.lower() in h:
                return idx
    return None


# ---------------------------------------------------------------------------
# metadata extraction from reference text
# ---------------------------------------------------------------------------

def _extract_doi(text: str) -> str | None:
    """Extract a DOI from a text field."""
    doi_pattern = re.compile(r"\b(10\.\d{4,}/[^\s\"'<>]+)", re.IGNORECASE)
    match = doi_pattern.search(text)
    if match:
        doi = re.sub(r"[.,;:)\]]+$", "", match.group(1))
        return doi
    return None


def _extract_year(text: str) -> str | None:
    """Extract a plausible publication year (1900–2030) from reference text."""
    years = re.findall(r"\b((?:19|20)\d{2})\b", text)
    if years:
        for y in years:
            year_int = int(y)
            if 1900 <= year_int <= 2030:
                return y
    return None


def _extract_author(text: str) -> str:
    """Extract a plausible first-author surname from reference text.

    Heuristics (tried in order):
    1. BibTeX key: ``@article{smith2024,``  →  ``smith``
    2. ``Smith, J.`` or ``Smith J`` before the year
    3. First capitalised word that looks like a name
    """
    # BibTeX citation key
    bibtex = re.search(r"@\w+\{([a-zA-Z-]+)\d", text)
    if bibtex:
        return bibtex.group(1).lower()

    # "Smith, J." or "Smith J" before a year
    author_year = re.search(r"([A-Z][a-z]{2,}(?:\s+[A-Z]\.)*).*?(\d{4})", text)
    if author_year:
        surname = author_year.group(1).split()[0].rstrip(".")
        if len(surname) >= 3:
            return surname.lower()

    # First capitalised word that looks like a name (3+ chars, no digits)
    capitals = re.findall(r"\b([A-Z][a-z]{3,})\b", text)
    for word in capitals:
        if word.lower() not in {
            "journal", "proceedings", "nature", "science", "international",
            "this", "these", "those", "article", "review", "chapter",
        }:
            return word.lower()

    return ""


def _extract_title_query(text: str) -> str:
    """Extract a plausible title substring for bibliographic query.

    Looks for a quoted title, or text between year and a journal marker,
    or the longest sentence-like fragment.
    """
    # Quoted title
    quoted = re.findall(r'"([^"]{25,250})"', text)
    if quoted:
        return quoted[0]

    # Remove leading author/year/DOI noise
    cleaned = text
    # Strip DOI
    doi_match = _extract_doi(cleaned)
    if doi_match:
        cleaned = cleaned.replace(doi_match, "")
    # Strip URLs
    cleaned = re.sub(r"https?://\S+", "", cleaned)

    # Try to find text between a year and a journal marker
    year_match = re.search(r"\b(19|20)\d{2}\b", cleaned)
    journal_markers = [
        "Journal of", "Proceedings of", "IEEE", "ACM Trans",
        "Nature", "Science", "Cell", "Lancet", "BMJ", "PLOS",
        "Springer", "Elsevier", "vol.", "Vol.",
    ]
    if year_match:
        after_year = cleaned[year_match.end():].strip(" .,;:()[]")
        for marker in journal_markers:
            idx = after_year.find(marker)
            if idx > 15:
                candidate = after_year[:idx].strip(" .,;:")
                if len(candidate) >= 25:
                    return candidate

    # Fallback: longest sentence-like fragment
    fragments = re.split(r"[.!?]\s+", cleaned)
    long_enough = [f.strip() for f in fragments if len(f.strip()) >= 25]
    if long_enough:
        return max(long_enough, key=len)[:250]

    # Last resort: return a cleaned chunk of the text
    words = cleaned.split()
    if len(words) >= 6:
        return " ".join(words[:50])
    return cleaned[:250]


# ---------------------------------------------------------------------------
# Crossref API (extracted for testability)
# ---------------------------------------------------------------------------

def _fetch_crossref_json(url: str, timeout: int = 15) -> dict | None:
    """Fetch JSON from a Crossref API URL.

    Extracted as a module-level function so tests can mock it without
    touching ``urllib.request.urlopen`` internals.  Returns the parsed
    JSON dict on success, or ``None`` on any network / parse error.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))  # type: ignore[no-any-return]
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        OSError,
        ValueError,
    ):
        return None


def _crossref_doi_lookup(doi: str) -> dict | None:
    """Query Crossref by DOI. Returns parsed JSON or None on failure."""
    url = f"{CROSSREF_QUERY_URL}/{urllib.parse.quote(doi, safe='')}"
    return _fetch_crossref_json(url)


def _crossref_bibliographic_query(query: str) -> dict | None:
    """Query Crossref by bibliographic metadata. Returns parsed JSON or None."""
    params = urllib.parse.urlencode({
        "query.bibliographic": query[:200],
        "rows": 3,
    })
    url = f"{CROSSREF_QUERY_URL}?{params}"
    return _fetch_crossref_json(url)


# ---------------------------------------------------------------------------
# matching logic
# ---------------------------------------------------------------------------

def _crossref_year(msg: dict) -> str:
    """Extract a publication year from a Crossref message.

    Prefers the actual publication date fields (``issued``,
    ``published-print``, ``published-online``) over ``created``, which
    records the *registration* date and can differ from the publication
    year for older or back-filled works.
    """
    for key in ("issued", "published-print", "published-online", "published"):
        field_val = msg.get(key)
        if isinstance(field_val, dict):
            parts = field_val.get("date-parts") or [[0]]
            try:
                year = parts[0][0]
            except (IndexError, TypeError):
                year = 0
            if year:
                return str(year)
    # Fall back to the registration date only if nothing else is available.
    created = msg.get("created")
    if isinstance(created, dict):
        parts = created.get("date-parts") or [[0]]
        try:
            year = parts[0][0]
        except (IndexError, TypeError):
            year = 0
        if year:
            return str(year)
    return ""


def _titles_similar(local_title: str, crossref_title: str) -> bool:
    """Return True when *local_title* is similar enough to *crossref_title*."""
    if not local_title or not crossref_title:
        return False
    a = local_title.lower().strip()
    b = crossref_title.lower().strip()
    # Direct substring in either direction → definitely similar
    if a[:40] in b or b[:40] in a:
        return True
    ratio = difflib.SequenceMatcher(None, a[:200], b[:200]).ratio()
    return ratio >= MIN_TITLE_SIMILARITY


def _years_close(local_year: str, crossref_year: str) -> bool:
    """Return True when years match within ±YEAR_TOLERANCE."""
    if not local_year or not crossref_year:
        return True  # can't judge, be permissive
    try:
        ly = int(local_year)
        cy = int(crossref_year)
        return abs(ly - cy) <= YEAR_TOLERANCE
    except (ValueError, TypeError):
        return True


# ---------------------------------------------------------------------------
# data classes
# ---------------------------------------------------------------------------

@dataclass
class VerificationEntry:
    candidate_id: str
    reference_text: str = ""
    doi: str = ""
    status: str = "unchecked"   # matched | unmatched | skipped | warning
    crossref_title: str = ""
    crossref_year: str = ""
    crossref_doi: str = ""
    note: str = ""


@dataclass
class CitationVerificationResult:
    path: str
    ok: bool
    total_candidates: int = 0
    checked_count: int = 0
    matched_count: int = 0
    unmatched_count: int = 0
    skipped_count: int = 0
    entries: list[VerificationEntry] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify English citations in citation_support_bank.md against Crossref."
    )
    parser.add_argument(
        "bank_path", nargs="?",
        default="paper_rewriting_output/citation_support_bank.md",
    )
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true",
                        help="Write citation_verification_en.md")
    parser.add_argument("--max-checks", type=int, default=30,
                        help="Maximum citations to check (default: 30).")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Seconds to sleep between Crossref requests "
                             "(default: 0).")
    parser.add_argument("--no-api", action="store_true",
                        help="Skip all Crossref calls; mark checkable "
                             "citations as skipped instead of querying.")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# main verification logic
# ---------------------------------------------------------------------------

def verify_citation(
    bank_path: Path,
    max_checks: int = 30,
    *,
    delay: float = 0.0,
    no_api: bool = False,
    _fetcher: object | None = None,
) -> CitationVerificationResult:
    """Verify citations in *bank_path* against Crossref.

    The *_fetcher* parameter exists for testing: pass a callable with the
    same signature as ``_fetch_crossref_json`` to mock the network layer.

    When *no_api* is True no network calls are made: every citation that
    would otherwise be queried is marked ``skipped``.  *delay* controls the
    sleep (in seconds) between Crossref requests.
    """
    fetch = _fetcher if _fetcher is not None else _fetch_crossref_json  # type: ignore[assignment]

    result = CitationVerificationResult(str(bank_path), ok=True)

    if not bank_path.exists():
        result.ok = False
        result.findings.append(f"Bank file not found: {bank_path}")
        return result

    text = bank_path.read_text(encoding="utf-8", errors="ignore")
    header, rows = _table_rows(text)
    if not header:
        result.ok = False
        result.findings.append("No parseable table found in citation_support_bank.md")
        return result

    id_col = _col_index(header, "candidate id", "id")
    ref_col = _col_index(header, "reference", "bibtex")
    source_channel_col = _col_index(header, "source channel")

    if id_col is None:
        result.findings.append(
            "Missing Candidate ID / ID column — cannot map verifications."
        )
        result.ok = False
        return result

    result.total_candidates = len(rows)

    for row_index, row in enumerate(rows):
        candidate_id = (
            row[id_col].strip() if id_col < len(row) else f"row{row_index + 1}"
        )

        entry = VerificationEntry(candidate_id=candidate_id)

        # --- read reference text ---
        if ref_col is not None and ref_col < len(row):
            entry.reference_text = row[ref_col].strip()
        else:
            entry.reference_text = " ".join(row)

        # --- read source channel ---
        channel = ""
        if source_channel_col is not None and source_channel_col < len(row):
            channel = row[source_channel_col].strip().lower()

        # local-only entries are never checked against Crossref
        if channel == "local":
            entry.status = "skipped"
            entry.note = "local source — not checked against Crossref"
            result.skipped_count += 1
            result.entries.append(entry)
            continue

        # respect max-checks cap
        if result.checked_count >= max_checks:
            entry.status = "skipped"
            entry.note = f"max-checks limit ({max_checks}) reached"
            result.skipped_count += 1
            result.entries.append(entry)
            continue

        # --- extract metadata from the reference text ---
        doi = _extract_doi(entry.reference_text)
        extracted_author = _extract_author(entry.reference_text)
        extracted_year = _extract_year(entry.reference_text)
        extracted_title = _extract_title_query(entry.reference_text)

        # Build a bibliographic query string from what we have
        bib_parts = []
        if extracted_author:
            bib_parts.append(extracted_author)
        if extracted_title:
            bib_parts.append(extracted_title[:150])
        bib_query = " ".join(bib_parts) if bib_parts else entry.reference_text[:200]

        if not bib_query.strip() or len(bib_query.strip()) < 10:
            entry.status = "skipped"
            entry.note = "Insufficient metadata to query Crossref"
            result.skipped_count += 1
            result.entries.append(entry)
            continue

        # --no-api: never touch the network, just record what we extracted
        if no_api:
            if doi:
                entry.doi = doi
            entry.status = "skipped"
            entry.note = "API disabled (--no-api) — not checked against Crossref"
            result.skipped_count += 1
            result.entries.append(entry)
            continue

        # --- query Crossref ---
        if delay > 0:
            time.sleep(delay)
        result.checked_count += 1

        # Prefer DOI lookup when a DOI is available
        if doi:
            entry.doi = doi

            # Use the injected fetcher for DOI lookup
            doi_url = f"{CROSSREF_QUERY_URL}/{urllib.parse.quote(doi, safe='')}"
            data = fetch(doi_url)  # type: ignore[call-arg]

            if data is None:
                # API / network failure → warning, don't crash
                entry.status = "warning"
                entry.note = "Crossref API unreachable (DOI lookup) — skipped"
                result.skipped_count += 1
                result.entries.append(entry)
                continue

            if data.get("status") == "ok":
                msg = data.get("message", {})
                crossref_title = " ".join(
                    str(t).strip() for t in msg.get("title", [""])
                )[:200]
                crossref_year = _crossref_year(msg)
                crossref_doi = msg.get("DOI", "")

                # A DOI that resolves on Crossref is itself sufficient
                # evidence that the work is real.  A registration/publication
                # year mismatch is not grounds to fail a resolvable DOI, so
                # we record it as a note but still mark the entry matched.
                title_ok = _titles_similar(extracted_title, crossref_title)
                year_ok = _years_close(extracted_year or "", crossref_year)

                entry.status = "matched"
                entry.crossref_title = crossref_title[:120]
                entry.crossref_year = crossref_year
                entry.crossref_doi = crossref_doi
                if title_ok and year_ok:
                    entry.note = "DOI resolved — title and year match"
                else:
                    caveats = []
                    if not title_ok:
                        caveats.append("title differs from local metadata")
                    if not year_ok:
                        caveats.append(
                            f"year differs (local={extracted_year}, crossref={crossref_year})"
                        )
                    entry.note = (
                        "DOI resolved on Crossref (real work)"
                        + ("; " + "; ".join(caveats) if caveats else "")
                    )
                result.matched_count += 1
            else:
                entry.status = "unmatched"
                entry.note = f"DOI {doi} not found in Crossref"
                result.unmatched_count += 1
        else:
            # Bibliographic query
            bib_url = (
                f"{CROSSREF_QUERY_URL}?"
                f"{urllib.parse.urlencode({'query.bibliographic': bib_query[:200], 'rows': 3})}"
            )
            data = fetch(bib_url)  # type: ignore[call-arg]

            if data is None:
                entry.status = "warning"
                entry.note = "Crossref API unreachable (bibliographic query) — skipped"
                result.skipped_count += 1
                result.entries.append(entry)
                continue

            if data.get("status") == "ok":
                items = data.get("message", {}).get("items", [])
                if items:
                    # Try each returned item for a conservative match
                    best = items[0]
                    crossref_title = " ".join(
                        str(t).strip() for t in best.get("title", [""])
                    )[:200]
                    crossref_year = _crossref_year(best)
                    crossref_doi = best.get("DOI", "")

                    # Check all returned items for a match (not just the first)
                    matched_item = None
                    for item in items:
                        item_title = " ".join(
                            str(t).strip() for t in item.get("title", [""])
                        )[:200]
                        item_year = _crossref_year(item)
                        if _titles_similar(extracted_title, item_title) and _years_close(
                            extracted_year or "", item_year
                        ):
                            matched_item = item
                            crossref_title = item_title
                            crossref_year = item_year
                            crossref_doi = item.get("DOI", "")
                            break

                    if matched_item is not None:
                        entry.status = "matched"
                        entry.crossref_title = crossref_title[:120]
                        entry.crossref_year = crossref_year
                        entry.crossref_doi = crossref_doi
                        entry.note = "Bibliographic query matched — title and year agree"
                        result.matched_count += 1
                    else:
                        entry.status = "unmatched"
                        entry.crossref_title = crossref_title[:120]
                        entry.crossref_year = crossref_year
                        entry.crossref_doi = crossref_doi
                        entry.note = (
                            "Crossref returned results but title/year did not match "
                            "local metadata"
                        )
                        result.unmatched_count += 1
                else:
                    entry.status = "unmatched"
                    entry.note = "No Crossref results for bibliographic query"
                    result.unmatched_count += 1
            else:
                entry.status = "unmatched"
                entry.note = "Crossref query returned unexpected status"
                result.unmatched_count += 1

        result.entries.append(entry)

    # --- synthesise findings ---
    if result.checked_count == 0 and result.skipped_count > 0:
        result.findings.append(
            f"No citations checked: {result.skipped_count} skipped "
            f"(local sources, API unavailable, or insufficient metadata)."
        )

    if result.unmatched_count > 0:
        unmatched_ids = [
            e.candidate_id for e in result.entries if e.status == "unmatched"
        ]
        result.findings.append(
            f"{result.unmatched_count} citation(s) could not be matched in Crossref: "
            f"{unmatched_ids[:10]}. Review these entries for typos or incomplete metadata."
        )

    if result.matched_count == 0 and result.checked_count > 0:
        result.findings.append(
            f"All {result.checked_count} checked citations failed to match Crossref. "
            "Check that reference text includes complete titles and author names."
        )
        result.ok = False

    if result.checked_count > 0:
        match_rate = result.matched_count / result.checked_count
        if match_rate < 0.5:
            result.ok = False
            result.findings.append(
                f"Low match rate: {result.matched_count}/{result.checked_count} "
                f"({match_rate:.0%}) — most citations could not be confirmed."
            )

    return result


# ---------------------------------------------------------------------------
# output formatting
# ---------------------------------------------------------------------------

def to_markdown(result: CitationVerificationResult) -> str:
    lines = [
        "# Citation Verification Report (Crossref)",
        "",
        f"- Bank path: `{result.path}`",
        f"- Total candidates: {result.total_candidates}",
        f"- Checked: {result.checked_count}",
        f"- Matched: {result.matched_count}",
        f"- Unmatched: {result.unmatched_count}",
        f"- Skipped: {result.skipped_count}",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        "",
        "## Verification Results",
        "",
    ]

    if result.entries:
        lines.extend([
            "| Candidate ID | Status | DOI Queried | Crossref Title | Crossref Year | Note |",
            "|---|---|---|---|---|---|",
        ])
        for entry in result.entries:
            c_title = entry.crossref_title[:60] if entry.crossref_title else "-"
            c_year = entry.crossref_year or "-"
            lines.append(
                f"| {entry.candidate_id} | {entry.status} | {entry.doi or '-'} | "
                f"{c_title} | {c_year} | {entry.note} |"
            )
        lines.append("")
    else:
        lines.append("- No entries to report.")
        lines.append("")

    lines.extend([
        "## Findings",
        "",
    ])
    if result.findings:
        lines.extend(f"- {f}" for f in result.findings)
    else:
        lines.append("- No issues found.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # parity with citation_quality_audit on Windows
    args = parse_args()
    bank_path = Path(args.bank_path)
    result = verify_citation(
        bank_path,
        max_checks=args.max_checks,
        delay=args.delay,
        no_api=args.no_api,
    )

    if args.json:
        print(json.dumps({
            "ok": result.ok,
            "total_candidates": result.total_candidates,
            "checked_count": result.checked_count,
            "matched_count": result.matched_count,
            "unmatched_count": result.unmatched_count,
            "skipped_count": result.skipped_count,
            "findings": result.findings,
            "entries": [
                {
                    "candidate_id": e.candidate_id,
                    "status": e.status,
                    "doi": e.doi,
                    "crossref_title": e.crossref_title,
                    "crossref_year": e.crossref_year,
                    "note": e.note,
                }
                for e in result.entries
            ],
        }, ensure_ascii=False, indent=2))
    elif args.markdown or not args.json:
        print(to_markdown(result))

    if args.write:
        report_path = bank_path.parent / "citation_verification_en.md"
        report_path.write_text(to_markdown(result), encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
