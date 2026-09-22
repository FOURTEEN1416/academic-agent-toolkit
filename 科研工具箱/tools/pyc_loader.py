# -*- coding: utf-8 -*-
"""
pyc_loader.py — 通用 .pyc 加载器（跨 Python 小版本兼容）

背景：tools/ 下部分工具以 .pyc 分发（Python 3.11 编译，magic 0x0a0d0da7），
当前默认环境为 Python 3.12+（magic 0x0a0d0dcb）。

两个加载路径：
  1. 优先：找到 Python 3.11 venv（.venv311），用 subprocess 原生运行 .pyc
     （字节码语义完全一致，最可靠）
  2. 回退：marshal 手动加载 code object（3.11→3.12 相邻版本 marshal 格式稳定，
     但部分 opcode 语义差异可能导致运行时错误）

用法：
  python pyc_loader.py <xxx.pyc> [args...]
"""
import os
import sys
import marshal
import pathlib
import subprocess

# .venv311 位置：优先套件根目录，其次工作区根
_VENV_CANDIDATES = [
    pathlib.Path(__file__).resolve().parent.parent / '.venv311',   # 科研工具箱/.venv311
    pathlib.Path(__file__).resolve().parent.parent.parent / '.venv311',  # 工作区根/.venv311
]
_VENV_PY = None
for _c in _VENV_CANDIDATES:
    _p = _c / 'Scripts' / 'python.exe'
    if _p.exists():
        _VENV_PY = str(_p)
        break

# 套件根目录（tools/ 的上一级）
_SUITE_ROOT = pathlib.Path(__file__).resolve().parent.parent
_ENV_FILE = _SUITE_ROOT / '.env'


def find_py311_venv():
    """查找 Python 3.11 venv 的 python.exe，未找到返回 None。"""
    return _VENV_PY


