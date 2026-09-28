# ARC-Bench

[![🤗 Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Dataset-ARC--Bench-yellow)](https://huggingface.co/datasets/AIMING-Lab-UNC/ARC-Bench)

Also available on the Hugging Face Hub: **[AIMING-Lab-UNC/ARC-Bench](https://huggingface.co/datasets/AIMING-Lab-UNC/ARC-Bench)** (`load_dataset("AIMING-Lab-UNC/ARC-Bench")`).

A self-contained **55-topic** open-ended autonomous-research benchmark spanning
five domains — **ML (25), high-energy physics (10), quantum (10), biology (7),
and statistics (3)**. Each framework receives the same per-topic manifest
(research question + synthesis + conditions + metrics + datasets +
hypotheses) and must produce code → measurements → claims → writeup.
Scoring is rubric-graded with a strict multi-criteria audit.

> **Note:** this public tree ships the benchmark *inputs* — manifests, rubrics,
> configs, and the baseline harness + scripts. Large run outputs (`results/`)
> and scoring write-ups (`analysis/`) are kept local-only (gitignored) and are
> reproducible via the runners in `scripts/`.

## Repo layout

```
experiments/arc_bench/
├── README.md                 # this file
├── RUN_GUIDE.md              # operational runbook
├── EXPERIMENT_DESIGN.md      # methodology
│   # (repo-root .gitignore keeps results/ + analysis/ + baseline/external/ local)
│
├── config/                   # ALL inputs in one place
│   ├── base_config.yaml      # global runner config
│   ├── _meta_paper_quality.json  # SHARED paper-quality meta-rubric
│   │                             #   (paper-content / code-orchestration /
│   │                             #    visual-layout / content-accuracy
│   │                             #    — graded manually, NOT auto-run)
│   ├── ml/                   # ML01-ML25 — ML topics (autoclaw native sandbox)
│   │   ├── topics.yaml       # 25-topic ML registry (id / domain / metric)
│   │   ├── manifests/        # ML01-ML25.yaml
│   │   └── rubrics/          # ML01-ML25.json (3-bucket: code/exec/results)
│   ├── physics/              # P01-P10 — HEP topics (collider_agent mode)
│   │   ├── topics.yaml       # physics topic registry
│   │   ├── manifests/        # P01-P10.yaml — sourced from
│   │   │                     #   external/agents/ColliderAgent/paper-reproduction/
│   │   └── rubrics/          # P01-P10.json (4-bucket: code/exec/results/repro)
│   ├── biology/              # B01-B07 — metabolic topics (biology_agent mode)
│   │   ├── topics.yaml
│   │   ├── manifests/        # B01-B07.yaml (uses external/agents/Biology-Agent)
│   │   └── rubrics/          # B01-B07.json (4-bucket)
│   ├── quantum/              # Q01-Q10 — quantum ML + VQE topics (autoclaw native, Qiskit 2.x)
│   │   ├── README.md         # topic registry + latest scores + repro + caveats
│   │   ├── topics.yaml
│   │   ├── manifests/        # Q01-Q10.yaml
│   │   └── rubrics/          # Q01-Q10.json (3-bucket: code/exec/results)
│   ├── statistics/           # S01-S03 — statistics topics (stat_agent mode)
│   │   ├── topics.yaml
│   │   ├── manifests/        # S01-S03.yaml
│   │   └── rubrics/          # S01-S03.json (4-bucket)
│   ├── credentials.example.env  # template; copy to .env.local for real values
│   └── credentials_loader.py    # python-dotenv loader for bench scripts
│
├── baseline/                 # SELF-CONTAINED baseline framework code
│   ├── README.md             # how to clone + install each baseline
│   ├── adapters/             # ARC-Bench framework adapters (one .py per baseline)
│   ├── external/             # cloned upstream repos (gitignored, see baseline/README.md)
│   │   ├── aideml/
│   │   ├── AgentLaboratory/
│   │   └── AI-Scientist-v2/
│   └── interventions/        # rc_copilot scripted HITL JSONs (ML01-ML25)
│
├── scripts/                  # runners + utilities
│   ├── run_baseline.py       # entry: any baseline × any topic
│   ├── run_bench.py          # entry: rc_full / rc_copilot
│   ├── run_aide.sh           # AIDE sweep (parallel by default)
│   ├── run_rc_full.sh        # rc_full sweep (sequential)
│   ├── run_rc_copilot.sh     # rc_copilot sweep
│   ├── run_ais_v2.sh         # AI Scientist v2 sweep
│   ├── run_agent_lab.sh      # AgentLab sweep
│   ├── prepare_run.py        # manifest → stage-07/08/09 artifacts (autoclaw)
│   ├── hitl_suggestor.py     # rc_full failure → rc_copilot intervention
│   ├── make_manifests.py     # author new topic manifests via LLM (utility)
│   ├── judge.py              # auto-judge (LLM-based, results-only)
│   ├── judge_manual.py       # manual-audit dispatcher (Claude/Codex/human)
│   ├── judge_results_only.py # programmatic results-only check (no LLM)
│   ├── evaluate.py           # aggregator over all judge_result.json
│   └── prompts/
│       └── manual_strict_audit_prompt.md  # unified manual-audit prompt
│
├── analysis/
│   ├── UNIFIED_JUDGE.md      # CANONICAL scoring view (single source of truth)
│   └── SCORE_TABLE_MOCK.md   # template preview (no real numbers)
│
└── results/                  # ALL outputs (gitignored)
    ├── rc_full/
    ├── rc_copilot/
    ├── ais_v2/
    ├── agent_lab/
    ├── aide_ml/
    └── legacy/               # backups + per-cell evidence + old audit docs
        ├── judges_T01_T05/   # 30 per-cell judge JSONs
        ├── judges_T06_T25/   # 90 per-cell judge JSONs
        ├── audit_docs_T*/    # historical audit MDs
        ├── log/              # per-run stdout logs
        └── ... (rubric backups, intermediate runs)
```

## Quickstart

### 0. Set env vars (proxy + models)

```bash
export OPENAI_API_KEY="<your-key>"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export ARC_JUDGE_MODEL="gpt-5.3-codex"
export ARC_WIRE_API="responses"
```

### 1. Install baselines (one-time, ~20 min)

See `baseline/README.md`.

### 2. Run a single cell (smoke test)

```bash
cd /path/to/AutoResearchClaw

# Any baseline, any topic, dry-run (no LLM cost; verifies wiring)
python experiments/arc_bench/scripts/run_baseline.py \
    --framework aide_ml --topic ML01 --dry-run

# Real run (~5 min for AIDE on ML01)
python experiments/arc_bench/scripts/run_baseline.py \
    --framework aide_ml --topic ML01

# Autoclaw modes
python experiments/arc_bench/scripts/run_bench.py \
    --mode rc_full --topic ML01

# Quantum topic (autoclaw native sandbox, Qiskit 2.x). See config/quantum/README.md.
python experiments/arc_bench/scripts/run_bench.py \
    --mode rc_full --topic Q03
```

### 3. Sweep all 25 topics (one baseline)

```bash
bash experiments/arc_bench/scripts/run_aide.sh        # parallel x8
bash experiments/arc_bench/scripts/run_rc_full.sh     # serial
bash experiments/arc_bench/scripts/run_rc_copilot.sh
bash experiments/arc_bench/scripts/run_ais_v2.sh      # parallel x4
bash experiments/arc_bench/scripts/run_agent_lab.sh   # known to fail under fair input
```

### 4. Judge

Two complementary methods:

**Manual (rubric-grounded, leaf-level evidence):**
```bash
# Dispatch a Claude Code subagent for one cell
python experiments/arc_bench/scripts/judge_manual.py \
    --framework aide_ml --topic ML01 --dispatch claude

# Or as a Codex CLI prompt
python experiments/arc_bench/scripts/judge_manual.py \
    --framework rc_full --topic ML17 --dispatch codex

# Or human-reviewer checklist + JSON template
python experiments/arc_bench/scripts/judge_manual.py \
    --framework rc_copilot --topic ML05 --dispatch human
```

The same prompt (`scripts/prompts/manual_strict_audit_prompt.md`) is
used in all three modes — Claude Code, Codex CLI, and human expert all
score against the same rubric and produce the same JSON schema. This
makes cross-validation trivial: re-run with a different `--dispatch`,
compare per-leaf scores, flag any |Δ| > 0.20.

**Results-only (programmatic, no LLM, fast):**
```bash
python experiments/arc_bench/scripts/judge_results_only.py --all
# or per-cell:
python experiments/arc_bench/scripts/judge_results_only.py \
    --framework aide_ml --topic ML01
```

This reads each framework's canonical artifacts (different paths per
baseline) and emits a results-only score (Code Exec + Result Analysis
only — Code Dev requires the manual judge).

### 5. Read the unified scoring view

```bash
less experiments/arc_bench/analysis/UNIFIED_JUDGE.md
```

Single source of truth for all 5 frameworks × 25 topics.

## Reproducibility checklist

- [x] `config/ml/manifests/ML01-ML25.yaml` — topic specs are version-controlled
- [x] `config/ml/rubrics/ML01-ML25.json` — rubrics are version-controlled (CD:CE:RA = 25:25:50)
- [x] `baseline/adapters/` — adapter code is version-controlled
- [x] `baseline/interventions/` — rc_copilot intervention specs are version-controlled
- [ ] `baseline/external/` — clone via `bash baseline/setup.sh` (gitignored)
- [ ] `results/` — generated by sweeps (gitignored)
- [x] `analysis/UNIFIED_JUDGE.md` — final analysis is version-controlled

## Attribution for non-ML topics

Physics (`P*`) and biology (`B*`) topics drive **external Claude-Code agents**
that live under `external/agents/` (see `external/agents/README.md`).  The
benchmark glue code, manifests, and rubrics are AutoResearchClaw's own work,
but the science pipelines themselves are upstream:

| Topic family | External agent | Upstream | Wired via |
|---|---|---|---|
| `P01-P10` (HEP)   | ColliderAgent | <https://github.com/HET-AGI/ColliderAgent> | `experiment.mode = collider_agent` → `ColliderAgentSandbox` |
| `B01+`  (metabolic) | Biology-Agent | local development repo | `experiment.mode = biology_agent` → `BiologyAgentSandbox` |

When publishing scoreboards or per-run READMEs, credit the upstream agent that
produced the science.  The bench's job is the framework comparison; the
domain pipelines belong to the listed projects.

## Paper-quality meta-rubric (manual grading)

Per-topic rubrics under `config/{ml,physics,biology}/rubrics/*.json` grade
the **science**: did the agent run the experiment, produce the right
numbers, support the hypotheses?

A SECOND layer — **`config/_meta_paper_quality.json`** — grades the
**paper output**: writing quality, code orchestration, visual layout, and
content accuracy.  This layer is intentionally **manual**, not auto-run.
Why: paper-quality judgments benefit from a human (or a vision-equipped
agent) reading the actual deliverable, not from a fast LLM summarising a
JSON dump.

### Rubric structure (19 leaves, 4 buckets)

| Bucket | Leaves | Weight |
|---|---|---|
| `paper-content`        | abstract / intro / method-clarity / results-grounded / discussion / citations | 30 |
| `code-orchestration`   | modular / reproducible / readable / no-dead-code | 18 |
| `visual-layout`        | axes / legend / caption / figure-relevance / color-accessibility | 17 |
| `content-accuracy`     | no-fabrication (8) / correct-units / claim-strength / internal-consistency | 21 |

Total leaf weight 86.  Combined with the per-topic science rubric (weight
100), overall score ≈ 54% science + 46% paper-quality.  The meta-rubric
is applied identically across all 46 topics (ML01-25 / P01-10 / B01+ / Q01-10).

### Running the manual grader

```bash
# Grade the latest run for a topic
experiments/arc_bench/scripts/judge_paper_manual.sh --topic B01

# Grade a specific run directory
experiments/arc_bench/scripts/judge_paper_manual.sh \
    experiments/arc_bench/results/e2e/B01/e2e-B01-20260510-073220

# Dry-run (writes the audit prompt but doesn't invoke claude)
experiments/arc_bench/scripts/judge_paper_manual.sh --topic B01 --dry-run
```

This launches a Claude Code session with the meta-rubric as reference
text, Read+vision access to `paper_final.md`, `charts/*.{png,pdf}`,
`code/`, and a strict scoring protocol (per-leaf score in
{0, 0.33, 0.5, 0.67, 1.0}, with evidence quotes).  Output:
`paper_quality_verdict.json` in the run dir.  Cost ≈ 5-15 min + ~$0.5 in
Claude credits per run.  Run this AFTER `run_e2e_topic.py` completes —
the pipeline does NOT auto-invoke it.

## End-to-end runner (1 → 23 stages)

`scripts/run_e2e_topic.py` is the cross-domain end-to-end driver — it picks
the right profile (`ml_general` / `hep_ph` / `biology_metabolic`) and the
right experiment mode (`sandbox` / `collider_agent` / `biology_agent`) from
the topic ID prefix (`T*` / `P*` / `B*`):

```bash
python experiments/arc_bench/scripts/run_e2e_topic.py --topic B01
python experiments/arc_bench/scripts/run_e2e_topic.py --topic P01
python experiments/arc_bench/scripts/run_e2e_topic.py --topic ML01
```

The pipeline runs all 23 stages, the agent writes a canonical
`results.json` at the workspace root (mandated by the prompt footer in
`BiologyAgentSandbox._prepare_workspace` / `ColliderAgentSandbox._prepare_workspace`),
the sandbox surfaces those scientific keys into stage-14 metrics, and the
judge produces a leaf-graded rubric score.  No python-code refinement
loops — the agent is atomic and either the results.json passes or it
doesn't.

## See also

- `RUN_GUIDE.md` — operational details + tmux runbook
- `EXPERIMENT_DESIGN.md` — benchmark methodology and scope
- `baseline/README.md` — per-baseline install + run instructions
- `analysis/UNIFIED_JUDGE.md` — full scoring view
- `external/agents/README.md` — upstream attribution for collider / biology agents
- `docs/DOMAIN_INTEGRATION_GUIDE.md` — how to add a new domain (with the canonical-results contract + run_project requirement)
