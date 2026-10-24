import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.execution_protocol import (
    collect_execution_evidence,
    execution_contract,
    legacy_execution_contract,
    normalize_legacy_evidence,
    validate_execution_evidence,
    write_execution_evidence,
)
from engine.agent_bridge import StepAction, StepResult


class _ActionView:
    """StepAction 的只读视图：为尚未落地的 StepAction 新字段提供测试替身。"""

    def __init__(self, action, **overrides):
        self._action = action
        for name, value in overrides.items():
            setattr(self, name, value)

    def __getattr__(self, name):
        return getattr(self._action, name)


def make_action(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("demo skill", encoding="utf-8")
    return StepAction("wf", "step", 0, "demo", "Demo", workspace, skill, ["out.txt"], "out.txt", False, None)


def make_execution_session(tmp_path):
    """真实 ExecutionSession 夹具（供采集/合同对账测试使用）。"""
    from engine.workflow_runner import WorkflowRunner
    from engine.workflow_store import WorkflowStore
    from execution.session import ExecutionSession

    skills = tmp_path / "suite" / "skills"
    folder = skills / "demo"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("Real task instructions: calculate the result.", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    catalog = {"demo": {"sub_steps": [{
        "skill_name": "demo", "output_files": ["result.txt"], "primary_output": "result.txt",
        "has_checkpoint": False, "metadata": {"skill_binding": {"main_required": True}},
    }]}}
    runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
    workflow = runner.start("demo", tmp_path / "work", {})
    session = ExecutionSession(runner, workflow.id)
    session.context()
    return store, runner, workflow.id, session


def set_workflow_metadata(store, workflow_id, **updates):
    metadata = store.get_workflow(workflow_id).metadata
    metadata.update(updates)
    store._connection.execute(
        "UPDATE workflows SET metadata=? WHERE id=?", (json.dumps(metadata), workflow_id))
    store._connection.commit()


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
    for field in ("schema_version", "commands", "inputs", "outputs"):
        payload = evidence(action)
        del payload[field]
        with pytest.raises(ValueError, match=f"missing required fields: {field}"):
            validate_execution_evidence(
                action.workspace, action,
                StepResult(ok=True, metadata={"execution_evidence": payload}))


def test_identity_fields_backfilled_from_step_action_never_invent_execution(tmp_path):
    """W5：引擎已知身份可回填；commands/inputs/outputs 永不代填。"""
    action = replace(make_action(tmp_path), attempt_id="att-1", expected_revision=3,
                     params={"agent": "runner-bot"})
    assert normalize_legacy_evidence(action, {"schema_version": 1}) == {
        "schema_version": 1, "step_id": "step", "attempt_id": "att-1",
        "expected_revision": 3, "skill_name": "demo",
        "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
        "agent": "runner-bot",
    }
    payload = {"schema_version": 1,
               "commands": [{"command": "python solve.py", "returncode": 0, "cwd": "."}],
               "inputs": [], "outputs": ["out.txt"]}
    validated = validate_execution_evidence(
        action.workspace, action,
        StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": payload}))
    assert validated["step_id"] == "step" and validated["attempt_id"] == "att-1"
    assert validated["expected_revision"] == 3 and validated["agent"] == "runner-bot"
    assert validated["skill_sha256"] == normalize_legacy_evidence(action, {})["skill_sha256"]


def test_identity_backfill_keeps_conflicting_values_for_explicit_rejection(tmp_path):
    action = make_action(tmp_path)
    payload = evidence(action, step_id="another-step")
    with pytest.raises(ValueError, match="does not match the active step"):
        validate_execution_evidence(action.workspace, action, StepResult(ok=True, metadata={"execution_evidence": payload}))


def test_identity_backfill_does_not_rescue_missing_commands(tmp_path):
    action = make_action(tmp_path)
    payload = {"schema_version": 1, "inputs": [], "outputs": ["out.txt"]}
    with pytest.raises(ValueError, match="missing required fields: commands"):
        validate_execution_evidence(
            action.workspace, action,
            StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": payload}))


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
    action = make_action(tmp_path)
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "comp_rules.json").write_text('{"page_cap": 30}', encoding="utf-8")
    metadata = {"required_checks": ["literature"], "output_specs": {"out.txt": {"min_bytes": 10}}}
    params = {"comp": "cumcm"}
    skill_sha = hashlib.sha256(action.skill_path.read_bytes()).hexdigest()

    def digest(body):
        return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()

    base = execution_contract(action, metadata, params, rules)
    assert base == digest({"contract_scope": 2, "params": params, "skill": skill_sha,
                           "session_protocol": 1})
    explore = execution_contract(action, metadata, params, rules, tier="explore")
    assert explore == digest({"contract_scope": 3, "params": params, "skill": skill_sha,
                              "session_protocol": 1, "contract_tier": "explore"})
    assert explore != base

    # 纯质量规则变化：metadata 质量字段与规则文件内容都变 → 两档合同都不变
    (rules / "comp_rules.json").write_text('{"page_cap": 80}', encoding="utf-8")
    metadata_changed = {"required_checks": ["literature", "review"], "quick_gates": True,
                        "output_specs": {"out.txt": {"min_bytes": 999}}}
    assert execution_contract(action, metadata_changed, params, rules) == base
    assert execution_contract(action, metadata_changed, params, rules, tier="explore") == explore

    # 影响执行的变化：params 或技能正文变化 → 合同变化
    assert execution_contract(action, metadata_changed, {"comp": "huawei"}, rules) != base
    action.skill_path.write_text("altered contract", encoding="utf-8")
    assert execution_contract(action, metadata_changed, params, rules) != base
    assert execution_contract(action, metadata_changed, params, rules, tier="explore") != explore

    # 历史口径函数保留用于对账，且与两档当前口径值都不同
    assert legacy_execution_contract(action, metadata, params, rules) not in {base, explore}

    with pytest.raises(ValueError, match="tier"):
        execution_contract(action, metadata, params, rules, tier="research")


def test_explore_contract_scope_three(tmp_path):
    """G2：explore 用 scope 3 + contract_tier，delivery 哈希必须保持原基线。"""
    action = make_action(tmp_path)
    rules = tmp_path / "rules"
    rules.mkdir()
    params = {"comp": "cumcm"}
    skill_sha = hashlib.sha256(action.skill_path.read_bytes()).hexdigest()

    def digest(body):
        return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()

    delivery = execution_contract(action, {}, params, rules)
    explore = execution_contract(action, {}, params, rules, tier="explore")
    assert delivery == digest({"contract_scope": 2, "params": params, "skill": skill_sha,
                               "session_protocol": 1})
    assert explore == digest({"contract_scope": 3, "params": params, "skill": skill_sha,
                              "session_protocol": 1, "contract_tier": "explore"})
    assert delivery != explore
    assert legacy_execution_contract(action, {}, params, rules) != delivery
    assert legacy_execution_contract(action, {}, params, rules) != explore


def test_validate_execution_evidence_contract_tier_must_match_action(tmp_path):
    action = make_action(tmp_path)
    delivery_action = _ActionView(action, contract_tier="delivery")
    explore_action = _ActionView(action, contract_tier="explore")

    def result(payload):
        return StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": payload})

    assert validate_execution_evidence(
        action.workspace, delivery_action,
        result(evidence(action, contract_tier="delivery")))["contract_tier"] == "delivery"
    assert validate_execution_evidence(
        action.workspace, explore_action,
        result(evidence(action, contract_tier="explore")))["contract_tier"] == "explore"
    # 旧 evidence 无 tier 时按当前步骤档位补齐
    assert validate_execution_evidence(
        action.workspace, explore_action, result(evidence(action)))["contract_tier"] == "explore"

    with pytest.raises(ValueError, match="does not match the active step"):
        validate_execution_evidence(
            action.workspace, delivery_action,
            result(evidence(action, contract_tier="explore")))
    with pytest.raises(ValueError, match="unsupported execution contract tier"):
        validate_execution_evidence(
            action.workspace, action, result(evidence(action, contract_tier="deep")))


def test_candidate_delivery_rejects_legacy_evidence(tmp_path):
    action = make_action(tmp_path)

    def result(payload):
        return StepResult(ok=True, artifacts=["out.txt"], metadata={"execution_evidence": payload})

    for candidate_action in (action, _ActionView(action, requires_collection=True)):
        with pytest.raises(ValueError, match="requires execution-session-v1 collection"):
            validate_execution_evidence(
                action.workspace, candidate_action, result(evidence(action)), require_collection=True)

    with pytest.raises(ValueError, match="requires execution-session-v1 collection"):
        validate_execution_evidence(
            action.workspace, _ActionView(action, requires_collection=True),
            result(evidence(action)))

    legacy_collection = evidence(action, collection={"source": "handbuilt", "operation_ids": []})
    with pytest.raises(ValueError, match="must use execution-session-v1"):
        validate_execution_evidence(
            action.workspace, action, result(legacy_collection), require_collection=True)
    with pytest.raises(ValueError, match="workspace_observations requires"):
        validate_execution_evidence(
            action.workspace, action,
            result(evidence(action, workspace_observations=[
                {"operation_id": "op", "path": "out.txt", "sha256": "0" * 64, "edge": False}])))


def test_collect_execution_evidence_exposes_tier_and_trace_only_observations(tmp_path):
    store, _runner, workflow_id, session = make_execution_session(tmp_path)
    # 外部预置文件（无生产者）只被阅读，不进入任何写操作的依赖
    (session.workspace / "notes.txt").write_text("unrelated", encoding="utf-8")
    session.files.read_file("notes.txt")
    session.files.write("input.txt", "7")
    session.commands.execute({
        "id": "solve", "argv": [sys.executable, "-c",
            "from pathlib import Path;Path('result.txt').write_text('ok')"],
        "inputs": ["input.txt"], "outputs": ["result.txt"],
        "pure": True, "complete_inputs": True,
    })

    collected = collect_execution_evidence(store, store.get_workflow(workflow_id), session.action)
    assert collected["contract_tier"] == "delivery"
    assert collected["delivery_candidate_id"] == ""
    observations = {entry["path"]: entry for entry in collected["workspace_observations"]}
    assert observations["notes.txt"]["edge"] is False
    assert observations["notes.txt"]["sha256"] == hashlib.sha256(b"unrelated").hexdigest()
    assert observations["notes.txt"]["operation_id"]
    # 观察只作审计可见性，不进入 evidence["inputs"]（inputs 只来自 inputs_snapshot）
    assert collected["inputs"] == ["input.txt"]
    assert "notes.txt" not in collected["inputs"]

    # 观察只证明"当时读过"：读取后磁盘字节变化不影响 workspace_observations 对账
    (session.workspace / "notes.txt").write_text("changed after read", encoding="utf-8")
    validated = validate_execution_evidence(
        session.workspace, session.action,
        StepResult(ok=True, artifacts=["result.txt"], metadata={"execution_evidence": collected}),
        store=store)
    assert validated["contract_tier"] == "delivery"
    assert any(entry["path"] == "notes.txt" for entry in validated["workspace_observations"])
    store.close()


def test_workspace_observations_use_folded_current_operations(tmp_path):
    store, _runner, workflow_id, session = make_execution_session(tmp_path)
    session.files.write("notes.txt", "v1")
    session.files.read_file("notes.txt")
    (session.workspace / "notes.txt").write_text("v2", encoding="utf-8")
    session.files.read_file("notes.txt")
    session.files.write("result.txt", "done")

    collected = collect_execution_evidence(store, store.get_workflow(workflow_id), session.action)
    notes = [entry for entry in collected["workspace_observations"] if entry["path"] == "notes.txt"]
    assert len(notes) == 1
    assert notes[0]["sha256"] == hashlib.sha256(b"v2").hexdigest()

    notes[0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="workspace observations mismatch"):
        validate_execution_evidence(
            session.workspace, session.action,
            StepResult(ok=True, artifacts=["result.txt"], metadata={"execution_evidence": collected}),
            store=store)
    store.close()


def test_explore_workflow_accepts_delivery_scope2_operation_contract(tmp_path):
    store, _runner, workflow_id, session = make_execution_session(tmp_path)
    session.files.write("input.txt", "7")
    session.commands.execute({
        "id": "solve", "argv": [sys.executable, "-c",
            "from pathlib import Path;Path('result.txt').write_text('ok')"],
        "inputs": ["input.txt"], "outputs": ["result.txt"],
        "pure": True, "complete_inputs": True,
    })
    # 模拟已按 G2 写入 explore 元数据的工作流；操作由旧接线记录为 scope 2。
    set_workflow_metadata(store, workflow_id,
                          execution_contract={"tier": "explore", "version": 1},
                          delivery_candidate={"candidate_id": "cand-1", "source_workflow_id": "src"})
    collected = collect_execution_evidence(store, store.get_workflow(workflow_id), session.action)
    assert collected["contract_tier"] == "explore"
    assert collected["delivery_candidate_id"] == "cand-1"
    validated = validate_execution_evidence(
        session.workspace, session.action,
        StepResult(ok=True, artifacts=["result.txt"], metadata={"execution_evidence": collected}),
        store=store)
    assert validated["contract_tier"] == "explore"

    command_row = next(row for row in store.execution_operations(
        session.action.step_id, session.action.attempt_id) if row["kind"] == "command")
    payload = dict(command_row["payload"])
    payload["contract"] = "0" * 64
    store._connection.execute(
        "UPDATE execution_operations SET payload=? WHERE id=?", (json.dumps(payload), command_row["id"]))
    store._connection.commit()
    tampered = collect_execution_evidence(store, store.get_workflow(workflow_id), session.action)
    with pytest.raises(ValueError, match="contract changed"):
        validate_execution_evidence(
            session.workspace, session.action,
            StepResult(ok=True, artifacts=["result.txt"], metadata={"execution_evidence": tampered}),
            store=store)
    store.close()
