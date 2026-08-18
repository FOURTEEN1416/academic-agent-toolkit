---
name: dev-code-frontend
description: "一句话生成项目·前端编码。按设计实现前端界面(React/Vue/纯HTML)。Use when 前端编码/写前端."
argument-hint: [project-idea]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# 一句话生成项目 · 前端编码

按系统设计实现**前端**：**$ARGUMENTS**

## ⛔ 先确认项目类型

读 CLAUDE.md 的"说明/参数"段拿 `project_type` 和技术栈。本步骤只做前端：
- **全栈(fullstack)**：前端放 `code/frontend/`，通过 API 调后端（后端由下一步实现，本步骤按 DESIGN.md 的 API 约定写好调用即可，允许先用假数据/占位）。
- **纯前端(frontend)**：前端放 `code/`，无后端。

## 输入

1. **DESIGN.md**（必须存在）— 架构/API/页面/目录结构。严格按它实现。
2. **REQUIREMENTS.md** — 页面清单、功能清单，逐条实现"必做"页面。
3. **CLAUDE.md** — 技术栈（前端框架）。

## ⛔ 恢复场景

若前端目录已有部分代码（上次跑了一半），在其基础上**续写补全，不要推倒重来**。

## ⛔ 前端审美铁律（界面不能丑）

**必须使用 daisyUI 组件库**，不手写零散 CSS。
- 按需读参考：`cat references/daisyui_ref.md`（组件 class 写法 + 审美原则）。
- **设计风格**：读 CLAUDE.md 的"前端设计风格"段。若指定了某风格，`cat references/styles/<风格>.md` 按其配色/字体/组件规格 + 指定的 daisyUI 主题实现；若是"系统自动"，按项目性质自选一个风格文件参考；若是自定义描述，按描述设计并选最接近的 daisyUI 主题。整站风格统一。
- 用 daisyUI 语义组件：`btn` `card` `navbar` `input` `table` `modal` `menu` `alert` 等。
- 选一个协调主题（`light`/`corporate`/`nord`），在 `<html data-theme="...">` 统一设置。
- 引入优先本地（daisyUI+Tailwind CSS 放本地），CDN 兜底并在 README 注明。
- 布局：统一间距、清晰层次、留白、响应式（`container mx-auto` `grid` `flex` + `sm:`/`lg:`）。

## 目录约定

- 全栈：`code/frontend/`（含 `package.json`、`src/` 或入口 `index.html`）
- 纯前端：`code/`（含 `package.json` 或 `index.html`）
- 同时写 `code/README.md`（说明前端结构）和 `RUN.md`（前端启动步骤，全栈的后端启动步骤下一步补）

## ⛔ 入口铁律（否则预览起不来）

前端目录**必须有明确入口**，预览服务靠它启动：
- **框架项目(React/Vue 等)**：必须有 `package.json` 且 `npm run dev` 能起。
- **纯 HTML 多页项目**：必须有 `index.html` 作为**首页/导航页**。⛔ 绝不能只产 `login.html`/`dashboard.html` 等散页而没有 `index.html` —— 这样预览打开是文件列表，用户找不到入口。若各页面是并列的，就写一个 `index.html` 作导航页（用 daisyUI 卡片/菜单链到各页），或让 `index.html` 直接跳转到主页面。

## 完成铁律

- 前端有真实页面代码（覆盖 REQUIREMENTS 的必做页面），不留大片 TODO 空壳。
- 有 `package.json`(框架项目) 或 `index.html`(纯 HTML)——见上方入口铁律。
- 用 daisyUI，界面美观。

## ⛔⛔ 分步写入规则（防大段写入被截断，务必遵守）

**绝不一次性 Write 一个大文件。** 单次写入过大会被截断，产出残缺代码。规则：
1. **每个文件用 Bash heredoc 分段写，每段 ≤ 150 行**：先 `cat > file` 写第一段，再 `cat >> file` 追加后续段。
2. **heredoc 必须用带单引号的 `'EOF'`** —— 代码含 `$` `\` `` ` `` 等特殊字符，不加引号会被转义成乱码：
   ```bash
   cat > code/frontend/src/App.jsx << 'EOF'
   ...前 150 行...
   EOF
   cat >> code/frontend/src/App.jsx << 'EOF'
   ...后续行...
   EOF
   ```
3. **写完每个文件用 `wc -l 文件` 确认行数符合预期**（验证没被截断）。
4. 一个文件写完就落盘，再写下一个，不要囤在上下文里。

⛔ **结束前必跑产出验证**：
```bash
echo "=== 前端编码产出验证 ==="
PASS=true
FE=code/frontend
[ -d "$FE" ] || FE=code   # 纯前端在 code/ 下
if [ -f "$FE/package.json" ]; then
  echo "OK 前端入口: package.json($FE)"
elif [ -f "$FE/index.html" ]; then
  echo "OK 前端入口: index.html($FE)"
elif find "$FE" -name "*.html" 2>/dev/null | grep -q .; then
  # ⛔ 有 .html 散页但没 index.html —— 预览会打开成文件列表, 必须补首页/导航
  echo "FAIL 有 .html 页面但缺 index.html 入口, 预览起不来 —— 必须补一个 index.html(首页/导航页)"; PASS=false
else
  echo "FAIL 缺 package.json/index.html/任何 .html"; PASS=false
fi
if grep -rqi "daisyui\|tailwind" "$FE" 2>/dev/null; then echo "OK 引用 daisyUI/Tailwind"; else echo "WARN 未检测到 daisyUI, 界面可能偏朴素"; fi
[ -f RUN.md ] && echo "OK RUN.md" || { echo "FAIL 缺 RUN.md"; PASS=false; }
[ "$PASS" != true ] && echo "产出验证失败 — 必须补全后重跑, 不要结束本步骤"
```
验证失败就继续补全，不要 end_turn。

**本步骤后有检查点**：用户可在编辑器「🚀 运行项目」里预览前端、提修改意见，确认后再进入后端编码。
