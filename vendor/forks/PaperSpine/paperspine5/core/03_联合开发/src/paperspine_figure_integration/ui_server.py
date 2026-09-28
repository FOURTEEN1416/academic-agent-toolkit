"""Loopback-only unified review UI for the integration workflow."""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .contracts import ContractError
from .coordinator import IntegrationCoordinator


UI_ROOT = Path(__file__).resolve().parents[2] / "ui"


def build_review_decision(
    snapshot: dict[str, Any],
    selections: dict[str, str],
    notes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the strict cross-project decision contract from UI selections."""
    review = snapshot.get("review") or {}
    requests = (snapshot.get("paper") or {}).get("requests") or {}
    review_figures = {
        item.get("figure_id"): item for item in review.get("figures", []) if item.get("figure_id")
    }
    figures: list[dict[str, Any]] = []
    for request in requests.get("figures", []):
        figure_id = request["figure_id"]
        if request.get("decision") == "keep":
            figures.append(
                {
                    "figure_id": figure_id,
                    "selected_candidate": "existing",
                    "panel_count": len(request.get("panels", [])),
                    "layout": "existing",
                    "panel_decisions": [
                        {"panel_id": panel["panel_id"], "action": "keep"}
                        for panel in request.get("panels", [])
                    ],
                    "notes": (notes or {}).get(
                        figure_id,
                        "Existing publication-ready figure retained by the PaperSpine story decision.",
                    ),
                    "confirmed": True,
                }
            )
            continue
        candidate_id = selections.get(figure_id)
        review_figure = review_figures.get(figure_id, {})
        candidate = (review_figure.get("candidates") or {}).get(candidate_id)
        if candidate_id not in {"A", "B", "C"} or not isinstance(candidate, dict):
            raise ContractError(f"review selection is missing or invalid for {figure_id}")
        panels = candidate.get("panels") or []
        panel_ids = candidate.get("panel_ids") or [panel.get("panel_id") for panel in panels]
        panel_ids = [panel_id for panel_id in panel_ids if panel_id]
        figures.append(
            {
                "figure_id": figure_id,
                "selected_candidate": candidate_id,
                "panel_count": len(panel_ids),
                "layout": candidate.get("layout", "auto"),
                "panel_decisions": [
                    {"panel_id": panel_id, "action": "keep"} for panel_id in panel_ids
                ],
                "notes": (notes or {}).get(figure_id, ""),
                "confirmed": True,
            }
        )
    if not figures:
        raise ContractError("no figure request is available for review")
    return {
        "schema_version": "1.0",
        "project_id": requests.get("paper_id"),
        "review_scope": "all_figures",
        "status": "confirmed",
        "figures": figures,
    }


def _safe_file(root: Path, relative: str) -> Path | None:
    try:
        target = (root / unquote(relative).lstrip("/")).resolve()
        target.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return target if target.is_file() else None


def make_handler(coordinator: IntegrationCoordinator) -> type[BaseHTTPRequestHandler]:
    figmirror_root = coordinator.figmirror.job_dir.resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "PaperSpineFigureUI/1.0"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 1_000_000:
                    raise ContractError("request body is too large")
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError) as exc:
                raise ContractError("request body must be a JSON object") from exc
            if not isinstance(payload, dict):
                raise ContractError("request body must be a JSON object")
            return payload

        def _same_origin(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return True
            parsed = urlparse(origin)
            return parsed.hostname in {"127.0.0.1", "localhost"} and parsed.port == self.server.server_port

        def _serve(self, path: Path) -> None:
            body = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in {"application/javascript", "image/svg+xml"}:
                content_type += "; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route == "/api/snapshot":
                try:
                    self._json(coordinator.snapshot())
                except Exception as exc:  # HTTP boundary converts domain errors to JSON.
                    self._json({"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            if route == "/api/body-contract":
                try:
                    contract = coordinator.body_contract()
                    self._json(contract or {"status": "FAIL", "error": "body contract is unavailable"})
                except Exception as exc:
                    self._json({"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            if route == "/api/workflow":
                try:
                    self._json(coordinator.workflow_snapshot())
                except Exception as exc:
                    self._json({"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            if route == "/api/publication-cycle":
                try:
                    self._json(coordinator.publication_cycle_snapshot())
                except Exception as exc:
                    self._json({"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            if route.startswith("/figmirror/"):
                path = _safe_file(figmirror_root, route.removeprefix("/figmirror/"))
            else:
                relative = "index.html" if route in {"", "/"} else route.lstrip("/")
                path = _safe_file(UI_ROOT, relative)
            if path is None:
                self.send_error(HTTPStatus.NOT_FOUND)
            else:
                self._serve(path)

        def do_POST(self) -> None:  # noqa: N802
            if not self._same_origin():
                self._json({"status": "FAIL", "error": "cross-origin requests are not accepted"}, HTTPStatus.FORBIDDEN)
                return
            route = urlparse(self.path).path
            try:
                body = self._body()
                if route == "/api/configuration":
                    configuration = body.get("configuration")
                    if not isinstance(configuration, dict):
                        raise ContractError("configuration must be a JSON object")
                    result = coordinator.save_configuration(configuration)
                elif route == "/api/advance":
                    result = coordinator.resume() if coordinator.state()["stage"] == "blocked" else coordinator.advance()
                elif route == "/api/decision":
                    decision = body.get("decision")
                    if not isinstance(decision, dict):
                        decision = build_review_decision(
                            coordinator.snapshot(),
                            body.get("selections") or {},
                            body.get("notes") or {},
                        )
                    result = coordinator.record_decision(decision)
                elif route == "/api/signal":
                    result = coordinator.record_signal(body)
                elif route == "/api/publication-cycle":
                    result = coordinator.invoke_publication_cycle(body)
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._json(result)
            except Exception as exc:  # HTTP boundary converts domain errors to JSON.
                self._json({"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST)

    return Handler


def create_server(job_path: str | Path, *, port: int = 0) -> ThreadingHTTPServer:
    coordinator = IntegrationCoordinator(job_path)
    coordinator.initialize()
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(coordinator))


def serve(job_path: str | Path, *, port: int = 0, open_browser: bool = False) -> None:
    server = create_server(job_path, port=port)
    address = f"http://127.0.0.1:{server.server_port}/"
    print(json.dumps({"status": "READY", "address": address}, ensure_ascii=False), flush=True)
    if open_browser:
        threading.Timer(0.2, webbrowser.open, args=(address,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
