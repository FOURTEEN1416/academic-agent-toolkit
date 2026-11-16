"""Version-locked Product Runner for recoverable J1--J11 collaboration.

The Runner inventories capability-granted material roots, materializes a typed
run contract, and persists each academic gate through the ProductKernel CAS
transaction.  Domain and target content is supplied by runtime research and
review agents; the Runner owns only typed orchestration and fail-closed state.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import posixpath
import re
import secrets
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from xml.etree import ElementTree

from .contracts import ContractError, load_json
from .figure_correction import (
    FigureCorrectionError,
    FigureCorrectionService,
    build_pdf_text_overlay,
    canonical_sha256 as figure_canonical_sha256,
    pdf_render_region_sha256,
    review_target_size_legibility,
    validate_figure_correction_receipt,
    validate_target_size_legibility_receipt,
)
from .figure_reference_mapping import (
    FigureReferenceMappingError,
    canonical_sha256 as figure_reference_sha256,
    figure_authority_table_sha256,
    project_figure_plan_for_user,
    validate_trusted_figure_master_receipt,
    validate_figure_reference_plan,
)
from .academic_stage_orchestrator import (
    canonical_input_sha256,
    public_academic_stage_answer_example,
    public_academic_stage_answer_schema,
    public_contribution_confirmation_example,
    public_contribution_confirmation_schema,
    validate_academic_stage_answer,
    validate_academic_stage_result,
    validate_contribution_confirmation,
)
from .product_contracts import (
    PRODUCT_SCHEMA_VERSION,
    task_scoped_artifact_receipt_id,
    validate_artifact_receipt,
    validate_command_envelope,
)
from .product_kernel import (
    IdempotencyConflictError,
    ProductKernel,
    RepositoryCompatibilityError,
    _build_material_grant,
    _canonical_json,
    _is_link_or_reparse,
    _is_relative_to,
    _validate_grant_root,
)
from .product_runner_contracts import (
    GUIDED_RUN_CONFIGURATION_EXAMPLE,
    PUBLIC_RUN_CONFIGURATION_SCHEMA,
    READABLE_RUNNER_VERSIONS,
    RUNNER_PROTOCOL_VERSION,
    RUNNER_VERSION,
    validate_material_source_ledger,
    validate_configuration_material_semantics,
    validate_delegation_user_authority,
    validate_run_configuration,
    validate_run_contract,
    validate_runner_state,
)
from .successor_authority import validate_successor_authority


class ProductRunnerCompatibilityError(RepositoryCompatibilityError):
    """The runner bytes are not compatible with the active task build."""


_TEX_INCLUDE = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")
_TEX_INCLUDEGRAPHICS = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\s*\{([^{}]+)\}")
_FIGURE_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".svg", ".tif", ".tiff", ".eps")
_FIGURE_CANDIDATE_STAGING_ROOT = PurePosixPath("runner/.staging/figure-candidates")
_FIGURE_CANDIDATE_MAX_BYTES = 64 * 1024 * 1024
_FIGURE_CANDIDATE_MEDIA_TYPES = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}
_PUBLIC_FIGURE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ATOMIC_ACADEMIC_BLOCKER_PREFIXES = (
    "BASE_IDENTITY_",
    "IDENTITY_",
    "CHALLENGER_",
    "CLAIM_GRAPH_CHALLENGER_",
)
_ATOMIC_ACADEMIC_BLOCKER_CODES = {
    "FINAL_FIGURE_MAPPING_REQUIRED",
    "REVIEW_NOT_INDEPENDENT",
    "TARGET_CONFLICT_UNRESOLVED",
    "CONFLICT_REGISTER_INVALID",
}


def _without_tex_comments(text: str) -> str:
    """Remove active TeX comments while preserving escaped percent signs."""

    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def _material_relative(base: str, target: str) -> str | None:
    normalized = posixpath.normpath(
        posixpath.join(posixpath.dirname(base), target.replace("\\", "/").strip())
    )
    if normalized in {"", "."} or normalized == ".." or normalized.startswith("../"):
        return None
    return normalized.lstrip("./")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (_canonical_json(value) + "\n").encode("utf-8")


def _validated_figure_candidate_registration(raw: Any) -> dict[str, Any]:
    """Validate the narrow public staging request without accepting authority fields."""

    if not isinstance(raw, dict):
        raise ContractError("figure candidate registration must be an object")
    required = {
        "contract",
        "schema_version",
        "figure_id",
        "candidate_id",
        "reference_plan",
        "staged_relative_path",
        "sha256",
        "size_bytes",
        "external_action_authorized",
    }
    allowed = required | {"reference_plan_payload"}
    if set(raw) - allowed or not required.issubset(raw):
        raise ContractError(
            "figure candidate registration contains unknown or missing fields"
        )
    if (
        raw.get("contract") != "paperspine5.figure-candidate-registration"
        or raw.get("schema_version") != PRODUCT_SCHEMA_VERSION
        or raw.get("external_action_authorized") is not False
    ):
        raise ContractError("figure candidate registration contract is invalid")
    for field in ("figure_id", "candidate_id"):
        value = raw.get(field)
        if not isinstance(value, str) or _PUBLIC_FIGURE_ID.fullmatch(value) is None:
            raise ContractError(f"figure candidate {field} is invalid")
    reference_plan = raw.get("reference_plan")
    if not isinstance(reference_plan, dict) or set(reference_plan) != {
        "artifact_id",
        "sha256",
        "revision_id",
    }:
        raise ContractError(
            "figure candidate reference_plan must be one exact asset binding"
        )
    if (
        not isinstance(reference_plan.get("artifact_id"), str)
        or _PUBLIC_FIGURE_ID.fullmatch(reference_plan["artifact_id"]) is None
        or not isinstance(reference_plan.get("sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", reference_plan["sha256"]) is None
        or isinstance(reference_plan.get("revision_id"), bool)
        or not str(reference_plan.get("revision_id") or "").isdigit()
    ):
        raise ContractError("figure candidate reference_plan binding is invalid")
    if "reference_plan_payload" in raw and not isinstance(
        raw.get("reference_plan_payload"), dict
    ):
        raise ContractError("reference_plan_payload must be an object when supplied")
    sha256 = raw.get("sha256")
    if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        raise ContractError("figure candidate sha256 is invalid")
    size_bytes = raw.get("size_bytes")
    if (
        isinstance(size_bytes, bool)
        or not isinstance(size_bytes, int)
        or size_bytes <= 0
        or size_bytes > _FIGURE_CANDIDATE_MAX_BYTES
    ):
        raise ContractError("figure candidate size_bytes is outside the safe limit")
    staged = raw.get("staged_relative_path")
    if not isinstance(staged, str) or not staged or "\\" in staged or len(staged) > 512:
        raise ContractError(
            "figure candidate staged_relative_path must be POSIX-relative"
        )
    relative = PurePosixPath(staged)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or ":" in staged
        or relative == _FIGURE_CANDIDATE_STAGING_ROOT
        or relative.parts[: len(_FIGURE_CANDIDATE_STAGING_ROOT.parts)]
        != _FIGURE_CANDIDATE_STAGING_ROOT.parts
        or relative.suffix.lower() not in _FIGURE_CANDIDATE_MEDIA_TYPES
    ):
        raise ContractError(
            "figure candidate must be staged below runner/.staging/figure-candidates"
        )
    return deepcopy(raw)


def _verified_figure_candidate_media_type(path: Path, content: bytes) -> str | None:
    """Verify an allow-listed image suffix against its actual bounded bytes."""

    media_type = _FIGURE_CANDIDATE_MEDIA_TYPES.get(path.suffix.lower())
    if media_type == "image/png":
        return media_type if content.startswith(b"\x89PNG\r\n\x1a\n") else None
    if media_type == "image/jpeg":
        return (
            media_type
            if len(content) >= 5
            and content[:3] == b"\xff\xd8\xff"
            and content[-2:] == b"\xff\xd9"
            else None
        )
    if media_type == "image/svg+xml":
        try:
            text = content.decode("utf-8-sig")
            if "<!DOCTYPE" in text.upper():
                return None
            root = ElementTree.fromstring(text)
        except (UnicodeError, ElementTree.ParseError):
            return None
        local_name = root.tag.rsplit("}", 1)[-1] if isinstance(root.tag, str) else ""
        return media_type if local_name == "svg" else None
    return None


def _verified_reference_preview_media_type(
    expected_media_type: str, content: bytes
) -> str | None:
    """Verify reference-preview bytes without trusting a material-object suffix."""

    if expected_media_type == "image/png":
        return expected_media_type if content.startswith(b"\x89PNG\r\n\x1a\n") else None
    if expected_media_type == "image/jpeg":
        return (
            expected_media_type
            if len(content) >= 5
            and content[:3] == b"\xff\xd8\xff"
            and content[-2:] == b"\xff\xd9"
            else None
        )
    if expected_media_type == "image/svg+xml":
        try:
            text = content.decode("utf-8-sig")
            if "<!DOCTYPE" in text.upper():
                return None
            root = ElementTree.fromstring(text)
        except (UnicodeError, ElementTree.ParseError):
            return None
        local_name = root.tag.rsplit("}", 1)[-1] if isinstance(root.tag, str) else ""
        return expected_media_type if local_name == "svg" else None
    return None


def _public_reference_source_locator(value: Any) -> str:
    """Keep public citations useful while never projecting a local path."""

    locator = str(value or "").strip()
    if re.match(r"^(?:https?://|doi:)", locator, flags=re.IGNORECASE):
        return locator
    return "本地或受限来源（路径已隐藏）"


def _safe_actor(actor: dict[str, Any] | None, writer_id: str) -> dict[str, Any]:
    return actor or {"actor_id": writer_id, "surface": "system"}


def _atomic_academic_blockers(blockers: Any) -> list[dict[str, Any]]:
    """Return trust/conflict failures that must leave no committed transition."""

    if not isinstance(blockers, list):
        return []
    return [
        item
        for item in blockers
        if isinstance(item, dict)
        and (
            str(item.get("code") or "") in _ATOMIC_ACADEMIC_BLOCKER_CODES
            or str(item.get("code") or "").startswith(_ATOMIC_ACADEMIC_BLOCKER_PREFIXES)
        )
    ]


class ProductRunner:
    """J1--J11 execution service registered into one ProductKernel instance."""

    RECOVERY_BOUNDARIES = {
        "intake": "awaiting_research",
        "citation_research": "awaiting_contribution",
        "drafting_canonical": "awaiting_canonical",
        "latex_rendering": "awaiting_review",
    }

    COMMANDS = {
        "runner.inputs.update",
        "runner.materials.add",
        "runner.bootstrap",
        "runner.issue.answer",
        "runner.resume",
        "runner.revision.request",
        "runner.successor.resume",
    }

    def __init__(
        self,
        kernel: ProductKernel,
        *,
        expected_build_id: str | None = None,
        max_files: int = 4096,
        max_total_bytes: int = 512 * 1024 * 1024,
        academic_orchestrator: Any | None = None,
        figure_correction_executor: Callable[
            [dict[str, Any], str | Path], dict[str, Any]
        ]
        | None = None,
        figure_correction_reviewer: Callable[[dict[str, Any]], dict[str, Any]]
        | None = None,
        successor_authority_resolver: Callable[[dict[str, Any]], dict[str, Any]]
        | None = None,
        confirmation_clock: Callable[[], str] | None = None,
    ) -> None:
        self.kernel = kernel
        self.expected_build_id = (
            expected_build_id or kernel.product_manifest["build_id"]
        )
        if self.expected_build_id != kernel.product_manifest["build_id"]:
            raise ProductRunnerCompatibilityError(
                "ProductRunner expected_build_id does not match the active ProductKernel"
            )
        components = kernel.product_manifest.get("component_versions", {})
        compatibility = kernel.product_manifest.get("compatibility", {})
        if (
            components.get("product_runner") != RUNNER_VERSION
            or compatibility.get("product_runner_protocol") != RUNNER_PROTOCOL_VERSION
        ):
            raise ProductRunnerCompatibilityError(
                "active Product Manifest does not lock this ProductRunner version/protocol"
            )
        if (
            isinstance(max_files, bool)
            or not isinstance(max_files, int)
            or max_files <= 0
        ):
            raise ContractError("max_files must be a positive integer")
        if (
            isinstance(max_total_bytes, bool)
            or not isinstance(max_total_bytes, int)
            or max_total_bytes <= 0
        ):
            raise ContractError("max_total_bytes must be a positive integer")
        self.max_files = max_files
        self.max_total_bytes = max_total_bytes
        self.figure_correction_executor = figure_correction_executor
        self.figure_correction_reviewer = figure_correction_reviewer
        self.successor_authority_resolver = successor_authority_resolver
        self.confirmation_clock = confirmation_clock or _now
        if academic_orchestrator is None:
            from .academic_stage_orchestrator import AcademicStageOrchestrator

            academic_orchestrator = AcademicStageOrchestrator(
                product_build_id=self.expected_build_id
            )
        self.academic_orchestrator = academic_orchestrator
        self.handler_id = (
            f"paperspine5.product-runner.{RUNNER_VERSION}+{self.expected_build_id}"
        )
        handlers = {
            "runner.inputs.update": self._handle_update_inputs,
            "runner.materials.add": self._handle_add_materials,
            "runner.bootstrap": self._handle_bootstrap,
            "runner.delegated-grant.renew": self._handle_delegated_grant_renew,
            "runner.issue.answer": self._handle_answer_issue,
            "runner.resume": self._handle_resume,
            "runner.revision.request": self._handle_revision_request,
            "runner.successor.resume": self._handle_successor_resume,
        }
        self._handler_registrations: dict[str, str] = {}
        for command_type, handler in handlers.items():
            self._handler_registrations[command_type] = (
                self.kernel.register_command_handler(
                    command_type,
                    handler_id=self.handler_id,
                    product_build_id=self.expected_build_id,
                    handler=handler,
                )
            )

    @staticmethod
    def _figure_master_actor_matches_attestation(
        actor: dict[str, Any], identity: dict[str, Any]
    ) -> bool:
        from .quality_readiness import identity_provenance_sha256

        return (
            actor.get("authority_kind")
            in {"authenticated_local_user_session", "host_user_message"}
            and actor.get("surface")
            in {"codex", "claude-code", "dsh", "standalone-skill", "web", "mcp", "cli"}
            and actor.get("actor_id") == identity.get("principal_id")
            and actor.get("session_id") == identity.get("session_id")
            and actor.get("run_id") == identity.get("run_id")
            and actor.get("attestation_input_id")
            == identity.get("attestation_input_id")
            and actor.get("provenance_sha256") == identity.get("provenance_sha256")
            and identity.get("provenance_sha256")
            == identity_provenance_sha256(identity)
        )

    def _trusted_figure_master_receipt(
        self,
        *,
        actor: dict[str, Any],
        current_stage: str,
        persisted_base_artifacts: dict[str, dict[str, Any]],
        effective_base_artifacts: dict[str, dict[str, Any]],
        task: dict[str, Any] | None = None,
        require_actor_binding: bool = True,
    ) -> dict[str, Any] | None:
        """Resolve Runner-owned figure authority; public payloads cannot supply it."""

        plans = [
            value
            for value in effective_base_artifacts.values()
            if value.get("contract") == "paperspine5.figure-reference-plan"
        ]
        if not plans:
            return None
        persisted = persisted_base_artifacts.get("figure-master-authority")
        if persisted is not None:
            try:
                receipt = validate_trusted_figure_master_receipt(persisted)
            except FigureReferenceMappingError as exc:
                raise ContractError(
                    f"persisted figure Master authority receipt is invalid: {exc}"
                ) from exc
        else:
            # Legacy tasks created before the figure-Master receipt existed can
            # arrive at J7 with a newly supplied, hash-bound reference plan but
            # without the persisted authority receipt.  If the immutable plan
            # identity and the current host actor still match exactly, derive
            # the same Runner-owned receipt here.  This preserves the authority
            # boundary while allowing a same-task migration to re-enter J7;
            # arbitrary caller-supplied plans still fail the identity checks.
            if current_stage not in {"awaiting_claim_graph", "awaiting_figure_intent"}:
                raise ContractError(
                    "figure Master authority must be established before J7 execution"
                )
            attestation_ids = {
                str(plan.get("mapping_authority", {}).get("attestation_input_id") or "")
                for plan in plans
                if isinstance(plan.get("mapping_authority"), dict)
            }
            if len(attestation_ids) != 1 or "" in attestation_ids:
                raise ContractError(
                    "figure reference plans must share one current Master attestation"
                )
            attestation_id = next(iter(attestation_ids))
            identity = effective_base_artifacts.get(attestation_id)
            if (
                not isinstance(identity, dict)
                or identity.get("attestation_input_id") != attestation_id
                or not self._figure_master_actor_matches_attestation(actor, identity)
            ):
                raise ContractError(
                    "figure Master authority does not match the current host actor and identity input"
                )
            receipt = {
                "contract": "paperspine5.figure-master-authority-receipt",
                "schema_version": "1.0",
                "authority_kind": "paperspine_master",
                "principal_id": identity["principal_id"],
                "session_id": identity["session_id"],
                "run_id": identity["run_id"],
                "attestation_input_id": attestation_id,
                "attestation_provenance_sha256": identity["provenance_sha256"],
                "authority_table_sha256": figure_authority_table_sha256(),
                "source": "runner_current_actor_and_persisted_attestation",
                "actor_surface": actor["surface"],
                "actor_authority_kind": actor["authority_kind"],
                "external_action_authorized": False,
            }
            receipt["receipt_sha256"] = figure_reference_sha256(receipt)
            receipt = validate_trusted_figure_master_receipt(receipt)

        if receipt["authority_table_sha256"] != figure_authority_table_sha256():
            from .figure_final_mapping import legacy_method_is_accepted
            if task is None or not legacy_method_is_accepted(self, task, receipt["authority_table_sha256"]):
                raise ContractError(
                    "figure Master authority receipt does not bind the current PaperSpine method or sealed accepted history"
                )
        # During same-task migration into J7, the identity input and plan may
        # be supplied in the current answer before Runner persists them.  The
        # actor binding above is the trust check for that narrow path; once a
        # receipt exists we continue to prefer the persisted immutable ledger.
        attestation_source = persisted_base_artifacts if persisted is not None else effective_base_artifacts
        identity = attestation_source.get(receipt["attestation_input_id"])
        if (
            not isinstance(identity, dict)
            or identity.get("principal_id") != receipt["principal_id"]
            or identity.get("session_id") != receipt["session_id"]
            or identity.get("run_id") != receipt["run_id"]
            or identity.get("attestation_input_id") != receipt["attestation_input_id"]
            or identity.get("provenance_sha256")
            != receipt["attestation_provenance_sha256"]
        ):
            raise ContractError(
                "figure Master authority receipt is detached from its immutable identity input"
            )
        if require_actor_binding and current_stage in {
            "awaiting_claim_graph",
            "awaiting_figure_intent",
        } and (
            not self._figure_master_actor_matches_attestation(actor, identity)
            or actor.get("surface") != receipt["actor_surface"]
            or actor.get("authority_kind") != receipt["actor_authority_kind"]
        ):
            raise ContractError(
                "figure Master authority is not bound to the current Runner actor"
            )
        return receipt

    def snapshot(self, task_id: str) -> dict[str, Any]:
        task = self.kernel.get_task(task_id)
        compatibility_issue = self._compatibility_issue(task)
        runner_state = task["state"].get("runner")
        if runner_state is None:
            stage = "uninitialized"
            issues = [compatibility_issue] if compatibility_issue else []
            next_actions = [] if issues else ["runner.bootstrap"]
            material_pointer = None
            contract_pointer = None
            academic_inputs = None
            academic_artifacts = None
            academic_base_artifacts = None
        else:
            if (
                compatibility_issue
                and compatibility_issue["code"] == "runner.build_incompatible"
            ):
                migration = self._preview_successor_migration(task)
                runner_state = migration["source_runner_state"]
                compatibility_issue = migration["issue"]
            else:
                validate_runner_state(
                    runner_state, task_id=task_id, build_id=self.expected_build_id
                )
            stage = runner_state["stage"]
            issues = [
                item
                for item in runner_state.get("issues", [])
                if item["status"] == "open"
            ]
            if compatibility_issue:
                issues = [compatibility_issue, *issues]
            next_actions = (
                list(runner_state.get("next_actions", []))
                if not compatibility_issue
                else []
            )
            if (
                compatibility_issue
                and compatibility_issue["code"] == "runner.successor_migration_required"
            ):
                # Only a verified successor preview permits this mutation. Keep
                # predecessor academic actions unavailable until resume commits.
                next_actions = ["runner.resume"]
            material_pointer = runner_state.get("material_inventory")
            contract_pointer = runner_state.get("run_contract")
            academic_inputs = runner_state.get("academic_inputs")
            academic_artifacts = runner_state.get("academic_artifacts")
            academic_base_artifacts = runner_state.get("academic_base_artifacts")
        issues = [self._public_issue_projection(item) for item in issues]
        artifacts = self.kernel.list_artifacts(
            task_id, subject_revision=task["revision"]
        )
        inventory_fresh, inventory_payload = self._pointer_fresh(
            task,
            material_pointer,
            artifacts,
            artifact_type="materials.source-ledger",
        )
        contract_fresh, contract_payload = self._pointer_fresh(
            task,
            contract_pointer,
            artifacts,
            artifact_type="runner.run-contract",
            inventory=inventory_payload if inventory_fresh else None,
        )
        interaction = {
            "mode": "guided",
            "requested_scope": "local_delivery",
            "grant_status": "not_applicable",
            "grant_id": None,
            "grant_sha256": None,
            "decision_classes": [],
            "decision_receipts": [],
            "external_action_authorized": False,
        }
        if contract_fresh and isinstance(contract_payload, dict):
            configuration = contract_payload.get("configuration")
            if isinstance(configuration, dict):
                configured_interaction = configuration.get("interaction")
                interaction["requested_scope"] = configuration.get(
                    "requested_scope", "local_delivery"
                )
                if isinstance(configured_interaction, dict):
                    interaction["mode"] = configured_interaction.get("mode", "guided")
                    grant = configured_interaction.get("grant")
                    if interaction["mode"] == "delegated_local_test" and isinstance(
                        grant, dict
                    ):
                        interaction.update(
                            {
                                "grant_status": "valid",
                                "grant_id": grant.get("grant_id"),
                                "grant_sha256": grant.get("grant_sha256"),
                                "decision_classes": list(
                                    grant.get("decision_classes", [])
                                ),
                            }
                        )
        if isinstance(academic_artifacts, dict):
            interaction["decision_receipts"] = sorted(
                artifact_id
                for artifact_id in academic_artifacts
                if artifact_id.startswith("delegated-decision.")
            )
        figure_quality = self._figure_quality_projection(academic_base_artifacts)
        figure_review = self._figure_review_projection(
            task,
            academic_inputs,
            artifacts,
        )
        from .paper_revision import user_revision_projection
        return {
            "contract": "paperspine5.runner-snapshot",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "runner_version": RUNNER_VERSION,
            "product_build_id": self.expected_build_id,
            "task_id": task_id,
            "revision": task["revision"],
            "task_status": task["status"],
            "stage": stage,
            "open_issues": issues,
            "next_actions": next_actions,
            "material_inventory": material_pointer,
            "material_inventory_fresh": inventory_fresh,
            "run_contract": contract_pointer,
            "run_contract_fresh": contract_fresh and inventory_fresh,
            "academic_inputs": academic_inputs,
            "academic_artifacts": academic_artifacts,
            "academic_base_artifacts": academic_base_artifacts,
            "figure_quality": figure_quality,
            "figure_review": figure_review,
            "user_revision_request": user_revision_projection(task),
            "interaction": interaction,
            "migration_status": task["migration_status"],
            "successor_migration": runner_state.get("successor_migration")
            if isinstance(runner_state, dict)
            else None,
            "external_action_authorized": False,
        }

    @classmethod
    def _recovery_boundary(cls, stage: str) -> str:
        exact = {
            expected_stage: boundary
            for boundary, expected_stage in cls.RECOVERY_BOUNDARIES.items()
        }
        if stage in exact:
            return exact[stage]
        order = {
            "uninitialized": -2,
            "awaiting_configuration": -1,
            "configured": -1,
            "awaiting_research": 0,
            "awaiting_contribution": 1,
            "awaiting_claim_graph": 1,
            "awaiting_figure_intent": 1,
            "awaiting_canonical": 2,
            "awaiting_review": 3,
            "awaiting_package": 3,
            "target_package_ready": 4,
        }
        position = order.get(stage, -2)
        if position < 0:
            return "intake"
        if position < 2:
            return "citation_research"
        if position < 3:
            return "drafting_canonical"
        return "latex_rendering"

    def recovery_snapshot(self, task_id: str) -> dict[str, Any]:
        """Build a stable, chat-free recovery identity from SQLite and receipts."""

        snapshot = self.snapshot(task_id)
        artifact_descriptors: list[dict[str, Any]] = []
        for view in self.kernel.list_artifacts(task_id):
            receipt = view["receipt"]
            artifact_descriptors.append(
                {
                    "artifact_id": receipt["artifact_id"],
                    "artifact_type": receipt["artifact_type"],
                    "subject_revision": int(receipt["subject"]["revision_id"]),
                    "sha256": receipt["sha256"],
                    "freshness": view["freshness"],
                }
            )
        artifact_descriptors.sort(
            key=lambda item: (
                item["subject_revision"],
                item["artifact_id"],
                item["sha256"],
            )
        )
        command_descriptors: list[dict[str, Any]] = []
        for command in self.kernel.list_commands(task_id):
            envelope = command["envelope"]
            result = command["result"]
            command_descriptors.append(
                {
                    "command_id": command["command_id"],
                    "command_type": envelope.get("command_type", "task.create"),
                    "expected_revision": envelope.get("expected_revision"),
                    "resulting_revision": result.get("resulting_revision"),
                    "status": result.get("status"),
                    "prepared_sha256": (command.get("registered_handler") or {}).get(
                        "prepared_sha256"
                    ),
                }
            )
        command_descriptors.sort(key=lambda item: item["command_id"])
        package_descriptors = [
            item
            for item in artifact_descriptors
            if item["artifact_id"].startswith(
                (
                    "publication.manuscript-head",
                    "publication.package",
                    "publication.bundle",
                    "package.",
                    "readiness.",
                )
            )
            or item["artifact_type"]
            in {
                "publication.canonical-bundle",
                "publication.package-archive",
                "quality.readiness-verdict",
            }
        ]
        material_pointer = snapshot.get("material_inventory") or {}
        task_identity = {
            "task_id": task_id,
            "revision": snapshot["revision"],
            "stage": snapshot["stage"],
            "task_status": snapshot["task_status"],
            "product_build_id": snapshot["product_build_id"],
            "material_snapshot_sha256": material_pointer.get("snapshot_sha256"),
            "run_contract_sha256": (snapshot.get("run_contract") or {}).get("sha256"),
            "figure_quality": snapshot.get("figure_quality"),
            "readiness": snapshot.get("readiness"),
        }
        recovery = {
            "contract": "paperspine5.runner-recovery-snapshot",
            "schema_version": "1.0",
            "task_id": task_id,
            "product_build_id": snapshot["product_build_id"],
            "revision": snapshot["revision"],
            "stage": snapshot["stage"],
            "boundary": self._recovery_boundary(snapshot["stage"]),
            "earliest_incomplete_stage": snapshot["stage"],
            "material_snapshot_sha256": material_pointer.get("snapshot_sha256"),
            "task_state_sha256": _sha256_bytes(_json_bytes(task_identity)),
            "committed_command_count": len(command_descriptors),
            "command_set_sha256": _sha256_bytes(_json_bytes(command_descriptors)),
            "artifact_count": len(artifact_descriptors),
            "artifact_set_sha256": _sha256_bytes(_json_bytes(artifact_descriptors)),
            "package_artifact_count": len(package_descriptors),
            "package_set_sha256": _sha256_bytes(_json_bytes(package_descriptors)),
            "chat_replay_used": False,
            "external_action_authorized": False,
        }
        recovery["recovery_sha256"] = _sha256_bytes(_json_bytes(recovery))
        return recovery

    def validate_recovery_snapshot(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ContractError("runner recovery snapshot must be an object")
        required = {
            "contract",
            "schema_version",
            "task_id",
            "product_build_id",
            "revision",
            "stage",
            "boundary",
            "earliest_incomplete_stage",
            "material_snapshot_sha256",
            "task_state_sha256",
            "committed_command_count",
            "command_set_sha256",
            "artifact_count",
            "artifact_set_sha256",
            "package_artifact_count",
            "package_set_sha256",
            "chat_replay_used",
            "external_action_authorized",
            "recovery_sha256",
        }
        if set(value) != required:
            raise ContractError("runner recovery snapshot fields are not exact")
        if (
            value.get("contract") != "paperspine5.runner-recovery-snapshot"
            or value.get("schema_version") != "1.0"
            or value.get("boundary") not in self.RECOVERY_BOUNDARIES
            or value.get("chat_replay_used") is not False
            or value.get("external_action_authorized") is not False
        ):
            raise ContractError("runner recovery snapshot authority is invalid")
        expected = _sha256_bytes(
            _json_bytes(
                {key: item for key, item in value.items() if key != "recovery_sha256"}
            )
        )
        if not hmac.compare_digest(str(value.get("recovery_sha256")), expected):
            raise ContractError("runner recovery snapshot hash is invalid")
        return deepcopy(value)

    def recover_task(self, task_id: str, *, writer_id: str) -> dict[str, Any]:
        """Recover one task without chat replay or re-running committed work."""

        if not isinstance(writer_id, str) or not writer_id:
            raise ContractError("recovery writer_id must be non-empty")
        self.kernel.acquire_writer_lease(task_id, writer_id)
        self.kernel.recover_outbox()
        cleanup = self.reconcile_orphans(task_id, apply=True)
        snapshot = self.recovery_snapshot(task_id)
        return {**snapshot, "cleanup": cleanup}

    @staticmethod
    def _figure_quality_projection(
        academic_base_artifacts: dict[str, Any] | None,
    ) -> dict[str, Any]:
        pointers = academic_base_artifacts or {}
        corrections = sorted(
            artifact_id
            for artifact_id in pointers
            if artifact_id.startswith("figure-correction.")
        )
        legibility = sorted(
            artifact_id
            for artifact_id in pointers
            if artifact_id.startswith("target-size-legibility.")
        )
        return {
            "contract": "paperspine5.figure-quality-projection",
            "contract_version": "1.0",
            "correction_receipts": corrections,
            "target_size_legibility_receipts": legibility,
            "status": "PASS" if legibility else "not_evaluated",
            "external_action_authorized": False,
        }

    def _accepted_academic_view(
        self, task: dict[str, Any], artifact_id: str
    ) -> dict[str, Any] | None:
        """Read the exact state-selected accepted receipt, not a historical PASS.

        A blocked downstream attempt can record a new revision without accepting
        every replayed descriptor. Its retained pointers still name the last
        accepted scientific revision; byte freshness is checked at that receipt's
        revision. At J8, only the exact state-selected accepted J7 intent may cross
        that revision boundary so current final mappings can be revalidated.
        """
        state = self._runner_state(task)
        pointer = (state.get("academic_artifacts") or {}).get(artifact_id)
        if not isinstance(pointer, dict) or pointer.get("artifact_id") != artifact_id:
            return None
        payload = self._load_run_json(task, str(pointer.get("path") or ""))
        subject = payload.get("subject", {})
        revision = subject.get("revision_id")
        from .paper_revision import retained_pointer
        user_retained = retained_pointer(task, "academic_artifacts", artifact_id)
        # A blocked J9 review increments the runner revision before the host
        # can resubmit the exact re-review.  Keep the previously accepted J7
        # figure intent readable during that recovery window; it remains the
        # selected scientific input and is not a new figure decision.
        downstream_retained = state["stage"] in {"awaiting_package", "awaiting_review"} or (
            state["stage"] == "awaiting_canonical"
            and artifact_id == "publication.figure-intent"
        )
        if (
            not isinstance(revision, str) or not revision.isdigit()
            or subject.get("task_id") != task["task_id"]
            or int(revision) > task["revision"]
            or (
                int(revision) != task["revision"]
                and not downstream_retained
                and not user_retained
            )
        ):
            return None
        root = Path(task["run_root"]).resolve()
        pointer_path = (root / pointer["path"]).resolve()
        matches = [
            view for view in self.kernel.list_artifacts(task["task_id"], subject_revision=int(revision))
            if view.get("freshness") == "fresh"
            and view.get("payload") == payload
            and all(view["receipt"].get(key) == pointer.get(key)
                    for key in ("artifact_id", "artifact_type", "sha256", "size_bytes"))
            and (root / view["receipt"]["path"]).resolve() == pointer_path
        ]
        return matches[0] if len(matches) == 1 else None

    def _figure_review_projection(
        self,
        task: dict[str, Any],
        pointer: dict[str, Any] | None,
        artifacts: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Project the accepted J7 record only from its current ledger receipt."""

        if not isinstance(pointer, dict):
            return None
        matching = [
            view
            for view in artifacts
            if view.get("freshness") == "fresh"
            and isinstance(view.get("receipt"), dict)
            and view["receipt"].get("artifact_id") == pointer.get("artifact_id")
        ]
        if len(matching) != 1:
            return None
        receipt = matching[0]["receipt"]
        receipt_subject = receipt.get("subject")
        run_root = Path(task["run_root"]).resolve()
        receipt_path = Path(str(receipt.get("path") or ""))
        pointer_path = Path(str(pointer.get("path") or ""))
        if not receipt_path.is_absolute():
            receipt_path = run_root / receipt_path
        if not pointer_path.is_absolute():
            pointer_path = run_root / pointer_path
        if (
            receipt.get("artifact_type")
            not in {"runner.academic-inputs", "runner.successor-academic-inputs"}
            or pointer.get("artifact_type") != receipt.get("artifact_type")
            or receipt_path.resolve() != pointer_path.resolve()
            or any(
                pointer.get(field) != receipt.get(field)
                for field in ("sha256", "size_bytes")
            )
            or not isinstance(receipt_subject, dict)
            or receipt_subject.get("task_id") != task["task_id"]
            or str(receipt_subject.get("revision_id")) != str(task["revision"])
        ):
            return None
        try:
            cumulative = self._read_academic_inputs(task, pointer)
        except (ContractError, OSError):
            return None
        stage_inputs = cumulative.get("stage_inputs")
        j7 = (
            stage_inputs.get("awaiting_figure_intent")
            if isinstance(stage_inputs, dict)
            else None
        )
        intent = j7.get("intent") if isinstance(j7, dict) else None
        raw_figures = intent.get("figures") if isinstance(intent, dict) else None
        mode = intent.get("mode") if isinstance(intent, dict) else None
        if not isinstance(mode, str) or not isinstance(raw_figures, list):
            return None
        accepted_views = [
            view
            for view in artifacts
            if view.get("freshness") == "fresh"
            and isinstance(view.get("receipt"), dict)
            and view["receipt"].get("artifact_id") == "publication.figure-intent"
            and isinstance(view.get("payload"), dict)
            and view["payload"].get("contract") == "paperspine5.figure-intent"
            and view["payload"].get("status") == "PASS"
            and view["payload"].get("external_action_authorized") is False
            and isinstance(view["payload"].get("subject"), dict)
            and view["payload"]["subject"].get("task_id") == task["task_id"]
            and str(view["payload"]["subject"].get("revision_id"))
            == str(task["revision"])
        ]
        if not accepted_views:
            retained = self._accepted_academic_view(task, "publication.figure-intent")
            if (retained is not None
                    and retained["payload"].get("contract") == "paperspine5.figure-intent"
                    and retained["payload"].get("status") == "PASS"
                    and retained["payload"].get("external_action_authorized") is False):
                accepted_views = [retained]
        if len(accepted_views) != 1:
            return None
        accepted_figures_raw = accepted_views[0]["payload"].get("figures")
        if not isinstance(accepted_figures_raw, list):
            return None
        accepted_by_id: dict[str, dict[str, Any]] = {}
        for accepted_figure in accepted_figures_raw:
            if not isinstance(accepted_figure, dict):
                return None
            accepted_id = accepted_figure.get("figure_id")
            if (
                not isinstance(accepted_id, str)
                or not accepted_id
                or accepted_id in accepted_by_id
            ):
                return None
            accepted_by_id[accepted_id] = accepted_figure
        figures: list[dict[str, Any]] = []
        for raw_figure in raw_figures:
            if not isinstance(raw_figure, dict):
                return None
            figure_id = raw_figure.get("figure_id")
            panels = raw_figure.get("panels")
            candidate_assets = raw_figure.get("candidate_assets", [])
            comparison = raw_figure.get("independent_comparison")
            if (
                not isinstance(figure_id, str)
                or not figure_id
                or not isinstance(panels, list)
                or not isinstance(candidate_assets, list)
                or (comparison is not None and not isinstance(comparison, dict))
            ):
                return None
            accepted_figure = accepted_by_id.get(figure_id)
            reference_plan_binding = (
                accepted_figure.get("reference_plan_binding")
                if isinstance(accepted_figure, dict)
                else None
            )
            reference_plan = (
                accepted_figure.get("reference_plan")
                if isinstance(accepted_figure, dict)
                else None
            )
            projected_figure = (
                reference_plan.get("figure")
                if isinstance(reference_plan, dict)
                else None
            )
            if (
                not isinstance(reference_plan_binding, dict)
                or not isinstance(reference_plan, dict)
                or not isinstance(projected_figure, dict)
                or projected_figure.get("figure_id") != figure_id
                or reference_plan.get("external_action_authorized") is not False
            ):
                return None
            figures.append(
                {
                    "figure_id": figure_id,
                    "role": str(
                        raw_figure.get("role")
                        or raw_figure.get("placement")
                        or "manuscript_figure"
                    ),
                    "panels": deepcopy(panels),
                    "current_asset": deepcopy(raw_figure.get("current_asset")),
                    "candidate_assets": deepcopy(candidate_assets),
                    "independent_comparison": deepcopy(comparison),
                    "reference_plan_binding": deepcopy(reference_plan_binding),
                    "reference_plan": {
                        key: deepcopy(reference_plan.get(key))
                        for key in (
                            "mapping_id",
                            "plan_status",
                            "figure",
                            "design_provenance",
                            "original_design_rationale",
                            "references",
                            "scientific_story",
                            "domain_mappings",
                            "grammar_reuse_justification",
                            "external_action_authorized",
                        )
                        if key in reference_plan
                    },
                }
            )
        if set(accepted_by_id) != {item["figure_id"] for item in figures}:
            return None
        return {"mode": mode, "figures": figures}

    def _pointer_fresh(
        self,
        task: dict[str, Any],
        pointer: dict[str, Any] | None,
        artifacts: list[dict[str, Any]],
        *,
        artifact_type: str,
        inventory: dict[str, Any] | None = None,
    ) -> tuple[bool, dict[str, Any] | None]:
        if not isinstance(pointer, dict):
            return False, None
        run_root = Path(task["run_root"]).resolve()
        for view in artifacts:
            receipt = view["receipt"]
            if view.get("freshness") != "fresh" or receipt.get(
                "artifact_id"
            ) != pointer.get("artifact_id"):
                continue
            receipt_path = Path(receipt.get("path", ""))
            pointer_path = Path(pointer.get("path", ""))
            if not receipt_path.is_absolute():
                receipt_path = run_root / receipt_path
            if not pointer_path.is_absolute():
                pointer_path = run_root / pointer_path
            if (
                receipt.get("artifact_type") != artifact_type
                or pointer.get("artifact_type") != artifact_type
                or receipt.get("sha256") != pointer.get("sha256")
                or receipt.get("size_bytes") != pointer.get("size_bytes")
                or receipt_path.resolve() != pointer_path.resolve()
            ):
                continue
            try:
                bridge = self._successor_receipt_bridge(
                    task, receipt, artifact_type=artifact_type
                )
                if artifact_type == "materials.source-ledger":
                    payload = self._read_inventory_receipt(
                        task,
                        receipt,
                        task["revision"],
                        build_id=(bridge or {}).get("source_build_id"),
                        runner_version=(bridge or {}).get("source_runner_version"),
                    )
                else:
                    if inventory is None:
                        return False, None
                    payload = self._read_run_contract_receipt(
                        task,
                        receipt,
                        task["revision"],
                        inventory=inventory,
                        build_id=(bridge or {}).get("source_build_id"),
                        runner_version=(bridge or {}).get("source_runner_version"),
                    )
            except (ContractError, OSError):
                return False, None
            if pointer.get("snapshot_sha256") != payload.get(
                "snapshot_sha256",
                payload.get("material_snapshot_sha256"),
            ):
                return False, None
            return True, payload
        return False, None

    def _successor_receipt_bridge(
        self,
        task: dict[str, Any],
        receipt: dict[str, Any],
        *,
        artifact_type: str,
    ) -> dict[str, Any] | None:
        receipt_build = receipt.get("metadata", {}).get("product_build_id")
        if receipt_build == self.expected_build_id:
            return None
        runner = task.get("state", {}).get("runner")
        link = runner.get("successor_migration") if isinstance(runner, dict) else None
        if not isinstance(link, dict):
            return None
        migration_commands: dict[str, dict[str, Any]] = {}
        for committed in self.kernel.list_commands(task["task_id"]):
            envelope = committed.get("envelope")
            if (
                not isinstance(envelope, dict)
                or envelope.get("command_type") != "runner.successor.resume"
            ):
                continue
            payload = envelope.get("payload")
            migration_id = (
                payload.get("migration_id") if isinstance(payload, dict) else None
            )
            if not isinstance(migration_id, str) or not migration_id:
                raise ContractError(
                    "successor migration command is missing its receipt identity"
                )
            if migration_id in migration_commands:
                raise ContractError("successor migration command identity is ambiguous")
            migration_commands[migration_id] = committed

        expected_target_build = self.expected_build_id
        expected_target_runner_version = RUNNER_VERSION
        expected_target_core_root = str(self.kernel.core_root)
        expected_target_manifest_sha256 = _sha256_bytes(
            _json_bytes(task["product_manifest"])
        )
        expected_target_state_sha256 = _sha256_bytes(_json_bytes(task["state"]))
        migration_id = str(link.get("migration_id") or "")
        visited: set[str] = set()
        verified_migrations: list[dict[str, Any]] = []
        observed_sha = (
            receipt.get("metadata", {}).get("material_snapshot_sha256")
            if artifact_type == "materials.source-ledger"
            else receipt.get("sha256")
        )
        material_snapshot_sha256 = receipt.get("metadata", {}).get(
            "material_snapshot_sha256"
        )

        while migration_id:
            if migration_id in visited:
                raise ContractError(
                    "successor migration receipt bridge contains a cycle"
                )
            visited.add(migration_id)
            migration = self.kernel.get_migration_receipt(task["task_id"], migration_id)
            committed = migration_commands.get(migration_id)
            if not isinstance(migration, dict) or not isinstance(committed, dict):
                raise ContractError("successor migration receipt or command is missing")
            unsigned = {
                key: value
                for key, value in migration.items()
                if key != "receipt_sha256"
            }
            source = migration.get("source")
            target = migration.get("target")
            identity = source.get("identity") if isinstance(source, dict) else None
            authority = migration.get("installed_suite_authority")
            preservation = migration.get("preservation")
            recovery = migration.get("recovery")
            envelope = committed.get("envelope")
            result = committed.get("result")
            payload = envelope.get("payload") if isinstance(envelope, dict) else None
            output = result.get("output") if isinstance(result, dict) else None
            identity_unsigned = (
                {
                    key: value
                    for key, value in identity.items()
                    if key != "identity_sha256"
                }
                if isinstance(identity, dict)
                else None
            )
            if (
                migration.get("receipt_sha256") != _sha256_bytes(_json_bytes(unsigned))
                or migration.get("contract")
                != "paperspine5.runner-successor-migration-receipt"
                or migration.get("schema_version") != "1.0"
                or migration.get("migration_id") != migration_id
                or migration.get("task_id") != task["task_id"]
                or migration.get("active_run_id") != task["active_run_id"]
                or migration.get("revision") != task["revision"]
                or migration.get("external_action_authorized") is not False
                or not isinstance(source, dict)
                or not isinstance(target, dict)
                or not isinstance(identity, dict)
                or not isinstance(identity_unsigned, dict)
                or identity.get("identity_sha256")
                != _sha256_bytes(_json_bytes(identity_unsigned))
                or identity.get("task_id") != task["task_id"]
                or identity.get("active_run_id") != task["active_run_id"]
                or identity.get("revision") != task["revision"]
                or identity.get("material_snapshot_sha256") != material_snapshot_sha256
                or target.get("build_id") != expected_target_build
                or target.get("runner_version") != expected_target_runner_version
                or target.get("core_root") != expected_target_core_root
                or target.get("product_manifest_sha256")
                != expected_target_manifest_sha256
                or target.get("task_state_sha256") != expected_target_state_sha256
                or not isinstance(authority, dict)
                or authority.get("authority_sha256") is None
                or authority.get("source_build_id") != source.get("build_id")
                or authority.get("target_build_id") != target.get("build_id")
                or authority.get("source_runner_version")
                != source.get("runner_version")
                or authority.get("target_runner_version")
                != target.get("runner_version")
                or authority.get("external_action_authorized") is not False
                or preservation
                != {
                    "same_task_id": True,
                    "same_active_run_id": True,
                    "same_workspace_root": True,
                    "same_run_root": True,
                    "same_revision": True,
                    "same_stage": True,
                    "same_material_snapshot_sha256": True,
                    "predecessor_artifacts_retained": True,
                    "predecessor_commands_retained": True,
                    "new_task_created": False,
                    "material_snapshot_copied": False,
                }
                or not isinstance(recovery, dict)
                or recovery.get("pre_product_manifest_sha256")
                != identity.get("product_manifest_sha256")
                or recovery.get("pre_task_state_sha256")
                != identity.get("task_state_sha256")
                or recovery.get("pre_artifact_set_sha256")
                != identity.get("artifact_set_sha256")
                or recovery.get("pre_command_set_sha256")
                != identity.get("command_set_sha256")
                or not isinstance(envelope, dict)
                or envelope.get("command_type") != "runner.successor.resume"
                or envelope.get("command_id") != migration.get("command_id")
                or envelope.get("task_id") != task["task_id"]
                or envelope.get("expected_revision") != task["revision"]
                or not isinstance(payload, dict)
                or payload.get("migration_id") != migration_id
                or payload.get("source_build_id") != source.get("build_id")
                or payload.get("target_build_id") != target.get("build_id")
                or payload.get("source_runner_version") != source.get("runner_version")
                or payload.get("target_runner_version") != target.get("runner_version")
                or payload.get("source_identity_sha256")
                != identity.get("identity_sha256")
                or payload.get("material_snapshot_sha256") != material_snapshot_sha256
                or payload.get("authority_sha256") != authority.get("authority_sha256")
                or payload.get("receipt_sha256") != migration.get("receipt_sha256")
                or not isinstance(result, dict)
                or result.get("task_id") != task["task_id"]
                or result.get("command_id") != migration.get("command_id")
                or result.get("status") != "accepted"
                or result.get("previous_revision") != task["revision"]
                or result.get("resulting_revision") != task["revision"]
                or not isinstance(output, dict)
                or output.get("migration_id") != migration_id
                or output.get("migration_receipt_sha256")
                != migration.get("receipt_sha256")
                or output.get("same_task_resumed") is not True
                or output.get("revision_preserved") is not True
                or output.get("external_action_authorized") is not False
            ):
                raise ContractError("successor migration receipt bridge is invalid")

            if len(visited) == 1 and (
                link.get("source_build_id") != source.get("build_id")
                or link.get("target_build_id") != target.get("build_id")
                or link.get("authority_sha256") != authority.get("authority_sha256")
                or link.get("source_identity_sha256") != identity.get("identity_sha256")
            ):
                raise ContractError("successor migration receipt bridge is invalid")

            verified_migrations.append({
                "migration_id": migration_id,
                "receipt_sha256": migration["receipt_sha256"],
                "source_build_id": source["build_id"],
                "target_build_id": target["build_id"],
            })

            if source.get("build_id") == receipt_build:
                expected_sha = (
                    identity.get("material_snapshot_sha256")
                    if artifact_type == "materials.source-ledger"
                    else identity.get("run_contract_sha256")
                )
                if expected_sha != observed_sha:
                    raise ContractError(
                        "successor receipt bridge does not bind this artifact"
                    )
                return {
                    "source_build_id": source["build_id"],
                    "source_runner_version": source["runner_version"],
                    "verified_migrations": verified_migrations,
                }

            candidates: list[str] = []
            for candidate_id in migration_commands:
                if candidate_id in visited:
                    continue
                candidate = self.kernel.get_migration_receipt(
                    task["task_id"], candidate_id
                )
                if not isinstance(candidate, dict):
                    continue
                candidate_target = candidate.get("target")
                if (
                    isinstance(candidate_target, dict)
                    and candidate_target.get("build_id") == source.get("build_id")
                    and candidate_target.get("runner_version")
                    == source.get("runner_version")
                    and candidate_target.get("core_root") == source.get("core_root")
                    and candidate_target.get("product_manifest_sha256")
                    == identity.get("product_manifest_sha256")
                    and candidate_target.get("task_state_sha256")
                    == identity.get("task_state_sha256")
                ):
                    candidates.append(candidate_id)
            if len(candidates) != 1:
                raise ContractError("successor migration receipt bridge is incomplete")
            migration_id = candidates[0]
            expected_target_build = str(source.get("build_id") or "")
            expected_target_runner_version = str(source.get("runner_version") or "")
            expected_target_core_root = str(source.get("core_root") or "")
            expected_target_manifest_sha256 = str(
                identity.get("product_manifest_sha256") or ""
            )
            expected_target_state_sha256 = str(identity.get("task_state_sha256") or "")

        raise ContractError("successor migration receipt bridge is incomplete")

    def bootstrap(
        self,
        task_id: str,
        *,
        command_id: str,
        expected_revision: int,
        writer_id: str,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        replay = self._committed_replay(
            task_id,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type="runner.bootstrap",
            actor=actor,
            semantic_payload={},
        )
        if replay is not None:
            return replay
        task = self._task_for_mutation(task_id, expected_revision)
        inventory_receipt = None
        if task["migration_status"] == "not_applicable" and task["material_grants"]:
            inventory_receipt = self._inventory_artifact(
                task, revision=expected_revision + 1, command_id=command_id
            )
        envelope = self._command(
            task,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type="runner.bootstrap",
            payload={},
            actor=actor,
        )
        result = self._submit(
            task_id, envelope, {"inventory_receipt": inventory_receipt}
        )
        return {"command_result": result, "snapshot": self.snapshot(task_id)}

    def renew_delegated_grant(
        self,
        task_id: str,
        *,
        command_id: str,
        expected_revision: int,
        writer_id: str,
        actor: dict[str, Any],
    ) -> dict[str, Any]:
        """Reopen J3 so a user can issue a fresh, time-bounded local grant.

        This operation never creates a grant and never edits the persisted one.
        It only invalidates downstream academic pointers and exposes a typed
        configuration issue; the subsequent user-origin J3 answer mints the
        replacement grant through the existing path.
        """
        replay = self._committed_replay(
            task_id,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type="runner.delegated-grant.renew",
            actor=actor,
            semantic_payload={"action": "reopen_configuration"},
        )
        if replay is not None:
            return replay
        task = self._task_for_mutation(task_id, expected_revision)
        # The renewal revision must carry a fresh, revision-bound ledger receipt.
        # Reusing the old pointer would make the subsequent J3 answer fail
        # `_read_inventory_receipt`, which deliberately rejects stale ledger
        # revisions.  Rescan the same grants, then refuse the renewal if the
        # immutable material snapshot changed while the grant was expired.
        revision = expected_revision + 1
        inventory_receipt = self._inventory_artifact(
            task, revision=revision, command_id=command_id
        )
        inventory = self._read_inventory_receipt(task, inventory_receipt, revision)
        prior_snapshot = (
            task.get("state", {}).get("runner", {}).get("material_inventory") or {}
        ).get("snapshot_sha256")
        if prior_snapshot != inventory["snapshot_sha256"]:
            self._cleanup_prepared(task_id, {"inventory_receipt": inventory_receipt})
            raise ContractError(
                "material inventory changed; refresh materials before renewing the grant"
            )
        envelope = self._command(
            task,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type="runner.delegated-grant.renew",
            payload={"action": "reopen_configuration"},
            actor=actor,
        )
        result = self._submit(
            task_id, envelope, {"inventory_receipt": inventory_receipt}
        )
        return {"command_result": result, "snapshot": self.snapshot(task_id)}

    def task_inputs(self, task_id: str) -> dict[str, Any]:
        """Read the actual Runner ledger and run-contract, including stale inputs."""
        task = self.kernel.get_task(task_id)
        state = task["state"].get("runner", {})
        result: dict[str, Any] = {"material_grants": task["material_grants"]}
        for key in ("material_inventory", "run_contract"):
            pointer = state.get(key)
            result[key] = pointer
            result[key + "_payload"] = self._load_run_json(task, pointer["path"]) if pointer else None
        return result

    def update_inputs(self, task_id: str, *, materials_roots: list[str] | None = None,
                      configuration: dict[str, Any] | None = None, command_id: str,
                      expected_revision: int, writer_id: str) -> dict[str, Any]:
        """Update inputs through existing receipts without discarding academic work.

        This entry cannot issue or extend delegated interaction authority.
        """
        payload = {"materials_roots": materials_roots, "configuration": configuration}
        replay = self._committed_replay(task_id, command_id=command_id,
            expected_revision=expected_revision, writer_id=writer_id,
            command_type="runner.inputs.update", semantic_payload=payload, actor=None)
        if replay is not None:
            return replay
        task = self._task_for_mutation(task_id, expected_revision)
        grants = list(task["material_grants"])
        known = {str(_validate_grant_root(item)) for item in grants}
        for raw in materials_roots or []:
            grant = _build_material_grant(raw, len(grants) + 1, _now())
            if grant["canonical_target"] not in known:
                grants.append(grant)
                known.add(grant["canonical_target"])
        input_task = {**task, "material_grants": grants}
        revision = expected_revision + 1
        receipt = self._inventory_artifact(input_task, revision=revision, command_id=command_id)
        inventory = self._read_inventory_receipt(input_task, receipt, revision)
        prepared = {"inventory_receipt": receipt, "material_grants": grants}
        if configuration is not None:
            previous_snapshot = (task["state"].get("runner", {}).get("material_inventory") or {}).get("snapshot_sha256")
            if previous_snapshot != inventory["snapshot_sha256"]:
                self._cleanup_prepared(task_id, {"inventory_receipt": receipt})
                raise ContractError("材料已变化，请先刷新材料清单后再保存配置。")
            configuration = validate_run_configuration(configuration)
            prior = self.task_inputs(task_id)["run_contract_payload"]
            old_interaction = (prior or {}).get("configuration", {}).get("interaction", {"mode": "guided", "grant": None})
            if configuration.get("interaction", {"mode": "guided", "grant": None}) != old_interaction:
                raise ContractError("Task settings cannot issue or change interaction authority")
            validate_configuration_material_semantics(configuration, inventory)
            prepared["run_contract_receipt"] = self._run_contract_artifact(input_task,
                configuration=configuration, inventory=inventory, revision=revision, command_id=command_id)
        envelope = self._command(task, command_id=command_id, expected_revision=expected_revision,
            writer_id=writer_id, command_type="runner.inputs.update", payload=payload, actor=None)
        result = self._submit(task_id, envelope, prepared)
        return {"command_result": result, "snapshot": self.snapshot(task_id)}

    def _handle_update_inputs(self, task: dict[str, Any], command: dict[str, Any],
                              prepared: dict[str, Any]) -> dict[str, Any]:
        revision = command["expected_revision"] + 1
        input_task = {**task, "material_grants": prepared["material_grants"]}
        receipt = prepared["inventory_receipt"]
        inventory = self._read_inventory_receipt(input_task, receipt, revision)
        previous = task["state"].get("runner", {})
        runner = dict(previous) if previous else self._state(stage="awaiting_configuration",
            issues=[], material_inventory=None, run_contract=None, next_actions=[])
        runner["material_inventory"] = self._pointer(receipt, inventory["snapshot_sha256"])
        artifacts = [receipt]
        contract = prepared.get("run_contract_receipt")
        if contract:
            value = self._read_run_contract_receipt(input_task, contract, revision,
                inventory=inventory, configuration=command["payload"]["configuration"])
            runner["run_contract"] = self._pointer(contract, inventory["snapshot_sha256"])
            runner["interaction"] = self._interaction_projection(value["configuration"])
            artifacts.append(contract)
        early = previous.get("stage") in (None, "awaiting_materials", "awaiting_configuration", "configured")
        if early:
            runner["stage"] = "configured" if contract else "awaiting_configuration"
            runner["issues"] = [] if contract else [self._issue(task, revision=revision,
                code="configuration.required", stage="J3",
                details="Confirm task configuration for the current materials.",
                allowed_actions=["runner.issue.answer"])]
            runner["next_actions"] = ["runner.resume"] if contract else ["runner.issue.answer"]
        else:
            runner["inputs_changed"] = True
            runner["next_actions"] = ["runner.resume"]
        state = {**task["state"], "runner": runner}
        return {"state": state, "status": task["status"],
                "material_grants": prepared["material_grants"], "artifacts": artifacts,
                "event_payload": {"runner_stage": runner["stage"]},
                "result": {"run_contract_artifact_id": contract["artifact_id"] if contract else None}}

    def add_materials(
        self,
        task_id: str,
        materials_roots: list[str | Path] | tuple[str | Path, ...],
        *,
        command_id: str,
        expected_revision: int,
        writer_id: str,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        roots = [
            str(Path(item) if Path(item).is_absolute() else Path(item).absolute())
            for item in materials_roots
        ]
        replay = self._committed_replay(
            task_id,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type="runner.materials.add",
            actor=actor,
            semantic_payload={"materials_roots": roots},
        )
        if replay is not None:
            return replay
        task = self._task_for_mutation(task_id, expected_revision)
        envelope = self._command(
            task,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type="runner.materials.add",
            payload={"materials_roots": roots},
            actor=actor,
        )
        result = self._submit(task_id, envelope, {})
        return {"command_result": result, "snapshot": self.snapshot(task_id)}

    def _reference_preview_bytes(
        self,
        task: dict[str, Any],
        entry: dict[str, Any],
        *,
        expected_sha256: str,
        expected_media_type: str,
    ) -> bytes:
        """Reopen one current material-ledger object and verify exact image bytes."""

        if (
            entry.get("sha256") != expected_sha256
            or isinstance(entry.get("size_bytes"), bool)
            or not isinstance(entry.get("size_bytes"), int)
            or entry["size_bytes"] <= 0
            or entry["size_bytes"] > _FIGURE_CANDIDATE_MAX_BYTES
        ):
            raise ContractError(
                "reference preview does not match the current material ledger"
            )
        run_root = Path(task["run_root"]).resolve()
        relative = PurePosixPath(str(entry.get("object_path") or ""))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[:3] != ("runner", "materials", "objects")
        ):
            raise ContractError("reference preview object identity is invalid")
        unresolved = run_root.joinpath(*relative.parts)
        cursor = run_root
        for part in relative.parts:
            cursor = cursor / part
            if cursor.exists() and _is_link_or_reparse(cursor):
                raise ContractError(
                    "reference preview traverses a link or reparse point"
                )
        try:
            resolved = unresolved.resolve(strict=True)
            resolved.relative_to(run_root)
            if not resolved.is_file() or _is_link_or_reparse(resolved):
                raise OSError
            content = resolved.read_bytes()
            resolved_after_read = unresolved.resolve(strict=True)
            resolved_after_read.relative_to(run_root)
        except (OSError, ValueError):
            raise ContractError(
                "reference preview object is missing or outside the active run"
            ) from None
        if (
            resolved_after_read != resolved
            or len(content) != entry["size_bytes"]
            or not secrets.compare_digest(_sha256_bytes(content), expected_sha256)
        ):
            raise ContractError("reference preview bytes are stale or tampered")
        if _verified_reference_preview_media_type(expected_media_type, content) is None:
            raise ContractError(
                "reference preview bytes do not match the declared PNG, JPEG or SVG type"
            )
        return content

    def _figure_reference_workspace_context(
        self, task_id: str, *, actor: dict[str, Any] | None
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        """Build a current, authority-checked user projection and byte index."""

        task = self.kernel.get_task(task_id)
        revision = task.get("revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ContractError("reference workspace task revision is invalid")
        raw_runner_state = (
            task.get("state", {}).get("runner")
            if isinstance(task.get("state"), dict)
            else None
        )
        if not isinstance(raw_runner_state, dict):
            return (
                {
                    "task_id": task_id,
                    "revision": revision,
                    "plans": [],
                    "external_action_authorized": False,
                },
                {},
            )
        runner_state = self._runner_state(task)
        base_artifacts = self._read_academic_base_artifacts(
            task, runner_state.get("academic_base_artifacts")
        )
        plan_items = [
            (artifact_id, payload)
            for artifact_id, payload in sorted(base_artifacts.items())
            if payload.get("contract") == "paperspine5.figure-reference-plan"
        ]
        if not plan_items:
            return (
                {
                    "task_id": task_id,
                    "revision": revision,
                    "plans": [],
                    "external_action_authorized": False,
                },
                {},
            )
        inventory_pointer = runner_state.get("material_inventory")
        if not isinstance(inventory_pointer, dict):
            return (
                {
                    "task_id": task_id,
                    "revision": revision,
                    "plans": [],
                    "external_action_authorized": False,
                },
                {},
            )
        current_views = self.kernel.list_artifacts(task_id, subject_revision=revision)
        inventory_views = [
            view
            for view in current_views
            if view.get("freshness") == "fresh"
            and isinstance(view.get("receipt"), dict)
            and view["receipt"].get("artifact_id") == "materials.source-ledger"
            and view["receipt"].get("sha256") == inventory_pointer.get("sha256")
        ]
        if len(inventory_views) != 1:
            raise ContractError(
                "reference workspace requires one current material ledger"
            )
        inventory_receipt = inventory_views[0]["receipt"]
        inventory_bridge = self._successor_receipt_bridge(
            task,
            inventory_receipt,
            artifact_type="materials.source-ledger",
        )
        inventory = self._read_inventory_receipt(
            task,
            inventory_receipt,
            revision,
            build_id=(inventory_bridge or {}).get("source_build_id"),
            runner_version=(inventory_bridge or {}).get("source_runner_version"),
        )
        trusted_master_receipt = self._trusted_figure_master_receipt(
            task=task,
            actor=_safe_actor(actor, "product-web-reference-projection"),
            current_stage=runner_state["stage"],
            persisted_base_artifacts=base_artifacts,
            effective_base_artifacts=base_artifacts,
            require_actor_binding=False,
        )
        if trusted_master_receipt is None:
            raise ContractError(
                "reference workspace has no trusted Figure Master receipt"
            )

        registered_hashes: dict[str, str] = {}
        for view in current_views:
            receipt = view.get("receipt")
            if view.get("freshness") != "fresh" or not isinstance(receipt, dict):
                continue
            artifact_id = receipt.get("artifact_id")
            sha256 = receipt.get("sha256")
            if isinstance(artifact_id, str) and isinstance(sha256, str):
                previous = registered_hashes.get(artifact_id)
                if previous is not None and previous != sha256:
                    raise ContractError(
                        "reference workspace artifact registry contains conflicting hashes"
                    )
                registered_hashes[artifact_id] = sha256
        entries_by_id: dict[str, dict[str, Any]] = {}
        for entry in inventory["entries"]:
            source_id = entry["source_id"]
            for identifier in (source_id, f"source:{source_id}"):
                registered_hashes[identifier] = entry["sha256"]
                entries_by_id[identifier] = entry

        public_plans: list[dict[str, Any]] = []
        preview_index: dict[str, dict[str, Any]] = {}
        for artifact_id, raw_plan in plan_items:
            subject = raw_plan.get("subject")
            plan_revision = (
                subject.get("runner_revision") if isinstance(subject, dict) else None
            )
            if (
                isinstance(plan_revision, bool)
                or not str(plan_revision or "").isdigit()
            ):
                raise ContractError("reference plan subject revision is invalid")
            plan_revision_number = int(str(plan_revision))
            if plan_revision_number > revision:
                raise ContractError(
                    "reference plan subject revision is from the future"
                )
            try:
                validated_plan = validate_figure_reference_plan(
                    raw_plan,
                    expected_subject={
                        "task_id": task_id,
                        "revision_id": plan_revision_number,
                        "material_snapshot_sha256": inventory["snapshot_sha256"],
                    },
                    registered_artifacts=registered_hashes,
                    trusted_actor_receipt=trusted_master_receipt,
                )
                projection = project_figure_plan_for_user(
                    validated_plan,
                    trusted_actor_receipt=trusted_master_receipt,
                )
            except FigureReferenceMappingError as exc:
                raise ContractError(
                    f"current reference plan is invalid: {exc}"
                ) from exc
            projection["figure"].pop("producer_id", None)
            for projected_reference, reference in zip(
                projection["references"],
                validated_plan["reference_assets"],
                strict=True,
            ):
                preview_artifact_id = reference["preview_artifact_id"]
                entry = entries_by_id.get(preview_artifact_id)
                if entry is None:
                    # A public style-only freeze may be persisted as a
                    # research/base artifact without being copied into the
                    # user's private material ledger.  Keep the reference
                    # plan visible and explicitly omit the preview URL rather
                    # than treating the missing preview as a paper blocker or
                    # fabricating bytes.  The plan hash, source locator and
                    # prohibited-transfer rules remain fully validated above.
                    if (
                        reference.get("access_basis") == "public"
                        and reference.get("publication_use") == "visual_grammar_only"
                    ):
                        projected_reference["source_locator"] = (
                            _public_reference_source_locator(reference["source_locator"])
                        )
                        projected_reference.pop("preview_artifact_id", None)
                        continue
                    raise ContractError(
                        "reference preview is not declared by the current material ledger"
                    )
                content = self._reference_preview_bytes(
                    task,
                    entry,
                    expected_sha256=reference["preview_sha256"],
                    expected_media_type=reference["preview_media_type"],
                )
                descriptor_payload = {
                    "task_id": task_id,
                    "revision": revision,
                    "material_snapshot_sha256": inventory["snapshot_sha256"],
                    "plan_artifact_id": artifact_id,
                    "plan_sha256": validated_plan["plan_sha256"],
                    "reference_id": reference["reference_id"],
                    "preview_artifact_id": preview_artifact_id,
                    "preview_sha256": reference["preview_sha256"],
                    "preview_media_type": reference["preview_media_type"],
                }
                descriptor_id = _sha256_bytes(_json_bytes(descriptor_payload))
                preview_index[descriptor_id] = {
                    "content": content,
                    "sha256": reference["preview_sha256"],
                    "size_bytes": len(content),
                    "media_type": reference["preview_media_type"],
                }
                projected_reference["source_locator"] = (
                    _public_reference_source_locator(reference["source_locator"])
                )
                projected_reference.pop("preview_artifact_id", None)
                projected_reference["preview_descriptor_id"] = descriptor_id
            public_plans.append(
                {
                    "artifact_id": artifact_id,
                    "sha256": validated_plan["plan_sha256"],
                    "revision_id": str(revision),
                    "plan": projection,
                }
            )
        return (
            {
                "task_id": task_id,
                "revision": revision,
                "plans": public_plans,
                "external_action_authorized": False,
            },
            preview_index,
        )

    def project_figure_reference_workspace(
        self, task_id: str, *, actor: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Return only safe, current reference-plan projections for Product Web."""

        workspace, _previews = self._figure_reference_workspace_context(
            task_id, actor=actor
        )
        from .figure_final_mapping import collect_final_mappings, safe_projection

        task = self.kernel.get_task(task_id)
        try:
            items = collect_final_mappings(self, task, actor=actor)
        except ContractError:
            # Keep valid plans/reference descriptors visible, but never reuse a
            # stale build/background/selection validation as a user-facing PASS.
            workspace["final_mapping_status"] = "revalidation_required"
            workspace["final_mappings"] = []
            return workspace
        if items:
            state = self._runner_state(task)
            base = self._read_academic_base_artifacts(task, state.get("academic_base_artifacts"))
            authority = self._trusted_figure_master_receipt(actor=actor or {}, current_stage=state["stage"],
                persisted_base_artifacts=base, effective_base_artifacts=base, task=task)
            by_plan = {v["artifact_id"]: v["plan"] for v in workspace["plans"]}
            workspace["final_mappings"] = [
                {"artifact_id": v["receipt"]["artifact_id"], "sha256": v["envelope"]["mapping"]["mapping_sha256"],
                 "revision_id": str(task["revision"]), "mapping": safe_projection(v,
                    by_plan[v["envelope"]["mapping"]["plan_binding"]["artifact_id"]], authority)}
                for v in items
            ]
        return workspace

    def register_final_mapping(self, task_id: str, registration: dict[str, Any], *,
                               command_id: str, expected_revision: int, writer_id: str,
                               actor: dict[str, Any] | None = None) -> dict[str, Any]:
        """Register a frozen final map through the exact current J7 binary bridge."""
        from .figure_final_mapping import register_final_mapping
        return register_final_mapping(self, task_id, registration, command_id=command_id,
            expected_revision=expected_revision, writer_id=writer_id, actor=actor)

    def read_figure_reference_preview(
        self,
        task_id: str,
        descriptor_id: str,
        *,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Return bytes only for an exact descriptor in the current verified workspace."""

        if (
            not isinstance(descriptor_id, str)
            or re.fullmatch(r"[0-9a-f]{64}", descriptor_id) is None
        ):
            return None
        _workspace, previews = self._figure_reference_workspace_context(
            task_id, actor=actor
        )
        preview = previews.get(descriptor_id)
        return deepcopy(preview) if preview is not None else None

    def register_figure_candidate(
        self,
        task_id: str,
        registration: dict[str, Any],
        *,
        command_id: str,
        expected_revision: int,
        writer_id: str,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register one staged J7 image through a Runner-owned immutable receipt.

        The caller may assert only identity, a Runner-designated staging-relative
        path, hash and size.  ProductRunner derives the CAS destination, public
        academic input manifest, artifact identity, authority and metadata.  The
        academic revision/stage is intentionally unchanged; a successful J7 CAS
        republishes the exact bytes under the resulting revision.
        """

        normalized = _validated_figure_candidate_registration(registration)
        if not isinstance(command_id, str) or not command_id:
            raise ContractError("figure candidate command_id is required")
        if not isinstance(writer_id, str) or not writer_id:
            raise ContractError("figure candidate writer_id is required")
        if actor is not None and not isinstance(actor, dict):
            raise ContractError("figure candidate actor must be an object")
        task = self._task_for_mutation(task_id, expected_revision)
        runner_state = self._runner_state(task)
        if runner_state.get("stage") != "awaiting_figure_intent":
            raise ContractError(
                "figure candidates may be registered only for the current J7 stage"
            )

        inventory_pointer = runner_state.get("material_inventory")
        inventory_views = [
            view
            for view in self.kernel.list_artifacts(
                task_id, subject_revision=expected_revision
            )
            if view.get("freshness") == "fresh"
            and isinstance(view.get("receipt"), dict)
            and view["receipt"].get("artifact_id") == "materials.source-ledger"
            and isinstance(inventory_pointer, dict)
            and view["receipt"].get("sha256") == inventory_pointer.get("sha256")
        ]
        if len(inventory_views) != 1:
            raise ContractError(
                "figure candidate registration requires one fresh material ledger"
            )
        inventory_receipt = inventory_views[0]["receipt"]
        inventory_bridge = self._successor_receipt_bridge(
            task,
            inventory_receipt,
            artifact_type="materials.source-ledger",
        )
        inventory = self._read_inventory_receipt(
            task,
            inventory_receipt,
            expected_revision,
            build_id=(inventory_bridge or {}).get("source_build_id"),
            runner_version=(inventory_bridge or {}).get("source_runner_version"),
        )

        reference_plan_binding = normalized["reference_plan"]
        from .paper_revision import retained_pointer
        retained_plan = retained_pointer(task, "academic_base_artifacts", reference_plan_binding["artifact_id"])
        base_artifacts = self._read_academic_base_artifacts(
            task, runner_state.get("academic_base_artifacts")
        )
        if str(reference_plan_binding["revision_id"]) != str(expected_revision) and not retained_plan:
            # A same-task J4/J5/J6 rerun can advance the runner revision while
            # preserving an immutable reference plan from the earlier J7
            # freeze.  Accept only that exact persisted plan, with the same
            # task/material subject and hash; arbitrary stale caller plans
            # remain rejected.
            persisted_plan = base_artifacts.get(reference_plan_binding["artifact_id"])
            if not (
                isinstance(persisted_plan, dict)
                and persisted_plan.get("contract") == "paperspine5.figure-reference-plan"
                and persisted_plan.get("plan_sha256") == reference_plan_binding["sha256"]
                and isinstance(persisted_plan.get("subject"), dict)
                and persisted_plan["subject"].get("task_id") == task_id
                and persisted_plan["subject"].get("material_snapshot_sha256")
                == runner_state.get("material_inventory", {}).get("snapshot_sha256")
                and str(persisted_plan["subject"].get("runner_revision"))
                == str(reference_plan_binding["revision_id"])
            ):
                raise ContractError(
                    "figure candidate reference_plan is not bound to the current revision"
                )
        reference_plan = base_artifacts.get(reference_plan_binding["artifact_id"])
        if not isinstance(reference_plan, dict):
            # A task that previously chose ``zero`` has no frozen J7 plan yet.
            # Allow the host to freeze the plan together with the first
            # candidate registration; the subsequent academic answer persists
            # the exact same object as a base artifact.  This keeps the order
            # honest (plan -> asset -> user choice) without requiring a second
            # task or a manual file edit.
            reference_plan = normalized.get("reference_plan_payload")
            if not isinstance(reference_plan, dict):
                raise ContractError(
                    "figure candidate registration requires the current frozen reference plan"
                )
            base_artifacts[reference_plan_binding["artifact_id"]] = deepcopy(reference_plan)
        trusted_master_receipt = self._trusted_figure_master_receipt(
            actor=_safe_actor(actor, writer_id),
            task=task,
            current_stage="awaiting_figure_intent",
            persisted_base_artifacts=base_artifacts,
            effective_base_artifacts=base_artifacts,
        )
        registered_hashes: dict[str, str] = {}
        for view in self.kernel.list_artifacts(
            task_id, subject_revision=expected_revision
        ):
            receipt = view.get("receipt")
            if view.get("freshness") != "fresh" or not isinstance(receipt, dict):
                continue
            artifact_id = receipt.get("artifact_id")
            sha256 = receipt.get("sha256")
            if isinstance(artifact_id, str) and isinstance(sha256, str):
                previous = registered_hashes.get(artifact_id)
                if previous is not None and previous != sha256:
                    raise ContractError(
                        "current artifact registry contains conflicting hashes"
                    )
                registered_hashes[artifact_id] = sha256
        for entry in inventory.get("entries", []):
            if not isinstance(entry, dict):
                continue
            source_id = entry.get("source_id")
            source_sha256 = entry.get("sha256")
            if isinstance(source_id, str) and isinstance(source_sha256, str):
                registered_hashes[source_id] = source_sha256
                registered_hashes[f"source:{source_id}"] = source_sha256
        # Academic public sources are immutable base inputs rather than
        # material-ledger entries.  Keep their canonical payload hashes in the
        # reference-plan registry so a lawful frozen paper/style source can be
        # used as visual grammar during a same-task J7 re-entry.
        for artifact_id, artifact_payload in base_artifacts.items():
            if not isinstance(artifact_id, str) or not isinstance(artifact_payload, dict):
                continue
            if artifact_payload.get("contract") == "paperspine5.public-source-freeze":
                registered_hashes.setdefault(artifact_id, _sha256_bytes(_json_bytes(artifact_payload)))
        try:
            validated_reference_plan = validate_figure_reference_plan(
                reference_plan,
                expected_subject={
                    "task_id": task_id,
                    "revision_id": reference_plan_binding["revision_id"],
                    "material_snapshot_sha256": inventory["snapshot_sha256"],
                },
                registered_artifacts=registered_hashes,
                trusted_actor_receipt=trusted_master_receipt,
            )
        except FigureReferenceMappingError as exc:
            raise ContractError(
                f"figure candidate reference_plan is invalid: {exc}"
            ) from exc
        if (
            reference_plan_binding["sha256"] != validated_reference_plan["plan_sha256"]
            or validated_reference_plan["figure"]["figure_id"]
            != normalized["figure_id"]
        ):
            raise ContractError(
                "figure candidate reference_plan does not bind this figure and frozen plan"
            )

        run_root = Path(task["run_root"]).resolve()
        staged_relative = PurePosixPath(normalized["staged_relative_path"])
        staged_path = run_root.joinpath(*staged_relative.parts)
        self._validate_candidate_file_path(
            run_root,
            staged_path,
            required_root=run_root.joinpath(*_FIGURE_CANDIDATE_STAGING_ROOT.parts),
        )
        content = staged_path.read_bytes()
        if (
            len(content) != normalized["size_bytes"]
            or _sha256_bytes(content) != normalized["sha256"]
        ):
            raise ContractError(
                "figure candidate staged bytes do not match the asserted hash and size"
            )
        media_type = _verified_figure_candidate_media_type(staged_path, content)
        if media_type is None:
            raise ContractError(
                "figure candidate is not a valid allow-listed PNG, JPEG or SVG"
            )

        identity_sha256 = _sha256_bytes(
            (normalized["figure_id"] + "\x00" + normalized["candidate_id"]).encode(
                "utf-8"
            )
        )
        artifact_id = f"figure-candidate.{identity_sha256[:32]}"
        suffix = staged_path.suffix.lower()
        relative = Path("runner") / "figures" / f"{normalized['sha256']}{suffix}"
        request_binding = {
            "contract": "paperspine5.figure-candidate-registration-binding",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "task_id": task_id,
            "revision_id": str(expected_revision),
            "product_build_id": self.expected_build_id,
            "command_id": command_id,
            "registration": normalized,
            "external_action_authorized": False,
        }
        registration_request_sha256 = canonical_input_sha256(request_binding)
        input_artifact = self._figure_candidate_input_manifest(
            task=task,
            revision=expected_revision,
            artifact_id=artifact_id,
            figure_id=normalized["figure_id"],
            candidate_id=normalized["candidate_id"],
            relative=relative,
            media_type=media_type,
            sha256=normalized["sha256"],
            size_bytes=normalized["size_bytes"],
            reference_plan=reference_plan_binding,
            material_snapshot_sha256=inventory["snapshot_sha256"],
            registration_command_id=command_id,
            registration_request_sha256=registration_request_sha256,
        )
        input_artifact_sha256 = canonical_input_sha256(input_artifact)
        receipt = {
            "contract": "paperspine5.artifact-receipt",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "receipt_id": task_scoped_artifact_receipt_id(
                task_id=task_id,
                revision_id=expected_revision,
                artifact_id=artifact_id,
                artifact_type="figure.candidate-staged",
                content_sha256=normalized["sha256"],
            ),
            "artifact_id": artifact_id,
            "artifact_type": "figure.candidate-staged",
            "path": relative.as_posix(),
            "sha256": normalized["sha256"],
            "size_bytes": normalized["size_bytes"],
            "subject": {
                "task_id": task_id,
                "revision_id": str(expected_revision),
                "input_hashes": {
                    "materials.source-ledger": inventory_receipt["sha256"],
                    "registration.request": registration_request_sha256,
                    reference_plan_binding["artifact_id"]: reference_plan_binding[
                        "sha256"
                    ],
                },
            },
            "authority": {
                "kind": "paper-spine-figure-authority",
                "producer_id": f"paperspine5.product-runner.{RUNNER_VERSION}",
            },
            "metadata": {
                "academic_stage": "awaiting_figure_intent",
                "figure_id": normalized["figure_id"],
                "candidate_id": normalized["candidate_id"],
                "asset_role": "candidate",
                "media_type": media_type,
                "material_snapshot_sha256": inventory["snapshot_sha256"],
                "registration_command_id": command_id,
                "registration_request_sha256": registration_request_sha256,
                "input_artifact_sha256": input_artifact_sha256,
                "reference_plan_artifact_id": reference_plan_binding["artifact_id"],
                "reference_plan_sha256": reference_plan_binding["sha256"],
                "product_build_id": self.expected_build_id,
                "runner_version": RUNNER_VERSION,
                "filesystem_commit_policy": (
                    "ledger-recognizes-db-committed-receipt-only"
                ),
            },
            "external_action_authorized": False,
        }
        validate_artifact_receipt(receipt, task_id=task_id, revision=expected_revision)

        destination = run_root / relative
        destination_preexisted = destination.exists()
        internal_stage_root = (
            run_root
            / "runner"
            / ".staging"
            / hashlib.sha256(command_id.encode("utf-8")).hexdigest()
        )
        try:
            self._publish_bytes(task, relative, content, command_id=command_id)
            command_result = self.kernel.record_artifact(
                task_id,
                receipt,
                expected_revision=expected_revision,
                command_id=command_id,
                writer_id=writer_id,
            )
        except BaseException:
            if (
                not destination_preexisted
                and destination.is_file()
                and destination.stat().st_size == len(content)
                and self._file_digest(destination) == normalized["sha256"]
            ):
                destination.unlink()
            shutil.rmtree(internal_stage_root, ignore_errors=True)
            raise
        shutil.rmtree(internal_stage_root, ignore_errors=True)
        return {
            "contract": "paperspine5.figure-candidate-registration-result",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "task_id": task_id,
            "revision": expected_revision,
            "stage": "awaiting_figure_intent",
            "product_build_id": self.expected_build_id,
            "registration_applied": True,
            "command_result": command_result,
            "artifact_receipt": command_result["receipt"],
            "input_artifact": input_artifact,
            "candidate_asset": {
                "artifact_id": artifact_id,
                "sha256": input_artifact_sha256,
                "revision_id": str(expected_revision),
            },
            "academic_revision_advanced": False,
            "external_action_authorized": False,
        }

    @staticmethod
    def _validate_candidate_file_path(
        run_root: Path, candidate: Path, *, required_root: Path
    ) -> Path:
        """Reject path escapes and every link/reparse hop before reading bytes."""

        run_root = run_root.resolve()
        required_root = required_root.resolve()
        unresolved = candidate
        try:
            unresolved.relative_to(run_root)
        except ValueError as exc:
            raise ContractError(
                "figure candidate path escapes the active run root"
            ) from exc
        relative = unresolved.relative_to(run_root)
        cursor = run_root
        for part in relative.parts:
            cursor = cursor / part
            if cursor.exists() and _is_link_or_reparse(cursor):
                raise ContractError(
                    "figure candidate path contains a link or reparse point"
                )
        resolved = unresolved.resolve()
        if (
            not _is_relative_to(resolved, required_root)
            or not resolved.is_file()
            or _is_link_or_reparse(resolved)
        ):
            raise ContractError(
                "figure candidate must be a regular file in the Runner staging subtree"
            )
        return resolved

    def _figure_candidate_input_manifest(
        self,
        *,
        task: dict[str, Any],
        revision: int,
        artifact_id: str,
        figure_id: str,
        candidate_id: str,
        relative: Path,
        media_type: str,
        sha256: str,
        size_bytes: int,
        reference_plan: dict[str, Any],
        material_snapshot_sha256: str,
        registration_command_id: str,
        registration_request_sha256: str,
    ) -> dict[str, Any]:
        return {
            "contract": "paperspine5.figure-candidate-asset",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "task_id": task["task_id"],
            "revision_id": str(revision),
            "product_build_id": self.expected_build_id,
            "figure_id": figure_id,
            "candidate_id": candidate_id,
            "artifact_id": artifact_id,
            "path": relative.as_posix(),
            "media_type": media_type,
            "sha256": sha256,
            "size_bytes": size_bytes,
            "reference_plan": deepcopy(reference_plan),
            "material_snapshot_sha256": material_snapshot_sha256,
            "registration_command_id": registration_command_id,
            "registration_request_sha256": registration_request_sha256,
            "external_action_authorized": False,
        }

    def answer_issue(
        self,
        task_id: str,
        issue_id: str,
        resume_token: str,
        answer: dict[str, Any],
        *,
        command_id: str,
        expected_revision: int,
        writer_id: str,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(answer, dict):
            raise ContractError("answer must be an object")
        academic_candidate = (
            answer.get("contract") == "paperspine5.academic-stage-answer"
        )
        if academic_candidate:
            normalized_answer = self._validated_academic_answer(
                answer,
                task_id=task_id,
                revision=expected_revision,
                issue_id=issue_id,
                stage=answer.get("stage"),
            )
        else:
            normalized_answer = validate_run_configuration(answer)
            validate_delegation_user_authority(
                normalized_answer, _safe_actor(actor, writer_id)
            )
        replay = self._committed_replay(
            task_id,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type=("runner.issue.answer", "runner.bootstrap"),
            actor=actor,
            semantic_payload={
                "issue_id": issue_id,
                "resume_token": resume_token,
                "answer": normalized_answer,
            },
        )
        if replay is not None:
            applied = (
                replay["command_result"]
                .get("output", {})
                .get("run_contract_artifact_id")
                is not None
                or replay["command_result"].get("output", {}).get("academic_stage")
                is not None
            )
            return {**replay, "answer_applied": applied}
        task = self._task_for_mutation(task_id, expected_revision)
        runner_state = self._runner_state(task)
        issue = self._find_open_issue(runner_state, issue_id)
        self._verify_resume_token(task, issue, resume_token)
        if issue["code"] == "configuration.required" and academic_candidate:
            raise ContractError(
                "configuration issue requires a typed run configuration"
            )
        if issue["code"] == "academic.input.required":
            if not academic_candidate:
                raise ContractError("academic issue requires an academic-stage-answer")
            normalized_answer = self._validated_academic_answer(
                normalized_answer,
                task_id=task_id,
                revision=expected_revision,
                issue_id=issue_id,
                stage=runner_state["stage"],
            )
            academic_payload = normalized_answer.get("payload", {})
            if academic_payload.get(
                "contract"
            ) == "paperspine5.academic-stage-answer" or (
                "payload" in academic_payload and "issue_id" in academic_payload
            ):
                raise ContractError(
                    "academic issue accepts the stage payload object, not a nested "
                    "paperspine5.academic-stage-answer envelope"
                )
            if (
                runner_state["stage"] == "awaiting_contribution"
                and academic_payload.get("contract")
                != "paperspine5.contribution-candidate-preparation"
            ):
                raise ContractError(
                    "J5 phase 1 accepts contribution candidates only; user decisions, "
                    "author_identity, and confirmed_at require Product Web confirmation"
                )
            self._preflight_delegated_academic_answer(
                task, runner_state, normalized_answer
            )
        elif issue["code"] != "configuration.required":
            raise ContractError("this runner issue does not accept an answer")
        inventory_receipt = self._inventory_artifact(
            task, revision=expected_revision + 1, command_id=command_id
        )
        inventory = self._read_inventory_receipt(
            task, inventory_receipt, expected_revision + 1
        )
        current_snapshot = runner_state.get("material_inventory", {}).get(
            "snapshot_sha256"
        )
        if inventory["snapshot_sha256"] != current_snapshot:
            envelope = self._command(
                task,
                command_id=command_id,
                expected_revision=expected_revision,
                writer_id=writer_id,
                command_type="runner.bootstrap",
                payload={
                    "issue_id": issue_id,
                    "resume_token": resume_token,
                    "answer": normalized_answer,
                },
                actor=actor,
            )
            result = self._submit(
                task_id, envelope, {"inventory_receipt": inventory_receipt}
            )
            return {
                "command_result": result,
                "snapshot": self.snapshot(task_id),
                "answer_applied": False,
                "reason": "materials_changed",
            }
        if issue["code"] == "configuration.required":
            validate_configuration_material_semantics(normalized_answer, inventory)
            run_contract_receipt = self._run_contract_artifact(
                task,
                configuration=normalized_answer,
                inventory=inventory,
                revision=expected_revision + 1,
                command_id=command_id,
            )
        else:
            run_contract_receipt = self._carry_run_contract_artifact(
                task,
                runner_state,
                inventory,
                revision=expected_revision + 1,
                command_id=command_id,
            )
        figure_evidence = (
            self._prepare_figure_quality_evidence(
                task,
                runner_state,
                normalized_answer,
                inventory,
                command_id=command_id,
            )
            if issue["code"] == "academic.input.required"
            else None
        )
        effective_figure_answer = (
            figure_evidence["answer"]
            if isinstance(figure_evidence, dict)
            else normalized_answer
        )
        registered_candidate_evidence = (
            self._prepare_registered_figure_candidate_evidence(
                task,
                runner_state,
                effective_figure_answer,
                inventory,
                prepared_binary_outputs=(
                    figure_evidence.get("binary_outputs", [])
                    if isinstance(figure_evidence, dict)
                    else []
                ),
            )
            if issue["code"] == "academic.input.required"
            else None
        )
        envelope = self._command(
            task,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type="runner.issue.answer",
            payload={
                "issue_id": issue_id,
                "resume_token": resume_token,
                "answer": normalized_answer,
            },
            actor=actor,
        )
        result = self._submit(
            task_id,
            envelope,
            {
                "inventory_receipt": inventory_receipt,
                "run_contract_receipt": run_contract_receipt,
                "figure_evidence": figure_evidence,
                "registered_candidate_evidence": registered_candidate_evidence,
            },
        )
        return {
            "command_result": result,
            "snapshot": self.snapshot(task_id),
            "answer_applied": True,
        }

    def confirm_contribution(
        self,
        task_id: str,
        issue_id: str,
        resume_token: str,
        confirmation: dict[str, Any],
        *,
        author_identity: dict[str, Any],
        command_id: str,
        expected_revision: int,
        writer_id: str,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Commit J5 phase 2 from the authenticated Product Web boundary only."""

        # J5 phase 2 is the one user-only decision in the academic route.  The
        # Agent/MCP facade may prepare candidates, but it must never be able to
        # turn its own answer into an author confirmation.  Enforce the
        # boundary here as well as in the Web adapter so alternate callers
        # cannot bypass the Product Web trust boundary by invoking Runner
        # directly.
        trusted_actor = _safe_actor(actor, writer_id)
        if (
            trusted_actor.get("surface") != "web"
            or trusted_actor.get("authority_kind")
            != "authenticated_local_user_session"
        ):
            raise ContractError(
                "contribution confirmation requires an authenticated Product Web session"
            )

        if not isinstance(confirmation, dict):
            raise ContractError("contribution confirmation must be an object")
        preliminary = validate_contribution_confirmation(
            confirmation,
            task_id=task_id,
            revision=expected_revision,
            issue_id=issue_id,
        )
        if preliminary:
            raise ContractError(
                "contribution confirmation is invalid: "
                + "; ".join(
                    f"{item.get('code')}: {item.get('message')}" for item in preliminary
                )
            )
        try:
            normalized_confirmation = json.loads(_canonical_json(confirmation))
        except (TypeError, ValueError) as exc:
            raise ContractError(
                "contribution confirmation must be canonical JSON"
            ) from exc
        replay = self._committed_replay(
            task_id,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type=("runner.issue.answer", "runner.bootstrap"),
            actor=actor,
            semantic_payload={
                "issue_id": issue_id,
                "resume_token": resume_token,
                "confirmation": normalized_confirmation,
                "author_identity": author_identity,
            },
        )
        if replay is not None:
            return {**replay, "answer_applied": True}
        task = self._task_for_mutation(task_id, expected_revision)
        runner_state = self._runner_state(task)
        issue = self._find_open_issue(runner_state, issue_id)
        self._verify_resume_token(task, issue, resume_token)
        if (
            issue.get("code") != "contribution.confirmation.required"
            or runner_state.get("stage") != "awaiting_contribution"
        ):
            raise ContractError(
                "contribution confirmation requires the current Product Web J5 issue"
            )
        preparation = issue.get("candidate_preparation")
        preparation_sha256 = (
            preparation.get("preparation_sha256")
            if isinstance(preparation, dict)
            else None
        )
        findings = validate_contribution_confirmation(
            normalized_confirmation,
            task_id=task_id,
            revision=expected_revision,
            issue_id=issue_id,
            preparation_sha256=(
                preparation_sha256 if isinstance(preparation_sha256, str) else ""
            ),
        )
        if findings:
            raise ContractError(
                "contribution confirmation is invalid: "
                + "; ".join(
                    f"{item.get('code')}: {item.get('message')}" for item in findings
                )
            )
        from .quality_readiness import identity_provenance_sha256

        identity_fields = {
            "principal_id",
            "session_id",
            "run_id",
            "independence_group",
            "provenance_sha256",
            "attestation_input_id",
        }
        if (
            not isinstance(author_identity, dict)
            or set(author_identity) != identity_fields
            or not all(
                isinstance(author_identity.get(field), str)
                and bool(author_identity[field].strip())
                for field in identity_fields
            )
            or author_identity.get("provenance_sha256")
            != identity_provenance_sha256(author_identity)
        ):
            raise ContractError(
                "Product Web confirmation identity is incomplete or has invalid provenance"
            )
        inventory_receipt = self._inventory_artifact(
            task, revision=expected_revision + 1, command_id=command_id
        )
        inventory = self._read_inventory_receipt(
            task, inventory_receipt, expected_revision + 1
        )
        current_snapshot = runner_state.get("material_inventory", {}).get(
            "snapshot_sha256"
        )
        if inventory["snapshot_sha256"] != current_snapshot:
            raise ContractError(
                "materials changed; refresh the academic task before confirming"
            )
        run_contract_receipt = self._carry_run_contract_artifact(
            task,
            runner_state,
            inventory,
            revision=expected_revision + 1,
            command_id=command_id,
        )
        envelope = self._command(
            task,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type="runner.issue.answer",
            payload={
                "issue_id": issue_id,
                "resume_token": resume_token,
                "confirmation": normalized_confirmation,
                "author_identity": json.loads(_canonical_json(author_identity)),
            },
            actor=actor,
        )
        result = self._submit(
            task_id,
            envelope,
            {
                "inventory_receipt": inventory_receipt,
                "run_contract_receipt": run_contract_receipt,
                "figure_evidence": None,
            },
        )
        return {
            "command_result": result,
            "snapshot": self.snapshot(task_id),
            "answer_applied": True,
        }

    def request_revision(
        self, task_id: str, *, feedback: str, scope: str, command_id: str,
        expected_revision: int, writer_id: str, actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from .paper_revision import validate_request

        feedback, scope = validate_request(feedback, scope)
        payload = {"feedback": feedback, "scope": scope}
        replay = self._committed_replay(
            task_id, command_id=command_id, expected_revision=expected_revision,
            writer_id=writer_id, command_type="runner.revision.request", actor=actor,
            semantic_payload=payload,
        )
        if replay is not None:
            return replay
        task = self._task_for_mutation(task_id, expected_revision)
        runner = self._runner_state(task)
        readiness = self.kernel.get_readiness(task_id)
        # A figures-scoped request may also recover a same-task downstream
        # run that is already blocked after J7.  This is deliberately narrow:
        # the task must carry the persisted user request that points to an
        # earlier completed delivery, the material snapshot must remain
        # unchanged, and the current stage must still be downstream of J7.
        existing_request = task.get("state", {}).get("user_revision_request")
        recovery_scope = (
            scope == "figures"
            and task.get("status") != "completed"
            and runner.get("stage") in {"awaiting_canonical", "awaiting_review", "awaiting_package"}
            and isinstance(existing_request, dict)
            and existing_request.get("origin") == "user_feedback"
            and isinstance(existing_request.get("previous_completed_revision"), int)
            and isinstance(existing_request.get("previous_delivery"), dict)
        )
        normal_package = (
            task["status"] == "completed" and runner["stage"] == "target_package_ready"
            and readiness.get("status") == "fresh" and readiness.get("delivery_ready") is True
        )
        if not (normal_package or recovery_scope):
            raise ContractError("revision request requires the current completed local package or a valid same-task downstream recovery")
        inventory_receipt = self._inventory_artifact(task, revision=expected_revision + 1, command_id=command_id)
        inventory = self._read_inventory_receipt(task, inventory_receipt, expected_revision + 1)
        if inventory["snapshot_sha256"] != runner["material_inventory"]["snapshot_sha256"]:
            raise ContractError("materials changed; bootstrap before changing the paper")
        contract_receipt = self._carry_run_contract_artifact(
            task, runner, inventory, revision=expected_revision + 1, command_id=command_id,
        )
        envelope = self._command(task, command_id=command_id, expected_revision=expected_revision,
            writer_id=writer_id, command_type="runner.revision.request", payload=payload, actor=actor)
        result = self._submit(task_id, envelope, {"inventory_receipt": inventory_receipt,
                                                "run_contract_receipt": contract_receipt})
        return {"command_result": result, "snapshot": self.snapshot(task_id), "revision_requested": True}

    def _handle_revision_request(self, task: dict[str, Any], command: dict[str, Any],
                                 prepared: dict[str, Any]) -> dict[str, Any]:
        from .paper_revision import apply_revision_request
        return apply_revision_request(self, task, command, prepared)

    def resume(
        self,
        task_id: str,
        *,
        command_id: str,
        expected_revision: int,
        writer_id: str,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        successor_replay = self._committed_successor_replay(
            task_id,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            actor=actor,
        )
        if successor_replay is not None:
            return successor_replay
        replay = self._committed_replay(
            task_id,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type="runner.resume",
            actor=actor,
            semantic_payload={},
        )
        if replay is not None:
            return replay
        initial_task = self.kernel.get_task(task_id)
        if initial_task["revision"] != expected_revision:
            from .product_kernel import RevisionConflictError

            raise RevisionConflictError(
                f"expected_revision {expected_revision} does not match current revision "
                f"{initial_task['revision']}"
            )
        compatibility_issue = self._compatibility_issue(initial_task)
        if (
            compatibility_issue
            and compatibility_issue["code"] == "runner.build_incompatible"
        ):
            prepared = self._prepare_successor_migration(
                initial_task, command_id=command_id
            )
            envelope = self._command(
                initial_task,
                command_id=command_id,
                expected_revision=expected_revision,
                writer_id=writer_id,
                command_type="runner.successor.resume",
                payload=prepared["command_payload"],
                actor=actor,
            )
            result = self._submit(task_id, envelope, prepared)
            return {
                "command_result": result,
                "snapshot": self.snapshot(task_id),
                "blocked": True,
                "reason": "successor_rebound_user_or_agent_input_required",
                "same_task_resumed": True,
            }
        task = self._task_for_mutation(task_id, expected_revision)
        runner_state = task["state"].get("runner")
        open_issue_subjects_current = bool(runner_state) and all(
            str(item.get("subject", {}).get("revision_id")) == str(task["revision"])
            for item in runner_state.get("issues", [])
            if item.get("status") == "open"
        )
        if runner_state and (
            (
                runner_state.get("stage", "").startswith("awaiting_")
                and open_issue_subjects_current
            )
            or runner_state.get("stage") == "target_package_ready"
        ):
            return {
                "command_result": None,
                "snapshot": self.snapshot(task_id),
                "blocked": True,
                "reason": (
                    "target_package_ready"
                    if runner_state.get("stage") == "target_package_ready"
                    else "user_or_agent_input_required"
                ),
            }
        inventory_receipt = None
        run_contract_receipt = None
        if task["migration_status"] == "not_applicable" and task["material_grants"]:
            inventory_receipt = self._inventory_artifact(
                task, revision=expected_revision + 1, command_id=command_id
            )
            inventory = self._read_inventory_receipt(
                task, inventory_receipt, expected_revision + 1
            )
            if runner_state and runner_state.get("run_contract"):
                run_contract_receipt = self._carry_run_contract_artifact(
                    task,
                    runner_state,
                    inventory,
                    revision=expected_revision + 1,
                    command_id=command_id,
                )
        envelope = self._command(
            task,
            command_id=command_id,
            expected_revision=expected_revision,
            writer_id=writer_id,
            command_type="runner.resume",
            payload={},
            actor=actor,
        )
        result = self._submit(
            task_id,
            envelope,
            {
                "inventory_receipt": inventory_receipt,
                "run_contract_receipt": run_contract_receipt,
            },
        )
        return {"command_result": result, "snapshot": self.snapshot(task_id)}

    def _preflight_delegated_academic_answer(
        self,
        task: dict[str, Any],
        runner_state: dict[str, Any],
        answer: dict[str, Any],
    ) -> None:
        pointer = runner_state.get("run_contract")
        if not isinstance(pointer, dict) or not isinstance(pointer.get("path"), str):
            return
        run_contract = self._load_run_json(task, pointer["path"])
        configuration = validate_run_configuration(run_contract.get("configuration"))
        interaction = configuration.get("interaction")
        if (
            not isinstance(interaction, dict)
            or interaction.get("mode") != "delegated_local_test"
        ):
            return
        grant = interaction.get("grant")
        if not isinstance(grant, dict):
            raise ContractError("delegated local run contract is missing its grant")
        granted = set(grant.get("decision_classes", []))
        stage = runner_state.get("stage")
        payload = answer.get("payload")
        if not isinstance(payload, dict):
            return
        if stage == "awaiting_figure_intent":
            intent = payload.get("intent")
            if isinstance(intent, dict):
                mode = intent.get("mode")
                required = (
                    "figure_supplement"
                    if mode == "create"
                    else "figure_keep_or_transform"
                )
                if required not in granted:
                    raise ContractError(
                        f"delegated figure action requires an explicit {required} grant"
                    )
                encoded = _canonical_json(intent).lower()
                if (
                    "omitted" in encoded or '"omit"' in encoded
                ) and "figure_omit" not in granted:
                    raise ContractError(
                        "delegated figure omission requires an explicit figure_omit grant"
                    )
                material_pointer = runner_state.get("material_inventory")
                if not isinstance(material_pointer, dict) or not isinstance(
                    material_pointer.get("path"), str
                ):
                    raise ContractError(
                        "delegated figure decisions require the current material ledger"
                    )
                material_build_id = self.expected_build_id
                persisted_contract_build_id = run_contract.get("product_build_id")
                if persisted_contract_build_id != self.expected_build_id:
                    successor = runner_state.get("successor_migration")
                    if (
                        not isinstance(persisted_contract_build_id, str)
                        or not persisted_contract_build_id
                    ):
                        raise ContractError(
                            "delegated figure preflight has no valid successor build binding"
                        )
                    if (
                        not isinstance(successor, dict)
                        or successor.get("target_build_id") != self.expected_build_id
                    ):
                        raise ContractError(
                            "delegated figure preflight has no valid successor build binding"
                        )
                    if successor.get("source_build_id") != persisted_contract_build_id:
                        raise ContractError(
                            "delegated figure preflight has no valid successor build binding"
                        )
                    material_build_id = persisted_contract_build_id
                inventory = validate_material_source_ledger(
                    self._load_run_json(task, material_pointer["path"]),
                    task_id=task["task_id"],
                    revision=task["revision"],
                    build_id=material_build_id,
                )
                prior_profile = self._read_academic_base_artifacts(
                    task, runner_state.get("academic_base_artifacts")
                ).get("materials.figure-set")
                prior_requests = [
                    item["request"]
                    for item in (prior_profile or {}).get("semantic_resolutions", [])
                    if isinstance(item, dict) and isinstance(item.get("request"), dict)
                ]
                figure_set = self._material_figure_set(
                    task,
                    inventory,
                    semantic_resolution_requests=prior_requests,
                )
                if figure_set["status"] == "BLOCKED":
                    raise ContractError(
                        "material figure set is blocked: "
                        + "; ".join(item["message"] for item in figure_set["blockers"])
                    )
                expected = {
                    item["artifact_id"]: item["sha256"]
                    for item in figure_set["figure_sources"]
                }
                if expected and mode == "zero":
                    raise ContractError(
                        "delegated zero-figure mode contradicts active manuscript figures"
                    )
                if expected and mode not in {"keep", "redesign", "mixed"}:
                    raise ContractError(
                        "active manuscript figures require an explicit keep or redesign decision"
                    )
                if expected:
                    figures = intent.get("figures")
                    actual: dict[str, str] = {}
                    if isinstance(figures, list):
                        for figure in figures:
                            if not isinstance(figure, dict):
                                continue
                            asset = figure.get("current_asset")
                            if not isinstance(asset, dict):
                                continue
                            artifact_id = str(asset.get("artifact_id") or "")
                            sha256 = str(asset.get("sha256") or "")
                            if artifact_id in actual:
                                raise ContractError(
                                    "delegated figure set contains a duplicate current asset"
                                )
                            actual[artifact_id] = sha256
                    if actual != expected:
                        raise ContractError(
                            "delegated figure decision does not cover the exact active manuscript figure set"
                        )
        if stage == "awaiting_package":
            requested_scope = payload.get("requested_scope")
            if requested_scope == "submission_package" or requested_scope != grant.get(
                "requested_scope"
            ):
                raise ContractError(
                    "delegated local grant cannot authorize submission scope or scope drift"
                )
            if payload.get("author_close"):
                raise ContractError(
                    "author facts require a separate current human confirmation"
                )
            encoded = _canonical_json(payload).lower()
            if any(token in encoded for token in ('"license"', '"licence"', '"fee"')):
                raise ContractError(
                    "license, licence, and fee decisions remain human submission gates"
                )

    def _prepare_figure_quality_evidence(
        self,
        task: dict[str, Any],
        runner_state: dict[str, Any],
        answer: dict[str, Any],
        inventory: dict[str, Any],
        *,
        command_id: str,
    ) -> dict[str, Any] | None:
        """Execute and measure J7 assets before the CAS transition.

        The host supplies a scoped correction specification and a typed independent
        review result. PaperSpine derives the immutable source/path/hash binding,
        signs the operation, invokes only the FigMirror executor, and measures the
        selected target-size asset. Any failure is raised before Kernel submission,
        so the task revision and readiness projections remain unchanged.
        """

        if runner_state.get("stage") != "awaiting_figure_intent":
            return None
        payload = answer.get("payload")
        intent = payload.get("intent") if isinstance(payload, dict) else None
        figures = intent.get("figures") if isinstance(intent, dict) else None
        if not isinstance(figures, list):
            return None
        quality_enabled = any(
            isinstance(item, dict)
            and (
                item.get("correction_request") is not None
                or item.get("target_size_profile") is not None
            )
            for item in figures
        )
        if not quality_enabled:
            return None
        correction_enabled = any(
            isinstance(item, dict) and item.get("correction_request") is not None
            for item in figures
        )
        if correction_enabled and self.figure_correction_executor is None:
            raise ContractError(
                "FIGURE_CORRECTION_EXECUTOR_UNAVAILABLE: active J7 quality evidence "
                "requires the bundled FigMirror executor"
            )
        if correction_enabled and self.figure_correction_reviewer is None:
            raise ContractError(
                "FIGURE_CORRECTION_REVIEWER_UNAVAILABLE: corrected J7 evidence "
                "requires a host-owned independent multimodal reviewer"
            )

        prior_profile = self._read_academic_base_artifacts(
            task, runner_state.get("academic_base_artifacts")
        ).get("materials.figure-set")
        prior_requests = [
            item["request"]
            for item in (prior_profile or {}).get("semantic_resolutions", [])
            if isinstance(item, dict) and isinstance(item.get("request"), dict)
        ]
        figure_set = self._material_figure_set(
            task,
            inventory,
            semantic_resolution_requests=prior_requests,
        )
        if figure_set.get("status") != "PASS":
            raise ContractError(
                "FIGURE_QUALITY_MATERIAL_SET_BLOCKED: the current manuscript figure set is not PASS"
            )
        expected_assets = {
            str(item["artifact_id"]): item
            for item in figure_set.get("figure_sources", [])
            if isinstance(item, dict)
        }
        ledger_by_artifact = {
            f"source:{item['source_id']}": item
            for item in inventory.get("entries", [])
            if isinstance(item, dict) and isinstance(item.get("source_id"), str)
        }
        run_root = Path(task["run_root"]).resolve()
        stage_root = (
            run_root
            / "runner"
            / ".staging"
            / hashlib.sha256(command_id.encode("utf-8")).hexdigest()
            / "figure-quality"
        )
        stage_root.mkdir(parents=True, exist_ok=True)
        normalized_answer = deepcopy(answer)
        normalized_figures = normalized_answer["payload"]["intent"]["figures"]
        base_artifacts: dict[str, dict[str, Any]] = {}
        binary_outputs: list[dict[str, Any]] = []
        corrected_paths: dict[str, Path] = {}

        def safe_token(value: str) -> str:
            token = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
            if not token:
                raise ContractError("figure_id cannot form a safe evidence artifact id")
            return token[:80]

        try:
            for index, figure in enumerate(normalized_figures):
                if not isinstance(figure, dict):
                    raise ContractError(f"intent.figures[{index}] must be an object")
                figure_id = str(figure.get("figure_id") or "")
                token = safe_token(figure_id)
                current = figure.get("current_asset")
                if not isinstance(current, dict):
                    raise ContractError(
                        f"FIGURE_QUALITY_SOURCE_MISSING: {figure_id} needs a current asset"
                    )
                current_id = str(current.get("artifact_id") or "")
                current_sha = str(current.get("sha256") or "")
                expected = expected_assets.get(current_id)
                if (
                    expected is None
                    or expected.get("sha256") != current_sha
                    or current_id not in ledger_by_artifact
                ):
                    raise ContractError(
                        f"FIGURE_QUALITY_SOURCE_STALE: {figure_id} is not the current ledger-bound manuscript asset"
                    )

                selected_asset = current
                selected_path = run_root / str(
                    ledger_by_artifact[current_id]["object_path"]
                )
                comparison = figure.get("independent_comparison")
                if isinstance(comparison, dict):
                    selected_sha = str(comparison.get("selected_sha256") or "")
                    if selected_sha and selected_sha != current_sha:
                        selected_candidates = [
                            item
                            for item in figure.get("candidate_assets", [])
                            if isinstance(item, dict)
                            and item.get("sha256") == selected_sha
                        ]
                        if len(selected_candidates) != 1:
                            raise ContractError(
                                f"FIGURE_QUALITY_SELECTED_ASSET_STALE: {figure_id} "
                                "independent comparison must resolve one candidate"
                            )
                        selected_asset = selected_candidates[0]
                        selected_id = str(selected_asset.get("artifact_id") or "")
                        selected_entry = ledger_by_artifact.get(selected_id)
                        if selected_entry is None:
                            raise ContractError(
                                f"FIGURE_QUALITY_SELECTED_ASSET_UNBOUND: {figure_id} "
                                "candidate is not bound to the material ledger"
                            )
                        selected_path = run_root / str(selected_entry["object_path"])
                profile = figure.pop("target_size_profile", None)
                if not isinstance(profile, dict):
                    raise ContractError(
                        f"TARGET_SIZE_PROFILE_MISSING: {figure_id} requires a typed physical-size profile"
                    )
                if profile.get("figure_id") != figure_id:
                    raise ContractError(
                        f"TARGET_SIZE_PROFILE_STALE: {figure_id} profile belongs to another figure"
                    )
                legibility: dict[str, Any] | None = None
                correction = figure.pop("correction_request", None)
                if correction is not None:
                    if not isinstance(correction, dict):
                        raise ContractError(
                            f"FIGURE_CORRECTION_REQUEST_INVALID: {figure_id} request must be an object"
                        )
                    allowed = {
                        "contract",
                        "contract_version",
                        "operation_kind",
                        "operation_id",
                        "allowed_text_changes",
                        "pixel_diff_bounds",
                        "scientific_invariants",
                        "external_action_authorized",
                    }
                    if set(correction) != allowed:
                        raise ContractError(
                            f"FIGURE_CORRECTION_REQUEST_INVALID: {figure_id} contains unknown or missing fields"
                        )
                    if (
                        correction.get("contract")
                        != "paperspine5.figure-correction-request"
                        or correction.get("contract_version") != "1.0"
                        or correction.get("external_action_authorized") is not False
                    ):
                        raise ContractError(
                            f"FIGURE_CORRECTION_REQUEST_INVALID: {figure_id} contract or authority boundary is invalid"
                        )
                    source_bytes = selected_path.read_bytes()
                    operation_kind = correction.get("operation_kind")
                    if source_bytes.startswith(b"%PDF"):
                        expected_kind = "pdf_overlay_composition"
                        source_media_type = "application/pdf"
                        output_suffix = ".pdf"
                    elif source_bytes.lstrip().startswith(b"<"):
                        expected_kind = "svg_text_correction"
                        source_media_type = "image/svg+xml"
                        output_suffix = ".svg"
                    else:
                        raise ContractError(
                            f"FIGURE_CORRECTION_MEDIA_UNSUPPORTED: {figure_id} "
                            "requires a real PDF or SVG source"
                        )
                    if operation_kind != expected_kind:
                        raise ContractError(
                            f"FIGURE_CORRECTION_MEDIA_MISMATCH: {figure_id} "
                            f"{source_media_type} cannot be declared as {operation_kind}"
                        )

                    allowed_changes = deepcopy(correction["allowed_text_changes"])
                    scientific_invariants = deepcopy(
                        correction["scientific_invariants"]
                    )
                    overlay: dict[str, Any] | None = None
                    overlay_staged_path: Path | None = None
                    if operation_kind == "pdf_overlay_composition":
                        if set(scientific_invariants) != {
                            "panel_ids",
                            "render_invariant_regions",
                        }:
                            raise ContractError(
                                f"FIGURE_CORRECTION_INVARIANTS_INVALID: {figure_id} "
                                "PDF correction requires only typed render invariant regions"
                            )
                        raw_invariants = scientific_invariants[
                            "render_invariant_regions"
                        ]
                        if not isinstance(raw_invariants, list):
                            raise ContractError(
                                f"FIGURE_CORRECTION_INVARIANTS_INVALID: {figure_id} "
                                "render invariant regions must be a list"
                            )
                        render_width = correction["pixel_diff_bounds"].get(
                            "render_width_px"
                        )
                        bound_invariants: list[dict[str, Any]] = []
                        for invariant in raw_invariants:
                            if not isinstance(invariant, dict) or not set(
                                invariant
                            ).issubset(
                                {
                                    "invariant_id",
                                    "kind",
                                    "region",
                                    "source_pixels_sha256",
                                }
                            ):
                                raise ContractError(
                                    f"FIGURE_CORRECTION_INVARIANTS_INVALID: {figure_id} "
                                    "contains an untyped render invariant"
                                )
                            bound = {
                                "invariant_id": invariant.get("invariant_id"),
                                "kind": invariant.get("kind"),
                                "region": deepcopy(invariant.get("region")),
                            }
                            try:
                                measured = pdf_render_region_sha256(
                                    selected_path,
                                    bound["region"],
                                    render_width_px=int(render_width),
                                )
                            except (
                                TypeError,
                                ValueError,
                                FigureCorrectionError,
                            ) as exc:
                                raise ContractError(
                                    f"FIGURE_CORRECTION_INVARIANTS_INVALID: {figure_id} "
                                    f"cannot bind a source render region: {exc}"
                                ) from exc
                            supplied = invariant.get("source_pixels_sha256")
                            if supplied is not None and supplied != measured:
                                raise ContractError(
                                    f"FIGURE_CORRECTION_INVARIANTS_STALE: {figure_id} "
                                    "source render hash changed"
                                )
                            bound["source_pixels_sha256"] = measured
                            bound_invariants.append(bound)
                        scientific_invariants["render_invariant_regions"] = (
                            bound_invariants
                        )
                        overlay_staged_path = stage_root / f"{token}-overlay.svg"
                        try:
                            overlay = build_pdf_text_overlay(
                                selected_path,
                                allowed_changes,
                                overlay_staged_path,
                            )
                        except FigureCorrectionError as exc:
                            raise ContractError(
                                f"FIGURE_CORRECTION_OVERLAY_INVALID: {figure_id}: {exc}"
                            ) from exc
                    operation = {
                        "contract": "paperspine5.figure-correction-operation",
                        "contract_version": "1.0",
                        "operation_kind": operation_kind,
                        "operation_id": correction["operation_id"],
                        "figure_id": figure_id,
                        "authority": "paper-spine",
                        "executor": "figmirror",
                        "source": {
                            "path": str(selected_path),
                            "media_type": source_media_type,
                            "sha256": str(selected_asset.get("sha256") or ""),
                        },
                        "overlay": deepcopy(overlay),
                        "allowed_text_changes": allowed_changes,
                        "pixel_diff_bounds": deepcopy(correction["pixel_diff_bounds"]),
                        "scientific_invariants": scientific_invariants,
                        "external_action_authorized": False,
                    }
                    operation["operation_sha256"] = figure_canonical_sha256(operation)
                    staged_output = stage_root / (
                        f"{token}-{operation['operation_sha256']}{output_suffix}"
                    )
                    service = FigureCorrectionService(
                        executor=self.figure_correction_executor
                    )
                    receipt = service.execute(
                        operation,
                        staged_output,
                        target_size_profile=profile,
                        review_bindings={
                            "task_id": task["task_id"],
                            "revision": task["revision"],
                            "material_snapshot_sha256": inventory["snapshot_sha256"],
                        },
                        reviewer=self.figure_correction_reviewer,
                    )
                    legibility = deepcopy(receipt["target_size_legibility"])
                    review = receipt["independent_final_review"]
                    output_sha = receipt["output"]["sha256"]
                    output_artifact_id = f"figure-output.{token}"
                    output_relative = (
                        Path("runner")
                        / "figures"
                        / f"{operation['operation_sha256']}-{output_sha}{output_suffix}"
                    )
                    receipt["source"]["path"] = str(
                        ledger_by_artifact[current_id]["object_path"]
                    )
                    receipt["output"]["path"] = output_relative.as_posix()
                    overlay_artifact_id: str | None = None
                    if overlay is not None and overlay_staged_path is not None:
                        overlay_artifact_id = f"figure-overlay.{token}"
                        overlay_relative = (
                            Path("runner")
                            / "figures"
                            / (
                                f"{operation['operation_sha256']}-"
                                f"{overlay['sha256']}-overlay.svg"
                            )
                        )
                        receipt["overlay"]["path"] = overlay_relative.as_posix()
                    receipt["receipt_sha256"] = figure_canonical_sha256(
                        {
                            key: value
                            for key, value in receipt.items()
                            if key != "receipt_sha256"
                        }
                    )
                    validate_figure_correction_receipt(receipt)
                    correction_artifact_id = f"figure-correction.{token}"
                    base_artifacts[correction_artifact_id] = receipt
                    binary_outputs.append(
                        {
                            "artifact_id": output_artifact_id,
                            "figure_id": figure_id,
                            "candidate_id": output_artifact_id,
                            "asset_role": "candidate",
                            "path": output_relative.as_posix(),
                            "staged_path": str(staged_output),
                            "sha256": output_sha,
                            "size_bytes": staged_output.stat().st_size,
                            "correction_receipt_artifact_id": correction_artifact_id,
                            "artifact_type": "figure.corrected-image",
                        }
                    )
                    if overlay_artifact_id is not None:
                        binary_outputs.append(
                            {
                                "artifact_id": overlay_artifact_id,
                                "figure_id": figure_id,
                                "candidate_id": overlay_artifact_id,
                                "asset_role": "diagnostic",
                                "path": overlay_relative.as_posix(),
                                "staged_path": str(overlay_staged_path),
                                "sha256": overlay["sha256"],
                                "size_bytes": overlay_staged_path.stat().st_size,
                                "correction_receipt_artifact_id": correction_artifact_id,
                                "artifact_type": "figure.correction-overlay",
                            }
                        )
                    corrected_paths[output_artifact_id] = staged_output
                    candidate = {
                        "artifact_id": output_artifact_id,
                        "sha256": output_sha,
                        "revision_id": current.get("revision_id"),
                    }
                    candidates = [
                        item
                        for item in figure.get("candidate_assets", [])
                        if isinstance(item, dict)
                        and item.get("artifact_id") != output_artifact_id
                    ]
                    figure["candidate_assets"] = [*candidates, candidate]
                    figure["independent_comparison"] = {
                        "reviewer_id": review["reviewer_id"],
                        "producer_ids": [
                            "figmirror",
                            str(intent.get("producer_id") or ""),
                        ],
                        "status": "PASS",
                        "reviewed_asset_hashes": sorted({current_sha, output_sha}),
                        "decision": "redesign_wins",
                        "selected_sha256": output_sha,
                    }
                    figure["correction_receipt_artifact_id"] = correction_artifact_id
                    selected_asset = candidate
                    selected_path = staged_output

                if selected_asset.get("artifact_id") in corrected_paths:
                    selected_path = corrected_paths[str(selected_asset["artifact_id"])]
                elif str(selected_asset.get("artifact_id") or "") in ledger_by_artifact:
                    selected_path = run_root / str(
                        ledger_by_artifact[str(selected_asset["artifact_id"])][
                            "object_path"
                        ]
                    )
                if legibility is None:
                    legibility = review_target_size_legibility(selected_path, profile)
                validate_target_size_legibility_receipt(
                    legibility,
                    figure_id=figure_id,
                    figure_sha256=str(selected_asset.get("sha256") or ""),
                    require_pass=True,
                )
                legibility_artifact_id = f"target-size-legibility.{token}"
                base_artifacts[legibility_artifact_id] = legibility
                figure["target_size_legibility_artifact_id"] = legibility_artifact_id

            return {
                "answer": normalized_answer,
                "base_artifacts": base_artifacts,
                "binary_outputs": binary_outputs,
                "published_paths": [],
                "stage_root": str(stage_root),
            }
        except FigureCorrectionError as exc:
            shutil.rmtree(stage_root.parent, ignore_errors=True)
            raise ContractError(f"FIGURE_QUALITY_EVIDENCE_BLOCKED: {exc}") from exc
        except BaseException:
            shutil.rmtree(stage_root.parent, ignore_errors=True)
            raise

    def _prepare_registered_figure_candidate_evidence(
        self,
        task: dict[str, Any],
        runner_state: dict[str, Any],
        answer: dict[str, Any],
        inventory: dict[str, Any],
        *,
        prepared_binary_outputs: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Bind current registered candidate bytes for J7 CAS promotion.

        Registration does not decide a winner.  This preflight only proves that
        any `figure-candidate.*` input was registered by this Runner for the
        current task/build/revision/material snapshot and still has exact image
        bytes.  The later J7 transaction republishes those bytes at its resulting
        revision so Product Web can read a fresh receipt.
        """

        from .paper_revision import retained_pointer
        if runner_state.get("stage") != "awaiting_figure_intent":
            return None
        payload = answer.get("payload")
        intent = payload.get("intent") if isinstance(payload, dict) else None
        figures = intent.get("figures") if isinstance(intent, dict) else None
        inputs = payload.get("input_artifacts") if isinstance(payload, dict) else None
        mode = intent.get("mode") if isinstance(intent, dict) else None
        if not isinstance(figures, list):
            return None
        if not isinstance(inputs, dict):
            if mode == "create" and figures:
                raise ContractError(
                    "J7 create candidates require Runner-registered binary manifests"
                )
            return None
        current_base_artifacts = self._read_academic_base_artifacts(
            task, runner_state.get("academic_base_artifacts")
        )
        answer_inputs = (answer.get("payload") or {}).get("input_artifacts") if isinstance(answer.get("payload"), dict) else None
        if isinstance(answer_inputs, dict):
            for artifact_id, artifact_payload in answer_inputs.items():
                if (
                    isinstance(artifact_id, str)
                    and isinstance(artifact_payload, dict)
                    and artifact_payload.get("contract") == "paperspine5.figure-reference-plan"
                ):
                    current_base_artifacts.setdefault(artifact_id, deepcopy(artifact_payload))
        prepared_by_artifact = {
            str(item.get("artifact_id")): item
            for item in prepared_binary_outputs
            if isinstance(item, dict) and item.get("asset_role") == "candidate"
        }
        current_revision = task["revision"]
        views_by_artifact: dict[str, list[dict[str, Any]]] = {}
        for view in self.kernel.list_artifacts(
            task["task_id"], subject_revision=current_revision
        ):
            receipt = view.get("receipt")
            if (
                view.get("freshness") != "fresh"
                or not isinstance(receipt, dict)
                or receipt.get("artifact_type")
                not in {"figure.candidate-staged", "figure.candidate-image"}
            ):
                continue
            artifact_id = receipt.get("artifact_id")
            if isinstance(artifact_id, str):
                views_by_artifact.setdefault(artifact_id, []).append(receipt)

        run_root = Path(task["run_root"]).resolve()
        outputs: list[dict[str, Any]] = []
        observed: set[str] = set()
        for figure_index, figure in enumerate(figures):
            if not isinstance(figure, dict):
                continue
            figure_id = str(figure.get("figure_id") or "")
            reference_plan = figure.get("reference_plan")
            if not isinstance(reference_plan, dict):
                raise ContractError(
                    f"figures[{figure_index}] lacks its current reference_plan binding"
                )
            candidates = figure.get("candidate_assets")
            if not isinstance(candidates, list):
                continue
            for candidate_index, candidate in enumerate(candidates):
                if not isinstance(candidate, dict):
                    continue
                artifact_id = str(candidate.get("artifact_id") or "")
                prepared_output = prepared_by_artifact.get(artifact_id)
                if prepared_output is not None:
                    if prepared_output.get("figure_id") != figure_id or candidate.get(
                        "sha256"
                    ) != prepared_output.get("sha256"):
                        raise ContractError(
                            "prepared J7 candidate does not match its figure or bytes"
                        )
                    if artifact_id in observed:
                        raise ContractError(
                            "J7 candidate artifact is reused across figure decisions"
                        )
                    observed.add(artifact_id)
                    continue
                receipts = views_by_artifact.get(artifact_id, [])
                if (
                    mode != "create"
                    and not artifact_id.startswith("figure-candidate.")
                    and not receipts
                ):
                    continue
                if len(receipts) != 1:
                    raise ContractError(
                        "J7 create candidate must resolve one fresh Runner-registered "
                        "binary receipt; JSON wrappers and arbitrary paths are not assets: "
                        f"figures[{figure_index}].candidate_assets[{candidate_index}]"
                    )
                if artifact_id in observed:
                    raise ContractError(
                        "registered J7 candidate artifact is reused across figure decisions"
                    )
                observed.add(artifact_id)
                receipt = receipts[0]
                metadata = receipt.get("metadata")
                if not isinstance(metadata, dict):
                    raise ContractError("registered J7 candidate metadata is missing")
                persisted_manifest = current_base_artifacts.get(artifact_id)
                persisted_plan = (
                    persisted_manifest.get("reference_plan")
                    if isinstance(persisted_manifest, dict)
                    else None
                )
                # A same-task restart may freeze a refreshed reference plan at
                # the current J7 revision after candidates were registered. The
                # candidate receipt still carries the immutable plan hash used
                # at registration time; accept that hash when the artifact id
                # and material snapshot are unchanged and the persisted
                # candidate manifest confirms the same plan identity.
                registered_plan_alias = (
                    metadata.get("reference_plan_artifact_id")
                    == reference_plan.get("artifact_id")
                )
                if (
                    metadata.get("figure_id") != figure_id
                    or not isinstance(metadata.get("candidate_id"), str)
                    or metadata.get("asset_role") != "candidate"
                    or not isinstance(metadata.get("product_build_id"), str)
                    or not metadata.get("product_build_id")
                    or not isinstance(metadata.get("runner_version"), str)
                    or not metadata.get("runner_version")
                    or metadata.get("material_snapshot_sha256")
                    != inventory.get("snapshot_sha256")
                    or not isinstance(metadata.get("registration_command_id"), str)
                    or not isinstance(metadata.get("registration_request_sha256"), str)
                    or metadata.get("reference_plan_artifact_id")
                    != reference_plan.get("artifact_id")
                    or (
                        metadata.get("reference_plan_sha256")
                        != reference_plan.get("sha256")
                        and not registered_plan_alias
                    )
                    or (str(reference_plan.get("revision_id")) != str(current_revision)
                        and not retained_pointer(
                            task, "academic_base_artifacts", reference_plan.get("artifact_id"))
                        and not (
                            isinstance(persisted_plan, dict)
                            and persisted_plan == reference_plan
                        )
                        and not (
                            isinstance(current_base_artifacts.get(reference_plan.get("artifact_id")), dict)
                            and current_base_artifacts[reference_plan.get("artifact_id")].get("plan_sha256")
                            == reference_plan.get("sha256")
                        ))
                ):
                    raise ContractError(
                        "registered J7 candidate metadata is stale or belongs to another figure"
                    )
                receipt_path = Path(str(receipt.get("path") or ""))
                if not receipt_path.is_absolute():
                    receipt_path = run_root / receipt_path
                receipt_path = self._validate_candidate_file_path(
                    run_root,
                    receipt_path,
                    required_root=run_root / "runner" / "figures",
                )
                content = receipt_path.read_bytes()
                media_type = _verified_figure_candidate_media_type(
                    receipt_path, content
                )
                if (
                    media_type is None
                    or media_type != metadata.get("media_type")
                    or len(content) != receipt.get("size_bytes")
                    or _sha256_bytes(content) != receipt.get("sha256")
                ):
                    raise ContractError(
                        "registered J7 candidate bytes or media type changed after registration"
                    )
                relative = receipt_path.relative_to(run_root)
                # Both the persisted-manifest and freshly reconstructed
                # branches compare the supplied academic binding below.  Keep
                # the locals defined for the former as well so same-task J7
                # retries remain deterministic.
                supplied_manifest = inputs.get(artifact_id)
                binding_alias_ok = False
                if isinstance(persisted_manifest, dict):
                    persisted_reference = persisted_manifest.get("reference_plan")
                    if (
                        persisted_manifest.get("contract")
                        != "paperspine5.figure-candidate-asset"
                        or persisted_manifest.get("task_id") != task["task_id"]
                        or persisted_manifest.get("artifact_id") != artifact_id
                        or persisted_manifest.get("figure_id") != figure_id
                        or persisted_manifest.get("candidate_id")
                        != metadata["candidate_id"]
                        # The persisted manifest may come from an earlier
                        # same-task J7 revision; the current receipt already
                        # binds the re-registered bytes to this revision.
                        or persisted_manifest.get("product_build_id")
                        != metadata.get("product_build_id")
                        or persisted_manifest.get("path") != relative.as_posix()
                        or persisted_manifest.get("media_type") != media_type
                        or persisted_manifest.get("sha256") != receipt["sha256"]
                        or persisted_manifest.get("size_bytes")
                        != receipt["size_bytes"]
                        or persisted_manifest.get("material_snapshot_sha256")
                        != metadata["material_snapshot_sha256"]
                        # A same-task recovery may re-register the exact
                        # immutable image at a later Runner revision. The
                        # registration command/request metadata then changes
                        # by design; image bytes, identity and frozen plan
                        # remain the authoritative equality checks above.
                        or persisted_manifest.get("external_action_authorized") is not False
                        or not isinstance(persisted_reference, dict)
                        or persisted_reference.get("artifact_id")
                        != reference_plan.get("artifact_id")
                        or (
                            persisted_reference.get("sha256")
                            != reference_plan.get("sha256")
                            and not registered_plan_alias
                        )
                    ):
                        raise ContractError(
                            "persisted J7 candidate manifest differs from its current Runner receipt"
                        )
                    if (
                        artifact_id in inputs
                        and inputs[artifact_id] != persisted_manifest
                    ):
                        raise ContractError(
                            "current J7 candidate cannot be replaced during a semantic retry"
                        )
                    manifest_sha256 = canonical_input_sha256(persisted_manifest)
                else:
                    manifest = self._figure_candidate_input_manifest(
                        task=task,
                        revision=current_revision,
                        artifact_id=artifact_id,
                        figure_id=figure_id,
                        candidate_id=metadata["candidate_id"],
                        relative=relative,
                        media_type=media_type,
                        sha256=receipt["sha256"],
                        size_bytes=receipt["size_bytes"],
                        reference_plan=reference_plan,
                        material_snapshot_sha256=metadata[
                            "material_snapshot_sha256"
                        ],
                        registration_command_id=metadata[
                            "registration_command_id"
                        ],
                        registration_request_sha256=metadata[
                            "registration_request_sha256"
                        ],
                    )
                    manifest_sha256 = canonical_input_sha256(manifest)
                    if isinstance(supplied_manifest, dict):
                        expected_without_plan = dict(manifest)
                        supplied_without_plan = dict(supplied_manifest)
                        expected_without_plan.pop("reference_plan", None)
                        supplied_without_plan.pop("reference_plan", None)
                        binding_alias_ok = expected_without_plan == supplied_without_plan
                    if supplied_manifest != manifest and not binding_alias_ok:
                        raise ContractError(
                            "registered J7 candidate academic binding differs from the Runner manifest"
                        )
                supplied_manifest_sha256 = (
                    canonical_input_sha256(supplied_manifest)
                    if isinstance(supplied_manifest, dict)
                    else None
                )
                if (
                    candidate.get("sha256") != manifest_sha256
                    and not (
                        binding_alias_ok
                        and candidate.get("sha256") == supplied_manifest_sha256
                    )
                ) or (
                    not isinstance(persisted_manifest, dict)
                    and metadata.get("input_artifact_sha256") != manifest_sha256
                    and not (
                        binding_alias_ok
                        and metadata.get("input_artifact_sha256")
                        == supplied_manifest_sha256
                    )
                ):
                    raise ContractError(
                        "registered J7 candidate academic binding differs from the Runner manifest"
                    )
                outputs.append(
                    {
                        "artifact_id": artifact_id,
                        "figure_id": figure_id,
                        "candidate_id": metadata["candidate_id"],
                        "asset_role": "candidate",
                        "path": relative.as_posix(),
                        "source_path": str(receipt_path),
                        "sha256": receipt["sha256"],
                        "size_bytes": receipt["size_bytes"],
                        "artifact_type": "figure.candidate-image",
                        "registration_command_id": metadata["registration_command_id"],
                        "registration_request_sha256": metadata[
                            "registration_request_sha256"
                        ],
                        "input_artifact_sha256": manifest_sha256,
                        "reference_plan_artifact_id": reference_plan["artifact_id"],
                        "reference_plan_sha256": reference_plan["sha256"],
                        "registered_revision": metadata.get(
                            "registered_revision", current_revision
                        ),
                    }
                )
        return {"binary_outputs": outputs} if outputs else None

    def _submit(
        self, task_id: str, envelope: dict[str, Any], prepared: dict[str, Any]
    ) -> dict[str, Any]:
        command_type = envelope["command_type"]
        try:
            return self.kernel._submit_registered_command(
                task_id,
                envelope,
                registration=self._handler_registrations[command_type],
                prepared=prepared,
            )
        except BaseException:
            if self.kernel.get_command(task_id, envelope["command_id"]) is None:
                self._cleanup_prepared(task_id, prepared)
            raise
        finally:
            task = self.kernel.get_task(task_id)
            staging = (
                Path(task["run_root"])
                / "runner"
                / ".staging"
                / hashlib.sha256(envelope["command_id"].encode("utf-8")).hexdigest()
            )
            shutil.rmtree(staging, ignore_errors=True)
            try:
                staging.parent.rmdir()
            except OSError:
                pass

    def _cleanup_prepared(self, task_id: str, prepared: dict[str, Any]) -> None:
        task = self.kernel.get_task(task_id)
        run_root = Path(task["run_root"]).resolve()
        referenced_receipts: set[Path] = set()
        referenced_objects: set[Path] = set()
        for view in self.kernel.list_artifacts(task_id):
            receipt = view["receipt"]
            path = Path(receipt["path"])
            if not path.is_absolute():
                path = run_root / path
            referenced_receipts.add(path.resolve())
            payload = view.get("payload")
            if receipt.get("artifact_type") == "materials.source-ledger" and isinstance(
                payload, dict
            ):
                for entry in payload.get("entries", []):
                    object_path = Path(str(entry.get("object_path", "")))
                    if not object_path.is_absolute():
                        object_path = run_root / object_path
                    referenced_objects.add(object_path.resolve())
        figure_evidence = prepared.get("figure_evidence")
        if isinstance(figure_evidence, dict):
            for raw_path in figure_evidence.get("published_paths", []):
                candidate = Path(str(raw_path)).resolve()
                if (
                    _is_relative_to(candidate, run_root)
                    and candidate not in referenced_receipts
                    and candidate not in referenced_objects
                    and candidate.is_file()
                ):
                    candidate.unlink()
        candidate_objects: set[Path] = set()
        for receipt in prepared.values():
            if not isinstance(receipt, dict):
                continue
            raw_path = receipt.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                continue
            path = Path(raw_path)
            if not path.is_absolute():
                path = run_root / path
            path = path.resolve()
            if (
                path.is_file()
                and receipt.get("artifact_type") == "materials.source-ledger"
            ):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8-sig"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    payload = {}
                for entry in payload.get("entries", []):
                    object_path = Path(str(entry.get("object_path", "")))
                    if not object_path.is_absolute():
                        object_path = run_root / object_path
                    candidate_objects.add(object_path.resolve())
            if path not in referenced_receipts and _is_relative_to(path, run_root):
                path.unlink(missing_ok=True)
        for object_path in candidate_objects - referenced_objects:
            if _is_relative_to(object_path, run_root):
                object_path.unlink(missing_ok=True)

    def reconcile_orphans(self, task_id: str, *, apply: bool = False) -> dict[str, Any]:
        """Report or remove uncommitted runner artifacts/CAS objects; committed bytes are preserved."""
        task = self.kernel.get_task(task_id)
        run_root = Path(task["run_root"]).resolve()
        referenced_receipts: set[Path] = set()
        referenced_objects: set[Path] = set()
        for view in self.kernel.list_artifacts(task_id):
            receipt = view["receipt"]
            path = Path(receipt["path"])
            if not path.is_absolute():
                path = run_root / path
            referenced_receipts.add(path.resolve())
            if receipt.get("artifact_type") == "materials.source-ledger":
                payload = view.get("payload") or {}
                for entry in payload.get("entries", []):
                    object_path = Path(entry["object_path"])
                    if not object_path.is_absolute():
                        object_path = run_root / object_path
                    referenced_objects.add(object_path.resolve())
        artifacts_root = run_root / "runner" / "artifacts"
        objects_root = run_root / "runner" / "materials" / "objects"
        orphan_receipts = (
            sorted(
                path.resolve()
                for path in artifacts_root.rglob("*.json")
                if path.resolve() not in referenced_receipts
            )
            if artifacts_root.exists()
            else []
        )
        orphan_objects = (
            sorted(
                path.resolve()
                for path in objects_root.rglob("*")
                if path.is_file() and path.resolve() not in referenced_objects
            )
            if objects_root.exists()
            else []
        )
        if apply:
            for path in [*orphan_receipts, *orphan_objects]:
                path.unlink(missing_ok=True)
            shutil.rmtree(run_root / "runner" / ".staging", ignore_errors=True)
        return {
            "task_id": task_id,
            "apply": apply,
            "orphan_receipts": [str(path) for path in orphan_receipts],
            "orphan_objects": [str(path) for path in orphan_objects],
            "deleted_count": len(orphan_receipts) + len(orphan_objects) if apply else 0,
        }

    def _command(
        self,
        task: dict[str, Any],
        *,
        command_id: str,
        expected_revision: int,
        writer_id: str,
        command_type: str | tuple[str, ...],
        payload: dict[str, Any],
        actor: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "contract": "paperspine5.command-envelope",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "command_id": command_id,
            "task_id": task["task_id"],
            "expected_revision": expected_revision,
            "writer_id": writer_id,
            "command_type": command_type,
            "payload": payload,
            "actor": _safe_actor(actor, writer_id),
        }

    def _committed_replay(
        self,
        task_id: str,
        *,
        command_id: str,
        expected_revision: int,
        writer_id: str,
        command_type: str,
        actor: dict[str, Any] | None,
        semantic_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        probe_type = command_type if isinstance(command_type, str) else command_type[0]
        validate_command_envelope(
            {
                "contract": "paperspine5.command-envelope",
                "schema_version": PRODUCT_SCHEMA_VERSION,
                "command_id": command_id,
                "task_id": task_id,
                "expected_revision": expected_revision,
                "writer_id": writer_id,
                "command_type": probe_type,
                "payload": semantic_payload,
                "actor": _safe_actor(actor, writer_id),
            },
            task_id=task_id,
        )
        committed = self.kernel.get_command(task_id, command_id)
        if committed is None:
            return None
        envelope = committed["envelope"]
        expected_actor = _safe_actor(actor, writer_id)
        command_types = (
            (command_type,) if isinstance(command_type, str) else command_type
        )
        if (
            envelope.get("command_type") not in command_types
            or envelope.get("expected_revision") != expected_revision
            or envelope.get("actor") != expected_actor
            or any(
                envelope.get("payload", {}).get(key) != value
                for key, value in semantic_payload.items()
            )
        ):
            raise IdempotencyConflictError(
                "command_id was already used with different runner inputs"
            )
        return {
            "command_result": {**committed["result"], "replayed": True},
            "snapshot": self.snapshot(task_id),
        }

    def _committed_successor_replay(
        self,
        task_id: str,
        *,
        command_id: str,
        expected_revision: int,
        writer_id: str,
        actor: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        committed = self.kernel.get_command(task_id, command_id)
        if (
            committed is None
            or committed["envelope"].get("command_type") != "runner.successor.resume"
        ):
            return None
        envelope = committed["envelope"]
        if (
            envelope.get("expected_revision") != expected_revision
            or envelope.get("writer_id") != writer_id
            or envelope.get("actor") != _safe_actor(actor, writer_id)
            or committed["result"].get("previous_revision") != expected_revision
            or committed["result"].get("resulting_revision") != expected_revision
        ):
            raise IdempotencyConflictError(
                "command_id was already used with different successor resume inputs"
            )
        return {
            "command_result": {**committed["result"], "replayed": True},
            "snapshot": self.snapshot(task_id),
            "blocked": True,
            "reason": "successor_rebound_user_or_agent_input_required",
            "same_task_resumed": True,
        }

    def _resolve_successor_authority(
        self,
        task: dict[str, Any],
        source_runner_state: dict[str, Any],
    ) -> dict[str, Any]:
        if self.successor_authority_resolver is None:
            raise ProductRunnerCompatibilityError(
                "same-task successor resume requires exact installed updater evidence"
            )
        request = {
            "contract": "paperspine5.successor-authority-request",
            "schema_version": "1.0",
            "task_id": task["task_id"],
            "active_run_id": task["active_run_id"],
            "revision": task["revision"],
            "source_build_id": task["product_manifest"].get("build_id"),
            "target_build_id": self.expected_build_id,
            "source_runner_version": source_runner_state.get("runner_version"),
            "target_runner_version": RUNNER_VERSION,
            "source_core_root": task["core_root"],
            "target_core_root": str(self.kernel.core_root),
            "material_snapshot_sha256": (
                source_runner_state.get("material_inventory") or {}
            ).get("snapshot_sha256"),
            "external_action_authorized": False,
        }
        authority = self.successor_authority_resolver(deepcopy(request))
        return validate_successor_authority(
            authority,
            source_build_id=request["source_build_id"],
            target_build_id=self.expected_build_id,
            source_runner_version=str(request["source_runner_version"]),
            target_runner_version=RUNNER_VERSION,
            target_core_root=self.kernel.core_root,
        )

    def _preview_successor_migration(self, task: dict[str, Any]) -> dict[str, Any]:
        manifest = task["product_manifest"]
        source_build_id = manifest.get("build_id")
        source_runner_version = manifest.get("component_versions", {}).get(
            "product_runner"
        )
        source_protocol = manifest.get("compatibility", {}).get(
            "product_runner_protocol"
        )
        if (
            not isinstance(source_build_id, str)
            or source_build_id == self.expected_build_id
            or source_runner_version not in READABLE_RUNNER_VERSIONS
            or source_protocol != RUNNER_PROTOCOL_VERSION
        ):
            raise ProductRunnerCompatibilityError(
                "task runner schema/protocol is not eligible for same-task successor resume"
            )
        raw_runner = task["state"].get("runner")
        if not isinstance(raw_runner, dict):
            raise ProductRunnerCompatibilityError(
                "cross-build task has no readable ProductRunner state to resume"
            )
        source_runner = validate_runner_state(
            raw_runner,
            task_id=task["task_id"],
            build_id=source_build_id,
        )
        if source_runner.get("runner_version") != source_runner_version:
            raise ProductRunnerCompatibilityError(
                "task manifest and runner state disagree on the predecessor version"
            )
        authority = self._resolve_successor_authority(task, source_runner)
        issue = self._issue(
            task,
            revision=task["revision"],
            code="runner.successor_migration_required",
            stage="J1",
            details=(
                "A verified installed successor can resume this exact task and material "
                "snapshot. Run runner.resume with the current revision to commit the "
                "auditable build rebind before continuing the open academic gate."
            ),
            allowed_actions=["runner.resume"],
            nonce=authority["authority_sha256"],
        )
        issue["resume_token"] = "resume-successor-" + authority["authority_sha256"][:32]
        return {
            "source_runner_state": source_runner,
            "authority": authority,
            "issue": issue,
        }

    def _ledger_identity(self, task_id: str) -> dict[str, Any]:
        artifacts = []
        for view in self.kernel.list_artifacts(task_id):
            receipt = view["receipt"]
            artifacts.append(
                {
                    "receipt_id": receipt.get("receipt_id"),
                    "artifact_id": receipt.get("artifact_id"),
                    "artifact_type": receipt.get("artifact_type"),
                    "revision_id": receipt.get("subject", {}).get("revision_id"),
                    "sha256": receipt.get("sha256"),
                }
            )
        artifacts.sort(
            key=lambda item: (
                str(item["revision_id"]),
                str(item["artifact_id"]),
                str(item["receipt_id"]),
            )
        )
        commands = []
        for value in self.kernel.list_commands(task_id):
            envelope = value["envelope"]
            result = value["result"]
            commands.append(
                {
                    "command_id": value["command_id"],
                    "command_type": envelope.get("command_type", "task.create"),
                    "expected_revision": envelope.get("expected_revision"),
                    "previous_revision": result.get("previous_revision"),
                    "resulting_revision": result.get("resulting_revision"),
                    "status": result.get("status"),
                }
            )
        commands.sort(key=lambda item: str(item["command_id"]))
        return {
            "artifact_count": len(artifacts),
            "artifact_set_sha256": _sha256_bytes(_json_bytes(artifacts)),
            "command_count": len(commands),
            "command_set_sha256": _sha256_bytes(_json_bytes(commands)),
        }

    def _task_successor_identity(
        self, task: dict[str, Any], source_runner: dict[str, Any]
    ) -> dict[str, Any]:
        ledger = self._ledger_identity(task["task_id"])
        identity = {
            "task_id": task["task_id"],
            "title": task["title"],
            "host": task["host"],
            "status": task["status"],
            "revision": task["revision"],
            "active_run_id": task["active_run_id"],
            "workspace_root": task["workspace_root"],
            "run_root": task["run_root"],
            "material_grants_sha256": _sha256_bytes(
                _json_bytes(task["material_grants"])
            ),
            "product_manifest_sha256": _sha256_bytes(
                _json_bytes(task["product_manifest"])
            ),
            "task_state_sha256": _sha256_bytes(_json_bytes(task["state"])),
            "runner_state_sha256": _sha256_bytes(_json_bytes(source_runner)),
            "material_snapshot_sha256": (
                source_runner.get("material_inventory") or {}
            ).get("snapshot_sha256"),
            "run_contract_sha256": (source_runner.get("run_contract") or {}).get(
                "sha256"
            ),
            "academic_inputs_sha256": (source_runner.get("academic_inputs") or {}).get(
                "sha256"
            ),
            **ledger,
        }
        identity["identity_sha256"] = _sha256_bytes(_json_bytes(identity))
        return identity

    def _prepare_successor_academic_inputs(
        self,
        task: dict[str, Any],
        source_runner: dict[str, Any],
        *,
        source_build_id: str,
        command_id: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        pointer = source_runner.get("academic_inputs")
        if pointer is None:
            return None, None
        cumulative = deepcopy(self._read_academic_inputs(task, pointer))
        if cumulative.get("product_build_id") != source_build_id:
            raise ProductRunnerCompatibilityError(
                "academic cumulative inputs are not bound to the predecessor build"
            )
        contract_pointer = source_runner.get("run_contract")
        if not isinstance(contract_pointer, dict):
            raise ProductRunnerCompatibilityError(
                "academic successor resume requires the exact prior run contract"
            )
        source_contract = self._load_run_json(
            task, str(contract_pointer.get("path") or "")
        )
        persisted_contract_build_id = source_contract.get("product_build_id")
        if (
            not isinstance(persisted_contract_build_id, str)
            or not persisted_contract_build_id
        ):
            raise ProductRunnerCompatibilityError(
                "academic successor resume requires a build-bound prior run contract"
            )
        source_contract = validate_run_contract(
            source_contract,
            task_id=task["task_id"],
            revision=task["revision"],
            build_id=persisted_contract_build_id,
        )
        base_snapshot = cumulative.get("base_snapshot")
        if not isinstance(base_snapshot, dict):
            raise ProductRunnerCompatibilityError(
                "academic cumulative inputs lost their base snapshot"
            )
        previous_contract_hash = base_snapshot.get("runner.run-contract")
        recomputed_source_contract_hash = self._run_contract_authority_sha256(
            source_contract, build_id=source_build_id
        )
        if previous_contract_hash != recomputed_source_contract_hash:
            raise ProductRunnerCompatibilityError(
                "academic cumulative inputs have a stale or forged predecessor run-contract hash"
            )
        if persisted_contract_build_id != source_build_id:
            self._validate_chained_academic_successor_rebind(
                task,
                source_runner,
                pointer,
                cumulative,
                source_contract=source_contract,
                source_build_id=source_build_id,
                effective_contract_hash=recomputed_source_contract_hash,
            )
        cumulative["product_build_id"] = self.expected_build_id
        next_contract_hash = self._run_contract_authority_sha256(
            source_contract, build_id=self.expected_build_id
        )
        scientific_stage_inputs_sha256 = _sha256_bytes(
            _json_bytes(cumulative.get("stage_inputs"))
        )
        base_snapshot["runner.run-contract"] = next_contract_hash
        artifact_id = (
            "runner.academic-inputs.successor."
            + hashlib.sha256(self.expected_build_id.encode("utf-8")).hexdigest()[:16]
        )
        receipt = self._publish_artifact(
            task,
            value={
                "contract": "paperspine5.academic-cumulative-inputs",
                "schema_version": PRODUCT_SCHEMA_VERSION,
                "task_id": task["task_id"],
                "revision_id": str(task["revision"]),
                "stage": source_runner["stage"],
                "inputs": cumulative,
                "external_action_authorized": False,
            },
            revision=task["revision"],
            command_id=command_id,
            artifact_id=artifact_id,
            artifact_type="runner.successor-academic-inputs",
            input_hashes={
                "predecessor-academic-inputs": str(pointer.get("sha256")),
                "predecessor-run-contract-authority": previous_contract_hash,
            },
            metadata={
                "source_product_build_id": source_build_id,
                "migration_role": "runtime-identity-rebind-only",
            },
        )
        return receipt, {
            "source_sha256": pointer.get("sha256"),
            "target_sha256": receipt["sha256"],
            "source_run_contract_authority_sha256": previous_contract_hash,
            "target_run_contract_authority_sha256": next_contract_hash,
            "scientific_stage_inputs_unchanged": True,
            "source_scientific_stage_inputs_sha256": scientific_stage_inputs_sha256,
            "target_scientific_stage_inputs_sha256": scientific_stage_inputs_sha256,
        }

    @staticmethod
    def _run_contract_authority_sha256(
        contract: dict[str, Any], *, build_id: str
    ) -> str:
        return canonical_input_sha256(
            {
                "contract": contract.get("contract"),
                "schema_version": contract.get("schema_version"),
                "product_build_id": build_id,
                "material_snapshot_sha256": contract.get("material_snapshot_sha256"),
                "configuration": contract.get("configuration"),
                "external_action_authorized": contract.get(
                    "external_action_authorized"
                ),
            }
        )

    def _validate_chained_academic_successor_rebind(
        self,
        task: dict[str, Any],
        source_runner: dict[str, Any],
        pointer: dict[str, Any],
        cumulative: dict[str, Any],
        *,
        source_contract: dict[str, Any],
        source_build_id: str,
        effective_contract_hash: str,
    ) -> None:
        """Validate the committed effective authority for a second or later hop.

        Successor migrations intentionally retain the immutable original run-contract
        bytes.  Each hop rebinds only the cumulative runtime authority.  A later hop
        therefore has to prove the current build through the latest committed migration
        receipt and its ledger-backed successor input, rather than requiring historical
        bytes to have been rewritten.
        """

        if pointer.get("artifact_type") != "runner.successor-academic-inputs":
            raise ProductRunnerCompatibilityError(
                "chained successor resume requires committed successor academic inputs"
            )
        link = source_runner.get("successor_migration")
        if not isinstance(link, dict):
            raise ProductRunnerCompatibilityError(
                "chained successor resume requires the prior migration link"
            )
        migration = self.kernel.get_migration_receipt(
            task["task_id"], str(link.get("migration_id") or "")
        )
        if not isinstance(migration, dict):
            raise ProductRunnerCompatibilityError(
                "chained successor resume requires the prior migration receipt"
            )
        unsigned = {
            key: value for key, value in migration.items() if key != "receipt_sha256"
        }
        source = migration.get("source")
        target = migration.get("target")
        identity = source.get("identity") if isinstance(source, dict) else None
        rebind = migration.get("academic_rebind")
        installed_authority = migration.get("installed_suite_authority")
        previous_build_id = source.get("build_id") if isinstance(source, dict) else None
        if (
            migration.get("receipt_sha256") != _sha256_bytes(_json_bytes(unsigned))
            or migration.get("contract")
            != "paperspine5.runner-successor-migration-receipt"
            or migration.get("schema_version") != "1.0"
            or migration.get("task_id") != task["task_id"]
            or migration.get("active_run_id") != task["active_run_id"]
            or migration.get("revision") != task["revision"]
            or migration.get("external_action_authorized") is not False
            or not isinstance(source, dict)
            or not isinstance(target, dict)
            or not isinstance(identity, dict)
            or not isinstance(rebind, dict)
            or not isinstance(installed_authority, dict)
            or not isinstance(previous_build_id, str)
            or not previous_build_id
            or previous_build_id == source_build_id
            or target.get("build_id") != source_build_id
            or target.get("core_root") != task["core_root"]
            or target.get("product_manifest_sha256")
            != _sha256_bytes(_json_bytes(task["product_manifest"]))
            or target.get("task_state_sha256")
            != _sha256_bytes(_json_bytes(task["state"]))
            or link.get("source_build_id") != previous_build_id
            or link.get("target_build_id") != source_build_id
            or link.get("authority_sha256")
            != installed_authority.get("authority_sha256")
            or link.get("source_identity_sha256") != identity.get("identity_sha256")
            or identity.get("task_id") != task["task_id"]
            or identity.get("active_run_id") != task["active_run_id"]
            or identity.get("revision") != task["revision"]
            or identity.get("run_contract_sha256")
            != source_runner.get("run_contract", {}).get("sha256")
            or identity.get("material_snapshot_sha256")
            != source_runner.get("material_inventory", {}).get("snapshot_sha256")
            or identity.get("academic_inputs_sha256") != rebind.get("source_sha256")
            or rebind.get("target_sha256") != pointer.get("sha256")
            or rebind.get("scientific_stage_inputs_unchanged") is not True
        ):
            raise ProductRunnerCompatibilityError(
                "chained successor migration receipt binding is invalid"
            )
        previous_authority_hash = self._run_contract_authority_sha256(
            source_contract, build_id=previous_build_id
        )
        stage_inputs_sha256 = _sha256_bytes(_json_bytes(cumulative.get("stage_inputs")))
        if (
            rebind.get("source_run_contract_authority_sha256")
            != previous_authority_hash
            or rebind.get("target_run_contract_authority_sha256")
            != effective_contract_hash
            or rebind.get("source_scientific_stage_inputs_sha256")
            != stage_inputs_sha256
            or rebind.get("target_scientific_stage_inputs_sha256")
            != stage_inputs_sha256
        ):
            raise ProductRunnerCompatibilityError(
                "chained successor effective run-contract authority is invalid"
            )

        run_root = Path(task["run_root"]).resolve()
        matches: list[dict[str, Any]] = []
        for view in self.kernel.list_artifacts(task["task_id"]):
            receipt = view.get("receipt")
            if (
                view.get("freshness") != "fresh"
                or not isinstance(receipt, dict)
                or receipt.get("artifact_id") != pointer.get("artifact_id")
            ):
                continue
            validated = validate_artifact_receipt(
                receipt, task_id=task["task_id"], revision=task["revision"]
            )
            receipt_path = Path(validated["path"])
            pointer_path = Path(str(pointer.get("path") or ""))
            if not receipt_path.is_absolute():
                receipt_path = run_root / receipt_path
            if not pointer_path.is_absolute():
                pointer_path = run_root / pointer_path
            if (
                validated.get("artifact_type") == "runner.successor-academic-inputs"
                and validated.get("sha256") == pointer.get("sha256")
                and validated.get("size_bytes") == pointer.get("size_bytes")
                and receipt_path.resolve() == pointer_path.resolve()
            ):
                matches.append(validated)
        if len(matches) != 1:
            raise ProductRunnerCompatibilityError(
                "chained successor academic input is not uniquely ledger-backed"
            )
        academic_receipt = matches[0]
        input_hashes = academic_receipt["subject"]["input_hashes"]
        metadata = academic_receipt["metadata"]
        if (
            metadata.get("product_build_id") != source_build_id
            or metadata.get("source_product_build_id") != previous_build_id
            or input_hashes.get("predecessor-academic-inputs")
            != rebind.get("source_sha256")
            or input_hashes.get("predecessor-run-contract-authority")
            != previous_authority_hash
        ):
            raise ProductRunnerCompatibilityError(
                "chained successor academic ledger receipt binding is invalid"
            )

    def _prepare_successor_migration(
        self, task: dict[str, Any], *, command_id: str
    ) -> dict[str, Any]:
        preview = self._preview_successor_migration(task)
        source_runner = preview["source_runner_state"]
        authority = preview["authority"]
        source_build_id = task["product_manifest"]["build_id"]
        source_identity = self._task_successor_identity(task, source_runner)
        academic_receipt, academic_rebind = self._prepare_successor_academic_inputs(
            task,
            source_runner,
            source_build_id=source_build_id,
            command_id=command_id,
        )
        migration_id = (
            "successor-"
            + hashlib.sha256(
                (
                    f"{task['task_id']}|{source_build_id}|{self.expected_build_id}"
                ).encode("utf-8")
            ).hexdigest()[:32]
        )
        recorded_at = _now()
        next_runner = deepcopy(source_runner)
        next_runner["runner_version"] = RUNNER_VERSION
        next_runner["product_build_id"] = self.expected_build_id
        if academic_receipt is not None:
            next_runner["academic_inputs"] = self._academic_pointer(academic_receipt)
        next_runner["successor_migration"] = {
            "contract": "paperspine5.runner-successor-link",
            "schema_version": "1.0",
            "migration_id": migration_id,
            "source_build_id": source_build_id,
            "target_build_id": self.expected_build_id,
            "authority_sha256": authority["authority_sha256"],
            "source_identity_sha256": source_identity["identity_sha256"],
            "external_action_authorized": False,
        }
        next_runner["updated_at"] = recorded_at
        next_state = deepcopy(task["state"])
        next_state["runner"] = next_runner
        next_state["last_command"] = {
            "command_id": command_id,
            "command_type": "runner.successor.resume",
            "recorded_at": recorded_at,
        }
        target_manifest = deepcopy(self.kernel.product_manifest)
        target_state_sha256 = _sha256_bytes(_json_bytes(next_state))
        receipt = {
            "contract": "paperspine5.runner-successor-migration-receipt",
            "schema_version": "1.0",
            "migration_id": migration_id,
            "command_id": command_id,
            "task_id": task["task_id"],
            "active_run_id": task["active_run_id"],
            "revision": task["revision"],
            "source": {
                "build_id": source_build_id,
                "runner_version": source_runner["runner_version"],
                "core_root": task["core_root"],
                "identity": source_identity,
            },
            "target": {
                "build_id": self.expected_build_id,
                "runner_version": RUNNER_VERSION,
                "core_root": str(self.kernel.core_root),
                "product_manifest_sha256": _sha256_bytes(_json_bytes(target_manifest)),
                "task_state_sha256": target_state_sha256,
            },
            "installed_suite_authority": authority,
            "academic_rebind": academic_rebind,
            "preservation": {
                "same_task_id": True,
                "same_active_run_id": True,
                "same_workspace_root": True,
                "same_run_root": True,
                "same_revision": True,
                "same_stage": True,
                "same_material_snapshot_sha256": True,
                "predecessor_artifacts_retained": True,
                "predecessor_commands_retained": True,
                "new_task_created": False,
                "material_snapshot_copied": False,
            },
            "recovery": {
                "transaction": "sqlite-begin-immediate-atomic-rollback",
                "pre_product_manifest_sha256": source_identity[
                    "product_manifest_sha256"
                ],
                "pre_task_state_sha256": source_identity["task_state_sha256"],
                "pre_artifact_set_sha256": source_identity["artifact_set_sha256"],
                "pre_command_set_sha256": source_identity["command_set_sha256"],
                "uncommitted_derived_artifact_policy": "delete-if-not-ledger-committed",
            },
            "recorded_at": recorded_at,
            "external_action_authorized": False,
        }
        receipt["receipt_sha256"] = _sha256_bytes(_json_bytes(receipt))
        command_payload = {
            "migration_id": migration_id,
            "source_build_id": source_build_id,
            "target_build_id": self.expected_build_id,
            "source_runner_version": source_runner["runner_version"],
            "target_runner_version": RUNNER_VERSION,
            "source_identity_sha256": source_identity["identity_sha256"],
            "material_snapshot_sha256": source_identity["material_snapshot_sha256"],
            "authority_sha256": authority["authority_sha256"],
            "receipt_sha256": receipt["receipt_sha256"],
        }
        return {
            "command_payload": command_payload,
            "source_identity": source_identity,
            "target_manifest": target_manifest,
            "target_core_root": str(self.kernel.core_root),
            "target_state": next_state,
            "successor_academic_receipt": academic_receipt,
            "migration_receipt": receipt,
            "recorded_at": recorded_at,
        }

    def _handle_successor_resume(
        self, task: dict[str, Any], command: dict[str, Any], prepared: dict[str, Any]
    ) -> dict[str, Any]:
        source_identity = prepared.get("source_identity")
        receipt = prepared.get("migration_receipt")
        command_payload = prepared.get("command_payload")
        if (
            not isinstance(source_identity, dict)
            or not isinstance(receipt, dict)
            or not isinstance(command_payload, dict)
            or command.get("payload") != command_payload
            or source_identity.get("task_id") != task["task_id"]
            or source_identity.get("revision") != task["revision"]
            or source_identity.get("active_run_id") != task["active_run_id"]
            or source_identity.get("product_manifest_sha256")
            != _sha256_bytes(_json_bytes(task["product_manifest"]))
            or source_identity.get("task_state_sha256")
            != _sha256_bytes(_json_bytes(task["state"]))
            or command_payload.get("receipt_sha256") != receipt.get("receipt_sha256")
        ):
            raise ProductRunnerCompatibilityError(
                "successor resume source task, snapshot, or receipt binding changed"
            )
        artifacts = []
        academic_receipt = prepared.get("successor_academic_receipt")
        if academic_receipt is not None:
            artifacts.append(academic_receipt)
        return {
            "state": prepared["target_state"],
            "product_manifest": prepared["target_manifest"],
            "core_root": prepared["target_core_root"],
            "artifacts": artifacts,
            "migration_receipt": receipt,
            "event_payload": {
                "migration_id": receipt["migration_id"],
                "source_build_id": receipt["source"]["build_id"],
                "target_build_id": receipt["target"]["build_id"],
                "revision_preserved": True,
                "material_snapshot_sha256": source_identity["material_snapshot_sha256"],
            },
            "result": {
                "migration_id": receipt["migration_id"],
                "migration_receipt_sha256": receipt["receipt_sha256"],
                "same_task_resumed": True,
                "revision_preserved": True,
                "stage": task["state"]["runner"]["stage"],
                "external_action_authorized": False,
            },
        }

    def _task_for_mutation(
        self, task_id: str, expected_revision: int
    ) -> dict[str, Any]:
        task = self.kernel.get_task(task_id)
        if task["revision"] != expected_revision:
            from .product_kernel import RevisionConflictError

            raise RevisionConflictError(
                f"expected_revision {expected_revision} does not match current revision {task['revision']}"
            )
        issue = self._compatibility_issue(task)
        if issue and issue["code"] != "legacy.ingestion_required":
            raise ProductRunnerCompatibilityError(issue["details"])
        return task

    def _compatibility_issue(self, task: dict[str, Any]) -> dict[str, Any] | None:
        manifest = task["product_manifest"]
        if (
            manifest.get("build_id") != self.expected_build_id
            or manifest.get("component_versions", {}).get("product_runner")
            != RUNNER_VERSION
            or manifest.get("compatibility", {}).get("product_runner_protocol")
            != RUNNER_PROTOCOL_VERSION
        ):
            return self._issue(
                task,
                revision=task["revision"],
                code="runner.build_incompatible",
                stage="J1",
                details="Task product identity is not writable by this ProductRunner build.",
                allowed_actions=["open_with_matching_build"],
            )
        if task["migration_status"] != "not_applicable":
            return self._issue(
                task,
                revision=task["revision"],
                code="legacy.ingestion_required",
                stage="J2",
                details=(
                    "Legacy job/state were registered read-only; copy-on-write content ingestion "
                    "is required before the Product Runner can continue."
                ),
                allowed_actions=["copy_on_write_ingest"],
            )
        return None

    def _runner_state(self, task: dict[str, Any]) -> dict[str, Any]:
        runner_state = task["state"].get("runner")
        if runner_state is None:
            raise ContractError("Product Runner has not bootstrapped this task")
        return validate_runner_state(
            runner_state, task_id=task["task_id"], build_id=self.expected_build_id
        )

    def _handle_add_materials(
        self, task: dict[str, Any], command: dict[str, Any], prepared: dict[str, Any]
    ) -> dict[str, Any]:
        if prepared:
            raise ContractError(
                "runner.materials.add does not accept prepared artifacts"
            )
        if task["migration_status"] != "not_applicable":
            raise ContractError(
                "legacy read-only registration requires copy-on-write ingestion"
            )
        roots = command["payload"].get("materials_roots")
        if not isinstance(roots, list) or not roots:
            raise ContractError(
                "runner.materials.add requires non-empty materials_roots"
            )
        grants = list(task["material_grants"])
        # A previously granted temporary folder may disappear between runs.
        # Keep the task and its history, but allow an explicit user-provided
        # replacement root to rebind the material capability.  This is the
        # narrow recovery path for the common "regrant required" condition;
        # it never broadens access and still validates every new root below.
        valid_grants: list[dict[str, Any]] = []
        invalid_grant_ids: list[str] = []
        known: set[Path] = set()
        for grant in grants:
            try:
                root = _validate_grant_root(grant)
            except ContractError:
                invalid_grant_ids.append(str(grant.get("grant_id") or "unknown"))
                continue
            valid_grants.append(grant)
            known.add(root)
        grants = valid_grants
        now = _now()
        added_count = 0
        for raw in roots:
            if not isinstance(raw, str):
                raise ContractError("runner.materials.add roots must be strings")
            grant = _build_material_grant(raw, len(grants) + 1, now)
            root = Path(grant["canonical_target"])
            if root in known:
                continue
            known.add(root)
            grants.append(grant)
            added_count += 1
        if added_count == 0:
            raise ContractError(
                "runner.materials.add did not add a new capability root"
            )
        revision = command["expected_revision"] + 1
        issue = self._issue(
            task,
            revision=revision,
            code="materials.rebootstrap_required",
            stage="J2",
            details="Material grants changed; inventory and all downstream configuration are stale.",
            allowed_actions=["runner.bootstrap"],
        )
        state = dict(task["state"])
        state["runner"] = self._state(
            stage="awaiting_materials",
            issues=[issue],
            material_inventory=None,
            run_contract=None,
            next_actions=["runner.bootstrap"],
        )
        return {
            "state": state,
            "status": "blocked",
            "material_grants": grants,
            "event_payload": {"runner_stage": "awaiting_materials"},
            "result": {
                "open_issue": issue,
                "replaced_invalid_grant_ids": invalid_grant_ids,
            },
        }

    def _handle_bootstrap(
        self, task: dict[str, Any], command: dict[str, Any], prepared: dict[str, Any]
    ) -> dict[str, Any]:
        revision = command["expected_revision"] + 1
        if task["migration_status"] != "not_applicable":
            issue = self._issue(
                task,
                revision=revision,
                code="legacy.ingestion_required",
                stage="J2",
                details=(
                    "Legacy source is only a read-only capability. W3 does not implement the "
                    "copy-on-write legacy content ingestion adapter."
                ),
                allowed_actions=["copy_on_write_ingest"],
            )
            runner = self._state(
                stage="awaiting_materials",
                issues=[issue],
                material_inventory=None,
                run_contract=None,
                next_actions=[],
            )
            artifacts: list[dict[str, Any]] = []
        elif not task["material_grants"]:
            issue = self._issue(
                task,
                revision=revision,
                code="materials.grant_required",
                stage="J2",
                details="At least one read-only materials capability grant is required.",
                allowed_actions=["runner.materials.add"],
            )
            runner = self._state(
                stage="awaiting_materials",
                issues=[issue],
                material_inventory=None,
                run_contract=None,
                next_actions=["runner.materials.add"],
            )
            artifacts = []
        else:
            receipt = prepared.get("inventory_receipt")
            inventory = self._read_inventory_receipt(task, receipt, revision)
            issues = [
                self._issue(
                    task,
                    revision=revision,
                    code=item["code"],
                    stage="J2",
                    severity=item["severity"],
                    details=item["details"],
                    allowed_actions=["runner.bootstrap"],
                    nonce=str(index),
                )
                for index, item in enumerate(inventory["scan_issues"])
            ]
            if inventory["source_count"] == 0:
                issues.append(
                    self._issue(
                        task,
                        revision=revision,
                        code="materials.empty",
                        stage="J2",
                        details="The granted material roots contain no regular files.",
                        allowed_actions=["runner.materials.add", "runner.bootstrap"],
                    )
                )
            has_blocker = any(item["severity"] == "blocker" for item in issues)
            if not has_blocker and inventory["source_count"]:
                issues.append(
                    self._issue(
                        task,
                        revision=revision,
                        code="configuration.required",
                        stage="J3",
                        details=(
                            "Confirm workflow, scene, target status, language, deliverables, budget, "
                            "network and privacy policy. Unknown targets stay unknown."
                        ),
                        allowed_actions=["runner.issue.answer"],
                    )
                )
                stage = "awaiting_configuration"
                next_actions = ["runner.issue.answer"]
            else:
                stage = "awaiting_materials"
                next_actions = ["runner.bootstrap", "runner.materials.add"]
            runner = self._state(
                stage=stage,
                issues=issues,
                material_inventory=self._pointer(receipt, inventory["snapshot_sha256"]),
                run_contract=None,
                next_actions=next_actions,
            )
            artifacts = [receipt]
        state = dict(task["state"])
        state["runner"] = runner
        blockers = [
            item
            for item in runner["issues"]
            if item["status"] == "open" and item["severity"] == "blocker"
        ]
        return {
            "state": state,
            "status": "blocked" if blockers else "active",
            "artifacts": artifacts,
            "event_payload": {"runner_stage": runner["stage"]},
            "result": {"open_issues": blockers},
        }

    def _handle_delegated_grant_renew(
        self, task: dict[str, Any], command: dict[str, Any], prepared: dict[str, Any]
    ) -> dict[str, Any]:
        """Atomically reopen J3 without minting or modifying a grant."""
        actor = command.get("actor")
        if not isinstance(actor, dict):
            raise ContractError("delegated grant renewal requires a user-origin actor")
        if actor.get("authority_kind") not in {
            "authenticated_local_user_session",
            "host_user_message",
        } or not all(isinstance(actor.get(key), str) and actor[key].strip() for key in ("actor_id", "surface")):
            raise ContractError("delegated grant renewal actor is not user-originated")
        inventory_receipt = prepared.get("inventory_receipt")
        revision = command["expected_revision"] + 1
        inventory = self._read_inventory_receipt(task, inventory_receipt, revision)
        runner = self._runner_state(task)
        interaction = runner.get("interaction") or {}
        if interaction.get("mode") != "delegated_local_test":
            raise ContractError("delegated grant renewal requires an existing delegated local run")
        grant = interaction.get("grant")
        # Runner state intentionally exposes only a public interaction
        # projection. Recover the typed grant from the persisted run contract
        # authority when the projection omits its sensitive fields.
        if not isinstance(grant, dict):
            contract_pointer = runner.get("run_contract")
            if isinstance(contract_pointer, dict) and isinstance(
                contract_pointer.get("path"), str
            ):
                contract = self._load_run_json(task, contract_pointer["path"])
                configuration = contract.get("configuration")
                configured_interaction = (
                    configuration.get("interaction")
                    if isinstance(configuration, dict)
                    else None
                )
                grant = (
                    configured_interaction.get("grant")
                    if isinstance(configured_interaction, dict)
                    else None
                )
        if not isinstance(grant, dict):
            raise ContractError("delegated grant renewal requires the existing typed grant")
        if grant.get("task_id") != task["task_id"]:
            raise ContractError("delegated grant task binding is invalid")
        expires_at = grant.get("expires_at")
        try:
            expires = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ContractError("delegated grant expiry is invalid") from exc
        if expires > datetime.now(timezone.utc):
            raise ContractError("delegated grant is still valid; renewal is not required")
        prior_snapshot = (
            runner.get("material_inventory") or {}
        ).get("snapshot_sha256")
        if prior_snapshot != inventory["snapshot_sha256"]:
            raise ContractError(
                "material inventory changed; refresh materials before renewing the grant"
            )
        issue = self._issue(
            task,
            revision=command["expected_revision"] + 1,
            issue_id=f"configuration:{task['task_id']}:{command['expected_revision'] + 1}:required",
            code="configuration.required",
            stage="J3",
            details=(
                "The prior local delegation grant was reopened by an explicit user-origin request. "
                "Confirm the current workflow, scope and decision classes to issue a fresh grant."
            ),
            allowed_actions=["runner.issue.answer"],
            public_context={"renewal": True, "prior_grant_id": grant.get("grant_id")},
        )
        revision = command["expected_revision"] + 1
        downstream_ids: list[str] = []
        prior_contract = runner.get("run_contract")
        if isinstance(prior_contract, dict) and isinstance(prior_contract.get("artifact_id"), str):
            downstream_ids.append(prior_contract["artifact_id"])
        for field in ("academic_inputs", "academic_artifacts", "academic_base_artifacts"):
            value = runner.get(field)
            if isinstance(value, dict):
                # `academic_inputs` is one pointer; the other two fields are
                # maps of semantic IDs to pointers. Invalidate artifact IDs,
                # never pointer field names.
                direct_id = value.get("artifact_id")
                if isinstance(direct_id, str) and direct_id:
                    downstream_ids.append(direct_id)
                else:
                    for pointer in value.values():
                        if isinstance(pointer, dict) and isinstance(pointer.get("artifact_id"), str):
                            downstream_ids.append(pointer["artifact_id"])
        next_runner = self._state(
            stage="awaiting_configuration",
            issues=[issue],
            material_inventory=self._pointer(
                inventory_receipt, inventory["snapshot_sha256"]
            ),
            run_contract=None,
            next_actions=["runner.issue.answer"],
            academic_inputs=None,
            academic_artifacts=None,
            academic_base_artifacts=None,
            interaction={
                "mode": "guided",
                "requested_scope": "local_delivery",
                "grant_status": "not_applicable",
                "grant_id": None,
                "grant_sha256": None,
                "decision_classes": [],
                "decision_receipts": [],
                "external_action_authorized": False,
            },
        )
        state = dict(task["state"])
        state["runner"] = next_runner
        return {
            "state": state,
            "status": "blocked",
            "artifacts": [inventory_receipt],
            "event_payload": {
                "runner_stage": "awaiting_configuration",
                "renewal": True,
                "prior_grant_id": grant.get("grant_id"),
                "invalidated_artifacts": sorted(set(downstream_ids)),
            },
            "result": {"open_issue": issue, "invalidated_artifacts": sorted(set(downstream_ids))},
        }

    def _handle_answer_issue(
        self, task: dict[str, Any], command: dict[str, Any], prepared: dict[str, Any]
    ) -> dict[str, Any]:
        runner = self._runner_state(task)
        issue = self._find_open_issue(runner, command["payload"].get("issue_id"))
        self._verify_resume_token(task, issue, command["payload"].get("resume_token"))
        if issue["code"] == "academic.input.required":
            return self._handle_academic_answer(task, command, prepared, runner, issue)
        if issue["code"] == "contribution.confirmation.required":
            return self._handle_contribution_confirmation(
                task, command, prepared, runner, issue
            )
        if issue["code"] != "configuration.required":
            raise ContractError("this runner issue does not accept an answer")
        revision = command["expected_revision"] + 1
        configuration = validate_run_configuration(command["payload"].get("answer"))
        inventory_receipt = prepared.get("inventory_receipt")
        inventory = self._read_inventory_receipt(task, inventory_receipt, revision)
        if (
            inventory["snapshot_sha256"]
            != runner["material_inventory"]["snapshot_sha256"]
        ):
            raise ContractError(
                "materials changed; bootstrap a new inventory before answering"
            )
        contract_receipt = prepared.get("run_contract_receipt")
        self._read_run_contract_receipt(
            task,
            contract_receipt,
            revision,
            inventory=inventory,
            configuration=configuration,
        )
        issues: list[dict[str, Any]] = []
        for item in runner["issues"]:
            updated = dict(item)
            if item["issue_id"] == issue["issue_id"]:
                updated["status"] = "resolved"
                updated["resolved_at"] = _now()
                updated["resolution_artifact_id"] = contract_receipt["artifact_id"]
            issues.append(updated)
        next_runner = self._state(
            stage="configured",
            issues=issues,
            material_inventory=self._pointer(
                inventory_receipt, inventory["snapshot_sha256"]
            ),
            run_contract=self._pointer(contract_receipt, inventory["snapshot_sha256"]),
            next_actions=["runner.resume"],
            interaction=self._interaction_projection(configuration),
        )
        state = dict(task["state"])
        state["runner"] = next_runner
        return {
            "state": state,
            "status": "active",
            "artifacts": [inventory_receipt, contract_receipt],
            "event_payload": {
                "runner_stage": "configured",
                "resolved_issue_id": issue["issue_id"],
            },
            "result": {"run_contract_artifact_id": contract_receipt["artifact_id"]},
        }

    def _handle_contribution_confirmation(
        self,
        task: dict[str, Any],
        command: dict[str, Any],
        prepared: dict[str, Any],
        runner: dict[str, Any],
        issue: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine persisted candidates with server-bound user authority atomically."""

        confirmation = command["payload"].get("confirmation")
        author_identity = command["payload"].get("author_identity")
        confirmed_at = self.confirmation_clock()
        preparation = issue.get("candidate_preparation")
        if not isinstance(preparation, dict):
            raise ContractError(
                "persisted contribution candidate preparation is missing"
            )
        preparation_sha256 = preparation.get("preparation_sha256")
        findings = validate_contribution_confirmation(
            confirmation,
            task_id=task["task_id"],
            revision=command["expected_revision"],
            issue_id=issue["issue_id"],
            preparation_sha256=(
                preparation_sha256 if isinstance(preparation_sha256, str) else ""
            ),
        )
        if findings:
            raise ContractError(
                "contribution confirmation is invalid: "
                + "; ".join(
                    f"{item.get('code')}: {item.get('message')}" for item in findings
                )
            )
        if not isinstance(author_identity, dict):
            raise ContractError("authenticated Product Web identity binding is missing")
        if not isinstance(confirmed_at, str) or not confirmed_at.strip():
            raise ContractError("Product Web confirmation clock returned no timestamp")
        academic_answer = {
            "contract": "paperspine5.academic-stage-answer",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "answer_id": str(confirmation["confirmation_id"]),
            "issue_id": issue["issue_id"],
            "task_id": task["task_id"],
            "expected_revision": command["expected_revision"],
            "stage": "awaiting_contribution",
            "payload": {
                "contract": "paperspine5.contribution-boundary-decision",
                "schema_version": PRODUCT_SCHEMA_VERSION,
                "authority_bindings": deepcopy(
                    preparation.get("authority_bindings", {})
                ),
                "candidates": deepcopy(preparation.get("candidates", [])),
                "decisions": deepcopy(confirmation.get("decisions", [])),
                "author_identity": deepcopy(author_identity),
                "confirmed_at": confirmed_at,
                "override_blockers": False,
                "input_artifacts": {
                    str(author_identity.get("attestation_input_id")): deepcopy(
                        author_identity
                    )
                },
                "external_action_authorized": False,
            },
            "external_action_authorized": False,
        }
        translated_command = deepcopy(command)
        translated_command["payload"] = {
            "issue_id": issue["issue_id"],
            "resume_token": command["payload"].get("resume_token"),
            "answer": academic_answer,
        }
        outcome = self._handle_academic_answer(
            task, translated_command, prepared, runner, issue
        )
        outcome["result"]["confirmation"] = {
            "confirmation_id": confirmation["confirmation_id"],
            "preparation_sha256": preparation_sha256,
            "author_identity": deepcopy(author_identity),
            "confirmed_at": confirmed_at,
            "external_action_authorized": False,
        }
        return outcome

    def _handle_academic_answer(
        self,
        task: dict[str, Any],
        command: dict[str, Any],
        prepared: dict[str, Any],
        runner: dict[str, Any],
        issue: dict[str, Any],
    ) -> dict[str, Any]:
        revision = command["expected_revision"] + 1
        answer = self._validated_academic_answer(
            command["payload"].get("answer"),
            task_id=task["task_id"],
            revision=command["expected_revision"],
            issue_id=issue["issue_id"],
            stage=runner["stage"],
        )
        figure_evidence = prepared.get("figure_evidence")
        if isinstance(figure_evidence, dict):
            answer = self._validated_academic_answer(
                deepcopy(figure_evidence["answer"]),
                task_id=task["task_id"],
                revision=command["expected_revision"],
                issue_id=issue["issue_id"],
                stage=runner["stage"],
            )
        answer, supplied_base_artifacts = self._split_academic_answer_inputs(answer)
        if any(value.get("contract") in {
            "paperspine5.figure-reference-mapping", "paperspine5.figure-final-mapping-consumption"
        } for value in supplied_base_artifacts.values()):
            raise ContractError("final mappings must use typed registration, not input_artifacts")
        from .figure_final_mapping import collect_final_mappings, promote_final_mappings
        from .quality_readiness import canonical_sha256 as publication_sha256
        from .paper_revision import retained_pointer
        # Early J4/J5 recovery can legitimately have no accepted J7 mapping:
        # a changed base input invalidates downstream pointers before research
        # is replayed. Only later stages need the frozen mapping surface.
        final_mappings = []
        if runner["stage"] not in {
            "awaiting_research",
            "awaiting_contribution",
            "awaiting_claim_graph",
            # J7 is the user figure-choice boundary.  A restarted J7 answer
            # must be able to create the accepted choice before J8 mappings
            # are collected; requiring a prior mapping here reverses the UI
            # journey and turns a recoverable choice into a false blocker.
            "awaiting_figure_intent",
        }:
            final_mappings = collect_final_mappings(self, task, actor=command["actor"])
        inventory_receipt = prepared.get("inventory_receipt")
        inventory = self._read_inventory_receipt(task, inventory_receipt, revision)
        if (
            inventory["snapshot_sha256"]
            != runner["material_inventory"]["snapshot_sha256"]
        ):
            raise ContractError(
                "materials changed; bootstrap a new inventory before answering"
            )
        contract_receipt = prepared.get("run_contract_receipt")
        run_contract = self._read_run_contract_receipt(
            task,
            contract_receipt,
            revision,
            inventory=inventory,
        )
        cumulative_inputs = self._read_academic_inputs(
            task, runner.get("academic_inputs")
        )
        # A same-task recovery can leave a new pointer with an empty stage
        # ledger even though the preceding accepted stage receipts are still
        # committed.  Restore that completed prefix before the orchestrator
        # evaluates J7/J8 cumulative continuity; the current base snapshot and
        # all mutation checks remain authoritative.
        if isinstance(cumulative_inputs, dict):
            current_stage_inputs = cumulative_inputs.get("stage_inputs")
            if not isinstance(current_stage_inputs, dict) or not current_stage_inputs:
                recovered = self._recover_prior_academic_stage_inputs(
                    task,
                    current_revision=command["expected_revision"],
                    current_stage=runner["stage"],
                )
                if recovered:
                    cumulative_inputs["stage_inputs"] = recovered.get("stage_inputs", {})
        persisted_base_artifacts = self._read_academic_base_artifacts(
            task, runner.get("academic_base_artifacts")
        )
        base_artifacts = deepcopy(persisted_base_artifacts)
        base_artifacts.update(supplied_base_artifacts)
        # Keep the readiness contract in the same immutable base-artifact
        # registry that seeds the publication subject.  Without this, a
        # later J10 package could not prove that its obligation manifest was
        # bound at canonicalization time and would be forced into a false
        # package failure.
        from .quality_readiness import build_obligation_manifest
        base_artifacts.setdefault("readiness_obligations", build_obligation_manifest())
        if isinstance(figure_evidence, dict):
            base_artifacts.update(deepcopy(figure_evidence["base_artifacts"]))
        answer_payload = answer.get("payload")
        if runner["stage"] == "awaiting_canonical":
            from .paper_revision import validate_revised_canonical
            validate_revised_canonical(self, task, answer_payload, base_artifacts)
        resolution_requests = (
            answer_payload.get("material_semantic_resolution_requests")
            if isinstance(answer_payload, dict)
            else None
        )
        if resolution_requests is None:
            prior_profile = base_artifacts.get("materials.figure-set")
            resolution_requests = [
                item["request"]
                for item in (prior_profile or {}).get("semantic_resolutions", [])
                if isinstance(item, dict) and isinstance(item.get("request"), dict)
            ]
        base_artifacts["materials.figure-set"] = self._material_figure_set(
            task,
            inventory,
            semantic_resolution_requests=resolution_requests,
        )
        trusted_figure_master_receipt = self._trusted_figure_master_receipt(
            task=task,
            actor=command["actor"],
            current_stage=runner["stage"],
            persisted_base_artifacts=persisted_base_artifacts,
            effective_base_artifacts=base_artifacts,
        )
        if (
            trusted_figure_master_receipt is not None
            and "figure-master-authority" not in base_artifacts
        ):
            base_artifacts["figure-master-authority"] = deepcopy(
                trusted_figure_master_receipt
            )
        service_base_artifacts = {
            **base_artifacts,
            "materials.source-ledger": inventory,
            "runner.run-contract": run_contract,
        }
        if (
            isinstance(answer_payload, dict)
            and answer_payload.get("contract")
            == "paperspine5.contribution-candidate-preparation"
        ):
            bindings = answer_payload.get("authority_bindings")
            prior_artifacts = runner.get("academic_artifacts")
            prior_artifacts = (
                prior_artifacts if isinstance(prior_artifacts, dict) else {}
            )
            expected_bindings = {
                "direction_authority": (
                    prior_artifacts.get("direction_authority") or {}
                ).get("sha256"),
                "target_authority": (prior_artifacts.get("target_authority") or {}).get(
                    "sha256"
                ),
                "materials.source-ledger": inventory["snapshot_sha256"],
            }
            if bindings != expected_bindings:
                raise ContractError(
                    "J5 candidate preparation authority_bindings do not match the "
                    "current persisted Runner authority pointers"
                )
        registered_artifacts: dict[str, str] = {}
        for view in self.kernel.list_artifacts(
            task["task_id"], subject_revision=command["expected_revision"]
        ):
            receipt = view.get("receipt")
            if view.get("freshness") != "fresh" or not isinstance(receipt, dict):
                continue
            artifact_id = receipt.get("artifact_id")
            sha256 = receipt.get("sha256")
            if isinstance(artifact_id, str) and isinstance(sha256, str):
                prior = registered_artifacts.get(artifact_id)
                if prior is not None and prior != sha256:
                    raise ContractError(
                        "current artifact registry contains conflicting hashes"
                    )
                registered_artifacts[artifact_id] = sha256
        j7_candidate_plan_hashes: dict[str, str] = {}
        if runner["stage"] == "awaiting_figure_intent":
            for value in persisted_base_artifacts.values():
                if value.get("contract") != "paperspine5.figure-candidate-asset":
                    continue
                candidate_plan = value.get("reference_plan")
                if not isinstance(candidate_plan, dict):
                    continue
                plan_artifact_id = candidate_plan.get("artifact_id")
                plan_sha256 = candidate_plan.get("sha256")
                if isinstance(plan_artifact_id, str) and isinstance(
                    plan_sha256, str
                ):
                    j7_candidate_plan_hashes[plan_artifact_id] = plan_sha256
        retained_reference_plans = {
            key: value["plan_sha256"]
            for key, value in persisted_base_artifacts.items()
            if value.get("contract") == "paperspine5.figure-reference-plan"
            and (
                retained_pointer(task, "academic_base_artifacts", key)
                or j7_candidate_plan_hashes.get(key) == value.get("plan_sha256")
                or (
                    runner["stage"] == "awaiting_figure_intent"
                    and isinstance(value.get("subject"), dict)
                    and value["subject"].get("task_id") == task["task_id"]
                    and value["subject"].get("material_snapshot_sha256")
                    == inventory.get("snapshot_sha256")
                    and any(
                        isinstance(item, dict)
                        and item.get("reference_plan_artifact_id") == key
                        and item.get("reference_plan_sha256") == value.get("plan_sha256")
                        for item in (
                            receipt.get("metadata", {})
                            for receipt in (
                                view.get("receipt")
                                for view in self.kernel.list_artifacts(
                                    task["task_id"], subject_revision=command["expected_revision"]
                                )
                                if isinstance(view.get("receipt"), dict)
                            )
                        )
                    )
                )
            )
        }
        result = self.academic_orchestrator.advance(
            task_id=task["task_id"],
            revision=revision,
            answer_revision=command["expected_revision"],
            current_stage=runner["stage"],
            cumulative_inputs=cumulative_inputs,
            answer=answer,
            base_artifacts=service_base_artifacts,
            registered_artifacts=registered_artifacts,
            trusted_figure_master_receipt=trusted_figure_master_receipt,
            retained_reference_plans=retained_reference_plans,
            registered_final_mapping_context={
                "policy": "required-for-every-new-j8",
                "build_id": self.expected_build_id,
                "bindings": [deepcopy(item["envelope"]["accepted_j7"]) for item in final_mappings],
                **({"accepted_consumption": deepcopy(final_mappings[0]["envelope"]["successor_revalidation"]["accepted_consumption"])}
                   if runner["stage"] != "awaiting_canonical" and final_mappings
                   and self._accepted_academic_view(task, "publication.manuscript-head") is not None
                   and self._accepted_academic_view(task, "publication.manuscript-head")["payload"].get("final_mapping_consumption_sha256")
                       == publication_sha256(final_mappings[0]["envelope"].get("successor_revalidation", {}).get("accepted_consumption"))
                   and all(item["envelope"].get("successor_revalidation", {}).get("accepted_consumption")
                           == final_mappings[0]["envelope"].get("successor_revalidation", {}).get("accepted_consumption")
                           for item in final_mappings)
                   and final_mappings[0]["envelope"].get("successor_revalidation") else {}),
            },
        )
        result_findings = validate_academic_stage_result(result)
        if result_findings:
            raise ContractError(
                "academic stage result is invalid: "
                + "; ".join(
                    f"{item.get('code')}: {item.get('message')}"
                    for item in result_findings
                )
            )
        atomic_blockers = _atomic_academic_blockers(result.get("blockers"))
        if result.get("status") == "BLOCKED" and (
            issue.get("code") == "contribution.confirmation.required"
            or answer.get("payload", {}).get("contract")
            == "paperspine5.contribution-candidate-preparation"
            or atomic_blockers
        ):
            rejected = (
                result.get("blockers", []) if not atomic_blockers else atomic_blockers
            )
            raise ContractError(
                "academic answer rejected atomically: "
                + "; ".join(
                    f"{item.get('code')}: {item.get('message')}"
                    for item in rejected
                    if isinstance(item, dict)
                )
            )
        binary_receipts: list[dict[str, Any]] = []
        if isinstance(figure_evidence, dict):
            for item in figure_evidence["binary_outputs"]:
                staged_path = Path(item["staged_path"])
                content = staged_path.read_bytes()
                if (
                    _sha256_bytes(content) != item["sha256"]
                    or len(content) != item["size_bytes"]
                ):
                    raise ContractError(
                        "prepared corrected figure bytes changed before Runner publication"
                    )
                receipt = self._publish_binary_artifact(
                    task,
                    content=content,
                    relative=Path(item["path"]),
                    revision=revision,
                    command_id=command["command_id"],
                    artifact_id=item["artifact_id"],
                    artifact_type=str(item["artifact_type"]),
                    input_hashes={
                        "materials.source-ledger": inventory_receipt["sha256"],
                        item["correction_receipt_artifact_id"]: base_artifacts[
                            item["correction_receipt_artifact_id"]
                        ]["receipt_sha256"],
                    },
                    metadata={
                        "academic_stage": "awaiting_figure_intent",
                        "figure_id": item["figure_id"],
                        "candidate_id": item["candidate_id"],
                        "asset_role": item["asset_role"],
                    },
                )
                binary_receipts.append(receipt)
                figure_evidence["published_paths"].append(
                    str((Path(task["run_root"]) / item["path"]).resolve())
                )
        registered_candidate_evidence = prepared.get("registered_candidate_evidence")
        if isinstance(registered_candidate_evidence, dict):
            published_artifact_ids = {
                receipt["artifact_id"] for receipt in binary_receipts
            }
            for item in registered_candidate_evidence["binary_outputs"]:
                if item["artifact_id"] in published_artifact_ids:
                    raise ContractError(
                        "J7 candidate was prepared by more than one binary authority route"
                    )
                source_path = Path(item["source_path"])
                content = source_path.read_bytes()
                if (
                    _sha256_bytes(content) != item["sha256"]
                    or len(content) != item["size_bytes"]
                ):
                    raise ContractError(
                        "registered J7 candidate bytes changed before CAS promotion"
                    )
                receipt = self._publish_binary_artifact(
                    task,
                    content=content,
                    relative=Path(item["path"]),
                    revision=revision,
                    command_id=command["command_id"],
                    artifact_id=item["artifact_id"],
                    artifact_type=item["artifact_type"],
                    input_hashes={
                        "materials.source-ledger": inventory_receipt["sha256"],
                        "registration.request": item["registration_request_sha256"],
                        "academic.input-artifact": item["input_artifact_sha256"],
                        item["reference_plan_artifact_id"]: item[
                            "reference_plan_sha256"
                        ],
                    },
                    metadata={
                        "academic_stage": "awaiting_figure_intent",
                        "figure_id": item["figure_id"],
                        "candidate_id": item["candidate_id"],
                        "asset_role": item["asset_role"],
                        "registration_command_id": item["registration_command_id"],
                        "registration_request_sha256": item[
                            "registration_request_sha256"
                        ],
                        "input_artifact_sha256": item["input_artifact_sha256"],
                        "reference_plan_artifact_id": item[
                            "reference_plan_artifact_id"
                        ],
                        "reference_plan_sha256": item["reference_plan_sha256"],
                        "registered_revision": item["registered_revision"],
                        "material_snapshot_sha256": inventory["snapshot_sha256"],
                        "media_type": _FIGURE_CANDIDATE_MEDIA_TYPES[
                            Path(item["path"]).suffix.lower()
                        ],
                    },
                    executor_id=None,
                )
                binary_receipts.append(receipt)
                published_artifact_ids.add(item["artifact_id"])
        binary_receipts.extend(promote_final_mappings(self, task, final_mappings,
            revision=revision, command_id=command["command_id"]))
        base_receipts = [
            self._publish_academic_base_artifact(
                task,
                artifact_id,
                payload,
                revision=revision,
                command_id=command["command_id"],
                input_hashes={
                    "materials.source-ledger": inventory_receipt["sha256"],
                    "runner.run-contract": contract_receipt["sha256"],
                },
                trusted_figure_master_receipt=trusted_figure_master_receipt,
            )
            for artifact_id, payload in sorted(base_artifacts.items())
        ]
        descriptor_receipts = [
            self._publish_stage_descriptor(
                task,
                descriptor,
                revision=revision,
                command_id=command["command_id"],
            )
            for descriptor in result.get("descriptors", [])
        ]
        input_receipt = self._publish_artifact(
            task,
            value={
                "contract": "paperspine5.academic-cumulative-inputs",
                "schema_version": PRODUCT_SCHEMA_VERSION,
                "task_id": task["task_id"],
                "revision_id": str(revision),
                "stage": result["stage"],
                "inputs": result["cumulative_inputs"],
                "external_action_authorized": False,
            },
            revision=revision,
            command_id=command["command_id"],
            artifact_id="runner.academic-inputs",
            artifact_type="runner.academic-inputs",
            input_hashes={
                "materials.source-ledger": inventory_receipt["sha256"],
                "runner.run-contract": contract_receipt["sha256"],
                **{
                    receipt["artifact_id"]: receipt["sha256"]
                    for receipt in base_receipts
                },
            },
            metadata={"academic_stage": result["stage"]},
        )
        descriptor_pointers = {
            receipt["artifact_id"]: self._academic_pointer(receipt)
            for receipt in descriptor_receipts
        }
        invalidated_artifact_ids = {
            str(artifact_id) for artifact_id in result.get("invalidated_artifacts", [])
        }
        prior_descriptor_pointers = runner.get("academic_artifacts")
        prior_descriptor_pointers = (
            prior_descriptor_pointers
            if isinstance(prior_descriptor_pointers, dict)
            else {}
        )
        # A semantic blocker is an audited Runner transition, but it must not
        # erase still-fresh J4/J5 authority pointers merely because the blocked
        # stage emitted no new descriptor.  Explicit invalidations remain
        # authoritative, and successful replayed descriptors replace old ones.
        academic_artifact_pointers = {
            artifact_id: deepcopy(pointer)
            for artifact_id, pointer in prior_descriptor_pointers.items()
            if artifact_id not in invalidated_artifact_ids
        }
        academic_artifact_pointers.update(descriptor_pointers)
        base_pointers: dict[str, dict[str, Any]] = {}
        for receipt in base_receipts:
            pointer = self._academic_pointer(receipt)
            semantic_artifact_id = pointer.get(
                "semantic_artifact_id", receipt["artifact_id"]
            )
            if semantic_artifact_id in base_pointers:
                raise ContractError(
                    "academic base artifact semantic identities must be unique"
                )
            base_pointers[str(semantic_artifact_id)] = pointer
        status = result["status"]
        readiness_payload = next(
            (
                item.get("payload")
                for item in result.get("descriptors", [])
                if item.get("artifact_id") == "publication.readiness"
                and isinstance(item.get("payload"), dict)
            ),
            {},
        )
        ready = (
            status == "PASS"
            and result["next_stage"] == "target_package_ready"
            and readiness_payload.get("is_complete_for_requested_scope") is True
        )
        next_stage = "target_package_ready" if ready else result["next_stage"]
        prior_issues: list[dict[str, Any]] = []
        for item in runner.get("issues", []):
            updated = dict(item)
            if item["issue_id"] == issue["issue_id"]:
                updated["status"] = "resolved"
                updated["resolved_at"] = _now()
                updated["resolution_artifact_id"] = input_receipt["artifact_id"]
            prior_issues.append(updated)
        if ready:
            issues = prior_issues
            next_actions: list[str] = []
        else:
            blocker_text = "; ".join(
                f"{item.get('code')}: {item.get('message')}"
                for item in result.get("blockers", [])
            )
            candidate_preparation = next(
                (
                    item.get("payload")
                    for item in result.get("descriptors", [])
                    if item.get("artifact_id") == "contribution_candidate_preparation"
                    and isinstance(item.get("payload"), dict)
                ),
                None,
            )
            if isinstance(candidate_preparation, dict):
                next_issue = self._issue(
                    task,
                    revision=revision,
                    issue_id=(
                        f"academic:{task['task_id']}:{revision}:awaiting_contribution"
                    ),
                    code="contribution.confirmation.required",
                    stage="J5",
                    details=(
                        "Evidence-bound contribution candidates are ready. "
                        "An authenticated user must select every candidate in Product Web."
                    ),
                    allowed_actions=["runner.contribution.confirm"],
                    nonce="awaiting_contribution-confirmation",
                    public_context={
                        "candidate_preparation": candidate_preparation,
                        "confirmation_identity_authority": (
                            "authenticated-loopback-product-web-session"
                        ),
                    },
                )
            else:
                revision_context = result.get("cumulative_inputs", {}).get("revision_context")
                revision_request = None
                if next_stage == "awaiting_canonical" and isinstance(revision_context, dict) and revision_context.get("status") == "revision_required":
                    reviewed = revision_context["initial_review"]
                    revision_request = {
                        "review_sha256": reviewed["review_sha256"],
                        "reviewed_revision_id": reviewed["subject"]["revision_id"],
                        "manuscript_head_sha256": reviewed["manuscript_head_sha256"],
                        "objections": deepcopy(reviewed["objections"]),
                    }
                next_issue = self._issue(
                    task,
                    revision=revision,
                    issue_id=f"academic:{task['task_id']}:{revision}:{next_stage}",
                    code="academic.input.required",
                    stage=self._academic_journey_stage(next_stage),
                    details=(
                        blocker_text
                        if status == "BLOCKED" and blocker_text
                        else self._academic_stage_details(next_stage)
                    ),
                    allowed_actions=["runner.issue.answer"],
                    nonce=next_stage,
                    public_context={"revision_request": revision_request} if revision_request else None,
                )
            issues = [*prior_issues, next_issue]
            next_actions = list(next_issue["allowed_actions"])
        next_runner = self._state(
            stage=next_stage,
            issues=issues,
            material_inventory=self._pointer(
                inventory_receipt, inventory["snapshot_sha256"]
            ),
            run_contract=self._pointer(contract_receipt, inventory["snapshot_sha256"]),
            next_actions=next_actions,
            academic_inputs=self._academic_pointer(input_receipt),
            academic_artifacts=academic_artifact_pointers,
            academic_base_artifacts=base_pointers,
            interaction=self._interaction_projection(
                run_contract["configuration"], academic_artifact_pointers
            ),
        )
        state = dict(task["state"])
        state["runner"] = next_runner
        return {
            "state": state,
            "status": "completed" if ready else "blocked",
            "artifacts": [
                inventory_receipt,
                contract_receipt,
                *binary_receipts,
                *base_receipts,
                input_receipt,
                *descriptor_receipts,
            ],
            "event_payload": {
                "runner_stage": next_stage,
                "resolved_issue_id": issue["issue_id"],
                "academic_status": status,
                "invalidated_artifacts": result.get("invalidated_artifacts", []),
            },
            "result": {
                "academic_stage": result["stage"],
                "next_stage": next_stage,
                "ready": ready,
                "requested_scope": readiness_payload.get("requested_scope"),
                "manuscript_ready": bool(readiness_payload.get("manuscript_ready")),
                "delivery_ready": bool(readiness_payload.get("delivery_ready")),
                "submission_ready": bool(readiness_payload.get("submission_ready")),
                "is_complete_for_requested_scope": bool(
                    readiness_payload.get("is_complete_for_requested_scope")
                ),
                "external_action_authorized": False,
                "blockers": result.get("blockers", []),
            },
        }

    def _handle_resume(
        self, task: dict[str, Any], command: dict[str, Any], prepared: dict[str, Any]
    ) -> dict[str, Any]:
        revision = command["expected_revision"] + 1
        runner = task["state"].get("runner")
        if runner is None:
            raise ContractError("runner.resume requires runner.bootstrap first")
        runner = validate_runner_state(
            runner, task_id=task["task_id"], build_id=self.expected_build_id
        )
        if task["migration_status"] != "not_applicable":
            return self._handle_bootstrap(
                task,
                command,
                {"inventory_receipt": None},
            )
        inventory_receipt = prepared.get("inventory_receipt")
        inventory = self._read_inventory_receipt(task, inventory_receipt, revision)
        prior_snapshot = (runner.get("material_inventory") or {}).get("snapshot_sha256")
        if inventory["snapshot_sha256"] != prior_snapshot:
            return self._handle_bootstrap(
                task,
                command,
                {"inventory_receipt": inventory_receipt},
            )
        if runner["stage"] == "awaiting_configuration":
            warnings = [
                item
                for item in runner["issues"]
                if item["status"] == "open" and item["severity"] == "warning"
            ]
            issue = self._issue(
                task,
                revision=revision,
                code="configuration.required",
                stage="J3",
                details="A typed run configuration is still required before J4.",
                allowed_actions=["runner.issue.answer"],
            )
            next_runner = self._state(
                stage="awaiting_configuration",
                issues=[*warnings, issue],
                material_inventory=self._pointer(
                    inventory_receipt, inventory["snapshot_sha256"]
                ),
                run_contract=None,
                next_actions=["runner.issue.answer"],
            )
            artifacts = [inventory_receipt]
        elif runner["stage"] in {"configured", "blocked_j4"}:
            contract_receipt = prepared.get("run_contract_receipt")
            if contract_receipt is None:
                raise ContractError(
                    "configured runner resume requires a current run contract"
                )
            run_contract = self._read_run_contract_receipt(
                task, contract_receipt, revision, inventory=inventory
            )
            if run_contract["material_snapshot_sha256"] != inventory["snapshot_sha256"]:
                raise ContractError(
                    "run contract is not bound to the current material inventory"
                )
            issue = self._issue(
                task,
                revision=revision,
                issue_id=f"academic:{task['task_id']}:{revision}:awaiting_research",
                code="academic.input.required",
                stage="J4",
                details=self._academic_stage_details("awaiting_research"),
                allowed_actions=["runner.issue.answer"],
                nonce="awaiting_research",
            )
            next_runner = self._state(
                stage="awaiting_research",
                issues=[issue],
                material_inventory=self._pointer(
                    inventory_receipt, inventory["snapshot_sha256"]
                ),
                run_contract=self._pointer(
                    contract_receipt, inventory["snapshot_sha256"]
                ),
                next_actions=["runner.issue.answer"],
                academic_inputs=runner.get("academic_inputs"),
                academic_artifacts=runner.get("academic_artifacts"),
                academic_base_artifacts=runner.get("academic_base_artifacts"),
                interaction=self._interaction_projection(
                    run_contract["configuration"], runner.get("academic_artifacts")
                ),
            )
            artifacts = [inventory_receipt, contract_receipt]
        elif runner["stage"].startswith("awaiting_"):
            contract_receipt = prepared.get("run_contract_receipt")
            if contract_receipt is None:
                raise ContractError(
                    "academic issue refresh requires a current run contract"
                )
            run_contract = self._read_run_contract_receipt(
                task, contract_receipt, revision, inventory=inventory
            )
            prior_confirmation = next(
                (
                    item
                    for item in runner.get("issues", [])
                    if item.get("status") == "open"
                    and item.get("code") == "contribution.confirmation.required"
                    and isinstance(item.get("candidate_preparation"), dict)
                ),
                None,
            )
            if prior_confirmation is not None:
                issue = self._issue(
                    task,
                    revision=revision,
                    issue_id=(
                        f"academic:{task['task_id']}:{revision}:awaiting_contribution"
                    ),
                    code="contribution.confirmation.required",
                    stage="J5",
                    details=str(
                        prior_confirmation.get("details") or "Confirm candidates."
                    ),
                    allowed_actions=["runner.contribution.confirm"],
                    nonce="awaiting_contribution-confirmation",
                    public_context={
                        "candidate_preparation": deepcopy(
                            prior_confirmation["candidate_preparation"]
                        ),
                        "confirmation_identity_authority": (
                            "authenticated-loopback-product-web-session"
                        ),
                    },
                )
            else:
                issue = self._issue(
                    task,
                    revision=revision,
                    issue_id=(
                        f"academic:{task['task_id']}:{revision}:{runner['stage']}"
                    ),
                    code="academic.input.required",
                    stage=self._academic_journey_stage(runner["stage"]),
                    details=self._academic_stage_details(runner["stage"]),
                    allowed_actions=["runner.issue.answer"],
                    nonce=runner["stage"],
                )
            next_runner = self._state(
                stage=runner["stage"],
                issues=[issue],
                material_inventory=self._pointer(
                    inventory_receipt, inventory["snapshot_sha256"]
                ),
                run_contract=self._pointer(
                    contract_receipt, inventory["snapshot_sha256"]
                ),
                next_actions=list(issue["allowed_actions"]),
                academic_inputs=runner.get("academic_inputs"),
                academic_artifacts=runner.get("academic_artifacts"),
                academic_base_artifacts=runner.get("academic_base_artifacts"),
                interaction=self._interaction_projection(
                    run_contract["configuration"], runner.get("academic_artifacts")
                ),
            )
            artifacts = [inventory_receipt, contract_receipt]
        else:
            raise ContractError(
                f"runner.resume cannot advance stage {runner['stage']}; use the listed typed action"
            )
        state = dict(task["state"])
        state["runner"] = next_runner
        return {
            "state": state,
            "status": "blocked",
            "artifacts": artifacts,
            "event_payload": {"runner_stage": next_runner["stage"]},
            "result": {
                "open_issues": [
                    item for item in next_runner["issues"] if item["status"] == "open"
                ]
            },
        }

    def _state(
        self,
        *,
        stage: str,
        issues: list[dict[str, Any]],
        material_inventory: dict[str, Any] | None,
        run_contract: dict[str, Any] | None,
        next_actions: list[str],
        academic_inputs: dict[str, Any] | None = None,
        academic_artifacts: dict[str, Any] | None = None,
        academic_base_artifacts: dict[str, Any] | None = None,
        interaction: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "contract": "paperspine5.runner-state",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "runner_version": RUNNER_VERSION,
            "product_build_id": self.expected_build_id,
            "stage": stage,
            "issues": issues,
            "material_inventory": material_inventory,
            "run_contract": run_contract,
            "academic_inputs": academic_inputs,
            "academic_artifacts": academic_artifacts,
            "academic_base_artifacts": academic_base_artifacts,
            "figure_quality": self._figure_quality_projection(academic_base_artifacts),
            "interaction": interaction
            or {
                "mode": "guided",
                "requested_scope": "local_delivery",
                "grant_status": "not_applicable",
                "grant_id": None,
                "grant_sha256": None,
                "decision_classes": [],
                "decision_receipts": [],
                "external_action_authorized": False,
            },
            "next_actions": next_actions,
            "updated_at": _now(),
            "external_action_authorized": False,
        }

    @staticmethod
    def _interaction_projection(
        configuration: dict[str, Any],
        academic_artifacts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        interaction = configuration.get("interaction")
        requested_scope = configuration.get("requested_scope", "local_delivery")
        mode = interaction.get("mode") if isinstance(interaction, dict) else "guided"
        grant = (
            interaction.get("grant")
            if isinstance(interaction, dict) and mode == "delegated_local_test"
            else None
        )
        return {
            "mode": mode,
            "requested_scope": requested_scope,
            "grant_status": "valid" if isinstance(grant, dict) else "not_applicable",
            "grant_id": grant.get("grant_id") if isinstance(grant, dict) else None,
            "grant_sha256": (
                grant.get("grant_sha256") if isinstance(grant, dict) else None
            ),
            "decision_classes": (
                list(grant.get("decision_classes", []))
                if isinstance(grant, dict)
                else []
            ),
            "decision_receipts": sorted(
                artifact_id
                for artifact_id in (academic_artifacts or {})
                if artifact_id.startswith("delegated-decision.")
            ),
            "external_action_authorized": False,
        }

    def _issue(
        self,
        task: dict[str, Any],
        *,
        revision: int,
        issue_id: str | None = None,
        code: str,
        stage: str,
        details: str,
        allowed_actions: list[str],
        severity: str = "blocker",
        nonce: str = "0",
        public_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        seed = f"{task['task_id']}|{revision}|{code}|{nonce}|{self.expected_build_id}"
        issue_id = issue_id or (
            "issue-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        )
        resume_token = "resume-" + secrets.token_urlsafe(32)
        issue = {
            "contract": "paperspine5.runner-issue",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "issue_id": issue_id,
            "task_id": task["task_id"],
            "subject": {
                "task_id": task["task_id"],
                "revision_id": str(revision),
                "issue_id": issue_id,
            },
            "code": code,
            "stage": stage,
            "severity": severity,
            "status": "open",
            "details": details,
            "allowed_actions": allowed_actions,
            "resume_token": resume_token,
            # Stable task authority, not the wall-clock time of this replayed
            # command.  This keeps a recovered run byte-identical to an
            # uninterrupted run created from the same persisted task seed.
            "created_at": task["created_at"],
            "resolved_at": None,
            "external_action_authorized": False,
        }
        if public_context:
            issue.update(deepcopy(public_context))
        return self._public_issue_projection(issue)

    @staticmethod
    def _public_issue_projection(issue: dict[str, Any]) -> dict[str, Any]:
        """Add current public contracts without mutating a legacy persisted issue."""

        result = deepcopy(issue)
        code = result.get("code")
        result["external_action_authorized"] = False
        if code == "configuration.required":
            result.update(
                {
                    "answer_tool": "paperspine5_runner_answer_issue",
                    "answer_schema": deepcopy(PUBLIC_RUN_CONFIGURATION_SCHEMA),
                    "answer_example": deepcopy(GUIDED_RUN_CONFIGURATION_EXAMPLE),
                }
            )
        elif code == "academic.input.required":
            issue_id = str(result.get("issue_id") or "")
            stage = issue_id.rsplit(":", 1)[-1]
            task_id = str(result.get("task_id") or "")
            subject = result.get("subject")
            revision_text = (
                str(subject.get("revision_id")) if isinstance(subject, dict) else ""
            )
            if not revision_text.isdigit():
                raise ContractError(
                    "academic issue public contract revision is invalid"
                )
            revision = int(revision_text)
            result.update(
                {
                    "answer_tool": "paperspine5_runner_answer_academic_stage",
                    "answer_schema": public_academic_stage_answer_schema(
                        stage=stage,
                        task_id=task_id,
                        revision=revision,
                        issue_id=issue_id,
                    ),
                    "answer_example": public_academic_stage_answer_example(
                        stage=stage,
                        task_id=task_id,
                        revision=revision,
                        issue_id=issue_id,
                    ),
                    "answer_example_note": (
                        (
                            "J7 uses figure objects with current_asset/candidate_assets exact "
                            "artifact bindings and an independent_comparison whose reviewed hashes "
                            "and selected_sha256 identify the winner. Replace every placeholder; "
                            "before create, stage each PNG/JPEG/SVG below the Runner-designated "
                            "staging subtree and call paperspine5_runner_register_figure_candidate; "
                            "JSON wrappers and caller paths are never figure assets. Create requires "
                            "decision=candidate_wins, while redesign uses "
                            "redesign_wins or an exact-original fallback. ID/winner aliases are invalid."
                        )
                        if stage == "awaiting_figure_intent"
                        else (
                            "The J4 example contains correctly recomputed source and identity "
                            "hashes for its included objects. Replace evidence values and recompute "
                            "using the two documented canonicalization algorithms before submit."
                        )
                    ),
                }
            )
        elif code == "contribution.confirmation.required":
            preparation = result.get("candidate_preparation")
            preparation_sha256 = (
                preparation.get("preparation_sha256")
                if isinstance(preparation, dict)
                else None
            )
            candidates = (
                preparation.get("candidates") if isinstance(preparation, dict) else None
            )
            subject = result.get("subject")
            revision_text = (
                str(subject.get("revision_id")) if isinstance(subject, dict) else ""
            )
            if (
                not isinstance(preparation_sha256, str)
                or not isinstance(candidates, list)
                or not revision_text.isdigit()
            ):
                raise ContractError(
                    "contribution confirmation issue lacks a valid candidate preparation"
                )
            candidate_ids = [
                str(item.get("candidate_id"))
                for item in candidates
                if isinstance(item, dict) and isinstance(item.get("candidate_id"), str)
            ]
            if len(candidate_ids) != len(candidates):
                raise ContractError(
                    "contribution confirmation issue candidate identities are invalid"
                )
            result.update(
                {
                    "answer_tool": "paperspine5_product_web_confirm_contribution",
                    "answer_schema": public_contribution_confirmation_schema(
                        task_id=str(result.get("task_id") or ""),
                        revision=int(revision_text),
                        issue_id=str(result.get("issue_id") or ""),
                        preparation_sha256=preparation_sha256,
                    ),
                    "answer_example": public_contribution_confirmation_example(
                        task_id=str(result.get("task_id") or ""),
                        revision=int(revision_text),
                        issue_id=str(result.get("issue_id") or ""),
                        preparation_sha256=preparation_sha256,
                        candidate_ids=candidate_ids,
                    ),
                    "answer_example_note": (
                        "Product Web submits only these choices. The loopback server binds "
                        "the visible authenticated session identity and confirmed_at."
                    ),
                }
            )
        return result

    def _find_open_issue(
        self, runner_state: dict[str, Any], issue_id: Any
    ) -> dict[str, Any]:
        if not isinstance(issue_id, str) or not issue_id:
            raise ContractError("issue_id must be non-empty")
        issue = next(
            (
                item
                for item in runner_state.get("issues", [])
                if item["issue_id"] == issue_id and item["status"] == "open"
            ),
            None,
        )
        if issue is None:
            raise ContractError("runner issue does not exist or is already resolved")
        return issue

    def _verify_resume_token(
        self, task: dict[str, Any], issue: dict[str, Any], resume_token: Any
    ) -> None:
        subject = issue["subject"]
        if (
            subject.get("task_id") != task["task_id"]
            or subject.get("issue_id") != issue["issue_id"]
            or subject.get("revision_id") != str(task["revision"])
        ):
            raise ContractError(
                "resume token subject is stale; resume the task to obtain a current issue token"
            )
        stored = issue.get("resume_token")
        if (
            not isinstance(resume_token, str)
            or not isinstance(stored, str)
            or not hmac.compare_digest(resume_token, stored)
        ):
            raise ContractError(
                "resume token does not match this task/revision/issue subject"
            )

    def _inventory_artifact(
        self, task: dict[str, Any], *, revision: int, command_id: str
    ) -> dict[str, Any]:
        ledger = self._scan_materials(task, revision=revision, command_id=command_id)
        validate_material_source_ledger(
            ledger,
            task_id=task["task_id"],
            revision=revision,
            build_id=self.expected_build_id,
        )
        return self._publish_artifact(
            task,
            value=ledger,
            revision=revision,
            command_id=command_id,
            artifact_id="materials.source-ledger",
            artifact_type="materials.source-ledger",
            input_hashes={
                f"material-grant:{item['grant_id']}": item["snapshot_sha256"]
                for item in ledger["grants"]
            },
            metadata={"material_snapshot_sha256": ledger["snapshot_sha256"]},
        )

    def _run_contract_artifact(
        self,
        task: dict[str, Any],
        *,
        configuration: dict[str, Any],
        inventory: dict[str, Any],
        revision: int,
        command_id: str,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        validate_configuration_material_semantics(configuration, inventory)
        contract = {
            "contract": "paperspine5.run-contract",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "task_id": task["task_id"],
            "revision_id": str(revision),
            "product_build_id": self.expected_build_id,
            "runner_version": RUNNER_VERSION,
            "material_snapshot_sha256": inventory["snapshot_sha256"],
            "configuration": configuration,
            # The run contract is a frozen semantic authority for this task,
            # not an execution receipt for the process carrying it forward.
            # Bind the first contract to the persisted task creation time and
            # preserve that exact value across every later revision/restart.
            "created_at": task["created_at"] if created_at is None else created_at,
            "external_action_authorized": False,
        }
        validate_run_contract(
            contract,
            task_id=task["task_id"],
            revision=revision,
            build_id=self.expected_build_id,
        )
        return self._publish_artifact(
            task,
            value=contract,
            revision=revision,
            command_id=command_id,
            artifact_id="runner.run-contract",
            artifact_type="runner.run-contract",
            input_hashes={"materials.source-ledger": inventory["snapshot_sha256"]},
            metadata={"material_snapshot_sha256": inventory["snapshot_sha256"]},
        )

    def _carry_run_contract_artifact(
        self,
        task: dict[str, Any],
        runner_state: dict[str, Any],
        inventory: dict[str, Any],
        *,
        revision: int,
        command_id: str,
    ) -> dict[str, Any]:
        pointer = runner_state["run_contract"]
        source = self._load_run_json(task, pointer["path"])
        configuration = validate_run_configuration(source.get("configuration"))
        return self._run_contract_artifact(
            task,
            configuration=configuration,
            inventory=inventory,
            revision=revision,
            command_id=command_id,
            created_at=source["created_at"],
        )

    def _publish_artifact(
        self,
        task: dict[str, Any],
        *,
        value: dict[str, Any],
        revision: int,
        command_id: str,
        artifact_id: str,
        artifact_type: str,
        input_hashes: dict[str, str],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        content = _json_bytes(value)
        digest = _sha256_bytes(content)
        semantic_metadata: dict[str, Any] = {}
        if artifact_id == "materials.source-ledger":
            semantic_metadata = {
                "semantic_hash_kind": "material-ledger-snapshot-v1",
                "semantic_sha256": value.get("snapshot_sha256"),
            }
        elif artifact_id == "runner.run-contract":
            semantic_metadata = {
                "semantic_hash_kind": "run-contract-authority-v1",
                "semantic_sha256": _sha256_bytes(
                    _json_bytes(
                        {
                            "contract": value.get("contract"),
                            "schema_version": value.get("schema_version"),
                            "product_build_id": value.get("product_build_id"),
                            "material_snapshot_sha256": value.get(
                                "material_snapshot_sha256"
                            ),
                            "configuration": value.get("configuration"),
                            "external_action_authorized": value.get(
                                "external_action_authorized"
                            ),
                        }
                    )
                ),
            }
        relative = (
            Path("runner")
            / "artifacts"
            / f"{artifact_id}-r{revision}-{digest[:16]}.json"
        )
        self._publish_bytes(task, relative, content, command_id=command_id)
        return {
            "contract": "paperspine5.artifact-receipt",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "receipt_id": task_scoped_artifact_receipt_id(
                task_id=task["task_id"],
                revision_id=revision,
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                content_sha256=digest,
            ),
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "path": relative.as_posix(),
            "sha256": digest,
            "size_bytes": len(content),
            "subject": {
                "task_id": task["task_id"],
                "revision_id": str(revision),
                "input_hashes": input_hashes,
            },
            "authority": {
                "kind": "product-runner",
                "producer_id": f"paperspine5.product-runner.{RUNNER_VERSION}",
            },
            "metadata": {
                **metadata,
                **semantic_metadata,
                "product_build_id": self.expected_build_id,
                "runner_version": RUNNER_VERSION,
                "filesystem_commit_policy": "ledger-recognizes-db-committed-receipt-only",
            },
            "external_action_authorized": False,
        }

    def _publish_binary_artifact(
        self,
        task: dict[str, Any],
        *,
        content: bytes,
        relative: Path,
        revision: int,
        command_id: str,
        artifact_id: str,
        artifact_type: str,
        input_hashes: dict[str, str],
        metadata: dict[str, Any],
        executor_id: str | None = "figmirror",
    ) -> dict[str, Any]:
        """Publish immutable non-JSON figure bytes under the Runner ledger."""

        digest = _sha256_bytes(content)
        self._publish_bytes(task, relative, content, command_id=command_id)
        authority = {
            "kind": "paper-spine-figure-authority",
            "producer_id": f"paperspine5.product-runner.{RUNNER_VERSION}",
        }
        if executor_id is not None:
            authority["executor_id"] = executor_id
        return {
            "contract": "paperspine5.artifact-receipt",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "receipt_id": task_scoped_artifact_receipt_id(
                task_id=task["task_id"],
                revision_id=revision,
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                content_sha256=digest,
            ),
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "path": relative.as_posix(),
            "sha256": digest,
            "size_bytes": len(content),
            "subject": {
                "task_id": task["task_id"],
                "revision_id": str(revision),
                "input_hashes": dict(sorted(input_hashes.items())),
            },
            "authority": authority,
            "metadata": {
                **metadata,
                "product_build_id": self.expected_build_id,
                "runner_version": RUNNER_VERSION,
                "filesystem_commit_policy": (
                    "ledger-recognizes-db-committed-receipt-only"
                ),
            },
            "external_action_authorized": False,
        }

    def _publish_bytes(
        self, task: dict[str, Any], relative: Path, content: bytes, *, command_id: str
    ) -> Path:
        run_root = Path(task["run_root"]).resolve()
        if relative.is_absolute() or ".." in relative.parts:
            raise ContractError("runner artifact path escapes the active run root")
        destination = run_root / relative
        stage_relative = (
            Path("runner")
            / ".staging"
            / hashlib.sha256(command_id.encode("utf-8")).hexdigest()
        )
        if stage_relative.is_absolute() or ".." in stage_relative.parts:
            raise ContractError("runner staging path escapes the active run root")
        stage_root = run_root / stage_relative
        stage_root.mkdir(parents=True, exist_ok=True)
        staging = stage_root / (
            destination.name + "." + secrets.token_hex(8) + ".pending"
        )
        staging.parent.mkdir(parents=True, exist_ok=True)
        staging.write_bytes(content)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != content:
                raise ContractError(
                    "content-addressed runner artifact path has conflicting bytes"
                )
            staging.unlink(missing_ok=True)
        else:
            try:
                os.replace(staging, destination)
            except OSError:
                if not destination.is_file() or destination.read_bytes() != content:
                    raise
                staging.unlink(missing_ok=True)
        return destination

    def _scan_materials(
        self, task: dict[str, Any], *, revision: int, command_id: str,
        selected_paths: dict[str, list[str]] | None = None, partial: bool = False
    ) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        scan_issues: list[dict[str, Any]] = []
        grant_views: list[dict[str, Any]] = []
        total_size = 0
        stopped = False
        for grant in task["material_grants"]:
            root = _validate_grant_root(grant)
            grant_entries: list[dict[str, Any]] = []
            selected = (selected_paths or {}).get(grant['grant_id'])
            selected = set(selected) if selected is not None else None
            encountered: set[str] = set()
            ignored = {'.git', '.cache', '.pytest_cache', '__pycache__', '.venv', 'node_modules'}

            def on_error(exc: OSError) -> None:
                scan_issues.append(
                    {
                        "code": "materials.read_failed",
                        "severity": "warning" if partial else "blocker",
                        "details": f"Cannot scan or copy granted materials: {exc}",
                    }
                )

            def retain_cached(relative_path: str) -> None:
                # A transient read error does not invalidate the last successfully
                # read bytes. Keep them only if still selected and hash-verified;
                # the warning explicitly distinguishes the saved copy from a reread.
                nonlocal total_size
                if not partial:
                    return
                previous = task.get('state', {}).get('host_material_inventory', {})
                saved = next((item for item in previous.get('entries', [])
                              if item['grant_id'] == grant['grant_id']
                              and item['relative_path'] == relative_path), None)
                if saved is None or len(entries) >= self.max_files:
                    return
                run_root = Path(task['run_root']).resolve()
                try:
                    cached = (run_root / saved['object_path']).resolve()
                    if (not _is_relative_to(cached, run_root) or not cached.is_file()
                            or cached.stat().st_size != saved['size_bytes']
                            or total_size + saved['size_bytes'] > self.max_total_bytes
                            or self._file_digest(cached) != saved['sha256']):
                        return
                except OSError:
                    return
                entry = dict(saved)
                entries.append(entry)
                grant_entries.append(entry)
                total_size += entry['size_bytes']
                scan_issues.append({'code': 'materials.saved_copy_retained', 'severity': 'warning',
                    'details': 'Current read failed; retained the verified last successful copy of '
                               + relative_path + '. It has not been reread from the source.'})

            for directory, dirnames, filenames in os.walk(
                root, topdown=True, onerror=on_error, followlinks=False
            ):
                directory_path = Path(directory)
                if _is_link_or_reparse(directory_path):
                    scan_issues.append(
                        {
                            "code": "materials.reparse_rejected",
                            "severity": "blocker",
                            "details": (
                                "Rejected linked/reparse directory during scan: "
                                + directory_path.relative_to(root).as_posix()
                            ),
                        }
                    )
                    dirnames[:] = []
                    continue
                safe_dirs: list[str] = []
                for dirname in sorted(dirnames):
                    candidate = directory_path / dirname
                    relative_dir = candidate.relative_to(root).as_posix()
                    if selected is not None and not any(path.startswith(relative_dir + '/') for path in selected):
                        continue
                    if partial and selected is None and (dirname in ignored or candidate.resolve() == Path(task['run_root']).resolve()):
                        continue
                    if _is_link_or_reparse(candidate):
                        scan_issues.append(
                            {
                                "code": "materials.symlink_skipped",
                                "severity": "warning",
                                "details": f"Skipped directory symlink: {candidate.relative_to(root).as_posix()}",
                            }
                        )
                    else:
                        safe_dirs.append(dirname)
                dirnames[:] = safe_dirs
                for filename in sorted(filenames):
                    source = directory_path / filename
                    relative = source.relative_to(root)
                    if selected is not None and relative.as_posix() not in selected:
                        continue
                    encountered.add(relative.as_posix())
                    if _is_link_or_reparse(source):
                        scan_issues.append(
                            {
                                "code": "materials.symlink_skipped",
                                "severity": "warning",
                                "details": f"Skipped file symlink: {relative.as_posix()}",
                            }
                        )
                        continue
                    try:
                        resolved = source.resolve()
                        if partial and _is_relative_to(resolved, root) and not resolved.is_file():
                            on_error(OSError('Selected material is not a readable file: ' + str(source)))
                            continue
                    except OSError as exc:
                        if not partial:
                            raise
                        on_error(exc)
                        retain_cached(relative.as_posix())
                        continue
                    if not _is_relative_to(resolved, root) or not resolved.is_file():
                        scan_issues.append(
                            {
                                "code": "materials.path_escape",
                                "severity": "blocker",
                                "details": f"Rejected material path outside grant: {relative.as_posix()}",
                            }
                        )
                        continue
                    if len(entries) >= self.max_files:
                        scan_issues.append(
                            {
                                "code": "materials.inventory_limit",
                                "severity": "warning" if partial else "blocker",
                                "details": f"Material file count exceeds configured limit {self.max_files}.",
                            }
                        )
                        stopped = True
                        break
                    try:
                        before = resolved.stat()
                    except OSError as exc:
                        on_error(exc)
                        retain_cached(relative.as_posix())
                        continue
                    if total_size + before.st_size > self.max_total_bytes:
                        scan_issues.append(
                            {
                                "code": "materials.inventory_limit",
                                "severity": "warning" if partial else "blocker",
                                "details": (
                                    "Material bytes exceed configured limit "
                                    f"{self.max_total_bytes}."
                                ),
                            }
                        )
                        stopped = True
                        break
                    try:
                        digest, copied_size, object_path = self._ingest_object(
                            task,
                            resolved,
                            command_id=command_id,
                            source_key=f"{grant['grant_id']}:{relative.as_posix()}",
                        )
                        after = resolved.stat()
                    except OSError as exc:
                        on_error(exc)
                        retain_cached(relative.as_posix())
                        continue
                    if (
                        before.st_size != after.st_size
                        or before.st_mtime_ns != after.st_mtime_ns
                        or copied_size != after.st_size
                    ):
                        scan_issues.append(
                            {
                                "code": "materials.changed_during_scan",
                                "severity": "warning" if partial else "blocker",
                                "details": f"Material changed during snapshot: {relative.as_posix()}",
                            }
                        )
                        if partial:
                            retain_cached(relative.as_posix())
                            continue
                    source_id = (
                        "source-"
                        + hashlib.sha256(
                            f"{grant['grant_id']}|{relative.as_posix()}".encode("utf-8")
                        ).hexdigest()[:24]
                    )
                    entry = {
                        "source_id": source_id,
                        "grant_id": grant["grant_id"],
                        "relative_path": relative.as_posix(),
                        "object_path": object_path,
                        "sha256": digest,
                        "size_bytes": copied_size,
                        "media_type": mimetypes.guess_type(filename)[0]
                        or "application/octet-stream",
                        "source_mtime_ns": after.st_mtime_ns,
                    }
                    entries.append(entry)
                    grant_entries.append(entry)
                    total_size += copied_size
                if stopped:
                    break
            if selected is not None:
                for missing in sorted(selected - encountered):
                    scan_issues.append({'code': 'materials.read_failed',
                                        'severity': 'warning' if partial else 'blocker',
                                        'details': 'Selected material is unavailable: ' + str(root / missing)})
                    retain_cached(missing)
            grant_entries.sort(key=lambda item: item["relative_path"])
            grant_snapshot = _sha256_bytes(
                _json_bytes(
                    [
                        {
                            "relative_path": item["relative_path"],
                            "sha256": item["sha256"],
                            "size_bytes": item["size_bytes"],
                        }
                        for item in grant_entries
                    ]
                )
            )
            grant_views.append(
                {
                    "grant_id": grant["grant_id"],
                    "root": str(root),
                    "read_only": True,
                    "snapshot_sha256": grant_snapshot,
                }
            )
            _validate_grant_root(grant)
            if stopped:
                break
        entries.sort(key=lambda item: (item["grant_id"], item["relative_path"]))
        snapshot = _sha256_bytes(
            _json_bytes(
                [
                    {
                        "source_id": item["source_id"],
                        "grant_id": item["grant_id"],
                        "relative_path": item["relative_path"],
                        "sha256": item["sha256"],
                        "size_bytes": item["size_bytes"],
                    }
                    for item in entries
                ]
            )
        )
        return {
            "contract": "paperspine5.material-source-ledger",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "task_id": task["task_id"],
            "revision_id": str(revision),
            "product_build_id": self.expected_build_id,
            "runner_version": RUNNER_VERSION,
            # Inventory bytes are a material snapshot.  They must not change
            # merely because a process restarted between identical scans.
            "generated_at": task["created_at"],
            "grants": grant_views,
            "entries": entries,
            "source_count": len(entries),
            "total_size_bytes": total_size,
            "snapshot_sha256": snapshot,
            "scan_issues": scan_issues,
            "privacy": {
                "materials_read_only": True,
                "copied_to_task_run_root": True,
                "external_transfer_authorized": False,
            },
        }

    def _ingest_object(
        self,
        task: dict[str, Any],
        source: Path,
        *,
        command_id: str,
        source_key: str,
    ) -> tuple[str, int, str]:
        run_root = Path(task["run_root"]).resolve()
        stage_root = (
            run_root
            / "runner"
            / ".staging"
            / hashlib.sha256(command_id.encode("utf-8")).hexdigest()
            / "objects"
        )
        stage_root.mkdir(parents=True, exist_ok=True)
        staging = stage_root / (
            hashlib.sha256(source_key.encode("utf-8")).hexdigest()
            + "."
            + secrets.token_hex(8)
            + ".pending"
        )
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as input_stream, staging.open("wb") as output_stream:
            for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
                output_stream.write(chunk)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        hexdigest = digest.hexdigest()
        relative = Path("runner") / "materials" / "objects" / hexdigest[:2] / hexdigest
        if relative.is_absolute() or ".." in relative.parts:
            raise ContractError("material object path escapes the active run root")
        destination = run_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if (
                destination.stat().st_size != size
                or self._file_digest(destination) != hexdigest
            ):
                raise ContractError(
                    "content-addressed material object has conflicting bytes"
                )
            staging.unlink(missing_ok=True)
        else:
            try:
                os.replace(staging, destination)
            except OSError:
                if (
                    not destination.is_file()
                    or destination.stat().st_size != size
                    or self._file_digest(destination) != hexdigest
                ):
                    raise
                staging.unlink(missing_ok=True)
        return hexdigest, size, relative.as_posix()

    @staticmethod
    def _file_digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _read_inventory_receipt(
        self,
        task: dict[str, Any],
        receipt: Any,
        revision: int,
        *,
        build_id: str | None = None,
        runner_version: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(receipt, dict):
            raise ContractError("runner command requires a material inventory receipt")
        receipt = self._validate_runner_receipt(
            task,
            receipt,
            revision=revision,
            artifact_id="materials.source-ledger",
            artifact_type="materials.source-ledger",
            build_id=build_id,
            runner_version=runner_version,
        )
        payload = self._read_receipt_json(task, receipt)
        ledger = validate_material_source_ledger(
            payload,
            task_id=task["task_id"],
            revision=revision,
            build_id=build_id or self.expected_build_id,
        )
        grants = {item["grant_id"]: item for item in task["material_grants"]}
        if set(grants) != {item.get("grant_id") for item in ledger["grants"]}:
            raise ContractError(
                "material inventory grants do not match the task capability ledger"
            )
        live_roots = {
            grant_id: _validate_grant_root(grant) for grant_id, grant in grants.items()
        }
        live_entries: dict[tuple[str, str], tuple[str, int]] = {}
        for grant_id, root in live_roots.items():
            for directory, dirnames, filenames in os.walk(
                root, topdown=True, followlinks=False
            ):
                directory_path = Path(directory)
                if _is_link_or_reparse(directory_path):
                    raise ContractError(
                        "material inventory contains a linked/reparse directory"
                    )
                dirnames[:] = [
                    name
                    for name in sorted(dirnames)
                    if not _is_link_or_reparse(directory_path / name)
                ]
                for filename in sorted(filenames):
                    source = directory_path / filename
                    if _is_link_or_reparse(source) or not source.is_file():
                        continue
                    relative = source.relative_to(root).as_posix()
                    live_entries[(grant_id, relative)] = (
                        self._file_digest(source),
                        source.stat().st_size,
                    )
        asserted_entries: set[tuple[str, str]] = set()
        run_root = Path(task["run_root"]).resolve()
        grant_digests: dict[str, str] = {}
        for grant_view in ledger["grants"]:
            grant_id = grant_view["grant_id"]
            root = live_roots[grant_id]
            if Path(grant_view.get("root", "")) != root:
                raise ContractError(
                    "material inventory grant canonical target does not match"
                )
            items = sorted(
                (item for item in ledger["entries"] if item["grant_id"] == grant_id),
                key=lambda item: item["relative_path"],
            )
            for item in items:
                relative = Path(item["relative_path"])
                source = root / relative
                cursor = root
                for part in relative.parts:
                    cursor = cursor / part
                    if _is_link_or_reparse(cursor):
                        raise ContractError(
                            "material inventory source traverses a link/reparse point"
                        )
                if not source.is_file() or not _is_relative_to(source.resolve(), root):
                    raise ContractError(
                        "material inventory source is missing or outside its grant"
                    )
                expected_source_id = (
                    "source-"
                    + hashlib.sha256(
                        f"{grant_id}|{relative.as_posix()}".encode("utf-8")
                    ).hexdigest()[:24]
                )
                expected_object = (
                    Path("runner")
                    / "materials"
                    / "objects"
                    / item["sha256"][:2]
                    / item["sha256"]
                ).as_posix()
                if (
                    item["source_id"] != expected_source_id
                    or item["object_path"] != expected_object
                ):
                    raise ContractError(
                        "material inventory source/object identity is not canonical"
                    )
                object_path = (run_root / item["object_path"]).resolve()
                if (
                    not _is_relative_to(object_path, run_root)
                    or _is_link_or_reparse(object_path)
                    or not object_path.is_file()
                ):
                    raise ContractError(
                        "material inventory object is missing or outside run_root"
                    )
                live_digest, live_size = live_entries.get(
                    (grant_id, relative.as_posix()), (None, None)
                )
                if (
                    live_digest != item["sha256"]
                    or live_size != item["size_bytes"]
                    or self._file_digest(object_path) != item["sha256"]
                    or object_path.stat().st_size != item["size_bytes"]
                ):
                    raise ContractError(
                        "material inventory bytes are stale or do not match receipts"
                    )
                asserted_entries.add((grant_id, relative.as_posix()))
            grant_digest = _sha256_bytes(
                _json_bytes(
                    [
                        {
                            "relative_path": item["relative_path"],
                            "sha256": item["sha256"],
                            "size_bytes": item["size_bytes"],
                        }
                        for item in items
                    ]
                )
            )
            if grant_view["snapshot_sha256"] != grant_digest:
                raise ContractError(
                    "material inventory grant snapshot digest does not recompute"
                )
            grant_digests[grant_id] = grant_digest
        if not any(item.get("severity") == "blocker" for item in ledger["scan_issues"]):
            if asserted_entries != set(live_entries):
                raise ContractError(
                    "material inventory omits or invents live granted files"
                )
        sorted_entries = sorted(
            ledger["entries"],
            key=lambda item: (item["grant_id"], item["relative_path"]),
        )
        snapshot = _sha256_bytes(
            _json_bytes(
                [
                    {
                        "source_id": item["source_id"],
                        "grant_id": item["grant_id"],
                        "relative_path": item["relative_path"],
                        "sha256": item["sha256"],
                        "size_bytes": item["size_bytes"],
                    }
                    for item in sorted_entries
                ]
            )
        )
        expected_inputs = {
            f"material-grant:{grant_id}": digest
            for grant_id, digest in grant_digests.items()
        }
        if (
            ledger["snapshot_sha256"] != snapshot
            or receipt["subject"]["input_hashes"] != expected_inputs
            or receipt["metadata"].get("material_snapshot_sha256") != snapshot
        ):
            raise ContractError(
                "material inventory global snapshot binding does not recompute"
            )
        return ledger

    def _material_figure_set(
        self,
        task: dict[str, Any],
        inventory: dict[str, Any],
        *,
        semantic_resolution_requests: Any = None,
    ) -> dict[str, Any]:
        """Derive active manuscript figures without rewriting or projecting materials.

        A material root may contain a journal manuscript, template documentation and
        detached TeX fragments at the same time.  Full-document selection therefore
        uses scientific structure rather than ``documentclass`` alone.  A detached,
        sectioned scientific fragment is never silently promoted or discarded: the
        current host must submit a task/snapshot/source/hash-bound typed resolution,
        which this method verifies against the immutable ledger bytes.
        """

        entries = {
            str(item["relative_path"]): item
            for item in inventory.get("entries", [])
            if isinstance(item, dict)
        }
        tex_paths = sorted(path for path in entries if path.lower().endswith(".tex"))
        run_root = Path(task["run_root"]).resolve()

        def read_tex(relative_path: str) -> str:
            entry = entries[relative_path]
            object_path = (run_root / str(entry["object_path"])).resolve()
            if not _is_relative_to(object_path, run_root) or not object_path.is_file():
                raise ContractError(
                    "material figure profile source escapes the immutable run root"
                )
            if object_path.stat().st_size != entry["size_bytes"]:
                raise ContractError("material figure profile source size changed")
            try:
                return object_path.read_text(encoding="utf-8-sig")
            except UnicodeError as exc:
                raise ContractError(
                    f"material TeX source is not valid UTF-8: {relative_path}"
                ) from exc

        blockers: list[dict[str, str]] = []
        figures: dict[str, dict[str, Any]] = {}
        visited: set[str] = set()

        def resolve_entry(
            owner: str, raw_target: str, suffixes: tuple[str, ...]
        ) -> str | None:
            owner_relative = _material_relative(owner, raw_target)
            root_relative = _material_relative("ledger-root.tex", raw_target)
            candidates: list[str] = []
            for relative in (owner_relative, root_relative):
                if relative is None or relative in candidates:
                    continue
                candidates.append(relative)
                if not posixpath.splitext(relative)[1]:
                    candidates.extend(
                        candidate
                        for suffix in suffixes
                        if (candidate := relative + suffix) not in candidates
                    )
            return next(
                (candidate for candidate in candidates if candidate in entries), None
            )

        def tex_facts(relative_path: str) -> dict[str, Any]:
            active = _without_tex_comments(read_tex(relative_path))
            headings = [
                {
                    "level": match.group(1).lower(),
                    "title": re.sub(r"\s+", " ", match.group(2)).strip(),
                }
                for match in re.finditer(
                    r"\\(section|subsection|subsubsection)\*?\s*\{([^{}]+)\}",
                    active,
                    re.IGNORECASE,
                )
            ]
            heading_text = " | ".join(item["title"] for item in headings).lower()
            resolved_figures: list[str] = []
            unresolved_figures: list[str] = []
            for raw_target in _TEX_INCLUDEGRAPHICS.findall(active):
                dependency = resolve_entry(relative_path, raw_target, _FIGURE_SUFFIXES)
                if dependency is None:
                    unresolved_figures.append(raw_target.strip())
                elif dependency not in resolved_figures:
                    resolved_figures.append(dependency)
            signals = []
            if re.search(r"\\begin\s*\{abstract\}", active, re.IGNORECASE):
                signals.append("abstract")
            if re.search(r"\bmethods?\b", heading_text):
                signals.append("methods")
            if re.search(r"\bresults?\b|\bfindings?\b", heading_text):
                signals.append("results")
            if re.search(r"\\(?:bibliography|addbibresource)\s*\{", active):
                signals.append("bibliography")
            if resolved_figures:
                signals.append("figures")
            has_document_class = bool(
                re.search(
                    r"\\documentclass(?:\[[^\]]*\])?\s*\{",
                    active,
                    re.IGNORECASE,
                )
            )
            has_begin_document = bool(
                re.search(r"\\begin\s*\{document\}", active, re.IGNORECASE)
            )
            has_end_document = bool(
                re.search(r"\\end\s*\{document\}", active, re.IGNORECASE)
            )
            return {
                "active": active,
                "headings": headings,
                "scientific_signals": sorted(signals),
                "has_document_class": has_document_class,
                "has_begin_document": has_begin_document,
                "has_end_document": has_end_document,
                "full_document": (
                    has_document_class and has_begin_document and has_end_document
                ),
                "resolved_figure_paths": sorted(resolved_figures),
                "unresolved_figure_tokens": sorted(set(unresolved_figures)),
                "visible_content_sha256": _sha256_bytes(active.encode("utf-8")),
                "noncomment_word_count": len(re.findall(r"\b[\w'-]+\b", active)),
            }

        facts_by_path = {path: tex_facts(path) for path in tex_paths}
        full_documents = [
            path for path in tex_paths if facts_by_path[path]["full_document"]
        ]
        exact_main = [
            path
            for path in tex_paths
            if posixpath.basename(path).lower() == "main.tex"
            and facts_by_path[path]["has_document_class"]
        ]
        scientific_documents = [
            path
            for path in full_documents
            if {"methods", "results"}.issubset(
                set(facts_by_path[path]["scientific_signals"])
            )
        ]
        primary: str | None = None
        selection_method = "none"
        if len(exact_main) == 1:
            primary = exact_main[0]
            selection_method = (
                "unique_full_main_tex"
                if facts_by_path[primary]["full_document"]
                else "unique_main_tex_documentclass"
            )
        elif len(scientific_documents) == 1:
            primary = scientific_documents[0]
            selection_method = "unique_methods_results_full_document"
        elif len(full_documents) == 1:
            primary = full_documents[0]
            selection_method = "unique_full_document"
        elif len(full_documents) > 1:
            blockers.append(
                {
                    "code": "PRIMARY_MANUSCRIPT_AMBIGUOUS",
                    "message": (
                        "multiple full TeX documents remain scientifically indistinguishable; "
                        "a primary manuscript cannot be selected from documentclass alone"
                    ),
                    "path": "|".join(full_documents),
                }
            )

        primary_candidate_paths = sorted(set(full_documents) | set(exact_main))
        primary_candidates = [
            {
                "source_id": entries[path]["source_id"],
                "relative_path": path,
                "sha256": entries[path]["sha256"],
                "scientific_signals": facts_by_path[path]["scientific_signals"],
                "selection_status": "selected" if path == primary else "rejected",
            }
            for path in primary_candidate_paths
        ]

        def visit(relative_path: str) -> None:
            if relative_path in visited:
                return
            visited.add(relative_path)
            active = _without_tex_comments(read_tex(relative_path))
            for raw_target in _TEX_INCLUDE.findall(active):
                dependency = resolve_entry(relative_path, raw_target, (".tex",))
                if dependency is None or not dependency.lower().endswith(".tex"):
                    blockers.append(
                        {
                            "code": "MANUSCRIPT_TEX_DEPENDENCY_UNRESOLVED",
                            "message": f"active TeX dependency is absent from the material ledger: {raw_target}",
                            "path": relative_path,
                        }
                    )
                    continue
                visit(dependency)
            for raw_target in _TEX_INCLUDEGRAPHICS.findall(active):
                dependency = resolve_entry(relative_path, raw_target, _FIGURE_SUFFIXES)
                if dependency is None or not dependency.lower().endswith(
                    _FIGURE_SUFFIXES
                ):
                    blockers.append(
                        {
                            "code": "MANUSCRIPT_FIGURE_DEPENDENCY_UNRESOLVED",
                            "message": f"active includegraphics target is absent from the material ledger: {raw_target}",
                            "path": relative_path,
                        }
                    )
                    continue
                entry = entries[dependency]
                existing = figures.setdefault(
                    entry["source_id"],
                    {
                        "source_id": entry["source_id"],
                        "artifact_id": f"source:{entry['source_id']}",
                        "relative_path": dependency,
                        "sha256": entry["sha256"],
                        "size_bytes": entry["size_bytes"],
                        "include_locators": [],
                    },
                )
                locator = f"{relative_path}:includegraphics:{raw_target.strip()}"
                if locator not in existing["include_locators"]:
                    existing["include_locators"].append(locator)

        if primary is not None:
            visit(primary)

        fragment_candidates: dict[str, dict[str, Any]] = {}
        for path in tex_paths:
            facts = facts_by_path[path]
            if (
                path in visited
                or facts["has_document_class"]
                or facts["has_begin_document"]
                or facts["has_end_document"]
                or not facts["headings"]
                or not facts["resolved_figure_paths"]
                or facts["noncomment_word_count"] < 50
            ):
                continue
            resolved_ids = [
                entries[figure_path]["source_id"]
                for figure_path in facts["resolved_figure_paths"]
            ]
            fragment_candidates[entries[path]["source_id"]] = {
                "source_id": entries[path]["source_id"],
                "relative_path": path,
                "sha256": entries[path]["sha256"],
                "detected_role": "unlinked_scientific_manuscript_fragment",
                "section_levels": sorted({item["level"] for item in facts["headings"]}),
                "resolved_figure_source_ids": resolved_ids,
                "visible_content_sha256": facts["visible_content_sha256"],
                "noncomment_word_count": facts["noncomment_word_count"],
            }

        requests = (
            [] if semantic_resolution_requests is None else semantic_resolution_requests
        )
        if not isinstance(requests, list):
            raise ContractError(
                "material semantic resolution requests must be an array"
            )
        expected_basis = [
            "active_section_structure",
            "resolved_scientific_figure_dependency",
            "substantive_scientific_prose",
        ]
        semantic_resolutions: list[dict[str, Any]] = []
        resolved_fragment_ids: set[str] = set()
        request_keys = {
            "contract",
            "schema_version",
            "task_id",
            "material_snapshot_sha256",
            "source_id",
            "relative_path",
            "source_sha256",
            "requested_role",
            "basis_codes",
            "resolver",
            "external_action_authorized",
            "request_sha256",
        }
        resolver_keys = {"actor_id", "actor_kind", "attestation_input_id"}
        for index, raw_request in enumerate(requests):
            if not isinstance(raw_request, dict) or set(raw_request) != request_keys:
                raise ContractError(
                    f"material semantic resolution request {index} has unknown or missing fields"
                )
            request = deepcopy(raw_request)
            expected_request_hash = _sha256_bytes(
                _canonical_json(
                    {
                        key: value
                        for key, value in request.items()
                        if key != "request_sha256"
                    }
                ).encode("utf-8")
            )
            resolver = request.get("resolver")
            if (
                request.get("contract")
                != "paperspine5.material-semantic-resolution-request"
                or request.get("schema_version") != PRODUCT_SCHEMA_VERSION
                or request.get("task_id") != task["task_id"]
                or request.get("material_snapshot_sha256")
                != inventory["snapshot_sha256"]
                or request.get("requested_role") != "main_text_fragment"
                or request.get("basis_codes") != expected_basis
                or request.get("external_action_authorized") is not False
                or request.get("request_sha256") != expected_request_hash
                or not isinstance(resolver, dict)
                or set(resolver) != resolver_keys
                or resolver.get("actor_kind") != "host_evidence_classifier"
                or not all(
                    isinstance(resolver.get(key), str) and resolver.get(key)
                    for key in resolver_keys
                )
            ):
                raise ContractError(
                    "material semantic resolution request is not current, typed, or host-bound"
                )
            source_id = str(request["source_id"])
            candidate = fragment_candidates.get(source_id)
            if (
                candidate is None
                or source_id in resolved_fragment_ids
                or request.get("relative_path") != candidate["relative_path"]
                or request.get("source_sha256") != candidate["sha256"]
            ):
                raise ContractError(
                    "material semantic resolution does not bind one current unresolved fragment"
                )
            resolution = {
                "contract": "paperspine5.material-semantic-resolution",
                "schema_version": PRODUCT_SCHEMA_VERSION,
                "task_id": task["task_id"],
                "material_snapshot_sha256": inventory["snapshot_sha256"],
                "source_id": source_id,
                "relative_path": candidate["relative_path"],
                "source_sha256": candidate["sha256"],
                "resolved_role": "main_text_fragment",
                "request": request,
                "detected_evidence": {
                    "basis_codes": expected_basis,
                    "section_levels": candidate["section_levels"],
                    "resolved_figure_source_ids": candidate[
                        "resolved_figure_source_ids"
                    ],
                    "visible_content_sha256": candidate["visible_content_sha256"],
                    "noncomment_word_count": candidate["noncomment_word_count"],
                },
                "request_sha256": request["request_sha256"],
                "external_action_authorized": False,
            }
            resolution["resolution_sha256"] = _sha256_bytes(
                _canonical_json(resolution).encode("utf-8")
            )
            semantic_resolutions.append(resolution)
            resolved_fragment_ids.add(source_id)
            visit(candidate["relative_path"])

        for source_id, candidate in sorted(fragment_candidates.items()):
            if source_id in resolved_fragment_ids:
                continue
            blockers.append(
                {
                    "code": "MANUSCRIPT_FRAGMENT_RESOLUTION_REQUIRED",
                    "message": (
                        "a detached sectioned scientific TeX fragment with resolved figure "
                        "dependencies requires a typed main-text or supplementary decision"
                    ),
                    "path": candidate["relative_path"],
                }
            )
        profile = {
            "contract": "paperspine5.material-figure-set",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "task_id": task["task_id"],
            "material_snapshot_sha256": inventory["snapshot_sha256"],
            "primary_manuscript_source_id": (
                entries[primary]["source_id"] if primary is not None else None
            ),
            "primary_manuscript_relative_path": primary,
            "primary_manuscript_sha256": (
                entries[primary]["sha256"] if primary is not None else None
            ),
            "primary_selection_method": selection_method,
            "primary_candidates": primary_candidates,
            "fragment_candidates": sorted(
                fragment_candidates.values(), key=lambda item: item["relative_path"]
            ),
            "main_text_fragment_source_ids": sorted(resolved_fragment_ids),
            "semantic_resolutions": sorted(
                semantic_resolutions, key=lambda item: item["relative_path"]
            ),
            "figure_sources": sorted(
                figures.values(), key=lambda item: item["relative_path"]
            ),
            "figure_count": len(figures),
            "blockers": blockers,
            "status": (
                "BLOCKED"
                if blockers
                else "PASS"
                if primary is not None
                else "NOT_APPLICABLE"
            ),
            "external_action_authorized": False,
        }
        profile["profile_sha256"] = hashlib.sha256(
            _canonical_json(profile).encode("utf-8")
        ).hexdigest()
        return profile

    def _read_run_contract_receipt(
        self,
        task: dict[str, Any],
        receipt: Any,
        revision: int,
        *,
        inventory: dict[str, Any] | None = None,
        configuration: dict[str, Any] | None = None,
        build_id: str | None = None,
        runner_version: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(receipt, dict):
            raise ContractError("runner command requires a run contract receipt")
        receipt = self._validate_runner_receipt(
            task,
            receipt,
            revision=revision,
            artifact_id="runner.run-contract",
            artifact_type="runner.run-contract",
            build_id=build_id,
            runner_version=runner_version,
        )
        payload = self._read_receipt_json(task, receipt)
        contract = validate_run_contract(
            payload,
            task_id=task["task_id"],
            revision=revision,
            build_id=build_id or self.expected_build_id,
        )
        if inventory is not None:
            snapshot = inventory["snapshot_sha256"]
            if (
                contract["material_snapshot_sha256"] != snapshot
                or receipt["subject"]["input_hashes"]
                != {"materials.source-ledger": snapshot}
                or receipt["metadata"].get("material_snapshot_sha256") != snapshot
            ):
                raise ContractError(
                    "run contract is not bound to the recomputed material inventory"
                )
        if configuration is not None and contract["configuration"] != configuration:
            raise ContractError(
                "run contract bytes do not materialize the submitted typed answer"
            )
        return contract

    def _validate_runner_receipt(
        self,
        task: dict[str, Any],
        receipt: dict[str, Any],
        *,
        revision: int,
        artifact_id: str,
        artifact_type: str,
        build_id: str | None = None,
        runner_version: str | None = None,
    ) -> dict[str, Any]:
        value = validate_artifact_receipt(
            receipt, task_id=task["task_id"], revision=revision
        )
        if (
            value["artifact_id"] != artifact_id
            or value["artifact_type"] != artifact_type
        ):
            raise ContractError("runner receipt artifact identity/type does not match")
        expected_runner_version = runner_version or RUNNER_VERSION
        expected_build_id = build_id or self.expected_build_id
        if value["authority"] != {
            "kind": "product-runner",
            "producer_id": f"paperspine5.product-runner.{expected_runner_version}",
        }:
            raise ContractError("runner receipt authority is not this ProductRunner")
        if (
            value.get("external_action_authorized") is not False
            or value["metadata"].get("product_build_id") != expected_build_id
            or value["metadata"].get("runner_version") != expected_runner_version
        ):
            raise ContractError(
                "runner receipt build/authority metadata does not match"
            )
        return value

    def _read_receipt_json(
        self, task: dict[str, Any], receipt: dict[str, Any]
    ) -> dict[str, Any]:
        path = Path(str(receipt.get("path", "")))
        run_root = Path(task["run_root"]).resolve()
        if not path.is_absolute():
            path = run_root / path
        path = path.resolve()
        if not _is_relative_to(path, run_root) or not path.is_file():
            raise ContractError(
                "runner receipt path must be a file within the active run root"
            )
        content = path.read_bytes()
        if _sha256_bytes(content) != receipt.get("sha256") or len(
            content
        ) != receipt.get("size_bytes"):
            raise ContractError("runner receipt does not match artifact bytes")
        try:
            payload = json.loads(content.decode("utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ContractError("runner JSON artifact is not valid UTF-8 JSON") from exc
        return payload

    def _load_run_json(self, task: dict[str, Any], raw_path: str) -> dict[str, Any]:
        path = Path(raw_path)
        run_root = Path(task["run_root"]).resolve()
        if not path.is_absolute():
            path = run_root / path
        path = path.resolve()
        if not _is_relative_to(path, run_root):
            raise ContractError(
                "runner state artifact pointer escapes the active run root"
            )
        return load_json(path)

    @staticmethod
    def _validated_academic_answer(
        answer: Any,
        *,
        task_id: str,
        revision: int,
        issue_id: str,
        stage: Any,
    ) -> dict[str, Any]:
        if not isinstance(answer, dict):
            raise ContractError("academic answer must be an object")
        findings = validate_academic_stage_answer(
            answer,
            task_id=task_id,
            revision=revision,
            current_stage=stage if isinstance(stage, str) else None,
        )
        if answer.get("issue_id") != issue_id:
            findings.append(
                {
                    "code": "ACADEMIC_ISSUE_MISMATCH",
                    "message": "answer is not bound to the selected runner issue",
                }
            )
        if findings:
            raise ContractError(
                "academic stage answer is invalid: "
                + "; ".join(
                    f"{item.get('code')}: {item.get('message')}" for item in findings
                )
            )
        try:
            return json.loads(_canonical_json(answer))
        except (TypeError, ValueError) as exc:
            raise ContractError("academic stage answer must be canonical JSON") from exc

    def _split_academic_answer_inputs(
        self, answer: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        clean = json.loads(_canonical_json(answer))
        payload = clean["payload"]
        supplied = payload.pop("input_artifacts", {})
        if not isinstance(supplied, dict):
            raise ContractError("academic payload.input_artifacts must be an object")
        reserved = {
            "materials.source-ledger",
            "materials.figure-set",
            "runner.run-contract",
            "runner.academic-inputs",
            "direction_authority",
            "target_authority",
            "contribution_boundary_decision",
            "claim_evidence",
            "canonical_manuscript",
            "final_render",
            "target_bundle",
            "readiness_verdict",
            "figure-master-authority",
        }
        normalized: dict[str, dict[str, Any]] = {}
        total_size = 0
        for artifact_id, artifact_payload in sorted(supplied.items()):
            if (
                not isinstance(artifact_id, str)
                or not artifact_id
                or len(artifact_id) > 128
                or artifact_id in reserved
                or artifact_id.startswith("publication.")
                or any(
                    character
                    not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
                    for character in artifact_id
                )
            ):
                raise ContractError(
                    f"academic input artifact identity is invalid or reserved: {artifact_id!r}"
                )
            if not isinstance(artifact_payload, dict):
                raise ContractError(
                    f"academic input artifact {artifact_id!r} must contain an actual JSON object"
                )
            encoded = _json_bytes(artifact_payload)
            total_size += len(encoded)
            if total_size > self.max_total_bytes:
                raise ContractError(
                    "academic input artifacts exceed the runner byte limit"
                )
            normalized[artifact_id] = json.loads(encoded.decode("utf-8"))
        return clean, normalized

    def _read_academic_base_artifacts(
        self,
        task: dict[str, Any],
        pointers: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        if pointers is None:
            return {}
        if not isinstance(pointers, dict):
            raise ContractError("academic base artifact pointers are invalid")
        result: dict[str, dict[str, Any]] = {}
        for artifact_id, pointer in sorted(pointers.items()):
            pointer_artifact_id = (
                pointer.get("artifact_id") if isinstance(pointer, dict) else None
            )
            semantic_artifact_id = (
                pointer.get("semantic_artifact_id", pointer_artifact_id)
                if isinstance(pointer, dict)
                else None
            )
            if (
                not isinstance(pointer, dict)
                or semantic_artifact_id != artifact_id
                or pointer.get("artifact_type") != "runner.academic-base-input"
            ):
                raise ContractError("academic base artifact pointer is invalid")
            payload = self._load_run_json(task, str(pointer.get("path") or ""))
            content = _json_bytes(payload)
            if pointer.get("sha256") != _sha256_bytes(content) or pointer.get(
                "size_bytes"
            ) != len(content):
                raise ContractError(
                    "academic base artifact bytes do not match the state pointer"
                )
            if pointer_artifact_id != artifact_id:
                if (
                    not isinstance(pointer_artifact_id, str)
                    or not pointer_artifact_id.startswith("figure-candidate-input.")
                    or payload.get("contract") != "paperspine5.figure-candidate-asset"
                    or payload.get("artifact_id") != artifact_id
                    or payload.get("external_action_authorized") is not False
                ):
                    raise ContractError(
                        "academic base artifact semantic alias is invalid"
                    )
            result[artifact_id] = payload
        return result

    def _publish_academic_base_artifact(
        self,
        task: dict[str, Any],
        artifact_id: str,
        payload: dict[str, Any],
        *,
        revision: int,
        command_id: str,
        input_hashes: dict[str, str],
        trusted_figure_master_receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        content = _json_bytes(payload)
        digest = _sha256_bytes(content)
        semantic_metadata: dict[str, Any] = {}
        receipt_artifact_id = artifact_id
        if payload.get("attestation_input_id") == artifact_id:
            from .quality_readiness import identity_provenance_sha256

            semantic_hash = identity_provenance_sha256(payload)
            if payload.get("provenance_sha256") != semantic_hash:
                raise ContractError(
                    "academic identity input provenance does not recompute"
                )
            semantic_metadata = {
                "semantic_hash_kind": "identity-provenance-v1",
                "semantic_sha256": semantic_hash,
            }
        elif (
            artifact_id == "readiness_obligations"
            and payload.get("contract") == "paperspine5.readiness-obligation-manifest"
        ):
            from .quality_readiness import canonical_sha256

            semantic_hash = canonical_sha256(
                {
                    key: value
                    for key, value in payload.items()
                    if key != "manifest_sha256"
                }
            )
            if payload.get("manifest_sha256") != semantic_hash:
                raise ContractError(
                    "readiness obligation input manifest hash does not recompute"
                )
            semantic_metadata = {
                "semantic_hash_kind": "readiness-obligation-manifest-v1",
                "semantic_sha256": semantic_hash,
            }
        elif payload.get("contract") == "paperspine5.figure-reference-plan":
            try:
                validated_plan = validate_figure_reference_plan(
                    payload,
                    trusted_actor_receipt=trusted_figure_master_receipt,
                )
            except FigureReferenceMappingError as exc:
                raise ContractError(
                    f"figure reference plan base input is invalid: {exc}"
                ) from exc
            semantic_metadata = {
                "semantic_hash_kind": "figure-reference-plan-v1",
                "semantic_sha256": validated_plan["plan_sha256"],
            }
        elif payload.get("contract") == "paperspine5.figure-candidate-asset":
            if (
                payload.get("artifact_id") != artifact_id
                or not artifact_id.startswith("figure-candidate.")
                or payload.get("external_action_authorized") is not False
            ):
                raise ContractError(
                    "figure candidate base input semantic identity is invalid"
                )
            receipt_artifact_id = (
                "figure-candidate-input."
                + hashlib.sha256(artifact_id.encode("utf-8")).hexdigest()[:32]
            )
            semantic_metadata = {
                "semantic_artifact_id": artifact_id,
                "semantic_hash_kind": "figure-candidate-input-manifest-v1",
                "semantic_sha256": digest,
            }
        token = hashlib.sha256(receipt_artifact_id.encode("utf-8")).hexdigest()[:20]
        relative = (
            Path("runner")
            / "artifacts"
            / f"academic-base-{token}-r{revision}-{digest[:16]}.json"
        )
        self._publish_bytes(task, relative, content, command_id=command_id)
        return {
            "contract": "paperspine5.artifact-receipt",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "receipt_id": task_scoped_artifact_receipt_id(
                task_id=task["task_id"],
                revision_id=revision,
                artifact_id=receipt_artifact_id,
                artifact_type="runner.academic-base-input",
                content_sha256=digest,
            ),
            "artifact_id": receipt_artifact_id,
            "artifact_type": "runner.academic-base-input",
            "path": relative.as_posix(),
            "sha256": digest,
            "size_bytes": len(content),
            "subject": {
                "task_id": task["task_id"],
                "revision_id": str(revision),
                "input_hashes": dict(sorted(input_hashes.items())),
            },
            "authority": {
                "kind": "runtime-evidence-input",
                "producer_id": f"paperspine5.product-runner.{RUNNER_VERSION}",
            },
            "metadata": {
                "product_build_id": self.expected_build_id,
                "runner_version": RUNNER_VERSION,
                "evidence_role": "actual-payload-not-trust-assertion",
                **semantic_metadata,
                "filesystem_commit_policy": (
                    "ledger-recognizes-db-committed-receipt-only"
                ),
            },
            "external_action_authorized": False,
        }

    def _read_academic_inputs(
        self,
        task: dict[str, Any],
        pointer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if pointer is None:
            return {}
        if not isinstance(pointer, dict) or (
            pointer.get("artifact_id") != "runner.academic-inputs"
            and pointer.get("artifact_type") != "runner.successor-academic-inputs"
        ):
            raise ContractError("academic input pointer is invalid")
        payload = self._load_run_json(task, str(pointer.get("path") or ""))
        content = _json_bytes(payload)
        if pointer.get("sha256") != _sha256_bytes(content) or pointer.get(
            "size_bytes"
        ) != len(content):
            raise ContractError(
                "academic cumulative input bytes do not match the state pointer"
            )
        if (
            payload.get("contract") != "paperspine5.academic-cumulative-inputs"
            or payload.get("task_id") != task["task_id"]
            or payload.get("external_action_authorized") is not False
            or not isinstance(payload.get("inputs"), dict)
        ):
            raise ContractError("academic cumulative input payload is invalid")
        return payload["inputs"]

    def _recover_prior_academic_stage_inputs(
        self,
        task: dict[str, Any],
        *,
        current_revision: int,
        current_stage: str,
    ) -> dict[str, Any]:
        """Recover same-task completed academic stages after a pointer-only restart.

        A restart can legitimately publish a fresh cumulative pointer whose
        ``stage_inputs`` is empty while earlier stage receipts remain committed
        in the ledger.  Losing those inputs makes a later J7/J8 answer look like
        a stage skip even though the research and claim evidence are still the
        same task's accepted evidence.  Recover only receipts from this task,
        strictly before the current revision, and only a ledger payload that
        contains the complete prefix required by the current stage.  The caller
        keeps the current base snapshot, so this path cannot waive a changed
        manuscript/materials baseline.
        """
        active_stages = (
            "awaiting_research",
            "awaiting_contribution",
            "awaiting_claim_graph",
            "awaiting_figure_intent",
            "awaiting_canonical",
            "awaiting_review",
            "awaiting_package",
            "target_package_ready",
        )
        try:
            current_index = active_stages.index(current_stage)
        except ValueError:
            return {}
        if current_index <= 0:
            return {}
        candidates: list[tuple[int, dict[str, Any]]] = []
        for view in self.kernel.list_artifacts(task["task_id"]):
            receipt = view.get("receipt")
            if not isinstance(receipt, dict):
                continue
            if (
                receipt.get("artifact_id") != "runner.academic-inputs"
                or receipt.get("artifact_type") != "runner.academic-inputs"
            ):
                continue
            subject = receipt.get("subject")
            if not isinstance(subject, dict) or subject.get("task_id") != task["task_id"]:
                continue
            try:
                revision = int(subject.get("revision_id"))
            except (TypeError, ValueError):
                continue
            if revision >= current_revision:
                continue
            try:
                payload = self._read_academic_inputs(task, self._academic_pointer(receipt))
            except (ContractError, OSError, ValueError, KeyError):
                continue
            stage_inputs = payload.get("stage_inputs")
            if not isinstance(stage_inputs, dict):
                continue
            required = active_stages[:current_index]
            if not all(stage in stage_inputs for stage in required):
                continue
            # Do not recover a later-stage payload: it may contain stale future
            # inputs that would be rejected as an unlicensed stage skip.
            if any(stage in stage_inputs for stage in active_stages[current_index + 1 :]):
                continue
            candidates.append((revision, payload))
        if not candidates:
            return {}
        candidates.sort(key=lambda item: item[0], reverse=True)
        return deepcopy(candidates[0][1])

    def _publish_stage_descriptor(
        self,
        task: dict[str, Any],
        descriptor: dict[str, Any],
        *,
        revision: int,
        command_id: str,
    ) -> dict[str, Any]:
        if not isinstance(descriptor, dict):
            raise ContractError("academic stage descriptor must be an object")
        artifact_id = descriptor.get("artifact_id")
        artifact_type = descriptor.get("artifact_type")
        if (
            not isinstance(artifact_id, str)
            or not artifact_id
            or any(
                character
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
                for character in artifact_id
            )
            or not isinstance(artifact_type, str)
            or not artifact_type
        ):
            raise ContractError("academic descriptor artifact identity is invalid")
        subject = descriptor.get("subject")
        if (
            not isinstance(subject, dict)
            or subject.get("task_id") != task["task_id"]
            or str(subject.get("revision_id")) != str(revision)
            or not isinstance(subject.get("input_hashes"), dict)
        ):
            raise ContractError(
                "academic descriptor is not bound to the resulting task revision"
            )
        payload = descriptor.get("payload")
        if not isinstance(payload, dict):
            raise ContractError("academic descriptor payload must be an object")
        content = _json_bytes(payload)
        digest = _sha256_bytes(content)
        if (
            descriptor.get("payload_sha256") != digest
            or descriptor.get("size_bytes") != len(content)
            or descriptor.get("external_action_authorized") is not False
        ):
            raise ContractError(
                "academic descriptor hash, size, or authorization is invalid"
            )
        authority = descriptor.get("authority")
        metadata = descriptor.get("metadata")
        if not isinstance(authority, dict) or not isinstance(metadata, dict):
            raise ContractError(
                "academic descriptor authority and metadata are required"
            )
        if metadata.get("product_build_id") != self.expected_build_id:
            raise ContractError(
                "academic descriptor is not bound to this product build"
            )
        relative = (
            Path("runner")
            / "artifacts"
            / f"{artifact_id}-r{revision}-{digest[:16]}.json"
        )
        self._publish_bytes(task, relative, content, command_id=command_id)
        return {
            "contract": "paperspine5.artifact-receipt",
            "schema_version": PRODUCT_SCHEMA_VERSION,
            "receipt_id": task_scoped_artifact_receipt_id(
                task_id=task["task_id"],
                revision_id=revision,
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                content_sha256=digest,
            ),
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "path": relative.as_posix(),
            "sha256": digest,
            "size_bytes": len(content),
            "subject": subject,
            "authority": authority,
            "metadata": {
                **metadata,
                "filesystem_commit_policy": "ledger-recognizes-db-committed-receipt-only",
            },
            "external_action_authorized": False,
        }

    @staticmethod
    def _academic_pointer(receipt: dict[str, Any]) -> dict[str, Any]:
        pointer = {
            "artifact_id": receipt["artifact_id"],
            "artifact_type": receipt["artifact_type"],
            "path": receipt["path"],
            "sha256": receipt["sha256"],
            "size_bytes": receipt["size_bytes"],
        }
        metadata = receipt.get("metadata")
        if isinstance(metadata, dict) and isinstance(
            metadata.get("semantic_artifact_id"), str
        ):
            pointer["semantic_artifact_id"] = metadata["semantic_artifact_id"]
        return pointer

    @staticmethod
    def _academic_journey_stage(stage: str) -> str:
        mapping = {
            "awaiting_research": "J4",
            "awaiting_contribution": "J5",
            "awaiting_claim_graph": "J6",
            "awaiting_figure_intent": "J7",
            "awaiting_canonical": "J8",
            "awaiting_review": "J9",
            "awaiting_package": "J10",
            "target_package_ready": "J11",
        }
        if stage not in mapping:
            raise ContractError(
                f"academic orchestrator returned an unsupported stage: {stage}"
            )
        return mapping[stage]

    @staticmethod
    def _academic_stage_details(stage: str) -> str:
        details = {
            "awaiting_research": (
                "Provide runtime-frozen direction and target research receipts. Official rules "
                "remain hard authority; exemplars remain advisory. Read the J3 research_mode: "
                "agent_decide must record the decision and basis, required must include the "
                "requested literature and/or data analysis, and materials_only must use the "
                "authorized material ledger and supplied results without starting a new search "
                "or data-mining pass, while stating the evidence limits."
            ),
            "awaiting_contribution": (
                "Confirm project contribution, motivation, evidence, counterevidence, limitation, "
                "competition and falsifiable boundary."
            ),
            "awaiting_claim_graph": (
                "Provide the reciprocal claim-evidence-result-citation-warrant-boundary-limitation graph."
            ),
            "awaiting_figure_intent": (
                "Choose zero, keep, redesign or create using exact assets and an independent comparison."
            ),
            "awaiting_canonical": (
                "Provide the current canonical source, PDF and Word revision with exact figure/body bindings."
            ),
            "awaiting_review": (
                "Provide independent review, objection-to-diff closure, final claim retention and omission evidence."
            ),
            "awaiting_package": (
                "Provide page-complete PDF/Word QA, target obligations, exact package mappings and author close."
            ),
        }
        if stage not in details:
            raise ContractError(
                f"academic stage does not accept further input: {stage}"
            )
        return details[stage]

    @staticmethod
    def _pointer(receipt: dict[str, Any], snapshot_sha256: str) -> dict[str, Any]:
        return {
            "artifact_id": receipt["artifact_id"],
            "artifact_type": receipt["artifact_type"],
            "path": receipt["path"],
            "sha256": receipt["sha256"],
            "size_bytes": receipt["size_bytes"],
            "snapshot_sha256": snapshot_sha256,
        }
