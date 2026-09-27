"""审计系统测试：AuditStore 读写、报告生成、未申报操作检测（防绕过）。"""
import json
import sys
import pytest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit_store import (
    AuditStore,
    audit_log_path,
    default_audit_dir,
    detect_unreported_operations,
    build_final_audit_report,
    generate_audit_report,
    official_logger_paths,
    write_final_audit_report,
    write_audit_report,
)


def _make_audit(project_root: Path) -> AuditStore:
    store = AuditStore(project_root)
    store.record({"type": "tool_call", "event": "before", "tool": "bash", "sessionID": "s1",
                  "detail": {"command": "python code/main.py"}})
    store.record({"type": "tool_result", "event": "after", "tool": "bash", "sessionID": "s1",
                  "ok": True, "resultSummary": "exit 0"})
    store.record({"type": "tool_call", "event": "before", "tool": "edit", "sessionID": "s1",
                  "detail": {"filePath": "RESULTS.md", "oldLen": 10, "newLen": 20}})
    store.record({"type": "tool_call", "event": "before", "tool": "skill", "sessionID": "s1",
                  "detail": {"skillName": "comp-modeling"}})
    store.record({"type": "file_edit", "event": "file.edited", "detail": "{}"})
    store.record({"type": "session", "event": "session.created", "sessionID": "s1"})
    return store


