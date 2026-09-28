# AutoResearchClaw 全仓代码审查报告

**日期**: 2026-07-03
**范围**: `researchclaw/` 全部 396 个 Python 文件（约 80k 行），8 个并行审查线程覆盖 pipeline 核心、23 个 stage 实现、agent/修复循环、LLM 适配层、experiment 沙箱、config/CLI、模板/文献验证、基础设施。
**基线**: 测试套件 `2831 passed, 49 skipped`（全绿）；`compileall` 通过；`ruff` 227 项（多为未用 import）。**下述问题全部处于测试盲区。**

---

## 核心结论

项目最大的系统性风险是：**多个以"反造假 / 反幻觉"为卖点的防线，在最需要生效的场景下自我关闭或被绕过**。防线本身写了，但边界条件、降级路径、schema 对齐上有缺陷，导致"配置了却没生效"或"失败了却报成功"。这与仓库近期的 `hard-guards-against-fabrication`、`silent-fallback-audit` 方向直接相悖。

三条主线问题：
1. **反造假防线被击穿**（P0 群）——引用验证、论文数字校验、实验失败硬闸都有绕过路径。
2. **版本目录选择错误**（反复出现的 P1）——回滚后诊断/修复/论文写作系统性读到归档的旧快照。`_helpers.py` 已有正确实现，但至少 9 处各自用 `sorted(glob, reverse=True)` 重写且语义相反。
3. **静默降级**——大量 `except Exception: pass/logger.debug` 把功能失效藏起来，包括 LLM 未接通、审批被跳过、数据源全空。

---

## P0（严重：数据伪造 / 安全 / 核心功能失效）

| # | 位置 | 问题 | 触发场景 | 状态 |
|---|------|------|---------|------|
| 1 | `literature/verify.py:128` | BibTeX 只解析 `{...}` 花括号字段，`title = "..."` 双引号语法解析后无 title → 标 SKIPPED → `filter_verified_bibtex` 保留所有 SKIPPED | 虚构引用用双引号 title 即可零校验进入最终 `references.bib` | ✅已复现 |
| 2 | `pipeline/paper_verifier.py:63` | 注释掩码正则 `% .*$` 不排除转义 `\%` | `91.5\% accuracy ... baseline 88.2` → `\%` 后整行被当注释，后面数字逃过反造假校验 | ✅已确认 |
| 3 | `experiment/sandbox.py` + `_code_generation.py:876` | 默认 sandbox 模式直接用宿主 Python 无隔离运行 LLM 代码；且 security 类校验错误不阻断执行（只 syntax/import 阻断） | LLM 生成含 `os.system` 的代码，repair 未清除 → 宿主命令执行 | ✅已确认 |
| 4 | `hitl/session.py:199` | 输入 callback 抛异常时降级路径硬编码 `auto_proceed_on_timeout=True`，无视用户配置的 `False` | `CLIAdapter.collect_input` 任何未捕获异常 → 人工审批 gate 60s 后静默自动批准 | ✅已确认 |
| 5 | `dashboard/collector.py:91` | 读 checkpoint 字段名（`stage`/`topic`）与 runner 写入的（`last_completed_stage`）不匹配；heartbeat 时间戳按 float 做算术但实际是 ISO 字符串 | 仪表盘 `current_stage` 恒 0、topic 恒空、`is_active` 恒 False，全被 bare except 吞掉 | ✅已确认 |
| 6 | `trends/feeds.py:106,82` | 导入不存在的 `search_s2`（真名 `search_semantic_scholar`）被当"未安装"；对 `Paper`（frozen dataclass）调 `.get()` 一有结果即 AttributeError | `researchclaw trends` 三源全空却正常退出；测试 mock 掉 `_fetch_*` 测不出 | ✅已复现 |
| 7 | `mcp/server.py:136` | `researchclaw mcp --start` 只置 `_running=True` 后退出，无 transport 绑定、无消息循环；`tools.py` 对外宣称能力但 `handle_tool_call` 无人调用 | MCP server 功能整体不存在 | ✅已确认 |

---

## P1（高：崩溃 / 逻辑错误 / 安全）

### 反造假与引用验证
- `literature/verify.py:794` — L1 arXiv 校验是死代码：OpenAlex 查无结果返回确定性 HALLUCINATED（非 None），永不回落到 arXiv API。**OpenAlex 尚未收录的新预印本被误判为幻觉并从正文删除**。
- `literature/verify.py:379` — 真 DOI + 假题目（相似度<0.5）只判 SUSPICIOUS，而 stage-23 用 `include_suspicious=True` 保留。元数据从不比对。
- `literature/verify.py:97` — 网络全挂/5 分钟超时 → 全部 SKIPPED → `integrity_score` 分母 `total-skipped` 为 0 返回 **1.0 满分**。单次无重试。
- `pipeline/stage_impls/_review_publish.py:2798`（BUG-26 回退）— 验证剔除 >50% 条目就整体还原原始 bib，即在**幻觉最严重时**把 HALLUCINATED 条目放回，且正文引用已被删 → bib 与正文不一致。