def _load_env_file(env_path: pathlib.Path) -> dict:
    """解析 .env 文件（简单键值对，跳过注释/空行）。"""
    result = {}
    if not env_path.exists():
        return result
    try:
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                result[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return result


def build_vision_env() -> dict:
    """构建 .pyc 工具运行所需的完整环境变量（2026-09-23 换驱动收敛）：
    1. 继承当前进程环境
    2. 合并套件 .env（已存在配置优先）
    旧实现的「从 OpenCode 桌面端 auth.json 挖掘视觉 API key 注入子进程」整段
    已随视觉审核换驱动（宿主独立窗口，零 key 零网络）拆除。
    """
    env = os.environ.copy()

    # 先加载 .env（套件自有配置优先）
    dotenv = _load_env_file(_ENV_FILE)
    for k, v in dotenv.items():
        if k in ('EDITOR_AI_BASE_URL', 'OPENAI_BASE_URL', 'AGNES_BASE_URL', 'GPT_IMAGE_BASE_URL'):
            if v.endswith('/v1'):
                v = v[:-3]
        env.setdefault(k, v)

    return env

def load_code_from_pyc(pyc_path: pathlib.Path):
    """跳过 pyc 头部（magic 4 + flags 4 + mtime 4 + size 4），用 marshal 加载 code object。"""
    with open(pyc_path, 'rb') as f:
        f.read(16)
        code = marshal.load(f)
    return code


def absolutize_caller_paths(argv, caller_cwd=None):
    """把"调用方 cwd 下真实存在的相对路径参数"转换为绝对路径，其余原样保留。

    背景（A7-F2）：run_pyc_native 以 tools/ 为子进程 cwd（payload 依赖 tools/ 下的
    数据文件，cwd 必须保留），而调用方按文档使用相对路径传图片参数
    （comp-visual-review Step4.5、paper-figure Step4.5、paper-figure-drawio Step5.7
    均是 `figures/xxx.png` 形态）——旧逻辑下参数一律按 tools/ 解析，
    必报 File not found → exit 2，被管线语义误判为"视觉 API 不可用"而静默跳过。

    转换规则（保持原报错语义）：
      - 选项（`-` 开头）、绝对路径、盘符锚定路径 → 原样保留；
      - 相对路径且在调用方 cwd 下真实存在 → 转绝对路径；
      - 相对路径但不存在 → 原样保留（工具按自己的 cwd 报 File not found，与旧版一致）。
    """
    cwd = pathlib.Path(caller_cwd) if caller_cwd is not None else pathlib.Path.cwd()
    result = []
    for arg in (argv or []):
        if not isinstance(arg, str) or not arg or arg.startswith("-"):
            result.append(arg)
            continue
        candidate = pathlib.Path(arg)
        if candidate.is_absolute() or (len(arg) >= 2 and arg[1] == ":"):
            result.append(arg)
            continue
        resolved = cwd / candidate
        if resolved.exists():
            result.append(str(resolved))
        else:
            result.append(arg)
    return result


def run_pyc_native(pyc_path: pathlib.Path, argv: list = None):
    """用 Python 3.11 venv 原生运行 .pyc（推荐路径）。"""
    py = find_py311_venv()
    if not py:
        return False
    # A7-F2：调用方 cwd 下真实存在的相对路径参数先转绝对路径，
    # 再以 tools/ 为子进程 cwd 启动（payload 数据文件依赖保留）。
    cmd = [py, str(pyc_path)] + absolutize_caller_paths(argv)
    env = build_vision_env()
    try:
        r = subprocess.run(cmd, cwd=str(pyc_path.parent), env=env)
    except Exception:
        return False
    sys.exit(r.returncode)
    return True


def run_pyc_marshal(pyc_path: pathlib.Path, argv: list = None):
    """回退路径：marshal 手动加载 code object 执行。"""
    # 注入套件 .env 到当前进程
    dotenv = _load_env_file(_ENV_FILE)
    for k, v in dotenv.items():
        os.environ.setdefault(k, v)

    code = load_code_from_pyc(pyc_path)
    globals_dict = {
        '__name__': '__main__',
        '__file__': str(pyc_path),
        '__package__': None,
        '__spec__': None,
        '__doc__': None,
        '__builtins__': __builtins__,
    }
    sys.argv = [str(pyc_path)] + (argv or [])
    exec(code, globals_dict, globals_dict)


def run_pyc(pyc_path: pathlib.Path, argv: list = None):
    """运行 .pyc：优先 venv311 原生，回退 marshal。"""
    if not run_pyc_native(pyc_path, argv):
        run_pyc_marshal(pyc_path, argv)


def import_pyc_module(pyc_path: pathlib.Path, module_globals: dict):
    """wrapper 被当作兄弟模块 **import** 时：把 pyc 代码执行进调用模块自身命名空间。

    背景（CI run 35708105058）：count_chapter_words.pyc 顶层 `from markdown_utils
    import compute_text_metrics` 命中的是 markdown_utils.py wrapper；旧 wrapper 无
    __main__ 分流，导入时走 run_pyc——marshal 路径把符号 exec 进 run_pyc_marshal 的
    局部 globals_dict，wrapper 模块命名空间始终为空 → ImportError。
    限制：跨解释器版本 marshal 不可行（3.12 载 3.11 pyc 会 ValueError），
    该场景本仓由 .venv311 原生路径覆盖。
    """
    module_globals.setdefault('__name__', pyc_path.stem)
    module_globals.setdefault('__file__', str(pyc_path))
    module_globals.setdefault('__package__', None)
    module_globals.setdefault('__spec__', None)
    code = load_code_from_pyc(pyc_path)
    exec(code, module_globals)


def build_wrappers(tools_dir: pathlib.Path, force: bool = False):
    """为 tools/ 下所有 .pyc 生成/更新 .py wrapper（优先 venv311，回退 marshal）。"""
    wrapper_template = '''# -*- coding: utf-8 -*-
"""Auto-generated wrapper for {pyc_name} (Python 3.11 pyc).

Generated by tools/pyc_loader.py — runs via .venv311 (Python 3.11) natively,
falls back to marshal loading on the current interpreter.
"""
import sys
import pathlib
import os as _os

_pyc_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "{pyc_name}")
if not _os.path.exists(_pyc_path):
    print(f"ERROR: {pyc_name} not found at {{_pyc_path}}")
    sys.exit(1)

# 确保 tools/ 在 sys.path（供兄弟模块导入）
_tools_dir = _os.path.dirname(_os.path.abspath(__file__))
if _tools_dir not in sys.path:
    sys.path.insert(0, _tools_dir)

{help_block}if __name__ == "__main__":
    from pyc_loader import run_pyc
    run_pyc(pathlib.Path(_pyc_path), sys.argv[1:])
else:
    # 被兄弟模块 import：符号须落进本模块命名空间（见 pyc_loader.import_pyc_module）
    from pyc_loader import import_pyc_module
    import_pyc_module(pathlib.Path(_pyc_path), globals())
'''
    help_block_template = '''# pyc 本体无 argparse（构建期探测）：wrapper 按其自身 Usage 常量响应 -h/--help
_USAGE = {usage!r}
if __name__ == "__main__" and sys.argv[1:2] in (["-h"], ["--help"]):
    print(_USAGE)
    sys.exit(0)

'''
    built = []
    for pyc in sorted(tools_dir.glob('*.pyc')):
        py = pyc.with_suffix('.py')
        help_block = ''
        try:
            code = load_code_from_pyc(pyc)
        except Exception:
            code = None
        if code is not None and not _code_uses_argparse(code):
            usage = _find_usage_const(code) or f"Usage: python {py.name} <args...>"
            help_block = help_block_template.format(usage=usage)
        need_write = force or not py.exists() \
            or 'import_pyc_module' not in py.read_text(encoding='utf-8', errors='replace') \
            or ('_USAGE' not in py.read_text(encoding='utf-8', errors='replace') and help_block)
        if need_write:
            py.write_text(wrapper_template.format(pyc_name=pyc.name, help_block=help_block), encoding='utf-8')
            built.append(pyc.name)
    return built


def _code_uses_argparse(code) -> bool:
    stack = [code]
    while stack:
        c = stack.pop()
        if 'argparse' in getattr(c, 'co_names', ()):
            return True
        stack.extend(k for k in c.co_consts if hasattr(k, 'co_names'))
    return False


def _find_usage_const(code):
    stack = [code]
    while stack:
        c = stack.pop()
        for k in c.co_consts:
            if hasattr(k, 'co_names'):
                stack.append(k)
            elif isinstance(k, str) and k.startswith(('Usage', 'usage')):
                return k.splitlines()[0].strip()
    return None


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    target = pathlib.Path(sys.argv[1])
    if not target.exists():
        print(f"ERROR: {target} not found")
        sys.exit(1)
    run_pyc(target, sys.argv[2:])