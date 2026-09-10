"""A7-M5 回归测试：视觉 API 不可用的人工降级路径（manual_review 三态）。

修复前：VISUAL_REVIEW_VERDICT.status ≠ pass 一律 ok=False，视觉 API 挂掉时
第 11 步永久卡死且无预案。修复后新增合法值 manual_review——仅当工作区同时存在
VISUAL_REVIEW_MANUAL_CHECK.md（approved_by 非空 + ≥5 条逐项检查记录）时放行；
status=unavailable 且无该文件维持拦截（静默降级仍然被拦）。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.quality_gates import QualityGate

MANUAL_CHECK = """# 视觉人工复核记录（视觉 API 不可用降级）
approved_by: 默默

## 逐项检查
- [x] 图1 fig_q1：坐标轴名称与单位可读
- [x] 图1 fig_q1：图例完整、不遮挡曲线
- [x] 图2 fig_q2：色盲（红绿色弱）模拟下系列可区分
- [x] 图2 fig_q2：黑白打印下仅靠色相区分的系列有线型冗余
- [x] 图3 tikz_arch：无文字截断与重叠
"""


def _workspace(ws, visual_status):
    (ws / "COMP_REVIEW.md").write_text("# Review", encoding="utf-8")
    (ws / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (ws / "VISUAL_REVIEW.md").write_text("# Visual", encoding="utf-8")
    (ws / "VISUAL_REVIEW_VERDICT.json").write_text(
        json.dumps({"findings": [], "fatal_count": 0, "status": visual_status}), encoding="utf-8")


def test_status_pass_gate_ok(tmp_path):
    """态一：status=pass → 正常放行。"""
    _workspace(tmp_path, "pass")
    result = QualityGate(tmp_path).check_review_evidence("visual")
    assert result["ok"] is True, f"status=pass 应放行: {result}"


def test_status_manual_review_with_valid_manual_check_gate_ok(tmp_path):
    """态二：status=manual_review + 合规人工复核文件 → 放行并注记 manual_review。"""
    _workspace(tmp_path, "manual_review")
    (tmp_path / "VISUAL_REVIEW_MANUAL_CHECK.md").write_text(MANUAL_CHECK, encoding="utf-8")

    result = QualityGate(tmp_path).check_review_evidence("visual")
    assert result["ok"] is True, f"合规人工复核应放行: {result}"
    assert "manual_review" in result["reason"], f"放行结果必须带 manual_review 注记: {result['reason']}"
    assert "approved_by=默默" in result["reason"]


def test_status_manual_review_run_all_ok(tmp_path):
    """run_all（comp-visual-review 技能语义）下 manual_review 同样放行。"""
    _workspace(tmp_path, "manual_review")
    (tmp_path / "VISUAL_REVIEW_MANUAL_CHECK.md").write_text(MANUAL_CHECK, encoding="utf-8")
    result = QualityGate(tmp_path).run_all("comp-visual-review")
    assert result["ok"] is True, json.dumps(result["checks"], ensure_ascii=False)


def test_status_manual_review_without_manual_check_file_blocked(tmp_path):
    """态三反例：manual_review 无人工复核文件 → 硬拦，错误信息含格式教学。"""
    _workspace(tmp_path, "manual_review")
    result = QualityGate(tmp_path).check_review_evidence("visual")
    assert result["ok"] is False
    assert "VISUAL_REVIEW_MANUAL_CHECK.md" in result["reason"]
    assert "approved_by" in result["reason"], "错误信息必须教学正确格式"


def test_manual_check_with_empty_approved_by_blocked(tmp_path):
    """approved_by 为空 → 硬拦（禁止 agent 冒充用户签字）。"""
    _workspace(tmp_path, "manual_review")
    bad = MANUAL_CHECK.replace("approved_by: 默默", "approved_by: ")
    (tmp_path / "VISUAL_REVIEW_MANUAL_CHECK.md").write_text(bad, encoding="utf-8")
    result = QualityGate(tmp_path).check_review_evidence("visual")
    assert result["ok"] is False
    assert "approved_by" in result["reason"]


def test_manual_check_with_fewer_than_five_items_blocked(tmp_path):
    """逐项检查记录 < 5 条 → 硬拦。"""
    _workspace(tmp_path, "manual_review")
    trimmed = MANUAL_CHECK.replace("- [x] 图2 fig_q2：黑白打印下仅靠色相区分的系列有线型冗余\n", "")
    (tmp_path / "VISUAL_REVIEW_MANUAL_CHECK.md").write_text(trimmed, encoding="utf-8")
    result = QualityGate(tmp_path).check_review_evidence("visual")
    assert result["ok"] is False
    assert "逐项检查记录不足" in result["reason"]


def test_status_unavailable_without_manual_check_still_blocked(tmp_path):
    """态三：status=unavailable 且无人工复核文件 → 维持拦截（静默降级被拦）。"""
    _workspace(tmp_path, "unavailable")
    result = QualityGate(tmp_path).check_review_evidence("visual")
    assert result["ok"] is False
    assert "unavailable" in result["reason"]


def test_status_unavailable_ignores_unrelated_manual_file(tmp_path):
    """unavailable 不因人工复核文件存在而放行——放行必须显式写 manual_review。"""
    _workspace(tmp_path, "unavailable")
    (tmp_path / "VISUAL_REVIEW_MANUAL_CHECK.md").write_text(MANUAL_CHECK, encoding="utf-8")
    result = QualityGate(tmp_path).check_review_evidence("visual")
    assert result["ok"] is False
    assert "unavailable" in result["reason"]


def test_status_fail_still_blocked(tmp_path):
    """status=fail（发现视觉问题）→ 维持拦截。"""
    _workspace(tmp_path, "fail")
    result = QualityGate(tmp_path).check_review_evidence("visual")
    assert result["ok"] is False
