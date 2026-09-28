"""Loopback-only HTTP server for FigMirror review artifacts."""

from __future__ import annotations

import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Timer


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def resolve_review_target(root: str | Path, index: str = "review/index.html") -> tuple[Path, str]:
    review_root = Path(root).resolve()
    if not review_root.is_dir():
        raise ValueError(f"review root is not a directory: {review_root}")
    index_path = (review_root / index).resolve()
    try:
        relative = index_path.relative_to(review_root)
    except ValueError as exc:
        raise ValueError("review index must stay inside the review root") from exc
    if not index_path.is_file():
        raise ValueError(f"review index does not exist: {index_path}")
    return review_root, relative.as_posix()


def serve_review(
    root: str | Path,
    *,
    index: str = "review/index.html",
    port: int = 0,
    open_browser: bool = False,
) -> None:
    """Serve one FigMirror job on loopback so local downloads work safely."""

    review_root, relative_index = resolve_review_target(root, index)
    if not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    handler = partial(QuietHandler, directory=review_root)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_port}/{relative_index}"
    print(f"FigMirror review: {url}")
    print(f"Serving only: {review_root}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

