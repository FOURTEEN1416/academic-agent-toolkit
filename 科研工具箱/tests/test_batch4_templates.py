"""批次四（产品能力补齐）模板契约回归。

覆盖 2026-09-22 第五轮批次四新增：
- academic_outputs：paper-poster → paper-slides → latex-document 三步管线；
- course_teaching：课程论文线 → 课程报告线 → docx 双导出五步管线；
- auto_review：required_checks 补 step_manifest + review 门禁豁免 note。

契约来源（改动前逐条核实过引擎实现）：
- 每步 required_checks 名称必须在 NAMED_CHECKS_REGISTRY（防名称漂移）；
- 每步必须嵌套 metadata（Phase 6 标准，test_template_upgrade_idempotent 同款）；
- 步骤技能目录必须实存（防模板引用幽灵技能）；
- 编译类产物走 output_specs 下限（compilation_log 候选路径不含 poster/、slides/ 子目录）；
- course_teaching 分段链序：论文线正文必须先于报告线规划落盘（OUTLINE.md/PAPER_PLAN.md
  同名覆盖是技能产物名硬编码所致，链序是唯一防踩踏手段）。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEMPLATES = ROOT / "engine" / "modex-core" / "templates.json"
SKILLS = ROOT / "skills"


@pytest.fixture(scope="module")
def catalog() -> dict:
    return json.loads(TEMPLATES.read_text(encoding="utf-8"))


def _steps(catalog: dict, template: str) -> list[dict]:
    assert template in catalog, f"缺少模板 {template}"
    return catalog[template]["sub_steps"]


def _skill_dir(skill_name: str) -> Path:
    return SKILLS / skill_name / "SKILL.md"


class TestAcademicOutputs:
    def test_three_step_chain_order(self, catalog):
        steps = _steps(catalog, "academic_outputs")
        assert [s["skill_name"] for s in steps] == [
            "paper-poster", "paper-slides", "latex-document",
        ]

    def test_all_steps_have_metadata_and_registered_checks(self, catalog):
        from engine.quality_gates import NAMED_CHECKS_REGISTRY

        for step in _steps(catalog, "academic_outputs"):
            assert isinstance(step.get("metadata"), dict)
            checks = step.get("required_checks")
            assert checks, f"{step['skill_name']} 不得零 required_checks（auto_review 空缺不得复制）"
            unknown = set(checks) - set(NAMED_CHECKS_REGISTRY)
            assert not unknown, f"{step['skill_name']} 引用未注册门禁: {unknown}"

    def test_skills_exist_on_disk(self, catalog):
        for step in _steps(catalog, "academic_outputs"):
            assert _skill_dir(step["skill_name"]).is_file(), (
                f"模板引用了不存在的技能: {step['skill_name']}")

    def test_compiled_outputs_guarded_by_output_specs(self, catalog):
        """compilation_log 候选路径不含 poster/、slides/ 子目录 → PDF 下限必须由
        output_specs 承载（对齐技能内置 ≥50000B 的 Output Verification 契约）。"""
        specs_by_step = {
            s["skill_name"]: (s["metadata"].get("output_specs") or {})
            for s in _steps(catalog, "academic_outputs")
        }
        for skill, spec_file in (("paper-poster", "poster/main.pdf"),
                                 ("paper-slides", "slides/main.pdf")):
            spec = specs_by_step[skill].get(spec_file)
            assert spec is not None, f"{skill} 缺 {spec_file} 的 output_specs"
            assert int(spec.get("min_bytes", 0)) >= 50000

    def test_poster_step_has_approve_checkpoint(self, catalog):
        poster = _steps(catalog, "academic_outputs")[0]
        assert poster["has_checkpoint"] is True
        assert poster["checkpoint_type"] == "approve"

    def test_binding_main_required(self, catalog):
        for step in _steps(catalog, "academic_outputs"):
            binding = step["metadata"].get("skill_binding") or {}
            assert binding.get("main_required") is True


class TestCourseTeaching:
    def test_five_step_staged_chain(self, catalog):
        steps = _steps(catalog, "course_teaching")
        assert [s["skill_name"] for s in steps] == [
            "course-plan", "course-paper", "course-report-plan",
            "course-report", "docx-export",
        ]

    def test_paper_line_completes_before_report_plan_overwrites(self, catalog):
        """course-report-plan 会覆盖论文线的 OUTLINE.md/PAPER_PLAN.md（技能产物名
        硬编码）；course-paper 必须排在它之前，否则论文线输入被踩。"""
        names = [s["skill_name"] for s in _steps(catalog, "course_teaching")]
        assert names.index("course-paper") < names.index("course-report-plan")

    def test_all_steps_have_metadata_and_registered_checks(self, catalog):
        from engine.quality_gates import NAMED_CHECKS_REGISTRY

        for step in _steps(catalog, "course_teaching"):
            assert isinstance(step.get("metadata"), dict)
            checks = step.get("required_checks")
            assert checks, f"{step['skill_name']} 不得零 required_checks"
            unknown = set(checks) - set(NAMED_CHECKS_REGISTRY)
            assert not unknown, f"{step['skill_name']} 引用未注册门禁: {unknown}"

    def test_skills_exist_on_disk(self, catalog):
        for step in _steps(catalog, "course_teaching"):
            assert _skill_dir(step["skill_name"]).is_file(), (
                f"模板引用了不存在的技能: {step['skill_name']}")

    def test_plan_specs_match_skill_contract(self, catalog):
        """output_specs 下限与技能完成铁律对齐：
        course-plan OUTLINE≥800B/PAPER_PLAN≥1KB；course-report-plan FACTS≥300B。"""
        specs = {
            s["skill_name"]: (s["metadata"].get("output_specs") or {})
            for s in _steps(catalog, "course_teaching")
        }
        assert specs["course-plan"]["OUTLINE.md"]["min_bytes"] >= 800
        assert specs["course-plan"]["PAPER_PLAN.md"]["min_bytes"] >= 1024
        assert specs["course-report-plan"]["PROJECT_FACTS.md"]["min_bytes"] >= 300

    def test_overwrite_note_present(self, catalog):
        report_plan = next(s for s in _steps(catalog, "course_teaching")
                           if s["skill_name"] == "course-report-plan")
        note = report_plan["metadata"].get("note", "")
        assert "覆盖" in note, "报告线规划步必须注明 OUTLINE/PAPER_PLAN 覆盖行为"

    def test_checkpoints_follow_house_style(self, catalog):
        """规划步 approve、正文步 feedback、导出步无检查点（与 course_paper/course_report
        既有模板同款）。"""
        by_skill = {s["skill_name"]: s for s in _steps(catalog, "course_teaching")}
        assert by_skill["course-plan"]["checkpoint_type"] == "approve"
        assert by_skill["course-paper"]["checkpoint_type"] == "feedback"
        assert by_skill["course-report-plan"]["checkpoint_type"] == "approve"
        assert by_skill["course-report"]["checkpoint_type"] == "feedback"
        assert by_skill["docx-export"]["has_checkpoint"] is False


class TestAutoReviewPatch:
    def test_step_manifest_declared(self, catalog):
        step = _steps(catalog, "auto_review")[0]
        assert step["required_checks"] == ["step_manifest"]
        assert step["metadata"]["required_checks"] == ["step_manifest"]

    def test_review_gate_exemption_note(self, catalog):
        note = _steps(catalog, "auto_review")[0]["metadata"].get("note", "")
        assert "review" in note and "豁免" in note


class TestGlobalInvariants:
    def test_no_duplicate_template_ids(self, catalog):
        # JSON 对象键天然唯一；此断言锁定"44→46 只增不重"的收编口径
        assert len(catalog) == 46

    def test_new_templates_resolve(self, catalog):
        from engine.template_resolver import resolve_template

        for name in ("academic_outputs", "course_teaching"):
            steps = resolve_template(name, {}, catalog)
            assert steps, f"{name} 解析为空"
            # skip_<skill_name> 通用跳过机制对新模板生效
            pruned = resolve_template(
                "academic_outputs", {"skip_paper-slides": True}, catalog)
            assert "paper-slides" not in [s["skill_name"] for s in pruned]
