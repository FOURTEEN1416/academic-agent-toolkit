# UPSTREAM

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（vendor/forks/Auto-claude-code-research-in-sleep，MIT）
- Pinned commit: 9f30e83（2026-11-16 实测上游 HEAD 9f30e834d24a337dbdd06fb20a1150d4376dfa59；原 94d8093，2026-08-26 拉取，vendor-asset-index #2）
- License: MIT（fork 根 LICENSE）
- 收编件: 本技能（V1.1 同名整采批；2026-09-23 v2.0 收尾补登记）。W3 语义化改名前后均在库；正文随本仓演进，与上游已分叉。
- Local adaptation: 原文入库后随本仓演进；本地适配与命名规范以本仓为准。


## 同步评估（2026-11-16，94d8093→9f30e83，UP-1）

- vendor/forks/Auto-claude-code-research-in-sleep 已镜像同步至实测 HEAD（768 文件更新、0 删除）。
- 上游区间 skills/ 变更 177 文件（+11563/-1014），主要为止(install/SSH 同步修复与文档扩充)。本件对应上游目录 skills/paper-plan：上游区间内有变更。
- 技能侧重收编待专项按改写融入规程执行：上游新版技能正文 allowed-tools 含 Codex MCP 评审桥类宿主特征词（host_dep_scan 词表项，字面量此处不复写以维持登记外零命中棘轮），本仓技能侧 SKILL.md 为中性化改写版，不盲目覆盖。

## 重收编融入（2026-11-16，PKG-02，pin 94d8093→9f30e83）

- 已吸收：writing-principles 引用处新增 Claims-Evidence Matrix 规划语义——从最强且证据最足的贡献讲起、每个实验分配论证职责、假设绑定到对应论断而非堆免责清单；已按本仓行文改写进 SKILL.md 写作 overlay 段。
- 未吸收：上游 allowed-tools 扩充（antigravity/grok/claude-review 等 MCP 桥）与 reviewer-backends 槽位解析段属宿主特征，本仓以 REVIEWER_SCRIPT 中性化机制覆盖；REVIEWER_MODEL gpt-5.6-sol→gpt-6-astra 为宿主内模型代号，本仓不预设模型名，不跟随。
- 自查：host_dep_scan 对本技能 SKILL.md 零命中（2026-11-16 实跑）。
