# UPSTREAM 溯源台账 — latex-document

- Upstream: https://github.com/ndpvt-web/latex-document-skill
- Pinned commit: fb5a159609371ca2c7905fa99ae8c92396cdbcae（fork FOURTEEN1416/latex-document-skill，2026-09-09 拉取；2026-11-16 复核：上游 main 已推进至 d165ee6（2026-11-15），52 个新提交全部为 stats/ 流量日更，技能内容零增量，pin 维持 fb5a159；fork 仓库侧快进同步待执行）
- License: MIT（仅上游 README.md "## License" 节单词声明；仓库无 LICENSE 文件、无许可正文；GitHub API license=null，2026-11-16 核查，详见 dev-docs/audits/2026-11-16-裁决落地/LICENSE_FACTS.md §2）

## 适配说明

- 2026-09-09 专项治理批次 2：拷入上游 references/ assets/ scripts/ 补齐本仓库技能目录（SKILL.md 沿用本仓库既有中文触发词版本未动）。
- 上游 scripts 依赖 TeX Live/pdftoppm 等本地工具链，运行时按 SKILL.md 自动安装逻辑处理；无外部 API 依赖。
- 残留断链（上游亦无）：见 tools/asset_gap_register.json 本技能条目。
- 改写融入（2026-09-23，R1）：references/advanced-features.md 路径解析说明已按本仓目录结构改写。
- 2026-11-16 重收编批：自 fork 快照（fb5a159，与上游 d165ee6 逐字节一致）补齐 SKILL.md 实际引用的缺失资产——examples/ieee-twocolumn{,-p1,-p2}.png（3 张 IEEE 预览图）、.chktexrc、setup.sh、requirements.txt（后二者与既有 scripts/install_deps.sh 配套，宿主中立）；其中 ieee-twocolumn.png 与 ieee-twocolumn-p1.png 为上游同内容双名件，已登记 data/duplicate_assets_registry.json。examples/ieee-twocolumn-sample.tex 经全量比对证实上游从无此文件，仍留 ASSET-GAP。上游 5 个 references 与 3 个 scripts 的既有本地差异（beamer-guide/debugging-guide/font-guide/python-charts/tables-and-images、graphviz_to_pdf/latex_wordcount/plantuml_to_pdf）为本仓内容纠错与中性化成果，优于上游旧文本，未回退。
- 2026-11-18 examples 全量对齐批：examples/ieee-twocolumn-sample.tex 为本仓自写样例（上游从无 .tex 样例，按 ASSET-GAP 处置口径"本仓自写样例"路径销账），按 SKILL.md 正文描述实现 journal,10pt + abstract/keywords/单栏图/单栏表/跨栏表*/数字参考文献，并对齐 ieee-journal-twocolumn-guide.md 版式规则（无 geometry、[!t] 浮动、\columnwidth/\textwidth 分工、hidelinks），pdfLaTeX 冒烟编译通过；3 张预览 PNG 仍为 fork 快照原件（md5 已核对一致）。上游其余 78 张模板预览 PNG 未收编——本仓口径为"正文实际引用才随仓"，SKILL.md 未引用这些预览，避免无引用二进制膨胀。
