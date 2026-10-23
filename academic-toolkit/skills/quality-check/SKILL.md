---
name: quality-check
description: "学术写作质量审查。检查论文/报告的字数、结构、引用、格式问题并生成审查报告。Use when user says \"质量检查\", \"quality check\", \"审稿\", \"review\"."
argument-hint: [target-source-file]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# 学术写作质量审查

对以下正文文档（Markdown 或 LaTeX 源）进行质量审查：**$ARGUMENTS**

## 常量

- **TARGET_FILE** — 默认从 $ARGUMENTS 或自动检测
- **MIN_WORD_COUNT** / **MAX_WORD_COUNT** — 从 Additional Parameters 读取
- **MIN_REFERENCES** — 最少参考文献数（默认 10）

## 审查目标

借鉴 lunwen-skill final_checker + PaperSpine audit 的审查思路，对学术文档执行 6 个维度的检查：

1. **字数检查**：总字数 + 各章节字数分布
2. **结构完整性**：必需章节是否齐全
3. **参考文献**：数量、时间分布、格式合规
4. **图表**：图表标题、引用一致性
5. **格式规范**：Markdown 残留标记、首行缩进、标题层级
6. **语言风格**：AI 套话、空泛表述检测

## 工作流程

### Step 1: 自动检测目标文件

```bash
# 按优先级查找待审查的正文文件：编译产物本体（paper/main.*）优先。
# 竞赛主链与论文工作区的交付物都在 paper/；Windows 大小写不敏感，literature_review.md
# 会命中 LITERATURE_REVIEW.md，若排在前面会把 LaTeX 主链挤出自动检测。
TARGET_FILE=""; TARGET_KIND=""
for candidate in paper/main.tex paper/main.md PROPOSAL.md LITERATURE_REVIEW.md COURSE_PAPER.md COURSE_REPORT.md; do
    if [ -f "$candidate" ]; then
        echo "Found target: $candidate"
        TARGET_FILE="$candidate"
        case "$candidate" in
            *.tex) TARGET_KIND="latex" ;;
            *)     TARGET_KIND="markdown" ;;
        esac
        break
    fi
done
[ -z "$TARGET_FILE" ] && echo "ERROR: No target source found (looked for paper/main.tex, paper/main.md and course documents)" && exit 1
```

### Step 1b: LaTeX 分支（TARGET_KIND=latex）

存在 `paper/main.tex` 时按 LaTeX 主链审查：不再要求 `paper/main.md`，也不因缺少 Markdown 文件而 `exit 1`。取证只用仓库现有两个检查器，**不新增阻塞阈值**——脚本退出码与输出原样写入报告：

```bash
if [ "$TARGET_KIND" = "latex" ]; then
    # 源级检查：引用/结构/图注/AI 套话/符号与假设版式
    WC=""
    for cand in skills/_utils/writing_check.sh academic-toolkit/skills/_utils/writing_check.sh ../../skills/_utils/writing_check.sh; do
        [ -f "$cand" ] && WC="$cand" && break
    done
    [ -z "$WC" ] && echo "WARN: writing_check.sh not found; record as CHECK_UNAVAILABLE" || bash "$WC" paper/
    # PDF 数字-账本一致性（RESULTS.md / figures/all_results.json）
    # 工作区根 cwd（如 academic-toolkit/workspaces/<name>）下命中 ../../tools/paper_data_check.py
    PDC=""
    for cand in academic-toolkit/tools/paper_data_check.py tools/paper_data_check.py ../../tools/paper_data_check.py; do
        [ -f "$cand" ] && PDC="$cand" && break
    done
    [ -z "$PDC" ] && echo "WARN: paper_data_check.py not found; record as CHECK_UNAVAILABLE" || python "$PDC" --mode pdf --workspace .
fi
```

退出码口径（原样写入报告，**不新增判定阈值**）：

- `writing_check.sh`：`0` = 无命中；`1` = 内容级检查命中（风格/一致/版式等，脚本自标 advisory，只记为审查发现，不直接判论文失败）；`3` = `CHECK_UNAVAILABLE`（脚本缺失或崩溃，不得据此改写论文）。
- `paper_data_check.py`：`0` = 无 fatal；`1` = 它自己报告的 fatal 数据不一致（原样记录输出）；其他非零的调用错误同样记 `CHECK_UNAVAILABLE`。
- 两种脚本的退出码都只是证据，不改写 Step 9 的既有四条判定。

LaTeX 分支下 Step 2–7 中的 Markdown 专用口径（正文字数、`## 章节` 标题提取、`![`/表管道计数、Markdown 残留标记）统一在报告中记「不适用（LaTeX 源）」而非判失败；其证据以上面两个脚本的输出为准。报告仍按 Step 8 汇总到同一个 `QUALITY_REPORT.md`，Step 9 仍只按既有四条判定，不因 LaTeX 分支新增门槛。

### Step 2: 字数统计

