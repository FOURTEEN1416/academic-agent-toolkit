"""oral-paper-skill 整技能收编契约（2026-09-22 A 批次）。

钉住四件事，防未来编辑静默破坏：
1. SKILL.md 适配块结构（触发/契约/质量铁律/数模桥接表/STEP_MANIFEST + 上游原文逐字保留起点）；
2. references/UPSTREAM.md 溯源三字段 + pinned 哈希 + license 未声明的如实标注（不得虚标 MIT）；
3. catalog 映射（academic_papers / experimental / routed / associated_skills 含自身）；
4. 上游四参考件在位。
"""
from __future__ import annotations

import json
from pathlib import Path

TOOLBOX = Path(__file__).resolve().parents[1]
SKILL_DIR = TOOLBOX / "skills" / "oral-paper-skill"
CATALOG = TOOLBOX.parent / "capabilities" / "catalog.json"

PINNED = "a2c4bc41b3aa6946b2ccce1c844ce9936ef83308"
REFERENCE_FILES = (
    "abstract-derived-practices.md",
    "archetypes.md",
    "oral-patterns.md",
    "review-scorecard.md",
)


def test_skill_md_adapter_block_structure() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "---\nname: oral-paper-skill" in text, "frontmatter name 缺失或不匹配目录名"
    for marker in (
        "本仓适配：输入/输出契约与触发条件",
        "触发条件（本仓场景）",
        "输出契约（两模式二选一，按用户请求）",
        "质量铁律（上游纪律，本仓强化）",
        "数模/通用桥接表",
        "STEP_MANIFEST 产出声明",
    ):
        assert marker in text, f"适配块缺段: {marker}"
    assert "# Oral Paper Skill" in text, "上游原文起点标题丢失"
    assert "Do not default to GO/WAIT/KILL" in text, "上游正文尾部丢失（适配块外正文被截断？）"


def test_upstream_md_provenance_and_honest_license() -> None:
    text = (SKILL_DIR / "references" / "UPSTREAM.md").read_text(encoding="utf-8")
    for field in ("Upstream:", "Pinned commit:", "License:"):
        assert field in text, f"溯源缺字段: {field}"
    assert "github.com/Adkid-Zephyr/oral-paper-skill" in text, "上游 URL 缺失"
    assert PINNED in text, f"pinned 哈希不符: 应为 {PINNED}"
    license_line = next(line for line in text.splitlines() if line.startswith("- License:"))
    assert "未声明" in license_line, "license 行必须如实标注上游未声明，禁止虚标 MIT/Apache"


def test_upstream_reference_files_present() -> None:
    for name in REFERENCE_FILES:
        assert (SKILL_DIR / "references" / name).is_file(), f"上游参考件缺失: {name}"


def test_catalog_entry_mapping() -> None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = [e for e in data.get("academic_papers", [])
               if e.get("capability_id") == "oral-paper-skill"]
    assert len(entries) == 1, "catalog 缺 oral-paper-skill 条目（或重复）"
    entry = entries[0]
    assert entry["domain"] == "academic_papers"
    assert entry["status"] == "experimental"
    assert entry["disposition"] == "routed"
    assert "oral-paper-skill" in entry["associated_skills"], "associated_skills 必须含自身"
    assert "无 LICENSE" in entry["upstream"], "upstream pin 必须如实登记 license 状态"
