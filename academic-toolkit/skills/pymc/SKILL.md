---
name: pymc
description: "贝叶斯建模与推断：层次模型、MCMC(NUTS)、变分推断、后验预测检验与不确定性量化。用于仿真参数校准与结果 UQ（仿真赛事 C 赛道）。"
license: MIT
metadata:
  version: "2.0"
  last-reviewed: "2026-10-01"
  skill-author: K-Dense Inc.
---

<!--ACAT-ADAPTED: 收编自 K-Dense-AI/scientific-agent-skills@36d8f13a1e754618794bf42f417884940077b4ae（MIT，fork FOURTEEN1416）。上游兼容性声明与网络/凭据类依赖在本仓库不适用，执行以本机实装版本为准；溯源见 references/UPSTREAM.md。2026-10-16 仿真建模赛补齐批。2026-11-16 重收编：融入上游 v2.72.0（2d2065f）v2.0 重写——目标 PyMC 6.3.2/PyTensor 3.3.2/ArviZ 1.3.0、ArviZ 1 拆包与 DataTree/PlotCollection API、nuts_sampler="pymc" 与 nuts={...} 新参数、model_averaging v2 预测混合采样语义、compute_log_likelihood 取代 log_likelihood 透传、WAIC 不作 PSIS 失败补救；上游文末引用节未收编。-->
# PyMC Bayesian Modeling

## Version and scope

Targets **PyMC 6.3.2**, **PyTensor 3.3.2**, and **ArviZ 1.3.0**. These are
local Python APIs, with no service endpoint, credentials, or remote inference
required. The native tests use the PyMC NUTS sampler on small synthetic models.
Optional nutpie/JAX samplers, SMC, and production-scale convergence are not
validated by those tests. Record the complete resolved environment, backend,
seeds, preprocessing, and data provenance for a scientific run.

ArviZ 1 splits into base/stats/plots packages, re-exported by `import arviz as az`.
PyMC returns an xarray `DataTree` despite the legacy `return_inferencedata` option
name. `az.summary(..., round_to="none")` returns numerical columns; the default
formats for display. Use `az.plot_ppc_dist`, `az.plot_dist`, and
`az.plot_trace_dist`; save their returned `PlotCollection`, not a separate pyplot
figure. `az.hdi(..., prob=.95)` uses `prob`, with bounds along `ci_bound`.

## Workflow

1. Define the estimand and predictive unit: another measurement, a new patient or
   group, or a future time block. Preserve units, missingness assumptions and
   grouping. Fit any scaling only on training data; reject constant columns.
2. Build a generative model with scientifically calibrated priors and named
   dimensions. Check likelihood support, finite initial log probability,
   design rank, confounding and symmetries before sampling.
3. Run a **prior predictive check** and inspect domain-relevant summaries before
   fitting. A broad prior is not automatically noninformative or plausible.
4. Fit several independent chains with explicit seeds. For reproducible backend
   selection use `nuts_sampler="pymc"`; the automatic choice can prefer installed
   nutpie. `nuts={...}` replaces deprecated `nuts_sampler_kwargs`.
5. Inspect rank R-hat, bulk/tail ESS, estimand-specific MCSE, divergences, energy
   BFMI and sampler-specific tree depth. Fix geometry and initialization before
   simply increasing draws. A clean screen does **not** prove convergence.
6. Generate posterior predictive replicates and inspect residual structure,
   tails, zeros, group effects and time dependence relevant to the question.
   In-sample agreement is not external validation or parameter identifiability.
7. Compare prior sensitivity and parameter recovery on synthetic data. Weakly
   informed scales, correlated parameters, separated logistic data, or mixture
   label switching can survive good MCMC diagnostics. A proper prior may make a
   posterior finite without the likelihood identifying its parameters.
8. Predict using the correct training transform and uncertainty levels. Keep
   `predictions` separate from in-sample `posterior_predictive`. Restore model
   data before recomputing training likelihoods.

See [standard_workflow.md](references/standard_workflow.md) for a complete
bounded API smoke example, [workflows.md](references/workflows.md) for missing
values, scaling, predictive scoring and serialization, and
[model_patterns.md](references/model_patterns.md) for model structures.

## Runnable templates

From the skill directory, run the synthetic linear or hierarchical template:

```bash
uv run --isolated --with "pymc==6.3.2" --with "arviz==1.3.0" --with "pytensor==3.3.2" --with matplotlib --with pandas --with h5netcdf --with h5py python assets/linear_regression_template.py --draws 80 --tune 80 --chains 2 --output-dir linear_smoke
uv run --isolated --with "pymc==6.3.2" --with "arviz==1.3.0" --with "pytensor==3.3.2" --with matplotlib --with pandas --with h5netcdf --with h5py python assets/hierarchical_model_template.py --draws 80 --tune 80 --chains 2 --output-dir hierarchical_smoke
```

