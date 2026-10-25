"""兼容层（裁决 6.4-C）：旧路径 engine.audit_store 不变；实现见 engine.audit.audit_store。勿在此实现业务逻辑。"""
from __future__ import annotations
import sys as _sys
if __name__ == '__main__':
    from pathlib import Path as _Path
    _root = str(_Path(__file__).resolve().parents[1])
    if _root not in _sys.path:
        _sys.path.insert(0, _root)
    import runpy as _runpy
    _runpy.run_module('engine.audit.audit_store', run_name='__main__', alter_sys=False)
elif __package__:
    from .audit import audit_store as _target
    _sys.modules[__name__] = _target
else:
    from pathlib import Path as _Path
    _root = str(_Path(__file__).resolve().parents[1])
    if _root not in _sys.path:
        _sys.path.insert(0, _root)
    from engine.audit import audit_store as _target
    globals().update({_k: _v for _k, _v in vars(_target).items() if not _k.startswith('__')})
    _sys.modules[__name__] = _target
