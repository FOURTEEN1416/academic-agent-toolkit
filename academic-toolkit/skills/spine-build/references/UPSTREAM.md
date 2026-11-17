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

- references/writing-rationale-matrix.md：与 spine-rewrite 单源同步（贡献承诺语义、深度软化、第四墙按功能判断、F1 行改写），两副本 `diff` 验证逐字节一致。
- 本技能正文编排不变；上游 build 侧增量（资产选择、渲染前守卫、真实引擎编译、Word 独立读者面）已吸收进套件级 `spine/references/build.md` 与 `spine/references/latex.md`。
- 未吸收（记入 skipped）：author_voice_* / asset_selection_receipt 等 v6 资产与产物链（本仓无对应阶段与脚本，收编待裁决）。
