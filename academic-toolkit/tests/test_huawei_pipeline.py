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
    """D3 快检页口径必须覆盖华为杯 80（quick_gates.py 默认 30 是 CUMCM 口径，
    不参数化会把 80 页正文误判 FAIL）。⚠️ 2026-09-25 用户裁决：华为杯页口径
    50→80（压缩延后）；原基线 50 记录于 comp_rules.json page_cap_note。
    ⚠️ 2026-09-27（C窗五轮）起共享模板不再承载 quick_gates_max_pages 默认：
    步骤只挂 quick_gates 开关，生效页限经 workflow_runner:330-332 → quality_gates
    回落链取 bound 快照 compliance 口径（行为断言见
    test_g1_huawei_page_cap_still_resolves_80_via_bound_snapshot）。"""
    for i, s in enumerate(_hw_steps(), 1):
        md = s["metadata"]
        if md.get("quick_gates"):
            assert "quick_gates_max_pages" not in md, (
                f"S{i} 共享模板不得承载页限默认（生效口径走 bound 快照回落链）")
    mounted = [s["skill_name"] for s in _hw_steps() if s["metadata"].get("quick_gates")]
    assert mounted == ["paper-figure", "comp-paper-zh"], mounted


def test_huawei_assets_all_exist():
    """华为杯 14 步资产指针逐一在位（公开 clone 缺 gitignored 私有资料区时 skip）。"""
    reason = None
    for name in ("assets-local/award-papers", "assets-local/reference-figures",
                 "assets-local/cumcm-templates"):
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
    """StepAction 渲染 --max-pages 80；未声明时保持无旗标（默认 30 兼容 CUMCM）。"""
    from agent_bridge import StepAction
    base = dict(workflow_id="wf", step_id="s", position=1, skill_name="paper-figure",
                display_name="图表生成", workspace=Path("."), skill_path=Path("x"),
                output_files=[], primary_output="", has_checkpoint=False,
                checkpoint_type=None, quick_gates=True)
    hw = StepAction(quick_gates_max_pages=80, **base)
    cum = StepAction(**base)
    assert "--max-pages 80" in hw.execution_instructions()
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
    for token in ("--max-pages 80", "30-46", "gmcmthesis"):
        assert token in section, f"§七 缺 {token}"


# ── G1：S14 合规口径 compliance_profile 分支（2026-09-22）──────────────────
#
# before：S14（comp-final-audit）与国赛共用同一技能，其合规判据只有国赛口径
# （SKILL.md:10『no commitment/ID pages…body ≤30 pages』；quick_gates 默认 30），
# 与华为杯硬规则（gmcmthesis 首页=参赛承诺书、正文页上限见 comp_rules）直接冲突。
# after：口径按竞赛族落在 comp_rules.json 的 compliance 块，S14 挂
# metadata.compliance_profile + 机器真源资产指针，quick_gates 数据驱动消费。

COMP_RULES = json.loads(
    (ROOT / "engine" / "modex-core" / "comp_rules.json").read_text(encoding="utf-8"))
# schema v2（E-MERGE-01）：赛事表包裹在顶层 contests 键下
COMP_RULES = COMP_RULES.get("contests") or COMP_RULES


def _resolve(fam, extra=None):
    from engine.contest_profile import resolve_profile
    contest = {"edition": "2026", "submission_form": "electronic"}
    contest.update(extra or {})
    return resolve_profile(fam, {"contest": contest})


def _constraint(cp, name):
    return next(c for c in cp.constraints if c.get("name") == name)


def _s14(fam):
    return TEMPLATES[fam]["sub_steps"][13]


def test_g1_s14_declares_compliance_profile():
    """两族 S14 各自声明 compliance_profile，指向 comp_rules.json 顶层键。
    schema v2：合规口径由 profiles 维度约束带承载（无顶层 compliance 块）。"""
    assert _s14("comp_huawei")["metadata"].get("compliance_profile") == "comp_huawei"
    assert _s14("comp_cumcm")["metadata"].get("compliance_profile") == "comp_cumcm"
    for fam in ("comp_huawei", "comp_cumcm"):
        assert fam in COMP_RULES, f"{fam} 在 comp_rules.json 无条目"
        profiles = COMP_RULES[fam].get("profiles")
        assert isinstance(profiles, list) and profiles, f"{fam} 缺 profiles 维度（v2 契约）"
        assert any(isinstance(p.get("constraints"), list) and p["constraints"]
                   for p in profiles), f"{fam} profiles 缺约束带"


