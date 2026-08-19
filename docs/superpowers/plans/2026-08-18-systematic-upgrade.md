# 系统级"CodeSucker 标准"升级计划

> 目标：让全系统所有技能达到 CodeSucker 融合的设计哲学完整度

## 零、当前差距全景

| 维度 | CodeSucker 标准 | 其他 5 大域 | 差距 |
|------|----------------|------------|------|
| **STEP_MANIFEST（输入/配置/输出哈希）** | ✅ `SOURCE_MATERIALS_MANIFEST.json` | ❌ 无任何 manifest | **全系统缺失** |
| **Backend 声明** | ✅ `backend: vendored-codesucker-core` | ❌ 不记录求解器/编译器/引擎版本 | **全系统缺失** |
| **版本/commit 追踪** | ✅ `coreVersion`, `coreCommit` | ❌ 不记录工具版本 | **全系统缺失** |
| **上游来源记录** | ✅ `UPSTREAM.md` | ❌ 0 个 UPSTREAM.md | **全系统缺失** |
| **专属质量门禁** | ✅ `check_source_materials()` | ⚠️ 只有通用门禁（min_size/companions） | **大差距** |
| **JSON 输出协议** | ✅ `files.json`, `selection.json`, `audit.json` | ❌ 只有自由格式 markdown | **全系统缺失** |
| **稳定适配层（bridge）** | ✅ `codesucker_bridge.py` | ❌ 直接调用工具/命令 | **全系统缺失** |
| **升级同步工具** | ✅ `sync_codesucker_core.py` | ❌ 无 | **全系统缺失** |
| **许可证审计** | ✅ `check_codesucker_licenses.py` | ❌ 无 | **全系统缺失** |

## 一、基础设施层（Phase 1）

### 1.1 `STEP_MANIFEST` 协议（核心）

**目标**：每个技能步骤产出 `STEP_MANIFEST.json`，标准化记录执行上下文。

```json
{
  "schemaVersion": 1,
  "stepName": "comp-modeling",
  "executedAt": "2026-08-18T10:00:00Z",
  "backend": "scipy 1.14.1",
  "inputFiles": [
    {"path": "data/clean.csv", "sha256": "abc123..."}
  ],
  "config": {
    "solver": "HiGHS",
    "timeLimit": 300
  },
  "outputFiles": [
    {"path": "RESULTS.md", "sha256": "def456..."},
    {"path": "figures/all_results.json", "sha256": "ghi789..."}
  ],
  "commands": [
    {"command": "python code/main.py --solver HiGHS", "exitCode": 0}
  ],
  "dependencies": {
    "scipy": "1.14.1",
    "numpy": "2.4.6"
  }
}
```

**实现**：
- `engine/step_manifest.py` — 新建模块，提供 `write_manifest()` 和 `validate_manifest()` 函数
- 所有技能 SKILL.md 增加"必须产出 STEP_MANIFEST.json"的硬性要求
- `quality_gates.py` 增加通用 `check_step_manifest()` 门禁

### 1.2 Bridge 模式（稳定适配层）

**目标**：每个外部依赖有独立的 Python bridge 模块，隔离实现细节。

**新增**：
- `tools/latex_bridge.py` — LaTeX 编译的稳定入口（`xelatex`/`pdflatex`/`latexmk` 统一调用 + 版本记录）
- `tools/solver_bridge.py` — 求解器调用（scipy/MIP/ortools 统一入口 + 版本记录）
- `tools/citation_bridge.py` — 引用核验（DOI/CrossRef 统一入口 + 源记录）
- `tools/visual_bridge.py` — 视觉检查工具（TikZ/drawio/data-fig 统一入口）

### 1.3 Quality Gate 扩展

**目标**：每个关键技能有专属门禁。

**新增命名门禁**：
- `check_paper_consistency()` — 论文数字 vs 代码结果一致性强制校验
- `check_citation_integrity()` — 引用 DOI 可解析性强制校验
- `check_experiment_reproducibility()` — 实验可复现性校验
- `check_step_manifest()` — 通用 manifest 存在性校验
- `check_figure_manifest()` — 图表元数据校验

### 1.4 Provenance 台账

**目标**：所有外部依赖有 `UPSTREAM.md` 来源记录。

**需新增**（估计 15+ 个）：
- `skills/paper-write/templates/UPSTREAM.md` — NeurIPS/ICML/ICLR 模板来源
- `skills/comp-paper-zh/references/UPSTREAM.md` — 竞赛模板来源
- `tools/humanize_chinese/UPSTREAM.md` — 外部工具来源
- `tools/docx-cn-engine/UPSTREAM.md` — Node 引擎来源
- `data/UPSTREAM.md` — 参考数据来源
- 等等

