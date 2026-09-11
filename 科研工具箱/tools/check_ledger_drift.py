#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多窗口账本漂移巡检与自动修复（2026-09-11 赛时新增）。

背景：ZCode/OpenCode 双宿主并行窗口下，审计 hook 的落账路径按进程 cwd 相对解析，
会在 skills/_utils/.engine、科研工具箱/.engine/audit、skills/shared-scripts/.engine
等位置产生"分账"（真实交互记录落错位置）——触发 test_dual_copy_consistency 挂 +
账本碎片化。本工具巡检已知漂移点，--fix 时按 ts 升序补账合并至主账本并清除错位文件。

用法：
    python tools/check_ledger_drift.py          # 只巡检报告
    python tools/check_ledger_drift.py --fix    # 巡检 + 补账合并 + 清理错位
退出码：0=干净或已修复；1=发现漂移（未加 --fix）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAIN_LEDGER = REPO / ".engine" / "audit" / "operations.jsonl"
# 已知漂移点（相对仓库根；随新症状追加）
DRIFT_GLOBS = [
    "科研工具箱/skills/_utils/.engine/audit/operations.jsonl",
    "科研工具箱/skills/shared-scripts/.engine/audit/operations.jsonl",
    "科研工具箱/.engine/audit/operations.jsonl",
    ".engine/audit/operations_*.jsonl",
]


def load_ts_set(path: Path) -> set:
    out = set()
    if not path.is_file():
        return out
    for ln in path.read_text(encoding="utf-8").splitlines():
        try:
            out.add(json.loads(ln)["ts"])
        except Exception:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="补账合并至主账本并清除错位文件")
    args = ap.parse_args()

    main_ts = load_ts_set(MAIN_LEDGER)
    drifted = []
    for pat in DRIFT_GLOBS:
        drifted.extend(p for p in REPO.glob(pat) if p.is_file() and p != MAIN_LEDGER)

    if not drifted:
        print("[ledger-drift] ✅ 无分账漂移（主账本唯一且在仓库根）")
        return 0

    print(f"[ledger-drift] ⛔ 发现 {len(drifted)} 处分账：")
    total_new = 0
    for sub in drifted:
        rows = []
        for ln in sub.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append((json.loads(ln)["ts"], ln))
            except Exception:
                rows.append(("", ln))
        new = [(ts, ln) for ts, ln in rows if ts and ts not in main_ts]
        total_new += len(new)
        rel = sub.relative_to(REPO)
        print(f"  - {rel}: {len(rows)} 行（其中 {len(new)} 行主账本缺失）")
        if args.fix:
            if new:
                MAIN_LEDGER.parent.mkdir(parents=True, exist_ok=True)
                with MAIN_LEDGER.open("a", encoding="utf-8") as f:
                    for ts, ln in sorted(new):
                        f.write(ln + "\n")
                print(f"    → 已按 ts 补账 {len(new)} 行至主账本")
            sub.unlink()
            # 清掉空的漂移目录树（.engine/audit 到仓库/技能根为止）
            parent = sub.parent
            while parent != REPO and parent.name in ("audit", ".engine"):
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
            print(f"    → 错位文件已移除")

    if not args.fix:
        print("[ledger-drift] 未加 --fix，仅报告。修复：python tools/check_ledger_drift.py --fix")
        return 1
    print(f"[ledger-drift] ✅ 修复完成（共补账 {total_new} 行，错位文件已清）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
