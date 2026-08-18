import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.template_resolver import resolve_template


CATALOG = {
    "competition": {
        "sub_steps": [
            {"skill_name": "comp-literature", "required_checks": []},
            {"skill_name": "comp-review", "required_checks": []},
            {"skill_name": "comp-consistency", "required_checks": ["consistency"]},
            {"skill_name": "comp-final-audit", "required_checks": ["literature", "review", "consistency"]},
        ]
    }
}


def test_skip_literature_prunes_only_literature_requirement_from_final_audit():
    steps = resolve_template("competition", {"skip_literature": True}, CATALOG)
    final_audit = next(step for step in steps if step["skill_name"] == "comp-final-audit")

    assert "literature" not in final_audit["required_checks"]
    assert final_audit["required_checks"] == ["review", "consistency"]


def test_skip_review_prunes_review_requirement_but_preserves_consistency():
    steps = resolve_template("competition", {"skip_review": True}, CATALOG)
    final_audit = next(step for step in steps if step["skill_name"] == "comp-final-audit")

    assert "review" not in final_audit["required_checks"]
    assert final_audit["required_checks"] == ["literature", "consistency"]
