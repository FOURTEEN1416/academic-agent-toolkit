"""Command implementations for the persistent state CLI."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .artifacts import (
    artifact_record,
    find_artifact,
    refresh_active_artifact_roles,
    refresh_pending_outputs,
    is_active_artifact,
    upsert_artifact_record,
    upsert_list_record,
)
from .constants import (
    CANONICAL_OUTPUTS,
    PENDING_CANONICAL_OUTPUTS,
    PREFERENCE_ANALYSIS_PATH,
    STEP_CLEANUP_EXTRA_DIRS,
    STEP_CLEANUP_EXTRA_FILES,
    TARGET_RASTER_IMAGE_EXTS,
    TARGET_RASTER_IMAGE_STEPS,
    TARGET_RASTER_REFERENCE_ROLES,
    WORKFLOW_STEPS,
    FIRST_ROUND_DEFAULT_STYLE_ID,
    FIRST_ROUND_STYLE_OPTIONS,
    FIRST_ROUND_STYLE_USER_REMINDER,
    S1_TO_S2_STYLE_OPTIONS_REMINDER,
    SECOND_ROUND_STYLE_OPTIONS,
    SECOND_ROUND_STYLE_USER_REMINDER,
)
from .errors import StateError
from .handoff_guidance import cmd_write_guidance as guidance_write_guidance
from .image_outputs import image_batch_records, image_generation_event
from .paths import load_state, normalize_project_id, normalize_relative_path, project_dir, safe_join, sha256_file, state_file, utc_now, write_json
from .preferences import preference_reference_records
from .runtime_config import default_image_generation_note, infer_image_generation_route, runtime_environment_note
from .state_schema import bump_step_epoch, ensure_output_dirs, ensure_step_runs, initial_state, mark_step_run_in_progress, workflow_state
from .substages import (
    cmd_create_checkpoint as substages_create_checkpoint,
    cmd_mark_candidate as substages_mark_candidate,
    cmd_mark_substage as substages_mark_substage,
    cmd_plan_substages as substages_plan_substages,
    cmd_recommend_next_action as substages_recommend_next_action,
    cmd_reset_candidate as substages_reset_candidate,
    cmd_scan_substages as substages_scan_substages,
    write_candidate_status_files as substages_write_candidate_status_files,
)
from .validation import validate_state


def workflow_step_names() -> list[str]:
    return [step for step, _, _, _ in WORKFLOW_STEPS]


def cleanup_target_steps(target_step: str, from_step: str | None = None) -> list[tuple[str, str]]:
    names = workflow_step_names()
    if target_step not in names:
        raise StateError(f"unknown target step: {target_step}")
    target_index = names.index(target_step)
    if from_step in names:
        from_index = names.index(str(from_step))
        end_index = from_index if from_index >= target_index else len(names) - 1
    else:
        end_index = len(names) - 1
    return [(step, output_dir) for step, _, _, output_dir in WORKFLOW_STEPS[target_index : end_index + 1]]


def path_has_release_content(run_dir: Path, rel: str) -> bool:
    target = safe_join(run_dir, rel)
    if target.is_file():
        return True
    if target.is_dir():
        return any(target.iterdir())
    return False


def step_family_existing_output_paths(run_dir: Path, target_step: str) -> tuple[list[str], list[str]]:
    """Return existing loose outputs that belong to a step family."""
    return [], []


def step_has_prior_products(run_dir: Path, state: dict, target_step: str) -> bool:
    target_dirs = [
        output_dir
        for step, _, _, output_dir in WORKFLOW_STEPS
        if step == target_step
    ]
    target_dirs.extend(STEP_CLEANUP_EXTRA_DIRS.get(target_step, []))
    target_files = {
        row["relative_path"]
        for row in PENDING_CANONICAL_OUTPUTS
        if row.get("step") == target_step and row.get("relative_path")
    }
    target_files.update(STEP_CLEANUP_EXTRA_FILES.get(target_step, []))
    if target_step in CANONICAL_OUTPUTS:
        target_files.add(CANONICAL_OUTPUTS[target_step])
    if any(path_has_release_content(run_dir, rel) for rel in target_dirs):
        return True
    if any(path_has_release_content(run_dir, rel) for rel in target_files):
        return True
    for artifact in state.get("artifacts", []):
        if artifact.get("step") == target_step and is_active_artifact(state, artifact):
            return True
    for event in state.get("image_generation_events", []):
        if event.get("step") == target_step and event.get("status") == "generation_succeeded":
            return True
    return False


def step_cleanup_plan(run_dir: Path, target_step: str, from_step: str | None = None) -> dict:
    targets = cleanup_target_steps(target_step, from_step=from_step)
    target_steps = {step for step, _ in targets}
    rel_dirs = [output_dir for _, output_dir in targets]
    rel_files = {
        row["relative_path"]
        for row in PENDING_CANONICAL_OUTPUTS
        if row.get("step") in target_steps and row.get("relative_path")
    }
    for step in target_steps:
        rel_dirs.extend(STEP_CLEANUP_EXTRA_DIRS.get(step, []))
        family_dirs, family_files = step_family_existing_output_paths(run_dir, step)
        rel_dirs.extend(family_dirs)
        rel_files.update(family_files)
    rel_dirs = list(dict.fromkeys(rel_dirs))
    rel_files.update(CANONICAL_OUTPUTS[step] for step in target_steps if step in CANONICAL_OUTPUTS)
    for step in target_steps:
        rel_files.update(STEP_CLEANUP_EXTRA_FILES.get(step, []))
    delete_dirs = []
    delete_files = []
    missing_paths = []
    for rel in rel_dirs:
        path = safe_join(run_dir, rel)
        if path.exists():
            delete_dirs.append(rel)
        else:
            missing_paths.append(rel)
    for rel in sorted(rel_files):
        if any(rel == d or rel.startswith(f"{d}/") for d in rel_dirs):
            continue
        path = safe_join(run_dir, rel)
        if path.exists():
            delete_files.append(rel)
        else:
            missing_paths.append(rel)
    return {
        "target_steps": sorted(target_steps, key=workflow_step_names().index),
        "delete_dirs": delete_dirs,
        "delete_files": delete_files,
        "missing_paths": sorted(set(missing_paths)),
    }


def cleanup_events(state: dict) -> list[dict]:
    cleanup_policy = state.setdefault("step_rewind_cleanup_policy", {})
    return cleanup_policy.setdefault("cleanup_events", [])


def step_index(step: str | None) -> int | None:
    names = workflow_step_names()
    if step in names:
        return names.index(str(step))
    return None


def should_cleanup_for_step_transition(from_step: str | None, target_step: str) -> bool:
    from_index = step_index(from_step)
    target_index = step_index(target_step)
    return from_index is not None and target_index is not None and target_index <= from_index


def clear_step_specific_state(state: dict, target_steps: set[str], event: dict) -> None:
    last_batch = state.get("last_registered_image_batch")
    if isinstance(last_batch, dict) and last_batch.get("step") in target_steps:
        state.pop("last_registered_image_batch", None)
    last_event = state.get("last_image_generation_event")
    if isinstance(last_event, dict) and last_event.get("step") in target_steps:
        state.pop("last_image_generation_event", None)
    state["generated_image_default_locations_to_register"] = []


def persist_cleanup_checkpoint(persist_path: Path | None, state: dict) -> None:
    if persist_path is not None:
        state["updated_at"] = utc_now()
        write_json(persist_path, state)


def find_cleanup_event(state: dict, event_id: str | None = None) -> dict | None:
    events = cleanup_events(state)
    if event_id:
        for event in events:
            if event.get("event_id") == event_id:
                return event
        return None
    for event in reversed(events):
        if event.get("status") in {"planned", "running"}:
            return event
    return None


def execute_cleanup_event(run_dir: Path, state: dict, event: dict, persist_path: Path | None = None) -> dict:
    target_step = event["target_step"]
    target_steps = set(event["target_steps"])
    event["status"] = "running"
    event.setdefault("started_at", utc_now())
    persist_cleanup_checkpoint(persist_path, state)

    deleted_paths: set[str] = set(event.get("deleted_paths", []))
    missing_paths: set[str] = set(event.get("missing_paths", []))
    for rel in event.get("planned_delete_dirs", []):
        target = safe_join(run_dir, rel)
        if target.exists():
            shutil.rmtree(target)
            deleted_paths.add(rel)
        else:
            missing_paths.add(rel)
    for rel in event.get("planned_delete_files", []):
        target = safe_join(run_dir, rel)
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            deleted_paths.add(rel)
        else:
            missing_paths.add(rel)

    removed_ids: set[str] = set(event.get("removed_artifact_ids", []))
    retained_artifacts: list[dict] = []
    for artifact in state.get("artifacts", []):
        rel = artifact.get("relative_path", "")
        artifact_step = artifact.get("step")
        in_deleted_step = artifact_step in target_steps
        in_deleted_path = any(
            rel == d or rel.startswith(f"{d}/") for d in event.get("planned_delete_dirs", [])
        ) or rel in event.get("planned_delete_files", [])
        if in_deleted_step or in_deleted_path:
            artifact_id = artifact.get("artifact_id")
            if artifact_id:
                removed_ids.add(artifact_id)
        else:
            retained_artifacts.append(artifact)
    state["artifacts"] = retained_artifacts

    removed_generation_event_ids: set[str] = set(event.get("removed_image_generation_event_ids", []))
    retained_generation_events: list[dict] = []
    for generation_event in state.get("image_generation_events", []):
        if generation_event.get("step") in target_steps:
            generation_event_id = generation_event.get("event_id")
            if generation_event_id:
                removed_generation_event_ids.add(generation_event_id)
        else:
            retained_generation_events.append(generation_event)
    state["image_generation_events"] = retained_generation_events
    clear_step_specific_state(state, target_steps, event)

    if not event.get("bumped_step_epochs"):
        bumped: list[dict] = []
        ordered_target_steps = [step for step, _, _, _ in WORKFLOW_STEPS if step in target_steps]
        for step in ordered_target_steps:
            bumped.append(bump_step_epoch(state, step, "in_progress" if step == target_step else "pending"))
        event["bumped_step_epochs"] = bumped
        persist_cleanup_checkpoint(persist_path, state)

    cleanup_policy = state.setdefault("step_rewind_cleanup_policy", {})
    cleanup_policy["last_cleanup_event_id"] = event["event_id"]
    cleanup_policy["state_file_deleted"] = False
    state["current_step"] = target_step
    state["workflow_plan"] = workflow_state(target_step)
    state["workflow_step_before_user_request"] = event.get("from_step")
    state["workflow_step_after_user_request"] = target_step
    state["state_transition_reason"] = event.get("reason") or f"rewound_to_{target_step}_and_cleaned_target_and_later_outputs"
    state["last_user_request"] = event.get("source_user_request") or state.get("last_user_request")
    state["updated_at"] = utc_now()
    ensure_output_dirs(run_dir)
    refresh_pending_outputs(state)

    event["deleted_paths"] = sorted(deleted_paths)
    event["missing_paths"] = sorted(missing_paths)
    event["removed_artifact_ids"] = sorted(artifact_id for artifact_id in removed_ids if artifact_id)
    event["removed_image_generation_event_ids"] = sorted(event_id for event_id in removed_generation_event_ids if event_id)
    event["status"] = "completed"
    event["completed_at"] = utc_now()
    event["state_file_deleted"] = False
    persist_cleanup_checkpoint(persist_path, state)
    return event


def apply_step_cleanup(
    run_dir: Path,
    state: dict,
    target_step: str,
    reason: str = "",
    source_user_request: str = "",
    dry_run: bool = False,
    persist_path: Path | None = None,
) -> dict:
    ensure_step_runs(state)
    before_step = state.get("current_step", "S0-PAPER-FOUNDATION")
    plan = step_cleanup_plan(run_dir, target_step, from_step=before_step)
    event_id = f"cleanup-{utc_now().replace(':', '').replace('-', '')}-{target_step.lower()}"
    event = {
        "event_id": event_id,
        "status": "dry_run" if dry_run else "planned",
        "created_at": utc_now(),
        "backjump_decision": "regenerate_or_replace_target",
        "cleanup_required": True,
        "cleanup_reason": reason or "return/rerun execution requires cleanup of covered target_step..from_step outputs",
        "target_step": target_step,
        "target_steps": plan["target_steps"],
        "from_step": before_step,
        "reason": reason,
        "source_user_request": source_user_request,
        "deleted_paths": [],
        "planned_delete_dirs": plan["delete_dirs"],
        "planned_delete_files": plan["delete_files"],
        "missing_paths": plan["missing_paths"],
        "removed_artifact_ids": [],
        "removed_image_generation_event_ids": [],
        "dry_run": dry_run,
        "policy": "hard rewind cleanup: when returning to a target step for execution, delete products for target_step through from_step, remove covered output records from active state, and never delete state/project-state.json",
    }
    if dry_run:
        return event

    cleanup_policy = state.setdefault("step_rewind_cleanup_policy", {})
    cleanup_policy.setdefault("cleanup_events", []).append(event)
    cleanup_policy["last_cleanup_event_id"] = event_id
    cleanup_policy["state_file_deleted"] = False
    persist_cleanup_checkpoint(persist_path, state)
    return execute_cleanup_event(run_dir, state, event, persist_path=persist_path)


def resume_step_cleanup(
    run_dir: Path,
    state: dict,
    event_id: str | None = None,
    persist_path: Path | None = None,
) -> dict:
    event = find_cleanup_event(state, event_id)
    if event is None:
        raise StateError("no planned or running cleanup event to resume")
    if event.get("status") == "completed":
        return event
    if event.get("dry_run"):
        raise StateError("dry-run cleanup events cannot be resumed")
    return execute_cleanup_event(run_dir, state, event, persist_path=persist_path)


def cmd_init(args) -> int:
    project_id = normalize_project_id(args.project_id)
    run_dir = project_dir(args)
    ensure_output_dirs(run_dir)
    path = state_file(run_dir)
    if path.exists() and not args.force:
        print(f"state already exists: {path}")
        return 0
    state = initial_state(project_id, run_dir, args.title)
    if args.source_material:
        state["notes"].append({"created_at": utc_now(), "summary": args.source_material})
    write_json(path, state)
    print(f"initialized {path}")
    return 0


def cmd_register(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    existing = find_artifact(state, args.artifact_id)
    record = artifact_record(args, run_dir, existing, state=state)
    upsert_artifact_record(state, record)
    state["last_user_request"] = args.source_user_request or state.get("last_user_request")
    state["updated_at"] = utc_now()
    if args.step in TARGET_RASTER_IMAGE_STEPS:
        substages_write_candidate_status_files(run_dir, args.step, state)
    refresh_pending_outputs(state)
    write_json(state_file(run_dir), state)
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


def cmd_update_step(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    before_step = state.get("current_step", "S0-PAPER-FOUNDATION")
    resume_interrupted = bool(getattr(args, "resume_interrupted", False))
    if resume_interrupted:
        if args.current_step != before_step:
            raise StateError("--resume-interrupted is only valid for the same current step; earlier-step returns require cleanup")
        resume_policy = state.setdefault("step_rewind_cleanup_policy", {})
        resume_policy["last_interrupted_resume"] = {
            "step": args.current_step,
            "status": "resume_without_cleanup_requested",
            "created_at": utc_now(),
            "source_user_request": args.source_user_request or "",
            "resume_instructions": args.resume_instructions or "",
            "policy": (
                "Explicit interrupted-resume exception: skip covered-step cleanup only when the user clearly asks "
                "to continue the current incomplete step without cleanup. Default same-step execution remains cleanup + rerun."
            ),
        }
    elif should_cleanup_for_step_transition(before_step, args.current_step):
        cleanup_reason = (
            f"returning from {before_step} to {args.current_step}; mandatory cleanup of covered step products before execution"
        )
        apply_step_cleanup(
            run_dir,
            state,
            args.current_step,
            reason=cleanup_reason,
            source_user_request=args.source_user_request or "",
            persist_path=state_file(run_dir),
        )
        state = load_state(run_dir)
    mark_step_run_in_progress(state, args.current_step, bump_if_zero=True)
    state["current_step"] = args.current_step
    state["workflow_plan"] = workflow_state(args.current_step)
    if args.resume_instructions:
        state["resume_instructions"] = args.resume_instructions
    if args.source_user_request:
        state["last_user_request"] = args.source_user_request
    state["updated_at"] = utc_now()
    write_json(state_file(run_dir), state)
    print(f"current_step={args.current_step}")
    return 0


def cmd_rewind_step(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    event = apply_step_cleanup(
        run_dir=run_dir,
        state=state,
        target_step=args.target_step,
        reason=args.reason,
        source_user_request=args.source_user_request,
        dry_run=args.dry_run,
        persist_path=None if args.dry_run else state_file(run_dir),
    )
    if not args.dry_run:
        write_json(state_file(run_dir), state)
    print(json.dumps(event, indent=2, ensure_ascii=False))
    return 0


def cmd_resume_cleanup(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    event = resume_step_cleanup(
        run_dir=run_dir,
        state=state,
        event_id=args.event_id,
        persist_path=state_file(run_dir),
    )
    write_json(state_file(run_dir), state)
    print(json.dumps(event, indent=2, ensure_ascii=False))
    return 0


def cmd_overwrite(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    existing = find_artifact(state, args.artifact_id)
    if existing is None:
        raise StateError(f"cannot overwrite missing artifact_id: {args.artifact_id}")
    record = artifact_record(args, run_dir, existing, state=state)
    existing.clear()
    existing.update(record)
    state["updated_at"] = utc_now()
    refresh_pending_outputs(state)
    write_json(state_file(run_dir), state)
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


def protected_target_image_artifact(state: dict, artifact: dict) -> bool:
    """Return True for target-paper image artifacts that must not be directly deleted."""
    rel_path = artifact.get("relative_path") or ""
    suffix = Path(rel_path).suffix.lower()
    role = artifact.get("artifact_role")
    step = artifact.get("step")
    kind = str(artifact.get("kind") or "").lower()
    if not is_active_artifact(state, artifact):
        return False
    if role in TARGET_RASTER_REFERENCE_ROLES:
        return True
    if step in TARGET_RASTER_IMAGE_STEPS and kind == "image" and suffix in TARGET_RASTER_IMAGE_EXTS:
        return True
    return False


def cmd_delete(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    existing = find_artifact(state, args.artifact_id)
    if existing is None:
        raise StateError(f"artifact_id not found: {args.artifact_id}")
    if protected_target_image_artifact(state, existing):
        raise StateError(
            "direct delete is forbidden for active target-paper image artifacts. Mark the artifact/candidate stale, "
            "use reset-candidate, or run rewind-step cleanup for an explicit rerun; do not delete generated image files or "
            "their provenance records directly."
        )
    rel_path = existing.get("relative_path")
    if rel_path:
        target = safe_join(run_dir, rel_path)
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
    state["artifacts"] = [
        artifact for artifact in state.get("artifacts", []) if artifact.get("artifact_id") != args.artifact_id
    ]
    state["updated_at"] = utc_now()
    refresh_active_artifact_roles(state)
    refresh_pending_outputs(state)
    write_json(state_file(run_dir), state)
    print(f"deleted artifact_id={args.artifact_id}")
    return 0


def cmd_mark_artifact_stale(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    existing = find_artifact(state, args.artifact_id)
    if existing is None:
        raise StateError(f"artifact_id not found: {args.artifact_id}")
    now = utc_now()
    existing["status"] = "stale"
    existing["stale_reason"] = args.reason or "marked stale without deleting the underlying file"
    existing["updated_at"] = now
    state.setdefault("artifact_staleness_events", []).append(
        {
            "artifact_id": args.artifact_id,
            "relative_path": existing.get("relative_path"),
            "step": existing.get("step"),
            "reason": args.reason or "",
            "file_delete_policy": "file_preserved; direct delete of target-paper images is prohibited",
            "created_at": now,
        }
    )
    state["updated_at"] = now
    refresh_active_artifact_roles(state)
    refresh_pending_outputs(state)
    write_json(state_file(run_dir), state)
    print(json.dumps(existing, indent=2, ensure_ascii=False))
    return 0


def cmd_register_image_batch(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    records = image_batch_records(args, run_dir, state)
    state["last_user_request"] = args.source_user_request or state.get("last_user_request")
    state["previous_image_only_output_recording_status"] = "recorded"
    state["previous_image_only_plus_prompt_output_recording_status"] = "recorded"
    state["image_output_registration_status"] = "copied_and_registered"
    state["generated_image_default_locations_to_register"] = []
    state["last_registered_image_batch"] = {
        "batch_id": args.batch_id,
        "step": args.step,
        "artifact_ids": [record["artifact_id"] for record in records],
        "output_dir": normalize_relative_path(args.output_dir),
    }
    state["updated_at"] = utc_now()
    if args.step in TARGET_RASTER_IMAGE_STEPS:
        substages_write_candidate_status_files(run_dir, args.step, state)
    refresh_pending_outputs(state)
    write_json(state_file(run_dir), state)
    print(json.dumps(records, indent=2, ensure_ascii=False))
    return 0


def cmd_record_image_generation(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    event = image_generation_event(args, run_dir, state=state)
    state.setdefault("image_generation_events", []).append(event)
    state["previous_image_only_output_recording_status"] = "state_recorded"
    state["previous_image_only_plus_prompt_output_recording_status"] = "state_recorded"
    state["image_generation_state_update_status"] = "auto_updated_project_state_json_only"
    state["image_output_registration_status"] = "pending_explicit_copy"
    state["generated_image_default_locations_to_register"] = event["generated_paths"]
    state["last_image_generation_event"] = {
        "event_id": event["event_id"],
        "batch_id": event["batch_id"],
        "step": event["step"],
        "generator": event["generator"],
        "generated_relative_path_count": len(event["generated_paths"]),
        "omitted_generated_path_count": event["omitted_generated_path_count"],
        "reference_image_path_count": len(event.get("reference_image_paths") or []),
        "reference_image_input_status": event.get("reference_image_input_status"),
        "generated_path_mode": event["generated_path_mode"],
        "generated_path_recording_status": event["generated_path_recording_status"],
        "canonical_copy_status": event["canonical_copy_status"],
    }
    state["last_user_request"] = args.source_user_request or state.get("last_user_request")
    state["updated_at"] = utc_now()
    write_json(state_file(run_dir), state)
    print(json.dumps(event, indent=2, ensure_ascii=False))
    return 0


def cmd_plan_substages(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    manifest = substages_plan_substages(args, run_dir, state)
    write_json(state_file(run_dir), state)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def cmd_scan_substages(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    report = substages_scan_substages(args, run_dir, state)
    write_json(state_file(run_dir), state)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_recommend_next_action(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    report = substages_recommend_next_action(args, run_dir, state)
    write_json(state_file(run_dir), state)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_mark_substage(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    row = substages_mark_substage(args, run_dir, state)
    write_json(state_file(run_dir), state)
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


def cmd_mark_candidate(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    row = substages_mark_candidate(args, run_dir, state)
    write_json(state_file(run_dir), state)
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


def cmd_reset_candidate(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    row = substages_reset_candidate(args, run_dir, state)
    write_json(state_file(run_dir), state)
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


def cmd_create_checkpoint(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    bundle = substages_create_checkpoint(args, run_dir, state)
    write_json(state_file(run_dir), state)
    print(json.dumps(bundle, indent=2, ensure_ascii=False))
    return 0


def cmd_write_guidance(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    row = guidance_write_guidance(args, run_dir, state)
    write_json(state_file(run_dir), state)
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


def cmd_register_reference_images(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    current_step_before = state.get("current_step", "S0-PAPER-FOUNDATION")
    records = preference_reference_records(args, run_dir)
    ref_records = state.setdefault("user_preference_reference_images", [])
    for record in records:
        upsert_list_record(ref_records, "reference_id", record["reference_id"], record)
        upsert_artifact_record(
            state,
            {
                "artifact_id": record["reference_id"],
                "step": "S0-PAPER-FOUNDATION",
                "kind": "preference-reference-image",
                "relative_path": record["relative_path"],
                "summary": record["summary"],
                "tags": record["tags"],
                "status": record["status"],
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
                "content_hash": record["content_hash"],
                "source_user_request": record["source_user_request"],
            },
        )
    profile = state.setdefault("user_preference_profile", {})
    profile["status"] = "analysis_pending" if records else profile.get("status", "none")
    profile["reference_image_count"] = len(state.get("user_preference_reference_images", []))
    profile.setdefault("analysis_artifact", PREFERENCE_ANALYSIS_PATH)
    profile["analysis_dimensions_source"] = "references/preference-reference-transfer-policy.md"
    profile["default_s2_sketch_count"] = 4
    profile["default_s5_candidate_count"] = 2
    profile["max_total_candidate_count"] = 4
    profile["first_round_default_style_id"] = FIRST_ROUND_DEFAULT_STYLE_ID
    profile["first_round_style_options"] = FIRST_ROUND_STYLE_OPTIONS
    profile["first_round_style_user_reminder"] = FIRST_ROUND_STYLE_USER_REMINDER
    profile["s1_to_s2_style_options_reminder"] = S1_TO_S2_STYLE_OPTIONS_REMINDER
    profile["second_round_optional_style_options"] = SECOND_ROUND_STYLE_OPTIONS
    profile["second_round_style_user_reminder"] = SECOND_ROUND_STYLE_USER_REMINDER
    profile["style_preference_scope_policy"] = (
        "User-uploaded style preference references are valid only for S1-FIGURE-STRATEGY "
        "figure-type and reader-effect suggestions. They must not automatically bias S2/S5."
    )
    profile["candidate_mix_policy"] = (
        "S2-SKETCH-EXPLORE generates exactly 4 first-round candidates from C01-C04 prompt packages, with formal_publication_schematic as the first-round surface style unless the user explicitly overrides or cancels it in the S1 request before S1 finalizes S2 prompt packages; "
        "S5-CANDIDATE-IMAGE generates exactly 2 terminal formal candidates from F01-F02 prompt packages. "
        "S1/S4 prompt packages must keep algorithm/model/framework figures compact-balanced, centered on the primary method mechanism, and free of oversized empty/context areas unless a source-grounded physical-layout exception is recorded."
    )
    state.setdefault("startup_questions", {}).setdefault("preference_reference_diagrams", {})["status"] = "provided"
    if current_step_before not in {"S0-PAPER-FOUNDATION", "S1-FIGURE-STRATEGY"}:
        cleanup_event = apply_step_cleanup(
            run_dir=run_dir,
            state=state,
            target_step="S1-FIGURE-STRATEGY",
            reason=(
                "late_preference_reference_images_registered; workflow returns to S1-FIGURE-STRATEGY for material rereading "
                "and preference-envelope analysis before continuing"
            ),
            source_user_request=args.source_user_request,
            dry_run=False,
            persist_path=state_file(run_dir),
        )
        state["last_preference_reference_cleanup_event_id"] = cleanup_event["event_id"]
        state["next_recommended_action"] = "S1-FIGURE-STRATEGY material close reading plus figure-type demand diagnosis with the updated preference references"
        state["late_preference_reference_policy_triggered"] = True
    state["last_user_request"] = args.source_user_request or state.get("last_user_request")
    state["updated_at"] = utc_now()
    refresh_pending_outputs(state)
    write_json(state_file(run_dir), state)
    print(json.dumps(records, indent=2, ensure_ascii=False))
    return 0


def cmd_set_runtime_config(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    image_generation_route = infer_image_generation_route(args.environment, args.image_generation_route)
    config = {
        "environment": args.environment,
        "image_generation_route": image_generation_route,
        "image_generation_note": args.image_generation_note or default_image_generation_note(args.environment),
        "runtime_environment_note": runtime_environment_note(args.environment),
        "updated_at": utc_now(),
    }
    state["runtime_environment"] = config
    state.setdefault("startup_questions", {}).setdefault("runtime_environment", {})["status"] = "configured"
    state["last_user_request"] = args.source_user_request or state.get("last_user_request")
    state["updated_at"] = utc_now()
    write_json(state_file(run_dir), state)
    print(json.dumps(config, indent=2, ensure_ascii=False))
    return 0


def cmd_resume(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    if args.json:
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return 0
    print(f"project_id: {state.get('project_id')}")
    print(f"current_step: {state.get('current_step')}")
    print(f"state_file: {state.get('state_file')}")
    print(f"artifacts: {len(state.get('artifacts', []))}")
    print(f"pending_outputs: {len(state.get('pending_outputs', []))}")
    print(f"resume: {state.get('resume_instructions')}")
    return 0


def doctor_report(run_dir: Path, state: dict) -> dict:
    ensure_step_runs(state)
    refresh_active_artifact_roles(state)
    errors = validate_state(run_dir, state)
    warnings: list[str] = []
    active_by_role: dict[str, str] = {}
    active_paths: set[str] = set()
    for artifact in state.get("artifacts", []):
        artifact_id = artifact.get("artifact_id", "<missing-id>")
        rel_path = artifact.get("relative_path")
        if not rel_path:
            continue
        try:
            path = safe_join(run_dir, rel_path)
        except StateError as exc:
            errors.append(str(exc))
            continue
        step = artifact.get("step")
        try:
            artifact_epoch = int(artifact.get("step_epoch") or 0)
        except (TypeError, ValueError):
            artifact_epoch = -1
        current_epoch = 0
        if step:
            current_epoch = int(ensure_step_runs(state).get(step, {}).get("epoch") or 0)
        if step and artifact.get("step_epoch") is not None and artifact_epoch < current_epoch:
            if artifact.get("status") not in {"deleted", "unavailable_after_step_rewind_cleanup", "stale"}:
                warnings.append(
                    f"artifact {artifact_id} is from stale {step} epoch {artifact_epoch}; active epoch is {current_epoch}"
                )
        if is_active_artifact(state, artifact):
            active_paths.add(rel_path)
            if not path.exists():
                errors.append(f"active artifact file is missing: {artifact_id} -> {rel_path}")
            elif artifact.get("content_hash"):
                actual_hash = sha256_file(path)
                if actual_hash and actual_hash != artifact.get("content_hash"):
                    warnings.append(f"active artifact hash changed outside the index: {artifact_id} -> {rel_path}")
            role = artifact.get("artifact_role")
            if role:
                if role in active_by_role:
                    warnings.append(
                        f"multiple active artifacts claim role {role}: {active_by_role[role]} and {artifact_id}"
                    )
                active_by_role[role] = artifact_id
        elif artifact.get("availability") == "file_deleted" and path.exists():
            warnings.append(f"artifact marked file_deleted but file still exists: {artifact_id} -> {rel_path}")

    for pending in PENDING_CANONICAL_OUTPUTS:
        rel_path = pending.get("relative_path")
        if rel_path and rel_path not in active_paths:
            try:
                pending_path = safe_join(run_dir, rel_path)
            except StateError as exc:
                errors.append(str(exc))
                continue
            if pending_path.exists():
                warnings.append(f"canonical file exists but is not active in index: {rel_path}")

    incomplete_events = [
        event.get("event_id")
        for event in state.get("step_rewind_cleanup_policy", {}).get("cleanup_events", [])
        if event.get("status") in {"planned", "running"}
    ]
    if incomplete_events:
        warnings.append(
            "cleanup event is incomplete; run resume-cleanup before continuing: "
            + ", ".join(str(event_id) for event_id in incomplete_events)
        )
    return {
        "ok": not errors and not warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "current_step": state.get("current_step"),
        "active_artifact_count": len(active_paths),
        "pending_output_count": len(state.get("pending_outputs", [])),
        "active_artifact_roles": dict(sorted(state.get("active_artifact_roles", {}).items())),
    }


def cmd_doctor(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    report = doctor_report(run_dir, state)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"ok: {report['ok']}")
        print(f"errors: {report['error_count']}")
        for error in report["errors"]:
            print(f"ERROR: {error}")
        print(f"warnings: {report['warning_count']}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
        print(f"current_step: {report['current_step']}")
        print(f"active_artifacts: {report['active_artifact_count']}")
        print(f"pending_outputs: {report['pending_output_count']}")
    if args.fail_on_issue and (report["errors"] or report["warnings"]):
        return 1
    return 0


def cmd_validate(args) -> int:
    run_dir = project_dir(args)
    state = load_state(run_dir)
    errors = validate_state(run_dir, state)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=__import__("sys").stderr)
        return 1
    print("state is valid")
    return 0
