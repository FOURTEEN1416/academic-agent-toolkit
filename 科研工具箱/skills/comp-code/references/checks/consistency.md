# consistency.md — 建模-代码契约自检

> 目标：确认「代码实现的就是建模报告说的那个模型」。数值合法 ≠ 实现正确，本文件查的是**翻译过程**有没有走样。
> 配套手册：`skills/_utils/error_prevention.md` 通用原则章 + 方法验证标准节。

## 1. 符号与参数一致性

- [ ] 代码中每个决策变量/常数与 MODELING_REPORT.md 的符号表一一对应（无"报告叫 x_i、代码叫 demand[i]"式的语义漂移）；
- [ ] 每个数值参数可追溯到来源（题面原文 / 题面附件数据 / 报告推导公式），代码里禁止出现无来源魔数；题面没给的参数若为假设值，必须在代码注释与 RESULTS.md 同时声明 `ASSUMED`；
- [ ] 单位一致：时间（s/min/h）、距离（m/km）、金额（元/万元）在数据读取、模型、结果输出三处统一；特别注意题面给"小时"数据但按"分钟"写约束这类错位。

## 2. 约束翻译完整性

- [ ] 把题面硬约束逐条编号（C1, C2, ...），在代码里找到每一条的落地位置（约束表达式 / 变量边界 / 数据预处理过滤），任何一条找不到落地位置即 ❌；
- [ ] 题面"至多/至少/不超过/恰好/相邻/连续"等措辞对应的方向（≤/≥/==）与代码一致；
- [ ] 隐含约束已显式化：非负性、整数性、容量下界为 0、时间窗先后顺序、互斥性——题面不写但物理上必须成立的约束，检查是否遗漏。

## 3. 方法声称 ↔ 代码 静态扫描（第 3 层，两模式都跑）

```bash
python _utils/claim_code_check.py 2>/dev/null || python skills/shared-scripts/claim_code_check.py
```

