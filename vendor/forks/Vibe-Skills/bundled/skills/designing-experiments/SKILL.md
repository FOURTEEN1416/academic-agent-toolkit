---
name: designing-experiments
description: Design experiments and quasi-experiments before analysis. Use when choosing study design, treatment/control structure, outcomes, assumptions, validation plans after scientific experiment failure, or which of DiD, ITS, synthetic control, or regression discontinuity fits the research question. For fitting models or estimating effects on existing data, use performing-causal-analysis instead.
---

# Designing Experiments

Helps choose and specify a research design before data analysis starts. This skill owns study-design decisions: what is treated, what is compared, what outcome is measured, which assumptions are required, which validation or recovery experiment should follow a failed scientific experiment, and which design is defensible.

It does not fit causal models, estimate treatment effects, interpret fitted model output from existing data, or debug software/build failures.

## Decision Framework

1.  **Control Group?**
    *   **Yes**: Go to Step 2.
    *   **No**: Consider **Interrupted Time Series (ITS)**.

2.  **Unit Structure?**
    *   **Single Treated Unit**:
        *   With multiple controls: **Synthetic Control (SC)**.
        *   No controls: **ITS**.
    *   **Multiple Treated Units**:
        *   With control group: **Difference-in-Differences (DiD)**.

3.  **Time Structure?**
    *   **Panel Data** (Multiple units over time): Required for DiD and SC.
    *   **Time Series** (Single unit over time): Required for ITS.

## Method Quick Reference

*   **Difference-in-Differences (DiD)**: Compares trend changes between treated and control groups. Assumes **Parallel Trends**.
*   **Interrupted Time Series (ITS)**: Analyzes trend/level change for a single unit after intervention. Assumes **Trend Continuity**.
*   **Synthetic Control (SC)**: Constructs a synthetic counterfactual from weighted control units. Assumes **Convex Hull** (treated unit within range of controls).

## Failed Experiment Recovery

When a scientific experiment or optimization plan produces weak or contradictory results, use the same design surface to:

* Separate implementation or measurement errors from design-assumption failures.
* Identify which assumption should be tested next.
* Define a minimal validation experiment before abandoning the approach.
* State the decision rule for continuing, revising, or stopping the line of work.
