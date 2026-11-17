---
name: doc-poster-latex
description: "Create professional research posters in LaTeX (beamerposter, tikzposter, baposter): layout design, color schemes, multi-column formats, figure integration, poster best practices. Use when 用户说\"做学术海报\"\"会议海报\"\"LaTeX 海报\"或要把论文改成一页海报；从已成稿论文走流水线生成海报改用 paper-poster。"
allowed-tools: Read Write Edit Bash
metadata:
  version: "1.1"
---


<!--ACAT-ADAPTED: 资产补齐自 K-Dense-AI/scientific-agent-skills@36d8f13a1e754618794bf42f417884940077b4ae（MIT，fork FOURTEEN1416）。上游 research-lookup/parallel-cli 等 API 依赖在本仓库不可直接运行，以当前 Agent 的联网检索/网页抓取能力替代；溯源见 references/UPSTREAM.md。2026-09-09 专项治理。2026-11-16 重收编：融入上游 2d2065f（v2.72.0，目录已重组为 latex-posters）增量——三份模板与九个参考件/脚本文件按上游补丁更新（ai_graphics_for_posters.md 与 poster_content_guide.md 采纳上游重写稿并保留本地去工具名适配），正文补 AI 生图准确性边界、SVG→PDF 转换、baposter 存档类来源与 generate_schematic 助手新契约（OpenRouter images 端点 + 评审模型 + 1-2 轮迭代不自动重试）。-->
# LaTeX Research Posters

## Overview

Research posters are a critical medium for scientific communication at conferences and academic events. This skill provides end-to-end guidance for professional LaTeX posters—layout, typography, color schemes, and visual hierarchy.

## When to Use This Skill

适用于：会议/研讨会/开放日的学术海报制作；论文转海报；课题组/院系模板海报；需要满足特定会议尺寸（A0、A1、36×48" 等）与多栏排版、集成图表公式引用的海报任务。（从已成稿论文走流水线生成海报的场景改用 paper-poster，见 frontmatter 分流说明。）

## AI-Powered Visual Element Generation

**STANDARD WORKFLOW: Generate ALL major visual elements using AI before creating the LaTeX poster.** 推荐流程：① 规划全部视觉元素（title/intro/methods/results/conclusions）→ ② 用 scientific-schematics 或 Nano Banana Pro 逐一生成 → ③ 在 LaTeX 模板中组装图片 → ④ 在视觉周围补文字。**Target: 60-70% poster area 为 AI 生成视觉、30-40% 文字。**

**⚠️ 准确性边界（上游 v2.72.0 增补）：** AI 生图仅适合概念性示意图，不是必需工序、没有"AI 图占比"硬指标。数值图、统计汇总、显微/谱学/仪器数据必须来自分析代码与原始观测——**不得用图像模型编造数值图表、显微照片、谱图或结果**。精确通路/流程/架构图优先手写 TikZ 或矢量编辑器（可先出 AI 草稿再人工核校）。不要为迁就配图而取舍或压制对比方法；坐标轴、单位、图例、基线、分母与不确定性信息必须保留。标题、引文、数值与二维码保持 LaTeX/绘图代码可编辑。

---

### CRITICAL: Preventing Content Overflow

**⚠️ POSTERS MUST NOT HAVE TEXT OR CONTENT CUT OFF AT EDGES.**

**Common Overflow Problems:** 标题/页脚越出页界、section 塞太多、图贴边、文本块超栏宽——四类都属「内容超出可用空间」，按下述 Prevention Rules 逐条防。

**Prevention Rules:**

**1. Limit Content Sections (MAXIMUM 5-6 sections for A0):** ✅ 5 sections（Title / Introduction / Methods / Results 1-2 key findings / Conclusions）留白充足；❌ 8+ sections（Overview+Introduction+Background+Methods+Results 1+Results 2+Discussion+Conclusions+Future Work）必然拥挤。

**2. Set Safe Margins in LaTeX:** tikzposter 用 `margin=25mm`（`\documentclass[25pt, a0paper, portrait, margin=25mm]{tikzposter}`）；baposter 在 `\begin{poster}{...}` 里给足 `colspacing`（如 2em）、压低 `headerheight`（如 0.1\textheight），底部留空。

**3. Figure Sizing - Never 100% Width:** `\includegraphics[width=0.85\linewidth]{figure.png}`（NOT 1.0\linewidth），给图四周留边。

**4. Check for Overflow Before Printing:** 编译后按 Section 11 Step 2 执行（`grep -i "overfull" poster.log` + 100% zoom 查四边），存在任何溢出先修再继续。

**5. Word Count Limits:**
- **A0 poster**: 300-800 words MAXIMUM
- **Per section**: 50-100 words maximum
- **If you have more content**: Cut it or make a handout

---

### CRITICAL: Poster-Size Font Requirements

**⚠️ ALL text within AI-generated visualizations MUST be poster-readable.** 每条生成 prompt 都必须带字号规格——海报图在 4-6 英尺外观看，文字必须 LARGE。

**⚠️ COMMON PROBLEM: Content Overflow and Density**——AI 海报图形的头号问题是**内容过多**（后果：文字溢出边界、字号小到不可读、视觉拥挤、留白不足）。**SOLUTION: Generate SIMPLE graphics with MINIMAL content.**

**MANDATORY prompt requirements for EVERY poster graphic:**

```
POSTER FORMAT REQUIREMENTS (STRICTLY ENFORCE):
- ABSOLUTE MAXIMUM 3-4 elements per graphic (3 is ideal)
- ABSOLUTE MAXIMUM 10 words total in the entire graphic
- NO complex workflows with 5+ steps (split into 2-3 simple graphics instead)
- NO multi-level nested diagrams (flatten to single level)
- NO case studies with multiple sub-sections (one key point per case)
- ALL text GIANT BOLD (80pt+ for labels, 120pt+ for key numbers)
- High contrast ONLY (dark on white OR white on dark, NO gradients with text)
- MANDATORY 50% white space minimum (half the graphic should be empty)
- Thick lines only (5px+ minimum), large icons (200px+ minimum)
- ONE SINGLE MESSAGE per graphic (not 3 related messages)
```

**⚠️ BEFORE GENERATING: Review your prompt and count elements**——按 Step 0 的四问审查执行（元素数 / 复杂度 / 词数 / 单消息），任一不过先简化或拆分再生成。

