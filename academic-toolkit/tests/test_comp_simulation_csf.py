"""仿真建模赛（comp_csf）赛事档案 + comp-simulation 产物契约测试。

批次：2026-10-16 仿真建模赛（全国大学生仿真建模应用挑战赛）能力补齐批。
落位：academic-toolkit/tests/test_comp_simulation_csf.py

覆盖三件事：
1. `comp_rules.json` 的 comp_csf 赛事档案（三赛道/四件套/命名/视频规格/匿名/提交节点）逐条存在且状态合法；
2. 官方格式真源文件在位且与 comp_rules 口径一致（页数等缺口**必须**保持缺席，不得臆测）；
3. `comp-simulation` 的产物契约脚本行为：缺文件 exit 2（不冒充通过）、契约不合规 exit 1、合规 exit 0。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
RULES_PATH = ROOT / "engine" / "modex-core" / "comp_rules.json"
SIM_DIR = ROOT / "skills" / "comp-simulation"
CHECK = SIM_DIR / "scripts" / "sim_manifest_check.py"
PROBE = SIM_DIR / "scripts" / "sim_env_probe.py"
FORMAT_MD = ROOT / "skills" / "comp-paper-zh" / "references" / "csf-official-format.md"


@pytest.fixture(scope="module")
def csf() -> dict:
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return rules["contests"]["comp_csf"]


def _constraint(csf: dict, cid: str) -> dict:
    for profile in csf["profiles"]:
        for con in profile["constraints"]:
            if con["id"] == cid:
                return con
    raise AssertionError(f"comp_csf 缺约束 {cid}")


def test_csf_profile_shape(csf: dict) -> None:
    """单档案：edition=2026 / submission_form=electronic / 生命周期 active。"""
    assert csf["contest_id"] == "comp_csf"
    assert csf["language"] == "zh"
    assert len(csf["profiles"]) == 1
    profile = csf["profiles"][0]
    assert profile["profile_id"] == "comp_csf_2026_electronic"
    assert profile["edition"] == "2026"
    assert profile["submission_form"] == "electronic"
    assert csf["lifecycle"]["status"] == "active"
    assert csf["lifecycle"]["checked_at"]


def test_csf_three_tracks(csf: dict) -> None:
    """第二届为 A/B/C 三赛道且三选一（不得退回首届 A/B 双赛道）。"""
    tracks = _constraint(csf, "csf26-competition-form")["value"]["tracks"]
    assert len(tracks) == 3
    assert tracks[0].startswith("A")
    assert tracks[1].startswith("B")
    assert tracks[2].startswith("C")
    assert _constraint(csf, "csf26-competition-form")["value"]["choose_tracks"] == 1


def test_csf_deliverable_components(csf: dict) -> None:
    """四件套组成与必要性（论文/承诺书/视频必要，支撑材料可选）。"""
    val = _constraint(csf, "csf26-components")["value"]
    assert set(val["components"]) == {"参赛电子版论文", "承诺书", "支撑材料", "仿真视频文件"}
    assert set(val["required"]) == {"参赛电子版论文", "承诺书", "仿真视频文件"}
    assert val["optional"] == ["支撑材料"]


def test_csf_file_naming_keyed_by_track_and_team(csf: dict) -> None:
    """命名口径：题号（赛道字母）+队伍号+后缀，四个后缀齐全。"""
    val = _constraint(csf, "csf26-file-naming")["value"]
    joined = json.dumps(val, ensure_ascii=False)
    for suffix in (".pdf", "cns", "fj", "fz"):
        assert suffix in joined, suffix
    assert "ACSF2600001" in joined
    assert val["pattern"] == "题号+队伍号+后缀"


def test_csf_paper_pdf_single_file(csf: dict) -> None:
    """论文仅 PDF 单文件、不压缩、不得含承诺书。"""
    val = _constraint(csf, "csf26-paper-file-format")["value"]
    assert val["allowed"] == ["pdf"]
    assert val["single_file"] is True
    assert "forbidden" in val["compression"]
    assert "forbidden" in val["pledge_inside_paper"]


def test_csf_abstract_first_page_and_code_appendix(csf: dict) -> None:
    """摘要第一页且不得拆分；源程序入附录且与正文同文件（页序硬约束）。"""
    order = _constraint(csf, "csf26-page-order")["value"]
    assert order["sequence"][0].startswith("abstract_page")
    assert order["appendix_same_file"] is True
    first = _constraint(csf, "csf26-first-page")["value"]
    assert first["page"] == 1 and first["separate_file_forbidden"] is True
    code = _constraint(csf, "csf26-source-code")["value"]
    assert code["appendix_in_paper"] is True and code["also_in_support_material"] is True


def test_csf_video_spec_within_official_bounds(csf: dict) -> None:
    """视频：mp4 / ≤3min / ≥1280x720 / 建议 ≤300MB / 三段内容要素齐全。"""
    val = _constraint(csf, "csf26-video-spec")["value"]
    assert val["container"] == "mp4"
    assert val["max_duration_s"] == 180
    assert val["min_resolution"] == "1280x720"
    assert val["max_size_mb"] == 300
    assert len(val["required_content"]) == 3


def test_csf_anonymity_and_pledge_separation(csf: dict) -> None:
    """匿名要求适用于任何材料；承诺书是规则豁免的独立签名件（不得判为违规）。"""
    anon = _constraint(csf, "csf26-anonymity")["value"]
    assert anon["identity_forbidden"] is True
    assert "姓名" in anon["forbidden_items"] and "学校" in anon["forbidden_items"]
    pledge = _constraint(csf, "csf26-pledge")["value"]
    assert pledge["separate_file"] is True and pledge["inside_paper"] == "forbidden"
    assert set(pledge["accepted_formats"]) == {"pdf", "jpg", "png"}


def test_csf_deadlines_two_stage(csf: dict) -> None:
    """两段截止：论文/承诺书/支撑材料 10-20 20:00；视频 10-21 20:00。"""
    val = _constraint(csf, "csf26-submission-deadline")["value"]
    assert val["paper_pledge_support_deadline"].startswith("2026-10-20T20:00")
    assert val["video_deadline"].startswith("2026-10-21T20:00")
    assert val["resubmit_allowed"] is True


def test_csf_no_page_limit_and_no_aigc_threshold_in_constraints(csf: dict) -> None:
    """**缺口纪律**：官方《论文规范》未取证 → 不得出现 page_limit 约束，
    也不得把 2025 首届的 AIGC/相似比数值阈值写进当届约束（只能隔离在 historical_notes）。"""
    kinds = [c["kind"] for p in csf["profiles"] for c in p["constraints"]]
    assert "page_limit" not in kinds, "《论文规范》未取证期间不得臆测页数上限"
    blob = json.dumps(csf["profiles"], ensure_ascii=False)
    assert "0.30" not in blob and "0.50" not in blob, "首届 AIGC/相似比阈值不得进当届约束层"
    hist = csf["historical_notes"][0]
    assert hist["kind"] == "superseded_edition"
    assert hist["material"]["aigc_threshold"] == 0.30
    assert hist["material"]["similarity_threshold"] == 0.50


def test_csf_open_questions_record_format_gap(csf: dict) -> None:
    """缺口必须显式登记（论文规范/赛项说明/承诺书模板），不得静默省略。"""
    questions = " ".join(csf["evidence_summary"]["open_questions"])
    assert "论文规范" in questions
    assert "赛项说明" in questions


def test_csf_sources_registered_and_cited(csf: dict) -> None:
    """引用的来源必须在顶层 sources 表登记，且至少一份为全文级。"""
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    sources = rules["sources"]
    cited = {s for p in csf["profiles"] for c in p["constraints"] for s in c["source_ids"]}
    assert cited, "comp_csf 约束未引用任何来源"
    for sid in cited:
        assert sid in sources, f"悬空 source_id: {sid}"
    levels = {sources[s]["verification"] for s in cited}
    assert levels & {"full_text", "full_text_image"}, levels


def test_csf_official_format_reference_exists() -> None:
    """官方格式真源文档在位，且显式声明缺口（不主张未取证项）。"""
    text = FORMAT_MD.read_text(encoding="utf-8")
    assert "四件套" in text
    assert "ACSF2600001" in text
    assert "缺口" in text
    assert "论文规范" in text


def test_sim_manifest_check_missing_file_exits_2(tmp_path: Path) -> None:
    """缺 manifest 必须 exit 2 并明示不冒充通过（本仓 SKIP 语义）。"""
    res = subprocess.run([sys.executable, str(CHECK), str(tmp_path / "nope.json")],
                         capture_output=True, text=True)
    assert res.returncode == 2, res.stdout + res.stderr
    assert "不冒充通过" in res.stdout or "SKIP" in res.stdout


def test_sim_manifest_check_rejects_incomplete_contract(tmp_path: Path) -> None:
    """契约不全（缺 V&V/基线/N=1）必须 exit 1 并逐项列出。"""
    bad = {"method": "abm", "engine": {"name": "mesa", "available": True, "version": "3.0"},
           "time": {"semantics": "fixed_step", "horizon": 10, "unit": "day"},
           "entities": [{"type": "a", "count": 1}],
           "randomness": {"generator": "default_rng", "seeds": [1], "replications": 1},
           "observations": [{"metric": "m", "aggregate": "mean"}],
           "calibration": {"source": "s"},
           "vv": {}, "runs": {"total": 1, "wall_clock_s": 1.0}}
    p = tmp_path / "SIM_MANIFEST.json"
    p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    res = subprocess.run([sys.executable, str(CHECK), str(p)], capture_output=True, text=True)
    assert res.returncode == 1, res.stdout + res.stderr
    assert "FAIL" in res.stdout
    assert "N=1" in res.stdout or "replications" in res.stdout
    assert "baseline" in res.stdout


def test_sim_manifest_check_accepts_complete_contract(tmp_path: Path) -> None:
    """完整契约 exit 0（正例，防判据单向收紧导致永久 FAIL）。"""
    good = {"method": "hybrid",
            "hybrid_roles": {"mechanism": "abm", "sampler": "montecarlo"},
            "engine": {"name": "mesa", "available": True, "version": "3.1.0"},
            "time": {"semantics": "fixed_step", "dt": 0.1, "horizon": 100, "unit": "day"},
            "entities": [{"type": "vehicle", "count": 40, "state_vars": ["soc"]}],
            "randomness": {"generator": "np.random.default_rng", "seeds": [1, 2], "replications": 2},
            "observations": [{"metric": "makespan", "aggregate": "mean", "ci": "t95"}],
            "calibration": {"params": {"v": 12.5}, "source": "官方数据集"},
            "vv": {"verification": ["解析解对比"], "validation": ["留出情景"],
                   "baseline": "历史均值"},
            "runs": {"total": 2, "wall_clock_s": 1.0, "artifact": "results/sim_runs.csv"}}
    p = tmp_path / "SIM_MANIFEST.json"
    p.write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
    res = subprocess.run([sys.executable, str(CHECK), str(p)], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "OK" in res.stdout


def test_sim_env_probe_runs_offline() -> None:
    """引擎探测脚本可离线运行并输出机读结果（缺席不阻断）。"""
    res = subprocess.run([sys.executable, str(PROBE), "--json"],
                         capture_output=True, text=True, timeout=120)
    assert res.returncode in (0, 2), res.stdout + res.stderr
    payload = json.loads(res.stdout)
    assert payload["libs"], "探测结果不能为空"
    assert {"python", "available", "missing"} <= set(payload)
