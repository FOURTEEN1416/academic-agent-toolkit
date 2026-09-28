"""Artifact diff viewer: show what changed between versions."""

from __future__ import annotations

import difflib
from pathlib import Path


def unified_diff(original: str, modified: str, filename: str = "file") -> str:
    """Generate a unified diff between two versions of text.

    Args:
        original: Original text content.
        modified: Modified text content.
        filename: Name for the diff header.

    Returns:
        Unified diff string, or "No changes" if identical.
    """
    if original == modified:
        return "No changes"

    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
    )
    return "".join(diff) or "No changes"


def side_by_side_diff(
    original: str, modified: str, width: int = 80
) -> str:
    """Generate a side-by-side diff for terminal display.

    Args:
        original: Original text.
        modified: Modified text.
        width: Total terminal width.

    Returns:
        Formatted side-by-side diff string.
    """
    if original == modified:
        return "No changes"

    half = (width - 3) // 2  # 3 for " | " separator
    orig_lines = original.splitlines()
    mod_lines = modified.splitlines()

    lines: list[str] = []
    lines.append(f"{'Original':<{half}} | {'Modified':<{half}}")
    lines.append("─" * half + "─┼─" + "─" * half)

    sm = difflib.SequenceMatcher(None, orig_lines, mod_lines)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                left = orig_lines[i1 + k][:half]
                right = mod_lines[j1 + k][:half]
                lines.append(f"{left:<{half}} │ {right:<{half}}")
        elif tag == "replace":
            max_len = max(i2 - i1, j2 - j1)
            for k in range(max_len):
                left = orig_lines[i1 + k][:half] if i1 + k < i2 else ""
                right = mod_lines[j1 + k][:half] if j1 + k < j2 else ""
                marker = "◄" if left != right else " "
                lines.append(f"{left:<{half}} {marker} {right:<{half}}")
        elif tag == "delete":
            for k in range(i2 - i1):
                left = orig_lines[i1 + k][:half]
                lines.append(f"{left:<{half}} - {'':>{half}}")
        elif tag == "insert":
            for k in range(j2 - j1):
                right = mod_lines[j1 + k][:half]
                lines.append(f"{'':>{half}} + {right:<{half}}")

    return "\n".join(lines)


def diff_summary(original: str, modified: str) -> dict[str, int]:
    """Compute diff statistics.

    Returns:
        Dict with keys: added, deleted, changed, unchanged.
    """
    orig_lines = original.splitlines()
    mod_lines = modified.splitlines()

    sm = difflib.SequenceMatcher(None, orig_lines, mod_lines)
    stats = {"added": 0, "deleted": 0, "changed": 0, "unchanged": 0}

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            stats["unchanged"] += i2 - i1
        elif tag == "replace":
            stats["changed"] += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            stats["deleted"] += i2 - i1
        elif tag == "insert":
            stats["added"] += j2 - j1

    return stats


def format_diff_stats(stats: dict[str, int]) -> str:
    """Format diff stats as a human-readable string."""
    parts = []
    if stats["added"]:
        parts.append(f"+{stats['added']} added")
    if stats["deleted"]:
        parts.append(f"-{stats['deleted']} deleted")
    if stats["changed"]:
        parts.append(f"~{stats['changed']} changed")
    parts.append(f"{stats['unchanged']} unchanged")
    return ", ".join(parts)


def diff_from_snapshot(
    run_dir: Path, stage_num: int, filename: str
) -> str | None:
    """Generate a diff between a snapshot and current version.

    Args:
        run_dir: Pipeline run directory.
        stage_num: Stage number.
        filename: File to diff.

    Returns:
        Unified diff string, or None if no snapshot exists.
    """
    snapshot = (
        run_dir / "hitl" / "snapshots"
        / f"stage_{stage_num:02d}_{filename}.orig"
    )
    current = run_dir / f"stage-{stage_num:02d}" / filename

    if not snapshot.exists() or not current.exists():
        return None

    try:
        orig = snapshot.read_text(encoding="utf-8")
        curr = current.read_text(encoding="utf-8")
        return unified_diff(orig, curr, filename)
    except (OSError, UnicodeDecodeError):
        return None
