# pubfig vendored 来源记录

- Upstream: https://github.com/Galaxy-Dawn/pubfig （本地 fork：FOURTEEN1416/pubfig）
- Pinned commit: 4eec116（2026-09-10 上游 HEAD feat(repo): publish core tests and CI signals）
- Checklist date: 2026-09-11
- License: **MIT**
- Local use: `third_party/pubfig/`（vendored，同 codesucker-core 惯例入 git）（Matplotlib-native 出版级 Python 库：paper-ready defaults/统一图族 API/期刊感知导出 save_figure+batch_export/agent-first JSON CLI render+validate-spec+list-kinds/panel-first Figma 多面板拼装）
- Local adaptation: 零改动 vendored（0.3.0）；定位=可选依赖——赛时环境冻结不 pip install，赛后评估纳入 .venv311；技能侧不直接 import，如需使用以 `pip install -e vendor/pubfig` 或 subprocess CLI 方式
- 评估登记: `dev-docs/figure-skills-batch-assessment.md`

## Upgrade rule

上游更新时先在 fork 同步，跑其 tests/ 后固定新 pinned commit 并更新本文件。
