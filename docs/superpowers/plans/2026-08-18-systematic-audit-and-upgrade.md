# 全系统深度审计与系统化升级方案

> 审计日期：2026-08-18
> 审计范围：数学建模全流程套件（6 大域，39 模板，236 技能，46 工具）
> 审计标准：CodeSucker 融合所达到的设计哲学完整度（manifest/bridge/gate/provenance）

---

## 第一部分：深度审计报告

### 1.1 系统规模

| 维度 | 数量 | 说明 |
|------|------|------|
| 技能（SKILL.md） | 236 | 覆盖 6 大域 |
| 模板（templates.json） | 39 | 22 数竞 + 7 论文/文献 + 4 课程 + 2 知识产权 + 4 其他 |
| 工作流步骤 | 257 | 分布在 39 个模板中 |
| 声明产出文件 | 329 | 每个步骤声明的 output_files 总和 |
| 工具脚本 | 46 | tools/ 目录下的独立 .py 文件 |
| 引擎模块 | 12 | engine/ 目录下的核心模块 |

### 1.2 产出文件类型分布（329 个声明产出）

| 类型 | 数量 | 占比 | 结构化？ | 可机器校验？ |
|------|------|------|---------|------------|
| `.md` | 144 | 44% | ❌ 自由格式 | ❌ |
| `.tex` | 86 | 26% | ❌ 自由格式 | ❌ |
| `.pdf` | 31 | 9% | ❌ 二进制 | ❌ |
| `.py` | 29 | 9% | ❌ 自由格式 | ❌ |
| `.json` | 20 | 6% | ✅ 结构化 | ✅ |
| `.bib` | 8 | 2% | ⚠️ 半结构化 | ⚠️ |
| `.docx` | 6 | 2% | ❌ 二进制 | ❌ |
| 其他 | 5 | 2% | ❌ | ❌ |

**结论：仅 6% 的产出是结构化 JSON（且全部来自 CodeSucker 融合）。94% 的产出是自由格式，无法通过机器校验内容完整性。**

### 1.3 质量门禁覆盖（11 个 gate）

| Gate | 类型 | 使用模板数 | 说明 |
|------|------|-----------|------|
| `min_size` | 通用 | 全部 | 只检查文件大小，不检查内容 |
| `companions` | 通用 | 全部 | 只检查文件存在性 |
| `paper_pages` | 竞赛专用 | 22 个竞赛模板 | 只检查 PDF 页数 |
| `figure_health` | 通用 | 所有含 figure 的步骤 | 只检查 PNG 文件可解码 |
| `literature_evidence` | 命名 | 1 个（comp_cumcm） | 检查文献引用状态 |
| `review_evidence` | 命名 | 1 个（comp_cumcm） | 检查审稿证据链 |
| `consistency_evidence` | 命名 | 1 个（comp_cumcm） | 检查代码-论文一致性 |
| `final_audit_report` | 命名 | 1 个（comp_cumcm） | 检查最终审计报告 |
| `source_materials` | 命名 | 1 个（copyright_source_materials） | ⭐ CodeSucker 标准 |
| `figures` | 通用 | 全部 | 检查图表目录 |
| `figure_quality` | 工具 | 按需调用 | 单图质量检查 |

**关键发现：只有 `comp_cumcm` 模板（6 个步骤）和 `copyright_source_materials`（1 个步骤）使用命名门禁。其余 37 个模板的 250 个步骤只使用通用门禁（min_size + companions）。**

### 1.4 模板 metadata 使用情况

| 字段 | 使用模板数 | 说明 |
|------|-----------|------|
| `metadata.requires_subagent` | **0** | 引擎支持此功能，但没有任何模板使用 |
| `metadata` 任何字段 | **0** | 全部模板的 metadata 字段为空 |
| `required_checks` | **7 个步骤** | 全在 comp_cumcm（6）和 copyright_source_materials（1） |

### 1.5 Provenance 台账覆盖

| 类型 | 应有 | 现有 | 缺口 |
|------|------|------|------|
| `UPSTREAM.md`（外部依赖来源） | 15+ | **1**（codesucker-core） | 94% |
| 外部依赖许可证审计 | 10+ | **1**（check_codesucker_licenses.py） | 90% |
| 工具版本声明 | 46 | **0** | 100% |
| 模板来源记录 | 20+ | **0** | 100% |

