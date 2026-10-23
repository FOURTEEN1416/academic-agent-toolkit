## Step 2: Abstracts（摘要规格：Step 2 只写占位，Step 5.6 整篇执行）

本文件是 `skills/comp-paper-zh/SKILL.md` Step 2 / Step 5.6 的摘要执行细则。Step 2 只落占位，摘要正文到 Step 5.6 才写；届时整篇读本文件并逐条执行。

**⛔ CRITICAL: Do NOT write the abstract now.** Skip this step entirely. Write a placeholder `[摘要待正文完成后填写]` in the abstract section. The abstract MUST be written LAST (after Step 5) because it needs specific numerical results from all chapters. Writing it first = making up numbers.

Come back to fill the abstract in Step 5.6 (after all body chapters are complete). At that point, read RESULTS.md and all section .tex files to extract the actual numbers.

<abstract_format>

**⛔ 摘要动笔前先读语料**：读 `academic-toolkit/data/award_paper_exemplars.json` 同赛事 2-3 篇结构化条目 + `skills/award-paper-mining/data/abstract_golden_structure.md`（摘要黄金结构）与 `sentence_pattern_library.md`（句式库），模仿其信息密度与节奏，禁止照抄措辞。下述规则是与语料对标后的底线要求，不是替代。

The template uses manual typesetting for abstracts. Do not use two `\begin{abstract}` environments — ctexart shows "摘要" as title for both.

**⛔ 华中杯例外**：华中杯模板基于 `cumcmthesis` 文档类，使用 `\begin{abstract}...\keywords{}\end{abstract}` 环境。不要改成手动排版格式。正确写法：

```latex

\begin{abstract}

[中文摘要内容，600-800字，写满一整页]

\keywords{[关键词1]\quad [关键词2]\quad [关键词3]}

\end{abstract}

```

**⛔ 五一杯说明**：五一杯模板有承诺书页（第一页）和封面页（第二页）。**五一杯摘要使用手动排版（不用 `\begin{abstract}` 环境）**：关键词在上（`\noindent \textbf{关键词：}...`），摘要在下（`\noindent \textbf{摘\quad 要：}`）。这是五一杯官方格式，跟国赛/华中杯不同。承诺书页不要删除。

Correct format for cumcm/stats templates (already in template):

```latex

% === 中文摘要 ===

\begin{center}

{\zihao{3}\heiti 摘\hspace{2em}要}

\end{center}

\zihao{-4}\songti

[中文摘要内容，600-800字，写满一整页]

\noindent\textbf{关键词：}...

% === 英文摘要（新页）===

\newpage

\begin{center}

{\zihao{3}\bfseries Abstract}

\end{center}

[English abstract, 300-400 words, faithful translation]

\noindent\textbf{Keywords:} ...

```

**数模竞赛摘要（国赛/MathorCup/APMCM/五一杯等通用）**: 600-800 字（硬范围，目标 680-760；单一事实源见 `skills/_utils/abstract_writing_contract.md`；统计建模特例 500-700 字）, every sub-problem must have specific numerical results（整篇合计 ≥3 个带单位/精度的真实数值结果）。

⛔⛔ **必须按问题分段，绝不允许所有问题挤成一大段。** 段骨架：

- 第 1 段：背景概述 + 整体建模思路

- 第 2 段起：**每个"针对问题 X"独占一段**（方法 + 具体数值结果）

- 末段：模型评价与推广

- **段间强制用 LaTeX 空行分隔**（源码里空一行 = 一个新段落）。五一杯手动排版摘要，分段规则同样适用。

⛔⛔ **摘要关键内容加粗（只在摘要正文，用 LaTeX `\textbf{}`）**：评审快速扫读摘要抓重点，把最关键的方法与结果加粗是加分项。**只加粗以下三类"结论锚点"**：

1. **关键结果数值**（最终答案数字）：如 `\textbf{2376.8}`、`\textbf{98.7\%}`、`\textbf{12.4 km}`（注意 `%` 在 LaTeX 里要写 `\%`）

2. **核心方法/模型名**：如 `\textbf{NSGA-II}`、`\textbf{灰色预测 GM(1,1)}`——**每个方法名只在首次出现或结论处加粗一次**，不是每次提到都加

3. **关键结论的核心名词**

⛔ **加粗铁律（防加粗过多反而杂乱，宁少勿多）**：

