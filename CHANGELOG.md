# Changelog

本项目所有显著变更记录于此，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循语义化版本。更早的分节操作日志存于项目内部文档（2026-09-23 起移出公开仓，不随仓库分发）。

## [Unreleased]

> 2026-10-01 四窗批（W1-REG 规范真源 / W2-CORPUS 语料 / W3-WRITE 写作链 / W4-FIG 图表真源）、comp_rules 规则审计修复批（三轮工作流）、W3 写作链工作流轮与 W5-GOV 终局治理（两轮）、2026-10-02 反形式主义+内容级合同批（闸门空转修复/写作层治本/合同升级）、2026-10-05 对抗扫描批（死闸接线/SKIP 语义统一/格式五修/AI 味三修）、2026-10-09~11 三轨遗留治理批（弱判据收紧/docx 格式补齐/三赛事官方取证）、2026-10-16 仿真建模赛能力补齐批（CSF 赛事档案与 9 步管线 / comp-simulation 主链 / 七技能收编）、2026-10-23 六窗收口批（W1 终审评分 / W2 建模选型与发现账本 / W3 写作上下文预算 / W4 图表惯例 / W5 一致性加固 / W6 基线与终检工具链）、2026-10-23 整仓升级四批执行批（诊断→裁决→22 工并行执行：评分卡前移/写作分片/出图收敛/方法落地卡/短链补尾/冷存与清理）；逐批操作细录见内部 LOG（不分发）。
### Added

- **2026-10-23 整仓升级四批执行批**（诊断→用户裁决→四批并行执行，工作流 22 工 + templates.json 顺序链 + 全量回归闸）：依据内部《整仓升级诊断报告》（54 条发现、9 条历史结论核验）与用户 8 项裁决落地——
  - **得分导向**：九维评分卡前移到第 8 步（初稿产出 scores/weighted_total/失分清单，每维必须引用正文/图/表位置）→ `comp-editor` 按失分清单改稿（新增 PAPER_SCORING.json 输入契约与失分→改稿动作映射）→ 第 13 步 `comp-final-review` 改为复核各维分数与失分段落闭环（保留 fatal 与合规终审）；`comp-review` 判据扩第 7 类（创新点/基线对比/验证强度，对应 0.30 权重），fix 字段强制写入"需补 baseline/验证"；`contest-retrospective` 输入契约补四份评审 verdict，§6 回灌表按 finding.category 落到章节清单/方法表/选图规范。
  - **创新链落地**：`tools/novelty_checker.py` 评分单调化（命中越多分越低、0 命中输出"未知，需人工/语料比对"），删除"可作为卖点"越界结论；新建 `tools/build_method_frequency.py` 生成 `data/method_frequency.json`（26 类方法/457 篇/按年份·题号频次）；`comp-model-innovation` 以建模步资产形式接入 comp_cumcm/comp_huawei。
  - **写作减负**：`comp-paper-zh` Workflow 11 步外移 `references/step_*.md`（主干 107,783 B→26,415 B；单步开工峰值 173,652 B→64,008 B，约 −63%），`writing_rules.md` 按 `<section>` tag 取段不再整篇 cat，三处重复 \upcite 解释合并为一张引用命令真源表。
  - **出图统一**：5 段 3D 配方（competition #6/#19/#27、academic #8/#11）删 `tight_layout()` 改 constrained 布局、figsize 按档收窄、字号交回 `academic.mplstyle`；`get_recipe.py` 单段抽取附文件头"必读"要点（双树锁步）；`plot-from-data` 8 个模板脚本改薄壳（统一 `_utils.plot_utils`，删自写 rcParams/fontsize/bbox_inches）；`figure-craft/figstyle.py` 收敛为可选叠加层、默认回落 mplstyle 基线，质感函数并入 plot_utils；`eco-community-plots` 新增 `scripts/_eco_style.R` 单一真源（CJK 字体回退链 + 按印刷公式折算的 base_size/mm 阶梯 + Okabe-Ito 语义色板），6 个 R 脚本全部接入。
  - **方法深度**：`method-map.md` 72→575 行，新增 F1–F12 十二张方法落地卡（适用规模阈值→求解器与关键参数→可直接粘贴的最小代码→3 条已知坑），12 段代码实跑与文档示例输出逐字符一致。
  - **竞赛链补齐**：21 条短 comp_* 链复用长链 6 个收口步骤（comp-literature/comp-consistency/comp-visual-review/comp-editor/comp-final-review/comp-final-audit），终检从"PDF≥100KB"升到与国赛同口径（[literature, review, consistency, final_audit]）；`quality-check` 从 23 个模板终审 mandatory 降级为可选 companion（LaTeX 分支与 consistency/compile 重复且无竞赛口径）；`dev-adversarial-code-review` 确认零挂载。
  - **工程卫生**：清理 untracked 残留 ~62.8 MiB（laya `_tmp*`、smoke JSON/日志、pytest 缓存等，明细见内部 DELETION_LOG）；laya_cmf 4 个实验原始 JSON（B1/B1b/B3b_v2/B4_multi，合计 1,578,973,393 B ≈ 1.47 GiB）移出仓外冷存（sha256 逐位保留、§11 哈希清单不动），新建 `audit_pack.json`（11.3 MB，含 _D/_E 数组 + verdict 子树 + 4 源哈希锚点）接管日常复算，`audit_values_tex.py` 改读 pack 并双校验（61/61 宏实测一致）；`comp_rules.json` 悬空路径（根 workspaces 系用户有意删除）改指现存 realpath；`skill_trigger_audit.py` 的 `route()` 支持按模板可达子集收窄（`--template/--all-templates`），全库回退保留；根 `AGENTS.md` 补 3 行高频意图直达并清除死引用。
  - **小修对齐**：`cumcm/main.tex` 符号表 `[htbp]`→`[H]`；`comp-latex-writing` 三处冲突规则（摘要字数/\tag 编号/[htbp]）对齐主线并加定位声明；`comp-simulation` ABM 骨架 `self.rng.integers` 修实（mesa 3.5.1 跑通，同种子逐位一致）；`case_patterns.md` 占位真题段改指 historical_problems.json、删"瞎猜版"预判段、§1 占比改真源统计；`academic-toolkit/AGENTS.md`/`SECURITY.md`/`CONTEST_SKILL_MAP.md` 路径与计数收口（技能计数统一 262 机检口径）。
  - **基线单源**：`pytest.ini` 权威值更新为实测 **1089 collected**（与 `sync_baselines --check` 全绿一致），`README`/`AGENTS` 传播面由 `tools/sync_baselines.py` 单源维护。
  - 终态实跑 **1089 passed / 0 failed（483.86s）**；`check_provenance` 117/117；`secret_scan --strict` 0 FAIL；`project_health_check --strict` 10/10 PASS、漂移 0。华为杯 15-22 届历史原件移出 contest-regs（23 届现行件保留）。完整清单见内部《整仓升级执行报告》（不分发）。
