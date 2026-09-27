"""E窗 赛事规则数据契约测试 v2（schema_version=2 · E-MERGE-01 合并版）。

落位：academic-toolkit/tests/test_contest_rule_data.py（E窗独占写域）。
验证对象：schema v2 合并候选/真源（draft_comp_rules_v2.json → comp_rules.json）。

运行方式（唯一数据测试、唯一接口）：
    COMP_RULES_PATH=<json路径> python -m pytest <本文件> -q
    缺省读生产真源 academic-toolkit/engine/modex-core/comp_rules.json；
    B 窗消费验证时把 COMP_RULES_PATH 指向候选文件即可，无需改测试。

E-MERGE-01 裁决钉死口径（2026-09-27，防静默回退）：
1. 约束三态封闭 verified/unknown/not_applicable；unknown value=null；
   attested/missing_evidence 不得回流（证据进 sources.kind/verification 与
   constraint.evidence，缺证原因进 evidence.reason，值材料进 evidence.material）。
2. 来源统一顶层 sources 登记表；constraint.source_ids 必须可解析；
   来源可达不等于支持具体结论（未被引用的登记来源合法）；verified 必须有
   全文级来源；约束不得引用 task_ruling/legacy_config 类来源。
3. edition 统一明确年份（\\d{4}）；submission_form 封闭 electronic|paper；
   文件格式（PDF/DOCX/大小）在约束里，不在 submission_form 里；无 null 维度档案，
   无 legacy 档案（旧值隔离在赛事级 historical_notes）。
4. 华为承诺书 unknown；旧届（apmcm 2022 / mcm 2026 / huazhong 2021 / stats 2025）
   不出现在 profiles 层；美赛 2027 材料只属 2027。
5. 任务 80 只在 migration_evidence（含运行时覆盖通道指针）；constraints/guidance 零命中。
6. 电子版 scope 文字与电子版页序一致（国赛电子版正文自摘要专用页后第 2 页起）。
7. 测试不锁 profile 数量、不比较两份旧 schema——只钉选择/隔离/来源支持/unknown 行为。
"""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = Path(os.environ.get(
    "COMP_RULES_PATH", ROOT / "engine" / "modex-core" / "comp_rules.json"))
RAW = RULES_PATH.read_text(encoding="utf-8")
RULES = json.loads(RAW)

CONTESTS = RULES["contests"]
SOURCES = RULES["sources"]

CONSTRAINT_STATUS = {"verified", "unknown", "not_applicable"}
FORBIDDEN_STATUS = {"attested", "missing_evidence"}
PROFILE_FIELDS = {"profile_id", "edition", "submission_form", "rules_revision",
                  "constraints", "guidance"}
PROFILE_OPTIONAL_FIELDS = {"region", "submit_stage"}
SUBMISSION_FORMS = {"electronic", "paper"}
CONSTRAINT_FIELDS = {"id", "kind", "status", "value", "scope", "source_ids"}
EVIDENCE_GRADES = {"searched_no_clause", "official_portal_snapshot",
                   "platform_official_snapshot", "university_repost",
                   "legacy_config", "third_party_only", "not_searched"}
SOURCE_KINDS = {"official_direct", "official_portal_snapshot",
                "platform_official_snapshot", "university_repost",
                "repo_artifact", "task_ruling", "legacy_config", "third_party"}
SOURCE_VERIFICATION = {"full_text", "full_text_image", "snapshot", "binary_scan",
                       "local_inspection", "metadata_only", "legacy_config"}
FULL_TEXT_LEVELS = {"full_text", "full_text_image"}
NON_OFFICIAL_SOURCE_KINDS = {"task_ruling", "legacy_config"}
EXPERIENCE_KINDS = {"figure_quota", "per_subquestion_quota", "length_target"}
HISTORICAL_KINDS = {"legacy_config", "copy_artifact", "superseded_edition",
                    "conflict_record", "correction_record"}
LIFECYCLE_STATUS = {"active", "suspended", "unverified"}

