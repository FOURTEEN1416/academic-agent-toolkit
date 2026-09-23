# ADAPTATION — claude-scientific-writer/modules 适应性改造说明

> 本目录 15 个模块来自上游 K-Dense-AI/claude-scientific-writer@0c72606（pinned，见 [../references/UPSTREAM.md](../references/UPSTREAM.md)）。
> **正文保持上游原样**（保证与 pinned 提交可 diff 对照）；适应性改造集中在三处：本说明、各模块 SKILL.md 头部 `<!--ACAT-ADAPTED: ...-->` 横幅、主 SKILL.md 头部适配块。审计标记体系：`ACAT-ADAPTED`=适应性改造声明，`ACAT-GOVERNANCE`=上游资产未集成断链声明（全库统一口径）。

## 1. 未随包拉取的兄弟模块引用 — 替代口径映射表

上游仓库共 26 个模块技能，本技能仅拉取主 SKILL.md 路由的 15 个。模块正文中引用其余兄弟模块时，按此表替代（不报错、不要求安装上游 CLI）：

| 正文引用 | 本仓库替代口径 |
|---|---|
| `pdf` skill / `pptx` skill / `docx` skill / `xlsx` skill | 宿主 document-skills（docx/pdf/pptx/xlsx），或工具箱 docx-export、paper-compile 等管线能力 |
| `research-lookup` skill / `parallel-web` skill / `parallel-cli` 命令 | 宿主 web_search / web_fetch 工具（无需 API key）；`parallel-cli search "..."` 一律视为"执行一次 web 检索"的占位符 |
| `generate-image` skill | 无直接等价；插图需求走多模态 LLM 视觉门（见 §2）或描述图形交由用户外部生成 |
| `scientific-schematics` skill | 本仓库技能 `scientific-schematics`（skills/scientific-schematics/） |
| `infographics` skill | 本仓库技能 `infographics`（skills/infographics/） |
| `markitdown` 命令 | 宿主原生文件读取（PDF/DOCX/PPTX/XLSX） |
| `pptx-posters` skill | 本仓库技能 `paper-poster` 或 `doc-poster-latex` |

## 2. API 依赖门（显性化，禁止静默失败）

模块正文与 scripts/ 中出现以下依赖时，**本仓库环境不可直接运行**，执行 agent 必须先走 Step 0 检测并向用户显性声明降级路径：

| 依赖标记 | 出现规模（2026-09-09 扫描） | 降级口径 |
|---|---|---|
| `parallel-cli` / `PARALLEL_API_KEY` | 45 处引用 | → web_search / web_fetch |
| `OPENROUTER_API_KEY` | 16 处引用（图像生成类脚本） | → 多模态 LLM 视觉门：检测当前宿主是否具备视觉生成能力的模型；无则声明缺口，产出改为文字描述/占位图 |
| `ANTHROPIC_API_KEY` | scripts 内直接调用 | → 由当前会话 agent 本体承担该职责，不经外部 API |
| `research-lookup` skill | 1 处引用 | → web_search / web_fetch |

纯本地脚本（`_common.py`、`calculate_scores.py`、校验类 check_*.py 等，标准库零 API 依赖）可直接运行。

## 3. 宿主与主技能关系

- 主 SKILL.md（本技能根）是**路由器**：15 模块的路由表、全局写作规范、工作流编排都在主文件；
- `modules/<m>/SKILL.md` 是**模块入口**（上游原文）：按主文件路由表进入对应模块后再读；
- 模块内 `references/`（主题文档）、`assets/`（模板）、`scripts/`（本地工具）按需加载，**不要一次性全读**。

## 4. 改造清单（2026-09-09）

1. 主 SKILL.md 头部适配块（modules/ 前缀解析口径 + API 占位替代）；
2. 15 个模块 SKILL.md 头部注入 `<!--ACAT-ADAPTED-->` 横幅（正文零改动）；
3. 本说明（映射表 + API 门 + 宿主关系）；
4. references/UPSTREAM.md 溯源台账（provenance 注册表第 29 项）。
