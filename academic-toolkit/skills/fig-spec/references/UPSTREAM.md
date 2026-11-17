# FigureSpec 技能来源记录

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（fork 自 wanshuiyin/Auto-claude-code-research-in-sleep， 科研绘图能力扩展集成）
- Pinned commit: 9f30e83（2026-11-16 实测上游 HEAD 9f30e834d24a337dbdd06fb20a1150d4376dfa59；原 94d8093，2026-08-26 拉取，vendor-asset-index #2）
- Checklist date: 2026-11-16
- Local use: `skills/fig-spec/`（SKILL.md 及附带 references/assets/scripts）
- License: MIT（见仓库 LICENSE）
- Local adaptation: 原样集成，未改动 SKILL.md 正文；路径引用按本套件目录结构解析。
- 改写融入（2026-09-24，R2 深度）：SKILL.md 渲染器解析链自上游 ARIS 多层安装布局重写为本仓两层（仓内技能目录+显式覆盖）；references/integration-contract.md 与 review-tracing.md 的 helper 解析链、traces 目录约定（.aris/traces → <workspace>/traces）、悬空的 save_trace.sh 引用全部改写/移除；通用工程方法论内容保留。
  - 2026-09-22（modex-3 同源吸收 P3）：自上游 `skills/shared-references/` 收编
    `integration-contract.md`、`review-tracing.md` 至本技能 `references/`（SKILL.md 原指针悬空已修）；
    SKILL.md 中 reviewer 工具名已改中性表述。2026-10 中性化清洗批已将
    `references/review-tracing.md` 的示例执行器名与后端枚举中性化（字段名、traces 目录契约不变）。

## Upgrade rule

上游 fork 更新后，对比 SKILL.md 与附带资产再同步；同步后刷新本文件的 Pinned commit 与 Checklist date。

## 重收编融入（2026-11-16，PKG-02，pin 94d8093→9f30e83）

- 复核结论：上游区间 figure-spec 仅 +15/-2，内容为 allowed-tools 扩充（antigravity/grok/claude-review 等 MCP 桥）、reviewer-backends 槽位解析前置段、评审模型代号 gpt-5.6-sol→gpt-6-astra——均属宿主特征/宿主内模型代号。本仓 SKILL.md Step 5 已以宿主中性评审通道（"whatever reviewer path the host provides"，模型与 effort 由宿主配置注入）覆盖同等语义，无实质写作方法论增量可融入，本轮未改动正文。
- 自查：host_dep_scan 对本技能 SKILL.md 零命中（2026-11-16 实跑）。
