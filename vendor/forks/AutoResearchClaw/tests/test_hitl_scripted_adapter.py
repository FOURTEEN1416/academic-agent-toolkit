"""Tests for the ScriptedHITLAdapter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from researchclaw.hitl.adapters.scripted_adapter import ScriptedHITLAdapter
from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    PauseReason,
    WaitingState,
)


def _make_waiting(stage: int, stage_name: str = "TEST_STAGE") -> WaitingState:
    return WaitingState(
        stage=stage,
        stage_name=stage_name,
        reason=PauseReason.GATE_APPROVAL,
        context_summary="test context",
        output_files=(),
    )


@pytest.fixture
def sample_interventions() -> dict:
    return {
        "topic_id": "T01",
        "topic": "Test topic",
        "expert_profile": "Test specialist",
        "interventions": {
            "5": {
                "action": "inject",
                "message": "Fix literature",
                "guidance": "Include papers on calibration.",
            },
            "9": {
                "action": "inject",
                "message": "Fix experiment design",
                "guidance": "Use 10 seeds, not 3.",
            },
            "20": {
                "action": "reject",
                "message": "Quality gate failed",
                "guidance": "Ablation integrity broken.",
            },
        },
    }


@pytest.fixture
def interventions_file(sample_interventions: dict, tmp_path: Path) -> Path:
    fp = tmp_path / "interventions_T01.json"
    fp.write_text(json.dumps(sample_interventions), encoding="utf-8")
    return fp


class TestScriptedHITLAdapter:
    def test_from_file(self, interventions_file: Path) -> None:
        adapter = ScriptedHITLAdapter.from_file(interventions_file)
        assert adapter.topic_id == "T01"
        assert len(adapter.pending_stages) == 3
        assert sorted(adapter.pending_stages) == [5, 9, 20]

    def test_from_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            ScriptedHITLAdapter.from_file("/nonexistent/file.json")

    def test_from_dict(self, sample_interventions: dict) -> None:
        adapter = ScriptedHITLAdapter.from_dict(sample_interventions)
        assert adapter.topic_id == "T01"
        assert adapter.has_intervention(5)
        assert adapter.has_intervention(9)
        assert not adapter.has_intervention(7)

    def test_collect_input_with_intervention(
        self, interventions_file: Path
    ) -> None:
        adapter = ScriptedHITLAdapter.from_file(interventions_file)
        waiting = _make_waiting(5, "LITERATURE_SCREEN")

        result = adapter.collect_input(waiting)

        assert result.action == HumanAction.INJECT
        assert result.message == "Fix literature"
        assert "calibration" in result.guidance

    def test_collect_input_auto_approves_unscripted(
        self, interventions_file: Path
    ) -> None:
        adapter = ScriptedHITLAdapter.from_file(interventions_file)
        waiting = _make_waiting(7, "HYPOTHESIS_GEN")

        result = adapter.collect_input(waiting)

        assert result.action == HumanAction.APPROVE
        assert result.message == ""
        assert result.guidance == ""

    def test_collect_input_reject_action(
        self, interventions_file: Path
    ) -> None:
        adapter = ScriptedHITLAdapter.from_file(interventions_file)
        waiting = _make_waiting(20, "QUALITY_GATE")

        result = adapter.collect_input(waiting)

        assert result.action == HumanAction.REJECT
        assert "Quality gate" in result.message

    def test_injection_log(self, interventions_file: Path) -> None:
        adapter = ScriptedHITLAdapter.from_file(interventions_file)

        # Inject at stage 5
        adapter.collect_input(_make_waiting(5, "LITERATURE_SCREEN"))
        # Auto-approve at stage 7
        adapter.collect_input(_make_waiting(7, "HYPOTHESIS_GEN"))
        # Inject at stage 9
        adapter.collect_input(_make_waiting(9, "EXPERIMENT_DESIGN"))

        log = adapter.injection_log
        # Only scripted interventions are logged, not auto-approves
        assert len(log) == 2
        assert log[0]["stage"] == 5
        assert log[0]["action"] == "inject"
        assert log[1]["stage"] == 9

    def test_has_intervention(self, interventions_file: Path) -> None:
        adapter = ScriptedHITLAdapter.from_file(interventions_file)
        assert adapter.has_intervention(5)
        assert adapter.has_intervention(9)
        assert adapter.has_intervention(20)
        assert not adapter.has_intervention(1)
        assert not adapter.has_intervention(14)

    def test_guidance_passed_through(
        self, interventions_file: Path
    ) -> None:
        adapter = ScriptedHITLAdapter.from_file(interventions_file)
        result = adapter.collect_input(_make_waiting(9))
        assert result.guidance == "Use 10 seeds, not 3."

    def test_noop_display_methods(
        self, interventions_file: Path
    ) -> None:
        """Display methods should not raise."""
        adapter = ScriptedHITLAdapter.from_file(interventions_file)
        adapter.show_stage_output(5, "TEST", "summary")
        adapter.show_message("hello")
        adapter.show_error("oops")
        adapter.show_progress(5, 23, "TEST", "done")

    def test_full_pipeline_simulation(
        self, interventions_file: Path
    ) -> None:
        """Simulate a full pipeline run with the scripted adapter."""
        adapter = ScriptedHITLAdapter.from_file(interventions_file)

        stages = [
            (1, "TOPIC_INIT"),
            (2, "LITERATURE_SEARCH"),
            (5, "LITERATURE_SCREEN"),
            (8, "HYPOTHESIS_GEN"),
            (9, "EXPERIMENT_DESIGN"),
            (14, "RESULT_ANALYSIS"),
            (17, "PAPER_DRAFT"),
            (20, "QUALITY_GATE"),
        ]

        results = []
        for stage_num, stage_name in stages:
            result = adapter.collect_input(_make_waiting(stage_num, stage_name))
            results.append((stage_num, result.action))

        # Verify intervention pattern
        assert results[0] == (1, HumanAction.APPROVE)   # no intervention
        assert results[1] == (2, HumanAction.APPROVE)   # no intervention
        assert results[2] == (5, HumanAction.INJECT)     # has intervention
        assert results[3] == (8, HumanAction.APPROVE)   # no intervention
        assert results[4] == (9, HumanAction.INJECT)     # has intervention
        assert results[5] == (14, HumanAction.APPROVE)  # no intervention
        assert results[6] == (17, HumanAction.APPROVE)  # no intervention
        assert results[7] == (20, HumanAction.REJECT)    # has intervention


class TestInterventionFiles:
    """Validate all 10 intervention JSON files."""

    INTERVENTIONS_DIR = Path(__file__).parent.parent / "experiments" / "hitl_ablation" / "interventions"

    @pytest.mark.parametrize("topic_num", range(1, 11))
    def test_intervention_file_loads(self, topic_num: int) -> None:
        """Each intervention file should load without error."""
        fname = self.INTERVENTIONS_DIR / f"interventions_T{topic_num:02d}.json"
        if not fname.exists():
            pytest.skip(f"Intervention file not found: {fname}")

        adapter = ScriptedHITLAdapter.from_file(fname)
        assert adapter.topic_id == f"T{topic_num:02d}"
        assert len(adapter.pending_stages) >= 1

    @pytest.mark.parametrize("topic_num", range(1, 11))
    def test_intervention_file_schema(self, topic_num: int) -> None:
        """Each file should have valid schema with required fields."""
        fname = self.INTERVENTIONS_DIR / f"interventions_T{topic_num:02d}.json"
        if not fname.exists():
            pytest.skip(f"Intervention file not found: {fname}")

        data = json.loads(fname.read_text(encoding="utf-8"))

        assert "topic_id" in data
        assert "topic" in data
        assert "expert_profile" in data
        assert "interventions" in data

        for stage_str, intervention in data["interventions"].items():
            assert int(stage_str) > 0, f"Invalid stage: {stage_str}"
            assert "action" in intervention
            assert "message" in intervention
            assert "guidance" in intervention
            assert len(intervention["guidance"]) > 50, (
                f"Guidance too short for stage {stage_str}"
            )

    @pytest.mark.parametrize("topic_num", range(1, 11))
    def test_intervention_stages_cover_key_gates(self, topic_num: int) -> None:
        """Each file should cover at least the 3 key gate stages."""
        fname = self.INTERVENTIONS_DIR / f"interventions_T{topic_num:02d}.json"
        if not fname.exists():
            pytest.skip(f"Intervention file not found: {fname}")

        adapter = ScriptedHITLAdapter.from_file(fname)
        key_stages = {5, 9, 20}
        covered = key_stages.intersection(adapter.pending_stages)
        assert covered == key_stages, (
            f"T{topic_num:02d} missing gate stages: {key_stages - covered}"
        )
