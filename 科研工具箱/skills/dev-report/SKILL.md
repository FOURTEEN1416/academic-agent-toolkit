---
name: dev-report
description: "一句话生成项目·项目报告撰写。把项目文档+代码+测试整理成毕设风格报告(供编译PDF/导出Word)。Use when 项目报告/写报告."
argument-hint: [project-idea]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch
---

# 一句话生成项目 · 项目报告撰写

把已完成的项目整理成一份**毕业设计/技术报告风格**的文档：**$ARGUMENTS**

## ⛔ 铁律：报告素材主要来自文档，别通读整个 code/

写报告的素材以 **REQUIREMENTS.md / DESIGN.md / TEST_REPORT.md** 这几份文档为主（它们已高度概括项目）。**绝不要 Read 整个 code/ 目录**（代码文件多，会撑爆上下文导致反复压缩、写不出报告）。需要引用代码时：
- 用 `ls -R code/ | head -60` 看目录结构；
- 用 `grep`/`head` 抓关键文件的关键片段（如入口函数签名），**不整文件读**。

## 输入（文档为主，代码按需 grep）

- **REQUIREMENTS.md** — 需求规格（主要素材）
- **DESIGN.md** + **schema.sql** — 系统设计、数据库（主要素材）
- **TEST_REPORT.md** — 测试验证结果（主要素材）
- **code/** — 只看目录结构 + grep 关键片段，**不通读**
- **CLAUDE.md** — 项目类型、技术栈（读参数段）

## ⛔ 输出格式（决定产 .tex 还是 .md，下游编译/导出要用）

```bash
grep -q "Word（.docx）\|输出格式：Word\|output_format.*docx" CLAUDE.md && echo "MODE=docx" || echo "MODE=pdf"
```
- **PDF 模式（默认）**：产出 `paper/main.tex`（LaTeX，用 ctexart 中文文档类）+ `paper/sections/*.tex`（可选分节）。下游 `paper-compile` 编译成 PDF。
- **docx 模式**：产出 `paper/main.md`（纯 Markdown，公式用 `$...$`）。下游 `docx-export` 转 Word。

## ⛔ 图表生成（写正文前先画图，报告才有真图，不要只写占位符）

报告的"系统设计/实现"章节需要**架构图、ER 图、流程图**。先用内嵌 draw.io 画出来存 `figures/`，正文再引用真图。

### 画哪些图（读 CLAUDE.md 的 project_type 决定）
- **fullstack**：系统架构图 `fig_arch` + 数据库 ER 图 `fig_er` + 1~2 张核心业务流程图 `fig_flow_1`(`fig_flow_2`)
- **frontend**：系统架构图 `fig_arch` + 1 张核心流程图 `fig_flow_1`（无 ER 图）
- **cli / script**：1 张核心流程图 `fig_flow_1`（架构太简单可省架构图）

### 素材（都是小文件，放心读；⛔ 仍不要通读 code/）
- 架构图 ← DESIGN.md 的"技术架构"+"模块划分"
- ER 图 ← schema.sql（每个 CREATE TABLE 的表名/字段/外键关系）
- 流程图 ← REQUIREMENTS.md 功能清单 + DESIGN.md 的 API/核心流程

### 参考 drawio 规范和示例（运行时 `_utils/` 里有）
```bash
cat _utils/drawio_rules.md 2>/dev/null | head -60      # DrawIO 规范
cat _utils/example_flow.drawio 2>/dev/null | head -50  # 流程图示例 XML 结构
```

### 生成 .drawio（heredoc 分段写，每段 ≤150 行，用单引号 'XMLEOF' 防转义）
文件名固定：`figures/fig_arch.drawio`、`figures/fig_er.drawio`、`figures/fig_flow_1.drawio`。
- 架构图：分层框（前端层 / 后端层 / 数据层），层间箭头标"REST JSON"等；节点写清技术栈。
- ER 图：每张表一个框（表名标题 + 字段列表），表间用带箭头连线表示外键关系。
- 流程图：菱形判断 + 矩形步骤 + 箭头，覆盖一条核心业务链（如"用户登录→鉴权→进主页"）。
- 遵守 drawio_rules.md：`html=1`、无 `shadow=1`、连线 `jumpStyle=arc`、中文 UTF-8、mxCell id 全局唯一。

### 导出图片（先探测 draw.io，非桌面环境没有就跳过、图退回占位符，不阻塞报告）
```bash
echo "=== 图表导出 ==="
# 输出格式决定导出 PDF(LaTeX) 还是 PNG(Markdown/docx)
MODE=$(grep -q "Word（.docx）\|输出格式：Word\|output_format.*docx" CLAUDE.md 2>/dev/null && echo docx || echo pdf)
FMT=$([ "$MODE" = docx ] && echo png || echo pdf)
echo "报告模式=$MODE, 图导出格式=$FMT"

# 探测 draw.io CLI（桌面版内嵌在 PATH；开发机可能没有）
DRAWIO=""
command -v draw.io.exe >/dev/null 2>&1 && DRAWIO="draw.io.exe"
[ -z "$DRAWIO" ] && command -v drawio >/dev/null 2>&1 && DRAWIO="drawio"
if [ -z "$DRAWIO" ]; then
  echo "⚠ 未找到 draw.io CLI — 本环境无法导出图，报告相应位置用占位符（[此处插入XX图]），不阻塞。"
else
  for src in figures/*.drawio; do
    [ -f "$src" ] || continue
    bn=$(basename "$src" .drawio)
    out="figures/${bn}.${FMT}"
    # 后台导出 + 60s 超时，防卡死
    "$DRAWIO" --export --format "$FMT" --crop --output "$out" "$src" >/dev/null 2>&1 &
    DPID=$!; ( sleep 60 && kill $DPID 2>/dev/null ) & TPID=$!
    wait $DPID 2>/dev/null; kill $TPID 2>/dev/null
    if [ -f "$out" ] && [ "$(wc -c < "$out")" -ge 3000 ]; then
      echo "✅ $out ($(wc -c < "$out") 字节)"
    else
      echo "❌ $bn 导出失败/过小 — 重导一次"
      "$DRAWIO" --export --format "$FMT" --crop --output "$out" "$src" >/dev/null 2>&1 &
      DPID=$!; ( sleep 60 && kill $DPID 2>/dev/null ) & TPID=$!; wait $DPID 2>/dev/null; kill $TPID 2>/dev/null
      [ -f "$out" ] && [ "$(wc -c < "$out")" -ge 3000 ] && echo "✅ 重导成功 $out" || echo "⚠ $bn 仍失败, 该图用占位符"
    fi
  done
fi
```

### 正文里引用真图（导出成功的用真图，失败的才用占位符）
- **PDF 模式**（写进 `paper/main.tex` 或分节 .tex）：
  ```latex
  \begin{figure}[H]\centering
  \includegraphics[width=0.9\textwidth,keepaspectratio]{../figures/fig_arch.pdf}
  \caption{系统架构图}\label{fig:arch}
  \end{figure}
  ```
  ⛔ 路径基准：paper-compile 编译时 `cd paper/` 再跑，图在上一级 `figures/`，所以引用路径**必须用 `../figures/fig_arch.pdf`**（见上，与现有论文 sections/*.tex 的约定一致；写成 `figures/...` 会编译找不到图）。
- **docx 模式**（写进 `paper/main.md`）：
  ```markdown
  ![系统架构图](../figures/fig_arch.png)
  ```
  同样注意基准：main.md 在 `paper/` 下，图在 `figures/`，用 `../figures/fig_arch.png`。

⛔ 每个引用前确认图存在（`[ -f figures/fig_arch.pdf ]`）；不存在就用占位符 `[此处插入系统架构图]`，不要引用不存在的文件（会导致编译/导出报错）。

## ⛔ 界面截图（优先复用自测阶段已截的真图，别只写占位符）

自测(dev-selfcheck)阶段联调时**已给运行中的前端界面截了真图**，存在 `figures/shot_*.png`（`shot_home.png`=首页，`shot_<页名>.png`=各页）。"系统实现"章节**优先引用这些真图**，没有对应真图的才退占位符。

```bash
echo "=== 可复用的界面截图 ==="
ls figures/shot_*.png 2>/dev/null && echo "→ 上面这些直接引用进'系统实现'章节" \
  || echo "→ 无界面截图(cli/script 或自测时截图不可用), '系统实现'界面处用占位符"
```

引用方式（同架构图，注意 `../figures/` 基准）：
- **PDF 模式**：`\includegraphics[width=0.9\textwidth,keepaspectratio]{../figures/shot_home.png}` + `\caption{系统主界面}`。
- **docx 模式**：`![系统主界面](../figures/shot_home.png)`。

⛔ 每个引用前确认存在（`[ -f figures/shot_home.png ]`）；存在用真图，不存在才用占位符 `[此处插入XX界面截图]`——绝不引用不存在的文件（会编译/导出报错）。

## 报告结构（毕设/技术报告风格）

```
1. 摘要（项目背景、目标、技术栈、主要成果）
2. 绪论（选题背景与意义、国内外现状简述、本文工作）
3. 需求分析（功能需求、用户角色、用例）——素材来自 REQUIREMENTS.md
4. 系统设计（技术架构、数据库设计、模块划分、API 设计）——素材来自 DESIGN.md/schema.sql
5. 系统实现（关键功能实现、核心代码说明、界面截图——优先引用 figures/shot_*.png 真图）——素材来自 code/
6. 系统测试（测试方法、功能验证结果）——素材来自 TEST_REPORT.md
7. 总结与展望（完成情况、不足、改进方向）
8. 参考文献（技术文档/框架官方文档等，用 scholar 工具查真实文献，禁止编造）
```

## 铁律

- 报告内容必须基于项目**真实产物**（需求/设计/代码/测试都是现成的），不编造功能。
- 代码说明引用真实文件路径和关键片段，不虚构。
- 参考文献用 `$SCHOLAR_SCRIPT` 查真实文献，禁止编造。
- 界面截图**优先引用 figures/shot_*.png**（自测已截的真图）、架构图引用 figures/fig_*.pdf|png；都不存在才退占位符（`[此处插入登录界面截图]`）。
- PDF 模式正文 ≥ 8KB；docx 模式 `paper/main.md` ≥ 8KB。

## ⛔ 恢复场景

若 `paper/main.tex`(或 main.md) 已有部分内容，在其基础上续写完善。

⛔ **结束前必跑产出验证**：
```bash
echo "=== 项目报告产出验证 ==="
PASS=true
MODE=$(grep -q "Word（.docx）\|输出格式：Word\|output_format.*docx" CLAUDE.md 2>/dev/null && echo docx || echo pdf)
echo "MODE=$MODE"
if [ "$MODE" = docx ]; then
  [ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0
  if [ "$SZ" -ge 8192 ]; then echo "OK paper/main.md ($SZ)"; else echo "FAIL paper/main.md 缺失或过小 ($SZ)"; PASS=false; fi
else
  [ -f paper/main.tex ] && SZ=$(wc -c < paper/main.tex) || SZ=0
  if [ "$SZ" -ge 8192 ]; then echo "OK paper/main.tex ($SZ)"; else echo "FAIL paper/main.tex 缺失或过小 ($SZ)"; PASS=false; fi
fi
[ "$PASS" != true ] && echo "产出验证失败 — 必须补全后重跑, 不要结束本步骤"
```
验证失败就继续补全，不要 end_turn。
