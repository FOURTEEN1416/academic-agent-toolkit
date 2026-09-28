from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .entry_policy import suggest_stage_stop as suggest_stage_stop_from_entry


@dataclass(frozen=True, slots=True)
class StageStopDecision:
    requested_stage_stop: str | None
    effective_requested_stage_stop: str
    stage_stop_source: str


def suggest_stage_stop(preferred_skill: str | None) -> str:
    return suggest_stage_stop_from_entry(preferred_skill)


def resolve_stage_stop(
    requested_stage_stop: str | None,
    default_stage_stop: str,
    *,
    default_source: str,
) -> StageStopDecision:
    normalized_requested = str(requested_stage_stop or "").strip() or None
    normalized_default = str(default_stage_stop or "").strip()
    if not normalized_default:
        raise ValueError("default stage stop must be non-empty")
    if normalized_requested:
        return StageStopDecision(
            requested_stage_stop=normalized_requested,
            effective_requested_stage_stop=normalized_requested,
            stage_stop_source="requested",
        )
    return StageStopDecision(
        requested_stage_stop=None,
        effective_requested_stage_stop=normalized_default,
        stage_stop_source=default_source,
    )


def resolve_progressive_stage_stop_source(
    *,
    requested_stage_stop: str | None,
    effective_requested_stage_stop: str | None,
) -> str:
    normalized_requested = str(requested_stage_stop or "").strip() or None
    normalized_effective = str(effective_requested_stage_stop or "").strip() or None
    if normalized_requested and normalized_requested == normalized_effective:
        return "requested"
    if normalized_requested:
        return "progressive_adjusted"
    return "progressive_default"


def extract_terminal_stage(stage_lineage: dict[str, Any]) -> str | None:
    last_stage_name = str(stage_lineage.get("last_stage_name") or stage_lineage.get("last_stage") or "").strip()
    if last_stage_name:
        return last_stage_name
    stages = stage_lineage.get("stages")
    if isinstance(stages, list) and stages:
        tail = stages[-1]
        if isinstance(tail, dict):
            stage_name = str(tail.get("stage_name") or tail.get("stage") or "").strip()
            if stage_name:
                return stage_name
    entries = stage_lineage.get("entries")
    if isinstance(entries, list) and entries:
        tail = entries[-1]
        if isinstance(tail, dict):
            stage_name = str(tail.get("stage_name") or tail.get("stage") or "").strip()
            if stage_name:
                return stage_name
    stage_name = str(stage_lineage.get("stage_name") or stage_lineage.get("stage") or "").strip()
    return stage_name or None


def resolve_terminal_stage(
    *,
    stage_lineage_payload: dict[str, Any],
    summary: dict[str, Any],
    fallback_terminal_stage: str | None,
) -> str:
    terminal_stage = extract_terminal_stage(stage_lineage_payload)
    if terminal_stage:
        return terminal_stage
    summary_terminal_stage = str(summary.get("terminal_stage") or "").strip()
    if summary_terminal_stage:
        return summary_terminal_stage
    normalized_fallback = str(fallback_terminal_stage or "").strip()
    if normalized_fallback:
        return normalized_fallback
    return "unknown"
