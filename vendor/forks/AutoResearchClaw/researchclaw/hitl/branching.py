"""Pipeline branching: explore multiple research paths in parallel.

When a human is reviewing hypotheses at Stage 8, they might want to
explore 2-3 promising directions simultaneously rather than committing
to one. This module supports:

1. **Branch creation** — fork the pipeline at any stage
2. **Parallel execution** — run branches independently
3. **Branch comparison** — compare outputs across branches
4. **Branch merging** — select the best branch to continue

This is a unique differentiator — no competing research automation
system supports branched exploration with human-guided selection.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Branch:
    """A pipeline execution branch."""

    branch_id: str
    parent_branch: str = "main"
    fork_stage: int = 0
    fork_stage_name: str = ""
    description: str = ""
    status: str = "active"  # active | completed | abandoned | merged
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
    )
    branch_dir: str = ""
    last_completed_stage: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "parent_branch": self.parent_branch,
            "fork_stage": self.fork_stage,
            "fork_stage_name": self.fork_stage_name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "branch_dir": self.branch_dir,
            "last_completed_stage": self.last_completed_stage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Branch:
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


@dataclass
class BranchComparison:
    """Comparison of outputs across branches."""

    stage: int
    stage_name: str
    branches: dict[str, dict[str, Any]]  # branch_id -> {artifacts, quality, summary}

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "stage_name": self.stage_name,
            "branches": self.branches,
        }


class BranchManager:
    """Manage pipeline branches for parallel exploration.

    Usage:
    1. Call ``create_branch()`` at a decision point (e.g., Stage 8)
    2. Each branch gets its own run_dir copy (stages up to fork are shared)
    3. Call ``compare_branches()`` to see outputs side by side
    4. Call ``merge_branch()`` to select the winner and continue
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.branches_dir = run_dir / "branches"
        self._branches: dict[str, Branch] = {}
        self._load_branches()

    def create_branch(
        self,
        branch_id: str,
        fork_stage: int,
        fork_stage_name: str = "",
        description: str = "",
    ) -> Branch:
        """Create a new branch by copying the pipeline state.

        Copies all stage directories up to and including ``fork_stage``
        into a new branch directory. Subsequent stages will execute
        independently in the branch.
        """
        branch_dir = self.branches_dir / branch_id
        branch_dir.mkdir(parents=True, exist_ok=True)

        # Copy all stages up to fork_stage
        for stage_num in range(1, fork_stage + 1):
            src = self.run_dir / f"stage-{stage_num:02d}"
            dst = branch_dir / f"stage-{stage_num:02d}"
            if src.is_dir() and not dst.exists():
                shutil.copytree(src, dst)

        # Copy checkpoint
        cp_src = self.run_dir / "checkpoint.json"
        if cp_src.exists():
            shutil.copy2(cp_src, branch_dir / "checkpoint.json")

        branch = Branch(
            branch_id=branch_id,
            fork_stage=fork_stage,
            fork_stage_name=fork_stage_name,
            description=description,
            branch_dir=str(branch_dir),
        )
        self._branches[branch_id] = branch
        self._save_branches()

        logger.info(
            "Created branch '%s' from stage %d (%s)",
            branch_id, fork_stage, fork_stage_name,
        )
        return branch

    def list_branches(self) -> list[Branch]:
        """List all branches."""
        return list(self._branches.values())

    def get_branch(self, branch_id: str) -> Branch | None:
        return self._branches.get(branch_id)

    def get_branch_dir(self, branch_id: str) -> Path | None:
        """Get the run directory for a branch."""
        branch = self._branches.get(branch_id)
        if branch is None:
            return None
        return Path(branch.branch_dir)

    def compare_branches(
        self, stage: int, stage_name: str = ""
    ) -> BranchComparison:
        """Compare outputs of all active branches at a specific stage.

        Returns a BranchComparison with side-by-side summaries.
        """
        branch_data: dict[str, dict[str, Any]] = {}

        # Include main branch
        main_stage = self.run_dir / f"stage-{stage:02d}"
        if main_stage.is_dir():
            branch_data["main"] = self._summarize_stage_dir(main_stage)

        # Include all active branches
        for branch_id, branch in self._branches.items():
            if branch.status != "active":
                continue
            stage_dir = Path(branch.branch_dir) / f"stage-{stage:02d}"
            if stage_dir.is_dir():
                branch_data[branch_id] = self._summarize_stage_dir(stage_dir)

        return BranchComparison(
            stage=stage,
            stage_name=stage_name,
            branches=branch_data,
        )

    def merge_branch(self, branch_id: str, from_stage: int) -> bool:
        """Merge a branch back into the main pipeline.

        Copies all stage outputs from ``from_stage`` onward from the
        branch into the main run directory, replacing existing outputs.
        """
        branch = self._branches.get(branch_id)
        if branch is None:
            return False

        branch_dir = Path(branch.branch_dir)
        if not branch_dir.is_dir():
            return False

        for stage_dir in sorted(branch_dir.glob("stage-*")):
            if not stage_dir.is_dir():
                continue
            try:
                stage_num = int(stage_dir.name.split("-")[1])
            except (ValueError, IndexError):
                continue

            if stage_num >= from_stage:
                dest = self.run_dir / stage_dir.name
                if dest.exists():
                    # Backup existing
                    backup = self.run_dir / f"{stage_dir.name}.pre-merge"
                    if not backup.exists():
                        dest.rename(backup)
                    else:
                        shutil.rmtree(dest)
                shutil.copytree(stage_dir, dest)

        branch.status = "merged"
        self._save_branches()

        logger.info(
            "Merged branch '%s' from stage %d into main",
            branch_id, from_stage,
        )
        return True

    def abandon_branch(self, branch_id: str) -> bool:
        """Mark a branch as abandoned."""
        branch = self._branches.get(branch_id)
        if branch is None:
            return False
        branch.status = "abandoned"
        self._save_branches()
        return True

    def _summarize_stage_dir(self, stage_dir: Path) -> dict[str, Any]:
        """Create a summary of a stage directory's outputs."""
        artifacts = []
        for f in sorted(stage_dir.iterdir()):
            if f.name.startswith(".") or f.name in ("stage_health.json", "manifest.json"):
                continue
            info: dict[str, Any] = {"name": f.name, "is_dir": f.is_dir()}
            if f.is_file():
                info["size"] = f.stat().st_size
                # Read first 200 chars as preview
                try:
                    preview = f.read_text(encoding="utf-8")[:200]
                    info["preview"] = preview
                except (OSError, UnicodeDecodeError):
                    pass
            artifacts.append(info)

        # Read quality score if available
        quality = None
        prm_file = stage_dir / "prm_score.json"
        if prm_file.exists():
            try:
                quality = json.loads(prm_file.read_text(encoding="utf-8")).get("prm_score")
            except (json.JSONDecodeError, OSError):
                pass

        return {
            "artifacts": artifacts,
            "quality_score": quality,
            "artifact_count": len(artifacts),
        }

    def _save_branches(self) -> None:
        self.branches_dir.mkdir(parents=True, exist_ok=True)
        data = {
            bid: b.to_dict() for bid, b in self._branches.items()
        }
        (self.branches_dir / "branches.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _load_branches(self) -> None:
        path = self.branches_dir / "branches.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for bid, bdata in data.items():
                self._branches[bid] = Branch.from_dict(bdata)
        except (json.JSONDecodeError, OSError):
            pass
