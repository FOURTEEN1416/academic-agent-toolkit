# 国赛（CUMCM）中文论文模板与规则来源记录

- Upstream: 中国工业与应用数学学会全国大学生数学建模竞赛组委会（CUMCM 官网）竞赛规则
- Pinned commit: 不可固定（每届规则随赛题公告发布）
- Checklist date: 2026-08-18
- Local use: `skills/comp-paper-zh/` 竞赛论文写作流程；页数上限、正文/附录语义见 `engine/modex-core/comp_rules.json`
- License: 竞赛规则公开可引用；本套件的模板与写作规范为本地自研编排
- Local adaptation: 将官网规则（页数上限、匿名要求、格式规范）固化为机器可校验的门禁配置。

## Upgrade rule

每届赛前核对官网最新规则公告，发现页数/格式变更时更新 `comp_rules.json` 与 `AGENTS.md` 路由说明，并刷新本文件。
## 模板资产来源（2026-09-09 赛前排查补录）

- `_templates/cumcm/`（cumcmthesis.cls + cumcm2026.sty）：来自 https://github.com/latexstudio/CUMCMThesis（fork FOURTEEN1416/CUMCMThesis，pinned 38d1f216bec3c9ffffb7dd09bf6b6c54f486b130，2026-09-09 拉取，已适配 2026 年国赛格式）。经 XeLaTeX 实测编译通过（含中文、表格、thebibliography）。
- **本地补丁（2026-09-09 独立审计修复 P0-1，重拉/升级上游时必须重放）**：cls 包加载顺序调整——`booktabs` 从与 `tabularx` 合载拆出，移到 `multirow/bigstrut/bigdelim` 之后单独加载。原因：上游把 booktabs 放在 bigstrut 之前，bigstrut 接管 `\\` 后 `\midrule` 报 `! Misplaced \noalign`，正文三线表必然编译中断。已在 `_templates/cumcm/main.tex` 补入经编译验证的论文骨架（booktabs 三线表实测通过）。
- 其余赛事模板（stats/apmcm_zh/mathorcup/huazhong/huawei/wuyi/changsanjiao/huashubei/diangongbei/dongsansheng/shuweibei）尚未入库：SKILL.md 模板分支已加落地断言，缺失时显式报错并给出补救路径，不再静默跳过。
