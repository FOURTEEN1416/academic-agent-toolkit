#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence


sys.dont_write_bytecode = True
CONTRACTS_SRC = Path(__file__).resolve().parents[2] / "packages" / "contracts" / "src"
if str(CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_SRC))

from vgo_contracts import (  # noqa: E402
    build_live_document_census,
    load_live_governance_contract,
    validate_live_document_changes,
    validate_live_document_registry_transition,
    validate_live_document_workspace,
)


CENSUS_MODES = ("migration-report", "strict")


def collect_added_paths(
    repo_root: str | Path,
    base_ref: str,
    head_ref: str = "HEAD",
) -> list[str]:
    root = Path(repo_root).resolve()
    completed = subprocess.run(
        [
            "git",
            "diff",
            "--no-renames",
            "--diff-filter=A",
            "--name-only",
            "-z",
            f"{base_ref}...{head_ref}",
            "--",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"unable to collect added paths from git diff: {detail}")
    return [
        raw_path.decode("utf-8", errors="strict").replace("\\", "/")
        for raw_path in completed.stdout.split(b"\0")
        if raw_path
    ]


def collect_tracked_markdown_paths(repo_root: str | Path) -> list[str]:
    root = Path(repo_root).resolve()
    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"unable to collect tracked paths from git: {detail}")
    paths = []
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="strict").replace("\\", "/")
        # `git ls-files --cached` includes index entries removed from the
        # working tree until the deletion is staged. Census must describe the
        # workspace that gates will run against, so omit absent paths.
        if Path(root, *path.split("/")).is_file():
            paths.append(path)
    return sorted(
        (path for path in paths if path.casefold().endswith(".md")),
        key=lambda path: (path.casefold(), path),
    )


def collect_previous_registered_paths(
    repo_root: str | Path,
    base_ref: str,
) -> list[str]:
    root = Path(repo_root).resolve()
    completed = subprocess.run(
        [
            "git",
            "show",
            f"{base_ref}:config/live-document-contract.json",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"unable to read the baseline live-document contract: {detail}")
    payload = json.loads(completed.stdout.decode("utf-8-sig"))
    documents = payload.get("documents") if isinstance(payload, dict) else None
    if not isinstance(documents, list):
        raise ValueError("baseline live-document contract must define documents")
    paths = [
        str(document.get("path") or "").strip()
        for document in documents
        if isinstance(document, dict)
    ]
    if len(paths) != len(documents) or any(not path for path in paths):
        raise ValueError("baseline live-document entries must define paths")
    return paths


def evaluate(
    repo_root: str | Path,
    added_paths: Sequence[str],
    previous_registered_paths: Sequence[str] = (),
    *,
    census_mode: str | None = None,
    tracked_markdown_paths: Sequence[str] | None = None,
) -> dict[str, object]:
    if census_mode is not None and census_mode not in CENSUS_MODES:
        raise ValueError(f"unsupported census mode: {census_mode}")
    if census_mode is None and tracked_markdown_paths is not None:
        raise ValueError("tracked Markdown paths require an explicit census mode")
    root = Path(repo_root).resolve()
    contract = load_live_governance_contract(root)
    validated_documents = validate_live_document_workspace(contract, root)
    validated_additions = validate_live_document_changes(
        contract,
        list(added_paths),
    )
    removed_documents = validate_live_document_registry_transition(
        contract,
        list(previous_registered_paths),
        root,
    )
    result: dict[str, object] = {
        "gate": "live-document-contract",
        "result": "PASS",
        "contract_path": "config/live-document-contract.json",
        "registered_document_count": len(validated_documents),
        "document_budget": contract.max_live_documents,
        "validated_added_documents": validated_additions,
        "checked_added_paths": list(added_paths),
        "removed_registered_documents": removed_documents,
    }
    if census_mode is not None:
        if tracked_markdown_paths is None:
            raise ValueError("census mode requires tracked Markdown paths")
        census = build_live_document_census(
            contract,
            list(tracked_markdown_paths),
        )
        result["census_mode"] = census_mode
        result["census"] = census.model_dump()
        if census_mode == "strict" and census.unregistered_count:
            suffix = "document" if census.unregistered_count == 1 else "documents"
            result["result"] = "FAIL"
            result["failure"] = (
                "strict census found "
                f"{census.unregistered_count} unregistered governed Markdown {suffix}"
            )
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the executable live-document contract",
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--added-path", action="append", default=[])
    parser.add_argument("--census-mode", choices=CENSUS_MODES)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        added_paths = list(args.added_path)
        previous_registered_paths: list[str] = []
        if args.base_ref:
            added_paths.extend(
                collect_added_paths(args.repo_root, args.base_ref, args.head_ref)
            )
            previous_registered_paths = collect_previous_registered_paths(
                args.repo_root,
                args.base_ref,
            )
        tracked_markdown_paths = (
            collect_tracked_markdown_paths(args.repo_root)
            if args.census_mode
            else None
        )
        result = evaluate(
            args.repo_root,
            list(dict.fromkeys(added_paths)),
            previous_registered_paths,
            census_mode=args.census_mode,
            tracked_markdown_paths=tracked_markdown_paths,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
