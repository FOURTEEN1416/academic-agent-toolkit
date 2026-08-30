# -*- coding: utf-8 -*-
"""P1/P2 新管线回归测试（C6）：模板契约 + catalog 合同完整性。"""
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


def test_paper_submission_template_contract():
    t = TPL["paper_submission"]
    names = [s["skill_name"] for s in t["sub_steps"]]
    assert names == ["scholar-presubmit-checks", "nature-submission-audit",
                     "galaxy-nature-response", "scholar-latex-cleanup", "comp-review"]
    review = t["sub_steps"][-1]
    assert review["metadata"]["requires_subagent"] is True
    assert "review" in review["required_checks"]
    # camera-ready 步骤必须同时产出记录与修订稿（P1 验收教训）
    cleanup = t["sub_steps"][3]
    assert set(cleanup["output_files"]) == {"CAMERA_READY.md", "manuscript_camera_ready.md"}


def test_deep_research_template_contract():
    t = TPL["deep_research"]
    names = [s["skill_name"] for s in t["sub_steps"]]
    assert names == ["idea-discovery", "research-lit", "ars-research-summarizer", "comp-review"]
    assert t["sub_steps"][-1]["metadata"]["requires_subagent"] is True


def test_p1_p2_catalog_contracts_complete():
    required = {"capability_id", "name", "domain", "description", "input_contract",
                "output_contract", "status", "associated_skills", "associated_tools",
                "external_dependencies", "high_risk_confirmation", "current_evidence", "current_gap"}
    for cid in ("paper_submission_closed_loop", "deep_research_pipeline"):
        e = _cap(cid)
        missing = required - set(e.keys())
        assert not missing, f"{cid}: {missing}"
        for s in e["associated_skills"]:
            assert (ROOT / "skills" / s / "SKILL.md").is_file(), f"{cid} -> missing skill {s}"


def test_templates_reference_existing_skills():
    for tname, t in TPL.items():
        for s in t.get("sub_steps", []):
            sk = s.get("skill_name")
            if sk:
                assert (ROOT / "skills" / sk / "SKILL.md").is_file(), f"{tname}: {sk}"
