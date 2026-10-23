## Step 6: Final verification

本文件是 `skills/comp-paper-zh/SKILL.md` Step 6 的执行细则；触发条件与放行判据见 SKILL.md「Workflow」。

```bash

bash skills/_utils/writing_check.sh paper/ 2>/dev/null || bash academic-toolkit/skills/_utils/writing_check.sh paper/ 2>/dev/null || bash ../../skills/_utils/writing_check.sh paper/

```

**⛔ 能力声称终检（正文写完后跑，扫"有没有把没通过的能力写成成果"）：**

```bash

FAST_MODE=0; grep -q 'MH_FAST_MODE=1' AGENTS.md 2>/dev/null && FAST_MODE=1

python skills/_utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE 2>/dev/null || python academic-toolkit/skills/_utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE 2>/dev/null || python ../../skills/_utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE

PCC=$?   # 此时正文已成型：会扫未通过能力名是否出现在正文(WARN),并复核验收状态(FAIL阻断)

```

> WARN（未通过能力名出现在正文）：确认不是把没做成的写成做到了；若确在"局限/未来工作"里如实提及可放行。`PCC=1`：仍有能力未通过验收，不能定稿。

Also check:

- `wc -c paper/sections/*.tex` 看各章明细（≈900 字符/页），找出最薄的 1-2 章优先扩充；页数是否达标以下方「正文页数预检」为唯一权威

- Any sub-problem chapter <3500 chars (~4 pages) needs expansion

