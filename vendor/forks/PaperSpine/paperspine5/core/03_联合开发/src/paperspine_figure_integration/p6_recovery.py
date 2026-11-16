"""Local command coordination and safe failure vocabulary; no academic workflow."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path


class WorkFailure(Exception):
    """A trusted effect boundary reports whether dispatch definitely did not happen.

    Never put provider messages into the public failure. Unknown is the default:
    a timeout alone cannot prove that an external effect did not happen.
    """
    def __init__(self, kind: str, *, not_started: bool = False):
        if kind not in {"network", "model", "tool", "process-restart"}:
            raise ValueError("unsupported failure kind")
        self.kind = kind
        self.not_started = not_started
        super().__init__(kind)


@contextmanager
def command_lock(database: Path, *, blocking: bool = True):
    """OS-released lock spanning journal, legacy effect and event commit.

    The lock is local coordination only. SQLite events remain domain authority.
    A killed owner releases the lock; its durable intent remains discoverable.
    """
    lock = database.with_suffix(database.suffix + ".command-lock")
    with lock.open("a+b") as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0"); handle.flush()
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if not blocking:
                        yield False
                        return
                    time.sleep(0.05)
            try:
                yield True
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