# 页限约束只允许出现在有届次限定官方证据或当届缺证显式声明的赛事上（扩集须改本测试并附证据）
PAGE_LIMIT_CONTESTS = {"comp_cumcm", "comp_mcm", "comp_huawei", "comp_apmcm",
                       "comp_apmcm_zh", "comp_huadong", "comp_diangong"}


def iter_constraints():
    for ck, ce in CONTESTS.items():
        for p in ce["profiles"]:
            for con in p["constraints"]:
                yield ck, p, con


def select_profile(ck, edition, form):
    """档案选择器语义：按 赛事+edition+submission_form 精确选中唯一 profile。"""
    hits = [p for p in CONTESTS[ck]["profiles"]
            if p["edition"] == edition and p["submission_form"] == form]
    assert len(hits) <= 1
    return hits[0] if hits else None


# ---------------------------------------------------------------- 结构
def test_schema_v2_structure():
    """schema_version=2；comp_* 索引；22 条目（quality_gates.json 哨兵 _COMP_RULES_count=22
    是真实消费契约）；赛事必备字段；档案层可为空但缺证赛事必有 evidence_summary。"""
    assert RULES["schema_version"] == 2
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", RULES["generated_at"])
    assert all(re.fullmatch(r"comp_[a-z0-9_]+", k) for k in CONTESTS), "非规范 comp_* ID"
    assert len(CONTESTS) == 22, f"赛事条目数漂移: {len(CONTESTS)}"
    for k, e in CONTESTS.items():
        assert e["contest_id"] == k, f"{k} contest_id 与索引键不一致"
        assert e.get("name") and e.get("language"), f"{k} 缺 name/language"
        assert isinstance(e.get("tooling"), dict), f"{k} 缺 tooling（v1 template_cls 迁移承接）"
        assert isinstance(e.get("profiles"), list), f"{k} 缺 profiles"
        lc = e.get("lifecycle")
        assert lc and lc["status"] in LIFECYCLE_STATUS, f"{k} lifecycle 缺失或非法"
        assert lc.get("checked_at"), f"{k} lifecycle 缺 checked_at"
        if not e["profiles"]:
            es = e.get("evidence_summary")
            assert es, f"{k} 无档案但缺 evidence_summary"
            assert es["status"] in {"missing_evidence", "unknown"}, f"{k} es.status 非法"
            assert isinstance(es.get("search_log"), list) and es["search_log"], f"{k} es 缺检索留痕"
            assert isinstance(es.get("open_questions"), list), f"{k} es 缺 open_questions"


def test_top_level_sources_registry():
    """来源统一顶层登记表：必备字段齐全、枚举封闭；constraint.source_ids 全部可解析；
    未被引用的登记来源合法（来源可达≠支持具体结论）。"""
    for sid, s in SOURCES.items():
        assert s["kind"] in SOURCE_KINDS, f"{sid} kind 非法: {s['kind']}"
        assert s["verification"] in SOURCE_VERIFICATION, f"{sid} verification 非法"
        assert s.get("title"), f"{sid} 缺 title"
        assert s.get("url") or s.get("path"), f"{sid} 缺 url/path"
        assert s.get("located") or s.get("excerpt") or s.get("applicable_scope"), (
            f"{sid} 缺定位/摘录/适用范围任一")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["retrieved_at"]), f"{sid} 缺 retrieved_at"
    cited = set()
    for ck, ce in CONTESTS.items():
        for p in ce["profiles"]:
            for con in p["constraints"]:
                for sid in con["source_ids"]:
                    assert sid in SOURCES, f"{ck}/{con['id']} 悬空 source_id: {sid}"
                    cited.add(sid)
        for h in ce.get("historical_notes", []):
            for sid in h["source_ids"]:
                assert sid in SOURCES, f"{ck} historical 悬空来源: {sid}"
        for m in ce.get("migration_evidence", []):
            for sid in m["sources"]:
                assert sid in SOURCES, f"{ck} migration 悬空来源: {sid}"
    assert cited, "无任何约束引用来源"
    # 不测"全部来源被引用"——登记可达不等于支持具体结论


