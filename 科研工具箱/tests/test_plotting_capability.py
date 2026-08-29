# -*- coding: utf-8 -*-
"""科研绘图扩展回归测试（C6）：C1 合同完整性 + 模板有效性 + 溯源注册。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
PLOTTING_SKILLS = [
    "scientific-visualization", "matplotlib", "seaborn", "plotly",
    "figure-spec", "graphviz", "excalidraw-diagram", "infographics",
    "scientific-schematics", "diagram-design",
]
REQUIRED_13 = {
    "capability_id", "name", "domain", "description", "input_contract",
    "output_contract", "status", "associated_skills", "associated_tools",
    "external_dependencies", "high_risk_confirmation", "current_evidence",
    "current_gap",
}


def test_plotting_skills_exist_with_upstream():
    for name in PLOTTING_SKILLS:
        assert (ROOT / "skills" / name / "SKILL.md").is_file(), name
        assert (ROOT / "skills" / name / "references" / "UPSTREAM.md").is_file(), name


def test_upstream_registry_covers_plotting():
    text = (ROOT / "tools" / "check_provenance.py").read_text(encoding="utf-8")
    for name in PLOTTING_SKILLS:
        assert f'"skills" / "{name}"' in text, name


def test_per_skill_c1_contracts_complete():
    catalog = json.loads((REPO / "capabilities" / "catalog.json").read_text(encoding="utf-8"))
    mapped = {}
    for entries in catalog.values():
        for e in entries:
            for s in e.get("associated_skills", []):
                mapped.setdefault(s, e)
    for name in PLOTTING_SKILLS:
        assert name in mapped, f"{name} 未映射到任何能力条目"
        e = mapped[name]
        missing = REQUIRED_13 - set(e.keys())
        assert not missing, f"{name} 合同缺字段: {missing}"


def test_scientific_plotting_template_valid():
    tpl = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    t = tpl["scientific_plotting"]
    assert t["pipeline_skill"] == t["sub_steps"][0]["skill_name"]
    names = [s["skill_name"] for s in t["sub_steps"]]
    assert len(names) == len(set(names)) == 5
    review = t["sub_steps"][-1]
    assert review["metadata"]["requires_subagent"] is True
    assert "review" in review["required_checks"]
    for s in t["sub_steps"][:2]:
        assert "figure_provenance" not in s["required_checks"]  # SVG 步骤不挂位图门禁
    for s in t["sub_steps"][2:4]:
        assert "figure_provenance" in s["required_checks"]  # PNG 步骤强制溯源门禁
