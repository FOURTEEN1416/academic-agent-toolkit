"""G2 end-to-end：explore -> promote -> candidate delivery -> reproduction ->
required reviews -> final-audit checkpoint -> L1 approve/degrade -> ready release.

The test intentionally uses the real runner/session/store code paths with a
minimal synthetic template and workspace; only the external host L1 log is
written as a test fixture (that is exactly what the host hook would record).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit_store import (  # noqa: E402
    AuditStore,
    candidate_readiness,
    write_final_audit_report,
)
from engine.workflow_runner import WorkflowRunner  # noqa: E402
from engine.workflow_store import WorkflowStore  # noqa: E402
from execution.session import ExecutionSession  # noqa: E402

REVIEW_INPUTS = (
    "paper/main.tex",
    "paper/main.pdf",
    "RESULTS.md",
    "figures/all_results.json",
    "CONSISTENCY_REPORT.json",
    "LITERATURE.md",
    "PAPER_SCORING.json",
    "COMP_REVIEW_VERDICT.json",
    "VISUAL_REVIEW_VERDICT.json",
    "EDITOR_CHANGELOG.md",
)

REVIEW_FILES = {
    "comp-review": ("COMP_REVIEW.md", "COMP_REVIEW_VERDICT.json"),
    "comp-visual-review": ("VISUAL_REVIEW.md", "VISUAL_REVIEW_VERDICT.json"),
    "comp-final-review": ("FINAL_REVIEW.md", "FINAL_REVIEW_VERDICT.json"),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _make_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    # Keep project_root == runner.audit_root.  ``build_final_audit_report`` uses
    # the runner audit root as project_root when re-evaluating candidate_frozen.
    project = tmp_path
    skills = project / "academic-toolkit" / "skills"
    for name in ("solve", "candidate-reproduction", *REVIEW_FILES, "comp-final-audit"):
        folder = skills / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(f"fixture skill {name}\n", encoding="utf-8")
    rules = project / "academic-toolkit" / "engine" / "modex-core"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / "comp_rules.json").write_text('{"contest": "fixture"}\n', encoding="utf-8")
    return project, skills, rules


def _catalog() -> dict:
    review_specs = []
    for skill_name, (report, verdict) in REVIEW_FILES.items():
        review_specs.append({
            "skill_name": skill_name,
            "display_name": skill_name,
            "output_files": [report, verdict],
            "primary_output": verdict,
            "has_checkpoint": False,
            "checkpoint_type": None,
            "required_checks": [],
            "output_specs": {},
        })
    return {
        "explore_demo": {"sub_steps": [{
            "skill_name": "solve",
            "display_name": "Solve fixture",
            "output_files": ["result.txt", *REVIEW_INPUTS],
            "primary_output": "result.txt",
            "has_checkpoint": False,
            "checkpoint_type": None,
            "required_checks": [],
            "output_specs": {},
        }]},
        "delivery_demo": {"sub_steps": [
            *review_specs,
            {
                "skill_name": "comp-final-audit",
                "display_name": "Final audit",
                "output_files": ["AUDIT_REPORT.json"],
                "primary_output": "AUDIT_REPORT.json",
                "has_checkpoint": True,
                "checkpoint_type": "approve",
                "required_checks": [],
                "output_specs": {},
            },
        ]},
    }


def _write_approvers(workspace: Path) -> None:
    config = workspace / ".engine" / "approvers.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"approvers": ["operator"], "require_human": True}),
                      encoding="utf-8")


def _run_explore(runner, workspace: Path):
    workflow = runner.start("explore_demo", workspace, {}, mode="explore")
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.write(
        "solve.py",
        "from pathlib import Path\n"
        "value = int(Path('input.txt').read_text())\n"
        "Path('result.txt').write_text(str(value * 3))\n",
        inputs=[],
    )
    session.files.write("input.txt", "7", inputs=[])
    for name in REVIEW_INPUTS:
        session.files.write(name, f"review fixture bytes for {name}\n", inputs=[])
    result = session.commands.execute({
        "id": "solve",
        "argv": [sys.executable, "solve.py"],
        "inputs": ["input.txt", "solve.py"],
        "outputs": ["result.txt"],
        "pure": True,
        "complete_inputs": True,
    })
    assert result["status"] == "succeeded", result
    finished = session.finish()
    assert finished["status"] == "completed", finished
    return workflow


def _review_step(runner, workflow_id: str, skill_name: str) -> None:
    report_name, verdict_name = REVIEW_FILES[skill_name]
    session = ExecutionSession(runner, workflow_id)
    session.context()
    session.files.write(report_name, f"# {skill_name}\nindependent review body\n", inputs=[])
    response_path = f"review_payloads/{skill_name}.json"
    verdict = {"findings": [], "fatal_count": 0,
               "summary": "fixture independent review response body"}
    if skill_name == "comp-visual-review":
        verdict["status"] = "pass"
    session.files.write(response_path, json.dumps(verdict), inputs=[])
    reviewed = ["result.txt"]
    if skill_name == "comp-visual-review":
        reviewed.append("COMP_REVIEW_VERDICT.json")
    elif skill_name == "comp-final-review":
        reviewed.extend(["COMP_REVIEW_VERDICT.json", "VISUAL_REVIEW_VERDICT.json"])
    task = session.review.request(reviewed, verdict_name, f"fixture rubric for {skill_name}")
    session.review.receive(task["review_task"], response_path,
                           reviewer=f"reviewer-{skill_name}",
                           host_call_id=f"host-call-{skill_name}")

    if skill_name == "comp-final-review":
        # The full review gate (triggered by FINAL_REVIEW.md) also requires the
        # editor changelog and a four-role provenance sidecar.
        session.files.write("EDITOR_CHANGELOG.md", "# editor changelog\nfixture edits\n", inputs=[])
        workspace = session.workspace
        roles = {
            "reviewer": ("COMP_REVIEW.md", "reviewer-comp-review"),
            "visual_reviewer": ("VISUAL_REVIEW.md", "reviewer-comp-visual-review"),
            "editor": ("EDITOR_CHANGELOG.md", "editor-fixture"),
            "final_reviewer": ("FINAL_REVIEW.md", "reviewer-comp-final-review"),
        }
        evidence = {"roles": {}}
        for role, (output_file, session_id) in roles.items():
            evidence["roles"][role] = {
                "session_id": session_id,
                "model": "fixture-model",
                "output_sha256": _sha((workspace / output_file).read_bytes()),
                "completed_at": "2026-10-24T00:00:00+00:00",
                "output_file": output_file,
            }
        session.files.write("REVIEW_EXECUTION_EVIDENCE.json",
                            json.dumps(evidence, ensure_ascii=False), inputs=[])

    finished = session.finish()
    if finished["status"] not in {"advanced", "completed"}:
        failed = {name: check for name, check in finished["diagnostics"]["checks"].items()
                  if not (isinstance(check, dict) and check.get("ok") is True)}
        raise AssertionError(json.dumps(failed, ensure_ascii=False, indent=2))


def _add_second_ready_workflow(store: WorkflowStore, workspace: Path, content: bytes) -> str:
    """Synthetic non-candidate delivery workflow used to force a second release."""
    workflow = store.create_workflow("release_probe", {"workspace": str(workspace), "params": {}})
    step = store.add_steps(workflow.id, [{
        "name": "comp-final-audit",
        "metadata": {"output_files": ["result.txt"], "has_checkpoint": True,
                     "checkpoint_type": "approve", "required_checks": []},
    }])[0]
    running = store.transition_step(step.id, "running")
    manifest = {"artifacts": [{"path": "result.txt", "sha256": _sha(content)}]}
    checks = {"checks": {"final_audit": {"ok": True}}}
    store.transition_step_with_checkpoint(
        workflow.id, step.id, "completed",
        {"status": "completed", "validation": {"ok": True}, "manifest": manifest,
         "quality_gates": checks},
        event={"type": "step_completed", "manifest": manifest, "quality_gates": checks},
        expected_revision=running.revision,
        finalize_if_complete=True,
    )
    return workflow.id


def test_g2_explore_promote_candidate_delivery_approve_and_immutable_release(tmp_path, monkeypatch):
    # Keep review-provenance model comparison deterministic; this fixture does not
    # exercise the real four-role model configuration.
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(tmp_path / "missing_contest_models.json"))
    project, skills, _rules = _make_project(tmp_path)
    catalog = _catalog()
    db = tmp_path / "workflow.sqlite"
    store = WorkflowStore(db)
    # The reproduction directory embeds the real candidate/recipe/attempt/
    # submission ids. Use a short temp prefix (outside pytest's long tmp_path)
    # so the real subprocess cwd stays inside the Windows MAX_PATH limit on
    # machines without long-path opt-in; the candidate id is not shortened.
    workspace = Path(tempfile.mkdtemp(prefix="g2e2e-"))
    try:
        runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)

        # 1) explore: real execution session, no DELIVERY_REPORT/AUDIT_REPORT.
        explore = _run_explore(runner, workspace)
        assert store.get_workflow(explore.id).status == "completed"
        assert (workspace / "EXPLORE_REPORT.json").is_file()
        explore_report = json.loads((workspace / "EXPLORE_REPORT.json").read_text(encoding="utf-8"))
        assert explore_report["delivery_decision"] == "explore_only"
        assert not (workspace / "AUDIT_REPORT.json").exists()
        assert not (workspace / "DELIVERY_REPORT.json").exists()

        # 2) promote freezes the accepted root, lineage, recipe and acceptance.
        _write_approvers(workspace)
        candidate = runner.promote(explore.id, ["result.txt"], by="operator",
                                   template="delivery_demo")
        # The explore fixtures include review-input placeholders. Remove the
        # verdict/editor stubs so the delivery review chain starts with the real
        # review steps (candidate review inputs are frozen but not re-read here).
        for stale in ("COMP_REVIEW_VERDICT.json", "VISUAL_REVIEW_VERDICT.json",
                      "EDITOR_CHANGELOG.md"):
            (workspace / stale).unlink(missing_ok=True)
        assert candidate.status == "not_ready"
        assert candidate.roots[0]["path"] == "result.txt"
        assert candidate.roots[0]["producer_operation_id"]
        assert candidate.inputs["input.txt"]["kind"] == "produced"
        assert candidate.acceptance["required_reviews"] == [
            {"skill_name": "comp-review", "role": "review"},
            {"skill_name": "comp-visual-review", "role": "visual"},
            {"skill_name": "comp-final-review", "role": "final"},
        ]
        assert candidate.acceptance["reproduction_targets"][0]["path"] == "result.txt"
        assert {"reproduction", "review", "approval"} <= set(candidate.missing)

        # 3) candidate delivery: only carry/reproduction/reviews/final-audit.
        delivery = runner.start("delivery_demo", workspace, {}, candidate_id=candidate.id)
        names = [row["name"] for row in store._connection.execute(
            "SELECT name FROM workflow_steps WHERE workflow_id=? ORDER BY position",
            (delivery.id,)).fetchall()]
        assert names == ["promotion-carry", "candidate-reproduction",
                         "comp-review", "comp-visual-review", "comp-final-review",
                         "comp-final-audit"]
        assert store.get_candidate(candidate.id).status == "in_delivery"

        # 4) reproduction through execute_reproduction in a fresh submission dir.
        reproduction = ExecutionSession(runner, delivery.id)
        reproduction.context()
        reproduced = reproduction.reproduce("REPRODUCTION_PLAN.json", candidate.id)
        assert reproduced["reproduction"]["ok"] is True, reproduced
        assert reproduced["reproduction"]["targets"][0]["target"] == "result.txt"
        assert reproduced["reproduction"]["targets"][0]["hash_match"] is True
        assert reproduced["reproduction"]["argv_rewrite"] == "workspace-absolute-to-repro-map-v1"
        repro_payload = json.loads(store._connection.execute(
            "SELECT payload FROM execution_operations WHERE workflow_id=? AND kind='command' "
            "ORDER BY rowid DESC LIMIT 1", (delivery.id,)).fetchone()["payload"])
        assert repro_payload["reproduction"]["fresh_outputs"] is True
        assert repro_payload["reproduction"]["recipe_sha256"]
        assert reproduction.finish()["status"] in {"advanced", "completed"}

        # 5) required reviews, each with a real version-bound review operation.
        for skill_name in ("comp-review", "comp-visual-review", "comp-final-review"):
            _review_step(runner, delivery.id, skill_name)

        # 6) final audit pre-audit -> BLOCKED checkpoint.
        final = ExecutionSession(runner, delivery.id)
        final.context()
        audit_check = final.commands.execute({
            "id": "audit-check",
            "argv": [sys.executable, "-c", "print('audit fixture ok')"],
            "mode": "check",
            "inputs": ["result.txt"],
        })
        assert audit_check["status"] == "succeeded", audit_check
        blocked = final.finish()
        if blocked["status"] != "waiting_checkpoint":
            failed = {name: check for name, check in blocked["diagnostics"]["checks"].items()
                      if not (isinstance(check, dict) and check.get("ok") is True)}
            raise AssertionError(json.dumps(failed, ensure_ascii=False, indent=2))
        checkpoint_id = blocked["checkpoint_id"]
        assert checkpoint_id
        pre_audit = json.loads(
            (workspace / "reports" / delivery.id / "AUDIT_REPORT.json").read_text(encoding="utf-8"))
        assert pre_audit["delivery_decision"] == "eligible"
        assert pre_audit["contract_tier"] == "delivery"
        assert not (workspace / "DELIVERY_REPORT.json").exists()

        # 7a) without path-attributed L1 host evidence: degraded + blocked, no approval.
        degraded = runner._approve_checkpoint(checkpoint_id, {"approved": True,
                                                              "approved_by": "operator"})
        assert degraded.status == "blocked"
        assert "degraded" in degraded.message or "L1" in degraded.message
        degraded_events = [e for e in store.candidate_events(candidate.id)
                           if e["event_type"] == "candidate_approval_degraded"]
        assert degraded_events and degraded_events[-1]["payload"]["l1_available"] is False
        assert degraded_events[-1]["payload"]["degraded_host_attestation"] is True
        assert store.get_step(blocked["step_id"]).status.value == "blocked"
        assert not any(e["event_type"] == "candidate_approved"
                       for e in store.candidate_events(candidate.id))

        # 7b) with a path-attributed L1 host event in the workflow window: approve.
        AuditStore(tmp_path).record({
            "type": "tool_result",
            "tool": "read",
            "detail": {"filePath": str(workspace / "result.txt"), "sessionID": "fixture-session"},
        })
        approved = runner._approve_checkpoint(checkpoint_id, {"approved": True,
                                                              "approved_by": "operator"})
        assert approved.status == "completed", approved.message
        approved_events = [e for e in store.candidate_events(candidate.id)
                           if e["event_type"] == "candidate_approved"]
        assert len(approved_events) == 1
        assert approved_events[0]["checkpoint_id"] == checkpoint_id
        assert approved_events[0]["orphan"] is False
        assert approved_events[0]["payload"]["l1_available"] is True
        assert approved_events[0]["payload"]["degraded_host_attestation"] is False
        assert approved_events[0]["payload"]["approved_by"] == "operator"

        # 8) delivery decision ready, candidate CAS to ready, release archived.
        readiness = candidate_readiness(workspace, project, db, candidate.id)
        assert readiness["ok"] is True, readiness
        delivery_report = json.loads(
            (workspace / "DELIVERY_REPORT.json").read_text(encoding="utf-8"))
        assert delivery_report["delivery_decision"] == "ready"
        assert delivery_report["candidate_id"] == candidate.id
        assert delivery_report["release_id"]
        assert delivery_report["immutable"] is True
        ready_candidate = store.get_candidate(candidate.id)
        assert ready_candidate.status == "ready"
        assert ready_candidate.release_id == delivery_report["release_id"]
        assert ready_candidate.release_report_path

        first_release = delivery_report["release_id"]
        first_archive = workspace / "releases" / first_release
        first_delivery_bytes = (first_archive / "DELIVERY_REPORT.json").read_bytes()
        first_audit_bytes = (first_archive / "AUDIT_REPORT.json").read_bytes()
        assert first_delivery_bytes == (workspace / "DELIVERY_REPORT.json").read_bytes()

        # 9) a later release must not rewrite the old release bytes.
        (workspace / "result.txt").write_text("result-v2", encoding="utf-8")
        second_workflow = _add_second_ready_workflow(
            store, workspace, (workspace / "result.txt").read_bytes())
        second_path = write_final_audit_report(
            workspace, project, workflow_db=db, workflow_id=second_workflow)
        second_report = json.loads(second_path.read_text(encoding="utf-8"))
        assert second_report["delivery_decision"] == "ready"
        assert second_report["release_id"] != first_release
        assert (first_archive / "DELIVERY_REPORT.json").read_bytes() == first_delivery_bytes
        assert (first_archive / "AUDIT_REPORT.json").read_bytes() == first_audit_bytes
        assert (workspace / "releases" / second_report["release_id"] /
                "DELIVERY_REPORT.json").is_file()
    finally:
        store.close()
        shutil.rmtree(workspace, ignore_errors=True)


def _orphan_candidate_setup(tmp_path: Path):
    project, skills, _rules = _make_project(tmp_path)
    workspace = tmp_path / "orphan-workspace"
    workspace.mkdir(parents=True)
    (workspace / "result.txt").write_text("orphan fixture", encoding="utf-8")
    _write_approvers(workspace)
    db = tmp_path / "orphan.sqlite"
    store = WorkflowStore(db)
    source = store.create_workflow("explore_demo", {
        "workspace": str(workspace),
        "execution_contract": {"tier": "explore", "version": 1},
    })
    source_step = store.add_steps(source.id, [{"name": "solve"}])[0]
    acceptance = {
        "params": {},
        "skills_root": "academic-toolkit/skills",
        "rules_root": "academic-toolkit/engine/modex-core",
        "rule_files": {},
        "delivery_steps": [
            {"skill_name": "comp-review", "output_files": ["COMP_REVIEW_VERDICT.json"],
             "has_checkpoint": False},
            {"skill_name": "comp-final-audit", "output_files": ["AUDIT_REPORT.json"],
             "has_checkpoint": True, "checkpoint_type": "approve"},
        ],
        "required_reviews": [{"skill_name": "comp-review", "role": "review"}],
        "reproduction_targets": [],
        "approval_policy": {"approvers": ["operator"], "require_human": True,
                            "config_sha256": _sha(
                                (workspace / ".engine" / "approvers.json").read_bytes())},
    }
    candidate = store.create_candidate(
        source_workflow_id=source.id, source_step_id=source_step.id,
        source_attempt_id="attempt-orphan",
        roots=[{"path": "result.txt",
                "sha256": _sha((workspace / "result.txt").read_bytes())}],
        inputs={},
        frozen_versions={"result.txt": _sha((workspace / "result.txt").read_bytes())},
        lineage={"producer_operations": {}, "external_inputs": {}, "unknown_inputs": []},
        recipe={},
        acceptance=acceptance, acceptance_sha256=_canonical_sha(acceptance),
        created_by="tester",
    )
    delivery = store.create_workflow("delivery_demo", {
        "workspace": str(workspace),
        "execution_contract": {"tier": "delivery", "version": 1},
        "delivery_candidate": {"candidate_id": candidate.id,
                               "source_workflow_id": source.id},
        "approval_policy": dict(acceptance["approval_policy"]),
    }, candidate_id=candidate.id)
    step = store.add_steps(delivery.id, [{
        "name": "comp-final-audit",
        "metadata": {"output_files": ["AUDIT_REPORT.json"], "has_checkpoint": True,
                     "checkpoint_type": "approve", "required_checks": []},
    }])[0]
    running = store.transition_step(step.id, "running")
    audit_path = workspace / "AUDIT_REPORT.json"
    audit_path.write_text('{"delivery_decision": "eligible"}', encoding="utf-8")
    manifest = {"artifacts": [{"path": "AUDIT_REPORT.json",
                               "sha256": _sha(audit_path.read_bytes())}]}
    _, checkpoint = store.transition_step_with_checkpoint(
        delivery.id, step.id, "blocked",
        {"status": "waiting_checkpoint", "validation": {"ok": True}, "manifest": manifest},
        event={"type": "step_completed", "manifest": manifest},
        expected_revision=running.revision,
    )
    return store, workspace, project, db, candidate, step, checkpoint


def test_orphan_candidate_approved_is_rejected(tmp_path):
    store, workspace, project, db, candidate, step, checkpoint = _orphan_candidate_setup(tmp_path)
    try:
        # Direct SQL is the documented malicious-local-process residual: the gate
        # must detect the orphan candidate event, not pretend it is an approval.
        store._connection.execute(
            "INSERT INTO candidate_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("orphan-event", candidate.id, checkpoint.id, step.id, "candidate_approved",
             json.dumps({"approved_by": "operator", "l1_available": True}),
             "2026-10-24T00:00:00+00:00"),
        )
        store._connection.commit()
        assert not store._connection.execute(
            "SELECT 1 FROM events WHERE workflow_id=? AND event_type='checkpoint_approved'",
            (store.get_step(step.id).workflow_id,)).fetchone()

        readiness = candidate_readiness(workspace, project, db, candidate.id)
        approval = readiness["gates"]["candidate_approval"]
        assert approval["ok"] is False
        assert "orphan" in approval["reason"]
        assert store.get_step(step.id).status.value == "blocked"
    finally:
        store.close()
