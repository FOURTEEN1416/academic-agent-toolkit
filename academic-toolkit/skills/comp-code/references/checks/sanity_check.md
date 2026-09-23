# sanity_check.md — 自动数值审查 + 9 问背景审查 + 编程 Bug 排查

> 目标：拦截"能跑通但结果荒谬"与"结果合理但来源可疑"。所有检查遵守规则 B（脚本全精度重算、只输出结论）。
> 配套手册：`skills/_utils/error_prevention.md` 通用原则章；题型细则见各分类自检文件。

## A. 自动数值审查（对 results.json / 输出数据）

- [ ] 无 NaN/Inf/None 混入结果文件；分类标签域合法（无越界类别、无 float 混进 int 域）；
- [ ] 量纲与数量级：结果与题面常识数量级一致（派车数 ≤ 车队规模、得分 ∈ 声明区间、概率 ∈ [0,1]）；
- [ ] 常数退化检查：输出不是全常数/全同值（全员一个方案 = 模型没生效的典型症状）；
- [ ] 求解状态：优化器返回 status == Optimal（或声明允许的次优凭证 + gap 值）；统计模型收敛（无 "convergence not achieved" 被静默吞掉）；
- [ ] 随机性受控：设了 seed 且写入 RESULTS.md；同 seed 重跑结果可复现（关键数字逐位一致）。

## B. 9 问背景审查（对照 PROBLEM_ANALYSIS.md）

- [ ] 本问回答的就是题目问的那个问题（防"任务降维"：要方案比较做成了单方案求解、要机理分析做成了曲线拟合）；
- [ ] 输出粒度与题目要求一致（按天/按小时、按站点/按线路、按事件簇/按记录）；
- [ ] 结论句能从 results.json 的数字直接支撑，无需"显然/大约"式跳步。

## C. 编程 Bug 高频模式排查

- [ ] 索引错位：pandas 按标签 vs 按位置（loc/iloc）、0-based 与题面 1-based 编号换算；
- [ ] 浅拷贝导致的原地修改（df 切片赋值 SettingWithCopy、list 别名）；
- [ ] 浮点比较用 `==`（改 abs(diff) < eps）；聚合前的分组键有 NaN 被静默丢弃（dropna 默认行为）；
- [ ] 时间列时区/格式混读（字符串排序 vs 真时间排序）；中文列名/路径在 Windows 下的编码（读写显式 encoding='utf-8'）；
- [ ] 循环里反复 append DataFrame / 全量重算（性能问题在数据量大时会翻车，提前查）。

## D. 凭证核对

- [ ] RESULTS.md 末尾有 `<!-- AUDIT_OK source=results.json rechecked_at=... -->`（无硬约束题标注 n_constraints=0 + 合理性自检说明）；
- [ ] `validate_capability()` 存在且运行通过（CAPABILITY_CHECKLIST 逐条 falsifiable_check 翻译成断言，断言不过就 raise）。

## S 区段 — 统计/实证类补充

- [ ] 样本量与检验功效：n 与结论强度匹配，不给 n=8 的组下强结论；
- [ ] 显著性表述与检验类型匹配（双侧 p 值、多重比较校正）；置信区间方法与分布假设一致；
- [ ] 相关 ≠ 因果：结论句里因果措辞有对应设计支撑（对照/随机化/工具变量），否则降级为"关联"。

## G 区段 — 图论/网络类补充

- [ ] 图的构建正确：有向/无向、连通性假设与题面一致；孤立点/自环处理已声明；
- [ ] 路径类问题：起点终点编号换算（题面 1-based vs 代码 0-based）核对；
- [ ] 最短路径/流结果做抽检：手工验证 2~3 条小规模实例（可用 networkx 对拍）。


---

## modex-3 增补块（2026-09-10 同源对照吸收）

> 来源：Modex v3 技能包 comp-code/references/checks/sanity_check.md（溯源见 skills/shared-scripts/UPSTREAM.md）。
> 以下为本仓原版未覆盖的检查条目与可执行代码模板；条目与本仓上方重叠时，以本仓上方（含 validate_capability / AUDIT_OK 契约衔接）为准。

