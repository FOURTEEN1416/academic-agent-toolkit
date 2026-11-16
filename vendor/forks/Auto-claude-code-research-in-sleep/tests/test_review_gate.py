from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "review_gate.py"
SPEC = importlib.util.spec_from_file_location("review_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
review_gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = review_gate
SPEC.loader.exec_module(review_gate)


@pytest.mark.parametrize("verdict", ["ready", "almost"])
def test_default_codex_positive_stops_without_executor_identity(verdict: str) -> None:
    transition = review_gate.evaluate_transition(
        round_backend="codex",
        score=7,
        verdict=verdict,
    )

    assert transition.decision == "stop"
    assert transition.requires_external_acquittal is False
    assert transition.identity_assurance == "not_required"


def test_default_codex_gate_does_not_require_native_helper(tmp_path: Path) -> None:
    standalone_gate = tmp_path / "review_gate.py"
    shutil.copy2(MODULE_PATH, standalone_gate)

    result = subprocess.run(
        [
            sys.executable,
            str(standalone_gate),
            "--round-backend",
            "codex",
            "--score",
            "7",
            "--verdict",
            "ready",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["decision"] == "stop"


@pytest.mark.parametrize("backend", ["oracle-pro", "agy"])
def test_existing_external_backend_positive_contract_is_preserved(backend: str) -> None:
    transition = review_gate.evaluate_transition(
        round_backend=backend,
        score=7,
        verdict="ready",
    )

    assert transition.decision == "stop"
    assert transition.identity_assurance == "not_required"


def test_high_score_not_ready_does_not_stop() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="codex",
        score=9,
        verdict="not ready",
    )

    assert transition.decision == "continue"
    assert transition.next_backend == "codex"


@pytest.mark.parametrize("score", [0, 11, float("nan"), float("inf")])
def test_invalid_score_fails_closed(score: float) -> None:
    transition = review_gate.evaluate_transition(
        round_backend="codex",
        score=score,
        verdict="ready",
    )

    assert transition.decision == "review_unavailable"


@pytest.mark.parametrize(
    ("executor_model", "expected_backend"),
    [("claude-sonnet-4.5", "codex"), ("gemini-3.1-pro", "codex"), ("gpt-5.4", "manual")],
)
def test_copilot_positive_escalates_to_policy_finalizer(
    executor_model: str, expected_backend: str
) -> None:
    availability = (
        {"manual_available": True}
        if expected_backend == "manual"
        else {"codex_available": True}
    )
    transition = review_gate.evaluate_transition(
        round_backend="copilot",
        score=8,
        verdict="ready",
        executor_model=executor_model,
        **availability,
    )

    assert transition.decision == "escalate"
    assert transition.next_backend == expected_backend
    assert transition.requires_external_acquittal is True
    assert transition.identity_assurance == "caller_declared"


def test_copilot_positive_fails_closed_for_unknown_executor() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="copilot",
        score=8,
        verdict="ready",
        executor_model="mystery-model",
    )

    assert transition.decision == "review_unavailable"


def test_copilot_positive_fails_closed_when_no_finalizer_is_confirmed() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="copilot",
        score=8,
        verdict="ready",
        executor_model="claude-sonnet-4.5",
    )

    assert transition.decision == "review_unavailable"


def test_non_openai_copilot_route_falls_back_to_manual_when_codex_is_unavailable() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="copilot",
        score=8,
        verdict="ready",
        executor_model="claude-sonnet-4.5",
        codex_available=False,
        manual_available=True,
    )

    assert transition.decision == "escalate"
    assert transition.next_backend == "manual"


def test_openai_copilot_route_fails_when_manual_is_unavailable() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="copilot",
        score=8,
        verdict="ready",
        executor_model="gpt-5.4",
        manual_available=False,
    )

    assert transition.decision == "review_unavailable"


def test_copilot_cannot_resume_after_finalizer_obligation_is_set() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="copilot",
        score=5,
        verdict="not ready",
        requires_external_acquittal=True,
        executor_model="claude-sonnet-4.5",
    )

    assert transition.decision == "review_unavailable"


def test_copilot_negative_stays_on_copilot() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="copilot",
        score=5,
        verdict="not ready",
        executor_model="claude-sonnet-4.5",
    )

    assert transition.decision == "continue"
    assert transition.next_backend == "copilot"
    assert transition.requires_external_acquittal is False


