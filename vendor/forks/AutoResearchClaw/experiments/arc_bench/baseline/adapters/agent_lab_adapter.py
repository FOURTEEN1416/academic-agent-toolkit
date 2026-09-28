"""Agent Laboratory adapter (samuelschmidgall/AgentLaboratory).

Entry point: ``python ai_lab_repo.py --yaml-location <config.yaml>``. The
upstream CLI accepts only ``--yaml-location``; everything else (research
topic, model, task notes, copilot mode) lives in the YAML.

This adapter:

1. Renders a per-run YAML config from the ARC-Bench topic manifest.
2. Sets ``AGENTLAB_RESEARCH_DIR`` to a per-run absolute path under
   ``/playpen2`` (so /home does not fill up). The upstream patch at
   ``ai_lab_repo.py:14`` reads that env var.
3. Shells out with ``cwd=<repo>`` so AgentLab finds its own modules.
4. Maps the produced ``research_dir_0_lab_<idx>/{src,tex}`` to a
   ``StandardArtifacts`` bundle the ARC-Bench bridge can wrap.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .base import FrameworkAdapter, FrameworkResult, StandardArtifacts


# Baseline scratch root. Override with ARC_BASELINE_ROOT (these conda envs /
# research dirs are large and machine-specific — see baseline/README.md).
_BASELINE_ROOT = Path(
    os.environ.get("ARC_BASELINE_ROOT", str(Path.home() / "arc_bench" / "baselines"))
)
DEFAULT_PLAYPEN_RESEARCH_ROOT = _BASELINE_ROOT / "agent_lab" / "research_dir"
DEFAULT_AGENTLAB_PYTHON = str(_BASELINE_ROOT / "agent_lab" / "conda_env" / "bin" / "python")


class AgentLabAdapter(FrameworkAdapter):
    framework_id = "agent_lab"

    def __init__(self, *, llm_backend: str = "gpt-4o",
                 lit_review_backend: str = "gpt-4o",
                 mlesolver_max_steps: int = 3,
                 papersolver_max_steps: int = 1,
                 num_papers_lit_review: int = 1,  # min-viable: rc_full skips lit-review entirely (stage-07 is manifest synthesis pre-baked); 1-paper lit-review is the closest AgentLab analog. NOT a prompt directive — a config knob.
                 strict_parity: bool = True,
                 research_dir_root: Path | None = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.llm_backend = llm_backend
        self.lit_review_backend = lit_review_backend
        self.mlesolver_max_steps = mlesolver_max_steps
        self.papersolver_max_steps = papersolver_max_steps
        self.num_papers_lit_review = num_papers_lit_review
        # strict_parity=True: drop ALL directive task-notes; match rc_full's
        # open-ended bench_note instead. strict_parity=False: keep the
        # phase-specific task-notes that compensate for AgentLab loops.
        self.strict_parity = strict_parity
        self.repo_dir = self.external_root / "AgentLaboratory"
        self.research_dir_root = Path(
            research_dir_root or os.environ.get(
                "ARC_AGENTLAB_RESEARCH_ROOT", DEFAULT_PLAYPEN_RESEARCH_ROOT
            )
        )

    # ---------------------------------------------------------------- availability
    def is_available(self) -> tuple[bool, str]:
        entry = self.repo_dir / "ai_lab_repo.py"
        if not entry.is_file():
            return (False, f"AgentLaboratory not cloned at {self.repo_dir}")
        if not os.environ.get("OPENAI_API_KEY"):
            return (False, "OPENAI_API_KEY not set")
        return (True, "ok")

    # ------------------------------------------------------------------- yaml prep
    def _build_yaml_config(self, topic: dict, *, api_key: str) -> dict:
        """Render an ARC-Bench-flavored AgentLab config from the manifest."""
        ed = topic.get("experiment_design") or {}
        question = ed.get("research_question") or topic.get("topic", "")
        synthesis = topic.get("synthesis", "").strip()
        hypotheses = topic.get("hypotheses") or []
        conditions = ed.get("conditions") or []
        metrics = ed.get("metrics") or []
        datasets = ed.get("datasets") or []

        cond_lines = "; ".join(
            f"{c.get('name')}: {c.get('description', '').strip()}" for c in conditions
        )
        metric_lines = ", ".join(
            f"{m.get('name')} ({m.get('direction', '')})" for m in metrics
        )
        dataset_lines = ", ".join(d.get("name", "") for d in datasets)
        hyp_lines = " | ".join(
            f"{h.get('id', f'H{i+1}')}: {h.get('statement', '')}"
            for i, h in enumerate(hypotheses)
        )

        # ------------------------------------------------------------------
        # STRICT INPUT-PARITY MODE (matches rc_full's exp_plan.yaml content):
        # research-topic carries exactly the fields rc_full's stage-09
        # exp_plan.yaml carries — research_question, conditions, metrics,
        # datasets, hypotheses, an open-ended bench_note — and NOTHING ELSE.
        # No phase-by-phase task-notes that would constitute extra HITL.
        #
        # Open-ended mode (strict_parity=False, kept for legacy runs):
        # the previous prescriptive task-notes that compensated for AgentLab
        # loops are restored.
        # ------------------------------------------------------------------
        bench_note = (
            "This is an ARC-Bench topic. Implement a competent experiment "
            "addressing the research question. You may tighten or extend the "
            "listed conditions/metrics if your design is coherent."
        )

        # Framework-fix-only task-notes: these compensate for AgentLab's
        # *internal control-flow pathologies* (lit-review SUMMARY-loop never
        # exits, data-prep "shall I proceed?" handshake never advances)
        # WITHOUT prescribing any task-level scientific behavior. rc_full has
        # no equivalent pathology — it doesn't share AgentLab's literature_review
        # while-loop or its post-step dialogue-turn pattern. Including these
        # under strict_parity is fair because they let AgentLab "be a working
        # framework" rather than encoding strict-grade-flavored guidance.
        framework_fix_notes = {
            "literature-review": [
                # Framework control-flow ONLY: tells the agent (a) what
                # AgentLab's lit-review depth knob is set to (=1, mirrors
                # rc_full's pre-baked synthesis state) and (b) the literal
                # tag syntax the AgentLab orchestrator parses
                # (```FULL_TEXT <id>``` / ```ADD_PAPER ...```). NO scientific
                # guidance. Equivalent to documenting the framework's API.
                "You only need ONE paper for the lit review. AgentLab is "
                "configured with num_papers_lit_review=1. After your FIRST "
                "SUMMARY query returns results, immediately issue ```FULL_TEXT "
                "<paper_id>``` for one paper, then ```ADD_PAPER <paper_id>\\n"
                "<one-paragraph summary>``` to finalize. Do NOT issue more "
                "than two SUMMARY queries — pick a paper from the first "
                "result set and proceed.",
            ],
            "data-preparation": [
                "Generate code immediately in your next turn. The orchestrator "
                "does not respond to clarifying questions like 'shall I proceed?'",
            ],
        }

        if self.strict_parity:
            # Mirror the rc_full stage-09/exp_plan.yaml shape inside one string.
            research_topic = (
                f"topic_id: {topic.get('id', '?')}\n"
                f"research_question: {question}\n"
                f"\nBackground:\n{synthesis}\n"
                f"\nConditions:\n  - " +
                "\n  - ".join(
                    f"{c.get('name')}: {c.get('description', '').strip()}"
                    for c in conditions
                ) +
                f"\n\nMetrics:\n  - " +
                "\n  - ".join(
                    f"{m.get('name')} ({m.get('direction', '')}): "
                    f"{m.get('description', '').strip()}"
                    for m in metrics
                ) +
                f"\n\nDatasets:\n  - " +
                "\n  - ".join(
                    f"{d.get('name')} ({d.get('source', '')})" for d in datasets
                ) +
                f"\n\nHypotheses:\n  - " +
                "\n  - ".join(
                    f"{h.get('id', f'H{i+1}')}: {h.get('statement', '')}"
                    for i, h in enumerate(hypotheses)
                ) +
                f"\n\nbench_note: {bench_note}\n"
            )
            # Strict scientific parity: no task-fidelity prescriptions, but
            # KEEP framework-bug-compensation so AgentLab's lit-review and
            # data-prep loops can exit at all.
            task_notes = framework_fix_notes
        else:
            research_topic = (
                f"{question}\n\n"
                f"Background: {synthesis}\n\n"
                f"Hypotheses to evaluate: {hyp_lines}\n"
                f"Required conditions: {cond_lines}\n"
                f"Metrics to report (mean over >=5 seeds): {metric_lines}\n"
                f"Datasets: {dataset_lines}\n"
                "Constraints: CPU-only run, single core, target wall-clock <= 240s "
                "for the experiment portion. Produce numerical results AND a brief "
                "writeup interpreting them."
            )
            task_notes = {
                "literature-review": [
                    "You only need ONE paper for the lit review. After your FIRST "
                    "SUMMARY query returns results, immediately issue ```FULL_TEXT "
                    "<paper_id>``` for the most relevant paper, then ```ADD_PAPER "
                    "<paper_id>\\n<concise summary>``` to finalize. Do NOT issue "
                    "more than two SUMMARY queries — pick a paper from the first "
                    "result set and proceed.",
                    "Stay focused: the experiment topic is fixed; do not pivot.",
                ],
                "plan-formulation": [
                    "Design a single CPU-friendly experiment that compares all "
                    "required conditions on all listed datasets, averaged over >=5 seeds.",
                    "Do NOT propose a different research question; stay on the one given.",
                    "Submit your plan promptly; do not iterate forever.",
                ],
                "data-preparation": [
                    "Use the sklearn datasets named in the topic exactly. "
                    "If the topic asks for synthetic benchmarks (Rastrigin / "
                    "Rosenbrock / Ackley / etc.), GENERATE THEM WITH numpy "
                    "DIRECTLY in Python — do NOT search HuggingFace for them.",
                    "Hold out 20% of each dataset as a stratified test split.",
                    "Do NOT ask 'shall I proceed?' or wait for permission.",
                ],
                "running-experiments": [
                    "Implement every named condition; do not silently drop any.",
                    "Report each metric per dataset per condition, mean and std over seeds.",
                    "Keep total runtime under 5 minutes on a single CPU core.",
                    "Save final numbers to a JSON file inside the lab directory.",
                ],
                "results-interpretation": [
                    "Explicitly answer each hypothesis (supported / "
                    "partially_supported / unsupported / inconclusive) with the "
                    "numerical evidence.",
                ],
                "report-writing": [
                    "Keep the report short (~3 pages of LaTeX); focus on the table "
                    "of metrics and the per-hypothesis verdicts.",
                ],
            }

        return {
            "copilot-mode": False,
            "research-topic": research_topic,
            "api-key": api_key,
            "llm-backend": self.llm_backend,
            "lit-review-backend": self.lit_review_backend,
            "language": "English",
            "num-papers-lit-review": self.num_papers_lit_review,
            "num-papers-to-write": 1,
            "parallel-labs": False,
            "mlesolver-max-steps": self.mlesolver_max_steps,
            "papersolver-max-steps": self.papersolver_max_steps,
            "lab-index": 1,
            "load-existing": False,
            "except-if-fail": False,
            "compile-latex": False,
            "task-notes": task_notes,
        }

    # ------------------------------------------------------------------------ run
    def run(self, topic: dict, output_dir: Path) -> FrameworkResult:
        ok, reason = self.is_available()
        if not ok:
            return self._skipped(topic, output_dir, reason)

        output_dir.mkdir(parents=True, exist_ok=True)
        api_key = os.environ["OPENAI_API_KEY"]
        cfg = self._build_yaml_config(topic, api_key=api_key)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_tag = f"{topic['id']}-{ts}"
        # Upstream ai_lab_repo composes paths via f"./{lab_dir}" in several
        # places, which breaks if RESEARCH_DIR_PATH is absolute (the leading
        # '.' makes the absolute path act relative to cwd). To stay
        # compatible we use a *relative* per-run dir under the repo, then
        # copy the produced tree to /playpen2 after the run completes.
        relative_research_dir = f"arc_research_dir_{run_tag}"
        research_dir_in_repo = self.repo_dir / relative_research_dir
        # Final archival home on playpen2 (so /home doesn't fill up).
        playpen_archive = self.research_dir_root / run_tag
        playpen_archive.parent.mkdir(parents=True, exist_ok=True)

        yaml_path = output_dir / "agentlab_config.yaml"
        with yaml_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(cfg, fh, sort_keys=False)

        # Don't echo api-key into the saved copy that lives in our run dir
        cfg_redacted = {**cfg, "api-key": "<redacted>"}
        (output_dir / "agentlab_config.redacted.yaml").write_text(
            yaml.safe_dump(cfg_redacted, sort_keys=False), encoding="utf-8"
        )

        py_exe = os.environ.get("ARC_AGENTLAB_PYTHON", DEFAULT_AGENTLAB_PYTHON)
        if not Path(py_exe).is_file():
            py_exe = sys.executable
        cmd = [
            py_exe, "-u", "ai_lab_repo.py",
            "--yaml-location", str(yaml_path),
        ]

        env = {
            **os.environ,
            # Relative path so upstream's f"./{lab_dir}" composition works.
            "AGENTLAB_RESEARCH_DIR": relative_research_dir,
            "PYTHONUNBUFFERED": "1",
        }

        if self.dry_run:
            (output_dir / "command.txt").write_text(
                f"cwd={self.repo_dir}\n"
                f"AGENTLAB_RESEARCH_DIR={relative_research_dir}\n"
                f"playpen_archive={playpen_archive}\n"
                f"OPENAI_BASE_URL={env.get('OPENAI_BASE_URL', '')}\n"
                f"cmd={' '.join(cmd)}\n",
                encoding="utf-8",
            )
            return FrameworkResult(
                framework_id=self.framework_id,
                topic_id=topic["id"],
                status="skipped",
                returncode=None,
                elapsed_sec=0.0,
                output_dir=str(output_dir),
                extra={"dry_run": True,
                       "relative_research_dir": relative_research_dir,
                       "playpen_archive": str(playpen_archive)},
            )

        log_path = output_dir / "agentlab_stdout.log"
        t0 = time.monotonic()
        try:
            with log_path.open("w", encoding="utf-8") as logfh:
                completed = subprocess.run(
                    cmd, cwd=str(self.repo_dir), env=env,
                    stdout=logfh, stderr=subprocess.STDOUT,
                    timeout=self.budget_sec,
                )
            elapsed = time.monotonic() - t0
            status = "completed" if completed.returncode == 0 else "failed"
            rc: int | None = completed.returncode
        except subprocess.TimeoutExpired:
            elapsed = float(self.budget_sec)
            status = "timeout"
            rc = None
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - t0
            status = "failed"
            rc = None
            (output_dir / "agentlab_error.txt").write_text(repr(exc),
                                                           encoding="utf-8")

        # Locate the lab directory AgentLab created inside the repo:
        # Layout: <repo>/<relative_research_dir>/research_dir_0_lab_1/{src,tex,...}
        candidates = []
        if research_dir_in_repo.is_dir():
            candidates = sorted(p for p in research_dir_in_repo.iterdir()
                                if p.is_dir() and p.name.startswith("research_dir_"))
        lab_dir_local = candidates[-1] if candidates else research_dir_in_repo

        # Move the produced tree to playpen2 so /home doesn't accumulate runs.
        if research_dir_in_repo.is_dir():
            try:
                if playpen_archive.exists():
                    shutil.rmtree(playpen_archive)
                shutil.move(str(research_dir_in_repo), str(playpen_archive))
            except Exception as exc:  # noqa: BLE001
                (output_dir / "agentlab_archive_error.txt").write_text(
                    f"failed to move {research_dir_in_repo} -> {playpen_archive}: {exc}\n",
                    encoding="utf-8",
                )

        # Re-resolve lab_dir under playpen2 if the move succeeded.
        if playpen_archive.is_dir():
            archived_candidates = sorted(p for p in playpen_archive.iterdir()
                                         if p.is_dir() and p.name.startswith("research_dir_"))
            if archived_candidates:
                lab_dir_local = archived_candidates[-1]

        artifacts = _read_agent_lab_artifacts(lab_dir_local)
        self._write_standard_artifacts(
            output_dir, artifacts,
            framework_meta={
                "native_run": str(lab_dir_local),
                "playpen_archive": str(playpen_archive),
                "llm_backend": self.llm_backend,
            },
        )

        # Convenience copies of the writeup at the run dir top level
        for name in ("research_report.md", "paper.md", "paper.tex"):
            src = lab_dir_local / name
            if src.is_file():
                shutil.copy(src, output_dir / src.name)
                break

        return FrameworkResult(
            framework_id=self.framework_id,
            topic_id=topic["id"],
            status=status,
            returncode=rc,
            elapsed_sec=round(elapsed, 1),
            output_dir=str(output_dir),
            artifacts=artifacts,
            extra={
                "native_run": str(lab_dir_local),
                "playpen_archive": str(playpen_archive),
                "yaml_config": str(yaml_path),
                "stdout_log": str(log_path),
            },
        )


def _read_agent_lab_artifacts(run_dir: Path) -> StandardArtifacts:
    out = StandardArtifacts()
    if not run_dir.is_dir():
        return out

    # Paper text — may be markdown or tex
    for name in ("research_report.md", "paper.md"):
        p = run_dir / name
        if p.is_file():
            out.paper_text = p.read_text(encoding="utf-8", errors="ignore")
            break
    if out.paper_text is None:
        for tex_dir in (run_dir / "tex", run_dir):
            if not tex_dir.is_dir():
                continue
            for tex in tex_dir.glob("*.tex"):
                out.paper_text = tex.read_text(encoding="utf-8", errors="ignore")
                break
            if out.paper_text:
                break

    # Numerical results — AgentLab does not write a canonical metrics file;
    # we scan src/ for .json output produced by the experiment script.
    src_dir = run_dir / "src"
    metrics_blob: dict | None = None
    if src_dir.is_dir():
        json_files = sorted(src_dir.glob("*.json"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        for jf in json_files:
            try:
                metrics_blob = json.loads(jf.read_text())
                break
            except Exception:  # noqa: BLE001
                continue
    if metrics_blob is not None:
        out.experiment_summary = metrics_blob

    out.stages_done = 23 if out.paper_text else 10
    return out
