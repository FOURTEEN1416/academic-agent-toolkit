# UPSTREAM 溯源台账 — latex-paper-results-backfill

- Upstream: https://github.com/yunshenwuchuxun/latex-paper-skills（技能目录 `.codex/skills/results-backfill`，共享资产 `_shared/` `_orchestration/`）
- Pinned commit: 7965fbc06cd2c34ef7a0a3a566c089f4757c3de5（2026-11-16 实测上游 main HEAD；原 d0f10610，fork FOURTEEN1416/latex-paper-skills 2026-09-09 拉取）
- License: 见上游仓库 LICENSE

## 适配说明

- 2026-09-09 专项治理批次 2：拷入上游技能目录与 _shared 共享资产补齐 references/assets/scripts（SKILL.md 沿用本仓库既有版本未动）。
- 上游部分脚本为 .codex 平台适配（引用 .codex/skills 路径），本仓库执行时按本技能目录相对路径解析。


## 同步记录（2026-11-16，d0f10610→7965fbc，UP-6）

- vendor/forks/latex-paper-skills 已镜像同步至实测 HEAD：上游更新 route_and_invoke.py（shlex 安全引用与 plan 脚本路径修正）、collaborating-with-claude/gemini SKILL.md、README 双语，新增顶层 skills/、distribution/、bin/、scripts/、tests/、package.json、THIRD_PARTY_NOTICES.md。
- 本仓 8 件 latex-paper-* 技能 references 为适应性改写蒸馏件，来源内容未受本次上游更新影响，无需重收编；上游新增顶层结构属其组织调整，vendor 原样保留备查。
