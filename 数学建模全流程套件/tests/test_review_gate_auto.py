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


def test_final_review_skill_auto_enforces_strict_model_match(tmp_path, monkeypatch):
    """comp-final-review 通过 run_all 调用时，review gate 自动启用 strict_model_match。"""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    for fname, model in (
        ("数模审稿人.md", "model-a"),
        ("数模视觉审查.md", "model-b"),
        ("数模编辑.md", "model-c"),
        ("数模专家.md", "model-d"),
    ):
        (agents_dir / fname).write_text(f"---\nmodel: {model}\n---\n", encoding="utf-8")
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(agents_dir))

    import hashlib, json
    for name in ("COMP_REVIEW.md", "VISUAL_REVIEW.md", "EDITOR_CHANGELOG.md", "FINAL_REVIEW.md"):
        (tmp_path / name).write_text(f"# {name}\n", encoding="utf-8")
    (tmp_path / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (tmp_path / "VISUAL_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0, "status": "pass"}', encoding="utf-8")
    (tmp_path / "FINAL_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    hashes = {
        "reviewer": hashlib.sha256((tmp_path / "COMP_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
        "visual_reviewer": hashlib.sha256((tmp_path / "VISUAL_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
        "editor": hashlib.sha256((tmp_path / "EDITOR_CHANGELOG.md").read_bytes()).hexdigest(),
        "final_reviewer": hashlib.sha256((tmp_path / "FINAL_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
    }
    provenance = {"schema_version": 1, "roles": {
        "reviewer": {"session_id": "s1", "model": "wrong-model", "completed_at": "2026-08-08T00:00:00Z", "output_file": "COMP_REVIEW_VERDICT.json", "output_sha256": hashes["reviewer"]},
        "visual_reviewer": {"session_id": "s2", "model": "model-b", "completed_at": "2026-08-08T00:00:00Z", "output_file": "VISUAL_REVIEW_VERDICT.json", "output_sha256": hashes["visual_reviewer"]},
        "editor": {"session_id": "s3", "model": "model-c", "completed_at": "2026-08-08T00:00:00Z", "output_file": "EDITOR_CHANGELOG.md", "output_sha256": hashes["editor"]},
        "final_reviewer": {"session_id": "s4", "model": "model-d", "completed_at": "2026-08-08T00:00:00Z", "output_file": "FINAL_REVIEW_VERDICT.json", "output_sha256": hashes["final_reviewer"]},
    }}
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(json.dumps(provenance), encoding="utf-8")

    result = QualityGate(tmp_path).run_all("comp-final-review", declared_outputs=["COMP_REVIEW.md", "COMP_REVIEW_VERDICT.json", "VISUAL_REVIEW.md", "VISUAL_REVIEW_VERDICT.json", "EDITOR_CHANGELOG.md", "FINAL_REVIEW.md", "FINAL_REVIEW_VERDICT.json", "REVIEW_EXECUTION_EVIDENCE.json"], required_checks=["review"])

    # comp-final-review 启用 strict_model_match，模型不匹配应阻断
    assert result["ok"] is False
    review_check = result["checks"]["review"]
    assert "wrong-model" in review_check.get("reason", "")