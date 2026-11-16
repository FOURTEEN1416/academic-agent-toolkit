#!/usr/bin/env python3
"""with_server.py — start one or more dev servers, wait for their ports, run an
automation script, then tear the servers down.

Usage:
    python scripts/with_server.py --server "npm run dev" --port 5173 -- python your_automation.py

    python scripts/with_server.py \
      --server "cd backend && python server.py" --port 3000 \
      --server "cd frontend && npm run dev" --port 5173 \
      -- python your_automation.py

The automation script (everything after ``--``) runs only after every declared
port accepts TCP connections (or its server exits early, which fails fast).
Servers are terminated when the automation script finishes.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import threading
import time

DEFAULT_TIMEOUT = 120.0
POLL_INTERVAL = 0.25


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def _wait_for_port(port: int, proc: subprocess.Popen, timeout: float) -> None:
    """Block until ``port`` accepts connections, ``proc`` exits, or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_open(port):
            return
        if proc.poll() is not None:
            raise RuntimeError(
                f"server for port {port} exited early with code {proc.returncode}"
            )
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"port {port} not ready within {timeout:.0f}s")


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="with_server.py",
        description=(
            "Start one or more dev servers, wait until their ports are ready, "
            "run an automation script, then stop the servers."
        ),
        epilog=(
            "Example:\n"
            "  python scripts/with_server.py --server \"npm run dev\" --port 5173"
            " -- python your_automation.py\n"
            "\n"
            "Repeat --server/--port pairs for multiple servers (backend+frontend)."
        ),
    )
    parser.add_argument(
        "--server",
        action="append",
        required=True,
        metavar="CMD",
        help="shell command that starts a server; repeat for multiple servers",
    )
    parser.add_argument(
        "--port",
        action="append",
        required=True,
        type=int,
        metavar="N",
        help="TCP port the server must listen on; one per --server, same order",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SEC",
        help=f"seconds to wait for each port (default: {DEFAULT_TIMEOUT:.0f})",
    )
    parser.add_argument(
        "automation",
        nargs=argparse.REMAINDER,
        metavar="-- SCRIPT [ARGS...]",
        help="automation command to run after all ports are ready (after --)",
    )
    args = parser.parse_args(argv)

    if len(args.server) != len(args.port):
        parser.error(
            f"--server count ({len(args.server)}) must match --port count ({len(args.port)})"
        )

    automation = args.automation
    if automation and automation[0] == "--":
        automation = automation[1:]
    if not automation:
        parser.error("no automation command given; add '-- python your_automation.py'")

    procs: list[subprocess.Popen] = []
    try:
        for cmd, port in zip(args.server, args.port):
            print(f"[with_server] starting: {cmd} (expecting port {port})", flush=True)
            proc = subprocess.Popen(cmd, shell=True)
            procs.append(proc)
            _wait_for_port(port, proc, args.timeout)
            print(f"[with_server] port {port} ready", flush=True)

        print(f"[with_server] running: {' '.join(automation)}", flush=True)
        result = subprocess.run(automation)
        return result.returncode
    except (RuntimeError, TimeoutError) as exc:
        print(f"[with_server] ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print("[with_server] interrupted", file=sys.stderr, flush=True)
        return 130
    finally:
        for proc in procs:
            _terminate(proc)


if __name__ == "__main__":
    sys.exit(main())
