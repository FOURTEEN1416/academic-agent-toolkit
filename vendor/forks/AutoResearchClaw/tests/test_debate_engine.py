"""Tests for the multi-model debate engine (Stage 8/14/18).

Covers panel construction (reuse of existing models) and the run_debate engine:
role-to-model binding, rebuttal visibility, judge synthesis, provenance record,
and the rounds=0 / single-model degradation paths. All offline.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from researchclaw.config import LlmConfig
from researchclaw.llm import build_panel_llms
from researchclaw.pipeline.debate import run_debate


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------

class _RecLLM:
    def __init__(self, model: str) -> None:
        self.config = LlmConfig(provider="x", primary_model=model)
        self.calls: list[dict] = []

    def chat(self, messages, *, system=None, max_tokens=None, **kw):
        self.calls.append({"system": system, "user": messages[-1]["content"]})

        class _R:
            content = f"[{self.config.primary_model}] said something"

        return _R()


class _PromptsStub:
    """Minimal PromptManager stand-in for sub_prompt rendering."""

    def sub_prompt(self, name, **kw):
        from researchclaw.prompts import _render

        if name == "debate_rebuttal":
            sys = "You are the {role} perspective."
            usr = "Prev:{own_position}\nOthers:\n{others}"
        else:  # synth
            sys = "Synthesize."
            usr = "{perspectives}"
        return SimpleNamespace(
            system=_render(sys, kw), user=_render(usr, kw),
            json_mode=False, max_tokens=None,
        )


_ROLES = {
    "innovator": {"system": "Be bold about {topic}.", "user": "Propose for {topic}."},
    "pragmatist": {"system": "Be practical about {topic}.", "user": "Ground it: {topic}."},
    "contrarian": {"system": "Attack {topic}.", "user": "Refute {topic}."},
}


def _cfg(debate_enabled=True, rounds=1, reviewer_model="", fallback=()):
    llm = LlmConfig(
        provider="openai-compatible", base_url="https://x/v1", api_key="k",
        primary_model="m-primary", reviewer_model=reviewer_model,
        fallback_models=tuple(fallback), debate_enabled=debate_enabled,
        debate_rounds=rounds,
    )
    return SimpleNamespace(llm=llm, research=SimpleNamespace(topic="t"))


# --------------------------------------------------------------------------
# build_panel_llms
# --------------------------------------------------------------------------

def test_panel_empty_when_disabled():
    assert build_panel_llms(_cfg(debate_enabled=False)) == []


def test_panel_reuses_and_dedupes_models():
    cfg = _cfg(reviewer_model="m-judge", fallback=("m-fb", "m-primary"))
    panel = build_panel_llms(cfg)
    names = [c.config.primary_model for c in panel]
    # primary + reviewer + fallback, deduped (m-primary appears once)
    assert names == ["m-primary", "m-judge", "m-fb"]
    # each member is single-model (no fallback chain)
    assert all(list(c.config.fallback_models) == [] for c in panel)


def test_panel_empty_for_acp():
    cfg = _cfg()
    cfg.llm = LlmConfig(provider="acp", primary_model="x", debate_enabled=True)
    assert build_panel_llms(cfg) == []


# --------------------------------------------------------------------------
# run_debate
# --------------------------------------------------------------------------

def test_roles_bound_to_distinct_models(tmp_path: Path):
    panel = [_RecLLM("A"), _RecLLM("B"), _RecLLM("C")]
    judge = _RecLLM("JUDGE")
    final, rec = run_debate(
        panel, judge, _ROLES, {"topic": "T"},
        rounds=0, synth_prompt="hypothesis_synthesize",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="m-primary",
    )
    # 3 roles round-robin over 3 models => each model gets exactly one opening call
    assert rec["roles"] == {"innovator": "A", "pragmatist": "B", "contrarian": "C"}
    assert all(len(c.calls) == 1 for c in panel)
    assert judge.calls and "JUDGE" in final
    assert rec["independent_judge"] is True
    assert (tmp_path / "debate_record.json").exists()
    assert (tmp_path / "innovator.r0.md").exists()


def test_rebuttal_round_sees_others(tmp_path: Path):
    panel = [_RecLLM("A"), _RecLLM("B"), _RecLLM("C")]
    run_debate(
        panel, _RecLLM("J"), _ROLES, {"topic": "T"},
        rounds=1, synth_prompt="hypothesis_synthesize",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="x",
    )
    # innovator's rebuttal (model A, 2nd call) must contain B's and C's text
    a_rebuttal = panel[0].calls[1]["user"]
    assert "pragmatist" in a_rebuttal and "contrarian" in a_rebuttal
    assert (tmp_path / "innovator.r1.md").exists()


def test_rounds_zero_skips_rebuttal(tmp_path: Path):
    panel = [_RecLLM("A"), _RecLLM("B"), _RecLLM("C")]
    run_debate(
        panel, _RecLLM("J"), _ROLES, {"topic": "T"},
        rounds=0, synth_prompt="hypothesis_synthesize",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="x",
    )
    assert all(len(c.calls) == 1 for c in panel)  # only opening, no rebuttal
    assert not (tmp_path / "innovator.r1.md").exists()


def test_single_model_panel_degrades(tmp_path: Path):
    solo = _RecLLM("SOLO")
    final, rec = run_debate(
        [solo], None, _ROLES, {"topic": "T"},
        rounds=1, synth_prompt="hypothesis_synthesize",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="SOLO",
    )
    # all roles bound to the one model; judge falls back to panel[0]
    assert set(rec["roles"].values()) == {"SOLO"}
    assert rec["judge_model"] == "SOLO"
    assert rec["independent_judge"] is False


def test_split_judge_and_synthesizer(tmp_path: Path):
    # When a distinct synthesizer is given, scoring and synthesis split: the
    # independent judge only scores/ranks, the synthesizer writes the final text.
    panel = [_RecLLM("A"), _RecLLM("B"), _RecLLM("C")]
    judge = _RecLLM("JUDGE")
    synth = _RecLLM("SYNTH")
    final, rec = run_debate(
        panel, judge, _ROLES, {"topic": "T"},
        rounds=0, synth_prompt="hypothesis_synthesize",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="A",
        synthesizer=synth,
    )
    # Final text comes from the synthesizer, not the judge.
    assert "SYNTH" in final
    assert "JUDGE" not in final
    # Judge was called exactly once (scoring), synthesizer once (synthesis).
    assert len(judge.calls) == 1
    assert len(synth.calls) == 1
    # The judge's ranking is fed into the synthesizer's input.
    assert "Independent reviewer assessment" in synth.calls[0]["user"]
    assert rec["split_judge_synthesis"] is True
    assert rec["judge_model"] == "JUDGE"
    assert rec["synthesizer_model"] == "SYNTH"
    assert (tmp_path / "debate_scores.md").exists()


def test_no_split_when_synthesizer_is_judge(tmp_path: Path):
    # synthesizer omitted -> judge does score+synthesis in one call (legacy).
    panel = [_RecLLM("A"), _RecLLM("B"), _RecLLM("C")]
    judge = _RecLLM("JUDGE")
    final, rec = run_debate(
        panel, judge, _ROLES, {"topic": "T"},
        rounds=0, synth_prompt="hypothesis_synthesize",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="A",
    )
    assert "JUDGE" in final
    assert len(judge.calls) == 1
    assert rec["split_judge_synthesis"] is False
    assert not (tmp_path / "debate_scores.md").exists()


def test_opening_retries_transient_failure(tmp_path: Path):
    # A role whose first opening call returns empty (transient) is retried once
    # and recovered, rather than being dropped from the debate.
    class _FlakyLLM(_RecLLM):
        def __init__(self, model: str) -> None:
            super().__init__(model)
            self._n = 0

        def chat(self, messages, *, system=None, max_tokens=None, **kw):
            self.calls.append({"system": system, "user": messages[-1]["content"]})
            self._n += 1
            content = "" if self._n == 1 else f"[{self.config.primary_model}] recovered"
            return SimpleNamespace(content=content)

    flaky = _FlakyLLM("C")
    panel = [_RecLLM("A"), _RecLLM("B"), flaky]
    final, rec = run_debate(
        panel, _RecLLM("J"), _ROLES, {"topic": "T"},
        rounds=0, synth_prompt="hypothesis_synthesize",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="A",
    )
    # Retried once (2 calls), recovered, and kept in the debate.
    assert flaky._n == 2
    assert "contrarian" in rec["perspectives_succeeded"]
    assert (tmp_path / "contrarian.r0.md").exists()


def test_opening_dropped_after_retry_exhausted(tmp_path: Path):
    # A role that returns empty on every attempt is dropped after the retry.
    class _AlwaysEmpty(_RecLLM):
        def chat(self, messages, *, system=None, max_tokens=None, **kw):
            self.calls.append({"system": system, "user": messages[-1]["content"]})
            return SimpleNamespace(content="")

    dead = _AlwaysEmpty("C")
    panel = [_RecLLM("A"), _RecLLM("B"), dead]
    _, rec = run_debate(
        panel, _RecLLM("J"), _ROLES, {"topic": "T"},
        rounds=0, synth_prompt="hypothesis_synthesize",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="A",
    )
    assert len(dead.calls) == 2  # tried twice, then gave up
    assert "contrarian" not in rec["perspectives_succeeded"]
    assert not (tmp_path / "contrarian.r0.md").exists()


def test_empty_panel_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        run_debate([], None, _ROLES, {}, rounds=0,
                   synth_prompt="x", out_dir=tmp_path, prompts=_PromptsStub())
