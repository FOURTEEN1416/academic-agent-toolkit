"""HITL output editor: view and modify stage outputs."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class StageEditor:
    """Provides read/write access to stage output files with snapshot support.

    Before any edit, the original file is backed up to ``hitl/snapshots/``
    so it can be restored if needed.
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self._snapshots_dir = run_dir / "hitl" / "snapshots"

    def stage_dir(self, stage_num: int) -> Path:
        return self.run_dir / f"stage-{stage_num:02d}"

    def list_outputs(self, stage_num: int) -> list[str]:
        """List all output files for a stage."""
        d = self.stage_dir(stage_num)
        if not d.exists():
            return []
        files: list[str] = []
        for item in sorted(d.iterdir()):
            if item.name.startswith(".") or item.name == "stage_health.json":
                continue
            if item.is_file():
                files.append(item.name)
            elif item.is_dir():
                files.append(item.name + "/")
        return files

    def read_output(self, stage_num: int, filename: str) -> str | None:
        """Read a stage output file. Returns None if not found."""
        fpath = self.stage_dir(stage_num) / filename
        if not fpath.is_file():
            return None
        try:
            return fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def write_output(
        self,
        stage_num: int,
        filename: str,
        content: str,
        *,
        create_snapshot: bool = True,
    ) -> bool:
        """Write content to a stage output file.

        Creates a backup of the original if ``create_snapshot`` is True.
        Returns True on success.
        """
        d = self.stage_dir(stage_num)
        d.mkdir(parents=True, exist_ok=True)
        fpath = d / filename

        if create_snapshot and fpath.exists():
            self._snapshot(stage_num, filename)

        try:
            fpath.write_text(content, encoding="utf-8")
            return True
        except OSError as exc:
            logger.error("Failed to write %s: %s", fpath, exc)
            return False

    def restore_snapshot(self, stage_num: int, filename: str) -> bool:
        """Restore a file from its snapshot. Returns True on success."""
        snap = self._snapshot_path(stage_num, filename)
        if not snap.exists():
            return False
        target = self.stage_dir(stage_num) / filename
        try:
            shutil.copy2(snap, target)
            return True
        except OSError as exc:
            logger.error("Failed to restore snapshot: %s", exc)
            return False

    def has_snapshot(self, stage_num: int, filename: str) -> bool:
        return self._snapshot_path(stage_num, filename).exists()

    def get_diff_summary(
        self, stage_num: int, filename: str
    ) -> str | None:
        """Generate a simple diff summary between snapshot and current."""
        snap = self._snapshot_path(stage_num, filename)
        if not snap.exists():
            return None
        try:
            original = snap.read_text(encoding="utf-8")
            current = self.read_output(stage_num, filename)
            if current is None:
                return "File deleted"
            if original == current:
                return "No changes"
            orig_lines = original.splitlines()
            curr_lines = current.splitlines()
            added = len(curr_lines) - len(orig_lines)
            return (
                f"Changed: {len(orig_lines)} → {len(curr_lines)} lines "
                f"({'+'  if added >= 0 else ''}{added})"
            )
        except (OSError, UnicodeDecodeError):
            return None

    def list_versions(self, stage_num: int, filename: str) -> list[int]:
        """List available version numbers for a file."""
        prefix = f"stage_{stage_num:02d}_{filename}"
        versions = [0]  # v0 = .orig
        if not self._snapshots_dir.exists():
            return []
        for p in self._snapshots_dir.glob(f"{prefix}.v*"):
            try:
                ver = int(p.suffix[2:])  # .v1 -> 1
                versions.append(ver)
            except (ValueError, IndexError):
                pass
        if self._snapshot_path(stage_num, filename).exists():
            return sorted(versions)
        return sorted(v for v in versions if v > 0)

    def undo(self, stage_num: int, filename: str) -> bool:
        """Undo the last edit by restoring the previous version.

        Returns True if undo was successful.
        """
        versions = self.list_versions(stage_num, filename)
        if not versions:
            return False

        # Current file → save as next version before restoring
        current = self.read_output(stage_num, filename)
        if current is not None:
            next_ver = (versions[-1] if versions else 0) + 1
            self._save_version(stage_num, filename, current, next_ver)

        # Restore the latest saved version
        latest = versions[-1]
        if latest == 0:
            return self.restore_snapshot(stage_num, filename)

        ver_path = self._version_path(stage_num, filename, latest)
        if ver_path.exists():
            target = self.stage_dir(stage_num) / filename
            shutil.copy2(ver_path, target)
            return True
        return False

    def _snapshot(self, stage_num: int, filename: str) -> None:
        """Create a versioned snapshot of the current file."""
        src = self.stage_dir(stage_num) / filename
        if not src.exists():
            return
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)

        # Always save .orig for the first version
        orig_dest = self._snapshot_path(stage_num, filename)
        if not orig_dest.exists():
            shutil.copy2(src, orig_dest)
            return

        # For subsequent edits, save versioned snapshots
        versions = self.list_versions(stage_num, filename)
        next_ver = (max(versions) if versions else 0) + 1
        content = src.read_text(encoding="utf-8")
        self._save_version(stage_num, filename, content, next_ver)

    def _save_version(
        self, stage_num: int, filename: str, content: str, version: int
    ) -> None:
        """Save a specific version of a file."""
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        path = self._version_path(stage_num, filename, version)
        path.write_text(content, encoding="utf-8")

    def _snapshot_path(self, stage_num: int, filename: str) -> Path:
        return (
            self._snapshots_dir / f"stage_{stage_num:02d}_{filename}.orig"
        )

    def _version_path(
        self, stage_num: int, filename: str, version: int
    ) -> Path:
        return (
            self._snapshots_dir
            / f"stage_{stage_num:02d}_{filename}.v{version}"
        )


