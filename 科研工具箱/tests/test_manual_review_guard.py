"""A7R-F1 防伪造红线回归：approved_by 必须是人类操作者署名。

修复前（敌意审计 A7R 实测）：validate_visual_manual_check 只查 approved_by 非空
+ ≥5 条逐项记录——approved_by=agent / 'AI审稿机器人' 照样放行，第 11 步受控
降级可被 agent 零门槛伪造，文档声称的"硬拦"不存在。
修复后：approved_by 命中 agent 自指词（agent/ai/bot/llm/auto/机器人/智能体/自动
及常见模型名；英文词 ASCII 字母边界匹配、中文词子串匹配，不区分大小写）→
manual_check 闸 ok=False，并教学"必须由人类操作者真实署名"。
与 test_review_gate_manual_fallback.py（manual_review 三态）互补不回归。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.quality_gates import (
    VISUAL_MANUAL_CHECK_FILE,
    QualityGate,
    validate_visual_manual_check,
)

MANUAL_CHECK_TEMPLATE = """# 视觉人工复核记录（视觉 API 不可用降级）
approved_by: {approved_by}

## 逐项检查
- [x] 图1 fig_q1：坐标轴名称与单位可读
- [x] 图1 fig_q1：图例完整、不遮挡曲线
- [x] 图2 fig_q2：色盲（红绿色弱）模拟下系列可区分
- [x] 图2 fig_q2：黑白打印下仅靠色相区分的系列有线型冗余
- [x] 图3 tikz_arch：无文字截断与重叠
"""


def _write_manual_check(ws, approved_by: str) -> Path:
    path = ws / VISUAL_MANUAL_CHECK_FILE
    path.write_text(MANUAL_CHECK_TEMPLATE.format(approved_by=approved_by), encoding="utf-8")
    return path


# ---------- 直接校验 validate_visual_manual_check ----------

@pytest.mark.parametrize("signature", [
    "agent", "Agent", "AGENT",
    "AI", "AI审稿机器人",
    "bot", "Bot-1",
    "LLM 审稿",
    "auto", "AUTO审核",
    "机器人", "智能体", "自动审核",
    "GLM-4", "gpt-4o", "GPT4",
    "deepseek-v3", "DeepSeek",
    "SenseNova", "sensenova",
    "claude-3", "gemini-pro", "qwen2.5", "kimi-k2",
    "OpenCode Desktop", "zcode",
])
def test_agent_self_reference_signatures_rejected(tmp_path, signature):
    """agent 自指词/模型名署名 → 一律硬拦，错误信息教学正确写法。"""
    result = validate_visual_manual_check(_write_manual_check(tmp_path, signature))
    assert result["ok"] is False, f"署名 {signature!r} 不应放行: {result}"
    assert "人类操作者" in result["reason"]
    assert "approved_by" in result["reason"]


@pytest.mark.parametrize("signature", [
    "默默", "operator-1", "歆歆", "Zhang San", "Maire Curie", "Rain Li",
])
def test_human_operator_signatures_pass(tmp_path, signature):
    """人类操作者真实署名 → 放行；含 'ai' 等子串的人名不被词边界误伤。"""
    result = validate_visual_manual_check(_write_manual_check(tmp_path, signature))
    assert result["ok"] is True, f"人类署名 {signature!r} 不应被拦: {result}"
    assert result["approved_by"] == signature
    assert result["items"] == 5


def test_boundary_matching_avoids_substring_false_positive(tmp_path):
    """词边界防误伤：said/rain/Baier 含 'ai' 子串但非独立词 → 放行；
    ragent 含 'agent' 子串 → 放行；独立词 agent → 拦截。"""
    for name, expect_ok in (("said", True), ("Rain", True), ("Baier", True),
                            ("ragent", True), ("agent", False)):
        result = validate_visual_manual_check(_write_manual_check(tmp_path, name))
        assert result["ok"] is expect_ok, f"{name!r}: {result}"


# ---------- 经 review 闸的集成路径（check_review_evidence mode=visual） ----------

def _workspace_with_verdict(ws, visual_status="manual_review"):
    (ws / "COMP_REVIEW.md").write_text("# Review", encoding="utf-8")
    (ws / "COMP_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (ws / "VISUAL_REVIEW.md").write_text("# Visual", encoding="utf-8")
    (ws / "VISUAL_REVIEW_VERDICT.json").write_text(
        json.dumps({"findings": [], "fatal_count": 0, "status": visual_status}),
        encoding="utf-8")


def test_gate_blocks_manual_review_signed_by_agent(tmp_path):
    """status=manual_review + approved_by=agent → review 闸硬拦（A7R 实测放行场景反例）。"""
    _workspace_with_verdict(tmp_path)
    _write_manual_check(tmp_path, "AI审稿机器人")
    result = QualityGate(tmp_path).check_review_evidence("visual")
    assert result["ok"] is False
    assert "agent 自指词" in result["reason"]
    assert "人类操作者" in result["reason"]


def test_gate_passes_manual_review_signed_by_human(tmp_path):
    """status=manual_review + 人类署名 → 放行并注记 approved_by。"""
    _workspace_with_verdict(tmp_path)
    _write_manual_check(tmp_path, "默默")
    result = QualityGate(tmp_path).check_review_evidence("visual")
    assert result["ok"] is True, result["reason"]
    assert "approved_by=默默" in result["reason"]
