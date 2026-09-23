# -*- coding: utf-8 -*-
"""逻辑体检 —— 竞赛链通用逻辑闸，补"数值合法但逻辑错"的盲区。

现有校验(facts_audit/sanity_check/constraint_audit)查的是"数字溯源 + 物理越界 +
内部自洽"，查不了"关系/方向/外推/特征完整性"这类逻辑有效性。本脚本补这一层。

四查(全部由 comp-modeling 声明的"逻辑合同"驱动，与具体赛题无关)：
  1. 外推报警   —— 预测/结果自变量落在训练区间外太远 → 强制标"情景模拟、需现场标定"
  2. 特征完整性 —— 台账/合同标为"应入模"的变量，是否真进了 code 的设计矩阵
  3. 重复计量   —— 合同声明"总量A已含分项B"，代码里又显式把B加一次
  4. 方向/界    —— 反解量声明的上/下界、单调方向，在有 sweep/敏感度数据时重算核对

数据来源(建模阶段产出)：
  LOGIC_CONTRACT_MACHINE (MODELING_REPORT.md 里的 json 块，或独立 LOGIC_CONTRACT.json)
  DATA_FACTS.json        (赛题分析阶段产出，变量 role/range/censored)
  figures/*_results.json (各问结果)
  code/*.py              (源码，用于特征完整性/重复计量的文本核对)

⛔ 全软失败：合同缺 / 文件缺 / 字段缺 → 该条跳过，绝不误判为失败。
   只有"合同齐全 + 确凿违反"才计 FAIL(退出码1)。防老工作流/合同没填全被误杀。

退出码：0=通过(可能带WARN)  1=确凿逻辑错(必修)  2=无据可查(跳过，不阻塞)
用法：python _utils/logic_audit.py [--stage code] [--contract ...] [--facts DATA_FACTS.json] [--figdir figures] [--codedir code]
"""
from __future__ import annotations
import sys
import re
import json
import argparse
import math
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 外推判定：预测点超出训练区间宽度的多少倍算"太远"(相对，通用默认)
_EXTRAP_FACTOR = 0.5
_REL_TOL = 1e-9


def _load_json(path: Path):
    try:
        if not path.exists() or not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def _as_float(x):
    try:
        if isinstance(x, bool):
            return None
        value = float(x)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def load_contract(contract_arg: str | None) -> dict | None:
    """加载 LOGIC_CONTRACT_MACHINE。优先独立文件，其次从 MODELING_REPORT.md 的 ```json 块里抓。
    未指定时抓不到返回 {}；显式指定但不可读返回 None，不回退全局合同。"""
    # An explicit scoped contract must never fall back to another question's
    # global contract when missing/corrupt. None is distinguishable from {}.
    if contract_arg is not None:
        data = _load_json(Path(contract_arg))
        return data.get("LOGIC_CONTRACT_MACHINE", data) if isinstance(data, dict) else None
    # 1) 独立文件（未显式指定时保持历史自动发现）
    for cand in ("LOGIC_CONTRACT.json", "LOGIC_CONTRACT_MACHINE.json"):
        if not cand:
            continue
        d = _load_json(Path(cand))
        if isinstance(d, dict):
            return d.get("LOGIC_CONTRACT_MACHINE", d)
    # 2) 从 MODELING_REPORT.md 的 json 代码块里找含 LOGIC_CONTRACT_MACHINE 的
    rep = Path("MODELING_REPORT.md")
    if rep.is_file():
        try:
            txt = rep.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return {}
        for m in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", txt, re.DOTALL):
            try:
                obj = json.loads(m.group(1))
            except Exception:
                continue
            if isinstance(obj, dict) and "LOGIC_CONTRACT_MACHINE" in obj:
                return obj["LOGIC_CONTRACT_MACHINE"]
            if isinstance(obj, dict) and any(
                    k in obj for k in ("must_features", "no_double_count", "bounds", "train_range")):
                return obj  # 直接就是合同本体
    return {}


class ResultEvidence(dict):
    """Keep unresolved provenance visible without selecting a random question."""

    def __init__(self):
        super().__init__()
        self.issues = []
        self.unresolved = {}


