# 同类项目批判式分析与融合评估（2026-09-19）

> **触发**：系统性升级第 5 项——"搜索调研同类优秀项目，批判式分析其设计优劣，将有价值的做法
> 吸收并融合进本项目，同时说明取舍理由"。
> **方法**：先检索（WebSearch，覆盖 agent 技能框架 / spec-driven 工作流 / 科学配色规范三条线），
> 只对能读到机制描述的项目做评判；对二手报道中的数字（如 star 量）**不作依据**——同一项目的
> star 数在不同报道里从 3 万到 8 万不等，来源互斥，故本文只用机制性结论。
> **输出**：采纳清单（含落地位置）+ 明确不采纳清单（含理由）+ 遗留待评估项。

---

## 一、调研对象与评判

### 1. addyosmani/agent-skills（生产级工程技能集，六阶段生命周期）

| 维度 | 评判 |
|------|------|
| **强项** | ① **反合理化表（anti-rationalization table）**——把"我稍后补测试""这个改动太小不用规格"这类借口预先配好反驳，直接针对 agent 的"跳过倾向"；② **每个技能有退出判据（exit criteria）** 而非散文；③ "Process over prose / workflows over reference" 的定位纪律；④ 每个技能声明 Output Contract（产物/格式/位置/质量判据） |
| **弱项** | ① 反合理化表是**通用劝诫**（"测试是代码可用的证明"），没有项目本地证据支撑，说服力依赖模型自觉；② 无跨步骤状态机与审计链——技能之间靠 agent 记忆衔接，"哪一步真的做过"不可核；③ 无防伪造机制（审核类步骤没有独立性强制） |
| **本项目现状** | ④ 已具备（`output_files` / `primary_output` / `output_specs` / `required_checks`）；② 已具备但覆盖不足（`output_specs` 原仅 2 步）；①③ 完全缺失 |
| **结论** | **采纳 ① + 补强 ②**。反合理化表按"本项目自有事故实证"重写（借口能不能站住用留痕直接判），并把 `output_specs` 从 2 步扩到 9 步 |

### 2. juandelossantos/another-agent-skills（git hook 机械门禁，14 道 pre-commit 闸）

| 维度 | 评判 |
|------|------|
| **强项** | ① **机械强制**："prompts 会忘，hooks 不会忘"——把约束放在 agent 记忆之外执行；② 设 **SKILL GATE**（提交前检查"技能是否被咨询过"）；③ 14 道闸可组合、可解释（每道闸给出通过/失败原因）；④ 覆盖 override 被跟踪 |
| **弱项** | ① git hook 可被 `--no-verify` 绕过，且**只覆盖 git 工作流**——竞赛解题、绘图、文档生产大量操作不在 commit 边界内；② 14 道闸全是"通用工程规范"（分支/暂存/远端同步/TDD），与学术与竞赛域无交集；③ 无产物级质量门禁（页数/图表/引用） |
| **本项目现状** | **已具备更强形态**：L1 拦截式审计在宿主 hook 层（agent 无法绕过），且已固化 fail-open 铁律（2026-09-09 锁死事故后） |
| **结论** | **采纳 ②的判据，但换承载层**：把"技能是否被咨询"实现为 **L1↔L3 交叉核验**（`verify_skill_bindings`），而非新增 git hook。**不采纳** git-hook 承载层（理由见 §二.2） |

### 3. buildermethods/agent-os v3（standards 发现 / 索引 / 选择性注入）

