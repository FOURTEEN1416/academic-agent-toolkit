from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import sklearn
from sklearn.datasets import load_breast_cancer


OUTPUT_DIR = Path(__file__).resolve().parent
DATASET_PATH = OUTPUT_DIR / "wisconsin-breast-cancer.csv"
METADATA_PATH = OUTPUT_DIR / "dataset-metadata.json"
DISTRIBUTION_PATH = OUTPUT_DIR / "target-distribution.csv"
REPORT_PATH = OUTPUT_DIR / "data-audit.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    dataset = load_breast_cancer(as_frame=True)
    features = dataset.data.copy()
    target_malignant = (dataset.target == 0).astype("int8")

    table = features.copy()
    table.insert(0, "sample_id", range(len(table)))
    table["target_malignant"] = target_malignant
    table["diagnosis"] = target_malignant.map({1: "malignant", 0: "benign"})
    table.to_csv(DATASET_PATH, index=False, lineterminator="\n")

    feature_duplicate_count = int(
        table.drop(columns=["sample_id", "diagnosis"]).duplicated().sum()
    )
    missing_cell_count = int(table.isna().sum().sum())
    infinite_cell_count = int(
        pd.DataFrame(features).isin([float("inf"), float("-inf")]).sum().sum()
    )
    target_counts = (
        table.groupby(["target_malignant", "diagnosis"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    target_counts["proportion"] = target_counts["count"] / len(table)
    target_counts.to_csv(DISTRIBUTION_PATH, index=False, lineterminator="\n")

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    metadata = {
        "schema_version": "dataset_metadata_v1",
        "generated_at": generated_at,
        "source": {
            "loader": "sklearn.datasets.load_breast_cancer",
            "download_required": False,
            "scikit_learn_version": sklearn.__version__,
            "loader_target_encoding": {"0": "malignant", "1": "benign"},
            "case_target_encoding": {"1": "malignant", "0": "benign"},
        },
        "shape": {"rows": int(table.shape[0]), "columns": int(table.shape[1])},
        "model_feature_count": int(features.shape[1]),
        "feature_names": list(features.columns),
        "quality": {
            "missing_cell_count": missing_cell_count,
            "infinite_feature_cell_count": infinite_cell_count,
            "duplicate_feature_and_target_rows": feature_duplicate_count,
            "unique_sample_id_count": int(table["sample_id"].nunique()),
            "target_class_count": int(table["target_malignant"].nunique()),
        },
        "target_distribution": [
            {
                "target_malignant": int(row.target_malignant),
                "diagnosis": str(row.diagnosis),
                "count": int(row.count),
                "proportion": float(row.proportion),
            }
            for row in target_counts.itertuples(index=False)
        ],
        "files": {
            "dataset": DATASET_PATH.name,
            "target_distribution": DISTRIBUTION_PATH.name,
        },
        "dataset_sha256": sha256(DATASET_PATH),
    }
    METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    malignant = next(item for item in metadata["target_distribution"] if item["target_malignant"] == 1)
    benign = next(item for item in metadata["target_distribution"] if item["target_malignant"] == 0)
    report = f"""# Data and Method Audit

## Scope

This case uses the Wisconsin Diagnostic Breast Cancer dataset bundled with scikit-learn. The snapshot is a public reproducibility demonstration, not a clinical validation dataset, diagnostic device, or basis for patient care.

## Materialization

- Loader: `sklearn.datasets.load_breast_cancer`
- scikit-learn: `{sklearn.__version__}`
- External download: no
- Rows: {metadata['shape']['rows']}
- Model features: {metadata['model_feature_count']}
- Exported columns: {metadata['shape']['columns']} (sample ID, 30 model features, binary target, diagnosis label)
- Dataset SHA-256: `{metadata['dataset_sha256']}`

The loader encodes malignant as 0 and benign as 1. This case deliberately flips that encoding so `target_malignant = 1` is the positive class used by all metrics, curves, reports, and slides.

## Quality Checks

| Check | Result | Interpretation |
| --- | ---: | --- |
| Missing cells | {missing_cell_count} | No imputation is required for this snapshot. |
| Infinite feature values | {infinite_cell_count} | No non-finite values were found. |
| Duplicate feature and target rows | {feature_duplicate_count} | Exact duplicate records do not inflate the sample count. |
| Unique sample IDs | {metadata['quality']['unique_sample_id_count']} / {metadata['shape']['rows']} | The generated row identifier is unique and excluded from modeling. |
| Target classes | {metadata['quality']['target_class_count']} | Binary stratification is supported. |

## Target Balance

| Diagnosis | Count | Proportion |
| --- | ---: | ---: |
| Malignant | {malignant['count']} | {malignant['proportion']:.3f} |
| Benign | {benign['count']} | {benign['proportion']:.3f} |

The class ratio is uneven but not extreme. The frozen experiment therefore uses stratification and reports balanced accuracy and F1 in addition to ROC AUC.

## Types and Modeling Boundary

- All 30 model features are numeric floating-point measurements.
- `sample_id`, `diagnosis`, and `target_malignant` are not model inputs.
- Scaling must be fitted inside each training fold through a pipeline; fitting it before splitting would leak validation information.
- The target is known only for evaluation and is never used by preprocessing.

## Leakage and Generalization Risks

1. Random stratified splits test interpolation within this one curated dataset, not transport to another hospital, device, time period, or population.
2. The 30 features are related measurements derived from the same digitized cell-nucleus images. They must remain grouped by sample and may not be split into independent observations.
3. No patient, site, acquisition-date, or external-cohort fields are available, so group leakage and temporal transport cannot be tested.
4. Model selection is frozen in advance. No hyperparameter search is permitted, which limits tuning leakage but does not create external validity.

## Downstream Requirements

- Use a fixed stratified holdout split and repeated stratified cross-validation.
- Compare a stratified `DummyClassifier` with `StandardScaler` plus `LogisticRegression`.
- Preserve `target_malignant = 1` as the positive class everywhere.
- Record split indices or sample IDs so train/test disjointness can be checked.
- Report variability and uncertainty with their method and assumptions; do not infer clinical utility or formal superiority from this demonstration alone.
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