### 1.6 Bridge 模式使用情况

| 模式 | 现有 | 说明 |
|------|------|------|
| 稳定适配层（Python bridge） | **1**（codesucker_bridge.py） | 唯一符合设计哲学的接入方式 |
| 直接调用子进程 | 10+ 个工具 | 直接调 LaTeX、drawio、pandoc 等 |
| 直接 import 外部库 | 46 个工具全部 | 无版本记录、无 fallback 策略 |

### 1.7 评分：6 大域 × 6 维度

| 域 | Manifest | Backend声明 | 质量门禁 | JSON输出 | Bridge | Provenance | **总分** |
|---|----------|------------|---------|---------|-------|-----------|--------|
| 知识产权（copyright） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **30/30** |
| 知识产权（patent） | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ | **10/30** |
| 数模竞赛（comp\_cumcm） | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | **12/30** |
| 数模竞赛（其他 21 模板） | ⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | **7/30** |
| 学术论文 | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | **6/30** |
| 文献研究 | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | **6/30** |
| 课程论文/报告 | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | **6/30** |
| 实验研究 | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | **6/30** |
| 通用工具 | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | **6/30** |

---

## 第二部分：系统化升级方案

### 核心模式：三条钢律

```
1. 每个步骤产出 STEP_MANIFEST.json（输入哈希 + 配置 + 输出哈希 + backend 声明）
2. 每个外部依赖有 UPSTREAM.md（来源 + commit + license + 修改记录）
3. 每个关键技能有专属质量门禁（named check）
```

### Phase 1：基础设施（引擎层）

#### 1.1 `engine/step_manifest.py`（新建）

通用 manifest 协议，供所有技能调用：

```python
def write_manifest(workspace: Path, step_name: str, config: dict, 
                   inputs: list[Path], outputs: list[Path], 
                   backend: str, commands: list[dict]) -> Path
def validate_manifest(workspace: Path, manifest_path: str) -> dict
```

输出 `STEP_MANIFEST.json` 格式：

```json
{
  "schemaVersion": 1,
  "stepName": "comp-modeling",
  "executedAt": "2026-08-18T10:00:00Z",
  "backend": "scipy 1.14.1",
  "inputFiles": [{"path": "data/clean.csv", "sha256": "abc..."}],
  "config": {"solver": "HiGHS", "timeLimit": 300},
  "outputFiles": [{"path": "RESULTS.md", "sha256": "def..."}],
  "commands": [{"command": "python code/main.py", "exitCode": 0}],
  "dependencies": {"scipy": "1.14.1", "numpy": "2.4.6"}
}
```

#### 1.2 `engine/quality_gates.py` 扩展

新增通用 gate：
```python
def check_step_manifest(self) -> dict
```
验证 `STEP_MANIFEST.json` 的存在性、schema 版本、必填字段完整性。

新增命名 gate（各域专属）：
```python
check_paper_consistency()      # 论文数字 vs 代码结果，用于 comp-paper-zh/comp-compile-zh
check_citation_integrity()     # 引用 DOI 可解析，用于 comp-literature/paper-write
check_experiment_reproduc()    # 实验可复现，用于 experiment-bridge
check_figure_provenance()      # 图表元数据，用于 paper-figure
check_compilation_log()        # 编译日志门禁，用于 comp-compile-zh/paper-compile
```

#### 1.3 Bridge 模式（稳定适配层）

新建 4 个 bridge：
- `tools/latex_bridge.py` — LaTeX 编译统一入口（`xelatex`/`pdflatex`/`latexmk`） + 版本记录 + 编译日志
- `tools/solver_bridge.py` — 求解器调用（scipy/MIP/ortools） + 版本记录 + 参数哈希
- `tools/citation_bridge.py` — 引用核验（DOI/CrossRef/DOI 回退） + 源记录
- `tools/visual_bridge.py` — 视觉检查（TikZ/drawio/data-fig 统一入口）

每个 bridge 必须：
1. 记录 backend 版本到 manifest
2. 记录输入文件哈希
3. 记录命令和退出码
4. 提供 fallback 策略

### Phase 2：数模竞赛域升级（22 模板）

#### 2.1 核心步骤升级（8 个核心技能）

