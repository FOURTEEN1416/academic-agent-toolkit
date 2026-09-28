"""State schema defaults and workflow state construction for v3.2.15f."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import (
    ARTIFACT_ROLES,
    CANONICAL_OUTPUTS,
    DEFAULT_ROOT,
    DEFAULT_NEXT_STEP_BY_STEP,
    FORBIDDEN_TARGET_IMAGE_EXTS,
    FORBIDDEN_TARGET_IMAGE_KINDS,
    PENDING_CANONICAL_OUTPUTS,
    PREFERENCE_ANALYSIS_PATH,
    PREFERENCE_REFERENCE_ROOT,
    SCHEMA_VERSION,
    SKILL_NAME,
    SKILL_VERSION,
    STATE_RELATIVE_PATH,
    STEP_CLEANUP_EXTRA_DIRS,
    STEP_SEQUENCE,
    TARGET_RASTER_IMAGE_EXTS,
    TARGET_RASTER_IMAGE_STEPS,
    TARGET_RASTER_REFERENCE_ROLES,
    TEXT_REPLY_STEP_BANNER_TEMPLATE,
    WORKFLOW_STEPS,
    ATLAS_DISPLAY_POLICY,
    ATLAS_MANIFEST_PATH,
    ATLAS_BOARD_ROOT,
    ATLAS_BOARD_IDS,
    CHATGPT_WEB_IMAGE_CHUNK_LIMIT,
    CHATGPT_WEB_RECOMMENDED_IMAGE_CHUNK_SIZE,
    CODEX_IMAGE_CHUNK_LIMIT,
    DEFAULT_CANDIDATE_COUNT_BY_STEP,
    GUIDANCE_STEPS,
    MAX_CANDIDATE_COUNT_BY_STEP,
    FIRST_ROUND_DEFAULT_STYLE_ID,
    FIRST_ROUND_STYLE_OPTIONS,
    FIRST_ROUND_STYLE_USER_REMINDER,
    S1_TO_S2_STYLE_OPTIONS_REMINDER,
    SECOND_ROUND_STYLE_OPTIONS,
    SECOND_ROUND_STYLE_USER_REMINDER,
    S5_REFERENCE_IMAGE_INPUT_POLICY,
    S0_SEMANTIC_PRECISION_POLICY,
)
from .paths import normalize_relative_path, safe_join, utc_now


def workflow_state(current_step: str = "S0-PAPER-FOUNDATION") -> list[dict[str, Any]]:
    rows = []
    step_order = [step for step, _, _, _ in WORKFLOW_STEPS]
    current_index = step_order.index(current_step)
    for index, (step, mode, purpose, output_dir) in enumerate(WORKFLOW_STEPS):
        if step == current_step:
            status = "in_progress"
        elif index < current_index:
            status = "completed"
        else:
            status = "pending"
        rows.append(
            {
                "step": step,
                "mode": mode,
                "purpose": purpose,
                "output_dir": output_dir,
                "canonical_output": CANONICAL_OUTPUTS[step],
                "default_next_step": DEFAULT_NEXT_STEP_BY_STEP[step],
                "status": status,
            }
        )
    return rows


def step_attempt_id(step: str, epoch: int) -> str:
    normalized_step = step.lower().replace("-", "_")
    return f"{normalized_step}-e{epoch:04d}"


def initial_step_runs(current_step: str, now: str) -> dict[str, dict[str, Any]]:
    current_index = [step for step, _, _, _ in WORKFLOW_STEPS].index(current_step)
    rows: dict[str, dict[str, Any]] = {}
    for index, (step, _, _, output_dir) in enumerate(WORKFLOW_STEPS):
        epoch = 1 if step == current_step else 0
        if step == current_step:
            status = "in_progress"
        elif index < current_index:
            status = "completed"
        else:
            status = "pending"
        rows[step] = {
            "step": step,
            "epoch": epoch,
            "attempt_id": step_attempt_id(step, epoch),
            "status": status,
            "output_dir": output_dir,
            "started_at": now if status == "in_progress" else None,
            "updated_at": now,
        }
    return rows


def ensure_step_runs(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    now = utc_now()
    current_step = state.get("current_step", "S0-PAPER-FOUNDATION")
    step_runs = state.setdefault("step_runs", {})
    for step, _, _, output_dir in WORKFLOW_STEPS:
        row = step_runs.setdefault(step, {})
        row.setdefault("step", step)
        row.setdefault("output_dir", output_dir)
        row.setdefault("epoch", 1 if step == current_step else 0)
        row.setdefault("attempt_id", step_attempt_id(step, int(row.get("epoch") or 0)))
        row.setdefault("status", "in_progress" if step == current_step else "pending")
        row.setdefault("started_at", now if step == current_step else None)
        row.setdefault("updated_at", now)
    for stale_step in list(step_runs):
        if stale_step not in STEP_SEQUENCE:
            step_runs.pop(stale_step, None)
    return step_runs


def current_step_epoch(state: dict[str, Any], step: str) -> int:
    step_runs = ensure_step_runs(state)
    return int(step_runs.get(step, {}).get("epoch") or 0)


def mark_step_run_in_progress(state: dict[str, Any], step: str, bump_if_zero: bool = True) -> dict[str, Any]:
    step_runs = ensure_step_runs(state)
    row = step_runs[step]
    epoch = int(row.get("epoch") or 0)
    now = utc_now()
    if bump_if_zero and epoch == 0:
        epoch = 1
        row["epoch"] = epoch
        row["attempt_id"] = step_attempt_id(step, epoch)
        row["started_at"] = now
    row["status"] = "in_progress"
    row["updated_at"] = now
    step_order = [name for name, _, _, _ in WORKFLOW_STEPS]
    current_index = step_order.index(step)
    for other_step, other_row in step_runs.items():
        if other_step == step or other_step not in step_order:
            continue
        other_index = step_order.index(other_step)
        other_epoch = int(other_row.get("epoch") or 0)
        other_row["status"] = "completed" if other_index < current_index and other_epoch > 0 else "pending"
        other_row["updated_at"] = now
    return row


def bump_step_epoch(state: dict[str, Any], step: str, status: str) -> dict[str, Any]:
    step_runs = ensure_step_runs(state)
    row = step_runs[step]
    now = utc_now()
    old_epoch = int(row.get("epoch") or 0)
    new_epoch = old_epoch + 1
    row.update(
        {
            "epoch": new_epoch,
            "attempt_id": step_attempt_id(step, new_epoch),
            "status": status,
            "started_at": now if status == "in_progress" else None,
            "updated_at": now,
        }
    )
    return {
        "step": step,
        "old_epoch": old_epoch,
        "new_epoch": new_epoch,
        "attempt_id": row["attempt_id"],
        "status": status,
    }


def ensure_output_dirs(run_dir: Path) -> None:
    safe_join(run_dir, "state").mkdir(parents=True, exist_ok=True)
    safe_join(run_dir, PREFERENCE_REFERENCE_ROOT).mkdir(parents=True, exist_ok=True)
    for _, _, _, output_dir in WORKFLOW_STEPS:
        safe_join(run_dir, output_dir).mkdir(parents=True, exist_ok=True)
    for extra_dirs in STEP_CLEANUP_EXTRA_DIRS.values():
        for output_dir in extra_dirs:
            safe_join(run_dir, output_dir).mkdir(parents=True, exist_ok=True)


def initial_state(project_id: str, run_dir: Path, title: str | None) -> dict[str, Any]:
    now = utc_now()
    return {
        "project_state_schema_version": SCHEMA_VERSION,
        "skill_name": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "project_id": project_id,
        "project_title": title or project_id,
        "created_at": now,
        "updated_at": now,
        "notes": [],
        "current_step": "S0-PAPER-FOUNDATION",
        "workflow_plan": workflow_state("S0-PAPER-FOUNDATION"),
        "step_sequence": list(STEP_SEQUENCE),
        "default_next_step_by_step": DEFAULT_NEXT_STEP_BY_STEP,
        "terminal_step": "S5-CANDIDATE-IMAGE",
        "terminal_message": "我的任务已经完成，剩下由人类来决策。",
        "step_runs": initial_step_runs("S0-PAPER-FOUNDATION", now),
        "output_root": normalize_relative_path(Path(DEFAULT_ROOT) / project_id),
        "state_file": normalize_relative_path(STATE_RELATIVE_PATH),
        "path_storage_policy": "all stored paths are project-run relative; host-specific absolute paths are not persisted",
        "v3215_terminal_candidate_workflow": {
            "status": "active",
            "rule": "S2 and S5 are image-generation-only public stages. S1 prepares S2 prompt packages, S3 reviews and aggregates S2 outputs, S4 prepares S5 prompt packages, and assistant workflow ends after S5 image generation.",
            "removed_units": [
                "S2 standalone text plan",
                "S2 candidate-level revision loop",
                "S3 aggregate over S2 outputs substage",
                "S5 standalone text plan",
                "S5 text-review substage",
                "S5 candidate-level revision loop",
                "S5 aggregate substage",
                "assistant workflow after S5",
            ],
        },

        "v3215_candidate_id_coherence_policy": {
            "status": "hard_required",
            "source_of_truth": "S1/S4 prompt-index candidates[].candidate_id",
            "rule": "candidate_id must match prompt_path, target_image_path, candidate_run_registry keys, substage candidate_ids, artifact candidate_id fields, active image paths, and checkpoint image inventories. Do not renumber or reinterpret IDs by stage defaults after a prompt-index exists.",
            "s2_default_id_family": "C01-C04 unless a validated prompt-index defines the same four first-round stage candidates",
            "s5_default_id_family": "F01-F02 unless a validated prompt-index defines the same two formal candidate IDs",
            "human_prompt_rule": "Suggested prompts should say '请使用 paper-framework-figure-studio-pro skill' and should not mention zip package names or versioned skill zip files.",
        },
        "s0_semantic_precision_policy": S0_SEMANTIC_PRECISION_POLICY,
        "v3215d_style_combination_palette_policy": {
            "status": "hard_required",
            "s1_style_combination_pool_count": 8,
            "s1_selected_s2_candidate_count": 4,
            "s2_image_count": 4,
            "s4_s5_prompt_candidate_count": 2,
            "s5_image_count": 2,
            "rule": "S1 plans eight complementary style combinations, selects the top four for C01-C04, and records why each selected combination is complementary. S4 prepares only F01-F02. S1/S4 prompts must include human-aesthetic palette fields and reject AI-looking color artifacts.",
            "required_prompt_palette_fields": [
                "palette_strategy",
                "palette_semantic_mapping",
                "palette_anti_ai_artifact_rules",
                "human_aesthetic_rationale",
                "color_accessibility_note",
            ],
        },
        "target_raster_image_generation_policy": {
            "status": "hard_required",
            "rule": "Target-paper sketches and formal candidates must be raster images produced by the runtime-locked image-generation route. SVG/HTML/Mermaid/canvas/PPT/PDF/code-drawn or programmatic-raster substitutes are invalid for target images even when saved as PNG/JPG/WebP.",
            "raster_generation_steps": sorted(TARGET_RASTER_IMAGE_STEPS),
            "raster_reference_roles": sorted(TARGET_RASTER_REFERENCE_ROLES),
            "allowed_generated_image_extensions": sorted(TARGET_RASTER_IMAGE_EXTS),
            "forbidden_target_image_kinds": sorted(FORBIDDEN_TARGET_IMAGE_KINDS),
            "forbidden_target_image_extensions": sorted(FORBIDDEN_TARGET_IMAGE_EXTS),
            "no_fallback_substitute": "If the required route is unavailable, stop and report the limitation instead of fabricating SVG, code-drawn, Python/PIL/Matplotlib/Graphviz/TikZ/Mermaid, canvas screenshot, SVG-to-PNG, PPT/PDF-rendered, or other local raster placeholders.",
            "codex_route_requirement": "In Codex, every S2/S5 target-paper image unit must call image_gen.",
            "chatgpt_web_route_requirement": "In ChatGPT web, every S2/S5 target-paper image unit must use Create Image / ChatGPT Images 2.0.",
            "approved_api_requirement": "A named approved image-generation API is allowed only in runtimes where neither Codex image_gen nor ChatGPT web Create Image is available.",
            "registration_provenance_requirement": "register-image-batch and target-image artifact registration must cite a recorded image_generation_event from the environment-locked route.",
            "direct_delete_policy": "Direct artifact delete is forbidden for active target-paper image artifacts. Mark stale, reset candidate, or use rewind-step cleanup for explicit upstream reruns; preserve provenance records.",
        },
        "paper_framework_non_poster_policy": (
            "This skill is only for research-paper framework/architecture/pipeline/mechanism figures. "
            "It must not produce posters, marketing visuals, cover art, decorative exhibition boards, or PPT-slide content pages."
        ),
        "default_canvas_policy": {
            "default_aspect_ratio": "16:9",
            "user_editable": True,
            "first_reply_disclosure_required": True,
            "applies_to_steps": ["S2-SKETCH-EXPLORE", "S5-CANDIDATE-IMAGE"],
            "user_adjustment_examples": ["4:3", "1:1", "3:2", "double-column landscape", "journal-specified size"],
            "state_recording_policy": "If the user changes the aspect ratio, record the requested ratio in project state and carry it through later image prompts.",
        },
        "default_density_policy": (
            "Default figure density is compact-balanced for algorithm/model/method/framework figures. "
            "S1/S4 prompt preparation must cap repeated dots, samples, rows, entities, legends, distributions, "
            "context panels, empty quadrants, and top-heavy support areas before generation. "
            "The primary method mechanism should occupy the central visual field; move definitions, caveats, dense equations, symbol meanings, and long explanations to surrounding manuscript text handled outside the assistant work after S5."
        ),
        "fixed_candidate_contract_policy": {
            "user_configurable": False,
            "rule": "S2/S5 have no standalone heavy per-image text review or candidate-level revision substages. S1/S4 must still prepare strict paper-grounded prompt contracts, and S3 must review S2 images before direction selection.",
        },
        "strict_source_grounded_modular_prompt_contract_policy": {
            "status": "hard_required",
            "contract": "references/strict-source-grounded-modular-prompt-contract-policy-v3215a.md",
            "supporting_contracts": [
                "references/no-false-relay-data-flow-policy-v3215d.md",
                "references/public-stage-human-wait-barrier-policy-v3215d.md",
                "references/layout-density-mainline-balance-policy-v3215f.md",
            ],
            "applies_to": ["S1-FIGURE-STRATEGY", "S4-CANDIDATE-BRIEF"],
            "max_audit_repair_cycles": 5,
            "required_prompt_records": [
                "s5_reference_image_input_plan",
                "edge_support_ledger",
                "data_consumer_transformer_ledger",
                "false_relay_data_flow_audit",
                "layout_information_density_plan",
                "canvas_area_budget",
                "context_inset_budget",
                "mainline_center_of_gravity_gate",
                "layout_density_audit",
            ],
            "rule": "Every S1/S4 image prompt must include strict source-grounded connector evidence, connector multiplicity/bundling, data consumer/transformer ledger, false relay data-flow audit, edge-label-first variable placement, modular-not-fragmented structure, simple reviewer-recognizable internal motifs, no duplicate workflow/inset, small background context, compact-balanced canvas density, centered mainline visual focus, and no oversized empty/context areas. If blockers remain after five audit/repair cycles, stop before image handoff and write residual risk.",
        },

        "entity_compression_and_navigation_guard_policy": {
            "status": "hard_required",
            "contract": "references/entity-compression-and-active-stage-navigation-guard-policy-v3215a.md",
            "applies_to": ["S1-FIGURE-STRATEGY", "S4-CANDIDATE-BRIEF", "next_prompt_suggestion"],
            "entity_rule": "Repeated entity families default to compact markers around one canonical process unless source evidence justifies distinct branches or explicit comparison.",
            "navigation_rule": "Next-step guidance resolves navigation_state from conversation execution and image-generation events before falling back to checkpoint restore_state.",
        },
        "substage_orchestration_policy": {
            "contract": "references/s2-s5-image-only-terminal-orchestration-policy-v3215.md",
            "text_image_separation_rule": "S2 and S5 only generate images. S1/S4 own prompt preparation; S3 reviews and aggregates S2 outputs; no S5 assistant-side review exists.",
            "image_route_guard": "S2/S5 IMAGE_GENERATE must use Codex image_gen, ChatGPT web Create Image / ChatGPT Images 2.0, or a named approved image-generation API only in other runtimes.",
            "default_required_sequence": "S1 prepares S2 prompts -> S2 generates images -> S3 reviews/aggregates S2 and selects direction -> S4 prepares S5 prompts -> S5 generates images -> END.",
            "s2_review_to_s4_transfer_rule": "S3 records review findings from S2 outputs; S4 transfers useful findings into S5 prompt constraints.",
            "s5_reference_image_input_policy": S5_REFERENCE_IMAGE_INPUT_POLICY,
            "s5_terminal_rule": "After S5 image generation, assistant workflow ends. No next prompt is offered.",
        },
        "workflow_boundary_policy": {
            "step_order": list(STEP_SEQUENCE),
            "terminal_step": "S5-CANDIDATE-IMAGE",
            "terminal_reply": "我的任务已经完成，剩下由人类来决策。",
            "one_public_step_per_user_turn": True,
            "hard_human_wait_barrier": True,
            "barrier_satisfaction_rule": "After S0-S4, the next public stage requires a later explicit user message or a source-allowed explicit skip/default/automation choice recorded before the barrier.",
            "not_barrier_satisfaction": [
                "reviewer_gate",
                "specialist_completion",
                "internal_handoff",
                "checkpoint_success",
                "silent_default",
                "copyable_prompt",
            ],
            "s1_to_s2_rule": "S1 prepares S2 prompts and stops; S2 image generation requires a new explicit user turn.",
            "s4_to_s5_rule": "S4 prepares S5 prompts and stops; S5 image generation requires a new explicit user turn.",
        },
        "style_transfer_policy": {
            "style_preference_scope_policy": "Preference references inform S1 figure-type/reader-effect suggestions and do not automatically force S2/S5 style.",
            "candidate_mix_policy": "S1 first plans eight complementary style-combination proposals, selects only four C01-C04 prompt packages, and S2 generates exactly four first-round candidates. S4 prepares exactly two F01-F02 formal prompt packages, and S5 generates exactly two terminal candidates.",
            "first_round_default_style_id": FIRST_ROUND_DEFAULT_STYLE_ID,
            "first_round_default_style_label_zh": "正式出版风格",
            "first_round_style_options": FIRST_ROUND_STYLE_OPTIONS,
            "first_round_style_user_reminder": FIRST_ROUND_STYLE_USER_REMINDER,
            "s1_to_s2_style_options_reminder": S1_TO_S2_STYLE_OPTIONS_REMINDER,
            "first_round_style_stage_reminder_policy": "S0 must include a compact non-blocking surface-style reminder outside the copyable S1 prompt block; S1 records any explicit surface-style override or default-surface cancellation from the S1 user request; S1-to-S2 must repeat the available first-round surface-style menu as non-copyable prose outside the copyable S2 prompt and must explain that changing the first-round surface after S1 requires rerunning S1 before S2; S2 is image-only and follows the prompt-index.",
            "second_round_optional_style_options": SECOND_ROUND_STYLE_OPTIONS,
            "second_round_style_user_reminder": SECOND_ROUND_STYLE_USER_REMINDER,
        },
        "atlas_display_policy": {
            "board_root": ATLAS_BOARD_ROOT,
            "manifest_path": ATLAS_MANIFEST_PATH,
            "board_ids": list(ATLAS_BOARD_IDS),
            "policy": ATLAS_DISPLAY_POLICY,
        },
        "runtime_environment": {
            "environment": "unknown",
            "image_generation_route": "unknown",
            "note": "set-runtime-config should record chatgpt_web/codex/other before image generation",
        },
        "image_generation_chunk_policy": {
            "chatgpt_web_image_chunk_limit": CHATGPT_WEB_IMAGE_CHUNK_LIMIT,
            "chatgpt_web_recommended_image_chunk_size": CHATGPT_WEB_RECOMMENDED_IMAGE_CHUNK_SIZE,
            "codex_image_chunk_limit": CODEX_IMAGE_CHUNK_LIMIT,
            "default_candidate_count_by_step": DEFAULT_CANDIDATE_COUNT_BY_STEP,
            "max_candidate_count_by_step": MAX_CANDIDATE_COUNT_BY_STEP,
        },
        "artifact_role_registry": ARTIFACT_ROLES,
        "pending_outputs": PENDING_CANONICAL_OUTPUTS,
        "artifacts": [],
        "candidate_run_registry": {"s2_sketches": {}, "s5_candidates": {}},
        "substage_runs": {},
        "substage_guidance_registry": {},
        "next_prompt_registry": {},
        "checkpoint_bundles": [],
        "image_generation_events": [],
        "user_preference_reference_images": [],
        "user_preference_profile": {
            "status": "none",
            "analysis_artifact": PREFERENCE_ANALYSIS_PATH,
            "default_s2_sketch_count": 8,
            "default_s5_candidate_count": 6,
            "max_total_candidate_count": 8,
            "first_round_default_style_id": FIRST_ROUND_DEFAULT_STYLE_ID,
            "first_round_style_options": FIRST_ROUND_STYLE_OPTIONS,
            "first_round_style_user_reminder": FIRST_ROUND_STYLE_USER_REMINDER,
            "s1_to_s2_style_options_reminder": S1_TO_S2_STYLE_OPTIONS_REMINDER,
            "second_round_optional_style_options": SECOND_ROUND_STYLE_OPTIONS,
            "second_round_style_user_reminder": SECOND_ROUND_STYLE_USER_REMINDER,
        },
        "chatgpt_web_text_only_guard": "本轮纯文字：只执行文字、state、manifest、brief、audit、guidance 或 checkpoint 写入；不要生成任何图片。",
        "text_reply_step_banner_template": TEXT_REPLY_STEP_BANNER_TEMPLATE,
        "required_terminal_answer_after_s5": "我的任务已经完成，剩下由人类来决策。",
    }
