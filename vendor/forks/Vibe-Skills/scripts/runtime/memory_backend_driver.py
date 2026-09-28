from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STOP_TOKENS = {
    "approved",
    "about",
    "after",
    "along",
    "and",
    "around",
    "asks",
    "because",
    "before",
    "between",
    "codex",
    "context",
    "continuity",
    "debug",
    "decision",
    "dependencies",
    "dependency",
    "evidence",
    "execution",
    "follow-up",
    "for",
    "from",
    "graph",
    "implementation",
    "into",
    "keep",
    "next",
    "onto",
    "over",
    "plan",
    "planner",
    "planning",
    "preserving",
    "prior",
    "prepare",
    "recall",
    "relationship",
    "retain",
    "review",
    "runtime",
    "step",
    "than",
    "that",
    "their",
    "them",
    "then",
    "there",
    "these",
    "the",
    "they",
    "this",
    "those",
    "through",
    "under",
    "until",
    "user",
    "vibe",
    "vibeskills",
    "what",
    "when",
    "where",
    "which",
    "while",
    "whose",
    "with",
    "within",
    "without",
    "would",
    "were",
    "your",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    content = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_/-]{3,}", text.lower())
        if token and token not in STOP_TOKENS
    }


def score_record(query: str, record: dict[str, Any]) -> int:
    query_tokens = tokenize(query)
    haystack = " ".join(
        [
            str(record.get("summary") or ""),
            " ".join(str(v) for v in record.get("keywords") or []),
            " ".join(str(v) for v in record.get("items") or []),
            " ".join(str(v) for v in record.get("evidence_paths") or []),
            str(record.get("relation") or ""),
            str(record.get("source") or ""),
            str(record.get("target") or ""),
        ]
    )
    return len(query_tokens & tokenize(haystack))


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = str(row.get("record_id") or "")
        if not row_id:
            row_id = hashlib.sha256(json.dumps(row, sort_keys=True).encode("utf-8")).hexdigest()[:16]
            row["record_id"] = row_id
        by_id[row_id] = row
    return list(by_id.values())


def read_ranked_rows(
    path: Path,
    *,
    project_key: str | None,
    query: str,
    top_k: int,
    filter_kind: str | None = None,
) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if project_key and str(row.get("project_key") or "") != project_key:
            continue
        if filter_kind and str(row.get("kind") or "") != filter_kind:
            continue
        row = dict(row)
        row["_score"] = score_record(query, row)
        filtered.append(row)
    filtered.sort(key=lambda row: (row["_score"], str(row.get("updated_at") or row.get("generated_at") or "")), reverse=True)
    return filtered[:top_k]


def write_response(
    response_path: Path,
    *,
    ok: bool,
    status: str,
    lane: str,
    store_path: Path,
    project_key: str | None,
    project_key_source: str | None,
    items: list[str],
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "ok": ok,
        "status": status,
        "lane": lane,
        "store_path": str(store_path),
        "project_key": project_key,
        "project_key_source": project_key_source,
        "item_count": len(items),
        "items": items,
        "generated_at": utc_now(),
    }
    if extra:
        payload.update(extra)
    write_json(response_path, payload)


def serena_read(payload: dict[str, Any], store_path: Path, project_key: str | None) -> tuple[str, list[str]]:
    if not project_key:
        return "deferred_no_project_key", []
    ranked = read_ranked_rows(store_path, project_key=project_key, query=str(payload.get("task") or ""), top_k=int(payload.get("top_k") or 2))
    items = [
        f"Serena decision: {row.get('summary')} (evidence: {', '.join(row.get('evidence_paths') or [])})"
        for row in ranked
        if row.get("_score", 0) > 0 or len(ranked) <= int(payload.get("top_k") or 2)
    ]
    return ("backend_read" if items else "backend_read_empty"), items