| 技能 | 新增产物 | 新增 gate | 工作量 |
|------|---------|-----------|--------|
| `comp-prob-analysis` | `STEP_MANIFEST.json`（题面哈希、分析工具版本） | `check_step_manifest` | 小 |
| `comp-modeling` | `STEP_MANIFEST.json`（求解器/版本/参数/输入哈希） | `check_step_manifest` | 中 |
| `comp-code` | `STEP_MANIFEST.json`（依赖清单/solver/运行时间/退出码） | `check_step_manifest` | 中 |
| `comp-paper-zh` | `STEP_MANIFEST.json`（模板版本/TeX Live 版本/引用数） | `check_paper_consistency` | 中 |
| `comp-paper-en` | 同上英文版 | 同上 | 中 |
| `comp-compile-zh` | `STEP_MANIFEST.json`（xelatex 版本/ctex 版本/页数/警告数） | `check_compilation_log` | 中 |
| `comp-compile-en` | 同上英文版 | 同上 | 中 |
| `comp-review` | `STEP_MANIFEST.json`（审稿人模型/session_id/审查轮次） | 现有 `check_review_evidence` | 小 |

#### 2.2 comp_cumcm 模板升级

当前已有 6 个 required_checks。增加：
- 步骤 3（comp-modeling）：`required_checks: ["step_manifest"]`
- 步骤 4（comp-code）：`required_checks: ["step_manifest"]`
- 步骤 5（paper-figure）：`required_checks: ["figure_provenance"]`
- 步骤 7（comp-paper-zh）：`required_checks: ["step_manifest", "paper_consistency"]`
- 步骤 8（comp-compile-zh）：`required_checks: ["step_manifest", "compilation_log"]`

#### 2.3 其他 21 个数竞模板统一升级

所有模板（comp_apmcm, comp_mcm, comp_huawei 等）的 8 个步骤：
- 增加 `metadata.requires_subagent` 到审稿步骤（当前为 0）
- 增加 `required_checks: ["step_manifest"]` 到建模/代码/论文步骤
- 增加 `metadata` 字段记录步骤元数据

### Phase 3：学术论文域升级（7 模板）

| 技能 | 升级内容 |
|------|---------|
| `paper-write` | `STEP_MANIFEST.json`（模板来源哈希、BibTeX 条目数、引用格式） |
| `paper-write-zh` | 同上中文版 |
| `paper-write-nature` | `STEP_MANIFEST.json` + Nature 模板版本 + 格式检查结果 |
| `paper-figure` | `STEP_MANIFEST.json`（每张图的数据源、脚本、colormap、参数） |
| `paper-figure-html` | 同上（HTML 渲染版） |
| `paper-figure-drawio` | 同上（drawio 版） |
| `paper-compile` | `STEP_MANIFEST.json`（LaTeX 引擎版本、包版本、编译警告） |
| `paper-compile-zh` | 同上中文版 |

### Phase 4：其他域升级

#### 4.1 文献研究域

| 技能 | 升级内容 |
|------|---------|
| `literature-review` | `STEP_MANIFEST.json`（搜索词、源 API、结果数、fallback 链） |
| `research-lit` | `STEP_MANIFEST.json`（搜索源、API 状态、请求耗时） |
| `novelty-check` | `STEP_MANIFEST.json`（对比文献 DOI、相似度阈值） |
| `idea-discovery` | `STEP_MANIFEST.json`（搜索参数、源、fallback 链） |

#### 4.2 知识产权域（patent 追平 copyright）

| 技能 | 升级内容 |
|------|---------|
| `patent-draft` | `STEP_MANIFEST.json`（草图来源、工具版本） |
| `patent-build` | `STEP_MANIFEST.json`（渲染引擎版本、截图方式） |
| `patent-draft` SKILL.md | 增加真实材料 mode 下的 manifest 读取要求 |
| `patent-build` SKILL.md | 增加 manifest 存在性校验 |

#### 4.3 实验研究域

| 技能 | 升级内容 |
|------|---------|
| `experiment-bridge` | `STEP_MANIFEST.json`（环境依赖、随机种子、GPU 信息、运行时间） |
| `experiment-plan` | `STEP_MANIFEST.json`（实验设计参数、消融矩阵） |
| `run-experiment` | `STEP_MANIFEST.json`（服务器信息、运行日志、退出码） |

#### 4.4 课程/报告域

