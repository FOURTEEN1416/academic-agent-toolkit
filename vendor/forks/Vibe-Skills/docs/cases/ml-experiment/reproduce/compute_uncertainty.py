from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import balanced_accuracy_score, f1_score, roc_auc_score


CASE_ROOT = Path(__file__).resolve().parents[3]
BASELINE_DIR = CASE_ROOT / "deliverables" / "02-baseline"
PREDICTIONS_PATH = BASELINE_DIR / "holdout-predictions.csv"
FOLDS_PATH = BASELINE_DIR / "fold-metrics.csv"
METRICS_PATH = BASELINE_DIR / "metrics.json"
OUTPUT_DIR = Path(__file__).resolve().parent
UNCERTAINTY_PATH = OUTPUT_DIR / "uncertainty.json"
REVIEW_PATH = OUTPUT_DIR / "statistical-review.md"

BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260819
CONFIDENCE_LEVEL = 0.95
MODELS = ["dummy_stratified", "scaled_logistic_regression"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile_interval(values: np.ndarray) -> list[float]:
    alpha = 1.0 - CONFIDENCE_LEVEL
    lower, upper = np.quantile(values, [alpha / 2, 1 - alpha / 2])
    return [float(lower), float(upper)]


def wilson_interval(successes: int, total: int) -> list[float]:
    if total <= 0:
        raise ValueError("Wilson interval requires a positive denominator.")
    z = float(norm.ppf(1 - (1 - CONFIDENCE_LEVEL) / 2))
    proportion = successes / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    half_width = (
        z
        * np.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2))
        / denominator
    )
    return [float(center - half_width), float(center + half_width)]


