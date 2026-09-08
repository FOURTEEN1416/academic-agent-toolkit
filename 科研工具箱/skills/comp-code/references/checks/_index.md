# 自检总索引（checks/_index.md）

> 每个子问题代码跑完、结果落盘（results.json + RESULTS.md）后、写稿/画图之前，立即执行本自检链。
> 仅第 1 问开始前完整读本索引一次，后续问题按此流程执行即可。
> 技术细节的判定标准一律指向 `skills/_utils/error_prevention.md` 对应章节（单一真源，本目录不复制其内容）。

## 三步流程

**第 1 步 · 必读（所有题型）**

| 文件 | 用途 |
|---|---|
| [consistency.md](consistency.md) | 建模-代码契约：符号/参数/单位一致性 + METHOD_CLAIMS 对照 + claim_code_check 静态扫描 |
| [sanity_check.md](sanity_check.md) | 自动数值审查 + 9 问背景审查 + 编程 Bug 排查（末尾含统计/实证 S 区段、图论 G 区段） |

**第 2 步 · 按本问题型选读一个分类自检文件**

| 本问类型 | 读哪个 | 侧重 |
|---|---|---|
| 优化类（调度/选址/路径/分配/规划/求最优值） | [optimization.md](optimization.md) | 约束闭环 + 基线同审 + 求解分层验证 + 结构性验证 |
| 预测类（时间序列/回归/分类） | [prediction.md](prediction.md) | 泄漏检查 + 基线对比 + 时序交叉验证 + 区间校准 |
| 评价类（TOPSIS/AHP/熵权法/排名打分） | [evaluation.md](evaluation.md) | 权重来源可复现 + AHP 一致性比率 + 灵敏度 + 序保持 |
| 物理/几何（碰撞检测/动力学/ODE/SAT） | [physical.md](physical.md) | 量纲 + 守恒律 + 步长收敛 + 碰撞误检率 |
| 统计/实证/图论 | sanity_check.md 末尾 S/G 区段 | — |

**第 3 步 · 产出自检报告**

- 写 `_tmp/problem_N_check.md`，每条结论标 ✅（通过）/ ⚠️（存疑，需说明）/ ❌（不通过，必须修复后重跑）；
- 修复任何 ❌ 后必须**重新运行本问全部脚本**并重跑对应自检，禁止只改文档不改代码；
- 全部 ✅/⚠️ 后才允许进入写稿与画图步骤。

## 硬凭证（缺一即该问不通过）

| 凭证 | 写在哪 | 来源机制 |
|---|---|---|
| `<!-- AUDIT_OK source=results.json rechecked_at=<timestamp> n_constraints=K -->` | RESULTS.md 末尾 | constraint_audit.py 约束闭环（无硬约束题：`n_constraints=0` + 一句话说明已跑合理性自检） |
| `validate_capability()` 全部断言通过 | code/problem_N.py 末尾（代码内） | CAPABILITY_CHECKLIST.json 各能力 falsifiable_check → 可证伪断言 |
| `<!-- METHOD_CHECK static_cc=<0/1> n_claims=K n_implemented=M fast_mode=<0/1> -->` | RESULTS.md 末尾 | claim_code_check.py 声称↔代码静态扫描 |

## 输出纪律（所有自检脚本通用）

自检/审计脚本遵守「规则 B」：Python 读全精度重算，但**只 print 结论**（PASS/FAIL、n_violations、max_error、最多 5 条越界定位）。禁止 print 整个数组/字典/DataFrame。
