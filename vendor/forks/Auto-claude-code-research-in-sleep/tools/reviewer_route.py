#!/usr/bin/env python3
"""Resolve reviewer selection without invoking models or changing host settings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ALIASES = {"gemini": "antigravity", "claude": "claude-code", "claude-review": "claude-code"}
BACKENDS = {"codex", "antigravity", "grok", "claude-code"}
LEGACY_BACKENDS = {"oracle-pro", "agy", "manual", "copilot", "copilot-native"}
HOSTS = {"codex", "claude-code", "copilot"}
TOOLS = {
    "antigravity": ("mcp__antigravity__antigravity", "mcp__antigravity__antigravity-reply"),
    "grok": ("mcp__grok__grok", "mcp__grok__grok-reply"),
    "claude-code": ("mcp__claude-review__review", "mcp__claude-review__review_reply"),
}


def _backend(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("reviewer backend must be a nonempty string")
    backend = ALIASES.get(value, value)
    if backend not in BACKENDS | LEGACY_BACKENDS:
        raise ValueError(f"unknown reviewer backend: {value!r}")
    return backend


def _config(project: str | Path) -> dict:
    path = Path(project) / ".aris" / "reviewer.json"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    try:
        config = json.loads(text)
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"invalid reviewer config {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError(f"reviewer config {path} must be a JSON object")
    unknown = config.keys() - {"backend", "model", "effort"}
    if unknown:
        raise ValueError(f"unknown reviewer config fields in {path}: {', '.join(sorted(unknown))}")
    for field, value in config.items():
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"reviewer config {field} must be a nonempty string or null")
    if "backend" in config:
        config["backend"] = _backend(config["backend"])
    return config


def resolve_route(
    project: str | Path,
    host: str,
    tier: str = "deep",
    reviewer: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    default_reviewer: str | None = None,
) -> dict:
    """Apply inline > project > host-default selection and provider-local options.

    Legacy routes retain their identity and are dispatched by existing callers.
    Returned tool names describe a protocol; availability is checked by callers.
    """
    if host not in HOSTS:
        raise ValueError(f"unknown host: {host!r}")
    if tier not in {"deep", "regular"}:
        raise ValueError(f"unknown review tier: {tier!r}")
    config = _config(project)
    default = _backend(default_reviewer) if default_reviewer is not None else "codex"
    project_backend = config.get("backend", default)
    backend = _backend(reviewer) if reviewer is not None else project_backend
    source = "inline" if reviewer is not None else "project" if config else "host-default"
    options = config if backend == project_backend else {}
    selected_model = model if model is not None else options.get("model")
    selected_effort = effort if effort is not None else options.get("effort")
    for field, value in (("model", selected_model), ("effort", selected_effort)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"reviewer {field} must be a nonempty string or null")

    transport = "mcp"
    fresh_tool = continuation_tool = None
    if backend in LEGACY_BACKENDS:
        transport = "legacy"
    elif backend == "codex":
        selected_model = selected_model or "gpt-6-astra"
        selected_effort = selected_effort or ("ultra" if tier == "deep" else "xhigh")
        if selected_effort not in {"xhigh", "max", "ultra"}:
            raise ValueError("Codex reviewer effort must be xhigh, max, or ultra")
        if host == "codex":
            transport = "native"
            fresh_tool, continuation_tool = "spawn_agent", "send_input"
        else:
            transport = "codex-mcp"
            fresh_tool, continuation_tool = "mcp__codex__codex", "mcp__codex__codex-reply"
    elif backend == "antigravity":
        selected_model = selected_model or "gemini-4-argon-high"
        selected_effort = selected_effort or "high"
        if selected_effort not in {"low", "medium", "high", "xhigh", "max"}:
            raise ValueError("Antigravity reviewer effort must be low, medium, high, xhigh, or max")
    elif backend == "grok":
        selected_model = selected_model or "grok-4.7"
        selected_effort = selected_effort or "xhigh"
        if selected_effort not in {"low", "medium", "high", "xhigh"}:
            raise ValueError("Grok reviewer effort must be low, medium, high, or xhigh")
    elif selected_effort is not None:
        raise ValueError("claude-code bridge cannot enforce effort; omit it and use existing CLI config")
    if backend in TOOLS:
        fresh_tool, continuation_tool = TOOLS[backend]
    return {
        "backend": backend,
        "host": host,
        "source": source,
        "model": selected_model,
        "effort": selected_effort,
        "transport": transport,
        "fresh_tool": fresh_tool,
        "continuation_tool": continuation_tool,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--host", choices=sorted(HOSTS), required=True)
    parser.add_argument("--tier", choices=("deep", "regular"), default="deep")
    parser.add_argument("--reviewer")
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--default-reviewer")
    args = parser.parse_args(argv)
    try:
        route = resolve_route(**vars(args))
    except (ValueError, UnicodeError) as exc:
        print(f"reviewer route error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(route, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
