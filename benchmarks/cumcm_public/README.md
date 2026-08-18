# CUMCM 公开基准集 (public benchmark)

小型、可再分发、本地可复现的数模竞赛验收样例题。作为 design §7 双层基准的**公开层**，
用于 CUMCM 能力正式验收（comp_problem_analysis / comp_modeling / comp_code_solve / comp_paper_zh 等）。

- 不含真实参赛题面、真实参赛数据或未授权参考论文。
- 每题均为合成题面，数据内嵌于 `data/`，可离线复现。
- 验收脚本：`tests/test_cumcm_benchmark.py`（消费本目录，输出四类指标报告）。

## 题目
| ID | 题型 | 主题 |
|----|------|------|
| P01 | Q5 工程 | 物流配送中心选址优化 |
| P02 | Q4 生物 | 传染病传播预测 (SIR) |
| P03 | Q1 经济 | 区域经济发展综合评价 |

## 两级结构（2026-08-17 合并）

本基准集含**两级验收**：

### 赛题级（P01-P03）
完整合成赛题，端到端验收聚合能力（comp_problem_analysis / comp_modeling / comp_code_solve / comp_paper_zh 等）。
每题含 `problem.md` / `delivery_contract.md` / `scoring_rubric.md` / `baseline/expected_outputs.md` / `data/`。

### 能力级（`_capability_level/`）
按能力拆分的微型验收（comp-prob-analysis / comp-literature / comp-modeling / comp-code / comp-paper-zh / comp-review），
各自含 `fixtures/` + `contract.json` + `evaluate.py` + `README.md`，对**单个步骤产物**做确定性评分：
```bash
python benchmarks/cumcm_public/_capability_level/<cap>/evaluate.py <工作区>
```
- comp-prob-analysis：子问题识别/FIGURE_MANIFEST/能力清单/DATA_FACTS/DATA_PROFILE
- comp-literature：引用真实性/BibTeX 交集（预置 2 条真实 arXiv 论文防编造）
- comp-modeling：子问题覆盖/能力认领/公式/符号表
- comp-code：代码/结果台账/predictions 非空（微型 STR 合成数据）
- comp-paper-zh：10 章节结构/摘要/参考文献/附录（兼容注释格式）
- comp-review：预埋 4 类缺陷检出率 ≥75%（防伪造审核基准）

## 验收流程
1. 对每题运行目标能力技能，产出交付合同要求的 artifacts。
2. `tests/test_cumcm_benchmark.py` 校验结构 + 运行 smoke 检查，输出四类指标初值。
3. 能力级验收：`_capability_level/<cap>/evaluate.py <工作区>` 确定性评分。
4. 专家量表对样例题评分（B4 校准），回填计划 §3 门槛。
