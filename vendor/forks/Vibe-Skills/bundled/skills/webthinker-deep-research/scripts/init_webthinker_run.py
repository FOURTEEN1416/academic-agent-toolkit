#!/usr/bin/env python3
"""
Initialize an auditable "deep research run" folder.

This is intentionally minimal (stdlib only). It does NOT perform web search.
It scaffolds a workspace so the agent/user can:
  - keep sources.json up to date
  - append trace.jsonl for every action
  - draft report.md continuously (think-search-and-draft)
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:64] or "topic"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a WebThinker-style deep research run folder.")
    parser.add_argument("--topic", required=True, help="Research topic/question (used for naming + header).")
    parser.add_argument(
        "--out",
        default="outputs/webthinker",
        help="Base output directory (default: outputs/webthinker).",
    )
    args = parser.parse_args()

    now = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(args.topic)
    run_dir = Path(args.out) / f"{now}-{slug}"
    run_dir.mkdir(parents=True, exist_ok=False)

    (run_dir / "trace.jsonl").write_text("", encoding="utf-8")
    (run_dir / "sources.json").write_text(json.dumps({"topic": args.topic, "sources": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    notes = f"""# Notes

- topic: {args.topic}
- created_at: {now}

## Working notes

"""
    (run_dir / "notes.md").write_text(notes, encoding="utf-8")

    report = f"""# Deep Research Report

**Topic:** {args.topic}
**Created:** {now}

## Executive summary

- (Write 3–6 bullets that can be validated by sources.json)

## Key questions

1. …

## Findings (evidence-linked)

### Finding 1

- Claim:
- Evidence: (link to sources.json entries)
- Confidence:

## Implications / trade-offs

## Next steps (verification plan)

- (Concrete next experiments / checks / code probes)

## Sources

See `sources.json`.
"""
    (run_dir / "report.md").write_text(report, encoding="utf-8")

    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

