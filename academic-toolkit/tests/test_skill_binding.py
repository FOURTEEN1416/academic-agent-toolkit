"""P4 技能强制绑定回归（2026-09-19 建立）。

背景（用户质询）："工作流步骤不会强制调用 skills"——原先主技能只以 `skill_sha256`
出现在执行证据里，算一个哈希即可过闸，无法区分"读了技能契约"与"只填了哈希"；
关键辅助技能也能被一条 skipped 理由绕过。

本文件守护三层：
  1. 声明层：模板步骤 `metadata.skill_binding` 的结构与真仓覆盖（comp_cumcm 全 14 步）；
  2. 执行层：`complete_step` 的三条硬判据（主技能痕迹 / mandatory 不可 skipped /
     mandatory 须有命令级痕迹），以及**向后兼容**（未声明绑定的步骤零影响）；
  3. 审计层：`verify_skill_bindings` 把声明与 L1 实际调用对账，
     L1 缺席时如实降级为 unavailable（而非判通过）。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.opencode_bridge import StepAction, StepResult  # noqa: E402
from engine.workflow_runner import WorkflowRunner  # noqa: E402
from engine.workflow_store import WorkflowStore  # noqa: E402


# ── 脚手架 ──────────────────────────────────────────────────────────

def _make_skills(tmp_path: Path, names: tuple[str, ...], main: str) -> Path:
    skills_root = tmp_path / "skills"
    for name in names:
        p = skills_root / name / "SKILL.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("skill", encoding="utf-8")
    return skills_root


def _run_step(tmp_path: Path, metadata: dict, evidence_extra: dict | None = None,
              skill_name: str = "demo-main", extra_skills: tuple[str, ...] = ()):
    skills_root = _make_skills(tmp_path, ("demo-main", *extra_skills), skill_name)
    catalog = {"demo": {"sub_steps": [{
        "skill_name": skill_name,
        "primary_output": "OUT.md",
        "output_files": ["OUT.md"],
        "has_checkpoint": False,
        "metadata": {"display_name": "demo", **metadata},
    }]}}
    workspace = tmp_path / "workspace"
    db = tmp_path / "workflow.sqlite"
    store = WorkflowStore(db)
    runner = WorkflowRunner(store, catalog, skills_root)
    workflow = runner.start("demo", workspace, {})
    action = runner.next_action(workflow.id).action
    (workspace / "OUT.md").write_text("# out\n" + "内容" * 200, encoding="utf-8")
    evidence = {
        "schema_version": 1,
        "agent": "OpenCode Desktop",
        "step_id": action.step_id,
        "skill_name": action.skill_name,
        "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
        "commands": [{"command": "python scripts/gen.py", "returncode": 0, "cwd": "."}],
        "inputs": [],
        "outputs": ["OUT.md"],
    }
    evidence.update(evidence_extra or {})
    result = StepResult(ok=True, artifacts=["OUT.md"],
                        metadata={"execution_evidence": evidence})
    outcome = runner.complete_step(workflow.id, result)
    store.close()
    return outcome, action


# ── 声明层 ──────────────────────────────────────────────────────────

def _binding_action(**kwargs) -> StepAction:
    base = dict(workflow_id="w", step_id="s", position=1, skill_name="comp-code",
                display_name="d", workspace=Path("."), skill_path=Path("x"),
                output_files=[], primary_output="", has_checkpoint=False,
                checkpoint_type=None)
    base.update(kwargs)
    return StepAction(**base)


def test_binding_requirements_empty_without_binding():
    action = _binding_action()
    assert action.binding_requirements() == []
    assert "技能绑定" not in action.execution_instructions()


def test_binding_requirements_render_main_and_mandatory():
    action = _binding_action(skill_binding={"main_required": True, "mandatory": ["sympy"]})
    text = "\n".join(action.binding_requirements())
    assert "comp-code" in text and "SKILL.md" in text
    assert "sympy" in text and "不得申报 skipped" in text
    assert "技能绑定（强制，complete 时校验）" in action.execution_instructions()


def test_real_comp_cumcm_steps_all_bound():
    """真仓机检：comp_cumcm 全 14 步必须显式声明 skill_binding.main_required。"""
    data = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = data["comp_cumcm"]["sub_steps"]
    assert len(steps) == 14
    for step in steps:
        binding = (step.get("metadata") or {}).get("skill_binding") or {}
        assert binding.get("main_required") is True, step["skill_name"]


def test_real_step5_mandatory_palette_is_also_a_companion():
    """mandatory 技能必须在 companion_skills 清单内，否则 C1 闸不会要求它申报。"""
    data = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = {s["skill_name"]: s for s in data["comp_cumcm"]["sub_steps"]}
    meta = steps["paper-figure"]["metadata"]
    mandatory = meta["skill_binding"]["mandatory"]
    assert mandatory == ["paper-figure-palette"]
    for skill in mandatory:
        assert skill in (meta.get("companion_skills") or []), skill


def test_real_all_templates_steps_bound():
    """全库口径：所有模板步骤都带 main_required 绑定（防新增模板漏声明）。"""
    data = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    unbound = []
    for tpl_name, tpl in data.items():
        if not isinstance(tpl, dict):
            continue
        for step in tpl.get("sub_steps", []):
            binding = (step.get("metadata") or {}).get("skill_binding") or {}
            if binding.get("main_required") is not True:
                unbound.append(f"{tpl_name}/{step.get('skill_name')}")
    assert unbound == [], unbound


# ── 执行层：主技能痕迹 ───────────────────────────────────────────────

def test_main_trace_missing_is_rejected(tmp_path):
    outcome, _ = _run_step(tmp_path, {"skill_binding": {"main_required": True}})
    assert outcome.status == "failed"
    assert "技能绑定不合规" in outcome.message
    assert "主技能" in outcome.message


def test_main_trace_via_skill_name_in_command_passes(tmp_path):
    outcome, _ = _run_step(
        tmp_path, {"skill_binding": {"main_required": True}},
        evidence_extra={"commands": [
            {"command": "python scripts/gen.py", "returncode": 0, "cwd": "."},
            {"command": "cat skills/demo-main/SKILL.md", "returncode": 0, "cwd": "."},
        ]})
    assert outcome.status != "failed", outcome.message


def test_no_binding_means_no_new_rejection(tmp_path):
    """向后兼容：未声明 skill_binding 的步骤，同一条证据不得被新闸拦下。"""
    outcome, _ = _run_step(tmp_path, {})
    assert outcome.status != "failed", outcome.message


def test_binding_with_hyphen_and_underscore_equivalent(tmp_path):
    """痕迹比对与技能名归一化同口径（'-' 与 '_' 等价）。"""
    outcome, _ = _run_step(
        tmp_path, {"skill_binding": {"main_required": True, "main": "demo_main"}},
        evidence_extra={"commands": [
            {"command": "cat skills/demo-main/SKILL.md", "returncode": 0, "cwd": "."},
        ]})
    assert outcome.status != "failed", outcome.message


# ── 执行层：mandatory 不可跳过 ───────────────────────────────────────

def test_mandatory_skipped_is_rejected(tmp_path):
    outcome, _ = _run_step(
        tmp_path,
        {"companion_skills": ["aux-tool"],
         "skill_binding": {"main_required": False, "mandatory": ["aux-tool"]}},
        evidence_extra={
            "commands": [{"command": "cat skills/demo-main/SKILL.md", "returncode": 0, "cwd": "."}],
            "companion_skills": {"used": [], "skipped": [{"skill": "aux-tool", "reason": "本题不需要"}]},
        },
        extra_skills=("aux-tool",))
    assert outcome.status == "failed"
    assert "必用项（不可跳过）" in outcome.message


def test_mandatory_used_without_command_is_rejected(tmp_path):
    """只在产物路径里蹭名不算——必须有命令级痕迹。"""
    outcome, _ = _run_step(
        tmp_path,
        {"companion_skills": ["aux-tool"],
         "skill_binding": {"main_required": False, "mandatory": ["aux-tool"]}},
        evidence_extra={
            "commands": [{"command": "python scripts/gen.py", "returncode": 0, "cwd": "."}],
            "inputs": ["aux-tool-notes.md"],
            "companion_skills": {"used": ["aux-tool"], "skipped": []},
        },
        extra_skills=("aux-tool",))
    assert outcome.status == "failed"
    assert "未出现在任何命令中" in outcome.message


def test_mandatory_used_with_command_passes(tmp_path):
    outcome, _ = _run_step(
        tmp_path,
        {"companion_skills": ["aux-tool"],
         "skill_binding": {"main_required": True, "mandatory": ["aux-tool"]}},
        evidence_extra={
            "commands": [
                {"command": "cat skills/demo-main/SKILL.md", "returncode": 0, "cwd": "."},
                {"command": "cat skills/aux-tool/SKILL.md", "returncode": 0, "cwd": "."},
            ],
            "companion_skills": {"used": ["aux-tool"], "skipped": []},
        },
        extra_skills=("aux-tool",))
    assert outcome.status != "failed", outcome.message


# ── 审计层：声明 vs L1 实际 --------------------------------------------------

def _write_evidence(workspace: Path, step_id: str, skill_name: str, binding: dict) -> None:
    d = workspace / ".engine" / "evidence"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{step_id}.json").write_text(json.dumps({
        "schema_version": 1,
        "action": {"workflow_id": "w", "step_id": step_id, "skill_name": skill_name,
                   "skill_binding": binding},
        "evidence": {"commands": []},
        "manifest": {},
    }, ensure_ascii=False), encoding="utf-8")


def test_verify_bindings_unavailable_without_l1(tmp_path):
    """无 L1 审计日志 → 如实标注 unavailable，不判通过。"""
    from engine.audit_store import verify_skill_bindings
    ws = tmp_path / "ws"
    _write_evidence(ws, "s1", "demo-main", {"main_required": True})
    res = verify_skill_bindings(ws, tmp_path / "project")
    assert res["verdict"] == "unavailable"
    assert res["steps_checked"] == 1
    assert "L1" in res["unavailable_reason"]


def test_verify_bindings_warning_when_no_actual_invocation(tmp_path):
    """L1 有日志但无对应技能调用/读取 → warning（自述与事实不符）。"""
    from engine.audit_store import AuditStore, verify_skill_bindings
    ws = tmp_path / "ws"
    project = tmp_path / "project"
    _write_evidence(ws, "s1", "demo-main", {"main_required": True})
    AuditStore(project).record({"type": "tool_call", "tool": "bash",
                                "detail": {"command": "python scripts/gen.py"}})
    res = verify_skill_bindings(ws, project)
    assert res["verdict"] == "warning"
    assert res["unverified"][0]["missing"] == ["demo-main"]


def test_verify_bindings_ok_when_skill_read_recorded(tmp_path):
    """L1 记录了读取 SKILL.md → 可核，判 ok。"""
    from engine.audit_store import AuditStore, verify_skill_bindings
    ws = tmp_path / "ws"
    project = tmp_path / "project"
    _write_evidence(ws, "s1", "demo-main", {"main_required": True, "mandatory": ["aux-tool"]})
    store = AuditStore(project)
    store.record({"type": "tool_call", "tool": "read",
                  "detail": {"filePath": "D:/repo/academic-toolkit/skills/demo-main/SKILL.md"}})
    store.record({"type": "tool_call", "tool": "skill", "detail": {"skillName": "aux-tool"}})
    res = verify_skill_bindings(ws, project)
    assert res["verdict"] == "ok", res
    assert res["unverified"] == []


def test_verify_bindings_ok_when_no_binding_declared(tmp_path):
    """没有任何步骤声明绑定 → 无事可查，ok 且 steps_checked=0。"""
    from engine.audit_store import verify_skill_bindings
    ws = tmp_path / "ws"
    _write_evidence(ws, "s1", "demo-main", {})
    res = verify_skill_bindings(ws, tmp_path / "project")
    assert res["verdict"] == "ok" and res["steps_checked"] == 0


def test_evidence_payload_persists_binding(tmp_path):
    """绑定必须随证据落盘——审计层才能在不回查模板的情况下对账。"""
    from engine.execution_protocol import write_execution_evidence
    ws = tmp_path / "ws"
    ws.mkdir()
    action = _binding_action(workspace=ws, skill_path=tmp_path / "SKILL.md",
                             skill_binding={"main_required": True, "mandatory": ["aux"]})
    (tmp_path / "SKILL.md").write_text("skill", encoding="utf-8")
    rel = write_execution_evidence(ws, action, {"commands": []}, {})
    payload = json.loads((ws / rel).read_text(encoding="utf-8"))
    assert payload["action"]["skill_binding"] == {"main_required": True, "mandatory": ["aux"]}
