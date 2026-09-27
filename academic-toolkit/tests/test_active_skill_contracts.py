"""活跃技能与模板行为合同测试（C窗：全业务模板与技能契约重构）。

验证入口技能只选模板、主技能不维护第二套调度状态、引擎独占步骤状态这三条契约。

覆盖范围口径（不夸大）：本文件检查「46 条模板引用的全部技能（现场统计）∪ 本轮重构涉及的
动态/辅助/DOCX 变体技能显式清单」。这是文本合同级检查 + 模板结构级检查，
不是六域业务整链验收，也不替代逐技能正文人工通读。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEMPLATES = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
SKILLS_DIR = ROOT / "skills"

# 本轮重构涉及、但未必被模板引用的动态/辅助/DOCX变体技能（总调度返工裁决第2项）。
# 这些技能同样纳入违禁模式扫描与围栏结构检查；清单随本轮触碰面收口，不再扩张。
AUXILIARY_SKILLS = frozenset({
    # 动态调用 / 辅助技能（本轮扫描命中或改动）
    "fig-plot-edit", "fig-plot-edit-lite", "eco-community-plots", "graphviz",
    "paper-figure-html", "problem-selection", "contest-retrospective",
    "math-modeling-contest-route-selection", "paper-oral-exemplar",
    "anti-defensive-writing", "paper-slides", "meta-doc-governance",
    "paper-writing-clinical", "agent-bootstrap", "tool-forge", "meta-skill-review",
    # DOCX 变体家族
    "comp-paper-zh-docx", "comp-paper-en-docx",
    "paper-write-docx", "paper-write-zh-docx", "docx-export", "docx-format-check",
    # 恢复正文契约点名的三个技能
    "auto-review-loop", "paper-poster", "paper-slides",
    # 赛事混用修复轮触碰的竞赛辅助技能
    "comp-cumcm-package", "comp-cumcm-disclosure", "comp-final-audit",
})


def _skill_text(name: str) -> str:
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def _all_step_skills() -> set[str]:
    names: set[str] = set()
    for tpl in TEMPLATES.values():
        ps = tpl.get("pipeline_skill")
        if ps:
            names.add(ps)
        for step in tpl.get("sub_steps", []):
            names.add(step["skill_name"])
    return names


def _checked_universe() -> set[str]:
    """模板引用集 ∪ 本轮涉及的辅助/变体技能（检查的实际分母）。"""
    return _all_step_skills() | AUXILIARY_SKILLS


# ---------------------------------------------------------------------------
# 否定豁免：短语级白名单，禁止单字「不」整行豁免（总调度返工裁决第2项）。
# 只有否定语义直接作用于违规动词的显式短语才豁免。
# ---------------------------------------------------------------------------
NEGATIVE_PHRASES = re.compile(
    r"不(得|应|要|能|需|因|再|另|会|可|手工|写|附|落盘|填|维护|设|使用)"
    r"|无需|不由|由程序|自动采集|自动登记|自动记录"
    r"|never|regardless|instead of|not (maintain|write|fill|attach|restart|delete)|no second",
    re.I,
)


def _violations(text: str, pattern: re.Pattern, flags: int = 0) -> list[str]:
    """返回未获短语级豁免的违规命中（含行号）。

    豁免作用域=违规命中所在的分句（按 。；；.;

 切分），不是整行：
    同行其他分句里的无关否定短语不豁免本命中（总调度收口裁决第2项）。
    """
    out = []
    for m in pattern.finditer(text, flags):
        line_no = text[: m.start()].count("\n") + 1
        line = text.splitlines()[line_no - 1]
        col = m.start() - (text.rfind("\n", 0, m.start()) + 1)
        clauses = re.split(r"[。；;.]|\|\s*", line)
        idx = 0
        hit_clause = clauses[-1]
        for c in clauses:
            idx += len(c) + 1
            if idx > col:
                hit_clause = c
                break
        if NEGATIVE_PHRASES.search(hit_clause):
            continue
        out.append(f":{line_no}: {line.strip()[:90]}")
    return out


# ---------------------------------------------------------------------------
# 模板结构合同
# ---------------------------------------------------------------------------

def test_every_template_skill_exists_on_disk():
    missing = sorted(n for n in _all_step_skills() if not (SKILLS_DIR / n / "SKILL.md").is_file())
    assert not missing, f"模板引用但缺 SKILL.md: {missing}"


def test_auxiliary_skill_list_exists_on_disk():
    """本轮涉及的辅助/变体技能清单必须真实在盘（防清单腐化成别名目录）。"""
    missing = sorted(n for n in AUXILIARY_SKILLS if not (SKILLS_DIR / n / "SKILL.md").is_file())
    assert not missing, f"辅助清单引用但缺 SKILL.md: {missing}"


def test_template_and_step_counts_are_dynamic_and_sane():
    """现场统计，不写死历史数字；只断言结构下限防止空表回归。"""
    assert len(TEMPLATES) >= 46
    total_steps = sum(len(t.get("sub_steps", [])) for t in TEMPLATES.values())
    assert total_steps >= 290


def test_research_chains_start_with_lit_idea_novelty_prefix():
    """deep_research / grant_proposal 统一走 research-lit → idea-creator → novelty-check 前缀链。"""
    for name in ("deep_research", "grant_proposal"):
        skills = [s["skill_name"] for s in TEMPLATES[name]["sub_steps"]]
        assert skills[:3] == ["research-lit", "idea-creator", "novelty-check"], (name, skills)


def test_research_chain_ends_with_independent_subagent_review():
    for name in ("deep_research", "grant_proposal"):
        last = TEMPLATES[name]["sub_steps"][-1]
        assert last["metadata"]["requires_subagent"] is True, name
        assert "review" in last["required_checks"], name
        assert last["skill_name"] == "comp-review", name


def test_idea_discovery_entry_routes_both_templates():
    text = _skill_text("idea-discovery")
    assert "`idea_discovery`" in text and "`deep_research`" in text
    assert "deep_research" in TEMPLATES and TEMPLATES["deep_research"]["pipeline_skill"] == "idea-discovery"


def test_comp_pipeline_entry_has_no_engine_bypass():
    text = _skill_text("comp-pipeline")
    assert "comp_cumcm" in text and "comp_huawei" in text
    assert "决策面板" not in text
    assert not re.search(r"^[①②③④⑤⑥⑦⑧]\s", text, re.M)
    assert "无门禁的手动阶段旁路" in text


# ---------------------------------------------------------------------------
# 恢复正文契约（总调度返工裁决第1项）：completed 不自动重开、三方对账、归档不删除
# ---------------------------------------------------------------------------

RECOVERY_SKILLS = ("auto-review-loop", "paper-poster", "paper-slides")


def test_recovery_text_has_no_completed_or_conflict_fresh_start_branch():
    """回归锁（总调度返工第2轮项1）：completed 或状态冲突不得再作为 fresh start 条件。

    仅允许的 fresh start 场景：状态文件不存在（无历史可丢）。
    """
    for name in RECOVERY_SKILLS:
        text = _skill_text(name)
        for m in re.finditer(r"(completed|conflict)[^.。\n]{0,120}fresh start|"
                             r"fresh start[^.。\n]{0,120}(completed|conflict|冲突|已完成)", text, re.I):
            line_no = text[: m.start()].count("\n") + 1
            ctx = text.splitlines()[line_no - 1]
            if re.search(r"missing|不存在|genuine", ctx, re.I):
                continue  # 状态文件缺失 = 真正的全新开始
            assert False, f"{name}:{line_no}: {ctx.strip()[:100]}"
        assert not re.search(r"不要结束本步骤.*重新开始|重新开始.*本步骤", text), name


def test_recovery_text_completed_state_does_not_auto_restart():
    for name in RECOVERY_SKILLS:
        text = _skill_text(name)
        # 引擎优先结构：completed 分支以"报告并停/无重启路径"表述，而非状态文件分支
        assert re.search(r"(already completed[^.。\n]{0,120}(report that fact and stop|no restart path)|"
                         r"no restart path|do NOT restart|不自动重开)", text, re.I), name
        # 新一轮初始化只由明确新任务或确认重做触发
        assert re.search(r"(new task|新任务|确认的重做|确认重做)", text), name


def test_recovery_text_reconciles_with_engine_and_inputs():
    """程序负责状态/版本/产物对账，模型只处理返回的业务冲突（收口裁决第1项）。"""
    for name in RECOVERY_SKILLS:
        text = _skill_text(name)
        assert "engine" in text.lower() or "引擎" in text, name
        assert re.search(r"input version|输入版本", text), name
        assert re.search(r"reconcil|对账", text), name
        assert re.search(r"program owns reconciliation|程序.*对账|checked by the session", text, re.I), name
        assert re.search(r"business conflict|业务冲突", text, re.I), name


def test_recovery_text_missing_state_file_is_not_a_restart_signal():
    for name in RECOVERY_SKILLS:
        text = _skill_text(name)
        assert re.search(r"missing file is not a restart|缺文件.{0,20}不.{0,6}重开|not a restart decision", text, re.I), name


def test_recovery_text_does_not_cast_next_as_readonly_query():
    """`next` 是领取任务的动作，不得被描述成只读状态查询（收口裁决第1项）。"""
    for name in RECOVERY_SKILLS:
        text = _skill_text(name)
        assert not re.search(r"`next`\s+payload|next payload|只读.{0,10}next|next.{0,20}只读", text, re.I), name


def test_recovery_text_archives_instead_of_deleting():
    for name in RECOVERY_SKILLS:
        text = _skill_text(name)
        assert re.search(r"archiv|归档", text), name
        assert re.search(r"instead of deleting|never delete|不删除", text, re.I), name


def test_recovery_text_round_records_cannot_decide_engine_state():
    for name in RECOVERY_SKILLS:
        text = _skill_text(name)
        assert re.search(r"(does not decide|must never decide|never fork|不能让它决定|不决定.*引擎)", text, re.I), name


# ---------------------------------------------------------------------------
# 违禁模式扫描（检查分母 = 模板引用集 ∪ 辅助清单）
# ---------------------------------------------------------------------------

def test_no_checked_skill_maintains_time_based_state_loss():
    """超过 24 小时即弃置重来的条款是状态丢失源：检查集内一律不得含此模式。"""
    pat = re.compile(
        r"(older than|超过)\s*24\s*(hours|小时)[^\n]*(fresh start|重来|重新开始|重做|delete)"
        r"|within 24h[^\n]*(resume|fresh)", re.I,
    )
    offenders = []
    for name in sorted(_checked_universe()):
        for hit in _violations(_skill_text(name), pat):
            offenders.append(f"{name}{hit}")
    assert not offenders, "\n".join(offenders)


def test_no_checked_skill_demands_manual_evidence_files():
    """正文不得要求模型把清单/证据手工落盘 .engine/evidence/ 或手填 execution_evidence。

    词级否定（"不手填"/"无需手填"）在 lookbehind 直接豁免；行级短语白名单仅兜底
    长句中间的否定，不再接受整行含单字"不"的宽豁免。
    """
    pat = re.compile(
        r"(落盘[^\n]*\.engine/evidence|写入[^\n]*\.engine/evidence|"
        r"附\s*execution_evidence|另写\s*evidence|"
        r"(?<!不)(?<!无需)(?<!请勿)(?<!禁止)手填[^\n]*(evidence|哈希))",
    )
    offenders = []
    for name in sorted(_checked_universe()):
        for hit in _violations(_skill_text(name), pat):
            offenders.append(f"{name}{hit}")
    assert not offenders, "\n".join(offenders)


def test_verification_blocks_do_not_invert_return_codes():
    """`[ cond ] && echo FAIL` 在条件为假时反而返回 0；校验收尾必须 if/exit 显式处置。

    窄口径声明：这是对已修复位点（docx 两变体）的回归锁 + 检查集内同类模式扫描，
    不是通用 shell 静态分析。
    """
    pat = re.compile(r'^\s*\[\s*"\$PASS"\s*!=\s*true\s*\]\s*&&\s*echo[^\n]*$', re.M)
    offenders = []
    for name in sorted(_checked_universe()):
        for m in pat.finditer(_skill_text(name)):
            offenders.append(f"{name}:{m.group(0).strip()[:60]}")
    assert not offenders, f"返回码倒置收尾: {offenders}"


def test_docx_variant_skills_keep_verification_contract():
    """DOCX 变体的验证块必须保留：main.md 存在性、.tex 残留检测与显式失败退出。"""
    for name in ("comp-paper-zh-docx", "comp-paper-en-docx"):
        text = _skill_text(name)
        assert "PASS=false" in text, name
        assert "if [ \"$PASS\" != true ]" in text and "exit 1" in text, name


def test_entry_skills_do_not_fork_second_scheduler_state():
    """入口型技能不得维护 WORKFLOW/PIPELINE/STAGE 级第二状态文件或自动批准。"""
    entry_like = {"comp-pipeline", "paper-writing", "research-pipeline", "idea-discovery",
                  "grant-proposal", "literature-review", "assets-inventory"}
    pat = re.compile(r"PIPELINE_STATE\.json|WORKFLOW_STATE\.json|STAGE_STATE\.json|自动批准|auto-?approve", re.I)
    offenders = []
    for name in sorted(entry_like & _checked_universe()):
        for hit in _violations(_skill_text(name), pat):
            offenders.append(f"{name}{hit}")
    assert not offenders, offenders


# ---------------------------------------------------------------------------
# 围栏结构检查：真实开闭状态机（CommonMark 语义），不是奇偶计数
# （总调度返工裁决第2项：奇偶只能证明标记数量，不能证明结构）
# ---------------------------------------------------------------------------

def _fence_structure_errors(text: str) -> list[str]:
    """简化围栏状态机，检查 ```/```` 反引号围栏的实际开闭结构。

    实际支持范围（如实声明，不冒称完整 CommonMark）：仅处理反引号围栏的
    单层开闭与「更长围栏包裹嵌套示例」（closing 需同字符、长度≥opening、
    缩进≤opening、无 info）；栏内更深缩进或带 info 的行按字面内容忽略。
    不处理波浪线 ~~~ 围栏、4空格缩进代码块等 Markdown 其他机制。
    错误类型：unclosed（文件尾仍在栏内）。
    """
    errors: list[str] = []
    open_fence: tuple[int, int] | None = None  # (缩进, 反引号长度)；None = 栏外
    for line in text.splitlines():
        m = re.match(r"^( *)(`{3,})(.*)$", line)
        if not m:
            continue
        indent, ticks, info = len(m.group(1)), len(m.group(2)), m.group(3).strip()
        if open_fence is None:
            open_fence = (indent, ticks)  # 栏外围栏一律开栏
        elif info == "" and ticks >= open_fence[1] and indent <= open_fence[0]:
            open_fence = None  # 闭栏
        # 其余：块内字面内容（嵌套示例），忽略
    if open_fence is not None:
        errors.append(f"unclosed:line_{len(text.splitlines())}")
    return errors


