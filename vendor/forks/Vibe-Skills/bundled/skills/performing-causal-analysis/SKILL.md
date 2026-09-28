---
name: performing-causal-analysis
description: Estimate causal effects from existing data. Use when fitting or interpreting DiD, ITS, synthetic control, regression discontinuity, or other treatment-effect analyses, including robustness checks and counterfactual plots. For choosing a study design before analysis, use designing-experiments instead.
---

# Performing Causal Analysis

Executes causal analysis on existing data. This skill owns model setup, treatment-effect estimation, counterfactual comparison, robustness checks, and interpretation of fitted causal results.

It does not own the earlier question of which experiment or quasi-experiment should be designed before analysis begins.

## Workflow

1.  **Load Data**: Ensure data is in a Pandas DataFrame.
2.  **Initialize Experiment**: Use the appropriate class (see References).
3.  **Fit & Model**: Models are fitted automatically upon initialization if arguments are provided.
4.  **Analyze Results**: Use `summary()`, `print_coefficients()`, and `plot()`.

## Core Methods

*   `experiment.summary()`: Prints model summary and main results.
*   `experiment.plot()`: Visualizes observed vs. counterfactual.
*   `experiment.print_coefficients()`: Shows model coefficients.

## References

Detailed usage for specific methods:
*   [Difference-in-Differences](reference/diff_in_diff.md)
*   [Interrupted Time Series](reference/interrupted_time_series.md)
*   [Synthetic Control](reference/synthetic_control.md)
