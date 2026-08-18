"""Build and validate a conservative file-level asset ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SENSITIVE_PARTS = {
    ".engine",
    ".playwright-mcp",
    ".pytest_cache",
    "__pycache__",
    "logs",
    "node_modules",
}
HISTORICAL_ROOT_NAMES = {
    "PLAN.md",
    "DESIGN.md",
    "SYSTEM_AUDIT_COVERAGE.md",
    "SYSTEM_DEEP_AUDIT.md",
    "快速开始.md",
    "start.ps1",
    "preflight_v2.ps1",
}
GOVERNANCE_OUTPUTS = {
    "asset-ledger.jsonl",
    "asset-ledger-summary.json",
    "ASSET_LEDGER.md",
}


def classify_path(relative_path: Path) -> tuple[str, str, str, str]:
    """Return classification, asset group, source status, and release status."""
    parts = relative_path.parts
    name = relative_path.name
    normalized = relative_path.as_posix()

    if name == ".env" or any(part in SENSITIVE_PARTS for part in parts):
        return (
            "excluded_sensitive",
            "sensitive_local_state",
            "not_inspected_sensitive",
            "excluded",
        )
    if parts and parts[0] == "数学建模大赛工具集":
        return (
            "historical_reference",
            "legacy_toolkit",
            "unverified",
            "excluded",
        )
    if parts and parts[0] in {"参考论文", "解析", "赛前试炼任务", "extracted_images"}:
        classification = "historical_reference" if parts[0] == "赛前试炼任务" else "private_extension"
        group = "historical_exercises" if parts[0] == "赛前试炼任务" else "private_research_material"
        return classification, group, "unverified", "excluded"
    if name in HISTORICAL_ROOT_NAMES or name.startswith(("analyze_", "check_", "ref_")):
        return "historical_reference", "root_historical_analysis", "unverified", "excluded"
    if name in {"opencode.json", "README.md", "CURRENT_STATE.md", ".gitignore"} or normalized.startswith("docs/"):
        return "candidate_public_core", "publication_governance", "project_authored_unverified", "blocked"
    if normalized.startswith(".opencode/"):
        return "candidate_public_core", "opencode_integration", "project_authored_unverified", "blocked"
    if normalized.startswith("数学建模全流程套件/engine/") or normalized.startswith(
        "数学建模全流程套件/tests/"
    ) or normalized.endswith("数学建模全流程套件/AGENTS.md"):
        return "candidate_public_core", "runtime_core", "project_authored_unverified", "blocked"
    if normalized.startswith("数学建模全流程套件/skills/"):
        source_status = "partial_notice_declared" if "humanities" in normalized else "unverified"
        return "experimental", "main_skills", source_status, "blocked"
    if normalized.startswith("数学建模全流程套件/tools/"):
        return "experimental", "main_tools", "unverified", "blocked"
    if normalized.startswith("数学建模全流程套件/data/"):
        return "private_extension", "main_reference_data", "unverified", "excluded"
    if normalized.startswith("数学建模全流程套件/"):
        return "candidate_public_core", "main_suite_support", "project_authored_unverified", "blocked"
    if name.endswith((".pdf", ".doc", ".docx", ".xlsx")) or name.lower().endswith((".jpg", ".jpeg", ".png")):
        return "private_extension", "private_research_material", "unverified", "excluded"
    return "historical_reference", "root_unclassified_artifact", "unverified", "excluded"


def sha256_file(path: Path) -> str:
    """Return a SHA-256 digest for a non-sensitive file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_output_path(relative_path: Path, output_relative: Path) -> bool:
    return relative_path == output_relative or output_relative in relative_path.parents


