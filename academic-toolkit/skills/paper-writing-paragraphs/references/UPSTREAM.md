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
