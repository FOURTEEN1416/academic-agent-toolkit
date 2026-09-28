#!/usr/bin/env python3
"""Persistent state helper CLI for paper-framework-figure-studio-pro."""

from __future__ import annotations

import argparse
import sys

from figure_studio_core.constants import (
    ARTIFACT_ROLES,
    DEFAULT_ROOT,
    GUIDANCE_STEPS,
    IMAGE_GENERATION_ROUTES,
    PREFERENCE_REFERENCE_ROOT,
    RUNTIME_ENVIRONMENTS,
    WORKFLOW_STEPS,
)
from figure_studio_core.errors import StateError
from figure_studio_core.state_commands import (
    cmd_delete,
    cmd_doctor,
    cmd_create_checkpoint,
    cmd_init,
    cmd_mark_artifact_stale,
    cmd_mark_candidate,
    cmd_mark_substage,
    cmd_overwrite,
    cmd_plan_substages,
    cmd_record_image_generation,
    cmd_recommend_next_action,
    cmd_register,
    cmd_register_image_batch,
    cmd_register_reference_images,
    cmd_reset_candidate,
    cmd_rewind_step,
    cmd_resume_cleanup,
    cmd_resume,
    cmd_scan_substages,
    cmd_set_runtime_config,
    cmd_update_step,
    cmd_validate,
    cmd_write_guidance,
)

def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--allow-custom-root", action="store_true")
    parser.add_argument("--project-id", required=True)

