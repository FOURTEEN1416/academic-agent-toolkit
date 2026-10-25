"""唯一路径锚点：engine 内所有模块一律从此取值，禁止各自推算 __file__ 深度。"""
from __future__ import annotations

from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
TOOLBOX_ROOT = ENGINE_DIR.parent
REPO_ROOT = TOOLBOX_ROOT.parent
MODEX_CORE = ENGINE_DIR / "modex-core"