def test_profile_shape_no_null_dimensions():
    """profile 六字段齐全；edition 明确年份；submission_form 封闭二值且不含格式词；
    region/submit_stage 只在非空时出现（不造 null 维度档案）；无 legacy 档案。"""
    seen_pids = set()
    for ck, ce in CONTESTS.items():
        seen_keys = set()
        for p in ce["profiles"]:
            missing = PROFILE_FIELDS - set(p)
            assert not missing, f"{ck}/{p.get('profile_id')} 缺字段 {sorted(missing)}"
            extra = set(p) - PROFILE_FIELDS - PROFILE_OPTIONAL_FIELDS
            assert not extra, f"{ck}/{p['profile_id']} 越界字段 {sorted(extra)}"
            for opt in ("region", "submit_stage"):
                if opt in p:
                    assert isinstance(p[opt], str) and p[opt], f"{p['profile_id']} {opt} 为空维度"
            pid = p["profile_id"]
            assert pid.startswith(ck + "_"), f"profile_id 前缀与赛事不符: {pid}"
            assert pid not in seen_pids, f"profile_id 全局重复: {pid}"
            seen_pids.add(pid)
            assert re.fullmatch(r"\d{4}", p["edition"]), f"{pid} edition 非明确年份: {p['edition']!r}"
            assert p["submission_form"] in SUBMISSION_FORMS, f"{pid} submission_form 非法"
            assert not re.search(r"pdf|docx|print|email", p["submission_form"], re.I), (
                f"{pid} 文件格式/渠道混入 submission_form（应另列约束）: {p['submission_form']}")
            key = (p["edition"], p["submission_form"], p.get("region"), p.get("submit_stage"))
            assert key not in seen_keys or True  # 赛内唯一在下一行按赛分组判定
            assert "legacy" not in pid, f"legacy 档案未溶解: {pid}"
            assert isinstance(p["rules_revision"], str) and p["rules_revision"]
        tuples = [(p["edition"], p["submission_form"], p.get("region"), p.get("submit_stage"))
                  for p in ce["profiles"]]
        assert len(tuples) == len(set(tuples)), f"{ck} 档案区分元组重复"


def test_constraint_fields_three_state_strict():
    """逐项约束六字段；三态封闭；attested/missing_evidence 回流即失败；
    unknown/not_applicable 的 value 恒为 null（E-MERGE-01 裁决 1）。"""
    for ck, p, con in iter_constraints():
        missing = CONSTRAINT_FIELDS - set(con)
        assert not missing, f"{ck}/{con.get('id')} 缺字段 {sorted(missing)}"
        assert con["status"] in CONSTRAINT_STATUS, f"{ck}/{con['id']} status 非法: {con['status']!r}"
        assert not (set(con) & FORBIDDEN_STATUS), f"{ck}/{con['id']} 四态字段回流"
        assert con["status"] not in FORBIDDEN_STATUS, f"{ck}/{con['id']} 四态 status 回流"
        assert isinstance(con["scope"], str) and con["scope"], f"{ck}/{con['id']} 缺 scope"
        assert isinstance(con["source_ids"], list) and con["source_ids"], f"{ck}/{con['id']} 缺 source_ids"
        if con["status"] in ("unknown", "not_applicable"):
            assert con["value"] is None, f"{ck}/{con['id']} {con['status']} 却携带 value"
        if "evidence" in con:
            ev = con["evidence"]
            assert ev.get("grade") in EVIDENCE_GRADES, f"{ck}/{con['id']} evidence.grade 非法"
            assert isinstance(ev.get("reason", ""), str), f"{ck}/{con['id']} evidence.reason 非法"
            if con["status"] == "verified":
                assert False, f"{ck}/{con['id']} verified 不需要 evidence 缺证材料"