**Content limits per graphic type (STRICT):**
| Graphic Type | Max Elements | Max Words | Reject If | Good Example |
|--------------|--------------|-----------|-----------|--------------|
| Flowchart | **3-4 boxes MAX** | **8 words** | 5+ stages, nested steps | "DISCOVER → VALIDATE → APPROVE" (3 words) |
| Key findings | **3 items MAX** | **9 words** | 4+ metrics, paragraphs | "95% ACCURATE" "2X FASTER" "FDA READY" (6 words) |
| Comparison chart | **3 bars MAX** | **6 words** | 4+ methods, legend text | "OURS: 95%" "BEST: 85%" (4 words) |
| Case study | **1 case, 3 elements** | **6 words** | Multiple cases, substories | Logo + "18 MONTHS" + "to discovery" (2 words) |
| Timeline | **3-4 points MAX** | **8 words** | Year-by-year detail | "2020 START" "2022 TRIAL" "2024 APPROVED" (6 words) |

**Example - WRONG vs CORRECT (workflow):**
```bash
# ❌ BAD - 7-stage 逐段展开：7+ stages with tiny text, unreadable from 6 feet - POSTER FAILURE
python scripts/generate_schematic.py "Drug discovery workflow showing: Stage 1 Target Identification, Stage 2 Molecular Synthesis, Stage 3 Virtual Screening, Stage 4 AI Lead Optimization, Stage 5 Clinical Trial Design, Stage 6 FDA Approval. Include success metrics, timelines, and validation steps for each stage." -o figures/workflow.png

# ✅ GOOD - 同一内容收敛为一张 3-box 高层图；细节图按需另出（clean, impactful, readable）
python scripts/generate_schematic.py "POSTER FORMAT for A0. ULTRA-SIMPLE 3-box workflow: 'DISCOVER' → 'VALIDATE' → 'APPROVE'. Each word in GIANT bold (120pt+). Thick arrows (10px). 60% white space. NO substeps, NO details. 3 words total. Readable from 10 feet." -o figures/workflow_overview.png
```

**Case study 同理**：多案例塞一张图 = 12+ 元素的小字灾难（❌）；✅ 正确做法是一图一案一指标（logo + '18 MONTHS' + 'to discovery'），需要 3 个案例就生成 3 张简单图。**Key findings 同理**：8 项指标全上（❌）；✅ 只留 top 3 做大字卡片（'95% ACCURACY' / '2X FASTER' / 'VALIDATED'）。

**Font size reference for poster prompts:**
| Element | Minimum Size | Prompt Keywords |
|---------|--------------|-----------------|
| Main numbers/metrics | 72pt+ | "huge", "very large", "giant", "poster-size" |
| Section titles | 60pt+ | "large bold", "prominent" |
| Labels/captions | 36pt+ | "readable from 6 feet", "clear labels" |
| Body text | 24pt+ | "poster-readable", "large text" |

**Always include in prompts:** "POSTER FORMAT / for A0 poster / readable from 6 feet" + "VERY LARGE TEXT / huge bold fonts" + 应出现的具体文字（烤进图里）+ "minimal text, maximum impact" + "high contrast" + "generous margins, no text near edges"。

---

### CRITICAL: AI-Generated Graphic Sizing

**⚠️ Each AI-generated graphic should focus on ONE concept with MINIMAL content.** 复杂图必然导致小字：元素越多、字号越小。上限一律按上方 MANDATORY requirements 与 Content limits 表执行（3-4 elements / ≤10 words / 流程 ≤4 步 / 对比 ≤3 项 / 不嵌套），不要按本文件早期流传的「3-5 elements / 10-15 words」宽松口径。

**Split complex content into multiple simple graphics:**
```
Instead of 1 complex diagram with 12 elements:
→ Create 3 simple diagrams with 4 elements each
→ Each graphic can have LARGER text
→ Arrange in poster with clear visual flow
```

---

### Step 0: MANDATORY Pre-Generation Review (DO THIS FIRST)

**⚠️ BEFORE generating ANY graphics, review your content plan:**

**For EACH planned graphic, ask these questions:**
1. **Element count**: 3-4 items or less? ❌ NO → Simplify or split into multiple graphics
2. **Complexity check**: multi-stage workflow (5+ steps) or nested diagram? ❌ YES → Flatten to 3-4 high-level steps only
3. **Word count**: all text in 10 words or less? ❌ NO → Cut text, use single-word labels
4. **Message clarity**: ONE clear message? ❌ NO → Split into multiple focused graphics

**Common patterns that ALWAYS fail (reject these):**
- "Show stages 1 through 7..." → Split into high-level overview (3 stages) + detail graphics
- "Multiple case studies..." → One case per graphic
- "Timeline from 2015 to 2024 with annual milestones..." → Show only 3-4 key years
- "Comparison of 6 methods..." → Show only top 3 or Our method vs Best baseline
- "Architecture with all layers and connections..." → High-level only (3-4 components)

### Step 1: Plan Your Poster Elements

After passing the pre-generation review, identify visual elements needed:

1. **Title Block** - Stylized title with institutional branding (optional - can be LaTeX text)
2. **Introduction Graphic** - Conceptual overview (3 elements max)
3. **Methods Diagram** - High-level workflow (3-4 steps max)
4. **Results Figures** - Key findings (3 metrics max per figure, may need 2-3 separate figures)
5. **Conclusion Graphic** - Summary visual (3 takeaways max)
6. **Supplementary Icons** - Simple icons, QR codes, logos (minimal)

### Step 2: Generate Each Element (After Pre-Generation Review)

**⚠️ CRITICAL: Review Step 0 checklist before proceeding.** 按元素类型选工具与 prompt 模式：

**For Schematics and Diagrams (scientific-schematics):**
```bash
# Create figures directory
mkdir -p figures

# Workflow - HIGH-LEVEL ONLY, 3 stages（7-stage 原始计划按 Step 0 拆掉）
# BAD: "Stage 1: Target ID, Stage 2: Molecular Synthesis, Stage 3: Virtual Screening, Stage 4: AI Lead Opt..."
# GOOD: Collapse to 3 mega-stages
python scripts/generate_schematic.py "POSTER FORMAT for A0. ULTRA-SIMPLE 3-box workflow: 'DISCOVER' (120pt bold) → 'VALIDATE' (120pt bold) → 'APPROVE' (120pt bold). Thick arrows (10px). 60% white space. ONLY these 3 words. NO substeps. Readable from 12 feet." -o figures/workflow_simple.png

# Case study 按「一图一案一指标」口径生成（见上方 Case study 同理段）；3 个案例 = 3 张简单图
```

