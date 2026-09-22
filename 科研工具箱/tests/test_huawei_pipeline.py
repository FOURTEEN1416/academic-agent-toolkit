"""华为杯（comp_huawei）14 步管线升级回归（2026-09-22，8 步裸流程补齐至与国赛同构）。

此前 comp_huawei 仅 8 步（缺文献/一致性/视觉审查/编辑/终审/交付审计六步），
companion_skills 资产与产出规格大多为空，且 comp-paper-zh 华为杯分支
`cp _templates/huawei/*` 因目录缺失静默空转。本文件钉死升级后的合同面，
防止模板编辑把华为杯悄悄退回裸流程（棘轮口径：缩减须显式改本测试）。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "tools"))

TEMPLATES = json.loads(
    (ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))


def _hw_steps():
    return TEMPLATES["comp_huawei"]["sub_steps"]


def test_huawei_pipeline_has_14_steps_aligned_to_cumcm():
    """步数与技能链与国赛逐步一致（华为杯与国赛共用中文竞赛主链）。"""
    hw = _hw_steps()
    cum = TEMPLATES["comp_cumcm"]["sub_steps"]
    assert len(hw) == 14
    assert [s["skill_name"] for s in hw] == [s["skill_name"] for s in cum]


def test_huawei_companions_match_cumcm():
    """companion_skills 与国赛同款 12 槽位（地图 §七 口径）——
    华为杯执行者拿到的辅助技能推荐不得少于国赛。"""
    hw = {s["skill_name"]: s for s in _hw_steps()}
    cum = {s["skill_name"]: s for s in TEMPLATES["comp_cumcm"]["sub_steps"]}
    for skill, cum_step in cum.items():
        expected = cum_step["metadata"].get("companion_skills") or []
        actual = hw[skill]["metadata"].get("companion_skills") or []
        assert actual == expected, f"{skill}: 华为杯={actual} 国赛={expected}"


def test_huawei_output_specs_match_cumcm():
    """产出规格（D7/P5 退出判据）与国赛逐步同款——拦薄产物门禁不得缺位。"""
    hw = {s["skill_name"]: s for s in _hw_steps()}
    cum = {s["skill_name"]: s for s in TEMPLATES["comp_cumcm"]["sub_steps"]}
    for skill, cum_step in cum.items():
        expected = cum_step["metadata"].get("output_specs") or {}
        actual = hw[skill]["metadata"].get("output_specs") or {}
        assert actual == expected, f"{skill}: 华为杯={sorted(actual)} 国赛={sorted(expected)}"


def test_huawei_steps_carry_expected_assets():
    """资产挂载不薄于国赛（华为杯 S5/S6 另挂图表配比基准；S13 审计去国赛专属指针）。"""
    hw = _hw_steps()
    cum = TEMPLATES["comp_cumcm"]["sub_steps"]
    for i, (h, c) in enumerate(zip(hw, cum), 1):
        h_assets = h["metadata"].get("assets") or []
        c_assets = c["metadata"].get("assets") or []
        assert len(h_assets) >= len(c_assets) - 1, (
            f"第 {i} 步 {h['skill_name']}: 华为杯 {len(h_assets)} 资产 < 国赛 {len(c_assets)} - 容差")
        for a in h_assets:
            assert a.get("name") and a.get("path"), h["skill_name"]
    for i in (4, 5):  # S5 图表 / S6 架构图（0 起计）
        names = {a["name"] for a in hw[i]["metadata"]["assets"]}
        assert "华为杯图表配比基准" in names, f"S{i+1} 缺图表配比基准"
    audit_paths = {a["path"] for a in hw[13]["metadata"]["assets"]}
    assert "CUMCM2026Problems/规则与合规" not in audit_paths, "国赛专属指针不得出现在华为杯"


def test_huawei_quick_gates_page_budget():
    """D3 快检页上限必须覆盖为 50（quick_gates.py 默认 30 是 CUMCM 口径，
    不参数化会把 50 页正文误判 FAIL）。"""
    for i, s in enumerate(_hw_steps(), 1):
        md = s["metadata"]
        if md.get("quick_gates"):
            assert md.get("quick_gates_max_pages") == 50, f"S{i} 页上限必须为 50"
    mounted = [s["skill_name"] for s in _hw_steps() if s["metadata"].get("quick_gates")]
    assert mounted == ["paper-figure", "comp-paper-zh"], mounted


def test_huawei_assets_all_exist():
    """华为杯 14 步资产指针逐一在位（公开 clone 缺 gitignored 私有资料区时 skip）。"""
    reason = None
    for name in ("参考论文", "参考图", "CUMCM论文模板"):
        if not (ROOT.parent / name).exists():
            reason = f"非完整本地仓（缺 gitignored 私有资料区 {name}）"
            break
    if reason:
        import pytest
        pytest.skip(reason)
    import check_asset_utilization as cau
    import tempfile
    tpl = {"comp_huawei": TEMPLATES["comp_huawei"]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(tpl, f, ensure_ascii=False)
        tmp = f.name
    res = cau.check_template_assets(Path(tmp), ROOT.parent)
    assert res.get("error") is None, res
    assert res["missing"] == [], f"华为杯失联资产指针: {res['missing']}"


def test_huawei_latex_template_vendored():
    """gmcmthesis 模板入库（修复 comp-paper-zh 华为杯分支空转断链）。"""
    base = ROOT / "skills" / "comp-paper-zh" / "_templates" / "huawei"
    assert (base / "gmcmthesis.cls").is_file()
    assert (base / "main.tex").is_file()
    main_tex = (base / "main.tex").read_text(encoding="utf-8")
    assert r"\documentclass" in main_tex and "gmcmthesis" in main_tex


def test_huawei_stepaction_renders_max_pages_flag():
    """StepAction 渲染 --max-pages 50；未声明时保持无旗标（默认 30 兼容 CUMCM）。"""
    from agent_bridge import StepAction
    base = dict(workflow_id="wf", step_id="s", position=1, skill_name="paper-figure",
                display_name="图表生成", workspace=Path("."), skill_path=Path("x"),
                output_files=[], primary_output="", has_checkpoint=False,
                checkpoint_type=None, quick_gates=True)
    hw = StepAction(quick_gates_max_pages=50, **base)
    cum = StepAction(**base)
    assert "--max-pages 50" in hw.execution_instructions()
    assert "--max-pages" not in cum.execution_instructions()


def test_huawei_catalog_entry_present():
    """catalog 聚合条目在册且带合同扩展字段（公开交付口径）。"""
    catalog = json.loads(
        (ROOT.parent / "capabilities" / "catalog.json").read_text(encoding="utf-8"))
    entry = next((it for it in catalog["math_modeling_competition"]
                  if it["capability_id"] == "comp_huawei_full_pipeline"), None)
    assert entry is not None, "catalog 缺 comp_huawei_full_pipeline"
    for field in ("associated_tools", "external_dependencies",
                  "current_evidence", "current_gap"):
        assert entry.get(field), f"扩展字段 {field} 为空"


def test_huawei_section_in_skill_map():
    """CONTEST_SKILL_MAP §七 特化差异表在册（页数/图表量/模板三要素）。"""
    map_text = (ROOT / "CONTEST_SKILL_MAP.md").read_text(encoding="utf-8")
    section = map_text.split("## 七、")[1] if "## 七、" in map_text else ""
    assert section, "缺 §七 华为杯管线对照"
    for token in ("--max-pages 50", "30-46", "gmcmthesis"):
        assert token in section, f"§七 缺 {token}"
