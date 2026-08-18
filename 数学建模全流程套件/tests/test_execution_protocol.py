import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.execution_protocol import validate_execution_evidence, write_execution_evidence
from engine.opencode_bridge import StepAction, StepResult


def make_action(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("demo skill", encoding="utf-8")
    return StepAction("wf", "step", 0, "demo", "Demo", workspace, skill, ["out.txt"], "out.txt", False, None)


def evidence(action, **overrides):
    payload = {
        "schema_version": 1,
        "agent": "OpenCode Desktop",
        "step_id": action.step_id,
        "skill_name": action.skill_name,
        "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
        "commands": [{"command": "python solve.py", "returncode": 0, "cwd": "."}],
        "inputs": ["input.csv"],
        "outputs": ["out.txt"],
    }
    payload.update(overrides)
    return payload


def test_validate_execution_evidence_accepts_versioned_workspace_relative_records(tmp_path):
    action = make_action(tmp_path)
    result = StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": evidence(action)})

    validated = validate_execution_evidence(action.workspace, action, result)

    assert validated["schema_version"] == 1
    assert validated["commands"][0]["cwd"] == "."
    assert validated["outputs"] == ["out.txt"]


@pytest.mark.parametrize("override, match", [
    ({"commands": []}, "commands"),
    ({"outputs": ["../escape.txt"]}, "escapes workspace"),
    ({"skill_sha256": "not-a-hash"}, "skill_sha256"),
])
def test_validate_execution_evidence_rejects_malformed_evidence(tmp_path, override, match):
    action = make_action(tmp_path)
    result = StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": evidence(action, **override)})

    with pytest.raises(ValueError, match=match):
        validate_execution_evidence(action.workspace, action, result)


def test_validate_execution_evidence_requires_all_fields(tmp_path):
    action = make_action(tmp_path)
    payload = evidence(action)
    del payload["agent"]

    with pytest.raises(ValueError, match="missing required fields: agent"):
        validate_execution_evidence(action.workspace, action, StepResult(ok=True, metadata={"execution_evidence": payload}))


def test_validate_execution_evidence_rejects_failed_command_in_successful_step(tmp_path):
    action = make_action(tmp_path)
    payload = evidence(action, commands=[{"command": "python solve.py", "returncode": 1, "cwd": "."}])

    with pytest.raises(ValueError, match="returncode 0"):
        validate_execution_evidence(
            action.workspace,
            action,
            StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": payload}),
        )


def test_validate_execution_evidence_requires_outputs_to_match_claimed_artifacts(tmp_path):
    action = make_action(tmp_path)
    payload = evidence(action, outputs=[])

    with pytest.raises(ValueError, match="outputs must match claimed artifacts"):
        validate_execution_evidence(
            action.workspace,
            action,
            StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": payload}),
        )


def test_write_execution_evidence_writes_workspace_contained_document(tmp_path):
    action = make_action(tmp_path)
    validated = validate_execution_evidence(action.workspace, action, StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": evidence(action)}))
    path = write_execution_evidence(action.workspace, action, validated, {"ok": True, "artifacts": []})

    assert path.startswith(".engine/evidence/")
    assert (action.workspace / path).is_file()


@pytest.mark.parametrize("fake", [
    "python workbook inspection for four supplied STR attachments",
    "python modeling capability coverage check",
    "Word COM main.docx -> main.pdf (xelatex unavailable, docx route)",
    "python -c \"# logic review: 5-category gap analysis per comp-review SKILL.md\"",
    "run the full pipeline and verify the results.",
])
def test_validate_execution_evidence_rejects_descriptive_fake_commands(tmp_path, fake):
    action = make_action(tmp_path)
    payload = evidence(action, commands=[{"command": fake, "returncode": 0, "cwd": "."}])

    with pytest.raises(ValueError, match="descriptive text"):
        validate_execution_evidence(
            action.workspace,
            action,
            StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": payload}),
        )


@pytest.mark.parametrize("real", [
    "python tools/scholar_fetch.py search test --max 3",
    "python code/main.py",
    "python -m pytest tests/ -q",
    "python paper/build_paper.py",
    "git status",
])
def test_validate_execution_evidence_accepts_real_executable_commands(tmp_path, real):
    action = make_action(tmp_path)
    payload = evidence(action, commands=[{"command": real, "returncode": 0, "cwd": "."}])

    validated = validate_execution_evidence(
        action.workspace,
        action,
        StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": payload}),
    )

    assert validated["commands"][0]["command"] == real
