# UPSTREAM 溯源台账 — agent-figure-gallery

- Upstream: https://github.com/FOURTEEN1416/AgentFigureGallery
- Pinned commit: 0b55f26（main @ 2026-09-04）
- License: MIT（见上游仓库 LICENSE）
- Local use: `skills/agent-figure-gallery/`（2026-09-11 整包收编，轻量控制器）
- Local adaptation: 控制器原样收编；KB 数据本体在上游仓库（本机唯一可跑源在
  `vendor/forks/AgentFigureGallery`，pip 未装），数据激活归 V3 批（#11）。
  vendor 源保留原位不删。台账补建于 2026-09-22 #16 批。
- V3 激活（2026-09-22）：新增只读检索脚本 `scripts/kb_search.py`（本技能目录下，
  零依赖、免 pip，KB 根相对推导，缺位时输出 TOOL_GAP 并 exit 2）；SKILL.md 增补
  "Loading the KB from a local source" 与真数据演示段。vendor 侧零改动。
