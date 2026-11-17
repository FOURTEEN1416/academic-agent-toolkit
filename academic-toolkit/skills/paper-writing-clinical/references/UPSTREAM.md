# UPSTREAM 溯源台账 — paper-writing-clinical

- Upstream: https://github.com/K-Dense-AI/claude-scientific-writer
- Pinned commit: 9820740d252800ecf0b8fc066ffb5bf9659f4a51（2026-11-16 实测上游 main HEAD，v2.23.0 线；原 0c726060，v2.9.1 线 2026-09-09 拉取）
- License: MIT（上游 LICENSE 随附于上游仓库根；fork：https://github.com/FOURTEEN1416/claude-scientific-writer，先 fork 后集成惯例）

## 拉取内容与目录适配

| 项 | 值 |
|----|----|
| 拉取文件 | 上游 `skills/` 下 15 个模块目录（scientific-writing / peer-review / citation-management / literature-review / scientific-critical-thinking / hypothesis-generation / venue-templates / scholar-evaluation / research-grants / clinical-reports / clinical-decision-support / treatment-plans / latex-posters / scientific-slides / market-research-reports），共 343 文件 / 约 4.0MB，纯文本（md/csv/json/txt/py/sh/tex） |
| 目录适配 | 上游 `skills/<module>/` 拷入本技能 `modules/<module>/`；**正文保持 pinned 原样**（可 diff 对照），适配层为：modules/ADAPTATION.md（兄弟模块映射表+API 依赖门）、15 个模块 SKILL.md 头部 `<!--ACAT-ADAPTED-->` 横幅、主 SKILL.md 头部适配块（2026-09-09 适应性改造） |
| SKILL.md 来源 | 本技能 SKILL.md **不是**上游文件：它是某 Claude.ai 用户定制打包版的孤本路由器（含该用户土耳其语/英语双语约定等个人偏好），其引用的合并版 `references/<module>.md` 结构在上游任何历史提交中都不存在（已核对上游 243 个提交全历史），资产孤本不可得 |
| 引用口径 | SKILL.md 正文 `references/ assets/ scripts/` 引用一律按 `modules/` 前缀解析（见 SKILL.md 头部适配说明块）；本 references/ 目录仅存放本台账 |
| API 依赖 | 上游 scripts 含 ANTHROPIC_API_KEY / Parallel CLI / OPENROUTER_API_KEY 依赖，本仓库无 API 环境；按 SKILL.md Global Rule 1 占位符替代口径处理，不可直接运行 |
| 未拉取部分 | 上游其余 11 个模块（docx/pdf/pptx/xlsx/infographics/markitdown/research-lookup/parallel-web/generate-image/scientific-schematics/pptx-posters）非本技能路由范围，未拉取 |

## 审计记录

- 2026-09-09：全库审计发现本技能自 initial public release（7529779）起仅含 SKILL.md 孤本，内部引用全部断链；定位上游并按上述口径补齐 `modules/` 资产，加 SKILL.md 头部适配说明块与本台账。

## 同步评估（2026-11-16，0c726060→9820740 跨 14 个 minor，UP-3）

- vendor/forks/claude-scientific-writer 已镜像同步至实测 HEAD（1838 文件更新、12 项旧版残留清理）。上游 v2.23.0 结构重组：新增 skill-overrides/、skills.lock.json、commands/ 等机制。
- ⚠️ 许可口径变化（实测核验）：上游主仓 LICENSE 仍为 MIT（K-Dense Inc.），但 `skills/docx|pdf|pptx|xlsx` 四个 Office 模块自本版起改源自 anthropics/skills（**Apache-2.0**，各模块自带 LICENSE.txt；上游 README.md:193 明示）。后续若吸收 Office 模块必须按 Apache-2.0 单独记账，不适用本技能现行的 MIT 口径。
- ~~本仓 15 个收编模块（modules/）的正文合并**待专项逐件 diff 评估**后再定~~ → **已完成（2026-11-16 重收编施工包 PKG-06）**，逐件结论：
  - **citation-management**（上游 15f）：`scripts/` 7 件取上游新版（新增 `_common.py` 标准库 BibTeX 解析/渲染/引文键、`search_openalex.py` 无钥 OpenAlex 客户端；`extract_metadata/format_bibtex/search_pubmed/search_google_scholar/validate_citations` 重构共享解析并修复 DOI URL 编码、PubMed 内联标题、结构化摘要、ESearch retmax 上限、arXiv entry_type 判定等）；`validate_citations.py` 移除未实现的 `--auto-fix`（报告与重写职责划界：validator 只报告，`format_bibtex.py --rekey/--deduplicate` 重写）；SKILL.md 与 5 个 references 按本仓口径融合（保留 ACAT 横幅、generate_schematic 退役声明、lit-zotero-obsidian 映射、GS 年份非运算符与两步提取法等既有裁决；融入 OpenAlex 优先的多库策略、`--rekey` 合并、`--check-dois`、报告 JSON 化）；`best_practices.md` 的 auto-fix 表述按新脚本事实修正。
  - **scientific-slides**（上游 10f）：`SKILL.md` 版本 1.5→1.8、html2pptx→PptxGenJS 3 处事实修正；`assets/powerpoint_design_guide.md`、`references/slide_capabilities.md`、`scripts/generate_slide_image_ai.py` 取上游新版（评审解析健壮化：ReviewResult 显式区分"未测出分数"与"通过"，防默认分数伪造）。
  - **research-grants / scientific-critical-thinking**：版本号同步；正文 `generate_schematic` 调用段按本仓退役裁决改写（上游仅改路径，本仓已于 2026-09-28 退役该路线，保留退役口径与第三方 API 披露）；`research-grants/references/README.md` 取上游新版（timeline_planning 并入 core_components 说明）。
  - **market-research-reports**：版本号同步；`scripts/validate_evidence_ledger.py` 取上游新版（publication 日期 "not-stated" 先行判别，修复误 parse）。
  - **latex-posters / literature-review / peer-review / hypothesis-generation / clinical-reports / clinical-decision-support / scholar-evaluation / scientific-writing / treatment-plans / venue-templates**：仅版本号元数据同步（上游其余变更为尾部新增 "Citing Scientific Agent Skills" 段与 pip→uv 工具链偏好，见下"未取用"）。
  - **未取用**（有意决策）：① 上游各 SKILL.md 尾部 "Citing Scientific Agent Skills"（arXiv:2609.00065）引用段——本仓 attribution 由本台账统一承担，不在 15 个模块内重复上游自我引用；② `pip install`→`uv pip install` 替换——执行环境不绑定 uv，保留通用 `pip` 写法；③ office 四模块（docx/pdf/pptx/xlsx，改源 anthropics/skills Apache-2.0）与 skill-overrides/ 机制——本技能从未收编，维持不收编。
- 上游新增/删除文件核对：`citation-management/scripts/generate_schematic.py`、`generate_schematic_ai.py` 上游已删除——本仓 modules 本就不含这两个文件，无动作；上游未新增本仓缺失的 references/assets。
