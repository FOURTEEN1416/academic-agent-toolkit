"""HITL TUI panel: rich terminal interface for pipeline monitoring.

Uses the ``rich`` library (already a project dependency) for formatted output.
Falls back to plain text if rich is not available.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import Progress, BarColumn, TextColumn
    from rich.columns import Columns
    from rich.markdown import Markdown

    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


# Stage phase labels
_PHASE_LABELS = {
    "A": ("Research Scoping", (1, 2)),
    "B": ("Literature Discovery", (3, 4, 5, 6)),
    "C": ("Knowledge Synthesis", (7, 8)),
    "D": ("Experiment Design", (9, 10, 11)),
    "E": ("Experiment Execution", (12, 13)),
    "F": ("Analysis & Decision", (14, 15)),
    "G": ("Paper Writing", (16, 17, 18, 19)),
    "H": ("Finalization", (20, 21, 22, 23)),
}


def show_pipeline_status(
    run_dir: Path,
    current_stage: int = 0,
    mode: str = "full-auto",
) -> None:
    """Display a rich pipeline status panel."""
    if _HAS_RICH:
        _show_rich_status(run_dir, current_stage, mode)
    else:
        _show_plain_status(run_dir, current_stage, mode)


def show_stage_review(
    stage_num: int,
    stage_name: str,
    run_dir: Path,
    summary: str = "",
) -> None:
    """Display a stage review panel."""
    if _HAS_RICH:
        _show_rich_review(stage_num, stage_name, run_dir, summary)
    else:
        print(f"\n--- Stage {stage_num}: {stage_name} ---")
        if summary:
            print(summary)


def show_intervention_log(run_dir: Path) -> None:
    """Display the intervention history."""
    log_path = run_dir / "hitl" / "interventions.jsonl"
    if not log_path.exists():
        print("  No interventions recorded.")
        return

    entries = []
    for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        print("  No interventions recorded.")
        return

    if _HAS_RICH:
        console = Console()
        table = Table(title="HITL Intervention History")
        table.add_column("Stage", style="cyan", width=8)
        table.add_column("Type", style="yellow", width=15)
        table.add_column("Outcome", width=40)
        table.add_column("Duration", style="dim", width=10)

        for entry in entries:
            stage = str(entry.get("stage", "?"))
            itype = entry.get("type", "?")
            outcome = entry.get("outcome", "")[:40]
            duration = f"{entry.get('duration_sec', 0):.1f}s"
            table.add_row(stage, itype, outcome, duration)

        console.print(table)
    else:
        print("\n  Intervention History:")
        for entry in entries:
            print(
                f"  Stage {entry.get('stage', '?')}: "
                f"{entry.get('type', '?')} — "
                f"{entry.get('outcome', '')[:60]}"
            )


# ---------------------------------------------------------------------------
# Rich implementations
# ---------------------------------------------------------------------------


def _show_rich_status(
    run_dir: Path, current_stage: int, mode: str
) -> None:
    console = Console()

    # Read stage health files
    stage_statuses: dict[int, str] = {}
    for i in range(1, 24):
        health_path = run_dir / f"stage-{i:02d}" / "stage_health.json"
        if health_path.exists():
            try:
                data = json.loads(health_path.read_text(encoding="utf-8"))
                stage_statuses[i] = data.get("status", "unknown")
            except (json.JSONDecodeError, OSError):
                pass

    # Build phase progress
    phase_rows = []
    for phase_key, (phase_name, stages) in _PHASE_LABELS.items():
        done = sum(1 for s in stages if stage_statuses.get(s) == "done")
        total = len(stages)
        if done == total:
            status_icon = "[green]✓[/green]"
        elif any(s == current_stage for s in stages):
            status_icon = "[yellow]●[/yellow]"
        elif done > 0:
            status_icon = "[yellow]◐[/yellow]"
        else:
            status_icon = "[dim]○[/dim]"
        phase_rows.append(f" {status_icon} Phase {phase_key}: {phase_name} ({done}/{total})")

    # Read run info
    run_id = "unknown"
    checkpoint_path = run_dir / "checkpoint.json"
    if checkpoint_path.exists():
        try:
            cp = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            run_id = cp.get("run_id", "unknown")
        except (json.JSONDecodeError, OSError):
            pass

    content = "\n".join(phase_rows)
    panel = Panel(
        content,
        title=f"[bold]AutoResearchClaw Pipeline[/bold] | {run_id} | Mode: {mode}",
        border_style="blue",
    )
    console.print(panel)


def _show_rich_review(
    stage_num: int,
    stage_name: str,
    run_dir: Path,
    summary: str,
) -> None:
    console = Console()

    content_parts = []
    if summary:
        content_parts.append(summary)

    # Show output files
    stage_dir = run_dir / f"stage-{stage_num:02d}"
    if stage_dir.exists():
        files = sorted(
            f for f in stage_dir.iterdir()
            if not f.name.startswith(".") and f.name != "stage_health.json"
        )
        if files:
            content_parts.append("\n[bold]Output files:[/bold]")
            for f in files[:10]:
                if f.is_file():
                    size = f.stat().st_size
                    content_parts.append(f"  [cyan]{f.name}[/cyan] ({size} bytes)")
                elif f.is_dir():
                    count = sum(1 for _ in f.iterdir())
                    content_parts.append(f"  [cyan]{f.name}/[/cyan] ({count} items)")

    panel = Panel(
        "\n".join(content_parts) if content_parts else "[dim]No output[/dim]",
        title=f"[bold]Stage {stage_num}: {stage_name}[/bold]",
        border_style="yellow",
    )
    console.print(panel)


# ---------------------------------------------------------------------------
# Plain text fallback
# ---------------------------------------------------------------------------


def _show_plain_status(
    run_dir: Path, current_stage: int, mode: str
) -> None:
    print(f"\n  Pipeline Status | Mode: {mode}")
    print("  " + "─" * 50)

    for phase_key, (phase_name, stages) in _PHASE_LABELS.items():
        done = 0
        for s in stages:
            health_path = run_dir / f"stage-{s:02d}" / "stage_health.json"
            if health_path.exists():
                try:
                    data = json.loads(health_path.read_text(encoding="utf-8"))
                    if data.get("status") == "done":
                        done += 1
                except (json.JSONDecodeError, OSError):
                    pass

        total = len(stages)
        if done == total:
            icon = "✓"
        elif done > 0:
            icon = "◐"
        else:
            icon = "○"
        print(f"  {icon} Phase {phase_key}: {phase_name} ({done}/{total})")
