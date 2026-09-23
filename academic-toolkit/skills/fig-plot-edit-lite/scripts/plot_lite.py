# -*- coding: utf-8 -*-
"""fig-plot-edit-lite：fig-plot-edit（Origin 版）方法论的无 Origin 渲染路线（matplotlib 引擎）。

方法论真源：academic-toolkit/skills/fig-plot-edit/SKILL.md；配色真源复用其官方 palette-catalog.json。
  1) 逐列角色分类：主证据/可见辅助(误差棒)/保留不画/不确定——不确定列拒画，列为待确认问题；
  2) 科学确认哈希冻结：确认书携带源 sha256 + 列映射，render 强校验，任一变化即拒绝；
  3) 配色取自 fig-plot-edit 官方目录，校验系列数 <= max_qualitative_categories 且图型在推荐列表；
  4) 出版图形合同：白底、Arial(中文回退微软雅黑)、无图内标题、单栏 9cm/双栏 19cm；
  5) 源数据不可变：渲染前后 sha256 一致才允许宣称完成；
  6) 完成口径：PNG(300dpi)+PDF+SVG+verify-report 全绿才算 success（lite 等价口径，
     非 Origin OPJU，对外表述见 SKILL.md §三）。

用法（两段式，对应 fig-plot-edit 的 understand→confirm→render 门禁）：
  python plot_lite.py propose <csv>                     # 列角色提案（Ask first 检查点）
  python plot_lite.py render <csv> --confirm c.json     # 校验确认书与哈希后渲染+验证
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import scienceplots  # noqa: F401  激活 'science' 样式族

SKILLS_DIR = Path(__file__).resolve().parents[2]
PALETTE_CATALOG = SKILLS_DIR / "fig-plot-edit" / "assets" / "palettes" / "palette-catalog.json"
ERR_SUFFIXES = ("_SD", "_SEM", "_SE", "_std", "_sem")  # 可见辅助列后缀 → 误差棒
SINGLE_COL_CM, DOUBLE_COL_CM = 9.0, 19.0  # 期刊单/双栏物理宽度


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_palettes() -> dict:
    return json.loads(PALETTE_CATALOG.read_text(encoding="utf-8"))["palettes"]


def classify_columns(df: pd.DataFrame) -> dict:
    """fig-plot-edit 纪律：每列必须归入唯一角色；数值列无明确语义时= uncertain（问题，不是新曲线）。"""
    cols = list(df.columns)
    roles, used = {}, set()
    if len(cols) > 1 and pd.api.types.is_numeric_dtype(df[cols[0]]):
        roles[cols[0]] = "x_axis"
        used.add(cols[0])
    for c in cols:
        if c in used:
            continue
        base = next((c[: -len(s)] for s in ERR_SUFFIXES if c.endswith(s)), None)
        if base and base in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            roles[c] = f"error_of:{base}"  # 可见辅助：只作误差棒，不画线
        elif pd.api.types.is_numeric_dtype(df[c]):
            roles[c] = "uncertain"  # fig-plot-edit：未知数值列是问题，不是自动曲线
        else:
            roles[c] = "reserved"  # 非数值列默认保留不画
    return roles


def propose(csv: Path, intent: str) -> dict:
    df = pd.read_csv(csv)
    roles = classify_columns(df)
    proposal = {
        "source": str(csv.resolve()), "source_sha256": sha256_file(csv),
        "intent": intent, "shape": list(df.shape),
        "column_roles": roles,
        "open_questions": [c for c, r in roles.items() if r == "uncertain"],
        "note": "uncertain 列在未获用户逐列确认前拒绝渲染（fig-plot-edit 纪律）",
    }
    print(json.dumps(proposal, ensure_ascii=False, indent=2))
    return proposal


def check_palette(pal: dict, chart: str, n_series: int) -> list:
    if chart not in pal["recommended_charts"]:
        raise SystemExit(f"[reject] 图型 {chart} 不在配色 {pal['palette_id']} 推荐列表 {pal['recommended_charts']}")
    if n_series > pal["max_qualitative_categories"]:
        raise SystemExit(f"[reject] 系列 {n_series} > 配色上限 {pal['max_qualitative_categories']}（拒绝彩虹化）")
    return pal["colors"][:n_series]


def validate_confirm(csv: Path, confirm: dict) -> tuple:
    """哈希冻结校验（fig-plot-edit 第 3 步）：源内容不变、列集合不变、x/误差棒角色不变；
    propose 阶段的 uncertain 列必须被用户逐列确认为 main_evidence 或 reserved，禁止仍为 uncertain。"""
    cur_sha = sha256_file(csv)
    if confirm.get("source_sha256") != cur_sha:
        raise SystemExit(f"[reject] 源文件已变化，确认失效：{str(confirm.get('source_sha256'))[:12]} → {cur_sha[:12]}")
    if "user_confirmed" not in confirm:
        raise SystemExit("[reject] 确认书缺 user_confirmed 字段（Ask-first 门禁）")
    df = pd.read_csv(csv)
    fresh = classify_columns(df)
    mapping = confirm["column_roles"]
    if set(mapping) != set(fresh):
        raise SystemExit("[reject] 列集合与当前文件不一致，确认失效，需重新 propose→confirm")
    for c, r in fresh.items():
        if r in ("x_axis", "reserved") or r.startswith("error_of:"):
            if mapping[c] != r:
                raise SystemExit(f"[reject] 列「{c}」角色被篡改：结构角色不可确认改写")
        elif r == "uncertain" and mapping[c] == "uncertain":
            raise SystemExit(f"[reject] 列「{c}」仍为未确认状态，不渲染（不确定≠自动曲线）")
        elif mapping[c] not in ("main_evidence", "reserved"):
            raise SystemExit(f"[reject] 列「{c}」确认角色 {mapping[c]} 非法")
    return df, cur_sha, mapping


def render(csv: Path, confirm: dict) -> dict:
    df, cur_sha, mapping = validate_confirm(csv, confirm)
    plot_cols = [c for c, r in mapping.items() if r == "main_evidence"]
    if not plot_cols:
        raise SystemExit("[reject] 无主证据列，无图可画")
    pal = next(p for p in load_palettes() if p["palette_id"] == confirm["palette_id"])
    colors = check_palette(pal, confirm["chart"], len(plot_cols))
    xcol = next(c for c, r in mapping.items() if r == "x_axis")

    width_cm = SINGLE_COL_CM if len(plot_cols) <= 2 else DOUBLE_COL_CM
    plt.style.use(["science", "no-latex"])
    plt.rcParams.update({
        "font.family": ["Arial", "Microsoft YaHei"],  # 直接给字体链才有逐字回退（Arial 缺 CJK 字形时落雅黑）
        "font.sans-serif": ["Arial", "Microsoft YaHei"],
        "axes.unicode_minus": False,
        "figure.dpi": 300,
    })
    fig, ax = plt.subplots(figsize=(width_cm / 2.54, width_cm / 2.54 * 0.75))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")

    for col, c in zip(plot_cols, colors):
        yerr = None
        ecol = next((e for e, r in mapping.items() if r == f"error_of:{col}"), None)
        if ecol:
            yerr = df[ecol].to_numpy(dtype=float)
        ax.errorbar(df[xcol], df[col], yerr=yerr, color=c, marker="o", ms=3.5,
                    lw=1.4, capsize=2, label=f"{col}" + (f" (±{ecol.rsplit('_', 1)[1]})" if ecol else ""))

    ax.set_xlabel(xcol); ax.set_ylabel(confirm.get("y_label", "数值"))
    ax.legend(frameon=False, loc="best")  # 合同：图例默认无框
    fig.tight_layout()

    out_dir = csv.parent / f"{csv.stem}_lite_{confirm['rendered_at']}"
    out_dir.mkdir(exist_ok=True)
    outputs = {}
    for ext, kw in {"png": {"dpi": 300}, "pdf": {}, "svg": {}}.items():
        p = out_dir / f"{csv.stem}.{ext}"
        fig.savefig(p, facecolor="white", **kw)
        outputs[ext] = str(p)
    plt.close(fig)

    # ── 校验（fig-plot-edit 第 8 步的 lite 等价）：产物齐 + 源数据不变 + 白底 ──
    from PIL import Image
    checks = {
        "outputs_complete": all(Path(v).stat().st_size > 0 for v in outputs.values()),
        "source_unchanged": sha256_file(csv) == cur_sha,
        "white_bg": Image.open(outputs["png"]).convert("RGB").getpixel((2, 2)) == (255, 255, 255),
        "palette_ok": len(colors) == len(plot_cols),
    }
    report = {
        "success": all(checks.values()), "checks": checks,
        "outputs": outputs, "palette_id": pal["palette_id"],
        "plan_hash": hashlib.sha256(json.dumps(confirm, sort_keys=True, ensure_ascii=False)
                                    .encode("utf-8")).hexdigest()[:16],
    }
    (out_dir / "verify-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["success"]:
        sys.exit(2)
    return report


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("propose"); p1.add_argument("csv"); p1.add_argument("--intent", default="")
    p2 = sub.add_parser("render"); p2.add_argument("csv"); p2.add_argument("--confirm", required=True)
    a = ap.parse_args()
    csv = Path(a.csv)
    if a.cmd == "propose":
        propose(csv, a.intent)
    else:
        render(csv, json.loads(Path(a.confirm).read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
