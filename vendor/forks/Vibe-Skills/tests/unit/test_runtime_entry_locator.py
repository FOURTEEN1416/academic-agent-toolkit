from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SRC = REPO_ROOT / "packages" / "runtime-core" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from vgo_runtime.entry_locator import locate_iteration_entry, main


def test_locate_iteration_entry_returns_primary_file_for_hot_path_change_kinds() -> None:
    expected = {
        "task-understanding": "packages/runtime-core/src/vgo_runtime/kernel/task_card.py",
        "planning": "packages/runtime-core/src/vgo_runtime/kernel/planner.py",
        "execution": "packages/runtime-core/src/vgo_runtime/kernel/loop.py",
        "verification": "packages/runtime-core/src/vgo_runtime/kernel/verifier.py",
        "local-skill-extension": "skills/local/<new-skill>/SKILL.md",
    }

    for change_kind, primary_entry_file in expected.items():
        payload = locate_iteration_entry(repo_root=REPO_ROOT, change_kind=change_kind)
        assert payload["change_kind"] == change_kind
        assert payload["primary_entry_file"] == primary_entry_file
        assert payload["recommended_test_targets"]
        assert payload["focused_test_command"].startswith("py -3 -m pytest ")
        if change_kind == "local-skill-extension":
            assert payload["authority_layer"] == "skill_surface"
            assert payload["steady_state_contract"] == "local skill frontmatter plus generated/skills-index.json"
            assert payload["recommended_test_targets"] == [
                "tests/unit/test_local_skill_index.py",
                "tests/unit/test_local_kernel_planning.py",
            ]
        else:
            assert payload["authority_layer"] == "kernel"


def test_entry_locator_main_prints_json(capsys) -> None:
    assert main(["--repo-root", str(REPO_ROOT), "--change-kind", "planning"]) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["change_kind"] == "planning"
    assert payload["primary_entry_file"] == "packages/runtime-core/src/vgo_runtime/kernel/planner.py"
    assert payload["recommended_test_targets"] == ["tests/unit/test_local_kernel_planning.py"]
    assert payload["focused_test_command"] == "py -3 -m pytest tests/unit/test_local_kernel_planning.py -q"
