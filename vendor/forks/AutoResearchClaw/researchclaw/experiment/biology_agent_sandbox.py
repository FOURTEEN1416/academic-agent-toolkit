"""Biology-Agent sandbox — runs constraint-based metabolic-modelling
experiments via Claude Code.

This backend integrates AutoResearchClaw with Biology-Agent
(``external/agents/Biology-Agent`` by default; override via config).  Mirrors :mod:`researchclaw.experiment.
collider_agent_sandbox` but targets COBRApy + BIGG genome-scale
metabolic models instead of HEP Monte-Carlo tools.

Workflow:

1. Writes the metabolic execution plan to a Markdown prompt file
   (``biology_plan.md``).
2. Installs Biology-Agent skills/agents into the workspace's ``.claude/``
   directory and globally to ``~/.claude/`` so the Claude Code CLI can
   load them.  Note: Biology-Agent stores skills/agents at the repository
   ROOT (``<biology_agent_dir>/skills`` and ``.../agents``), NOT under
   ``src/`` like ColliderAgent.
3. Invokes ``claude -p "Execute the metabolic analysis following
   biology_plan.md"`` with ``--dangerously-skip-permissions``
   (configurable) from the workspace directory.
4. Collects output artifacts (figures, CSV flux tables, JSON results,
   model files) and returns a
   :class:`~researchclaw.experiment.sandbox.SandboxResult` compatible
   with the rest of the pipeline.

The full metabolic pipeline run by Biology-Agent is:
  BIGG model id / SBML -> COBRApy model -> medium / objective ->
  FBA -> pFBA -> FVA -> knockout screen -> Escher map / phase plane.

For lighter tasks (e.g. pure flux-table analysis with no LP) the
``flux-analyzer`` subagent can produce figures directly from a provided
flux CSV.
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

from researchclaw.config import BiologyAgentConfig
from researchclaw.experiment.sandbox import SandboxResult

logger = logging.getLogger(__name__)

# Sentinel written to the prompt file name
_PROMPT_FILENAME = "biology_plan.md"

# Claude invocation instruction
_CLAUDE_INSTRUCTION = "Execute the metabolic analysis following " + _PROMPT_FILENAME


class BiologyAgentSandbox:
    """Run a Biology-Agent metabolic-modelling pipeline via the Claude Code CLI.

    Parameters
    ----------
    config:
        :class:`~researchclaw.config.BiologyAgentConfig` with all
        Biology-Agent / Claude Code settings.
    workdir:
        Base working directory for this experiment run. The sandbox
        creates a ``biology_workspace/`` sub-directory here where the
        Claude Code session operates.
    """

    def __init__(self, config: BiologyAgentConfig, workdir: Path) -> None:
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
        """Run the Biology-Agent pipeline for the given metabolic prompt.

        Parameters
        ----------
        prompt_text:
            Markdown text describing the metabolic-modelling task (organism,
            GEM, medium, perturbations, analysis steps). Written to
            ``biology_plan.md`` in the workspace before invoking Claude Code.
        timeout_sec:
            Wall-clock timeout for the Claude Code session. Defaults to
            ``config.timeout_sec``.
        """
        timeout_sec = timeout_sec if timeout_sec is not None else self.config.timeout_sec
        workspace = self._prepare_workspace(prompt_text)
        cmd = self._build_command()

        logger.info(
            "BiologyAgentSandbox: running %r in %s (timeout=%ds)",
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
            logger.warning("BiologyAgentSandbox: timed out after %ds", timeout_sec)
        except Exception as exc:  # noqa: BLE001
            returncode = -1
            stderr_parts.append(f"BiologyAgentSandbox launch error: {exc}")
            logger.exception("BiologyAgentSandbox: unexpected error")

        elapsed = time.monotonic() - start
        stdout = "\n".join(stdout_parts)
        stderr = "\n".join(stderr_parts)

        artifacts = self._collect_artifacts(workspace)
        metrics = self._build_metrics(returncode, timed_out, artifacts, workspace)
        self._write_summary(workspace, returncode, elapsed, artifacts, timed_out)

        logger.info(
            "BiologyAgentSandbox: finished (rc=%d, elapsed=%.1fs, artifacts=%d)",
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
        """``SandboxProtocol.run_project`` adapter for the agent sandbox.

        For Biology-Agent the experiment is end-to-end inside a single Claude
        Code session; "running a project directory" reduces to re-invoking the
        agent against the existing workspace.  Two cases:

        * If the original ``biology_plan.md`` is in the workspace already, we
          just dispatch to :meth:`run` with that plan text — the agent picks up
          the existing artifacts and continues.  This is what stage-14 repair
          loops want: "re-run with the latest fixes."

        * If a *project_dir* contains its own delta plan (``biology_plan.md``
          or ``REPAIR_PROMPT.md``), that text is used as the prompt instead.

        ``entry_point`` / ``args`` are part of the SandboxProtocol signature
        but unused for agent sandboxes (the entry point is always the plan).
        """
        del entry_point, args, env_overrides  # SandboxProtocol parity only

        # Pick up a delta plan from the project_dir if present, else fall
        # back to the existing workspace plan.
        candidates = (
            project_dir / "REPAIR_PROMPT.md",
            project_dir / _PROMPT_FILENAME,
            self.workdir / _PROMPT_FILENAME,
        )
        prompt_text = ""
        for cand in candidates:
            if cand.is_file():
                prompt_text = cand.read_text(encoding="utf-8")
                logger.info("BiologyAgentSandbox.run_project: using prompt %s", cand)
                break
        if not prompt_text:
            return SandboxResult(
                returncode=-1,
                stdout="",
                stderr=(
                    "BiologyAgentSandbox.run_project: no biology_plan.md found "
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
        """Set up the Biology-Agent workspace directory.

        If a ``REPAIR_PROMPT.md`` is present (written by the stage-15
        requirements gate when must_pass items are unmet), prepend it to the
        plan as a FOLLOWUP DELTA section, then delete it so it is consumed
        exactly once.  This is the mechanism that makes "1 retry max" work
        for agent-based experiment modes.
        """
        workspace = self.workdir
        workspace.mkdir(parents=True, exist_ok=True)

        prompt_path = workspace / _PROMPT_FILENAME

        # Detect a follow-up rerun request from the requirements gate.
        # Look in two places (in order):
        #   1. workspace/REPAIR_PROMPT.md  — own dir (rare, only when no rollback happened)
        #   2. run_dir/REPAIR_PROMPT.md    — preserved across stage-12 archival
        # The run-dir-root location is the primary one because the runner's
        # _version_rollback_stages renames the live stage-12 to stage-12_v{N}
        # BEFORE the rerun, archiving anything written there.
        followup_delta = ""
        consumed_paths: list[Path] = []
        candidates: list[Path] = [workspace / "REPAIR_PROMPT.md"]
        try:
            run_dir_candidate = workspace.parents[3]
            candidates.append(run_dir_candidate / "REPAIR_PROMPT.md")
        except IndexError:
            pass  # workspace not nested deeply enough — skip
        for cand in candidates:
            if cand.is_file():
                try:
                    followup_delta = cand.read_text(encoding="utf-8")
                    consumed_paths.append(cand)
                    logger.info(
                        "BiologyAgentSandbox: consumed %s (%d chars) — "
                        "this is a requirements-gate rerun",
                        cand, len(followup_delta),
                    )
                    break
                except OSError as exc:
                    logger.warning(
                        "BiologyAgentSandbox: failed to read %s: %s", cand, exc
                    )
        # Delete consumed file (and any leftover at the alternate path) so the
        # next clean run does not re-trigger.
        for cand in candidates:
            if cand.is_file():
                try:
                    cand.unlink()
                except OSError:
                    pass

        # Append hard resource constraints so the Biology-Agent always
        # sees them, regardless of what the plan says.
        resource_constraint = (
            "\n\n---\n"
            "## MANDATORY RESOURCE CONSTRAINTS (read before any FBA / scan run)\n\n"
            "**Server resources are limited. Strictly follow these limits:**\n\n"
            "1. **Maximum FBA / knockout scan: 100 conditions per run.**\n"
            "   - Single-gene knockout sweeps cap at 100 genes per condition.\n"
            "   - Double-knockout sweeps cap at 50 x 50 (= 2500 LPs) per condition.\n"
            "2. **Phenotypic phase plane grid: at most 50 x 50 substrate-uptake points.**\n"
            "3. **FVA fraction-of-optimum: >= 0.95 (do not loosen below 0.9).**\n"
            "4. **Monte Carlo flux sampling: 1000 samples by default; 5000 hard max.**\n"
            "5. **Priority order:** wild-type FBA -> pFBA -> FVA -> headline knockouts ->\n"
            "   phase plane -> sampling. Abort gracefully if the time budget is exhausted\n"
            "   so partial results are still saved.\n"
            "6. These limits override any other instructions in this plan.\n"
        )
        # Mandatory canonical output: this is the single source of truth that
        # downstream pipeline stages read.  No JSON here = no metric forwarding
        # = bench rubric gets all-null leaves.  Keep schema stable.
        canonical_output = (
            "\n\n---\n"
            "## MANDATORY CANONICAL OUTPUT (write BEFORE you exit)\n\n"
            "When all numerical work is finished, write a SINGLE machine-readable\n"
            "file at workspace root (alongside this plan):\n\n"
            "    results.json\n\n"
            "It MUST contain at least the following keys (extra keys allowed):\n\n"
            "```json\n"
            "{\n"
            '  "primary_metric": <number>,                  // headline scalar (e.g. best KO yield, max growth)\n'
            '  "metric_key": "<string>",                     // identifier for primary_metric\n'
            '  "metrics": {                                   // ALL numeric scientific results\n'
            '    "wt_growth_observed_1_per_h": <number>,\n'
            '    "max_succinate_yield_at_zero_growth_mmol_gDW_h": <number>,\n'
            '    "best_ko_succinate_yield_mmol_gDW_h": <number>,\n'
            '    "...other domain numbers...": <number>\n'
            "  },\n"
            '  "hypotheses": {                                // explicit per-hypothesis verdicts\n'
            '    "h1": {"supported": true|false, "value": <number>, "details": "..."},\n'
            '    "h2": {"supported": true|false, "details": "..."},\n'
            '    "h3": {"supported": true|false, "details": "..."}\n'
            "  },\n"
            '  "summary": "human-readable 1-paragraph narrative of what was done and found",\n'
            '  "structured_results": {                        // optional but recommended\n'
            '    "top_targets": [...], "envelope": [...], "essentiality": [...]\n'
            "  }\n"
            "}\n"
            "```\n\n"
            "Rules:\n"
            "1. **One file. results.json. Workspace root.** Not under analysis/, not\n"
            "   under simulations/ — root.\n"
            "2. The pipeline reads this file exactly once. If it is missing or\n"
            "   malformed, the bench scores 0 for every result-leaf.\n"
            "3. All numeric values must be JSON numbers (not 'NaN' strings, not\n"
            "   numpy types). Use `null` for genuinely missing values.\n"
            "4. The downstream pipeline does NOT re-run code, does NOT refine python\n"
            "   files. It reads results.json and either proceeds (results good) or\n"
            "   rejects (results missing/bad). So your numbers in results.json ARE\n"
            "   the experimental output of record.\n"
        )
        # If a REPAIR_PROMPT was consumed, prepend a FOLLOWUP DELTA section
        # so the agent sees the must_pass items still failing FIRST, before
        # the original plan and the resource/output footers.
        prefix = ""
        if followup_delta:
            prefix = (
                "## FOLLOWUP DELTA — requirements gate rerun (read this FIRST)\n\n"
                "The previous run did not satisfy one or more must_pass\n"
                "requirements.  This is the FINAL retry — the next stage-15 gate\n"
                "will proceed-with-flag regardless of outcome.  Focus on the\n"
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
        logger.debug("BiologyAgentSandbox: wrote prompt to %s", prompt_path)

        # Standard Biology-Agent output directories (idempotent)
        for subdir in (
            "models",
            "simulations",
            "analysis",
            "figures",
            "data",
            "progress",
        ):
            (workspace / subdir).mkdir(parents=True, exist_ok=True)

        if self.config.install_skills:
            self._install_skills(workspace)

        return workspace

    def _install_skills(self, workspace: Path) -> None:
        """Install Biology-Agent skills and agents so Claude Code can load them.

        Skills and agents live at the Biology-Agent repository ROOT
        (``<biology_agent_dir>/skills`` and ``.../agents``) — NOT under
        ``src/`` like ColliderAgent. This method copies them both globally
        to ``~/.claude/`` and project-scoped to ``<workspace>/.claude/``.
        """
        ba_dir = Path(self.config.biology_agent_dir).expanduser().resolve()
        skills_src = ba_dir / "skills"
        agents_src = ba_dir / "agents"

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
                    "BiologyAgentSandbox: %s not found — skills may be missing",
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
            logger.info("BiologyAgentSandbox: installed %s -> %s (global)", src, dst)

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
                "BiologyAgentSandbox: installed %s -> %s (project-scoped)", src, dst
            )

    def _build_command(self) -> list[str]:
        """Construct the ``claude`` CLI invocation."""
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
        """Build environment variables for the Claude Code subprocess."""
        env = os.environ.copy()
        if self.config.magnus_address:
            env["MAGNUS_ADDRESS"] = self.config.magnus_address
        if self.config.magnus_token:
            env["MAGNUS_TOKEN"] = self.config.magnus_token
        return env

    def _collect_artifacts(self, workspace: Path) -> dict[str, list[str]]:
        """Scan workspace for output artifacts and return a categorised dict."""
        artifacts: dict[str, list[str]] = {
            "figures": [],
            "data": [],
            "scripts": [],
            "models": [],
            "logs": [],
        }

        # Figures (PNG / PDF in figures/ and analysis/)
        for pattern in (
            "figures/*.png",
            "figures/*.pdf",
            "figures/**/*.png",
            "figures/**/*.pdf",
            "analysis/*.png",
            "analysis/*.pdf",
            "analysis/**/*.png",
            "analysis/**/*.pdf",
        ):
            for p in sorted(workspace.glob(pattern)):
                rel = str(p.relative_to(workspace))
                if rel not in artifacts["figures"]:
                    artifacts["figures"].append(rel)

        # Data files (flux CSVs, JSON, escher HTML)
        for pattern in (
            "simulations/*.csv",
            "simulations/*.json",
            "simulations/**/*.csv",
            "simulations/**/*.json",
            "data/*.csv",
            "data/*.json",
            "data/**/*.csv",
            "data/**/*.json",
            "figures/*.html",  # escher maps
            "analysis/*.csv",
            "analysis/*.json",
        ):
            for p in sorted(workspace.glob(pattern)):
                rel = str(p.relative_to(workspace))
                if rel not in artifacts["data"]:
                    artifacts["data"].append(rel)

        # Python scripts
        for pattern in ("*.py", "scripts/*.py", "scripts/**/*.py"):
            for p in sorted(workspace.glob(pattern)):
                rel = str(p.relative_to(workspace))
                if rel not in artifacts["scripts"]:
                    artifacts["scripts"].append(rel)

        # Models (COBRApy JSON / SBML XML)
        for pattern in (
            "models/*.json",
            "models/*.xml",
            "models/*.sbml",
            "models/**/*.json",
            "models/**/*.xml",
            "models/**/*.sbml",
        ):
            for p in sorted(workspace.glob(pattern)):
                rel = str(p.relative_to(workspace))
                if rel not in artifacts["models"]:
                    artifacts["models"].append(rel)

        # Progress / execution summary
        for pattern in ("execution_summary.md", "progress/**/*.md"):
            for p in sorted(workspace.glob(pattern)):
                artifacts["logs"].append(str(p.relative_to(workspace)))

        return artifacts

    def _build_metrics(
        self,
        returncode: int,
        timed_out: bool,
        artifacts: dict[str, list[str]],
        workspace: Path,
    ) -> dict[str, Any]:
        """Convert Biology-Agent output into AutoResearchClaw metrics.

        Coverage stats (figures_produced, models_generated, ...) describe the
        sandbox run.  Domain metrics (wt_growth, succinate yield, hypothesis
        flags, ...) come from the agent-written ``results.json`` at workspace
        root and are merged in here so stage 14 / the bench rubric see them.
        """
        metrics: dict[str, Any] = {
            "biology_agent_success": 1.0 if returncode == 0 and not timed_out else 0.0,
            "figures_produced": float(len(artifacts.get("figures", []))),
            "data_files_produced": float(len(artifacts.get("data", []))),
            "scripts_generated": float(len(artifacts.get("scripts", []))),
            "models_generated": float(len(artifacts.get("models", []))),
        }

        # Pipeline step counts from execution_summary.md (if agent wrote one)
        summary_path = workspace / "execution_summary.md"
        if summary_path.exists():
            summary_text = summary_path.read_text(encoding="utf-8")
            metrics["pipeline_steps_completed"] = float(summary_text.lower().count("completed"))
            metrics["pipeline_steps_failed"] = float(summary_text.lower().count("failed"))

        # Merge agent-written domain metrics from results.json (canonical output).
        # Fall back to analysis/summary.json if the agent followed the older
        # convention.  Both are merged additively without clobbering coverage stats.
        agent_doc = self._read_agent_results(workspace)
        if agent_doc:
            agent_metrics = agent_doc.get("metrics") or {}
            for k, v in agent_metrics.items():
                if isinstance(v, (int, float, bool)):
                    metrics[k] = float(v)
            # Surface hypothesis-supported flags as 0/1 metrics so they show
            # up in the bench rubric / experiment_summary aggregation.
            hyps = agent_doc.get("hypotheses") or {}
            if isinstance(hyps, dict):
                for hid, payload in hyps.items():
                    if isinstance(payload, dict) and "supported" in payload:
                        metrics[f"hypothesis_{hid}_supported"] = 1.0 if payload["supported"] else 0.0
                    elif isinstance(payload, bool):
                        metrics[f"hypothesis_{hid}_supported"] = 1.0 if payload else 0.0

        # Primary metric resolution order:
        #   1. agent-declared results.json["primary_metric"]
        #   2. legacy figure-reproduction-rate
        agent_primary = (agent_doc or {}).get("primary_metric")
        if isinstance(agent_primary, (int, float)):
            metrics["primary_metric"] = float(agent_primary)
        else:
            figures = metrics["figures_produced"]
            failed = metrics.get("pipeline_steps_failed", 0.0)
            metrics["primary_metric"] = figures / max(1.0, figures + failed)

        return metrics

    # Top-level keys written by the sandbox's own _write_summary().  Used to
    # detect and skip a sandbox-written stub when probing for the agent's
    # canonical output.
    _SANDBOX_META_KEYS = frozenset(
        {"source", "returncode", "elapsed_sec", "timed_out", "artifacts", "status"}
    )

    @classmethod
    def _read_agent_results(cls, workspace: Path) -> dict[str, Any] | None:
        """Read the agent-written canonical results.json, with fallbacks.

        Resolution order:
          1. ``workspace/results.json``  — only if it contains AGENT data
             (``metrics``, ``primary_metric``, or ``hypotheses`` keys).  If
             the sandbox merged its meta into the file but the agent never
             populated scientific keys, we skip it and fall back.
          2. ``workspace/analysis/summary.json``  — older Biology-Agent
             convention; numeric/bool top-level keys are auto-wrapped.
          3. ``workspace/analysis/flux_analysis_summary.json``
        """
        for path in (workspace / "results.json",
                     workspace / "analysis" / "summary.json",
                     workspace / "analysis" / "flux_analysis_summary.json"):
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

            # If the only keys are sandbox meta, this is a stub from
            # _write_summary() — skip and try the next candidate.
            non_meta = set(data.keys()) - cls._SANDBOX_META_KEYS
            if not non_meta:
                continue

            # Older convention: numeric / bool keys at top level → wrap into
            # the canonical schema.  Only consider keys outside sandbox-meta.
            numeric_keys = {
                k: v for k, v in data.items()
                if k in non_meta and isinstance(v, (int, float)) and not isinstance(v, bool)
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
        """Write a machine-readable results.json for the pipeline.

        If Biology-Agent already wrote a structured ``results.json`` during
        the session, this method merges sandbox metadata into it without
        clobbering the model-emitted content. Existing keys take precedence
        over sandbox defaults, EXCEPT ``returncode``/``elapsed_sec``/
        ``timed_out`` which are always sandbox-authoritative.
        """
        sandbox_meta = {
            "source": "biology_agent",
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
                merged[k] = v  # sandbox-authoritative
            elif k not in merged:
                merged[k] = v
        if "artifacts" not in existing:
            merged["artifacts"] = artifacts
        results_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        logger.debug("BiologyAgentSandbox: wrote results to %s", results_path)
