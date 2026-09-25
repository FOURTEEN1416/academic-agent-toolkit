# -*- coding: utf-8 -*-
"""W2 资产激活机制单测：asset_catalog 台账 + boot/probe 暴露 + 第六类三方对账。

背景（2026-09-23 v2.0 改造研究结论）：技能有五级登记（SKILL.md→catalog→
routing_index→路由表→probe），资产零级登记——智能体进仓后"不知道自己有什么"，
默认只走 skills。W2 给资产上户籍：台账真源 + boot/probe/bootstrap 三链暴露 +
check_asset_utilization 第六类"台账↔磁盘↔git tracked"三方对账。
"""
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SUITE_ROOT = TESTS_DIR.parent
REPO_ROOT = SUITE_ROOT.parent
sys.path.insert(0, str(SUITE_ROOT))

from engine.agent_protocol import bootstrap  # noqa: E402
from engine.capability_probe import probe  # noqa: E402
from tools.check_asset_utilization import ledger_reconciliation  # noqa: E402

CATALOG = SUITE_ROOT / "data" / "asset_catalog.json"


def _load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def test_catalog_schema_and_uniqueness():
    data = _load_catalog()
    assert data.get("schema_version") == 1
    assets = data["assets"]
    assert len(assets) >= 40, "台账条目意外缩水"
    ids = [a["id"] for a in assets]
    assert len(ids) == len(set(ids)), "台账 id 必须唯一"
    required = {"id", "path", "zone", "type", "description", "when_to_use",
                "owner_skills", "consumers", "local_only"}
    for a in assets:
        missing = required - set(a)
        assert not missing, f"{a.get('id')} 缺字段: {missing}"
        assert a["path"], f"{a['id']} path 不得为空"


def test_catalog_covers_all_zones():
    zones = {a["zone"] for a in _load_catalog()["assets"]}
    assert zones == {"data", "skills-internal", "assets-local", "seasonal", "third_party"}


def test_ledger_reconciliation_real_repo_clean():
    """真仓三方对账：缺盘（非 local_only）/未跟踪/schema 错 必须为零（strict 语义）。"""
    result = ledger_reconciliation(REPO_ROOT)
    assert result["entries"] >= 40
    assert result["schema_errors"] == [], result["schema_errors"]
    assert result["missing_disk"] == [], [m["path"] for m in result["missing_disk"]]
    assert result["not_tracked"] == [], [m["path"] for m in result["not_tracked"]]


def test_ledger_reconciliation_template_coverage():
    """templates.json 接线资产必须入台账（智能体发现面无缺口）。"""
    result = ledger_reconciliation(REPO_ROOT)
    assert result["uncovered_template_paths"] == [], result["uncovered_template_paths"]


def test_ledger_local_only_missing_is_semantic_not_fake():
    """local_only 条目缺盘记'未交付'（语义缺位）而非'缺盘'（假接线）。"""
    result = ledger_reconciliation(REPO_ROOT)
    seasonal = [a for a in _load_catalog()["assets"] if a["zone"] == "seasonal"]
    assert seasonal, "seasonal 区（赛时预置）应在台账登记"
    # 本机 CUMCM2026Problems 可能缺席：若缺席必须落在 missing_local_only 桶
    if not (REPO_ROOT / "CUMCM2026Problems").exists():
        assert any(m["id"] == "cumcm-2026-problems" for m in result["missing_local_only"])


def test_boot_contract_exposes_assets():
    contract = bootstrap()
    paths = contract["paths"]
    assert paths["asset_catalog"] == "academic-toolkit/data/asset_catalog.json"
    assert paths["data"] == "academic-toolkit/data/"
    assert paths["assets_local"] == "assets-local/"
    assert "assets" in contract, "boot 契约须含 assets 使用说明节"
    intents = [r["intent"] for r in contract["routing_shortcuts"]]
    assert any("资产" in i for i in intents), "路由快捷方式须含资产直查入口"
    assert "adapters" not in paths, "agents/adapters 已随宿主适配层裁决退役，不得残留指针"


def test_probe_exposes_asset_summary():
    result = probe()
    summary = result.get("asset_catalog")
    assert summary and summary.get("available") is True
    assert summary["entries"] >= 40
    assert summary["local_only_entries"] >= 10
    assert set(summary["zones"]) == {"data", "skills-internal", "assets-local", "seasonal", "third_party"}


def test_bootstrap_skill_mentions_catalog():
    text = (SUITE_ROOT / "skills" / "agent-bootstrap" / "SKILL.md").read_text(encoding="utf-8")
    assert "asset_catalog.json" in text, "agent-bootstrap 须有资产发现步（3.5 步）"


