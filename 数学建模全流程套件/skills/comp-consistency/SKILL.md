---
name: comp-consistency
description: Use when a mathematical modeling competition paper must be checked against its canonical results JSON, code outputs, figures, and reported headline metrics before compilation.
---

# Competition Code-Paper Consistency

Read `RESULTS.md`, `figures/all_results.json`, `paper/main.tex`, and declared figures. Create `CONSISTENCY_REPORT.json` with `ok`, `claims`, and each claim's paper location, result-ledger path, observed values, and comparison status. Any missing metric, mismatched value, or untraceable claim sets `ok` to false.
