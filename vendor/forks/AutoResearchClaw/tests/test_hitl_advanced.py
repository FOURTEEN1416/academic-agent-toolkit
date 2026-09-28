# pyright: basic, reportMissingImports=false, reportUnusedCallResult=false
"""Tests for advanced HITL features: file_wait, cost_guard, diff_view, checksums, hooks."""

from __future__ import annotations

import json
import time
import threading
from pathlib import Path

import pytest

from researchclaw.hitl.file_wait import (
    write_waiting,
    write_response,
    poll_for_response,
    clear_waiting,
)
from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    PauseReason,
    WaitingState,
)
from researchclaw.hitl.cost_guard import CostGuard, CostStatus
from researchclaw.hitl.diff_view import (
    unified_diff,
    side_by_side_diff,
    diff_summary,
    format_diff_stats,
    diff_from_snapshot,
)
from researchclaw.hitl.checksums import (
    compute_sha256,
    generate_manifest,
    write_manifest,
    verify_manifest,
)
from researchclaw.hitl.hooks import HookRegistry, HookResult


# ══════════════════════════════════════════════════════════════════
# File-based wait tests
# ══════════════════════════════════════════════════════════════════


class TestFileWait:
    def test_write_waiting(self, tmp_path: Path) -> None:
        ws = WaitingState(stage=8, stage_name="HYPOTHESIS_GEN", reason=PauseReason.POST_STAGE)
        hitl_dir = tmp_path / "hitl"
        path = write_waiting(hitl_dir, ws)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["stage"] == 8

    def test_write_response(self, tmp_path: Path) -> None:
        hi = HumanInput(action=HumanAction.APPROVE, message="LGTM")
        hitl_dir = tmp_path / "hitl"
        path = write_response(hitl_dir, hi)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["action"] == "approve"

    def test_poll_finds_existing_response(self, tmp_path: Path) -> None:
        hitl_dir = tmp_path / "hitl"
        write_response(hitl_dir, HumanInput(action=HumanAction.APPROVE))

        result = poll_for_response(hitl_dir, poll_interval_sec=0.1, timeout_sec=2)
        assert result.action == HumanAction.APPROVE
        # Response file should be cleaned up
        assert not (hitl_dir / "response.json").exists()

    def test_poll_with_delayed_response(self, tmp_path: Path) -> None:
        hitl_dir = tmp_path / "hitl"
        hitl_dir.mkdir(parents=True)

        # Write response after a short delay in another thread
        def delayed_write():
            time.sleep(0.3)
            write_response(hitl_dir, HumanInput(action=HumanAction.REJECT, message="bad"))

        t = threading.Thread(target=delayed_write)
        t.start()

        result = poll_for_response(hitl_dir, poll_interval_sec=0.1, timeout_sec=5)
        t.join()
        assert result.action == HumanAction.REJECT

    def test_poll_timeout_auto_proceed(self, tmp_path: Path) -> None:
        hitl_dir = tmp_path / "hitl"
        hitl_dir.mkdir(parents=True)

        result = poll_for_response(
            hitl_dir,
            poll_interval_sec=0.1,
            timeout_sec=0.3,
            auto_proceed_on_timeout=True,
        )
        assert result.action == HumanAction.APPROVE

    def test_poll_timeout_abort(self, tmp_path: Path) -> None:
        hitl_dir = tmp_path / "hitl"
        hitl_dir.mkdir(parents=True)

        result = poll_for_response(
            hitl_dir,
            poll_interval_sec=0.1,
            timeout_sec=0.3,
            auto_proceed_on_timeout=False,
        )
        assert result.action == HumanAction.ABORT

    def test_clear_waiting(self, tmp_path: Path) -> None:
        hitl_dir = tmp_path / "hitl"
        ws = WaitingState(stage=8, stage_name="X", reason=PauseReason.POST_STAGE)
        write_waiting(hitl_dir, ws)
        assert (hitl_dir / "waiting.json").exists()
        clear_waiting(hitl_dir)
        assert not (hitl_dir / "waiting.json").exists()


# ══════════════════════════════════════════════════════════════════
# Cost guard tests
# ══════════════════════════════════════════════════════════════════