- 每段 **1~3 处**，全篇 **≤ 12 处**。超了就是错。

- **禁止**：整句 `\textbf{}`、背景铺垫加粗、连接词加粗、同一方法名反复加粗。

- ⛔ 只用 `\textbf{}`（LaTeX），**不要用 markdown `**xxx**`**（LaTeX 下 `**` 不渲染成粗体、会原样显示）。

- ⛔ **不影响关键词行**：`\textbf{关键词：}` 那个加粗是标签本身，照旧。

- ⛔ `\textbf{}` 只包文字，**数字本身必须仍从正文如实摘出**，不能因加粗改动或编造。

- ⛔ 五一杯等手动排版摘要同样适用（`\textbf{}` 在正文任意位置都合法）。

正例：`本文构建 \textbf{NSGA-II} 多目标模型，求得最优成本 \textbf{2376.8 万元}，较基线降低 \textbf{12.3\%}。`

⛔ **硬约束：一个自然段里绝不允许出现两个及以上"针对问题"。** 正反例：

```latex

（正确 ✅ — 每个"针对问题 X"之间空一行，各自独立成段）

本文针对……建立了……模型。

针对问题一，构建……模型，采用……算法求解，最优解为……，适应度达 0.917。

针对问题二，构建……模型，……MAPE 由 29.48\% 降至 14.93\%。

针对问题三，……预测结果为 952.8、1570.5、11030.9。

灵敏度分析表明……，模型评价显示……。

```

```latex

（错误 ❌ — 问题二/三挤在同一段，评委无法按问题快速定位）

针对问题二，构建……模型，MAPE 14.93\%。针对问题三，预测结果为 952.8、1570.5。

```

⛔ **写完摘要后跑自检（检测→修复→再检测闭环）**：

```bash

python skills/_utils/abstract_paragraph_check.py 2>/dev/null || python academic-toolkit/skills/_utils/abstract_paragraph_check.py 2>/dev/null || python ../../skills/_utils/abstract_paragraph_check.py

```

检测"针对问题 X"是否每问独立成段（含定位逻辑：abstract 环境 → 手动排版摘要段 → sections/ 兜底）。exit 1 时在每个"针对问题 X"前补一个 LaTeX 空行拆成独立段落，重跑直到输出"✓ 摘要按问题分段正确"，方可进入下一步。

> 其余摘要质量线由机器分工：「随着…的发展」式 AI 套话开头由引擎 `ai_flavor` 强制闸硬拦——现在就别写；摘要加粗克制度由 `abstract_emphasis_check`（writing_check.sh 全家桶）把关；字数/六要素/分段骨架的唯一事实源见 `skills/_utils/abstract_writing_contract.md`。

**⛔⛔ 丰满模式摘要标准（华为杯默认 / 任意竞赛开启丰满模式时生效，1500-2200 字，跨两页）**：

⛔ **触发条件**（赛事判据=下发的 `CONTEST_ID`；用户开关才读 AGENTS.md，不用文本猜赛事）：

- `CONTEST_ID = comp_huawei` — 华为杯默认走丰满模式

- `丰满模式` / `rich_mode` — 任意竞赛通过前端"丰满模式"开关启用（用户开关，读 AGENTS.md 合法）

**触发自检**：`CONTEST_ID = comp_huawei`，或 AGENTS.md 含 `丰满模式`/`rich_mode` 用户开关 ⇒ 摘要按 1500-2200 字 + 6 项要素 + 5 段骨架写。

丰满模式下官方允许/鼓励摘要跨两页，**字数压在通用 600-800 字会让评委觉得工作量不够**。

**篇幅与结构（强制）**：

- **总字数 1500-2200 字**（不算空格、空行），允许跨 2 页，**不要刻意压缩到一页**

- **每子问题段 280-400 字**（5 个问题 → 1400-2000 字主体 + 100-200 字开头背景 + 关键词）

- 段间用 LaTeX 空行分隔，**每段独立成块**，便于评委按问题快速定位

**6 项展示要素清单（每段必须命中）**：

| 要素 | 反例（AI 常犯） | 正例（华为杯优秀作品） |

|---|---|---|

| **1. 问题背景开头（写具体矛盾）** | "随着...的发展" 式空背景（AI 套话，ai_tell_check 硬拦） | 首句直接给现实矛盾或数据事实："...在...场景下存在...瓶颈，...作为核心组件，其[关键指标]直接制约[宏观目标]。" |