### 版本目录选择（同一根因，多处）
- `pipeline/runner.py:224,235,253,268` — 诊断读 `sorted(glob("stage-14*"), reverse=True)` 取到 `stage-14_vN` 旧快照。首次 REFINE 后诊断/修复全基于过期数据。
- 同族问题：`_analysis.py:869,1222`、`_paper_writing.py:1398,1950,1988`、`_review_publish.py:1589,2264`、`_execution.py:851`。**建议统一为 `find_latest_stage_artifact()`，一次消灭 BUG-58/178/207/222/DA8-16 全系列。**

### 控制流 / 门禁 / 回滚
- `pipeline/executor.py:769` — GATE 阶段即使 `FAILED` 也被无条件改写成 `BLOCKED_APPROVAL`，失败被吞。
- `pipeline/runner.py:845` — `BLOCKED_APPROVAL` 仅在 `stop_on_gate=True` 时中断；`execute_iterative_pipeline` 从不传该参数 → 未批准的质量门禁被跳过继续导出论文。
- `pipeline/runner.py:762` — PIVOT/REFINE 递归调用 `execute_pipeline` **漏传 `to_stage`**，`--to-stage 17` 触发 REFINE 后无视上限跑到 Stage 23。
- `pipeline/runner.py:660` — 回滚时不回退 checkpoint；递归重跑期间崩溃 → resume 从错误阶段起、读被改名的旧目录。
- `pipeline/executor.py:641` — Ollama 无 api_key（其 preset 无 key 且本不需要）→ `llm=None` 无任何日志 → 23 阶段全部静默降级为模板兜底，产出无 LLM 参与的"论文"。而 `validate_config` 明确豁免 ollama 需要 key，两处矛盾。

### 数据伪造 / 静默 fallback（stage 层）
- `_code_generation.py:776,1298` — 代码生成失败时合成噪声 `1/(1+‖x‖²)` 冠以真实指标名；对齐检查解析失败默认 `aligned=True` 放行 → 合成数据绕过零指标硬闸流向论文。
- `_execution.py:269` — collider_agent 失败仍返回 DONE，绕过 stage 12 的 fabrication 硬闸（硬闸只保护 sandbox/docker 模式）。
- `_paper_writing.py:241` — 精炼"最优"选择硬编码 maximize 方向；`minimize`（loss/RMSE）下选出**最差**迭代注入论文提示词。
- `_execution.py:1072`/`_analysis.py:1173`/`experiment_diagnosis.py:572` — 饱和/退化/近随机检测假设指标在 [0,1] 或百分制；百分制 accuracy 恒触发"饱和"，0.92 小数 accuracy 被误诊为"接近随机"。

### 确定性崩溃
- `_paper_writing.py:2293` — `re.search(draft_text, re.DOTALL)` 参数错位（pattern 未用、flag 当字符串），PaperCoWriter 章节提取 100% 抛异常被吞，section 永远为空。
- `opencode_bridge.py:583`/`code_agent.py:567` — 把库文件改名为 `main.py`，`from main import X` 导入自身 → 必然 ImportError。

### 修复循环
- `experiment_repair.py:373` + `experiment_diagnosis.py:709` — `repairable`/`repair_possible` 计算了但从不检查，循环终止条件失效；`_assess_repairability` 要求 3 种不同缺陷，同一 crash 每轮复现永不触发 → 烧满 3 周期。
- `opencode_bridge.py:477` — 超时只杀直接子进程，OpenCode 的 Node 孙进程成孤儿。
- `experiment_diagnosis.py:214` — 2 段 key 场景 `actual_seeds` 恒 1 → 永达不到 FULL_PAPER，修复即使成功也返回 `success=False`。
- `agents/figure_agent`（renderer/critic/orchestrator）— `figure_id` 清洗不一致 → 数值校验被跳过、失败图从重试集剔除、空转耗尽 `max_iterations`。

### LLM 适配层
- `llm/client.py:333` — 可重试 HTTP 错误耗尽重试后 `raise RuntimeError`（无 `from e`），`preflight` 依赖 `e.__cause__` 的 401/403/429 分类全部失效，速率限制误报"All models failed"。
- `llm/acp_client.py:100` — ACP 路径丢弃 `json_mode`/`max_tokens`，同一 stage 在 OpenAI/Anthropic 下有 JSON 强制、ACP 下没有，下游解析成功率不一致。

