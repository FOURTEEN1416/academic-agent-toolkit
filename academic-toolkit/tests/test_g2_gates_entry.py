"""G2 闸门与入口层回归：explore 档、候选绑定、审批边界、abandon、质量门读取口径。"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.quality_gates import QualityGate  # noqa: E402
from engine.workflow_runner import WorkflowRunner  # noqa: E402
from engine.workflow_store import WorkflowStore  # noqa: E402
from engine.agent_bridge import StepResult  # noqa: E402
from execution.session import ExecutionSession  # noqa: E402


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _report(action, *, manifest=True):
    for output in action.output_files:
        path = action.workspace / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture result\n" * 200, encoding="utf-8")
    if manifest:
        from engine.step_manifest import write_manifest
        write_manifest(
            workspace=action.workspace, step_name=action.skill_name, config={},
            outputs=[action.workspace / name for name in action.output_files],
            backend="test-backend 1.0",
            commands=[{"command": "python generate.py", "exitCode": 0}],
            dependencies={},
        )
    return StepResult(
        ok=True, artifacts=list(action.output_files), step_id=action.step_id,
        attempt_id=action.attempt_id, expected_revision=action.expected_revision,
        metadata={"execution_evidence": {
            "schema_version": 1, "agent": "test-runner", "step_id": action.step_id,
            "skill_name": action.skill_name, "skill_sha256": action.skill_sha256,
            "commands": [{"command": "python generate.py", "returncode": 0, "cwd": "."}],
            "inputs": [], "outputs": list(action.output_files),
        }})


def _catalog(*steps):
    return {"demo": {"sub_steps": list(steps)}}


def _skills(tmp_path, *names):
    skills = tmp_path / "skills"
    for name in names:
        (skills / name).mkdir(parents=True, exist_ok=True)
        (skills / name / "SKILL.md").write_text("fixture skill", encoding="utf-8")
    return skills


def test_quality_gate_prefers_workflow_scoped_audit_and_rejects_explore(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper/main.pdf").write_bytes(b"paper")
    scoped = tmp_path / "reports" / "wf-new" / "AUDIT_REPORT.json"
    scoped.parent.mkdir(parents=True)
    ready = {"workflow_id": "wf-new",
             "artifacts": [{"path": "paper/main.pdf", "sha256": _sha(b"paper")}],
             "gate_outcomes": {"artifact_integrity": "pass"}, "waivers": [],
             "delivery_decision": "ready", "contract_tier": "delivery"}
    scoped.write_text(json.dumps(ready), encoding="utf-8")
    root = tmp_path / "AUDIT_REPORT.json"
    root.write_text(json.dumps({**ready, "workflow_id": "wf-old", "delivery_decision": "eligible"}),
                    encoding="utf-8")
    gate = QualityGate(tmp_path, audit_report_path=scoped)
    gate._active_final_step_id = "step-1"
    assert gate.check_final_audit_report()["ok"] is True

    root.write_text(json.dumps({**ready, "delivery_decision": "explore_only",
                                "contract_tier": "explore"}), encoding="utf-8")
    scoped.unlink()
    result = QualityGate(tmp_path, audit_report_path=scoped).check_final_audit_report()
    assert result["ok"] is False
    assert "explore" in result["reason"]


def test_quality_gate_candidate_failure_reason_is_explicit(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper/main.pdf").write_bytes(b"paper")
    report = {
        "workflow_id": "wf-1",
        "artifacts": [{"path": "paper/main.pdf", "sha256": _sha(b"paper")}],
        "gate_outcomes": {"candidate_reproduction": "fail", "candidate_review": "pass"},
        "waivers": [], "delivery_decision": "blocked", "contract_tier": "delivery",
        "candidate": {"gates": {"candidate_reproduction": {
            "ok": False, "reason": "missing fresh reproduction covering every frozen command target"}}},
    }
    path = tmp_path / "reports" / "wf-1" / "AUDIT_REPORT.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(report), encoding="utf-8")
    result = QualityGate(tmp_path, audit_report_path=path).check_final_audit_report()
    assert result["ok"] is False
    assert result["failed_gates"] == ["candidate_reproduction"]
    assert "fresh reproduction" in result["reason"]


def test_explore_start_filters_final_audit_and_writes_explore_report(tmp_path):
    skills = _skills(tmp_path, "solve", "comp-final-audit")
    catalog = _catalog(
        {"skill_name": "solve", "output_files": ["out.txt"], "primary_output": "out.txt",
         "has_checkpoint": True, "checkpoint_type": "approve", "required_checks": []},
        {"skill_name": "comp-final-audit", "output_files": ["AUDIT_REPORT.json"],
         "primary_output": "AUDIT_REPORT.json", "has_checkpoint": True,
         "checkpoint_type": "approve", "required_checks": ["final_audit"]},
    )
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills)
        workflow = runner.start("demo", tmp_path / "workspace", {}, mode="explore")
        contract = workflow.metadata["execution_contract"]
        assert contract["tier"] == "explore"
        assert contract["excluded_steps"] == ["comp-final-audit"]
        assert contract["excluded_checkpoints"]
        rows = store._connection.execute(
            "SELECT name, status FROM workflow_steps WHERE workflow_id=? ORDER BY position",
            (workflow.id,)).fetchall()
        assert [row["name"] for row in rows] == ["solve"]
        action = runner.next_action(workflow.id).action
        assert action.has_checkpoint is False
        completed = runner.complete_step(workflow.id, _report(action))
        assert completed.status == "completed", completed.message
        explore = json.loads((action.workspace / "EXPLORE_REPORT.json").read_text(encoding="utf-8"))
        assert explore["delivery_decision"] == "explore_only"
        assert not (action.workspace / "AUDIT_REPORT.json").exists()
        assert not (action.workspace / "DELIVERY_REPORT.json").exists()
        assert store.get_workflow(workflow.id).status == "completed"
        assert not any(step.status.value == "blocked"
                       for step in [store.get_step(row["id"]) for row in
                                    store._connection.execute(
                                        "SELECT id FROM workflow_steps WHERE workflow_id=?",
                                        (workflow.id,)).fetchall()])


def test_explore_real_template_filters_final_audit(tmp_path):
    catalog = json.loads((ROOT / "engine/modex-core/templates.json").read_text(encoding="utf-8"))
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, ROOT / "skills")
        workflow = runner.start("comp_cumcm", tmp_path / "workspace",
                                {"contest": {"submission_form": "paper"}}, mode="explore")
        contract = workflow.metadata["execution_contract"]
        assert contract["excluded_steps"] == ["comp-final-audit"]
        rows = store._connection.execute(
            "SELECT id, name, metadata FROM workflow_steps WHERE workflow_id=? ORDER BY position",
            (workflow.id,)).fetchall()
        names = [row["name"] for row in rows]
        assert "comp-final-audit" not in names
        assert all(json.loads(row["metadata"]).get("has_checkpoint") is False for row in rows)
        assert contract["excluded_checkpoints"]


def test_explore_operation_contract_differs_from_delivery(tmp_path):
    from execution.context import OperationContext

    skills = _skills(tmp_path, "solve")
    catalog = _catalog({"skill_name": "solve", "output_files": [], "has_checkpoint": False})
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills)
        explore = runner.start("demo", tmp_path / "explore-ws", {}, mode="explore")
        delivery = runner.start("demo", tmp_path / "delivery-ws", {})
        explore_action = runner.next_action(explore.id).action
        delivery_action = runner.next_action(delivery.id).action
        assert explore_action.contract_tier == "explore"
        assert delivery_action.contract_tier is None  # 旧交付直连接口不变
        explore_contract = OperationContext(store, explore_action, tmp_path).contract()
        delivery_contract = OperationContext(store, delivery_action, tmp_path).contract()
        assert explore_contract != delivery_contract
        assert OperationContext(store, explore_action, tmp_path).execution_relevant_contract() != \
            OperationContext(store, delivery_action, tmp_path).execution_relevant_contract()


def test_explore_output_spec_failure_is_advisory_but_delivery_blocks(tmp_path):
    catalog = _catalog({"skill_name": "solve", "output_files": ["out.txt"],
                        "primary_output": "out.txt", "has_checkpoint": False,
                        "required_checks": [], "output_specs": {
                            "out.txt": {"min_bytes": 10_000_000, "rationale": "advisory fixture"}}})
    skills = _skills(tmp_path, "solve")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, catalog, skills)
        explore = runner.start("demo", tmp_path / "explore-ws", {}, mode="explore")
        action = runner.next_action(explore.id).action
        report = runner.complete_step(explore.id, _report(action))
        assert report.status == "completed", report.message
        assert "output_spec:out.txt" in report.diagnostics["advisories"]
        assert report.diagnostics["contract_tier"] == "explore"

        delivery = runner.start("demo", tmp_path / "delivery-ws", {})
        action = runner.next_action(delivery.id).action
        blocked = runner.complete_step(delivery.id, _report(action))
        assert blocked.status == "failed"
        assert blocked.diagnostics["checks"]["output_spec:out.txt"]["ok"] is False


def _candidate(store, workspace: Path):
    root = workspace / "paper/main.pdf"
    root.parent.mkdir(parents=True)
    root.write_bytes(b"candidate pdf")
    skill = workspace.parent / "project/skills/comp-final-audit/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("audit", encoding="utf-8")
    source = store.create_workflow("demo", {"workspace": str(workspace)})
    source_step = store.add_steps(source.id, [{"name": "solve"}])[0]
    acceptance = {
        "params": {},
        "delivery_steps": [
            {"skill_name": "comp-review", "output_files": ["COMP_REVIEW_VERDICT.json"],
             "primary_output": "COMP_REVIEW_VERDICT.json", "has_checkpoint": False,
             "checkpoint_type": None, "required_checks": ["review"], "output_specs": {}},
            {"skill_name": "comp-final-audit", "output_files": ["AUDIT_REPORT.json"],
             "primary_output": "AUDIT_REPORT.json", "has_checkpoint": True,
             "checkpoint_type": "approve", "required_checks": ["final_audit"],
             "output_specs": {}},
        ],
        "required_reviews": [{"skill_name": "comp-review", "role": "review"}],
        "reproduction_targets": [{"path": "paper/main.pdf",
                                  "sha256": _sha(b"candidate pdf"), "recipe_id": "r1"}],
        "approval_policy": {"approvers": ["operator"], "require_human": True,
                            "config_sha256": "a" * 64},
    }
    return store.create_candidate(
        source_workflow_id=source.id, source_step_id=source_step.id,
        source_attempt_id="attempt-1",
        roots=[{"path": "paper/main.pdf", "sha256": _sha(b"candidate pdf")}],
        inputs={"raw.csv": {"sha256": "b" * 64, "kind": "external",
                            "producer_operation_id": None, "depth": 1}},
        frozen_versions={"paper/main.pdf": _sha(b"candidate pdf"), "raw.csv": "b" * 64},
        lineage={"producer_operations": {}, "external_inputs": {"raw.csv": "b" * 64},
                 "unknown_inputs": []},
        recipe={"r1": {"argv": ["python", "solve.py"], "cwd": ".", "inputs": ["raw.csv"],
                       "outputs": ["paper/main.pdf"], "mutates": []}},
        acceptance=acceptance, acceptance_sha256=_canonical_sha(acceptance),
        created_by="tester", missing=["reproduction", "review", "approval"])


def test_candidate_start_builds_carry_reproduction_reviews_and_final(tmp_path):
    workspace = tmp_path / "workspace"
    skills = _skills(tmp_path, "comp-review", "comp-final-audit", "candidate-reproduction")
    catalog = _catalog({"skill_name": "solve"})
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        candidate = _candidate(store, workspace)
        runner = WorkflowRunner(store, catalog, skills)
        workflow = runner.start("demo", workspace, {"agent": "tester"},
                                candidate_id=candidate.id)
        rows = store._connection.execute(
            "SELECT id, name, status FROM workflow_steps WHERE workflow_id=? ORDER BY position",
            (workflow.id,)).fetchall()
        assert [row["name"] for row in rows] == [
            "promotion-carry", "candidate-reproduction", "comp-review", "comp-final-audit"]
        assert rows[0]["status"] == "completed"
        assert store.get_candidate(candidate.id).status == "in_delivery"
        assert workflow.metadata["delivery_candidate"]["candidate_id"] == candidate.id
        assert workflow.metadata["approval_policy"]["approvers"] == ["operator"]
        plan = json.loads((workspace / "REPRODUCTION_PLAN.json").read_text(encoding="utf-8"))
        assert plan["candidate_id"] == candidate.id
        assert plan["targets"][0]["recipe_id"] == "r1"
        assert all("paper/main.pdf" not in (row.metadata.get("output_files") or [])
                   for row in [store.get_step(item["id"]) for item in rows])
        # carry-over 事件必须是本工作流已接受版本，而不是重跑生产步骤。
        events = store.workflow_timeline(workflow.id)["events"]
        carry = [event for event in events if event["payload"].get("carrier") is True]
        assert carry and carry[0]["payload"]["manifest"]["artifacts"][0]["path"] == "paper/main.pdf"


def test_candidate_ordinary_step_checkpoint_cannot_write_candidate_approved(tmp_path):
    workspace = tmp_path / "workspace"
    skills = _skills(tmp_path, "comp-review")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        candidate = _candidate(store, workspace)
        workflow = store.create_workflow("delivery", {
            "workspace": str(workspace),
            "execution_contract": {"tier": "delivery", "version": 1},
            "delivery_candidate": {"candidate_id": candidate.id,
                                   "source_workflow_id": candidate.source_workflow_id},
            "approval_policy": {"approvers": ["operator"], "require_human": True},
        }, candidate_id=candidate.id)
        (workspace / "COMP_REVIEW_VERDICT.json").write_text('{"verdict": "pass"}', encoding="utf-8")
        verdict_sha = _sha((workspace / "COMP_REVIEW_VERDICT.json").read_bytes())
        step = store.add_steps(workflow.id, [{
            "name": "comp-review", "has_checkpoint": True,
            "metadata": {"has_checkpoint": True, "checkpoint_type": "approve",
                         "output_files": ["COMP_REVIEW_VERDICT.json"]}}])[0]
        store.transition_step(step.id, "running")
        _, checkpoint = store.transition_step_with_checkpoint(
            workflow.id, step.id, "blocked",
            {"status": "waiting_checkpoint", "validation": {"ok": True},
             "manifest": {"artifacts": [{"path": "COMP_REVIEW_VERDICT.json",
                                         "sha256": verdict_sha}]}},
            event={"type": "step_completed"})
        runner = WorkflowRunner(store, _catalog({"skill_name": "comp-review"}), skills)
        result = runner._approve_checkpoint(checkpoint.id, {"approved": True,
                                                            "approved_by": "operator"})
        assert result.status == "blocked"
        assert "comp-final-audit" in result.message
        assert store._connection.execute(
            "SELECT COUNT(*) FROM candidate_events WHERE candidate_id=?",
            (candidate.id,)).fetchone()[0] == 0


def test_candidate_final_approval_degrades_without_path_attributed_l1(tmp_path):
    workspace = tmp_path / "workspace"
    skills = _skills(tmp_path, "comp-final-audit")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        candidate = _candidate(store, workspace)
        workflow = store.create_workflow("delivery", {
            "workspace": str(workspace),
            "execution_contract": {"tier": "delivery", "version": 1},
            "delivery_candidate": {"candidate_id": candidate.id,
                                   "source_workflow_id": candidate.source_workflow_id},
            "approval_policy": {"approvers": ["operator"], "require_human": True},
        }, candidate_id=candidate.id)
        (workspace / "AUDIT_REPORT.json").write_text('{"delivery_decision": "eligible"}',
                                                     encoding="utf-8")
        audit_sha = _sha((workspace / "AUDIT_REPORT.json").read_bytes())
        step = store.add_steps(workflow.id, [{
            "name": "comp-final-audit", "has_checkpoint": True,
            "metadata": {"has_checkpoint": True, "checkpoint_type": "approve",
                         "output_files": ["AUDIT_REPORT.json"]}}])[0]
        store.transition_step(step.id, "running")
        _, checkpoint = store.transition_step_with_checkpoint(
            workflow.id, step.id, "blocked",
            {"status": "waiting_checkpoint", "validation": {"ok": True},
             "manifest": {"artifacts": [{"path": "AUDIT_REPORT.json", "sha256": audit_sha}]}},
            event={"type": "step_completed"})
        # checkpoint 绑定的旧 blocked checkpoint 即批准身份。
        runner = WorkflowRunner(store, _catalog({"skill_name": "comp-final-audit"}),
                                skills, audit_root=tmp_path)
        result = runner._approve_checkpoint(checkpoint.id, {"approved": True,
                                                            "approved_by": "operator"})
        assert result.status == "blocked"
        assert "degraded" in result.message or "L1" in result.message
        events = store.candidate_events(candidate.id)
        assert any(event["event_type"] == "candidate_approval_degraded" for event in events)
        assert not any(event["event_type"] == "candidate_approved" for event in events)
        assert store.get_step(step.id).status.value == "blocked"


def test_candidate_backfill_and_legacy_evidence_are_rejected(tmp_path):
    workspace = tmp_path / "workspace"
    skills = _skills(tmp_path, "comp-review", "comp-final-audit", "candidate-reproduction")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        candidate = _candidate(store, workspace)
        runner = WorkflowRunner(store, _catalog({"skill_name": "solve"}), skills)
        workflow = runner.start("demo", workspace, {}, candidate_id=candidate.id)
        backfill = runner.backfill_step(workflow.id, "candidate-reproduction", ["REPRODUCTION_REPORT.json"])
        assert backfill.status == "failed"
        assert "候选交付禁止" in backfill.message

        from engine import workflow_cli
        step = store._connection.execute(
            "SELECT id FROM workflow_steps WHERE workflow_id=? AND name='comp-review'",
            (workflow.id,)).fetchone()
        with pytest.raises(workflow_cli.WorkflowCliError, match="候选交付工作流"):
            workflow_cli._reject_handbuilt_final_evidence(store, step["id"], {})


def test_abandon_invalidates_old_ticket(tmp_path):
    skills = _skills(tmp_path, "solve")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, _catalog({"skill_name": "solve"}), skills)
        workflow = runner.start("demo", tmp_path / "workspace", {}, mode="explore")
        action = runner.next_action(workflow.id).action
        session = ExecutionSession(runner, workflow.id, action)
        before = store._connection.execute(
            "SELECT COUNT(*) FROM execution_operations WHERE workflow_id=?",
            (workflow.id,)).fetchone()[0]
        result = session.abandon("changed direction", "operator")
        assert result["status"] == "abandoned"
        with pytest.raises(ValueError, match="会话已失效"):
            session.files.write("out.txt", "late write")
        with pytest.raises(ValueError, match="会话已失效"):
            session.finish()
        assert store._connection.execute(
            "SELECT COUNT(*) FROM execution_operations WHERE workflow_id=?",
            (workflow.id,)).fetchone()[0] == before
        assert workflow.id not in {item.workflow_id for item in store.resume_candidates()}
        assert runner.next_action(workflow.id).status == "abandoned"


def test_approve_public_api_is_closed(tmp_path):
    skills = _skills(tmp_path, "solve")
    with WorkflowStore(tmp_path / "workflow.sqlite") as store:
        runner = WorkflowRunner(store, _catalog({"skill_name": "solve"}), skills)
        assert not hasattr(runner, "approve_checkpoint")
        assert hasattr(runner, "_approve_checkpoint")
