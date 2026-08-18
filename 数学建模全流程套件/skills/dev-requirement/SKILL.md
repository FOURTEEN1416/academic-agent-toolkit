---
name: dev-requirement
description: "毕业设计(软件开发)需求分析。把项目想法+用户功能要求拆解成结构化需求规格。Use when user says 需求分析/毕设需求."
argument-hint: [project-idea]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# 毕业设计 · 需求分析

对以下项目进行需求分析：**$ARGUMENTS**

## 输入

1. **CLAUDE.md** — 含用户填的：**project_type（项目类型）**、技术栈、功能需求、自定义要求。**先读它的"说明/参数"段获取这些。** 需求分析要贴合项目类型（全栈Web/纯前端/CLI/脚本）。
2. **user_data/** — 用户可能上传的任务书/需求文档（读 `user_data/*_extracted.txt` 或 `user_data/*.txt`，若存在）。

## ⛔ 恢复场景

若工作区已有 `REQUIREMENTS.md`（上次跑了一半），在其基础上**补全完善**，不要推倒重写。

## 任务

把"项目想法 + 用户功能要求 + 上传的任务书"拆解、补全成一份**完整、可执行的需求规格** `REQUIREMENTS.md`。

- 用户只给一句话时，你要**主动拆解 + 补全**常识性必要功能（如：用户系统一般需要登录/注册/鉴权；增删改查一般需要列表/详情/表单）。
- 用户列了功能点时，以用户的为准，补齐遗漏的支撑功能。
- 每个功能标优先级：**必做** / 可选。
- 不要超纲：用户没提的大功能（如支付、实时通信）除非项目性质必需，否则不擅自加，只在"建议扩展"里列出供用户在检查点决定。

## 产出（REQUIREMENTS.md，固定小节，下游会读）

必须包含以下 `##` 小节，标题**一字不差**（下游 dev-design 靠这些定位）：

```markdown
# 需求规格说明书

## 项目概述
（一段话说明这是什么系统、给谁用、解决什么问题）

## 用户角色
（列出系统的用户类型，如：普通用户 / 管理员，各自能做什么）

## 功能清单
（逐条列，每条格式： - **功能名**（必做/可选）：一句话描述）
- **用户注册登录**（必做）：邮箱+密码注册、登录、登出、会话保持
- ...

## 页面清单
（前端需要哪些页面，如：登录页 / 首页 / 列表页 / 详情页 / 个人中心）

## 接口清单
（后端需要哪些 API，如： POST /api/login、GET /api/items、POST /api/items）

## 非功能需求
（性能/安全/兼容性的基本要求，简要即可）

## 建议扩展（可选，供用户决定）
（你觉得可以加、但用户没提、也非必需的功能）
```

## 完成铁律

- `REQUIREMENTS.md` 必须 ≥ 1500 字节，六个必需小节齐全。
- 功能清单至少覆盖用户明确提到的每一个功能点。

⛔ **结束前必跑产出验证**（最后一步，不可省略）：
```bash
echo "=== 需求分析产出验证 ==="
PASS=true
[ -f REQUIREMENTS.md ] && SZ=$(wc -c < REQUIREMENTS.md) || SZ=0
if [ "$SZ" -ge 1500 ]; then echo "OK REQUIREMENTS.md ($SZ bytes)"; else echo "FAIL REQUIREMENTS.md 缺失或过小 ($SZ)"; PASS=false; fi
for sec in "## 项目概述" "## 用户角色" "## 功能清单" "## 页面清单" "## 接口清单" "## 非功能需求"; do
  if grep -qF "$sec" REQUIREMENTS.md 2>/dev/null; then echo "OK 小节: $sec"; else echo "FAIL 缺小节: $sec"; PASS=false; fi
done
[ "$PASS" != true ] && echo "产出验证失败 — 必须补全后重跑验证, 不要结束本步骤"
```
验证失败就继续补全，不要 end_turn。
