# UPSTREAM 溯源台账 — spine（PaperSpine 套件）

- Upstream: https://github.com/WUBING2023/PaperSpine（Claude 适配分发 `dist/claude/skills/paper-spine/`）
- Pinned commit: 1a79bf21c76a73cb31f4310bc42f847a04e91d1a（2026-11-16 实测上游 HEAD，tag v4.0.0；原 1fe46f0，fork FOURTEEN1416/PaperSpine 2026-09-09 拉取）
- License: MIT（2026-11-16 UP-4 落实：上游仓库 LICENSE 原文核验为 MIT License, Copyright (c) 2026 PaperSpine contributors）

## 适配说明

- 本仓库 spine 系 11 个技能为上游单一 paper-spine 技能的**拆分重组**编排；2026-09-09 专项治理批次 2 按各技能 SKILL.md 引用从上游分发目录回填 scripts/references 资产。
- 上游脚本对本仓库为只读工具，编排仍按本仓库各技能 SKILL.md 执行。

## 收编记录

- 2026-09-28：用户裁决允许拉取；自 pin `1fe46f0`（fork FOURTEEN1416/PaperSpine，HEAD 即 pin）回填缺失资产至本技能；上游 LICENSE=MIT 核验通过（sha256 e89308aa6fe435bd…）。部分引用件（humanize-tiers/build-from-materials/paragraph_function_templates/result_narrative_templates）上游 pin 亦无，维持 ASSET-GAP 缺位登记。


## 同步评估（2026-11-16，1fe46f0→1a79bf2 tag v4.0.0，UP-4）

- vendor/forks/PaperSpine 已镜像同步至实测 HEAD（1648 文件更新、9 项上游旧版发布残留清理）；上游 2 个月更新含 v4.0.0 大版本（多语言 README、portable suites/release v6 工作流、INSTALL 文档族等）。
- 本仓 spine 系 11 技能为上游单一 paper-spine 技能的拆分重组编排（脚本/资产只读引用），上游 v4.0.0 技能包结构变化须经逐件 diff 评估后按收编规程重放，本单仅完成 vendor 同步与台账刷新，技能侧重收编待专项。

## 重收编施工记录（2026-11-16，PKG-07 spine 系批）

- writing-rationale-matrix.md：吸收贡献承诺语义（推进/验证/解释/约束四类、动机对齐不越声明边界）、深度要求软化（行数≠深度）、第四墙规则按科学/透明功能判断（保留必需 AI 披露）、F1 框架行改写；保持本仓 9 列表头为单一真源。
- rewrite-matrix.md：吸收贡献任务/声明 ID 与动机对齐列、红线推导读贡献+动机、草稿暗示更强声明回确认而非静默改约、closed-book 适用条件精化、unchanged ratio 诊断化。
- deep-imitation-protocol.md：吸收「按观察到的推理与写作变化判断学习」、no-op 精准证据、KEEP/ADD 比例诊断化、revision_audit 相似度仅为诊断、Results 保留用户已报告结果并区分复现、Discussion 允许已验证公共文献检索。
- motivation-thread-writing.md：吸收「贡献契约治理动机线」、确认前锁贡献、未决时继续安全工作、confirmed_motivation 增 governing contribution 字段与声明边界约束。
- logic-transfer-audit.md：吸收重写判据精化（未解决论证缺陷才是重写理由，段落功能未变不是）。
- 未吸收（记入 skipped）：上游对 rationale matrix 的 strict-only 降级（本仓裁决 matrix 为执行计划，保持必需）；author_voice_* 与 results-validation/scientific-evidence-ledger 等 v6 产物链（本仓无对应阶段与脚本，收编待裁决）。
