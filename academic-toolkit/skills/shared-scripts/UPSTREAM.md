# shared-scripts 共享脚本级台账（modex-3 同源吸收批次）

> 覆盖范围：2026-09-10 自 Modex v3 技能包吸收的共享脚本与规范（双副本与 `_utils/` 同步）：
> `mechanism_accuracy_addendum.md`、`ai_disclosure_rules.md`、`build_ai_disclosure.py`、
> `paper_source_scope.py`、`ai_tell_check.py`、`human_paper_style_check.py`、
> `human_competition_paper_style.md`；及 `comp-code/references/checks/` 六份增补块。

- Upstream: Modex-MH-Agent v3 技能包（本地分发件 `modex-3-skills/`，用户 2026-09-10 放入仓库根；本仓技能库 v1 与其同源——源自 Modex-MH-Agent 解密复刻，见 dev-docs/解析/ 溯源链）
- Pinned commit: 2026-09-10（本地包无 git 历史，以吸收日期+内容指纹为准；吸收文件 sha256 记录于 LOG 对应条目）
- Checklist date: 2026-09-10
- License: 同源私有升级（本仓 v1 即源自 Modex 解密复刻，无第三方再分发义务；本仓整体许可口径 CC-BY-NC-4.0 不变）
- Local adaptation: 工具/规范类按本仓共享脚本双副本惯例同步（_utils + shared-scripts，`test_dual_copy_consistency` 守护）；checks 六份走"增补附录"合并（本仓治理改造与 validate_capability/AUDIT_OK 契约衔接保留，modex-3 独有条目原样收录并标注来源）；comp-modeling/comp-prob-analysis/comp-paper-zh/comp-code checks/_index 增加按需路由段（本仓路径写法）

## Upgrade rule

Modex 后续版本更新时，对照本批次文件逐个 diff，仍按"本仓契约保留 + 增量收录"方式吸收；吸收后更新本文件日期并复跑双副本一致性测试。

## 2026-09-22 P1 扫尾批次（compile_check.sh / writing_check.sh 双向取长）

- `compile_check.sh`：库内版为基线，吸收上游独有块——`CHECKS_UNAVAILABLE` 退出码 3 机检块、
  `run_python_check` 包装、`paper_source_scope.py`/`compile_source_check.py` 依赖存在性校验与
  活跃源清单（`ACTIVE_TEX`→`TEX_SRC`，解析为空回退库内 glob 口径）、`MH_PYTHON` 软探测
  （带宿主中立回退 python/python3/py）。库内独有 `gcount()` 计数消毒与 `PYTHON="python3"`
  兜底全部保留。
- `writing_check.sh`：整替为上游 42 行编排器（委派 `writing_source_check.py`、
  `figure_narrative_check.py`、`modeling_tex_policy.py`、`assumption_layout_check.py`、
  `symbol_layout_check.py`、`abstract_emphasis_check.py`、`human_paper_style_check.py`、
  `ai_tell_check.py` 共 8 个检查器；`--supplemental` 仅跑 `writing_source_check.py`）。
  8 个 py 在 `_utils/` 与 `shared-scripts/` 实测全部在位（除 `abstract_emphasis_check.py`
  为本仓本地版外均与上游逐字节一致），无悬空委派。
- 双副本 sha256 已对齐；两脚本 `bash -n` 通过并在样例 paper/ 上冒烟实测。