使用 `count_chapter_words.py` 工具统计字数：

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON tools/count_chapter_words.py "$TARGET_FILE"
```

**审查规则：**
- 开题报告：4000-6000 字
- 文献综述：6000-10000 字
- 课程论文：5000-15000 字（按 word_count_target 设定）
- 课程报告：8000-15000 字

如果总字数超出 ±20% 范围，记录到审查报告。

### Step 3: 结构完整性检查

**开题报告必需章节：**
- 选题背景与意义
- 国内外研究现状
- 研究内容（或目标）
- 研究方法（或技术路线）
- 进度安排
- 参考文献

**文献综述必需章节：**
- 引言
- 文献检索方法（或综述方法）
- 主题分类（至少 3 个分类）
- 不足与未来方向（或现有研究不足）
- 结论
- 参考文献

**课程论文必需章节：**
- 摘要
- 引言
- 主体内容（方法/理论/分析）
- 结论
- 参考文献

**课程报告必需章节：**
- 项目背景（或概述）
- 系统设计（或方案设计）
- 系统实现（或核心实现）
- 测试（或验证）
- 总结
- 参考文献

```bash
# 提取所有一级和二级标题
grep -E "^#{1,2}\s" "$TARGET_FILE"
```

逐一比对必需章节是否存在。

### Step 4: 参考文献检查

```bash
# 提取参考文献部分
sed -n '/^##\?\s.*参考文献\|^##\?\s.*References/,$p' "$TARGET_FILE" | grep -c '^\[[0-9]\+\]'
```

**检查项：**
1. 数量：≥ MIN_REFERENCES（默认 10）
2. 时间分布：近 3 年文献占比 ≥ 60%
3. 格式：是否符合 GB/T 7714（`[N] 作者. 题名[J/M/C]. 出处, 年, 卷(期): 页码.`）
4. 完整性：每条引用是否有作者+题名+年份

### Step 5: 图表检查

```bash
# 统计图片引用
grep -c '!\[' "$TARGET_FILE"
# 统计 Mermaid 图块
grep -c '^```mermaid' "$TARGET_FILE"
# 统计表格
grep -c '^|.*|.*|' "$TARGET_FILE"
```

**检查项：**
- 课程报告：是否有架构图/流程图（Mermaid）
- 是否有图题/表题（"图 X-Y" / "表 X-Y" 格式）
- 图表是否在正文中被引用（如"如图 3-1 所示"）

### Step 6: 格式规范检查

**Markdown 残留检查（不应在最终文档中）：**

```bash
# 检测残留的 Markdown 行内标记（不在代码块内）
grep -n '\*\*[^*]\+\*\*' "$TARGET_FILE" | head -5  # 残留加粗
grep -n '`[^`]\+`' "$TARGET_FILE" | head -5         # 残留代码标记
grep -n '\[.*\](http' "$TARGET_FILE" | head -5      # 残留链接
```

**章节层级检查：**
- 是否跳级（如直接从 # 跳到 ###）
- 一级标题（#）是否唯一（应只有标题或不存在）

### Step 7: 语言风格检查

**AI 套话黑名单（借鉴 PaperSpine humanize）：**

```bash
# 高频 AI 套话
for phrase in "具有重要意义" "实现了良好效果" "具有较高价值" "综上所述" "总而言之" \
              "首先.*其次.*最后" "本文/本研究/本系统" "随着.*的快速发展" "在当今"; do
    count=$(grep -c "$phrase" "$TARGET_FILE")
    [ "$count" -gt 0 ] && echo "WARN: '$phrase' 出现 $count 次"
done
```

如果出现 ≥ 3 次相同套话，标记为风险点。

### Step 8: 生成审查报告

将所有检查结果写入 `QUALITY_REPORT.md`：

```markdown
# 质量审查报告

## 审查目标
- 文件：$TARGET_FILE
- 审查时间：$(date)

## 一、字数检查

| 章节 | 字数 | 目标范围 | 状态 |
|------|------|----------|------|
| 总计 | XXX | YYY-ZZZ | ✅/⚠️/❌ |
| ... | ... | ... | ... |

## 二、结构完整性

- ✅ 已包含的必需章节：[列出]
- ❌ 缺失的必需章节：[列出]

## 三、参考文献

- 总数：N 篇（要求 ≥ 10）
- 近 3 年文献占比：XX%（要求 ≥ 60%）
- 格式问题：[列出有问题的条目]

## 四、图表检查

- 图片数量：N 张
- 表格数量：M 个
- 缺失的图题/表题：[列出]
- 未在正文引用的图表：[列出]

## 五、格式规范

- Markdown 残留标记：[行号 + 内容]
- 章节跳级问题：[列出]

## 六、语言风格

- AI 套话警告：[词组 + 出现次数]
- 空泛表述：[列出代表性句子]

## 总体评分

- 整体得分：X/10
- 阻塞问题（必须修复）：N 个
- 警告问题（建议修复）：M 个

## 修复建议

按优先级列出：
1. [阻塞] ...
2. [警告] ...
```

LaTeX 分支：在报告中追加一节 `## 七、LaTeX 源级检查`，原样粘贴 `writing_check.sh` 与 `paper_data_check.py --mode pdf` 的输出与退出码；Markdown 专用小节写「不适用（LaTeX 源）」。输出文件仍为 `QUALITY_REPORT.md`。

### Step 9: 阻塞判定

**如果存在以下任一问题，报告标记为"未通过"，需要修复后重新审查：**
1. 缺失任何必需章节
2. 总字数低于目标范围 30%
3. 参考文献少于 5 篇
4. 残留 ≥ 5 处 Markdown 标记

**如果通过，在 QUALITY_REPORT.md 末尾添加：**

```
## 审查结论

✅ 审查通过，可以进入下一步（Word 导出）
```

## 输出文件

- `QUALITY_REPORT.md` — 审查报告（主产出）