def _collect_results(fig_dir: Path) -> dict:
    """Bare keys require unambiguous values; file.json::key is always scoped.

    File enumeration order is not evidence that Q1's cost belongs to Q2.
    Unreadable and non-finite numeric inputs remain unresolved, never PASS.
    """
    out = ResultEvidence()
    if not fig_dir.is_dir():
        return out
    try:
        cands = sorted(set(fig_dir.glob("*_results.json")) | set(fig_dir.glob("all_results.json")))
    except Exception:
        return out
    candidates = {}
    for f in cands:
        d = _load_json(f)
        if not isinstance(d, dict):
            out.issues.append(f"[结果未载入] {f.name}: 不可读或不是字段对象；只有合同引用此文件时才需补证据")
            continue
        for k, v in d.items():
            fv = _as_float(v)
            if fv is not None:
                scoped = f"{f.name}::{k}"
                out[scoped] = fv
                candidates.setdefault(k, []).append((scoped, fv))
            elif isinstance(v, (float, int)) and not isinstance(v, bool):
                issue = f"[NEEDS_EVIDENCE] {f.name}::{k}: 非有限数值，不能作为有效逻辑证据"
                out.unresolved[f"{f.name}::{k}"] = issue
                out.unresolved[k] = issue
    for key, values in candidates.items():
        if all(value == values[0][1] for _, value in values):
            if key not in out.unresolved:
                out[key] = values[0][1]
        else:
            locations = ', '.join(name for name, _ in values[:5])
            out.unresolved[key] = f"[NEEDS_EVIDENCE] 同名结果 {key} 在不同问/文件中数值不同：{locations}；用 文件名::字段 明确合同来源，不混合比较"
    return out


def _load_raw_results(fig_dir: Path) -> dict:
    """读 figures 下 results，保留嵌套结构(供方向探针 logic_probes 用)。
    优先 all_results.json；其次合并各 *_results.json 的 logic_probes。读不到返回 {}。"""
    if not fig_dir.is_dir():
        return {}
    allr = _load_json(fig_dir / "all_results.json")
    if isinstance(allr, dict) and "logic_probes" in allr:
        return allr
    merged = {"logic_probes": {"bounds": [], "monotonic": []}}
    found = False
    try:
        cands = sorted(fig_dir.glob("*_results.json"))
    except Exception:
        cands = []
    if isinstance(allr, dict):
        cands = [fig_dir / "all_results.json"] + cands
    for f in cands:
        d = _load_json(f)
        if not isinstance(d, dict):
            continue
        lp = d.get("logic_probes")
        if isinstance(lp, dict):
            found = True
            for key in ("bounds", "monotonic"):
                if isinstance(lp.get(key), list):
                    merged["logic_probes"][key].extend(lp[key])
    return merged if found else (allr if isinstance(allr, dict) else {})


