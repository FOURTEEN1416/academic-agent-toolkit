"""AutoResearchClaw adapter — runs the main pipeline in full-auto or co-pilot.

Output is native ResearchClaw, which means no translation is needed: we just
point the evaluator at the run directory. ``FrameworkResult.artifacts`` is
populated by re-reading the canonical pipeline_summary.json so all adapters
follow the same contract.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from .base import FrameworkAdapter, FrameworkResult, StandardArtifacts

ROOT = Path(__file__).resolve().parent.parent.parent.parent


class ResearchClawAdapter(FrameworkAdapter):
    """Runs ``python -m researchclaw run`` on the topic.

    Two variants are exposed:
        framework_id = "rc_full"     → --auto-approve, no HITL
        framework_id = "rc_copilot"  → --mode co-pilot + scripted interventions
    """

    def __init__(
        self,
        *,
        mode: str,  # "full-auto" | "co-pilot"
        base_config: Path,
        interventions_dir: Path | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.mode = mode
        self.framework_id = "rc_copilot" if mode == "co-pilot" else "rc_full"
        self.base_config = Path(base_config)
        self.interventions_dir = (
            Path(interventions_dir) if interventions_dir else None
        )

    def is_available(self) -> tuple[bool, str]:
        cli = ROOT / "researchclaw" / "cli.py"
        if not cli.is_file():
            return (False, f"researchclaw CLI not found at {cli}")
        if self.mode == "co-pilot" and self.interventions_dir is None:
            return (False, "co-pilot mode requires --interventions-dir")
        return (True, "ok")

    def run(self, topic: dict, output_dir: Path) -> FrameworkResult:
        ok, reason = self.is_available()
        if not ok:
            return self._skipped(topic, output_dir, reason)

        output_dir.mkdir(parents=True, exist_ok=True)
        config_path = self._materialize_config(topic, output_dir)
        artifacts_dir = output_dir / "artifacts"

        cmd: list[str] = [
            sys.executable, "-m", "researchclaw", "run",
            "--config", str(config_path),
            "--output", str(artifacts_dir),
        ]
        if self.mode == "full-auto":
            cmd.append("--auto-approve")
        else:
            cmd.extend(["--mode", "co-pilot"])
            iv_file = self._locate_interventions(topic["id"])
            if iv_file is not None:
                cmd.extend(["--interventions", str(iv_file)])

        if self.dry_run:
            (output_dir / "command.txt").write_text(" ".join(cmd) + "\n")
            return FrameworkResult(
                framework_id=self.framework_id,
                topic_id=topic["id"],
                status="skipped",
                returncode=None,
                elapsed_sec=0.0,
                output_dir=str(artifacts_dir),
                extra={"dry_run": True, "cmd": cmd},
            )

        t0 = time.monotonic()
        try:
            completed = subprocess.run(
                cmd,
                cwd=str(ROOT),
                env={**os.environ, "PYTHONPATH": str(ROOT)},
                timeout=self.budget_sec,
            )
            elapsed = time.monotonic() - t0
            status = "completed" if completed.returncode == 0 else "failed"
            rc: int | None = completed.returncode
        except subprocess.TimeoutExpired:
            elapsed = float(self.budget_sec)
            status = "timeout"
            rc = None

        artifacts = _read_native_artifacts(artifacts_dir)
        result = FrameworkResult(
            framework_id=self.framework_id,
            topic_id=topic["id"],
            status=status,
            returncode=rc,
            elapsed_sec=round(elapsed, 1),
            output_dir=str(artifacts_dir),
            artifacts=artifacts,
        )
        (output_dir / "framework_result.json").write_text(
            self.to_json(result), encoding="utf-8"
        )
        return result

    # ------------------------------------------------------------------

    def _materialize_config(self, topic: dict, output_dir: Path) -> Path:
        cfg = yaml.safe_load(self.base_config.read_text())
        cfg["project"]["name"] = f"fc-{self.framework_id}-{topic['id']}"
        cfg["project"]["mode"] = (
            "full-auto" if self.mode == "full-auto" else "semi-auto"
        )
        cfg["research"]["topic"] = topic["topic"]
        cfg["research"]["domains"] = topic.get("domains", ["machine-learning"])
        cfg["experiment"]["metric_key"] = topic.get("metric_key", "primary_metric")
        cfg["experiment"]["metric_direction"] = topic.get("metric_direction", "minimize")

        if self.mode == "co-pilot":
            cfg["hitl"] = {
                "enabled": True,
                "mode": "co-pilot",
                "timeouts": {
                    "default_human_timeout_sec": 86400,
                    "auto_proceed_on_timeout": False,
                },
            }

        path = output_dir / "config.yaml"
        path.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True))
        return path

    def _locate_interventions(self, topic_id: str) -> Path | None:
        if self.interventions_dir is None:
            return None
        candidate = self.interventions_dir / f"interventions_{topic_id}.json"
        return candidate if candidate.is_file() else None


def _read_native_artifacts(artifacts_dir: Path) -> StandardArtifacts:
    """Re-read ResearchClaw outputs into the shared StandardArtifacts shape."""
    out = StandardArtifacts()
    summary_path = artifacts_dir / "pipeline_summary.json"
    if summary_path.is_file():
        summary: dict[str, Any] = json.loads(summary_path.read_text())
        out.stages_done = summary.get("stages_done")
        cm = summary.get("content_metrics") or {}
        out.template_ratio = cm.get("template_ratio")
        out.citation_verify_score = cm.get("citation_verify_score")
        out.total_citations = cm.get("total_citations")
        out.verified_citations = cm.get("verified_citations")

    for path in [
        artifacts_dir / "stage-19" / "paper_revised.md",
        artifacts_dir / "stage-17" / "paper_draft.md",
    ]:
        if path.is_file():
            out.paper_text = path.read_text(encoding="utf-8", errors="ignore")
            break

    exp_path = artifacts_dir / "stage-14" / "experiment_summary.json"
    if exp_path.is_file():
        try:
            out.experiment_summary = json.loads(exp_path.read_text())
        except json.JSONDecodeError:
            out.experiment_summary = None

    for name in ("peer_review.json", "review.json"):
        rp = artifacts_dir / "stage-18" / name
        if rp.is_file():
            try:
                review = json.loads(rp.read_text())
                out.review_overall = review.get("overall_score")
            except json.JSONDecodeError:
                pass
            break
    return out