def _native_evidence(*, score: float = 8, verdict: str = "ready"):
    return review_gate.NativeEvidence(
        evidence_id="cne_test",
        executor_model="claude-sonnet-4.6",
        reviewer_model="gpt-5.5",
        score=score,
        verdict=verdict,
    )


def test_native_copilot_positive_stops_without_external_finalizer() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="copilot-native",
        score=8,
        verdict="ready",
        native_evidence=_native_evidence(),
    )

    assert transition.decision == "stop"
    assert transition.requires_external_acquittal is False
    assert transition.identity_assurance == "host_event_verified"


def test_native_copilot_negative_continues_on_native_backend() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="copilot-native",
        score=5,
        verdict="not ready",
        native_evidence=_native_evidence(score=5, verdict="not ready"),
    )

    assert transition.decision == "continue"
    assert transition.next_backend == "copilot-native"
    assert transition.identity_assurance == "host_event_verified"


def test_native_copilot_missing_evidence_fails_closed() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="copilot-native",
        score=8,
        verdict="ready",
    )

    assert transition.decision == "review_unavailable"
    assert transition.identity_assurance == "unverified"


def test_native_evidence_cannot_be_attached_to_another_backend() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="codex",
        score=8,
        verdict="ready",
        native_evidence=_native_evidence(),
    )

    assert transition.decision == "review_unavailable"
    assert transition.identity_assurance == "failed"


@pytest.mark.parametrize(
    ("score", "verdict"),
    [(7, "ready"), (8, "almost"), (8, "not ready")],
)
def test_native_copilot_declared_assessment_must_match_bound_response(
    score: float, verdict: str
) -> None:
    transition = review_gate.evaluate_transition(
        round_backend="copilot-native",
        score=score,
        verdict=verdict,
        native_evidence=_native_evidence(),
    )

    assert transition.decision == "review_unavailable"
    assert transition.identity_assurance == "failed"


@pytest.mark.parametrize(
    ("model", "expected_family"),
    [
        ("gpt-5.4", "openai"),
        ("claude-sonnet-4.5", "anthropic"),
        ("gemini-3.1-pro", "google"),
        ("mystery-model", "unknown"),
        ("gpt-5.4-claude", "unknown"),
    ],
)
def test_model_family_is_derived_fail_closed(model: str, expected_family: str) -> None:
    assert review_gate.derive_model_family(model) == expected_family


def test_gate_does_not_accept_caller_supplied_family_labels() -> None:
    parameters = inspect.signature(review_gate.evaluate_transition).parameters
    parser_destinations = {action.dest for action in review_gate.build_parser()._actions}

    assert "executor_family" not in parameters
    assert "reviewer_family" not in parameters
    assert "executor_family" not in parser_destinations
    assert "reviewer_family" not in parser_destinations


def test_codex_finalizer_positive_stops_but_identity_remains_declared() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="codex",
        score=7,
        verdict="ready",
        requires_external_acquittal=True,
        executor_model="claude-sonnet-4.5",
        reviewer_model="gpt-6-astra",
    )

    assert transition.decision == "stop"
    assert transition.requires_external_acquittal is False
    assert transition.identity_assurance == "caller_declared"


def test_same_family_finalizer_fails_closed() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="codex",
        score=7,
        verdict="ready",
        requires_external_acquittal=True,
        executor_model="gpt-5.4",
        reviewer_model="gpt-6-astra",
    )

    assert transition.decision == "review_unavailable"
    assert transition.identity_assurance == "failed"


def test_manual_finalizer_requires_reported_identity() -> None:
    missing = review_gate.evaluate_transition(
        round_backend="manual",
        score=7,
        verdict="ready",
        requires_external_acquittal=True,
        executor_model="gpt-5.4",
        reviewer_model="claude-sonnet-4.5",
        manual_identity_reported=False,
    )
    present = review_gate.evaluate_transition(
        round_backend="manual",
        score=7,
        verdict="ready",
        requires_external_acquittal=True,
        executor_model="gpt-5.4",
        reviewer_model="claude-sonnet-4.5",
        manual_identity_reported=True,
    )

    assert missing.decision == "review_unavailable"
    assert present.decision == "stop"


def test_explicit_manual_positive_still_rejects_same_family() -> None:
    transition = review_gate.evaluate_transition(
        round_backend="manual",
        score=7,
        verdict="ready",
        executor_model="gpt-5.4",
        reviewer_model="gpt-6-astra",
        manual_identity_reported=True,
    )

    assert transition.decision == "review_unavailable"
    assert transition.identity_assurance == "failed"