def _read_code_blob(code_dir: Path) -> str:
    """把 code/*.py 拼成一个大字符串，供文本级核对(特征完整性/重复计量)。读不到返回 ''。"""
    if not code_dir.is_dir():
        return ""
    blob = []
    try:
        for f in code_dir.rglob("*.py"):
            try:
                blob.append(f.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
    except Exception:
        return ""
    return "\n".join(blob)


def audit_extrapolation(contract: dict, facts: dict, results: dict) -> list:
    """外推报警(WARN，不阻塞)：结果里的量超出训练/观测区间太远 → 提示标注情景模拟。
    区间来源：合同 train_range 优先，其次 DATA_FACTS 的 variables[].range。"""
    warns = []
    ranges = {}
    tr = contract.get("train_range")
    if isinstance(tr, dict):
        for k, v in tr.items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                lo, hi = _as_float(v[0]), _as_float(v[1])
                if lo is not None and hi is not None and hi >= lo:
                    ranges[k] = (lo, hi)
    if isinstance(facts, dict):
        for var in (facts.get("variables") or []):
            if not isinstance(var, dict):
                continue
            name = var.get("name")
            rg = var.get("range")
            if name and name not in ranges and isinstance(rg, (list, tuple)) and len(rg) == 2:
                lo, hi = _as_float(rg[0]), _as_float(rg[1])
                if lo is not None and hi is not None and hi >= lo:
                    ranges[name] = (lo, hi)
    for name, val in results.items():
        if name not in ranges:
            continue
        lo, hi = ranges[name]
        width = max(hi - lo, 1e-12)
        if val < lo - _EXTRAP_FACTOR * width or val > hi + _EXTRAP_FACTOR * width:
            warns.append(
                f"[外推] 「{name}={val:g}」远超训练/观测区间 [{lo:g},{hi:g}] —— "
                f"正文须标注「情景模拟、需现场标定」，禁用确定性口吻当数据结论。")
    return warns


def audit_feature_completeness(contract: dict, code_blob: str) -> list:
    """Only an explicit observed input schema can prove a required feature missing.

    Code-name absence alone is inconclusive for aliases or vectorized frames.
    """
    fails = []
    feats = contract.get("must_features")
    if not isinstance(feats, list) or not code_blob:
        return fails
    for feat in feats:
        if not isinstance(feat, str) or not feat.strip():
            continue
        # 词边界匹配，避免 T1 命中 T12
        # Absence of a column name is not absence of the column: all-column
        # frames, aliases and pipelines need runtime schema evidence.
        observed = contract.get("observed_model_features")
        if isinstance(observed, list) and all(isinstance(x, str) for x in observed) and feat not in observed:
            fails.append(f"[特征完整性] 实际入模列清单缺少合同要求的「{feat}」；请核对模型输入而不是改写报告。")
    return fails


def audit_double_count(contract: dict, code_blob: str) -> list:
    """Find positive aggregate/part terms in a parsed assignment or return.

    Subtraction and canceled terms are not duplicate positive contributions.
    """
    fails = []
    rules = contract.get("no_double_count")
    if not isinstance(rules, list) or not code_blob:
        return fails
    import ast
    try:
        tree = ast.parse(code_blob)
    except SyntaxError:
        return fails  # Syntax belongs to the code syntax gate.

    def terms(node, sign=1):
        if isinstance(node, ast.Name):
            return {node.id: sign}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return terms(node.operand, -sign if isinstance(node.op, ast.USub) else sign)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            left = terms(node.left, sign)
            for key, value in terms(node.right, -sign if isinstance(node.op, ast.Sub) else sign).items():
                left[key] = left.get(key, 0) + value
            return left
        return {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        agg = rule.get("aggregate")
        con = rule.get("contains")
        if not (isinstance(agg, str) and isinstance(con, str) and agg and con):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.Return)) or node.value is None:
                continue
            coefficients = terms(node.value)
            if coefficients.get(agg, 0) > 0 and coefficients.get(con, 0) > 0:
                ln = ast.get_source_segment(code_blob, node) or ""
                fails.append(
                    f"[重复计量] 合同声明「{agg}」已含「{con}」，但代码里又把二者相加："
                    f"`{ln.strip()[:80]}` —— 同一部分被计两次。")
                break
    return fails


def audit_direction(contract: dict, results_raw: dict) -> tuple:
    """方向/界核对 —— 把①"方向反"从纯判断拉回可验证。返回 (fails, warns)。

    依据 comp-code 按合同做的「扰动重算探针」，写在 figures 的 results 里的 logic_probes：
    {
      "logic_probes": {
        "bounds": [
          {"quantity":"eta","claim":"upper|lower","probe_delta_sign": -1}
          // 把被截断/封顶的输入朝"真值方向"推一点后重算，目标量的变化符号(+1/-1/0)。
          // 数学事实：若反算量是【上界】，输入朝真值方向动 → 该量应【减小】(sign<0)；
          //           若是【下界】→ 应【增大】(sign>0)。符号与 claim 矛盾 = 方向标反(FAIL)。
        ],
        "monotonic": [
          {"more":"voltage","then":"cost","observed_sign": +1, "expect_dir":"worse|better"}
          // 决策资源增大时目标量的实测变化符号。expect_dir 由合同声明。
        ]
      }
    }
    ⛔ 无探针数据 → 跳过(不报，方向反此时只能靠 comp-review 兜)。这是"让数据说话"、
       不需模型判断方向的一道半硬闸；但探针本身走的是可能有误的模型，故只作层层减漏之一。
    """
    fails, warns = [], []
    probes = results_raw.get("logic_probes") if isinstance(results_raw, dict) else None
    if not isinstance(probes, dict):
        return fails, warns
    # 1) 界方向：claim=upper 期望 sign<0；claim=lower 期望 sign>0
    for b in (probes.get("bounds") or []):
        if not isinstance(b, dict):
            continue
        claim = str(b.get("claim", "")).lower()
        sign = _as_float(b.get("probe_delta_sign"))
        qty = b.get("quantity", "?")
        if claim not in ("upper", "lower") or sign is None or sign == 0:
            continue  # 信息不全/无变化 → 跳过，不误判
        expect_neg = (claim == "upper")   # 上界→应减小(负)
        if (sign < 0) != expect_neg:
            got = "减小" if sign < 0 else "增大"
            should = "减小" if expect_neg else "增大"
            fails.append(
                f"[方向/界反] 「{qty}」声明为{('上界' if claim=='upper' else '下界')}，"
                f"但扰动重算显示输入朝真值方向变化时该量实际{got}(应{should}) —— "
                f"上/下界方向标反了(会系统性高估/低估)，核对反解/取界的不等号。")
    # 2) 单调方向：observed_sign 与 expect_dir 是否一致(需合同给 expect_sign 才判 FAIL，否则 WARN)
    for m in (probes.get("monotonic") or []):
        if not isinstance(m, dict):
            continue
        osign = _as_float(m.get("observed_sign"))
        exp_sign = _as_float(m.get("expect_sign"))  # 可选：+1/-1，给了才硬判
        more, then = m.get("more", "?"), m.get("then", "?")
        if osign is None or osign == 0:
            continue
        if exp_sign is not None and exp_sign != 0:
            if (osign > 0) != (exp_sign > 0):
                fails.append(
                    f"[单调方向反] 「{more}」增大时「{then}」的实测变化方向与合同声明相反 —— "
                    f"检查目标函数符号/约束方向(经典 max/min 取负号写反)。")
        else:
            warns.append(
                f"[单调方向] 「{more}」增大时「{then}」变化符号={'+' if osign>0 else '-'}，"
                f"请人工确认与预期一致(合同未给 expect_sign，未硬判)。")
    return fails, warns


