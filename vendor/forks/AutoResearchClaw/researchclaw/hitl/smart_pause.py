"""Smart pause: confidence-driven dynamic intervention routing.

Instead of fixed gate stages, SmartPause dynamically decides whether
a stage needs human review based on:
- Output quality score (from PRM or heuristics)
- Confidence of the LLM in its output
- Historical intervention patterns
- Stage criticality
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceSignal:
    """Aggregated confidence assessment for a stage output."""

    stage: int
    stage_name: str
    quality_score: float = 1.0       # 0-1, from PRM or heuristics
    confidence_score: float = 1.0    # 0-1, LLM self-assessed confidence
    novelty_risk: float = 0.0        # 0-1, how novel/risky is the output
    historical_rejection_rate: float = 0.0  # 0-1, past rejection rate
    criticality: float = 0.5         # 0-1, importance of the stage

    @property
    def overall_confidence(self) -> float:
        """Weighted confidence score."""
        weights = {
            "quality": 0.30,
            "confidence": 0.25,
            "novelty_risk": 0.15,
            "history": 0.10,
            "criticality": 0.20,
        }
        score = (
            weights["quality"] * self.quality_score
            + weights["confidence"] * self.confidence_score
            + weights["novelty_risk"] * (1.0 - self.novelty_risk)
            + weights["history"] * (1.0 - self.historical_rejection_rate)
            + weights["criticality"] * (1.0 - self.criticality)
        )
        return max(0.0, min(1.0, score))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "stage_name": self.stage_name,
            "quality_score": self.quality_score,
            "confidence_score": self.confidence_score,
            "novelty_risk": self.novelty_risk,
            "historical_rejection_rate": self.historical_rejection_rate,
            "criticality": self.criticality,
            "overall_confidence": self.overall_confidence,
        }


# Stage criticality weights (higher = more critical)
_STAGE_CRITICALITY: dict[int, float] = {
    1: 0.6,   # TOPIC_INIT — direction-setting
    2: 0.5,   # PROBLEM_DECOMPOSE
    3: 0.3,   # SEARCH_STRATEGY
    4: 0.2,   # LITERATURE_COLLECT
    5: 0.5,   # LITERATURE_SCREEN (gate)
    6: 0.2,   # KNOWLEDGE_EXTRACT
    7: 0.7,   # SYNTHESIS — critical for idea quality
    8: 0.9,   # HYPOTHESIS_GEN — the idea itself
    9: 0.8,   # EXPERIMENT_DESIGN — experiment quality
    10: 0.6,  # CODE_GENERATION
    11: 0.2,  # RESOURCE_PLANNING
    12: 0.5,  # EXPERIMENT_RUN
    13: 0.4,  # ITERATIVE_REFINE
    14: 0.5,  # RESULT_ANALYSIS
    15: 0.7,  # RESEARCH_DECISION — pivot or proceed
    16: 0.5,  # PAPER_OUTLINE
    17: 0.6,  # PAPER_DRAFT
    18: 0.4,  # PEER_REVIEW
    19: 0.5,  # PAPER_REVISION
    20: 0.7,  # QUALITY_GATE
    21: 0.1,  # KNOWLEDGE_ARCHIVE
    22: 0.3,  # EXPORT_PUBLISH
    23: 0.4,  # CITATION_VERIFY
}


class SmartPause:
    """Dynamic intervention routing based on confidence signals.

    Decides at runtime whether a stage output should be reviewed
    by the human, based on multiple confidence signals.
    """

    def __init__(
        self,
        threshold: float = 0.7,
        run_dir: Path | None = None,
    ) -> None:
        self.threshold = threshold
        self.run_dir = run_dir
        self._history: list[ConfidenceSignal] = []

    def should_pause(
        self,
        stage: int,
        stage_name: str,
        *,
        quality_score: float | None = None,
        confidence_score: float | None = None,
    ) -> tuple[bool, ConfidenceSignal]:
        """Determine if a stage needs human review.

        Args:
            stage: Stage number.
            stage_name: Stage name.
            quality_score: PRM or heuristic quality score (0-1).
            confidence_score: LLM self-assessed confidence (0-1).

        Returns:
            Tuple of (should_pause, signal).
        """
        signal = ConfidenceSignal(
            stage=stage,
            stage_name=stage_name,
            quality_score=quality_score if quality_score is not None else 1.0,
            confidence_score=(
                confidence_score if confidence_score is not None else 1.0
            ),
            criticality=_STAGE_CRITICALITY.get(stage, 0.5),
            historical_rejection_rate=self._get_rejection_rate(stage),
        )

        self._history.append(signal)
        should = signal.overall_confidence < self.threshold

        if should:
            logger.info(
                "SmartPause: stage %d (%s) confidence %.2f < %.2f — pausing",
                stage,
                stage_name,
                signal.overall_confidence,
                self.threshold,
            )

        return should, signal

    def _get_rejection_rate(self, stage: int) -> float:
        """Get historical rejection rate for a stage from intervention log."""
        if self.run_dir is None:
            return 0.0

        try:
            log_path = self.run_dir / "hitl" / "interventions.jsonl"
            if not log_path.exists():
                return 0.0

            total = 0
            rejected = 0
            for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("stage") == stage:
                    total += 1
                    if entry.get("type") == "reject":
                        rejected += 1

            if total == 0:
                return 0.0
            return rejected / total

        except (OSError, json.JSONDecodeError):
            return 0.0

    def get_report(self) -> list[dict[str, Any]]:
        """Return confidence signals for all assessed stages."""
        return [s.to_dict() for s in self._history]
