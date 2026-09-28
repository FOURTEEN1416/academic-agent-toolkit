"""Codex and Claude Code projections over one host-neutral state protocol."""

from __future__ import annotations

from typing import Any


def host_message(job: dict[str, Any], state: dict[str, Any], host: str | None = None) -> dict[str, Any]:
    selected_host = host or job["host"]
    if selected_host not in {"codex", "claude-code", "dsh", "standalone-skill"}:
        raise ValueError("host must be codex, claude-code, dsh, or standalone-skill")
    stage = state["stage"]
    plan = {
        "initialized": (
            "advance",
            "Validate the PaperSpine handoff and create the FigMirror generation plan.",
        ),
        "awaiting_candidates": (
            "author_candidates",
            "Use the paperFig process and every generation_request.json to author, render, inspect, finalize, and score each configured candidate.",
        ),
        "awaiting_review": (
            "request_human_review",
            "Open the unified review UI, compare complete candidate schemes, and submit one confirmed decision for every figure.",
        ),
        "figures_confirmed": (
            "assemble",
            "Advance once more to copy confirmed exports into final_paper and inject configured LaTeX markers.",
        ),
        "awaiting_paper_integration": (
            "continue_paper",
            "Consume figure_body_contract.json in Results and captions, add real body references, then finish the PaperSpine final pixel audit before advancing again.",
        ),
        "canonical_paper_ready": (
            "choose_publication_operation",
            "The canonical paper is ready. Validate a target profile, assemble a submission bundle, check or render rebuttal materials, or plan a destination rebuild.",
        ),
        "target_profile_ready": (
            "prepare_target_materials",
            "The target profile is valid. Finish the target-specific manuscript and materials, then assemble an immutable local bundle.",
        ),
        "rebuttal_validated": (
            "render_rebuttal",
            "The review-round contract is valid. Render the local rebuttal materials when the responses are complete.",
        ),
        "rebuttal_materials_ready": (
            "review_rebuttal_materials",
            "The local rebuttal materials are ready. External resubmission still requires separate user authorization.",
        ),
        "destination_rebuild_ready": (
            "rebuild_for_destination",
            "The transfer delta is ready. Return to target planning, drafting, formatting, and audit for the destination venue.",
        ),
        "awaiting_external_authorization": (
            "request_external_authorization",
            "The immutable local target bundle is ready. Do not submit, accept fees, or accept licenses without separate user authorization.",
        ),
        "complete": (
            "done",
            "The figure story, generated or retained assets, manuscript references, and final pixel audit are complete.",
        ),
        "blocked": ("resolve_blocker", state.get("last_error", "Resolve the recorded integration blocker.")),
    }
    action, instruction = plan.get(stage, ("inspect", state.get("next_action", "Inspect integration state.")))
    host_hints = {
        "codex": "Codex should call the PaperSpine5 MCP tools in the current task and keep all generated candidate evidence in the FigMirror job directory.",
        "claude-code": "Claude Code should call the same PaperSpine5 MCP tools; slash commands are optional because the JSON state is authoritative.",
        "dsh": "DSH should use the host-neutral JSON bridge or MCP adapter and treat integration_state.json as the source of truth.",
        "standalone-skill": "The standalone Skill should launch the loopback workspace and continue from the persisted integration state.",
    }
    host_hint = host_hints[selected_host]
    return {
        "protocol_version": "1.0",
        "message_type": "paperspine.figure.next_action",
        "job_id": job["job_id"],
        "host": selected_host,
        "stage": stage,
        "action": action,
        "instruction": instruction,
        "host_hint": host_hint,
        "artifacts": {
            "job": job["job_file"],
            "state": job["state_file"],
            "paper_output": job["paper"]["output_dir"],
            "figure_job": job["figure"]["job_dir"],
        },
        "continue_signal": {
            "schema_version": "1.0",
            "signal_type": "continue",
            "job_id": job["job_id"],
            "source": selected_host,
        },
    }