- All figures/*.pdf and TABLE files (PDF模式 .tex / Word模式 .md) referenced in sections/正文

- No template bracket placeholders remaining (`[论文标题]`, `[中文摘要内容]`, etc.)

**⛔ Constraint consistency check (MUST do before finishing):**

Read PROBLEM_ANALYSIS.md (or the original problem statement in user_data/) and check every numerical result in the paper against the problem's constraints:

```

=== 论文-题目约束一致性检查 ===

1. 读取题目中的所有约束条件（容量、预算、时间窗、数量限制等）

2. 逐个检查论文正文中的结果是否满足这些约束

3. 例如：题目说"车辆载重上限 6000kg"，论文写"装载 7344kg" → 矛盾，必须修正

4. 例如：题目说"30 个省份"，论文分析了 28 个 → 不完整，必须补充

5. 摘要中的数字是否与正文一致？

6. 不同章节引用同一个结果时数字是否一致？（如问题一的最优解在摘要、正文、结论中出现 3 次，必须完全相同）

```

如果发现矛盾，修改论文正文（不是修改约束）。如果是代码结果本身违反约束，说明代码有 bug，需要回到 comp-code 修复。

**⛔ Page count pre-check (MUST pass before finishing — do NOT leave this to compile step):**

> ⛔ 上限取 **PAGE_CAP**（`contest_profile.gate_page_cap`，本任务 operative 门禁口径）；计哪些页由 **PAGE_SCOPE**（`gate_page_scope`：`body`/`total`）决定——正文/总页数分开统计，不混成一个数。

> `PAGE_SCOPE=body`（如 `comp_cumcm`/`comp_huawei`）：上限只计正文（章节 1 - 结论，含图表），**不含**摘要 / 目录 / 参考文献 / **附录代码**；检查只统计 `paper/sections/*.tex`，附录代码归 `paper/appendix/*.tex`，单独不限页数。

> `PAGE_SCOPE=total`（如 `comp_mcm`，25 页按整本计）：对照**全文估算**检查，不拿正文估算充数（正文口径会静默少算）。

> **PAGE_CAP_STATUS**（`page_cap_status`）必须随数值一起上报：`unverified` = 来源未核验——**不产生默认硬页限**、不得当作已证官方规则，未知只使对应合规结论保持阻塞；仅 `official_verified` 或单独标识的显式任务授权（`task_override`）才按硬上限执行，禁止包装混充。

```bash

python skills/_utils/page_precheck.py --workspace . 2>/dev/null || python academic-toolkit/skills/_utils/page_precheck.py --workspace . 2>/dev/null || python ../../skills/_utils/page_precheck.py --workspace .

```

脚本做三件事：①代码块（lstlisting/verbatim 等）混进 sections/ 即违约——代码属 appendix/，混入会让估页虚高而实际正文薄；②字符估页（sections/ 900 字符/页）对照 PAGE_CAP，超限即违约；③附录单独统计不计入。cap 缺失=上限未知（待核实），禁止编默认值。finish 时 quick_gates 会以真实 PDF 按同一合同终检。cwd 语义：`--workspace .` 要求在工作区根执行；从工具箱根跑时改传 `--workspace workspaces/<工作区名>`。

不为凑任何页数目标扩写充数；章节完整性由写作合同保证（每个子问题覆盖、论断有证据支撑），篇幅随建模与论证需要自然形成。

⛔ **正文 vs 附录归档约束**：

- `paper/sections/` — 仅放正文章节（绪论 / 方法 / 结果 / 讨论 / 结论）

- `paper/appendix/` — 放代码 / 长数据表 / 求解日志 / 公式补充推导 / 算法伪代码

- 严禁把代码塞 sections/（会让页数预检虚高但实际正文薄）

⛔ **页数扩展约束（防幻觉）— 写公式 / 加过程图 / 加灵敏度时必须遵守**：

| 扩展方向 | ✅ 允许 | ⛔ 禁止 |

|---|---|---|

| **补公式推导** | 从 MODELING_REPORT.md 抄推导链；中间步骤展开（如 (a)→(b) 的代数变换写明）；编号 (1)(2)(3) 连续 | 凭印象写新公式；编"假设 X 服从 Y 分布"等没有依据的统计假设；公式里编数字（如 ρ=0.873） |

| **增过程图** | 用 plot_utils 真画图（gen_fig_xxx.py 跑出 PDF/PNG）；流程图节点对应 comp-code 实际算法步骤；TikZ 流程图节点文本与代码注释一致 | 用占位符；编一个不存在的算法步骤；流程图数字不与 RESULTS 一致 |

| **加灵敏度** | 必须**真跑** sensitivity 代码，把结果存 `figures/sensitivity_*.json`；表格数字从 json 读 | 直接在正文写"参数 α 增加 10% 时目标值下降 5.2%" 而**没有真跑实验** |

| **充实结果讨论** | 解读已有结果（results.json / RESULTS.md）；对比基准方法；分析误差来源 | 重复说同一件事；加"如表所示"水文；编未做的对比实验 |

⛔ **进阶扩展方向（按题型分类，所有数字必须真跑代码产出）**：

**🔹 通用扩展（任何题型都适用，每个能扩 3-8 页）**：

| 扩展模块 | 内容 | 必须真做的事 | 推荐图表 |

|---|---|---|---|

| **数据预处理章节** | 异常值检测（boxplot/Mahalanobis）/ 缺失值处理（均值/KNN/多重插补）/ 归一化（min-max/z-score/robust）/ 特征工程（PCA/多项式/交互项）/ 数据划分（8:1:1 或 K-Fold） | comp-code 跑预处理脚本，保存 `figures/preprocess_*.json` | EDA 概览 4-panel（basic #1+#5）/ 预处理前后 2-panel / 缺失值热图 / 相关性矩阵 |

| **多算法对比** | 同一问题用 ≥3 个算法解（GA/SA/PSO/Greedy / RF/XGBoost/LightGBM/DNN / SVM/Logistic/kNN） | 真跑所有算法，记录准确率/F1/RMSE/运行时间/收敛迭代数 | 收敛曲线对比（comp #1）/ Performance Profile（adv #25）/ 雷达图 / 方法对比柱状图 |

| **超参敏感性** | 学习率 / batch size / 正则化系数 / 树深度 / λ 罚项；用 grid search / 贝叶斯优化 / Optuna | 用 sklearn.model_selection 跑 GridSearchCV，保存 `figures/hpopt_*.json` | 超参敏感性热图 / 等高线图 / 学习曲线 2-panel |

| **消融实验**（ML 类必备） | 移除某组件看性能变化（完整方法 vs -A vs -B vs -C 各组件） | 真跑每个消融变体，保存 `figures/ablation_*.json` | Diverging Bar（adv #20）/ 消融对比表 |

| **复杂度分析** | 时间复杂度 O(N²)/O(N log N) / 空间复杂度 / 实测 wall clock time（不同 N 下） | 用 time.perf_counter() 真测，画 log-log 复杂度图 | 复杂度 log-log 图 / 内存占用曲线 |

| **理论支撑** | 收敛性证明（数值方法）/ 唯一性证明 / 可行性证明 / 稳定性分析 | 从 MODELING_REPORT.md 抄推导，不能新编；引文献 | TikZ 证明流程图（推导逻辑可视化） |

| **可解释性** | SHAP / LIME / PDP / 决策树可视化 / 注意力图（NN 类） | 用 shap.Explainer / lime 真跑，保存 `figures/explain_*.json` | SHAP 摘要图（adv #7）/ ICE+PDP（adv #26）/ 注意力热图 |

**🔹 工程优化类（A/B 题）专属扩展**：

| 扩展模块 | 内容 | 真做要求 |

|---|---|---|

| **多目标 Pareto** | 双目标 / 三目标 Pareto 前沿 + 决策偏好分析 | 用 NSGA-II / MOEAD 真跑（pymoo 库） |

| **鲁棒性分析** | 数据扰动 / 参数扰动下的解稳定性 | 蒙特卡洛 N=1000 次扰动 |

| **求解器对比** | Gurobi / CPLEX / SCIP / 自实现启发式 | 真跑各求解器对比 |

| **大规模数据扩展** | 100/1000/10000 实例规模下的算法表现 | 跑不同规模 benchmark |

**🔹 数据分析/ML 类（C/D 题）专属扩展**：

| 扩展模块 | 内容 | 真做要求 |

|---|---|---|

| **误差来源分解** | 偏差-方差权衡（bias-variance tradeoff）；噪声拆解 | 5×CV + 多模型测 bias 和 variance |

| **类别不平衡处理** | SMOTE / 欠采样 / 类别权重 | 真跑各方法对比 |

| **特征重要性** | 排列重要性 / SHAP / 信息增益 | 至少 2 种方法交叉验证 |

| **学习曲线诊断** | train / val 损失曲线，判断欠拟合 / 过拟合 | 真跑不同训练集大小 |

**🔹 综合建模类（E/F 题）专属扩展**：

| 扩展模块 | 内容 | 真做要求 |

|---|---|---|

| **多种建模思路对比** | 机理模型 vs 数据驱动 vs 混合模型；同一现象 3 种描述 | 真跑各建模思路 |

| **物理一致性检查** | 量纲检验 / 守恒律 / 边界条件 | 公式真验 |

| **仿真验证** | 数值仿真 vs 解析解 / 历史数据回测 | 真跑仿真代码 |

| **不确定性量化** | 蒙特卡洛 / Bootstrap / 贝叶斯后验 | N≥500 次重复 |

⛔ **仅当本轮确实扩展了章节，才立即重跑 facts_audit**（扩完当场抓虚构数字）：

> ⛔ **去重说明**：这与数据可追溯性一节的 `facts_audit.py --stage paper` 是**同一份检查**（[13][14][15][16]），后者是**权威终检、一定会跑**。本轮没扩展任何章节就跳过这里，不重复跑。

```bash

python skills/_utils/facts_audit.py --stage paper 2>/dev/null || python academic-toolkit/skills/_utils/facts_audit.py --stage paper 2>/dev/null || python ../../skills/_utils/facts_audit.py --stage paper

```

[15] 会抽 60 个 2 位以上小数浮点数核对溯源。**审计 FAIL 不允许结束**，必须把不能溯源的数字改回真实值或删掉。

⛔ **乱码防护（LaTeX 模式）**：

- 公式定界符：`\begin{equation} ... \end{equation}` 或 `$ ... $`（不要 markdown `$$...$$`）

- 特殊字符必须转义：`& → \&`、`% → \%`、`_ → \_`、`# → \#`、`~ → \~{}`、`^ → \^{}`

- 中英文混排：变量符号英文（如 R²、RMSE、α），描述中文；不要中英文之间多空格

- 中文标点和英文符号之间不加空格（如 `f(x)。` 而非 `f(x) 。`）

- 公式中含中文用 `\text{...}`（如 `\sum_{i \in \text{测试集}}`）

**Figure embedding verification（必须全绿才能进入 Step 7）**：

```bash

python skills/_utils/figure_layout_check.py paper/ 2>/dev/null || python academic-toolkit/skills/_utils/figure_layout_check.py paper/ 2>/dev/null || python ../../skills/_utils/figure_layout_check.py paper/

```

终检版覆盖：figures/*.pdf 全部被正文引用、FIGURE_MANIFEST 对账（规划→产出→嵌入逐环核对）、流程图堆叠。任何 ❌ 回对应章节补嵌/补画后再跑，直到全绿。

**⛔ 模板完整性自检（写完所有章节后必须跑，确认 main.tex 没有被破坏）：**

```bash

python skills/_utils/template_integrity_check.py --full 2>/dev/null || python academic-toolkit/skills/_utils/template_integrity_check.py --full 2>/dev/null || python ../../skills/_utils/template_integrity_check.py --full

```

通用五项（documentclass / sections input / 参考文献结构 / 附录结构 / 上标引用定义）+ 按 `CONTEST_ID` 自动带赛事专属检查（五一杯承诺书页与封面 logo、MathorCup·APMCM 的 cls 与队伍信息、华中杯 cls、华为杯标题约束）。任一失败 = main.tex 可能被意外重写，从模板重新复制、只替换占位符。
