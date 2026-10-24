"""Store-layer candidate approval guard regression (G2).

These tests exercise ``engine.approvals.assert_candidate_approval_allowed``
through the real ``WorkflowStore`` seams used by
``WorkflowRunner._approve_checkpoint``:

* ``transition_step_with_checkpoint(..., approval_checkpoint_id=, candidate_event=)``
* ``create_checkpoint(..., approval_checkpoint_id=, candidate_event=)``
* private ``_record_candidate_event``

The L1 log is the real ``AuditStore`` JSONL under the temp project root; no
mocked signature/token is used.  The documented malicious-local-process
residual (direct SQLite writes / forged L1) is intentionally not asserted as
prevented: the guard is normal-path validation plus audit traceability, not a
sandbox.
"""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.approvals import (
    APPROVAL_BOUNDARY,
    CandidateApprovalError,
    assert_candidate_approval_allowed,
    collect_candidate_l1_evidence,
)
from engine.audit_store import AuditStore, _candidate_approval_gate
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _setup(tmp_path: Path, *, names=("comp-final-audit",), block_index=None,
           approvers=("operator",)):
    """Create a candidate-bound delivery workflow with a blocked checkpoint."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    report = workspace / "AUDIT_REPORT.json"
    report.write_bytes(b'{"delivery_decision": "eligible"}')
    report_sha = _sha(report.read_bytes())

    store = WorkflowStore(tmp_path / "workflow.sqlite")
    source = store.create_workflow("explore", {"workspace": str(workspace)})
    source_step = store.add_steps(source.id, [{"name": "solve"}])[0]
    acceptance = {
        "params": {},
        "delivery_steps": [{"skill_name": "comp-final-audit",
                            "output_files": ["AUDIT_REPORT.json"],
                            "has_checkpoint": True, "checkpoint_type": "approve"}],
        "required_reviews": [{"skill_name": "comp-review", "role": "review"}],
        "reproduction_targets": [{"path": "AUDIT_REPORT.json", "sha256": report_sha,
                                  "recipe_id": "r1"}],
        "approval_policy": {"approvers": list(approvers), "require_human": True,
                            "config_sha256": "a" * 64},
    }
    candidate = store.create_candidate(
        source_workflow_id=source.id, source_step_id=source_step.id,
        source_attempt_id="attempt-1",
        roots=[{"path": "AUDIT_REPORT.json", "sha256": report_sha}],
        inputs={"raw.csv": {"sha256": "b" * 64, "kind": "external",
                            "producer_operation_id": None, "depth": 1}},
        frozen_versions={"AUDIT_REPORT.json": report_sha, "raw.csv": "b" * 64},
        lineage={"producer_operations": {}, "external_inputs": {"raw.csv": "b" * 64},
                 "unknown_inputs": []},
        recipe={"r1": {"argv": ["python", "solve.py"], "cwd": ".", "inputs": ["raw.csv"],
                       "outputs": ["AUDIT_REPORT.json"], "mutates": []}},
        acceptance=acceptance, acceptance_sha256=_canonical_sha(acceptance),
        created_by="tester", missing=["reproduction", "review", "approval"])
    workflow = store.create_workflow("delivery", {
        "workspace": str(workspace),
        "execution_contract": {"tier": "delivery", "version": 1},
        "delivery_candidate": {"candidate_id": candidate.id,
                               "source_workflow_id": source.id},
        "approval_policy": dict(acceptance["approval_policy"]),
    }, candidate_id=candidate.id)
    steps = store.add_steps(workflow.id, [
        {"name": name, "has_checkpoint": True, "checkpoint_type": "approve",
         "metadata": {"has_checkpoint": True, "checkpoint_type": "approve",
                      "output_files": ["AUDIT_REPORT.json"]}}
        for name in names])
    index = len(steps) - 1 if block_index is None else block_index
    step = steps[index]
    store.transition_step(step.id, "running")
    _, checkpoint = store.transition_step_with_checkpoint(
        workflow.id, step.id, "blocked",
        {"status": "waiting_checkpoint", "validation": {"ok": True},
         "manifest": {"artifacts": [{"path": "AUDIT_REPORT.json",
                                     "sha256": report_sha}]}},
        event={"type": "step_completed"})
    return SimpleNamespace(store=store, workspace=workspace, candidate=candidate,
                           workflow=workflow, steps=steps, step=step,
                           checkpoint=checkpoint, report_sha=report_sha)


def _record_host_event(tmp_path: Path, workspace: Path, *, command: str = "",
                       file_path: str = "", session: str = "S1",
                       tool: str = "bash", event_type: str = "tool_call",
                       ts: str | None = None):
    entry = {"type": event_type, "tool": tool, "detail": {}}
    if command:
        entry["detail"]["command"] = command
    if file_path:
        entry["detail"]["filePath"] = file_path
    if session:
        entry["detail"]["sessionID"] = session
    if ts:
        entry["ts"] = ts
    AuditStore(tmp_path).record(entry)


def _approve(setup, *, by: str = "operator", payload: dict | None = None,
             approval_checkpoint_id: str | None = None):
    store = setup.store
    checkpoint_id = setup.checkpoint.id if approval_checkpoint_id is None else approval_checkpoint_id
    return store.transition_step_with_checkpoint(
        setup.workflow.id, setup.step.id, "completed",
        {"status": "approved", "approved_checkpoint_id": checkpoint_id},
        event={"type": "checkpoint_approved", "approved_by": by,
               "approved_checkpoint_id": checkpoint_id},
        expected_revision=store.get_step(setup.step.id).revision,
        expected_checkpoint_id=setup.checkpoint.id,
        approval_checkpoint_id=checkpoint_id,
        candidate_event={"event_type": "candidate_approved",
                         "candidate_id": setup.candidate.id,
                         "approved_by": by,
                         "payload": payload if payload is not None else {"approved_by": by}},
        finalize_if_complete=True,
    )


def _counts(store, workflow_id: str) -> tuple[int, int, int]:
    checkpoints = store._connection.execute(
        "SELECT COUNT(*) FROM checkpoints WHERE workflow_id=?", (workflow_id,)).fetchone()[0]
    events = store._connection.execute(
        "SELECT COUNT(*) FROM events WHERE workflow_id=?", (workflow_id,)).fetchone()[0]
    candidate_events = store._connection.execute(
        "SELECT COUNT(*) FROM candidate_events").fetchone()[0]
    return checkpoints, events, candidate_events


def test_guard_accepts_valid_final_approval_and_binds_old_checkpoint(tmp_path):
    setup = _setup(tmp_path)
    _record_host_event(tmp_path, setup.workspace,
                       command=f"python inspect.py --workspace {setup.workspace}",
                       session="S1")

    step, transition_checkpoint = _approve(setup)

    assert step.status.value == "completed"
    assert transition_checkpoint.id != setup.checkpoint.id
    candidate_events = setup.store.candidate_events(setup.candidate.id)
    approved = [event for event in candidate_events
                if event["event_type"] == "candidate_approved"]
    assert len(approved) == 1
    assert approved[0]["checkpoint_id"] == setup.checkpoint.id
    assert approved[0]["orphan"] is False
    assert approved[0]["payload"]["l1_available"] is True
    assert approved[0]["payload"]["agent_approve_seen"] is False
    assert approved[0]["payload"]["same_session_approve"] is False
    assert approved[0]["payload"]["degraded_host_attestation"] is False
    assert approved[0]["payload"]["approved_by"] == "operator"
    assert approved[0]["payload"]["attributed_event_count"] == 1

    timeline = setup.store.workflow_timeline(setup.workflow.id)
    workflow_approval = [event for event in timeline["events"]
                         if event["type"] == "checkpoint_approved"]
    assert len(workflow_approval) == 1
    # The workflow event row is attached to the NEW transition checkpoint, while
    # its payload binds the OLD blocked checkpoint.
    assert workflow_approval[0]["checkpoint_id"] == transition_checkpoint.id
    assert workflow_approval[0]["payload"]["approved_checkpoint_id"] == setup.checkpoint.id

    gate = _candidate_approval_gate(
        setup.store, setup.store.get_candidate(setup.candidate.id), setup.workspace)
    assert gate["ok"] is True, gate


def test_guard_rejects_non_final_audit_step_and_non_last_step(tmp_path):
    setup = _setup(tmp_path, names=("comp-review",))
    _record_host_event(tmp_path, setup.workspace, command=f"cd {setup.workspace} && python x.py")
    with pytest.raises(CandidateApprovalError, match="comp-final-audit"):
        _approve(setup)
    assert setup.store.get_step(setup.step.id).status.value == "blocked"
    assert not any(event["event_type"] == "candidate_approved"
                   for event in setup.store.candidate_events(setup.candidate.id))

    setup2 = _setup(tmp_path / "second", names=("comp-final-audit", "comp-review"),
                    block_index=0)
    _record_host_event(tmp_path / "second", setup2.workspace,
                       command=f"cd {setup2.workspace} && python x.py")
    with pytest.raises(CandidateApprovalError, match="最后一步"):
        _approve(setup2)
    assert setup2.store.get_step(setup2.step.id).status.value == "blocked"


def test_guard_rejects_whitelist_and_agent_self_reference(tmp_path):
    setup = _setup(tmp_path)
    _record_host_event(tmp_path, setup.workspace, command=f"cd {setup.workspace} && python x.py")
    with pytest.raises(CandidateApprovalError, match="白名单"):
        _approve(setup, by="intruder")

    setup2 = _setup(tmp_path / "agent", approvers=("agent", "operator"))
    _record_host_event(tmp_path / "agent", setup2.workspace,
                       command=f"cd {setup2.workspace} && python x.py")
    with pytest.raises(CandidateApprovalError, match="自指"):
        _approve(setup2, by="agent")

    setup3 = _setup(tmp_path / "empty")
    _record_host_event(tmp_path / "empty", setup3.workspace,
                       command=f"cd {setup3.workspace} && python x.py")
    with pytest.raises(CandidateApprovalError, match="approved_by 为空"):
        _approve(setup3, by="   ")


def test_guard_rejects_without_path_attributed_l1(tmp_path):
    setup = _setup(tmp_path)
    # Pathless host events do not make L1 available.
    _record_host_event(tmp_path, setup.workspace, command="", tool="skill", session="S1")
    before = _counts(setup.store, setup.workflow.id)
    with pytest.raises(CandidateApprovalError, match="degraded_host_attestation"):
        _approve(setup)
    assert _counts(setup.store, setup.workflow.id) == before
    assert setup.store.get_step(setup.step.id).status.value == "blocked"
    assert setup.store.candidate_events(setup.candidate.id) == []


def test_guard_ignores_other_workspace_and_pre_window_events(tmp_path):
    setup = _setup(tmp_path)
    other = tmp_path / "other-workspace"
    other.mkdir()
    _record_host_event(tmp_path, setup.workspace,
                       command=f"cd {other} && python x.py", session="S1")
    _record_host_event(tmp_path, setup.workspace,
                       command=f"cd {setup.workspace} && python x.py", session="S1",
                       ts="2000-01-01T00:00:00+00:00")
    with pytest.raises(CandidateApprovalError, match="degraded_host_attestation"):
        _approve(setup)


@pytest.mark.parametrize("command", [
    "python -m engine.workflow_cli approve --checkpoint cp",
    ('python -c "from engine.workflow_runner import WorkflowRunner; '
     'WorkflowRunner.approve_checkpoint(self, cp)"'),
    "python workflow_runner.py --approve",
    'sqlite3 workflow.sqlite "INSERT INTO candidate_events VALUES (... candidate_approved ...)"',
    'sqlite3 workflow.sqlite "DELETE FROM events WHERE id=1"',
    "python approve.py --checkpoint cp",
])
def test_guard_rejects_agent_approval_patterns_a_to_f(tmp_path, command):
    setup = _setup(tmp_path)
    _record_host_event(tmp_path, setup.workspace,
                       command=f"cd {setup.workspace} && {command}", session="S1")
    with pytest.raises(CandidateApprovalError, match="agent"):
        _approve(setup)
    assert setup.store.get_step(setup.step.id).status.value == "blocked"
    assert not any(event["event_type"] == "candidate_approved"
                   for event in setup.store.candidate_events(setup.candidate.id))


def test_guard_computes_same_session_from_host_sessions(tmp_path):
    setup = _setup(tmp_path)
    _record_host_event(tmp_path, setup.workspace,
                       command=f"cd {setup.workspace} && python generate.py", session="S1")
    _record_host_event(tmp_path, setup.workspace,
                       command=f"cd {setup.workspace} && python -m engine.workflow_cli approve --checkpoint {setup.checkpoint.id}",
                       session="S1")
    evidence = collect_candidate_l1_evidence(
        setup.store, setup.workflow, checkpoint_id=setup.checkpoint.id,
        approved_by="operator")
    assert evidence["l1_available"] is True
    assert evidence["agent_approve_seen"] is True
    assert evidence["same_session_approve"] is True
    assert evidence["attributed_event_count"] == 2
    with pytest.raises(CandidateApprovalError):
        _approve(setup)


def test_guard_rejects_claimed_l1_without_host_evidence(tmp_path):
    setup = _setup(tmp_path)
    forged = {"approved_by": "operator", "l1_available": True,
              "agent_approve_seen": False, "same_session_approve": False,
              "degraded_host_attestation": False,
              "l1_window_start": "2000-01-01T00:00:00+00:00"}
    with pytest.raises(CandidateApprovalError, match="degraded_host_attestation"):
        _approve(setup, payload=forged)
    assert not any(event["event_type"] == "candidate_approved"
                   for event in setup.store.candidate_events(setup.candidate.id))


def test_guard_rejects_missing_or_mismatched_checkpoint_binding(tmp_path):
    setup = _setup(tmp_path)
    _record_host_event(tmp_path, setup.workspace, command=f"cd {setup.workspace} && python x.py")
    with pytest.raises(CandidateApprovalError, match="旧 blocked checkpoint"):
        _approve(setup, approval_checkpoint_id="")

    setup2 = _setup(tmp_path / "mismatch", names=("comp-final-audit", "comp-review"))
    # Approve the non-final step with the review checkpoint id: step/checkpoint mismatch.
    _record_host_event(tmp_path / "mismatch", setup2.workspace,
                       command=f"cd {setup2.workspace} && python x.py")
    review_step = setup2.steps[1]
    setup2.store.transition_step(review_step.id, "running")
    _, review_checkpoint = setup2.store.transition_step_with_checkpoint(
        setup2.workflow.id, review_step.id, "blocked",
        {"status": "waiting_checkpoint", "validation": {"ok": True},
         "manifest": {"artifacts": [{"path": "AUDIT_REPORT.json",
                                     "sha256": setup2.report_sha}]}},
        event={"type": "step_completed"})
    with pytest.raises(CandidateApprovalError):
        _approve(setup2, approval_checkpoint_id=review_checkpoint.id)


def test_guard_rejects_tampered_manifest(tmp_path):
    setup = _setup(tmp_path)
    _record_host_event(tmp_path, setup.workspace, command=f"cd {setup.workspace} && python x.py")
    (setup.workspace / "AUDIT_REPORT.json").write_text("changed after checkpoint", encoding="utf-8")
    with pytest.raises(CandidateApprovalError, match="manifest"):
        _approve(setup)


def test_guard_rejects_candidate_workflow_mismatch(tmp_path):
    setup = _setup(tmp_path)
    _record_host_event(tmp_path, setup.workspace, command=f"cd {setup.workspace} && python x.py")
    with pytest.raises(CandidateApprovalError, match="绑定不一致"):
        assert_candidate_approval_allowed(
            setup.store, workflow_id=setup.workflow.id, step_id=setup.step.id,
            approval_checkpoint_id=setup.checkpoint.id,
            transition_checkpoint_id="00000000-0000-0000-0000-000000000000",
            candidate_id="some-other-candidate", approved_by="operator",
            event_type="candidate_approved", event_payload={"payload": {}})


def test_guard_rejects_existing_transition_checkpoint_id(tmp_path):
    setup = _setup(tmp_path)
    source = setup.store.get_workflow(setup.candidate.source_workflow_id)
    source_step = setup.store._connection.execute(
        "SELECT id FROM workflow_steps WHERE workflow_id=?", (source.id,)).fetchone()
    existing = setup.store.create_checkpoint(
        source.id, source_step["id"], {"status": "fixture"})
    with pytest.raises(CandidateApprovalError, match="已存在"):
        assert_candidate_approval_allowed(
            setup.store, workflow_id=setup.workflow.id, step_id=setup.step.id,
            approval_checkpoint_id=setup.checkpoint.id,
            transition_checkpoint_id=existing.id,
            candidate_id=setup.candidate.id, approved_by="operator",
            event_type="candidate_approved", event_payload={"payload": {}})


def test_create_checkpoint_cannot_write_candidate_approved(tmp_path):
    setup = _setup(tmp_path)
    before = _counts(setup.store, setup.workflow.id)
    with pytest.raises(ValueError, match="approval guard"):
        setup.store.create_checkpoint(
            setup.workflow.id, setup.step.id, {"status": "waiting_checkpoint"},
            event={"type": "checkpoint_approved", "approved_by": "operator",
                   "approved_checkpoint_id": setup.checkpoint.id},
            approval_checkpoint_id=setup.checkpoint.id,
            candidate_event={"event_type": "candidate_approved",
                             "candidate_id": setup.candidate.id,
                             "approved_by": "operator", "payload": {}})
    assert _counts(setup.store, setup.workflow.id) == before


def test_guard_rejects_unattributed_approve_command_by_checkpoint_id(tmp_path):
    setup = _setup(tmp_path)
    # One benign attributed event makes L1 "available"...
    _record_host_event(tmp_path, setup.workspace,
                       command=f"cd {setup.workspace} && python generate.py", session="S1")
    # ...while the approve wrapper does not mention the workspace path; the
    # conservative fallback must still catch it through the checkpoint id.
    _record_host_event(
        tmp_path, setup.workspace,
        command=f"python -m engine.workflow_cli approve --checkpoint {setup.checkpoint.id}",
        session="S2")
    with pytest.raises(CandidateApprovalError, match="agent"):
        _approve(setup)


def test_create_checkpoint_approval_requires_candidate_event(tmp_path):
    setup = _setup(tmp_path)
    before = _counts(setup.store, setup.workflow.id)
    with pytest.raises(CandidateApprovalError, match="candidate_event"):
        setup.store.create_checkpoint(
            setup.workflow.id, setup.step.id, {"status": "waiting_checkpoint"},
            event={"type": "checkpoint_approved", "approved_by": "operator",
                   "approved_checkpoint_id": setup.checkpoint.id},
            approval_checkpoint_id=setup.checkpoint.id)
    assert _counts(setup.store, setup.workflow.id) == before


def test_private_recorder_rejects_candidate_approved_without_guard(tmp_path):
    setup = _setup(tmp_path)
    with pytest.raises(ValueError, match="approval guard"):
        setup.store._record_candidate_event(
            setup.candidate.id, setup.checkpoint.id, setup.step.id,
            "candidate_approved", {"approved_by": "operator"})
    assert setup.store.candidate_events(setup.candidate.id) == []


def test_guard_returns_audit_evidence_for_file_path_attribution(tmp_path):
    setup = _setup(tmp_path)
    _record_host_event(tmp_path, setup.workspace, tool="read", event_type="tool_result",
                       file_path=str(setup.workspace / "AUDIT_REPORT.json"), session="S1")
    evidence = collect_candidate_l1_evidence(
        setup.store, setup.workflow, checkpoint_id=setup.checkpoint.id,
        approved_by="operator")
    assert evidence["l1_available"] is True
    assert evidence["degraded_host_attestation"] is False
    assert evidence["attributed_event_count"] == 1


def test_runner_approval_call_site_passes_store_guard(tmp_path, monkeypatch):
    setup = _setup(tmp_path)
    _record_host_event(tmp_path, setup.workspace,
                       command=f"cd {setup.workspace} && python generate.py", session="S1")
    from engine import audit_store

    monkeypatch.setattr(
        audit_store, "build_final_audit_report",
        lambda *args, **kwargs: {"delivery_decision": "eligible"})

    def _fake_write_final(workspace, *args, **kwargs):
        out = kwargs.get("out") or Path(workspace) / "DELIVERY_REPORT.json"
        Path(out).write_text('{"delivery_decision": "ready"}', encoding="utf-8")
        return Path(out)

    monkeypatch.setattr(audit_store, "write_final_audit_report", _fake_write_final)
    skills = tmp_path / "skills"
    skills.mkdir()
    runner = WorkflowRunner(setup.store, {"demo": {"sub_steps": []}}, skills,
                            audit_root=tmp_path)
    result = runner._approve_checkpoint(
        setup.checkpoint.id, {"approved": True, "approved_by": "operator"})
    assert result.status == "completed", result.message
    approved = [event for event in setup.store.candidate_events(setup.candidate.id)
                if event["event_type"] == "candidate_approved"]
    assert len(approved) == 1
    assert approved[0]["checkpoint_id"] == setup.checkpoint.id
    assert approved[0]["payload"]["l1_available"] is True
    assert approved[0]["payload"]["attributed_event_count"] == 1


# G4/G2 设计文档在 dev-docs/（内部真源根，全私有零入库）：公开 clone 缺席时只丢
# 设计文档那半段断言，tracked 生产资料 APPROVAL_BOUNDARY 照常断言——口径同
# test_award_layout_index.py（gitignored 私有资产缺席按语义 SKIP，不得以文件缺失红 CI）。
DESIGN_DOC = (ROOT.parent / "dev-docs" / "designs"
              / "2026-10-23-G4-G2-引擎改造设计.md")


def test_approval_boundary_is_documented():
    assert "恶意本地进程残余类" in APPROVAL_BOUNDARY
    assert "不是沙箱" in APPROVAL_BOUNDARY
    if not DESIGN_DOC.is_file():
        pytest.skip("G4/G2 设计文档为 dev-docs 私有真源（零入库），公开 clone 语义缺位")
    design = DESIGN_DOC.read_text(encoding="utf-8")
    assert "恶意本地进程残余类，进程内无法防御" in design
    assert "不是沙箱" in design
    assert "可追溯检测" in design
