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
