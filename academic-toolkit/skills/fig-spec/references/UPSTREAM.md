# FigureSpec 技能来源记录

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（fork 自 wanshuiyin/Auto-claude-code-research-in-sleep， 科研绘图能力扩展集成）
- Pinned commit: 94d8093
- Checklist date: 2026-08-28
- Local use: `skills/fig-spec/`（SKILL.md 及附带 references/assets/scripts）
- License: MIT（见仓库 LICENSE）
- Local adaptation: 原样集成，未改动 SKILL.md 正文；路径引用按本套件目录结构解析。
- 改写融入（2026-09-24，R2 深度）：SKILL.md 渲染器解析链自上游 ARIS 多层安装布局重写为本仓两层（仓内技能目录+显式覆盖）；references/integration-contract.md 与 review-tracing.md 的 helper 解析链、traces 目录约定（.aris/traces → <workspace>/traces）、悬空的 save_trace.sh 引用全部改写/移除；通用工程方法论内容保留。
  - 2026-09-22（modex-3 同源吸收 P3）：自上游 `skills/shared-references/` 收编
    `integration-contract.md`、`review-tracing.md` 至本技能 `references/`（SKILL.md 原指针悬空已修）；
    SKILL.md 中宿主专有 reviewer 工具名改为宿主中性表述。

## Upgrade rule

上游 fork 更新后，对比 SKILL.md 与附带资产再同步；同步后刷新本文件的 Pinned commit 与 Checklist date。
