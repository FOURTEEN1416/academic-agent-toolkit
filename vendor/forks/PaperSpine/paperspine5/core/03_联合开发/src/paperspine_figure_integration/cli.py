"""Command-line interface for the integration coordinator."""

from __future__ import annotations

import argparse
import json
from typing import Any

from .contracts import ContractError, load_integration_job, load_json
from .coordinator import IntegrationCoordinator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PaperSpine × PaperFigure V5 integration coordinator")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "init", "advance", "resume", "status", "body-contract", "workflow"):
        current = subparsers.add_parser(command)
        current.add_argument("job")
        if command == "init":
            current.add_argument("--force", action="store_true")
    decision = subparsers.add_parser("decision")
    decision.add_argument("job")
    decision.add_argument("decision")
    signal = subparsers.add_parser("signal")
    signal.add_argument("job")
    signal.add_argument("signal")
    publication_describe = subparsers.add_parser("publication-cycle-describe")
    publication_describe.add_argument("job")
    publication_invoke = subparsers.add_parser("publication-cycle-invoke")
    publication_invoke.add_argument("job")
    publication_invoke.add_argument("request")
    host_next = subparsers.add_parser("host-next")
    host_next.add_argument("job")
    host_next.add_argument("--host", choices=("codex", "claude-code", "dsh", "standalone-skill"))
    serve = subparsers.add_parser("serve")
    serve.add_argument("job")
    serve.add_argument("--port", type=int, default=0)
    serve.add_argument("--open", action="store_true")
    return parser.parse_args()


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    args = parse_args()
    try:
        if args.command == "validate":
            job = load_integration_job(args.job)
            result = {"status": "PASS", "job_id": job["job_id"], "project_root": job["project_root"]}
        elif args.command == "serve":
            from .ui_server import serve

            serve(args.job, port=args.port, open_browser=args.open)
            return 0
        else:
            coordinator = IntegrationCoordinator(args.job)
            if args.command == "init":
                result = coordinator.initialize(force=args.force)
            elif args.command == "advance":
                result = coordinator.advance()
            elif args.command == "resume":
                result = coordinator.resume()
            elif args.command == "status":
                result = coordinator.snapshot()
            elif args.command == "body-contract":
                result = coordinator.body_contract()
            elif args.command == "workflow":
                result = coordinator.workflow_snapshot()
            elif args.command == "decision":
                result = coordinator.record_decision(load_json(args.decision))
            elif args.command == "signal":
                result = coordinator.record_signal(load_json(args.signal))
            elif args.command == "publication-cycle-describe":
                result = coordinator.publication_cycle_snapshot()
            elif args.command == "publication-cycle-invoke":
                result = coordinator.invoke_publication_cycle(load_json(args.request))
            elif args.command == "host-next":
                result = coordinator.host_next(args.host)
            else:  # pragma: no cover
                raise ContractError(f"unsupported command: {args.command}")
        _print(result)
        return 1 if result.get("stage") == "blocked" else 0
    except (ContractError, OSError, ValueError) as exc:
        _print({"status": "FAIL", "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
