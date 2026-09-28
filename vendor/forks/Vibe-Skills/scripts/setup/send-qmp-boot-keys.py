#!/usr/bin/env python3

import json
import pathlib
import socket
import sys
import time


SOCKET_TIMEOUT_SECONDS = 2.0


def print_usage() -> None:
    print(
        "usage: send-qmp-boot-keys.py <qmp-socket> <key[,key]> <rounds> <interval-ms>",
        file=sys.stderr,
    )


def parse_positive_int(raw: str, label: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{label} must be an integer: {raw!r}") from None
    if value < 0:
        raise ValueError(f"{label} must be >= 0: {raw!r}")
    return value


def connect_qmp(qmp_socket: pathlib.Path) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(SOCKET_TIMEOUT_SECONDS)
    sock.connect(str(qmp_socket))
    sock.recv(4096)
    sock.sendall(b'{"execute":"qmp_capabilities"}\r\n')
    sock.recv(4096)
    return sock


def send_keypress(sock: socket.socket, boot_key: str) -> None:
    wire = json.dumps(
        {
            "execute": "input-send-event",
            "arguments": {
                "events": [
                    {
                        "type": "key",
                        "data": {
                            "down": True,
                            "key": {"type": "qcode", "data": boot_key},
                        },
                    },
                    {
                        "type": "key",
                        "data": {
                            "down": False,
                            "key": {"type": "qcode", "data": boot_key},
                        },
                    },
                ]
            },
        }
    ).encode() + b"\r\n"
    sock.sendall(wire)
    sock.recv(4096)


def main() -> int:
    if len(sys.argv) != 5:
        print_usage()
        return 2

    qmp_socket = pathlib.Path(sys.argv[1])
    boot_keys = [key for key in sys.argv[2].split(",") if key]
    try:
        rounds = parse_positive_int(sys.argv[3], "rounds")
        interval_ms = parse_positive_int(sys.argv[4], "interval-ms")
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        print_usage()
        return 2

    if not boot_keys or rounds <= 0:
        return 0

    for _ in range(120):
        if qmp_socket.exists():
            break
        time.sleep(0.25)
    else:
        print(f"[WARN] QMP socket did not appear: {qmp_socket}", file=sys.stderr)
        return 0

    had_success = False
    for _ in range(rounds):
        sock: socket.socket | None = None
        try:
            sock = connect_qmp(qmp_socket)
            for boot_key in boot_keys:
                send_keypress(sock, boot_key)
            had_success = True
        except (OSError, TimeoutError) as exc:
            print(f"[WARN] failed to send boot keys via {qmp_socket}: {exc}", file=sys.stderr)
        finally:
            if sock is not None:
                sock.close()

        time.sleep(interval_ms / 1000.0)

    return 0 if had_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
