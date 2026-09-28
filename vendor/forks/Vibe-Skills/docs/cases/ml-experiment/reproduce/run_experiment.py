from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RepeatedStratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


CASE_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = CASE_ROOT / "deliverables" / "01-data-audit"
OUTPUT_DIR = Path(__file__).resolve().parent
DATASET_PATH = DATA_DIR / "wisconsin-breast-cancer.csv"
DATASET_METADATA_PATH = DATA_DIR / "dataset-metadata.json"
CONFIG_PATH = OUTPUT_DIR / "experiment-config.json"
METRICS_PATH = OUTPUT_DIR / "metrics.json"
FOLD_METRICS_PATH = OUTPUT_DIR / "fold-metrics.csv"
PREDICTIONS_PATH = OUTPUT_DIR / "holdout-predictions.csv"
REPRODUCTION_PATH = OUTPUT_DIR / "reproduction-check.json"

SEED = 20260718
TEST_SIZE = 0.20
CV_SPLITS = 5
CV_REPEATS = 10
POSITIVE_LABEL = 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def combined_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray) -> dict[str, float | int]:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "average_precision": float(average_precision_score(y_true, y_score)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, pos_label=POSITIVE_LABEL, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, pos_label=POSITIVE_LABEL, zero_division=0)),
        "sensitivity": float(recall_score(y_true, y_pred, pos_label=POSITIVE_LABEL, zero_division=0)),
        "specificity": float(tn / (tn + fp)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "n": int(len(y_true)),
    }


def model_specs() -> dict[str, object]:
    return {
        "dummy_stratified": DummyClassifier(strategy="stratified", random_state=SEED),
        "scaled_logistic_regression": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        C=1.0,
                        class_weight=None,
                        max_iter=2000,
                        random_state=SEED,
                        solver="liblinear",
                    ),
                ),
            ]
        ),
    }


def summarize_folds(folds: pd.DataFrame) -> dict[str, object]:
    metric_names = [
        "roc_auc",
        "average_precision",
        "balanced_accuracy",
        "f1",
        "precision",
        "sensitivity",
        "specificity",
    ]
    summary: dict[str, object] = {}
    for model_name, group in folds.groupby("model", sort=True):
        model_summary: dict[str, object] = {"fold_count": int(len(group))}
        for metric in metric_names:
            values = group[metric].astype(float)
            model_summary[metric] = {
                "mean": float(values.mean()),
                "sample_sd": float(values.std(ddof=1)),
                "minimum": float(values.min()),
                "maximum": float(values.max()),
            }
        summary[str(model_name)] = model_summary
    return summary


