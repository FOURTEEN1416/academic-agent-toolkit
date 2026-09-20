# 可选宿主适配器（Host Adapters）

本目录描述**可选**宿主接入层。本项目驱动协议**不依赖**任何适配器：

- 任意能读文件、能执行 `python -m engine.workflow_cli` 的智能体均可驱动本项目
- 适配器只提供增强能力：技能自动扫描、L1 拦截式审计 hook、角色定义等
- 无适配器时：L1 记为 `unavailable`（不阻断），L2/L3 与质量门禁完整可用

## 目录约定

```
agents/adapters/<adapter-id>/
  adapter.json     # 元数据（是否在位、配置路径、L1 能力）
  models.json      # 可选：{"roles": {"reviewer": "provider/model", ...}}
```

`models.json` 会进入质量门禁的模型解析链（优先级低于 `contest_models.json`）。

## 内置适配器

| id | 状态 | 配置位置 | 说明 |
|----|------|----------|------|
| `generic` | 永远可用 | 无 | 协议层：AGENTS.md + skills/ + workflow_cli |
| `opencode` | 可选 | `opencode.json` / `.opencode/` | OpenCode Desktop/CLI |
| `zcode` | 可选 | `.zcode/` | ZCode（含 L1 hook） |
| `claude-code` | 可选 | `.claude/` / `CLAUDE.md` | Claude Code |
| `mimocode` | 可选 | `.mimocode/` | MiMo Desktop |

## 新宿主如何接入

1. **最小接入（推荐）**：什么配置都不用加。读根 `AGENTS.md`，跑 `boot`/`probe`，按协议执行。
2. **增强接入**：在本目录新建 `agents/adapters/<id>/adapter.json`，
   把该宿主的 skills 路径 / hooks / 角色定义写进去；需要审稿模型时再加 `models.json`。
3. **能力缺口**：`python -m engine.workflow_cli probe` 后，用 `forge --tool/--skill/--adapter` 补齐。

## 铁律

- 适配器配置不得写入本机绝对路径到 tracked 文件
- 审计证据 `agent` 字段由驱动方自报（如 `claude-code`），不绑定某一宿主名
- 适配器缺失 ≠ 项目不可用
