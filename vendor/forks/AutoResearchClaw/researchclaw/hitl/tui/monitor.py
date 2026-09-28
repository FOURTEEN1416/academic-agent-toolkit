"""Real-time experiment monitoring for terminal display.

Shows live training metrics, resource usage, and pipeline progress
during Stage 12 (EXPERIMENT_RUN) and Stage 13 (ITERATIVE_REFINE).

Uses the ``rich`` library for formatted output.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.text import Text

    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


class ExperimentMonitor:
    """Monitor experiment execution with live terminal updates.

    Reads experiment run data from the stage directory and displays:
    - Current metrics (loss, accuracy, etc.)
    - Comparison with baselines
    - Training progress (epoch/iteration)
    - Time estimates
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self._last_metrics: dict[str, float] = {}

    def get_experiment_status(self) -> dict[str, Any]:
        """Read current experiment status from run artifacts."""
        status: dict[str, Any] = {
            "runs": [],
            "current_metrics": {},
            "best_metrics": {},
            "baselines": {},
            "progress": 0.0,
            "elapsed_sec": 0.0,
        }

        # Read runs from stage-12 or stage-13
        for stage in ("stage-12", "stage-13"):
            runs_dir = self.run_dir / stage / "runs"
            if runs_dir.is_dir():
                for run_file in sorted(runs_dir.glob("*.json")):
                    try:
                        data = json.loads(run_file.read_text(encoding="utf-8"))
                        status["runs"].append(data)
                        # Track metrics
                        metrics = data.get("metrics", {})
                        if isinstance(metrics, dict):
                            for k, v in metrics.items():
                                if isinstance(v, (int, float)):
                                    status["current_metrics"][k] = v
                                    if k not in status["best_metrics"] or v > status["best_metrics"][k]:
                                        status["best_metrics"][k] = v
                    except (json.JSONDecodeError, OSError):
                        continue

        # Read experiment summary if available
        for stage in ("stage-14", "stage-12"):
            summary = self.run_dir / stage / "experiment_summary.json"
            if summary.exists():
                try:
                    data = json.loads(summary.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        status["summary"] = data
                        # Extract baseline metrics
                        conditions = data.get("conditions", [])
                        for cond in conditions:
                            if isinstance(cond, dict):
                                name = cond.get("name", "")
                                metrics = cond.get("metrics", {})
                                if "baseline" in name.lower() or cond.get("is_baseline"):
                                    status["baselines"][name] = metrics
                except (json.JSONDecodeError, OSError):
                    pass
                break

        # Calculate progress
        total_runs = len(status["runs"])
        if total_runs > 0:
            completed = sum(1 for r in status["runs"] if r.get("metrics"))
            status["progress"] = completed / total_runs

        return status

    def format_metrics_table(self, status: dict[str, Any] | None = None) -> str:
        """Format experiment metrics as a readable table."""
        if status is None:
            status = self.get_experiment_status()

        if not status["current_metrics"] and not status["baselines"]:
            return "  No experiment data available yet."

        lines = ["  Experiment Metrics:"]
        lines.append("  " + "─" * 50)

        # Current metrics
        if status["current_metrics"]:
            lines.append("  Current:")
            for name, value in sorted(status["current_metrics"].items()):
                old = self._last_metrics.get(name)
                trend = ""
                if old is not None:
                    if value > old:
                        trend = " ↑"
                    elif value < old:
                        trend = " ↓"
                if isinstance(value, float):
                    lines.append(f"    {name}: {value:.4f}{trend}")
                else:
                    lines.append(f"    {name}: {value}{trend}")
            self._last_metrics = dict(status["current_metrics"])

        # Best metrics
        if status["best_metrics"]:
            lines.append("  Best:")
            for name, value in sorted(status["best_metrics"].items()):
                if isinstance(value, float):
                    lines.append(f"    {name}: {value:.4f}")
                else:
                    lines.append(f"    {name}: {value}")

        # Baselines
        if status["baselines"]:
            lines.append("  Baselines:")
            for bname, metrics in status["baselines"].items():
                if isinstance(metrics, dict):
                    metric_str = ", ".join(
                        f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                        for k, v in list(metrics.items())[:3]
                    )
                    lines.append(f"    {bname}: {metric_str}")

        # Progress
        pct = int(status["progress"] * 100)
        bar_width = 30
        filled = int(bar_width * status["progress"])
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"\n  Progress: [{bar}] {pct}%")
        lines.append(f"  Runs: {len(status['runs'])}")

        return "\n".join(lines)

    def show_live(self, interval_sec: float = 5.0, max_updates: int = 100) -> None:
        """Show live-updating experiment monitor in terminal.

        Refreshes every ``interval_sec`` seconds until the experiment
        completes or ``max_updates`` is reached.
        """
        if _HAS_RICH:
            self._show_live_rich(interval_sec, max_updates)
        else:
            self._show_live_plain(interval_sec, max_updates)

    def _show_live_rich(self, interval_sec: float, max_updates: int) -> None:
        console = Console()

        with Live(console=console, refresh_per_second=1) as live:
            for _ in range(max_updates):
                status = self.get_experiment_status()
                table = self._build_rich_table(status)
                live.update(table)

                if status["progress"] >= 1.0:
                    break
                time.sleep(interval_sec)

    def _show_live_plain(self, interval_sec: float, max_updates: int) -> None:
        for i in range(max_updates):
            status = self.get_experiment_status()
            print(f"\033[2J\033[H")  # Clear screen
            print(self.format_metrics_table(status))

            if status["progress"] >= 1.0:
                break
            time.sleep(interval_sec)

    def _build_rich_table(self, status: dict[str, Any]) -> Panel:
        table = Table(title="Experiment Monitor", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Current", style="yellow")
        table.add_column("Best", style="green")
        table.add_column("Trend", style="dim")

        for name in sorted(status["current_metrics"]):
            current = status["current_metrics"][name]
            best = status["best_metrics"].get(name, "")
            old = self._last_metrics.get(name)
            trend = ""
            if old is not None:
                if current > old:
                    trend = "↑"
                elif current < old:
                    trend = "↓"

            fmt = lambda v: f"{v:.4f}" if isinstance(v, float) else str(v)
            table.add_row(name, fmt(current), fmt(best), trend)

        self._last_metrics = dict(status["current_metrics"])

        # Progress bar
        pct = int(status["progress"] * 100)
        bar_width = 30
        filled = int(bar_width * status["progress"])
        bar = "█" * filled + "░" * (bar_width - filled)
        progress_text = f"[{bar}] {pct}% | Runs: {len(status['runs'])}"

        return Panel(
            table,
            subtitle=progress_text,
            border_style="blue",
        )
