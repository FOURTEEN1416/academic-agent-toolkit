# UPSTREAM 溯源台账 — tools/extract_pdf_figures.py

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（路径 skills/paper-poster-html/scripts/extract_pdf_figures.py，666 行上游版）
- Pinned commit: 94d8093e
- License: MIT（见上游仓库 LICENSE）
- Local use: `tools/extract_pdf_figures.py`（图级抽图工具，V2 移植批，2026-09-22）
- Local adaptation: 宿主中性化移植——上游依赖同目录 `_posterly.textutil.ascii_safe`
  （1 行转义器）已内联，去除包依赖（仅 PyMuPDF + Pillow）；CLI 改 flag 式
  `--pdf/--outdir`，manifest 落 `--outdir` 内；新增 `extract` 批量子命令
  （P5 图料语料入口）；检测逻辑（矢量簇/嵌入栅格/文本空隙、贪心重叠合并、
  面积地板）逐行保留。vendor 源保留原位不删（用户红线）。
