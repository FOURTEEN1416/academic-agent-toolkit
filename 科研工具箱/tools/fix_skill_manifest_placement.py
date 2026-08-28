#!/usr/bin/env python3
"""修复 P2 债务：数模域 SKILL.md 的 STEP_MANIFEST 声明块从文件末尾移到「关键规则/Key Rules」之前。

背景：backfill 脚本因锚点标题含 emoji（## ⛔⛔⛔ 完成铁律）未匹配，声明块被追加到文件末尾。
本次修复按公认最优解：声明块（输出契约性质）应位于「关键规则/Key Rules」章节之前，
与 paper-write（14% 位置）等合理插入点保持一致。幂等：已处于合理位置的跳过。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"

# 各文件的目标锚点标题（声明块插入到该标题之前）
ANCHORS = {
    "comp-prob-analysis": "## 关键规则",
    "comp-modeling": "## 关键规则",
    "comp-code": "## 关键规则",
    "comp-paper-zh": "## Key Rules",
    "comp-paper-en": "## Key Rules",
    "comp-compile-zh": "## Key Rules",
    "comp-compile-en": "## Key Rules",
    # comp-review 无关键规则章节，插到 Step 4 硬门禁之前
    "comp-review": "## Step 4: 硬门禁",
}

DECL_HEAD = "## STEP_MANIFEST 产出声明"


def extract_decl_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """提取从 start 开始的声明块（到下一个 ## 标题或文件末尾），返回 (块内容, 块结束行号)。"""
    end = start
    while end < len(lines):
        if end > start and lines[end].startswith("## "):
            break
        end += 1
    # 去掉块尾多余空行
    block = lines[start:end]
    while block and block[-1].strip() == "":
        block.pop()
    return block, end


def fix_file(skill_name: str) -> str:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    if not path.exists():
        return f"{skill_name}: SKILL.md 不存在，跳过"

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 找声明块
    decl_idx = [i for i, l in enumerate(lines) if l.strip() == DECL_HEAD]
    if not decl_idx:
        return f"{skill_name}: 未找到 {DECL_HEAD}，跳过"
    decl_idx = decl_idx[0]

    # 找锚点
    anchor = ANCHORS[skill_name]
    anchor_idx = [i for i, l in enumerate(lines) if l.strip().startswith(anchor)]
    if not anchor_idx:
        return f"{skill_name}: 未找到锚点 {anchor!r}，跳过"
    anchor_idx = anchor_idx[0]

    # 幂等：声明块已在锚点之前（位置合理）→ 跳过
    if decl_idx < anchor_idx:
        return f"{skill_name}: 声明块已在合理位置（行 {decl_idx + 1} < 锚点 {anchor_idx + 1}），跳过"

    block, end = extract_decl_block(lines, decl_idx)

    # 删除原位置（保留一个空行分隔）
    new_lines = lines[:decl_idx] + lines[end:]
    # 清理可能产生的连续空行
    cleaned = []
    prev_blank = False
    for l in new_lines:
        blank = l.strip() == ""
        if blank and prev_blank:
            continue
        cleaned.append(l)
        prev_blank = blank
    new_lines = cleaned

    # 插入到锚点之前（前面补一个空行分隔）
    insert_at = new_lines.index(next(l for l in new_lines if l.strip().startswith(anchor)))
    insert = [""] + block + [""]
    new_lines = new_lines[:insert_at] + insert + new_lines[insert_at:]

    # 写回
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # 验证
    new_text = path.read_text(encoding="utf-8")
    if new_text.count(DECL_HEAD) != 1:
        return f"{skill_name}: ⚠️ 验证失败——声明块数量异常 ({new_text.count(DECL_HEAD)})"
    new_lines2 = new_text.splitlines()
    new_decl = [i for i, l in enumerate(new_lines2) if l.strip() == DECL_HEAD][0]
    new_anchor = [i for i, l in enumerate(new_lines2) if l.strip().startswith(anchor)][0]
    if new_decl > new_anchor:
        return f"{skill_name}: ⚠️ 验证失败——声明块仍在锚点之后"
    ratio = new_decl / len(new_lines2)
    return f"{skill_name}: ✅ 已移动（行 {decl_idx + 1} → {new_decl + 1}，位置 {ratio:.0%}）"


def main():
    results = []
    for skill in ANCHORS:
        results.append(fix_file(skill))
    print("\n".join(results))


if __name__ == "__main__":
    main()