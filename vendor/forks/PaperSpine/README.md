<p align="center">
  <img src="website/assets/brand/paperspine-mark.svg" width="112" alt="PaperSpine 山脊印章标志">
</p>

# PaperSpine

[English](README.en.md) | [中文](README.md)

[**PaperSpine 使用讲解视频（Bilibili）**](https://www.bilibili.com/video/BV1rjVa6ZEYu)

配音贡献：[https://github.com/YiShanZheng](https://github.com/YiShanZheng)

[**🌍 社区 Stargazer 星图 · 公开 GitHub 社区信号**](https://wubing2023.github.io/PaperSpine/)

## PaperSpine5 发布候选版

PaperSpine5 `0.3.0-rc.1` 在保留本仓库 V4 安装与更新身份的基础上，增加五阶段本地科研生产工作区。请从[中文发布页](https://wubing2023.github.io/PaperSpine/v5/)开始：先把完整的零起点安装指令交给 AI，也可以按宿主选择 Codex、Claude Code 或 DSH 插件包。[GitHub prerelease](https://github.com/WUBING2023/PaperSpine/releases/tag/v0.3.0-rc.1)提供四个原样 ZIP、SHA-256、manifest 与验证证据。

V5 当前是显式选择的 RC，不会替换 V4 的 `dist/paperspine_version.json` 更新源。更新检查默认关闭；发布软件也不代表授权任何论文外部投稿。精确范围、限制与回滚方式见 [`RELEASE-NOTES-v0.3.0-rc.1.md`](RELEASE-NOTES-v0.3.0-rc.1.md) 和 [`ROLLBACK.md`](ROLLBACK.md)。


> PaperSpine 是一个以「贡献为先、面向审稿人」为核心的学术写作系统，支持 Claude Code、Codex、OpenClaw 和 Hermes CLI 四个宿主。

它适合目标格式很重要的写作任务：期刊论文、会议论文、课程或技术报告、综述、竞赛论文。PaperSpine 要求 agent 先学习目标场景和优秀样例，先和用户确认论文的「贡献」，再逐单元设计文章，最后才写作或重建稿件，并输出 LaTeX / PDF / Word。

V4 不再是 12 个扁平 worker skill 的套件，而是 **一个** 名为 `paper-spine` 的编排 skill：12 个阶段的路由都在 `SKILL.md` 内完成，每个阶段读取 `references/` 下对应的 playbook，角色信息放在 `agents/` 中。

## 仓库结构

```text
PaperSpine/
  src/                          # 唯一真源
    skill/
      SKILL.md                  # 单一 paper-spine 编排 skill（含 12 阶段路由）
      references/               # 各阶段 playbook（40+ 篇）
      agents/                   # 角色卡（研究、审稿人等）
    scripts/                    # 确定性辅助与关卡脚本
    adapters/                   # 各宿主适配（claude / codex / hermes）
  dist/                         # 由 sync 从 src/ 生成（不要手改）
    claude/skills/paper-spine/  # Claude Code 单 skill
    claude/commands/paperspine.md
    codex/skills/paper-spine/   # Codex 单 skill
    codex/prompts/paperspine.md
    openclaw/skills/paper-spine/ # OpenClaw 单 skill
    hermes/skills/academic-writing/paper-spine/  # Hermes CLI 单 skill
    paperspine_version.json     # 版本元数据（4.0.0）
  .claude-plugin/               # Claude Code 插件元数据
  install.ps1                   # Windows 安装器（薄包装）
  install.sh                    # macOS / Linux 安装器（薄包装）
  README.md
  README.en.md
```

`src/` 是唯一真源，`dist/` 完全由同步脚本 `src/scripts/sync_local_installs.py` 从 `src/skill` + `src/scripts` + `src/adapters` 生成。不要直接编辑 `dist/`。

## 快速安装

Windows PowerShell：

```powershell
git clone https://github.com/WUBING2023/PaperSpine.git
cd PaperSpine
.\install.ps1
```

macOS / Linux：

```bash
git clone https://github.com/WUBING2023/PaperSpine.git
cd PaperSpine
bash install.sh
```

`install.ps1` 和 `install.sh` 都是薄包装，统一委托给 `src/scripts/sync_local_installs.py`：脚本会先从 `src/` 生成 `dist/`，再把同一个 `paper-spine` skill 安装到四个宿主。它对 PowerShell 5.1 友好，并且 **永不写入 settings.json**（修复了 issue #3 中旧安装器抹掉 settings.json 的问题）。

清理旧版残留：

```powershell
.\install.ps1 -CleanLegacy
```

```bash
bash install.sh --clean-legacy
```

`-CleanLegacy` / `--clean-legacy` 会清理旧 PaperSpine 目录和遗留的 `paper-spine-*` worker 副本，避免重复发现或找不到 skill。安装器会把当前版本写入 `~/.paperspine/install_state.json`，并保留 `~/.paperspine/config.json`（含 UI 语言等全局配置）。

## 四个宿主

同一个 `paper-spine` skill 被安装到四个宿主，互不混用：

| 宿主 | 安装位置 | 常用入口 |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/paper-spine` + `~/.claude/commands/paperspine.md` | `/paperspine` 命令 |
| Codex | `~/.codex/skills/paper-spine` + `~/.codex/prompts/paperspine.md` | `/paperspine` prompt |
| OpenClaw | `~/.openclaw/skills/paper-spine` | `paper-spine` |
| Hermes CLI | `~/AppData/Local/hermes/skills/academic-writing/paper-spine` | `paper-spine` |

对应的 `dist/` 来源分别是 `dist/claude/skills`、`dist/claude/commands`、`dist/codex/skills`、`dist/openclaw/skills` 和 `dist/hermes/skills/academic-writing`。安装后请重启或 reload 对应宿主。不要把整个仓库直接复制进 `skills` 文件夹——那是重复或缺失 skill 的主要原因。

## /paperspine 入口

在 Claude Code 和 Codex 中，推荐统一用：

```text
/paperspine
```

当 `paper_rewriting_output/paper_spine_config.json` 缺失时，这个入口会自动启动外部终端 intake UI 来收集配置，而不是让用户手写 JSON。兜底方式是 Python wizard：

```powershell
python src/scripts/intake_wizard.py
```

配置完成后会生成：

```text
paper_rewriting_output/paper_spine_config.json
paper_rewriting_output/paper_spine_config.md
```

OpenClaw 和 Hermes CLI 没有 slash 入口，直接调用 `paper-spine` skill 即可，缺配置时同样会引导走 intake。

## Claude Code 插件安装

Claude Code 也可以用 `.claude-plugin` 中的插件元数据：

```text
/plugin marketplace add https://github.com/WUBING2023/PaperSpine
/plugin install paper-spine
/reload-plugins
```

插件 manifest 指向 `dist/claude/skills` 下的单一 `paper-spine` skill。

## 主工作流

PaperSpine 有两条平级主流程：

1. **Rewrite Existing**：改进已有论文或报告，但不把任务降级成简单润色。
2. **Build From Materials**：从素材文件夹构筑论文或报告，素材可以包括说明文档、图片、PDF、数据摘要、部分初稿和实验描述。

支持四类目标场景：

- `journal`：期刊论文
- `conference`：会议论文
- `report_review`：课程报告、技术报告或综述
- `competition`：竞赛论文或竞赛报告

研究深度：

- `flash`：3 篇目标场景样例、3 篇近期/高质量同领域论文和官方要求。
- `pro`：6 篇目标场景样例、6 篇近期/高质量同领域论文和官方要求。

输出语言为 `en` 或 `zh`。选择英文输出时，可通过 `translation_package=zh` 额外生成中文翻译包，并产出最终中文 Word 文档。

## 方法论升级（V4）

V4 在原有的 motivation 主线之上，引入三条由关卡强制执行的核心规则。motivation 仍然必需（`confirmed_motivation.md`），但它现在服务于「贡献」，而不再是顶层组织单元。

1. **Contribution-First（贡献为先）**：稿件最高优先级的组织单元是已确认的贡献。在 `confirmed_contribution.md` 存在之前不得开始实质写作。关卡：`contribution_check.py`。
2. **Results-as-Validation（结果即验证）**：每个主要 Results 子节都必须验证至少一条贡献承诺，只有指标、没有映射到贡献的单元视为失败，记录于 `results_validation.md`。关卡：`results_validation_check.py`。
3. **Reviewer-Aware（面向审稿人）**：在声称「可投稿」之前，必须基于三个审稿人角色生成 `reviewer_audit.md`（审稿人价值图 + 异议登记 + 期刊匹配）。关卡：`reviewer_audit_check.py`。

第 12 阶段的最终审计硬关卡会一次性运行这三个检查，任一失败都不得宣布完成。

## 12 阶段编排

`paper-spine` 编排 skill 不直接修句子，而是逐阶段路由，每个阶段读取 `references/` 下的 playbook：

1. **Intake**：校验 `paper_spine_config.json`。
2. **Research**：学习目标场景、本地/指定参考资料和优秀样例。
3. **Citation**：构建 claim 级别的引用支持库。
4. **Motivation Confirmation**：停下等用户确认控制性 motivation（BLOCKED，不自动选择）。
5. **Humanize**（按需）：按 tier 应用去 AI 痕迹约束。
6. **Writing / Drafting**：rewrite 或 build，先产出蓝图与写作思路矩阵。
7. **Integrity Audit**：LaTeX 组装前的完整性审计。
8. **LaTeX / PDF / Word**：生成并检查 LaTeX、可用时编译 PDF，并产出 Word。
9. **Submission Package**（按需）：highlights、cover letter 等投稿材料。
10. **Translation Package**（按需）：英文输出时产出 `translation_zh/` 翻译包及最终中文 Word。
11. **Review Response**（按需）：生成审稿意见回复。
12. **Final Audit**：完成度硬关卡，所有检查通过才算完成。

每个阶段都是一道关卡，由 `progress_check.py --gate <stage>` 把守；关卡失败就路由回该阶段，不允许跳过或手写缺失产物。历史上的 `paper-spine-research` 等 worker 名称只是遗留别名，不再是用户入口。

## V4 新能力

- **阶段关卡 + 断点续跑**：`progress_check.py` 提供逐阶段 gate，并支持从第一个未完成阶段 `resume` 续跑，不必从头重来。
- **投稿材料包**：`submission_check.py` 校验 highlights、cover letter 等投稿材料。
- **审稿意见回复**：`respond_check.py` 协助生成结构化的 review response。
- **英文引用核验**：`citation_verification_en.py` 对英文稿件中的引用进行核验。
- **更深的去 AI 痕迹（humanize）**：`humanize_check.py` 按 `light` / `medium` / `heavy` 分级，输出 D1–D5 五个维度的可测量指标，区分必过项与建议项。

## 本地参考文献读取

参考材料获取不再只依赖网络。配置字段 `reference_mode` 控制 PaperSpine 如何开始文献和样例读取：

- `local_first`：默认。先索引当前工作文件夹中的参考材料，再按需进行网络补充。
- `specified_paths`：只索引 `reference_paths` 中指定的文件夹或文件，再按任务需要补充。
- `web`：用户没有本地参考材料时使用网络收集。

本地参考路径会写入 `paper_rewriting_output/reference_materials/source_index.md`。辅助脚本：

```powershell
python src/scripts/reference_inventory.py . --output-dir paper_rewriting_output --mode local_first
```

PaperSpine 可以读取用户提供的 PDF、下载论文、BibTeX/RIS、模板、笔记、学校或竞赛文档。它不能绕过付费墙或私有数据库权限。

## 引用支持库

Citation 阶段会生成 `paper_rewriting_output/citation_support_bank.md`。它和优秀论文学习是两件事：样例论文用于学习结构和写法；引用支持库用于为 Introduction、Related Work、Discussion、局限性、应用背景等位置提供可选择的候选引用。

默认行为：

- `citation_target_count`：`20`
- 候选池：`citation_target_count * 3`，默认 `60`
- 近期论文目标：约 `80%` 候选来自近三年（2026 年的简单阈值是 2023 年及以后）
- 每一行候选都必须包含参考文献/BibTeX 风格信息、年份、来源，以及一两句可以支撑正文论述的句子

检查引用库：

```powershell
python src/scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --target-count 20 --markdown
```

## 关键产物

一次完整运行不应该只有最终论文，而应留下完整可审计的写作轨迹：

```text
paper_rewriting_output/
  paper_spine_config.json
  paper_spine_config.md
  reference_materials/source_index.md
  research_dossier.md
  exemplar_learning_dossier.md
  style_profile.md
  sota_gap_map.md
  motivation_options_after_research.md
  citation_support_bank.md
  confirmed_motivation.md
  confirmed_contribution.md       # V4 贡献为先
  results_validation.md           # V4 结果即验证
  reviewer_audit.md               # V4 面向审稿人
  section_blueprints.md
  writing_rationale_matrix.md
  latex_report.md
  final_artifact_manifest.md
  final_paper/
    main.tex
    references.bib
    figures/
    paper.pdf                     # 本机有 LaTeX 编译器时生成
    paper.docx                    # 英文 Word 输出
    paper.zh.docx                 # output_language=zh 或翻译包时生成
  submission_package/             # 请求投稿材料时
  review_response/                # 请求审稿回复时
  translation_zh/                 # translation_package=zh 时
```

最核心产物是 `writing_rationale_matrix.md`。它必须按真实论文或报告结构逐单元解释：该单元承担什么功能、如何服务确认后的贡献与 motivation、学习了哪些 SOTA 或目标场景样例、使用了哪些证据、最终文本应通过什么检查。`citation_support_bank.md` 是第二个重要推理产物，它让每个候选引用在进入正文前先绑定到一个具体句子级 claim。

## 检查命令

检查产物完整性：

```powershell
python src/scripts/artifact_check.py paper_rewriting_output --markdown --write
```

各阶段关卡与方法论硬关卡：

```powershell
python src/scripts/progress_check.py paper_rewriting_output --gate final_audit
python src/scripts/contribution_check.py paper_rewriting_output --markdown --write
python src/scripts/results_validation_check.py paper_rewriting_output --markdown --write
python src/scripts/reviewer_audit_check.py paper_rewriting_output --markdown --write
python src/scripts/integrity_audit.py paper_rewriting_output --markdown --write
```

检查 LaTeX 与 Word：

```powershell
python src/scripts/latex_guard.py paper_rewriting_output/final_paper/main.tex --markdown
python src/scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --markdown
```

检查本地参考索引与引用候选覆盖：

```powershell
python src/scripts/reference_inventory.py . --output-dir paper_rewriting_output --mode local_first
python src/scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --target-count 20 --markdown
```

运行项目测试：

```powershell
python -m pytest tests -q
```

## 更新 PaperSpine

> ⚠️ **从 3.x 升级到 4.0 请手动重装，自更新不适用。** 4.0 把原来的 12 个子技能收敛成单一 `paper-spine` orchestrator，3.x 的更新器会把新包判为「缺 11 个 skill」而中止。**跑一次安装脚本，务必带 `--clean-legacy`**（否则旧的 worker skill 会残留，cc switch 里会新旧混杂）：
>
> - Windows：`powershell -File install.ps1 -CleanLegacy`
> - macOS/Linux：`bash install.sh --clean-legacy`
>
> 装完 `--check-only` 会显示 `already latest: 4.0.0`，之后自更新恢复正常。4.0 起的更新器已前向容错，不会再因文档改名等原因中止。

第一次安装之后，如果想检查或更新本地安装，可以在宿主里让 `paper-spine` 走 update 路由（`/paperspine update`），它会运行：

```powershell
python src/scripts/paperspine_update.py --yes
```

它会把 `~/.paperspine/install_state.json` 中记录的版本和 GitHub `main` 上的 `dist/paperspine_version.json` 进行比较。已是最新版会直接提示；发现新版本时会下载 GitHub 压缩包、校验 PaperSpine 目录结构，然后同步更新四个宿主的 `paper-spine` skill，并保留 `~/.paperspine/config.json`。只想检查而不修改本地安装：

```powershell
python src/scripts/paperspine_update.py --check-only
```

**仍报 "incomplete"?** 任何旧版本自更新到新版报 `Downloaded PaperSpine package is incomplete`，都是**旧版校验器拒收新版包**导致的（升级跑的是本地旧校验器，issue #13）。按上面的手动重装即可打通；也可直接从 `main` 复制 `dist/claude/skills/*` 与 `dist/claude/commands/paperspine.md` 到 `~/.claude/skills/`、`~/.claude/commands/`。4.0.0 起的更新器对可选文件（README / 安装脚本）只告警不中止，此问题不再复发。

## PaperSpine 试图避免的问题

- 只改句子，不改论文逻辑或贡献。
- 没确认贡献和 motivation 就开始写。
- Results 只堆指标，却不验证任何一条贡献承诺。
- 在没做面向审稿人审计的情况下声称「可投稿」。
- 添加没有证据支撑的 claim。
- 只输出 `main.tex`，但不解释为什么这样设计文章，也不产出 Word。
- 用户要求翻译包时，只翻译一部分中间产物。

## License

MIT License. See [LICENSE](LICENSE).

## 贡献者

- [Wubin2023](https://github.com/WUBING2023) — PaperSpine 发起者、V1–V4 核心贡献者与维护者，主导项目的设计、开发与持续迭代。
- [ZHOUYUNCHEN](https://github.com/ZHOUYUNCHEN) — V4 早期协作者。