- 扫描 METHOD_CLAIMS 里每个方法必备 API 标记在 code/*.py 中的落点；
- 任何"声称用了 X 方法但代码无 X 调用痕迹"→ ❌，禁止改声称迁就代码（要改的是代码）；
- 静态扫不了的残余（如"某条约束进没进模型"）按 SKILL.md 第 4 层锚定式对账处理，严格模式下逐条核对并把结果写进 METHOD_CHECK 凭证。

## 4. 数据链一致性

- [ ] code 读的输入文件与 problem 题设/附件一致（文件名、sheet、列名），禁止引用不存在的列；
- [ ] results.json 的键与 RESULTS.md、后续画图脚本（paper-figure）引用的键一致；
- [ ] 中间产物（清洗后数据/预处理矩阵）与最终结果可互相推导，无"结果来自另一份没写盘的数据"的断裂。

## 输出

按 `_tmp/problem_N_check.md` 格式逐条 ✅/⚠️/❌；任何 ❌ 修复后必须重跑本问全部脚本。


---

## modex-3 增补块（2026-09-10 同源对照吸收）

> 来源：Modex v3 技能包 comp-code/references/checks/consistency.md（溯源见 skills/shared-scripts/UPSTREAM.md）。
> 以下为本仓原版未覆盖的检查条目与可执行代码模板；条目与本仓上方重叠时，以本仓上方（含 validate_capability / AUDIT_OK 契约衔接）为准。

**适用边界补充（原有清单与案例保留）**：方法/异常预案用于保持数学合同，不锁死
有依据的等价实现。已有等效验证函数可复用，不为函数名或文件位置重复写一套。
检验条件先核题设依据、单位、容差、对象和时间范围；错条件应修并留依据，不能改正确结果。
近似可通过误差界或小算例精确参考验证，不一律同时全量运行精确/近似两个版本。

**核心问题**：建模报告写了完整模型, 但代码实现时偷偷简化（用更简单的方法/忽略约束/降维）。
**核心问题**：题目给了具体数值约束（预算/时间/容量/数量等）, 但代码结果违反这些约束。

## 步骤 1：建模-代码契约对照

⛔ 从 MODELING_REPORT.md 提取以下"契约", 编码时必须逐条兑现：

⛔ 首先确认建模报告末尾的 5 项必备内容已经读过：
1. **结果约束清单** → 题设硬约束与已有数学证明用于 validate_constraints()；模型猜测的预期范围不能当硬边界
2. **预期行为描述** → 作为核对线索（稳态/瞬态/单调性），先验证适用条件，不能强行改变结果形状
3. **异常处理预案** → 遇到异常只能按预案操作, 不得自行发明修正方法
4. **方法唯一性声明** → 每个步骤只能用指定方法, 禁止替代
5. **验证检查点** → 代码跑完后逐项 pass/fail 检查

```bash
echo "=== 建模-代码一致性契约 ==="
echo "从 MODELING_REPORT.md 提取关键承诺："
echo ""

# 1. 算法承诺
echo "--- 算法承诺（建模报告说用什么算法, 代码就必须用什么算法）---"
grep -i '算法\|方法\|求解\|使用.*法\|采用' MODELING_REPORT.md | head -20

# 2. 约束承诺
echo ""
echo "--- 约束承诺（建模报告列的约束, 代码必须全部实现）---"
grep -i '约束\|s\.t\.\|subject to\|≤\|≥\|不超过\|至少\|必须满足' MODELING_REPORT.md | head -20

# 3. 物理参数承诺
echo ""
echo "--- 物理参数（建模报告定义的参数值, 代码必须一致）---"
grep -oE '[A-Za-z_]+\s*=\s*[0-9.]+' MODELING_REPORT.md | head -20

# 4. 结果预期范围
echo ""
echo "--- 结果预期范围表（代码跑完后必须对照验证）---"
sed -n '/结果预期范围/,/^##/p' MODELING_REPORT.md | head -20
```

⛔ **一致性规则（硬性, 不可变通）：**

1. **算法不能降级**：建模报告说"遗传算法", 代码不能偷偷换成"贪心"; 说"SAT碰撞检测"不能换成"中心距判断"
2. **约束不能遗漏**：建模报告列了 N 个约束, 代码必须实现 N 个（不能"为了简化"省掉几个）
3. **参数不能篡改**：建模报告定义 L=2.20m, 代码里不能写 L=1.65（用中间量代替）
4. **精度不能降低**：建模报告说"自适应步长 rtol=1e-8", 代码不能改成固定步长 dt=0.1

⛔ **如果编码时发现建模报告的方案确实无法实现**（如算法太慢/库不支持）, 必须：
- 在 RESULTS.md 中明确说明"建模报告方案X无法实现, 原因是Y, 替代方案是Z"
- 替代方案的精度不能比原方案差
- 不能静默替换——必须显式声明

## 步骤 2：题目数值约束对照

题目通常给具体数值约束（预算/时间/容量/数量等）, 跑完代码后要回到赛题验证：

```bash
echo "=== 题目约束对照 ==="
echo "--- 从赛题中提取数值约束 ---"
for src in PROBLEM_ANALYSIS.md user_data/*_extracted.txt; do
    [ -f "$src" ] || continue
    echo "来源: $src"
    grep -oE '(不超过|最多|至少|不低于|大于|小于|≤|≥|<|>|=)[^。, ,.\n]{0,40}[0-9]+[^。, ,.\n]*' "$src" 2>/dev/null | head -20
    echo ""
done
```

如果发现约束违反：
- ❌ 禁止做法：把违反的值手动改小/改大让报告看起来合规
- ✅ 正确做法：回去修改优化模型（加约束 / 改目标函数 / 调求解方法）重新跑

## 步骤 3：自动化约束验证（写进每个子问题代码末尾）

在每个子问题的代码末尾, **必须**加入以下约束验证代码块。这不是可选的"人工检查", 而是代码的一部分：

```python
# ===== ⛔ 约束验证（每个子问题必须有, 不可删除）=====
def validate_constraints(results: dict, constraints: dict) -> bool:
    """
    results: 计算结果字典, 如 {'gap': 0.081, 'velocity': -3.5}
    constraints: 约束字典, 如 {'gap': (0, 0.06, '悬浮间隙'), 'velocity': (-10, 10, '速度')}
                 格式: {key: (min_val, max_val, description)}
    返回: True=全部通过, False=有违反
    """
    violations = []
    for key, (lo, hi, desc) in constraints.items():
        val = results.get(key)
        if val is None:
            violations.append(f"FAIL {key}: required constrained result missing")
            continue
        import numpy as np
        try:
            vals = np.atleast_1d(val).ravel()
        except (TypeError, ValueError):
            violations.append(f"FAIL {key}: invalid numeric result array")
            continue
        if not vals.size or vals.dtype.kind not in 'fiu':
            violations.append(f"FAIL {key}: empty or non-numeric constrained result")
            continue
        for v in vals:
            if not np.isfinite(v) or v < lo or v > hi:
                violations.append(f"❌ {desc}: {v} 超出范围 [{lo}, {hi}]")

    if violations:
        print("\n" + "="*60)
        print("⛔⛔⛔ 约束验证失败 — 必须修正后才能继续")
        print("="*60)
        for v in violations[:5]:
            print(f"  {v}")
        print("\n修正要求：")
        print("  1. 分析超出原因（数据漂移/模型缺约束/边界效应）")
        print("  2. 核题设与检查条件；只补确实遗漏的机制，不自动加接触/饱和或 clip")
        print("  3. 重新计算, 确保结果在约束范围内")
        print("  4. 不要删除此检查代码！")
        print("="*60 + "\n")
        return False
    else:
        print("✅ 约束验证通过")
        return True

# ⛔ 使用方法（根据题目实际约束填写）：
# constraints = {
#     'gap': (0, 0.06, '悬浮间隙(m)'),           # 题目明确给出最大间隙0.06m
#     'displacement': (-0.06, 0.06, '位移(m)'),   # 物理约束
# }
# passed = validate_constraints(results_dict, constraints)
# if not passed:
#     raise ValueError("约束验证失败, 必须修正代码后重新运行")
```

⛔ **强制规则**：
1. 每个子问题的代码文件末尾必须有 `validate_constraints()` 调用
2. 硬约束必须溯源题目、已确认模型或数学证明；预期范围和经验猜测仅作提示，不能强制贴合
3. 验证失败不得保存为正式有效结果；保留独立失败诊断和前面已验证的算例检查点
4. 修正真实错误后只重算受影响部分；遵守本问预算与有限返修次数，不能无限等待通过

⛔ **AI 常见逃避行为（全部禁止）**：
- ❌ "数学上正确所以不需要约束" → 错！物理约束 > 数学正确性
- ❌ "这是题目数据的特性" → 错！数据有问题就修正数据处理方式
- 不适用接触/饱和约束的纯数学 ODE 不应强行添加；只实施题目与已确认模型要求的约束
- ❌ 删除或注释掉 validate_constraints 代码 → 严重违规
- ❌ 把约束范围改大让结果"通过" → 篡改约束, 严重违规

## 步骤 4：物理参数引用规则

代码中涉及碰撞检测、约束校验、目标函数计算时：

**必须使用 MODELING_REPORT.md 中定义的完整物理参数**（如板凳全长220cm、矩形宽30cm、车身长4.5m）, 
**禁止直接复用上游步骤为其他目的计算的中间量**（如孔中心距165cm、把手坐标间距、质心偏移量）作为物理实体的几何代理。

**强制规则**：
1. 每个约束判定函数的文档字符串中必须注明其引用的物理参数来源及数值
2. 物理参数必须在代码顶部统一定义（从 MODELING_REPORT.md 提取）, 不能散落在各处硬编码
3. 约束函数使用的参数值与 MODELING_REPORT.md 不一致时, 必须抛出异常而非静默执行
4. 禁止"就近取值"——不能因为某个中间变量数值接近就拿来当物理参数用

**典型错误示例**：
- 板凳碰撞检测用"孔中心距165cm"代替"板凳全长220cm" → 错误（少算了两端各27.5cm）
- 矩形放置约束用"中心坐标差"代替"边缘到边缘距离" → 错误（忽略了物体宽度）
- 车辆避障用"质心距离"代替"车身外轮廓最近点距离" → 错误（可能已经碰撞）

**正确做法**：

```python
# ⛔ 物理参数定义（来源：MODELING_REPORT.md 第X节）
BENCH_TOTAL_LENGTH = 2.20  # 板凳全长 220cm（题目原文）
BENCH_WIDTH = 0.30          # 板凳宽度 30cm（题目原文）

def check_collision(bench_a, bench_b):
    """检测两个板凳是否碰撞。

    物理参数来源：MODELING_REPORT.md 符号说明表
    - 板凳全长: BENCH_TOTAL_LENGTH = 2.20m
    - 板凳宽度: BENCH_WIDTH = 0.30m
    使用完整外轮廓（矩形四角）判断, 非中心点距离。
    """
    # 使用完整矩形碰撞检测（SAT 分离轴定理）
    ...
```

## 步骤 5：未经验证的几何简化

如果 MODELING_REPORT.md 中标注了"待验证近似"的简化假设, 代码中必须：
1. 同时实现精确版本和简化版本
2. 对比两者结果差异
3. 按题设精度、数值误差界和结论敏感性判断能否使用近似，不能通用写死 1~3% 的阈值
4. 在 RESULTS.md 中报告简化误差
