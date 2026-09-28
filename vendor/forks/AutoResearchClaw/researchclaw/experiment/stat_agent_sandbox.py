"""stat_research_agent sandbox — runs statistical-methodology experiments
via Claude Code.

This backend integrates AutoResearchClaw with stat_research_agent
(``external/agents/stat_research_agent`` by default; override via config). Mirrors
:mod:`researchclaw.experiment.biology_agent_sandbox` but targets
statistical simulation studies (bootstrap coverage, double-ML ATE,
LLM-assisted model selection, etc.) instead of constraint-based
metabolic modelling.

Workflow:

1. Writes the statistics execution plan to a Markdown prompt file
   (``stat_plan.md``).
2. Installs stat_research_agent skills/agents into the workspace's
   ``.claude/`` directory and globally to ``~/.claude/`` so the Claude
   Code CLI can load them. Both skills and agents live at the
   stat_research_agent repository ROOT, mirroring Biology-Agent.
3. Invokes ``claude -p "Execute the statistical analysis following
   stat_plan.md"`` with ``--dangerously-skip-permissions`` (configurable)
   from the workspace directory.
4. Collects output artifacts (figures, CSV/JSON metric tables, reports)
   and returns a :class:`~researchclaw.experiment.sandbox.SandboxResult`
   compatible with the rest of the pipeline.

The stat_research_agent workflow runs:
  problem formulation -> method proposal -> theory analysis ->
  experimental evaluation -> comparison -> result synthesis ->
  quality audit.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from researchclaw.config import StatAgentConfig
from researchclaw.experiment.sandbox import SandboxResult

logger = logging.getLogger(__name__)

_PROMPT_FILENAME = "stat_plan.md"
_CLAUDE_INSTRUCTION = "Execute the statistical analysis following " + _PROMPT_FILENAME


class StatAgentSandbox:
    """Run a stat_research_agent statistical pipeline via the Claude Code CLI."""

    def __init__(self, config: StatAgentConfig, workdir: Path) -> None:
        self.config = config
        self.workdir = workdir

    # ------------------------------------------------------------------
    # Public API (matches SandboxProtocol)
    # ------------------------------------------------------------------

    def run(
        self,
        prompt_text: str,
        *,
        timeout_sec: int | None = None,
    ) -> SandboxResult:
        """Run the stat_research_agent pipeline for the given statistics prompt."""
        timeout_sec = timeout_sec if timeout_sec is not None else self.config.timeout_sec
        workspace = self._prepare_workspace(prompt_text)
        cmd = self._build_command()

        logger.info(
            "StatAgentSandbox: running %r in %s (timeout=%ds)",
            " ".join(cmd),
            workspace,
            timeout_sec,
        )

        start = time.monotonic()
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        timed_out = False
        returncode = -1

        try:
            env = self._build_env()
            proc = subprocess.run(
                cmd,
                cwd=str(workspace),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            returncode = proc.returncode
            stdout_parts.append(proc.stdout or "")
            stderr_parts.append(proc.stderr or "")
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            returncode = -1
            stdout_parts.append(
                (exc.stdout or b"").decode("utf-8", errors="replace")
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")
            )
            stderr_parts.append(
                (exc.stderr or b"").decode("utf-8", errors="replace")
                if isinstance(exc.stderr, bytes)
                else (exc.stderr or "")
            )
            logger.warning("StatAgentSandbox: timed out after %ds", timeout_sec)
        except Exception as exc:  # noqa: BLE001
            returncode = -1
            stderr_parts.append(f"StatAgentSandbox launch error: {exc}")
            logger.exception("StatAgentSandbox: unexpected error")

        elapsed = time.monotonic() - start
        stdout = "\n".join(stdout_parts)
        stderr = "\n".join(stderr_parts)

        artifacts = self._collect_artifacts(workspace)
        metrics = self._build_metrics(returncode, timed_out, artifacts, workspace)
        self._write_summary(workspace, returncode, elapsed, artifacts, timed_out)

        logger.info(
            "StatAgentSandbox: finished (rc=%d, elapsed=%.1fs, artifacts=%d)",
            returncode,
            elapsed,
            sum(len(v) for v in artifacts.values()),
        )
        return SandboxResult(
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            elapsed_sec=elapsed,
            metrics=metrics,
            timed_out=timed_out,
        )

    def run_project(
        self,
        project_dir: Path,
        *,
        entry_point: str = "main.py",
        timeout_sec: int = 300,
        args: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> SandboxResult:
        """Re-entry adapter for SandboxProtocol parity. See
        :meth:`BiologyAgentSandbox.run_project` for the contract."""
        del entry_point, args, env_overrides

        candidates = (
            project_dir / "REPAIR_PROMPT.md",
            project_dir / _PROMPT_FILENAME,
            self.workdir / _PROMPT_FILENAME,
        )
        prompt_text = ""
        for cand in candidates:
            if cand.is_file():
                prompt_text = cand.read_text(encoding="utf-8")
                logger.info("StatAgentSandbox.run_project: using prompt %s", cand)
                break
        if not prompt_text:
            return SandboxResult(
                returncode=-1,
                stdout="",
                stderr=(
                    "StatAgentSandbox.run_project: no stat_plan.md found "
                    f"in project_dir={project_dir} or workspace={self.workdir}"
                ),
                elapsed_sec=0.0,
                metrics={},
                timed_out=False,
            )
        return self.run(prompt_text, timeout_sec=timeout_sec)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prepare_workspace(self, prompt_text: str) -> Path:
        workspace = self.workdir
        workspace.mkdir(parents=True, exist_ok=True)

        prompt_path = workspace / _PROMPT_FILENAME

        # Detect a follow-up rerun request from the requirements gate.
        followup_delta = ""
        consumed_paths: list[Path] = []
        candidates: list[Path] = [workspace / "REPAIR_PROMPT.md"]
        try:
            run_dir_candidate = workspace.parents[3]
            candidates.append(run_dir_candidate / "REPAIR_PROMPT.md")
        except IndexError:
            pass
        for cand in candidates:
            if cand.is_file():
                try:
                    followup_delta = cand.read_text(encoding="utf-8")
                    consumed_paths.append(cand)
                    logger.info(
                        "StatAgentSandbox: consumed %s (%d chars) — "
                        "this is a requirements-gate rerun",
                        cand, len(followup_delta),
                    )
                    break
                except OSError as exc:
                    logger.warning(
                        "StatAgentSandbox: failed to read %s: %s", cand, exc
                    )
        for cand in candidates:
            if cand.is_file():
                try:
                    cand.unlink()
                except OSError:
                    pass

        # Hard resource constraints — keep CPU sim studies tractable.
        resource_constraint = (
            "\n\n---\n"
            "## MANDATORY RESOURCE CONSTRAINTS (read before any simulation run)\n\n"
            "**Server resources are limited. Strictly follow these limits:**\n\n"
            "1. **Monte Carlo repetitions: 500 default; 2000 hard cap per condition.**\n"
            "2. **Bootstrap resamples: 1000 default; 5000 hard cap.**\n"
            "3. **Sample-size grid: at most 5 distinct sample sizes per study.**\n"
            "4. **Condition x distribution grid: at most 6 x 6 cells.**\n"
            "5. **Wall-clock priority:** scaffold all CI methods first, then\n"
            "   increase repetitions until time budget exhausted. Abort gracefully\n"
            "   so partial results are still saved to results.json.\n"
            "6. These limits override any other instructions in this plan.\n"
        )
        canonical_output = (
            "\n\n---\n"
            "## MANDATORY CANONICAL OUTPUT (write BEFORE you exit)\n\n"
            "When all numerical work is finished, write a SINGLE machine-readable\n"
            "file at workspace root (alongside this plan):\n\n"
            "    results.json\n\n"
            "It MUST contain at least the following keys (extra keys allowed):\n\n"
            "```json\n"
            "{\n"
            '  "primary_metric": <number>,                  // headline scalar (e.g. mean coverage gap, ATE bias)\n'
            '  "metric_key": "<string>",                     // identifier for primary_metric\n'
            '  "metrics": {                                   // ALL numeric scientific results\n'
            '    "coverage_<method>_<distribution>_<n>": <number>,\n'
            '    "interval_width_<method>_<distribution>_<n>": <number>,\n'
            '    "...other domain numbers...": <number>\n'
            "  },\n"
            '  "hypotheses": {                                // explicit per-hypothesis verdicts\n'
            '    "h1": {"supported": true|false, "value": <number>, "details": "..."},\n'
            '    "h2": {"supported": true|false, "details": "..."},\n'
            '    "h3": {"supported": true|false, "details": "..."}\n'
            "  },\n"
            '  "summary": "human-readable 1-paragraph narrative of what was done and found",\n'
            '  "structured_results": {                        // optional but recommended\n'
            '    "coverage_table": [...], "width_table": [...]\n'
            "  }\n"
            "}\n"
            "```\n\n"
            "Rules:\n"
            "1. **One file. results.json. Workspace root.**\n"
            "2. The pipeline reads this file exactly once. If it is missing or\n"
            "   malformed, the bench scores 0 for every result-leaf.\n"
            "3. All numeric values must be JSON numbers (not 'NaN' strings, not\n"
            "   numpy types). Use `null` for genuinely missing values.\n"
            "4. The downstream pipeline does NOT re-run code. It reads results.json\n"
            "   and either proceeds (results good) or rejects (results missing/bad).\n"
            "   So your numbers in results.json ARE the experimental output of record.\n"
        )
        prefix = ""
        if followup_delta:
            prefix = (
                "## FOLLOWUP DELTA — requirements gate rerun (read this FIRST)\n\n"
                "The previous run did not satisfy one or more must_pass\n"
                "requirements. This is the FINAL retry — the next stage-15 gate\n"
                "will proceed-with-flag regardless of outcome. Focus on the\n"
                "missing requirements below, reuse existing artifacts, and update\n"
                "results.json accordingly.\n\n"
                f"{followup_delta}\n\n"
                "---\n\n"
                "## ORIGINAL PLAN (executed last run; may need follow-up only)\n\n"
            )
        prompt_path.write_text(
            prefix + prompt_text + resource_constraint + canonical_output,
            encoding="utf-8",
        )
        logger.debug("StatAgentSandbox: wrote prompt to %s", prompt_path)

        # Standard stat_research_agent output directories (idempotent).
        # Mirrors stat_research_agent/README.md "Required Artifacts" layout.
        for subdir in (
            "src",
            "results",
            "results/figures",
            "report",
            "progress",
            "experiments",
        ):
            (workspace / subdir).mkdir(parents=True, exist_ok=True)

        if self.config.install_skills:
            self._install_skills(workspace)

        return workspace

    def _install_skills(self, workspace: Path) -> None:
        """Install stat_research_agent skills + agents so Claude Code finds them.

        Skills/agents live at the repo ROOT (``<stat_agent_dir>/skills`` and
        ``.../agents``), matching Biology-Agent's layout.
        """
        sa_dir = Path(self.config.stat_agent_dir).expanduser().resolve()
        skills_src = sa_dir / "skills"
        agents_src = sa_dir / "agents"

        # --- Global installation to ~/.claude/ ---
        global_claude = Path.home() / ".claude"
        global_claude.mkdir(exist_ok=True)

        targets = [
            (skills_src, global_claude / "skills"),
            (agents_src, global_claude / "agents"),
        ]

        for src, dst in targets:
            if not src.exists():
                logger.warning(
                    "StatAgentSandbox: %s not found — skills may be missing",
                    src,
                )
                continue
            dst.mkdir(parents=True, exist_ok=True)
            for item in src.iterdir():
                item_dst = dst / item.name
                if item_dst.exists():
                    if item_dst.is_dir():
                        shutil.rmtree(item_dst)
                    else:
                        item_dst.unlink()
                if item.is_dir():
                    shutil.copytree(item, item_dst)
                else:
                    shutil.copy2(item, item_dst)
            logger.info("StatAgentSandbox: installed %s -> %s (global)", src, dst)

        # --- Project-scoped copy in workspace/.claude/ ---
        dot_claude = workspace / ".claude"
        dot_claude.mkdir(exist_ok=True)
        for src, dst in [
            (skills_src, dot_claude / "skills"),
            (agents_src, dot_claude / "agents"),
        ]:
            if not src.exists():
                continue
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            logger.debug(
                "StatAgentSandbox: installed %s -> %s (project-scoped)", src, dst
            )

    def _build_command(self) -> list[str]:
        binary = self.config.claude_binary
        if not binary:
            binary = shutil.which("claude") or "claude"

        cmd = [binary, "-p", _CLAUDE_INSTRUCTION]

        if self.config.max_turns > 0:
            cmd += ["--max-turns", str(self.config.max_turns)]

        for arg in self.config.extra_args:
            if arg:
                cmd.append(arg)

        return cmd

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.config.magnus_address:
            env["MAGNUS_ADDRESS"] = self.config.magnus_address
        if self.config.magnus_token:
            env["MAGNUS_TOKEN"] = self.config.magnus_token
        return env

    def _collect_artifacts(self, workspace: Path) -> dict[str, list[str]]:
        artifacts: dict[str, list[str]] = {
            "figures": [],
            "data": [],
            "scripts": [],
            "models": [],
            "logs": [],
        }

        # Figures (PNG / PDF anywhere under results/, report/, figures/)
        for pattern in (
            "results/figures/*.png",
            "results/figures/*.pdf",
            "results/figures/**/*.png",
            "results/figures/**/*.pdf",
            "results/*.png",
            "results/*.pdf",
            "figures/*.png",
            "figures/*.pdf",
            "figures/**/*.png",
            "figures/**/*.pdf",
            "report/*.png",
            "report/*.pdf",
        ):
            for p in sorted(workspace.glob(pattern)):
                rel = str(p.relative_to(workspace))
                if rel not in artifacts["figures"]:
                    artifacts["figures"].append(rel)

        # Data files (metric tables, claim verdicts)
        for pattern in (
            "results/*.csv",
            "results/*.json",
            "results/**/*.csv",
            "results/**/*.json",
            "experiments/**/*.csv",
            "experiments/**/*.json",
            "data/*.csv",
            "data/*.json",
        ):
            for p in sorted(workspace.glob(pattern)):
                rel = str(p.relative_to(workspace))
                if rel not in artifacts["data"]:
                    artifacts["data"].append(rel)

        # Python scripts
        for pattern in ("*.py", "src/*.py", "src/**/*.py",
                        "experiments/**/*.py"):
            for p in sorted(workspace.glob(pattern)):
                rel = str(p.relative_to(workspace))
                if rel not in artifacts["scripts"]:
                    artifacts["scripts"].append(rel)

        # Progress / report / writeup
        for pattern in (
            "report/*.md",
            "report/**/*.md",
            "progress/**/*.md",
            "execution_summary.md",
        ):
            for p in sorted(workspace.glob(pattern)):
                rel = str(p.relative_to(workspace))
                if rel not in artifacts["logs"]:
                    artifacts["logs"].append(rel)

        return artifacts

    def _build_metrics(
        self,
        returncode: int,
        timed_out: bool,
        artifacts: dict[str, list[str]],
        workspace: Path,
    ) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "stat_agent_success": 1.0 if returncode == 0 and not timed_out else 0.0,
            "figures_produced": float(len(artifacts.get("figures", []))),
            "data_files_produced": float(len(artifacts.get("data", []))),
            "scripts_generated": float(len(artifacts.get("scripts", []))),
        }

        summary_path = workspace / "execution_summary.md"
        if summary_path.exists():
            summary_text = summary_path.read_text(encoding="utf-8")
            metrics["pipeline_steps_completed"] = float(
                summary_text.lower().count("completed")
            )
            metrics["pipeline_steps_failed"] = float(
                summary_text.lower().count("failed")
            )

        agent_doc = self._read_agent_results(workspace)
        if agent_doc:
            agent_metrics = agent_doc.get("metrics") or {}
            for k, v in agent_metrics.items():
                if isinstance(v, (int, float, bool)):
                    metrics[k] = float(v)
            hyps = agent_doc.get("hypotheses") or {}
            if isinstance(hyps, dict):
                for hid, payload in hyps.items():
                    if isinstance(payload, dict) and "supported" in payload:
                        metrics[f"hypothesis_{hid}_supported"] = (
                            1.0 if payload["supported"] else 0.0
                        )
                    elif isinstance(payload, bool):
                        metrics[f"hypothesis_{hid}_supported"] = (
                            1.0 if payload else 0.0
                        )

        agent_primary = (agent_doc or {}).get("primary_metric")
        if isinstance(agent_primary, (int, float)):
            metrics["primary_metric"] = float(agent_primary)
        else:
            figures = metrics["figures_produced"]
            failed = metrics.get("pipeline_steps_failed", 0.0)
            metrics["primary_metric"] = figures / max(1.0, figures + failed)

        return metrics

    _SANDBOX_META_KEYS = frozenset(
        {"source", "returncode", "elapsed_sec", "timed_out", "artifacts", "status"}
    )

    @classmethod
    def _read_agent_results(cls, workspace: Path) -> dict[str, Any] | None:
        """Read the agent-written canonical results.json with fallbacks.

        Resolution order:
          1. workspace/results.json
          2. workspace/results/metrics.json (stat_research_agent's
             "Required Artifacts" file)
        """
        for path in (
            workspace / "results.json",
            workspace / "results" / "metrics.json",
        ):
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue

            has_agent_keys = (
                "metrics" in data
                or "primary_metric" in data
                or "hypotheses" in data
                or "structured_results" in data
            )
            if has_agent_keys:
                return data

            non_meta = set(data.keys()) - cls._SANDBOX_META_KEYS
            if not non_meta:
                continue

            numeric_keys = {
                k: v for k, v in data.items()
                if k in non_meta
                and isinstance(v, (int, float))
                and not isinstance(v, bool)
            }
            bool_keys = {
                k: v for k, v in data.items()
                if k in non_meta and isinstance(v, bool)
            }
            if numeric_keys or bool_keys:
                wrapped: dict[str, Any] = {"metrics": numeric_keys}
                if bool_keys:
                    wrapped["hypotheses"] = {
                        k: {"supported": v} for k, v in bool_keys.items()
                    }
                return wrapped
        return None

    def _write_summary(
        self,
        workspace: Path,
        returncode: int,
        elapsed: float,
        artifacts: dict[str, list[str]],
        timed_out: bool,
    ) -> None:
        sandbox_meta = {
            "source": "stat_agent",
            "returncode": returncode,
            "elapsed_sec": round(elapsed, 2),
            "timed_out": timed_out,
            "artifacts": artifacts,
            "status": (
                "success"
                if returncode == 0 and not timed_out
                else ("timeout" if timed_out else "failed")
            ),
        }
        results_path = workspace / "results.json"
        existing: dict[str, Any] = {}
        if results_path.is_file():
            try:
                _data = json.loads(results_path.read_text(encoding="utf-8"))
                if isinstance(_data, dict):
                    existing = _data
            except (OSError, json.JSONDecodeError):
                existing = {}
        merged = dict(existing)
        for k, v in sandbox_meta.items():
            if k in ("returncode", "elapsed_sec", "timed_out"):
                merged[k] = v
            elif k not in merged:
                merged[k] = v
        if "artifacts" not in existing:
            merged["artifacts"] = artifacts
        results_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        logger.debug("StatAgentSandbox: wrote results to %s", results_path)
