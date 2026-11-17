# UPSTREAM

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（vendor/forks/Auto-claude-code-research-in-sleep，MIT）
- Pinned commit: 9f30e83（2026-11-16 实测上游 HEAD 9f30e834d24a337dbdd06fb20a1150d4376dfa59；原 94d8093，2026-08-26 拉取，vendor-asset-index #2）
- License: MIT（fork 根 LICENSE）
- 收编件: 本技能（V1.1 同名整采批；2026-09-23 v2.0 收尾补登记）。W3 语义化改名前后均在库；正文随本仓演进，与上游已分叉。
- Local adaptation: 原文入库后随本仓演进；本地适配与命名规范以本仓为准。
- 改写融入（2026-09-23，R1）：SKILL.md 环境目录 fallback 探测行移除。


## 同步评估（2026-11-16，94d8093→9f30e83，UP-1）

- vendor/forks/Auto-claude-code-research-in-sleep 已镜像同步至实测 HEAD（768 文件更新、0 删除）。
- 上游区间 skills/ 变更 177 文件（+11563/-1014），主要为止(install/SSH 同步修复与文档扩充)。本件对应上游目录 skills/research-lit：上游区间内有变更。
- 改写融入（2026-11-16，PKG-01 研究实验环批）：已融入证据纪律——只基于已读证据（摘要/原文片段/本地 PDF/笔记）提取，仅有标题无证据者记 UNPROCESSABLE_NO_LOCAL_EVIDENCE 并保持未覆盖，不凭标题推断、不静默剔除，覆盖率如实记录。有界扇出（aris-fanout-leaf）绑定上游叶子 Agent 基建，不融入。
