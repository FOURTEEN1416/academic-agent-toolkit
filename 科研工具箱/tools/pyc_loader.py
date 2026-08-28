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
import json
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


def _load_opencode_vision_config() -> dict:
    """从 OpenCode 桌面端配置读取视觉模型配置（agnes/sensenova 的多模态 provider）。

    读取顺序：
      1. ~/.config/opencode/opencode.json  — OpenCode 桌面端全局配置
      2. OpenCode 桌面端数据目录的 globalConfig（auth.json 含 apiKey）
    返回可直接注入环境的 dict。
    """
    result = {}
    home = pathlib.Path.home()

    # 候选配置文件
    cfg_candidates = [
        home / '.config' / 'opencode' / 'opencode.json',
        home / '.config' / 'opencode' / 'opencode.jsonc',
    ]
    auth_candidates = [
        home / '.local' / 'share' / 'opencode' / 'auth.json',
        home / '.config' / 'opencode' / 'auth.json',
        home / '.local' / 'share' / 'opencode' / 'credentials.json',
    ]

    # 1. 读取 provider 配置（baseURL + apiKey + 多模态模型）
    cfg = None
    for c in cfg_candidates:
        if c.exists():
            try:
                cfg = json.loads(c.read_text(encoding='utf-8'))
                break
            except Exception:
                continue

    if cfg:
        providers = cfg.get('provider', {}) if isinstance(cfg, dict) else {}
        # 优先选择支持图像输入（modalities.input 含 image）的 provider
        vision_provider_key = None
        vision_model_id = None
        for pname, pconf in providers.items():
            if not isinstance(pconf, dict):
                continue
            for mname, mconf in (pconf.get('models', {}) or {}).items():
                if not isinstance(mconf, dict):
                    continue
                mods = mconf.get('modalities') or {}
                inputs = mods.get('input') or []
                if 'image' in inputs:
                    vision_provider_key = pname
                    vision_model_id = mconf.get('id') or mname
                    break
            if vision_provider_key:
                break

        if vision_provider_key and vision_provider_key in providers:
            pconf = providers[vision_provider_key]
            opts = pconf.get('options', {}) or {}
            base_url = opts.get('baseURL', '')
            # 工具内部会拼接 /v1/chat/completions，因此 base_url 必须去掉 /v1 后缀
            if base_url.endswith('/v1'):
                base_url = base_url[:-3]
            result['EDITOR_AI_BASE_URL'] = base_url
            result['OPENAI_BASE_URL'] = base_url
            result['EDITOR_AI_MODEL_ID'] = vision_model_id
            result['REVIEWER_MODEL_ID'] = vision_model_id
            # apiKey 通常在 auth.json
            result['_vision_provider'] = vision_provider_key

    # 2. 读取 auth.json 中的 apiKey（按 provider 查找）
    for auth_file in auth_candidates:
        if not auth_file.exists():
            continue
        try:
            auth = json.loads(auth_file.read_text(encoding='utf-8'))
        except Exception:
            continue
        # 结构示例: {"agnes": {"type": "api", "key": "sk-..."}}
        for key_name in (result.get('_vision_provider'), 'agnes', 'sensenova', 'newapi'):
            if not key_name:
                continue
            entry = auth.get(key_name) or {}
            if isinstance(entry, dict):
                api_key = entry.get('key') or entry.get('apiKey') or ''
                if api_key:
                    result['EDITOR_AI_API_KEY'] = api_key
                    result['OPENAI_API_KEY'] = api_key
                    break
            elif isinstance(entry, str) and entry.startswith('sk-'):
                result['EDITOR_AI_API_KEY'] = entry
                result['OPENAI_API_KEY'] = entry
                break

    result.pop('_vision_provider', None)
    return result


def build_vision_env() -> dict:
    """构建工具运行所需的完整环境变量：
    1. 继承当前进程环境
    2. 合并套件 .env（已存在配置优先）
    3. 从 OpenCode 桌面端配置补充视觉模型配置（.env 缺失的 key 才补）
    注意：工具会自行拼接 /v1/chat/completions，因此 base_url 统一去掉 /v1 后缀。
    """
    env = os.environ.copy()

    # 先加载 .env（套件自有配置优先）
    dotenv = _load_env_file(_ENV_FILE)
    for k, v in dotenv.items():
        if k in ('EDITOR_AI_BASE_URL', 'OPENAI_BASE_URL', 'AGNES_BASE_URL', 'GPT_IMAGE_BASE_URL'):
            if v.endswith('/v1'):
                v = v[:-3]
        env.setdefault(k, v)

    # 再补充 OpenCode 桌面端视觉配置（仅补缺失项）
    vision_cfg = _load_opencode_vision_config()
    for k, v in vision_cfg.items():
        env.setdefault(k, v)

    return env


def load_code_from_pyc(pyc_path: pathlib.Path):
    """跳过 pyc 头部（magic 4 + flags 4 + mtime 4 + size 4），用 marshal 加载 code object。"""
    with open(pyc_path, 'rb') as f:
        f.read(16)
        code = marshal.load(f)
    return code


def run_pyc_native(pyc_path: pathlib.Path, argv: list = None):
    """用 Python 3.11 venv 原生运行 .pyc（推荐路径）。"""
    py = find_py311_venv()
    if not py:
        return False
    cmd = [py, str(pyc_path)] + (argv or [])
    env = build_vision_env()
    try:
        r = subprocess.run(cmd, cwd=str(pyc_path.parent), env=env)
    except Exception:
        return False
    sys.exit(r.returncode)
    return True


def run_pyc_marshal(pyc_path: pathlib.Path, argv: list = None):
    """回退路径：marshal 手动加载 code object 执行。"""
    # 注入套件 .env + OpenCode 视觉配置到当前进程
    dotenv = _load_env_file(_ENV_FILE)
    vision_cfg = _load_opencode_vision_config()
    for k, v in {**dotenv, **vision_cfg}.items():
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

from pyc_loader import run_pyc
run_pyc(pathlib.Path(_pyc_path), sys.argv[1:])
'''
    built = []
    for pyc in sorted(tools_dir.glob('*.pyc')):
        py = pyc.with_suffix('.py')
        need_write = force or not py.exists() or 'pyc_loader' not in py.read_text(encoding='utf-8', errors='replace')
        if need_write:
            py.write_text(wrapper_template.format(pyc_name=pyc.name), encoding='utf-8')
            built.append(pyc.name)
    return built


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    target = pathlib.Path(sys.argv[1])
    if not target.exists():
        print(f"ERROR: {target} not found")
        sys.exit(1)
    run_pyc(target, sys.argv[2:])