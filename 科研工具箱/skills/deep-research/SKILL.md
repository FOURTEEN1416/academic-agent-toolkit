---
name: deep-research
description: "深度调研（Deep Research for CUMCM）——赛题分析的顶层调研技能。比赛出题后 6 小时内快速吃透题目背景、数据来源、前沿方法、可用工具，为选题决策提供证据。"
---

# 深度调研（Deep Research for CUMCM）

## 定位
赛题分析的顶层调研技能。比赛出题后 6 小时内快速吃透题目背景、数据来源、前沿方法、可用工具，为选题决策提供证据。

## 依赖
- `paper-search` — ykdojo OpenAlex 论文搜索
- `sci-paper-lookup` — scientific-agent-skills 论文检索
- `sci-literature-review` — 系统性文献综述
- `paper-writing` 增强版— 调研结果输出
- `tools/arxiv_miner.py` — arXiv 批量抓取
- `data/search_links.md` — 常用搜索链接

## 比赛时间线（4 天 96h）

```
Day 1 (18:00→24:00)  ═══ 调研阶段 ═══
  18:00-19:00  🔍 读题 + deep-research 启动
  19:00-22:00  📚 大规模调研（论文/数据/方法）
  22:00-24:00  📊 选题决策 + 初步方案

Day 2-3  ═══ 建模求解 ═══
Day 4     ═══ 论文撰写 ═══
```

## 调研工作流

### Step 1: 读题解析
```
题目 → 提取关键词 → 识别题型(A/B/C/D/E/F) → 
定位学科方向 → 列出 5 个核心研究问题
```

### Step 2: 关键词升华
```
原始词 → 学术化
"交通流量" → "traffic flow prediction / traffic state estimation"
"碳排放" → "carbon emission / CO2 footprint / life cycle assessment"
"投资组合" → "portfolio optimization / asset allocation / risk parity"
```

### Step 3: 论文检索（3 条线并行）
| 渠道 | 用途 | 工具 |
|------|------|------|
| OpenAlex | 快速广撒网 | `paper-search` |
| arXiv | AI/ML 前沿方法 | `arxiv_miner.py` |
| CNKI/百度学术 | 中文文献 | `data/search_links.md` |

### Step 4: 方法速览
```
对每篇高相关论文：
  方法名 → 适用条件 → 优缺点 → 是否可用
输出：候选方法矩阵（3-5 个 candidate）
```

### Step 5: 选题报告
```
输出一份 2 页的调研结论：
  1. 选题建议（优先级排序）
  2. 数据来源（具体URL/API）
  3. 推荐方法（含参考文献）
  4. 风险提示（数据缺失/方法不适配）
```

## 调研产出格式
```markdown
## 选题调研报告

### 推荐选题：B 题（最优化类）
**理由**：数据公开完整、方法成熟、可解释性强

### 数据来源
| 数据 | 来源 | 格式 | 预估大小 |
|------|------|------|----------|
| 数据集1 | xxx | CSV | 10MB |

### 推荐方法（按优先级）
1. XGBoost + SHAP — 精度高可解释
   - 论文：xxx (2025)
   - 适用条件：特征<100 样本>1000
2. 神经网络 — 上限高
   - 论文：xxx (2024)
   - 适用条件：样本>50000

### 风险
- ⚠️ 数据可能 3 天后才更新 → 备选方案
```

## 关键原则
- **不花超过 6 小时调研**：比赛只有 96h
- **调研和建模并行**：有人继续调研，有人开始 baseline
- **不采纳无参考文献的方法**
- **数据可用性优先**：先确认数据能拿到再选方法

## 调用方式
```powershell
skill("deep-research")         # 本 skill
skill("paper-search")          # OpenAlex 搜索
skill("sci-paper-lookup")      # 论文检索
python tools/arxiv_miner.py    # arXiv 抓取
```
