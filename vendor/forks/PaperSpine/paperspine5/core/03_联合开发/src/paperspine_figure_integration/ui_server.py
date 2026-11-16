"""Loopback-only unified review UI for the integration workflow."""

from __future__ import annotations

import json
import hashlib
import io
import mimetypes
import os
import re
import secrets
import stat
import threading
import webbrowser
import xml.etree.ElementTree as ElementTree
import zipfile
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import parse_qs, unquote, urlparse

from .contracts import ContractError
from .coordinator import IntegrationCoordinator
from .product_contracts import validate_artifact_receipt
from .product_runner_contracts import (
    validate_delegation_user_authority,
    validate_run_configuration,
)


UI_ROOT = Path(__file__).resolve().parents[2] / "ui"

_SAFE_ARTIFACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FIGURE_MEDIA_TYPES = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}

_PACKAGE_MAX_BYTES = 512 * 1024 * 1024


def _package_relative_name(value: Any) -> str:
    """Portable extraction-safe member/path, including Windows device names."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ValueError("invalid package member")
    parts = value.split("/")
    if any(character in value for character in '\\:*?"<>|') or any(ord(c) < 32 for c in value):
        raise ValueError("invalid package member")
    if any(not part or part in {".", ".."} or part.endswith((".", " "))
           or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
           for part in parts):
        raise ValueError("unsafe package member")
    return value


def _package_bytes(root: Path, relative: str, sha256: str, size: int,
                   *, maximum: int = _PACKAGE_MAX_BYTES) -> bytes:
    """Read a bounded regular file; reject links/reparse points at every level."""
    name = _package_relative_name(relative)
    if type(size) is not int or not 0 <= size <= maximum or not re.fullmatch(r"[a-f0-9]{64}", str(sha256)):
        raise ValueError("invalid package byte binding")
    path = root
    for part in (None, *name.split("/")):
        if part is not None:
            path = path / part
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked package file")
    resolved = path.resolve(strict=True)
    resolved.relative_to(root.resolve(strict=True))
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != size:
            raise ValueError("invalid package file size")
        body = stream.read(size + 1)
        after = os.fstat(stream.fileno())
    final = path.lstat()
    if (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns) != (
        after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns
    ) or (after.st_ino, after.st_dev) != (final.st_ino, final.st_dev):
        raise ValueError("package changed during read")
    if path.resolve(strict=True) != resolved or len(body) != size or hashlib.sha256(body).hexdigest() != sha256:
        raise ValueError("package bytes changed")
    return body


def _current_local_package(kernel: Any, runner: Any, task_id: str, *,
                           expected_revision: int, expected_build_id: str,
                           product_info: dict[str, Any],
                           package_revision: int | None = None) -> tuple[bytes, str]:
    """Read-only download adapter over accepted Runner/Kernel authority.

    The descriptor generation revision may precede the accepted revision. It
    is the selected ledger wrapper and target-package binding that authorize it.
    The only historical selection is the exact previous completed delivery
    pinned by a user revision request, never an arbitrary old readiness PASS.
    Nothing here compiles readiness, writes artifacts, or approves submission.
    """
    selected_revision = expected_revision if package_revision is None else package_revision

    def current():
        task = kernel.get_task(task_id)
        snapshot = runner.snapshot(task_id)
        if (not _SAFE_ARTIFACT_ID.fullmatch(task_id)
            or task.get("task_id") != task_id or snapshot.get("task_id") != task_id
            or task.get("revision") != expected_revision or snapshot.get("revision") != expected_revision
            or not expected_build_id or product_info.get("build_id") != expected_build_id
            or any(item.get("code") == "runner.successor_migration_required" for item in snapshot.get("open_issues", []))):
            raise ValueError("package task is not current")
        if package_revision is None:
            if snapshot.get("stage") != "target_package_ready":
                raise ValueError("current package is not complete")
            readiness = kernel.get_readiness(task_id)
        else:
            request = task.get("state", {}).get("user_revision_request")
            previous = request.get("previous_delivery") if isinstance(request, dict) else None
            if (not isinstance(previous, dict) or request.get("origin") != "user_feedback"
                or type(selected_revision) is not int or not 0 <= selected_revision < expected_revision
                or previous.get("revision") != selected_revision
                or type(request.get("requested_revision")) is not int
                or not selected_revision < request["requested_revision"] <= expected_revision
                or previous.get("active_run_id") != task.get("active_run_id")):
                raise ValueError("previous completed package is not pinned")
            readiness = kernel.get_readiness(task_id, revision=selected_revision)
            if not previous.get("readiness_receipt") or readiness.get("receipt") != previous["readiness_receipt"]:
                raise ValueError("previous readiness no longer matches its pinned receipt")
            # This is a read-only historical selection, not current readiness.
            snapshot = deepcopy(previous)
        if (readiness.get("task_id") != task_id or readiness.get("revision") != selected_revision
            or readiness.get("status") != "fresh" or readiness.get("delivery_ready") is not True):
            raise ValueError("package is not current and locally ready")
        return task, snapshot, readiness

    task, snapshot, readiness = current()
    workspace = Path(task["workspace_root"])
    run_root = Path(task["run_root"])
    if (not workspace.is_absolute() or not run_root.is_absolute()
        or run_root != workspace / "runs" / task["active_run_id"]
        or workspace.resolve(strict=True) != (Path(kernel.user_data_root) / "tasks" / task_id).resolve(strict=True)):
        raise ValueError("package task/run binding is invalid")
    for root_part in (workspace, workspace / "runs", run_root):
        root_info = root_part.lstat()
        if stat.S_ISLNK(root_info.st_mode) or getattr(root_info, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked task/run root")
    views = kernel.list_artifacts(task_id, subject_revision=selected_revision)

    def registered(pointer: Any, artifact_id: str, artifact_type: str) -> dict[str, Any]:
        if not isinstance(pointer, dict) or pointer.get("artifact_id") != artifact_id or pointer.get("artifact_type") != artifact_type:
            raise ValueError("package pointer is missing")
        matches = [view for view in views if view.get("receipt", {}).get("artifact_id") == artifact_id]
        if len(matches) != 1:
            raise ValueError("package receipt is missing or ambiguous")
        view = matches[0]
        receipt = validate_artifact_receipt(view["receipt"], task_id=task_id, revision=selected_revision)
        if (view.get("freshness") != "fresh" or view.get("task_id") != task_id
            or view.get("reference_revision") != selected_revision
            or receipt["artifact_type"] != artifact_type
            or any(receipt[key] != pointer.get(key) for key in ("sha256", "size_bytes"))):
            raise ValueError("package receipt is stale")
        path = run_root / _package_relative_name(pointer["path"])
        if Path(receipt["path"]).resolve(strict=True) != path.resolve(strict=True):
            raise ValueError("package receipt path mismatch")
        body = _package_bytes(run_root, pointer["path"], pointer["sha256"], pointer["size_bytes"], maximum=16 * 1024 * 1024)
        payload = json.loads(body)
        if payload != view.get("payload"):
            raise ValueError("package payload does not match ledger")
        return payload

    base_pointer = snapshot.get("academic_base_artifacts", {}).get("bundle_archive")
    package_pointer = snapshot.get("academic_artifacts", {}).get("publication.target-package")
    descriptor = registered(base_pointer, "bundle_archive", "runner.academic-base-input")
    package = registered(package_pointer, "publication.target-package", "publication.target-package-manifest")
    legacy_descriptor = (
        descriptor.get("contract") is None
        and descriptor.get("build_status") == "PASS"
        and descriptor.get("media_type") == "application/zip"
        and isinstance(descriptor.get("content_sha256"), str)
        and isinstance(descriptor.get("path"), str)
    )
    descriptor_valid = (
        descriptor.get("contract") == "paperspine5.local-package-archive"
        and descriptor.get("schema_version") == "1.0"
        and descriptor.get("artifact_id") == "bundle_archive"
        and descriptor.get("task_id") == task_id
        and descriptor.get("local_only") is True
        and descriptor.get("external_action_authorized") is False
        and re.fullmatch(r"[0-9]+", str(descriptor.get("revision_id", "")))
        and 0 <= int(descriptor["revision_id"]) <= selected_revision
    ) or legacy_descriptor
    current_artifacts = readiness.get("payload", {}).get("current_artifacts")
    descriptor_archive_sha256 = (
        descriptor.get("sha256")
        if not legacy_descriptor and isinstance(descriptor.get("sha256"), str)
        else descriptor.get("content_sha256")
    )
    current_artifacts_valid = (
        not isinstance(current_artifacts, dict)
        or (
            current_artifacts.get("bundle_archive") == descriptor_archive_sha256
            and current_artifacts.get("target_package") == package.get("manifest_sha256")
        )
    )
    archive_binding = package.get("archive_sha256") == descriptor_archive_sha256
    if legacy_descriptor:
        archive_binding = package.get("archive_sha256") in {
            base_pointer["sha256"], descriptor.get("content_sha256")
        }
    if (not descriptor_valid
        or package.get("contract") != "paperspine5.target-package-manifest" or package.get("status") != "PASS"
        or package.get("archive_artifact_id") != "bundle_archive" or not archive_binding
        or package.get("subject", {}).get("task_id") != task_id
        or package.get("subject", {}).get("revision_id") != str(selected_revision)
        or not current_artifacts_valid):
        raise ValueError("package authority binding is invalid")
    archive_sha256 = descriptor_archive_sha256
    # Runner academic inputs are stored relative to the active run, whereas
    # the older host package wrapper stored paths relative to the task root.
    # Resolve the existing path without broadening the allowed roots.
    archive_root = run_root if (run_root / descriptor["path"]).is_file() else workspace
    body = _package_bytes(archive_root, descriptor["path"], archive_sha256, descriptor["size_bytes"])
    entries = descriptor.get("entries")
    if legacy_descriptor:
        # Legacy Runner manifests bind logical artifact receipts rather than
        # ZIP member paths/hashes.  Bind the expected member count from that
        # manifest, then derive safe member records from the already hash-
        # verified ZIP bytes.
        expected_count = len([item for item in package.get("entries", []) if isinstance(item, dict)])
        with zipfile.ZipFile(io.BytesIO(body)) as probe:
            if len(probe.infolist()) != expected_count:
                raise ValueError("legacy package member count differs")
            entries = [
                {"archive_path": member.filename, "sha256": hashlib.sha256(probe.read(member)).hexdigest(), "size_bytes": member.file_size}
                for member in probe.infolist()
            ]
    if not body.startswith(b"PK\x03\x04") or not isinstance(entries, list) or not 0 < len(entries) <= 4096:
        raise ValueError("package is not a bounded ZIP")
    declared = {_package_relative_name(item["archive_path"]): item for item in entries}
    names = [name.casefold() for name in declared]
    if len(declared) != len(entries) or len(set(names)) != len(names):
        raise ValueError("duplicate package members")
    if any("/".join(name.split("/")[:i]) in names for name in names for i in range(1, len(name.split("/")))):
        raise ValueError("package file/directory collision")
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        members = archive.infolist()
        if len(members) != len(entries) or set(archive.namelist()) != set(declared) or sum(item.file_size for item in members) > 2 * _PACKAGE_MAX_BYTES:
            raise ValueError("package members differ")
        for member in members:
            entry = declared[member.filename]
            mode = stat.S_IFMT(member.external_attr >> 16)
            if member.is_dir() or mode not in {0, stat.S_IFREG} or member.flag_bits & 1 or not 0 <= member.file_size <= _PACKAGE_MAX_BYTES:
                raise ValueError("unsafe package member type")
            encoded = archive.read(member)
            if (entry.get("size_bytes") is not None and entry.get("size_bytes") != len(encoded)) or entry.get("sha256") != hashlib.sha256(encoded).hexdigest():
                raise ValueError("package member bytes differ")
            # Readme may be regenerated outside the current canonical sources;
            # all archived sources must still equal the accepted task files.
            if entry.get("role") != "local-readme" and entry.get("workspace_path"):
                source = _package_bytes(workspace, entry["workspace_path"], entry["sha256"], entry["size_bytes"])
                if source != encoded:
                    raise ValueError("package source changed")
    after_task, after_snapshot, after_readiness = current()
    if (any(after_task.get(key) != task.get(key) for key in ("active_run_id", "run_root", "workspace_root"))
        or after_snapshot.get("academic_base_artifacts", {}).get("bundle_archive") != base_pointer
        or after_snapshot.get("academic_artifacts", {}).get("publication.target-package") != package_pointer
        or (package_revision is not None and after_snapshot != snapshot)
        or after_readiness != readiness):
        raise ValueError("package changed during download preparation")
    return body, hashlib.sha256(body).hexdigest()


class ProductKernelSurface(Protocol):
    """The host-neutral subset used by the Web projection."""

    user_data_root: Path

    def create_task(
        self,
        *,
        command_id: str,
        materials_roots: tuple[str, ...] = (),
        title: str | None = None,
        description: str | None = None,
        host: str = "codex",
        task_id: str | None = None,
    ) -> Any: ...

    def list_tasks(self, status: str | None = None) -> list[Any]: ...

    def get_task(self, task_id: str) -> Any: ...

    def get_readiness(self, task_id: str, *, revision: int | None = None) -> Any: ...

    def list_artifacts(
        self,
        task_id: str,
        *,
        artifact_type: str | None = None,
        subject_revision: int | None = None,
    ) -> list[Any]: ...

    def submit_command(self, task_id: str, envelope: dict[str, Any]) -> Any: ...


class ProductRunnerSurface(Protocol):
    """Only the sealed ProductRunner facade exposed to the Web projection."""

    def snapshot(self, task_id: str) -> dict[str, Any]: ...

    def bootstrap(self, task_id: str, **kwargs: Any) -> dict[str, Any]: ...

    def add_materials(
        self, task_id: str, materials_roots: list[str], **kwargs: Any
    ) -> dict[str, Any]: ...

    def answer_issue(
        self,
        task_id: str,
        issue_id: str,
        resume_token: str,
        answer: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    def confirm_contribution(
        self,
        task_id: str,
        issue_id: str,
        resume_token: str,
        confirmation: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    def resume(self, task_id: str, **kwargs: Any) -> dict[str, Any]: ...

    def request_revision(self, task_id: str, *, feedback: str, scope: str, **kwargs: Any) -> dict[str, Any]: ...

    def register_figure_candidate(
        self, task_id: str, registration: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]: ...

    def register_final_mapping(
        self, task_id: str, registration: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]: ...

    def project_figure_reference_workspace(
        self, task_id: str, *, actor: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...

    def read_figure_reference_preview(
        self,
        task_id: str,
        descriptor_id: str,
        *,
        actor: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None: ...


class ProductWebAgentSurface(Protocol):
    """Optional isolated Agent jobs, never the default current-host route."""

    def status(self, task_id: str) -> dict[str, Any]: ...

    def start(
        self, task_id: str, *, user_message: str | None = None
    ) -> dict[str, Any]: ...


class ProductSurfaceError(ContractError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        http_status: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def _current_host_handoff(
    kernel: ProductKernelSurface,
    runner: ProductRunnerSurface,
    task_id: str,
    *,
    expected_revision: int,
    expected_build_id: str,
    product_info: dict[str, Any],
) -> dict[str, Any]:
    """Closed locator projection; prepares no answer and starts no execution.

    The output root belongs to the existing kernel, not a caller-supplied path
    or a materials grant. Private issue schemas and identities stay out.
    """
    def unavailable() -> ProductSurfaceError:
        return ProductSurfaceError(
            "当前任务状态已变化或尚不能交回宿主，请刷新当前任务后重试。",
            code="HOST_HANDOFF_NOT_CURRENT",
            http_status=HTTPStatus.CONFLICT,
        )

    task = kernel.get_task(task_id)
    snapshot = runner.snapshot(task_id)
    issues = snapshot.get("open_issues") or []
    academic = next(
        (issue for issue in issues if issue.get("code") == "academic.input.required"),
        None,
    )
    output_root = getattr(kernel, "user_data_root", None)
    if (
        not _SAFE_ARTIFACT_ID.fullmatch(task_id)
        or task.get("task_id") != task_id
        or snapshot.get("task_id") != task_id
        or task.get("revision") != expected_revision
        or snapshot.get("revision") != expected_revision
        or not expected_build_id
        or product_info.get("build_id") != expected_build_id
        or not academic
        or academic.get("answer_tool") != "paperspine5_runner_answer_academic_stage"
        or any(issue.get("code") in {
            "runner.successor_migration_required", "contribution.confirmation.required",
        } for issue in issues)
        or not isinstance(snapshot.get("stage"), str)
        or not isinstance(output_root, (str, Path))
        or not str(output_root).strip()
        or not Path(output_root).is_absolute()
    ):
        raise unavailable()
    # Explicit allowlist: do not serialize task/state/issue/product-info wholes.
    return {
        "mode": "current_host",
        "task_id": task_id,
        "revision": expected_revision,
        "stage": snapshot["stage"],
        "build_id": expected_build_id,
        "output_dir": str(output_root),
    }


def _verified_figure_media_type(path: Path, body: bytes) -> str | None:
    """Return an allow-listed media type only when bytes match the suffix."""

    suffix = path.suffix.lower()
    media_type = _FIGURE_MEDIA_TYPES.get(suffix)
    if media_type == "image/png":
        return media_type if body.startswith(b"\x89PNG\r\n\x1a\n") else None
    if media_type == "image/jpeg":
        return (
            media_type
            if len(body) >= 5
            and body[:3] == b"\xff\xd8\xff"
            and body[-2:] == b"\xff\xd9"
            else None
        )
    if media_type == "image/svg+xml":
        try:
            text = body.decode("utf-8-sig")
            if "<!DOCTYPE" in text.upper():
                return None
            root = ElementTree.fromstring(text)
        except (UnicodeError, ElementTree.ParseError):
            return None
        local_name = root.tag.rsplit("}", 1)[-1] if isinstance(root.tag, str) else ""
        return media_type if local_name == "svg" else None
    return None


def _verified_declared_figure_media_type(media_type: str, body: bytes) -> str | None:
    """Verify an allow-listed image body when no filesystem suffix is public."""

    suffix = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/svg+xml": ".svg",
    }.get(media_type)
    if suffix is None:
        return None
    return _verified_figure_media_type(Path(f"preview{suffix}"), body)


def _safe_source_locator(value: Any) -> str:
    locator = str(value or "").strip()
    if re.match(r"^(?:https?://|doi:)", locator, flags=re.IGNORECASE):
        return locator
    return "本地或受限来源（路径已隐藏）"


def _safe_reference_plan_projection(value: Any) -> dict[str, Any] | None:
    """Apply a closed Web allowlist even to an already verified plan projection."""

    if (
        not isinstance(value, dict)
        or value.get("plan_status") != "PASS"
        or value.get("external_action_authorized") is not False
        or not isinstance(value.get("figure"), dict)
        or not isinstance(value.get("references"), list)
        or not isinstance(value.get("domain_mappings"), list)
    ):
        return None
    figure = value["figure"]
    public_figure = {
        key: deepcopy(figure[key])
        for key in (
            "figure_id",
            "figure_kind",
            "publication_role",
            "panel_ids",
        )
        if key in figure
    }
    public_references: list[dict[str, Any]] = []
    for reference in value["references"]:
        if not isinstance(reference, dict):
            continue
        panels = []
        for panel in reference.get("panels", []):
            if not isinstance(panel, dict):
                continue
            panels.append(
                {
                    key: deepcopy(panel[key])
                    for key in (
                        "panel_id",
                        "bbox_normalized",
                        "layout_role",
                        "mark_type",
                        "encodings",
                        "visual_hierarchy",
                        "reading_order",
                        "transferable_features",
                        "prohibited_transfer",
                    )
                    if key in panel
                }
            )
        public_references.append(
            {
                **{
                    key: deepcopy(reference[key])
                    for key in (
                        "reference_id",
                        "source_id",
                        "figure_locator",
                        "asset_sha256",
                        "asset_sha256_short",
                        "preview_descriptor_id",
                        "preview_sha256",
                        "preview_media_type",
                    )
                    if key in reference
                },
                "source_locator": _safe_source_locator(reference.get("source_locator")),
                "panels": panels,
            }
        )
    public_mappings = []
    for mapping in value["domain_mappings"]:
        if not isinstance(mapping, dict):
            continue
        public_mappings.append(
            {
                key: deepcopy(mapping[key])
                for key in (
                    "mapping_row_id",
                    "source_kind",
                    "reference_id",
                    "reference_panel_id",
                    "current_panel_id",
                    "evidence_anchor_ids",
                    "data_bindings",
                    "semantic_transform",
                    "retained_differences",
                )
                if key in mapping
            }
        )
    story = value.get("scientific_story")
    public_story = None
    if isinstance(story, dict):
        public_story = {
            key: deepcopy(story[key])
            for key in (
                "question",
                "claim_boundary",
                "intended_conclusion",
                "hero_panel_id",
            )
            if key in story
        }
    return {
        "mapping_id": value.get("mapping_id"),
        "plan_status": "PASS",
        "figure": public_figure,
        "design_provenance": value.get("design_provenance"),
        "original_design_rationale": value.get("original_design_rationale"),
        "references": public_references,
        "scientific_story": public_story,
        "domain_mappings": public_mappings,
        "grammar_reuse_justification": value.get("grammar_reuse_justification"),
        "external_action_authorized": False,
    }


def _safe_final_mapping_projection(value: Any) -> dict[str, Any] | None:
    plan = _safe_reference_plan_projection(value)
    if plan is None or value.get("mapping_status") != "REGISTERED_VALIDATED":
        return None
    background = value.get("background", {})
    review = value.get("independent_review", {})
    if background.get("status") != "PASS" or review.get("status") != "PASS":
        return None
    return {**plan, "mapping_status": "REGISTERED_VALIDATED", "mapping_sha256": value.get("mapping_sha256"),
            "background": {key: deepcopy(background[key]) for key in ("policy", "status", "canvas", "axes", "panels") if key in background},
            "independent_review": {key: deepcopy(review[key]) for key in ("status", "decision", "rationale") if key in review},
            "publication_asset": {key: deepcopy(value.get("publication_asset", {}).get(key)) for key in ("artifact_id", "sha256")},
            "browser_visual_acceptance": "not_claimed", "external_action_authorized": False}


def _public_artifact_receipt(receipt: Any) -> dict[str, Any] | None:
    """Project only fields needed to explain or retrieve a current artifact."""

    if not isinstance(receipt, dict):
        return None
    metadata = receipt.get("metadata")
    public_metadata = {}
    if isinstance(metadata, dict):
        public_metadata = {
            key: deepcopy(metadata[key])
            for key in (
                "academic_stage",
                "figure_id",
                "candidate_id",
                "asset_role",
                "media_type",
                "content_type",
                "product_build_id",
                "runner_version",
            )
            if key in metadata
        }
    if "media_type" not in public_metadata:
        suffix = Path(str(receipt.get("path") or "")).suffix.lower()
        inferred_media_type = _FIGURE_MEDIA_TYPES.get(suffix)
        if inferred_media_type is not None:
            public_metadata["media_type"] = inferred_media_type
    subject = receipt.get("subject")
    public_subject = {}
    if isinstance(subject, dict):
        public_subject = {
            key: deepcopy(subject[key])
            for key in ("task_id", "revision_id")
            if key in subject
        }
    return {
        key: deepcopy(receipt[key])
        for key in (
            "receipt_id",
            "artifact_id",
            "artifact_type",
            "sha256",
            "size_bytes",
            "external_action_authorized",
        )
        if key in receipt
    } | {"subject": public_subject, "metadata": public_metadata}


def _public_candidate_registration_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("figure candidate registration result is invalid")
    receipt = _public_artifact_receipt(value.get("artifact_receipt"))
    candidate = value.get("candidate_asset")
    if receipt is None or not isinstance(candidate, dict):
        raise ContractError("figure candidate registration result is incomplete")
    return {
        "task_id": value.get("task_id"),
        "revision": value.get("revision"),
        "stage": value.get("stage"),
        "registration_applied": value.get("registration_applied") is True,
        "artifact_receipt": receipt,
        "candidate_asset": {
            key: deepcopy(candidate[key])
            for key in ("artifact_id", "sha256", "revision_id")
            if key in candidate
        },
        "academic_revision_advanced": value.get("academic_revision_advanced") is True,
        "external_action_authorized": False,
    }


def _public_record(value: Any) -> Any:
    """Project dataclasses and result objects into JSON without mutating them."""
    if is_dataclass(value):
        return {key: _public_record(item) for key, item in asdict(value).items()}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _public_record(to_dict())
    if isinstance(value, dict):
        return {str(key): _public_record(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_public_record(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def build_review_decision(
    snapshot: dict[str, Any],
    selections: dict[str, str],
    notes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the strict cross-project decision contract from UI selections."""
    review = snapshot.get("review") or {}
    requests = (snapshot.get("paper") or {}).get("requests") or {}
    review_figures = {
        item.get("figure_id"): item
        for item in review.get("figures", [])
        if item.get("figure_id")
    }
    figures: list[dict[str, Any]] = []
    for request in requests.get("figures", []):
        figure_id = request["figure_id"]
        if request.get("decision") == "keep":
            figures.append(
                {
                    "figure_id": figure_id,
                    "selected_candidate": "existing",
                    "panel_count": 0,
                    "layout": "existing",
                    "panel_decisions": [],
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
        comparison = review_figure.get("redesign_comparison") or {}
        if candidate_id == "existing" and request.get("decision") in {
            "redesign",
            "improve",
        }:
            figures.append(
                {
                    "figure_id": figure_id,
                    "selected_candidate": "existing",
                    "panel_count": 0,
                    "layout": "existing",
                    "panel_decisions": [],
                    "notes": (notes or {}).get(
                        figure_id, "Original selected as the fail-safe redesign result."
                    ),
                    "confirmed": True,
                    "explicit_override": True,
                    "selection_authority": "human_explicit_original",
                    "comparison_receipt": comparison.get("receipt"),
                    "fallback_reason": comparison.get("fallback_reason"),
                }
            )
            continue
        candidate = (review_figure.get("candidates") or {}).get(candidate_id)
        if not isinstance(candidate_id, str) or not isinstance(candidate, dict):
            raise ContractError(
                f"review selection is missing or invalid for {figure_id}"
            )
        panels = candidate.get("panels") or []
        panel_ids = candidate.get("panel_ids") or [
            panel.get("panel_id") for panel in panels
        ]
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
                "explicit_override": True,
                "selection_authority": "human_explicit_candidate",
                "comparison_receipt": comparison.get("receipt"),
                "fallback_reason": comparison.get("fallback_reason"),
            }
        )
    if not figures:
        raise ContractError("no figure request is available for review")
    return {
        "schema_version": "1.1",
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

        def _json(
            self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
        ) -> None:
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
                if length > 5_000_000:
                    raise ContractError("request body is too large")
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError) as exc:
                raise ContractError("request body must be a JSON object") from exc
            if not isinstance(payload, dict):
                raise ContractError("request body must be a JSON object")
            return payload

        def _discard_body(self) -> None:
            """Drain a bounded unauthorized POST so Windows does not reset it."""
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return
            if 0 < length <= 1_000_000:
                self.rfile.read(length)

        def _same_origin(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return True
            parsed = urlparse(origin)
            return (
                parsed.hostname in {"127.0.0.1", "localhost"}
                and parsed.port == self.server.server_port
            )

        def _serve(self, path: Path) -> None:
            body = path.read_bytes()
            content_type = (
                mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            )
            if content_type.startswith("text/") or content_type in {
                "application/javascript",
                "image/svg+xml",
            }:
                content_type += "; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def _serve_pdf(self) -> None:
            path = coordinator.manuscript.pdf_path.resolve()
            try:
                path.relative_to(Path(coordinator.job["project_root"]).resolve())
            except ValueError:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'inline; filename="{path.name}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route == "/api/snapshot":
                try:
                    self._json(coordinator.snapshot())
                except (
                    Exception
                ) as exc:  # HTTP boundary converts domain errors to JSON.
                    self._json(
                        {"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST
                    )
                return
            if route == "/api/body-contract":
                try:
                    contract = coordinator.body_contract()
                    self._json(
                        contract
                        or {"status": "FAIL", "error": "body contract is unavailable"}
                    )
                except Exception as exc:
                    self._json(
                        {"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST
                    )
                return
            if route == "/api/workflow":
                try:
                    self._json(coordinator.workflow_snapshot())
                except Exception as exc:
                    self._json(
                        {"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST
                    )
                return
            if route == "/api/publication-cycle":
                try:
                    self._json(coordinator.publication_cycle_snapshot())
                except Exception as exc:
                    self._json(
                        {"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST
                    )
                return
            if route == "/api/manuscript":
                try:
                    self._json(coordinator.manuscript_snapshot())
                except Exception as exc:
                    self._json(
                        {"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST
                    )
                return
            if route == "/api/manuscript/pdf":
                self._serve_pdf()
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
                self._json(
                    {
                        "status": "FAIL",
                        "error": "cross-origin requests are not accepted",
                    },
                    HTTPStatus.FORBIDDEN,
                )
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
                    result = (
                        coordinator.resume()
                        if coordinator.state()["stage"] == "blocked"
                        else coordinator.advance()
                    )
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
                elif route == "/api/manuscript/revision":
                    result = coordinator.save_manuscript_revision(body)
                elif route == "/api/manuscript/restore":
                    result = coordinator.restore_manuscript_revision(body)
                elif route == "/api/manuscript/confirm":
                    result = coordinator.confirm_manuscript_revision(body)
                elif route == "/api/issues/resolve":
                    result = coordinator.resolve_user_input_issue(body)
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._json(result)
            except Exception as exc:  # HTTP boundary converts domain errors to JSON.
                self._json(
                    {"status": "FAIL", "error": str(exc)}, HTTPStatus.BAD_REQUEST
                )

    return Handler


def create_server(job_path: str | Path, *, port: int = 0) -> ThreadingHTTPServer:
    coordinator = IntegrationCoordinator(job_path)
    coordinator.initialize()
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(coordinator))


def make_product_handler(
    kernel: ProductKernelSurface,
    *,
    runner: ProductRunnerSurface,
    runner_writer_owner: Callable[[str], str],
    runner_writer_used: Callable[[str, str], None],
    session_token: str,
    csrf_token: str,
    web_user_identity: dict[str, str],
    product_info: dict[str, Any] | None = None,
    web_agent: ProductWebAgentSurface | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Create the Web-first landing projection over the Product Kernel API."""

    static_allowlist = {
        "/": UI_ROOT / "product.html",
        "/product.html": UI_ROOT / "product.html",
        "/product.js": UI_ROOT / "product.js",
        "/product.css": UI_ROOT / "product.css",
        "/assets/brand/paperspine-mark.svg": (
            Path(__file__).resolve().parents[3]
            / "07_发布页"
            / "assets"
            / "brand"
            / "paperspine-mark.svg"
        ),
    }
    info = dict(product_info or {})

    class ProductHandler(BaseHTTPRequestHandler):
        server_version = "PaperSpine5ProductUI/0.1"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def _host_origin(self) -> str:
            return f"http://127.0.0.1:{self.server.server_port}"

        def _valid_host(self) -> bool:
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def _valid_session(self) -> bool:
            supplied = self.headers.get("X-PaperSpine5-Session", "")
            return bool(supplied) and secrets.compare_digest(supplied, session_token)

        def _valid_write_boundary(self) -> bool:
            origin = self.headers.get("Origin")
            supplied_csrf = self.headers.get("X-PaperSpine5-CSRF", "")
            return (
                origin == self._host_origin()
                and bool(supplied_csrf)
                and secrets.compare_digest(supplied_csrf, csrf_token)
            )

        def _runner_actor(self) -> dict[str, str]:
            return {
                "actor_id": web_user_identity["principal_id"],
                "surface": "web",
                "authority_kind": "authenticated_local_user_session",
                "session_id": web_user_identity["session_id"],
                "run_id": web_user_identity["run_id"],
                "attestation_input_id": web_user_identity["attestation_input_id"],
                "provenance_sha256": web_user_identity["provenance_sha256"],
            }

        def _headers(self, content_type: str, length: int) -> None:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; "
                "script-src 'self'; connect-src 'self'; frame-src 'none'; "
                "object-src 'none'; base-uri 'none'; form-action 'self'",
            )

        def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(
                _public_record(payload), ensure_ascii=False, indent=2
            ).encode("utf-8")
            self.send_response(status)
            self._headers("application/json; charset=utf-8", len(body))
            self.end_headers()
            self.wfile.write(body)

        def _deny(
            self, message: str, status: HTTPStatus = HTTPStatus.FORBIDDEN
        ) -> None:
            self._json({"status": "FAIL", "error": message}, status)

        def _body(self) -> dict[str, Any]:
            if self.headers.get_content_type() != "application/json":
                raise ContractError("Content-Type must be application/json")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ContractError("invalid Content-Length") from exc
            if length < 0 or length > 1_000_000:
                raise ContractError("request body is too large")
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ContractError("request body must be a JSON object") from exc
            if not isinstance(payload, dict):
                raise ContractError("request body must be a JSON object")
            return payload

        def _discard_body(self) -> None:
            """Drain a bounded unauthorized POST so Windows does not reset it."""
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return
            if 0 < length <= 1_000_000:
                self.rfile.read(length)

        def _serve_static(self, path: Path) -> None:
            body = path.read_bytes()
            content_type = (
                mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            )
            if (
                content_type.startswith("text/")
                or content_type == "application/javascript"
            ):
                content_type += "; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self._headers(content_type, len(body))
            self.end_headers()
            self.wfile.write(body)

        def _serve_figure_artifact(self, task_id: str, artifact_id: str) -> None:
            """Serve one current, ledger-bound figure without accepting a path."""

            if not _SAFE_ARTIFACT_ID.fullmatch(artifact_id):
                raise ProductSurfaceError(
                    "图件资产不存在。",
                    code="FIGURE_ARTIFACT_NOT_FOUND",
                    http_status=HTTPStatus.NOT_FOUND,
                )
            try:
                task = kernel.get_task(task_id)
            except Exception as exc:
                if exc.__class__.__name__ not in {"KeyError", "TaskNotFoundError"}:
                    raise
                raise ProductSurfaceError(
                    "图件资产不存在。",
                    code="FIGURE_ARTIFACT_NOT_FOUND",
                    http_status=HTTPStatus.NOT_FOUND,
                ) from None
            if not isinstance(task, dict):
                raise ProductSurfaceError(
                    "图件资产账本无效。",
                    code="FIGURE_ARTIFACT_INTEGRITY_FAILED",
                    http_status=HTTPStatus.CONFLICT,
                )
            revision = task.get("revision")
            run_root_value = task.get("run_root")
            if (
                isinstance(revision, bool)
                or not isinstance(revision, int)
                or revision < 0
                or not isinstance(run_root_value, str)
                or not run_root_value
            ):
                raise ProductSurfaceError(
                    "图件资产账本无效。",
                    code="FIGURE_ARTIFACT_INTEGRITY_FAILED",
                    http_status=HTTPStatus.CONFLICT,
                )
            try:
                run_root = Path(run_root_value).resolve(strict=True)
            except OSError:
                raise ProductSurfaceError(
                    "图件资产当前不可用。",
                    code="FIGURE_ARTIFACT_INTEGRITY_FAILED",
                    http_status=HTTPStatus.CONFLICT,
                ) from None
            if not run_root.is_dir():
                raise ProductSurfaceError(
                    "图件资产当前不可用。",
                    code="FIGURE_ARTIFACT_INTEGRITY_FAILED",
                    http_status=HTTPStatus.CONFLICT,
                )

            views = kernel.list_artifacts(task_id, subject_revision=revision)
            matches = [
                view
                for view in views
                if isinstance(view, dict)
                and isinstance(view.get("receipt"), dict)
                and view["receipt"].get("artifact_id") == artifact_id
            ]
            if not matches:
                raise ProductSurfaceError(
                    "图件资产不存在。",
                    code="FIGURE_ARTIFACT_NOT_FOUND",
                    http_status=HTTPStatus.NOT_FOUND,
                )
            if len(matches) != 1:
                raise ProductSurfaceError(
                    "图件资产账本无效。",
                    code="FIGURE_ARTIFACT_INTEGRITY_FAILED",
                    http_status=HTTPStatus.CONFLICT,
                )
            view = matches[0]
            if (
                view.get("task_id") != task_id
                or view.get("freshness") != "fresh"
                or view.get("reference_revision") != revision
            ):
                raise ProductSurfaceError(
                    "图件资产已过期或不再属于当前修订。",
                    code="FIGURE_ARTIFACT_STALE",
                    http_status=HTTPStatus.CONFLICT,
                )
            try:
                receipt = validate_artifact_receipt(
                    view["receipt"], task_id=task_id, revision=revision
                )
                artifact_path = Path(receipt["path"])
                if not artifact_path.is_absolute():
                    artifact_path = run_root / artifact_path
                resolved_path = artifact_path.resolve(strict=True)
                resolved_path.relative_to(run_root)
                if not resolved_path.is_file():
                    raise OSError
                body = resolved_path.read_bytes()
                resolved_after_read = artifact_path.resolve(strict=True)
                resolved_after_read.relative_to(run_root)
            except (ContractError, OSError, ValueError):
                raise ProductSurfaceError(
                    "图件资产完整性校验失败。",
                    code="FIGURE_ARTIFACT_INTEGRITY_FAILED",
                    http_status=HTTPStatus.CONFLICT,
                ) from None
            actual_sha256 = hashlib.sha256(body).hexdigest()
            if (
                resolved_after_read != resolved_path
                or len(body) != receipt["size_bytes"]
                or not secrets.compare_digest(actual_sha256, receipt["sha256"])
            ):
                raise ProductSurfaceError(
                    "图件资产完整性校验失败。",
                    code="FIGURE_ARTIFACT_INTEGRITY_FAILED",
                    http_status=HTTPStatus.CONFLICT,
                )
            media_type = _verified_figure_media_type(resolved_path, body)
            if media_type is None:
                raise ProductSurfaceError(
                    "该工件不是受支持的 PNG、JPEG 或 SVG 图件。",
                    code="FIGURE_ARTIFACT_UNSUPPORTED_MEDIA_TYPE",
                    http_status=HTTPStatus.UNPROCESSABLE_ENTITY,
                )

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", media_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", f'"sha256:{actual_sha256}"')
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; img-src data:; style-src 'unsafe-inline'; "
                "object-src 'none'; frame-src 'none'; base-uri 'none'; sandbox",
            )
            self.end_headers()
            self.wfile.write(body)

        def _figure_reference_workspace(self, task_id: str) -> dict[str, Any]:
            projector = getattr(runner, "project_figure_reference_workspace", None)
            if not callable(projector):
                return {
                    "task_id": task_id,
                    "revision": None,
                    "plans": [],
                    "external_action_authorized": False,
                }
            workspace = projector(task_id, actor=self._runner_actor())
            if (
                not isinstance(workspace, dict)
                or not isinstance(workspace.get("plans"), list)
                or workspace.get("external_action_authorized") is not False
            ):
                raise ProductSurfaceError(
                    "参考图映射投影无效。",
                    code="FIGURE_REFERENCE_PROJECTION_INVALID",
                    http_status=HTTPStatus.CONFLICT,
                )
            return workspace

        def _public_artifact_views(
            self,
            task_id: str,
            views: list[Any],
            *,
            include_unlisted_plans: bool,
        ) -> list[dict[str, Any]]:
            workspace = self._figure_reference_workspace(task_id)
            projected_plans: dict[str, dict[str, Any]] = {}
            for item in workspace["plans"]:
                if not isinstance(item, dict):
                    continue
                artifact_id = item.get("artifact_id")
                projection = _safe_reference_plan_projection(item.get("plan"))
                if isinstance(artifact_id, str) and projection is not None:
                    projected_plans[artifact_id] = {
                        "binding": {
                            key: deepcopy(item[key])
                            for key in ("artifact_id", "sha256", "revision_id")
                            if key in item
                        },
                        "plan": projection,
                    }

            projected_final = {}
            for item in workspace.get("final_mappings", []):
                projection = _safe_final_mapping_projection(item.get("mapping")) if isinstance(item, dict) else None
                if projection is not None:
                    projected_final[item["artifact_id"]] = projection
            public_views: list[dict[str, Any]] = []
            represented_plans: set[str] = set()
            for raw_view in views:
                if not isinstance(raw_view, dict):
                    continue
                receipt = raw_view.get("receipt")
                public_receipt = _public_artifact_receipt(receipt)
                payload = raw_view.get("payload")
                receipt_artifact_id = (
                    receipt.get("artifact_id") if isinstance(receipt, dict) else None
                )
                current_projection_subject = raw_view.get(
                    "freshness"
                ) == "fresh" and raw_view.get("reference_revision") == workspace.get(
                    "revision"
                )
                if (
                    isinstance(payload, dict)
                    and payload.get("contract") == "paperspine5.figure-reference-plan"
                ):
                    projected = (
                        projected_plans.get(str(receipt_artifact_id or ""))
                        if current_projection_subject
                        else None
                    )
                    payload = deepcopy(projected["plan"]) if projected else None
                    if projected:
                        represented_plans.add(str(receipt_artifact_id))
                        if public_receipt is not None:
                            public_receipt["sha256"] = projected["binding"].get(
                                "sha256"
                            )
                            public_receipt["subject"] = {
                                "task_id": task_id,
                                "revision_id": projected["binding"].get("revision_id"),
                            }
                elif isinstance(payload, dict) and payload.get("contract") in {
                    "paperspine5.figure-reference-mapping", "paperspine5.figure-final-mapping-consumption"
                }:
                    payload = deepcopy(projected_final.get(receipt_artifact_id)) if current_projection_subject else None
                elif isinstance(payload, dict) and payload.get("plan_status") == "PASS":
                    payload = (
                        _safe_reference_plan_projection(payload)
                        if current_projection_subject
                        else None
                    )
                else:
                    payload = deepcopy(payload)
                public_views.append(
                    {
                        key: deepcopy(raw_view[key])
                        for key in (
                            "task_id",
                            "current_revision",
                            "reference_revision",
                            "freshness",
                        )
                        if key in raw_view
                    }
                    | {"receipt": public_receipt, "payload": payload}
                )

            for artifact_id, projected in projected_plans.items():
                if not include_unlisted_plans:
                    break
                if artifact_id in represented_plans:
                    continue
                binding = projected["binding"]
                public_views.append(
                    {
                        "task_id": task_id,
                        "current_revision": workspace.get("revision"),
                        "reference_revision": workspace.get("revision"),
                        "freshness": "fresh",
                        "receipt": {
                            "artifact_id": artifact_id,
                            "artifact_type": "figure.reference-plan-projection",
                            "sha256": binding.get("sha256"),
                            "subject": {
                                "task_id": task_id,
                                "revision_id": binding.get("revision_id"),
                            },
                            "metadata": {"asset_role": "reference_plan"},
                            "external_action_authorized": False,
                        },
                        "payload": deepcopy(projected["plan"]),
                    }
                )
            return public_views

        def _serve_reference_preview(self, task_id: str, descriptor_id: str) -> None:
            if re.fullmatch(r"[0-9a-f]{64}", descriptor_id) is None:
                raise ProductSurfaceError(
                    "参考缩略图不存在。",
                    code="FIGURE_REFERENCE_PREVIEW_NOT_FOUND",
                    http_status=HTTPStatus.NOT_FOUND,
                )
            reader = getattr(runner, "read_figure_reference_preview", None)
            if not callable(reader):
                raise ProductSurfaceError(
                    "参考缩略图不存在。",
                    code="FIGURE_REFERENCE_PREVIEW_NOT_FOUND",
                    http_status=HTTPStatus.NOT_FOUND,
                )
            try:
                preview = reader(task_id, descriptor_id, actor=self._runner_actor())
            except ContractError:
                raise ProductSurfaceError(
                    "参考缩略图已过期或完整性校验失败。",
                    code="FIGURE_REFERENCE_PREVIEW_INTEGRITY_FAILED",
                    http_status=HTTPStatus.CONFLICT,
                ) from None
            if preview is None:
                raise ProductSurfaceError(
                    "参考缩略图不存在或已随修订失效。",
                    code="FIGURE_REFERENCE_PREVIEW_NOT_FOUND",
                    http_status=HTTPStatus.NOT_FOUND,
                )
            if not isinstance(preview, dict) or not isinstance(
                preview.get("content"), bytes
            ):
                raise ProductSurfaceError(
                    "参考缩略图完整性校验失败。",
                    code="FIGURE_REFERENCE_PREVIEW_INTEGRITY_FAILED",
                    http_status=HTTPStatus.CONFLICT,
                )
            body = preview["content"]
            sha256 = hashlib.sha256(body).hexdigest()
            if preview.get("sha256") != sha256 or preview.get("size_bytes") != len(
                body
            ):
                raise ProductSurfaceError(
                    "参考缩略图完整性校验失败。",
                    code="FIGURE_REFERENCE_PREVIEW_INTEGRITY_FAILED",
                    http_status=HTTPStatus.CONFLICT,
                )
            media_type = _verified_declared_figure_media_type(
                str(preview.get("media_type") or ""), body
            )
            if media_type is None:
                raise ProductSurfaceError(
                    "参考缩略图不是受支持的 PNG、JPEG 或 SVG 图像。",
                    code="FIGURE_REFERENCE_PREVIEW_UNSUPPORTED_MEDIA_TYPE",
                    http_status=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", media_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", f'"sha256:{sha256}"')
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; img-src data:; style-src 'unsafe-inline'; "
                "object-src 'none'; frame-src 'none'; base-uri 'none'; sandbox",
            )
            self.end_headers()
            self.wfile.write(body)

        def _task_route(self, route: str) -> tuple[str | None, str | None, str | None]:
            parts = [part for part in route.split("/") if part]
            if len(parts) == 4 and parts[:3] == ["api", "v1", "tasks"]:
                return unquote(parts[3]), "task", None
            if (
                len(parts) == 5
                and parts[:3] == ["api", "v1", "tasks"]
                and parts[4]
                in {"commands", "readiness", "artifacts", "runner", "agent", "host-handoff", "local-package"}
            ):
                return unquote(parts[3]), parts[4], None
            if (
                len(parts) == 7
                and parts[:3] == ["api", "v1", "tasks"]
                and parts[4] == "artifacts"
                and parts[6] == "content"
            ):
                return unquote(parts[3]), "artifact_content", unquote(parts[5])
            if (
                len(parts) == 7
                and parts[:3] == ["api", "v1", "tasks"]
                and parts[4] == "figure-references"
                and parts[6] == "content"
            ):
                return unquote(parts[3]), "reference_content", unquote(parts[5])
            if (
                len(parts) == 6
                and parts[:3] == ["api", "v1", "tasks"]
                and parts[4] == "runner"
                and parts[5]
                in {"bootstrap", "materials", "resume", "figure-candidates", "final-mappings", "revision-request"}
            ):
                return unquote(parts[3]), f"runner_{parts[5]}", None
            if (
                len(parts) == 6
                and parts[:3] == ["api", "v1", "tasks"]
                and parts[4] == "agent"
                and parts[5] in {"start", "reply"}
            ):
                return unquote(parts[3]), f"agent_{parts[5]}", None
            if (
                len(parts) == 8
                and parts[:3] == ["api", "v1", "tasks"]
                and parts[4] == "runner"
                and parts[5] == "issues"
                and parts[7]
                in {"answer", "academic-answer", "contribution-confirmation"}
            ):
                action = {
                    "answer": "runner_answer_issue",
                    "academic-answer": "runner_answer_academic_stage",
                    "contribution-confirmation": "runner_confirm_contribution",
                }[parts[7]]
                return unquote(parts[3]), action, unquote(parts[6])
            return None, None, None

        def do_GET(self) -> None:  # noqa: N802
            if not self._valid_host():
                self._deny("invalid Host header")
                return
            parsed = urlparse(self.path)
            route = parsed.path
            static_path = static_allowlist.get(route)
            if static_path is not None:
                if not static_path.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self._serve_static(static_path)
                return
            if not route.startswith("/api/v1/"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not self._valid_session():
                self._deny("invalid or missing session token")
                return
            try:
                if route == "/api/v1/session":
                    self._json(
                        {
                            "status": "PASS",
                            "csrf_token": csrf_token,
                            "user_identity": deepcopy(web_user_identity),
                            "product": info,
                            "security": {
                                "loopback": True,
                                "host": "127.0.0.1",
                                "origin_required_for_writes": True,
                                "cache": "no-store",
                            },
                        }
                    )
                    return
                if route == "/api/v1/tasks":
                    self._json({"status": "PASS", "tasks": kernel.list_tasks()})
                    return
                task_id, action, route_subject = self._task_route(route)
                if task_id is not None and action == "local-package":
                    query = parse_qs(parsed.query, keep_blank_values=True)
                    if (set(query) not in ({"expected_revision", "expected_build_id"},
                                          {"expected_revision", "expected_build_id", "package_revision"})
                        or any(len(values) != 1 for values in query.values())
                        or not re.fullmatch(r"0|[1-9][0-9]*", query["expected_revision"][0])
                        or ("package_revision" in query and not re.fullmatch(r"0|[1-9][0-9]*", query["package_revision"][0]))):
                        raise ProductSurfaceError("请刷新当前任务后重试下载。", code="LOCAL_PACKAGE_INVALID_REQUEST")
                    revision = int(query["expected_revision"][0])
                    package_revision = int(query["package_revision"][0]) if "package_revision" in query else None
                    try:
                        body, sha256 = _current_local_package(
                            kernel, runner, task_id, expected_revision=revision,
                            expected_build_id=query["expected_build_id"][0], product_info=info,
                            package_revision=package_revision,
                        )
                    except Exception as exc:
                        # No paths, session identities, schemas or raw errors
                        # cross this ordinary-user download boundary.
                        raise ProductSurfaceError(
                            "当前修订的本地论文包尚不可下载，或文件已变化。请刷新任务后重试。",
                            code="LOCAL_PACKAGE_UNAVAILABLE", http_status=HTTPStatus.CONFLICT,
                        ) from exc
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Length", str(len(body)))
                    filename_task = re.sub(r"[^A-Za-z0-9._-]", "_", task_id)
                    selected_revision = revision if package_revision is None else package_revision
                    self.send_header("Content-Disposition", f'attachment; filename="paperspine5-{filename_task}-r{selected_revision}.zip"')
                    self.send_header("ETag", f'"sha256:{sha256}"')
                    self.send_header("X-PaperSpine5-Task", task_id)
                    self.send_header("X-PaperSpine5-Revision", str(revision))
                    self.send_header("X-PaperSpine5-Package-Revision", str(selected_revision))
                    self.send_header("Cache-Control", "no-store, max-age=0")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("Cross-Origin-Resource-Policy", "same-origin")
                    self.send_header("Content-Security-Policy", "default-src 'none'; sandbox")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if task_id is not None and action == "host-handoff":
                    query = parse_qs(parsed.query, keep_blank_values=True)
                    if set(query) != {"expected_revision", "expected_build_id"} or any(
                        len(values) != 1 for values in query.values()
                    ):
                        raise ProductSurfaceError(
                            "请刷新当前任务后重新准备宿主续作指引。",
                            code="HOST_HANDOFF_INVALID_REQUEST",
                        )
                    revision_text = query["expected_revision"][0]
                    if not re.fullmatch(r"0|[1-9][0-9]*", revision_text):
                        raise ProductSurfaceError(
                            "请刷新当前任务后重新准备宿主续作指引。",
                            code="HOST_HANDOFF_INVALID_REQUEST",
                        )
                    try:
                        handoff = _current_host_handoff(
                            kernel, runner, task_id,
                            expected_revision=int(revision_text),
                            expected_build_id=query["expected_build_id"][0],
                            product_info=info,
                        )
                    except ProductSurfaceError:
                        raise
                    except Exception as exc:
                        # Do not echo private storage/identity errors to this
                        # ordinary-user route, even for unknown tasks.
                        raise ProductSurfaceError(
                            "无法读取当前任务的宿主续作信息，请刷新任务后重试。",
                            code="HOST_HANDOFF_UNAVAILABLE",
                        ) from exc
                    self._json({"status": "PASS", "handoff": handoff})
                    return
                if task_id is not None and action == "task":
                    self._json({"status": "PASS", "task": kernel.get_task(task_id)})
                    return
                if task_id is not None and action == "readiness":
                    query = parse_qs(parsed.query, keep_blank_values=True)
                    revision_text = (query.get("revision") or [None])[0]
                    revision = None
                    if revision_text is not None:
                        try:
                            revision = int(revision_text)
                        except ValueError as exc:
                            raise ContractError(
                                "revision must be a non-negative integer"
                            ) from exc
                        if revision < 0:
                            raise ContractError(
                                "revision must be a non-negative integer"
                            )
                    self._json(
                        {
                            "status": "PASS",
                            "readiness": kernel.get_readiness(
                                task_id, revision=revision
                            ),
                        }
                    )
                    return
                if task_id is not None and action == "artifacts":
                    query = parse_qs(parsed.query, keep_blank_values=True)
                    artifact_type = (query.get("artifact_type") or [None])[0]
                    revision_text = (query.get("revision") or [None])[0]
                    subject_revision = None
                    if revision_text is not None:
                        try:
                            subject_revision = int(revision_text)
                        except ValueError as exc:
                            raise ContractError(
                                "revision must be a non-negative integer"
                            ) from exc
                        if subject_revision < 0:
                            raise ContractError(
                                "revision must be a non-negative integer"
                            )
                    views = kernel.list_artifacts(
                        task_id,
                        artifact_type=artifact_type,
                        subject_revision=subject_revision,
                    )
                    self._json(
                        {
                            "status": "PASS",
                            "artifacts": self._public_artifact_views(
                                task_id,
                                views,
                                include_unlisted_plans=(
                                    artifact_type is None and subject_revision is None
                                ),
                            ),
                        }
                    )
                    return
                if task_id is not None and action == "artifact_content":
                    if parsed.query:
                        raise ProductSurfaceError(
                            "图件资产不存在。",
                            code="FIGURE_ARTIFACT_NOT_FOUND",
                            http_status=HTTPStatus.NOT_FOUND,
                        )
                    assert route_subject is not None
                    self._serve_figure_artifact(task_id, route_subject)
                    return
                if task_id is not None and action == "reference_content":
                    if parsed.query:
                        raise ProductSurfaceError(
                            "参考缩略图不存在。",
                            code="FIGURE_REFERENCE_PREVIEW_NOT_FOUND",
                            http_status=HTTPStatus.NOT_FOUND,
                        )
                    assert route_subject is not None
                    self._serve_reference_preview(task_id, route_subject)
                    return
                if task_id is not None and action == "runner":
                    self._json({"status": "PASS", "snapshot": runner.snapshot(task_id)})
                    return
                if task_id is not None and action == "agent":
                    if web_agent is None:
                        raise ProductSurfaceError(
                            "本地 Agent 作业层不可用。",
                            code="WEB_AGENT_UNAVAILABLE",
                        )
                    self._json({"status": "PASS", "agent": web_agent.status(task_id)})
                    return
                self.send_error(HTTPStatus.NOT_FOUND)
            except Exception as exc:
                self._json(
                    {
                        "status": "FAIL",
                        "error_code": getattr(exc, "code", "PRODUCT_WEB_ERROR"),
                        "error": str(exc),
                        "external_action_authorized": False,
                    },
                    getattr(exc, "http_status", HTTPStatus.BAD_REQUEST),
                )

        def do_POST(self) -> None:  # noqa: N802
            if not self._valid_host():
                self._discard_body()
                self._deny("invalid Host header")
                return
            if not self._valid_session():
                self._discard_body()
                self._deny("invalid or missing session token")
                return
            if not self._valid_write_boundary():
                self._discard_body()
                self._deny("Origin or CSRF token is invalid")
                return
            route = urlparse(self.path).path
            action = None
            try:
                body = self._body()
                if route == "/api/v1/tasks":
                    materials = body.get("materials_roots") or []
                    if not isinstance(materials, list) or not all(
                        isinstance(item, str) and item.strip() for item in materials
                    ):
                        raise ContractError(
                            "materials_roots must be an array of non-empty paths"
                        )
                    create_kwargs = {
                        "command_id": body.get("command_id"),
                        "materials_roots": tuple(materials),
                        "title": body.get("title"),
                        "host": body.get("host", "codex"),
                        "task_id": body.get("task_id"),
                    }
                    if body.get("description") is not None:
                        create_kwargs["description"] = body.get("description")
                    result = kernel.create_task(**create_kwargs)
                    self._json(
                        {"status": "CREATED", "task": result}, HTTPStatus.CREATED
                    )
                    return
                task_id, action, issue_id = self._task_route(route)
                if task_id is not None and action in {"agent_start", "agent_reply"}:
                    if web_agent is None:
                        raise ProductSurfaceError(
                            "本地 Agent 作业层不可用。",
                            code="WEB_AGENT_UNAVAILABLE",
                        )
                    user_message = (
                        body.get("user_message") if action == "agent_reply" else None
                    )
                    if action == "agent_reply" and not isinstance(user_message, str):
                        raise ProductSurfaceError(
                            "user_message is required",
                            code="WEB_AGENT_INPUT_INVALID",
                        )
                    result = web_agent.start(task_id, user_message=user_message)
                    self._json(
                        {"status": "ACCEPTED", "agent": result}, HTTPStatus.ACCEPTED
                    )
                    return
                if task_id is not None and action == "commands":
                    envelope = body.get("envelope", body)
                    if not isinstance(envelope, dict):
                        raise ContractError("command envelope must be a JSON object")
                    command_type = envelope.get("command_type")
                    if isinstance(command_type, str) and command_type.startswith(
                        "runner."
                    ):
                        raise ProductSurfaceError(
                            "runner.* commands must use the ProductRunner Web facade",
                            code="RUNNER_FACADE_REQUIRED",
                        )
                    if "writer_id" in envelope:
                        raise ProductSurfaceError(
                            "writer_id is runtime-owned and cannot be supplied in a command envelope",
                            code="COMMAND_WRITER_SPOOFED",
                        )
                    writer_id = runner_writer_owner(task_id)
                    if not isinstance(writer_id, str) or not writer_id:
                        raise ProductSurfaceError(
                            "runtime writer owner is unavailable",
                            code="RUNNER_WRITER_OWNER_UNAVAILABLE",
                        )
                    result = kernel.submit_command(
                        task_id, {**envelope, "writer_id": writer_id}
                    )
                    runner_writer_used(task_id, writer_id)
                    self._json({"status": "COMMITTED", "result": result})
                    return
                if task_id is not None and action and action.startswith("runner_"):
                    if "writer_id" in body:
                        raise ProductSurfaceError(
                            "writer_id is runtime-owned and cannot be supplied by the browser",
                            code="RUNNER_WRITER_SPOOFED",
                        )
                    command_id = body.get("command_id")
                    expected_revision = body.get("expected_revision")
                    actor = self._runner_actor()
                    if not isinstance(command_id, str) or not command_id:
                        raise ProductSurfaceError(
                            "command_id is required", code="RUNNER_INPUT_INVALID"
                        )
                    if (
                        isinstance(expected_revision, bool)
                        or not isinstance(expected_revision, int)
                        or expected_revision < 0
                    ):
                        raise ProductSurfaceError(
                            "expected_revision must be a non-negative integer",
                            code="RUNNER_INPUT_INVALID",
                        )
                    writer_id = runner_writer_owner(task_id)
                    if not isinstance(writer_id, str) or not writer_id:
                        raise ProductSurfaceError(
                            "runtime writer owner is unavailable",
                            code="RUNNER_WRITER_OWNER_UNAVAILABLE",
                        )
                    common = {
                        "command_id": command_id,
                        "expected_revision": expected_revision,
                        "writer_id": writer_id,
                        "actor": actor,
                    }
                    if action == "runner_revision-request":
                        if (urlparse(self.path).query
                            or set(body) - {"command_id", "expected_revision", "expected_build_id", "actor", "feedback", "scope"}
                            or not isinstance(body.get("feedback"), str)
                            or not body["feedback"].strip() or len(body["feedback"]) > 8000
                            or body.get("scope") not in {"manuscript", "figures", "figure_mapping"}):
                            raise ProductSurfaceError("请填写修改意见并选择修改范围。", code="REVISION_REQUEST_INVALID")
                        task = kernel.get_task(task_id)
                        snapshot = runner.snapshot(task_id)
                        if (body.get("expected_build_id") != info.get("build_id")
                            or not body.get("expected_build_id")
                            or task.get("task_id") != task_id or snapshot.get("task_id") != task_id
                            or task.get("revision") != expected_revision or snapshot.get("revision") != expected_revision
                            or snapshot.get("stage") != "target_package_ready"
                            or any(item.get("code") == "runner.successor_migration_required" for item in snapshot.get("open_issues", []))):
                            raise ProductSurfaceError("任务已变化，请刷新后重新提交修改意见。",
                                                      code="REVISION_REQUEST_NOT_CURRENT", http_status=HTTPStatus.CONFLICT)
                        result = runner.request_revision(task_id, feedback=body["feedback"], scope=body["scope"], **common)
                    elif action == "runner_bootstrap":
                        result = runner.bootstrap(task_id, **common)
                    elif action == "runner_materials":
                        roots = body.get("materials_roots")
                        if (
                            not isinstance(roots, list)
                            or not roots
                            or not all(isinstance(item, str) and item for item in roots)
                        ):
                            raise ProductSurfaceError(
                                "materials_roots must be a non-empty array of paths",
                                code="RUNNER_INPUT_INVALID",
                            )
                        result = runner.add_materials(task_id, roots, **common)
                    elif action == "runner_final-mappings":
                        registration = body.get("registration")
                        if not isinstance(registration, dict):
                            raise ProductSurfaceError("registration must be an object", code="RUNNER_INPUT_INVALID")
                        result = runner.register_final_mapping(task_id, registration, **common)
                        runner_writer_used(task_id, writer_id)
                        self._json({"status": "COMMITTED", "result": {
                            key: result.get(key) for key in ("task_id", "revision", "stage", "registration_applied",
                                "academic_revision_advanced", "mapping_sha256", "consumption_sha256", "external_action_authorized")}})
                        return
                    elif action == "runner_figure-candidates":
                        registration = body.get("registration")
                        if not isinstance(registration, dict):
                            raise ProductSurfaceError(
                                "registration must be an object",
                                code="RUNNER_INPUT_INVALID",
                            )
                        result = runner.register_figure_candidate(
                            task_id,
                            registration,
                            **common,
                        )
                        runner_writer_used(task_id, writer_id)
                        self._json(
                            {
                                "status": "COMMITTED",
                                "result": _public_candidate_registration_result(result),
                            }
                        )
                        return
                    elif action in {
                        "runner_answer_issue",
                        "runner_answer_academic_stage",
                    }:
                        if not isinstance(issue_id, str) or not issue_id:
                            raise ProductSurfaceError(
                                "issue_id is required", code="RUNNER_INPUT_INVALID"
                            )
                        token = body.get("resume_token")
                        answer = body.get("answer")
                        if not isinstance(token, str) or not token:
                            raise ProductSurfaceError(
                                "resume_token is required", code="RUNNER_INPUT_INVALID"
                            )
                        if not isinstance(answer, dict):
                            raise ProductSurfaceError(
                                "answer must be an object", code="RUNNER_INPUT_INVALID"
                            )
                        if (
                            action == "runner_answer_academic_stage"
                            and answer.get("contract")
                            != "paperspine5.academic-stage-answer"
                        ):
                            raise ProductSurfaceError(
                                "answer must use the paperspine5.academic-stage-answer contract",
                                code="RUNNER_ACADEMIC_ANSWER_REQUIRED",
                            )
                        interaction = answer.get("interaction")
                        if (
                            action == "runner_answer_issue"
                            and isinstance(interaction, dict)
                            and interaction.get("mode") == "delegated_local_test"
                        ):
                            grant = interaction.get("grant")
                            if not isinstance(grant, dict) or not isinstance(
                                grant.get("grant_sha256"), str
                            ):
                                raise ProductSurfaceError(
                                    "Web local delegation must include its canonical grant_sha256",
                                    code="LOCAL_DELEGATION_GRANT_HASH_REQUIRED",
                                )
                            try:
                                answer = validate_run_configuration(answer)
                                validate_delegation_user_authority(answer, actor)
                            except ContractError as exc:
                                raise ProductSurfaceError(
                                    str(exc),
                                    code="LOCAL_DELEGATION_GRANT_INVALID",
                                ) from exc
                        result = runner.answer_issue(
                            task_id, issue_id, token, answer, **common
                        )
                    elif action == "runner_confirm_contribution":
                        if not isinstance(issue_id, str) or not issue_id:
                            raise ProductSurfaceError(
                                "issue_id is required", code="RUNNER_INPUT_INVALID"
                            )
                        token = body.get("resume_token")
                        confirmation = body.get("confirmation")
                        if not isinstance(token, str) or not token:
                            raise ProductSurfaceError(
                                "resume_token is required", code="RUNNER_INPUT_INVALID"
                            )
                        if not isinstance(confirmation, dict):
                            raise ProductSurfaceError(
                                "confirmation must be an object",
                                code="RUNNER_INPUT_INVALID",
                            )
                        result = runner.confirm_contribution(
                            task_id,
                            issue_id,
                            token,
                            confirmation,
                            author_identity=deepcopy(web_user_identity),
                            **common,
                        )
                    elif action == "runner_resume":
                        result = runner.resume(task_id, **common)
                    else:  # pragma: no cover - route parser is closed.
                        raise ProductSurfaceError(
                            "unsupported runner route", code="RUNNER_ACTION_INVALID"
                        )
                    runner_writer_used(task_id, writer_id)
                    self._json({"status": "COMMITTED", "result": result})
                    return
                self.send_error(HTTPStatus.NOT_FOUND)
            except Exception as exc:
                self._json(
                    {
                        "status": "FAIL",
                        "error_code": (
                            "RUNNER_WRITER_LEASE_HELD"
                            if exc.__class__.__name__ == "WriterLeaseError"
                            else getattr(exc, "code", "PRODUCT_WEB_ERROR")
                        ),
                        "error": (
                            "修改意见未确认登记，请刷新任务后核对并重试。"
                            if action == "runner_revision-request" and not isinstance(exc, ProductSurfaceError)
                            else str(exc)
                        ),
                        "external_action_authorized": False,
                    },
                    getattr(exc, "http_status", HTTPStatus.BAD_REQUEST),
                )

    return ProductHandler


def create_product_server(
    kernel: ProductKernelSurface,
    *,
    runner: ProductRunnerSurface,
    runner_writer_owner: Callable[[str], str],
    runner_writer_used: Callable[[str, str], None],
    port: int = 0,
    session_token: str | None = None,
    product_info: dict[str, Any] | None = None,
    web_agent: ProductWebAgentSurface | None = None,
) -> ThreadingHTTPServer:
    """Create a token-bound loopback landing server over ProductKernel."""
    token = session_token or secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    from .quality_readiness import identity_provenance_sha256

    session_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
    run_digest = hashlib.sha256(csrf.encode("utf-8")).hexdigest()[:24]
    web_user_identity = {
        "principal_id": "local-user",
        "session_id": f"product-web-session-{session_digest}",
        "run_id": f"product-web-server-{run_digest}",
        "independence_group": f"authenticated-local-user-{session_digest}",
        "attestation_input_id": f"identity:web-user:{session_digest}",
    }
    web_user_identity["provenance_sha256"] = identity_provenance_sha256(
        web_user_identity
    )
    server = ThreadingHTTPServer(
        ("127.0.0.1", port),
        make_product_handler(
            kernel,
            runner=runner,
            runner_writer_owner=runner_writer_owner,
            runner_writer_used=runner_writer_used,
            session_token=token,
            csrf_token=csrf,
            web_user_identity=web_user_identity,
            product_info=product_info,
            web_agent=web_agent,
        ),
    )
    server.session_token = token  # type: ignore[attr-defined]
    server.csrf_token = csrf  # type: ignore[attr-defined]
    server.web_user_identity = deepcopy(web_user_identity)  # type: ignore[attr-defined]
    return server


def serve(job_path: str | Path, *, port: int = 0, open_browser: bool = False) -> None:
    server = create_server(job_path, port=port)
    address = f"http://127.0.0.1:{server.server_port}/"
    print(
        json.dumps({"status": "READY", "address": address}, ensure_ascii=False),
        flush=True,
    )
    if open_browser:
        threading.Timer(0.2, webbrowser.open, args=(address,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
