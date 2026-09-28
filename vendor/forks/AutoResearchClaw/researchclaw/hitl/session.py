"""HITL session manager: orchestrates human-pipeline interaction."""

from __future__ import annotations

import json
import logging
import time as _time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from researchclaw.hitl.config import HITLConfig, InterventionMode, StagePolicy
from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    Intervention,
    InterventionType,
    PauseReason,
    WaitingState,
)

logger = logging.getLogger(__name__)


class SessionState:
    ACTIVE = "active"
    PAUSED = "paused"
    WAITING_HUMAN = "waiting_human"
    COLLABORATING = "collaborating"
    COMPLETED = "completed"
    ABORTED = "aborted"


@dataclass
class HITLSession:
    """Manages all human-pipeline interaction for a single run.

    The session is created when the pipeline starts and persists across
    pauses and resumes. It can be serialized to disk so that a detached
    ``researchclaw attach`` command can reconnect.
    """

    session_id: str = field(
        default_factory=lambda: str(uuid.uuid4())[:12]
    )
    run_id: str = ""
    config: HITLConfig = field(default_factory=HITLConfig)
    state: str = SessionState.ACTIVE
    run_dir: Path | None = None

    # Intervention log
    interventions: list[Intervention] = field(default_factory=list)
    human_edits: list[int] = field(default_factory=list)
    total_human_time_sec: float = 0.0
    interventions_count: int = 0

    # Current wait state
    _waiting: WaitingState | None = field(default=None, repr=False)
    _input_callback: Callable[
        [WaitingState], HumanInput
    ] | None = field(default=None, repr=False)

    # Timestamps
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
    )
    last_activity: str = ""

    @property
    def is_active(self) -> bool:
        return self.state in (
            SessionState.ACTIVE,
            SessionState.COLLABORATING,
        )

    @property
    def is_waiting(self) -> bool:
        return self.state == SessionState.WAITING_HUMAN

    @property
    def intervention_mode(self) -> InterventionMode:
        return self.config.intervention_mode

    def set_input_callback(
        self,
        callback: Callable[[WaitingState], HumanInput],
    ) -> None:
        """Register the function that collects human input.

        The callback receives a WaitingState describing *why* the pipeline
        paused and *what actions* are available. It must return a HumanInput.
        For the CLI adapter this blocks on ``input()``; for WebSocket it
        awaits a message.
        """
        self._input_callback = callback

    # ------------------------------------------------------------------
    # Policy queries
    # ------------------------------------------------------------------

    def get_policy(self, stage_num: int) -> StagePolicy:
        return self.config.get_stage_policy(stage_num)

    def should_pause_before(self, stage_num: int) -> bool:
        if not self.config.enabled:
            return False
        return self.get_policy(stage_num).pause_before

    def should_pause_after(self, stage_num: int) -> bool:
        if not self.config.enabled:
            return False
        policy = self.get_policy(stage_num)
        return (
            policy.pause_after
            or policy.require_approval
            or policy.enable_collaboration
        )

    def should_stream(self, stage_num: int) -> bool:
        if not self.config.enabled:
            return False
        return self.get_policy(stage_num).stream_output

    def should_collaborate(self, stage_num: int) -> bool:
        if not self.config.enabled:
            return False
        return self.get_policy(stage_num).enable_collaboration

    def quality_threshold(self, stage_num: int) -> float:
        return self.get_policy(stage_num).min_quality_score

    # ------------------------------------------------------------------
    # Pause / wait / resume cycle
    # ------------------------------------------------------------------

    def pause(
        self,
        stage_num: int,
        stage_name: str,
        reason: PauseReason,
        *,
        context_summary: str = "",
        output_files: tuple[str, ...] = (),
        quality_score: float | None = None,
        confidence_score: float | None = None,
    ) -> None:
        """Pause the pipeline and enter waiting state."""
        self.state = SessionState.WAITING_HUMAN
        self._waiting = WaitingState(
            stage=stage_num,
            stage_name=stage_name,
            reason=reason,
            context_summary=context_summary,
            output_files=output_files,
        )
        self._persist_waiting()
        logger.info(
            "HITL session %s paused at stage %d (%s): %s",
            self.session_id,
            stage_num,
            stage_name,
            reason.value,
        )

    def wait_for_human(self) -> HumanInput:
        """Block until human provides input.

        If no input callback is registered (e.g., non-interactive mode),
        returns an auto-approve action after the configured timeout, or
        immediately if auto_proceed_on_timeout is set.
        """
        if self._waiting is None:
            return HumanInput(action=HumanAction.APPROVE)

        t0 = _time.monotonic()

        if self._input_callback is not None:
            try:
                human_input = self._input_callback(self._waiting)
            except Exception as _cb_exc:
                logger.warning(
                    "HITL input callback failed: %s — falling back to file polling",
                    _cb_exc,
                )
                # Fall through to file polling or auto-approve
                human_input = None
            if human_input is not None:
                pass  # callback succeeded
            elif self.run_dir is not None:
                # Callback failed — fall back to file polling, honouring the
                # user's configured timeout policy (do NOT silently
                # auto-approve a gate the user asked to review).
                from researchclaw.hitl.file_wait import poll_for_response
                human_input = poll_for_response(
                    self.run_dir / "hitl",
                    timeout_sec=self.config.timeouts.default_human_timeout_sec,
                    auto_proceed_on_timeout=(
                        self.config.timeouts.auto_proceed_on_timeout
                    ),
                )
            else:
                # No file channel to recover on — approve only if the user
                # opted into auto-proceed; otherwise abort rather than fabricate
                # an approval.
                if self.config.timeouts.auto_proceed_on_timeout:
                    human_input = HumanInput(action=HumanAction.APPROVE)
                else:
                    human_input = HumanInput(
                        action=HumanAction.ABORT,
                        message="HITL input callback failed and no run_dir "
                        "to recover input from",
                    )
        elif self.run_dir is not None:
            # No interactive callback — use file-based polling
            # External tools (attach, web, MCP) can write response.json
            from researchclaw.hitl.file_wait import poll_for_response

            logger.info(
                "No interactive callback — polling for file response "
                "at %s/hitl/response.json",
                self.run_dir,
            )
            print(
                f"  Waiting for input... "
                f"Use 'researchclaw attach {self.run_dir}' to respond."
            )
            human_input = poll_for_response(
                self.run_dir / "hitl",
                timeout_sec=self.config.timeouts.default_human_timeout_sec,
                auto_proceed_on_timeout=(
                    self.config.timeouts.auto_proceed_on_timeout
                ),
            )
        else:
            # No callback and no run_dir — auto-approve (full-auto fallback)
            logger.info(
                "No HITL input callback — auto-approving stage %d",
                self._waiting.stage,
            )
            human_input = HumanInput(action=HumanAction.APPROVE)

        elapsed = _time.monotonic() - t0
        self.total_human_time_sec += elapsed

        # Record intervention
        intervention = Intervention(
            type=_action_to_intervention_type(human_input.action),
            stage=self._waiting.stage,
            stage_name=self._waiting.stage_name,
            human_input=human_input,
            pause_reason=self._waiting.reason,
            outcome=f"Human chose: {human_input.action.value}",
            accepted=human_input.action != HumanAction.ABORT,
            duration_sec=elapsed,
        )
        self.interventions.append(intervention)
        self.interventions_count += 1

        if human_input.action == HumanAction.EDIT:
            if self._waiting.stage not in self.human_edits:
                self.human_edits.append(self._waiting.stage)

        # Clear waiting state
        self.state = SessionState.ACTIVE
        self._clear_waiting()
        self._update_activity()
        self._persist_session()
        self._persist_interventions(intervention)

        return human_input

    def resume(self) -> None:
        """Resume from paused state without collecting new input."""
        self.state = SessionState.ACTIVE
        self._clear_waiting()
        self._update_activity()

    def enter_collaboration(self, stage_num: int, stage_name: str) -> None:
        """Switch to collaborating state for a stage."""
        self.state = SessionState.COLLABORATING
        self._update_activity()
        logger.info(
            "HITL session %s entering collaboration at stage %d (%s)",
            self.session_id,
            stage_num,
            stage_name,
        )

    def exit_collaboration(self) -> None:
        """Exit collaboration mode and return to active."""
        self.state = SessionState.ACTIVE
        self._update_activity()

    def complete(self) -> None:
        """Mark session as completed."""
        self.state = SessionState.COMPLETED
        self._update_activity()
        self._persist_session()

    def abort(self) -> None:
        """Mark session as aborted."""
        self.state = SessionState.ABORTED
        self._update_activity()
        self._persist_session()

    # ------------------------------------------------------------------
    # Guidance injection
    # ------------------------------------------------------------------

    def inject_guidance(
        self, stage_num: int, stage_name: str, guidance: str
    ) -> Intervention:
        """Record a guidance injection for a stage."""
        intervention = Intervention(
            type=InterventionType.INJECT_GUIDANCE,
            stage=stage_num,
            stage_name=stage_name,
            human_input=HumanInput(
                action=HumanAction.INJECT,
                guidance=guidance,
            ),
            pause_reason=PauseReason.HUMAN_REQUESTED,
            outcome=f"Guidance injected: {guidance[:80]}...",
            accepted=True,
        )
        self.interventions.append(intervention)
        self.interventions_count += 1
        self._persist_interventions(intervention)
        return intervention

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "run_id": self.run_id,
            "state": self.state,
            "mode": self.config.mode,
            "interventions_count": self.interventions_count,
            "human_edits": self.human_edits,
            "total_human_time_sec": round(self.total_human_time_sec, 1),
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "waiting": self._waiting.to_dict() if self._waiting else None,
        }

    def hitl_checkpoint_data(self) -> dict[str, Any]:
        """Return HITL data to embed in the pipeline checkpoint."""
        return {
            "mode": self.config.mode,
            "interventions_count": self.interventions_count,
            "last_intervention": (
                self.interventions[-1].to_dict()
                if self.interventions
                else None
            ),
            "pending_stage": (
                self._waiting.stage if self._waiting else None
            ),
            "collaboration_active": (
                self.state == SessionState.COLLABORATING
            ),
            "human_edits": self.human_edits,
            "total_human_time_sec": round(self.total_human_time_sec, 1),
        }

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _hitl_dir(self) -> Path | None:
        if self.run_dir is None:
            return None
        d = self.run_dir / "hitl"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _persist_session(self) -> None:
        d = self._hitl_dir()
        if d is None:
            return
        try:
            (d / "session.json").write_text(
                json.dumps(self.to_dict(), indent=2), encoding="utf-8"
            )
        except OSError:
            logger.debug("Failed to persist HITL session")

    def _persist_waiting(self) -> None:
        d = self._hitl_dir()
        if d is None or self._waiting is None:
            return
        try:
            (d / "waiting.json").write_text(
                json.dumps(self._waiting.to_dict(), indent=2),
                encoding="utf-8",
            )
        except OSError:
            logger.debug("Failed to persist waiting state")

    def _clear_waiting(self) -> None:
        self._waiting = None
        d = self._hitl_dir()
        if d is None:
            return
        waiting_file = d / "waiting.json"
        if waiting_file.exists():
            waiting_file.unlink(missing_ok=True)

    def _persist_interventions(self, intervention: Intervention) -> None:
        d = self._hitl_dir()
        if d is None:
            return
        try:
            with open(
                d / "interventions.jsonl", "a", encoding="utf-8"
            ) as fh:
                fh.write(json.dumps(intervention.to_dict()) + "\n")
        except OSError:
            logger.debug("Failed to persist intervention")

    def _update_activity(self) -> None:
        self.last_activity = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, run_dir: Path, config: HITLConfig) -> HITLSession | None:
        """Load an existing HITL session from run_dir/hitl/session.json."""
        session_file = run_dir / "hitl" / "session.json"
        if not session_file.exists():
            return None
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            session = cls(
                session_id=data.get("session_id", ""),
                run_id=data.get("run_id", ""),
                config=config,
                state=data.get("state", SessionState.ACTIVE),
                run_dir=run_dir,
                human_edits=data.get("human_edits", []),
                total_human_time_sec=data.get("total_human_time_sec", 0.0),
                interventions_count=data.get("interventions_count", 0),
                created_at=data.get("created_at", ""),
                last_activity=data.get("last_activity", ""),
            )
            # Restore waiting state if present
            waiting_file = run_dir / "hitl" / "waiting.json"
            if waiting_file.exists():
                wdata = json.loads(
                    waiting_file.read_text(encoding="utf-8")
                )
                session._waiting = WaitingState.from_dict(wdata)
                session.state = SessionState.WAITING_HUMAN
            return session
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            logger.warning("Failed to load HITL session: %s", exc)
            return None


def _action_to_intervention_type(action: HumanAction) -> InterventionType:
    """Map a human action to an intervention type for logging."""
    mapping = {
        HumanAction.APPROVE: InterventionType.APPROVE,
        HumanAction.REJECT: InterventionType.REJECT,
        HumanAction.EDIT: InterventionType.EDIT_OUTPUT,
        HumanAction.SKIP: InterventionType.SKIP_STAGE,
        HumanAction.COLLABORATE: InterventionType.START_CHAT,
        HumanAction.INJECT: InterventionType.INJECT_GUIDANCE,
        HumanAction.ROLLBACK: InterventionType.ROLLBACK,
        HumanAction.TAKE_OVER: InterventionType.TAKE_OVER,
        HumanAction.RESUME: InterventionType.APPROVE,
        HumanAction.ABORT: InterventionType.REJECT,
    }
    return mapping.get(action, InterventionType.VIEW_OUTPUT)