def test_audit_store_records_and_reads(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    store = _make_audit(project_root)

    events = store.events()
    assert len(events) == 6
    assert store.tool_calls() and len(store.tool_calls()) == 3
    assert store.tool_results() and len(store.tool_results()) == 1
    assert len(store.file_edits()) == 1
    assert len(store.sessions()) == 1
    assert audit_log_path(project_root).exists()


def test_audit_store_stats(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    store = _make_audit(project_root)

    stats = store.stats()
    assert stats["total_events"] == 6
    assert stats["tool_calls"] == 3
    assert stats["bash_commands"] == ["python code/main.py"]
    assert stats["edit_targets"] == ["RESULTS.md"]
    assert stats["skill_usage"] == {"comp-modeling": 1}
    assert stats["failed_tool_calls"] == 0
    assert stats["first_event"] is not None


def test_audit_store_handles_corrupt_lines(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    path = audit_log_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"ts": "2026-01-01", "type": "ok"}\nNOT_JSON\n', encoding="utf-8")

    store = AuditStore(project_root)
    events = store.events()
    assert len(events) == 2
    assert events[1]["type"] == "corrupt_line"


def test_detect_unreported_bash_commands(tmp_path):
    """防绕过：审计日志有但 evidence 未申报的命令 → warning。"""
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()

    # 审计日志记录了一个命令
    store = AuditStore(project_root)
    store.record({"type": "tool_call", "tool": "bash", "detail": {"command": "python hack.py"}})
    # evidence 里申报了另一个命令
    ev_dir = workspace / ".engine" / "evidence"
    ev_dir.mkdir(parents=True)
    (ev_dir / "step1.json").write_text(json.dumps({
        "evidence": {"commands": [{"command": "python legit.py"}], "outputs": ["out.md"], "inputs": []},
    }), encoding="utf-8")

    result = detect_unreported_operations(workspace, project_root)
    assert result["verdict"] == "warning"
    assert "python hack.py" in result["unreported_bash"]


@pytest.mark.parametrize("variant,classified", [
    ("plain", True), ("compound", False), ("redirect", False),
    ("wrong-workflow", False), ("wrong-db", False), ("wrong-output", False),
    ("duplicate-option", False), ("truncated", False), ("wrapper", False),
])
def test_control_call_classification_is_narrow_and_visible(tmp_path, variant, classified):
    ws = tmp_path / "workspace"
    ws.mkdir()
    db = tmp_path / "workflow.sqlite"
    command = f'python -m engine.workflow_cli final-audit --workspace "{ws}" --db "{db}" --wf wf-1'
    suffixes = {"compound": " && python mutate.py", "redirect": " > paper.txt",
                "wrong-output": f' --out "{ws / "paper.txt"}"',
                "duplicate-option": " --wf wf-1", "truncated": "...[TRUNC]"}
    command += suffixes.get(variant, "")
    if variant == "wrong-workflow":
        command = command.replace("wf-1", "wf-other")
    elif variant == "wrong-db":
        command = command.replace(str(db), str(tmp_path / "other.sqlite"))
    elif variant == "wrapper":
        command = "echo " + command
    AuditStore(tmp_path).record({"type": "tool_call", "tool": "bash", "detail": {"command": command}})
    result = detect_unreported_operations(ws, tmp_path, evidence_paths=set(),
        control_scope={"database": db, "workflow_id": "wf-1", "checkpoint_ids": set()})
    assert bool(result["workflow_control_calls"]) is classified
    assert result["actual_bash_count"] == 1
    assert (result["verdict"] == "ok") is classified
    if classified:
        assert result["workflow_control_calls"][0]["execution_status"] == "not_attested"
        # A declared long prefix cannot hide a compound tail outside classification.
        compound = command + " && python mutate.py"
        AuditStore(tmp_path).record({"type": "tool_call", "tool": "bash", "detail": {"command": compound}})
        again = detect_unreported_operations(ws, tmp_path, evidence_paths=set(),
            candidate_evidence={"commands": [{"command": command}], "outputs": [], "inputs": []},
            control_scope={"database": db, "workflow_id": "wf-1", "checkpoint_ids": set()})
        assert compound in again["unreported_bash"]
    else:
        assert result["unreported_bash"] == [command]


def test_detect_unreported_edits(tmp_path):
    """防绕过：编辑了未申报的文件 → warning。"""
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()

    store = AuditStore(project_root)
    store.record({"type": "tool_call", "tool": "edit", "detail": {"filePath": "SECRET.md"}})
    ev_dir = workspace / ".engine" / "evidence"
    ev_dir.mkdir(parents=True)
    (ev_dir / "step1.json").write_text(json.dumps({
        "evidence": {"commands": [], "outputs": ["out.md"], "inputs": []},
    }), encoding="utf-8")

    result = detect_unreported_operations(workspace, project_root)
    assert result["verdict"] == "warning"
    assert "SECRET.md" in result["unreported_edit_targets"]


def test_detect_reports_ok_when_all_declared(tmp_path):
    """全部操作都申报 → ok。"""
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()

    store = AuditStore(project_root)
    store.record({"type": "tool_call", "tool": "bash", "detail": {"command": "python code/main.py"}})
    ev_dir = workspace / ".engine" / "evidence"
    ev_dir.mkdir(parents=True)
    (ev_dir / "step1.json").write_text(json.dumps({
        "evidence": {"commands": [{"command": "python code/main.py"}], "outputs": ["out.md"], "inputs": []},
    }), encoding="utf-8")

    result = detect_unreported_operations(workspace, project_root)
    assert result["verdict"] == "ok"


def test_generate_and_write_audit_report(tmp_path):
    """报告生成：包含 stats/workflow/evidence/未申报检测。"""
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()
    _make_audit(project_root)
    ev_dir = workspace / ".engine" / "evidence"
    ev_dir.mkdir(parents=True)
    (ev_dir / "step1.json").write_text(json.dumps({
        "evidence": {"skill_name": "comp-code", "agent": "test", "commands": [{"command": "python code/main.py"}],
                     "outputs": [], "inputs": []},
    }), encoding="utf-8")

    report = generate_audit_report(workspace, project_root)
    assert report["stats"]["total_events"] >= 6
    assert len(report["evidence_files"]) == 1
    assert report["overall"]["audit_trail_present"] is True
    assert "unreported_operations" in report

    out = write_audit_report(workspace, project_root)
    assert out.exists()
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["stats"]["total_events"] >= 6


def test_build_and_write_final_audit_report(tmp_path):
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()

    paper = workspace / "paper"
    paper.mkdir()
    pdf = paper / "main.pdf"
    pdf.write_bytes(b"fake pdf bytes")

    evidence_dir = workspace / ".engine" / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "step.json").write_text(json.dumps({
        "evidence": {"skill_name": "comp-final-audit", "agent": "test", "commands": [{"command": "python tools/reviewer_client.py --prompt 审查", "returncode": 0, "cwd": "."}], "outputs": ["AUDIT_REPORT.json"], "inputs": []},
    }), encoding="utf-8")

    db = tmp_path / "workflow.sqlite"
    from engine.workflow_store import WorkflowStore

    with WorkflowStore(db) as store:
        # 非赛事合成工作流（contest_compliance=not_applicable 计 pass）；
        # 赛事待绑定/未核验 → blocked 的语义由 test_contest_profile_runtime 覆盖
        workflow = store.create_workflow("demo_tpl", {"workspace": str(workspace), "params": {}})
        step = store.add_steps(workflow.id, [{
            "name": "comp-final-audit",
            "metadata": {
                "display_name": "最终交付审计",
                "required_checks": ["final_audit"],
                "output_files": ["AUDIT_REPORT.json"],
                "primary_output": "AUDIT_REPORT.json",
                "has_checkpoint": True,
                "checkpoint_type": "approve",
            },
        }])[0]
        store.transition_step(step.id, "running")
        store.transition_step_with_checkpoint(
            workflow.id,
            step.id,
            "completed",
            {"status": "completed", "manifest": {"artifacts": [{"path": "paper/main.pdf", "sha256": __import__("hashlib").sha256(b"fake pdf bytes").hexdigest()}]}, "quality_gates": {"checks": {"literature": {"ok": True}, "review": {"ok": True}, "consistency": {"ok": True}, "final_audit": {"ok": True}}}},
            event={"type": "step_completed", "quality_gates": {"checks": {"literature": {"ok": True}, "review": {"ok": True}, "consistency": {"ok": True}, "final_audit": {"ok": True}}}, "manifest": {"artifacts": [{"path": "paper/main.pdf", "sha256": __import__("hashlib").sha256(b"fake pdf bytes").hexdigest()}]}}
        )

    report = build_final_audit_report(workspace, project_root, workflow_db=db)
    assert report["artifacts"]
    assert report["delivery_decision"] == "ready"
    assert report["gate_outcomes"]["final_audit"] == "pass"

    out = write_final_audit_report(workspace, project_root, workflow_db=db)
    assert out.exists()
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["workflow_id"] == report["workflow_id"]


def test_pending_workflow_with_fallback_paper_is_not_ready(tmp_path):
    from engine.workflow_store import WorkflowStore
    workspace = tmp_path / "ws"
    (workspace / "paper").mkdir(parents=True)
    (workspace / "paper/main.pdf").write_bytes(b"paper")
    db = tmp_path / "workflow.sqlite"
    with WorkflowStore(db) as store:
        wf = store.create_workflow("demo", {"workspace": str(workspace)})
        store.add_steps(wf.id, [{"name": "unfinished"}])
    report = build_final_audit_report(workspace, tmp_path, db)
    assert report["delivery_decision"] == "blocked"
    assert report["gate_outcomes"]["workflow_steps"] == "fail"


def test_latest_failure_is_not_masked_by_previous_pass(tmp_path):
    from engine.workflow_store import WorkflowStore
    import hashlib
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "paper.txt").write_bytes(b"paper")
    manifest = {"artifacts": [{"path": "paper.txt", "sha256": hashlib.sha256(b"paper").hexdigest()}]}
    db = tmp_path / "workflow.sqlite"
    with WorkflowStore(db) as store:
        wf = store.create_workflow("demo", {"workspace": str(workspace)})
        step = store.add_steps(wf.id, [{"name": "solve"}])[0]
        store.transition_step(step.id, "running")
        store.create_checkpoint(wf.id, step.id, {}, event={"type": "step_completed", "manifest": manifest,
            "quality_gates": {"checks": {"math": {"ok": True}}}})
        store.transition_step_with_checkpoint(wf.id, step.id, "failed", {"status": "failed"},
            event={"type": "step_failed", "quality_gates": {"checks": {"math": {"ok": False}}}})
    report = build_final_audit_report(workspace, tmp_path, db)
    assert report["delivery_decision"] == "blocked"
    assert report["gate_outcomes"]["math"] == "fail"


