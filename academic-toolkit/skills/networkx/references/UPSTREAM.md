# UPSTREAM 溯源台账 — networkx

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills（技能目录 `skills/networkx`）
- Pinned commit: 2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5（2026-11-16 实测上游 main HEAD，v2.72.0 线；原 36d8f13a，2026-08-24/09-09 两代拉取统一）
- License: MIT

## 适配说明

- 2026-09-09 专项治理批次 1a：从 fork https://github.com/FOURTEEN1416/scientific-agent-skills 拉取该技能 references/ assets/ scripts/ 补齐本仓库技能目录（SKILL.md 沿用本仓库既有版本未动）。
- 上游正文中 `research-lookup` 技能与 API 依赖（parallel-cli 等）在本仓库无对应环境，执行时以执行环境提供的 web_search/web_fetch 替代，API 调用类脚本不可直接运行。
- 残留断链（上游亦无该资产）：以本技能 ASSET-GAP.md 清单与"根目录平铺"现状为准（登记册无本技能条目；2026-09-28 核对）。


## 同步评估（2026-11-16，36d8f13a→2d2065f v2.72.0，UP-2）

- vendor/forks/scientific-agent-skills 已镜像同步至实测 HEAD（2780 文件更新、246 项删除——含上游移除的 vendored docx/pdf/pptx/xlsx）。
- 上游 v2.72.0 本技能目录仍在，正文有更新（本仓技能侧差异 7 处，上游含 SKILL.md 重写与新增 references）；技能侧重收编待专项按改写融入规程执行（本仓含 ACAT-ADAPTED 适配层与归一化 frontmatter，不盲目覆盖）。

## 重收编落地（2026-11-16，2d2065f 增量改写融入，UP-3）

- SKILL.md：NetworkX 3.7 口径与"片段非顺序脚本"声明；最短路权重语义（距离 vs 强度）与自洽示例；社区发现补 Leiden（3.7 原生，CPM/modularity 之别）；node-link JSON `edges="edges"`；邻接矩阵/稀疏往返保序保零权并重挂节点标签；新增"分析契约"与"科学解释"两条边界；backend 派发谨慎表述；节点不可为 `None`；先删边后删点；官方文档链接 latest→stable。上游新增的 "Citing Scientific Agent Skills" 段属上游自我引用话术，未收编。
- references/algorithms.md、generators.md、graph-basics.md、io.md、visualization.md：按上游增量补丁融入（路径重写 + 忽略行尾差异），含 Leiden 小节、连通性前提、`default=set()`、`node_connected_component(n=1)`、closeness 方向性、PageRank 个性化质量校验、配置模型化简不保度、DAG 保孤立点、GraphML/GEXF 类型契约、CSV 表头/重复边校验、momepy CRS 前提、`mmread(spmatrix=False)`、BFS 前驱 3.7 弃用替代、`max_weight_matching(maxcardinality=True)` 等。
- 上游新增的 review.md 自测记录（位于上游 references 目录；其测试栈/执行清单不可转述为本仓已执行）未收编；其"科学解释与互操作边界"实质要点已改写并入上述文件，文中不再指向 review.md。
