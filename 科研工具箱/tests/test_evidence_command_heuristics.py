"""伪命令启发式误杀修复回归（A5 摩擦日志 ⑤⑬ / 修复清单 P0-2）。

两实杀案例必须放行：
① 含引号包裹 grep 模式的命令（comp-prob-analysis 完成铁律强制命令，
   曾被引号内 `-->` 箭头规则误杀）；
② Windows 绝对路径可执行命令（盘符冒号曾被 ':' 描述性规则误杀）。

同时不得整体放松：纯描述性文本（无引号、无可执行形态）必须继续被拒。
"""
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.execution_protocol import (
    _looks_like_descriptive_command,
    validate_execution_evidence,
)
from engine.opencode_bridge import StepAction, StepResult


# ── 实杀案例 ①：引号包裹的 grep 模式（含 "-->"）必须放行 ──────────────────

@pytest.mark.parametrize("command", [
    "grep -q '<!-- END FIGURE_MANIFEST -->' PROBLEM_ANALYSIS.md",
    "grep -q \"<!-- END FIGURE_MANIFEST -->\" PROBLEM_ANALYSIS.md",
    "grep -q 'problem-analysis' notes.md && echo ok",
])
def test_quoted_grep_pattern_with_arrow_is_accepted(command):
    assert _looks_like_descriptive_command(command) is False


# ── 实杀案例 ②：Windows 绝对路径可执行命令（盘符冒号）必须放行 ────────────

@pytest.mark.parametrize("command", [
    "C:/Program Files/draw.io/draw.io.EXE -x -f png figures/flow.drawio -o figures/flow.png",
    "C:\\Program Files\\draw.io\\draw.io.EXE -x -f png figures/flow.drawio",
    '"C:/Program Files/draw.io/draw.io.EXE" -x -f png figures/flow.drawio',
])
def test_windows_absolute_path_command_is_accepted(command):
    assert _looks_like_descriptive_command(command) is False


# ── 引号内代码是操作对象：真实 -c 代码放行，注释仍拒 ─────────────────────

def test_real_inline_python_code_is_accepted():
    assert _looks_like_descriptive_command(
        "python -c \"import json; print(json.load(open('a.json')))\""
    ) is False


def test_inline_comment_only_code_is_still_rejected():
    # 现有守卫保持：-c 后只有注释文本 = 伪命令（引号不豁免 -c 注释分支）
    assert _looks_like_descriptive_command(
        "python -c \"# logic review: 5-category gap analysis per comp-review SKILL.md\""
    ) is True


# ── 不得整体放松：纯描述性文本必须继续被拒 ─────────────────────────────

@pytest.mark.parametrize("fake", [
    "运行分析脚本->得到结果",  # 无引号无真实可执行形态的箭头流程描述
    "Word COM main.docx -> main.pdf (xelatex unavailable, docx route)",
    "python workbook inspection for four supplied STR attachments",
    "python modeling capability coverage check",
    "run the full pipeline and verify the results.",
    "数据检查: 确认所有图表已生成并归档",
])
def test_descriptive_text_without_quotes_is_still_rejected(fake):
    assert _looks_like_descriptive_command(fake) is True


# ── 端到端：validate_execution_evidence 层两实杀命令通过完整校验 ──────────

def _make_action(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("demo skill", encoding="utf-8")
    return StepAction("wf", "step", 0, "demo", "Demo", workspace, skill,
                      ["out.txt"], "out.txt", False, None)


def _evidence(action, command):
    return {
        "schema_version": 1,
        "agent": "OpenCode Desktop",
        "step_id": action.step_id,
        "skill_name": action.skill_name,
        "skill_sha256": hashlib.sha256(action.skill_path.read_bytes()).hexdigest(),
        "commands": [{"command": command, "returncode": 0, "cwd": "."}],
        "inputs": [],
        "outputs": ["out.txt"],
    }


@pytest.mark.parametrize("command", [
    "grep -q '<!-- END FIGURE_MANIFEST -->' PROBLEM_ANALYSIS.md",
    "C:/Program Files/draw.io/draw.io.EXE -x -f png figures/flow.drawio -o figures/flow.png",
])
def test_real_kill_cases_pass_full_evidence_validation(tmp_path, command):
    action = _make_action(tmp_path)
    (action.workspace / "out.txt").write_text("x" * 100, encoding="utf-8")
    result = StepResult(ok=True, artifacts=["out.txt"],
                        metadata={"execution_evidence": _evidence(action, command)})

    validated = validate_execution_evidence(action.workspace, action, result)

    assert validated["commands"][0]["command"] == command


@pytest.mark.parametrize("fake", [
    "运行分析脚本->得到结果",
    "Word COM main.docx -> main.pdf (xelatex unavailable, docx route)",
])
def test_descriptive_cases_fail_full_evidence_validation(tmp_path, fake):
    action = _make_action(tmp_path)
    (action.workspace / "out.txt").write_text("x" * 100, encoding="utf-8")
    result = StepResult(ok=True, artifacts=["out.txt"],
                        metadata={"execution_evidence": _evidence(action, fake)})

    with pytest.raises(ValueError, match="descriptive text"):
        validate_execution_evidence(action.workspace, action, result)