def test_final_report_revalidates_actual_content(tmp_path):
    import hashlib
    from engine.quality_gates import QualityGate
    path = tmp_path / "paper.txt"
    path.write_bytes(b"original")
    report = {"workflow_id": "wf", "artifacts": [{"path": "paper.txt",
        "sha256": hashlib.sha256(b"original").hexdigest()}], "gate_outcomes": {"math": "pass"},
        "waivers": [], "delivery_decision": "ready"}
    (tmp_path / "AUDIT_REPORT.json").write_text(json.dumps(report), encoding="utf-8")
    assert QualityGate(tmp_path).check_final_audit_report()["ok"]
    path.write_bytes(b"modified")
    assert not QualityGate(tmp_path).check_final_audit_report()["ok"]


def test_delivery_keeps_pdf_and_package_when_last_step_only_writes_review(tmp_path):
    import hashlib
    from engine.workflow_store import WorkflowStore
    ws = tmp_path / "ws"
    (ws / "paper").mkdir(parents=True)
    files = {"paper/main.pdf": b"accepted pdf", "submission.zip": b"accepted package", "FINAL_REVIEW.md": b"review"}
    db = tmp_path / "workflow.sqlite"
    with WorkflowStore(db) as store:
        wf = store.create_workflow("demo", {"workspace": str(ws)})
        steps = store.add_steps(wf.id, [{"name": name} for name in ("compile", "package", "review")])
        for step, (rel, content) in zip(steps, files.items()):
            (ws / rel).write_bytes(content)
            store.transition_step(step.id, "running")
            manifest = {"artifacts": [{"path": rel, "sha256": hashlib.sha256(content).hexdigest()}]}
            store.transition_step_with_checkpoint(wf.id, step.id, "completed", {"manifest": manifest},
                event={"type": "step_completed", "manifest": manifest, "quality_gates": {"checks": {"fixture": {"ok": True}}}})
        store.complete_workflow(wf.id)
    report = build_final_audit_report(ws, tmp_path, db)
    assert report["delivery_decision"] == "ready", report
    assert {a["path"] for a in report["artifacts"]} == set(files)
    pdf = ws / "paper/main.pdf"
    pdf.write_bytes(b"changed pdf")
    assert build_final_audit_report(ws, tmp_path, db)["delivery_decision"] == "blocked"
    pdf.write_bytes(files["paper/main.pdf"])
    package = ws / "submission.zip"
    package.rename(ws / "missing-package.fixture")
    assert build_final_audit_report(ws, tmp_path, db)["delivery_decision"] == "blocked"