- **2026-10-23 六窗收口批（W1–W6）**：本批六窗改动已落地（W4 为部分交付），分窗细目见本节下方 W1 / W2 / W3-W4 / W5 / W6 条目。W1 终审九维评分（每维必须给正文/图/表位置，无位置不算证据）与 `session review-evidence` 脚本盖章；W2 每个子问题五列选型锦标赛、`RESULTS.md` 固定发现账本，并将 18/62 张 `status=done` 获奖版面卡投影为 `data/award_layout_cards.json`（`local_only`，公开 clone 不交付）；W3 写作规则按 tag 按需读取、创新点契约两份副本锁步；W4 出图前按 `CONTEST_ID` 读图表惯例（90KB→29KB，-67.7%）；W5 身份字段由引擎回填、`quick_gates` 单跑、分章一致性递归覆盖 `\input/\include`；W6 基线单源（`sync_baselines`）、`final_check`/`safe_cleanup` 工具链，基线 **1089 collected**。**边界**：W4 未改动 `figure_check` 判定规则，按"默认观感不违规、不强制自定义"执行，属部分交付；版面卡余 44 篇、终审评分硬门槛、门禁缓存、单写者租约等列入内部缓议，不在本批。
- **2026-10-16 仿真建模赛能力补齐批（CSF）**（ccb2908 + a2e3a8e + 4c44e91）：新增仿真建模赛档案 `comp_csf`——`engine/modex-core/comp_rules.json` 赛事 22→23，12 条 `verified` 约束（A/B/C 三赛道、四件套=论文/承诺书/支撑材料/仿真视频、仅 PDF 单文件、论文第一页为摘要、源程序入论文附录、承诺书独立成件、命名「题号+队伍号+后缀」如 `ACSF2600001.pdf`/`cns`/`fj`/`fz`、mp4 ≤180s 且 ≥1280x720/≤300MB、匿名、原创性、两段截止），《论文规范》未取证故页数/版式全项缺席不臆测；一手来源快照 `assets-local/contest-regs/csf/`。新管线 `comp_csf`（9 步，含 `comp-simulation` 步）+ 骨架 `comp-paper-zh/_templates/csf/`（ctexart + `csf.sty`）+ 格式真源 `comp-paper-zh/references/csf-official-format.md` + 四件套校验器 `tools/pack_csf_submission.py`。新建仿真主链 `comp-simulation`：方法选型（ABM/DES/SD/连续系统/蒙特卡洛/数据驱动）、五要素规格化与随机性纪律、V&V + 不确定性量化、DOE 与敏感性/稳健性，产物契约 `SIM_MANIFEST.json`，附 `sim_env_probe.py` 环境探测与 `sim_manifest_check.py` 校验器。收编 6 个技能：`simpy`/`pymoo`/`stable-baselines3`/`pymc`/`experimental-design`（vendor pin `36d8f13`，MIT）与 `figure-craft`（增量收编，与 `skills/_utils/` 重复的 9 组不复制第二份）。模板 46→47、技能 255→262；ABM 骨架按 mesa 3.5.1 实跑校准为 `self.rng.integers`。终态实跑 **1066 passed / 0 failed（482.17s）**。
- **华为杯 15-23 届官方规范一手原件库**（`assets-local/contest-regs/huawei/`，8926c8d+860ff10）：历届格式规范/论文模板/使用规定原件 + `index.md` 索引 + 2026-23rd 抓取快照；`engine/modex-core/comp_rules.json` 华为杯口径按一手来源逐条核对升级（约束带 vintage 2026-23rd），`contest_profile.load_entry` 支持单 profile 合成脚本视图。
- **获奖语料三批 735 篇入库**（d980526+d2d5649）：研赛/华为杯 686 篇 + MathorCup 大数据 49 篇（`data/award_paper_exemplars.json` 增 `graduate_contest`/`mathorcup_bigdata` 分型索引，奖项佐证 0 全部如实降级 `award_unverified`）；2022 批版面蒸馏 10 卡 + 目录章节树/定位器 v2；`skills/award-paper-mining/data/figure_table_conventions.md` 研赛图表惯例增量（题注「章-序」主流与国赛跨赛事不同流）。
- **图表风格唯一真源**（b4d96f1+f14545f+5a4a042）：`skills/_utils/academic.mplstyle` 定版（CJK 字体链 + elegant 色板 + 印刷字号，色板择优量化对比在文件头）；`plot_utils.setup_style` 改加载 mplstyle（签名/行为不变）；四系绘图技能（fig-academic/matplotlib/paper-figure/scientific-visualization）收敛为「引用基线+差异项」，正面示范 tab10/默认色环清零；shared-scripts 双副本锁步。
- **W5-GOV 台账登记**：`data/asset_catalog.json` 补登 `contest-regs-corpus`/`figure-table-conventions`/`academic-mplstyle` 三条（45→48）；查重台账补第 715 组。
- **闸门体系接线与 SKIP 语义统一**（2026-10-05 对抗扫描批 2e4c58b，四路对抗扫描坐实后修复）：`figure_narrative` 死闸接线——引擎注册/实现/测试齐全但 templates.json 零引用、SKILL 宣称"引擎强制闸"为假，18 个 comp-paper-zh 步补挂 `figure_narrative`+`ai_flavor`（顶层+metadata 双数组），新增注册闸反向对账测试（孤儿闸/死挂双向防再发生）；`figure_narrative_check` 判据升级为零引用孤儿零容忍（label 存在全文零 `\ref` 即拦，旁有叙述不豁免；真实冻结稿 12→20 孤儿全抓）+ SKIP exit 2；9+1 检查脚本 SKIP-as-pass 统一为 exit 2 明示"不冒充通过"（含 host_visual_review 裸执行保护），双副本 md5 锁步；`ai_tell_check` 无参治理文档哨兵（仓库根拒扫防误报）。**格式五修**：cumcm 骨架删 16 骨架中唯一活 `\tableofcontents`（违反自家 toc:false 基线）；`template_integrity_check` comp_cumcm 内联分支（拔除"老实复制骨架被判 FAIL vs 不要重写 main.tex"两难）；comp-latex-writing 第三套冲突模板改指主线骨架；mcm 队号占位 4→7 位对齐官方；MathorCup TOC 硬断言条件化。**AI 味三修**：`cumcm_section_prompts.json` 摘要"随着…的发展"万能开头具体化；`anti_ai_detector` 删与 `de_ai_writer` 保护表冲突的正当词+权威口径声明；14 个零覆盖写作技能（latex-paper-*×8+paper-writing*×6）补 `writing_rules <de_ai_polish>` 强制指针。
- **三轨遗留治理**（2026-10-09~11 批 762d463，工作流双子智能体执行+换人复核）：论文正文类合同判据收紧——forbidden 补通用占位词（TODO/待补/此处补充/（略），「……」仅摘要专用条目防误拦题面省略号，换人复核曾抓到 $primary 误拦高危已修），赛题分析空判据 require_any 迁移 contains[模型,假设] 全命中，runner output_specs 增 contains 判据（原文精确匹配）；docx 路线格式补齐——`docx_export` 页脚 PAGE 域页码、行距 profile 1.5→1.38 对齐 cumcmthesis.cls、新增 `docx_format_probe` 双层探针（A 层免转换 XML 检查：页码域/身份泄漏/行距；B 层 soffice 在场才转 PDF，缺席诚实 SKIP）+孪生+两 SKILL 收尾硬拦接线（真实 docx 实测抓 3 项 FAIL）；三赛事官方取证入 comp_rules——MathorCup 16 届 14 条（组委会规范 PDF 全文直读）/数维杯 11 届春季赛 7 条（官网公告直读）/中青杯 8 届 3 条（提交通知快照；页数版式未直读保持缺席），快照+MD5 按整区分发裁决入根原件库。全量 1050 passed / 0 failed。
- **W6 基线与终检工具链**（2026-10-23）：`tools/sync_baselines.py`——`--check` 实测 tests/skills/capabilities 并与 `pytest.ini` 单源比对，`--accept` 只重写 `project_health_check.DRIFT_SOURCES` 的第 1 捕获组（命中历史横幅的行整体跳过，原样保留 CRLF，不改 prose）；`tools/final_check.py`——固定从仓库根跑 `pytest -q` / `check_provenance` / `secret_scan --strict`，命令、退出码、耗时、尾 40 行写入 `dev-docs/FINAL_CHECK.json`，任一步非零 exit 1，支持 `--background` / `--status`；`tools/safe_cleanup.py`——显式 allowlist + `git ls-files` 为空 + 工作区内三重核验，默认 dry-run，`--apply` 才删除并追加 `dev-docs/DELETION_LOG.md`；`project_health_check --print-baselines` 一行输出机读基线，`_actual_counts` 复用 `sync_baselines.measure()` 单一实现。
- **W1 终审评分框架**：`comp-final-review` 输入增 `data/paper_selfcheck_287.json` 与九维评分框架，`FINAL_REVIEW_VERDICT.json` 增 `scores` / `weighted_total` / `fatal_dimensions` / `selfcheck_failures`（每维必须给正文/图/表位置，无位置不算证据）；`REVIEW_EXECUTION_EVIDENCE.json` 改由 `workflow_cli session review-evidence` 从工作区真实输出文件计算 hash 并盖章，禁止手算 hash/时间戳。
- **W2 建模选型与发现账本**：`comp-modeling` 每个子问题固定填「baseline / 被拒替代 / 选定路线 / 判别测试 / 翻转条件」五列锦标赛表（缺一列即选型未完成），方法族改查 `method-map.md` 唯一真源；`comp-code` 在 `RESULTS.md` 增固定节 `## 发现账本（FINDINGS）`——六项（baseline vs 选定 / 差值消融 / 灵敏度 / 机理决策含义 / 对下一问约束 / 适用边界）缺一即未完成，数字必须与 `figures/*_results.json` 同源。
- **W3/W4 上下文预算与图表惯例**：`comp-paper-zh` 不再整篇 `cat` 65KB 的 `writing_rules.md`，改按 tag 目录只读本章所需 1-2 节；`paper-figure` 先按 `CONTEST_ID` 读 `figure_table_conventions.md` 第 5/6 节（题注制式、目录页、≥4 问泳道路线图），90KB 风格指南按节读、禁止整篇。
- **W5 一致性加固**：`quality_gates.paper_consistency` 经 `skills/_utils/paper_source_scope.py` 递归展开 `\input/\include`（`\includeonly` 生效），分章正文数字漂移在写作步即被捕获；`workflow_cli` 增 session ticket 五字段校验，并拒绝终审/终审复审使用无持久 collection 的手拼证据。

