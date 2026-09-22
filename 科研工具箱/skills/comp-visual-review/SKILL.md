---
name: comp-visual-review
description: Use when a mathematical modeling competition paper or its figures need dedicated visual review for readability, clipping, labels, units, and export quality.
---

# Competition Visual Review

The designated visual-review subagent inspects final PNGs and PDF pages.

## ⛔ 多模态视觉模型铁律（必须遵守）

本角色须配置**具备视觉能力的多模态模型**（支持 image_url 输入；仓库不预设具体型号——比赛时在 `engine/modex-core/contest_models.json` 或宿主 agent 配置中填写，示例：任一具备视觉能力的 GLM 系列模型）。**必须实际调用视觉工具对每张图进行多模态审查**，禁止只用 PIL/PyMuPDF 等确定性检查后直接判 pass。

1. 先运行确定性图像检查（PIL 解码/尺寸/DPI、PyMuPDF 页数与嵌入图）。
2. **每张 PNG 必须调用 `tools/data_fig_vision_check.py`（数据图）或 `tools/tikz_vision_check.py`（TikZ/流程/架构图）或 `tools/drawio_vision_check.py`（draw.io 图）**，用配置的视觉模型检查：坐标轴名称与单位、刻度可读性、图例、颜色区分、截断、重叠、误导性比例、题注对应、文字溢出、配色对比度、**黑白打印下仍可分辨（仅靠色相区分的系列必须有线型/hatch 冗余编码——打印安全三件套）**、**色盲模拟（红绿色弱）下各系列可区分**。
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
 "status":"pass|fail|manual_review|unavailable"}
```

- `status=pass`：仅当所有确定性检查通过 **且** 视觉模型 API 调用成功且未发现 fatal/major 问题。
- `status=fail`：发现 fatal/major 视觉问题。
- `status=manual_review`：视觉模型 API 不可用时的**受控人工降级**（见下方降级预案），必须伴随合规的 `VISUAL_REVIEW_MANUAL_CHECK.md`，否则质量闸硬拦。
- `status=unavailable`：视觉模型 API 不可用且**未完成人工复核**。**此时禁止判 pass**——在报告中明确列出未验证项，`VISUAL_REVIEW.md` 中标注"视觉复核未验证"，不得伪造通过。注意：`unavailable` 且无人工复核记录时，review 闸一律不放行（静默降级被拦截是设计行为）。
- `fatal_count` 必须为整数；任何 fatal 都阻止后续 final-review 放行。

## ⛔ 视觉 API 不可用降级预案（A7-M5：禁止静默跳过，也禁止第 11 步永久卡死）

视觉探针失败（`data_fig_vision_check.py` / `tikz_vision_check.py` / `drawio_vision_check.py`
exit 2 且**已排除相对路径问题**——先用绝对路径重试一次）时，按以下顺序处置：

1. **先确认是真不可用**：用绝对路径重试（`python tools/data_fig_vision_check.py <工作区>/figures/fig_q1.png --review`）；
   仍失败（无 key / 调用失败 / 超时）才进入降级。
2. **人工按检查单逐项目检**：用户本人对每张图逐项核对视觉检查单
   （坐标轴名称与单位、刻度可读性、图例、颜色区分与色盲可辨、黑白打印可辨、截断、重叠、
   误导性比例、题注对应、文字溢出、对比度）。
3. **写 `VISUAL_REVIEW_MANUAL_CHECK.md`**（格式硬性要求，缺一即被闸拦截）：

   ```markdown
   # 视觉人工复核记录（视觉 API 不可用降级）
   approved_by: <操作者真实姓名>     ← 必填非空，必须是人类操作者本人署名，禁止填 agent/AI/模型名

   ## 逐项检查
   - [x] 图1 fig_q1：坐标轴名称与单位可读
   - [x] 图1 fig_q1：图例完整、不遮挡曲线
   - [x] 图2 fig_q2：色盲（红绿色弱）模拟下系列可区分
   - [x] 图2 fig_q2：黑白打印仅靠色相区分的系列有线型冗余
   - [x] 图3 tikz_arch：无文字截断/重叠
   ```

   `approved_by` 合规 + `- [x]` 逐项记录 **≥5 条**（每张图每个检查维度一行），质量闸才认。
4. **verdict 写 `status=manual_review`**（不是 unavailable、更不是 pass），保留未验证项说明于 `VISUAL_REVIEW.md`。
5. **重跑 complete**：review 闸校验人工复核文件合规后放行，并在结果中注记 manual_review。

⛔ 红线（引擎强制实现，非纸面条款）：以下任一情形都被 review 闸硬拦——
1. 没有人工复核文件就写 `manual_review`；
2. `approved_by` 非空但**命中 agent 自指词**：`agent`、`ai`、`bot`、`llm`、`auto`、
   `机器人`、`智能体`、`自动`，以及模型/厂商名 `glm`、`agnes`、`gpt`、`chatgpt`、`openai`、
   `anthropic`、`claude`、`gemini`、`deepseek`、`sensenova`、`sense`、`qwen`、`kimi`、
   `doubao`、`ernie`、`hunyuan`、`llama`、`mistral`、`copilot`、`zhipu`、`opencode`、`zcode`
   （英文词按 ASCII 字母边界匹配，不区分大小写；中文词按子串匹配；`subagent`、
   `multi-agent`、`multiagent` 按子串匹配硬拦——边界规则会放过 "sub**agent**" 这类
   紧邻字母写法，2026-09-22 补漏。命中的典型写法：
   `approved_by: agent`、`approved_by: AI审稿机器人`、`approved_by: GLM-4`——全部硬拦）；
3. 逐项记录凑数不足 5 条。

正确写法只有一个：`approved_by: <操作者真实姓名>`（人类本人署名，如 `默默`、`operator-1`；
不含上述任何自指词）。伪造用户签名视同伪造审核证据。

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
5. 若 API 不可用：按"视觉 API 不可用降级预案"走人工复核（status=`manual_review` +
   `VISUAL_REVIEW_MANUAL_CHECK.md`）；无法完成人工复核时 status=`unavailable`，
   并把未验证项全部列出，绝不含糊通过。

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 由只读子智能体执行且实际调用视觉审查通道
- [ ] 发现项按分级列出，含图号与具体位置
- [ ] 审查模式为 review（不受开发期迭代计数限制）
- [ ] 不可用时如实记录 unavailable，绝不伪造通过

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "图我看过了没问题" | 未经视觉通道的「看过」不构成证据；本项目曾因防死循环而被迫跳过真实审查。 |
| "小瑕疵不值得记" | 图表硬伤正是靠逐项记录才被发现的（本项目实测 6 major）。 |
| "工具报错就跳过审查" | 工具不可用要如实记录 unavailable，不得折算为通过。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。
