#!/usr/bin/env python3
"""Validate paper_rewriting_output/confirmed_contribution.md (Contribution-First gate).

The Contribution-First hard rule: no confirmed_contribution.md, no substantive
writing. This check enforces that the artifact exists and that its four required
sections are actually filled in — not left as empty cells, TODOs, or template
placeholders. A vague or missing contribution is the single most common reason a
generated paper reads fluently while committing to nothing a reviewer can accept.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paper_spine_utils import read_text, table_rows

ARTIFACT_NAME = "confirmed_contribution.md"

# Cell content that means "the decision was never made". Treated as a failure
# because an unfilled cell cannot govern the downstream manuscript.
PLACEHOLDER_PATTERNS = (
    r"^\s*$",
    r"^\s*todo\b",
    r"^\s*tbd\b",
    r"^\s*fixme\b",
    r"^\s*xxx\b",
    r"^\s*n/?a\b",
    r"^\s*-+\s*$",
    r"^\s*\.\.\.+\s*$",
    r"^\s*<[^>]*>\s*$",      # <fill this in>
    r"^\s*\[[^\]]*\]\s*$",   # [placeholder]
    r"^\s*（?待填）?\s*$",
    r"^\s*待定\s*$",
    r"^\s*无\s*$",
)

# Minimum real characters for a content cell to count as "filled".
MIN_CELL_CHARS = 12
# Some fields are legitimately short category labels (e.g. "new theory"); for
# these only emptiness/placeholder text fails, not the prose-length floor.
SHORT_OK_MIN_CHARS = 4
SHORT_OK_FIELDS = frozenset({"contribution type"})

# The four required sections. Each is matched by keyword against ## headings, and
# carries the field rows that must be present AND non-placeholder. The field key
# tuples are the accepted aliases for that row's label (first table column).
REQUIRED_SECTIONS: tuple[dict, ...] = (
    {
        "key": "Core Contribution",
        "heading_terms": ("core contribution",),
        "fields": {
            "main statement": ("main contribution statement", "main statement", "main contribution", "contribution statement"),
            "contribution type": ("contribution type", "type of contribution"),
            "reviewer payoff": ("reviewer payoff", "one-sentence reviewer payoff", "payoff"),
        },
    },
    {
        "key": "Why This Contribution Is Needed",
        "heading_terms": ("why this contribution is needed", "why this contribution", "why needed", "why this is needed"),
        "fields": {
            "field problem": ("field problem",),
            "specific gap": ("specific gap", "gap"),
            "concrete challenge": ("concrete challenge", "challenge"),
            "why prior work leaves it unresolved": ("prior work", "unresolved", "why prior"),
        },
    },
    {
        "key": "How This Paper Responds",
        "heading_terms": ("how this paper responds", "how the paper responds", "how this responds", "paper responds"),
        "fields": {
            "design response": ("design response", "response", "core idea"),
            "evidence required": ("evidence required",),
            "evidence available": ("evidence available",),
            "evidence missing": ("evidence missing", "missing evidence"),
        },
    },
    {
        "key": "Claim Boundary",
        "heading_terms": ("claim boundary", "claim boundaries", "boundary"),
        "fields": {
            "strong claims allowed": ("strong claims allowed", "strong claims", "claims allowed"),
            "claims to soften or avoid": ("soften", "avoid", "claims to soften"),
            "novelty risk": ("novelty risk", "novelty"),
            "significance risk": ("significance risk", "significance"),
        },
    },
)


@dataclass
class ContributionResult:
    path: str
    ok: bool
    exists: bool
    sections_found: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check confirmed_contribution.md (Contribution-First gate)."
    )
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write contribution_check.md into the output directory.",
    )
    return parser.parse_args()


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def is_placeholder(cell: str, min_chars: int = MIN_CELL_CHARS) -> bool:
    value = cell.strip()
    for pattern in PLACEHOLDER_PATTERNS:
        if re.match(pattern, value, flags=re.IGNORECASE):
            return True
    # Strip Markdown emphasis/backticks before measuring real content length.
    stripped = re.sub(r"[`*_~]", "", value).strip()
    return len(stripped) < min_chars


def split_sections(text: str) -> dict[str, str]:
    """Split a Markdown doc into {normalized-heading: body-text} by ## headings."""
    sections: dict[str, str] = {}
    current_heading: str | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*##\s+(.*\S)\s*$", line)
        if match and not line.strip().startswith("###"):
            if current_heading is not None:
                sections[current_heading] = "\n".join(buffer)
            current_heading = _normalize(match.group(1))
            buffer = []
        else:
            if current_heading is not None:
                buffer.append(line)
    if current_heading is not None:
        sections[current_heading] = "\n".join(buffer)
    return sections


