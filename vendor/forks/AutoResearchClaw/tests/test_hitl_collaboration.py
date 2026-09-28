# pyright: basic, reportMissingImports=false, reportUnusedCallResult=false
"""Tests for HITL collaboration layer: chat, editor, workshops, store."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from researchclaw.hitl.chat import ChatMessage, ChatSession, build_stage_context
from researchclaw.hitl.collaboration import CollaborationSession
from researchclaw.hitl.editor import StageEditor, StageReviewer
from researchclaw.hitl.store import HITLStore
from researchclaw.hitl.workshops.idea import IdeaCandidate, IdeaEvaluation, IdeaWorkshop
from researchclaw.hitl.workshops.baseline import BaselineCandidate, BaselineNavigator
from researchclaw.hitl.workshops.paper import PaperCoWriter, SectionDraft


# ══════════════════════════════════════════════════════════════════
# ChatSession tests
# ══════════════════════════════════════════════════════════════════


class TestChatMessage:
    def test_serialize_roundtrip(self) -> None:
        msg = ChatMessage(role="human", content="Hello")
        data = msg.to_dict()
        restored = ChatMessage.from_dict(data)
        assert restored.role == "human"
        assert restored.content == "Hello"


class TestChatSession:
    def test_empty_session(self) -> None:
        session = ChatSession()
        assert session.turn_count == 0
        assert not session.is_at_limit

    def test_add_messages(self) -> None:
        session = ChatSession()
        session.add_system_message("Context info")
        session.add_human_message("Hello")
        session.add_ai_message("Hi there!")
        assert len(session.messages) == 3
        assert session.turn_count == 1

    def test_build_llm_messages(self) -> None:
        session = ChatSession()
        session.add_system_message("You are a helper")
        session.add_human_message("Help me")
        messages = session.build_llm_messages()
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_turn_limit(self) -> None:
        session = ChatSession(max_turns=2)
        session.add_human_message("q1")
        session.add_human_message("q2")
        assert session.is_at_limit

    def test_get_ai_response_at_limit(self) -> None:
        session = ChatSession(max_turns=1)
        session.add_human_message("q1")
        llm = MagicMock()
        response = session.get_ai_response(llm)
        assert "limit reached" in response.lower()
        llm.chat.assert_not_called()

    def test_get_ai_response_with_llm(self) -> None:
        session = ChatSession()
        session.add_human_message("q1")
        llm = MagicMock()
        llm.chat.return_value = "AI response"
        response = session.get_ai_response(llm)
        assert response == "AI response"
        assert len(session.messages) == 2  # human + ai

    def test_save_and_load(self, tmp_path: Path) -> None:
        session = ChatSession()
        session.add_human_message("Hello")
        session.add_ai_message("Hi!")
        path = tmp_path / "chat.jsonl"
        session.save(path)
        assert path.exists()

        loaded = ChatSession.load(path)
        assert loaded is not None
        assert len(loaded.messages) == 2

    def test_to_dict(self) -> None:
        session = ChatSession(stage_num=8, stage_name="HYPOTHESIS_GEN")
        data = session.to_dict()
        assert data["stage_num"] == 8
        assert data["message_count"] == 0


class TestBuildStageContext:
    def test_basic_context(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("# Hypothesis 1\nTest")
        context = build_stage_context(
            8, "HYPOTHESIS_GEN", "ML research", tmp_path,
            artifacts=("hypotheses.md",),
        )
        assert "HYPOTHESIS_GEN" in context
        assert "ML research" in context
        assert "Hypothesis 1" in context


# ══════════════════════════════════════════════════════════════════
# CollaborationSession tests
# ══════════════════════════════════════════════════════════════════


class TestCollaborationSession:
    def test_initialize(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("# Test")

        collab = CollaborationSession()
        collab.initialize(
            8, "HYPOTHESIS_GEN", "Test topic", tmp_path,
            artifacts=("hypotheses.md",),
        )
        assert collab.stage_num == 8
        assert "hypotheses.md" in collab.shared_artifacts

    def test_human_edits_artifact(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("original")

        collab = CollaborationSession(run_dir=tmp_path)
        collab.stage_num = 8
        collab.shared_artifacts["hypotheses.md"] = "original"

        collab.human_edits_artifact("hypotheses.md", "edited content")
        assert collab.shared_artifacts["hypotheses.md"] == "edited content"
        assert len(collab.revision_history) == 1
        # Check file was written to disk
        assert (stage_dir / "hypotheses.md").read_text() == "edited content"

    def test_finalize(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()

        collab = CollaborationSession(run_dir=tmp_path)
        collab.stage_num = 8
        collab.shared_artifacts["output.md"] = "original"
        collab.human_edits_artifact("output.md", "final content")

        result = collab.finalize()
        assert result["output.md"] == "final content"
        assert collab.finalized
        assert (stage_dir / "output.md").read_text() == "final content"
        assert (tmp_path / "hitl" / "chat_stage_08.jsonl").exists()

    def test_finalize_preserves_external_edits(self, tmp_path: Path) -> None:
        """finalize() must not overwrite files the user edited on disk."""
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "notes.md").write_text("original")

        collab = CollaborationSession(run_dir=tmp_path)
        collab.stage_num = 8
        collab.shared_artifacts["notes.md"] = "original"

        # Simulate external edit (user edits file on disk directly)
        (stage_dir / "notes.md").write_text("externally edited")

        result = collab.finalize()
        # finalize should pick up the external edit, not overwrite it
        assert result["notes.md"] == "externally edited"
        assert (stage_dir / "notes.md").read_text() == "externally edited"

    def test_ai_proposes_edit_writes_to_disk(self, tmp_path: Path) -> None:
        """ai_proposes_edit() must persist changes to disk."""
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("original")

        collab = CollaborationSession(run_dir=tmp_path)
        collab.stage_num = 8
        collab.shared_artifacts["hypotheses.md"] = "original"

        collab.ai_proposes_edit("hypotheses.md", "ai improved content")
        assert (stage_dir / "hypotheses.md").read_text() == "ai improved content"
        assert len(collab.revision_history) == 1
        assert collab.revision_history[0]["action"] == "ai_proposal"

    def test_ai_responds_parses_edits(self, tmp_path: Path) -> None:
        """ai_responds() must detect <<<FILE:...>>> blocks and apply edits."""
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("original")

        collab = CollaborationSession(run_dir=tmp_path)
        collab.stage_num = 8
        collab.shared_artifacts["hypotheses.md"] = "original"

        llm = MagicMock()
        llm.chat.return_value = (
            "Here is my suggestion:\n"
            "<<<FILE: hypotheses.md>>>\n"
            "# Improved Hypothesis\nBetter content\n"
            "<<<END_FILE>>>\n"
            "Let me know what you think."
        )
        collab.chat.add_human_message("please improve")
        response = collab.ai_responds(llm)
        assert "suggestion" in response
        assert collab.shared_artifacts["hypotheses.md"] == "# Improved Hypothesis\nBetter content\n"
        assert (stage_dir / "hypotheses.md").read_text() == "# Improved Hypothesis\nBetter content\n"


# ══════════════════════════════════════════════════════════════════
# StageEditor tests
# ══════════════════════════════════════════════════════════════════


class TestStageEditor:
    def test_list_outputs(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("test")
        (stage_dir / "stage_health.json").write_text("{}")

        editor = StageEditor(tmp_path)
        files = editor.list_outputs(8)
        assert "hypotheses.md" in files
        assert "stage_health.json" not in files

    def test_read_write_output(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("original")

        editor = StageEditor(tmp_path)
        assert editor.read_output(8, "hypotheses.md") == "original"

        editor.write_output(8, "hypotheses.md", "edited")
        assert editor.read_output(8, "hypotheses.md") == "edited"

    def test_snapshot(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("original")

        editor = StageEditor(tmp_path)
        editor.write_output(8, "hypotheses.md", "edited")

        assert editor.has_snapshot(8, "hypotheses.md")
        assert editor.restore_snapshot(8, "hypotheses.md")
        assert editor.read_output(8, "hypotheses.md") == "original"

    def test_diff_summary(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("line1\nline2")

        editor = StageEditor(tmp_path)
        editor.write_output(8, "hypotheses.md", "line1\nline2\nline3")
        diff = editor.get_diff_summary(8, "hypotheses.md")
        assert diff is not None
        assert "+1" in diff


class TestStageReviewer:
    def test_summarize_stage(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-08"
        stage_dir.mkdir()
        (stage_dir / "hypotheses.md").write_text("# Hypothesis\nContent here")

        reviewer = StageReviewer(tmp_path)
        summary = reviewer.summarize_stage(8)
        assert "hypotheses.md" in summary
        assert "2 lines" in summary

    def test_summarize_json_output(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-14"
        stage_dir.mkdir()
        (stage_dir / "analysis.json").write_text('{"key": "value"}')

        reviewer = StageReviewer(tmp_path)
        summary = reviewer.summarize_json_output(14, "analysis.json")
        assert summary is not None
        assert "key" in summary


# ══════════════════════════════════════════════════════════════════
# HITLStore tests
# ══════════════════════════════════════════════════════════════════


class TestHITLStore:
    def test_ensure_dirs(self, tmp_path: Path) -> None:
        store = HITLStore(tmp_path)
        store.ensure_dirs()
        assert (tmp_path / "hitl").exists()
        assert (tmp_path / "hitl" / "snapshots").exists()

    def test_session_persistence(self, tmp_path: Path) -> None:
        store = HITLStore(tmp_path)
        store.save_session({"run_id": "test", "state": "active"})
        data = store.load_session()
        assert data is not None
        assert data["run_id"] == "test"

    def test_waiting_state(self, tmp_path: Path) -> None:
        store = HITLStore(tmp_path)
        assert not store.is_waiting()
        store.save_waiting({"stage": 8, "reason": "review"})
        assert store.is_waiting()
        data = store.load_waiting()
        assert data is not None
        assert data["stage"] == 8
        store.clear_waiting()
        assert not store.is_waiting()

    def test_interventions(self, tmp_path: Path) -> None:
        from researchclaw.hitl.intervention import Intervention, InterventionType

        store = HITLStore(tmp_path)
        iv = Intervention(type=InterventionType.APPROVE, stage=8)
        store.append_intervention(iv)
        store.append_intervention(iv)
        assert store.intervention_count() == 2
        entries = store.load_interventions()
        assert len(entries) == 2

    def test_chat(self, tmp_path: Path) -> None:
        store = HITLStore(tmp_path)
        msgs = [
            {"role": "human", "content": "Hello"},
            {"role": "ai", "content": "Hi!"},
        ]
        store.save_chat(8, msgs)
        assert store.has_chat(8)
        loaded = store.load_chat(8)
        assert len(loaded) == 2

    def test_guidance(self, tmp_path: Path) -> None:
        store = HITLStore(tmp_path)
        store.save_guidance(8, "Focus on X")
        assert store.load_guidance(8) == "Focus on X"

    def test_summary(self, tmp_path: Path) -> None:
        store = HITLStore(tmp_path)
        store.ensure_dirs()
        summary = store.get_summary()
        assert "has_session" in summary
        assert "is_waiting" in summary


# ══════════════════════════════════════════════════════════════════
# Idea Workshop tests
# ══════════════════════════════════════════════════════════════════


class TestIdeaCandidate:
    def test_serialize_roundtrip(self) -> None:
        idea = IdeaCandidate(
            title="Quantum Regularization",
            description="Use quantum noise as regularization",
            baselines=["Dropout", "Label Smoothing"],
        )
        data = idea.to_dict()
        restored = IdeaCandidate.from_dict(data)
        assert restored.title == "Quantum Regularization"
        assert len(restored.baselines) == 2


class TestIdeaWorkshop:
    def test_brainstorm_without_llm(self, tmp_path: Path) -> None:
        workshop = IdeaWorkshop(tmp_path)
        ideas = workshop.brainstorm("synthesis text", num_ideas=3)
        assert len(ideas) == 3

    def test_brainstorm_with_llm(self, tmp_path: Path) -> None:
        llm = MagicMock()
        llm.chat.return_value = json.dumps([
            {"title": "Idea 1", "description": "Desc 1"},
            {"title": "Idea 2", "description": "Desc 2"},
        ])
        workshop = IdeaWorkshop(tmp_path, llm_client=llm)
        ideas = workshop.brainstorm("synthesis", num_ideas=2)
        assert len(ideas) == 2
        assert ideas[0].title == "Idea 1"

    def test_evaluate_without_llm(self, tmp_path: Path) -> None:
        workshop = IdeaWorkshop(tmp_path)
        workshop.candidates = [
            IdeaCandidate(title="Test", description="Test idea")
        ]
        evals = workshop.evaluate()
        assert len(evals) == 1
        assert evals[0].novelty == 5.0  # Default

    def test_select(self, tmp_path: Path) -> None:
        workshop = IdeaWorkshop(tmp_path)
        idea = IdeaCandidate(title="Best idea", description="The one")
        workshop.select(idea)
        assert workshop.selected_idea is idea
        assert idea.human_approved

    def test_save(self, tmp_path: Path) -> None:
        workshop = IdeaWorkshop(tmp_path)
        workshop.candidates = [
            IdeaCandidate(title="Test", description="Desc")
        ]
        workshop.save()
        assert (tmp_path / "hitl" / "idea_workshop.json").exists()


# ══════════════════════════════════════════════════════════════════
# Baseline Navigator tests
# ══════════════════════════════════════════════════════════════════


class TestBaselineCandidate:
    def test_serialize(self) -> None:
        b = BaselineCandidate(
            name="ResNet-50", code_url="https://github.com/pytorch"
        )
        data = b.to_dict()
        restored = BaselineCandidate.from_dict(data)
        assert restored.name == "ResNet-50"


class TestBaselineNavigator:
    def test_human_add_remove(self, tmp_path: Path) -> None:
        nav = BaselineNavigator(tmp_path)
        nav.human_add_baseline("Dropout", notes="Classic baseline")
        assert len(nav.baselines) == 1
        assert nav.baselines[0].added_by == "human"

        assert nav.human_remove_baseline("Dropout")
        assert len(nav.baselines) == 0
        assert not nav.human_remove_baseline("Nonexistent")

    def test_suggest_baselines_with_llm(self, tmp_path: Path) -> None:
        llm = MagicMock()
        llm.chat.return_value = json.dumps([
            {"name": "ResNet-50", "is_standard": True},
            {"name": "ViT-B/16", "is_standard": True},
        ])
        nav = BaselineNavigator(tmp_path, llm_client=llm)
        baselines = nav.suggest_baselines("Image classification idea")
        assert len(baselines) == 2

    def test_generate_checklist(self, tmp_path: Path) -> None:
        nav = BaselineNavigator(tmp_path)
        nav.human_add_baseline("Method A")
        nav.metrics = ["accuracy", "f1"]
        checklist = nav.generate_checklist()
        assert "Method A" in checklist
        assert "accuracy" in checklist
        assert "Checklist" in checklist

    def test_save(self, tmp_path: Path) -> None:
        nav = BaselineNavigator(tmp_path)
        nav.human_add_baseline("Test")
        nav.save()
        assert (tmp_path / "hitl" / "baseline_navigator.json").exists()


# ══════════════════════════════════════════════════════════════════
# Paper Co-Writer tests
# ══════════════════════════════════════════════════════════════════


class TestPaperCoWriter:
    def test_load_outline(self, tmp_path: Path) -> None:
        stage_dir = tmp_path / "stage-16"
        stage_dir.mkdir()
        (stage_dir / "outline.md").write_text(
            "## Introduction\n## Method\n## Experiments\n## Conclusion\n"
        )
        writer = PaperCoWriter(tmp_path)
        writer.load_outline()
        assert len(writer.sections) == 4
        assert writer.sections[0].name == "Introduction"

    def test_human_edit_section(self, tmp_path: Path) -> None:
        writer = PaperCoWriter(tmp_path)
        writer.human_edit_section("Introduction", "New intro content")
        section = writer.sections[0]
        assert section.status == "human_edited"
        assert section.content == "New intro content"

    def test_finalize_section(self, tmp_path: Path) -> None:
        writer = PaperCoWriter(tmp_path)
        writer.human_edit_section("Method", "Method content")
        writer.finalize_section("Method")
        assert writer.sections[0].status == "finalized"

    def test_compile_paper(self, tmp_path: Path) -> None:
        writer = PaperCoWriter(tmp_path)
        writer.human_edit_section("Introduction", "Intro text")
        writer.human_edit_section("Method", "Method text")
        paper = writer.compile_paper()
        assert "Introduction" in paper
        assert "Method" in paper
        assert "Intro text" in paper

    def test_get_status(self, tmp_path: Path) -> None:
        writer = PaperCoWriter(tmp_path)
        writer.human_edit_section("Intro", "text")
        writer.finalize_section("Intro")
        writer.human_edit_section("Method", "text")
        status = writer.get_status()
        assert status["completed"] == 1
        assert status["in_progress"] == 1

    def test_write_section_without_llm(self, tmp_path: Path) -> None:
        writer = PaperCoWriter(tmp_path)
        result = writer.write_section("Introduction")
        assert "requires LLM" in result

    def test_save(self, tmp_path: Path) -> None:
        writer = PaperCoWriter(tmp_path)
        writer.human_edit_section("Test", "content")
        writer.save()
        assert (tmp_path / "hitl" / "paper_cowriter.json").exists()
