"""HITL interface adapters (CLI, WebSocket, MCP)."""

from __future__ import annotations

from typing import Protocol

from researchclaw.hitl.intervention import HumanInput, WaitingState


class HITLAdapter(Protocol):
    """Protocol for HITL input/output adapters."""

    def collect_input(self, waiting: WaitingState) -> HumanInput:
        """Collect human input when the pipeline is paused."""
        ...

    def show_stage_output(
        self, stage_num: int, stage_name: str, summary: str
    ) -> None:
        """Display stage output to the human."""
        ...

    def show_message(self, message: str) -> None:
        """Display an informational message."""
        ...

    def show_error(self, message: str) -> None:
        """Display an error message."""
        ...

    def show_progress(
        self, stage_num: int, total: int, stage_name: str, status: str
    ) -> None:
        """Display stage progress."""
        ...