def find_section_body(sections: dict[str, str], heading_terms: tuple[str, ...]) -> str | None:
    for heading, body in sections.items():
        if any(term in heading for term in heading_terms):
            return body
    return None


def field_content_map(body: str) -> dict[str, str]:
    """Map each table row's first cell (normalized) to its content cell(s)."""
    header, rows = table_rows(body)
    mapping: dict[str, str] = {}
    all_rows = ([header] if header else []) + rows
    for row in all_rows:
        if len(row) < 2:
            continue
        label = _normalize(row[0])
        if label in {"field", "字段", ""}:
            continue
        content = " ".join(cell for cell in row[1:]).strip()
        mapping[label] = content
    return mapping


def check_section(spec: dict, body: str) -> list[str]:
    findings: list[str] = []
    section_name = spec["key"]
    content_map = field_content_map(body)

    if not content_map:
        findings.append(
            f"Section '{section_name}' has no filled field table; add a `| Field | Content |` "
            "table and complete every row."
        )
        return findings

    for field_label, aliases in spec["fields"].items():
        matched_content: str | None = None
        for row_label, content in content_map.items():
            if any(alias in row_label for alias in aliases):
                matched_content = content
                break
        min_chars = SHORT_OK_MIN_CHARS if field_label in SHORT_OK_FIELDS else MIN_CELL_CHARS
        if matched_content is None:
            findings.append(
                f"Section '{section_name}' is missing the required `{field_label}` row."
            )
        elif is_placeholder(matched_content, min_chars):
            findings.append(
                f"Section '{section_name}' field `{field_label}` is empty or a placeholder; "
                "fill it with a concrete, non-TODO entry."
            )
    return findings


def check_contribution(output_dir: Path) -> ContributionResult:
    path = output_dir / ARTIFACT_NAME
    if not path.exists():
        return ContributionResult(
            path=str(path),
            ok=False,
            exists=False,
            missing_sections=[spec["key"] for spec in REQUIRED_SECTIONS],
            findings=[
                f"{ARTIFACT_NAME} does not exist. Contribution-First hard rule: no "
                "confirmed_contribution.md, no substantive writing. Create it before drafting."
            ],
        )

    text = read_text(path)
    sections = split_sections(text)

    findings: list[str] = []
    found: list[str] = []
    missing: list[str] = []
    for spec in REQUIRED_SECTIONS:
        body = find_section_body(sections, spec["heading_terms"])
        if body is None:
            missing.append(spec["key"])
            findings.append(
                f"Required section '{spec['key']}' (## heading) is missing from {ARTIFACT_NAME}."
            )
            continue
        found.append(spec["key"])
        findings.extend(check_section(spec, body))

    return ContributionResult(
        path=str(path),
        ok=not findings,
        exists=True,
        sections_found=found,
        missing_sections=missing,
        findings=findings,
    )


def to_markdown(result: ContributionResult) -> str:
    lines = [
        "# Contribution Check",
        "",
        f"- Path: `{result.path}`",
        f"- Artifact exists: {'yes' if result.exists else 'no'}",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Required sections found: {', '.join(result.sections_found) or '(none)'}",
        f"- Required sections missing: {', '.join(result.missing_sections) or '(none)'}",
        "",
        "## Findings",
        "",
    ]
    if result.findings:
        lines.extend(f"- {finding}" for finding in result.findings)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    result = check_contribution(output_dir)
    markdown = to_markdown(result)

    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "contribution_check.md").write_text(markdown, encoding="utf-8")

    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
