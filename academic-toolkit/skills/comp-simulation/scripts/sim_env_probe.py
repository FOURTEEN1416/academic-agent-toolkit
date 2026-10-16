#!/usr/bin/env python3
"""仿真引擎可用性探测（不联网、不安装）。

用途：comp-simulation 开场先跑——决定可选路径。缺席引擎如实记 unavailable，不阻断。

用法：
    python skills/comp-simulation/scripts/sim_env_probe.py
    python skills/comp-simulation/scripts/sim_env_probe.py --json

退出码：0 = 有可用引擎（或至少纯标准库路径可用）；2 = 全缺席（仍可走标准库最小实现）。
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys

# (导入名, 展示名, 方向, 赛道)
TARGETS: list[tuple[str, str, str, str]] = [
    ("mesa", "Mesa", "多智能体 ABM", "A"),
    ("mesa_geo", "Mesa-Geo", "空间 ABM", "A/B"),
    ("simpy", "SimPy", "离散事件 DES", "B/C"),
    ("salabim", "Salabim", "DES + 动画", "B"),
    ("pysd", "PySD", "系统动力学 SD", "B/C"),
    ("scipy", "SciPy", "连续系统 / 数值", "通用"),
    ("numpy", "NumPy", "数值 / 蒙特卡洛", "通用"),
    ("pandas", "pandas", "账本与统计", "通用"),
    ("matplotlib", "matplotlib", "出图", "通用"),
    ("pymoo", "pymoo", "多目标优化", "C"),
    ("stable_baselines3", "stable-baselines3", "强化学习", "C"),
    ("pymc", "PyMC", "贝叶斯校准 / UQ", "C"),
    ("SALib", "SALib", "敏感性分析", "通用"),
    ("pyDOE3", "pyDOE3", "实验设计 DOE", "通用"),
    ("sklearn", "scikit-learn", "机器学习基线", "C"),
    ("statsmodels", "statsmodels", "统计建模", "C"),
    ("networkx", "networkx", "网络 / 图论", "A/B"),
    ("sympy", "sympy", "符号推导", "通用"),
]


def probe() -> list[dict]:
    rows: list[dict] = []
    for mod, label, direction, track in TARGETS:
        row = {"module": mod, "name": label, "direction": direction, "track": track}
        try:
            m = importlib.import_module(mod)
            row["installed"] = True
            row["version"] = str(getattr(m, "__version__", "unknown"))
        except Exception as exc:  # noqa: BLE001 — 探测就是要吞掉一切导入异常
            row["installed"] = False
            row["version"] = None
            row["import_error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="仿真引擎可用性探测（只读、离线）")
    ap.add_argument("--json", action="store_true", help="机读 JSON 输出")
    args = ap.parse_args(argv)

    import platform

    rows = probe()
    available = [r for r in rows if r["installed"]]
    missing = [r for r in rows if not r["installed"]]

    if args.json:
        print(json.dumps({
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "available": len(available),
            "missing": len(missing),
            "libs": rows,
            "stdlib_only": len(available) == 0,
        }, ensure_ascii=False, indent=2))
    else:
        print("=" * 68)
        print("仿真引擎探测（comp-simulation / 离线只读）")
        print("=" * 68)
        print(f"Python {sys.version.split()[0]}  ·  {platform.platform()}")
        print(f"\n可用 {len(available)} / {len(rows)}\n")
        w = max(len(r["name"]) for r in rows)
        for r in rows:
            mark = "OK  " if r["installed"] else "MISS"
            ver = r["version"] or "-"
            print(f"  {mark}  {r['name']:<{w}}  {ver:<14} {r['direction']}  [{r['track']}]")
        if missing:
            print("\n缺席（如实记为 unavailable，不阻断）：")
            for r in missing:
                print(f"  - {r['name']}: {r['import_error']}")
            print("\n  安装示例：pip install " + " ".join(
                {"mesa": "mesa", "mesa_geo": "mesa-geo", "simpy": "simpy",
                 "salabim": "salabim", "pysd": "pysd", "pymoo": "pymoo",
                 "stable_baselines3": "stable-baselines3", "pymc": "pymc",
                 "SALib": "SALib", "pyDOE3": "pyDOE3", "sklearn": "scikit-learn",
                 "statsmodels": "statsmodels"}.get(r["module"], r["module"])
                for r in missing[:6]))
        print("\n提示：方法论层（选型/V&V/实验设计）不依赖任何特定库——全缺席亦可走标准库最小实现。")

    return 0 if available else 2


if __name__ == "__main__":
    raise SystemExit(main())
