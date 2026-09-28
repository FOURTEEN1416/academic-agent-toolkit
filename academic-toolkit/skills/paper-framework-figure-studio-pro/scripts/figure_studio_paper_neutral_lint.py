#!/usr/bin/env python3
"""Configurable paper-neutral hardcoding lint for reusable skill packages.

The scanner is generic: it accepts release-time forbidden terms and derives the
file set from the package tree or zip. It does not embed any target-paper name,
method name, dataset, candidate id, or image count. Asset/vector libraries can
be excluded because retrieval metadata is not prompt doctrine; active-core files
remain linted.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".txt"}
DEFAULT_EXCLUDED_PARTS = {"assets", "__pycache__"}
DEFAULT_EXCLUDED_PREFIXES = {"references/vector-library/"}


@dataclass
class Finding:
    path: str
    term: str
    line_number: int
    excerpt: str


def is_text_path(name: str) -> bool:
    return Path(name).suffix.lower() in TEXT_SUFFIXES


def should_skip(name: str, include_assets: bool = False) -> bool:
    parts = set(Path(name).parts)
    if not include_assets and parts.intersection(DEFAULT_EXCLUDED_PARTS):
        return True
    if not include_assets and any(name.startswith(prefix) for prefix in DEFAULT_EXCLUDED_PREFIXES):
        return True
    return False


def iter_text_files(target: Path, include_assets: bool = False) -> Iterable[tuple[str, str]]:
    if target.is_dir():
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(target).as_posix()
            if should_skip(rel, include_assets=include_assets) or not is_text_path(rel):
                continue
            yield rel, path.read_text(encoding="utf-8", errors="replace")
    elif target.is_file() and target.suffix.lower() == ".zip":
        with zipfile.ZipFile(target) as zf:
            for info in sorted(zf.infolist(), key=lambda row: row.filename):
                if info.is_dir():
                    continue
                name = info.filename
                if should_skip(name, include_assets=include_assets) or not is_text_path(name):
                    continue
                yield name, zf.read(info).decode("utf-8", errors="replace")
    else:
        raise ValueError("target must be a directory or .zip file")


def compile_terms(terms: Iterable[str], ignore_case: bool = True) -> list[tuple[str, re.Pattern[str]]]:
    flags = re.IGNORECASE if ignore_case else 0
    compiled = []
    for term in terms:
        term = term.strip()
        if not term:
            continue
        compiled.append((term, re.compile(re.escape(term), flags)))
    return compiled


def scan(target: Path, terms: Iterable[str], include_assets: bool = False, ignore_case: bool = True) -> list[Finding]:
    patterns = compile_terms(terms, ignore_case=ignore_case)
    findings: list[Finding] = []
    for name, text in iter_text_files(target, include_assets=include_assets):
        for line_number, line in enumerate(text.splitlines(), start=1):
            for term, pattern in patterns:
                if pattern.search(line):
                    findings.append(Finding(name, term, line_number, line.strip()[:240]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--forbidden-term", action="append", default=[], help="Term that must not appear in active reusable files; repeatable")
    parser.add_argument("--terms-file", help="UTF-8 file with one forbidden term per line")
    parser.add_argument("--include-assets", action="store_true", help="Also scan assets/vector metadata; normally false")
    parser.add_argument("--case-sensitive", action="store_true")
    parser.add_argument("--json-output")
    parser.add_argument("--fail-on-match", action="store_true")
    args = parser.parse_args(argv)

    terms = list(args.forbidden_term)
    if args.terms_file:
        terms.extend(Path(args.terms_file).read_text(encoding="utf-8").splitlines())
    findings = scan(Path(args.target), terms, include_assets=args.include_assets, ignore_case=not args.case_sensitive)
    payload = {
        "schema_version": 1,
        "target": args.target,
        "scanned_forbidden_term_count": len([t for t in terms if t.strip()]),
        "include_assets": args.include_assets,
        "finding_count": len(findings),
        "findings": [asdict(f) for f in findings],
        "non_hardcoding_statement": "Forbidden terms are supplied at release time; the scanner itself does not encode a target paper, domain, candidate id, or image count.",
    }
    if args.json_output:
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if findings and args.fail_on_match:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
