#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_test.py — 验证全部 118 个 Skill 完整性
用途：交付前的烟雾测试（smoke test）
适用：CI / 本地快速验证
作者：QwenPaw 数模竞赛工具集
"""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"


# 8 个核心 Skill 必备文件清单（带 Python 脚本检查）
CORE_REQUIREMENTS = {
    "problem-selection": {
        "must_exist": ["SKILL.md"],
        "tool_files": ["score.py", "model_recommender.py"],
        "min_total_size": 5000,
    },
    "problem-analysis": {
        "must_exist": ["SKILL.md"],
        "min_total_size": 1000,
    },
    "data-processing": {
        "must_exist": ["SKILL.md"],
        "min_total_size": 1000,
    },
    "model-building": {
        "must_exist": ["SKILL.md"],
        "min_total_size": 1000,
    },
    "model-innovation": {
        "must_exist": ["SKILL.md"],
        "tool_files": ["arxiv_miner.py", "novelty_checker.py"],
        "min_total_size": 5000,
    },
    "visualization": {
        "must_exist": ["SKILL.md"],
        "min_total_size": 1000,
    },
    "paper-writing": {
        "must_exist": ["SKILL.md"],
        "min_total_size": 1000,
    },
    "team-coordination": {
        "must_exist": ["SKILL.md"],
        "tool_files": ["timeline_96h.py"],
        "min_total_size": 5000,
    },
}


def check_skill(skill_name: str, requirements: dict) -> tuple:
    """检查单个 Skill 文件级完整性"""
    skill_dir = SKILLS_DIR / skill_name
    if not skill_dir.exists():
        return False, [f"Skill 目录不存在: {skill_dir}"], 0

    errors = []
    total_size = 0
    files = list(skill_dir.iterdir())

    existing_names = {f.name for f in files}
    for must in requirements["must_exist"]:
        if must not in existing_names:
            errors.append(f"  缺少文件: {must}")
    for tool_file in requirements.get("tool_files", []):
        tool_path = PROJECT_ROOT / "tools" / tool_file
        if not tool_path.is_file():
            errors.append(f"  tools/ 缺少文件: {tool_file}")
        else:
            total_size += tool_path.stat().st_size

    for f in files:
        if f.is_file():
            total_size += f.stat().st_size

    if total_size < requirements["min_total_size"]:
        errors.append(f"  总大小 {total_size} < 最小 {requirements['min_total_size']}")

    return len(errors) == 0, errors, total_size


def check_skill_dir_exists(skill_name: str) -> tuple:
    """检查 Skill 目录和 SKILL.md 是否存在"""
    skill_dir = SKILLS_DIR / skill_name
    if not skill_dir.exists():
        return False, "目录不存在"
    if not (skill_dir / "SKILL.md").exists():
        return False, "缺少 SKILL.md"
    sk = skill_dir / "SKILL.md"
    sz = sk.stat().st_size
    if sz < 500:
        return False, f"SKILL.md 过小 ({sz} bytes)"
    return True, f"SKILL.md {sz} bytes"


def main():
    print("=" * 72)
    print("  QwenPaw 数模工具集 - 烟雾测试（118 个 Skill）")
    print("=" * 72)
    print()

    # === Part 1: 8 个核心 Skill 详细检查 ===
    print("--- 8 个核心 Skill 详细检查 ---")
    print()
    core_passed = 0
    core_failed = 0

    for skill_name, requirements in CORE_REQUIREMENTS.items():
        ok, errors, size = check_skill(skill_name, requirements)
        flags = ", ".join(requirements["must_exist"])
        if ok:
            print(f"  [PASS] {skill_name} ({size}b) [{flags}]")
            core_passed += 1
        else:
            print(f"  [FAIL] {skill_name}")
            for e in errors:
                print(e)
            core_failed += 1

    print()

    # === Part 2: 全部 118 个 Skill SKILL.md 快速检查 ===
    print("--- 全部 118 个 Skill 快速检查 ---")
    print()

    # 核心 Skill 排除（已在 Part 1）
    core_skills = set(CORE_REQUIREMENTS.keys())
    excluded_dirs = {"_utils", "shared-scripts"}
    all_skills = sorted(d.name for d in SKILLS_DIR.iterdir() if d.is_dir() and d.name not in excluded_dirs)

    all_passed = 0
    all_failed = 0
    all_checked = 0

    for skill_name in all_skills:
        ok, msg = check_skill_dir_exists(skill_name)
        if ok:
            if skill_name not in core_skills:
                all_passed += 1
            all_checked += 1
            print(f"  [PASS] {skill_name}: {msg}" if skill_name not in core_skills else None)
        else:
            all_failed += 1
            print(f"  [FAIL] {skill_name}: {msg}")

    # Suppress individual pass lines for non-core to keep output manageable
    # Just show summary
    print()
    total_passed = core_passed + all_passed
    total_failed = core_failed + all_failed
    total_skills = len(all_skills)

    print("=" * 72)
    print(f"  核心文件检查: {core_passed}/{len(CORE_REQUIREMENTS)} PASS")
    print(f"  全部 SKILL.md: {total_passed}/{total_skills} PASS")
    print(f"  失败: {total_failed}")
    print(f"  总计: {total_skills} 个 Skill 目录")
    print("=" * 72)
    print()

    if total_failed == 0:
        print("[PASS] 全部 Skill 就绪")
        sys.exit(0)
    else:
        print(f"[FAIL] {total_failed} 个 Skill 不完整")
        sys.exit(1)


if __name__ == "__main__":
    main()
