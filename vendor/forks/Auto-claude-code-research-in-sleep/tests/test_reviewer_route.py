"""Behavioral tests for deterministic reviewer selection; no models are invoked."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.reviewer_route import resolve_route


def configure(project, **config):
    directory = project / ".aris"
    directory.mkdir(exist_ok=True)
    (directory / "reviewer.json").write_text(json.dumps(config))


@pytest.mark.parametrize("host,transport", [("codex", "native"), ("claude-code", "codex-mcp"), ("copilot", "codex-mcp")])
@pytest.mark.parametrize("tier,effort", [("deep", "ultra"), ("regular", "xhigh")])
def test_host_defaults(tmp_path, host, transport, tier, effort):
    route = resolve_route(tmp_path, host, tier)
    assert route["backend"] == "codex"
    assert route["transport"] == transport
    assert route["source"] == "host-default"
    assert route["model"] == "gpt-6-astra"
    assert route["effort"] == effort
    assert route["fresh_tool"] == ("spawn_agent" if host == "codex" else "mcp__codex__codex")
    assert route["continuation_tool"] == ("send_input" if host == "codex" else "mcp__codex__codex-reply")


def test_priority_and_same_provider_options(tmp_path):
    configure(tmp_path, backend="gemini", model="gemini-custom", effort="max")
    route = resolve_route(tmp_path, "codex", default_reviewer="grok")
    assert (route["backend"], route["model"], route["effort"], route["source"]) == ("antigravity", "gemini-custom", "max", "project")
    route = resolve_route(tmp_path, "codex", reviewer="antigravity", model="gemini-override")
    assert (route["model"], route["effort"], route["source"]) == ("gemini-override", "max", "inline")
    route = resolve_route(tmp_path, "codex", reviewer="gemini", effort="high")
    assert (route["model"], route["effort"]) == ("gemini-custom", "high")


def test_switching_provider_does_not_inherit_project_options(tmp_path):
    configure(tmp_path, backend="antigravity", model="gemini-custom", effort="max")
    route = resolve_route(tmp_path, "codex", reviewer="grok")
    assert (route["model"], route["effort"]) == ("grok-4.7", "xhigh")
    route = resolve_route(tmp_path, "codex", reviewer="claude-code")
    assert (route["model"], route["effort"]) == (None, None)
    route = resolve_route(tmp_path, "codex", reviewer="grok", model="grok-custom", effort="high")
    assert (route["model"], route["effort"]) == ("grok-custom", "high")


def test_partial_project_config_uses_host_default(tmp_path):
    configure(tmp_path, effort="high")
    route = resolve_route(tmp_path, "copilot", default_reviewer="grok")
    assert (route["backend"], route["effort"], route["source"]) == ("grok", "high", "project")


@pytest.mark.parametrize("alias,backend,tool", [("gemini", "antigravity", "mcp__antigravity__antigravity"), ("claude", "claude-code", "mcp__claude-review__review"), ("claude-review", "claude-code", "mcp__claude-review__review")])
def test_aliases(tmp_path, alias, backend, tool):
    route = resolve_route(tmp_path, "codex", reviewer=alias)
    assert route["backend"] == backend
    assert route["fresh_tool"] == tool


@pytest.mark.parametrize("backend", ["oracle-pro", "agy", "manual", "copilot", "copilot-native"])
def test_legacy_routes_retain_identity_and_options(tmp_path, backend):
    route = resolve_route(tmp_path, "copilot", reviewer=backend, model="legacy-model", effort="low")
    assert route["backend"] == backend
    assert route["transport"] == "legacy"
    assert route["model"] == "legacy-model"
    assert route["effort"] == "low"
    assert route["fresh_tool"] is None
    assert route["continuation_tool"] is None


@pytest.mark.parametrize("effort", ["low", "medium", "high", "unknown"])
def test_codex_rejects_lower_or_unknown_effort(tmp_path, effort):
    with pytest.raises(ValueError, match="Codex reviewer effort"):
        resolve_route(tmp_path, "codex", effort=effort)


@pytest.mark.parametrize("backend,effort", [("codex", "xhigh"), ("codex", "max"), ("codex", "ultra"), ("antigravity", "max"), ("grok", "xhigh")])
def test_supported_efforts(tmp_path, backend, effort):
    assert resolve_route(tmp_path, "codex", reviewer=backend, effort=effort)["effort"] == effort


def test_claude_model_uses_config_without_fabricated_effort(tmp_path):
    route = resolve_route(tmp_path, "claude-code", reviewer="claude-code", model="configured-model")
    assert route["model"] == "configured-model"
    assert route["effort"] is None
    with pytest.raises(ValueError, match="cannot enforce effort"):
        resolve_route(tmp_path, "codex", reviewer="claude-code", effort="high")


@pytest.mark.parametrize("text", ['{', '[]', '{"backend": "missing"}', '{"backend": null}', '{"model": 4}', '{"effort": ""}', '{"profiles": {}}'])
def test_invalid_config_is_not_silently_ignored(tmp_path, text):
    directory = tmp_path / ".aris"
    directory.mkdir()
    (directory / "reviewer.json").write_text(text)
    with pytest.raises(ValueError):
        resolve_route(tmp_path, "codex", reviewer="grok")


def test_cli_json_and_clear_config_error(tmp_path):
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "tools/reviewer_route.py"), "--project", str(tmp_path), "--host", "codex", "--reviewer", "grok"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["backend"] == "grok"
    configure(tmp_path, backend="unknown")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "reviewer route error:" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("backend,model,effort", [("antigravity", "gemini-4-argon-high", "high"), ("grok", "grok-4.7", "xhigh"), ("claude-code", None, None)])
def test_bridge_defaults(tmp_path, backend, model, effort):
    route = resolve_route(tmp_path, "codex", reviewer=backend)
    assert (route["model"], route["effort"], route["transport"]) == (model, effort, "mcp")
    assert route["continuation_tool"] is not None


@pytest.mark.parametrize("backend,effort", [("antigravity", "ultra"), ("grok", "max")])
def test_bridge_rejects_unsupported_effort(tmp_path, backend, effort):
    with pytest.raises(ValueError, match="reviewer effort must"):
        resolve_route(tmp_path, "codex", reviewer=backend, effort=effort)
