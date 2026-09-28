"""Candidate / prompt-index identity coherence helpers for v3.2.15f.

The workflow treats prompt-index candidate ids as the source of truth for image
stages. Generated rasters, target_image_path, candidate registry rows,
substage rows, artifact ids, and checkpoint inventories must use the same
candidate id. These helpers are deliberately paper-agnostic: they validate
shape and path consistency without knowing any paper-specific module names.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .constants import (
    STEP_OUTPUT_DIRS,
    TARGET_RASTER_IMAGE_EXTS,
    S5_REFERENCE_IMAGE_INPUT_POLICY,
    S5_REFERENCE_IMAGE_ROW_FIELD,
)
from .errors import StateError
from .paths import normalize_relative_path, safe_join

DEFAULT_CANDIDATE_ID_PREFIX_BY_STEP = {
    "S2-SKETCH-EXPLORE": "C",
    "S5-CANDIDATE-IMAGE": "F",
}

PROMPT_INDEX_PATH_BY_STEP = {
    "S2-SKETCH-EXPLORE": "outputs/S2-sketch-explore/prompt-index.json",
    "S5-CANDIDATE-IMAGE": "outputs/S5-candidate-image/prompt-index.json",
}

SAFE_CANDIDATE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CANDIDATE_PATH_SEGMENT_RE = re.compile(r"(?:^|/)candidates/([^/]+)/", re.I)


def normalize_candidate_id(value: Any, *, label: str = "candidate_id") -> str:
    cid = str(value or "").strip()
    if not cid:
        raise StateError(f"{label} is required")
    if not SAFE_CANDIDATE_ID_RE.fullmatch(cid):
        raise StateError(
            f"{label}={cid!r} is not safe for path/id use; use letters, digits, dot, underscore, or hyphen only"
        )
    return cid


def candidate_id_for_index(step: str, index: int) -> str:
    prefix = DEFAULT_CANDIDATE_ID_PREFIX_BY_STEP.get(step, "C")
    return f"{prefix}{index:02d}"


def candidate_id_path_segment(path_value: Any) -> str | None:
    if not isinstance(path_value, str) or not path_value:
        return None
    rel = normalize_relative_path(path_value)
    match = CANDIDATE_PATH_SEGMENT_RE.search(rel)
    return match.group(1) if match else None


def assert_path_candidate_id(path_value: Any, candidate_id: str, *, label: str) -> str:
    rel = normalize_relative_path(path_value)
    segment = candidate_id_path_segment(rel)
    if segment is not None and segment != candidate_id:
        raise StateError(
            f"{label} candidate id mismatch: path uses candidates/{segment}/ but row candidate_id is {candidate_id!r}: {rel}"
        )
    return rel


def normalize_reference_image_paths(value: Any, *, label: str = S5_REFERENCE_IMAGE_ROW_FIELD) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise StateError(f"{label} must be a list of project-run-relative raster image paths")
    paths: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(value, start=1):
        if not isinstance(raw, str) or not raw:
            raise StateError(f"{label}[{index}] must be a non-empty path string")
        rel = normalize_relative_path(raw)
        if Path(rel).suffix.lower() not in TARGET_RASTER_IMAGE_EXTS:
            raise StateError(f"{label}[{index}] must be a raster PNG/JPG/JPEG/WebP path: {rel}")
        if rel not in seen:
            seen.add(rel)
            paths.append(rel)
    return paths


def default_candidate_paths(step: str, candidate_id: str) -> dict[str, str]:
    cid = normalize_candidate_id(candidate_id)
    output_dir = STEP_OUTPUT_DIRS[step]
    base = f"{output_dir}/candidates/{cid}"
    return {
        "candidate_dir": base,
        "prompt_path": f"{base}/prompt-v01.md",
        "target_image_path": f"{base}/image-v01.png",
        "active_image_path": f"{base}/image-v01.png",
        "active_audit_json": f"{base}/audit-latest.json",
        "active_audit_md": f"{base}/audit-latest.md",
        "status_path": f"{base}/status.json",
        "audit_history_dir": f"{base}/audit-history",
        "revision_history_dir": f"{base}/revision-history",
    }


def _candidate_rows_from_raw(data: dict[str, Any], *, stage: str | None = None) -> list[dict[str, Any]]:
    raw = data.get("candidates")
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for index, row in enumerate(raw, start=1):
            if not isinstance(row, dict):
                raise StateError(f"prompt-index candidates[{index}] is not an object")
            rows.append(dict(row))
    elif isinstance(raw, dict):
        for key, row in raw.items():
            if not isinstance(row, dict):
                raise StateError(f"prompt-index candidates[{key!r}] is not an object")
            payload = dict(row)
            payload.setdefault("candidate_id", key)
            rows.append(payload)
    else:
        raise StateError("prompt-index must contain candidates as a list or object")

    normalized_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        cid_value = row.get("candidate_id") or row.get("id") or (candidate_id_for_index(stage, index) if stage else f"C{index:02d}")
        cid = normalize_candidate_id(cid_value, label=f"prompt-index candidate row {index}.candidate_id")
        if cid in seen:
            raise StateError(f"duplicate prompt-index candidate_id: {cid}")
        seen.add(cid)
        defaults = default_candidate_paths(stage, cid) if stage else {}
        prompt_path = row.get("prompt_path") or defaults.get("prompt_path")
        target_image_path = row.get("target_image_path") or row.get("active_image_path") or defaults.get("target_image_path")
        if not prompt_path:
            raise StateError(f"prompt-index row {cid} lacks prompt_path")
        if not target_image_path:
            raise StateError(f"prompt-index row {cid} lacks target_image_path")
        prompt_rel = assert_path_candidate_id(prompt_path, cid, label=f"prompt-index row {cid}.prompt_path")
        target_rel = assert_path_candidate_id(target_image_path, cid, label=f"prompt-index row {cid}.target_image_path")
        if Path(target_rel).suffix.lower() not in TARGET_RASTER_IMAGE_EXTS:
            raise StateError(f"prompt-index row {cid}.target_image_path must be a raster image path: {target_rel}")
        normalized = dict(row)
        normalized["candidate_id"] = cid
        normalized["prompt_path"] = prompt_rel
        normalized["target_image_path"] = target_rel
        if S5_REFERENCE_IMAGE_ROW_FIELD in row:
            normalized[S5_REFERENCE_IMAGE_ROW_FIELD] = normalize_reference_image_paths(
                row.get(S5_REFERENCE_IMAGE_ROW_FIELD),
                label=f"prompt-index row {cid}.{S5_REFERENCE_IMAGE_ROW_FIELD}",
            )
        normalized_rows.append(normalized)
    return normalized_rows


def normalize_prompt_index(data: dict[str, Any], *, stage: str | None = None) -> dict[str, Any]:
    rows = _candidate_rows_from_raw(data, stage=stage)
    normalized = {
        **data,
        "schema_version": max(2, int(data.get("schema_version") or 1)),
        "stage": data.get("stage") or stage,
        "candidate_ids": [row["candidate_id"] for row in rows],
        "candidates": rows,
        "candidate_map": {row["candidate_id"]: row for row in rows},
        "candidate_id_source_of_truth": "prompt-index candidates[].candidate_id",
        "id_path_coherence_rule": "candidate_id must match the candidates/<candidate_id>/ path segment in prompt_path, target_image_path, active_image_path, registry rows, artifacts, and checkpoints.",
    }
    if normalized.get("stage") == "S5-CANDIDATE-IMAGE":
        normalized.setdefault("s5_reference_image_input_policy", S5_REFERENCE_IMAGE_INPUT_POLICY)
    return normalized


def load_prompt_index(
    run_dir: Path,
    prompt_index: str | Path,
    *,
    stage: str | None = None,
    require_prompt_files: bool = False,
) -> dict[str, Any]:
    rel = normalize_relative_path(prompt_index)
    path = safe_join(run_dir, rel)
    if not path.is_file():
        raise StateError(f"prompt index does not exist: {rel}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise StateError(f"prompt index is not a JSON object: {rel}")
    normalized = normalize_prompt_index(data, stage=stage)
    normalized["prompt_index_path"] = rel
    if require_prompt_files:
        missing: list[str] = []
        for row in normalized["candidates"]:
            prompt_rel = row["prompt_path"]
            if not safe_join(run_dir, prompt_rel).is_file():
                missing.append(prompt_rel)
        if missing:
            raise StateError("prompt-index prompt_path files are missing: " + ", ".join(missing))
    return normalized


def default_prompt_index_path(step: str) -> str:
    return PROMPT_INDEX_PATH_BY_STEP[step]


def safe_id_fragment(candidate_id: str) -> str:
    return normalize_candidate_id(candidate_id).lower().replace("_", "-").replace(".", "-")
