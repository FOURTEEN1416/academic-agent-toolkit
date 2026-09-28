#!/usr/bin/env python3

import json
import socket
import sys
import time


SOCKET_TIMEOUT_SECONDS = 2.0
ASCII_TO_KEYS = {
    " ": ["spc"],
    ".": ["dot"],
    "\\": ["backslash"],
    "/": ["slash"],
    "-": ["minus"],
    "_": ["shift", "minus"],
    ":": ["shift", "semicolon"],
}


def char_to_keys(ch: str) -> list[str]:
    if ch in ASCII_TO_KEYS:
        return ASCII_TO_KEYS[ch]
    if "a" <= ch <= "z":
        return [ch]
    if "0" <= ch <= "9":
        return [ch]
    raise ValueError(f"unsupported character: {ch!r}")


def send_event(sock: socket.socket, key: str, down: bool) -> None:
    wire = json.dumps(
        {
            "execute": "input-send-event",
            "arguments": {
                "events": [
                    {
                        "type": "key",
                        "data": {"down": down, "key": {"type": "qcode", "data": key}},
                    }
                ]
            },
        }
    ).encode() + b"\r\n"
    sock.sendall(wire)
    sock.recv(4096)


def print_usage() -> None:
    print("usage: send-qmp-text.py <qmp-socket> <text> [delay-ms]", file=sys.stderr)


def parse_delay_ms(argv: list[str]) -> int:
    if len(argv) <= 3:
        return 50
    try:
        delay_ms = int(argv[3])
    except ValueError:
        raise ValueError(f"delay-ms must be an integer: {argv[3]!r}") from None
    if delay_ms < 0:
        raise ValueError(f"delay-ms must be >= 0: {argv[3]!r}")
    return delay_ms


def validate_text(text: str) -> None:
    for ch in text:
        char_to_keys(ch)


def main() -> int:
    if len(sys.argv) < 3:
        print_usage()
        return 2

    qmp_socket = sys.argv[1]
    text = sys.argv[2]
    try:
        delay_ms = parse_delay_ms(sys.argv)
        validate_text(text)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        print_usage()
        return 2

    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(SOCKET_TIMEOUT_SECONDS)
        sock.connect(qmp_socket)
        sock.recv(4096)
        sock.sendall(b'{"execute":"qmp_capabilities"}\r\n')
        sock.recv(4096)

        for ch in text:
            keys = char_to_keys(ch)
            if len(keys) == 2 and keys[0] == "shift":
                send_event(sock, "shift", True)
                send_event(sock, keys[1], True)
                send_event(sock, keys[1], False)
                send_event(sock, "shift", False)
            else:
                send_event(sock, keys[0], True)
                send_event(sock, keys[0], False)
            time.sleep(delay_ms / 1000.0)

        send_event(sock, "ret", True)
        send_event(sock, "ret", False)
        return 0
    except (OSError, TimeoutError) as exc:
        print(f"[ERROR] failed to send QMP text via {qmp_socket}: {exc}", file=sys.stderr)
        return 1
    finally:
        if sock is not None:
            sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
