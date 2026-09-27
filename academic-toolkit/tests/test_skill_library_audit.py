"""skill_library_audit 引用清洗回归（2026-09-28 粗体引用漏扫盲区修复钉住）。

盲区：'**references/x.md**' 粗体引用的尾随 '**' 曾未被剥离，
_dynamic_placeholder 见 '*' 即判动态占位符 → 整类引用静默漏扫。
"""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import skill_library_audit as sla  # noqa: E402


def test_bold_wrapped_ref_is_cleaned_not_treated_as_wildcard():
    raw = "references/code-review-best-practices.md**"
    cleaned = sla._clean_ref(raw)
    assert cleaned == "references/code-review-best-practices.md", cleaned
    assert sla._dynamic_placeholder(cleaned) is False, "粗体星号不得触发通配豁免"


def test_double_bold_wrapped_ref_is_cleaned():
    assert sla._clean_ref("scripts/pr-analyzer.py**") == "scripts/pr-analyzer.py"


def test_true_midpath_glob_still_exempted():
    cleaned = sla._clean_ref("references/recipes/*.md")
    assert "*" in cleaned
    assert sla._dynamic_placeholder(cleaned) is True, "路径中段通配仍是动态占位符"


def test_trailing_punct_stripping_unchanged():
    assert sla._clean_ref("references/x.md).") == "references/x.md"
    assert sla._clean_ref("references/x.md”") == "references/x.md"
