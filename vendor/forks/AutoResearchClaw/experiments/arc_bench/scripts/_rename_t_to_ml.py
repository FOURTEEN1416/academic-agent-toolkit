#!/usr/bin/env python3
"""One-shot rename: T01-T25 → ML01-ML25, move to config/ml/.

Usage:
    python experiments/arc_bench/scripts/_rename_t_to_ml.py

Idempotent — safe to re-run.  Does:
  1. Create config/ml/{manifests,rubrics}/
  2. For each T01-T25:
     - read manifest, patch `id: TNN` → `id: MLNN`, patch rubric_path,
       write to config/ml/manifests/MLNN.yaml
     - read rubric JSON, walk every node, rewrite `id` from `tNN-*` → `mlNN-*`,
       write to config/ml/rubrics/MLNN.json
  3. Write config/ml/topics.yaml (port of config/topics.yaml with renamed IDs)
  4. After successful copy, remove the old files (hard cutover).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent  # experiments/arc_bench
CONFIG = ROOT / "config"
OLD_MANIFESTS = CONFIG / "manifests"
OLD_RUBRICS = CONFIG / "rubrics"
OLD_TOPICS = CONFIG / "topics.yaml"
NEW_DIR = CONFIG / "ml"
NEW_MANIFESTS = NEW_DIR / "manifests"
NEW_RUBRICS = NEW_DIR / "rubrics"
NEW_TOPICS = NEW_DIR / "topics.yaml"


def _t_to_ml(tid: str) -> str:
    """T01 → ML01; preserve casing prefix."""
    m = re.match(r"^[Tt](\d+)$", tid)
    if not m:
        return tid
    return f"ML{m.group(1)}"


def patch_manifest(text: str, old_id: str, new_id: str) -> str:
    """Patch a manifest YAML text in place."""
    text = re.sub(rf"^id:\s*{re.escape(old_id)}\b", f"id: {new_id}", text, flags=re.MULTILINE)
    # rubric_path can sit in various forms; rewrite both old layout AND
    # already-canonical paths to the new location.
    text = re.sub(
        rf'rubric_path:\s*"experiments/arc_bench/rubrics/{re.escape(old_id)}\.json"',
        f'rubric_path: "experiments/arc_bench/config/ml/rubrics/{new_id}.json"',
        text,
    )
    text = re.sub(
        rf'rubric_path:\s*"experiments/arc_bench/config/rubrics/{re.escape(old_id)}\.json"',
        f'rubric_path: "experiments/arc_bench/config/ml/rubrics/{new_id}.json"',
        text,
    )
    return text


def patch_rubric(doc: dict, old_pref: str, new_pref: str) -> dict:
    """Walk the rubric tree and replace IDs starting with old_pref (e.g. 't01-')
    with new_pref (e.g. 'ml01-')."""
    def walk(node: dict) -> None:
        rid = node.get("id", "")
        if isinstance(rid, str) and rid.startswith(old_pref):
            node["id"] = new_pref + rid[len(old_pref):]
        for c in node.get("sub_tasks") or []:
            walk(c)
    walk(doc)
    return doc


def main() -> int:
    if not OLD_MANIFESTS.is_dir():
        print(f"  nothing to rename — {OLD_MANIFESTS} not found", file=sys.stderr)
        return 0

    NEW_MANIFESTS.mkdir(parents=True, exist_ok=True)
    NEW_RUBRICS.mkdir(parents=True, exist_ok=True)

    moves: list[tuple[Path, Path]] = []  # (old, new) tuples for cleanup at end

    t_files = sorted(OLD_MANIFESTS.glob("T*.yaml"))
    print(f"  found {len(t_files)} T-manifests to rename")

    for old_man in t_files:
        old_id = old_man.stem  # T01
        new_id = _t_to_ml(old_id)  # ML01
        new_man = NEW_MANIFESTS / f"{new_id}.yaml"

        text = old_man.read_text(encoding="utf-8")
        text = patch_manifest(text, old_id, new_id)
        new_man.write_text(text, encoding="utf-8")
        moves.append((old_man, new_man))

        # Matching rubric
        old_rub = OLD_RUBRICS / f"{old_id}.json"
        if old_rub.is_file():
            doc = json.loads(old_rub.read_text(encoding="utf-8"))
            old_pref = old_id.lower() + "-"   # 't01-'
            new_pref = new_id.lower() + "-"   # 'ml01-'
            doc = patch_rubric(doc, old_pref, new_pref)
            new_rub = NEW_RUBRICS / f"{new_id}.json"
            new_rub.write_text(json.dumps(doc, indent=4) + "\n", encoding="utf-8")
            moves.append((old_rub, new_rub))

        print(f"    {old_id} → {new_id}")

    # Topics registry
    if OLD_TOPICS.is_file():
        data = yaml.safe_load(OLD_TOPICS.read_text(encoding="utf-8"))
        for t in data.get("topics", []):
            t["id"] = _t_to_ml(t.get("id", ""))
        # Preserve header comment
        header_lines = []
        for line in OLD_TOPICS.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                header_lines.append(line)
            else:
                break
        header = "\n".join(header_lines) + "\n\n"
        body = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        # Update header to mention ML naming
        body = body.replace("T01-T10", "ML01-ML10").replace("T11-T25", "ML11-ML25")
        header = header.replace("T01-T10", "ML01-ML10").replace("T11-T25", "ML11-ML25")
        header = header.replace("ARC-Bench — 25", "ARC-Bench ML — 25")
        NEW_TOPICS.write_text(header + body, encoding="utf-8")
        moves.append((OLD_TOPICS, NEW_TOPICS))
        print(f"    topics.yaml → ml/topics.yaml")

    # Hard cutover: remove old files
    for old, _ in moves:
        try:
            old.unlink()
        except OSError as exc:
            print(f"    WARN could not unlink {old}: {exc}", file=sys.stderr)

    # Remove empty old dirs
    for d in (OLD_MANIFESTS, OLD_RUBRICS):
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
                print(f"    removed empty {d}")
        except OSError:
            pass

    print(f"\n  done — {len(moves)} files moved + patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
