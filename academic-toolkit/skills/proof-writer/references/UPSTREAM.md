# UPSTREAM

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（vendor/forks/Auto-claude-code-research-in-sleep，MIT）
- Pinned commit: 9f30e83（2026-11-16 实测上游 HEAD 9f30e834d24a337dbdd06fb20a1150d4376dfa59；原 94d8093，2026-08-26 拉取，vendor-asset-index #2）
- License: MIT（fork 根 LICENSE）
- 收编件: 本技能（V1.1 同名整采批；2026-09-23 v2.0 收尾补登记）。W3 语义化改名前后均在库；正文随本仓演进，与上游已分叉。
- Local adaptation: 原文入库后随本仓演进；本地适配与命名规范以本仓为准。


## 同步评估（2026-11-16，94d8093→9f30e83，UP-1）

- vendor/forks/Auto-claude-code-research-in-sleep 已镜像同步至实测 HEAD（768 文件更新、0 删除）。
- 上游区间 skills/ 变更 177 文件（+11563/-1014），主要为止(install/SSH 同步修复与文档扩充)。本件对应上游目录 skills/proof-writer：上游区间内有变更。
- 改写融入（2026-11-16，PKG-01 研究实验环批）：上游新增 Optional Lean proof route 依赖未收编技能 lean-formalize（上游新增件收编待裁决），为免悬空引用本批不融入；其余无增量。
- 补记（2026-11-17 裁决第二批）：lean-formalize 已收编入库，Optional Lean proof route 已接入本技能正文（`SKILL.md` Step 2 后「Optional Lean proof route」节；见 dev-docs/audits/2026-11-17-裁决第二批/absorb-lean-formalize.md），原「本批不融入」悬空状态撤销。
