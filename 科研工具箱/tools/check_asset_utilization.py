#!/usr/bin/env python3
"""资产利用率审计（2026-09-12 资产缺口研究的反馈闭环件）。

三类审计，对应"十四步流程资产未充分使用"研究的三个缺口：
  1. utilization  —— 扫 workspaces/*/evidence 的 companion_skills/assets 申报账本，
     输出各技能/资产的 used/skipped 率（死推荐 = 被推荐 N 次被用 0 次一览无余）；
  2. map-coverage —— skills/ 实存技能 vs CONTEST_SKILL_MAP.md 五类覆盖的零漏网机检
     （固化 2026-09-11 的一次性对账为可重跑工具）；
  3. assets-paths —— templates.json 各步 assets 指针的仓库根相对路径存在性校验
     （资产指针指向不存在文件 = 假接线，必查）。

用法：
  python tools/check_asset_utilization.py                # 三类审计，人读输出
  python tools/check_asset_utilization.py --json         # 机读 JSON
  python tools/check_asset_utilization.py --strict       # 覆盖缺口/假接线时 exit 1
  python tools/check_asset_utilization.py --workspaces X # 指定工作区根（默认 <仓库根>/workspaces）

退出码：默认恒 0（审计报告件，不拦截）；--strict 时发现缺口/假接线 exit 1。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLBOX_ROOT = Path(__file__).resolve().parents[1]
NON_SKILL_DIRS = {"_utils", "shared-scripts"}


def iter_skill_dirs(skills_root: Path) -> list[str]:
    """skills/ 下含 SKILL.md 的目录名（排除 _utils/shared-scripts 两个非技能目录）。"""
    if not skills_root.is_dir():
        return []
    return sorted(
        p.name for p in skills_root.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file() and p.name not in NON_SKILL_DIRS
    )


def _expand_slash_groups(text: str) -> str:
    """斜杠缩写展开（对账口径之一，2026-09-11 首轮对账即含此规则）：
    "copyright-build/draft/source-materials" = copyright-build + copyright-draft
    + copyright-source-materials（共享前缀 = 头段去尾段）。展开后逐名词边界匹配。"""
    def _expand(m: re.Match) -> str:
        head, segs = m.group(1), m.group(2).split("/")
        base = head.rsplit("-", 1)[0] if "-" in head else head
        family = [head] + [f"{base}-{s}" for s in segs]
        return " ".join(family)
    return re.sub(
        r"(?<![A-Za-z0-9_-])([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9-]+(?:/[A-Za-z0-9-]+)*)",
        _expand, text)


def load_map_coverage(map_path: Path, skill_names: list[str]) -> dict:
    """CONTEST_SKILL_MAP.md 覆盖对账：显式具名（词边界）+ 斜杠缩写展开 + 前缀域展开（fnmatch）。

    返回 {"covered", "missing", "prefix_domains"}：missing 必须为空（零漏网口径）。
    """
    text = map_path.read_text(encoding="utf-8") if map_path.is_file() else ""
    text = _expand_slash_groups(text)
    covered: set[str] = set()
    for name in skill_names:
        if re.search(r"(?<![A-Za-z0-9_-])" + re.escape(name) + r"(?![A-Za-z0-9_-])", text):
            covered.add(name)
    prefixes = sorted(set(re.findall(r"(?<![A-Za-z0-9_-])([A-Za-z0-9][A-Za-z0-9-]*)-\*", text)))
    prefix_matched: set[str] = set()
    for name in skill_names:
        if name in covered:
            continue
        for prefix in prefixes:
            if fnmatch.fnmatchcase(name, prefix + "-*"):
                prefix_matched.add(name)
                break
    covered |= prefix_matched
    return {
        "covered": sorted(covered),
        "missing": sorted(set(skill_names) - covered),
        "prefix_domains": prefixes,
    }


def _declaration_stats(value, used_key: str) -> tuple[list[str], list[str]]:
    """从申报对象取 (used, skipped_names)；格式异常一律记 used/skipped 为空并返回。"""
    if not isinstance(value, dict):
        return [], []
    used = [u for u in value.get("used", []) if isinstance(u, str)]
    skipped = []
    for s in value.get("skipped", []):
        if isinstance(s, dict) and str(s.get(used_key, "")).strip():
            skipped.append(str(s[used_key]))
    return used, skipped


def scan_evidence(workspaces_root: Path) -> dict:
    """扫 workspaces/*/.engine/evidence/*.json 的申报账本，汇总利用率。"""
    companion = {}  # skill -> {recommended, used, skipped}
    assets = {}     # asset name -> {offered, used, skipped}
    workflows = []  # per-workspace 汇总
    if not workspaces_root.is_dir():
        return {"workflows": [], "companion": {}, "assets": {}, "totals": {}}
    for ws in sorted(p for p in workspaces_root.iterdir() if p.is_dir()):
        ev_dir = ws / ".engine" / "evidence"
        if not ev_dir.is_dir():
            continue
        steps_declared = steps_used = steps_skipped = 0
        for ev_file in sorted(ev_dir.glob("*.json")):
            try:
                ev = json.loads(ev_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(ev, dict):
                continue
            # 证据文件为 {"action", "evidence", "manifest", "schema_version"} 包装结构，
            # 申报字段在 evidence 内层；兼容历史裸 evidence 形态。
            inner = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else ev
            skill_name = str(inner.get("skill_name") or (ev.get("action") or {}).get("skill_name", "")).strip()
            comp_used, comp_skipped = _declaration_stats(inner.get("companion_skills"), "skill")
            a_used, a_skipped = _declaration_stats(inner.get("assets"), "name")
            if not (comp_used or comp_skipped or a_used or a_skipped):
                continue
            steps_declared += 1
            steps_used += len(comp_used) + len(a_used)
            steps_skipped += len(comp_skipped) + len(a_skipped)
            # companion 统计口径：used+skipped 即该步实际申报的推荐清单覆盖数
            touched = set(comp_used) | set(comp_skipped)
            for name in touched:
                slot = companion.setdefault(name, {"recommended": 0, "used": 0, "skipped": 0})
                slot["recommended"] += 1
                slot["used"] += 1 if name in comp_used else 0
                slot["skipped"] += 1 if name in comp_skipped else 0
            for name in set(a_used) | set(a_skipped):
                slot = assets.setdefault(name, {"offered": 0, "used": 0, "skipped": 0})
                slot["offered"] += 1
                slot["used"] += 1 if name in a_used else 0
                slot["skipped"] += 1 if name in a_skipped else 0
        if steps_declared:
            workflows.append({"workspace": ws.name, "steps_declared": steps_declared,
                              "used": steps_used, "skipped": steps_skipped})
    totals = {
        "workflows_with_evidence": len(workflows),
        "steps_declared": sum(w["steps_declared"] for w in workflows),
        "used": sum(w["used"] for w in workflows),
        "skipped": sum(w["skipped"] for w in workflows),
    }
    totals["use_rate"] = round(totals["used"] / (totals["used"] + totals["skipped"]), 4) \
        if (totals["used"] + totals["skipped"]) else None
    return {"workflows": workflows, "companion": companion, "assets": assets, "totals": totals}


def dead_recommendations(companion_stats: dict) -> list[dict]:
    """死推荐：被推荐 ≥1 次且 used=0 的技能，按被跳次数降序。"""
    dead = [
        {"skill": name, **stats}
        for name, stats in companion_stats.items()
        if stats["recommended"] > 0 and stats["used"] == 0
    ]
    return sorted(dead, key=lambda d: (-d["recommended"], d["skill"]))


def check_template_assets(templates_path: Path, repo_root: Path) -> dict:
    """templates.json 全模板 assets 指针存在性校验（仓库根相对）。"""
    if not templates_path.is_file():
        return {"checked": 0, "missing": [], "error": f"templates not found: {templates_path}"}
    try:
        data = json.loads(templates_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"checked": 0, "missing": [], "error": f"templates unreadable: {exc}"}
    checked, missing = 0, []
    for tpl_name, tpl in data.items():
        if not isinstance(tpl, dict):
            continue
        for step in tpl.get("sub_steps", []):
            if not isinstance(step, dict):
                continue
            for asset in ((step.get("metadata") or {}).get("assets") or []):
                if not isinstance(asset, dict):
                    continue
                checked += 1
                rel = str(asset.get("path", "")).strip()
                if rel and not (repo_root / rel).exists():
                    missing.append({"template": tpl_name, "step": step.get("skill_name"),
                                    "asset": asset.get("name"), "path": rel})
    return {"checked": checked, "missing": missing}


def _print_report(result: dict) -> None:
    totals = result["utilization"]["totals"]
    print("=" * 72)
    print("资产利用率审计（check_asset_utilization）")
    print("=" * 72)
    print(f"\n[1] 申报账本利用率：{totals.get('workflows_with_evidence', 0)} 个工作区 / "
          f"{totals.get('steps_declared', 0)} 步申报 / used {totals.get('used', 0)} / "
          f"skipped {totals.get('skipped', 0)} / 利用率 {totals.get('use_rate')}")
    comp = result["utilization"]["companion"]
    if comp:
        rows = sorted(comp.items(), key=lambda kv: (kv[1]["used"], -kv[1]["recommended"], kv[0]))
        print(f"\n    {'技能':<44}{'荐':>4}{'用':>4}{'跳':>4}")
        for name, s in rows:
            print(f"    {name:<44}{s['recommended']:>4}{s['used']:>4}{s['skipped']:>4}")
    dead = result["dead_recommendations"]
    if dead:
        print(f"\n    死推荐（荐而从未用）{len(dead)} 个：" +
              ", ".join(d["skill"] for d in dead))
        # 统计纪律（2026-09-19 治理收口）：死推荐的含义随样本量而变，禁止无条件据其修剪。
        _ws = totals.get("workflows_with_evidence", 0)
        if _ws < 3:
            print(f"    ⚠️ 样本不足：当前仅 {_ws} 个工作区的申报账本。**样本 < 3 时不得据此修剪"
                  "推荐清单**——单一样本中的\"从未用\"极可能是\"场景不匹配\"（如专利/基金域技能在"
                  "数模工作区自然不会用），而非推荐冗余。请先按场景分类再裁（见 CONTEST_SKILL_MAP"
                  " §二/§三），或待积累 ≥3 个真实工作区后复核。")
        else:
            print(f"    ℹ️ 样本 {_ws} 个工作区；修剪前仍须按场景分类剔除\"场景不匹配\"项，"
                  "不可仅按 used=0 直接删（见 CONTEST_SKILL_MAP §二/§三）。")
    assets = result["utilization"]["assets"]
    if assets:
        print(f"\n    资产申报：{sum(a['offered'] for a in assets.values())} 次提供 / "
              f"{sum(a['used'] for a in assets.values())} used / "
              f"{sum(a['skipped'] for a in assets.values())} skipped")
        for name, s in sorted(assets.items()):
            print(f"      {name}: 荐{s['offered']} 用{s['used']} 跳{s['skipped']}")
    cov = result["map_coverage"]
    print(f"\n[2] 技能地图对账：实存 {cov['skills_total']} 技能 / 覆盖 {len(cov['covered'])} / "
          f"漏网 {len(cov['missing'])}（前缀域 {len(cov['prefix_domains'])} 个）")
    if cov["missing"]:
        print("    漏网（必须归入 CONTEST_SKILL_MAP 五类之一）: " + ", ".join(cov["missing"]))
    tpl = result["template_assets"]
    _miss = tpl.get("missing", [])
    _undelivered = [m for m in _miss if is_local_only_asset(m.get("path", ""))]
    _fake = [m for m in _miss if not is_local_only_asset(m.get("path", ""))]
    print(f"[3] 模板资产指针：校验 {tpl.get('checked', 0)} 条 / 失联 {len(_miss)}"
          f"（未交付私有资产 {len(_undelivered)} / 真假接线 {len(_fake)}）")
    for m in _fake:
        print(f"    ❌ 假接线: {m['template']}/{m['step']} — {m['asset']} → {m['path']}")
    for m in _undelivered:
        print(f"    ○ 未交付（公开 clone 不含该私有资料区，不拦截）: {m['path']}")
    if tpl.get("error"):
        print(f"    ⚠️ {tpl['error']}")


# 公开 clone / CI 不交付的本地私有资料区（被根 .gitignore 隔离）。
# 资产指针落在这些前缀下时，缺失属"未交付"而非"假接线"——strict 不据此拦截。
# 与 tests/test_asset_utilization.py 的 LOCAL_ASSET_ROOTS 同源，此处为工具侧单一真源。
LOCAL_ONLY_ASSET_ROOTS = ("参考论文", "参考图", "CUMCM论文模板", "CUMCM2026Problems")


def is_local_only_asset(path: str) -> bool:
    """该资产路径是否落在不随公开仓交付的私有资料区下。"""
    p = str(path or "").replace("\\", "/").lstrip("./")
    return any(p == r or p.startswith(r + "/") for r in LOCAL_ONLY_ASSET_ROOTS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="资产利用率审计（账本/地图对账/资产在位）")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="仓库根（资产路径与 workspaces 的解析基准）")
    parser.add_argument("--workspaces", default=None, help="工作区根目录（默认 <repo>/workspaces）")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出机读 JSON")
    parser.add_argument("--strict", action="store_true", help="地图漏网或资产失联时 exit 1")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    workspaces_root = Path(args.workspaces) if args.workspaces else repo / "workspaces"
    skills_root = TOOLBOX_ROOT / "skills"
    skill_names = iter_skill_dirs(skills_root)

    cov = load_map_coverage(TOOLBOX_ROOT / "CONTEST_SKILL_MAP.md", skill_names)
    cov["skills_total"] = len(skill_names)
    util = scan_evidence(workspaces_root)
    tpl = check_template_assets(TOOLBOX_ROOT / "engine" / "modex-core" / "templates.json", repo)

    result = {
        "repo": str(repo),
        "skills_total": len(skill_names),
        "map_coverage": cov,
        "utilization": util,
        "dead_recommendations": dead_recommendations(util["companion"]),
        "template_assets": tpl,
    }
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_report(result)
    # 2026-09-19：资产指针落在 gitignored 私有资料区时，缺失属"公开 clone 未交付"
    # 而非"假接线"——否则公开仓/CI 上 project_health_check 的 asset_utilization
    # 组件会误报 FAIL（实测公开 clone 唯一 FAIL 组件即此）。
    fake_wiring = [m for m in (tpl.get("missing") or [])
                   if not is_local_only_asset(m.get("path", ""))]
    if args.strict and (cov["missing"] or fake_wiring):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
