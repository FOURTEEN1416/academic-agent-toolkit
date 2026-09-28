"""Project state validation and security checks for v3.2.15f."""

from __future__ import annotations

from typing import Any
from pathlib import Path

from .constants import (
    ARTIFACT_ROLES,
    CANDIDATE_STATUS_VALUES,
    FORBIDDEN_TARGET_IMAGE_EXTS,
    FORBIDDEN_TARGET_IMAGE_KINDS,
    GUIDANCE_STEPS,
    IMAGE_GENERATION_ROUTES,
    RUNTIME_ENVIRONMENTS,
    SCHEMA_VERSION,
    SECRET_KEY_RE,
    S5_REFERENCE_IMAGE_ROW_FIELD,
    SKILL_NAME,
    TARGET_RASTER_IMAGE_EXTS,
    TARGET_RASTER_IMAGE_STEPS,
    TARGET_RASTER_REFERENCE_ROLES,
    SUBSTAGE_STATUS_VALUES,
    SUBSTAGE_STEPS,
    WORKFLOW_STEPS,
)
from .errors import StateError
from .paths import normalize_relative_path, safe_join
from .runtime_config import validate_image_generation_route
from .identity import (
    candidate_id_path_segment,
    default_prompt_index_path,
    load_prompt_index,
    normalize_candidate_id,
)


