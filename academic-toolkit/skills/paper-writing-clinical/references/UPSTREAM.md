# UPSTREAM 溯源台账 — paper-writing-clinical

- Upstream: https://github.com/K-Dense-AI/claude-scientific-writer
- Pinned commit: 0c7260603be3de4dd5161565ab92e85b31c45eb5（v2.9.1 线 main，2026-09-09 拉取）
- License: MIT（上游 LICENSE 随附于上游仓库根；fork：https://github.com/FOURTEEN1416/claude-scientific-writer，先 fork 后集成惯例）

## 拉取内容与目录适配

| 项 | 值 |
|----|----|
| 拉取文件 | 上游 `skills/` 下 15 个模块目录（scientific-writing / peer-review / citation-management / literature-review / scientific-critical-thinking / hypothesis-generation / venue-templates / scholar-evaluation / research-grants / clinical-reports / clinical-decision-support / treatment-plans / latex-posters / scientific-slides / market-research-reports），共 343 文件 / 约 4.0MB，纯文本（md/csv/json/txt/py/sh/tex） |
| 目录适配 | 上游 `skills/<module>/` 拷入本技能 `modules/<module>/`；**正文保持 pinned 原样**（可 diff 对照），适配层为：modules/ADAPTATION.md（兄弟模块映射表+API 依赖门）、15 个模块 SKILL.md 头部 `<!--ACAT-ADAPTED-->` 横幅、主 SKILL.md 头部适配块（2026-09-09 适应性改造） |
| SKILL.md 来源 | 本技能 SKILL.md **不是**上游文件：它是某 Claude.ai 用户定制打包版的孤本路由器（含该用户土耳其语/英语双语约定等个人偏好），其引用的合并版 `references/<module>.md` 结构在上游任何历史提交中都不存在（已核对上游 243 个提交全历史），资产孤本不可得 |
| 引用口径 | SKILL.md 正文 `references/ assets/ scripts/` 引用一律按 `modules/` 前缀解析（见 SKILL.md 头部适配说明块）；本 references/ 目录仅存放本台账 |
| API 依赖 | 上游 scripts 含 ANTHROPIC_API_KEY / Parallel CLI / OPENROUTER_API_KEY 依赖，本仓库无 API 环境；按 SKILL.md Global Rule 1 占位符替代口径处理，不可直接运行 |
| 未拉取部分 | 上游其余 11 个模块（docx/pdf/pptx/xlsx/infographics/markitdown/research-lookup/parallel-web/generate-image/scientific-schematics/pptx-posters）非本技能路由范围，未拉取 |

## 审计记录

- 2026-09-09：全库审计发现本技能自 initial public release（7529779）起仅含 SKILL.md 孤本，内部引用全部断链；定位上游并按上述口径补齐 `modules/` 资产，加 SKILL.md 头部适配说明块与本台账。