### Changed

- **comp-paper-zh/SKILL.md 整体瘦身（W-SLIM，"治本不闸门"落地批）**：3039→1883 行（-38%），闸门类标记 391→133，正文回归"教写作"本职。内嵌检查脚本外提为五个 `_utils` 独立工具（`template_integrity_check`/`figure_layout_check`/`page_precheck`/`summarize_results`/`abstract_paragraph_check`，shared-scripts 双副本 md5 锁步，各带最小正反例 pytest）；引擎已等价覆盖的内嵌块（上游存在性 ceremony、图连排检查、溯源 30 采样兜底等）删除并留一行闸感知；Step 4 重复块与"算法伪代码扩写"矛盾条目清除；写作质量指导（六条心法/图表 Rules/优化三要素/四问/丰满模式）零删除。新增 `tests/test_slim_extracted_checks.py`（验收批后 10 测试）。验收批修正：调用行统一三段 cwd 兜底（工具箱根/仓库根/工作区根，原双路径在工作区根形态失效）；`figure_layout_check` 引用匹配支持无扩展名 `\includegraphics` 形态（冻结稿实测 28/31 图此形态，修复前 59 条违约中 56 条假阳）；fingerprint 调用补 `--template-base`（原形态在非技能目录 cwd 下静默跳过）。二次复核批：`figure_layout_check` 扩展名/门槛/判据单位三处对齐——svg 纳入（与 output_contracts 同口径）、PNG 门槛放开、嵌入完整性按逻辑图（stem）去重不因 pdf+png 双格式双计；SKILL.md bash 块逐字抽取执行验证（照抄可跑）。
- **写作链停止生产 AI 套话**（646eedb+a1d7289）：中文套话（值得注意的是/综上所述/不难发现/显而易见/在此基础上/随着…的发展）在 `_utils/ai_tell_check` 升 BANNED 硬拦并新增「随着…的发展」正则；comp-paper-zh(+docx) 六要素正例/摘要自检/骨架教学改因果衔接叙述；接获奖语料对标（动笔前读同赛事 2-3 篇）+ 人类痕迹四问 + 结构多样性纪律；docx 写作链同口径补齐。
- **AI 痕迹词表证据级校准**（053584e）：`ai_tell_check` 按一手证据（AI 论痕检测词库/真实检测报告）增补硬拦词与泄漏构式模式，新增获奖论文正当句式反证白名单；735 篇真实获奖论文全量假阳实测治本——11 个领域字面义词（链路/上下游/复用/工作流等）自词级硬拦收窄为工程泄漏构式、参考文献区豁免、误伤 ≈1968→11（坏探针检出力无损）；docx 链摘要字数契约 400-600→600-800 对齐 `_utils/abstract_writing_contract.md` 真源；`writing_rules` 图注「优先承载发现」口径与旧教学矛盾（enumerate 双口径/教学正例带套话尾巴）清理。
- **图表叙述闸挂进引擎强制链**（同上历遍批复核）：真实终版 20+ 图中 11+ 张"孤儿图"（贴进正文零引用零解读，图海堆砌=图表 AI 味首因，label/ref 对账无一假阳）。新增引擎 `figure_narrative` named gate（孤儿图零容忍——修复动作明确：补引用句/解读段/删图），comp_huawei/comp_cumcm 写作步挂闸；SKILL 图表嵌入规则补闸感知（每图同步写引用句+解读句）。
- **内容级合同扩展至 7 个中文赛事模板**：骨架逐个核验后，apmcm_zh/mathorcup/yangtze/diangong/huashu/shuwei（专用中文内联摘要骨架）挂摘要导航词 contains；huazhong（复用 cumcm 骨架）加 cumcm 同款占位 forbidden；wuyi/dongsansheng/default 摘要非内联不动（防误拦）。teddy 等 6 赛事走档案指定 default/ 通用骨架（既有治理现状）。
- **数模写作步合同升级为内容级**（承接前窗移交项）：`engine/output_contracts.py` 文件检查新增 `forbidden`（未完成占位/违规内容残留，对称 `contains`）；`comp_huawei`/`comp_cumcm` 写作步合同从裸 `min_bytes:5120` 升级——华为杯加摘要导航词「针对问题」+六要素「创新点」contains 与封面/摘要骨架占位 forbidden（新合同对真实终版实测当场抓到封面 5 字段占位残留，min_bytes 级合同对此失明）；国赛同口径。**骨架真源对齐**：cumcm 骨架摘要占位「关于问题一」改「针对问题一」，消除与 `abstract_writing_contract.md`（四套 Skill 单一事实源）的口径冲突；huawei 骨架补导航词与六要素口径。其余 16 赛事模板待骨架逐个核验后升级（不盲改）。
- **AI 痕迹闸挂进引擎强制链**（全仓历遍复核实锤后）：真实工作流执行记录（workflow.sqlite 10 份 evidence）显示写作质量闸（ai_tell_check/writing_check 全家桶等）在生产中零执行——引擎强制闸只卡证据格式、质量闸全靠自觉（"机械过闸"完整图景：强制的不管质量，管质量的不强制）。新增引擎 `ai_flavor` named gate（quality_gates 注册表）+ `ai_tell_check --max-errors` 阈值参数（默认 0 不变；闸定标 3 = 获奖论文抽样 0-2 处/篇的水平上界），comp_huawei/comp_cumcm 写作步 required_checks 挂闸——finish 时强制重扫，超阈值拒绝完成并附行号改写指引。获奖论文对照定标：8 篇抽样 0-2 处/篇 vs 旧终版 12 处（密度差约 10 倍）。
- **`quality-check` SKILL 结构重排**（515 行改写）：常量 / 审查目标 / 九步工作流 / 六类检查分节，LaTeX 分支（`TARGET_KIND=latex`）独立成节，消除同一检查在"流程"与"清单"两处各写一遍的漂移面。
- **provenance 台账口径收紧**：移除 `LOCAL_ONLY_UPSTREAM` 语义 SKIP（`eco-community-plots` 已随仓交付），审计输出不再有 SKIP 计数——117/117 全通过才算过。
- **基线数字单源化**：README（徽章 + 两处基线表）、根 `AGENTS.md`（仓库根/工具箱内两行）、`pytest.ini`、内部 truth-index 的 tests/skills/capabilities 数字统一由 `sync_baselines --accept` 传播；新增两条漂移锚点（README 安装节"口径一"行、AGENTS"工具箱内"行）。
- **本地缓存与失败残留清理**（untracked，2026-10-23）：allowlist 内 35 条路径 / 737 文件 / 59.8MB（`__pycache__`、`.pytest_cache`、`.ruff_cache`、`.coverage`、`figures_stray`、`_tmp` 具名残留、`render_*.png`、一次性 docread 输出），删除前逐路径 `git ls-files` 核验为空；`_tmp/` 根与另一工作区未触碰。终检全量 pytest 会再生缓存，收尾以 `safe_cleanup --apply` 二次清理 11 条 / 225 文件 / 5.16MB（DELETION_LOG 同日第二条），最终 `__pycache__` 计数 0。
- **CLEANUP_PROPOSALS 七项删除执行**（2026-10-23 用户裁决，tracked 五件 + untracked 两组）：五件零引用 tracked 死文件 `git rm`——latex-document `qa-test-report.md`（结论已沉淀进教学）、figure-studio-pro 补丁报告与矢量库校验快照（vendor zip 内固化同批内容）、`example_roadmap_stats_warm.drawio.bak`（原件同目录在用）；`copyright_material_rules.md` 按提案选项②先将《计算机软件著作权登记办法》第十条口径并入 `copyright-draft/SKILL.md` 分页段再删（信息零丢失）；untracked 删 laya_cmf 六件 `*prev*.bak*`（25.7MB，现行 30 件结果完好）与过期快照 `_snapshots/`（10/10 与现行测试 DIFF，git 历史保有同期 tracked 状态）。删除前零引用复核重跑通过，明细见内部 DELETION_LOG。

