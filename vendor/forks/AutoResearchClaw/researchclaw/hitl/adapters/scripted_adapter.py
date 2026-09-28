"""Scripted HITL adapter for automated intervention injection.

Reads pre-written intervention JSON files and returns the appropriate
HumanInput when the pipeline pauses at a matching stage. Used for
reproducible HITL ablation experiments where expert interventions
are pre-defined rather than collected interactively.

Intervention JSON schema:
{
  "topic_id": "T01",
  "topic": "...",
  "expert_profile": "...",
  "interventions": {
    "5": {"action": "inject", "message": "...", "guidance": "..."},
    "8": {"action": "inject", "message": "...", "guidance": "..."},
    ...
  }
}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    WaitingState,
)

logger = logging.getLogger(__name__)

# Map string action names from JSON to HumanAction enum values
_ACTION_MAP: dict[str, HumanAction] = {
    "approve": HumanAction.APPROVE,
    "reject": HumanAction.REJECT,
    "edit": HumanAction.EDIT,
    "skip": HumanAction.SKIP,
    "collaborate": HumanAction.COLLABORATE,
    "inject": HumanAction.INJECT,
    "rollback": HumanAction.ROLLBACK,
    "abort": HumanAction.ABORT,
    "resume": HumanAction.RESUME,
}


class ScriptedHITLAdapter:
    """Non-interactive adapter that injects pre-written expert interventions.

    When the pipeline pauses at a stage that has a matching intervention
    in the loaded JSON, the adapter returns the scripted HumanInput.
    For stages without interventions, it auto-approves.

    Usage::

        adapter = ScriptedHITLAdapter.from_file("interventions_T01.json")
        session.set_input_callback(adapter.collect_input)
    """

    def __init__(
        self,
        interventions: dict[int, dict[str, Any]],
        *,
        topic_id: str = "",
        default_action: HumanAction = HumanAction.APPROVE,
    ) -> None:
        self.interventions = interventions
        self.topic_id = topic_id
        self.default_action = default_action
        self._injection_log: list[dict[str, Any]] = []

    @classmethod
    def from_file(cls, path: str | Path) -> ScriptedHITLAdapter:
        """Load interventions from a JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Intervention file not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        topic_id = data.get("topic_id", "")

        # Parse interventions — keys are stage numbers as strings
        interventions: dict[int, dict[str, Any]] = {}
        for stage_str, intervention_data in data.get("interventions", {}).items():
            try:
                stage_num = int(stage_str)
            except ValueError:
                logger.warning(
                    "Skipping non-numeric stage key: %s", stage_str
                )
                continue
            interventions[stage_num] = intervention_data

        logger.info(
            "Loaded %d scripted interventions for topic %s from %s",
            len(interventions),
            topic_id,
            path,
        )
        return cls(interventions, topic_id=topic_id)

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, topic_id: str = ""
    ) -> ScriptedHITLAdapter:
        """Create adapter from an already-parsed dict."""
        interventions: dict[int, dict[str, Any]] = {}
        for stage_str, intervention_data in data.get("interventions", {}).items():
            try:
                stage_num = int(stage_str)
            except ValueError:
                continue
            interventions[stage_num] = intervention_data
        return cls(
            interventions,
            topic_id=topic_id or data.get("topic_id", ""),
        )

    def collect_input(self, waiting: WaitingState) -> HumanInput:
        """Return scripted intervention or auto-approve.

        This method signature matches the HITLAdapter protocol and can
        be passed to ``HITLSession.set_input_callback()``.
        """
        stage = waiting.stage
        intervention = self.interventions.get(stage)

        if intervention is None:
            logger.debug(
                "No scripted intervention for stage %d — auto-approving",
                stage,
            )
            return HumanInput(action=self.default_action)

        action_str = intervention.get("action", "inject").lower()
        action = _ACTION_MAP.get(action_str, HumanAction.INJECT)
        message = intervention.get("message", "")
        guidance = intervention.get("guidance", "")

        human_input = HumanInput(
            action=action,
            message=message,
            guidance=guidance,
            edited_files=intervention.get("edited_files", {}),
            config_changes=intervention.get("config_changes", {}),
        )

        self._injection_log.append({
            "stage": stage,
            "stage_name": waiting.stage_name,
            "action": action.value,
            "message": message,
            "guidance_length": len(guidance),
        })

        logger.info(
            "Scripted intervention at stage %d (%s): action=%s, "
            "guidance=%d chars",
            stage,
            waiting.stage_name,
            action.value,
            len(guidance),
        )

        return human_input

    @property
    def injection_log(self) -> list[dict[str, Any]]:
        """Return log of all injections made during this session."""
        return list(self._injection_log)

    @property
    def pending_stages(self) -> list[int]:
        """Return stage numbers that have interventions defined."""
        return sorted(self.interventions.keys())

    def has_intervention(self, stage_num: int) -> bool:
        """Check if a scripted intervention exists for a stage."""
        return stage_num in self.interventions

    # ------------------------------------------------------------------
    # HITLAdapter protocol methods (display-related — no-op for scripted)
    # ------------------------------------------------------------------

    def show_stage_output(
        self, stage_num: int, stage_name: str, summary: str
    ) -> None:
        """No-op: scripted adapter does not display output."""
        pass

    def show_message(self, message: str) -> None:
        logger.info("Scripted adapter message: %s", message)

    def show_error(self, message: str) -> None:
        logger.warning("Scripted adapter error: %s", message)

    def show_progress(
        self, stage_num: int, total: int, stage_name: str, status: str
    ) -> None:
        """No-op: scripted adapter does not display progress."""
        pass