| 技能 | 升级内容 |
|------|---------|
| `course-paper` | `STEP_MANIFEST.json`（模板版本、引用数） |
| `course-report` | `STEP_MANIFEST.json`（项目事实哈希、引用数） |
| `thesis-proposal` | `STEP_MANIFEST.json`（文献数量、模板版本） |

### Phase 5：Provenance 台账

#### 5.1 UPSTREAM.md 清单（15+ 个）

需新建的源码来源记录文件：

| 文件路径 | 记录内容 |
|---------|---------|
| `skills/paper-write/templates/UPSTREAM.md` | NeurIPS/ICML/ICLR 模板来源 commit |
| `skills/comp-paper-zh/references/UPSTREAM.md` | 国赛模板来源 |
| `skills/comp-paper-en/references/UPSTREAM.md` | MCM/COMAP 模板来源 |
| `tools/humanize_chinese/UPSTREAM.md` | voidborne-d/humanize-chinese 来源 |
| `tools/docx-cn-engine/UPSTREAM.md` | Node 引擎来源 |
| `tools/docx_style_profiles/UPSTREAM.md` | 各样式 profile 来源 |
| `data/UPSTREAM.md` | 参考数据来源（historical_papers 等） |
| `skills/nature-figure/references/UPSTREAM.md` | Nature 图表风格指南来源 |
| `skills/paper-write-nature/references/UPSTREAM.md` | Nature 模板来源 |
| `skills/patent-draft/references/UPSTREAM.md` | 专利模板来源 |
| `skills/copyright-draft/references/UPSTREAM.md` | 软著模板来源（已有部分） |
| 各竞赛模板 `comp-*/references/UPSTREAM.md` | 竞赛规则/模板来源 |

#### 5.2 许可证审计工具扩展

`tools/check_codesucker_licenses.py` → 通用化重命名为 `tools/check_provenance.py`，支持：
- 检查所有 `UPSTREAM.md` 文件的存在性和格式
- 检查所有外部依赖的 LICENSE 文件
- 生成许可证审计报告

### Phase 6：模板元数据标准化

#### 6.1 所有模板补全 metadata 字段

当前所有 39 个模板的 metadata 为空。需为每个步骤补全：

```json
{
  "metadata": {
    "requires_subagent": true,    // 审稿/审查类步骤
    "required_checks": ["step_manifest", "..."],  // 按技能类型
    "display_name": "..."
  }
}
```

#### 6.2 审稿步骤补全 requires_subagent

当前 0 个模板使用 `requires_subagent`。需为以下步骤补全：
- 所有 `comp-review` 步骤（22 个竞赛模板）
- 所有 `comp-visual-review` 步骤
- 所有 `comp-final-review` 步骤
- `auto-review-loop` 步骤

### 工作量估算

| Phase | 主题 | 新增文件 | 修改文件 | 工作量 |
|-------|------|---------|---------|--------|
| P1 | 引擎基础设施 | 3（step_manifest + 4 bridge） | 2（quality_gates + workflow_runner） | ~3 天 |
| P2 | 数模竞赛域（22 模板） | 0 | 22（templates.json）+ 8（SKILL.md）+ 8（工具） | ~5 天 |
| P3 | 学术论文域（7 模板） | 0 | 7（templates.json）+ 8（SKILL.md）+ 8（工具） | ~3 天 |
| P4 | 其他域（文献/知产/实验/课程） | 0 | 15+（SKILL.md）+ 4（工具） | ~4 天 |
| P5 | Provenance 台账 | 15+ UPSTREAM.md | 1（check_provenance.py） | ~2 天 |
| P6 | 模板元数据标准化 | 0 | 39（templates.json） | ~1 天 |

**总计：约 18 个工作日，可并行进行。**

### 升级策略

1. **P1 是前置依赖**：必须先完成 manifest 协议和 bridge 模式，后续各域升级才能统一调用。
2. **P2-P4 可并行**：各域升级互不依赖，可分配给不同开发者/子智能体。
3. **P5 可并行**：台账是文档工作，不依赖代码变更。
4. **P6 可并行**：模板元数据修改不涉及工具逻辑。
5. **测试门禁**：每个 Phase 完成后运行 `pytest tests/ -q` 确保 43 项验收通过，套件 `pytest -q` 确保 178 项通过。