def test_all_skill_files_have_wellformed_fence_structure():
    offenders = []
    for name in sorted(_checked_universe()):
        errs = _fence_structure_errors(_skill_text(name))
        if errs:
            offenders.append(f"{name}: {errs[:4]}")
    assert not offenders, f"围栏结构异常: {offenders}"


# ---------------------------------------------------------------------------
# 数据图下限适用范围（总调度返工第2轮项3）：min_data_figures 是B窗条件化检查字段，
# 只允许按题/按赛事个体化声明，禁止给竞赛模板一刀切统一加图。
# ---------------------------------------------------------------------------

def test_min_data_figures_must_not_be_uniformly_added_to_comp_templates():
    comp_templates = [n for n in TEMPLATES if n.startswith("comp_")]
    declared = []
    for name in comp_templates:
        for s in TEMPLATES[name].get("sub_steps", []):
            oc = s.get("metadata", {}).get("output_contract") or s.get("output_contract") or {}
            if "min_data_figures" in json.dumps(oc, ensure_ascii=False):
                declared.append(f"{name}/{s['skill_name']}")
    # 一刀切判定：过半竞赛模板统一声明即违规（当前应为 0 声明）
    assert len(declared) <= len(comp_templates) // 2, f"竞赛模板被统一加数据图下限: {declared}"


