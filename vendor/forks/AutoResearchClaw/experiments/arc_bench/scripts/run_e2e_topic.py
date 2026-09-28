#!/usr/bin/env python3
"""End-to-end ARC-Bench runner — full 1→23 stage pipeline per topic.

Mirrors ``experiments/hitl_ablation/scripts/run_g1.py``: materialises a
per-topic ``config.yaml`` from ``base_config.yaml`` and invokes
``python -m researchclaw run --auto-approve`` so ALL 23 stages execute,
not just the bench's default 10→14 trim.

Topic prefix routes profile + experiment mode:
    ML* → ml_general profile,        experiment.mode=sandbox
    P*  → hep_ph profile,            experiment.mode=collider_agent
    B*  → biology_metabolic,         experiment.mode=biology_agent
    S*  → statistics_general,        experiment.mode=stat_agent
    Q*  → ml_general profile,        experiment.mode=sandbox (Qiskit native)

Credentials are loaded from ``config/.env.local`` via
``credentials_loader.load_credentials``.

Usage:
    python experiments/arc_bench/scripts/run_e2e_topic.py --topic B01
    python experiments/arc_bench/scripts/run_e2e_topic.py --topic B01 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent.parent
BASE_CONFIG = ROOT / "config" / "base_config.yaml"
RESULTS_DIR = ROOT / "results" / "e2e"

# Reuse manifest loader (knows the prefix → subdir mapping)
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_run import load_manifest, prepare  # noqa: E402

# Reuse credentials loader
sys.path.insert(0, str(ROOT / "config"))
from credentials_loader import load_credentials  # noqa: E402


PREFIX_TO_PROFILE: dict[str, tuple[str, str]] = {
    "ML": ("ml_general", "sandbox"),
    "P":  ("hep_ph", "collider_agent"),
    "B":  ("biology_metabolic", "biology_agent"),
    "S":  ("statistics_general", "stat_agent"),
    "Q":  ("ml_general", "sandbox"),
}


def _resolve_profile(topic_id: str) -> tuple[str, str]:
    """Longest-prefix match so ML01 matches `ML` (not `M`)."""
    tid = topic_id.upper()
    for prefix in sorted(PREFIX_TO_PROFILE, key=len, reverse=True):
        if tid.startswith(prefix):
            return PREFIX_TO_PROFILE[prefix]
    raise SystemExit(
        f"unknown topic prefix in {topic_id!r} — expected one of {sorted(PREFIX_TO_PROFILE)}"
    )


def materialize_config(
    manifest: dict[str, Any],
    run_dir: Path,
    profile_id: str,
    experiment_mode: str,
) -> Path:
    cfg = yaml.safe_load(BASE_CONFIG.read_text())
    cfg["project"]["name"] = f"arc-e2e-{manifest['id']}"
    cfg["project"]["mode"] = "full-auto"
    cfg["project"]["profile"] = profile_id

    synthesis_lines = (manifest.get("synthesis") or "").strip().splitlines()
    synopsis_head = " ".join(synthesis_lines[:4])[:400]
    design = manifest.get("experiment_design") or {}
    cfg["research"]["topic"] = (
        f"ARC-Bench {manifest['id']}: {manifest['title']}. "
        f"Research question: {design.get('research_question', manifest['title'])}. "
        f"Context: {synopsis_head}"
    )
    domains_default = {"hep_ph": ["high-energy-physics", "phenomenology"],
                       "biology_metabolic": ["systems-biology", "metabolic-engineering"],
                       "ml_general": ["machine-learning", "arc-bench"],
                       "statistics_general": ["statistics", "simulation-study"]}
    cfg["research"]["domains"] = domains_default.get(profile_id, ["arc-bench"])

    # Pick first metric whose direction validates as minimize/maximize.
    # Manifest may use "match_reference" (P/B topics) which the config
    # validator rejects — fall back to "maximize" in that case.
    metrics = design.get("metrics") or []
    primary = next(
        (m for m in metrics if m.get("direction") in ("minimize", "maximize")),
        metrics[0] if metrics else None,
    )
    if primary:
        cfg["experiment"]["metric_key"] = primary.get("name", "primary_metric")
        d = primary.get("direction", "maximize")
        cfg["experiment"]["metric_direction"] = d if d in ("minimize", "maximize") else "maximize"

    cfg["experiment"]["mode"] = experiment_mode
    # Agent paths point at external/agents/* (see external/agents/README.md
    # for attribution).  Resolved relative to REPO_ROOT (the cwd we launch
    # researchclaw from below).
    if experiment_mode == "biology_agent":
        cfg["experiment"]["biology_agent"] = {
            "biology_agent_dir": str(REPO_ROOT / "external" / "agents" / "Biology-Agent"),
            "working_dir": "biology_workspace",
            "timeout_sec": int(design.get("compute_requirements", {})
                               .get("estimated_wall_clock_sec", 1800)),
            "max_turns": 100,
            "install_skills": True,
            "extra_args": ["--dangerously-skip-permissions"],
        }
    elif experiment_mode == "collider_agent":
        cfg["experiment"]["collider_agent"] = {
            "collider_agent_dir": str(REPO_ROOT / "external" / "agents" / "ColliderAgent"),
            "working_dir": "collider_workspace",
            "timeout_sec": int(design.get("compute_requirements", {})
                               .get("estimated_wall_clock_sec", 7200)),
            "max_turns": 150,
            "install_skills": True,
            "extra_args": ["--dangerously-skip-permissions"],
        }
    elif experiment_mode == "stat_agent":
        # Stat sims are CPU-cheap but the Claude Code session itself needs
        # time to run problem formulation → method → theory → experiment →
        # comparison → synthesis → audit. Floor the manifest estimate at
        # 1800s so short manifest estimates don't starve the session.
        manifest_estimate = int(design.get("compute_requirements", {})
                                 .get("estimated_wall_clock_sec", 1800))
        cfg["experiment"]["stat_agent"] = {
            "stat_agent_dir": "external/agents/stat_research_agent",
            "working_dir": "stat_workspace",
            "timeout_sec": max(manifest_estimate, 1800),
            "max_turns": 100,
            "install_skills": True,
            "extra_args": ["--dangerously-skip-permissions"],
        }

    path = run_dir / "config.yaml"
    path.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True))
    return path


def run_one(topic_id: str, *, dry_run: bool, timeout_sec: int, skip_judge: bool = False) -> dict[str, Any]:
    manifest = load_manifest(topic_id)
    profile_id, experiment_mode = _resolve_profile(topic_id)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"e2e-{topic_id}-{ts}"
    run_dir = RESULTS_DIR / topic_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*72}")
    print(f"  {run_id}")
    print(f"  Topic:   {topic_id} — {manifest.get('title', '?')[:64]}")
    print(f"  Profile: {profile_id}   Experiment mode: {experiment_mode}")
    print(f"  Stages:  1 → 23 (full end-to-end via --auto-approve)")
    print(f"{'='*72}")

    prepare(topic_id, run_dir)
    config_path = materialize_config(manifest, run_dir, profile_id, experiment_mode)
    # Pre-create paths the config validator expects to exist
    (run_dir / "docs" / "kb").mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-u", "-m", "researchclaw", "run",
        "--config", str(config_path),
        "--output", str(run_dir),
        "--profile", profile_id,
        "--auto-approve",
        "--skip-preflight",
        "--from-stage", "CODE_GENERATION",
    ]

    meta: dict[str, Any] = {
        "run_id": run_id,
        "topic_id": topic_id,
        "profile": profile_id,
        "experiment_mode": experiment_mode,
        "title": manifest.get("title"),
        "run_dir": str(run_dir),
        "config_path": str(config_path),
        "command": " ".join(cmd),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    meta_path = run_dir / "bench_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    if dry_run:
        print(f"  [dry-run] {' '.join(cmd)}")
        meta["status"] = "dry_run"
        meta_path.write_text(json.dumps(meta, indent=2))
        return meta

    creds = load_credentials()
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    for k, v in creds.items():
        if not v.startswith("REPLACE-ME") and v:
            env[k] = v

    log_path = run_dir / "run.log"
    print(f"  log → {log_path}")

    t0 = time.monotonic()
    with log_path.open("w", encoding="utf-8") as logf:
        try:
            completed = subprocess.run(
                cmd, cwd=str(REPO_ROOT), env=env,
                stdout=logf, stderr=subprocess.STDOUT,
                timeout=timeout_sec,
            )
            elapsed = time.monotonic() - t0
            meta["status"] = "completed" if completed.returncode == 0 else "failed"
            meta["returncode"] = completed.returncode
            meta["elapsed_sec"] = round(elapsed, 1)
        except subprocess.TimeoutExpired:
            meta["status"] = "timeout"
            meta["elapsed_sec"] = timeout_sec
        except Exception as exc:  # noqa: BLE001
            meta["status"] = "error"
            meta["error"] = str(exc)
    meta["finished_at"] = datetime.now(timezone.utc).isoformat()
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"  Result: {meta['status']} ({meta.get('elapsed_sec', '?')}s)")

    if meta.get("status") == "completed" and not skip_judge:
        # Agent-mode runs (stat_agent / biology_agent / collider_agent)
        # use the claude-code-based judge: same agent that ran the
        # experiment also grades the rubric, avoiding some proxies'
        # silently-failing json_mode handling.  ML topics keep
        # the existing LLM-backed judge.
        is_agent_run = experiment_mode in (
            "collider_agent", "biology_agent", "stat_agent",
        )
        if is_agent_run:
            judge_cmd = [
                sys.executable, str(ROOT / "scripts" / "judge_claude.py"),
                "--run-dir", str(run_dir),
                "--topic", topic_id,
                "--timeout-sec", "900",
            ]
        else:
            judge_cmd = [
                sys.executable, str(ROOT / "scripts" / "judge.py"),
                "--run-dir", str(run_dir),
                "--topic", topic_id,
                "--backend", "llm",
            ]
        try:
            jresult = subprocess.run(judge_cmd, capture_output=True,
                                     text=True, timeout=1200)
            print(f"  [judge] {jresult.stdout.strip()[:200] or jresult.stderr.strip()[:200]}")
            jp = run_dir / "judge_result.json"
            if jp.is_file():
                meta["judge"] = json.loads(jp.read_text())
        except Exception as exc:  # noqa: BLE001
            meta["judge_error"] = str(exc)
            print(f"  [judge] ERROR: {exc}")
        meta_path.write_text(json.dumps(meta, indent=2))
    elif skip_judge:
        meta["judge_skipped"] = True
        meta_path.write_text(json.dumps(meta, indent=2))
        print("  [judge] skipped (--no-judge)")

    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end ARC-Bench runner (1→23)")
    parser.add_argument("--topic", required=True, help="topic id, e.g. B01 / P01 / T01")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout-sec", type=int, default=7200,
                        help="overall wall-clock cap (default 2h)")
    parser.add_argument("--no-judge", action="store_true",
                        help="Skip the post-pipeline LLM judge subprocess")
    args = parser.parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    skip_judge = args.no_judge or os.environ.get("ARC_SKIP_JUDGE") == "1"
    run_one(args.topic, dry_run=args.dry_run, timeout_sec=args.timeout_sec,
            skip_judge=skip_judge)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
