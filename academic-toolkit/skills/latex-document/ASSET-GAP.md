# ASSET-GAP 资产缺口声明 — latex-document

> 2026-09-28 深读批补登，上游资产未随本仓集成：以下条目为 SKILL.md 正文实际引用、盘上缺失、且未经内联标记/登记册棘轮/本清单三渠道豁免的资产（IEEE 两栏工作流样例 1 tex + 3 PNG；正文另处的 `examples/ieee-twocolumn*.png` 通配引用由这 3 件具体 PNG 覆盖）。`data/results` 已在登记册棘轮豁免，不重复列。
> 2026-11-16 重收编批更新：`examples/ieee-twocolumn.png`、`examples/ieee-twocolumn-p1.png`、`examples/ieee-twocolumn-p2.png` 已自 fork 快照（vendor/forks/latex-document-skill@fb5a159，经 compare 实证与上游 d165ee6 内容一致）补齐销账；`.chktexrc`、`setup.sh`、`requirements.txt` 同批补齐。`ieee-twocolumn.png` 与 `ieee-twocolumn-p1.png` 为上游同内容双名件，已登记 duplicate_assets_registry。
> 2026-11-18 examples 全量对齐批（销账）：`examples/ieee-twocolumn-sample.tex` 按下方处置口径的"本仓自写样例"路径补齐——上游 examples/ 仅有 81 张 PNG 预览、从无该 .tex 文件，故无法自上游补齐；样例按 SKILL.md 正文描述实现（`journal,10pt` + abstract + keywords + 单栏图 + 单栏表 + 跨栏表* + 数字参考文献），并对齐 ieee-journal-twocolumn-guide.md 版式规则（无 geometry、`[!t]` 浮动、`\columnwidth`/`\textwidth` 分工、hidelinks），pdfLaTeX 两遍冒烟编译通过（无错误、无 undefined、零 overfull，2 页）。至此 SKILL.md 正文引用的 examples/ 资产全部在盘，缺失清单清零。

## 缺失资产清单（0 项，2026-11-18 复核）

无。SKILL.md 正文引用的 examples/ 资产（`examples/ieee-twocolumn-sample.tex` 与 3 张 `examples/ieee-twocolumn*.png`）均在盘上。

## 处置口径

- 原缺失项 `examples/ieee-twocolumn-sample.tex` 已走"本仓自写样例"路径销账：文件落盘于 `examples/`，文件头注释标注本仓自写溯源；UPSTREAM.md 已同步台账。预览 PNG 与 fork 快照 md5 核对一致（`0cca93f3…`×2、`f9b1589b…`×1）。
- 本声明保留为零缺口台账；后续新增断链必须重新登记（登记册棘轮：新断链必 FAIL）。