| 维度 | 评判 |
|------|------|
| **强项** | ① **standards 从既有代码反向抽取**（不是让用户手写规则），降低规则维护成本；② **index + 只注入相关标准**——避免"把整本手册塞进每个 prompt"的上下文税；③ v3 主动**退役**编排与子智能体（"frontier models 自己能做"），是罕见的"减法"案例 |
| **弱项** | ① 退役编排的代价：**spec 不再是可留存的事实源**（v3 的 spec 变成 claude plan mode 的临时规划产物）——对"可复盘"场景是倒退；② 无审计链、无产物门禁，质量依赖模型自觉；③ 强依赖宿主（claude plan mode），跨宿主一致性弱 |
| **本项目现状** | ② 已具备（选择性注入＝`companion_skills` / `assets` 按步暴露 + `CONTEST_SKILL_MAP` 索引）；① 部分具备（技能/模板已在 `templates.json` 与目录中声明，但没有"从既有产物反向抽取经验"的机制） |
| **结论** | **采纳 ② 的思路作为设计校验**（我们的按步暴露与索引化正符合"选择性注入"）；**明确不采纳 ① 的退役编排**——本项目差异点就是"没证据＝未执行"的审计链，放弃编排等于放弃产品定位。同时吸收 ① 的**反向抽取**精神 → 落地为 `contest-retrospective` 技能（从留痕反向抽取经验并归因强制点） |

### 4. Claude Skills 官方规范（渐进披露 / description 即路由索引）

| 维度 | 评判 |
|------|------|
| **强项** | ① **三层渐进披露**（frontmatter 常驻→SKILL.md 按需→references 再按需），控制上下文税；② **description 是路由索引而非文档**（≤1024 字符、含触发词、what+when）；③ 明确"**画边界**"——写出"何时不用它、该用哪个"，避免相邻技能抢同一请求；④ 提供测试法：3-5 条应触发 + 2-3 条不应触发的提示词 |
| **弱项** | ① 触发靠模型对 description 的语义匹配，**无机械校验**——描述写错就静默不触发；② 无跨技能一致性检查（重叠/冲突无人管）；③ `disable-model-invocation` 等安全开关是可选字段，非默认 |
| **本项目现状** | ① 部分具备（260 技能有 frontmatter）；② 无任何机检；③ 无边界的普遍缺失（实测 242/260 技能正文无边界声明） |
| **结论** | **采纳 ②③ 并机械化**：新增 `tools/skill_trigger_audit.py`（frontmatter 合规 + 触发信号 + **重叠歧义检测** + 目录/地图对账），并把实测命中的歧义对逐对补上判别说明。**不采纳**"仅靠描述触发"的被动模式——本项目的路由主通道是引擎 StepAction 显式给出 skill_path |

### 5. 科学配色规范（Okabe-Ito / Paul Tol / ColorBrewer / viridis / cividis / Crameri）

| 维度 | 评判 |
|------|------|
| **强项** | ① 按**数据类型**分类（qualitative / sequential / diverging），先定类型再选色板；② **CVD（色觉障碍）可访问性**已从"加分项"变成期刊硬要求（Nature/Cell/PLOS/eLife 明确要求）；③ **灰度单调性**判据（把图转灰度仍可读）；④ 给出**禁用清单**（jet/rainbow、RdGn/RdYlGn）；⑤ 明确"期刊品牌色板（ggsci 系）是风格合规工具、不是无障碍工具"——这一条极容易被误用 |
| **弱项** | ① 规范面向"人看图"，不面向"agent 选色"——无机器可读注册表；② 各来源之间无统一索引，agent 需要自行拼装；③ 对"填充型浅色板"（如本项目 v6「夏日海滩」）没有专门说法，容易被误当作可直用的分类色板 |
| **本项目现状** | 仅有一套场景色板（CUMCM 2026A v6），无类型/场景映射、无禁用清单、无注册表 |
| **结论** | **全面采纳并机械化为注册表**：`assets/palette_registry.json`（5 场景 × 3 类型 × 9 色板）+ `references/scenarios.md`（三步选色法/10 条规范/禁用清单）+ `palette_kit.py registry-verify` 机检（含 CVD 契约与场景交叉一致）。**诚实处理本地色板**：实测其 CVD 最近色对 ΔE=1.7，故登记为 `cvd_mode: secondary_encoding`（依赖墨色描边+线型+直接标签），而不是假装它通过色盲检查 |

---

## 二、关键取舍（逐条给理由）

### 1. 为什么保留编排引擎，而不学 Agent OS v3 做减法？

Agent OS v3 的退役理由（模型自己能规划）对**通用编码**成立，对**本项目场景不成立**：