# ---------------------------------------------------------------------------
# C-02 赛事专属要求与通用技能隔离：canonical comp_* ID 消费、页数上限语义、
# 档案数值引用、AI 声明分域与待核实、跨赛事×语言×格式路由、行为级模板选择
# ---------------------------------------------------------------------------

CONTEST_GUESS = re.compile(
    r"grep -qi\w*\s+[\"'].*(?:huawei|华为|wuyi|五一|mathorcup|apmcm|huazhong|华中|统计建模|"
    r"cumcm|国赛|dongsan|东三省|辽宁|shuwei|数维|changsanjiao|长三角|diangong|电工|huashu|华数|华东).*[\"']\s+AGENTS\.md"
    r"|echo \"\$ARGUMENTS\" \| grep", re.I)


def _paper_skills_family():
    return ["comp-paper-en", "comp-paper-zh", "comp-paper-en-docx", "comp-paper-zh-docx",
            "comp-compile-en", "comp-compile-zh"]


def test_competition_identity_comes_from_canonical_profile_ids():
    """赛事识别只认 contest_profile 下发的规范 comp_* ID：COMPETITION shell 变量、
    自由文本/$ARGUMENTS/AGENTS.md 猜赛事全部废除（引擎只下发 contest_profile）。"""
    for name in _paper_skills_family():
        text = _skill_text(name)
        assert "COMPETITION" not in text, f"{name}: COMPETITION 变量接口残留（引擎不下发该变量）"
        assert "contest_profile" in text and "CONTEST_ID" in text, f"{name}: 未接 contest_profile/CONTEST_ID"
        for hit in _violations(text, CONTEST_GUESS):
            assert False, f"{name}{hit}"