### Fixed

- **paper-figure Step 1 工作区 cwd 路径断裂**（2026-10-23 终审复核遗留，主控收尾）：W4 新增的赛事惯例/问数计数块只覆盖「仓库根/工具箱根」两种 cwd，在真实工作区（`academic-toolkit/workspaces/<ws>`，`../../skills/` 形态）全部 MISS（复核实测 `count_subproblems.sh` RC=127）；CONV/GUIDE/count 脚本统一补齐与 comp-paper-zh 同口径的多级链，`figure_recipes_*` 五个读取块补齐四级链（含仓库根级）；三种 cwd（仓库根/工具箱根/工作区）实测全部命中，`test_skill_smoke + test_active_skill_contracts + test_context_budget_check` 58 passed。
- **quick_gates 单入口断言同步**（2026-10-23 复核修复）：`test_quick_gates.py::test_step_action_quick_gates_instruction_line` 仍断言 W5 已废弃的「手跑 `quick_gates.py` / 回报 complete 前必跑」，与 `engine/agent_bridge.py` 的 early_quality 单入口文案冲突（统一终检红灯）；断言改为新文案并加两条负向断言防旧文案回流，`agent_bridge.py:37-38` 旧注释同步。
- **AI 痕迹闸门空转修复**（本批）：`_utils/ai_tell_check.py` 目录形态参数（如 SKILL 教学的 `--strict paper/`）此前被「只认文件」过滤整批丢弃——零扫描 exit 2 被当"SKIP 不阻塞"，治理工具从未真正扫过按文档调用的工作区（真实终版实测残留 12 处必修 AI 痕迹）；新增目录递归发现（工作区根/paper 根/sections 均可），同一命令修复后实测从零扫描变为抓到全部 12 处。shared-scripts 双副本锁步（md5 一致）。
- **写作步「检查压倒写作」结构倒挂矫正**：comp-paper-zh Step 4 开头前置六条正面写作心法（段首结论句/数值嵌叙述/图题写发现/因果衔接等，提炼自 `_utils/human_competition_paper_style.md`）；Step 5.5 De-AI polish 从 10 行指针扩为可执行改写卡（定位→按优先级改写→重跑到绿；改写方向=程序验收话改读者视角事实，非同义词替换）。
- **W5-GOV 终局治理**（四窗改动面遗留清零）：W1 遗留 21st 官方模板 1.01MB 字节级重复组补登记（原件库证据件↔技能消费副本职责异构并存，消解 `test_duplicate_assets`/`test_project_health_check` 三挂）；W2 核验报告 `new_corpus_stats_2026-10-01.md` 补入库（修复 `award_paper_exemplars.json` `stats_report` 悬空指针）；全量 pytest **1011 passed / 0 failed** 复跑收口，`check_provenance`/`check_asset_utilization --strict`/`secret_scan --strict`/`project_health_check --strict` 全过。
- **comp_rules 规则审计修复**（c9d8f23）：`field_contract` 悬空指针（MIGRATION.md 从未落库）内联化、`hw-anonymity` 等 source_ids 与人读行对齐等十处；23 届「重要提醒」官方快照归档 `23rd_2026/`（第 24 届离线逐字重验依据）；图表量「硬下限」降格经验参考区间（对齐 guidance 经验层）；华为杯页数经验值 40-50→55-65 标注历届经验口径；AI 双件套在华为杯链改标仓库工程约定（官方=附件4 标注+第6条条件披露）。
- **W5-GOV 第二轮治理**（本批，含 c9d8f23+053584e 改动面遗留）：`comp_rules.json` 19 处「去留见 MIGRATION.md M7」悬空 note 尾巴清除（note 自足化）；`submission_checklist.md` 废除块指针 `comp_huawei.compliance` 改 profiles 约束带；测试幻影文档引用 ×2 自足化；绘图规范收敛外溢残留清零——latex-document `python-charts.md` tab10「colorblind-safe」推荐改 Okabe-Ito + 30 处 `bbox_inches='tight'` 正向教学对齐不裁剪护栏、`visualization`/`networkx`/`plotly`/`seaborn`/`paper-figure-palette recipes` 默认色环与 tight 教学清零（复现域 plot-from-data/image 有出处标注者保留）；`CONTEST_SKILL_MAP.md` 外域行重复 token/过期计数（22→20、7→5）/过期「待合并 W3f 处理中」行修正；award-paper-mining 三库（摘要黄金结构/句式模板库/排版规格）补入 `asset_catalog.json`（48→51）；`typography_spec.md` 过程性注记清除。
- **基线锚点盲区**（2026-10-23 实测）：`README.md` 安装节「口径一（仓库根，回归门禁口径）」行与 `AGENTS.md`「工具箱内」行的基线数字此前不被任何 `DRIFT_SOURCES` 模式命中（逐条 regex 扫描零命中），`sync_baselines --accept` 传播不到、健康检查也对这两行失明；补两条锚点并以 `test_drift_sources_anchor_readme_install_line_and_agents_toolbox_row` 守护。
- **`safe_cleanup` 保护粒度**：初版把 `_tmp/` 整棵子树设为受保护前缀，导致 allowlist 内的具名残留全部被误拒（dry-run 0 条可删）；改为"精确保护 `_tmp/` 根 + 前缀保护 `code/` 与另一工作区"后，按 allowlist 正确匹配 35 条 / 737 文件 / 59.8MB。


## [v2.1.0] - 2026-09-27 —— 赛事档案 v2 隔离（跨赛事规则不再混用）

> 定版范围：2026-09-27 赛事隔离主线（comp_rules v1→v2 + 规则选档接口 + 技能/模板对齐 + 文档基线 1005）。
> tag v2.1.0 已打在 fb87e99（2026-09-27）；GitHub Release notes 待公开发布时补。

### Added

- **`academic-toolkit/engine/modex-core/comp_rules.json` 升级 schema v2 并切生产**（`schema_version=2` / `artifact_status=production`）：22 赛事 · 8 个有效 profile · 51 条约束（36 `verified` + 15 `unknown`）· 15 个无档案赛事（`profiles=[]` + 证据摘要 + 历史备注）。v1 数据留作回滚点。契约测试落位 `tests/test_contest_rule_data.py`。
- **规则选档接口**：`contests[id].profiles[]` 按 `edition` / `submission_form`（必要时 `region` / `stage`）精确选档，`profile_id` + `rules_revision` 随档冻结；逐条约束带 `status` / `value` / `scope` / `source_ids`，`sources` 统一顶层 ID 登记表。多 profile 同 `edition` 时拒绝模糊匹配。
- **`contest_profile.py` v2 解析器** + execution 受控缓存（命令复用资格先判定、受控环境白名单），输出合同与命令环境注入：`CONTEST_ID` / `PAGE_CAP` / `PAGE_SCOPE` / `PAGE_CAP_STATUS` / `EDITION` 由绑定快照注入，智能体不再逐字转录；无口径即 SKIP，不回退默认页数。
- **研赛/华为杯分型入库骨架**（`5b714bd`）：`data/award_paper_exemplars.json` 增 `graduate_contest` 分型（国赛既有 62 篇 / priority_25 / A-E 学习路径一字未动，新容器缺省为空、未编造条目）；`data/cumcm_section_prompts.json` 增 `huawei-cover-identity` / `huawei-abstract` / `huawei-references` / `huawei-format-page` 四板块（字段同构国赛 9 板块，逐条带 `source_level` + `provenance`，经验口径显式标 `internal_empirical`）。
- `comp-paper-zh/_templates/certcup_en/` **独立骨架**（不再复用 mcm 骨架，Summary 独立成页）；`comp-paper-zh/references/huawei-official-format.md` 增下游接线表与来源层级声明。