def test_g1_huawei_compliance_pledge_and_page_budget():
    """华为杯口径实测钉住（schema v2）：承诺书方向 hw-pledge=unknown（不硬执行任一
    方向，人工确认）；首页封皮不可删 + 除首页外无身份信息已核验；正文页上限
    hw-page-limit=unknown（无官方记载）——历轮 80/50 只留 migration_evidence
    不自动继承，新任务口径走显式通道（MIGRATION.md M4）。"""
    hw = _resolve("comp_huawei")
    pledge = _constraint(hw, "hw-pledge")
    assert pledge["status"] == "unknown" and pledge.get("value") is None, (
        "华为杯承诺书方向当前 unknown（value=null，E 契约三态），勿回退旧口径硬执行")
    first_page = _constraint(hw, "hw-first-page")
    assert first_page["status"] == "verified"
    assert first_page["value"]["cover_immutable"] is True
    assert _constraint(hw, "hw-anonymity")["status"] == "verified"
    assert _constraint(hw, "hw-anonymity")["value"]["identity_forbidden_outside_first_page"] is True
    page_limit = _constraint(hw, "hw-page-limit")
    assert page_limit["status"] == "unknown" and page_limit.get("value") is None, (
        "23 届公开文件集无页数上限条款——unknown 不等于无要求，不猜值")
    non_inherited = [o for o in hw.non_inherited_overrides if o.get("value") == 80]
    assert non_inherited, "华为 80 历史裁决必须留在 non_inherited_overrides（不继承但留痕）"
    assert "runtime_channel" in json.dumps(COMP_RULES["comp_huawei"].get("migration_evidence", []), ensure_ascii=False)
    for s in _hw_steps():
        md = s["metadata"]
        if md.get("quick_gates"):
            assert "quick_gates_max_pages" not in md
    assert hw.compliance == {}, "unknown 约束不构造 compliance 视图（不冒充方向）"


def test_g1_huawei_page_cap_still_resolves_80_via_bound_snapshot(tmp_path):
    """行为断言（schema v2）：华为 80 不在 compliance.max_body_pages 顶层，只留
    migration_evidence；bound 快照 operative cap=None（task_override 不继承）；
    80 经 runtime channel（任务显式声明）解析为 explicit_task 生效口径。"""
    from engine.quality_gates import QualityGate
    snapshot = _resolve("comp_huawei").to_snapshot()
    assert snapshot["status"] == "bound"
    assert snapshot["profile_id"] == "comp_huawei_2026_electronic"
    # 无显式任务口径：不继承 80，页检无口径（SKIP 语义），留痕披露
    assert snapshot["operative"]["cap"] is None
    assert snapshot["operative"]["status"] == "task_override"
    assert any(o.get("value") == 80 for o in snapshot["non_inherited_overrides"])
    # runtime channel：任务显式声明 80 → operative 生效口径 80（explicit_task）
    explicit = _resolve("comp_huawei", {"page_cap": 80})
    assert explicit.operative == {"cap": 80, "scope": "body", "status": "explicit_task",
                                  "reason": "任务显式声明口径（只影响当前任务）"}
    gate = QualityGate(tmp_path).run_all(
        "comp-paper-zh", comp_name="",
        page_contract=dict(explicit.operative),
        quick_gates=True,
        compliance_profile="comp_huawei",
        compliance_block=dict(explicit.compliance))
    early = gate["checks"]["early_quality"]
    assert early["max_pages_effective"] == 80, early
    assert early["page_contract"]["scope"] == "body", early["page_contract"]


def test_g1_cumcm_compliance_not_regressed():
    """国赛链不受扰（schema v2 profiles 维度）：电子版承诺书 forbidden + 正文 30 页
    official_verified；纸质版承诺书 required（双 profile 精确化语义）。"""
    elec = _resolve("comp_cumcm")
    assert elec.profile_id == "comp_cumcm_2026_electronic"
    assert elec.compliance["pledge_page"] == "forbidden_in_electronic"
    assert elec.max_body_pages == 30
    assert elec.page_cap_status == "official_verified"
    assert elec.operative == {"cap": 30, "scope": "body", "status": "official_verified",
                              "reason": ""}
    from engine.contest_profile import resolve_profile
    paper = resolve_profile("comp_cumcm", {"contest": {"edition": "2026",
                                                       "submission_form": "paper"}})
    assert paper.compliance["pledge_page"] == "required"


def test_g1_s14_assets_point_to_machine_rules_and_no_cumcm_only_pointers():
    """S14 挂 comp_rules.json 机器真源指针；华为杯侧不引用国赛专属常量/路径。"""
    for fam in ("comp_huawei", "comp_cumcm"):
        paths = {a["path"] for a in _s14(fam)["metadata"]["assets"]}
        assert "academic-toolkit/engine/modex-core/comp_rules.json" in paths, f"{fam} S14 缺合规真源指针"
    hw_blob = json.dumps(_s14("comp_huawei"), ensure_ascii=False)
    for token in ("cumcm_2026_format", "CUMCM2026Problems", "≤30", "30 页硬上限"):
        assert token not in hw_blob.replace("勿沿用国赛 30 页", ""), \
            f"华为杯 S14 仍引用 CUMCM 专属口径: {token}"


