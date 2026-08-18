---
name: docx-template-map
description: "分析用户上传的 .docx/.dotx 模板，识别占位段位置，生成 _template_map.json，并通过「试填→自检→修复」循环验证映射正确性。Use when user says \"分析 word 模板\", \"识别模板占位\", \"docx-template-map\"."
argument-hint: [template-path]
allowed-tools: Bash(*), Read, Write, Edit
---

# DOCX 模板占位映射器（带试填自检循环）

把用户上传的 `.docx` / `.dotx` 模板转换成 `docx_template_fill.py` 能用的「占位映射 JSON」，并通过「生成→试填→分析→修复」循环确保映射正确，让 docx-export 用上的 map 是已验证的。

## 输入

- **TEMPLATE_PATH**：从 `$ARGUMENTS` 传入，或自动检测 `user_data/` 下首个 `.docx` / `.dotx` 模板
- **WORKSPACE**：当前工作区（含 `paper/main.md` 或 `COURSE_PAPER.md` 等已生成的 markdown）

## 输出

- `_template_map.json`（**必须**，工作区根目录）— 已验证可用
- `_template_structure.txt`（中间产物，模板段落清单）
- `_template_test_filled.docx`（中间产物，试填验证用，最后会保留以便检查）
- `_template_check_report.md`（中间产物，记录每轮自检发现的问题）

## 核心原则

1. **不要凭推理就交付** — 必须真实跑过 `fill_template`，并验证结果 docx 是否含残留占位/示例/说明文字
2. **idx 是硬约束** — 一旦 anchor idx 错位，整个填充失败，所以每轮都要打印实际段落对照
3. **删除冲突要避免** — `delete_paragraph_indices` 不能包含任何 `*_anchor_para_idx` 的值，否则 anchor 段被删，对应 section 整段消失
4. **最多 3 轮自检** — 第 3 轮还失败就如实记录，让后续 docx-export 退到正则启发式

## ⛔⛔⛔ 完成铁律（最高优先级）

**本步骤必须产出 `_template_map.json`（合法 JSON，含 anchor_para_idx 字段）+ `_template_check_report.md`（自检报告）**。

⛔ **结束前必跑产出验证**：
```bash
PASS=true
[ -f _template_map.json ] && SZ=$(wc -c < _template_map.json) || SZ=0
if [ "$SZ" -ge 100 ] && python3 -m json.tool _template_map.json > /dev/null 2>&1; then
    echo "✅ _template_map.json ($SZ bytes, 合法 JSON)"
else
    echo "❌ _template_map.json 缺失或不是合法 JSON"
    PASS=false
fi
[ -f _template_check_report.md ] && echo "✅ _template_check_report.md" || { echo "❌ _template_check_report.md 缺失"; PASS=false; }
[ "$PASS" != true ] && echo "⛔ 产出验证失败 — 必须补全后重新跑验证, 不要结束本步骤"
```

## 工作流程

### Step 1：定位模板 + 源 markdown

```bash
TEMPLATE=""
if [ -n "$ARGUMENTS" ] && [ -f "$ARGUMENTS" ]; then
    TEMPLATE="$ARGUMENTS"
else
    # 优先 user_data/ 下，再扫工作区根
    for cand in user_data/*.docx user_data/*.dotx *.docx *.dotx; do
        [ -f "$cand" ] || continue
        # 跳过我们自己生成的
        case "$cand" in
            *converted.docx|*test_filled.docx|*paper/main.docx|paper/*.docx) continue;;
        esac
        TEMPLATE="$cand"; break
    done
fi
[ -z "$TEMPLATE" ] && { echo "未找到模板"; exit 1; }
echo "Template: $TEMPLATE"

# 源 markdown — 先尝试已生成的论文 / 报告
SOURCE=""
for cand in paper/main.md PROPOSAL.md LITERATURE_REVIEW.md COURSE_PAPER.md COURSE_REPORT.md; do
    [ -f "$cand" ] && { SOURCE="$cand"; break; }
done
[ -z "$SOURCE" ] && echo "⚠ 未找到源 markdown，只能生成 map 不能试填"
echo "Source MD: $SOURCE"
```

### Step 2：dump 模板结构

⛔ 工具文件：复制到 `_utils/` 目录（`docx_template_analyze.py` / `docx_template_fill.py` / `docx_export.py`）。统一用 `python3 _utils/<tool>.py` 调用。

```bash
python3 _utils/docx_template_analyze.py \
    --template "$TEMPLATE" \
    --output _template_structure.json \
    --summary _template_structure.txt
```

`_template_structure.txt` 形如：

