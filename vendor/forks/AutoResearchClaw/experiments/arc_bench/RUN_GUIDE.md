# ARC-Bench Run Guide (minimal)

How to reproduce the three framework sweeps: **rc_full** / **rc_copilot** (autoclaw) and **ais_v2** (AI-Scientist-v2 baseline).

---

## 0. One-time env setup

```bash
# autoclaw (root repo)
conda create -n autoclaw python=3.11 -y
conda activate autoclaw
pip install -e .        # installs `researchclaw` CLI
pip install -r requirements.txt

# AI-Scientist-v2 baseline — separate venv to keep deps isolated
cd /playpen2/shiqiu/arc_bench
python3.11 -m venv ais_v2_venv
source ais_v2_venv/bin/activate
pip install -r <path-to-repo>/experiments/framework_comparison/external/AI-Scientist-v2/requirements.txt
# Apply the /v1/responses patch so gpt-5.x codex works through the proxy
cd <path-to-repo>/experiments/framework_comparison/external/AI-Scientist-v2
git apply <path-to-repo>/experiments/framework_comparison/patches/ai_scientist_v2_responses_api.patch
```

The AIS-v2 **clone is not in this repo** (it's the upstream SakanaAI repo, 351M). Clone it yourself:

```bash
git clone https://github.com/SakanaAI/AI-Scientist-v2.git \
  experiments/framework_comparison/external/AI-Scientist-v2
```

Then apply the patch (see `experiments/framework_comparison/patches/`). The patch routes gpt-5.x codex through `/v1/responses` instead of `/v1/chat/completions` so an OpenAI-compatible proxy accepts it.

## 1. Environment variables

All scripts expect these at run time:

```bash
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_API_KEY="<your-proxy-key>"
export CUDA_VISIBLE_DEVICES=""   # bench is CPU-only
```

## 2. Run a single topic end-to-end

```bash
# autoclaw — full pipeline, stages 10→14
python experiments/arc_bench/scripts/run_bench.py \
  --mode rc_full --topic T01

# autoclaw — copilot (human-in-the-loop stubs auto-answer "proceed")
python experiments/arc_bench/scripts/run_bench.py \
  --mode rc_copilot --topic T01

# AI-Scientist-v2 baseline (runs ideation + BFTS + bridge + judge)
python experiments/arc_bench/scripts/run_ais_v2.py --topic T01
```

Each run writes:

```
results/<mode>/<topic>/<run_id>/
  judge_result.json         # overall_score + correctness/verdicts/rubric breakdown
  submission/               # claims.json + results/metrics.json + code/ + README.md
  stage-10/experiment.py    # initial code
  stage-13/experiment_final.py  # final code
  stage-14/experiment_summary.json  # condition_summaries + ablation_warnings
log/<mode>/<topic>/<run_id>.log   # full stdout/stderr (NOT in git)
```

## 3. Run the full 25-topic sweep (parallel=5)

```bash
# rc_full
python experiments/arc_bench/scripts/sweep.py \
  --mode rc_full --parallel 5

# ais_v2
python experiments/arc_bench/scripts/sweep.py \
  --mode ais_v2 --parallel 5
```

Wall-clock budget (observed):

| Mode | Per topic | 25-topic serial | 25-topic @ parallel=5 | Est. $ |
|---|---|---|---|---|
| rc_full | ~25 min | ~10 h | ~2 h | $15-25 |
| rc_copilot | ~25 min | ~10 h | ~2 h | $15-25 |
| ais_v2 | ~60 min | ~25 h | ~5 h | $100-125 |

## 4. Aggregate scoreboard

```bash
python experiments/arc_bench/scripts/evaluate.py
# → experiments/arc_bench/analysis/scoreboard.json + .md
```

## 5. Current scoreboard (T01 example)

| Framework | overall | correctness | verdicts | notes |
|---|---|---|---|---|
| rc_full | 0.685 | 0.30 | 0.53 | 4 conds, **zero variance** — wiring bug |
| rc_copilot | TBD | — | — | — |
| ais_v2 | **1.000** | 1.00 | 1.00 | 8 conds, real variance 0.90-0.97 |

Full breakdown: `analysis/scoreboard.md`.

## 6. Model routing

| Role | Model | Wire |
|---|---|---|
| code generation (all frameworks) | `gpt-5.3-codex` | `/v1/responses` |
| tool calls / JSON / feedback | `gpt-4o` | `/v1/chat/completions` |
| local judge | `gpt-4o` | `/v1/chat/completions` (for claims extraction) |

The proxy rejects any model name with date suffixes (e.g. `gpt-4o-2024-08-06`) — use bare `gpt-4o`.

## 7. Key code files

- `scripts/run_bench.py` — autoclaw (rc_full / rc_copilot) single-topic runner
- `scripts/run_ais_v2.py` — AIS-v2 runner + bridge that synthesizes ARC-Bench submission/stage-14 layout from `logs/0-run/*_summary.json`
- `scripts/judge.py` — local judge (heuristic + rubric + correctness + verdicts, weights 0.25/0.20/0.25/0.30)
- `scripts/sweep.py` — parallel sweep driver
- `scripts/evaluate.py` — scoreboard aggregator
- `manifests/T*.yaml` — topic specs (hypotheses, conditions, metrics, datasets)
- `rubrics/T*.json` — per-topic judge rubric (≥8 leaves)