def audit_margin(contract: dict, results: dict) -> tuple:
    """核对题设限值与显式要求的裕度。等号合法，不自动发明安全余量。

    依据合同 constraints_with_margin（建模声明，字段缺则跳过）：
    [
      {"quantity":"Cout","limit":10,"kind":"le","min_margin":0.05}
      // kind: le=结果应≤limit / ge=应≥limit
      // min_margin(可选,比例): 仅题设/已确认模型明确要求时填写
    ]
    裕度定义(相对): le → (limit-val)/|limit| ; ge → (val-limit)/|limit|
      裕度低于声明容差 → 真实越界；等号允许
      0<裕度<min_margin → 裕度不足(FAIL)
    ⛔ 无 constraints_with_margin → 跳过(不误报)。限值全来自合同,脚本不预置任何数值。
    """
    fails, warns = [], []
    cons = contract.get("constraints_with_margin")
    if not isinstance(cons, list):
        return fails, warns
    for c in cons:
        if not isinstance(c, dict):
            continue
        q = c.get("quantity")
        limit = _as_float(c.get("limit"))
        kind = str(c.get("kind", "le")).lower()
        # ⛔ kind 白名单校验：只认 le/ge，非法(拼错/垃圾)一律软跳过，绝不猜方向(猜错会算反裕度)
        if kind not in ("le", "ge"):
            continue
        if q is None or limit is None or q not in results:
            warns.append(f"[NEEDS_EVIDENCE] 限值条件 {q!r}: 缺少明确的结果来源或有效限值")
            continue  # 下游无该量 → 软跳过
        val = _as_float(results.get(q))
        if val is None:
            warns.append(f"[NEEDS_EVIDENCE] 限值条件 {q!r}: 结果不是有限数值")
            continue
        denom = abs(limit) if abs(limit) > 1e-12 else 1.0
        margin = (limit - val) / denom if kind == "le" else (val - limit) / denom
        req = _as_float(c.get("min_margin"))
        if margin < -1e-9:
            state = "越界"
            fails.append(
                f"[安全裕度] 「{q}={val:g}」相对限值 {limit:g}({kind}) {state} —— "
                f"结果超出题设限值，须修正求解结果；不得自行改变题设可行域。")
        elif req is not None and req > 0 and margin + 1e-9 < req:
            fails.append(
                f"[安全裕度] 「{q}={val:g}」距限值 {limit:g} 仅余 {margin*100:.2f}%，"
                f"低于要求的 {req*100:.2f}% —— 裕度不足，须内收。")
    return fails, warns


