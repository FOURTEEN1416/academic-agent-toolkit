# pyright: basic, reportMissingImports=false, reportUnusedCallResult=false
"""Tests for HITL branching and context management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from researchclaw.hitl.branching import Branch, BranchManager, BranchComparison
from researchclaw.hitl.context_manager import ContextManager


# ══════════════════════════════════════════════════════════════════
# Branching tests
# ══════════════════════════════════════════════════════════════════


class TestBranch:
    def test_serialize_roundtrip(self) -> None:
        b = Branch(branch_id="explore-1", fork_stage=8, description="Try quantum approach")
        data = b.to_dict()
        restored = Branch.from_dict(data)
        assert restored.branch_id == "explore-1"
        assert restored.fork_stage == 8


class TestBranchManager:
    def _setup_pipeline(self, run_dir: Path, stages: int = 10) -> None:
        """Create fake stage directories."""
        for i in range(1, stages + 1):
            stage_dir = run_dir / f"stage-{i:02d}"
            stage_dir.mkdir(parents=True)
            (stage_dir / "output.md").write_text(f"Stage {i} output")
        (run_dir / "checkpoint.json").write_text(
            json.dumps({"last_completed_stage": stages, "run_id": "test"})
        )

    def test_create_branch(self, tmp_path: Path) -> None:
        self._setup_pipeline(tmp_path, stages=8)
        mgr = BranchManager(tmp_path)

        branch = mgr.create_branch(
            "quantum", fork_stage=8, description="Quantum regularization"
        )
        assert branch.branch_id == "quantum"
        assert branch.fork_stage == 8
        assert branch.status == "active"

        # Branch dir should have stages 1-8
        branch_dir = Path(branch.branch_dir)
        assert (branch_dir / "stage-08" / "output.md").exists()
        assert (branch_dir / "stage-01" / "output.md").exists()

    def test_list_branches(self, tmp_path: Path) -> None:
        self._setup_pipeline(tmp_path, stages=8)
        mgr = BranchManager(tmp_path)

        mgr.create_branch("branch-a", fork_stage=8)
        mgr.create_branch("branch-b", fork_stage=8)

        branches = mgr.list_branches()
        assert len(branches) == 2

    def test_compare_branches(self, tmp_path: Path) -> None:
        self._setup_pipeline(tmp_path, stages=8)
        mgr = BranchManager(tmp_path)

        branch = mgr.create_branch("alt", fork_stage=8)
        # Modify the branch's stage 8
        branch_dir = Path(branch.branch_dir)
        (branch_dir / "stage-08" / "output.md").write_text("Alternative output")

        comparison = mgr.compare_branches(8, "HYPOTHESIS_GEN")
        assert "main" in comparison.branches
        assert "alt" in comparison.branches
        # Check previews differ
        main_preview = comparison.branches["main"]["artifacts"][0].get("preview", "")
        alt_preview = comparison.branches["alt"]["artifacts"][0].get("preview", "")
        assert main_preview != alt_preview

    def test_merge_branch(self, tmp_path: Path) -> None:
        self._setup_pipeline(tmp_path, stages=10)
        mgr = BranchManager(tmp_path)

        branch = mgr.create_branch("better", fork_stage=8)
        branch_dir = Path(branch.branch_dir)
        # Add stage 9 to branch
        (branch_dir / "stage-09").mkdir()
        (branch_dir / "stage-09" / "plan.yaml").write_text("better plan")

        success = mgr.merge_branch("better", from_stage=9)
        assert success
        # Main should now have the branch's stage 9
        assert (tmp_path / "stage-09" / "plan.yaml").read_text() == "better plan"

        # Branch status should be merged
        b = mgr.get_branch("better")
        assert b is not None
        assert b.status == "merged"

    def test_abandon_branch(self, tmp_path: Path) -> None:
        self._setup_pipeline(tmp_path, stages=8)
        mgr = BranchManager(tmp_path)

        mgr.create_branch("doomed", fork_stage=8)
        success = mgr.abandon_branch("doomed")
        assert success

        b = mgr.get_branch("doomed")
        assert b is not None
        assert b.status == "abandoned"

    def test_persistence(self, tmp_path: Path) -> None:
        self._setup_pipeline(tmp_path, stages=8)
        mgr1 = BranchManager(tmp_path)
        mgr1.create_branch("persistent", fork_stage=8)

        # Reload
        mgr2 = BranchManager(tmp_path)
        branches = mgr2.list_branches()
        assert len(branches) == 1
        assert branches[0].branch_id == "persistent"

    def test_get_branch_dir(self, tmp_path: Path) -> None:
        self._setup_pipeline(tmp_path, stages=8)
        mgr = BranchManager(tmp_path)
        mgr.create_branch("test", fork_stage=8)

        d = mgr.get_branch_dir("test")
        assert d is not None
        assert d.is_dir()

        assert mgr.get_branch_dir("nonexistent") is None


# ══════════════════════════════════════════════════════════════════
# Context manager tests
# ══════════════════════════════════════════════════════════════════


class TestContextManager:
    def test_build_basic_context(self, tmp_path: Path) -> None:
        cm = ContextManager(tmp_path)
        messages = cm.build_context(8, "HYPOTHESIS_GEN", "ML research")
        assert len(messages) >= 1
        assert messages[0]["role"] == "system"
        assert "HYPOTHESIS_GEN" in messages[0]["content"]

    def test_includes_stage_output(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("# Hypothesis 1\nQuantum regularization")

        cm = ContextManager(tmp_path)
        messages = cm.build_context(
            8, "HYPOTHESIS_GEN", "ML",
            focus_artifacts=("hypotheses.md",),
        )
        combined = " ".join(m["content"] for m in messages)
        assert "Quantum" in combined

    def test_includes_guidance(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hitl_guidance.md").write_text("Focus on NLP tasks")

        cm = ContextManager(tmp_path)
        messages = cm.build_context(8, "HYPOTHESIS_GEN", "ML")
        combined = " ".join(m["content"] for m in messages)
        assert "NLP" in combined

    def test_cross_stage_context(self, tmp_path: Path) -> None:
        s7 = tmp_path / "stage-07"
        s7.mkdir()
        (s7 / "synthesis.md").write_text("# Synthesis\nGap: no robust evaluation")

        cm = ContextManager(tmp_path)
        messages = cm.build_context(
            8, "HYPOTHESIS_GEN", "ML",
            cross_stage_refs=(7,),
        )
        combined = " ".join(m["content"] for m in messages)
        assert "robust" in combined.lower()

    def test_chat_history_trimming(self, tmp_path: Path) -> None:
        cm = ContextManager(tmp_path, max_total_chars=2000)
        long_history = [
            {"role": "user", "content": f"Message {i} " * 100}
            for i in range(20)
        ]
        messages = cm.build_context(
            8, "HYPOTHESIS_GEN", "ML",
            chat_messages=long_history,
        )
        # Should include system + trimmed history, not all 20 messages
        total_chars = sum(len(m["content"]) for m in messages)
        assert total_chars <= 2500  # Some buffer

    def test_summarize_short_artifact(self, tmp_path: Path) -> None:
        cm = ContextManager(tmp_path)
        result = cm.summarize_artifact("Short text", max_chars=1000)
        assert result == "Short text"

    def test_summarize_long_artifact(self, tmp_path: Path) -> None:
        cm = ContextManager(tmp_path)
        long_text = (
            "# Introduction\n"
            "This is the introduction section with important findings.\n"
            "The results show significant improvement.\n"
            + "Filler text. " * 500
            + "\n# Conclusion\nThe hypothesis is confirmed.\n"
        )
        result = cm.summarize_artifact(long_text, max_chars=500)
        assert len(result) <= 600  # Some overhead for stats
        assert "Introduction" in result


class TestBranchComparison:
    def test_to_dict(self) -> None:
        comp = BranchComparison(
            stage=8,
            stage_name="HYPOTHESIS_GEN",
            branches={
                "main": {"artifacts": [], "quality_score": 0.8},
                "alt": {"artifacts": [], "quality_score": 0.9},
            },
        )
        data = comp.to_dict()
        assert data["stage"] == 8
        assert len(data["branches"]) == 2
