"""S2/S5 image-only stage orchestration and checkpoint helpers for v3.2.15f."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from .constants import (
    CANDIDATE_STATUS_VALUES,
    CHATGPT_WEB_IMAGE_CHUNK_LIMIT,
    CHATGPT_WEB_RECOMMENDED_IMAGE_CHUNK_SIZE,
    CODEX_IMAGE_CHUNK_LIMIT,
    DEFAULT_CANDIDATE_COUNT_BY_STEP,
    DEFAULT_NEXT_STEP_BY_STEP,
    IMAGE_ONLY_ROW_ATOMICITY_POLICY,
    MAX_CANDIDATE_COUNT_BY_STEP,
    S5_REFERENCE_IMAGE_INPUT_POLICY,
    S5_REFERENCE_IMAGE_ROW_FIELD,
    STEP_OUTPUT_DIRS,
    SUBSTAGE_STATUS_VALUES,
    SUBSTAGE_STEPS,
    TARGET_RASTER_IMAGE_EXTS,
    WORKFLOW_STEPS,
)
from .errors import StateError
from .paths import normalize_relative_path, safe_join, utc_now, write_json
from .identity import (
    assert_path_candidate_id,
    candidate_id_for_index,
    default_candidate_paths,
    default_prompt_index_path,
    load_prompt_index,
    normalize_candidate_id,
    safe_id_fragment,
)


FINAL_CANDIDATE_STATUS_VALUES = {"PASS", "FLAG_MINOR", "FLAG_MAJOR", "BLOCKED", "ISSUE_LEDGER_READY", "HAS_ISSUES", "HAS_BLOCKER_ISSUE", "NEEDS_HUMAN_SELECTION"}

# Checkpoint restore semantics distinguish assets that already exist or were
# produced by a completed image unit from future planned outputs. This keeps
# upstream text-stage checkpoints resume-ready without treating not-yet-generated
# candidate images as missing, while still blocking restore if any already
# generated/registered raster asset is absent.
IMAGE_REQUIRED_CANDIDATE_STATUS_VALUES = FINAL_CANDIDATE_STATUS_VALUES | {"NEEDS_REVIEW"}
IMAGE_PENDING_CANDIDATE_STATUS_VALUES = {"PENDING", "MISSING", None, ""}

AGGREGATE_REPORT_FILES = {
    "S2-SKETCH-EXPLORE": [
        "outputs/S2-sketch-explore/s2-sketch-explore-report.md",
        "outputs/S2-sketch-explore/sketch-explore-report.md",
        "outputs/S2-sketch-explore/s2-sketch-report.md",
    ],
    "S5-CANDIDATE-IMAGE": [
        "outputs/S5-candidate-image/s5-candidate-image-report.md",
        "outputs/S5-candidate-image/candidate-image-report.md",
        "outputs/S5-candidate-image/s5-candidates-report.md",
    ],
}


def step_prefix(step: str) -> str:
    if step == "S2-SKETCH-EXPLORE":
        return "S2"
    if step == "S5-CANDIDATE-IMAGE":
        return "S5"
    raise StateError("dynamic substages are supported only for S2-SKETCH-EXPLORE and S5-CANDIDATE-IMAGE")


def candidate_registry_key(step: str) -> str:
    return "s2_sketches" if step == "S2-SKETCH-EXPLORE" else "s5_candidates"


def runtime_from_state(state: dict[str, Any], explicit_runtime: str | None = None) -> str:
    if explicit_runtime:
        return explicit_runtime
    runtime = state.get("runtime_environment", {})
    if isinstance(runtime, dict):
        return runtime.get("environment") or "unknown"
    return "unknown"


def image_chunk_limit(runtime: str) -> int:
    return CHATGPT_WEB_IMAGE_CHUNK_LIMIT if runtime == "chatgpt_web" else CODEX_IMAGE_CHUNK_LIMIT


def image_chunk_size(runtime: str) -> int:
    if runtime == "chatgpt_web":
        return min(CHATGPT_WEB_RECOMMENDED_IMAGE_CHUNK_SIZE, CHATGPT_WEB_IMAGE_CHUNK_LIMIT)
    return CODEX_IMAGE_CHUNK_LIMIT


def validate_candidate_count(step: str, count: int) -> None:
    default_count = DEFAULT_CANDIDATE_COUNT_BY_STEP[step]
    max_count = MAX_CANDIDATE_COUNT_BY_STEP[step]
    if count < 1 or (max_count is not None and count > max_count):
        upper = "unbounded when prompt-index/preference coverage requires expansion" if max_count is None else str(max_count)
        raise StateError(f"{step} candidate count must be at least 1 and at most {upper}")
    if count != default_count:
        raise StateError(
            f"{step} must keep exactly {default_count} candidates unless a validated prompt-index "
            "explicitly defines that same stage candidate set"
        )


def candidate_id(index: int, step: str = "S2-SKETCH-EXPLORE") -> str:
    return candidate_id_for_index(step, index)


def candidate_range_label_from_ids(candidate_ids: list[str]) -> str:
    if not candidate_ids:
        return "empty"
    if len(candidate_ids) == 1:
        return safe_id_fragment(candidate_ids[0])
    return f"{safe_id_fragment(candidate_ids[0])}-{safe_id_fragment(candidate_ids[-1])}"


def candidate_paths(step: str, cid: str) -> dict[str, str]:
    paths = default_candidate_paths(step, cid)
    # Internal callers may use active_image_path; prompt indexes use target_image_path.
    paths.setdefault("target_image_path", paths["active_image_path"])
    return paths


def manifest_candidate_row(manifest: dict[str, Any] | None, cid: str) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return {}
    candidates = manifest.get("candidates")
    if isinstance(candidates, dict):
        row = candidates.get(cid)
        return row if isinstance(row, dict) else {}
    if isinstance(candidates, list):
        for row in candidates:
            if isinstance(row, dict) and (row.get("candidate_id") or row.get("id")) == cid:
                return row
    return {}


def manifest_candidate_image_path(manifest: dict[str, Any] | None, cid: str) -> str | None:
    row = manifest_candidate_row(manifest, cid)
    for key in ("active_image_path", "target_image_path", "expected_image_path", "image_path", "relative_path"):
        rel = image_path_candidate(row.get(key))
        if rel:
            return rel
    return None


def registered_candidate_paths(
    step: str, cid: str, state: dict[str, Any] | None = None, manifest: dict[str, Any] | None = None
) -> dict[str, str]:
    paths = candidate_paths(step, cid)
    manifest_image_path = manifest_candidate_image_path(manifest, cid)
    if manifest_image_path:
        paths["active_image_path"] = manifest_image_path
    if not isinstance(state, dict):
        return paths
    registry = state.get("candidate_run_registry", {}).get(candidate_registry_key(step), {})
    row = registry.get(cid) if isinstance(registry, dict) else None
    if not isinstance(row, dict):
        return paths
    for key in ("active_image_path", "active_audit_json", "active_audit_md", "status_path"):
        rel = row.get(key)
        if isinstance(rel, str) and rel:
            paths[key] = normalize_relative_path(rel)
    return paths


def make_substage_plan(step: str, runtime: str, candidate_count: int, candidate_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Return v3.2.15f image-only plans for S2/S5.

    Text preparation is owned by S1/S4. Review/aggregate over S2 outputs is owned by S3.
    S5 has no assistant-side audit/aggregate/candidate revision after image generation.
    Every image-generation unit is row-atomic: one prompt-index row, one candidate_id,
    one prompt_path, one target_image_path, and one active raster registration.
    """
    prefix = step_prefix(step)
    candidate_ids = candidate_ids or [candidate_id_for_index(step, i) for i in range(1, candidate_count + 1)]
    if len(candidate_ids) != candidate_count:
        raise StateError(f"{step} candidate_count={candidate_count} does not match candidate_ids length={len(candidate_ids)}")
    limit = image_chunk_limit(runtime)
    chunk_size = image_chunk_size(runtime)
    rows: list[dict[str, Any]] = []
    ordinal = 1
    for start in range(0, candidate_count, chunk_size):
        cids = [normalize_candidate_id(cid) for cid in candidate_ids[start : start + chunk_size]]
        label = candidate_range_label_from_ids(cids)
        rows.append(
            {
                "substage_id": f"{prefix}-{ordinal:02d}-image-generate-{label}",
                "mode": "IMAGE_GENERATE",
                "candidate_ids": cids,
                "status": "pending",
                "image_chunk_limit": limit,
                "planned_chunk_size": len(cids),
                "rule": (
                    "Generate only the single prompt-index candidate listed in candidate_ids. This is a row-atomic image call: "
                    "read exactly that row prompt_path, activate exactly that candidate_id, and mirror the raster to exactly that row target_image_path. "
                    "Use the environment-locked image route only: Codex=image_gen; ChatGPT web=Create Image / ChatGPT Images 2.0; "
                    "other runtimes=named approved image-generation API. Do not write audit/ranking/explanation/aggregate/next-step text. "
                    "Do not create SVG, code-drawn PNGs, screenshots, PPT/PDF renders, or local programmatic raster substitutes. "
                    "Do not composite, tile, contact-sheet, batch-render, or combine multiple prompt-index rows in one image."
                ),
            }
        )
        ordinal += 1
    return rows


