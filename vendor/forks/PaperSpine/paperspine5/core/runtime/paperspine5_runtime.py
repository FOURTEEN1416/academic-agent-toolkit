"""Host-neutral local MCP and JSON bridge for PaperSpine5.

The runtime intentionally contains no paper-writing logic.  It locates the
project's canonical integration core and translates host calls into that API.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


for _stream in (sys.stdin, sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="strict")


SERVER_NAME = "paperspine5-local"
SERVER_VERSION = "0.3.0-rc.1"
SERVER_BUILD_ID = "paperspine5-0.3.0-rc.1-build.20260823.1"
BRIDGE_PROTOCOL = "paperspine5.host"
BRIDGE_VERSION = "0.1.0"
SUPPORTED_HOSTS = {"codex", "claude-code", "dsh", "standalone-skill"}
_SERVERS: dict[str, tuple[Any, threading.Thread]] = {}


class RuntimeErrorWithContext(RuntimeError):
    """A user-facing runtime failure with a stable message."""


def _trace(event: str, **fields: Any) -> None:
    """Write opt-in protocol diagnostics without recording tool arguments."""
    target = os.environ.get("PAPERSPINE5_MCP_TRACE")
    if not target:
        return
    record = {
        "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event,
        **fields,
    }
    try:
        with Path(target).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _runtime_dir() -> Path:
    return Path(__file__).resolve().parent


def locate_project_root(explicit: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("PAPERSPINE5_PROJECT_ROOT"):
        candidates.append(Path(os.environ["PAPERSPINE5_PROJECT_ROOT"]))

    config_paths = [
        _runtime_dir() / "local-project.json",
        _runtime_dir().parent / "config" / "local-project.json",
    ]
    for config_path in config_paths:
        if not config_path.is_file():
            continue
        try:
            value = json.loads(config_path.read_text(encoding="utf-8-sig")).get("project_root")
        except (OSError, ValueError, AttributeError):
            value = None
        if isinstance(value, str) and value.strip():
            candidate = Path(value)
            candidates.append(candidate if candidate.is_absolute() else config_path.parent / candidate)

    candidates.extend([_runtime_dir(), *_runtime_dir().parents])
    for candidate in candidates:
        root = candidate.resolve()
        expected = root / "03_联合开发" / "src" / "paperspine_figure_integration" / "coordinator.py"
        if expected.is_file():
            return root
    raise RuntimeErrorWithContext(
        "PaperSpine5 project root was not found; set PAPERSPINE5_PROJECT_ROOT or update config/local-project.json"
    )


def _load_core(project_root: Path) -> tuple[Any, Any]:
    source = project_root / "03_联合开发" / "src"
    source_text = str(source)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    try:
        from paperspine_figure_integration.coordinator import IntegrationCoordinator
        from paperspine_figure_integration.ui_server import create_server
    except ImportError as exc:  # pragma: no cover - only possible in a broken install
        raise RuntimeErrorWithContext(f"PaperSpine5 core import failed: {exc}") from exc
    return IntegrationCoordinator, create_server


def _job_path(project_root: Path, raw: Any) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeErrorWithContext("job_path is required")
    candidate = Path(raw)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise RuntimeErrorWithContext("job_path must stay inside the PaperSpine5 project root") from exc
    if not resolved.is_file():
        raise RuntimeErrorWithContext(f"integration job does not exist: {resolved}")
    return resolved


def health(project_root: Path, *, detailed: bool = True) -> dict[str, Any]:
    IntegrationCoordinator, _ = _load_core(project_root)
    result: dict[str, Any] = {
        "status": "PASS",
        "runtime": SERVER_NAME,
        "version": SERVER_VERSION,
        "build_id": SERVER_BUILD_ID,
    }
    if detailed:
        result.update(
            {
                "project_root": str(project_root),
                "core": f"{IntegrationCoordinator.__module__}.{IntegrationCoordinator.__name__}",
                "transport": ["mcp-stdio", "json-bridge"],
                "hosts": sorted(SUPPORTED_HOSTS),
            }
        )
    return result


def dispatch(action: str, arguments: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _trace("dispatch.start", action=action)
    if action == "health":
        # Tool results may be sent to a hosted model; keep local paths on-device.
        result = health(project_root, detailed=False)
        _trace("dispatch.complete", action=action, status=result.get("status"))
        return result

    IntegrationCoordinator, create_server = _load_core(project_root)
    job_path = _job_path(project_root, arguments.get("job_path"))
    coordinator = IntegrationCoordinator(job_path)
    host = arguments.get("host")
    if host is not None and host not in SUPPORTED_HOSTS:
        raise RuntimeErrorWithContext(f"unsupported host: {host}")

    if action == "snapshot":
        result = coordinator.snapshot()
        if host:
            result["host_next"] = coordinator.host_next(host)
        return result
    if action == "save_configuration":
        configuration = arguments.get("configuration")
        if not isinstance(configuration, dict):
            raise RuntimeErrorWithContext("configuration must be a JSON object")
        return coordinator.save_configuration(configuration)
    if action == "advance":
        return coordinator.resume() if coordinator.state()["stage"] == "blocked" else coordinator.advance()
    if action == "record_decision":
        decision = arguments.get("decision")
        if not isinstance(decision, dict):
            raise RuntimeErrorWithContext("decision must be a JSON object")
        return coordinator.record_decision(decision)
    if action == "record_signal":
        signal = arguments.get("signal")
        if not isinstance(signal, dict):
            raise RuntimeErrorWithContext("signal must be a JSON object")
        return coordinator.record_signal(signal)
    if action == "open_workspace":
        key = str(job_path)
        current = _SERVERS.get(key)
        if current and current[1].is_alive():
            server = current[0]
        else:
            server = create_server(job_path, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True, name=f"paperspine5-ui-{server.server_port}")
            thread.start()
            _SERVERS[key] = (server, thread)
        return {
            "status": "READY",
            "address": f"http://127.0.0.1:{server.server_port}/",
            "job_path": str(job_path),
            "lifecycle": "owned-by-mcp-process",
        }
    raise RuntimeErrorWithContext(f"unsupported action: {action}")


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": required,
        },
    }


JOB = {"type": "string", "description": "Absolute path, or project-relative path, to integration_job.json."}
HOST = {"type": "string", "enum": sorted(SUPPORTED_HOSTS), "description": "Host projection for next-action guidance."}


TOOLS = [
    _tool("paperspine5_health", "Verify the shared PaperSpine5 runtime and canonical core location.", {}, []),
    _tool("paperspine5_status", "Read the persistent workflow snapshot and host-specific next action.", {"job_path": JOB, "host": HOST}, ["job_path"]),
    _tool("paperspine5_save_configuration", "Validate and save the PaperSpine configuration before the workflow advances.", {"job_path": JOB, "configuration": {"type": "object"}}, ["job_path", "configuration"]),
    _tool("paperspine5_advance", "Advance or resume the PaperSpine and PaperFigure state machine by one safe boundary.", {"job_path": JOB}, ["job_path"]),
    _tool("paperspine5_record_decision", "Persist a complete human figure-review decision and continue assembly.", {"job_path": JOB, "decision": {"type": "object"}}, ["job_path", "decision"]),
    _tool("paperspine5_record_signal", "Persist a host-neutral confirmation or continue signal.", {"job_path": JOB, "signal": {"type": "object"}}, ["job_path", "signal"]),
    _tool("paperspine5_open_workspace", "Start the loopback-only PaperSpine5 workspace and return its local URL.", {"job_path": JOB}, ["job_path"]),
]


def _result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
    }
    if is_error:
        result["isError"] = True
    return result


def _response(request_id: Any, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    payload["error" if error is not None else "result"] = error if error is not None else result
    return payload


def handle_mcp(message: dict[str, Any], project_root: Path) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if request_id is None:
        return None
    if method == "initialize":
        requested = (message.get("params") or {}).get("protocolVersion")
        return _response(
            request_id,
            {
                "protocolVersion": requested or "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        action = {
            "paperspine5_health": "health",
            "paperspine5_status": "snapshot",
            "paperspine5_save_configuration": "save_configuration",
            "paperspine5_advance": "advance",
            "paperspine5_record_decision": "record_decision",
            "paperspine5_record_signal": "record_signal",
            "paperspine5_open_workspace": "open_workspace",
        }.get(tool_name)
        if action is None:
            return _response(request_id, _result({"status": "FAIL", "error": f"unknown tool: {tool_name}"}, is_error=True))
        try:
            return _response(request_id, _result(dispatch(action, arguments, project_root)))
        except Exception as exc:  # MCP boundary converts domain errors into tool errors.
            return _response(request_id, _result({"status": "FAIL", "error": str(exc)}, is_error=True))
    return _response(request_id, error={"code": -32601, "message": f"method not found: {method}"})


def serve_stdio(project_root: Path, input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout) -> int:
    for line in input_stream:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("message must be a JSON object")
            _trace("mcp.received", method=message.get("method"), has_id=message.get("id") is not None)
            response = handle_mcp(message, project_root)
        except Exception as exc:
            _trace("mcp.exception", error=str(exc))
            response = _response(None, error={"code": -32700, "message": str(exc)})
        if response is not None:
            # ASCII-only framing avoids Windows locale encodings corrupting JSON-RPC pipes.
            output_stream.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")
            output_stream.flush()
            _trace("mcp.sent", response_id=response.get("id"), has_error="error" in response)
    for server, thread in _SERVERS.values():
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    return 0


def serve_bridge(project_root: Path, input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout) -> int:
    try:
        envelope = json.load(input_stream)
        if not isinstance(envelope, dict):
            raise RuntimeErrorWithContext("bridge request must be a JSON object")
        if envelope.get("protocol") != BRIDGE_PROTOCOL or envelope.get("version") != BRIDGE_VERSION:
            raise RuntimeErrorWithContext("bridge protocol or version is unsupported")
        host = envelope.get("host")
        if host not in SUPPORTED_HOSTS:
            raise RuntimeErrorWithContext("bridge host is unsupported")
        arguments = {**(envelope.get("payload") or {}), "job_path": envelope.get("job_path"), "host": host}
        result = dispatch(str(envelope.get("action")), arguments, project_root)
        payload = {"status": "OK", "request_id": envelope.get("request_id"), "result": result}
        code = 0
    except Exception as exc:
        payload = {"status": "FAIL", "error": str(exc)}
        code = 1
    output_stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    output_stream.flush()
    return code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PaperSpine5 local host runtime")
    parser.add_argument("mode", nargs="?", choices=("mcp", "bridge", "health"), default="mcp")
    parser.add_argument("--project-root")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        project_root = locate_project_root(args.project_root)
        if args.mode == "mcp":
            return serve_stdio(project_root)
        if args.mode == "bridge":
            return serve_bridge(project_root)
        print(json.dumps(health(project_root), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