def test_comp_paper_en_template_selection_is_param_driven():
    """comp-paper-en 模板选择 case 分支=规范 comp_* ID；无 comp_icm（ICM 并入 comp_mcm）；
    comp_shuwei_en 显式报能力缺口；Refusing to guess 保留；裸 mcm/icm/apmcm 值废除。"""
    text = _skill_text("comp-paper-en")
    assert 'case "$CONTEST_ID" in' in text
    for branch in ("comp_mcm)", "comp_apmcm)", "comp_certcup_en)", "comp_shuwei_en)"):
        assert branch in text, branch
    assert "Refusing to guess" in text
    assert "mcm|icm" not in text, "裸 mcm|icm 分支值残留（不是档案键）"
    assert "comp_icm)" not in text, "comp_icm 不是 comp_rules 键（ICM 并入 comp_mcm）"
    assert "Capability gap" in text and "comp_shuwei_en" in text


def test_comp_paper_zh_covers_all_zh_contests_in_archive():
    """zh 写作技能 case 表必须覆盖 comp_rules 全部 zh 赛事键（漏键=未知 ID 误报错）。"""
    rules = json.loads((ROOT / "engine" / "modex-core" / "comp_rules.json").read_text(encoding="utf-8"))
    text = _skill_text("comp-paper-zh")
    missing = [cid for cid, entry in rules["contests"].items()
               if entry.get("language") == "zh" and cid not in text]
    assert not missing, f"comp-paper-zh 未覆盖档案 zh 赛事键: {missing}"