**For Stylized Blocks and Graphics (Nano Banana Pro):**
```bash
# Conclusion/summary - ONLY 3 items, GIANT numbers
python scripts/generate_schematic.py "POSTER FORMAT for A0. KEY FINDINGS with EXACTLY 3 cards only. Card 1: '95%' (150pt font) with 'ACCURACY' (60pt). Card 2: '2X' (150pt) with 'FASTER' (60pt). Card 3: checkmark icon with 'READY' (60pt). 50% white space. NO other text. Readable from 10 feet." -o figures/conclusions_graphic.png
```

其余类型（architecture/timeline/title block/intro/background）按同一 prompt 模式与 Content limits 表生成（POSTER FORMAT for A0 + 元素上限 + GIANT 字号 + 留白 + 观看距离 + 精确词数）。

**For Data Visualizations - SIMPLE, 3 bars max:**
```bash
# SIMPLE chart with ONLY 3 bars, GIANT labels
python scripts/generate_schematic.py "POSTER FORMAT for A0. SIMPLE bar chart with ONLY 3 bars: BASELINE (70%), EXISTING (85%), OURS (95%). GIANT percentage labels ON the bars (100pt+). NO axis labels, NO legend, NO gridlines. Our bar highlighted in different color. 40% white space. Readable from 8 feet." -o figures/comparison_chart.png
```

### Step 2b: MANDATORY Post-Generation Review (Before Assembly)

**⚠️ CRITICAL: Review EVERY generated graphic before adding to poster.** 每图在 25% zoom 下逐项检查：

1. **✅ PASS criteria (all must be true):** 25% zoom 下全部文字清晰可读；元素 ≤3-4；留白 ≥50%；2 秒内能看懂；无 5+ 步复杂流程、无多层嵌套。

2. **❌ FAIL criteria (regenerate if ANY are true):** 文字小/难读 → REGENERATE with "150pt+" fonts；元素 >4 → REGENERATE with "ONLY 3 elements"；留白 <50% → REGENERATE with "60% white space"；复杂多阶段流程或多案例挤一图 → SPLIT into 2-3 simple graphics；3 秒看不懂 → SIMPLIFY and regenerate。

**Common failures and fixes**: 见 Step 0 的「Common patterns that ALWAYS FAIL」（拆分/简化口径一致），FAIL 项按修复口径重新生成后再复查。

**DO NOT PROCEED to assembly if ANY graphic fails the checks above.**

### Step 3: Assemble in LaTeX Template

After all figures pass the post-generation review, include them in your poster template:

**tikzposter example**（完整可编译模板见 `assets/tikzposter_template.tex`；图宽一律 <1.0\linewidth 留边）:
```latex
\documentclass[25pt, a0paper, portrait]{tikzposter}
\begin{document}
\maketitle
\begin{columns}
\column{0.5}
\block{Introduction}{%
  \centering\includegraphics[width=0.85\linewidth]{figures/intro_visual.png}}
\block{Methods}{%
  \centering\includegraphics[width=0.9\linewidth]{figures/methods_flowchart.png}}
\column{0.5}
\block{Results}{%
  \centering\includegraphics[width=0.9\linewidth]{figures/comparison_chart.png}}
\block{Conclusions}{%
  \centering\includegraphics[width=0.8\linewidth]{figures/conclusions_graphic.png}}
\end{columns}
\end{document}
```

**baposter example**: 见 `assets/baposter_template.tex`——结构同类，每栏用 `\headerbox{Title}{name=...,column=...,row=...}` 包裹 `\includegraphics`（宽度建议 0.95\linewidth 以下，留出边距）。

### Example: Complete Poster Generation Workflow

端到端串联（各步骤细节一律引用上文对应小节，不重复 prompts）：

```bash
# STEP 0: Pre-Generation Review (MANDATORY，见 Step 0)：7 stages → 3 mega-stages ✅；3 case studies → 一图一案 ✅；timeline 2018-2024 → 只留 3 个关键年 ✅

mkdir -p figures

# STEP 2: 按上方 Step 2 prompt 模式生成 workflow/case1-3/timeline/results（ULTRA-SIMPLE：3-4 elements、GIANT fonts、60% white space）

# STEP 2b: Post-Generation Review (MANDATORY，见 Step 2b)
# 每图 25% zoom 检查：元素数、可读性、留白——ALL PASS 才继续

pdflatex poster.tex

# STEP 4: PDF Overflow Check (见 Section 11)
grep "Overfull" poster.log
# Open at 100% and check all 4 edges
```

任一图未过 Step 2b：按 Step 2b 的 FAIL→fix 口径重新生成后再组装。

### Visual Element Guidelines

**⚠️ CRITICAL: Each graphic must have ONE message and MAXIMUM 3-4 elements.** 硬限制（元素/词数/留白/字号）、MANDATORY prompt 要素与失败模式一律按「AI-Powered Visual Element Generation」权威口径与 Step 0 执行，此处不重复。

**For each poster section - STRICT requirements:**

| Section | Max Elements | Max Words | Example Prompt (REQUIRED PATTERN) |
|---------|--------------|-----------|-------------------------------------|
| **Introduction** | 3 icons | 6 words | "POSTER FORMAT for A0: ULTRA-SIMPLE 3 icons: [icon1] [icon2] [icon3]. ONE WORD labels (100pt bold). 60% white space. 3 words total." |
| **Methods** | 3 boxes | 6 words | "POSTER FORMAT for A0: ULTRA-SIMPLE 3-box workflow: 'STEP1' → 'STEP2' → 'STEP3'. GIANT labels (120pt+). 60% white space. 3 words only." |
| **Results** | 2-3 bars | 6 words | "POSTER FORMAT for A0: TWO bars: 'BASELINE 70%' 'OURS 95%'. GIANT percentages (150pt+) ON bars. NO axis. 60% white space." |
| **Conclusions** | 3 cards | 9 words | "POSTER FORMAT for A0: THREE cards: '95%' (150pt) 'ACCURATE', '2X' (150pt) 'FASTER', checkmark 'READY'. 60% white space." |
| **Case Study** | 3 elements | 5 words | "POSTER FORMAT for A0: ONE case: logo + '18 MONTHS' (150pt) + 'to discovery' (60pt). 60% white space." |
| **Timeline** | 3 points | 3 words | "POSTER FORMAT for A0: THREE years only: '2018' '2021' '2024' (150pt each). Large icons. 60% white space. NO details." |

---

## Scientific Schematics Integration

For detailed guidance on creating schematics, refer to the **scientific-schematics** skill documentation.

**Key capabilities:**
- Nano Banana Pro automatically generates, reviews, and refines diagrams
- Creates publication-quality images with proper formatting
- Ensures accessibility (colorblind-friendly, high contrast)
- Supports iterative refinement for complex diagrams

---

## Core Capabilities

### 1. LaTeX Poster Packages

