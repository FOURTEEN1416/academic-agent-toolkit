"""Image generation provenance and canonical image batch registration helpers for v3.2.15f."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

from .artifacts import artifact_record, find_artifact
from .constants import (
    MAX_CANDIDATE_COUNT_BY_STEP,
    S5_REFERENCE_IMAGE_INPUT_POLICY,
    TARGET_RASTER_IMAGE_EXTS,
    TARGET_RASTER_IMAGE_STEPS,
)
from .errors import StateError
from .paths import generated_path_to_relative, normalize_relative_path, safe_join, utc_now
from .identity import default_candidate_paths, load_prompt_index, normalize_candidate_id
from .runtime_config import canonicalize_generator, validate_image_generation_route


def runtime_environment_from_state(state: dict[str, Any] | None, explicit_environment: str | None = None) -> str:
    if explicit_environment:
        return explicit_environment
    runtime = (state or {}).get("runtime_environment", {})
    if isinstance(runtime, dict):
        return runtime.get("environment") or "unknown"
    return "unknown"


def _target_image_step(step: str) -> bool:
    return step in TARGET_RASTER_IMAGE_STEPS


def _event_matches(event: dict[str, Any], *, step: str, batch_id: str, event_id: str | None = None) -> bool:
    if event_id and event.get("event_id") != event_id:
        return False
    return event.get("step") == step and event.get("batch_id") == batch_id and event.get("status") == "generation_succeeded"


def _find_generation_event(state: dict[str, Any], *, step: str, batch_id: str, event_id: str | None = None) -> dict[str, Any] | None:
    for event in reversed(state.get("image_generation_events", [])):
        if _event_matches(event, step=step, batch_id=batch_id, event_id=event_id):
            return event
    return None


def _validate_target_batch_source_event(
    args: argparse.Namespace,
    run_dir: Path,
    state: dict[str, Any],
) -> dict[str, Any] | None:
    if not _target_image_step(args.step) or str(args.kind or "").lower() != "image":
        return None
    event_id = getattr(args, "generation_event_id", None)
    event = _find_generation_event(state, step=args.step, batch_id=args.batch_id, event_id=event_id)
    if event is None:
        raise StateError(
            "register-image-batch for S2/S5 target-paper images requires a matching recorded image_generation_event "
            "from the environment-locked image route. Record the image_gen/Create Image/API event first; do not register a locally drawn PNG."
        )
    runtime_env = runtime_environment_from_state(state)
    validate_image_generation_route(
        environment=event.get("environment") or runtime_env,
        generator=event.get("generator"),
        approved_api_name=event.get("approved_api_name"),
        route_unavailable_reason=event.get("route_unavailable_reason"),
    )
    recorded_paths = set(event.get("generated_paths") or [])
    if not recorded_paths:
        raise StateError(
            f"image_generation_event {event.get('event_id')} has no project-run-relative generated_paths; "
            "target image registration is blocked to prevent local/programmatic PNG substitution."
        )
    source_rel_paths: list[str] = []
    for source in args.source or []:
        rel = generated_path_to_relative(run_dir, source, require_exists=True)
        if rel is None:
            raise StateError(
                f"source image is outside the project run and cannot be tied to the recorded generation event: {source}"
            )
        source_rel_paths.append(rel)
    missing_from_event = [rel for rel in source_rel_paths if rel not in recorded_paths]
    if missing_from_event:
        raise StateError(
            "source images do not match the recorded image-generation event; blocked to prevent registering local/programmatic output: "
            + ", ".join(missing_from_event)
        )
    return event



def _prompt_index_target_paths(
    args: argparse.Namespace,
    run_dir: Path,
    source_count: int,
) -> list[tuple[str, str]] | None:
    """Return [(candidate_id, target_rel_path)] from a prompt index for target images.

    S2/S5 active target images must be registered through prompt-index rows so
    image records, status files, artifacts, and checkpoint inventories use the
    same candidate_id. Non-target auxiliary image batches may still use a plain
    output directory, but target raster stages cannot silently fall back to
    numeric artifact ids.
    """
    prompt_index = getattr(args, "prompt_index", None)
    wants_prompt_index = bool(getattr(args, "use_target_image_paths", False) or prompt_index)
    if _target_image_step(args.step) and str(getattr(args, "kind", "image") or "image").lower() == "image":
        if not prompt_index:
            from .identity import default_prompt_index_path
            default_rel = default_prompt_index_path(args.step)
            if safe_join(run_dir, default_rel).is_file():
                prompt_index = default_rel
            else:
                raise StateError(
                    f"{args.step} target image registration requires a prompt-index so candidate_id, prompt_path, "
                    "target_image_path, status, artifacts, and checkpoints stay coherent"
                )
        wants_prompt_index = True
    if not wants_prompt_index:
        return None
    if not prompt_index:
        raise StateError("--use-target-image-paths requires --prompt-index")
    index_path = safe_join(run_dir, normalize_relative_path(prompt_index))
    if not index_path.is_file():
        raise StateError(f"prompt index does not exist: {prompt_index}")
    normalized = load_prompt_index(run_dir, prompt_index, stage=args.step, require_prompt_files=True)
    candidates = normalized["candidates"]
    start = max(0, int(getattr(args, "start_index", 1)) - 1)
    selected = candidates[start : start + source_count]
    if len(selected) != source_count:
        raise StateError(
            f"prompt index candidate count mismatch: need {source_count} entries starting at {start + 1}, found {len(selected)}"
        )
    field = getattr(args, "target_path_field", None) or "target_image_path"
    result: list[tuple[str, str]] = []
    for idx, row in enumerate(selected, start=start + 1):
        target = row.get(field)
        if not target:
            raise StateError(f"prompt index candidate row {idx} ({row.get('candidate_id')}) lacks {field}")
        rel = normalize_relative_path(target)
        if Path(rel).suffix.lower() not in TARGET_RASTER_IMAGE_EXTS:
            raise StateError(f"target image path must be raster PNG/JPG/JPEG/WebP: {rel}")
        cid = normalize_candidate_id(row.get("candidate_id"), label=f"prompt index candidate row {idx}.candidate_id")
        result.append((cid, rel))
    return result


def _reference_image_paths(args: argparse.Namespace, run_dir: Path) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for raw in getattr(args, "reference_image_path", None) or []:
        rel = normalize_relative_path(raw)
        if Path(rel).suffix.lower() not in TARGET_RASTER_IMAGE_EXTS:
            raise StateError(f"reference image path must be raster PNG/JPG/JPEG/WebP: {rel}")
        if not safe_join(run_dir, rel).is_file():
            raise StateError(f"reference image path does not exist: {rel}")
        if rel not in seen:
            seen.add(rel)
            refs.append(rel)
    return refs

def _candidate_registry_key(step: str) -> str:
    return "s2_sketches" if step == "S2-SKETCH-EXPLORE" else "s5_candidates"


def _candidate_status_after_image_registration(step: str) -> str:
    return "NEEDS_REVIEW" if step == "S2-SKETCH-EXPLORE" else "NEEDS_HUMAN_SELECTION"


def _upsert_registered_candidate_image(
    state: dict[str, Any],
    *,
    step: str,
    candidate_id: str,
    active_image_path: str,
    source_event: dict[str, Any] | None,
    batch_id: str,
) -> None:
    registry = state.setdefault("candidate_run_registry", {}).setdefault(_candidate_registry_key(step), {})
    cid = normalize_candidate_id(candidate_id)
    row = registry.setdefault(cid, {"step": step, "candidate_id": cid})
    defaults = default_candidate_paths(step, cid)
    row.update(
        {
            "step": step,
            "candidate_id": cid,
            "status": row.get("status") if row.get("status") not in {None, "", "PENDING", "MISSING"} else _candidate_status_after_image_registration(step),
            "candidate_dir": row.get("candidate_dir") or defaults["candidate_dir"],
            "active_image_path": normalize_relative_path(active_image_path),
            "active_audit_json": row.get("active_audit_json") or defaults["active_audit_json"],
            "status_path": row.get("status_path") or defaults["status_path"],
            "image_generated": True,
            "image_generation_event_id": (source_event or {}).get("event_id"),
            "registration_batch_id": batch_id,
            "candidate_id_source_of_truth": "prompt-index target path" if source_event else "registration input",
            "id_path_coherence_status": "candidate_id_matches_active_image_path",
            "updated_at": utc_now(),
        }
    )


def image_batch_records(args: argparse.Namespace, run_dir: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    source_event = _validate_target_batch_source_event(args, run_dir, state)
    target_paths = _prompt_index_target_paths(args, run_dir, len(args.source or []))
    output_dir_rel = normalize_relative_path(args.output_dir)
    output_dir = safe_join(run_dir, output_dir_rel)
    output_dir.mkdir(parents=True, exist_ok=True)
    max_count = MAX_CANDIDATE_COUNT_BY_STEP.get(args.step)
    if max_count is not None and (args.start_index < 1 or args.start_index + len(args.source) - 1 > max_count):
        raise StateError(
            f"{args.step} candidate image batches must stay within the planned prompt-index candidate count or max_count={max_count}; "
            "do not infer candidate ids from C/F prefixes when a prompt-index is available."
        )

    created: list[dict[str, Any]] = []
    for offset, source in enumerate(args.source):
        src = Path(source).expanduser().resolve()
        if not src.exists() or not src.is_file():
            raise StateError(f"source image does not exist or is not a file: {source}")
        ext = src.suffix.lower()
        if ext not in TARGET_RASTER_IMAGE_EXTS:
            raise StateError(f"unsupported image extension for source: {source}")
        index = args.start_index + offset
        candidate_id_for_artifact = f"{index:02d}"
        if target_paths is not None:
            candidate_id_for_artifact, dest_rel = target_paths[offset]
        else:
            file_name = args.filename_pattern.format(index=index, step=args.step.lower().replace("-", "_"))
            if Path(file_name).name != file_name:
                raise StateError("filename pattern must produce a file name, not a path")
            if not Path(file_name).suffix:
                file_name += ext
            dest_rel = normalize_relative_path(Path(output_dir_rel) / file_name)
        dest = safe_join(run_dir, dest_rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not args.replace:
            raise StateError(f"destination exists; use --replace to overwrite: {dest_rel}")
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        candidate_id_for_artifact = normalize_candidate_id(candidate_id_for_artifact)
        artifact_id = f"{args.batch_id}-{candidate_id_for_artifact}"
        record_args = argparse.Namespace(
            artifact_id=artifact_id,
            step=args.step,
            kind=args.kind,
            path=dest_rel,
            summary=args.summary or f"{args.batch_id} image {index:02d}",
            tag=sorted(set((args.tag or []) + [args.batch_id, args.step])),
            status=args.status,
            source_user_request=args.source_user_request or "",
            source_artifact_role=[],
            generation_event_id=(source_event or {}).get("event_id") if source_event else None,
        )
        existing = find_artifact(state, artifact_id)
        record = artifact_record(record_args, run_dir, existing, state=state)
        record["candidate_id"] = candidate_id_for_artifact
        record["id_path_coherence_status"] = "candidate_id_matches_relative_path"
        if source_event:
            record["image_generation_event_id"] = source_event.get("event_id")
            record["image_generation_generator"] = source_event.get("generator")
            record["image_generation_environment"] = source_event.get("environment")
            record["image_route_guard_status"] = source_event.get("route_guard_status")
            record["stage_local_image_mirror_status"] = "complete" if target_paths is not None else "copied_to_registration_output_dir"
            record["stage_local_image_mirror_mode"] = "prompt_index_target_image_path" if target_paths is not None else "batch_output_dir"
        if existing is None:
            state.setdefault("artifacts", []).append(record)
        else:
            existing.clear()
            existing.update(record)
        _upsert_registered_candidate_image(state, step=args.step, candidate_id=candidate_id_for_artifact, active_image_path=dest_rel, source_event=source_event, batch_id=args.batch_id)
        created.append(record)
    if source_event:
        source_event["canonical_copy_status"] = "stage_local_mirror_complete" if target_paths is not None else "copied_to_registration_output_dir"
        source_event["canonical_target_image_paths"] = [record.get("relative_path") for record in created]
        source_event["candidate_outputs"] = {record.get("candidate_id"): record.get("relative_path") for record in created}
    return created


def image_generation_event(args: argparse.Namespace, run_dir: Path, state: dict[str, Any] | None = None) -> dict[str, Any]:
    now = utc_now()
    approved_api_name = getattr(args, "approved_api_name", None)
    environment = runtime_environment_from_state(state, getattr(args, "environment", None))
    route_unavailable_reason = getattr(args, "route_unavailable_reason", None)
    route_guard = validate_image_generation_route(
        environment=environment,
        generator=args.generator,
        approved_api_name=approved_api_name,
        route_unavailable_reason=route_unavailable_reason,
    )
    generator = route_guard["generator"]
    max_count = MAX_CANDIDATE_COUNT_BY_STEP.get(args.step)
    if max_count is not None and len(args.generated_path or []) > max_count:
        raise StateError(
            f"{args.step} image generation events must not record more than {max_count} generated paths. "
            "Smaller image-only substage chunks are allowed."
        )
    generated_paths: list[str] = []
    omitted_count = 0
    for source in args.generated_path or []:
        rel_path = generated_path_to_relative(run_dir, source, True if _target_image_step(args.step) else args.require_exists)
        if rel_path is None:
            omitted_count += 1
        else:
            if _target_image_step(args.step) and Path(rel_path).suffix.lower() not in TARGET_RASTER_IMAGE_EXTS:
                raise StateError(f"target-paper generated path must be raster PNG/JPG/JPEG/WebP, not: {rel_path}")
            generated_paths.append(rel_path)
    if _target_image_step(args.step):
        if not generated_paths:
            raise StateError(
                "target-paper image generation events must record at least one existing project-run-relative generated_path; "
                "do not record prompt-only, external-only, local-renderer, or placeholder generations."
            )
        if len(generated_paths) != 1:
            raise StateError(
                "S2/S5 image-only generation is row-atomic: record exactly one generated raster per image-generation event/call. "
                "Split multi-row or multi-image batches into one event per prompt-index candidate."
            )
        if omitted_count:
            raise StateError(
                "target-paper image generation paths cannot be omitted as external/unsafe; save generated rasters inside the project run first"
            )
    if args.generated_path and omitted_count == 0:
        path_status = "relative_paths_recorded"
    elif args.generated_path:
        path_status = "external_or_unsafe_paths_omitted"
    else:
        path_status = "no_generated_paths_provided"
    reference_paths = _reference_image_paths(args, run_dir)
    reference_input_status = getattr(args, "reference_input_status", None)
    if not reference_input_status:
        reference_input_status = "not_requested" if not reference_paths else "ignored_unsupported"
    return {
        "event_id": args.event_id,
        "batch_id": args.batch_id,
        "step": args.step,
        "environment": route_guard["environment"],
        "generator": generator,
        "approved_api_name": approved_api_name or None,
        "route_unavailable_reason": route_unavailable_reason or None,
        "required_generator": route_guard["required_generator"],
        "route_guard_status": route_guard["route_guard_status"],
        "route_guard_rule": route_guard["route_guard_rule"],
        "generator_policy": (
            "Target-paper S2/S5 images must come from the environment-locked image-generation route: "
            "Codex=image_gen, ChatGPT web=Create Image / ChatGPT Images 2.0, other runtimes=named approved image-generation API. "
            "Programmatic raster drawing is invalid even if it saves PNG/JPG/WebP files."
        ),
        "status": "generation_succeeded",
        "state_update_mode": "auto_project_state_json_only",
        "generated_paths": generated_paths,
        "generated_path_mode": "project_run_relative",
        "generated_path_recording_status": path_status,
        "omitted_generated_path_count": omitted_count,
        "reference_image_paths": reference_paths,
        "reference_image_input_status": reference_input_status,
        "reference_image_input_policy": S5_REFERENCE_IMAGE_INPUT_POLICY if args.step == "S5-CANDIDATE-IMAGE" else None,
        "canonical_copy_status": "pending_explicit_copy",
        "summary": args.summary or "",
        "source_user_request": args.source_user_request or "",
        "created_at": now,
        "updated_at": now,
    }
