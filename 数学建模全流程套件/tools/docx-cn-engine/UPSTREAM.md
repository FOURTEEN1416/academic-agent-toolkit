# DOCX 中文导出引擎来源记录

- Upstream: 本套件自研 Python DOCX 导出工具，依赖 python-docx / Pandoc 可选能力。
- Pinned commit: internal-suite-2026-08-18
- Checklist date: 2026-08-18
- Local use: `tools/docx_export.py`、`tools/docx_precheck.py`、`tools/docx_template_*.py`
- License: 与本套件一致；第三方运行时依赖遵循各自 license。
- Local adaptation: 面向中文论文、课程报告、竞赛论文和软著材料统一封装字号、行距、标题、图表与模板填充流程。

## Upgrade rule

升级 DOCX 导出逻辑时，同步运行 docx 预检/导出相关测试，并记录新增第三方模板或 profile 来源。