```
=== 模板结构清单（语言：zh）===
[段   1]     标题（此处换成论文的标题）
[段   2]     摘要
[段   3]     (说明：以下开始写摘要...)
[段  38]     正文内容(原则上不能超过20页)
[段  43]     参考文献 （可另起一页）
[段  52]     附录（另起一页）
```

### Step 3：用 Read 工具读 _template_structure.txt，按语义判断占位

按以下顺序识别每个 anchor：

| anchor | 识别特征 |
|---|---|
| `title_anchor_para_idx` | 含「标题」/「题目」/「Title」+「此处」/「填」/「换成」/「__」 |
| `abstract_anchor_para_idx` | 段是「摘要」/「Abstract」/「[摘 要]」/「摘 要」 |
| `body_anchor_para_idx` | 段是「正文内容(...)」/「正文」/「绪论」/「Body」 |
| `references_anchor_para_idx` | 段是「参考文献」/「References」/「Bibliography」 |
| `appendix_anchor_para_idx` | 段是「附录」/「Appendix」/「Annex」（可选） |

收集 `delete_paragraph_indices`：
- 起头 `(注：` `（说明：` `(示例：` 的提示段
- 含「请删除」/「看完后删除」/「示例段落」
- 含「[编号] 作者」/「书籍的表述方式」/「参考文献著录格式」
- **模板示例正文**（如果模板含完整示例论文）：示例的章节标题、示例的代码、示例的图表
- **格式说明区**（如「装订格式」「撰写格式要求」等独立章节及其下属段落）
- **多余空段**：摘要 anchor 之后到正文 anchor 之间的空段（fill 会替换）

⛔ 关键约束（必须自检）：
- `delete_paragraph_indices` **不能**含任何 anchor idx
- 例如 `body_anchor_para_idx=36`，那 36 不能在 `delete_paragraph_indices` 里

### Step 4：写出 _template_map.json（v1）

```bash
cat > _template_map.json <<'JSON'
{
  "language": "zh",
  "title_anchor_para_idx": <N>,
  "abstract_anchor_para_idx": <N>,
  "body_anchor_para_idx": <N>,
  "body_anchor_mode": "delete",
  "references_anchor_para_idx": <N>,
  "appendix_anchor_para_idx": <N or null>,
  "delete_paragraph_indices": [...],
  "preserve_table_indices": [0]
}
JSON
```

写完后立即用 Bash 自检 anchor 与 delete 列表无冲突：

```bash
python3 - <<'PY'
import json
m = json.load(open('_template_map.json', encoding='utf-8'))
del_set = set(m.get('delete_paragraph_indices') or [])
anchors = {k: m.get(k) for k in [
    'title_anchor_para_idx', 'abstract_anchor_para_idx',
    'body_anchor_para_idx', 'references_anchor_para_idx',
    'appendix_anchor_para_idx',
]}
for k, v in anchors.items():
    if v is not None and v in del_set:
        print(f"❌ {k}={v} 在 delete_paragraph_indices 里 — 必须移除")
        import sys; sys.exit(1)
print("OK: anchors 与 delete_paragraph_indices 无冲突")
PY
```

### Step 5：试填一次

```bash
[ -z "$SOURCE" ] && exit 0  # 没源 md 就交付当前 map

python3 _utils/docx_template_fill.py \
    --template "$TEMPLATE" \
    --source "$SOURCE" \
    --output _template_test_filled.docx \
    --workspace . 2>&1 | tee _template_fill.log
```

**重点关注 log 中的：**
- `Title replaced via template_map: '...'`  → 标题命中
- `Abstract (N paras) + keywords inserted`  → 摘要命中
- `Body (N elements) inserted (anchor_mode=delete)`  → 正文命中
- `References (N items) inserted`  → 参考文献命中
- `Appendix (N elements) inserted`  → 附录命中（可选）

**如果某条 log 缺失**，说明对应 anchor 错位 / 已被删除。需要修 map：
- 缺 `Body` → `body_anchor_para_idx` 不对，重新核对实际正文起点段
- 缺 `Abstract` → `abstract_anchor_para_idx` 不对
- log 含 `body_p anchor: ... has_parent=False` → anchor 被某个 `delete_paragraph_indices` 误删

### Step 6：分析试填后的 docx，定量检查残留

```bash
python3 _utils/docx_template_analyze.py \
    --template _template_test_filled.docx \
    --output _template_filled_structure.json \
    --summary _template_filled_structure.txt
```

读 `_template_filled_structure.txt`，逐项检查：