| 场景需求 | 无编排的后果 |
|----------|-------------|
| 多智能体/多来源并行的产物追溯（本项目真实发生过：三套独立实现、两条同名稿件线） | 无法回答"这份数值是哪个 run、哪条命令产的" |
| 交付合规审计（评审可要求每步可复盘） | `STEP_MANIFEST` / 证据链断档，无法自证 |
| 防伪造审核（自审恒等于表演） | 无 `requires_subagent` 这类结构性隔离 |
| 检查点＝用户裁决点 | 无状态机即无"谁在什么依据下放行" |

**取舍结论**：保留引擎，但采纳 v3 的**减法精神到别处**——把"选择性地只注入相关内容"做到位（按步暴露 skill/asset，而不是把全库手册塞进上下文）。

### 2. 为什么"技能强制调用"落在审计层而不是 git hook？

another-agent-skills 的 SKILL GATE 在 git hook 层，本项目做了不同选择：

1. **覆盖域不符**：git hook 只在 commit 边界生效；我们的工作单元是**工作流步骤**（题目分析、建模、出图、审稿都不产生 commit）。
2. **可绕过性**：`--no-verify` 可跳过 git hook；本项目的 L1 在宿主 hook 层，agent 无法跳过。
3. **与既有铁律冲突**：本项目 hook 层已固化 **fail-open 铁律**（hook 自身故障一律放行）——那是从 2026-09-09 全工具锁死事故换来的教训；把业务门禁塞进 hook 会重新引入"钩子故障阻断全部工作"的风险。
4. **分离关注**：执行层（`complete_step` 硬校验，快、确定性）＋审计层（`verify_skill_bindings` 交叉核验，可与 L1 对账）两层已经覆盖"自述合规 → 可核合规"。

### 3. 为什么反合理化表必须重写而不能直接抄？

通用反驳（"测试是代码可用的证明"）对模型是劝诫，权重低且不可核。本项目版本改为**每行带自有事故实证 + 机器判据**：
借口"总体没问题" → 反驳直接指向"COMP_REVIEW 真实样本含 major/minor 分级" → 机器判据 `require_any=["major","minor","fatal","结论"]`。
**代价**：表体不能无限扩张（只在事故重演或可泛化时增行）；**收益**：每行都是可拦截的闸，而非提示语。

### 4. 为什么配色注册表存"指针"而不复制本地色值？

本项目已吃过双源分叉的亏（D5：工程 sty 与仓库 sty 私改偏移、无法回答"改了模板什么"）。
故注册表对本地色板**只登记已解析色值并声明真源路径**（`palette_v6.json`），机检里另有一条
`test_local_palette_matches_v6_source` 做双向一致性——避免两处色值各自漂移。

### 5. 为什么不采纳"不做阻塞式审稿门禁"的做法？

有同类框架（如 ClaudeKit 系）明确采取"no blocking reviewer gates / no orchestrator"的轻量立场。
该立场适合日用编码代理，**不适合学术与竞赛交付**：本项目的真实证据是——独立视角的审稿
在首轮就抓出 2 fatal + 1 major（同一次运行里"自审"给的是全 PASS）。对交付物而言，
审稿不是开销而是产品价值本身。故本项目反向加强：审核类步骤 `requires_subagent`、
`skip_` 豁免只留痕不放行。

---

## 三、已落地融合清单（本轮）

| # | 融合项 | 来源 | 落地位置 | 验证 |
|---|--------|------|----------|------|
| F1 | 反合理化表（自有事故实证版，12 条） | agent-skills | `skills/_utils/anti_rationalization.md` + 模板 step7/step14 资产 | 资产指针审计 163 条全在位 |
| F2 | 退出判据（exit criteria）扩展 | agent-skills | `output_specs` 从 2 步 → 9 步（关键字由真实产物实测推导） | `tests/test_output_specs.py` |
| F3 | SKILL GATE 判据（换承载层） | another-agent-skills | `engine/audit_store.verify_skill_bindings()` + `AUDIT_REPORT.json` gate | `tests/test_skill_binding.py`（17 项） |
| F4 | 技能路由索引机械化（触发词/边界/歧义） | Claude Skills 规范 | `tools/skill_trigger_audit.py` + 5 对歧义补判别说明 + 7 个可达技能补触发词 | `tests/test_skill_trigger_audit.py`（14 项） |
| F5 | 科学配色类型/场景/禁用体系 | Okabe-Ito / Paul Tol / ColorBrewer / viridis | `assets/palette_registry.json` + `references/scenarios.md` + `registry-verify` | `tests/test_palette_registry.py`（18 项） |
| F6 | 从留痕反向抽取经验（反向抽取精神） | Agent OS v3 | 新技能 `contest-retrospective` + `data/contest_lessons.*` + 机检 | `tests/test_contest_lessons.py`（15 项） |

