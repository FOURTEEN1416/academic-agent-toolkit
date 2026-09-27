---
name: dev-code
description: "一句话生成项目·编码实现。按设计文档写真实可运行的代码(全栈/纯前端/CLI/脚本)。Use when user says 编码实现/写代码."
argument-hint: [project-idea]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# 编码实现

按系统设计实现真实可运行的代码：**$ARGUMENTS**

## ⛔ 先确认项目类型

**读 AGENTS.md 的 `project_type` 决定实现方式**（fullstack / frontend / cli / script）。不同类型目录结构和技术栈不同，按 DESIGN.md 的"目录结构"实现。

## ⛔⛔⛔ 任务规模警示

这是**完整的软件项目**，不是玩具。要按 DESIGN.md 把代码全部实现成**能真正跑起来**的，代码量大，别写一半就退出。end_turn 前自问：主入口写了吗？能跑吗？RUN.md 写了怎么启动吗？任何"否"→继续干。

## 输入

1. **DESIGN.md**（必须存在）— 架构/目录结构/技术选型。严格按它实现。
2. **REQUIREMENTS.md** — 功能清单，逐条实现"必做"项。
3. **schema.sql** — 全栈项目的建表 SQL（仅全栈有）。
4. **AGENTS.md** — project_type + 技术栈参数。

## 各类型目录约定（按 project_type）

- **fullstack**：`code/frontend/`（前端+package.json）+ `code/backend/`（入口 `code/backend/main.py`、requirements.txt、database.py）+ `code/README.md` + `RUN.md`
- **frontend**：`code/`（前端项目，入口 index.html 或框架入口 + package.json）+ `code/README.md` + `RUN.md`
- **cli**：`code/`（源码，主入口如 `code/main.py`/`code/cli.py`、requirements.txt）+ `code/README.md` + `RUN.md`
- **script**：`code/`（源码，主脚本如 `code/main.py`）+ `code/README.md` + `RUN.md`

`RUN.md`（工作区根）：写清怎么装依赖、怎么启动/运行。

## ⛔ 前端审美铁律（fullstack / frontend 类型必读）

前端**必须使用 daisyUI 组件库**，不手写零散 CSS：
- 按需读参考：`cat references/daisyui_ref.md`（本 skill 自带）获取组件 class 和主题。
- 用 daisyUI 语义组件：`btn` `card` `navbar` `input` `table` `alert` `modal` `menu` 等。
- 选协调主题（`light`/`corporate`/`nord`），`<html data-theme="...">` 统一设置。
- 优先本地引入（CSS 放 `code/frontend/` 本地），CDN 兜底并在 README 注明离线方案。
- 布局遵循基本原则：`container mx-auto`、统一间距、清晰层次、响应式（`sm:`/`lg:`）。禁止裸 HTML 无样式表单/按钮。

## 完成铁律

- 主入口存在且是有效代码（全栈后端 `code/backend/main.py` 是有效应用；其余 `code/` 下有明确主入口）。
- 有依赖清单（Python→requirements.txt，Node→package.json）。
- `RUN.md` + `code/README.md` 齐全。
- 真实业务逻辑，不留大片 `# TODO` 空函数。
- ⛔ **恢复场景**：若 `code/` 已有部分代码（上次跑了一半），在其基础上**续写补全，不要推倒重来**。

## ⛔⛔ 分步写入规则（防大段写入被截断，务必遵守）

**绝不一次性 Write 一个大文件。** 单次写入过大会被截断，产出残缺代码。规则：
1. **每个文件用 Bash heredoc 分段写，每段 ≤ 150 行**：先 `cat > file` 写第一段，再 `cat >> file` 追加后续段。
2. **heredoc 必须用带单引号的 `'EOF'`** —— 代码含 `$` `\` `` ` `` 等特殊字符，不加引号会被转义成乱码：
   ```bash
   cat > code/main.py << 'EOF'
   ...前 150 行...
   EOF
   cat >> code/main.py << 'EOF'
   ...后续行...
   EOF
   ```
3. **写完每个文件用 `wc -l 文件` 确认行数符合预期**（验证没被截断）。
4. 一个文件写完就落盘，再写下一个，不要囤在上下文里。

产出结构、存在性和最低完整性由 `finish` 按模板中的 `output_contract` 自动核验；修复返回的具体问题，不复制执行验证脚本。
验证失败就继续补全，不要 end_turn。

## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

保留实际输入来源与模板信息；其内容摘要由程序记录。
