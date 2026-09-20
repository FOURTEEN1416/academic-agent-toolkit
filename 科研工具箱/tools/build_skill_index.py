#!/usr/bin/env python3
"""技能分层常驻：tier 派生 + 路由索引生成 + 按需层描述压缩（2026-09-19）。

背景与动机
----------
技能 frontmatter 的 name+description 是**每会话常驻**的（宿主必须在选择技能前知道有哪些
技能）。实测本项目 261 技能常驻 61,224 字符 ≈ 27,800 tokens ≈ 200K 的 14%——而按需层
（外域集成件等 232 个从未在主链被加载的技能）占了其中 **92%**。同行做法很明确：
技能本体做成短索引、细节按需加载（another-agent-skills 常驻仅 1.9%）。

三层设计（不是简单截断）
------------------------
1. **核心层（core）**：竞赛主链 + 主链推荐位 + 主链资产指向 + catalog「正式」+ 治理基础设施。
   描述保持完整——它们是路由关键集，压缩核心层等于拿准确率换指标。
2. **按需层（ondemand）**：其余技能。常驻描述压到 `OND_RESEARCH_CAP` 以内（保留"是什么"的
   首句，因为那才是路由判据）。
3. **路由索引（data/skill_routing_index.json）**：**无损**保存每个技能的完整原描述 +
   完整触发词，供"核心层没解决该请求"时按需读取。压缩不是丢信息，是把信息从常驻层
   移到按需层——**索引必须真的被用到**（见 `skill_trigger_audit.route(with_index=True)`），
   否则这就是拿路由质量换指标，故 README/AGENTS 与测试都强制它的可用性。

诚实边界
--------
常驻税不可能降到同行的 1.9%：宿主发现机制要求 frontmatter 全量可读，本项目技能数（261）
是同行（24-57）的 4-10 倍。本工具把税降到结构允许的下限，并把"再降需要宿主契约支持分层
发现"记为遗留项（融合评估 §6.6 L5）。

用法：
  python tools/build_skill_index.py --check          # 校验索引/分层与真仓同步（CI 用）
  python tools/build_skill_index.py --emit           # 生成 skill_tiers.json + routing_index.json
  python tools/build_skill_index.py --compact        # 一次性迁移：压缩按需层描述（幂等）

退出码：--check 不同步时 exit 1；其余 0。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLBOX_ROOT.parent
SKILLS_ROOT = TOOLBOX_ROOT / "skills"
TIERS_PATH = TOOLBOX_ROOT / "data" / "skill_tiers.json"
INDEX_PATH = TOOLBOX_ROOT / "data" / "skill_routing_index.json"
# 路由关键集：被词法路由回归与歧义判别断言直接依赖的技能，一律归核心层（描述不压缩）。
# 为什么必须显式列出而不是"看情况"：压缩它们会让路由回归失败——那就成了**用测试覆盖的
# 能力去换指标**。清单由 data/skill_routing_critical.json 维护（可视 review、可审计）。
CRITICAL_PATH = TOOLBOX_ROOT / "data" / "skill_routing_critical.json"

OND_RESEARCH_CAP = 120      # 按需层常驻描述上限（保留"是什么"的短句；完整描述在索引）
CORE_CAP = 512              # 核心层单条上限（与 context_budget_check 同口径）
MIN_USEFUL = 24             # 首句短于此值视为不足以承载路由，退回原描述截断

# 治理/基础设施：虽不在主链，但每个会话都可能被调用，属核心层
INFRA_CORE = ("acat-doc-governance", "skill-creator-official", "contest-retrospective",
              "codesucker-integration", "agent-bootstrap", "tool-forge")

SPLIT_RE = re.compile(r"(?<=[。！？])|(?<=\.\s)|(?<=\.(?=[A-Z]))")


def iter_skill_names() -> list[str]:
    return sorted(d.name for d in SKILLS_ROOT.iterdir()
                  if d.is_dir() and (d / "SKILL.md").is_file())


def read_description(name: str) -> str:
    text = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return ""
    dm = re.search(r"^description:\s*(.+?)(?=\n[a-zA-Z_-]+:|\Z)", m.group(1), re.S | re.M)
    return dm.group(1).strip().strip('"').strip() if dm else ""


def derive_tiers() -> dict[str, dict]:
    """派生分层。三类信号，全部可复现（不写死名单）。"""
    tiers: dict[str, dict] = {}
    names = iter_skill_names()

    chain: set[str] = set()
    companions: set[str] = set()
    try:
        tpl = json.loads((TOOLBOX_ROOT / "engine" / "modex-core" / "templates.json")
                         .read_text(encoding="utf-8"))
        steps = tpl["comp_cumcm"]["sub_steps"]
        chain = {s["skill_name"] for s in steps}
        companions = {c for s in steps
                      for c in ((s.get("metadata") or {}).get("companion_skills") or [])}
    except Exception:
        pass

    formal: set[str] = set()
    try:
        cat = json.loads((REPO_ROOT / "capabilities" / "catalog.json").read_text(encoding="utf-8"))
        formal = {str(i.get("capability_id")) for items in cat.values() for i in items
                  if i.get("status") == "正式"}
    except Exception:
        pass

    critical = {}
    try:
        critical = dict((json.loads(CRITICAL_PATH.read_text(encoding="utf-8"))
                         .get("skills")) or {})
    except Exception:
        critical = {}

    for name in names:
        if name in critical:
            tiers[name] = {"tier": "core", "reason": "路由关键集（路由回归/歧义判别直接断言）"}
        elif name in chain:
            tiers[name] = {"tier": "core", "reason": "comp_cumcm 主链步骤"}
        elif name in companions:
            tiers[name] = {"tier": "core", "reason": "主链步骤的推荐/必用位"}
        elif name in formal:
            tiers[name] = {"tier": "core", "reason": "catalog 状态=正式"}
        elif name in INFRA_CORE:
            tiers[name] = {"tier": "core", "reason": "治理/基础设施（每会话可能调用）"}
        else:
            tiers[name] = {"tier": "ondemand", "reason": "非主链、非常驻调用面"}
    return tiers


def compact_description(desc: str, cap: int = OND_RESEARCH_CAP) -> str:
    """把描述压到 cap 以内：优先收在**句子结束**，其次收在**自然子句边界**。

    刻意不按键截断，也不在任意子句处截断——实测后者会留下半句
    （"Patent prior-art and landscape intelligence skill — not generic patent"），
    半句比短句更难路由也更难读。边界优先级：
        句末标点（。！？. ） > 破折号同位语（ — / – / - ） > 分号（；;） > 逗号（，,、） > 空格
    """
    text = " ".join(desc.split())
    # frontmatter 用双引号包裹，正文里的 " 会破坏 YAML → 统一换成全角引号（视觉等价、可读）
    text = text.replace('"', '”')
    if len(text) <= cap:
        return text

    SENTENCE_FINAL = ("。", "！", "？")
    # (分隔串, 是否保留该分隔串本身)
    BOUNDARIES = [("。", True), ("！", True), ("？", True), (". ", True),
                  (" — ", False), (" – ", False), (" - ", False),
                  ("；", True), ("; ", True), ("，", False), (", ", False), ("、", False), (" ", False)]
    best = ""
    for sep, keep in BOUNDARIES:
        idx = text.rfind(sep, 0, cap + len(sep))
        if idx < MIN_USEFUL:
            continue
        head = text[:idx + len(sep)].rstrip() if keep else text[:idx].rstrip()
        if not head or len(head) > cap:
            continue
        # 句子结束优先；同一优先级取更长者（信息更多）
        if sep in SENTENCE_FINAL:
            return head
        if len(head) > len(best):
            best = head
    if best:
        return best
    head = SPLIT_RE.split(text, maxsplit=1)[0].strip()
    if len(head) <= cap:
        return head
    # 兜底：绝不在词中间断（宁可更短）——靠空格回退到最后一个完整词
    cut = text[:cap].rstrip()
    space = cut.rfind(" ")
    if space >= MIN_USEFUL:
        cut = cut[:space].rstrip()
    return cut


def _previous_index_entries() -> dict[str, dict]:
    """读取既有索引条目（用于"压缩产物可回溯"保护）。"""
    if not INDEX_PATH.is_file():
        return {}
    try:
        prev = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        return dict(prev.get("skills") or {})
    except Exception:
        return {}


def build_index(keep_previous: bool = True) -> dict:
    tiers = derive_tiers()
    prev = _previous_index_entries() if keep_previous else {}
    skills = {}
    for name in iter_skill_names():
        # 空白归一：block scalar 描述在文件里带换行；统一成单行后，"常驻=截取"
        # 这一不变量才可机检（换行格式不是信息，丢掉它不影响任何语义）。
        desc = " ".join(read_description(name).split())
        tier = tiers.get(name, {}).get("tier", "ondemand")
        full = desc
        # ⛔ full_description 单调不减：压缩是单向迁移，索引一旦保存过更长的完整描述，
        # 后续重建（例如再跑一次 --emit）不得把它缩短——否则原描述会被静默吞掉。
        # 2026-09-19 踩过：--compact 中途断言失败后，重跑 --emit 用"已压缩的现况"覆盖了
        # 索引，26 个技能的原描述就此丢失（已从 HEAD 恢复）。此约束即该事故的修复。
        # ⛔ 保护只在"现存描述确实是压缩产物"时生效（prev.description_compacted=True）：
        # 那时文件里的短文本是派生结果，必须回到索引取更长的原文。
        # 若上一条目并非压缩产物，说明文件里就是权威描述（可能刚被人有意改写），
        # 此时以文件为准——否则"人工把描述改短"会被保护逻辑悄悄回滚（2026-09-19 踩过）。
        prev_entry = prev.get(name) or {}
        if keep_previous and prev_entry.get("description_compacted")                 and len(prev_entry.get("full_description", "")) > len(full):
            full = prev_entry["full_description"]
        # 常驻短描述由 **受保护的原描述** 派生（不是由文件现状再压）：
        # 这样 --compact 可重入，且压缩规则改进后旧结果会被自动重算，不会沉淀半句。
        resident = full if tier == "core" else compact_description(full)
        skills[name] = {
            "tier": tier,
            "reason": tiers.get(name, {}).get("reason", ""),
            "resident_description": resident,
            "full_description": full,
            "description_compacted": resident != full,
            "path": f"科研工具箱/skills/{name}/SKILL.md",
        }
    return {
        "schema_version": 1,
        "meta": {
            "purpose": "技能分层常驻的路由索引：常驻层只保留短描述，完整描述与触发词在此按需读取",
            "policy": ("核心层（主链/推荐位/正式/治理）描述保持完整；按需层压缩到 "
                       f"{OND_RESEARCH_CAP} 字符以内；本索引无损保存 full_description。"
                       "权威路由通道仍是引擎 StepAction 显式下发；本索引是第二通道。"),
            "cap": {"ondemand": OND_RESEARCH_CAP, "core": CORE_CAP},
            "derived_from": ["engine/modex-core/templates.json", "capabilities/catalog.json"],
        },
        "counts": {
            "core": sum(1 for v in skills.values() if v["tier"] == "core"),
            "ondemand": sum(1 for v in skills.values() if v["tier"] == "ondemand"),
            "resident_chars": sum(len(v["resident_description"]) for v in skills.values()),
            "full_chars": sum(len(v["full_description"]) for v in skills.values()),
        },
        "skills": skills,
    }


def emit(keep_previous: bool = True) -> dict:
    index = build_index(keep_previous=keep_previous)
    TIERS_PATH.write_text(json.dumps(
        {"schema_version": 1,
         "meta": {"derived_from": index["meta"]["derived_from"],
                  "rules": "主链 > 推荐位 > catalog 正式 > 治理基础设施 > 其余按需"},
         "tiers": {k: v["tier"] for k, v in index["skills"].items()},
         "reasons": {k: v["reason"] for k, v in index["skills"].items()}},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")
    return index


def sync_descriptions() -> tuple[list[str], list[str]]:
    """双向迁移：按需层压到短描述，核心层回填完整描述（幂等）。

    为什么核心层也要回填：分层口径可能演进（例如某个技能从按需层升为核心层），
    此时必须把它的完整描述从索引写回文件——单向的"只压不还原"会让升级后的技能
    永久停留在短描述上，而这正是本项目 2026-09-19 踩过的坑。
    """
    index = emit()
    compacted, restored = [], []
    for name, entry in index["skills"].items():
        target = entry["resident_description"]
        if target == read_description(name):
            continue
        path = SKILLS_ROOT / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        if not m:
            continue
        fm = m.group(1)
        dm = re.search(r"^description:\s*(.+?)(?=\n[a-zA-Z_-]+:|\Z)", fm, re.S | re.M)
        if not dm:
            continue
        escaped = target.replace('"', '\\"')
        new_fm = fm[:dm.start()] + f'description: "{escaped}"' + fm[dm.end():]
        path.write_text(text[:m.start(1)] + new_fm + text[m.end(1):], encoding="utf-8")
        (compacted if entry["tier"] == "ondemand" else restored).append(name)
    return compacted, restored


def check() -> dict:
    """索引/分层与真仓是否同步（CI 与漂移检测用）。"""
    problems = []
    warns = []
    if not INDEX_PATH.is_file():
        return {"ok": False, "problems": [f"索引缺失: {INDEX_PATH.relative_to(TOOLBOX_ROOT)}"]}
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    live = build_index()
    for name in sorted(set(index["skills"]) | set(live["skills"])):
        cur, want = index["skills"].get(name), live["skills"].get(name)
        if cur is None:
            problems.append(f"新增技能未入索引: {name}")
            continue
        if want is None:
            # 2026-09-19：区分"技能被删"与"该技能本就不随公开仓交付"。
            # 索引随仓分发、按完整仓生成，公开 clone 里被 .gitignore 隔离的技能
            # （无 License 上游件）必然"索引有、磁盘无"。这是**预期状态**而非缺陷：
            # 该条目在路由时不会被选中（无对应技能目录可执行），故降为 WARN 不拦截。
            # 反向（磁盘有、索引无）仍是 problem —— 那会让技能漏出索引，属真缺陷。
            warns.append(f"索引含未交付条目（本机无此技能，公开 clone 预期）: {name}")
            continue
        if cur["tier"] != want["tier"]:
            problems.append(f"{name}: tier 漂移（索引 {cur['tier']} ≠ 实况 {want['tier']}）")
        if cur["resident_description"] != want["resident_description"]:
            problems.append(f"{name}: 常驻描述与实况不一致（需重跑 --emit）")
        if cur["full_description"] != want["full_description"] and cur["description_compacted"]:
            problems.append(f"{name}: 索引保存的完整描述已过期")
    return {"ok": not problems, "problems": problems[:20], "warns": warns[:20],
            "warns_total": len(warns), "counts": live["counts"],
            "problems_total": len(problems)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="技能分层常驻：tier 派生 / 路由索引 / 按需层压缩")
    parser.add_argument("--check", action="store_true", help="校验同步（不同步 exit 1）")
    parser.add_argument("--emit", action="store_true", help="生成分层与索引文件")
    parser.add_argument("--compact", action="store_true", help="一次性压缩按需层描述（幂等）")
    parser.add_argument("--reset-full", action="store_true",
                        help="允许 full_description 缩短（仅当确认旧索引内容无用时）")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if args.check:
        res = check()
        if args.as_json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            c = res.get("counts", {})
            print(f"分层：核心 {c.get('core', 0)} / 按需 {c.get('ondemand', 0)}；"
                  f"常驻 {c.get('resident_chars', 0):,} chars（完整 {c.get('full_chars', 0):,}）")
            if res["ok"]:
                print("索引同步：OK")
            else:
                print(f"索引不同步（{res.get('problems_total', 0)} 项）：")
                for prob in res["problems"]:
                    print("  ✗ " + prob)
        return 0 if res["ok"] else 1

    if args.compact:
        compacted, restored = sync_descriptions()
        print(f"按需层压缩 {len(compacted)} 个 / 核心层回填 {len(restored)} 个")
        return 0

    if args.reset_full:
        # ⛔ 危险开关安全网：--reset-full 会放弃索引里保存的原描述。本项目 2026-09-19
        # 两次因误用它而丢失 26/130 条原文（从 git HEAD 恢复）。故先落备份再执行。
        if INDEX_PATH.is_file():
            backup = INDEX_PATH.with_suffix(".json.bak")
            backup.write_text(INDEX_PATH.read_text(encoding="utf-8"),
                              encoding="utf-8", newline="\n")
            print(f"⚠️ --reset-full：已备份旧索引到 {backup.name}（原文丢失可从此恢复）")
    index = emit(keep_previous=not args.reset_full)
    c = index["counts"]
    print(f"已生成：核心 {c['core']} / 按需 {c['ondemand']}")
    print(f"常驻 {c['resident_chars']:,} chars（压缩前 {c['full_chars']:,}）"
          f" ≈ {int(c['resident_chars'] / 2.2):,} tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