## 四、明确不采纳项

| 不采纳 | 理由 |
|--------|------|
| 退役编排层 / 不做状态机（Agent OS v3） | 与产品差异点直接冲突：本项目卖点就是"没证据＝未执行"的可复盘链 |
| git hook 承载业务门禁（another-agent-skills） | 覆盖域不符（工作单元是步骤不是 commit）＋可 `--no-verify` 绕过＋与既有 fail-open 铁律冲突 |
| 不做阻塞式审稿门禁（ClaudeKit 立场） | 与真实证据相反：自审给全 PASS 时，独立审稿抓出 2 fatal + 1 major |
| 通用（无实证）的反合理化话术 | 不可核、权重低；本项目版本要求每行带事故实证 + 机器判据 |
| 直接采用期刊品牌色板作为"无障碍方案" | 品牌色板是风格合规工具；无障碍必须单独复核灰度与 CVD |
| 通用 spec-driven 流程（在编码代理上重造规格链） | 本项目已覆盖更细的领域契约（`output_specs`/`required_checks`/三层审计），重造只会增加并行体系 |

## 五、遗留待评估（诚实标注）

| # | 项 | 待评估理由 |
|---|----|-----------|
| L1 | 触发条件测试法（每技能 3-5 应触发 + 2-3 不应触发的提示词）落地为机检 | 需先确定"谁来判断触发是否正确"（当前路由主通道是引擎显式下发，纯描述触发的收益尚未量化） |
| L2 | standards 反向抽取（从既有产物自动建议规则） | 本轮只做了"复盘技能"这一最小形态；自动化抽取需要先定义规则粒度与误报容忍度 |
| L3 | 88 个外域/未接入库技能的触发词补齐 | 有意排除：改上游 vendored 描述会与上游分叉；`tools/skill_trigger_audit.py` 的 WARN 输出保留了完整清单，待按可达性分批处理 |
| L4 | CVD 拟真精度（当前为 Machado 线性近似） | 当前用于"分不开/分得开"的二值判断够用；若要做阈值级判定需换更精确模型并重新标定 |

---

## 六、第二轮：从"读过"到"搬进来"（2026-09-19 追加）

> **追加原因（用户质询）**：第一轮只用了二手搜索摘要，产出的"融合"以文档与少量规则为主——
> 这是**读过了**，不是**搬进来了**。第二轮改为直接取上游真实产物（`raw.githubusercontent.com` 的
> SKILL.md / 安装壳 / 门禁脚本说明），把可机检的机制搬进本项目，并以"搬进来之后发现了什么"
> 作为融合是否真实的证据。

### 6.1 这一轮真正读到的上游产物

