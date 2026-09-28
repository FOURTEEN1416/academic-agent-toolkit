"""Base class for framework adapters.

Every competitor must map its outputs into the layout produced by
AutoResearchClaw so that ``evaluate.py`` (which already knows that layout)
can score them without special-casing each framework.

Minimum expected layout written by ``FrameworkAdapter.run``::

    <output_dir>/
      pipeline_summary.json          # stages_done, template_ratio, citations
      stage-17/paper_draft.md        # final paper text (or closest analog)
      stage-14/experiment_summary.json  # run metrics if available
      stage-18/peer_review.json      # overall_score if available
      adapter_meta.json              # framework, version, native_output_path

Fields not produced by the framework are omitted; the composite scorer treats
missing fields as 0 (conservative against the framework, fair to all).
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StandardArtifacts:
    """Subset of ResearchClaw artifacts our scorer reads.

    Adapters populate whichever fields their framework produces; the scorer
    gracefully handles missing values.
    """
    paper_text: str | None = None
    paper_section_count: int | None = None
    stages_done: int | None = None
    template_ratio: float | None = None
    citation_verify_score: float | None = None
    total_citations: int | None = None
    verified_citations: int | None = None
    experiment_summary: dict[str, Any] | None = None
    review_overall: float | None = None


@dataclass
class FrameworkResult:
    framework_id: str
    topic_id: str
    status: str  # "completed" | "failed" | "timeout" | "skipped"
    returncode: int | None
    elapsed_sec: float
    output_dir: str
    artifacts: StandardArtifacts = field(default_factory=StandardArtifacts)
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class FrameworkAdapter(ABC):
    framework_id: str = "UNKNOWN"

    def __init__(self, *, external_root: Path, budget_sec: int = 5400,
                 dry_run: bool = False):
        self.external_root = Path(external_root)
        self.budget_sec = budget_sec
        self.dry_run = dry_run

    @abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """Return (ok, reason). Called before ``run`` — used by the runner to
        skip frameworks that aren't set up rather than fail mid-batch."""

    @abstractmethod
    def run(self, topic: dict, output_dir: Path) -> FrameworkResult:
        """Execute the framework on ``topic`` and materialize the standard
        artifact layout inside ``output_dir``.

        ``topic`` is one entry from ``topics.yaml`` (``id``, ``topic``,
        ``domains``, ``metric_key``, ``metric_direction``).
        """

    # ---------- helpers used by every adapter ---------------------------------

    def _write_standard_artifacts(
        self,
        output_dir: Path,
        artifacts: StandardArtifacts,
        *,
        framework_meta: dict[str, Any] | None = None,
    ) -> None:
        """Serialize ``artifacts`` into the ResearchClaw layout."""
        output_dir.mkdir(parents=True, exist_ok=True)

        summary = {
            "stages_executed": artifacts.stages_done or 0,
            "stages_done": artifacts.stages_done or 0,
            "stages_failed": 0,
            "degraded": (artifacts.stages_done or 0) < 23,
            "content_metrics": {
                "template_ratio": artifacts.template_ratio,
                "citation_verify_score": artifacts.citation_verify_score,
                "total_citations": artifacts.total_citations,
                "verified_citations": artifacts.verified_citations,
            },
        }
        (output_dir / "pipeline_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

        if artifacts.paper_text is not None:
            stage17 = output_dir / "stage-17"
            stage17.mkdir(exist_ok=True)
            (stage17 / "paper_draft.md").write_text(
                artifacts.paper_text, encoding="utf-8"
            )

        if artifacts.experiment_summary is not None:
            stage14 = output_dir / "stage-14"
            stage14.mkdir(exist_ok=True)
            (stage14 / "experiment_summary.json").write_text(
                json.dumps(artifacts.experiment_summary, indent=2),
                encoding="utf-8",
            )

        if artifacts.review_overall is not None:
            stage18 = output_dir / "stage-18"
            stage18.mkdir(exist_ok=True)
            (stage18 / "peer_review.json").write_text(
                json.dumps({"overall_score": artifacts.review_overall}, indent=2),
                encoding="utf-8",
            )

        meta = {
            "framework_id": self.framework_id,
            "written_at": time.time(),
            **(framework_meta or {}),
        }
        (output_dir / "adapter_meta.json").write_text(
            json.dumps(meta, indent=2, default=str), encoding="utf-8"
        )

    def _skipped(self, topic: dict, output_dir: Path, reason: str) -> FrameworkResult:
        return FrameworkResult(
            framework_id=self.framework_id,
            topic_id=topic["id"],
            status="skipped",
            returncode=None,
            elapsed_sec=0.0,
            output_dir=str(output_dir),
            error=reason,
        )

    def to_json(self, result: FrameworkResult) -> str:
        d = asdict(result)
        return json.dumps(d, indent=2, default=str)
