"""Versioned, workspace-contained execution evidence for workflow steps."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .agent_bridge import StepAction, StepResult
from .step_manifest import atomic_write_json


SCHEMA_VERSION = 1
CONTRACT_TIERS = ("delivery", "explore")
_REQUIRED_FIELDS = {
    "schema_version", "agent", "step_id", "skill_name", "skill_sha256",
    "commands", "inputs", "outputs",
}


def _workflow_contract_tier(workflow_metadata: Any) -> str:
    """Read the workflow's execution contract tier (legacy workflows are delivery).

    An explicitly declared unknown tier is an error: silently downgrading it to
    delivery would let a typo disable explore semantics.
    """
    contract = workflow_metadata.get("execution_contract") if isinstance(workflow_metadata, dict) else None
    if contract is None:
        return "delivery"
    if not isinstance(contract, dict):
        raise ValueError("execution_contract metadata must be an object")
    if "tier" not in contract:
        return "delivery"
    tier = contract.get("tier")
    if tier not in CONTRACT_TIERS:
        raise ValueError(f"unknown execution contract tier: {tier!r}")
    return tier


# Windows 盘符（C:\、C:/）——冒号是路径语法不是描述性分隔符（A5 误杀②修复：
# `C:/Program Files/draw.io/draw.io.EXE -x ...` 曾被 ':' 规则误杀）
_WINDOWS_DRIVE_RE = re.compile(r"\b[A-Za-z]:[\\/]")


def _strip_quoted_spans(text: str) -> str:
    """命令含成对引号时把引号内内容替换为空格，返回"外壳"。

    引号内内容（grep 模式、-c 代码、带空格路径）是被操作的对象，
    不算命令作者的自述——描述性判断只看引号外的外壳。
    引号不成对（奇数个）视为字面量，返回原文。
    （A5 误杀①修复：`grep -q '<!-- END FIGURE_MANIFEST -->' file` 曾被
    引号内 "-->" 箭头规则误杀，而这是 comp-problem-analysis 完成铁律强制命令）
    """
    shell = text
    for quote in ("'", '"'):
        if shell.count(quote) >= 2 and shell.count(quote) % 2 == 0:
            kept = []
            inside = False
            for ch in shell:
                if ch == quote:
                    inside = not inside
                    kept.append(" ")
                else:
                    kept.append(" " if inside else ch)
            shell = "".join(kept)
    return shell


def _looks_like_descriptive_command(command: str) -> bool:
    """启发式判断命令是否为描述性文本（伪命令）。

    判定为伪命令的条件（任一）：
    1. 命令文本包含句子性标点（句号+空格、中文句号、逗号后接中文等），
       且不以可执行文件/脚本路径开头；
    2. 首词不是已知可执行程序/解释器/脚本且包含空格后接自然语言动词
       （inspection/check/review/generation/verification 等名词短语）。
    保守起见：仅当同时满足「首词可执行」与「命令不含 shell 元字符/重定向/管道」
    之外的描述性特征时才判伪——宁可放行不可误伤。
    引号内内容（成对 '…' 或 "…"）不算命令作者的自述，箭头/描述性规则只看外壳。
    """
    text = command.strip()
    if not text:
        return True
    # 引号外壳：引号内内容是被操作对象，描述性判断只对引号外外壳生效
    shell = _strip_quoted_spans(text)
    # 描述性箭头（-> / →）优先检测且只看外壳——"main.docx -> main.pdf"（无引号）
    # 是流程描述；引号内 "-->"（如 grep 模式）不是作者自述。
    # 其中的 ">" 会与 shell 重定向元字符混淆，必须先于 shell 检查处理。
    if "->" in shell or "→" in shell:
        return True
    # 允许常见的 shell 结构（管道/重定向/逻辑符/子 shell）——外壳上出现才是
    # 命令作者写的真实命令结构（引号内的 | > < 是字面量）
    shell_constructs = ("|", ">", "<", "&&", "||", ";", "$(", "`")
    if any(c in shell for c in shell_constructs):
        return False
    # 描述性句子特征：外壳以句号/中文句号结尾（引号内句号不算）
    if shell.rstrip().endswith((".", "。", "！", "？")):
        return True
    # 解析首词与剩余部分
    parts = text.split(None, 1)
    first_token = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ""
    # `-c` / `-m` / `--flag` 等立即参数：解释器直接执行代码/模块 → 真实命令；
    # 但 `-c` 后只有注释文本（# 开头、无实际代码）属于伪命令。
    if rest.startswith(("-c", "-m", "--")):
        if rest.startswith("-c"):
            code = rest[2:].strip().strip('"').strip("'")
            if code.startswith("#") or not code:
                return True
        return False
    # "python xxx inspection for ..." 这类描述（首词可执行但后续是自然语言）
    executable_roots = {
        "python", "python3", "py", "bash", "sh", "cmd", "powershell", "pwsh",
        "node", "npm", "npx", "pip", "git", "dotnet", "java", "ruby", "perl",
        "xelatex", "pdflatex", "latexmk", "drawio", "soffice", "word", "excel",
        "rscript", "Rscript", "tesseract", "magick", "convert", "ffmpeg",
    }
    if first_token in executable_roots:
        if first_token.lower() == "word":
            # "Word COM main.docx -> main.pdf" 是文档流程描述，不是命令
            return True
        if not rest:
            return False  # 裸解释器不判伪
        if rest.startswith(("/", "\\", ".", "..", "@")):
            return False
        if " " not in rest and "." in rest:
            return False  # 单个脚本文件（如 solve.py）
        natural_language_words = (
            "inspection", "check", "review", "verification", "verifying",
            "analysis", "analyzing", "generation", "generating", "for the",
            "for four", "capability", "coverage", "workbook", "script that",
            "to ", "the ", "and ", "with ",
        )
        lowered = rest.lower()
        if any(lowered.startswith(w) or f" {w} " in f" {lowered} " for w in natural_language_words):
            return True
        return False
    # 首词不是已知可执行程序：含括号说明/冒号等描述性特征 → 伪命令；
    # 冒号规则排除 Windows 盘符冒号（C:\、C:/ 开头段）——那是路径语法
    colon_scan = _WINDOWS_DRIVE_RE.sub(" ", shell)
    if "(" in colon_scan or ")" in colon_scan or ":" in colon_scan:
        return True
    # 首词带路径/扩展名（如 C:\...\xelatex.EXE、./tools/x.py）→ 真实命令
    if "/" in first_token or "\\" in first_token or "." in first_token:
        return False
    # 无法判定：保守放行（宁可放行不可误伤）
    return False


def _relative_path(workspace: Path, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("evidence paths must be non-empty strings")
    candidate = Path(value)
    if candidate.is_absolute() or os.path.isabs(value):
        raise ValueError(f"evidence path must be workspace-relative: {value}")
    root = workspace.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"evidence path escapes workspace: {value}") from exc
    return resolved.relative_to(root).as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_command_record(command: dict[str, Any], workspace: Path) -> dict[str, Any]:
    """Adapt real bridge receipts without inventing execution or success."""
    normalized = dict(command)
    raw = command.get("command")
    if isinstance(raw, list):
        if not raw or any(not isinstance(v, str) for v in raw):
            raise ValueError("command argv must be a non-empty string list")
        normalized["argv"] = list(raw)
        normalized["command"] = subprocess.list2cmdline(raw) if os.name == "nt" else shlex.join(raw)
    if "returncode" not in normalized and "exitCode" in command:
        normalized["returncode"] = command["exitCode"]
    elif "exitCode" in command and command["exitCode"] != normalized.get("returncode"):
        raise ValueError("conflicting returncode and exitCode")
    cwd = command.get("cwd", ".")
    if not isinstance(cwd, str):
        raise ValueError("command cwd must be a string")
    if Path(cwd).is_absolute():
        try:
            cwd = Path(cwd).resolve().relative_to(Path(workspace).resolve()).as_posix()
        except ValueError as exc:
            raise ValueError("command cwd escapes workspace") from exc
    normalized["cwd"] = _relative_path(Path(workspace), cwd)
    return normalized


def _is_blank_identity(value: Any) -> bool:
    """空串/None 视为"未提供"；0 与 False 是合法值，不算缺失。"""
    return value is None or (isinstance(value, str) and not value.strip())


def normalize_legacy_evidence(action: StepAction, evidence: dict[str, Any]) -> dict[str, Any]:
    """只用引擎已知身份回填 legacy evidence；绝不生成执行事实。

    旧接入（手工 `complete --evidence`）过去要求模型手抄 step_id / skill_sha256 /
    expected_revision 等身份字段——这些值引擎本来就有，抄错或抄漏只会制造噪声失败。
    这里补的只有"我是谁"：step_id/attempt_id/expected_revision/skill_name/
    skill_sha256/agent。commands/inputs/outputs/returncode 一律不生成、不补默认值，
    缺真实命令仍在 required-field 校验处被拒绝；已提供且冲突的值原样保留，
    由后续校验显式报冲突（不静默覆盖执行者声明）。
    """
    normalized = dict(evidence)
    # StepAction 在技能文件缺席时 skill_sha256 为空；有文件则按文件实况计算——
    # 这是引擎已拥有的身份，不是替执行者编造执行事实。
    skill_sha = action.skill_sha256 or (
        _file_sha256(action.skill_path) if action.skill_path.is_file() else "")
    defaults: dict[str, Any] = {
        "step_id": action.step_id,
        "attempt_id": action.attempt_id,
        "expected_revision": action.expected_revision,
        "skill_name": action.skill_name,
        "skill_sha256": skill_sha,
        "agent": str((action.params or {}).get("agent") or "execution-session"),
    }
    for field, value in defaults.items():
        if field not in normalized or _is_blank_identity(normalized[field]):
            normalized[field] = value
    return normalized


def validate_execution_evidence(
    workspace: Path, action: StepAction, result: StepResult, *, store=None, fingerprint_session=None,
    require_collection: bool = False,
) -> dict[str, Any]:
    """Validate and normalize version 1 evidence reported by the executing agent.

    ``require_collection`` (or ``StepAction.requires_collection``) restricts the
    caller to ``execution-session-v1`` evidence: candidate delivery must never
    accept hand-built legacy evidence.  Non-candidate workflows stay compatible.
    """
    evidence = result.metadata.get("execution_evidence")
    if not isinstance(evidence, dict):
        raise ValueError("execution evidence must be an object")
    # 单入口身份回填（W5）：引擎已知的身份字段不必由模型手抄；执行事实不代填。
    evidence = normalize_legacy_evidence(action, evidence)
    missing = sorted(_REQUIRED_FIELDS - evidence.keys())
    if missing:
        raise ValueError(f"execution evidence missing required fields: {', '.join(missing)}")
    if evidence["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported execution evidence schema version: {evidence['schema_version']!r}")
    if not isinstance(evidence["agent"], str) or not evidence["agent"].strip():
        raise ValueError("execution evidence agent must be a non-empty string")
    if evidence["step_id"] != action.step_id or evidence["skill_name"] != action.skill_name:
        raise ValueError("execution evidence does not match the active step")
    if not action.skill_path.is_file() or evidence["skill_sha256"] != _file_sha256(action.skill_path):
        raise ValueError("execution evidence skill_sha256 does not match the skill file")

    normalized = dict(evidence)
    # 证据真实性两档同严；tier 只是标记，必须与当前步骤一致，防止把探索档
    # 证据挂到交付档（或反之）导致验收策略错位。旧 evidence 无该字段时按
    # action 的档位补齐；action 也来自旧接入时回落 delivery。
    action_tier = getattr(action, "contract_tier", None)
    if action_tier is not None and action_tier not in CONTRACT_TIERS:
        raise ValueError(f"unknown execution contract tier: {action_tier!r}")
    declared_tier = evidence.get("contract_tier") or None
    if declared_tier is None:
        normalized["contract_tier"] = action_tier or "delivery"
    else:
        if declared_tier not in CONTRACT_TIERS:
            raise ValueError(f"unsupported execution contract tier: {declared_tier!r}")
        if action_tier is not None and declared_tier != action_tier:
            raise ValueError("execution evidence contract_tier does not match the active step")
        normalized["contract_tier"] = declared_tier

    collection = evidence.get("collection")
    if collection is None and (require_collection or bool(getattr(action, "requires_collection", False))):
        raise ValueError(
            "candidate delivery requires execution-session-v1 collection; legacy evidence is rejected")
    if collection is not None:
        if not isinstance(collection, dict) or collection.get("source") != "execution-session-v1":
            raise ValueError("execution collection must use execution-session-v1")
        _validate_collected_operations(workspace, action, evidence, store, fingerprint_session)
    elif evidence.get("resource_reads"):
        raise ValueError("resource_reads requires a persisted execution collection")
    elif evidence.get("workspace_observations"):
        # 观察清单只能来自执行会话的持久操作行；手写清单无法与任何
        # current_operations 对账，不能作为审计可见性证据。
        raise ValueError("workspace_observations requires a persisted execution collection")
    for field in ("inputs", "outputs"):
        paths = evidence[field]
        if not isinstance(paths, list):
            raise ValueError(f"execution evidence {field} must be a list")
        normalized[field] = [_relative_path(Path(workspace), value) for value in paths]

    claimed_artifacts = [_relative_path(Path(workspace), value) for value in result.artifacts]
    if set(normalized["outputs"]) != set(claimed_artifacts):
        raise ValueError("execution evidence outputs must match claimed artifacts")

    commands = evidence["commands"]
    if not isinstance(commands, list) or (not commands and not collection):
        raise ValueError("execution evidence commands must be a non-empty list")
    normalized_commands = []
    for command in commands:
        if not isinstance(command, dict):
            raise ValueError("execution evidence command records must be objects")
        command = normalize_command_record(command, Path(workspace))
        if not isinstance(command.get("command"), str) or not command["command"].strip():
            raise ValueError("execution evidence command record requires command")
        if _looks_like_descriptive_command(command["command"]):
            raise ValueError(
                f"execution evidence command is descriptive text, not an executable command: "
                f"{command['command'][:120]!r}"
            )
        if type(command.get("returncode")) is not int:
            raise ValueError("execution evidence command record requires integer returncode")
        if command["returncode"] != 0:
            raise ValueError("successful execution evidence commands must have returncode 0")
        normalized_command = dict(command)
        normalized_command["cwd"] = _relative_path(Path(workspace), command.get("cwd", "."))
        normalized_commands.append(normalized_command)
    normalized["commands"] = normalized_commands
    return normalized


def execution_contract(action, step_metadata, workflow_params, rules_root: Path,
                       tier: str = "delivery") -> str:
    """执行语义合同：只绑定"改变即影响执行"的要素。

    delivery 档保持 scope 2 原哈希（历史/在途操作仍按原值对账）；explore 档
    使用 scope 3 并显式携带 ``contract_tier="explore"``，使探索操作不会与
    交付操作混用合同。两档都只绑 skill/params，不绑纯质量规则：
    required_checks/companion_skills/output_specs 等 metadata 质量字段与
    modex-core 规则文件变化只在验收时由 quality_gates/output_contracts 按
    当前规则实时重验，不要求模型重跑命令刷新合同。

    兼容：历史/在途记录携带的是 scope 1（全量）合同，对账走 legacy_execution_contract。
    """
    tier = tier or "delivery"
    if tier not in CONTRACT_TIERS:
        raise ValueError(f"unknown execution contract tier: {tier!r}")
    body = {"contract_scope": 3 if tier == "explore" else 2,
            "params": workflow_params,
            "skill": _file_sha256(action.skill_path),
            "session_protocol": 1}
    if tier == "explore":
        body["contract_tier"] = "explore"
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def legacy_execution_contract(action, step_metadata, workflow_params, rules_root: Path) -> str:
    """scope 1 全量合同（历史口径）：仅用于对账既有操作记录，不再新发。"""
    body = {"metadata": step_metadata, "params": workflow_params,
            "skill": _file_sha256(action.skill_path),
            "rules": {p.name: _file_sha256(p) for p in rules_root.glob("*.json")},
            "session_protocol": 1}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def collect_execution_evidence(store, workflow, action, *, subagent_session="") -> dict[str, Any]:
    """从当前操作事实机械组装提交对象；只有执行协议拥有这份映射。"""
    rows = store.current_operations(action.step_id, action.attempt_id)
    pending = [row for row in rows if row["status"] not in {"succeeded", "reused"}]
    if pending:
        raise ValueError("尚有失败/中断操作，修复后重跑相应任务: " + ", ".join(row["node_key"] for row in pending))
    workflow_metadata = workflow.metadata if isinstance(workflow.metadata, dict) else {}
    delivery_candidate = workflow_metadata.get("delivery_candidate")
    if not isinstance(delivery_candidate, dict):
        delivery_candidate = {}
    resources = [row["payload"] for row in rows if row["kind"] == "resource"]
    consulted = {r["name"] for r in resources if r["kind"] == "skill"}
    all_assets = {r["name"] for r in resources if r["kind"] == "asset"}
    used_assets = all_assets & {a["name"] for a in action.assets}
    outputs = list(action.output_files or dict.fromkeys(
        path for row in rows for path in row["payload"].get("outputs_snapshot", {})))
    extra = sorted(consulted - set(action.companion_skills) - {action.skill_name})
    evidence = {"schema_version": SCHEMA_VERSION,
        "agent": workflow.metadata.get("params", {}).get("agent", "execution-session"),
        "step_id": action.step_id, "attempt_id": action.attempt_id,
        "expected_revision": action.expected_revision, "skill_name": action.skill_name,
        "skill_sha256": action.skill_sha256,
        "contract_tier": _workflow_contract_tier(workflow_metadata),
        "delivery_candidate_id": str(delivery_candidate.get("candidate_id") or ""),
        "workspace_observations": [
            {"operation_id": row["id"], "path": row["payload"].get("path"),
             "sha256": row["payload"].get("sha256"),
             "bytes": row["payload"].get("bytes", 0), "edge": False}
            for row in rows if row["kind"] == "observation" and row["status"] == "succeeded"],
        "commands": [row["payload"]["command_record"] for row in rows if row["kind"] == "command"],
        "inputs": list(dict.fromkeys(path for row in rows for path in row["payload"].get("inputs_snapshot", {}))),
        "outputs": outputs, "resource_reads": resources,
        "additional_assets": sorted(all_assets - used_assets),
        "collection": {"source": "execution-session-v1", "operation_ids": [row["id"] for row in rows]},
        "companion_skills": {"used": sorted(set(action.companion_skills) & consulted),
            "skipped": [{"skill": name, "reason": "本轮未选择；自动记录，不等同不适用判断"}
                        for name in action.companion_skills if name not in consulted]},
        "assets": {"used": sorted(used_assets), "skipped": [
            {"name": a["name"], "reason": "本轮未选择；自动记录，不等同不适用判断"}
            for a in action.assets if a["name"] not in used_assets]},
        "additional_skills": [{"skill": name, "reason": "执行者按任务主动加载",
            "contribution": "已提供上下文，实质贡献待成果审查", "output": outputs[0] if outputs else ""} for name in extra]}
    dependencies = {}
    for row in rows:
        for name, version in row["payload"].get("dependencies", {}).items():
            if name in dependencies and dependencies[name] != version:
                raise ValueError(f"操作之间依赖版本不一致: {name}")
            dependencies[name] = version
    evidence["producer_manifests"] = [row["payload"]["producer_manifest"] for row in rows if row["payload"].get("producer_manifest")]
    if len(evidence["producer_manifests"]) == 1:
        path = action.workspace / evidence["producer_manifests"][0]
        producer = json.loads(path.read_text(encoding="utf-8"))
        producer_outputs = {entry["path"].rstrip("/") for entry in producer.get("outputFiles", [])}
        if {name.rstrip("/") for name in outputs} <= producer_outputs:
            evidence["execution_manifest"] = evidence["producer_manifests"][0]
    evidence["dependencies"] = dependencies
    evidence["backend"] = "recorded-execution"
    evidence["execution_config"] = {row["payload"].get("node", row["id"]): row["payload"].get("execution_config", {})
                                    for row in rows if row["kind"] == "command"}
    reviews = [row["payload"] for row in rows if row["kind"] == "review"]
    if reviews:
        evidence["review_receipts"] = reviews
        evidence["subagent_session"] = reviews[-1]["host_call_id"]
    elif subagent_session:
        evidence["subagent_session"] = subagent_session
    return evidence


def _validate_collected_operations(workspace, action, evidence, store, fingerprint_session):
    """机器采集证据必须逐条绑定当前attempt的持久事实，不信任Agent自报resource/hash。"""
    collection = evidence.get("collection")
    if store is None or not isinstance(collection, dict) or collection.get("source") != "execution-session-v1":
        raise ValueError("execution collection requires the workflow store")
    rows = store.current_operations(action.step_id, action.attempt_id)
    if not rows or any(r["status"] not in {"succeeded", "reused"} for r in rows):
        raise ValueError("execution collection contains missing, failed or interrupted operations")
    ids = collection.get("operation_ids")
    if not isinstance(ids, list) or set(ids) != {r["id"] for r in rows} or len(ids) != len(rows):
        raise ValueError("execution collection operation set mismatch")
    workflow_row = store._connection.execute("SELECT metadata FROM workflows WHERE id=?", (action.workflow_id,)).fetchone()
    workflow = {"metadata": json.loads(workflow_row[0])}
    rules_root = action.skill_path.parents[2] / "engine/modex-core"
    step = store.get_step(action.step_id)
    workflow_params = workflow["metadata"].get("params", {})
    tier = _workflow_contract_tier(workflow["metadata"])
    declared_tier = evidence.get("contract_tier") or None
    if declared_tier is not None and declared_tier != tier:
        raise ValueError("execution evidence contract_tier does not match the workflow")
    # 当前档执行语义合同：只绑 skill/params，不绑纯质量规则（metadata 质量字段/
    # modex-core 规则文件变化只在验收时实时重验，不要求重跑命令）。
    current_contract = execution_contract(action, step.metadata, workflow_params, rules_root, tier=tier)
    # 三集合对账：当前档合同 + delivery scope 2（explore 工作流里历史/跨档
    # 操作仍须可对账，不能只算 scope 3）+ scope 1 历史全量合同。不能无条件
    # 放行任意 contract；只有这三个可复算值之一才通过。
    delivery_contract = execution_contract(action, step.metadata, workflow_params, rules_root, tier="delivery")
    legacy_contract = legacy_execution_contract(action, step.metadata, workflow_params, rules_root)
    accepted_contracts = {current_contract, delivery_contract, legacy_contract}
    if any(r["kind"] == "command" and r["payload"].get("contract") not in accepted_contracts
           for r in rows):
        raise ValueError("execution collection contract changed")
    if "workspace_observations" in evidence:
        # 只与 current_operations 折叠后的 observation 行对账：路径/哈希/
        # operation_id。不比对当前磁盘字节（观察只证明"当时读过"），也不并入
        # evidence["inputs"]（依赖边只由 write/edit 的 declared_inputs 决定）。
        observations = evidence["workspace_observations"]
        if not isinstance(observations, list):
            raise ValueError("execution evidence workspace_observations must be a list")
        expected_observations = sorted(
            (str(r["payload"].get("path", "")), str(r["payload"].get("sha256", "")), str(r["id"]))
            for r in rows if r["kind"] == "observation" and r["status"] == "succeeded")
        actual_observations = []
        for observation in observations:
            if not isinstance(observation, dict):
                raise ValueError("execution evidence workspace_observations entries must be objects")
            actual_observations.append((
                str(observation.get("path", "")),
                str(observation.get("sha256", "")),
                str(observation.get("operation_id", ""))))
        if sorted(actual_observations) != expected_observations:
            raise ValueError("execution collection workspace observations mismatch")
    commands = [r["payload"]["command_record"] for r in rows if r["kind"] == "command"]
    reads = [r["payload"] for r in rows if r["kind"] == "resource"]
    reviews = [r["payload"] for r in rows if r["kind"] == "review"]
    if evidence.get("review_receipts", []) != reviews:
        raise ValueError("review receipts do not match persisted response records")
    if action.requires_subagent and not reviews:
        raise ValueError("独立评审步骤必须有版本绑定的实际返回记录，单个session字符串不能代替评审")
    if evidence.get("commands") != commands or evidence.get("resource_reads") != reads:
        raise ValueError("execution collection facts do not match persisted records")
    machine_only = (action.skill_name == "comp-final-audit"
                    and store.get_step(action.step_id).metadata.get("machine_audit_only") is True)
    if not machine_only and not any(r["kind"] in {"command", "write", "review"} for r in rows):
        raise ValueError("resource consultation alone is not task execution")
    from .artifact_manifest import FingerprintSession
    fingerprints = fingerprint_session or FingerprintSession(Path(workspace))
    current_versions = {}
    produced_paths = set()
    for row in rows:
        payload = row["payload"]
        if row["kind"] == "review":
            for reviewed_path, reviewed_hash in payload.get("outputs_snapshot", {}).items():
                if fingerprints.fingerprint(reviewed_path).sha256 != reviewed_hash:
                    raise ValueError("独立评审原文被后续操作覆盖；必须接收新的独立评审，不能改写裁定")
        # 每个命令的输入仍须匹配；上游重算后，不能用新的上游摘要掩盖旧下游。
        mutations = set(payload.get("mutates", []))
        if not mutations <= (set(payload.get("inputs_snapshot", {})) & set(payload.get("outputs_snapshot", {}))):
            raise ValueError("collected mutation must bind both pre-execution input and post-execution output")
        for name, expected in {**payload.get("lineage_inputs", {}), **payload.get("inputs_snapshot", {})}.items():
            # 明确原地修订保存before→after，不要求修订后的文件仍等于旧输入。
            # 其他命令（编译/核查等）仍按当前输入对账，旧下游结果不会被新修订掩盖。
            if name not in mutations and fingerprints.fingerprint(name).sha256 != expected:
                raise ValueError(f"execution dependency changed; rerun affected node {row['node_key']}: {name}")
        current_versions.update(payload.get("outputs_snapshot", {}))
        produced_paths.update(payload.get("outputs_snapshot", {}))
    for name, expected in current_versions.items():
        if fingerprints.fingerprint(name).sha256 != expected:
            raise ValueError(f"execution collection bytes changed: {name}")
    consulted = {read["name"] for read in reads if read.get("kind") == "skill"}
    if not {action.skill_name, *action.skill_binding.get("mandatory", [])} <= consulted:
        raise ValueError("collected execution must receive current main/mandatory skill content")
    for read in reads:
        path = Path(read["path"])
        suite = action.skill_path.parents[2]
        if read.get("kind") == "skill":
            expected_path = (suite / "skills" / read.get("name", "") / "SKILL.md").resolve()
            if path.resolve() != expected_path or not expected_path.is_relative_to((suite / "skills").resolve()):
                raise ValueError("collected skill resource path mismatch")
        elif not path.resolve().is_relative_to(suite.parent.resolve()):
            raise ValueError("collected asset resource escapes repository")
        if not path.is_file() or _file_sha256(path) != read["sha256"]:
            raise ValueError(f"consulted resource changed: {read['name']}")
    for declared in evidence.get("outputs", []):
        if action.skill_name == "comp-final-audit" and declared == "AUDIT_REPORT.json":
            continue  # 真正报告由final-audit生成且随后实时完整验收。
        canonical = _relative_path(Path(workspace), declared)
        if not any(canonical == p or canonical.startswith(p.rstrip("/") + "/") for p in produced_paths):
            raise ValueError(f"output has no collected producer: {declared}")
    expected_inputs = list(dict.fromkeys(p for r in rows for p in r["payload"].get("inputs_snapshot", {})))
    if evidence.get("inputs") != expected_inputs:
        raise ValueError("execution collection inputs mismatch")
    fingerprints.assert_unchanged()


def write_execution_evidence(
    workspace: Path, action: StepAction, evidence: dict[str, Any], manifest: dict[str, Any],
    *, submission_id: str = "",
) -> str:
    """Write validated evidence and its declared-artifact manifest under the workspace."""
    root = Path(workspace).resolve()
    directory = root / ".engine" / "evidence"
    if not directory.resolve().is_relative_to(root):
        raise ValueError("evidence directory escapes workspace")
    directory.mkdir(parents=True, exist_ok=True)
    suffix = f"_{action.attempt_id}" if action.attempt_id else ""
    if submission_id:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", submission_id):
            raise ValueError("invalid submission_id")
        suffix += "_" + submission_id
    path = directory / f"{action.step_id}{suffix}.json"
    if not path.resolve().is_relative_to(root):
        raise ValueError("evidence directory escapes workspace")
    payload = {"schema_version": SCHEMA_VERSION, "action": {
        "workflow_id": action.workflow_id,
        "step_id": action.step_id,
        "skill_name": action.skill_name,
        "attempt_id": action.attempt_id,
        "expected_revision": action.expected_revision,
        # P4：把本步的技能绑定随证据落盘，使审计层（audit_store.verify_skill_bindings）
        # 无需回查模板/SQLite 即可对账"声明绑定 vs L1 实际操作"。
        "skill_binding": dict(getattr(action, "skill_binding", None) or {}),
        "companion_skills": list(action.companion_skills),
        "assets": list(action.assets),
    }, "evidence": evidence, "manifest": manifest,
       "resource_usage": {
           "offered": {"skills": list(action.companion_skills), "assets": list(action.assets)},
           "declared": {key: evidence.get(key, {}) for key in ("companion_skills", "assets", "additional_skills")},
           "verification_level": "declaration_and_trace; semantic contribution requires review",
       }}
    atomic_write_json(path, payload)
    return path.relative_to(root).as_posix()
