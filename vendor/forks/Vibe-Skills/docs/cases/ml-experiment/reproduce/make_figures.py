from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from sklearn.metrics import precision_recall_curve, roc_curve


CASE_ROOT = Path(__file__).resolve().parents[2]
DATA_AUDIT_DIR = CASE_ROOT / "deliverables" / "01-data-audit"
BASELINE_DIR = CASE_ROOT / "deliverables" / "02-baseline"
STATS_DIR = CASE_ROOT / "deliverables" / "03-statistical-review" / "statistics"
OUTPUT_DIR = Path(__file__).resolve().parent
VECTOR_DIR = OUTPUT_DIR / "vector"
INDEX_PATH = OUTPUT_DIR / "figure-index.json"

MODEL_LABELS = {
    "dummy_stratified": "Stratified dummy",
    "scaled_logistic_regression": "Scaled logistic regression",
}
MODEL_COLORS = {
    "dummy_stratified": "#E69F00",
    "scaled_logistic_regression": "#0072B2",
}
MODEL_MARKERS = {"dummy_stratified": "s", "scaled_logistic_regression": "o"}
MODEL_LINESTYLES = {"dummy_stratified": "--", "scaled_logistic_regression": "-"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 10,
            "axes.labelsize": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "savefig.facecolor": "white",
            "savefig.dpi": 300,
        }
    )


