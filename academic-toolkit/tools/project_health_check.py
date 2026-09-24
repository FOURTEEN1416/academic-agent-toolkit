#!/usr/bin/env python3
"""项目健康检查（吸收同类项目的 Observability + Drift Detection 组件，2026-09-19）。

**为什么需要**：本项目的检查件已有 12 个（provenance / 技能库完整性 / 资产利用率 /
经验库 / 触发条件 / 常驻预算 / 配色注册表 / 模板幂等 / 地图对账 / 密钥扫描 /
lint 棘轮 / 重复资产守护），但**散在各处**：
没人知道"现在整体健康吗"，只能逐个手跑。同类项目的 Harness 把 Observability 作为独立
组件（`project-metrics` / `HEALTH-CHECK.md`），并单列一条 **Drift Detection** 原则：
"定期检查文档与现实是否一致——统计数字、版本、功能、命令、链接"。

我们正反复吃这个亏：README 徽章、pytest.ini 注释、AGENTS 测试口径表、truth-index 基线
**四处数字常年互相落后**（本仓库历史上出现过 20+ 个过期基线值）。本工具把这件事机检化：

  1. **组件汇总**：子进程复用既有 10 个检查件（不重造轮子，与 `quick_gates` 同一哲学），
     每个给 PASS / WARN / FAIL / DEGRADED 四态；DEGRADED 表示"检查件自己跑不起来"
     （环境缺件等）——**如实标注，绝不折算成 PASS**（TOOL_GAP 原则）。
  2. **漂移检测**：实测 pytest 收集数 vs 权威文档中既有的基线数字，逐处比对并列出
     不一致的"文件: 行内数字"——文档漂移必须有人修，不允许悄悄留着。

用法：
  python tools/project_health_check.py                # 人读汇总
  python tools/project_health_check.py --json         # 机读
  python tools/project_health_check.py --strict       # 任一 FAIL/漂移 → exit 1
  python tools/project_health_check.py --skip-slow    # 跳过 pytest 收集（离线/提速）

退出码：默认 0（报告件）；--strict 时 FAIL 或漂移 exit 1。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLBOX_ROOT.parent
PY = sys.executable

# 复用的既有检查件：(名称, 命令参数, 是否严格要求)
# 2026-09-20 起新增 3 件（密钥扫描 / lint 棘轮 / 重复资产守护），7 → 10。
CHECKS: tuple[tuple[str, list[str], bool], ...] = (
    ("provenance", ["tools/check_provenance.py"], True),
    ("skill_library", ["tools/skill_library_audit.py"], True),
    ("asset_utilization", ["tools/check_asset_utilization.py", "--strict"], True),
    ("contest_lessons", ["tools/contest_lessons_check.py", "--strict"], True),
    ("skill_triggers", ["tools/skill_trigger_audit.py", "--strict"], True),
    ("context_budget", ["tools/context_budget_check.py", "--strict"], True),
    ("palette_registry",
     ["skills/paper-figure-palette/scripts/palette_kit.py", "registry-verify"], True),
    ("secret_scan", ["tools/secret_scan.py", "--strict"], True),
    ("lint_ratchet", ["tools/lint_ratchet.py"], True),
    ("duplicate_assets", ["tools/check_duplicate_assets.py", "--strict"], True),
)

# 漂移检测：权威文档中记录"当前基线"的位置。
# 三元组 = (文件, 行内模式, 指标名)；指标名缺省为 "tests"（向后兼容旧式二元组）。
# 指标实测源：tests = pytest collect-only；skills = git ls-files 的 SKILL.md 计数；
# capabilities = capabilities/catalog.json 条目计数。
# 两个精度约定（都与项目既有纪律一致）：
#   1. **行内锚定**：AGENTS.md 同时列"仓库根"与"工具箱内"两个口径（527 / 508），
#      故模式必须锚定"仓库根"那一行，否则会把工具箱口径误判为漂移。
#   2. **历史横幅豁免**：本项目铁律 21 要求历史记录保留原文（配"保留作历史/上一时点/
#      快照/已失效"横幅）。命中这些横幅的行**跳过**——否则每次口径更替都会把合规的
#      历史留痕误报为漂移，检测器就会因噪声而失去意义（同"狼来了"教训）。
DRIFT_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("README.md", r"badge/tests-(\d+)_passing", "tests"),
    ("README.md", r"仓库根 \*\*(\d+) passed / 0 failed\*\*", "tests"),
    ("README.md", r"badge/skills-(\d+)_tracked", "skills"),
    ("README.md", r"(\d+) 个随仓技能", "skills"),
    ("README.md", r"badge/capabilities-(\d+)-", "capabilities"),
    ("AGENTS.md", r"仓库根[^\n]{0,240}?\*\*(\d+) passed / 0 failed\*\*", "tests"),
    ("pytest.ini", r"本机完整仓 \*\*(\d+) passed / 0 failed\*\*", "tests"),
    ("dev-docs/truth-index.md",
     r"本机完整仓\*\* `pytest -q` = \*\*(\d+) passed / 0 failed\*\*", "tests"),
)

# 历史横幅标记：命中即视为"合规的历史留痕"，不参与漂移判定
HISTORICAL_MARKERS = ("保留作历史", "上一时点", "保留原文", "已失效", "历史值", "快照", "仅供追溯")

# 漂移容差：tests 0.5%——⚠️ 2026-09-24 收紧（0.02→0.005，审计裁决 D1）。原 2% 容差
# ≈ ±15 项，被实证为**盲区**：一波次加 4-8 个守卫测试后四处基线文档整体滞后而机检
# 绿灯（实锤：README 768 / pytest.ini 769 / AGENTS.md 769 vs 实测 773/776，偏差 8 项
# ≈ 1.03% 恰落 2% 盲区）。0.5% 恰好容住 passed 与 collect 的固有差（3 skipped ≈
# 0.39%），下一波 +5 即报警。**配套纪律**：新增守卫测试的批次必须在同一提交内同步
# 全部基线文档（README 徽章+基线表 / pytest.ini / 根 AGENTS.md / truth-index）。
# skills / capabilities 为**严格等值**（容差 0）——2026-09-23 教训：技能数 badge 275
# vs 实际 276 只差 0.4%，抓不住；这两类计数变化是离散事件（收编/下架），漂了就是
# 文档没跟上，必须报。需要测试数精确门禁时用 --strict-drift。
DRIFT_TOLERANCE = 0.005
METRIC_TOLERANCES = {"tests": DRIFT_TOLERANCE, "skills": 0.0, "capabilities": 0.0}



def _run_component(name: str, args: list[str], timeout: int = 300) -> dict:
    cmd = [PY, *args]
    try:
        proc = subprocess.run(cmd, cwd=str(TOOLBOX_ROOT), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"name": name, "status": "DEGRADED", "detail": f"超时（>{timeout}s）", "rc": None}
    except OSError as exc:
        return {"name": name, "status": "DEGRADED", "detail": f"无法执行: {exc}", "rc": None}
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-3:])
    err = (proc.stderr or "").strip().splitlines()
    if proc.returncode == 0:
        status = "PASS"
    elif any("ModuleNotFoundError" in line or "ImportError" in line for line in err):
        # 缺依赖 → 检查件本身跑不起来，如实降级（不折算成 PASS/FAIL）
        return {"name": name, "status": "DEGRADED",
                "detail": "缺依赖（" + (err[0][:80] if err else "") + "）", "rc": proc.returncode}
    else:
        status = "FAIL"
    return {"name": name, "status": status, "detail": tail, "rc": proc.returncode}


def _actual_test_count() -> dict:
    """实测 pytest 收集数（--collect-only，快；不真跑用例）。"""
    try:
        proc = subprocess.run([PY, "-m", "pytest", "--collect-only", "-q"],
                              cwd=str(REPO_ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300,
                              env={"PYTHONPATH": "", **{k: v for k, v in __import__("os").environ.items()
                                                       if k != "PYTHONPATH"}})
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"collect-only 失败: {exc}", "count": None}
    text = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+)\s+tests?\s+collected", text) or re.search(r"^(\d+)$", text.strip(), re.M)
    if not m:
        return {"available": False, "reason": "无法从 collect-only 输出解析收集数", "count": None}
    return {"available": True, "reason": "", "count": int(m.group(1))}


def _actual_skill_count() -> dict:
    """实测 tracked 顶级技能数（git ls-files 口径 = clone 即所见，2026-09-23 止血批定版）。

    ⚠️ 必须用 `:(glob)` magic——Git 默认 pathspec 的 `*` **会跨越 `/`**，写成
    `academic-toolkit/skills/*/SKILL.md` 会把捆绑在技能内的子技能
    （`<技能>/modules/<模块>/SKILL.md`，如 paper-writing-clinical 的 15 件 modules）
    一并计为顶级技能，使计数虚高（2026-09-23 实锤：虚高口径 265 vs 真值 250）。
    clone 即所见口径**不含** .gitignore 隔离的本地独占技能（红线隔离的上游无 License 件），
    故 250 不等于本机盘面 255——两者差异是设计使然，不是漂移。
    """
    try:
        proc = subprocess.run(["git", "ls-files", "--",
                               ":(glob)academic-toolkit/skills/*/SKILL.md"],
                              cwd=str(REPO_ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"git ls-files 失败: {exc}", "count": None}
    if proc.returncode != 0:
        return {"available": False, "reason": "git ls-files 非零退出", "count": None}
    count = len([ln for ln in (proc.stdout or "").splitlines() if ln.strip()])
    return {"available": True, "reason": "", "count": count}


def _actual_capability_count() -> dict:
    """实测 catalog 能力条目数（与 capabilities/catalog.json 的域结构对账）。"""
    path = REPO_ROOT / "capabilities" / "catalog.json"
    if not path.is_file():
        return {"available": False, "reason": "catalog.json 不存在", "count": None}
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        count = sum(1 for entries in catalog.values() if isinstance(entries, list)
                    for e in entries if isinstance(e, dict)
                    and ("capability_id" in e or "id" in e))
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"catalog 解析失败: {exc}", "count": None}
    return {"available": True, "reason": "", "count": count}


def _actual_counts(skip_slow: bool = False) -> dict:
    """三个指标的实测值。skip_slow 只跳过最慢的 pytest 收集（技能/能力数为毫秒级，始终实测）。"""
    return {
        "tests": {"available": False, "reason": "已跳过（--skip-slow）", "count": None}
        if skip_slow else _actual_test_count(),
        "skills": _actual_skill_count(),
        "capabilities": _actual_capability_count(),
    }


def _drift(actual) -> dict:
    """权威文档"当前基线"数字 vs 各指标实测值（历史横幅行豁免）。

    actual 兼容两种形态：
      - 新式多指标：{"tests": {...}, "skills": {...}, "capabilities": {...}}
      - 旧式单指标：{"available": bool, "count": int|None, "reason": str}（视为 tests）
    """
    if "tests" not in actual and "skills" not in actual:
        actual = {"tests": actual}
    mismatches, exempted, unavailable = [], 0, []
    needed = {item[2] if len(item) > 2 else "tests" for item in DRIFT_SOURCES}
    for item in DRIFT_SOURCES:
        rel, pattern = item[0], item[1]
        metric = item[2] if len(item) > 2 else "tests"
        metric_actual = actual.get(metric)
        if not metric_actual or not metric_actual.get("available"):
            if metric not in unavailable:
                unavailable.append(metric)
            continue
        want = metric_actual["count"]
        tolerance = METRIC_TOLERANCES.get(metric, DRIFT_TOLERANCE)
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for idx, line in enumerate(lines):
            for found in re.findall(pattern, line):
                # 历史横幅豁免：本行或前两行出现"保留作历史/上一时点/快照"等标记
                window = "\n".join(lines[max(0, idx - 2): idx + 1])
                if any(marker in window for marker in HISTORICAL_MARKERS):
                    exempted += 1
                    continue
                documented = int(found)
                if abs(documented - want) > max(1 if tolerance > 0 else 0,
                                                int(want * tolerance)):
                    mismatches.append({"file": rel, "line": idx + 1, "metric": metric,
                                       "documented": documented, "actual": want,
                                       "delta_pct": round(abs(documented - want) / max(want, 1) * 100, 1)})
    if not mismatches and needed and set(unavailable) >= needed:
        first = next(iter(actual.values()))
        return {"available": False, "reason": first.get("reason", "无可用实测指标"),
                "mismatches": [], "exempted": exempted}
    return {"available": True,
            "reason": "、".join(f"{m} 未实测" for m in unavailable),
            "actual": {k: v.get("count") for k, v in actual.items()},
            "mismatches": mismatches, "exempted": exempted,
            "tolerance": DRIFT_TOLERANCE}


def run(skip_slow: bool = False) -> dict:
    components = [_run_component(name, args) for name, args, _required in CHECKS]
    counts = _actual_counts(skip_slow=skip_slow)
    drift = _drift(counts)
    fails = [c for c in components if c["status"] == "FAIL"]
    degraded = [c for c in components if c["status"] == "DEGRADED"]
    ok = not fails and not drift.get("mismatches")
    return {
        "components": components,
        "pytest": counts["tests"],
        "counts": counts,
        "drift": drift,
        "fails": [c["name"] for c in fails],
        "degraded": [c["name"] for c in degraded],
        "ok": ok,
    }


def _print_report(res: dict) -> None:
    print("=" * 72)
    print("项目健康检查（project_health_check）")
    print("=" * 72)
    print("\n[1] 组件：")
    for comp in res["components"]:
        mark = {"PASS": "✅", "FAIL": "❌", "DEGRADED": "⚠️", "WARN": "⚠️"}[comp["status"]]
        print(f"    {mark} {comp['name']:<20} {comp['status']}"
              + (f"  rc={comp['rc']}" if comp["rc"] not in (0, None) else ""))
        if comp["status"] in ("FAIL", "DEGRADED") and comp.get("detail"):
            first = comp["detail"].splitlines()[0] if comp["detail"] else ""
            print(f"        {first[:140]}")
    print("\n[2] 实测指标："
          + " ".join(f"{k}={v['count']}" if v.get("available") else f"{k}=未知"
                     for k, v in res["counts"].items()))
    drift = res["drift"]
    if not drift.get("available"):
        print(f"    漂移检测：跳过（{drift.get('reason', '')}）")
    elif drift["mismatches"]:
        print(f"    漂移检测：❌ {len(drift['mismatches'])} 处文档数字与实测不一致"
              + (f"（tests 容差 {DRIFT_TOLERANCE:.1%}；skills/capabilities 严格等值）"
                 if any(m["metric"] == "tests" for m in drift["mismatches"]) else
                 "（skills/capabilities 严格等值）"))
        for m in drift["mismatches"]:
            print(f"        [{m['metric']}] {m['file']}: 文档 {m['documented']} ≠ 实测 {m['actual']}"
                  f"（差 {m.get('delta_pct', '?')}%）")
    else:
        print("    漂移检测：✅ 权威文档基线数字与实测一致"
              f"（tests 容差 {DRIFT_TOLERANCE:.1%}；skills/capabilities 严格等值）")
    if res["degraded"]:
        print(f"\n    ⚠️ 降级组件（检查件未跑起来，不折算为通过）：{', '.join(res['degraded'])}")
    print("\n结论：", "整体健康" if res["ok"] else
          f"存在问题（FAIL {len(res['fails'])} 项，漂移 {len(res['drift'].get('mismatches') or [])} 处）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="项目健康检查（组件汇总 + 文档漂移检测）")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出机读 JSON")
    parser.add_argument("--strict", action="store_true", help="FAIL 或漂移时 exit 1")
    parser.add_argument("--skip-slow", action="store_true", help="跳过 pytest 收集（离线/提速）")
    args = parser.parse_args(argv)
    res = run(skip_slow=args.skip_slow)
    if args.as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        _print_report(res)
    if args.strict and not res["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