## 第一步：自动化 sanity check

跑下面这个脚本（先跑脚本, 不依赖人工判断）：

```python
# code/sanity_check.py — 自动化结果验证
import json, os, sys, re

# 读取所有结果 JSON
results = {}
for f in sorted(os.listdir('figures')):
    if f.endswith('_results.json') or f == 'all_results.json':
        with open(f'figures/{f}', 'r', encoding='utf-8') as fh:
            results[f] = json.load(fh)

errors = []
warnings = []
suspicious = []  # ⛔ 可疑的"太完美"结果

def check_value(name, val, context=""):
    """通用数值检查"""
    if val is None:
        errors.append(f"❌ {name} 为 None")
    elif isinstance(val, float):
        import math
        if math.isnan(val):
            errors.append(f"❌ {name} 为 NaN")
        elif math.isinf(val):
            errors.append(f"❌ {name} 为 Inf")
        elif abs(val) > 1e15:
            warnings.append(f"⚠ {name} = {val}, 数值异常大")

def check_unrealistic(name, val):
    """⛔ 标记可能不合理的数值"""
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        return
    # Match the metric field, not a substring such as "acc" in acceleration.
    key = re.sub(r'\[\d+\]', '', name.rsplit('.', 1)[-1]).lower()
    # R² / accuracy / precision / recall / f1 / auc：归一化指标（>0.99 标记）
    if key in {'r2', 'r_squared', 'r_score'}:
        if val < 0.5:
            warnings.append(f"WARN {name} = {val:.4f}: low R2, investigate prediction quality; not an invalid number")
        elif val > 1 + 1e-12:
            errors.append(f"FAIL {name}: standard R2 cannot exceed 1")
    elif key in {'accuracy', 'acc', 'precision', 'recall', 'f1', 'auc'}:
        if not 0 <= val <= 1:
            errors.append(f"FAIL {name}: probability metric outside [0,1]; check units")
        elif val > 0.99:
            suspicious.append(f"🚩 {name} = {val:.4f}（>0.99）, 请确认是否过拟合")
    # RMSE / MAE / MSE / Loss
    if key in {'rmse', 'mae', 'mse'}:
        if val == 0:
            suspicious.append(f"🚩 {name} = 0 完美误差, 请确认训练/测试是否分开")
        elif val < 0:
            errors.append(f"❌ {name} = {val} 误差负值")
    # 提升百分比
    if any(w in key for w in ['improvement', 'speedup', 'gain', '提升', '改进']):
        if val > 1:
            suspicious.append(f"🚩 {name} = {val:.2f}（提升 {val*100:.0f}%）, 请结合题目确认")
    # p-value
    if key in {'p_value', 'pvalue', 'p值'}:
        if val == 0:
            warnings.append(f"WARN {name} = 0: check floating-point underflow; report significance without claiming exact zero")
        elif val > 1 or val < 0:
            errors.append(f"FAIL {name}: p value outside [0,1]")

def walk_check(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk_check(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_check(v, f"{path}[{i}]")
    elif isinstance(obj, (int, float)):
        check_value(path, obj)
        check_unrealistic(path, obj)

for fname, data in results.items():
    walk_check(data, fname)

for e in errors[:5]:
    print(e)
for w in warnings[:5]:
    print(w)
for s in suspicious[:5]:
    print(s)
if not errors and not warnings and not suspicious:
    print("✅ 所有数值通过 sanity check")
elif errors:
    print(f"\n共 {len(errors)} 个错误, {len(warnings)} 个警告, {len(suspicious)} 个可疑点 — 必须修复错误后再继续")
    sys.exit(1)
elif suspicious:
    print(f"\n共 {len(suspicious)} 个可疑的'完美'结果 — ⛔ 必须逐条确认：")
    print("  1. 确认训练集/测试集没有重叠？（过拟合或数据泄漏）")
    print("  2. 确认数据规模合理？（样本量 < 100 时 R² > 0.95 可能过拟合）")
    print("  3. 确认模型没有直接看到标签？（比如回归中自变量包含因变量的函数）")
    print("  4. 如果确实合理（物理仿真、确定性问题）, 在 RESULTS.md 中说明原因")
```