### Changed

- **竞赛技能正文与模板对齐 v2 档案**（95 文件）：移除共享模板 `quick_gates_max_pages` 默认与旧 `max_pages` 直读，统一 `gate_page_cap` / `scope` / `page_cap_status`；页数语义 `body` / `total` 不折叠；官方 `verified` 与经验/工具建议分离，任务级覆盖仅限当前工作流参数，未知赛事不回落国赛。
- 文档基线统一 **1005 collected**（`README.md` / `AGENTS.md` / `pytest.ini` 同口径，唯一真源 = `pytest.ini` 注释）；lint scope 补 `repo:tests`；技能索引快照重生成；清理废弃脚本（`fix_skill_manifest_placement`、`run_cumcm_e2e`）。

### Fixed

- **跨赛事混用根因修复**：MCM/APMCM 路由精确化（不再模糊命中美赛分支）；单任务页数覆盖不污染其他任务；承诺书 electronic/paper 形态区分；国赛 AI 声明不误入其他赛事；旧工作流不静默迁移合同，无档任务显式待绑定而非按现盘标为历史。
- **P1 假绿修复**：打包承诺书检查静默消失仍报"✅通过" → 改为显式 SKIP；`quality_gates` pending_binding 合规分支 ERROR → 诚实 SKIP；快检无口径不再冒充通过。
- **迁移债收尾**：v1→v2 消费路径测试迁移（`test_active_skill_contracts` / `test_workflow_backfill_stall` / `test_contest_profile_runtime` / `test_g2_package_gmcm` / `test_huawei_pipeline`）；`test_old_task_does_not_drift_when_global_rules_change` 改为 `tmp_path` 副本 + 显式 `rules_file` 传参，不再读写生产真源。
- 双副本一致性：`claim_code_check.py` 两副本字节一致；三族分支 fail-fast。

## [v2.0.0] - 2026-09-23 —— 整仓彻底重构（框架到文件名）

> **破坏性变更**：套件目录更名、技能大面积改名与合并、私有资料区重新布局。公开 clone 与下游引用须按下方迁移指引更新。

### Changed —— 套件目录与分区（v2.0）

- 套件主目录 `科研工具箱/` → **`academic-toolkit/`**（git mv 保 rename；58 文件 1023 处引用字节级替换）。CI 路径、pytest.ini、opencode.json、模板资产指针、zcode hook 契约同步。
- 私有资料区统一 **`assets-local/`**（原根级 `参考论文/` `参考图/` `CUMCM论文模板/` → `award-papers/` `reference-figures/` `cumcm-templates/`；7.6GB PDF 合并版冷归档 `_archive/`）。
- 第三方子项目独立分区 **`third_party/`**（codesucker-core / pubfig / docx-cn-engine / humanize-chinese / docx-style-profiles 自 `tools/` 迁入，下划线名规范 kebab）。
- 上游 fork 暂存 `fork/` → **`vendor/forks/`**（激活 13 处 tracked 契约引用）。
- 引擎运行态三处散落合一：索引/默认库/审计统一写入仓库根 `.engine/`。

### Changed —— 技能命名法（139 件改名 + 9 对真重复合并，264→255）

- 命名法：全小写 ASCII kebab-case；禁宿主/厂商/机构名、批次前缀、事故名、谜语缩写。
- `spine-paper-spine-*`（事故名）→ `spine-*`；`latexpap-*` → `latex-paper-*`；`galaxy-*` 45 件语义化（→ `dev-*`/`meta-*`/`lit-*` 等）；`ars-*`/`nature-*`/`sci-*`/`scholar-*` 去批次前缀。
- 真重复合并（保内容，正文折入主推者 `references/merged-*.md`）：problem-analysis→comp-problem-analysis、model-building→comp-modeling、ars-pr-review-expert→dev-code-review、ars-senior-data-scientist→data-statistics-analyst、ars-academic-pipeline→research-pipeline、galaxy-nature-data→paper-data-availability、galaxy-nature-response→paper-rebuttal-nature、rebuttal-workflow→rebuttal、galaxy-ml-paper-writing→paper-write。

### Added —— 资产激活机制（治"智能体只见 skills"）

- `academic-toolkit/data/asset_catalog.json` 资产台账（非技能资产唯一机器可读目录，含 `when_to_use`/`owner_skills`/`local_only`）。
- boot 契约新增 `paths.data`/`third_party`/`asset_catalog`/`assets_local` 与 `assets` 说明节；probe 输出 `asset_catalog` 摘要；agent-bootstrap 增资产发现步。
- `check_asset_utilization.py` 新增第六类审计"台账↔磁盘↔git tracked 三方对账"；C2 门禁增 `mandatory` 档（历年真题索引试点）。
- 内容融入（闲置资产升级）：287 项提交前自查表 → `data/paper_selfcheck_287.json`（挂最终复审/交付审计步）；范文精选包 → `data/award_paper_exemplars.json`（挂写作步）；CUMCM 9 板块写作提示词 → `data/cumcm_section_prompts.json`；88 色板接入 palette 注册表；05 号 ggraph R 代码入 git；Origin 构图索引入 agent-figure-gallery。
- 新增技能 `award-paper-mining`（获奖论文语料挖掘流水线固化）。

### Changed —— v2.0 收尾强化批（09-23 午后—09-24 晨，tag 补记）

- **pyc 真源码彻底退役**：14 工具真源码自 `.pyc` 反编译重建为 `.py` 入库（行为等价验证 14/14）；删 `pyc_loader.py`；`tools/` 零 `.pyc`（棘轮钉住）——上文 Fixed 节"pyc 即真源码"为退役前的过渡态表述，最终态以本条为准。
- **上游收编口径修订**：原样整采 → **改写融入**；新守卫 `tools/host_dep_scan.py`（六特征词全量扫描 + 豁免登记封闭，登记外零命中棘轮）；R1-R6 批次改写融入收口。
- **GPL 传染解除**：graphviz 技能 clean-room 独立重写（仅以上游主题覆盖清单为事实输入）。
- **审计修复批（2026-09-24）**：技能计数口径修复（Git 默认通配符跨 `/` → `:(glob)` 单级）；tests 漂移容差 2%→0.5%（实证 2% 盲区吞掉基线滞后）；测试拆分（宿主无关模型配置契约迁出 `test_model_config_contract.py`）。
- 基线终态：**773 passed / 3 skipped**（collect 776）· provenance **117/117** · skills **250**（clone 即所见）。

### Fixed

- `tools/` 下 14 个工具的 `.pyc` 是**真源码**（同名 `.py` 仅为 `pyc_loader.py` 生成的薄包装器）——修正 SECURITY/AGENTS 中"以 .py 为真源"的错误表述（该表述会误导删除 pyc 致 14 工具失效）。
- 重命名波期间修正两处工程事故：改名波提交须全仓 `git add`（根级 catalog/README 含引用）；批量替换须用标识符边界正则（避免误伤 `vendor/forks/editaplot` 等上游实体名）。

### 迁移指引

- 下游引用 `科研工具箱/` → `academic-toolkit/`；`fork/` → `vendor/forks/`；根级 `参考论文/` 等 → `assets-local/` 对应子目录。
- 旧技能名可用 `academic-toolkit/data/skill_rename_map.json`（renames + merges 全量映射，2026-09-27 起随公开仓分发）反查新名。
- 本机 ZCode 用户重建 skills 联结：`cmd /c mklink /J .zcode\skills academic-toolkit\skills`。

## [v1.3.0] - 2026-09-22

> 定版范围：2026-09-19 系统性升级五项 → 2026-09-20 基线基础设施加固 → 宿主无关自适应泛化 → L8-L12 遗留裁决落地 → 第五轮四批次并行升级。
> 设计文档：三件 dated 快照（peer-project-fusion-assessment / baseline-infrastructure-hardening / host-agnostic-adaptive-agent）已于 2026-09-23 随 `docs/superpowers/` 移出仓库，git 历史可溯。

