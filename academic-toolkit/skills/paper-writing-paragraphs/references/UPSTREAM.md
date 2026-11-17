# UPSTREAM 溯源台账 — paper-writing-paragraphs

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills（技能目录 `skills/scientific-writing`）
- Pinned commit: 2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5（2026-11-16 实测上游 main HEAD，v2.72.0 线；原 36d8f13a，2026-08-24/09-09 两代拉取统一）
- License: MIT

## 适配说明

- 2026-09-09 专项治理批次 1a：从 fork https://github.com/FOURTEEN1416/scientific-agent-skills 拉取该技能 references/ assets/ scripts/ 补齐本仓库技能目录（SKILL.md 沿用本仓库既有版本未动）。
- 上游正文中 `research-lookup` 技能与 API 依赖（parallel-cli 等）在本仓库无对应环境，执行时以当前会话可用的网页检索/抓取能力替代，API 调用类脚本不可直接运行。
- 残留断链（上游亦无该资产）：见 tools/asset_gap_register.json 中本技能条目（诚实存量）。


## 同步评估（2026-11-16，36d8f13a→2d2065f v2.72.0，UP-2）

- vendor/forks/scientific-agent-skills 已镜像同步至实测 HEAD。
- ⚠️ 上游 v2.72.0 已移除/重组本技能来源目录 `skills/paper-writing-paragraphs`（新址：无直接对应（writing 技能族重组））；本仓收编副本为存续快照，后续升级转本地维护为主，如需跟进新上游结构须按收编规程重新评估。

## 重收编落地（2026-11-16，2d2065f 增量改写融入，UP-3）

- assets/reporting_guidelines.json、references/ 六份、scripts/ 四份按上游增量补丁融入（11 个非正文文件与上游旧版全同，应用干净、无拒绝）；`_common.py`/`audit_claims.py`/`validate_authorship.py`/`validate_manifest.py` `python -I -m py_compile` 全部通过。
- SKILL.md 保留本仓文本体系；择要融入上游增量：报告规范一节补"主要路线 2026-10-01 复核（CONSORT 2025、SPIRIT 2025）"与二分类结局口径（各组 events/分母 + 绝对与相对效应并列及不确定性；risk difference/RR/OR 不得互改、无基线风险不推算绝对效应，附 CONSORT 2025 explanation 链接）；Resources 补 claim-evidence 台账哈希纪律（CSV 存哈希不存原文、一条主张一行、改写后先重验再更新哈希）。上游另有的 ICMJE 署名闸门/保证人记录与 COPE 2026-07-21 Code of Conduct 取代 Core Practices 的提示，属 references/authorship_ai_confidentiality.md 与 journal_policies.md 补丁内容随文件收编，正文未重复展开。
- 上游新增 "Citing Scientific Agent Skills" 段属上游自我引用话术，未收编。
