---
name: defuddle
description: HTML-to-Markdown 网页正文提取工具。从任意 URL/HTML 中提取主内容，去除导航/广告/侧栏，返回干净 Markdown。
source: https://github.com/kepano/defuddle
author: kepano (Obsidian 作者)
---

# Defuddle — 网页正文提取器

Defuddle 从网页中提取**正文内容**，自动去除导航栏、广告、评论、侧栏等干扰，返回干净 HTML 或 Markdown。

由 Obsidian 作者 kepano 开发，用于 Obsidian Web Clipper 的底层内容提取。

## 安装

```bash
# 全局安装
npm install -g defuddle

# 或用 npx 免安装直接运行
npx defuddle parse <url>
```

> Windows 环境：已有 Node.js 时直接用 `npx`，无需全局安装。

## CLI 用法

```bash
# 基础：提取 URL 正文为 HTML
npx defuddle parse https://example.com/article

# 输出为 Markdown（核心用途）
npx defuddle parse https://example.com/article --markdown

# 简写
npx defuddle parse https://example.com/article --md

# 输出为 JSON（含元数据）
npx defuddle parse https://example.com/article --json

# 提取特定元数据字段
npx defuddle parse https://example.com/article --property title
npx defuddle parse https://example.com/article --property author

# 保存到文件
npx defuddle parse https://example.com/article --output result.md

# 指定语言
npx defuddle parse https://example.com/article --lang zh-CN

# 解析本地 HTML 文件
npx defuddle parse page.html --markdown
```

### CLI 选项

| 选项 | 别名 | 说明 |
|------|------|------|
| `--output <path>` | `-o` | 输出到文件 |
| `--markdown` | `-m`, `--md` | 输出 Markdown |
| `--json` | `-j` | 输出 JSON（含元数据） |
| `--property <name>` | `-p` | 提取特定字段 |
| `--debug` | | 调试模式 |
| `--lang <code>` | `-l` | 语言偏好 (BCP 47, 如 `zh-CN`) |

## 作为 Node.js 库使用

```javascript
import { defuddle } from 'defuddle'

// 从 URL 解析
const result = await defuddle('https://example.com/article')
console.log(result.content)       // 正文 HTML
console.log(result.title)         // 标题
console.log(result.description)   // 描述
console.log(result.author)        // 作者

// 输出 Markdown
const md = await defuddle('https://example.com/article', { markdown: true })
console.log(md.content)           // Markdown 正文
```

### 配置选项

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `markdown` | boolean | false | 正文转为 Markdown |
| `removeExactSelectors` | boolean | true | 移除广告/社交按钮 |
| `removeHiddenElements` | boolean | true | 移除隐藏元素 |
| `removeLowScoring` | boolean | true | 移除低分内容块 |
| `removeSmallImages` | boolean | true | 移除小图标 |
| `removeImages` | boolean | false | 移除所有图片 |
| `standardize` | boolean | true | 标准化 HTML |
| `url` | string | | 页面 URL |
| `language` | string | | 语言偏好 |
| `contentSelector` | string | | 自定义 CSS 选择器 |
| `debug` | boolean | false | 调试日志 |

### 返回值

| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | string | 正文 HTML |
| `contentMarkdown` | string | Markdown 版本 |
| `title` | string | 标题 |
| `description` | string | 摘要 |
| `author` | string | 作者 |
| `site` | string | 站点名称 |
| `domain` | string | 域名 |
| `image` | string | 文章封面图 |
| `language` | string | 语言 |
| `wordCount` | number | 字数 |
| `schemaOrgData` | object | Schema.org 结构化数据 |

## 数模竞赛场景用例

### 1. 赛题资料提取

从赛题发布页或参考资料页提取正文做预研：

```bash
npx defuddle parse "https://www.mcm.edu.cn/" --md -o data/problem_info.md
```

### 2. 论文正文提取

从 arXiv/OpenAlex 论文页提取摘要和正文做文献综述：

```bash
npx defuddle parse "https://arxiv.org/abs/2401.00001" --json
# 提取 title + abstract，喂给 AI 做选题/模型参考
```

### 3. 知识库素材采集

配合 Obsidian 工作流，将网页文章转 Markdown 存入知识库：

```bash
npx defuddle parse "https://example.com/algorithm" --md -o "Sources/Web/algorithm.md"
```

### 4. PDF 转 Markdown 管线

```bash
# 1. 先用 OCR 提取 PDF 文字为 HTML
python tools/pdf_ocr.py input.pdf -o output.html

# 2. 再用 Defuddle 清洗转 Markdown
npx defuddle parse output.html --md -o output.md
```

## 与其他工具配合

| 场景 | 管线 |
|------|------|
| 文献调研 | `defuddle` 提取正文 → AI 摘要 → 存入 `data/` |
| 选题参考 | `defuddle` 提取赛题页 → `problem-selection` 模型打分 |
| 论文参考 | OpenAlex 搜 → `defuddle` 提取 → `citation-check` 引用 |

## 限制

- ⚠️ 需要 Node.js 环境（`npx` 或全局 npm）
- ⚠️ 不处理 JavaScript 渲染的 SPA 页面（需配合 Puppeteer）
- ⚠️ 仅提取正文，不保留原页面布局/样式
