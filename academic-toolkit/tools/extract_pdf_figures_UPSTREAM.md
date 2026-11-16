# UPSTREAM 溯源台账 — tools/extract_pdf_figures.py

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（路径 skills/paper-poster-html/scripts/extract_pdf_figures.py，666 行上游版）
- Pinned commit: 9f30e834d24a337dbdd06fb20a1150d4376dfa59（2026-11-16 实测上游 HEAD；原 94d8093e，2026-08-26 拉取）
- License: MIT（见上游仓库 LICENSE）
- Local use: `tools/extract_pdf_figures.py`（图级抽图工具，V2 移植批，2026-09-22）
- Local adaptation: 去运行时绑定移植——上游依赖同目录 `_posterly.textutil.ascii_safe`
  （1 行转义器）已内联，去除包依赖（仅 PyMuPDF + Pillow）；CLI 改 flag 式
  `--pdf/--outdir`，manifest 落 `--outdir` 内；新增 `extract` 批量子命令
  （P5 图料语料入口）；检测逻辑（矢量簇/嵌入栅格/文本空隙、贪心重叠合并、
  面积地板）逐行保留。vendor 源保留原位不删（用户红线）。
- 同步评估（2026-11-16，94d8093→9f30e83，UP-1）: 上游区间内
  `skills/paper-poster-html/scripts/extract_pdf_figures.py` 无变化（git diff 实测），
  本仓移植版无需改动；本单仅刷新 pin 至实测 HEAD，vendor/forks 快照已同步。