### Added —— 宿主无关 · 自适应 Agent 泛化（2026-09-20）

- **引擎深度重构**：新增 `engine/agent_bridge.py`（canonical，`opencode_bridge.py` 降为兼容 shim）；默认 agent 标签 → `acat-agent`（evidence.agent 为自由字符串）；`quality_gates` 模型解析链泛化（contest_models → `agents/adapters/*/models.json` → 可选宿主目录；显式 env 覆盖时不扫默认宿主）。
- **驱动协议 + 自适应铸造**：`engine/agent_protocol.py` / `capability_probe.py` / `tool_forge.py`；CLI 新增 `boot` / `probe` / `forge`（三者惰性加载重型依赖，最小环境可跑）。
- **旧宿主降为可选适配器**：`agents/adapters/{generic,opencode,zcode,claude-code,mimocode}`；无适配器时协议与 L2/L3 审计完整可用，L1 如实 `unavailable`（不阻断、不伪造通过）。
- **文档与技能**：根/工具箱 AGENTS.md、README、skills/CLAUDE.md 宿主中立化；新增技能 `agent-bootstrap`、`tool-forge`（catalog `agent_runtime` 域 + CONTEST_SKILL_MAP §四 + skill index）。
- **收尾整理**：清项目内 `__pycache__`/`.pytest_cache`/`workflow-index.json` 运行态（保留 `.engine` 审计与 SQLite、`tools/*.pyc` 分发件）；galaxy-* 与 meta-doc-governance 过期宿主措辞同步。

### Added —— 基线基础设施加固（2026-09-20）

前三轮升级补完技能层机制后，本轮补工程基座盲区（608 个 .py 此前零 lint、零安全扫描、8 工具零测试）：

- **`tools/secret_scan.py` 密钥与路径卫生门禁**（吸收 gitleaks 高精度正则 + CI 纵深思路，自建保持自包含）：tracked 面 9 类凭证模式 + 硬性规则 6 机检化（配置绝对路径 FAIL / 文档家目录 WARN / 历史横幅豁免）；豁免台账逐行 sha256 锚定且必须有理由。**首跑即抓到存量违例**（tracked 文档写 `C:\Users\...` 本机绝对路径，已修为可移植写法）。新增 `SECURITY.md`。
- **`tools/lint_ratchet.py` lint 棘轮**（吸收 NVIDIA tensorrt-llm baseline-gated 模式，改 per-rule 聚合）：基线锁存 8×F841 只降不升，新增违规即拦、存量下降提示收紧；ruff==0.16.8 锁死保证计数可比。ruff 首扫另修 4 真实缺陷（`run_logger.py` F821 NameError、`academic_cn.py` F601、W605 无效转义、F811 重复导入）+ 80 项安全 autofix，全量 pytest 验证零回归。
- **`tools/check_duplicate_assets.py` 重复资产注册表守护**：tracked ≥4KB 字节级重复组必须登记台账并给理由——**152 组 / 23.0MB 重复显性化**，未登记新组即拦；有意不去重（技能自包含原则）。
- **`tests/test_tool_smoke.py` 工具冒烟闸**（140 工具全量编译 + 11 工具 CLI 契约 + data_init 防覆盖回归）：**探测当场抓到 `data_init.py` 破坏性行为**（`--help` 即执行主逻辑并覆盖 `data/README.md` 回 8 月旧模板，已修复为默认只写缺失文件 + `--force`/`--data-dir`/`--dry-run`）。
- **CI 加固**：`permissions: contents: read` 最小权限、pip 缓存、新增 secret-scan / lint-ratchet / duplicate-assets 三道门禁步；健康检查组件 7 → 10。

### Added —— 系统性升级五项（2026-09-19）

按用户给定的五项优先级顺序执行（LOG 续37-39 三轮全量留痕）：

- **P1 实战经验沉淀（可机检，防"复盘变散文"）**：新增 `科研工具箱/data/contest_lessons.{json,md}` 双真源——9 典型场景（含决策依据）+ 16 踩坑与避坑 + 2 交付硬闸清单，全部源自 CUMCM 2026 A 题真实参赛留痕。核心纪律：每条经验的 `enforced_by` 必须指向仓库内真实存在的强制点，由 `tools/contest_lessons_check.py` 逐条验证在位 + JSON↔MD 双向一致锁死；`tests/test_contest_lessons.py` 15 项。经验库登记为 comp 系模板 step1/step14 资产（22 处）。
- **P2 统一配色方案与模板**：`paper-figure-palette` 升级为多场景配色体系——`assets/palette_registry.json`（5 场景 × 3 类型 × 9 色板 + 禁用清单）+ 三步选色法/10 条规范；`palette_kit.py registry-verify` 机检（色值/顺序单调性/CVD 契约/场景交叉一致）。诚实分类：实测「夏日海滩」CVD 最近色对 ΔE=1.7，登记为 `secondary_encoding`（必须叠加墨色描边+线型+直接标签），不假装通过色盲检查。`tests/test_palette_registry.py` 18 项。
- **P3 技能覆盖与调用准确性**：新增 `tools/skill_trigger_audit.py`（frontmatter 合规 / 触发信号 / 路由歧义检测 Jaccard≥0.30 且共词≥6 / 能力目录对账）。定位并修复 5 对未声明判别说明的歧义技能 + 补齐 7 个"可达但无触发信号"技能；新增技能 `contest-retrospective`（赛后复盘与经验沉淀，技能 260→261、能力目录 307→308，均为当时口径）。
- **P4 工作流强制绑定 skill_binding（可验证）**：步骤级 `metadata.skill_binding` 全库 **279 步全部声明**——`main_required` 要求主技能契约留真实读取痕迹（只填 `skill_sha256` 不再算数）、`mandatory` 技能不得 skipped 且须有命令级痕迹。三层保障：执行层硬校验（`complete_step`）+ 审计层 L1↔L3 交叉核验（缺席如实判 `unavailable`，不伪造通过）+ 指令层 `StepAction` 渲染。向后兼容：未声明绑定的步骤零行为变化。`tests/test_skill_binding.py` 17 项。
- **P5 同类项目批判式融合（三轮）**：
  - 第一轮：反合理化表（本项目事故实证版 12 条，挂 step7/13/14 资产）、退出判据扩展（`output_specs` 2 步 → 9 步，关键字由真实产物实测推导）、SKILL GATE 换承载层（L1↔L3 交叉核验，理由：工作单元是步骤不是 commit、git hook 可绕过、与 fail-open 铁律冲突）；明确不采纳退役编排层与阻塞式审稿门禁（与"没证据＝未执行"的产品差异点冲突）。
  - 第二轮（直取上游真实产物）：`tools/context_budget_check.py` 常驻上下文预算（62,000 字符棘轮）；`tools/project_health_check.py` 统一健康检查 + 文档漂移检测（比对权威文档基线并豁免历史横幅）；退出判据 + 岗位级反合理化下沉 SKILL.md；词法路由回归（IDF 二次排序 + `KNOWN_LEXICAL_LIMITS` 清单制）；命名原则表（TOOL_GAP/三振升级/决策点≠批准/无证据＝未执行）。**机制当场抓到四个真问题**：常驻税 87,334 字符 ≈ 200K 的 19.8% → 53 条描述瘦身 18%；漂移检测抓到 527→576 文档漂移；"编译中文论文"误命中英文版；判别句会反噬（为说明边界引入对手词汇反被命中）。
  - 第三轮：技能分层常驻（核心 52 完整 + 按需压缩 ≤120 字符，完整原文无损存进路由索引；常驻税 17.1% → **10.5%**，路由关键集防作弊）；路由二次排序（IDF 加权，修掉 `paper-plan-zh` 词法黑洞）；`mandatory` 扩至 5/14 步。新增 `tools/build_skill_index.py` + `tests/test_skill_tiering.py` 23 项。

### Changed —— L8-L12 遗留裁决落地（2026-09-20，用户"按推荐执行"）

