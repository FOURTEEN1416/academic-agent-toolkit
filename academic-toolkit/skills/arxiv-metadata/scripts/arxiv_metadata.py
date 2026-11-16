#!/usr/bin/env python3
"""Fetch structured metadata for one arXiv paper and print it as JSON.

Accepts a bare ID (``2301.10140``), an old-style ID (``hep-ph/9901234``), or a
full arXiv URL (``https://arxiv.org/abs/2301.10140``). Uses the public arXiv
Atom API only (stdlib urllib + ElementTree, no third-party dependencies).

Usage (relative to this skill's directory)::

    ./scripts/arxiv_metadata.py 2301.10140
    ./scripts/arxiv_metadata.py https://arxiv.org/abs/2301.10140
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"
API_BASE = "https://export.arxiv.org/api/query"


def extract_arxiv_id(arg: str) -> str:
    """Normalize an arXiv ID or URL to the bare arXiv identifier."""
    value = arg.strip()
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+)", value)
    if match:
        value = match.group(1)
    return value.rstrip("/").removesuffix(".pdf")


def fetch_metadata(arg: str) -> dict:
    arxiv_id = extract_arxiv_id(arg)
    url = f"{API_BASE}?id_list={urllib.parse.quote(arxiv_id)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        root = ET.fromstring(resp.read())
    entry = root.find(f"{{{ATOM_NS}}}entry")
    if entry is None:
        raise SystemExit(f"arXiv entry not found for id: {arxiv_id}")

    title = (entry.findtext(f"{{{ATOM_NS}}}title", "") or "").strip().replace("\n", " ")
    authors = [
        (author.findtext(f"{{{ATOM_NS}}}name", "") or "").strip()
        for author in entry.findall(f"{{{ATOM_NS}}}author")
    ]
    published = (entry.findtext(f"{{{ATOM_NS}}}published", "") or "")[:10]
    primary = entry.find(f"{{{ARXIV_NS}}}primary_category")
    primary_category = primary.get("term") if primary is not None else None
    categories = [
        cat.get("term") for cat in entry.findall(f"{{{ATOM_NS}}}category") if cat.get("term")
    ]
    doi = (entry.findtext(f"{{{ARXIV_NS}}}doi", "") or "").strip() or None
    url_out = f"https://doi.org/{doi}" if doi else f"https://arxiv.org/abs/{arxiv_id}"

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": authors,
        "published": published,
        "primary_category": primary_category,
        "categories": categories,
        "doi": doi,
        "url": url_out,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-2].strip(), file=sys.stderr)
        return 2
    print(json.dumps(fetch_metadata(argv[1]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
