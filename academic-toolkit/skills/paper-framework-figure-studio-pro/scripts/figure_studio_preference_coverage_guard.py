#!/usr/bin/env python3
"""Validate S4/S5 preference-led first-round carryover coverage.

This validator is deliberately generic. It reads S3 preference signals, S4
candidate rows, or S5 prompt-index rows and checks whether every
user-preferred first-round candidate has at least one second-round
local-essence refinement for every active second-round style family.
It never assumes a project id, paper domain, fixed candidate id list,
paper-specific image count, or filename. It enforces the generic S5 cap of at most two second-round candidates.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[0]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from figure_studio_core.preference_carryover import (  # noqa: E402
    extract_preferred_candidate_ids,
    preference_coverage_audit,
    style_families_from_rows,
)


def read_json(path: str | None) -> Any:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows_from_json(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        for key in ("candidates", "formal_candidates", "candidate_matrix", "rows"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        if "candidate_map" in value and isinstance(value["candidate_map"], dict):
            return [row for row in value["candidate_map"].values() if isinstance(row, dict)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s3-record", action="append", default=[], help="S3 direction/issue/preference JSON file. Repeatable.")
    parser.add_argument("--candidate-matrix-json", help="S4 candidate matrix JSON, if available.")
    parser.add_argument("--prompt-index", help="S5 prompt-index JSON, if available.")
    parser.add_argument("--preferred-candidate-id", action="append", default=[], help="Explicit preferred first-round candidate id; repeatable.")
    parser.add_argument("--style-family", action="append", default=[], help="Explicit active S5 style family; repeatable.")
    parser.add_argument("--report", help="Write JSON report here.")
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args()

    records = [read_json(p) for p in args.s3_record]
    preferred = extract_preferred_candidate_ids(*records)
    for cid in args.preferred_candidate_id:
        if cid not in preferred:
            preferred.append(cid)

    rows: list[dict[str, Any]] = []
    for source in (read_json(args.candidate_matrix_json), read_json(args.prompt_index)):
        rows.extend(rows_from_json(source))

    styles = args.style_family or style_families_from_rows(rows)
    report = preference_coverage_audit(rows, preferred, styles)
    if not preferred:
        report["status"] = "PASS"
        report["note"] = "No preferred first-round candidate IDs were supplied or detected."
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.fail_on_error and report["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
