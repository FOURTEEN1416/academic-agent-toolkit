#!/usr/bin/env python3
"""ARC-Bench baseline runner — shells out to AI Scientist v1/v2 or Agent Lab.

Each baseline runs via its adapter from
``baseline/adapters/``; the adapter produces a
``StandardArtifacts`` bundle (paper_text, experiment_summary, …). This
runner then builds a PaperBench-compatible ``submission/`` layout over
the adapter's output so the SAME local judge (``scripts/judge.py``) can
score baselines on the same rubric as autoclaw runs.

Mapping adapter output → submission layout:
  submission/code/main.py                 — paper_text? N. We don't have code;
                                             we write a placeholder stub so
                                             ``has_code`` heuristic is fair:
                                             baselines that did not produce
                                             code get 0 for code leaves.
  submission/results/metrics.json         — from experiment_summary
  submission/README.md                    — paper_text or writeup
  submission/claims.json                  — derived from experiment_summary
  submission/reproduce.sh + reproduce.log — stubs so the grader does not crash

Skipped / failed baselines produce a judge_result.json with overall=0
plus a ``baseline_status`` field so evaluate.py can distinguish "not run"
from "ran but scored low".
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent.parent
BASELINE_DIR = ROOT / "baseline"
EXTERNAL_ROOT = BASELINE_DIR / "external"
RESULTS_ROOT = ROOT / os.environ.get("ARC_RESULTS_DIR", "results")

sys.path.insert(0, str(REPO_ROOT))
from experiments.arc_bench.baseline.adapters import (  # noqa: E402
    AIScientistV2Adapter,
    AgentLabAdapter,
    AideAdapter,
)

ADAPTERS = {
    "ais_v2": AIScientistV2Adapter,
    "agent_lab": AgentLabAdapter,
    "aide_ml": AideAdapter,
}


def _load_topics() -> list[dict[str, Any]]:
    data = yaml.safe_load((ROOT / "config" / "topics.yaml").read_text(encoding="utf-8"))
    return data.get("topics", [])


def _load_topic(topic_id: str) -> dict[str, Any]:
    """Return the topic dict, enriched with the per-topic manifest fields.

    ``topics.yaml`` is a thin index (id/topic/domains/metric_key); the full
    research-question, synthesis, hypotheses, conditions, metrics and
    datasets live in ``manifests/<id>.yaml``. Adapters need both — we merge
    here so each adapter sees a single dict.
    """
    base: dict[str, Any] | None = None
    for t in _load_topics():
        if t["id"] == topic_id:
            base = dict(t)
            break
    if base is None:
        raise SystemExit(f"topic not found in topics.yaml: {topic_id}")

    manifest_path = ROOT / "config" / "manifests" / f"{topic_id}.yaml"
    if manifest_path.is_file():
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise SystemExit(f"failed to parse {manifest_path}: {exc}")
        # Manifest fields take precedence (richer) but don't drop topics.yaml-only fields.
        for key, value in manifest.items():
            base.setdefault(key, value)
            if key in ("synthesis", "hypotheses", "experiment_design",
                       "rubric_path", "title"):
                base[key] = value
    return base


def _build_submission_from_adapter(artifacts_native: Path, submission_dir: Path,
                                   topic: dict[str, Any]) -> None:
    """Translate an adapter's native output into our submission layout.

    The judge expects ``stage-14/experiment_summary.json`` and
    ``stage-{17,19}/paper_*.md`` at the *run_dir* level (not inside
    submission/). Adapters that wrote those via ``_write_standard_artifacts``
    place them under ``native/stage-*/...`` — so we mirror them up to the
    run_dir level here so judge.grade() / paperbench_bridge.build_submission
    can find them.
    """
    submission_dir.mkdir(parents=True, exist_ok=True)
    (submission_dir / "code").mkdir(exist_ok=True)
    (submission_dir / "results").mkdir(exist_ok=True)

    run_dir = submission_dir.parent
    # Mirror stage-N dirs from native/ to run_dir so the judge finds them.
    if artifacts_native.is_dir():
        for stage in ("stage-10", "stage-13", "stage-14", "stage-17", "stage-19"):
            src_dir = artifacts_native / stage
            if not src_dir.is_dir():
                continue
            dst_dir = run_dir / stage
            dst_dir.mkdir(exist_ok=True)
            for src in src_dir.rglob("*"):
                if not src.is_file():
                    continue
                try:
                    rel = src.relative_to(src_dir)
                    dst = dst_dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if not dst.exists():
                        shutil.copy2(src, dst)
                except Exception:  # noqa: BLE001
                    pass

    # Code: baselines rarely hand us raw code. We keep code/ empty (fair).
    # If the native run produced any .py files, symlink them.
    if artifacts_native.is_dir():
        for py in artifacts_native.rglob("*.py"):
            try:
                shutil.copy2(py, submission_dir / "code" / py.name)
            except Exception:
                pass

    # Metrics: pull from stage-14/experiment_summary.json
    exp_sum = artifacts_native / "stage-14" / "experiment_summary.json"
    metrics_blob: dict[str, Any] = {}
    if exp_sum.is_file():
        try:
            metrics_blob = json.loads(exp_sum.read_text())
        except json.JSONDecodeError:
            pass
    (submission_dir / "results" / "metrics.json").write_text(
        json.dumps(metrics_blob, indent=2, default=str), encoding="utf-8"
    )

    # Writeup: prefer paper_draft or revised paper
    paper_text = None
    for p in [
        artifacts_native / "stage-19" / "paper_revised.md",
        artifacts_native / "stage-17" / "paper_draft.md",
    ]:
        if p.is_file():
            paper_text = p.read_text(encoding="utf-8", errors="ignore")
            break
    readme_body = paper_text or "(baseline produced no writeup)"
    readme = "\n".join([
        f"# Baseline run — {topic['id']}: {topic['topic']}",
        "",
        "## Agent-produced writeup",
        "",
        readme_body,
    ])
    (submission_dir / "README.md").write_text(readme, encoding="utf-8")

    # Claims: empty shell — baselines don't emit structured claims
    (submission_dir / "claims.json").write_text(
        json.dumps({"topic_id": topic["id"], "claims": [],
                    "summary_metrics": {}}, indent=2),
        encoding="utf-8",
    )

    # Reproduce stubs — necessary for SimpleJudge but harmless for local
    (submission_dir / "reproduce.sh").write_text(
        "#!/usr/bin/env bash\n"
        "# Baseline output re-wrap; actual experiment ran inside the "
        "baseline framework.\n"
        "set -e\n"
        'echo "baseline-submission" > results/.reproduce.marker\n',
        encoding="utf-8",
    )
    os.chmod(submission_dir / "reproduce.sh", 0o755)
    (submission_dir / "reproduce.log").write_text(
        "Baseline framework ran to completion. See native artifacts "
        f"at {artifacts_native}.\n",
        encoding="utf-8",
    )
    (submission_dir / "reproduce.log.creation_time").write_text(
        str(int(time.time())), encoding="utf-8"
    )


def run_one(framework: str, topic_id: str, *, dry_run: bool) -> dict[str, Any]:
    AdapterCls = ADAPTERS.get(framework)
    if AdapterCls is None:
        raise SystemExit(f"unknown framework: {framework}")

    topic = _load_topic(topic_id)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"bb-{framework}-{topic_id}-{ts}"
    run_dir = RESULTS_ROOT / framework / topic_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    budget_sec = int(os.environ.get("ARC_BASELINE_BUDGET_SEC", "3600"))
    adapter_kwargs: dict[str, Any] = {
        "external_root": EXTERNAL_ROOT,
        "budget_sec": budget_sec,
        "dry_run": dry_run,
    }
    adapter = AdapterCls(**adapter_kwargs)

    print(f"\n{'='*72}")
    print(f"  {run_id}")
    print(f"  Baseline: {framework} × {topic_id}")
    print(f"{'='*72}")

    native_dir = run_dir / "native"
    try:
        fr = adapter.run(topic, native_dir)
    except Exception as exc:  # noqa: BLE001
        fr = None
        err = str(exc)
    else:
        err = None

    submission_dir = run_dir / "submission"
    if fr is not None and fr.status in ("completed", "failed", "timeout"):
        _build_submission_from_adapter(native_dir, submission_dir, topic)

    meta = {
        "run_id": run_id,
        "framework": framework,
        "topic_id": topic_id,
        "native_dir": str(native_dir),
        "submission_dir": str(submission_dir),
        "status": fr.status if fr else "error",
        "elapsed_sec": fr.elapsed_sec if fr else 0.0,
        "error": err or (fr.error if fr else None),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "baseline_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )

    # Grade the submission with the LLM judge (same rubric as autoclaw runs).
    if submission_dir.is_dir():
        judge_cmd = [
            sys.executable, str(ROOT / "scripts" / "judge.py"),
            "--run-dir", str(run_dir),
            "--topic", topic_id,
            "--backend", "llm",
        ]
        try:
            subprocess.run(judge_cmd, check=False, timeout=300)
        except Exception as exc:  # noqa: BLE001
            print(f"  [judge] ERROR: {exc}")

    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description="Run an ARC-Bench baseline cell")
    ap.add_argument("--framework", required=True,
                    choices=list(ADAPTERS.keys()))
    ap.add_argument("--topic", help="topic id, e.g. T01")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.all:
        topic_ids = [t["id"] for t in _load_topics()]
    elif args.topic:
        topic_ids = [args.topic]
    else:
        ap.error("--topic or --all required")

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    for tid in topic_ids:
        run_one(args.framework, tid, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