def serena_write(payload: dict[str, Any], store_path: Path, project_key: str | None) -> tuple[str, list[str]]:
    decisions = [dict(item) for item in payload.get("decisions") or [] if isinstance(item, dict)]
    if not project_key or not decisions:
        return "guarded_no_write", []
    rows = load_jsonl(store_path)
    for decision in decisions:
        record_basis = json.dumps(
            {
                "project_key": project_key,
                "summary": decision.get("summary"),
                "evidence_paths": decision.get("evidence_paths"),
            },
            sort_keys=True,
        )
        rows.append(
            {
                "record_id": hashlib.sha256(record_basis.encode("utf-8")).hexdigest()[:16],
                "project_key": project_key,
                "kind": "architecture_decision",
                "signal_type": "architecture_decision",
                "summary": str(decision.get("summary") or "").strip(),
                "evidence_paths": [str(v) for v in decision.get("evidence_paths") or [] if str(v).strip()],
                "keywords": [str(v) for v in decision.get("keywords") or [] if str(v).strip()],
                "updated_at": utc_now(),
            }
        )
    write_jsonl(store_path, dedupe_rows(rows))
    items = [f"Persisted Serena decision: {decision.get('summary')}" for decision in decisions]
    return "backend_write", items


def ruflo_read(payload: dict[str, Any], store_path: Path, project_key: str | None) -> tuple[str, list[str]]:
    ranked = read_ranked_rows(
        store_path,
        project_key=project_key,
        query=str(payload.get("task") or ""),
        top_k=int(payload.get("top_k") or 2),
        filter_kind="handoff_card",
    )
    items = [
        f"ruflo handoff: {row.get('summary')} (scope: {row.get('scope')})"
        for row in ranked
        if row.get("_score", 0) > 0 or len(ranked) <= int(payload.get("top_k") or 2)
    ]
    return ("backend_read" if items else "backend_read_empty"), items


def ruflo_write(payload: dict[str, Any], store_path: Path, project_key: str | None) -> tuple[str, list[str]]:
    cards = [dict(item) for item in payload.get("cards") or [] if isinstance(item, dict)]
    if not cards:
        return "guarded_no_write", []
    rows = load_jsonl(store_path)
    for card in cards:
        record_basis = json.dumps(
            {
                "project_key": project_key,
                "run_id": payload.get("run_id"),
                "summary": card.get("summary"),
                "scope": card.get("scope"),
            },
            sort_keys=True,
        )
        rows.append(
            {
                "record_id": hashlib.sha256(record_basis.encode("utf-8")).hexdigest()[:16],
                "project_key": project_key,
                "kind": "handoff_card",
                "scope": str(card.get("scope") or "xl"),
                "summary": str(card.get("summary") or "").strip(),
                "items": [str(v) for v in card.get("items") or [] if str(v).strip()],
                "evidence_paths": [str(v) for v in card.get("evidence_paths") or [] if str(v).strip()],
                "keywords": [str(v) for v in card.get("keywords") or [] if str(v).strip()],
                "run_id": str(payload.get("run_id") or ""),
                "updated_at": utc_now(),
            }
        )
    write_jsonl(store_path, dedupe_rows(rows))
    items = [f"Persisted ruflo handoff card: {card.get('summary')}" for card in cards]
    return "backend_write", items


def cognee_read(payload: dict[str, Any], store_path: Path, project_key: str | None) -> tuple[str, list[str]]:
    ranked = read_ranked_rows(
        store_path,
        project_key=project_key,
        query=str(payload.get("task") or ""),
        top_k=int(payload.get("top_k") or 1),
        filter_kind="entity_relation_ingest",
    )
    items = [
        f"Cognee relation: {row.get('source')} {row.get('relation')} {row.get('target')}"
        for row in ranked
        if row.get("_score", 0) > 0 or len(ranked) <= int(payload.get("top_k") or 1)
    ]
    return ("backend_read" if items else "backend_read_empty"), items


