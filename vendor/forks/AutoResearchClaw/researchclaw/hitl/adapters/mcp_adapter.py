"""MCP adapter for HITL: expose intervention endpoints to external agents.

External agents (Claude, OpenClaw) can interact with the HITL system
via MCP tool calls to approve gates, inject guidance, or review outputs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    PauseReason,
    WaitingState,
)

logger = logging.getLogger(__name__)


# MCP tool definitions for HITL
HITL_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "hitl_get_status",
        "description": "Get the current HITL session status for a pipeline run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Pipeline run ID"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "hitl_approve_stage",
        "description": "Approve the current stage and continue the pipeline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "message": {"type": "string", "description": "Optional approval note"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "hitl_reject_stage",
        "description": "Reject the current stage output and trigger rollback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "reason": {"type": "string", "description": "Rejection reason"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "hitl_inject_guidance",
        "description": "Inject guidance/direction for the current or next stage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "stage": {"type": "integer", "description": "Target stage number"},
                "guidance": {"type": "string", "description": "Guidance text"},
            },
            "required": ["run_id", "stage", "guidance"],
        },
    },
    {
        "name": "hitl_view_output",
        "description": "View the output of a specific pipeline stage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "stage": {"type": "integer"},
                "filename": {"type": "string", "description": "Specific file to view (optional)"},
            },
            "required": ["run_id", "stage"],
        },
    },
]


class MCPHITLAdapter:
    """Handle HITL-related MCP tool calls.

    This adapter reads/writes to the run directory's hitl/ folder
    to communicate with the pipeline process.
    """

    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir

    async def handle_tool_call(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Route MCP tool calls to handlers."""
        handlers = {
            "hitl_get_status": self._handle_get_status,
            "hitl_approve_stage": self._handle_approve,
            "hitl_reject_stage": self._handle_reject,
            "hitl_inject_guidance": self._handle_inject,
            "hitl_view_output": self._handle_view_output,
        }

        handler = handlers.get(name)
        if handler is None:
            return {"error": f"Unknown HITL tool: {name}", "success": False}

        try:
            return await handler(arguments)
        except Exception as exc:
            return {"error": str(exc), "success": False}

    async def _handle_get_status(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        run_dir = self._resolve_run_dir(args["run_id"])
        if run_dir is None:
            return {"error": "Run not found", "success": False}

        session_path = run_dir / "hitl" / "session.json"
        waiting_path = run_dir / "hitl" / "waiting.json"

        result: dict[str, Any] = {"success": True, "run_id": args["run_id"]}

        if session_path.exists():
            result["session"] = json.loads(
                session_path.read_text(encoding="utf-8")
            )

        if waiting_path.exists():
            result["waiting"] = json.loads(
                waiting_path.read_text(encoding="utf-8")
            )
            result["needs_input"] = True
        else:
            result["needs_input"] = False

        return result

    async def _handle_approve(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        run_dir = self._resolve_run_dir(args["run_id"])
        if run_dir is None:
            return {"error": "Run not found", "success": False}

        # Write approval response for the pipeline to pick up
        response = {
            "action": "approve",
            "message": args.get("message", ""),
        }
        response_path = run_dir / "hitl" / "response.json"
        response_path.parent.mkdir(parents=True, exist_ok=True)
        response_path.write_text(
            json.dumps(response, indent=2), encoding="utf-8"
        )

        return {"success": True, "action": "approve"}

    async def _handle_reject(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        run_dir = self._resolve_run_dir(args["run_id"])
        if run_dir is None:
            return {"error": "Run not found", "success": False}

        response = {
            "action": "reject",
            "message": args.get("reason", ""),
        }
        response_path = run_dir / "hitl" / "response.json"
        response_path.parent.mkdir(parents=True, exist_ok=True)
        response_path.write_text(
            json.dumps(response, indent=2), encoding="utf-8"
        )

        return {"success": True, "action": "reject"}

    async def _handle_inject(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        run_dir = self._resolve_run_dir(args["run_id"])
        if run_dir is None:
            return {"error": "Run not found", "success": False}

        stage = args["stage"]
        guidance = args["guidance"]

        # Write guidance file
        guidance_dir = run_dir / "hitl" / "guidance"
        guidance_dir.mkdir(parents=True, exist_ok=True)
        (guidance_dir / f"stage_{stage:02d}.md").write_text(
            guidance, encoding="utf-8"
        )

        # Also write to stage dir for the executor to pick up
        stage_dir = run_dir / f"stage-{stage:02d}"
        stage_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / "hitl_guidance.md").write_text(
            guidance, encoding="utf-8"
        )

        return {
            "success": True,
            "stage": stage,
            "guidance_length": len(guidance),
        }

    async def _handle_view_output(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        run_dir = self._resolve_run_dir(args["run_id"])
        if run_dir is None:
            return {"error": "Run not found", "success": False}

        stage = args["stage"]
        stage_dir = run_dir / f"stage-{stage:02d}"
        if not stage_dir.exists():
            return {"error": f"Stage {stage} not found", "success": False}

        filename = args.get("filename")
        if filename:
            fpath = stage_dir / filename
            if fpath.is_file():
                content = fpath.read_text(encoding="utf-8")
                return {
                    "success": True,
                    "filename": filename,
                    "content": content[:5000],
                    "truncated": len(content) > 5000,
                }
            return {"error": f"File not found: {filename}", "success": False}

        # List all files
        files = []
        for f in sorted(stage_dir.iterdir()):
            if f.name.startswith("."):
                continue
            info = {"name": f.name, "is_dir": f.is_dir()}
            if f.is_file():
                info["size"] = f.stat().st_size
            files.append(info)

        return {"success": True, "stage": stage, "files": files}

    def _resolve_run_dir(self, run_id: str) -> Path | None:
        """Find the run directory for a given run ID."""
        # Direct path
        candidate = self.artifacts_dir / run_id
        if candidate.is_dir():
            return candidate

        # Search in artifacts dir
        if self.artifacts_dir.exists():
            for d in self.artifacts_dir.iterdir():
                if d.is_dir() and run_id in d.name:
                    return d

        return None
