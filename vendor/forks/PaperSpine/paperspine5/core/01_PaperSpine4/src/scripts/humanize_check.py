#!/usr/bin/env python3
"""Legacy PaperSpine humanize compatibility diagnostics.

This module is intentionally non-authoritative. It does not identify AI
authorship, estimate an AI percentage, or fail prose for sentence-length or
connector patterns. New workflows use ``author_voice_check.py`` for provenance,
semantic invariants, independent audit, clean-text no-op, and author approval.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from author_voice_check import (
    scan_diagnostics,
    validate_author_voice,
)
from author_voice_check import (
    to_json_dict as voice_to_json,
)
from author_voice_check import (
    to_markdown as voice_to_markdown,
)

AI_CONNECTORS_ZH = (
    "首先", "其次", "再次", "最后", "综上所述", "总而言之", "此外", "另外",
    "值得注意的是", "需要指出的是", "因此", "与此同时",
)
AI_CONNECTORS_EN = (
    "firstly", "secondly", "thirdly", "finally", "in conclusion", "to sum up",
    "furthermore", "moreover", "additionally", "it is worth noting", "therefore",
)
MIN_PARAGRAPH_CHARS = 50
DIMENSION_NAMES = {
    "D1": "sentence structure",
    "D2": "paragraph similarity",
    "D3": "information density",
    "D4": "connector frequency",
    "D5": "term-context matching",
}


@dataclass
class DimensionResult:
    code: str
    name: str
    status: str = "ADVISORY"
    metrics: dict[str, float | int | str] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    affected_units: list[str] = field(default_factory=list)


@dataclass
class HumanizeCheckResult:
    path: str
    ok: bool
    # ``ok`` is retained for callers that only need to know whether the legacy
    # table is parseable. It is deliberately not a PaperSpine readiness verdict.
    authority: str = "diagnostic_only"
    readiness_authority: bool = False
    humanize_tier: str = "compatibility"
    matrix_rows: int = 0
    manuscript_paragraphs: int = 0
    coverage_ratio: float = 0.0
    sentence_length_stddev: float = 0.0
    connector_density: float = 0.0
    dimension_results: dict[str, DimensionResult] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    required_findings: list[str] = field(default_factory=list)
    advisory_findings: list[str] = field(default_factory=list)
    thresholds: dict[str, float | int] = field(default_factory=dict)
    threshold_warnings: list[str] = field(default_factory=list)


def count_connectors(text: str, lang: str) -> int:
    pool = AI_CONNECTORS_ZH if lang == "zh" else AI_CONNECTORS_EN
    lowered = text.casefold()
    return sum(lowered.count(item.casefold()) for item in pool)


def _table_rows(text: str) -> tuple[list[str], list[list[str]]]:
    rows: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and all(cell and set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        rows.append(cells)
    return (rows[0], rows[1:]) if rows else ([], [])


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n+", text) if len(part.strip()) > MIN_PARAGRAPH_CHARS]


def check_matrix(
    matrix_path: Path,
    manuscript_text: str,
    lang: str,
    humanize_tier: str = "compatibility",
    thresholds: object | None = None,
    threshold_warnings: list[str] | None = None,
) -> HumanizeCheckResult:
    """Read old humanize artifacts without turning style metrics into a gate."""
    del thresholds
    result = HumanizeCheckResult(str(matrix_path), False, humanize_tier=humanize_tier)
    result.threshold_warnings = list(threshold_warnings or [])
    if not matrix_path.is_file():
        result.findings = ["humanize_matrix.md not found; migrate to author_voice_revision.json."]
        result.required_findings = list(result.findings)
        return result
    text = matrix_path.read_text(encoding="utf-8", errors="ignore")
    header, rows = _table_rows(text)
    if not header:
        result.findings = ["humanize_matrix.md has no parseable table."]
        result.required_findings = list(result.findings)
        return result

    result.matrix_rows = len(rows)
    if result.matrix_rows == 0:
        result.findings = [
            "humanize_matrix.md has a header but no data rows; use author_voice_check.py "
            "for the current evidence-bound restoration gate."
        ]
        result.required_findings = list(result.findings)
        return result
    result.manuscript_paragraphs = len(_paragraphs(manuscript_text))
    result.coverage_ratio = round(min(1.0, len(rows) / max(result.manuscript_paragraphs, 1)), 3)
    diagnostics = scan_diagnostics(manuscript_text)
    result.connector_density = round(
        count_connectors(manuscript_text, lang) / max(len(manuscript_text) / 1000, 0.001),
        3,
    )

    advisory = [
        "Legacy D1-D5 rows are diagnostic only; they are not authorship judgments or automatic rewrite commands.",
        "Use author_voice_check.py for the current evidence-bound restoration gate.",
    ]
    if result.manuscript_paragraphs and result.coverage_ratio < 0.5:
        advisory.append(f"Coverage advisory: matrix addresses {result.coverage_ratio:.0%} of long paragraphs.")
    joined = " ".join(" ".join(row).casefold() for row in rows)
    missing = [name for name in DIMENSION_NAMES.values() if name not in joined]
    if missing:
        advisory.append("Legacy diagnostic dimensions not covered: " + ", ".join(missing))
    if diagnostics:
        advisory.append(f"Template-pattern diagnostics found in {len(diagnostics)} group(s); review in section context.")

    result.advisory_findings = advisory
    result.findings = list(advisory)
    result.ok = True
    return result


def to_markdown(result: HumanizeCheckResult) -> str:
    lines = [
        "# Legacy Humanize Compatibility Report",
        "",
        f"- Matrix path: `{result.path}`",
        f"- Status: {'PASS' if result.ok else 'BLOCKED'}",
        "- Readiness gate: `not_authoritative`",
        "- Authority: `diagnostic_only`",
        "- Authorship inference: `not_performed`",
        "- Detector pass / AI percentage: `not_claimed`",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {item}" for item in result.findings) if result.findings else lines.append("- None")
    lines.extend([
        "",
        "Use `author_voice_check.py` and its hash-bound receipt for current workflows.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run legacy humanize diagnostics or delegate to Authorial Voice Restoration."
    )
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    if (output_dir / "author_voice_revision.json").is_file() or (output_dir / "author_voice_profile.json").is_file():
        voice = validate_author_voice(output_dir)
        payload = voice_to_json(voice)
        markdown = voice_to_markdown(voice)
        if args.write:
            (output_dir / "author_voice_receipt.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (output_dir / "author_voice_report.md").write_text(markdown, encoding="utf-8")
            (output_dir / "humanize_report.md").write_text(
                "# Compatibility Redirect\n\nSee `author_voice_report.md`; the legacy report has no independent gate authority.\n",
                encoding="utf-8",
            )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.markdown or not args.json:
            print(markdown)
        return 0 if voice.ok else 1

    config: dict[str, object] = {}
    config_path = output_dir / "paper_spine_config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            config = {}
    language = "zh" if str(config.get("output_language") or "en").lower().startswith("zh") else "en"
    manuscript = ""
    final_paper = output_dir / "final_paper"
    if final_paper.is_dir():
        manuscript = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in sorted(final_paper.glob("*.tex"))
        )
    result = check_matrix(output_dir / "humanize_matrix.md", manuscript, language)
    markdown = to_markdown(result)
    if args.write:
        (output_dir / "humanize_report.md").write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
