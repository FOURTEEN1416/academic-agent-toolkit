---
created: {{timestamp}}
type: {{type}}
tags: {{tags}}
status: inbox
source: claude-code
---

# {{title}}

## 背景 (Context)

{{context}}

## 内容 (Content)

{{content}}

## 分析 (Analysis)

{{analysis}}

---

## 使用说明

这是Knowledge Steward技能使用的笔记模板。

### 字段说明

- **created**: 创建时间戳（YYYY-MM-DD HH:MM:SS）
- **type**: 笔记类型（提示词|模式|问题修复|想法|效率优化）
- **tags**: 标签数组，用于Obsidian检索
- **status**: 状态（inbox表示待处理，可改为processed/archived）
- **source**: 来源标识（claude-code）

### 内容结构

1. **背景 (Context)**: 记录当时在做什么，为什么需要这个内容
2. **内容 (Content)**: 核心的提示词/代码/想法/解决方案
3. **分析 (Analysis)**: 苏格拉底式反思，理解"为什么"

### Obsidian集成

#### Dataview查询示例

查看最近7天的笔记：
```dataview
TABLE type, tags
FROM "Claude_Insights"
WHERE file.cday >= date(today) - dur(7 days)
SORT file.ctime DESC
```

按类型统计：
```dataview
TABLE rows.file.link as "笔记"
FROM "Claude_Insights"
GROUP BY type
```

查看所有提示词：
```dataview
LIST
FROM "Claude_Insights/提示词"
SORT file.ctime DESC
```

#### 标签使用

- 使用 `#提示词工程` `#代码重构` 等标签快速检索
- 在Obsidian中点击标签可查看所有相关笔记
- 建议定期整理标签，合并同义标签

### 工作流建议

1. **每日捕获**：在Claude Code会话中随时保存有价值的内容
2. **每周复盘**：周五查看本周保存的所有笔记，将status改为processed
3. **每月归档**：整理高价值笔记，提炼成知识卡片
4. **季度回顾**：分析积累的模式，形成个人最佳实践库
