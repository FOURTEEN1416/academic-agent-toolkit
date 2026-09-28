#!/usr/bin/env python3
"""Validate and summarize observable model-usage telemetry from JSONL."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "reasoning_tokens", "output_tokens")
REQUIRED_FIELDS = ("timestamp", "stage", "role", "model", "reasoning_effort", "usage_source", "gate_result", "retry")
USAGE_SOURCES = {"api", "host", "telemetry_unavailable"}


@dataclass
class UsageResult:
    path: str
    ok: bool
    status: str
    event_count: int
    unavailable_count: int
    totals: dict[str, int]
    by_stage: dict[str, dict[str, int]]
    findings: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate usage_ledger.jsonl and aggregate tokens by stage.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def validate(path: Path) -> UsageResult:
    findings: list[str] = []
    totals = {field: 0 for field in TOKEN_FIELDS}
    by_stage: dict[str, dict[str, int]] = defaultdict(lambda: {field: 0 for field in TOKEN_FIELDS})
    if not path.is_file():
        return UsageResult(str(path), False, "FAIL", 0, 0, totals, {}, ["usage_ledger.jsonl does not exist"])
    events: list[dict] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            findings.append(f"line {line_number}: invalid JSON ({exc})")
            continue
        if not isinstance(event, dict):
            findings.append(f"line {line_number}: event must be an object")
            continue
        events.append(event)
        for field in REQUIRED_FIELDS:
            if field not in event or str(event.get(field, "")).strip() == "":
                findings.append(f"line {line_number}: missing {field}")
        usage_source = str(event.get("usage_source") or "").strip().lower()
        if usage_source not in USAGE_SOURCES:
            findings.append(f"line {line_number}: invalid usage_source '{usage_source}'")
        stage = str(event.get("stage") or "unknown").strip() or "unknown"
        if usage_source == "telemetry_unavailable":
            if not str(event.get("telemetry_note") or "").strip():
                findings.append(f"line {line_number}: telemetry_unavailable requires telemetry_note")
            continue
        for field in TOKEN_FIELDS:
            value = event.get(field)
            if not isinstance(value, int) or value < 0:
                findings.append(f"line {line_number}: {field} must be a non-negative integer for measured usage")
                continue
            totals[field] += value
            by_stage[stage][field] += value
        if not isinstance(event.get("input_hashes", []), (list, dict)):
            findings.append(f"line {line_number}: input_hashes must be a list or object")
        if not isinstance(event.get("output_artifacts", []), list):
            findings.append(f"line {line_number}: output_artifacts must be a list")
    if not events:
        findings.append("usage ledger contains no events")
    unavailable_count = sum(1 for event in events if str(event.get("usage_source") or "").lower() == "telemetry_unavailable")
    status = "UNAVAILABLE" if events and unavailable_count == len(events) and not findings else ("PASS" if not findings else "FAIL")
    return UsageResult(str(path), not findings, status, len(events), unavailable_count, totals, dict(by_stage), findings)


def to_markdown(result: UsageResult) -> str:
    lines = [
        "# Token Budget by Stage",
        "",
        f"- Ledger: `{result.path}`",
        f"- Status: {result.status}",
        f"- Events: {result.event_count}",
        f"- Telemetry unavailable events: {result.unavailable_count}",
        "",
        "## Measured Totals",
        "",
        "| Stage | Input | Cached input | Reasoning | Output |",
        "|---|---:|---:|---:|---:|",
    ]
    for stage, values in sorted(result.by_stage.items()):
        lines.append(
            f"| {stage} | {values['input_tokens']} | {values['cached_input_tokens']} | {values['reasoning_tokens']} | {values['output_tokens']} |"
        )
    if not result.by_stage:
        lines.append("| telemetry_unavailable | - | - | - | - |")
    lines.extend(["", "## Findings", ""])
    lines.extend(f"- {finding}" for finding in result.findings) if result.findings else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    result = validate(output_dir / "usage_ledger.jsonl")
    markdown = to_markdown(result)
    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "token_budget_by_stage.md").write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
