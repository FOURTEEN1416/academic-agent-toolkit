"""Idea Workshop: collaborative hypothesis generation (Stages 7-8).

Provides a structured framework for human-AI co-creation of research ideas:
1. Brainstorm — generate multiple candidate ideas
2. Evaluate — score each idea on novelty, feasibility, impact
3. Refine — iteratively improve the chosen idea
4. Validate — check novelty against literature
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IdeaCandidate:
    """A research idea candidate."""

    title: str
    description: str
    novelty_notes: str = ""
    feasibility_notes: str = ""
    impact_notes: str = ""
    baselines: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    score: float = 0.0
    human_approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "novelty_notes": self.novelty_notes,
            "feasibility_notes": self.feasibility_notes,
            "impact_notes": self.impact_notes,
            "baselines": self.baselines,
            "keywords": self.keywords,
            "score": self.score,
            "human_approved": self.human_approved,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IdeaCandidate:
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            novelty_notes=data.get("novelty_notes", ""),
            feasibility_notes=data.get("feasibility_notes", ""),
            impact_notes=data.get("impact_notes", ""),
            baselines=data.get("baselines", []),
            keywords=data.get("keywords", []),
            score=data.get("score", 0.0),
            human_approved=data.get("human_approved", False),
        )


@dataclass
class IdeaEvaluation:
    """Structured evaluation of an idea."""

    idea_title: str
    novelty: float = 0.0       # 0-10
    feasibility: float = 0.0   # 0-10
    impact: float = 0.0        # 0-10
    overall: float = 0.0       # 0-10
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "idea_title": self.idea_title,
            "novelty": self.novelty,
            "feasibility": self.feasibility,
            "impact": self.impact,
            "overall": self.overall,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "suggestions": self.suggestions,
        }


class IdeaWorkshop:
    """Structured collaboration for hypothesis generation.

    Designed for Stages 7 (SYNTHESIS) and 8 (HYPOTHESIS_GEN),
    this workshop guides human-AI interaction through a structured
    idea development process.
    """

    def __init__(self, run_dir: Path, llm_client: Any = None) -> None:
        self.run_dir = run_dir
        self.llm = llm_client
        self.candidates: list[IdeaCandidate] = []
        self.evaluations: list[IdeaEvaluation] = []
        self.selected_idea: IdeaCandidate | None = None

    def brainstorm(
        self,
        synthesis: str,
        human_hint: str = "",
        num_ideas: int = 3,
    ) -> list[IdeaCandidate]:
        """Generate multiple idea candidates from synthesis + human hint.

        Args:
            synthesis: Output of Stage 7 (research gap analysis).
            human_hint: Optional human guidance for idea direction.
            num_ideas: Number of candidates to generate.

        Returns:
            List of IdeaCandidate objects.
        """
        prompt = self._build_brainstorm_prompt(
            synthesis, human_hint, num_ideas
        )

        if self.llm is None:
            # No LLM — return placeholder
            self.candidates = [
                IdeaCandidate(
                    title=f"Idea {i+1} (requires LLM)",
                    description="LLM not available for brainstorming.",
                )
                for i in range(num_ideas)
            ]
            return self.candidates

        try:
            response = self.llm.chat([
                {"role": "system", "content": (
                    "You are a research advisor helping generate novel "
                    "research ideas. Return a JSON array of idea objects."
                )},
                {"role": "user", "content": prompt},
            ])
            ideas = self._parse_ideas(response, num_ideas)
            self.candidates = ideas
            return ideas
        except Exception as exc:
            logger.error("Brainstorm failed: %s", exc)
            return []

    def evaluate(
        self, ideas: list[IdeaCandidate] | None = None
    ) -> list[IdeaEvaluation]:
        """Evaluate each idea on novelty, feasibility, and impact.

        Args:
            ideas: Ideas to evaluate (defaults to current candidates).

        Returns:
            List of IdeaEvaluation objects.
        """
        ideas = ideas or self.candidates
        if not ideas:
            return []

        evaluations = []
        for idea in ideas:
            eval_result = IdeaEvaluation(
                idea_title=idea.title,
                novelty=5.0,
                feasibility=5.0,
                impact=5.0,
                overall=5.0,
            )

            if self.llm is not None:
                try:
                    response = self.llm.chat([
                        {"role": "system", "content": (
                            "Evaluate this research idea. Return JSON with "
                            "fields: novelty (0-10), feasibility (0-10), "
                            "impact (0-10), overall (0-10), "
                            "strengths (list), weaknesses (list), "
                            "suggestions (list)."
                        )},
                        {"role": "user", "content": (
                            f"Title: {idea.title}\n"
                            f"Description: {idea.description}"
                        )},
                    ])
                    eval_result = self._parse_evaluation(
                        response, idea.title
                    )
                except Exception as exc:
                    logger.warning("Evaluation failed for %s: %s", idea.title, exc)

            evaluations.append(eval_result)

        self.evaluations = evaluations
        return evaluations

    def refine(
        self, idea: IdeaCandidate, feedback: str
    ) -> IdeaCandidate:
        """Refine an idea based on human feedback.

        Args:
            idea: The idea to refine.
            feedback: Human's feedback and suggestions.

        Returns:
            Refined IdeaCandidate.
        """
        if self.llm is None:
            return idea

        try:
            response = self.llm.chat([
                {"role": "system", "content": (
                    "Refine this research idea based on the feedback. "
                    "Return updated JSON with title, description, "
                    "baselines (list), keywords (list)."
                )},
                {"role": "user", "content": (
                    f"Original idea:\n"
                    f"Title: {idea.title}\n"
                    f"Description: {idea.description}\n\n"
                    f"Human feedback:\n{feedback}"
                )},
            ])
            refined = self._parse_single_idea(response)
            if refined:
                return refined
        except Exception as exc:
            logger.warning("Refinement failed: %s", exc)

        return idea

    def select(self, idea: IdeaCandidate) -> None:
        """Mark an idea as the selected hypothesis."""
        idea.human_approved = True
        self.selected_idea = idea

    def save(self) -> None:
        """Save workshop state to run_dir/hitl/."""
        hitl_dir = self.run_dir / "hitl"
        hitl_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "candidates": [c.to_dict() for c in self.candidates],
            "evaluations": [e.to_dict() for e in self.evaluations],
            "selected": (
                self.selected_idea.to_dict() if self.selected_idea else None
            ),
        }
        (hitl_dir / "idea_workshop.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _build_brainstorm_prompt(
        self, synthesis: str, human_hint: str, num_ideas: int
    ) -> str:
        parts = [
            f"Based on the following research synthesis, generate "
            f"{num_ideas} novel research idea candidates.\n\n"
            f"## Research Synthesis\n{synthesis[:3000]}",
        ]
        if human_hint:
            parts.append(
                f"\n## Human Guidance\n{human_hint}"
            )
        parts.append(
            "\n\nFor each idea, provide:\n"
            "- title: A concise title\n"
            "- description: 2-3 sentence description\n"
            "- baselines: Suggested baseline methods\n"
            "- keywords: Key technical terms\n\n"
            "Return as a JSON array of objects."
        )
        return "\n".join(parts)

    def _parse_ideas(
        self, response: str, expected: int
    ) -> list[IdeaCandidate]:
        """Parse LLM response into IdeaCandidate list."""
        try:
            # Try direct JSON parse
            data = json.loads(response)
            if isinstance(data, list):
                return [IdeaCandidate.from_dict(d) for d in data[:expected]]
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code block
        import re
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, list):
                    return [
                        IdeaCandidate.from_dict(d) for d in data[:expected]
                    ]
            except json.JSONDecodeError:
                pass

        # Fallback: create a single idea from the text
        return [
            IdeaCandidate(
                title="AI-generated idea",
                description=response[:500],
            )
        ]

    def _parse_single_idea(self, response: str) -> IdeaCandidate | None:
        try:
            data = json.loads(response)
            if isinstance(data, dict):
                return IdeaCandidate.from_dict(data)
        except json.JSONDecodeError:
            pass
        import re
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict):
                    return IdeaCandidate.from_dict(data)
            except json.JSONDecodeError:
                pass
        return None

    def _parse_evaluation(
        self, response: str, idea_title: str
    ) -> IdeaEvaluation:
        default = IdeaEvaluation(idea_title=idea_title)
        try:
            data = json.loads(response)
            if isinstance(data, dict):
                return IdeaEvaluation(
                    idea_title=idea_title,
                    novelty=float(data.get("novelty", 5.0)),
                    feasibility=float(data.get("feasibility", 5.0)),
                    impact=float(data.get("impact", 5.0)),
                    overall=float(data.get("overall", 5.0)),
                    strengths=data.get("strengths", []),
                    weaknesses=data.get("weaknesses", []),
                    suggestions=data.get("suggestions", []),
                )
        except (json.JSONDecodeError, ValueError):
            pass
        return default
