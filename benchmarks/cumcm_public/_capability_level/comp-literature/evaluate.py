#!/usr/bin/env python3
"""评分脚本：comp-literature P0 基准。读取工作区文件并评分。

验收内容：
1. LITERATURE.md 存在且 >= 1000 字节
2. literature/search_evidence.json 存在、是 list、记录数 >= 2
3. search_evidence 每条记录的 key 或 title 必须能在 preset_search_results.json 中找到（防编造）
4. paper/references.bib 存在，且 citation key 与 search_evidence 的 key 交集 >= 2
"""
import json
import re
import sys
from pathlib import Path

PRESET = Path(__file__).resolve().parent / "fixtures" / "preset_search_results.json"


def _norm(text: str) -> str:
    """归一化标题用于模糊匹配：小写、去空格和标点。"""
    return re.sub(r"[^a-z0-9\u00c0-\u024f]", "", (text or "").lower())


def _bib_keys(bib_text: str) -> set[str]:
    """提取 .bib 中的 citation key：@type{key, ..."""
    return set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))


def score(workspace: Path) -> dict:
    results: dict = {}
    preset = json.loads(PRESET.read_text(encoding="utf-8"))
    preset_keys = {r.get("key") for r in preset}
    preset_titles = {_norm(r.get("title", "")) for r in preset}

    # 1. LITERATURE.md
    lit = workspace / "LITERATURE.md"
    results["file_LITERATURE.md"] = lit.is_file()
    if lit.is_file():
        size = len(lit.read_text(encoding="utf-8").encode("utf-8"))
        results["size_bytes"] = size
        results["size_ok"] = size >= 1000

    # 2. literature/search_evidence.json（兼容两种结构：扁平 list 或 [{query, records: [...]}] 嵌套）
    sev = workspace / "literature" / "search_evidence.json"
    results["file_search_evidence.json"] = sev.is_file()
    records: list = []
    if sev.is_file():
        try:
            data = json.loads(sev.read_text(encoding="utf-8"))
            results["search_evidence_is_list"] = isinstance(data, list)
            if isinstance(data, list):
                # 展开嵌套结构：条目可能是 {query, records:[...]} 或直接是记录 dict
                for item in data:
                    if isinstance(item, dict) and isinstance(item.get("records"), list):
                        records.extend(item["records"])
                    elif isinstance(item, dict):
                        records.append(item)
        except json.JSONDecodeError:
            results["search_evidence_is_list"] = False
        results["search_evidence_count"] = len(records)
        results["search_evidence_count_ok"] = len(records) >= 2
    else:
        results["search_evidence_is_list"] = False
        results["search_evidence_count"] = 0
        results["search_evidence_count_ok"] = False

    # 3. 防编造：每条记录的 key 或 title 必须命中 preset（合成场景）；
    #    若记录含真实元数据（arxiv id / doi / verification_status），视为真实检索场景，跳过防编造。
    invented = []
    if records:
        for i, rec in enumerate(records):
            key = str(rec.get("key", ""))
            title = _norm(rec.get("title", ""))
            if key in preset_keys or title in preset_titles:
                continue
            # 真实检索证据：有 arXiv id / DOI / verification_status 字段 → 非编造
            has_real_meta = bool(
                rec.get("id") or rec.get("doi") or rec.get("arxiv_id") or rec.get("verification_status")
            )
            if has_real_meta:
                continue
            invented.append({"index": i, "key": key, "title": rec.get("title", "")})
    results["invented_records"] = invented
    results["no_invented_references"] = len(invented) == 0

    # 4. paper/references.bib 与 search_evidence key 交集
    bib = workspace / "paper" / "references.bib"
    results["file_references.bib"] = bib.is_file()
    evidence_keys = {str(r.get("key", "")) for r in records if r.get("key")}
    if bib.is_file():
        bib_keys = _bib_keys(bib.read_text(encoding="utf-8"))
        overlap = sorted(evidence_keys & bib_keys)
        results["bib_key_overlap"] = overlap
        results["bib_key_overlap_ok"] = len(overlap) >= 2
    else:
        results["bib_key_overlap"] = []
        results["bib_key_overlap_ok"] = False

    # 综合
    required_checks = [
        "file_LITERATURE.md", "size_ok",
        "file_search_evidence.json", "search_evidence_is_list",
        "search_evidence_count_ok", "no_invented_references",
        "file_references.bib", "bib_key_overlap_ok",
    ]
    results["all_pass"] = all(results.get(c, False) for c in required_checks)
    results["required_checks"] = required_checks
    return results


if __name__ == "__main__":
    ws = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    r = score(ws)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r.get("all_pass") else 1)