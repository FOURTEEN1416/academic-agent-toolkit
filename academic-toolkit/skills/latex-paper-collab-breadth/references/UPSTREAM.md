# UPSTREAM 溯源台账 — latex-paper-collab-breadth

- Upstream: https://github.com/yunshenwuchuxun/latex-paper-skills（技能目录 `.codex/skills/collaborating-with-gemini`，共享资产 `_shared/` `_orchestration/`）
- Pinned commit: 7965fbc06cd2c34ef7a0a3a566c089f4757c3de5（2026-11-16 实测上游 main HEAD；原 d0f10610，fork FOURTEEN1416/latex-paper-skills 2026-09-09 拉取）
- License: MIT（Copyright (c) 2026 renocrypt；2026-11-16 实测上游 LICENSE）；内嵌 IEEEtran 模板为 LPPL 1.3（见上游 THIRD_PARTY_NOTICES.md）

## 适配说明

- 2026-09-09 专项治理批次 2：拷入上游技能目录与 _shared 共享资产补齐 references/assets/scripts（SKILL.md 沿用本仓库既有版本未动）。
- 上游部分脚本为 .codex 平台适配（引用 .codex/skills 路径），本仓库执行时按本技能目录相对路径解析。


## 同步记录（2026-11-16，d0f10610→7965fbc，UP-6）

- vendor/forks/latex-paper-skills 已镜像同步至实测 HEAD：上游更新 route_and_invoke.py（shlex 安全引用与 plan 脚本路径修正）、collaborating-with-claude/gemini SKILL.md、README 双语，新增顶层 skills/、distribution/、bin/、scripts/、tests/、package.json、THIRD_PARTY_NOTICES.md。
- 2026-11-16 收尾批复核：上游 collaborating-with-gemini/SKILL.md 本区间仅修共享规则相对路径（../../_shared→../_shared，上游目录树内部修正）；本仓 _shared 基线未收编（见本技能 ASSET-GAP.md），引用由 ACAT-GOVERNANCE 豁免注记管辖，正文无需改动。
