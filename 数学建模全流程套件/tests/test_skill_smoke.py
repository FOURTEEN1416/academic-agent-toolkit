"""烟雾测试：验证核心技能路径、SKILL.md 可读性、共享脚本可访问性"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# 核心技能列表（竞赛主线流程 + 论文 + 其他）
CORE_SKILLS = [
    "comp-prob-analysis", "comp-modeling", "comp-code",
    "comp-review", "comp-paper-zh", "comp-paper-en",
    "comp-compile-zh", "comp-compile-en",
    "comp-stats-topic",
    "comp-literature", "comp-consistency", "comp-visual-review",
    "comp-editor", "comp-final-review", "comp-final-audit",
    "paper-write", "paper-write-zh", "paper-write-nature",
    "paper-figure", "paper-figure-html", "paper-figure-drawio", "nature-figure",
    "paper-analysis", "paper-plan-zh",
    "paper-compile", "paper-compile-zh",
    "literature-review", "auto-review-loop",
    # patent-draft/patent-build/copyright-draft/copyright-build: private_extension, 不随公开包分发
    "docx-export",
    "course-paper", "course-report",
    "thesis-proposal",
    "dev-requirement", "dev-design", "dev-report",
    "experiment-bridge",
]


def test_core_skills_exist():
    """所有核心技能目录存在且有 SKILL.md"""
    skills_root = ROOT / "skills"
    missing = []
    for name in CORE_SKILLS:
        skill_dir = skills_root / name
        skill_file = skill_dir / "SKILL.md"
        if not skill_dir.is_dir():
            missing.append(f"{name}/ (dir)")
        elif not skill_file.is_file():
            missing.append(f"{name}/SKILL.md")
    assert not missing, f"Missing core skills:\n" + "\n".join(f"  - {m}" for m in missing)


def test_core_skills_have_content():
    """SKILL.md 至少 500 字节（非空壳）"""
    empty = []
    for name in CORE_SKILLS:
        skill_file = ROOT / "skills" / name / "SKILL.md"
        if skill_file.is_file() and skill_file.stat().st_size < 500:
            empty.append(name)
    assert not empty, f"Empty/too-small SKILL.md: {empty}"


def test_modeling_closure_skills_have_required_frontmatter():
    """数模闭环步骤必须能被 OpenCode 技能扫描器发现。"""
    closure_skills = [
        "comp-literature", "comp-consistency", "comp-visual-review",
        "comp-editor", "comp-final-review", "comp-final-audit",
    ]
    invalid = []
    for name in closure_skills:
        skill_file = ROOT / "skills" / name / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8")
        if not text.startswith("---\n") or "\nname:" not in text or "\ndescription:" not in text:
            invalid.append(name)
    assert not invalid, f"数模闭环技能 frontmatter 无效: {invalid}"


def test_shared_scripts_accessible():
    """共享脚本目录可访问且至少有 50 个文件（含 .py/.sh/.tex/.md）"""
    utils = ROOT / "skills" / "_utils"
    shared = ROOT / "skills" / "shared-scripts"
    assert utils.is_dir(), "_utils 目录不存在"
    assert shared.is_dir(), "shared-scripts 目录不存在"
    all_files = list(utils.iterdir()) + list(shared.iterdir())
    assert len(all_files) >= 50, f"共享脚本不足 ({len(all_files)} < 50)"


def test_template_references_exist():
    """引擎模板中引用的技能都存在"""
    import json
    tpl_file = ROOT / "engine" / "modex-core" / "templates.json"
    if not tpl_file.exists():
        pytest.skip("templates.json 不存在")
    catalog = json.loads(tpl_file.read_text(encoding="utf-8"))
    skills_root = ROOT / "skills"
    missing = []
    for name, tpl in catalog.items():
        for step in tpl.get("sub_steps", []):
            skill_name = step.get("skill_name", "")
            if skill_name and not (skills_root / skill_name).is_dir():
                missing.append(f"模板 {name} 引用 {skill_name}")
    assert not missing, f"模板引用了不存在的技能:\n" + "\n".join(f"  - {m}" for m in missing)


def test_engine_modules_importable():
    """所有引擎模块可导入"""
    import importlib
    modules = [
        "engine.workflow_store", "engine.workflow_runner",
        "engine.opencode_bridge", "engine.template_resolver",
        "engine.runtime_adapter", "engine.artifact_manifest",
        "engine.quality_gates", "engine.env_loader",
    ]
    failed = []
    for mod_name in modules:
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            failed.append(f"{mod_name}: {e}")
    assert not failed, f"模块导入失败:\n" + "\n".join(f"  - {m}" for m in failed)


def test_comp_rules_loaded():
    """竞赛规则可加载"""
    import json
    rules_file = ROOT / "engine" / "modex-core" / "comp_rules.json"
    assert rules_file.exists(), "comp_rules.json 不存在"
    rules = json.loads(rules_file.read_text(encoding="utf-8"))
    assert len(rules) >= 20, f"竞赛规则不足 ({len(rules)} < 20)"


def test_quality_gates_config_loaded():
    """质量门禁配置可加载"""
    import json
    gates_file = ROOT / "engine" / "modex-core" / "quality_gates.json"
    assert gates_file.exists(), "quality_gates.json 不存在"
    gates = json.loads(gates_file.read_text(encoding="utf-8"))
    assert "_STEP_MIN_SIZE" in gates, "缺少 _STEP_MIN_SIZE"
    assert len(gates["_STEP_MIN_SIZE"]) >= 40, f"技能阈值不足 ({len(gates['_STEP_MIN_SIZE'])} < 40)"


def test_tools_importable():
    """关键工具脚本可导入"""
    import importlib
    tools = [
        "tools.reviewer_client", "tools.gpt_image",
        "tools.citation_checker", "tools.score",
        "tools.scholar_fetch", "tools.timeline_96h",
        "tools.skill_test", "tools.watchdog",
    ]
    failed = []
    for mod_name in tools:
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            failed.append(f"{mod_name}: {e}")
    assert not failed, f"工具导入失败:\n" + "\n".join(f"  - {m}" for m in failed)
