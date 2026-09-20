# 2026-09-20 基线基础设施加固（Baseline Infrastructure Hardening）

> 定位：系统性升级第四轮（续 37/38/39 之后）。前三轮吸收 agent-skills / another-agent-skills / agent-os / Claude Skills 规范并落地技能层机制；本轮补**工程基座盲区**——lint / 密钥安全 / 资产重复 / 工具冒烟 / CI 加固。本文是调研溯源与取舍记录（批判式吸收，非全盘照搬）。

## 一、动机（普查证据）

2026-09-20 整仓普查（Explore 代理 26 次工具调用实测）发现治理盲区：

| 盲区 | 实测证据 | 严重度 |
|------|---------|--------|
| 零 lint/类型检查 | 608 个 tracked .py 无任何 ruff/flake8/mypy 配置；CI 仅 pytest+provenance 两步 | 高 |
| 零安全扫描 | 无 gitleaks/pip-audit/dependabot；`.env` 防护仅 gitignore 单层；无 SECURITY.md | 高 |
| 测试盲区 | 8 个工具零测试引用（含 711 行 derive_reference_from_docx）；无覆盖率测量 | 高 |
| 重复无守护 | 189 组字节级重复仅 _utils↔shared-scripts 1 组有守护；双份 10.56MB 字体无人知晓 | 中 |
| CI 缺口 | 无 permissions 最小化、无缓存、单 job | 中 |
| 台账陈旧 | governance/asset-ledger.jsonl 4.63MB 停留在 2026-08-13（5 周前），与 9 月三轮升级脱节 | 中 |

**lint 盲区的直接代价（本轮实证）**：首次引入 ruff 即抓到 4 个真实缺陷——`engine/run_logger.py` F821（`__main__` 块调用尚未定义的 `_count_by`，CLI report 子命令必炸 NameError）、`academic_cn.py` F601 重复字典键（后者静默覆盖前者）、`test_facts_audit_numre.py` W605 无效转义、`test_quality_gates.py` F811 重复导入；另有 92 项安全可修（F401/F541 类）。

## 二、调研来源与批判式吸收

