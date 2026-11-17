# UPSTREAM

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（vendor/forks/Auto-claude-code-research-in-sleep，MIT）
- Pinned commit: 9f30e83（2026-11-16 实测上游 HEAD 9f30e834d24a337dbdd06fb20a1150d4376dfa59；原 94d8093，2026-08-26 拉取，vendor-asset-index #2）
- License: MIT（fork 根 LICENSE）
- 收编件: 本技能（V1.1 同名整采批；2026-09-23 v2.0 收尾补登记）。W3 语义化改名前后均在库；正文随本仓演进，与上游已分叉。
- Local adaptation: 原文入库后随本仓演进；本地适配与命名规范以本仓为准。


## 同步评估（2026-11-16，94d8093→9f30e83，UP-1）

- vendor/forks/Auto-claude-code-research-in-sleep 已镜像同步至实测 HEAD（768 文件更新、0 删除）。
- 上游区间 skills/ 变更 177 文件（+11563/-1014），主要为止(install/SSH 同步修复与文档扩充)。本件对应上游目录 skills/paper-slides：上游区间内有变更。
- 技能侧重收编待专项按改写融入规程执行：上游新版技能正文 allowed-tools 含 Codex MCP 评审桥类宿主特征词（host_dep_scan 词表项，字面量此处不复写以维持登记外零命中棘轮），本仓技能侧 SKILL.md 为中性化改写版，不盲目覆盖。

## 重收编融入（2026-11-16，PKG-02，pin 94d8093→9f30e83）

- 已吸收：Phase 5 评审降级语义增强——评审脚本不可用时在 `SLIDES_STATE.json` 记录 `review_status: REVIEW_UNAVAILABLE`，该轮结论按草稿期自评对待，后续不得标注为"已外部评审"、不得临时切换评审服务；已并入 SKILL.md Phase 5 两处降级提示，保留本仓"自身分析能力完成评审"的闸门下沉裁决。
- 未吸收：上游 allowed-tools 扩充、reviewer-backends 槽位解析段、REVIEWER_MODEL gpt-5.6-sol→gpt-6-astra 改名（本仓为外部评审脚本 + 环境注入模型，不预设模型名）；"勿把 style-ref 缓存传给评审"条款因本仓已裁剪 style-ref/缓存体系，无对应机制，不臆造。
- 自查：host_dep_scan 对本技能 SKILL.md 零命中（2026-11-16 实跑）。
