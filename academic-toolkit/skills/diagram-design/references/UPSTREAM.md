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

## 重收编落地（2026-11-16，PKG-13 改写融入批）

- 方法：以 `20be6e0`（=旧 pin ac490fd）为 base、本仓工作树为 ours、`1228954`（=新 pin f6db0de）为 theirs 做**逐文件三方合并**（git merge-file），保留本仓全部既有适配（执行与产出节、R1 中性化、E3/E4 修复），在其上融入上游增量。
- 结果：317 个上游文件——111 件新增（16 references + 5 scripts + 90 assets，含 50 型画廊补全：heatmap/waterfall/steps/exploded/axonometric-plan/service-blueprint/sbgn/requirement-traceability/event-modeling/unit-grid/architecture-delta 及 Excalidraw/PlantUML 导入与 SVG/PNG 导出链）、188 件快进、7 件无冲突合并、11 件冲突人工解决（6 assets 取上游中性新版；type-nested/type-process/type-high-level/SKILL.md description 取上游；doctor.md 维持本仓中性版，上游"插件布线节"针对 Claude commands/Pi prompts 维护者模式，不适用本仓分发形态，不收）。
- 皮肤令牌升级随上游全量落位：accent `#eb6c36`→`#bf4520`（burnt-tangerine，对比度达标）、soft `#7a8399`→`#5a6580`；style-guide 增对比度合同、Font source（web/system）、韩/中/西里尔标签扩展。
- 宿主中性化：合并引入的上游多宿主安装路径清单（Pi/Kiro/OpenCode/Cursor/Cline/Codex/Copilot/Droid）改写为宿主中性检索口径（用户级/项目级/运行时声明路径 + 本仓随仓使用），host_dep_scan 登记外零命中保持。
- 验证：py_compile 8 件脚本通过；self_check/verify_geometry 抽测 OK；mermaid/drawio/excalidraw/plantuml 四提取器与 export_svg 以最小夹具实测出正确 IR/SVG；最小 pytest 集（host_dep_scan/查重/INNER_REF/中性化棘轮）通过。
