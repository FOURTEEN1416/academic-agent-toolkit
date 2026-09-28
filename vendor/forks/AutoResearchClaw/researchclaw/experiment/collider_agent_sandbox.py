"""ColliderAgent sandbox — runs particle physics experiments via Claude Code.

This backend integrates AutoResearchClaw with ColliderAgent
(https://github.com/HET-AGI/ColliderAgent).  Instead of running
Python sandbox code, it:

1. Writes the physics execution plan to a Markdown prompt file.
2. Installs ColliderAgent skills/agents into the workspace's ``.claude/``
   directory (or globally to ``~/.claude/``) so the Claude Code CLI can
   load them.
3. Invokes ``claude -p "Execute the analysis following prompt.md"``
   with ``--dangerously-skip-permissions`` (configurable) from the
   workspace directory.
4. Collects output artifacts (figures, data files, logs) and returns a
   :class:`~researchclaw.experiment.sandbox.SandboxResult` compatible
   with the rest of the pipeline.

The full physics pipeline run by ColliderAgent is:
  Lagrangian → FeynRules → UFO → MadGraph5 → Delphes → MadAnalysis5 → Figure

For lighter tasks (e.g. pure numerical analysis, parameter-space scans)
that do not need HEP Monte-Carlo tools, the ``pheno-analyzer`` subagent
can produce figures directly from provided cross-section data.
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

from researchclaw.config import ColliderAgentConfig
from researchclaw.experiment.sandbox import SandboxResult

logger = logging.getLogger(__name__)

# Sentinel written to the prompt file name
_PROMPT_FILENAME = "collider_plan.md"

# Claude invocation instruction (matches ColliderAgent README quickstart)
_CLAUDE_INSTRUCTION = "Execute the analysis following " + _PROMPT_FILENAME


class ColliderAgentSandbox:
    """Run a ColliderAgent physics pipeline via the Claude Code CLI.

    Parameters
    ----------
    config:
        :class:`~researchclaw.config.ColliderAgentConfig` with all
        ColliderAgent / Claude Code settings.
    workdir:
        Base working directory for this experiment run.  The sandbox
        creates a ``collider_workspace/`` sub-directory here where the
        Claude Code session operates.
    """

    def __init__(self, config: ColliderAgentConfig, workdir: Path) -> None:
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
        """Run the ColliderAgent pipeline for the given physics prompt.

        Parameters
        ----------
        prompt_text:
            Markdown text describing the physics task (Lagrangian, process,
            analysis steps, etc.).  Written to ``collider_plan.md`` in the
            workspace before invoking Claude Code.
        timeout_sec:
            Wall-clock timeout for the Claude Code session.  Defaults to
            ``config.timeout_sec``.
        """
        timeout_sec = timeout_sec if timeout_sec is not None else self.config.timeout_sec
        workspace = self._prepare_workspace(prompt_text)
        cmd = self._build_command()

        logger.info(
            "ColliderAgentSandbox: running %r in %s (timeout=%ds)",
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
            stdout_parts.append((exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
            stderr_parts.append((exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
            logger.warning("ColliderAgentSandbox: timed out after %ds", timeout_sec)
        except Exception as exc:  # noqa: BLE001
            returncode = -1
            stderr_parts.append(f"ColliderAgentSandbox launch error: {exc}")
            logger.exception("ColliderAgentSandbox: unexpected error")

        elapsed = time.monotonic() - start
        stdout = "\n".join(stdout_parts)
        stderr = "\n".join(stderr_parts)

        # Collect artifacts from the workspace
        artifacts = self._collect_artifacts(workspace)
        metrics = self._build_metrics(returncode, timed_out, artifacts, workspace)

        # Write a summary for the pipeline
        self._write_summary(workspace, returncode, elapsed, artifacts, timed_out)

        # Incremental mode: merge new results.json with the snapshotted prior one
        if getattr(self.config, "incremental", False):
            try:
                self._merge_incremental_results(workspace)
            except Exception as _merge_exc:  # noqa: BLE001
                logger.warning(
                    "Incremental result merge failed (non-fatal): %s", _merge_exc
                )

        logger.info(
            "ColliderAgentSandbox: finished (rc=%d, elapsed=%.1fs, artifacts=%d)",
            returncode,
            elapsed,
            len(artifacts),
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
        """``SandboxProtocol.run_project`` adapter for ColliderAgent.

        Mirror of :meth:`BiologyAgentSandbox.run_project`.  The ColliderAgent
        pipeline is atomic — a single Claude Code session — so "running a
        project directory" really means: dispatch to :meth:`run` with the
        existing or delta plan markdown.  This is what stage-14 repair loops
        invoke when results need re-execution; the agent re-enters with the
        existing workspace artifacts in place.
        """
        del entry_point, args, env_overrides  # SandboxProtocol parity only

        candidates = (
            project_dir / "REPAIR_PROMPT.md",
            project_dir / _PROMPT_FILENAME,
            self.workdir / _PROMPT_FILENAME,
        )
        prompt_text = ""
        for cand in candidates:
            if cand.is_file():
                prompt_text = cand.read_text(encoding="utf-8")
                logger.info("ColliderAgentSandbox.run_project: using prompt %s", cand)
                break
        if not prompt_text:
            return SandboxResult(
                returncode=-1,
                stdout="",
                stderr=(
                    "ColliderAgentSandbox.run_project: no collider_plan.md found "
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
        """Set up the ColliderAgent workspace directory.

        In incremental mode, when an existing ``collider_plan.md`` and at least
        one of ``models/`` or ``events/`` is present, the new ``prompt_text``
        is treated as a *delta* and combined with a continuation context
        block listing reusable artifacts plus the prior plan as reference.
        """
        workspace = self.workdir
        workspace.mkdir(parents=True, exist_ok=True)

        prompt_path = workspace / _PROMPT_FILENAME

        # Detect a follow-up rerun request from the requirements gate.
        # Look in two places (in order):
        #   1. workspace/REPAIR_PROMPT.md  — own dir (only if no rollback happened)
        #   2. run_dir/REPAIR_PROMPT.md    — preserved across stage-12 archival
        # See BiologyAgentSandbox._prepare_workspace for the rationale.
        followup_delta = ""
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
                    logger.info(
                        "ColliderAgentSandbox: consumed %s (%d chars) — "
                        "this is a requirements-gate rerun",
                        cand, len(followup_delta),
                    )
                    break
                except OSError as exc:
                    logger.warning(
                        "ColliderAgentSandbox: failed to read %s: %s", cand, exc
                    )
        for cand in candidates:
            if cand.is_file():
                try:
                    cand.unlink()
                except OSError:
                    pass

        def _has_artifacts(sub: str) -> bool:
            d = workspace / sub
            return d.is_dir() and any(d.iterdir())

        is_incremental = bool(
            getattr(self.config, "incremental", False)
            and prompt_path.is_file()
            and (_has_artifacts("models") or _has_artifacts("events"))
        )

        if is_incremental:
            prev_plan_text = prompt_path.read_text(encoding="utf-8")
            prev_path = workspace / "collider_plan.prev.md"
            prev_path.write_text(prev_plan_text, encoding="utf-8")

            manifest = self._build_workspace_manifest(workspace)
            (workspace / "workspace_manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )

            keep_path = workspace / "keep.txt"
            if keep_path.is_file():
                keep_globs = [
                    line.strip()
                    for line in keep_path.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
            else:
                keep_globs = []

            tree_lines = [
                f"  - {entry['path']} ({entry['kind']})"
                for entry in manifest.get("entries", [])[:200]
            ]
            tree_block = "\n".join(tree_lines) if tree_lines else "  (empty)"
            pinned_block = (
                "\n".join(f"  - {g}" for g in keep_globs) if keep_globs else "  (none)"
            )

            full_prompt = (
                "## CONTINUATION CONTEXT (MUST READ)\n"
                "The workspace already contains the following artifacts. Reuse them; "
                "do NOT regenerate unless the NEW TASKS section explicitly says so.\n"
                "Paths are relative to the workspace root.\n\n"
                f"{tree_block}\n\n"
                f"Pinned paths (NEVER overwrite):\n{pinned_block}\n\n"
                "---\n\n"
                "## PRIOR PLAN (reference only — already executed)\n\n"
                f"{prev_plan_text}\n\n"
                "---\n\n"
                "## NEW / ADDITIONAL TASKS (do these now; touch existing artifacts only "
                "if explicitly stated)\n\n"
                f"{prompt_text}\n"
            )
        else:
            full_prompt = prompt_text

        # IMPORTANT — no resource_constraint cap any more.  Magnus cluster has
        # ample compute (6× A100 + 112 CPU), so per-run nevents is driven by
        # the manifest spec and the agent's pheno-judgment.  Earlier we capped
        # at 5000 events for safety; that has been removed.  The plan in
        # collider_plan.md is now the SINGLE SOURCE OF TRUTH for event counts.
        resource_constraint = ""

        # Strict plan-adherence directive — prevents agents from unilaterally
        # rewriting the plan (e.g. "I'll skip FeynRules and use analytic
        # Breit-Wigner instead because the spin-2 UFO is hard").
        plan_adherence = (
            "\n\n---\n"
            "## STRICT PLAN-ADHERENCE DIRECTIVE (read before any decision)\n\n"
            "The plan above (collider_plan.md, top of this prompt) is binding.\n"
            "You are NOT authorised to override its model-implementation choices,\n"
            "tool choices, or pipeline structure unless ALL of the following hold:\n\n"
            "1. The plan's literal instruction is **physically impossible** in this\n"
            "   environment (missing binary, missing dataset, unsupported syntax).\n"
            "2. You document the impossibility concretely in\n"
            "   ``progress/<run>/blocker_<step>.md`` with the exact error message.\n"
            "3. Your fallback is the smallest possible deviation — never replace\n"
            "   an entire workflow stage with an analytic shortcut.\n\n"
            "Specifically forbidden (without satisfying the three rules above):\n\n"
            "- Skipping FeynRules / UFO model generation when the plan asks for it.\n"
            "  Spin-2 / non-trivial Lorentz structures ARE achievable via FeynRules\n"
            "  + UFO export; difficulty is not a reason to skip.\n"
            "- Replacing MadGraph events with analytic cross-section formulas.\n"
            "- Skipping Pythia8 / Delphes stages declared in the plan.\n"
            "- Reducing the number of scan points / mass benchmarks declared in\n"
            "  the plan's experiment_design section.\n\n"
            "If you genuinely cannot complete a step, STOP and write the blocker\n"
            "note — do NOT silently substitute.  The downstream requirements gate\n"
            "will see the blocker and the pipeline will either rerun the agent or\n"
            "proceed with the unmet requirement flagged.\n"
        )
        canonical_output = (
            "\n\n---\n"
            "## MANDATORY CANONICAL OUTPUT (write BEFORE you exit)\n\n"
            "When all event generation, analysis and figure production is finished,\n"
            "write a SINGLE machine-readable file at workspace root:\n\n"
            "    results.json\n\n"
            "It MUST contain at least the following keys (extra keys allowed):\n\n"
            "```json\n"
            "{\n"
            '  "primary_metric": <number>,                  // headline scalar (e.g. peak position GeV, integrated yield)\n'
            '  "metric_key": "<string>",                     // identifier for primary_metric\n'
            '  "metrics": {                                   // ALL numeric scientific results\n'
            '    "cross_section_pb": <number>,\n'
            '    "peak_position_gev": <number>,\n'
            '    "integrated_yield_at_100fbinv": <number>,\n'
            '    "...other physics numbers...": <number>\n'
            "  },\n"
            '  "hypotheses": {                                // explicit per-hypothesis verdicts\n'
            '    "h1": {"supported": true|false, "value": <number>, "details": "..."},\n'
            '    "h2": {"supported": true|false, "details": "..."},\n'
            '    "h3": {"supported": true|false, "details": "..."}\n'
            "  },\n"
            '  "summary": "human-readable 1-paragraph narrative of the run",\n'
            '  "structured_results": {"artifacts": {"figures": [...], "data": [...]}}\n'
            "}\n"
            "```\n\n"
            "Rules:\n"
            "1. **One file. results.json. Workspace root.**\n"
            "2. The pipeline reads this file once after your session ends. If it is\n"
            "   missing or malformed, downstream rubric scoring degrades to zero.\n"
            "3. All numeric values must be JSON numbers (not 'NaN' strings, not numpy\n"
            "   types). Use `null` for genuinely missing values.\n"
            "4. The downstream pipeline does NOT re-run code or refine python files.\n"
            "   It reads results.json and either proceeds (good) or rejects (missing/\n"
            "   bad). Your numbers in results.json ARE the experimental output of record.\n"
        )
        # Prepend a FOLLOWUP DELTA section if the requirements gate asked
        # for a rerun.  This goes BEFORE the (possibly incremental) plan so
        # the agent reads must_pass-failures first.
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
            prefix + full_prompt + plan_adherence + resource_constraint + canonical_output,
            encoding="utf-8",
        )
        logger.debug(
            "ColliderAgentSandbox: wrote prompt to %s (incremental=%s)",
            prompt_path,
            is_incremental,
        )

        # Standard ColliderAgent output directories (idempotent; preserves existing)
        for subdir in ("models", "scripts", "events", "analysis", "output/figures", "output/data", "progress"):
            (workspace / subdir).mkdir(parents=True, exist_ok=True)

        # Install ColliderAgent skills/agents
        if self.config.install_skills:
            self._install_skills(workspace)

        return workspace

    def _merge_incremental_results(self, workspace: Path) -> None:
        """Union the freshly-written results.json with the snapshotted previous one.

        Looks for the most recent ``stage-12_v{N}/runs/results.json`` two levels
        up from the workspace
        (workspace = ``run_dir/stage-12/runs/collider_workspace``).
        If found, performs a shallow key-level union with these rules:

          - ``metrics``: new wins on collision; new keys added; old-only kept.
          - ``structured_results.artifacts.{figures,data,scripts,models}``:
            list concat, dedupe preserving order.
          - other top-level keys: new wins.

        Writes the merged document back to ``workspace/results.json`` and
        an ``incremental_merge.json`` audit sidecar with kept/updated/new keys.
        """
        new_path = workspace / "results.json"
        if not new_path.is_file():
            logger.debug("Incremental merge: no new results.json — skipping")
            return

        # workspace = .../run_dir/stage-12/runs/collider_workspace
        try:
            run_dir = workspace.parents[2]
        except IndexError:
            logger.debug("Incremental merge: workspace has unexpected parent depth")
            return

        snapshots = sorted(
            (p for p in run_dir.glob("stage-12_v*") if p.is_dir()),
            key=lambda p: int(p.name.replace("stage-12_v", "") or "0"),
        )
        if not snapshots:
            logger.debug("Incremental merge: no stage-12_v* snapshot found")
            return
        snap_results = snapshots[-1] / "runs" / "results.json"
        if not snap_results.is_file():
            logger.debug("Incremental merge: snapshot has no results.json")
            return

        try:
            old_doc = json.loads(snap_results.read_text(encoding="utf-8"))
            new_doc = json.loads(new_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Incremental merge skipped: %s", exc)
            return

        merged, kept, updated, new_keys = self._merge_docs(old_doc, new_doc)
        new_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")

        try:
            rel_from = str(snap_results.relative_to(run_dir))
        except ValueError:
            rel_from = str(snap_results)
        audit = {
            "merged_from": rel_from,
            "merged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kept_keys": kept,
            "updated_keys": updated,
            "new_keys": new_keys,
        }
        (workspace / "incremental_merge.json").write_text(
            json.dumps(audit, indent=2), encoding="utf-8"
        )
        logger.info(
            "Incremental merge: kept=%d, updated=%d, new=%d",
            len(kept), len(updated), len(new_keys),
        )

    @staticmethod
    def _merge_docs(
        old_doc: dict, new_doc: dict
    ) -> tuple[dict, list[str], list[str], list[str]]:
        """Shallow union with the documented rules. Returns
        ``(merged, kept_keys, updated_keys, new_keys)`` with dotted-path keys."""
        merged: dict[str, Any] = dict(old_doc) if isinstance(old_doc, dict) else {}
        kept: list[str] = []
        updated: list[str] = []
        new_keys: list[str] = []

        old_metrics = (old_doc.get("metrics") or {}) if isinstance(old_doc, dict) else {}
        new_metrics = (new_doc.get("metrics") or {}) if isinstance(new_doc, dict) else {}
        merged_metrics = dict(old_metrics)
        for k, v in new_metrics.items():
            if k in merged_metrics and merged_metrics[k] != v:
                updated.append(f"metrics.{k}")
            elif k not in merged_metrics:
                new_keys.append(f"metrics.{k}")
            merged_metrics[k] = v
        for k in old_metrics:
            if k not in new_metrics:
                kept.append(f"metrics.{k}")
        if merged_metrics:
            merged["metrics"] = merged_metrics

        old_sr = old_doc.get("structured_results") if isinstance(old_doc, dict) else None
        new_sr = new_doc.get("structured_results") if isinstance(new_doc, dict) else None
        merged_sr: dict[str, Any] = dict(old_sr) if isinstance(old_sr, dict) else {}
        old_arts = old_sr.get("artifacts") if isinstance(old_sr, dict) else None
        new_arts = new_sr.get("artifacts") if isinstance(new_sr, dict) else None
        if isinstance(old_arts, dict) or isinstance(new_arts, dict):
            merged_arts = dict(old_arts) if isinstance(old_arts, dict) else {}
            for cat in ("figures", "data", "scripts", "models"):
                old_list = list(merged_arts.get(cat) or [])
                add_list = list((new_arts or {}).get(cat) or [])
                if not old_list and not add_list:
                    continue
                seen: set[Any] = set()
                combined: list[Any] = []
                for item in old_list + add_list:
                    if item not in seen:
                        seen.add(item)
                        combined.append(item)
                if combined != old_list:
                    if old_list:
                        updated.append(f"structured_results.artifacts.{cat}")
                    else:
                        new_keys.append(f"structured_results.artifacts.{cat}")
                else:
                    kept.append(f"structured_results.artifacts.{cat}")
                merged_arts[cat] = combined
            merged_sr["artifacts"] = merged_arts
        if isinstance(new_sr, dict):
            for k, v in new_sr.items():
                if k != "artifacts":
                    merged_sr[k] = v
        if merged_sr:
            merged["structured_results"] = merged_sr

        if isinstance(new_doc, dict):
            for k, v in new_doc.items():
                if k in ("metrics", "structured_results"):
                    continue
                if k in merged and merged[k] != v:
                    updated.append(k)
                elif k not in merged:
                    new_keys.append(k)
                merged[k] = v

        return merged, kept, updated, new_keys

    def _build_workspace_manifest(self, workspace: Path) -> dict[str, Any]:
        """Snapshot top-level workspace artifacts for the continuation context.

        Walks five canonical sub-trees one level deep and records
        ``{path, kind, mtime, size}`` per entry.
        """
        roots = ("models", "events", "analysis", "output/figures", "output/data")
        entries: list[dict[str, Any]] = []
        for rel in roots:
            base = workspace / rel
            if not base.is_dir():
                continue
            for child in sorted(base.iterdir()):
                rel_path = f"{rel}/{child.name}" + ("/" if child.is_dir() else "")
                kind = "dir" if child.is_dir() else "file"
                try:
                    stat = child.stat()
                    mtime = stat.st_mtime
                    size = stat.st_size if child.is_file() else None
                except OSError:
                    mtime = None
                    size = None
                entries.append({
                    "path": rel_path,
                    "kind": kind,
                    "mtime": mtime,
                    "size": size,
                })
        return {
            "generated_at": time.time(),
            "workspace": str(workspace),
            "entries": entries,
        }

    def _install_skills(self, workspace: Path) -> None:
        """Install ColliderAgent skills and agents so Claude Code can load them.

        Following the ColliderAgent README, skills and agents are installed to
        ``~/.claude/skills/`` and ``~/.claude/agents/`` (global scope).
        Additionally, a project-scoped copy is placed in
        ``<workspace>/.claude/`` so the session picks them up when Claude Code
        runs from the workspace directory.
        """
        ca_dir = Path(self.config.collider_agent_dir).expanduser().resolve()
        skills_src = ca_dir / "src" / "skills"
        agents_src = ca_dir / "src" / "agents"

        # --- Global installation to ~/.claude/ (matches ColliderAgent README) ---
        global_claude = Path.home() / ".claude"
        global_claude.mkdir(exist_ok=True)

        targets = [
            (skills_src, global_claude / "skills"),
            (agents_src, global_claude / "agents"),
        ]

        for src, dst in targets:
            if not src.exists():
                logger.warning(
                    "ColliderAgentSandbox: %s not found — skills may be missing", src
                )
                continue
            dst.mkdir(parents=True, exist_ok=True)
            # Merge: copy individual skill dirs rather than overwriting the whole tree
            # This avoids clobbering other skills the user may have installed
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
            logger.info(
                "ColliderAgentSandbox: installed %s → %s (global)", src, dst
            )

        # --- Project-scoped copy in workspace/.claude/ (takes priority in CWD) ---
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
                "ColliderAgentSandbox: installed %s → %s (project-scoped)", src, dst
            )

    def _build_command(self) -> list[str]:
        """Construct the ``claude`` CLI invocation."""
        binary = self.config.claude_binary
        if not binary:
            binary = shutil.which("claude") or "claude"

        cmd = [binary, "-p", _CLAUDE_INSTRUCTION]

        # Max turns
        if self.config.max_turns > 0:
            cmd += ["--max-turns", str(self.config.max_turns)]

        # Extra args (e.g. --dangerously-skip-permissions)
        for arg in self.config.extra_args:
            if arg:
                cmd.append(arg)

        return cmd

    def _build_env(self) -> dict[str, str]:
        """Build environment variables for the Claude Code subprocess."""
        env = os.environ.copy()

        # Magnus credentials if provided
        if self.config.magnus_address:
            env["MAGNUS_ADDRESS"] = self.config.magnus_address
        if self.config.magnus_token:
            env["MAGNUS_TOKEN"] = self.config.magnus_token

        return env

    def _collect_artifacts(self, workspace: Path) -> dict[str, list[str]]:
        """Scan workspace for output artifacts and return a categorized dict."""
        artifacts: dict[str, list[str]] = {
            "figures": [],
            "data": [],
            "scripts": [],
            "models": [],
            "logs": [],
        }

        # Figures
        for pattern in ("output/figures/*.pdf", "output/figures/*.png", "output/**/*.pdf", "output/**/*.png"):
            for p in sorted(workspace.glob(pattern)):
                rel = str(p.relative_to(workspace))
                if rel not in artifacts["figures"]:
                    artifacts["figures"].append(rel)

        # Data files
        for pattern in ("output/data/*.txt", "output/data/*.csv", "output/data/*.json", "output/**/*.dat"):
            for p in sorted(workspace.glob(pattern)):
                rel = str(p.relative_to(workspace))
                if rel not in artifacts["data"]:
                    artifacts["data"].append(rel)

        # MadGraph/analysis scripts
        for pattern in ("scripts/*.mg5", "scripts/*.py", "scripts/*.ma5"):
            for p in sorted(workspace.glob(pattern)):
                artifacts["scripts"].append(str(p.relative_to(workspace)))

        # FeynRules/UFO models
        for pattern in ("models/*.fr", "models/**/*.py"):
            for p in sorted(workspace.glob(pattern)):
                artifacts["models"].append(str(p.relative_to(workspace)))

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
        """Convert ColliderAgent output into AutoResearchClaw metrics.

        Coverage stats describe the sandbox run.  Domain metrics (cross
        sections, peak positions, hypothesis flags) come from the
        agent-written ``results.json`` at workspace root and are merged in
        here so stage 14 / the bench rubric see them.
        """
        metrics: dict[str, Any] = {
            "collider_agent_success": 1.0 if returncode == 0 and not timed_out else 0.0,
            "figures_produced": float(len(artifacts.get("figures", []))),
            "scripts_generated": float(len(artifacts.get("scripts", []))),
            "models_generated": float(len(artifacts.get("models", []))),
        }

        summary_path = workspace / "execution_summary.md"
        if summary_path.exists():
            summary_text = summary_path.read_text(encoding="utf-8")
            metrics["pipeline_steps_completed"] = float(summary_text.lower().count("completed"))
            metrics["pipeline_steps_failed"] = float(summary_text.lower().count("failed"))

        # Merge agent-written domain metrics from canonical results.json.
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
            total_possible = max(
                1.0, metrics["figures_produced"] + metrics.get("pipeline_steps_failed", 0.0)
            )
            metrics["primary_metric"] = metrics["figures_produced"] / total_possible

        return metrics

    # Top-level keys written by the sandbox's own _write_summary().  Skipped
    # when probing for agent-authored canonical output.
    _SANDBOX_META_KEYS = frozenset(
        {"source", "returncode", "elapsed_sec", "timed_out", "artifacts", "status"}
    )

    @classmethod
    def _read_agent_results(cls, workspace: Path) -> dict[str, Any] | None:
        """Read the agent-written canonical results.json (or fallbacks).

        Resolution order:
          1. ``workspace/results.json``  — only if it carries AGENT keys
             (``metrics``, ``primary_metric``, ``hypotheses``,
             ``structured_results``).  Sandbox-meta-only stubs are skipped.
          2. ``workspace/output/data/results.json``  (older convention)
        """
        for path in (workspace / "results.json",
                     workspace / "output" / "data" / "results.json"):
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            if (
                "metrics" in data
                or "primary_metric" in data
                or "hypotheses" in data
                or "structured_results" in data
            ):
                return data
            # If only sandbox-meta keys are present, this is the stub from
            # _write_summary() — try next candidate.
            non_meta = set(data.keys()) - cls._SANDBOX_META_KEYS
            if non_meta:
                # Bare data without canonical keys; do nothing — we only
                # surface explicitly-structured agent output.
                pass
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

        If ColliderAgent already wrote a structured ``results.json`` during
        the session, this method merges sandbox metadata (source, returncode,
        elapsed_sec, timed_out, status, artifacts) into it without clobbering
        the model-emitted content. Existing keys in the file take precedence
        over sandbox defaults, EXCEPT ``returncode``/``elapsed_sec``/``timed_out``
        which are always sandbox-authoritative.
        """
        sandbox_meta = {
            "source": "collider_agent",
            "returncode": returncode,
            "elapsed_sec": round(elapsed, 2),
            "timed_out": timed_out,
            "artifacts": artifacts,
            "status": "success" if returncode == 0 and not timed_out else ("timeout" if timed_out else "failed"),
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
        # Existing wins for "soft" keys
        for k, v in sandbox_meta.items():
            if k in ("returncode", "elapsed_sec", "timed_out"):
                merged[k] = v  # sandbox-authoritative
            elif k not in merged:
                merged[k] = v
        # If artifacts not pre-existing, attach sandbox-collected artifacts
        if "artifacts" not in existing:
            merged["artifacts"] = artifacts
        results_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        logger.debug("ColliderAgentSandbox: wrote results to %s", results_path)