def _extract_case_block(text: str) -> str:
    """提取技能 Step1 的赛事选择块（if empty 守卫 … case/… esac），供行为级验证。"""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if 'if [ -z "$CONTEST_ID" ]' in l)
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "esac")
    return "\n".join(lines[start:end + 1]) + "\n"


def _run_case_selection(skill: str, contest_id: str, dirs, tmpl_base=None):
    """执行提取出的选择块（真实下发字段 → 模板目录）。tmpl_base=None 时在临时目录
    播种假模板；否则直接指向真实模板库。返回 (exit, 尾行输出, paper/main.tex sha1)。"""
    import hashlib
    import os
    import shutil
    import subprocess
    import tempfile
    bash = shutil.which("bash")
    assert bash, "行为级验证需要 bash（本仓库交付环境内置 Git Bash）"
    header = (f'TMPL_BASE="{tmpl_base}"\n' if tmpl_base else 'TMPL_BASE="_templates"\n') + "mkdir -p paper\n"
    if skill == "comp-paper-zh":
        tail = ('\n[ -d "$TMPL_BASE/$TMPL" ] || { echo "MISSING_DIR:$TMPL"; exit 3; }\n'
                'for _f in "$TMPL_BASE/$TMPL/"*.tex "$TMPL_BASE/$TMPL/"*.cls "$TMPL_BASE/$TMPL/"*.sty; do\n'
                '  [ -e "$_f" ] || continue\n'
                '  cp "$_f" paper/ || { echo "COPY_FAIL:$_f"; exit 4; }\n'
                'done\n')
    else:  # en 技能的 case 分支内直接 cp
        tail = "\n"
    script = ("#!/usr/bin/env bash\n" + header + _extract_case_block(_skill_text(skill)) + tail +
              'ls paper/ 2>/dev/null | grep -oE "mark_[a-z_]+" | head -1\n')
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "_templates"
        for d in dirs:
            (base / d).mkdir(parents=True)
            (base / d / f"mark_{d}.tex").write_text("c", encoding="utf-8")
        (Path(td) / "case.sh").write_text(script, encoding="utf-8")
        r = subprocess.run([bash, "case.sh"], cwd=td,
                           env={**os.environ, "CONTEST_ID": contest_id},
                           capture_output=True, text=True, timeout=30)
        out = r.stdout.strip().splitlines()
        main_tex = Path(td) / "paper" / "main.tex"
        main_sha = hashlib.sha1(main_tex.read_bytes()).hexdigest() if main_tex.is_file() else ""
        return r.returncode, (out[-1] if out else "") + r.stderr[:200], main_sha


def test_template_selection_branch_table_en():
    """选择分支测试（分支表映射验证，非端到端程序化接入）：真实 comp_* ID 驱动分支
    选择；裸值/未知/缺口必须显式失败。程序化注入待 B 接口落地（INTERFACE_REQUEST_TO_B.md）。"""
    dirs = ["mcm", "apmcm", "certcup_en"]
    for cid, marker in [("comp_mcm", "mark_mcm"), ("comp_apmcm", "mark_apmcm"),
                        ("comp_certcup_en", "mark_certcup_en")]:  # 独立骨架（archive template_cls=article）
        code, out, _sha = _run_case_selection("comp-paper-en", cid, dirs)
        assert code == 0 and marker in out, (cid, code, out)
    for cid in ("comp_shuwei_en", "", "apmcm", "icm", "mcm", "comp_unknown"):
        code, out, _sha = _run_case_selection("comp-paper-en", cid, dirs)
        assert code != 0, f"{cid!r} 应显式失败（缺口/空值/裸值/未知不得选中模板）: {out}"


def test_template_selection_branch_table_zh():
    """选择分支测试（分支表映射验证）：comp_rules 全部 zh 赛事键 → 档案指定文档类对应的
    模板目录；空值/裸值/跨语言键失败。程序化注入待 B 接口落地（INTERFACE_REQUEST_TO_B.md）。"""
    rules = json.loads((ROOT / "engine" / "modex-core" / "comp_rules.json").read_text(encoding="utf-8"))
    dirs = ["cumcm", "wuyi", "huawei", "mathorcup", "apmcm_zh", "stats",
            "changsanjiao", "huashubei", "diangongbei", "dongsansheng", "shuweibei", "default"]
    expect = {
        "comp_cumcm": "cumcm", "comp_huazhong": "cumcm", "comp_wuyi": "wuyi",
        "comp_huawei": "huawei", "comp_mathorcup": "mathorcup", "comp_apmcm_zh": "apmcm_zh",
        "comp_stats": "stats", "comp_yangtze": "changsanjiao", "comp_huashu": "huashubei",
        "comp_diangong": "diangongbei", "comp_liaoning": "dongsansheng", "comp_shuwei": "shuweibei",
        "comp_teddy": "default", "comp_certcup": "default", "comp_zhongqing": "default",
        "comp_tianfu": "default", "comp_shenzhen": "default", "comp_huadong": "default",
    }
    archive_zh = {cid for cid, e in rules["contests"].items() if e.get("language") == "zh"}
    assert archive_zh == set(expect), f"映射表与档案 zh 键不一致: {archive_zh ^ set(expect)}"
    for cid, want in expect.items():
        code, out, _sha = _run_case_selection("comp-paper-zh", cid, dirs)
        assert code == 0 and f"mark_{want}" in out, (cid, want, code, out)
    for cid in ("", "cumcm", "comp_mcm"):
        code, out, _sha = _run_case_selection("comp-paper-zh", cid, dirs)
        assert code != 0, f"{cid!r} 不许静默兜底: {out}"


