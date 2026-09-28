from __future__ import annotations

import os
import subprocess
import sys

from _python_source_roots import REPO_ROOT
from tests.bash_test_support import bash_test_env, is_bash_command_args, normalize_bash_command_args


PYCACHE_ROOT = REPO_ROOT / ".tmp" / "pycache"
_RAW_SUBPROCESS_RUN = getattr(subprocess.run, "_vibe_raw_run", subprocess.run)

# Keep pytest runs hermetic for repo-owned Python sources.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ.setdefault("PYTHONPYCACHEPREFIX", str(PYCACHE_ROOT))
sys.dont_write_bytecode = True
sys.pycache_prefix = str(PYCACHE_ROOT)


def _is_powershell_command_args(command_args):
    if not isinstance(command_args, (list, tuple)) or not command_args:
        return False
    leaf = str(command_args[0]).replace("/", "\\").rsplit("\\", 1)[-1].casefold()
    return leaf in {"pwsh", "pwsh.exe", "powershell", "powershell.exe"}


def _utf8_text_subprocess_run(*args, **kwargs):
    command_args = None
    if args:
        command_args = args[0]
        args = (normalize_bash_command_args(command_args), *args[1:])
    elif "args" in kwargs:
        command_args = kwargs["args"]
        kwargs["args"] = normalize_bash_command_args(command_args)
    if kwargs.get("text") or kwargs.get("universal_newlines"):
        if is_bash_command_args(command_args):
            kwargs.setdefault("encoding", "utf-8")
            kwargs["env"] = bash_test_env(kwargs.get("env"))
        elif _is_powershell_command_args(command_args):
            kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return _RAW_SUBPROCESS_RUN(*args, **kwargs)


if not getattr(subprocess.run, "_vibe_bash_path_compat", False):
    _utf8_text_subprocess_run._vibe_bash_path_compat = True
    _utf8_text_subprocess_run._vibe_raw_run = _RAW_SUBPROCESS_RUN
    subprocess.run = _utf8_text_subprocess_run