- **L9 死代码复核（推翻普查初判）**：4 件（analyze_latex_template / derive_profile / markdown_utils / generate_format_reference）均有同名 `.pyc` 分发件=真源契约；codesucker_end_to_end_demo 为有意改名留痕。**零删除**，spec 改记"已复核非死代码"。
- **L10/L11 不立项**：quality_gates / scholar_fetch 拆分改"触碰时顺手拆"约定；mypy 触发条件定为 engine 打包时。
- **L12 归档移出**：asset-ledger 3 文件（4.63MB）零丢失归档 `dev-docs/archive/asset-ledger-20260813/`（sha256 manifest + 逐字节比对全过），`git rm` + 4 处活文档引用改指归档路径 + 6 处 dated 快照按铁律保留原文。
- **L8 待用户操作**：GitHub Settings → Code security 开启 Secret scanning + Push protection（AI 不可代开 web 设置）。

### Added —— 第五轮四批次并行升级（2026-09-22）

四窗口（wt/batch1..4）并行作业、主窗 `merge --no-ff` 收编；具体增量以各批次报告与收编后口径为准：

- **batch1 缺陷快修（9 项）**：恒真断言、反 AI 检测器基线加载链与退出码契约、case_fetcher 统计自洽、个人路径占位化（4 文件）、secret_scan 文档家目录 WARN→FAIL、lint 基线相对路径、gpt_image 第三方域名去硬编码、arxiv_miner 隐式依赖与空元素、plotting_env_check `--strict`。
- **batch2 公开面与口径（本节所属）**：CHANGELOG 定版 v1.3.0（本文件重排）、真源指针公开侧改写、技能计数双轨（tracked/盘面）、`科研工具箱/baseline/` 吞件陷阱修复、快速开始补依赖安装步、LICENSE 与历史引用本地性修正。
- **batch3 机制补强（九项）**：RunLogger 落盘链路接通、workflow-index 原子写与回退、CLI 错误契约 + `--evidence-file`、catalog 双向校验 + 补齐、`--help` 契约扩容、断链棘轮盲区四类、适配器三方对账、门禁互检去重、17 工具零覆盖分档。
- **batch4 产品能力**：管线模板 `academic_outputs`（poster→slides）与 `course_teaching`、写论文/审稿循环/文献三簇仲裁表、§三路由表扩容、auto_review 模板 required_checks 补齐、索引再生成。

### 测试口径（定版时点）

- 仓库根 `pytest -q` **639 passed / 0 failed**（= 工具箱 **620** + 根级门禁 **19**，2026-09-20 宿主无关改造轮实测）；同日基线加固轮 **628 = 609 + 19**。演进轨迹：463 → 527 → 576 → 603 → 628 → 639。
- 六项收口验证全过：provenance **66/66**、`skill_library_audit` OK、经验库机检 OK、触发条件审计 OK、配色注册表 ALL PASS、`upgrade_templates` 幂等 changed_steps=0；secret_scan 全绿。
- 公开 clone / CI 口径以 CI 实测为准（2026-09-19 run 35425878920：600 passed + 3 skipped）；**唯一真源 = `pytest.ini` 注释**。

## [v1.2.2] - 2026-09-09 —— ZCode 赛时主控 + 模型去预设（用户裁定）

- **模型不预设（全链落地）**：新增 `engine/modex-core/contest_models.json` 配置槽（出厂四角色全空）；`quality_gates.load_configured_role_models` 改宿主中立三级解析（ACAT_CONTEST_MODELS > 配置槽 > OpenCode agents，逐角色回退）并新增 `model_config_provenance()`；strict 门禁在两处皆空时降级 warn（显式留痕不静默）。工具层去预设：`doc_reader`（原默认 agnes-2.5-flash）、`tikz_vision_check`（原默认 gpt-4o）改为未配置即明确报错；`pyc_loader` auth 查找不再硬编码厂商名（动态发现 provider 优先+全量遍历）；`comp-visual-review`/`infographics`/`scientific-schematics` SKILL 与 README/AGENTS 措辞改为"比赛时配置，仓库不预设"（例：任一具备视觉能力的模型）。
- **ZCode 升格赛时主控宿主**：L1 拦截式审计 hook 等价实现 `科研工具箱/hooks/zcode_audit_l1.py`（PreToolUse/PostToolUse/PostToolUseFailure → 与 OpenCode 插件同格式的 `operations.jsonl`；`git add .` 级治理拦截 exit 2；异常静默绝不打断会话）；`.zcode/config.json` 注册 hooks（enabled + 三事件，随仓库分发）。审计降级句（"ZCode 仅 L2+L3"）全库清除，宿主矩阵/三层审计表/独立性契约测试同步演化。
- **赛前自检入库**：`tools/contest_dryrun/`（14 步全链驱动 + 终审真实模型探针，2026-09-09 审计驱动通用化入库：路径参数化、fig 自生成、终审端点 env 三级解析不预设厂商）。
- **残留修复**：README `28/28` 过期数字 → 63/63。
- **测试**：新增 `tests/test_zcode_host_compat.py` 12 项（三级解析/strict 联动/hook 五态/注册契约）；基线 工具箱 **259** / 仓库根 **303**。

## [v1.2.1] - 2026-09-09 —— 独立审计全量修复

无上下文独立审计（`dev-docs/INDEPENDENT_AUDIT_REPORT_2026-09-09.md`，内部文档）发现项全量修复：

- **P0 国赛三线表编译中断**：`cumcmthesis.cls` 包序修复（booktabs 移至 bigstrut/bigdelim 之后），SKILL 教授的 `\toprule/\midrule` 与 longtable `\endfirsthead` 格式实测编译通过；补入编译验证的 `_templates/cumcm/main.tex` 骨架；UPSTREAM.md 登记本地补丁。
- **P1 编译门禁盲区**：`compile_check.sh` 新增 `^! ` LaTeX 硬错误检测与真实 undefined-reference 判据（旧 `\[?\]` 恒 0）；"修前放行的断表工程"现 exit 1 拦截。
- **P1 引擎检查点非硬闸**：`workflow_runner.next_action` 新增 blocked-checkpoint 拦截（未 approve 不得推进），回归测试正反两路。
- **P1 模板死声称**：comp-paper-zh 5 套模板声称改为现状如实口径；华中杯分支复用 cumcm 模板；comp-compile-zh 8 条死路径模板对比循环改动态探测+显式跳过。
- **P1 机检前缀盲区**：`skill_library_audit` 内部引用检测扩展 `_utils/`、`shared-scripts/` 前缀；全库暴露 17 处真断链全部修复或内联声明（含 dev-selfcheck/paper-figure 系列；`.pyc` 直调教学全部纠正为 `.py` 真源 + 防回归测试）。
- **P2 双副本漂移**：`claim_code_check.py` 同步；新增 `test_dual_copy_consistency`（hash 级机器防线，注入破坏反验）。
- **P2 mermaid -p 缺失**：可执行命令模板补 `-p` 配置探测；实测裸跑失败→带配置成功。
- **P3 graphviz/环境**：Windows dot 检索指引入技能；provenance 收紧（URL 源强制 7-40 位哈希 Pinned commit，正反测试）；`quality_gates.check_review_evidence` reason 优先级 bug 修复（真因不再被警告文案遮蔽）。
- **验证**：工具箱 247 / 仓库根 291 全绿；两机检 exit 0；CUMCM 14 步全链驱动 0-11 步通过（含 blocked 硬闸 4 次 approve、step9 真实编译、终审由 sensenova/deepseek-v4-flash 真实执行 fatal=0）；step12 strict 门禁在 ZCode 宿主**正确拒绝**（mimo-v2.5-free 配置通道当前环境 503/404 不可达，不可伪造模型证据）；step13 final-audit 独立验证全绿。

> 历史条目保持原样（dated 快照仅供追溯）：以下 v1.2.0 一节中的 242/28/245 为发布时数字，现值见 v1.3.0 节与 README 徽章。

## [v1.2.0] - 2026-08-30

> 发布日期：2026-08-30
> 宿主：OpenCode Desktop + ZCode（双宿主）
> 变更基线：v1.1.0..HEAD（13 commits）

### 范围（三大主题）

#### 1. 科研绘图能力域：C1-C6 全闭环（首个全验收域）