def test_g1_quick_gates_profile_functions():
    """quick_gates 数据驱动（schema v2）：档案解析 / 页口径优先级 / 承诺书判定。
    华为杯 hw-pledge=unknown → 无 compliance 视图 → 判定 SKIP（不冒充任一方向）；
    国赛电子版 forbidden 照常 FAIL/PASS。任何路径都没有缺省页数——无口径页检
    SKIP，未知 ID 显式报错不默认；华为 80 不再从档案直出（migration_evidence
    非继承，显式 --max-pages 才生效）。"""
    sys.path.insert(0, str(ROOT / "skills" / "_utils"))
    import quick_gates as qg

    cp_hw, entry_hw, err_hw = qg._load_entry("comp_huawei")
    cp_cm, entry_cm, err_cm = qg._load_entry("comp_cumcm")
    assert err_hw is None and err_cm is None, (err_hw, err_cm)
    # v2：条目无顶层 compliance 块（合规口径在 profiles 维度），脚本路径如实无视图
    assert not isinstance(entry_hw.get("compliance"), dict)
    assert not isinstance(entry_cm.get("compliance"), dict)
    _, entry_missing, err_missing = qg._load_entry("comp_nobody")
    assert entry_missing is None and err_missing, "未知赛事 ID 必须显式报错，不得默认任何赛事"
    # 优先级（B-02 契约）：显式 --max-pages > 档案 operative 口径 > 无缺省（cap=None 页检 SKIP）
    hw_contract = qg.page_contract(None, entry_hw, cp_hw)
    assert hw_contract["cap"] is None, "华为 80 在 migration_evidence 不继承，档案直出必须无口径"
    cm_contract = qg.page_contract(None, entry_cm, cp_cm)
    assert cm_contract["cap"] is None, "脚本路径未选 profiles 维度，不得直出国赛 30"
    assert qg.page_contract(60, entry_hw, cp_hw)["cap"] == 60  # 显式 --max-pages 优先
    bare = qg.page_contract(None, None)
    assert bare["cap"] is None and bare["status"] == "unconfigured", bare
    # 承诺书判定（v2）：华为 unknown → SKIP 双向；国赛电子版 forbidden → FAIL/PASS
    pages = ["华为杯研究生数学建模竞赛 参赛承诺书 …", "封面", "摘要"]
    assert qg._pledge_verdict(pages, {})[0] == "SKIP"
    cm_elec_view = _resolve("comp_cumcm").compliance
    assert qg._pledge_verdict(pages, cm_elec_view)[0] == "FAIL"
    pages2 = ["摘要", "问题重述", "正文"]
    assert qg._pledge_verdict(pages2, {})[0] == "SKIP"
    assert qg._pledge_verdict(pages2, cm_elec_view)[0] == "PASS"


def test_g1_quick_gates_cli_profile_end_to_end(tmp_path):
    """CLI 端到端（schema v2）：--compliance-profile comp_huawei 下页口径无记载
    → max_pages_effective=None、page_count SKIP（不默认 80/30）；pledge 检查项在册
    且如实 SKIP（profiles 维度未选择/unknown，不冒充通过）；显式 --max-pages 80
    生效为任务口径。默认无 profile 时 B-02 契约照旧——双副本各跑一遍。"""
    import subprocess
    for copy in (ROOT / "skills" / "_utils", ROOT / "skills" / "shared-scripts"):
        script = copy / "quick_gates.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--workspace", str(tmp_path),
             "--compliance-profile", "comp_huawei", "--skip", "figures", "--skip", "leakage"],
            capture_output=True, text=True, timeout=300)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        rep = json.loads(proc.stdout)
        assert rep["compliance_profile"] == "comp_huawei"
        assert rep["max_pages_effective"] is None, "华为杯 v2 无页数口径，不得直出 80"
        assert rep["page_contract"]["cap"] is None
        assert {c["name"] for c in rep["checks"]} == {"page_count", "pledge_page"}
        page_check = next(c for c in rep["checks"] if c["name"] == "page_count")
        assert page_check["status"] == "SKIP", page_check
        pledge_check = next(c for c in rep["checks"] if c["name"] == "pledge_page")
        assert pledge_check["status"] == "SKIP", pledge_check  # unknown 不冒充通过
        # runtime channel：--max-pages 80 显式声明才生效（任务口径，非档案继承）
        capped = subprocess.run(
            [sys.executable, str(script), "--workspace", str(tmp_path),
             "--compliance-profile", "comp_huawei", "--max-pages", "80",
             "--skip", "figures", "--skip", "leakage"],
            capture_output=True, text=True, timeout=300)
        rep80 = json.loads(capped.stdout)
        assert rep80["max_pages_effective"] == 80, rep80["page_contract"]
        assert rep80["page_contract"]["status"] == "explicit_task", rep80["page_contract"]  # 显式任务口径只影响本任务，不写回档案
        bare = subprocess.run(
            [sys.executable, str(script), "--workspace", str(tmp_path)],
            capture_output=True, text=True, timeout=300)
        rep0 = json.loads(bare.stdout)
        assert {c["name"] for c in rep0["checks"]} == {"page_count", "figure_font", "leakage"}
        # B-02（2026-09-27）：无口径不再默认 30——cap=None（unconfigured），页检 SKIP 不冒充
        assert rep0["max_pages_effective"] is None and rep0["compliance_profile"] is None
        assert rep0["page_contract"]["status"] == "unconfigured", rep0["page_contract"]
        page_check0 = next(c for c in rep0["checks"] if c["name"] == "page_count")
        assert page_check0["status"] == "SKIP", page_check0
