---
name: dev-code
description: "一句话生成项目·编码实现。按设计文档写真实可运行的代码(全栈/纯前端/CLI/脚本)。Use when user says 编码实现/写代码."
argument-hint: [project-idea]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# 编码实现

按系统设计实现真实可运行的代码：**$ARGUMENTS**

## ⛔ 先确认项目类型

**读 CLAUDE.md 的 `project_type` 决定实现方式**（fullstack / frontend / cli / script）。不同类型目录结构和技术栈不同，按 DESIGN.md 的"目录结构"实现。

## ⛔⛔⛔ 任务规模警示

这是**完整的软件项目**，不是玩具。要按 DESIGN.md 把代码全部实现成**能真正跑起来**的，代码量大，别写一半就退出。end_turn 前自问：主入口写了吗？能跑吗？RUN.md 写了怎么启动吗？任何"否"→继续干。

## 输入

1. **DESIGN.md**（必须存在）— 架构/目录结构/技术选型。严格按它实现。
2. **REQUIREMENTS.md** — 功能清单，逐条实现"必做"项。
3. **schema.sql** — 全栈项目的建表 SQL（仅全栈有）。
4. **CLAUDE.md** — project_type + 技术栈参数。

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

⛔ **结束前必跑产出验证**（按类型自适应）：
```bash
echo "=== 编码产出验证 ==="
PASS=true
PTYPE=$(grep -oE "project_type[:=] *(fullstack|frontend|cli|script)" CLAUDE.md 2>/dev/null | grep -oE "(fullstack|frontend|cli|script)" | head -1)
PTYPE=${PTYPE:-fullstack}
echo "项目类型: $PTYPE"
[ -f RUN.md ] && echo "OK RUN.md" || { echo "FAIL 缺 RUN.md"; PASS=false; }
[ -f code/README.md ] && echo "OK code/README.md" || { echo "FAIL 缺 code/README.md"; PASS=false; }
if [ "$PTYPE" = "fullstack" ]; then
  if [ -f code/backend/main.py ]; then echo "OK backend/main.py"; else echo "FAIL 缺 code/backend/main.py"; PASS=false; fi
  { [ -f code/backend/requirements.txt ] || [ -f code/backend/package.json ]; } && echo "OK 后端依赖清单" || { echo "FAIL 缺后端依赖清单"; PASS=false; }
  [ -d code/frontend ] && echo "OK code/frontend/" || { echo "FAIL 缺 code/frontend/"; PASS=false; }
else
  # 前端/CLI/脚本: code/ 下要有至少一个主源码文件
  N=$(find code -maxdepth 3 -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.jsx" -o -name "*.tsx" -o -name "*.html" \) 2>/dev/null | wc -l)
  if [ "$N" -ge 1 ]; then echo "OK code/ 下有 $N 个源码文件"; else echo "FAIL code/ 无源码文件"; PASS=false; fi
  # ⛔ 纯前端/静态 HTML: 若有 .html 散页但无 index.html + 无 package.json, 预览起不来 → 必须补 index.html
  if [ "$PTYPE" = "frontend" ] && ! [ -f code/package.json ] && ! [ -f code/index.html ] && find code -name "*.html" 2>/dev/null | grep -q .; then
    echo "FAIL 纯前端有 .html 页面但缺 index.html 入口, 预览起不来 —— 必须补一个 index.html(首页/导航)"; PASS=false
  fi
fi
[ "$PASS" != true ] && echo "产出验证失败 — 必须补全后重跑, 不要结束本步骤"
```
验证失败就继续补全，不要 end_turn。
