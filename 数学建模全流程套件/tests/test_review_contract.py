import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_cumcm_final_review_declares_review_execution_evidence():
    templates = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = templates["comp_cumcm"]["sub_steps"]
    final_review = next(step for step in steps if step["skill_name"] == "comp-final-review")

    assert "REVIEW_EXECUTION_EVIDENCE.json" in final_review["output_files"]


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1].parent / '.opencode' / 'agents').exists(), reason='宿主 agent 配置不随套件分发')
def test_read_only_reviewer_agents_delegate_evidence_writing_to_primary_agent():
    agents_dir = ROOT.parent / ".opencode" / "agents"

    for name in ("数模审稿人.md", "数模视觉审查.md"):
        content = (agents_dir / name).read_text(encoding="utf-8")
        assert "edit: deny" in content
        assert "主 Agent" in content
        assert "不直接写入工作区文件" in content
