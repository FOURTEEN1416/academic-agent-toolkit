#!/usr/bin/env python3
"""Validate S3 -> S4/S5 preference carryover generically.

The guard derives preferences, S5 candidate rows, styles, and prompts from
project artifacts. It never assumes a paper topic, project id, candidate id,
image count, page count, or fixed filename beyond user-supplied paths.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from figure_studio_core.preference_carryover import (
    parse_markdown_table,
    preference_ids_from_sources,
    read_json,
    validate_preference_carryover,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Project run directory.")
    parser.add_argument("--prompt-index", required=True, help="S5 prompt-index path, absolute or run-relative.")
    parser.add_argument("--preference-source", action="append", default=[], help="JSON file(s) containing S3 preference carryover data. Repeatable.")
    parser.add_argument("--preferred-id", action="append", default=[], help="Explicit preferred source candidate id. Repeatable; useful when the user prompt is the only source.")
    parser.add_argument("--matrix", action="append", default=[], help="Optional S4 candidate matrix JSON or markdown table. Repeatable.")
    parser.add_argument("--report", help="Write guard report JSON.")
    args = parser.parse_args(argv)

    run = Path(args.run_dir).resolve()
    prompt_index_path = Path(args.prompt_index)
    if not prompt_index_path.is_absolute():
        prompt_index_path = run / prompt_index_path
    prompt_index = read_json(prompt_index_path)

    pref_paths = []
    for src in args.preference_source:
        p = Path(src)
        pref_paths.append(p if p.is_absolute() else run / p)
    preferred = []
    preferred.extend(args.preferred_id or [])
    preferred.extend(preference_ids_from_sources(pref_paths))
    # preserve order
    preferred = list(dict.fromkeys(preferred))

    matrix_rows = []
    for src in args.matrix:
        p = Path(src)
        p = p if p.is_absolute() else run / p
        if not p.is_file():
            continue
        if p.suffix.lower() == ".json":
            data = read_json(p)
            if isinstance(data, list):
                matrix_rows.extend([row for row in data if isinstance(row, dict)])
            elif isinstance(data, dict):
                rows = data.get("candidates") or data.get("rows") or data.get("matrix") or []
                if isinstance(rows, list):
                    matrix_rows.extend([row for row in rows if isinstance(row, dict)])
        else:
            matrix_rows.extend(parse_markdown_table(p))

    report = validate_preference_carryover(prompt_index, preferred, prompt_root=run, matrix_rows=matrix_rows)
    if args.report:
        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = run / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
