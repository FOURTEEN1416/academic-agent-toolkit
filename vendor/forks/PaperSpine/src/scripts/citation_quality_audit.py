#!/usr/bin/env python3
"""Citation Quality Audit — teaching-oriented citation analysis for PaperSpine.

Goes beyond DOI verification.  Each citation is scored across three axes
(resolvability, recency, field relevance).  The report identifies diversity gaps,
recommends replacements for dead citations, and produces a scene-specific
citation strategy section that teaches the user *why* certain citation types
matter for their target venue.

Pattern: follows the writing_rationale_matrix philosophy — every analysis row
teaches the user something about citation strategy.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from _paper_spine_utils import markdown_tables

DOI_RE = re.compile(
    r"\b(?:doi\s*[:=]\s*|https?://doi\.org/|https?://dx\.doi\.org/)?(10\.\d{4,}/[^\s,;)\]]+)",
    re.IGNORECASE,
)
ARXIV_RE = re.compile(r"\barxiv\s*:?\s*(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)
CROSSREF_URL = "https://api.crossref.org/works/"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/DOI:"
USER_AGENT = "PaperSpine/3.0 (citation-quality; https://github.com/WUBING2023/PaperSpine)"
VALID_VERIFICATION_VALUES = {"yes", "verified", "pass", "true"}
EXTERNAL_CHANNEL_TOKENS = (
    "web",
    "mcp",
    "crossref",
    "pubmed",
    "scholar",
    "semantic scholar",
    "ieee",
    "cnki",
    "wos",
    "publisher",
    "journal",
    "conference",
    "proceedings",
    "arxiv",
    "preprint",
    "regulatory",
    "database",
)
MANUAL_VERIFICATION_TOKENS = (
    "confirmed",
    "verified",
    "accessed",
    "publisher",
    "official",
    "crossref",
    "pubmed",
    "arxiv",
    "database",
    "metadata",
    "proceedings",
    "repository",
    "website",
)


# ---------------------------------------------------------------------------
# citation-type taxonomy
# ---------------------------------------------------------------------------

CITATION_TYPES = {
    "sota": "direct task or state-of-the-art paper",
    "foundational": "foundational method or theory paper",
    "benchmark": "dataset, benchmark, or evaluation protocol paper",
    "survey": "survey, review, or meta-analysis",
    "application": "domain-application or impact paper",
    "critique": "limitation, robustness, reproducibility, or ethics paper",
}

SCENE_CITATION_GUIDANCE: dict[str, dict[str, str]] = {
    "journal": {
        "sota": "Must cite the 3-5 most recent competing methods. Missing these is a desk-reject risk.",
        "foundational": "Cite the 2-3 methods your work builds on. Explain inheritance clearly.",
        "benchmark": "Cite the datasets you evaluate on. Report dataset statistics.",
        "survey": "Cite 1-2 recent surveys to position your work in the broader landscape.",
        "application": "Optional unless your contribution is application-motivated.",
        "critique": "Include 1-2 limitation/robustness papers to show awareness of field challenges.",
    },
    "conference": {
        "sota": "Cite the 5-8 most recent competing methods. Conference reviewers check recency aggressively.",
        "foundational": "Cite the 2-3 methods you build on. Be specific about what you inherit vs. change.",
        "benchmark": "Cite all datasets used. Standard benchmarks are expected.",
        "survey": "Cite 1 recent survey if it helps position your work concisely.",
        "application": "Optional.",
        "critique": "Optional but helpful for discussion section.",
    },
    "report_review": {
        "sota": "Cite representative methods across the field. Breadth matters more than exhaustiveness.",
        "foundational": "Cite the key methods that define the field. Explain their contributions.",
        "benchmark": "Cite datasets if you use them.",
        "survey": "Essential: cite 3-5 surveys to establish the review's coverage.",
        "application": "Include application papers that show real-world relevance.",
        "critique": "Include limitation/robustness discussions to show balanced coverage.",
    },
    "competition": {
        "sota": "Cite the top-3 solutions from prior competitions or leaderboards.",
        "foundational": "Cite the base methods your solution extends.",
        "benchmark": "Cite the competition dataset and evaluation protocol.",
        "survey": "Optional.",
        "application": "Cite real-world applications if your solution targets practical deployment.",
        "critique": "Cite known limitations of competing approaches.",
    },
}


# ---------------------------------------------------------------------------
# data types
# ---------------------------------------------------------------------------

@dataclass
class CitationQualityEntry:
    candidate_id: str
    doi: str
    reference: str
    year: str
    source: str = ""
    source_channel: str = ""
    verified: str = ""
    verification_note: str = ""
    # verification
    doi_resolves: bool = False
    crossref_title: str | None = None
    api_year: int | None = None
    title_similarity: float = 0.0
    year_matches: bool = False
    # quality scores (0-100)
    resolvability_score: int = 0
    recency_score: int = 0
    # classification
    citation_type: str = "sota"
    # assessment
    status: str = "pending"     # verified | mismatched | dead | error
    issues: list[str] = field(default_factory=list)
    teaching_note: str = ""
    manual_identifier: str = ""


@dataclass
class CitationQualityReport:
    output_dir: str
    scene: str
    target_count: int
    entries: list[CitationQualityEntry] = field(default_factory=list)
    gap_analysis: dict[str, str] = field(default_factory=dict)
    replacement_recommendations: list[str] = field(default_factory=list)
    overall_score: int = 0

    @property
    def verified_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "verified")

    @property
    def dead_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "dead")

    @property
    def mismatched_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "mismatched")

    @property
    def error_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "error")

    @property
    def pending_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "pending")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Citation quality audit for PaperSpine.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write citation_quality_audit.md")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--no-api", action="store_true", help="Skip API calls; analyze structure only")
    parser.add_argument("--max-dois", type=int, default=30, help="Maximum DOIs to verify via API (default: 30)")
    parser.add_argument("--min-score", type=int, default=60, help="Minimum overall score for PASS (default: 60)")
    parser.add_argument("--max-error-ratio", type=float, default=0.30, help="Maximum error ratio for PASS (default: 0.30)")
    parser.add_argument("--max-pending-ratio", type=float, default=0.50, help="Maximum pending ratio for PASS (default: 0.50)")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# DOI extraction and API verification
# ---------------------------------------------------------------------------

def extract_dois(text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in DOI_RE.finditer(text):
        doi = match.group(1).rstrip(".")
        clean = doi.lower().strip()
        if clean not in seen:
            seen.add(clean)
            result.append(doi)
    return result


def parse_citation_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    header, rows = find_citation_table(text)
    if not rows:
        return []
    result: list[dict[str, str]] = []

    index = {normalize_header(cell): i for i, cell in enumerate(header)}

    def cell(row: list[str], *names: str, fallback: int | None = None) -> str:
        for name in names:
            idx = index.get(name)
            if idx is not None and idx < len(row):
                return row[idx]
        if fallback is not None and fallback < len(row):
            return row[fallback]
        return ""

    for row in rows:
        if len(row) < 6:
            continue
        joined = " ".join(row)
        dois = extract_dois(joined)
        result.append({
            "candidate_id": cell(row, "candidate id", "id", fallback=0),
            "reference": cell(row, "reference/bibtex", "reference", "citation", "bibtex", fallback=1),
            "year": cell(row, "year", fallback=2),
            "doi": dois[0] if dois else "",
            "source": cell(row, "source"),
            "source_channel": cell(row, "source channel"),
            "verified": cell(row, "verified"),
            "verification_note": cell(row, "verification note"),
        })
    return result


def normalize_header(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[*_`]", "", value)
    return re.sub(r"\s+", " ", value.strip().lower())


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


def title_similarity(a: str, b: str) -> float:
    a_words = re.sub(r"[^a-z0-9]+", " ", a.lower()).strip().split()
    b_words = re.sub(r"[^a-z0-9]+", " ", b.lower()).strip().split()
    if not a_words or not b_words:
        return 0.0
    a_set = set(a_words)
    b_set = set(b_words)
    jaccard = len(a_set & b_set) / len(a_set | b_set)
    sm = SequenceMatcher(None, " ".join(a_words), " ".join(b_words))
    return round(jaccard * 0.5 + sm.ratio() * 0.5, 4)


def extract_reference_title(reference: str) -> str:
    """Extract the cited work title from a reference cell.

    The audit should compare Crossref's title against the paper title, not the
    whole reference string with authors, venue, pages, DOI, and notes.
    """
    if not reference:
        return ""
    bibtex = re.search(r"title\s*=\s*[\{\"]([^{}\"]+)[\}\"]", reference, re.IGNORECASE)
    if bibtex:
        return re.sub(r"\s+", " ", bibtex.group(1)).strip()

    quoted = re.search(r'["“”]([^"“”]{8,})["“”]', reference)
    if quoted:
        return re.sub(r"\s+", " ", quoted.group(1)).strip(" .")

    text = re.sub(r"\b(?:doi\s*[:=]\s*|https?://doi\.org/|https?://dx\.doi\.org/)?10\.\d{4,}/\S+", " ", reference, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    year_match = re.search(r"\((?:19|20)\d{2}\)\.\s+", text)
    if year_match:
        start = year_match.end()
        tail = text[start:]
        venue_match = re.search(r"\.\s+(?:\*|[A-Z][A-Za-z& ]{2,}[,;]|\barXiv:|\b[A-Z]{2,}\b)", tail)
        title = tail[: venue_match.start()] if venue_match else tail
        return title.strip(" \"'“”‘’.")

    # Fallback: remove obvious leading author/year fragments and stop before DOI.
    text = re.sub(r"^.*?\b(?:19|20)\d{2}\b[).,:]*\s*", "", text)
    text = re.sub(r"\s+(?:DOI|doi|https?://).*$", "", text).strip()
    return text.strip(" \"'“”‘’.")


def fetch_crossref(doi: str, timeout: int) -> dict | None:
    try:
        req = Request(CROSSREF_URL + doi, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            msg = data.get("message", {})
            title_list = msg.get("title", [])
            year = msg.get("published-print", {}).get("date-parts", [[None]])[0][0]
            if year is None:
                year = msg.get("created", {}).get("date-parts", [[None]])[0][0]
            return {"title": title_list[0] if title_list else None, "year": year}
    except Exception:
        return None


def extract_manual_identifier(record: dict[str, str]) -> str:
    joined = " ".join(record.get(key, "") for key in ("reference", "source", "verification_note"))
    arxiv = ARXIV_RE.search(joined)
    if arxiv:
        return f"arXiv:{arxiv.group(1)}"
    url = URL_RE.search(joined)
    if url:
        return url.group(0).rstrip(".,;")
    return ""


def is_external_channel(source_channel: str, source: str = "") -> bool:
    text = f"{source_channel} {source}".lower()
    return any(token in text for token in EXTERNAL_CHANNEL_TOKENS)


def has_manual_verification(record: dict[str, str]) -> bool:
    verified = normalize_header(record.get("verified", ""))
    note = record.get("verification_note", "").strip()
    if verified not in VALID_VERIFICATION_VALUES or len(note) < 12:
        return False
    note_lower = note.lower()
    if any(token in note_lower for token in ("todo", "tbd", "pending", "[verify]", "unknown")):
        return False
    if any(token in note_lower for token in MANUAL_VERIFICATION_TOKENS):
        return True
    return bool(extract_manual_identifier(record))


def classify_citation_type(reference: str) -> str:
    text = reference.lower()
    if any(w in text for w in ("survey", "review", "meta-analysis", "综述", "回顾")):
        return "survey"
    if any(w in text for w in ("benchmark", "dataset", "corpus", "evaluation", "数据集")):
        return "benchmark"
    if any(w in text for w in ("limitation", "robustness", "reproducib", "bias", "fairness")):
        return "critique"
    if any(w in text for w in ("application", "real-world", "deployment", "clinical", "应用")):
        return "application"
    if any(w in text for w in ("foundation", "seminal", "classic", "theory", "theorem")):
        return "foundational"
    return "sota"


def compute_recency_score(year: str | None, current_year: int = 2026) -> int:
    if year is None:
        return 30
    try:
        y = int(year)
    except (ValueError, TypeError):
        return 30
    if y >= current_year:
        return 100
    if y >= current_year - 2:
        return 90
    if y >= current_year - 4:
        return 70
    if y >= current_year - 7:
        return 50
    return 20


# ---------------------------------------------------------------------------
# main audit logic
# ---------------------------------------------------------------------------

def audit_citations(output_dir: Path, no_api: bool, timeout: int, delay: float, max_dois: int = 30) -> CitationQualityReport:
    config_path = output_dir / "paper_spine_config.json"
    config = {}
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))

    scene = config.get("scene", "journal")
    target_count = config.get("citation_target_count", 20)
    report = CitationQualityReport(str(output_dir), scene, target_count)

    bank_path = output_dir / "citation_support_bank.md"
    if not bank_path.exists():
        return report

    records = parse_citation_rows(bank_path)
    if not records:
        return report

    records = records[:max_dois]
    for record in records:
        entry = CitationQualityEntry(
            candidate_id=record["candidate_id"],
            doi=record["doi"],
            reference=record["reference"],
            year=record["year"],
            source=record.get("source", ""),
            source_channel=record.get("source_channel", ""),
            verified=record.get("verified", ""),
            verification_note=record.get("verification_note", ""),
            citation_type=classify_citation_type(record["reference"]),
            recency_score=compute_recency_score(record["year"]),
        )

        if not entry.doi:
            entry.manual_identifier = extract_manual_identifier(record)
            if has_manual_verification(record) and entry.manual_identifier:
                entry.status = "verified"
                entry.doi_resolves = True
                entry.resolvability_score = 80
                entry.teaching_note = (
                    "Citation verified through a non-DOI channel recorded in the citation bank. "
                    "This is acceptable for arXiv preprints, official policy pages, proceedings, "
                    "and publisher/database records when the verification note is specific."
                )
            elif has_manual_verification(record):
                # Verified flag is set, but no stable identifier (DOI/arXiv/URL)
                # was recorded — this is self-attestation without independent
                # evidence, so it must not reach verified status or a high score.
                entry.status = "pending"
                entry.resolvability_score = 35
                entry.issues.append(
                    "Verified flag set but no stable identifier (DOI, arXiv ID, or URL) "
                    "found in the row; self-attestation alone cannot confirm the citation"
                )
                entry.teaching_note = (
                    "A Verified=yes flag is not enough on its own. Record a stable identifier "
                    "(DOI, arXiv ID, or URL) in the reference, source, or verification note so the "
                    "citation can be independently re-checked. Until then this row stays unverified."
                )
            else:
                entry.status = "error"
                if is_external_channel(entry.source_channel, entry.source):
                    entry.issues.append(
                        "No DOI found and no sufficient external verification note was recorded"
                    )
                    entry.teaching_note = (
                        "Non-DOI sources are acceptable only when the bank records a stable identifier "
                        "(such as arXiv ID or URL), Verified=yes/verified/pass/true, and a concrete "
                        "verification note naming the official page, publisher, database, or metadata check."
                    )
                else:
                    entry.issues.append("No DOI or stable external identifier found in citation entry")
                    entry.teaching_note = (
                        "Every citation should include a DOI, URL, arXiv ID, or local metadata note. "
                        "Without one, the reference cannot be verified and readers cannot easily locate the source."
                    )
                entry.resolvability_score = 0
            report.entries.append(entry)
            continue

        if no_api:
            # Offline: a DOI is itself a stable, re-checkable identifier. Honor the
            # bank's verification columns instead of forcing every DOI row to pending,
            # so a properly verified bank can pass structural-only (--no-api) analysis.
            entry.manual_identifier = entry.doi
            if has_manual_verification(record):
                entry.status = "verified"
                entry.doi_resolves = True  # structurally verifiable, not network-confirmed
                entry.resolvability_score = 80
                entry.teaching_note = (
                    "Offline mode: DOI present and the bank records Verified=yes with a specific "
                    "note. Accepted as structurally verifiable (not network-confirmed)."
                )
            else:
                entry.resolvability_score = 50
            report.entries.append(entry)
            continue

        crossref = fetch_crossref(entry.doi, timeout)
        time.sleep(delay)

        if crossref is None:
            entry.status = "dead"
            entry.resolvability_score = 0
            entry.issues.append(f"DOI {entry.doi} does not resolve via Crossref")
            entry.teaching_note = "Dead DOIs suggest the citation was hallucinated or the paper was retracted. Replace with a verified alternative or remove the citation."
            report.entries.append(entry)
            continue

        entry.doi_resolves = True
        entry.crossref_title = crossref.get("title")
        entry.api_year = crossref.get("year")

        reference_title = extract_reference_title(entry.reference)
        comparison_title = reference_title or entry.reference
        if entry.crossref_title and comparison_title:
            sim = title_similarity(entry.crossref_title, comparison_title)
            entry.title_similarity = sim
            if sim >= 0.75:
                entry.status = "verified"
                entry.resolvability_score = 100
                entry.teaching_note = "Citation verified: DOI resolves and title matches."
            elif sim >= 0.50:
                entry.status = "mismatched"
                entry.resolvability_score = 40
                entry.issues.append(f"Title similarity {sim:.2f} below 0.75 threshold. Crossref title: '{entry.crossref_title[:100]}'")
                entry.teaching_note = f"Partial title match ({sim:.0%}). The DOI resolves but the title doesn't match your citation text. Check whether the DOI is correct or the citation text needs updating."
            else:
                entry.status = "mismatched"
                entry.resolvability_score = 20
                entry.issues.append(f"Title similarity {sim:.2f} — likely wrong DOI. Crossref title: '{entry.crossref_title[:100]}'")
                entry.teaching_note = f"Poor title match ({sim:.0%}). This likely means the DOI points to a different paper than the one you're citing. Verify manually."
        else:
            entry.status = "verified"
            entry.resolvability_score = 80

        if entry.api_year and entry.year:
            try:
                entry.year_matches = int(entry.year) == entry.api_year
            except ValueError:
                pass
            if not entry.year_matches:
                entry.issues.append(f"Year mismatch: bank={entry.year}, API={entry.api_year}")
                entry.teaching_note += " Year mismatch between citation bank and API — verify the publication date."

        report.entries.append(entry)

    # ---- gap analysis ----
    type_counts: dict[str, int] = {k: 0 for k in CITATION_TYPES}
    for entry in report.entries:
        type_counts[entry.citation_type] = type_counts.get(entry.citation_type, 0) + 1
    total = len(report.entries) or 1

    for ctype, label in CITATION_TYPES.items():
        count = type_counts[ctype]
        ratio = count / total
        guidance = SCENE_CITATION_GUIDANCE.get(scene, {}).get(ctype, "")
        if ratio < 0.05 and ctype != "critique":
            report.gap_analysis[ctype] = (
                f"**Missing {label}s.** Only {count} of {total} entries ({ratio:.0%}). "
                f"{guidance} Consider adding 1-3 {label} references."
            )

    # ---- replacement recommendations for dead citations ----
    dead_entries = [e for e in report.entries if e.status == "dead"]
    if dead_entries:
        report.replacement_recommendations.append(
            f"{len(dead_entries)} dead DOIs detected. For each: (1) verify the paper exists via Google Scholar, "
            "(2) find the correct DOI, (3) update the citation bank, (4) re-run this audit."
        )

    # ---- overall score ----
    if report.entries:
        scores = [(e.resolvability_score + e.recency_score) / 2 for e in report.entries]
        report.overall_score = int(sum(scores) / len(scores))

    return report


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def to_markdown(report: CitationQualityReport, status: str = "") -> str:
    lines = [
        "# Citation Quality Audit",
        "",
        f"- Output directory: `{report.output_dir}`",
        f"- Scene: {report.scene}",
        f"- Target citation count: {report.target_count}",
        f"- Entries analyzed: {len(report.entries)}",
        f"- Verified: {report.verified_count} | Mismatched: {report.mismatched_count} | Dead: {report.dead_count}",
        f"- Overall quality score: {report.overall_score}/100",
    ]
    if status:
        lines.append(f"- Status: {status}")
    lines.extend([
        "",
        "> Each entry below includes a teaching note explaining *why* the citation quality matters.",
        "",
        "## Per-Citation Analysis",
        "",
        "| ID | DOI | Type | Resolves | Title Match | Year Match | Score | Status |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for e in report.entries:
        identifier = e.doi[:30] if e.doi else (e.manual_identifier[:30] if e.manual_identifier else "-")
        lines.append(
            f"| {e.candidate_id} | {identifier} | {e.citation_type} | "
            f"{'yes' if e.doi_resolves else 'no'} | {e.title_similarity:.0%} | "
            f"{'yes' if e.year_matches else 'no'} | {((e.resolvability_score + e.recency_score) // 2)} | "
            f"{e.status} |"
        )
    lines.append("")

    # detailed entries with teaching notes
    for e in report.entries:
        if e.status == "verified":
            continue
        lines.append(f"### {e.candidate_id} — {e.doi}")
        lines.append("")
        lines.append(f"Status: **{e.status}**")
        if e.issues:
            lines.append("")
            lines.extend(f"- {issue}" for issue in e.issues)
        if e.teaching_note:
            lines.append("")
            lines.append(f"> {e.teaching_note}")
        lines.append("")

    # gap analysis
    if report.gap_analysis:
        lines.append("## Citation Diversity Gaps")
        lines.append("")
        for analysis in report.gap_analysis.values():
            lines.append(analysis)
            lines.append("")
        lines.append("")

    # replacement recommendations
    if report.replacement_recommendations:
        lines.append("## Replacement Recommendations")
        lines.append("")
        for rec in report.replacement_recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    # scene-specific guidance
    lines.append("## Scene-Specific Citation Strategy")
    lines.append("")
    lines.append(f"For **{report.scene}** papers, your citation strategy should:")
    lines.append("")
    guidance = SCENE_CITATION_GUIDANCE.get(report.scene, {})
    for ctype, guide in guidance.items():
        lines.append(f"- **{CITATION_TYPES[ctype]}**: {guide}")
    lines.append("")

    # top-level teaching
    lines.append("## Citation Strategy Principles")
    lines.append("")
    lines.append("- **Diversity over density.** A narrow citation pool makes your Introduction read as insular. "
                 "Mix SOTA, foundational, benchmark, survey, and application papers.")
    lines.append("- **Recency signals engagement.** Most citations should be from the last 3 years. "
                 "Older citations are fine for foundational work, but they need a reason to be there.")
    lines.append("- **Verifiability is non-negotiable.** Every DOI must resolve. A dead DOI in your final paper "
                 "is a credibility failure that reviewers notice immediately.")
    lines.append("- **Type matters by venue.** Journals expect deep SOTA coverage. Reports expect broad survey coverage. "
                 "Competitions expect benchmark and leaderboard coverage. Match your strategy to your scene.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    if not out_dir.is_dir():
        print(f"Output directory not found: {out_dir}", file=sys.stderr)
        return 2

    report = audit_citations(out_dir, args.no_api, args.timeout, args.delay, args.max_dois)

    total = len(report.entries) or 1
    error_ratio = report.error_count / total
    pending_ratio = report.pending_count / total
    failures: list[str] = []

    if report.overall_score < args.min_score:
        failures.append(f"Overall score {report.overall_score} below minimum {args.min_score}")
    if error_ratio > args.max_error_ratio:
        failures.append(f"Error ratio {error_ratio:.2f} exceeds maximum {args.max_error_ratio}")
    if pending_ratio > args.max_pending_ratio:
        failures.append(f"Pending ratio {pending_ratio:.2f} exceeds maximum {args.max_pending_ratio}")

    status = "PASS" if not failures else "FAIL"

    if args.json:
        print(json.dumps({
            "output_dir": str(out_dir), "scene": report.scene,
            "verified": report.verified_count, "mismatched": report.mismatched_count,
            "dead": report.dead_count, "overall_score": report.overall_score,
            "status": status, "error_count": report.error_count,
            "pending_count": report.pending_count,
            "error_ratio": round(error_ratio, 4),
            "pending_ratio": round(pending_ratio, 4),
            "failures": failures,
            "gap_analysis": report.gap_analysis,
        }, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(to_markdown(report, status))

    if args.write:
        report_path = out_dir / "citation_quality_audit.md"
        report_path.write_text(to_markdown(report, status), encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