## 第二、三步：跨问题比较先核对适用条件

先逐项核对目标的定义、单位、输入与场景是否可比，不能从“问题编号更大”推断结果必须改善。

只有目标相同、可行域有可验证的包含关系、且比较的是已认证的最优值时，才能声称相应的非严格单调关系；即使严格包含，也不保证严格改善。约束更紧可能使最小化目标不变或变大，新增资源可能完全不影响最优解，这些均不是程序错误。

启发式结果不适用最优值的单调性定理。可将前一问题的解代入当前问题独立验证：若确实可行且目标更好，它是已知候选，可在预算内作 warm start；不能因此直接修改约束、伪造数值或无上限重跑。

跨问题输出相同，只核对输入来源、实际执行及是否错误复用了同一对象/缓存。不要求各问、各算例四舍五入后的指标互不相同。发现真实依赖遗漏才修改代码，不能为了“递进感”加入未被题目要求的目标项。

## 第四步：物理合理性原则

**核心原则**：物理/业务约束 > 数据忠实度 > 计算正确性

代码没有 bug、数据是题目给的 ≠ 结果就是对的。每个子问题跑完后必须问自己：
**"我的结果在题目描述的物理世界中是否可能发生？"**

⛔ **触发条件（同时满足才修正, 防止误杀）**：
1. 计算结果超出了题目明确给定的物理边界（白纸黑字写的, 不是你猜的）
2. 超出已声明的数值容差；容差必须有依据，不为通过临时放宽
3. 记录位置与观测值并诊断原因；原因未明时也不能把真实违例标为通过

⛔ **不触发的情况（保持原始结果）**：
- 结果"看起来大"但题目没给明确上限 → 不修正
- 结果在边界附近（如 59mm vs 60mm 上限）→ 不修正, 可能是正常极端工况
- 你不确定约束是否适用 → 不修正, 在论文中讨论

⛔ **按题型的红旗信号**：

| 题型 | 红旗信号 | 可能原因 |
|------|---------|---------|
| 物理/工程 | 结果超出题目给定的物理极限 | 数据漂移/截断/模型缺约束 |
| 优化 | 最优解违反约束条件 | 约束未正确加入求解器 |
| 预测 | 预测值超出历史数据范围 5 倍以上 | 模型外推发散/趋势项过强 |
| 预测 | 远期预测单调发散（不收敛不震荡） | 模型不稳定/缺阻尼项 |
| 评价 | 权重之和超出模型声明的归一化容差 | 核对数值精度与归一化步骤 |
| 评价 | 所有方案得分差异 < 1% | 可能真实相近，不强迫拉大差异 |
| 评价 | 排名与题目暗示的常识严重矛盾 | 正负向指标处理反了 |
| 图论 | 非负边权场景路径长度/成本为负 | 核对权重与算法；允许负权的模型不能套此项 |
| 图论 | 流量不守恒（流入≠流出） | 模型遗漏节点或边 |
| 统计 | 回归系数方向与所有文献相反 | 变量编码错误/共线性 |
| 动力学 | 状态变量单调增长不收敛 | 开环积分漂移/缺反馈 |

⛔ **修正流程（触发后）**：
1. 记录原始结果（不删除, 论文中需要对比说明）
2. 分析超出原因：数据截断？测量误差？净偏差累积？边界效应？模型假设不完整？
3. 定位实现、输入读取或模型原因后修相应范围，不凭空去漂移、加阻尼或改原始观测
4. 重新计算, 验证修正后结果在约束内
5. 在 RESULTS.md 中写明：原始结果 → 为什么不合理 → 修正方法 → 修正后结果
6. 正式结果使用已验证的修正版本；原始结果单独保存并标明未通过的原因，便于追溯，不能伪装成最终有效结果。

