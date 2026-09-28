# ARC-Bench Quantum Domain

Ten open-ended quantum machine learning and variational quantum algorithm topics that run on the autoclaw native sandbox (Qiskit 2.x stack, statevector and finite-shot simulation, no GPU, no IBM Quantum hardware, no external agent).

Added in branch `feat/quantum-domain`. Same `rc_full` runner that drives the ML domain (`run_bench.py`), same stages 10 to 14, same `paperbench_finalize` + `judge` post-processing.

## Layout

```
config/quantum/
  topics.yaml              registry of 10 topics (Q01-Q10)
  manifests/Q0N.yaml       per-topic manifest: synthesis, hypotheses, experiment_design, rubric_path
  rubrics/Q0N.json         per-topic 3-bucket rubric (code / exec / results)
  README.md                this file

results/rc_full/Q0N/<run_id>/
  bench_meta.json          run config and bench inputs
  judge_result.json        per-leaf grades + overall_score
  claims.json              extracted quantitative claims
  RESULTS_README.md        auto-generated run summary
  submission/              trimmed agent output (code + figures + writeup)

log/rc_full/Q0N/<run_id>/full_run/
  full stage-07..14 archive. Gitignored.
```

## Topic registry

| ID  | Theme                              | Primary metric                  | Direction |
|-----|------------------------------------|---------------------------------|-----------|
| Q01 | Data encoding strategies for VQC   | test_accuracy                   | maximize  |
| Q02 | CNOT ablation in VQC               | test_accuracy                   | maximize  |
| Q03 | Classical optimizers for VQE on H2 | shots_to_chemical_accuracy      | minimize  |
| Q04 | Data re-uploading depth scaling    | test_mse                        | minimize  |
| Q05 | Barren plateau cost locality       | log_gradient_variance           | maximize  |
| Q06 | NN warm-start for QAOA MaxCut      | iterations_to_target_ratio      | minimize  |
| Q07 | MPS classifier vs NN baselines     | test_accuracy                   | maximize  |
| Q08 | Layerwise vs end-to-end VQC        | test_accuracy                   | maximize  |
| Q09 | Noise-aware VQC training           | test_accuracy                   | maximize  |
| Q10 | Quantum autoencoder fidelity       | reconstruction_fidelity         | maximize  |

Full topic strings live in `topics.yaml`. Per-topic hypotheses H1 / H2 / H3, conditions, baselines, and seed counts live in `manifests/Q0N.yaml`.

## Latest single-run scores (rc_full, gpt-5.3-codex + gpt-4o judge)

Methodology: one latest run per topic, no best-of-N cherry picking.

| ID  | Score | Run timestamp           |
|-----|-------|-------------------------|
| Q01 | 0.709 | 20260517-192423         |
| Q02 | 0.430 | 20260517-192423         |
| Q03 | 0.757 | 20260517-212933         |
| Q04 | 0.571 | 20260517-212933         |
| Q05 | 0.576 | 20260517-212933         |
| Q06 | 0.317 | 20260517-212933         |
| Q07 | 0.513 | 20260517-212933         |
| Q08 | 0.421 | 20260517-212720         |
| Q09 | 0.145 | 20260517-192423         |
| Q10 | 0.421 | 20260517-192422         |
| **Mean** | **0.486** |                |

Stage-15 PROCEED gate requires at least 2 baselines plus the proposed method, so every quantum manifest declares two or more baselines (random / random_init_control / classical MLP / logistic-regression as appropriate).

## How to run

Single topic:
```bash
python experiments/arc_bench/scripts/run_bench.py \
  --mode rc_full \
  --topic Q03 \
  --runs 1
```

All quantum topics:
```bash
python experiments/arc_bench/scripts/run_bench.py \
  --mode rc_full \
  --domain quantum \
  --runs 1
```

The runner reads `base_config.yaml`, expands `Q0N` to the matching `manifests/Q0N.yaml` and `rubrics/Q0N.json`, registers `Q -> quantum` in `prepare_run.py`, and drops outputs under `results/rc_full/Q0N/<run_id>/`.