class StageReviewer:
    """Generate human-readable review summaries of stage outputs.

    Reads the stage output and produces a concise summary that helps
    the human quickly understand what the AI produced.
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self._editor = StageEditor(run_dir)

    def summarize_stage(self, stage_num: int) -> str:
        """Generate a summary of the stage's output."""
        files = self._editor.list_outputs(stage_num)
        if not files:
            return f"Stage {stage_num}: No outputs found."

        lines = [f"Stage {stage_num} outputs ({len(files)} files):"]
        for fname in files:
            if fname.endswith("/"):
                # Directory
                d = self._editor.stage_dir(stage_num) / fname.rstrip("/")
                count = sum(1 for _ in d.iterdir()) if d.exists() else 0
                lines.append(f"  {fname} ({count} items)")
            else:
                content = self._editor.read_output(stage_num, fname)
                if content is None:
                    lines.append(f"  {fname}: [unreadable]")
                else:
                    size = len(content)
                    line_count = content.count("\n") + 1
                    # Extract first meaningful line as preview
                    preview = ""
                    for line in content.split("\n"):
                        stripped = line.strip()
                        if stripped and not stripped.startswith(("{", "[", "#", "---")):
                            preview = stripped[:80]
                            break
                    if not preview and content.strip():
                        preview = content.strip()[:80]
                    lines.append(
                        f"  {fname}: {line_count} lines, {size} bytes"
                    )
                    if preview:
                        lines.append(f"    → {preview}")

        return "\n".join(lines)

    def summarize_json_output(
        self, stage_num: int, filename: str
    ) -> str | None:
        """Parse and summarize a JSON output file."""
        content = self._editor.read_output(stage_num, filename)
        if content is None:
            return None
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                keys = list(data.keys())[:10]
                return f"JSON object with keys: {', '.join(keys)}"
            if isinstance(data, list):
                return f"JSON array with {len(data)} items"
            return f"JSON value: {str(data)[:100]}"
        except json.JSONDecodeError:
            return "Invalid JSON"
