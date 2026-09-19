#!/usr/bin/env python3
"""项目健康检查（吸收同类项目的 Observability + Drift Detection 组件，2026-09-19）。

**为什么需要**：本项目的检查件已有 9 个（provenance / 技能库完整性 / 资产利用率 /
经验库 / 触发条件 / 常驻预算 / 配色注册表 / 模板幂等 / 地图对账），但**散在各处**：
没人知道"现在整体健康吗"，只能逐个手跑。同类项目的 Harness 把 Observability 作为独立
组件（`project-metrics` / `HEALTH-CHECK.md`），并单列一条 **Drift Detection** 原则：
"定期检查文档与现实是否一致——统计数字、版本、功能、命令、链接"。

我们正反复吃这个亏：README 徽章、pytest.ini 注释、AGENTS 测试口径表、truth-index 基线
**四处数字常年互相落后**（本仓库历史上出现过 20+ 个过期基线值）。本工具把这件事机检化：

  1. **组件汇总**：子进程复用既有 9 个检查件（不重造轮子，与 `quick_gates` 同一哲学），
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
CHECKS: tuple[tuple[str, list[str], bool], ...] = (
    ("provenance", ["tools/check_provenance.py"], True),
    ("skill_library", ["tools/skill_library_audit.py"], True),
    ("asset_utilization", ["tools/check_asset_utilization.py", "--strict"], True),
    ("contest_lessons", ["tools/contest_lessons_check.py", "--strict"], True),
    ("skill_triggers", ["tools/skill_trigger_audit.py", "--strict"], True),
    ("context_budget", ["tools/context_budget_check.py", "--strict"], True),
    ("palette_registry",
     ["skills/paper-figure-palette/scripts/palette_kit.py", "registry-verify"], True),
)

# 漂移检测：权威文档中记录"当前基线"的位置。
# 两个精度约定（都与项目既有纪律一致）：
#   1. **行内锚定**：AGENTS.md 同时列"仓库根"与"工具箱内"两个口径（527 / 508），
#      故模式必须锚定"仓库根"那一行，否则会把工具箱口径误判为漂移。
#   2. **历史横幅豁免**：本项目铁律 21 要求历史记录保留原文（配"保留作历史/上一时点/
#      快照/已失效"横幅）。命中这些横幅的行**跳过**——否则每次口径更替都会把合规的
#      历史留痕误报为漂移，检测器就会因噪声而失去意义（同"狼来了"教训）。
DRIFT_SOURCES: tuple[tuple[str, str], ...] = (
    ("README.md", r"badge/tests-(\d+)_passing"),
    ("README.md", r"仓库根 \*\*(\d+) passed / 0 failed\*\*"),
    ("AGENTS.md", r"仓库根[^\n]{0,240}?\*\*(\d+) passed / 0 failed\*\*"),
    ("pytest.ini", r"本机完整仓 \*\*(\d+) passed / 0 failed\*\*"),
    ("dev-docs/truth-index.md",
     r"本机完整仓\*\* `pytest -q` = \*\*(\d+) passed / 0 failed\*\*"),
)

# 历史横幅标记：命中即视为"合规的历史留痕"，不参与漂移判定
HISTORICAL_MARKERS = ("保留作历史", "上一时点", "保留原文", "已失效", "历史值", "快照", "仅供追溯")

# 漂移容差（默认 2%）：本项目常有**并行窗口**同时增删测试与更新文档，严格等值会
# 在并发编辑期间持续误报，把真漂移淹掉（狼来了）。2% 仍能抓住"463 vs 576"这类真过期
# （20% 级），同时容忍并行窗口的窗口期抖动。需要精确门禁时用 --strict-drift。
DRIFT_TOLERANCE = 0.02



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


def _drift(actual: dict) -> dict:
    """权威文档"当前基线"数字 vs 实测收集数（历史横幅行豁免）。"""
    if not actual.get("available"):
        return {"available": False, "reason": actual.get("reason", ""), "mismatches": [],
                "exempted": 0}
    want = actual["count"]
    mismatches, exempted = [], 0
    for rel, pattern in DRIFT_SOURCES:
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
                if abs(documented - want) > max(1, int(want * DRIFT_TOLERANCE)):
                    mismatches.append({"file": rel, "line": idx + 1,
                                       "documented": documented, "actual": want,
                                       "delta_pct": round(abs(documented - want) / max(want, 1) * 100, 1)})
    return {"available": True, "reason": "", "actual": want,
            "mismatches": mismatches, "exempted": exempted,
            "tolerance": DRIFT_TOLERANCE}


def run(skip_slow: bool = False) -> dict:
    components = [_run_component(name, args) for name, args, _required in CHECKS]
    actual = {"available": False, "reason": "已跳过（--skip-slow）", "count": None} if skip_slow \
        else _actual_test_count()
    drift = _drift(actual)
    fails = [c for c in components if c["status"] == "FAIL"]
    degraded = [c for c in components if c["status"] == "DEGRADED"]
    ok = not fails and not drift.get("mismatches")
    return {
        "components": components,
        "pytest": actual,
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
    py = res["pytest"]
    print(f"\n[2] 测试收集：{'实测 ' + str(py['count']) if py.get('available') else '未知（' + py.get('reason', '') + '）'}")
    drift = res["drift"]
    if not drift.get("available"):
        print(f"    漂移检测：跳过（{drift.get('reason', '')}）")
    elif drift["mismatches"]:
        print(f"    漂移检测：❌ {len(drift['mismatches'])} 处文档数字与实测不一致"
              f"（容差 {drift.get('tolerance', 0):.0%}）")
        for m in drift["mismatches"]:
            print(f"        {m['file']}: 文档 {m['documented']} ≠ 实测 {m['actual']}"
                  f"（差 {m.get('delta_pct', '?')}%）")
    else:
        print(f"    漂移检测：✅ 权威文档基线数字与实测一致（容差 {drift.get('tolerance', 0):.0%}）")
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
