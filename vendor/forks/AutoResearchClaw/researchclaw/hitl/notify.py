"""HITL notification system: alert humans when intervention is needed."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    """A notification to be sent to the human."""

    title: str
    body: str
    level: str = "info"  # info | warning | critical
    stage: int = 0
    stage_name: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
    )
    channel: str = "terminal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body": self.body,
            "level": self.level,
            "stage": self.stage,
            "stage_name": self.stage_name,
            "timestamp": self.timestamp,
            "channel": self.channel,
        }


class NotificationManager:
    """Multi-channel notification dispatcher."""

    def __init__(
        self,
        channels: tuple[str, ...] = ("terminal",),
        run_dir: Path | None = None,
    ) -> None:
        self.channels = channels
        self.run_dir = run_dir
        self.history: list[Notification] = []

    def notify_pause(
        self, stage: int, stage_name: str, reason: str
    ) -> None:
        """Notify that the pipeline has paused for human input."""
        notification = Notification(
            title=f"Pipeline paused at Stage {stage}",
            body=(
                f"Stage {stage} ({stage_name}) needs your attention.\n"
                f"Reason: {reason}\n"
                f"Use 'researchclaw attach <run-id>' to respond."
            ),
            level="warning",
            stage=stage,
            stage_name=stage_name,
        )
        self._dispatch(notification)

    def notify_quality_drop(
        self, stage: int, stage_name: str, score: float, threshold: float
    ) -> None:
        """Notify about quality score below threshold."""
        notification = Notification(
            title=f"Quality alert: Stage {stage}",
            body=(
                f"Stage {stage} ({stage_name}) quality score {score:.2f} "
                f"is below threshold {threshold:.2f}."
            ),
            level="warning",
            stage=stage,
            stage_name=stage_name,
        )
        self._dispatch(notification)

    def notify_error(
        self, stage: int, stage_name: str, error: str
    ) -> None:
        """Notify about a stage error."""
        notification = Notification(
            title=f"Error at Stage {stage}",
            body=f"Stage {stage} ({stage_name}) failed: {error[:200]}",
            level="critical",
            stage=stage,
            stage_name=stage_name,
        )
        self._dispatch(notification)

    def notify_complete(self, run_id: str, stages_done: int) -> None:
        """Notify that the pipeline has completed."""
        notification = Notification(
            title="Pipeline completed",
            body=f"Run {run_id} completed ({stages_done} stages done).",
            level="info",
        )
        self._dispatch(notification)

    def _dispatch(self, notification: Notification) -> None:
        """Send notification to all configured channels."""
        self.history.append(notification)

        for channel in self.channels:
            try:
                if channel == "terminal":
                    self._send_terminal(notification)
                elif channel == "slack":
                    self._send_slack(notification)
                elif channel == "webhook":
                    self._send_webhook(notification)
                else:
                    logger.debug("Unknown channel: %s", channel)
            except Exception as exc:
                logger.warning(
                    "Notification to %s failed: %s", channel, exc
                )

        # Persist to log
        self._persist(notification)

    def _send_terminal(self, n: Notification) -> None:
        """Display notification in terminal."""
        icons = {"info": "ℹ", "warning": "⚠", "critical": "🚨"}
        icon = icons.get(n.level, "•")
        print(f"\n  {icon} {n.title}")
        if n.body:
            for line in n.body.split("\n"):
                print(f"    {line}")

    def _send_slack(self, n: Notification) -> None:
        """Send notification to Slack via webhook."""
        webhook_url = os.environ.get("RESEARCHCLAW_SLACK_WEBHOOK", "")
        if not webhook_url:
            logger.debug("Slack webhook not configured")
            return

        try:
            import urllib.request

            payload = json.dumps({
                "text": f"*{n.title}*\n{n.body}",
            }).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:
            logger.warning("Slack notification failed: %s", exc)

    def _send_webhook(self, n: Notification) -> None:
        """Send notification to a generic webhook."""
        webhook_url = os.environ.get("RESEARCHCLAW_WEBHOOK_URL", "")
        if not webhook_url:
            return

        try:
            import urllib.request

            payload = json.dumps(n.to_dict()).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:
            logger.warning("Webhook notification failed: %s", exc)

    def _persist(self, notification: Notification) -> None:
        """Append notification to the HITL log."""
        if self.run_dir is None:
            return
        log_dir = self.run_dir / "hitl"
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(
                log_dir / "notifications.jsonl", "a", encoding="utf-8"
            ) as fh:
                fh.write(json.dumps(notification.to_dict()) + "\n")
        except OSError:
            pass