# ---------------------------------------------------------------------------
# 研赛/华为杯 分型守护（2026-09-25 建立）
# 背景：范文库与板块提示词原本 0 处覆盖研赛。本组断言锁三件事——
#   ① 研赛分型与国赛 A–E 并列且只增不改；② 逐篇抽取字段与出处齐备（禁编造）；
#   ③ 研赛板块提示词对齐官方格式硬约束（改文案即红，防止静默漂移）。
# ---------------------------------------------------------------------------

CUMCM_SECTION_IDS = [
    "abstract", "problem-restatement", "problem-analysis", "model-assumptions",
    "notations", "modeling-solving", "model-summary", "references-appendix",
    "ai-disclosure",
]
HUAWEI_SECTION_IDS = {
    "huawei-cover-identity", "huawei-abstract",
    "huawei-references", "huawei-format-page",
}
EXEMPLAR_FIELDS = {"题", "年", "题型", "方法链", "图表风格", "结构特色",
                   "可迁移要点", "provenance"}


def test_graduate_contest_branch_is_additive():
    """研赛/华为杯 分型与国赛 A–E 并列，且国赛既有数据一字未动。"""
    data = json.loads((SUITE_ROOT / "data" / "award_paper_exemplars.json").read_text(encoding="utf-8"))
    # 国赛既有口径保持
    assert data["counts"]["papers"] == 62, "国赛 62 篇基数被改动"
    assert len(data["priority_25"]) == 25
    assert set("ABCDE") <= set(data["learning_paths"])
    # 研赛分型并列存在
    assert "研赛/华为杯" in data["learning_paths"], "研赛分型键缺失"
    grad = data["graduate_contest"]
    assert grad["key"] == "研赛/华为杯"
    assert EXEMPLAR_FIELDS <= set(grad["field_schema"]), "抽取字段契约缺项"
    assert grad["counts"]["papers"] == len(grad["papers"]), "counts 与 papers 条目数不一致"
    # 逐篇：字段齐 + 有值字段必须带 provenance 出处
    for pid, item in grad["papers"].items():
        assert set(item) == EXEMPLAR_FIELDS, f"{pid} 字段须与 field_schema 一致"
        prov = item["provenance"]
        assert isinstance(prov, dict), f"{pid} provenance 须为对象"
        for key, val in item.items():
            if key == "provenance" or val in (None, "", [], {}):
                continue
            assert key in prov, f"{pid}.{key} 有值但缺出处（禁止无源填充）"


def test_huawei_section_prompts_align_official_format():
    """研赛板块提示词须同构、带来源层级，并对齐官方格式硬约束。"""
    data = json.loads((SUITE_ROOT / "data" / "cumcm_section_prompts.json").read_text(encoding="utf-8"))
    sections = data["sections"]
    ids = [s["id"] for s in sections]
    assert ids[:9] == CUMCM_SECTION_IDS, "国赛 9 板块 id/顺序被改动"

    hw = [s for s in sections if s["id"].startswith("huawei-")]
    assert {s["id"] for s in hw} == HUAWEI_SECTION_IDS, "研赛板块集合不符"
    for s in hw:
        for field in ("id", "title", "source_docx", "template_hint", "prompt", "selfcheck"):
            assert s.get(field), f"{s['id']} 缺同构字段 {field}"
        assert s.get("selfcheck"), f"{s['id']} 自查清单不得为空"
        assert "官方规范" in (s.get("source_level") or ""), f"{s['id']} 缺来源层级声明"
        assert "huawei-official-format.md" in (s.get("provenance") or ""), f"{s['id']} 缺官方出处"

    by_id = {s["id"]: s for s in sections}
    abstract_blob = by_id["huawei-abstract"]["template_hint"] + by_id["huawei-abstract"]["prompt"]
    for token in ("2 页", "无需译成英文", "建模思路", "主要方法", "结果与结论", "创新点", "关键词"):
        assert token in abstract_blob, f"摘要板块丢失官方约束：{token}"

    fmt_blob = by_id["huawei-format-page"]["template_hint"] + by_id["huawei-format-page"]["prompt"]
    for token in ("2.5 cm", "无页眉", "页脚中部", "50 页", "MD5", "50 MB"):
        assert token in fmt_blob, f"版式板块丢失官方约束：{token}"
    for token in ("内部经验口径", "非官方"):
        assert token in fmt_blob, "须显式标注内部经验口径，不得冒充官方规定"
    assert "internal_empirical" in by_id["huawei-format-page"]["provenance"], "provenance 须标 internal_empirical 三级来源"

    cover_blob = by_id["huawei-cover-identity"]["template_hint"] + by_id["huawei-cover-identity"]["prompt"]
    for token in ("不可删除", "logo", "承诺书"):
        assert token in cover_blob, f"封皮板块丢失官方约束：{token}"
