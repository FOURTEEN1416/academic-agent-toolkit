#!/usr/bin/env python3
"""评分脚本：comp-code P0 基准。读取工作区文件并评分。"""
import json, sys, tempfile
from pathlib import Path

REQUIRED_SIZE = {"code/main.py": 500, "RESULTS.md": 1000}
LEDGER = "figures/all_results.json"
PROBLEM_RESULTS = "figures/problem_1_results.json"

def score(workspace: Path) -> dict:
    r = {}
    for f, minsz in REQUIRED_SIZE.items():
        p = workspace / f
        size = p.stat().st_size if p.is_file() else 0
        r[f"file_{f}"] = size >= minsz
        r[f"size_{f}"] = size
    # 结果台账：figures/all_results.json 含 problem_1，且含 accuracy 或 predictions
    ledger = workspace / LEDGER
    r["file_figures/all_results.json"] = ledger.is_file()
    ledger_ok = False
    if ledger.is_file():
        try:
            data = json.loads(ledger.read_text(encoding="utf-8"))
            p1 = data.get("problem_1") if isinstance(data, dict) else None
            has_key = isinstance(p1, dict) and ("predictions" in p1 or "accuracy" in p1)
            r["ledger_problem_1"] = has_key
            acc_ok, pred_ok = True, True
            if has_key:
                if "accuracy" in p1:
                    acc = p1["accuracy"]
                    acc_ok = isinstance(acc, (int, float)) and not isinstance(acc, bool) and 0 < acc <= 1
                    r["accuracy_valid"] = acc_ok
                if "predictions" in p1:
                    preds = p1["predictions"]
                    pred_ok = (
                        (isinstance(preds, list) and len(preds) > 0)
                        or (isinstance(preds, dict) and len(preds) > 0)
                    )
                    r["predictions_nonempty"] = pred_ok
            ledger_ok = has_key and acc_ok and pred_ok
        except (json.JSONDecodeError, UnicodeDecodeError):
            r["ledger_problem_1"] = False
    r["ledger_ok"] = ledger_ok
    # 问题一结果明细
    r["file_figures/problem_1_results.json"] = (workspace / PROBLEM_RESULTS).is_file()
    required_checks = [f"file_{f}" for f in REQUIRED_SIZE] + ["file_figures/all_results.json", "ledger_ok", "file_figures/problem_1_results.json"]
    r["all_pass"] = all(r.get(c, False) for c in required_checks)
    r["required_checks"] = required_checks
    return r

def _self_test() -> bool:
    with tempfile.TemporaryDirectory() as td:
        empty = Path(td) / "empty"
        empty.mkdir()
        if score(empty)["all_pass"]:
            print("FAIL: empty workspace must fail")
            return False
        ok = Path(td) / "ok"
        (ok / "code").mkdir(parents=True)
        (ok / "figures").mkdir()
        (ok / "code" / "main.py").write_text("#" * 500 + "\nimport csv\n", encoding="utf-8")
        (ok / "RESULTS.md").write_text("# 结果报告\n" + "=" * 1000, encoding="utf-8")
        (ok / "figures" / "all_results.json").write_text(
            json.dumps({"problem_1": {"accuracy": 1.0, "predictions": ["A_n2", "B_n3", "C_n2"]}}), encoding="utf-8")
        (ok / "figures" / "problem_1_results.json").write_text("{}", encoding="utf-8")
        if not score(ok)["all_pass"]:
            print("FAIL: simulated pass scenario must pass")
            return False
    return True

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if _self_test() else 1)
    ws = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    r = score(ws)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r.get("all_pass") else 1)