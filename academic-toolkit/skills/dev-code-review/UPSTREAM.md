# UPSTREAM 溯源台账 — dev-code-review

- Upstream: https://github.com/alirezarezvani/claude-skills（路径 `engineering-team/skills/code-reviewer/`）
- Pinned commit: 4680893d91f2aee6f77ca1519fd1b86b7a104c87（main @ 2026-11-16 实测 HEAD，Release v2.14.12；2026-11-17 收编核验）
- License: MIT（上游仓库 LICENSE；本仓未随附副本，溯源以本台账 + pinned commit 为准）
- Local use: `skills/dev-code-review/`（2026-11-17 裁决第二批资产补齐：按 pinned commit 原样收编 19 件——
  3 件 `scripts/*.py`、`rules/universal.md`、13 件 `languages/*.md`、`assets/sample_java_smells.java`、
  `expected_outputs/sample_java_smells_quality.json`，与本技能 ASSET-GAP.md 历史缺口清单一一对应）
- Local adaptation: ① 14 件规则包（rules/languages）仅于文件头追加一行 HTML 溯源注释，正文原样；
  ② `expected_outputs/sample_java_smells_quality.json` 的 `file` 字段由上游机器绝对路径改写为本仓相对路径
  `assets/sample_java_smells.java`（脚本 `main()` 对入参做 `Path(...).resolve()`，该字段本就随机而异）；
  ③ SKILL.md 恢复上游「组织结构/加载表/工具节/新增语言/回归夹具」正文并与实际文件对齐，
  保留本仓 P0-7 自足版方法论/检查清单/判定表为互补章节；frontmatter 沿用本仓短 description（上游约 490 字符超预算，不采用）。
  ④ 上游 `assets/`+`expected_outputs/` 另有 C、C# 两组 smells/clean 夹具及期望输出共 8 件，本仓未收编（正文仅具体引用 Java 一组）。
- Verification: 本机 Windows + Python 3.12.4 实测——3 脚本 `--help` 均 exit=0；
  `code_quality_checker.py assets/sample_java_smells.java --json` 输出与仓内期望 JSON 在 `file` 字段归一化后逐字节一致；
  `pr_analyzer.py` 对临时 git 仓实跑识别 critical 秘密/TODO/复杂度/commit 规范；`review_report_generator.py` json/markdown/text 三模式 exit=0。
  纯标准库（argparse/json/re/sys/os/subprocess/pathlib/typing/datetime），无新增依赖。
- 上游更新方法：按新 pinned commit 重拉 `engineering-team/skills/code-reviewer/` 对应件，重放 ①–③ 适配，更新本台账同步记录。
- 同步记录（2026-11-17，初收编 4680893d）: 19 件收编 + SKILL.md 正文恢复 + ASSET-GAP.md 销账 + 登记册销账 4 条。