三选一（详细对比与各包专属指引见 `references/latex_poster_packages.md`）：
- **beamerposter**: Beamer 扩展，语法对 Beamer 熟手友好、主题与机构品牌支持强——适合传统学术海报。
- **tikzposter**: TikZ 集成、现代灵活、内置配色主题与版式模板——适合彩色现代设计与自定义图形。
- **baposter**: 盒式布局系统、自动间距定位、默认样式专业——适合多栏一致排版。

### 2. Poster Layout and Structure

Create effective poster layouts following visual communication principles. For comprehensive layout guidance, refer to `references/poster_layout_design.md`.

**Common Poster Sections**: Header/Title（标题、作者、机构、logo）→ Introduction/Background（研究语境与动机）→ Methods/Approach（方法与实验设计）→ Results（关键发现 + 图表）→ Conclusions（要点与结论）→ References（精选文献）→ Acknowledgments（资助/合作者/机构）。

**Layout Strategies**: 栏式布局（2/3/4 栏网格）、块式布局（内容块灵活排布）、Z 型阅读动线、视觉层级（用字号/颜色/间距突出重点）。

### 3. Design Principles for Research Posters

Apply evidence-based design principles for maximum impact. For detailed design guidance, refer to `references/poster_design_principles.md`.

**Typography**: Title 72-120pt / section headers 48-72pt / body 24-36pt minimum（与 Section 11 Step 3 质检口径一致）；无衬线字体（Arial/Helvetica/Calibri），全篇 ≤2-3 个字体族。

**Color and Contrast**: 高对比配色保证可读；机构色板做品牌；色盲友好（避红绿组合）；留白是主动设计空间，别塞满。

**Visual Elements**: 印刷图 ≥300 DPI；图上标签大而清晰；全篇图风格一致；善用图标与图形；图文比约 40-50% 视觉。

**Content Guidelines**: 全文 300-800 words（与溢出 Prevention 的 Word Count Limits 一致）；bullet 优先于段落、图自解释、少即是多；QR 码挂补充材料或在线资源。

### 4. Standard Poster Sizes

Support for international and conference-specific poster dimensions:

**International Standards**:
- A0 (841 × 1189 mm / 33.1 × 46.8 inches) - Most common European standard
- A1 (594 × 841 mm / 23.4 × 33.1 inches) - Smaller format
- A2 (420 × 594 mm / 16.5 × 23.4 inches) - Compact posters

**North American Standards**:
- 36 × 48 inches (914 × 1219 mm) - Common US conference size
- 42 × 56 inches (1067 × 1422 mm) - Large format
- 48 × 72 inches (1219 × 1829 mm) - Extra large

**Orientation**:
- Portrait (vertical) - Most common, traditional
- Landscape (horizontal) - Better for wide content, timelines

### 5. Package-Specific Templates

三套开箱即用模板在 `assets/`：`beamerposter_template.tex`、`tikzposter_template.tex`、`baposter_template.tex`（完整清单与说明见文末 Templates 节）。

### 6. Figure and Image Integration

Optimize visual content for poster presentations:

**Best Practices**:
- Use vector graphics (PDF, SVG) when possible for scalability; **SVG 须先转 PDF 再 `\includegraphics`**——pdfLaTeX 不直接支持 SVG（上游 v2.72.0 增补）
- Raster images: minimum 300 DPI at final print size
- Consistent image styling (borders, captions, sizes)
- Group related figures together
- Use subfigures for comparisons

**LaTeX Figure Commands**:
```latex
\usepackage{graphicx}   % 必备
\includegraphics[width=0.8\linewidth]{figure.pdf}   % 简单图（宽 <1.0 留边）

% tikzposter 中带 caption 的图
\block{Results}{%
  \begin{tikzfigure}
    \includegraphics[width=0.9\linewidth]{results.png}
  \end{tikzfigure}}

% 多子图用 subcaption 包：\begin{subfigure}{0.48\linewidth}...\end{subfigure} 两个并排
```

### 7. Color Schemes and Themes

Provide professional color palettes for various contexts:

**Academic Institution Colors**:
- Match university or department branding
- Use official color codes (RGB, CMYK, or LaTeX color definitions)

**Scientific Color Palettes** (color-blind friendly):
- Viridis: Professional gradient from purple to yellow
- ColorBrewer: Research-tested palettes for data visualization
- IBM Color Blind Safe: Accessible corporate palette

**Package-Specific Theme Selection**: beamerposter 用 `\usetheme{...}` + `\usecolortheme{...}`（如 Berlin / beaver）；tikzposter 用 `\usetheme{...}` + `\usecolorstyle{...}`（如 Rays / Denmark）；baposter 在 `\begin{poster}{...}` 里设 `background=plain, bgColorOne=white, headerColorOne=blue!70, textborder=rounded`。完整主题与配色对比见 `references/latex_poster_packages.md`。

### 8. Typography and Text Formatting

**Font Selection**: 海报推荐无衬线——`\usepackage{helvet}`（Helvetica）或 `avant`（Avant Garde），数学用 `sfmath`；`\renewcommand{\familydefault}{\sfdefault}` 设默认无衬线。

**Text Sizing**（beamerposter）: `\setbeamerfont{title}{size=\VeryHuge}`、`\setbeamerfont{author}{size=\Large}`、`\setbeamerfont{institute}{size=\normalsize}`。

**Emphasis and Highlighting**: 关键词 `\textbf{important}`、少量 `\textcolor{blue}{highlight}` 高亮、关键信息加框；避免斜体（远距离难读）。

### 9. QR Codes and Interactive Elements

**QR Code Integration**: `\usepackage{qrcode}` + `\qrcode[height=2cm]{https://github.com/username/project}`；带说明的样式用 `\begin{center}\qrcode[height=3cm]{https://doi.org/...}\\ \small Scan for full paper\end{center}`。

**Digital Enhancements**: 二维码/链接指向 GitHub 代码仓、视频演示、交互式可视化、补充数据或附录。

### 10. Compilation and Output

Generate high-quality PDF output for printing or digital display:

**Compilation Commands**: 基本编译 `pdflatex poster.tex`；带参考文献按 `pdflatex → bibtex poster → pdflatex → pdflatex` 四连跑；beamer 系海报可用 `lualatex poster.tex`（更好字体支持）或 `xelatex poster.tex`（Unicode 与现代字体）。

**Ensuring Full Page Coverage**:

Posters should use the entire page without excessive margins. Configure packages correctly:

