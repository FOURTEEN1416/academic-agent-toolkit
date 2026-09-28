"""Tests for the best-of-N tournament engine (Stage 8 / 9).

Covers candidate generation round-robin, judge selection, JSON-parse fallback,
single-candidate degradation, the ablation / env hooks, provenance record, and
empty-input guards. All offline (no network, fake clients).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from researchclaw.config import LlmConfig
from researchclaw.pipeline.tournament import effective_candidates, run_tournament


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------

class _GenLLM:
    """Records calls; returns content tagged by model name."""

    def __init__(self, model: str) -> None:
        self.config = LlmConfig(provider="x", primary_model=model)
        self.calls: list[dict] = []

    def chat(self, messages, *, system=None, max_tokens=None, **kw):
        self.calls.append({"system": system, "user": messages[-1]["content"]})

        class _R:
            content = f"CANDIDATE from {self.config.primary_model}"

        return _R()


class _JudgeLLM:
    """Returns a fixed JSON verdict; records that it was called."""

    def __init__(self, model: str, verdict: str) -> None:
        self.config = LlmConfig(provider="x", primary_model=model)
        self.verdict = verdict
        self.calls = 0

    def chat(self, messages, *, system=None, max_tokens=None, **kw):
        self.calls += 1
        return SimpleNamespace(content=self.verdict)


class _PromptsStub:
    def sub_prompt(self, name, **kw):
        from researchclaw.prompts import _render

        sys = "Rank them."
        usr = "n={n}\n{candidates}"
        return SimpleNamespace(
            system=_render(sys, kw), user=_render(usr, kw),
            json_mode=False, max_tokens=None,
        )


def _cps(n):
    return [(f"sys {i}", f"user {i}") for i in range(n)]


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def test_candidates_round_robin_over_generators(tmp_path):
    gens = [_GenLLM("m0"), _GenLLM("m1"), _GenLLM("m2")]
    judge = _JudgeLLM("judge", '{"rankings": [], "winner": 0}')
    run_tournament(
        gens, judge, _cps(3), rank_prompt="tournament_rank",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="m0",
    )
    # Each generator generates exactly one candidate.
    assert [len(g.calls) for g in gens] == [1, 1, 1]
    # Per-candidate transcripts written.
    assert (tmp_path / "candidate_0.md").exists()
    assert (tmp_path / "candidate_2.md").exists()


def test_judge_picks_declared_winner(tmp_path):
    gens = [_GenLLM("m0"), _GenLLM("m1"), _GenLLM("m2")]
    verdict = json.dumps(
        {"rankings": [{"id": 0, "score": 3}, {"id": 1, "score": 9},
                      {"id": 2, "score": 5}], "winner": 1}
    )
    judge = _JudgeLLM("judge", verdict)
    winner, rec = run_tournament(
        gens, judge, _cps(3), rank_prompt="tournament_rank",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="m0",
    )
    assert judge.calls == 1
    assert winner == "CANDIDATE from m1"
    assert rec["winner"] == 1
    assert rec["independent_judge"] is True
    assert rec["scores"] == {"0": 3, "1": 9, "2": 5}
    # Record persisted.
    saved = json.loads((tmp_path / "tournament_record.json").read_text())
    assert saved["winner"] == 1


def test_winner_from_fenced_json(tmp_path):
    gens = [_GenLLM("m0"), _GenLLM("m1")]
    judge = _JudgeLLM(
        "judge",
        'Here is my verdict:\n```json\n{"rankings": [], "winner": 1}\n```\nDone.',
    )
    winner, rec = run_tournament(
        gens, judge, _cps(2), rank_prompt="tournament_rank",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="m0",
    )
    assert rec["winner"] == 1
    assert winner == "CANDIDATE from m1"


def test_judge_parse_failure_falls_back_to_first(tmp_path):
    gens = [_GenLLM("m0"), _GenLLM("m1")]
    judge = _JudgeLLM("judge", "this is not json at all")
    winner, rec = run_tournament(
        gens, judge, _cps(2), rank_prompt="tournament_rank",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="m0",
    )
    assert rec["winner"] == 0
    assert winner == "CANDIDATE from m0"


def test_out_of_range_winner_falls_back(tmp_path):
    gens = [_GenLLM("m0"), _GenLLM("m1")]
    judge = _JudgeLLM("judge", '{"rankings": [], "winner": 7}')
    _, rec = run_tournament(
        gens, judge, _cps(2), rank_prompt="tournament_rank",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="m0",
    )
    assert rec["winner"] == 0


def test_single_candidate_skips_judge(tmp_path):
    gens = [_GenLLM("m0")]
    judge = _JudgeLLM("judge", '{"winner": 0}')
    winner, rec = run_tournament(
        gens, judge, _cps(1), rank_prompt="tournament_rank",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="m0",
    )
    assert judge.calls == 0
    assert rec["n"] == 1
    assert winner == "CANDIDATE from m0"


def test_single_generator_degrades(tmp_path):
    gen = _GenLLM("only")
    # Judge reuses the author model => judging is not independent.
    judge = _JudgeLLM("only", '{"rankings": [], "winner": 1}')
    winner, rec = run_tournament(
        [gen], judge, _cps(3), rank_prompt="tournament_rank",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="only",
    )
    # One generator handles all three candidate prompts.
    assert len(gen.calls) == 3
    assert rec["winner"] == 1
    # judge == author model => not independent.
    assert rec["independent_judge"] is False


def test_ablation_collapses_to_one(tmp_path, monkeypatch):
    monkeypatch.setenv("ARC_ABL_DISABLE_TOURNAMENT", "1")
    gens = [_GenLLM("m0"), _GenLLM("m1"), _GenLLM("m2")]
    judge = _JudgeLLM("judge", '{"winner": 0}')
    _, rec = run_tournament(
        gens, judge, _cps(3), rank_prompt="tournament_rank",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="m0",
    )
    assert rec["candidates_succeeded"] == 1
    assert judge.calls == 0  # only one survivor => no judging


def test_failed_generation_is_skipped(tmp_path):
    class _BoomLLM(_GenLLM):
        def chat(self, *a, **k):
            raise RuntimeError("boom")

    gens = [_GenLLM("m0"), _BoomLLM("m1"), _GenLLM("m2")]
    judge = _JudgeLLM("judge", '{"rankings": [], "winner": 1}')
    winner, rec = run_tournament(
        gens, judge, _cps(3), rank_prompt="tournament_rank",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="m0",
    )
    # Candidate 1 (boom) dropped -> 2 survivors -> winner index 1 = m2.
    assert rec["candidates_succeeded"] == 2
    assert winner == "CANDIDATE from m2"


def test_empty_candidate_is_dropped(tmp_path):
    # A provider returning "" (or whitespace) without raising must NOT count as
    # a candidate: it would otherwise inflate candidates_succeeded, be judged,
    # and could win — shipping an empty artifact. Mirrors the exception-skip
    # guard for the empty-content case (observed with some OpenRouter models).
    class _EmptyLLM(_GenLLM):
        def chat(self, *a, **k):
            return SimpleNamespace(content="   \n  ")

    gens = [_GenLLM("m0"), _EmptyLLM("m1"), _GenLLM("m2")]
    judge = _JudgeLLM("judge", '{"rankings": [], "winner": 1}')
    winner, rec = run_tournament(
        gens, judge, _cps(3), rank_prompt="tournament_rank",
        out_dir=tmp_path, prompts=_PromptsStub(), author_model="m0",
    )
    # Empty m1 dropped -> 2 real candidates (m0, m2), compacted indices 0/1.
    assert rec["candidates_succeeded"] == 2
    assert rec["generator_models"] == ["m0", "m2"]
    assert winner == "CANDIDATE from m2"  # judge winner=1 -> compacted idx 1 = m2
    # Transcripts use compacted indices; no third/empty file written.
    assert (tmp_path / "candidate_0.md").exists()
    assert (tmp_path / "candidate_1.md").exists()
    assert not (tmp_path / "candidate_2.md").exists()


def test_all_empty_candidates_raises(tmp_path):
    class _EmptyLLM(_GenLLM):
        def chat(self, *a, **k):
            return SimpleNamespace(content="")

    with pytest.raises(RuntimeError):
        run_tournament(
            [_EmptyLLM("m0"), _EmptyLLM("m1")], _JudgeLLM("judge", "{}"),
            _cps(2), rank_prompt="tournament_rank",
            out_dir=tmp_path, prompts=_PromptsStub(), author_model="m0",
        )


def test_empty_candidate_prompts_raises(tmp_path):
    with pytest.raises(ValueError):
        run_tournament(
            [_GenLLM("m0")], None, [], rank_prompt="tournament_rank",
            out_dir=tmp_path, prompts=_PromptsStub(),
        )


def test_empty_generators_raises(tmp_path):
    with pytest.raises(ValueError):
        run_tournament(
            [], None, _cps(2), rank_prompt="tournament_rank",
            out_dir=tmp_path, prompts=_PromptsStub(),
        )


def test_effective_candidates_env_override(monkeypatch):
    assert effective_candidates(3) == 3
    monkeypatch.setenv("ARC_TOURNAMENT_CANDIDATES", "5")
    assert effective_candidates(3) == 5
    monkeypatch.setenv("ARC_TOURNAMENT_CANDIDATES", "garbage")
    assert effective_candidates(3) == 3
    assert effective_candidates(0) == 1  # floor at 1
