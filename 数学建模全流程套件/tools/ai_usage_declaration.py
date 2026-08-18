#!/usr/bin/env python3
"""
AI 工具使用声明生成器 v1.0
依据《全国大学生数学建模竞赛人工智能工具使用规定（2026年试行）》生成合规声明。

规定要点（2026-09-01 试行，来源 mcm.edu.cn 官方公告）：
1. 论文参考文献之前必须设置「AI工具使用声明」，二选一：
   - 未使用AI："本参赛队在竞赛过程中未使用任何AI工具。"
   - 使用AI："本参赛队在竞赛过程中使用了AI工具，主要用于【简要用途，如语言润色、代码调试等】，
     详细使用情况见支撑材料。"
2. 使用AI工具的参赛作品，支撑材料须包含「AI工具使用详情.pdf」，内容包括：
   (1) 所用AI工具名称、版本或型号
   (2) 具体使用目的和环节
   (3) 主要提示方式与使用过程说明（可附典型交互示例）
   (4) 对AI输出的采纳、人工修改和核验的主要情况（语言润色除外）
3. 故意隐瞒或虚假声明 → 取消评奖资格

输出：
- 论文内声明段（LaTeX 片段，插在参考文献前）
- AI工具使用详情.md（转 PDF 后作为支撑材料）

用法：
python tools/ai_usage_declaration.py --used --usage "语言润色、代码调试、文献检索" \
    --output <工作区>/AI使用声明
"""

import argparse
import json
import os
import sys
from datetime import datetime


TEMPLATE_USED = """本参赛队在竞赛过程中使用了AI工具，主要用于{usage}，详细使用情况见支撑材料。"""

TEMPLATE_NOT_USED = """本参赛队在竞赛过程中未使用任何AI工具。"""

DETAIL_MD_TEMPLATE = """# AI工具使用详情

> 依据《全国大学生数学建模竞赛人工智能工具使用规定（2026年试行）》第4条编制。
> 本文件随支撑材料提交，文件名为"AI工具使用详情.pdf"。

## 一、所用AI工具名称、版本或型号

| 工具名称 | 版本/型号 | 用途分类 |
|---------|----------|---------|
{tools_table}

## 二、具体使用目的和环节

{usage_detail}

## 三、主要提示方式与使用过程说明

{prompt_detail}

### 典型交互示例

{examples}

## 四、对AI输出的采纳、人工修改和核验情况

{verification}

---
生成时间：{timestamp}
"""


def build_declaration(used: bool, usage: str) -> str:
    """生成论文内声明段（插在参考文献之前）"""
    if used:
        body = TEMPLATE_USED.format(usage=usage or "语言润色、代码调试等")
    else:
        body = TEMPLATE_NOT_USED
    latex = (
        "\\section*{AI工具使用声明}\n"
        f"{body}\n"
        "% 依据《全国大学生数学建模竞赛人工智能工具使用规定（2026年试行）》\n"
    )
    return latex


def build_detail_md(usage: str, tools: list, usage_detail: str,
                    prompt_detail: str, examples: str, verification: str) -> str:
    """生成 AI工具使用详情.md（供转PDF）"""
    if not tools:
        tools = [{"name": "（自行填写）", "version": "（自行填写）", "category": "（语言润色/代码调试/文献检索等）"}]
    table_rows = "\n".join(
        f"| {t.get('name','')} | {t.get('version','')} | {t.get('category','')} |" for t in tools
    )
    return DETAIL_MD_TEMPLATE.format(
        tools_table=table_rows,
        usage=usage or "（填写：语言润色、代码调试、文献检索、图表绘制建议等）",
        usage_detail=usage_detail or "（填写：在哪些环节使用了AI，例如——\n1. 模型求解阶段：使用AI调试Python求解代码；\n2. 论文写作阶段：使用AI润色语言表达；\n3. 文献检索阶段：使用AI辅助检索与筛选参考文献。）",
        prompt_detail=prompt_detail or "（填写：主要提示方式与过程说明，例如——\n以自然语言向工具描述需求，工具返回结果后由队员人工审查。提示词均围绕具体技术问题，不涉及赛题核心建模结论。）",
        examples=examples or "（可选：附1-2条典型交互示例，如——\n提问：「请帮我检查这段Python代码的语法错误」\n工具回答：「第X行缺少冒号，已修正为...」\n处理方式：人工核对后采纳。）",
        verification=verification or "（填写：对AI输出的采纳、人工修改和核验情况，例如——\n1. 代码：所有AI生成的代码均经人工逐行审查并运行验证；\n2. 文本：AI润色内容经全文复核，核心建模分析均由队员完成；\n3. 数据：所有计算结果均与题目数据独立核对。）",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def main():
    parser = argparse.ArgumentParser(description="AI工具使用声明生成器（2026国赛新规）")
    parser.add_argument("--used", action="store_true", help="使用了AI工具（默认未使用）")
    parser.add_argument("--usage", default="", help="简要用途，如「语言润色、代码调试」")
    parser.add_argument("--tools", default="", help="工具列表JSON: [{'name':'ChatGPT','version':'4o','category':'代码调试'}]")
    parser.add_argument("--output", default=".", help="输出目录（默认当前目录）")
    args = parser.parse_args()

    out_dir = args.output
    os.makedirs(out_dir, exist_ok=True)

    # 1. 论文内声明段
    decl = build_declaration(args.used, args.usage)
    decl_path = os.path.join(out_dir, "AI工具使用声明.tex")
    with open(decl_path, "w", encoding="utf-8") as f:
        f.write(decl)
    print(f"论文内声明段已生成: {decl_path}")
    print("---- 内容预览 ----")
    print(decl)
    print("------------------")

    # 2. 使用详情（仅使用AI时需要）
    if args.used:
        tools = []
        if args.tools:
            try:
                tools = json.loads(args.tools)
            except json.JSONDecodeError:
                print("警告: --tools 解析失败，将使用占位符")
        detail = build_detail_md(args.usage, tools, "", "", "", "")
        detail_path = os.path.join(out_dir, "AI工具使用详情.md")
        with open(detail_path, "w", encoding="utf-8") as f:
            f.write(detail)
        print(f"\nAI工具使用详情已生成: {detail_path}")
        print("注意: 请将 AI工具使用详情.md 转为 PDF（文件名「AI工具使用详情.pdf」）放入支撑材料压缩包，并补全【】中的待填写内容。")
    else:
        print("\n已选择「未使用AI工具」声明。注意：如实际使用了AI，必须如实声明，隐瞒将取消评奖资格。")

    # 提示插入位置
    print("\n=== 使用说明 ===")
    print("1. 将 AI工具使用声明.tex 内容插入论文「参考文献」之前（2026年规定第3条）。")
    print("2. 声明内容不允许修改措辞，二选一填写。")
    print("3. 使用AI的队：AI工具使用详情.pdf 放入支撑材料，正文引用标注AI使用位置（美赛2026新规同样要求）。")


if __name__ == "__main__":
    main()
