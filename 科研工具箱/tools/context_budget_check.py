#!/usr/bin/env python3
"""常驻上下文预算审计（吸收自同类项目的上下文税纪律，2026-09-19）。

**为什么需要这个工具**：技能 frontmatter 的 `name` + `description` 是**每会话常驻**的
（宿主必须在选择技能前就知道"有哪些技能"）。同行项目把它量化得很清楚——
another-agent-skills 常驻约 3,870 tokens（占 200K 的 1.9%），并把"技能本体做成
250 行索引、细节按需加载"当作硬纪律（lazy loading）。

**本项目实测（2026-09-19，261 技能）**：常驻 description 合计 74,607 字符
≈ 34,000 tokens ≈ 200K 上下文的 **17%**——是同行量级的近 10 倍。这不是"描述写得好"，
而是机制性风险：常驻层越胖，① 每会话固定付税；② 261 条描述互相干扰（注意力稀释），
直接损害"调用的准确性"（P3 的诉求）；③ 新增技能越多越糟，是**只增不减的负债**。

**两条可机检的判据**：

  1. **预算上限**（TOTAL_DESC_CEILING）：description 合计字符数不得超上限——
     把"常驻税"变成一个有天花板、可棘轮回归的量，而不是感觉问题。
  2. **描述污染**（POLLUTION）：description 是**搜索索引**，不是文档。出现
     步骤编号、仓库路径、门禁名、哈希字段、`→` 流程箭头等**实施细节**即判污染——
     这些属于 SKILL.md 正文（按需加载层），放在常驻层是纯浪费。

上游族（ars-/galaxy-/latexpap-/nature-/spine-paper-/dev- 等 vendored 技能）的
描述随上游分发，**只计数不计罚**（改描述会与上游分叉）；罚只落本地自研技能。
豁免必须显式登记在 `UPSTREAM_FAMILIES`，不做隐式放过。

用法：
  python tools/context_budget_check.py              # 人读报告
  python tools/context_budget_check.py --json       # 机读
  python tools/context_budget_check.py --strict     # 超预算或本地污染时 exit 1

退出码：默认 0（报告件）；--strict 时 FAIL exit 1。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = TOOLBOX_ROOT / "skills"
sys.path.insert(0, str(TOOLBOX_ROOT / "tools"))

import skill_trigger_audit as sta  # noqa: E402

# ── 预算（2026-09-19 标定：实测 74,607 → 目标留 15% 余量后设天花板） ──────
TOTAL_DESC_CEILING = 34_000      # 全库**常驻** description 合计字符上限（分层后实测 32,773 + 4% 余量）
# 分层上限（2026-09-19 技能分层常驻落地）：按需层压到短索引，完整描述移入
# data/skill_routing_index.json 按需读取。核心层保持完整（压缩核心层＝拿路由准确率换指标）。
PER_SKILL_DESC_CEILING = 512     # 核心层单条上限（本地自研）
ONDEMAND_DESC_CEILING = 132      # 按需层单条上限（build_skill_index.OND_RESEARCH_CAP + 余量）
INDEX_PATH = TOOLBOX_ROOT / "data" / "skill_routing_index.json"

# 外部集成族前缀：这些技能的描述随上游仓库分发，改它＝与上游分叉（只计数不计罚）。
# 注意：**只列真正的外部族**——本校自研的六域技能（course-/humanities-/patent-/copyright-/
# research-/idea-/dev- 等）属本地资产，必须计入罚则，不得靠前缀逃避预算。
UPSTREAM_FAMILIES = ("ars-", "galaxy-", "latexpap-", "spine-paper-", "nature-")


def has_upstream_ledger(name: str) -> bool:
    """溯源台账判定：技能目录内有 UPSTREAM.md（或其 references/ 下有）即视为上游集成件。"""
    d = SKILLS_ROOT / name
    return (d / "references" / "UPSTREAM.md").is_file() or (d / "UPSTREAM.md").is_file()

# 实施细节污染判据（description 应是搜索索引，这些应留在 SKILL.md 正文）
POLLUTION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"→", "流程箭头（逐步流程属正文）"),
    (r"科研工具箱/|skills/|tools/|engine/|_utils/|shared-scripts/", "仓库路径（属正文）"),
    (r"步骤\s*[1-9]|Step\s*[1-9]", "步骤编号（属正文）"),
    (r"门禁|gates?\b|哈希|sha256|min_bytes", "门禁/哈希实现细节（属正文）"),
    (r"──|===|\|\s*$", "表格/分隔线（属正文）"),
)


def iter_skill_dirs() -> list[str]:
    return sta.iter_skill_names()


def is_upstream(name: str) -> bool:
    """外部来源判定：外部族前缀 ∪ 溯源台账在位（两信号取并，口径写进报告）。"""
    return name.startswith(UPSTREAM_FAMILIES) or has_upstream_ledger(name)


def load_tiers() -> dict[str, str]:
    """读分层（由 build_skill_index 派生）；缺失时全部按核心层对待（不放松罚则）。"""
    try:
        data = json.loads((TOOLBOX_ROOT / "data" / "skill_tiers.json").read_text(encoding="utf-8"))
        return dict(data.get("tiers") or {})
    except Exception:
        return {}


def measure() -> dict:
    global TIERS
    TIERS = load_tiers()
    records = sta.audit_skills(SKILLS_ROOT)["records"]
    rows = []
    for name, rec in records.items():
        desc = rec["description"]
        hits = [why for pat, why in POLLUTION_PATTERNS if re.search(pat, desc)]
        tier = TIERS.get(name, "core")
        rows.append({
            "skill": name,
            "chars": len(desc),
            "upstream": is_upstream(name),
            "tier": tier,
            "pollution": hits,
        })
    rows.sort(key=lambda r: -r["chars"])
    total = sum(r["chars"] for r in rows)
    own_total = sum(r["chars"] for r in rows if not r["upstream"])
    up_total = total - own_total
    local_polluted = [r for r in rows if r["pollution"] and not r["upstream"]]
    upstream_polluted = [r for r in rows if r["pollution"] and r["upstream"]]
    over_cap = [r for r in rows
                if not r["upstream"] and r["chars"] > (
                    ONDEMAND_DESC_CEILING if r["tier"] == "ondemand" else PER_SKILL_DESC_CEILING)]
    errors, warns = [], []
    if total > TOTAL_DESC_CEILING:
        errors.append(f"常驻 description 合计 {total:,} 字符 > 上限 {TOTAL_DESC_CEILING:,}"
                      f"（超出 {total - TOTAL_DESC_CEILING:,}）")
    if local_polluted:
        errors.append(f"本地自研技能描述含实施细节 {len(local_polluted)} 个"
                      f"（共 {sum(r['chars'] for r in local_polluted):,} 字符）："
                      + ", ".join(r["skill"] for r in local_polluted[:8]))
    if over_cap:
        warns.append(f"本地自研技能描述超单条上限 {PER_SKILL_DESC_CEILING}：{len(over_cap)} 个")
    if upstream_polluted:
        warns.append(f"上游族描述含实施细节 {len(upstream_polluted)} 个（随上游分发，只计数不计罚）")
    # 常驻税估算：混排中文按 ~2.2 字符/token
    est_tokens = int(total / 2.2) + sum(30 + len(r["skill"]) for r in rows) // 2
    return {
        "skills_total": len(rows),
        "total_chars": total,
        "own_chars": own_total,
        "upstream_chars": up_total,
        "est_resident_tokens": est_tokens,
        "share_of_200k": round(est_tokens / 200_000 * 100, 1),
        "ceilings": {"total_desc": TOTAL_DESC_CEILING, "per_skill": PER_SKILL_DESC_CEILING,
                     "ondemand": ONDEMAND_DESC_CEILING},
        "local_polluted": local_polluted,
        "upstream_polluted": upstream_polluted,
        "over_cap": over_cap,
        "longest": rows[:10],
        "errors": errors,
        "warns": warns,
        "ok": not errors,
    }


TIERS: dict[str, str] = {}


def _print_report(res: dict) -> None:
    print("=" * 72)
    print("常驻上下文预算审计（context_budget_check）")
    print("=" * 72)
    print(f"\n[1] 常驻规模：{res['skills_total']} 技能 / description {res['total_chars']:,} 字符"
          f"（自研 {res['own_chars']:,} + 上游 {res['upstream_chars']:,}）")
    print(f"    估算常驻 ≈ {res['est_resident_tokens']:,} tokens（200K 上下文的 {res['share_of_200k']}%）")
    print(f"    上限 {res['ceilings']['total_desc']:,} 字符（分层：核心 ≤"
          f"{res['ceilings']['per_skill']} / 按需 ≤{res['ceilings']['ondemand']}）→ "
          f"{'OK' if res['total_chars'] <= res['ceilings']['total_desc'] else 'FAIL'}")
    print("\n[2] 描述污染（description 应为搜索索引，非文档）：")
    print(f"    本地自研 {len(res['local_polluted'])} 个（计罚）／"
          f"上游族 {len(res['upstream_polluted'])} 个（只计数）")
    for row in res["local_polluted"][:12]:
        print(f"      {row['chars']:>4}  {row['skill']:<40} {'；'.join(row['pollution'][:2])}")
    print("\n[3] 最长 10 条：")
    for row in res["longest"]:
        flag = "上游" if row["upstream"] else "自研"
        print(f"      {row['chars']:>4}  [{flag}] {row['skill']}")
    if res["warns"]:
        print("\n== WARN ==")
        for w in res["warns"]:
            print("  ⚠️ " + w)
    if res["errors"]:
        print("\n== FAIL ==")
        for e in res["errors"]:
            print("  ✗ " + e)
    print("\n结论：", "预算内且无本地污染" if res["ok"] else "超预算或存在本地描述污染")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="常驻上下文预算审计（技能 frontmatter 税）")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出机读 JSON")
    parser.add_argument("--strict", action="store_true", help="FAIL 时 exit 1")
    args = parser.parse_args(argv)
    res = measure()
    if args.as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        _print_report(res)
    if args.strict and not res["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
