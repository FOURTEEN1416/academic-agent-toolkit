#!/usr/bin/env python3
"""转写结果数值自检（latex-equation-from-image 的真实执行入口）。

对"图片→LaTeX"转写结果做两类 sympy 数值自检：
  eval   —— 把转写表达式在给定变量赋值下求值（核对已知数值/与其他独立计算对账）；
  check  —— 把两个转写表达式在随机采样点上做数值等价比对（核对转写结构是否自洽，
            例如"分式转写 vs 展开式"应逐点相等）。

表达式语法：sympy 语法（转写得到的 LaTeX 片段先按 SKILL.md 规范化为 sympy 语法；
本脚本亦容忍常见 LaTeX 残留：\\frac{a}{b}、\\sqrt{x}、\\pi/\\mu 等希腊字母、
\\cdot/\\times、\\left/\\right、x^{2} 上标花括号、^ 乘方）。

用法：
  python scripts/verify_latex.py eval --expr "EXPR" [--assign a=2 b=3 c=-5]
                                        [--as-symbol E,N,S] [--tol 1e-9]
  python scripts/verify_latex.py check --lhs "EXPR1" --rhs "EXPR2"
                                       [--assign mu=0 sigma=1] [--samples 8]
                                       [--tol 1e-9] [--seed 20261116]
退出码：0=通过；1=不一致或求值失败；2=参数错误。

诚实边界：数值自检只能证明"在采样点上不一致/一致"，不能证明符号恒等；
高置信结论 = 多采样点一致 + 量纲/结构人工复核。异常（除零、复数越界）按
跳过该采样点处理，全部点失败时判 FAIL 并如实报告。
"""
from __future__ import annotations

import argparse
import random
import re
import sys

import sympy
from sympy import Symbol
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


def _replace_frac_once(s: str) -> str | None:
    m = re.search(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}", s)
    if not m:
        return None
    return s[: m.start()] + "((" + m.group(1) + ")/(" + m.group(2) + "))" + s[m.end():]


def _replace_sqrt_once(s: str) -> str | None:
    m = re.search(r"\\sqrt\{([^{}]*)\}", s)
    if not m:
        return None
    return s[: m.start()] + "sqrt(" + m.group(1) + ")" + s[m.end():]


def latex_to_sympy(text: str) -> str:
    """把转写 LaTeX 片段宽容地规范化为 sympy 语法（不完美处按报错人工修）。"""
    s = text.strip()
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\cdot", "*").replace("\\times", "*")
    s = re.sub(r"\\[,;:! ]", "", s)
    changed = True
    while changed:
        changed = False
        for fn in (_replace_frac_once, _replace_sqrt_once):
            out = fn(s)
            if out is not None:
                s, changed = out, True
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)  # \pi->pi, \mu->mu, \alpha->alpha ...
    # 转写惯例：指数位置的小写 e 是欧拉常数（sympy 记作 E），不是自由变量
    s = re.sub(r"(?<![A-Za-z0-9_])e(?=\s*[\^(\{])", "E", s)
    s = s.replace("{", "(").replace("}", ")")
    s = s.replace("^", "**")
    return s


_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)


def _parse(text: str, forced_symbols: list[str]):
    """解析为 sympy 表达式：容忍 LaTeX 残留 + 隐式乘法（4ac、2a、x y 等）。"""
    expr_str = latex_to_sympy(text)
    local_dict = {name: Symbol(name) for name in forced_symbols}
    return parse_expr(expr_str, local_dict=local_dict, transformations=_TRANSFORMS)


def _parse_assign(pairs: list[str]) -> dict:
    values: dict[str, float] = {}
    for item in pairs or []:
        if "=" not in item:
            raise ValueError(f"赋值须形如 k=v：{item!r}")
        k, v = item.split("=", 1)
        values[k.strip()] = float(v)
    return values