def stratified_bootstrap_indices(y_true: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    negative = np.flatnonzero(y_true == 0)
    positive = np.flatnonzero(y_true == 1)
    return np.concatenate(
        [
            rng.choice(negative, size=len(negative), replace=True),
            rng.choice(positive, size=len(positive), replace=True),
        ]
    )


def bootstrap_model(predictions: pd.DataFrame, model: str) -> dict[str, object]:
    y_true = predictions["y_true_malignant"].to_numpy(dtype=int)
    y_score = predictions[f"{model}_probability_malignant"].to_numpy(dtype=float)
    y_pred = predictions[f"{model}_predicted_malignant"].to_numpy(dtype=int)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    distributions = {
        "roc_auc": np.empty(BOOTSTRAP_REPLICATES, dtype=float),
        "balanced_accuracy": np.empty(BOOTSTRAP_REPLICATES, dtype=float),
        "f1": np.empty(BOOTSTRAP_REPLICATES, dtype=float),
    }
    for index in range(BOOTSTRAP_REPLICATES):
        sample = stratified_bootstrap_indices(y_true, rng)
        distributions["roc_auc"][index] = roc_auc_score(y_true[sample], y_score[sample])
        distributions["balanced_accuracy"][index] = balanced_accuracy_score(
            y_true[sample], y_pred[sample]
        )
        distributions["f1"][index] = f1_score(
            y_true[sample], y_pred[sample], pos_label=1, zero_division=0
        )

    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    point_estimates = {
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "sensitivity": float(tp / (tp + fn)),
        "specificity": float(tn / (tn + fp)),
    }
    return {
        "n": int(len(y_true)),
        "negative_n": int((y_true == 0).sum()),
        "positive_n": int((y_true == 1).sum()),
        "point_estimates": point_estimates,
        "stratified_bootstrap_percentile_95_interval": {
            metric: percentile_interval(values) for metric, values in distributions.items()
        },
        "wilson_95_interval": {
            "sensitivity": wilson_interval(tp, tp + fn),
            "specificity": wilson_interval(tn, tn + fp),
        },
        "confusion_counts": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


def cross_validation_variability(folds: pd.DataFrame) -> dict[str, object]:
    output: dict[str, object] = {}
    for model, model_rows in folds.groupby("model", sort=True):
        repeat_means = (
            model_rows.groupby("repeat", sort=True)[
                ["roc_auc", "balanced_accuracy", "f1"]
            ]
            .mean()
            .reset_index()
        )
        output[str(model)] = {
            "fold_count": int(len(model_rows)),
            "repeat_count": int(len(repeat_means)),
            "fold_metric_variability": {
                metric: {
                    "mean": float(model_rows[metric].mean()),
                    "sample_sd": float(model_rows[metric].std(ddof=1)),
                    "minimum": float(model_rows[metric].min()),
                    "maximum": float(model_rows[metric].max()),
                }
                for metric in ["roc_auc", "balanced_accuracy", "f1"]
            },
            "repeat_mean_empirical_95_interval": {
                metric: percentile_interval(repeat_means[metric].to_numpy(dtype=float))
                for metric in ["roc_auc", "balanced_accuracy", "f1"]
            },
        }
    return output


def format_interval(interval: list[float]) -> str:
    return f"[{interval[0]:.3f}, {interval[1]:.3f}]"


def main() -> None:
    predictions = pd.read_csv(PREDICTIONS_PATH)
    folds = pd.read_csv(FOLDS_PATH)
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))

    holdout = {model: bootstrap_model(predictions, model) for model in MODELS}
    cv_variability = cross_validation_variability(folds)
    payload = {
        "schema_version": "uncertainty_analysis_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "confidence_level": CONFIDENCE_LEVEL,
        "source_files": {
            "holdout_predictions": {
                "path": "deliverables/02-baseline/holdout-predictions.csv",
                "sha256": sha256(PREDICTIONS_PATH),
            },
            "fold_metrics": {
                "path": "deliverables/02-baseline/fold-metrics.csv",
                "sha256": sha256(FOLDS_PATH),
            },
            "metrics": {
                "path": "deliverables/02-baseline/metrics.json",
                "sha256": sha256(METRICS_PATH),
            },
        },
        "methods": {
            "holdout_primary_metrics": {
                "method": "class-stratified nonparametric percentile bootstrap",
                "replicates": BOOTSTRAP_REPLICATES,
                "seed": BOOTSTRAP_SEED,
                "unit": "holdout sample",
                "assumption": "The fixed holdout rows approximate exchangeable observations within each observed class; intervals are conditional on the fitted model and frozen split.",
            },
            "holdout_sensitivity_specificity": {
                "method": "Wilson score interval",
                "unit": "class-conditional holdout outcome",
                "assumption": "Each class-conditional outcome is treated as a binomial observation for the fixed model and split.",
            },
            "cross_validation": {
                "method": "descriptive fold SD, range, and empirical interval across ten repeat means",
                "unit": "validation fold or repeat mean",
                "assumption": "Repeated folds reuse observations and are not independent; these summaries are variability descriptions, not formal population confidence intervals.",
            },
        },
        "holdout": holdout,
        "cross_validation": cv_variability,
        "formal_significance_test": {
            "performed": False,
            "reason": "The repeated folds are dependent and the single fixed holdout does not establish external superiority. Descriptive paired differences and uncertainty are reported without a p-value.",
        },
        "claim_boundary": "Intervals quantify conditional uncertainty in this public demonstration and do not establish clinical validity, deployment performance, or transportability.",
    }
    UNCERTAINTY_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    logistic = holdout["scaled_logistic_regression"]
    dummy = holdout["dummy_stratified"]
    logistic_cv = cv_variability["scaled_logistic_regression"]
    dummy_cv = cv_variability["dummy_stratified"]
    report = f"""# Statistical Review

## Decision

The evidence supports descriptive reporting with conditional uncertainty intervals. It does not support a formal claim that the logistic model is clinically superior, externally valid, or ready for deployment. No p-value or formal significance test is reported.

## Sources and Units

- Holdout: {logistic['n']} samples ({logistic['positive_n']} malignant and {logistic['negative_n']} benign), evaluated once after all preprocessing and model fitting were confined to the training partition.
- Cross-validation: 5 folds repeated 10 times on the 455-sample training partition, yielding 50 validation folds per model.
- Positive class: malignant (`target_malignant = 1`).

## Holdout Estimates and Uncertainty

| Model | ROC AUC (95% bootstrap interval) | Balanced accuracy (95% bootstrap interval) | F1 (95% bootstrap interval) |
| --- | ---: | ---: | ---: |
| Scaled logistic regression | {logistic['point_estimates']['roc_auc']:.3f} {format_interval(logistic['stratified_bootstrap_percentile_95_interval']['roc_auc'])} | {logistic['point_estimates']['balanced_accuracy']:.3f} {format_interval(logistic['stratified_bootstrap_percentile_95_interval']['balanced_accuracy'])} | {logistic['point_estimates']['f1']:.3f} {format_interval(logistic['stratified_bootstrap_percentile_95_interval']['f1'])} |
| Stratified dummy | {dummy['point_estimates']['roc_auc']:.3f} {format_interval(dummy['stratified_bootstrap_percentile_95_interval']['roc_auc'])} | {dummy['point_estimates']['balanced_accuracy']:.3f} {format_interval(dummy['stratified_bootstrap_percentile_95_interval']['balanced_accuracy'])} | {dummy['point_estimates']['f1']:.3f} {format_interval(dummy['stratified_bootstrap_percentile_95_interval']['f1'])} |

For the scaled logistic model, sensitivity was {logistic['point_estimates']['sensitivity']:.3f} with Wilson 95% interval {format_interval(logistic['wilson_95_interval']['sensitivity'])}; specificity was {logistic['point_estimates']['specificity']:.3f} with Wilson 95% interval {format_interval(logistic['wilson_95_interval']['specificity'])}. The confusion counts were TN={logistic['confusion_counts']['tn']}, FP={logistic['confusion_counts']['fp']}, FN={logistic['confusion_counts']['fn']}, TP={logistic['confusion_counts']['tp']}.

The bootstrap resamples holdout observations separately within the observed benign and malignant classes for 10,000 fixed-seed replicates. These percentile intervals are conditional on this fitted model and frozen split. They do not include uncertainty from collecting another cohort, changing sites or devices, or refitting after model selection.

## Cross-Validation Variability

| Model | ROC AUC, mean (fold SD) | Balanced accuracy, mean (fold SD) | F1, mean (fold SD) |
| --- | ---: | ---: | ---: |
| Scaled logistic regression | {logistic_cv['fold_metric_variability']['roc_auc']['mean']:.3f} ({logistic_cv['fold_metric_variability']['roc_auc']['sample_sd']:.3f}) | {logistic_cv['fold_metric_variability']['balanced_accuracy']['mean']:.3f} ({logistic_cv['fold_metric_variability']['balanced_accuracy']['sample_sd']:.3f}) | {logistic_cv['fold_metric_variability']['f1']['mean']:.3f} ({logistic_cv['fold_metric_variability']['f1']['sample_sd']:.3f}) |
| Stratified dummy | {dummy_cv['fold_metric_variability']['roc_auc']['mean']:.3f} ({dummy_cv['fold_metric_variability']['roc_auc']['sample_sd']:.3f}) | {dummy_cv['fold_metric_variability']['balanced_accuracy']['mean']:.3f} ({dummy_cv['fold_metric_variability']['balanced_accuracy']['sample_sd']:.3f}) | {dummy_cv['fold_metric_variability']['f1']['mean']:.3f} ({dummy_cv['fold_metric_variability']['f1']['sample_sd']:.3f}) |

Fold standard deviations and empirical intervals across the ten repeat means describe resampling variability. Because observations recur across folds and repeats, those values are not treated as independent-sample confidence intervals and are not used for a hypothesis test.

## Assumptions and Interpretation

1. The class-stratified bootstrap treats holdout observations as exchangeable within each observed class.
2. Wilson intervals treat class-conditional outcomes as binomial observations for the fixed model.
3. The holdout was used once for the frozen baseline evaluation; no hyperparameter search or post-hoc threshold tuning was performed.
4. The dataset lacks site, time, device, and external-cohort identifiers, so transportability and group leakage cannot be assessed.
5. High performance on this small curated dataset is evidence of a reproducible software workflow, not evidence of clinical usefulness.

## Reporting Rule

Report point estimates with the named interval method, show cross-validation mean and fold SD, disclose all confusion counts, and keep every conclusion within the non-clinical demonstration boundary. Do not attach a significance claim to the observed model difference.
"""
    REVIEW_PATH.write_text(report, encoding="utf-8")

    baseline_logistic = metrics["holdout"]["scaled_logistic_regression"]
    for metric in ["roc_auc", "balanced_accuracy", "f1", "sensitivity", "specificity"]:
        if not np.isclose(
            baseline_logistic[metric], logistic["point_estimates"][metric], rtol=0, atol=1e-12
        ):
            raise RuntimeError(f"Point estimate mismatch for {metric}.")


if __name__ == "__main__":
    main()