# ---------------------------------------------------------------- 来源支持
def test_verified_backed_by_full_text_official():
    """verified 约束必须至少引用一份全文级来源（full_text/full_text_image）；
    约束不得引用 task_ruling/legacy_config 类来源（非官方证据）。"""
    for ck, p, con in iter_constraints():
        kinds = {SOURCES[s]["kind"] for s in con["source_ids"]}
        assert not (kinds & NON_OFFICIAL_SOURCE_KINDS), (
            f"{ck}/{con['id']} 约束引用非官方来源: {sorted(kinds & NON_OFFICIAL_SOURCE_KINDS)}")
        if con["status"] != "verified":
            continue
        levels = {SOURCES[s]["verification"] for s in con["source_ids"]}
        assert levels & FULL_TEXT_LEVELS, (
            f"{ck}/{con['id']} verified 缺全文级来源（现级别: {sorted(levels)}）")


def test_unknown_page_limit_null_not_forced():
    """unknown 页限 value=null、无数值断言、无 legacy 标记回流（unknown≠无要求，
    未核实赛事不得被测试强制要求正整数页限）；只有 verified 页限要求正整数 limit。"""
    for ck, p, con in iter_constraints():
        if con["kind"] != "page_limit":
            continue
        v = con.get("value")
        if con["status"] == "unknown":
            assert v is None, f"{ck} unknown 页限携带 value: {v!r}"
        elif con["status"] == "verified":
            assert isinstance(v.get("limit"), int) and v["limit"] > 0, (
                f"{ck} verified 页限缺正整数 limit")
            assert v.get("basis") in ("body", "total"), f"{ck} verified 页限缺 body/total 口径"
        blob = json.dumps(con, ensure_ascii=False)
        assert '"legacy"' not in blob, f"{ck} legacy 标记回流进约束"


def test_page_limit_scope_whitelist_and_no_fold():
    """页限只允许出现在白名单赛事（届次限定证据）；body/total 口径不得折叠。"""
    for ck, p, con in iter_constraints():
        if con["kind"] == "page_limit":
            assert ck in PAGE_LIMIT_CONTESTS, f"{ck} 不在页限白名单却携带页限约束"
        v = con.get("value") or {}
        blob = json.dumps(v, ensure_ascii=False)
        assert not ("body" in blob and "total" in blob), f"{ck} 页限 body/total 折叠回潮"


def test_no_word_limit_substitute_in_constraints():
    """统计建模官方约束形式是字数制：字数材料只在 historical_notes；
    任何约束层不得以 page_limit 冒充、也不得出现 word_limit 约束（当届证据未建立）。"""
    for ck, p, con in iter_constraints():
        assert con["kind"] != "word_limit", f"{ck} word_limit 约束当届证据未建立"
    stats_blob = json.dumps(CONTESTS["comp_stats"], ensure_ascii=False)
    assert "16000" in stats_blob, "统计建模字数制材料丢失（candidate 线独有发现）"
    for ck, p, con in iter_constraints():
        assert "16000" not in json.dumps(con, ensure_ascii=False), (
            f"{ck} 字数材料混入约束层")


# ---------------------------------------------------------------- 任务覆盖隔离
def test_task80_only_in_migration_evidence():
    """任务 80 只留迁移证据：constraints/guidance 零命中；migration_evidence 留值与
    运行时覆盖通道指针；来源登记表含 task_ruling 材料。"""
    assert "task_override" not in CONSTRAINT_STATUS
    for ck, p, con in iter_constraints():
        blob = json.dumps(con, ensure_ascii=False)
        assert '"limit": 80' not in blob and '"limit":80' not in blob, f"{ck} 约束携带 80"
        assert "task_override" not in (con.get("status") or "")
    for ck, ce in CONTESTS.items():
        for p in ce["profiles"]:
            gblob = json.dumps(p["guidance"], ensure_ascii=False)
            assert '"limit": 80' not in gblob, f"{ck} guidance 携带 80"
    hw = CONTESTS["comp_huawei"]
    hw_pg = [c for p in hw["profiles"] for c in p["constraints"] if c["kind"] == "page_limit"]
    assert len(hw_pg) == 1 and hw_pg[0]["status"] == "unknown" and hw_pg[0]["value"] is None
    hw_pg_blob = json.dumps(hw_pg, ensure_ascii=False)
    assert "80" not in hw_pg_blob and "50" not in hw_pg_blob, "华为页限约束携带历史数值"
    records = json.dumps(hw.get("migration_evidence", []), ensure_ascii=False)
    assert records, "华为杯缺 migration_evidence"
    assert "80" in records, "任务 80 迁移证据缺失"
    assert "quick_gates_max_pages" in records, "migration_evidence 未记录运行时覆盖通道"
    rulings = [s for s in SOURCES.values() if s["kind"] == "task_ruling"]
    assert rulings, "来源登记表缺 task_ruling 可追溯材料"