def audit_self_consistency(contract: dict, results: dict) -> tuple:
    """问内自洽核对(治"声称退化/等价却数值对不上、只能含糊归因")。返回 (fails, warns)。
    通用、无题目常量——任何"A 退化为/等价于 B"的声称都能查，不限某一类题。

    依据合同 equivalence_claims（建模声明，字段缺则跳过）：
    [
      {"claim":"非线性最优退化为线性",
       "quantity_a":"nonlinear_opt_power","quantity_b":"linear_power",
       "rel_tol":0.02,                 // 可选,声称"等价"允许的相对差,默认 0.02(2%)
       "explanation":""}               // 可选,若确有量化机理解释两者为何仍差,填在此
    ]
    逻辑：a、b 两个量都能在 results 里取到数值时——
      相对差 rel = |a-b| / max(|a|,|b|,eps)
      rel ≤ rel_tol            → 自洽,通过
      rel > rel_tol 且无 explanation → FAIL(声称等价/退化,数值却对不上,又无机理 = 自相矛盾)
      rel > rel_tol 且有 explanation → WARN(给了解释,提示复核解释是否站得住,不阻塞)
    ⛔ 无 equivalence_claims / 缺量 / 缺数值 → 软跳过(不误报)。阈值来自合同,脚本不预置题目常量。
    """
    fails, warns = [], []
    claims = contract.get("equivalence_claims")
    if not isinstance(claims, list):
        return fails, warns
    for c in claims:
        if not isinstance(c, dict):
            continue
        qa, qb = c.get("quantity_a"), c.get("quantity_b")
        if qa is None or qb is None or qa not in results or qb not in results:
            warns.append(f"[NEEDS_EVIDENCE] 等价声称缺明确数值来源: {qa!r}, {qb!r}")
            continue  # 缺量 → 软跳过
        va, vb = _as_float(results.get(qa)), _as_float(results.get(qb))
        if va is None or vb is None:
            warns.append(f"[NEEDS_EVIDENCE] 等价声称含非有限/非数值结果: {qa!r}, {qb!r}")
            continue
        tol = _as_float(c.get("rel_tol"))
        if "rel_tol" not in c:
            tol = 0.02
        atol = _as_float(c.get("abs_tol", 0.0))
        if tol is None or tol < 0 or atol is None or atol < 0:
            warns.append("[NEEDS_EVIDENCE] 等价声称容差无效；修合同，不改变计算结果")
            continue
        denom = max(abs(va), abs(vb), 1e-12)
        rel = abs(va - vb) / denom
        if abs(va - vb) <= atol + tol * max(abs(va), abs(vb)):
            continue  # 自洽
        claim = str(c.get("claim") or f"{qa} 等价/退化为 {qb}")
        expl = c.get("explanation")
        # ⛔ 只认"非空字符串"为有效解释：数字 0 / false / 空列表这类"伪解释"(填了个无意义假值)
        #    不算解释，仍判 FAIL——否则硬拦会被一个 explanation:0 绕过。真正的机理说明必须是文字。
        expl_s = expl.strip() if isinstance(expl, str) else ""
        if expl_s:
            warns.append(
                f"[问内自洽] 声称「{claim}」，但 {qa}={va:g} 与 {qb}={vb:g} 相差 {rel*100:.1f}%"
                f"(>容差 {tol*100:.1f}%)，已给解释「{expl_s}」—— 请复核该解释是否量化站得住。")
        else:
            fails.append(
                f"[问内自洽] 声称「{claim}」，但 {qa}={va:g} 与 {qb}={vb:g} 相差 {rel*100:.1f}%"
                f"(>容差 {tol*100:.1f}%)，且无任何量化机理解释 —— 自相矛盾(不能用「瞬态残余」等词含糊带过)，"
                f"要么改正声称(其实不等价)、要么把差异用机理定量说清并写进 explanation。")
    return fails, warns


