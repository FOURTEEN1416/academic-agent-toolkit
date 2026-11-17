# UPSTREAM 溯源台账 — spine（PaperSpine 套件）

- Upstream: https://github.com/WUBING2023/PaperSpine（Claude 适配分发 `dist/claude/skills/paper-spine/`）
- Pinned commit: 1a79bf21c76a73cb31f4310bc42f847a04e91d1a（2026-11-16 实测上游 HEAD，tag v4.0.0；原 1fe46f0，fork FOURTEEN1416/PaperSpine 2026-09-09 拉取）
- License: MIT（2026-11-16 UP-4 落实：上游仓库 LICENSE 原文核验为 MIT License, Copyright (c) 2026 PaperSpine contributors）

## 适配说明

- 本仓库 spine 系 11 个技能为上游单一 paper-spine 技能的**拆分重组**编排；2026-09-09 专项治理批次 2 按各技能 SKILL.md 引用从上游分发目录回填 scripts/references 资产。
- 上游脚本对本仓库为只读工具，编排仍按本仓库各技能 SKILL.md 执行。
- 改写融入（2026-09-23，R1）：SKILL.md 死路径命令改仓内解析（ACAT-GOVERNANCE 语义保留）。

## 收编记录

- 2026-09-28：用户裁决允许拉取；自 pin `1fe46f0`（fork FOURTEEN1416/PaperSpine，HEAD 即 pin）回填缺失资产至本技能；上游 LICENSE=MIT 核验通过（sha256 e89308aa6fe435bd…）。部分引用件（humanize-tiers/build-from-materials/paragraph_function_templates/result_narrative_templates）上游 pin 亦无，维持 ASSET-GAP 缺位登记。


## 同步评估（2026-11-16，1fe46f0→1a79bf2 tag v4.0.0，UP-4）

- vendor/forks/PaperSpine 已镜像同步至实测 HEAD（1648 文件更新、9 项上游旧版发布残留清理）；上游 2 个月更新含 v4.0.0 大版本（多语言 README、portable suites/release v6 工作流、INSTALL 文档族等）。
- 本仓 spine 系 11 技能为上游单一 paper-spine 技能的拆分重组编排（脚本/资产只读引用），上游 v4.0.0 技能包结构变化须经逐件 diff 评估后按收编规程重放，本单仅完成 vendor 同步与台账刷新，技能侧重收编待专项。

## 重收编施工记录（2026-11-16，PKG-07 spine 系批）

- 上游 1fe46f0e→1a79bf2 区间 src/skill 增量已按「改写融入」规程落到本技能（逐件明细见 `dev-docs/audits/2026-11-16-裁决落地/absorb-PaperSpine（spine 系）.md`）。
- SKILL.md：增补「工具成功≠就绪」原则、图与证据纪律（含机制图显式决策）、完成契约（本地交付≠投稿就绪、外部投稿需单独授权）；动机确认扩展为「动机+贡献承诺+声明边界」。
- references 10 件增量吸收：research（研究范围三态/evidence handoff/tier 不授权分析）、citation（文献范围契约/去重/覆盖核对/诊断以实引为准）、intake（恢复复用配置/研究范围纪律/交付不变性）、rewrite（证据感知计划/直接陈述有支持的发现/评审针对实际渲染物）、build（资产选择/值-来源绑定/渲染前守卫/真实引擎编译）、latex（模板采用验证/图最终尺寸/Word 独立读者面与纯文本回读）、audit（检查失效重跑/editor synthesis 前置/同输入三振）、submission（本地交付≠上传就绪/可移植包构建法）、translate（清单为守卫基线/Word 多后端）、orchestrator-branch-map（语义确认/路由扩充/终审回溯最上游）。
- 未吸收（记入 skipped）：v6 产品运行时（Web 任务工作台、paperspine_* 工具链、update preflight 自动更新）、paperspine5/ 开发树、website/atlas/install 脚本、contracts/*.schema.json、上游对 terminal-wizard 路线的降级（与本仓「终端向导为受支持 UI」裁决冲突，保持本仓裁决）。
