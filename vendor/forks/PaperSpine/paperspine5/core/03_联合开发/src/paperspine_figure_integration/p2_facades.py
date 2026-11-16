"""P2 transport facades for the P1 OpenTask/read vertical slice.

Both transports are deliberately thin: identity is injected by the trusted
host/server process, and all state reads and writes go to one ApplicationService.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Annotated, Any, Mapping
from urllib.parse import parse_qs, quote, unquote, urlparse
from uuid import uuid4

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field, WithJsonSchema

from .p1_application import (
    ApplicationService,
    DomainError,
    DomainEventStore,
    LegacyStageAdapter,
    agent_open_task,
    agent_execute,
    agent_request_decision,
    business_open_task,
    business_execute,
    business_request_decision,
    business_resolve_decision,
    reviewer_execute,
    _reject_untrusted_identity,
)
from .product_kernel import ContractError, ProductKernel
from .p6_recovery import command_lock
from .product_runner import ProductRunner
from .delivery_manifest import build_delivery_manifest
from .figure_read_facade import resolve_reference_content
from .quality_readiness import identity_provenance_sha256
from .skill_bridge import (_figure_candidates, figure_reference_catalog, configuration_readiness,
                           list_bridge_files)


_SAFE_HANDOFF_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _require_user_configuration(service: ApplicationService, task_id: str) -> dict[str, Any]:
    """Fail closed before scientific Runner work without a Web confirmation."""
    task = service.get_task(task_id)
    readiness = configuration_readiness(task)
    if not readiness["ready"]:
        raise DomainError(
            "decision_required",
            "请在同一任务的 PaperSpine Web 配置页保存配置后再继续论文执行。",
            category="decision", task_id=task_id,
            current_version=task.get("task_version"), details={
                "next_action": "open_same_task_web_configuration",
                "task_version": task.get("task_version"),
                "configuration_source": readiness["source"],
                "configuration_readiness": readiness,
                "wait_with": "paperspine_wait_for_task_change",
            },
        )
    return task


def _business_host_handoff(service: ApplicationService, task_id: str, *,
                           expected_revision: int | None = None,
                           expected_build_id: str | None = None) -> dict[str, Any]:
    """Locate the same Skill task without requiring an academic Runner issue."""
    if not _SAFE_HANDOFF_TASK_ID.fullmatch(task_id):
        raise DomainError("validation_failed", "任务编号无效。", category="validation", task_id=task_id)
    task = service.get_task(task_id)
    kernel = service.legacy_adapter._kernel
    kernel_task = kernel.get_task(task_id)
    build_id = kernel.product_manifest.get("build_id")
    if ((expected_revision is not None and expected_revision not in
         {task.get("task_version"), kernel_task.get("revision")})
            or (expected_build_id is not None and expected_build_id != build_id)):
        raise DomainError("version_conflict", "任务已更新，请读取最新任务继续。",
                          category="conflict", task_id=task_id, retryable=True)
    bridge = task.get("skill_bridge") or {}
    return {"mode": "current_host", "task_id": task_id,
            "revision": task["task_version"], "task_version": task["task_version"],
            "stage": task.get("stage"), "build_id": build_id,
            "output_dir": str(kernel.user_data_root),
            "workspace_root": kernel_task["workspace_root"],
            "workflow_directory": bridge.get("directory"),
            "host_binding": {"user_data_root": str(kernel.user_data_root),
                             "core_root": str(kernel.core_root),
                             "domain_database": str(service.event_store.database_path)},
            "web_path": bridge.get("web_path"),
            "instruction": "请用唯一 paper-spine Skill 接手同一论文任务，不另建任务。先核对下方服务定位与任务 ID，读取最新配置、材料授权、选择、反馈、实际成果和下一步所需工作笔记；不假定获得原 Agent 的聊天记忆。保留有效成果和用户决定，只有当前宿主在已授权范围内执行后才算继续工作。"}


def build_application(*, user_data_root: str | Path, core_root: str | Path,
                      domain_database: str | Path, contracts_root: str | Path,
                      initialize_on_startup: bool = True,
                      ) -> tuple[ApplicationService, ProductKernel]:
    kernel = ProductKernel(user_data_root, core_root=core_root, recover_on_startup=initialize_on_startup)
    runner = ProductRunner(kernel)
    service = ApplicationService(
        DomainEventStore(domain_database), LegacyStageAdapter(kernel, runner),
        contracts_root=contracts_root, initialize_on_startup=initialize_on_startup,
    )
    return service, kernel


def _import_legacy_task(
    service: ApplicationService,
    request: Mapping[str, Any],
    *,
    principal_id: str,
    session_id: str,
    surface: str,
) -> dict[str, Any]:
    """Import one explicitly supplied legacy job into this P2 runtime.

    ``ProductKernel.import_legacy_job`` owns the copy-on-write snapshot and
    fixes all output paths below the configured ``user_data_root``.  This
    facade deliberately does not accept an output-root override and does not
    ingest or execute the imported academic state.  A domain ``resume`` event
    is recorded after the kernel import so the new task is visible through the
    same P2 REST/MCP read surfaces.
    """
    _reject_untrusted_identity(request)
    allowed = {"command_id", "job_path", "title", "description", "task_id", "host"}
    unknown = sorted(set(request) - allowed)
    if unknown:
        raise DomainError(
            "validation_failed", "legacy import 请求包含不支持的字段。",
            category="validation", command_id=request.get("command_id"),
            details={"rejected_fields": unknown},
        )
    command_id = request.get("command_id")
    job_path = request.get("job_path")
    if not isinstance(command_id, str) or not command_id:
        raise DomainError("validation_failed", "legacy import 需要 command_id。",
                          category="validation")
    if not isinstance(job_path, str) or not job_path.strip():
        raise DomainError("validation_failed", "legacy import 需要 job_path。",
                          category="validation", command_id=command_id)
    kernel = service.legacy_adapter._kernel
    try:
        imported = kernel.import_legacy_job(
            job_path,
            command_id=command_id,
            title=request.get("title"),
            description=request.get("description"),
            task_id=request.get("task_id"),
            host=request.get("host") or "codex",
        )
    except (ContractError, OSError, ValueError) as exc:
        raise DomainError("validation_failed", str(exc), category="validation",
                          command_id=command_id) from exc
    imported_task = imported.get("task") if isinstance(imported, Mapping) else None
    if not isinstance(imported_task, Mapping) or not imported_task.get("task_id"):
        raise DomainError("effect_failed", "legacy import 未返回有效任务。",
                          category="effect", command_id=command_id, retryable=False)
    task_id = str(imported_task["task_id"])
    # Materialize the Runner's typed migration blocker as a read-only setup
    # step. This makes a subsequently opened task URL show the same blocker
    # through GET .../runner; it does not ingest files or start academic work.
    runner = service.legacy_adapter._runner
    if runner is not None:
        bootstrap_id = "legacy-bootstrap-" + hashlib.sha256(
            command_id.encode("utf-8")
        ).hexdigest()[:24]
        try:
            runner.bootstrap(
                task_id,
                command_id=bootstrap_id,
                expected_revision=0,
                writer_id="p2-legacy-import",
                actor={"actor_id": principal_id,
                       "surface": "mcp" if surface == "agent" else "web"},
            )
        except (ContractError, OSError, ValueError) as exc:
            raise DomainError("effect_failed", "无法初始化导入任务的迁移阻塞状态。",
                              category="effect", task_id=task_id,
                              command_id=command_id, retryable=True) from exc
        finally:
            service.legacy_adapter._kernel.release_writer_lease(
                task_id, "p2-legacy-import"
            )
    # The kernel import and P2 event store are separate persistence layers.
    # Open the imported task in resume mode to materialize its read projection;
    # this does not claim the legacy academic files were ingested.
    domain_command_id = "legacy-open-" + hashlib.sha256(
        command_id.encode("utf-8")
    ).hexdigest()[:24]
    open_request = {
        "task_id": task_id,
        "command_id": domain_command_id,
        "schema_version": "1.0",
        "expected_version": 0,
        "payload": {"mode": "resume"},
    }
    try:
        if surface == "agent":
            agent_open_task(service, open_request, principal_id=principal_id)
        else:
            business_open_task(
                service, open_request, principal_id=principal_id,
                session_id=session_id,
            )
        projection = service.get_task(task_id)
    except DomainError:
        raise
    except Exception as exc:  # pragma: no cover - defensive transport boundary
        raise DomainError("effect_failed", "无法登记导入任务的公开投影。",
                          category="effect", task_id=task_id,
                          command_id=command_id, retryable=True) from exc
    blocker = next(
        (item for item in imported_task.get("state", {}).get("issues", [])
         if isinstance(item, Mapping) and item.get("status") == "open"),
        None,
    )
    return {
        "status": "COMMITTED",
        "task_id": task_id,
        "projection": projection,
        "migration_receipt": imported.get("migration_receipt"),
        "blocker": blocker,
        "execution_started": False,
        "source_mutated": False,
    }


def create_mcp_server(service: ApplicationService, *, principal_id: str,
                      reviewer_id: str | None = None) -> MCPServer:
    server = MCPServer(
        "paperspine-p2", title="PaperSpine P2 Agent facade", version="2.0.0",
        instructions="Open and read PaperSpine tasks through the shared application service.",
    )

    def inline(value: Any, resolver: Any) -> Any:
        if isinstance(value, list):
            return [inline(item, resolver) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            resolved = resolver.lookup(value["$ref"])
            return inline(resolved.contents, resolved.resolver)
        return {key: inline(item, resolver) for key, item in value.items()
                if key not in {"$id", "$schema", "$defs"}}

    def register_command(fn: Any, name: str, command_type: str) -> None:
        # Advertise the same payload contract that actually validates commands.
        # An untyped `request: object` otherwise leaves a fresh host guessing.
        validator = service._v11_validators["command"]
        schema = validator.schema

        payload = next(branch["then"]["properties"]["payload"] for branch in schema["allOf"]
                       if branch["if"]["properties"]["command_type"]["const"] == command_type)
        fields = ("schema_version", "command_id", "task_id", "expected_version", "expected_revision")
        request_schema = {"type": "object", "additionalProperties": False,
                          "required": ["schema_version", "command_id", "task_id", "expected_version", "payload"],
                          "properties": {key: inline(schema["properties"][key], validator._resolver) for key in fields}}
        request_schema["properties"]["payload"] = inline(payload, validator._resolver)
        fn.__annotations__["request"] = Annotated[dict[str, Any], WithJsonSchema(request_schema)]
        server.add_tool(fn, name=name, structured_output=True)

    def open_task(request: dict[str, Any]) -> dict[str, Any]:
        """Open or resume one task. Host identity is not accepted in request."""
        try:
            result = agent_open_task(service, request, principal_id=principal_id)
            # Reads are enriched through the same compatibility projection as
            # REST.  Returning the enriched view here keeps the two facades
            # byte-for-byte aligned after a task is opened.
            if result.get("task_id"):
                result = dict(result)
                result["projection"] = service.get_task(result["task_id"])
            return result
        except DomainError as exc:
            return {"error": exc.to_dict()}

    register_command(open_task, "paperspine_open_task", "OpenTask")

    def check_delivery(request: dict[str, Any]) -> dict[str, Any]:
        """Read-only candidate ZIP check at the returned task_version, before publish.

        Inspect candidate issues, nested_archives, missing current bytes, pending
        publication and every unreviewed current artifact (including figures).
        This does not prepare delivery or authorize sharing. Future publication
        and review change the task snapshot; repeat the check after those changes.
        """
        try:
            return service.check_delivery(request)
        except DomainError as exc:
            return {'error': exc.to_dict()}

    check_validator = service._delivery_check_validator
    check_delivery.__annotations__['request'] = Annotated[
        dict[str, Any], WithJsonSchema(inline(check_validator.schema, check_validator._resolver))]
    server.add_tool(check_delivery, name='paperspine_check_delivery', structured_output=True,
                    annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                                idempotent_hint=True, open_world_hint=False))

    @server.tool(name="paperspine_get_task", structured_output=True)
    def get_task(task_id: str) -> dict[str, Any]:
        """Read one task projection from the shared event store."""
        try:
            return service.get_task(task_id)
        except DomainError as exc:
            return {"error": exc.to_dict()}

    @server.tool(name="paperspine_wait_for_task_change", structured_output=True,
                 annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                             idempotent_hint=True, open_world_hint=False))
    async def wait_for_task_change(
        task_id: Annotated[str, Field(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")],
        after_version: Annotated[int, Field(strict=True, ge=0)],
        timeout_seconds: Annotated[float, Field(strict=True, ge=1, le=50, allow_inf_nan=False)] = 30,
    ) -> dict[str, Any]:
        """Wait read-only for a newer public task version, for at most 1–50 seconds.

        changed=true returns task_version and task (the public task with its file
        bridge). changed=false returns the current task_version on timeout.
        A version change is NOT confirmation of a user choice: inspect the exact
        decision/configuration before continuing. No research or business event
        is started by this tool. Correct invalid parameters and retry; for a
        future after_version, read the current task and use its task_version.
        """
        def public_snapshot() -> dict[str, Any] | None:
            # Reuse the existing short command lock, never hold it while waiting.
            # get_task's nested nonblocking lock then skips recovery, so this read
            # cannot turn an unrelated interrupted operation into a business event.
            with command_lock(service.event_store.database_path, blocking=False) as acquired:
                return service.get_task(task_id) if acquired else None

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        try:
            while True:
                projection = await asyncio.to_thread(service.event_store.projection, task_id)
                if projection is None:
                    raise DomainError("not_found", "The task does not exist; check task_id and retry.",
                                      category="missing", task_id=task_id,
                                      details={"next_action": "check_task_id"})
                version = projection["task_version"]
                if after_version > version:
                    raise DomainError("version_conflict", "after_version is ahead of the current task; read task_version and retry.",
                                      category="conflict", task_id=task_id, current_version=version,
                                      retryable=True, details={"next_action": "read_task_and_retry"})
                if version > after_version:
                    task = await asyncio.to_thread(public_snapshot)
                    if task is not None:
                        return {"task_id": task_id, "changed": True,
                                "task_version": task["task_version"], "task": task}
                remaining = deadline - loop.time()
                if remaining <= 0:
                    if version > after_version:
                        raise DomainError("effect_failed", "The task changed but its snapshot is busy; retry this read.",
                                          category="effect", task_id=task_id, current_version=version,
                                          retryable=True, details={"next_action": "retry"})
                    return {"task_id": task_id, "changed": False, "task_version": version}
                await asyncio.sleep(min(0.1, remaining))
        except DomainError as exc:
            return {"error": exc.to_dict()}

    @server.tool(name="paperspine_import_legacy_task", structured_output=True)
    def import_legacy_task(request: dict[str, Any]) -> dict[str, Any]:
        """Import an explicitly supplied legacy job without starting execution."""
        try:
            return _import_legacy_task(
                service, request, principal_id=principal_id,
                session_id="mcp", surface="agent",
            )
        except DomainError as exc:
            return {"error": exc.to_dict()}

    @server.tool(name="paperspine_recover_operation", structured_output=True)
    def recover_operation(task_id: str, operation_id: str, expected_version: int) -> dict[str, Any]:
        """Retry the exact saved operation only when its outcome is known safe.

        Unknown results require the user's confirmation in Product Web.
        Read the task's recovery message and next_action first.
        """
        try:
            return service.recover(task_id, operation_id, expected_version=expected_version)
        except DomainError as exc:
            return {"error": exc.to_dict()}

    def request_decision(request: dict[str, Any]) -> dict[str, Any]:
        """Request a user decision. Agents cannot resolve decisions."""
        try:
            return agent_request_decision(service, request, principal_id=principal_id)
        except DomainError as exc:
            return {"error": exc.to_dict()}

    register_command(request_decision, "paperspine_request_decision", "RequestDecision")

    @server.tool(name="paperspine_list_task_events", structured_output=True)
    def list_task_events(task_id: str, after_sequence: int = 0) -> dict[str, Any]:
        """Read ordered task events after a sequence number."""
        try:
            return {"task_id": task_id, "events": service.list_task_events(
                task_id, after_sequence=after_sequence
            )}
        except DomainError as exc:
            return {"error": exc.to_dict()}

    def public_tool(name: str, command_type: str, *, reviewer: bool = False) -> None:
        def invoke(request: dict[str, Any]) -> dict[str, Any]:
            try:
                return agent_execute(service, request, principal_id=principal_id,
                                     command_type=command_type, reviewer=reviewer)
            except DomainError as exc:
                return {"error": exc.to_dict()}
        register_command(invoke, name, command_type)

    for tool_name, command_type in (
        ("paperspine_save_configuration", "SaveConfiguration"),
        ("paperspine_authorize_materials", "AuthorizeMaterials"),
        ("paperspine_commit_milestone", "CommitMilestone"),
        ("paperspine_bind_evidence", "BindEvidence"),
        ("paperspine_publish_artifact", "PublishArtifact"),
        ("paperspine_resolve_finding", "ResolveFinding"),
        ("paperspine_prepare_delivery", "PrepareDelivery"),
    ):
        public_tool(tool_name, command_type, reviewer=False)

    # The old workbench's academic Runner operations are also available to an
    # Agent over MCP during the migration window.  They deliberately remain a
    # small, allow-listed set instead of accepting arbitrary ``runner.*``
    # command envelopes.  This keeps the Agent and business facades aligned
    # while ProductRunner continues to own the J-stage semantics.
    def runner_tool(name: str, operation: str) -> None:
        @server.tool(name=name, structured_output=True)
        def invoke(request: dict[str, Any]) -> dict[str, Any]:
            try:
                _reject_untrusted_identity(request)
                task_id = request.get("task_id")
                command_id = request.get("command_id")
                expected_revision = request.get("expected_revision")
                if (not isinstance(task_id, str) or not task_id
                        or not isinstance(command_id, str) or not command_id
                        or isinstance(expected_revision, bool)
                        or not isinstance(expected_revision, int)
                        or expected_revision < 0):
                    raise DomainError(
                        "validation_failed", "runner 命令需要 task_id、command_id 和非负 expected_revision。",
                        category="validation", task_id=task_id, command_id=command_id,
                    )
                runner = service.legacy_adapter._runner
                if runner is None:
                    raise DomainError(
                        "effect_failed", "论文流程执行器当前不可用。", category="effect",
                        task_id=task_id, command_id=command_id, retryable=True,
                    )
                if operation in {"resume", "figure-candidates", "final-mappings",
                                 "answer", "academic-answer", "contribution-confirmation"}:
                    _require_user_configuration(service, task_id)
                common = {
                    "command_id": command_id,
                    "expected_revision": expected_revision,
                    "writer_id": "p2-mcp-facade",
                    "actor": {"actor_id": principal_id, "surface": "mcp"},
                }
                if operation == "bootstrap":
                    result = runner.bootstrap(task_id, **common)
                elif operation == "materials":
                    roots = request.get("materials_roots")
                    if (not isinstance(roots, list) or not roots
                            or not all(isinstance(item, str) and item.strip() for item in roots)):
                        raise DomainError("validation_failed", "materials_roots 必须是非空路径数组。", category="validation", task_id=task_id)
                    result = runner.add_materials(task_id, roots, **common)
                elif operation == "resume":
                    result = runner.resume(task_id, **common)
                elif operation == "figure-candidates":
                    registration = request.get("registration")
                    if not isinstance(registration, dict):
                        raise DomainError("validation_failed", "registration 必须是对象。", category="validation", task_id=task_id)
                    result = runner.register_figure_candidate(task_id, registration, **common)
                elif operation == "final-mappings":
                    registration = request.get("registration")
                    if not isinstance(registration, dict):
                        raise DomainError("validation_failed", "registration 必须是对象。", category="validation", task_id=task_id)
                    result = runner.register_final_mapping(task_id, registration, **common)
                elif operation in {"answer", "academic-answer"}:
                    issue_id, token, answer = request.get("issue_id"), request.get("resume_token"), request.get("answer")
                    if not all(isinstance(value, str) and value for value in (issue_id, token)) or not isinstance(answer, dict):
                        raise DomainError("validation_failed", "issue_id、resume_token 和 answer 必须有效。", category="validation", task_id=task_id)
                    if operation == "academic-answer" and answer.get("contract") != "paperspine5.academic-stage-answer":
                        raise DomainError("validation_failed", "academic-answer 必须使用论文阶段回答契约。", category="validation", task_id=task_id)
                    result = runner.answer_issue(task_id, issue_id, token, answer, **common)
                elif operation == "contribution-confirmation":
                    issue_id, token, confirmation = request.get("issue_id"), request.get("resume_token"), request.get("confirmation")
                    if not all(isinstance(value, str) and value for value in (issue_id, token)) or not isinstance(confirmation, dict):
                        raise DomainError("validation_failed", "issue_id、resume_token 和 confirmation 必须有效。", category="validation", task_id=task_id)
                    identity = {
                        "principal_id": principal_id, "session_id": "mcp",
                        "run_id": f"p2-mcp-run-{principal_id}",
                        "independence_group": f"authenticated-local-user-{principal_id}",
                        "attestation_input_id": f"identity:p2-mcp:{principal_id}",
                    }
                    identity["provenance_sha256"] = identity_provenance_sha256(identity)
                    result = runner.confirm_contribution(task_id, issue_id, token, confirmation, author_identity=identity, **common)
                else:
                    raise DomainError("not_found", "不支持的 runner 操作。", category="missing", task_id=task_id)
                return {"status": "COMMITTED", "result": result}
            except DomainError as exc:
                return {"error": exc.to_dict()}
            except ContractError as exc:
                return {"error": DomainError("validation_failed", str(exc), category="validation", task_id=request.get("task_id")).to_dict()}

    for _name, _operation in (
        ("paperspine_runner_bootstrap", "bootstrap"),
        ("paperspine_runner_materials", "materials"),
        ("paperspine_runner_resume", "resume"),
        ("paperspine_runner_figure_candidates", "figure-candidates"),
        ("paperspine_runner_final_mappings", "final-mappings"),
        ("paperspine_runner_answer_issue", "answer"),
        ("paperspine_runner_academic_answer", "academic-answer"),
        ("paperspine_runner_confirm_contribution", "contribution-confirmation"),
    ):
        runner_tool(_name, _operation)

    @server.tool(name="paperspine_get_runner_snapshot", structured_output=True)
    def get_runner_snapshot(task_id: str) -> dict[str, Any]:
        try:
            runner = service.legacy_adapter._runner
            if runner is None:
                raise DomainError("effect_failed", "论文流程执行器当前不可用。", category="effect", task_id=task_id)
            return {"task_id": task_id, "snapshot": runner.snapshot(task_id)}
        except DomainError as exc:
            return {"error": exc.to_dict()}
        except ContractError as exc:
            return {"error": DomainError("validation_failed", str(exc), category="validation", task_id=task_id).to_dict()}

    # Independent review is a separate trust boundary.  A normal MCP host
    # must not obtain that role merely because the old helper passed
    # ``reviewer=True``.  Enable it only for a process explicitly started
    # with a trusted reviewer identity.
    if reviewer_id:
        def submit_review(request: dict[str, Any]) -> dict[str, Any]:
            try:
                return reviewer_execute(service, request, reviewer_id=reviewer_id)
            except DomainError as exc:
                return {"error": exc.to_dict()}

        register_command(submit_review, "paperspine_submit_review", "SubmitReview")

    return server


_WEB_PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>PaperSpine 论文工作台</title>
<style>body{margin:0;background:#f3f0e9;color:#25231f;font:16px system-ui}main{max-width:920px;margin:auto;padding:40px 24px}header{display:flex;justify-content:space-between;align-items:center}.card{background:#fff;border:1px solid #d8d1c4;border-radius:16px;padding:24px;margin:18px 0}#stages{display:grid;grid-template-columns:repeat(8,1fr);gap:6px;padding:0;list-style:none}#stages li{padding:9px 4px;text-align:center;border-radius:8px;background:#ebe7df;font-size:13px}#stages li.active{background:#1f5b4b;color:white}.decision,.finding,.artifact{padding:12px;border-top:1px solid #eee}button,select{padding:8px;margin:4px}a{color:#1f5b4b}.muted{color:#6c675f}#task{display:none}</style></head><body><main>
<header><h1>PaperSpine 论文工作台</h1><a href="/help">使用帮助</a><div id="status">正在读取论文任务…</div></header>
<section class="card" id="welcome" hidden><h2>开始论文工作</h2>
<form id="create-form"><label>论文主题 <input id="paper-title" required maxlength="200"></label><label>任务简介 <input id="paper-description" maxlength="1000" placeholder="用于区分并行任务，可留空自动生成"></label><button>创建任务</button></form>
<form id="resume-form"><label>任务编号 <input id="resume-id" required pattern="[A-Za-z0-9][A-Za-z0-9._:-]*"></label><button>恢复任务</button></form>
<p>已有任务请打开保存的任务网址，或输入任务编号。创建任务不会自动开始研究。</p></section>
<section class="card" id="materials-card" hidden><h2>提供本地材料</h2><p id="task-reference"></p>
<form id="materials-form"><label>材料文件夹的完整路径 <input id="material-path" required></label>
<label><input id="material-consent" type="checkbox" required>我有权使用这些材料，允许本任务在本机只读使用</label><button>授权本地材料</button></form>
<p id="material-message">只选择本篇论文需要的材料。此操作不授权对外上传。完成后请回到原 Agent，要求它继续同一任务。</p></section>
<section class="card" id="recovery-card" hidden><h2>继续论文工作</h2><p id="recovery-message"></p><button id="continue-work">继续</button></section>
<section class="card"><h2>论文进度</h2><ol id="stages"></ol><p id="stage-copy" class="muted"></p></section>
<section class="card"><h2>需要你的选择</h2><div id="decisions"><p class="muted">暂无待确认选择。</p></div></section>
<section class="card"><h2>论文、图件与下载</h2><div id="artifacts"><p class="muted">尚无可读文件。</p></div></section>
<section class="card"><h2>独立审核</h2><div id="findings"><p class="muted">尚无审核问题。</p></div></section>
<pre id="task" aria-hidden="true"></pre><ol id="events" hidden></ol></main><script>
const id=new URLSearchParams(location.search).get('task_id');
const status=document.getElementById('status'), out=document.getElementById('task');
const list=document.getElementById('events');
const decisions=document.getElementById('decisions');
let renderedVersion=null,renderedRunnerRevision=null;
const stageNames={intake:'材料与设置',research:'研究',contribution:'动机与贡献',evidence:'证据',draft:'稿件',figure:'图件',review:'审核',delivery:'本地交付'};
function render(v){out.textContent=JSON.stringify(v,null,2);document.body.dataset.taskId=v.task_id;
 document.getElementById('materials-card').hidden=false;document.getElementById('task-reference').textContent='任务编号：'+v.task_id+'。请保存当前网址以便恢复。';
 renderedVersion=v.task_version;renderedRunnerRevision=(v.legacy_runner||{}).revision;
 showRecovery(v);
 const effectiveStage=v.effective_stage||v.stage;const runnerComplete=v.legacy_runner&&v.legacy_runner.task_status==='completed'&&v.legacy_runner.stage==='target_package_ready';
 const stages=document.getElementById('stages');stages.replaceChildren();for(const [key,label] of Object.entries(stageNames)){const li=document.createElement('li');li.textContent=label;if(key===effectiveStage)li.className='active';stages.appendChild(li)}
 document.getElementById('stage-copy').textContent=(runnerComplete||v.status==='delivery_ready')?'本地论文包已准备好；投稿仍需单独确认。':`当前：${stageNames[effectiveStage]||'处理中'}`;
 const artifacts=document.getElementById('artifacts');artifacts.replaceChildren();for(const a of (v.artifacts||[])){const row=document.createElement('div');row.className='artifact';const link=document.createElement('a');link.textContent=a.artifact_type==='delivery_package'?'下载完整论文包':a.artifact_type;link.href=a.download_url||`/api/v1/tasks/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(a.artifact_id)}/download`;row.appendChild(link);artifacts.appendChild(row)}if(!(v.artifacts||[]).length)artifacts.innerHTML='<p class="muted">尚无可读文件。</p>';
 const findings=document.getElementById('findings');findings.replaceChildren();for(const f of (v.findings||[])){const row=document.createElement('div');row.className='finding';row.textContent=`${f.status==='resolved'?'已修复':'待修复'}：${f.message}`;findings.appendChild(row)}if(!(v.findings||[]).length)findings.innerHTML='<p class="muted">尚无审核问题。</p>';showDecisions(v)}
function showEvent(e){const li=document.createElement('li');li.dataset.eventId=e.event_id;
 li.textContent=e.event_type;list.appendChild(li)}
async function refreshTask(){try{const r=await fetch(`/api/v1/tasks/${encodeURIComponent(id)}`);const v=await r.json();if(v.error)throw Error(v.error.message);if(renderedVersion!==v.task_version||renderedRunnerRevision!==(v.legacy_runner||{}).revision)render(v);else showRecovery(v);status.textContent=v.recovery?'需要继续论文工作':'已连接论文任务';return v}catch(e){status.textContent='连接中断，已保存的论文仍会保留。';document.getElementById('recovery-card').hidden=false;document.getElementById('recovery-message').textContent='请重新连接，读取同一任务的最新进度。';const b=document.getElementById('continue-work');b.textContent='重新连接';b.onclick=refreshTask}}
function showRecovery(v){const card=document.getElementById('recovery-card'),b=document.getElementById('continue-work');const recovery=v.recovery;card.hidden=!recovery;if(!recovery)return;
 document.getElementById('recovery-message').textContent=recovery.message;
 b.textContent=recovery.retryable?'安全重试':'我已核对，确认未执行后继续';b.disabled=false;b.onclick=async()=>{b.disabled=true;try{const r=await fetch(`/api/v1/tasks/${encodeURIComponent(id)}/recovery`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation_id:recovery.operation_id,expected_version:v.task_version,confirm_no_effect:!recovery.retryable})});const x=await r.json();if(x.error){status.textContent=x.error.message;await refreshTask();return}render(x.projection);status.textContent='已继续同一论文任务。'}catch(e){await refreshTask()}finally{b.disabled=false}}}
function showDecisions(v){decisions.replaceChildren();for(const d of (v.decisions||[])){
 const row=document.createElement('div');row.dataset.decisionId=d.decision_id;
 row.className='decision';row.dataset.decisionStatus=d.status;row.textContent=`${d.status==='resolved'?'已确认':'待确认'}：${d.prompt||d.decision_type}`;
 if(d.status==='pending'){const select=document.createElement('select');
  for(const option of (d.allowed_decision_details||d.allowed_decisions.map(x=>({option_id:x,label:x})))){const o=document.createElement('option');o.value=option.option_id;o.textContent=option.label;select.appendChild(o)}
  const button=document.createElement('button');button.textContent='Confirm decision';button.onclick=async()=>{
   const body={command_id:`resolve-${d.decision_id}`,expected_version:v.task_version,
    payload:{decision_id:d.decision_id,option_id:select.value,confirmed_at:new Date().toISOString(),reason:'Confirmed in Product Web'}};
   const r=await fetch(`/api/v1/tasks/${encodeURIComponent(id)}/decisions/${encodeURIComponent(d.decision_id)}/resolution`,
    {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const x=await r.json();
   if(x.error){status.textContent=x.error.message;return}render(x.projection)};
  row.append(' ',select,' ',button)}decisions.appendChild(row)}
 if(!(v.decisions||[]).length)decisions.innerHTML='<p class="muted">暂无待确认选择。</p>'}
const createForm=document.getElementById('create-form');let pendingOpen=null,pendingMaterials=null;
createForm.onsubmit=async e=>{e.preventDefault();const b=createForm.querySelector('button');b.disabled=true;
 try{if(!pendingOpen)pendingOpen={command_id:'web-open-'+crypto.randomUUID(),expected_version:0,payload:{mode:'open',title:document.getElementById('paper-title').value,description:document.getElementById('paper-description').value.trim()||undefined}};
 const r=await fetch('/api/v1/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pendingOpen)});const x=await r.json();if(x.error){status.textContent=x.error.message;return}location.href='/?task_id='+encodeURIComponent(x.task_id);
 }catch(e){status.textContent='连接中断。请保持页面，重新点击创建任务以核对同一次请求。'}finally{b.disabled=false}};
document.getElementById('resume-form').onsubmit=e=>{e.preventDefault();location.href='/?task_id='+encodeURIComponent(document.getElementById('resume-id').value.trim())};
const materialForm=document.getElementById('materials-form');materialForm.onsubmit=async e=>{e.preventDefault();const b=materialForm.querySelector('button');b.disabled=true;
 try{if(!pendingMaterials){const v=await refreshTask();if(!v)return;pendingMaterials={command_id:'web-materials-'+crypto.randomUUID(),expected_version:v.task_version,payload:{grants:[{grant_id:'materials-'+crypto.randomUUID(),uri:document.getElementById('material-path').value.trim(),scope:'read_only'}]}}}
 const r=await fetch(`/api/v1/tasks/${encodeURIComponent(id)}/materials`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pendingMaterials)});const x=await r.json();if(x.error){status.textContent=x.error.message;await refreshTask();return}pendingMaterials=null;render(x.projection);document.getElementById('material-message').textContent='材料已授权在本机只读使用。请回到原 Agent，继续同一任务的研究。';
 }catch(e){status.textContent='连接中断。请保持页面并核对任务进度，再重试同一次材料请求。'}finally{b.disabled=false}};
if(!id){document.getElementById('welcome').hidden=false;status.textContent='请创建或恢复任务'}else{
 refreshTask();
 setInterval(()=>{if(!document.hidden)refreshTask()},3000);
 const stream=new EventSource(`/api/v1/tasks/${encodeURIComponent(id)}/events`);
 stream.addEventListener('task-event',m=>showEvent(JSON.parse(m.data)));
 stream.addEventListener('snapshot-end',()=>stream.close());
}
</script></body></html>"""