**Full Page Setup（关键参数速查，完整可编译模板见 `assets/`）**:
- **beamerposter**: `\documentclass[final,t]{beamer}` + `\usepackage[size=a0,scale=1.4,orientation=portrait]{beamerposter}`；`\setbeamersize{text margin left=0mm, text margin right=0mm}` 去默认边距，再用 `\usepackage[margin=10mm]{geometry}` 精确控边；清掉 navigation symbols / footline / headline。
- **tikzposter**: `\documentclass[25pt,a0paper,portrait,margin=10mm,innermargin=15mm,blockverticalspace=15mm,colspace=15mm,subcolspace=8mm]{tikzposter}`。
- **baposter**: `\documentclass[a0paper,portrait,fontscale=0.285]{baposter}` + `\begin{poster}{grid=false, columns=3, colspacing=1.5em, headerheight=0.12\textheight, boxheaderheight=2em, ...}`。

**Common Issues and Fixes**:
- **Large white margins**: 调小 margin——beamerposter `\setbeamersize{text margin left=5mm, text margin right=5mm}`；tikzposter `margin=5mm, innermargin=10mm`；baposter `\documentclass[a0paper, margin=5mm]{baposter}`。
- **Content doesn't fill vertical space**: 段落间插 `\vfill`（`\block{Introduction}{...}` `\vfill` `\block{Methods}{...}`） distributing space；或对特定块手动 `\vspace{1cm}`。
- **Poster extends beyond page boundaries**: 核对总宽（3 栏时 = 3×columnwidth + 2×colspace + 2×margins，应等于 \paperwidth）；调试可加可见页界：`\usepackage{eso-pic}` + `\AddToShipoutPictureBG{\AtPageLowerLeft{\put(0,0){\framebox(\LenToUnit{\paperwidth},\LenToUnit{\paperheight}){}}}}`。

**Print Preparation / Digital Display**: 按 Section 11 Step 9 的打印前清单执行（PDF/X-1a、字体全嵌入、CMYK/RGB 色彩空间、图片 ≥300 DPI、bleed 3-5mm、页面尺寸精确核对）；数字显示侧用 RGB、压缩文件体积并在多屏测试可读性。

### 11. PDF Review and Quality Control

**CRITICAL**: Always review the generated PDF before printing or presenting. Use this systematic checklist:

**质检分栏总览（先分清哪些能自动跑、哪些必须人看——不要把不可执行项伪装成已检查）：**

| 类别 | 步骤 | 工具 / 方法 |
|------|------|-------------|
| ✅ 可自动化 | Step 1 页面尺寸 | `pdfinfo poster.pdf` |
| ✅ 可自动化 | Step 2a 溢出警告 | `grep -i "overfull\|underfull\|badbox" poster.log` |
| ✅ 可自动化 | Step 5 字体嵌入 / 图片分辨率 | `pdffonts poster.pdf` / `pdfimages -list poster.pdf` |
| ✅ 可自动化 | Step 8 编译日志复查 | `grep -i "warning\|error" poster.log` |
| ✅ 可自动化 | 一键汇总 | `bash scripts/review_poster.sh poster.pdf` |
| 👤 须人工 | Step 2b 四边视觉检查 | PDF 100% zoom 逐边核对 |
| 👤 须人工 | Step 3 视觉检查清单 | 逐项打勾（排版/字号/图质量/内容完整） |
| 👤 须人工 | Step 4 缩尺打印测试 | A4 试印（≈25%），距 2-3 英尺读 |
| 👤 须人工 | Step 6 可访问性 | 对比度/色盲模拟工具 + 人眼复核 |
| 👤 须人工 | Step 7 校对与同事评审 | 拼写/数字核对、30 秒测试、5 分钟评审 |
| 👤 须人工 | Step 9 打印前确认 | 与印刷厂核对规格、试印签样 |

**Step 1: Page Size Verification（✅ 可自动化）**
```bash
# Check PDF dimensions (should match poster size exactly)
pdfinfo poster.pdf | grep "Page size"

# Expected outputs:
# A0: 2384 x 3370 points (841 x 1189 mm)
# 36x48": 2592 x 3456 points
# A1: 1684 x 2384 points (594 x 841 mm)
```

**Step 2: OVERFLOW CHECK (CRITICAL) - DO THIS IMMEDIATELY AFTER COMPILATION（2a 可自动化 / 2b 须人工）**

**⚠️ THIS IS THE #1 CAUSE OF POSTER FAILURES. Check BEFORE proceeding.**

**Step 2a: Check LaTeX Log File**
```bash
# Check for overflow warnings (these are ERRORS, not suggestions)
grep -i "overfull\|underfull\|badbox" poster.log

# ANY "Overfull" warning = content is cut off or extending beyond boundaries
# FIX ALL OF THESE before proceeding
```

**Common overflow warnings and what they mean:**
- `Overfull \hbox (15.2pt too wide)` → Text or graphic is 15.2pt wider than column
- `Overfull \vbox (23.5pt too high)` → Content is 23.5pt taller than available space
- `Badbox` → LaTeX struggling to fit content within boundaries

**Step 2b: Visual Edge Inspection (100% zoom in PDF viewer)**

**Check ALL FOUR EDGES systematically:**

1. **TOP EDGE:**
   - [ ] Title completely visible (not cut off)
   - [ ] Author names fully visible
   - [ ] No graphics touching top margin
   - [ ] Header content within safe zone

2. **BOTTOM EDGE:**
   - [ ] References fully visible (not cut off)
   - [ ] Acknowledgments complete
   - [ ] Contact info readable
   - [ ] No graphics cut off at bottom

3. **LEFT EDGE:**
   - [ ] No text touching left margin
   - [ ] All bullet points fully visible
   - [ ] Graphics have left margin (not bleeding off)
   - [ ] Column content within bounds

4. **RIGHT EDGE:**
   - [ ] No text extending beyond right margin
   - [ ] Graphics not cut off on right
   - [ ] Column content stays within bounds
   - [ ] QR codes fully visible

5. **BETWEEN COLUMNS:**
   - [ ] Content stays within individual columns
   - [ ] No text bleeding into adjacent columns
   - [ ] Figures respect column boundaries

**If ANY check fails, you have overflow. FIX IMMEDIATELY before continuing:**

**Fix hierarchy (try in order):**
1. **Check AI-generated graphics first**: 太复杂（5+ 元素）→ Regenerate simpler；字太小 → Regenerate with "150pt+" fonts；图太多 → Reduce number of figures。
2. **Reduce sections**: 超过 5-6 个 → Combine or remove（如把 Discussion 并入 Conclusions）。
3. **Cut text content**: 全文超 800 words → 砍到 300-500；单节超 100 words → 砍到 50-80。
4. **Adjust figure sizing**: `width=\linewidth` → `0.85\linewidth`；`width=1.0\columnwidth` → `0.9\columnwidth`。
5. **Increase margins (last resort)**: `\documentclass[25pt, a0paper, portrait, margin=25mm]{tikzposter}`。

