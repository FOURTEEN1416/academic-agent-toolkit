#!/usr/bin/env python3
"""Plan or validate S4/S5 preferred-source coverage.

This utility is deliberately paper-agnostic. It never assumes a paper topic,
fixed first-round candidate IDs, fixed paper-specific image count, or a fixed
number of style slots. Coverage is derived only from explicit user-preferred
first-round IDs recorded by S3 and the style/treatment slots declared by S4.
v3.2.15f enforces the public S5 cap: the second-round/formal candidate set must
fit within exactly two rows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from figure_studio_core.formal_matrix import (
    generate_preference_covered_formal_candidate_matrix,
    preference_coverage_report,
)


def load_json(path: str | None) -> Any:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def extract_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        for key in ("formal_candidate_matrix", "candidates", "rows", "matrix"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def parse_style_slot(raw: str) -> dict[str, str]:
    # Accept either a plain style id or a JSON object, without assuming any style vocabulary.
    raw = raw.strip()
    if not raw:
        raise ValueError("empty style slot")
    if raw.startswith("{"):
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("style JSON must be an object")
        return {str(k): str(v) for k, v in value.items()}
    return {"style_id": raw, "style_label": raw, "visual_treatment": raw}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="generate a preference-covered formal candidate matrix")
    p_plan.add_argument("--preferred-id", action="append", default=[], help="S3-recorded preferred first-round candidate id; repeatable")
    p_plan.add_argument("--style", action="append", default=[], help="S4 style/treatment slot; plain id or JSON object; repeatable")
    p_plan.add_argument("--default-count", type=int, default=2, help="caller-supplied default S5 candidate count")
    p_plan.add_argument("--max-count", type=int, help="second-round maximum candidate count; values above the skill cap are reduced to the cap")
    p_plan.add_argument("--id-prefix", default="F")
    p_plan.add_argument("--json-output")

    p_validate = sub.add_parser("validate", help="validate preference x style coverage in an existing matrix")
    p_validate.add_argument("--matrix-json", required=True)
    p_validate.add_argument("--preferred-id", action="append", default=[])
    p_validate.add_argument("--style", action="append", default=[])
    p_validate.add_argument("--json-output")
    p_validate.add_argument("--fail-on-error", action="store_true")

    args = parser.parse_args(argv)
    styles = [parse_style_slot(raw) for raw in getattr(args, "style", [])]

    if args.command == "plan":
        try:
            rows = generate_preference_covered_formal_candidate_matrix(
                preferred_source_ids=args.preferred_id,
                style_slots=styles,
                default_count=args.default_count,
                max_count=args.max_count,
                id_prefix=args.id_prefix,
            )
            report = preference_coverage_report(rows, preferred_source_ids=args.preferred_id, style_slots=styles)
            status = report["status"]
        except ValueError as exc:
            rows = []
            report = {
                "schema_version": 1,
                "status": "REDO_REQUIRED",
                "redo_required": True,
                "error": str(exc),
                "instruction": "Redo S4 candidate-matrix planning with a feasible style-slot/preference allocation that fits the two-candidate S5 cap before S5 handoff.",
            }
            status = "REDO_REQUIRED"
        payload = {
            "schema_version": 1,
            "command": "plan",
            "status": status,
            "candidate_count": len(rows),
            "candidates": rows,
            "coverage_report": report,
            "requested_max_count": args.max_count,
            "max_count_policy": "The S5 second-round/formal candidate set must never exceed the configured two-candidate skill cap; if coverage cannot fit, redo S4 planning before S5.",
            "non_hardcoding_statement": "Candidate count and coverage derive from explicit preferred ids and style slots; no paper-specific count or project-specific ids are encoded.",
        }
    else:
        rows = extract_rows(load_json(args.matrix_json))
        report = preference_coverage_report(rows, preferred_source_ids=args.preferred_id, style_slots=styles)
        payload = {
            "schema_version": 1,
            "command": "validate",
            "status": report["status"],
            "candidate_count": len(rows),
            "coverage_report": report,
        }

    if getattr(args, "json_output", None):
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.command == "validate" and args.fail_on_error and payload["status"] != "PASS":
        return 2
    if payload.get("status") == "REDO_REQUIRED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
