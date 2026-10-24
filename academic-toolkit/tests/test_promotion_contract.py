"""G2 promotion 冻结合同回归：根/输入/谱系/recipe/验收合同与负向闭包。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit_store import build_final_audit_report, candidate_readiness  # noqa: E402
from engine.promotion import PromotionError, freeze_candidate  # noqa: E402
from engine.workflow_runner import WorkflowRunner  # noqa: E402
from engine.workflow_store import WorkflowStore  # noqa: E402
from execution.session import ExecutionSession  # noqa: E402


REVIEW_INPUTS = (
    "paper/main.tex", "paper/main.pdf", "RESULTS.md", "figures/all_results.json",
    "CONSISTENCY_REPORT.json", "LITERATURE.md", "PAPER_SCORING.json",
    "COMP_REVIEW_VERDICT.json", "VISUAL_REVIEW_VERDICT.json", "EDITOR_CHANGELOG.md",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _skills(tmp_path: Path, *names: str) -> Path:
    skills = tmp_path / "skills"
    for name in names:
        folder = skills / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(f"fixture skill {name}", encoding="utf-8")
    return skills


def _rules(tmp_path: Path) -> Path:
    rules = tmp_path / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / "comp_rules.json").write_text('{"contest": "fixture"}', encoding="utf-8")
    (rules / "quality_gates.json").write_text('{"gates": []}', encoding="utf-8")
    return rules


def _source_catalog(outputs, *, skill_name="solve"):
    return {"explore_demo": {"sub_steps": [{
        "skill_name": skill_name, "display_name": "Solve", "output_files": list(outputs),
        "primary_output": list(outputs)[0] if outputs else "", "has_checkpoint": False,
        "checkpoint_type": None, "required_checks": [], "output_specs": {},
    }]}}


def _delivery_catalog():
    return {"delivery_demo": {"sub_steps": [
        {"skill_name": "comp-review", "display_name": "Review",
         "output_files": ["COMP_REVIEW.md", "COMP_REVIEW_VERDICT.json"],
         "primary_output": "COMP_REVIEW_VERDICT.json", "has_checkpoint": False,
         "checkpoint_type": None, "required_checks": ["review"], "output_specs": {}},
        {"skill_name": "comp-editor", "display_name": "Editor",
         "output_files": ["EDITOR_CHANGELOG.md"], "primary_output": "EDITOR_CHANGELOG.md",
         "has_checkpoint": False, "checkpoint_type": None, "required_checks": None,
         "output_specs": {}},
        {"skill_name": "comp-visual-review", "display_name": "Visual review",
         "output_files": ["VISUAL_REVIEW.md", "VISUAL_REVIEW_VERDICT.json"],
         "primary_output": "VISUAL_REVIEW_VERDICT.json", "has_checkpoint": False,
         "checkpoint_type": None, "required_checks": ["review"], "output_specs": {}},
        {"skill_name": "comp-final-review", "display_name": "Final review",
         "output_files": ["FINAL_REVIEW.md", "FINAL_REVIEW_VERDICT.json"],
         "primary_output": "FINAL_REVIEW_VERDICT.json", "has_checkpoint": False,
         "checkpoint_type": None, "required_checks": ["review"], "output_specs": {}},
        {"skill_name": "comp-final-audit", "display_name": "Final audit",
         "output_files": ["AUDIT_REPORT.json"], "primary_output": "AUDIT_REPORT.json",
         "has_checkpoint": True, "checkpoint_type": "approve",
         "required_checks": ["final_audit"], "output_specs": {}},
    ]}}


def _runner(tmp_path: Path, catalog, *skill_names: str):
    skills = _skills(tmp_path, *skill_names)
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
    return store, runner, skills


def _write_approvers(workspace: Path) -> dict:
    config = workspace / ".engine" / "approvers.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    data = {"approvers": ["operator"], "require_human": True}
    config.write_text(json.dumps(data), encoding="utf-8")
    return data


def _command_spec(session, output="mid.txt", factor=2):
    session.files.write(
        "solve.py",
        "from pathlib import Path\n"
        "p = Path('input.txt')\n"
        f"Path('{output}').write_text(str(int(p.read_text()) * {factor}))\n",
    )
    return {"id": "solve", "argv": [sys.executable, "solve.py"],
            "inputs": ["input.txt", "solve.py"], "outputs": [output],
            "pure": True, "complete_inputs": True}


def _run_explore(tmp_path, runner, workspace: Path, outputs, *, review_files=False):
    workflow = runner.start("explore_demo", workspace, {}, mode="explore")
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.write("input.txt", "7")
    if review_files:
        for name in REVIEW_INPUTS:
            session.files.write(name, f"review fixture {name}")
    spec = _command_spec(session, output=list(outputs)[0])
    assert session.commands.execute(spec)["status"] == "succeeded"
    result = session.finish()
    assert result["status"] == "completed", result
    return workflow, session


def _freeze(store, workflow_id, roots, tmp_path, skills, rules, *, template="delivery_demo"):
    return freeze_candidate(
        store, workflow_id, roots, by="operator", template=template,
        catalog={**_source_catalog(["mid.txt"]), **_delivery_catalog()},
        project_root=tmp_path, skills_root=skills, rules_root=rules,
    )


def test_promotion_freezes_roots_inputs_lineage_recipe_acceptance(tmp_path):
    catalog = {**_source_catalog(["mid.txt", *REVIEW_INPUTS]), **_delivery_catalog()}
    store, runner, skills = _runner(tmp_path, catalog, "solve", "comp-review", "comp-editor",
                                    "comp-visual-review", "comp-final-review", "comp-final-audit")
    workspace = tmp_path / "workspace"
    workflow, _session = _run_explore(tmp_path, runner, workspace, ["mid.txt", *REVIEW_INPUTS],
                                      review_files=True)
    _write_approvers(workspace)
    rules = _rules(tmp_path)

    candidate = _freeze(store, workflow.id, ["mid.txt"], tmp_path, skills, rules)
    root_sha = _sha((workspace / "mid.txt").read_bytes())

    assert candidate.status == "not_ready"
    assert candidate.roots[0]["path"] == "mid.txt"
    assert candidate.roots[0]["sha256"] == root_sha
    assert candidate.roots[0]["producer_operation_id"] == candidate.lineage["producer_operations"]["mid.txt"]
    assert candidate.inputs["input.txt"]["kind"] == "produced"
    assert candidate.inputs["input.txt"]["producer_operation_id"]
    assert candidate.inputs["solve.py"]["kind"] == "produced"
    assert candidate.inputs["paper/main.tex"]["kind"] == "review_input"
    assert candidate.frozen_versions == {
        **{path: meta["sha256"] for path, meta in candidate.inputs.items()},
        "mid.txt": root_sha,
    }
    assert candidate.lineage["producer_operations"]["mid.txt"]
    assert candidate.lineage["unknown_inputs"] == []
    target = candidate.acceptance["reproduction_targets"][0]
    assert target["path"] == "mid.txt" and target["recipe_id"]
    assert candidate.recipe[target["recipe_id"]]["argv"][0]
    assert "python" in Path(candidate.recipe[target["recipe_id"]]["argv"][0]).name.lower()
    assert candidate.acceptance["required_reviews"] == [
        {"skill_name": "comp-review", "role": "review"},
        {"skill_name": "comp-visual-review", "role": "visual"},
        {"skill_name": "comp-final-review", "role": "final"},
    ]
    assert candidate.acceptance["rule_files"]["comp_rules.json"] == _sha(
        (rules / "comp_rules.json").read_bytes())
    assert candidate.acceptance["approval_policy"]["approvers"] == ["operator"]
    assert candidate.acceptance_sha256 == _canonical_sha(candidate.acceptance)
    assert "closure" not in candidate.missing


def test_promotion_requires_completed_explore_and_accepted_roots(tmp_path):
    catalog = _source_catalog(["result.txt"])
    store, runner, skills = _runner(tmp_path, catalog, "solve")
    workspace = tmp_path / "workspace"
    workflow = runner.start("explore_demo", workspace, {}, mode="explore")
    _write_approvers(workspace)
    rules = _rules(tmp_path)
    with pytest.raises(PromotionError, match="COMPLETED"):
        _freeze(store, workflow.id, ["result.txt"], tmp_path, skills, rules,
                template="explore_demo")

    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.write("result.txt", "done")
    assert session.finish()["status"] == "completed"
    (workspace / "unaccepted.txt").write_text("not in any manifest", encoding="utf-8")
    with pytest.raises(PromotionError, match="已接受版本"):
        _freeze(store, workflow.id, ["unaccepted.txt"], tmp_path, skills, rules,
                template="explore_demo")


def test_candidate_not_ready_without_reproduction_review_approval(tmp_path):
    catalog = {**_source_catalog(["result.txt"]), **_delivery_catalog()}
    store, runner, skills = _runner(tmp_path, catalog, "solve", "candidate-reproduction",
                                    "comp-review", "comp-visual-review", "comp-final-review",
                                    "comp-final-audit")
    workspace = tmp_path / "workspace"
    workflow = runner.start("explore_demo", workspace, {}, mode="explore")
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.write("result.txt", "write-only result")
    assert session.finish()["status"] == "completed"
    _write_approvers(workspace)
    rules = _rules(tmp_path)

    candidate = _freeze(store, workflow.id, ["result.txt"], tmp_path, skills, rules)
    assert {"reproduction", "review", "approval"} <= set(candidate.missing)
    assert candidate.acceptance["reproduction_targets"] == []

    delivery = runner.start("delivery_demo", workspace, {}, candidate_id=candidate.id)
    readiness = candidate_readiness(workspace, tmp_path, tmp_path / "workflow.sqlite", candidate.id)
    assert readiness["candidate_status"] == "in_delivery"
    for gate in ("candidate_reproduction", "candidate_review", "candidate_approval"):
        assert readiness["gates"][gate]["ok"] is False

    report = build_final_audit_report(workspace, tmp_path, tmp_path / "workflow.sqlite",
                                      workflow_id=delivery.id)
    assert report["delivery_decision"] == "blocked"
    assert report["gate_outcomes"]["candidate_reproduction"] == "fail"


def test_candidate_delivery_does_not_reuse_explore_cache(tmp_path):
    catalog = {**_source_catalog(["result.txt"]), **_delivery_catalog()}
    store, runner, skills = _runner(tmp_path, catalog, "solve", "candidate-reproduction",
                                    "comp-review", "comp-visual-review", "comp-final-review",
                                    "comp-final-audit")
    workspace = tmp_path / "workspace"
    workflow, session = _run_explore(tmp_path, runner, workspace, ["result.txt"])
    source_contract = session.operations.execution_relevant_contract()
    _write_approvers(workspace)
    candidate = _freeze(store, workflow.id, ["result.txt"], tmp_path, skills, _rules(tmp_path))

    delivery = store.create_workflow(
        "cache_probe",
        {"workspace": str(workspace), "params": {},
         "execution_contract": {"tier": "delivery", "version": 1},
         "delivery_candidate": {"candidate_id": candidate.id,
                                "source_workflow_id": candidate.source_workflow_id}},
        candidate_id=candidate.id,
    )
    store.add_steps(delivery.id, [{"name": "solve", "metadata": {}}])
    delivery_session = ExecutionSession(runner, delivery.id)
    assert delivery_session.operations.execution_relevant_contract() != source_contract


def test_external_leaf_is_valid_candidate_input(tmp_path):
    catalog = _source_catalog(["result.txt"])
    store, runner, skills = _runner(tmp_path, catalog, "solve")
    workspace = tmp_path / "workspace"
    workflow = runner.start("explore_demo", workspace, {}, mode="explore")
    (workspace / "raw.csv").write_text("1,2,3\n", encoding="utf-8")
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.read_file("raw.csv")
    session.files.write("result.txt", "result from raw", inputs=["raw.csv"])
    assert session.finish()["status"] == "completed"
    _write_approvers(workspace)

    candidate = _freeze(store, workflow.id, ["result.txt"], tmp_path, skills, _rules(tmp_path),
                        template="explore_demo")
    assert candidate.inputs["raw.csv"]["kind"] == "external"
    assert candidate.inputs["raw.csv"]["producer_operation_id"] is None
    assert "raw.csv" in candidate.lineage["external_inputs"]
    assert "closure" not in candidate.missing


def test_legacy_write_inputs_snapshot_counts_as_closure(tmp_path):
    catalog = _source_catalog(["result.txt"])
    store, runner, skills = _runner(tmp_path, catalog, "solve")
    workspace = tmp_path / "workspace"
    workflow = runner.start("explore_demo", workspace, {}, mode="explore")
    (workspace / "raw.csv").write_text("1,2,3\n", encoding="utf-8")
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.read_file("raw.csv")
    session.files.write("result.txt", "legacy result", inputs=["raw.csv"])
    assert session.finish()["status"] == "completed"
    _write_approvers(workspace)

    rows = store._connection.execute(
        "SELECT id, payload FROM execution_operations WHERE workflow_id=? AND kind='write'",
        (workflow.id,)).fetchall()
    changed = False
    for row in rows:
        payload = json.loads(row["payload"])
        if payload.get("path") != "result.txt":
            continue
        payload.pop("declared_inputs", None)
        payload.pop("dependency_policy", None)
        store._connection.execute("UPDATE execution_operations SET payload=? WHERE id=?",
                                  (json.dumps(payload, ensure_ascii=True, sort_keys=True), row["id"]))
        changed = True
    assert changed
    store._connection.commit()

    candidate = _freeze(store, workflow.id, ["result.txt"], tmp_path, skills, _rules(tmp_path),
                        template="explore_demo")
    assert "closure" not in candidate.missing
    assert candidate.lineage["unknown_inputs"] == []


def test_zero_input_script_write_is_not_unknown(tmp_path):
    catalog = _source_catalog(["solve.py"])
    store, runner, skills = _runner(tmp_path, catalog, "solve")
    workspace = tmp_path / "workspace"
    workflow = runner.start("explore_demo", workspace, {}, mode="explore")
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.write("solve.py", "print('from zero')\n", inputs=[])
    assert session.finish()["status"] == "completed"
    _write_approvers(workspace)

    candidate = _freeze(store, workflow.id, ["solve.py"], tmp_path, skills, _rules(tmp_path),
                        template="explore_demo")
    assert "closure" not in candidate.missing
    assert candidate.lineage["unknown_inputs"] == []


def test_promotion_requires_human_approvers_config(tmp_path):
    catalog = _source_catalog(["result.txt"])
    store, runner, skills = _runner(tmp_path, catalog, "solve")
    workspace = tmp_path / "workspace"
    workflow = runner.start("explore_demo", workspace, {}, mode="explore")
    session = ExecutionSession(runner, workflow.id)
    session.context()
    session.files.write("result.txt", "result")
    assert session.finish()["status"] == "completed"
    rules = _rules(tmp_path)

    with pytest.raises(PromotionError, match="approvers.json"):
        _freeze(store, workflow.id, ["result.txt"], tmp_path, skills, rules,
                template="explore_demo")

    config = workspace / ".engine" / "approvers.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"approvers": [], "require_human": true}', encoding="utf-8")
    with pytest.raises(PromotionError, match="不能为空"):
        _freeze(store, workflow.id, ["result.txt"], tmp_path, skills, rules,
                template="explore_demo")

    config.write_text('{"approvers": ["operator"], "require_human": false}', encoding="utf-8")
    with pytest.raises(PromotionError, match="require_human"):
        _freeze(store, workflow.id, ["result.txt"], tmp_path, skills, rules,
                template="explore_demo")


def test_real_comp_cumcm_promotion_required_reviews(tmp_path):
    """真实模板：review 集合只取三个评审技能，不含 comp-editor。"""
    catalog_path = ROOT / "engine" / "modex-core" / "templates.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    workspace = tmp_path / "workspace"
    (workspace / "paper").mkdir(parents=True)
    (workspace / ".engine").mkdir(parents=True)
    (workspace / "paper" / "main.pdf").write_bytes(b"real template root")
    (workspace / ".engine" / "approvers.json").write_text(
        '{"approvers": ["operator"], "require_human": true}', encoding="utf-8")
    root_sha = _sha((workspace / "paper" / "main.pdf").read_bytes())

    store = WorkflowStore(tmp_path / "workflow.sqlite")
    workflow = store.create_workflow("comp_cumcm", {
        "workspace": str(workspace), "params": {}, "template": "comp_cumcm",
        "execution_contract": {"tier": "explore", "version": 1}})
    step = store.add_steps(workflow.id, [{"name": "comp-code", "metadata": {}}])[0]
    running = store.transition_step(step.id, "running")
    payload = {"path": "paper/main.pdf", "operation": "write", "declared_inputs": [],
               "dependency_policy": "explicit-declared-inputs-v1", "inputs_snapshot": {},
               "outputs_snapshot": {"paper/main.pdf": root_sha}, "previous_sha256": None}
    timestamp = "2026-10-24T00:00:00+00:00"
    store._connection.execute(
        "INSERT INTO execution_operations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("op-root", workflow.id, step.id, running.attempt_id, "write", "succeeded",
         "write:paper/main.pdf", "", json.dumps(payload, ensure_ascii=True, sort_keys=True),
         timestamp, timestamp))
    store._connection.commit()
    store.transition_step_with_checkpoint(
        workflow.id, step.id, "completed", {"status": "completed"},
        artifacts=[{"name": "main.pdf", "path": "paper/main.pdf",
                    "metadata": {"sha256": root_sha}}],
        event={"type": "step_completed",
               "manifest": {"artifacts": [{"path": "paper/main.pdf", "sha256": root_sha}]}},
        expected_revision=running.revision, finalize_if_complete=True)

    candidate = freeze_candidate(
        store, workflow.id, ["paper/main.pdf"], by="operator", template="comp_cumcm",
        catalog=catalog, project_root=ROOT.parent, skills_root=ROOT / "skills",
        rules_root=ROOT / "engine" / "modex-core",
    )
    names = [item["skill_name"] for item in candidate.acceptance["required_reviews"]]
    assert names == ["comp-review", "comp-visual-review", "comp-final-review"]
    assert "comp-editor" not in names
    assert candidate.acceptance["skills_root"] == "academic-toolkit/skills"
    assert candidate.acceptance["rules_root"] == "academic-toolkit/engine/modex-core"
    assert candidate.acceptance["rule_files"]["comp_rules.json"] == _sha(
        (ROOT / "engine" / "modex-core" / "comp_rules.json").read_bytes())
    assert candidate.frozen_versions == {"paper/main.pdf": root_sha}
    assert candidate.roots[0]["producer_operation_id"] == "op-root"
