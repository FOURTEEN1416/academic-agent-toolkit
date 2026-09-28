#!/usr/bin/env python3
"""Validate layout-density and mainline-balance records in S2/S5 prompt packages.

This guard is intentionally paper-neutral. It checks whether each active row in a
prompt-index points to a prompt package that carries the mandatory layout-density
contracts introduced for compact manuscript framework diagrams.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REQUIRED_MARKER_GROUPS: dict[str, tuple[str, ...]] = {
    "layout_information_density_plan": (
        "layout_information_density_plan",
        "Layout information density plan",
        "layout information density",
    ),
    "canvas_area_budget": (
        "canvas_area_budget",
        "Canvas area budget",
        "canvas area budget",
        "active_payload_ratio_target",
        "primary_method_content_pct",
    ),
    "context_inset_budget": (
        "context_inset_budget",
        "Context inset budget",
        "context inset budget",
        "background/context",
    ),
    "mainline_center_of_gravity_gate": (
        "mainline_center_of_gravity_gate",
        "mainline center-of-gravity",
        "center of gravity",
        "visual focus",
    ),
    "layout_density_audit": (
        "layout_density_audit",
        "layout density audit",
        "excessive_whitespace",
        "fragmented_microblock_scatter",
        "top-heavy context",
    ),
}

PROMPT_HARD_PHRASES: tuple[str, ...] = (
    "compact-balanced",
    "compact manuscript",
    "primary method",
    "usable canvas",
    "empty quadrants",
    "oversized margins",
    "scattered micro-block",
    "top-heavy context",
    "background context",
    "physical-layout exception",
)

@dataclass
class Finding:
    level: str
    candidate_id: str
    path: str
    message: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def active_rows(index: dict[str, Any]) -> list[dict[str, Any]]:
    rows = index.get("candidates")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict) and r.get("selected", True) and not r.get("skip", False)]
    cmap = index.get("candidate_map")
    if isinstance(cmap, dict):
        out: list[dict[str, Any]] = []
        for cid, row in cmap.items():
            if isinstance(row, dict) and row.get("selected", True) and not row.get("skip", False):
                row = {**row, "candidate_id": row.get("candidate_id", cid)}
                out.append(row)
        return out
    return []


def resolve_prompt_path(root: Path, row: dict[str, Any]) -> Path | None:
    prompt_path = row.get("prompt_path") or row.get("clean_framework_prompt_path")
    if not isinstance(prompt_path, str) or not prompt_path.strip():
        return None
    path = Path(prompt_path)
    if path.is_absolute():
        return path
    return root / path


def check_prompt(candidate_id: str, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not path.exists():
        return [Finding("ERROR", candidate_id, path.as_posix(), "prompt_path does not exist")]
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lower = text.lower()
    for group, markers in REQUIRED_MARKER_GROUPS.items():
        if not any(marker.lower() in lower for marker in markers):
            findings.append(Finding("ERROR", candidate_id, path.as_posix(), f"missing layout-density marker group: {group}"))
    if not any(phrase.lower() in lower for phrase in PROMPT_HARD_PHRASES):
        findings.append(Finding("ERROR", candidate_id, path.as_posix(), "image prompt lacks compact layout-density hard wording"))
    if "large top" in lower and "block" not in lower and "forbid" not in lower and "avoid" not in lower:
        findings.append(Finding("WARN", candidate_id, path.as_posix(), "prompt mentions a large top area without an explicit avoid/block framing"))
    if "lots of whitespace" in lower or "large whitespace" in lower or "spacious layout" in lower:
        if "avoid" not in lower and "do not" not in lower and "forbid" not in lower:
            findings.append(Finding("WARN", candidate_id, path.as_posix(), "prompt may encourage excessive whitespace"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-index", required=True, help="Path to S2/S5 prompt-index.json")
    parser.add_argument("--root", default=".", help="Project/run root used to resolve relative prompt_path values")
    parser.add_argument("--json-output")
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root)
    prompt_index = Path(args.prompt_index)
    index = load_json(prompt_index)
    findings: list[Finding] = []
    rows = active_rows(index)
    if not rows:
        findings.append(Finding("ERROR", "<index>", prompt_index.as_posix(), "no active candidates found in prompt-index"))
    for row in rows:
        cid = str(row.get("candidate_id") or "<missing-candidate-id>")
        path = resolve_prompt_path(root, row)
        if path is None:
            findings.append(Finding("ERROR", cid, "<none>", "row missing prompt_path"))
            continue
        findings.extend(check_prompt(cid, path))

    error_count = sum(1 for f in findings if f.level == "ERROR")
    warn_count = sum(1 for f in findings if f.level == "WARN")
    payload = {
        "prompt_index": prompt_index.as_posix(),
        "active_candidate_count": len(rows),
        "status": "PASS" if error_count == 0 else "FAIL",
        "error_count": error_count,
        "warn_count": warn_count,
        "findings": [asdict(f) for f in findings],
    }
    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if args.fail_on_error and error_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
