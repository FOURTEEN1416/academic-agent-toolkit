"""C1 申报自洽回归（A2 minor 审计修复）：used∩skipped 重叠申报必须拒绝。

修复前：C1 覆盖校验用 set(used) | set(skipped)，同一技能同时出现在 used 与
skipped（含大小写/连字符变体）均放行——申报自相矛盾而不留违规记录。
修复后：used∩skipped 非空即拒绝（教学"二选一"）；归一化口径与 used 痕迹校验
一致（不区分大小写、'-' 与 '_' 等价），变体拼写重叠同样拦截。
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.opencode_bridge import StepResult
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


def _make_catalog(companion_skills):
    return {"demo": {"sub_steps": [{
        "skill_name": "comp-prob-analysis",
        "primary_output": "REPORT.md",
        "output_files": ["REPORT.md"],
        "has_checkpoint": False,
        "companion_skills": list(companion_skills),
   }]}}


def _setup(tmp_path, companion_skills):
    skill = tmp_path / "skills" / "comp-prob-analysis" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("skill", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, _make_catalog(companion_skills), tmp_path / "skills")
    workflow = runner.start("demo", tmp_path / "workspace", {})
    return runner, workflow.id


def _complete(runner, wf_id, companion):
    action = runner.next_action(wf_id).action
    assert action is not None
    path = action.workspace / "REPORT.md"
    path.write_text("x" * 3000, encoding="utf-8")
    evidence = {
        "schema_version": 1,
        "agent": "OpenCode Desktop",
        "step_id": action.step_id,
        "skill_name": action.skill_name,
        "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
        "commands": [{"command": "grep -q problem-analysis REPORT.md",
                      "returncode": 0, "cwd": "."}],
        "inputs": [],
        "outputs": ["REPORT.md"],
    }
    if companion is not None:
        evidence["companion_skills"] = companion
    return runner.complete_step(wf_id, StepResult(
        ok=True, artifacts=["REPORT.md"], metadata={"execution_evidence": evidence}))


def test_exact_overlap_used_and_skipped_rejected(tmp_path):
    """同一技能同时申报 used 与 skipped → 拒绝 + 教学"二选一"。"""
    runner, wf = _setup(tmp_path, ["problem-analysis"])
    result = _complete(runner, wf, {
        "used": ["problem-analysis"],
        "skipped": [{"skill": "problem-analysis", "reason": "顺手也跳过"}],
    })
    assert result.status == "failed", result.message
    assert "同时申报了 used 与 skipped" in result.message
    assert "problem-analysis" in result.message
    assert "二选一" in result.message
    # 拒绝必须真实落 FAILED（可带内恢复），不是仅返回错误文案
    row = runner.store._connection.execute(
        "SELECT status FROM workflow_steps WHERE workflow_id = ?", (wf,)).fetchone()
    assert row[0] == "failed"


def test_case_variant_overlap_rejected(tmp_path):
    """大小写/连字符变体的重叠同样拦截（归一化口径与 used 痕迹校验一致）。

    推荐清单含同一技能的两种拼写（模板层面可能出现的变体），此时原始集合
    交集为空、归一化交集非空——修复前该申报会照常过闸。
    """
    runner, wf = _setup(tmp_path, ["problem-analysis", "PROBLEM_ANALYSIS"])
    result = _complete(runner, wf, {
        "used": ["problem-analysis"],
        "skipped": [{"skill": "PROBLEM_ANALYSIS", "reason": "拼写不同想蒙混"}],
    })
    assert result.status == "failed", result.message
    assert "同时申报了 used 与 skipped" in result.message


def test_disjoint_declaration_still_passes(tmp_path):
    """无重叠的合规申报（used 有痕 / skipped 有理由）不受影响。"""
    runner, wf = _setup(tmp_path, ["problem-analysis", "another-skill"])
    result = _complete(runner, wf, {
        "used": ["problem-analysis"],
        "skipped": [{"skill": "another-skill", "reason": "本步无需该技能"}],
    })
    assert result.status in ("advanced", "completed"), result.message

