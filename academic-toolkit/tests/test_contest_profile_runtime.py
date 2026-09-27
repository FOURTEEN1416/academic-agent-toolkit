"""赛事档案运行时（B窗 2026-09-27；B-02 端到端隔离重构）。

覆盖面：身份/偏好分离与冲突拒绝、页数语义分名（总页≠正文页）、性质不自动升级、
profiles 维度按届次/形态选择、快照冻结与漂移检测、pending_binding 不冒充快照、
unknown 不伪放行（终审合规结论）、消费者收敛（quick_gates 无默认口径）。
真实数据接入范围：comp_rules.json 现有字段（E 独占）；E 候选新增字段
（verification/classification/profiles）以临时 fixture 锁定适配语义。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import contest_profile as cp
from engine.contest_profile import (ContestProfileError, compliance_conclusion,
                                    known_contest_ids, load_entry, resolve_profile)
from engine.workflow_runner import WorkflowRunner
from engine.workflow_store import WorkflowStore
from execution.session import ExecutionSession


# ── 解析语义：精确命中 / 未知不回退 / 模糊禁令 ──────────────────────────────

def test_exact_id_resolves_real_profiles():
    assert "comp_cumcm" in known_contest_ids()
    # v2（MIGRATION.md 不变式12）：cumcm 双 profile，空诉求 → 歧义拒绝（不静默取第一条）
    with pytest.raises(ContestProfileError, match="2 个 profile"):
        resolve_profile("comp_cumcm", {})
    cumcm = resolve_profile("comp_cumcm", {"contest": {"edition": "2026",
                                                       "submission_form": "electronic"}})
    assert cumcm is not None and cumcm.contest_id == "comp_cumcm"
    assert cumcm.profile_id == "comp_cumcm_2026_electronic"
    # 页数语义分名：cumcm 电子版是正文口径（body），不冒用总页数名字
    assert cumcm.max_body_pages == 30 and cumcm.max_total_pages is None
    assert cumcm.gate_page_cap == 30 and cumcm.gate_page_scope == "body"
    assert cumcm.page_cap_status == "official_verified"
    assert cumcm.compliance.get("pledge_page") == "forbidden_in_electronic"
    # 华为杯单 profile（2026 electronic）：空诉求唯一匹配可解析；80 非继承
    huawei = resolve_profile("comp_huawei", {})
    assert huawei.profile_id == "comp_huawei_2026_electronic"
    assert huawei.max_body_pages is None and huawei.operative["cap"] is None
    assert huawei.contest_id != cumcm.contest_id


def test_total_and_body_pages_are_distinct_names():
    """总页数与正文页限不能都叫 max_body_pages：MCM 仅 2027 届档案、25 是全PDF计。
    v2：档案 25 页为 official_verified（带内性质），不再是无记载 unverified。"""
    mcm = resolve_profile("comp_mcm", {})
    assert mcm.profile_id == "comp_mcm_2027_electronic", "MCM 仅 2027 届电子形态一档"
    assert mcm.max_total_pages == 25 and mcm.max_body_pages is None
    assert mcm.gate_page_scope == "total"
    assert mcm.page_cap_status == "official_verified", "v2 带内核验性质如实承载，不自动升级也不降级"
    with pytest.raises(ContestProfileError, match="无匹配"):
        resolve_profile("comp_mcm", {"contest": {"edition": "2026"}})


def test_unknown_ids_never_fall_back_to_default_contest():
    assert resolve_profile("paper_writing", {}) is None
    assert resolve_profile("comp_huawai", {}) is None  # 拼写错误的comp键也不是赛事
    with pytest.raises(ContestProfileError):
        resolve_profile("paper_writing", {"contest": {"id": "不存在赛事"}})


@pytest.mark.parametrize("fuzzy", ["华为杯", "comp_hua", "huawei", "CUMCM", "comp_cumcm2026"])
def test_fuzzy_matching_is_not_parsing(fuzzy):
    assert resolve_profile(fuzzy, {}) is None
    with pytest.raises(ContestProfileError):
        resolve_profile("paper_writing", {"contest": {"id": fuzzy}})


# ── B-02：身份与偏好分离 ────────────────────────────────────────────────────

def test_conflicting_identity_is_rejected_not_applied():
    """固定赛事模板与显式赛事ID冲突必须拒绝——不能把国赛流程覆盖成华为杯。"""
    with pytest.raises(ContestProfileError, match="冲突"):
        resolve_profile("comp_cumcm", {"contest": {"id": "comp_huawei"}})
    with pytest.raises(ContestProfileError):
        resolve_profile("comp_huawei", {"contest": {"id": "comp_cumcm"}})
    # 一致声明合法（v2 仍须 profiles 维度精确化，歧义拒绝照旧）
    same = resolve_profile("comp_cumcm", {"contest": {"id": "comp_cumcm",
                                                      "edition": "2026",
                                                      "submission_form": "electronic"}})
    assert same.contest_id == "comp_cumcm"
    with pytest.raises(ContestProfileError, match="2 个 profile"):
        resolve_profile("comp_cumcm", {"contest": {"id": "comp_cumcm"}})


def test_generic_template_can_select_contest_explicitly():
    sel = resolve_profile("generic_tpl", {"contest": {"id": "comp_mcm"}})
    assert sel is not None and sel.contest_id == "comp_mcm" and sel.max_total_pages == 25
    assert sel.source["declared_sources"] == ["params.contest"]


def test_task_page_preference_scoped_and_capped():
    """任务页数目标只影响当前任务：不放宽已核验官方上限、不污染其他工作流。
    v2：comp_cumcm 30 已 official_verified，直接用真实档案钉不可放宽。"""
    dims = {"edition": "2026", "submission_form": "electronic"}
    a = resolve_profile("comp_cumcm", {"contest": {**dims, "page_target": 25}})
    assert a.task_preferences.get("page_target") == 25
    b = resolve_profile("comp_cumcm", {"contest": dict(dims)})
    assert b.task_preferences == {}, "另一工作流不继承任务偏好"
    # 已核验官方硬上限（30，official_verified）不可放宽
    with pytest.raises(ContestProfileError, match="不得放宽"):
        resolve_profile("comp_cumcm", {"contest": {**dims, "page_cap": 80}})
    ok = resolve_profile("comp_cumcm", {"contest": {**dims, "page_cap": 25}})
    assert ok.gate_page_cap == 25 and ok.gate_page_scope == "body"
    assert ok.operative["status"] == "explicit_task"


# ── B-02：profiles 维度选择（届次/形态选真正对应规则，不是覆盖标签） ──────────

def _fixture_file(data: dict) -> Path:
    import tempfile
    path = Path(tempfile.mkdtemp()) / "comp_rules.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


_PROFILED = {
    "comp_fx": {
        "name": "示例赛", "language": "zh",
        "profiles": [
            {"profile_id": "comp_fx@22@paper", "edition": "22", "submission_form": "paper",
             "rules_revision": "rev-22", "max_pages": 30, "page_scope": "body",
             "compliance": {"pledge_page": "required", "preface_scan_pages": 3}},
            {"profile_id": "comp_fx@23@electronic", "edition": "23", "submission_form": "electronic",
             "rules_revision": "rev-23", "max_pages": 50, "page_scope": "body",
             "compliance": {"pledge_page": "absent_in_official_template", "preface_scan_pages": 3}},
        ],
    }
}


def test_profiles_dimension_selects_real_corresponding_rules():
    fx = _fixture_file(_PROFILED)
    p23 = resolve_profile("comp_fx", {"contest": {"edition": "23", "submission_form": "electronic"}}, rules_file=fx)
    assert p23.profile_id == "comp_fx@23@electronic" and p23.rules_revision == "rev-23"
    assert p23.gate_page_cap == 50 and p23.compliance["pledge_page"] == "absent_in_official_template"
    p22 = resolve_profile("comp_fx", {"contest": {"edition": "22"}}, rules_file=fx)
    assert p22.rules_revision == "rev-22" and p22.gate_page_cap == 30
    assert p22.compliance["pledge_page"] == "required", "不同届次/形态必须命中各自规则"


def test_profiles_dimension_request_without_match_fails_loudly():
    fx = _fixture_file(_PROFILED)
    with pytest.raises(ContestProfileError, match="无匹配"):
        resolve_profile("comp_fx", {"contest": {"edition": "24"}}, rules_file=fx)
    with pytest.raises(ContestProfileError):
        resolve_profile("comp_fx", {"contest": {"edition": "23", "submission_form": "paper"}},
                        rules_file=fx), "形态不匹配也不回退"


def test_selection_request_without_dimension_is_pending_not_label():
    """档案无 profiles/edition 维度时（v2 15 个无档案赛事），请求值只记待数据，
    不冒充已选规则。comp_mcm 已有 profiles 维度（仅 2027），改用无档案赛事钉语义。"""
    p = resolve_profile("comp_mathorcup", {"contest": {"edition": "2026", "submission_form": "electronic"}})
    assert p.edition is None and p.submission_form is None
    assert "edition" in p.missing_fields and "submission_form" in p.missing_fields
    assert "edition_selection_unavailable" in p.missing_fields
    assert p.override.get("edition") == "2026", "请求留痕在 override，不进规则字段"


# ── B-02：性质与来源（不自动升级官方硬限制）+ guidance 独立 ──────────────────

def test_unverified_caps_are_not_upgraded_and_guidance_separate():
    """v2：性质只来自档案记载——cumcm 电子版带内全 verified（30 官方核验）；
    无档案赛事（如 mathorcup）无约束带、无口径 → unverified 不升级；guidance
    独立成带下发（nature=experience），不与 constraints 混装。"""
    cumcm = resolve_profile("comp_cumcm", {"contest": {"edition": "2026",
                                                       "submission_form": "electronic"}})
    assert cumcm.page_cap_status == "official_verified"
    statuses = {c["name"]: c["status"] for c in cumcm.constraints}
    assert statuses and set(statuses.values()) <= {"verified"}, statuses
    assert cumcm.guidance and all(g["nature"] == "experience" for g in cumcm.guidance)
    bare = resolve_profile("comp_mathorcup", {})
    assert bare.max_total_pages is None and bare.page_cap_status == "unverified"
    assert bare.constraints == () and bare.guidance == ()


def test_e_candidate_bands_drive_status_and_non_inheritance():
    """E 候选形态：task_override 带口径不继承给新任务；official_verified 驱动结论。"""
    fx = _fixture_file({"comp_hw_next": {
        "name": "华为杯", "language": "zh",
        "profiles": [{"profile_id": "p23", "edition": "23", "submission_form": "electronic",
                      "rules_revision": "rev23", "max_pages": 80, "page_scope": "body",
                      "compliance": {"pledge_page": "absent_in_official_template", "max_body_pages": 80},
                      "verification": {"status": "partial_official", "checked_at": "2026-09-27"},
                      "classification": {
                          "official_verified": [
                              {"claim": "官方无页数上限条款", "evidence": "cmathc 644.html"},
                              {"claim": "规范无承诺书条款", "evidence": "644.html"}],
                          "task_override": [
                              {"key": "max_pages / compliance.max_body_pages", "value": 80,
                               "ruling": "2026-09-25 用户裁决", "scope": "仅本轮投稿"}]},
                      }]}})
    fresh = resolve_profile("comp_hw_next", {}, rules_file=fx)
    assert fresh.operative["cap"] is None, "新任务不继承单次80页"
    assert fresh.non_inherited_overrides and "2026-09-25" in fresh.non_inherited_overrides[0]["ruling"]
    by_name = {c["name"]: c for c in fresh.constraints}
    assert by_name["official_page_cap"]["status"] == "official_verified"
    declared = resolve_profile("comp_hw_next", {"contest": {"page_cap": 80}}, rules_file=fx)
    assert declared.operative["cap"] == 80 and declared.operative["status"] == "explicit_task"


# ── B-02：快照冻结 / 漂移 / pending_binding / unknown 不伪放行 ───────────────

def _make_session(tmp_path: Path, template: str, params: dict, *, catalog_templates=None):
    skills = tmp_path / "suite/skills"
    (skills / "demo").mkdir(parents=True, exist_ok=True)
    (skills / "demo" / "SKILL.md").write_text("Real task instructions.", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    templates = catalog_templates or [template, "non_contest_tpl"]
    catalog = {t: {"sub_steps": [{"skill_name": "demo", "output_files": ["result.txt"],
        "primary_output": "result.txt", "has_checkpoint": False,
        "metadata": {"skill_binding": {"main_required": True}}}]} for t in templates}
    runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
    wf = runner.start(template, tmp_path / "work", params)
    return store, runner, wf.id, ExecutionSession(runner, wf.id)


def test_start_freezes_snapshot_into_workflow_metadata(tmp_path):
    store, runner, wf_id, session = _make_session(tmp_path, "comp_huawei", {"agent": "x"})
    wf = store.get_workflow(wf_id)
    snap = wf.metadata.get("contest_profile_snapshot")
    assert isinstance(snap, dict) and snap["status"] == "bound"
    assert snap["contest_id"] == "comp_huawei"
    assert snap["profile_id"] == "comp_huawei_2026_electronic"
    # v2：华为无官方页限（unknown），快照如实无口径；80 只留 non_inherited 留痕
    assert snap["max_body_pages"] is None and snap["max_total_pages"] is None
    assert snap["operative"]["cap"] is None and snap["operative"]["status"] == "task_override"
    assert any(o.get("value") == 80 for o in snap["non_inherited_overrides"])
    assert snap["rules_revision"].startswith("第23届"), "v2 快照版本用档案显式 rules_revision"
    assert snap.get("resolved_at")
    store.close()


def test_old_task_does_not_drift_when_global_rules_change(tmp_path, monkeypatch):
    """修改全局档案后旧任务消费冻结快照：口径不变，漂移仅显式提示重验。
    P1 安全化（总调度 2026-09-27）：复制 comp_rules 到 tmp_path 副本，模块级
    RULES_FILE 指向副本（runner 启动解析与 session 漂移检测同源），禁止
    backup/restore 生产真源。"""
    import shutil
    rules_copy = tmp_path / "comp_rules.json"
    shutil.copyfile(ROOT / "engine/modex-core/comp_rules.json", rules_copy)
    # 摘掉华为 profile 显式 rules_revision → 快照版本回落 sha256（与 session 漂移
    # 检测的摘要比对同构；显式版本串与摘要不等是 B 第八轮已知的既有消费行为）
    data0 = json.loads(rules_copy.read_text(encoding="utf-8"))
    data0["contests"]["comp_huawei"]["profiles"][0].pop("rules_revision", None)
    rules_copy.write_text(json.dumps(data0, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(cp, "RULES_FILE", rules_copy)
    store, runner, wf_id, session = _make_session(tmp_path, "comp_huawei", {"agent": "x"})
    before = session.context()["contest_profile"]
    assert before["profile_id"] == "comp_huawei_2026_electronic"
    assert "rules_drift" not in before, "副本未改动前不得报漂移"
    assert before["operative"]["cap"] is None and before["operative"]["status"] == "task_override"
    # 修改 tmp_path 副本：模拟 comp_rules 被 E 窗 Phase-2 重写（生产文件不触碰）
    data = json.loads(rules_copy.read_text(encoding="utf-8"))
    prof = data["contests"]["comp_huawei"]["profiles"][0]
    prof["constraints"] = [c for c in prof["constraints"] if c.get("kind") != "page_limit"]
    prof["constraints"].append({"id": "hw-page-limit", "kind": "page_limit", "status": "verified",
                                "value": {"basis": "body", "limit": 66}, "scope": "第N届"})
    rules_copy.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    cp._RULES_CACHE.clear()
    after = session.context()["contest_profile"]
    assert after["operative"]["cap"] is None, "旧任务不得静默漂移到新全局口径（66 不入旧任务）"
    assert after["rules_drift"]["detected"] is True, "档案变化必须显式提示（规则变化优先重验）"
    assert "重验" in after["rules_drift"]["guidance"]
    store.close()


def test_legacy_contest_workflow_is_pending_binding_not_faked(tmp_path):
    """快照机制启用前的赛事工作流：显式待绑定，不拿现盘规则冒充历史快照。"""
    skills = tmp_path / "s2"; (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text("x", encoding="utf-8")
    store = WorkflowStore(tmp_path / "wf.sqlite")
    catalog = {"comp_cumcm": {"sub_steps": [{"skill_name": "demo", "output_files": ["o.txt"],
        "primary_output": "o.txt", "has_checkpoint": False, "metadata": {}}]}}
    runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
    # v2：cumcm 双 profile 须维度精确化（不变式12）
    params = {"contest": {"edition": "2026", "submission_form": "electronic"}}
    wf = runner.start("comp_cumcm", tmp_path / "w", params)
    # 模拟"机制启用前创建"：抹掉启动时快照
    store._connection.execute("UPDATE workflows SET metadata = ? WHERE id = ?",
                              (json.dumps({"workspace": str(tmp_path / "w"), "params": params,
                                           "template": "comp_cumcm"}), wf.id))
    store._connection.commit()
    session = ExecutionSession(runner, wf.id)
    view = session.context()["contest_profile"]
    assert view["status"] == "pending_binding" and view["contest_hint"] == "comp_cumcm"
    assert "max_body_pages" not in view, "不冒充快照：现盘口径不得假借历史名义下发"
    # 终审结论：待绑定 → unknown，不伪放行
    from engine.audit_store import build_final_audit_report
    report = build_final_audit_report(tmp_path / "w", tmp_path, Path(store.db_path), workflow_id=wf.id)
    assert report["gate_outcomes"]["contest_compliance"] == "unknown"
    assert report["delivery_decision"] == "blocked"
    store.close()


def test_compliance_conclusion_matrix():
    assert compliance_conclusion(None, contest_intent=False)["verdict"] == "not_applicable"
    assert compliance_conclusion(None, contest_intent=True)["verdict"] == "unknown"
    assert compliance_conclusion({"status": "pending_binding"}, contest_intent=True)["verdict"] == "unknown"
    bound_ok = {"status": "bound", "constraints": [
        {"name": "page_cap", "status": "official_verified"},
        {"name": "pledge_page", "status": "task_override"}]}
    assert compliance_conclusion(bound_ok, contest_intent=True)["verdict"] == "pass"
    bound_unknown = {"status": "bound", "constraints": [
        {"name": "page_cap", "status": "unverified"}]}
    out = compliance_conclusion(bound_unknown, contest_intent=True)
    assert out["verdict"] == "unknown" and out["unknown_constraints"][0]["name"] == "page_cap"


def test_rules_digest_changes_with_file(tmp_path):
    rules_file = tmp_path / "comp_rules.json"
    rules_file.write_text(json.dumps({"comp_x": {"name": "X", "max_pages": 10}}), encoding="utf-8")
    first = resolve_profile("comp_x", {}, rules_file=rules_file)
    assert first.gate_page_cap == 10
    rules_file.write_text(json.dumps({"comp_x": {"name": "X", "max_pages": 50}}), encoding="utf-8")
    second = resolve_profile("comp_x", {}, rules_file=rules_file)
    assert second.gate_page_cap == 50
    assert first.rules_revision != second.rules_revision, "规则文件变化必须可检（重验/重算分界证据）"


def test_load_entry_converged_loader_and_compliance_helper():
    """v2：load_entry 返回赛事级条目（profiles 未选择——脚本路径不猜口径）；
    compliance 视图只在 profile 选中后经 resolve_profile 构造。"""
    entry = load_entry("comp_cumcm")
    assert isinstance(entry.get("profiles"), list) and len(entry["profiles"]) == 2
    assert not isinstance(entry.get("compliance"), dict), "v2 条目无顶层 compliance 块"
    hw = load_entry("comp_huawei")
    assert isinstance(hw.get("migration_evidence"), list), "华为历史裁决留痕在 migration_evidence"
    with pytest.raises(ContestProfileError):
        load_entry("comp_nonexistent")
    assert cp.compliance_profile(None) is None
    assert cp.compliance_profile({"max_pages": 1}) is None
    assert cp.compliance_profile({"compliance": {"pledge_page": "required"}}) == {"pledge_page": "required"}


# ── 消费者端到端：context 三态 / runner 双源统一 ─────────────────────────────

def test_context_delivers_only_current_applicable_profile(tmp_path):
    store, runner, wf, session = _make_session(tmp_path, "comp_huawei", {"agent": "executor-agent"})
    ctx = session.context()
    profile = ctx["contest_profile"]
    assert profile["contest_id"] == "comp_huawei"
    assert profile["profile_id"] == "comp_huawei_2026_electronic"
    assert profile["operative"]["cap"] is None, "v2 华为无官方页限，80 非继承不下发"
    assert "comp_cumcm" not in json.dumps(profile, ensure_ascii=False)
    store.close()


def test_context_none_for_non_contest_template(tmp_path):
    store, runner, wf, session = _make_session(tmp_path, "non_contest_tpl", {"agent": "x"})
    assert session.context()["contest_profile"] is None
    store.close()


def test_context_explicit_unknown_override_fails_loudly(tmp_path):
    with pytest.raises(ContestProfileError):
        _make_session(tmp_path, "comp_cumcm", {"agent": "x", "contest": {"id": "comp_huawai"}})


def test_runner_unifies_early_check_and_compile_page_source(tmp_path, monkeypatch):
    """双源修复：早检与编译页检消费同一份快照口径，不再各取一处。"""
    import pymupdf
    from engine.artifact_manifest import FingerprintSession
    skills = tmp_path / "s3"; (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text("x", encoding="utf-8")
    store = WorkflowStore(tmp_path / "wf3.sqlite")
    catalog = {"generic_tpl": {"sub_steps": [{"skill_name": "demo", "output_files": ["o.txt"],
        "primary_output": "o.txt", "has_checkpoint": False,
        "metadata": {"revalidate_paper_pages": True, "quick_gates": True}}]}}
    runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
    wf = runner.start("generic_tpl", tmp_path / "w3", {"contest": {"id": "comp_mcm"}})
    snap = store.get_workflow(wf.id).metadata["contest_profile_snapshot"]
    assert snap["contest_id"] == "comp_mcm" and snap["operative"]["scope"] == "total"
    # 编译页检（原第二真源位）现消费快照 contract：MCM 总口径 25；
    # 不得再绕过快照直调 load_entry/get_comp_rules 取现盘原始条目
    import engine.quality_gates as gates
    seen = {}
    monkeypatch.setattr(gates, "get_comp_rules", lambda name: seen.__setitem__("name", name) or (_ for _ in ()).throw(AssertionError("绕过快照直调 get_comp_rules")))
    (tmp_path / "w3/paper").mkdir(parents=True)
    with pymupdf.open() as doc:
        for _ in range(2):
            doc.new_page().insert_text((72, 72), "page")
        (tmp_path / "w3/paper/main.pdf").write_bytes(doc.tobytes())
    action = runner.next_action(wf.id).action
    step = store.get_step(action.step_id)
    result = type("R", (), {"ok": True, "artifacts": ["o.txt"], "step_id": action.step_id,
                            "attempt_id": step.attempt_id, "expected_revision": action.expected_revision,
                            "request_id": "x", "metadata": {}})()
    report = runner._validate_step(wf, step, result, FingerprintSession(tmp_path / "w3"))[0]
    assert seen == {}, "消费者不得绕过快照取现盘原始条目"
    pages = report["checks"]["quality:paper_pages"]
    assert pages["ok"] and pages["page_cap_scope"] == "total"
    assert pages["page_cap_status"] == "official_verified", "v2 MCM 25 带内已核验"
    early = report["checks"]["quality:early_quality"]
    assert early["max_pages_effective"] == 25, "早检与编译页检消费同一份快照口径"
    store.close()


def test_step_profile_conflicting_with_bound_identity_is_rejected(tmp_path):
    """步骤显式合规口径与绑定身份冲突 → 验收失败，不以步骤配置改写赛事。"""
    from engine.artifact_manifest import FingerprintSession
    skills = tmp_path / "s4"; (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text("x", encoding="utf-8")
    store = WorkflowStore(tmp_path / "wf4.sqlite")
    catalog = {"comp_cumcm": {"sub_steps": [{"skill_name": "demo", "output_files": ["o.txt"],
        "primary_output": "o.txt", "has_checkpoint": False,
        "metadata": {"quick_gates": True, "compliance_profile": "comp_huawei"}}]}}
    runner = WorkflowRunner(store, catalog, skills, audit_root=tmp_path)
    wf = runner.start("comp_cumcm", tmp_path / "w4",
                      {"contest": {"edition": "2026", "submission_form": "electronic"}})
    action = runner.next_action(wf.id).action
    step = store.get_step(action.step_id)
    (tmp_path / "w4/o.txt").write_text("result", encoding="utf-8")
    result = type("R", (), {"ok": True, "artifacts": ["o.txt"], "step_id": action.step_id,
                            "attempt_id": step.attempt_id, "expected_revision": action.expected_revision,
                            "request_id": "x", "metadata": {}})()
    report = runner._validate_step(wf, step, result, FingerprintSession(tmp_path / "w4"))[0]
    assert not report["checks"]["contest_identity"]["ok"]
    assert "冲突" in report["checks"]["contest_identity"]["reason"]
    store.close()


# ── v2 候选消费验证（总调度收口 2026-09-27）：profiles 选择为唯一消费路径 ──────
# 生产真源仍 v1（切换是 E 窗的活、须总调度放行）；本段把 COMP_RULES_PATH 指向
# v2 合并候选，验证 B 消费端在候选上的选择/三态/快照绑定/非继承语义。

import os  # noqa: E402

V2_CANDIDATE = Path(os.environ.get(
    "COMP_RULES_PATH",
    "D:/Desktop/优化分析工程/outputs/collaboration/E/draft_comp_rules_v2.json"))

_v2_on_disk = pytest.mark.skipif(not V2_CANDIDATE.is_file(),
                                 reason="v2 合并候选不在盘上（E 窗产物）")


@_v2_on_disk
def test_v2_candidate_unwraps_contests_and_has_22_ids():
    ids = cp.known_contest_ids(V2_CANDIDATE)
    assert len(ids) == 22, f"候选赛事数漂移: {len(ids)}"
    assert "comp_cumcm" in ids and "comp_huawei" in ids
    assert "contests" not in ids and "sources" not in ids, "包裹键不得当作赛事ID"


@_v2_on_disk
def test_v2_profiles_selection_picks_real_corresponding_rules():
    elec = cp.resolve_profile("comp_cumcm", {"contest": {"edition": "2026",
                                                         "submission_form": "electronic"}},
                              rules_file=V2_CANDIDATE)
    assert elec.profile_id == "comp_cumcm_2026_electronic"
    assert elec.max_body_pages == 30 and elec.max_total_pages is None
    assert elec.gate_page_cap == 30 and elec.gate_page_scope == "body"
    assert elec.page_cap_status == "official_verified", "带内 verified 性质如实升为已核验"
    assert elec.compliance.get("pledge_page") == "forbidden_in_electronic", \
        "v2 承诺书约束须映射为脚本消费者的等效 compliance 视图"
    paper = cp.resolve_profile("comp_cumcm", {"contest": {"submission_form": "paper"}},
                               rules_file=V2_CANDIDATE)
    assert paper.profile_id == "comp_cumcm_2026_paper", "电子/纸质是两个真实规则档，不共用"


@_v2_on_disk
def test_v2_profiles_selection_never_falls_back():
    with pytest.raises(ContestProfileError):
        cp.resolve_profile("comp_cumcm", {"contest": {"edition": "2025"}}, rules_file=V2_CANDIDATE)
    with pytest.raises(ContestProfileError):
        cp.resolve_profile("comp_cumcm", {}, rules_file=V2_CANDIDATE), \
            "双 profile 无请求须要求精确化，不得静默取第一条"


@_v2_on_disk
def test_v2_constraint_band_triple_state_closed_and_sourced():
    raw = json.loads(V2_CANDIDATE.read_text(encoding="utf-8"))
    sources = set(raw["sources"].keys())
    prof = cp.resolve_profile("comp_cumcm", {"contest": {"submission_form": "electronic"}},
                              rules_file=V2_CANDIDATE)
    assert prof.constraints, "v2 选中的 profile 须携带约束带"
    for c in prof.constraints:
        assert c["status"] in {"verified", "unknown", "not_applicable"}, \
            f"约束三态封闭，实得 {c.get('name')}: {c.get('status')}"
        if c["status"] == "unknown":
            assert c["value"] is None, f"unknown 约束 value 须为 null: {c.get('name')}"
        for sid in c["source_ids"]:
            assert sid in sources, f"source_ids 须可解析到来源登记表: {sid}"


@_v2_on_disk
def test_v2_snapshot_binds_explicit_rules_revision():
    prof = cp.resolve_profile("comp_mcm", {}, rules_file=V2_CANDIDATE)
    assert prof.profile_id == "comp_mcm_2027_electronic"
    assert prof.max_total_pages == 25 and prof.max_body_pages is None, "MCM 2027 是全PDF计"
    assert prof.gate_page_cap == 25 and prof.gate_page_scope == "total"
    assert prof.rules_revision.startswith("2027 届规则"), \
        "快照版本标识须用档案显式 rules_revision，不是 sha256 回落"
    snap = prof.to_snapshot()
    assert snap["status"] == "bound" and snap["profile_id"] == prof.profile_id
    assert snap["rules_revision"] == prof.rules_revision
    assert snap["source"]["selection"]["selection_dimension"] == "profiles"


@_v2_on_disk
def test_v2_task_ruling_not_inherited_by_new_tasks():
    huawei = cp.resolve_profile("comp_huawei", {}, rules_file=V2_CANDIDATE)
    assert huawei.operative["cap"] is None, "migration_evidence 的任务 80 不得成为新任务默认口径"
    assert huawei.operative["status"] == "task_override"
    assert huawei.non_inherited_overrides, "非继承必须留痕披露"
    ov = huawei.non_inherited_overrides[0]
    assert ov["value"] == 80 and "80" in ov["ruling"]
    declared = cp.resolve_profile("comp_huawei", {"contest": {"page_cap": 80}},
                                  rules_file=V2_CANDIDATE)
    assert declared.operative["cap"] == 80 and declared.operative["status"] == "explicit_task", \
        "在途链显式声明 80 仍可用（任务口径只影响当前任务）"


@_v2_on_disk
def test_v2_script_loader_without_selection_degrades_honestly():
    """脚本消费者 load_entry（无请求维度）不选 profile：无口径即无口径，不猜不兜底。"""
    entry = cp.load_entry("comp_huawei", V2_CANDIDATE)
    contract = cp.page_cap_contract(entry)
    assert contract["max_body_pages"] is None and contract["max_total_pages"] is None
    op = cp.resolve_operative_cap(contract, None)
    assert op["cap"] is None, "赛事级条目未经 profiles 选择，页检须 SKIP 而非编口径"
