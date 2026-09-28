---
name: preprocessing-data-with-automated-pipelines
description: |
  Design and implement repeatable preprocessing pipelines for cleaning, encoding, transforming, and validating ML input data.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(cmd:*)
version: 1.0.0
author: Jeremy Longshore <jeremy@intentsolutions.io>
license: MIT
---
# Data Preprocessing Pipeline

## Positioning

Use this skill as the direct owner for ML input-preparation pipelines.

It covers preprocessing-heavy tasks where the requested deliverable is a repeatable pipeline for cleaning, encoding, transforming, and validating input data.

## When to Use

Use this skill when:
- Prepare raw data for machine learning models.
- Automate data cleaning and transformation processes.
- Implement a robust ETL (Extract, Transform, Load) pipeline.

## Not For / Boundaries

- Whole-task ML ownership: use `scikit-learn` or `ml-pipeline-workflow`
- Leakage and prediction-time auditing: use `ml-data-leakage-guard`
- Grouped scientific preprocessing with stronger methodological constraints: use `scientific-data-preprocessing`

## Typical Outputs

- A preprocessing pipeline plan or implementation sketch
- Clear sequencing for clean, encode, transform, and validate steps
- Notes that identify where leakage review, training, or evaluation should be run next

## Related Skills

- `ml-data-leakage-guard` before trusting fitted preprocessing steps
- `splitting-datasets` when the next narrow problem is partition strategy