### 配置 / CLI
- `config.py:1182` — `collider_agent.extra_args` 默认 `--dangerously-bypass-permissions`（非法 CLI 参数），与 dataclass 默认及其他两个解析器的 `--dangerously-skip-permissions` 不一致 → HEP Stage 12 CLI 报错失败。
- `config.py:920` 等约 20 处 — 顶层字段对 YAML `null` 裸用 `int()`/`float()` → `int(None)` TypeError，`validate_config` 不拦截（experiment 段有 `_safe_int` 但其余段没用）。
- `cli.py:1285` 等 5 处 — serve/dashboard/project/overleaf/trends 的 `--config` 默认硬编码 `config.yaml`，而 `init` 生成 `config.arc.yaml` → 官方流程走完后这些命令报找不到配置。

### 安全（server / web / hitl）
- `server/middleware/auth.py:40` — `BaseHTTPMiddleware` 对非 http scope 直接放行 → 所有 WebSocket 端点绕过 token 鉴权。
- `web/crawler.py:210`/`pdf_extractor.py:144`/`search.py:204` — SSRF 校验只查初始 URL，`urlopen` 自动跟随 3xx 重定向不复检 → 302 到 `169.254.169.254`/`127.0.0.1` 读内网。
- `server/app.py:49` — CORS 默认 `("*",)` + `allow_credentials=True` + auth_token 默认空 → 任意站点携凭证跨域调 `/api/*`。
- `overleaf/sync.py:42` — Overleaf git URL 含认证 token 明文写日志和异常。
- `overleaf/sync.py:142` — 以 stderr 含 "conflict" 决定吞非零退出码 → pull 冲突被静默，随后把带冲突标记的 .tex 推到 Overleaf。
- `hitl/adapters/mcp_adapter.py:229` — `hitl_view_output` 的 `filename` 无消毒 → 路径穿越读任意文件（ws_adapter 有防护，此处没有）。
- `metaclaw_bridge/prm_gate.py:191` — 质量门平票时 `statistics.mode` 取"最先出现"，顺序来自线程完成顺序 → 门禁 pass/fail 非确定。

### LaTeX / 编译
- `templates/converter.py:1804` — `_escape_latex` 正序还原保护块，嵌套时输出残留 `\x00PROT0\x00` 空字节 → pdflatex 崩溃（`_convert_inline` 已逆序修过，此处漏改）。**已复现**。
- `templates/converter.py:198` — `_fix_tabular_amp` 无差别把单元格内合法 `\&` 反转义成 `&` → "Extra alignment tab" 编译错误（R&D、A&B 消融名）。
- `templates/compiler.py:283` — "Missing $ inserted" 自动修复把全文档 `$x_i$` 破坏成 `$x\_i$`，编译"成功"但所有下标公式错。
- `report.py:154` — 读 `total_references`/`verified_count` 等键，而写入方 schema 是 `{"summary": {"total", "verified"}}` → 运行报告引用验证恒显示 "0/0 N/A"（同错复制在 hitl/quality_predictor.py、summarizer.py）。

---

## P2（中：健壮性 / 正确性 / 资源）

（节选，完整清单见各模块）
- `experiment/code_agent.py:450` — `proc.returncode or -1` 把成功码 0 变成 -1。
- `experiment/code_agent.py:436` — Windows 上 `os.killpg` 抛 AttributeError（docker_sandbox 有 win32 保护，此处没有）。
- `experiment/validator.py:807` — `auto_fix_unbound_locals` 只看函数直接子级赋值，for/with/try 内赋值 + if 分支赋值的变量被误插 `var=None` 覆盖循环算好的值，自动应用改错正确代码。
- `experiment/validator.py:67` — 安全扫描遗漏 `pathlib.Path.unlink/write_text`、`open(p,'w')`、别名 `import os as o`、`getattr(os,'system')`。
- `experiment/docker_sandbox.py:407` — `setup_only`/`pip_only` 不加 `--network none`，依赖容器内 iptables，无 root 时网络全程可用。
- 三个 `*_agent_sandbox.py` — `_install_skills` 把技能复制进共享 `~/.claude/skills` 并对同名先 rmtree → 破坏用户全局技能，并发 race。
- `pipeline/_helpers.py:657` — `_extract_multi_file_blocks` 缺 main.py 时把第一个文件改名为 main.py，其余文件 `import model` ImportError。
- `pipeline/_helpers.py:966` — `_primary_metric` 缺失指标返回 0.0，minimize 方向下失败 run 以 0.0"战胜"所有真实 run；不过滤 NaN。
- `utils/thinking_tags.py:36` — 未闭合 `<think>` 正则 `.*` 从该处删到文末；`[PLAN]` 大写时守卫过但替换不命中。
- `memory/embeddings.py:73` — API 失败回退 TF-IDF 致 1536 与 256 维向量混存，检索静默退化为按时间排序。
- `hitl/cost_guard.py:52` — 阈值去重是实例级但每 stage 新建实例 → 预算过半后每步重复暂停。
- `assessor/scorer.py:107`/`trends/daily_digest.py:92` — LLM 未按格式回复时静默编造固定分。
- 多处非原子整文件覆写（memory/store、assessor/comparator、collaboration/repository、project/idea_pool、hitl/file_wait）— 并发或 SIGKILL 中途丢数据/截断。

