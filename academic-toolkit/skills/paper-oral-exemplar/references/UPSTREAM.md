# Oral Paper Skill 上游溯源与许可状态

- Upstream: https://github.com/Adkid-Zephyr/oral-paper-skill（向顶会优秀论文学科研｜Oral Paper Skill）
- Pinned commit: a2c4bc41b3aa6946b2ccce1c844ce9936ef83308（2026-09-22 拉取，本地浅克隆在 `vendor/forks/oral-paper-skill/`，gitignored）
- Checklist date: 2026-09-22
- License: **未声明**——上游仓库根目录无 LICENSE/COPYING 文件（2026-09-22 经 GitHub API 核查 `license: null`，git tracked 文件中无 license 文件）。本仓以 status `experimental` 收编，**公开再发布（release 快照对外分发）待上游授权后方可解除**；作者前作 Kiterlin 系 anti-defensive-writing 为 MIT 且本仓库页声明 PRs welcome，授权预期良好，待办：向上游提 license 请求 issue。
- Local use: `skills/paper-oral-exemplar/` 论文范例对照改进与学习复盘；八十八三篇证据卡语料与蒸馏脚本未入库，仅存上游仓库/本地 vendor 副本。
- Local adaptation: 正文为上游原文（SKILL.md 从 `# Oral Paper Skill` 标题起逐字保留）；仅头部加本仓适配块（触发条件/输入输出契约/质量铁律/数模桥接表/STEP_MANIFEST）。`references/` 四件（abstract-derived-practices / archetypes / oral-patterns / review-scorecard）与 `agents/openai.yaml` 为上游原样拷贝。上游 `prompts/`（免依赖提示词）与 `research/`、`scripts/`（语料与蒸馏管线）不随收编——需要时从上游仓库获取。

## 与 anti-defensive-writing 的关系

同一作者生态的前后作：anti-defensive-writing（本仓 2026-09-03 收编，删多余防御性限定）负责"删"，本技能负责"对照优秀范例增补"，修订轮可先后使用（先对照增补、后删 hedge），互不替代。

## Upgrade rule

重拉上游后：① 更新 Pinned commit 为新 40 位哈希并刷新 Checklist date；② diff 上游 SKILL.md 正文与本仓 SKILL.md（从 `# Oral Paper Skill` 行起比对），上游变更需重放本仓适配块（头部新增、尾部 STEP_MANIFEST 不动正文）；③ 若上游新增 LICENSE，更新本文件 License 行并把 catalog 条目 status/promotion_history 一并推进；④ `python tools/check_provenance.py` + `python -m pytest -q`（仓库根）回归。