## 二、按域升级路线图（Phase 2-4）

### Phase 2：数学建模竞赛域（最高优先级，用户最常用）

| 技能 | 当前 | 升级后 |
|------|------|--------|
| `comp-prob-analysis` | 产出 `PROBLEM_ANALYSIS.md` | + `STEP_MANIFEST.json`（含题面文件哈希、分析工具版本） |
| `comp-modeling` | 产出 `MODELING_REPORT.md` | + `STEP_MANIFEST.json`（含求解器/版本/参数、输入数据哈希、模型方程摘要） |
| `comp-code` | 产出 `code/main.py` + `RESULTS.md` | + `STEP_MANIFEST.json`（含 Python 依赖清单、solver 版本、运行时间、退出码） |
| `comp-paper-zh` | 产出 `paper/main.tex` | + `STEP_MANIFEST.json`（含模板版本、TeX Live 版本、引用数） |
| `comp-compile-zh` | 产出 `paper/main.pdf` | + `STEP_MANIFEST.json`（含 xelatex 版本、ctex 版本、页数） |
| `comp-review` | 产出 `COMP_REVIEW.md` | + `STEP_MANIFEST.json`（含审稿人模型、session_id、审查轮次） |

**新增模板门禁**：`comp-modeling` 和 `comp-compile-zh` 的 `required_checks` 清单增加 `step_manifest`。

### Phase 2：学术论文域

| 技能 | 升级内容 |
|------|---------|
| `paper-write` | manifest 含模板来源哈希、BibTeX 条目数 |
| `paper-figure` | manifest 含每张图的数据源、脚本、colormap、参数 |
| `paper-compile` | manifest 含 LaTeX 引擎版本、包版本、编译警告计数 |
| `paper-write-nature` | manifest 含 Nature 模板版本、格式检查结果 |

### Phase 2：知识产权域（patent 跟进 copyright 标准）

| 技能 | 升级内容 |
|------|---------|
| `patent-draft` | manifest 含草图来源、工具版本 |
| `patent-build` | manifest 含渲染引擎版本、截图方式 |

### Phase 3：文献研究域

| 技能 | 升级内容 |
|------|---------|
| `literature-review` | manifest 含搜索词、源 API、结果数、fallback 链 |
| `research-lit` | manifest 含搜索源、API 状态、每次请求的响应时间 |
| `novelty-check` | manifest 含对比文献 DOI、相似度阈值 |

### Phase 3：实验研究域

| 技能 | 升级内容 |
|------|---------|
| `experiment-bridge` | manifest 含环境依赖、随机种子、GPU 信息、运行时间 |
| `experiment-plan` | manifest 含实验设计参数、消融矩阵 |

### Phase 4：通用工具域

| 技能 | 升级内容 |
|------|---------|
| `docx-export` | manifest 含 pandoc/引擎版本、样式 profile 哈希 |
| `sci-pdf` | manifest 含每步操作（合并/拆分/加密）的日志 |
| `latex-document` | manifest 含模板来源、编译引擎版本 |

## 三、预计工作量

| Phase | 主题 | 新增文件 | 修改文件 | 预估工作量 |
|-------|------|---------|---------|-----------|
| P1 | 基础设施（manifest 协议、bridge 模式、gate 扩展） | 5-8 | 10-15 | 大（但有可复用的参考实现） |
| P2 | 数模竞赛域 + 论文域 + 知识产权域 | 15-20 | 20-30 | 最大（但模式重复，可批量处理） |
| P3 | 文献域 + 实验域 | 10-15 | 15-20 | 中 |
| P4 | 通用工具域 + provenance 台账 | 15+ | 5-10 | 中（台账是文档工作，非代码） |

## 四、关键约束

1. **不破坏现有工作流**：manifest 是附加产物，不影响现有 `complete_step()` 逻辑。quality gate 增加 `check_step_manifest` 后，旧工作流不会自动触发（需模板显式声明 `required_checks`）。
2. **渐进式升级**：每个技能独立升级，不必全系统同时完成。升级顺序按用户优先级。
3. **CodeSucker 为参考实现**：`step_manifest.py` 的 API 设计参考 `codesucker_bridge.py` 的 manifest 模式。
4. **测试先行**：每个新 gate 和 manifest 协议必须有对应的 `test_step_manifest.py` 测试。