⛔ **绝对禁止的行为**：发现结果超出物理约束后"解释原因"但继续使用超出的结果。
解释原因 ≠ 处理完毕。发现超出 → 必须修正 → 用修正后的值。

## 第五步：9 问背景审查（最关键）

读取 PROBLEM_ANALYSIS.md（或 TOPIC_PLAN.md）和 RESULTS.md, **结合本题的具体背景**逐项自检。

⛔ **审查时必须同时对照三个来源**：
1. 赛题原文（PROBLEM_ANALYSIS.md / user_data/*_extracted.txt）— 题目给的约束和背景
2. 建模报告（MODELING_REPORT.md）— 之前设计的模型和预期行为
3. 实际结果（figures/all_results.json）— 代码跑出来的数字

```
=== 合理性审查（结合题目背景）===

Q1. [数值量级] 每个结果的数值量级是否符合题目实际？
   举例：
   - 一个城市的年用电量应该是几亿度（10^8-10^9）, 不是几千度
   - 一辆货车的载重应该是几吨到几十吨, 不是几克或几千吨
   - 一个班级的学生数应该是 30-50 人, 不是 3 人或 500 人
   - 一天的时间应该是 24 小时内, 不是 200 小时

Q2. [符号方向] 结果的正负/大小方向是否符合直觉？
   举例：
   - 资源变化是否满足同目标、可比场景与可行域包含的前提？没有前提不能强求改善
   - 距离越近应该运输成本越低, 不是越高
   - 产品价格上升应该让需求下降（正常商品）

Q3. [约束边界] 结果是否在题目给定的物理/业务边界内？
   ⛔⛔⛔ Q3 判定规则（硬性, 不可变通）：
   - 结果在边界内 → ✅
   - 结果超出边界 → ❌（无论你是否"已讨论"、"已解释原因"）
   - "已在报告中讨论" ≠ ✅, 仍然是 ❌
   - "数学解超出物理范围" = ❌, 不是 ✅
   - 只要有任何一个结果超出题目明确给定的边界 → 整个 Q3 = ❌
   - Q3 = ❌ 时在共享返修预算内修真实原因、重验受影响算例；预算耗尽报未完成，不无限重算或随意加约束
   - ⛔ 禁止：标 ❌ 后写"但这是合理的因为XXX"然后继续 → 这不是通过

Q4. [结果分布] 多个结果之间的比例/差异是否合理？

Q5. [与赛题相同的场景数据] 如果赛题给了数据样本, 我的结果是否与之量级一致？

Q6. [物理/业务常识] 是否违反了常识性的物理/业务规律？
   - 物理：能量守恒、动量守恒、质量守恒
   - 经济：帕累托改进、边际递减
   - 统计：大数定律、中心极限

Q7. [子问题关系] 输入、目标与可行域是否可比？
   - 条件符合时只核对非严格单调关系；最优值可以不变
   - 更换策略、不同算例或启发式输出不保证改善，不因此强制返工

Q8. [灵敏度合理] 灵敏度分析显示的敏感性是否合理？
   - 关键参数应该敏感
   - 无关参数应该不敏感

Q9. [与建模报告一致] 代码实现是否忠实于 MODELING_REPORT.md？（⛔ 最关键的一条）

   自动化对照：
   ```bash
   echo "--- 算法对照 ---"
   echo "建模报告承诺的算法："
   grep -i '算法\|方法\|求解.*法\|采用.*法' MODELING_REPORT.md | head -10
   echo "代码中实际使用的算法/库："
   grep -rh 'from\|import\|minimize\|solve_ivp\|linprog\|genetic\|simulated' code/*.py 2>/dev/null | sort -u | head -15
   echo "--- 约束对照 ---"
   echo "建模报告列出的约束数量："
   grep -c '≤\|≥\|约束\|s\.t\.' MODELING_REPORT.md
   echo "代码中实现的约束数量："
   grep -rch 'constraint\|bounds\|<=\|>=' code/*.py 2>/dev/null | paste -sd+ | bc 2>/dev/null || echo "(手动检查)"
   echo "--- 参数对照 ---"
   echo "建模报告定义的关键参数："
   grep -oE '[A-Za-z_]+\s*[=:]\s*[0-9]+\.?[0-9]*' MODELING_REPORT.md | head -10
   echo "代码中的对应参数值："
   grep -rh '^[A-Z_]*\s*=' code/*.py 2>/dev/null | head -10
   ```

   ⛔ Q9 判定规则：
   - 算法被降级（如遗传算法→贪心）→ ❌
   - 约束被省略（建模报告有但代码没实现）→ ❌
   - 参数值不一致（建模报告 L=2.20 但代码 L=1.65）→ ❌
   - 以上任何一条 = ❌ = 必须修改代码重跑
```

对每个问题必须明确回答 ✅（通过）、⚠️（需说明）、❌（有问题）。

## 第六步：常见编程 Bug 排查（按题型选做）

```
=== 求解器/算法常见坑 ===
B1. [最大化vs最小化] scipy.optimize.minimize 是最小化器 — 如果要最大化, 目标函数是否取了负号？
B2. [初始值敏感] 优化结果是否依赖初始值？换一组初始值结果是否一致？（局部最优陷阱）
B3. [约束写反] 不等式约束方向是否正确？scipy 的 'ineq' 约束要求 f(x) >= 0
B4. [整数松弛] 用连续优化器解整数规划后, 是否做了取整？取整后是否仍然可行？
B5. [索引越界] 数组索引是否从 0 开始？矩阵维度是否匹配？
B6. [数据泄露] 测试集的数据是否参与了训练/归一化？（StandardScaler 必须只 fit 训练集）
B7. [随机种子] 是否设了 random seed？不同运行结果是否可复现？

=== 数据处理常见坑 ===
D1. [缺失值] 是否处理了 NaN/空值？pandas 的 mean() 默认跳过 NaN 但 numpy 不会
D2. [类型错误] 字符串列是否被当成数值参与了计算？（pandas 读 CSV 可能把数字列读成 str）
D3. [归一化时机] 归一化是在 train/test split 之前还是之后？（应该在之后, 只用训练集的统计量）
D4. [时间序列顺序] 时间序列数据是否按时间排序？是否有重复时间戳？
D5. [编码问题] 中文 CSV 是否用了正确的编码读取？（gbk/utf-8/gb2312）

=== 模型选择常见坑 ===
M1. [线性假设] 用线性回归拟合明显非线性的数据？（看残差图是否有弯曲模式）
M2. [样本不平衡] 分类问题中各类样本量是否严重不平衡？是否用了 class_weight 或过采样？
M3. [特征缩放] SVM/KNN/神经网络等距离敏感模型是否做了特征缩放？
M4. [时序交叉验证] 时间序列是否用了普通 k-fold？（应该用 TimeSeriesSplit）
M5. [多重比较] 做了多次假设检验是否做了 Bonferroni 校正？
```

## ⛔ 强制修复原则（不可跳过）

**检测到问题 = 必须修复。解释原因 ≠ 处理完毕。本步骤不允许带着已知问题输出结果。**

无论是物理合理性检查、9 问背景审查、还是上面的自检项, 只要发现 ❌：
1. 必须立即修改代码 — 不能写"发现XXX问题, 但由于时间/复杂度原因暂不处理"
2. 必须重新运行 — 修改后必须重跑代码验证修正有效, 不能只改代码不跑
3. 必须验证修正后结果合理 — 修正后的结果必须通过同样的检查
4. 必须在 RESULTS.md 中记录 — 写明"原始结果X → 发现问题Y → 修正方法Z → 修正后结果W"

## 第七步：逻辑体检（⛔ 补"数值合法但逻辑错"的盲区，两个确定性脚本，零额度必跑）

前六步查的是"数值越界/物理不合理/内部自洽"，但查不了**方向反、外推吹过头、真实变量漏用、同一项算两次、跨子问题结论矛盾**这类"数字都合法、逻辑却错"的问题。这一步用两个确定性脚本兜底（不调模型、几乎零额度）。

**A. 截断/删失方向自检（先自答，防方向反）：** 凡涉及传感器封顶/删失/反解取界，出结果前**必须写一行**并代入数值验证不等号：
```
观测值 ≤ 或 ≥ 真实值？  →  反算出的量是【上界】还是【下界】？
例：传感器右截断(封顶50) → 观测浓度 ≤ 真实浓度 → 反算除尘效率是【上界】(不是下界)
```
写反 = 概念硬错，会系统性高估/低估，必须改。建模阶段的 `LOGIC_CONTRACT_MACHINE.bounds` 已声明方向，这里核对代码实现与声明是否一致。

**A+. 方向探针（⛔ 让数据替你验方向，比自答更硬）：** 对每条 `bounds` 声明，写几行代码做**扰动重算**——把被截断/封顶的输入**朝真值方向**推一点（如封顶值 +δ），重算该量，记下变化符号，写进 `figures/all_results.json`：
```python
# 例：封顶浓度朝真值方向 +δ 后重算效率，记符号
eta0 = compute_eta(cout_obs)
eta1 = compute_eta(cout_obs + delta)     # delta>0: 朝真值方向(封顶=真值被低估)
probe_sign = 1 if eta1 > eta0 else (-1 if eta1 < eta0 else 0)
results.setdefault("logic_probes", {}).setdefault("bounds", []).append(
    {"quantity": "eta", "claim": "upper", "probe_delta_sign": probe_sign})
```
> `logic_audit.py` 会核：声明 `upper` 则该量应随之**减小**(sign<0)、`lower` 应**增大**(sign>0)，矛盾即 FAIL。**这一步不靠判断、纯数值证伪**，是抓"方向反"最硬的一道。单调方向同理可填 `logic_probes.monotonic`（`{"more","then","observed_sign","expect_sign"}`，给了 expect_sign 才硬判）。填不了就不填（logic_audit 无探针时软跳过）。

**B. 跑逻辑体检脚本（退出码 1 必修，2 跳过不阻塞）：**
```bash
# 逻辑体检：外推报警 + 特征完整性 + 重复计量（读建模的 LOGIC_CONTRACT + 赛题分析的 DATA_FACTS）
python3 _utils/logic_audit.py --stage code 2>&1 | tee -a AUDIT_REPORT.md
LA=${PIPESTATUS[0]}   # 0=过 1=确凿逻辑错(必修) 2=无合同可查(跳过)
# ⛔ 必须用 ${PIPESTATUS[0]} 而非 $? —— 有 `| tee` 时 $? 取的是 tee 的退出码(恒0)，
#   会把 logic_audit 的 FAIL(1) 吞掉，导致下面的 if 永不成立、逻辑闸形同虚设。

# 跨子问题一致性终检：把各问结论摆一起对撞（读建模的 CROSS_PROBLEM_LEDGER）
python3 _utils/cross_problem_check.py 2>&1 | tee -a AUDIT_REPORT.md
CP=${PIPESTATUS[0]}   # 0=过 1=检出跨问矛盾(必修) 2=无登记(跳过)（同样必须用 PIPESTATUS，别用 $?）

if [ "$LA" = "1" ] || [ "$CP" = "1" ]; then
    echo "❌ 逻辑体检/跨问终检发现必修问题 — 按上面明细回改 code/模型，重跑至通过"
fi
```
> - 退出码 **2 是正常的软跳过**（建模阶段没填逻辑合同/跨问登记时），不阻塞、不算失败。
> - 退出码 **1 必修**：漏用的真实变量补进模型、重复计入的项去掉一次、跨问矛盾要么把上游结论纳入下游约束、要么修正矛盾结论。
> - ⛔ 这两个脚本**只在建模阶段填了合同/台账/登记时才真正发力**；填得越全，拦得越准。它们**抓不到方向反**（代码用的是建模那个可能已想反的脑子）——方向反主要靠上面 A 的自答 + 第二期的跨模型对抗复查兜。
