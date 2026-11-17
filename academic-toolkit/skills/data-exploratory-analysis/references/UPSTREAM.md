# UPSTREAM 溯源台账 — data-exploratory-analysis

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills（技能目录 `skills/exploratory-data-analysis`）
- Pinned commit: 2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5（2026-11-16 实测上游 main HEAD，v2.72.0 线；原 36d8f13a，2026-08-24/09-09 两代拉取统一）
- License: MIT

## 适配说明

- 2026-09-09 专项治理批次 1a：从 fork https://github.com/FOURTEEN1416/scientific-agent-skills 拉取该技能 references/ assets/ scripts/ 补齐本仓库技能目录（SKILL.md 沿用本仓库既有版本未动）。
- 上游正文中 `research-lookup` 技能与 API 依赖（parallel-cli 等）在本仓库无对应环境，执行时以当前 Agent 的联网检索/网页抓取能力替代，API 调用类脚本不可直接运行。
- 残留断链（上游亦无该资产）：以本技能 ASSET-GAP.md 清单与"根目录平铺"现状为准（登记册无本技能条目；2026-09-28 核对）。


## 同步评估（2026-11-16，36d8f13a→2d2065f v2.72.0，UP-2）

- vendor/forks/scientific-agent-skills 已镜像同步至实测 HEAD。
- ⚠️ 上游 v2.72.0 已移除/重组本技能来源目录 `skills/data-exploratory-analysis`（新址：exploratory-data-analysis）；本仓收编副本为存续快照，后续升级转本地维护为主，如需跟进新上游结构须按收编规程重新评估。

## 重收编落地（2026-11-16，2d2065f 增量改写融入，UP-3）

- scripts/ 与 references/、assets/ 共 13 个共享文件按上游增量补丁融入（路径映射 data-exploratory-analysis→exploratory-data-analysis，忽略行尾差异应用干净）：含 image_inspector 渲染健壮性、_tabular/_structured/_capabilities 解析修订、六份格式参考件与报告模板的说明修订。
- SKILL.md 保留本仓另一代"200+ 格式 / eda_analyzer.py"文本体系不整篇照搬；择要融入上游增量：数据解读补"前缀扫描顺序陷阱（行数上限只扫文件开头，先查日期/批次/站点/结局/切分排序再外推）+ 游程图提示（NIST eda33p）"与"TIFF 仅报告通用 page/series 分组、不重建 OME XYZCT 轴、不打开伴生文件"两条边界。
- 上游新增 "Citing Scientific Agent Skills" 段属上游自我引用话术，未收编。