def test_orphan_evidence_cannot_manufacture_delivery_or_declared_operations(tmp_path):
    import hashlib
    from engine.workflow_store import WorkflowStore
    from engine.audit_store import _evidence_files
    ws = tmp_path / "ws"
    (ws / ".engine/evidence").mkdir(parents=True)
    (ws / "paper.pdf").write_bytes(b"unaccepted")
    db = ws / ".engine/workflow.sqlite"
    with WorkflowStore(db) as store:
        wf = store.create_workflow("demo", {"workspace": str(ws)})
        step = store.add_steps(wf.id, [{"name": "solve"}])[0]
        store.transition_step(step.id, "running")
        store.transition_step_with_checkpoint(wf.id, step.id, "completed", {},
            event={"type": "step_completed", "quality_gates": {"checks": {"fixture": {"ok": True}}}})
        store.complete_workflow(wf.id)
    (ws / ".engine/evidence/orphan.json").write_text(json.dumps({
        "evidence": {"commands": [{"command": "python uncommitted.py"}]},
        "manifest": {"artifacts": [{"path": "paper.pdf", "sha256": hashlib.sha256(b"unaccepted").hexdigest()}]}}), encoding="utf-8")
    assert _evidence_files(ws) == []
    assert detect_unreported_operations(ws, tmp_path)["declared_command_count"] == 0
    report = build_final_audit_report(ws, tmp_path, db)
    assert report["delivery_decision"] == "blocked" and report["artifacts"] == []


