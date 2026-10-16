# UPSTREAM 溯源台账 — vendor/forks/GMCMthesis

- Upstream: **GMCMthesis**（LaTeX 论文模板，latexstudio.net 原始作者；andy123t 维护版）
- 上游版本线索：`gmcmthesis.cls` 头部 `\ProvidesClass{gmcmthesis}[2023/09/19 v2.4 update by andy123t]`
- 本地副本：`D:\Desktop\GMCMthesis\GMCMthesis-master`（master 压缩包解出，**无 `.git`，无 pinned commit 可读**）
  → 以 **版本号 + 日期（v2.4 / 2023-09-19）** 作为 pin 代理，如实登记"无 commit 可核验"
- License: **上游未附 LICENSE 文件**（仓库内无许可声明）；原样保留，不主张再分发边界
- 收编日期: 2026-10-16（"四项桌面材料收编"批）

## 本仓使用情况（收编状态 = absorbed，模板基座）

| 上游件 | 本仓落位 | 状态 |
|---|---|---|
| `gmcmthesis.cls` | `skills/comp-paper-zh/_templates/huawei/gmcmthesis.cls` | **已三方合并**（上游 v2.4 + 本仓 v2.3 补丁 → v2.4），逐项取舍记录见该目录 `README.md`「cls 版本」节 |
| `gmcm.bst` | 同上目录 | **逐字节一致**（2026-10-16 实测 md5 相同） |
| `附件3：…第二十一届…论文模板.doc` | `assets-local/contest-regs/huawei/21st_2024/` | **逐字节一致**（2026-10-16 实测 md5 `7efd9d34…`） |
| `figures/logo.pdf` / `title.pdf` | `_templates/huawei/logo.pdf` / `title.pdf` | 已落位（2026-09-22 融合批） |
| `example.tex` / `example-color.tex` / `makefiles.*` / `reference.bib` / `figures/*` | **本 vendor 副本**（未并入技能目录） | 保留为**换届再融合**的上游参照（下一届官方模板变更时比对用） |

- 融合决策真源：`academic-toolkit/skills/comp-paper-zh/_templates/huawei/README.md`（含"未吸收、留待裁定"与"已裁定不吸收"两类逐项记录）。
- **本目录是上游参照，不是恢复源**——工作版以 `_templates/huawei/` 为准（库内领先 vendor，含本地补丁）。

## 注意事项

- 上游 cls 含**跨平台字体自适应块**（硬探测 Windows 路径），本仓**已裁定不吸收**（见 huawei 模板 README）。
- 上游 `README.md` / `example.tex` 内含 2024 年（第 21 届）格式变化情报，是换届比对的依据之一；**不得直接当 23 届/当届条款引用**。
- 上游**无 LICENSE**：按本仓 2026-10-16 现行口径（许可状态不作为入库门槛）人库留档；如需据此判断再分发边界，自行决定。
