---
name: dev-design
description: "毕业设计(软件开发)系统设计。基于需求规格产出架构/数据库/API设计。Use when user says 系统设计/毕设设计."
argument-hint: [project-idea]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# 毕业设计 · 系统设计

基于需求规格进行系统设计：**$ARGUMENTS**

## 输入

1. **REQUIREMENTS.md**（必须存在）— 上一步的需求规格。**先完整读它。**
2. **AGENTS.md** — **project_type（项目类型）**+ 技术栈参数在"说明/参数"段。

## ⛔ 按项目类型 + 用户技术栈设计（不要写死）

先读 AGENTS.md 的 `project_type` 和技术栈参数，按用户实际选择设计：
- **fullstack**：前端(tech_frontend) + 后端(tech_backend) + 数据库(tech_db)。产 DESIGN.md + `schema.sql`。
- **frontend**：纯前端(tech_frontend)，无后端/数据库。**不产 schema.sql**，DESIGN.md 的"数据库设计"小节写"本项目为纯前端，无数据库（如需本地存储用 localStorage）"。
- **cli / script**：命令行/脚本(tech_lang)。**不产 schema.sql**，"数据库设计"小节写"无数据库"或说明数据存储方式（文件/JSON 等）。"API 设计"小节改为"命令/参数设计"或"函数/模块接口"。

## ⛔ 恢复场景

若已有 `DESIGN.md`，在其基础上补全，不要推倒重写。

## 任务

产出 `DESIGN.md`（系统设计文档）+ `schema.sql`（SQLite 建表语句）。

- 数据库设计要覆盖需求里的所有实体，字段类型用 SQLite 支持的（INTEGER/TEXT/REAL/BLOB）。
- API 设计要覆盖需求"接口清单"里的每一条，用 RESTful 风格。
- 目录结构要明确前后端怎么组织（见下方约定）。

## 产出（固定小节，下游 dev-code 会读）

**DESIGN.md** 必须含以下 `##` 小节（标题一字不差）：

```markdown
# 系统设计文档

## 技术架构
（技术栈选型：React + FastAPI + SQLite，及各自职责；前后端如何通信——REST JSON）

## 数据库设计
（每张表：表名、字段、类型、约束、表间关系。与 schema.sql 一致）

## API 设计
（每个接口：方法 + 路径 + 入参 + 返回示例。覆盖 REQUIREMENTS 的接口清单）

## 模块划分
（前端组件/页面划分；后端路由/模型/服务划分）

## 目录结构
（明确 code/ 下的目录树，遵循下方约定）
```

**目录结构约定**（dev-code 会照此实现，务必写清）：
```
code/
  frontend/          # React 前端
    src/
    package.json
  backend/           # FastAPI 后端
    main.py          # 应用入口(必须)
    models.py        # 数据模型
    database.py      # SQLite 连接
    requirements.txt
  README.md          # 目录说明
```

**schema.sql**：可直接被 SQLite 执行的完整建表 SQL（CREATE TABLE ...）。

## 完成铁律

- `DESIGN.md` ≥ 2000 字节。核心小节（技术架构/模块划分/目录结构）必备；数据库/API 设计小节全栈与前端必备，CLI/脚本可省。
- **仅 fullstack** 类型：`schema.sql` 必须存在且含至少一条 `CREATE TABLE`（前端/CLI/脚本不需要）。
- API/接口 设计要覆盖 REQUIREMENTS 的接口清单。

产出结构、存在性和最低完整性由 `finish` 按模板中的 `output_contract` 自动核验；修复返回的具体问题，不复制执行验证脚本。
验证失败就继续补全，不要 end_turn。

## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

保留实际输入来源与模板信息；其内容摘要由程序记录。
