#!/usr/bin/env python3
"""PaperSpine post-delivery Open Release Beta orchestration.

The module is intentionally split into local preparation and host execution.
It can recommend platforms, verify artifacts/permissions/compliance, prepare a
hash-bound action plan, validate the user's final confirmation, and record host
receipts.  It never stores credentials and never performs an external publish
by itself; a host Agent may act only from an authorized release ticket.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

INTERFACE_VERSION = "0.1-beta"
PLAN_CONTRACT = "paperspine.open-release.plan"
RESULT_CONTRACT = "paperspine.open-release.result"
CATALOG_CONTRACT = "paperspine.open-release.platform-catalog"
PREFLIGHT_CONTRACT = "paperspine.open-release.preflight"
MANIFEST_CONTRACT = "paperspine.open-release.manifest"
CONFIRMATION_CONTRACT = "paperspine.open-release.confirmation"
TICKET_CONTRACT = "paperspine.open-release.agent-ticket"
RECEIPTS_CONTRACT = "paperspine.open-release.platform-receipts"
FINAL_RECEIPT_CONTRACT = "paperspine.open-release.receipt"

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SECRET_KEY_NAMES = {
    "token",
    "access_token",
    "api_token",
    "password",
    "secret",
    "client_secret",
    "cookie",
    "session_cookie",
    "credential_value",
}
SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
SENSITIVE_STATES = {
    "deidentified_human",
    "identifiable_human",
    "controlled_human",
    "confidential",
    "restricted",
    "unknown",
}
PUBLIC_BLOCKING_SENSITIVITY = {"identifiable_human", "confidential", "restricted"}
CONTROLLED_PLATFORMS = {"dbgap"}
GUIDED_AUTOMATION_PREFIXES = ("guided_",)
SUCCESS_RECEIPT_STATUSES = {
    "PUBLISHED",
    "SUBMITTED_FOR_REVIEW",
    "DRAFT_CREATED",
    "PREPARED_FOR_INSTITUTIONAL_REVIEW",
}
RECEIPT_STATUSES = SUCCESS_RECEIPT_STATUSES | {"WAITING_USER", "FAILED", "SKIPPED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_inside(root: Path, raw: str, *, label: str) -> Path:
    candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if not is_relative_to(candidate, root.resolve()):
        raise ValueError(f"{label} escapes project_root: {raw}")
    return candidate


def relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def catalog_path() -> Path:
    script = Path(__file__).resolve()
    candidates = [
        script.parents[1] / "skill" / "references" / "open-release-platforms.json",
        script.parent.parent / "references" / "open-release-platforms.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("open-release-platforms.json is missing from the source or installed Skill")


def load_catalog() -> dict[str, Any]:
    value = read_json(catalog_path())
    if value.get("contract") != CATALOG_CONTRACT:
        raise ValueError("platform catalog contract is invalid")
    return value


def platform_map() -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in load_catalog().get("platforms", [])}


def hash_path(path: Path) -> tuple[str, int, int]:
    """Return deterministic SHA-256, byte count, and file count for a file/tree."""
    if path.is_symlink():
        raise ValueError(f"symlink artifacts are not allowed: {path.name}")
    if path.is_file():
        return sha256_file(path), path.stat().st_size, 1
    if not path.is_dir():
        raise ValueError(f"artifact path is not a file or directory: {path}")
    digest = hashlib.sha256()
    total = 0
    count = 0
    for child in sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: item.relative_to(path).as_posix()):
        if child.is_symlink():
            raise ValueError(f"symlink artifacts are not allowed: {child.relative_to(path).as_posix()}")
        rel = child.relative_to(path).as_posix()
        file_digest = sha256_file(child)
        size = child.stat().st_size
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\n")
        total += size
        count += 1
    return digest.hexdigest(), total, count


def iter_artifact_files(path: Path, *, limit: int = 5000) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    seen = 0
    for child in sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        if seen >= limit:
            return
        seen += 1
        yield child


def secret_key_paths(value: object, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            child_path = f"{prefix}.{key}"
            if normalized in SECRET_KEY_NAMES or normalized.endswith("_password") or normalized.endswith("_secret"):
                findings.append(child_path)
            findings.extend(secret_key_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(secret_key_paths(child, f"{prefix}[{index}]"))
    return findings


def secret_value_paths(value: object, prefix: str = "$") -> list[str]:
    """Locate obvious secret *values* without returning or logging the value."""
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            findings.extend(secret_value_paths(child, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(secret_value_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
        findings.append(prefix)
    return findings


def obvious_secret_files(path: Path, project_root: Path) -> list[str]:
    filename_patterns = (
        re.compile(r"^\.env(?:\..+)?$", re.I),
        re.compile(r"^(?:id_rsa|id_dsa|id_ecdsa|id_ed25519)$", re.I),
        re.compile(r"(?:credential|service[-_]?account).+\.json$", re.I),
        re.compile(r"\.(?:pem|p12|pfx|key)$", re.I),
    )
    text_suffixes = {".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".py", ".js", ".ts", ".sh", ".ps1"}
    findings: list[str] = []
    for child in iter_artifact_files(path):
        rel = relative_posix(child, project_root)
        if any(pattern.search(child.name) for pattern in filename_patterns) and child.name.lower() != ".env.example":
            findings.append(rel)
            continue
        if child.suffix.lower() not in text_suffixes or child.stat().st_size > 1024 * 1024:
            continue
        try:
            text = child.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern.search(text) for pattern in SECRET_VALUE_PATTERNS):
            findings.append(rel)
    return sorted(set(findings))


def get_nonempty(mapping: dict[str, Any], key: str) -> bool:
    value = mapping.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, dict, str)):
        return bool(value)
    return value is not None


def gap(
    *,
    code: str,
    platform: str | None,
    category: str,
    message_zh: str,
    recovery_zh: str,
    recovery_url: str | None = None,
    owner: str = "user",
) -> dict[str, Any]:
    return {
        "code": code,
        "platform": platform,
        "category": category,
        "message_zh": message_zh,
        "blocks_full_one_click": True,
        "can_retry": True,
        "recovery": {
            "owner": owner,
            "action_zh": recovery_zh,
            "url": recovery_url,
        },
    }


def capability_feedback(platform: dict[str, Any], capability: str) -> tuple[str, str, str | None]:
    label = str(platform["label"])
    urls = platform.get("official_urls") or {}
    url = urls.get("authentication") or urls.get("submit") or urls.get("requirements") or urls.get("home")
    if capability == "computer_control":
        return (
            f"缺少 Agent 使用用户电脑/浏览器的授权，无法操作 {label}。",
            "在主流程中开启电脑或浏览器控制权限，然后重新运行预检。",
            None,
        )
    if "browser_session" in capability:
        return (
            f"未验证 {label} 的已登录浏览器会话。",
            f"请在用户电脑上登录 {label}，再让 Agent 重新检查会话。",
            url,
        )
    if "token" in capability or "api" in capability:
        return (
            f"缺少 {label} 所需的 API 凭据能力：{capability}。",
            "在平台创建最小权限凭据并保存到主机凭据存储；不要把 token 写进 JSON 或聊天。",
            url,
        )
    if "cli" in capability and "available" in capability:
        return (
            f"用户电脑上未验证 {label} 所需的命令行工具：{capability}。",
            "安装官方命令行工具后重新运行只读探测。",
            url,
        )
    if "authenticated" in capability or "account" in capability:
        return (
            f"未验证 {label} 的账号登录能力：{capability}。",
            f"请登录 {label} 并允许 Agent 重新做只读权限检查。",
            url,
        )
    if any(word in capability for word in ("eligible", "endorse", "authority", "permission", "official", "responsible_party")):
        return (
            f"缺少 {label} 的资格或角色权限：{capability}。",
            "由作者、项目负责人或机构管理员在官方页面确认资格/角色后，保存不含秘密值的权限证据并重试。",
            url,
        )
    return (
        f"缺少 {label} 所需能力：{capability}。",
        "按平台官方要求补齐该能力，并重新运行预检。",
        url,
    )


def recommendation_catalog(domain: str | None, artifact_roles: list[str], sensitivity: str | None) -> dict[str, Any]:
    catalog = load_catalog()
    roles = {item.strip() for item in artifact_roles if item.strip()}
    domain_value = (domain or "all").strip()
    recommendations: list[dict[str, Any]] = []
    for platform in catalog.get("platforms", []):
        if not platform.get("selectable"):
            continue
        domains = set(platform.get("domains") or [])
        supported_roles = set(platform.get("artifact_roles") or [])
        domain_match = domain_value in domains
        generalist = "all" in domains
        role_match = roles & supported_roles
        if roles and not role_match:
            continue
        if not roles and not (domain_match or generalist):
            continue
        if sensitivity in PUBLIC_BLOCKING_SENSITIVITY and platform["id"] not in CONTROLLED_PLATFORMS:
            continue
        score = (18 if domain_match else 6 if generalist else 0) + (12 * len(role_match))
        if sensitivity == "controlled_human" and platform["id"] in {"dbgap", "physionet"}:
            score += 25
        if score <= 0:
            continue
        recommendations.append(
            {
                "id": platform["id"],
                "label": platform["label"],
                "score": score,
                "matched_roles": sorted(role_match),
                "recommended_mode": platform["recommended_mode"],
                "automation_level": platform["automation_level"],
                "requires_guided_handoff": str(platform["automation_level"]).startswith(GUIDED_AUTOMATION_PREFIXES),
                "recommendation_zh": platform["recommendation_zh"],
                "boundary_zh": platform["boundary_zh"],
            }
        )
    recommendations.sort(key=lambda item: (-int(item["score"]), str(item["label"])))
    discovery = [
        {"id": item["id"], "label": item["label"], "url": item["official_urls"]["home"]}
        for item in catalog.get("platforms", [])
        if not item.get("selectable")
    ]
    return {
        "contract": CATALOG_CONTRACT,
        "catalog_version": catalog["catalog_version"],
        "checked_at": catalog["checked_at"],
        "filters": {"domain": domain_value, "artifact_roles": sorted(roles), "sensitivity": sensitivity or "none"},
        "recommendations": recommendations,
        "platforms": catalog["platforms"],
        "discovery_fallbacks": discovery,
        "rule_zh": "优先使用匹配数据类型的学科仓库；无合适学科仓库时再使用通用仓库。医学和人类数据必须先判断公开、限制或受控访问路线。",
    }


def plan_context(plan_path: Path, *, invocation_root: Path | None = None) -> tuple[dict[str, Any], Path, list[dict[str, Any]], list[str]]:
    plan_path = plan_path.resolve()
    plan = read_json(plan_path)
    findings: list[dict[str, Any]] = []
    warnings: list[str] = []
    if plan.get("contract") != PLAN_CONTRACT:
        findings.append(gap(code="PLAN_CONTRACT_INVALID", platform=None, category="contract", message_zh=f"计划 contract 必须是 {PLAN_CONTRACT}。", recovery_zh="由主流程按 Open Release 计划 Schema 重新生成。", owner="main_flow"))
    if str(plan.get("schema_version")) != "1.0":
        findings.append(gap(code="PLAN_SCHEMA_UNSUPPORTED", platform=None, category="contract", message_zh="仅支持 open-release plan schema_version=1.0。", recovery_zh="迁移计划到 1.0 后重试。", owner="main_flow"))
    for key_path in secret_key_paths(plan):
        findings.append(gap(code="SECRET_IN_PLAN", platform=None, category="security", message_zh=f"计划中出现禁止保存的秘密字段：{key_path}。", recovery_zh="删除秘密值，只保留 capability/status/source 等不含秘密的权限证据。", owner="main_flow"))
    for value_path in secret_value_paths(plan):
        findings.append(gap(code="SECRET_VALUE_IN_PLAN", platform=None, category="security", message_zh=f"计划中出现疑似秘密值：{value_path}（内容已隐藏）。", recovery_zh="删除该值、必要时轮换凭据，只保留不含秘密的权限状态。", owner="main_flow"))
    raw_root = str(plan.get("project_root") or ".")
    project_root = (plan_path.parent / raw_root).resolve()
    if invocation_root is not None and not is_relative_to(project_root, invocation_root.resolve()):
        findings.append(gap(code="PROJECT_ROOT_ESCAPE", platform=None, category="security", message_zh="计划 project_root 超出调用方授权范围。", recovery_zh="把计划与产物放回 invocation project_root 内。", owner="main_flow"))
    if not is_relative_to(plan_path, project_root):
        findings.append(gap(code="PLAN_OUTSIDE_PROJECT", platform=None, category="security", message_zh="计划文件不在其声明的 project_root 内。", recovery_zh="修正 project_root 或移动计划文件。", owner="main_flow"))
    if not str(plan.get("release_id") or "").strip():
        findings.append(gap(code="RELEASE_ID_MISSING", platform=None, category="metadata", message_zh="缺少 release_id。", recovery_zh="生成稳定且唯一的 release_id。", owner="main_flow"))
    if not isinstance(plan.get("selected_platforms"), list) or not plan.get("selected_platforms"):
        findings.append(gap(code="PLATFORM_SELECTION_MISSING", platform=None, category="selection", message_zh="尚未勾选任何发布平台。", recovery_zh="让用户至少勾选一个平台。"))
    if not isinstance(plan.get("artifacts"), list) or not plan.get("artifacts"):
        findings.append(gap(code="ARTIFACTS_MISSING", platform=None, category="artifact", message_zh="发布计划没有任何产物。", recovery_zh="从交稿材料包中选择要发布的文件、目录或数据。", owner="main_flow"))
    if not project_root.exists():
        findings.append(gap(code="PROJECT_ROOT_MISSING", platform=None, category="artifact", message_zh="计划声明的 project_root 不存在。", recovery_zh="修正路径并重新生成计划。", owner="main_flow"))
    return plan, project_root, findings, warnings


def access_lookup(plan: dict[str, Any]) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for item in plan.get("access_evidence") or []:
        if not isinstance(item, dict):
            continue
        platform = str(item.get("platform") or "*")
        capability = str(item.get("capability") or "")
        if capability:
            result[(platform, capability)] = str(item.get("status") or "unknown").lower()
    return result


def access_available(lookup: dict[tuple[str, str], str], platform: str, capability: str) -> bool:
    return lookup.get((platform, capability)) == "available" or lookup.get(("*", capability)) == "available"


def artifact_records(plan: dict[str, Any], project_root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    gaps: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, artifact in enumerate(plan.get("artifacts") or []):
        if not isinstance(artifact, dict):
            gaps.append(gap(code="ARTIFACT_INVALID", platform=None, category="artifact", message_zh=f"artifacts[{index}] 必须是对象。", recovery_zh="修正计划结构。", owner="main_flow"))
            continue
        artifact_id = str(artifact.get("id") or "").strip()
        if not artifact_id or artifact_id in records:
            gaps.append(gap(code="ARTIFACT_ID_INVALID", platform=None, category="artifact", message_zh=f"artifacts[{index}] 的 id 缺失或重复。", recovery_zh="为每个产物设置唯一 id。", owner="main_flow"))
            continue
        raw_path = str(artifact.get("path") or "")
        try:
            path = resolve_inside(project_root, raw_path, label=f"artifact {artifact_id}")
        except ValueError as exc:
            gaps.append(gap(code="ARTIFACT_PATH_ESCAPE", platform=None, category="security", message_zh=str(exc), recovery_zh="只选择 project_root 内的产物。", owner="main_flow"))
            continue
        if not path.exists():
            gaps.append(gap(code="ARTIFACT_NOT_FOUND", platform=None, category="artifact", message_zh=f"找不到产物 {artifact_id}: {raw_path}。", recovery_zh="恢复文件或修正路径。", owner="main_flow"))
            continue
        try:
            digest, size, file_count = hash_path(path)
        except ValueError as exc:
            gaps.append(gap(code="ARTIFACT_UNSAFE_PATH", platform=None, category="security", message_zh=str(exc), recovery_zh="移除符号链接并使用确定的普通文件/目录。", owner="main_flow"))
            continue
        expected = str(artifact.get("sha256") or "")
        if expected and expected != digest:
            gaps.append(gap(code="ARTIFACT_HASH_MISMATCH", platform=None, category="artifact", message_zh=f"产物 {artifact_id} 的 SHA-256 与计划不一致。", recovery_zh="确认文件是否变化，然后刷新计划哈希。", owner="main_flow"))
        if not expected:
            warnings.append(f"产物 {artifact_id} 未预先绑定 SHA-256；prepare 将使用当前计算值 {digest}。")
        sensitivity = str(artifact.get("sensitivity") or "unknown")
        if sensitivity not in SENSITIVE_STATES | {"none"}:
            gaps.append(gap(code="ARTIFACT_SENSITIVITY_INVALID", platform=None, category="compliance", message_zh=f"产物 {artifact_id} 的 sensitivity 值无效。", recovery_zh="使用 none/deidentified_human/identifiable_human/controlled_human/confidential/restricted/unknown。", owner="main_flow"))
        secret_paths = obvious_secret_files(path, project_root)
        for secret_path in secret_paths:
            gaps.append(gap(code="POSSIBLE_SECRET_IN_ARTIFACT", platform=None, category="security", message_zh=f"产物中发现疑似凭据文件或秘密模式：{secret_path}（内容已隐藏）。", recovery_zh="移除秘密、轮换可能泄露的凭据，并重新生成产物。", owner="user"))
        records[artifact_id] = {
            "id": artifact_id,
            "path": relative_posix(path, project_root),
            "roles": sorted({str(role) for role in artifact.get("roles") or [] if str(role)}),
            "sensitivity": sensitivity,
            "sha256": digest,
            "size_bytes": size,
            "file_count": file_count,
        }
    return records, gaps, warnings


def platform_status_from_gaps(platform_gaps: list[dict[str, Any]], guided: bool) -> str:
    if not platform_gaps:
        return "READY_FOR_GUIDED_HANDOFF" if guided else "READY_FOR_FINAL_CONFIRMATION"
    categories = {str(item["category"]) for item in platform_gaps}
    if categories & {"security", "compliance"}:
        return "NEEDS_COMPLIANCE"
    if "eligibility" in categories:
        return "NEEDS_ELIGIBILITY"
    if "permission" in categories:
        return "NEEDS_LOGIN_OR_PERMISSION"
    if "metadata" in categories:
        return "NEEDS_METADATA"
    if "artifact" in categories:
        return "NEEDS_ARTIFACT"
    return "BLOCKED"


def preflight(plan_path: Path, *, invocation_root: Path | None = None) -> dict[str, Any]:
    plan, project_root, global_gaps, warnings = plan_context(plan_path, invocation_root=invocation_root)
    platforms = platform_map()
    artifacts, artifact_gaps, artifact_warnings = artifact_records(plan, project_root) if project_root.exists() else ({}, [], [])
    global_gaps.extend(artifact_gaps)
    warnings.extend(artifact_warnings)
    permissions = plan.get("permissions") if isinstance(plan.get("permissions"), dict) else {}
    licenses = plan.get("licenses") if isinstance(plan.get("licenses"), dict) else {}
    global_metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    access = access_lookup(plan)
    seen_platforms: set[str] = set()
    platform_results: list[dict[str, Any]] = []
    all_platform_gaps: list[dict[str, Any]] = []

    for selection in plan.get("selected_platforms") or []:
        if not isinstance(selection, dict) or selection.get("enabled") is False:
            continue
        platform_id = str(selection.get("id") or "")
        platform_gaps: list[dict[str, Any]] = []
        platform = platforms.get(platform_id)
        if platform_id in seen_platforms:
            platform_gaps.append(gap(code="PLATFORM_DUPLICATE", platform=platform_id, category="selection", message_zh=f"平台 {platform_id} 被重复勾选。", recovery_zh="每个平台只保留一个选择项。", owner="main_flow"))
        seen_platforms.add(platform_id)
        if platform is None or not platform.get("selectable"):
            platform_gaps.append(gap(code="PLATFORM_UNKNOWN", platform=platform_id or None, category="selection", message_zh=f"未知或不可选择的平台：{platform_id or '<empty>'}。", recovery_zh="从当前平台目录重新选择。", owner="main_flow"))
            platform_results.append({"id": platform_id, "label": platform_id, "status": "BLOCKED", "gaps": platform_gaps})
            all_platform_gaps.extend(platform_gaps)
            continue
        mode = str(selection.get("mode") or platform["recommended_mode"])
        if mode not in set(platform.get("allowed_modes") or []):
            platform_gaps.append(gap(code="PLATFORM_MODE_INVALID", platform=platform_id, category="selection", message_zh=f"{platform['label']} 不支持执行模式 {mode}。", recovery_zh=f"改用允许模式：{', '.join(platform['allowed_modes'])}。", owner="main_flow"))
        metadata = dict(global_metadata)
        if isinstance(selection.get("metadata"), dict):
            metadata.update(selection["metadata"])
        for field in platform.get("required_metadata") or []:
            if not get_nonempty(metadata, str(field)):
                platform_gaps.append(gap(code=f"METADATA_{platform_id}_{str(field).upper()}_MISSING", platform=platform_id, category="metadata", message_zh=f"{platform['label']} 缺少必填元数据：{field}。", recovery_zh="从论文元数据或用户确认中补齐该字段。", recovery_url=platform["official_urls"].get("requirements"), owner="main_flow"))
        for declaration in platform.get("required_declarations") or []:
            if permissions.get(str(declaration)) is not True:
                platform_gaps.append(gap(code=f"DECLARATION_{platform_id}_{str(declaration).upper()}_MISSING", platform=platform_id, category="compliance", message_zh=f"{platform['label']} 缺少作者/合规确认：{declaration}。", recovery_zh="由有权作者、PI、Responsible Party 或机构明确确认；不得从论文正文推断。", recovery_url=platform["official_urls"].get("requirements")))
        for capability in (platform.get("mode_requirements") or {}).get(mode, []):
            capability = str(capability)
            if not access_available(access, platform_id, capability):
                message, recovery, url = capability_feedback(platform, capability)
                category = "eligibility" if any(word in capability for word in ("eligible", "authority", "responsible_party", "official", "endorse")) else "permission"
                platform_gaps.append(gap(code=f"ACCESS_{platform_id}_{capability.upper()}_MISSING", platform=platform_id, category=category, message_zh=message, recovery_zh=recovery, recovery_url=url))
        selected_artifact_ids = [str(item) for item in selection.get("artifact_ids") or []]
        if not selected_artifact_ids:
            platform_gaps.append(gap(code=f"ARTIFACT_{platform_id}_SELECTION_MISSING", platform=platform_id, category="artifact", message_zh=f"{platform['label']} 没有绑定要上传的产物。", recovery_zh="勾选至少一个与平台类型相符的产物。", owner="main_flow"))
        bound_artifacts = [artifacts[item] for item in selected_artifact_ids if item in artifacts]
        missing_ids = [item for item in selected_artifact_ids if item not in artifacts]
        if missing_ids:
            platform_gaps.append(gap(code=f"ARTIFACT_{platform_id}_UNKNOWN", platform=platform_id, category="artifact", message_zh=f"{platform['label']} 引用了不存在或无效的产物：{', '.join(missing_ids)}。", recovery_zh="修正 artifact_ids 后重试。", owner="main_flow"))
        supported_roles = set(platform.get("artifact_roles") or [])
        if bound_artifacts and not any(set(item["roles"]) & supported_roles for item in bound_artifacts):
            platform_gaps.append(gap(code=f"ARTIFACT_{platform_id}_ROLE_MISMATCH", platform=platform_id, category="artifact", message_zh=f"绑定产物的角色不符合 {platform['label']} 接收类型。", recovery_zh=f"该平台接收：{', '.join(sorted(supported_roles))}。", recovery_url=platform["official_urls"].get("requirements"), owner="main_flow"))
        sensitivities = {item["sensitivity"] for item in bound_artifacts}
        if "unknown" in sensitivities:
            platform_gaps.append(gap(code=f"COMPLIANCE_{platform_id}_SENSITIVITY_UNKNOWN", platform=platform_id, category="compliance", message_zh=f"{platform['label']} 的某个产物尚未判定敏感性。", recovery_zh="完成 PHI/PII、合同、出口管制和第三方权利检查并设置 sensitivity。"))
        if sensitivities & PUBLIC_BLOCKING_SENSITIVITY and platform_id not in CONTROLLED_PLATFORMS:
            platform_gaps.append(gap(code=f"COMPLIANCE_{platform_id}_PUBLIC_SENSITIVE_BLOCKED", platform=platform_id, category="compliance", message_zh=f"{platform['label']} 不能接收当前标记为可识别、机密或受限的公开产物。", recovery_zh="不要上传；先去标识化并获得授权，或改选符合条件的受控仓库。"))
        if sensitivities & {"deidentified_human", "controlled_human", "identifiable_human"}:
            if platform_id in CONTROLLED_PLATFORMS:
                required_human = ("consent_status_established", "irb_or_ethics_route_confirmed", "data_use_agreement_allows_deposit")
            else:
                required_human = ("deidentified", "ethics_approval_allows_release", "consent_allows_public_release")
            for declaration in required_human:
                if permissions.get(declaration) is not True:
                    platform_gaps.append(gap(code=f"COMPLIANCE_{platform_id}_{declaration.upper()}_MISSING", platform=platform_id, category="compliance", message_zh=f"人类受试者产物缺少确认：{declaration}。", recovery_zh="由伦理/数据治理责任人确认后再重试；Agent 不得替代该判断。"))
        constraints = set(platform.get("license_constraints") or [])
        configured_licenses = {str(value) for value in licenses.values() if isinstance(value, str)}
        if constraints and not constraints.issubset(configured_licenses):
            platform_gaps.append(gap(code=f"LICENSE_{platform_id}_CONSTRAINT_MISSING", platform=platform_id, category="compliance", message_zh=f"{platform['label']} 要求许可：{', '.join(sorted(constraints))}。", recovery_zh="让权利人确认兼容许可；不得由 Agent 自动选择。", recovery_url=platform["official_urls"].get("requirements")))
        guided = str(platform["automation_level"]).startswith(GUIDED_AUTOMATION_PREFIXES)
        status = platform_status_from_gaps(platform_gaps, guided)
        platform_results.append(
            {
                "id": platform_id,
                "label": platform["label"],
                "mode": mode,
                "automation_level": platform["automation_level"],
                "maximum_agent_action": platform["maximum_agent_action"],
                "status": status,
                "artifact_ids": selected_artifact_ids,
                "gaps": platform_gaps,
                "official_urls": platform["official_urls"],
                "boundary_zh": platform["boundary_zh"],
            }
        )
        all_platform_gaps.extend(platform_gaps)

    all_gaps = global_gaps + all_platform_gaps
    ready = [item for item in platform_results if not item["gaps"]]
    guided_ready = [item for item in ready if str(item["automation_level"]).startswith(GUIDED_AUTOMATION_PREFIXES)]
    one_click_ready = [item for item in ready if item not in guided_ready]
    allow_partial = bool((plan.get("release_policy") or {}).get("allow_partial_release", False)) if isinstance(plan.get("release_policy"), dict) else False
    selected_count = len(platform_results)
    if not all_gaps and selected_count and not guided_ready:
        status = "FULL_BETA_READY"
    elif not all_gaps and selected_count:
        status = "ASSISTED_RELEASE_READY"
    elif ready:
        status = "PARTIAL_RELEASE_READY"
    else:
        status = "BLOCKED"
    can_prepare = bool(ready) and (not all_gaps or allow_partial)
    full_available = status == "FULL_BETA_READY"
    missing_permissions = [item for item in all_gaps if item["category"] in {"permission", "eligibility"}]
    if full_available:
        headline = "完整一键开源 Beta 已通过预检"
        summary = "所有已选平台的产物、元数据、权限和合规声明均已就绪；仍需用户做最后一次发布确认。"
    elif status == "ASSISTED_RELEASE_READY":
        headline = "可进入发布确认，但包含平台人工/机构步骤"
        summary = "已选平台没有已知缺口，但部分医学或学科仓库只允许引导式提交，不能宣称完整全自动发布。"
    elif status == "PARTIAL_RELEASE_READY":
        headline = "完整一键开源暂不可用，可按授权发布已就绪平台"
        summary = "部分平台仍缺少登录、角色、资格、元数据或合规确认；只有在 allow_partial_release=true 且用户明确同意时才能发布就绪子集。"
    else:
        headline = "完整一键开源 Beta 不可用"
        summary = "当前没有可安全执行的平台。请按缺口清单补齐权限、资格、产物或合规确认后重试。"
    result = {
        "contract": PREFLIGHT_CONTRACT,
        "schema_version": "1.0",
        "interface_version": INTERFACE_VERSION,
        "generated_at": utc_now(),
        "release_id": plan.get("release_id"),
        "plan_sha256": sha256_file(plan_path),
        "status": status,
        "platforms": platform_results,
        "artifacts": list(artifacts.values()),
        "gaps": all_gaps,
        "warnings": warnings,
        "signals": {
            "full_one_click_beta_available": full_available,
            "assisted_release_available": bool(ready),
            "partial_release_possible": bool(ready) and bool(all_gaps),
            "manual_handoff_required": bool(guided_ready),
            "can_prepare": can_prepare,
            "can_request_final_confirmation": can_prepare,
            "external_action_authorized": False,
        },
        "ready_platforms": [item["id"] for item in ready],
        "one_click_ready_platforms": [item["id"] for item in one_click_ready],
        "guided_ready_platforms": [item["id"] for item in guided_ready],
        "blocked_platforms": [item["id"] for item in platform_results if item["gaps"]],
        "user_feedback": {
            "headline_zh": headline,
            "summary_zh": summary,
            "missing_permissions": missing_permissions,
            "next_actions": [item["recovery"] for item in all_gaps],
        },
    }
    return result


def ensure_new_output(output_dir: Path, project_root: Path) -> None:
    output_dir = output_dir.resolve()
    if not is_relative_to(output_dir, project_root.resolve()):
        raise ValueError("output directory escapes project_root")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be new or empty")
    output_dir.mkdir(parents=True, exist_ok=True)


def markdown_summary(preflight_result: dict[str, Any]) -> str:
    lines = [
        "# Open Release Beta 预检摘要",
        "",
        f"- 状态：`{preflight_result['status']}`",
        f"- 发布 ID：`{preflight_result.get('release_id')}`",
        f"- 完整一键 Beta：`{preflight_result['signals']['full_one_click_beta_available']}`",
        f"- 可请求最终确认：`{preflight_result['signals']['can_request_final_confirmation']}`",
        "",
        "## 平台",
        "",
        "| 平台 | 模式 | 状态 | 最大 Agent 动作 |",
        "|---|---|---|---|",
    ]
    for platform in preflight_result["platforms"]:
        lines.append(f"| {platform['label']} | `{platform.get('mode', '')}` | `{platform['status']}` | `{platform.get('maximum_agent_action', '')}` |")
    lines.extend(["", "## 阻断与恢复", ""])
    if not preflight_result["gaps"]:
        lines.append("无已知阻断；仍需用户对精确平台、文件、可见性和许可进行最后确认。")
    else:
        for item in preflight_result["gaps"]:
            lines.append(f"- `{item['code']}`：{item['message_zh']} 恢复：{item['recovery']['action_zh']}")
    lines.extend(["", "> 本摘要不包含任何 token、密码、Cookie 或会话值。", ""])
    return "\n".join(lines)


def prepare(plan_path: Path, output_dir: Path, *, invocation_root: Path | None = None) -> dict[str, Any]:
    plan, project_root, context_gaps, _ = plan_context(plan_path, invocation_root=invocation_root)
    check = preflight(plan_path, invocation_root=invocation_root)
    if context_gaps or not check["signals"]["can_prepare"]:
        return operation_result(
            operation="prepare",
            ok=False,
            outcome="BLOCKED",
            stage="open_release_preflight",
            audit=check,
            user_feedback=check["user_feedback"],
            gaps=check["gaps"],
            warnings=check["warnings"],
        )
    try:
        ensure_new_output(output_dir, project_root)
    except ValueError as exc:
        item = gap(code="OUTPUT_DIRECTORY_INVALID", platform=None, category="security", message_zh=str(exc), recovery_zh="选择 project_root 内新的空运行目录。", owner="main_flow")
        return operation_result(operation="prepare", ok=False, outcome="BLOCKED", stage="open_release_preflight", audit=check, user_feedback={"headline_zh": "无法准备发布", "summary_zh": str(exc), "missing_permissions": [], "next_actions": [item["recovery"]]}, gaps=[item], warnings=check["warnings"])
    selection_map = {str(item.get("id")): item for item in plan.get("selected_platforms") or [] if isinstance(item, dict)}
    platform_check_map = {item["id"]: item for item in check["platforms"]}
    eligible = check["ready_platforms"]
    manifest = {
        "contract": MANIFEST_CONTRACT,
        "schema_version": "1.0",
        "interface_version": INTERFACE_VERSION,
        "release_id": plan["release_id"],
        "created_at": utc_now(),
        "status": "READY_FOR_CONFIRMATION" if not check["blocked_platforms"] else "PARTIAL_READY_FOR_CONFIRMATION",
        "source_plan": {"path": relative_posix(plan_path, project_root), "sha256": sha256_file(plan_path)},
        "artifacts": check["artifacts"],
        "eligible_platforms": eligible,
        "blocked_platforms": check["blocked_platforms"],
        "release_policy": plan.get("release_policy") or {"allow_partial_release": False},
        "confirmation_id": sha256_bytes(f"{plan['release_id']}:{sha256_file(plan_path)}:{','.join(sorted(eligible))}".encode())[:24],
        "platform_snapshots": [],
    }
    action_plan = {
        "contract": "paperspine.open-release.agent-actions",
        "schema_version": "1.0",
        "release_id": plan["release_id"],
        "external_action_authorized": False,
        "rule_zh": "这些动作只能在 agent_release_ticket.json 通过最终用户确认后执行。任何平台返回新的许可、费用、资格或声明页面时必须暂停并回报用户。",
        "actions": [],
    }
    catalog = platform_map()
    for platform_id in eligible:
        selection = selection_map[platform_id]
        checked = platform_check_map[platform_id]
        platform = catalog[platform_id]
        metadata = dict(plan.get("metadata") or {})
        metadata.update(selection.get("metadata") or {})
        snapshot = {
            "id": platform_id,
            "label": platform["label"],
            "mode": checked["mode"],
            "automation_level": checked["automation_level"],
            "maximum_agent_action": checked["maximum_agent_action"],
            "artifact_ids": checked["artifact_ids"],
            "metadata": metadata,
            "visibility": metadata.get("visibility") or metadata.get("access_right") or platform["public_access"],
            "official_submit_url": platform["official_urls"].get("submit"),
        }
        manifest["platform_snapshots"].append(snapshot)
        action_plan["actions"].append(
            {
                "platform": platform_id,
                "label": platform["label"],
                "mode": checked["mode"],
                "launch_url": platform["official_urls"].get("submit"),
                "maximum_agent_action": checked["maximum_agent_action"],
                "artifact_ids": checked["artifact_ids"],
                "metadata": metadata,
                "requires_ticket": True,
                "stop_conditions": [
                    "new_fee_or_payment",
                    "new_license_or_terms",
                    "new_author_declaration",
                    "new_eligibility_or_institutional_approval",
                    "artifact_hash_changed",
                    "platform_requests_secret_in_chat_or_plan",
                ],
            }
        )
    preflight_path = output_dir / "open_release_preflight.json"
    manifest_path = output_dir / "open_release_manifest.json"
    actions_path = output_dir / "open_release_actions.json"
    summary_path = output_dir / "open_release_summary.md"
    write_json(preflight_path, check)
    write_json(manifest_path, manifest)
    write_json(actions_path, action_plan)
    summary_path.write_text(markdown_summary(check), encoding="utf-8", newline="\n")
    confirmation_request = {
        "contract": "paperspine.open-release.confirmation-request",
        "schema_version": "1.0",
        "confirmation_id": manifest["confirmation_id"],
        "release_id": plan["release_id"],
        "manifest_sha256": sha256_file(manifest_path),
        "eligible_platforms": eligible,
        "blocked_platforms": check["blocked_platforms"],
        "allow_partial_release": bool((plan.get("release_policy") or {}).get("allow_partial_release", False)),
        "confirmation_required": True,
        "consequences_zh": [
            "所选文件将离开本机并发送到确认的平台。",
            "公开记录、预印本、代码仓库或 DOI 可能永久可见或只能通过新版本修正。",
            "确认只覆盖清单哈希、平台、可见性、许可和最大 Agent 动作完全一致的本次发布。",
        ],
        "required_confirmation_fields": ["confirmed", "confirmed_by", "confirmed_at", "manifest_sha256", "authorized_platforms"],
    }
    confirmation_path = output_dir / "open_release_confirmation_request.json"
    write_json(confirmation_path, confirmation_request)
    artifacts_out = file_receipts([preflight_path, manifest_path, actions_path, confirmation_path, summary_path], project_root)
    return operation_result(
        operation="prepare",
        ok=True,
        outcome=manifest["status"],
        stage="open_release_confirmation_pending",
        audit=check,
        user_feedback={"headline_zh": "发布动作已准备，等待用户最后确认", "summary_zh": "尚未执行任何外部上传或公开动作。", "missing_permissions": check["user_feedback"]["missing_permissions"], "next_actions": [{"owner": "user", "action_zh": "核对平台、产物哈希、可见性、许可和动作范围后提交 confirmation JSON。", "url": None}]},
        gaps=[],
        warnings=check["warnings"],
        artifacts=artifacts_out,
        signals={"prepared": True, "final_confirmation_required": True, "external_action_authorized": False, "full_one_click_beta_available": check["signals"]["full_one_click_beta_available"], "partial_release_possible": check["signals"]["partial_release_possible"], "release_recorded": False},
    )


def artifact_drift_gaps(manifest: dict[str, Any], project_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for artifact in manifest.get("artifacts") or []:
        try:
            path = resolve_inside(project_root, str(artifact["path"]), label=f"artifact {artifact.get('id')}")
            digest, size, file_count = hash_path(path)
        except (ValueError, OSError) as exc:
            findings.append(gap(code="AUTHORIZED_ARTIFACT_UNAVAILABLE", platform=None, category="artifact", message_zh=f"最终确认前无法验证产物 {artifact.get('id')}：{exc}", recovery_zh="恢复原产物并重新 prepare。", owner="main_flow"))
            continue
        if digest != artifact.get("sha256") or size != artifact.get("size_bytes") or file_count != artifact.get("file_count"):
            findings.append(gap(code="AUTHORIZED_ARTIFACT_DRIFT", platform=None, category="artifact", message_zh=f"产物 {artifact.get('id')} 在 prepare 后发生变化。", recovery_zh="废弃本次确认请求，重新 prepare 并让用户确认新哈希。", owner="main_flow"))
    return findings


def authorize(manifest_path: Path, confirmation_path: Path, output_dir: Path, *, invocation_root: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    confirmation = read_json(confirmation_path)
    gaps: list[dict[str, Any]] = []
    if manifest.get("contract") != MANIFEST_CONTRACT:
        gaps.append(gap(code="MANIFEST_CONTRACT_INVALID", platform=None, category="contract", message_zh="发布清单 contract 无效。", recovery_zh="重新运行 prepare。", owner="main_flow"))
    if confirmation.get("contract") != CONFIRMATION_CONTRACT:
        gaps.append(gap(code="CONFIRMATION_CONTRACT_INVALID", platform=None, category="authorization", message_zh=f"确认文件 contract 必须是 {CONFIRMATION_CONTRACT}。", recovery_zh="由确认界面生成正式 confirmation JSON。"))
    for key_path in secret_key_paths(confirmation):
        gaps.append(gap(code="SECRET_IN_CONFIRMATION", platform=None, category="security", message_zh=f"确认文件中出现禁止保存的秘密字段：{key_path}。", recovery_zh="删除秘密值并重新确认。"))
    for value_path in secret_value_paths(confirmation):
        gaps.append(gap(code="SECRET_VALUE_IN_CONFIRMATION", platform=None, category="security", message_zh=f"确认文件中出现疑似秘密值：{value_path}（内容已隐藏）。", recovery_zh="删除秘密值，必要时轮换凭据，并重新确认。"))
    if confirmation.get("confirmed") is not True:
        gaps.append(gap(code="USER_CONFIRMATION_MISSING", platform=None, category="authorization", message_zh="用户尚未明确确认发布。", recovery_zh="在确认界面核对后勾选确认。"))
    if str(confirmation.get("manifest_sha256") or "") != sha256_file(manifest_path):
        gaps.append(gap(code="CONFIRMATION_MANIFEST_HASH_MISMATCH", platform=None, category="authorization", message_zh="用户确认绑定的 manifest SHA-256 与当前清单不一致。", recovery_zh="拒绝执行并对当前清单重新确认。"))
    for field in ("confirmed_by", "confirmed_at", "confirmation_id"):
        if not str(confirmation.get(field) or "").strip():
            gaps.append(gap(code=f"CONFIRMATION_{field.upper()}_MISSING", platform=None, category="authorization", message_zh=f"确认文件缺少 {field}。", recovery_zh="由确认界面补齐审计字段。"))
    if confirmation.get("confirmation_id") != manifest.get("confirmation_id"):
        gaps.append(gap(code="CONFIRMATION_ID_MISMATCH", platform=None, category="authorization", message_zh="confirmation_id 不属于当前 prepare 运行。", recovery_zh="从当前 open_release_confirmation_request.json 重新确认。"))
    authorized = [str(item) for item in confirmation.get("authorized_platforms") or []]
    eligible = set(str(item) for item in manifest.get("eligible_platforms") or [])
    if not authorized:
        gaps.append(gap(code="AUTHORIZED_PLATFORMS_MISSING", platform=None, category="authorization", message_zh="用户没有确认任何发布平台。", recovery_zh="至少选择一个已就绪平台。"))
    unauthorized = sorted(set(authorized) - eligible)
    if unauthorized:
        gaps.append(gap(code="AUTHORIZED_PLATFORM_NOT_ELIGIBLE", platform=None, category="authorization", message_zh=f"确认包含未通过预检的平台：{', '.join(unauthorized)}。", recovery_zh="只确认 eligible_platforms，或补齐权限后重新 prepare。"))
    if len(authorized) != len(set(authorized)):
        gaps.append(gap(code="AUTHORIZED_PLATFORM_DUPLICATE", platform=None, category="authorization", message_zh="确认的平台列表包含重复项。", recovery_zh="去重后重新确认。"))
    blocked = set(str(item) for item in manifest.get("blocked_platforms") or [])
    policy = manifest.get("release_policy") or {}
    if blocked and not (policy.get("allow_partial_release") is True and confirmation.get("allow_partial_release") is True):
        gaps.append(gap(code="PARTIAL_RELEASE_NOT_AUTHORIZED", platform=None, category="authorization", message_zh="仍有阻断平台，但计划或用户没有明确允许部分发布。", recovery_zh="补齐所有平台，或同时在计划与最终确认中明确允许只发布就绪子集。"))
    source_plan = manifest.get("source_plan") or {}
    try:
        plan_path = resolve_inside(invocation_root, str(source_plan.get("path") or ""), label="source plan")
        if sha256_file(plan_path) != source_plan.get("sha256"):
            gaps.append(gap(code="SOURCE_PLAN_DRIFT", platform=None, category="authorization", message_zh="prepare 后源计划发生变化。", recovery_zh="重新 prepare 并确认新清单。", owner="main_flow"))
    except (ValueError, OSError) as exc:
        gaps.append(gap(code="SOURCE_PLAN_UNAVAILABLE", platform=None, category="authorization", message_zh=f"无法验证源计划：{exc}", recovery_zh="恢复源计划或重新 prepare。", owner="main_flow"))
    gaps.extend(artifact_drift_gaps(manifest, invocation_root))
    if gaps:
        return operation_result(operation="authorize", ok=False, outcome="BLOCKED", stage="open_release_confirmation_pending", audit={"manifest_sha256": sha256_file(manifest_path), "confirmation_sha256": sha256_file(confirmation_path), "authorized_platforms_requested": authorized}, user_feedback={"headline_zh": "发布授权未生效", "summary_zh": "未执行任何外部动作。请修复确认或产物漂移问题。", "missing_permissions": [], "next_actions": [item["recovery"] for item in gaps]}, gaps=gaps, warnings=[])
    try:
        ensure_new_output(output_dir, invocation_root)
    except ValueError as exc:
        item = gap(code="OUTPUT_DIRECTORY_INVALID", platform=None, category="security", message_zh=str(exc), recovery_zh="选择 project_root 内新的空运行目录。", owner="main_flow")
        return operation_result(operation="authorize", ok=False, outcome="BLOCKED", stage="open_release_confirmation_pending", audit={}, user_feedback={"headline_zh": "发布授权未生效", "summary_zh": str(exc), "missing_permissions": [], "next_actions": [item["recovery"]]}, gaps=[item], warnings=[])
    snapshot_map = {str(item["id"]): item for item in manifest.get("platform_snapshots") or []}
    actions: list[dict[str, Any]] = []
    for platform_id in authorized:
        snapshot = snapshot_map[platform_id]
        action_scope = str(snapshot["maximum_agent_action"])
        key_payload = f"{manifest['release_id']}:{sha256_file(manifest_path)}:{platform_id}:{action_scope}"
        actions.append(
            {
                "platform": platform_id,
                "mode": snapshot["mode"],
                "action_scope": action_scope,
                "launch_url": snapshot["official_submit_url"],
                "artifact_ids": snapshot["artifact_ids"],
                "metadata": snapshot["metadata"],
                "idempotency_key": sha256_bytes(key_payload.encode("utf-8")),
                "stop_on_new_authority_request": True,
            }
        )
    full_one_click = all(not str(snapshot_map[platform_id]["automation_level"]).startswith(GUIDED_AUTOMATION_PREFIXES) for platform_id in authorized)
    ticket = {
        "contract": TICKET_CONTRACT,
        "schema_version": "1.0",
        "interface_version": INTERFACE_VERSION,
        "ticket_id": sha256_bytes(f"{confirmation['confirmation_id']}:{sha256_file(manifest_path)}:{','.join(sorted(authorized))}".encode()),
        "release_id": manifest["release_id"],
        "issued_at": utc_now(),
        "manifest": {"path": relative_posix(manifest_path, invocation_root), "sha256": sha256_file(manifest_path)},
        "confirmation": {"path": relative_posix(confirmation_path, invocation_root), "sha256": sha256_file(confirmation_path), "confirmed_by": confirmation["confirmed_by"], "confirmed_at": confirmation["confirmed_at"]},
        "external_action_authorized": True,
        "authorized_platforms": authorized,
        "actions": actions,
        "authority_boundary": {
            "exact_scope_only": True,
            "may_accept_new_fees_licenses_or_declarations": False,
            "may_upload_changed_artifacts": False,
            "guided_platforms_may_not_exceed_maximum_agent_action": True,
        },
    }
    ticket_path = output_dir / "agent_release_ticket.json"
    write_json(ticket_path, ticket)
    receipt_md = output_dir / "authorization_receipt.md"
    receipt_md.write_text(
        "# Open Release Beta 授权回执\n\n"
        f"- 发布 ID：`{manifest['release_id']}`\n"
        f"- Ticket ID：`{ticket['ticket_id']}`\n"
        f"- 已确认平台：{', '.join(authorized)}\n"
        "- 外部动作授权：`true`（仅限 ticket 中精确动作）\n\n"
        "> 新费用、新许可、新声明、新资格或文件变化会立即使当前授权失效并要求再次确认。\n",
        encoding="utf-8",
        newline="\n",
    )
    return operation_result(operation="authorize", ok=True, outcome="AGENT_RELEASE_AUTHORIZED", stage="open_release_host_execution", audit={"ticket": ticket}, user_feedback={"headline_zh": "已授权 Agent 执行精确发布动作", "summary_zh": "授权仅覆盖 ticket 中的平台、产物哈希、元数据和最大动作；遇到新权限或条款必须暂停。", "missing_permissions": [], "next_actions": [{"owner": "host_agent", "action_zh": "使用用户电脑执行 ticket actions，并为每个平台记录结构化回执。", "url": None}]}, gaps=[], warnings=[], artifacts=file_receipts([ticket_path, receipt_md], invocation_root), signals={"prepared": True, "final_confirmation_required": False, "external_action_authorized": True, "full_one_click_beta_available": full_one_click, "partial_release_possible": bool(blocked), "release_recorded": False})


def _has_external_identity(receipt: dict[str, Any], action: dict[str, Any]) -> bool:
    """Require a host-observed record locator, not a generic launch page.

    This is local structural verification; it does not prove remote existence or
    perform a publication/retry. Private draft IDs are legitimate locators too.
    """
    placeholders = {"", "none", "null", "unknown", "pending", "tbd", "todo", "n/a", "na", "-", "—"}
    for field in ("public_url", "doi", "accession", "platform_record_id"):
        value = receipt.get(field)
        if not isinstance(value, str) or value.strip().lower() in placeholders:
            continue
        value = value.strip()
        if field == "public_url":
            try:
                parsed = urlsplit(value)
                if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
                    continue
            except ValueError:
                continue
            if value.rstrip("/") == str(action.get("launch_url") or "").rstrip("/"):
                continue
        elif field == "doi" and not re.fullmatch(r"(?:https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/\S+", value, re.I):
            continue
        return True
    return False


def record(ticket_path: Path, receipts_path: Path, output_dir: Path, *, invocation_root: Path) -> dict[str, Any]:
    ticket = read_json(ticket_path)
    receipts = read_json(receipts_path)
    gaps: list[dict[str, Any]] = []
    if ticket.get("contract") != TICKET_CONTRACT or ticket.get("external_action_authorized") is not True:
        gaps.append(gap(code="TICKET_INVALID", platform=None, category="authorization", message_zh="Agent release ticket 无效或未授权。", recovery_zh="重新完成 prepare 与最终确认。", owner="main_flow"))
    if receipts.get("contract") != RECEIPTS_CONTRACT:
        gaps.append(gap(code="PLATFORM_RECEIPTS_CONTRACT_INVALID", platform=None, category="contract", message_zh=f"平台回执 contract 必须是 {RECEIPTS_CONTRACT}。", recovery_zh="由主机执行器按回执 Schema 重新生成。", owner="host_agent"))
    if str(receipts.get("ticket_sha256") or "") != sha256_file(ticket_path):
        gaps.append(gap(code="PLATFORM_RECEIPTS_TICKET_HASH_MISMATCH", platform=None, category="authorization", message_zh="平台回执没有绑定当前 ticket SHA-256。", recovery_zh="拒绝合并，使用本 ticket 的实际执行回执。", owner="host_agent"))
    for key_path in secret_key_paths(receipts):
        gaps.append(gap(code="SECRET_IN_PLATFORM_RECEIPTS", platform=None, category="security", message_zh=f"平台回执中出现禁止保存的秘密字段：{key_path}。", recovery_zh="删除 token/Cookie/密码，只记录公开标识、状态与错误码。", owner="host_agent"))
    for value_path in secret_value_paths(receipts):
        gaps.append(gap(code="SECRET_VALUE_IN_PLATFORM_RECEIPTS", platform=None, category="security", message_zh=f"平台回执中出现疑似秘密值：{value_path}（内容已隐藏）。", recovery_zh="删除秘密值并在必要时轮换凭据。", owner="host_agent"))
    authorized = set(str(item) for item in ticket.get("authorized_platforms") or [])
    actions: dict[str, dict[str, Any]] = {}
    raw_actions = ticket.get("actions")
    if not authorized or not isinstance(raw_actions, list):
        gaps.append(gap(code="TICKET_ACTIONS_INVALID", platform=None, category="authorization", message_zh="Ticket 必须包含已授权平台及精确动作。", recovery_zh="使用 authorize 生成的完整 ticket。", owner="host_agent"))
    for action in raw_actions if isinstance(raw_actions, list) else []:
        if not isinstance(action, dict):
            gaps.append(gap(code="TICKET_ACTIONS_INVALID", platform=None, category="contract", message_zh="Ticket 动作结构无效。", recovery_zh="使用 authorize 生成的完整 ticket。", owner="host_agent"))
            continue
        platform = str(action.get("platform") or "")
        scope = action.get("action_scope")
        manifest_hash = (ticket.get("manifest") or {}).get("sha256")
        release_id = ticket.get("release_id")
        key = action.get("idempotency_key")
        expected_key = sha256_bytes(f"{release_id}:{manifest_hash}:{platform}:{scope}".encode())
        if (platform not in authorized or platform in actions
                or not isinstance(scope, str) or not scope.strip()
                or not isinstance(release_id, str) or not release_id.strip()
                or not isinstance(manifest_hash, str) or not HEX64.fullmatch(manifest_hash)
                or key != expected_key):
            gaps.append(gap(code="TICKET_ACTION_SCOPE_INVALID", platform=platform or None, category="authorization", message_zh="Ticket 动作的平台/范围/幂等键与发布清单不一致。", recovery_zh="使用原 authorize ticket，不改写动作或键。", owner="host_agent"))
        actions[platform] = action
    if set(actions) != authorized:
        gaps.append(gap(code="TICKET_ACTIONS_COVERAGE_MISMATCH", platform=None, category="authorization", message_zh="Ticket 动作必须逐一对应已授权平台。", recovery_zh="使用 authorize 生成的完整 ticket。", owner="host_agent"))
    receipt_items = receipts.get("platforms") or []
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for item in receipt_items:
        if not isinstance(item, dict):
            gaps.append(gap(code="RECEIPT_ITEM_INVALID", platform=None, category="contract", message_zh="平台回执条目必须是对象。", recovery_zh="记录每个平台的实际结果。", owner="host_agent"))
            continue
        platform = str(item.get("id") or "")
        status = str(item.get("status") or "")
        if platform not in authorized:
            gaps.append(gap(code="RECEIPT_PLATFORM_NOT_AUTHORIZED", platform=platform or None, category="authorization", message_zh=f"回执包含未授权平台：{platform or '<empty>'}。", recovery_zh="只记录 ticket 授权的平台。", owner="host_agent"))
        if platform in seen:
            gaps.append(gap(code="RECEIPT_PLATFORM_DUPLICATE", platform=platform, category="contract", message_zh=f"平台 {platform} 有重复回执。", recovery_zh="每个平台只保留一条最终回执。", owner="host_agent"))
        seen.add(platform)
        if status not in RECEIPT_STATUSES:
            gaps.append(gap(code="RECEIPT_STATUS_INVALID", platform=platform, category="contract", message_zh=f"平台 {platform} 的回执状态无效：{status}。", recovery_zh="使用 Schema 允许的状态。", owner="host_agent"))
        if not str(item.get("recorded_at") or "").strip():
            gaps.append(gap(code="RECEIPT_TIMESTAMP_MISSING", platform=platform, category="contract", message_zh=f"平台 {platform} 缺少 recorded_at。", recovery_zh="记录主机观察到结果的时间。", owner="host_agent"))
        key = item.get("idempotency_key")
        action = actions.get(platform) or {}
        if not isinstance(key, str) or not HEX64.fullmatch(key) or key != action.get("idempotency_key"):
            gaps.append(gap(code="RECEIPT_IDEMPOTENCY_KEY_MISMATCH", platform=platform, category="authorization", message_zh=f"平台 {platform} 回执幂等键缺失或不属于当前 ticket 的精确动作。", recovery_zh="读取本次 ticket.actions 中对应平台的键并核对实际执行记录；不要重新发布。", owner="host_agent"))
        if status in {"PUBLISHED", "SUBMITTED_FOR_REVIEW", "DRAFT_CREATED"} and not _has_external_identity(item, action):
            gaps.append(gap(code="RECEIPT_EXTERNAL_IDENTITY_MISSING", platform=platform, category="contract", message_zh=f"平台 {platform} 的成功/审核/草稿结果缺少实际外部记录标识。", recovery_zh="从实际平台结果记录 URL、DOI、accession 或 platform_record_id；未知时如实报告等待或失败。", owner="host_agent"))
        normalized.append(item)
    missing = sorted(authorized - seen)
    for platform in missing:
        gaps.append(gap(code="RECEIPT_PLATFORM_MISSING", platform=platform, category="contract", message_zh=f"缺少已授权平台 {platform} 的执行回执。", recovery_zh="执行或明确记录 WAITING_USER/FAILED/SKIPPED。", owner="host_agent"))
    if gaps:
        return operation_result(operation="record", ok=False, outcome="BLOCKED", stage="open_release_host_execution", audit={"ticket_sha256": sha256_file(ticket_path), "receipts_sha256": sha256_file(receipts_path), "authorized_platforms": sorted(authorized)}, user_feedback={"headline_zh": "无法形成可信发布回执", "summary_zh": "平台回执与授权范围不一致或结构不完整。", "missing_permissions": [], "next_actions": [item["recovery"] for item in gaps]}, gaps=gaps, warnings=[])
    try:
        ensure_new_output(output_dir, invocation_root)
    except ValueError as exc:
        item = gap(code="OUTPUT_DIRECTORY_INVALID", platform=None, category="security", message_zh=str(exc), recovery_zh="选择 project_root 内新的空运行目录。", owner="main_flow")
        return operation_result(operation="record", ok=False, outcome="BLOCKED", stage="open_release_host_execution", audit={}, user_feedback={"headline_zh": "无法写入发布回执", "summary_zh": str(exc), "missing_permissions": [], "next_actions": [item["recovery"]]}, gaps=[item], warnings=[])
    success_count = sum(1 for item in normalized if item.get("status") in SUCCESS_RECEIPT_STATUSES)
    if success_count == len(authorized):
        overall = "RELEASE_RECORDED"
        stage = "open_release_recorded"
    elif success_count:
        overall = "PARTIAL_RELEASE_RECORDED"
        stage = "open_release_follow_up"
    else:
        overall = "RELEASE_WAITING_OR_FAILED"
        stage = "open_release_follow_up"
    final_receipt = {
        "contract": FINAL_RECEIPT_CONTRACT,
        "schema_version": "1.0",
        "interface_version": INTERFACE_VERSION,
        "release_id": ticket.get("release_id"),
        "ticket_id": ticket.get("ticket_id"),
        "ticket_sha256": sha256_file(ticket_path),
        "recorded_at": utc_now(),
        "status": overall,
        "platforms": normalized,
        "ticket_consumed": True,
        "replay_rule_zh": "重试前先读取本回执和每个平台的 idempotency_key；不得对已成功的平台重复创建记录。",
    }
    final_path = output_dir / "open_release_receipt.json"
    write_json(final_path, final_receipt)
    summary_path = output_dir / "open_release_receipt.md"
    lines = ["# Open Release Beta 发布回执", "", f"- 状态：`{overall}`", f"- Ticket：`{ticket.get('ticket_id')}`", "", "| 平台 | 状态 | 公开标识/URL |", "|---|---|---|"]
    for item in normalized:
        public_ref = item.get("public_url") or item.get("doi") or item.get("accession") or item.get("platform_record_id") or "—"
        lines.append(f"| {item.get('id')} | `{item.get('status')}` | {public_ref} |")
    lines.append("")
    summary_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return operation_result(operation="record", ok=True, outcome=overall, stage=stage, audit=final_receipt, user_feedback={"headline_zh": "发布结果已记录", "summary_zh": "已按平台逐项保留成功、审核中、等待用户或失败状态，不会把部分成功误报为全部完成。", "missing_permissions": [], "next_actions": []}, gaps=[], warnings=[], artifacts=file_receipts([final_path, summary_path], invocation_root), signals={"prepared": True, "final_confirmation_required": False, "external_action_authorized": False, "full_one_click_beta_available": False, "partial_release_possible": overall != "RELEASE_RECORDED", "release_recorded": overall in {"RELEASE_RECORDED", "PARTIAL_RELEASE_RECORDED"}})


def file_receipts(paths: Iterable[Path], root: Path) -> list[dict[str, Any]]:
    return [
        {"path": relative_posix(path, root), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        for path in paths
    ]


def operation_result(
    *,
    operation: str,
    ok: bool,
    outcome: str,
    stage: str,
    audit: dict[str, Any],
    user_feedback: dict[str, Any],
    gaps: list[dict[str, Any]],
    warnings: list[str],
    artifacts: list[dict[str, Any]] | None = None,
    signals: dict[str, Any] | None = None,
    request_sha256: str | None = None,
) -> dict[str, Any]:
    default_signals = {
        "prepared": False,
        "final_confirmation_required": False,
        "external_action_authorized": False,
        "full_one_click_beta_available": False,
        "partial_release_possible": False,
        "release_recorded": False,
    }
    if signals:
        default_signals.update(signals)
    return {
        "contract": RESULT_CONTRACT,
        "interface_version": INTERFACE_VERSION,
        "request_sha256": request_sha256,
        "operation": operation,
        "ok": ok,
        "outcome": outcome,
        "stage": stage,
        "gaps": gaps,
        "warnings": warnings,
        "artifacts": artifacts or [],
        "signals": default_signals,
        "user_feedback": user_feedback,
        "authority_boundary": {
            "external_action_authorized": bool(default_signals["external_action_authorized"]),
            "scope": "ticket_exact_scope_only" if default_signals["external_action_authorized"] else "local_read_prepare_or_record_only",
            "may_store_secrets": False,
            "may_infer_author_or_institutional_declarations": False,
            "may_accept_new_fees_licenses_terms_or_eligibility": False,
        },
        "audit": audit,
    }


def public_interface_descriptor() -> dict[str, Any]:
    catalog = load_catalog()
    return {
        "contract": "paperspine.open-release.interface",
        "interface_version": INTERFACE_VERSION,
        "status": "beta",
        "purpose_zh": "在交稿完成后推荐开放平台，检查本机权限与学科合规，准备精确动作，并在用户最终确认后把动作交给主机 Agent。",
        "transport": {
            "describe_cli": "python scripts/open_release.py describe",
            "invoke_cli": "python scripts/open_release.py invoke <open-release-invocation.json>",
            "python": "invoke_open_release(request_path)",
        },
        "operations": [
            {"id": "catalog", "inputs": [], "output_directory": False, "external_mutation": False},
            {"id": "preflight", "inputs": ["plan"], "output_directory": False, "external_mutation": False},
            {"id": "prepare", "inputs": ["plan"], "output_directory": True, "external_mutation": False},
            {"id": "authorize", "inputs": ["manifest", "confirmation"], "output_directory": True, "external_mutation": False, "produces_external_action_ticket": True},
            {"id": "record", "inputs": ["ticket", "receipts"], "output_directory": True, "external_mutation": False},
        ],
        "platform_catalog": {
            "version": catalog["catalog_version"],
            "selectable_count": sum(1 for item in catalog["platforms"] if item.get("selectable")),
            "discovery_services": [item["id"] for item in catalog["platforms"] if not item.get("selectable")],
        },
        "host_execution_boundary": {
            "module_executes_network_publish": False,
            "host_agent_requires_ticket": True,
            "final_user_confirmation_is_hash_bound": True,
            "new_fees_licenses_declarations_or_eligibility_require_reconfirmation": True,
            "credentials_are_never_written_to_contracts": True,
        },
        "schemas": [
            "references/contracts/open-release-invocation.schema.json",
            "references/contracts/open-release-plan.schema.json",
            "references/contracts/open-release-manifest.schema.json",
            "references/contracts/open-release-confirmation.schema.json",
            "references/contracts/open-release-agent-ticket.schema.json",
            "references/contracts/open-release-platform-receipts.schema.json",
            "references/contracts/open-release-result.schema.json",
        ],
    }


def resolve_request_path(request_path: Path, project_root: Path, inputs: dict[str, Any], key: str) -> Path:
    raw = str(inputs.get(key) or "")
    if not raw:
        raise ValueError(f"missing required input: {key}")
    return resolve_inside(project_root, raw, label=f"input {key}")


def invoke_open_release(request_path: str | Path) -> dict[str, Any]:
    request_path = Path(request_path).resolve()
    try:
        request = read_json(request_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return operation_result(operation="unknown", ok=False, outcome="BLOCKED", stage="open_release_request", audit={}, user_feedback={"headline_zh": "Open Release 请求无效", "summary_zh": str(exc), "missing_permissions": [], "next_actions": []}, gaps=[gap(code="REQUEST_INVALID", platform=None, category="contract", message_zh=str(exc), recovery_zh="修正请求 JSON。", owner="main_flow")], warnings=[])
    operation = str(request.get("operation") or "unknown")
    request_sha = sha256_file(request_path)
    if request.get("contract") != "paperspine.open-release.invoke-request" or request.get("interface_version") != INTERFACE_VERSION:
        return operation_result(operation=operation, ok=False, outcome="BLOCKED", stage="open_release_request", audit={"request_sha256": request_sha}, user_feedback={"headline_zh": "Open Release 接口版本或 contract 不匹配", "summary_zh": f"需要 interface_version={INTERFACE_VERSION}。", "missing_permissions": [], "next_actions": []}, gaps=[gap(code="REQUEST_CONTRACT_INVALID", platform=None, category="contract", message_zh="请求 contract/interface_version 无效。", recovery_zh="调用 describe 后按当前 Schema 重建请求。", owner="main_flow")], warnings=[], request_sha256=request_sha)
    try:
        raw_root = str(request.get("project_root") or ".")
        project_root = (request_path.parent / raw_root).resolve()
        if not is_relative_to(request_path, project_root):
            raise ValueError("request file must be inside project_root")
        inputs = request.get("inputs") if isinstance(request.get("inputs"), dict) else {}
        outputs = request.get("outputs") if isinstance(request.get("outputs"), dict) else {}
        options = request.get("options") if isinstance(request.get("options"), dict) else {}
        if operation == "catalog":
            audit = recommendation_catalog(str(options.get("domain") or "all"), [str(item) for item in options.get("artifact_roles") or []], str(options.get("sensitivity") or "none"))
            result = operation_result(operation="catalog", ok=True, outcome="CATALOG_READY", stage="open_release_selection", audit=audit, user_feedback={"headline_zh": "开放平台目录已就绪", "summary_zh": "主流程可按推荐分数与边界显示复选框；没有覆盖的学科需转 FAIRsharing/re3data 做实时发现。", "missing_permissions": [], "next_actions": []}, gaps=[], warnings=[])
        elif operation == "preflight":
            check = preflight(resolve_request_path(request_path, project_root, inputs, "plan"), invocation_root=project_root)
            result = operation_result(operation="preflight", ok=check["signals"]["can_prepare"], outcome=check["status"], stage="open_release_preflight", audit=check, user_feedback=check["user_feedback"], gaps=check["gaps"], warnings=check["warnings"], signals={"prepared": False, "final_confirmation_required": check["signals"]["can_request_final_confirmation"], "external_action_authorized": False, "full_one_click_beta_available": check["signals"]["full_one_click_beta_available"], "partial_release_possible": check["signals"]["partial_release_possible"], "release_recorded": False})
        elif operation == "prepare":
            output_dir = resolve_inside(project_root, str(outputs.get("directory") or ""), label="output directory")
            result = prepare(resolve_request_path(request_path, project_root, inputs, "plan"), output_dir, invocation_root=project_root)
        elif operation == "authorize":
            output_dir = resolve_inside(project_root, str(outputs.get("directory") or ""), label="output directory")
            result = authorize(resolve_request_path(request_path, project_root, inputs, "manifest"), resolve_request_path(request_path, project_root, inputs, "confirmation"), output_dir, invocation_root=project_root)
        elif operation == "record":
            output_dir = resolve_inside(project_root, str(outputs.get("directory") or ""), label="output directory")
            result = record(resolve_request_path(request_path, project_root, inputs, "ticket"), resolve_request_path(request_path, project_root, inputs, "receipts"), output_dir, invocation_root=project_root)
        else:
            raise ValueError(f"unsupported operation: {operation}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = operation_result(operation=operation, ok=False, outcome="BLOCKED", stage="open_release_request", audit={}, user_feedback={"headline_zh": "Open Release 调用被阻断", "summary_zh": str(exc), "missing_permissions": [], "next_actions": []}, gaps=[gap(code="INVOCATION_INVALID", platform=None, category="contract", message_zh=str(exc), recovery_zh="修正路径、输入或输出目录后重试。", owner="main_flow")], warnings=[])
    result["request_sha256"] = request_sha
    return result


def add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit JSON (the default; retained for cross-script consistency).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PaperSpine post-delivery Open Release Beta.")
    sub = parser.add_subparsers(dest="command", required=True)
    describe_parser = sub.add_parser("describe")
    add_json_flag(describe_parser)
    catalog_parser = sub.add_parser("catalog")
    catalog_parser.add_argument("--domain", default="all")
    catalog_parser.add_argument("--artifact-role", action="append", default=[])
    catalog_parser.add_argument("--sensitivity", default="none")
    add_json_flag(catalog_parser)
    preflight_parser = sub.add_parser("preflight")
    preflight_parser.add_argument("plan", type=Path)
    add_json_flag(preflight_parser)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("plan", type=Path)
    prepare_parser.add_argument("output_dir", type=Path)
    add_json_flag(prepare_parser)
    authorize_parser = sub.add_parser("authorize")
    authorize_parser.add_argument("manifest", type=Path)
    authorize_parser.add_argument("confirmation", type=Path)
    authorize_parser.add_argument("output_dir", type=Path)
    authorize_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    add_json_flag(authorize_parser)
    record_parser = sub.add_parser("record")
    record_parser.add_argument("ticket", type=Path)
    record_parser.add_argument("receipts", type=Path)
    record_parser.add_argument("output_dir", type=Path)
    record_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    add_json_flag(record_parser)
    invoke_parser = sub.add_parser("invoke")
    invoke_parser.add_argument("request", type=Path)
    add_json_flag(invoke_parser)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "describe":
        payload = public_interface_descriptor()
        ok = True
    elif args.command == "catalog":
        payload = recommendation_catalog(args.domain, args.artifact_role, args.sensitivity)
        ok = True
    elif args.command == "preflight":
        check = preflight(args.plan)
        payload = operation_result(operation="preflight", ok=check["signals"]["can_prepare"], outcome=check["status"], stage="open_release_preflight", audit=check, user_feedback=check["user_feedback"], gaps=check["gaps"], warnings=check["warnings"], signals={"final_confirmation_required": check["signals"]["can_request_final_confirmation"], "full_one_click_beta_available": check["signals"]["full_one_click_beta_available"], "partial_release_possible": check["signals"]["partial_release_possible"]})
        ok = payload["ok"]
    elif args.command == "prepare":
        payload = prepare(args.plan.resolve(), args.output_dir.resolve())
        ok = payload["ok"]
    elif args.command == "authorize":
        payload = authorize(args.manifest.resolve(), args.confirmation.resolve(), args.output_dir.resolve(), invocation_root=args.project_root.resolve())
        ok = payload["ok"]
    elif args.command == "record":
        payload = record(args.ticket.resolve(), args.receipts.resolve(), args.output_dir.resolve(), invocation_root=args.project_root.resolve())
        ok = payload["ok"]
    else:
        payload = invoke_open_release(args.request)
        ok = payload["ok"]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