| 来源 | 读到的具体东西 | 与第一轮的差别 |
|------|----------------|----------------|
| addyosmani/agent-skills | `code-review-and-quality/SKILL.md` **逐字结构**：frontmatter 仅 name+description；19 段 H2 骨架（Overview → When to Use → 五轴审查 → Review Process 五步 → … → `## Common Rationalizations` → `## Red Flags` → `## Verification`）；反合理化表是 **2 列**（`Rationalization \| Reality`）；有 `### Verdict`（Approve / Request changes）与 "Presumptive blockers" 升级规则 | 第一轮只知道"有反合理化表这个名目"，不知道它长什么样、挂在 SKILL.md 的哪一段 |
| juandelossantos/another-agent-skills | **Harness 六组件**（Instructions / Tools / Sandboxes / **Orchestration** / **Guardrails & Hooks** / **Observability**）；Gate 0 = `DECISION_APPROVED`（计划批准≠提交批准）；commit-msg v6 TDD 闸**零豁免**；**25 条**反合理化；Debug **3-strikes**；**TOOL_GAP**（工具够不到世界就报"状态未知"，绝不伪造成功）；**Context Engineering：常驻 ~3,870 tokens = 200K 的 1.9%**（技能做成 ~250 行索引、细节按需加载）；`project-metrics` / `HEALTH-CHECK.md` 可观测件；**Drift Detection**（定期比对文档与现实的统计/版本/功能/命令/链接） | 第一轮只知道"有 git hook 门禁"，漏掉了它的 Harness 分层、常驻税数字与漂移检测原则 |
| buildermethods/agent-os | standards 的 **discover → index → inject** 三段（index 驱动"自动判断哪些标准相关"，只注入相关的，避免整本手册进上下文） | 第一轮只知道"有 index.yml" |

### 6.2 搬进来的五个机制（全部可机检）

