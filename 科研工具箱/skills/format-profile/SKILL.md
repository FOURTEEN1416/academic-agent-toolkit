---
name: format-profile
description: "根据用户的文字格式要求或上传的格式说明文档，生成 docx-export 用的样式 profile JSON。Claude 自主理解中文字号术语、字体、行距、缩进等参数。"
argument-hint: [format-description-or-doc]
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# 格式 profile 生成

读取用户的文字格式要求，生成 `_text_profile.json` 供 docx-export 使用。

## 输入来源（按优先级）

1. **`FORMAT_REQUIREMENTS.md`**（工作区根目录）— 用户在前端输入的纯文字格式要求
2. **`user_data/*_extracted.txt`** — 用户上传的文档（学校规范/老师要求）的提取文本，需筛选出格式相关段落
3. **`_derived_profile.json`** — 已从 .docx 模板派生的 profile（如有），文字要求基于此覆盖
4. **`CUSTOM_REQUIREMENTS.md`** — 用户的整体自定义要求（可能含格式描述）

## 硬约束

1. **本步骤只输出一个 JSON 文件**：`_text_profile.json`（写到工作区根目录）
2. **必须严格遵守 docx_export 的 profile schema**（下面给出）
3. **不要写正文，不要修改其他文件**
4. **未明确提及的字段** → **保留默认值**（不要瞎猜）
5. JSON 必须可被 `python -m json.tool` 解析

## docx_export profile Schema（必须遵守）

```json
{
  "profile_name": "用户文字要求派生样式",
  "_derived_from": "text-description",
  "_matched_items": ["列出你识别到的格式要点，便于用户审查"],
  "page": {
    "size": "A4",
    "margin_top_cm": 2.5,
    "margin_bottom_cm": 2.5,
    "margin_left_cm": 2.5,
    "margin_right_cm": 2.5
  },
  "fonts": {
    "chinese_heading": "SimHei",
    "chinese_body": "SimSun",
    "latin": "Times New Roman",
    "monospace": "Consolas"
  },
  "headings": {
    "level1_pt": 16,
    "level2_pt": 14,
    "level3_pt": 12,
    "level4_pt": 11,
    "bold": true,
    "level1_alignment": "center",
    "level2_alignment": "left",
    "level3_alignment": "left",
    "level1_page_break_before": false,
    "level2_page_break_before": false,
    "level3_page_break_before": false
  },
  "body": {
    "font_size_pt": 12,
    "line_spacing": 1.5,
    "first_line_indent_chars": 2,
    "space_before_pt": 0,
    "space_after_pt": 0
  },
  "title": {
    "font_size_pt": 18,
    "bold": true,
    "alignment": "center",
    "font_family": "SimHei"
  },
  "table": {
    "top_border_pt": 1.5,
    "header_border_pt": 0.75,
    "bottom_border_pt": 1.5,
    "font_size_pt": 10.5,
    "header_bold": true,
    "cell_alignment": "center"
  },
  "references": {
    "hanging_indent_cm": 0.74,
    "font_size_pt": 10.5,
    "numbering_style": "bracket"
  },
  "image": {
    "max_width_cm": 14,
    "alignment": "center"
  },
  "code_block": {
    "font_size_pt": 9,
    "line_spacing": 1.0,
    "background_color": "F5F5F5"
  }
}
```

## 中文字号 → pt 参考表（你需要熟练掌握）

| 中文字号 | pt | 中文字号 | pt |
|---------|----|---------|----|
| 初号 | 42 | 三号 | 16 |
| 小初 | 36 | 小三 | 15 |
| 一号 | 26 | 四号 | 14 |
| 小一 | 24 | 小四 | 12 |
| 二号 | 22 | 五号 | 10.5 |
| 小二 | 18 | 小五 | 9 |

## 字体术语 → 系统字体名

| 术语 | 系统名 |
|------|--------|
| 宋体 | SimSun |
| 黑体 | SimHei |
| 仿宋 / 仿宋_GB2312 | FangSong / FangSong_GB2312 |
| 楷体 / 楷体_GB2312 | KaiTi / KaiTi_GB2312 |
| 微软雅黑 / 雅黑 | Microsoft YaHei |
| 等线 | DengXian |
| 华文宋体 / 华文中宋 / 华文黑体 / 华文楷体 | STSong / STZhongsong / STHeiti / STKaiti |
| Times New Roman | Times New Roman |

## 字段对齐说明

- 对齐值：`"center" | "left" | "right" | "justify"`
- 行距：`1.0`(单倍) / `1.15` / `1.25` / `1.5`(常用) / `2.0`(双倍) — 也可以是固定 pt 值（行距 22 磅 → 22/12 ≈ 1.83）
- 首行缩进：以**字符数**为单位（中文论文常用 `2`，即 2 个汉字宽度）
- 边距：cm 为单位