def manifest_candidate_rows_from_prompt_index(step: str, candidate_ids: list[str], prompt_index_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    by_id = {}
    for row in prompt_index_rows or []:
        if not isinstance(row, dict):
            continue
        try:
            cid = normalize_candidate_id(row.get("candidate_id"))
        except StateError:
            continue
        by_id[cid] = row
    rows: list[dict[str, Any]] = []
    for cid in candidate_ids:
        cid = normalize_candidate_id(cid)
        defaults = candidate_paths(step, cid)
        source = by_id.get(cid, {})
        prompt_path = source.get("prompt_path") or defaults["prompt_path"]
        target_image_path = source.get("target_image_path") or defaults["target_image_path"]
        candidate_row = {
            "candidate_id": cid,
            "candidate_dir": defaults["candidate_dir"],
            "prompt_path": assert_path_candidate_id(prompt_path, cid, label=f"manifest candidate {cid}.prompt_path"),
            "target_image_path": assert_path_candidate_id(target_image_path, cid, label=f"manifest candidate {cid}.target_image_path"),
            "active_image_path": assert_path_candidate_id(target_image_path, cid, label=f"manifest candidate {cid}.active_image_path"),
            "status_path": defaults["status_path"],
        }
        if step == "S5-CANDIDATE-IMAGE" and isinstance(source.get(S5_REFERENCE_IMAGE_ROW_FIELD), list):
            candidate_row[S5_REFERENCE_IMAGE_ROW_FIELD] = source.get(S5_REFERENCE_IMAGE_ROW_FIELD)
        rows.append(candidate_row)
    return rows


def default_manifest(step: str, runtime: str, candidate_count: int, candidate_ids: list[str] | None = None, prompt_index_path: str | None = None, prompt_index_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    now = utc_now()
    upstream_prepare_stage = "S1-FIGURE-STRATEGY" if step == "S2-SKETCH-EXPLORE" else "S4-CANDIDATE-BRIEF"
    downstream_text_stage = "S3-DIRECTION-SELECT" if step == "S2-SKETCH-EXPLORE" else None
    normalized_candidate_ids = [normalize_candidate_id(cid) for cid in (candidate_ids or [candidate_id_for_index(step, i) for i in range(1, candidate_count + 1)])]
    prompt_index_candidate_rows = manifest_candidate_rows_from_prompt_index(step, normalized_candidate_ids, prompt_index_rows)
    return {
        "schema_version": 2,
        "stage": step,
        "created_at": now,
        "updated_at": now,
        "runtime": runtime,
        "image_chunk_limit": image_chunk_limit(runtime),
        "recommended_image_chunk_size": image_chunk_size(runtime),
        "candidate_count": candidate_count,
        "max_candidate_count": MAX_CANDIDATE_COUNT_BY_STEP[step],
        "candidate_ids": normalized_candidate_ids,
        "candidates": prompt_index_candidate_rows,
        "prompt_index_path": prompt_index_path,
        "candidate_id_source_of_truth": "prompt-index" if prompt_index_path else "stage-default-prefix",
        "candidate_id_coherence_policy": "Use the exact same candidate_id in prompt-index rows, substage candidate_ids, candidate directory, active_image_path/target_image_path, artifacts, and checkpoint manifests. Do not renumber S5 candidates as Cxx when the prompt-index uses Fxx or any other registered id.",
        "s5_reference_image_input_policy": S5_REFERENCE_IMAGE_INPUT_POLICY if step == "S5-CANDIDATE-IMAGE" else None,
        "v3215_image_only_policy": {
            "upstream_prepare_stage": upstream_prepare_stage,
            "downstream_text_stage": downstream_text_stage,
            "text_plan_substage_removed": True,
            "candidate_revision_loop_removed": True,
            "text_recheck_removed": True,
            "aggregate_substage_removed": True,
            "s5_is_terminal": step == "S5-CANDIDATE-IMAGE",
        },
        "substage_execution_policy": {
            "chatgpt_web": "use row-atomic image calls only: one selected/non-skipped prompt-index row per Create Image call; never satisfy multiple candidate rows with one broad/batch/composite image",
            "codex": "candidate image workers may run in parallel, but every worker is row-atomic and must call image_gen for exactly one prompt-index candidate; only the coordinator writes project-state.json",
            "image_route_guard": "Image stages are not file-production chores. They must call the runtime image-generation route: Codex=image_gen; ChatGPT web=Create Image / ChatGPT Images 2.0; other runtimes=named approved image-generation API. SVG, Python/PIL, Matplotlib, Graphviz, TikZ, Mermaid, canvas, PPT/PDF rendering, screenshots, and local programmatic raster PNG/WebP files are invalid even when target_image_path is filled.",
            "text_image_separation": "S2 and S5 image stages must not write audit/ranking/explanation/aggregate/next-step text. S1 owns S2 prompt preparation, S3 owns S3 review/aggregate over S2 outputs, and S4 owns S5 prompt preparation.",
            "row_atomic_completion_gate": "The stage is incomplete until every selected and non-skipped prompt-index row has exactly one active generated raster mirrored to that same row target_image_path and bound to the same candidate_id; orphan rasters are not candidate outputs.",
            "user_guidance": "Before image-only units, the preceding text stage shows only a compact prompt-index or prompt-file reference as user-facing copyable text; full image prompts stay in prompt files.",
            "prompt_readiness": "S1/S4 must save evidence lock, edge-support ledger, connector multiplicity/bundling audit, data consumer/transformer ledger, false relay data-flow audit, reviewer first-glance gate, element layout plan, routing and evidence-backed arrow plan, edge-label-first variable placement, modularity-not-fragmentation gate, simple internal motif gate, text/symbol verification, density and whitespace budget, layout_information_density_plan, canvas_area_budget, context_inset_budget, mainline_center_of_gravity_gate, repeated-flow compression plan, redundancy budget, background/context budget gate, style-combination complementarity audit, human palette contract, and prompt hallucination audit before IMAGE_GENERATE; max five audit/repair cycles.",
            "s5_reference_inputs": "For S5, read row-level reference_image_paths from the prompt-index and candidate prompt package. Attach those S2 rasters as references when supported by the image route; otherwise ignore them automatically and continue with the text prompt.",
        },
        "image_only_row_atomicity_policy": IMAGE_ONLY_ROW_ATOMICITY_POLICY,
        "substage_plan": make_substage_plan(step, runtime, candidate_count, candidate_ids=normalized_candidate_ids),
        "default_next_step": DEFAULT_NEXT_STEP_BY_STEP[step],
    }


def ensure_substage_dirs(run_dir: Path, step: str, manifest: dict[str, Any]) -> None:
    output_dir = STEP_OUTPUT_DIRS[step]
    safe_join(run_dir, output_dir).mkdir(parents=True, exist_ok=True)
    safe_join(run_dir, f"{output_dir}/substages").mkdir(parents=True, exist_ok=True)
    safe_join(run_dir, f"{output_dir}/substage-guides").mkdir(parents=True, exist_ok=True)
    for substage in manifest.get("substage_plan", []):
        safe_join(run_dir, f"{output_dir}/substages/{substage['substage_id']}").mkdir(parents=True, exist_ok=True)
    for cid in manifest.get("candidate_ids", []):
        cid = normalize_candidate_id(cid)
        paths = candidate_paths(step, cid)
        safe_join(run_dir, paths["candidate_dir"]).mkdir(parents=True, exist_ok=True)
        safe_join(run_dir, paths["audit_history_dir"]).mkdir(parents=True, exist_ok=True)
        safe_join(run_dir, paths["revision_history_dir"]).mkdir(parents=True, exist_ok=True)


def upsert_candidate_registry(state: dict[str, Any], step: str, manifest: dict[str, Any]) -> None:
    registry = state.setdefault("candidate_run_registry", {})
    candidate_rows = registry.setdefault(candidate_registry_key(step), {})
    for cid in manifest.get("candidate_ids", []):
        cid = normalize_candidate_id(cid)
        paths = candidate_paths(step, cid)
        manifest_row = manifest_candidate_row(manifest, cid)
        manifest_image_path = manifest_candidate_image_path(manifest, cid)
        if manifest_image_path:
            paths["active_image_path"] = manifest_image_path
        existing = candidate_rows.setdefault(cid, {})
        update_payload = {
            "step": step,
            "candidate_id": cid,
            "status": existing.get("status", "PENDING"),
            "attempt": int(existing.get("attempt") or 1),
            "revision_attempts_used": int(existing.get("revision_attempts_used") or 0),
            "candidate_dir": paths["candidate_dir"],
            "prompt_path": manifest_row.get("prompt_path") or existing.get("prompt_path") or paths.get("prompt_path"),
            "target_image_path": manifest_row.get("target_image_path") or existing.get("target_image_path") or paths["active_image_path"],
            "active_image_path": existing.get("active_image_path") or paths["active_image_path"],
            "active_audit_json": existing.get("active_audit_json") or paths["active_audit_json"],
            "status_path": paths["status_path"],
            "id_path_coherence_status": "planned_from_prompt_index" if manifest_row else existing.get("id_path_coherence_status", "planned_from_stage_default"),
            "updated_at": utc_now(),
        }
        if step == "S5-CANDIDATE-IMAGE":
            update_payload[S5_REFERENCE_IMAGE_ROW_FIELD] = manifest_row.get(S5_REFERENCE_IMAGE_ROW_FIELD) or existing.get(S5_REFERENCE_IMAGE_ROW_FIELD) or []
        existing.update(update_payload)


def upsert_substage_runs(state: dict[str, Any], step: str, manifest: dict[str, Any]) -> None:
    substage_runs = state.setdefault("substage_runs", {}).setdefault(step, {})
    for row in manifest.get("substage_plan", []):
        existing = substage_runs.setdefault(row["substage_id"], {})
        existing.update(
            {
                "stage": step,
                "substage_id": row["substage_id"],
                "mode": row["mode"],
                "candidate_ids": row.get("candidate_ids", []),
                "status": existing.get("status", row.get("status", "pending")),
                "updated_at": utc_now(),
            }
        )


def write_candidate_status_files(run_dir: Path, step: str, state: dict[str, Any]) -> None:
    registry = state.get("candidate_run_registry", {}).get(candidate_registry_key(step), {})
    for cid, row in registry.items():
        status_path = safe_join(run_dir, row.get("status_path") or candidate_paths(step, cid)["status_path"])
        status_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(status_path, row)


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def cmd_plan_substages(args: argparse.Namespace, run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    step = args.step
    if step not in SUBSTAGE_STEPS:
        raise StateError("plan-substages supports only S2-SKETCH-EXPLORE and S5-CANDIDATE-IMAGE")
    runtime = runtime_from_state(state, args.runtime)
    prompt_index_rel = getattr(args, "prompt_index", None)
    if not prompt_index_rel:
        default_index = default_prompt_index_path(step)
        if safe_join(run_dir, default_index).is_file():
            prompt_index_rel = default_index
    prompt_index = None
    candidate_ids = None
    if prompt_index_rel:
        prompt_index = load_prompt_index(run_dir, prompt_index_rel, stage=step, require_prompt_files=True)
        if step == "S5-CANDIDATE-IMAGE":
            missing_refs = [
                row.get("candidate_id")
                for row in prompt_index.get("candidates", [])
                if not isinstance(row.get(S5_REFERENCE_IMAGE_ROW_FIELD), list) or not row.get(S5_REFERENCE_IMAGE_ROW_FIELD)
            ]
            if missing_refs:
                raise StateError(
                    "S5 prompt-index rows must include non-empty reference_image_paths pointing to relevant registered S2 raster outputs: "
                    + ", ".join(str(cid) for cid in missing_refs)
                )
        candidate_ids = prompt_index["candidate_ids"]
    candidate_count = args.candidate_count or (len(candidate_ids) if candidate_ids else DEFAULT_CANDIDATE_COUNT_BY_STEP[step])
    if candidate_ids and args.candidate_count and args.candidate_count != len(candidate_ids):
        raise StateError(f"candidate-count {args.candidate_count} does not match prompt-index candidate count {len(candidate_ids)}")
    validate_candidate_count(step, candidate_count)
    manifest = default_manifest(step, runtime, candidate_count, candidate_ids=candidate_ids, prompt_index_path=prompt_index_rel, prompt_index_rows=(prompt_index or {}).get("candidates"))
    ensure_substage_dirs(run_dir, step, manifest)
    write_json(safe_join(run_dir, f"{STEP_OUTPUT_DIRS[step]}/stage-manifest.json"), manifest)
    upsert_candidate_registry(state, step, manifest)
    upsert_substage_runs(state, step, manifest)
    state.setdefault("substage_orchestration_policy", {})["last_planned_stage"] = {
        "step": step,
        "runtime": runtime,
        "candidate_count": candidate_count,
        "image_chunk_limit": image_chunk_limit(runtime),
        "created_at": utc_now(),
        "source_user_request": args.source_user_request or "",
    }
    state["updated_at"] = utc_now()
    write_candidate_status_files(run_dir, step, state)
    return manifest


def candidate_file_status(
    run_dir: Path, step: str, cid: str, state: dict[str, Any] | None = None, manifest: dict[str, Any] | None = None
) -> dict[str, Any]:
    paths = registered_candidate_paths(step, cid, state, manifest)
    image_path = safe_join(run_dir, paths["active_image_path"])
    status_path = safe_join(run_dir, paths["status_path"])
    image_exists = image_path.is_file()
    status_data = read_json_if_exists(status_path)
    status_file_exists = status_path.is_file()
    status_value = status_data.get("status") if status_data else None
    status_valid = status_value in CANDIDATE_STATUS_VALUES if status_value else True
    inferred = "complete" if image_exists else "missing_image"
    return {
        "candidate_id": cid,
        "image_exists": image_exists,
        "audit_latest_exists": False,
        "status_file_exists": status_file_exists,
        "status_value": status_value,
        "status_valid": status_valid,
        "final_status": image_exists,
        "inferred_status": inferred,
        **paths,
    }


def aggregate_report_exists(run_dir: Path, step: str) -> bool:
    for rel in AGGREGATE_REPORT_FILES.get(step, []):
        if safe_join(run_dir, rel).is_file():
            return True
    output_dir = safe_join(run_dir, STEP_OUTPUT_DIRS[step])
    return any(path.is_file() for path in output_dir.glob("*report*.md")) if output_dir.exists() else False


def checkpoint_exists(state: dict[str, Any], stage: str, checkpoint_type: str = "stage-final") -> bool:
    return any(
        bundle.get("stage") == stage and bundle.get("checkpoint_type") == checkpoint_type
        for bundle in state.get("checkpoint_bundles", [])
        if isinstance(bundle, dict)
    )


def substage_completion_report(state: dict[str, Any], step: str, manifest: dict[str, Any] | None) -> dict[str, Any]:
    if not manifest:
        return {
            "planned_count": 0,
            "complete_count": 0,
            "incomplete_substage_ids": [],
            "complete": False,
        }
    runs = state.get("substage_runs", {}).get(step, {})
    incomplete: list[str] = []
    complete_count = 0
    for row in manifest.get("substage_plan", []):
        substage_id = row.get("substage_id")
        run_row = runs.get(substage_id, {}) if substage_id else {}
        status = run_row.get("status") or row.get("status")
        skipped = bool(run_row.get("skip_reason") or run_row.get("intentional_skip_reason"))
        if status == "complete" or skipped:
            complete_count += 1
        elif substage_id:
            incomplete.append(substage_id)
    planned_count = len(manifest.get("substage_plan", []))
    return {
        "planned_count": planned_count,
        "complete_count": complete_count,
        "incomplete_substage_ids": incomplete,
        "complete": planned_count > 0 and not incomplete,
    }


def cmd_scan_substages(args: argparse.Namespace, run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    step = args.step
    manifest_path = safe_join(run_dir, f"{STEP_OUTPUT_DIRS[step]}/stage-manifest.json")
    manifest = None
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        candidate_ids = manifest.get("candidate_ids", [])
    else:
        count = args.candidate_count or DEFAULT_CANDIDATE_COUNT_BY_STEP[step]
        validate_candidate_count(step, count)
        candidate_ids = [candidate_id(i, step) for i in range(1, count + 1)]
    candidates = [candidate_file_status(run_dir, step, cid, state, manifest) for cid in candidate_ids]
    complete = [row["candidate_id"] for row in candidates if row["inferred_status"] == "complete"]
    missing = [row["candidate_id"] for row in candidates if row["inferred_status"] == "missing_image"]
    invalid_status = [row["candidate_id"] for row in candidates if row["status_file_exists"] and not row["status_valid"]]
    runtime = manifest.get("runtime") if isinstance(manifest, dict) else runtime_from_state(state, None)
    substage_report = substage_completion_report(state, step, manifest)
    candidate_set_complete = len(complete) == len(candidate_ids)
    stage_complete = candidate_set_complete and substage_report["complete"]
    report = {
        "stage": step,
        "runtime": runtime,
        "candidate_count": len(candidate_ids),
        "complete_candidates": complete,
        "needs_audit_candidates": [],
        "missing_image_candidates": missing,
        "invalid_or_nonfinal_status_candidates": invalid_status,
        "candidate_set_complete": candidate_set_complete,
        "aggregate_report_exists": False,
        "aggregate_required": False,
        "substage_completion": substage_report,
        "stage_final_checkpoint_exists": False,
        "checkpoint_required": False,
        "stage_complete": stage_complete,
        "complete": stage_complete,
        "candidates": candidates,
        "v3215_policy": "S2/S5 image stages complete when all planned image chunks are complete and active raster images exist, with candidate ids matching prompt-index/registry/artifact/checkpoint records. Text review/aggregate/candidate revision substages are removed.",
        "scanned_at": utc_now(),
    }
    state.setdefault("substage_orchestration_policy", {})["last_scan"] = report
    state["updated_at"] = utc_now()
    return report


def guidance_for_substage(state: dict[str, Any], step: str, substage_id: str | None) -> dict[str, Any] | None:
    if not substage_id:
        return None
    row = state.get("substage_guidance_registry", {}).get(step, {}).get(substage_id)
    return row if isinstance(row, dict) else None


def find_next_image_substage(manifest: dict[str, Any] | None, candidate_ids: list[str]) -> dict[str, Any] | None:
    wanted = set(candidate_ids)
    if not manifest:
        return None
    for row in manifest.get("substage_plan", []):
        if row.get("mode") != "IMAGE_GENERATE":
            continue
        if wanted.intersection(row.get("candidate_ids", [])):
            return row
    return None


def cmd_recommend_next_action(args: argparse.Namespace, run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    step = args.step or state.get("current_step")
    if not step:
        raise StateError("cannot recommend a next action without --step or current_step in state")
    if step in SUBSTAGE_STEPS:
        scan_args = argparse.Namespace(step=step, candidate_count=getattr(args, "candidate_count", None))
        report = cmd_scan_substages(scan_args, run_dir, state)
        manifest_path = safe_join(run_dir, f"{STEP_OUTPUT_DIRS[step]}/stage-manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig")) if manifest_path.exists() else None
        if report["missing_image_candidates"]:
            image_row = find_next_image_substage(manifest, report["missing_image_candidates"])
            guidance = guidance_for_substage(state, step, image_row.get("substage_id") if image_row else None)
            recommendation = {
                "action": "resume_image_generation",
                "mode": image_row.get("mode") if image_row else "IMAGE_GENERATE",
                "substage_id": image_row.get("substage_id") if image_row else None,
                "candidate_ids": image_row.get("candidate_ids") if image_row else report["missing_image_candidates"],
                "guidance": guidance,
                "v3215_policy": "S2/S5 only generate images; candidate ids must match the prompt-index source of truth; text review/aggregate/candidate revision substages are removed.",
            }
        else:
            next_step = DEFAULT_NEXT_STEP_BY_STEP.get(step)
            if step == "S5-CANDIDATE-IMAGE":
                recommendation = {
                    "action": "workflow_complete_human_decision",
                    "mode": "TERMINAL",
                    "next_main_step": None,
                    "message": "我的任务已经完成，剩下由人类来决策。",
                }
            else:
                recommendation = {
                    "action": "main_stage_complete",
                    "mode": "TEXT_NEXT_PROMPT",
                    "next_main_step": next_step,
                    "guidance": state.get("next_prompt_registry", {}).get(step),
                }
        navigation_state = {
            "resolved_current_stage": step,
            "resolved_from": ["explicit step argument or current_step", "prompt-index/image scan"],
            "image_only_stage_completed_for_navigation": bool(step in SUBSTAGE_STEPS and not report["missing_image_candidates"]),
            "checkpoint_may_lag": bool(step in SUBSTAGE_STEPS),
            "canonical_next_stage": recommendation.get("next_main_step"),
            "terminal": recommendation.get("mode") == "TERMINAL",
            "policy": "navigation_state is used for next-step recommendations; checkpoint restore_state is not the sole source after image-only stages.",
        }
        result = {
            "stage": step,
            "scan": report,
            "navigation_state": navigation_state,
            "recommendation": recommendation,
            "resolved_at": utc_now(),
        }
    else:
        next_step = DEFAULT_NEXT_STEP_BY_STEP.get(step)
        result = {
            "stage": step,
            "navigation_state": {
                "resolved_current_stage": step,
                "resolved_from": ["explicit step argument or current_step"],
                "image_only_stage_completed_for_navigation": False,
                "checkpoint_may_lag": False,
                "canonical_next_stage": next_step,
                "terminal": step == "S5-CANDIDATE-IMAGE",
                "policy": "next-step prompts are generated from active stage transitions after resolving navigation_state.",
            },
            "recommendation": {
                "action": "run_public_step_or_follow_default_next",
                "next_main_step": next_step,
            },
            "resolved_at": utc_now(),
        }
    state["next_action_recommendation"] = result
    state["updated_at"] = utc_now()
    return result


def cmd_mark_substage(args: argparse.Namespace, run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    if args.status not in SUBSTAGE_STATUS_VALUES:
        raise StateError(f"substage status must be one of {sorted(SUBSTAGE_STATUS_VALUES)}")
    runs = state.setdefault("substage_runs", {}).setdefault(args.step, {})
    row = runs.setdefault(args.substage_id, {"stage": args.step, "substage_id": args.substage_id})
    row["status"] = args.status
    row["updated_at"] = utc_now()
    if args.note:
        row.setdefault("notes", []).append({"created_at": utc_now(), "note": args.note})
    state["updated_at"] = utc_now()
    return row


def cmd_mark_candidate(args: argparse.Namespace, run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    if args.status not in CANDIDATE_STATUS_VALUES:
        raise StateError(f"candidate status must be one of {sorted(CANDIDATE_STATUS_VALUES)}")
    cid = normalize_candidate_id(args.candidate_id)
    registry = state.setdefault("candidate_run_registry", {}).setdefault(candidate_registry_key(args.step), {})
    row = registry.setdefault(cid, {"step": args.step, "candidate_id": cid})
    paths = candidate_paths(args.step, cid)
    row.update(
        {
            "step": args.step,
            "candidate_id": cid,
            "status": args.status,
            "active_image_path": args.image_path or row.get("active_image_path") or paths["active_image_path"],
            "active_audit_json": args.audit_json or row.get("active_audit_json") or paths["active_audit_json"],
            "status_path": paths["status_path"],
            "risk_note": args.risk_note or row.get("risk_note", ""),
            "updated_at": utc_now(),
        }
    )
    write_candidate_status_files(run_dir, args.step, state)
    state["updated_at"] = utc_now()
    return row


def cmd_reset_candidate(args: argparse.Namespace, run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    cid = normalize_candidate_id(args.candidate_id)
    paths = candidate_paths(args.step, cid)
    candidate_dir = safe_join(run_dir, paths["candidate_dir"])
    timestamp = utc_now().replace(":", "").replace("-", "")
    archive_rel = f"{STEP_OUTPUT_DIRS[args.step]}/candidate-rerun-history/{cid}-{timestamp}"
    archive_dir = safe_join(run_dir, archive_rel)
    moved = False
    if candidate_dir.exists():
        archive_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(candidate_dir), str(archive_dir))
        moved = True
    candidate_dir.mkdir(parents=True, exist_ok=True)
    safe_join(run_dir, paths["audit_history_dir"]).mkdir(parents=True, exist_ok=True)
    safe_join(run_dir, paths["revision_history_dir"]).mkdir(parents=True, exist_ok=True)
    registry = state.setdefault("candidate_run_registry", {}).setdefault(candidate_registry_key(args.step), {})
    row = registry.setdefault(cid, {"step": args.step, "candidate_id": cid})
    row.update(
        {
            "status": "PENDING",
            "attempt": int(row.get("attempt") or 1) + 1,
            "revision_attempts_used": 0,
            "candidate_dir": paths["candidate_dir"],
            "active_image_path": paths["active_image_path"],
            "active_audit_json": paths["active_audit_json"],
            "reset_reason": args.reason or "",
            "previous_candidate_dir": archive_rel if moved else None,
            "updated_at": utc_now(),
        }
    )
    state.setdefault("downstream_staleness", []).append(
        {
            "created_at": utc_now(),
            "step": args.step,
            "candidate_id": cid,
            "reason": "single_candidate_rerun",
            "downstream_policy": "Other same-stage candidates remain valid. If S3 already consumed this candidate, downstream outputs must be reconfirmed or explicitly rerun before use.",
        }
    )
    write_candidate_status_files(run_dir, args.step, state)
    state["updated_at"] = utc_now()
    return row


def checkpoint_redo_status_payload(reason: str) -> dict[str, Any]:
    """Return paper-neutral redo diagnostics for failed checkpoint repair.

    v3.2.15f does not use incomplete restore checkpoints as a terminal
    workflow state. A failed cumulative checkpoint build triggers redo of the
    earliest affected stage or registration/prompt-preparation step.
    """
    return {
        "checkpoint_status": "redo_required",
        "restore_status": "not_restore_ready_redo_required",
        "redo_required": True,
        "redo_reason": reason,
        "user_facing_checkpoint_link_allowed": False,
    }


def checkpoint_manifest(
    state: dict[str, Any],
    stage: str,
    checkpoint_type: str,
    sequence: int,
    included_roots: list[str],
    required_existing_asset_paths: list[str],
    required_image_paths: list[str],
    pending_future_image_paths: list[str],
    missing_image_entries: list[dict[str, Any]] | None = None,
    missing_asset_entries: list[dict[str, Any]] | None = None,
    checkpoint_parts: list[str] | None = None,
) -> dict[str, Any]:
    missing_image_entries = missing_image_entries or []
    missing_asset_entries = missing_asset_entries or []
    restore_complete = not missing_image_entries and not missing_asset_entries
    manifest = {
        "schema_version": 2,
        "skill_name": state.get("skill_name"),
        "skill_version": state.get("skill_version"),
        "project_id": state.get("project_id"),
        "stage": stage,
        "checkpoint_type": checkpoint_type,
        "sequence": sequence,
        "created_at": utc_now(),
        "state_file": state.get("state_file"),
        "included_roots": included_roots,
        "stage_coverage": checkpoint_stage_coverage(included_roots),
        "cumulative_required": True,
        "substage_checkpoint_page_integrity_required": True,
        "checkpoint_scope": "cumulative_from_workflow_start_to_current_stage_or_substage",
        "non_delta_checkpoint_guard": "Do not accept or advertise current-stage-only or current-substage-only checkpoint zips as cumulative restore bundles.",
        "required_existing_asset_paths": required_existing_asset_paths,
        "required_existing_asset_count": len(required_existing_asset_paths),
        "required_image_paths": required_image_paths,
        "required_existing_image_paths": required_image_paths,
        "required_existing_image_count": len(required_image_paths),
        "pending_future_image_paths": pending_future_image_paths,
        "pending_future_image_count": len(pending_future_image_paths),
        "pending_future_policy": "Planned images that have not yet been generated are recorded for next-action guidance only; they are not restore blockers and must not be listed as missing required images.",
        "restore_policy": "Upload/extract this cumulative checkpoint, restore project-run-relative paths exactly, load the state file, then run resume/scan-substages for the requested stage. If checkpoint_parts is present, all listed parts are required for restore.",
        "required_asset_policy": "Every already-existing file inside the cumulative included roots and every generated/registered raster asset that should exist is required for restore. Prior checkpoint zip files are intentionally not recursively included.",
    }
    manifest["checkpoint_integrity"] = checkpoint_integrity_summary(
        stage=stage,
        checkpoint_type=checkpoint_type,
        included_roots=included_roots,
        required_existing_asset_paths=required_existing_asset_paths,
        required_image_paths=required_image_paths,
        pending_future_image_paths=pending_future_image_paths,
        missing_image_entries=missing_image_entries,
        missing_asset_entries=missing_asset_entries,
        validation_attempts=0,
    )
    if checkpoint_parts:
        manifest["checkpoint_parts"] = checkpoint_parts
        manifest["all_parts_required_for_restore"] = True
    if restore_complete:
        manifest["checkpoint_status"] = "complete_restore_ready"
        manifest["restore_status"] = "complete_restore_ready"
        manifest["image_checkpoint_completeness"] = "complete_all_required_images_present"
        manifest["asset_checkpoint_completeness"] = "complete_all_required_assets_present"
    else:
        manifest["checkpoint_status"] = "redo_required"
        manifest["restore_status"] = "not_restore_ready_redo_required"
        manifest["redo_required"] = True
        manifest["redo_reason"] = "missing_required_checkpoint_assets_after_rebuild_attempts"
        if missing_image_entries:
            manifest["image_checkpoint_completeness"] = "incomplete_missing_required_images"
            manifest["missing_image_manifest"] = "checkpoint-missing-images.json"
            manifest["missing_image_count"] = len(missing_image_entries)
            manifest[
                "missing_image_restore_instruction"
            ] = "Restore each already-generated/required image at the exact listed project-run-relative zip path. Future planned images are listed separately as pending_future_image_paths and are not restore blockers."
        else:
            manifest["image_checkpoint_completeness"] = "complete_all_required_images_present"
        if missing_asset_entries:
            manifest["asset_checkpoint_completeness"] = "incomplete_missing_required_assets"
            manifest["missing_asset_manifest"] = "checkpoint-missing-assets.json"
            manifest["missing_asset_count"] = len(missing_asset_entries)
        else:
            manifest["asset_checkpoint_completeness"] = "complete_all_required_assets_present"
    return manifest

def image_path_candidate(rel_path: Any) -> str | None:
    if not isinstance(rel_path, str) or not rel_path:
        return None
    normalized = normalize_relative_path(rel_path)
    if Path(normalized).suffix.lower() not in TARGET_RASTER_IMAGE_EXTS:
        return None
    return normalized


def candidate_lineage_image_paths(row: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("original_image_path", "active_image_path", "latest_failed_image_path"):
        rel = image_path_candidate(row.get(key))
        if rel:
            paths.append(rel)
    for rel_value in row.get(S5_REFERENCE_IMAGE_ROW_FIELD, []) or []:
        rel = image_path_candidate(rel_value)
        if rel:
            paths.append(rel)
    for attempt in row.get("revision_attempts", []):
        if not isinstance(attempt, dict):
            continue
        for key in ("input_original_image_path", "input_failed_image_path", "output_image_path"):
            rel = image_path_candidate(attempt.get(key))
            if rel:
                paths.append(rel)
    return sorted(set(paths))


def prompt_index_reference_image_paths(run_dir: Path, included_roots: list[str]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    outputs = safe_join(run_dir, "outputs")
    if not outputs.exists():
        return refs
    for path in outputs.rglob("prompt-index.json"):
        try:
            rel_index = normalize_relative_path(path.relative_to(run_dir))
        except StateError:
            continue
        if not should_include_path(rel_index, included_roots):
            continue
        data = read_json_if_exists(path) or {}
        if data.get("stage") != "S5-CANDIDATE-IMAGE":
            continue
        for row in data.get("candidates", []) or []:
            if not isinstance(row, dict):
                continue
            cid = row.get("candidate_id") or "unknown"
            for rel_value in row.get(S5_REFERENCE_IMAGE_ROW_FIELD, []) or []:
                rel = image_path_candidate(rel_value)
                if rel:
                    refs.append((rel, f"prompt_index_s5_reference:{rel_index}:{cid}"))
    return refs


def checkpoint_included_roots(stage: str) -> list[str]:
    included_roots = ["state", "inputs"]
    for step, _, _, output_dir in WORKFLOW_STEPS:
        included_roots.append(output_dir)
        if step == stage:
            return included_roots
    raise StateError(f"unknown checkpoint stage: {stage}")


def checkpoint_stage_coverage(included_roots: list[str]) -> list[dict[str, str]]:
    """Return workflow stages covered by cumulative roots.

    This derives coverage from the canonical workflow/output roots rather than
    from project-specific file names, candidate ids, or image counts.
    """
    coverage: list[dict[str, str]] = []
    root_set = set(included_roots)
    for step, mode, _, output_dir in WORKFLOW_STEPS:
        if output_dir in root_set:
            coverage.append({"step": step, "mode": mode, "output_dir": output_dir})
    return coverage


def checkpoint_integrity_summary(
    stage: str,
    checkpoint_type: str,
    included_roots: list[str],
    required_existing_asset_paths: list[str],
    required_image_paths: list[str],
    pending_future_image_paths: list[str],
    missing_image_entries: list[dict[str, Any]],
    missing_asset_entries: list[dict[str, Any]],
    validation_attempts: int = 0,
) -> dict[str, Any]:
    complete = not missing_image_entries and not missing_asset_entries
    return {
        "schema_version": 1,
        "cumulative_required": True,
        "checkpoint_scope": "cumulative_from_workflow_start_to_current_stage_or_substage",
        "current_stage": stage,
        "checkpoint_type": checkpoint_type,
        "included_roots": included_roots,
        "stage_coverage": checkpoint_stage_coverage(included_roots),
        "required_existing_asset_count": len(required_existing_asset_paths),
        "required_existing_image_count": len(required_image_paths),
        "pending_future_image_count": len(pending_future_image_paths),
        "post_write_validation_status": "passed" if complete else "failed",
        "rebuild_attempt_count": validation_attempts,
        "checkpoint_status": "complete_restore_ready" if complete else "redo_required",
        "non_delta_checkpoint_guard": "current_stage_or_substage_only_zips_are_invalid_when_earlier_workflow_assets_exist",
        "hardcoding_forbidden": "Do not hard-code project ids, paper names, candidate ids, image counts, filenames, or task-specific stage assumptions.",
    }


def required_candidate_ids_for_checkpoint(
    step: str, manifest: dict[str, Any] | None, state: dict[str, Any]
) -> list[str]:
    """Return only explicitly planned/registered candidate ids.

    Checkpoints must never invent required image paths from hard-coded candidate
    counts. A dynamic stage can have any number of registered candidates, and a
    upstream text-stage checkpoint before IMAGE_GENERATE must be restore-complete even
    though future image paths are known but not yet produced.
    """
    candidate_ids: list[str] = []
    if isinstance(manifest, dict):
        candidate_ids = [cid for cid in manifest.get("candidate_ids", []) if isinstance(cid, str)]
    registry = state.get("candidate_run_registry", {}).get(candidate_registry_key(step), {})
    if isinstance(registry, dict):
        for cid in sorted(cid for cid in registry if isinstance(cid, str)):
            if cid not in candidate_ids:
                candidate_ids.append(cid)
    return candidate_ids


def image_path_exists(run_dir: Path, rel: str) -> bool:
    try:
        return safe_join(run_dir, rel).is_file()
    except StateError:
        return False


def substage_image_output_should_exist(state: dict[str, Any], step: str, cid: str) -> bool:
    """Return true if a completed image unit indicates this candidate image should exist."""
    runs = state.get("substage_runs", {}).get(step, {})
    if not isinstance(runs, dict):
        return False
    for row in runs.values():
        if not isinstance(row, dict):
            continue
        if row.get("mode") not in {"IMAGE_GENERATE"}:
            continue
        if cid not in (row.get("candidate_ids") or []):
            continue
        if row.get("status") == "complete":
            return True
    return False


def candidate_row_image_should_exist(row: dict[str, Any] | None, state: dict[str, Any], step: str, cid: str) -> bool:
    if not isinstance(row, dict):
        return substage_image_output_should_exist(state, step, cid)
    status = row.get("status")
    if status in IMAGE_REQUIRED_CANDIDATE_STATUS_VALUES:
        return True
    explicit_flags = (
        "image_generated",
        "generated",
        "generation_succeeded",
        "image_generation_complete",
    )
    if any(bool(row.get(flag)) for flag in explicit_flags):
        return True
    if row.get("generated_at") or row.get("image_generation_event_id"):
        return True
    if substage_image_output_should_exist(state, step, cid):
        return True
    return False


def add_required_pending_or_missing(
    *,
    run_dir: Path,
    rel: str | None,
    included_roots: list[str],
    should_exist: bool,
    source: str,
    required: set[str],
    pending: set[str],
    missing: dict[str, dict[str, Any]],
) -> None:
    rel = image_path_candidate(rel)
    if not rel or not should_include_path(rel, included_roots):
        return
    if image_path_exists(run_dir, rel):
        required.add(rel)
        return
    if should_exist:
        missing.setdefault(
            rel,
            {
                "relative_path": rel,
                "zip_path": rel,
                "status": "missing_required_existing_or_generated_asset_before_checkpoint_zip",
                "source": source,
                "required_for_complete_restore": True,
                "user_action": "Restore this already-generated/required raster asset at the exact project-run-relative zip path before cross-session resume.",
            },
        )
    else:
        pending.add(rel)


def iter_state_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(iter_state_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(iter_state_strings(child))
    return found


def checkpoint_image_inventory(run_dir: Path, state: dict[str, Any], included_roots: list[str]) -> dict[str, Any]:
    """Classify image paths without hard-coding counts or stage-specific filenames."""
    required: set[str] = set()
    pending: set[str] = set()
    missing: dict[str, dict[str, Any]] = {}
    registries = state.get("candidate_run_registry", {})

    # Any raster file already present in the cumulative scope is restore-required,
    # even if a prior stage failed to register it explicitly.
    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = normalize_relative_path(path.relative_to(run_dir))
        except StateError:
            continue
        if image_path_candidate(rel) and should_include_path(rel, included_roots):
            required.add(rel)

    # Dynamic candidate registries and manifests provide planned paths plus
    # status. Missing planned PENDING images are pending_future, not blockers.
    for step in SUBSTAGE_STEPS:
        output_dir = STEP_OUTPUT_DIRS[step]
        if not should_include_path(output_dir, included_roots):
            continue
        manifest_path = safe_join(run_dir, f"{output_dir}/stage-manifest.json")
        manifest = read_json_if_exists(manifest_path) or {}
        candidate_ids = required_candidate_ids_for_checkpoint(step, manifest, state)
        registry = registries.get(candidate_registry_key(step), {}) if isinstance(registries, dict) else {}
        for cid in candidate_ids:
            row = registry.get(cid) if isinstance(registry, dict) else None
            should_exist = candidate_row_image_should_exist(row, state, step, cid)
            rel = image_path_candidate(row.get("active_image_path")) if isinstance(row, dict) else None
            rel = rel or manifest_candidate_image_path(manifest, cid)
            if not rel:
                # Record default active path as future only when the stage has
                # explicitly planned this candidate; never make it a missing
                # image merely because a default count exists.
                rel = candidate_paths(step, cid)["active_image_path"]
            add_required_pending_or_missing(
                run_dir=run_dir,
                rel=rel,
                included_roots=included_roots,
                should_exist=should_exist,
                source=f"candidate_registry_or_manifest:{step}:{cid}",
                required=required,
                pending=pending,
                missing=missing,
            )
            if isinstance(row, dict):
                active_rel = image_path_candidate(row.get("active_image_path")) or rel
                for lineage_rel in candidate_lineage_image_paths(row):
                    # active_image_path is already classified above; when it is
                    # merely a planned future image, do not promote it to a
                    # missing restore blocker through the generic lineage scan.
                    lineage_should_exist = should_exist if lineage_rel == active_rel else True
                    add_required_pending_or_missing(
                        run_dir=run_dir,
                        rel=lineage_rel,
                        included_roots=included_roots,
                        should_exist=lineage_should_exist,
                        source=f"candidate_lineage:{step}:{cid}",
                        required=required,
                        pending=pending,
                        missing=missing,
                    )

    # Image generation events are authoritative generated-output records.
    for event in state.get("image_generation_events", []):
        if not isinstance(event, dict):
            continue
        event_should_exist = event.get("status") in {"generation_succeeded", "complete", "succeeded"}
        for rel_path in event.get("generated_paths", []):
            add_required_pending_or_missing(
                run_dir=run_dir,
                rel=rel_path,
                included_roots=included_roots,
                should_exist=event_should_exist,
                source=f"image_generation_event:{event.get('event_id') or event.get('batch_id') or 'unknown'}",
                required=required,
                pending=pending,
                missing=missing,
            )
        for rel_path in event.get("reference_image_paths", []) or []:
            add_required_pending_or_missing(
                run_dir=run_dir,
                rel=rel_path,
                included_roots=included_roots,
                should_exist=True,
                source=f"image_generation_event_reference:{event.get('event_id') or event.get('batch_id') or 'unknown'}",
                required=required,
                pending=pending,
                missing=missing,
            )

    # S5 prompt-index reference images are existing inputs to the formal image
    # generation stage, not future S5 outputs.
    for rel_path, source in prompt_index_reference_image_paths(run_dir, included_roots):
        add_required_pending_or_missing(
            run_dir=run_dir,
            rel=rel_path,
            included_roots=included_roots,
            should_exist=True,
            source=source,
            required=required,
            pending=pending,
            missing=missing,
        )

    # Artifact records with image kind/extension are required when active or
    # already present; pending artifact rows remain pending if not on disk.
    for artifact in state.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        rel = image_path_candidate(artifact.get("relative_path"))
        if not rel and artifact.get("kind") != "image":
            continue
        status = artifact.get("status")
        should_exist = status not in {"pending", "planned", "PENDING", "MISSING", None, ""}
        add_required_pending_or_missing(
            run_dir=run_dir,
            rel=rel or artifact.get("relative_path"),
            included_roots=included_roots,
            should_exist=should_exist,
            source=f"artifact:{artifact.get('artifact_id') or 'unknown'}",
            required=required,
            pending=pending,
            missing=missing,
        )

    # Generic recovery guard: any raster path string already materialized on
    # disk is required. Nonexistent generic strings are left alone unless a
    # registry/event above declared that they should exist.
    for value in iter_state_strings(state):
        rel = image_path_candidate(value)
        if rel and should_include_path(rel, included_roots) and image_path_exists(run_dir, rel):
            required.add(rel)

    return {
        "required_image_paths": sorted(required),
        "pending_future_image_paths": sorted(p for p in pending if p not in required and p not in missing),
        "missing_image_entries": [missing[key] for key in sorted(missing)],
    }


def expected_checkpoint_image_paths(run_dir: Path, state: dict[str, Any], included_roots: list[str]) -> list[str]:
    return checkpoint_image_inventory(run_dir, state, included_roots)["required_image_paths"]


def checkpoint_missing_image_entries(
    run_dir: Path, state: dict[str, Any], included_roots: list[str]
) -> list[dict[str, Any]]:
    return checkpoint_image_inventory(run_dir, state, included_roots)["missing_image_entries"]

def should_include_path(rel: str, included_roots: list[str]) -> bool:
    normalized = normalize_relative_path(rel)
    if "/__pycache__/" in f"/{normalized}/":
        return False
    if normalized.endswith(".pyc"):
        return False
    if normalized.startswith("checkpoints/"):
        return False
    return any(normalized == root or normalized.startswith(f"{root}/") for root in included_roots)


def checkpoint_required_existing_asset_paths(
    run_dir: Path,
    checkpoint_dir_rel: str,
    included_roots: list[str],
    excluded_zip_rels: set[str] | None = None,
) -> list[str]:
    excluded_zip_rels = excluded_zip_rels or set()
    assets: set[str] = set()
    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = normalize_relative_path(path.relative_to(run_dir))
        except StateError:
            continue
        if rel in excluded_zip_rels or rel.startswith(f"{checkpoint_dir_rel}/"):
            continue
        if should_include_path(rel, included_roots):
            assets.add(rel)
    return sorted(assets)


def checkpoint_missing_asset_entries_from_zip(
    zip_paths: list[Path], required_existing_asset_paths: list[str]
) -> list[dict[str, Any]]:
    members: set[str] = set()
    for zip_path in zip_paths:
        if not zip_path.is_file():
            continue
        with zipfile.ZipFile(zip_path, "r") as archive:
            members.update(archive.namelist())
    missing: list[dict[str, Any]] = []
    for rel in required_existing_asset_paths:
        if rel not in members:
            missing.append(
                {
                    "relative_path": rel,
                    "zip_path": rel,
                    "status": "missing_from_checkpoint_zip_after_write",
                    "required_for_complete_restore": True,
                    "user_action": "Rebuild the checkpoint; this existing cumulative asset was not packed into the zip.",
                }
            )
    return missing



def checkpoint_existing_roots_with_files(run_dir: Path, included_roots: list[str]) -> list[str]:
    roots: list[str] = []
    for root in included_roots:
        root_path = safe_join(run_dir, root)
        if root_path.is_file():
            roots.append(root)
            continue
        if not root_path.is_dir():
            continue
        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = normalize_relative_path(path.relative_to(run_dir))
            except StateError:
                continue
            if should_include_path(rel, included_roots):
                roots.append(root)
                break
    return roots


def checkpoint_member_union(zip_paths: list[Path]) -> set[str]:
    members: set[str] = set()
    for zip_path in zip_paths:
        if not zip_path.is_file():
            continue
        with zipfile.ZipFile(zip_path, "r") as archive:
            members.update(archive.namelist())
    return members


def checkpoint_manifest_from_zip(zip_paths: list[Path]) -> dict[str, Any]:
    for zip_path in zip_paths:
        if not zip_path.is_file():
            continue
        with zipfile.ZipFile(zip_path, "r") as archive:
            if "checkpoint-manifest.json" in archive.namelist():
                return json.loads(archive.read("checkpoint-manifest.json").decode("utf-8"))
    return {}


def checkpoint_cumulative_integrity_report(
    run_dir: Path,
    stage: str,
    zip_paths: list[Path],
    included_roots: list[str],
    required_existing_asset_paths: list[str],
) -> dict[str, Any]:
    """Paper-agnostic guard against current-stage-only checkpoint bundles.

    This guard derives expected roots from the workflow stage and on-disk project
    run. It intentionally never uses paper-specific entities, candidate ids,
    image counts, or fixed filenames beyond the generic checkpoint manifest.
    """
    members = checkpoint_member_union(zip_paths)
    manifest = checkpoint_manifest_from_zip(zip_paths)
    roots_with_files = checkpoint_existing_roots_with_files(run_dir, included_roots)
    roots_without_members = [
        root for root in roots_with_files if not any(member == root or member.startswith(f"{root}/") for member in members)
    ]
    missing_asset_entries = checkpoint_missing_asset_entries_from_zip(zip_paths, required_existing_asset_paths)
    manifest_roots = [normalize_relative_path(root) for root in manifest.get("included_roots", []) if isinstance(root, str)] if isinstance(manifest, dict) else []
    manifest_missing_expected_roots = [root for root in included_roots if root not in manifest_roots]
    scope = str(manifest.get("checkpoint_scope", "")) if isinstance(manifest, dict) else ""
    scope_ok = bool(scope) and "cumulative" in scope.lower()
    manifest_present = bool(manifest)
    failures: list[dict[str, Any]] = []
    for entry in missing_asset_entries:
        failures.append({"category": "missing_existing_asset", **entry})
    for root in roots_without_members:
        failures.append({"category": "existing_root_without_archive_members", "root": root})
    for root in manifest_missing_expected_roots:
        failures.append({"category": "manifest_missing_expected_root", "root": root})
    if not manifest_present:
        failures.append({"category": "missing_checkpoint_manifest", "member": "checkpoint-manifest.json"})
    elif not scope_ok:
        failures.append({"category": "manifest_scope_not_cumulative", "checkpoint_scope": scope})
    return {
        "schema_version": 1,
        "guard": "cumulative_checkpoint_integrity_guard",
        "stage": stage,
        "created_at": utc_now(),
        "status": "PASS" if not failures else "FAIL",
        "zip_paths": [normalize_relative_path(path) if not path.is_absolute() else str(path) for path in zip_paths],
        "included_roots": included_roots,
        "existing_roots_with_files": roots_with_files,
        "roots_without_archive_members": roots_without_members,
        "archive_member_count": len(members),
        "required_existing_asset_count": len(required_existing_asset_paths),
        "missing_existing_asset_count": len(missing_asset_entries),
        "manifest_present": manifest_present,
        "manifest_scope": scope,
        "manifest_scope_is_cumulative": scope_ok,
        "manifest_included_roots": manifest_roots,
        "manifest_missing_expected_roots": manifest_missing_expected_roots,
        "failures": failures,
        "non_hardcoding_statement": "Derived from workflow state/step order and on-disk roots; never from paper-specific names, candidate ids, image counts, or fixed task files.",
        "rerun_instruction": "If status is FAIL, rebuild the checkpoint using the cumulative checkpoint builder and rerun the guard before claiming complete_restore_ready.",
    }



def checkpoint_zip_member_names(zip_paths: list[Path]) -> set[str]:
    """Return the union of zip members across a single checkpoint or split parts."""
    members: set[str] = set()
    for zip_path in zip_paths:
        if not zip_path.is_file():
            continue
        with zipfile.ZipFile(zip_path, "r") as archive:
            members.update(archive.namelist())
    return members


def checkpoint_expected_root_counts(run_dir: Path, included_roots: list[str]) -> dict[str, int]:
    """Count existing files per included root without encoding any stage-specific filenames."""
    counts: dict[str, int] = {}
    for root in included_roots:
        count = 0
        root_path = safe_join(run_dir, root)
        if root_path.exists():
            if root_path.is_file():
                count = 1
            else:
                for path in root_path.rglob("*"):
                    if path.is_file():
                        try:
                            rel = normalize_relative_path(path.relative_to(run_dir))
                        except StateError:
                            continue
                        if should_include_path(rel, included_roots):
                            count += 1
        counts[root] = count
    return counts


def checkpoint_root_coverage_audit(
    run_dir: Path,
    stage: str,
    included_roots: list[str],
    zip_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Verify that the checkpoint scope is cumulative through the requested stage."""
    expected_roots = checkpoint_included_roots(stage)
    root_counts = checkpoint_expected_root_counts(run_dir, expected_roots)
    members = checkpoint_zip_member_names(zip_paths or []) if zip_paths else set()
    member_counts: dict[str, int] = {}
    if members:
        for root in expected_roots:
            member_counts[root] = sum(1 for member in members if member == root or member.startswith(f"{root}/"))
    missing_in_scope = [root for root in expected_roots if root not in included_roots]
    existing_root_payload_missing_from_zip = []
    if members:
        existing_root_payload_missing_from_zip = [
            root for root in expected_roots if root_counts.get(root, 0) > 0 and member_counts.get(root, 0) == 0
        ]
    status = "complete_cumulative_scope"
    if missing_in_scope or existing_root_payload_missing_from_zip:
        status = "incomplete_cumulative_scope"
    return {
        "stage": stage,
        "expected_included_roots_through_stage": expected_roots,
        "actual_included_roots": included_roots,
        "existing_file_count_by_expected_root": root_counts,
        "zip_member_count_by_expected_root": member_counts,
        "missing_expected_roots_from_manifest_scope": missing_in_scope,
        "existing_expected_roots_with_no_zip_payload": existing_root_payload_missing_from_zip,
        "status": status,
        "policy": "generic cumulative checkpoint scope audit; no project, candidate, or filename hard-coding",
    }


def checkpoint_substage_token_fragments(substage_id: str | None) -> set[str]:
    """Derive loose filename/path fragments from a substage id generically."""
    if not substage_id:
        return set()
    normalized = substage_id.lower().replace("_", "-")
    parts = [p for p in normalized.split("-") if p]
    fragments = {normalized}
    if len(parts) >= 2:
        fragments.add("-".join(parts[:2]))
    if len(parts) >= 3:
        fragments.add("-".join(parts[:3]))
    return fragments


def checkpoint_collect_existing_relpaths_from_value(
    run_dir: Path,
    value: Any,
    included_roots: list[str],
) -> set[str]:
    """Collect existing run-relative file paths from arbitrary state/guidance rows."""
    found: set[str] = set()
    if isinstance(value, str):
        try:
            rel = normalize_relative_path(value)
        except StateError:
            return found
        if should_include_path(rel, included_roots) and safe_join(run_dir, rel).is_file():
            found.add(rel)
    elif isinstance(value, dict):
        for child in value.values():
            found.update(checkpoint_collect_existing_relpaths_from_value(run_dir, child, included_roots))
    elif isinstance(value, list):
        for child in value:
            found.update(checkpoint_collect_existing_relpaths_from_value(run_dir, child, included_roots))
    return found


def checkpoint_required_substage_page_asset_paths(
    run_dir: Path,
    state: dict[str, Any],
    stage: str,
    substage_id: str | None,
    included_roots: list[str],
) -> list[str]:
    """Return substage-local text/manifest/guidance/prompt pages that must be in a substage checkpoint.

    This intentionally discovers pages from state, guidance rows, manifests, and path fragments.
    It never encodes project names, paper terms, candidate IDs, or stage-specific output filenames.
    """
    output_root = STEP_OUTPUT_DIRS.get(stage)
    if not output_root:
        return []
    assets: set[str] = set()
    fragments = checkpoint_substage_token_fragments(substage_id)

    # 1) Include state/guidance references for this exact substage when present.
    run_rows = state.get("substage_runs", {}).get(stage, {})
    if isinstance(run_rows, dict) and substage_id and isinstance(run_rows.get(substage_id), dict):
        assets.update(checkpoint_collect_existing_relpaths_from_value(run_dir, run_rows[substage_id], included_roots))
    guide_rows = state.get("substage_guidance_registry", {}).get(stage, {})
    if isinstance(guide_rows, dict) and substage_id and isinstance(guide_rows.get(substage_id), dict):
        assets.update(checkpoint_collect_existing_relpaths_from_value(run_dir, guide_rows[substage_id], included_roots))

    # 2) Include the stage manifest and prompt index / registries because they are substage navigation pages.
    for rel in (
        f"{output_root}/stage-manifest.json",
        f"{output_root}/prompt-index.json",
        f"{output_root}/rerun-prompt-index.json",
        f"{output_root}/final-prompt-index.json",
    ):
        try:
            if should_include_path(rel, included_roots) and safe_join(run_dir, rel).is_file():
                assets.add(rel)
        except StateError:
            pass

    # 3) Include current substage pages by generic fragment match inside the current stage output root.
    root_path = safe_join(run_dir, output_root)
    if root_path.exists():
        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = normalize_relative_path(path.relative_to(run_dir))
            except StateError:
                continue
            lower_rel = rel.lower().replace("_", "-")
            if fragments and any(fragment in lower_rel for fragment in fragments) and should_include_path(rel, included_roots):
                assets.add(rel)
    return sorted(assets)


def checkpoint_integrity_report(
    *,
    run_dir: Path,
    stage: str,
    checkpoint_type: str,
    sequence: int,
    substage_id: str | None,
    included_roots: list[str],
    output_zip_paths: list[Path],
    required_existing_asset_paths: list[str],
    required_substage_page_asset_paths: list[str],
    missing_image_entries: list[dict[str, Any]],
    missing_asset_entries: list[dict[str, Any]],
    attempt_count: int,
) -> dict[str, Any]:
    members = checkpoint_zip_member_names(output_zip_paths)
    root_audit = checkpoint_root_coverage_audit(run_dir, stage, included_roots, output_zip_paths)
    missing_substage_pages = [rel for rel in required_substage_page_asset_paths if rel not in members]
    complete = (
        root_audit["status"] == "complete_cumulative_scope"
        and not missing_image_entries
        and not missing_asset_entries
        and not missing_substage_pages
    )
    return {
        "schema_version": 1,
        "stage": stage,
        "substage_id": substage_id,
        "checkpoint_type": checkpoint_type,
        "sequence": sequence,
        "created_at": utc_now(),
        "checkpoint_scope": "cumulative_from_S0_to_current_stage_or_substage",
        "no_hardcoded_candidate_or_filename_counts": True,
        "root_coverage_audit": root_audit,
        "required_existing_asset_count": len(required_existing_asset_paths),
        "required_substage_page_asset_paths": required_substage_page_asset_paths,
        "missing_substage_page_asset_paths": missing_substage_pages,
        "missing_substage_page_asset_count": len(missing_substage_pages),
        "missing_image_count": len(missing_image_entries),
        "missing_asset_count": len(missing_asset_entries),
        "attempt_count": attempt_count,
        "checkpoint_integrity_status": "complete_restore_ready" if complete else "redo_required",
        "policy": "A checkpoint cannot be reported as complete unless cumulative root coverage, required existing assets, generated images, and substage pages all pass post-write zip-member validation.",
    }



def checkpoint_enrich_manifest_with_substage_integrity(
    manifest: dict[str, Any],
    *,
    stage: str,
    substage_id: str | None,
    required_substage_page_asset_paths: list[str],
    included_roots: list[str],
    run_dir: Path,
) -> dict[str, Any]:
    """Attach generic cumulative/substage-page guard metadata to a manifest."""
    manifest["cumulative_required"] = True
    manifest["current_substage_id"] = substage_id
    manifest["required_substage_page_asset_paths"] = required_substage_page_asset_paths
    manifest["required_substage_page_asset_count"] = len(required_substage_page_asset_paths)
    manifest["substage_page_policy"] = (
        "When a checkpoint is emitted from an internal substage, existing substage text pages, "
        "manifests, prompt indexes, guidance, and audit pages are required restore assets. "
        "Discovery is derived from state/guidance/path fragments and never from project-specific filenames."
    )
    manifest["root_coverage_prewrite_audit"] = checkpoint_root_coverage_audit(run_dir, stage, included_roots, None)
    manifest["non_hardcoding_checkpoint_policy"] = (
        "Checkpoint completeness is derived from workflow roots, state, manifests, registries, and existing files; "
        "do not hard-code project ids, paper names, candidate ids, image counts, or task-specific output filenames."
    )
    return manifest

def checkpoint_archive_entries(
    run_dir: Path,
    checkpoint_dir_rel: str,
    included_roots: list[str],
    manifest_path: Path,
    missing_manifest_path: Path,
    missing_image_entries: list[dict[str, Any]],
    excluded_zip_rels: set[str],
    missing_asset_manifest_path: Path | None = None,
    missing_asset_entries: list[dict[str, Any]] | None = None,
    integrity_manifest_path: Path | None = None,
) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = [(manifest_path, "checkpoint-manifest.json")]
    if missing_image_entries:
        entries.append((missing_manifest_path, "checkpoint-missing-images.json"))
    if missing_asset_entries and missing_asset_manifest_path is not None:
        entries.append((missing_asset_manifest_path, "checkpoint-missing-assets.json"))
    if integrity_manifest_path is not None and integrity_manifest_path.is_file():
        entries.append((integrity_manifest_path, "checkpoint-cumulative-integrity.json"))
    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = normalize_relative_path(path.relative_to(run_dir))
        except StateError:
            continue
        if rel in excluded_zip_rels or rel.startswith(f"{checkpoint_dir_rel}/"):
            continue
        if should_include_path(rel, included_roots):
            entries.append((path, rel))
    return entries


def write_checkpoint_zip(zip_path: Path, entries: list[tuple[Path, str]]) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        seen: set[str] = set()
        for source, arcname in entries:
            if arcname in seen:
                continue
            seen.add(arcname)
            archive.write(source, arcname)


def split_payload_entries(
    entries: list[tuple[Path, str]],
    max_zip_bytes: int,
) -> list[list[tuple[Path, str]]]:
    metadata_names = {"checkpoint-manifest.json", "checkpoint-missing-images.json", "checkpoint-missing-assets.json", "checkpoint-cumulative-integrity.json"}
    payload_entries = [(source, arcname) for source, arcname in entries if arcname not in metadata_names]
    metadata_size = sum(
        source.stat().st_size for source, arcname in entries if arcname in metadata_names and source.exists()
    )
    groups: list[list[tuple[Path, str]]] = []
    current: list[tuple[Path, str]] = []
    current_size = metadata_size
    for entry in payload_entries:
        source, _ = entry
        entry_size = source.stat().st_size if source.exists() else 0
        if current and current_size + entry_size > max_zip_bytes:
            groups.append(current)
            current = []
            current_size = metadata_size
        current.append(entry)
        current_size += entry_size
    if current or not groups:
        groups.append(current)
    return groups


def cmd_create_checkpoint(args: argparse.Namespace, run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    stage = args.stage
    sequence = args.sequence
    checkpoint_type = args.checkpoint_type
    checkpoint_dir_rel = f"checkpoints/{stage}/{checkpoint_type}-{sequence:04d}"
    checkpoint_dir = safe_join(run_dir, checkpoint_dir_rel)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    zip_rel = f"{checkpoint_dir_rel}.zip"
    zip_path = safe_join(run_dir, zip_rel)
    included_roots = checkpoint_included_roots(stage)
    substage_id = getattr(args, "substage_id", None)

    # Cumulative restore inventory. This is intentionally independent of any
    # particular stage's candidate count: existing assets are required, future
    # planned images are pending, and only already-generated/declared-required
    # missing images block restore.
    image_inventory = checkpoint_image_inventory(run_dir, state, included_roots)
    required_image_paths = image_inventory["required_image_paths"]
    pending_future_image_paths = image_inventory["pending_future_image_paths"]
    missing_image_entries = image_inventory["missing_image_entries"]

    excluded_zip_rels = {zip_rel}
    required_existing_asset_paths = checkpoint_required_existing_asset_paths(
        run_dir, checkpoint_dir_rel, included_roots, excluded_zip_rels
    )
    required_substage_page_asset_paths = checkpoint_required_substage_page_asset_paths(
        run_dir, state, stage, substage_id, included_roots
    )
    required_existing_asset_paths = sorted(
        set(required_existing_asset_paths).union(required_substage_page_asset_paths)
    )

    manifest = checkpoint_manifest(
        state,
        stage,
        checkpoint_type,
        sequence,
        included_roots,
        required_existing_asset_paths,
        required_image_paths,
        pending_future_image_paths,
        missing_image_entries,
        [],
    )
    manifest = checkpoint_enrich_manifest_with_substage_integrity(
        manifest,
        stage=stage,
        substage_id=substage_id,
        required_substage_page_asset_paths=required_substage_page_asset_paths,
        included_roots=included_roots,
        run_dir=run_dir,
    )
    bundle = {
        "stage": stage,
        "checkpoint_type": checkpoint_type,
        "sequence": sequence,
        "relative_path": zip_rel,
        "created_at": utc_now(),
        "included_roots": included_roots,
        "stage_coverage": checkpoint_stage_coverage(included_roots),
        "cumulative_required": True,
        "substage_checkpoint_page_integrity_required": True,
        "checkpoint_scope": "cumulative_from_workflow_start_to_current_stage_or_substage",
        "non_delta_checkpoint_guard": "Do not accept or advertise current-stage-only or current-substage-only checkpoint zips as cumulative restore bundles.",
        "required_existing_asset_count": len(required_existing_asset_paths),
        "required_image_count": len(required_image_paths),
        "required_existing_image_count": len(required_image_paths),
        "pending_future_image_count": len(pending_future_image_paths),
        "checkpoint_status": manifest["checkpoint_status"],
        "restore_status": manifest["restore_status"],
        "image_checkpoint_completeness": manifest["image_checkpoint_completeness"],
        "asset_checkpoint_completeness": manifest["asset_checkpoint_completeness"],
    }
    if pending_future_image_paths:
        bundle["pending_future_image_count"] = len(pending_future_image_paths)
        bundle["pending_future_image_policy"] = "pending_next_outputs_not_restore_blockers"
    if missing_image_entries:
        bundle["redo_required_until_missing_images_restored_or_stage_redone"] = True
        bundle["missing_image_manifest"] = f"{checkpoint_dir_rel}/checkpoint-missing-images.json"
        bundle["missing_image_count"] = len(missing_image_entries)
    state.setdefault("checkpoint_bundles", []).append(bundle)
    state["updated_at"] = utc_now()
    write_json(safe_join(run_dir, state.get("state_file") or "state/project-state.json"), state)

    manifest_path = checkpoint_dir / "checkpoint-manifest.json"
    write_json(manifest_path, manifest)
    missing_manifest_path = checkpoint_dir / "checkpoint-missing-images.json"
    if missing_image_entries:
        write_json(
            missing_manifest_path,
            {
                "schema_version": 2,
                "stage": stage,
                "checkpoint_type": checkpoint_type,
                "sequence": sequence,
                "created_at": utc_now(),
                "instruction": "Restore each already-generated/required image into the exact zip_path listed below. Future planned images appear in checkpoint-manifest.json as pending_future_image_paths and are not missing required images.",
                "missing_images": missing_image_entries,
            },
        )
    missing_asset_manifest_path = checkpoint_dir / "checkpoint-missing-assets.json"
    integrity_manifest_path = checkpoint_dir / "checkpoint-cumulative-integrity.json"

    entries = checkpoint_archive_entries(
        run_dir,
        checkpoint_dir_rel,
        included_roots,
        manifest_path,
        missing_manifest_path,
        missing_image_entries,
        {zip_rel},
    )
    write_checkpoint_zip(zip_path, entries)

    max_zip_bytes = int(getattr(args, "max_zip_bytes", 0) or 0)
    output_zip_paths: list[Path] = [zip_path]
    part_rels: list[str] = []
    if max_zip_bytes > 0 and zip_path.stat().st_size > max_zip_bytes:
        groups = split_payload_entries(entries, max_zip_bytes)
        part_rels = [f"{checkpoint_dir_rel}-part{index:02d}.zip" for index in range(1, len(groups) + 1)]
        manifest = checkpoint_manifest(
            state,
            stage,
            checkpoint_type,
            sequence,
            included_roots,
            required_existing_asset_paths,
            required_image_paths,
            pending_future_image_paths,
            missing_image_entries,
            [],
            part_rels,
        )
        manifest = checkpoint_enrich_manifest_with_substage_integrity(
            manifest,
            stage=stage,
            substage_id=substage_id,
            required_substage_page_asset_paths=required_substage_page_asset_paths,
            included_roots=included_roots,
            run_dir=run_dir,
        )
        manifest["split_policy"] = {
            "max_zip_bytes": max_zip_bytes,
            "size_limit_is_soft": True,
            "reason": "single cumulative checkpoint exceeded configured size limit",
        }
        write_json(manifest_path, manifest)
        bundle["relative_path"] = part_rels[0]
        bundle["checkpoint_parts"] = part_rels
        bundle["all_parts_required_for_restore"] = True
        bundle["split"] = True
        bundle["max_zip_bytes"] = max_zip_bytes
        bundle["checkpoint_status"] = manifest["checkpoint_status"]
        bundle["restore_status"] = manifest["restore_status"]
        bundle["image_checkpoint_completeness"] = manifest["image_checkpoint_completeness"]
        bundle["asset_checkpoint_completeness"] = manifest["asset_checkpoint_completeness"]
        if missing_image_entries:
            bundle["redo_required_until_missing_images_restored_or_stage_redone"] = True
        state["updated_at"] = utc_now()
        write_json(safe_join(run_dir, state.get("state_file") or "state/project-state.json"), state)
        part_exclusions = set(part_rels)
        part_exclusions.add(zip_rel)
        entries = checkpoint_archive_entries(
            run_dir,
            checkpoint_dir_rel,
            included_roots,
            manifest_path,
            missing_manifest_path,
            missing_image_entries,
            part_exclusions,
        )
        metadata_entries = [
            entry for entry in entries if entry[1] in {"checkpoint-manifest.json", "checkpoint-missing-images.json"}
        ]
        payload_groups = split_payload_entries(entries, max_zip_bytes)
        output_zip_paths = []
        for part_rel, payload_group in zip(part_rels, payload_groups):
            part_path = safe_join(run_dir, part_rel)
            write_checkpoint_zip(part_path, metadata_entries + payload_group)
            output_zip_paths.append(part_path)
        if zip_path.exists():
            zip_path.unlink()

    # Post-write validation is mandatory: a checkpoint cannot be claimed as a
    # complete restore bundle unless every existing cumulative asset is present
    # in the single zip or across the split zip-part union.
    validation_attempts = 1
    max_validation_attempts = max(1, int(getattr(args, "checkpoint_validation_attempts", 3) or 3))
    missing_asset_entries = checkpoint_missing_asset_entries_from_zip(output_zip_paths, required_existing_asset_paths)
    while missing_asset_entries and validation_attempts < max_validation_attempts:
        validation_attempts += 1
        # Bounded generic rebuild: repack the same cumulative inventory and revalidate.
        # This prevents a current-substage-only or partially packed archive from
        # being recorded as complete without relying on candidate ids or filenames.
        if part_rels:
            part_exclusions = set(part_rels)
            part_exclusions.add(zip_rel)
            entries = checkpoint_archive_entries(
                run_dir,
                checkpoint_dir_rel,
                included_roots,
                manifest_path,
                missing_manifest_path,
                missing_image_entries,
                part_exclusions,
            )
            metadata_entries = [
                entry for entry in entries if entry[1] in {"checkpoint-manifest.json", "checkpoint-missing-images.json"}
            ]
            payload_groups = split_payload_entries(entries, max_zip_bytes)
            if len(payload_groups) != len(part_rels):
                part_rels = [f"{checkpoint_dir_rel}-part{index:02d}.zip" for index in range(1, len(payload_groups) + 1)]
            output_zip_paths = []
            for part_rel, payload_group in zip(part_rels, payload_groups):
                part_path = safe_join(run_dir, part_rel)
                write_checkpoint_zip(part_path, metadata_entries + payload_group)
                output_zip_paths.append(part_path)
        else:
            entries = checkpoint_archive_entries(
                run_dir,
                checkpoint_dir_rel,
                included_roots,
                manifest_path,
                missing_manifest_path,
                missing_image_entries,
                {zip_rel},
            )
            write_checkpoint_zip(zip_path, entries)
            output_zip_paths = [zip_path]
        missing_asset_entries = checkpoint_missing_asset_entries_from_zip(output_zip_paths, required_existing_asset_paths)
    bundle["checkpoint_validation_attempts"] = validation_attempts
    bundle["bounded_rebuild_attempt_limit"] = max_validation_attempts
    if missing_asset_entries:
        write_json(
            missing_asset_manifest_path,
            {
                "schema_version": 2,
                "stage": stage,
                "checkpoint_type": checkpoint_type,
                "sequence": sequence,
                "created_at": utc_now(),
                "instruction": "These files existed in the cumulative checkpoint scope but were not present in the checkpoint zip/part union. Rebuild the checkpoint before cross-session resume.",
                "missing_assets": missing_asset_entries,
            },
        )
        manifest = checkpoint_manifest(
            state,
            stage,
            checkpoint_type,
            sequence,
            included_roots,
            required_existing_asset_paths,
            required_image_paths,
            pending_future_image_paths,
            missing_image_entries,
            missing_asset_entries,
            part_rels or None,
        )
        manifest = checkpoint_enrich_manifest_with_substage_integrity(
            manifest,
            stage=stage,
            substage_id=substage_id,
            required_substage_page_asset_paths=required_substage_page_asset_paths,
            included_roots=included_roots,
            run_dir=run_dir,
        )
        write_json(manifest_path, manifest)
        bundle["checkpoint_status"] = manifest["checkpoint_status"]
        bundle["restore_status"] = manifest["restore_status"]
        bundle["asset_checkpoint_completeness"] = manifest["asset_checkpoint_completeness"]
        bundle["redo_required_until_missing_assets_restored_or_stage_redone"] = True
        bundle["missing_asset_manifest"] = f"{checkpoint_dir_rel}/checkpoint-missing-assets.json"
        bundle["missing_asset_count"] = len(missing_asset_entries)
        state["updated_at"] = utc_now()
        write_json(safe_join(run_dir, state.get("state_file") or "state/project-state.json"), state)
        # Repack once so checkpoint-missing-assets.json and updated manifest are
        # also included in the artifact the user receives.
        if part_rels:
            part_exclusions = set(part_rels)
            entries = checkpoint_archive_entries(
                run_dir,
                checkpoint_dir_rel,
                included_roots,
                manifest_path,
                missing_manifest_path,
                missing_image_entries,
                part_exclusions,
                missing_asset_manifest_path,
                missing_asset_entries,
            )
            metadata_entries = [
                entry
                for entry in entries
                if entry[1] in {"checkpoint-manifest.json", "checkpoint-missing-images.json", "checkpoint-missing-assets.json"}
            ]
            payload_groups = split_payload_entries(entries, max_zip_bytes)
            for part_rel, payload_group in zip(part_rels, payload_groups):
                write_checkpoint_zip(safe_join(run_dir, part_rel), metadata_entries + payload_group)
        else:
            entries = checkpoint_archive_entries(
                run_dir,
                checkpoint_dir_rel,
                included_roots,
                manifest_path,
                missing_manifest_path,
                missing_image_entries,
                {zip_rel},
                missing_asset_manifest_path,
                missing_asset_entries,
            )
            write_checkpoint_zip(zip_path, entries)
    # Cumulative integrity guard: every substage/page checkpoint must prove it
    # includes all existing files under the cumulative roots through this stage,
    # not only the current substage's output folder. This is paper-agnostic and
    # does not assume any candidate id, image count, or project-specific file.
    integrity_report = checkpoint_integrity_report(
        run_dir=run_dir,
        stage=stage,
        checkpoint_type=checkpoint_type,
        sequence=sequence,
        substage_id=substage_id,
        included_roots=included_roots,
        output_zip_paths=output_zip_paths,
        required_existing_asset_paths=required_existing_asset_paths,
        required_substage_page_asset_paths=required_substage_page_asset_paths,
        missing_image_entries=missing_image_entries,
        missing_asset_entries=missing_asset_entries,
        attempt_count=validation_attempts,
    )
    write_json(integrity_manifest_path, integrity_report)
    bundle["cumulative_integrity_report"] = f"{checkpoint_dir_rel}/checkpoint-cumulative-integrity.json"
    bundle["cumulative_integrity_status"] = integrity_report["checkpoint_integrity_status"]
    bundle["substage_page_checkpoint_completeness"] = (
        "complete_all_required_substage_pages_present"
        if integrity_report["missing_substage_page_asset_count"] == 0
        else "incomplete_missing_required_substage_pages"
    )
    if integrity_report["checkpoint_integrity_status"] != "complete_restore_ready":
        bundle["checkpoint_status"] = "redo_required"
        bundle["restore_status"] = "not_restore_ready_redo_required"
        bundle["redo_required"] = True
        bundle["redo_reason"] = "cumulative_integrity_failed_after_rebuild_attempts"
    state["updated_at"] = utc_now()
    write_json(safe_join(run_dir, state.get("state_file") or "state/project-state.json"), state)

    # Repack once so checkpoint-cumulative-integrity.json is in the checkpoint
    # artifact the user receives. The final archive is a superset of the archive
    # inspected by the guard, so a PASS cannot become less complete by adding
    # this metadata file.
    if part_rels:
        part_exclusions = set(part_rels)
        part_exclusions.add(zip_rel)
        entries = checkpoint_archive_entries(
            run_dir,
            checkpoint_dir_rel,
            included_roots,
            manifest_path,
            missing_manifest_path,
            missing_image_entries,
            part_exclusions,
            missing_asset_manifest_path,
            missing_asset_entries if 'missing_asset_entries' in locals() else [],
            integrity_manifest_path,
        )
        metadata_entries = [
            entry
            for entry in entries
            if entry[1]
            in {
                "checkpoint-manifest.json",
                "checkpoint-missing-images.json",
                "checkpoint-missing-assets.json",
                "checkpoint-cumulative-integrity.json",
            }
        ]
        payload_groups = split_payload_entries(entries, max_zip_bytes)
        for part_rel, payload_group in zip(part_rels, payload_groups):
            write_checkpoint_zip(safe_join(run_dir, part_rel), metadata_entries + payload_group)
    else:
        entries = checkpoint_archive_entries(
            run_dir,
            checkpoint_dir_rel,
            included_roots,
            manifest_path,
            missing_manifest_path,
            missing_image_entries,
            {zip_rel},
            missing_asset_manifest_path,
            missing_asset_entries if 'missing_asset_entries' in locals() else [],
            integrity_manifest_path,
        )
        write_checkpoint_zip(zip_path, entries)
    # Keep the user-facing bundle aligned with the latest post-write validation.
    bundle["checkpoint_integrity"] = checkpoint_integrity_summary(
        stage=stage,
        checkpoint_type=checkpoint_type,
        included_roots=included_roots,
        required_existing_asset_paths=required_existing_asset_paths,
        required_image_paths=required_image_paths,
        pending_future_image_paths=pending_future_image_paths,
        missing_image_entries=missing_image_entries,
        missing_asset_entries=missing_asset_entries,
        validation_attempts=validation_attempts if "validation_attempts" in locals() else 0,
    )
    return bundle
