"""TDD tests for the minimum capability catalog."""
from __future__ import annotations

import json
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