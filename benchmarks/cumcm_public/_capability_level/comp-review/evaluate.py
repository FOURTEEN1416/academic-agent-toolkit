#!/usr/bin/env python3
"""评分脚本：comp-review P0 基准。检查审稿报告能否检出预埋缺陷（缺陷检出率）。"""
import json
import sys
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def score(workspace: Path) -> dict:
    results = {}
    # 预埋缺陷清单
    manifest = json.loads((FIXTURES_DIR / "defect_manifest.json").read_text(encoding="utf-8"))
    defects = manifest["defects"]

    # 审稿产物
    review_md = workspace / "COMP_REVIEW.md"
    verdict = workspace / "COMP_REVIEW_VERDICT.json"

    results["file_COMP_REVIEW.md"] = review_md.exists()
    results["file_COMP_REVIEW_VERDICT.json"] = verdict.exists()
    if not review_md.exists():
        results.update({
            "detection_rate": 0.0, "detection_ok": False,
            "verdict_json": False, "evidence_based": False,
            "size_bytes": 0, "size_ok": False, "all_pass": False,
            "detected": [], "missing": [d["id"] for d in defects],
        })
        return results

    content = review_md.read_text(encoding="utf-8", errors="ignore")
    results["size_bytes"] = len(content.encode("utf-8"))
    results["size_ok"] = results["size_bytes"] >= 500

    # 检出判定：每类缺陷的关键词命中（宽松匹配，命中任一 hint 即算检出）
    detected = []
    for d in defects:
        hit = any(hint in content for hint in d["keyword_hint"])
        if hit:
            detected.append(d["id"])
    results["detected"] = detected
    results["missing"] = [d["id"] for d in defects if d["id"] not in detected]
    results["detection_rate"] = len(detected) / len(defects)
    results["detection_ok"] = results["detection_rate"] >= 0.75

    # verdict JSON 结构
    if verdict.exists():
        try:
            v = json.loads(verdict.read_text(encoding="utf-8"))
            results["verdict_json"] = (
                isinstance(v.get("fatal_count"), int)
                and (isinstance(v.get("findings"), list))
            )
        except json.JSONDecodeError:
            results["verdict_json"] = False
    else:
        results["verdict_json"] = False

    # 证据型审稿：报告引用了具体行/数值（如 "L12"、"10 vs 8"、"问题二"）
    evidence_markers = ["L1", "L2", "行", "第", "问题", "数值", "10 vs 8", "d12"]
    results["evidence_based"] = any(m in content for m in evidence_markers)

    results["all_pass"] = all([
        results["file_COMP_REVIEW.md"],
        results["detection_ok"],
        results["verdict_json"],
        results["evidence_based"],
        results["size_ok"],
    ])
    results["required_checks"] = [
        "file_COMP_REVIEW.md", "detection_ok", "verdict_json", "evidence_based", "size_ok",
    ]
    return results


if __name__ == "__main__":
    ws = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    r = score(ws)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r.get("all_pass") else 1)