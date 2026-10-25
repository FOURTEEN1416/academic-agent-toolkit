"""P4 模板契约（裁决 6.6-A）：PAPER_SCORING 显式 3 真 / 16 假 + promotion 条件化。

覆盖三件事：
1. 19 条同时含 comp-paper-zh + comp-editor 的链必须**显式**声明 ``paper_scoring``
   （3 true / 16 false，false 必须带理由），true 链的写作步必须真的把
   ``PAPER_SCORING.json`` 列入 ``output_files`` 并声明可程序化评分合同；
2. 显式 ``false`` 与「漏写」可区分：漏写按 legacy 口径仍要求该文件；含
   comp-editor 的英文链（无 comp-paper-zh、无评分生产者）同样必须显式 false；
3. promotion 的 ``_REVIEW_INPUTS`` 按模板声明条件化：true 链缺件记 missing，
   false 链不要求、不记 missing。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.promotion import PromotionError, freeze_candidate  # noqa: E402
from engine.template_resolver import resolve_template, template_paper_scoring  # noqa: E402
from engine.workflow_store import WorkflowStore  # noqa: E402

TEMPLATES_PATH = ROOT / "engine" / "modex-core" / "templates.json"
CATALOG = json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))
PAPER_SCORING = "PAPER_SCORING.json"
VERDICT = "COMP_REVIEW_VERDICT.json"

TRUE_CHAINS = {"comp_cumcm", "comp_huawei", "comp_csf"}
FALSE_CHAINS = {
    "comp_apmcm_zh", "comp_mathorcup", "comp_stats", "comp_teddy", "comp_certcup",
    "comp_huazhong", "comp_huadong", "comp_wuyi", "comp_shuwei", "comp_zhongqing",
    "comp_yangtze", "comp_diangong", "comp_shenzhen", "comp_huashu", "comp_tianfu",
    "comp_liaoning",
}
# 含 comp-editor 但写作步是 comp-paper-en 的英文链：无评分生产者，必须显式 false，
# 不能让 legacy 缺省 True 把不存在的文件变成候选冻结的隐性要求。
ENGLISH_EDITOR_CHAINS = {"comp_mcm", "comp_apmcm", "comp_certcup_en", "comp_shuwei_en"}


def _dual_chains() -> list[str]:
    chains = []
    for name, template in CATALOG.items():
        if not name.startswith("comp_"):
            continue
        skills = {step.get("skill_name") for step in template.get("sub_steps") or []}
        if {"comp-paper-zh", "comp-editor"} <= skills:
            chains.append(name)
    return sorted(chains)


def _step(template: str, skill_name: str) -> dict:
    matches = [s for s in CATALOG[template]["sub_steps"] if s.get("skill_name") == skill_name]
    assert len(matches) == 1, f"{template} 的 {skill_name} 步数异常: {len(matches)}"
    return matches[0]


# ── 声明矩阵（19 条链） ────────────────────────────────────────────────

def test_dual_chain_population_matches_audit_19():
    chains = _dual_chains()
    assert len(chains) == 19, chains
    assert set(chains) == TRUE_CHAINS | FALSE_CHAINS


def test_every_dual_chain_declares_paper_scoring_explicitly():
    missing = [name for name in _dual_chains() if "paper_scoring" not in CATALOG[name]]
    assert not missing, f"以下链漏写显式 paper_scoring 声明: {missing}"


def test_declaration_matrix_is_three_true_sixteen_false():
    declared_true = {name for name in _dual_chains() if CATALOG[name].get("paper_scoring") is True}
    declared_false = {name for name in _dual_chains() if CATALOG[name].get("paper_scoring") is False}
    assert declared_true == TRUE_CHAINS
    assert declared_false == FALSE_CHAINS
    assert declared_true | declared_false == set(_dual_chains())


def test_every_declaration_is_boolean_and_false_carries_reason():
    for name, template in CATALOG.items():
        if "paper_scoring" not in template:
            continue
        assert isinstance(template["paper_scoring"], bool), f"{name} 的 paper_scoring 非布尔"
        if template["paper_scoring"] is False:
            reason = template.get("paper_scoring_reason")
            assert isinstance(reason, str) and reason.strip(), f"{name} 显式 false 缺理由"


def test_true_chains_commit_paper_scoring_in_writer_outputs():
    for name in TRUE_CHAINS:
        outputs = _step(name, "comp-paper-zh")["output_files"]
        assert PAPER_SCORING in outputs, f"{name} 声明 true 但写作步未承诺产出该文件"


@pytest.mark.parametrize("template", sorted(TRUE_CHAINS))
def test_true_chains_declare_machine_parseable_scoring_contract(template):
    """评分合同不只靠「文件存在」：true 链必须挂载解析器检查器。"""
    from engine.quality_gates import auto_checks_for
    mounted = {entry["name"] for entry in auto_checks_for(template, "comp-paper-zh")}
    assert "paper_scoring_contract" in mounted, template
    assert template_paper_scoring(template, CATALOG) is True


def test_empty_scoring_json_is_rejected_by_scoring_parser(tmp_path):
    from engine.quality_gates import QualityGate
    (tmp_path / PAPER_SCORING).write_text("{}", encoding="utf-8")
    rejected = QualityGate(tmp_path).check_paper_scoring_contract()
    assert rejected["status"] == "fail"
    assert "scores" in rejected["reason"]
    # 非法 JSON 同样不合格（不是「文件存在即通过」）
    (tmp_path / PAPER_SCORING).write_text("{not json", encoding="utf-8")
    malformed = QualityGate(tmp_path).check_paper_scoring_contract()
    assert malformed["status"] == "fail" and "不可解析" in malformed["reason"]
    # 合法评分合同（三字段 + 九维明细）通过
    (tmp_path / PAPER_SCORING).write_text(json.dumps({
        "scores": {f"dim_{index}": {"score": 4, "evidence": f"§{index}"} for index in range(9)},
        "weighted_total": 4.0,
        "fatal_dimensions": [],
        "selfcheck_failures": [],
    }, ensure_ascii=False), encoding="utf-8")
    accepted = QualityGate(tmp_path).check_paper_scoring_contract()
    assert accepted["status"] == "pass", accepted["reason"]
    assert accepted["dimension_count"] == 9


def test_english_editor_chains_declare_paper_scoring_false_explicitly():
    for name in ENGLISH_EDITOR_CHAINS:
        assert CATALOG[name]["paper_scoring"] is False, (
            f"{name} 含 comp-editor 但无评分生产者，必须显式 false")
        assert CATALOG[name]["paper_scoring_reason"].strip(), name
        assert template_paper_scoring(name, CATALOG) is False, name
    # 反向：所有含 comp-editor 的 comp_* 链不得再依赖 legacy 缺省
    holes = []
    for name, template in CATALOG.items():
        if not name.startswith("comp_"):
            continue
        skills = {step.get("skill_name") for step in template.get("sub_steps") or []}
        if "comp-editor" in skills and "paper_scoring" not in template:
            holes.append(name)
    assert not holes, f"含 comp-editor 但未显式声明 paper_scoring: {holes}"


def test_false_chains_do_not_commit_paper_scoring_in_writer_outputs():
    for name in FALSE_CHAINS:
        outputs = _step(name, "comp-paper-zh")["output_files"]
        assert PAPER_SCORING not in outputs, f"{name} 声明 false 却仍承诺产出该文件"


@pytest.mark.parametrize("template", ["comp_cumcm", "comp_huawei", "comp_csf"])
def test_review_step_declares_verdict(template):
    outputs = _step(template, "comp-review")["output_files"]
    assert "COMP_REVIEW.md" in outputs
    assert VERDICT in outputs, f"{template} 的 comp-review 未声明 {VERDICT}"


@pytest.mark.parametrize("template", sorted(TRUE_CHAINS))
def test_editor_step_does_not_redeclare_scoring(template):
    """评分件是编辑步的输入而非改稿产物：不进 comp-editor 的 revalidate 输出面。"""
    steps = {step["skill_name"]: step for step in resolve_template(template, {}, CATALOG)}
    assert PAPER_SCORING in steps["comp-paper-zh"]["output_files"]
    assert PAPER_SCORING not in steps["comp-editor"]["output_files"]
    assert steps["comp-editor"]["output_files"] == [
        "EDITOR_CHANGELOG.md", "paper/main.tex", "CONSISTENCY_REPORT.json", "paper/main.pdf"]


def test_resolver_honours_revalidate_exclude_outputs():
    catalog = {"pipeline": {"sub_steps": [
        {"skill_name": "writer", "output_files": ["paper.md", "SCORE.json"],
         "primary_output": "paper.md"},
        {"skill_name": "editor", "output_files": ["EDITOR_CHANGELOG.md"],
         "primary_output": "EDITOR_CHANGELOG.md",
         "revalidates_outputs_from": ["writer"],
         "revalidate_exclude_outputs": ["SCORE.json"]},
    ]}}
    steps = resolve_template("pipeline", {}, catalog)
    assert steps[1]["output_files"] == ["EDITOR_CHANGELOG.md", "paper.md"]


# ── comp-editor 正文条件措辞 ───────────────────────────────────────────

def test_comp_editor_wording_is_conditional():
    text = (ROOT / "skills" / "comp-editor" / "SKILL.md").read_text(encoding="utf-8")
    assert "paper_scoring: true" in text
    assert "paper_scoring: false" in text
    assert "No-verdict fallback" in text
    assert "comp_stats" in text
    assert "a missing or unparseable `PAPER_SCORING.json` is equally blocking" not in text


def test_comp_stats_reason_does_not_claim_a_verdict_producer_it_lacks():
    """comp_stats 没有 comp-review → COMP_REVIEW_VERDICT.json 无生产者，理由不得写实。"""
    skills = {step.get("skill_name") for step in CATALOG["comp_stats"]["sub_steps"]}
    assert "comp-review" not in skills
    reason = CATALOG["comp_stats"]["paper_scoring_reason"]
    assert "没有 comp-review 步" in reason
    assert "COMP_REVIEW_VERDICT.json 无生产者" in reason


# ── 解析器契约 ─────────────────────────────────────────────────────────

def test_undeclared_template_keeps_legacy_requirement():
    # 未显式声明的模板（含自定义链）仍按 legacy 口径要求该文件。
    assert template_paper_scoring("legacy_demo", {"legacy_demo": {"sub_steps": []}}) is True
    # 英文链已显式 false，不再落入 legacy 缺省
    assert template_paper_scoring("comp_mcm", CATALOG) is False


def test_non_boolean_declaration_is_rejected():
    with pytest.raises(ValueError, match="paper_scoring"):
        template_paper_scoring("bad", {"bad": {"paper_scoring": "false"}})


# ── promotion 条件化路径（真实模板 + 真实 store） ──────────────────────

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _freeze(tmp_path: Path, template: str, *, include_scoring: bool,
            catalog: dict | None = None):
    workspace = tmp_path / "workspace"
    (workspace / "paper").mkdir(parents=True)
    (workspace / ".engine").mkdir()
    (workspace / ".engine" / "approvers.json").write_text(
        '{"approvers": ["operator"], "require_human": true}', encoding="utf-8")
    main_bytes = b"accepted main pdf fixture"
    (workspace / "paper" / "main.pdf").write_bytes(main_bytes)

    artifacts = [{"name": "main.pdf", "path": "paper/main.pdf",
                  "metadata": {"sha256": _sha(main_bytes)}}]
    manifest = [{"path": "paper/main.pdf", "sha256": _sha(main_bytes)}]
    if include_scoring:
        scoring_bytes = b'{"scores": {}, "weighted_total": 0}'
        (workspace / PAPER_SCORING).write_bytes(scoring_bytes)
        artifacts.append({"name": PAPER_SCORING, "path": PAPER_SCORING,
                          "metadata": {"sha256": _sha(scoring_bytes)}})
        manifest.append({"path": PAPER_SCORING, "sha256": _sha(scoring_bytes)})

    store = WorkflowStore(tmp_path / "workflow.sqlite")
    workflow = store.create_workflow(template, {
        "workspace": str(workspace), "params": {}, "template": template,
        "execution_contract": {"tier": "explore", "version": 1}})
    step = store.add_steps(workflow.id, [{"name": "comp-code", "metadata": {}}])[0]
    running = store.transition_step(step.id, "running")
    payload = {"path": "paper/main.pdf", "operation": "write", "declared_inputs": [],
               "dependency_policy": "explicit-declared-inputs-v1", "inputs_snapshot": {},
               "outputs_snapshot": {"paper/main.pdf": _sha(main_bytes)},
               "previous_sha256": None}
    timestamp = "2026-10-25T00:00:00+00:00"
    store._connection.execute(
        "INSERT INTO execution_operations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("op-root", workflow.id, step.id, running.attempt_id, "write", "succeeded",
         "write:paper/main.pdf", "", json.dumps(payload, ensure_ascii=True, sort_keys=True),
         timestamp, timestamp))
    store._connection.commit()
    store.transition_step_with_checkpoint(
        workflow.id, step.id, "completed", {"status": "completed"},
        artifacts=artifacts,
        event={"type": "step_completed", "manifest": {"artifacts": manifest}},
        expected_revision=running.revision, finalize_if_complete=True)

    return freeze_candidate(
        store, workflow.id, ["paper/main.pdf"], by="operator", template=template,
        catalog=catalog if catalog is not None else CATALOG,
        project_root=ROOT.parent, skills_root=ROOT / "skills",
        rules_root=ROOT / "engine" / "modex-core",
    )


@pytest.mark.parametrize("template", sorted(TRUE_CHAINS))
def test_true_chain_missing_scoring_is_recorded(tmp_path, template):
    candidate = _freeze(tmp_path, template, include_scoring=False)
    assert candidate.lineage["paper_scoring_required"] is True
    assert "review_input:PAPER_SCORING.json" in candidate.missing


@pytest.mark.parametrize("template", sorted(TRUE_CHAINS))
def test_true_chain_present_scoring_is_frozen(tmp_path, template):
    candidate = _freeze(tmp_path, template, include_scoring=True)
    assert candidate.lineage["paper_scoring_required"] is True
    assert "review_input:PAPER_SCORING.json" not in candidate.missing
    assert candidate.inputs[PAPER_SCORING]["kind"] == "review_input"


@pytest.mark.parametrize("template", sorted(ENGLISH_EDITOR_CHAINS))
def test_english_chain_missing_scoring_does_not_block(tmp_path, template):
    """英文链显式 false 后，promotion 不再要求它们没有生产者的评分件。"""
    candidate = _freeze(tmp_path, template, include_scoring=False)
    assert candidate.lineage["paper_scoring_required"] is False
    assert "review_input:PAPER_SCORING.json" not in candidate.missing
    assert PAPER_SCORING not in candidate.inputs


@pytest.mark.parametrize("template", sorted(FALSE_CHAINS))
def test_false_chain_missing_scoring_does_not_block(tmp_path, template):
    candidate = _freeze(tmp_path, template, include_scoring=False)
    assert candidate.lineage["paper_scoring_required"] is False
    assert "review_input:PAPER_SCORING.json" not in candidate.missing
    assert PAPER_SCORING not in candidate.inputs
    assert PAPER_SCORING not in candidate.frozen_versions


def test_false_chain_tolerates_scoring_when_present(tmp_path):
    candidate = _freeze(tmp_path, "comp_stats", include_scoring=True)
    assert candidate.lineage["paper_scoring_required"] is False
    assert "review_input:PAPER_SCORING.json" not in candidate.missing


def test_promotion_rejects_non_boolean_declaration(tmp_path):
    bad = {**CATALOG["comp_cumcm"], "paper_scoring": "true"}
    with pytest.raises(PromotionError, match="paper_scoring"):
        _freeze(tmp_path, "comp_cumcm", include_scoring=False,
                catalog={"comp_cumcm": bad})
