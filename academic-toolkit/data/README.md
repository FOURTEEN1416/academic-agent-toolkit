# data/ 目录

存放科研/竞赛相关数据资产（**真源区**，随仓库分发）。

## 文件清单

| 文件 | 用途 | 消费者 |
|------|------|--------|
| `reference_models.json` | 6 类题型参考模型库 | 建模步选型参照（`comp-modeling` 技能；模板 `comp_cumcm` S3 资产指针） |
| `case_patterns.md` | 题型规律 + 常见国一方法库 | `tools/arxiv_miner.py` 离线兜底读取；`comp-model-innovation` / `comp-problem-analysis` 查重参照 |
| `historical_problems.json` | 历年真题索引与题型规律速查 | `comp_cumcm` step 1 赛题分析（assets「历年真题索引」） |
| `risk_alerts.md` | 20 个数模国赛常见坑 + 急救 SOP | 赛中现场急救（`comp_cumcm` step 1 资产「风险预警清单」） |
| `contest_lessons.json` | **CUMCM 实战经验库（机器可读）**：典型场景 / 决策依据 / 踩坑与避坑 / 交付清单 | `tools/contest_lessons_check.py`、`tests/test_contest_lessons.py`、写作与交付类步骤 |
| `contest_lessons.md` | **CUMCM 实战经验库（人读真源）**：与 JSON 双向锁死的决策叙述版 | 开赛前通读 / 赛后复盘（`comp_cumcm` step 1、step 14 资产） |
| `search_links.md` / `historical_papers.md` | 检索入口与优秀论文索引 | 文献类步骤 |

## 经验库的使用与维护

经验库的纪律是 **"每条经验必须绑定一个强制点"**：`contest_lessons.json` 里每条条目的
`enforced_by` 必须指向仓库内真实存在的文件（代码/规则/模板），机检逐条验证在位——
这是为了阻止经验退化成"应当建立 XXX"式的空话。

```bash
# 机检：schema + 强制点在位 + JSON↔MD 双向一致（--strict 有错即 exit 1）
python academic-toolkit/tools/contest_lessons_check.py --strict
# 随 pytest 护航
pytest academic-toolkit/tests/test_contest_lessons.py -q
```

维护要点：
- 新增/修改条目必须 **JSON 与 MD 同改**（ID 一一对应，机检会把不一致打成失败）；
- `stage` 取值只限 `meta.stages`，`topic` 只限 `meta.topics`，`severity` 只限 P0/P1/P2；
- 强制点过度集中（单文件覆盖 >60% 条目）时工具告警——说明经验其实只落在一个机制上。

## 维护说明

- 比赛结束后，可把新的真题与优秀论文登记进 `historical_papers.json`；
- 重跑 `python academic-toolkit/tools/data_init.py` 可重置（**注意：会覆盖本目录数据文件**，
  经验库 `contest_lessons.*` 属人工累积资产，重置前先备份）。
