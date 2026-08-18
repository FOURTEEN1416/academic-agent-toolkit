#!/usr/bin/env python3
"""图表质量自检脚本 — Claude 每生成一张图后运行此脚本检查代码质量。

用法：python _utils/figure_check.py figures/gen_fig_xxx.py
输出：PASS 或 FAIL + 具体问题列表
"""
import sys
import re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def check_figure_script(filepath: str) -> list:
    """检查单个图表脚本的质量问题，返回问题列表。"""
    issues = []
    path = Path(filepath)
    if not path.exists():
        return [f"文件不存在: {filepath}"]

    code = path.read_text(encoding="utf-8", errors="replace")
    lines = code.split("\n")

    # 1. 硬编码 hex 色值
    hex_pattern = re.compile(r"['\"]#[0-9A-Fa-f]{6}['\"]")
    allowed_hex_contexts = ["LinearSegmentedColormap", "from_list", "PALETTE", "COLORS", "_lighten"]
    for i, line in enumerate(lines, 1):
        if hex_pattern.search(line):
            if not any(ctx in line for ctx in allowed_hex_contexts):
                issues.append(f"L{i}: 硬编码色值 — 应使用 PALETTE[n]/COLORS['xxx']/_lighten()")

    # 2. set_title / plt.title
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "set_title(" in stripped or "plt.title(" in stripped:
            issues.append(f"L{i}: 使用了 set_title/plt.title — 标题应由 LaTeX caption 管理")

    # 3. 缺少 setup_style()
    if "setup_style()" not in code and "setup_style(" not in code:
        issues.append("缺少 setup_style() 调用 — 图表风格未初始化")

    # 4. save_fig 格式
    save_calls = re.findall(r"save_fig\(([^)]+)\)", code)
    for call in save_calls:
        args = [a.strip() for a in call.split(",")]
        if len(args) < 2:
            issues.append(f"save_fig 只有 {len(args)} 个参数 — 应为 save_fig(fig, 'path')")

    # 5. 缺少 spines 隐藏（热力图/3D/极坐标除外）
    is_heatmap = "heatmap" in code.lower() or "imshow" in code.lower() or "sns.heatmap" in code
    is_3d = "projection='3d'" in code or "Axes3D" in code
    is_polar = "polar=True" in code or "subplot_kw=dict(polar" in code
    if not is_heatmap and not is_3d and not is_polar:
        if "spines['top'].set_visible(False)" not in code and "spines['top']" not in code:
            issues.append("缺少 spines['top'].set_visible(False)")
        if "spines['right'].set_visible(False)" not in code and "spines['right']" not in code:
            issues.append("缺少 spines['right'].set_visible(False)")

    # 6. RdYlGn 交通灯色图
    if "RdYlGn" in code:
        issues.append("使用了 RdYlGn 交通灯色图 — 应改为 coolwarm/YlOrRd")

    # 7. gridspec 用于热力图+树状图（应该用 add_axes）
    if ("dendrogram" in code or "linkage" in code) and "GridSpec" in code:
        issues.append("热力图+树状图使用了 GridSpec — 应使用 fig.add_axes() 确保对齐")

    # 8. 密集标签未用 smart_labels（区分 2D / 3D：3D 用不了 smart_labels，须手动防遮挡）
    text_calls = re.findall(r"ax\w*\.text\(", code)
    if len(text_calls) > 5 and "smart_labels" not in code:
        if re.search(r"projection=['\"]3d['\"]|Axes3D|plot_surface|scatter3|\.plot3D", code):
            issues.append(f"3D 图有 {len(text_calls)} 个 ax.text() — 3D 用不了 smart_labels，须手动防遮挡：短代号+图例 / xytext 异向偏移+引线 / 只标图例，别让标注糊成一团")
        else:
            issues.append(f"有 {len(text_calls)} 个 ax.text() 调用但未使用 smart_labels() — 标签可能重叠")

    # 9. 中文内容但没有 setup_style
    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", code))
    if has_chinese and "setup_style" not in code:
        issues.append("包含中文但未调用 setup_style() — 中文可能显示为方块")

    # 9b. y label 超长检测 — 防止 y 轴标签溢出 figure 左边界
    # 抓 set_yticklabels(...) 的内容，看是否有超长元素
    yticklabels_calls = re.findall(r"set_yticklabels\(\s*([^,)]+)", code)
    for ytl_arg in yticklabels_calls:
        # 提取字符串列表中的元素
        items = re.findall(r"['\"]([^'\"]{15,})['\"]", ytl_arg)
        if items:
            max_len = max(len(s) for s in items)
            if max_len > 25:
                issues.append(
                    f"y label 元素含超长文本（最长 {max_len} 字符）— 容易溢出 figure 边界，"
                    f"建议 1) 缩写到 ≤20 字符 / 2) 调用 auto_truncate_yticklabels(ax, max_chars=18) / 3) rotation=15"
                )
                break  # 一个图只报一次

    # 9c. 横向条形图 / SHAP / 聚类热力图 等 y 标签依赖型场景，建议预留 figsize 宽度
    is_yaxis_heavy = ('barh(' in code or 'cluster_heatmap' in code.lower()
                     or 'dendrogram' in code or 'shap' in code.lower())
    if is_yaxis_heavy and yticklabels_calls:
        # 检查 figsize 第一维（宽度）是否够 ≥ 8
        figsize_match = re.search(r"figsize\s*=\s*\(\s*([\d.]+)", code)
        if figsize_match:
            w = float(figsize_match.group(1))
            if w < 7:
                issues.append(
                    f"y 标签依赖型图（横向条形/聚类热力图/SHAP）figsize 宽度 {w}<7，"
                    f"长 y 标签易被压缩；建议 figsize=(8-10, ...) 给 y 轴留宽度"
                )

    # 9d. figsize 高度过大 / 比例失衡检测 — 防"axes 在顶部 + 下方大片白边"
    # 常见错误：figsize=(10, 16) 但只画了 1 个 panel → 画布 80% 白边
    figsize_match_full = re.search(r"figsize\s*=\s*\(\s*([\d.]+)\s*,\s*([\d.]+)", code)
    if figsize_match_full:
        w = float(figsize_match_full.group(1))
        h = float(figsize_match_full.group(2))
        # 推断 subplot 行列
        subplots_match = re.search(r"subplots\(\s*(\d+)\s*,\s*(\d+)", code)
        n_rows = int(subplots_match.group(1)) if subplots_match else 1
        n_cols = int(subplots_match.group(2)) if subplots_match else 1
        # 期望 height：每行约 3-4 英寸
        max_reasonable_h = max(4.0, n_rows * 4.5)
        if h > max_reasonable_h and not (is_3d or 'GridSpec' in code):
            issues.append(
                f"figsize 高度 {h} 偏大（{n_rows}×{n_cols} 子图建议 ≤{max_reasonable_h:.0f}）— "
                f"axes 会被压到顶部，下方大片白边。建议 figsize=({w}, {max_reasonable_h:.1f})"
            )
        # 比例失衡：宽高比 < 0.4 或 > 4.0
        if h > 0 and w > 0:
            ratio = w / h
            if ratio < 0.4 and not (is_3d or n_rows >= 4):
                issues.append(
                    f"figsize 宽高比 {ratio:.2f} 过小（图过细长）— "
                    f"竖向数据建议 figsize 比例 0.6-1.5"
                )

    # 9e. ★ ax.text(transAxes, y<0 or y>1) 反模式 — 严重 bug 触发器
    # 这种 axes 外标注配合 science 样式默认 savefig.bbox='tight' → PDF mediabox 爆炸
    # 实测产出 1496×23966 px 超长条 PNG（中间一大片全白）
    # 正则注意：第三个参数 "(a) title" 含 `)`，所以用 .*? 非贪婪匹配到 transform=
    outside_transaxes = re.findall(
        r"\.text\([^,]+,\s*(-?[\d.]+).*?transform\s*=\s*\w+\.transAxes",
        code
    )
    for y_str in outside_transaxes:
        try:
            y = float(y_str)
            if y > 1.0 or y < 0.0:
                issues.append(
                    f"ax.text(transAxes, y={y}) 是 axes 外标注 — 配合 SciencePlots 默认 "
                    f"savefig.bbox='tight' 会让 PDF mediabox 异常拉长（实测过 1496×23966 px）。"
                    f"改用 fig.text(x, 0.015, ...) figure 坐标钉在画布底部，或用 ax.set_title(loc='left', pad=3)"
                )
                break  # 一个图只报一次
        except ValueError:
            pass

    # 9f. 显式 bbox_inches='tight' + 含 transAxes 反模式时双重警告
    if "bbox_inches='tight'" in code and outside_transaxes:
        # 检查是不是真有 y 越界的
        has_bad = any(
            (float(y) > 1.0 or float(y) < 0.0)
            for y in outside_transaxes if y.replace('-', '').replace('.', '').isdigit()
        )
        if has_bad:
            issues.append(
                "显式 bbox_inches='tight' + ax.text(transAxes, y 在 [0,1] 外) — 双重触发 mediabox 爆炸。"
                "把 bbox_inches 换 None，或删掉 transAxes 越界标注"
            )

    # 10. 高级样式检测 — 检查是否使用了配方级别的视觉增强
    style_score = 0
    style_missing = []

    # 是否有渐变填充 (fill_between / fill / alpha 填充)
    if "fill_between" in code or "fill(" in code or "axvspan" in code or "axhspan" in code:
        style_score += 1
    else:
        if "plot(" in code or "bar(" in code:
            style_missing.append("缺少渐变/半透明填充 — 配方用 fill_between/axvspan 增加层次感")

    # 是否有标注框 (bbox)
    if "bbox=dict(" in code or "bbox=" in code:
        style_score += 1
    else:
        if "annotate" in code or "ax.text(" in code:
            style_missing.append("标注文字缺少 bbox 背景框 — 配方用 bbox=dict(boxstyle='round,pad=0.3', facecolor='white', ...)")

    # 是否有 edgecolor='white' (柱子/散点的白色边框，增加层次)
    if "edgecolor='white'" in code or "edgecolors='white'" in code:
        style_score += 1
    else:
        if "bar(" in code or "scatter(" in code:
            style_missing.append("柱子/散点缺少 edgecolor='white' — 白色边框让元素更清晰")

    # 是否有 grid 设置
    if "grid(" in code or "grid=True" in code:
        style_score += 1
    else:
        if not is_heatmap and not is_polar:
            style_missing.append("缺少网格线 — 配方用 ax.grid(axis='y', alpha=0.15, linestyle='--')")

    # 是否有 tight_layout
    if "tight_layout" in code or "bbox_inches='tight'" in code:
        style_score += 1
    else:
        style_missing.append("缺少 fig.tight_layout() — 可能导致标签被裁切")

    # 是否有 zorder 控制图层
    if "zorder" in code:
        style_score += 1

    # 是否用了 _lighten() 做浅色变体
    if "_lighten(" in code:
        style_score += 1

    # 是否有 markeredgecolor='white' (散点/折线标记的白色边框)
    if "markeredgecolor='white'" in code:
        style_score += 1

    # 11. 组合图/多层叠加检测 — 高级图表应有多个视觉层
    layers = 0
    layer_details = []
    if "contour" in code or "contourf" in code:
        layers += 1; layer_details.append("KDE等高线")
    if "scatter(" in code:
        layers += 1; layer_details.append("散点")
    if "hexbin(" in code:
        layers += 1; layer_details.append("六边形分箱")
    if "fill_between" in code or "axvspan" in code:
        layers += 1; layer_details.append("区域填充")
    if "axhline" in code or "axvline" in code:
        layers += 1; layer_details.append("参考线")
    if "annotate(" in code:
        layers += 1; layer_details.append("箭头标注")
    if "colorbar" in code or "colorbar(" in code:
        layers += 1; layer_details.append("颜色条")
    if "legend(" in code or "auto_legend" in code:
        layers += 1; layer_details.append("图例")

    # 12. 边际分布检测（组合图标志）
    has_marginal = ("add_subplot(gs[0" in code or "ax_top" in code or
                    "ax_right" in code or "add_axes" in code)
    if has_marginal:
        layers += 1; layer_details.append("边际分布/多面板")

    # 13. 颜色映射检测（时间/类别维度编码）
    has_cmap = "cmap=" in code and ("scatter" in code or "hexbin" in code)
    if has_cmap:
        layers += 1; layer_details.append("颜色映射维度")

    # 简单图表（只有 1-2 层）给警告
    is_simple_type = ("barh(" in code and "scatter" not in code and
                      "contour" not in code)
    if layers < 2 and not is_simple_type and not is_heatmap and not is_3d:
        style_missing.append(
            f"视觉层次偏少（{layers} 层: {', '.join(layer_details) if layer_details else '无'}）"
            f"— 高级配方通常有 3+ 层叠加（如散点+等高线+填充+标注）"
        )

    # 评分：8 项满分，低于 3 分警告
    if style_score < 3 and not is_3d:
        issues.append(f"视觉质量偏低（得分 {style_score}/8）— 缺少配方级别的视觉增强:")
        for m in style_missing[:3]:  # 最多报 3 条
            issues.append(f"  → {m}")

    return issues


def main():
    if len(sys.argv) < 2:
        print("用法: python figure_check.py <script.py> [script2.py ...]")
        sys.exit(1)

    all_pass = True
    for filepath in sys.argv[1:]:
        issues = check_figure_script(filepath)
        name = Path(filepath).name
        if issues:
            print(f"FAIL: {name}")
            for issue in issues:
                print(f"  ✗ {issue}")
            all_pass = False
        else:
            print(f"PASS: {name}")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
