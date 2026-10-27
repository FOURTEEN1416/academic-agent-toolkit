# UPSTREAM 溯源台账 — fig-plot-edit

- Upstream: https://github.com/hang-jin/editaplot
- Pinned commit: 0172103（main @ 2026-09-07，feat: add native SHAP dashboard with nested contribution rings #28）
- License: Apache-2.0（见本目录 LICENSE；NOTICE 一并保留）
- Local use: `skills/fig-plot-edit/`（2026-09-22 B 方案整技能收编：复制上游
  `skill/editaplot/` 全包，删除上游平台专属 `agents/openai.yaml`，SKILL.md 深度改写为本仓适配层）
- Local adaptation: SKILL.md 重写为中文适配层——①上游执行器沙箱审批流程整体替换为本仓
  三段式边界（渲染=Ask first；管理员/注册表/DCOM 红线保留为 Never）；②runtime 引擎不随包，
  启动器指向 `vendor/forks/editaplot/editaplot.cmd`（vendor/ 快照不入库，gitignored）；
  ③新增 complete_step/evidence 申报协议与本机无 Origin 如实降级条款。
  references/ 已同步中性化（2026-10 清洗批），其余为上游原样副本。
- Verification: 本机 Origin 未安装，smoke/render/verify 全链未在本机验证（登记待用；
  上游模板验证基线 Origin 2024b）。安装 Origin 后首跑 `editaplot.cmd doctor` + `origin-smoke`。
- 上游更新方法见本技能 SKILL.md §八。