@pytest.mark.parametrize("direction", ["parent-child", "child-parent", "parent-subdir", "legacy"])
def test_hierarchical_accepted_outputs_keep_siblings_and_closed_membership(tmp_path, direction):
    from engine.workflow_runner import _manifest_payload
    from engine.artifact_manifest import ArtifactManifest
    from engine.workflow_store import WorkflowStore
    from engine.quality_gates import QualityGate
    ws = tmp_path / "ws"
    figures = ws / "figures"
    (figures / "sub").mkdir(parents=True)
    child = figures / "sub/plot.txt"
    sibling = figures / "sibling.txt"
    child.write_bytes(b"old")
    sibling.write_bytes(b"untouched")
    db = tmp_path / "workflow.sqlite"
    with WorkflowStore(db) as store:
        wf = store.create_workflow("hierarchy", {"workspace": str(ws)})
        steps = store.add_steps(wf.id, [{"name": "first"}, {"name": "second"}])
        def accept(step, outputs, legacy=False):
            manifest = _manifest_payload(ArtifactManifest.validate(ws, outputs))
            if legacy:
                for a in manifest["artifacts"]:
                    a.pop("members", None)
            store.transition_step(step.id, "running")
            store.transition_step_with_checkpoint(wf.id, step.id, "completed", {"manifest": manifest},
                event={"type": "step_completed", "manifest": manifest,
                       "quality_gates": {"checks": {"fixture": {"ok": True}}}})
        accept(steps[0], ["figures/sub/plot.txt"] if direction == "child-parent" else ["figures/"],
               legacy=direction == "legacy")
        child.write_bytes(b"new")
        if direction == "child-parent":
            sibling.write_bytes(b"fully revalidated")
        accept(steps[1], ["figures/"] if direction == "child-parent" else
               ["figures/sub/"] if direction == "parent-subdir" else ["figures/sub/plot.txt"])
        store.complete_workflow(wf.id)
        # Deliberately force equal event timestamps: insertion order is authoritative.
        store._connection.execute("UPDATE events SET created_at = '2026-09-26T00:00:00+00:00'")
        store._connection.commit()
    report = build_final_audit_report(ws, tmp_path, db)
    if direction == "legacy":
        assert report["delivery_decision"] == "blocked"
        assert report["gate_outcomes"]["artifact_integrity"] == "fail"
        return
    assert report["delivery_decision"] == "ready", report
    assert {a["path"] for a in report["artifacts"]} == {"figures/sub/plot.txt", "figures/sibling.txt"}
    (ws / "DELIVERY_REPORT.json").write_text(json.dumps(report), encoding="utf-8")
    assert QualityGate(ws).check_final_audit_report()["ok"]
    accepted_sibling = sibling.read_bytes()
    sibling.write_bytes(b"unaccepted change")
    assert build_final_audit_report(ws, tmp_path, db)["delivery_decision"] == "blocked"
    sibling.write_bytes(accepted_sibling)
    sibling.rename(ws / "removed.fixture")
    assert build_final_audit_report(ws, tmp_path, db)["delivery_decision"] == "blocked"
    (ws / "removed.fixture").rename(sibling)
    (figures / "rogue.txt").write_bytes(b"not accepted")
    assert build_final_audit_report(ws, tmp_path, db)["delivery_decision"] == "blocked"
    assert not QualityGate(ws).check_final_audit_report()["ok"]


def test_accepted_new_child_extends_directory_without_accepting_other_files(tmp_path):
    from engine.audit_store import _accepted_coverage
    from engine.artifact_manifest import ArtifactManifest
    from engine.workflow_runner import _manifest_payload
    directory = tmp_path / "figures"
    directory.mkdir()
    (directory / "old.txt").write_bytes(b"old")
    old = _manifest_payload(ArtifactManifest.validate(tmp_path, ["figures/"]))["artifacts"]
    (directory / "new.txt").write_bytes(b"new")
    new = _manifest_payload(ArtifactManifest.validate(tmp_path, ["./figures/new.txt"]))["artifacts"]
    leaves, coverage, errors = _accepted_coverage(tmp_path, [old, new])
    assert not errors
    assert ArtifactManifest.validate_coverage(tmp_path, list(leaves.values()), coverage)["ok"]
    (directory / "unknown.txt").write_bytes(b"unknown")
    assert not ArtifactManifest.validate_coverage(tmp_path, list(leaves.values()), coverage)["ok"]


def test_official_logger_paths_and_events(tmp_path):
    """官方 opencode-logger 输出（log.jsonl + 轮转）可被审计报告读取。"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    audit_dir = default_audit_dir(project_root)
    audit_dir.mkdir(parents=True)
    # 模拟官方 logger 输出（eventType 格式）
    (audit_dir / "log.jsonl").write_text(
        json.dumps({"timestamp": "2026-01-01T00:00:00Z", "eventType": "tool.execute.before",
                    "payload": {"tool": "bash"}}) + "\n" +
        json.dumps({"timestamp": "2026-01-01T00:00:01Z", "eventType": "file.edited",
                    "payload": {"path": "a.md"}}) + "\n",
        encoding="utf-8",
    )

    paths = official_logger_paths(project_root)
    assert len(paths) == 1
    store = AuditStore(project_root)
    events = store.official_events()
    assert len(events) == 2
    assert events[0]["eventType"] == "tool.execute.before"

    report = generate_audit_report(tmp_path / "ws" if False else project_root, project_root)
    assert report["official_logger_events"] == 2
