#!/usr/bin/env python3
"""Reject workflow scaffolding that leaks into the publication surface."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

PATTERNS = (
    ("inline audit tag", re.compile(r"\[(?:claim|evidence|source|numeric|method|outcome|result)\s*:\s*[SCNMOR]\d+[^\]]*\]", re.I)),
    ("workflow artifact name", re.compile(r"\b(?:writing_rationale_matrix|scientific_evidence_ledger|results_validation|reviewer_audit|claim_register)\.(?:md|json)\b", re.I)),
    ("audit identifier prose", re.compile(r"\b(?:claim|evidence|numeric|method|outcome|result)\s+ID\s*[:=]\s*[SCNMOR]\d+", re.I)),
    ("internal gate narration", re.compile(r"\b(?:artifact_check|progress_check|citation_bank_check|publication_surface_check)\.py\b", re.I)),
)


@dataclass
class SurfaceResult:
    files: list[str]
    ok: bool
    findings: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check final manuscript files for internal audit scaffolding.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def validate(output_dir: Path) -> SurfaceResult:
    final_dir = output_dir / "final_paper"
    candidates = [final_dir / "main.tex", final_dir / "paper.md", output_dir / "final_paper.md"]
    files = [path for path in candidates if path.is_file()]
    findings: list[str] = []
    if not files:
        findings.append("no final manuscript source was found")
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in PATTERNS:
            matches = list(pattern.finditer(text))
            if matches:
                sample = matches[0].group(0).replace("\n", " ")[:100]
                findings.append(f"{path.name}: {label} leaked into publication text ({sample})")
    return SurfaceResult([str(path) for path in files], not findings, findings)


def to_markdown(result: SurfaceResult) -> str:
    lines = [
        "# Publication Surface Check",
        "",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Manuscript sources inspected: {len(result.files)}",
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
    result = validate(output_dir)
    markdown = to_markdown(result)
    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "publication_surface_check.md").write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
