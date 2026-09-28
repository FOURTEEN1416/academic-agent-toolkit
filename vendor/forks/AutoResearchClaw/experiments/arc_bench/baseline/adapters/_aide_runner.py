"""Subprocess entry-point that drives a single AIDE ML experiment.

Invoked by ``AideAdapter.run`` via ``subprocess.run`` so the heavy AIDE
imports (torch, transformers, …) stay isolated in the AIDE conda env.

Reads its inputs from CLI flags + environment variables, runs
``aide.Experiment``, generates the journal2report writeup, and writes a
small ``aide_run_meta.json`` summarizing what landed where.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path


def _parse() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--goal-file", required=True,
                    help="Path to a UTF-8 file containing the goal string.")
    ap.add_argument("--eval-file", required=True,
                    help="Path to a UTF-8 file containing the eval string.")
    ap.add_argument("--log-dir", required=True,
                    help="Top-level log directory; AIDE creates "
                         "<log_dir>/<idx>-<exp_name> inside it.")
    ap.add_argument("--workspace-dir", required=True)
    ap.add_argument("--exp-name", required=True)
    ap.add_argument("--steps", type=int, default=10)
    ap.add_argument("--num-drafts", type=int, default=3)
    ap.add_argument("--code-model", default="gpt-5.3-codex")
    ap.add_argument("--code-temp", type=float, default=0.5)
    ap.add_argument("--feedback-model", default="gpt-4o")
    ap.add_argument("--feedback-temp", type=float, default=0.5)
    ap.add_argument("--report-model", default="gpt-4o")
    ap.add_argument("--report-temp", type=float, default=1.0)
    return ap.parse_args()


def main() -> int:
    args = _parse()
    goal = Path(args.goal_file).read_text(encoding="utf-8")
    eval_str = Path(args.eval_file).read_text(encoding="utf-8")

    # Lazy import: this module lives in our repo but only runs inside the AIDE
    # conda env, so import errors here are operator misconfiguration.
    import aide
    from aide.utils.config import (
        _load_cfg, prep_cfg, load_task_desc, prep_agent_workspace, save_run,
    )
    from aide.journal import Journal
    from aide.agent import Agent
    from aide.interpreter import Interpreter
    from aide.journal2report import journal2report
    from omegaconf import OmegaConf

    cfg = _load_cfg(use_cli_args=False)
    cfg.data_dir = args.data_dir
    cfg.goal = goal
    cfg.eval = eval_str
    cfg.log_dir = args.log_dir
    cfg.workspace_dir = args.workspace_dir
    cfg.exp_name = args.exp_name

    # Knob overrides — keep all OTHER defaults so input parity is bounded
    # to model+steps+drafts (the only knobs we tune for compute budget).
    cfg.agent.steps = int(args.steps)
    cfg.agent.search.num_drafts = int(args.num_drafts)
    cfg.agent.code.model = args.code_model
    cfg.agent.code.temp = args.code_temp
    cfg.agent.feedback.model = args.feedback_model
    cfg.agent.feedback.temp = args.feedback_temp
    cfg.report.model = args.report_model
    cfg.report.temp = args.report_temp

    cfg = prep_cfg(cfg)
    log_dir = Path(cfg.log_dir)
    workspace_dir = Path(cfg.workspace_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    task_desc = load_task_desc(cfg)
    prep_agent_workspace(cfg)

    journal = Journal()
    agent = Agent(task_desc=task_desc, cfg=cfg, journal=journal)
    interpreter = Interpreter(
        cfg.workspace_dir,
        **OmegaConf.to_container(cfg.exec),
    )

    t0 = time.monotonic()
    error_str = None
    try:
        for _ in range(cfg.agent.steps):
            agent.step(exec_callback=interpreter.run)
            save_run(cfg, journal)
        interpreter.cleanup_session()
    except Exception as exc:
        error_str = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        try:
            interpreter.cleanup_session()
        except Exception:
            pass

    elapsed = time.monotonic() - t0

    # Best solution + journal already written by save_run; produce report.
    best_node = journal.get_best_node(only_good=False)
    report_path = log_dir / "report.md"
    if best_node is not None:
        try:
            report = journal2report(journal, task_desc, cfg.report)
            report_path.write_text(report, encoding="utf-8")
        except Exception as exc:
            (log_dir / "report_error.txt").write_text(
                f"journal2report failed: {exc!r}\n", encoding="utf-8"
            )

    meta = {
        "exp_name": cfg.exp_name,
        "log_dir": str(log_dir),
        "workspace_dir": str(workspace_dir),
        "steps_completed": len(journal),
        "steps_requested": int(args.steps),
        "elapsed_sec": round(elapsed, 2),
        "best_metric_value": (
            best_node.metric.value if best_node and best_node.metric else None
        ),
        "best_metric_maximize": (
            getattr(best_node.metric, "maximize", None)
            if best_node and best_node.metric else None
        ),
        "models": {
            "code": args.code_model,
            "feedback": args.feedback_model,
            "report": args.report_model,
        },
        "error": error_str,
    }
    (log_dir / "aide_run_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )

    return 0 if error_str is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
