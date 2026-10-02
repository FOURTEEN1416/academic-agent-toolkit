#!/usr/bin/env python3
"""Summarize figures/*_results.json to a KB-level overview (extracted from SKILL.md).

Paper prose only needs scalar values (fitness / optimum / metrics / solve
time).  The raw result files often carry full-precision arrays of millions of
lines; reading them whole blows up the model context.  This tool prints scalars
verbatim (zero precision loss) and compresses big lists to "length + range +
first 3 samples", so the paper can copy exact numbers without ever `cat`-ing
the raw files.

Usage: python summarize_results.py [glob-or-dir]
  default: figures/*_results.json
Exit codes: 0 = printed, 2 = nothing matched.
"""
from __future__ import annotations

import glob
import json
import os
import sys


def summarize(v, depth=0):
    if isinstance(v, list):
        n = len(v)
        nums = [x for x in v if isinstance(x, (int, float))]
        if nums:
            return f"list[{n}] range=[{min(nums):.4g},{max(nums):.4g}] sample={v[:3]}"
        if v and isinstance(v[0], (list, dict)):
            first = len(v[0]) if hasattr(v[0], "__len__") else "?"
            return f"list[{n}] of {type(v[0]).__name__}, first_shape={first}"
        return f"list[{n}] sample={str(v[:3])[:80]}"
    if isinstance(v, dict) and depth < 2:
        inner = ", ".join(f"{k}: {summarize(x, depth + 1)}" for k, x in list(v.items())[:6])
        return "dict{" + inner + "}"
    return f"{type(v).__name__}={str(v)[:60]}"


def main() -> int:
    pattern = sys.argv[1] if len(sys.argv) > 1 else "figures/*_results.json"
    if os.path.isdir(pattern):
        pattern = os.path.join(pattern, "*_results.json")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"[SKIP] 无匹配结果文件: {pattern}")
        return 2
    for f in files:
        size = os.path.getsize(f)
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"=== {os.path.basename(f)} ({size // 1024}KB) 读取失败: {exc} ===")
            continue
        print(f"\n=== {os.path.basename(f)} ({size // 1024}KB) ===")
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"  {k}: {summarize(v)}")
        else:
            print(f"  {summarize(data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
