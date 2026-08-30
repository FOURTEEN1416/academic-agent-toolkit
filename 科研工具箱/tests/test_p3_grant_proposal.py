# -*- coding: utf-8 -*-
"""P3 grant_proposal 管线回归测试（C6）：模板契约 + catalog 合同 + 防编造门禁配置。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

TPL = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
CAT = json.loads((REPO / "capabilities" / "catalog.json").read_text(encoding="utf-8"))


def _cap(cap_id):
    for entries in CAT.values():
        for e in entries:
            if e["capability_id"] == cap_id:
                return e
    raise AssertionError(f"capability not found: {cap_id}")


def test_grant_proposal_template_contract():
    t = TPL["grant_proposal"]
    names = [s["skill_name"] for s in t["sub_steps"]]
    assert names == ["idea-discovery", "research-lit", "grant-proposal", "comp-review"]
    # 独立评审门禁：requires_subagent + review 检查（防伪造审核）
    review = t["sub_steps"][-1]
    assert review["metadata"]["requires_subagent"] is True
    assert review["required_checks"] == ["step_manifest", "review"]
    # 核心执行步骤产出申请书
    core = t["sub_steps"][2]
    assert core["primary_output"] == "GRANT_PROPOSAL.md"
    # 证据登记步骤产出防编造层
    lit = t["sub_steps"][1]
    assert set(lit["output_files"]) == {"LIT_EVIDENCE.json", "search_evidence/"}


def test_grant_proposal_catalog_contract_complete():
    required = {"capability_id", "name", "domain", "description", "input_contract",
                "output_contract", "status", "associated_skills", "associated_tools",
                "external_dependencies", "high_risk_confirmation", "current_evidence", "current_gap"}
    e = _cap("grant_proposal")
    missing = required - set(e.keys())
    assert not missing, missing
    for s in e["associated_skills"]:
        assert (ROOT / "skills" / s / "SKILL.md").is_file(), f"missing skill {s}"
    # C2 证据必须登记（管线级验收后不得为空）
    assert e["current_evidence"], "current_evidence empty"


def test_grant_proposal_pipeline_skills_exist():
    t = TPL["grant_proposal"]
    for s in t["sub_steps"]:
        assert (ROOT / "skills" / s["skill_name"] / "SKILL.md").is_file(), s["skill_name"]


def test_grant_proposal_anti_fabrication_gate_config():
    """证据登记与评审步骤的产出契约必须支撑防编造体系（P2/P3 教训）。"""
    t = TPL["grant_proposal"]
    lit = t["sub_steps"][1]
    review = t["sub_steps"][-1]
    assert "step_manifest" in lit["required_checks"]
    assert "step_manifest" in review["required_checks"]
