# -*- coding: utf-8 -*-
"""技能库完整性回归（2026-08-29 补充验证轮）：frontmatter/编码/模板引用一致性。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from skill_library_audit import audit  # noqa: E402


def test_no_frontmatter_failures():
    rep = audit()
    assert not rep["failures"].get("frontmatter"), rep["failures"]["frontmatter"]


def test_no_encoding_pollution():
    rep = audit()
    assert not rep["failures"].get("encoding"), rep["failures"]["encoding"]


def test_no_unacknowledged_broken_refs():
    rep = audit()
    assert not rep["failures"].get("broken_ref"), rep["failures"]["broken_ref"]


def test_templates_reference_existing_skills():
    rep = audit()
    assert not rep["failures"].get("template_missing_skill"), rep["failures"]["template_missing_skill"]
