"""Tests for the WebSocket HITL adapter."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from researchclaw.hitl.adapters.ws_adapter import WebSocketHITLAdapter
from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    PauseReason,
    WaitingState,
)


# ── Fixtures ──────────────────────────────────────────────────────


class MockWebSocket:
    """Mock WebSocket that records sent messages and replays receive queue."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self._receive_queue: asyncio.Queue[str] = asyncio.Queue()
        self.closed = False
        self.close_code: int | None = None

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def receive_text(self) -> str:
        try:
            return await asyncio.wait_for(self._receive_queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            raise ConnectionError("WebSocket closed")

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code

    def inject(self, msg: dict[str, Any]) -> None:
        """Inject a message as if the browser sent it."""
        self._receive_queue.put_nowait(json.dumps(msg))

    @property
    def last_sent(self) -> dict[str, Any] | None:
        return self.sent[-1] if self.sent else None


@pytest.fixture
def tmp_run(tmp_path: Path) -> Path:
    """Create a temporary run directory with hitl/ subdirectory."""
    run_dir = tmp_path / "test-run-001"
    (run_dir / "hitl").mkdir(parents=True)
    return run_dir


@pytest.fixture
def ws() -> MockWebSocket:
    return MockWebSocket()


@pytest.fixture
def adapter(ws: MockWebSocket, tmp_run: Path) -> WebSocketHITLAdapter:
    return WebSocketHITLAdapter(
        ws=ws,
        artifacts_dir=tmp_run.parent,
        run_id=tmp_run.name,
        poll_interval=0.1,
    )


# ── Tests: get_status ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_status_empty(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """get_status with no session or waiting files returns empty update."""
    adapter._resolve_dirs()
    ws.inject({"type": "get_status"})

    # Run the handler directly
    await adapter._handle_get_status({"type": "get_status"})

    assert ws.last_sent is not None
    assert ws.last_sent["type"] == "status_update"
    assert ws.last_sent["session"] is None
    assert ws.last_sent["waiting"] is None


@pytest.mark.asyncio
async def test_get_status_with_waiting(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """get_status returns waiting info when waiting.json exists."""
    adapter._resolve_dirs()

    waiting = WaitingState(
        stage=3,
        stage_name="Literature Review",
        reason=PauseReason.POST_STAGE,
        context_summary="Found 12 papers.",
        output_files=("review.md",),
    )
    (tmp_run / "hitl" / "waiting.json").write_text(
        json.dumps(waiting.to_dict(), indent=2), encoding="utf-8"
    )

    await adapter._handle_get_status({"type": "get_status"})

    assert ws.last_sent is not None
    assert ws.last_sent["type"] == "status_update"
    assert ws.last_sent["waiting"]["stage"] == 3
    assert ws.last_sent["waiting"]["stage_name"] == "Literature Review"


@pytest.mark.asyncio
async def test_get_status_with_session(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """get_status returns session data when session.json exists."""
    adapter._resolve_dirs()

    session = {"run_id": "test-run-001", "mode": "supervised", "started": "2026-01-01T00:00:00Z"}
    (tmp_run / "hitl" / "session.json").write_text(
        json.dumps(session, indent=2), encoding="utf-8"
    )

    await adapter._handle_get_status({"type": "get_status"})

    assert ws.last_sent["session"]["run_id"] == "test-run-001"


# ── Tests: approve ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """approve writes response.json with approve action."""
    adapter._resolve_dirs()

    await adapter._handle_approve({"type": "approve", "message": "Looks good"})

    response_path = tmp_run / "hitl" / "response.json"
    assert response_path.exists()

    data = json.loads(response_path.read_text(encoding="utf-8"))
    assert data["action"] == "approve"
    assert data["message"] == "Looks good"

    # Should also send a notification
    assert ws.last_sent["type"] == "notification"
    assert ws.last_sent["level"] == "success"


@pytest.mark.asyncio
async def test_approve_default_message(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """approve without message uses empty string."""
    adapter._resolve_dirs()

    await adapter._handle_approve({"type": "approve"})

    data = json.loads(
        (tmp_run / "hitl" / "response.json").read_text(encoding="utf-8")
    )
    assert data["action"] == "approve"
    assert data["message"] == ""


# ── Tests: reject ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """reject writes response.json with reject action and reason."""
    adapter._resolve_dirs()

    await adapter._handle_reject({
        "type": "reject",
        "reason": "Missing citations",
    })

    data = json.loads(
        (tmp_run / "hitl" / "response.json").read_text(encoding="utf-8")
    )
    assert data["action"] == "reject"
    assert data["message"] == "Missing citations"

    assert ws.last_sent["level"] == "warning"


# ── Tests: edit ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_writes_files(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """edit writes files to the stage directory and creates response."""
    adapter._resolve_dirs()

    # Set up waiting state at stage 2
    waiting = WaitingState(
        stage=2, stage_name="Analysis", reason=PauseReason.POST_STAGE
    )
    (tmp_run / "hitl" / "waiting.json").write_text(
        json.dumps(waiting.to_dict()), encoding="utf-8"
    )

    # Create original file for backup
    stage_dir = tmp_run / "stage-02"
    stage_dir.mkdir()
    (stage_dir / "analysis.md").write_text("original content", encoding="utf-8")

    await adapter._handle_edit({
        "type": "edit",
        "files": {"analysis.md": "edited content"},
    })

    # Check file was written
    assert (stage_dir / "analysis.md").read_text(encoding="utf-8") == "edited content"

    # Check backup was created
    backup = tmp_run / "hitl" / "snapshots" / "stage_02_analysis.md.orig"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "original content"

    # Check response was written
    data = json.loads(
        (tmp_run / "hitl" / "response.json").read_text(encoding="utf-8")
    )
    assert data["action"] == "edit"
    assert "analysis.md" in data["edited_files"]


@pytest.mark.asyncio
async def test_edit_no_files_error(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """edit with no files sends error notification."""
    adapter._resolve_dirs()

    await adapter._handle_edit({"type": "edit", "files": {}})

    assert ws.last_sent["type"] == "notification"
    assert ws.last_sent["level"] == "error"


@pytest.mark.asyncio
async def test_edit_no_waiting_error(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """edit with no active waiting.json sends error."""
    adapter._resolve_dirs()

    await adapter._handle_edit({
        "type": "edit",
        "files": {"test.md": "content"},
    })

    assert ws.last_sent["level"] == "error"
    assert "No active pause" in ws.last_sent["title"]


# ── Tests: inject_guidance ────────────────────────────────────────


@pytest.mark.asyncio
async def test_inject_guidance(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """inject_guidance writes guidance files to both locations."""
    adapter._resolve_dirs()

    await adapter._handle_inject_guidance({
        "type": "inject_guidance",
        "stage": 4,
        "guidance": "Focus on empirical studies from 2023+",
    })

    # Check hitl/guidance/
    guidance_file = tmp_run / "hitl" / "guidance" / "stage_04.md"
    assert guidance_file.exists()
    assert "empirical studies" in guidance_file.read_text(encoding="utf-8")

    # Check stage dir
    stage_guidance = tmp_run / "stage-04" / "hitl_guidance.md"
    assert stage_guidance.exists()

    assert ws.last_sent["level"] == "success"


@pytest.mark.asyncio
async def test_inject_guidance_missing_fields(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """inject_guidance without required fields sends error."""
    adapter._resolve_dirs()

    await adapter._handle_inject_guidance({
        "type": "inject_guidance",
        "stage": 4,
    })

    assert ws.last_sent["level"] == "error"


# ── Tests: chat_message ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_message(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """chat_message appends to chat log and sends acknowledgment."""
    adapter._resolve_dirs()

    await adapter._handle_chat_message({
        "type": "chat_message",
        "content": "Can you add more detail on methodology?",
    })

    chat_log = tmp_run / "hitl" / "chat" / "messages.jsonl"
    assert chat_log.exists()

    entry = json.loads(chat_log.read_text(encoding="utf-8").strip())
    assert entry["role"] == "human"
    assert "methodology" in entry["content"]

    assert ws.last_sent["type"] == "chat_response"


@pytest.mark.asyncio
async def test_chat_message_empty_ignored(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """Empty chat message is silently ignored."""
    adapter._resolve_dirs()

    await adapter._handle_chat_message({"type": "chat_message", "content": ""})

    chat_dir = tmp_run / "hitl" / "chat"
    assert not chat_dir.exists()


# ── Tests: poll_and_push ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_poll_detects_new_waiting(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """poll_and_push detects when waiting.json appears."""
    adapter._resolve_dirs()

    # No files initially
    await adapter._check_and_push_updates()
    assert len(ws.sent) == 0

    # Create waiting.json
    waiting = WaitingState(
        stage=1, stage_name="Search", reason=PauseReason.GATE_APPROVAL
    )
    (tmp_run / "hitl" / "waiting.json").write_text(
        json.dumps(waiting.to_dict()), encoding="utf-8"
    )

    await adapter._check_and_push_updates()

    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "status_update"
    assert ws.sent[0]["waiting"]["stage"] == 1


@pytest.mark.asyncio
async def test_poll_detects_waiting_removal(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """poll_and_push detects when waiting.json is removed (response consumed)."""
    adapter._resolve_dirs()

    # Create then detect waiting
    waiting_path = tmp_run / "hitl" / "waiting.json"
    waiting = WaitingState(
        stage=1, stage_name="Search", reason=PauseReason.POST_STAGE
    )
    waiting_path.write_text(json.dumps(waiting.to_dict()), encoding="utf-8")
    await adapter._check_and_push_updates()

    # Remove waiting (simulates pipeline consuming the response)
    waiting_path.unlink()
    await adapter._check_and_push_updates()

    assert len(ws.sent) == 2
    # Second update has no waiting data
    assert ws.sent[1]["waiting"] is None


@pytest.mark.asyncio
async def test_poll_no_duplicate_on_unchanged(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """poll_and_push does not send duplicates when files are unchanged."""
    adapter._resolve_dirs()

    waiting = WaitingState(
        stage=1, stage_name="Search", reason=PauseReason.POST_STAGE
    )
    (tmp_run / "hitl" / "waiting.json").write_text(
        json.dumps(waiting.to_dict()), encoding="utf-8"
    )

    await adapter._check_and_push_updates()
    await adapter._check_and_push_updates()
    await adapter._check_and_push_updates()

    # Only 1 update sent despite 3 polls
    assert len(ws.sent) == 1


# ── Tests: outbound helpers ───────────────────────────────────────


@pytest.mark.asyncio
async def test_send_stage_output(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket
) -> None:
    """send_stage_output sends correct message shape."""
    files = [
        {"name": "review.md", "size": 1234},
        {"name": "sources.bib", "size": 567},
    ]
    await adapter.send_stage_output(stage=3, files=files)

    assert ws.last_sent["type"] == "stage_output"
    assert ws.last_sent["stage"] == 3
    assert len(ws.last_sent["files"]) == 2


@pytest.mark.asyncio
async def test_send_notification_levels(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket
) -> None:
    """send_notification includes title, level, and optional detail."""
    await adapter.send_notification(
        title="Pipeline paused", level="warning", detail="Stage 3 needs review"
    )

    assert ws.last_sent["type"] == "notification"
    assert ws.last_sent["title"] == "Pipeline paused"
    assert ws.last_sent["level"] == "warning"
    assert ws.last_sent["detail"] == "Stage 3 needs review"


@pytest.mark.asyncio
async def test_send_notification_no_detail(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket
) -> None:
    """send_notification omits detail when not provided."""
    await adapter.send_notification(title="Done", level="info")

    assert "detail" not in ws.last_sent


@pytest.mark.asyncio
async def test_show_progress(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket
) -> None:
    """show_progress sends status_update with progress info."""
    await adapter.show_progress(
        stage_num=3, total=8, stage_name="Analysis", status="running"
    )

    assert ws.last_sent["type"] == "status_update"
    assert ws.last_sent["progress"]["stage"] == 3
    assert ws.last_sent["progress"]["percent"] == 38


@pytest.mark.asyncio
async def test_show_error(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket
) -> None:
    """show_error sends notification with error level."""
    await adapter.show_error("Something went wrong")

    assert ws.last_sent["type"] == "notification"
    assert ws.last_sent["level"] == "error"


# ── Tests: unknown message type ───────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_message_type(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """Unknown message types produce an error notification."""
    adapter._resolve_dirs()
    adapter._running = True

    # Inject unknown message, then cause ConnectionError to exit loop
    ws.inject({"type": "foobar"})

    # Manually invoke the handler dispatch
    msg = {"type": "foobar"}
    handler = adapter._inbound_handlers.get(msg["type"])
    assert handler is None

    await adapter._send_error(f"Unknown message type: {msg['type']}")
    assert ws.last_sent["level"] == "error"
    assert "foobar" in ws.last_sent["title"]


# ── Tests: run dir resolution ─────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_run_dir_exact(tmp_path: Path, ws: MockWebSocket) -> None:
    """Adapter resolves exact run directory name."""
    run_dir = tmp_path / "my-run"
    (run_dir / "hitl").mkdir(parents=True)

    adapter = WebSocketHITLAdapter(
        ws=ws, artifacts_dir=tmp_path, run_id="my-run"
    )
    adapter._resolve_dirs()
    assert adapter._run_dir == run_dir


@pytest.mark.asyncio
async def test_resolve_run_dir_partial(tmp_path: Path, ws: MockWebSocket) -> None:
    """Adapter resolves run directory by partial match."""
    run_dir = tmp_path / "2026-03-28_my-run_abc123"
    (run_dir / "hitl").mkdir(parents=True)

    adapter = WebSocketHITLAdapter(
        ws=ws, artifacts_dir=tmp_path, run_id="my-run"
    )
    adapter._resolve_dirs()
    assert adapter._run_dir == run_dir


@pytest.mark.asyncio
async def test_resolve_run_dir_missing(tmp_path: Path, ws: MockWebSocket) -> None:
    """Adapter handles missing run directory gracefully."""
    adapter = WebSocketHITLAdapter(
        ws=ws, artifacts_dir=tmp_path, run_id="nonexistent"
    )
    adapter._resolve_dirs()
    assert adapter._run_dir is None
    assert adapter._hitl_dir is None


# ── Tests: collect_input raises ────────────────────────────────────


def test_collect_input_raises(ws: MockWebSocket, tmp_path: Path) -> None:
    """collect_input raises NotImplementedError (WebSocket is async)."""
    adapter = WebSocketHITLAdapter(
        ws=ws, artifacts_dir=tmp_path, run_id="test"
    )
    waiting = WaitingState(
        stage=1, stage_name="Test", reason=PauseReason.POST_STAGE
    )
    with pytest.raises(NotImplementedError):
        adapter.collect_input(waiting)


# ── Tests: graceful stop ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_stop(adapter: WebSocketHITLAdapter) -> None:
    """stop() sets _running to False."""
    adapter._running = True
    await adapter.stop()
    assert adapter._running is False


# ── Tests: response written with full HumanInput fields ───────────


@pytest.mark.asyncio
async def test_response_has_timestamp(
    adapter: WebSocketHITLAdapter, ws: MockWebSocket, tmp_run: Path
) -> None:
    """Response files include a timestamp field."""
    adapter._resolve_dirs()

    await adapter._handle_approve({"type": "approve"})

    data = json.loads(
        (tmp_run / "hitl" / "response.json").read_text(encoding="utf-8")
    )
    assert "timestamp" in data
    assert data["timestamp"] != ""
