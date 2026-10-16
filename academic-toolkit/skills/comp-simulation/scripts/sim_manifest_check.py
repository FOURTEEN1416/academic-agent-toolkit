#!/usr/bin/env python3
"""SIM_MANIFEST.json 结构性校验器（comp-simulation 产物契约）。

校验"仿真模型可复现所必需的最小字段集"：方法/引擎/时间语义/实体/随机性/观测量/校准/V&V/运行账本。
本工具**只做结构与口径校验**，不评价模型正确性，也不读仿真输出内容。

用法：
    python skills/comp-simulation/scripts/sim_manifest_check.py [SIM_MANIFEST.json]
    python skills/comp-simulation/scripts/sim_manifest_check.py --json

退出码：0 = 通过；1 = 契约不合规（FAIL 项列出）；2 = 文件缺失或不可解析（不冒充通过）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

METHODS = {"abm", "des", "sd", "continuous", "montecarlo", "data-driven", "hybrid"}
TIME_SEMANTICS = {"discrete_event", "fixed_step", "hybrid"}
AGGREGATES = {"mean", "median", "max", "min", "p95", "sum", "last"}


def _fail(problems: list[str], msg: str) -> None:
    problems.append(msg)


def check(manifest: dict) -> list[str]:
    p: list[str] = []

    method = manifest.get("method")
    if method not in METHODS:
        _fail(p, f"method 非法或缺失：{method!r}（应为 {sorted(METHODS)} 之一）")
    if method == "hybrid":
        roles = manifest.get("hybrid_roles")
        if not isinstance(roles, dict) or not roles:
            _fail(p, "method=hybrid 必须给 hybrid_roles（谁机理/谁优化/谁抽样）")

    eng = manifest.get("engine")
    if not isinstance(eng, dict):
        _fail(p, "engine 缺失（应含 name/version/available）")
    else:
        for k in ("name", "available"):
            if k not in eng:
                _fail(p, f"engine 缺字段 {k}")
        if eng.get("available") is True and not eng.get("version"):
            _fail(p, "engine.available=true 但未记录 version（版本未记即不可复现）")

    tm = manifest.get("time")
    if not isinstance(tm, dict):
        _fail(p, "time 缺失（应含 semantics/horizon/unit；fixed_step 还需 dt）")
    else:
        if tm.get("semantics") not in TIME_SEMANTICS:
            _fail(p, f"time.semantics 非法：{tm.get('semantics')!r}")
        if tm.get("semantics") == "fixed_step" and not tm.get("dt"):
            _fail(p, "time.semantics=fixed_step 必须给 time.dt")
        if not tm.get("horizon"):
            _fail(p, "time.horizon 缺失（总时长/总事件数）")
        if not tm.get("unit"):
            _fail(p, "time.unit 缺失（时间单位）")

    ents = manifest.get("entities")
    if not isinstance(ents, list) or not ents:
        _fail(p, "entities 缺失或为空（至少一类实体）")
    else:
        for i, e in enumerate(ents):
            if not isinstance(e, dict) or not e.get("type"):
                _fail(p, f"entities[{i}] 缺 type")
            elif not e.get("count"):
                _fail(p, f"entities[{i}]({e.get('type')}) 缺 count")

    rnd = manifest.get("randomness")
    if not isinstance(rnd, dict):
        _fail(p, "randomness 缺失（应含 generator/seeds/replications）")
    else:
        if not rnd.get("generator"):
            _fail(p, "randomness.generator 缺失（应显式声明随机源，如 np.random.default_rng）")
        seeds = rnd.get("seeds")
        if not isinstance(seeds, list) or not seeds:
            _fail(p, "randomness.seeds 缺失或为空（种子必须落盘）")
        n = rnd.get("replications")
        if not isinstance(n, int) or n < 1:
            _fail(p, f"randomness.replications 非法：{n!r}")
        elif n == 1:
            _fail(p, "randomness.replications=1：单次运行不构成证据（N=1 只能作调试输出）")
        elif isinstance(seeds, list) and seeds and n != len(seeds):
            _fail(p, f"replications({n}) 与 seeds 数({len(seeds)}) 不一致（种子表必须一一对应）")

    obs = manifest.get("observations")
    if not isinstance(obs, list) or not obs:
        _fail(p, "observations 缺失或为空（观测量是仿真的产出，必须有）")
    else:
        for i, o in enumerate(obs):
            if not isinstance(o, dict) or not o.get("metric"):
                _fail(p, f"observations[{i}] 缺 metric")
            elif o.get("aggregate") not in AGGREGATES:
                _fail(p, f"observations[{i}].aggregate 非法：{o.get('aggregate')!r}（应为 {sorted(AGGREGATES)} 之一）")

    cal = manifest.get("calibration")
    if not isinstance(cal, dict):
        _fail(p, "calibration 缺失（无数据也须显式声明 source 并标注未校准）")
    else:
        if not cal.get("source"):
            _fail(p, "calibration.source 缺失（参数来源必须可溯源）")

    vv = manifest.get("vv")
    if not isinstance(vv, dict):
        _fail(p, "vv 缺失（应含 verification/validation/baseline）")
    else:
        for k in ("verification", "validation"):
            if not vv.get(k):
                _fail(p, f"vv.{k} 缺失或为空（V&V 缺一即结论不成立）")
        if not vv.get("baseline"):
            _fail(p, "vv.baseline 缺失（无基线对照则提升百分比不成立）")

    runs = manifest.get("runs")
    if not isinstance(runs, dict):
        _fail(p, "runs 缺失（应含 total/wall_clock_s/artifact）")
    else:
        if not isinstance(runs.get("total"), int) or runs["total"] < 1:
            _fail(p, "runs.total 非法")
        if not runs.get("artifact"):
            _fail(p, "runs.artifact 缺失（结果账本路径必须落盘）")

    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SIM_MANIFEST.json 契约校验（只读）")
    ap.add_argument("manifest", nargs="?", default="SIM_MANIFEST.json")
    ap.add_argument("--json", action="store_true", help="机读 JSON 输出")
    args = ap.parse_args(argv)

    path = Path(args.manifest)
    if not path.is_file():
        msg = f"未找到 {path} —— 无 manifest 即未完成（不冒充通过）"
        if args.json:
            print(json.dumps({"ok": False, "reason": "missing", "path": str(path)},
                             ensure_ascii=False))
        else:
            print(f"[SKIP] {msg}")
        return 2

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        if args.json:
            print(json.dumps({"ok": False, "reason": "unparsable", "error": str(exc)},
                             ensure_ascii=False))
        else:
            print(f"[SKIP] {path} 不可解析：{exc}")
        return 2

    if not isinstance(manifest, dict):
        print(f"[FAIL] {path} 顶层应为对象")
        return 1

    problems = check(manifest)
    if args.json:
        print(json.dumps({"ok": not problems, "path": str(path),
                          "problems": problems, "count": len(problems)},
                         ensure_ascii=False, indent=2))
    else:
        print(f"[sim-manifest] {path}")
        if problems:
            print(f"FAIL {len(problems)} 项：")
            for i, item in enumerate(problems, 1):
                print(f"  {i}. {item}")
        else:
            print("OK 契约完整（方法/时间/实体/随机性/观测/校准/V&V/账本齐备）")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