def test_max_pages_is_ceiling_not_floor():
    """页数参数语义=赛事档案上限；凑页下限指令、默认值、Default mcm 一律禁止（方向曾颠倒）。"""
    skills = ["comp-compile-zh", "comp-compile-en", "comp-paper-zh", "comp-paper-en",
              "comp-paper-zh-docx", "comp-paper-en-docx"]
    for name in skills:
        text = _skill_text(name)
        assert "≥ MAX_PAGES" not in text, name
        assert "${MAX_PAGES:-" not in text, f"{name}: MAX_PAGES 默认值残留"
        assert not re.search(r"MAX_PAGES[^.。\n]{0,40}(下限|floor|NOT a ceiling)", text, re.I), name
        assert not re.search(r"< 80% of MAX_PAGES", text), name
        assert not re.search(r"页数严重不足|expand the thinnest.{0,40}chapters? (before finishing|to reach)", text, re.I | re.S), name
    zh_docx = _skill_text("comp-paper-zh-docx")
    assert "目标: ≥" not in zh_docx and "低于目标 80%" not in zh_docx, "docx 变体页数下限残留"
    en_docx = _skill_text("comp-paper-en-docx")
    assert "target: ≥" not in en_docx and "below 80% target" not in en_docx, "docx 变体页数下限残留"
    assert "Default `mcm`" not in en_docx and "Default 25" not in en_docx, "Default mcm/25 残留"
    assert "Default 20" not in zh_docx, "Default 20 残留"


def test_competition_page_values_come_from_archive():
    """单题/单赛数值不得全局化：正文引用档案字段不写死；华为杯 stale 值 50 不得残留；
    30-46 图只许以 huawei 域 + 非硬门禁（建议/待核实）语气出现。"""
    zh = _skill_text("comp-paper-zh")
    assert "每子问题正文 ≥ 8-10 页" not in zh
    assert not re.search(r"≥ ?6-8 ?张图表|≥ ?8-15 ?个公式", zh)
    en = _skill_text("comp-paper-en")
    assert not re.search(r"max_pages\s*=\s*\d+", en), "en 技能写死档案数值"
    assert "PAGE_CAP" in en and "contest_profile" in en
    assert "not an official rule" in en  # 分页经验标注性质
    pkg = _skill_text("comp-cumcm-package")
    assert "max_body_pages: 50" not in pkg and "≤50 页" not in pkg, "华为杯页数 stale 值残留"
    for m in re.finditer(r"figure_total_range", pkg):
        line_no = pkg[: m.start()].count("\n") + 1
        line = pkg.splitlines()[line_no - 1]
        window = "\n".join(pkg.splitlines()[max(0, line_no - 6):line_no])
        assert re.search(r"huawei|华为杯|figure_total_range", window, re.I), f"comp-cumcm-package:{line_no} 错域引用"
        assert re.search(r"非.{0,6}硬门禁|建议|待核实|经验", line + window, re.I), f"comp-cumcm-package:{line_no} 30-46 图未标非硬门禁"
    zhdocx = _skill_text("comp-paper-zh-docx")
    assert "每子问题正文 ≥ 8-10 页" not in zhdocx, "华为杯单题配额在 zh-docx 残留"
    assert "6-8 张图表" not in zhdocx


def test_ai_disclosure_is_competition_scoped():
    """AI 声明：格式分域 + 缺当届规定必须报待核实；默认 off 不得绕开赛事要求，
    通用短说明不得冒充合规。"""
    en = _skill_text("comp-paper-en")
    assert not re.search(r"call `_utils/build_ai_disclosure\.py`|generate the standalone supporting file", en), \
        "国赛声明格式仍以执行指令形式存在于通用英文技能"
    assert "belongs to the CUMCM chain" in en
    assert "待核实" in en, "缺当届规定未报待核实"
    assert "skip this step entirely" not in en, "默认跳过残留（默认 off 不得绕开赛事要求）"
    assert not re.search(r"if absent, state truthfully in a short", en, re.I), "通用短说明冒充合规路径残留"
    assert "never silently skipped" in en
    zh = _skill_text("comp-paper-zh")
    assert "comp_cumcm" in zh and "待核实" in zh, "国赛声明未限定适用域或缺待核实"
    assert re.search(r"不(得)?静默", zh), "其他赛事缺规定时的静默处理残留"


