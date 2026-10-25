"""兼容层（裁决 6.4-C）：旧路径 engine.approvals 不变；实现见 engine.candidates.approvals。勿在此实现业务逻辑。"""
from __future__ import annotations
import sys as _sys
if __name__ == '__main__':
    from pathlib import Path as _Path
    _root = str(_Path(__file__).resolve().parents[1])
    if _root not in _sys.path:
        _sys.path.insert(0, _root)
    import runpy as _runpy
    _runpy.run_module('engine.candidates.approvals', run_name='__main__', alter_sys=False)
elif __package__:
    from .candidates import approvals as _target
    _sys.modules[__name__] = _target
else:
    from pathlib import Path as _Path
    _root = str(_Path(__file__).resolve().parents[1])
    if _root not in _sys.path:
        _sys.path.insert(0, _root)
    from engine.candidates import approvals as _target
    globals().update({_k: _v for _k, _v in vars(_target).items() if not _k.startswith('__')})
    _sys.modules[__name__] = _target
