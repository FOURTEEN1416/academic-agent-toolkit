"""Tests for the independent reviewer/judge model (P0-3).

Covers:
  - LLMClient.reviewer_from_rc_config factory (None / same-endpoint / independent)
  - build_reviewer_llm helper (acp + unset => None)
  - config parsing of reviewer_* fields
  - review-stage routing & provenance (Stage 18 peer review, Stage 20 gate helper)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from researchclaw.config import LlmConfig, RCConfig
from researchclaw.llm.client import LLMClient
from researchclaw.llm import build_reviewer_llm


def _make_rc_config(provider: str = "openai-compatible", **llm_kwargs):
    """Lightweight RCConfig stand-in.

    The reviewer factory and review stages only read ``config.llm.*`` and
    ``config.research.topic``, so a SimpleNamespace avoids RCConfig's many
    required sub-configs.
    """
    from types import SimpleNamespace

    llm = LlmConfig(provider=provider, **llm_kwargs)
    return SimpleNamespace(llm=llm, research=SimpleNamespace(topic="t"))


# --------------------------------------------------------------------------
# Factory: reviewer_from_rc_config
# --------------------------------------------------------------------------

def test_reviewer_none_when_unset() -> None:
    cfg = _make_rc_config(primary_model="gpt-4o", base_url="https://x/v1", api_key="k")
    assert LLMClient.reviewer_from_rc_config(cfg) is None
    assert build_reviewer_llm(cfg) is None


def test_reviewer_same_endpoint_different_model() -> None:
    cfg = _make_rc_config(
        primary_model="gpt-4o",
        base_url="https://main/v1",
        api_key="mainkey",
        reviewer_model="claude-sonnet-4-6",
    )
    rc = LLMClient.reviewer_from_rc_config(cfg)
    assert rc is not None
    # Different model, but reuses the main endpoint/key.
    assert rc.config.primary_model == "claude-sonnet-4-6"
    assert rc.config.base_url == "https://main/v1"
    assert rc.config.api_key == "mainkey"
    # Reviewer never falls back to the author model.
    assert list(rc.config.fallback_models) == []


def test_reviewer_fully_independent_provider() -> None:
    # Use a plain OpenAI-compatible provider so the unit test never constructs a
    # provider adapter that might touch the network.
    cfg = _make_rc_config(
        primary_model="gpt-4o",
        base_url="https://main/v1",
        api_key="mainkey",
        reviewer_model="some-other-model",
        reviewer_provider="openai-compatible",
        reviewer_base_url="https://rev/v1",
        reviewer_api_key="revkey",
    )
    rc = LLMClient.reviewer_from_rc_config(cfg)
    assert rc is not None
    assert rc.config.primary_model == "some-other-model"
    assert rc.config.base_url == "https://rev/v1"
    assert rc.config.api_key == "revkey"


def test_reviewer_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVIEWER_KEY", "fromenv")
    cfg = _make_rc_config(
        primary_model="gpt-4o",
        base_url="https://main/v1",
        api_key="mainkey",
        reviewer_model="m2",
        reviewer_api_key_env="REVIEWER_KEY",
    )
    rc = LLMClient.reviewer_from_rc_config(cfg)
    assert rc is not None
    assert rc.config.api_key == "fromenv"


def test_build_reviewer_llm_none_for_acp() -> None:
    cfg = _make_rc_config(provider="acp", reviewer_model="whatever")
    assert build_reviewer_llm(cfg) is None


# --------------------------------------------------------------------------
# Config parsing
# --------------------------------------------------------------------------

def test_parse_reviewer_fields() -> None:
    from researchclaw.config import _parse_llm_config

    cfg = _parse_llm_config(
        {
            "provider": "openai-compatible",
            "primary_model": "gpt-4o",
            "reviewer_model": "claude-sonnet-4-6",
            "reviewer_provider": "anthropic",
            "reviewer_base_url": "https://rev/v1",
            "reviewer_api_key_env": "ANTHROPIC_API_KEY",
        }
    )
    assert cfg.reviewer_model == "claude-sonnet-4-6"
    assert cfg.reviewer_provider == "anthropic"
    assert cfg.reviewer_base_url == "https://rev/v1"
    assert cfg.reviewer_api_key_env == "ANTHROPIC_API_KEY"


def test_parse_reviewer_defaults_empty() -> None:
    from researchclaw.config import _parse_llm_config

    cfg = _parse_llm_config({"provider": "openai", "primary_model": "gpt-4o"})
    assert cfg.reviewer_model == ""
    assert cfg.reviewer_provider == ""


# --------------------------------------------------------------------------
# Review-stage routing & provenance
# --------------------------------------------------------------------------

class _RecordingLLM:
    """Fake LLM client recording who was asked to chat."""

    def __init__(self, name: str, model: str) -> None:
        self.name = name
        self.config = LlmConfig(provider="x", primary_model=model)
        self.calls = 0

    def chat(self, messages, *, system=None, json_mode=False, max_tokens=None,
             strip_thinking=False, temperature=None, model=None):
        self.calls += 1

        class _Resp:
            content = "Reviewer A (methodology): looks ok.\nScore: 5"

        return _Resp()


def _helper_routes(monkeypatch, reviewer):
    """Drive _build_reviewer_or_generator with a patched build_reviewer_llm."""
    import researchclaw.llm as _llm_pkg

    monkeypatch.setattr(_llm_pkg, "build_reviewer_llm", lambda config: reviewer)
    from researchclaw.pipeline.stage_impls._review_publish import (
        _build_reviewer_or_generator,
    )

    gen = _RecordingLLM("gen", "gen-model")
    cfg = _make_rc_config(primary_model="gen-model")
    return _build_reviewer_or_generator(cfg, gen), gen


def test_helper_falls_back_to_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    (client, author, judge), gen = _helper_routes(monkeypatch, None)
    assert client is gen
    assert author == "gen-model"
    assert judge == "gen-model"  # not independent


def test_helper_uses_reviewer(monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = _RecordingLLM("rev", "judge-model")
    (client, author, judge), gen = _helper_routes(monkeypatch, reviewer)
    assert client is reviewer
    assert author == "gen-model"
    assert judge == "judge-model"


def test_peer_review_uses_reviewer_and_records_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import researchclaw.llm as _llm_pkg

    reviewer = _RecordingLLM("rev", "judge-model")
    monkeypatch.setattr(_llm_pkg, "build_reviewer_llm", lambda config: reviewer)

    from researchclaw.pipeline.stage_impls._review_publish import _execute_peer_review

    run_dir = tmp_path
    (run_dir / "stage-17").mkdir(parents=True)
    (run_dir / "stage-17" / "paper_draft.md").write_text("# Paper\nbody", encoding="utf-8")
    stage_dir = run_dir / "stage-18"
    stage_dir.mkdir()

    gen = _RecordingLLM("gen", "gen-model")
    cfg = _make_rc_config(primary_model="gen-model")
    result = _execute_peer_review(stage_dir, run_dir, cfg, object(), llm=gen)

    assert result.status.name == "DONE"
    # The independent reviewer answered, not the generator.
    assert reviewer.calls == 1
    assert gen.calls == 0
    import json

    prov = json.loads((stage_dir / "review_provenance.json").read_text())
    assert prov["independent_reviewer"] is True
    assert prov["author_model"] == "gen-model"
    assert prov["judge_model"] == "judge-model"