## Skill

Agents pick up Qiskit-specific patterns from a domain skill:

```
researchclaw/skills/builtin/domain/quantum-qiskit/SKILL.md
```

Triggered on stages 10 and 13 whenever the topic synthesis or experiment plan mentions Qiskit, VQE, VQC, QAOA, EfficientSU2, ZZFeatureMap, MPS, noise model, etc. The skill is intentionally generic. It contains no Q-topic narratives and no bench-specific signal that would leak rubric information to the agent.

Key patterns it documents:
1. Imports for Qiskit 2.x (StatevectorEstimator, StatevectorSampler, BackendSamplerV2, AerSimulator).
2. Data-encoding feature maps (ZFeatureMap, ZZFeatureMap, StatePreparation).
3. Variational ansatze (EfficientSU2, n-local).
4. VQC training with `qiskit_machine_learning.VQC.fit`.
5. Manual VQE loop pattern. `qiskit_algorithms.VQE` is broken under Qiskit 2.x because `qiskit_nature.second_q.algorithms` imports the removed `BaseEstimator`. The skill shows the StatevectorEstimator + `optimizer.minimize()` replacement.
6. MPS-structured circuits via `AerSimulator(method='matrix_product_state', matrix_product_state_max_bond_dimension=chi)`.
7. Noise model wiring. `qiskit_machine_learning.Sampler` does not accept a `noise_model` kwarg, so noisy training routes through `BackendSamplerV2(backend=AerSimulator(noise_model=...))`.
8. Qiskit 2.x compatibility notes and a table of common errors with fixes.

## Dependencies

Pinned in `config/base_config.yaml` `allowed_imports`:

```
qiskit, qiskit_aer, qiskit_algorithms, qiskit_machine_learning, qiskit_nature, pyscf
numpy, scipy, matplotlib, sklearn, pandas, statsmodels, networkx, skimage
```

The agent runs inside a sandbox so it cannot install new packages mid-run. Anything outside this list fails the import gate at stage 10.

## Caveats

- **LLM nondeterminism.** Single-run scores carry std around 0.2 to 0.4. Compare topics with caution. The committed runs are one snapshot. A rerun on the same manifest can swing materially.
- **Q09 is hard.** Noise-aware training under our sandbox time budget regularly bottoms out near the random-prediction floor. The 0.145 score reflects this. The skill already documents the correct noise model wiring, so the failure mode is not a missing pattern but a genuinely thin training signal under the configured noise rates.
- **Multi-file consistency.** Topics such as Q08 require the agent to keep `main.py`, `model.py`, `evaluate.py`, etc. in sync. When the agent gets out of sync, the run fails at stage 12 with a missing-import error. This is an agent capability ceiling and is not fixable by skill updates.
- **Code bucket weight.** Rubrics carry a Code Development bucket (weight 2 of 7), but the autoclaw default `judge.py` operates in `results_only` mode and skips code-leaf grading. Code leaves are kept in the rubric so that a future code-aware judge can score them without re-authoring.

## Adding a new quantum topic

1. Add an entry to `topics.yaml` with a `Q11+` id, a verbose topic string, domains, metric_key, metric_direction.
2. Write `manifests/Q11.yaml` with synthesis (research question + skill pointer + protocol), hypotheses (H1 / H2 / H3), experiment_design (conditions, at least 2 baselines, metrics, datasets, compute_requirements), and a `rubric_path` pointing to `rubrics/Q11.json`.
3. Write `rubrics/Q11.json` as a 3-bucket tree (code / exec / results), 25 / 25 / 50 weights, with 9 leaves total.
4. Make sure `scripts/prepare_run.py` `_PREFIX_MAP` and `scripts/judge.py` `_PREFIX_MAP` both map `Q -> quantum`. They already do for Q01-Q10.
5. Run end-to-end with `--runs 1` first to shake out manifest typos before committing.
