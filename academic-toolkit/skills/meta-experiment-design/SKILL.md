---
name: meta-experiment-design
description: "Use when planning product experiments: testable hypotheses, sample size, test prioritization, defensible evaluation."
---

# Experiment Designer

Design, prioritize, and evaluate product experiments with clear hypotheses and defensible decisions.

## When To Use

Use this skill for:
- A/B and multivariate experiment planning
- Hypothesis writing and success criteria definition
- Sample size and minimum detectable effect planning
- Experiment prioritization with ICE scoring
- Reading statistical output for product decisions

## Core Workflow

1. Write hypothesis in If/Then/Because format
- If we change `[intervention]`
- Then `[metric]` will change by `[expected direction/magnitude]`
- Because `[behavioral mechanism]`

2. Define metrics before running test
- Primary metric: single decision metric
- Guardrail metrics: quality/risk protection
- Secondary metrics: diagnostics only

3. Estimate sample size
- Baseline conversion or baseline mean
- Minimum detectable effect (MDE)
- Significance level (alpha) and power

Use:
脚本 `scripts/sample_size_calculator.py` 未随本仓集成（已入 asset_gap_register.json），按公式手工估算：
两比例检验每变体样本量 **n ≈ (z_{α/2}+z_β)² · [p₁(1−p₁)+p₂(1−p₂)] / (p₂−p₁)²**。
例（--baseline-rate 0.12 --mde 0.02 --mde-type absolute，即 p₁=0.12、p₂=0.14，α=0.05、power=0.8）：(1.96+0.84)²=7.84，n ≈ 7.84 × (0.1056+0.1204) / 0.02² ≈ **4430/变体**。

4. Prioritize experiments with ICE
- Impact: potential upside
- Confidence: evidence quality
- Ease: cost/speed/complexity

ICE Score = (Impact * Confidence * Ease) / 10

5. Launch with stopping rules
- Decide fixed sample size or fixed duration in advance
- Avoid repeated peeking without proper method
- Monitor guardrails continuously

6. Interpret results
- Statistical significance is not business significance
- Compare point estimate + confidence interval to decision threshold
- Investigate novelty effects and segment heterogeneity

## Hypothesis Quality Checklist

- [ ] Contains explicit intervention and audience
- [ ] Specifies measurable metric change
- [ ] States plausible causal reason
- [ ] Includes expected minimum effect
- [ ] Defines failure condition

## Common Experiment Pitfalls

- Underpowered tests leading to false negatives
- Running too many simultaneous changes without isolation
- Changing targeting or implementation mid-test
- Stopping early on random spikes
- Ignoring sample ratio mismatch and instrumentation drift
- Declaring success from p-value without effect-size context

## Statistical Interpretation Guardrails

- p-value < alpha indicates evidence against null, not guaranteed truth.
- Confidence interval crossing zero/no-effect means uncertain directional claim.
- Wide intervals imply low precision even when significant.
- Use practical significance thresholds tied to business impact.

See:
- `references/experiment-playbook.md`
- `references/statistics-reference.md`

## Tooling

### `scripts/sample_size_calculator.py`

> **脚本未随本仓集成**（已入 asset_gap_register.json）；需要时按下列公式手工计算。

Computes required sample size (per variant and total) from:
- baseline rate
- MDE (absolute or relative)
- significance level (alpha)
- statistical power

Example（p₁=0.10、绝对 MDE 0.015 即 p₂=0.115、α=0.05、power=0.8，(1.96+0.84)²=7.84）：
n ≈ 7.84 × (0.10×0.90 + 0.115×0.885) / 0.015² ≈ 7.84 × 0.1918 / 0.000225 ≈ **6680/变体**（双变体合计约 13360）。
