# Graphviz 技能溯源记录（clean-room 改写结案）

- Upstream: https://github.com/FOURTEEN1416/skills（fork 自 markdown-viewer/skills；2026-11-16 订正：原记 URL FOURTEEN1416/markdown-viewer-skills 已 404）
- Pinned commit: a3afd45（2026-05-26，上游最后包含 graphviz 技能的时点——其后 fc70465 即删除该技能，见下方同步评估）
- Checklist date: 2026-09-23
- License: GPL-3.0（仅约束上游仓库内的原件文本，见下方声明；系 pin a3afd45 时点口径，非现值）
- 上游许可演变：MIT → GPL-3.0（2026-04-23 c9c64d1）→ CC-BY-4.0（2026-09-22 6c078f5 起，并新增根 LICENSE 文件）；2026-11-16 核查现值为 CC-BY-4.0（仅要求 attribution，无传染义务；其 documd CLI 与渲染引擎仍为 GPL-3.0-only 且不在授权内）。本仓现行文本为独立创作，不受影响。核查依据：dev-docs/audits/2026-11-16-裁决落地/LICENSE_FACTS.md §3/§3a。

## Clean-room 改写声明（2026-09-23 用户裁决：二次改写后保留）

- 本技能现行文本（SKILL.md、references/syntax.md）为**独立创作**：创作过程仅以
  "上游两个技能文件覆盖安装、DOT 语法、渲染用法三类主题"这一事实清单为输入，
  未参考、未复制、未改译上游文件的任何文字表达。DOT 语言与 Graphviz 软件本身
  是开放知识，不受那两个技能文件的版权约束。
- 上游 GPL-3.0 原件文本已不再以任何形式存在于本库（含正文、frontmatter 描述、
  能力目录、路由索引等派生面）；此前收编的集成件已被上述独立创作文本整体替换。
- 据此，本技能现行文本不构成上游作品的衍生件，GPL-3.0 传染义务随原件移除而
  解除；文本随本仓既有许可分发。裁决与结案记录：
  `dev-docs/vendor-asset-index.md` §5.4（内部私有文档）。
- 下方溯源字段（Upstream / Pinned commit / License）按审计要求保留：它们记录的
  是**历史来源事实**，不代表现行文本的许可状态。

## 同步规则（改写后）

- 现行文本为独立创作，无上游同步对象；**禁止**从原上游仓回灌文本。
- 如未来确需参考上游表达，须先经用户重新裁决，并改写本记录。
- 2026-11-16 复核：上游已于 fc70465 删除 graphviz 技能（见下方同步评估），"无上游同步对象"由裁决口径进一步成为事实状态。

## 同步评估（2026-11-16，a3afd45→2672b69，PKG-17）

- 上游复核时点：markdown-viewer/skills HEAD 2672b69（2026-10-05）。**上游已删除 graphviz 技能**：pin 的下一个提交 fc70465（2026-09-22 "refactor skills."）将全仓重组为 documd-visuals/ 包，graphviz/ 目录整体移除（该提交全树 0 个 graphviz 路径）；191673c（2026-09-25）进一步删除 dot 渲染引擎、把对应示例改写为 PlantUML。
- 故本区间 graphviz 技能**无可融入的上游文本增量**——不存在"上游改进版 graphviz 正文"可供改写吸收。本仓 SKILL.md 与 references/syntax.md 保持不动：既不回退 2026-09-23 clean-room 裁决成果，也不臆造上游已不存在的内容。
- pin 维持 a3afd45：镜像 vendor/forks/skills/graphviz/ 快照与上游 a3afd45 原件逐字节一致（仅行尾 CRLF 差异），仍是"上游最后包含 graphviz"的忠实快照。
- 前置澄清结论（PKG-17"许可冲突"）：GitHub 现检出的 CC-BY-4.0 与本台账 GPL-3.0 并非矛盾——GPL-3.0 为 pin 时点（2026-05-26~2026-09-22）历史口径，现值 CC-BY-4.0；本仓文本为独立创作，两者均不约束现行正文。
- 遗留：vendor/forks/skills 整镜像是否跟进上游 documd-visuals/ 新结构（fork 同步）属独立基建决策，超出本包范围；dev-docs/vendor-asset-index.md:39 的同一 fork URL 笔误与 LICENSE"待核"注记留待台账批统一订正。