# ---------------------------------------------------------------- 经验/历史隔离
def test_experience_items_live_in_guidance_only():
    """经验图数/公式数/篇幅配额只在 guidance；华为图表 30-46 不得回潮进 constraints；
    guidance 无 status、不得携带机器门禁语义。"""
    for ck, p, con in iter_constraints():
        assert con["kind"] not in EXPERIENCE_KINDS, f"{ck}/{con['id']} 经验项混入 constraints"
    hw_cons = json.dumps([c for p in CONTESTS["comp_huawei"]["profiles"]
                          for c in p["constraints"]], ensure_ascii=False)
    assert "30-46" not in hw_cons and "图表总量区间字段" not in hw_cons.replace("图表总量区间字段", "")
    assert "figure_total" not in hw_cons
    for ck, ce in CONTESTS.items():
        for p in ce["profiles"]:
            for g in p["guidance"]:
                assert "status" not in g, f"{ck} guidance 携带 status"
                assert "source_ids" not in g, f"{ck} guidance 应单数 source"
                if "nature" in g:
                    assert g["nature"] in ("experience", "practice", "historical_config"), (
                        f"{ck} guidance nature 非法")


def test_historical_notes_isolation():
    """旧届快照/复制污染/v1 历史值/冲突记录隔离在赛事级 historical_notes：
    条目结构封闭、来源可解析；不得回流进 constraints/guidance。"""
    for ck, ce in CONTESTS.items():
        for h in ce.get("historical_notes", []):
            assert h.get("kind") in HISTORICAL_KINDS, f"{ck} historical kind 非法: {h.get('kind')}"
            assert h.get("note"), f"{ck} historical 缺 note"
            assert isinstance(h.get("source_ids"), list) and h["source_ids"], f"{ck} historical 缺来源"
    # 关键历史材料在档（E-MERGE-01 裁决 4/5：不丢证据）
    ap_blob = json.dumps(CONTESTS["comp_apmcm"].get("historical_notes", []), ensure_ascii=False)
    assert "2022" in ap_blob and "25" in ap_blob, "apmcm 2022 届快照材料丢失"
    hz_blob = json.dumps(CONTESTS["comp_huazhong"].get("historical_notes", []), ensure_ascii=False)
    assert "20页左右" in hz_blob, "华中杯 2021 软目标材料丢失"
    wy_blob = json.dumps(CONTESTS["comp_wuyi"].get("historical_notes", []), ensure_ascii=False)
    assert "20 页" in wy_blob and "30 页" in wy_blob, "五一杯 20/30 页冲突记录丢失"
    sz = CONTESTS["comp_shenzhen"]
    assert sz["lifecycle"]["status"] == "suspended" and not sz["profiles"], "深圳杯停办口径丢失"
    kinds = {h["kind"] for ce in CONTESTS.values() for h in ce.get("historical_notes", [])}
    assert "copy_artifact" in kinds, "复制污染隔离记录丢失"


