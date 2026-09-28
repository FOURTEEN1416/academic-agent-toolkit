"""File-based async wait: allow pipeline to pause and resume via file IPC.

When the pipeline pauses for human input, it writes ``waiting.json``
and enters a poll loop checking for ``response.json``. This allows:
- The pipeline process to sleep (no stdin blocking)
- External tools (``researchclaw attach``, web dashboard, MCP) to
  write ``response.json`` to provide the human's decision
- The pipeline to pick up the response and resume

This is the key mechanism for detached/async HITL interaction.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    WaitingState,
)

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_SEC = 2.0
DEFAULT_TIMEOUT_SEC = 86400  # 24 hours


def write_waiting(hitl_dir: Path, waiting: WaitingState) -> Path:
    """Write waiting state for external tools to discover."""
    hitl_dir.mkdir(parents=True, exist_ok=True)
    path = hitl_dir / "waiting.json"
    path.write_text(
        json.dumps(waiting.to_dict(), indent=2), encoding="utf-8"
    )
    return path


def write_response(hitl_dir: Path, human_input: HumanInput) -> Path:
    """Write a response file (used by ``attach``, ``approve``, etc)."""
    hitl_dir.mkdir(parents=True, exist_ok=True)
    path = hitl_dir / "response.json"
    path.write_text(
        json.dumps(human_input.to_dict(), indent=2), encoding="utf-8"
    )
    return path


def poll_for_response(
    hitl_dir: Path,
    *,
    poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    auto_proceed_on_timeout: bool = False,
) -> HumanInput:
    """Poll for a response.json file written by an external process.

    Blocks until either:
    - ``response.json`` appears → parse and return HumanInput
    - Timeout → return APPROVE (if auto_proceed) or ABORT

    Args:
        hitl_dir: The hitl/ directory under run_dir.
        poll_interval_sec: How often to check (default 2s).
        timeout_sec: Max wait time (default 24h).
        auto_proceed_on_timeout: If True, auto-approve on timeout.

    Returns:
        HumanInput from the response file.
    """
    response_path = hitl_dir / "response.json"
    deadline = time.monotonic() + timeout_sec

    logger.info(
        "Polling for response at %s (timeout=%ds)",
        response_path,
        timeout_sec,
    )

    consecutive_errors = 0
    max_consecutive_errors = 5

    while time.monotonic() < deadline:
        # Atomic read attempt — skip exists() check to avoid TOCTOU race
        try:
            raw = response_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            human_input = HumanInput.from_dict(data)
            # Clean up response file after reading
            response_path.unlink(missing_ok=True)
            logger.info(
                "Response received: %s", human_input.action.value
            )
            return human_input
        except FileNotFoundError:
            pass  # Normal — no response yet
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            consecutive_errors += 1
            logger.warning(
                "Invalid response file (attempt %d/%d): %s",
                consecutive_errors, max_consecutive_errors, exc,
            )
            response_path.unlink(missing_ok=True)
            if consecutive_errors >= max_consecutive_errors:
                logger.error("Too many invalid response files — aborting poll")
                break
        except OSError:
            pass  # File access issue — retry

        time.sleep(poll_interval_sec)

    # Timeout
    logger.warning("HITL poll timeout after %ds", timeout_sec)
    if auto_proceed_on_timeout:
        return HumanInput(action=HumanAction.APPROVE, message="auto-approved (timeout)")
    return HumanInput(action=HumanAction.ABORT, message="timeout — no response")


def clear_waiting(hitl_dir: Path) -> None:
    """Remove the waiting.json file after response is received."""
    (hitl_dir / "waiting.json").unlink(missing_ok=True)
