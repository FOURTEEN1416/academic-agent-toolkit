"""HITL persistence store: save/load all HITL state to disk."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from researchclaw.hitl.intervention import Intervention

logger = logging.getLogger(__name__)


class HITLStore:
    """Manages all HITL persistence for a single run.

    Directory layout::

        {run_dir}/hitl/
        ├── session.json              # Session state
        ├── waiting.json              # Current wait state (if any)
        ├── interventions.jsonl       # All interventions (append log)
        ├── chat_stage_07.jsonl       # Chat history per stage
        ├── chat_stage_08.jsonl
        ├── revisions_stage_08.json   # Revision history per stage
        ├── snapshots/                # Original file backups
        │   ├── stage_08_hypotheses.md.orig
        │   └── ...
        └── guidance/                 # Injected guidance files
            ├── stage_08.md
            └── ...
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.hitl_dir = run_dir / "hitl"

    def ensure_dirs(self) -> None:
        """Create HITL directory structure."""
        self.hitl_dir.mkdir(parents=True, exist_ok=True)
        (self.hitl_dir / "snapshots").mkdir(exist_ok=True)
        (self.hitl_dir / "guidance").mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Session state
    # ------------------------------------------------------------------

    def save_session(self, data: dict[str, Any]) -> None:
        self.ensure_dirs()
        (self.hitl_dir / "session.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def load_session(self) -> dict[str, Any] | None:
        path = self.hitl_dir / "session.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    # ------------------------------------------------------------------
    # Waiting state
    # ------------------------------------------------------------------

    def save_waiting(self, data: dict[str, Any]) -> None:
        self.ensure_dirs()
        (self.hitl_dir / "waiting.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def load_waiting(self) -> dict[str, Any] | None:
        path = self.hitl_dir / "waiting.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def clear_waiting(self) -> None:
        path = self.hitl_dir / "waiting.json"
        path.unlink(missing_ok=True)

    def is_waiting(self) -> bool:
        return (self.hitl_dir / "waiting.json").exists()

    # ------------------------------------------------------------------
    # Interventions log
    # ------------------------------------------------------------------

    def append_intervention(self, intervention: Intervention) -> None:
        self.ensure_dirs()
        with open(
            self.hitl_dir / "interventions.jsonl", "a", encoding="utf-8"
        ) as fh:
            fh.write(json.dumps(intervention.to_dict()) + "\n")

    def load_interventions(self) -> list[dict[str, Any]]:
        path = self.hitl_dir / "interventions.jsonl"
        if not path.exists():
            return []
        results = []
        for line in path.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return results

    def intervention_count(self) -> int:
        path = self.hitl_dir / "interventions.jsonl"
        if not path.exists():
            return 0
        return sum(
            1
            for line in path.read_text(encoding="utf-8").strip().split("\n")
            if line.strip()
        )

    # ------------------------------------------------------------------
    # Chat history
    # ------------------------------------------------------------------

    def save_chat(
        self, stage_num: int, messages: list[dict[str, Any]]
    ) -> None:
        self.ensure_dirs()
        path = self.hitl_dir / f"chat_stage_{stage_num:02d}.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for msg in messages:
                fh.write(json.dumps(msg) + "\n")

    def load_chat(self, stage_num: int) -> list[dict[str, Any]]:
        path = self.hitl_dir / f"chat_stage_{stage_num:02d}.jsonl"
        if not path.exists():
            return []
        results = []
        for line in path.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return results

    def has_chat(self, stage_num: int) -> bool:
        return (
            self.hitl_dir / f"chat_stage_{stage_num:02d}.jsonl"
        ).exists()

    # ------------------------------------------------------------------
    # Guidance
    # ------------------------------------------------------------------

    def save_guidance(self, stage_num: int, guidance: str) -> None:
        self.ensure_dirs()
        (self.hitl_dir / "guidance" / f"stage_{stage_num:02d}.md").write_text(
            guidance, encoding="utf-8"
        )

    def load_guidance(self, stage_num: int) -> str | None:
        path = self.hitl_dir / "guidance" / f"stage_{stage_num:02d}.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_summary(self) -> dict[str, Any]:
        """Return a summary of all HITL activity for this run."""
        return {
            "has_session": (self.hitl_dir / "session.json").exists(),
            "is_waiting": self.is_waiting(),
            "intervention_count": self.intervention_count(),
            "chat_stages": sorted(
                int(p.stem.split("_")[-1])
                for p in self.hitl_dir.glob("chat_stage_*.jsonl")
            )
            if self.hitl_dir.exists()
            else [],
            "guidance_stages": sorted(
                int(p.stem.split("_")[-1])
                for p in (self.hitl_dir / "guidance").glob("stage_*.md")
            )
            if (self.hitl_dir / "guidance").exists()
            else [],
            "snapshot_count": len(
                list((self.hitl_dir / "snapshots").glob("*.orig"))
            )
            if (self.hitl_dir / "snapshots").exists()
            else 0,
        }