| # | 机制 | 吸收自 | 落地物 | 机检 |
|---|------|--------|--------|------|
| F7 | **常驻上下文预算** | another-agent-skills 的 1.9% 纪律 + Claude 规范"description 是搜索索引，不是文档" | `tools/context_budget_check.py`：全库常驻字符预算 + 单条上限 + **六类描述污染判据**（路径/步骤编号/门禁哈希/箭头/表格线） | `tests/test_context_budget_check.py`（13 项，含六类污染负例） |
| F8 | **统一健康检查 + 文档漂移检测** | Harness 的 Observability + Drift Detection | `tools/project_health_check.py`：子进程汇总 7 个既有检查件 → PASS/WARN/**FAIL/DEGRADED** 四态；漂移检测比对实测测试数与 5 处权威文档基线（含**历史横幅豁免**） | `tests/test_project_health_check.py`（13 项，含"文档写 999 实测 1"必须报、DEGRADED 不得折算 PASS） |
| F9 | **退出判据 + 岗位级反合理化下沉到 SKILL.md** | agent-skills 的 `## Verification` + `## Common Rationalizations` 段 | 主链 14 技能各补「退出判据（Verification）」checklist 与「常见合理化」表（≥3 行，内容取自本项目真实事故） | `skill_trigger_audit` Layer E：**主链名单从 templates.json 自动派生**，缺段即 ERROR |
| F10 | **触发词测试法机械化（词法路由回归）** | Claude 规范的"3-5 条应触发 + 2-3 条不应触发"提示词测试 | `skill_trigger_audit.route()` + `--route` 诊断 + 中文 n-gram 词元；`tests/test_skill_routing.py` 做"判别查询必须正确排序" | 23 项，含**歧义对二分完备性**断言（要么登记为词法不可分，要么给出可判查询） |
| F11 | **命名原则**（TOOL_GAP / 三振升级 / 决策点≠批准 / 无证据＝未执行） | another-agent-skills 的显式命名 | `skills/_utils/anti_rationalization.md` §四原则表，**每条必须给出可 grep 的落地位置**（只起名不落机制不许入库） | 双副本逐字节一致由 `test_dual_copy_consistency` 守护 |

### 6.3 证据：搬进来的机制**当场抓到了什么**（这是本轮最有价值的部分）

融合是否真实，标志是"新机制立刻发现了旧做法看不见的问题"。本轮四个机制各自抓到真问题：

| # | 机制 | 当场发现 | 处置 |
|---|------|---------|------|
| 1 | F7 常驻预算 | 261 技能 frontmatter 常驻 **87,334 字符 ≈ 39,700 tokens = 200K 的 19.8%**，是同行（1.9%）的 10 倍；21 条描述含实施细节（路径/箭头/步骤编号）——**描述写成了文档** | 重写 **53 条**本地自研描述为"搜索索引"形态（保留触发词与判别句、剥离实施细节）：74,607 → **61,056 字符**（-18%），本地污染 **21 → 0**，并设 62,000 字符棘轮上限 |
| 2 | F8 漂移检测 | 首次运行即报 2 处（其中 1 处是"工具箱 508 ≠ 仓库根 527"的口径误伤，1 处是合规历史留痕）→ 修正模式与横幅豁免后全绿；**随后在本轮新增测试后再次抓到 527 → 576 的真实漂移** | 精化判据（行内锚定 + 历史横幅豁免）+ 按实测更新全部权威文档 |
| 3 | F10 词法路由 | `帮我编译中文论文，输出PDF` 排第一的是 **英文版 `paper-compile`** ——根因是中文按 2-4 字贪婪切分导致词元不对齐 | 引入**独立**的 2-3 字 n-gram 词元（`route_tokens`，与已标定的歧义检测词元 `tokenize` 分离，避免移动阈值）；修复后正确命中 `paper-compile-zh` |
| 4 | F10 词法路由（反直觉发现） | 上一轮为消除歧义加的**判别句会反噬**：`humanities-write` 为说明边界而写了 "LaTeX"，结果含 LaTeX 的请求反而命中它（1.0 > 0.9578）。另发现 `paper-plan-zh` 因描述短且高频词密集，对"中文论文"类请求形成**词法黑洞**（持续抢分） | 不再追求描述层面的完全可分：登记 `KNOWN_LEXICAL_LIMITS`（4 对，附不可分原因）并**强制二分完备**；权威路由仍以引擎 StepAction 显式绑定为主通道（P4） |

> 结论性判断：**"能不能被机检"是融合真假的判据**。第一轮的产出（文档、表格）无法自证有效；
> 第二轮搬进来的四个机制在落地当天就报出了四个本项目此前看不见的问题，其中两个（常驻税、
> 判别句反噬）只有量测/回归才可能发现。

### 6.4 本轮修正的第一轮判断（自我批判）

| 第一轮结论 | 第二轮修正 | 依据 |
|-----------|-----------|------|
| "反合理化表要重写成本项目事故实证版"（只做了 12 条全局表） | **不够**：应像上游那样**下沉到每个技能**（岗位级），全局表只作兜底；上游是 25 条且逐技能分布 | `code-review-and-quality/SKILL.md` 的 `## Common Rationalizations` 就在技能内；已补 14 个主链技能 |
| "不采纳 git-hook 承载门禁"（结论仍成立） | 但要补一句：上游的**判据设计**（Gate 0 决策点、TDD 零豁免、3-strikes）值得单独吸收，与承载层无关 | Harness 六组件描述中 Guardrails 与 Orchestration 是两层，判据可移植 |
| "已具备更强的 L1 审计，无需借鉴" | **漏了 Observability**：我们有 9 个检查件却没有统一入口，也没有漂移检测——上游把它列为独立组件是对的 | 本项目四处文档数字常年互相落后（历史出现 20+ 个过期基线值） |

### 6.5 仍不采纳（维持第一轮结论，理由不变）

见 §四。本轮新增一条**不采纳**：不做 `DECISION_APPROVED` 式的二次令牌（Gate 0）——
本项目已有检查点机制（`checkpoint_type=approve`）承担"决策点≠批准"，再加一层令牌会在
赛时高压下变成纯粹的仪式成本，而它防的风险（计划批准被当成执行批准）已由"skip_ 豁免只留痕
不放行 + 检查点硬闸"覆盖。

### 6.6 遗留（本轮新识别，诚实登记）

| # | 项 | 为什么留着 |
|---|----|-----------|
| L5 | **分层常驻（tiered residency）**：把 261 技能拆为"常驻路由层（核心 40-60 个）+ 按需库（其余）" | 常驻税降到 17.1% 仍是同行量级的一个数量级以上；但宿主发现机制要求 frontmatter 全量可读，分层需要改宿主契约或引入索引层——属架构级改动，须单独立项评估 |
| L6 | `paper-plan-zh` 词法黑洞的缓解 | 纯词法无解；可行路径是给高频短描述加"负向词"或让引擎在小候选集内二次排序，需先量化收益 |
| L7 | 上游族 6 条描述污染 + 111 条上游描述未纳入瘦身 | 有意不改（与上游分叉）；但可在下次上游同步时向上游反馈 |
