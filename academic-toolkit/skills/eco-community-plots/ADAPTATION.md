# ADAPTATION 本地化适应性改写声明 — eco-community-plots

- 上游：本地完整复刻（生态/社区数据图方向，原始上游与作者未详）。
- 本地化适应性改写内容：
  - 集成进 academic-toolkit 技能路由与 frontmatter 规范；
  - 溯源登记：tools/check_provenance.py 的正常 upstream 记录（台账见 dev-docs）；
  - 产出遵循 FIGURE_MANIFEST 契约与 `_utils/` 检查器口径；
  - R 侧样式本地化：6 个脚本统一 `source()` 同目录 `scripts/_eco_style.R`
    （`theme_classic` + CJK 字体回退链 + 印刷 mm 尺寸/字号阶梯 + Okabe-Ito 语义色板），
    不再保留上游逐字副本形态。
