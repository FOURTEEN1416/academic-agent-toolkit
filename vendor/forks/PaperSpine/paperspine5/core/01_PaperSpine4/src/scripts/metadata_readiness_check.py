#!/usr/bin/env python3
"""Validate submission metadata without inventing unavailable author inputs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FIELDS = (
    "title",
    "authors",
    "affiliations",
    "corresponding_author",
    "funding",
    "conflicts",
    "ethics",
    "data_availability",
    "code_availability",
    "author_contributions",
    "ai_use_disclosure",
)
ALLOWED_STATES = {"provided", "not_applicable", "blinded"}


@dataclass
class MetadataResult:
    path: str
    ok: bool
    provided: int
    not_applicable: int
    blinded: int
    findings: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate submission_metadata.json.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def validate(path: Path) -> MetadataResult:
    findings: list[str] = []
    counts = {state: 0 for state in ALLOWED_STATES}
    if not path.is_file():
        return MetadataResult(str(path), False, 0, 0, 0, ["submission_metadata.json does not exist"])
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return MetadataResult(str(path), False, 0, 0, 0, [f"invalid JSON: {exc}"])
    fields = data.get("fields", {}) if isinstance(data, dict) else {}
    if not isinstance(fields, dict):
        findings.append("fields must be a JSON object")
        fields = {}
    for name in REQUIRED_FIELDS:
        entry = fields.get(name)
        if not isinstance(entry, dict):
            findings.append(f"fields.{name} is missing")
            continue
        state = str(entry.get("state") or "").strip().lower()
        if state not in ALLOWED_STATES:
            findings.append(f"fields.{name}.state must be provided, not_applicable, or blinded; got '{state or 'empty'}'")
            continue
        counts[state] += 1
        value = entry.get("value")
        has_value = bool(str(value).strip()) if not isinstance(value, list) else bool(value)
        reason = str(entry.get("reason") or "").strip()
        if state == "provided" and not has_value:
            findings.append(f"fields.{name} is provided but value is empty")
        if state in {"not_applicable", "blinded"} and not reason:
            findings.append(f"fields.{name} is {state} but reason is empty")
    return MetadataResult(
        str(path),
        not findings,
        counts["provided"],
        counts["not_applicable"],
        counts["blinded"],
        findings,
    )


def to_markdown(result: MetadataResult) -> str:
    lines = [
        "# Metadata Readiness Check",
        "",
        f"- Path: `{result.path}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Provided: {result.provided}",
        f"- Not applicable: {result.not_applicable}",
        f"- Blinded: {result.blinded}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in result.findings) if result.findings else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    result = validate(output_dir / "submission_metadata.json")
    markdown = to_markdown(result)
    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "metadata_readiness_check.md").write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
