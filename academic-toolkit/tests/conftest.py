# -*- coding: utf-8 -*-
"""仓库级 pytest 共享配置（2026-11-16 终检修复批）。

Windows 加固：pytest 临时目录清理器（_pytest.pathlib.cleanup_numbered_dir，
经 atexit 与新会话建目录两条路径触发）会对 ``pytest-current`` junction 逐项
``resolve().exists()``。当该 junction 指向的目标已被清理或句柄被瞬时占用时，
Windows 对损坏 reparse point 的 ``os.stat`` 报 ``PermissionError(WinError 5)``
而非 ``FileNotFoundError``，令 pytest 退出阶段抛出内部 traceback——不改变测试
结果与退出码，但污染 final_check 输出尾部。此处把死链清理包一层 ``OSError``
保护：个别条目清理失败仅影响临时目录回收，不影响任何测试断言。
"""
import _pytest.pathlib as _pl

_orig_cleanup_dead_symlinks = _pl.cleanup_dead_symlinks


def _safe_cleanup_dead_symlinks(root):
    try:
        _orig_cleanup_dead_symlinks(root)
    except OSError:
        # Windows：损坏/被占用的 junction（如 pytest-current）stat 报 WinError 5。
        pass


_pl.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
