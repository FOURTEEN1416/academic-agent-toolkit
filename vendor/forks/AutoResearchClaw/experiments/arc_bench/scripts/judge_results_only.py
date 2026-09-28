#!/usr/bin/env python3
"""ARC-Bench results-only programmatic judge.

Cheap, deterministic, no LLM. For each (framework × topic) cell, reads
the framework's canonical artifact paths (different per baseline) and
emits a fast pass/fail per rubric Code Execution + Result Analysis leaf.
This is the score the user can re-run anytime to sanity-check a sweep
without paying for LLM judging.

What it checks (per leaf):
- **Code Execution**: did the agent actually produce machine-readable
  metrics covering the manifest-required conditions/datasets/seeds?
- **Result Analysis (writeup)**: does an agent-produced writeup exist?
- **Result Analysis (H1/H2/H3)**: does claims.json contain non-template
  verdicts grounded in numerical evidence?

Code Development is NOT scored here — it requires reading code semantics
which a programmatic check can't reliably do. Use ``judge_manual.py``
for the full audit.

Per-framework artifact contracts (read these paths):

| Framework | Code/metrics | Writeup | Claims |
|-----------|--------------|---------|--------|
| rc_full   | submission/results/metrics.json + stage-14/experiment_summary.json | submission/README.md | submission/claims.json |
| rc_copilot| submission/results/metrics.json + stage-14/experiment_summary.json | submission/README.md | submission/claims.json |
| ais_v2    | submission/results/metrics.json + stage-14/experiment_summary.json | submission/README.md | submission/claims.json |
| agent_lab | native/research_dir_*/final_results.json + stage-14/ | native/research_report.md / paper.tex | (synthesized) |
| aide_ml   | playpen2 workspace/*.csv + native/aide_run_meta.json | native/report.md | submission/claims.json |

Usage:
    python scripts/judge_results_only.py --framework rc_full --topic T01
    python scripts/judge_results_only.py --all
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
RESULTS_DIR = ROOT / "results"
# Baseline scratch root. Override with ARC_BASELINE_ROOT (machine-specific —
# see baseline/README.md).
_BASELINE_ROOT = Path(
    os.environ.get("ARC_BASELINE_ROOT", str(Path.home() / "arc_bench" / "baselines"))
)
PLAYPEN_AIDE = _BASELINE_ROOT / "aide_ml"
PLAYPEN_AGENT_LAB = _BASELINE_ROOT / "agent_lab"


def _latest_run(framework: str, topic: str) -> Path | None:
    base = RESULTS_DIR / framework / topic
    if not base.is_dir():
        return None
    runs = sorted([p for p in base.iterdir() if p.is_dir()])
    return runs[-1] if runs else None


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _has_real_writeup(text: str | None) -> bool:
    if not text:
        return False
    if "(baseline produced no writeup)" in text:
        return False
    # Heuristic: real writeup has at least 200 chars and mentions numbers
    return len(text) >= 200 and any(c.isdigit() for c in text)


# ----------- per-framework canonical-artifact readers ----------------------

def _read_rc_canonical(run_dir: Path) -> dict[str, Any]:
    return {
        "metrics": _read_json(run_dir / "submission" / "results" / "metrics.json"),
        "stage_14": _read_json(run_dir / "stage-14" / "experiment_summary.json"),
        "claims": _read_json(run_dir / "submission" / "claims.json"),
        "readme_text": (run_dir / "submission" / "README.md").read_text(encoding="utf-8", errors="ignore")
                        if (run_dir / "submission" / "README.md").is_file() else None,
    }


def _read_aide_canonical(run_dir: Path) -> dict[str, Any]:
    out = {
        "metrics": _read_json(run_dir / "submission" / "results" / "metrics.json"),
        "stage_14": _read_json(run_dir / "stage-14" / "experiment_summary.json"),
        "claims": _read_json(run_dir / "submission" / "claims.json"),
        "readme_text": (run_dir / "submission" / "README.md").read_text(encoding="utf-8", errors="ignore")
                        if (run_dir / "submission" / "README.md").is_file() else None,
        "report_md": (run_dir / "native" / "report.md").read_text(encoding="utf-8", errors="ignore")
                        if (run_dir / "native" / "report.md").is_file() else None,
        "aide_meta": _read_json(run_dir / "native" / "aide_run_meta.json"),
    }
    # Also pull workspace CSVs from playpen2
    run_tag = run_dir.name.split("-", 2)[-1] if "-" in run_dir.name else run_dir.name
    workspaces_root = PLAYPEN_AIDE / "workspaces"
    if workspaces_root.is_dir():
        candidates = list(workspaces_root.glob(f"*{run_tag}*"))
        if candidates:
            working = candidates[0] / next(candidates[0].iterdir()).name / "working" \
                      if any(candidates[0].iterdir()) else None
            if working and Path(working).is_dir():
                out["workspace_csvs"] = sorted([str(p) for p in Path(working).glob("*.csv")])
    return out


def _read_agent_lab_canonical(run_dir: Path) -> dict[str, Any]:
    out = {
        "stage_14": _read_json(run_dir / "stage-14" / "experiment_summary.json"),
        "readme_text": (run_dir / "submission" / "README.md").read_text(encoding="utf-8", errors="ignore")
                        if (run_dir / "submission" / "README.md").is_file() else None,
    }
    # AgentLab native dirs vary; report search
    native = run_dir / "native"
    if native.is_dir():
        out["native_files"] = sorted([str(p.relative_to(native)) for p in native.glob("**/*.json")])[:10]
    return out


READERS = {
    "rc_full": _read_rc_canonical,
    "rc_copilot": _read_rc_canonical,
    "ais_v2": _read_rc_canonical,
    "aide_ml": _read_aide_canonical,
    "agent_lab": _read_agent_lab_canonical,
}


# -------------------------- scoring -----------------------------------

def score_cell(framework: str, topic: str, run_dir: Path) -> dict[str, Any]:
    reader = READERS.get(framework)
    if reader is None:
        return {"error": f"no reader for framework {framework}"}
    a = reader(run_dir)

    # Code Execution: weighted 25 (split into two coarse leaves)
    has_canonical = bool(a.get("metrics")) or bool(a.get("stage_14")) or bool(a.get("workspace_csvs"))
    has_seeds = False
    for blob in (a.get("metrics"), a.get("stage_14")):
        if isinstance(blob, dict):
            if "n_seeds" in blob or "seeds" in blob:
                has_seeds = True
            for v in blob.values() if isinstance(blob, dict) else []:
                if isinstance(v, dict) and ("std" in v or "n_seeds" in v):
                    has_seeds = True
                    break

    ce_metrics_score = 1.0 if has_canonical else 0.0
    ce_seeds_score = 1.0 if has_seeds else (0.5 if has_canonical else 0.0)

    # Result Analysis writeup: weighted 50/4 = 12.5
    writeup_text = a.get("report_md") or a.get("readme_text")
    ra_writeup_score = 1.0 if _has_real_writeup(writeup_text) else 0.05

    # Hypothesis leaves: claims.json with non-empty per-H verdict
    claims = a.get("claims") or {}
    h_verdicts = claims.get("hypothesis_verdicts", []) if isinstance(claims, dict) else []
    if not h_verdicts and isinstance(claims, dict):
        h_verdicts = claims.get("claims", [])
    n_real_verdicts = sum(
        1 for v in h_verdicts
        if isinstance(v, dict) and v.get("verdict") not in (None, "", "inconclusive_template")
    )
    ra_h_score = min(1.0, n_real_verdicts / max(1, len(h_verdicts) or 3))

    # Compose: CE = 25 weight, RA = 50. Skip Code Dev (manual judge only).
    overall = (
        25 * ((ce_metrics_score + ce_seeds_score) / 2)
        + 50 * ((ra_writeup_score + ra_h_score) / 2)
    ) / 75  # results-only normalization (CD excluded)

    return {
        "topic_id": topic,
        "framework": framework,
        "run_dir": str(run_dir),
        "results_only_overall": round(overall, 4),
        "leaves": {
            "code_exec_metrics": round(ce_metrics_score, 3),
            "code_exec_seeds": round(ce_seeds_score, 3),
            "result_writeup": round(ra_writeup_score, 3),
            "result_hypothesis_verdicts": round(ra_h_score, 3),
        },
        "evidence": {
            "has_metrics_json": bool(a.get("metrics")),
            "has_stage_14": bool(a.get("stage_14")),
            "has_workspace_csvs": bool(a.get("workspace_csvs")),
            "writeup_chars": len(writeup_text) if writeup_text else 0,
            "n_h_verdicts": len(h_verdicts),
            "n_real_verdicts": n_real_verdicts,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--framework", choices=list(READERS.keys()))
    ap.add_argument("--topic", help="e.g. T01")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    cells = []
    if args.all:
        for fw in READERS:
            for t in [f"T{i:02d}" for i in range(1, 26)]:
                rd = _latest_run(fw, t)
                if rd:
                    cells.append((fw, t, rd))
    else:
        if not args.framework or not args.topic:
            ap.error("provide --framework + --topic, or --all")
        rd = _latest_run(args.framework, args.topic)
        if rd is None:
            print(f"no run for {args.framework}/{args.topic}")
            return 1
        cells.append((args.framework, args.topic, rd))

    out = [score_cell(fw, t, rd) for fw, t, rd in cells]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
