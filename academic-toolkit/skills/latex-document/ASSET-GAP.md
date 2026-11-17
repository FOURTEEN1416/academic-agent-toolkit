# ASSET-GAP 资产缺口声明 — latex-document

> 2026-09-28 深读批补登，上游资产未随本仓集成：以下条目为 SKILL.md 正文实际引用、盘上缺失、且未经内联标记/登记册棘轮/本清单三渠道豁免的资产（IEEE 两栏工作流样例 1 tex + 3 PNG；正文另处的 `examples/ieee-twocolumn*.png` 通配引用由这 3 件具体 PNG 覆盖）。`data/results` 已在登记册棘轮豁免，不重复列。
> 2026-11-16 重收编批更新：`examples/ieee-twocolumn.png`、`examples/ieee-twocolumn-p1.png`、`examples/ieee-twocolumn-p2.png` 已自 fork 快照（vendor/forks/latex-document-skill@fb5a159，经 compare 实证与上游 d165ee6 内容一致）补齐销账；`.chktexrc`、`setup.sh`、`requirements.txt` 同批补齐。`ieee-twocolumn.png` 与 `ieee-twocolumn-p1.png` 为上游同内容双名件，已登记 duplicate_assets_registry。

## 缺失资产清单（1 项，2026-11-16 复核）

- `examples/ieee-twocolumn-sample.tex`

## 处置口径

- 本声明使上述断链显性化（audit 豁免），删除本文件前必须先补齐资产或登记新台账。
- 本仓 SKILL.md 适配层引用的 IEEEtran 基线样例（`examples/ieee-twocolumn-sample.tex`）：2026-11-16 上游全量比对（fb5a159→d165ee6）证实上游 examples/ 仅有 81 张 PNG 预览、从无该 .tex 文件，无法自上游补齐；销账路径二选一：本仓自写样例，或改写 SKILL.md 引用口径。
- 若后续获得上游来源：按先 fork 后集成惯例拉取 → 补 UPSTREAM.md 台账 → 从 tools/asset_gap_register.json 删除对应条目 → 删除本声明。
