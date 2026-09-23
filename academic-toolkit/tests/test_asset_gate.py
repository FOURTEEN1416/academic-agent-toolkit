"""C2 步骤资产强制申报闸回归（2026-09-12 资产利用率审计落地）。

背景：C1 只覆盖"技能"，数据/参考论文/工具脚本/参考图集等非技能资产在
StepAction 零暴露——引擎只给技能，仓库其余资产处于"流程不可见"状态。
修复：步骤 metadata 带 assets（{"name","path","note"}，path 仓库根相对）时，
evidence 必须含 assets 申报 {"used":[资产名], "skipped":[{"name","reason"}]}，
used/skipped 恰好覆盖清单；used 须有真实痕迹（资产名或路径出现在
commands/outputs/inputs）。语义与 C1 完全同构。

⚠️ 零扰动契约：运行中的工作流（start 早于本机制）持久化 metadata 无 assets，
C2 闸不激活——test_step_without_assets_gate_inactive 守护该口径。
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.opencode_bridge import StepResult
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore

ASSETS = [
    {"name": "引用核验器", "path": "academic-toolkit/tools/citation_checker.py", "note": "引用条目机检"},
    {"name": "获奖论文配色分析", "path": "assets-local/award-papers/图表配色分析报告.md", "note": "配色对照"},
]


def _make_catalog(output_files, assets):
    step = {
        "skill_name": "comp-literature",
        "primary_output": output_files[0],
        "output_files": list(output_files),
        "has_checkpoint": False,
    }
    if assets is not None:
        step["assets"] = assets
    return {"demo": {"sub_steps": [step]}}


def _setup(tmp_path, output_files=("LITERATURE.md",), assets=ASSETS):
    skill = tmp_path / "skills" / "comp-literature" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("skill", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, _make_catalog(output_files, assets), tmp_path / "skills")
    workflow = runner.start("demo", tmp_path / "workspace", {})
    return store, runner, workflow.id


def _complete(runner, wf_id, commands, outputs=("LITERATURE.md",), assets_decl=None):
    action = runner.next_action(wf_id).action
    assert action is not None
    for output in outputs:
        path = action.workspace / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * 3000, encoding="utf-8")
    evidence = {
        "schema_version": 1,
        "agent": "ZCode",
        "step_id": action.step_id,
        "skill_name": action.skill_name,
        "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
        "commands": commands,
        "inputs": [],
        "outputs": list(outputs),
    }
    if assets_decl is not None:
        evidence["assets"] = assets_decl
    return runner.complete_step(wf_id, StepResult(
        ok=True, artifacts=list(outputs), metadata={"execution_evidence": evidence}))


def test_stepaction_carries_assets(tmp_path):
    """StepAction.assets 透传（两构造点同步口径），指令文本必须可见。"""
    _store, runner, wf = _setup(tmp_path)
    result = runner.next_action(wf)
    assert result.action.assets == ASSETS
    instructions = result.action.execution_instructions()
    assert "本步资产" in instructions
    assert "引用核验器" in instructions
    assert "academic-toolkit/tools/citation_checker.py" in instructions


def test_missing_assets_declaration_rejected(tmp_path):
    """步骤带 assets 但证据缺 assets 申报 → FAILED + 教学格式。"""
    store, runner, wf = _setup(tmp_path)
    result = _complete(runner, wf, commands=[{"command": "python code/build.py", "returncode": 0, "cwd": "."}])
    assert result.status == "failed"
    assert "缺少 assets 申报" in result.message
    assert '"assets": {"used"' in result.message
    row = store._connection.execute(
        "SELECT status FROM workflow_steps WHERE workflow_id = ?", (wf,)).fetchone()
    assert row[0] == "failed"


def test_full_skip_with_reasons_passes(tmp_path):
    """申报 ≠ 强制使用：全部 skipped+非空理由 → 过闸。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[{"command": "python code/build.py", "returncode": 0, "cwd": "."}],
        assets_decl={"used": [], "skipped": [
            {"name": "引用核验器", "reason": "文献均经三源核验，无引用条目需机检"},
            {"name": "获奖论文配色分析", "reason": "本步不产图"},
        ]})
    assert result.status in ("advanced", "completed"), result.message