class TestCostGuard:
    def test_no_budget(self) -> None:
        guard = CostGuard(budget_usd=0)
        status = guard.check()
        assert not status.over_budget
        assert status.threshold_breached == ""

    def test_under_budget(self, tmp_path: Path) -> None:
        # Write a cost log
        (tmp_path / "cost_log.jsonl").write_text(
            json.dumps({"cost_usd": 1.5}) + "\n"
            + json.dumps({"cost_usd": 0.5}) + "\n"
        )
        guard = CostGuard(budget_usd=10.0)
        status = guard.check(tmp_path)
        assert status.total_usd == 2.0
        assert not status.over_budget
        assert status.percent_used == pytest.approx(20.0)

    def test_threshold_breach(self, tmp_path: Path) -> None:
        (tmp_path / "cost_log.jsonl").write_text(
            json.dumps({"cost_usd": 6.0}) + "\n"
        )
        guard = CostGuard(budget_usd=10.0, thresholds=(0.5, 0.8, 1.0))
        status = guard.check(tmp_path)
        assert status.threshold_breached == "50%"
        assert not status.over_budget

    def test_over_budget(self, tmp_path: Path) -> None:
        (tmp_path / "cost_log.jsonl").write_text(
            json.dumps({"cost_usd": 12.0}) + "\n"
        )
        guard = CostGuard(budget_usd=10.0)
        status = guard.check(tmp_path)
        assert status.over_budget

    def test_should_pause(self, tmp_path: Path) -> None:
        (tmp_path / "cost_log.jsonl").write_text(
            json.dumps({"cost_usd": 9.0}) + "\n"
        )
        guard = CostGuard(budget_usd=10.0, thresholds=(0.5, 0.8))
        assert guard.should_pause(tmp_path)

    def test_format_display(self) -> None:
        guard = CostGuard(budget_usd=10.0)
        display = guard.format_display()
        assert "$" in display
        assert "10.00" in display


# ══════════════════════════════════════════════════════════════════
# Diff view tests
# ══════════════════════════════════════════════════════════════════


class TestDiffView:
    def test_unified_diff_identical(self) -> None:
        assert unified_diff("hello", "hello") == "No changes"

    def test_unified_diff_changed(self) -> None:
        result = unified_diff("line1\nline2", "line1\nline3")
        assert "-line2" in result
        assert "+line3" in result

    def test_side_by_side(self) -> None:
        result = side_by_side_diff("line1\nline2", "line1\nline3")
        assert "Original" in result
        assert "Modified" in result

    def test_diff_summary_stats(self) -> None:
        stats = diff_summary("a\nb\nc", "a\nd\nc\ne")
        assert stats["unchanged"] >= 1
        assert stats["added"] >= 0 or stats["changed"] >= 0

    def test_format_diff_stats(self) -> None:
        stats = {"added": 5, "deleted": 2, "changed": 1, "unchanged": 10}
        formatted = format_diff_stats(stats)
        assert "+5 added" in formatted
        assert "-2 deleted" in formatted

    def test_diff_from_snapshot(self, tmp_path: Path) -> None:
        # Create snapshot
        snapshots = tmp_path / "hitl" / "snapshots"
        snapshots.mkdir(parents=True)
        (snapshots / "stage_08_hypotheses.md.orig").write_text("original")
        # Create current
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("modified")

        result = diff_from_snapshot(tmp_path, 8, "hypotheses.md")
        assert result is not None
        assert "-original" in result
        assert "+modified" in result

    def test_diff_from_snapshot_no_snapshot(self, tmp_path: Path) -> None:
        result = diff_from_snapshot(tmp_path, 8, "hypotheses.md")
        assert result is None


# ══════════════════════════════════════════════════════════════════
# Checksums tests
# ══════════════════════════════════════════════════════════════════


