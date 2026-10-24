"""G2 审计层回归：candidate 就绪门、explore 报告、release 不可变、控制调用白名单。"""
import hashlib
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit_store import (  # noqa: E402
    AuditStore,
    build_final_audit_report,
    candidate_readiness,
    detect_unreported_operations,
    write_explore_report,
    write_final_audit_report,
    _candidate_closure_gate,
)
from engine.workflow_store import WorkflowStore  # noqa: E402


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _ready_workflow(db, workspace, content: bytes, required_checks=("final_audit",)):
    with WorkflowStore(db) as store:
        workflow = store.create_workflow("demo", {"workspace": str(workspace), "params": {}})
        step = store.add_steps(workflow.id, [{
            "name": "comp-final-audit",
            "metadata": {"required_checks": list(required_checks),
                         "output_files": ["AUDIT_REPORT.json"],
                         "has_checkpoint": True, "checkpoint_type": "approve"},
        }])[0]
        store.transition_step(step.id, "running")
        manifest = {"artifacts": [{"path": "paper/main.pdf", "sha256": _sha(content)}]}
        checks = {"checks": {name: {"ok": True} for name in required_checks}}
        store.transition_step_with_checkpoint(
            workflow.id, step.id, "completed",
            {"status": "completed", "manifest": manifest, "quality_gates": checks},
            event={"type": "step_completed", "manifest": manifest, "quality_gates": checks})
        return workflow.id