**DO NOT proceed to Step 3 if ANY overflow exists.**

**Step 3: Visual Inspection Checklist（👤 须人工）**

Open PDF at 100% zoom and check:

**Layout and Spacing**:
- [ ] Content fills entire page (no large white margins)
- [ ] Consistent spacing between columns
- [ ] Consistent spacing between blocks/sections
- [ ] All elements aligned properly (use ruler tool)
- [ ] No overlapping text or figures
- [ ] White space evenly distributed

**Typography**（口径同 Core Capabilities §8）:
- [ ] Title clearly visible and large (72pt+)；headers 48-72pt；body 24-36pt minimum
- [ ] No text cutoff or running off edges
- [ ] Consistent font usage throughout
- [ ] All special characters render correctly (symbols, Greek letters)

**Visual Elements**:
- [ ] All figures display correctly
- [ ] No pixelated or blurry images
- [ ] Figure captions present and readable
- [ ] Colors render as expected (not washed out or too dark)
- [ ] Logos display clearly
- [ ] QR codes visible and scannable

**Content Completeness / Technical Quality**: 并入下两步执行，不重复设清单——内容完整性（标题作者齐全、Intro/Methods/Results/Conclusions 章节俱在、参考文献、联系方式、致谢、无 Lorem ipsum/TODO 占位残留）随 Step 7 校对核对；技术质量（无关键区编译警告、引用无 [?]、交叉引用可用、页界无裁切）随 Step 8 日志复查核对。

**Step 4: Reduced-Scale Print Test（👤 须人工）**

**Essential Pre-Printing Test**:
```bash
# Create reduced-size test print (25% of final size)
# This simulates viewing full poster from ~8-10 feet

# For A0 poster, print on A4 paper (24.7% scale)
# For 36x48" poster, print on letter paper (~25% scale)
```

**Print Test Checklist**:
- [ ] Title readable from 6 feet away
- [ ] Section headers readable from 4 feet away
- [ ] Body text readable from 2 feet away
- [ ] Figures clear and understandable
- [ ] Colors printed accurately
- [ ] No obvious design flaws

**Step 5: Digital Quality Checks（✅ 可自动化）**

**Font Embedding Verification**:
```bash
# Check that all fonts are embedded (required for printing)
pdffonts poster.pdf

# All fonts should show "yes" in "emb" column
# If any show "no", recompile with:
pdflatex -dEmbedAllFonts=true poster.tex
```

**Image Resolution Check**:
```bash
# Extract image information
pdfimages -list poster.pdf

# Check that all images are at least 300 DPI
# Formula: DPI = pixels / (inches in poster)
# For A0 width (33.1"): 300 DPI = 9930 pixels minimum
```

**File Size Optimization**:
```bash
# For email/web, compress if needed (>50MB)
gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 \
   -dPDFSETTINGS=/printer -dNOPAUSE -dQUIET -dBATCH \
   -sOutputFile=poster_compressed.pdf poster.pdf

# For printing, keep original (no compression)
```

**Step 6: Accessibility Check（👤 须人工，工具辅助）**

**Color Contrast Verification**:
- [ ] Text-background contrast ratio ≥ 4.5:1 (WCAG AA)
- [ ] Important elements contrast ratio ≥ 7:1 (WCAG AAA)
- Test online: https://webaim.org/resources/contrastchecker/

**Color Blindness Simulation**:
- [ ] View PDF through color blindness simulator
- [ ] Information not lost with red-green simulation
- [ ] Use Coblis (color-blindness.com) or similar tool

**Step 7: Content Proofreading（👤 须人工）**

**Systematic Review**:
- [ ] Spell-check all text
- [ ] Verify all author names and affiliations
- [ ] Check all numbers and statistics for accuracy
- [ ] Confirm all citations are correct
- [ ] Review figure labels and captions
- [ ] Check for typos in headers and titles

**Peer Review**:
- [ ] Ask colleague to review poster
- [ ] 30-second test: Can they identify main message?
- [ ] 5-minute review: Do they understand conclusions?
- [ ] Note any confusing elements

**Step 8: Technical Validation（✅ 可自动化）**

**LaTeX Compilation Log Review**:
```bash
# Check for warnings in .log file
grep -i "warning\|error\|overfull\|underfull" poster.log

# Common issues to fix:
# - Overfull hbox: Text extending beyond margins
# - Underfull hbox: Excessive spacing
# - Missing references: Citations not resolved
# - Missing figures: Image files not found
```

**Fix Common Warnings**:
```latex
% Overfull hbox (text too wide)
\usepackage{microtype}  % Better spacing
\sloppy  % Allow slightly looser spacing
\hyphenation{long-word}  % Manual hyphenation

% Missing fonts
\usepackage[T1]{fontenc}  % Better font encoding

% Image not found
% Ensure paths are correct and files exist
\graphicspath{{./figures/}{./images/}}
```

**Step 9: Final Pre-Print Checklist（👤 须人工为主）**

**Before Sending to Printer**:
- [ ] PDF size exactly matches requirements (check with pdfinfo)
- [ ] All fonts embedded (check with pdffonts)
- [ ] Color mode correct (RGB for screen, CMYK for print if required)
- [ ] Bleed area added if required (usually 3-5mm)
- [ ] Crop marks visible if required
- [ ] Test print completed and reviewed
- [ ] File naming clear: [LastName]_[Conference]_Poster.pdf
- [ ] Backup copy saved

**Printing Specifications to Confirm**:
- [ ] Paper type (matte vs. glossy)
- [ ] Printing method (inkjet, large format, fabric)
- [ ] Color profile (provided to printer if required)
- [ ] Delivery deadline and shipping address
- [ ] Tube or flat packaging preference

**Digital Presentation Checklist**:
- [ ] PDF size optimized (<10MB for email)
- [ ] Tested on multiple PDF viewers (Adobe, Preview, etc.)
- [ ] Displays correctly on different screens
- [ ] QR codes tested and functional
- [ ] Alternative formats prepared (PNG for social media)

**Review Script**: 自动化项直接跑 `bash scripts/review_poster.sh poster.pdf`（脚本检查页面尺寸、字体嵌入、文件大小、页数，并提示须人工的视觉检查/缩尺试印/对比度/校对项）；脚本缺失时按上方分栏表逐项手动执行。

**Common PDF Issues and Solutions**:

