from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SRC = ROOT / "packages" / "runtime-core" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from vgo_runtime.grade_intent import suggest_internal_grade


def test_suggest_internal_grade_marks_execution_like_work_as_l() -> None:
    assert suggest_internal_grade("coding", task="implement the approved plan") == "L"


def test_suggest_internal_grade_keeps_small_docs_prompt_at_m() -> None:
    assert suggest_internal_grade("planning", task="suffix cleanup in docs") == "M"


def test_suggest_internal_grade_marks_planning_heavy_prompt_as_l() -> None:
    assert suggest_internal_grade("planning", task="create PRD and backlog with quality gate") == "L"


def test_suggest_internal_grade_marks_cross_host_rollout_as_xl() -> None:
    task = "cross-host install to runtime end-to-end verification workflow"

    assert suggest_internal_grade("planning", task=task) == "XL"
