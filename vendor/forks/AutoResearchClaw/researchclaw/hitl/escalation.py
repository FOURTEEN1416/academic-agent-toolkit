"""Escalation policy: tiered notification escalation when humans don't respond.

Production research pipelines can't wait forever. When a gate is
unattended, escalation kicks in:

1. First: Terminal notification (immediate)
2. After N minutes: Slack/email notification
3. After M minutes: Secondary contact notification
4. After T minutes: Auto-halt or auto-proceed (configurable)

This prevents pipelines from silently stalling for days.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EscalationLevel:
    """One level in the escalation chain."""

    delay_sec: int        # Seconds after pause to trigger
    channel: str          # "terminal" | "slack" | "email" | "webhook"
    message: str = ""     # Custom message template
    auto_action: str = "" # "approve" | "abort" | "" (just notify)


@dataclass(frozen=True)
class EscalationPolicy:
    """Complete escalation policy for a stage or default."""

    levels: tuple[EscalationLevel, ...] = (
        EscalationLevel(delay_sec=0, channel="terminal"),
        EscalationLevel(delay_sec=1800, channel="slack",
                        message="Pipeline paused for 30min — needs attention"),
        EscalationLevel(delay_sec=7200, channel="email",
                        message="Pipeline paused for 2h — critical review needed"),
        EscalationLevel(delay_sec=86400, channel="terminal",
                        auto_action="abort",
                        message="Pipeline paused for 24h — auto-aborting"),
    )
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EscalationPolicy:
        if not data:
            return cls()
        levels = []
        for level_data in data.get("levels", []):
            levels.append(EscalationLevel(
                delay_sec=int(level_data.get("delay_sec", 0)),
                channel=level_data.get("channel", "terminal"),
                message=level_data.get("message", ""),
                auto_action=level_data.get("auto_action", ""),
            ))
        return cls(
            levels=tuple(levels) if levels else EscalationPolicy().levels,
            enabled=data.get("enabled", True),
        )


class EscalationTracker:
    """Track and execute escalation for a paused pipeline.

    Call ``check()`` periodically (e.g., in the file polling loop)
    to trigger escalation levels as time passes.
    """

    def __init__(
        self,
        policy: EscalationPolicy,
        notify_callback: Any = None,
    ) -> None:
        self.policy = policy
        self.notify_callback = notify_callback
        self._pause_time: float = 0.0
        self._triggered_levels: set[int] = set()  # delay_sec values
        self._active = False

    def start(self, stage: int, stage_name: str) -> None:
        """Start tracking a pause."""
        self._pause_time = time.monotonic()
        self._triggered_levels = set()
        self._active = True
        self._stage = stage
        self._stage_name = stage_name

    def stop(self) -> None:
        """Stop tracking (pause resolved)."""
        self._active = False

    def check(self) -> str:
        """Check if any escalation level should fire.

        Returns:
            The auto_action of the highest triggered level ("approve"/"abort"/"")),
            or "" if no action should be taken.
        """
        if not self._active or not self.policy.enabled:
            return ""

        elapsed = time.monotonic() - self._pause_time
        auto_action = ""

        for level in self.policy.levels:
            if level.delay_sec in self._triggered_levels:
                continue
            if elapsed >= level.delay_sec:
                self._triggered_levels.add(level.delay_sec)
                self._fire_level(level, elapsed)
                if level.auto_action:
                    auto_action = level.auto_action

        return auto_action

    @property
    def elapsed_sec(self) -> float:
        if not self._active:
            return 0.0
        return time.monotonic() - self._pause_time

    @property
    def next_escalation_sec(self) -> float | None:
        """Seconds until the next escalation level fires."""
        if not self._active:
            return None
        elapsed = time.monotonic() - self._pause_time
        for level in sorted(self.policy.levels, key=lambda l: l.delay_sec):
            if level.delay_sec not in self._triggered_levels:
                remaining = level.delay_sec - elapsed
                if remaining > 0:
                    return remaining
        return None

    def _fire_level(self, level: EscalationLevel, elapsed: float) -> None:
        """Execute an escalation level."""
        message = level.message or (
            f"Pipeline paused at Stage {self._stage} ({self._stage_name}) "
            f"for {elapsed:.0f}s"
        )
        if level.auto_action:
            message += f" — auto-{level.auto_action} triggered"

        logger.info(
            "Escalation fired: channel=%s, delay=%ds, action=%s",
            level.channel, level.delay_sec, level.auto_action or "notify",
        )

        if self.notify_callback is not None:
            try:
                self.notify_callback(
                    channel=level.channel,
                    title=f"Escalation: Stage {self._stage}",
                    message=message,
                    level="critical" if level.auto_action else "warning",
                )
            except Exception as exc:
                logger.warning("Escalation notify failed: %s", exc)
