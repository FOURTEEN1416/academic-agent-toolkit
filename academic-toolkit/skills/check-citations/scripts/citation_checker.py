#!/usr/bin/env python3
"""citation_checker.py -- three-source academic citation verifier.

Verifies entries in one or more .bib files against CrossRef and OpenAlex
(Semantic Scholar is queried as a best-effort third source) to detect
AI-hallucinated, chimeric (real title + wrong authors) and modified
citations before submission.

Usage:
    python scripts/citation_checker.py references.bib
    python scripts/citation_checker.py path/to/report/
    python scripts/citation_checker.py references.bib --json
    python scripts/citation_checker.py references.bib --verbose

Exit codes:
    0    all citations verified
    1    one or more citations not found
    2    suspicious citations only (no hard failures)

Note: this is the skill-bundled three-source verifier. Do NOT confuse it
with ``academic-toolkit/tools/citation_checker.py``, which is a GB/T 7714
*format* checker that only accepts positional arguments.

No API keys are required: CrossRef, OpenAlex and the Semantic Scholar
public endpoint are used through their free tiers. When Semantic Scholar
rate-limits or errors out, the verdict falls back to the two core
sources (CrossRef + OpenAlex) automatically.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests

CROSSREF_API = "https://api.crossref.org"
OPENALEX_API = "https://api.openalex.org"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"

HTTP_TIMEOUT = 20          # seconds per API request
INTER_ENTRY_PAUSE = 0.4    # seconds between entries (be polite, free tiers)
TITLE_MATCH_RATIO = 0.92   # normalized-title similarity threshold
MAX_TITLE_CANDIDATES = 5   # rows fetched per title search

HEADERS = {
    "User-Agent": "check-citations/1.0 (academic-toolkit skill; free-tier use)",
    "Accept": "application/json",
}

DOI_RE = re.compile(r"10\.\d{4,9}/\S+")
ENTRY_RE = re.compile(r"@(\w+)\s*\{")
FIELD_RE = re.compile(r"(\w+)\s*=\s*")

VERIFIED = "verified"
SUSPICIOUS = "suspicious"
NOT_FOUND = "not_found"


# --------------------------------------------------------------------------
# BibTeX parsing
# --------------------------------------------------------------------------

def _skip_braced(text: str, start: int) -> int:
    """``start`` points at '{'; return the index just past its matching '}'."""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _read_value(body: str, i: int):
    """Read one BibTeX field value starting at ``i``; return (value, next_i)."""
    if i < len(body) and body[i] == "{":
        j = i + 1
        buf = []
        depth = 1
        while j < len(body):
            c = body[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            buf.append(c)
            j += 1
        return "".join(buf), j + 1
    if i < len(body) and body[i] == '"':
        j = i + 1
        buf = []
        while j < len(body):
            c = body[j]
            if c == "\\" and j + 1 < len(body):
                buf.append(body[j:j + 2])
                j += 2
                continue
            if c == '"':
                break
            buf.append(c)
            j += 1
        return "".join(buf), j + 1
    m = re.compile(r"[^,}]*").match(body, i)
    return m.group(0), m.end()


def _clean_field(value: str) -> str:
    value = value.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_")
    value = re.sub(r"\\[a-zA-Z]+", " ", value)  # drop TeX macros, keep args
    value = value.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", value).strip()


def parse_fields(body: str) -> dict:
    fields: dict = {}
    i, n = 0, len(body)
    while i < n:
        while i < n and body[i] in ", \t\r\n":
            i += 1
        if i >= n:
            break
        m = FIELD_RE.match(body, i)
        if not m:
            nxt = body.find(",", i)
            if nxt == -1:
                break
            i = nxt + 1
            continue
        name = m.group(1).lower()
        value, i = _read_value(body, m.end())
        fields[name] = _clean_field(value)
    return fields


def parse_bib(text: str) -> list:
    """Parse BibTeX text into a list of {key, type, fields} entries."""
    entries = []
    pos = 0
    while True:
        m = ENTRY_RE.search(text, pos)
        if not m:
            break
        etype = m.group(1).lower()
        end = _skip_braced(text, m.end() - 1)
        body = text[m.end():end - 1]
        if etype not in ("string", "preamble", "comment"):
            comma = body.find(",")
            if comma >= 0:
                key = body[:comma].strip().strip("{}")
                entries.append({
                    "key": key,
                    "type": etype,
                    "fields": parse_fields(body[comma + 1:]),
                })
        pos = end
    return entries


def parse_authors(field: str):
    """Return (surnames, full_names) for a BibTeX author field."""
    surnames, full_names = [], []
    for raw in re.split(r"\s+and\s+", field or "", flags=re.IGNORECASE):
        name = raw.strip().strip("{}")
        if not name or name.lower() == "others":
            continue
        if "," in name:
            surname = name.split(",")[0]
        else:
            parts = name.split()
            surname = parts[-1] if parts else ""
        surname = surname.strip().strip("{}")
        if surname:
            surnames.append(surname.lower())
            full_names.append(re.sub(r"\s+", " ", name).strip())
    return surnames, full_names


def parse_year(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    m = re.search(r"\d{4}", raw)
    if m:
        return int(m.group(0))
    if re.fullmatch(r"\d{1,2}", raw):  # two-digit legacy years
        v = int(raw)
        return 1900 + v if v < 30 else v
    return None


def extract_doi(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    m = DOI_RE.search(raw)
    return m.group(0).rstrip(".,;)") if m else ""


# --------------------------------------------------------------------------
# Matching helpers
# --------------------------------------------------------------------------

def norm_title(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def titles_match(bib_title: str, source_title: str) -> bool:
    a, b = norm_title(bib_title), norm_title(source_title)
    if not a or not b:
        return False
    if a == b:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= TITLE_MATCH_RATIO


def authors_overlap(bib_surnames, source_authors) -> bool:
    """True when any source author shares a surname token with the bib entry."""
    if not bib_surnames or not source_authors:
        return False
    bib_tokens = set()
    for surname in bib_surnames:
        parts = surname.split()
        bib_tokens.add(surname)
        if len(parts) > 1:
            bib_tokens.add(parts[-1])  # also match without 'van'/'de' prefixes
    for author in source_authors:
        for token in author.replace(",", " ").split():
            if token in bib_tokens:
                return True
    return False


# --------------------------------------------------------------------------
# Source queries (each returns a hit dict or None; raises on transport error)
# --------------------------------------------------------------------------

def _get_json(url: str, params: dict | None = None) -> dict:
    resp = requests.get(url, params=params, headers=HEADERS, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _doi_path(doi: str) -> str:
    return urllib.parse.quote(doi.strip(), safe="/._-")


def _crossref_hit(item: dict) -> dict:
    authors = []
    for author in item.get("author", []) or []:
        family = (author.get("family") or "").strip()
        if family:
            authors.append(family.lower())
    year = None
    issued = (item.get("issued") or {}).get("date-parts") or []
    if issued and issued[0]:
        year = issued[0][0]
    return {
        "source": "crossref",
        "title": " ".join(item.get("title") or []).strip(),
        "authors": authors,
        "year": year,
        "url": item.get("URL", "") or "",
    }


def _openalex_hit(item: dict) -> dict:
    authors = []
    for authorship in item.get("authorships", []) or []:
        name = (authorship.get("author") or {}).get("display_name", "")
        if name:
            authors.append(name.strip().lower())
    return {
        "source": "openalex",
        "title": (item.get("display_name") or "").strip(),
        "authors": authors,
        "year": item.get("publication_year"),
        "url": item.get("doi") or item.get("id", "") or "",
    }


def _semantic_scholar_hit(paper: dict) -> dict:
    authors = []
    for author in paper.get("authors", []) or []:
        name = (author.get("name") or "").strip()
        if name:
            authors.append(name.lower())
    return {
        "source": "semantic_scholar",
        "title": (paper.get("title") or "").strip(),
        "authors": authors,
        "year": paper.get("year"),
        "url": paper.get("url", "") or "",
    }


def query_crossref(doi: str, title: str):
    if doi:
        try:
            data = _get_json(f"{CROSSREF_API}/works/{_doi_path(doi)}")
            hit = _crossref_hit(data.get("message", {}))
            if titles_match(title, hit["title"]):
                return hit
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            # DOI unknown at CrossRef -> fall through to title search
    if title:
        data = _get_json(
            f"{CROSSREF_API}/works",
            {"query.bibliographic": title, "rows": MAX_TITLE_CANDIDATES},
        )
        for item in data.get("message", {}).get("items", []) or []:
            hit = _crossref_hit(item)
            if titles_match(title, hit["title"]):
                return hit
    return None


def query_openalex(doi: str, title: str):
    if doi:
        try:
            data = _get_json(f"{OPENALEX_API}/works/doi:{_doi_path(doi)}")
            hit = _openalex_hit(data)
            if titles_match(title, hit["title"]):
                return hit
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            # DOI unknown at OpenAlex -> fall through to title search
    if title:
        data = _get_json(
            f"{OPENALEX_API}/works",
            {"search": title, "per-page": MAX_TITLE_CANDIDATES},
        )
        for item in data.get("results", []) or []:
            hit = _openalex_hit(item)
            if titles_match(title, hit["title"]):
                return hit
    return None


def query_semantic_scholar(doi: str, title: str):
    """Best-effort third source: any transport error simply means 'no hit'."""
    fields = "title,year,authors,url"
    if doi:
        try:
            data = _get_json(
                f"{SEMANTIC_SCHOLAR_API}/paper/DOI:{_doi_path(doi)}", {"fields": fields}
            )
            hit = _semantic_scholar_hit(data)
            if titles_match(title, hit["title"]):
                return hit
        except requests.RequestException:
            pass  # rate-limited or unknown DOI: fall through to title search
    if title:
        data = _get_json(
            f"{SEMANTIC_SCHOLAR_API}/paper/search",
            {"query": title, "fields": fields, "limit": MAX_TITLE_CANDIDATES},
        )
        for paper in data.get("data") or []:
            hit = _semantic_scholar_hit(paper)
            if titles_match(title, hit["title"]):
                return hit
    return None


SOURCES = (
    ("crossref", query_crossref),
    ("openalex", query_openalex),
    ("semantic_scholar", query_semantic_scholar),
)


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------

def check_entry(entry: dict, source_file: str | None = None, verbose: bool = False) -> dict:
    fields = entry["fields"]
    title = fields.get("title", "")
    raw_doi = (fields.get("doi") or "").strip()
    doi = extract_doi(raw_doi)
    year = parse_year(fields.get("year", ""))
    bib_surnames, bib_full_names = parse_authors(fields.get("author", ""))
    current_year = datetime.date.today().year

    flags = []
    if raw_doi and not doi:
        flags.append(f"invalid DOI format: {raw_doi!r}")
    if year is None:
        flags.append("missing or unparsable year")
    elif year > current_year + 1:
        flags.append(f"future publication year: {year}")
    if not (fields.get("author") or "").strip():
        flags.append("missing author")
    for name in bib_full_names:
        if len(name.split()) == 1:
            flags.append(f"single-word author name: {name!r}")
    if re.search(r"comprehensive survey|systematic survey", norm_title(title)):
        flags.append("suspiciously generic title pattern")

    label = f"{entry['key']} ({source_file})" if source_file else entry["key"]
    if verbose:
        print(f"--- {label} ---", file=sys.stderr)
        print(f"    title: {title!r} | doi: {doi or '-'} | year: {year}", file=sys.stderr)

    hits: dict = {}
    errors: dict = {}
    for name, query in SOURCES:
        try:
            hit = query(doi, title)
            hits[name] = hit
        except requests.RequestException as exc:
            hits[name] = None
            errors[name] = f"{type(exc).__name__}: {exc}"
        if verbose:
            if name in errors:
                print(f"    [{name:16s}] error: {errors[name]}", file=sys.stderr)
            elif hits[name] is None:
                print(f"    [{name:16s}] no matching record", file=sys.stderr)
            else:
                h = hits[name]
                print(
                    f"    [{name:16s}] match: {h['title']!r} ({h['year']}) "
                    f"authors={h['authors'][:4]}",
                    file=sys.stderr,
                )

    matched = {
        name: hit
        for name, hit in hits.items()
        if hit and titles_match(title, hit["title"])
    }
    n_sources = len(matched)

    if "crossref" in errors and "openalex" in errors:
        # Both core sources unreachable: never guess, ask for a manual check.
        verdict = SUSPICIOUS
        flags.append(
            "core sources unreachable (crossref: {}; openalex: {}); manual check required".format(
                errors["crossref"], errors["openalex"]
            )
        )
    elif n_sources >= 2:
        overlap = any(
            authors_overlap(bib_surnames, hit["authors"]) for hit in matched.values()
        )
        if bib_surnames and not overlap:
            verdict = SUSPICIOUS
            flags.append(
                "chimeric citation: title matches real paper(s) but authors do not overlap"
            )
        else:
            verdict = VERIFIED
    elif n_sources == 1:
        verdict = SUSPICIOUS
        only = next(iter(matched.values()))
        if (
            bib_surnames
            and only["authors"]
            and not authors_overlap(bib_surnames, only["authors"])
        ):
            flags.append("single-source match with non-overlapping authors")
    else:
        verdict = NOT_FOUND

    if verbose:
        print(f"    => verdict: {verdict} | matched: {sorted(matched)}", file=sys.stderr)

    return {
        "key": entry["key"],
        "entry_type": entry["type"],
        "source_file": source_file,
        "title": title,
        "year": year,
        "doi": doi or raw_doi,
        "verdict": verdict,
        "sources_matched": sorted(matched),
        "chimeric": any("chimeric" in flag for flag in flags),
        "flags": flags,
        "source_errors": errors,
    }


# --------------------------------------------------------------------------
# I/O and reporting
# --------------------------------------------------------------------------

def collect_bib_files(path: str) -> list:
    target = Path(path)
    if target.is_dir():
        return sorted(target.rglob("*.bib"))
    if target.is_file():
        return [target]
    raise OSError(f"path not found: {path}")


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def print_human(results: list, summary: dict) -> None:
    print("== check-citations report ==")
    for r in results:
        desc = f"{r['key']}: \"{r['title']}\""
        if r["year"]:
            desc += f" ({r['year']})"
        if r.get("source_file"):
            desc += f" [{r['source_file']}]"
        extras = []
        if r["sources_matched"]:
            extras.append("sources: " + ", ".join(r["sources_matched"]))
        for flag in r["flags"]:
            extras.append(f"flag: {flag}")
        line = f"[{r['verdict'].upper():9s}] {desc}"
        if extras:
            line += " | " + "; ".join(extras)
        print(line)
    print("-" * 48)
    print(
        f"summary: {summary['total']} checked | {summary['verified']} verified | "
        f"{summary['suspicious']} suspicious | {summary['not_found']} not found"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify .bib citations against CrossRef, OpenAlex and Semantic Scholar; "
            "detect hallucinated and chimeric references."
        )
    )
    parser.add_argument("path", help=".bib file or a directory containing .bib files")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable JSON report")
    parser.add_argument("--verbose", action="store_true", help="print API query details to stderr")
    args = parser.parse_args(argv)

    try:
        bib_files = collect_bib_files(args.path)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not bib_files:
        print(f"error: no .bib file found at {args.path!r}", file=sys.stderr)
        return 1

    results = []
    for path in bib_files:
        text = read_text(path)
        for entry in parse_bib(text):
            results.append(check_entry(entry, source_file=str(path), verbose=args.verbose))
            time.sleep(INTER_ENTRY_PAUSE)

    summary = {
        "total": len(results),
        "verified": sum(1 for r in results if r["verdict"] == VERIFIED),
        "suspicious": sum(1 for r in results if r["verdict"] == SUSPICIOUS),
        "not_found": sum(1 for r in results if r["verdict"] == NOT_FOUND),
    }

    if args.json:
        print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    else:
        print_human(results, summary)

    if summary["not_found"]:
        return 1
    if summary["suspicious"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
