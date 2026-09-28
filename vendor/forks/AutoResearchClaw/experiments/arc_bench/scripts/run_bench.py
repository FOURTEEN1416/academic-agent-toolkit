#!/usr/bin/env python3
"""ARC-Bench dispatcher — runs one or all topics in a given mode.

Modes:
  rc_full     — autoclaw full-auto (--auto-approve)
  rc_copilot  — autoclaw co-pilot with interventions/<Txx>.json

For each run:
  1. prepare_run.py injects stage-07/08/09 + checkpoint
  2. python -m researchclaw run --from-stage CODE_GENERATION --to-stage RESULT_ANALYSIS
  3. paper_replication/scripts/paperbench_finalize.py produces submission/*
  4. paper_replication/scripts/judge.py (llm backend) grades the submission
  5. results/<mode>/<Txx>/<run_id>/ keeps EVAL_KEEP only; log/ archives full run
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
BASE_CONFIG = ROOT / "config" / "base_config.yaml"
INTERVENTIONS_DIR = ROOT / "baseline" / "interventions"
RESULTS_DIR = ROOT / "results"
LOG_DIR = ROOT / "log"

# Paper-replication harness we reuse. We import the finalizer directly; the
# local judge is invoked as a subprocess because it is self-contained.
PR_ROOT = REPO_ROOT / "experiments" / "paper_replication"
sys.path.insert(0, str(PR_ROOT / "scripts"))
from paperbench_finalize import finalize as paperbench_finalize  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from prepare_run import load_manifest, prepare  # noqa: E402

EVAL_KEEP = {
    "submission",
    "judge_result.json",
    "bench_meta.json",
    "claims.json",
    "RESULTS_README.md",
}


def _load_topics() -> list[dict[str, Any]]:
    """Aggregate topics from every sub-domain registry.

    Post-rename the layout is split: ML topics live in ``config/ml/topics.yaml``,
    physics in ``config/physics/topics.yaml``, biology in ``config/biology/topics.yaml``,
    statistics in ``config/statistics/topics.yaml``, quantum in
    ``config/quantum/topics.yaml``. Legacy ``config/topics.yaml`` (pre-2026-05)
    is honoured if present so old branches keep working.
    """
    registries = [
        ROOT / "config" / "ml" / "topics.yaml",
        ROOT / "config" / "physics" / "topics.yaml",
        ROOT / "config" / "biology" / "topics.yaml",
        ROOT / "config" / "statistics" / "topics.yaml",
        ROOT / "config" / "quantum" / "topics.yaml",
        ROOT / "config" / "topics.yaml",  # legacy fallback
    ]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for reg in registries:
        if not reg.is_file():
            continue
        data = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
        for t in data.get("topics", []):
            tid = t.get("id")
            if tid and tid not in seen:
                seen.add(tid)
                out.append(t)
    return out


def _archive_and_trim(run_dir: Path, mode: str, topic_id: str, run_id: str,
                      meta: dict[str, Any]) -> Path:
    archive_root = LOG_DIR / mode / topic_id / run_id
    archive_full = archive_root / "full_run"
    archive_full.parent.mkdir(parents=True, exist_ok=True)
    if archive_full.exists():
        shutil.rmtree(archive_full)
    rsync = subprocess.run(
        ["rsync", "-a", "--exclude=__pycache__", "--exclude=*.pyc",
         f"{run_dir}/", f"{archive_full}/"],
        capture_output=True, text=True,
    )
    if rsync.returncode != 0:
        shutil.copytree(run_dir, archive_full, dirs_exist_ok=True)

    judge_path = run_dir / "judge_result.json"
    judge = {}
    if judge_path.is_file():
        try:
            judge = json.loads(judge_path.read_text())
        except json.JSONDecodeError:
            judge = {}
    lines = [
        f"# {topic_id} — {meta.get('title', '')}",
        "",
        f"- Mode: `{mode}`",
        f"- Run: `{run_id}`",
        f"- Status: {meta.get('status', '?')} "
        f"(rc={meta.get('returncode', '?')}, elapsed={meta.get('elapsed_sec', '?')}s)",
        "",
        "## Judge",
        "",
        "```json",
        json.dumps(judge, indent=2),
        "```",
        "",
        f"Full run archive: `{archive_full}`.",
    ]
    (run_dir / "RESULTS_README.md").write_text("\n".join(lines), encoding="utf-8")
    (archive_root / "RUN_README.md").write_text("\n".join(lines), encoding="utf-8")

    submission = run_dir / "submission"
    claims_src = submission / "claims.json"
    if claims_src.is_file():
        shutil.copy2(claims_src, run_dir / "claims.json")

    for entry in run_dir.iterdir():
        if entry.name in EVAL_KEEP:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()

    return archive_full


def materialize_config(manifest: dict[str, Any], run_dir: Path, mode: str) -> Path:
    cfg = yaml.safe_load(BASE_CONFIG.read_text())
    cfg["project"]["name"] = f"arc-{mode}-{manifest['id']}"
    cfg["project"]["mode"] = "full-auto" if mode == "rc_full" else "semi-auto"

    synthesis = (manifest.get("synthesis") or "").strip().splitlines()
    synopsis_head = " ".join(synthesis[:4])[:400]
    design = manifest.get("experiment_design") or {}
    cfg["research"]["topic"] = (
        f"ARC-Bench {manifest['id']}: {manifest['title']}. "
        f"Research question: {design.get('research_question', manifest['title'])}. "
        f"Context: {synopsis_head}"
    )
    cfg["research"]["domains"] = ["machine-learning", "arc-bench"]

    metrics = design.get("metrics") or []
    if metrics:
        primary = metrics[0]
        cfg["experiment"]["metric_key"] = primary.get("name", "primary_metric")
        cfg["experiment"]["metric_direction"] = primary.get("direction", "maximize")

    if mode == "rc_copilot":
        cfg["project"]["mode"] = "semi-auto"
        cfg["hitl"] = {
            "enabled": True,
            "mode": "co-pilot",
            "timeouts": {
                "default_human_timeout_sec": 86400,
                "auto_proceed_on_timeout": False,
            },
        }

    path = run_dir / "config.yaml"
    path.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True))
    return path


def run_one(topic_id: str, mode: str, *, dry_run: bool) -> dict[str, Any]:
    manifest = load_manifest(topic_id)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"ab-{mode}-{topic_id}-{ts}"
    run_dir = RESULTS_DIR / mode / topic_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*72}")
    print(f"  {run_id}")
    print(f"  Mode:   {mode}")
    print(f"  Topic:  {topic_id} — {manifest.get('title', '?')[:64]}")
    print(f"  Inject: stage-07/08/09 + checkpoint")
    print(f"  Range:  stage 10 (CODE_GENERATION) → stage 14 (RESULT_ANALYSIS)")
    print(f"{'='*72}")

    prepare(topic_id, run_dir)
    config_path = materialize_config(manifest, run_dir, mode)

    cmd = [
        sys.executable, "-u", "-m", "researchclaw", "run",
        "--config", str(config_path),
        "--output", str(run_dir),
        "--from-stage", "CODE_GENERATION",
        "--to-stage", "RESULT_ANALYSIS",
        "--skip-preflight",
    ]
    if mode == "rc_full":
        cmd.append("--auto-approve")
    elif mode == "rc_copilot":
        cmd.extend(["--mode", "co-pilot"])
        iv = INTERVENTIONS_DIR / f"{topic_id}.json"
        if iv.is_file():
            cmd.extend(["--interventions", str(iv)])
        else:
            print(f"  [copilot] WARNING: no interventions file at {iv}; "
                  f"falling back to --auto-approve")
            cmd.append("--auto-approve")
    else:
        raise ValueError(f"unknown mode: {mode}")

    meta: dict[str, Any] = {
        "run_id": run_id,
        "mode": mode,
        "topic_id": topic_id,
        "title": manifest.get("title"),
        "run_dir": str(run_dir),
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

    t0 = time.monotonic()
    try:
        completed = subprocess.run(
            cmd, cwd=str(REPO_ROOT),
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
            timeout=7200,
        )
        elapsed = time.monotonic() - t0
        meta["status"] = "completed" if completed.returncode == 0 else "failed"
        meta["returncode"] = completed.returncode
        meta["elapsed_sec"] = round(elapsed, 1)
    except subprocess.TimeoutExpired:
        meta["status"] = "timeout"
        meta["elapsed_sec"] = 7200
    except Exception as exc:  # noqa: BLE001
        meta["status"] = "error"
        meta["error"] = str(exc)
    meta["finished_at"] = datetime.now(timezone.utc).isoformat()
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"  Result: {meta['status']} ({meta.get('elapsed_sec', '?')}s)")

    if meta.get("status") == "completed":
        try:
            claims = paperbench_finalize(run_dir, topic_id, manifest_override=manifest)
            meta["bench_claims"] = len(claims.get("claims", []))
        except TypeError:
            # paperbench_finalize may not accept manifest_override on older
            # revisions; fall back to passing by paper id and relying on its
            # internal loader. Autoclaw_bench uses a distinct manifest dir so
            # the fallback may fail — in that case, we surface the error and
            # move on so the run still archives.
            try:
                claims = paperbench_finalize(run_dir, topic_id)
                meta["bench_claims"] = len(claims.get("claims", []))
            except Exception as exc:  # noqa: BLE001
                meta["finalize_error"] = str(exc)
                print(f"  [finalize] ERROR: {exc}")
        except Exception as exc:  # noqa: BLE001
            meta["finalize_error"] = str(exc)
            print(f"  [finalize] ERROR: {exc}")
        meta_path.write_text(json.dumps(meta, indent=2))

    if meta.get("status") == "completed":
        judge_cmd = [
            sys.executable, str(ROOT / "scripts" / "judge.py"),
            "--run-dir", str(run_dir),
            "--topic", topic_id,
            "--backend", "llm",
        ]
        try:
            jresult = subprocess.run(judge_cmd, capture_output=True,
                                     text=True, timeout=300)
            print(f"  [judge] {jresult.stdout.strip() or jresult.stderr.strip()}")
            jp = run_dir / "judge_result.json"
            if jp.is_file():
                meta["judge"] = json.loads(jp.read_text())
        except Exception as exc:  # noqa: BLE001
            meta["judge_error"] = str(exc)
            print(f"  [judge] ERROR: {exc}")
        meta_path.write_text(json.dumps(meta, indent=2))

    try:
        archive = _archive_and_trim(run_dir, mode, topic_id, run_id, meta)
        meta["log_archive"] = str(archive)
        print(f"  [archive] full run → {archive}")
    except Exception as exc:  # noqa: BLE001
        meta["archive_error"] = str(exc)
        print(f"  [archive] ERROR: {exc}")
    meta_path.write_text(json.dumps(meta, indent=2))
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an ARC-Bench cell")
    parser.add_argument("--mode", required=True, choices=["rc_full", "rc_copilot"])
    parser.add_argument("--topic", help="single topic id, e.g. T01")
    parser.add_argument("--all", action="store_true", help="run every topic in topics.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if args.all:
        topic_ids = [t["id"] for t in _load_topics()]
    elif args.topic:
        topic_ids = [args.topic]
    else:
        parser.error("--topic or --all required")

    for tid in topic_ids:
        run_one(tid, args.mode, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