def make_business_handler(service: ApplicationService, *, principal_id: str,
                          session_id: str,
                          reviewer_id: str | None = None,
                          reviewer_credential: str | None = None) -> type[BaseHTTPRequestHandler]:
    if reviewer_id is not None and not reviewer_id.strip():
        raise ValueError("reviewer_id must be non-empty when configured")
    if reviewer_credential is not None and not reviewer_credential:
        raise ValueError("reviewer_credential must be non-empty when configured")
    if (reviewer_id is None) != (reviewer_credential is None):
        raise ValueError("reviewer_id and reviewer_credential must be configured together")
    class Handler(BaseHTTPRequestHandler):
        server_version = "PaperSpineP2/2.0"

        def log_message(self, _format: str, *args: object) -> None:
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                # A browser refresh or a test/server shutdown can close the
                # loopback socket after headers are sent.  Treat it as a
                # completed transport cancellation rather than logging an
                # unhandled request exception.
                return

        def _json(self, status: int, value: Any) -> None:
            self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _error(self, exc: DomainError) -> None:
            code = exc.to_dict()["code"]
            self._json(404 if code == "not_found" else 409 if code.endswith("conflict") else 400,
                       {"error": exc.to_dict()})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 1024 * 1024:
                    self._json(413, {"error": {"code": "validation_failed", "message": "请求内容为空或超过 1 MiB 限额。"}})
                    return
                request = json.loads(self.rfile.read(size))
                if not isinstance(request, Mapping):
                    raise ValueError("request body must be an object")
                parts = [part for part in path.split("/") if part]
                if path in {"/api/v1/imports/legacy", "/api/tasks/import-legacy"}:
                    result = _import_legacy_task(
                        service, request, principal_id=principal_id,
                        session_id=session_id, surface="business",
                    )
                elif path in {"/api/tasks/open", "/api/v1/tasks"}:
                    result = business_open_task(
                        service, request, principal_id=principal_id, session_id=session_id)
                    if result.get("task_id"):
                        result = dict(result)
                        result["projection"] = service.get_task(result["task_id"])
                elif len(parts) == 5 and parts[:3] == ["api", "v1", "tasks"] and parts[4] == "recovery":
                    if set(request) - {"operation_id", "expected_version", "confirm_no_effect"}:
                        raise DomainError("validation_failed", "恢复请求包含不支持的内容。", category="validation", task_id=parts[3])
                    if not isinstance(request.get("operation_id"), str) or type(request.get("expected_version")) is not int or type(request.get("confirm_no_effect", False)) is not bool:
                        raise DomainError("validation_failed", "恢复请求无效。", category="validation", task_id=parts[3])
                    result = service.recover(parts[3], request["operation_id"], expected_version=request["expected_version"],
                                             confirm_no_effect=request.get("confirm_no_effect", False), surface="business")
                elif len(parts) == 5 and parts[:3] == ["api", "v1", "tasks"] and parts[4] == "feedback":
                    task_id = parts[3]
                    feedback = request.get("feedback")
                    scope = request.get("scope", "all")
                    if scope in {"user_uploaded_feedback", "manuscript_and_figures"}:
                        scope = "all"
                    if not isinstance(feedback, str) or not feedback.strip() or len(feedback) > 32000:
                        raise DomainError("validation_failed", "反馈内容不能为空且不能超过 32,000 个字符。",
                                          category="validation", task_id=task_id)
                    if scope not in {"all", "manuscript", "figures", "figure_mapping"}:
                        raise DomainError("validation_failed", "反馈范围无效。", category="validation", task_id=task_id)
                    task = service.get_task(task_id)
                    command_id = request.get("command_id") or f"web-feedback-{uuid4().hex}"
                    if not isinstance(command_id, str) or not _SAFE_HANDOFF_TASK_ID.fullmatch(command_id):
                        raise DomainError("validation_failed", "反馈操作编号无效。", category="validation", task_id=task_id)
                    kernel_task = service.legacy_adapter._kernel.get_task(task_id)
                    workspace = Path(kernel_task["workspace_root"]).resolve()
                    feedback_dir = workspace / "paper" / "feedback"
                    feedback_dir.mkdir(parents=True, exist_ok=True)
                    if not feedback_dir.resolve().is_relative_to(workspace):
                        raise DomainError("validation_failed", "反馈目录无效。", category="validation", task_id=task_id)
                    original_name = Path(str(request.get("filename") or "feedback.md")).name
                    name = re.sub(r"[^\w. -]", "_", original_name, flags=re.UNICODE)[-100:]
                    if not name.lower().endswith((".md", ".txt")):
                        name += ".md"
                    identity = hashlib.sha256(command_id.encode("utf-8")).hexdigest()[:20]
                    feedback_path = feedback_dir / f"{identity}-{name}"
                    content = f"# User feedback\n\nScope: {scope}\n\n{feedback.strip()}\n"
                    if feedback_path.exists():
                        if feedback_path.is_symlink() or feedback_path.read_text(encoding="utf-8") != content:
                            raise DomainError("idempotency_conflict", "此操作编号已用于另一份反馈。", category="conflict", task_id=task_id)
                    else:
                        with feedback_path.open("x", encoding="utf-8") as stream:
                            stream.write(content)
                    result = business_execute(
                        service,
                        {"schema_version": "1.1", "command_id": command_id, "task_id": task_id,
                         "expected_version": request.get("expected_version", task.get("task_version")),
                         "payload": {"feedback": feedback.strip(), "scope": scope,
                                     "feedback_file": feedback_path.relative_to(workspace).as_posix()}},
                        principal_id=principal_id, session_id=session_id,
                        command_type="RequestRevision",
                    )
                    result = dict(result)
                    result["feedback_file"] = str(feedback_path)
                elif len(parts) == 5 and parts[:3] == ["api", "v1", "tasks"] and parts[4] == "open-package":
                    task_id = parts[3]
                    task = service.get_task(task_id)
                    kernel_task = service.legacy_adapter._kernel.get_task(task_id)
                    workspace = Path(kernel_task["workspace_root"]).resolve()
                    package_dir = Path((task.get("skill_bridge") or {}).get("package_directory") or "").resolve()
                    if not package_dir.is_dir():
                        package_dir = (workspace / "paper").resolve()
                    if workspace not in package_dir.parents and package_dir != workspace:
                        raise DomainError("forbidden", "论文工作包路径不在当前任务工作区内。", category="authorization", task_id=task_id)
                    opened = False
                    if os.name == "nt" and package_dir.is_dir():
                        os.startfile(str(package_dir))
                        opened = True
                    result = {"status": "PASS", "task_id": task_id,
                              "package_directory": str(package_dir), "opened": opened}
                elif len(parts) == 5 and parts[:3] == ["api", "v1", "tasks"] and parts[4] == "decisions":
                    request = dict(request); request["task_id"] = parts[3]
                    result = business_request_decision(
                        service, request, principal_id=principal_id, session_id=session_id)
                elif (len(parts) == 7 and parts[:3] == ["api", "v1", "tasks"]
                      and parts[4] == "decisions" and parts[6] == "resolution"):
                    request = dict(request); request["task_id"] = parts[3]
                    payload = request.get("payload")
                    if not isinstance(payload, Mapping) or payload.get("decision_id") != parts[5]:
                        raise DomainError("validation_failed", "Path and payload decision_id must match.",
                                          category="validation", task_id=parts[3],
                                          command_id=request.get("command_id"))
                    result = business_resolve_decision(
                        service, request, principal_id=principal_id, session_id=session_id)
                # Compatibility runner facade.  The old rich workbench
                # exposed the academic J-stage operations directly while the
                # P2 domain facade initially exposed only the small command
                # set.  Keep these operations behind the same authenticated
                # business HTTP boundary so existing hosts can migrate one
                # route at a time.  ProductRunner remains the legacy academic
                # executor; reads from ``GET .../runner`` and ``get_task``
                # provide the corresponding compatibility projection.
                elif (len(parts) >= 6 and parts[:3] == ["api", "v1", "tasks"]
                      and parts[4] == "runner" and parts[5] != "revision-request"):
                    task_id = parts[3]
                    action_parts = parts[5:]
                    if "writer_id" in request:
                        raise DomainError(
                            "validation_failed", "writer_id 由运行时管理，不能由业务请求指定。",
                            category="validation", task_id=task_id,
                        )
                    command_id = request.get("command_id")
                    expected_revision = request.get("expected_revision")
                    if (not isinstance(command_id, str) or not command_id
                            or isinstance(expected_revision, bool)
                            or not isinstance(expected_revision, int)
                            or expected_revision < 0):
                        raise DomainError(
                            "validation_failed", "runner 命令需要 command_id 和非负 expected_revision。",
                            category="validation", task_id=task_id, command_id=command_id,
                        )
                    runner = service.legacy_adapter._runner
                    if runner is None:
                        raise DomainError(
                            "effect_failed", "论文流程执行器当前不可用。", category="effect",
                            task_id=task_id, command_id=command_id, retryable=True,
                        )
                    common = {
                        "command_id": command_id,
                        "expected_revision": expected_revision,
                        # Never trust a writer identity supplied over HTTP.
                        "writer_id": "p2-business-facade",
                        # ProductRunner's actor contract names the browser
                        # surface ``web`` (the domain facade still records
                        # the authenticated principal separately).  Include
                        # the authenticated session authority marker here as
                        # well: delegated_local_test J3 configuration binds
                        # its grant to this exact actor tuple, so omitting it
                        # would make the otherwise valid Web grant impossible
                        # to submit through the migrated facade.
                        "actor": {
                            "actor_id": principal_id,
                            "surface": "web",
                            "authority_kind": "authenticated_local_user_session",
                            # Bind the browser mutation to the same immutable
                            # identity attestation used by the academic figure
                            # authority.  Older calls omitted these fields,
                            # which made a freshly supplied J7 reference plan
                            # impossible to validate even though the session
                            # was authenticated.
                            "session_id": session_id or "p2-business",
                            "run_id": f"p2-business-run-{principal_id}",
                            "attestation_input_id": f"identity:p2-business:{principal_id}:{session_id or 'default'}",
                        },
                    }
                    common["actor"]["provenance_sha256"] = identity_provenance_sha256({
                        "principal_id": principal_id,
                        "session_id": common["actor"]["session_id"],
                        "run_id": common["actor"]["run_id"],
                        "independence_group": f"authenticated-local-user-{principal_id}",
                        "attestation_input_id": common["actor"]["attestation_input_id"],
                    })
                    if action_parts == ["bootstrap"]:
                        result = runner.bootstrap(task_id, **common)
                    elif action_parts == ["materials"]:
                        roots = request.get("materials_roots")
                        if (not isinstance(roots, list) or not roots
                                or not all(isinstance(item, str) and item.strip() for item in roots)):
                            raise DomainError(
                                "validation_failed", "materials_roots 必须是非空路径数组。",
                                category="validation", task_id=task_id, command_id=command_id,
                            )
                        result = runner.add_materials(task_id, roots, **common)
                    elif action_parts == ["resume"]:
                        result = runner.resume(task_id, **common)
                    elif action_parts == ["figure-candidates"]:
                        registration = request.get("registration")
                        if not isinstance(registration, dict):
                            raise DomainError(
                                "validation_failed", "registration 必须是对象。",
                                category="validation", task_id=task_id, command_id=command_id,
                            )
                        result = runner.register_figure_candidate(task_id, registration, **common)
                    elif action_parts == ["final-mappings"]:
                        registration = request.get("registration")
                        if not isinstance(registration, dict):
                            raise DomainError(
                                "validation_failed", "registration 必须是对象。",
                                category="validation", task_id=task_id, command_id=command_id,
                            )
                        result = runner.register_final_mapping(task_id, registration, **common)
                    elif len(action_parts) == 3 and action_parts[0] == "issues" and action_parts[2] in {
                        "answer", "academic-answer", "contribution-confirmation"
                    }:
                        issue_id = unquote(action_parts[1])
                        token = request.get("resume_token")
                        if not isinstance(token, str) or not token:
                            raise DomainError(
                                "validation_failed", "resume_token 不能为空。",
                                category="validation", task_id=task_id, command_id=command_id,
                            )
                        if action_parts[2] == "contribution-confirmation":
                            confirmation = request.get("confirmation")
                            if not isinstance(confirmation, dict):
                                raise DomainError(
                                    "validation_failed", "confirmation 必须是对象。",
                                    category="validation", task_id=task_id, command_id=command_id,
                                )
                            author_identity = {
                                "principal_id": principal_id,
                                "session_id": session_id or "p2-business",
                                "run_id": f"p2-business-run-{principal_id}",
                                "independence_group": f"authenticated-local-user-{principal_id}",
                                "attestation_input_id": f"identity:p2-business:{principal_id}:{session_id or 'default'}",
                            }
                            author_identity["provenance_sha256"] = identity_provenance_sha256(
                                author_identity
                            )
                            result = runner.confirm_contribution(
                                task_id, issue_id, token, confirmation,
                                author_identity=author_identity, **common,
                            )
                        else:
                            answer = request.get("answer")
                            if not isinstance(answer, dict):
                                raise DomainError(
                                    "validation_failed", "answer 必须是对象。",
                                    category="validation", task_id=task_id, command_id=command_id,
                                )
                            if (action_parts[2] == "academic-answer"
                                    and answer.get("contract") != "paperspine5.academic-stage-answer"):
                                raise DomainError(
                                    "validation_failed", "academic-answer 必须使用论文阶段回答契约。",
                                    category="validation", task_id=task_id, command_id=command_id,
                                )
                            result = runner.answer_issue(
                                task_id, issue_id, token, answer, **common,
                            )
                    else:
                        raise DomainError(
                            "not_found", "不支持的 runner 操作。", category="missing",
                            task_id=task_id, command_id=command_id,
                        )
                    # ProductRunner acquires a CAS writer lease for each
                    # mutation.  The HTTP compatibility facade owns the
                    # writer identity, so it must release it before returning
                    # (otherwise the immediately-following domain mirror
                    # command is rejected as a stale/held lease).
                    service.legacy_adapter._kernel.release_writer_lease(
                        task_id, "p2-business-facade"
                    )
                    self._json(200, {"status": "COMMITTED", "result": result})
                    return
                elif len(parts) >= 5 and parts[:3] == ["api", "v1", "tasks"]:
                    request = dict(request); request["task_id"] = parts[3]
                    command_type = None
                    if parts[4:] == ["materials"]: command_type = "AuthorizeMaterials"
                    elif parts[4:] == ["configuration"]: command_type = "SaveConfiguration"
                    elif parts[4:] == ["milestones"]: command_type = "CommitMilestone"
                    elif parts[4:] == ["evidence-links"]: command_type = "BindEvidence"
                    elif parts[4:] == ["artifacts"]: command_type = "PublishArtifact"
                    elif parts[4:] == ["reviews"]: command_type = "SubmitReview"
                    elif parts[4:] == ["runner", "revision-request"]:
                        command_type = "RequestRevision"
                    elif len(parts) == 7 and parts[4] == "findings" and parts[6] == "resolution":
                        command_type = "ResolveFinding"
                        if not isinstance(request.get("payload"), Mapping) or request["payload"].get("finding_id") != parts[5]:
                            raise DomainError("validation_failed", "Path and payload finding_id must match.",
                                              category="validation", task_id=parts[3])
                    elif parts[4:] == ["delivery"]: command_type = "PrepareDelivery"
                    if command_type is None:
                        self._json(404, {"error": {"code": "not_found"}}); return
                    if command_type == "SubmitReview":
                        if reviewer_id is None or reviewer_credential is None:
                            raise DomainError(
                                "forbidden", "当前业务入口未启用独立审核角色。",
                                category="authorization", task_id=parts[3],
                                command_id=request.get("command_id"),
                            )
                        supplied = self.headers.get("X-PaperSpine-Reviewer-Credential", "")
                        if not hmac.compare_digest(supplied, reviewer_credential):
                            raise DomainError(
                                "forbidden", "独立审核凭据无效。", category="authorization",
                                task_id=parts[3], command_id=request.get("command_id"),
                            )
                        result = reviewer_execute(service, request, reviewer_id=reviewer_id)
                    else:
                        result = business_execute(service, request, principal_id=principal_id,
                                                  session_id=session_id, command_type=command_type)
                else:
                    self._json(404, {"error": {"code": "not_found"}}); return
                self._json(200, result)
            except DomainError as exc:
                if len(parts) >= 6 and parts[:3] == ["api", "v1", "tasks"] and parts[4] == "runner":
                    try:
                        service.legacy_adapter._kernel.release_writer_lease(parts[3], "p2-business-facade")
                    except Exception:
                        pass
                self._error(exc)
            except ContractError as exc:
                if len(parts) >= 6 and parts[:3] == ["api", "v1", "tasks"] and parts[4] == "runner":
                    try:
                        service.legacy_adapter._kernel.release_writer_lease(parts[3], "p2-business-facade")
                    except Exception:
                        pass
                self._error(DomainError(
                    "validation_failed", str(exc), category="validation",
                ))
            except (ValueError, json.JSONDecodeError):
                self._error(DomainError("validation_failed", "请求格式无效，请检查后重新提交。", category="validation"))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                # One canonical workbench for the host Skill's task.
                page = Path(__file__).resolve().parents[2] / "ui" / "product.html"
                if not page.is_file():
                    self._json(503, {"error": {"code": "missing_workbench", "message": "论文工作台文件缺失。"}}); return
                self._send(200, page.read_bytes(), "text/html; charset=utf-8"); return
            if parsed.path == "/product-v1.html":
                self.send_response(303)
                self.send_header("Location", "/" + ("?" + parsed.query if parsed.query else ""))
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            if parsed.path in {"/product.js", "/product.css", "/product-v1.js", "/product-v1.css"}:
                asset_name = parsed.path[1:]
                asset = Path(__file__).resolve().parents[2] / "ui" / asset_name
                if not asset.is_file():
                    self._json(404, {"error": {"code": "not_found"}}); return
                media = "text/javascript" if asset.suffix == ".js" else "text/css"
                self._send(200, asset.read_bytes(), media + "; charset=utf-8"); return
            if parsed.path == "/assets/brand/paperspine-mark.svg":
                asset = Path(__file__).resolve().parents[3] / "07_发布页" / "assets" / "brand" / "paperspine-mark.svg"
                if not asset.is_file():
                    self._json(404, {"error": {"code": "not_found"}}); return
                self._send(200, asset.read_bytes(), "image/svg+xml; charset=utf-8"); return
            if parsed.path == "/help":
                help_path = Path(__file__).resolve().parents[2] / "ui" / "user-help.html"
                self._send(200, help_path.read_bytes(), "text/html; charset=utf-8"); return
            if parsed.path == "/api/v1/session":
                # The business facade is bound to a local principal/session at
                # startup (unlike the older tokenised UI server).  Expose the
                # small session envelope expected by the rich workbench; the
                # values are only CSRF/request labels, never material access
                # credentials, and writes remain scoped by the configured
                # ApplicationService principal.
                self._json(200, {
                    "status": "PASS",
                    "csrf_token": f"business-csrf-{session_id or 'default'}",
                    "user_identity": {"principal_id": principal_id, "session_id": session_id},
                    # The rich workbench binds host handoffs and artifact
                    # downloads to the active immutable build.  Returning it
                    # in the session envelope avoids the historical
                    # ``expected_build_id=undefined`` request and lets the
                    # compatibility route reject stale pages deterministically.
                    "product": {
                        "name": "PaperSpine5", "surface": "business-http",
                        "build_id": service.legacy_adapter._kernel.product_manifest.get("build_id"),
                    },
                    "security": {"loopback": True, "host": "127.0.0.1", "cache": "no-store"},
                }); return
            if parsed.path == "/api/v1/capabilities":
                self._json(200, service.capabilities()); return
            if parsed.path == "/api/v1/tasks":
                self._json(200, {"tasks": service.list_tasks()}); return
            parts = [unquote(part) for part in parsed.path.split("/") if part]
            legacy = len(parts) >= 3 and parts[:2] == ["api", "tasks"]
            v1 = len(parts) >= 4 and parts[:3] == ["api", "v1", "tasks"]
            if not (legacy or v1):
                self._json(404, {"error": {"code": "not_found"}}); return
            task_id = parts[2] if legacy else parts[3]
            tail = parts[3:] if legacy else parts[4:]
            try:
                if not tail:
                    self._json(200, service.get_task(task_id)); return
                if tail == ["figure-files"]:
                    kernel_task = service.legacy_adapter._kernel.get_task(task_id)
                    candidates = _figure_candidates(kernel_task, Path(kernel_task["workspace_root"]).resolve())
                    catalog = figure_reference_catalog(Path(kernel_task["workspace_root"]), candidates)
                    for item in [*candidates, *catalog["reference_documents"]]:
                        item["content_url"] = f"/api/v1/tasks/{quote(task_id, safe='')}/figure-files/{quote(item['relative_path'], safe='')}"
                    self._json(200, {"task_id": task_id, "files": candidates, **catalog}); return
                if len(tail) >= 2 and tail[0] == "figure-files":
                    relative = "/".join(tail[1:])
                    kernel_task = service.legacy_adapter._kernel.get_task(task_id)
                    workspace = Path(kernel_task["workspace_root"]).resolve()
                    candidates = _figure_candidates(kernel_task, workspace)
                    documents = figure_reference_catalog(workspace, candidates)["reference_documents"] if relative.startswith("paper/references/") else []
                    match = next((item for item in [*candidates, *documents] if item.get("relative_path") == relative), None)
                    if match is None:
                        raise DomainError("not_found", "图件候选文件不存在。", category="missing", task_id=task_id)
                    path = Path(match["path"]).resolve()
                    if not path.is_relative_to(workspace) or (relative.startswith("paper/references/")
                            and not path.is_relative_to((workspace / "paper/references").resolve())):
                        raise DomainError("not_found", "原文路径已变化，请刷新核对。", category="missing", task_id=task_id)
                    if match.get("media_type") == "application/pdf" and "preview" in parse_qs(parsed.query):
                        from .pdf_preview import pdf_response
                        try:
                            body, media = pdf_response(path.read_bytes(), path.name, self.path, task_id)
                        except ValueError as exc:
                            raise DomainError("validation_failed", str(exc), category="validation") from exc
                        self._send(200, body, media); return
                    self._send(200, path.read_bytes(), match.get("media_type", "application/octet-stream")); return
                if tail == ["skill-files"]:
                    task = service.get_task(task_id)
                    bridge = task.get("skill_bridge") or {}
                    self._json(200, {"task_id": task_id, "directory": bridge.get("directory"),
                                     "stage": bridge.get("stage"), "files": bridge.get("files") or []}); return
                if len(tail) == 2 and tail[0] == "skill-files":
                    task = service.get_task(task_id)
                    bridge_dir = Path((task.get("skill_bridge") or {}).get("directory") or "").resolve()
                    allowed = {item["name"] for item in list_bridge_files(bridge_dir.parent.parent)}
                    filename = tail[1]
                    if filename not in allowed or Path(filename).name != filename:
                        raise DomainError("not_found", "工作流文件不存在。", category="missing", task_id=task_id)
                    path = bridge_dir / filename
                    if not path.is_file() or bridge_dir not in path.resolve().parents:
                        raise DomainError("not_found", "工作流文件不存在。", category="missing", task_id=task_id)
                    media = "text/markdown; charset=utf-8" if path.suffix == ".md" else "application/json; charset=utf-8"
                    self._send(200, path.read_bytes(), media); return
                if tail == ["configuration"]:
                    task = service.get_task(task_id)
                    self._json(200, {"schema_version": "1.1", "task_id": task_id,
                        "task_version": task["task_version"], "configuration": task.get("configuration"),
                        "run_contract": task.get("run_contract"),
                        "configuration_stale": task.get("configuration_stale", False),
                        "configuration_source": task.get("configuration_source", "legacy_unknown"),
                        "configuration_user_confirmed": bool(task.get("configuration_user_confirmed", False)),
                        "configuration_readiness": configuration_readiness(task)}); return
                if tail == ["materials"]:
                    task = service.get_task(task_id)
                    self._json(200, {"schema_version": "1.1", "task_id": task_id,
                        "task_version": task["task_version"], "material_grants": task.get("material_grants", []),
                        "material_inventory": task.get("material_inventory")}); return
                if tail == ["decisions"]:
                    self._json(200, {"task_id": task_id, "decisions": service.list_decisions(task_id)}); return
                if tail == ["artifacts"]:
                    self._json(200, {"task_id": task_id,
                                     "artifacts": service.get_task(task_id).get("artifacts", [])}); return
                if tail == ["readiness"]:
                    # Compatibility envelope for the rich workbench.  Keep the
                    # manifest as the single source of truth and expose only
                    # derived readiness facts; this endpoint never promotes a
                    # task or creates a delivery receipt.
                    from .delivery_manifest import build_delivery_manifest
                    task = service.get_task(task_id)
                    manifest = task.get("delivery_manifest") or build_delivery_manifest(task)
                    configuration = task.get("configuration") or {}
                    runner_snapshot = None
                    try:
                        runner_snapshot = service.legacy_adapter._runner.snapshot(task_id)
                    except Exception:
                        runner_snapshot = None
                    self._json(200, {
                        "task_id": task_id,
                        "readiness": {
                            "status": "fresh" if manifest["ready"] else "blocked",
                            # The rich workbench binds package/handoff reads to
                            # the academic Runner revision, which is separate
                            # from the domain task_version.
                            "revision": (runner_snapshot or {}).get("revision", task.get("task_version", 0)),
                            "requested_scope": configuration.get("requested_scope", "local_delivery"),
                            "is_complete_for_requested_scope": manifest["ready"],
                            "manuscript_ready": bool(manifest["checks"].get("fresh_package")) and not bool(manifest["open_blocking_finding_ids"]),
                            "delivery_ready": manifest["ready"],
                            "submission_ready": False,
                            "payload": {"blockers_by_layer": {"local_delivery": manifest["blockers"]}},
                            "manifest": manifest,
                        },
                    }); return
                if tail == ["agent"]:
                    # Agent execution remains owned by the host conversation;
                    # the web surface reports an explicit idle state instead of
                    # treating a missing endpoint as a broken page.
                    self._json(200, {"task_id": task_id,
                                     "agent": {"task_id": task_id, "status": "idle",
                                                "execution_enabled": False,
                                                "message": "请回到当前宿主 Agent 继续此任务。"}}); return
                if tail == ["host-handoff"]:
                    query = parse_qs(parsed.query, keep_blank_values=True)
                    allowed = {"expected_revision", "expected_build_id"}
                    if not set(query).issubset(allowed) or any(len(v) != 1 for v in query.values()):
                        raise DomainError("validation_failed", "续作参数无效。", category="validation", task_id=task_id)
                    revision_text = query.get("expected_revision", [None])[0]
                    if revision_text is not None and not re.fullmatch(r"0|[1-9][0-9]*", revision_text):
                        raise DomainError("validation_failed", "续作版本无效。", category="validation", task_id=task_id)
                    handoff = _business_host_handoff(
                        service, task_id,
                        expected_revision=int(revision_text) if revision_text is not None else None,
                        expected_build_id=query.get("expected_build_id", [None])[0],
                    )
                    self._json(200, {"status": "PASS", "handoff": handoff}); return
                if tail == ["local-package"]:
                    # Keep the old workbench's download contract available on
                    # the migrated P2 server.  Package authority is still the
                    # Kernel/Runner ledger; this adapter only reconciles their
                    # two revision streams for the read-only package helper.
                    query = parse_qs(parsed.query, keep_blank_values=True)
                    allowed = {"expected_revision", "expected_build_id", "package_revision"}
                    if not set(query).issubset(allowed) or not {"expected_revision", "expected_build_id"}.issubset(query) or any(
                        len(values) != 1 for values in query.values()
                    ):
                        raise DomainError(
                            "validation_failed", "请刷新当前任务后重新下载论文包。",
                            category="validation", task_id=task_id,
                        )
                    revision_text = query["expected_revision"][0]
                    if not re.fullmatch(r"0|[1-9][0-9]*", revision_text):
                        raise DomainError(
                            "validation_failed", "请刷新当前任务后重新下载论文包。",
                            category="validation", task_id=task_id,
                        )
                    package_revision = None
                    if "package_revision" in query:
                        package_text = query["package_revision"][0]
                        if not re.fullmatch(r"0|[1-9][0-9]*", package_text):
                            raise DomainError(
                                "validation_failed", "请刷新当前任务后重新下载论文包。",
                                category="validation", task_id=task_id,
                            )
                        package_revision = int(package_text)
                    runner = service.legacy_adapter._runner
                    kernel = service.legacy_adapter._kernel
                    if runner is None:
                        raise DomainError(
                            "effect_failed", "论文流程执行器当前不可用。", category="effect",
                            task_id=task_id, retryable=True,
                        )
                    try:
                        # ui_server's helper is the hardened package reader
                        # (ZIP member/path/link/hash checks).  The proxy only
                        # presents the Runner revision as ``task.revision``;
                        # no state is copied or mutated by this read.
                        from .ui_server import _current_local_package

                        class _P2KernelView:
                            user_data_root = kernel.user_data_root

                            def get_task(self, current_task_id: str) -> dict[str, Any]:
                                value = dict(kernel.get_task(current_task_id))
                                value["revision"] = runner.snapshot(current_task_id).get("revision")
                                return value

                            def list_artifacts(self, current_task_id: str, **kwargs: Any) -> list[dict[str, Any]]:
                                return kernel.list_artifacts(current_task_id, **kwargs)

                            def get_readiness(self, current_task_id: str, **kwargs: Any) -> dict[str, Any]:
                                return kernel.get_readiness(current_task_id, **kwargs)

                        body, sha256 = _current_local_package(
                            _P2KernelView(), runner, task_id,
                            expected_revision=int(revision_text),
                            expected_build_id=query["expected_build_id"][0],
                            product_info={"build_id": kernel.product_manifest.get("build_id")},
                            package_revision=package_revision,
                        )
                    except Exception as exc:
                        raise DomainError(
                            "version_conflict", "当前修订的本地论文包尚不可下载，或文件已变化。请刷新任务后重试。",
                            category="conflict", task_id=task_id, retryable=True,
                        ) from exc
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Length", str(len(body)))
                    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", task_id)
                    selected = int(revision_text) if package_revision is None else package_revision
                    self.send_header("Content-Disposition", f'attachment; filename="paperspine5-{safe_name}-r{selected}.zip"')
                    self.send_header("ETag", f'"sha256:{sha256}"')
                    self.send_header("X-PaperSpine-Task", task_id)
                    self.send_header("X-PaperSpine-Revision", revision_text)
                    self.send_header("X-PaperSpine-Package-Revision", str(selected))
                    self.send_header("Cache-Control", "no-store, max-age=0")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Content-Security-Policy", "default-src 'none'; sandbox")
                    self.end_headers(); self.wfile.write(body); return
                if tail == ["runner"]:
                    # Compatibility read for the old rich workbench.  This
                    # is intentionally a read-only Runner snapshot; writes
                    # use the explicit runner sub-routes below and retain the
                    # runtime-owned writer identity.
                    runner = service.legacy_adapter._runner
                    if runner is None:
                        raise DomainError(
                            "effect_failed", "论文流程执行器当前不可用。", category="effect",
                            task_id=task_id, retryable=True,
                        )
                    self._json(200, {"task_id": task_id, "snapshot": runner.snapshot(task_id)}); return
                if tail == ["delivery", "manifest"]:
                    task = service.get_task(task_id)
                    self._json(200, task.get("delivery_manifest") or build_delivery_manifest(task)); return
                if len(tail) == 3 and tail[0] == "figure-references" and tail[2] == "content":
                    reader = getattr(service.legacy_adapter._runner, "read_figure_reference_preview", None)
                    if not callable(reader):
                        self._json(404, {"error": {"code": "not_found"}}); return
                    try:
                        preview = resolve_reference_content(
                            task_id, tail[1], reader,
                            actor={"actor_id": principal_id, "surface": "business"},
                        )
                    except (ContractError, ValueError, FileNotFoundError, KeyError, TypeError, OSError):
                        self._json(404, {"error": {"code": "not_found", "message": "参考图预览不存在或已失效。"}}); return
                    self.send_response(200)
                    self.send_header("Content-Type", preview["media_type"])
                    self.send_header("Content-Length", str(len(preview["body"])))
                    self.send_header("ETag", f'"sha256:{preview["sha256"]}"')
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Content-Security-Policy", "default-src 'none'; img-src data:; object-src 'none'")
                    self.end_headers(); self.wfile.write(preview["body"]); return
                if len(tail) == 3 and tail[0] == "artifacts" and tail[2] == "content":
                    historical = parse_qs(parsed.query).get("version") == ["historical"]
                    filename, body, media = service.read_artifact_preview(task_id, tail[1], allow_historical=historical)
                    if media == "application/pdf" and "preview" in parse_qs(parsed.query):
                        from .pdf_preview import pdf_response
                        try:
                            body, media = pdf_response(body, filename, self.path, task_id)
                        except ValueError as exc:
                            raise DomainError("validation_failed", str(exc), category="validation") from exc
                        self._send(200, body, media); return
                    self.send_response(200)
                    self.send_header("Content-Type", media)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Content-Disposition", "inline; filename*=UTF-8''" + quote(filename, safe=""))
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Content-Security-Policy", "sandbox; default-src 'none'")
                    self.send_header("X-PaperSpine-Artifact-Version", "historical" if historical else "current")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers(); self.wfile.write(body); return
                if len(tail) == 3 and tail[0] == "artifacts" and tail[2] == "download":
                    historical = parse_qs(parsed.query).get("version") == ["historical"]
                    filename, body = service.read_artifact(task_id, tail[1], allow_historical=historical)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(filename, safe=""))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers(); self.wfile.write(body); return
                if tail == ["events"] and self.headers.get("Accept", "").find("text/event-stream") < 0:
                    query = parse_qs(parsed.query)
                    after = int(query.get("after_sequence", ["0"])[0])
                    self._json(200, {"task_id": task_id, "events": service.list_task_events(
                        task_id, after_sequence=after
                    )}); return
                if tail in (["events", "stream"], ["events"]):
                    last_event_id = self.headers.get("Last-Event-ID")
                    after = 0
                    if last_event_id:
                        prior = service.list_task_events(task_id)
                        found = next((event for event in prior if event["event_id"] == last_event_id), None)
                        if found is None:
                            raise DomainError("validation_failed", "Last-Event-ID is not in this task.",
                                              category="validation", task_id=task_id)
                        after = found["sequence"]
                    events = service.list_task_events(task_id, after_sequence=after)
                    chunks = []
                    for event in events:
                        chunks.append(f"id: {event['event_id']}\nevent: task-event\ndata: " + json.dumps(event, ensure_ascii=False) + "\n\n")
                    chunks.append("event: snapshot-end\ndata: {}\n\n")
                    self._send(200, "".join(chunks).encode("utf-8"),
                               "text/event-stream; charset=utf-8"); return
                self._json(404, {"error": {"code": "not_found"}})
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                # Browser navigation/download cancellation is not a domain
                # failure and must not turn into a noisy server traceback.
                return
            except DomainError as exc:
                self._error(exc)
            except ValueError:
                self._error(DomainError("validation_failed", "读取请求无效，请刷新后继续。", category="validation", task_id=task_id))

    return Handler


