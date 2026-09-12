---
name: comp-consistency
description: Use when a mathematical modeling competition paper must be checked against its canonical results JSON, code outputs, figures, and reported headline metrics before compilation.
---

# Competition Code-Paper Consistency

Read `RESULTS.md`, `figures/all_results.json`, `paper/main.tex`, and declared figures. Create `CONSISTENCY_REPORT.json` with `ok`, `claims`, and each claim's paper location, result-ledger path, observed values, and comparison status. Any missing metric, mismatched value, or untraceable claim sets `ok` to false.

Auxiliary sweep (2026-09-12 asset wiring): also run `python tools/paper_data_check.py <工作区>` (repo-root relative; the tool existed unwired before this line) and fold its findings into `CONSISTENCY_REPORT.json` — it cross-checks paper numbers against the result ledger and is the mandatory machine backstop for this step. The contract and `ok` semantics above remain unchanged.
