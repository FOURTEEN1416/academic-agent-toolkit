# UPSTREAM

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（vendor/forks/Auto-claude-code-research-in-sleep，MIT）
- Pinned commit: 9f30e83（2026-11-16 实测上游 HEAD 9f30e834d24a337dbdd06fb20a1150d4376dfa59；原 94d8093，2026-08-26 拉取，vendor-asset-index #2）
- License: MIT（fork 根 LICENSE）
- 收编件: 本技能（V1.1 同名整采批；2026-09-23 v2.0 收尾补登记）。W3 语义化改名前后均在库；正文随本仓演进，与上游已分叉。
- Local adaptation: 原文入库后随本仓演进；本地适配与命名规范以本仓为准。


## 同步评估（2026-11-16，94d8093→9f30e83，UP-1）

- vendor/forks/Auto-claude-code-research-in-sleep 已镜像同步至实测 HEAD（768 文件更新、0 删除）。
- 上游区间 skills/ 变更 177 文件（+11563/-1014），主要为止(install/SSH 同步修复与文档扩充)。本件对应上游目录 skills/run-experiment：上游区间内有变更。
- 改写融入（2026-11-16，PKG-01 研究实验环批）：已融入三处——环境优先复用纪律（缺台账≠重建、无记录先跑小任务冒烟并留证、稳定后一次"文档逐字执行"核验、纯文档/日志改动不触发重建）；准备失败处置（同一环境问题两次定向修复无进展即上报接管；权限/认证/网络/驱动是环境前提而非改码理由；代码修复预算与评审闸门保留）；rsync 规则强化（有序排除/包含、显式纳入命令所需小配置资源、隐藏配置与数据/权重/产物不外发、以项目源根为准、同步成功≠启动核验）。
