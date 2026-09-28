from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SRC = REPO_ROOT / "packages" / "runtime-core" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from vgo_runtime.kernel.text_tokens import (
    BENCHMARK_STOPWORDS,
    DEFAULT_STOPWORDS,
    SKILL_MATCH_STOPWORDS,
    expand_tokens,
    tokens_from_text,
)


def test_tokens_from_text_without_stemming_preserves_original_tokens() -> None:
    tokens = tokens_from_text("reviewing plans and studies", stopwords=DEFAULT_STOPWORDS)

    assert "reviewing" in tokens
    assert "plans" in tokens
    assert "studies" in tokens
    assert "review" not in tokens
    assert "plan" not in tokens
    assert "study" not in tokens


def test_tokens_from_text_with_stemming_normalizes_plural_and_ing_forms() -> None:
    tokens = tokens_from_text(
        "reviewing plans and studies",
        stopwords=SKILL_MATCH_STOPWORDS,
        stem=True,
    )

    assert "review" in tokens
    assert "plan" in tokens
    assert "study" in tokens


def test_expand_tokens_keeps_original_and_variants() -> None:
    expanded = expand_tokens(("debugging", "stories"))

    assert "debugging" in expanded
    assert "story" in expanded


def test_benchmark_stopwords_extend_shared_stopwords() -> None:
    tokens = tokens_from_text(
        "produce benchmark notes",
        stopwords=BENCHMARK_STOPWORDS,
        stem=True,
    )

    assert "produce" not in tokens
    assert "benchmark" in tokens
    assert "note" in tokens
