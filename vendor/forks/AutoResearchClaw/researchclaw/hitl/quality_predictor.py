"""HITL quality predictor: estimate final paper quality from current state.

Uses heuristic signals from pipeline artifacts to predict whether
the current trajectory will produce a high-quality paper.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QualityPrediction:
    """Predicted quality assessment at a given point in the pipeline."""

    current_stage: int
    predicted_quality: float  # 0-10 scale
    confidence: float         # 0-1, how confident in the prediction
    risk_factors: list[str]
    suggestions: list[str]
    component_scores: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_stage": self.current_stage,
            "predicted_quality": round(self.predicted_quality, 2),
            "confidence": round(self.confidence, 2),
            "risk_factors": self.risk_factors,
            "suggestions": self.suggestions,
            "component_scores": {
                k: round(v, 2) for k, v in self.component_scores.items()
            },
        }


class QualityPredictor:
    """Predict final paper quality from pipeline artifacts.

    Checks multiple signals:
    - Literature coverage (number and diversity of papers)
    - Hypothesis specificity
    - Experiment completeness (baselines, conditions, metrics)
    - Result strength (improvement over baselines)
    - Draft quality (length, structure, citations)
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def predict(self, current_stage: int = 23) -> QualityPrediction:
        """Generate quality prediction based on available artifacts.

        Args:
            current_stage: Up to which stage to analyze.

        Returns:
            QualityPrediction with scores and risk factors.
        """
        components: dict[str, float] = {}
        risks: list[str] = []
        suggestions: list[str] = []

        # Literature quality
        if current_stage >= 5:
            score, risk = self._assess_literature()
            components["literature"] = score
            risks.extend(risk)

        # Hypothesis quality
        if current_stage >= 8:
            score, risk = self._assess_hypothesis()
            components["hypothesis"] = score
            risks.extend(risk)

        # Experiment design quality
        if current_stage >= 9:
            score, risk = self._assess_experiment_design()
            components["experiment_design"] = score
            risks.extend(risk)

        # Experiment results quality
        if current_stage >= 14:
            score, risk = self._assess_results()
            components["results"] = score
            risks.extend(risk)

        # Paper draft quality
        if current_stage >= 17:
            score, risk = self._assess_draft()
            components["draft"] = score
            risks.extend(risk)

        # Citation quality
        if current_stage >= 23:
            score, risk = self._assess_citations()
            components["citations"] = score
            risks.extend(risk)

        # Compute overall
        if components:
            predicted = sum(components.values()) / len(components)
        else:
            predicted = 5.0  # Unknown

        confidence = min(1.0, len(components) / 6.0)

        # Generate suggestions based on risks
        if "Few literature references" in risks:
            suggestions.append("Add more references in the related work section")
        if "No baselines in experiment" in risks:
            suggestions.append("Add baseline comparisons before writing the paper")
        if "Paper draft is too short" in risks:
            suggestions.append("Expand method and experiment sections")

        return QualityPrediction(
            current_stage=current_stage,
            predicted_quality=predicted,
            confidence=confidence,
            risk_factors=risks,
            suggestions=suggestions,
            component_scores=components,
        )

    def _assess_literature(self) -> tuple[float, list[str]]:
        risks: list[str] = []
        score = 5.0

        shortlist = self.run_dir / "stage-05" / "shortlist.jsonl"
        if shortlist.exists():
            try:
                lines = shortlist.read_text(encoding="utf-8").strip().split("\n")
                count = sum(1 for l in lines if l.strip())
                if count >= 20:
                    score = 8.0
                elif count >= 10:
                    score = 6.0
                elif count >= 5:
                    score = 4.0
                else:
                    score = 2.0
                    risks.append("Few literature references")
            except OSError:
                pass
        else:
            score = 3.0
            risks.append("Literature screening not completed")

        return score, risks

    def _assess_hypothesis(self) -> tuple[float, list[str]]:
        risks: list[str] = []
        score = 5.0

        hyp_path = self.run_dir / "stage-08" / "hypotheses.md"
        if hyp_path.exists():
            try:
                text = hyp_path.read_text(encoding="utf-8")
                # Check for specificity markers
                if len(text) > 500:
                    score = 7.0
                elif len(text) > 200:
                    score = 5.0
                else:
                    score = 3.0
                    risks.append("Hypothesis description is thin")

                # Check for falsifiability markers
                falsifiable_markers = [
                    "improve", "outperform", "reduce", "increase",
                    "hypothesis", "expect", "predict",
                ]
                marker_count = sum(
                    1 for m in falsifiable_markers if m in text.lower()
                )
                if marker_count < 2:
                    risks.append("Hypothesis may lack falsifiability")
            except OSError:
                pass
        else:
            score = 0.0
            risks.append("No hypothesis generated")

        return score, risks

    def _assess_experiment_design(self) -> tuple[float, list[str]]:
        risks: list[str] = []
        score = 5.0

        for exp_path in [
            self.run_dir / "stage-09" / "exp_plan.yaml",
            self.run_dir / "stage-09" / "experiment_design.json",
        ]:
            if exp_path.exists():
                try:
                    text = exp_path.read_text(encoding="utf-8")
                    has_baselines = "baseline" in text.lower()
                    has_metrics = "metric" in text.lower()
                    has_ablation = "ablation" in text.lower()

                    score = 4.0
                    if has_baselines:
                        score += 2.0
                    else:
                        risks.append("No baselines in experiment")
                    if has_metrics:
                        score += 1.0
                    if has_ablation:
                        score += 1.0
                    else:
                        risks.append("No ablation study planned")
                except OSError:
                    pass
                break
        else:
            score = 0.0
            risks.append("No experiment design found")

        return score, risks

    def _assess_results(self) -> tuple[float, list[str]]:
        risks: list[str] = []
        score = 5.0

        analysis_path = self.run_dir / "stage-14" / "analysis.md"
        if analysis_path.exists():
            try:
                text = analysis_path.read_text(encoding="utf-8")
                if len(text) > 1000:
                    score = 7.0
                elif len(text) > 300:
                    score = 5.0
                else:
                    score = 3.0
                    risks.append("Thin analysis — may lack depth")
            except OSError:
                pass
        else:
            score = 0.0
            risks.append("No result analysis found")

        return score, risks

    def _assess_draft(self) -> tuple[float, list[str]]:
        risks: list[str] = []
        score = 5.0

        draft_path = self.run_dir / "stage-17" / "paper_draft.md"
        if draft_path.exists():
            try:
                text = draft_path.read_text(encoding="utf-8")
                word_count = len(text.split())

                if word_count > 6000:
                    score = 8.0
                elif word_count > 3000:
                    score = 6.0
                elif word_count > 1000:
                    score = 4.0
                else:
                    score = 2.0
                    risks.append("Paper draft is too short")

                # Check for key sections
                sections = ["introduction", "method", "experiment", "result", "conclusion"]
                found = sum(1 for s in sections if s in text.lower())
                if found < 4:
                    risks.append(f"Missing paper sections (found {found}/5)")
            except OSError:
                pass
        else:
            score = 0.0
            risks.append("No paper draft found")

        return score, risks

    def _assess_citations(self) -> tuple[float, list[str]]:
        risks: list[str] = []
        score = 5.0

        verify_path = self.run_dir / "stage-23" / "verification_report.json"
        if verify_path.exists():
            try:
                data = json.loads(verify_path.read_text(encoding="utf-8"))
                total = data.get("total_references", 0)
                verified = data.get("verified_count", 0)
                hallucinated = data.get("hallucinated_count", 0)

                if total > 0:
                    verify_rate = verified / total
                    score = verify_rate * 10
                    if hallucinated > 0:
                        risks.append(
                            f"{hallucinated} hallucinated citations detected"
                        )
                else:
                    score = 3.0
                    risks.append("No citations to verify")
            except (json.JSONDecodeError, OSError):
                pass

        return score, risks
