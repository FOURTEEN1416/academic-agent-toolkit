"""P4 资产充分吸收批次（2026-09-22）机械棘轮与激活登记测试。

守护五组断言（全部为"实测后钉死、只准更严不准放松"的棘轮）：

  A. P0 路由修复在册：13 个此前仅"注册不可路由"的技能必须在
     CONTEST_SKILL_MAP §一-§三（活跃路由段）具名，且 catalog 侧 disposition=routed
     （根级 catalog 硬校验测试已于 2026-09-23 随根级门禁退役，本文件守地图半区）。
  C. 强制步棘轮：全仓 templates.json 声明非空 `mandatory` 的步骤数 / 槽位数
     只升不降——防止"把必用位改回可选"这类静默降级（资产激活成果不可回撤）。
  D. 辅助技能死槽分代：legacy 代际死槽只登记不删除（用户红线"资产不撤只激活"），
     活跃代际死槽数只减不增；工具 `companion_dead_slots()` 的分代逻辑有合成用例锁定。
  E. 报告接线：check_asset_utilization 主流程必须输出第 [4] 项死槽分代报表与
     第 [5] 项 catalog disposition 分级账（工具侧棘轮：守回填进度可读；原与根级
     schema 测试互为镜像，该测试已于 2026-09-23 随根级门禁退役）。

口径与真值均为 2026-09-22 本地实测（数字与审计口头 claim 不一致时以本文件实测为准，
见 test_mandatory_* 与 LEGACY_DEAD_SLOT_REGISTRY 的注释）。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import check_asset_utilization as cau

TEMPLATES = ROOT / "engine" / "modex-core" / "templates.json"
MAP = ROOT / "CONTEST_SKILL_MAP.md"

# ---------- A：P0 路由修复批次（13 个） ----------

P0_ROUTED_BATCH = [
    # 绘图/可视化（6）
    "matplotlib", "plotly", "seaborn", "visualization", "infographics",
    "excalidraw-diagram",
    # 文献/研究辅助（4）
    "arxiv", "lit-review-communications", "comp-contest-research", "lit-review-systematic",
    # 其他单点（3）
    "ablation-planner", "paper-illustration", "problem-selection",
]


def _map_active_sections() -> str:
    """§一/§二/§三 三段正文（活跃路由面；§四外域/§五未接入不算路由）。"""
    text = MAP.read_text(encoding="utf-8")
    keep = []
    for block in text.split("## ")[1:]:
        header = block.split("\n", 1)[0]
        if header[:2] in ("一、", "二、", "三、"):
            keep.append(block)
    assert keep, "CONTEST_SKILL_MAP 未解析出 §一/§二/§三 活跃段"
    return "\n".join(keep)


def test_p0_batch_skills_named_in_active_map_sections():
    """13 个 P0 技能必须在地图活跃段（§一-§三）具名——"注册即可见"不等于"可路由"。"""
    body = _map_active_sections()
    not_routed = [
        n for n in P0_ROUTED_BATCH
        if not re.search(r"(?<![A-Za-z0-9_-])" + re.escape(n) + r"(?![A-Za-z0-9_-])", body)
    ]
    assert not not_routed, f"P0 批次技能未进入地图活跃段（§一-§三）: {not_routed}"


def test_p0_batch_count_is_thirteen_and_unique():
    """批次清单本身钉死：13 个、无重复（原与根级 catalog 测试互锁，该测试 2026-09-23 退役）。"""
    assert len(P0_ROUTED_BATCH) == 13
    assert len(set(P0_ROUTED_BATCH)) == 13


def test_p0_batch_skills_are_real_registered_skills():
    """回填路由的前提：这些技能确实在 skills/ 注册（SKILL.md 在位），不路由幽灵名。"""
    for n in P0_ROUTED_BATCH:
        assert (ROOT / "skills" / n / "SKILL.md").is_file(), f"技能未注册却声称已路由: {n}"


# ---------- C：强制步棘轮（只升不降） ----------

# 2026-09-22 实测基线：全仓 46 模板中 2 个模板（comp_cumcm / comp_huawei）
# 共 10 个步骤声明非空 metadata.skill_binding.mandatory，合计 12 个必用槽位
# （5 步/模板 ×2 = 10 步；final-audit 步各 2 槽 → 6+6=12 槽）。
# 注：审计口径口头"mandatory 仅 10 步"系步骤级读数，与槽位级 12 并存，本测试两者都钉。
MANDATORY_TEMPLATES_BASELINE = 2
MANDATORY_STEPS_BASELINE = 10
MANDATORY_SLOTS_BASELINE = 12


def _mandatory_declarations(templates: dict) -> list[tuple[str, str, list[str]]]:
    """递归收集 (模板名, 步骤名, mandatory 列表)，不限定 mandatory 挂在哪个 metadata 子键下。"""
    found: list[tuple[str, str, list[str]]] = []

    def walk(node, tpl_name, step_name):
        if isinstance(node, dict):
            step_name = node.get("skill_name") or step_name
            for key, value in node.items():
                if key == "mandatory" and isinstance(value, list) and value:
                    found.append((tpl_name, step_name, [str(v) for v in value]))
                else:
                    walk(value, tpl_name, step_name)
        elif isinstance(node, list):
            for item in node:
                walk(item, tpl_name, step_name)

    for name, tpl in templates.items():
        walk(tpl, name, None)
    return found


def _real_templates() -> dict:
    return json.loads(TEMPLATES.read_text(encoding="utf-8"))


def test_mandatory_step_count_ratchet_only_up():
    """强制步数/槽位数棘轮：低于基线即视为资产激活成果被静默回撤，必须红。"""
    decls = _mandatory_declarations(_real_templates())
    step_count = len(decls)
    slot_count = sum(len(m) for _, _, m in decls)
    tpl_count = len({t for t, _, _ in decls})
    assert step_count >= MANDATORY_STEPS_BASELINE, (
        f"全仓 mandatory 步骤数 {step_count} < 基线 {MANDATORY_STEPS_BASELINE}："
        "必用位只能增加不能撤销（P4 资产充分吸收红线）"
    )
    assert slot_count >= MANDATORY_SLOTS_BASELINE, (
        f"全仓 mandatory 槽位 occurrences {slot_count} < 基线 {MANDATORY_SLOTS_BASELINE}"
    )
    assert tpl_count >= MANDATORY_TEMPLATES_BASELINE, (
        f"声明 mandatory 的模板数 {tpl_count} < 基线 {MANDATORY_TEMPLATES_BASELINE}"
    )


def test_mandatory_slots_point_to_real_skills_and_companion_declared():
    """必用槽指向真实技能，且该技能必须同时出现在同一步的 companion_skills 里
    （否则 C1 闸会拒绝申报——mandatory 悬空 = 假强制）。"""
    templates = _real_templates()
    problems = []
    for tpl_name, step_name, mandatory in _mandatory_declarations(templates):
        for skill in mandatory:
            if not (ROOT / "skills" / skill / "SKILL.md").is_file():
                problems.append(f"{tpl_name}/{step_name}: mandatory 指向未注册技能 {skill}")
        step = next((s for name, tpl in templates.items() if name == tpl_name
                     for s in tpl.get("sub_steps", [])
                     if isinstance(s, dict) and s.get("skill_name") == step_name), None)
        declared = set(((step or {}).get("metadata") or {})
                       .get("companion_skills") or [])
        for skill in mandatory:
            if skill not in declared:
                problems.append(f"{tpl_name}/{step_name}: {skill} 必用但未进 companion_skills")
    assert not problems, "假强制: " + "；".join(problems)


# ---------- D：辅助技能死槽分代（legacy 登记 + 活跃棘轮只减） ----------

# 2026-09-22 实测：46 模板 = legacy 代际死槽 41 + 活跃代际死槽 3 + 活跃已接线 2。
# （审计口头口径"legacy 40 / active 7"与机械分代实测不符，此处以工具
# `companion_dead_slots()` 的可复现读数为准：当前代 = 任一步 metadata 携带
# companion_skills / output_specs / note 三个机制字段之一，字段引入日期见工具注释。）
ACTIVE_DEAD_SLOT_BASELINE = 3
# catalog disposition 回填棘轮（2026-09-22 实测 15：13 P0 + pdf-toolkit(routed)
# + paper-compile-zh(evidence-bound)，共 routed 14 / evidence-bound 1）
DISPOSITION_FILLED_BASELINE = 15
LEGACY_DEAD_SLOT_REGISTRY = [
    "comp_apmcm", "comp_apmcm_zh", "comp_certcup", "comp_certcup_en", "comp_diangong",
    "comp_huadong", "comp_huashu", "comp_huazhong", "comp_liaoning", "comp_mathorcup",
    "comp_mcm", "comp_shenzhen", "comp_shuwei", "comp_shuwei_en", "comp_stats",
    "comp_teddy", "comp_tianfu", "comp_wuyi", "comp_yangtze", "comp_zhongqing",
    "copyright_material", "copyright_source_materials", "course_paper", "course_report",
    "deep_research", "experiment_bridge", "full_pipeline", "grad_project",
    "grant_proposal", "humanities_paper", "idea_discovery", "literature_review",
    "nature_writing", "paper_from_assets", "paper_submission", "paper_writing",
    "paper_writing_zh", "patent_disclosure", "scientific_figure_suite",
    "scientific_plotting", "thesis_proposal",
]
ACTIVE_CLEAN_BASELINE = ["comp_cumcm", "comp_huawei"]


def test_companion_dead_slots_synthetic_generation(tmp_path):
    """分代单元用例（合成模板，不依赖真仓状态）：
    legacy 无 companion / 活跃代死槽（有机制字段但 companion 全空）/ 活跃已接线。"""
    payload = {
        "legacy_dead": {"sub_steps": [
            {"skill_name": "s1", "metadata": {}},
            {"skill_name": "s2", "metadata": {"assets": []}},
        ]},
        "active_dead": {"sub_steps": [
            {"skill_name": "s1", "metadata": {"output_specs": ["a.md"],
                                              "companion_skills": []}},
            {"skill_name": "s2", "metadata": {"note": "batch4", "companion_skills": []}},
        ]},
        "active_clean": {"sub_steps": [
            {"skill_name": "s1", "metadata": {"companion_skills": ["x-skill"]}},
        ]},
        "empty_steps": {"sub_steps": []},
    }
    path = tmp_path / "templates.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    got = cau.companion_dead_slots(path)
    assert got["templates_total"] == 4
    assert got["legacy_dead_slots"] == ["empty_steps", "legacy_dead"]  # 工具按名排序输出
    assert got["active_dead_slots"] == ["active_dead"]
    assert got["active_clean_templates"] == ["active_clean"]


def test_companion_dead_slots_missing_file_reports_error():
    got = cau.companion_dead_slots(Path(__file__).resolve().parent / "nope.json")
    assert got["templates_total"] == 0 and got["error"]


def test_real_repo_dead_slot_generations_measure_and_reconcile():
    """真仓读数自洽：三桶之和 == 模板总数；活跃已接线至少含两大赛模板（棘轮只升）。"""
    got = cau.companion_dead_slots(TEMPLATES)
    assert got.get("error") is None
    legacy, active_dead, active_clean = (got["legacy_dead_slots"], got["active_dead_slots"],
                                         got["active_clean_templates"])
    assert len(legacy) + len(active_dead) + len(active_clean) == got["templates_total"], (
        "分代三桶之和与模板总数不符——分代逻辑或模板结构变了，须先修口径再改基线")
    for name in ACTIVE_CLEAN_BASELINE:
        assert name in active_clean, f"活跃已接线模板被降级: {name}"
    assert len(active_clean) >= len(ACTIVE_CLEAN_BASELINE), (
        f"活跃已接线模板数 {len(active_clean)} < 基线 {len(ACTIVE_CLEAN_BASELINE)}（只升不降）")


def test_real_repo_active_dead_slot_ratchet_only_down():
    """活跃代际死槽只减不增（新增模板若属当代机制却空推荐 = 新的激活欠账，必须拦）。"""
    got = cau.companion_dead_slots(TEMPLATES)
    assert len(got["active_dead_slots"]) <= ACTIVE_DEAD_SLOT_BASELINE, (
        f"活跃代际死槽 {len(got['active_dead_slots'])} 个 > 基线 "
        f"{ACTIVE_DEAD_SLOT_BASELINE}：{got['active_dead_slots']}——"
        "当代模板的 companion 空槽必须补齐或明确降级为 legacy 代，不得默认放行")


def test_legacy_dead_slots_registered_not_deleted():
    """legacy 代际死槽只登记不删除：
    1) 已登记的 41 个若消失，必须确已从 templates.json 删除（防止字段补挂后漏登记）；
    2) 新出现的 legacy 死槽必须显式加入登记表，不得静默扩大。"""
    got = cau.companion_dead_slots(TEMPLATES)
    legacy = set(got["legacy_dead_slots"])
    templates = set(_real_templates().keys())
    unregistered = sorted(legacy - set(LEGACY_DEAD_SLOT_REGISTRY))
    assert not unregistered, (
        f"新 legacy 代际死槽未登记（须并入登记表并说明为何不激活）: {unregistered}")
    vanished = sorted(set(LEGACY_DEAD_SLOT_REGISTRY) - legacy)
    still_there_but_no_longer_legacy = [n for n in vanished if n in templates]
    for name in still_there_but_no_longer_legacy:
        # 从 legacy 名单消失但模板仍在：只允许"被激活"（转入已接线）这一种解释
        assert name in set(got["active_clean_templates"]), (
            f"legacy 模板 {name} 既未激活也未删除，却从死槽登记表消失——分代口径被改动")


# ---------- E/报告接线：工具主流程必须输出死槽分代段与 disposition 账 ----------

def test_tool_main_emits_dead_slot_section(capsys):
    """check_asset_utilization 报告含第 [4] 项死槽分代（人读）与 JSON 键（机读）。"""
    rc = cau.main(["--repo", str(ROOT.parent)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[4] companion 死槽分代" in out, out[-800:]
    assert "legacy 代际死槽" in out and "活跃代际死槽" in out
    assert "[5] catalog disposition 分级账" in out, out[-800:]


def test_catalog_dispositions_synthetic_grading(tmp_path):
    """disposition 账单元用例：三级取值计数 + 技能名形态未回填数 + 缺文件如实报错。"""
    payload = {
        "domain_a": [
            {"capability_id": "skill-one", "disposition": "routed"},
            {"capability_id": "skill-two", "disposition": "evidence-bound"},
            {"capability_id": "skill-three"},
        ],
        "domain_b": [
            {"capability_id": "aggregate_four", "disposition": "active"},
            {"capability_id": "aggregate_five"},  # 聚合条目（下划线命名）未回填：不计入技能名未回填数
        ],
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    got = cau.catalog_dispositions(path)
    assert got == {"entries_total": 5, "filled": 3,
                   "by_level": {"routed": 1, "evidence-bound": 1, "active": 1},
                   "unfilled_skill_entries": 1}
    missing = cau.catalog_dispositions(tmp_path / "nope-catalog.json")
    assert missing["entries_total"] == 0 and missing["error"]


def test_real_repo_catalog_disposition_report_matches_catalog():
    """真仓 disposition 账必须与 catalog 实际一致，且回填数不低于基线（工具侧棘轮）。"""
    got = cau.catalog_dispositions(ROOT.parent / "capabilities" / "catalog.json")
    data = json.loads((ROOT.parent / "capabilities" / "catalog.json").read_text(encoding="utf-8"))
    entries = [i for items in data.values() for i in items]
    assert got["entries_total"] == len(entries)
    assert got["filled"] == len([i for i in entries if i.get("disposition")])
    assert got["filled"] >= DISPOSITION_FILLED_BASELINE, (
        f"disposition 回填数 {got['filled']} < 基线 {DISPOSITION_FILLED_BASELINE}"
        "（P4 批次 E 棘轮只升）")
    assert got["by_level"].get("routed", 0) >= 14
    assert got["by_level"].get("evidence-bound", 0) >= 1
    assert not got.get("error")


def test_json_payload_carries_dead_slots(capsys):
    rc = cau.main(["--repo", str(ROOT.parent), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "companion_dead_slots" in payload
    ds = payload["companion_dead_slots"]
    assert {"templates_total", "legacy_dead_slots", "active_dead_slots",
            "active_clean_templates"} <= set(ds)
    assert ds["templates_total"] == len(_real_templates())
    assert "catalog_disposition" in payload
