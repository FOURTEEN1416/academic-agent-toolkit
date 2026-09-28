"""HITL intervention types, actions, and data models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class InterventionType(str, Enum):
    """Types of human interventions."""

    # Tier 1: Observe
    VIEW_OUTPUT = "view_output"
    VIEW_LOGS = "view_logs"
    VIEW_LLM_TRACE = "view_llm_trace"

    # Tier 2: Steer
    APPROVE = "approve"
    REJECT = "reject"
    EDIT_OUTPUT = "edit_output"
    INJECT_GUIDANCE = "inject_guidance"
    MODIFY_CONFIG = "modify_config"
    SKIP_STAGE = "skip_stage"
    ROLLBACK = "rollback"

    # Tier 3: Collaborate
    START_CHAT = "start_chat"
    CO_WRITE = "co_write"
    PROVIDE_RESOURCE = "provide_resource"
    TAKE_OVER = "take_over"


class PauseReason(str, Enum):
    """Why the pipeline paused for human input."""

    PRE_STAGE = "pre_stage"
    POST_STAGE = "post_stage"
    GATE_APPROVAL = "gate_approval"
    QUALITY_BELOW_THRESHOLD = "quality_below_threshold"
    COST_BUDGET_EXCEEDED = "cost_budget_exceeded"
    ERROR_OCCURRED = "error_occurred"
    HUMAN_REQUESTED = "human_requested"
    CONFIDENCE_LOW = "confidence_low"


class HumanAction(str, Enum):
    """Actions a human can take when the pipeline is paused."""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    SKIP = "skip"
    COLLABORATE = "collaborate"
    INJECT = "inject"
    ROLLBACK = "rollback"
    TAKE_OVER = "take_over"
    RESUME = "resume"
    ABORT = "abort"


@dataclass
class HumanInput:
    """Structured input from a human during an intervention."""

    action: HumanAction
    message: str = ""
    guidance: str = ""
    edited_files: dict[str, str] = field(default_factory=dict)
    config_changes: dict[str, Any] = field(default_factory=dict)
    resources: list[str] = field(default_factory=list)
    rollback_to_stage: int | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "message": self.message,
            "guidance": self.guidance,
            "edited_files": self.edited_files,
            "config_changes": self.config_changes,
            "resources": self.resources,
            "rollback_to_stage": self.rollback_to_stage,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HumanInput:
        return cls(
            action=HumanAction(data["action"]),
            message=data.get("message", ""),
            guidance=data.get("guidance", ""),
            edited_files=data.get("edited_files", {}),
            config_changes=data.get("config_changes", {}),
            resources=data.get("resources", []),
            rollback_to_stage=data.get("rollback_to_stage"),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class Intervention:
    """Complete record of one human intervention."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    type: InterventionType = InterventionType.VIEW_OUTPUT
    stage: int = 0
    stage_name: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
    )

    # Intervention content
    human_input: HumanInput | None = None
    pause_reason: PauseReason = PauseReason.POST_STAGE

    # Context
    stage_output_summary: str = ""
    quality_score: float | None = None
    confidence_score: float | None = None

    # Result
    outcome: str = ""
    accepted: bool = True
    duration_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "stage": self.stage,
            "stage_name": self.stage_name,
            "timestamp": self.timestamp,
            "human_input": self.human_input.to_dict()
            if self.human_input
            else None,
            "pause_reason": self.pause_reason.value,
            "stage_output_summary": self.stage_output_summary,
            "quality_score": self.quality_score,
            "confidence_score": self.confidence_score,
            "outcome": self.outcome,
            "accepted": self.accepted,
            "duration_sec": self.duration_sec,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Intervention:
        human_input = None
        if data.get("human_input"):
            human_input = HumanInput.from_dict(data["human_input"])
        return cls(
            id=data.get("id", ""),
            type=InterventionType(data.get("type", "view_output")),
            stage=data.get("stage", 0),
            stage_name=data.get("stage_name", ""),
            timestamp=data.get("timestamp", ""),
            human_input=human_input,
            pause_reason=PauseReason(
                data.get("pause_reason", "post_stage")
            ),
            stage_output_summary=data.get("stage_output_summary", ""),
            quality_score=data.get("quality_score"),
            confidence_score=data.get("confidence_score"),
            outcome=data.get("outcome", ""),
            accepted=data.get("accepted", True),
            duration_sec=data.get("duration_sec", 0.0),
        )


@dataclass
class WaitingState:
    """Persisted state when pipeline is waiting for human input.

    Written to ``run_dir/hitl/waiting.json`` so external tools
    (CLI ``attach``, web dashboard, MCP) can detect and respond.
    """

    stage: int
    stage_name: str
    reason: PauseReason
    since: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
    )
    available_actions: tuple[str, ...] = (
        "approve",
        "reject",
        "edit",
        "collaborate",
        "skip",
        "abort",
    )
    context_summary: str = ""
    output_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "stage_name": self.stage_name,
            "reason": self.reason.value,
            "since": self.since,
            "available_actions": list(self.available_actions),
            "context_summary": self.context_summary,
            "output_files": list(self.output_files),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WaitingState:
        return cls(
            stage=data.get("stage", 0),
            stage_name=data.get("stage_name", ""),
            reason=PauseReason(data.get("reason", "post_stage")),
            since=data.get("since", ""),
            available_actions=tuple(
                data.get(
                    "available_actions",
                    ["approve", "reject", "edit", "skip"],
                )
            ),
            context_summary=data.get("context_summary", ""),
            output_files=tuple(data.get("output_files", [])),
        )