NEW_REVIEWERS = [
    ("antigravity", "claude-opus-5-5-high"),
    ("grok", "grok-4.7-build"),
    ("claude-code", "deepseek-flash"),
]


def _reported_review(backend: str, reviewer: str, **overrides):
    arguments = dict(
        round_backend=backend, score=8, verdict="ready",
        executor_model="gpt-6-astra", reviewer_model=reviewer,
        review_completed=True, review_scope_complete=True, review_status="ok",
    )
    arguments.update(overrides)
    return review_gate.evaluate_transition(**arguments)


@pytest.mark.parametrize(("backend", "reviewer"), NEW_REVIEWERS)
def test_completed_reported_cross_family_review_accepts(backend: str, reviewer: str) -> None:
    result = _reported_review(backend, reviewer)
    assert result.decision == "stop"
    assert result.review_independence == "cross-family"
    assert result.acceptance_status == "accepted"
    assert result.identity_assurance == "caller_declared"


@pytest.mark.parametrize(("backend", "reviewer"), NEW_REVIEWERS)
def test_same_family_review_can_stop_drive_only_provisionally(backend: str, reviewer: str) -> None:
    result = _reported_review(backend, reviewer, executor_model=reviewer)
    assert result.decision == "stop"
    assert result.review_independence == "same-family"
    assert result.acceptance_status == "provisional"


@pytest.mark.parametrize(("backend", "reviewer"), NEW_REVIEWERS)
@pytest.mark.parametrize(("score", "verdict"), [(8, "not ready"), (5, "ready")])
def test_completed_negative_review_continues_provisionally(
    backend: str, reviewer: str, score: float, verdict: str,
) -> None:
    result = _reported_review(backend, reviewer, score=score, verdict=verdict)
    assert result.decision == "continue"
    assert result.next_backend == backend
    assert result.acceptance_status == "provisional"


@pytest.mark.parametrize(("backend", "reviewer"), NEW_REVIEWERS)
@pytest.mark.parametrize("overrides", [
    {"review_completed": False},
    {"review_scope_complete": False},
    {"review_status": "error"},
    {"review_status": ""},
    {"reviewer_model": ""},
    {"reviewer_model": "mystery-reviewer"},
    {"executor_model": "mystery-executor"},
])
def test_failed_or_incomplete_review_is_unavailable_even_when_negative(
    backend: str, reviewer: str, overrides: dict,
) -> None:
    result = _reported_review(backend, reviewer, verdict="not ready", **overrides)
    assert result.decision == "review_unavailable"
    assert result.acceptance_status == "provisional"


@pytest.mark.parametrize(("backend", "reviewer"), NEW_REVIEWERS)
@pytest.mark.parametrize("verdict", ["ready", "not ready"])
def test_new_routes_cannot_discharge_a_copilot_finalizer_obligation(
    backend: str, reviewer: str, verdict: str,
) -> None:
    result = _reported_review(backend, reviewer, verdict=verdict, requires_external_acquittal=True)
    assert result.decision == "review_unavailable"
    assert result.requires_external_acquittal is True
    assert result.acceptance_status == "provisional"


@pytest.mark.parametrize("status", ["ok", "fallback_used", "SUCCESS", "completed"])
def test_reported_route_accepts_successful_status_spellings(status: str) -> None:
    assert _reported_review("grok", "grok-4.7-build", review_status=status).acceptance_status == "accepted"


@pytest.mark.parametrize(("backend", "reviewer"), NEW_REVIEWERS)
def test_reported_route_cli_requires_explicit_completion_and_scope(backend: str, reviewer: str) -> None:
    base = [sys.executable, str(MODULE_PATH), "--round-backend", backend,
            "--score", "8", "--verdict", "ready", "--executor-model", "gpt-6-astra",
            "--reviewer-model", reviewer, "--review-status", "success"]
    missing = subprocess.run(base, capture_output=True, text=True, check=True)
    complete = subprocess.run(base + ["--review-completed", "--review-scope-complete"],
                              capture_output=True, text=True, check=True)
    assert json.loads(missing.stdout)["decision"] == "review_unavailable"
    assert json.loads(complete.stdout)["acceptance_status"] == "accepted"
