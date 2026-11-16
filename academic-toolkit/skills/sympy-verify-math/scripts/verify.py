#!/usr/bin/env python3
"""verify.py — sympy-verify-math 技能核心校验脚本。

按 SKILL.md「Verification Commands」契约实现五个子命令（纯 sympy）：

    verify.py eq EXPR1 EXPR2   # 判等：相等退出码 0 并打印 EQUAL，否则退出码 1
    verify.py diff EXPR [VAR]  # 求导（VAR 缺省 x）
    verify.py int EXPR [VAR]   # 积分（VAR 缺省 x）
    verify.py simp EXPR        # 化简/展开
    verify.py solve EXPR [VAR] # 解方程 EXPR = 0（VAR 缺省 x）

表达式语法见 SKILL.md：`^` 视为 `**`；预定义符号 x y z t s n k a b c C；
保留名 E I S N O 一律按普通变量处理（不当作 SymPy 常量/函数）。
"""
import sys

import sympy

# SKILL.md 约定的预定义符号 + 需屏蔽的保留名（E=欧拉数、I=虚数单位等）。
SYMBOL_NAMES = ("x y z t s n k a b c C E I S N O").split()
DEFAULT_VAR = "x"

USAGE = """usage:
  verify.py eq EXPR1 EXPR2
  verify.py diff EXPR [VAR]
  verify.py int EXPR [VAR]
  verify.py simp EXPR
  verify.py solve EXPR [VAR]"""


def _parse(text):
    """把 SKILL.md 语法的表达式解析为 SymPy 表达式。"""
    local = {name: sympy.Symbol(name) for name in SYMBOL_NAMES}
    return sympy.sympify(text.replace("^", "**"), locals=local)


def _var(text):
    """可选变量参数：缺省 x；传入时按同一套符号规则解析。"""
    return _parse(text) if text else sympy.Symbol(DEFAULT_VAR)


def main(argv):
    if len(argv) < 2:
        print(USAGE, file=sys.stderr)
        return 2
    cmd = argv[1]
    try:
        if cmd == "eq":
            if len(argv) != 4:
                print(USAGE, file=sys.stderr)
                return 2
            a, b = _parse(argv[2]), _parse(argv[3])
            equal = sympy.simplify(a - b) == 0 or a.equals(b) is True
            print("EQUAL" if equal else "NOT EQUAL")
            return 0 if equal else 1
        if len(argv) < 3 or len(argv) > 4:
            print(USAGE, file=sys.stderr)
            return 2
        expr = _parse(argv[2])
        if cmd == "diff":
            result = sympy.diff(expr, _var(argv[3] if len(argv) > 3 else ""))
        elif cmd == "int":
            result = sympy.integrate(expr, _var(argv[3] if len(argv) > 3 else ""))
        elif cmd == "simp":
            result = sympy.simplify(sympy.expand(expr))
        elif cmd == "solve":
            result = sympy.solve(expr, _var(argv[3] if len(argv) > 3 else ""))
        else:
            print(f"unknown command: {cmd}\n{USAGE}", file=sys.stderr)
            return 2
    except Exception as exc:  # CLI 边界：解析/计算失败统一报错退出，不裸抛堆栈
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
