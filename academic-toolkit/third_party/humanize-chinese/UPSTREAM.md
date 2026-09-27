# 中文文本润色/降痕规则来源记录

- Upstream: 外部第三方 skill 快照（非本套件自研）。快照内自带两处来源记录，内容不一致，
  一并如实登记：
  - `package.json`: `humanize-chinese` v2.1.0 · author `voidborne-d` · MIT ·
    https://github.com/voidborne-d/humanize-chinese
  - `_meta.json` / `skill-card.md`: ClawHub 注册表元数据，slug `humanize-chinese` v2.4.0
    （skill-card 标注发布者 swaylq、License MIT-0——与 package.json 的 MIT 存在口径冲突）
- Pinned commit: 不可固定——快照无 `.git`，无法定 hash；以快照内 `package.json` v2.1.0 为
  版本锚点。若需升级，从上述 GitHub 上游按 release 重新快照并补 pin。
- Checklist date: 2026-08-18（迁入时点）；本 UPSTREAM 订正 2026-09-28（原登记
  "自研/未 vendored 外部仓库" 与快照内来源元数据矛盾，按 vendored 实情改写）。
- License: 按 `package.json` 登记 **MIT**（skill-card 的 MIT-0 口径冲突待上游澄清；
  分发本快照时按更严格的 MIT 全文条款执行）。
- Local use: `tools/de_ai_writer.py`、`tools/anti_ai_detector.py`、相关写作技能的语言质量检查规则
- Local adaptation（本仓改动，均已在此声明）:
  - 2026-09-28: `scripts/humanize_cn.py`、`scripts/compare_cn.py` 子进程硬编码
    `python3` 改 `sys.executable`（Windows 平台无 `python3` 命令，`--style` 曾静默降级）。
- 版本口径备注: package.json 2.1.0 / skill-card v2.1 / _meta.json 2.4.0 三处不一致，
  升级时一并向上游核实。

## Upgrade rule

若引入第三方 humanize 工具或词表，必须追加仓库、commit、license 和本地修改记录。
