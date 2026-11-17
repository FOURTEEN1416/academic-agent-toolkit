# UPSTREAM 溯源台账 — lit-review-systematic

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills（技能目录 `skills/literature-review`）
- Pinned commit: 2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5（2026-11-16 实测上游 main HEAD，v2.72.0 线；原 36d8f13a，2026-08-24/09-09 两代拉取统一）
- License: MIT

## 适配说明

- 2026-09-09 专项治理批次 1a：从 fork https://github.com/FOURTEEN1416/scientific-agent-skills 拉取该技能 references/ assets/ scripts/ 补齐本仓库技能目录（SKILL.md 沿用本仓库既有版本未动）。
- 上游正文中 `research-lookup` 技能与 API 依赖（parallel-cli 等）在本仓库无对应环境，执行时以执行侧 web_search/web_fetch 工具替代，API 调用类脚本不可直接运行。
- 残留断链（上游亦无该资产）：以本技能 ASSET-GAP.md 清单与"根目录平铺"现状为准（登记册无本技能条目；2026-09-28 核对）。


## 同步评估（2026-11-16，36d8f13a→2d2065f v2.72.0，UP-2）

- vendor/forks/scientific-agent-skills 已镜像同步至实测 HEAD。
- ⚠️ 上游 v2.72.0 已移除/重组本技能来源目录 `skills/lit-review-systematic`（新址：literature-review / peer-review）；本仓收编副本为存续快照，后续升级转本地维护为主，如需跟进新上游结构须按收编规程重新评估。

## 重收编落地（2026-11-16，2d2065f 增量改写融入，UP-3）

- assets/review_template.md、references/ 四份、scripts/ 五份按上游增量补丁融入（11 个非正文文件与上游旧版全同，应用干净、无拒绝）；`generate_pdf.py`/`generate_schematic_ai.py`/`search_databases.py`/`verify_citations.py` 等五个脚本 `python -I -m py_compile` 全部通过。`generate_schematic_ai.py` 契约随补丁对齐（OpenRouter images/chat 端点、gemini-3.1-flash-image / gemini-3.7-flash、1-2 轮迭代、失败保留前稿）。
- SKILL.md 保留本仓七阶段文本体系；择要融入上游增量：示意图一节补 PRISMA 2020 流程模板与 records/reports/studies 三分计数口径、助手新契约摘要与"success≠科学准确、禁在图像 prompt 编造研究计数"；Phase 3 新增第 7/8 条（records-reports-studies 关联与 PRISMA 计数核对、双人资格判定与分歧留痕；引用量只作探索排序不作资格判据）；Phase 6 新增第 4 条（verify_citations 只验 DOI 与元数据，论断支持须对照原文，DOI 存在≠证据成立）。
- 上游新增 "Citing Scientific Agent Skills" 段属上游自我引用话术，未收编。