def main() -> None:
    if not DATASET_PATH.exists() or not DATASET_METADATA_PATH.exists():
        raise FileNotFoundError("Run the data-audit module before the baseline experiment.")

    table = pd.read_csv(DATASET_PATH)
    metadata = json.loads(DATASET_METADATA_PATH.read_text(encoding="utf-8"))
    feature_names = list(metadata["feature_names"])
    required_columns = {"sample_id", "target_malignant", "diagnosis", *feature_names}
    if set(table.columns) != required_columns:
        raise ValueError("Dataset columns do not match the frozen data-audit contract.")
    if table.isna().any().any():
        raise ValueError("The frozen snapshot contains missing values.")
    if sorted(table["target_malignant"].unique().tolist()) != [0, 1]:
        raise ValueError("The target must use 0=benign and 1=malignant.")

    X = table[feature_names]
    y = table["target_malignant"].astype(int)
    sample_ids = table["sample_id"].astype(int)
    train_index, test_index = train_test_split(
        np.arange(len(table)),
        test_size=TEST_SIZE,
        stratify=y,
        random_state=SEED,
    )
    train_index = np.sort(train_index)
    test_index = np.sort(test_index)
    if np.intersect1d(train_index, test_index).size:
        raise RuntimeError("Holdout train and test indices overlap.")
    if len(train_index) + len(test_index) != len(table):
        raise RuntimeError("Holdout split does not cover every row exactly once.")

    X_train = X.iloc[train_index]
    y_train = y.iloc[train_index]
    X_test = X.iloc[test_index]
    y_test = y.iloc[test_index]
    models = model_specs()

    holdout_metrics: dict[str, object] = {}
    prediction_table = pd.DataFrame(
        {
            "sample_id": sample_ids.iloc[test_index].to_numpy(),
            "y_true_malignant": y_test.to_numpy(),
        }
    )
    fitted_models: dict[str, object] = {}
    for model_name, estimator in models.items():
        fitted = clone(estimator).fit(X_train, y_train)
        fitted_models[model_name] = fitted
        y_score = fitted.predict_proba(X_test)[:, list(fitted.classes_).index(POSITIVE_LABEL)]
        y_pred = fitted.predict(X_test)
        holdout_metrics[model_name] = evaluate(y_test.to_numpy(), y_pred, y_score)
        prediction_table[f"{model_name}_probability_malignant"] = y_score
        prediction_table[f"{model_name}_predicted_malignant"] = y_pred.astype(int)

    cv = RepeatedStratifiedKFold(
        n_splits=CV_SPLITS,
        n_repeats=CV_REPEATS,
        random_state=SEED,
    )
    fold_rows: list[dict[str, object]] = []
    for split_number, (fit_position, validation_position) in enumerate(cv.split(X_train, y_train), start=1):
        repeat_number = (split_number - 1) // CV_SPLITS + 1
        fold_number = (split_number - 1) % CV_SPLITS + 1
        X_fit = X_train.iloc[fit_position]
        y_fit = y_train.iloc[fit_position]
        X_validation = X_train.iloc[validation_position]
        y_validation = y_train.iloc[validation_position]
        for model_name, estimator in models.items():
            fitted = clone(estimator).fit(X_fit, y_fit)
            y_score = fitted.predict_proba(X_validation)[:, list(fitted.classes_).index(POSITIVE_LABEL)]
            y_pred = fitted.predict(X_validation)
            result = evaluate(y_validation.to_numpy(), y_pred, y_score)
            fold_rows.append(
                {
                    "repeat": repeat_number,
                    "fold": fold_number,
                    "split_number": split_number,
                    "model": model_name,
                    "train_n": int(len(fit_position)),
                    "validation_n": int(len(validation_position)),
                    **result,
                }
            )

    folds = pd.DataFrame(fold_rows)
    config = {
        "schema_version": "experiment_config_v1",
        "purpose": "Public reproducibility demonstration only; not for clinical use.",
        "dataset": {
            "path": "deliverables/01-data-audit/wisconsin-breast-cancer.csv",
            "sha256": sha256(DATASET_PATH),
            "rows": int(len(table)),
            "features": int(len(feature_names)),
            "target": "target_malignant",
            "positive_label": POSITIVE_LABEL,
            "positive_class": "malignant",
        },
        "software": {
            "python": "3.12.12",
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "random_seed": SEED,
        "holdout": {
            "test_size": TEST_SIZE,
            "stratified": True,
            "train_n": int(len(train_index)),
            "test_n": int(len(test_index)),
            "train_sample_ids": sample_ids.iloc[train_index].astype(int).tolist(),
            "test_sample_ids": sample_ids.iloc[test_index].astype(int).tolist(),
            "train_positive_count": int(y_train.sum()),
            "test_positive_count": int(y_test.sum()),
        },
        "cross_validation": {
            "scope": "holdout training partition only",
            "strategy": "RepeatedStratifiedKFold",
            "n_splits": CV_SPLITS,
            "n_repeats": CV_REPEATS,
            "total_folds_per_model": CV_SPLITS * CV_REPEATS,
        },
        "models": {
            "dummy_stratified": {
                "estimator": "DummyClassifier",
                "parameters": {"strategy": "stratified", "random_state": SEED},
            },
            "scaled_logistic_regression": {
                "estimator": "Pipeline(StandardScaler, LogisticRegression)",
                "parameters": {
                    "C": 1.0,
                    "class_weight": None,
                    "max_iter": 2000,
                    "random_state": SEED,
                    "solver": "liblinear",
                },
            },
        },
        "hyperparameter_search": False,
    }
    metrics = {
        "schema_version": "experiment_metrics_v1",
        "positive_label": POSITIVE_LABEL,
        "positive_class": "malignant",
        "holdout": holdout_metrics,
        "cross_validation": summarize_folds(folds),
        "interpretation_boundary": "Performance estimates describe this fixed public demonstration only.",
    }

    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    METRICS_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")
    folds.to_csv(FOLD_METRICS_PATH, index=False, float_format="%.12g", lineterminator="\n")
    prediction_table.to_csv(PREDICTIONS_PATH, index=False, float_format="%.12g", lineterminator="\n")

    previous = None
    if REPRODUCTION_PATH.exists():
        previous = json.loads(REPRODUCTION_PATH.read_text(encoding="utf-8")).get("combined_sha256")
    required_outputs = [CONFIG_PATH, METRICS_PATH, FOLD_METRICS_PATH, PREDICTIONS_PATH]
    current = combined_digest(required_outputs)
    reproduction = {
        "schema_version": "reproduction_check_v1",
        "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "command": "deliverables/00-environment/reproduce.ps1",
        "required_outputs_exist": all(path.exists() for path in required_outputs),
        "file_sha256": {path.name: sha256(path) for path in required_outputs},
        "combined_sha256": current,
        "previous_combined_sha256": previous,
        "exact_match_previous_run": previous == current if previous is not None else None,
        "split_integrity": {
            "train_test_disjoint": True,
            "all_rows_assigned_once": True,
            "stratification_requested": True,
        },
    }
    REPRODUCTION_PATH.write_text(
        json.dumps(reproduction, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
