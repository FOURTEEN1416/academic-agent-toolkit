# pyright: basic, reportMissingImports=false, reportUnusedCallResult=false
"""Integration tests for HITL: CLI commands, executor hooks, checkpoint enhancement."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from researchclaw.adapters import AdapterBundle
from researchclaw.hitl.config import HITLConfig
from researchclaw.hitl.intervention import HumanAction, HumanInput, PauseReason
from researchclaw.hitl.session import HITLSession, SessionState


# ══════════════════════════════════════════════════════════════════
# CLI integration tests
# ══════════════════════════════════════════════════════════════════


class TestCLICommands:
    def test_status_command(self, tmp_path: Path) -> None:
        """Test `researchclaw status <run_dir>` command."""
        from researchclaw.cli import main

        # Create minimal run directory
        (tmp_path / "hitl").mkdir(parents=True)
        (tmp_path / "hitl" / "session.json").write_text(
            json.dumps({"mode": "co-pilot", "interventions_count": 2})
        )
        # Should not crash
        result = main(["status", str(tmp_path)])
        assert result == 0

    def test_approve_command(self, tmp_path: Path) -> None:
        """Test `researchclaw approve <run_dir>` command."""
        from researchclaw.cli import main

        result = main(["approve", str(tmp_path), "--message", "Looks good"])
        assert result == 0
        response = json.loads(
            (tmp_path / "hitl" / "response.json").read_text()
        )
        assert response["action"] == "approve"
        assert response["message"] == "Looks good"

    def test_reject_command(self, tmp_path: Path) -> None:
        """Test `researchclaw reject <run_dir>` command."""
        from researchclaw.cli import main

        result = main(["reject", str(tmp_path), "--reason", "Missing baseline"])
        assert result == 0
        response = json.loads(
            (tmp_path / "hitl" / "response.json").read_text()
        )
        assert response["action"] == "reject"
        assert response["message"] == "Missing baseline"

    def test_guide_command(self, tmp_path: Path) -> None:
        """Test `researchclaw guide <run_dir> --stage 8 --message '...'`."""
        from researchclaw.cli import main

        result = main([
            "guide", str(tmp_path),
            "--stage", "8",
            "--message", "Focus on transformer architectures",
        ])
        assert result == 0
        # Check guidance was saved in both locations
        assert (tmp_path / "hitl" / "guidance" / "stage_08.md").exists()
        assert (tmp_path / "stage-08" / "hitl_guidance.md").exists()
        content = (tmp_path / "stage-08" / "hitl_guidance.md").read_text()
        assert "transformer" in content

    def test_attach_no_waiting(self, tmp_path: Path) -> None:
        """Test attach when pipeline is not waiting."""
        from researchclaw.cli import main

        (tmp_path / "hitl").mkdir(parents=True)
        result = main(["attach", str(tmp_path)])
        assert result == 0


# ══════════════════════════════════════════════════════════════════
# Executor HITL hook tests
# ══════════════════════════════════════════════════════════════════


class TestExecutorHITLHooks:
    def test_pre_stage_hook_skips_when_no_hitl(self, tmp_path: Path) -> None:
        """Pre-stage hook returns None when HITL is not configured."""
        from researchclaw.pipeline.executor import _run_hitl_pre_stage
        from researchclaw.pipeline.stages import Stage

        adapters = AdapterBundle()  # hitl=None
        result = _run_hitl_pre_stage(Stage.TOPIC_INIT, tmp_path, adapters)
        assert result is None

    def test_pre_stage_hook_pauses(self, tmp_path: Path) -> None:
        """Pre-stage hook pauses when policy requires."""
        from researchclaw.pipeline.executor import _run_hitl_pre_stage
        from researchclaw.pipeline.stages import Stage

        config = HITLConfig.from_dict({
            "enabled": True,
            "mode": "custom",
            "stage_policies": {
                "1": {"pause_before": True},
            },
        })
        session = HITLSession(config=config, run_dir=tmp_path)
        session.set_input_callback(
            lambda _: HumanInput(action=HumanAction.APPROVE)
        )
        adapters = AdapterBundle(hitl=session)

        result = _run_hitl_pre_stage(Stage.TOPIC_INIT, tmp_path, adapters)
        assert result is None  # Approve → proceed normally
        assert session.interventions_count == 1

    def test_pre_stage_hook_skip(self, tmp_path: Path) -> None:
        """Pre-stage hook can skip a stage."""
        from researchclaw.pipeline.executor import _run_hitl_pre_stage
        from researchclaw.pipeline.stages import Stage, StageStatus

        config = HITLConfig.from_dict({
            "enabled": True,
            "mode": "custom",
            "stage_policies": {
                "1": {"pause_before": True},
            },
        })
        session = HITLSession(config=config, run_dir=tmp_path)
        session.set_input_callback(
            lambda _: HumanInput(action=HumanAction.SKIP)
        )
        adapters = AdapterBundle(hitl=session)

        result = _run_hitl_pre_stage(Stage.TOPIC_INIT, tmp_path, adapters)
        assert result is not None
        assert result.status == StageStatus.DONE

    def test_pre_stage_hook_abort(self, tmp_path: Path) -> None:
        """Pre-stage hook can abort the pipeline."""
        from researchclaw.pipeline.executor import _run_hitl_pre_stage
        from researchclaw.pipeline.stages import Stage, StageStatus

        config = HITLConfig.from_dict({
            "enabled": True,
            "mode": "custom",
            "stage_policies": {
                "1": {"pause_before": True},
            },
        })
        session = HITLSession(config=config, run_dir=tmp_path)
        session.set_input_callback(
            lambda _: HumanInput(action=HumanAction.ABORT)
        )
        adapters = AdapterBundle(hitl=session)

        result = _run_hitl_pre_stage(Stage.TOPIC_INIT, tmp_path, adapters)
        assert result is not None
        assert result.status == StageStatus.FAILED
        assert "Aborted" in (result.error or "")

    def test_pre_stage_hook_injects_guidance(self, tmp_path: Path) -> None:
        """Pre-stage hook writes guidance file."""
        from researchclaw.pipeline.executor import _run_hitl_pre_stage
        from researchclaw.pipeline.stages import Stage

        config = HITLConfig.from_dict({
            "enabled": True,
            "mode": "custom",
            "stage_policies": {
                "1": {"pause_before": True},
            },
        })
        session = HITLSession(config=config, run_dir=tmp_path)
        session.set_input_callback(
            lambda _: HumanInput(
                action=HumanAction.INJECT,
                guidance="Focus on NLP tasks",
            )
        )
        adapters = AdapterBundle(hitl=session)

        _run_hitl_pre_stage(Stage.TOPIC_INIT, tmp_path, adapters)
        guidance_file = tmp_path / "stage-01" / "hitl_guidance.md"
        assert guidance_file.exists()
        assert "NLP" in guidance_file.read_text()

    def test_post_stage_hook_approve(self, tmp_path: Path) -> None:
        """Post-stage hook approves and returns original result."""
        from researchclaw.pipeline.executor import _run_hitl_post_stage
        from researchclaw.pipeline._helpers import StageResult
        from researchclaw.pipeline.stages import Stage, StageStatus

        config = HITLConfig.from_dict({
            "enabled": True,
            "mode": "custom",
            "stage_policies": {
                "8": {"pause_after": True},
            },
        })
        session = HITLSession(config=config, run_dir=tmp_path)
        session.set_input_callback(
            lambda _: HumanInput(action=HumanAction.APPROVE)
        )
        adapters = AdapterBundle(hitl=session)

        original = StageResult(
            stage=Stage.HYPOTHESIS_GEN,
            status=StageStatus.DONE,
            artifacts=("hypotheses.md",),
        )
        result = _run_hitl_post_stage(
            Stage.HYPOTHESIS_GEN, original, tmp_path, adapters
        )
        assert result.status == StageStatus.DONE

    def test_post_stage_hook_reject(self, tmp_path: Path) -> None:
        """Post-stage hook rejects with REJECTED status."""
        from researchclaw.pipeline.executor import _run_hitl_post_stage
        from researchclaw.pipeline._helpers import StageResult
        from researchclaw.pipeline.stages import Stage, StageStatus

        config = HITLConfig.from_dict({
            "enabled": True,
            "mode": "custom",
            "stage_policies": {
                "8": {"require_approval": True},
            },
        })
        session = HITLSession(config=config, run_dir=tmp_path)
        session.set_input_callback(
            lambda _: HumanInput(
                action=HumanAction.REJECT,
                message="Hypothesis too vague",
            )
        )
        adapters = AdapterBundle(hitl=session)

        original = StageResult(
            stage=Stage.HYPOTHESIS_GEN,
            status=StageStatus.DONE,
            artifacts=("hypotheses.md",),
        )
        result = _run_hitl_post_stage(
            Stage.HYPOTHESIS_GEN, original, tmp_path, adapters
        )
        assert result.status == StageStatus.REJECTED
        assert "vague" in (result.error or "")


# ══════════════════════════════════════════════════════════════════
# Checkpoint enhancement tests
# ══════════════════════════════════════════════════════════════════


class TestCheckpointEnhancement:
    def test_checkpoint_includes_hitl_data(self, tmp_path: Path) -> None:
        """Checkpoint should include HITL session data when available."""
        from researchclaw.pipeline.runner import _write_checkpoint
        from researchclaw.pipeline.stages import Stage

        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(config=config)
        session.set_input_callback(
            lambda _: HumanInput(action=HumanAction.APPROVE)
        )
        # Simulate an intervention
        session.pause(8, "HYPOTHESIS_GEN", PauseReason.POST_STAGE)
        session.wait_for_human()

        adapters = AdapterBundle(hitl=session)
        _write_checkpoint(tmp_path, Stage.HYPOTHESIS_GEN, "rc-test", adapters=adapters)

        cp = json.loads((tmp_path / "checkpoint.json").read_text())
        assert "hitl" in cp
        assert cp["hitl"]["mode"] == "co-pilot"
        assert cp["hitl"]["interventions_count"] == 1

    def test_checkpoint_without_hitl(self, tmp_path: Path) -> None:
        """Checkpoint should work fine without HITL."""
        from researchclaw.pipeline.runner import _write_checkpoint
        from researchclaw.pipeline.stages import Stage

        _write_checkpoint(tmp_path, Stage.TOPIC_INIT, "rc-test")
        cp = json.loads((tmp_path / "checkpoint.json").read_text())
        assert "hitl" not in cp
        assert cp["last_completed_stage"] == 1


# ══════════════════════════════════════════════════════════════════
# Context preamble guidance injection test
# ══════════════════════════════════════════════════════════════════


class TestContextPreambleGuidance:
    def test_includes_hitl_guidance(self, tmp_path: Path) -> None:
        """_build_context_preamble should include HITL guidance files."""
        from researchclaw.pipeline._helpers import _build_context_preamble

        # Create guidance file
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir(parents=True)
        (stage_dir / "hitl_guidance.md").write_text(
            "Focus on quantum computing applications"
        )

        # Create minimal config mock
        config = MagicMock()
        config.research.topic = "ML Research"
        config.research.domains = ("ml",)

        preamble = _build_context_preamble(config, tmp_path)
        assert "quantum computing" in preamble
        assert "Human Guidance" in preamble


# ══════════════════════════════════════════════════════════════════
# End-to-end flow tests
# ══════════════════════════════════════════════════════════════════


class TestEndToEndFlow:
    def test_full_hitl_lifecycle(self, tmp_path: Path) -> None:
        """Test complete HITL session lifecycle: create → pause → resume → complete."""
        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(
            run_id="rc-test-e2e",
            config=config,
            run_dir=tmp_path,
        )

        # 1. Start
        assert session.is_active

        # 2. Pause at Stage 8
        approve_count = [0]

        def auto_approve(_):
            approve_count[0] += 1
            if approve_count[0] == 1:
                return HumanInput(
                    action=HumanAction.INJECT,
                    guidance="Use transformers",
                )
            return HumanInput(action=HumanAction.APPROVE)

        session.set_input_callback(auto_approve)

        # 3. First pause — inject guidance
        session.pause(8, "HYPOTHESIS_GEN", PauseReason.POST_STAGE)
        result = session.wait_for_human()
        assert result.action == HumanAction.INJECT
        assert session.interventions_count == 1

        # 4. Second pause — approve
        session.pause(9, "EXPERIMENT_DESIGN", PauseReason.GATE_APPROVAL)
        result = session.wait_for_human()
        assert result.action == HumanAction.APPROVE
        assert session.interventions_count == 2

        # 5. Complete
        session.complete()
        assert session.state == SessionState.COMPLETED
        assert session.total_human_time_sec >= 0

        # 6. Verify persistence
        assert (tmp_path / "hitl" / "session.json").exists()
        assert (tmp_path / "hitl" / "interventions.jsonl").exists()

        lines = (tmp_path / "hitl" / "interventions.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2

    def test_session_survives_reload(self, tmp_path: Path) -> None:
        """Test that a session can be saved and restored from disk."""
        config = HITLConfig(enabled=True, mode="co-pilot")
        session1 = HITLSession(
            run_id="rc-reload-test",
            config=config,
            run_dir=tmp_path,
        )
        session1.set_input_callback(
            lambda _: HumanInput(action=HumanAction.APPROVE)
        )

        # Simulate some activity
        session1.pause(5, "LITERATURE_SCREEN", PauseReason.GATE_APPROVAL)
        session1.wait_for_human()
        session1._persist_session()

        # Reload
        session2 = HITLSession.load(tmp_path, config)
        assert session2 is not None
        assert session2.run_id == "rc-reload-test"
        assert session2.interventions_count == 1

    def test_presets_produce_valid_configs(self) -> None:
        """All presets should produce valid HITLConfig objects."""
        from researchclaw.hitl.presets import list_presets, get_preset

        for name in list_presets():
            config = get_preset(name)
            assert config is not None, f"Preset '{name}' returned None"
            # Every non-auto preset should be enabled
            if name not in ("autonomous", "full-auto"):
                assert config.enabled, f"Preset '{name}' is not enabled"
            # Mode should be valid
            _ = config.intervention_mode
