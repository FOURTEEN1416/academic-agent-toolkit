# evaluation.md — 评价类自检（TOPSIS/AHP/熵权法/排名打分）

> 目标：评价类结论的公信力全在"权重与过程可复现"。翻车模式：权重拍脑袋、正逆方向标错、序对扰动脆变。
> 配套手册：`skills/_utils/error_prevention.md` 四章（评价/决策类）。

## 1. 指标与方向

- [ ] 每个指标的效益/成本方向（正向/负向）显式声明并与题面语义一致（"故障率"是负向指标——方向标错是本题型第一大错）；
- [ ] 指标选取可追溯到题面要求或建模报告论证；增删指标对结论的影响已说明；
- [ ] 数据标准化方法声明（极差/z-score/向量归一化），且正向、负向指标的处理公式各自正确。

## 2. 权重可复现性（核心审查点）

- [ ] AHP：判断矩阵完整写入 RESULTS.md 或附录；一致性比率 CR < 0.1 有计算过程（λmax、CI、RI 查表值）；CR ≥ 0.1 必须回炉重标，禁止带病继续；
- [ ] 熵权法：数据矩阵非负处理后计算（log(0) 处理有声明）；权重不出现 0 或 1 的极端值（出现即检查数据退化）；
- [ ] 主客观组合权重：组合公式（乘积/线性加权）明确，线性组合系数有依据；
- [ ] 所有权重之和 = 1（数值容差内），权重向量写盘供灵敏度复用。

## 3. 计算正确性抽检

- [ ] TOPSIS：正/负理想解逐指标方向正确；贴近度 ∈ [0,1]；
- [ ] 用一个 2×3 手算小例（2 方案 3 指标）对拍程序结果（逐位一致）；
- [ ] 得分与排名同时输出且互相一致（排序稳定策略已定，无并列名次歧义未处理）。

## 4. 灵敏度与稳健性

- [ ] 权重 ±10%（或取两组合理对立权重）扰动，前 1~2 名不发生互易；发生互易时在 RESULTS.md 说明结论如何表述（"A、B 方案接近，对 X 权重敏感"）；
- [ ] 剔除单一指标的留一敏感性（可选，时间允许时做）：排名是否由单一指标主导。

## 5. 凭证

- [ ] validate_capability() 通过（如：排序结果对合法扰动保持、方向声明与代码实现一致）；
- [ ] RESULTS.md 有 AUDIT_OK 凭证（评价类通常无硬约束：n_constraints=0 + 合理性自检说明）。

## 输出

`_tmp/problem_N_check.md` 逐条 ✅/⚠️/❌；❌ 修复后重跑本问全部脚本。


---

## modex-3 增补块（2026-09-10 同源对照吸收）

> 来源：Modex v3 技能包 comp-code/references/checks/evaluation.md（溯源见 skills/shared-scripts/UPSTREAM.md）。
> 以下为本仓原版未覆盖的检查条目与可执行代码模板；条目与本仓上方重叠时，以本仓上方（含 validate_capability / AUDIT_OK 契约衔接）为准。

## 专项检查清单

```
E1. [权重归一] 需要归一化的权重是否满足模型约定的数值容差？检查有限值与方向，不统一容忍 0.01 的误差。
E2. [一致性] 使用 AHP 时按矩阵阶数、RI 来源与预设 CR 标准检查；1/2 阶矩阵不盲算 0/0。
E3. [排名稳定] 权重微调后排名是否稳定？
E4. [指标方向] 正向/负向指标是否正确处理？
E5. [得分区分度] 小差异或并列可能真实存在，结合测量误差与扰动解释，不为拉开得分改权重或数据。
E6. [常识对照] 排名是否与题目暗示的常识严重矛盾（正负向反了）？
```

## 红旗信号

| 现象 | 可能原因 |
|------|---------|
| 权重之和不满足声明的归一化容差 | 检查数值精度和归一化步骤 |
| 所有方案得分差异 < 1% | 可能真实接近；先核对指标方向，不自动返工 |
| 排名与题目暗示的常识严重矛盾 | 正负向指标处理反了 |
| AHP CR 不满足预设标准 | 如实报告判断不一致，重新征询或采用有依据的替代方案；不篡改判断值凑通过 |

## 权重稳定性验证

```python
# 幅度、次数按本题方案与计算预算预先确定；这是例子，不是所有题必跑 20 次。
import numpy as np
base_weights = np.array([0.3, 0.25, 0.2, 0.15, 0.1])
# compute_rank 返回固定方案顺序对应的名次，不能返回排序后的方案 ID。
# 并列名次按事先声明的方法处理。
base_rank = compute_rank(base_weights)
rng = np.random.default_rng(seed)
shaken_ranks = []
for trial in range(n_trials):
    perturb = 1 + rng.uniform(-perturb_fraction, perturb_fraction, len(base_weights))
    w = base_weights * perturb
    w /= w.sum()
    shaken_ranks.append(compute_rank(w))

# 计算每个方案的排名变化范围
for idx in range(num_alternatives):
    ranks_at_idx = [r[idx] for r in shaken_ranks]
    span = max(ranks_at_idx) - min(ranks_at_idx)
    print(f"方案 {idx} 排名变化范围 {span} 名")  # 现象不是自动 FAIL
```

## 必产数据

稳定性试验复用已有同设置运行，不在多个质检层各重做一遍。只输出真实使用的方法字段；
未用 AHP 不填 ahp_cr，未运行扰动试验不得写稳定性通过。样本数量不足或排名不稳定须说明适用范围。

```json
{
  "method": "TOPSIS / AHP / 熵权法",
  "weights": {"指标1": 0.3, "指标2": 0.25, ...},
  "weights_sum": 1.0,
  "ahp_cr": 0.08,
  "scores": {"方案A": 0.85, "方案B": 0.72, ...},
  "ranking": ["方案A", "方案B", "方案C"],
  "stability": {"weight_perturb_pct": 10, "max_rank_change": 1}
}
```
