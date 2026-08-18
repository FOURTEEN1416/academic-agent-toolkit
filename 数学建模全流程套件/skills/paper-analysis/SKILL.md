---
name: paper-analysis
description: "论文数据分析与建模。根据论文大纲执行数据处理、统计分析、模型训练，输出结果数据供图表生成使用。有用户数据则用真实数据，无数据则模拟高质量仿真数据。"
argument-hint: [paper-plan-or-topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent
---

# 论文数据分析与建模

根据论文大纲执行数据分析：**$ARGUMENTS**

## ⛔ 结果约束审计（写入 RESULTS.md 前必做）

> **核心问题：「优化/求解/统计推断的结果」与「正文图表引用的结果」不一致是常见 bug。**
> 详见 `_utils/error_prevention.md` 第九章（comp-modeling 防错手册）。

**触发条件**：本步骤涉及优化求解 / 参数估计 / 置信区间 / 硬物理或业务约束 / 因果识别（IV、DiD 等）/ 仿真实验时，**必做**以下复核；
若任务只是纯描述统计或可视化 EDA，**仅需完成第 1、3、4 项，第 2 项可写 `n_constraints=0` 跳过**。

1. **从最终落盘的 JSON 重新计算合理性**（不要信任求解器的 "converged=True" 标记，也不要相信进程内变量）
2. **物理/业务约束硬边界复核**（变量范围、符号、守恒律、单调性等；对纯 EDA 任务可填 `n_constraints=0`）
3. **历史产物清理**：跑前删除 `*_v[0-9]*.json`、`*_old.json` 等旧版本，确保只有当前一次跑的结果
4. **RESULTS.md 末尾必须有审计凭证**：
   ```html
   <!-- AUDIT_OK source=<json路径> rechecked_at=<timestamp> n_constraints=<N> -->
   ```
   `n_constraints` 为本次复核通过的约束条数（无约束任务填 0）；缺这一行：本步骤不通过。

具体约束的可机器审计 lambda 形式 + 模板代码：见 `_utils/error_prevention.md` 第九章。

---

## 输入

1. **PAPER_PLAN.md** — 论文大纲（必须存在）
2. **TOPIC_PLAN.md** — 选题规划（如有）
3. **user_data/** — 用户上传的数据文件（可选）
4. **data/** — 已有数据目录（可选）

## ⛔⛔⛔ 完成铁律（最高优先级，违反则本步骤失败）

**本步骤必须产出 `RESULTS.md`（≥ 1KB）+ 至少 1 个 `figures/*.json`**。否则下游步骤拿不到数据。

**任何理由都不能绕过这条铁律**。具体来说：

1. **不要"边写边算"**：先用 Python 脚本算完所有结果落到 `figures/all_results.json`，再统一写 `RESULTS.md`
2. **不要在工作流末尾才创建文件**：每完成一个分析任务立刻 `cat << EOF >> RESULTS.md` 追加（避免 token 用完时整个 RESULTS.md 还没写）
3. **结束前必跑产出验证**（步骤的最后一步）：

```bash
echo "=== 产出验证（必须全部 ✅，否则继续补全）==="
PASS=true
[ -f RESULTS.md ] && SZ=$(wc -c < RESULTS.md) || SZ=0
if [ "$SZ" -ge 1024 ]; then echo "✅ RESULTS.md ($SZ bytes)"; else echo "❌ RESULTS.md 缺失或过小 ($SZ bytes)"; PASS=false; fi

JSON_COUNT=$(ls figures/*.json 2>/dev/null | wc -l)
if [ "$JSON_COUNT" -ge 1 ]; then echo "✅ figures/*.json ($JSON_COUNT 个)"; else echo "❌ figures/*.json 缺失"; PASS=false; fi

if [ "$PASS" != true ]; then
    echo ""
    echo "⛔ 产出验证失败 — 必须立刻补全后重新跑验证。不要结束本步骤。"
    echo "   正确做法: 用 Edit/Write 工具补全 RESULTS.md, 或重跑代码生成 figures/*.json"
fi
```

**如果验证失败,继续补全产出而不是退出**。Claude 必须看到"✅"才能结束本步骤。

## 工作流程

### Step 0: 恢复检查（断线重跑必读）

⛔ **本步骤可能因为断线/手动重跑被多次启动**。每次启动前**必须**先扫描已有产物，避免重复劳动 + 覆盖用户修改：

```bash
echo "=== 工作区扫描 ==="
HAS_CODE=$(ls code/*.py 2>/dev/null | wc -l)
HAS_JSON=$(ls figures/*.json 2>/dev/null | wc -l)
HAS_RESULTS=$([ -f RESULTS.md ] && wc -c < RESULTS.md || echo 0)
echo "  code/*.py: $HAS_CODE 个"
echo "  figures/*.json: $HAS_JSON 个"
echo "  RESULTS.md: $HAS_RESULTS 字节"
```

**根据扫描结果决定行动**：

| 状态 | 行动 |
|---|---|
| RESULTS.md ≥ 1KB + 至少 1 个 figures/*.json | **跳到 Step 6 自检**（前次已完成，仅做验证） |
| code/*.py 存在 + RESULTS.md 不完整或缺失 | **执行已有 code/main.py 拿到 JSON → 仅重写 RESULTS.md**（不要重写 code/） |
| code/*.py 存在 + figures/*.json 缺失 | **运行已有代码生成 JSON → 写 RESULTS.md**（不要重写 code/） |
| 都没有 | 从头开始（Step 1） |

⛔ **铁律**：
- **已有 `code/*.py` 文件不要重写**（用户可能改过；除非语法错误必须修复）
- **已有 `figures/*.json` 不要重新生成**（数据已固化，重跑会覆盖）
- **已有 `figures/*.png` 不要重画**（重画会让审稿人看到的图变了）
- 只有 RESULTS.md 不完整时才补它，且基于已有 JSON 写，不要重新计算

**如何判断"完整"**：
- RESULTS.md ≥ 1KB
- 包含每个分析任务的关键数值（参考 PAPER_PLAN.md 的图表预规划）
- 末尾有"分析任务清单"小结

**例外**：如果 `code/*.py` 跑起来报错（找不到模块/数据文件路径错），可以修改/补全代码使其能跑通，但不要重新设计逻辑。

### Step 1: 读取论文大纲 + 确定分析任务

从 PAPER_PLAN.md（或 TOPIC_PLAN.md）提取：
- 研究问题与假设
- 需要的统计方法/模型
- 变量定义（自变量、因变量、控制变量）
- 预期的图表清单（从图表预规划部分提取）

**⛔ MANDATORY: 输出分析任务清单：**
```
ANALYSIS CHECKLIST (from PAPER_PLAN.md):
[ ] 数据准备: [数据来源], [变量列表], [样本量]
[ ] 描述性统计: 均值/标准差/分布
[ ] 分析任务1: [方法名] — 输入: [xxx], 输出: [yyy]
[ ] 分析任务2: [方法名] — 输入: [xxx], 输出: [yyy]
[ ] 稳健性检验: [方法]
```

### Step 1.5: 提取图表预规划

**⛔ MANDATORY: 读取规划文档的图表预规划，了解 paper-figure 需要哪些数据。**

```bash
echo "=== 图表预规划 ==="
for plan in PAPER_PLAN.md TOPIC_PLAN.md; do
    [ -f "$plan" ] || continue
    echo "--- $plan ---"
    grep -i 'fig_\|图表\|TABLE_\|figure\|预规划\|配方' "$plan" | head -30
done
```

确保每个图表对应的数据都会在分析过程中输出到 JSON。

### Step 2: 数据来源判断 + 环境准备

**⛔ 关键决策：真实数据 vs 模拟数据**

```bash
echo "=== 数据来源检查 ==="
DATA_SOURCE="simulate"
for dir in user_data data; do
    if [ -d "$dir" ] && [ "$(ls -A $dir 2>/dev/null)" ]; then
        echo "✅ 发现用户数据: $dir/"
        ls -la $dir/
        DATA_SOURCE="real"
    fi
done
echo "数据来源: $DATA_SOURCE"
```

- **有用户数据** (`user_data/` 或 `data/` 非空)：读取真实数据，做清洗、缺失值处理、异常值检测
- **无用户数据**：根据论文主题模拟高质量仿真数据（见 data_quality 规则）

安装必要库：numpy, pandas, scipy, scikit-learn, statsmodels。

### Step 3: 代码目录结构

```
code/
  main.py              # 主程序（串联所有分析）
  data_preparation.py   # 数据准备（读取/模拟 + 清洗）
  analysis_1.py         # 分析任务 1
  analysis_2.py         # 分析任务 2
  robustness.py         # 稳健性检验
  utils.py              # 公共工具
  requirements.txt
```

### Step 3.0: ⛔⛔⛔ 模块导入铁律（违反必失败）

**问题本质：** code/ 下的脚本互相 `import` 时，从工作区根目录跑 `python code/xxx.py` 会让 sys.path
不含 `code/`，sibling import (`import utils`) 立即报 `ModuleNotFoundError`。这是历史最高频的失败原因。

**⛔ 规则 1：每个 .py 文件顶部必须有自举 import 头：**

```python
# ⛔ 自举模块路径（让 sibling import 不依赖调用方式）
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 之后才能写其它 import
import numpy as np
import utils as u
```

**⛔ 规则 2：执行任何 code/ 下的脚本必须 `cd code && python xxx.py`：**

```bash
# ✅ 正确
cd code && python main.py && cd ..

# ❌ 错误：sibling import 必报 ModuleNotFoundError
python code/main.py
python -m code.main
```

**⛔ 规则 3：写 problem/analysis 脚本前先创建 utils.py，避免"先写 analysis_1 → import utils → utils 不存在"瞬时错。**


### Step 4: 数据准备

**有用户数据时：**
1. 读取 CSV/Excel/JSON 文件
2. 数据清洗：缺失值、异常值、类型转换
3. 变量构造：交互项、滞后项、虚拟变量
4. 描述性统计输出到 `figures/descriptive_stats.json`

**无用户数据时（模拟）：**
1. 根据论文主题构造合理的模拟数据
2. 数据必须符合 data_quality 规则（见下方）
3. 设置随机种子 `np.random.seed(42)` 保证可复现
4. 模拟数据保存到 `data/simulated_data.csv`
5. 描述性统计输出到 `figures/descriptive_stats.json`

### Step 5: 逐任务分析执行

**必须按顺序逐项执行：编写 → 执行 → 验证 → 下一项。**

**⛔ MANDATORY: 数值必须从真实计算/真实数据得出，不得硬编码、不得编造。**

禁止行为：
- ❌ 在 Python 代码里写死结果值，如 `accuracy = 0.95`（必须从 `model.score()` 或 `accuracy_score()` 得出）
- ❌ 在 RESULTS.md 里直接写数字但没有对应代码（所有数字都必须能从 `figures/*.json` 中找到出处）
- ❌ 为了配合论文叙述而篡改结果（结果不理想就改数字、调 seed 直到好看）
- ❌ LLM 脑补实验结果（必须真实跑代码）

正确做法：
- ✅ 代码真实执行，结果存入 `figures/analysis_N_results.json`
- ✅ 关键指标（accuracy、rmse、r2、p_value 等）必须通过 sklearn/statsmodels/scipy 等库真实计算
- ✅ 结果异常（太完美或太差）时回去查代码/数据，**不要调参凑好看的结果**

每个分析任务：
1. 编写独立 Python 文件
2. 执行并检查输出
3. 验证结果合理性（系数方向、显著性、R²范围）
4. 保存结果到 `figures/analysis_N_results.json`
5. 结果异常则修改代码重跑

代码性能要求：
- 优先使用 numpy/pandas 向量化运算
- 每个脚本执行前后打印进度信息
- 如果代码跑超过 3 分钟，立即重写优化版本

### Step 5.5: 稳健性检验

根据论文类型执行适当的稳健性检验：
- 实证论文：替换变量、子样本回归、工具变量
- 统计建模：交叉验证、Bootstrap、敏感性分析
- 机器学习：消融实验、超参数敏感性

结果保存到 `figures/robustness_results.json`。

### Step 6: 结果验证 + 完整性检查

**⛔ 第一步：自动化"太完美"检测（查 AI 编造结果 / 过拟合）：**

```python
# code/sanity_check.py — 检测不合理数值
import json, os, sys, math

results = {}
for f in sorted(os.listdir('figures')):
    if f.endswith('_results.json') or f == 'all_results.json':
        try:
            with open(f'figures/{f}', 'r') as fh:
                results[f] = json.load(fh)
        except: pass

errors, warnings, suspicious = [], [], []

def check_unrealistic(name, val):
    if not isinstance(val, (int, float)) or isinstance(val, bool): return
    key = name.lower()
    # 归一化指标：R²/accuracy/precision/recall/f1/auc（>0.99 标记）
    if any(w in key for w in ['r2', 'r_squared', 'accuracy', 'acc', 'precision', 'recall', 'f1', 'auc']):
        if val > 0.99:
            suspicious.append(f"🚩 {name} = {val:.4f}（>0.99），请在审查中确认是否过拟合")
        elif val < 0:
            errors.append(f"❌ {name} = {val} 负值（模型比均值预测还差，必须换模型）")
        elif val < 0.5 and any(w in key for w in ['r2', 'r_squared']):
            errors.append(f"❌ {name} = {val:.4f}（R² < 0.5，模型解释力极弱，必须改进模型或检查数据预处理）")
    # 误差类：RMSE/MAE/MSE/Loss
    if any(w in key for w in ['rmse', 'mae', 'mse', 'loss']):
        if val == 0:
            suspicious.append(f"🚩 {name} = 0 完美误差，请确认训练/测试是否分开")
        elif val < 0:
            errors.append(f"❌ {name} = {val} 误差不应为负")
    # 提升百分比（>100% 标记）
    if any(w in key for w in ['improvement', 'speedup', 'gain', '提升', '改进']):
        if val > 1:  # >100%
            suspicious.append(f"🚩 {name} = {val:.2f}（提升 {val*100:.0f}%），请结合研究背景确认")
    # p-value
    if 'p_value' in key or 'pvalue' in key or 'p值' in key:
        if val == 0:
            suspicious.append(f"🚩 {name} = 0 完美显著（应 > 1e-16），请确认")
        elif val > 1:
            errors.append(f"❌ {name} = {val} p 值 > 1 不可能")

def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items(): walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj): walk(v, f"{path}[{i}]")
    elif isinstance(obj, (int, float)):
        if isinstance(obj, float):
            if math.isnan(obj): errors.append(f"❌ {path} 为 NaN")
            elif math.isinf(obj): errors.append(f"❌ {path} 为 Inf")
        check_unrealistic(path, obj)

for fname, data in results.items():
    walk(data, fname)

for e in errors: print(e)
for s in suspicious: print(s)
if errors:
    print(f"\n❌ {len(errors)} 个硬错误 — 必须修复"); sys.exit(1)
if suspicious:
    print(f"\n🚩 {len(suspicious)} 个可疑的'完美'结果 — 逐条确认：")
    print("  1. 训练/测试是否真的分开了？（数据泄漏最常见的原因）")
    print("  2. 样本量是否足够？（<100 时 R²>0.95 通常是过拟合）")
    print("  3. 自变量是否含因变量函数？（回归中最易犯的错）")
    print("  4. 如果确实合理（物理仿真/确定性问题），在 RESULTS.md 中明确说明")
elif not errors:
    print("✅ 所有数值通过 sanity check")
```

**⛔ 第 1.5 步：结合研究背景的全面合理性审查（最关键）：**

前面的自动 sanity check 只能抓固定模式。真正的合理性必须**结合论文选题的实际场景**来判断——只有你自己（AI）结合常识和研究背景才能发现所有问题。

**强制执行以下审查流程：**

```bash
echo "=== 结合研究背景的合理性审查 ==="

# 1. 完整读取选题与研究设计
echo "--- 选题与研究设计 ---"
for src in PAPER_PLAN.md TOPIC_PLAN.md FINAL_PROPOSAL.md; do
    [ -f "$src" ] && echo "=== $src ===" && cat "$src" | head -150
done

echo "--- 用户上传的数据概况 ---"
for src in user_data/*.csv user_data/*.xlsx; do
    [ -f "$src" ] && echo "文件: $src ($(wc -l < "$src" 2>/dev/null) 行)"
done

# 2. 列出所有计算结果
echo "--- 所有结果数值 ---"
python3 -c "
import json, os
for f in sorted(os.listdir('figures')):
    if not (f.endswith('_results.json') or f == 'all_results.json'): continue
    try:
        data = json.load(open(f'figures/{f}', 'r', encoding='utf-8'))
        print(f'=== {f} ===')
        print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
    except: pass
" 2>/dev/null
```

**然后你必须逐条回答以下 9 个问题（不能跳过，必须写在 RESULTS.md 末尾的"合理性审查"章节）：**

```
=== 合理性审查（结合研究背景）===

Q1. [数值量级] 每个关键指标的数值量级是否符合研究场景？
   举例：
   - 社会科学：回归系数绝对值一般 < 10（标准化后一般 < 1）
   - 经济学：GDP 增长率一般 0-20%，通货膨胀率一般 0-50%
   - 机器学习：准确率 0-1，训练时间 < 100 小时（中等规模）
   - 医学：OR 值一般 0.1-10，RR 值一般 0.5-5
   - 你的研究领域：[自行判断]
   逐条列出每个关键结果的数值，判断量级是否合理。

Q2. [符号方向] 结果的正负/大小方向是否符合先验假设和文献？
   举例：
   - 已知文献显示 X 对 Y 有正向影响，我的系数也应该是正的
   - 理论预期：教育投入越多，收入越高 → 系数应为正
   - 如果结果方向与主流文献相反，要么是重大发现（极罕见），
     要么是代码 bug（更常见），必须深入检查
   逐条检查结果方向是否与文献/理论一致。

Q3. [统计显著性分布] p 值分布是否合理？
   - 所有变量的 p 值都 < 0.001？（太完美，可能过度拟合或数据泄漏）
   - 所有 p 值都 > 0.05？（研究设计可能有问题）
   - 正常应该：关键变量显著，控制变量部分显著，一些不显著
   如果 p 值分布异常，说明数据或模型有问题。

Q4. [效应大小] 效应大小是否在文献报告范围内？
   - 同类研究的效应大小一般 [a, b] 区间
   - 我的效应大小是否与该区间一致？
   - 如果效应特别大（比同类研究大 10 倍），要么是真正的重大发现，
     要么是我的模型/数据处理有问题
   查阅文献比较，在 RESULTS.md 中引用 2-3 篇同类研究作为对照。

Q5. [R² / 拟合优度] 拟合优度是否在合理范围？
   **⛔ 关键：R² 的合理范围取决于任务类型，不能一刀切！**
   - 截面数据经济学/社科研究：R² 一般 0.2-0.6（因为噪声大、变量多）
   - 时间序列（含趋势）：R² 一般 0.7-0.95
   - **物理/工程曲线拟合（如光谱拟合、信号拟合、传递函数拟合）：R² 应 > 0.8**
     - 如果 R² < 0.5 → 模型形式错误（如缺少基线项、频率估计错误），必须换模型
     - 如果 R² 在 0.5-0.8 → 模型可能遗漏了重要物理效应，需要检查
   - 机器学习测试集：accuracy 一般 0.7-0.95（视任务难度）
   - 物理仿真/确定性问题：R² 可能接近 1.0（正常）
   
   **⛔ R² < 0.5 的拟合结果绝对不能直接写入论文。** 必须先诊断原因：
   1. 模型形式是否正确？（是否遗漏了基线漂移、非线性项、相位偏移等）
   2. 数据预处理是否正确？（是否需要去趋势、归一化、截取有效区间）
   3. 初始参数是否合理？（非线性拟合对初值敏感）
   修复后 R² 应显著提升，否则说明模型假设与数据不匹配。
   
   如果 R² > 0.99 而任务又不是确定性问题，极大概率过拟合或数据泄漏。

Q6. [样本量与自由度] 样本量是否支撑所用方法？
   - OLS 回归：每个参数至少 10-20 个样本
   - Logistic 回归：每个事件至少 10 个（EPV 原则）
   - 面板：截面 × 时间 至少 > 3 × 参数数量
   - 机器学习：训练集至少 > 10 × 特征数（防维度灾难）
   如果样本量不足，结果可能不稳定。

Q7. [变量间关系] 关键变量间的相关性是否合理？
   - 互斥变量不应正相关（如 A 组 vs B 组）
   - 同一概念的不同度量应正相关（如学历水平和毕业年限）
   - 如果出现违反常识的相关性，检查数据处理是否出错

Q8. [稳健性] 稳健性检验结果是否与主模型一致？
   - 替换变量/子样本/不同方法后，系数方向应基本一致
   - 如果稳健性检验结果方向相反或差异巨大，主模型可能不可靠
   至少做 2 种稳健性检验，并在 RESULTS.md 中对比报告。

Q9. [与研究设计一致] 实际结果是否与 PAPER_PLAN.md 中的研究设计预期一致？
   逐条对照：
   - 论文大纲说用 XX 方法 → 代码里确实用了 XX 方法？（不是偷换成更简单的）
   - 论文大纲的研究假设 → 结果支持还是拒绝？（都支持太完美，都拒绝说明设计有问题）
   - 论文大纲规划的分析任务 → 全部完成了？有遗漏的吗？
   - 论文大纲预期的效应方向 → 实际方向一致？
   - 如果结果与研究设计严重不符 → 要么代码有 bug（回去查），
     要么研究设计需要调整（回去改 PAPER_PLAN.md 再重跑）
   - 如果假设被拒绝 → 这是正常的科研结果，诚实报告，不要篡改
```

**对每个问题必须明确回答 ✅（通过）、⚠️（需说明）、❌（有问题）。**

如果任何一项打 ❌：
- **必须修改代码重新跑**，直到结果通过这 9 个问题的审查
- 不允许调参调随机种子来让结果"好看"
- 如果修改后某项仍然异常（如物理仿真的 R²=1），必须在 RESULTS.md 中**明确说明原因**

**⛔ 第二步：智能自检（代码跑完后，你必须逐项回答以下问题）：**

读取 PAPER_PLAN.md（或 TOPIC_PLAN.md）和 RESULTS.md，对照研究设计逐项自检。

**通用检查（必做）：**
```
=== 通用自检 ===
1. [研究覆盖] 论文大纲中规划的分析任务是否全部完成？缺了哪个？
2. [数值合理] 结果数值是否符合领域常识？（回归系数方向、效应大小）
3. [NaN/Inf] JSON 结果中是否有 NaN、Inf、null？
4. [统计规范] 是否报告了所有必要的统计量？（系数、标准误、p值、R²、样本量）
5. [数据一致] 描述性统计的样本量是否与回归分析一致？
```

**统计/实证类检查（论文写作场景必做）：**
```
=== 统计/实证类 ===
S1. [多重共线性] VIF 是否有 > 10 的变量？
S2. [内生性] 是否考虑了遗漏变量/反向因果？
S3. [异方差] 是否用了稳健标准误？
S4. [p值分布] 是否所有 p 值都 < 0.001？（太完美=可疑）
S5. [样本量] 截面 ≥ 200？面板 ≥ 30×10？时间序列 ≥ 100？
S6. [稳健性] 是否做了至少一种稳健性检验？
S7. [过拟合] R² < 0.99？训练集和测试集差距 < 10%？
```

对每项回答 ✅ 或 ❌ + 原因。如果有 ❌，修改代码重跑。

**⛔ MANDATORY: 对照 Step 1 的分析清单，逐项验证：**

```bash
echo "=== 分析清单对照 ==="
echo "检查结果文件："
for f in figures/descriptive_stats.json figures/all_results.json figures/robustness_results.json; do
    if [ -f "$f" ] && [ -s "$f" ]; then
        echo "  ✅ $f ($(wc -c < "$f") bytes)"
    else
        echo "  ❌ $f — MISSING or EMPTY"
    fi
done
echo ""
echo "检查分析结果 JSON："
ls -la figures/analysis_*_results.json 2>/dev/null || echo "  (无)"
echo ""
echo "检查代码文件："
for f in code/*.py; do
    [ -f "$f" ] && echo "  ✅ $(basename $f)" || echo "  ❌ $(basename $f)"
done
```

**如果有 ❌，必须回去补完再继续。**

**⛔ MANDATORY: 下游预期检查（paper-figure / paper-write 需要什么）：**

```bash
echo "=== 下游预期检查 ==="
# 1. 图表规划中的每张图是否都有对应 JSON 数据
if [ -f PAPER_PLAN.md ]; then
    echo "--- 图表规划 vs JSON 数据 ---"
    # 提取规划中的图表文件名（fig_xxx 或 fig_yyy 形式）
    PLANNED_FIGS=$(grep -o 'fig_[a-zA-Z_0-9]*' PAPER_PLAN.md 2>/dev/null | sort -u)
    for fig in $PLANNED_FIGS; do
        # 对应的 JSON 是否存在或 all_results.json 中有对应 key
        if [ -f figures/all_results.json ] && grep -q "$fig\|${fig#fig_}" figures/all_results.json 2>/dev/null; then
            echo "  ✅ $fig — 在 all_results.json 中找到对应数据"
        elif [ -f "figures/${fig}_results.json" ]; then
            echo "  ✅ $fig — 有独立 JSON 文件"
        else
            echo "  ⚠ $fig — 未找到支撑数据（paper-figure 将难以画图）"
        fi
    done
fi

# 2. Claims-Evidence 回填：PAPER_PLAN.md 中每个 claim 是否都有 evidence
if [ -f PAPER_PLAN.md ]; then
    echo ""
    echo "--- Claims-Evidence 回填检查 ---"
    python3 -c "
import re, json, os
try:
    plan = open('PAPER_PLAN.md', 'r', encoding='utf-8').read()
except: exit(0)
# 提取 claims-evidence 表格（| Claim | Evidence | ... |）
rows = re.findall(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|', plan)
# 过滤表头和分隔符
claims = [(c.strip(), e.strip()) for c, e in rows if c.strip() not in ('Claim', '---') and '---' not in c and len(c.strip()) > 5]
if not claims:
    print('  （未检测到 Claims-Evidence 矩阵）')
    exit(0)
# 加载实验数据
results_text = ''
for f in ['figures/all_results.json', 'RESULTS.md', 'experiment_results.md']:
    if os.path.exists(f):
        try: results_text += open(f, 'r', encoding='utf-8').read()
        except: pass
missing = []
for c, e in claims[:10]:  # 最多检查前 10 个
    # Evidence 里提到的关键词是否在结果数据中出现
    keywords = re.findall(r'[a-zA-Z_]{4,}|[\u4e00-\u9fff]{2,}', e)[:3]
    if not any(kw.lower() in results_text.lower() for kw in keywords):
        missing.append(c[:40])
if missing:
    print(f'  ⚠ {len(missing)}/{len(claims)} claims 在实验数据中找不到对应证据:')
    for m in missing[:5]: print(f'    - {m}')
else:
    print(f'  ✅ {len(claims)} claims 在实验数据中都能找到对应证据')
" 2>/dev/null || echo "  (Python 检查失败，跳过)"
fi
```

如果下游预期检查发现缺失，考虑补充对应的分析代码再重跑，或在 RESULTS.md 中明确标注该 claim 需要的数据还没算。

### Step 7: 结果汇总

1. 汇总所有分析结果到 `figures/all_results.json`
2. 编写 `RESULTS.md`：每个分析任务的方法、关键发现、数据文件路径

## 关键规则

- **paper-analysis 只负责数据处理、统计分析、输出结果数据（JSON/CSV）。不画图。**
- **⛔ 禁止生成 PDF 图表。** 不要调用 `plt.savefig()` 或 `save_fig()`。图表全部由下一步 paper-figure 生成。
- 主输出文件：`RESULTS.md` + `figures/*.json` + `code/*.py`
- 代码必须能运行：写完必须执行验证
- 结果必须保存为 JSON/CSV 文件（供 paper-figure 读取画图）
- 代码要有注释
- 数据路径用相对路径
- requirements.txt 必须生成


<data_quality>
### 数据模拟质量规则（无用户数据时）

1. **真实范围**：数值必须符合研究领域 — 如 GDP 用万亿元不是随机 0-1，温度用 °C 不是任意整数
2. **有意义的模式**：数据应体现模型要捕捉的趋势/关系 — 如研究季节性需求，数据应有季节性波动
3. **图表友好**：设计数据使图表看起来专业且有信息量：
   - 避免极端异常值把主数据压缩到很小的范围
   - 不同方法/组之间有可见但不夸张的差异（5-20% 差距，不是 0.1% 或 500%）
   - 足够的数据点保证曲线平滑（折线图 ≥50 点，分布图 ≥200 点）
   - 方法对比：本文方法应最优但不要不切实际地碾压 — 其他方法在某些指标上也有优势
4. **与论文主题一致**：所有生成的数据必须可追溯到论文大纲的描述
5. **可复现**：设置随机种子 `np.random.seed(42)`
6. **样本量合理**：
   - 实证论文：至少 200+ 观测值
   - 面板数据：至少 30 个体 × 10 期
   - 时间序列：至少 100 个时间点
   - 截面数据：至少 500 个样本
</data_quality>