def test_legacy_values_not_in_constraint_layer():
    """v1 历史配置页限值不丢但只在 historical_notes/migration_evidence：
    17 个 legacy 值逐项留档；constraints/guidance 全层无 legacy 值标记。"""
    V1 = {"comp_mathorcup": 30, "comp_stats": 30, "comp_teddy": 40, "comp_certcup": 35,
          "comp_huazhong": 30, "comp_huadong": 30, "comp_shuwei": 30, "comp_zhongqing": 30,
          "comp_yangtze": 30, "comp_diangong": 30, "comp_shenzhen": 30, "comp_huashu": 30,
          "comp_tianfu": 30, "comp_liaoning": 30, "comp_wuyi": 30,
          "comp_certcup_en": 25, "comp_shuwei_en": 25}
    for ck, pages in V1.items():
        blob = json.dumps(CONTESTS[ck].get("historical_notes", []), ensure_ascii=False)
        assert f"max_pages={pages}" in blob or f"{pages} 页" in blob, f"{ck} v1 值 {pages} 未留档"
    layer = []
    for ck, ce in CONTESTS.items():
        for p in ce["profiles"]:
            layer.extend(p["constraints"])
            layer.extend(p["guidance"])
    layer_blob = json.dumps(layer, ensure_ascii=False)
    for dead in ("page_cap_note", "body_start_pdf_page", "appendix_unlimited",
                 "figure_total_range"):
        assert dead not in RAW, f"死字段名回潮: {dead}"
    assert '"legacy": true' not in layer_blob, "legacy 标记回流约束/guidance 层"


# ---------------------------------------------------------------- 裁决专项钉死
def test_huawei_pledge_unknown():
    """E-MERGE-01 裁决 4：华为承诺书按 unknown（draft 线 verified-absent 不采纳）。"""
    hw = [c for p in CONTESTS["comp_huawei"]["profiles"] for c in p["constraints"]
          if c["kind"] == "pledge_page"]
    assert len(hw) == 1, "华为杯承诺书约束缺失或多条"
    assert hw[0]["status"] == "unknown" and hw[0]["value"] is None, (
        "华为承诺书必须 unknown/null（旧届模板不证明新届禁令）")
    assert "21" in json.dumps(hw[0].get("evidence", {}), ensure_ascii=False) or \
           "21" in hw[0].get("note", ""), "缺证原因未记录旧届模板不证明新届的口径"


def test_superseded_editions_not_selectable():
    """裁决 4：旧届不出现在档案层；美赛 2027 材料只属 2027。"""
    apmcm_eds = {p["edition"] for p in CONTESTS["comp_apmcm"]["profiles"]}
    assert apmcm_eds == {"2026"}, f"apmcm 档案届次异常: {apmcm_eds}"
    mcm_eds = {p["edition"] for p in CONTESTS["comp_mcm"]["profiles"]}
    assert mcm_eds == {"2027"}, f"mcm 档案届次异常: {mcm_eds}"
    for ck in ("comp_huazhong", "comp_stats"):
        assert not CONTESTS[ck]["profiles"], f"{ck} 旧届档案未溶解"
    mcm = CONTESTS["comp_mcm"]["profiles"][0]
    assert "2027" in mcm["rules_revision"], "mcm 档案未钉 2027 届规则版本"


def test_electronic_scope_matches_electronic_page_order():
    """裁决 7：电子版 scope 文字须与电子版页序一致——国赛电子版首页=摘要专用页，
    正文自第 2 页起；「第4页/第四页」是纸质页序，不得出现在任何 electronic 档案；
    纸质档案页序=承诺书p1/编号p2/摘要p3/正文p4。"""
    e = select_profile("comp_cumcm", "2026", "electronic")
    p = select_profile("comp_cumcm", "2026", "paper")
    assert e and p, "国赛 2026 电子/纸质双档案缺失"
    for con in e["constraints"]:
        blob = con.get("scope", "") + json.dumps(con.get("value") or {}, ensure_ascii=False)
        assert "第4页" not in blob and "第四页" not in blob, (
            f"{con['id']} 电子版档案出现纸质页序文字")
    epg = [c for c in e["constraints"] if c["kind"] == "page_limit"][0]
    assert "摘要" in epg["scope"], "电子版页限 scope 未声明自摘要页起算"
    eord = [c for c in e["constraints"] if c["kind"] == "page_order"][0]
    assert eord["value"]["sequence"] == ["abstract_page"], "电子版页序首项非摘要专用页"
    assert set(eord["value"]["excluded"]) == {"pledge_page", "numbering_page"}
    pord = [c for c in p["constraints"] if c["kind"] == "page_order"][0]
    assert pord["value"]["sequence"][0] == "pledge_page", "纸质页序首项非承诺书"
    ppl = [c for c in p["constraints"] if c["kind"] == "page_limit"][0]
    assert "第4页" in ppl["scope"], "纸质页限 scope 未按纸质页序声明"


