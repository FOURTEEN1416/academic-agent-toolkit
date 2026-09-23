#!/usr/bin/env python3
"""数据图视觉自检 — 宿主独立窗口驱动（2026-09-23 第三次用户裁定：换驱动，不拆机制）。

旧实现为 pyc 闭源件经 wrapper 调用外部 vision LLM API（需预填 API key）；
现驱动置换为：项目驱动宿主自身具备视觉能力的 LLM 在**独立窗口**实际读图审核——
本工具只做开发期防死循环计数、确定性检查、审核任务卡生成与证据收集，
不发起任何网络调用、不需要任何 API key。

用法:
  python tools/data_fig_vision_check.py <fig.png|fig.pdf> [--review]

退出码（与旧实现兼容）:
  0 = 通过（PASS）或 STOP_VISION_LOOP 定稿放行
  1 = 有问题（输出独立窗口回写的 ISSUE 清单）
  2 = 独立窗口证据未就绪（任务卡已生成，待宿主独立窗口审核回写）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import host_visual_review as hvr  # noqa: E402


def main() -> int:
    return hvr.main_stub(
        "data-fig",
        "Usage: python data_fig_vision_check.py <fig.png|fig.pdf> [--review]",
    )


if __name__ == "__main__":
    sys.exit(main())
