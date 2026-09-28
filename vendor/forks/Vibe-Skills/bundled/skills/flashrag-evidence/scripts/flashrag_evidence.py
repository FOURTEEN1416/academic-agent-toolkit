#!/usr/bin/env python3
"""
FlashRAG Evidence (Lite)

Goal:
  Provide a lightweight, dependency-free way to retrieve citeable evidence
  from local VCO/vibe docs + config + skills metadata.

Design constraints:
  - Stdlib-first (no pip deps required)
  - Optional: if `bm25s` is installed, can use a faster BM25 backend
  - Works on Windows paths (including non-ASCII)
  - Outputs path + 1-based line anchors
  - "Good enough" lexical BM25 for short queries
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class Chunk:
    path: Path
    start_line: int  # 1-based
    text: str


def _default_roots() -> list[Path]:
    home = Path.home()
    codex_root = home / ".codex"
    roots: list[Path] = []

    vibe_root = codex_root / "skills" / "vibe"
    skills_root = codex_root / "skills"

    if vibe_root.exists():
        roots.append(vibe_root)
    if skills_root.exists():
        roots.append(skills_root)

    # Optional project-local VCO skeleton (if present in current workspace).
    cwd = Path.cwd()
    local_candidates = [
        cwd / "my_righthand_man" / "vco",
        cwd / "vco",
    ]
    for candidate in local_candidates:
        if candidate.exists():
            roots.append(candidate)

    # De-duplicate while preserving order.
    seen: set[Path] = set()
    deduped: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def _iter_files(
    roots: Sequence[Path],
    allowed_suffixes: set[str],
    max_files: int,
    exclude_dir_names: set[str],
) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("*"):
                if len(files) >= max_files:
                    return files
                try:
                    if not path.is_file():
                        continue
                except OSError:
                    continue

                # Skip excluded directories by name (quick check on parts).
                if any(part in exclude_dir_names for part in path.parts):
                    continue

                if path.name == "SKILL.md":
                    files.append(path)
                    continue
                suffix = path.suffix.lower()
                if suffix in allowed_suffixes:
                    files.append(path)
        except Exception:
            # Root might contain unreadable entries; be resilient.
            continue
    return files


def _read_text(path: Path, max_chars: int) -> str:
    # Robust UTF-8 read with replacement; limit total chars to avoid RAM blowups.
    try:
        data = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        data = path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        data = path.read_text(encoding="utf-8", errors="replace")

    if max_chars > 0 and len(data) > max_chars:
        return data[:max_chars]
    return data


def _chunk_by_lines(
    path: Path, text: str, lines_per_chunk: int, overlap: int
) -> list[Chunk]:
    if lines_per_chunk <= 0:
        return []
    overlap = max(0, min(overlap, max(0, lines_per_chunk - 1)))

    lines = text.splitlines()
    chunks: list[Chunk] = []
    step = max(1, lines_per_chunk - overlap)
    for start in range(0, len(lines), step):
        end = min(len(lines), start + lines_per_chunk)
        chunk_lines = lines[start:end]
        if not chunk_lines:
            continue
        chunk_text = "\n".join(chunk_lines).strip()
        if not chunk_text:
            continue
        chunks.append(
            Chunk(
                path=path,
                start_line=start + 1,
                text=chunk_text,
            )
        )
        if end >= len(lines):
            break
    return chunks


_ASCII_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    lower = text.lower()

    ascii_tokens = _ASCII_WORD_RE.findall(lower)
    cjk_chars = _CJK_RE.findall(lower)

    # Add CJK bigrams for better matching on Chinese phrases.
    cjk_bigrams: list[str] = []
    if len(cjk_chars) >= 2:
        for i in range(len(cjk_chars) - 1):
            cjk_bigrams.append(cjk_chars[i] + cjk_chars[i + 1])

    return ascii_tokens + cjk_chars + cjk_bigrams


def _bm25_scores(
    query_tokens: Sequence[str],
    doc_tokens_list: Sequence[list[str]],
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    # BM25 over tokenized docs (chunks).
    n_docs = len(doc_tokens_list)
    if n_docs == 0:
        return []

    # Document frequencies.
    df: dict[str, int] = {}
    doc_lens: list[int] = []
    for tokens in doc_tokens_list:
        doc_lens.append(len(tokens))
        seen = set(tokens)
        for token in seen:
            df[token] = df.get(token, 0) + 1

    avgdl = sum(doc_lens) / max(1, n_docs)

    # Precompute IDF for query terms.
    idf: dict[str, float] = {}
    for token in set(query_tokens):
        freq = df.get(token, 0)
        # Standard BM25+ style smoothing to avoid negative idf for very common terms.
        idf[token] = math.log(1.0 + (n_docs - freq + 0.5) / (freq + 0.5))

    # Score each doc.
    scores: list[float] = [0.0] * n_docs
    for i, tokens in enumerate(doc_tokens_list):
        if not tokens:
            continue
        dl = doc_lens[i]
        norm = k1 * (1.0 - b + b * (dl / avgdl))
        # Term frequency within doc.
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for q in query_tokens:
            if q not in idf:
                continue
            f = tf.get(q, 0)
            if f == 0:
                continue
            score += idf[q] * (f * (k1 + 1.0)) / (f + norm)
        scores[i] = score
    return scores


def _bm25s_retrieve_topk(
    query_tokens: Sequence[str],
    doc_tokens_list: Sequence[list[str]],
    topk: int,
) -> list[Tuple[float, int]] | None:
    """
    Optional fast BM25 backend using `bm25s` (used by FlashRAG).

    Returns:
      - list of (score, doc_index), sorted by score desc
      - None if bm25s is unavailable or fails
    """
    try:
        import bm25s  # type: ignore
    except Exception:
        return None

    try:
        bm25 = bm25s.BM25()
        bm25.index(list(doc_tokens_list), show_progress=False)
        idx, scores = bm25.retrieve([list(query_tokens)], k=max(1, int(topk)), show_progress=False)

        idx0 = idx[0].tolist()
        scores0 = scores[0].tolist()

        results: list[Tuple[float, int]] = []
        for i, s in zip(idx0, scores0):
            s = float(s)
            if s <= 0:
                continue
            results.append((s, int(i)))
        results.sort(key=lambda x: x[0], reverse=True)
        return results
    except Exception:
        # Be resilient: never fail the whole script because bm25s is broken/misconfigured.
        return None


def _format_result_snippet(text: str, max_chars: int) -> str:
    snippet = " ".join(text.strip().split())
    if max_chars > 0 and len(snippet) > max_chars:
        return snippet[: max_chars - 1] + "…"
    return snippet


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="FlashRAG Evidence (Lite) — local citeable snippet retrieval.")
    parser.add_argument("--query", required=True, help="Search query (short, concrete).")
    parser.add_argument("--topk", type=int, default=8, help="Top K chunks to return.")
    parser.add_argument(
        "--roots",
        nargs="*",
        default=None,
        help="Optional root directories to search. Defaults to ~/.codex/skills/vibe + ~/.codex/skills (+ local vco skeleton if present).",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=4000,
        help="Safety limit for how many files to scan.",
    )
    parser.add_argument(
        "--max-file-chars",
        type=int,
        default=200_000,
        help="Safety limit for how many chars to read per file (0=unlimited).",
    )
    parser.add_argument("--lines-per-chunk", type=int, default=18)
    parser.add_argument("--overlap", type=int, default=4)
    parser.add_argument("--snippet-chars", type=int, default=360)
    parser.add_argument(
        "--engine",
        choices=("auto", "lite", "bm25s"),
        default="auto",
        help="Retrieval engine. auto=prefer bm25s if installed; lite=stdlib BM25; bm25s=force bm25s backend.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "jsonl"),
        default="markdown",
        help="Output format.",
    )
    args = parser.parse_args(list(argv))

    query = args.query.strip()
    if not query:
        print("Empty query.", file=sys.stderr)
        return 2

    roots = [Path(r).expanduser() for r in (args.roots or [])] if args.roots is not None else _default_roots()
    allowed_suffixes = {".md", ".json", ".ps1", ".txt", ".yml", ".yaml"}
    exclude_dir_names = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

    files = _iter_files(
        roots=roots,
        allowed_suffixes=allowed_suffixes,
        max_files=max(1, int(args.max_files)),
        exclude_dir_names=exclude_dir_names,
    )

    chunks: list[Chunk] = []
    for path in files:
        try:
            text = _read_text(path, max_chars=int(args.max_file_chars))
        except Exception:
            continue
        chunks.extend(_chunk_by_lines(path, text, lines_per_chunk=int(args.lines_per_chunk), overlap=int(args.overlap)))

    query_tokens = _tokenize(query)
    if not query_tokens:
        print("Query produced no tokens.", file=sys.stderr)
        return 2

    doc_tokens_list = [_tokenize(c.text) for c in chunks]
    topk = max(1, int(args.topk))

    ranked: list[Tuple[float, Chunk]] = []
    engine = args.engine
    used_bm25s = False
    if engine in ("auto", "bm25s"):
        bm25s_results = _bm25s_retrieve_topk(query_tokens, doc_tokens_list, topk=topk)
        if bm25s_results is not None:
            used_bm25s = True
            for score, doc_idx in bm25s_results:
                if 0 <= doc_idx < len(chunks):
                    ranked.append((score, chunks[doc_idx]))
        elif engine == "bm25s":
            print("bm25s requested but unavailable; falling back to lite BM25.", file=sys.stderr)

    if not ranked:
        scores = _bm25_scores(query_tokens, doc_tokens_list)
        for score, chunk in zip(scores, chunks):
            if score <= 0:
                continue
            ranked.append((score, chunk))

    ranked.sort(key=lambda x: x[0], reverse=True)
    top = ranked[:topk]

    if args.format == "jsonl":
        import json  # stdlib

        for score, chunk in top:
            print(
                json.dumps(
                    {
                        "score": round(float(score), 6),
                        "path": str(chunk.path),
                        "line": int(chunk.start_line),
                        "snippet": _format_result_snippet(chunk.text, max_chars=int(args.snippet_chars)),
                    },
                    ensure_ascii=False,
                )
            )
        return 0

    # markdown
    engine_used = "bm25s" if used_bm25s else "lite"
    print(f"# FlashRAG Evidence ({engine_used})\n")
    print(f"- query: `{query}`")
    print(f"- roots: {len(roots)}")
    for root in roots[:6]:
        print(f"  - `{root}`")
    if len(roots) > 6:
        print(f"  - … ({len(roots) - 6} more)")
    print(f"- files_scanned: {len(files)}")
    print(f"- chunks_indexed: {len(chunks)}")
    print(f"- hits: {len(top)}\n")

    if not top:
        print("No hits. Try:")
        print("- broaden roots via `--roots`")
        print("- increase `--max-files` or `--topk`")
        print("- use a more specific keyword (exact term from the doc/config)")
        return 0

    for idx, (score, chunk) in enumerate(top, start=1):
        anchor = f"{chunk.path}:{chunk.start_line}"
        snippet = _format_result_snippet(chunk.text, max_chars=int(args.snippet_chars))
        print(f"## {idx}. score={score:.4f}")
        print(f"- source: `{anchor}`")
        print(f"- snippet: {snippet}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