def test_absorbed_candidate_findings_keep_unknown_strength():
    """裁决 5：candidate 线独有发现逐条在档且不自动升级 verified——
    华东杯/电工杯 2026 档案约束全部 unknown（快照级），缺证原因带材料。"""
    for ck in ("comp_huadong", "comp_diangong"):
        profs = CONTESTS[ck]["profiles"]
        assert len(profs) == 1 and profs[0]["edition"] == "2026", f"{ck} 当届档案缺失"
        for con in profs[0]["constraints"]:
            assert con["status"] == "unknown", f"{ck}/{con['id']} 快照级证据被升级"
        setup = [c for c in profs[0]["constraints"] if c["kind"] in ("page_setup",)][0]
        assert setup.get("evidence", {}).get("material"), f"{ck} 快照值材料丢失"
    assert not CONTESTS["comp_mathorcup"]["profiles"], "mathorcup 缺证却出现档案"


def test_selection_semantics_cumcm_dual_profile():
    """档案选择语义：按赛事+届次+提交形式唯一命中；电子/纸质互不串档
    （承诺书方向相反：电子 forbidden / 纸质 required）。"""
    e = select_profile("comp_cumcm", "2026", "electronic")
    p = select_profile("comp_cumcm", "2026", "paper")
    assert select_profile("comp_cumcm", "2025", "electronic") is None, "选错届次应落空"
    ep = [c for c in e["constraints"] if c["kind"] == "pledge_page"][0]
    pp = [c for c in p["constraints"] if c["kind"] == "pledge_page"][0]
    assert ep["value"]["presence"] == "forbidden", "电子版承诺书应禁止"
    assert pp["value"]["presence"] == "required", "纸质版承诺书应必备"
    # 无档案赛事不得有默认口径可选中
    assert CONTESTS["comp_mathorcup"]["profiles"] == []


# ---------------------------------------------------------------- 旧键防回流
def test_resolved_contradictions_stay_dead():
    """已定案矛盾禁止回潮（Phase-1 定案 + E-02 + E-MERGE-01）。"""
    assert "电子版第 1 页保证书" not in RAW, "国赛电子版页序旧口径回潮"
    assert "page_cap_note" not in RAW, "页数备注自由文本字段名回潮"
    assert "页数上限 50" not in RAW and "正文 ≤50" not in RAW, "华为杯伪官方 50 页上限回潮"
    assert "body_start_pdf_page" not in RAW, "正文起始死字段名回潮"
    assert "appendix_unlimited" not in RAW, "附录不限死字段名回潮"
    assert "figure_total_range" not in RAW, "图表区间机器字段回潮"
    for ck, ce in CONTESTS.items():
        assert "max_pages" not in ce, f"{ck} 赛事层 max_pages 回潮"
        assert "compliance" not in ce, f"{ck} 赛事层 compliance 平行格式回潮"
        assert "default_max_pages" not in RAW and "DEFAULT_MAX_PAGES" not in RAW, (
            "全局默认页数键回潮（未知赛事不落默认）")
        for p in ce["profiles"]:
            assert "compliance" not in p, f"{ck} profile 内嵌 compliance 回潮"
            assert "max_pages" not in p, f"{ck} profile 顶层 max_pages 回潮"


def test_migration_evidence_structure():
    """migration_evidence 结构：有 legacy/ruling 描述 + disposition + 可解析来源；
    国赛/华为两大赛事迁移记录在档。"""
    for ck, ce in CONTESTS.items():
        for m in ce.get("migration_evidence", []):
            assert (m.get("legacy") or m.get("ruling")), f"{ck} migration 记录缺 legacy/ruling"
            assert m.get("disposition"), f"{ck} migration 记录缺 disposition"
            assert m.get("sources"), f"{ck} migration 记录缺来源"
    assert CONTESTS["comp_cumcm"].get("migration_evidence"), "国赛迁移记录缺失"
    assert CONTESTS["comp_huawei"].get("migration_evidence"), "华为迁移记录缺失"
