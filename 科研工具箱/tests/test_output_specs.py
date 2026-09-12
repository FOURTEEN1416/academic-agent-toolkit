"""D7 中间产物最低内容规格（output_specs）回归测试。

背景（2026-09-12 原仓库缺陷修复建议 D7）：Step 2/4 曾产出 5.7KB/2.9KB
"目录级" LITERATURE.md/RESULTS.md——产物存在（manifest 过闸）但信息密度
近零，"走完了"的形式合规掩盖"走透了"的实质缺位。本文件覆盖：

- 薄产物（< min_bytes）→ 步骤失败，信息含最低规格教学；
- 达大小但无实质内容特征词 → 失败（require_any 任一命中即过）；
- 合格产物 → 正常推进；规格声明的文件不在本步产物清单 → 不激活；
- 真实模板 comp_cumcm：comp-literature / comp-code 的 output_specs 落位冒烟。
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.opencode_bridge import StepResult
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore


def make_catalog(specs=None, first_checkpoint=False):
    """两步小模板；第一步可选挂 output_specs（D7 规格声明同款结构）。"""
    first = {"skill_name": "comp-prob-analysis", "primary_output": "REPORT.md",
             "output_files": ["REPORT.md"], "has_checkpoint": first_checkpoint,
             "checkpoint_type": "approve" if first_checkpoint else None}
    if specs is not None:
        first["output_specs"] = specs
    return {"demo": {"sub_steps": [
        first,
        {"skill_name": "comp-modeling", "primary_output": "MODEL.md",
         "output_files": ["MODEL.md"], "has_checkpoint": False},
    ]}}


def setup_runner(tmp_path, specs=None, first_checkpoint=False):
    skills = tmp_path / "skills"
    for name in ("comp-prob-analysis", "comp-modeling"):
        skill = skills / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("skill", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    runner = WorkflowRunner(store, make_catalog(specs, first_checkpoint), skills)
    workflow = runner.start("demo", tmp_path / "workspace", {})
    return store, runner, workflow.id


def complete_with_text(runner, wf_id, text):
    action = runner.next_action(wf_id).action
    assert action is not None
    for output in action.output_files:
        path = action.workspace / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return runner.complete_step(wf_id, StepResult(
        ok=True, artifacts=list(action.output_files),
        metadata={"execution_evidence": {
            "schema_version": 1, "agent": "OpenCode Desktop",
            "step_id": action.step_id, "skill_name": action.skill_name,
            "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
            "commands": [{"command": "python code/gen_report.py", "returncode": 0, "cwd": "."}],
            "inputs": [], "outputs": list(action.output_files),
        }},
    ))


# ── 规格闸：拦薄 / 择词 / 放行 ────────────────────────────────────────────

def test_thin_output_rejected_by_min_bytes(tmp_path):
    """产物小于 min_bytes → 步骤失败，信息含最低规格与 rationale 教学。"""
    specs = {"REPORT.md": {"min_bytes": 5000, "require_any": [],
                           "rationale": "报告必须含实质台账，拦目录级薄产物"}}
    _store, runner, wf = setup_runner(tmp_path, specs=specs)
    result = complete_with_text(runner, wf, "x" * 3000)
    assert result.status == "failed", result.message
    assert "最低规格 5000B" in result.message
    assert "目录级薄产物" in result.message


def test_featureless_output_rejected_by_require_any(tmp_path):
    """达大小但不含任何特征词 → 失败（require_any 任一命中即过）。"""
    specs = {"REPORT.md": {"min_bytes": 100,
                           "require_any": ["核验", "台账", "引用"],
                           "rationale": "文献台账必须含核验/检索类实质内容"}}
    _store, runner, wf = setup_runner(tmp_path, specs=specs)
    result = complete_with_text(runner, wf, "纯目录清单\n- 文献1\n- 文献2\n" + "x" * 3000)
    assert result.status == "failed", result.message
    assert "特征词" in result.message


def test_good_output_passes_spec_gate(tmp_path):
    """合格产物（达大小 + 命中特征词）→ 正常推进。"""
    specs = {"REPORT.md": {"min_bytes": 100, "require_any": ["核验", "检索"],
                           "rationale": "文献台账必须含核验/检索类实质内容"}}
    _store, runner, wf = setup_runner(tmp_path, specs=specs)
    result = complete_with_text(runner, wf, "# 台账\n每条文献的核验状态已登记。\n" + "x" * 3000)
    assert result.status in ("advanced", "completed"), result.message


def test_spec_not_activated_for_files_outside_outputs(tmp_path):
    """规格声明的文件不在本步 output_files → 规格不激活（向后兼容语义）。"""
    specs = {"OTHER.md": {"min_bytes": 99999, "require_any": ["不存在"],
                          "rationale": "不应被激活"}}
    _store, runner, wf = setup_runner(tmp_path, specs=specs)
    result = complete_with_text(runner, wf, "x" * 3000)
    assert result.status in ("advanced", "completed"), result.message


def test_no_specs_step_unaffected(tmp_path):
    """未声明 output_specs 的步骤零影响（既有全量套件同款路径）。"""
    _store, runner, wf = setup_runner(tmp_path, specs=None)
    result = complete_with_text(runner, wf, "x" * 3000)
    assert result.status in ("advanced", "completed"), result.message


def test_failed_spec_lands_step_failed_event(tmp_path):
    """规格失败也走 step_failed 事件（与其他闸同口径，审计可查）。"""
    specs = {"REPORT.md": {"min_bytes": 5000, "require_any": [], "rationale": "规格闸"}}
    store, runner, wf = setup_runner(tmp_path, specs=specs)
    result = complete_with_text(runner, wf, "x" * 3000)
    assert result.status == "failed"
    rows = store._connection.execute(
        "SELECT payload FROM events WHERE workflow_id = ? AND event_type = 'step_failed'",
        (wf,)).fetchall()
    assert rows, "规格失败必须落 step_failed 事件"
    assert "规格" in json.loads(rows[-1]["payload"])["stderr"]


# ── 真实模板：output_specs 落位冒烟 ──────────────────────────────────────

def test_real_template_comp_cumcm_output_specs_in_place():
    """comp-literature / comp-code 的 output_specs 已按 D7 落位且结构合法。"""
    templates = json.loads(
        (ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = templates["comp_cumcm"]["sub_steps"]
    by_name = {s["skill_name"]: s for s in steps}

    lit_specs = by_name["comp-literature"]["metadata"]["output_specs"]
    assert "LITERATURE.md" in lit_specs
    lit = lit_specs["LITERATURE.md"]
    assert int(lit["min_bytes"]) > 0
    assert lit["require_any"], "LITERATURE.md 规格必须含实质内容特征词"
    assert lit.get("rationale")

    code_specs = by_name["comp-code"]["metadata"]["output_specs"]
    assert "RESULTS.md" in code_specs
    code = code_specs["RESULTS.md"]
    assert int(code["min_bytes"]) > 0
    assert code["require_any"]
    assert code.get("rationale")