class TestChecksums:
    def test_compute_sha256(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = compute_sha256(f)
        assert len(h) == 64
        # Same content → same hash
        f2 = tmp_path / "test2.txt"
        f2.write_text("hello world")
        assert compute_sha256(f2) == h

    def test_generate_manifest(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("content")
        (stage_dir / "data.json").write_text("{}")

        manifest = generate_manifest(stage_dir)
        assert "hypotheses.md" in manifest
        assert "data.json" in manifest
        assert len(manifest) == 2

    def test_write_and_verify(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("content")

        write_manifest(stage_dir)
        assert (stage_dir / "manifest.json").exists()

        # Should verify clean
        errors = verify_manifest(stage_dir)
        assert errors == []

    def test_verify_detects_changes(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("original")

        write_manifest(stage_dir)

        # Modify file
        (stage_dir / "hypotheses.md").write_text("modified")

        errors = verify_manifest(stage_dir)
        assert len(errors) == 1
        assert "Changed" in errors[0]

    def test_verify_detects_missing(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("content")

        write_manifest(stage_dir)
        (stage_dir / "hypotheses.md").unlink()

        errors = verify_manifest(stage_dir)
        assert len(errors) == 1
        assert "Missing" in errors[0]

    def test_no_manifest(self, tmp_path: Path) -> None:
        errors = verify_manifest(tmp_path)
        assert "No manifest" in errors[0]


# ══════════════════════════════════════════════════════════════════
# Hook system tests
# ══════════════════════════════════════════════════════════════════


class TestHookRegistry:
    def test_register_and_run_pre_hook(self) -> None:
        registry = HookRegistry()
        called = []
        registry.register_pre(8, lambda sn, name: called.append(sn))
        results = registry.run_pre_hooks(8, "HYPOTHESIS_GEN")
        assert len(results) == 1
        assert results[0].success
        assert called == [8]

    def test_wildcard_hook(self) -> None:
        registry = HookRegistry()
        called = []
        registry.register_post("*", lambda sn, name, status: called.append(sn))
        registry.run_post_hooks(5, "LITERATURE_SCREEN", "done")
        registry.run_post_hooks(8, "HYPOTHESIS_GEN", "done")
        assert called == [5, 8]

    def test_error_hook(self) -> None:
        registry = HookRegistry()
        called = []
        registry.register_error(lambda sn, name, err: called.append(err))
        registry.run_error_hooks(12, "EXPERIMENT_RUN", "OOM")
        assert called == ["OOM"]

    def test_hook_failure_captured(self) -> None:
        registry = HookRegistry()
        registry.register_pre(8, lambda sn, name: 1 / 0)
        results = registry.run_pre_hooks(8, "HYPOTHESIS_GEN")
        assert len(results) == 1
        assert not results[0].success
        assert "division" in results[0].error.lower()

    def test_shell_hooks(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        script = hooks_dir / "pre_stage_08.sh"
        script.write_text("#!/bin/sh\necho 'hook ran'\n")
        script.chmod(0o755)

        registry = HookRegistry(run_dir=tmp_path)
        results = registry.run_pre_hooks(8, "HYPOTHESIS_GEN")
        assert len(results) >= 1
        shell_results = [r for r in results if ".sh" in r.hook_name]
        assert len(shell_results) == 1
        assert shell_results[0].success
        assert "hook ran" in shell_results[0].output


# ══════════════════════════════════════════════════════════════════
# Editor versioned snapshots tests
# ══════════════════════════════════════════════════════════════════


class TestEditorVersionedSnapshots:
    def test_multiple_edits_create_versions(self, tmp_path: Path) -> None:
        from researchclaw.hitl.editor import StageEditor

        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("v0")

        editor = StageEditor(tmp_path)
        editor.write_output(8, "hypotheses.md", "v1")
        editor.write_output(8, "hypotheses.md", "v2")
        editor.write_output(8, "hypotheses.md", "v3")

        versions = editor.list_versions(8, "hypotheses.md")
        assert 0 in versions  # .orig
        assert len(versions) >= 2

    def test_undo_restores_previous(self, tmp_path: Path) -> None:
        from researchclaw.hitl.editor import StageEditor

        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("original")

        editor = StageEditor(tmp_path)
        editor.write_output(8, "hypotheses.md", "edited")
        assert editor.read_output(8, "hypotheses.md") == "edited"

        success = editor.undo(8, "hypotheses.md")
        assert success