| 检查项 | 命中（fail）即为 bug |
|---|---|
| **占位符未替换** | 含「(此处换成」「请输入」「____」「[摘 要]」「<TITLE>」 |
| **模板示例正文残留** | 含模板原本的示例标题（"职场不败玫瑰" / "1.1文献综述" / "2.1创建文档" 等） |
| **格式说明残留** | 含「[编号] 作者」「装订格式」「撰写格式要求」「参考文献著录格式说明」 |
| **应有内容缺失** | 检查源 md 的章节标题在 filled docx 中是否出现 |
| **封面字段保留** | 检查模板原有的封面字段（学院 / 学号 / 学校 / 参赛编号 等）仍在 |

```bash
# 残留占位检查
echo "=== 残留占位 ==="
grep -nE '(此处|请输入|请填写|____|\[摘 要\]|<.*>)' _template_filled_structure.txt | grep -v '^=' || echo "OK 无占位残留"

# 残留示例 / 格式说明（用户根据模板特征自行补充关键词）
echo "=== 残留示例 ==="
grep -nE '(职场不败玫瑰|1\.1文献综述|2\.1创建文档|装订格式|参考文献著录格式|\[编号\] 作者)' \
    _template_filled_structure.txt || echo "OK 无示例残留"

# 应有内容（源 md 的章节标题）
echo "=== 源 md 章节是否在 filled 里 ==="
grep -E '^##\s' "$SOURCE" | sed 's/^## *//' | while read title; do
    [ -z "$title" ] && continue
    if grep -qF "$title" _template_filled_structure.txt; then
        echo "  ✅ $title"
    else
        echo "  ❌ 缺失: $title"
    fi
done
```

### Step 7：如有问题，调整 _template_map.json 重试

把 Step 6 的发现写到 `_template_check_report.md`，然后用 Edit 工具修 map。常见修复：

| 现象 | 修复 |
|---|---|
| Body 章节缺失 | 核对 `_template_structure.txt` 中正文起点段的真实 idx，更新 `body_anchor_para_idx` |
| 示例正文残留（如"绪论 / 1.1文献综述"） | 把它们的 idx 加到 `delete_paragraph_indices` |
| 格式说明残留（如"装订格式" 整章） | 找到该段及其后所有相关段，全部加到 `delete_paragraph_indices` |
| 摘要被删（"Abstract 0 paras"）| `abstract_anchor_para_idx` 不对，或 anchor 被 `delete_paragraph_indices` 误删 |
| 封面字段消失 | `delete_paragraph_indices` 误把封面段（学院/学号等）也删了，移除 |

修完 map 后回到 Step 4 的合法性自检 → Step 5 重试。**最多循环 3 次**，第 3 次仍失败也保存当前 map 让 docx-export 自己处理（fill_template 内部有 fallback）。

### Step 8：清理 + 输出报告

试填验证通过后，写最终报告：

```bash
cat > _template_check_report.md <<EOF
# DOCX 模板占位映射报告

**模板**：\`$TEMPLATE\`
**源 markdown**：\`$SOURCE\`
**自检轮数**：N / 3
**最终状态**：✅ 通过 / ⚠️ 部分通过 / ❌ 未通过

## anchor 映射

| 区域 | idx | 命中段文本 |
|------|-----|------------|
| 标题 | $title_idx | ... |
| 摘要 | $abs_idx | ... |
| 正文起点 | $body_idx | ... |
| 参考文献 | $ref_idx | ... |
| 附录 | $app_idx | ... |

## 删除段（共 N 个）

按类别归类：
- 标题占位说明：[idx 列表]
- 摘要说明：[idx 列表]
- 模板示例正文：[idx 列表]
- 格式说明区：[idx 列表]

## 自检结果

- ✅/❌ 占位符全部替换
- ✅/❌ 模板示例残留清除
- ✅/❌ 格式说明清除
- ✅/❌ 应有正文章节齐全
- ✅/❌ 封面字段保留

## 仍需人工处理

（如有残留无法自动修，列在此处）
EOF
```

保留 `_template_test_filled.docx`（用户可下载查看预览），让后续 docx-export 步骤跑正式版。

## 注意事项

1. **不要硬编码模板字段名** — 全部按段落内容语义判断
2. **anchor 找不到的占位 → null** — 让 fill 退到正则兜底
3. **多语言模板（中英对照）** — 取占字符多的那个作为 `language`
4. **示例正文要彻底清理** — 用户绝不希望看到模板自带的"职场不败玫瑰"之类示例文字
5. **不要扩大删除范围** — 只删确认是说明 / 示例的段，宁可漏删也不要误删用户上传内容
6. **最多 3 轮** — 防止陷入死循环；第 3 轮仍失败时保存当前 map，让 fill_template 退到正则