| **2. 方法链叙述（因果衔接）** | 只甩结论"构建了 XGBoost 三分类模型"（无过程无取舍） | 方法按因果连缀成句："噪声叠加导致直接拟合失真，故先以傅里叶变换分离趋势项并提取 X/Y/Z 特征；为避免单模型偏差，建立 A/B/C 三模型对比，以混淆矩阵和交叉验证择优"（不用"首先/接着/最后"机械过渡词） |

| **3. 候选方法对比** | 只讲最优方案（XGBoost） | 列 2-3 个候选方法 + 选定 + 选择理由（MLP / 随机森林 / MLP-RF 加权集成；Solow / 二次多项式 / 温度饱和） |

| **4. 中间过程数值** | 只给最终 MAPE/R² | 加候选模型对比数（"MAPE 由 29.48% 降至 14.93%"、"参数估计值分别接近 1.5、1.4、1.5"） |

| **5. 附件预测结果数值** | 只说"已对附件三 400 样本完成预测" | **列若干代表性预测值**："部分模型预测结果为 952.8 W/m³、1570547.8 W/m³、11030.9 W/m³、..."（4-10 个数值） |

| **6. 可视化手段提及** | 不提图表 | "借助混淆矩阵和残差图"、"对磁通密度可视化"、"部分结果以表格呈现" |

**关键词数量**：8-12 个，**算法名 + 数学工具 + 模型族**全列，每个 `\quad` 分隔

- ❌ 反例（5-6 个）：磁芯损耗 XGBoost Steinmetz方程 方差分解 NSGA-II

- ✅ 正例（8+ 个）：多层感知机 随机森林 最小二乘法 温度饱和模型 方差分析（ANOVA） 多目标优化 双目标-单目标转化 粒子群算法

**⛔ 关键词行约束（国赛强制）**：`\keywords{...}` 或 `\noindent\textbf{关键词：}...` 中所有关键词加上 `\quad` 分隔后，**必须在一行内排完，不得换行**。若关键词过多导致换行，应精简至 6-8 个核心关键词，确保单行容纳。自检方法：编译 PDF 后检查关键词行是否有换行，若有则减少关键词数量。

**5 段华为杯摘要骨架模板**（按这个填）：

```latex

% 第 1 段：问题导入（150-200 字）

[现实场景中的具体矛盾或数据事实：...在...场景下存在...瓶颈]，

[问题对象]作为[系统]中的核心组件，其[关键指标]直接影响[宏观目标]。

本文针对[赛题 5 个子问题]，基于[数据集规模]，建立了[方法链概述]。

% 第 2 段：问题一（280-400 字，过程式 + 候选对比 + 数值）

针对问题一[一句话交代：要解决什么、难点在哪]。考虑[约束/难点]，建立 [方法 A、B、C] 等模型进行对比，

最终选用 [选定方法] 并通过 [评估方式] 验证。结果表明 [关键数值1, 2]，

[附件二/三/四 的具体结果如：分类为正弦波 20 个、三角波 44 个、梯形波 16 个]。

% 第 3-5 段：问题二、三、四、五，结构同问题一

% 第 6 段（可选）：模型评价与意义（80-150 字）

% 关键词（8-12 个，\quad 分隔）

\noindent\textbf{关键词：} 算法名1 \quad 算法名2 \quad ... \quad 数学工具N

```

⛔ **华为杯摘要写作禁区**：

- ❌ 把摘要压到 1 页：评委一眼判工作量不够

- ❌ 只讲最终方案不讲候选对比：评委看不到方法选择的合理性

- ❌ 关键词只 5-6 个：丧失关键词检索曝光

- ❌ 用「随着…的发展」式空背景开头：AI 套话（ai_tell_check 硬拦）；背景必须写具体矛盾或数据事实

- ❌ 不列附件预测代表数值：评委无法快速核验工作量

**统计建模摘要**: 500-700 字, aim to fill most of one page but leave 3-4 lines margin at bottom — overflowing onto a second page looks worse than being slightly short. Content chain: 研究背景与意义 → 现有方法不足 → 本文方法 → 数据来源与处理 → 关键数值结果 → 应用价值与政策建议. English abstract: 350-500 words, same structure and all numerical results, also fit on one page.

</abstract_format>
