# pyright: basic, reportMissingImports=false, reportUnusedCallResult=false
"""Tests for HITL escalation policy and experiment monitor."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from researchclaw.hitl.escalation import (
    EscalationLevel,
    EscalationPolicy,
    EscalationTracker,
)
from researchclaw.hitl.tui.monitor import ExperimentMonitor


class TestEscalationLevel:
    def test_defaults(self) -> None:
        level = EscalationLevel(delay_sec=60, channel="slack")
        assert level.auto_action == ""
        assert level.message == ""


class TestEscalationPolicy:
    def test_default_policy(self) -> None:
        policy = EscalationPolicy()
        assert len(policy.levels) == 4
        assert policy.enabled

    def test_from_dict(self) -> None:
        policy = EscalationPolicy.from_dict({
            "enabled": True,
            "levels": [
                {"delay_sec": 0, "channel": "terminal"},
                {"delay_sec": 300, "channel": "slack", "auto_action": "approve"},
            ],
        })
        assert len(policy.levels) == 2
        assert policy.levels[1].auto_action == "approve"

    def test_from_empty_dict(self) -> None:
        policy = EscalationPolicy.from_dict({})
        assert len(policy.levels) == 4  # defaults


class TestEscalationTracker:
    def test_basic_tracking(self) -> None:
        policy = EscalationPolicy(levels=(
            EscalationLevel(delay_sec=0, channel="terminal"),
        ))
        tracker = EscalationTracker(policy)
        tracker.start(8, "HYPOTHESIS_GEN")

        action = tracker.check()
        assert action == ""  # No auto_action

    def test_auto_action_triggered(self) -> None:
        policy = EscalationPolicy(levels=(
            EscalationLevel(delay_sec=0, channel="terminal", auto_action="approve"),
        ))
        tracker = EscalationTracker(policy)
        tracker.start(8, "HYPOTHESIS_GEN")

        action = tracker.check()
        assert action == "approve"

    def test_delayed_escalation(self) -> None:
        policy = EscalationPolicy(levels=(
            EscalationLevel(delay_sec=0, channel="terminal"),
            EscalationLevel(delay_sec=999999, channel="slack"),
        ))
        tracker = EscalationTracker(policy)
        tracker.start(8, "HYPOTHESIS_GEN")

        # First check triggers level 0
        tracker.check()
        # Second check should not trigger level 1 (not enough time)
        action = tracker.check()
        assert action == ""

    def test_no_duplicate_triggers(self) -> None:
        notified = []

        def mock_notify(**kwargs):
            notified.append(kwargs)

        policy = EscalationPolicy(levels=(
            EscalationLevel(delay_sec=0, channel="terminal"),
        ))
        tracker = EscalationTracker(policy, notify_callback=mock_notify)
        tracker.start(8, "HYPOTHESIS_GEN")

        tracker.check()
        tracker.check()
        tracker.check()
        # Should only notify once
        assert len(notified) == 1

    def test_stop_resets(self) -> None:
        policy = EscalationPolicy(levels=(
            EscalationLevel(delay_sec=0, channel="terminal"),
        ))
        tracker = EscalationTracker(policy)
        tracker.start(8, "TEST")
        tracker.check()
        tracker.stop()
        assert tracker.elapsed_sec == 0.0
        assert tracker.check() == ""

    def test_elapsed_and_next(self) -> None:
        policy = EscalationPolicy(levels=(
            EscalationLevel(delay_sec=0, channel="terminal"),
            EscalationLevel(delay_sec=300, channel="slack"),
        ))
        tracker = EscalationTracker(policy)
        tracker.start(8, "TEST")
        time.sleep(0.05)

        assert tracker.elapsed_sec > 0
        tracker.check()  # Trigger level 0
        next_sec = tracker.next_escalation_sec
        assert next_sec is not None
        assert next_sec > 200  # Should be about 300 minus elapsed

    def test_disabled_policy(self) -> None:
        policy = EscalationPolicy(
            levels=(EscalationLevel(delay_sec=0, channel="terminal", auto_action="abort"),),
            enabled=False,
        )
        tracker = EscalationTracker(policy)
        tracker.start(8, "TEST")
        assert tracker.check() == ""

    def test_notify_callback_error_handled(self) -> None:
        def broken_notify(**kwargs):
            raise RuntimeError("Notify failed")

        policy = EscalationPolicy(levels=(
            EscalationLevel(delay_sec=0, channel="terminal"),
        ))
        tracker = EscalationTracker(policy, notify_callback=broken_notify)
        tracker.start(8, "TEST")
        # Should not raise
        tracker.check()


class TestExperimentMonitor:
    def test_empty_monitor(self, tmp_path: Path) -> None:
        monitor = ExperimentMonitor(tmp_path)
        status = monitor.get_experiment_status()
        assert status["runs"] == []
        assert status["progress"] == 0.0

    def test_with_runs(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "stage-12" / "runs"
        runs_dir.mkdir(parents=True)
        (runs_dir / "run_001.json").write_text(json.dumps({
            "run_id": "1", "metrics": {"loss": 0.5, "accuracy": 0.75},
        }))
        (runs_dir / "run_002.json").write_text(json.dumps({
            "run_id": "2", "metrics": {"loss": 0.3, "accuracy": 0.82},
        }))

        monitor = ExperimentMonitor(tmp_path)
        status = monitor.get_experiment_status()
        assert len(status["runs"]) == 2
        assert status["current_metrics"]["accuracy"] == 0.82
        assert status["best_metrics"]["accuracy"] == 0.82

    def test_format_metrics_table(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "stage-12" / "runs"
        runs_dir.mkdir(parents=True)
        (runs_dir / "run_001.json").write_text(json.dumps({
            "run_id": "1", "metrics": {"loss": 0.5},
        }))

        monitor = ExperimentMonitor(tmp_path)
        table = monitor.format_metrics_table()
        assert "loss" in table
        assert "0.5" in table

    def test_no_data_message(self, tmp_path: Path) -> None:
        monitor = ExperimentMonitor(tmp_path)
        table = monitor.format_metrics_table()
        assert "No experiment data" in table

    def test_trend_detection(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "stage-12" / "runs"
        runs_dir.mkdir(parents=True)
        (runs_dir / "run_001.json").write_text(json.dumps({
            "metrics": {"loss": 0.5},
        }))

        monitor = ExperimentMonitor(tmp_path)
        # First call — no trend
        monitor.format_metrics_table()
        # Update the data
        (runs_dir / "run_001.json").write_text(json.dumps({
            "metrics": {"loss": 0.3},
        }))
        # Second call — should detect downward trend
        table = monitor.format_metrics_table()
        assert "↓" in table
