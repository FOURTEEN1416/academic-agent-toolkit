"""Regression tests for the read-only Codex policy auditor."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tools.audit_codex_invocation import audit, policy_state


def test_missing_policy_keeps_default():
    with tempfile.TemporaryDirectory() as tmp:
        assert policy_state(Path(tmp) / "openai.yaml") == ("implicit-default", None)


def test_explicit_only_policy():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "openai.yaml"
        path.write_text("policy:\n  allow_implicit_invocation: false\n")
        assert policy_state(path) == ("explicit-only", None)


def test_duplicate_policy_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "openai.yaml"
        path.write_text("policy:\n  allow_implicit_invocation: false\n  allow_implicit_invocation: true\n")
        assert policy_state(path)[0] == "invalid"


def test_referenced_explicit_child_is_reported_without_editing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        parent, child = root / "parent", root / "child"
        parent.mkdir()
        (child / "agents").mkdir(parents=True)
        (parent / "SKILL.md").write_text("invoke /child, or ../child/SKILL.md")
        (child / "SKILL.md").write_text("child instructions")
        (child / "agents" / "openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
        report = audit(root)
        assert report["skill_count"] == 2
        assert report["referenced_explicit_only"] == ["child"]
        assert report["runtime_verified"] is False


def test_agent_ui_metadata_without_policy_is_valid_default():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "openai.yaml"
        path.write_text('interface:\n  display_name: "Research skill"\n')
        assert policy_state(path) == ("implicit-default", None)


@pytest.mark.parametrize("raw, expected", [
    ("policy:\n  allow_implicit_invocation: false", "explicit-only"),
    ("policy: {allow_implicit_invocation: false}\n", "explicit-only"),
    ("policy: # invocation controls\n  allow_implicit_invocation: false\n", "explicit-only"),
    ("policy: {allow_implicit_invocation: true}", "implicit-allowed"),
    ("policy: {allow_implicit_invocation: False}", "explicit-only"),
    ("policy: {allow_implicit_invocation: TRUE}", "implicit-allowed"),
    ("{}", "implicit-default"),
    ("policy: {}", "implicit-default"),
    ("policy: {other_option: value}", "implicit-default"),
])
def test_valid_yaml_policy_forms(tmp_path, raw, expected):
    path = tmp_path / "openai.yaml"
    path.write_text(raw)
    assert policy_state(path) == (expected, None)


@pytest.mark.parametrize("raw", [
    "policy: {allow_implicit_invocation: false}\npolicy: {}",
    'policy: {allow_implicit_invocation: false, allow_implicit_invocation: "false"}',
    "policy: [",
    "[]",
    "null",
    "policy: false",
    "policy: null",
    "policy: []",
    "policy: {allow_implicit_invocation: yes}",
    "policy: {allow_implicit_invocation: no}",
    "policy: {allow_implicit_invocation: !!bool yes}",
    'policy: {allow_implicit_invocation: "false"}',
    "policy: {allow_implicit_invocation: 0}",
    "policy: {allow_implicit_invocation: null}",
])
def test_invalid_yaml_policy_forms(tmp_path, raw):
    path = tmp_path / "openai.yaml"
    path.write_text(raw)
    state, error = policy_state(path)
    assert state == "invalid"
    assert error


def test_cli_strict_flag_catches_flow_policy(tmp_path):
    parent, child = tmp_path / "parent", tmp_path / "child"
    parent.mkdir()
    (child / "agents").mkdir(parents=True)
    (parent / "SKILL.md").write_text("Invoke $child.\n")
    (child / "SKILL.md").write_text("Child instructions.\n")
    policy = child / "agents/openai.yaml"
    raw = "policy: {allow_implicit_invocation: false}"
    policy.write_text(raw)
    script = Path(__file__).resolve().parents[1] / "tools/audit_codex_invocation.py"
    command = [sys.executable, str(script), "--root", str(tmp_path)]
    ordinary = subprocess.run(command, capture_output=True, text=True)
    strict = subprocess.run(command + ["--fail-on-referenced-explicit"], capture_output=True, text=True)
    assert ordinary.returncode == 0
    assert strict.returncode == 1
    report = json.loads(strict.stdout)
    assert report["referenced_explicit_only"] == ["child"]
    assert report["invalid_policies"] == []
    assert report["runtime_verified"] is False
    assert policy.read_text() == raw