| Issue | Cause | Solution |
|-------|-------|----------|
| Large white margins | Incorrect margin settings | Reduce margin in documentclass |
| Content cut off | Exceeds page boundaries | Check total width/height calculations |
| Blurry images | Low resolution (<300 DPI) | Replace with higher resolution images |
| Missing fonts | Fonts not embedded | Compile with -dEmbedAllFonts=true |
| Wrong page size | Incorrect paper size setting | Verify documentclass paper size |
| Colors look wrong | RGB vs CMYK mismatch | Convert color space for print |
| File too large (>50MB) | Uncompressed images | Optimize images or compress PDF |
| QR codes don't work | Too small or low resolution | Minimum 2×2cm, high contrast |

### 11. Common Poster Content Patterns

Effective content organization for different research types:

**Experimental Research Poster**:
1. Title and authors
2. Introduction: Problem and hypothesis
3. Methods: Experimental design (with diagram)
4. Results: Key findings (2-4 main figures)
5. Conclusions: Main takeaways (3-5 bullet points)
6. Future work (optional)
7. References and acknowledgments

**Computational/Modeling Poster**:
1. Title and authors
2. Motivation: Problem statement
3. Approach: Algorithm or model (with flowchart)
4. Implementation: Technical details
5. Results: Performance metrics and comparisons
6. Applications: Use cases
7. Code availability (QR code to GitHub)
8. References

**Review/Survey Poster**:
1. Title and authors
2. Scope: Topic overview
3. Methods: Literature search strategy
4. Key findings: Main themes (organized by category)
5. Trends: Visualizations of publication patterns
6. Gaps: Identified research needs
7. Conclusions: Summary and implications
8. References

### 12. Accessibility and Inclusive Design

**Color Blindness Considerations**: 避开红绿组合（最常见色盲类型）、在颜色外加形状/纹理区分、用色盲模拟器复核（工具与流程见 Section 11 Step 6）；对比度按 WCAG AA ≥4.5:1。

**Visual Impairment Accommodations**: 大字号（正文 ≥24pt）、高对比文字/背景、清晰视觉层级、背景避免复杂纹理图案。

**Language and Content**: 语言简明、缩写与术语先定义、考虑国际听众、全球会议可提供多语言 QR 码选项。

### 13. Poster Presentation Best Practices

Guidance beyond LaTeX for effective poster sessions:

