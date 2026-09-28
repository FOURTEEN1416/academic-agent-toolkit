"""Baseline Navigator: assists in selecting and configuring baselines (Stage 9).

Helps the human researcher and AI collaboratively choose:
- Baseline methods to compare against
- Benchmark datasets to evaluate on
- Metrics to report
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BaselineCandidate:
    """A potential baseline method."""

    name: str
    description: str = ""
    paper_url: str = ""
    code_url: str = ""
    is_standard: bool = False
    notes: str = ""
    added_by: str = "ai"  # "ai" or "human"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "paper_url": self.paper_url,
            "code_url": self.code_url,
            "is_standard": self.is_standard,
            "notes": self.notes,
            "added_by": self.added_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaselineCandidate:
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


@dataclass
class BenchmarkCandidate:
    """A potential benchmark dataset."""

    name: str
    description: str = ""
    url: str = ""
    size_info: str = ""
    standard_metrics: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "size_info": self.size_info,
            "standard_metrics": self.standard_metrics,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkCandidate:
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


class BaselineNavigator:
    """Assists in baseline and benchmark selection for experiment design.

    Provides a structured workflow:
    1. AI suggests baselines based on the research idea
    2. Human reviews, adds, or removes baselines
    3. AI searches for open-source implementations
    4. Human confirms final selection
    """

    def __init__(self, run_dir: Path, llm_client: Any = None) -> None:
        self.run_dir = run_dir
        self.llm = llm_client
        self.baselines: list[BaselineCandidate] = []
        self.benchmarks: list[BenchmarkCandidate] = []
        self.metrics: list[str] = []

    def suggest_baselines(
        self, idea: str, domain: str = ""
    ) -> list[BaselineCandidate]:
        """AI suggests baseline methods based on the research idea.

        Args:
            idea: Research idea/hypothesis description.
            domain: Research domain (e.g., "ml", "nlp", "cv").

        Returns:
            List of suggested baseline candidates.
        """
        if self.llm is None:
            return []

        try:
            response = self.llm.chat([
                {"role": "system", "content": (
                    "You are a research advisor. Suggest baseline methods "
                    "for comparison in an experiment. Return a JSON array "
                    "of objects with: name, description, paper_url (if known), "
                    "code_url (GitHub link if known), is_standard (bool)."
                )},
                {"role": "user", "content": (
                    f"Research idea: {idea}\n"
                    f"Domain: {domain or 'general ML'}\n\n"
                    "Suggest 3-5 strong baseline methods."
                )},
            ])
            candidates = self._parse_baselines(response)
            self.baselines.extend(candidates)
            return candidates
        except Exception as exc:
            logger.error("Baseline suggestion failed: %s", exc)
            return []

    def human_add_baseline(
        self, name: str, code_url: str = "", notes: str = ""
    ) -> BaselineCandidate:
        """Human manually adds a baseline."""
        baseline = BaselineCandidate(
            name=name,
            code_url=code_url,
            notes=notes,
            added_by="human",
        )
        self.baselines.append(baseline)
        return baseline

    def human_remove_baseline(self, name: str) -> bool:
        """Remove a baseline by name. Returns True if found."""
        for i, b in enumerate(self.baselines):
            if b.name.lower() == name.lower():
                self.baselines.pop(i)
                return True
        return False

    def suggest_benchmarks(
        self, idea: str, domain: str = ""
    ) -> list[BenchmarkCandidate]:
        """AI suggests benchmark datasets."""
        if self.llm is None:
            return []

        try:
            response = self.llm.chat([
                {"role": "system", "content": (
                    "Suggest benchmark datasets for evaluating this research. "
                    "Return JSON array with: name, description, url, "
                    "size_info, standard_metrics (list of metric names)."
                )},
                {"role": "user", "content": (
                    f"Research: {idea}\nDomain: {domain or 'general ML'}"
                )},
            ])
            benchmarks = self._parse_benchmarks(response)
            self.benchmarks.extend(benchmarks)
            return benchmarks
        except Exception as exc:
            logger.error("Benchmark suggestion failed: %s", exc)
            return []

    def suggest_metrics(
        self, idea: str, benchmarks: list[BenchmarkCandidate] | None = None
    ) -> list[str]:
        """Suggest evaluation metrics based on idea and benchmarks."""
        benchmarks = benchmarks or self.benchmarks
        if self.llm is None:
            return ["accuracy", "f1_score"]

        try:
            bench_info = ", ".join(b.name for b in benchmarks)
            response = self.llm.chat([
                {"role": "system", "content": (
                    "Suggest evaluation metrics. Return a JSON array of "
                    "metric name strings."
                )},
                {"role": "user", "content": (
                    f"Research: {idea}\nBenchmarks: {bench_info}"
                )},
            ])
            metrics = self._parse_metrics(response)
            self.metrics = metrics
            return metrics
        except Exception as exc:
            logger.error("Metric suggestion failed: %s", exc)
            return []

    def generate_checklist(self) -> str:
        """Generate a human-readable checklist for experiment design review."""
        lines = ["## Experiment Design Checklist\n"]

        lines.append("### Baselines")
        if self.baselines:
            for b in self.baselines:
                status = "+" if b.added_by == "human" else " "
                code = f" [{b.code_url}]" if b.code_url else ""
                lines.append(f"  [{status}] {b.name}{code}")
        else:
            lines.append("  [!] No baselines selected — add at least 2")

        lines.append("\n### Benchmarks")
        if self.benchmarks:
            for b in self.benchmarks:
                lines.append(f"  [ ] {b.name}: {b.description[:60]}")
        else:
            lines.append("  [!] No benchmarks selected")

        lines.append("\n### Metrics")
        if self.metrics:
            for m in self.metrics:
                lines.append(f"  [ ] {m}")
        else:
            lines.append("  [!] No metrics defined")

        lines.append("\n### Review Questions")
        lines.append("  [ ] Are all standard baselines for this domain included?")
        lines.append("  [ ] Do the benchmarks cover the claimed scope?")
        lines.append("  [ ] Are the metrics appropriate for the task?")
        lines.append("  [ ] Is there at least one ablation planned?")

        return "\n".join(lines)

    def save(self) -> None:
        """Save navigator state."""
        hitl_dir = self.run_dir / "hitl"
        hitl_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "baselines": [b.to_dict() for b in self.baselines],
            "benchmarks": [b.to_dict() for b in self.benchmarks],
            "metrics": self.metrics,
        }
        (hitl_dir / "baseline_navigator.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _parse_baselines(self, response: str) -> list[BaselineCandidate]:
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return [BaselineCandidate.from_dict(d) for d in data]
        except json.JSONDecodeError:
            pass
        import re
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, list):
                    return [BaselineCandidate.from_dict(d) for d in data]
            except json.JSONDecodeError:
                pass
        return []

    def _parse_benchmarks(self, response: str) -> list[BenchmarkCandidate]:
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return [BenchmarkCandidate.from_dict(d) for d in data]
        except json.JSONDecodeError:
            pass
        return []

    def _parse_metrics(self, response: str) -> list[str]:
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return [str(m) for m in data]
        except json.JSONDecodeError:
            pass
        return []
