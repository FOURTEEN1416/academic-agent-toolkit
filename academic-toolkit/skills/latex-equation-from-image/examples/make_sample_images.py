#!/usr/bin/env python3
"""生成本技能验证批的 3 张样例图（两张公式 + 一张表格）。

样例图是**自造夹具**（matplotlib mathtext 渲染已知内容），用于把
"图片→视觉转写→LaTeX→sympy 自检"整条链路走通并留痕，不是真实论文截图。
重跑：python examples/make_sample_images.py（相对本技能目录）。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent

FORMULAS = {
    "eq1_quadratic.png": r"$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$",
    "eq2_gaussian.png": r"$f(x) = \frac{1}{\sigma\sqrt{2\pi}}\; e^{-\frac{(x-\mu)^2}{2\sigma^2}}$",
}

TABLE_ROWS = [
    ["Group", "Mean", "SD", "Delta vs A"],
    ["A", "12.4", "0.8", "-"],
    ["B", "15.1", "1.2", "2.7"],
    ["C", "9.8", "0.5", "-2.6"],
]


def render_formula(name: str, tex: str) -> None:
    fig = plt.figure(figsize=(8, 2.4))
    fig.text(0.5, 0.5, tex, ha="center", va="center", fontsize=30)
    fig.savefig(HERE / name, dpi=150, bbox_inches="tight")
    plt.close(fig)


def render_table() -> None:
    fig, ax = plt.subplots(figsize=(5.2, 2.4))
    ax.axis("off")
    tbl = ax.table(cellText=TABLE_ROWS[1:], colLabels=TABLE_ROWS[0],
                   loc="center", cellLoc="center")
    tbl.scale(1.0, 1.7)
    for j in range(len(TABLE_ROWS[0])):
        tbl[0, j].set_text_props(weight="bold")
    fig.savefig(HERE / "tab1_summary.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    for name, tex in FORMULAS.items():
        render_formula(name, tex)
    render_table()
    print("generated:", ", ".join(list(FORMULAS) + ["tab1_summary.png"]))


if __name__ == "__main__":
    main()