---

## 架构 / 质量改进

### 高优先级重构
1. **版本目录选择统一** — 抽 `find_latest_stage_artifact(run_dir, pattern)`，语义"当前 > 最高版本号"。消灭 9 处重复 + BUG 全系列。
2. **状态机死代码** — `stages.py` 的 `TRANSITION_MAP`/`TransitionOutcome`/`GATE_ROLLBACK` 定义完整但只被 `advance(...START)` 仪式性调用一次，真实门禁/回滚在 runner/executor ad-hoc 重写且已漂移。要么驱动它、要么删。
3. **LaTeX 转义碎片化** — 至少 4 份互不一致的转义实现，"先全局转义、再按环境反转义"是 `\&` 表格 bug 的根因。抽单一 `latex_escape(text, context=...)`，生成时按上下文转义，删掉所有事后反转义 pass。
4. **子进程调用统一封装** — `run_subprocess(cmd, timeout, kill_process_group=True)`，统一 `start_new_session`+killpg、bytes/str、returncode 归一化。消灭孤儿进程 + returncode + Windows 三类 bug。
5. **provider 适配接口** — 定义显式 adapter 契约（能力声明 supports_json/max_tokens/temperature + 规范化错误类型），消除散落的 `startswith` 前缀判断（`_NEW_PARAM_MODELS`/`_NO_TEMPERATURE_MODELS`/`_no_response_format` 三张列表互不同步）。

### 巨型文件拆分
- `_review_publish.py`（2880 行）、`_paper_writing.py`（2308 行）、`cli.py`（2295，22 分支手工 if/elif 分发）、`_helpers.py`（1837，杂物抽屉）、`config.py`（1673，默认值双份维护是 bug 之源）、`_code_generation.py`（1531，单函数 1300 行串 8 环节）。

### 死代码 / 半成品模块（建议删除或标注 experimental）
- `servers/` 整包（dispatcher/slurm/ssh/cloud，slurm 提交命令有 shell 语法错误，生产走 `experiment/ssh_sandbox.py`）。
- `copilot/`（455 行，被 hitl 取代）、`collaboration/`（469 行，被 hitl/collaboration 取代）。
- `mcp/` 整包内核空心（stub run_id、literature/review 恒返回占位，但对外宣称能力）。
- 配置有节但从未接线：`assessor/`、`knowledge/graph/`、`memory/` 大部（runner 接线 API 对不上从未运行）。
- hitl 近半模块（ws_adapter/escalation/learning/quality_predictor/branching/notify/hooks）仅测试喂养；`hitl.hooks` 配置字段根本不解析。
- 零调用函数：`domains.detector.detect_domain_async`、`knowledge.base.generate_weekly_report`、`wizard.validator`、`voice.synthesizer`、`project.scheduler` 等。

### 横切建议
- **`atomic_write_json`（temp + `os.replace`）+ 文件锁** — 统一所有磁盘 JSON 读写。
- **静默吞异常审计** — 把 `except Exception: pass|debug` 改为至少 `logger.warning(exc_info=True)`，尤其在标榜 anti-fabrication 的审批/评分/记忆/验证路径上；pipeline_summary 增加 `silent_degradations: []` 字段留痕。
- **example yaml 同步 CI** — config.py 大量字段 example 未覆盖；加测试保证 example 可被 `from_dict` 加载 + 每个 key 映射到 dataclass 字段。

---

## 最该先修的清单（投入产出比排序）

1. `literature/verify.py:128` 双引号 BibTeX 解析（P0，反造假核心，~5 行）
2. `paper_verifier.py:63` `\%` 掩码（P0，反造假核心，1 行负向后顾）
3. `hitl/session.py:199` 硬编码 auto-approve（P0，审批语义，1 行）
4. `dashboard/collector.py` + `trends/feeds.py` schema/import 对齐（P0，整个仪表盘和 trends 恢复）
5. `config.py:1182` extra_args 默认值（P1，HEP 直接失败，1 词）
6. `cli.py` `--config` 默认统一走 `resolve_config_path`（P1，官方流程可用性）
7. 版本目录选择统一 helper（P1，消灭一整个 BUG 系列）
8. `experiment_diagnosis.py:572` + `_execution.py:1072` 指标刻度（P1，误诊正常模型）
