"""HITL learning: learn from human intervention patterns over time.

Implements Agent Learning from Human Feedback (ALHF):
- Track which stages humans frequently intervene in
- Learn common edit patterns
- Adjust confidence thresholds based on rejection rates
- Generate recommendations for future runs
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class InterventionStats:
    """Aggregated statistics for interventions at a stage."""

    stage: int
    stage_name: str = ""
    total_runs: int = 0
    approval_count: int = 0
    rejection_count: int = 0
    edit_count: int = 0
    collaborate_count: int = 0
    avg_human_time_sec: float = 0.0
    common_feedback: list[str] = field(default_factory=list)

    @property
    def approval_rate(self) -> float:
        total = self.approval_count + self.rejection_count
        if total == 0:
            return 1.0
        return self.approval_count / total

    @property
    def intervention_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return (
            self.edit_count + self.rejection_count + self.collaborate_count
        ) / self.total_runs

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "stage_name": self.stage_name,
            "total_runs": self.total_runs,
            "approval_rate": round(self.approval_rate, 3),
            "intervention_rate": round(self.intervention_rate, 3),
            "edit_count": self.edit_count,
            "rejection_count": self.rejection_count,
            "avg_human_time_sec": round(self.avg_human_time_sec, 1),
            "common_feedback": self.common_feedback[:5],
        }


class InterventionLearner:
    """Learns from historical intervention patterns.

    Analyzes past HITL interactions to:
    1. Identify stages that frequently need human intervention
    2. Recommend confidence thresholds
    3. Suggest stage policies for new runs
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize with a directory containing past run data.

        Args:
            data_dir: Directory containing run directories
                      (e.g., ``artifacts/``).
        """
        self.data_dir = data_dir
        self._stats: dict[int, InterventionStats] = {}

    def analyze_history(self) -> dict[int, InterventionStats]:
        """Analyze all past runs to build intervention statistics.

        Returns:
            Dict of stage number -> InterventionStats.
        """
        self._stats = {}
        run_dirs = self._find_run_dirs()

        for run_dir in run_dirs:
            self._analyze_run(run_dir)

        return self._stats

    def recommend_thresholds(self) -> dict[int, float]:
        """Recommend SmartPause confidence thresholds per stage.

        Stages with high rejection rates get lower thresholds (more pauses).
        Stages that are always approved get higher thresholds (fewer pauses).

        Returns:
            Dict of stage number -> recommended threshold (0-1).
        """
        if not self._stats:
            self.analyze_history()

        thresholds: dict[int, float] = {}
        for stage, stats in self._stats.items():
            if stats.total_runs < 3:
                # Not enough data — use default
                thresholds[stage] = 0.7
                continue

            # High rejection → lower threshold (pause more)
            # High approval → higher threshold (pause less)
            approval_rate = stats.approval_rate
            thresholds[stage] = max(0.3, min(0.95, approval_rate * 0.9))

        return thresholds

    def recommend_policies(self) -> dict[int, dict[str, Any]]:
        """Recommend stage policies based on historical patterns.

        Returns:
            Dict of stage number -> policy suggestion dict.
        """
        if not self._stats:
            self.analyze_history()

        policies: dict[int, dict[str, Any]] = {}
        for stage, stats in self._stats.items():
            policy: dict[str, Any] = {}

            if stats.rejection_count > stats.approval_count:
                # More rejections than approvals — require approval
                policy["require_approval"] = True
                policy["enable_collaboration"] = True

            if stats.edit_count > stats.total_runs * 0.5:
                # Edits happen in >50% of runs
                policy["allow_edit_output"] = True
                policy["pause_after"] = True

            if stats.collaborate_count > 0:
                policy["enable_collaboration"] = True

            if stats.intervention_rate < 0.1 and stats.total_runs > 5:
                # Very low intervention rate — can auto-proceed
                policy["auto_execute"] = True
                policy["pause_after"] = False

            if policy:
                policies[stage] = policy

        return policies

    def get_report(self) -> str:
        """Generate a human-readable report of learning insights."""
        if not self._stats:
            self.analyze_history()

        if not self._stats:
            return "No historical data found."

        lines = ["## HITL Learning Report\n"]
        lines.append(
            f"Analyzed {len(self._find_run_dirs())} runs across "
            f"{len(self._stats)} stages.\n"
        )

        # Most intervened stages
        sorted_stages = sorted(
            self._stats.values(),
            key=lambda s: s.intervention_rate,
            reverse=True,
        )

        lines.append("### Stages needing most human attention:")
        for stats in sorted_stages[:5]:
            if stats.intervention_rate > 0:
                lines.append(
                    f"  Stage {stats.stage} ({stats.stage_name}): "
                    f"{stats.intervention_rate:.0%} intervention rate, "
                    f"{stats.approval_rate:.0%} approval rate"
                )

        lines.append("\n### Stages running well autonomously:")
        for stats in sorted_stages[-5:]:
            if stats.total_runs > 0 and stats.intervention_rate < 0.2:
                lines.append(
                    f"  Stage {stats.stage} ({stats.stage_name}): "
                    f"{stats.approval_rate:.0%} auto-approved"
                )

        return "\n".join(lines)

    def save(self, path: Path) -> None:
        """Save learning data."""
        data = {
            "stats": {
                str(k): v.to_dict() for k, v in self._stats.items()
            },
            "thresholds": self.recommend_thresholds(),
            "policies": self.recommend_policies(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _find_run_dirs(self) -> list[Path]:
        """Find all run directories with HITL data."""
        if not self.data_dir.exists():
            return []
        return sorted(
            d
            for d in self.data_dir.iterdir()
            if d.is_dir() and (d / "hitl" / "interventions.jsonl").exists()
        )

    def _analyze_run(self, run_dir: Path) -> None:
        """Analyze a single run's intervention log."""
        log_path = run_dir / "hitl" / "interventions.jsonl"
        if not log_path.exists():
            return

        try:
            for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                entry = json.loads(line)
                stage = entry.get("stage", 0)
                if stage == 0:
                    continue

                if stage not in self._stats:
                    self._stats[stage] = InterventionStats(
                        stage=stage,
                        stage_name=entry.get("stage_name", ""),
                    )

                stats = self._stats[stage]
                stats.total_runs += 1

                itype = entry.get("type", "")
                if itype == "approve":
                    stats.approval_count += 1
                elif itype == "reject":
                    stats.rejection_count += 1
                elif itype == "edit_output":
                    stats.edit_count += 1
                elif itype == "start_chat":
                    stats.collaborate_count += 1

                duration = entry.get("duration_sec", 0)
                if duration > 0:
                    # Running average
                    n = stats.total_runs
                    stats.avg_human_time_sec = (
                        stats.avg_human_time_sec * (n - 1) + duration
                    ) / n

                # Collect feedback messages
                hi = entry.get("human_input", {})
                msg = hi.get("message", "") if isinstance(hi, dict) else ""
                if msg and len(msg) > 10:
                    stats.common_feedback.append(msg[:100])

        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to analyze run %s: %s", run_dir, exc)
