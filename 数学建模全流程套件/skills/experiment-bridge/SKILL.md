---
name: experiment-bridge
description: "Implement experiments, run code, collect results, and generate publication-quality figures. Accepts an experiment plan, a research idea, or uploaded data. Use when user says \"实现实验\", \"implement experiments\", \"bridge\", \"从计划到跑实验\", \"跑实验出图\", \"run experiments\", \"deploy the plan\", or has an experiment plan or idea ready to execute."
argument-hint: [experiment-plan-path-or-topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, Skill
---

# Workflow 1.5: Experiment Bridge

Implement and deploy experiments from plan: **$ARGUMENTS**

## Overview

This skill bridges Workflow 1 (idea discovery + method refinement) and Workflow 2 (auto review loop). It takes the experiment plan, turns it into running experiments, collects results, and **directly generates publication-quality figures and LaTeX tables** so downstream paper-write can embed them immediately.

```
Workflow 1 output:                    This skill:                                              Downstream:
refine-logs/EXPERIMENT_PLAN.md   →   implement → review → deploy → collect → generate figures → figures/ ready
refine-logs/EXPERIMENT_TRACKER.md     code       (cross)  /run-exp  results   PDF + LaTeX        for paper-write
refine-logs/FINAL_PROPOSAL.md                                                                    or auto-review
```

## Constants

- **CODE_REVIEW = true** — The configured reviewer model reviews experiment code before deployment. Catches logic bugs before wasting GPU hours. Set `false` to skip.
- **AUTO_DEPLOY = true** — Automatically deploy experiments after implementation + review. Set `false` to manually inspect code before deploying.
- **SANITY_FIRST = true** — Run the sanity-stage experiment first (smallest, fastest) before launching the rest. Catches setup bugs early.
- **MAX_PARALLEL_RUNS = 4** — Maximum number of experiments to deploy in parallel (limited by available GPUs).

> Override: `/experiment-bridge "EXPERIMENT_PLAN.md" — code review: false, auto deploy: false`

## Inputs

This skill accepts flexible inputs — from a detailed experiment plan to just a research idea:

1. **`refine-logs/EXPERIMENT_PLAN.md`** (best) — claim-driven experiment roadmap from `/experiment-plan`
2. **`refine-logs/FINAL_PROPOSAL.md`** — method description for implementation context
3. **`refine-logs/EXPERIMENT_TRACKER.md`** — run-by-run execution table
4. **`IDEA_REPORT.md`** — research idea description
5. **`$ARGUMENTS` text** — a topic or idea description passed directly by the user
6. **`user_data/*.csv` / `user_data/*.json`** — uploaded datasets to analyze

**If none of the above exist and $ARGUMENTS is empty, stop and explain what inputs are needed.**

## Workflow

### Phase 0: Input Detection & Experiment Plan Generation

```bash
echo "=== Input detection ==="
[ -f "refine-logs/EXPERIMENT_PLAN.md" ] && echo "✅ EXPERIMENT_PLAN.md found" || echo "⚠ No EXPERIMENT_PLAN.md"
[ -f "refine-logs/FINAL_PROPOSAL.md" ] && echo "✅ FINAL_PROPOSAL.md found" || echo "⚠ No FINAL_PROPOSAL.md"
[ -f "IDEA_REPORT.md" ] && echo "✅ IDEA_REPORT.md found" || echo "⚠ No IDEA_REPORT.md"
ls user_data/*.csv user_data/*.json 2>/dev/null | head -5
```

**If `EXPERIMENT_PLAN.md` exists** → skip to Phase 1 (parse it directly).

**If `EXPERIMENT_PLAN.md` does NOT exist** → auto-generate one from whatever is available:

1. Read available context: `FINAL_PROPOSAL.md` > `IDEA_REPORT.md` > `$ARGUMENTS` text > `user_data/` files
2. If user uploaded datasets (`user_data/*.csv` or `user_data/*.json`), scan them with pandas to understand columns, data types, and size
3. Generate `refine-logs/EXPERIMENT_PLAN.md` with the following structure:

```markdown
# Experiment Plan (Auto-Generated)

## Research Question
[Derived from the idea/topic/data]

## Datasets
[List available data files with column descriptions, or specify what to generate/download]

## Milestones

### M0: Sanity Check
- Task: [smallest possible experiment to verify setup works]
- Success criterion: [runs without error, produces output]
- Priority: MUST-RUN

### M1: Baseline
- Task: [simple baseline method]
- Metrics: [accuracy/RMSE/F1/etc.]
- Priority: MUST-RUN

### M2: Main Method
- Task: [the core proposed approach]
- Compared against: M1 baseline
- Metrics: [same as M1]
- Priority: MUST-RUN

### M3: Ablation / Analysis
- Task: [remove/vary key components to understand contribution]
- Priority: NICE-TO-HAVE

## Expected Outputs
- Main results comparison table (JSON)
- Training curves (JSON per run)
- Ablation results (JSON)

## Compute Budget
- Estimated: [X] minutes on CPU / [Y] GPU-hours
```

4. If only `$ARGUMENTS` is a short topic (e.g., "image classification with ViT"), expand it into a concrete plan:
   - Pick a standard benchmark dataset (CIFAR-10, MNIST, etc.) or use uploaded data
   - Define 2-3 baselines + the main method
   - Set concrete metrics and success criteria

5. Save to `refine-logs/EXPERIMENT_PLAN.md` and proceed to Phase 1.

### Phase 1: Parse the Experiment Plan

Read `EXPERIMENT_PLAN.md` and extract:

1. **Run order and milestones** — which experiments run first (sanity → baseline → main → ablation → polish)
2. **For each experiment block:**
   - Dataset / split / task
   - Compared systems and variants
   - Metrics to compute
   - Setup details (backbone, hyperparameters, seeds)
   - Success criterion
   - Priority (MUST-RUN vs NICE-TO-HAVE)
3. **Compute budget** — total estimated GPU-hours
4. **Method details** from `FINAL_PROPOSAL.md` — what exactly to implement

Present a brief summary:

```
📋 Experiment plan loaded:
- Milestones: [N] (sanity → baseline → main → ablation)
- Must-run experiments: [N]
- Nice-to-have: [N]
- Estimated GPU-hours: [X]

Proceeding to implementation.
```

### Phase 2: Implement Experiment Code

For each milestone (in order), write the experiment scripts:

1. **Check existing code** — scan the project for existing experiment scripts, model code, data loaders. Reuse as much as possible.

2. **Implement missing pieces:**
   - Training scripts with proper argparse (all hyperparameters configurable)
   - Evaluation scripts computing the specified metrics
   - Data loading / preprocessing if needed
   - Baseline implementations if not already present
   - Fixed random seeds for reproducibility
   - Results saved to JSON/CSV for later analysis
   - Proper logging (wandb if configured in CLAUDE.md)

3. **Follow the plan's run order** — implement sanity-stage experiments first, then baselines, then main method, then ablations.

4. **Self-review before deploying:**
   - Are all hyperparameters from EXPERIMENT_PLAN.md reflected in argparse?
   - Is the random seed fixed and controllable?
   - Are results saved in a parseable format (JSON/CSV)?
   - Does the code match FINAL_PROPOSAL.md's method description?

### Phase 2.5: Cross-Model Code Review (when CODE_REVIEW = true)

**Skip this step if `CODE_REVIEW` is `false` or if the reviewer script fails (API key not configured).**

Before deploying, send the experiment code to the external reviewer for review:

```bash
cat << 'REVIEW_EOF' > _review_prompt.txt
Review the following experiment implementation for correctness.

## Experiment Plan:
[paste key sections from EXPERIMENT_PLAN.md]

## Method Description:
[paste from FINAL_PROPOSAL.md]

## Implementation:
[paste the experiment scripts]

Check for:
1. Does the code correctly implement the method described in the proposal?
2. Are all hyperparameters from the plan reflected in the code?
3. Are there any logic bugs (wrong loss function, incorrect data split, missing eval)?
4. Is the evaluation metric computed correctly?
5. Any potential issues (OOM risk, numerical instability, missing seeds)?

For each issue found, specify: CRITICAL / MAJOR / MINOR and the exact fix.
REVIEW_EOF
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _review_prompt.txt --thread-file _reviewer_thread.json
```

**On review results:**
- **No CRITICAL issues** → proceed to Phase 3
- **CRITICAL issues found** → fix them, then re-submit for review (max 2 rounds). 对话历史通过 `_reviewer_thread.json` 自动保存。
- **Reviewer script fails (API key not configured)** → skip silently, proceed to Phase 3 (graceful degradation)

### Phase 3: Sanity Check (if SANITY_FIRST = true)

Before deploying the full experiment suite, run the sanity-stage experiment:

```
/run-experiment [sanity experiment command]
```

Wait for completion. Verify:
- Training loop runs without errors
- Metrics are computed and saved correctly
- GPU memory usage is within bounds
- Output format matches expectations

If sanity fails → fix the code, re-run. Do not proceed to full deployment with broken code.

### Phase 4: Deploy Full Experiments

Deploy experiments following the plan's milestone order:

```
/run-experiment [experiment commands]
```

For each milestone:
1. Deploy experiments in parallel (up to MAX_PARALLEL_RUNS)
2. Use `/monitor-experiment` to track progress
3. Collect results as experiments complete

**🚦 Checkpoint (if AUTO_DEPLOY = false):**

```
🔧 Code implementation complete. Ready to deploy:

Milestone 0 (sanity): [status — passed/pending]
Milestone 1 (baseline): [N experiments, ~X GPU-hours]
Milestone 2 (main method): [N experiments, ~X GPU-hours]
Milestone 3 (ablations): [N experiments, ~X GPU-hours]

Total estimated: ~X GPU-hours on [N] GPUs

Deploy now? Or review the code first?
```

### Phase 5: Collect & Structure Results

As experiments complete:

1. **Parse output files** (JSON/CSV/logs) for key metrics
2. **Update `refine-logs/EXPERIMENT_TRACKER.md`** — fill in Status and Notes columns
3. **Check success criteria** from EXPERIMENT_PLAN.md — did each experiment meet its bar?
4. **Consolidate all results into structured data files** for downstream figure generation:

```bash
mkdir -p figures
# Consolidate all experiment results into a single JSON for easy plotting
python3 << 'PYEOF'
import json, glob, os
all_results = {}
for f in sorted(glob.glob("results/**/*.json", recursive=True) + glob.glob("results/**/*.csv", recursive=True)):
    key = os.path.splitext(os.path.basename(f))[0]
    if f.endswith(".json"):
        with open(f) as fh: all_results[key] = json.load(fh)
    else:
        import csv
        with open(f) as fh: all_results[key] = list(csv.DictReader(fh))
with open("figures/experiment_data.json", "w") as fh:
    json.dump(all_results, fh, indent=2, default=str)
print(f"Consolidated {len(all_results)} result files -> figures/experiment_data.json")
PYEOF
```

5. **Write `experiment_results.md`** (human-readable summary):

```markdown
# Experiment Results

**Date**: [today]
**Plan**: refine-logs/EXPERIMENT_PLAN.md

## Results by Milestone

### M0: Sanity — PASSED
- [result]

### M1: Baselines
| Run | System | Key Metric | Status |
|-----|--------|-----------|--------|
| R001 | baseline_1 | X.XX | DONE |

### M2: Main Method
| Run | System | Key Metric | Status |
|-----|--------|-----------|--------|
| R003 | our_method | X.XX | DONE |

### M3: Ablations
...

## Summary
- [X/Y] must-run experiments completed
- Main result: [positive/negative/inconclusive]
```

### Phase 5.5: Generate Publication-Quality Figures (⛔ must not skip)

**Directly produce paper-ready figures from experiment results.** This eliminates the gap between raw data and the paper-figure step — downstream paper-write can embed these figures immediately.

#### Setup

**⛔ First, read the figure plan from planning docs to know what figures are expected:**
```bash
echo "=== Figure plan from planning docs ==="
for plan in TOPIC_PLAN.md PAPER_PLAN.md PROBLEM_ANALYSIS.md MODELING_REPORT.md; do
    [ -f "$plan" ] || continue
    echo "--- $plan ---"
    grep -i 'fig\|图\|table\|表\|chart\|plot\|heatmap\|radar\|TikZ\|tikz\|森林图\|雷达图\|热力图\|散点图\|箱线图\|小提琴' "$plan" | head -30
done
```
Generate ALL figures mentioned in the plan, plus any additional figures warranted by the data.

```python
import os, sys, shutil
from pathlib import Path
os.makedirs('_utils', exist_ok=True)
for src in ['plot_utils.py', 'stats_utils.py']:
    for search in ['skills/shared-scripts', '../skills/shared-scripts']:
        p = os.path.join(search, src)
        if os.path.isfile(p):
            shutil.copy2(p, f'_utils/{src}'); break
sys.path.insert(0, '.')
from _utils.plot_utils import setup_style, save_fig, PALETTE
setup_style()  # defaults to Soft palette
```

#### Figure generation rules

Each figure is a standalone `figures/gen_fig_*.py` script (same convention as paper-figure). Must follow:
- `setup_style()` called, no matplotlib default blue
- No `plt.title()` — captions go in LaTeX only
- PDF vector output at 300 DPI
- Read data from `figures/experiment_data.json` or individual result JSON/CSV files, never hardcode numbers

**MANDATORY**: Before writing each figure script, read the matching recipe from `_utils/figure_recipes_*.md`:
```bash
# Scan available recipes
for f in _utils/figure_recipes_*.md; do [ -f "$f" ] && echo "=== $f ===" && grep '^## ' "$f"; done
# Then read the full code for the matched recipe, e.g.:
cat _utils/figure_recipes_advanced.md | sed -n '/^## 6\./,/^## 7\./p'
```
Copy the recipe code as starting point, adapt to actual data. Do NOT write figure scripts from scratch.

#### Required figures (generate all that apply)

| Data available | Figure type | Script name |
|---------------|-------------|-------------|
| Main results table (ours vs baselines × metrics) | Grouped bar chart | `gen_fig_main_results.py` |
| Training logs (loss/metric per epoch) | Multi-line convergence plot | `gen_fig_training_curves.py` |
| Ablation results | Ablation bar chart (with delta annotations) | `gen_fig_ablation.py` |
| Per-class / per-dataset breakdown | Heatmap or grouped bar | `gen_fig_breakdown.py` |
| Hyperparameter sensitivity | Line plot with CI band | `gen_fig_hyperparam.py` |
| Qualitative examples | Subfigure grid (if image data) | `gen_fig_qualitative.py` |
| Confusion matrix | Heatmap | `gen_fig_confusion.py` |
| t-SNE / UMAP embeddings | Scatter plot | `gen_fig_embeddings.py` |

Only generate figures for which data actually exists. Skip the rest.

#### Execute and verify

```bash
for script in figures/gen_fig*.py; do
    [ -f "$script" ] || continue
    echo "Running: $script"
    python3 "$script" 2>&1
done
# Fix nested output
[ -d "figures/figures" ] && mv figures/figures/*.pdf figures/ 2>/dev/null
echo "Generated PDFs:"
ls -la figures/*.pdf 2>/dev/null | wc -l
```

#### Generate result tables (format depends on output mode)

For main results and ablation tables, generate three-line tables. **Pick the format by output mode** (read `output_format` from CLAUDE.md's `## 参数` section; default `pdf`):
- **PDF mode** → LaTeX tables `figures/TABLE_*.tex` (booktabs three-line)
- **Word/DOCX mode** → Markdown tables `figures/TABLE_*.md` (Markdown three-line)

```python
# 自动按输出模式选格式
import os, re
_cm = ''
try:
    _cm = open('CLAUDE.md', encoding='utf-8').read()
except Exception:
    pass
_m = re.search(r'^- output_format:\s*(\w+)', _cm, re.MULTILINE)
output_format = (_m.group(1).strip().lower() if _m else 'pdf')
ext = 'md' if output_format == 'docx' else 'tex'

# Use stats_utils if available, otherwise write raw table
try:
    from _utils.stats_utils import regression_table
    # stats_utils 按 output 后缀自动产出对应格式
    # regression_table(results, [...], output=f'figures/TABLE_main_results.{ext}', caption='...')
except ImportError:
    pass

# Save as figures/TABLE_main_results.{ext}, figures/TABLE_ablation.{ext}, etc.
# ⛔ docx 模式禁止生成 .tex 表（Word 不读 LaTeX）；PDF 模式禁止生成 .md 表
```

#### Generate LaTeX include snippets

Save to `figures/latex_includes.tex`:
```latex
% Auto-generated by experiment-bridge Phase 5.5
% Figures use [H]; tables use [H] (requires \usepackage{float})

\begin{figure}[H]
    \centering
    \includegraphics[width=0.95\textwidth]{figures/fig_main_results.pdf}
    \caption{Main results comparison across all datasets and metrics.}
    \label{fig:main-results}
\end{figure}

% ... one block per generated figure/table
```

#### Quality check

```bash
echo "=== Output completeness check ==="
GATE_FAIL=0
# experiment_data.json must exist
[ -s figures/experiment_data.json ] && echo "✅ experiment_data.json" || { echo "❌ experiment_data.json missing"; GATE_FAIL=$((GATE_FAIL+1)); }
# experiment_results.md must exist
[ -s experiment_results.md ] && echo "✅ experiment_results.md" || { echo "❌ experiment_results.md missing"; GATE_FAIL=$((GATE_FAIL+1)); }
# PDF figures
pdf_count=$(ls figures/*.pdf 2>/dev/null | wc -l)
table_count=$(ls figures/TABLE_*.tex figures/TABLE_*.md 2>/dev/null | wc -l)
latex_inc=$([ -s figures/latex_includes.tex ] && echo "YES" || echo "NO")
echo "PDF figures: $pdf_count, Tables: $table_count, latex_includes: $latex_inc"
[ "$pdf_count" -gt 0 ] && echo "✅ Figures generated" || { echo "❌ No PDF figures"; GATE_FAIL=$((GATE_FAIL+1)); }
[ "$latex_inc" = "YES" ] && echo "✅ latex_includes.tex" || { echo "❌ latex_includes.tex missing"; GATE_FAIL=$((GATE_FAIL+1)); }
echo ""
[ "$GATE_FAIL" -eq 0 ] && echo "✅ ALL PASSED" || echo "❌ $GATE_FAIL FAILURES — fix before proceeding"
```

**⛔ If GATE_FAIL > 0, fix and re-run. Do NOT proceed to paper writing with missing data.**

### Phase 6: Handoff

Present final status:

```
Experiment bridge complete:
- Implemented: [N] experiment scripts
- Deployed: [N] experiments on [M] GPUs
- Completed: [X/Y] must-run, [A/B] nice-to-have
- Main result: [one sentence]
- Figures generated: [N] PDFs + [N] LaTeX tables

Key outputs:
  experiment_results.md          — human-readable results summary
  figures/experiment_data.json   — consolidated raw data
  figures/*.pdf                  — publication-quality figures
  figures/TABLE_*.tex|md         — result tables (.tex for PDF mode, .md for Word/docx mode)
  figures/latex_includes.tex     — LaTeX snippets for paper-write
  refine-logs/EXPERIMENT_TRACKER.md — updated run tracker

Ready for next steps:
→ /auto-review-loop "[topic]"    (review + iterate on narrative)
→ /paper-figure                  (add TikZ architecture diagrams or extra figures if needed)
→ /paper-write                   (figures/ already populated, can write directly)
```

## Key Rules

⛔ **File writing strategy (prevent both failure modes):**
- For short content (<150 lines): use the **Write tool** directly (atomic, reliable)
- For long content (>150 lines): use **Write** for the first section (ensures file exists on disk), then append remaining sections with `cat << 'EOF' >> experiment_results.md`
- **NEVER `end_turn` without producing `experiment_results.md`** — even if upstream steps had issues, write what you have

⛔ **MUST run output verification before ending**:
```bash
PASS=true
[ -f experiment_results.md ] && SZ=$(wc -c < experiment_results.md) || SZ=0
if [ "$SZ" -ge 500 ]; then
    echo "✅ experiment_results.md ($SZ bytes)"
else
    echo "❌ experiment_results.md missing or too small ($SZ bytes) — write it NOW before ending"
    PASS=false
fi
# 引擎按 figures/ 目录判定本步骤成败, 必须有至少 1 张图产出
PDF_N=$(ls figures/*.pdf figures/*.png 2>/dev/null | wc -l)
if [ "$PDF_N" -ge 1 ]; then
    echo "✅ figures/ 有 $PDF_N 张图"
else
    echo "❌ figures/ 没有任何图 — 必须产出图表后再结束 (引擎按 figures/ 判定成败)"
    PASS=false
fi
[ "$PASS" != true ] && echo "⛔ Verification failed — must produce output before ending step"
```

- **Follow the plan.** Do not invent experiments not in EXPERIMENT_PLAN.md. If you think something is missing, note it but don't add it.
- **Sanity first.** Never deploy a full suite without verifying the sanity stage passes.
- **Reuse existing code.** Scan the project before writing new scripts. Extend, don't duplicate.
- **Save everything as JSON/CSV.** Both auto-review-loop and figure generation need parseable results, not just terminal output.
- **Update the tracker.** `EXPERIMENT_TRACKER.md` should reflect real status after each run completes.
- **Don't wait forever.** If an experiment exceeds 2x its estimated time, flag it and move on to the next milestone.
- **Budget awareness.** Track GPU-hours against the plan's budget. Warn if approaching the limit.
- **Figures use plot_utils.py.** All generated figures must use `setup_style()` from `shared-scripts/plot_utils.py` for consistent academic styling. No matplotlib default colors, no `plt.title()`, PDF vector output only.
- **One script per figure.** Each figure is a standalone `figures/gen_fig_*.py` that reads from JSON/CSV and outputs PDF. This allows re-running individual figures without re-running experiments.
- **latex_includes.tex is mandatory.** Without it, paper-write has no figure snippets to embed. Always generate it even if only one figure exists.

## Composing with Other Skills

```
/idea-discovery "direction"          ← Workflow 1: find + refine + plan
/experiment-bridge                   ← you are here (1.5: implement + deploy + generate figures)
/auto-review-loop "topic"            ← Workflow 2: review + iterate on narrative
/paper-figure                        ← (optional) add TikZ diagrams or extra figures not covered above
/paper-write "NARRATIVE_REPORT.md"   ← Workflow 3: write the paper (figures/ already populated)

Or use /research-pipeline for the full end-to-end flow (includes this bridge).
```
