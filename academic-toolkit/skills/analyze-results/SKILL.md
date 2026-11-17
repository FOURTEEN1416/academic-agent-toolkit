---
name: analyze-results
description: Analyze ML experiment results, compute statistics, generate comparison tables and insights. Trigger: "analyze results", "compare"; interpret experimental data. Numeric cross-checks and tabulation only; for significance/CI/effect-size evidence bundles use results-analysis.
argument-hint: [results-path-or-description]
allowed-tools: Bash(*), Read, Grep, Glob, Write, Edit, Agent
---

# Analyze Experiment Results

Analyze: $ARGUMENTS

> **分工说明**：本技能 = **快速数值口径核对与表格化**（对比表、趋势观察、洞察草拟，不含严格统计保证）。**严格统计 + 证据包**（显著性/CI/效应量/图目录）走 `results-analysis`；学术论文级 APA 统计报告走 `data-statistics-report`。触发词相近时按此分工路由，不要用本技能替代论文级统计分析。

## Workflow

### Step 1: Locate Results
Find all relevant JSON/CSV result files:
- Check `figures/`, `results/`, or project-specific output directories
- Parse JSON results into structured data

### Step 2: Build Comparison Table
Organize results by:
- **Independent variables**: model type, hyperparameters, data config
- **Dependent variables**: primary metric (e.g., perplexity, accuracy, loss), secondary metrics
- **Delta vs baseline**: always compute relative improvement

### Step 3: Statistical Analysis
- If multiple seeds: report mean +/- std, check reproducibility
- If sweeping a parameter: identify trends (monotonic, U-shaped, plateau)
- Flag outliers or suspicious results

### Step 4: Generate Insights
For each finding, structure as:
1. **Observation**: what the data shows (with numbers)
2. **Interpretation**: why this might be happening
3. **Implication**: what this means for the research question
4. **Next step**: what experiment would test the interpretation

### Step 5: Update Documentation
If findings are significant:
- Propose updates to project notes or experiment reports
- Draft a concise finding statement (1-2 sentences)

## Output Format
Always include:
1. Raw data table
2. Key findings (numbered, concise)
3. Suggested next experiments (if any)
