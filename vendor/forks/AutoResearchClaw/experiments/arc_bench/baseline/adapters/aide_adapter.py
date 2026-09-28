"""AIDE ML adapter (WecoAI/aideml).

Mirrors :class:`AgentLabAdapter` strict-parity input shape so AIDE receives
the SAME information as agent_lab/rc_full and NOTHING ELSE — no
phase-specific scaffolding, no "implement every condition" directive, no
"do not pivot" reminders. The only knobs the adapter tunes are:

* ``code_model`` / ``feedback_model`` / ``report_model`` — proxy-routing
  choices, not scientific-content choices.
* ``agent_steps`` / ``num_drafts`` — compute budget (matches the
  ``mlesolver_max_steps`` knob in :class:`AgentLabAdapter`).

Run flow:

1. Build the strict-parity ``goal`` and ``eval`` strings from the topic
   manifest (research_question + synthesis + conditions + metrics +
   datasets + hypotheses + open-ended ``bench_note``).
2. Materialize a stub ``data_dir`` containing only a ``README.md`` that
   tells the agent there is no external dataset (sklearn / synthetic
   datasets are referenced in the goal). AIDE requires ``data_dir`` to
   exist; we do not pre-load any data the agent didn't ask for.
3. Shell out to ``_aide_runner.py`` inside the AIDE conda env so torch /
   AIDE imports stay isolated.
4. Map AIDE's ``logs/<exp>/`` outputs into the ``StandardArtifacts``
   bundle our judge reads.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .base import FrameworkAdapter, FrameworkResult, StandardArtifacts


# Baseline scratch root. Override with ARC_BASELINE_ROOT (these conda envs /
# workspaces are large and machine-specific — see baseline/README.md).
_BASELINE_ROOT = Path(
    os.environ.get("ARC_BASELINE_ROOT", str(Path.home() / "arc_bench" / "baselines"))
)
DEFAULT_PLAYPEN_LOG_ROOT = _BASELINE_ROOT / "aide_ml" / "logs"
DEFAULT_PLAYPEN_WORKSPACE_ROOT = _BASELINE_ROOT / "aide_ml" / "workspaces"
DEFAULT_AIDE_PYTHON = str(_BASELINE_ROOT / "aide_ml" / "conda_env" / "bin" / "python")


class AideAdapter(FrameworkAdapter):
    framework_id = "aide_ml"

    def __init__(
        self,
        *,
        code_model: str = "gpt-5.3-codex",
        feedback_model: str = "gpt-4o",
        report_model: str = "gpt-4o",
        agent_steps: int = 10,
        num_drafts: int = 3,
        strict_parity: bool = True,
        log_root: Path | None = None,
        workspace_root: Path | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.code_model = os.environ.get("ARC_AIDE_CODE_MODEL", code_model)
        self.feedback_model = os.environ.get("ARC_AIDE_FEEDBACK_MODEL", feedback_model)
        self.report_model = os.environ.get("ARC_AIDE_REPORT_MODEL", report_model)
        self.agent_steps = int(os.environ.get("ARC_AIDE_STEPS", agent_steps))
        self.num_drafts = int(os.environ.get("ARC_AIDE_NUM_DRAFTS", num_drafts))
        # AIDE has no analog to AgentLab's lit-review / data-prep
        # control-flow pathologies, so strict_parity=True simply means "do
        # not embed any phase-specific scaffolding into goal/eval". Kept as
        # a flag for symmetry with AgentLabAdapter.
        self.strict_parity = strict_parity
        self.repo_dir = self.external_root / "aideml"
        self.log_root = Path(log_root or os.environ.get(
            "ARC_AIDE_LOG_ROOT", DEFAULT_PLAYPEN_LOG_ROOT))
        self.workspace_root = Path(workspace_root or os.environ.get(
            "ARC_AIDE_WORKSPACE_ROOT", DEFAULT_PLAYPEN_WORKSPACE_ROOT))

    # ---------------------------------------------------------------- availability
    def is_available(self) -> tuple[bool, str]:
        if not (self.repo_dir / "aide" / "__init__.py").is_file():
            return (False, f"aideml not cloned at {self.repo_dir}")
        py_exe = os.environ.get("ARC_AIDE_PYTHON", DEFAULT_AIDE_PYTHON)
        if not Path(py_exe).is_file():
            return (False, f"AIDE conda env python not found at {py_exe}")
        if not os.environ.get("OPENAI_API_KEY"):
            return (False, "OPENAI_API_KEY not set")
        if not os.environ.get("OPENAI_BASE_URL"):
            return (False, "OPENAI_BASE_URL not set")
        return (True, "ok")

    # ------------------------------------------------------------------ goal/eval
    def _build_goal_and_eval(self, topic: dict) -> tuple[str, str]:
        """Render the strict-parity ``goal`` and ``eval`` strings.

        The goal mirrors :meth:`AgentLabAdapter._build_yaml_config` strict-
        parity ``research-topic``: a single string carrying exactly the
        fields rc_full's stage-09 ``exp_plan.yaml`` carries — and nothing
        more.
        """
        ed = topic.get("experiment_design") or {}
        question = ed.get("research_question") or topic.get("topic", "")
        synthesis = (topic.get("synthesis") or "").strip()
        hypotheses = topic.get("hypotheses") or []
        conditions = ed.get("conditions") or []
        metrics = ed.get("metrics") or []
        datasets = ed.get("datasets") or []

        bench_note = (
            "This is an ARC-Bench topic. Implement a competent experiment "
            "addressing the research question. You may tighten or extend "
            "the listed conditions/metrics if your design is coherent."
        )

        cond_block = "\n  - ".join(
            f"{c.get('name')}: {c.get('description', '').strip()}"
            for c in conditions
        ) if conditions else "(none specified)"
        metric_block = "\n  - ".join(
            f"{m.get('name')} ({m.get('direction', '')}): "
            f"{m.get('description', '').strip()}"
            for m in metrics
        ) if metrics else "(none specified)"
        dataset_block = "\n  - ".join(
            f"{d.get('name')} ({d.get('source', '')})" for d in datasets
        ) if datasets else "(none specified)"
        hyp_block = "\n  - ".join(
            f"{h.get('id', f'H{i+1}')}: {h.get('statement', '')}"
            for i, h in enumerate(hypotheses)
        ) if hypotheses else "(none specified)"

        goal = (
            f"topic_id: {topic.get('id', '?')}\n"
            f"research_question: {question}\n"
            f"\nBackground:\n{synthesis}\n"
            f"\nConditions:\n  - {cond_block}\n"
            f"\nMetrics:\n  - {metric_block}\n"
            f"\nDatasets:\n  - {dataset_block}\n"
            f"\nHypotheses:\n  - {hyp_block}\n"
            f"\nbench_note: {bench_note}\n"
        )

        # ``eval`` is AIDE-specific: a one-line description of the metric
        # AIDE selects best-of-N solutions on. Pick the FIRST listed metric
        # with its declared direction (parity with how AgentLab's
        # papersolver picks the headline metric from the topic).
        if metrics:
            primary = metrics[0]
            direction = (primary.get("direction") or "").lower()
            verb = "MAXIMIZE" if direction == "maximize" else (
                "MINIMIZE" if direction == "minimize" else "OPTIMIZE"
            )
            eval_str = (
                f"{primary.get('name')} — "
                f"{primary.get('description', '').strip()} ({verb}) "
                f"averaged across all listed datasets and seeds."
            )
        else:
            eval_str = "Use a sensible held-out metric matching the research question."

        return goal, eval_str

    # ----------------------------------------------------------- stub data_dir
    def _materialize_stub_data_dir(self, topic: dict, target: Path) -> None:
        """Create a minimal ``data_dir`` AIDE can copy.

        AIDE requires ``data_dir`` to exist and be readable. ARC-Bench
        topics either use sklearn-bundled datasets or generate synthetic
        data; we MUST NOT pre-load those, because doing so would give AIDE
        information rc_full does not get. The stub contains only a
        README.md noting "no external dataset; refer to goal for data
        generation instructions" so the data_preview AIDE shows the agent
        is informationally neutral.
        """
        target.mkdir(parents=True, exist_ok=True)
        (target / "README.md").write_text(
            "ARC-Bench task — no external dataset is provided.\n"
            "All datasets are either bundled with sklearn (see Datasets in "
            "the task goal) or are to be generated synthetically by the "
            "experiment code. Refer to the task goal for the full topic "
            "manifest.\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------------------ run
    def run(self, topic: dict, output_dir: Path) -> FrameworkResult:
        ok, reason = self.is_available()
        if not ok:
            return self._skipped(topic, output_dir, reason)

        output_dir.mkdir(parents=True, exist_ok=True)
        goal, eval_str = self._build_goal_and_eval(topic)
        goal_file = output_dir / "aide_goal.txt"
        eval_file = output_dir / "aide_eval.txt"
        goal_file.write_text(goal, encoding="utf-8")
        eval_file.write_text(eval_str, encoding="utf-8")

        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_tag = f"{topic['id']}-{ts}"
        exp_name = f"arc-{run_tag}"

        # Per-run absolute paths under playpen2 so /home doesn't fill up.
        log_root = self.log_root / run_tag
        workspace_root = self.workspace_root / run_tag
        log_root.mkdir(parents=True, exist_ok=True)
        workspace_root.mkdir(parents=True, exist_ok=True)

        data_dir = output_dir / "data"
        self._materialize_stub_data_dir(topic, data_dir)

        py_exe = os.environ.get("ARC_AIDE_PYTHON", DEFAULT_AIDE_PYTHON)
        runner_script = Path(__file__).parent / "_aide_runner.py"
        cmd = [
            py_exe, "-u", str(runner_script),
            "--data-dir", str(data_dir),
            "--goal-file", str(goal_file),
            "--eval-file", str(eval_file),
            "--log-dir", str(log_root),
            "--workspace-dir", str(workspace_root),
            "--exp-name", exp_name,
            "--steps", str(self.agent_steps),
            "--num-drafts", str(self.num_drafts),
            "--code-model", self.code_model,
            "--feedback-model", self.feedback_model,
            "--report-model", self.report_model,
        ]

        env = {**os.environ, "PYTHONUNBUFFERED": "1"}

        if self.dry_run:
            (output_dir / "command.txt").write_text(
                f"OPENAI_BASE_URL={env.get('OPENAI_BASE_URL', '')}\n"
                f"log_root={log_root}\n"
                f"workspace_root={workspace_root}\n"
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
                extra={
                    "dry_run": True,
                    "log_root": str(log_root),
                    "workspace_root": str(workspace_root),
                },
            )

        log_path = output_dir / "aide_stdout.log"
        t0 = time.monotonic()
        try:
            with log_path.open("w", encoding="utf-8") as logfh:
                completed = subprocess.run(
                    cmd, env=env,
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
            (output_dir / "aide_error.txt").write_text(
                repr(exc), encoding="utf-8"
            )

        # AIDE creates <log_root>/<idx>-<exp_name>/ inside its top-level
        # log dir. Locate the most recent one.
        exp_log_dir = self._latest_exp_dir(log_root)
        exp_workspace_dir = self._latest_exp_dir(workspace_root)

        artifacts = _read_aide_artifacts(exp_log_dir, exp_workspace_dir, topic)
        self._write_standard_artifacts(
            output_dir, artifacts,
            framework_meta={
                "native_log_dir": str(exp_log_dir) if exp_log_dir else None,
                "native_workspace_dir": (
                    str(exp_workspace_dir) if exp_workspace_dir else None
                ),
                "code_model": self.code_model,
                "feedback_model": self.feedback_model,
                "report_model": self.report_model,
                "agent_steps": self.agent_steps,
                "num_drafts": self.num_drafts,
            },
        )

        # Convenience copies at the run-dir top level for quick inspection.
        if exp_log_dir is not None:
            for name in ("report.md", "best_solution.py", "tree_plot.html",
                         "aide_run_meta.json"):
                src = exp_log_dir / name
                if src.is_file():
                    shutil.copy(src, output_dir / src.name)

        return FrameworkResult(
            framework_id=self.framework_id,
            topic_id=topic["id"],
            status=status,
            returncode=rc,
            elapsed_sec=round(elapsed, 1),
            output_dir=str(output_dir),
            artifacts=artifacts,
            extra={
                "native_log_dir": str(exp_log_dir) if exp_log_dir else None,
                "native_workspace_dir": (
                    str(exp_workspace_dir) if exp_workspace_dir else None
                ),
                "stdout_log": str(log_path),
                "goal_file": str(goal_file),
                "eval_file": str(eval_file),
            },
        )

    @staticmethod
    def _latest_exp_dir(root: Path) -> Path | None:
        if not root.is_dir():
            return None
        candidates = [p for p in root.iterdir() if p.is_dir()]
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]


def _read_aide_artifacts(
    log_dir: Path | None,
    workspace_dir: Path | None,
    topic: dict,
) -> StandardArtifacts:
    out = StandardArtifacts()
    if log_dir is None or not log_dir.is_dir():
        return out

    # Paper text — AIDE's journal2report markdown report
    report = log_dir / "report.md"
    if report.is_file():
        out.paper_text = report.read_text(encoding="utf-8", errors="ignore")

    # Numerical results — pull AIDE's run_meta + best metric AND any JSON
    # the agent wrote into workspace/working/. AIDE doesn't enforce a
    # canonical metrics file, so we surface what's there and let the judge
    # cross-check against the report.
    meta_path = log_dir / "aide_run_meta.json"
    meta_blob: dict = {}
    if meta_path.is_file():
        try:
            meta_blob = json.loads(meta_path.read_text())
        except Exception:  # noqa: BLE001
            meta_blob = {}

    workspace_metrics: dict = {}
    if workspace_dir is not None and workspace_dir.is_dir():
        # AIDE runs code in workspace_dir/working/ and may emit JSON there
        for sub in (workspace_dir / "working", workspace_dir):
            if not sub.is_dir():
                continue
            for jf in sorted(sub.glob("*.json"),
                             key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    workspace_metrics[jf.name] = json.loads(jf.read_text())
                except Exception:  # noqa: BLE001
                    continue
            if workspace_metrics:
                break

    if meta_blob or workspace_metrics:
        out.experiment_summary = {
            "topic_id": topic.get("id"),
            "aide_run_meta": meta_blob,
            "workspace_json": workspace_metrics,
        }

    out.stages_done = 23 if out.paper_text else 13
    return out