def test_control_call_whitelists_g4_g2_cli(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    db = tmp_path / "workflow.sqlite"
    with WorkflowStore(db) as store:
        workflow = store.create_workflow("demo", {"workspace": str(workspace)})
        step = store.add_steps(workflow.id, [{"name": "solve"}])[0]
        running = store.transition_step(step.id, "running")
    ticket = workspace / ".engine" / "sessions" / "ticket.json"
    ticket.parent.mkdir(parents=True)
    ticket.write_text(json.dumps({"database": str(db), "workflow_id": workflow.id,
                                  "step_id": step.id, "attempt_id": running.attempt_id,
                                  "revision": running.revision}), encoding="utf-8")
    commands = [
        f'python -m engine.workflow_cli session write --session "{ticket}" --path result.txt --stdin --input a.txt --input b.txt',
        f'python -m engine.workflow_cli session edit --session "{ticket}" --path report.txt --changes-file change.json --input fig.png',
        f'python -m engine.workflow_cli session reproduce --session "{ticket}" --plan plan.json --candidate cand-1',
        f'python -m engine.workflow_cli session abandon --session "{ticket}" --reason exploratory --by operator',
        f'python -m engine.workflow_cli promote --wf {workflow.id} --db "{db}" --root a.pdf --root b.pdf --by operator',
        f'python -m engine.workflow_cli start --template demo --workspace "{workspace}" --db "{db}" --mode explore --candidate cand-1',
        f'python -m engine.workflow_cli abandon --wf {workflow.id} --db "{db}" --reason stopped --by operator',
    ]
    calls = AuditStore(tmp_path)
    for command in commands:
        calls.record({"type": "tool_call", "tool": "bash", "detail": {"command": command}})
    result = detect_unreported_operations(
        workspace, tmp_path, evidence_paths=set(),
        control_scope={"workflow_id": workflow.id, "database": db,
                       "source_workflow_ids": [workflow.id], "checkpoint_ids": set()})
    assert result["unreported_bash"] == []
    assert result["verdict"] == "ok"
    assert {item["operation"] for item in result["workflow_control_calls"]} == {
        "session:write", "session:edit", "session:reproduce", "session:abandon",
        "promote", "start", "abandon"}
    # A promote for an unrelated source workflow is not whitelisted.
    calls.record({"type": "tool_call", "tool": "bash", "detail": {
        "command": f'python -m engine.workflow_cli promote --wf unrelated --db "{db}" --root a.pdf --by operator'}})
    again = detect_unreported_operations(
        workspace, tmp_path, evidence_paths=set(),
        control_scope={"workflow_id": workflow.id, "database": db,
                       "source_workflow_ids": [workflow.id], "checkpoint_ids": set()})
    assert any("promote --wf unrelated" in command for command in again["unreported_bash"])


def test_candidate_gates_block_delivery_report(tmp_path):
    workspace = tmp_path / "ws"
    project = tmp_path / "project"
    (workspace / "paper").mkdir(parents=True)
    (workspace / "paper/main.pdf").write_bytes(b"candidate pdf")
    (workspace / "raw.csv").write_text("x\n1\n", encoding="utf-8")
    raw_bytes = (workspace / "raw.csv").read_bytes()
    (workspace / ".engine").mkdir(parents=True)
    approvers = workspace / ".engine/approvers.json"
    approvers.write_text(json.dumps({"approvers": ["operator"], "require_human": True}),
                         encoding="utf-8")
    skill = project / "skills/comp-final-audit/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("audit skill", encoding="utf-8")
    rule = project / "rules/comp_rules.json"
    rule.parent.mkdir(parents=True)
    rule.write_text('{"rule": 1}', encoding="utf-8")
    acceptance = {
        "skills_root": "skills", "rules_root": "rules",
        "rule_files": {"comp_rules.json": _sha(rule.read_bytes())},
        "delivery_steps": [{"skill_name": "comp-final-audit", "skill_sha256": _sha(skill.read_bytes())}],
        "required_reviews": [{"skill_name": "comp-review", "role": "review"}],
        "reproduction_targets": [{"path": "paper/main.pdf",
                                  "sha256": _sha(b"candidate pdf"), "recipe_id": "r1"}],
        "approval_policy": {"approvers": ["operator"], "require_human": True,
                            "config_sha256": _sha(approvers.read_bytes())},
    }
    db = tmp_path / "workflow.sqlite"
    with WorkflowStore(db) as store:
        source = store.create_workflow("explore", {"workspace": str(workspace)})
        source_step = store.add_steps(source.id, [{"name": "solve"}])[0]
        candidate = store.create_candidate(
            source_workflow_id=source.id, source_step_id=source_step.id,
            source_attempt_id="a1",
            roots=[{"path": "paper/main.pdf", "sha256": _sha(b"candidate pdf")}],
            inputs={"raw.csv": {"sha256": _sha(raw_bytes), "kind": "external",
                                "producer_operation_id": None, "depth": 1}},
            frozen_versions={"paper/main.pdf": _sha(b"candidate pdf"),
                             "raw.csv": _sha(raw_bytes)},
            lineage={"producer_operations": {}, "external_inputs": {}, "unknown_inputs": []},
            recipe={"r1": {"argv": ["python", "solve.py"], "cwd": ".", "inputs": [],
                           "outputs": ["paper/main.pdf"], "mutates": []}},
            acceptance=acceptance, acceptance_sha256=_canonical_sha(acceptance),
            created_by="tester")
        delivery = store.create_workflow("delivery", {
            "workspace": str(workspace),
            "execution_contract": {"tier": "delivery", "version": 1},
            "delivery_candidate": {"candidate_id": candidate.id,
                                   "source_workflow_id": source.id},
        }, candidate_id=candidate.id)
        step = store.add_steps(delivery.id, [{
            "name": "comp-final-audit",
            "metadata": {"has_checkpoint": True, "required_checks": ["final_audit"],
                         "output_files": ["AUDIT_REPORT.json"]},
        }])[0]
        store.transition_step(step.id, "running")

        readiness = candidate_readiness(workspace, project, db, candidate.id)
        assert readiness["gates"]["candidate_frozen"]["ok"] is True, readiness
        assert readiness["gates"]["candidate_closure"]["ok"] is True, readiness
        assert readiness["gates"]["candidate_reproduction"]["ok"] is False, readiness
        assert readiness["gates"]["candidate_review"]["ok"] is False, readiness

    report = build_final_audit_report(workspace, project, workflow_db=db)
    assert report["delivery_decision"] == "blocked"
    assert report["gate_outcomes"]["candidate_frozen"] == "pass"
    assert report["gate_outcomes"]["candidate_reproduction"] == "fail"
    assert report["gate_outcomes"]["candidate_review"] == "fail"
    assert "candidate_approval" not in report["gate_outcomes"]  # pre-audit avoids deadlock
    assert report["candidate"]["missing"]


def test_release_report_is_immutable(tmp_path):
    workspace = tmp_path / "ws"
    (workspace / "paper").mkdir(parents=True)
    (workspace / "paper/main.pdf").write_bytes(b"release one")
    db = tmp_path / "workflow.sqlite"
    _ready_workflow(db, workspace, b"release one")
    first = write_final_audit_report(workspace, tmp_path, workflow_db=db)
    first_bytes = first.read_bytes()
    first_report = json.loads(first_bytes)
    assert first_report["delivery_decision"] == "ready"
    assert first_report["release_id"] and first_report["immutable"] is True
    old_audit = (workspace / "AUDIT_REPORT.json").read_bytes()
    old_release = first_report["release_id"]
    old_archive = workspace / "releases" / old_release

    time.sleep(0.02)
    (workspace / "paper/main.pdf").write_bytes(b"release two")
    _ready_workflow(db, workspace, b"release two")
    second = write_final_audit_report(workspace, tmp_path, workflow_db=db)
    second_report = json.loads(second.read_bytes())
    assert second_report["delivery_decision"] == "ready"
    assert second_report["release_id"] != old_release
    assert (workspace / "DELIVERY_REPORT.json").read_bytes() == second.read_bytes()
    assert (old_archive / "DELIVERY_REPORT.json").read_bytes() == first_bytes
    assert (old_archive / "AUDIT_REPORT.json").read_bytes() == old_audit
    new_archive = workspace / "releases" / second_report["release_id"]
    assert (new_archive / "DELIVERY_REPORT.json").is_file()
    assert (new_archive / "AUDIT_REPORT.json").is_file()


def test_blocked_report_can_become_ready(tmp_path):
    workspace = tmp_path / "ws"
    (workspace / "paper").mkdir(parents=True)
    (workspace / "paper/main.pdf").write_bytes(b"ready later")
    db = tmp_path / "workflow.sqlite"
    workflow_id = _ready_workflow(db, workspace, b"ready later")
    blocked = {
        "workflow_id": workflow_id,
        "artifacts": [{"path": "paper/main.pdf", "sha256": _sha(b"ready later")}],
        "gate_outcomes": {"old": "fail"},
        "waivers": [],
        "delivery_decision": "blocked",
        "release_id": "",
    }
    (workspace / "DELIVERY_REPORT.json").write_text(json.dumps(blocked), encoding="utf-8")
    target = write_final_audit_report(workspace, tmp_path, workflow_db=db)
    report = json.loads(target.read_bytes())
    assert report["delivery_decision"] == "ready"
    assert report["release_id"]


def test_write_explore_report_is_explore_only(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "notes.md").write_text("explore notes", encoding="utf-8")
    db = tmp_path / "workflow.sqlite"
    manifest = {"artifacts": [{"path": "notes.md", "sha256": _sha(b"explore notes")}]}
    with WorkflowStore(db) as store:
        workflow = store.create_workflow("demo", {
            "workspace": str(workspace),
            "execution_contract": {"tier": "explore", "version": 1},
        })
        step = store.add_steps(workflow.id, [{"name": "solve"}])[0]
        store.transition_step(step.id, "running")
        store.transition_step_with_checkpoint(
            workflow.id, step.id, "completed", {"manifest": manifest},
            event={"type": "step_completed", "manifest": manifest,
                   "quality_gates": {"checks": {"quality:page": {"ok": False}}}})
        store.complete_workflow(workflow.id)
    target = write_explore_report(workspace, tmp_path, workflow_db=db)
    report = json.loads(target.read_text(encoding="utf-8"))
    assert target.name == "EXPLORE_REPORT.json"
    assert report["contract_tier"] == "explore"
    assert report["delivery_decision"] == "explore_only"
    assert report["release_id"] == "" and report["immutable"] is False
    assert report["accepted_artifacts"] == [{"path": "notes.md", "sha256": _sha(b"explore notes")}]
    assert report["advisories"] == ["quality:page"]
    assert not (workspace / "AUDIT_REPORT.json").exists()
    assert not (workspace / "DELIVERY_REPORT.json").exists()
    with pytest.raises(ValueError, match="explore workflows use write_explore_report"):
        write_final_audit_report(workspace, tmp_path, workflow_db=db)


def test_candidate_reproduction_and_review_gates_pass(tmp_path):
    workspace = tmp_path / "ws"
    project = tmp_path / "project"
    (workspace / "paper").mkdir(parents=True)
    (workspace / "paper/main.pdf").write_bytes(b"reproduced pdf")
    (workspace / "raw.csv").write_text("x\n1\n", encoding="utf-8")
    raw_bytes = (workspace / "raw.csv").read_bytes()
    (workspace / ".engine").mkdir(parents=True)
    approvers = workspace / ".engine/approvers.json"
    approvers.write_text(json.dumps({"approvers": ["operator"], "require_human": True}),
                         encoding="utf-8")
    skill = project / "skills/comp-final-audit/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("audit skill", encoding="utf-8")
    rule = project / "rules/comp_rules.json"
    rule.parent.mkdir(parents=True)
    rule.write_text('{"rule": 1}', encoding="utf-8")
    spec = {"argv": ["python", "solve.py"], "cwd": ".", "inputs": ["raw.csv"],
            "outputs": ["paper/main.pdf"], "mutates": []}
    acceptance = {
        "skills_root": "skills", "rules_root": "rules",
        "rule_files": {"comp_rules.json": _sha(rule.read_bytes())},
        "delivery_steps": [{"skill_name": "comp-final-audit", "skill_sha256": _sha(skill.read_bytes())}],
        "required_reviews": [{"skill_name": "comp-review", "role": "review"}],
        "reproduction_targets": [{"path": "paper/main.pdf",
                                  "sha256": _sha(b"reproduced pdf"), "recipe_id": "r1"}],
        "approval_policy": {"approvers": ["operator"], "require_human": True,
                            "config_sha256": _sha(approvers.read_bytes())},
    }
    db = tmp_path / "workflow.sqlite"
    with WorkflowStore(db) as store:
        source = store.create_workflow("explore", {"workspace": str(workspace)})
        source_step = store.add_steps(source.id, [{"name": "solve"}])[0]
        candidate = store.create_candidate(
            source_workflow_id=source.id, source_step_id=source_step.id,
            source_attempt_id="a1",
            roots=[{"path": "paper/main.pdf", "sha256": _sha(b"reproduced pdf")}],
            inputs={"raw.csv": {"sha256": _sha(raw_bytes), "kind": "external",
                                "producer_operation_id": None, "depth": 1}},
            frozen_versions={"paper/main.pdf": _sha(b"reproduced pdf"),
                             "raw.csv": _sha(raw_bytes)},
            lineage={"producer_operations": {}, "external_inputs": {}, "unknown_inputs": []},
            recipe={"r1": spec},
            acceptance=acceptance, acceptance_sha256=_canonical_sha(acceptance),
            created_by="tester")
        delivery = store.create_workflow("delivery", {
            "workspace": str(workspace),
            "execution_contract": {"tier": "delivery", "version": 1},
            "delivery_candidate": {"candidate_id": candidate.id,
                                   "source_workflow_id": source.id},
        }, candidate_id=candidate.id)
        reproduction_step = store.add_steps(delivery.id, [{"name": "candidate-reproduction"}])[0]
        running = store.transition_step(reproduction_step.id, "running")
        operation_id = store.begin_operation(
            delivery.id, reproduction_step.id, running.attempt_id, running.revision,
            "command", "repro:paper/main.pdf", {})
        store.finish_operation(operation_id, "succeeded", {
            "command_record": {"command": "python solve.py", "cwd": "_reproduction/placeholder"},
            "outputs_snapshot": {"_reproduction/placeholder/paper/main.pdf": _sha(b"reproduced pdf")},
            "reproduction": {
                "candidate_id": candidate.id,
                "recipe_sha256": _canonical_sha(spec),
                "recipe": spec,
                "argv_rewrite": "workspace-absolute-to-repro-map-v1",
                "fresh_outputs": True,
                "targets": [{"target": "paper/main.pdf",
                             "mapped_path": f"_reproduction/{candidate.id}/r1/a/s/paper/main.pdf",
                             "hash_match": True,
                             "after_sha256": _sha(b"reproduced pdf")}],
            },
        })
        store.transition_step_with_checkpoint(
            delivery.id, reproduction_step.id, "completed", {},
            event={"type": "step_completed"})
        review_step = store.add_steps(delivery.id, [{"name": "comp-review"}])[0]
        running = store.transition_step(review_step.id, "running")
        operation_id = store.begin_operation(
            delivery.id, review_step.id, running.attempt_id, running.revision,
            "review", "review:COMP_REVIEW_VERDICT.json", {})
        store.finish_operation(operation_id, "succeeded", {
            "inputs_snapshot": {"paper/main.pdf": _sha(b"reproduced pdf")},
            "reviewer": "independent", "host_call_id": "host-1"})
        store.transition_step_with_checkpoint(
            delivery.id, review_step.id, "completed", {},
            event={"type": "step_completed"})

        readiness = candidate_readiness(workspace, project, db, candidate.id)
    assert readiness["gates"]["candidate_reproduction"]["ok"] is True, readiness
    assert readiness["gates"]["candidate_review"]["ok"] is True, readiness
    assert readiness["gates"]["candidate_approval"]["ok"] is False


def test_candidate_closure_allows_external_and_zero_inputs():
    from types import SimpleNamespace

    external = SimpleNamespace(missing=[], lineage={"external_inputs": {"raw.csv": "a" * 64}})
    assert _candidate_closure_gate(external)["ok"] is True
    zero_input = SimpleNamespace(missing=[], lineage={"unknown_inputs": []})
    assert _candidate_closure_gate(zero_input)["ok"] is True
    unknown = SimpleNamespace(missing=[], lineage={"unknown_inputs": ["mystery.py"]})
    assert _candidate_closure_gate(unknown)["ok"] is False
