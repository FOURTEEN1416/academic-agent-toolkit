# comp-prob-analysis P0 基准 — 赛题分析能力验收

## 任务描述

本基准测试评估数学建模竞赛智能体的**赛题分析能力**。智能体需要读取赛题描述和数据文件，输出结构化的赛题分析报告，包含子问题拆分、数据事实台账、能力清单和数据画像。

## 输入

- `fixtures/problem.md` — 合成微型赛题（城市共享单车调度优化，3 个子问题，含数据表格）
- `fixtures/data.csv` — 5 站点 × 7 天合成使用量数据

## 验收方式

```powershell
python evaluate.py <工作区路径>
```

工作区路径应包含智能体产出的以下文件：
- `PROBLEM_ANALYSIS.md` — 赛题分析报告
- `CAPABILITY_CHECKLIST.json` — 能力清单
- `DATA_FACTS.json` — 数据事实台账
- `DATA_PROFILE.json` — 数据画像

## 评分项与最低要求

| 评分项 | 最低要求 |
|--------|---------|
| 文件存在性 | 4 个产出文件全部存在 |
| 子问题数 | ≥ 3 个（正确识别 3 个子问题） |
| FIGURE_MANIFEST | 含 `<!-- BEGIN FIGURE_MANIFEST -->` / `<!-- END FIGURE_MANIFEST -->` 区块 |
| 能力清单 | ≥ 3 条能力项（每个子问题至少 1 条） |
| 数据事实 | DATA_FACTS.json 含 `variables` 字段 |
| 数据画像 | DATA_PROFILE.json 含 `_meta.n_files > 0` |
| 最小大小 | PROBLEM_ANALYSIS.md ≥ 1500 字节 |

所有检查项通过即 `all_pass: true`，评分脚本退出码 0。

## 许可

本基准数据为合成数据，仅供内部验收测试使用。