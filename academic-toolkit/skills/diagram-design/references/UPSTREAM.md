# Diagram Design 技能来源记录

- Upstream: https://github.com/FOURTEEN1416/diagram-design（fork 自 cathrynlavery/diagram-design，科研绘图能力扩展 v1.1 追加集成）
- Pinned commit: f6db0de（2026-11-16 实测上游 HEAD f6db0decea96de66b901331a0f79a8d4b147ebae；原 ac490fd，科研绘图能力扩展 v1.1 追加集成）
- Checklist date: 2026-08-29
- Local use: `skills/diagram-design/`（SKILL.md + references 39 类图型规范 + assets + scripts 自检工具）
- License: MIT（见上游仓库 LICENSE；内嵌第三方见上游 THIRD_PARTY_LICENSES.md）
- Local adaptation: 原样集成，未改动 SKILL.md 正文；`.diagram-design` 风格档按原设计在用户项目内生效。
- 改写融入（2026-09-24，R1）：HTML 示例六件主题中性化、onboarding 安装教学改随仓使用、type-nested 用例措辞中性化。

## Upgrade rule

上游 fork 更新后对比 SKILL.md 与 references 再同步；同步后刷新本文件的 Pinned commit 与 Checklist date。

## 同步评估（2026-11-16，ac490fd→f6db0de，UP-11）

- vendor/forks/diagram-design 已镜像同步至实测 HEAD（763 文件，上游 skills/scripts/docs 大版本更新，本地无独有文件）。
- 上游技能包变化：SKILL.md 重写（546 行 diff）、references 8 件更新（animation/doctor/export/import-drawio/import-mermaid/onboarding/output-spec/primitive-annotation，新增 print-a3-landscape 尺寸与窄屏画布规范等）、assets 新增 20+ HTML 示例（含 dark/full 变体）、scripts 新增 excalidraw_extract/export_png/export_svg 并更新 drawio/mermaid 提取器。
- 技能侧重收编**待专项按改写融入规程执行**（AGENTS.md 上游资产收编规程）：①上游新版 onboarding.md 含宿主安装路径教学 5 处特征词（宿主用户级/项目级配置目录类词表项，host_dep_scan 登记外零命中棘轮会被打破，字面量此处不复写），须重放"随仓使用"中性化；②新增 HTML 示例须过主题中性化；③SKILL.md 546 行重写须与 references 版本配套收编，避免错配。本仓 2026-09-24 R1 批中性化成果在专项中重放。