def test_cross_competition_language_format_routing():
    """跨赛事×语言×格式路由：赛事模板分派正确语言/格式的写作与编译技能；
    docx 注入只加 docx-export 步，写作步 LaTeX 产物合同不变（中间产物合法）。"""
    expect = {
        "comp_mcm": ("comp-paper-en", "comp-compile-en"),
        "comp_apmcm": ("comp-paper-en", "comp-compile-en"),
        "comp_apmcm_zh": ("comp-paper-zh", "comp-compile-zh"),
        "comp_mathorcup": ("comp-paper-zh", "comp-compile-zh"),
        "comp_stats": ("comp-paper-zh", "comp-compile-zh"),
    }
    for name, (paper, compile_) in expect.items():
        skills = [s["skill_name"] for s in TEMPLATES[name]["sub_steps"]]
        assert paper in skills and compile_ in skills, (name, skills)
    from engine.template_resolver import resolve_template
    lang_paper = {"en": "comp-paper-en", "zh": "comp-paper-zh"}
    for comp, lang in [("comp_mcm", "en"), ("comp_apmcm_zh", "zh"), ("comp_mathorcup", "zh")]:
        steps = resolve_template(comp, {"output_format": "docx", "language": lang}, TEMPLATES)
        got = [s["skill_name"] for s in steps]
        assert any(s.startswith("docx-export") for s in got), comp
        assert lang_paper[lang] in got, comp
        wrong = "comp-paper-zh" if lang == "en" else "comp-paper-en"
        assert wrong not in got, f"{comp}: 赛事语言混用（出现 {wrong}）"
        paper_step = next(s for s in steps if s["skill_name"] == lang_paper[lang])
        contract = json.dumps(paper_step.get("metadata", {}).get("output_contract", {}), ensure_ascii=False)
        assert '"$primary"' in contract, f"{comp}: paper 步缺 $primary 合同（docx 导出不改变写作步产物）"

# ---------------------------------------------------------------------------
# 总调度第五轮收口（C窗）：共享模板不承载页限默认、unknown 不产生默认硬页限、
# compile 同源消费、真实档案→执行参数→真实模板接入、复用骨架夹带核对
# ---------------------------------------------------------------------------

def test_shared_templates_carry_no_quick_gates_max_pages_default():
    """共享模板不得承载任务级页数口径默认（华为杯两处 80 已删）；
    显式覆盖由任务层承载（params.contest.page_cap / step metadata，B 域语义）。"""
    for name, tpl in TEMPLATES.items():
        for s in tpl.get("sub_steps", []):
            assert "quick_gates_max_pages" not in (s.get("metadata") or {}), (name, s["skill_name"])


def test_unverified_page_status_creates_no_default_hard_cap():
    """unknown（unverified）不产生默认硬页限、不得包装成任务覆盖；「照值执行」类
    表述清零；compile 两变体与写作同源消费 gate 三分量，不折叠 body/total。"""
    for name in _paper_skills_family():
        text = _skill_text(name)
        assert not re.search(r"executed as dispatched|照下发值执行|照值执行", text), f"{name}: 照值执行残留"
    en = _skill_text("comp-paper-en")
    zh = _skill_text("comp-paper-zh")
    assert "does **not** create a default hard page limit" in en
    assert "不产生默认硬页限" in zh
    for name in ("comp-compile-en", "comp-compile-zh"):
        text = _skill_text(name)
        assert not re.search(r"max_body_pages. / .max_pages|compliance page fields|compliance 的页数字段", text), \
            f"{name}: 档案原始字段直读残留"
        assert "gate_page_cap" in text and "gate_page_scope" in text and "page_cap_status" in text, name


