"""Small, durable file bridge between the PaperSpine Skill and the Web UI.

The Skill remains the authority for research, writing, figures and review. This
module only materialises the current event projection as human-readable files so
the host Agent can resume work and the Web surface can show the same state. It
never stores credentials. Configuration readiness is derived from the trusted
event surface: a host proposal is visible, but it is not a user confirmation.
"""

from __future__ import annotations

import json
import os
import mimetypes
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


BRIDGE_VERSION = "1.0"
FIGURE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".svg", ".tif", ".tiff", ".webp"}
USER_CONFIGURATION_SOURCE = "web_user"


def configuration_readiness(projection: Mapping[str, Any]) -> dict[str, Any]:
    """Return the execution boundary for the current task configuration."""
    configuration = projection.get("configuration")
    source = projection.get("configuration_source") or "legacy_unknown"
    stale = bool(projection.get("configuration_stale", False))
    ready = (isinstance(configuration, Mapping) and bool(configuration)
             and source == USER_CONFIGURATION_SOURCE and not stale)
    if ready:
        reason = "web_user_confirmed"
    elif not configuration:
        reason = "configuration_missing"
    elif stale:
        reason = "configuration_stale"
    elif source == "agent_proposal":
        reason = "agent_proposal_requires_web_confirmation"
    else:
        reason = "configuration_source_unverified"
    return {
        "ready": ready, "source": source, "user_confirmed": ready,
        "stale": stale, "reason": reason,
        "next_action": "continue_paper_spine_skill" if ready else "save_configuration",
    }