- **设计哲学式集成**（非技能堆放）：引擎模板 `scientific_plotting`（5 步含独立评审门禁）+ 逐技能 C1 合同（13 字段）+ C2 引擎驱动真实验收（SVG/PNG300dpi/溯源 JSON 全真实产物，6 次门禁拒绝留档）
- **C3 公开基准** `benchmarks/six_domains_public/FIGURES-01`（evaluate.py 8 类机检）；**C4 私有基准**（62 篇获奖论文实证样式规范）；**C5 四维指标**（质量/可靠/效率/成本，0 外部 API）
- **本地运行时就绪**：Graphviz 16 + mermaid-cli（Edge 渲染）实渲染验收；`tools/plotting_env_check.py` 一键体检
- **多模态 LLM 专属技能改造**：infographics/scientific-schematics 加 Step 0 生成后端强制检测，禁止占位图冒充
- **技能库常驻审计器** `tools/skill_library_audit.py`（frontmatter/体积/编码/断链/模板一致性五类机检）+ diagram-design（28.3k★ MIT fork）集成

#### 2. 三条学术管线建成并全部 C2 闭环（独立评审 PASS）

| 管线 | 引擎模板 | 独立评审 | 亮点 |
|------|---------|---------|------|
| P1 论文投稿与返修 `paper_submission` | 5 步 | 三轮评审终审 PASS（0/0/2） | 初评抓出 8 major（虚构数据集等）全部整改 |
| P2 深度调研 `deep_research` | 4 步 | 四轮评审 round-4 PASS（0/0/2） | 首轮 5 条编造引用全驳→证据层重建；round-3 E2 PII 经 Crossref 全量比对证伪→权威绑定替换；核验台账重建为 curl 原始输出可复现留档 |
| P3 基金申请 `grant_proposal` | 4 步（第 44 个模板） | round-1 一次过 PASS（0/0/3） | NSFC 青年草稿；证据层继承 P2 已核验集合零新增引用；PI 信息全部显式占位禁止编造；future-work 口径 |

- 防编造体系实测有效：引用必须可点开核验、used_in 章节级回链、推断显式标注、"首次/最优"断言禁用、subagent_session 审核独立视角门禁

#### 3. 基础设施与治理

- **技能名冲突修复**：113 个 frontmatter name ≠ 目录名归一（宿主扫描遮蔽根因），跨作用域冲突 11→2（余为用户级设计内）
- 5 条 minor（P2×2 + P3×3）措辞级修复并经 16 项逻辑校验（2026-08-30，按用户裁定不重放工作流，修正记录留档）
- README 全面重写（徽章墙/mermaid 架构图/提示框/折叠面板/双宿主快速开始）

### 验收基线

- pytest **242 passed**（figures 域 4 项 + 冲突回归 1 项 + P1/P2 管线 4 项 + P3 管线 4 项新增）
- provenance 台账 28/28；skill audit OK（245 技能 / 44 模板 / template_missing_skill=0）
- catalog **281 条能力**（正式 10 / experimental 271；发布≠转正式，未验收能力保持 experimental）

### 已知限制

- P1/P2/P3 的 C3/C4 基准未建（figures 是目前唯一 C1-C6 全闭环域）；5 条 minor 修复未重放工作流（用户裁定，差异措辞级）
- 逐技能 C2 覆盖率有限，未验收能力保持 experimental
- ars-grants（NIH 专属）依赖外部 MCP，保持 experimental

### 许可

- 核心（套件/配置）：CC-BY-NC-4.0（含禁 AI 训练附加条款）
- 公开基准集：CC-BY-4.0（该基准集已于 2026-09-19 废弃入库，归档于内部区，不再随仓库分发）

## [v1.1.0] - 2026-08-28

### Added

- 科研绘图扩展：集成 9 个上游技能（scientific-visualization / matplotlib / seaborn / plotly / figure-spec / graphviz / excalidraw-diagram / infographics / scientific-schematics），catalog 新增 `scientific_plotting_expanded` 能力
- ZCode 兼容层：根 AGENTS.md（宿主支持矩阵）、`.zcode/config.json`（docsearch MCP）、`.zcode/skills` 技能联结、`/doc-governance` 命令与 `meta-doc-governance` 治理技能
- 全学术定位：主套件目录更名 `科研工具箱/`（原 数学建模全流程套件/），文档定位统一为 6 大能力域科研工具箱

### Changed

- **发布边界（用户裁定 2026-08-28）：项目所有能力公开发布**——9 项 private_extension（软著 copyright-draft/build、专利 patent-draft/build、基金 grants 等）转为 experimental，不再设私有扩展边界；验收状态保持如实（未跑 C2-C5 者仍为实验性，正式仍为 10 项）
- 文档治理：45+ 份文档全文审计，17 份过期快照加"仅供追溯"横幅，修正许可矛盾（MIT→CC-BY-NC-4.0）与多处漂移数字；溯源台账扩至 26 条

## [v1.0.0] - 2026-08-17

> 宿主：OpenCode Desktop（唯一正式支持宿主）
> 发布包：本地 dated 快照 `releases/v1/`（gitignored，不入库）；历史发布参见 [GitHub Releases](https://github.com/FOURTEEN1416/academic-agent-toolkit/releases)

### 范围

六大领域 33 个聚合能力（225 个公开技能映射）：

| 域 | 能力 | 状态 |
|----|------|------|
| 数模竞赛 | comp_cumcm_full_pipeline / comp_problem_analysis / comp_modeling / comp_code_solve / comp_paper_zh / comp_review_visual / comp_final_audit / comp_mcm_icm / comp_consistency / comp_literature | **正式**（10） |
| 数模竞赛 | comp_stats_topic | experimental（数据获取证据待补） |
| 学术论文 / 文献研究 / 课程材料 / 知识产权 / 图表文档 | 22 个聚合能力 | experimental（C1+C2 已验，C3/C4 基准待建） |

### 正式能力验收依据（design §7）

- C1 合同完整：33/33（13 字段，0 缺失）
- C2 真实验收：公开基准 P01-P03 + 私有 2025B + 14 步 workflow 流程级验收
- C3/C4 双层基准：公开（合成题）+ 私有（真实题面）端到端通过
- C5 四类指标：多智能体独立评审校准（≥4/5 质量、≥90% 成功率、≥95% 证据完整率、≤15min 效率、≤15 credits 成本）
- C6 回归：204 tests passing（源仓库）+ 发布包 200 tests（160+3skip 套件 + 37+3skip 基准）
- 防伪造机制：requires_subagent + 命令真实性 + review full 模式 + manifest 哈希

### 关键机制

- 三层审计（L1 拦截式 plugin / L2 编排式 runner / L3 申报式 evidence）+ 防绕过检测
- 检查点审批原子事务；质量门禁（大小/伴随/页数/图表/审稿）
- 多角色审稿闭环（executor/reviewer/editor，独立视角强制）

### 许可

- 核心（套件/配置）：CC-BY-NC-4.0（与 LICENSE 文件一致；原记录 MIT 系笔误，2026-08-28 治理修正）
- 公开基准集：CC-BY-4.0（已于 2026-09-19 废弃入库）
- 私有扩展/真实题面/内部文档：不随包分发

### 已知限制

- 私有扩展能力（专利/软著/基金等 9 条）不在此包，需单独申请（后于 v1.1.0 全量公开发布）
- 跨域能力（论文/文献/课程等 22 个）仅 C1+C2 验收，基准待建，状态 experimental
- **C5 校准已定稿（2026-08-17）**：放弃人工专家复核——多智能体独立评审（2 评审者共识）为最终校准，理由：基于全部真实观测、独立评审一致、保守取值、session 可追溯（见 CALIBRATION.md 方法变更声明）
- 视觉审查依赖视觉 API（不可用时如实记录 unavailable）

### 变更历史

- 2026-08-17：v1.0.0 发布包组装完成（净化：剔除 .env/sqlite/私有技能/私有模板；适配：私有基准与宿主配置测试跳过）
- 2026-08-17：发布前最终复核完成——C5 放弃人工复核定稿；catalog 合规修正强制（10 正式）；全量回归源 214 + 包 200；边界安全扫描无残留；合规修正曾被覆盖后重新强制执行（根因：后续 catalog 重写操作），现已锁定不再变更
