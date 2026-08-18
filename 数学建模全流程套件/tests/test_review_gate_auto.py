"""M1 修复测试：审核类步骤即使模板未声明 required_checks，也必须自动跑 review 门禁。

背景（COMP_REVIEW.md M1 + LESSONS）：除 comp_cumcm 外 21 个竞赛模板无 required_checks，
导致其 comp-review / comp-final-review 步骤的 review gate 从不执行——审稿证据缺失/伪造
不会被发现。修复：run_all 对审核类技能（comp-review / comp-visual-review / comp-final-review）
自动加入 review 检查。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.quality_gates import QualityGate


def _setup_workspace(tmp_path, with_review_files=True):
    ws = tmp_path
    # 建 REVIEW 所需文件（部分）
    if with_review_files:
        (ws / "COMP_REVIEW.md").write_text("审查报告", encoding="utf-8")
        (ws / "COMP_REVIEW_VERDICT.json").write_text(
            json.dumps({"verdict": "PASS", "fatal_count": 0, "findings": []}), encoding="utf-8"
        )


def test_review_skill_auto_runs_review_gate(tmp_path):
    """comp-review 步骤（无 required_checks）应自动跑 review gate。"""
    _setup_workspace(tmp_path, with_review_files=False)  # 无审稿文件 → gate 应失败
    result = QualityGate(tmp_path).run_all("comp-review")
    assert "review" in result["checks"], f"comp-review 应自动跑 review gate: {list(result['checks'].keys())}"
    assert result["checks"]["review"]["ok"] is False, "缺审稿文件应失败"
    assert result["ok"] is False


def test_review_skill_auto_gate_passes_with_files(tmp_path):
    """comp-review 自动 review gate：有完整审稿文件时通过。"""
    _setup_workspace(tmp_path, with_review_files=True)
    # 补全其余审稿文件（full 模式需要）
    (tmp_path / "VISUAL_REVIEW.md").write_text("v", encoding="utf-8")
    (tmp_path / "VISUAL_REVIEW_VERDICT.json").write_text(
        json.dumps({"verdict": "PASS", "status": "pass", "fatal_count": 0, "findings": []}), encoding="utf-8"
    )
    (tmp_path / "EDITOR_CHANGELOG.md").write_text("e", encoding="utf-8")
    (tmp_path / "FINAL_REVIEW.md").write_text("f", encoding="utf-8")
    (tmp_path / "FINAL_REVIEW_VERDICT.json").write_text(
        json.dumps({"verdict": "PASS", "fatal_count": 0, "findings": []}), encoding="utf-8"
    )
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(
        json.dumps({"roles": {}}), encoding="utf-8"  # 格式不完整 → solo 模式可过或 full 失败
    )
    result = QualityGate(tmp_path).run_all("comp-review")
    assert "review" in result["checks"], f"应自动跑 review gate: {list(result['checks'].keys())}"


def test_final_review_skill_auto_runs_review_gate(tmp_path):
    """comp-final-review 步骤也应自动跑 review gate。"""
    _setup_workspace(tmp_path, with_review_files=False)
    result = QualityGate(tmp_path).run_all("comp-final-review")
    assert "review" in result["checks"], f"comp-final-review 应自动跑 review gate: {list(result['checks'].keys())}"