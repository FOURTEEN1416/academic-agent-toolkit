"""WebSocket adapter for HITL: real-time browser-based interaction.

Enables the web dashboard to:
- Receive real-time pipeline status updates
- View stage outputs when paused
- Submit approve/reject/edit/collaborate decisions
- Stream chat messages during collaboration

Uses file-based IPC (waiting.json / response.json) for communication
with the pipeline process, and WebSocket for real-time browser updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Protocol

from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    PauseReason,
    WaitingState,
)

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_SEC = 1.0


class WebSocketLike(Protocol):
    """Minimal WebSocket interface compatible with FastAPI/Starlette."""

    async def send_text(self, data: str) -> None: ...
    async def receive_text(self) -> str: ...
    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class WebSocketHITLAdapter:
    """WebSocket-based HITL adapter for the web dashboard.

    Bridges browser ↔ pipeline via two channels:
    - WebSocket: real-time bidirectional messaging with the browser
    - File IPC: waiting.json / response.json for pipeline communication

    Usage with FastAPI::

        @app.websocket("/ws/hitl/{run_id}")
        async def hitl_ws(websocket: WebSocket, run_id: str):
            await websocket.accept()
            adapter = WebSocketHITLAdapter(
                ws=websocket,
                artifacts_dir=Path("projects"),
                run_id=run_id,
            )
            await adapter.run()
    """

    def __init__(
        self,
        ws: WebSocketLike,
        artifacts_dir: Path,
        run_id: str,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SEC,
    ) -> None:
        self.ws = ws
        self.artifacts_dir = artifacts_dir
        self.run_id = run_id
        self.poll_interval = poll_interval

        self._run_dir: Path | None = None
        self._hitl_dir: Path | None = None
        self._running = False
        self._last_waiting_mtime: float = 0.0
        self._last_session_mtime: float = 0.0
        self._connected_clients: list[WebSocketLike] = []

    # ── Public API ─────────────────────────────────────────────────

    async def run(self) -> None:
        """Main loop: listen for browser messages + push file changes.

        Runs two concurrent tasks:
        - _receive_loop: handles incoming WebSocket messages from browser
        - poll_and_push: watches file system for state changes, pushes updates
        """
        self._resolve_dirs()
        self._running = True

        try:
            await asyncio.gather(
                self._receive_loop(),
                self.poll_and_push(),
            )
        except Exception as exc:
            logger.debug("WebSocket session ended: %s", exc)
        finally:
            self._running = False

    async def poll_and_push(self) -> None:
        """Watch for file changes and push status updates to the browser.

        Monitors waiting.json and session.json for modifications and
        sends status_update messages when changes are detected.
        """
        while self._running:
            try:
                await self._check_and_push_updates()
            except Exception as exc:
                logger.warning("Poll error: %s", exc)
            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        """Gracefully stop the adapter."""
        self._running = False

    # ── Outbound messages (adapter → browser) ─────────────────────

    async def send_status_update(
        self,
        session: dict[str, Any] | None = None,
        waiting: dict[str, Any] | None = None,
    ) -> None:
        """Push a status update to the browser."""
        await self._send({
            "type": "status_update",
            "session": session,
            "waiting": waiting,
        })

    async def send_stage_output(
        self, stage: int, files: list[dict[str, Any]]
    ) -> None:
        """Push stage output file listing to the browser."""
        await self._send({
            "type": "stage_output",
            "stage": stage,
            "files": files,
        })

    async def send_chat_response(self, content: str) -> None:
        """Push a chat response to the browser (collaboration mode)."""
        await self._send({
            "type": "chat_response",
            "content": content,
        })

    async def send_notification(
        self, title: str, level: str = "info", detail: str = ""
    ) -> None:
        """Push a notification to the browser."""
        msg: dict[str, Any] = {
            "type": "notification",
            "title": title,
            "level": level,
        }
        if detail:
            msg["detail"] = detail
        await self._send(msg)

    # ── HITLAdapter protocol methods ──────────────────────────────

    def collect_input(self, waiting: WaitingState) -> HumanInput:
        """Not used directly — WebSocket interaction is async message-based."""
        raise NotImplementedError(
            "WebSocket adapter uses async message handling, not collect_input"
        )

    async def show_stage_output(
        self, stage_num: int, stage_name: str, summary: str
    ) -> None:
        """Send stage output summary to the browser."""
        await self.send_notification(
            title=f"Stage {stage_num:02d}: {stage_name}",
            level="info",
            detail=summary,
        )

    async def show_message(self, message: str) -> None:
        """Send an informational message to the browser."""
        await self.send_notification(title=message, level="info")

    async def show_error(self, message: str) -> None:
        """Send an error message to the browser."""
        await self.send_notification(title=message, level="error")

    async def show_progress(
        self, stage_num: int, total: int, stage_name: str, status: str
    ) -> None:
        """Send progress update to the browser."""
        await self._send({
            "type": "status_update",
            "progress": {
                "stage": stage_num,
                "total": total,
                "stage_name": stage_name,
                "status": status,
                "percent": round(stage_num / total * 100) if total else 0,
            },
        })

    # ── Inbound message handling (browser → adapter) ──────────────

    async def _receive_loop(self) -> None:
        """Listen for incoming WebSocket messages from the browser."""
        while self._running:
            try:
                raw = await self.ws.receive_text()
            except Exception:
                # Connection closed
                self._running = False
                return

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await self._send_error("Invalid JSON")
                continue

            msg_type = msg.get("type", "")
            handler = self._inbound_handlers.get(msg_type)
            if handler is None:
                await self._send_error(f"Unknown message type: {msg_type}")
                continue

            try:
                await handler(self, msg)
            except Exception as exc:
                logger.exception("Error handling %s", msg_type)
                await self._send_error(f"Error handling {msg_type}: {exc}")

    async def _handle_get_status(self, msg: dict[str, Any]) -> None:
        """Handle get_status request from browser."""
        session = self._read_json("session.json")
        waiting = self._read_json("waiting.json")
        await self.send_status_update(session=session, waiting=waiting)

    async def _handle_approve(self, msg: dict[str, Any]) -> None:
        """Handle approve action from browser."""
        human_input = HumanInput(
            action=HumanAction.APPROVE,
            message=msg.get("message", ""),
        )
        self._write_response(human_input)
        await self.send_notification(
            title="Approved", level="success"
        )

    async def _handle_reject(self, msg: dict[str, Any]) -> None:
        """Handle reject action from browser."""
        human_input = HumanInput(
            action=HumanAction.REJECT,
            message=msg.get("reason", ""),
        )
        self._write_response(human_input)
        await self.send_notification(
            title="Rejected", level="warning",
            detail=msg.get("reason", ""),
        )

    async def _handle_edit(self, msg: dict[str, Any]) -> None:
        """Handle edit action from browser.

        Expects ``{"type": "edit", "files": {"filename": "content", ...}}``.
        Writes files to the stage directory and sends a response.
        """
        files: dict[str, str] = msg.get("files", {})
        if not files:
            await self._send_error("No files provided for edit")
            return

        # Determine current stage from waiting.json
        waiting_data = self._read_json("waiting.json")
        if not waiting_data:
            await self._send_error("No active pause — cannot edit")
            return

        stage = waiting_data.get("stage", 0)
        run_dir = self._get_run_dir()
        if run_dir is None:
            await self._send_error("Run directory not found")
            return

        stage_dir = run_dir / f"stage-{stage:02d}"
        stage_dir.mkdir(parents=True, exist_ok=True)

        # Save backups and write edited files
        snapshots_dir = run_dir / "hitl" / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)

        for fname, content in files.items():
            # SECURITY: Prevent path traversal attacks
            safe_name = Path(fname).name  # Strip any directory components
            if not safe_name or safe_name.startswith("."):
                continue
            fpath = stage_dir / safe_name
            # Verify resolved path is within stage_dir
            try:
                fpath.resolve().relative_to(stage_dir.resolve())
            except ValueError:
                continue  # Skip files that would escape the stage dir
            # Backup original if it exists
            backup = snapshots_dir / f"stage_{stage:02d}_{safe_name}.orig"
            if fpath.is_file() and not backup.exists():
                backup.write_text(
                    fpath.read_text(encoding="utf-8"), encoding="utf-8"
                )
            fpath.write_text(content, encoding="utf-8")

        human_input = HumanInput(
            action=HumanAction.EDIT,
            edited_files=files,
            message=f"Edited {len(files)} file(s) via web dashboard",
        )
        self._write_response(human_input)
        await self.send_notification(
            title=f"Edited {len(files)} file(s)",
            level="success",
        )

    async def _handle_inject_guidance(self, msg: dict[str, Any]) -> None:
        """Handle inject_guidance action from browser."""
        stage = msg.get("stage")
        guidance = msg.get("guidance", "")

        if stage is None or not guidance:
            await self._send_error(
                "inject_guidance requires 'stage' and 'guidance'"
            )
            return

        run_dir = self._get_run_dir()
        if run_dir is None:
            await self._send_error("Run directory not found")
            return

        # Write guidance to hitl/guidance/
        guidance_dir = run_dir / "hitl" / "guidance"
        guidance_dir.mkdir(parents=True, exist_ok=True)
        (guidance_dir / f"stage_{stage:02d}.md").write_text(
            guidance, encoding="utf-8"
        )

        # Also write to stage dir for executor pickup
        stage_dir = run_dir / f"stage-{stage:02d}"
        stage_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / "hitl_guidance.md").write_text(
            guidance, encoding="utf-8"
        )

        await self.send_notification(
            title=f"Guidance injected for stage {stage}",
            level="success",
            detail=guidance[:200],
        )

    async def _handle_chat_message(self, msg: dict[str, Any]) -> None:
        """Handle chat_message for collaboration sessions.

        Writes the message to a chat log file for the pipeline to pick up.
        """
        content = msg.get("content", "")
        if not content:
            return

        run_dir = self._get_run_dir()
        if run_dir is None:
            await self._send_error("Run directory not found")
            return

        chat_dir = run_dir / "hitl" / "chat"
        chat_dir.mkdir(parents=True, exist_ok=True)

        # Append to chat log as JSONL
        chat_entry = json.dumps({
            "role": "human",
            "content": content,
        })
        chat_log = chat_dir / "messages.jsonl"
        with chat_log.open("a", encoding="utf-8") as f:
            f.write(chat_entry + "\n")

        # Acknowledge receipt
        await self._send({
            "type": "chat_response",
            "content": f"Message received: {content[:100]}",
        })

    # Handler dispatch table
    _inbound_handlers: dict[str, Any] = {
        "get_status": _handle_get_status,
        "approve": _handle_approve,
        "reject": _handle_reject,
        "edit": _handle_edit,
        "inject_guidance": _handle_inject_guidance,
        "chat_message": _handle_chat_message,
    }

    # ── File IPC helpers ──────────────────────────────────────────

    def _resolve_dirs(self) -> None:
        """Resolve run_dir and hitl_dir from artifacts_dir + run_id."""
        self._run_dir = self._get_run_dir()
        if self._run_dir is not None:
            self._hitl_dir = self._run_dir / "hitl"
            self._hitl_dir.mkdir(parents=True, exist_ok=True)

    def _get_run_dir(self) -> Path | None:
        """Find the run directory for the current run_id."""
        candidate = self.artifacts_dir / self.run_id
        if candidate.is_dir():
            return candidate

        # Search by partial match
        if self.artifacts_dir.exists():
            for d in self.artifacts_dir.iterdir():
                if d.is_dir() and self.run_id in d.name:
                    return d
        return None

    def _read_json(self, filename: str) -> dict[str, Any] | None:
        """Read a JSON file from the hitl directory."""
        if self._hitl_dir is None:
            return None
        path = self._hitl_dir / filename
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None

    def _write_response(self, human_input: HumanInput) -> None:
        """Write response.json for the pipeline to pick up."""
        if self._hitl_dir is None:
            self._resolve_dirs()
        if self._hitl_dir is None:
            logger.error("Cannot write response — hitl_dir not resolved")
            return

        self._hitl_dir.mkdir(parents=True, exist_ok=True)
        response_path = self._hitl_dir / "response.json"
        response_path.write_text(
            json.dumps(human_input.to_dict(), indent=2), encoding="utf-8"
        )

    async def _check_and_push_updates(self) -> None:
        """Check for file changes and push updates if needed."""
        if self._hitl_dir is None:
            # Run dir may not exist yet; try to resolve
            self._resolve_dirs()
            if self._hitl_dir is None:
                return

        waiting_path = self._hitl_dir / "waiting.json"
        session_path = self._hitl_dir / "session.json"

        changed = False
        session_data = None
        waiting_data = None

        if session_path.exists():
            mtime = session_path.stat().st_mtime
            if mtime != self._last_session_mtime:
                self._last_session_mtime = mtime
                session_data = self._read_json("session.json")
                changed = True

        if waiting_path.exists():
            mtime = waiting_path.stat().st_mtime
            if mtime != self._last_waiting_mtime:
                self._last_waiting_mtime = mtime
                waiting_data = self._read_json("waiting.json")
                changed = True
        elif self._last_waiting_mtime != 0.0:
            # waiting.json was removed (response consumed)
            self._last_waiting_mtime = 0.0
            changed = True

        if changed:
            await self.send_status_update(
                session=session_data, waiting=waiting_data
            )

    # ── Transport helpers ─────────────────────────────────────────

    async def _send(self, msg: dict[str, Any]) -> None:
        """Send a JSON message over the WebSocket."""
        try:
            await self.ws.send_text(json.dumps(msg))
        except Exception as exc:
            logger.debug("Failed to send message: %s", exc)
            self._running = False

    async def _send_error(self, detail: str) -> None:
        """Send an error notification to the browser."""
        await self._send({
            "type": "notification",
            "title": detail,
            "level": "error",
        })
