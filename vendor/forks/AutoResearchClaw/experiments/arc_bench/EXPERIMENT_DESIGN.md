# ARC-Bench — experiment design

## Research question

When given only a research **question** (not a method), can autonomous
research frameworks (a) design a reasonable experiment, (b) write
runnable code, (c) execute it with sufficient statistical care, and
(d) produce a faithful writeup? How does autoclaw's **co-pilot mode**
(with HITL suggestions auto-derived from the full-auto run) compare to
other frameworks on the exact same 25 questions?

## Primary hypotheses

- **H1 (autoclaw > baselines).** rc_full produces higher weighted rubric
  scores than AI Scientist v1/v2 and Agent Laboratory on the 25 topics,
  averaged, with paired-seed comparison.

- **H2 (copilot > full-auto).** rc_copilot, consuming interventions
  auto-generated from rc_full's weak points, produces higher weighted
  rubric scores than rc_full on the same 25 topics.

- **H3 (evolutionary gain scales with gap).** The copilot improvement
  (copilot − full-auto) is larger on topics where rc_full's judge score
  was lowest — the HITL suggestor successfully identifies and patches
  the worst failure modes.

## Measurables

Every run (autoclaw or baseline) produces a `submission/` directory
with the PaperBench layout. The same finalizer + judges are run on all
submissions so scoring is framework-agnostic.

Per-topic rubric (≈8 leaves, weighted):
- Code Development — method-faithful code for each listed condition.
- Code Execution — metrics.json with the declared metric keys across
  the declared seeds.
- Result Analysis — per-hypothesis claim in claims.json with an
  expected/observed/verdict triple backed by metrics evidence.
- Writeup — `README.md ## Agent-produced writeup` of 400-1200 words
  with Method / Results / Verdict / Limitations sections.

## Stage range

Inject at stage 10 (`CODE_GENERATION`), stop after stage 14
(`RESULT_ANALYSIS`), finalize via
`paper_replication/scripts/paperbench_finalize.py`. No manuscript
generation (stages 15-23) — that is scored elsewhere
(`framework_comparison/`).

## Why topics, not papers

PaperBench grades *replication of a known paper* — synopses given.
ARC-Bench grades *experimental problem solving from a question*. The
injected synthesis says "here is the research question and a light
framing" — it does NOT hand the model the answer. This is closer to
what a grad student actually does.

## HITL suggestor contract

After all 25 rc_full runs complete, `hitl_suggestor.py`:

1. For each topic Txx, loads:
   - `submission/README.md`, `submission/claims.json`, `submission/results/metrics.json`
   - `judge_result.json` (which leaves failed)
   - `log/Txx/<run>/full_run/stage-14/analysis.md`
2. Makes ONE LLM call whose prompt says: "You are a senior ML advisor
   writing scripted interventions for a co-pilot re-run. The full-auto
   run produced X; leaves Y, Z, W failed. Write interventions keyed by
   pipeline stage id (5, 8, 9, 14) that would plausibly fix these gaps."
3. Writes `interventions/Txx.json` matching the existing HITL ablation
   format (see `hitl_ablation/interventions/interventions_T01.json`).

This is the **model-evolve** hinge: copilot improvement is measured
specifically against interventions that were auto-generated from the
full-auto gap, not hand-tuned by us.

## Fairness notes

- Every framework sees the same topic string (one sentence) + keywords.
- Autoclaw sees additionally the injected synthesis / hypotheses /
  exp_plan at stages 7-9. This matches PaperBench's "synopsis given"
  contract and mirrors what baselines effectively get via their
  ideation step (AI Scientist v2's ideation runs before its launch).
- AI Scientist v1 may `skipped` topics with no template mapping — this
  is honest about v1's constraint.
- Finalizer + judges are the SAME for all frameworks, so writeup grading
  is not biased by adapter differences.

## Deliverables

`results/<mode>/<topic>/<run_id>/submission/` — PaperBench layout
`results/<mode>/<topic>/<run_id>/judge_result.json` — local judge
`results/<mode>/<topic>/<run_id>/paperbench_judge/` — SimpleJudge (on-demand)
`results_baseline/<framework>/<topic>/<run_id>/…` — same structure
`interventions/<topic>.json` — auto-derived copilot interventions
`analysis/arc_bench_scores.md` — final scoreboard
