# 中文文本润色/降痕规则来源记录

- Upstream: 本套件自研中文学术文本润色与反模板化规则；未 vendored 外部仓库。
- Pinned commit: internal-suite-2026-08-18
- Checklist date: 2026-08-18
- Local use: `tools/de_ai_writer.py`、`tools/anti_ai_detector.py`、相关写作技能的语言质量检查规则
- License: 与本套件一致。
- Local adaptation: 面向中文课程论文、科研论文、竞赛论文，保留事实与引用，减少空泛套话和机械连接词。

## Upgrade rule

若引入第三方 humanize 工具或词表，必须追加仓库、commit、license 和本地修改记录。
