# FBA-Agent — Skills (Constraint-Based Metabolic Modelling)

**Reusable skill modules for constraint-based metabolic modelling and flux analysis.**

> Naming note: this suite focuses on genome-scale metabolic models, COBRApy, FBA,
> pFBA, FVA, and in-silico perturbation screens. It is not a full experimental
> `13C-MFA` / isotope-tracing flux-inference system.

## Pipeline Overview

```
BIGG model ID / Custom reaction list
         │
         ▼
  gsmm-builder ──► models/<Model>.json  (COBRApy model)
         │
         ▼
  gsmm-validator ──► mass balance check, growth rate validation
         │
         ▼
  fba-simulator ──► simulations/fba_fluxes.csv  +  gene_essentiality.csv
    [FBA → pFBA → FVA → knockout screen]
         │
         ▼
  flux-analyzer ──► analysis/phase_plane.png  +  essentiality_heatmap.png
         │
         ▼
  → metabolic maps, yield predictions, publication figures
```

## Skills

| Skill | Description |
|---|---|
| [`gsmm-builder`](gsmm-builder/) | 加载 BIGG 基因组规模代谢模型或从零构建自定义代谢网络 |
| [`gsmm-validator`](gsmm-validator/) | 校验代谢模型：质量守恒、电荷守恒、生物量正生长率、死端代谢物检测 |
| [`fba-simulator`](fba-simulator/) | 运行 FBA / pFBA / FVA / 基因敲除筛选，计算通量分布和生长速率 |
| [`flux-analyzer`](flux-analyzer/) | 分析通量分布：基因必需性、表型相图、通量采样、代谢工程靶点识别 |
| [`mfa-pipeline-orchestrator`](mfa-pipeline-orchestrator/) | 编排从模型加载到代谢表型预测的完整流水线 |
| [`metabolic-study-planner`](metabolic-study-planner/) | 在没有具体 idea 时选择模型、条件、扰动、指标和论文级研究计划 |

## Analogy with ColliderAgent

| ColliderAgent (粒子物理) | FBA-Agent (约束代谢建模) | 对应关系 |
|---|---|---|
| LaTeX 拉氏量 | 化学计量矩阵 / 反应方程 | 网络的数学定义 |
| FeynRules `.fr` | COBRApy `Model` 对象 + JSON | 标准化模型格式 |
| MadGraph 蒙特卡洛 | Flux Balance Analysis (FBA) | 核心数学求解 |
| MadAnalysis 事件分析 | Flux Variability Analysis + 基因敲除 | 条件约束分析 |
| micrOmegas 暗物质观测量 | 理论最大产物产率、必需基因 | 关键可观测量 |
| 唯象流水线编排器 | mfa-pipeline-orchestrator | 全流程自动化 |

## Key Tools

| Tool | Purpose |
|------|---------|
| COBRApy | Core FBA solver and model I/O |
| BIGG Database | Standard genome-scale model repository |
| Escher | Metabolic map visualisation |
| Gurobi / GLPK | LP solver backend (Gurobi recommended for speed) |