def audit_anchor(contract: dict, facts: dict) -> tuple:
    """标定锚点口径核对(治"锚点比观测更乐观→系统性高估能力→低估达标代价")。返回 (fails, warns)。

    依据合同 calibration_anchors（建模声明，字段缺则跳过）：
    [
      {"quantity":"Cout","anchor":20,"optimistic_dir":"low"}
      // optimistic_dir: 该量朝哪个方向算"乐观/高估设备能力"。
      //   "low"=值越低越乐观(如出口浓度锚点取得越低→显得设备越强)
      //   "high"=值越高越乐观
      // 观测区间优先取合同同名 train_range，其次 DATA_FACTS.variables[].range
    ]
    判据：锚点落在观测区间的"乐观端之外"→ 报警(锚点比真实数据更乐观，会系统性高估能力)。
    ⛔ 无 calibration_anchors → 跳过。区间/方向全来自声明，脚本不预置任何题目数值。
    """
    fails, warns = [], []
    anchors = contract.get("calibration_anchors")
    if not isinstance(anchors, list):
        return fails, warns
    # 收集观测区间：train_range 优先，其次 DATA_FACTS
    ranges = {}
    tr = contract.get("train_range")
    if isinstance(tr, dict):
        for k, v in tr.items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                lo, hi = _as_float(v[0]), _as_float(v[1])
                if lo is not None and hi is not None and hi >= lo:
                    ranges[k] = (lo, hi)
    if isinstance(facts, dict):
        for var in (facts.get("variables") or []):
            if isinstance(var, dict) and var.get("name") and var["name"] not in ranges:
                rg = var.get("range")
                if isinstance(rg, (list, tuple)) and len(rg) == 2:
                    lo, hi = _as_float(rg[0]), _as_float(rg[1])
                    if lo is not None and hi is not None and hi >= lo:
                        ranges[var["name"]] = (lo, hi)
    for a in anchors:
        if not isinstance(a, dict):
            continue
        q = a.get("quantity")
        av = _as_float(a.get("anchor"))
        od = str(a.get("optimistic_dir", "")).lower()
        if q is None or av is None or q not in ranges or od not in ("low", "high"):
            continue
        lo, hi = ranges[q]
        if od == "low" and av < lo:
            warns.append(
                f"[锚点乐观] 标定锚点「{q}={av:g}」低于观测区间下界 {lo:g}(越低越乐观) —— "
                f"等于假设设备比数据显示的更强，会系统性高估能力、低估达标所需代价。建议锚点回到观测口径或标注偏乐观。")
        elif od == "high" and av > hi:
            warns.append(
                f"[锚点乐观] 标定锚点「{q}={av:g}」高于观测区间上界 {hi:g}(越高越乐观) —— "
                f"会系统性高估能力、低估达标代价。建议锚点回到观测口径或标注偏乐观。")
    return fails, warns


def audit_contract_completeness(contract: dict, facts: dict, code_blob: str) -> list:
    """合同完整性(WARN，不阻塞)——治本体系命门："该声明的合同没声明，闸就软跳过=形同虚设"。
    只认两条【极精准、低误报】的信号(都基于显式标记/明确 API，不做"有除法就报"的宽泛匹配)：
      A. DATA_FACTS 里有变量被标了 censored(封顶/删失) → 但合同 bounds 为空
         = 有删失数据、却没声明"反算量是上界还是下界"(方向反的高发区没上闸)。
      B. 代码里出现明确的优化 API(minimize/linprog/milp/GRB/pulp/argmin…) → 但 constraints_with_margin 为空
         = 提醒核题设限值与已有可行性证据；不自动要求额外安全裕度。
    ⛔ 全 WARN：没声明是"提醒补"不是"硬错"，不阻塞、不误杀。缺 DATA_FACTS/代码则相应条跳过。
    """
    warns = []
    bounds = contract.get("bounds")
    cwm = contract.get("constraints_with_margin")
    has_bounds = isinstance(bounds, list) and len(bounds) > 0
    has_cwm = isinstance(cwm, list) and len(cwm) > 0

    # A. 有删失数据却没声明界方向
    if not has_bounds and isinstance(facts, dict):
        censored_vars = []
        for var in (facts.get("variables") or []):
            if not isinstance(var, dict):
                continue
            cz = var.get("censored")
            kind = (cz.get("kind") if isinstance(cz, dict) else None)
            if kind and str(kind).lower() not in ("none", "", "null"):
                censored_vars.append(var.get("name", "?"))
        if censored_vars:
            warns.append(
                f"[合同缺口] DATA_FACTS 标了删失/封顶变量({', '.join(map(str, censored_vars[:5]))})，"
                f"但 LOGIC_CONTRACT 的 bounds 为空 —— 凡由删失值反解/取界的量，务必声明是【上界还是下界】"
                f"(否则方向反这类错没有任何闸在核)。")

    # B. 核题设限值；不强迫优化题增加安全裕度
    if not has_cwm and code_blob:
        import re as _re
        # 明确的优化 API 关键词(词边界，避免误伤)；不匹配泛化的数学符号
        opt_pat = _re.compile(
            r"(?<![\w.])(minimize|maximize|linprog|milp|argmin|argmax|LpProblem|LpMinimize|"
            r"GRB\.|gurobipy|pulp|scipy\.optimize|differential_evolution|linear_sum_assignment)(?![\w])")
        if opt_pat.search(code_blob):
            warns.append(
                "[合同缺口] 代码里有优化求解，但 LOGIC_CONTRACT 的 constraints_with_margin 为空 —— "
                "核对题设是否有限值，并复用已有可行性验证；题目没要求安全余量时不另加限制，等号可以是合法最优解。")
    return warns


