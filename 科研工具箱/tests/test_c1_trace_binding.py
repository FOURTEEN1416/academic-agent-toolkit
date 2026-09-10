"""C1 used 痕迹绑定回归（A2 major / A5 ⑫ / 修复清单 P1-5）。

修复前：C1 闸只查申报格式与集合覆盖，used 技能可以零使用痕迹直接过闸
（实测伪报 used=['problem-analysis'] 命令零引用通过）。
修复后：used 技能名（大小写不敏感，'-' 与 '_' 等价）必须出现在
evidence.commands 任一命令串或任一 declared outputs/inputs 路径中，
否则步骤 FAILED 并教学两条出路；skipped 申报不受影响。
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.opencode_bridge import StepResult
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


def _make_catalog(output_files):
    return {"demo": {"sub_steps": [{
        "skill_name": "comp-prob-analysis",
        "primary_output": output_files[0],
        "output_files": list(output_files),
        "has_checkpoint": False,
        "companion_skills": ["problem-analysis"],
   }]}}


CATALOG = _make_catalog(["REPORT.md"])


def _setup(tmp_path, output_files=("REPORT.md",)):
    skill = tmp_path / "skills" / "comp-prob-analysis" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("skill", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, _make_catalog(output_files), tmp_path / "skills")
    workflow = runner.start("demo", tmp_path / "workspace", {})
    return store, runner, workflow.id


def _complete(runner, wf_id, commands, outputs=("REPORT.md",), companion=None):
    """推进到 RUNNING 并以给定 commands 完成步骤。"""
    action = runner.next_action(wf_id).action
    assert action is not None
    for output in outputs:
        path = action.workspace / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * 3000, encoding="utf-8")
    evidence = {
        "schema_version": 1,
        "agent": "OpenCode Desktop",
        "step_id": action.step_id,
        "skill_name": action.skill_name,
        "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
        "commands": commands,
        "inputs": [],
        "outputs": list(outputs),
    }
    if companion is not None:
        evidence["companion_skills"] = companion
    return runner.complete_step(wf_id, StepResult(
        ok=True, artifacts=list(outputs), metadata={"execution_evidence": evidence}))


def test_used_with_command_trace_passes(tmp_path):
    """used 技能名出现在命令串中 → 有痕，过闸。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[{"command": "grep -q problem-analysis REPORT.md", "returncode": 0, "cwd": "."}],
        companion={"used": ["problem-analysis"], "skipped": []},
    )
    assert result.status in ("advanced", "completed"), result.message


def test_used_with_path_trace_passes(tmp_path):
    """used 技能名出现在 declared output 路径中（路径大小写形态不同也归一匹配）→ 有痕，过闸。"""
    _store, runner, wf = _setup(tmp_path, output_files=("Problem_Analysis/REPORT.md",))
    result = _complete(
        runner, wf,
        commands=[{"command": "python code/gen_report.py", "returncode": 0, "cwd": "."}],
        outputs=("Problem_Analysis/REPORT.md",),
        companion={"used": ["problem-analysis"], "skipped": []},
    )
    assert result.status in ("advanced", "completed"), result.message


def test_used_without_trace_rejected_with_teaching(tmp_path):
    """used 零使用痕迹（命令与产物/输入路径均无技能名）→ 拒 + 教学两条出路。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[{"command": "python code/gen_report.py", "returncode": 0, "cwd": "."}],
        companion={"used": ["problem-analysis"], "skipped": []},
    )
    assert result.status == "failed"
    assert "零使用痕迹" in result.message
    # 教学①：如实补记 consult 命令；教学②：改报 skipped+理由
    assert "evidence.commands" in result.message
    assert "skipped" in result.message


def test_used_without_trace_block_is_recorded_as_failed_step(tmp_path):
    """无痕拒绝必须真实落 FAILED（可被 retry 带内恢复），不是仅返回错误。"""
    store, runner, wf = _setup(tmp_path)
    _complete(
        runner, wf,
        commands=[{"command": "python code/gen_report.py", "returncode": 0, "cwd": "."}],
        companion={"used": ["problem-analysis"], "skipped": []},
    )
    row = store._connection.execute(
        "SELECT status FROM workflow_steps WHERE workflow_id = ?", (wf,)
    ).fetchone()
    assert row[0] == "failed"


def test_skipped_declaration_unaffected(tmp_path):
    """skipped+理由 申报不受痕迹校验影响，照常过闸。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[{"command": "python code/gen_report.py", "returncode": 0, "cwd": "."}],
        companion={"used": [],
                   "skipped": [{"skill": "problem-analysis", "reason": "问题已直接拆解，无需辅助技能"}]},
    )
    assert result.status in ("advanced", "completed"), result.message


def test_double_brace_escape_residue_fixed(tmp_path):
    """小修 6a：拒绝消息里的格式教学必须渲染单花括号（此前 {{...}} 残留）。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[{"command": "python code/gen_report.py", "returncode": 0, "cwd": "."}],
        companion={"used": [], "skipped": []},
    )
    assert result.status == "failed"
    assert '{{' not in result.message
    assert '{"used": ["技能名"]' in result.message
