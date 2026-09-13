---
name: comp-cumcm-disclosure
description: >-
  CUMCM 2026 AI 工具使用申报双件套的入口与门禁。当需要生成/校验《AI工具使用详情.pdf》与论文正文
  AI 使用声明、或需要确认"声明措辞与详情用途一致"时使用。本技能不重写生成器，而是把既有确定性脚本
  skills/_utils/build_ai_disclosure.py（+ 唯一真源 skills/_utils/ai_disclosure_rules.md）暴露为可发现的
  技能契约，并固化两道硬闸：⛔不得由语言模型自由编写详情、⛔正文与详情必须口径一致。
  触发词：AI 申报、AI工具使用详情、AI 使用声明、disclosure、人工智能工具使用规定、申报四节、
  build_ai_disclosure、--check-only。
---

# CUMCM AI 工具使用申报（comp-cumcm-disclosure）

**定位**：本条是**入口与门禁**，不是生成器。生成逻辑与全部细则以既有真源为准：

| 真源 | 路径 | 作用 |
|---|---|---|
| 执行脚本 | `skills/_utils/build_ai_disclosure.py`（镜像 `skills/shared-scripts/build_ai_disclosure.py`） | 确定性生成声明 + 详情 PDF + `--check-only` 反查 |
| 规则全文 | `skills/_utils/ai_disclosure_rules.md` | 八条不可变边界 + 执行方式 + 正文声明格式（**唯一真源，本技能不复制其内容**） |

> 依《全国大学生数学建模竞赛人工智能工具使用规定（2026 年试行）》执行。

## 何时用

- 需要在论文正文放 AI 使用声明、并产出独立支撑材料 `AI工具使用详情.pdf`。
- 主稿/章节/代码/图表/参考文献发生变化后，需要**重跑同步**（旧详情不能沿用）。
- `comp-final-audit` 的 AI 申报反查闸（fatal 级）报错时，回到本技能排查。

## 唯一执行方式（照抄，勿手改产物）

```bash
# 前置：CLAUDE.md 必须含 MH_AI_DISCLOSURE=used 或 =none；=invalid 时立即停止并请用户重新确认

AI_TOOL=skills/_utils/build_ai_disclosure.py
[ -f "$AI_TOOL" ] || AI_TOOL=skills/shared-scripts/build_ai_disclosure.py

# 生成（LaTeX 工程；Word/Markdown 工程把 --paper-source 换成 paper/main.md）
python "$AI_TOOL" --manifest .mh/ai_disclosure.json \
  --paper-source paper/main.tex --output "AI工具使用详情.pdf"

# 收尾阻断检查（未通过不得把写作步骤标为完成）
python "$AI_TOOL" --manifest .mh/ai_disclosure.json \
  --paper-source paper/main.tex --output "AI工具使用详情.pdf" --check-only
```

## manifest 最小样例（`.mh/ai_disclosure.json`）

```json
{
  "schema_version": 3,
  "mode": "used",
  "confirmed_truthful": true,
  "records": [
    { "provider_id": "hunyuan", "model": "hunyuan-turbo",
      "used_on": "2026-09-11", "purposes": ["语言润色", "参考文献格式整理"] }
  ]
}
```

- `provider_id` 只允许白名单国产工具（脚本内 `PROVIDERS`：deepseek / qwen / zhipu / kimi / hunyuan /
  doubao / ernie / spark …），`model` 必须与该 provider 匹配且不得出现境外工具名。
- `purposes` 只允许五类辅助环节：**语言润色、代码调试、排版检查、参考文献格式整理、术语翻译与校对**。
- `mode=used` 时 `records` 1–5 条且 `confirmed_truthful` 必须为 `true`。
- `mode=none` 时正文写"本参赛队在竞赛过程中未使用任何AI工具。"，且不得残留旧的详情 PDF。

## 硬约束（违反即合规事故）

1. ⛔ **不得让语言模型自由编写详情**——必须调用确定性脚本；工具/型号/日期/用途只来自用户确认。
2. ⛔ **正文与详情分离**——声明在参考文献**之前**（不编号 `\section*{AI 工具使用声明}`，`\newpage` 独立成页），
   详情 PDF 放工作区根，**不入论文附录**。
3. ⛔ **不把 AI 工具列入参考文献**（2026 规定只要求正文声明 + 独立支撑材料）。
4. ⛔ **不得宣称逐轮对话实录**——第三节只写提问范围与边界（"限于/不含/不涉及"）。
5. ⛔ **工作区变化必须触发同步**——`--check-only` 指纹比对不通过就重跑生成。

## 与 comp-final-audit 的接口

反查闸必查 5 个结构 token（详情 PDF 须全部命中）：
`AI工具使用详情` / `所用AI工具名称` / `具体使用目的和环节` / `主要提示方式与使用过程` / `采纳、人工修改和核验情况`，
外加论文题名一致性检查（防顶替）。

## STEP_MANIFEST 产出声明

| 产出 | 类型 | 说明 |
|---|---|---|
| `AI工具使用详情.pdf` | 支撑材料 | 四节结构；由脚本按工作区指纹自适应，同一工作区重复生成逐字一致 |
| `paper/main.tex` 声明段 | 正文产物 | 脚本插入/校验，禁止手工改写 |
| `--check-only` 退出码 | 门禁信号 | 非 0 即未与当前工作区同步，阻断交付 |