def cognee_write(payload: dict[str, Any], store_path: Path, project_key: str | None) -> tuple[str, list[str]]:
    relations = [dict(item) for item in payload.get("relations") or [] if isinstance(item, dict)]
    if not relations:
        return "guarded_no_write", []
    rows = load_jsonl(store_path)
    for relation in relations:
        record_basis = json.dumps(
            {
                "project_key": project_key,
                "source": relation.get("source"),
                "relation": relation.get("relation"),
                "target": relation.get("target"),
            },
            sort_keys=True,
        )
        rows.append(
            {
                "record_id": hashlib.sha256(record_basis.encode("utf-8")).hexdigest()[:16],
                "project_key": project_key,
                "kind": "entity_relation_ingest",
                "signal_type": "entity_relation_ingest",
                "source": str(relation.get("source") or "").strip(),
                "relation": str(relation.get("relation") or "").strip(),
                "target": str(relation.get("target") or "").strip(),
                "evidence_paths": [str(v) for v in relation.get("evidence_paths") or [] if str(v).strip()],
                "keywords": [str(v) for v in relation.get("keywords") or [] if str(v).strip()],
                "updated_at": utc_now(),
            }
        )
    write_jsonl(store_path, dedupe_rows(rows))
    items = [f"Persisted Cognee relation: {relation.get('source')} {relation.get('relation')} {relation.get('target')}" for relation in relations]
    return "backend_write", items


def invoke_workspace_shell(args: argparse.Namespace) -> int:
    module_path = Path(__file__).with_name("workspace_memory_driver.py")
    if not module_path.exists():
        return 1

    spec = importlib.util.spec_from_file_location("workspace_memory_driver", module_path)
    if spec is None or spec.loader is None:
        return 1
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return int(
        module.execute(
            lane=args.lane,
            action=args.action,
            repo_root=Path(args.repo_root),
            payload_path=Path(args.payload_path),
            response_path=Path(args.response_path),
            project_key=args.project_key,
            driver_mode="compatibility_shell",
        )
    )


def invoke_legacy_shell(args: argparse.Namespace) -> int:
    payload = load_json(Path(args.payload_path))
    response_path = Path(args.response_path)
    store_path = Path(args.store_path)
    ensure_parent(store_path)

    project_key = args.project_key
    project_key_source = payload.get("project_key_source")

    handlers = {
        ("serena", "read"): serena_read,
        ("serena", "write"): serena_write,
        ("ruflo", "read"): ruflo_read,
        ("ruflo", "write"): ruflo_write,
        ("cognee", "read"): cognee_read,
        ("cognee", "write"): cognee_write,
    }
    status, items = handlers[(args.lane, args.action)](payload, store_path, project_key)
    write_response(
        response_path,
        ok=status.startswith("backend_"),
        status=status,
        lane=args.lane,
        store_path=store_path,
        project_key=project_key,
        project_key_source=str(project_key_source) if project_key_source else None,
        items=items,
        extra={"driver_mode": "legacy_lane_store"},
    )
    return 0


def fail_hard(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", required=True, choices=["serena", "ruflo", "cognee"])
    parser.add_argument("--action", required=True, choices=["read", "write"])
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--session-root", required=True)
    parser.add_argument("--store-path", required=True)
    parser.add_argument("--payload-path", required=True)
    parser.add_argument("--response-path", required=True)
    parser.add_argument("--project-key")
    parser.add_argument("--driver-mode")
    args = parser.parse_args()

    requested_driver_mode = (args.driver_mode or "").strip().lower()
    configured_driver_mode = (os.getenv("VIBE_MEMORY_BACKEND_DRIVER_MODE") or "workspace").strip().lower()

    if requested_driver_mode in {"legacy", "legacy_lane_store"}:
        return fail_hard("legacy memory backend mode is forbidden; workspace broker is required")

    if configured_driver_mode in {"legacy", "legacy_lane_store"}:
        return fail_hard("legacy memory backend mode is forbidden; workspace broker is required")

    workspace_status = invoke_workspace_shell(args)
    if workspace_status == 0:
        return 0

    return fail_hard(f"workspace memory broker invocation failed with exit code {workspace_status}")


if __name__ == "__main__":
    raise SystemExit(main())