def create_business_server(service: ApplicationService, *, principal_id: str,
                           session_id: str, port: int = 0,
                           reviewer_id: str | None = None,
                           reviewer_credential: str | None = None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_business_handler(
        service, principal_id=principal_id, session_id=session_id,
        reviewer_id=reviewer_id, reviewer_credential=reviewer_credential
    ))


def create_reviewer_business_server(
    service: ApplicationService, *, reviewer_id: str, reviewer_credential: str,
    session_id: str = "reviewer", port: int = 0,
) -> ThreadingHTTPServer:
    """Trusted factory for the opt-in independent-review HTTP facade.

    Keeping this separate from the ordinary business factory makes the trust
    boundary explicit at call sites.  The credential is checked per request
    by :func:`make_business_handler` and is never accepted from JSON.
    """
    return create_business_server(
        service, principal_id=reviewer_id, session_id=session_id, port=port,
        reviewer_id=reviewer_id, reviewer_credential=reviewer_credential,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("mcp-stdio", "business-http"))
    parser.add_argument("--user-data-root", required=True)
    parser.add_argument("--core-root", required=True)
    parser.add_argument("--domain-database", required=True)
    parser.add_argument("--contracts-root", required=True)
    parser.add_argument("--principal-id", required=True)
    parser.add_argument("--session-id", default="")
    # Reviewer access is opt-in.  A normal host process gets no reviewer
    # tool/route unless it is started with an explicit independent identity.
    parser.add_argument("--reviewer-id", default=None)
    parser.add_argument("--reviewer-credential", default=None,
                        help="trusted HTTP reviewer credential (never put this in JSON body)")
    parser.add_argument("--port", type=int, default=0)
    return parser


def main() -> None:
    args = _parser().parse_args()
    service, kernel = build_application(
        user_data_root=args.user_data_root, core_root=args.core_root,
        domain_database=args.domain_database, contracts_root=args.contracts_root,
        initialize_on_startup=args.mode != 'mcp-stdio',
    )
    try:
        if args.mode == "mcp-stdio":
            create_mcp_server(service, principal_id=args.principal_id,
                              reviewer_id=args.reviewer_id).run()
        else:
            server = create_business_server(
                service, principal_id=args.principal_id, session_id=args.session_id,
                port=args.port, reviewer_id=args.reviewer_id,
                reviewer_credential=args.reviewer_credential,
            )
            print(json.dumps({"port": server.server_port}), flush=True)
            server.serve_forever()
    finally:
        kernel.close(flush=not service._startup_pending)


if __name__ == "__main__":
    main()