def test_used_with_path_trace_passes(tmp_path):
    """used 资产路径出现在命令串（Windows 反斜杠归一化）→ 有痕过闸。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[
            {"command": "python code/build.py", "returncode": 0, "cwd": "."},
            {"command": r"python academic-toolkit\tools\citation_checker.py paper/references.bib",
             "returncode": 0, "cwd": "."},
        ],
        assets_decl={"used": ["引用核验器"], "skipped": [
            {"name": "获奖论文配色分析", "reason": "本步不产图"}]})
    assert result.status in ("advanced", "completed"), result.message


def test_used_without_trace_rejected_with_teaching(tmp_path):
    """used 资产零痕迹（命令与产物/输入均无资产名/路径）→ 拒 + 教学两条出路。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[{"command": "python code/build.py", "returncode": 0, "cwd": "."}],
        assets_decl={"used": ["引用核验器"], "skipped": [
            {"name": "获奖论文配色分析", "reason": "本步不产图"}]})
    assert result.status == "failed"
    assert "零使用痕迹" in result.message
    assert "evidence.commands" in result.message


def test_used_trace_absent_in_outputs_rejected(tmp_path):
    """used 痕迹口径与 C1 同源：declared outputs/commands/inputs 全部无资产名/路径 → 拒。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[{"command": "python code/build.py", "returncode": 0, "cwd": "."}],
        assets_decl={"used": ["引用核验器", "获奖论文配色分析"], "skipped": []},
    )
    assert result.status == "failed"  # 产物路径无资产痕迹 → 拒（与 C1 同口径：伪报必拦）


def test_unknown_asset_rejected(tmp_path):
    """申报了清单外的资产 → 拒（防清单漂移下的伪覆盖）。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[{"command": "python code/build.py", "returncode": 0, "cwd": "."}],
        assets_decl={"used": [], "skipped": [
            {"name": "引用核验器", "reason": "不适用"},
            {"name": "获奖论文配色分析", "reason": "不适用"},
            {"name": "清单外资产", "reason": "不适用"},
        ]})
    assert result.status == "failed"
    assert "未给出的资产" in result.message


def test_missing_coverage_rejected(tmp_path):
    """清单资产未逐一申报 → 拒。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[{"command": "python code/build.py", "returncode": 0, "cwd": "."}],
        assets_decl={"used": [], "skipped": [
            {"name": "引用核验器", "reason": "不适用"}]})
    assert result.status == "failed"
    assert "未逐一申报" in result.message


def test_used_skipped_overlap_rejected(tmp_path):
    """同一资产既 used 又 skipped（自相矛盾申报）→ 拒。"""
    _store, runner, wf = _setup(tmp_path)
    result = _complete(
        runner, wf,
        commands=[{"command": "python academic-toolkit/tools/citation_checker.py", "returncode": 0, "cwd": "."}],
        assets_decl={"used": ["引用核验器"], "skipped": [
            {"name": "引用核验器", "reason": "没用"},
            {"name": "获奖论文配色分析", "reason": "本步不产图"}]})
    assert result.status == "failed"
    assert "自相矛盾" in result.message


def test_step_without_assets_gate_inactive(tmp_path):
    """零扰动契约：步骤无 assets（运行中旧工作流形态）→ 无需申报照常过闸。"""
    _store, runner, wf = _setup(tmp_path, assets=None)
    result = _complete(runner, wf, commands=[{"command": "python code/build.py", "returncode": 0, "cwd": "."}])
    assert result.status in ("advanced", "completed"), result.message


def test_mandatory_asset_skip_rejected(tmp_path):
    """W2 mandatory 档：标 "mandatory": true 的资产申报 skipped → 拒（强制使用）。"""
    assets = [dict(ASSETS[0]), dict(ASSETS[1])]
    assets[1]["mandatory"] = True
    _store, runner, wf = _setup(tmp_path, assets=assets)
    result = _complete(
        runner, wf,
        commands=[{"command": "python code/build.py", "returncode": 0, "cwd": "."}],
        assets_decl={"used": [], "skipped": [
            {"name": "引用核验器", "reason": "本步无引用核验需求"},
            {"name": "获奖论文配色分析", "reason": "时间不够"},
        ]})
    assert result.status == "failed"
    assert "mandatory" in result.message


def test_mandatory_asset_used_with_trace_passes(tmp_path):
    """W2 mandatory 档：真实使用留痕 → 过（强制但可达成）。"""
    assets = [dict(ASSETS[0]), dict(ASSETS[1])]
    assets[1]["mandatory"] = True
    _store, runner, wf = _setup(tmp_path, assets=assets)
    result = _complete(
        runner, wf,
        commands=[{"command": "python academic-toolkit/tools/citation_checker.py LITERATURE.md && "
                              "cat assets-local/award-papers/图表配色分析报告.md", "returncode": 0, "cwd": "."}],
        assets_decl={"used": ["引用核验器", "获奖论文配色分析"], "skipped": []})
    assert result.status == "completed", result.message
