"""Run the whole suite under a throwaway $HOME.

Several tests run the real installers, which write the global pointer
`$HOME/.aris/repo` by design. Without this, a test run repoints a developer's
existing ARIS install at the clone under test, or at a temp directory that is
gone a moment later (#449). Set at import time so subprocesses inherit it.
"""
import atexit
import os
import shutil
import tempfile

_home = tempfile.mkdtemp(prefix="aris-test-home-")
os.environ["HOME"] = _home
os.environ["USERPROFILE"] = _home
atexit.register(shutil.rmtree, _home, ignore_errors=True)