def configuration_with_defaults(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Project additive user preferences without rewriting historical events.

    Counts are research instructions for the host, never delivery predicates.
    Explicit scenes (including report) and unrelated saved fields are retained.
    """
    return {
        "scene": "journal", **raw,
        "literature": {
            "same_field_papers": 3, "target_venue_papers": 3,
            "reference_count_mode": "venue_average", "reference_count": None,
            "mechanism_figure": "prefer", **raw.get("literature", {}),
        },
    }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _atomic(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(body, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _md(title: str, value: Mapping[str, Any]) -> str:
    lines = [f"# {title}", "", "```json", _json(value).rstrip(), "```", ""]
    return "\n".join(lines)


def _safe_artifact(item: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("artifact_id", "artifact_type", "filename", "media_type", "size_bytes",
            "sha256", "stage", "freshness", "previewable", "content_url", "download_url",
            "source", "runner_revision", "path", "relative_path", "manifest_sha256", "archive_sha256",
            "package_scope")
    return {key: item[key] for key in keys if key in item}


def _figure_candidates(task: Mapping[str, Any], workspace_root: Path) -> list[dict[str, Any]]:
    """Discover editable/current figure candidates in the task's paper folders.

    Only conventional figure directories below the task workspace/run are
    scanned. This keeps the Web surface useful for files the Agent has just
    generated without exposing arbitrary material paths.
    """
    roots = [workspace_root / "paper" / "figures", workspace_root / "paper" / "figure-candidates"]
    run_root = task.get("run_root")
    if run_root:
        run = Path(str(run_root)).resolve()
        roots.extend([run / "paper" / "figures", run / "paper" / "figure-candidates",
                      run / ".staging" / "figure-candidates"])
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.resolve().is_relative_to(workspace_root.resolve()):
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in FIGURE_SUFFIXES:
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(workspace_root.resolve()) or path.is_symlink():
                continue
            if str(resolved) in seen:
                continue
            seen.add(str(resolved))
            found.append({"filename": path.name, "relative_path": path.relative_to(workspace_root).as_posix(),
                          "path": str(resolved), "size_bytes": path.stat().st_size,
                          "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                          "source": "skill_bridge_candidate"})
    return found


def figure_reference_catalog(workspace_root: Path, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Read bounded descriptive pair metadata and local paper PDFs, never task state.

    Missing metadata is normal. Never infer paired assets by array position or
    expose arbitrary files. The optional metadata is authored alongside figures.
    """
    workspace = workspace_root.resolve()
    documents: list[dict[str, Any]] = []
    root = workspace / "paper" / "references"
    if root.is_dir() and root.resolve().is_relative_to(workspace) and not root.is_symlink():
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() != ".pdf" or path.is_symlink():
                continue
            if not path.resolve().is_relative_to(root.resolve()):
                continue
            try:
                with path.open("rb") as stream:
                    if not stream.read(1024).lstrip().startswith(b"%PDF-"):
                        continue
                documents.append({"filename": path.name, "relative_path": path.relative_to(workspace).as_posix(),
                                  "path": str(path.resolve()), "size_bytes": path.stat().st_size,
                                  "media_type": "application/pdf", "source": "local_reference_document"})
            except OSError:
                continue
    assets = {item["relative_path"] for item in candidates}
    docs = {item["relative_path"] for item in documents}
    pairs: list[dict[str, Any]] = []
    warnings: list[str] = []
    for parent in ("figures", "figure-candidates"):
        path = workspace / "paper" / parent / "reference-pairs.json"
        if not path.exists():
            continue
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(workspace) or path.stat().st_size > 131072:
                raise ValueError("unsafe or oversized metadata")
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            entries = data.get("pairs") if isinstance(data, dict) else None
            if not isinstance(entries, list) or len(entries) > 500:
                raise ValueError("expected a bounded pairs list")
            for item in entries:
                if not isinstance(item, dict) or not isinstance(item.get("figure_file"), str) or not isinstance(item.get("reference_file"), str):
                    warnings.append("配对元数据存在无效条目，未用于配对。")
                    continue
                if item["figure_file"] not in assets or item["reference_file"] not in assets:
                    warnings.append("配对文件尚未出现在当前任务图件目录中，未用于配对。")
                    continue
                pair = {"figure_file": item["figure_file"], "reference_file": item["reference_file"]}
                if isinstance(item.get("source_pdf"), str) and item["source_pdf"] in docs:
                    pair["source_pdf"] = item["source_pdf"]
                elif item.get("source_pdf"):
                    warnings.append("原文PDF未在当前任务的paper/references目录中找到，未开放该路径。")
                if isinstance(item.get("source_url"), str) and len(item["source_url"]) <= 4096:
                    pair["source_url"] = item["source_url"]  # Click-only UI validates http(s), never server-fetch.
                if type(item.get("page")) is int and 1 <= item["page"] <= 100000:
                    pair["page"] = item["page"]
                if isinstance(item.get("figure_label"), str):
                    pair["figure_label"] = item["figure_label"][:180]
                if pair not in pairs:
                    pairs.append(pair)
        except (OSError, UnicodeError, ValueError):
            warnings.append("参考配对说明暂不可读；已有图件与用户选择保持不变。")
    return {"reference_documents": documents, "reference_pairs": pairs,
            "reference_warnings": list(dict.fromkeys(warnings))}


def _choice_status(decisions: list[dict[str, Any]]) -> str:
    decisions = [item for item in decisions if not item.get("stale")]
    if any(item.get("status") == "pending" for item in decisions):
        return "pending"
    if decisions and all(item.get("status") == "resolved" for item in decisions):
        return "resolved"
    return "not_started"


def export_workflow_files(task: Mapping[str, Any], projection: Mapping[str, Any],
                          workspace_root: str | Path) -> dict[str, Any]:
    """Write the stable Skill/Web handoff files and return their metadata.

    The function is intentionally best-effort at the call site, but is strict
    about the output location: all files stay below the task workspace.
    """
    root = Path(workspace_root).resolve()
    bridge = (root / "paper" / "workflow").resolve()
    if root not in bridge.parents:
        raise ValueError("workflow bridge escaped task workspace")
    bridge.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    stage = projection.get("stage") or "intake"
    decisions = [dict(item) for item in (projection.get("decisions") or []) if isinstance(item, Mapping)]
    motivation = [item for item in decisions if any(token in str(item.get("decision_type", "")).lower()
                                                   for token in ("motivation", "contribution", "research_question", "hypothesis"))]
    figures = [item for item in decisions if any(token in str(item.get("decision_type", "")).lower()
                                                 for token in ("figure", "visual", "plot", "chart"))]
    revisions = list(projection.get("revision_requests") or [])
    if not revisions and projection.get("revision_request"):
        revisions = [projection["revision_request"]]
    review = {
        "findings": projection.get("findings") or [],
        "revision_requests": revisions,
        "reviews": projection.get("reviews") or [],
        "last_review": projection.get("last_review") or next(iter(reversed(projection.get("reviews") or [])), None),
    }
    pending_decisions = [item for item in decisions if item.get("status") == "pending" and not item.get("stale")]
    current_decision_phase = (
        "motivation" if _choice_status(motivation) == "pending"
        else "figure" if _choice_status(figures) == "pending"
        else None
    )
    configuration_state = configuration_readiness(projection)
    files: dict[str, Any] = {}
    state = {
        "schema_version": BRIDGE_VERSION, "source": "paperspine5.skill_bridge",
        "task_id": projection.get("task_id") or task.get("task_id"),
        "task_version": projection.get("task_version"), "updated_at": now,
        "stage": stage, "effective_stage": stage,
        "status": projection.get("status"),
        "current_decision_phase": current_decision_phase,
        "pending_decision_ids": [item["decision_id"] for item in pending_decisions],
        "next_action": (["complete_user_choices"] if pending_decisions else
                        [configuration_state["next_action"]] if not configuration_state["ready"] else
                        ["review_local_delivery"] if projection.get("status") == "delivery_ready" else
                        ["continue_paper_spine_skill"]),
        "current_milestone": next(iter(reversed(projection.get("milestones") or [])), None),
        "agent_instruction": "读取本目录的阶段文件；用户选择由 Web 写入并由宿主 Agent 继续原 PaperSpine Skill。",
    }
    configuration = {
        "schema_version": BRIDGE_VERSION, "task_id": state["task_id"],
        "status": ("saved" if configuration_state["ready"] else
                    "proposal" if projection.get("configuration") else "pending"),
        "configuration": (configuration_with_defaults(projection["configuration"])
                          if projection.get("configuration") is not None else None),
        "source": configuration_state["source"],
        "user_confirmed": configuration_state["user_confirmed"],
        "readiness": configuration_state,
        "run_contract": projection.get("run_contract"),
    }
    materials = {
        "schema_version": BRIDGE_VERSION, "task_id": state["task_id"],
        "grants": projection.get("material_grants") or [],
        "inventory": projection.get("material_inventory"),
    }
    motivation_choice = {"schema_version": BRIDGE_VERSION, "task_id": state["task_id"],
                         "status": _choice_status(motivation),
                         "decisions": motivation,
                         "historical_decisions": [dict(item) for item in projection.get("historical_decisions", [])
                                                  if any(token in str(item.get("decision_type", "")) + str(item.get("decision_id", ""))
                                                         for token in ("motivation", "contribution"))]}
    discovered_figures = _figure_candidates(task, root)
    figure_choice = {"schema_version": BRIDGE_VERSION, "task_id": state["task_id"],
                     "status": _choice_status(figures),
                     "decisions": figures,
                     "historical_decisions": [dict(item) for item in projection.get("historical_decisions", [])
                                              if "figure" in str(item.get("decision_type", "")) + str(item.get("decision_id", ""))],
                     "reference_workspace": projection.get("figure_reference_workspace") or {},
                     "candidate_files": [_safe_artifact(i) for i in (projection.get("artifacts") or [])
                                         if isinstance(i, Mapping) and (i.get("artifact_type") or "").startswith("figure")]
                     + discovered_figures}
    delivery = {
        "schema_version": BRIDGE_VERSION, "task_id": state["task_id"],
        "manifest": projection.get("delivery_manifest") or {},
        "artifacts": [_safe_artifact(i) for i in (projection.get("artifacts") or []) if isinstance(i, Mapping)],
        "runner_delivery_package": _safe_artifact(projection["runner_delivery_package"])
        if isinstance(projection.get("runner_delivery_package"), Mapping) else None,
        "package_directory": str((root / "paper").resolve()),
    }
    payloads = {
        "00_task_state.json": state, "01_configuration.json": configuration,
        "02_materials.json": materials, "03_motivation_choice.json": motivation_choice,
        "04_figure_choice.json": figure_choice, "05_review_feedback.json": review,
        "06_delivery_manifest.json": delivery,
    }
    # Write the state marker last. Readers can compare task_version across
    # files and refresh the same task if they caught an in-progress export.
    for name, payload in sorted(payloads.items(), key=lambda item: item[0] == "00_task_state.json"):
        payload["task_version"] = projection.get("task_version")
        _atomic(bridge / name, _json(payload))
        files[name] = {"name": name, "path": str(bridge / name), "kind": "json"}
    _atomic(bridge / "00_task_state.md", _md("PaperSpine task state", state))
    _atomic(bridge / "README.md", "# PaperSpine workflow files\n\n"
            "These files are a derived handoff for the host Agent and Web UI.\n"
            "Continue the original PaperSpine Skill workflow; do not edit state manually.\n"
            "User choices and review feedback are written here by the Web surface.\n")
    for name in ("00_task_state.md", "README.md"):
        files[name] = {"name": name, "path": str(bridge / name), "kind": "markdown"}
    # Public host work belongs to the task paper directory. Retained Runner
    # artifacts keep their own historical download links, not the current folder.
    package_dir = (root / "paper").resolve()
    return {"directory": str(bridge), "package_directory": str(package_dir),
            "web_path": f"/?task_id={state['task_id']}",
            "files": list(files.values()), "figure_candidates": discovered_figures,
            "current_decision_phase": current_decision_phase,
            "stage": stage, "updated_at": now}


def list_bridge_files(workspace_root: str | Path) -> list[dict[str, Any]]:
    bridge = (Path(workspace_root).resolve() / "paper" / "workflow").resolve()
    if not bridge.is_dir():
        return []
    return [{"name": p.name, "path": str(p), "kind": "markdown" if p.suffix == ".md" else "json",
             "size_bytes": p.stat().st_size} for p in sorted(bridge.iterdir())
            if p.is_file() and p.suffix in {".json", ".md"}]
