#!/usr/bin/env python3
"""通用步骤 Manifest 协议 — 所有技能统一调用。

每条钢律：
1. 每个步骤产出 STEP_MANIFEST.json（输入哈希 + 配置 + 输出哈希 + backend 声明）
2. 每个外部依赖有 UPSTREAM.md（来源 + commit + license + 修改记录）
3. 每个关键技能有专属质量门禁（named check）

用法：
    from engine.step_manifest import write_manifest, validate_manifest

    manifest_path = write_manifest(
        workspace=Path("workspaces/cumcm-demo"),
        step_name="comp-modeling",
        config={"solver": "HiGHS", "timeLimit": 300},
        inputs=[Path("data/clean.csv")],
        outputs=[Path("MODELING_REPORT.md")],
        backend="scipy 1.14.1",
        commands=[{"command": "python code/main.py", "exitCode": 0}],
        dependencies={"scipy": "1.14.1", "numpy": "2.4.6"},
    )
    result = validate_manifest(workspace, manifest_path)
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# 当前 schema 版本
SCHEMA_VERSION = 1


def _sha256(path: Path) -> str:
    """计算文件或目录 SHA-256，路径不存在时返回空字符串。"""
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    if path.is_dir():
        files = sorted(item for item in path.rglob("*") if item.is_file())
        if not files:
            return ""
        for item in files:
            rel = item.relative_to(path).as_posix().encode("utf-8")
            digest.update(len(rel).to_bytes(8, "big"))
            digest.update(rel)
            digest.update(item.read_bytes())
        return digest.hexdigest()
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return ""


def _path_metadata(workspace: Path, path: Path) -> dict[str, Any]:
    abs_path = path.resolve() if not path.is_absolute() else path.resolve()
    try:
        rel = abs_path.relative_to(workspace.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"路径超出工作区: {path}")
    exists = abs_path.exists()
    if abs_path.is_dir():
        size = sum(item.stat().st_size for item in abs_path.rglob("*") if item.is_file())
        kind = "directory"
    elif abs_path.is_file():
        size = abs_path.stat().st_size
        kind = "file"
    else:
        size = 0
        kind = "missing"
    return {"path": rel, "sha256": _sha256(abs_path), "exists": exists, "size": size, "kind": kind}


def _resolve_paths(workspace: Path, paths: list[Path]) -> list[dict[str, Any]]:
    """将路径列表解析为相对路径 + SHA-256 + 元数据的字典列表。"""
    resolved = []
    for p in paths:
        resolved.append(_path_metadata(workspace, p))
    return resolved


def _manifest_entry_path(workspace: Path, declared_path: str) -> Path | None:
    if not declared_path:
        return None
    candidate = Path(declared_path)
    if candidate.is_absolute():
        return None
    resolved = (workspace / candidate).resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError:
        return None
    return resolved


def write_manifest(
    workspace: Path,
    step_name: str,
    config: dict[str, Any] | None = None,
    inputs: list[Path] | None = None,
    outputs: list[Path] | None = None,
    backend: str = "",
    commands: list[dict[str, Any]] | None = None,
    dependencies: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """写入 STEP_MANIFEST.json 到工作区根目录。

    Args:
        workspace: 工作区路径
        step_name: 步骤名称（如 "comp-modeling"）
        config: 步骤配置参数
        inputs: 输入文件路径列表
        outputs: 输出文件路径列表
        backend: 后端引擎及版本声明（如 "scipy 1.14.1"）
        commands: 执行的命令列表，每项含 command/exitCode
        dependencies: 依赖库版本字典
        extra: 额外自定义字段

    Returns:
        manifest_path: 生成的 manifest 文件路径
    """
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "stepName": step_name,
        "executedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "backend": backend,
        "config": config or {},
        "inputFiles": _resolve_paths(workspace, inputs or []),
        "outputFiles": _resolve_paths(workspace, outputs or []),
        "commands": commands or [],
        "dependencies": dependencies or {},
    }

    config_json = json.dumps(manifest["config"], sort_keys=True, ensure_ascii=False)
    manifest["configSha256"] = hashlib.sha256(config_json.encode("utf-8")).hexdigest()

    if extra:
        manifest.update(extra)

    manifest_path = workspace / "STEP_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def validate_manifest(workspace: Path, manifest_path: str | Path | None = None) -> dict[str, Any]:
    """验证 STEP_MANIFEST.json 的存在性、schema 版本、必填字段完整性。

    Args:
        workspace: 工作区路径
        manifest_path: manifest 文件路径（默认 workspace/STEP_MANIFEST.json）

    Returns:
        {"ok": bool, "errors": list[str], "manifest": dict|None}
    """
    workspace = Path(workspace).resolve()
    if manifest_path is None:
        manifest_path = workspace / "STEP_MANIFEST.json"
    else:
        manifest_path = Path(manifest_path)
        if not manifest_path.is_absolute():
            manifest_path = workspace / manifest_path
        manifest_path = manifest_path.resolve()

    try:
        manifest_path.relative_to(workspace)
    except ValueError:
        return {"ok": False, "errors": [f"STEP_MANIFEST.json 超出工作区: {manifest_path}"], "manifest": None}

    errors: list[str] = []

    if not manifest_path.is_file():
        return {"ok": False, "errors": [f"STEP_MANIFEST.json 不存在: {manifest_path}"], "manifest": None}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "errors": [f"STEP_MANIFEST.json 不是有效 JSON: {exc}"], "manifest": None}

    if not isinstance(manifest, dict):
        return {"ok": False, "errors": ["STEP_MANIFEST.json 不是字典"], "manifest": None}

    # 校验 schemaVersion
    sv = manifest.get("schemaVersion")
    if sv != SCHEMA_VERSION:
        errors.append(f"schemaVersion 应为 {SCHEMA_VERSION}，实际为 {sv}")

    # 校验必填字段
    required_fields = ["stepName", "executedAt", "backend", "config", "inputFiles", "outputFiles", "commands", "dependencies"]
    for field in required_fields:
        if field not in manifest or manifest.get(field) is None or manifest.get(field) == "":
            errors.append(f"缺少必填字段: {field}")

    for field in ("config", "dependencies"):
        if field in manifest and not isinstance(manifest[field], dict):
            errors.append(f"字段类型错误: {field} 应为 dict")
    for field in ("inputFiles", "outputFiles", "commands"):
        if field in manifest and not isinstance(manifest[field], list):
            errors.append(f"字段类型错误: {field} 应为 list")

    config = manifest.get("config", {}) if isinstance(manifest.get("config", {}), dict) else {}
    expected_config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    if manifest.get("configSha256") != expected_config_hash:
        errors.append("configSha256 不匹配")

    # 校验输入文件存在性
    for inp in manifest.get("inputFiles", []):
        path = inp.get("path", "")
        if path:
            full_path = _manifest_entry_path(workspace, path)
            if full_path is None:
                errors.append(f"输入文件路径超出工作区: {path}")
                continue
            if not full_path.exists():
                errors.append(f"输入文件不存在: {path}")
            else:
                actual_sha = _sha256(full_path)
                declared_sha = inp.get("sha256", "")
                if declared_sha and actual_sha and actual_sha != declared_sha:
                    errors.append(f"输入文件 SHA-256 不匹配: {path}")

    # 校验输出文件存在性
    for out in manifest.get("outputFiles", []):
        path = out.get("path", "")
        if path:
            full_path = _manifest_entry_path(workspace, path)
            if full_path is None:
                errors.append(f"输出文件路径超出工作区: {path}")
                continue
            if not full_path.exists():
                errors.append(f"输出文件不存在: {path}")
            else:
                actual_sha = _sha256(full_path)
                declared_sha = out.get("sha256", "")
                if declared_sha and actual_sha and actual_sha != declared_sha:
                    errors.append(f"输出文件 SHA-256 不匹配: {path}")

    # S7 FIX: UPSTREAM.md provenance 强制校验
    # 每个 dependencies 条目必须有对应的 UPSTREAM.md 溯源文档
    dependencies = manifest.get("dependencies", {})
    if dependencies:
        upstream_errors = _validate_upstream_provenance(workspace, dependencies)
        errors.extend(upstream_errors)

    return {
        "ok": not errors,
        "errors": errors,
        "manifest": manifest,
        "schemaVersion": sv,
        "stepName": manifest.get("stepName", ""),
        "executedAt": manifest.get("executedAt", ""),
        "backend": manifest.get("backend", ""),
        "outputCount": len(manifest.get("outputFiles", [])),
        "inputCount": len(manifest.get("inputFiles", [])),
    }


def get_step_manifest(workspace: Path) -> dict[str, Any] | None:
    """读取工作区的 STEP_MANIFEST.json（如果存在）。"""
    manifest_path = Path(workspace).resolve() / "STEP_MANIFEST.json"
    if not manifest_path.is_file():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _validate_upstream_provenance(workspace: Path, dependencies: dict[str, str]) -> list[str]:
    """校验 dependencies 中每个包是否有对应的 UPSTREAM.md 溯源文档。

    搜索路径：
    1. 工作区根目录下的 UPSTREAM.md
    2. tools/ 目录下的各子目录 UPSTREAM.md
    3. skills/*/references/UPSTREAM.md
    4. 项目根目录的 data/UPSTREAM.md

    返回错误列表，空列表表示通过。
    """
    errors = []
    project_root = workspace.resolve()
    suite_root = Path(__file__).resolve().parent.parent

    # 收集所有已存在的 UPSTREAM.md 路径
    upstream_files: set[Path] = set()
    for root in (project_root, suite_root):
        for pattern in ["UPSTREAM.md", "tools/*/UPSTREAM.md", "skills/*/references/UPSTREAM.md",
                        "skills/*/*/UPSTREAM.md", "data/UPSTREAM.md"]:
            upstream_files.update(root.glob(pattern))

    # 对每个 dependency 检查是否有溯源
    for pkg_name in dependencies:
        # 简单匹配：包名出现在某个 UPSTREAM.md 的内容中
        found = False
        for up_file in upstream_files:
            try:
                content = up_file.read_text(encoding="utf-8", errors="ignore")
                haystack = f"{up_file.as_posix()}\n{content}".lower()
                if pkg_name.lower() in haystack:
                    found = True
                    break
            except (OSError, UnicodeDecodeError):
                continue

        if not found:
            # 特殊处理：已知标准库或无溯源要求的包
            known_without_upstream = {"python", "numpy", "scipy", "pandas", "matplotlib",
                                      "seaborn", "pillow", "fitz", "pymupdf"}
            if pkg_name.lower() not in known_without_upstream:
                errors.append(f"依赖 {pkg_name} 缺少 UPSTREAM.md 溯源文档")

    return errors
