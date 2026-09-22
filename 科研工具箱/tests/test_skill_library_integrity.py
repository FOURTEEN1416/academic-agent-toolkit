# -*- coding: utf-8 -*-
"""技能库完整性回归（2026-08-29 补充验证轮）：frontmatter/编码/模板引用一致性。

B3-8（2026-09-22）：audit() 全库扫描 258+ SKILL.md，此前 6 个测试各自无缓存调用
（×6 全量重扫）——改为 module 级 fixture 缓存一次共享。CI 独立 step 保留双保险不变。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from skill_library_audit import audit  # noqa: E402


@pytest.fixture(scope="module")
def audit_report():
    return audit()


def test_no_frontmatter_failures(audit_report):
    rep = audit_report
    assert not rep["failures"].get("frontmatter"), rep["failures"].get("frontmatter")


def test_no_encoding_pollution(audit_report):
    rep = audit_report
    assert not rep["failures"].get("encoding"), rep["failures"].get("encoding")


def test_no_unacknowledged_broken_refs(audit_report):
    rep = audit_report
    assert not rep["failures"].get("broken_ref"), rep["failures"].get("broken_ref")


def test_no_new_unregistered_broken_inner_refs(audit_report):
    """技能内部引用断链棘轮：asset_gap_register.json 登记的 2026-09-09 存量豁免，
    新增断链（SKILL.md 引用了既不存在也无声明的内部文件）必须 FAIL。"""
    rep = audit_report
    assert not rep["failures"].get("broken_inner_ref"), rep["failures"].get("broken_inner_ref", [])[:10]


def test_templates_reference_existing_skills(audit_report):
    rep = audit_report
    assert not rep["failures"].get("template_missing_skill"), rep["failures"].get("template_missing_skill")


def test_no_name_mismatch_or_duplicates(audit_report):
    """frontmatter name 必须等于目录名，且全库无重名（防宿主发现遮蔽）。"""
    rep = audit_report
    assert not rep["failures"].get("name_mismatch"), rep["failures"].get("name_mismatch", [])[:5]
    assert not rep["failures"].get("name_duplicate"), rep["failures"].get("name_duplicate")
