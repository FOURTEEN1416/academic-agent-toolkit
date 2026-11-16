#!/usr/bin/env python3
"""Inspect Chinese citation format and DOI availability.

These diagnostics cannot prove fabrication, bibliographic identity, or claim
support. Complete verification requires the original source or authoritative
metadata; no row becomes VERIFIED from format or a resolved DOI alone.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paper_spine_utils import table_rows

USER_AGENT = "PaperSpine/3.0 (citation-zh; https://github.com/WUBING2023/PaperSpine)"
DOI_RE = re.compile(r"(?:doi\s*[:=]\s*|https?://doi\.org/)?(10\.\d{4,}/[^\s,;)]+)", re.IGNORECASE)

# Chinese citation format patterns
CN_AUTHOR_RE = re.compile(r"[^\x00-\x7f]{2,4}(?:[,，、\s]+[^\x00-\x7f]{2,4})*")  # Chinese author names
CN_JOURNAL_RE = re.compile(r"《([^》]+)》")  # 《期刊名》
CN_YEAR_RE = re.compile(r"(\d{4})[年]?")
CN_VOLUME_RE = re.compile(r"(\d+)\s*[卷\(（]")
CN_PAGES_RE = re.compile(r"(\d+)[-~]\s*(\d+)")

@dataclass
class CitationCheckZH:
    candidate_id: str
    reference_text: str
    status: str = "INCOMPLETE"  # format/lookup diagnostic; never infers fabrication
    has_author: bool = False
    has_title: bool = False
    has_journal: bool = False
    has_year: bool = False
    has_doi: bool = False
    doi_resolves: bool = False
    issues: list[str] = field(default_factory=list)


@dataclass
class CitationVerificationZHResult:
    path: str
    total: int = 0
    verified: int = 0
    suspicious: int = 0
    incomplete: int = 0
    fake: int = 0
    checks: list[CitationCheckZH] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Legacy exit/JSON flag: a nonempty bank was diagnosed, not verified."""
        return self.total > 0 and len(self.checks) == self.total

    @property
    def complete_verification(self) -> bool:
        # This helper does not compare bibliographic identity or claim support.
        return False

    @property
    def diagnostic_status(self) -> str:
        if not self.ok:
            return "FAIL"
        return "WARN" if self.suspicious or self.incomplete or self.fake else "COMPLETE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose Chinese citation format and DOI availability; not complete verification.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def check_zh_format(ref: str) -> dict:
    return {
        "has_author": bool(CN_AUTHOR_RE.search(ref)),
        "has_journal": bool(CN_JOURNAL_RE.search(ref)),
        "has_year": bool(CN_YEAR_RE.search(ref)),
    }


def has_doi(ref: str) -> str:
    m = DOI_RE.search(ref)
    return m.group(1) if m else ""


def verify_doi(doi: str) -> bool:
    try:
        req = Request(f"https://api.crossref.org/works/{doi}", headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception:
        return False


def check_citation_bank_zh(out_dir: Path) -> CitationVerificationZHResult:
    bank_path = out_dir / "citation_support_bank.md"
    if not bank_path.exists():
        return CitationVerificationZHResult(str(bank_path))

    text = bank_path.read_text(encoding="utf-8", errors="ignore")
    header, rows = table_rows(text)
    if not rows:
        return CitationVerificationZHResult(str(bank_path))

    result = CitationVerificationZHResult(str(bank_path), total=len(rows))
    reference_index = next((i for i, name in enumerate(header)
                            if any(term in name.casefold() for term in
                                   ("reference", "citation", "bibtex", "文献", "引用"))), None)

    for row in rows:
        joined = " ".join(row)
        candidate_id = row[0] if len(row) > 0 else "?"
        ref = row[reference_index] if reference_index is not None and reference_index < len(row) else joined

        check = CitationCheckZH(candidate_id=candidate_id, reference_text=ref[:120])

        fmt = check_zh_format(ref)
        check.has_author = fmt["has_author"]
        check.has_journal = fmt["has_journal"]
        check.has_year = fmt["has_year"]

        # Format heuristics cannot establish fabrication.
        if len(ref.strip()) < 20:
            check.status = "INCOMPLETE"
            check.issues.append("Citation text is short; inspect full bibliographic metadata")

        elif not check.has_author and not check.has_journal:
            check.status = "INCOMPLETE"
            check.issues.append("Author/journal not recognized by the format heuristic; verify the source metadata")

        elif not check.has_author or not check.has_journal or not check.has_year:
            check.status = "INCOMPLETE"
            missing = []
            if not check.has_author: missing.append("author")
            if not check.has_journal: missing.append("journal")
            if not check.has_year: missing.append("year")
            check.issues.append(f"Missing: {', '.join(missing)}")

        else:
            doi = has_doi(ref)
            check.has_doi = bool(doi)
            if doi:
                time.sleep(0.3)
                check.doi_resolves = verify_doi(doi)
                if not check.doi_resolves:
                    check.status = "SUSPICIOUS"
                    check.issues.append(f"Crossref lookup unsuccessful for {doi[:30]}; identity remains unverified, not proved invalid")
                else:
                    check.status = "SUSPICIOUS"
                    check.issues.append("DOI record resolves; compare title, authors, year and claim support before treating this citation as verified")
            else:
                check.status = "SUSPICIOUS"
                check.issues.append("No DOI in this row; verify through the original paper, publisher or authoritative Chinese index. A DOI is not required for a real source")

        if check.status == "VERIFIED": result.verified += 1
        elif check.status == "SUSPICIOUS": result.suspicious += 1
        elif check.status == "INCOMPLETE": result.incomplete += 1
        elif check.status == "FAKE": result.fake += 1
        result.checks.append(check)

    return result


def to_markdown(result: CitationVerificationZHResult) -> str:
    lines = [
        "# Chinese Citation Diagnostic Report",
        "",
        f"- Total citations: {result.total}",
        f"- Verified: {result.verified}",
        f"- Pending source verification (legacy suspicious count): {result.suspicious}",
        f"- Incomplete: {result.incomplete}",
        "- Scope: format and DOI availability only; no fabrication inference or complete citation verification is performed.",
        f"- Diagnostic status: {result.diagnostic_status}",
        "- Complete verification: not performed. Exit 0 / ok=true means diagnosis completed only; reuse valid source checks or inspect the source, not repeated runs of this heuristic.",
        "",
        "## Details",
        "",
        "| ID | Reference | Status | Issues |",
        "|---|---|---|---|",
    ]
    for c in result.checks:
        lines.append(f"| {c.candidate_id} | {c.reference_text[:60]} | {c.status} | {'; '.join(c.issues[:2])} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    result = check_citation_bank_zh(out_dir)

    if args.json:
        print(json.dumps({"ok": result.ok, "diagnostic_status": result.diagnostic_status,
                          "complete_verification": result.complete_verification,
                          "scope": "format_and_doi_availability_only",
                          "total": result.total, "verified": result.verified,
                          "suspicious": result.suspicious, "incomplete": result.incomplete,
                          "fake": result.fake}, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(to_markdown(result))

    if args.write:
        (out_dir / "citation_verification_zh.md").write_text(to_markdown(result), encoding="utf-8")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