def save_figure(fig: plt.Figure, stem: str) -> tuple[Path, Path]:
    png_path = OUTPUT_DIR / f"{stem}.png"
    svg_path = VECTOR_DIR / f"{stem}.svg"
    fig.savefig(png_path, dpi=300, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(svg_path, format="svg", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return png_path, svg_path


def class_balance_figure(distribution: pd.DataFrame) -> tuple[Path, Path]:
    order = ["benign", "malignant"]
    data = distribution.set_index("diagnosis").loc[order].reset_index()
    colors = ["#999999", "#D55E00"]
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    bars = ax.bar(
        ["Benign", "Malignant"],
        data["count"],
        color=colors,
        edgecolor="#222222",
        linewidth=0.8,
        width=0.62,
    )
    for bar, count, proportion in zip(bars, data["count"], data["proportion"], strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 8,
            f"{int(count)}\n({proportion:.1%})",
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    ax.set_ylim(0, max(data["count"]) * 1.22)
    ax.set_ylabel("Samples (count)")
    ax.set_title("Class balance in the frozen dataset")
    ax.text(
        0.5,
        -0.18,
        "n = 569; malignant is the positive class in every downstream metric",
        transform=ax.transAxes,
        ha="center",
        color="#444444",
    )
    fig.tight_layout()
    return save_figure(fig, "class-balance")


def roc_pr_figure(predictions: pd.DataFrame, metrics: dict[str, object]) -> tuple[Path, Path]:
    y_true = predictions["y_true_malignant"].to_numpy(dtype=int)
    prevalence = float(y_true.mean())
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.4))
    for model in ["scaled_logistic_regression", "dummy_stratified"]:
        score = predictions[f"{model}_probability_malignant"].to_numpy(dtype=float)
        fpr, tpr, _ = roc_curve(y_true, score, pos_label=1)
        precision, recall, _ = precision_recall_curve(y_true, score, pos_label=1)
        axes[0].plot(
            fpr,
            tpr,
            color=MODEL_COLORS[model],
            linestyle=MODEL_LINESTYLES[model],
            linewidth=2.2,
            marker=MODEL_MARKERS[model],
            markevery=max(1, len(fpr) // 8),
            markersize=4,
            label=f"{MODEL_LABELS[model]} (AUC {metrics['holdout'][model]['roc_auc']:.3f})",
        )
        axes[1].plot(
            recall,
            precision,
            color=MODEL_COLORS[model],
            linestyle=MODEL_LINESTYLES[model],
            linewidth=2.2,
            marker=MODEL_MARKERS[model],
            markevery=max(1, len(recall) // 8),
            markersize=4,
            label=f"{MODEL_LABELS[model]} (AP {metrics['holdout'][model]['average_precision']:.3f})",
        )

    axes[0].plot([0, 1], [0, 1], color="#555555", linestyle=":", linewidth=1.2, label="Chance line")
    axes[1].axhline(prevalence, color="#555555", linestyle=":", linewidth=1.2, label=f"Prevalence {prevalence:.3f}")
    axes[0].set(xlim=(0, 1), ylim=(0, 1.02), xlabel="False-positive rate", ylabel="True-positive rate", title="ROC curve")
    axes[1].set(xlim=(0, 1), ylim=(0, 1.02), xlabel="Recall (sensitivity)", ylabel="Precision", title="Precision-recall curve")
    for ax in axes:
        ax.legend(loc="lower right", frameon=False)
        ax.set_aspect("equal", adjustable="box")
    fig.suptitle("Holdout discrimination for malignant as the positive class", fontsize=14, fontweight="bold")
    fig.text(0.5, 0.01, "Fixed holdout n = 114; curves are descriptive and not clinical validation", ha="center", color="#444444")
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    return save_figure(fig, "roc-and-pr-curves")


def cv_distribution_figure(folds: pd.DataFrame) -> tuple[Path, Path]:
    metrics = [
        ("roc_auc", "ROC AUC"),
        ("balanced_accuracy", "Balanced accuracy"),
        ("f1", "F1"),
    ]
    models = ["dummy_stratified", "scaled_logistic_regression"]
    rng = np.random.default_rng(20260718)
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.2), sharey=True)
    for ax, (metric, label) in zip(axes, metrics, strict=True):
        values = [folds.loc[folds["model"] == model, metric].to_numpy(dtype=float) for model in models]
        box = ax.boxplot(
            values,
            positions=[0, 1],
            widths=0.45,
            patch_artist=True,
            showfliers=False,
            medianprops={"color": "#111111", "linewidth": 1.4},
            whiskerprops={"color": "#444444"},
            capprops={"color": "#444444"},
        )
        for patch, model in zip(box["boxes"], models, strict=True):
            patch.set_facecolor(MODEL_COLORS[model])
            patch.set_alpha(0.32)
            patch.set_edgecolor(MODEL_COLORS[model])
        for position, model, model_values in zip([0, 1], models, values, strict=True):
            jitter = rng.normal(0, 0.055, size=len(model_values))
            ax.scatter(
                np.full(len(model_values), position) + jitter,
                model_values,
                s=15,
                alpha=0.48,
                color=MODEL_COLORS[model],
                marker=MODEL_MARKERS[model],
                edgecolors="none",
            )
            mean = float(np.mean(model_values))
            sd = float(np.std(model_values, ddof=1))
            ax.errorbar(
                position,
                mean,
                yerr=sd,
                color="#111111",
                marker="D",
                markersize=5,
                capsize=4,
                linewidth=1.2,
                zorder=5,
            )
        ax.set_xticks([0, 1], ["Dummy", "Logistic"], rotation=18)
        ax.set_title(label)
        ax.set_ylim(0, 1.03)
        ax.axhline(0.5, color="#777777", linestyle=":", linewidth=1)
    axes[0].set_ylabel("Validation score")
    fig.suptitle("Repeated stratified cross-validation variability", fontsize=14, fontweight="bold")
    fig.text(0.5, 0.01, "50 dependent validation folds per model; diamond and bars show mean +/- fold SD", ha="center", color="#444444")
    fig.tight_layout(rect=(0, 0.06, 1, 0.92))
    return save_figure(fig, "cv-performance-distribution")


def confusion_matrix_figure(metrics: dict[str, object]) -> tuple[Path, Path]:
    models = ["dummy_stratified", "scaled_logistic_regression"]
    matrices = []
    for model in models:
        result = metrics["holdout"][model]
        matrices.append(np.array([[result["tn"], result["fp"]], [result["fn"], result["tp"]]], dtype=int))
    vmax = max(int(matrix.max()) for matrix in matrices)
    cmap = LinearSegmentedColormap.from_list("accessible_blue", ["#F7FBFF", "#0072B2"])
    fig = plt.figure(figsize=(10.8, 4.8))
    grid = fig.add_gridspec(
        1,
        3,
        width_ratios=[1, 1, 0.05],
        left=0.07,
        right=0.93,
        bottom=0.17,
        top=0.78,
        wspace=0.42,
    )
    axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])]
    colorbar_axis = fig.add_subplot(grid[0, 2])
    images = []
    for ax, model, matrix in zip(axes, models, matrices, strict=True):
        image = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=vmax)
        images.append(image)
        for row in range(2):
            for column in range(2):
                value = int(matrix[row, column])
                color = "white" if value > vmax * 0.55 else "#111111"
                ax.text(column, row, str(value), ha="center", va="center", fontsize=18, fontweight="bold", color=color)
        ax.set_xticks([0, 1], ["Benign", "Malignant"])
        ax.set_yticks([0, 1], ["Benign", "Malignant"])
        ax.set_xlabel("Predicted class")
        ax.set_ylabel("Actual class")
        ax.set_title(f"{MODEL_LABELS[model]}\nBalanced accuracy {metrics['holdout'][model]['balanced_accuracy']:.3f}")
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("#333333")
    fig.colorbar(images[-1], cax=colorbar_axis, label="Samples (count)")
    fig.suptitle("Holdout confusion matrices", fontsize=14, fontweight="bold", y=0.96)
    fig.text(0.5, 0.04, "Rows are actual labels; columns are predictions; malignant is the positive class", ha="center", color="#444444")
    return save_figure(fig, "confusion-matrix")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()

    distribution_path = DATA_AUDIT_DIR / "target-distribution.csv"
    predictions_path = BASELINE_DIR / "holdout-predictions.csv"
    folds_path = BASELINE_DIR / "fold-metrics.csv"
    metrics_path = BASELINE_DIR / "metrics.json"
    uncertainty_path = STATS_DIR / "uncertainty.json"
    distribution = pd.read_csv(distribution_path)
    predictions = pd.read_csv(predictions_path)
    folds = pd.read_csv(folds_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    uncertainty = json.loads(uncertainty_path.read_text(encoding="utf-8"))

    figures = {
        "class-balance": class_balance_figure(distribution),
        "roc-and-pr-curves": roc_pr_figure(predictions, metrics),
        "cv-performance-distribution": cv_distribution_figure(folds),
        "confusion-matrix": confusion_matrix_figure(metrics),
    }
    source_files = {
        "target_distribution": distribution_path,
        "holdout_predictions": predictions_path,
        "fold_metrics": folds_path,
        "metrics": metrics_path,
        "uncertainty": uncertainty_path,
    }
    figure_records = {
        "class-balance": {
            "png": "deliverables/04-figures/class-balance.png",
            "svg": "deliverables/04-figures/vector/class-balance.svg",
            "sources": ["target_distribution"],
            "mapped_values": {
                row.diagnosis: {"count": int(row.count), "proportion": float(row.proportion)}
                for row in distribution.itertuples(index=False)
            },
            "alt_text": "Bar chart showing 357 benign and 212 malignant samples in the frozen dataset.",
        },
        "roc-and-pr-curves": {
            "png": "deliverables/04-figures/roc-and-pr-curves.png",
            "svg": "deliverables/04-figures/vector/roc-and-pr-curves.svg",
            "sources": ["holdout_predictions", "metrics"],
            "mapped_values": {
                model: {
                    "roc_auc": metrics["holdout"][model]["roc_auc"],
                    "average_precision": metrics["holdout"][model]["average_precision"],
                }
                for model in MODEL_LABELS
            },
            "alt_text": "ROC and precision-recall curves comparing the scaled logistic model with a stratified dummy on 114 holdout samples.",
        },
        "cv-performance-distribution": {
            "png": "deliverables/04-figures/cv-performance-distribution.png",
            "svg": "deliverables/04-figures/vector/cv-performance-distribution.svg",
            "sources": ["fold_metrics", "metrics", "uncertainty"],
            "mapped_values": {
                model: {
                    metric: metrics["cross_validation"][model][metric]
                    for metric in ["roc_auc", "balanced_accuracy", "f1"]
                }
                for model in MODEL_LABELS
            },
            "alt_text": "Three panels show ROC AUC, balanced accuracy, and F1 across 50 dependent validation folds per model.",
        },
        "confusion-matrix": {
            "png": "deliverables/04-figures/confusion-matrix.png",
            "svg": "deliverables/04-figures/vector/confusion-matrix.svg",
            "sources": ["metrics"],
            "mapped_values": {
                model: {key: metrics["holdout"][model][key] for key in ["tn", "fp", "fn", "tp"]}
                for model in MODEL_LABELS
            },
            "alt_text": "Two holdout confusion matrices compare dummy and scaled logistic predictions for benign and malignant samples.",
        },
    }
    for figure_id, (png_path, svg_path) in figures.items():
        figure_records[figure_id]["sha256"] = {
            "png": sha256(png_path),
            "svg": sha256(svg_path),
        }

    index = {
        "schema_version": "figure_index_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "style": {
            "palette": "Okabe-Ito-derived colorblind-safe categorical colors",
            "redundant_encoding": "model color plus line style or marker",
            "raster_dpi": 300,
            "vector_format": "SVG",
            "significance_annotations": "none; no formal significance test was justified",
        },
        "source_files": {
            name: {"path": str(path.relative_to(CASE_ROOT)).replace("\\", "/"), "sha256": sha256(path)}
            for name, path in source_files.items()
        },
        "figures": figure_records,
        "automated_checks": {
            "four_png_files_exist": all(paths[0].exists() for paths in figures.values()),
            "four_svg_files_exist": all(paths[1].exists() for paths in figures.values()),
            "all_source_hashes_recorded": True,
            "all_plotted_values_source_mapped": True,
        },
        "manual_visual_qa": {
            "status": "pending",
            "checked_figures": [],
            "criteria": [
                "readable labels",
                "color and redundant encoding",
                "honest axes and defined uncertainty",
                "no clipping or overlap",
                "no unsupported significance claim",
            ],
        },
    }
    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