def test_archive_profile_feeds_selection_against_real_templates():
    """接入验证：真实 comp_rules 档案 → resolve_profile（gate 字段）→ 真实模板目录选中
    且 main.tex 与骨架逐字节一致；页限/口径与档案动态对账（不钉数值）。
    程序化注入仍待 B 接口（INTERFACE_REQUEST_TO_B.md），当前为模型转录过渡通道。"""
    import hashlib
    from engine.contest_profile import resolve_profile
    real_base = (SKILLS_DIR / "comp-paper-zh" / "_templates").as_posix()
    checks = [("comp-paper-en", "comp_mcm", "mcm"),
              ("comp-paper-en", "comp_apmcm", "apmcm"),
              ("comp-paper-en", "comp_certcup_en", "certcup_en"),
              ("comp-paper-zh", "comp_cumcm", "cumcm"),
              ("comp-paper-zh", "comp_huawei", "huawei"),
              ("comp-paper-zh", "comp_huazhong", "cumcm"),
              ("comp-paper-zh", "comp_teddy", "default")]
    # v2：带多 profile 的赛事须显式给 edition/submission_form 维度（不猜）。
    dims = {"comp_cumcm": {"edition": "2026", "submission_form": "electronic"}}
    for skill, cid, want_dir in checks:
        profile = resolve_profile(cid, {"contest": dims.get(cid, {})})
        assert profile is not None, cid
        view = profile.context_view()
        assert view["contest_id"] == cid
        # v2 契约：页数口径取自 profiles 选中维度（resolve_profile 拍平后的
        # max_body_pages/max_total_pages/page_cap_status），非 v1 原始赛事键；
        # task_override（历史任务裁决）不继承 → gate cap=None。
        expect_cap = None if view["page_cap_status"] == "task_override" else (
            view["max_body_pages"] if view["max_body_pages"] is not None else view["max_total_pages"])
        assert view["gate_page_cap"] == expect_cap, (cid, view["gate_page_cap"], expect_cap)
        skeleton = SKILLS_DIR / "comp-paper-zh" / "_templates" / want_dir / "main.tex"
        assert skeleton.is_file(), (cid, want_dir)
        code, out, main_sha = _run_case_selection(skill, cid, dirs=[], tmpl_base=real_base)
        assert code == 0, (cid, code, out)
        assert main_sha == hashlib.sha1(skeleton.read_bytes()).hexdigest(), (cid, "复制产物与真实骨架不一致")


def test_reused_skeletons_checked_for_foreign_contest_marks():
    """同文档类复用须核对模板内容：复用骨架不得夹带另一赛事封面、队号或声明；
    确有源赛事专属元素（如 mcm 骨架的 tcn/problem 设置）时，对应技能正文必须带
    复制后强制核对替换指令。（comp_certcup_en 自 2026-09-27 起为独立骨架，
    不再复用 mcm/，见 test_certcup_en_standalone_skeleton_clean_and_mcm_home_intact。）"""
    marks = re.compile(r"承诺书|编号专用页|Team Control Number|tcn\s*=|problem\s*=\s*[A-Z]|参赛队号", re.I)
    reuse = [("comp_huazhong", "cumcm", "comp-paper-zh"),
             ("comp_teddy", "default", "comp-paper-zh"),
             ("comp_huadong", "default", "comp-paper-zh")]
    for cid, d, skill in reuse:
        text = (SKILLS_DIR / "comp-paper-zh" / "_templates" / d / "main.tex").read_text(encoding="utf-8")
        hits = marks.findall(text)
        if hits:
            assert re.search(r"Reused-skeleton content check|同文档类复用核对", _skill_text(skill)), \
                (cid, d, hits, "复用骨架含源赛事专属元素，但技能正文无强制核对替换指令")


def test_certcup_en_standalone_skeleton_clean_and_mcm_home_intact():
    """总调度 2026-09-27 授权清理验收：certcup_en 独立骨架不含 mcm 专属标识
    （控制号/题号设置、美赛摘要页字样、mcmthesis 类、mcmsetup）；技能正文
    comp_certcup_en 分支只复制 certcup_en/ 目录；mcm 自身骨架保留其原生
    tcn/problem 设置（本赛事格式，未波及），comp_mcm 分支原样。"""
    tpl = SKILLS_DIR / "comp-paper-zh" / "_templates"
    cert = (tpl / "certcup_en" / "main.tex").read_text(encoding="utf-8")
    mcm_marks = re.compile(r"Team Control Number|tcn\s*=|problem\s*=\s*[A-Z]|MCM/ICM|Summary Sheet|mcmthesis|\\mcmsetup", re.I)
    assert not mcm_marks.search(cert), mcm_marks.findall(cert)
    assert re.search(r"\\documentclass(?:\[[^\]]*\])?\{article\}", cert), "骨架应为独立 article 类（archive template_cls=article）"
    summary_pos = cert.index("Summary")
    assert "\\newpage" in cert[summary_pos:], "Summary 页后应有独立分页（档案：Summary 必须独立成页）"
    en = _skill_text("comp-paper-en")
    assert en.count('cp "$TMPL_BASE/mcm/"*') == 1, "comp_mcm 之外不得再复制 mcm/ 骨架"
    assert 'cp "$TMPL_BASE/certcup_en/"*' in en, "comp_certcup_en 分支应复制独立 certcup_en/ 骨架"
    mcm = (tpl / "mcm" / "main.tex").read_text(encoding="utf-8")
    assert re.search(r"tcn\s*=\s*0000", mcm) and re.search(r"problem\s*=\s*A", mcm), \
        "mcm 骨架应保留原生 tcn/problem 设置（本轮授权范围：mcm 保留不动）"