## ⛔⛔⛔ 完成铁律（最高优先级）

**本步骤必须产出 `_text_profile.json`（合法 JSON，≥ 300 字节）**。

⛔ **结束前必跑产出验证**：
```bash
[ -f _text_profile.json ] && SZ=$(wc -c < _text_profile.json) || SZ=0
if [ "$SZ" -ge 300 ] && python3 -m json.tool _text_profile.json > /dev/null 2>&1; then
    echo "✅ _text_profile.json ($SZ bytes, 合法 JSON)"
else
    echo "❌ _text_profile.json 缺失或过小或不是合法 JSON — 必须补全后重新跑验证, 不要结束本步骤"
fi
```

## 工作流程

### Step 1: 读取所有可能的格式来源

```bash
echo "=== 检查格式来源 ==="

# 1. 用户在前端直接输入的文字要求
[ -f FORMAT_REQUIREMENTS.md ] && { echo "--- FORMAT_REQUIREMENTS.md ---"; cat FORMAT_REQUIREMENTS.md; }

# 2. 上传文档中的格式要求
for f in user_data/*_extracted.txt; do
    [ -f "$f" ] || continue
    # 只取含格式关键词的部分
    echo "--- 来自 $f 的格式段落 ---"
    grep -E '正文|宋体|黑体|字号|字体|行距|缩进|边距|对齐|页面|余量|字距|页码|标题' "$f" | head -50
done

# 3. 自定义要求中可能含格式
[ -f CUSTOM_REQUIREMENTS.md ] && {
    echo "--- CUSTOM_REQUIREMENTS.md 中的格式段 ---"
    grep -E '正文|宋体|黑体|字号|字体|行距|缩进|边距|对齐' CUSTOM_REQUIREMENTS.md | head -20
}

# 4. 已派生的 profile（如有 docx 模板，后端已预先派生好）
[ -f _derived_profile.json ] && { echo "--- _derived_profile.json（基础值）---"; cat _derived_profile.json; }
```

### Step 2: 提取并理解格式要求

对每条格式要求，识别它属于哪个角色（正文/各级标题/表格/参考文献/封面标题/代码/图题等）：

| 要求示例 | 解析 |
|---------|------|
| "正文小四宋体，1.5 倍行距，首行缩进 2 字符" | body: 12pt SimSun，1.5 倍，缩进 2 |
| "一级标题三号黑体居中加粗" | headings.level1_pt=16, font=SimHei, alignment=center, bold=true |
| "二级标题四号黑体顶格" | level2_pt=14, alignment=left |
| "三级标题小四黑体" | level3_pt=12 |
| "页边距上下 2.54cm，左右 3.17cm" | page.margin_top/bottom=2.54, left/right=3.17 |
| "参考文献小五号" | references.font_size_pt=9 |
| "表格内容五号宋体" | table.font_size_pt=10.5 |
| "页码居中宋体五号" | （docx_export 默认页码居中，无需特殊处理）|

### Step 3: 构建 JSON

1. 以默认 profile 作为基础
2. 如果 `_derived_profile.json` 存在，先用它作为基础（不是默认值）
3. 把识别出来的字段**逐一覆盖**到对应位置
4. 没识别到的字段**保留基础值**，不要乱改
5. 在 `_matched_items` 数组里按顺序列出你识别到的每条规则（用人类可读的中文）

### Step 4: 输出

把构建好的 JSON 用 `Write` 工具写到 `_text_profile.json`：

```bash
# 验证 JSON 合法性
python3 -m json.tool _text_profile.json > /dev/null && echo "✅ JSON 合法" || echo "❌ JSON 不合法"

# 显示识别到的项
python3 -c "
import json
p = json.load(open('_text_profile.json', encoding='utf-8'))
print('识别到的格式要点:')
for item in p.get('_matched_items', []):
    print('  -', item)
"
```

### Step 5: 自检

确保：
- [ ] `_text_profile.json` 文件存在
- [ ] JSON 合法
- [ ] 所有识别出的格式都体现在了对应字段
- [ ] 未提到的字段是默认值（没有瞎改）
- [ ] `_matched_items` 列出至少 1 条（如果用户真的描述了格式）

## 输出文件

- `_text_profile.json` — 派生的样式 profile，docx-export 步骤会读取并应用

## 关键规则

1. **只产出 `_text_profile.json`**，不写任何其他文件，不修改正文
2. **不要瞎猜**：用户没明确说的字段保留默认值，别自作主张
3. **字号必须用 pt**（不是中文字号术语），字体必须用系统字体名
4. **JSON 必须合法**，否则 docx-export 会回退到默认 profile
5. **在 `_matched_items` 里详细列出识别到的项**，便于用户验证
