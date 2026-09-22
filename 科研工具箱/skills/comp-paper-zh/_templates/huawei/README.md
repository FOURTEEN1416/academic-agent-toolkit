# 华为杯（研赛）LaTeX 模板

`gmcmthesis.cls` + 骨架 `main.tex` + 封面 `logo.pdf` / `title.pdf`（2026-09-22 自本地
modex-3-skills 模板目录入库，修复 SKILL.md 华为杯分支 `cp _templates/huawei/*` 空操作断链）。
另有参考文献样式 `gmcm.bst` 与官方 Word/PDF 附件模板 `official_docx/`（见下）。

## cls 版本：v2.3+本地补丁 → v2.4 三方合并（2026-09-22）

- 基线 = 本目录原 v2.3（含本地补丁：`\clearpage` 摘要后换页防空白页、题目行 parbox
  防掉字号 (v1.5.0)、`[normalem]{ulem}`、中文引号锁字体块（原 `mhquote` 族，本轮更名
  `zhquote` 去宿主标记）、图表题注宋体加粗）。
- 上游 = GMCMthesis v2.4（latexstudio/GMCMthesis + andy123t 合并版，2024-09-17 更新）。
- 本轮吸收：①封面更新（题目行 `-2` 号隶书标签样式 + `\vskip0.2cm`）；②首页页码修复
  （封面 `thispagestyle empty`，移除 `\setcounter{page}{0}`/`\thepage{0}` hack，正文页
  仍由 `\makenametitle` 置 1）；③`\LoadClass` 选项 `cs4size` → `zihao=-4`；④全局
  `\lstset`（并激活 `dkgreen`/`mauve` 颜色定义，上游为注释态会引用未定义颜色）；
  ⑤`listings,color` → `listings,xcolor`。
- 未吸收、留待裁定（上游 2024 改动 vs 本地既有补丁冲突）：摘要标题 `zihao 3→-2`、
  关键词 `-4 黑体→-3 隶书`、题注去 `bf`、跨平台字体自适应块（含 `C:/bootfont.bin`
  探测路径，触宿主红线）、定理环境块恢复、末尾 `\pagestyle{plain}` 注释化。

## 2024 年（第 21 届）格式变化两条情报（源：上游 README.md / example.tex）

1. **论文第一页为标识替换** —— 封面竞赛标识图按当届官方图替换；本目录 `logo.pdf` /
   `title.pdf` 与上游 v2.4 版逐字节一致（即 2024 官方样式），换届时须替换。
2. **调整摘要、标题、关键词和浮动体标题等字体** —— 官方 Word 模板见
   `official_docx/`；LaTeX 侧对应上游字体调整项（见上"待裁定"，采纳前以本地补丁渲染为准）。

## 官方附件 3 模板（docx 分支参考）

`official_docx/huabei-21st-official-paper-template.{doc,pdf}`（~1.2MB，
自上游仓库附件 3 重命名为 ASCII 安全名落位；原文件名含全角冒号）。

## 字体依赖（本地恢复源已落位 `_fonts-local/`）

cls 用 `\setCJKmainfont` 系列声明 **SimSun / SimHei / KaiTi / LiSu**：

- Windows：SimSun/SimHei/KaiTi 随系统自带；LiSu（隶书）随中文语言包/Office 提供；
- 非 Windows 或系统缺字体：从 **`../_fonts-local/`**（本 `_templates` 目录下的集中字体库，
  2026-09-22 自 modex-3-skills 去重落位，16 个唯一字体/103MB，含 `simsun.ttf`、
  `SimHei.ttf`、`KaiTi.ttf`、`LiSu.ttf`、`simkai.ttf`、`simsun.ttc` 等）取用，
  与 `paper/` 同放（或装系统字体）。原"回 modex-3-skills 兜底"指针作废——modex-3-skills
  为本地对照源、不入 git，`_fonts-local/` 才是工具箱内长期落位（注意其 git 忽略状态，
  见仓库根 `.gitignore` 讨论）。

## 使用

comp-paper-zh Step 1 华为杯分支自动 `cp _templates/huawei/* paper/`；
落地断言要求 paper/ 出现 `.cls` 才放行。骨架占位符（标题/队号/成员）按 SKILL.md
华为杯标题硬约束填写：标题必须照抄赛题官方原标题，禁止 `\\` 强制换行。
参考文献如需 bibtex：`gmcm.bst`（v2.4 上游件，随本目录分发）。
