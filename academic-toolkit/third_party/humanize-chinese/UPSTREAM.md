# 中文文本润色/降痕规则来源记录

- Upstream: 外部第三方 skill 快照（非本套件自研）。快照内自带两处来源记录，内容不一致，
  一并如实登记：
  - `package.json`: `humanize-chinese` v2.1.0 · author `voidborne-d` · MIT ·
    https://github.com/voidborne-d/humanize-chinese
    （2026-11-16 核查：该原址已 404；上游现址 https://github.com/swaylq/humanize-chinese ，
    实测 HEAD 6510ca7；版本/许可口径 2.1.0 vs 2.4.0、MIT/MIT-0/NOASSERTION 待上游澄清）
  - `_meta.json` / `skill-card.md`: ClawHub 注册表元数据，slug `humanize-chinese` v2.4.0
    （skill-card 标注发布者 swaylq、License MIT-0——经 2026-11-16 核查两者均不准确：
    实际许可以上游 LICENSE 正文为准 = MIT License (Non-Commercial)，见下；skill-card 的
    ClawHub 链接 `clawhub.ai/swaylq/humanize-chinese` 实测 404，正确路径为
    `clawhub.ai/swaylq/skills/humanize-chinese`，本仓已订正）
- Pinned commit: 不可固定——快照无 `.git`，无法定 hash；以快照内 `package.json` v2.1.0 为
  版本锚点。若需升级，从上述 GitHub 上游按 release 重新快照并补 pin。
- Checklist date: 2026-08-18（迁入时点）；本 UPSTREAM 订正 2026-09-28（原登记
  "自研/未 vendored 外部仓库" 与快照内来源元数据矛盾，按 vendored 实情改写）。
- License: **MIT License (Non-Commercial)**（以上游 LICENSE 正文为准，含 NON-COMMERCIAL
  USE ONLY 与衍生同许可条款；GitHub API 识别 NOASSERTION。2026-11-16 核查订正：原按
  `package.json` 登记的 "MIT" 与 skill-card 的 "MIT-0" 均不准确）。分发本快照必须
  原样保留 LICENSE 文本；涉商业场景使用前需按 NC 条款评估。
- Local use: `tools/de_ai_writer.py`、`tools/anti_ai_detector.py`、相关写作技能的语言质量检查规则
- Local adaptation（本仓改动，均已在此声明）:
  - 2026-09-28: `scripts/humanize_cn.py`、`scripts/compare_cn.py` 子进程硬编码
    `python3` 改 `sys.executable`（Windows 平台无 `python3` 命令，`--style` 曾静默降级）。
  - 2026-11-16: 许可核查订正——`skill-card.md` 的 ClawHub skill page URL 由
    `clawhub.ai/swaylq/humanize-chinese`（实测 404）更正为
    `clawhub.ai/swaylq/skills/humanize-chinese`，其 License 节加注实际许可
    （MIT License (Non-Commercial)，以 LICENSE 正文为准）。
- 版本口径（2026-11-16 核查落定为双口径并列，不再视作待澄清冲突）：GitHub 仓库
  `package.json` **2.1.0**（HEAD 6510ca7，2026-08-29）= 代码锚点；ClawHub 平台发布号
  **2.4.0**（publishedAt 2026-03-26T13:57:21Z；本地 `_meta.json` 即来自该注册表）=
  平台发布号。skill-card 的 "v2.1" 系旧快照笔误。升级时两口径分别对齐。

## Upgrade rule

若引入第三方 humanize 工具或词表，必须追加仓库、commit、license 和本地修改记录。
