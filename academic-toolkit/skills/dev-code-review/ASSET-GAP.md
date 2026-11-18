# ASSET-GAP 资产缺口声明 — dev-code-review

> 状态：**已全部补齐销账（2026-11-17 裁决第二批）**。本文件保留作销账台账，不再声明任何在盘缺失资产。
> 上游真源：`alirezarezvani/claude-skills` @ `4680893d91f2aee6f77ca1519fd1b86b7a104c87`（`engineering-team/skills/code-reviewer/`，MIT）——2026-11-17 检索定位，推翻本文件早期「2026-09-09 溯源未检索到对应仓库」的结论。

## 原缺失资产清单（19 项，均已补齐）

- `assets/sample_java_smells.java` — ✅ 2026-11-17 原样收编
- `scripts/code_quality_checker.py` — ✅ 2026-11-17 原样收编
- `scripts/pr_analyzer.py` — ✅ 2026-11-17 原样收编
- `scripts/review_report_generator.py` — ✅ 2026-11-17 原样收编
- `rules/universal.md` — ✅ 2026-11-17 原样收编
- `languages/python.md` — ✅ 2026-11-17 原样收编
- `languages/typescript.md` — ✅ 2026-11-17 原样收编
- `languages/go.md` — ✅ 2026-11-17 原样收编
- `languages/swift.md` — ✅ 2026-11-17 原样收编
- `languages/kotlin.md` — ✅ 2026-11-17 原样收编
- `languages/csharp.md` — ✅ 2026-11-17 原样收编
- `languages/java.md` — ✅ 2026-11-17 原样收编
- `languages/c.md` — ✅ 2026-11-17 原样收编
- `languages/cpp.md` — ✅ 2026-11-17 原样收编
- `languages/rust.md` — ✅ 2026-11-17 原样收编
- `languages/ruby.md` — ✅ 2026-11-17 原样收编
- `languages/php.md` — ✅ 2026-11-17 原样收编
- `languages/dart.md` — ✅ 2026-11-17 原样收编
- `expected_outputs/sample_java_smells_quality.json` — ✅ 2026-11-17 收编并改写（`file` 字段由上游机器绝对路径改写为本仓相对路径，其余为回归基线原样保留）

## 处置记录

- 2026-11-17：19 项全部按上游 pinned commit 原件收编；溯源台账见 [UPSTREAM.md](UPSTREAM.md)。Java 夹具回归：`code_quality_checker.py assets/sample_java_smells.java --json` 输出与 `expected_outputs/sample_java_smells_quality.json` 在 `file` 字段归一化后逐字节一致（实跑验证）。
- `tools/asset_gap_register.json` 中本技能 4 条目（3 脚本 + Java 夹具）同日删除，棘轮收紧；`_meta.disposal_log` 已追加本批记录。
- 本声明按其自身处置条款「补齐资产后删除本声明」本应删除；因本批「不删除 tracked 文件」约束，保留为销账台账（正文已不再被 SKILL.md 依赖）。