def main() -> int:
    ap = argparse.ArgumentParser(description="逻辑体检")
    ap.add_argument("--stage", default="code")
    ap.add_argument("--contract", default=None)
    ap.add_argument("--facts", default="DATA_FACTS.json")
    ap.add_argument("--figdir", default="figures")
    ap.add_argument("--codedir", default="code")
    args = ap.parse_args()

    contract = load_contract(args.contract)
    if not isinstance(contract, dict):
        print("[CHECK_UNAVAILABLE] 指定逻辑合同不可读或不是对象；先核路径和合同结构，不重新生成求解结果")
        return 2
    facts = _load_json(Path(args.facts)) or {}
    results = _collect_results(Path(args.figdir))          # 仅标量(给外推用)
    results_raw = _load_raw_results(Path(args.figdir))     # 保留嵌套(给方向探针用)
    code_blob = _read_code_blob(Path(args.codedir))

    has_contract = bool(contract) and any(
        k in contract for k in ("must_features", "no_double_count", "bounds", "train_range",
                                "monotonic", "constraints_with_margin", "calibration_anchors",
                                "equivalence_claims"))
    has_facts = isinstance(facts, dict) and bool(facts.get("variables"))

    if not has_contract and not has_facts:
        print("⚠ 逻辑体检：未找到 LOGIC_CONTRACT_MACHINE(建模阶段) 或 DATA_FACTS.json(赛题分析阶段)，"
              "跳过(不阻塞)。填了逻辑合同/数据台账后本闸才生效。")
        return 2

    # Unrelated questions may legitimately reuse cost/seed/n. Only inspect the
    # quantities this contract actually references; never trigger global repair.
    requested = set()
    for field in ("constraints_with_margin", "equivalence_claims"):
        entries = contract.get(field)
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, dict):
                requested.update(entry[key] for key in ("quantity", "quantity_a", "quantity_b")
                                 if isinstance(entry.get(key), str))
    ranges = contract.get("train_range")
    if isinstance(ranges, dict):
        requested.update(ranges)
    warns = [message for key, message in getattr(results, "unresolved", {}).items() if key in requested]
    fails = []
    warns += audit_extrapolation(contract, facts, results)
    fails += audit_feature_completeness(contract, code_blob)
    if contract.get("must_features") and "observed_model_features" not in contract:
        warns.append("[特征待核实] 请从模型实际输入导出 observed_model_features；源码未出现列名不等于漏用变量。")
    fails += audit_double_count(contract, code_blob)
    _dir_fails, _dir_warns = audit_direction(contract, results_raw)
    fails += _dir_fails
    warns += _dir_warns
    _mg_fails, _mg_warns = audit_margin(contract, results)
    fails += _mg_fails
    warns += _mg_warns
    _sc_fails, _sc_warns = audit_self_consistency(contract, results)
    fails += _sc_fails
    warns += _sc_warns
    _an_fails, _an_warns = audit_anchor(contract, facts)
    fails += _an_fails
    warns += _an_warns
    warns += audit_contract_completeness(contract, facts, code_blob)

    print("=== 逻辑体检 (logic_audit) ===")
    if warns:
        print("— 提醒(WARN，不阻塞)：")
        for w in warns:
            print("   " + w)
    if fails:
        print("❌ 检出逻辑错 %d 处(必修)：" % len(fails))
        for f in fails:
            print("   " + f)
        print("⛔ 请回 comp-modeling/comp-code 修正：漏用真实变量补进模型、重复计入的项去掉一次。")
        return 1
    if any("[NEEDS_EVIDENCE]" in warning for warning in warns):
        print("NEEDS_EVIDENCE — 来源或检查证据未齐；先核对应项，不重跑全阶段")
        return 2
    print("PASS — 已有可检查证据未发现矛盾；不证明未覆盖的能力或模型正确性。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
