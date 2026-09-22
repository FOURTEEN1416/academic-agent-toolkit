"""TDD tests for the minimum capability catalog."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "capabilities"
sys.path.insert(0, str(ROOT.parent))

CATALOG = ROOT / "catalog.json"


def test_catalog_structure_exists() -> None:
    assert CATALOG.is_file(), f"目录文件缺失: {CATALOG}"


def test_catalog_json_is_valid() -> None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_domain_groups_have_list_values() -> None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    expected_fields = {"math_modeling_competition", "academic_papers", "literature_research",
                       "course_research_materials", "intellectual_property_materials",
                       "figures_and_document_production"}
    for field in expected_fields:
        assert field in data, f"缺少领域组: {field}"
        assert isinstance(data[field], list), f"领域 {field} 的值应为列表"


def test_all_status_are_experimental_or_private() -> None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for field, items in data.items():
        for item in items:
            status = item.get("status", "")
            assert status in ("experimental", "private_extension", "正式"), \
                f"非法状态: {status} in {items}"


def test_capability_fields_present() -> None:
    """每个候选能力必须声明所需的最低字段。"""
    REQUIRED = {"capability_id", "name", "domain", "description", "input_contract",
                "output_contract", "status"}
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for field, items in data.items():
        for item in items:
            missing = REQUIRED - set(item.keys())
            assert not missing, f"能力 {item.get('capability_id', '<unknown>')} 缺少字段: {missing}"


def test_capability_ids_unique() -> None:
    """能力 ID 不得重复登记（设计规格验收点：不重复登记）。"""
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    ids = [item.get("capability_id") for items in data.values() for item in items]
    assert len(ids) == len(set(ids)), f"存在重复 capability_id: {[i for i in set(ids) if ids.count(i) > 1]}"


def test_all_skills_mapped() -> None:
    """目录必须覆盖套件 skills 目录中的全部技能（设计规格：200+ 项技能映射）。"""
    skills_root = Path(__file__).resolve().parents[1] / "科研工具箱" / "skills"
    skill_dirs = {d.name for d in skills_root.iterdir() if d.is_dir() and (d / "SKILL.md").exists()}
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_ids = {item.get("capability_id") for items in data.values() for item in items}
    missing = skill_dirs - catalog_ids
    assert not missing, f"未映射到目录的技能: {sorted(missing)}"


def test_associated_skills_point_to_real_skill_dirs() -> None:
    """反向校验：所有条目 associated_skills 引用的技能名必须对应真实技能目录。
    （2026-09-09 审计：曾出现 34 处家族前缀丢失的悬空引用，如 arxiv-metadata→scholar-arxiv-metadata。）

    例外（2026-09-19 首次 CI 实测新增）：公开 clone 不交付的 5 个无 License 上游技能
    经根 .gitignore 隔离，catalog 条目在册但实体不随公开仓分发，故其引用不算悬空。
    """
    local_only = {
        "plot-from-data", "plot-from-image", "visio-image-rebuilder",
        "paper-framework-figure-studio-pro", "eco-community-plots",
    }
    skills_root = Path(__file__).resolve().parents[1] / "科研工具箱" / "skills"
    skill_dirs = {d.name for d in skills_root.iterdir() if d.is_dir() and (d / "SKILL.md").exists()}
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    dangling: list[str] = []
    for items in data.values():
        for item in items:
            for ref in (item.get("associated_skills") or []):
                if ref not in skill_dirs and ref not in local_only:
                    dangling.append(f"{item.get('capability_id')} -> {ref}")
    assert not dangling, f"associated_skills 引用了不存在的技能目录: {sorted(dangling)}"


def test_aggregated_capabilities_have_extended_contract_fields() -> None:
    """聚合能力（能力合同条目，非技能映射条目）必须补齐合同扩展字段（能力合同细化验收点）：
    associated_tools / external_dependencies / current_evidence / current_gap。
    识别方式：聚合能力 capability_id 用下划线命名（comp_cumcm_full_pipeline），
    技能映射条目用技能目录名（comp-code，短横线）。"""
    EXTENDED = {"associated_tools", "external_dependencies", "current_evidence", "current_gap"}
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    agg_checked = 0
    for field, items in data.items():
        for item in items:
            cid = item.get("capability_id", "")
            if "-" in cid or cid in ("deep-research", "litreview", "sci-literature-review"):
                continue  # 技能映射条目（短横线命名）不要求扩展字段
            agg_checked += 1
            missing = EXTENDED - set(item.keys())
            assert not missing, (
                f"聚合能力 {item.get('capability_id')} 缺少合同扩展字段: {sorted(missing)}"
            )
            # 内容非空校验：工具/依赖/证据至少一个非空，gap 必须有说明
            has_content = bool(item.get("associated_tools") or item.get("external_dependencies")
                               or item.get("current_evidence") or item.get("current_gap"))
            assert has_content, f"聚合能力 {item.get('capability_id')} 扩展字段全为空"
    assert agg_checked >= 30, f"应至少识别 30 个聚合能力，实际 {agg_checked}"

def test_skill_named_entries_list_themselves() -> None:
    """双向校验①：与技能目录同名的条目，associated_skills 必须包含该技能名自身。
    （2026-09-22 批次三：route-selection / anti-defensive-writing / codesucker-integration
    曾缺自身，按 capability_id 反查关联技能时拿不到入口技能。）"""
    skills_root = Path(__file__).resolve().parents[1] / "科研工具箱" / "skills"
    skill_dirs = {d.name for d in skills_root.iterdir() if d.is_dir() and (d / "SKILL.md").exists()}
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    missing_self: list[str] = []
    for items in data.values():
        for item in items:
            cid = item.get("capability_id", "")
            if "-" in cid and cid in skill_dirs and cid not in (item.get("associated_skills") or []):
                missing_self.append(cid)
    assert not missing_self, f"技能名形态条目的 associated_skills 缺少自身: {sorted(missing_self)}"


def test_skill_named_entries_point_to_existing_skill_dirs() -> None:
    """双向校验②（反向差集）：技能名形态条目的 capability_id 必须对应真实技能目录。
    （test_all_skills_mapped 只查"目录→catalog"单向，技能目录删除/改名后条目成为幽灵不会被抓。）"""
    local_only = {
        "plot-from-data", "plot-from-image", "visio-image-rebuilder",
        "paper-framework-figure-studio-pro", "eco-community-plots",
    }
    skills_root = Path(__file__).resolve().parents[1] / "科研工具箱" / "skills"
    skill_dirs = {d.name for d in skills_root.iterdir() if d.is_dir() and (d / "SKILL.md").exists()}
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    ghosts: list[str] = []
    for items in data.values():
        for item in items:
            cid = item.get("capability_id", "")
            if "-" in cid and cid not in skill_dirs and cid not in local_only:
                ghosts.append(cid)
    assert not ghosts, f"capability_id 无对应技能目录（幽灵条目）: {sorted(ghosts)}"


# ---------------------------------------------------------------------------
# disposition 字段（2026-09-22 P4 资产激活批次 E）
#   分级：active（已接入引擎且有证据绑定面） / routed（已在路由表面在册，可被找到）
#         / evidence-bound（已由模板步骤或 companion/mandatory 槽位驱动证据留痕）
#   纪律：字段值合法 + 覆盖率棘轮只升不降 + 已声明的分级必须与真实资产面互证（不得虚报）。
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[1]
DISPOSITION_LEVELS = ("active", "routed", "evidence-bound")
# 2026-09-22 P4 批次 A 的 13 个 P0 路由修复技能（本批诚实回填为 routed，见
# 科研工具箱/CONTEST_SKILL_MAP.md §三 "P0 激活批次" 小节）。
P0_ACTIVATION_BATCH = [
    "matplotlib", "plotly", "seaborn", "visualization", "infographics",
    "excalidraw-diagram", "arxiv", "comm-lit-review", "deep-research",
    "sci-literature-review", "ablation-planner", "paper-illustration",
    "problem-selection",
]
# 覆盖率棘轮基线（2026-09-22 实测：13 P0 + sci-pdf(routed) + paper-compile-zh(evidence-bound)）
DISPOSITION_COVERAGE_BASELINE = 15


def _iter_entries(data: dict):
    for items in data.values():
        for item in items:
            yield item


def _mentions(text: str, name: str) -> bool:
    """词边界具名匹配（与 tools/check_asset_utilization.load_map_coverage 同口径）。"""
    return re.search(r"(?<![A-Za-z0-9_-])" + re.escape(name) + r"(?![A-Za-z0-9_-])", text) is not None


def _map_active_sections_text() -> str:
    """CONTEST_SKILL_MAP §一/§二/§三（活跃路由面）正文拼接。"""
    text = (REPO / "科研工具箱" / "CONTEST_SKILL_MAP.md").read_text(encoding="utf-8")
    out = []
    keep = False
    for block in text.split("## ")[1:]:
        header = block.split("\n", 1)[0]
        keep = header[:2] in ("一、", "二、", "三、")
        if keep:
            out.append(block)
    return "\n".join(out)


def _templates_text() -> str:
    return (REPO / "科研工具箱" / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8")


def _is_routed(name: str) -> bool:
    """可路由：地图活跃段具名 ∪ 模板任一处具名 ∪ 工具箱 AGENTS.md 路由表具名。"""
    return (_mentions(_map_active_sections_text(), name)
            or _mentions(_templates_text(), name)
            or _mentions((REPO / "科研工具箱" / "AGENTS.md").read_text(encoding="utf-8"), name))


def _is_evidence_bound(name: str) -> bool:
    """证据绑定：作为模板步骤主技能出现（StepAction.skill_name → 引擎 P4/C1 留痕闸覆盖）。"""
    data = json.loads(_templates_text())
    for tpl in data.values():
        if not isinstance(tpl, dict):
            continue
        for step in tpl.get("sub_steps", []):
            if isinstance(step, dict) and step.get("skill_name") == name:
                return True
    return False


def test_disposition_values_are_legal() -> None:
    """schema 允许项：disposition 只接受三级分级值（缺省表示尚未回填，允许）。"""
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    bad = [(item.get("capability_id"), item.get("disposition"))
           for item in _iter_entries(data)
           if "disposition" in item and item["disposition"] not in DISPOSITION_LEVELS]
    assert not bad, f"非法 disposition 取值: {bad}"


def test_disposition_coverage_ratchet_only_up() -> None:
    """覆盖率棘轮：已回填 disposition 的条目数只升不降（基线为 2026-09-22 实测值）。"""
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    filled = [item.get("capability_id") for item in _iter_entries(data) if item.get("disposition")]
    assert len(filled) >= DISPOSITION_COVERAGE_BASELINE, (
        f"disposition 回填数 {len(filled)} < 基线 {DISPOSITION_COVERAGE_BASELINE}"
        "——该棘轮只允许上调，不得回撤已激活资产的登记"
    )


def test_p0_batch_entries_disposition_routed() -> None:
    """P4 批次 A 的 13 个 P0 技能必须在 catalog 登记 disposition=routed（A 与 E 互锁）。"""
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_id = {item.get("capability_id"): item for item in _iter_entries(data)}
    for name in P0_ACTIVATION_BATCH:
        assert name in by_id, f"catalog 缺少 P0 条目: {name}"
        got = by_id[name].get("disposition")
        assert got == "routed", f"{name} disposition 应为 routed，实际 {got!r}"


def test_disposition_claims_match_real_surfaces() -> None:
    """不虚报：routed 必须真在活跃路由面在册，evidence-bound 必须真是模板步骤主技能。"""
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    false_claims = []
    for item in _iter_entries(data):
        disp = item.get("disposition")
        cid = item.get("capability_id", "")
        if "-" not in cid:  # 聚合条目按合同扩展字段另行校验
            continue
        if disp == "routed" and not _is_routed(cid):
            false_claims.append(f"{cid}: 声称 routed 但活跃路由面（地图 §一-§三/模板/AGENTS）无具名")
        if disp == "evidence-bound" and not _is_evidence_bound(cid):
            false_claims.append(f"{cid}: 声称 evidence-bound 但非任何模板步骤主技能")
    assert not false_claims, f"disposition 虚报: {false_claims}"