def check_no_secret_keys(value: Any, path: str = "$" ) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if SECRET_KEY_RE.search(str(key)):
                errors.append(f"secret-like key is not allowed in state: {child_path}")
            errors.extend(check_no_secret_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(check_no_secret_keys(child, f"{path}[{index}]"))
    return errors


def validate_relative_path_text(label: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be a non-empty relative path string")
        return
    try:
        normalize_relative_path(value)
    except StateError as exc:
        errors.append(f"{label}: {exc}")


def validate_project_run_relative_path(run_dir: Path, label: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be a non-empty project-run-relative path string")
        return
    try:
        if any(char in value for char in "*?[]"):
            normalize_relative_path(value)
            return
        safe_join(run_dir, value)
    except StateError as exc:
        errors.append(f"{label}: {exc}")
    except OSError as exc:
        errors.append(f"{label}: invalid project-run-relative path {value!r}: {exc}")


def path_suffix(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return Path(value).suffix.lower()


def validate_target_raster_artifact(
    label: str,
    rel_path: Any,
    kind: Any,
    artifact_role: Any,
    step: Any,
    errors: list[str],
) -> None:
    suffix = path_suffix(rel_path)
    normalized_kind = str(kind or "").lower()
    if artifact_role in TARGET_RASTER_REFERENCE_ROLES:
        if normalized_kind != "image":
            errors.append(f"{label} role {artifact_role} must have kind=image, not {kind!r}")
        if suffix not in TARGET_RASTER_IMAGE_EXTS:
            errors.append(
                f"{label} role {artifact_role} must point to a generated raster image "
                f"({', '.join(sorted(TARGET_RASTER_IMAGE_EXTS))}), not {rel_path!r}"
            )
    if step in TARGET_RASTER_IMAGE_STEPS:
        if normalized_kind in FORBIDDEN_TARGET_IMAGE_KINDS:
            errors.append(
                f"{label} in {step} uses forbidden target-image kind {kind!r}; "
                "S2/S5 target-paper images must be generated raster images, not SVG/HTML/Mermaid/canvas/PPT/PDF substitutes."
            )
        if suffix in FORBIDDEN_TARGET_IMAGE_EXTS:
            errors.append(
                f"{label} in {step} uses forbidden target-image path {rel_path!r}; "
                "SVG/PPT editability is outside the target-image generation workflow."
            )



def candidate_registry_key_for_step(step: str) -> str | None:
    if step == "S2-SKETCH-EXPLORE":
        return "s2_sketches"
    if step == "S5-CANDIDATE-IMAGE":
        return "s5_candidates"
    return None


def validate_candidate_id_path_match(label: str, candidate_id: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        return
    try:
        segment = candidate_id_path_segment(value)
    except StateError as exc:
        errors.append(f"{label}: {exc}")
        return
    if segment is not None and segment != candidate_id:
        errors.append(f"{label}: candidate_id mismatch; row id is {candidate_id!r} but path uses candidates/{segment}/: {value}")


def validate_prompt_index_consistency(run_dir: Path, state: dict[str, Any], step: str, errors: list[str]) -> None:
    rel = default_prompt_index_path(step)
    try:
        path = safe_join(run_dir, rel)
    except StateError as exc:
        errors.append(str(exc))
        return
    if not path.is_file():
        return
    try:
        index = load_prompt_index(run_dir, rel, stage=step, require_prompt_files=True)
    except Exception as exc:  # StateError, JSONDecodeError, OSError
        errors.append(f"prompt-index consistency error for {step}: {exc}")
        return
    prompt_ids = index.get("candidate_ids", [])
    prompt_rows = {row.get("candidate_id"): row for row in index.get("candidates", []) if isinstance(row, dict)}
    if step == "S5-CANDIDATE-IMAGE":
        for cid in prompt_ids:
            row = prompt_rows.get(cid) or {}
            refs = row.get(S5_REFERENCE_IMAGE_ROW_FIELD)
            if not isinstance(refs, list) or not refs:
                errors.append(f"S5 prompt-index row {cid} must include non-empty {S5_REFERENCE_IMAGE_ROW_FIELD} with registered S2 raster references")
                continue
            for ref_index, ref in enumerate(refs, start=1):
                validate_project_run_relative_path(run_dir, f"S5 prompt-index {cid}.{S5_REFERENCE_IMAGE_ROW_FIELD}[{ref_index}]", ref, errors)
                if path_suffix(ref) not in TARGET_RASTER_IMAGE_EXTS:
                    errors.append(f"S5 prompt-index {cid}.{S5_REFERENCE_IMAGE_ROW_FIELD}[{ref_index}] must be a raster image path: {ref!r}")
                else:
                    try:
                        if not safe_join(run_dir, ref).is_file():
                            errors.append(f"S5 prompt-index {cid}.{S5_REFERENCE_IMAGE_ROW_FIELD}[{ref_index}] does not exist: {ref}")
                    except StateError as exc:
                        errors.append(str(exc))
    registry_key = candidate_registry_key_for_step(step)
    if registry_key:
        registry = state.get("candidate_run_registry", {}).get(registry_key, {})
        if isinstance(registry, dict) and registry:
            registry_ids = list(registry.keys())
            missing_in_registry = [cid for cid in prompt_ids if cid not in registry]
            extra_registry = [cid for cid in registry_ids if cid not in prompt_ids]
            if missing_in_registry:
                errors.append(f"{registry_key} missing prompt-index candidate ids: {missing_in_registry}")
            if extra_registry:
                errors.append(f"{registry_key} contains ids not present in prompt-index: {extra_registry}")
            for cid, row in registry.items():
                if cid not in prompt_rows or not isinstance(row, dict):
                    continue
                prompt_row = prompt_rows[cid]
                for field in ("prompt_path", "target_image_path"):
                    if row.get(field) and prompt_row.get(field) and normalize_relative_path(row.get(field)) != normalize_relative_path(prompt_row.get(field)):
                        errors.append(f"{registry_key}.{cid}.{field} does not match prompt-index {field}: {row.get(field)} != {prompt_row.get(field)}")
                active = row.get("active_image_path")
                target = prompt_row.get("target_image_path")
                if active and target and normalize_relative_path(active) != normalize_relative_path(target):
                    errors.append(f"{registry_key}.{cid}.active_image_path does not match prompt-index target_image_path: {active} != {target}")
    manifest_path = path.parent / "stage-manifest.json"
    if manifest_path.is_file():
        try:
            import json
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            manifest_ids = manifest.get("candidate_ids", []) if isinstance(manifest, dict) else []
            if manifest_ids and manifest_ids != prompt_ids:
                errors.append(f"{step} stage-manifest candidate_ids do not match prompt-index order: manifest={manifest_ids}, prompt-index={prompt_ids}")
            for row in (manifest.get("substage_plan", []) if isinstance(manifest, dict) else []):
                if not isinstance(row, dict):
                    continue
                for cid in row.get("candidate_ids", []):
                    if cid not in prompt_ids:
                        errors.append(f"{step} substage {row.get('substage_id')} has candidate_id not in prompt-index: {cid}")
        except Exception as exc:
            errors.append(f"{step} stage-manifest candidate id audit failed: {exc}")


def validate_state(run_dir: Path, state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    known_steps = [step for step, _, _, _ in WORKFLOW_STEPS]
    if state.get("project_state_schema_version") != SCHEMA_VERSION:
        errors.append("unexpected or missing project_state_schema_version")
    if state.get("skill_name") != SKILL_NAME:
        errors.append("unexpected or missing skill_name")
    if not state.get("project_id"):
        errors.append("missing project_id")
    if state.get("current_step") not in known_steps:
        errors.append("current_step is not a known workflow step")
    if state.get("terminal_step") not in {None, "S5-CANDIDATE-IMAGE"}:
        errors.append("terminal_step must be S5-CANDIDATE-IMAGE in v3.2.15f")
    if "final_verdict" in state:
        errors.append("assistant workflow state keys after S5 are not valid in v3.2.15f")
    errors.extend(check_no_secret_keys(state))
    validate_relative_path_text("output_root", state.get("output_root"), errors)
    validate_project_run_relative_path(run_dir, "state_file", state.get("state_file"), errors)

    for index, step_state in enumerate(state.get("workflow_plan", [])):
        step = step_state.get("step")
        if step not in known_steps:
            errors.append(f"workflow_plan[{index}].step is not valid in v3.2.15f: {step}")
        validate_project_run_relative_path(run_dir, f"workflow_plan[{index}].output_dir", step_state.get("output_dir"), errors)
        validate_project_run_relative_path(run_dir, f"workflow_plan[{index}].canonical_output", step_state.get("canonical_output"), errors)

    for index, pending in enumerate(state.get("pending_outputs", [])):
        validate_project_run_relative_path(run_dir, f"pending_outputs[{index}].relative_path", pending.get("relative_path"), errors)
        if pending.get("artifact_role") and pending.get("artifact_role") not in ARTIFACT_ROLES:
            errors.append(f"pending_outputs[{index}].artifact_role is not known")
        if pending.get("artifact_role") in TARGET_RASTER_REFERENCE_ROLES:
            suffix = path_suffix(pending.get("relative_path"))
            if suffix not in TARGET_RASTER_IMAGE_EXTS:
                errors.append(
                    f"pending_outputs[{index}] for {pending.get('artifact_role')} must use a raster image path, not {pending.get('relative_path')!r}"
                )

    for role_id, role in state.get("artifact_role_registry", {}).items():
        if role_id not in ARTIFACT_ROLES:
            errors.append(f"artifact_role_registry contains unknown role: {role_id}")
        validate_project_run_relative_path(run_dir, f"artifact_role_registry.{role_id}.relative_path", role.get("relative_path"), errors)
        if role.get("step") not in known_steps:
            errors.append(f"artifact_role_registry.{role_id}.step is not a known workflow step")
        validate_target_raster_artifact(
            f"artifact_role_registry.{role_id}", role.get("relative_path"), role.get("kind"), role_id, role.get("step"), errors
        )

    for step, run in state.get("step_runs", {}).items():
        if step not in known_steps:
            errors.append(f"step_runs contains unknown step: {step}")
            continue
        try:
            epoch = int(run.get("epoch"))
            if epoch < 0:
                errors.append(f"step_runs.{step}.epoch must be non-negative")
        except (TypeError, ValueError):
            errors.append(f"step_runs.{step}.epoch must be an integer")
        validate_project_run_relative_path(run_dir, f"step_runs.{step}.output_dir", run.get("output_dir"), errors)

    if state.get("preference_reference_root") is not None:
        validate_project_run_relative_path(run_dir, "preference_reference_root", state.get("preference_reference_root"), errors)
    preference_profile = state.get("user_preference_profile")
    if isinstance(preference_profile, dict) and preference_profile.get("analysis_artifact"):
        validate_project_run_relative_path(run_dir, "user_preference_profile.analysis_artifact", preference_profile.get("analysis_artifact"), errors)

    runtime_environment = state.get("runtime_environment")
    if isinstance(runtime_environment, dict):
        environment = runtime_environment.get("environment")
        image_route = runtime_environment.get("image_generation_route")
        if environment not in RUNTIME_ENVIRONMENTS:
            errors.append(f"runtime_environment.environment must be one of {sorted(RUNTIME_ENVIRONMENTS)}")
        if image_route not in IMAGE_GENERATION_ROUTES:
            errors.append(f"runtime_environment.image_generation_route must be one of {sorted(IMAGE_GENERATION_ROUTES)}")

    for index, reference in enumerate(state.get("user_preference_reference_images", [])):
        validate_project_run_relative_path(run_dir, f"user_preference_reference_images[{index}].relative_path", reference.get("relative_path"), errors)

    for event_index, event in enumerate(state.get("image_generation_events", [])):
        if event.get("generated_path_mode") not in {None, "project_run_relative"}:
            errors.append(f"image_generation_events[{event_index}].generated_path_mode must be project_run_relative")
        if event.get("step") in TARGET_RASTER_IMAGE_STEPS:
            try:
                env = event.get("environment")
                if not env and isinstance(runtime_environment, dict):
                    env = runtime_environment.get("environment")
                route_guard = validate_image_generation_route(
                    environment=env,
                    generator=event.get("generator"),
                    approved_api_name=event.get("approved_api_name"),
                    route_unavailable_reason=event.get("route_unavailable_reason"),
                )
                if event.get("generator") != route_guard["generator"]:
                    errors.append(
                        f"image_generation_events[{event_index}].generator should be canonical {route_guard['generator']!r}; found noncanonical/alias value {event.get('generator')!r}"
                    )
            except StateError as exc:
                errors.append(f"image_generation_events[{event_index}].route_guard: {exc}")
            if not event.get("generated_paths"):
                errors.append(f"image_generation_events[{event_index}] must record at least one project-run-relative generated raster path for target-paper images")
            if event.get("omitted_generated_path_count"):
                errors.append(f"image_generation_events[{event_index}] cannot omit external/unsafe generated paths for target-paper images")
        for path_index, generated_path in enumerate(event.get("generated_paths", [])):
            validate_project_run_relative_path(run_dir, f"image_generation_events[{event_index}].generated_paths[{path_index}]", generated_path, errors)
            if event.get("step") in TARGET_RASTER_IMAGE_STEPS and path_suffix(generated_path) not in TARGET_RASTER_IMAGE_EXTS:
                errors.append(f"image_generation_events[{event_index}].generated_paths[{path_index}] must be a generated raster image path, not {generated_path!r}")
        for ref_index, ref_path in enumerate(event.get("reference_image_paths", []) or []):
            validate_project_run_relative_path(run_dir, f"image_generation_events[{event_index}].reference_image_paths[{ref_index}]", ref_path, errors)
            if path_suffix(ref_path) not in TARGET_RASTER_IMAGE_EXTS:
                errors.append(f"image_generation_events[{event_index}].reference_image_paths[{ref_index}] must be a raster image path, not {ref_path!r}")
            else:
                try:
                    if not safe_join(run_dir, ref_path).is_file():
                        errors.append(f"image_generation_events[{event_index}].reference_image_paths[{ref_index}] does not exist: {ref_path}")
                except StateError as exc:
                    errors.append(str(exc))
        if event.get("reference_image_input_status") not in {None, "supplied_to_generator", "ignored_unsupported", "not_requested"}:
            errors.append(f"image_generation_events[{event_index}].reference_image_input_status is invalid")
        candidate_outputs = event.get("candidate_outputs")
        if isinstance(candidate_outputs, dict):
            for cid, rel in candidate_outputs.items():
                try:
                    canonical_cid = normalize_candidate_id(cid, label=f"image_generation_events[{event_index}].candidate_outputs key")
                    validate_project_run_relative_path(run_dir, f"image_generation_events[{event_index}].candidate_outputs.{cid}", rel, errors)
                    validate_candidate_id_path_match(f"image_generation_events[{event_index}].candidate_outputs.{cid}", canonical_cid, rel, errors)
                except StateError as exc:
                    errors.append(str(exc))

    for stage, substages in state.get("substage_runs", {}).items():
        if stage not in SUBSTAGE_STEPS:
            errors.append(f"substage_runs contains unsupported stage: {stage}")
            continue
        if not isinstance(substages, dict):
            errors.append(f"substage_runs.{stage} must be an object")
            continue
        for substage_id, substage in substages.items():
            if substage.get("status") not in SUBSTAGE_STATUS_VALUES:
                errors.append(f"substage_runs.{stage}.{substage_id}.status is invalid")
            if substage.get("stage") not in {None, stage}:
                errors.append(f"substage_runs.{stage}.{substage_id}.stage must match its parent stage")
            if substage.get("mode") not in {None, "IMAGE_GENERATE"}:
                errors.append(f"substage_runs.{stage}.{substage_id}.mode must be IMAGE_GENERATE in v3.2.15f")

    registry = state.get("candidate_run_registry", {})
    for registry_key in ("s2_sketches", "s5_candidates"):
        candidates = registry.get(registry_key, {})
        if not isinstance(candidates, dict):
            errors.append(f"candidate_run_registry.{registry_key} must be an object")
            continue
        for candidate_id, candidate in candidates.items():
            try:
                canonical_candidate_id = normalize_candidate_id(candidate_id, label=f"candidate_run_registry.{registry_key} key")
            except StateError as exc:
                errors.append(str(exc))
                canonical_candidate_id = str(candidate_id)
            if candidate.get("candidate_id") and candidate.get("candidate_id") != canonical_candidate_id:
                errors.append(f"candidate_run_registry.{registry_key}.{candidate_id}.candidate_id does not match registry key")
            if candidate.get("status") not in CANDIDATE_STATUS_VALUES:
                errors.append(f"candidate_run_registry.{registry_key}.{candidate_id}.status is invalid")
            for field in ("candidate_dir", "prompt_path", "target_image_path", "active_image_path", "active_audit_json", "active_audit_md", "status_path"):
                if candidate.get(field):
                    validate_project_run_relative_path(run_dir, f"candidate_run_registry.{registry_key}.{candidate_id}.{field}", candidate.get(field), errors)
                    validate_candidate_id_path_match(f"candidate_run_registry.{registry_key}.{candidate_id}.{field}", canonical_candidate_id, candidate.get(field), errors)
            if candidate.get("active_image_path") and path_suffix(candidate.get("active_image_path")) not in TARGET_RASTER_IMAGE_EXTS:
                errors.append(f"candidate_run_registry.{registry_key}.{candidate_id}.active_image_path must be a raster image path")
            if candidate.get("target_image_path") and path_suffix(candidate.get("target_image_path")) not in TARGET_RASTER_IMAGE_EXTS:
                errors.append(f"candidate_run_registry.{registry_key}.{candidate_id}.target_image_path must be a raster image path")
            for ref_index, ref_path in enumerate(candidate.get(S5_REFERENCE_IMAGE_ROW_FIELD, []) or []):
                validate_project_run_relative_path(run_dir, f"candidate_run_registry.{registry_key}.{candidate_id}.{S5_REFERENCE_IMAGE_ROW_FIELD}[{ref_index}]", ref_path, errors)
                if path_suffix(ref_path) not in TARGET_RASTER_IMAGE_EXTS:
                    errors.append(f"candidate_run_registry.{registry_key}.{candidate_id}.{S5_REFERENCE_IMAGE_ROW_FIELD}[{ref_index}] must be a raster image path")

    for bundle_index, bundle in enumerate(state.get("checkpoint_bundles", [])):
        if bundle.get("relative_path"):
            validate_project_run_relative_path(run_dir, f"checkpoint_bundles[{bundle_index}].relative_path", bundle.get("relative_path"), errors)

    for step, guidance_rows in state.get("substage_guidance_registry", {}).items():
        if step not in GUIDANCE_STEPS:
            errors.append(f"substage_guidance_registry contains unsupported step: {step}")
            continue
        if not isinstance(guidance_rows, dict):
            errors.append(f"substage_guidance_registry.{step} must be an object")
            continue
        for guide_id, guide in guidance_rows.items():
            if guide.get("relative_path"):
                validate_project_run_relative_path(run_dir, f"substage_guidance_registry.{step}.{guide_id}.relative_path", guide.get("relative_path"), errors)
            if guide.get("checkpoint_path"):
                validate_project_run_relative_path(run_dir, f"substage_guidance_registry.{step}.{guide_id}.checkpoint_path", guide.get("checkpoint_path"), errors)

    for step, prompt in state.get("next_prompt_registry", {}).items():
        if step not in GUIDANCE_STEPS:
            errors.append(f"next_prompt_registry contains unsupported step: {step}")
            continue
        if isinstance(prompt, dict) and prompt.get("relative_path"):
            validate_project_run_relative_path(run_dir, f"next_prompt_registry.{step}.relative_path", prompt.get("relative_path"), errors)

    for prompt_step in TARGET_RASTER_IMAGE_STEPS:
        validate_prompt_index_consistency(run_dir, state, prompt_step, errors)

    seen_ids: set[str] = set()
    for artifact in state.get("artifacts", []):
        artifact_id = artifact.get("artifact_id")
        if not artifact_id:
            errors.append("artifact missing artifact_id")
        elif artifact_id in seen_ids:
            errors.append(f"duplicate artifact_id: {artifact_id}")
        else:
            seen_ids.add(artifact_id)
        rel_path = artifact.get("relative_path")
        if not rel_path:
            errors.append(f"artifact {artifact_id or '<unknown>'} missing relative_path")
            continue
        try:
            safe_join(run_dir, rel_path)
        except StateError as exc:
            errors.append(str(exc))
        artifact_role = artifact.get("artifact_role")
        if artifact_role and artifact_role not in ARTIFACT_ROLES:
            errors.append(f"artifact {artifact_id or '<unknown>'} has unknown artifact_role: {artifact_role}")
        validate_target_raster_artifact(f"artifact {artifact_id or '<unknown>'}", rel_path, artifact.get("kind"), artifact_role, artifact.get("step"), errors)
        artifact_candidate_id = artifact.get("candidate_id")
        if artifact_candidate_id:
            try:
                artifact_candidate_id = normalize_candidate_id(artifact_candidate_id, label=f"artifact {artifact_id or '<unknown>'}.candidate_id")
                validate_candidate_id_path_match(f"artifact {artifact_id or '<unknown>'}.relative_path", artifact_candidate_id, rel_path, errors)
            except StateError as exc:
                errors.append(str(exc))
        if artifact.get("step") in TARGET_RASTER_IMAGE_STEPS and str(artifact.get("kind") or "").lower() == "image" and path_suffix(rel_path) in TARGET_RASTER_IMAGE_EXTS:
            source_roles = artifact.get("source_artifact_roles") or []
            event_id = artifact.get("image_generation_event_id")
            if not source_roles and not event_id:
                errors.append(f"artifact {artifact_id or '<unknown>'} is a target-paper raster image without image_generation_event_id provenance")
        if artifact.get("step_epoch") is not None:
            try:
                if int(artifact.get("step_epoch")) < 0:
                    errors.append(f"artifact {artifact_id or '<unknown>'} has negative step_epoch")
            except (TypeError, ValueError):
                errors.append(f"artifact {artifact_id or '<unknown>'} step_epoch must be an integer")
    return errors
