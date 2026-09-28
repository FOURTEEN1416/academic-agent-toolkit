# pyright: basic, reportMissingImports=false, reportUnusedCallResult=false
"""Tests for HITL intelligence layer: smart pause, learning, summarizer, quality predictor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from researchclaw.hitl.smart_pause import ConfidenceSignal, SmartPause
from researchclaw.hitl.learning import InterventionLearner, InterventionStats
from researchclaw.hitl.summarizer import generate_pause_summary
from researchclaw.hitl.quality_predictor import QualityPredictor, QualityPrediction
from researchclaw.hitl.presets import get_preset, list_presets
from researchclaw.hitl.notify import NotificationManager, Notification


# ══════════════════════════════════════════════════════════════════
# SmartPause tests
# ══════════════════════════════════════════════════════════════════


class TestConfidenceSignal:
    def test_overall_confidence(self) -> None:
        signal = ConfidenceSignal(
            stage=8,
            stage_name="HYPOTHESIS_GEN",
            quality_score=0.9,
            confidence_score=0.8,
        )
        assert 0.0 <= signal.overall_confidence <= 1.0

    def test_low_quality_lowers_confidence(self) -> None:
        high = ConfidenceSignal(stage=8, stage_name="X", quality_score=1.0)
        low = ConfidenceSignal(stage=8, stage_name="X", quality_score=0.1)
        assert high.overall_confidence > low.overall_confidence

    def test_high_criticality_lowers_confidence(self) -> None:
        low_crit = ConfidenceSignal(stage=8, stage_name="X", criticality=0.1)
        high_crit = ConfidenceSignal(stage=8, stage_name="X", criticality=0.9)
        assert low_crit.overall_confidence > high_crit.overall_confidence

    def test_to_dict(self) -> None:
        signal = ConfidenceSignal(stage=8, stage_name="TEST")
        data = signal.to_dict()
        assert "overall_confidence" in data
        assert data["stage"] == 8


class TestSmartPause:
    def test_high_confidence_no_pause(self) -> None:
        sp = SmartPause(threshold=0.5)
        should, signal = sp.should_pause(
            4, "LITERATURE_COLLECT",
            quality_score=0.9,
            confidence_score=0.9,
        )
        assert not should

    def test_low_quality_triggers_pause(self) -> None:
        sp = SmartPause(threshold=0.7)
        should, signal = sp.should_pause(
            8, "HYPOTHESIS_GEN",
            quality_score=0.2,
            confidence_score=0.3,
        )
        assert should

    def test_critical_stage_more_likely_to_pause(self) -> None:
        sp = SmartPause(threshold=0.6)
        # Stage 8 (high criticality) vs stage 21 (low criticality)
        should_8, _ = sp.should_pause(8, "HYPOTHESIS_GEN", quality_score=0.7)
        should_21, _ = sp.should_pause(21, "KNOWLEDGE_ARCHIVE", quality_score=0.7)
        # Stage 8 should be more likely to pause
        assert should_8 or not should_21

    def test_historical_rejection_rate(self, tmp_path: Path) -> None:
        # Write fake intervention log
        hitl_dir = tmp_path / "hitl"
        hitl_dir.mkdir(parents=True)
        with open(hitl_dir / "interventions.jsonl", "w") as f:
            f.write(json.dumps({"stage": 8, "type": "reject"}) + "\n")
            f.write(json.dumps({"stage": 8, "type": "reject"}) + "\n")
            f.write(json.dumps({"stage": 8, "type": "approve"}) + "\n")

        sp = SmartPause(threshold=0.7, run_dir=tmp_path)
        rate = sp._get_rejection_rate(8)
        assert abs(rate - 2 / 3) < 0.01

    def test_get_report(self) -> None:
        sp = SmartPause()
        sp.should_pause(1, "TOPIC_INIT")
        sp.should_pause(2, "PROBLEM_DECOMPOSE")
        report = sp.get_report()
        assert len(report) == 2


# ══════════════════════════════════════════════════════════════════
# InterventionLearner tests
# ══════════════════════════════════════════════════════════════════


class TestInterventionStats:
    def test_approval_rate(self) -> None:
        stats = InterventionStats(
            stage=8, approval_count=7, rejection_count=3
        )
        assert abs(stats.approval_rate - 0.7) < 0.01

    def test_intervention_rate(self) -> None:
        stats = InterventionStats(
            stage=8, total_runs=10, edit_count=3, rejection_count=2
        )
        assert abs(stats.intervention_rate - 0.5) < 0.01

    def test_zero_division(self) -> None:
        stats = InterventionStats(stage=8)
        assert stats.approval_rate == 1.0
        assert stats.intervention_rate == 0.0


class TestInterventionLearner:
    def _create_run(self, artifacts_dir: Path, run_name: str, interventions: list) -> None:
        run_dir = artifacts_dir / run_name / "hitl"
        run_dir.mkdir(parents=True)
        with open(run_dir / "interventions.jsonl", "w") as f:
            for iv in interventions:
                f.write(json.dumps(iv) + "\n")

    def test_analyze_history(self, tmp_path: Path) -> None:
        self._create_run(tmp_path, "run1", [
            {"stage": 8, "stage_name": "HYPOTHESIS_GEN", "type": "approve"},
            {"stage": 8, "stage_name": "HYPOTHESIS_GEN", "type": "reject"},
            {"stage": 9, "stage_name": "EXPERIMENT_DESIGN", "type": "edit_output"},
        ])
        self._create_run(tmp_path, "run2", [
            {"stage": 8, "stage_name": "HYPOTHESIS_GEN", "type": "approve"},
        ])

        learner = InterventionLearner(tmp_path)
        stats = learner.analyze_history()
        assert 8 in stats
        assert stats[8].total_runs == 3
        assert stats[8].approval_count == 2
        assert stats[8].rejection_count == 1

    def test_recommend_thresholds(self, tmp_path: Path) -> None:
        self._create_run(tmp_path, "run1", [
            {"stage": 8, "type": "reject"},
            {"stage": 8, "type": "reject"},
            {"stage": 8, "type": "reject"},
            {"stage": 9, "type": "approve"},
            {"stage": 9, "type": "approve"},
            {"stage": 9, "type": "approve"},
        ])

        learner = InterventionLearner(tmp_path)
        thresholds = learner.recommend_thresholds()
        # Stage 8 (high rejection) should have lower threshold
        # Stage 9 (high approval) should have higher threshold
        assert thresholds[8] < thresholds[9]

    def test_get_report(self, tmp_path: Path) -> None:
        self._create_run(tmp_path, "run1", [
            {"stage": 8, "type": "reject"},
        ])
        learner = InterventionLearner(tmp_path)
        report = learner.get_report()
        assert "Learning Report" in report

    def test_empty_history(self, tmp_path: Path) -> None:
        learner = InterventionLearner(tmp_path)
        report = learner.get_report()
        assert "No historical data" in report

    def test_save(self, tmp_path: Path) -> None:
        self._create_run(tmp_path, "run1", [
            {"stage": 8, "type": "approve"},
        ])
        learner = InterventionLearner(tmp_path)
        learner.analyze_history()
        save_path = tmp_path / "learning.json"
        learner.save(save_path)
        assert save_path.exists()


# ══════════════════════════════════════════════════════════════════
# Summarizer tests
# ══════════════════════════════════════════════════════════════════


class TestSummarizer:
    def test_basic_summary(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("# Hypothesis\nContent")

        summary = generate_pause_summary(8, "HYPOTHESIS_GEN", tmp_path)
        assert "HYPOTHESIS_GEN" in summary
        assert "hypotheses.md" in summary

    def test_error_summary(self, tmp_path: Path) -> None:
        summary = generate_pause_summary(
            12, "EXPERIMENT_RUN", tmp_path, error="OOM killed"
        )
        assert "ERROR" in summary
        assert "OOM" in summary

    def test_with_quality_score(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "prm_score.json").write_text(
            json.dumps({"prm_score": 0.85})
        )
        summary = generate_pause_summary(8, "HYPOTHESIS_GEN", tmp_path)
        assert "0.85" in summary


# ══════════════════════════════════════════════════════════════════
# QualityPredictor tests
# ══════════════════════════════════════════════════════════════════


class TestQualityPredictor:
    def test_empty_run(self, tmp_path: Path) -> None:
        predictor = QualityPredictor(tmp_path)
        prediction = predictor.predict()
        # No artifacts → low/default quality
        assert isinstance(prediction, QualityPrediction)

    def test_with_literature(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-05"
        stage_dir.mkdir()
        lines = [json.dumps({"title": f"Paper {i}"}) for i in range(15)]
        (stage_dir / "shortlist.jsonl").write_text("\n".join(lines))

        predictor = QualityPredictor(tmp_path)
        prediction = predictor.predict(current_stage=5)
        assert prediction.component_scores.get("literature", 0) > 0

    def test_with_draft(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-17"
        stage_dir.mkdir()
        # Write a decent-length draft
        content = (
            "## Introduction\n" + "word " * 2000 + "\n"
            "## Method\n" + "word " * 1000 + "\n"
            "## Experiments\n" + "word " * 1000 + "\n"
            "## Results\n" + "word " * 500 + "\n"
            "## Conclusion\n" + "word " * 500 + "\n"
        )
        (stage_dir / "paper_draft.md").write_text(content)

        predictor = QualityPredictor(tmp_path)
        prediction = predictor.predict(current_stage=17)
        assert prediction.component_scores.get("draft", 0) >= 6.0

    def test_risk_factors(self, tmp_path: Path) -> None:
        # Empty stage-09 → no experiment design
        predictor = QualityPredictor(tmp_path)
        prediction = predictor.predict(current_stage=9)
        assert any("No experiment design" in r for r in prediction.risk_factors)


# ══════════════════════════════════════════════════════════════════
# Presets tests
# ══════════════════════════════════════════════════════════════════


class TestPresets:
    def test_list_presets(self) -> None:
        presets = list_presets()
        assert "co-pilot" in presets
        assert "express" in presets

    def test_get_copilot(self) -> None:
        config = get_preset("co-pilot")
        assert config is not None
        assert config.enabled is True
        assert config.mode == "co-pilot"

    def test_get_express(self) -> None:
        config = get_preset("express")
        assert config is not None
        assert config.stage_policies.get(8) is not None

    def test_get_nonexistent(self) -> None:
        assert get_preset("nonexistent") is None


# ══════════════════════════════════════════════════════════════════
# Notification tests
# ══════════════════════════════════════════════════════════════════


class TestNotificationManager:
    def test_notify_pause(self, tmp_path: Path, capsys) -> None:
        mgr = NotificationManager(channels=("terminal",), run_dir=tmp_path)
        mgr.notify_pause(8, "HYPOTHESIS_GEN", "post-stage review")
        captured = capsys.readouterr()
        assert "paused" in captured.out.lower()
        assert len(mgr.history) == 1

    def test_notify_error(self, tmp_path: Path, capsys) -> None:
        mgr = NotificationManager(channels=("terminal",), run_dir=tmp_path)
        mgr.notify_error(12, "EXPERIMENT_RUN", "OOM killed")
        captured = capsys.readouterr()
        assert "OOM" in captured.out

    def test_persistence(self, tmp_path: Path) -> None:
        mgr = NotificationManager(channels=("terminal",), run_dir=tmp_path)
        mgr.notify_complete("rc-test", 23)
        log_path = tmp_path / "hitl" / "notifications.jsonl"
        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
