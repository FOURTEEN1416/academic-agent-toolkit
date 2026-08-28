---
name: comp-visual-review
description: Use when a mathematical modeling competition paper or its figures need dedicated visual review for readability, clipping, labels, units, and export quality.
---

# Competition Visual Review

The designated visual-review subagent inspects final PNGs and PDF pages.

## ⛔ 多模态视觉模型铁律（必须遵守）

本角色配置了多模态视觉模型（`agnes-2.5-flash`，支持 image_url 输入）。**必须实际调用视觉工具对每张图进行多模态审查**，禁止只用 PIL/PyMuPDF 等确定性检查后直接判 pass。

1. 先运行确定性图像检查（PIL 解码/尺寸/DPI、PyMuPDF 页数与嵌入图）。
2. **每张 PNG 必须调用 `tools/data_fig_vision_check.py`（数据图）或 `tools/tikz_vision_check.py`（TikZ/流程/架构图）或 `tools/drawio_vision_check.py`（draw.io 图）**，用配置的视觉模型检查：坐标轴名称与单位、刻度可读性、图例、颜色区分、截断、重叠、误导性比例、题注对应、文字溢出、配色对比度。
3. 记录每次视觉 API 调用的输出（PASS / ISSUE N: ...）作为 `VISUAL_REVIEW.md` 的证据。
4. 检查 PDF 页面布局与图题对应关系（确定性检查辅助）。

## ⛔⛔ --review 审核模式（审核/终审必须使用，防伪造证据）

视觉工具带开发防死循环计数（STOP_VISION_LOOP：per-key 同图 2 轮上限 + 全局 图数×2+2 上限），
**开发迭代**阶段该计数防"改坐标→重编→重调"无限震荡是合理的；但**审核/终审**阶段必须真实调用视觉 API——
开发阶段的迭代额度耗尽后，审核不能被迫"定稿/绕过工具/直接看图判 pass"（那等于伪造审核证据）。

⛔ **审核/终审调用视觉工具必须加 `--review` 参数**：

```bash
python tools/data_fig_vision_check.py figures/fig_q1.png --review     # 数据图
python tools/tikz_vision_check.py figures/tikz_arch.pdf --review       # TikZ 图
```

- `--review` 模式：不累计开发计数（不污染 dev 额度）、不受 per-key/全局上限拦截 → 审核永远能真实调用视觉 API
- 审核报告（VISUAL_REVIEW.md）必须记录每张图**实际调用视觉 API 的证据输出**（PASS / ISSUE N: ...）
- ⛔ 禁止：计数器被拦截后"直接看图片凭感觉判 pass"；发现 STOP_VISION_LOOP 提示时改用 --review 重试，而不是绕过工具

## 输出契约（机器可读，硬性要求）

写 `VISUAL_REVIEW.md` 和 `VISUAL_REVIEW_VERDICT.json`，**verdict 必须包含 `status` 字段**：

```json
{"findings":[{"id":"V1","severity":"fatal|major|minor","where":"文件/页/图","evidence":"...","fix":"..."}],
 "fatal_count":0,
 "status":"pass|fail|unavailable"}
```

- `status=pass`：仅当所有确定性检查通过 **且** 视觉模型 API 调用成功且未发现 fatal/major 问题。
- `status=fail`：发现 fatal/major 视觉问题。
- `status=unavailable`：视觉模型 API 不可用（未配置 key/调用失败/超时）。**此时禁止判 pass**——在报告中明确列出未验证项，`VISUAL_REVIEW.md` 中标注"视觉复核未验证"，不得伪造通过。
- `fatal_count` 必须为整数；任何 fatal 都阻止后续 final-review 放行。

## 输入

- `figures/*.png`（全部数据图）
- `paper/main.pdf`（页面布局、嵌入图、图题）
- `paper/build_paper.py` 或 `paper/main.tex`（图题/caption 核对）
- 格式规范（`FORMAT_SPEC_2025.txt` 等，若存在）

## 方法

1. PIL/PyMuPDF 确定性检查（解码、尺寸、DPI、页数、嵌入图、图题命中）。
2. 逐图调用多模态视觉工具，记录每张图的 API 输出。
3. 汇总 findings，按严重性分级，写 `VISUAL_REVIEW.md`。
4. 生成 `VISUAL_REVIEW_VERDICT.json`（含 `status` 字段）。
5. 若 API 不可用：status=`unavailable`，并把未验证项全部列出，绝不含糊通过。
