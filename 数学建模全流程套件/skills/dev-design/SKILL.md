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
2. **CLAUDE.md** — **project_type（项目类型）**+ 技术栈参数在"说明/参数"段。

## ⛔ 按项目类型 + 用户技术栈设计（不要写死）

先读 CLAUDE.md 的 `project_type` 和技术栈参数，按用户实际选择设计：
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

⛔ **结束前必跑产出验证**（按类型自适应）：
```bash
echo "=== 系统设计产出验证 ==="
PASS=true
PTYPE=$(grep -oE "project_type[:=] *(fullstack|frontend|cli|script)" CLAUDE.md 2>/dev/null | grep -oE "(fullstack|frontend|cli|script)" | head -1)
PTYPE=${PTYPE:-fullstack}
echo "项目类型: $PTYPE"
[ -f DESIGN.md ] && SZ=$(wc -c < DESIGN.md) || SZ=0
if [ "$SZ" -ge 2000 ]; then echo "OK DESIGN.md ($SZ bytes)"; else echo "FAIL DESIGN.md 过小 ($SZ)"; PASS=false; fi
# 所有类型都要的核心小节
for sec in "## 技术架构" "## 模块划分" "## 目录结构"; do
  grep -qF "$sec" DESIGN.md 2>/dev/null && echo "OK 小节: $sec" || { echo "FAIL 缺小节: $sec"; PASS=false; }
done
# 数据库设计/API 设计: 全栈和前端(可能有API对接)要, CLI/脚本可省(或写"无")
if [ "$PTYPE" = "fullstack" ] || [ "$PTYPE" = "frontend" ]; then
  for sec in "## 数据库设计" "## API 设计"; do
    grep -qF "$sec" DESIGN.md 2>/dev/null && echo "OK 小节: $sec" || { echo "FAIL 缺小节: $sec"; PASS=false; }
  done
else
  echo "OK $PTYPE 类型, 数据库/API 设计小节可省"
fi
if [ "$PTYPE" = "fullstack" ]; then
  if [ -f schema.sql ] && grep -qi "CREATE TABLE" schema.sql; then echo "OK schema.sql"; else echo "FAIL 全栈项目 schema.sql 缺失或无建表"; PASS=false; fi
else
  echo "OK 非全栈, 跳过 schema.sql 检查"
fi
[ "$PASS" != true ] && echo "产出验证失败 — 必须补全后重跑, 不要结束本步骤"
```
验证失败就继续补全，不要 end_turn。
