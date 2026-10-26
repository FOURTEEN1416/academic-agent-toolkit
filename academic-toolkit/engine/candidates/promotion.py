"""G2 promotion：把已完成的 explore 工作流冻结成不可变交付候选。

本模块只做一次性的“取证 + 冻结”：读取源工作流已接受的事件 manifest、递归
追溯产物的 producer 闭包、冻结输入/根产物字节与复现 recipe，并生成候选验收
合同。它不推进源工作流状态，也不复制第二套谱系/折叠逻辑——前者复用
``OperationContext.trace_lineage``，后者复用 ``accepted_artifacts_by_path``。
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping

from ..audit.audit_store import accepted_artifacts_by_path
from ..contracts.template_resolver import resolve_template, template_paper_scoring
from ..storage.workflow_store import DeliveryCandidate


class PromotionError(ValueError):
    """候选冻结失败（源不完整、根未接受、审批配置缺失等）。"""


# 与 quality_gates.py 的独立评审集合保持一致；comp-editor 是编辑步骤，
# 不产生 review 操作，不能当作 required_reviews。
_REVIEW_ROLES = {
    "comp-review": "review",
    "comp-visual-review": "visual",
    "comp-final-review": "final",
}

# comp-final-review/SKILL.md 的固定读取清单。清单外的评审输入必须由
# ``--root`` 显式覆盖，否则 candidate_review 会因读取集合外路径而失败。
# P4-1（裁决 6.6-A）：每个 comp_* 模板顶层必须显式声明 ``review_inputs``
# （允许空列表），冻结读取集合由声明推导；本元组只作为**未声明模板**的
# legacy 缺省，保持 2026-10-25 改造前的行为。PAPER_SCORING.json 是条件输入：
# 声明 ``paper_scoring: true`` 的链在自己的 review_inputs 里显式列入；
# 未声明模板仍按 legacy 口径要求它（false 声明时由 paper_scoring 条件跳过）。
_REVIEW_INPUTS = (
    "paper/main.tex",
    "paper/main.pdf",
    "RESULTS.md",
    "figures/all_results.json",
    "CONSISTENCY_REPORT.json",
    "LITERATURE.md",
    "PAPER_SCORING.json",
    "COMP_REVIEW_VERDICT.json",
    "VISUAL_REVIEW_VERDICT.json",
    "EDITOR_CHANGELOG.md",
)

_RULE_FILE_NAMES = ("comp_rules.json", "quality_gates.json", "contest_models.json")


def _review_inputs_for(template_name: str, catalog: Mapping[str, Any]) -> tuple[str, ...]:
    """按模板显式声明推导候选冻结的评审输入清单。

    P4-1：``review_inputs`` 是模板级契约（允许空列表）。字段缺席时回退到
    ``_REVIEW_INPUTS``（legacy 口径），由 tests 层的一致性测试锁死「comp_*
    模板必须显式声明」，避免新模板作者漏写后静默少冻结。
    """
    template = catalog.get(template_name) if isinstance(catalog, Mapping) else None
    if not isinstance(template, dict) or "review_inputs" not in template:
        return _REVIEW_INPUTS
    raw = template["review_inputs"]
    if not isinstance(raw, list):
        raise PromotionError(
            f"模板 {template_name} 的 review_inputs 必须是数组（允许空）: {type(raw).__name__}")
    declared: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise PromotionError(
                f"模板 {template_name} 的 review_inputs 含非法条目（需非空字符串）: {item!r}")
        name = item.strip()
        if name in declared:
            raise PromotionError(f"模板 {template_name} 的 review_inputs 重复声明: {name}")
        declared.append(name)
    return tuple(declared)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _norm_path(value: Any) -> str:
    return os.path.normcase(str(value).replace("\\", "/")).replace("\\", "/")


def _workspace_relative(workspace: Path, value: str) -> str:
    """把工作区相对路径规范化；拒绝绝对路径、越界路径与 .engine 状态域。"""
    text = str(value or "").strip()
    if not text:
        raise PromotionError("候选路径不能为空")
    raw = Path(text)
    if raw.is_absolute() or os.path.isabs(text):
        raise PromotionError(f"候选路径必须是工作区相对路径: {text}")
    candidate_path = workspace / raw
    for ancestor in (candidate_path, *candidate_path.parents):
        if ancestor == workspace:
            break
        if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
            raise PromotionError(f"候选路径不能经过链接或目录联结: {text}")
    resolved = candidate_path.resolve()
    try:
        relative = resolved.relative_to(workspace)
    except ValueError:
        raise PromotionError(f"候选路径越出工作区: {text}") from None
    if ".engine" in relative.parts:
        raise PromotionError(f"候选路径不能指向引擎状态域: {text}")
    return relative.as_posix()


def _normalise_roots(workspace: Path, roots: Iterable[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in roots:
        relative = _workspace_relative(workspace, str(value))
        key = _norm_path(relative)
        if key in seen:
            continue
        seen.add(key)
        path = workspace / relative
        if not path.is_file():
            raise PromotionError(f"候选根产物不存在: {relative}")
        records.append({"path": relative, "sha256": _sha256_file(path)})
    if not records:
        raise PromotionError("promote 至少需要一个根产物")
    return records


def _accepted_lookup(accepted: Mapping[str, Mapping[str, Any]], path: str) -> Mapping[str, Any] | None:
    wanted = _norm_path(path)
    if wanted in accepted:
        return accepted[wanted]
    for key, artifact in accepted.items():
        if _norm_path(key) == wanted or _norm_path(artifact.get("path", "")) == wanted:
            return artifact
    return None


def _source_snapshot(store, workflow_id: str):
    workflow = store.get_workflow(workflow_id)
    metadata = workflow.metadata if isinstance(workflow.metadata, dict) else {}
    contract = metadata.get("execution_contract")
    contract = contract if isinstance(contract, dict) else {}
    if str(contract.get("tier") or "") != "explore":
        raise PromotionError("只有 execution_contract.tier=explore 的工作流可以 promote")
    if workflow.status == "abandoned":
        raise PromotionError("已放弃（abandoned）的 explore 工作流不能 promote")
    rows = store._connection.execute(
        "SELECT id, name, position, status, attempt_id, revision FROM workflow_steps "
        "WHERE workflow_id=? ORDER BY position, rowid", (workflow_id,)).fetchall()
    if not rows:
        raise PromotionError("源工作流没有步骤")
    incomplete = [row["name"] for row in rows if row["status"] != "completed"]
    if incomplete:
        raise PromotionError("源 explore 工作流尚未全部 COMPLETED: " + ", ".join(incomplete))
    source = max(rows, key=lambda row: (int(row["position"]), row["id"]))
    if not source["attempt_id"]:
        raise PromotionError("源工作流缺少可追溯的 attempt_id")
    workspace = Path(str(metadata.get("workspace") or "")).resolve()
    if not str(metadata.get("workspace") or ""):
        raise PromotionError("源工作流缺少 workspace 元数据")
    return workflow, metadata, rows, source, workspace


def _trace_lineage(store, workflow_id: str, source, workspace: Path, roots: list[dict[str, Any]],
                   project_root: Path) -> dict[str, Any]:
    from execution.context import OperationContext

    action = SimpleNamespace(
        workflow_id=workflow_id, step_id=source["id"], attempt_id=source["attempt_id"],
        expected_revision=int(source["revision"]), workspace=workspace,
    )
    context = OperationContext(store, action, project_root)
    return context.trace_lineage({root["path"]: root["sha256"] for root in roots})


def _freeze_inputs(lineage: Mapping[str, Any], roots: list[dict[str, Any]],
                   accepted: Mapping[str, Mapping[str, Any]],
                   missing: list[str], *, paper_scoring_required: bool = True,
                   review_inputs: Iterable[str] | None = None) -> dict[str, dict[str, Any]]:
    """lineage 输入 + 模板声明的评审输入清单，统一成 inputs_json。

    ``review_inputs`` 为 None 时按 legacy 元组处理（未声明模板的旧行为）。
    ``paper_scoring_required=False``（模板显式声明 ``paper_scoring: false``）时
    不把 PAPER_SCORING.json 记入必需输入，也不因它缺件写 missing；该文件若真的
    被生产过，仍会作为普通 lineage 输入进入 inputs。
    """
    declared_inputs = _REVIEW_INPUTS if review_inputs is None else tuple(review_inputs)
    root_paths = {_norm_path(root["path"]) for root in roots}
    inputs: dict[str, dict[str, Any]] = {}
    producer_operations = lineage.get("producer_operations") if isinstance(
        lineage.get("producer_operations"), dict) else {}
    depths = lineage.get("input_depths") if isinstance(lineage.get("input_depths"), dict) else {}
    for path, digest in (lineage.get("lineage_inputs") or {}).items():
        if _norm_path(path) in root_paths:
            continue
        producer_id = producer_operations.get(path)
        inputs[str(path)] = {
            "sha256": str(digest),
            "producer_operation_id": str(producer_id) if producer_id else None,
            "kind": "produced" if producer_id else "external",
            "depth": int(depths.get(path, 1) or 1),
        }
    for name in declared_inputs:
        if name == "PAPER_SCORING.json" and not paper_scoring_required:
            continue
        if _norm_path(name) in root_paths:
            continue
        artifact = _accepted_lookup(accepted, name)
        if artifact is None:
            missing.append(f"review_input:{name}")
            continue
        digest = str(artifact.get("sha256") or "")
        if not digest:
            missing.append(f"review_input:{name}")
            continue
        prior = inputs.get(name) if isinstance(inputs.get(name), dict) else {}
        inputs[name] = {
            "sha256": digest,
            "producer_operation_id": prior.get("producer_operation_id"),
            "kind": "review_input",
            "depth": int(prior.get("depth", 1) or 1),
        }
    return inputs


def _operation_payload(store, operation_id: str) -> tuple[str, Mapping[str, Any]]:
    row = store._connection.execute(
        "SELECT kind, status, payload FROM execution_operations WHERE id=?", (operation_id,)).fetchone()
    if row is None:
        raise PromotionError(f"冻结 recipe 失败：生产操作不存在 {operation_id}")
    try:
        payload = json.loads(row["payload"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise PromotionError(f"冻结 recipe 失败：操作载荷不可解析 {operation_id}: {exc}") from None
    if not isinstance(payload, dict):
        raise PromotionError(f"冻结 recipe 失败：操作载荷不是对象 {operation_id}")
    return str(row["kind"]), payload


def _freeze_recipe(store, producer_operations: Mapping[str, str],
                   frozen_versions: Mapping[str, str]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """按 producer 冻结 recipe；command 产出同时成为复现目标。"""
    recipes: dict[str, Any] = {}
    kinds: dict[str, str] = {}
    for operation_id in sorted({str(value) for value in producer_operations.values() if value}):
        kind, payload = _operation_payload(store, operation_id)
        kinds[operation_id] = kind
        entry: dict[str, Any] = {
            "recipe_id": operation_id,
            "operation_id": operation_id,
            "kind": kind,
            "node_key": str(payload.get("node") or ""),
        }
        if kind == "command":
            entry.update({
                "argv": list(payload.get("argv") or []),
                "cwd": str(payload.get("cwd") or "."),
                "inputs": sorted(str(path) for path in (payload.get("inputs_snapshot") or {})),
                "outputs": sorted(str(path) for path in (payload.get("outputs_snapshot") or {})),
                "mutates": sorted(str(path) for path in (payload.get("mutates") or [])),
                "inputs_snapshot": dict(payload.get("inputs_snapshot") or {}),
                "outputs_snapshot": dict(payload.get("outputs_snapshot") or {}),
                "cacheable": bool(payload.get("cacheable")),
            })
        elif kind == "write":
            entry.update({
                "path": str(payload.get("path") or ""),
                "operation": str(payload.get("operation") or ""),
                "previous_sha256": payload.get("previous_sha256"),
                "outputs_snapshot": dict(payload.get("outputs_snapshot") or {}),
            })
        else:
            entry.update({
                "inputs_snapshot": dict(payload.get("inputs_snapshot") or {}),
                "outputs_snapshot": dict(payload.get("outputs_snapshot") or {}),
            })
        recipes[operation_id] = entry

    targets: list[dict[str, str]] = []
    for path, digest in sorted(frozen_versions.items()):
        producer_id = str(producer_operations.get(path) or "")
        if not producer_id or kinds.get(producer_id) != "command":
            continue
        entry = recipes.get(producer_id) or {}
        if str((entry.get("outputs_snapshot") or {}).get(path) or "") != str(digest):
            continue
        targets.append({"path": str(path), "sha256": str(digest), "recipe_id": producer_id})
    return recipes, targets


def _closure(store, producer_operations: Mapping[str, str]) -> list[str]:
    """检查 write producer 的输入声明；显式空输入与 legacy 非空快照都算已知。"""
    unknown: list[str] = []
    for path, operation_id in sorted(producer_operations.items()):
        try:
            kind, payload = _operation_payload(store, str(operation_id))
        except PromotionError:
            unknown.append(str(path))
            continue
        if kind != "write":
            continue
        if "declared_inputs" in payload or payload.get("dependency_policy") == "explicit-declared-inputs-v1":
            continue
        if payload.get("inputs_snapshot") or payload.get("lineage_inputs"):
            continue
        unknown.append(str(path))
    return unknown


def _read_approval_policy(workspace: Path) -> dict[str, Any]:
    config = workspace / ".engine" / "approvers.json"
    if not config.is_file():
        raise PromotionError("promote 需要操作者手写的 workspace/.engine/approvers.json")
    raw = config.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PromotionError(f"approvers.json 不可解析: {exc}") from None
    if not isinstance(data, dict):
        raise PromotionError("approvers.json 必须是对象")
    raw_approvers = data.get("approvers")
    if not isinstance(raw_approvers, list):
        raise PromotionError("approvers.json 的 approvers 必须是数组")
    approvers = [str(value).strip() for value in raw_approvers if str(value).strip()]
    if not approvers:
        raise PromotionError("approvers.json 的 approvers 不能为空")
    if data.get("require_human") is not True:
        raise PromotionError("approvers.json 必须显式声明 require_human=true")
    return {
        "approvers": list(dict.fromkeys(approvers)),
        "require_human": True,
        "config_sha256": _sha256_bytes(raw),
    }


def _relative_to_project(project_root: Path, value: Path | str, label: str) -> str:
    try:
        return Path(value).resolve().relative_to(Path(project_root).resolve()).as_posix()
    except ValueError:
        raise PromotionError(f"{label} 必须位于 project_root 内: {value}") from None


def _freeze_acceptance(*, template: str, params: Mapping[str, Any], catalog: Mapping[str, Any],
                       project_root: Path, skills_root: Path, rules_root: Path,
                       approval_policy: Mapping[str, Any],
                       reproduction_targets: list[dict[str, str]]) -> tuple[dict[str, Any], list[str]]:
    try:
        resolved = resolve_template(template, dict(params), dict(catalog))
    except KeyError:
        raise PromotionError(f"交付模板不存在: {template}") from None
    if not resolved:
        raise PromotionError("交付模板解析后没有步骤")

    delivery_steps: list[dict[str, Any]] = []
    required_reviews: list[dict[str, str]] = []
    for raw in resolved:
        item = dict(raw)
        skill_name = str(item.get("skill_name") or "")
        if not skill_name:
            raise PromotionError("交付模板存在缺少 skill_name 的步骤")
        skill_file = Path(skills_root) / skill_name / "SKILL.md"
        item["skill_name"] = skill_name
        item["skill_sha256"] = _sha256_file(skill_file) if skill_file.is_file() else ""
        item["output_files"] = list(item.get("output_files") or [])
        item["primary_output"] = str(item.get("primary_output") or "")
        item["required_checks"] = list(item.get("required_checks") or [])
        item["output_specs"] = dict(item.get("output_specs") or {})
        item["has_checkpoint"] = bool(item.get("has_checkpoint"))
        item["checkpoint_type"] = item.get("checkpoint_type")
        delivery_steps.append(item)
        role = _REVIEW_ROLES.get(skill_name)
        if role:
            required_reviews.append({"skill_name": skill_name, "role": role})

    rules: dict[str, str] = {}
    for name in _RULE_FILE_NAMES:
        candidate = Path(rules_root) / name
        if candidate.is_file():
            rules[name] = _sha256_file(candidate)

    acceptance = {
        "version": 1,
        "template": template,
        "params": dict(params),
        "skills_root": _relative_to_project(project_root, skills_root, "skills_root"),
        "rules_root": _relative_to_project(project_root, rules_root, "rules_root"),
        "rule_files": rules,
        "delivery_steps": delivery_steps,
        "required_reviews": required_reviews,
        "reproduction_targets": list(reproduction_targets),
        "approval_policy": dict(approval_policy),
    }
    missing: list[str] = []
    if not required_reviews:
        missing.append("review_step")
    if not any(step["skill_name"] == "comp-final-audit" and step["has_checkpoint"]
               for step in delivery_steps):
        missing.append("approval_checkpoint")
    return acceptance, missing


def freeze_candidate(store, workflow_id: str, roots: Iterable[str], *, by: str,
                     template: str = "", catalog: Mapping[str, Any],
                     project_root: Path, skills_root: Path,
                     rules_root: Path) -> DeliveryCandidate:
    """冻结一个交付候选；源 explore 工作流只读，任何内容列插入后不可变。"""
    workflow, metadata, _steps, source, workspace = _source_snapshot(store, workflow_id)
    root_records = _normalise_roots(workspace, roots)

    timeline = store.workflow_timeline(workflow_id)
    accepted = accepted_artifacts_by_path(workspace, list(timeline.get("checkpoints") or []),
                                          list(timeline.get("events") or []))
    for root in root_records:
        artifact = _accepted_lookup(accepted, root["path"])
        if artifact is None:
            raise PromotionError(f"根产物不是事件 manifest 中的已接受版本: {root['path']}")
        accepted_sha = str(artifact.get("sha256") or "")
        if accepted_sha.lower() != root["sha256"].lower():
            raise PromotionError(f"根产物当前字节与已接受版本不一致: {root['path']}")

    params = metadata.get("params") if isinstance(metadata.get("params"), dict) else {}
    for key, value in params.items():
        if str(key).startswith("skip_") and bool(value):
            raise PromotionError(f"交付验收合同不得含 truthy skip_ 参数: {key}")
    template_name = str(template or metadata.get("template") or workflow.name).strip()
    if not template_name:
        raise PromotionError("promote 需要交付模板或源工作流 template 元数据")
    try:
        paper_scoring_required = template_paper_scoring(template_name, catalog)
    except ValueError as exc:
        raise PromotionError(str(exc)) from None
    review_inputs = _review_inputs_for(template_name, catalog)

    lineage = _trace_lineage(store, workflow_id, source, workspace, root_records, project_root)
    missing: list[str] = []
    inputs = _freeze_inputs(lineage, root_records, accepted, missing,
                           paper_scoring_required=paper_scoring_required,
                           review_inputs=review_inputs)
    frozen_versions = {path: str(meta["sha256"]) for path, meta in inputs.items()}
    frozen_versions.update({root["path"]: root["sha256"] for root in root_records})

    producer_operations = lineage.get("producer_operations") if isinstance(
        lineage.get("producer_operations"), dict) else {}
    for root in root_records:
        root["producer_operation_id"] = producer_operations.get(root["path"])
    recipe, reproduction_targets = _freeze_recipe(store, producer_operations, frozen_versions)
    unknown_inputs = _closure(store, producer_operations)
    if unknown_inputs:
        missing.append("closure")

    approval_policy = _read_approval_policy(workspace)
    acceptance, acceptance_missing = _freeze_acceptance(
        template=template_name, params=params, catalog=catalog, project_root=project_root,
        skills_root=skills_root, rules_root=rules_root, approval_policy=approval_policy,
        reproduction_targets=reproduction_targets,
    )
    missing.extend(acceptance_missing)
    # 候选创建时尚未跑复现/审核/批准；这三项是初始缺口的显式记账，
    # 后续 candidate_readiness 按交付工作流的真实操作逐项复算。
    missing = list(dict.fromkeys(["reproduction", "review", "approval", *missing]))

    lineage_json = {
        "producer_operations": dict(producer_operations),
        "external_inputs": dict(lineage.get("external_inputs") or {}),
        "input_depths": dict(lineage.get("input_depths") or {}),
        "lineage_inputs": dict(lineage.get("lineage_inputs") or {}),
        "unknown_inputs": unknown_inputs,
        "paper_scoring_required": paper_scoring_required,
        "review_inputs": list(review_inputs),
        "source_step_id": source["id"],
        "source_attempt_id": source["attempt_id"],
    }
    logical_target = hashlib.sha256(
        _canonical_json(sorted(root["path"] for root in root_records)).encode()).hexdigest()
    return store.create_candidate(
        source_workflow_id=workflow_id,
        source_step_id=source["id"],
        source_attempt_id=source["attempt_id"],
        roots=root_records,
        inputs=inputs,
        frozen_versions=frozen_versions,
        lineage=lineage_json,
        recipe=recipe,
        acceptance=acceptance,
        acceptance_sha256=_canonical_sha256(acceptance),
        missing=missing,
        created_by=str(by or ""),
        logical_target=logical_target,
    )