These short commands intentionally test execution and artifacts; they are not
adequate evidence of converged scientific estimates. For a real analysis,
inspect priors before fitting and budget chains/draws around diagnostics and
required MCSE. The templates default to four chains and longer runs, but those
counts are not acceptance criteria by themselves.

The hierarchical template predicts an unseen group by drawing group effects
from every hyperposterior draw, sharing each group effect across that group's
new rows, then adding observation noise. Using only population means omits
between-group uncertainty. Centered, non-centered, and partial parameterizations
can each be appropriate; non-centering is not universally superior.

## Diagnostic and comparison helpers

Import the modules from this skill's `scripts/` directory (add that directory to
`sys.path` when working elsewhere). Example fragments below assume fitted data:

```python
from scripts.model_diagnostics import check_diagnostics, create_diagnostic_report
result = check_diagnostics(idata, var_names=["alpha", "beta", "sigma"])
create_diagnostic_report(idata, var_names=["alpha", "beta", "sigma"], output_dir="diagnostics")
```

`check_diagnostics` flags nonfinite statistics and insufficient chains. It reports
missing HMC statistics as unavailable rather than claiming zero divergences.
It uses recorded `reached_max_treedepth`, or an explicit `max_treedepth` matching
the actual sampler; never infer the configured limit from the maximum observed
value. The default ESS floor of 400 is pooled across chains, a screening floor,
not a universal precision target. BFMI below 0.3 is a warning heuristic.

```python
from scripts.model_comparison import compare_models, check_loo_reliability, model_averaging
models = {"linear": idata_linear, "robust": idata_robust}
check_loo_reliability(models, var_name="y_obs")
comparison = compare_models(models, var_name="y_obs")
mixture_draws, weights = model_averaging(models, var_name="y_obs", random_seed=42)
```

Compute pointwise log likelihood while the model contains the training data:
`pm.compute_log_likelihood(idata, model=model)`. Passing `log_likelihood`
through `idata_kwargs` still works in 6.3.2 but now emits a deprecation warning. ArviZ 1 `az.compare` ranks
PSIS-LOO ELPD and has no `ic=` argument. The helper retains `ic="loo"` as an
explicit compatibility option. WAIC is separate and is not a remedy for failed
PSIS diagnostics. Use each LOO result's `good_k` threshold, refit influential
holdouts or choose structured cross-validation when needed.

Comparisons require identical outcomes, ordering, scale, likelihood measure and
predictive unit. A higher ELPD is preferable for that target; inspect paired score
uncertainty and diagnostics before ranking. Stacking weights are predictive
combination weights, **not posterior model probabilities**.

**Version 2 behavior change:** `model_averaging` now samples a predictive mixture
with shape `(sample, *prediction_dimensions)`, preserving both within-model and
between-model variation. It returns weights in input model order and rejects
missing/misaligned predictions or invalid weights. Pointwise averages of paired
posterior draws are not draws from a mixture. Use an explicit `group="predictions"`
for new data; the default is `posterior_predictive`.

## Distribution and inference choices

- Continuous outcomes: Normal or Student-t with scale calibrated to units.
- Counts: Poisson for equidispersion, NegativeBinomial for overdispersion; audit
  the zero-generating mechanism before adding a hurdle or zero-inflation term.
- Binary outcomes: Bernoulli with `logit_p`; priors must remain plausible on the
  probability scale, especially under separation.
- Positive scales: HalfNormal, Exponential or Gamma with domain-specific scales.
- Covariance: `LKJCholeskyCov`; ordinary `dims` labels do not align PyTensor math.
- VI: `pm.fit` provides approximations that can miss modes and underestimate
  uncertainty. Finite ELBO and good ESS on approximation draws do not establish
  posterior accuracy. Compare against MCMC on a feasible representative model.

See [distributions.md](references/distributions.md) for parameter conventions and
[sampling_inference.md](references/sampling_inference.md) for NUTS, discrete
sampling, variational inference, prediction semantics and limitations.

## Primary sources

Reviewed 2026-10-01: [PyMC sampling](https://www.pymc.io/projects/docs/en/stable/api/generated/pymc.sample.html),
[data containers](https://www.pymc.io/projects/docs/en/stable/api/generated/pymc.Data.html),
[forward sampling source](https://www.pymc.io/projects/docs/en/stable/_modules/pymc/sampling/forward.html),
[ArviZ LOO](https://python.arviz.org/projects/stats/en/stable/api/generated/arviz_stats.loo.html),
[comparison](https://python.arviz.org/projects/stats/en/stable/api/generated/arviz_stats.compare.html),
[predictive plots](https://python.arviz.org/projects/plots/en/stable/api/generated/arviz_plots.plot_ppc_dist.html).
