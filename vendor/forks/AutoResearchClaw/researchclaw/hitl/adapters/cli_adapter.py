"""CLI (terminal) adapter for HITL interaction.

Provides a rich terminal interface for reviewing stage outputs,
approving/rejecting gates, editing files, and collaborating with AI.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    PauseReason,
    WaitingState,
)

logger = logging.getLogger(__name__)

# ANSI color codes
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BLUE = "\033[34m"
_CYAN = "\033[36m"
_MAGENTA = "\033[35m"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


_COLOR = _supports_color()


def _c(code: str, text: str) -> str:
    if not _COLOR:
        return text
    return f"{code}{text}{_RESET}"


def _hr() -> str:
    cols = shutil.get_terminal_size(fallback=(80, 24)).columns
    return "─" * min(cols, 80)


# Action descriptions shown to the user
_ACTION_LABELS: dict[str, str] = {
    "approve": f"  {_c(_GREEN, '[a]')} Approve and continue",
    "reject": f"  {_c(_RED, '[r]')} Reject and rollback",
    "edit": f"  {_c(_YELLOW, '[e]')} Edit stage output",
    "collaborate": f"  {_c(_CYAN, '[c]')} Start collaborative chat",
    "inject": f"  {_c(_MAGENTA, '[i]')} Inject guidance / direction",
    "skip": f"  {_c(_DIM, '[s]')} Skip this stage",
    "rollback": f"  {_c(_RED, '[b]')} Rollback to a specific stage",
    "abort": f"  {_c(_RED, '[q]')} Abort pipeline",
    "view_output": f"  {_c(_BLUE, '[v]')} View full stage output",
    "resume": f"  {_c(_GREEN, '[a]')} Resume (continue)",
}

# Short key -> HumanAction mapping
_KEY_MAP: dict[str, HumanAction] = {
    "a": HumanAction.APPROVE,
    "r": HumanAction.REJECT,
    "e": HumanAction.EDIT,
    "c": HumanAction.COLLABORATE,
    "i": HumanAction.INJECT,
    "s": HumanAction.SKIP,
    "b": HumanAction.ROLLBACK,
    "q": HumanAction.ABORT,
    "v": HumanAction.RESUME,  # view → handled separately
    "approve": HumanAction.APPROVE,
    "reject": HumanAction.REJECT,
    "edit": HumanAction.EDIT,
    "collaborate": HumanAction.COLLABORATE,
    "inject": HumanAction.INJECT,
    "skip": HumanAction.SKIP,
    "rollback": HumanAction.ROLLBACK,
    "abort": HumanAction.ABORT,
    "resume": HumanAction.RESUME,
}


class CLIAdapter:
    """Terminal-based HITL adapter using stdin/stdout."""

    def __init__(self, run_dir: Path | None = None) -> None:
        self.run_dir = run_dir

    def collect_input(self, waiting: WaitingState) -> HumanInput:
        """Display pause info and collect human input interactively."""
        self._show_pause_banner(waiting)
        self._show_context(waiting)
        self._show_available_actions(waiting)

        while True:
            try:
                raw = input(
                    f"\n{_c(_BOLD, 'Action')} > "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return HumanInput(action=HumanAction.ABORT)

            if not raw:
                continue

            # Handle 'v' (view) specially
            if raw == "v":
                self._show_full_output(waiting)
                continue

            action = _KEY_MAP.get(raw)
            if action is None:
                print(
                    f"  {_c(_RED, '?')} Unknown action '{raw}'. "
                    "Use one of the keys shown above."
                )
                continue

            if action.value not in waiting.available_actions:
                print(
                    f"  {_c(_RED, '!')} Action '{action.value}' "
                    "not available at this point."
                )
                continue

            return self._build_human_input(action, waiting)

    def _show_pause_banner(self, waiting: WaitingState) -> None:
        reason_labels = {
            PauseReason.PRE_STAGE: "Pre-stage checkpoint",
            PauseReason.POST_STAGE: "Post-stage review",
            PauseReason.GATE_APPROVAL: "Gate approval required",
            PauseReason.QUALITY_BELOW_THRESHOLD: "Quality below threshold",
            PauseReason.ERROR_OCCURRED: "Error — human decision needed",
            PauseReason.HUMAN_REQUESTED: "Paused by user",
            PauseReason.CONFIDENCE_LOW: "Low confidence — review needed",
        }
        reason_text = reason_labels.get(waiting.reason, waiting.reason.value)

        print()
        print(_c(_BOLD, _hr()))
        print(
            _c(
                _BOLD,
                f"  HITL | Stage {waiting.stage:02d}: "
                f"{waiting.stage_name}",
            )
        )
        print(f"  {_c(_YELLOW, reason_text)}")
        print(_c(_BOLD, _hr()))

    def _show_context(self, waiting: WaitingState) -> None:
        if waiting.context_summary:
            print()
            print(_c(_DIM, "  Stage output summary:"))
            for line in waiting.context_summary.split("\n")[:20]:
                print(f"  {line}")
            if waiting.context_summary.count("\n") > 20:
                print(
                    _c(_DIM, f"  ... ({waiting.context_summary.count(chr(10)) - 20} more lines)")
                )

        if waiting.output_files:
            print()
            print(_c(_DIM, "  Output files:"))
            for f in waiting.output_files:
                print(f"    {_c(_BLUE, f)}")

    def _show_available_actions(self, waiting: WaitingState) -> None:
        print()
        print(_c(_DIM, "  Available actions:"))
        for action_name in waiting.available_actions:
            label = _ACTION_LABELS.get(action_name, f"  [{action_name}]")
            print(label)
        # Always show view
        print(_ACTION_LABELS["view_output"])

    def _show_full_output(self, waiting: WaitingState) -> None:
        """Display the full output files of the current stage."""
        if self.run_dir is None:
            print(_c(_RED, "  No run directory available."))
            return

        stage_dir = self.run_dir / f"stage-{waiting.stage:02d}"
        if not stage_dir.exists():
            print(_c(_RED, f"  Stage directory not found: {stage_dir}"))
            return

        for fname in waiting.output_files:
            fpath = stage_dir / fname
            if fpath.is_file():
                print()
                print(_c(_BOLD, f"  ── {fname} ──"))
                try:
                    content = fpath.read_text(encoding="utf-8")
                    # Truncate very long files
                    lines = content.split("\n")
                    if len(lines) > 100:
                        for line in lines[:100]:
                            print(f"  {line}")
                        print(
                            _c(_DIM, f"\n  ... ({len(lines) - 100} more lines)")
                        )
                    else:
                        for line in lines:
                            print(f"  {line}")
                except (OSError, UnicodeDecodeError) as exc:
                    print(_c(_RED, f"  Error reading file: {exc}"))
            elif fpath.is_dir():
                print()
                print(_c(_BOLD, f"  ── {fname}/ ──"))
                children = sorted(fpath.iterdir())[:20]
                for child in children:
                    size = (
                        child.stat().st_size if child.is_file() else 0
                    )
                    print(
                        f"    {child.name}"
                        f" {_c(_DIM, f'({size} bytes)') if size else ''}"
                    )

    def _build_human_input(
        self, action: HumanAction, waiting: WaitingState
    ) -> HumanInput:
        """Collect additional data for the chosen action."""

        if action == HumanAction.APPROVE:
            return HumanInput(action=action)

        if action == HumanAction.REJECT:
            reason = self._prompt("  Rejection reason (optional): ")
            return HumanInput(action=action, message=reason)

        if action == HumanAction.EDIT:
            return self._handle_edit(waiting)

        if action == HumanAction.INJECT:
            guidance = self._prompt_multiline(
                "  Enter guidance (end with empty line):"
            )
            return HumanInput(action=action, guidance=guidance)

        if action == HumanAction.COLLABORATE:
            return HumanInput(action=action)

        if action == HumanAction.SKIP:
            confirm = self._prompt("  Confirm skip? [y/N] ")
            if confirm.lower() != "y":
                return HumanInput(action=HumanAction.RESUME)
            return HumanInput(action=action)

        if action == HumanAction.ROLLBACK:
            target = self._prompt("  Rollback to stage number: ")
            try:
                stage_num = int(target)
            except ValueError:
                print(_c(_RED, "  Invalid stage number."))
                return HumanInput(action=HumanAction.RESUME)
            return HumanInput(
                action=action, rollback_to_stage=stage_num
            )

        if action == HumanAction.ABORT:
            confirm = self._prompt(
                f"  {_c(_RED, 'Abort pipeline? [y/N]')} "
            )
            if confirm.lower() != "y":
                return HumanInput(action=HumanAction.RESUME)
            return HumanInput(action=action)

        return HumanInput(action=action)

    def _handle_edit(self, waiting: WaitingState) -> HumanInput:
        """Let user edit stage output files."""
        if self.run_dir is None:
            print(_c(_RED, "  No run directory — cannot edit."))
            return HumanInput(action=HumanAction.RESUME)

        stage_dir = self.run_dir / f"stage-{waiting.stage:02d}"
        editable = [
            f
            for f in waiting.output_files
            if (stage_dir / f).is_file()
        ]

        if not editable:
            print(_c(_RED, "  No editable files found."))
            return HumanInput(action=HumanAction.RESUME)

        if len(editable) == 1:
            target = editable[0]
        else:
            print("  Select file to edit:")
            for i, f in enumerate(editable, 1):
                print(f"    {i}. {f}")
            choice = self._prompt("  File number: ")
            try:
                idx = int(choice) - 1
                target = editable[idx]
            except (ValueError, IndexError):
                print(_c(_RED, "  Invalid choice."))
                return HumanInput(action=HumanAction.RESUME)

        fpath = stage_dir / target
        original = fpath.read_text(encoding="utf-8")

        # Use $EDITOR or platform-appropriate fallback
        editor = os.environ.get("EDITOR", "")
        if not editor:
            if sys.platform == "win32":
                editor = "notepad"
            else:
                editor = "nano"
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=fpath.suffix or ".md",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(original)
            tmp_path = tmp.name

        try:
            subprocess.run([editor, tmp_path], check=True)
            edited = Path(tmp_path).read_text(encoding="utf-8")
        except (subprocess.CalledProcessError, OSError) as exc:
            print(_c(_RED, f"  Editor failed: {exc}"))
            Path(tmp_path).unlink(missing_ok=True)
            return HumanInput(action=HumanAction.RESUME)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if edited == original:
            print(_c(_DIM, "  No changes made."))
            return HumanInput(action=HumanAction.RESUME)

        # Save backup of original
        snapshots_dir = self.run_dir / "hitl" / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        backup = snapshots_dir / f"stage_{waiting.stage:02d}_{target}.orig"
        if not backup.exists():
            backup.write_text(original, encoding="utf-8")

        # Write edited version
        fpath.write_text(edited, encoding="utf-8")
        print(_c(_GREEN, f"  Saved edits to {target}"))

        return HumanInput(
            action=HumanAction.EDIT,
            edited_files={target: edited},
            message=f"Edited {target}",
        )

    def show_stage_output(
        self, stage_num: int, stage_name: str, summary: str
    ) -> None:
        print(f"\n{_c(_DIM, f'  Stage {stage_num:02d} ({stage_name}):')}")
        for line in summary.split("\n")[:10]:
            print(f"  {line}")

    def show_message(self, message: str) -> None:
        print(f"  {_c(_BLUE, 'ℹ')} {message}")

    def show_error(self, message: str) -> None:
        print(f"  {_c(_RED, '✗')} {message}")

    def show_progress(
        self, stage_num: int, total: int, stage_name: str, status: str
    ) -> None:
        bar_width = 30
        progress = stage_num / total
        filled = int(bar_width * progress)
        bar = "█" * filled + "░" * (bar_width - filled)
        pct = int(progress * 100)
        print(
            f"  [{bar}] {pct}% — Stage {stage_num}/{total} "
            f"{stage_name} {status}"
        )

    @staticmethod
    def _prompt(message: str) -> str:
        try:
            return input(message).strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    @staticmethod
    def _prompt_multiline(header: str) -> str:
        print(header)
        lines: list[str] = []
        while True:
            try:
                line = input("  > ")
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                break
            lines.append(line)
        return "\n".join(lines)
