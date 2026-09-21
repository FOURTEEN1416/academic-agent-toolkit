# -*- coding: utf-8 -*-
"""B1-6 回归：lint 棘轮 scope 的可移植语法（repo: 前缀 + 绝对路径规范化）。

修复前：data/lint_baseline.json 的 scope 混入本机绝对路径
`D:\\Desktop\\学术工作流\\tests`——tracked 基线不可移植，换机即失效。
"""
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import lint_ratchet  # noqa: E402


def test_resolve_scope_repo_prefix():
    assert lint_ratchet.resolve_scope("repo:tests") == \
        lint_ratchet.REPO_ROOT / "tests"


def test_resolve_scope_bare_name_is_toolbox_relative():
    assert lint_ratchet.resolve_scope("tools") == lint_ratchet.TOOLBOX_ROOT / "tools"
    assert lint_ratchet.resolve_scope("engine") == lint_ratchet.TOOLBOX_ROOT / "engine"


def test_normalize_scope_entry_abs_path_under_repo():
    abs_path = lint_ratchet.REPO_ROOT / "tests"
    assert lint_ratchet.normalize_scope_entry(str(abs_path)) == "repo:tests"


def test_normalize_scope_entry_bare_name_unchanged():
    assert lint_ratchet.normalize_scope_entry("hooks") == "hooks"


def test_baseline_scope_is_portable():
    """tracked 基线内不得再出现本机绝对路径。"""
    baseline = lint_ratchet._load_baseline()
    for entry in baseline.get("scope", []):
        assert not Path(entry).is_absolute(), f"基线 scope 仍含绝对路径: {entry}"
    assert "repo:tests" in baseline["scope"], "仓库根 tests 未以 repo: 形态登记"
