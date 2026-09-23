"""check_asset_utilization 工具回归 + 资产机制配套契约（2026-09-12 资产缺口研究落地）。

守护三件事：
  1. 工具本身：斜杠缩写展开 / 地图对账 / 账本扫描 / 死推荐 / 模板资产在位；
  2. 真仓零漏网：CONTEST_SKILL_MAP 对 255 实存技能覆盖必须为 0 漏网（机检固化）；
  3. 真仓假接线防线：templates.json 全模板 assets 指针必须存在 + step5 companion
     漂移回归（eco-community-plots / figure-aesthetics-craft 曾"地图在册引擎不荐"）。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import check_asset_utilization as cau


# 公开 clone 不交付的两类本地资产（均被根 .gitignore 隔离）：
#   1) 无 License 上游技能（侵权红线隔离，5 个）
#   2) 私有资料区 assets-local/（award-papers / reference-figures / cumcm-templates）
#      与赛时预置区 CUMCM2026Problems（2026-09-23 v2.0 改造统一布局）
# 下两条"真仓机检"以**完整本地仓**为前提，在公开 clone（含 CI）上必须 skip 而非 fail
# ——2026-09-19 首次 CI 实测发现（本地 node/资产常驻故从未暴露）。
LOCAL_ONLY_SKILLS = (
    "plot-from-data", "plot-from-image", "visio-image-rebuilder",
    "paper-framework-figure-studio-pro", "eco-community-plots",
)
LOCAL_ASSET_ROOTS = ("assets-local", "CUMCM2026Problems")


def _skip_reason_without_local_assets():
    """返回非完整本地仓的缺件说明；完整仓返回 None。"""
    missing_skills = [n for n in LOCAL_ONLY_SKILLS
                      if not (ROOT / "skills" / n / "SKILL.md").exists()]
    missing_assets = [n for n in LOCAL_ASSET_ROOTS if not (ROOT.parent / n).exists()]
    if not missing_skills and not missing_assets:
        return None
    parts = []
    if missing_skills:
        parts.append(f"{len(missing_skills)} 个 gitignored 无 License 技能 {missing_skills}")
    if missing_assets:
        parts.append(f"{len(missing_assets)} 个 gitignored 私有资料区 {missing_assets}")
    return "非完整本地仓（公开 clone / CI）缺 " + "；缺 ".join(parts)


# ---------- 斜杠缩写展开 ----------

def test_expand_slash_groups_family():
    text = "知识产权（5） | copyright-build/draft/source-materials, patent-build/draft | 理由"
    expanded = cau._expand_slash_groups(text)
    for name in ("copyright-build", "copyright-draft", "copyright-source-materials",
                 "patent-build", "patent-draft"):
        assert name in expanded, name


def test_expand_slash_groups_single_segment():
    assert "patent-draft" in cau._expand_slash_groups("patent-build/draft")


def test_expand_slash_groups_leaves_plain_text():
    assert cau._expand_slash_groups("no slash here, 中文/路径 不动") == \
        "no slash here, 中文/路径 不动"


# ---------- 地图对账 ----------

def test_load_map_coverage_explicit_slash_prefix(tmp_path):
    skills = ["alpha-one", "alpha-two", "beta", "gamma-sub-x", "delta"]
    (tmp_path / "skills").mkdir()
    (tmp_path / "CONTEST_SKILL_MAP.md").write_text(
        "## 一\n`beta` 主链\n## 四\n| 前缀 | alpha-one/two, delta | 理由 |\n"
        "前缀域：`gamma-*`\n", encoding="utf-8")
    cov = cau.load_map_coverage(tmp_path / "CONTEST_SKILL_MAP.md", skills)
    assert cov["missing"] == []
    assert set(cov["covered"]) == set(skills)


def test_load_map_coverage_reports_missing(tmp_path):
    (tmp_path / "CONTEST_SKILL_MAP.md").write_text("`known` 在册\n", encoding="utf-8")
    cov = cau.load_map_coverage(tmp_path / "CONTEST_SKILL_MAP.md", ["known", "orphan"])
    assert cov["missing"] == ["orphan"]


def test_real_map_covers_all_skills_zero_missing():
    """真仓零漏网机检（CONTEST_SKILL_MAP §六 口径的固化版）：255 实存 / 0 漏网。"""
    reason = _skip_reason_without_local_assets()
    if reason:
        pytest.skip(reason)
    skills = cau.iter_skill_dirs(ROOT / "skills")
    cov = cau.load_map_coverage(ROOT / "CONTEST_SKILL_MAP.md", skills)
    assert cov["missing"] == [], f"漏网技能: {cov['missing']}"
    assert len(skills) >= 255


def test_iter_skill_dirs_excludes_non_skill_dirs(tmp_path):
    for name in ("real-skill", "_utils", "shared-scripts"):
        (tmp_path / name).mkdir()
    (tmp_path / "real-skill" / "SKILL.md").write_text("x", encoding="utf-8")
    (tmp_path / "_utils" / "SKILL.md").write_text("x", encoding="utf-8")
    assert cau.iter_skill_dirs(tmp_path) == ["real-skill"]


# ---------- 账本扫描 ----------

def _write_evidence(ws: Path, fname: str, companion, assets, skill="comp-code"):
    ev_dir = ws / ".engine" / "evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    (ev_dir / fname).write_text(json.dumps({
        "action": {"skill_name": skill},
        "evidence": {"skill_name": skill, "companion_skills": companion, "assets": assets},
        "manifest": {},
        "schema_version": 1,
    }, ensure_ascii=False), encoding="utf-8")


def test_scan_evidence_wrapped_structure_and_stats(tmp_path):
    ws = tmp_path / "wsA"
    _write_evidence(ws, "a.json",
                    {"used": ["citation-check"], "skipped": [{"skill": "paper-search", "reason": "r"}]},
                    {"used": ["引用核验器"],
                     "skipped": [{"name": "参考图集", "reason": "不产图"}]},
                    skill="comp-literature")
    _write_evidence(ws, "b.json",
                    {"used": [], "skipped": [{"skill": "meta-design-space-exploration", "reason": "r"}]}, None)
    result = cau.scan_evidence(tmp_path)
    assert result["totals"]["steps_declared"] == 2
    assert result["totals"]["used"] == 2
    assert result["totals"]["skipped"] == 3
    assert result["companion"]["citation-check"] == {"recommended": 1, "used": 1, "skipped": 0}
    assert result["companion"]["meta-design-space-exploration"]["used"] == 0
    assert result["assets"]["引用核验器"]["used"] == 1
    assert result["assets"]["参考图集"]["skipped"] == 1


def test_dead_recommendations_ordering():
    stats = {"a": {"recommended": 3, "used": 0, "skipped": 3},
             "b": {"recommended": 1, "used": 1, "skipped": 0},
             "c": {"recommended": 2, "used": 0, "skipped": 2}}
    dead = cau.dead_recommendations(stats)
    assert [d["skill"] for d in dead] == ["a", "c"]


# ---------- 模板资产在位（真仓假接线防线） ----------

def test_real_templates_assets_all_exist():
    reason = _skip_reason_without_local_assets()
    if reason:
        pytest.skip(reason)
    tpl = cau.check_template_assets(ROOT / "engine" / "modex-core" / "templates.json", ROOT.parents[0])
    assert tpl.get("error") is None
    assert tpl["checked"] >= 23
    assert tpl["missing"] == [], f"失联资产指针: {tpl['missing']}"


def test_check_template_assets_detects_missing(tmp_path):
    tpl_data = {"demo": {"sub_steps": [{"skill_name": "x", "metadata": {"assets": [
        {"name": "失联资产", "path": "不存在的路径/asset.md", "note": ""}]}}]}}
    tpl_file = tmp_path / "templates.json"
    tpl_file.write_text(json.dumps(tpl_data, ensure_ascii=False), encoding="utf-8")
    result = cau.check_template_assets(tpl_file, tmp_path)
    assert result["checked"] == 1
    assert len(result["missing"]) == 1
    assert result["missing"][0]["asset"] == "失联资产"


# ---------- companion 修剪定案钉死 + 地图↔引擎同步 ----------

def test_comp_cumcm_companion_lists_compact():
    """推荐槽位紧缩度存证：2026-09-12 修剪定案 54→11，仅保留合同互补位
    （CR/NA/Dup/ST 分类见 LOG 续20/21 与地图 §二修剪注）；
    2026-09-19 P4 技能绑定落地时为 step5 补入必用位 `paper-figure-palette`
    （配色统一注册表，色值不得自创）→ 11→12。"""
    data = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = {s["skill_name"]: s for s in data["comp_cumcm"]["sub_steps"]}
    expected = {
        "comp-problem-analysis": [],
        "comp-literature": ["citation-check"],
        "comp-modeling": ["sympy"],
        "comp-code": ["data-statistics-report"],
        "paper-figure": ["figure-aesthetics-craft", "paper-figure-palette"],
        "paper-figure-drawio": [],
        "comp-review": [],
        "comp-paper-zh": [],
        "comp-consistency": ["analyze-results"],
        "comp-compile-zh": [],
        "comp-visual-review": ["fig-critique", "figure-spec"],
        "comp-editor": ["anti-defensive-writing"],
        "comp-final-review": ["paper-self-review"],
        "comp-final-audit": ["citation-check", "quality-check"],
    }
    for skill, comp in expected.items():
        assert steps[skill]["metadata"]["companion_skills"] == comp, skill
    assert sum(len(c) for c in expected.values()) == 12


def test_map_section2_matches_engine_companions():
    """地图 §二 表格与引擎 templates.json companion 集合逐步一致——
    杀死"地图在册、StepAction 不荐"漂移类（eco/figure-aesthetics-craft 曾死信）。"""
    map_text = (ROOT / "CONTEST_SKILL_MAP.md").read_text(encoding="utf-8")
    section = map_text.split("## 二、")[1].split("## 三、")[0]
    rows = {}
    for line in section.splitlines():
        if not line.startswith("| ") or "步骤 |" in line or "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        raw = cells[1]
        if raw.startswith("（"):
            rows[cells[0]] = set()
        else:
            rows[cells[0]] = {s.strip() for s in raw.split(",") if s.strip()}
    assert len(rows) == 14, f"§二 行数异常: {len(rows)}"

    data = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = data["comp_cumcm"]["sub_steps"]
    order = ["1 赛题分析", "2 文献", "3 建模", "4 编程", "5 图表", "6 架构图", "7 逻辑复核",
             "8 论文", "9 一致性", "10 编译", "11 视觉审查", "12 编辑", "13 终审", "14 交付审计"]
    for i, s in enumerate(steps):
        engine_set = set(s["metadata"].get("companion_skills") or [])
        assert rows[order[i]] == engine_set, f"第 {i+1} 步 {s['skill_name']}: 地图={rows[order[i]]} 引擎={engine_set}"


def test_comp_cumcm_steps_carry_expected_assets():
    """14 步中 12 步带非空 assets（S4/S12 有意不设），且每条含 name/path/note。

    计数演进：原始 10 步（S4/S7/S12/S13 不设）→ 2026-09-19 P5 为 S7（逻辑复核）与
    S13（终审）挂上「反合理化表」（跳过步骤的常见借口与反驳），故 10→12。
    这是**有意增补**：S7/S13 正是"自审 vs 独立审"最容易合理化的两个位置。
    """
    data = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = data["comp_cumcm"]["sub_steps"]
    by_skill = {s["skill_name"]: s for s in steps}
    with_assets = [s for s in steps if s.get("metadata", {}).get("assets")]
    assert len(with_assets) == 12
    for s in with_assets:
        for asset in s["metadata"]["assets"]:
            assert asset.get("name") and asset.get("path"), s["skill_name"]
    # 反合理化表必须挂在"最容易被合理化"的三步上（复核 / 终审 / 交付审计）
    for skill in ("comp-review", "comp-final-review", "comp-final-audit"):
        names = {a["name"] for a in by_skill[skill]["metadata"]["assets"]}
        assert "反合理化表" in names, skill
