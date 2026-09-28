# ASSET-GAP 资产缺口声明 — spine-update

> 2026-09-28 收编批（裁决卡 A：用户允许拉取）：本技能脚本自上游 pin 1fe46f0 回填，
> 无缺失资产。本登记为宿主特征词豁免声明，非缺位登记。

## 宿主特征词豁免（运行时依赖事实）

- `scripts/paperspine_update.py` × 宿主用户级技能目录（host_dep_scan 词表条目之一）
- `scripts/paperspine_update.py` × 宿主项目级配置目录（词表条目之二）

理由：本脚本的**职能**即更新宿主安装副本（用户级 skills 目录下的 spine-update 等），
宿主路径是其功能语义而非依赖泄漏（host_dep_scan 词表说明的"运行时依赖事实"类）。
仓库内使用不触发这些路径；词表其余条目本脚本零命中。
豁免已同步登记于 `academic-toolkit/tools/data/host_dep_exemptions.json`（机检真源）。
