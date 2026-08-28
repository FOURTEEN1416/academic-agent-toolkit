# v1.0.0 发布说明（CHANGELOG）

> 发布日期：2026-08-17
> 宿主：OpenCode Desktop（唯一正式支持宿主）
> 发布包：`releases/v1/`

## 范围

六大领域 33 个聚合能力（225 个公开技能映射）：

| 域 | 能力 | 状态 |
|----|------|------|
| 数模竞赛 | comp_cumcm_full_pipeline / comp_problem_analysis / comp_modeling / comp_code_solve / comp_paper_zh / comp_review_visual / comp_final_audit / comp_mcm_icm / comp_consistency / comp_literature | **正式**（10） |
| 数模竞赛 | comp_stats_topic | experimental（数据获取证据待补） |
| 学术论文 / 文献研究 / 课程材料 / 知识产权 / 图表文档 | 22 个聚合能力 | experimental（C1+C2 已验，C3/C4 基准待建） |

## 正式能力验收依据（design §7）

- C1 合同完整：33/33（13 字段，0 缺失）
- C2 真实验收：公开基准 P01-P03 + 私有 2025B + 14 步 workflow 流程级验收
- C3/C4 双层基准：公开（合成题）+ 私有（真实题面）端到端通过
- C5 四类指标：多智能体独立评审校准（≥4/5 质量、≥90% 成功率、≥95% 证据完整率、≤15min 效率、≤15 credits 成本）
- C6 回归：204 tests passing（源仓库）+ 发布包 200 tests（160+3skip 套件 + 37+3skip 基准）
- 防伪造机制：requires_subagent + 命令真实性 + review full 模式 + manifest 哈希

## 关键机制

- 三层审计（L1 拦截式 plugin / L2 编排式 runner / L3 申报式 evidence）+ 防绕过检测
- 检查点审批原子事务；质量门禁（大小/伴随/页数/图表/审稿）
- 多角色审稿闭环（executor/reviewer/editor，独立视角强制）

## 许可

- 核心（套件/配置）：CC-BY-NC-4.0（与 LICENSE 文件一致；原记录 MIT 系笔误，2026-08-28 治理修正）
- 公开基准集：CC-BY-4.0
- 私有扩展/真实题面/内部文档：不随包分发

## 已知限制

- 私有扩展能力（专利/软著/基金等 9 条）不在此包，需单独申请
- 跨域能力（论文/文献/课程等 22 个）仅 C1+C2 验收，基准待建，状态 experimental
- **C5 校准已定稿（2026-08-17）**：放弃人工专家复核——多智能体独立评审（2 评审者共识）为最终校准，理由：基于全部真实观测、独立评审一致、保守取值、session 可追溯（见 CALIBRATION.md 方法变更声明）
- 视觉审查依赖视觉 API（不可用时如实记录 unavailable）

## 变更历史

- 2026-08-17：v1.0.0 发布包组装完成（净化：剔除 .env/sqlite/私有技能/私有模板；适配：私有基准与宿主配置测试跳过）
- 2026-08-17：发布前最终复核完成——C5 放弃人工复核定稿；catalog 合规修正强制（10 正式）；全量回归源 214 + 包 200；边界安全扫描无残留；合规修正曾被覆盖后重新强制执行（根因：后续 catalog 重写操作），现锁## [v1.1.0] - 2026-08-28

### Added

- 科研绘图扩展：集成 9 个上游技能（scientific-visualization / matplotlib / seaborn / plotly / figure-spec / graphviz / excalidraw-diagram / infographics / scientific-schematics），catalog 新增 `scientific_plotting_expanded` 能力
- ZCode 兼容层：根 AGENTS.md（宿主支持矩阵）、`.zcode/config.json`（docsearch MCP）、`.zcode/skills` 技能联结、`/doc-governance` 命令与 `acat-doc-governance` 治理技能
- 全学术定位：主套件目录更名 `科研工具箱/`（原 数学建模全流程套件/），文档定位统一为 6 大能力域科研工具箱

### Changed

- **发布边界（用户裁定 2026-08-28）：项目所有能力公开发布**——9 项 private_extension（软著 copyright-draft/build、专利 patent-draft/build、基金 grants 等）转为 experimental，不再设私有扩展边界；验收状态保持如实（未跑 C2-C5 者仍为实验性，正式仍为 10 项）
- 文档治理：45+ 份文档全文审计，17 份过期快照加"仅供追溯"横幅，修正许可矛盾（MIT→CC-BY-NC-4.0）与多处漂移数字；溯源台账扩至 26 条

定