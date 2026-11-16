"""Behavioral assurance tests for actual reviewer metadata saved by Bash."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRACE_SCRIPT = ROOT / "tools" / "save_trace.sh"
sys.path.insert(0, str(ROOT / "tools"))
import provenance  # noqa: E402
import review_gate  # noqa: E402


def save_trace(
    tmp_path: Path, *arguments: str, mode: str = "full", response: str = "Review result.",
) -> tuple[dict, dict, dict]:
    result = subprocess.run(
        ["bash", str(TRACE_SCRIPT), "--skill", "research-review", "--purpose", "review",
         "--prompt", "Read the assigned files.", "--response", response,
         "--trace-mode", mode, *arguments],
        cwd=tmp_path, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    run_dir = next((tmp_path / ".aris" / "traces" / "research-review").iterdir())
    request_path = sorted(run_dir.glob("*.request.json"))[-1]
    meta_path = request_path.with_name(request_path.name.replace(".request.json", ".meta.json"))
    return tuple(json.loads(path.read_text()) for path in (request_path, meta_path, run_dir / "run.meta.json"))


@pytest.mark.parametrize("mode", ["full", "meta"])
@pytest.mark.parametrize(("backend", "actual", "family"), [
    ("grok", "grok-4.7-build", "xai"),
    ("claude-code", "deepseek-flash", "deepseek"),
    ("antigravity", "claude-opus-5-5-high", "anthropic"),
])
def test_actual_reported_model_controls_trace_assurance(
    tmp_path: Path, mode: str, backend: str, actual: str, family: str,
) -> None:
    request, meta, run_meta = save_trace(
        tmp_path, "--backend", backend, "--executor-model", "gpt-6-astra",
        "--model", "gpt-6-astra", "--requested-reviewer-model", "gpt-6-astra",
        "--reported-reviewer-model", actual, "--review-completed", "--review-positive", "--review-scope-complete",
        "--verdict", "ready", mode=mode,
    )
    for artifact in (request, meta):
        assert artifact["reviewer_model"] == actual
        assert artifact["requested_reviewer_model"] == "gpt-6-astra"
        assert artifact["reported_reviewer_model"] == actual
        assert artifact["reviewer_model_source"] == "backend-reported"
        assert artifact["review_independence"] == "cross-family"
        assert artifact["acceptance_status"] == "accepted"
        assert artifact["review_completed"] is True
        assert artifact["review_scope_complete"] is True
        assert artifact["review_positive"] is True
        assert artifact["status"] == "ok"
        assert artifact["independence_verified"] == "unverified"
    assert request["reviewer_family"] == meta["model_family"] == family
    assert "acceptance_status" not in run_meta  # initial context is not a run verdict
    assert "review_independence" not in run_meta
    if mode == "full":
        assert request["prompt"] == "Read the assigned files.\n"
    else:
        assert "prompt" not in request
        assert request["prompt_length"] == len("Read the assigned files.")


def test_claude_code_with_deepseek_is_same_family_when_executor_is_deepseek(tmp_path: Path) -> None:
    request, meta, _ = save_trace(
        tmp_path, "--backend", "claude-code", "--executor-model", "deepseek-v3",
        "--model", "claude-opus-5-5-high", "--reported-reviewer-model", "deepseek-flash",
        "--review-completed", "--review-positive", "--review-scope-complete", "--verdict", "PASS",
    )
    for artifact in (request, meta):
        assert artifact["reviewer_model"] == "deepseek-flash"
        assert artifact["review_independence"] == "same-family"
        assert artifact["acceptance_status"] == "provisional"


@pytest.mark.parametrize("mode", ["full", "meta"])
@pytest.mark.parametrize("arguments", [
    ["--reported-reviewer-model", "grok-4.7-build", "--review-scope-complete", "--verdict", "ready"],
    ["--reported-reviewer-model", "grok-4.7-build", "--review-completed", "--verdict", "ready"],
    ["--reported-reviewer-model", "grok-4.7-build", "--review-completed", "--review-scope-complete", "--verdict", "ready", "--status", "error"],
    ["--reported-reviewer-model", "grok-4.7-build", "--review-completed", "--review-scope-complete", "--verdict", "ready", "--status", "unknown"],
    ["--reported-reviewer-model", "unknown", "--review-completed", "--review-scope-complete", "--verdict", "ready"],
    ["--reported-reviewer-model", "mystery-model", "--review-completed", "--review-scope-complete", "--verdict", "ready"],
    ["--review-completed", "--review-scope-complete", "--verdict", "ready"],
])
def test_trace_never_accepts_missing_evidence_or_failed_result(
    tmp_path: Path, mode: str, arguments: list[str],
) -> None:
    request, meta, _ = save_trace(
        tmp_path, "--backend", "grok", "--executor-model", "gpt-6-astra",
        "--model", "grok-4.7", "--requested-reviewer-model", "grok-4.7",
        "--review-positive", *arguments, mode=mode,
    )
    for artifact in (request, meta):
        assert artifact["acceptance_status"] == "provisional"
        assert artifact["review_positive"] is True
        if "error" in arguments:
            assert artifact["status"] == "error"


@pytest.mark.parametrize("verdict", ["ready", "almost", "PASS", "WARN", "clean"])
def test_trace_uses_the_skill_positive_gate_without_parsing_raw_verdict(tmp_path: Path, verdict: str) -> None:
    request, meta, _ = save_trace(
        tmp_path, "--backend", "grok", "--executor-model", "gpt-6-astra",
        "--reported-reviewer-model", "grok-4.7-build", "--review-completed", "--review-positive",
        "--review-scope-complete", "--verdict", verdict,
    )
    assert request["acceptance_status"] == meta["acceptance_status"] == "accepted"


@pytest.mark.parametrize("status", ["ok", "fallback_used", "SUCCESS", "completed"])
def test_trace_accepts_successful_status_spellings(tmp_path: Path, status: str) -> None:
    request, _, _ = save_trace(
        tmp_path, "--backend", "grok", "--executor-model", "gpt-6-astra",
        "--reported-reviewer-model", "grok-4.7-build", "--review-completed", "--review-positive",
        "--review-scope-complete", "--verdict", "WARN", "--status", status,
    )
    assert request["status"] == status
    assert request["acceptance_status"] == "accepted"


def test_warn_without_completed_scope_does_not_accept(tmp_path: Path) -> None:
    request, _, _ = save_trace(
        tmp_path, "--backend", "grok", "--executor-model", "gpt-6-astra",
        "--reported-reviewer-model", "grok-4.7-build", "--verdict", "WARN", "--review-positive",
    )
    assert request["verdict"] == "WARN"
    assert request["acceptance_status"] == "provisional"


@pytest.mark.parametrize("mode", ["full", "meta"])
@pytest.mark.parametrize("score", [5, 8])
def test_ready_text_never_implies_a_positive_skill_gate(tmp_path: Path, mode: str, score: int) -> None:
    request, meta, _ = save_trace(
        tmp_path, "--backend", "grok", "--executor-model", "gpt-6-astra",
        "--reported-reviewer-model", "grok-4.7-build", "--review-completed",
        "--review-scope-complete", "--verdict", "ready", mode=mode,
        response=f"Score: {score}/10\nVerdict: ready",
    )
    for artifact in (request, meta):
        assert artifact["review_completed"] is True
        assert artifact["review_scope_complete"] is True
        assert artifact["review_positive"] is False
        assert artifact["verdict"] == "ready"
        assert artifact["acceptance_status"] == "provisional"


@pytest.mark.parametrize("score", [5, 8])
def test_trace_and_score_gate_agree_when_caller_forwards_the_gate_result(tmp_path: Path, score: int) -> None:
    transition = review_gate.evaluate_transition(
        round_backend="grok", score=score, verdict="ready",
        executor_model="gpt-6-astra", reviewer_model="grok-4.7-build",
        review_completed=True, review_scope_complete=True, review_status="ok",
    )
    positive_flags = ["--review-positive"] if transition.decision == "stop" else []
    request, meta, _ = save_trace(
        tmp_path, "--backend", "grok", "--executor-model", "gpt-6-astra",
        "--reported-reviewer-model", "grok-4.7-build", "--review-completed",
        "--review-scope-complete", "--verdict", "ready", *positive_flags,
        response=f"Score: {score}/10\nVerdict: ready",
    )
    for artifact in (request, meta):
        assert artifact["acceptance_status"] == transition.acceptance_status
        assert artifact["review_positive"] is bool(positive_flags)


def test_unknown_executor_cannot_be_accepted(tmp_path: Path) -> None:
    request, _, _ = save_trace(
        tmp_path, "--backend", "grok", "--executor-model", "mystery-executor",
        "--reported-reviewer-model", "grok-4.7-build", "--review-completed", "--review-positive",
        "--review-scope-complete", "--verdict", "ready",
    )
    assert request["review_independence"] == "unknown"
    assert request["acceptance_status"] == "provisional"


def test_copilot_compatibility_trace_stays_drive_only(tmp_path: Path) -> None:
    request, _, _ = save_trace(
        tmp_path, "--backend", "copilot", "--executor-model", "claude-sonnet-4.5",
        "--reported-reviewer-model", "gpt-5.4", "--review-completed", "--review-positive",
        "--review-scope-complete", "--verdict", "ready",
    )
    assert request["review_independence"] == "cross-family"
    assert request["acceptance_status"] == "provisional"


def test_unknown_backend_remains_traceable_without_acceptance(tmp_path: Path) -> None:
    request, _, _ = save_trace(
        tmp_path, "--backend", "mystery-backend", "--executor-model", "gpt-6-astra",
        "--reported-reviewer-model", "grok-4.7-build", "--review-completed", "--review-positive",
        "--review-scope-complete", "--verdict", "ready",
    )
    assert request["backend"] == "mystery-backend"
    assert request["acceptance_status"] == "provisional"


def test_call_assurance_does_not_reuse_initial_run_identity_or_acceptance(tmp_path: Path) -> None:
    _, _, initial = save_trace(
        tmp_path, "--backend", "grok", "--executor-model", "gpt-6-astra",
        "--reported-reviewer-model", "grok-4.7-build", "--review-completed", "--review-positive",
        "--review-scope-complete", "--verdict", "ready",
    )
    request, meta, run_meta = save_trace(
        tmp_path, "--backend", "claude-code", "--executor-model", "deepseek-v3",
        "--reported-reviewer-model", "deepseek-flash", "--status", "error",
    )
    assert run_meta == initial
    for artifact in (request, meta):
        assert artifact["reviewer_model"] == "deepseek-flash"
        assert artifact["review_independence"] == "same-family"
        assert artifact["acceptance_status"] == "provisional"
        assert artifact["status"] == "error"


@pytest.mark.parametrize("model", [
    "gpt-6-astra", "claude-opus-5-5-high", "gemini-4-argon-high", "deepseek-flash",
    "kimi-k2.5", "qwen3.6-plus", "glm-5.2", "MiniMax-M2.7", "mimo-v2.5-pro",
    "doubao-pro-4k", "grok-4.7-build", "llama-4", "mistral-large",
    "ollama/deepseek-r1", "claude-gpt-4", "mystery-model",
])
def test_trace_gate_and_provenance_recognize_the_same_families(tmp_path: Path, model: str) -> None:
    request, _, _ = save_trace(tmp_path, "--reported-reviewer-model", model)
    assert request["reviewer_family"] == review_gate.derive_model_family(model) == provenance.model_family(model)
