"""Deterministic local figure/code/data discovery with newest-version receipts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DISCOVERY_CONTRACT_VERSION = "figmirror.source-discovery.v1"
ASSET_SUFFIXES = {
    "figure": {".pdf", ".svg", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pptx"},
    "data": {".xlsx", ".xls", ".csv", ".tsv", ".json", ".parquet"},
    "code": {".py", ".r", ".m", ".js", ".mjs", ".ts", ".qmd", ".ipynb"},
}
IGNORED_PARTS = {
    ".git",
    ".project-atlas",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "vendor",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _utc_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _query_tokens(value: str) -> tuple[str, ...]:
    return tuple(token for token in re.findall(r"[\w\u3400-\u9fff]+", value.casefold()) if token)


def _match_score(path: Path, root: Path, tokens: tuple[str, ...]) -> int:
    if not tokens:
        return 1
    relative = path.relative_to(root).as_posix().casefold()
    stem = path.stem.casefold()
    stem_hits = sum(2 for token in tokens if token in stem)
    path_hits = sum(1 for token in tokens if token in relative and token not in stem)
    return stem_hits + path_hits


def _resolve_override(root: Path, value: str | Path | None, label: str) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes discovery root: {path}") from exc
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    return path


def discover_source_versions(
    root: str | Path,
    *,
    asset_kind: str,
    semantic_query: str,
    current_figure: str | Path | None = None,
    user_selected: str | Path | None = None,
    output: str | Path | None = None,
) -> dict[str, Any]:
    """Find semantic matches and select user/current overrides before newest mtime.

    Automatic discovery first keeps only the highest semantic-match tier.  If
    several local versions remain, nanosecond mtime wins; an exact timestamp
    tie is resolved by normalized relative path so the receipt is replayable.
    """

    project_root = Path(root).resolve()
    if not project_root.is_dir():
        raise ValueError(f"discovery root is not a directory: {project_root}")
    if asset_kind not in ASSET_SUFFIXES:
        raise ValueError("asset_kind must be figure, data, or code")
    tokens = _query_tokens(semantic_query)
    records: list[dict[str, Any]] = []
    for path in project_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in ASSET_SUFFIXES[asset_kind]:
            continue
        relative = path.relative_to(project_root)
        if any(part.casefold() in IGNORED_PARTS or part.casefold().startswith("tmp") for part in relative.parts):
            continue
        score = _match_score(path, project_root, tokens)
        if score <= 0:
            continue
        stat = path.stat()
        records.append(
            {
                "path": str(path.resolve()),
                "relative_path": relative.as_posix(),
                "semantic_match_score": score,
                "mtime_ns": stat.st_mtime_ns,
                "mtime_utc": _utc_iso(stat.st_mtime),
                "bytes": stat.st_size,
                "sha256": _sha256(path),
            }
        )
    highest_score = max((int(item["semantic_match_score"]) for item in records), default=0)
    semantic_matches = [item for item in records if int(item["semantic_match_score"]) == highest_score]
    semantic_matches.sort(key=lambda item: (-int(item["mtime_ns"]), str(item["relative_path"]).casefold()))

    selected_override = _resolve_override(project_root, user_selected, "user_selected")
    precedence = "user_selected"
    if selected_override is None:
        selected_override = _resolve_override(project_root, current_figure, "current_figure")
        precedence = "explicit_current_figure"
    if selected_override is not None:
        stat = selected_override.stat()
        selected = {
            "path": str(selected_override),
            "relative_path": (
                selected_override.relative_to(project_root).as_posix()
                if selected_override.is_relative_to(project_root)
                else None
            ),
            "semantic_match_score": _match_score(selected_override, project_root, tokens)
            if selected_override.is_relative_to(project_root)
            else None,
            "mtime_ns": stat.st_mtime_ns,
            "mtime_utc": _utc_iso(stat.st_mtime),
            "bytes": stat.st_size,
            "sha256": _sha256(selected_override),
        }
        tie_break = "override_precedence"
    else:
        if not semantic_matches:
            raise ValueError(f"no {asset_kind} asset matched semantic query: {semantic_query}")
        selected = dict(semantic_matches[0])
        precedence = "newest_mtime"
        top_mtime = int(selected["mtime_ns"])
        tied = [item for item in semantic_matches if int(item["mtime_ns"]) == top_mtime]
        tie_break = "normalized_relative_path_ascending" if len(tied) > 1 else "none"

    receipt = {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "status": "SELECTED",
        "asset_kind": asset_kind,
        "semantic_query": semantic_query,
        "root": str(project_root),
        "precedence": precedence,
        "selection_rule": "user_selected > explicit_current_figure > highest_semantic_match > newest_mtime > normalized_relative_path",
        "selected": selected,
        "candidate_count": len(semantic_matches),
        "candidates": semantic_matches,
        "tie_break": tie_break,
    }
    if output is not None:
        destination = Path(output)
        if not destination.is_absolute():
            destination = project_root / destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        receipt["receipt_path"] = str(destination.resolve())
    return receipt
