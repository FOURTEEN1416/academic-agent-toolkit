"""The catalog probe must distinguish filtering from a failed control."""
import json
from types import SimpleNamespace

import pytest

from tools import probe_codex_invocation as probe


def prompt_messages(names):
    catalog = "<skills_instructions>\n" + "\n".join(f"- {name}: test" for name in names)
    return json.dumps([
        {"role": "developer", "content": [{"type": "input_text", "text": catalog}]},
        {"role": "user", "content": [{"text": "- policy-probe: literal user text"}]},
    ])


@pytest.mark.parametrize("names, expected", [
    (["plain-probe"], 0),
    (["plain-probe", "policy-probe"], 3),
    ([], 2),
])
def test_probe_outcome_and_isolated_neutral_prompt(monkeypatch, names, expected):
    calls = []

    def fake_codex(project, home, prompt):
        calls.append(prompt)
        assert "probe" not in prompt and "$" not in prompt
        assert home.is_dir() and home.parent == project.parent
        skills = project / ".agents" / "skills"
        assert (skills / "plain-probe" / "SKILL.md").is_file()
        assert "allow_implicit_invocation: false" in (
            skills / "policy-probe" / "agents" / "openai.yaml"
        ).read_text()
        return 0, prompt_messages(names), ""

    monkeypatch.setattr(probe, "run_codex", fake_codex)
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="test-version"))
    assert probe.main() == expected
    assert len(calls) == 1


@pytest.mark.parametrize("payload", ["not json", "{}", "[]", json.dumps([
    {"role": "user", "content": [{"text": "<skills_instructions>\n- plain-probe: test"}]},
])])
def test_missing_or_invalid_catalog_is_not_success(payload):
    with pytest.raises(ValueError):
        probe.catalog_visibility(payload)
