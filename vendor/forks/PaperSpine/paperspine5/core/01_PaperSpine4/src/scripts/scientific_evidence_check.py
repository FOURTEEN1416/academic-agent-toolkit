#!/usr/bin/env python3
"""Validate PaperSpine's source/claim/numeric/method/outcome/result ledger."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

GROUP_PREFIXES = {
    "sources": "S",
    "claims": "C",
    "numeric_facts": "N",
    "methods": "M",
    "outcomes": "O",
    "results": "R",
}
FINAL_STATES = {"verified", "user_authoritative", "not_applicable"}
PLANNING_STATES = FINAL_STATES | {"planned", "unverified"}
ID_PATTERN = re.compile(r"^[SCNMOR]\d{3,}$")


@dataclass
class EvidenceResult:
    path: str
    phase: str
    ok: bool
    counts: dict[str, int]
    linked_records: int
    verified_records: int
    findings: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate scientific_evidence_ledger.json.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--phase", choices=("planning", "final"), default="planning")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def _records(data: dict, group: str) -> list[dict]:
    records = data.get("records", {})
    value = records.get(group, []) if isinstance(records, dict) else []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _text(value: object) -> str:
    return str(value or "").strip()


def _refs(record: dict, key: str) -> list[str]:
    value = record.get(key, [])
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    return []


def validate(path: Path, phase: str) -> EvidenceResult:
    findings: list[str] = []
    counts = {group: 0 for group in GROUP_PREFIXES}
    if not path.is_file():
        return EvidenceResult(str(path), phase, False, counts, 0, 0, ["scientific_evidence_ledger.json does not exist"])
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return EvidenceResult(str(path), phase, False, counts, 0, 0, [f"invalid JSON: {exc}"])
    if not isinstance(data, dict):
        return EvidenceResult(str(path), phase, False, counts, 0, 0, ["ledger root must be a JSON object"])

    grouped = {group: _records(data, group) for group in GROUP_PREFIXES}
    counts = {group: len(records) for group, records in grouped.items()}
    for required in ("sources", "claims", "methods", "outcomes", "results"):
        if not grouped[required]:
            findings.append(f"records.{required} must contain at least one record")

    all_ids: dict[str, str] = {}
    for group, records in grouped.items():
        prefix = GROUP_PREFIXES[group]
        for index, record in enumerate(records, 1):
            record_id = _text(record.get("id"))
            if not ID_PATTERN.fullmatch(record_id) or not record_id.startswith(prefix):
                findings.append(f"records.{group}[{index}] has invalid id '{record_id}'; expected {prefix}###")
                continue
            if record_id in all_ids:
                findings.append(f"duplicate record id: {record_id}")
            all_ids[record_id] = group

    linked_records = 0
    verified_records = 0
    allowed_states = PLANNING_STATES if phase == "planning" else FINAL_STATES
    for group, records in grouped.items():
        for record in records:
            record_id = _text(record.get("id")) or f"{group} record"
            state = _text(record.get("verification_state")).lower()
            if state:
                if state not in allowed_states:
                    findings.append(f"{record_id} verification_state '{state}' is not allowed in {phase} phase")
                if state in FINAL_STATES:
                    verified_records += 1
                if state == "verified" and not _text(record.get("verified_by")):
                    findings.append(f"{record_id} is verified but verified_by is empty")
                if state == "user_authoritative" and not _text(record.get("evidence_locator")):
                    findings.append(f"{record_id} is user_authoritative but evidence_locator is empty")
            elif group in {"sources", "numeric_facts", "methods", "results"}:
                findings.append(f"{record_id} must declare verification_state")

            for key, expected_prefix in (
                ("source_ids", "S"),
                ("claim_ids", "C"),
                ("numeric_fact_ids", "N"),
                ("method_ids", "M"),
                ("outcome_ids", "O"),
                ("result_ids", "R"),
            ):
                for ref in _refs(record, key):
                    if ref not in all_ids:
                        findings.append(f"{record_id}.{key} references missing id {ref}")
                    elif not ref.startswith(expected_prefix):
                        findings.append(f"{record_id}.{key} references {ref}, expected {expected_prefix}###")
                    else:
                        linked_records += 1

    for claim in grouped["claims"]:
        record_id = _text(claim.get("id"))
        if not _text(claim.get("text")):
            findings.append(f"{record_id} claim text is empty")
        if not _text(claim.get("boundary")):
            findings.append(f"{record_id} claim boundary is empty")
        if not _refs(claim, "source_ids") and not _refs(claim, "result_ids"):
            findings.append(f"{record_id} must link to source_ids or result_ids")

    for result in grouped["results"]:
        record_id = _text(result.get("id"))
        if not _refs(result, "claim_ids"):
            findings.append(f"{record_id} must link to at least one claim_id")
        if not _refs(result, "method_ids") or not _refs(result, "outcome_ids"):
            findings.append(f"{record_id} must link method_ids and outcome_ids")
        if not _text(result.get("conditions")):
            findings.append(f"{record_id} conditions are empty")
        if "uncertainty" not in result or not _text(result.get("uncertainty")):
            findings.append(f"{record_id} uncertainty/statistical-boundary note is empty")

    if phase == "final":
        for claim in grouped["claims"]:
            if claim.get("used_in_final") is True:
                linked_results = _refs(claim, "result_ids")
                if not linked_results:
                    findings.append(f"{_text(claim.get('id'))} is used_in_final but has no result_ids")
        if _text(data.get("status")).lower() != "manuscript_ready":
            findings.append("ledger status must be 'manuscript_ready' for final audit")

    return EvidenceResult(str(path), phase, not findings, counts, linked_records, verified_records, findings)


def to_markdown(result: EvidenceResult) -> str:
    lines = [
        "# Scientific Evidence Check",
        "",
        f"- Path: `{result.path}`",
        f"- Phase: `{result.phase}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Verified/final-state records: {result.verified_records}",
        f"- Valid links inspected: {result.linked_records}",
        "",
        "## Record Counts",
        "",
    ]
    lines.extend(f"- {group}: {count}" for group, count in result.counts.items())
    lines.extend(["", "## Findings", ""])
    lines.extend(f"- {finding}" for finding in result.findings) if result.findings else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    result = validate(output_dir / "scientific_evidence_ledger.json", args.phase)
    markdown = to_markdown(result)
    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scientific_evidence_check.md").write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