| 来源 | 读到的机制 | 采纳 | 不采纳/改造理由 |
|------|-----------|------|----------------|
| [NVIDIA tensorrt-llm #11469](https://github.com/nvidia/tensorrt-llm/issues/11469) | `ruff-legacy-baseline.json`：per-file/per-rule 违规快照，新增即拦、减少提示收紧棘轮 | ✅ `tools/lint_ratchet.py` + `data/lint_baseline.json` | 改 per-rule 聚合（非 per-file）：per-file 粒度在持续演进的仓里每次编辑都触发基线更新仪式，聚合口径的棘轮语义等价而维护成本低 |
| [astral-sh/ruff #1149](https://github.com/astral-sh/ruff/issues/1149) | 官方 baseline 提案（多年未实现） | ✅ 佐证"社区需要此模式" | 官方未实现，自建脚本补位；版本锁死 `ruff==0.16.8` 保证计数可比（提案讨论中的版本漂移问题） |
| [gitleaks]/[TruffleHog]/[GitHub 官方安全实践](https://github.blog)/[StepSecurity 清单](https://www.stepsecurity.io) | CI 密钥扫描纵深 + push protection + `permissions:` 最小权限 | ✅ `tools/secret_scan.py`（自建高精度正则面 + 豁免台账）+ CI `permissions: contents: read` | 不引 gitleaks 二进制（自包含原则 + Windows 中文路径仓的确定性优先）；模式面只收"几乎必然是凭证"的类——误报泛滥的扫描器会被绕过（狼来了原理）；GitHub 原生 secret scanning 属仓库设置项，写入 SECURITY.md 提示操作员开启 |
| [agent-ecosystem/skill-validator](https://github.com/agent-ecosystem/skill-validator) | CI 里对 skills/ 目录做结构校验（strict 分档） | ❌ 不采纳 | 本仓 `skill_trigger_audit.py` 已覆盖且更深（frontmatter/触发信号/路由歧义/主链契约段），外引校验器是重复真源 |
| tensorrt-llm 同款 "ratchet hint"（存量下降打印收紧提示） | 退出码 0 + 提示 | ✅ 同款语义 | — |

## 三、落地清单（全部带测试）

| # | 落地物 | 测试 | 备注 |
|---|--------|------|------|
| U0 | 修复 ruff 首扫抓到的 4 真实缺陷 + 84 项安全修复（autofix 80 + 手工 4） | 全量 pytest 603/0 验证零回归 | 存量 96→11 |
| U1 | `tools/secret_scan.py` + `data/secret_scan_allowlist.json`（3 条豁免，全部带理由） | `test_secret_scan.py` 8 项 | **首跑即抓到存量违例**：CROSS_PROJECT_FIGURE_SKILLS_PROMPT.md 写本机绝对路径（硬性规则 6 违例，已修为 `~/.zcode` 可移植写法） |
| U2 | `tools/lint_ratchet.py` + `data/lint_baseline.json`（8×F841 锁存）+ ruff==0.16.8 入 requirements-dev | `test_lint_ratchet.py` 7 项 | 棘轮当场抓住本批新测试文件的未使用导入（狗粮验证） |
| U3 | `tools/check_duplicate_assets.py` + `data/duplicate_assets_registry.json`（152 组全登记、0 TODO、23.0MB 重复显性化） | `test_duplicate_assets.py` 6 项 | 台账棘轮：未登记的新重复组即拦；已消解组提示移除 |
| U5 | `tests/test_tool_smoke.py`：140 工具全量 py_compile + 11 工具 --help 契约 + **data_init 防覆盖回归** | 4 项 | **冒烟探测当场抓到**：data_init --help 真写文件且把 data/README.md 覆盖回 8 月旧模板（34 行现行文档被毁，git 恢复）；修复为默认不覆盖 + --force + --data-dir + --dry-run |
| U4 | CI：`permissions: contents: read` + pip 缓存 + secret-scan/lint-ratchet/duplicate-assets 三步 | CI 本身 | job 名 pytest+provenance → +gates |
| U6 | ~~governance 资产台账刷新~~ **降级为遗留项 L12**（见下） | — | 两次实测重生成（仓库根 77,039 条 / 工具箱子树 9,299 条）均与 HEAD 口径（11,252 条、含 8 月改名前路径）语义不一致——现版工具是"全量分类"而旧台账疑为"仅本地未跟踪资产"；无消费者/测试锚定范围契约（TOOL_GAP：状态未知不伪造）。governance/ 已保持 HEAD 干净态，待厘清契约后刷新 |
| U7 | `SECURITY.md`（密钥边界/报告渠道/TOOL_GAP 声明） | — | 公开仓标准件 |

## 四、有意不做（及理由）

1. **不引入 pre-commit 框架**：本仓已有 L1 hook 审计层 + 9→12 检查件体系，再叠 pre-commit 是第三套门禁真源；CI 侧已覆盖同等检查。
2. **不做 pip-audit/dependabot**：依赖面极小（7 个 dev 依赖 + vendored node 子项目），扫描噪声大于收益；可后续依赖增长时再启用。
3. **不自动去重 23.0MB 重复资产**（含双份 10.56MB 字体）：技能自包含（可独立拷走）是设计原则，符号链接/共享目录会破坏它；台账显性化后清理属用户裁定的空间权衡。
4. **不删 5 个"零引用"疑似死代码工具**（analyze_latex_template 等）：删除铁律要求用户过目；且 check_ledger_drift 被普查判"零引用"实为活跃运维工具（LOG 续11/续13 在案），证明 grep 引用计数不足以定死罪。已登记待用户裁定。
5. **不引入覆盖率测量（pytest-cov）**：本轮已新增 25 项测试把最大盲区（8 工具零测试）补上；覆盖率棘轮的价值要在"测试数量增长放缓后"才显现，避免本轮铺太开。
6. **不采纳 per-file lint 基线粒度**：见上表改造理由。

## 五、遗留项（2026-09-20 用户裁决"按推荐执行"后全部闭环）

- L8 ✅ 已建议用户开启：GitHub 原生 secret scanning + push protection（仓库 Settings → Code security，AI 无法代开 web 设置）。开启后与本仓 `secret_scan.py` 形成纵深（原生覆盖历史/合作伙伴模式/未跟踪面，自建覆盖 tracked 文本面模式级）。**状态：等用户 web 操作，若遇 push protection 误拦可走 GitHub bypass 流程**。
- L9 ✅ **已复核：非死代码，全部保留零删除**（2026-09-20 复核推翻普查"零引用"初判）：`analyze_latex_template` / `derive_profile` / `markdown_utils` / `generate_format_reference` 四件均有同名 .pyc 分发件（真源契约，删除将制造不可审查的孤儿分发件）；`codesucker_end_to_end_demo` 为 2026-08-19 修 pytest 收集冲突的有意改名留痕（task_plan Phase 记录）。grep 引用计数不足以定死罪——`check_ledger_drift` 同案例再次验证删除铁律。
- L10 ✅ **推迟，改"触碰时顺手拆"约定**：`quality_gates.py`（1694 行）/`scholar_fetch.py`（1325 行）不立独立拆分任务（纯结构运动无功能收益，且 quality_gates 是多窗口并行高频改动区）；约定为**下次因功能改动触碰这两个文件时，把触碰的那一段顺手拆出**，609+ 项测试护栏兜底。
- L11 ✅ **暂缓，绑定触发条件**：mypy 引入推迟到"engine/ 抽成可复用安装包（pyproject/setup）时"——那才是类型系统产生回报的形态；当前 140 工具以独立 CLI 为主，铺注解成本高于收益。
- L12 ✅ **已执行（2026-09-20 用户裁定"按推荐执行"）**：8-13 资产台账零丢失归档 `dev-docs/archive/asset-ledger-20260813/`（3 文件 sha256 manifest + 逐字节比对通过）+ `git rm` 移出公开 tracked 面（4.63MB 减重）；活文档 4 处引用改指归档路径，dated 快照 6 处按铁律 21 保留原文。**执行中的诚实留痕**：归档前全读 ASSET_LEDGER.md 发现 2026-09-19 治理收口已有"不重跑、不删除"标废横幅——本裁决为其延伸而非推翻（归档保全了"硬删会丢的历史"，且"不重跑"经本轮两次实测反向证实：仓库根 77,039 条 / 工具箱子树 9,299 条均与旧口径 11,252 条语义不一致）。`build_asset_ledger.py` 工具保留（受冒烟测试保护），产物默认不入 git。
