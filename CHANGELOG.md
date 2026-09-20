# v1.2.0 发布说明（CHANGELOG）

## 未发布（2026-09-20）—— 宿主无关 · 自适应 Agent 泛化 + 仓库收尾整理

设计：`docs/superpowers/specs/2026-09-20-host-agnostic-adaptive-agent.md`。
目标：不依赖特定宿主；任意能读文件、跑 Python CLI 的智能体皆可驱动，并可通过能力探测 + 工具铸造自适应补能力。

- **引擎深度重构**：新增 `engine/agent_bridge.py`（canonical，`opencode_bridge.py` 降为兼容 shim）；默认 agent 标签 → `acat-agent`（evidence.agent 为自由字符串）；`quality_gates` 模型解析链泛化（contest_models → `agents/adapters/*/models.json` → 可选宿主目录；显式 env 覆盖时不扫默认宿主）。
- **驱动协议 + 自适应铸造**：`engine/agent_protocol.py` / `capability_probe.py` / `tool_forge.py`；CLI 新增 `boot` / `probe` / `forge`（三者惰性加载重型依赖，最小环境可跑）。
- **旧宿主降为可选适配器**：`agents/adapters/{generic,opencode,zcode,claude-code,mimocode}`；无适配器时协议与 L2/L3 完整可用，L1 如实 `unavailable`。
- **文档与技能**：根/工具箱 AGENTS.md、README、skills/CLAUDE.md 宿主中立化；新增技能 `agent-bootstrap`、`tool-forge`（catalog `agent_runtime` 域 + CONTEST_SKILL_MAP §四 + skill index）。
- **收尾整理**：清项目内 `__pycache__`/`.pytest_cache`/`workflow-index.json` 运行态（保留 `.engine` 审计与 SQLite、`tools/*.pyc` 分发件）；galaxy-* 与 acat-doc-governance 过期宿主措辞同步。
- **测试**：仓库根 `pytest -q` **639 passed / 0 failed**（= 工具箱 **620** + 根级门禁 **19**）；health check / provenance 66/66 / secret_scan 全绿。

## 未发布（2026-09-20）—— 基线基础设施加固：lint 棘轮 / 密钥扫描 / 重复资产守护 / 工具冒烟 / CI 加固

前三轮升级补完技能层机制后，本轮补工程基座盲区（608 个 .py 此前零 lint、零安全扫描、8 工具零测试）。
调研溯源与批判式取舍：`docs/superpowers/specs/2026-09-20-baseline-infrastructure-hardening.md`。

- **ruff 引入 + 4 真实缺陷修复**：首次 lint 即抓到 `engine/run_logger.py` F821（`__main__` 块调用尚未定义函数，CLI 必炸 NameError）、`academic_cn.py` F601（字典键重复静默覆盖）、W605 无效转义、F811 重复导入；另 80 项安全 autofix + 4 项手工修，全量 pytest 验证零回归。
- **`tools/secret_scan.py` 密钥与路径卫生门禁**（吸收 gitleaks 高精度正则 + CI 纵深思路，自建保持自包含）：tracked 面 9 类凭证模式 + 硬性规则 6 机检化（配置绝对路径 FAIL / 文档家目录 WARN / 历史横幅豁免）；豁免台账逐行 sha256 锚定且必须有理由。**首跑即抓到存量违例**（tracked 文档写 `C:\Users\...` 本机绝对路径，已修为可移植写法）。新增 `SECURITY.md`。
- **`tools/lint_ratchet.py` lint 棘轮**（吸收 NVIDIA tensorrt-llm baseline-gated 模式，改 per-rule 聚合）：基线锁存 8×F841 只降不升，新增违规即拦、存量下降提示收紧；ruff==0.16.8 锁死保证计数可比。
- **`tools/check_duplicate_assets.py` 重复资产注册表守护**：tracked ≥4KB 字节级重复组必须登记台账并给理由——**152 组 / 23.0MB 重复显性化**（双份 10.56MB 字体、技能族共享脚本等），未登记新组即拦；有意不去重（技能自包含原则）。
- **`tests/test_tool_smoke.py` 工具冒烟闸**（140 工具全量编译 + 11 工具 CLI 契约 + data_init 防覆盖回归）：**探测当场抓到 `data_init.py` 破坏性行为**——`--help` 即执行主逻辑并把 `data/README.md` 覆盖回 8 月旧模板（34 行现行文档被毁，已恢复）；修复为默认只写缺失文件 + `--force`/`--data-dir`/`--dry-run`。
- **CI 加固**：`permissions: contents: read` 最小权限、pip 缓存、新增 secret-scan / lint-ratchet / duplicate-assets 三道门禁步。
- **健康检查组件 7 → 10**；测试基线 603 → **628 passed / 0 failed**（工具箱 609 + 根级 19）。遗留 L8-L12（GitHub 原生 secret scanning 待仓库设置开启、死代码工具处决待裁定、quality_gates 拆分、mypy、governance 台账范围契约）。

