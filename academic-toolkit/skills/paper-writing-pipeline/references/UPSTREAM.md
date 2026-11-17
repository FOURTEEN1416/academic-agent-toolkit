# UPSTREAM 溯源台账 — paper-writing-pipeline

- Upstream: https://github.com/Imbad0202/academic-research-skills（技能目录 `academic-paper`）
- Pinned commit: 23bd688bbc121da6ae98ec3c4d4a7675cefc4c83（Imbad0202 上游 HEAD，2026-11-16 同步；原 5debcd2efb686dce0205ba9094b6413dae5f89c0，2026-09-09 拉取）
- License: CC-BY-NC-4.0（上游根 LICENSE，Copyright (c) 2026 Cheng-I Wu；DEF-13 复核见 dev-docs/audits/2026-11-16-裁决落地/LICENSE_FACTS.md）

## 适配说明

- 2026-09-09 专项治理批次 1c：拷入上游 references/assets/scripts 补齐本仓库技能目录（SKILL.md 沿用本仓库既有版本未动）。
- 共享脚本（check_pipeline_integrity.py 等）来自上游全局 scripts/，标准库零内部依赖，可直接运行（check_sprint_contract.py 需 jsonschema）。
- 2026-11-16 重收编批（待 fork 同步 + 许可复核）：12 件参考件按上游 5debcd2..23bd688 区间增量更新——abstract_writing_guide（新增长度/关键词单一来源表，本仓 150–300 词旧数随上游和解入表）、mode_selection_guide 按本仓改名适配三方合并，其余 10 件直采新版；本仓 deep-research→comp-contest-research 改名与宿主中性化适配全部保留。原记载的 franklee16 URL 系历史误记——pinned 5debcd2 仅在 Imbad0202 仓命中，franklee16 为同名异构项目且无 LICENSE，已按 LICENSE_FACTS.md 更正。
