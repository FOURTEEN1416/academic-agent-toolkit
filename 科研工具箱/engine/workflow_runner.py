"""Agent-in-the-loop 工作流编排器。

引擎不执行，只编排：
  - next_action() → 告诉 agent 下一步做什么
  - complete_step() → agent 做完后回报结果
  - approve_checkpoint() → 用户确认后继续

Agent（当前 OpenCode 桌面版 agent）按 StepAction 执行，然后调用 complete_step()。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .opencode_bridge import StepAction, StepResult
from .artifact_manifest import ArtifactManifest
from .execution_protocol import validate_execution_evidence, write_execution_evidence
from .quality_gates import QualityGate
from .run_logger import RunLogger
from .template_resolver import resolve_template
from .workflow_store import StepStatus, Workflow, WorkflowStore
from .step_manifest import write_manifest as write_step_manifest


def _norm_skill_token(name: str) -> str:
    """技能名归一化口径（与 used 痕迹校验一致）：去首尾空白、小写、'-' 与 '_' 等价。"""
    return str(name).strip().lower().replace("-", "_")


@dataclass(frozen=True)
class RunResult:
    """引擎返回给 agent 的响应。"""
    workflow_id: str
    status: str  # completed | failed | waiting_checkpoint | advanced | blocked
    step_id: str | None = None
    message: str = ""
    action: StepAction | None = None
    # A5 ⑦ 修复：checkpoint UUID 直接随结果输出（此前只能从 report JSON/SQLite 捞）
    checkpoint_id: str | None = None


class WorkflowRunner:
    def __init__(self, store: WorkflowStore, catalog: dict[str, Any], skills_root: Path,
                 logger: RunLogger | None = None, audit_root: Path | None = None):
        self.store = store
        self.catalog = catalog
        self.skills_root = Path(skills_root)
        self.logger = logger
        # 操作审计（共享根 .engine/audit，与 plugin 同库）——引擎侧主动记录，
        # 与 plugin 拦截式记录互补：plugin 记"实际调用"，引擎记"编排决策"。
        self._audit = None
        if audit_root is not None:
            try:
                from .audit_store import AuditStore
                self._audit = AuditStore(audit_root)
            except Exception:
                self._audit = None

    start_params: dict[str, Any] = {}

    def _audit_record(self, **entry) -> None:
        """写入引擎侧审计事件（失败不阻断主流程）。"""
        if self._audit is not None:
            try:
                self._audit.record(entry)
            except Exception:
                pass

    def start(self, template: str, workspace: Path, params: dict[str, Any]) -> Workflow:
        """创建持久化工作流；调用 next_action() 获取第一个 StepAction。"""
        self.start_params = params
        steps = resolve_template(template, params, self.catalog)
        workspace = Path(workspace).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        workflow = self.store.create_workflow(template, {
            "workspace": str(workspace),
            "params": params,
            "template": template,
        })
        # 默认在工作区 .engine/logs 下建立运行日志（审计闭环）
        if self.logger is None:
            self.logger = RunLogger(workspace / ".engine" / "logs")
        self._log(workflow.id, None, None, "started",
                  f"工作流 {template} 启动（{len(steps)} 步）", agent=params.get("agent", ""))
        self._audit_record(type="engine_event", event="workflow_started", workflow_id=workflow.id,
                           template=template, workspace=str(workspace), step_count=len(steps),
                           agent=params.get("agent", ""))
        step_specs = []
        for s in steps:
            meta = dict(s)
            meta["primary_output"] = s.get("primary_output")
            meta["output_files"] = s.get("output_files", [])
            meta["has_checkpoint"] = s.get("has_checkpoint", False)
            meta["checkpoint_type"] = s.get("checkpoint_type")
            meta["display_name"] = s.get("display_name", s["skill_name"])
            step_specs.append({"name": s["skill_name"], "metadata": meta})
        self.store.add_steps(workflow.id, step_specs)
        return workflow

    def next_action(self, workflow_id: str) -> RunResult:
        """返回下一个要执行的 StepAction，或告知工作流已完成/失败。"""
        running = self._last_running_step(workflow_id)
        if running is not None:
            workflow = self._workflow(workflow_id)
            return RunResult(
                workflow_id, "advanced", running.id,
                message=f"步骤 {running.name} 正在执行，重发当前动作",
                action=self._action_for_step(workflow, running),
            )

        # ⛔ 任何步骤失败后立即阻断：不允许带着失败步骤继续推进后续步骤
        failed = self._has_failed_steps(workflow_id)
        if failed:
            return RunResult(workflow_id, "failed", message=f"步骤 {failed} 已失败，先修复再继续")

        # ⛔ checkpoint 硬闸：存在 blocked 步骤 = 等待用户 approve，禁止 next 越过
        #（2026-09-09 独立审计 P1-2：此前 next 可在未 approve 时启动下一步，检查点形同虚设）
        blocked = self._first_blocked_step(workflow_id)
        if blocked is not None:
            return RunResult(
                workflow_id, "blocked", blocked.id,
                message=(f"步骤 {blocked.name} 的检查点等待用户批准"
                         f"（workflow_cli approve --checkpoint <UUID> --by <批准人>），不得跳过"),
                checkpoint_id=self._latest_checkpoint_id(blocked.id),
            )

        step = self._next_pending_step(workflow_id)
        if step is None:
            # 检查是否有失败的步骤
            failed = self._has_failed_steps(workflow_id)
            if failed:
                return RunResult(workflow_id, "failed", message=f"步骤 {failed} 已失败")
            return RunResult(workflow_id, "completed", message="所有步骤已完成")

        workflow = self._workflow(workflow_id)
        workspace = Path(workflow.metadata["workspace"])
        skill_path = self.skills_root / step.name / "SKILL.md"

        self.store.transition_step(step.id, StepStatus.RUNNING)
        self._log(workflow_id, step.id, step.name, "started",
                  f"开始执行 {step.name}", agent=self._agent_label(workflow))

        action = StepAction(
            workflow_id=workflow_id,
            step_id=step.id,
            position=step.position,
            skill_name=step.name,
            display_name=step.metadata.get("display_name", step.name),
            workspace=workspace,
            skill_path=skill_path,
            output_files=step.metadata.get("output_files", []),
            primary_output=step.metadata.get("primary_output", ""),
            has_checkpoint=step.metadata.get("has_checkpoint", False),
            checkpoint_type=step.metadata.get("checkpoint_type"),
            companion_skills=step.metadata.get("companion_skills", []),
            assets=step.metadata.get("assets", []),
            quick_gates=bool(step.metadata.get("quick_gates", False)),
            params=workflow.metadata.get("params", {}),
        )
        return RunResult(workflow_id, "advanced", step.id, action=action)

    def complete_step(self, workflow_id: str, result: StepResult) -> RunResult:
        """agent 执行完一个步骤后调用此方法回报结果。"""
        workflow = self._workflow(workflow_id)
        # 从 RUNNING 状态中找最新的步骤
        step = self._last_running_step(workflow_id)
        if step is None:
            return RunResult(workflow_id, "failed", message="没有正在执行的步骤")

        if not result.ok:
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.FAILED,
                {"status": "failed", "error": result.stderr},
                artifacts=[{"name": a, "path": a} for a in result.artifacts],
                event={"type": "step_failed", "stderr": result.stderr},
            )
            self._log(workflow_id, step.id, step.name, "failed",
                      f"步骤 {step.name} 失败: {result.stderr[:200]}", agent=self._agent_label(workflow))
            return RunResult(workflow_id, "failed", step.id, result.stderr)

        # 检查执行证据：技能必须有产出文件作为执行证据
        declared_outputs = step.metadata.get("output_files", [])
        has_evidence = bool(result.artifacts) or bool(declared_outputs and any(
            (Path(workflow.metadata["workspace"]) / o).exists()
            for o in declared_outputs
        ))
        if not has_evidence:
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.FAILED,
                {"status": "failed", "error": "no execution evidence"},
                event={"type": "step_failed", "stderr": "no execution evidence: agent claimed success but produced no artifacts"},
            )
            return RunResult(workflow_id, "failed", step.id,
                             "no execution evidence: agent claimed success but produced no artifacts")

        try:
            evidence = validate_execution_evidence(workflow.metadata["workspace"], self._action_for_step(workflow, step), result)
        except ValueError as exc:
            message = f"invalid execution evidence: {exc}"
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.FAILED,
                {"status": "failed", "error": message},
                artifacts=[{"name": a, "path": a} for a in result.artifacts],
                event={"type": "step_failed", "stderr": message},
            )
            return RunResult(workflow_id, "failed", step.id, message)

        # ⛔ M5: 审核独立视角强制（防伪造审核——LESSONS 教训 1）
        # 模板步骤标记 requires_subagent=true（审核类：comp-review/comp-visual-review/comp-final-review 等）
        # 时，执行证据必须包含真实只读子智能体会话 ID（subagent_session）。
        # 主 Agent 不得直接提交手写审核产物冒充独立审查。
        # ⛔ P1: 审核步骤的 commands 必须含真实工具调用（tools/ 下脚本），
        # 防 "echo done" 伪命令冒充实际执行。
        if step.metadata.get("requires_subagent"):
            subagent_session = str(result.metadata.get("execution_evidence", {}).get("subagent_session", "")).strip()
            if not subagent_session:
                message = ("invalid execution evidence: 该步骤要求由只读子智能体执行（requires_subagent），"
                           "执行证据缺少 subagent_session（真实子智能体会话 ID）。主 Agent 不得直接提交审核产物。")
                self.store.transition_step_with_checkpoint(
                    workflow_id, step.id, StepStatus.FAILED,
                    {"status": "failed", "error": message},
                    artifacts=[{"name": a, "path": a} for a in result.artifacts],
                    event={"type": "step_failed", "stderr": message},
                )
                return RunResult(workflow_id, "failed", step.id, message)
            # P1: commands 必须含真实工具调用（tools/ 或 skills/_utils 下脚本）
            commands = result.metadata.get("execution_evidence", {}).get("commands", [])
            has_tool_call = any(
                isinstance(c, dict) and ("tools/" in str(c.get("command", "")) or "_utils/" in str(c.get("command", "")))
                for c in commands
            )
            if not has_tool_call:
                message = ("invalid execution evidence: 审核步骤（requires_subagent）的 commands 必须包含"
                           "真实工具调用（tools/ 或 skills/_utils 下脚本），禁止用 echo 等伪命令冒充实际执行。")
                self.store.transition_step_with_checkpoint(
                    workflow_id, step.id, StepStatus.FAILED,
                    {"status": "failed", "error": message},
                    artifacts=[{"name": a, "path": a} for a in result.artifacts],
                    event={"type": "step_failed", "stderr": message},
                )
                return RunResult(workflow_id, "failed", step.id, message)

        # ⛔ C1: 辅助技能强制申报（2026-09-11 用户质询"只推荐不强制会便宜行事"）
        # 步骤定义了 companion_skills 时，执行证据必须含 companion_skills 申报：
        #   {"used": [技能名...], "skipped": [{"skill": 名, "reason": 非空理由}...]}
        # used ∪ skipped 必须恰好覆盖本步推荐清单（申报 ≠ 强制使用，但"不用"必须留痕给理由）；
        # 缺申报/覆盖不全/申报了未推荐的技能/格式错 = 步骤失败（错误信息含正确格式教学）。
        recommended = list(step.metadata.get("companion_skills") or [])
        if recommended:
            def _companion_reject(detail: str) -> RunResult:
                # 注意：只有第一段是 f-string；后两段是普通字符串，花括号无需转义
                # （2026-09-11 小修：此前 {{...}} 转义残留导致教学格式渲染成双花括号）
                message = (f"invalid execution evidence: 辅助技能申报不合规——{detail}。"
                           '正确格式: "companion_skills": {"used": ["技能名"], '
                           '"skipped": [{"skill": "技能名", "reason": "为何跳过"}]}，'
                           "used 与 skipped 须恰好覆盖本步推荐清单。")
                self.store.transition_step_with_checkpoint(
                    workflow_id, step.id, StepStatus.FAILED,
                    {"status": "failed", "error": message},
                    artifacts=[{"name": a, "path": a} for a in result.artifacts],
                    event={"type": "step_failed", "stderr": message},
                )
                return RunResult(workflow_id, "failed", step.id, message)

            raw_decl = result.metadata.get("execution_evidence", {}).get("companion_skills")
            if not isinstance(raw_decl, dict):
                return _companion_reject(f"本步推荐了辅助技能 {recommended} 但证据缺少 companion_skills 申报")
            used = raw_decl.get("used", [])
            skipped = raw_decl.get("skipped", [])
            if not isinstance(used, list) or not all(isinstance(s, str) and s.strip() for s in used):
                return _companion_reject("used 必须是非空技能名字符串数组")
            if not isinstance(skipped, list) or not all(
                isinstance(s, dict) and str(s.get("skill", "")).strip() and str(s.get("reason", "")).strip()
                for s in skipped
            ):
                return _companion_reject('skipped 必须是 [{"skill": 技能名, "reason": 非空理由}] 数组')
            declared = set(used) | {str(s["skill"]) for s in skipped}
            unknown = sorted(declared - set(recommended))
            missing = sorted(set(recommended) - declared)
            if unknown:
                return _companion_reject(f"申报了本步未推荐的技能 {unknown}（本步推荐清单: {recommended}）")
            if missing:
                return _companion_reject(f"推荐技能未逐一申报使用或跳过: {missing}")
            # ⛔ C1 申报自洽（A2 minor 审计修复）：used 与 skipped 不得重叠——同一技能
            # "既声称用了又声称跳过"是自相矛盾申报，留痕必须口径唯一。归一化与痕迹
            # 校验同口径（不区分大小写、'-' 与 '_' 等价），大小写/连字符变体的重叠同样拦截。
            used_norm = {_norm_skill_token(u) for u in used}
            skipped_norm = {_norm_skill_token(s["skill"]) for s in skipped}
            overlap_norm = used_norm & skipped_norm
            if overlap_norm:
                overlap_display = sorted(
                    {u for u in used if _norm_skill_token(u) in overlap_norm}
                    | {str(s["skill"]) for s in skipped
                       if _norm_skill_token(s["skill"]) in overlap_norm}
                )
                return _companion_reject(
                    f"同一技能同时申报了 used 与 skipped: {overlap_display}（自相矛盾申报）。"
                    "每个技能只能二选一：真实使用 → 申报 used（须留使用痕迹）；"
                    "确未使用 → 申报 skipped 并写明非空理由")
            # ⛔ C1 痕迹绑定（A5 ⑫/A2 major 修复：used 伪报零校验直接过闸）：
            # 覆盖校验通过后，每个 used 技能必须有真实使用痕迹——技能名
            # （不区分大小写，'-' 与 '_' 等价）出现在任一 evidence.commands 命令串
            # 或任一 declared outputs/inputs 路径中才算有痕；无痕 = 步骤失败，
            # 并教学两条出路（如实补记 consult 命令，或改报 skipped+理由）。
            trace_blob = " ".join(
                [str(c.get("command", "")) for c in evidence.get("commands", []) if isinstance(c, dict)]
                + [str(p) for p in evidence.get("outputs", []) or []]
                + [str(p) for p in evidence.get("inputs", []) or []]
            ).lower().replace("-", "_")
            for used_skill in used:
                trace_key = _norm_skill_token(used_skill)
                if trace_key and trace_key not in trace_blob:
                    return _companion_reject(
                        f"used 申报的技能 {used_skill} 在命令与产物/输入路径中零使用痕迹"
                        "（伪报 used 直接过闸已被禁止）。两条出路："
                        "① 把 consult 该技能的真实命令（如读取其 SKILL.md 的命令）如实记入 "
                        "evidence.commands；② 若确未使用，改申报为 skipped 并写明理由")

        # ⛔ C2: 步骤资产强制申报（2026-09-12 资产利用率审计落地）
        # 现状：C1 只覆盖"技能"，数据/参考论文/工具脚本/参考图集等非技能资产在
        # StepAction 零暴露——引擎只给技能，仓库其余资产处于"流程不可见"状态。
        # 步骤定义了 assets（{"name","path","note"} 列表，path 为仓库根相对）时，
        # 执行证据必须含 assets 申报，语义与 C1 同构：
        #   {"used": [资产名...], "skipped": [{"name": 资产名, "reason": 非空理由}...]}
        # used ∪ skipped 恰好覆盖清单；申报 ≠ 强制使用，但"不用"必须留痕给理由；
        # used 资产须有真实痕迹（资产名或仓库根相对路径出现在命令/产物/输入路径中）。
        required_assets = [a for a in (step.metadata.get("assets") or []) if isinstance(a, dict) and str(a.get("name", "")).strip()]
        if required_assets:
            def _asset_reject(detail: str) -> RunResult:
                message = (f"invalid execution evidence: 步骤资产申报不合规——{detail}。"
                           '正确格式: "assets": {"used": ["资产名"], '
                           '"skipped": [{"name": "资产名", "reason": "为何跳过"}]}，'
                           "used 与 skipped 须恰好覆盖 StepAction.assets 清单。")
                self.store.transition_step_with_checkpoint(
                    workflow_id, step.id, StepStatus.FAILED,
                    {"status": "failed", "error": message},
                    artifacts=[{"name": a, "path": a} for a in result.artifacts],
                    event={"type": "step_failed", "stderr": message},
                )
                return RunResult(workflow_id, "failed", step.id, message)

            raw_assets_decl = result.metadata.get("execution_evidence", {}).get("assets")
            asset_names = [str(a["name"]).strip() for a in required_assets]
            if not isinstance(raw_assets_decl, dict):
                return _asset_reject(f"本步给出了资产清单 {asset_names} 但证据缺少 assets 申报")
            assets_used = raw_assets_decl.get("used", [])
            assets_skipped = raw_assets_decl.get("skipped", [])
            if not isinstance(assets_used, list) or not all(isinstance(s, str) and s.strip() for s in assets_used):
                return _asset_reject("used 必须是非空资产名字符串数组")
            if not isinstance(assets_skipped, list) or not all(
                isinstance(s, dict) and str(s.get("name", "")).strip() and str(s.get("reason", "")).strip()
                for s in assets_skipped
            ):
                return _asset_reject('skipped 必须是 [{"name": 资产名, "reason": 非空理由}] 数组')
            assets_declared = set(assets_used) | {str(s["name"]) for s in assets_skipped}
            assets_unknown = sorted(assets_declared - set(asset_names))
            assets_missing = sorted(set(asset_names) - assets_declared)
            if assets_unknown:
                return _asset_reject(f"申报了本步未给出的资产 {assets_unknown}（本步资产清单: {asset_names}）")
            if assets_missing:
                return _asset_reject(f"资产未逐一申报使用或跳过: {assets_missing}")
            if set(assets_used) & {str(s["name"]) for s in assets_skipped}:
                return _asset_reject("同一资产同时申报了 used 与 skipped（自相矛盾申报）。"
                                     "真实使用 → used（须留使用痕迹）；确未使用 → skipped+理由")
            # used 痕迹绑定：资产名或路径（归一化大小写与路径分隔符）出现在
            # commands/outputs/inputs 任一串中即有痕。路径按仓库根相对形态匹配，
            # 绝对路径命令天然包含该子串。
            asset_trace_blob = " ".join(
                [str(c.get("command", "")) for c in evidence.get("commands", []) if isinstance(c, dict)]
                + [str(p) for p in evidence.get("outputs", []) or []]
                + [str(p) for p in evidence.get("inputs", []) or []]
            ).lower().replace("\\", "/")
            for asset in required_assets:
                if str(asset["name"]).strip() not in assets_used:
                    continue
                asset_path_norm = str(asset.get("path", "")).strip().lower().replace("\\", "/")
                name_hit = str(asset["name"]).strip() in asset_trace_blob
                path_hit = bool(asset_path_norm) and asset_path_norm in asset_trace_blob
                if not name_hit and not path_hit:
                    return _asset_reject(
                        f"used 申报的资产 {asset['name']} 在命令与产物/输入路径中零使用痕迹。"
                        "两条出路：① 把读取/执行该资产的真实命令如实记入 evidence.commands"
                        "（含资产路径或资产名）；② 若确未使用，改申报为 skipped 并写明理由")

        workspace = Path(workflow.metadata["workspace"])
        declared_outputs = list(step.metadata.get("output_files", []))
        claimed = set(result.artifacts)
        undeclared = sorted(claimed - set(declared_outputs))
        manifest = ArtifactManifest.validate(workspace, declared_outputs)
        if undeclared or not manifest["ok"]:
            details = []
            if undeclared:
                details.append(f"undeclared artifacts: {', '.join(undeclared)}")
            if manifest["missing"]:
                details.append(f"missing declared outputs: {', '.join(manifest['missing'])}")
            if manifest["invalid"]:
                details.append(f"invalid declared outputs: {', '.join(manifest['invalid'])}")
            message = "declared outputs validation failed: " + "; ".join(details)
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.FAILED,
                {"status": "failed", "error": message, "manifest": _manifest_payload(manifest)},
                event={"type": "step_failed", "stderr": message},
            )
            return RunResult(workflow_id, "failed", step.id, message)

        # ⛔ D7: 中间产物最低内容规格（2026-09-13 原仓库缺陷修复建议 D7 落地）
        # 背景：Step 2/4 曾产出 5.7KB/2.9KB "目录级" LITERATURE.md/RESULTS.md——
        # 产物存在（manifest 过闸）但信息密度近零，"走完了"的形式合规掩盖
        # "走透了"的实质缺位。步骤 metadata.output_specs =
        # {文件名: {min_bytes, require_any, rationale}} 时逐项校验：
        #   - min_bytes：产物字节数下限（拦纯目录清单）；
        #   - require_any：实质内容特征词（任一命中即过，UTF-8 忽略错误解码）；
        #   - rationale：失败信息引用，教学为何被拦。
        # 未声明 output_specs 的步骤零影响（向后兼容）；规格是下限不是完备审查。
        specs = {k: v for k, v in (step.metadata.get("output_specs") or {}).items()
                 if isinstance(v, dict)}
        if specs:
            spec_failures = []
            for spec_name, spec in specs.items():
                rel = next((o for o in declared_outputs
                            if Path(o).name == spec_name or o == spec_name), None)
                if rel is None:
                    continue  # 该文件不在本步声明产物清单中，规格不激活
                spec_path = workspace / rel
                if not spec_path.exists():
                    spec_failures.append(f"{spec_name}: 文件不存在")
                    continue
                size = spec_path.stat().st_size
                min_bytes = int(spec.get("min_bytes", 0))
                if min_bytes and size < min_bytes:
                    spec_failures.append(
                        f"{spec_name}: {size}B < 最低规格 {min_bytes}B"
                        f"（{spec.get('rationale', '产物规格下限')}）")
                    continue
                require_any = [str(kw) for kw in (spec.get("require_any") or []) if str(kw).strip()]
                if require_any:
                    try:
                        text = spec_path.read_text(encoding="utf-8", errors="ignore").lower()
                    except OSError:
                        text = ""
                    if not any(kw.lower() in text for kw in require_any):
                        spec_failures.append(
                            f"{spec_name}: 未含任何实质内容特征词 {require_any}"
                            f"（{spec.get('rationale', '产物规格下限')}）")
            if spec_failures:
                message = ("declared outputs content spec failed (D7 产物规格下限): "
                           + "; ".join(spec_failures)
                           + "。请补足实质内容（台账/证据/数值快照）后重报，而非仅罗列目录。")
                self.store.transition_step_with_checkpoint(
                    workflow_id, step.id, StepStatus.FAILED,
                    {"status": "failed", "error": message},
                    artifacts=[{"name": a, "path": a} for a in result.artifacts],
                    event={"type": "step_failed", "stderr": message},
                )
                return RunResult(workflow_id, "failed", step.id, message)

        action = self._action_for_step(workflow, step)
        evidence_path = write_execution_evidence(workspace, action, evidence, _manifest_payload(manifest))
        self._audit_record(type="engine_event", event="step_completed", workflow_id=workflow_id,
                           step_id=step.id, skill_name=step.name, evidence_path=evidence_path,
                           agent=self._agent_label(workflow),
                           declared_commands=[c.get("command", "") for c in evidence.get("commands", [])])

        # S1 FIX: STEP_MANIFEST 无条件强制执行
        # 所有声明了 output_files 的步骤必须产出 STEP_MANIFEST.json
        # 这不再是可选的 required_checks，而是步骤完成的硬闸
        declared_outputs = step.metadata.get("output_files", [])
        if declared_outputs:
            # 检查是否已有 step_manifest 检查，若无则强制添加
            required_checks = list(step.metadata.get("required_checks") or [])
            if "step_manifest" not in required_checks:
                required_checks.append("step_manifest")
        else:
            required_checks = list(step.metadata.get("required_checks") or [])

        self._write_step_manifest(workflow, step, evidence, declared_outputs)

        gate_result = QualityGate(workspace).run_all(
            step.name,
            declared_outputs=declared_outputs,
            comp_name=workflow.name if step.name in {"comp-compile-zh", "comp-compile-en"} else "",
            requires_figures=step.name.startswith("paper-figure"),
            required_checks=required_checks,
            primary_output=step.metadata.get("primary_output"),
        )
        if not gate_result["ok"]:
            message = "quality gates failed"
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.FAILED,
                {"status": "failed", "error": message, "quality_gates": gate_result},
                event={"type": "step_failed", "stderr": message, "quality_gates": gate_result},
            )
            self._log(workflow_id, step.id, step.name, "failed",
                      f"步骤 {step.name} 质量门禁失败", agent=self._agent_label(workflow))
            return RunResult(workflow_id, "failed", step.id, message)

        # 检查是否需要检查点
        has_checkpoint = step.metadata.get("has_checkpoint", False)
        if has_checkpoint:
            checkpoint_type = step.metadata.get("checkpoint_type", "approve")
            _step_after, checkpoint = self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.BLOCKED,
                {"status": "waiting_checkpoint", "type": checkpoint_type},
                artifacts=_manifest_artifacts(manifest),
                event={"type": "step_completed", "evidence_path": evidence_path, "manifest": _manifest_payload(manifest), "quality_gates": gate_result},
            )
            self._log(workflow_id, step.id, step.name, "checkpoint",
                      f"步骤 {step.name} 完成，等待用户确认", agent=self._agent_label(workflow))
            # A5 ⑦ 修复：checkpoint UUID 直接随 complete 结果输出，agent 不用再捞 report/SQLite
            # 返回下一个动作（如果有），但标记为 waiting_checkpoint
            next_action = self._next_pending_step(workflow_id)
            if next_action:
                return RunResult(workflow_id, "waiting_checkpoint", step.id,
                                 message=f"步骤 {step.name} 完成，等待用户确认"
                                         f"（checkpoint_id: {checkpoint.id}，批准: workflow_cli approve --checkpoint {checkpoint.id} --by <批准人>）",
                                 checkpoint_id=checkpoint.id)
            return RunResult(workflow_id, "waiting_checkpoint", step.id,
                             message=f"所有步骤完成，等待最后检查点确认"
                                     f"（checkpoint_id: {checkpoint.id}，批准: workflow_cli approve --checkpoint {checkpoint.id} --by <批准人>）",
                             checkpoint_id=checkpoint.id)

        self.store.transition_step_with_checkpoint(
            workflow_id, step.id, StepStatus.COMPLETED,
            {"status": "completed", "evidence_path": evidence_path, "manifest": _manifest_payload(manifest), "quality_gates": gate_result},
            artifacts=_manifest_artifacts(manifest),
            event={"type": "step_completed", "evidence_path": evidence_path, "manifest": _manifest_payload(manifest), "quality_gates": gate_result},
        )
        self._log(workflow_id, step.id, step.name, "completed",
                  f"步骤 {step.name} 完成，证据: {evidence_path}", agent=self._agent_label(workflow),
                  evidence_path=evidence_path)
        # 每步完成后即时落盘日志（固定文件名覆盖），中断/崩溃也不丢审计链
        if self.logger is not None:
            try:
                self.logger.save(workflow_id, f"run_{workflow_id}.json")
            except Exception:
                pass

        # 检查是否还有下一步
        next_step = self._next_pending_step(workflow_id)
        if next_step is None:
            self.store.complete_workflow(workflow_id)
            self._log(workflow_id, None, None, "completed", "所有步骤完成", agent=self._agent_label(workflow))
            return RunResult(workflow_id, "completed", step.id, "所有步骤完成")

        return RunResult(workflow_id, "advanced", step.id,
                         message=f"步骤 {step.name} 完成，继续下一步")

    def approve_checkpoint(self, checkpoint_id: str, response: dict[str, Any]) -> RunResult:
        """用户批准检查点后继续工作流。"""
        candidates = [c for c in self.store.resume_candidates() if c.checkpoint.id == checkpoint_id]
        if not candidates:
            raise KeyError(f"unknown checkpoint: {checkpoint_id}")
        candidate = candidates[0]

        if response.get("approved") is not True:
            return RunResult(candidate.workflow_id, "blocked", candidate.step_id,
                             "检查点未批准")

        # M3 FIX: 批准记录 + 步骤完成合并为一次原子事务（transition_step_with_checkpoint），
        # 避免两次独立 transition_step 中途失败导致状态不一致（BLOCKED→RUNNING→COMPLETED 非原子）。
        # approve 检查点会附带一次 checkpoint_approved 事件，步骤直接原子转为 COMPLETED。
        step, _ = self.store.transition_step_with_checkpoint(
            candidate.workflow_id, candidate.step_id, StepStatus.COMPLETED,
            {"status": "approved", "response": response},
            event={"type": "checkpoint_approved", "approved_by": response.get("approved_by", "")},
        )
        self._log(candidate.workflow_id, candidate.step_id, step.name, "checkpoint",
                  "用户批准检查点", agent=response.get("approved_by", ""))
        self._audit_record(type="engine_event", event="checkpoint_approved", workflow_id=candidate.workflow_id,
                           step_id=candidate.step_id, approved_by=response.get("approved_by", ""))

        # 返回下一个动作，并在工作流完成时落盘
        next_step = self._next_pending_step(candidate.workflow_id)
        if next_step is None:
            self.store.complete_workflow(candidate.workflow_id)
            return RunResult(candidate.workflow_id, "completed", candidate.step_id,
                             "所有步骤完成")

        # F1 FIX: 即使还有后续步骤，也检查是否所有步骤实际上已完成（无 pending 步骤）
        # 如果没有 pending 步骤，标记工作流完成；否则继续下一步
        all_pending = self._has_pending_steps(candidate.workflow_id)
        if not all_pending:
            self.store.complete_workflow(candidate.workflow_id)
            return RunResult(candidate.workflow_id, "completed", candidate.step_id,
                             "所有步骤完成")

        return self.next_action(candidate.workflow_id)

    def retry_last_failed(self, workflow_id: str, by: str = "") -> RunResult:
        """FAILED 步骤的带内恢复路径（A2 minor 审计修复）。

        FAILED→RUNNING 在 _TRANSITIONS 中合法但此前引擎不可达（CLI 无 retry 命令），
        恢复被迫手改 SQLite（未审计通道）。本方法经引擎走合法转移，落 step_retry
        审计事件（含 step_id、by），把恢复行为纳入审计链。
        """
        workflow = self._workflow(workflow_id)
        row = self.store._connection.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND status = 'failed' "
            "ORDER BY updated_at DESC, position DESC LIMIT 1",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return RunResult(workflow_id, "failed",
                             message="没有 FAILED 步骤可重试（retry 仅用于失败步骤的带内恢复；"
                                     "正常推进请用 next）")
        failed_step = self.store._step_from_row(row)
        step, _checkpoint = self.store.transition_step_with_checkpoint(
            workflow_id, failed_step.id, StepStatus.RUNNING,
            {"status": "retrying", "by": by},
            event={"type": "step_retry", "step_id": failed_step.id,
                   "skill_name": failed_step.name, "by": by},
        )
        self._log(workflow_id, step.id, step.name, "retry",
                  f"步骤 {step.name} 重试（FAILED→RUNNING 带内恢复）",
                  agent=by or self._agent_label(workflow))
        self._audit_record(type="engine_event", event="step_retry", workflow_id=workflow_id,
                           step_id=step.id, skill_name=step.name, by=by)
        return RunResult(workflow_id, "advanced", step.id,
                         message=f"步骤 {step.name} 已复位为 RUNNING，重新执行后 complete",
                         action=self._action_for_step(workflow, step))

    # ── D1 断链告警与手工补录（2026-09-13 原仓库缺陷修复建议 D1 落地） ─────
    # 背景：engine_step.log（2026-09-12）显示 14 步 runner 推进到 step 3 等待
    # checkpoint 批准后即停，step 4–14 全部绕开 runner 手工完成，引擎无任何
    # "断链"告警，STEP_MANIFEST/事件库对 4–14 步零记录——评审若要求"每步
    # 可复盘"则溯源断档。本段补两条带内通道：stall 停滞告警 + backfill 补录。

    def detect_stalled(self, workflow_id: str, stall_hours: float = 12.0) -> dict[str, Any]:
        """扫描长期无进展的步骤并告警（D1 断链检测）。

        覆盖两类断链：
        - running_stalled：步骤 RUNNING 后超 ``stall_hours`` 小时未回报
          complete（agent 执行中断/会话丢失）；
        - checkpoint_pending：步骤 BLOCKED 等待用户批准超 ``stall_hours``
          （批准悬置，工作流名存实亡）。

        命中任一即写入运行日志（stall_alert）与引擎侧操作审计事件
        （step_stall_alert）；检测本身失败不阻断主流程。返回结构::

            {"workflow_id", "stall_hours", "alert": bool,
             "stalled": [{step_id, skill_name, position, status,
                          stalled_hours, kind}, ...]}
        """
        now = datetime.now(timezone.utc)
        rows = self.store._connection.execute(
            "SELECT id, name, position, status, updated_at FROM workflow_steps "
            "WHERE workflow_id = ? AND status IN ('running','blocked')",
            (workflow_id,),
        ).fetchall()
        stalled: list[dict[str, Any]] = []
        for row in rows:
            try:
                updated = datetime.fromisoformat(str(row["updated_at"]))
            except (TypeError, ValueError):
                continue
            hours = (now - updated).total_seconds() / 3600.0
            if hours < float(stall_hours):
                continue
            stalled.append({
                "step_id": row["id"],
                "skill_name": row["name"],
                "position": row["position"],
                "status": row["status"],
                "stalled_hours": round(hours, 2),
                "kind": "running_stalled" if row["status"] == "running" else "checkpoint_pending",
            })
        report: dict[str, Any] = {
            "workflow_id": workflow_id,
            "stall_hours": float(stall_hours),
            "alert": bool(stalled),
            "stalled": stalled,
        }
        if stalled:
            self._log(workflow_id, None, None, "stall_alert",
                      f"检测到 {len(stalled)} 个停滞步骤（>{stall_hours} 小时无进展）",
                      stalled=stalled)
            self._audit_record(type="engine_event", event="step_stall_alert",
                               workflow_id=workflow_id, stall_hours=float(stall_hours),
                               stalled=stalled)
        return report

    def backfill_step(self, workflow_id: str, skill_name: str, artifacts: list[str],
                      commands: list[str] | None = None, note: str = "",
                      by: str = "") -> RunResult:
        """手工补录绕开 runner 完成的步骤（D1 溯源链闭合）。

        把手工步骤的真实产物哈希与命令补进事件库与 STEP_MANIFEST，走带内
        转移（PENDING/BLOCKED→RUNNING→COMPLETED），不新增状态机边、不绕过
        审计。事件类型记 ``step_backfilled``（区别于 step_completed，复审时
        可区分"在环执行"与"人工补录"）。产物不存在即拒绝（backfill 只补
        真实存在的产物，防伪造溯源）。
        """
        workflow = self._workflow(workflow_id)
        row = self.store._connection.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND name = ? "
            "ORDER BY position LIMIT 1",
            (workflow_id, skill_name),
        ).fetchone()
        if row is None:
            return RunResult(workflow_id, "failed",
                             message=f"未知步骤: {skill_name}（--step 须为模板中的 skill_name）")
        step = self.store._step_from_row(row)
        if step.status == StepStatus.COMPLETED:
            return RunResult(workflow_id, "failed", step.id,
                             f"步骤 {skill_name} 已 COMPLETED，无需补录")
        workspace = Path(workflow.metadata["workspace"])
        missing = [a for a in artifacts if not (workspace / a).exists()]
        if missing:
            return RunResult(workflow_id, "failed", step.id,
                             "补录产物在工作区不存在: " + ", ".join(missing)
                             + "（backfill 只补录真实存在的产物；相对路径基于工作区根）")
        if not artifacts:
            return RunResult(workflow_id, "failed", step.id,
                             "补录至少需要 --artifact 一个产物（防空补录洗白断链）")

        # 带内转移 1：→ RUNNING（PENDING/BLOCKED 合法；已在 RUNNING 则不动）
        if step.status != StepStatus.RUNNING:
            self.store.transition_step(step.id, StepStatus.RUNNING)
        # 产物哈希（复用 ArtifactManifest，与 complete_step 同一产物账本口径）
        manifest = ArtifactManifest.validate(workspace, artifacts)
        if not manifest.get("ok"):
            return RunResult(workflow_id, "failed", step.id,
                             "产物校验失败: " + "; ".join(
                                 [f"missing: {', '.join(manifest['missing'])}" if manifest.get("missing") else "",
                                  f"invalid: {', '.join(manifest['invalid'])}" if manifest.get("invalid") else "",
                                 ]).strip("; "))
        config = {
            "workflow_id": workflow.id,
            "step_name": step.name,
            "backfill": True,
            "by": by,
            "note": note,
            "params": workflow.metadata.get("params", {}),
        }
        manifest_path = write_step_manifest(
            workspace=workspace,
            step_name=step.name,
            config=config,
            inputs=[],
            outputs=[workspace / a for a in artifacts],
            backend="manual-backfill",
            commands=[{"command": c, "exitCode": 0} for c in (commands or [])],
            dependencies={},
        )
        # 带内转移 2：RUNNING → COMPLETED，产物哈希进 artifacts 表 + 事件 payload
        self.store.transition_step_with_checkpoint(
            workflow_id, step.id, StepStatus.COMPLETED,
            {"status": "backfilled", "by": by, "note": note,
             "manifest": _manifest_payload(manifest)},
            artifacts=[{"name": Path(a).name, "path": a,
                        "metadata": {"sha256": art.sha256, "size": art.size}}
                       for a, art in zip(artifacts, manifest["artifacts"])],
            event={"type": "step_backfilled", "skill_name": step.name, "by": by,
                   "note": note, "artifacts": list(artifacts),
                   "commands": list(commands or []),
                   "manifest_path": str(manifest_path)},
        )
        self._log(workflow_id, step.id, step.name, "backfill",
                  f"步骤 {step.name} 手工补录（by={by or '未署名'}，产物 {len(artifacts)} 项）",
                  agent=by or self._agent_label(workflow))
        self._audit_record(type="engine_event", event="step_backfilled",
                           workflow_id=workflow_id, step_id=step.id,
                           skill_name=step.name, by=by, artifacts=list(artifacts))

        # 补录后若无 pending/blocked/failed 步骤，正常收尾工作流
        if (not self._has_pending_steps(workflow_id)
                and self._first_blocked_step(workflow_id) is None
                and self._has_failed_steps(workflow_id) is None):
            self.store.complete_workflow(workflow_id)
            self._log(workflow_id, None, None, "completed",
                      "所有步骤完成（含手工补录）", agent=self._agent_label(workflow))
        return RunResult(workflow_id, "advanced", step.id,
                         message=f"步骤 {step.name} 补录完成（step_backfilled 事件已落账，"
                                 f"STEP_MANIFEST 已更新）")

    def _latest_checkpoint_id(self, step_id: str) -> str | None:
        """返回步骤最近一次 checkpoint 的 ID（供 next blocked 输出，A5 ⑦ 修复）。"""
        row = self.store._connection.execute(
            "SELECT id FROM checkpoints WHERE step_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (step_id,),
        ).fetchone()
        return row[0] if row else None

    def _has_pending_steps(self, workflow_id: str) -> bool:
        """检查工作流是否还有待执行的 pending 步骤。"""
        row = self.store._connection.execute(
            "SELECT COUNT(*) FROM workflow_steps WHERE workflow_id = ? AND status = 'pending'",
            (workflow_id,),
        ).fetchone()
        return row[0] > 0 if row else False

    def _workflow(self, workflow_id: str) -> Workflow:
        row = self.store._connection.execute(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
        ).fetchone()
        if row is None:
            raise KeyError(workflow_id)
        return Workflow(
            row["id"], row["name"], row["status"],
            json.loads(row["metadata"]), row["created_at"], row["updated_at"],
        )

    def _agent_label(self, workflow: Workflow) -> str:
        """返回当前步骤的执行 agent 标签（默认 OpenCode Desktop 数模专家）。"""
        params = workflow.metadata.get("params", {})
        return str(params.get("agent", "") or "OpenCode Desktop 数模专家")

    def _log(self, workflow_id: str, step_id: str | None, step_name: str | None,
             event: str, message: str = "", **metadata) -> None:
        """写入运行日志；日志器未创建时静默跳过（不阻断主流程）。"""
        if self.logger is not None:
            try:
                self.logger.log(workflow_id, step_id, step_name, event, message, **metadata)
            except Exception:
                pass

    def _next_pending_step(self, workflow_id: str):
        row = self.store._connection.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND status = 'pending' ORDER BY position LIMIT 1",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return None
        return self.store._step_from_row(row)

    def _last_running_step(self, workflow_id: str):
        row = self.store._connection.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND status = 'running' ORDER BY updated_at DESC LIMIT 1",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return None
        return self.store._step_from_row(row)

    def _has_failed_steps(self, workflow_id: str) -> str | None:
        row = self.store._connection.execute(
            "SELECT name FROM workflow_steps WHERE workflow_id = ? AND status = 'failed' ORDER BY position LIMIT 1",
            (workflow_id,),
        ).fetchone()
        return row[0] if row else None

    def _first_blocked_step(self, workflow_id: str):
        """checkpoint 等待批准的步骤（blocked）。2026-09-09 审计 P1-2：blocked 必须是推进硬闸。"""
        row = self.store._connection.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND status = 'blocked' ORDER BY position LIMIT 1",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return None
        return self.store._step_from_row(row)

    def _action_for_step(self, workflow: Workflow, step: Any) -> StepAction:
        return StepAction(
            workflow_id=workflow.id, step_id=step.id, position=step.position, skill_name=step.name,
            display_name=step.metadata.get("display_name", step.name),
            workspace=Path(workflow.metadata["workspace"]), skill_path=self.skills_root / step.name / "SKILL.md",
            output_files=step.metadata.get("output_files", []), primary_output=step.metadata.get("primary_output", ""),
            has_checkpoint=step.metadata.get("has_checkpoint", False), checkpoint_type=step.metadata.get("checkpoint_type"),
            companion_skills=step.metadata.get("companion_skills", []),
            assets=step.metadata.get("assets", []),
            quick_gates=bool(step.metadata.get("quick_gates", False)),
            params=workflow.metadata.get("params", {}),
        )

    def _write_step_manifest(self, workflow: Workflow, step: Any, evidence: dict[str, Any], declared_outputs: list[str]) -> None:
        workspace = Path(workflow.metadata["workspace"])
        step_meta = dict(step.metadata) if step.metadata else {}
        backend = str(step_meta.get("backend") or "workflow-runner")
        dependencies = dict(step_meta.get("dependencies") or {})
        if step.name == "copyright-source-materials":
            backend = "vendored-codesucker-core 0.4.4"
            dependencies.setdefault("codesucker-core", "0.4.4")
        commands = evidence.get("commands", [])
        manifest_outputs = [workspace / output for output in declared_outputs]
        config = dict(step_meta.get("manifest_config") or {})
        config.setdefault("workflow_id", workflow.id)
        config.setdefault("step_name", step.name)
        config.setdefault("params", workflow.metadata.get("params", {}))
        write_step_manifest(
            workspace=workspace,
            step_name=step.name,
            config=config,
            inputs=[],
            outputs=manifest_outputs,
            backend=backend,
            commands=commands,
            dependencies=dependencies,
        )


def _manifest_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    """Convert artifact dataclasses into JSON-safe audit payloads."""
    return {
        **manifest,
        "artifacts": [
            {
                "path": artifact.path,
                "size": artifact.size,
                "sha256": artifact.sha256,
                "exists": artifact.exists,
                "mime_type": artifact.mime_type,
            }
            for artifact in manifest["artifacts"]
        ],
    }


def _manifest_artifacts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": Path(artifact.path).name, "path": artifact.path,
         "metadata": {"sha256": artifact.sha256, "size": artifact.size, "mime_type": artifact.mime_type}}
        for artifact in manifest["artifacts"]
    ]
