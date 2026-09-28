#!/usr/bin/env python3
"""Convert an ARC-Bench topic manifest into pre-stage-10 ResearchClaw artifacts.

Parallel to ``experiments/paper_replication/scripts/prepare_run.py``: reads
``manifests/<Txx>.yaml`` and materialises stage-07/08/09 + checkpoint so the
pipeline picks up at ``CODE_GENERATION`` (stage 10).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


_PREFIX_MAP: dict[str, str] = {
    "ML": "ml",         # ML01-ML25 → config/ml/{manifests,rubrics}/
    "P":  "physics",    # P01-P10   → config/physics/...
    "B":  "biology",    # B01+      → config/biology/...
    "S":  "statistics", # S01+      → config/statistics/...
    "Q":  "quantum",    # Q01+      → config/quantum/...
}


def _resolve_topic_subdir(topic_id: str) -> str:
    """Map topic ID prefix → config subdirectory.

    Multi-char prefixes are matched longest-first so ``ML`` wins over a
    hypothetical single-char ``M``.  Returns "" for unknown prefixes
    (caller falls back to the legacy ``config/manifests`` layout).
    """
    tid = topic_id.upper()
    for prefix in sorted(_PREFIX_MAP, key=len, reverse=True):
        if tid.startswith(prefix):
            return _PREFIX_MAP[prefix]
    return ""


def load_manifest(topic_id: str) -> dict[str, Any]:
    sub = _resolve_topic_subdir(topic_id)
    base = ROOT / "config" / sub if sub else ROOT / "config"
    path = base / "manifests" / f"{topic_id}.yaml"
    if not path.is_file():
        raise SystemExit(f"topic manifest not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_synthesis(run_dir: Path, manifest: dict[str, Any]) -> None:
    stage_dir = run_dir / "stage-07"
    stage_dir.mkdir(parents=True, exist_ok=True)
    body = manifest.get("synthesis", "").strip() or "(synthesis not provided)"
    md = f"# Synthesis for {manifest['id']}: {manifest['title']}\n\n{body}\n"
    (stage_dir / "synthesis.md").write_text(md, encoding="utf-8")


def write_hypotheses(run_dir: Path, manifest: dict[str, Any]) -> None:
    stage_dir = run_dir / "stage-08"
    stage_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# Hypotheses — ARC-Bench {manifest['id']}", ""]
    for h in manifest.get("hypotheses") or []:
        lines.append(f"## Hypothesis {h.get('id', '?')}")
        lines.append(h.get("statement", ""))
        lines.append("")
    (stage_dir / "hypotheses.md").write_text("\n".join(lines), encoding="utf-8")
    novelty = {
        "overall_novelty": 0.5,
        "note": ("ARC-Bench topic — novelty is moderate; the task is to design "
                 "and run a competent experiment on the stated question, not "
                 "to replicate a specific paper."),
    }
    (stage_dir / "novelty_report.json").write_text(
        json.dumps(novelty, indent=2), encoding="utf-8"
    )


def write_exp_plan(run_dir: Path, manifest: dict[str, Any]) -> None:
    stage_dir = run_dir / "stage-09"
    stage_dir.mkdir(parents=True, exist_ok=True)
    design = manifest.get("experiment_design") or {}
    plan = {
        "topic_id": manifest["id"],
        "research_question": design.get("research_question"),
        "conditions": design.get("conditions", []),
        "baselines": design.get("baselines", []),
        "metrics": design.get("metrics", []),
        "datasets": design.get("datasets", []),
        "compute_requirements": design.get("compute_requirements", {}),
        "hypotheses": [h.get("statement") for h in manifest.get("hypotheses") or []],
        "bench_note": (
            "This is an ARC-Bench topic. Implement a competent experiment "
            "addressing the research question. You may tighten or extend the "
            "listed conditions/metrics if your design is coherent."
        ),
    }
    (stage_dir / "exp_plan.yaml").write_text(
        yaml.dump(plan, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    sub = _resolve_topic_subdir(manifest["id"])
    if sub == "physics":
        domain = {
            "domain_id": "hep_ph",
            "display_name": "High Energy Physics Phenomenology (ARC-Bench)",
            "experiment_paradigm": "SIMULATION",
            "core_libraries": ["numpy", "scipy", "matplotlib"],
            "gpu_required": False,
        }
    elif sub == "biology":
        domain = {
            "domain_id": "biology_metabolic",
            "display_name": "Constraint-Based Metabolic Modelling (ARC-Bench)",
            "experiment_paradigm": "SIMULATION",
            "core_libraries": ["cobra", "pandas", "numpy", "matplotlib", "escher"],
            "gpu_required": False,
        }
    elif sub == "quantum":
        domain = {
            "domain_id": "quantum_ml",
            "display_name": "Quantum Machine Learning (ARC-Bench)",
            "experiment_paradigm": "BENCHMARK_EXPERIMENT",
            "core_libraries": [
                "numpy", "scipy", "sklearn", "matplotlib",
                "qiskit", "qiskit_aer", "qiskit_algorithms",
                "qiskit_machine_learning", "qiskit_nature",
            ],
            "gpu_required": False,
        }
    elif sub == "statistics":
        domain = {
            "domain_id": "statistics_general",
            "display_name": "Statistical Methodology & Simulation (ARC-Bench)",
            "experiment_paradigm": "BENCHMARK_EXPERIMENT",
            "core_libraries": ["numpy", "scipy", "pandas", "sklearn", "statsmodels",
                               "matplotlib"],
            "gpu_required": False,
        }
    else:
        # sub == "ml" or "" — both are ML topics (the "" fallback covers any
        # legacy bare-config manifests during migration).
        domain = {
            "domain_id": "ml_general",
            "display_name": "Machine Learning (ARC-Bench)",
            "experiment_paradigm": "BENCHMARK_EXPERIMENT",
            "core_libraries": ["numpy", "scipy", "sklearn", "pandas"],
            "gpu_required": bool(
                design.get("compute_requirements", {}).get("gpu_required")
            ),
        }
    (stage_dir / "domain_profile.json").write_text(
        json.dumps(domain, indent=2), encoding="utf-8"
    )


def write_requirements(run_dir: Path, manifest: dict[str, Any]) -> None:
    """Persist manifest.requirements as a top-level file under stage-09.

    The agent-mode requirements gate (researchclaw.pipeline.stage_impls.
    _analysis._read_requirements_from_manifest) looks here first when it
    fires at stage 15 — having a dedicated file avoids re-parsing the
    full manifest and lets us declare bench-only requirements separate
    from manifest fields the pipeline already consumes.
    """
    reqs = manifest.get("requirements") or []
    if not isinstance(reqs, list):
        return
    stage_dir = run_dir / "stage-09"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "requirements.json").write_text(
        json.dumps(reqs, indent=2), encoding="utf-8"
    )


def write_checkpoint(run_dir: Path) -> None:
    checkpoint = {
        "last_completed_stage": 9,
        "last_completed_name": "EXPERIMENT_DESIGN",
        "written_at": time.time(),
        "source": "arc_bench/prepare_run.py",
    }
    (run_dir / "checkpoint.json").write_text(
        json.dumps(checkpoint, indent=2), encoding="utf-8"
    )


def prepare(topic_id: str, output: Path) -> Path:
    manifest = load_manifest(topic_id)
    output.mkdir(parents=True, exist_ok=True)
    write_synthesis(output, manifest)
    write_hypotheses(output, manifest)
    write_exp_plan(output, manifest)
    write_requirements(output, manifest)
    write_checkpoint(output)
    (output / "topic_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    # Also stash a manifest snapshot under stage-07 for the requirements
    # gate (it falls back to stage-07/topic_manifest.json if stage-09/
    # requirements.json is absent — useful for topics that declare reqs
    # inline without a separate file).
    (output / "stage-07" / "topic_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    print(f"  prepared stage-07/08/09 + checkpoint under {output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an ARC-Bench run directory")
    parser.add_argument("--topic", required=True, help="topic ID, e.g. T01")
    parser.add_argument("--output", required=True, type=Path, help="run directory")
    args = parser.parse_args()
    prepare(args.topic, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
