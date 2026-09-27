import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.execution_protocol import validate_execution_evidence, write_execution_evidence
from engine.agent_bridge import StepAction, StepResult


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


def test_bridge_native_receipt_normalizes_without_fabricating_success(tmp_path):
    action = make_action(tmp_path)
    command = {"command": ["python", "solve.py", "a b"], "exitCode": 0,
               "cwd": str(action.workspace), "stdout": "done", "stderr": ""}
    payload = evidence(action, commands=[command])
    result = StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": payload})
    actual = validate_execution_evidence(action.workspace, action, result)["commands"][0]
    assert actual["argv"] == command["command"]
    assert actual["returncode"] == 0 and actual["stdout"] == "done" and actual["cwd"] == "."
    command["exitCode"] = 2
    with pytest.raises(ValueError, match="returncode 0"):
        validate_execution_evidence(action.workspace, action, result)


def test_bridge_conflicting_return_codes_and_external_cwd_rejected(tmp_path):
    action = make_action(tmp_path)
    for command in [
        {"command": ["python", "solve.py"], "exitCode": 1, "returncode": 0},
        {"command": "python solve.py", "returncode": 0, "cwd": str(tmp_path)},
        {"command": "python solve.py", "returncode": True},
    ]:
        with pytest.raises(ValueError):
            validate_execution_evidence(action.workspace, action, StepResult(ok=True, artifacts=["out.txt"],
                metadata={"execution_evidence": evidence(action, commands=[command])}))


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


def test_execution_contract_separates_execution_semantics_from_quality_rules(tmp_path):
    """B窗收口1：合同只绑执行语义面（skill/params）。纯质量规则（metadata 质量字段、
    modex-core 规则文件）变化不改变合同——已执行命令不因规则更新而要求重跑。"""
    from engine.execution_protocol import execution_contract, legacy_execution_contract

    action = make_action(tmp_path)
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "comp_rules.json").write_text('{"page_cap": 30}', encoding="utf-8")
    metadata = {"required_checks": ["literature"], "output_specs": {"out.txt": {"min_bytes": 10}}}
    params = {"comp": "cumcm"}
    base = execution_contract(action, metadata, params, rules)

    # 纯质量规则变化：metadata 质量字段与规则文件内容都变 → 合同不变
    (rules / "comp_rules.json").write_text('{"page_cap": 80}', encoding="utf-8")
    metadata_changed = {"required_checks": ["literature", "review"], "quick_gates": True,
                        "output_specs": {"out.txt": {"min_bytes": 999}}}
    assert execution_contract(action, metadata_changed, params, rules) == base

    # 影响执行的变化：params 或技能正文变化 → 合同变化
    assert execution_contract(action, metadata_changed, {"comp": "huawei"}, rules) != base
    action.skill_path.write_text("altered contract", encoding="utf-8")
    assert execution_contract(action, metadata_changed, params, rules) != base

    # 历史口径函数保留用于对账，且与当前口径值不同
    assert legacy_execution_contract(action, metadata, params, rules) != base