def add_artifact_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--step", required=True, choices=[step for step, _, _, _ in WORKFLOW_STEPS])
    parser.add_argument("--kind", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--status", default="active")
    parser.add_argument("--artifact-role", choices=sorted(ARTIFACT_ROLES))
    parser.add_argument("--source-artifact-role", action="append", default=[], choices=sorted(ARTIFACT_ROLES))
    parser.add_argument("--generation-event-id", help="Required for generated target-paper image artifacts unless adopting from an existing registered source artifact role.")
    parser.add_argument("--source-user-request", default="")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init")
    add_common(p_init)
    p_init.add_argument("--title")
    p_init.add_argument("--source-material")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_register = sub.add_parser("register")
    add_common(p_register)
    add_artifact_args(p_register)
    p_register.set_defaults(func=cmd_register)

    p_update = sub.add_parser("update-step")
    add_common(p_update)
    p_update.add_argument("--current-step", required=True, choices=[step for step, _, _, _ in WORKFLOW_STEPS])
    p_update.add_argument("--resume-instructions")
    p_update.add_argument("--source-user-request")
    p_update.add_argument(
        "--allow-step-skip",
        action="store_true",
        help="Explicit override for unusual documented reroutes.",
    )
    p_update.add_argument(
        "--resume-interrupted",
        action="store_true",
        help=(
            "Explicitly continue the current in-progress step after an interrupted turn without cleanup. "
            "Default same-step execution still performs cleanup + rerun."
        ),
    )
    p_update.set_defaults(func=cmd_update_step)

    p_rewind = sub.add_parser("rewind-step")
    add_common(p_rewind)
    p_rewind.add_argument("--target-step", required=True, choices=[step for step, _, _, _ in WORKFLOW_STEPS])
    p_rewind.add_argument("--reason", default="")
    p_rewind.add_argument("--source-user-request", default="")
    p_rewind.add_argument("--dry-run", action="store_true")
    p_rewind.set_defaults(func=cmd_rewind_step)

    p_resume_cleanup = sub.add_parser("resume-cleanup")
    add_common(p_resume_cleanup)
    p_resume_cleanup.add_argument("--event-id")
    p_resume_cleanup.set_defaults(func=cmd_resume_cleanup)

    p_overwrite = sub.add_parser("overwrite")
    add_common(p_overwrite)
    add_artifact_args(p_overwrite)
    p_overwrite.set_defaults(func=cmd_overwrite)

    p_delete = sub.add_parser("delete")
    add_common(p_delete)
    p_delete.add_argument("--artifact-id", required=True)
    p_delete.set_defaults(func=cmd_delete)

    p_stale = sub.add_parser("mark-artifact-stale")
    add_common(p_stale)
    p_stale.add_argument("--artifact-id", required=True)
    p_stale.add_argument("--reason", default="")
    p_stale.set_defaults(func=cmd_mark_artifact_stale)

    p_image_batch = sub.add_parser("register-image-batch")
    add_common(p_image_batch)
    p_image_batch.add_argument("--batch-id", required=True)
    p_image_batch.add_argument("--step", required=True, choices=[step for step, _, _, _ in WORKFLOW_STEPS])
    p_image_batch.add_argument("--source", action="append", required=True)
    p_image_batch.add_argument("--output-dir", required=True)
    p_image_batch.add_argument("--filename-pattern", default="{step}-{index:02d}.png")
    p_image_batch.add_argument("--start-index", type=int, default=1)
    p_image_batch.add_argument("--kind", default="image")
    p_image_batch.add_argument("--summary", default="")
    p_image_batch.add_argument("--tag", action="append", default=[])
    p_image_batch.add_argument("--status", default="active")
    p_image_batch.add_argument("--source-user-request", default="")
    p_image_batch.add_argument("--generation-event-id", help="Generation event that produced the source images. Required for target-paper image batches unless the latest matching event is unambiguous.")
    p_image_batch.add_argument("--prompt-index", help="Optional project-run-relative prompt-index.json. With --use-target-image-paths, sources are mirrored into each candidate target_image_path from this index.")
    p_image_batch.add_argument("--use-target-image-paths", action="store_true", help="Mirror generated rasters into prompt-index target_image_path values instead of output-dir/filename-pattern paths.")
    p_image_batch.add_argument("--target-path-field", default="target_image_path", help="Prompt-index field used as the stage-local mirror path when --use-target-image-paths is set.")
    p_image_batch.add_argument("--replace", action="store_true")
    p_image_batch.set_defaults(func=cmd_register_image_batch)

    p_record_generation = sub.add_parser("record-image-generation")
    add_common(p_record_generation)
    p_record_generation.add_argument("--event-id", required=True)
    p_record_generation.add_argument("--batch-id", required=True)
    p_record_generation.add_argument("--step", required=True, choices=[step for step, _, _, _ in WORKFLOW_STEPS])
    p_record_generation.add_argument(
        "--generator",
        required=True,
        choices=["image_gen", "imagegen", "create-image", "approved-image-api"],
        help="Canonical values: image_gen for Codex Image Gen, create-image for ChatGPT web Create Image, approved-image-api only in other runtimes.",
    )
    p_record_generation.add_argument("--environment", choices=sorted(RUNTIME_ENVIRONMENTS), help="Override state runtime only when migrating alias-based state; normal runs use set-runtime-config first.")
    p_record_generation.add_argument(
        "--approved-api-name",
        help="Required when --generator=approved-image-api; must name the actual image generation API, not a drawing script.",
    )
    p_record_generation.add_argument(
        "--route-unavailable-reason",
        help="Required for approved-image-api fallback; record why first-party image routes were unavailable.",
    )
    p_record_generation.add_argument("--generated-path", action="append", default=[])
    p_record_generation.add_argument(
        "--reference-image-path",
        action="append",
        default=[],
        help="Project-run-relative S2 reference image used or offered for an S5 generation event.",
    )
    p_record_generation.add_argument(
        "--reference-input-status",
        choices=["supplied_to_generator", "ignored_unsupported", "not_requested"],
        help="For S5 reference_image_paths: supplied when the generator accepted image inputs, ignored_unsupported when the route could not accept them.",
    )
    p_record_generation.add_argument("--summary", default="")
    p_record_generation.add_argument("--source-user-request", default="")
    p_record_generation.add_argument("--require-exists", action="store_true")
    p_record_generation.set_defaults(func=cmd_record_image_generation)

    p_plan_substages = sub.add_parser("plan-substages")
    add_common(p_plan_substages)
    p_plan_substages.add_argument("--step", required=True, choices=["S2-SKETCH-EXPLORE", "S5-CANDIDATE-IMAGE"])
    p_plan_substages.add_argument("--candidate-count", type=int)
    p_plan_substages.add_argument("--runtime", choices=sorted(RUNTIME_ENVIRONMENTS))
    p_plan_substages.add_argument("--prompt-index", help="Optional prompt-index.json. When provided or when the default prompt-index exists, its candidate_id order becomes the source of truth for substages and registries.")
    p_plan_substages.add_argument("--source-user-request", default="")
    p_plan_substages.set_defaults(func=cmd_plan_substages)

    p_scan_substages = sub.add_parser("scan-substages")
    add_common(p_scan_substages)
    p_scan_substages.add_argument("--step", required=True, choices=["S2-SKETCH-EXPLORE", "S5-CANDIDATE-IMAGE"])
    p_scan_substages.add_argument("--candidate-count", type=int)
    p_scan_substages.set_defaults(func=cmd_scan_substages)

    p_recommend_next = sub.add_parser("recommend-next-action")
    add_common(p_recommend_next)
    p_recommend_next.add_argument("--step", choices=[step for step, _, _, _ in WORKFLOW_STEPS])
    p_recommend_next.add_argument("--candidate-count", type=int)
    p_recommend_next.set_defaults(func=cmd_recommend_next_action)

    p_mark_substage = sub.add_parser("mark-substage")
    add_common(p_mark_substage)
    p_mark_substage.add_argument("--step", required=True, choices=["S2-SKETCH-EXPLORE", "S5-CANDIDATE-IMAGE"])
    p_mark_substage.add_argument("--substage-id", required=True)
    p_mark_substage.add_argument("--status", required=True)
    p_mark_substage.add_argument("--note", default="")
    p_mark_substage.set_defaults(func=cmd_mark_substage)

    p_mark_candidate = sub.add_parser("mark-candidate")
    add_common(p_mark_candidate)
    p_mark_candidate.add_argument("--step", required=True, choices=["S2-SKETCH-EXPLORE", "S5-CANDIDATE-IMAGE"])
    p_mark_candidate.add_argument("--candidate-id", required=True)
    p_mark_candidate.add_argument("--status", required=True)
    p_mark_candidate.add_argument("--image-path")
    p_mark_candidate.add_argument("--audit-json")
    p_mark_candidate.add_argument("--risk-note", default="")
    p_mark_candidate.set_defaults(func=cmd_mark_candidate)

    p_reset_candidate = sub.add_parser("reset-candidate")
    add_common(p_reset_candidate)
    p_reset_candidate.add_argument("--step", required=True, choices=["S2-SKETCH-EXPLORE", "S5-CANDIDATE-IMAGE"])
    p_reset_candidate.add_argument("--candidate-id", required=True)
    p_reset_candidate.add_argument("--reason", default="")
    p_reset_candidate.set_defaults(func=cmd_reset_candidate)

    p_checkpoint = sub.add_parser("create-checkpoint")
    add_common(p_checkpoint)
    p_checkpoint.add_argument("--stage", required=True, choices=[step for step, _, _, _ in WORKFLOW_STEPS])
    p_checkpoint.add_argument("--checkpoint-type", choices=["chunk", "stage-final"], default="stage-final")
    p_checkpoint.add_argument("--sequence", type=int, default=1)
    p_checkpoint.add_argument(
        "--max-zip-bytes",
        type=int,
        default=0,
        help="Optional soft size limit. When a cumulative checkpoint exceeds this value, write numbered zip parts instead.",
    )
    p_checkpoint.add_argument(
        "--checkpoint-validation-attempts",
        type=int,
        default=3,
        help="Bounded rebuild-and-revalidate attempts before the producing stage/substage must be redone; incomplete bundles cannot close a stage.",
    )
    p_checkpoint.add_argument(
        "--substage-id",
        default=None,
        help="Optional current substage id; when set, checkpoint validation records and verifies substage page assets without hard-coded filenames.",
    )
    p_checkpoint.set_defaults(func=cmd_create_checkpoint)

    p_guidance = sub.add_parser("write-guidance")
    add_common(p_guidance)
    p_guidance.add_argument("--step", required=True, choices=sorted(GUIDANCE_STEPS))
    p_guidance.add_argument("--substage-id", required=True)
    p_guidance.add_argument("--next-prompt", required=True)
    p_guidance.add_argument("--summary", default="")
    p_guidance.add_argument("--checkpoint-path")
    p_guidance.add_argument("--source-user-request", default="")
    p_guidance.set_defaults(func=cmd_write_guidance)

    p_reference = sub.add_parser("register-reference-images")
    add_common(p_reference)
    p_reference.add_argument("--source", action="append", required=True)
    p_reference.add_argument("--output-dir", default=PREFERENCE_REFERENCE_ROOT)
    p_reference.add_argument("--reference-id-prefix", default="preference-reference")
    p_reference.add_argument("--start-index", type=int, default=1)
    p_reference.add_argument("--summary", default="")
    p_reference.add_argument("--tag", action="append", default=[])
    p_reference.add_argument("--source-user-request", default="")
    p_reference.add_argument("--replace", action="store_true")
    p_reference.set_defaults(func=cmd_register_reference_images)

    p_runtime = sub.add_parser("set-runtime-config")
    add_common(p_runtime)
    p_runtime.add_argument("--environment", required=True, choices=sorted(RUNTIME_ENVIRONMENTS))
    p_runtime.add_argument("--image-generation-route", choices=sorted(IMAGE_GENERATION_ROUTES))
    p_runtime.add_argument("--image-generation-note")
    p_runtime.add_argument("--source-user-request", default="")
    p_runtime.set_defaults(func=cmd_set_runtime_config)

    p_resume = sub.add_parser("resume")
    add_common(p_resume)
    p_resume.add_argument("--json", action="store_true")
    p_resume.set_defaults(func=cmd_resume)

    p_validate = sub.add_parser("validate")
    add_common(p_validate)
    p_validate.set_defaults(func=cmd_validate)

    p_doctor = sub.add_parser("doctor")
    add_common(p_doctor)
    p_doctor.add_argument("--json", action="store_true")
    p_doctor.add_argument("--fail-on-issue", action="store_true")
    p_doctor.set_defaults(func=cmd_doctor)

    return parser

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except StateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())

