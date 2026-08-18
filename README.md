# Academic Agent Toolkit

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Benchmarks: CC-BY-4.0](https://img.shields.io/badge/Benchmarks-CC--BY--4.0-green.svg)](./LICENSE)
[![OpenCode Desktop](https://img.shields.io/badge/Host-OpenCode%20Desktop-purple.svg)](https://opencode.ai)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-orange.svg)](https://www.python.org)
[![CUMCM 2026](https://img.shields.io/badge/CUMCM-2026%20Ready-red.svg)](https://www.mcm.edu.cn)
[![Skills](https://img.shields.io/badge/Skills-225%2B-brightgreen.svg)](./数学建模全流程套件/skills)

> An academic Agent toolkit for mathematical modeling competitions (CUMCM/MCM/ICM), academic papers, literature research, course materials, intellectual-property materials, and scientific figure production.
>
> OpenCode Desktop 为唯一正式支持宿主。

## Quick Start

```bash
# 1. Clone this repo
git clone https://github.com/<your-org>/academic-agent-toolkit.git
cd academic-agent-toolkit

# 2. Open in OpenCode Desktop
#    OpenCode Desktop → Open Project → 选择本目录

# 3. Describe your task
#    直接用中文或英文描述学术任务，系统自动路由到对应技能
```

OpenCode Desktop 是唯一正式支持宿主。不依赖 `opencode` CLI。

## What's Inside

### 10 Formal Capabilities (数学竞赛域)

| Capability | Description |
|-----------|-------------|
| `comp_cumcm_full_pipeline` | 完整 CUMCM 流程编排（14 步） |
| `comp_problem_analysis` | 赛题分析与子问题拆解 |
| `comp_modeling` | 数学建模与公式推导 |
| `comp_code_solve` | 编程实现与数值求解 |
| `comp_paper_zh` | 中文竞赛论文撰写（LaTeX） |
| `comp_review_visual` | 逻辑对抗复核与视觉审查 |
| `comp_final_audit` | 最终交付审计 |
| `comp_mcm_icm` | MCM/ICM 英文论文适配 |
| `comp_consistency` | 数字-代码-图表一致性校验 |
| `comp_literature` | 竞赛文献检索与引用核验 |

### 225+ Skills (跨 6 大领域)

- **数学建模竞赛** — CUMCM / MCM / ICM / APMCM 全流程
- **学术论文** — LaTeX/DOCX 写作、Nature 风格、引用管理
- **文献研究** — 文献综述、查新、idea 发现
- **课程材料** — 课程论文、开题报告、毕业设计
- **知识产权** — 专利交底书、软著申请
- **图表文档** — 科研插图、海报、PDF 处理

### 5 Anti-AI Detection Tools

| Tool | Description |
|------|-------------|
| `anti_ai_detector.py` | 8 维度 AI 检测（62 篇获奖论文基线校准） |
| `de_ai_writer.py` | 问题定位 + 改写方向建议（非机械替换） |
| `rewrite_quality_gate.py` | 4 维美学护栏（语义/语法/新痕迹/保护词） |
| `reference_paper_baseline.py` | 获奖论文定量特征解析器 |
| `ai_usage_declaration.py` | 2026 CUMCM AI 使用声明生成器 |

### Benchmark Suite

- **Public benchmarks** (CC-BY-4.0) — 合成样例题 + 评估器
- **Capability benchmarks** — 7 项 C1-C4 能力级评估
- **Cross-domain benchmarks** — 5 项跨域样例（学术/文献/课程/知产/文档）

## Architecture

```
数学建模全流程套件/
├── AGENTS.md              ← Agent 入口路由
├── skills/                ← 225+ 技能（每个一个 SKILL.md）
├── tools/                 ← 45+ 可执行工具脚本
├── engine/                ← 状态库 + 编排 + 质量门禁 + 审计
├── data/                  ← 参考数据
└── tests/                 ← 171+ 测试

benchmarks/
├── cumcm_public/          ← 公开基准集（合成题 + 评估器）
├── cumcm_private/         ← 私有基准集（真实题面，不随包分发）
└── six_domains_public/    ← 跨域基准样例
```

## Three-Layer Audit

| Layer | Mechanism | Records |
|-------|-----------|---------|
| **L1** | OpenCode plugin (runtime hook) | Every tool call, file edit, permission request |
| **L2** | WorkflowRunner | Step completion, checkpoint approval |
| **L3** | complete_step() evidence | Skill hash, declared commands, output manifest |

## Usage Examples

### 数模竞赛

```
用户: 我要参加 2026 年国赛，帮我分析 B 题
→ 自动路由到 comp-prob-analysis → comp-modeling → comp-code → comp-paper-zh
```

### 学术论文

```
用户: 写一篇关于深度强化学习的 Nature 风格论文
→ 自动路由到 paper-write-nature → paper-figure → paper-compile
```

### 文献综述

```
用户: 做一篇关于大语言模型安全性的文献综述
→ 自动路由到 literature-review → scholar_fetch → citation_checker
```

## License

| Component | License |
|-----------|---------|
| Core (skills/tools/engine) | MIT |
| Benchmarks (public) | CC-BY-4.0 |
| Private extensions | Not included |
| humanize_chinese (third-party) | MIT (voidborne-d/humanize-chinese) |

See [LICENSE](./LICENSE) for full text.

## Contributing

1. Fork the repo
2. Create a feature branch
3. Add your skill/tool following the SKILL.md format
4. Run tests: `python -m pytest tests/ -q`
5. Submit a PR

Skills must follow the input/output contract format in `AGENTS.md`. Each skill requires a `SKILL.md` with execution steps, quality rules, and evidence format.

## Acknowledgments

- Built with [OpenCode Desktop](https://opencode.ai)
- Anti-AI detection calibrated against 20 award-winning CUMCM papers
- humanize_chinese detection rules from [voidborne-d/humanize-chinese](https://github.com/voidborne-d/humanize-chinese) (MIT)
