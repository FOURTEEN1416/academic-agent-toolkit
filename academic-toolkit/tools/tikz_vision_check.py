#!/usr/bin/env python3
"""TikZ 图视觉自检 — 独立审核会话驱动（2026-09-23 第三次用户裁定：换驱动，不拆机制）。

旧实现经 base64 + HTTP 调用外部 vision LLM API（需预填 API key）；
现驱动置换为：由驱动本项目、具备视觉能力的主控 Agent，在**独立审核会话/窗口**中实际读图审核——
本工具只做开发期防死循环计数、确定性检查、审核任务卡生成与证据收集，
不发起任何网络调用、不需要任何 API key。

用法:
  python tools/tikz_vision_check.py <image.png|fig.pdf> [--review]

退出码（与旧实现兼容）:
  0 = 通过（PASS）或 STOP_VISION_LOOP 定稿放行
  1 = 有问题（输出独立审核会话回写的 ISSUE 清单）
  2 = 独立审核会话证据未就绪（任务卡已生成，待独立审核会话审核回写）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import visual_review as hvr  # noqa: E402


def main() -> int:
    return hvr.main_stub(
        "tikz",
        "Usage: python tikz_vision_check.py <image.png|fig.pdf> [--review]",
        checklist=hvr.TIKZ_CHECKLIST,
    )


if __name__ == "__main__":
    sys.exit(main())
