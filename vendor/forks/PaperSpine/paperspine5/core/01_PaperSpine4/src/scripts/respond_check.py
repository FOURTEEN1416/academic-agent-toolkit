#!/usr/bin/env python3
"""Validate a PaperSpine review_response/ package.

Self-contained — standard library only.  Checks that every reviewer comment
has a response, the matrix has required columns, and no unresolved placeholders
are left behind.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paper_spine_utils import table_rows

# ---------------------------------------------------------------------------
# comment ID extraction
# ---------------------------------------------------------------------------

_COMMENT_ID_RE = re.compile(
    r"\b(R\d+\.C\d+|C\d+|Comment\s*\d+|Reviewer\s*\d+\s*[-:]\s*Comment\s*\d+)",
    re.IGNORECASE,
)


def _extract_comment_ids(text: str) -> list[str]:
    """Extract comment IDs from text using conservative patterns."""
    seen: set[str] = set()
    ids: list[str] = []
    for match in _COMMENT_ID_RE.finditer(text):
        cid = match.group(1).strip()
        # Normalise: "Comment 1" → "C1", "Reviewer 1 - Comment 2" → "R1.C2"
        cid = re.sub(r"\s+", "", cid)
        cid = re.sub(r"Reviewer(\d+)[-:]Comment(\d+)", r"R\1.C\2", cid, flags=re.IGNORECASE)
        cid = re.sub(r"^Comment(\d+)$", r"C\1", cid, flags=re.IGNORECASE)
        if cid not in seen:
            seen.add(cid)
            ids.append(cid)
    return ids


def _id_present(cid: str, text: str) -> bool:
    """Word-boundary match so C1 does not match inside C10/C11."""
    return re.search(r"\b" + re.escape(cid) + r"\b", text, re.IGNORECASE) is not None


# ---------------------------------------------------------------------------
# forbidden markers
# ---------------------------------------------------------------------------

_FORBIDDEN = [
    "TODO",
    "TBD",
    "[[",
    "]]",
]

_PLACEHOLDER_RE = re.compile(
    r"\[NEEDS USER DATA:.*?\]|\[AUTHOR CONFIRMATION REQUIRED:.*?\]",
    re.IGNORECASE,
)


def _check_forbidden(text: str) -> list[str]:
    """Return list of forbidden markers found in text."""
    hits = []
    for marker in _FORBIDDEN:
        if marker in text:
            hits.append(marker)
    return hits


def _check_placeholders(text: str) -> list[str]:
    """Return list of placeholder instances found."""
    return _PLACEHOLDER_RE.findall(text)


# ---------------------------------------------------------------------------
# result types
# ---------------------------------------------------------------------------

@dataclass
class RespondCheckResult:
    path: str
    ok: bool
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_comments: list[str] = field(default_factory=list)
    placeholders: list[str] = field(default_factory=list)
    comment_count: int = 0


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate PaperSpine review_response/ package."
    )
    parser.add_argument(
        "output_dir", nargs="?",
        default="paper_rewriting_output/review_response",
    )
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true",
                        help="Write respond_check.md")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# core logic
# ---------------------------------------------------------------------------

REQUIRED_FILES = [
    "reviewer_comments_extracted.md",
    "response_matrix.md",
    "response_letter.md",
    "revision_change_log.md",
]

MATRIX_REQUIRED_COLS = [
    "comment id",
    "reviewer",
    "original comment",
    "issue type",
    "required action",
    "manuscript change",
    "evidence",
    "response draft",
    "status",
]

# Allowed Status values per respond.md spec.
ALLOWED_STATUS = {"draft", "final", "needs-author"}


def check_respond(out_dir: Path) -> RespondCheckResult:
    result = RespondCheckResult(str(out_dir), ok=True)

    # --- required files ---
    for fname in REQUIRED_FILES:
        if not (out_dir / fname).exists():
            result.ok = False
            result.findings.append(f"Missing required file: {fname}")

    # If critical files are missing, stop early
    extracted_path = out_dir / "reviewer_comments_extracted.md"
    matrix_path = out_dir / "response_matrix.md"
    letter_path = out_dir / "response_letter.md"

    # --- extract comment IDs ---
    extracted_ids: list[str] = []
    if extracted_path.exists():
        text = extracted_path.read_text(encoding="utf-8", errors="ignore")
        extracted_ids = _extract_comment_ids(text)
        result.comment_count = len(extracted_ids)
        if not extracted_ids:
            result.findings.append(
                "No comment IDs found in reviewer_comments_extracted.md. "
                "Expected format: R1.C1, C1, Comment 1, etc."
            )
    else:
        result.findings.append(
            "reviewer_comments_extracted.md missing — cannot verify comment coverage."
        )
        return result

    # --- response_matrix.md ---
    if matrix_path.exists():
        matrix_text = matrix_path.read_text(encoding="utf-8", errors="ignore")
        header, rows = table_rows(matrix_text)

        if not header:
            result.ok = False
            result.findings.append("response_matrix.md has no parseable table.")
        else:
            # Check required columns
            header_lower = [c.lower() for c in header]
            header_text = " ".join(header_lower)
            for col in MATRIX_REQUIRED_COLS:
                if col not in header_text:
                    result.ok = False
                    result.findings.append(
                        f"response_matrix.md missing required column: {col}"
                    )

            def _find_col(*names: str) -> int | None:
                for name in names:
                    for idx, h in enumerate(header_lower):
                        if name in h:
                            return idx
                return None

            status_idx = _find_col("status")
            response_idx = _find_col("response draft", "response")

            # Check comment coverage in matrix (word-boundary, not substring)
            if rows:
                matrix_text_full = " ".join(" ".join(r) for r in rows)
                matrix_ids = {
                    cid for cid in extracted_ids
                    if _id_present(cid, matrix_text_full)
                }
                missing_matrix = [c for c in extracted_ids if c not in matrix_ids]
                if missing_matrix:
                    result.ok = False
                    result.missing_comments.extend(missing_matrix)
                    result.findings.append(
                        f"Comments missing from response_matrix.md: "
                        f"{missing_matrix[:10]}"
                    )

            # Validate per-row Response Draft + Status cells
            for row_num, row in enumerate(rows, start=1):
                if response_idx is not None:
                    cell = row[response_idx] if response_idx < len(row) else ""
                    if not re.search(r"[A-Za-z0-9一-鿿]", cell):
                        result.ok = False
                        result.findings.append(
                            f"response_matrix.md row {row_num}: empty Response Draft cell."
                        )
                if status_idx is not None:
                    cell = row[status_idx] if status_idx < len(row) else ""
                    norm = re.sub(r"[^a-z-]", "", cell.lower())
                    if not norm:
                        result.ok = False
                        result.findings.append(
                            f"response_matrix.md row {row_num}: empty Status cell."
                        )
                    elif norm not in ALLOWED_STATUS:
                        result.ok = False
                        result.findings.append(
                            f"response_matrix.md row {row_num}: invalid Status "
                            f"'{cell}' (allowed: {sorted(ALLOWED_STATUS)})."
                        )

            # Check forbidden markers in matrix
            forbidden = _check_forbidden(matrix_text)
            if forbidden:
                result.ok = False
                result.findings.append(
                    f"response_matrix.md contains forbidden markers: {forbidden}"
                )

            # Check placeholders
            ph = _check_placeholders(matrix_text)
            if ph:
                result.placeholders.extend(ph)
                result.warnings.append(
                    f"response_matrix.md has {len(ph)} placeholder(s) needing user data."
                )
    else:
        result.findings.append(
            "response_matrix.md missing — cannot verify comment coverage."
        )

    # --- response_letter.md ---
    if letter_path.exists():
        letter_text = letter_path.read_text(encoding="utf-8", errors="ignore")

        # Length check
        letter_words = len(re.findall(r"[A-Za-z]+", letter_text))
        letter_chars = len(re.findall(r"[一-鿿]", letter_text))
        if letter_words < 150 and letter_chars < 300:
            result.ok = False
            result.findings.append(
                f"response_letter.md is too short: {letter_words} words, "
                f"{letter_chars} Chinese chars. Minimum 150 words or 300 Chinese chars."
            )

        # Comment coverage in letter (word-boundary, not substring)
        missing_letter = [
            c for c in extracted_ids if not _id_present(c, letter_text)
        ]
        if missing_letter:
            result.ok = False
            # Merge with existing missing_comments
            for c in missing_letter:
                if c not in result.missing_comments:
                    result.missing_comments.append(c)
            result.findings.append(
                f"Comments missing from response_letter.md: {missing_letter[:10]}"
            )

        # Forbidden markers
        forbidden = _check_forbidden(letter_text)
        if forbidden:
            result.ok = False
            result.findings.append(
                f"response_letter.md contains forbidden markers: {forbidden}"
            )

        # Placeholders
        ph = _check_placeholders(letter_text)
        if ph:
            for p in ph:
                if p not in result.placeholders:
                    result.placeholders.append(p)
            result.warnings.append(
                f"response_letter.md has {len(ph)} placeholder(s) needing user data."
            )

    # --- revision_change_log.md ---
    change_log = out_dir / "revision_change_log.md"
    if change_log.exists():
        ct = change_log.read_text(encoding="utf-8", errors="ignore")
        forbidden = _check_forbidden(ct)
        if forbidden:
            result.ok = False
            result.findings.append(
                f"revision_change_log.md contains forbidden markers: {forbidden}"
            )

    # --- revised manuscript (spec output #5) ---
    revised_path = out_dir / "revised_manuscript.md"
    has_revised = (
        revised_path.exists()
        and revised_path.read_text(encoding="utf-8", errors="ignore").strip()
    )
    if not has_revised:
        # Accept a note that changes were applied to final_paper/main.tex.
        note_sources = []
        for fname in (
            "revision_change_log.md",
            "response_letter.md",
            "response_matrix.md",
        ):
            fp = out_dir / fname
            if fp.exists():
                note_sources.append(
                    fp.read_text(encoding="utf-8", errors="ignore")
                )
        combined = "\n".join(note_sources).lower()
        if "main.tex" not in combined:
            result.ok = False
            result.findings.append(
                "Revised manuscript missing (spec output #5): provide "
                "revised_manuscript.md or a note that changes were applied "
                "to final_paper/main.tex."
            )

    return result


# ---------------------------------------------------------------------------
# output formatting
# ---------------------------------------------------------------------------

def to_markdown(result: RespondCheckResult) -> str:
    lines = [
        "# Respond Check Report",
        "",
        f"- Path: `{result.path}`",
        f"- Comment count: {result.comment_count}",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {f}" for f in result.findings) if result.findings else lines.append("- None")
    lines.append("")

    lines.extend([
        "## Warnings",
        "",
    ])
    lines.extend(f"- {w}" for w in result.warnings) if result.warnings else lines.append("- None")
    lines.append("")

    lines.extend([
        "## Missing Comments",
        "",
    ])
    lines.extend(f"- {c}" for c in result.missing_comments) if result.missing_comments else lines.append("- None")
    lines.append("")

    lines.extend([
        "## Placeholders (Needs User Data)",
        "",
    ])
    lines.extend(f"- {p}" for p in result.placeholders) if result.placeholders else lines.append("- None")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    result = check_respond(out_dir)

    if args.json:
        print(json.dumps({
            "ok": result.ok,
            "comment_count": result.comment_count,
            "findings": result.findings,
            "warnings": result.warnings,
            "missing_comments": result.missing_comments,
            "placeholders": result.placeholders,
        }, ensure_ascii=False, indent=2))
    elif args.markdown or not args.json:
        print(to_markdown(result))

    if args.write:
        report_path = out_dir / "respond_check.md"
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(to_markdown(result), encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
