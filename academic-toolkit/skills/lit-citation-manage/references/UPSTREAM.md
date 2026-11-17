# UPSTREAM 溯源台账 — lit-citation-manage

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills（技能目录 `skills/citation-management`）
- Pinned commit: 2d2065fb4520fa3f3f2bcf61cff26ec8b7eba4b5（2026-11-16 实测上游 main HEAD，v2.72.0 线；原 36d8f13a，2026-08-24/09-09 两代拉取统一）
- License: MIT

## 适配说明

- 2026-09-09 专项治理批次 1a：从 fork https://github.com/FOURTEEN1416/scientific-agent-skills 拉取该技能 references/ assets/ scripts/ 补齐本仓库技能目录（SKILL.md 沿用本仓库既有版本未动）。
- 上游正文中 `research-lookup` 技能与 API 依赖（parallel-cli 等）在本仓库无对应环境，执行时以执行侧 web_search/web_fetch 工具替代，API 调用类脚本不可直接运行。
- 残留断链（上游亦无该资产）：见 tools/asset_gap_register.json 中本技能条目（诚实存量）。


## 同步评估（2026-11-16，36d8f13a→2d2065f v2.72.0，UP-2）

- vendor/forks/scientific-agent-skills 已镜像同步至实测 HEAD。
- ⚠️ 上游 v2.72.0 已移除/重组本技能来源目录 `skills/lit-citation-manage`（新址：citation-management）；本仓收编副本为存续快照，后续升级转本地维护为主，如需跟进新上游结构须按收编规程重新评估。

## 重收编落地（2026-11-16，2d2065f 增量改写融入，UP-3）

- assets/ 两份、references/ 十二份、scripts/ 七份按上游增量补丁融入（除 pubmed_search.md 含本地既有修正外其余与上游旧版全同，应用干净、无拒绝 hunk；pubmed_search.md 应用后与上游新版仅差一处本地既有代码围栏修正）。新增上游 references/api_contracts.md（九类服务端点/鉴权/分页/校验边界契约表，事实性内容，直接收编）。六个脚本 `python -I -m py_compile` 全部通过。
- SKILL.md 保留本仓文本体系；择要融入上游增量：Phase 2 补"元数据完整性纪律"（online-first 缺卷/页/DOI 不造假、审计日志记录来源、citation-key 重复以 DOI+书目一致性判定）；Resources 参考件清单补全（含新增 api_contracts.md），脚本清单补 `_common.py` 并更新 search_openalex 描述；新增可选凭据矩阵（NCBI_EMAIL / OPENALEX_EMAIL / OPENALEX_API_KEY 各自独立发送、key 非配额保证、分页失败即退出不输出残缺"完整"结果）。
- 上游新增 "Citing Scientific Agent Skills" 段属上游自我引用话术，未收编。
