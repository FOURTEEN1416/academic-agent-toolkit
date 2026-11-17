# UPSTREAM

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（vendor/forks/Auto-claude-code-research-in-sleep，MIT）
- Pinned commit: 9f30e83（2026-11-16 实测上游 HEAD 9f30e834d24a337dbdd06fb20a1150d4376dfa59；原 94d8093，2026-08-26 拉取，vendor-asset-index #2）
- License: MIT（fork 根 LICENSE）
- 收编件: 本技能（V1.1 同名整采批；2026-09-23 v2.0 收尾补登记）。共享参考目录（非技能，随同名整采入库）
- Local adaptation: 原文入库后随本仓演进；本地适配与命名规范以本仓为准。
- 改写融入（2026-09-23，R1）：reviewer-independence.md 示例评审通道去 Codex MCP 绑定（协议原则不变）。


## 同步评估（2026-11-16，94d8093→9f30e83，UP-1）

- vendor/forks/Auto-claude-code-research-in-sleep 已镜像同步至实测 HEAD（768 文件更新、0 删除）。
- 上游区间 skills/ 变更 177 文件（+11563/-1014），主要为止(install/SSH 同步修复与文档扩充)。本件对应上游目录 skills/shared-references：上游区间内有变更。
- 改写融入（2026-11-16，PKG-01 研究实验环批）：assurance-contract.md 融入 reviewer_model/reviewer_reasoning 实证语义收紧（实际回报模型为准、请求别名非证据、缺失 effort 不放宽身份核验）与 acceptance_status 判据细化（仅同族 provisional、跨族 accepted 需在范围内完成、失败/身份不明/不完整评审不得伪造成 PASS），示例模型名同步更替；writing-principles.md 新增 Launch Mindset 与 Who Writes 两节（写作分工中性化改写）。上游其余 11 个区间变更文件（reviewer-backends/reviewer-routing/review-tracing/compute-env-contract/fan-out-pattern 等）服务上游未收编技能或绑定宿主传输层，按既有子集裁剪裁决不新增。
