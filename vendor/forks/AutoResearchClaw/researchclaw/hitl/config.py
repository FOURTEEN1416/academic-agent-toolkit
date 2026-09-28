"""HITL configuration: intervention modes, stage policies, and presets."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InterventionMode(str, Enum):
    """Top-level pipeline intervention mode."""

    FULL_AUTO = "full-auto"
    GATE_ONLY = "gate-only"
    CHECKPOINT = "checkpoint"
    STEP_BY_STEP = "step-by-step"
    CO_PILOT = "co-pilot"
    CUSTOM = "custom"


class NotificationChannel(str, Enum):
    TERMINAL = "terminal"
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclass(frozen=True)
class StagePolicy:
    """Per-stage human intervention policy.

    Controls exactly how the HITL system interacts with the user at each stage.
    """

    # Basic control
    auto_execute: bool = True
    pause_before: bool = False
    pause_after: bool = False
    require_approval: bool = False

    # Observation level
    stream_output: bool = False
    show_llm_calls: bool = False

    # Intervention level
    allow_edit_output: bool = False
    allow_inject_prompt: bool = False
    enable_collaboration: bool = False

    # Quality gate
    min_quality_score: float = 0.0
    max_auto_retries: int = 2

    # Timeout
    human_timeout_sec: int = 86400
    auto_proceed_on_timeout: bool = False


@dataclass(frozen=True)
class HITLNotificationsConfig:
    """Notification settings for HITL events."""

    on_pause: bool = True
    on_quality_drop: bool = True
    on_error: bool = True
    channels: tuple[str, ...] = ("terminal",)


@dataclass(frozen=True)
class HITLCollaborationConfig:
    """Settings for collaborative sessions."""

    llm_model: str = ""
    max_chat_turns: int = 50
    save_chat_history: bool = True


@dataclass(frozen=True)
class HITLTimeoutsConfig:
    """Timeout settings for human responses."""

    default_human_timeout_sec: int = 86400
    auto_proceed_on_timeout: bool = False


@dataclass(frozen=True)
class HITLConfig:
    """Complete HITL configuration."""

    enabled: bool = False
    mode: str = "full-auto"
    cost_budget_usd: float = 0.0  # 0 = no budget limit

    notifications: HITLNotificationsConfig = field(
        default_factory=HITLNotificationsConfig
    )
    collaboration: HITLCollaborationConfig = field(
        default_factory=HITLCollaborationConfig
    )
    timeouts: HITLTimeoutsConfig = field(default_factory=HITLTimeoutsConfig)

    # Per-stage policies (stage number -> policy)
    stage_policies: dict[int, StagePolicy] = field(default_factory=dict)

    @property
    def intervention_mode(self) -> InterventionMode:
        try:
            return InterventionMode(self.mode)
        except ValueError:
            return InterventionMode.FULL_AUTO

    def get_stage_policy(self, stage_num: int) -> StagePolicy:
        """Return the policy for a stage, falling back to mode defaults."""
        if stage_num in self.stage_policies:
            return self.stage_policies[stage_num]
        return _default_policy_for_mode(self.intervention_mode, stage_num)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HITLConfig:
        """Load HITLConfig from a config dict (e.g., YAML section)."""
        if not data:
            return cls()

        notifications = HITLNotificationsConfig(
            on_pause=data.get("notifications", {}).get("on_pause", True),
            on_quality_drop=data.get("notifications", {}).get(
                "on_quality_drop", True
            ),
            on_error=data.get("notifications", {}).get("on_error", True),
            channels=tuple(
                data.get("notifications", {}).get("channels", ["terminal"])
            ),
        )

        collaboration = HITLCollaborationConfig(
            llm_model=data.get("collaboration", {}).get("llm_model", ""),
            max_chat_turns=data.get("collaboration", {}).get(
                "max_chat_turns", 50
            ),
            save_chat_history=data.get("collaboration", {}).get(
                "save_chat_history", True
            ),
        )

        timeouts = HITLTimeoutsConfig(
            default_human_timeout_sec=data.get("timeouts", {}).get(
                "default_human_timeout_sec", 86400
            ),
            auto_proceed_on_timeout=data.get("timeouts", {}).get(
                "auto_proceed_on_timeout", False
            ),
        )

        # Parse per-stage policies
        stage_policies: dict[int, StagePolicy] = {}
        raw_policies = data.get("stage_policies", {})
        for stage_key, policy_dict in raw_policies.items():
            stage_num = int(stage_key)
            stage_policies[stage_num] = StagePolicy(**{
                k: v
                for k, v in policy_dict.items()
                if k in StagePolicy.__dataclass_fields__
            })

        return cls(
            enabled=data.get("enabled", False),
            mode=data.get("mode", "full-auto"),
            cost_budget_usd=float(data.get("cost_budget_usd", 0.0)),
            notifications=notifications,
            collaboration=collaboration,
            timeouts=timeouts,
            stage_policies=stage_policies,
        )


# ---------------------------------------------------------------------------
# Gate stages and phase boundaries (imported from stages.py values)
# ---------------------------------------------------------------------------

_GATE_STAGES = frozenset({5, 9, 20})

_PHASE_BOUNDARIES = frozenset({
    2,   # End of Phase A (Research Scoping)
    6,   # End of Phase B (Literature Discovery)
    8,   # End of Phase C (Knowledge Synthesis)
    11,  # End of Phase D (Experiment Design)
    13,  # End of Phase E (Experiment Execution)
    15,  # End of Phase F (Analysis & Decision)
    19,  # End of Phase G (Paper Writing)
    23,  # End of Phase H (Finalization)
})

# Co-pilot mode: critical stages needing deep collaboration
_COPILOT_COLLABORATION_STAGES = frozenset({7, 8, 9, 17})
_COPILOT_APPROVAL_STAGES = frozenset({5, 8, 9, 15, 20})
_COPILOT_PAUSE_AFTER_STAGES = frozenset({1, 2, 3, 10, 13, 16, 18, 23})
_COPILOT_STREAM_STAGES = frozenset({12})


def _default_policy_for_mode(
    mode: InterventionMode, stage_num: int
) -> StagePolicy:
    """Generate a default StagePolicy based on intervention mode."""

    if mode == InterventionMode.FULL_AUTO:
        return StagePolicy()

    if mode == InterventionMode.GATE_ONLY:
        if stage_num in _GATE_STAGES:
            return StagePolicy(
                require_approval=True,
                allow_edit_output=True,
            )
        return StagePolicy()

    if mode == InterventionMode.CHECKPOINT:
        if stage_num in _PHASE_BOUNDARIES:
            return StagePolicy(
                pause_after=True,
                allow_edit_output=True,
                require_approval=True,
            )
        return StagePolicy()

    if mode == InterventionMode.STEP_BY_STEP:
        return StagePolicy(
            pause_after=True,
            allow_edit_output=True,
            stream_output=True,
        )

    if mode == InterventionMode.CO_PILOT:
        return StagePolicy(
            pause_after=stage_num in _COPILOT_PAUSE_AFTER_STAGES,
            require_approval=stage_num in _COPILOT_APPROVAL_STAGES,
            allow_edit_output=True,
            allow_inject_prompt=True,
            enable_collaboration=stage_num in _COPILOT_COLLABORATION_STAGES,
            stream_output=stage_num in _COPILOT_STREAM_STAGES,
        )

    # CUSTOM mode: all defaults off (user configures each stage)
    return StagePolicy()
