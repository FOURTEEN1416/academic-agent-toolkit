"""AI Scientist v2 adapter (SakanaAI/AI-Scientist-v2).

Two-phase:
  (a) `perform_ideation_temp_free.py` — generates JSON ideas from a Markdown
      topic file. We write the topic markdown on the fly.
  (b) `launch_scientist_bfts.py --load_ideas <json>` — runs the agentic tree
      search, experiments, and writeup.

Outputs land in `experiments/<timestamp>/` under the v2 repo. This adapter
copies the final PDF + logs into our ``output_dir`` and maps to
``StandardArtifacts``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .base import FrameworkAdapter, FrameworkResult, StandardArtifacts


class AIScientistV2Adapter(FrameworkAdapter):
    framework_id = "ais_v2"

    def __init__(
        self,
        *,
        model_writeup: str = "o1-preview-2024-09-12",
        model_citation: str = "gpt-4o-2024-11-20",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model_writeup = model_writeup
        self.model_citation = model_citation
        self.repo_dir = self.external_root / "AI-Scientist-v2"

    def is_available(self) -> tuple[bool, str]:
        entry = self.repo_dir / "launch_scientist_bfts.py"
        if not entry.is_file():
            return (False, f"AI-Scientist-v2 not cloned at {self.repo_dir} "
                           f"(run scripts/setup_frameworks.py)")
        return (True, "ok")

    def run(self, topic: dict, output_dir: Path) -> FrameworkResult:
        ok, reason = self.is_available()
        if not ok:
            return self._skipped(topic, output_dir, reason)

        output_dir.mkdir(parents=True, exist_ok=True)
        topic_md = self._write_topic_markdown(topic, output_dir)

        ideation_cmd = [
            sys.executable, "perform_ideation_temp_free.py",
            "--topic-file", str(topic_md),
        ]
        launch_cmd_tmpl = [
            sys.executable, "launch_scientist_bfts.py",
            "--load_ideas", "IDEAS_JSON",
            "--model_writeup", self.model_writeup,
            "--model_citation", self.model_citation,
        ]

        if self.dry_run:
            (output_dir / "command.txt").write_text(
                " ".join(ideation_cmd) + "\n"
                + " ".join(launch_cmd_tmpl) + "\n"
            )
            return FrameworkResult(
                framework_id=self.framework_id,
                topic_id=topic["id"],
                status="skipped",
                returncode=None,
                elapsed_sec=0.0,
                output_dir=str(output_dir),
                extra={"dry_run": True, "topic_md": str(topic_md)},
            )

        before = _snapshot(self.repo_dir / "experiments")

        t0 = time.monotonic()
        # Phase (a): ideation
        try:
            completed = subprocess.run(
                ideation_cmd, cwd=str(self.repo_dir),
                env={**os.environ},
                timeout=max(600, self.budget_sec // 4),
            )
        except subprocess.TimeoutExpired:
            return self._failed(topic, output_dir, "ideation_timeout", t0)
        if completed.returncode != 0:
            return self._failed(topic, output_dir, "ideation_failed", t0)

        ideas_json = _find_latest_ideas(self.repo_dir)
        if ideas_json is None:
            return self._failed(topic, output_dir, "ideas_json_missing", t0)

        # Phase (b): launch
        launch_cmd = [c if c != "IDEAS_JSON" else str(ideas_json)
                      for c in launch_cmd_tmpl]
        remaining = max(60, self.budget_sec - int(time.monotonic() - t0))
        try:
            completed = subprocess.run(
                launch_cmd, cwd=str(self.repo_dir),
                env={**os.environ},
                timeout=remaining,
            )
            elapsed = time.monotonic() - t0
            status = "completed" if completed.returncode == 0 else "failed"
            rc: int | None = completed.returncode
        except subprocess.TimeoutExpired:
            elapsed = float(self.budget_sec)
            status = "timeout"
            rc = None

        after = _snapshot(self.repo_dir / "experiments")
        new_exps = sorted(after - before)
        native_run_dir = (
            self.repo_dir / "experiments" / new_exps[-1] if new_exps else None
        )

        artifacts = _read_ais_v2_artifacts(native_run_dir) if native_run_dir else StandardArtifacts()
        self._write_standard_artifacts(
            output_dir, artifacts,
            framework_meta={"native_run": str(native_run_dir)},
        )

        # Copy the PDF for archival
        if native_run_dir:
            for pdf in native_run_dir.glob("*.pdf"):
                shutil.copy(pdf, output_dir / pdf.name)

        return FrameworkResult(
            framework_id=self.framework_id,
            topic_id=topic["id"],
            status=status,
            returncode=rc,
            elapsed_sec=round(elapsed, 1),
            output_dir=str(output_dir),
            artifacts=artifacts,
            extra={"native_run": str(native_run_dir)},
        )

    # ------------------------------------------------------------------

    def _write_topic_markdown(self, topic: dict, output_dir: Path) -> Path:
        """AI Scientist v2 expects a Markdown file with Title/Keywords/Abstract."""
        lines = [
            f"# Title",
            topic["topic"],
            "",
            f"# Keywords",
            ", ".join(topic.get("domains", ["machine-learning"])),
            "",
            f"# Abstract",
            (
                f"This research topic asks: {topic['topic']}. "
                f"The expected evaluation metric is {topic.get('metric_key', 'primary_metric')} "
                f"({topic.get('metric_direction', 'minimize')}). "
                f"The goal is a CPU-executable ML study comparable across frameworks."
            ),
        ]
        path = output_dir / "topic.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _failed(self, topic: dict, output_dir: Path, reason: str,
                t0: float) -> FrameworkResult:
        return FrameworkResult(
            framework_id=self.framework_id,
            topic_id=topic["id"],
            status="failed",
            returncode=None,
            elapsed_sec=round(time.monotonic() - t0, 1),
            output_dir=str(output_dir),
            error=reason,
        )


def _snapshot(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    return {p.name for p in path.iterdir() if p.is_dir()}


def _find_latest_ideas(repo_dir: Path) -> Path | None:
    ideas_dir = repo_dir / "ai_scientist" / "ideas"
    if not ideas_dir.is_dir():
        return None
    jsons = sorted(ideas_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return jsons[-1] if jsons else None


def _read_ais_v2_artifacts(run_dir: Path) -> StandardArtifacts:
    out = StandardArtifacts()
    if not run_dir or not run_dir.is_dir():
        return out

    # Paper text (tex → md fallback)
    for name in ("final_paper.md", "paper.md", "writeup.md"):
        p = run_dir / name
        if p.is_file():
            out.paper_text = p.read_text(encoding="utf-8", errors="ignore")
            break
    if out.paper_text is None:
        for tex in run_dir.glob("**/*.tex"):
            out.paper_text = tex.read_text(encoding="utf-8", errors="ignore")
            break

    # Tree search log → approximate stages_done by best-node depth
    summary = run_dir / "experiment_summary.json"
    if summary.is_file():
        try:
            data = json.loads(summary.read_text())
            out.experiment_summary = data
        except json.JSONDecodeError:
            pass

    # v2 reviewer scores
    review = run_dir / "review.json"
    if review.is_file():
        try:
            out.review_overall = json.loads(review.read_text()).get("overall_score")
        except json.JSONDecodeError:
            pass

    out.stages_done = 23 if out.paper_text else 12
    return out
