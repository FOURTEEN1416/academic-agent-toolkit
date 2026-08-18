#!/usr/bin/env python3
"""Run the maintained vision checker with a data-figure-specific review rubric."""
from __future__ import annotations

import tikz_vision_check as vision


vision.PROMPT = (
    "这是一张数学建模论文中的数据图。检查坐标轴名称和单位、刻度可读性、"
    "图例、颜色区分、截断、重叠、误导性比例和题注对应关系。"
    "全部通过时只回答 PASS；否则按 ISSUE N: [位置] [问题] 输出。"
)


if __name__ == "__main__":
    vision.main()
