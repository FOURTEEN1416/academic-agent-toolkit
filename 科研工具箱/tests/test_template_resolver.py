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


def test_nested_metadata_expands_to_step_top_level():
    """Phase 6 标准：嵌套 metadata 子对象应展开到 step 顶层，供 runner 消费。"""
    catalog = {
        "demo": {
            "sub_steps": [
                {
                    "skill_name": "comp-modeling",
                    "display_name": "建模求解",
                    "metadata": {
                        "requires_subagent": False,
                        "required_checks": ["step_manifest"],
                        "display_name": "建模求解（元数据版）",
                    },
                }
            ]
        }
    }

    steps = resolve_template("demo", {}, catalog)
    step = steps[0]

    assert step["requires_subagent"] is False
    assert step["required_checks"] == ["step_manifest"]
    # 嵌套 metadata 优先于顶层同名字段
    assert step["display_name"] == "建模求解（元数据版）"
    # metadata 键本身保留（审计/溯源用）
    assert step["metadata"]["required_checks"] == ["step_manifest"]


def test_nested_metadata_works_with_skip_literature_pruning():
    """嵌套 metadata 中的 required_checks 也应参与 skip 剪枝。"""
    catalog = {
        "demo": {
            "sub_steps": [
                {
                    "skill_name": "comp-final-audit",
                    "metadata": {
                        "required_checks": ["literature", "review", "final_audit"],
                    },
                }
            ]
        }
    }

    steps = resolve_template("demo", {"skip_literature": True, "skip_review": True}, catalog)
    step = steps[0]

    assert step["required_checks"] == ["final_audit"]