**Content Strategy**:
- Tell a story, don't just list facts
- Focus on 1-3 main messages
- Use visual abstract or graphical summary
- Leave room for conversation (don't over-explain)

**Physical Presentation Tips**:
- Bring printed handouts or business cards with QR code
- Prepare 30-second, 2-minute, and 5-minute verbal summaries
- Stand to the side, not blocking the poster
- Engage viewers with open-ended questions

**Digital Backups**:
- Save poster as PDF on mobile device
- Prepare digital version for email sharing
- Create social media-friendly image version
- Have backup printed copy or digital display option

## Workflow for Poster Creation

### Stage 1: Planning and Content Development

1. **Determine poster requirements**: 会议尺寸规格（A0、36×48" 等）、横竖方向、投稿截止与格式要求。
2. **Develop content outline**: 提炼 1-3 个核心信息；选 3-6 张主视觉；逐节拟 bullet 短文；全文 300-800 words。

3. **Choose LaTeX package**: 按「Core Capabilities §1 LaTeX Poster Packages」的对比选型——beamerposter（Beamer 熟手/机构主题）、tikzposter（现代灵活/自定义图形）、baposter（结构化多栏）；详见 `references/latex_poster_packages.md`。

### Stage 2: Generate Visual Elements (AI-Powered)

**CRITICAL: Generate SIMPLE figures with MINIMAL content. Each graphic = ONE message.** 上限/字号/留白/prompt 模板一律按「AI-Powered Visual Element Generation」的 MANDATORY requirements 与 Content limits 表执行（3-4 elements / ≤10 words / ≥50% white space / GIANT fonts），不另立口径。

1. **Create figures directory**:
   ```bash
   mkdir -p figures
   ```

2. **Generate SIMPLE visual elements**: 按上方 Step 2 的工具分类与 prompt 模式逐元素生成——Introduction 3 icons、Methods ≤4 boxes、Results ≤3 bars、Conclusions 3 cards（prompt 必含 "POSTER FORMAT for A0"、元素数、GIANT 字号、留白比例、观看距离）。

3. **Review generated figures**: 按上方 Step 2b 逐图审查（25% zoom 可读、元素数、留白、字号）。任一图不过 → 按修复口径重新生成后再进入 Stage 3，不要带病组装。

### Stage 3: Design and Layout

1. **Select or create template**: 从 `assets/` 模板起步，按机构品牌调色，配置页面尺寸与方向。
2. **Design layout structure**: 规划 2-4 栏、内容流向（一般左→右、上→下）；空间配比 title 10-15% / content 70-80% / footer 5-10%。
3. **Set typography**: 按字号层级配置（Title 72pt+ / headers 48-72pt / body ≥24pt，口径同 Core Capabilities §3 与 Section 11 Step 3），保证 4-6 英尺距离可读。

### Stage 4: Content Integration

1. **Create poster header**: 标题（10-15 词）、作者与机构、高清机构 logo、会议 logo（如需）。
2. **Integrate AI-generated figures**: Stage 2 产出逐一对位入栏；`\includegraphics` 控宽（<1.0\linewidth）；图主导版面（先图后文）、栏内居中。
3. **Add minimal supporting text**: 全文 300-800 words、bullet 优先、主动语态；文字补充图，不重复图。
4. **Add supplementary elements**: QR 码（补充材料）、精选参考文献（5-10 条）、联系方式与致谢。

### Stage 5: Refinement and Testing

1. **Review and iterate**: 查错别字与错误、确认图片分辨率、格式与配色一致。
2. **Test readability**: 按 Section 11 Step 4 做缩尺试印（25%），按 Step 7 做同事评审与 30 秒测试；不同显示器核对颜色，验证二维码可用。
3. **Optimize for printing**: 按 Section 11 Step 9 打印前清单执行（字体嵌入、图片分辨率、PDF 尺寸、bleed）。

### Stage 6: Compilation and Delivery

1. **Compile final PDF**: `pdflatex poster.tex`（编译命令与参考文献连跑口径见 Core Capabilities §10 Compilation Commands）。

2. **Verify output quality**: 按 Section 11 执行——100% zoom 查四边溢出、检查元素位置与 figure 质量、核对颜色、多查看器打开确认。

3. **Prepare for printing**: 按 Section 11 Step 9 打印前清单执行（PDF/X-1a、备份）；普通纸试印先行，提前 2-3 天下单专业打印。
4. **Create supplementary materials**: PNG/JPG 社媒版、8.5×11" 讲义版、邮件分享数字版（对应 Step 9 Digital Presentation Checklist）。

## Integration with Other Skills

This skill works effectively with:
- **Scientific Schematics**: CRITICAL - Use for generating all poster diagrams and flowcharts
- **Generate Image / Nano Banana Pro**: For stylized graphics, conceptual illustrations, and summary visuals
- **Scientific Writing / Literature Review / Data Analysis**: 分别用于从论文发展海报内容、研究语境梳理、结果图表制作

**Recommended workflow**: Always use scientific-schematics and generate-image skills BEFORE creating the LaTeX poster to generate all visual elements.

**上游 API 依赖替代（本仓环境）**：scientific-schematics / Generate Image / Nano Banana Pro 是上游宿主的技能与工具名；在本仓运行时没有这些现成入口，以当前 Agent 的联网检索 / 网页抓取 / 图像生成能力替代，或直接用本技能自带的 `scripts/generate_schematic.py` 本地生成示意图（适配说明见 `references/UPSTREAM.md`）。不要因为找不到名为 "Nano Banana Pro" 的工具而中断流程。

## Common Pitfalls to Avoid

**AI-Generated Graphics Mistakes (MOST COMMON):** 元素超限 / 字太小 / 留白不足 / 复杂流程不拆分——一律按「AI-Powered Visual Element Generation」的 MANDATORY requirements、Step 0 失败模式与 Step 2b FAIL 口径拦截修复，此处不重复。

**Fixing Overflow in AI Graphics:**
If your AI-generated graphics are overflowing or have small text:
1. Add "SIMPLER" or "ONLY 3 elements" to prompt
2. Increase font sizes: "150pt+" instead of "80pt+"
3. Add "60% white space" instead of "50%"
4. Remove sub-details: "NO sub-steps", "NO axis labels", "NO legend"
5. Regenerate with fewer elements

**Design Mistakes**:
- ❌ Too much text (over 1000 words)
- ❌ Font sizes too small (under 24pt body text)
- ❌ Low-contrast color combinations
- ❌ Cluttered layout with no white space
- ❌ Inconsistent styling across sections
- ❌ Poor quality or pixelated images

**Content Mistakes**:
- ❌ No clear narrative or message
- ❌ Too many research questions or objectives
- ❌ Overuse of jargon without definitions
- ❌ Results without context or interpretation
- ❌ Missing author contact information

**Technical Mistakes**:
- ❌ Wrong poster dimensions for conference requirements
- ❌ RGB colors sent to CMYK printer (color shift)
- ❌ Fonts not embedded in PDF
- ❌ File size too large for submission portal
- ❌ QR codes too small or not tested

**Best Practices**: AI 图形按权威规范生成（3-4 elements / ≤10 words / GIANT fonts / ≥50% white space）；尺寸严格对齐会议要求、缩尺试印、高对比配色、正文极简可扫读、联系信息与二维码齐备、付印前逐字校对（错误在海报上会被放大）。

## Post-Acceptance Promotion Content（会后宣传内容）

> 迁移自 2026-11-16 退役并入裁决的原「会后宣传内容」技能（原技能目录已删除，溯源见 dev-docs/DELETION_LOG.md 2026-11-16 退役批）；以下内容逐字保留。

Guidance for creating promotional content after paper acceptance:

**Twitter/X Thread**
- Thread structure: Hook -> Problem -> Method -> Key Result -> Link
- First tweet: Attention-grabbing summary with emoji
- Include 1-2 key figures
- End with paper link and relevant hashtags
- Tag co-authors and relevant accounts

**LinkedIn Post**
- Professional tone, 3-5 paragraphs
- Highlight practical implications
- Include key figure or diagram
- Add relevant hashtags

**Blog Post**
- 800-1500 words
- Non-technical summary for broader audience
- Include figures with explanations
- Link to paper, code, and demo

**When to use**: Research promotion - Create social media and blog content after paper acceptance.

**Promotion Workflow**
```
Paper accepted -> Write Twitter thread -> Create LinkedIn post -> Draft blog post -> Schedule posts around conference dates
```

**Promotion Best Practices**
- Post within 1-2 weeks of acceptance notification
- Coordinate timing with co-authors
- Engage with comments and questions
- Share across multiple platforms
- Include accessible descriptions for figures

## Package Installation

TeX Live（Linux/Mac）：`tlmgr install beamerposter tikzposter baposter`，推荐附加包 `tlmgr install qrcode graphics xcolor tcolorbox subcaption`；MiKTeX（Windows）通常首次使用自动安装。**baposter 注意**：其官方站点在 上游 2026-09-30 复核时已不可达，类文件以 v2.0（2011/11/26）存档源为 pinned 依据（见 `references/latex_poster_packages.md` 的存档镜像链接）；不要把"老的稳定包版本"当作"当前支持 tagged-PDF"的证明。

## Scripts and Automation

`scripts/` 下：`review_poster.sh`（海报 PDF 质检）、`generate_schematic.py`（科研示意图生成）、`generate_schematic_ai.py`（AI 生图入口）。

**generate_schematic 助手契约（上游 v2.72.0 更新）**：`generate_schematic.py` 委托 `generate_schematic_ai.py`，需 Python 3.10+、`requests`、网络与 `OPENROUTER_API_KEY`（从环境变量或项目 `.env` 读取，优先于命令行传入）。生成走 OpenRouter `POST /api/v1/images`（模型 `google/gemini-3.1-flash-image`，即 Nano Banana 2），校验 PNG 签名、仅接受 `.png` 输出路径；评审走 `POST /api/v1/chat/completions`（模型 `google/gemini-3.7-flash`）。`--doc-type poster` 启用 7/10 评审启发式——它不是外部验证过的质量标准；`--iterations` 上限 1-2，精修失败保留前一张已存草稿，失败请求不自动重试。生成与评审都消耗 API 额度：AI 分数或已存图都不等于科学正确或最终印刷合格，仍须走 Section 11 人工质检。

## References

- `references/latex_poster_packages.md`：beamerposter / tikzposter / baposter 详细对比与示例
- `references/poster_layout_design.md`：布局原则、网格系统、视觉流
- `references/poster_design_principles.md`：排版、色彩理论、视觉层级与无障碍
- `references/poster_content_guide.md`：内容组织、写作风格、分节指引

## Templates

`assets/` 下备有各包模板（beamerposter classic/modern/colorful、tikzposter default/rays/wave/envelope、baposter portrait/landscape/minimal）、多学科示例海报与机构配色定义；载入后按具体研究与会议要求定制。

