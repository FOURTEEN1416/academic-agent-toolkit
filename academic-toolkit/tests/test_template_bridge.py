"""模板解析与桥接测试（agent-in-the-loop 模式）"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.template_resolver import resolve_template
from engine.opencode_bridge import StepAction, StepResult


def test_cumcm_template_requires_literature_and_review_closure_by_default():
    import json

    catalog = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    skills = [step["skill_name"] for step in resolve_template("comp_cumcm", {}, catalog)]

    assert "comp-literature" in skills
    assert "comp-review" in skills
    assert "comp-visual-review" in skills
    assert "comp-editor" in skills
    assert "comp-final-review" in skills
    assert "comp-final-audit" in skills


def test_cumcm_template_has_14_ordered_executable_stages_and_gate_bindings():
    import json

    catalog = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = resolve_template("comp_cumcm", {}, catalog)

    assert [step["skill_name"] for step in steps] == [
        "comp-prob-analysis", "comp-literature", "comp-modeling", "comp-code",
        "paper-figure", "paper-figure-drawio", "comp-review", "comp-paper-zh",
        "comp-consistency", "comp-compile-zh", "comp-visual-review", "comp-editor",
        "comp-final-review", "comp-final-audit",
    ]
    assert len(steps) == 14
    assert all((ROOT / "skills" / step["skill_name"] / "SKILL.md").is_file() for step in steps)
    assert steps[1]["required_checks"] == ["literature_search", "step_manifest", "citation_integrity"]
    assert steps[2]["required_checks"] == ["step_manifest", "modeling_contract"]
    assert steps[3]["required_checks"] == ["step_manifest"]
    assert steps[4]["required_checks"] == ["figure_provenance"]
    assert steps[7]["required_checks"] == ["literature", "step_manifest", "paper_consistency"]
    assert steps[8]["required_checks"] == ["consistency"]
    assert steps[9]["required_checks"] == ["literature", "consistency", "step_manifest", "compilation_log"]
    assert steps[12]["required_checks"] == ["review"]
    assert steps[13]["required_checks"] == ["literature", "review", "consistency", "final_audit"]


def test_cumcm_template_allows_explicit_literature_and_review_waivers():
    import json

    catalog = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    skills = [step["skill_name"] for step in resolve_template(
        "comp_cumcm", {"skip_literature": True, "skip_review": True}, catalog
    )]

    assert "comp-literature" not in skills
    assert not {"comp-review", "comp-visual-review", "comp-editor", "comp-final-review"} & set(skills)
    assert "comp-final-audit" in skills


def test_cumcm_closure_steps_declare_verdict_and_audit_outputs():
    import json

    catalog = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = {step["skill_name"]: step for step in resolve_template("comp_cumcm", {}, catalog)}

    assert steps["comp-review"]["output_files"] == ["COMP_REVIEW.md", "COMP_REVIEW_VERDICT.json"]
    assert steps["comp-visual-review"]["output_files"] == ["VISUAL_REVIEW.md", "VISUAL_REVIEW_VERDICT.json"]
    assert steps["comp-editor"]["output_files"] == ["EDITOR_CHANGELOG.md"]
    assert steps["comp-final-review"]["output_files"] == [
        "FINAL_REVIEW.md", "FINAL_REVIEW_VERDICT.json", "REVIEW_EXECUTION_EVIDENCE.json"
    ]
    assert steps["comp-final-audit"]["output_files"] == ["AUDIT_REPORT.json"]


def test_resolver_applies_language_and_format_options():
    catalog = {
        "pipeline": {
            "sub_steps": [
                {"skill_name": "paper-write", "output_files": ["paper.md"], "primary_output": "paper.md"},
                {"skill_name": "paper-compile", "output_files": ["paper.pdf"], "primary_output": "paper.pdf"},
            ]
        }
    }
    steps = resolve_template("pipeline", {"language": "zh", "output_format": "docx"}, catalog)
    assert [step["skill_name"] for step in steps] == ["paper-write-zh", "paper-compile", "docx-export"]


def test_resolver_rejects_unknown_template():
    with pytest.raises(KeyError):
        resolve_template("missing", {}, {})


def test_step_action_has_execution_instructions():
    """StepAction 能生成给 agent 的清晰指令。"""
    action = StepAction(
        workflow_id="wf-1",
        step_id="s-1",
        position=1,
        skill_name="comp-prob-analysis",
        display_name="问题分析",
        workspace=Path("/workspace"),
        skill_path=Path("/skills/comp-prob-analysis/SKILL.md"),
        output_files=["PROB_ANALYSIS.md"],
        primary_output="PROB_ANALYSIS.md",
        has_checkpoint=False,
        checkpoint_type=None,
    )
    instructions = action.execution_instructions()
    assert "comp-prob-analysis" in instructions
    assert "PROB_ANALYSIS.md" in instructions
    assert "workspace" in instructions


def test_step_action_checkpoint_instructions():
    """有检查点的步骤，指令中应包含提示。"""
    action = StepAction(
        workflow_id="wf-1", step_id="s-1", position=1,
        skill_name="comp-review", display_name="审查",
        workspace=Path("/ws"), skill_path=Path("/s/SKILL.md"),
        output_files=["review.md"], primary_output="review.md",
        has_checkpoint=True, checkpoint_type="approve",
    )
    instructions = action.execution_instructions()
    assert "批准" in instructions


def test_step_result_construction():
    """StepResult 可正确构造。"""
    result = StepResult(ok=True, stdout="done", artifacts=["out.md"], duration_seconds=1.5)
    assert result.ok is True
    assert result.artifacts == ["out.md"]
    assert result.duration_seconds == 1.5