def _record(path: Path, root: Path) -> dict[str, Any]:
    relative_path = path.relative_to(root)
    classification, asset_group, source_status, release_status = classify_path(relative_path)
    stat = path.stat()
    sensitive = classification == "excluded_sensitive"
    return {
        "path": relative_path.as_posix(),
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "modified_at_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "classification": classification,
        "asset_group": asset_group,
        "source_status": source_status,
        "release_status": release_status,
        "sha256": None if sensitive else sha256_file(path),
        "notes": "Path-only sensitive record; content was not read." if sensitive else "Provisional inventory record.",
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    classification_rows = "\n".join(
        f"| `{name}` | {count} |" for name, count in summary["classification_counts"].items()
    )
    group_rows = "\n".join(
        f"| `{name}` | {count} |" for name, count in summary["asset_group_counts"].items()
    )
    return f"""# File-Level Asset Ledger

> **Status: provisional inventory evidence, not release authorization.** Generated at {summary["generated_at_utc"]}.

## Scope

- Root: `{summary["root"]}`
- Registered files: {summary["total_records"]}
- `.env` entries are path-only sensitive records. Their content was not opened and their SHA-256 values are `null`.
- No record establishes ownership, license, redistribution permission, formal capability status, or host compatibility.

## Classification Counts

| Classification | Files |
| --- | ---: |
{classification_rows}

## Asset Group Counts

| Asset group | Files |
| --- | ---: |
{group_rows}

## Required Follow-Up

Every `candidate_public_core` or `experimental` record remains blocked until provenance, licensing, dependency, security, benchmark, and OpenCode Desktop acceptance evidence is recorded. Private, historical, and sensitive records are excluded from a public package.
"""


def build_ledger(root: Path, output_dir: Path) -> dict[str, Any]:
    """Scan root and write deterministic JSONL, JSON summary, and Markdown outputs."""
    root = root.resolve()
    output_dir = output_dir.resolve()
    output_relative = output_dir.relative_to(root)
    records = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        if _is_output_path(relative_path, output_relative):
            continue
        records.append(_record(path, root))

    classification_counts = Counter(record["classification"] for record in records)
    asset_group_counts = Counter(record["asset_group"] for record in records)
    source_status_counts = Counter(record["source_status"] for record in records)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "total_records": len(records),
        "classification_counts": dict(sorted(classification_counts.items())),
        "asset_group_counts": dict(sorted(asset_group_counts.items())),
        "source_status_counts": dict(sorted(source_status_counts.items())),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "asset-ledger.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    (output_dir / "asset-ledger-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "ASSET_LEDGER.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def check_ledger(output_dir: Path) -> dict[str, Any]:
    """Validate generated ledger shape, ordering, and summary counts."""
    jsonl_path = output_dir / "asset-ledger.jsonl"
    summary_path = output_dir / "asset-ledger-summary.json"
    markdown_path = output_dir / "ASSET_LEDGER.md"
    if not jsonl_path.is_file() or not summary_path.is_file() or not markdown_path.is_file():
        raise ValueError("Ledger outputs are incomplete.")
    records = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line]
    paths = [record["path"] for record in records]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ValueError("Ledger paths must be unique and sorted.")
    required = {
        "path",
        "extension",
        "size_bytes",
        "modified_at_utc",
        "classification",
        "asset_group",
        "source_status",
        "release_status",
        "sha256",
        "notes",
    }
    for record in records:
        if required - set(record):
            raise ValueError(f"Ledger record misses required fields: {record.get('path', '<unknown>')}")
        if record["classification"] == "excluded_sensitive" and record["sha256"] is not None:
            raise ValueError(f"Sensitive record has a hash: {record['path']}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("total_records") != len(records):
        raise ValueError("Summary total does not match JSONL record count.")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a conservative file-level asset ledger.")
    parser.add_argument("--root", default=".", help="Workspace root to scan.")
    parser.add_argument("--output", default="governance", help="Output directory, relative to root when not absolute.")
    parser.add_argument("--check", action="store_true", help="Validate existing ledger output without scanning.")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output)
    output_dir = output if output.is_absolute() else root / output
    if args.check:
        summary = check_ledger(output_dir)
        print(json.dumps({"status": "ok", "total_records": summary["total_records"]}, ensure_ascii=False))
    else:
        summary = build_ledger(root, output_dir)
        print(json.dumps({"status": "built", "total_records": summary["total_records"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
