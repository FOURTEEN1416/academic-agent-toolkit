#!/usr/bin/env python3
"""Run the maintained vision checker with a draw.io-specific review rubric."""
from __future__ import annotations

import tikz_vision_check as vision


vision.PROMPT = (
    "这是一张数学建模论文中的 draw.io 流程图或架构图。检查文字截断、重叠、"
    "箭头方向、连线穿过节点、图例/题注缺失、布局空洞和导出清晰度。"
    "全部通过时只回答 PASS；否则按 ISSUE N: [位置] [问题] 输出。"
)


if __name__ == "__main__":
    vision.main()
