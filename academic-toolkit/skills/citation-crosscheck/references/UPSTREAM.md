# UPSTREAM

- Upstream: https://github.com/FOURTEEN1416/Auto-claude-code-research-in-sleep（vendor/forks/Auto-claude-code-research-in-sleep，MIT）
- Pinned commit: 9f30e83（2026-11-16 实测上游 HEAD 9f30e834d24a337dbdd06fb20a1150d4376dfa59；原 94d8093，2026-08-26 拉取，vendor-asset-index #2）
- License: MIT（fork 根 LICENSE）
- 收编件: 本技能（2026-11-17 裁决第二批新建收编，施工图 dev-docs/audits/2026-11-17-裁决第二批/SKILL_ABSORB_PLAN.md §3）。以 skills/ 主线版（531 行）为底本；codex 镜像版「条件双盲」normative 措辞并入正文；scripts/cx_verify.py（1572 行）原样收编零改动，--selftest 121/121 实测通过。
- Local adaptation: SKILL.md 改写融入——宿主中性化（resolver 改为 $CX_VERIFY/自 cwd 向上找本仓技能目录，找不到 exit 1 且禁止手判 MATCH/MINOR；/tmp 中间产物改项目内 .engine/tmp/（CX_TMP 变量）；python3→python）；上游 shared-references 四件（external-cadence/fan-out-pattern/acceptance-gate/integration-contract）本仓缺失，关键契约内联进正文；citation-audit 对比段改为与本仓 check-citations 对比；新增「依赖与降级路径」段（外部 API 不可用/openpyxl 缺失 CSV 兜底/无 Agent 宿主 blind:false）。正文随本仓演进，与上游已分叉。
