# UPSTREAM

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（vendor/forks/Auto-claude-code-research-in-sleep，MIT）
- Pinned commit: 9f30e83（2026-11-16 实测上游 HEAD 9f30e834d24a337dbdd06fb20a1150d4376dfa59；原 94d8093，2026-08-26 拉取，vendor-asset-index #2）
- License: MIT（fork 根 LICENSE）
- 收编件: 本技能（V1.1 同名整采批；2026-09-23 v2.0 收尾补登记）。W3 语义化改名前后均在库；正文随本仓演进，与上游已分叉。
- Local adaptation: 原文入库后随本仓演进；本地适配与命名规范以本仓为准。
- 改写融入（2026-09-23，R1）：merged-rebuttal-workflow.md 上游未集成文件引用改中性表述。


## 同步评估（2026-11-16，94d8093→9f30e83，UP-1）

- vendor/forks/Auto-claude-code-research-in-sleep 已镜像同步至实测 HEAD（768 文件更新、0 删除）。
- 上游区间 skills/ 变更 177 文件（+11563/-1014），主要为止(install/SSH 同步修复与文档扩充)。本件对应上游目录 skills/rebuttal：上游区间内有变更。
- 技能侧重收编待专项按改写融入规程执行：上游新版技能正文 allowed-tools 含 Codex MCP 评审桥类宿主特征词（host_dep_scan 词表项，字面量此处不复写以维持登记外零命中棘轮），本仓技能侧 SKILL.md 为中性化改写版，不盲目覆盖。

## 重收编融入（2026-11-16，PKG-02，pin 94d8093→9f30e83）

- 已吸收：REVIEWER_MODEL 条目补入跨模型家族约束——评审模型须来自与被评正文写作模型不同的家族（OpenAI / Anthropic / Google / DeepSeek / Moonshot·Kimi / Qwen 等互为跨族），防同族自评偏置；具体模型仍由环境注入，本仓不预设。
- 未吸收：上游 allowed-tools 扩充、reviewer-backends 槽位解析段、REVIEWER_MODEL gpt-5.6-sol→gpt-6-astra 改名——本仓评审桥机制已覆盖"先解析评审槽位再调用"语义（工具名以当前环境为准，缺席降级自审），不跟随宿主特征。
- 自查：host_dep_scan 对本技能 SKILL.md 零命中（2026-11-16 实跑）。
