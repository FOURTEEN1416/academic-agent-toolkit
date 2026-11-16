#!/usr/bin/env python3
"""CLI for deterministic bundle and explicit-profile lifecycle candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .lifecycle import LifecycleManager, doctor
    from .suite_release import build_bundle, verify_bundle
    from .user_update import UserUpdateManager, make_update_feed
    from .product_runtime import prepare as prepare_product, serve as serve_product
except ImportError:  # Direct execution from an installed bundle.
    from lifecycle import LifecycleManager, doctor  # type: ignore
    from suite_release import build_bundle, verify_bundle  # type: ignore
    from user_update import UserUpdateManager, make_update_feed  # type: ignore
    from product_runtime import prepare as prepare_product, serve as serve_product  # type: ignore


def _add_surface_update_options(parser: argparse.ArgumentParser, install_kind: str) -> None:
    if install_kind == "plugin":
        parser.add_argument("--marketplace-path")
    else:
        parser.add_argument("--skill-root")
    parser.add_argument(
        "--control-root",
        default=str(Path.home() / ".paperspine5" / f"{install_kind}-updates"),
        help=f"independent {install_kind} receipt, exact-bundle, and rollback state root",
    )


def _add_surface_commands(subparsers: Any, install_kind: str) -> None:
    check = subparsers.add_parser(
        f"{install_kind}-update-check",
        help=f"read-only check for the standalone {install_kind} installation",
    )
    check.add_argument("--source", required=True, help="exact suite ZIP or kind-bound update feed")
    _add_surface_update_options(check, install_kind)

    upgrade = subparsers.add_parser(
        f"{install_kind}-upgrade",
        help=f"transactionally upgrade only the {install_kind} installation",
    )
    upgrade.add_argument("--source", required=True, help="exact suite ZIP or kind-bound update feed")
    upgrade.add_argument("--operation-id", required=True)
    upgrade.add_argument("--confirm", action="store_true")
    _add_surface_update_options(upgrade, install_kind)

    rollback = subparsers.add_parser(
        f"{install_kind}-upgrade-rollback",
        help=f"restore only the latest committed {install_kind} upgrade",
    )
    rollback.add_argument("--operation-id", required=True)
    rollback.add_argument("--confirm", action="store_true")
    _add_surface_update_options(rollback, install_kind)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PaperSpine5 W7 candidate release lifecycle")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build one deterministic allowlisted suite zip")
    build.add_argument("--source-root", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--dsh-output", help="also project a native DSH bundle from this suite")

    dsh = subparsers.add_parser("build-dsh", help="project DSH from a verified platform suite")
    dsh.add_argument("--bundle", required=True)
    dsh.add_argument("--output", required=True)

    verify = subparsers.add_parser("verify-bundle", help="verify exact suite bytes")
    verify.add_argument("--bundle", required=True)

    feed = subparsers.add_parser("make-update-feed", help="write a hash-bound update feed")
    feed.add_argument("--bundle", required=True)
    feed.add_argument("--output", required=True)
    feed.add_argument("--install-kind", choices=("plugin", "skill"), required=True)
    feed.add_argument("--bundle-url")

    inspect = subparsers.add_parser("doctor", help="dry-run an explicit local profile")
    inspect.add_argument("--profile-root", required=True)
    inspect.add_argument("--bundle")

    install = subparsers.add_parser("install", help="transactionally activate into an explicit profile")
    install.add_argument("--profile-root", required=True)
    install.add_argument("--bundle", required=True)
    install.add_argument("--operation-id", required=True)

    update = subparsers.add_parser("update", help="transactionally update an explicit profile")
    update.add_argument("--profile-root", required=True)
    update.add_argument("--bundle", required=True)
    update.add_argument("--operation-id", required=True)
    update.add_argument("--confirm", action="store_true")

    reload_parser = subparsers.add_parser("reload", help="acknowledge the profile-local reload marker")
    reload_parser.add_argument("--profile-root", required=True)
    reload_parser.add_argument("--operation-id", required=True)

    rollback = subparsers.add_parser("rollback", help="switch to a compatible installed build")
    rollback.add_argument("--profile-root", required=True)
    rollback.add_argument("--target-build-id", required=True)
    rollback.add_argument("--operation-id", required=True)

    uninstall = subparsers.add_parser("uninstall", help="remove suite binaries while retaining task data")
    uninstall.add_argument("--profile-root", required=True)
    uninstall.add_argument("--operation-id", required=True)

    first_start = subparsers.add_parser("first-start", help="initialize and verify the active PaperSpine product")
    first_start.add_argument("--profile-root", required=True)

    serve = subparsers.add_parser("serve", help="run the active PaperSpine MCP or business facade")
    serve.add_argument("--profile-root", required=True)
    serve.add_argument("--mode", choices=("mcp-stdio", "business-http"), required=True)
    serve.add_argument("--principal-id", default="local-user")
    serve.add_argument("--session-id", default="local-session")
    serve.add_argument("--reviewer-id", default=None)
    serve.add_argument("--port", type=int, default=0)

    _add_surface_commands(subparsers, "plugin")
    _add_surface_commands(subparsers, "skill")
    return parser


def run(arguments: argparse.Namespace) -> dict[str, Any]:
    if arguments.command == "first-start":
        return prepare_product(arguments.profile_root)
    if arguments.command == "serve":
        serve_product(
            arguments.profile_root, arguments.mode, principal_id=arguments.principal_id,
            session_id=arguments.session_id, reviewer_id=arguments.reviewer_id,
            port=arguments.port,
        )
        return {"status": "PASS"}
    if arguments.command in {"build", "build-dsh"}:
        try:
            from .dsh_release import build_dsh_bundle
        except ImportError:
            from dsh_release import build_dsh_bundle
        if arguments.command == "build-dsh":
            return build_dsh_bundle(arguments.bundle, arguments.output)
        result = build_bundle(arguments.source_root, arguments.output)
        if arguments.dsh_output:
            result["dsh"] = build_dsh_bundle(arguments.output, arguments.dsh_output)
        return result
    if arguments.command == "verify-bundle":
        return verify_bundle(arguments.bundle)
    if arguments.command == "make-update-feed":
        return make_update_feed(
            arguments.bundle,
            arguments.output,
            install_kind=arguments.install_kind,
            bundle_url=arguments.bundle_url,
        )
    if arguments.command == "doctor":
        return doctor(arguments.profile_root, bundle=arguments.bundle)
    if arguments.command in {"plugin-update-check", "skill-update-check"}:
        install_kind = arguments.command.split("-", 1)[0]
        return UserUpdateManager(install_kind, arguments.control_root).check(
            arguments.source,
            marketplace_path=getattr(arguments, "marketplace_path", None),
            skill_root=getattr(arguments, "skill_root", None),
        )
    if arguments.command in {"plugin-upgrade", "skill-upgrade"}:
        install_kind = arguments.command.split("-", 1)[0]
        return UserUpdateManager(install_kind, arguments.control_root).upgrade(
            arguments.source,
            operation_id=arguments.operation_id,
            confirmed=arguments.confirm,
            marketplace_path=getattr(arguments, "marketplace_path", None),
            skill_root=getattr(arguments, "skill_root", None),
        )
    if arguments.command in {"plugin-upgrade-rollback", "skill-upgrade-rollback"}:
        install_kind = arguments.command.split("-", 1)[0]
        return UserUpdateManager(install_kind, arguments.control_root).rollback(
            operation_id=arguments.operation_id,
            confirmed=arguments.confirm,
        )
    manager = LifecycleManager(arguments.profile_root)
    if arguments.command == "install":
        return manager.install(arguments.bundle, operation_id=arguments.operation_id)
    if arguments.command == "update":
        return manager.update(
            arguments.bundle,
            operation_id=arguments.operation_id,
            confirmed=arguments.confirm,
        )
    if arguments.command == "reload":
        return manager.reload(operation_id=arguments.operation_id)
    if arguments.command == "rollback":
        return manager.rollback(arguments.target_build_id, operation_id=arguments.operation_id)
    if arguments.command == "uninstall":
        return manager.uninstall(operation_id=arguments.operation_id, retain_data=True)
    raise RuntimeError(f"unsupported command: {arguments.command}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    arguments = _parser().parse_args()
    stdio_server = arguments.command == "serve" and arguments.mode == "mcp-stdio"
    try:
        payload = run(arguments)
        if stdio_server:
            # MCP owns stdout until EOF; a CLI footer is not a protocol message.
            return 0
        status = payload.get("status")
        code = 0 if status in {"PASS", "READY", "committed", "noop"} else 1
    except Exception as exc:
        if stdio_server:
            sys.stderr.write("PaperSpine connection stopped. Reconnect to resume the saved task.\n")
            return 1
        payload = {
            "contract": "paperspine5.release-cli-error",
            "schema_version": "1.0",
            "status": "FAIL",
            "error": str(exc),
            "external_action_authorized": False,
        }
        code = 1
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
