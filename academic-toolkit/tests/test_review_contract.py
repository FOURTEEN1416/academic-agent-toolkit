import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cumcm_final_review_declares_review_execution_evidence():
    templates = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = templates["comp_cumcm"]["sub_steps"]
    final_review = next(step for step in steps if step["skill_name"] == "comp-final-review")

    assert "REVIEW_EXECUTION_EVIDENCE.json" in final_review["output_files"]


def test_read_only_reviewer_subagents_delegate_evidence_writing_to_primary_agent():
    """只读审稿角色契约（2026-09-23 起角色定义内联于 opencode.json，
    原 .opencode/agents/*.md 已随宿主适配层移除）：审稿人/视觉审查 edit=deny
    且描述声明只读，证据落盘由主 Agent 承担。"""
    config = json.loads((ROOT.parent / "opencode.json").read_text(encoding="utf-8"))

    for name in ("数模审稿人", "数模视觉审查"):
        agent = config["agent"][name]
        assert agent["permission"]["edit"] == "deny"
        assert "只读" in agent["description"]
        assert agent["mode"] == "subagent"