def _eval_numeric(expr, assign: dict[str, float], tol: float):
    """代入求值；返回 (ok, value_or_error)。复数按模比较。"""
    subs = {Symbol(k): v for k, v in assign.items()}
    try:
        val = complex(expr.evalf(subs=subs, chop=True))
    except Exception as exc:  # noqa: BLE001
        return False, f"求值失败: {type(exc).__name__}: {exc}"
    if abs(val.imag) > tol * max(1.0, abs(val)):
        return True, val  # 复数值如实返回，由调用方判定
    return True, val.real


def cmd_eval(args) -> int:
    try:
        assign = _parse_assign(args.assign)
        expr = _parse(args.expr, args.as_symbol)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 表达式/赋值解析失败: {type(exc).__name__}: {exc}")
        return 1
    ok, val = _eval_numeric(expr, assign, args.tol)
    if not ok:
        print(f"❌ {val}")
        return 1
    print(f"✅ eval = {val}   (expr={args.expr!r}, assign={assign or '无'})")
    return 0


def cmd_check(args) -> int:
    try:
        assign = _parse_assign(args.assign)
        lhs = _parse(args.lhs, args.as_symbol)
        rhs = _parse(args.rhs, args.as_symbol)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 表达式/赋值解析失败: {type(exc).__name__}: {exc}")
        return 1
    free = sorted((lhs.free_symbols | rhs.free_symbols)
                  - {Symbol(k) for k in assign}, key=str)
    rng = random.Random(args.seed)
    passed = skipped = failed = 0
    for i in range(args.samples):
        point = dict(assign)
        point.update({s.name: rng.uniform(0.5, 2.0) for s in free})
        ok_l, v_l = _eval_numeric(lhs, point, args.tol)
        ok_r, v_r = _eval_numeric(rhs, point, args.tol)
        if not (ok_l and ok_r):
            skipped += 1
            continue
        diff = abs(complex(v_l) - complex(v_r))
        bound = args.tol * max(1.0, abs(complex(v_l)), abs(complex(v_r)))
        if diff <= bound:
            passed += 1
        else:
            failed += 1
            print(f"  ✗ 采样点{ i + 1 }: lhs={v_l} rhs={v_r} |diff|={diff:.3g} point={point}")
    total = args.samples
    print(f"check 结果：{passed}/{total} 点一致，{failed} 点不一致，{skipped} 点跳过"
          f"（自由符号采样：{[s for s in (x.name for x in free)] or '无'}）")
    if failed == 0 and passed > 0:
        print(f"✅ lhs 与 rhs 在全部有效采样点一致（tol={args.tol}）")
        return 0
    print("❌ 数值自检未通过（不一致点存在，或全部采样点求值失败）")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="转写 LaTeX 的 sympy 数值自检")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_eval = sub.add_parser("eval", help="代入求值")
    p_eval.add_argument("--expr", required=True)
    p_eval.add_argument("--assign", nargs="*", default=[], help="k=v 赋值列表")
    p_eval.add_argument("--as-symbol", default="", help="强制按变量处理的名单（逗号分隔，如 E,N,S）")
    p_eval.add_argument("--tol", type=float, default=1e-9)
    p_eval.set_defaults(func=cmd_eval)

    p_chk = sub.add_parser("check", help="两表达式采样点数值比对")
    p_chk.add_argument("--lhs", required=True)
    p_chk.add_argument("--rhs", required=True)
    p_chk.add_argument("--assign", nargs="*", default=[], help="固定赋值 k=v，其余自由符号随机采样")
    p_chk.add_argument("--samples", type=int, default=8)
    p_chk.add_argument("--tol", type=float, default=1e-9)
    p_chk.add_argument("--seed", type=int, default=20261116)
    p_chk.add_argument("--as-symbol", default="")
    p_chk.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    args.as_symbol = [x for x in args.as_symbol.split(",") if x] if args.as_symbol else []
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 未处理异常: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