## 未发布（2026-09-19）—— 系统性升级：经验沉淀 / 配色标准 / 技能覆盖 / 强制绑定 / 同类项目融合

按用户给定的五项优先级顺序执行，全部改动遵循既有结构与代码风格，逐项过回归。

- **P1 实战经验沉淀（可机检，防"复盘变散文"）**：新增 `科研工具箱/data/contest_lessons.{json,md}` 双真源——9 典型场景（含**决策依据**）+ 16 踩坑与避坑 + 2 交付硬闸清单，全部源自 CUMCM 2026 A 题真实参赛留痕。**核心纪律：每条经验的 `enforced_by` 必须指向仓库内真实存在的强制点**，由新增 `tools/contest_lessons_check.py` 逐条验证在位（含"强制点过度集中"告警）＋ JSON↔MD 双向一致锁死；`tests/test_contest_lessons.py` 15 项。经验库登记为 comp 系模板 step1/step14 资产（22 处）。
- **P2 统一配色方案与模板**：`paper-figure-palette` 升级为**多场景配色体系**——新增 `assets/palette_registry.json`（5 场景 × 3 类型 × 9 色板 + 禁用清单）与 `references/scenarios.md`（三步选色法 / 10 条规范 / 禁用清单），`palette_kit.py` 增 `registry-verify` 机检（色值 / 顺序与发散单调性 / **CVD 契约** / 场景交叉一致）。**诚实分类**：实测本地「夏日海滩」CVD 最近色对 ΔE=1.7，故登记为 `secondary_encoding`（必须叠加墨色描边+线型+直接标签），不假装通过色盲检查。`tests/test_palette_registry.py` 18 项。
- **P3 技能覆盖与调用准确性**：新增 `tools/skill_trigger_audit.py`（frontmatter 合规 / 触发信号 / **路由歧义检测**（Jaccard≥0.30 且共词≥6）/ 能力目录与全库地图对账）。实测定位 5 对未声明判别说明的歧义技能（humanities-write×-latex、paper-compile-zh×paper-write-zh、paper-poster×paper-slides、comp-paper-*-docx、auto-review-loop-llm×minimax）并逐对补判别说明；补齐 7 个"可达但无触发信号"技能。**补齐缺失场景**：新增技能 `contest-retrospective`（赛后复盘与经验沉淀，把"每条教训落强制点"做成可执行流程）→ 技能 260→**261**、能力目录 307→**308**（计数已同步 README/AGENTS/地图）。
- **P4 工作流强制绑定 skill（可验证）**：步骤级 `metadata.skill_binding`（全库 **279 步全部声明**）——`main_required` 要求**主技能契约留真实读取痕迹**（只填 `skill_sha256` 不再算数）、`mandatory` 技能不得 skipped 且须有**命令级**痕迹。三层保障：执行层硬校验（`complete_step`）＋审计层 `audit_store.verify_skill_bindings()` 与 **L1 实际调用对账**（缺席时如实判 `unavailable`，**不伪造通过**）＋指令层 `StepAction` 渲染。向后兼容：未声明绑定的步骤零行为变化。`tests/test_skill_binding.py` 17 项。
- **P5 同类项目批判式融合**：产出 `docs/superpowers/specs/2026-09-19-peer-project-fusion-assessment.md`（6 类对象评判 + 5 条关键取舍理由 + 已落地 6 项 + 明确不采纳 6 项 + 遗留 4 项）。落地融合：①**反合理化表**（融合 agent-skills 做法，改为**本项目事故实证版** 12 条，挂 step7/13/14 资产，双副本同步）；②**退出判据扩展**（`output_specs` 从 2 步 → **9 步**，关键字全部由真实产物实测推导）；③**SKILL GATE 换承载层**（改为 L1↔L3 交叉核验，理由：工作单元是步骤不是 commit、git hook 可 `--no-verify` 绕过、与既有 fail-open 铁律冲突）。明确**不采纳**：退役编排层（与"没证据＝未执行"的产品差异点冲突）、不做阻塞式审稿门禁（与真实证据相反：自审全 PASS 时独立审稿抓出 2 fatal + 1 major）。
- **P5 融合第二轮（用户质询"为什么没有吸收接纳其他项目"后追加）**：第一轮只用二手搜索摘要＝"读过了"未"搬进来"。第二轮直取上游真实产物（raw SKILL.md 原文 / Harness 六组件表 / 门禁设计），新增 **5 个可机检机制**：①`tools/context_budget_check.py` **常驻上下文预算**（六类描述污染判据 + 62,000 字符棘轮上限）；②`tools/project_health_check.py` **统一健康检查 + 文档漂移检测**（7 检查件汇总 PASS/FAIL/**DEGRADED**，比对 5 处权威文档基线并豁免历史横幅）；③**退出判据 + 岗位级反合理化下沉 SKILL.md**（主链 14 技能各补两段，主链名单从 templates.json 自动派生，`skill_trigger_audit` Layer E 机检）；④**词法路由回归**（`--route` 诊断 + 中文 n-gram 词元 + `KNOWN_LEXICAL_LIMITS` 清单制与二分完备性断言）；⑤**命名原则表**（TOOL_GAP / 三振升级 / 决策点≠批准 / 无证据＝未执行，每条须给可 grep 落地位置）。
  **机制当场抓到四个真问题**（融合真实性的判据）：常驻税 87,334 字符 ≈ 39,700 tokens = **200K 的 19.8%**（同行 1.9%）→ 重写 53 条描述瘦身 18%、污染 21→0；漂移检测抓到 527→576 的文档漂移；词法路由发现"编译中文论文"误命中英文版 `paper-compile`；反直觉发现**判别句会反噬**（为说明边界引入对手词汇反而被命中）。自我批判修正第一轮两处判断（反合理化应岗位级下沉；漏掉了 Observability 组件）。详见 `docs/superpowers/specs/2026-09-19-peer-project-fusion-assessment.md` §六。
- **P5 融合第三轮（分层常驻 / 路由二次排序 / 扩大强制绑定）**：①**技能分层常驻**——核心 52 个描述完整、按需 209 个压到 ≤120 字符，完整原文（67,135 字符）无损存进路由索引按需读取；**常驻税 17.1% → 10.5%**（61,224 → 31,510 字符）。防作弊机制：**路由关键集**（被路由回归断言的技能一律不压缩，清单从测试派生）＋**索引必须真被用到**（数据驱动派生翻转案例，派生不出即测试失败）；②**路由二次排序**——`route()` 改 IDF 加权，修掉 `paper-plan-zh` 的"词法黑洞"（短描述高频词对任意中文论文请求抢分）；③**扩大强制绑定**——`mandatory` 从 1 处扩到 5/14 步（图规格/删防御性表达/外部审稿清单/引用与质量终检）。新增 `tools/build_skill_index.py` + `tests/test_skill_tiering.py`（23 项）。修复三个真实缺陷：`--reset-full` 造成原文丢失（加备份安全网 + 收紧保护条件）、IDF 缓存 `id()` 复用串数据（移除缓存）、"只压不补"退化（被新测试抓住）。
- **测试与口径**：仓库根 `pytest -q` **463 → 527 → 576 → 603 passed / 0 failed**（工具箱 557 + 根级门禁 19，加法自洽；两轮新增 113 项 = 第一轮 64 + 第二轮 49）。六项收口验证全过：provenance **66/66**、`skill_library_audit` OK、经验库机检 OK、触发条件审计 OK、配色注册表 ALL PASS、`upgrade_templates` 幂等 **changed_steps=0**、资产指针 **163 条全在位**、地图零漏网（261/261）。公开 clone / CI 口径**待下次 CI 复测**，不预填未实测数字。

## v1.2.2（2026-09-09）—— ZCode 赛时主控 + 模型去预设（用户裁定）

- **模型不预设（全链落地）**：新增 `engine/modex-core/contest_models.json` 配置槽（出厂四角色全空）；`quality_gates.load_configured_role_models` 改宿主中立三级解析（ACAT_CONTEST_MODELS > 配置槽 > OpenCode agents，逐角色回退）并新增 `model_config_provenance()`；strict 门禁在两处皆空时降级 warn（显式留痕不静默）。工具层去预设：`doc_reader`（原默认 agnes-2.5-flash）、`tikz_vision_check`（原默认 gpt-4o）改为未配置即明确报错；`pyc_loader` auth 查找不再硬编码厂商名（动态发现 provider 优先+全量遍历）；`comp-visual-review`/`infographics`/`scientific-schematics` SKILL 与 README/AGENTS 措辞改为"比赛时配置，仓库不预设"（例：任一具备视觉能力的模型）。
- **ZCode 升格赛时主控宿主**：L1 拦截式审计 hook 等价实现 `科研工具箱/hooks/zcode_audit_l1.py`（PreToolUse/PostToolUse/PostToolUseFailure → 与 OpenCode 插件同格式的 `operations.jsonl`；`git add .` 级治理拦截 exit 2；异常静默绝不打断会话）；`.zcode/config.json` 注册 hooks（enabled + 三事件，随仓库分发）。审计降级句（"ZCode 仅 L2+L3"）全库清除，宿主矩阵/三层审计表/独立性契约测试同步演化。
- **赛前自检入库**：`tools/contest_dryrun/`（14 步全链驱动 + 终审真实模型探针，2026-09-09 审计驱动通用化入库：路径参数化、fig 自生成、终审端点 env 三级解析不预设厂商）。
- **残留修复**：README `28/28` 过期数字 → 63/63。
- **测试**：新增 `tests/test_zcode_host_compat.py` 12 项（三级解析/strict 联动/hook 五态/注册契约）；基线 工具箱 **259** / 仓库根 **303**。

## v1.2.1（2026-09-09）—— 独立审计全量修复

无上下文独立审计（`dev-docs/INDEPENDENT_AUDIT_REPORT_2026-09-09.md`）发现项全量修复：

- **P0 国赛三线表编译中断**：`cumcmthesis.cls` 包序修复（booktabs 移至 bigstrut/bigdelim 之后），SKILL 教授的 `\toprule/\midrule` 与 longtable `\endfirsthead` 格式实测编译通过；补入编译验证的 `_templates/cumcm/main.tex` 骨架；UPSTREAM.md 登记本地补丁。
- **P1 编译门禁盲区**：`compile_check.sh` 新增 `^! ` LaTeX 硬错误检测与真实 undefined-reference 判据（旧 `\[?\]` 恒 0）；"修前放行的断表工程"现 exit 1 拦截。
- **P1 引擎检查点非硬闸**：`workflow_runner.next_action` 新增 blocked-checkpoint 拦截（未 approve 不得推进），回归测试正反两路。
- **P1 模板死声称**：comp-paper-zh 5 套模板声称改为现状如实口径；华中杯分支复用 cumcm 模板；comp-compile-zh 8 条死路径模板对比循环改动态探测+显式跳过。
- **P1 机检前缀盲区**：`skill_library_audit` 内部引用检测扩展 `_utils/`、`shared-scripts/` 前缀；全库暴露 17 处真断链全部修复或内联声明（含 dev-selfcheck/paper-figure 系列；`.pyc` 直调教学全部纠正为 `.py` 真源 + 防回归测试）。
- **P2 双副本漂移**：`claim_code_check.py` 同步；新增 `test_dual_copy_consistency`（hash 级机器防线，注入破坏反验）。
- **P2 mermaid -p 缺失**：可执行命令模板补 `-p` 配置探测；实测裸跑失败→带配置成功。
- **P3 graphviz/环境**：Windows dot 检索指引入技能；provenance 收紧（URL 源强制 7-40 位哈希 Pinned commit，正反测试）；`quality_gates.check_review_evidence` reason 优先级 bug 修复（真因不再被警告文案遮蔽）。
- **验证**：工具箱 247 / 仓库根 291 全绿；两机检 exit 0；CUMCM 14 步全链驱动 0-11 步通过（含 blocked 硬闸 4 次 approve、step9 真实编译、终审由 sensenova/deepseek-v4-flash 真实执行 fatal=0）；step12 strict 门禁在 ZCode 宿主**正确拒绝**（mimo-v2.5-free 配置通道当前环境 503/404 不可达，不可伪造模型证据）；step13 final-audit 独立验证全绿。

> 历史条目保持原样（dated 快照仅供追溯）：以下 v1.2.0 一节中的 242/28/245 为发布时数字，现值见上节与 README 徽章。

---

> 发布日期：2026-08-30
> 宿主：OpenCode Desktop + ZCode（双宿主）
> 变更基线：v1.1.0..HEAD（13 commits）

## 范围（三大主题）

### 1. 科研绘图能力域：C1-C6 全闭环（首个全验收域）

- **设计哲学式集成**（非技能堆放）：引擎模板 `scientific_plotting`（5 步含独立评审门禁）+ 逐技能 C1 合同（13 字段）+ C2 引擎驱动真实验收（SVG/PNG300dpi/溯源 JSON 全真实产物，6 次门禁拒绝留档）
- **C3 公开基准** `benchmarks/six_domains_public/FIGURES-01`（evaluate.py 8 类机检）；**C4 私有基准**（62 篇获奖论文实证样式规范）；**C5 四维指标**（质量/可靠/效率/成本，0 外部 API）
- **本地运行时就绪**：Graphviz 16 + mermaid-cli（Edge 渲染）实渲染验收；`tools/plotting_env_check.py` 一键体检
- **多模态 LLM 专属技能改造**：infographics/scientific-schematics 加 Step 0 生成后端强制检测，禁止占位图冒充
- **技能库常驻审计器** `tools/skill_library_audit.py`（frontmatter/体积/编码/断链/模板一致性五类机检）+ diagram-design（28.3k★ MIT fork）集成

### 2. 三条学术管线建成并全部 C2 闭环（独立评审 PASS）

| 管线 | 引擎模板 | 独立评审 | 亮点 |
|------|---------|---------|------|
| P1 论文投稿与返修 `paper_submission` | 5 步 | 三轮评审终审 PASS（0/0/2） | 初评抓出 8 major（虚构数据集等）全部整改 |
| P2 深度调研 `deep_research` | 4 步 | 四轮评审 round-4 PASS（0/0/2） | 首轮 5 条编造引用全驳→证据层重建；round-3 E2 PII 经 Crossref 全量比对证伪→权威绑定替换；核验台账重建为 curl 原始输出可复现留档 |
| P3 基金申请 `grant_proposal` | 4 步（第 44 个模板） | round-1 一次过 PASS（0/0/3） | NSFC 青年草稿；证据层继承 P2 已核验集合零新增引用；PI 信息全部显式占位禁止编造；future-work 口径 |

- 防编造体系实测有效：引用必须可点开核验、used_in 章节级回链、推断显式标注、"首次/最优"断言禁用、subagent_session 审核独立视角门禁

### 3. 基础设施与治理

- **技能名冲突修复**：113 个 frontmatter name ≠ 目录名归一（宿主扫描遮蔽根因），跨作用域冲突 11→2（余为用户级设计内）
- 5 条 minor（P2×2 + P3×3）措辞级修复并经 16 项逻辑校验（2026-08-30，按用户裁定不重放工作流，修正记录留档）
- README 全面重写（徽章墙/mermaid 架构图/提示框/折叠面板/双宿主快速开始）

## 验收基线

- pytest **242 passed**（figures 域 4 项 + 冲突回归 1 项 + P1/P2 管线 4 项 + P3 管线 4 项新增）
- provenance 台账 28/28；skill audit OK（245 技能 / 44 模板 / template_missing_skill=0）
- catalog **281 条能力**（正式 10 / experimental 271；发布≠转正式，未验收能力保持 experimental）

## 已知限制

- P1/P2/P3 的 C3/C4 基准未建（figures 是目前唯一 C1-C6 全闭环域）；5 条 minor 修复未重放工作流（用户裁定，差异措辞级）
- 逐技能 C2 覆盖率有限，未验收能力保持 experimental
- ars-grants（NIH 专属）依赖外部 MCP，保持 experimental

## 许可

- 核心（套件/配置）：CC-BY-NC-4.0（含禁 AI 训练条款）
- 公开基准集：CC-BY-4.0

---

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
- 2026-08-17：发布前最终复核完成——C5 放弃人工复核定稿；catalog 合规修正强制（10 正式）；全量回归源 214 + 包 200；边界安全扫描无残留；合规修正曾被覆盖后重新强制执行（根因：后续 catalog 重写操作），现已锁定不再变更

## [v1.1.0] - 2026-08-28

### Added

- 科研绘图扩展：集成 9 个上游技能（scientific-visualization / matplotlib / seaborn / plotly / figure-spec / graphviz / excalidraw-diagram / infographics / scientific-schematics），catalog 新增 `scientific_plotting_expanded` 能力
- ZCode 兼容层：根 AGENTS.md（宿主支持矩阵）、`.zcode/config.json`（docsearch MCP）、`.zcode/skills` 技能联结、`/doc-governance` 命令与 `acat-doc-governance` 治理技能
- 全学术定位：主套件目录更名 `科研工具箱/`（原 数学建模全流程套件/），文档定位统一为 6 大能力域科研工具箱

### Changed

- **发布边界（用户裁定 2026-08-28）：项目所有能力公开发布**——9 项 private_extension（软著 copyright-draft/build、专利 patent-draft/build、基金 grants 等）转为 experimental，不再设私有扩展边界；验收状态保持如实（未跑 C2-C5 者仍为实验性，正式仍为 10 项）
- 文档治理：45+ 份文档全文审计，17 份过期快照加"仅供追溯"横幅，修正许可矛盾（MIT→CC-BY-NC-4.0）与多处漂移数字；溯源台账扩至 26 条