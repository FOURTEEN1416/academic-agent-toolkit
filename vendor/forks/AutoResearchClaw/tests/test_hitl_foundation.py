# pyright: basic, reportMissingImports=false, reportUnusedCallResult=false
"""Tests for HITL foundation: config, intervention, session, adapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from researchclaw.hitl.config import (
    HITLConfig,
    InterventionMode,
    StagePolicy,
    _default_policy_for_mode,
)
from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    Intervention,
    InterventionType,
    PauseReason,
    WaitingState,
)
from researchclaw.hitl.session import HITLSession, SessionState


# ══════════════════════════════════════════════════════════════════
# HITLConfig tests
# ══════════════════════════════════════════════════════════════════


class TestHITLConfig:
    def test_default_config(self) -> None:
        config = HITLConfig()
        assert config.enabled is False
        assert config.mode == "full-auto"
        assert config.intervention_mode == InterventionMode.FULL_AUTO

    def test_from_dict_empty(self) -> None:
        config = HITLConfig.from_dict({})
        assert config.enabled is False

    def test_from_dict_copilot(self) -> None:
        config = HITLConfig.from_dict({
            "enabled": True,
            "mode": "co-pilot",
            "notifications": {"on_pause": True, "channels": ["terminal"]},
            "collaboration": {"max_chat_turns": 30},
            "timeouts": {"default_human_timeout_sec": 3600},
        })
        assert config.enabled is True
        assert config.intervention_mode == InterventionMode.CO_PILOT
        assert config.notifications.on_pause is True
        assert config.collaboration.max_chat_turns == 30
        assert config.timeouts.default_human_timeout_sec == 3600

    def test_from_dict_with_stage_policies(self) -> None:
        config = HITLConfig.from_dict({
            "enabled": True,
            "mode": "custom",
            "stage_policies": {
                "8": {"require_approval": True, "enable_collaboration": True},
                "9": {"require_approval": True, "allow_edit_output": True},
            },
        })
        assert config.stage_policies[8].require_approval is True
        assert config.stage_policies[8].enable_collaboration is True
        assert config.stage_policies[9].allow_edit_output is True

    def test_get_stage_policy_custom(self) -> None:
        config = HITLConfig.from_dict({
            "enabled": True,
            "mode": "custom",
            "stage_policies": {
                "8": {"require_approval": True},
            },
        })
        # Stage 8 has explicit policy
        assert config.get_stage_policy(8).require_approval is True
        # Stage 1 falls back to default for custom mode (all off)
        assert config.get_stage_policy(1).require_approval is False

    def test_intervention_mode_invalid(self) -> None:
        config = HITLConfig(mode="nonexistent")
        assert config.intervention_mode == InterventionMode.FULL_AUTO


class TestStagePolicy:
    def test_defaults(self) -> None:
        policy = StagePolicy()
        assert policy.auto_execute is True
        assert policy.pause_before is False
        assert policy.require_approval is False
        assert policy.enable_collaboration is False

    def test_custom_values(self) -> None:
        policy = StagePolicy(
            require_approval=True,
            enable_collaboration=True,
            min_quality_score=0.5,
        )
        assert policy.require_approval is True
        assert policy.min_quality_score == 0.5


class TestDefaultPolicyForMode:
    def test_full_auto(self) -> None:
        policy = _default_policy_for_mode(InterventionMode.FULL_AUTO, 8)
        assert policy.require_approval is False
        assert policy.pause_after is False

    def test_gate_only_at_gate(self) -> None:
        policy = _default_policy_for_mode(InterventionMode.GATE_ONLY, 9)
        assert policy.require_approval is True
        assert policy.allow_edit_output is True

    def test_gate_only_at_non_gate(self) -> None:
        policy = _default_policy_for_mode(InterventionMode.GATE_ONLY, 10)
        assert policy.require_approval is False

    def test_checkpoint_at_boundary(self) -> None:
        policy = _default_policy_for_mode(InterventionMode.CHECKPOINT, 8)
        assert policy.pause_after is True
        assert policy.require_approval is True

    def test_checkpoint_at_non_boundary(self) -> None:
        policy = _default_policy_for_mode(InterventionMode.CHECKPOINT, 7)
        assert policy.pause_after is False

    def test_step_by_step(self) -> None:
        policy = _default_policy_for_mode(
            InterventionMode.STEP_BY_STEP, 3
        )
        assert policy.pause_after is True
        assert policy.stream_output is True

    def test_copilot_collaboration_stage(self) -> None:
        policy = _default_policy_for_mode(InterventionMode.CO_PILOT, 8)
        assert policy.enable_collaboration is True
        assert policy.require_approval is True

    def test_copilot_stream_stage(self) -> None:
        policy = _default_policy_for_mode(InterventionMode.CO_PILOT, 12)
        assert policy.stream_output is True

    def test_copilot_normal_stage(self) -> None:
        policy = _default_policy_for_mode(InterventionMode.CO_PILOT, 4)
        assert policy.pause_after is False
        assert policy.enable_collaboration is False


# ══════════════════════════════════════════════════════════════════
# Intervention tests
# ══════════════════════════════════════════════════════════════════


class TestHumanInput:
    def test_serialize_roundtrip(self) -> None:
        hi = HumanInput(
            action=HumanAction.EDIT,
            message="Fixed formatting",
            edited_files={"paper.md": "new content"},
        )
        data = hi.to_dict()
        restored = HumanInput.from_dict(data)
        assert restored.action == HumanAction.EDIT
        assert restored.message == "Fixed formatting"
        assert restored.edited_files == {"paper.md": "new content"}

    def test_default_values(self) -> None:
        hi = HumanInput(action=HumanAction.APPROVE)
        assert hi.message == ""
        assert hi.guidance == ""
        assert hi.edited_files == {}
        assert hi.timestamp  # auto-generated


class TestIntervention:
    def test_serialize_roundtrip(self) -> None:
        iv = Intervention(
            type=InterventionType.APPROVE,
            stage=9,
            stage_name="EXPERIMENT_DESIGN",
            human_input=HumanInput(action=HumanAction.APPROVE),
            outcome="Approved experiment design",
        )
        data = iv.to_dict()
        restored = Intervention.from_dict(data)
        assert restored.type == InterventionType.APPROVE
        assert restored.stage == 9
        assert restored.human_input is not None
        assert restored.human_input.action == HumanAction.APPROVE

    def test_without_human_input(self) -> None:
        iv = Intervention(type=InterventionType.VIEW_OUTPUT, stage=5)
        data = iv.to_dict()
        restored = Intervention.from_dict(data)
        assert restored.human_input is None


class TestWaitingState:
    def test_serialize_roundtrip(self) -> None:
        ws = WaitingState(
            stage=8,
            stage_name="HYPOTHESIS_GEN",
            reason=PauseReason.POST_STAGE,
            context_summary="Generated 3 hypotheses",
            output_files=("hypotheses.md",),
        )
        data = ws.to_dict()
        restored = WaitingState.from_dict(data)
        assert restored.stage == 8
        assert restored.reason == PauseReason.POST_STAGE
        assert "hypotheses.md" in restored.output_files


# ══════════════════════════════════════════════════════════════════
# HITLSession tests
# ══════════════════════════════════════════════════════════════════


class TestHITLSession:
    def test_create_default(self) -> None:
        session = HITLSession()
        assert session.state == SessionState.ACTIVE
        assert session.is_active
        assert not session.is_waiting
        assert session.interventions_count == 0

    def test_disabled_config_skips_pauses(self) -> None:
        config = HITLConfig(enabled=False)
        session = HITLSession(config=config)
        assert not session.should_pause_before(8)
        assert not session.should_pause_after(8)

    def test_copilot_policy_queries(self) -> None:
        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(config=config)
        # Stage 8 should collaborate and require approval
        assert session.should_pause_after(8)
        assert session.should_collaborate(8)
        # Stage 4 (auto) should not pause
        assert not session.should_pause_after(4)
        # Stage 12 should stream
        assert session.should_stream(12)

    def test_pause_and_wait_with_callback(self) -> None:
        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(config=config, run_dir=None)

        # Register a callback that always approves
        session.set_input_callback(
            lambda _: HumanInput(action=HumanAction.APPROVE)
        )

        session.pause(8, "HYPOTHESIS_GEN", PauseReason.POST_STAGE)
        assert session.is_waiting

        result = session.wait_for_human()
        assert result.action == HumanAction.APPROVE
        assert session.is_active
        assert session.interventions_count == 1
        assert len(session.interventions) == 1

    def test_pause_without_callback_auto_approves(self) -> None:
        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(config=config)

        session.pause(5, "LITERATURE_SCREEN", PauseReason.GATE_APPROVAL)
        result = session.wait_for_human()
        assert result.action == HumanAction.APPROVE

    def test_edit_tracking(self) -> None:
        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(config=config)

        session.set_input_callback(
            lambda _: HumanInput(
                action=HumanAction.EDIT,
                edited_files={"hypotheses.md": "edited"},
            )
        )

        session.pause(8, "HYPOTHESIS_GEN", PauseReason.POST_STAGE)
        session.wait_for_human()
        assert 8 in session.human_edits

    def test_inject_guidance(self) -> None:
        session = HITLSession()
        iv = session.inject_guidance(
            8, "HYPOTHESIS_GEN", "Focus on quantum regularization"
        )
        assert iv.type == InterventionType.INJECT_GUIDANCE
        assert session.interventions_count == 1

    def test_session_states(self) -> None:
        session = HITLSession()
        assert session.state == SessionState.ACTIVE

        session.enter_collaboration(8, "HYPOTHESIS_GEN")
        assert session.state == SessionState.COLLABORATING

        session.exit_collaboration()
        assert session.state == SessionState.ACTIVE

        session.complete()
        assert session.state == SessionState.COMPLETED
        assert not session.is_active

    def test_to_dict(self) -> None:
        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(
            run_id="rc-test-123",
            config=config,
        )
        data = session.to_dict()
        assert data["run_id"] == "rc-test-123"
        assert data["mode"] == "co-pilot"
        assert data["interventions_count"] == 0

    def test_hitl_checkpoint_data(self) -> None:
        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(config=config)
        cp = session.hitl_checkpoint_data()
        assert cp["mode"] == "co-pilot"
        assert cp["interventions_count"] == 0
        assert cp["collaboration_active"] is False

    def test_persistence(self, tmp_path: Path) -> None:
        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(
            run_id="rc-test",
            config=config,
            run_dir=tmp_path,
        )

        # Persist session
        session._persist_session()
        assert (tmp_path / "hitl" / "session.json").exists()

        # Persist waiting state
        session.pause(8, "HYPOTHESIS_GEN", PauseReason.POST_STAGE)
        assert (tmp_path / "hitl" / "waiting.json").exists()

        # Load from disk
        loaded = HITLSession.load(tmp_path, config)
        assert loaded is not None
        assert loaded.run_id == "rc-test"
        assert loaded.is_waiting
        assert loaded._waiting is not None
        assert loaded._waiting.stage == 8

    def test_persistence_interventions_log(self, tmp_path: Path) -> None:
        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(
            run_id="rc-test",
            config=config,
            run_dir=tmp_path,
        )
        session.set_input_callback(
            lambda _: HumanInput(action=HumanAction.APPROVE)
        )

        session.pause(8, "HYPOTHESIS_GEN", PauseReason.POST_STAGE)
        session.wait_for_human()

        log_file = tmp_path / "hitl" / "interventions.jsonl"
        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["type"] == "approve"
        assert entry["stage"] == 8

    def test_abort(self) -> None:
        session = HITLSession()
        session.abort()
        assert session.state == SessionState.ABORTED
        assert not session.is_active


# ══════════════════════════════════════════════════════════════════
# AdapterBundle integration tests
# ══════════════════════════════════════════════════════════════════


class TestAdapterBundleHITL:
    def test_default_hitl_is_none(self) -> None:
        from researchclaw.adapters import AdapterBundle

        bundle = AdapterBundle()
        assert bundle.hitl is None

    def test_hitl_can_be_set(self) -> None:
        from researchclaw.adapters import AdapterBundle

        config = HITLConfig(enabled=True, mode="co-pilot")
        session = HITLSession(config=config)
        bundle = AdapterBundle(hitl=session)
        assert bundle.hitl is session


# ══════════════════════════════════════════════════════════════════
# Config integration tests
# ══════════════════════════════════════════════════════════════════


class TestRCConfigHITL:
    def test_hitl_field_default(self) -> None:
        """RCConfig should have hitl field defaulting to None."""
        from researchclaw.config import RCConfig

        assert hasattr(RCConfig, "__dataclass_fields__")
        assert "hitl" in RCConfig.__dataclass_fields__
