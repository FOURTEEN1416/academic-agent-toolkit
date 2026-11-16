"""Hidden, auditable Codex worker for the Product Web collaboration surface.

The browser never submits academic JSON through this module.  It starts a
revision-bound job or supplies one natural-language reply.  A local Codex
process prepares a candidate stage payload, and this host adapter is the only
code that may pass that payload to the existing ProductRunner CAS facade.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from xml.etree import ElementTree

from jsonschema import Draft202012Validator

from material_profile import build_material_profile


RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract",
        "schema_version",
        "task_id",
        "revision",
        "issue_id",
        "stage",
        "status",
        "summary",
        "question",
        "stage_payload_json",
        "external_action_authorized",
    ],
    "properties": {
        "contract": {"type": "string", "const": "paperspine5.web-agent-result"},
        "schema_version": {"type": "string", "const": "1.0"},
        "task_id": {"type": "string", "minLength": 1},
        "revision": {"type": "integer", "minimum": 0},
        "issue_id": {"type": "string", "minLength": 1},
        "stage": {"type": "string", "minLength": 1},
        "status": {
            "type": "string",
            "enum": ["submit_stage", "awaiting_user", "blocked"],
        },
        "summary": {"type": "string"},
        "question": {"type": ["string", "null"]},
        "stage_payload_json": {"type": ["string", "null"]},
        "external_action_authorized": {"type": "boolean", "const": False},
    },
}

REVIEW_RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract",
        "schema_version",
        "task_id",
        "revision",
        "issue_id",
        "stage",
        "decision",
        "summary",
        "objections",
        "external_action_authorized",
    ],
    "properties": {
        "contract": {
            "type": "string",
            "const": "paperspine5.web-agent-independent-review",
        },
        "schema_version": {"type": "string", "const": "1.0"},
        "task_id": {"type": "string", "minLength": 1},
        "revision": {"type": "integer", "minimum": 0},
        "issue_id": {"type": "string", "minLength": 1},
        "stage": {"type": "string", "minLength": 1},
        "decision": {"type": "string", "enum": ["pass", "block"]},
        "summary": {"type": "string"},
        "objections": {
            "type": "array",
            "items": {"type": "string"},
        },
        "target_rule_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "authority_rule_id",
                    "status",
                    "evidence_locator",
                ],
                "properties": {
                    "authority_rule_id": {"type": "string", "minLength": 1},
                    "status": {
                        "type": "string",
                        "enum": ["satisfied", "unsatisfied"],
                    },
                    "evidence_locator": {"type": "string", "minLength": 1},
                },
            },
        },
        "external_action_authorized": {"type": "boolean", "const": False},
    },
}

FIGURE_CORRECTION_REVIEW_RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract",
        "contract_version",
        "subject",
        "decision",
        "checks",
        "summary",
        "objections",
        "reviewed_at",
        "external_action_authorized",
    ],
    "properties": {
        "contract": {
            "type": "string",
            "const": "paperspine5.figure-correction-review-result",
        },
        "contract_version": {"type": "string", "const": "1.0"},
        "subject": {"type": "object"},
        "decision": {"type": "string", "enum": ["pass", "block"]},
        "checks": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "allowed_tokens_only",
                "mask_scope_valid",
                "scientific_invariants_valid",
                "target_size_legible",
            ],
            "properties": {
                "allowed_tokens_only": {"type": "boolean"},
                "mask_scope_valid": {"type": "boolean"},
                "scientific_invariants_valid": {"type": "boolean"},
                "target_size_legible": {"type": "boolean"},
            },
        },
        "summary": {"type": "string"},
        "objections": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "reviewed_at": {"type": "string", "format": "date-time"},
        "external_action_authorized": {"type": "boolean", "const": False},
    },
}

INDEPENDENT_REVIEW_STAGES = frozenset(
    {
        "awaiting_research",
        "awaiting_claim_graph",
        "awaiting_canonical",
        "awaiting_review",
    }
)
RUNNER_RESERVED_STAGE_FIELDS = frozenset(
    {"subject", "trusted_artifacts", "frozen_authority", "artifact_descriptors"}
)

PUBLIC_JOB_FIELDS = {
    "contract",
    "schema_version",
    "job_id",
    "task_id",
    "revision",
    "issue_id",
    "stage",
    "status",
    "committed_blocked",
    "summary",
    "question",
    "created_at",
    "updated_at",
    "started_at",
    "finished_at",
    "attempt",
    "error",
    "resource_blocker",
    "runtime_blocker",
    "external_action_authorized",
}
MALFORMED_STAGE_PAYLOAD_ERRORS = frozenset(
    {
        "stage_payload_json must contain valid JSON",
        "submit_stage requires stage_payload_json",
    }
)

AGENT_LOG_LIMIT_BYTES = 2 * 1024 * 1024
AGENT_RESULT_LIMIT_BYTES = 4 * 1024 * 1024
ROLLOUT_PARSE_FAILURE_MARKER = b"EOF while parsing a string at line 1 column"
PORTABLE_RENDER_TEMP_ROOTS = (
    "cache/document_render_tmp",
    "cache/docx_render_temp",
    "document_render_tmp",
    "docx_render_temp",
    "canonical/cache/document_render_tmp",
    "canonical/docx_render_temp",
)
AUTHOR_ONLY_TARGET_FACT_KEYS = frozenset(
    {
        "author_identity",
        "affiliation",
        "orcid",
        "funding",
        "conflict_of_interest",
        "data_availability",
        "code_availability",
        "author_contributions",
        "corresponding_author",
    }
)


class AgentResourceLimitError(RuntimeError):
    """A bounded child-process failure that must not be retried or submitted."""

    def __init__(
        self,
        code: str,
        *,
        limit_bytes: int,
        observed_bytes_at_least: int,
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.limit_bytes = limit_bytes
        self.observed_bytes_at_least = observed_bytes_at_least
        self.detail = detail


class AgentProfileIsolationUnavailableError(RuntimeError):
    """The safe child profile cannot use CLI-managed authentication."""

    code = "AGENT_PROFILE_ISOLATION_UNAVAILABLE"

    def __init__(self, *, detail: str, evidence_path: Path) -> None:
        super().__init__(detail)
        self.detail = detail
        self.evidence_path = evidence_path


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _without_tex_comments(text: str) -> str:
    """Return only active TeX source lines while preserving escaped percent signs."""

    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def _cleanup_portable_render_temporary_roots(workspace_root: Path) -> None:
    """Remove only task-local allowlisted office scratch and prove enumeration."""

    root = workspace_root.resolve()
    for relative in PORTABLE_RENDER_TEMP_ROOTS:
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:  # pragma: no cover - constants are controlled
            raise ValueError("portable render temp root escapes the task workspace") from exc
        if not candidate.exists():
            continue
        if not candidate.is_dir():
            raise ValueError(f"portable render temp root is not a directory: {relative}")
        children = list(candidate.iterdir())
        unexpected = [
            child.name
            for child in children
            if not child.name.startswith(("soffice_profile_", "soffice_convert_"))
        ]
        if unexpected:
            raise ValueError(
                f"portable render temp root contains non-allowlisted entries: {relative}: {sorted(unexpected)}"
            )
        for child in children:
            shutil.rmtree(child)
        candidate.rmdir()
        parent = candidate.parent
        while parent != root and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent

    def fail_enumeration(error: OSError) -> None:
        raise ValueError(f"task workspace is not fully enumerable: {error}") from error

    for _directory, _subdirs, _files in os.walk(root, onerror=fail_enumeration):
        pass


def _iso_calendar_date(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.date().isoformat()


def _elapsed_seconds(job: dict[str, Any]) -> int | None:
    started_at = job.get("started_at")
    if not isinstance(started_at, str):
        return None
    try:
        started = datetime.fromisoformat(started_at)
        finished_text = job.get("finished_at")
        finished = (
            datetime.fromisoformat(finished_text)
            if isinstance(finished_text, str)
            else datetime.now(UTC)
        )
    except ValueError:
        return None
    return max(0, int((finished - started).total_seconds()))


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    for attempt in range(12):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 11:
                raise
            time.sleep(0.01)


def _creation_flags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))


def _host_identity(job: dict[str, Any], role: str) -> dict[str, str]:
    token = f"{job['job_id']}-{role}"
    identity = {
        "principal_id": f"paperspine-web-{role}",
        "session_id": f"session-{token}",
        "run_id": f"run-{token}",
        "independence_group": f"group-{token}",
        "attestation_input_id": f"identity:web-{token}",
    }
    core = {
        key: identity[key]
        for key in ("principal_id", "session_id", "run_id", "independence_group")
    }
    encoded = json.dumps(
        core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    identity["provenance_sha256"] = hashlib.sha256(encoded).hexdigest()
    return identity


def _self_hashed(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = copy.deepcopy(value)
    unsigned = {key: item for key, item in result.items() if key != field}
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    result[field] = hashlib.sha256(encoded).hexdigest()
    return result


def _derive_target_obligation_ledger(
    target_authority: dict[str, Any], target_authority_sha256: str
) -> dict[str, Any]:
    """Derive stable J9/J10 obligation IDs from frozen typed hard rules.

    The producer never chooses an obligation ID or readiness layer.  Both are
    frozen at J4 and this host projection is deterministic for the same target
    authority bytes.
    """

    if (
        target_authority.get("contract") != "paperspine5.target-authority"
        or target_authority.get("schema_version") != "1.0"
        or not re.fullmatch(r"[0-9a-f]{64}", target_authority_sha256)
    ):
        raise ValueError("target authority is missing or invalid")
    raw_rules = target_authority.get("official_hard_rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("target authority has no official hard rules")
    obligations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, rule in enumerate(raw_rules):
        if not isinstance(rule, dict):
            raise ValueError(f"target hard rule is invalid: {index}")
        rule_id = str(rule.get("rule_id") or "").strip()
        if not rule_id or rule_id in seen:
            raise ValueError(f"target hard rule ID is missing or duplicated: {index}")
        seen.add(rule_id)
        if rule.get("kind") != "hard" or rule.get("enforcement") != "hard":
            raise ValueError(f"target hard rule authority is invalid: {rule_id}")
        scope = rule.get("readiness_scope")
        if scope not in {"local_delivery", "author_only_submission"}:
            raise ValueError(f"target hard rule readiness scope is missing: {rule_id}")
        evidence_locator = str(rule.get("evidence_locator") or "").strip()
        if not evidence_locator:
            raise ValueError(f"target hard rule evidence locator is missing: {rule_id}")
        author_fact_key = rule.get("author_fact_key")
        if scope == "author_only_submission":
            if author_fact_key not in AUTHOR_ONLY_TARGET_FACT_KEYS:
                raise ValueError(
                    f"target author-only rule has no fixed author fact key: {rule_id}"
                )
        elif author_fact_key is not None:
            raise ValueError(
                f"local-delivery target rule cannot carry an author fact key: {rule_id}"
            )
        obligation = {
            "obligation_id": f"target-rule:{rule_id}",
            "authority_rule_id": rule_id,
            "hard": True,
            "readiness_scope": scope,
            "authority_binding": {
                "artifact_id": "target_authority",
                "sha256": target_authority_sha256,
            },
            "evidence_locator": evidence_locator,
        }
        if scope == "author_only_submission":
            obligation["author_fact_key"] = author_fact_key
        obligations.append(obligation)
    if not any(item["readiness_scope"] == "local_delivery" for item in obligations):
        raise ValueError("target authority has no local-delivery hard rule")
    return _self_hashed(
        {
            "contract": "paperspine5.target-obligation-ledger",
            "contract_version": "1.0",
            "status": "PASS",
            "frozen": True,
            "target_authority_sha256": target_authority_sha256,
            "obligations": sorted(obligations, key=lambda item: item["obligation_id"]),
            "external_action_authorized": False,
            "ledger_sha256": "0" * 64,
        },
        "ledger_sha256",
    )


def _docx_paragraphs(path: Path) -> list[str]:
    """Return reader-visible Word paragraphs or fail closed on a malformed DOCX."""
    try:
        with zipfile.ZipFile(path, "r") as archive:
            document_xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(document_xml)
    except (KeyError, OSError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError("J8 Word file is not a readable DOCX document") from exc
    word_namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    paragraph_tag = f"{{{word_namespace}}}p"
    text_tag = f"{{{word_namespace}}}t"
    paragraphs: list[str] = []
    for paragraph in root.iter(paragraph_tag):
        value = "".join(
            node.text or "" for node in paragraph.iter(text_tag)
        ).strip()
        if value:
            paragraphs.append(value)
    if not paragraphs:
        raise ValueError("J8 Word file contains no reader-visible paragraphs")
    return paragraphs


def _docx_media_inventory(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Return hash-bound DOCX media and the subset referenced by the main body.

    A file merely present under ``word/media`` is not reader-visible evidence.
    Resolve OOXML image relationships used by ``word/document.xml`` and verify
    PNG signatures so a renamed PDF cannot satisfy the Word delivery gate.
    """

    relationship_namespace = (
        "http://schemas.openxmlformats.org/package/2006/relationships"
    )
    office_relationship_namespace = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            document_xml = archive.read("word/document.xml")
            relationships_xml = (
                archive.read("word/_rels/document.xml.rels")
                if "word/_rels/document.xml.rels" in names
                else (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/'
                    'package/2006/relationships"/>'
                ).encode("utf-8")
            )
            media_bytes = {
                name: archive.read(name)
                for name in sorted(names)
                if name.startswith("word/media/") and not name.endswith("/")
            }
        document_root = ElementTree.fromstring(document_xml)
        relationships_root = ElementTree.fromstring(relationships_xml)
    except (KeyError, OSError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError(
            "J8 Word image-complete surface has no readable OOXML media relationships"
        ) from exc

    relationships: dict[str, str] = {}
    for relationship in relationships_root.iter(
        f"{{{relationship_namespace}}}Relationship"
    ):
        relationship_id = relationship.get("Id")
        relationship_type = relationship.get("Type") or ""
        target = relationship.get("Target")
        if (
            not relationship_id
            or not target
            or not relationship_type.endswith("/image")
            or relationship.get("TargetMode") == "External"
        ):
            continue
        raw_target = PurePosixPath(target.replace("\\", "/"))
        combined = (
            raw_target
            if raw_target.is_absolute()
            else PurePosixPath("word") / raw_target
        )
        normalized_parts: list[str] = []
        for part in combined.parts:
            if part in {"", "/", "."}:
                continue
            if part == "..":
                if not normalized_parts:
                    raise ValueError("J8 Word media relationship escapes the DOCX package")
                normalized_parts.pop()
                continue
            normalized_parts.append(part)
        normalized = PurePosixPath(*normalized_parts).as_posix()
        if not normalized.startswith("word/media/"):
            continue
        relationships[relationship_id] = normalized

    referenced_ids: list[str] = []
    relationship_attributes = {
        f"{{{office_relationship_namespace}}}embed",
        f"{{{office_relationship_namespace}}}id",
    }
    for element in document_root.iter():
        for attribute in relationship_attributes:
            relationship_id = element.get(attribute)
            if relationship_id and relationship_id not in referenced_ids:
                referenced_ids.append(relationship_id)

    def descriptor(name: str) -> dict[str, Any]:
        encoded = media_bytes[name]
        suffix = PurePosixPath(name).suffix.lower()
        media_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".svg": "image/svg+xml",
            ".emf": "image/emf",
            ".wmf": "image/wmf",
            ".pdf": "application/pdf",
        }.get(suffix, "application/octet-stream")
        if suffix == ".png" and not encoded.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"J8 Word media uses .png without PNG bytes: {name}")
        return {
            "path": name,
            "suffix": suffix,
            "media_type": media_type,
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "size_bytes": len(encoded),
        }

    all_media = [descriptor(name) for name in sorted(media_bytes)]
    visible_media: list[dict[str, Any]] = []
    visible_paths: set[str] = set()
    for relationship_id in referenced_ids:
        name = relationships.get(relationship_id)
        if not name or name in visible_paths:
            continue
        if name not in media_bytes:
            raise ValueError(f"J8 Word image relationship target is missing: {name}")
        visible_paths.add(name)
        visible_media.append(descriptor(name))
    return {"all_media": all_media, "visible_media": visible_media}


class ProductWebAgentRuntime:
    """One active hidden Agent job per task, with immutable per-job evidence."""

    def __init__(
        self,
        *,
        kernel: Any,
        runner: Any,
        project_root: str | Path,
        user_data_root: str | Path,
        runner_writer_owner: Callable[[str], str],
        runner_writer_used: Callable[[str, str], None],
        standalone_skill_path: str | Path | None = None,
        codex_executable: str | None = None,
        process_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        base_environment: dict[str, str] | None = None,
    ) -> None:
        self.kernel = kernel
        self.runner = runner
        self.project_root = Path(project_root).resolve()
        self.user_data_root = Path(user_data_root).resolve()
        self.control_root = self.user_data_root / ".paperspine5-web-agent"
        self.runner_writer_owner = runner_writer_owner
        self.runner_writer_used = runner_writer_used
        embedded_skill = self.project_root.parent / "SKILL.md"
        configured_codex_home = Path(
            os.environ.get("CODEX_HOME", Path.home() / ".codex")
        )
        self.standalone_skill_path = Path(
            standalone_skill_path
            or (
                embedded_skill
                if embedded_skill.is_file()
                else configured_codex_home / "skills" / "paper-spine" / "SKILL.md"
            )
        ).expanduser().resolve()
        self.codex_executable = codex_executable or shutil.which("codex") or "codex"
        self.process_runner = process_runner or subprocess.run
        self._stream_process_output = process_runner is None
        self.base_environment = dict(
            os.environ if base_environment is None else base_environment
        )
        self._lock = threading.RLock()
        self._active: dict[str, str] = {}
        self._threads: dict[str, threading.Thread] = {}

    @staticmethod
    def _paperspine_canonical_sha256(value: dict[str, Any]) -> str:
        return hashlib.sha256(
            (
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        ).hexdigest()

    def review_figure_correction(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run the host-owned post-output/post-legibility multimodal review.

        The J7 producer cannot call this as a payload field.  ProductRunner
        invokes this production callback only after FigMirror, pixel/invariant
        checks and the physical-size receipt have all succeeded.
        """

        if context.get("contract") != "paperspine5.figure-correction-review-context":
            raise ValueError("figure correction review context contract is invalid")
        subject = context.get("subject")
        artifacts = context.get("artifacts")
        if not isinstance(subject, dict) or not isinstance(artifacts, dict):
            raise ValueError("figure correction review context is incomplete")
        task_id = str(subject.get("task_id") or "")
        task = self.kernel.get_task(task_id)
        if task["revision"] != subject.get("revision"):
            raise ValueError("figure correction review revision is stale")
        snapshot = self.runner.snapshot(task_id)
        material_pointer = snapshot.get("material_inventory")
        snapshot_material_sha256 = (
            material_pointer.get("snapshot_sha256")
            if isinstance(material_pointer, dict)
            else snapshot.get("material_snapshot_sha256")
        )
        if snapshot_material_sha256 != subject.get("material_snapshot_sha256"):
            raise ValueError("figure correction review material snapshot is stale")
        if context.get("external_action_authorized") is not False:
            raise ValueError("figure correction review cannot authorize external action")

        job_id = "figure-review-" + uuid.uuid4().hex
        run_root = Path(task["run_root"]).resolve()
        output_descriptor = artifacts.get("output")
        if not isinstance(output_descriptor, dict):
            raise ValueError("figure correction review output artifact is missing")
        output_stage = Path(str(output_descriptor.get("path") or "")).resolve()
        review_root = output_stage.parent / (
            "independent-figure-review-"
            + str(subject.get("operation_sha256") or "")[:16]
        )
        expected_staging_root = (run_root / "runner" / ".staging").resolve()
        try:
            review_root.resolve().relative_to(expected_staging_root)
        except ValueError as exc:
            raise ValueError(
                "figure correction review staging escaped the Runner command"
            ) from exc
        review_root.mkdir(parents=True, exist_ok=True)
        context_path = review_root / "context.json"
        schema_path = review_root / "result.schema.json"
        result_path = review_root / "result.json"
        log_path = review_root / "reviewer.log"
        try:
            _atomic_json(context_path, context)
            _atomic_json(schema_path, FIGURE_CORRECTION_REVIEW_RESULT_SCHEMA)
            image_paths = self._render_figure_review_images(
                artifacts=artifacts,
                run_root=run_root,
                review_root=review_root,
            )
        except BaseException:
            shutil.rmtree(review_root, ignore_errors=False)
            raise

        job = {
            "job_id": job_id,
            "task_id": task_id,
            "revision": subject["revision"],
            "issue_id": "figure-correction-independent-review",
            "stage": "awaiting_figure_intent",
        }
        prompt = f"""You are the host-owned independent multimodal reviewer for one PaperSpine figure correction.

Read the immutable typed context at {context_path}. The two attached images are the exact source and corrected output. You are a separate reviewer process, not the PaperSpine producer and not FigMirror.

Verify only the authorized token changes, mask-bounded pixel difference, preservation of every panel/data-curve/data-value invariant, and the already measured target-size legibility receipt. Bind your result to the exact unchanged subject object from the context. A producer claim, reviewer name string, or PASS status is not evidence. If any check is not independently supported, decision must be block and the failed check must be false. Do not edit files, call PaperSpine tools, spawn agents, use the network, or authorize external action.

Return only the JSON allowed by {schema_path}; output is written by the host to {result_path}.
"""
        try:
            completed = self._run_codex_process(
                command=self._review_command(
                    task, schema_path, result_path, image_paths=image_paths
                ),
                stdout_path=log_path,
                process_options={
                    "input": prompt,
                    "text": True,
                    "encoding": "utf-8",
                    "errors": "replace",
                    "cwd": task["workspace_root"],
                    "env": self._child_environment(task, snapshot),
                    "stderr": subprocess.STDOUT,
                    "creationflags": _creation_flags(),
                    "timeout": 60 * 20,
                    "check": False,
                },
            )
        except BaseException:
            shutil.rmtree(review_root, ignore_errors=False)
            raise
        if completed.returncode != 0 or not result_path.is_file():
            shutil.rmtree(review_root, ignore_errors=False)
            raise RuntimeError(
                "host-owned independent figure reviewer did not return a typed result"
            )
        try:
            result = self._load_agent_json(result_path)
        finally:
            # Context, rendered PNGs, bounded log and the child result are
            # transient reviewer inputs.  The returned signed review is the
            # audit artifact; no reviewer staging survives success or failure.
            shutil.rmtree(review_root, ignore_errors=False)
        schema_errors = sorted(
            Draft202012Validator(
                FIGURE_CORRECTION_REVIEW_RESULT_SCHEMA
            ).iter_errors(result),
            key=lambda error: tuple(str(item) for item in error.absolute_path),
        )
        if schema_errors:
            raise ValueError(
                "host-owned independent figure review result violates its schema: "
                + "; ".join(error.message for error in schema_errors)
            )
        if (
            result.get("contract")
            != "paperspine5.figure-correction-review-result"
            or result.get("contract_version") != "1.0"
            or result.get("subject") != subject
            or result.get("decision") != "pass"
            or result.get("objections") != []
            or set(result.get("checks") or {})
            != {
                "allowed_tokens_only",
                "mask_scope_valid",
                "scientific_invariants_valid",
                "target_size_legible",
            }
            or not all((result.get("checks") or {}).values())
            or result.get("external_action_authorized") is not False
        ):
            raise ValueError(
                "host-owned independent figure review is blocked, forged, or stale"
            )
        reviewer = {
            **_host_identity(job, "reviewer"),
            "actor_kind": "host_independent_multimodal",
        }
        reviewer.pop("provenance_sha256", None)
        reviewer["provenance_sha256"] = self._paperspine_canonical_sha256(
            reviewer
        )
        review = {
            "contract": "paperspine5.figure-correction-review",
            "contract_version": "1.0",
            "subject": copy.deepcopy(subject),
            "reviewer_id": reviewer["principal_id"],
            "reviewer_type": "independent_multimodal",
            "reviewer": reviewer,
            "producer_ids": ["paper-spine", "figmirror"],
            "producer_actor": "figmirror",
            "checks": copy.deepcopy(result["checks"]),
            "status": "pass",
            "reviewed_at": result["reviewed_at"],
            "external_action_authorized": False,
        }
        review["review_sha256"] = self._paperspine_canonical_sha256(review)
        return review

    @staticmethod
    def _render_figure_review_images(
        *,
        artifacts: dict[str, Any],
        run_root: Path,
        review_root: Path,
    ) -> list[Path]:
        image_paths: list[Path] = []
        for label in ("source", "output"):
            descriptor = artifacts.get(label)
            if not isinstance(descriptor, dict):
                raise ValueError(
                    f"figure correction review {label} artifact is missing"
                )
            path = Path(str(descriptor.get("path") or "")).resolve()
            try:
                path.relative_to(run_root)
            except ValueError as exc:
                raise ValueError(
                    f"figure correction review {label} escapes the task run"
                ) from exc
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != descriptor.get("sha256"):
                raise ValueError(f"figure correction review {label} hash changed")
            image_path = review_root / f"{label}.png"
            media_type = descriptor.get("media_type")
            if media_type == "application/pdf":
                import fitz

                document = fitz.open(stream=content, filetype="pdf")
                try:
                    if document.page_count != 1:
                        raise ValueError("figure review requires one-page PDF figures")
                    page = document[0]
                    scale = 1800 / float(page.rect.width)
                    page.get_pixmap(
                        matrix=fitz.Matrix(scale, scale), alpha=False
                    ).save(image_path)
                finally:
                    document.close()
            elif media_type == "image/svg+xml":
                import cairosvg

                cairosvg.svg2png(
                    bytestring=content,
                    write_to=str(image_path),
                    output_width=1800,
                )
            else:
                raise ValueError(
                    f"figure correction review media type is unsupported: {media_type}"
                )
            image_paths.append(image_path)
        return image_paths

    def status(self, task_id: str) -> dict[str, Any]:
        task = self.kernel.get_task(task_id)
        pointer = self._latest_path(task_id)
        with self._lock:
            if not pointer.is_file():
                return {
                    "contract": "paperspine5.web-agent-status",
                    "schema_version": "1.0",
                    "task_id": task_id,
                    "status": "idle",
                    "task_revision": task["revision"],
                    "external_action_authorized": False,
                }
            try:
                job = json.loads(pointer.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {
                    "contract": "paperspine5.web-agent-status",
                    "schema_version": "1.0",
                    "task_id": task_id,
                    "status": "failed",
                    "task_revision": task["revision"],
                    "error": "Agent 作业状态无法读取。",
                    "external_action_authorized": False,
                }
        public = {key: copy.deepcopy(value) for key, value in job.items() if key in PUBLIC_JOB_FIELDS}
        public["task_revision"] = task["revision"]
        public["elapsed_seconds"] = _elapsed_seconds(job)
        if job.get("status") == "running":
            activity = self._activity(job)
            if activity is not None:
                public.update(activity)
        public["stale"] = (
            job.get("status") not in {"queued", "running"}
            and job.get("revision") != task["revision"]
            and job.get("status") != "stage_submitted"
        )
        return public

    def _activity(self, job: dict[str, Any]) -> dict[str, Any] | None:
        job_dir = self._job_dir(job["task_id"], job["job_id"])
        reviewer_log = job_dir / "reviewer.log"
        log_path = reviewer_log if reviewer_log.is_file() else job_dir / "agent.log"
        if not log_path.is_file():
            return None
        try:
            stat = log_path.stat()
            idle_seconds = max(
                0,
                int((datetime.now(UTC) - datetime.fromtimestamp(stat.st_mtime, UTC)).total_seconds()),
            )
            with log_path.open("rb") as stream:
                stream.seek(max(0, stat.st_size - 32_768))
                tail = stream.read().decode("utf-8", errors="replace").lower()
        except OSError:
            return None
        if log_path == reviewer_log:
            return {
                "summary": "正在执行独立关卡复核。",
                "activity_idle_seconds": idle_seconds,
            }
        markers = {
            "web search:": "正在检索公开研究与目标要求。",
            "apply patch": "正在整理本地研究产物。",
            "exec\n": "正在盘点材料并写入本地证据。",
        }
        marker, summary = max(
            markers.items(),
            key=lambda item: tail.rfind(item[0]),
        )
        if tail.rfind(marker) < 0:
            summary = "正在推理并核对当前关卡。"
        return {
            "summary": summary,
            "activity_idle_seconds": idle_seconds,
        }

    def start(self, task_id: str, *, user_message: str | None = None) -> dict[str, Any]:
        self.kernel.get_task(task_id)
        snapshot = self.runner.snapshot(task_id)
        issue = next(
            (
                item
                for item in snapshot.get("open_issues", [])
                if item.get("code") == "academic.input.required"
            ),
            None,
        )
        if not isinstance(issue, dict):
            raise ValueError("当前任务没有可由网页 Agent 处理的学术协作问题。")
        clean_message = user_message.strip() if isinstance(user_message, str) else None
        if user_message is not None and not clean_message:
            raise ValueError("用户回答不能为空。")
        with self._lock:
            active_id = self._active.get(task_id)
            if active_id:
                active = self._read_job(task_id, active_id)
                if active.get("status") in {"queued", "running"}:
                    return self.status(task_id)
            prior = self.status(task_id)
            carried_message = None
            carried_question = None
            carried_review = None
            reusable_producer_job_id = None
            malformed_repair_job_id = None
            pointer = self._latest_path(task_id)
            try:
                prior_job = json.loads(pointer.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                prior_job = {}
            prior_private = prior_job.get("private")
            if not isinstance(prior_private, dict):
                prior_private = {}
            if clean_message is None and prior.get("status") in {"blocked", "failed"}:
                same_issue = (
                    prior_job.get("revision") == snapshot.get("revision")
                    and prior_job.get("issue_id") == issue.get("issue_id")
                    and prior_job.get("stage") == snapshot.get("stage")
                )
                if same_issue and isinstance(prior_private.get("prior_review"), dict):
                    carried_review = copy.deepcopy(prior_private["prior_review"])
                elif same_issue and isinstance(prior_job.get("job_id"), str):
                    # Upgrade-safe recovery for jobs completed before the
                    # private prior_review pointer was introduced.  The review
                    # result is host-written, schema-bound evidence in the old
                    # job directory, so a retry can still address the exact
                    # objection instead of silently resubmitting stale pages.
                    review_path = (
                        self._job_dir(task_id, prior_job["job_id"])
                        / "review-result.json"
                    )
                    try:
                        recovered_review = json.loads(
                            review_path.read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError):
                        recovered_review = None
                    if (
                        isinstance(recovered_review, dict)
                        and recovered_review.get("decision") == "block"
                        and recovered_review.get("task_id") == task_id
                        and recovered_review.get("revision") == snapshot.get("revision")
                        and recovered_review.get("issue_id") == issue.get("issue_id")
                        and recovered_review.get("stage") == snapshot.get("stage")
                        and isinstance(recovered_review.get("objections"), list)
                    ):
                        carried_review = {
                            "decision": "block",
                            "summary": recovered_review.get("summary"),
                            "objections": copy.deepcopy(
                                recovered_review["objections"]
                            ),
                        }
                if (
                    same_issue
                    and prior_job.get("status") == "failed"
                    and isinstance(prior_job.get("error"), str)
                    and prior_job["error"].startswith("Runner 拒绝 Agent 阶段结果：")
                    and isinstance(prior_job.get("job_id"), str)
                ):
                    prior_dir = self._job_dir(task_id, prior_job["job_id"])
                    prior_result_path = prior_dir / "result.json"
                    prior_review_path = prior_dir / "review-result.json"
                    try:
                        prior_result = json.loads(
                            prior_result_path.read_text(encoding="utf-8")
                        )
                        prior_review = json.loads(
                            prior_review_path.read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError):
                        prior_result = None
                        prior_review = None
                    if (
                        isinstance(prior_result, dict)
                        and prior_result.get("status") == "submit_stage"
                        and prior_result.get("task_id") == task_id
                        and prior_result.get("revision") == snapshot.get("revision")
                        and prior_result.get("issue_id") == issue.get("issue_id")
                        and prior_result.get("stage") == snapshot.get("stage")
                        and isinstance(prior_review, dict)
                        and prior_review.get("decision") == "pass"
                        and prior_review.get("task_id") == task_id
                        and prior_review.get("revision") == snapshot.get("revision")
                        and prior_review.get("issue_id") == issue.get("issue_id")
                        and prior_review.get("stage") == snapshot.get("stage")
                    ):
                        reusable_producer_job_id = prior_job["job_id"]
                if (
                    same_issue
                    and prior_job.get("status") == "failed"
                    and prior_job.get("error") in MALFORMED_STAGE_PAYLOAD_ERRORS
                    and isinstance(prior_job.get("job_id"), str)
                ):
                    malformed_repair_job_id = prior_job["job_id"]
                if (
                    same_issue
                    and isinstance(prior_private.get("user_message"), str)
                    and prior_private.get("user_message").strip()
                ):
                    carried_message = prior_private["user_message"].strip()
                    carried_question = prior_private.get("prior_question")
            prior_committed_block = (
                prior_job.get("status") == "stage_submitted"
                and (
                    prior_job.get("committed_blocked") is True
                    or (
                        isinstance(prior_job.get("summary"), str)
                        and prior_job["summary"].startswith("Runner 已保存本次阻断结果")
                    )
                )
            )
            if (
                clean_message is None
                and prior_committed_block
                and prior_job.get("stage") == snapshot.get("stage")
                and isinstance(prior_private.get("user_message"), str)
                and prior_private["user_message"].strip()
            ):
                # Runner committed blocks deliberately create a new revision and
                # issue id.  Preserve only the user's explicit same-stage facts;
                # never reuse the old producer payload or review across revisions.
                carried_message = prior_private["user_message"].strip()
                carried_question = prior_private.get("prior_question")
            if clean_message is not None:
                if prior.get("status") != "awaiting_user" or prior.get("stale"):
                    raise ValueError("当前没有绑定此 revision 的待回答问题。")
                if prior.get("issue_id") != issue.get("issue_id"):
                    raise ValueError("待回答问题已失效，请重新启动 Agent。")
            job_id = f"agent-{uuid.uuid4().hex}"
            attempt = int(prior.get("attempt") or 0) + 1
            job = {
                "contract": "paperspine5.web-agent-job",
                "schema_version": "1.0",
                "job_id": job_id,
                "task_id": task_id,
                "revision": snapshot["revision"],
                "issue_id": issue["issue_id"],
                "stage": snapshot["stage"],
                "status": "queued",
                "committed_blocked": False,
                "summary": "PaperSpine Agent 已排队。",
                "question": None,
                "created_at": _now(),
                "updated_at": _now(),
                "started_at": None,
                "finished_at": None,
                "attempt": attempt,
                "error": None,
                "external_action_authorized": False,
                "private": {
                    "resume_token": issue["resume_token"],
                    "user_message": clean_message or carried_message,
                    "prior_question": (
                        prior.get("question") if clean_message else carried_question
                    ),
                    "prior_review": carried_review,
                    "reuse_producer_job_id": reusable_producer_job_id,
                    "repair_malformed_job_id": malformed_repair_job_id,
                },
            }
            self._write_job(job)
            self._active[task_id] = job_id
            thread = threading.Thread(
                target=self._run_job,
                args=(job_id,),
                daemon=True,
                name=f"paperspine-web-agent-{task_id[-8:]}",
            )
            self._threads[job_id] = thread
            thread.start()
        return self.status(task_id)

    def _run_job(self, job_id: str) -> None:
        task_id = self._task_id_for_job(job_id)
        job = self._read_job(task_id, job_id)
        job.update(
            status="running",
            summary="PaperSpine Agent 正在读取材料与当前关卡。",
            started_at=_now(),
            updated_at=_now(),
        )
        self._write_job(job)
        job_dir = self._job_dir(task_id, job_id)
        try:
            task = self.kernel.get_task(task_id)
            snapshot = self.runner.snapshot(task_id)
            if snapshot.get("revision") != job["revision"]:
                raise RuntimeError("任务 revision 已变化，未启动过期 Agent。")
            context = self._context(task, snapshot, job)
            context_path = job_dir / "context.json"
            schema_path = job_dir / "result.schema.json"
            result_path = job_dir / "result.json"
            stdout_path = job_dir / "agent.log"
            _atomic_json(context_path, context)
            _atomic_json(schema_path, RESULT_SCHEMA)
            command = self._command(task, schema_path, result_path)
            process_options = {
                "input": None,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "cwd": task["workspace_root"],
                "env": self._child_environment(task, snapshot),
                "stderr": subprocess.STDOUT,
                "creationflags": _creation_flags(),
                "timeout": 60 * 45,
                "check": False,
            }

            def repair_malformed_result(invalid: dict[str, Any]) -> dict[str, Any]:
                invalid_path = job_dir / "invalid-result.json"
                repair_log_path = job_dir / "agent-format-repair.log"
                repair_last_message_path = job_dir / "repair-last-message.json"
                _atomic_json(invalid_path, invalid)
                job.update(
                    summary="正在自动修复 Agent 的结构化结果，不会重做研究。",
                    updated_at=_now(),
                )
                self._write_job(job)
                repair_options = dict(process_options)
                repair_options["input"] = self._format_repair_prompt(
                    context_path=context_path,
                    invalid_result_path=invalid_path,
                    result_path=result_path,
                    job=job,
                )
                if result_path.is_file():
                    result_path.unlink()
                repair_command = self._command(
                    task, schema_path, repair_last_message_path
                )
                repaired = self._run_codex_process(
                    command=repair_command,
                    stdout_path=repair_log_path,
                    process_options=repair_options,
                )
                if repaired.returncode != 0:
                    raise RuntimeError(
                        f"本地 Agent 格式修复退出码为 {repaired.returncode}。"
                    )
                candidates = [
                    path
                    for path in (result_path, repair_last_message_path)
                    if path.is_file()
                ]
                if not candidates:
                    raise RuntimeError("本地 Agent 格式修复未返回结构化结果。")
                last_error: Exception | None = None
                for candidate_path in candidates:
                    try:
                        candidate = self._load_agent_json(candidate_path)
                        self._validate_result(candidate, job)
                        return candidate
                    except (OSError, json.JSONDecodeError, ValueError) as exc:
                        last_error = exc
                raise ValueError(
                    f"Agent format repair result is invalid: {last_error}"
                )

            reuse_job_id = job["private"].get("reuse_producer_job_id")
            repair_job_id = job["private"].get("repair_malformed_job_id")
            repaired_from_prior = False
            if isinstance(repair_job_id, str) and repair_job_id.startswith("agent-"):
                prior_invalid_path = self._job_dir(task_id, repair_job_id) / "result.json"
                prior_invalid = self._load_agent_json(prior_invalid_path)
                result = repair_malformed_result(prior_invalid)
                repaired_from_prior = True
            elif isinstance(reuse_job_id, str) and reuse_job_id.startswith("agent-"):
                reused_path = self._job_dir(task_id, reuse_job_id) / "result.json"
                result = self._load_agent_json(reused_path)
                _atomic_json(result_path, result)
                stdout_path.write_text(
                    "Reusing the prior producer result after a reviewer PASS; "
                    "the host will rematerialize bytes and run a fresh independent review.\n",
                    encoding="utf-8",
                )
                job.update(
                    summary="正在重新绑定已审稿候选并执行独立复核。",
                    updated_at=_now(),
                )
                self._write_job(job)
            else:
                prompt = self._prompt(context_path, result_path, job)
                process_options["input"] = prompt
                completed = self._run_codex_process(
                    command=command,
                    stdout_path=stdout_path,
                    process_options=process_options,
                )
                if completed.returncode != 0:
                    raise RuntimeError(f"本地 Agent 退出码为 {completed.returncode}。")
                if not result_path.is_file():
                    raise RuntimeError("本地 Agent 未返回结构化结果。")
                result = self._load_agent_json(result_path)
            try:
                self._validate_result(result, job)
            except ValueError as exc:
                if (
                    not repaired_from_prior
                    and str(exc) in MALFORMED_STAGE_PAYLOAD_ERRORS
                ):
                    result = repair_malformed_result(result)
                    self._validate_result(result, job)
                else:
                    raise
            if result["status"] == "submit_stage":
                result = self._prepare_stage_result(
                    task=task,
                    snapshot=snapshot,
                    context_path=context_path,
                    job=job,
                    job_dir=job_dir,
                    result=result,
                )
            if result["status"] == "submit_stage":
                submission = self._submit_result(job, result)
                committed_blocked = submission.get("committed_blocked", False)
                job.update(
                    status="stage_submitted",
                    committed_blocked=bool(committed_blocked),
                    summary=(
                        submission.get("summary")
                        if committed_blocked
                        else result["summary"]
                        or "当前学术阶段已由 Runner 验证并提交。"
                    ),
                    question=None,
                    finished_at=_now(),
                    updated_at=_now(),
                    error=None,
                )
            elif result["status"] == "awaiting_user":
                job.update(
                    status="awaiting_user",
                    summary=result["summary"] or "需要用户确认后才能继续。",
                    question=result["question"],
                    finished_at=_now(),
                    updated_at=_now(),
                    error=None,
                )
            else:
                job.update(
                    status="blocked",
                    summary=result["summary"] or "Agent 无法在证据边界内继续。",
                    question=result["question"],
                    finished_at=_now(),
                    updated_at=_now(),
                    error=None,
                )
        except AgentProfileIsolationUnavailableError as exc:
            blocker = self._record_runtime_blocker(job_dir=job_dir, job=job, error=exc)
            job.update(
                status="blocked",
                committed_blocked=False,
                summary=(
                    "PaperSpine Agent 的空 task profile 未找到可用的 Codex OS keyring 登录；"
                    "请先完成一次 keyring 登录再重试。系统已停止一次，未读取 auth.json、"
                    "未回退到主会话历史、未提交阶段结果，Runner revision 保持不变。"
                ),
                question=None,
                error=exc.code,
                runtime_blocker=blocker,
                finished_at=_now(),
                updated_at=_now(),
            )
        except AgentResourceLimitError as exc:
            blocker = self._record_resource_blocker(job_dir=job_dir, job=job, error=exc)
            job.update(
                status="blocked",
                committed_blocked=False,
                summary=(
                    "PaperSpine Agent 的本地输出超过安全边界；已停止一次，"
                    "未重试、未提交阶段结果，Runner revision 保持不变。"
                ),
                question=None,
                error=exc.code,
                resource_blocker=blocker,
                finished_at=_now(),
                updated_at=_now(),
            )
        except subprocess.TimeoutExpired:
            job.update(
                status="failed",
                summary="PaperSpine Agent 超时，未提交任何阶段结果。",
                error="AGENT_TIMEOUT",
                finished_at=_now(),
                updated_at=_now(),
            )
        except Exception as exc:  # Host boundary records a compact public failure.
            job.update(
                status="failed",
                summary="PaperSpine Agent 未能完成当前阶段，Runner 状态保持不变。",
                error=str(exc),
                finished_at=_now(),
                updated_at=_now(),
            )
        finally:
            self._write_job(job)
            with self._lock:
                if self._active.get(task_id) == job_id:
                    self._active.pop(task_id, None)
                self._threads.pop(job_id, None)

    def _record_resource_blocker(
        self,
        *,
        job_dir: Path,
        job: dict[str, Any],
        error: AgentResourceLimitError,
    ) -> dict[str, Any]:
        log_path = job_dir / "agent.log"
        evidence: dict[str, Any] | None = None
        if log_path.is_file():
            content = log_path.read_bytes()
            evidence = {
                "path": "agent.log",
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        blocker = {
            "contract": "paperspine5.web-agent-resource-blocker",
            "schema_version": "1.0",
            "code": error.code,
            "task_id": job["task_id"],
            "revision": job["revision"],
            "issue_id": job["issue_id"],
            "stage": job["stage"],
            "limit_bytes": error.limit_bytes,
            "observed_bytes_at_least": error.observed_bytes_at_least,
            "detail": error.detail,
            "retry_performed": False,
            "runner_revision_unchanged": True,
            "runner_submission_performed": False,
            "evidence": evidence,
            "external_action_authorized": False,
        }
        _atomic_json(job_dir / "resource-blocker.json", blocker)
        return blocker

    def _record_runtime_blocker(
        self,
        *,
        job_dir: Path,
        job: dict[str, Any],
        error: AgentProfileIsolationUnavailableError,
    ) -> dict[str, Any]:
        evidence: dict[str, Any] | None = None
        log_path = error.evidence_path
        if log_path.is_file():
            content = log_path.read_bytes()
            try:
                relative_path = log_path.relative_to(job_dir).as_posix()
            except ValueError:
                relative_path = log_path.name
            evidence = {
                "path": relative_path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        blocker = {
            "contract": "paperspine5.web-agent-runtime-blocker",
            "schema_version": "1.0",
            "code": error.code,
            "task_id": job["task_id"],
            "revision": job["revision"],
            "issue_id": job["issue_id"],
            "stage": job["stage"],
            "detail": error.detail,
            "safe_profile_mode": "empty_task_codex_home_os_keyring",
            "parent_profile_fallback_performed": False,
            "retry_performed": False,
            "runner_revision_unchanged": True,
            "runner_submission_performed": False,
            "evidence": evidence,
            "external_action_authorized": False,
        }
        _atomic_json(job_dir / "runtime-blocker.json", blocker)
        return blocker

    def _prepare_stage_result(
        self,
        *,
        task: dict[str, Any],
        snapshot: dict[str, Any],
        context_path: Path,
        job: dict[str, Any],
        job_dir: Path,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._extract_stage_payload(result["stage_payload_json"], job)
        for field in RUNNER_RESERVED_STAGE_FIELDS:
            payload.pop(field, None)
        payload = self._materialize_stage_inputs(
            task=task,
            snapshot=snapshot,
            payload=payload,
            user_message=job["private"].get("user_message"),
            final_mappings=self._package_mappings(task, snapshot, self.runner),
        )
        review: dict[str, Any] | None = None
        if job["stage"] in INDEPENDENT_REVIEW_STAGES:
            review = self._run_independent_review(
                task=task,
                snapshot=snapshot,
                context_path=context_path,
                job=job,
                job_dir=job_dir,
                payload=payload,
            )
            if review["decision"] != "pass" and job["stage"] != "awaiting_review":
                job["private"]["prior_review"] = {
                    "decision": "block",
                    "summary": review.get("summary"),
                    "objections": copy.deepcopy(review.get("objections", [])),
                }
                review_scope = {
                    "awaiting_research": "研究证据",
                    "awaiting_claim_graph": "主张—证据",
                    "awaiting_canonical": "页面与图文",
                    "awaiting_review": "终稿",
                }.get(job["stage"], "学术证据")
                public_summary = str(review.get("summary") or "").strip()
                return {
                    **result,
                    "status": "blocked",
                    "summary": (
                        f"独立{review_scope}复核未通过："
                        + (
                            public_summary
                            if public_summary
                            else "候选仍有未关闭的证据异议。"
                        )
                        + " 具体异议已记录，重试时 AI 会逐条修订。"
                    ),
                    "question": None,
                    "stage_payload_json": None,
                }
        if job["stage"] == "awaiting_canonical":
            payload = self._finalize_canonical_review(
                payload=payload, job=job, review=review
            )
        elif job["stage"] == "awaiting_review":
            payload = self._finalize_publication_review(
                payload=payload, job=job, review=review
            )
        delegated_contribution = (
            job["stage"] == "awaiting_contribution"
            and isinstance(snapshot.get("interaction"), dict)
            and snapshot["interaction"].get("mode") == "delegated_local_test"
            and snapshot["interaction"].get("grant_status") == "valid"
            and "contribution_selection"
            in snapshot["interaction"].get("decision_classes", [])
        )
        bound = self._bind_host_identities(
            payload,
            job,
            review=review,
            delegated_contribution=delegated_contribution,
        )
        return {
            **result,
            "stage_payload_json": json.dumps(
                bound, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        }

    @staticmethod
    def _persisted_revision_context(
        task: dict[str, Any], snapshot: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Read the Runner-owned prior review across a J9 -> J8 transition."""

        pointer = snapshot.get("academic_inputs")
        if not isinstance(pointer, dict):
            return None
        root = Path(task["run_root"]).resolve()
        path = (root / str(pointer.get("path") or "")).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("revision context pointer escapes the run root") from exc
        encoded = path.read_bytes()
        if pointer.get("sha256") != hashlib.sha256(encoded).hexdigest() or pointer.get("size_bytes") != len(encoded):
            raise ValueError("revision context pointer bytes changed")
        value = json.loads(encoded.decode("utf-8"))
        cumulative = value.get("inputs", value)
        context = cumulative.get("revision_context") if isinstance(cumulative, dict) else None
        if context is None:
            return None
        if not isinstance(context, dict) or context.get("contract") != "paperspine5.publication-revision-context":
            raise ValueError("persisted revision context is invalid")
        review = context.get("initial_review")
        head = context.get("manuscript_head")
        if (
            not isinstance(review, dict) or not isinstance(head, dict)
            or not isinstance(review.get("subject"), dict)
            or review.get("subject", {}).get("task_id") != task["task_id"]
            or review.get("manuscript_head_sha256") != head.get("head_sha256")
            or _self_hashed(review, "review_sha256") != review
            or _self_hashed(head, "head_sha256") != head
        ):
            raise ValueError("persisted revision context review/head binding is invalid")
        return copy.deepcopy(context)

    @staticmethod
    def _package_mappings(task: dict[str, Any], snapshot: dict[str, Any], runner: Any) -> list | None:
        if snapshot.get("stage") not in {"awaiting_canonical", "awaiting_package"}:
            return None
        from paperspine_figure_integration.figure_final_mapping import collect_final_mappings

        return collect_final_mappings(runner, task)

    @staticmethod
    def _materialize_stage_inputs(
        *,
        task: dict[str, Any],
        payload: dict[str, Any],
        snapshot: dict[str, Any] | None = None,
        user_message: str | None = None,
        final_mappings: list | None = None,
    ) -> dict[str, Any]:
        """Bind producer receipts and figure assets to actual Runner inputs.

        A producer may hand the host a task-relative ``artifact_path`` while it
        is constructing J4.  That path is transport metadata, not part of the
        runtime-research-bundle schema.  The host resolves it inside the task
        workspace, reads the actual JSON object, records an attestation for the
        bytes it read, and derives the canonical Runner content hash.  The
        reviewer therefore receives the evidence object rather than a trusted
        path/hash assertion from the producer.

        At J7 the producer can select a material-ledger ``source_id`` as a
        current figure asset.  The source ledger hashes the binary file, while
        the academic Runner intentionally hashes registered JSON input objects.
        The host verifies both the ledger pointer and the immutable material
        object, registers a deterministic JSON binding object, and replaces the
        producer's file-hash assertion with the canonical Runner input hash.
        """

        bound = copy.deepcopy(payload)
        if (
            isinstance(snapshot, dict)
            and snapshot.get("stage") == "awaiting_contribution"
        ):
            # The current host owns phase-1 evidence preparation only.  Strip
            # any model-authored confirmation fields and derive authority
            # bindings from the current Runner snapshot.  Product Web alone
            # may create the subsequent user confirmation.
            for field in (
                "decisions",
                "author_identity",
                "confirmed_at",
                "override_blockers",
                "subject",
            ):
                bound.pop(field, None)
            artifacts = snapshot.get("academic_artifacts")
            inventory = snapshot.get("material_inventory")
            artifacts = artifacts if isinstance(artifacts, dict) else {}
            inventory = inventory if isinstance(inventory, dict) else {}
            direction = artifacts.get("direction_authority")
            target = artifacts.get("target_authority")
            direction = direction if isinstance(direction, dict) else {}
            target = target if isinstance(target, dict) else {}
            bound["contract"] = "paperspine5.contribution-candidate-preparation"
            bound["schema_version"] = "1.0"
            bound["authority_bindings"] = {
                "direction_authority": direction.get("sha256"),
                "target_authority": target.get("sha256"),
                "materials.source-ledger": inventory.get("snapshot_sha256"),
            }
            bound["external_action_authorized"] = False
            return bound
        if (
            isinstance(snapshot, dict)
            and snapshot.get("stage") == "awaiting_figure_intent"
            and isinstance(bound.get("intent"), dict)
        ):
            return ProductWebAgentRuntime._materialize_figure_inputs(
                task=task,
                snapshot=snapshot,
                payload=bound,
                user_message=user_message,
            )
        if (
            isinstance(snapshot, dict)
            and snapshot.get("stage") == "awaiting_canonical"
            and isinstance(bound.get("host_canonical_files"), dict)
        ):
            return ProductWebAgentRuntime._materialize_canonical_inputs(
                task=task,
                snapshot=snapshot,
                payload=bound,
                final_mappings=final_mappings,
            )
        if (
            isinstance(snapshot, dict)
            and snapshot.get("stage") == "awaiting_review"
            and isinstance(bound.get("host_review_pages"), dict)
        ):
            return ProductWebAgentRuntime._materialize_publication_review_inputs(
                task=task, snapshot=snapshot, payload=bound
            )
        if (
            isinstance(snapshot, dict)
            and snapshot.get("stage") == "awaiting_package"
        ):
            return ProductWebAgentRuntime._materialize_target_package_inputs(
                task=task,
                snapshot=snapshot,
                payload=bound,
                user_message=user_message,
                final_mappings=final_mappings,
            )
        if bound.get("contract") != "paperspine5.runtime-research-bundle":
            return bound
        sources = bound.get("sources")
        if not isinstance(sources, list):
            raise ValueError("J4 research payload sources must be an array")
        raw_inputs = bound.get("input_artifacts")
        if raw_inputs is None:
            raw_inputs = {}
        if not isinstance(raw_inputs, dict):
            raise ValueError("J4 research input_artifacts must be an object")
        inputs = copy.deepcopy(raw_inputs)
        workspace_root = Path(task["workspace_root"]).resolve()
        as_of_date = _iso_calendar_date(bound.get("as_of_date"))
        if as_of_date is None:
            candidates = [
                normalized
                for source in sources
                if isinstance(source, dict)
                for normalized in (
                    _iso_calendar_date(source.get("retrieved_at")),
                    _iso_calendar_date(source.get("effective_date")),
                )
                if normalized is not None
            ]
            if not candidates:
                raise ValueError("J4 research payload has no usable as_of_date")
            as_of_date = max(candidates)
        bound["as_of_date"] = as_of_date

        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                raise ValueError(f"J4 research source {index} must be an object")
            source_id = source.get("source_id")
            if not isinstance(source_id, str) or not source_id:
                raise ValueError(f"J4 research source {index} has no source_id")
            artifact_id = f"source:{source_id}"
            artifact_path = source.pop("artifact_path", None)
            source.pop("source_file_sha256", None)
            source.pop("source_file_size_bytes", None)
            if "valid_until" not in source and isinstance(as_of_date, str):
                source["valid_until"] = as_of_date
            if (
                source.get("availability") == "lawful_frozen_cache"
                and source.get("access_basis") == "public"
            ):
                source["access_basis"] = "lawful_cache"

            if isinstance(artifact_path, str) and artifact_path.strip():
                candidate = Path(artifact_path)
                if not candidate.is_absolute():
                    candidate = workspace_root / candidate
                candidate = candidate.resolve()
                try:
                    relative = candidate.relative_to(workspace_root)
                except ValueError as exc:
                    raise ValueError(
                        f"J4 source artifact escapes task workspace: {source_id}"
                    ) from exc
                if not candidate.is_file():
                    raise ValueError(
                        f"J4 source artifact does not exist: {source_id}"
                    )
                encoded = candidate.read_bytes()
                try:
                    artifact = json.loads(encoded.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"J4 source artifact is not UTF-8 JSON: {source_id}"
                    ) from exc
                if not isinstance(artifact, dict):
                    raise ValueError(
                        f"J4 source artifact must contain an object: {source_id}"
                    )
                artifact = copy.deepcopy(artifact)
                artifact["host_file_attestation"] = {
                    "contract": "paperspine5.host-file-attestation",
                    "schema_version": "1.0",
                    "path": relative.as_posix(),
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                    "size_bytes": len(encoded),
                }
                inputs[artifact_id] = artifact
            else:
                artifact = inputs.get(artifact_id)
                if not isinstance(artifact, dict):
                    raise ValueError(
                        f"J4 source has no actual input artifact: {source_id}"
                    )

            canonical = (
                json.dumps(
                    inputs[artifact_id],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            source["content_sha256"] = hashlib.sha256(canonical).hexdigest()

        bound["input_artifacts"] = inputs
        return bound

    @staticmethod
    def _materialize_figure_inputs(
        *,
        task: dict[str, Any],
        snapshot: dict[str, Any],
        payload: dict[str, Any],
        user_message: str | None = None,
    ) -> dict[str, Any]:
        run_root = Path(task["run_root"]).resolve()
        pointer = snapshot.get("material_inventory")
        if not isinstance(pointer, dict):
            raise ValueError("J7 material inventory pointer is missing")
        pointer_path = pointer.get("path")
        if not isinstance(pointer_path, str) or not pointer_path.strip():
            raise ValueError("J7 material inventory path is missing")
        ledger_path = (run_root / pointer_path).resolve()
        try:
            ledger_path.relative_to(run_root)
        except ValueError as exc:
            raise ValueError("J7 material inventory escapes the run root") from exc
        if not ledger_path.is_file():
            raise ValueError("J7 material inventory does not exist")
        ledger_bytes = ledger_path.read_bytes()
        if (
            pointer.get("sha256") != hashlib.sha256(ledger_bytes).hexdigest()
            or pointer.get("size_bytes") != len(ledger_bytes)
        ):
            raise ValueError("J7 material inventory bytes do not match the state pointer")
        try:
            ledger = json.loads(ledger_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("J7 material inventory is not UTF-8 JSON") from exc
        entries = ledger.get("entries") if isinstance(ledger, dict) else None
        if not isinstance(entries, list):
            raise ValueError("J7 material inventory entries are invalid")
        entries_by_source = {
            entry["source_id"]: entry
            for entry in entries
            if isinstance(entry, dict)
            and isinstance(entry.get("source_id"), str)
            and entry.get("source_id")
        }

        raw_inputs = payload.get("input_artifacts")
        if raw_inputs is None:
            raw_inputs = {}
        if not isinstance(raw_inputs, dict):
            raise ValueError("J7 input_artifacts must be an object")
        inputs = copy.deepcopy(raw_inputs)
        intent = payload["intent"]
        figures = intent.get("figures")
        if not isinstance(figures, list):
            raise ValueError("J7 intent figures must be an array")

        material_profile = build_material_profile(task, snapshot)
        primary_candidates = material_profile.get("primary_manuscript_candidates")
        primary = (
            primary_candidates[0]
            if isinstance(primary_candidates, list) and primary_candidates
            else None
        )
        expected_main_figures = set(
            material_profile.get("main_manuscript_figure_source_ids") or []
        )
        if isinstance(primary, dict) and expected_main_figures:
            coverage = intent.get("material_coverage")
            if not isinstance(coverage, dict):
                raise ValueError(
                    "J7 material coverage is required when a populated primary manuscript exists"
                )
            if coverage.get("primary_manuscript_source_id") != primary.get(
                "source_id"
            ):
                raise ValueError("J7 material coverage selects the wrong primary manuscript")
            raw_dispositions = coverage.get("figure_dispositions")
            dispositions = (
                raw_dispositions if isinstance(raw_dispositions, list) else []
            )
            by_source = {
                item.get("source_id"): item
                for item in dispositions
                if isinstance(item, dict)
                and isinstance(item.get("source_id"), str)
            }
            if set(by_source) != expected_main_figures:
                raise ValueError(
                    "J7 material coverage must disposition every figure referenced by the primary manuscript"
                )
            selected_source_ids = {
                figure.get("current_asset", {}).get("artifact_id")
                for figure in figures
                if isinstance(figure, dict)
                and isinstance(figure.get("current_asset"), dict)
            }
            omitted = []
            for source_id, disposition in by_source.items():
                outcome = disposition.get("disposition")
                if outcome == "selected":
                    if source_id not in selected_source_ids:
                        raise ValueError(
                            f"J7 selected material figure is absent from intent: {source_id}"
                        )
                elif outcome in {"supplementary", "omit"}:
                    omitted.append(source_id)
                    if not isinstance(disposition.get("reason"), str) or not str(
                        disposition.get("reason")
                    ).strip():
                        raise ValueError(
                            f"J7 non-main figure disposition needs a reason: {source_id}"
                        )
                else:
                    raise ValueError(
                        f"J7 material figure disposition is invalid: {source_id}"
                    )
            if omitted:
                if not isinstance(user_message, str) or not user_message.strip():
                    raise ValueError(
                        "J7 figure omission or supplementary disposition requires the current user's Web answer"
                    )
                confirmation_sha256 = hashlib.sha256(
                    user_message.strip().encode("utf-8")
                ).hexdigest()
                if coverage.get("user_confirmation_sha256") != confirmation_sha256:
                    raise ValueError(
                        "J7 figure disposition is not bound to the current user's Web answer"
                    )
            coverage["profile_sha256"] = material_profile["profile_sha256"]
            coverage["status"] = "PASS"
            coverage["external_action_authorized"] = False

        def canonical_hash(value: dict[str, Any]) -> str:
            encoded = (
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            return hashlib.sha256(encoded).hexdigest()

        existing_pointers = snapshot.get("academic_base_artifacts")
        if not isinstance(existing_pointers, dict):
            existing_pointers = {}

        def reuse_stable_existing_asset(
            artifact_id: str, candidate: dict[str, Any]
        ) -> dict[str, Any]:
            """Keep a legacy J7 manifest byte-stable when its source did not move.

            Older manifests bound the revision-specific material-ledger receipt
            hash.  Recreating them at a later revision changed only that receipt
            hash and incorrectly looked like source-material drift.  Reuse is
            allowed only after every source identity field still matches the
            freshly verified ledger entry and object bytes.
            """

            existing_pointer = existing_pointers.get(artifact_id)
            if not isinstance(existing_pointer, dict):
                return candidate
            raw_path = existing_pointer.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                return candidate
            existing_path = (run_root / raw_path).resolve()
            try:
                existing_path.relative_to(run_root)
            except ValueError:
                return candidate
            if not existing_path.is_file():
                return candidate
            existing_bytes = existing_path.read_bytes()
            if (
                existing_pointer.get("sha256")
                != hashlib.sha256(existing_bytes).hexdigest()
                or existing_pointer.get("size_bytes") != len(existing_bytes)
            ):
                return candidate
            try:
                existing = json.loads(existing_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return candidate
            if not isinstance(existing, dict):
                return candidate
            stable_fields = (
                "contract",
                "schema_version",
                "source_id",
                "grant_id",
                "relative_path",
                "object_path",
                "media_type",
                "sha256",
                "size_bytes",
                "external_action_authorized",
            )
            if all(existing.get(field) == candidate.get(field) for field in stable_fields):
                return existing
            return candidate

        current_revision = snapshot.get("revision")
        if not isinstance(current_revision, int) or current_revision < 0:
            raise ValueError("J7 snapshot revision is invalid")

        def bind_asset(asset: Any, *, label: str) -> tuple[str, str]:
            if not isinstance(asset, dict):
                raise ValueError(f"J7 {label} descriptor must be an object")
            artifact_id = asset.get("artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id:
                raise ValueError(f"J7 {label} has no artifact_id")
            asserted_sha256 = asset.get("sha256")
            if (
                not isinstance(asserted_sha256, str)
                or len(asserted_sha256) != 64
                or any(character not in "0123456789abcdef" for character in asserted_sha256)
            ):
                raise ValueError(f"J7 {label} has no exact SHA-256 assertion")
            entry = entries_by_source.get(artifact_id)
            if entry is not None:
                object_path = entry.get("object_path")
                if not isinstance(object_path, str) or not object_path.strip():
                    raise ValueError(f"J7 material object path is missing: {artifact_id}")
                object_file = (run_root / object_path).resolve()
                try:
                    object_file.relative_to(run_root)
                except ValueError as exc:
                    raise ValueError(
                        f"J7 material object escapes the run root: {artifact_id}"
                    ) from exc
                if not object_file.is_file():
                    raise ValueError(f"J7 material object does not exist: {artifact_id}")
                object_bytes = object_file.read_bytes()
                file_sha256 = hashlib.sha256(object_bytes).hexdigest()
                if (
                    entry.get("sha256") != file_sha256
                    or entry.get("size_bytes") != len(object_bytes)
                ):
                    raise ValueError(
                        f"J7 material object bytes do not match the ledger: {artifact_id}"
                    )
                if asserted_sha256 != file_sha256:
                    raise ValueError(
                        f"J7 {label} SHA-256 does not match the material ledger: {artifact_id}"
                    )
                candidate_manifest = {
                    "contract": "paperspine5.figure-source-asset",
                    "schema_version": "1.0",
                    "source_id": artifact_id,
                    "grant_id": entry.get("grant_id"),
                    "relative_path": entry.get("relative_path"),
                    "object_path": object_path,
                    "media_type": entry.get("media_type"),
                    "sha256": file_sha256,
                    "size_bytes": len(object_bytes),
                    "source_ledger_sha256": (
                        ledger.get("snapshot_sha256")
                        or pointer.get("snapshot_sha256")
                        or pointer["sha256"]
                    ),
                    "external_action_authorized": False,
                }
                inputs[artifact_id] = reuse_stable_existing_asset(
                    artifact_id, candidate_manifest
                )
            artifact = inputs.get(artifact_id)
            if not isinstance(artifact, dict):
                raise ValueError(f"J7 {label} has no actual input artifact: {artifact_id}")
            runner_sha256 = canonical_hash(artifact)
            if entry is None and asserted_sha256 != runner_sha256:
                raise ValueError(
                    f"J7 {label} SHA-256 does not match the actual input artifact: {artifact_id}"
                )
            asset["sha256"] = runner_sha256
            asset["revision_id"] = str(current_revision)
            return asserted_sha256, runner_sha256

        for index, figure in enumerate(figures):
            if not isinstance(figure, dict):
                raise ValueError(f"J7 figure {index} must be an object")
            rebound_assets: list[tuple[str, str, str]] = []
            current_asset = figure.get("current_asset")
            if current_asset is not None:
                asserted, rebound = bind_asset(current_asset, label="current asset")
                rebound_assets.append((asserted, rebound, "current"))
            candidate_assets = figure.get("candidate_assets", [])
            if not isinstance(candidate_assets, list):
                raise ValueError(f"J7 figure {index} candidate_assets must be an array")
            for candidate in candidate_assets:
                asserted, rebound = bind_asset(candidate, label="candidate asset")
                rebound_assets.append((asserted, rebound, "candidate"))

            comparison = figure.get("independent_comparison")
            if isinstance(comparison, dict):
                asserted_scope = comparison.get("reviewed_asset_hashes")
                expected_asserted_scope = {item[0] for item in rebound_assets}
                if (
                    not isinstance(asserted_scope, list)
                    or any(not isinstance(item, str) for item in asserted_scope)
                    or set(asserted_scope) != expected_asserted_scope
                ):
                    raise ValueError(
                        f"J7 figure {index} comparison does not review the exact asserted asset set"
                    )
                decision = comparison.get("decision")
                selected_assertion = comparison.get("selected_sha256")
                selected_kind = (
                    "candidate"
                    if decision in {"redesign_wins", "candidate_wins"}
                    else "current"
                )
                selected_rebounds = {
                    rebound
                    for asserted, rebound, kind in rebound_assets
                    if asserted == selected_assertion and kind == selected_kind
                }
                if len(selected_rebounds) != 1:
                    raise ValueError(
                        f"J7 figure {index} comparison winner is missing or ambiguous after host binding"
                    )
                comparison["reviewed_asset_hashes"] = sorted(
                    {item[1] for item in rebound_assets}
                )
                comparison["selected_sha256"] = next(iter(selected_rebounds))

            if not candidate_assets and intent.get("mode") == "keep":
                figure.pop("candidate_assets", None)

        # material_coverage is producer-to-host transport.  The Runner derives
        # its authoritative coverage from the verified material ledger, so the
        # host must not leak this non-public field into the exact J7 contract.
        intent.pop("material_coverage", None)

        payload["input_artifacts"] = inputs
        return payload

    @staticmethod
    def _validate_j8_source_text(source_bytes: bytes) -> str:
        """Decode and reject serialized LaTeX that cannot be compiled."""
        try:
            source_text = source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("J8 source file must be UTF-8") from exc
        if len(source_bytes.strip()) < 200:
            raise ValueError("J8 source file is not a substantive manuscript")
        # A serialized JSON/JSONL payload can accidentally persist every
        # LaTeX command with two leading backslashes (for example
        # ``\\\\documentclass``). That is not valid source and can result in
        # a fallback PDF whose visible text is the raw TeX document.
        if re.search(
            r"(?m)^\s*\\\\(?:documentclass|usepackage|begin|end|section|subsection|title|author|date)\b",
            source_text,
            re.IGNORECASE,
        ):
            raise ValueError(
                "J8 source contains doubled LaTeX command slashes; regenerate a real UTF-8 LaTeX source"
            )
        return source_text

    @staticmethod
    def _validate_j8_figure_prose_references(source_bytes: bytes) -> None:
        """Require a labelled, independently cited prose reference per figure."""
        figure_ranges: list[tuple[int, int]] = []
        labels: list[str] = []
        for match in re.finditer(
            rb"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}",
            source_bytes,
            re.IGNORECASE | re.DOTALL,
        ):
            figure_ranges.append((match.start(), match.end()))
            label_match = re.search(rb"\\label\{([^{}]+)\}", match.group(0))
            if label_match is None:
                raise ValueError("J8 figure environment is missing a label")
            labels.append(label_match.group(1).decode("utf-8"))
        if not figure_ranges:
            return
        prose_parts: list[bytes] = []
        cursor = 0
        for start, end in figure_ranges:
            prose_parts.append(source_bytes[cursor:start])
            cursor = end
        prose_parts.append(source_bytes[cursor:])
        prose = b"".join(prose_parts)
        for label in labels:
            label_bytes = re.escape(label.encode("utf-8"))
            if not re.search(
                rb"\\(?:ref|figrefwhole|figpanelref)\*?\s*\{\s*"
                + label_bytes
                + rb"\s*\}(?:\s*\{[^{}]*\})?",
                prose,
                re.IGNORECASE,
            ):
                raise ValueError(
                    f"J8 figure {label!r} is not referenced in manuscript prose"
                )

    @staticmethod
    def _materialize_canonical_inputs(
        *,
        task: dict[str, Any],
        snapshot: dict[str, Any],
        payload: dict[str, Any],
        final_mappings: list | None = None,
    ) -> dict[str, Any]:
        """Verify J8 files and page renders before independent review.

        The producer authors and renders the manuscript inside the task
        workspace, then supplies only task-relative transport paths.  The host
        ignores producer hashes, reads every source/PDF/DOCX/page byte, creates
        deterministic Runner input manifests, and leaves the candidate in
        ``REVIEW_REQUIRED`` until the isolated reviewer completes.
        """

        workspace_root = Path(task["workspace_root"]).resolve()
        run_root = Path(task["run_root"]).resolve()

        def load_pointer(pointer: Any, *, label: str) -> dict[str, Any]:
            if not isinstance(pointer, dict):
                raise ValueError(f"J8 {label} pointer is missing")
            raw_path = pointer.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError(f"J8 {label} pointer path is missing")
            candidate = (run_root / raw_path).resolve()
            try:
                candidate.relative_to(run_root)
            except ValueError as exc:
                raise ValueError(f"J8 {label} pointer escapes the run root") from exc
            if not candidate.is_file():
                raise ValueError(f"J8 {label} pointer does not exist")
            encoded = candidate.read_bytes()
            if (
                pointer.get("sha256") != hashlib.sha256(encoded).hexdigest()
                or pointer.get("size_bytes") != len(encoded)
            ):
                raise ValueError(f"J8 {label} bytes do not match the state pointer")
            try:
                value = json.loads(encoded.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"J8 {label} is not UTF-8 JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"J8 {label} must contain an object")
            return value

        cumulative = load_pointer(
            snapshot.get("academic_inputs"), label="academic inputs"
        )
        # The Runner pointer stores the cumulative contract inside an
        # ``inputs`` envelope.  Keep accepting the unwrapped shape used by
        # older local receipts, but prefer and validate the real persisted
        # envelope so J8 can resume across revisions.
        cumulative_inputs = cumulative.get("inputs")
        if isinstance(cumulative_inputs, dict):
            cumulative = cumulative_inputs
        revision_context = ProductWebAgentRuntime._persisted_revision_context(task, snapshot)
        stage_inputs = cumulative.get("stage_inputs")
        if not isinstance(stage_inputs, dict):
            raise ValueError("J8 cumulative stage inputs are invalid")
        figure_stage = stage_inputs.get("awaiting_figure_intent")
        claim_stage = stage_inputs.get("awaiting_claim_graph")
        intent = figure_stage.get("intent") if isinstance(figure_stage, dict) else None
        claim_nodes = claim_stage.get("nodes") if isinstance(claim_stage, dict) else None
        if not isinstance(intent, dict) or not isinstance(claim_nodes, list):
            raise ValueError("J8 prior figure intent or claim graph is missing")
        expected_figures = intent.get("figures")
        if not isinstance(expected_figures, list):
            raise ValueError("J8 prior figure intent figures are invalid")
        material_ledger = load_pointer(
            snapshot.get("material_inventory"), label="material inventory"
        )
        material_entries = {
            entry.get("source_id"): entry
            for entry in material_ledger.get("entries", [])
            if isinstance(entry, dict) and isinstance(entry.get("source_id"), str)
        }
        transport = payload.pop("host_canonical_files")
        files = transport.get("files") if isinstance(transport, dict) else None
        if not isinstance(files, dict):
            raise ValueError("J8 host_canonical_files.files must be an object")
        word_figure_media_transport = transport.get("word_figure_media")
        expected_suffixes = {
            "source": ".tex",
            "pdf": ".pdf",
            "word": ".docx",
        }
        resolved: dict[str, Path] = {}

        def resolve_workspace_file(raw: Any, *, label: str) -> Path:
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError(f"J8 {label} path is missing")
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = workspace_root / candidate
            candidate = candidate.resolve()
            try:
                candidate.relative_to(workspace_root)
            except ValueError as exc:
                raise ValueError(f"J8 {label} escapes the task workspace") from exc
            if not candidate.is_file():
                raise ValueError(f"J8 {label} does not exist")
            return candidate

        for role, suffix in expected_suffixes.items():
            path = resolve_workspace_file(files.get(role), label=f"{role} file")
            if path.suffix.lower() != suffix:
                raise ValueError(f"J8 {role} file must use {suffix}")
            if isinstance(revision_context, dict) and revision_context.get("status") == "revision_required":
                prior_path = revision_context["initial_review"].get("review_scope", {}).get("files", {}).get(role, {}).get("path")
                if prior_path and path == (workspace_root / prior_path).resolve():
                    raise ValueError(f"J8 {role} revision must use a new path and preserve the reviewed bytes")
            resolved[role] = path
        source_bytes = resolved["source"].read_bytes()
        source_text = ProductWebAgentRuntime._validate_j8_source_text(source_bytes)

        material_profile = build_material_profile(task, snapshot)
        primary_candidates = material_profile.get("primary_manuscript_candidates")
        primary = (
            primary_candidates[0]
            if isinstance(primary_candidates, list) and primary_candidates
            else None
        )
        normalized_source = re.sub(r"(?m)(?<!\\)%.*$", "", source_text)
        lowered_source = normalized_source.lower()
        contradiction_phrases = (
            "not submission-ready",
            "not a submission-ready",
            "not for submission",
            "local acceptance manuscript",
            "acceptance manuscript",
        )
        contradictions = [
            phrase for phrase in contradiction_phrases if phrase in lowered_source
        ]
        if contradictions:
            raise ValueError(
                "J8 manuscript contains readiness-disqualifying internal language: "
                + ", ".join(contradictions)
            )

        canonical_sections = [
            re.sub(r"\s+", " ", match.group(1)).strip()
            for match in re.finditer(
                r"\\(?:section|section\*|subsection|subsection\*)\s*\{([^{}]+)\}",
                normalized_source,
                re.IGNORECASE,
            )
        ]
        canonical_section_text = " | ".join(canonical_sections).lower()
        coverage_ratio: float | None = None
        if isinstance(primary, dict):
            coverage = intent.get("material_coverage")
            if not isinstance(coverage, dict):
                raise ValueError(
                    "J8 cannot bind a populated primary manuscript without J7 material coverage"
                )
            if (
                coverage.get("profile_sha256")
                != material_profile.get("profile_sha256")
                or coverage.get("primary_manuscript_source_id")
                != primary.get("source_id")
            ):
                raise ValueError("J8 material coverage is stale or selects the wrong primary manuscript")
            original_words = int(primary.get("noncomment_word_count") or 0)
            canonical_words = len(re.findall(r"\b[\w'-]+\b", normalized_source))
            coverage_ratio = canonical_words / max(original_words, 1)
            if original_words >= 500 and coverage_ratio < 0.25:
                raise ValueError(
                    "J8 canonical manuscript silently collapses the populated source draft "
                    f"({canonical_words}/{original_words} structural words)"
                )
            if primary.get("has_methods") and not re.search(
                r"\bmethod", canonical_section_text
            ):
                raise ValueError("J8 canonical manuscript drops the source draft's Methods section")
            if primary.get("has_results") and not re.search(
                r"\bresults?\b|\bfindings?\b", canonical_section_text
            ):
                raise ValueError("J8 canonical manuscript drops the source draft's Results section")
            original_class = str(primary.get("document_class") or "").strip()
            canonical_class_match = re.search(
                r"\\documentclass(?:\[[^\]]*\])?\s*\{([^{}]+)\}",
                normalized_source,
                re.IGNORECASE,
            )
            canonical_class = (
                canonical_class_match.group(1).strip()
                if canonical_class_match
                else ""
            )
            generic_classes = {"article", "report", "book", "scrartcl"}
            if (
                original_class
                and original_class.lower() not in generic_classes
                and canonical_class.lower() in generic_classes
            ):
                raise ValueError(
                    "J8 canonical manuscript replaces the supplied target template "
                    f"{original_class!r} with generic class {canonical_class!r}"
                )
            if primary.get("bibliography_dependencies") and not re.search(
                r"\\(?:bibliography|addbibresource)\s*\{",
                normalized_source,
                re.IGNORECASE,
            ):
                raise ValueError("J8 canonical manuscript drops the source bibliography dependency")

        figure_blocks: list[dict[str, Any]] = []
        for block_match in re.finditer(
            rb"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}",
            source_bytes,
            re.IGNORECASE | re.DOTALL,
        ):
            block = block_match.group(0)
            label_match = re.search(rb"\\label\{([^{}]+)\}", block)
            label = (
                label_match.group(1).decode("utf-8") if label_match else None
            )
            for include_match in re.finditer(
                rb"\\includegraphics(?:\[[^\]]*\])?\s*\{([^{}]+)\}",
                block,
                re.IGNORECASE,
            ):
                raw_target = include_match.group(1).decode("utf-8").strip()
                raw_candidate = resolved["source"].parent / raw_target
                candidates = [raw_candidate]
                if not raw_candidate.suffix:
                    candidates.extend(
                        raw_candidate.with_suffix(suffix)
                        for suffix in (".pdf", ".png", ".jpg", ".jpeg", ".svg", ".eps")
                    )
                dependency = next(
                    (path.resolve() for path in candidates if path.is_file()), None
                )
                if dependency is None:
                    raise ValueError(f"J8 source figure dependency is missing: {raw_target}")
                try:
                    dependency.relative_to(workspace_root)
                except ValueError as exc:
                    raise ValueError("J8 source figure dependency escapes the task workspace") from exc
                dependency_bytes = dependency.read_bytes()
                figure_blocks.append(
                    {
                        "label": label,
                        "path": dependency,
                        "sha256": hashlib.sha256(dependency_bytes).hexdigest(),
                        "size_bytes": len(dependency_bytes),
                        "start_byte": block_match.start(),
                        "end_byte": block_match.end(),
                    }
                )
        # Every selected figure must be independently named and cited in the
        # prose; image bytes or a caption label alone are insufficient.
        ProductWebAgentRuntime._validate_j8_figure_prose_references(source_bytes)
        file_bytes = {role: path.read_bytes() for role, path in resolved.items()}
        if not file_bytes["pdf"].startswith(b"%PDF-"):
            raise ValueError("J8 PDF file does not contain PDF bytes")
        # A PDF magic header alone is insufficient: a failed LaTeX build can
        # be wrapped by a fallback renderer as a one-page PDF containing the
        # literal TeX source.  Reject that before page receipts are accepted.
        # Synthetic unit-test fixtures may not be parseable PDFs, so only
        # apply the semantic probe when a real parser can open the document.
        try:
            import fitz

            parsed_pdf = fitz.open(stream=file_bytes["pdf"], filetype="pdf")
            try:
                extracted_pdf_text = "\n".join(
                    page.get_text("text") for page in parsed_pdf
                )
            finally:
                parsed_pdf.close()
        except Exception:
            extracted_pdf_text = ""
        source_markers = re.findall(
            r"(?i)(?:documentclass|usepackage|begin\s*\{document\}|"
            r"end\s*\{document\}|(?:^|\s)section\s*\{)",
            extracted_pdf_text,
        )
        if len(source_markers) >= 2:
            raise ValueError(
                "J8 PDF surface contains literal LaTeX source instead of a rendered manuscript"
            )
        if not file_bytes["word"].startswith(b"PK\x03\x04"):
            raise ValueError("J8 Word file does not contain DOCX/ZIP bytes")
        word_paragraphs = _docx_paragraphs(resolved["word"])
        word_text = "\n".join(word_paragraphs)
        if re.search(
            r"\\(?:begin|end)\s*\{(?:equation|align|aligned|gather|multline)\*?\}|\$\$",
            word_text,
            re.IGNORECASE,
        ):
            raise ValueError("J8 Word surface contains raw LaTeX equation markup")
        if re.search(r"\(\s*(?:[,;]\s*)+\)", word_text):
            raise ValueError("J8 Word surface contains an empty rendered citation group")
        if re.search(r"\\cite|\bcite(?:alt|p|t|author|year)[A-Za-z0-9_:{]", word_text):
            raise ValueError("J8 Word surface contains an unrendered citation command")
        reference_libraries = material_profile.get("reference_libraries")
        expected_reference_count = (
            max(
                (
                    int(item.get("entry_count") or 0)
                    for item in reference_libraries
                    if isinstance(item, dict)
                ),
                default=0,
            )
            if isinstance(reference_libraries, list)
            else 0
        )
        if expected_reference_count:
            reference_headings = {
                "references",
                "bibliography",
                "literature cited",
                "works cited",
                "参考文献",
            }
            heading_index = next(
                (
                    index
                    for index, paragraph in enumerate(word_paragraphs)
                    if paragraph.strip().rstrip(":：").lower() in reference_headings
                ),
                None,
            )
            if heading_index is None:
                raise ValueError("J8 Word surface drops the bibliography heading")
            rendered_reference_count = len(word_paragraphs[heading_index + 1 :])
            if rendered_reference_count < expected_reference_count:
                raise ValueError(
                    "J8 Word surface does not preserve the complete reference library "
                    f"({rendered_reference_count}/{expected_reference_count} entries)"
                )
        word_media_inventory = _docx_media_inventory(resolved["word"])
        unsupported_pdf_media = [
            item["path"]
            for item in word_media_inventory["all_media"]
            if item["suffix"] == ".pdf"
        ]
        if unsupported_pdf_media:
            raise ValueError(
                "J8 Word image-complete surface contains unsupported PDF media: "
                + ", ".join(unsupported_pdf_media)
            )

        raw_inputs = payload.get("input_artifacts")
        if raw_inputs is None:
            raw_inputs = {}
        if not isinstance(raw_inputs, dict):
            raise ValueError("J8 input_artifacts must be an object")
        inputs = copy.deepcopy(raw_inputs)
        binding_spec_path = transport.get("binding_spec_path")
        if binding_spec_path is not None:
            binding_path = resolve_workspace_file(binding_spec_path, label="binding spec file")
            if binding_path.suffix.lower() != ".json":
                raise ValueError("J8 binding spec file must use .json")
            binding_bytes = binding_path.read_bytes()
            inputs["canonical_binding_spec"] = {
                "contract": "paperspine5.local-file-artifact",
                "schema_version": "1.0",
                "artifact_id": "canonical_binding_spec",
                "role": "binding_spec",
                "path": binding_path.relative_to(workspace_root).as_posix(),
                "sha256": hashlib.sha256(binding_bytes).hexdigest(),
                "size_bytes": len(binding_bytes),
                "media_type": "application/json",
                "external_action_authorized": False,
            }
        artifact_ids = {
            "source": "manuscript_source",
            "pdf": "manuscript_pdf",
            "word": "manuscript_word",
        }
        binary_sha256: dict[str, str] = {}
        for role, artifact_id in artifact_ids.items():
            encoded = file_bytes[role]
            binary_sha256[role] = hashlib.sha256(encoded).hexdigest()
            inputs[artifact_id] = {
                "contract": "paperspine5.local-file-artifact",
                "schema_version": "1.0",
                "artifact_id": artifact_id,
                "role": role,
                "path": resolved[role].relative_to(workspace_root).as_posix(),
                "sha256": binary_sha256[role],
                "size_bytes": len(encoded),
                "media_type": {
                    "source": "application/x-tex",
                    "pdf": "application/pdf",
                    "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                }[role],
                "external_action_authorized": False,
            }

        revision = payload.get("manuscript_revision")
        if (
            not isinstance(revision, dict)
            or revision.get("contract")
            != "paperspine5.canonical-manuscript-revision"
        ):
            raise ValueError("J8 canonical manuscript revision is missing")
        revision["artifacts"] = {
            role: {
                "artifact_id": artifact_id,
                "sha256": ProductWebAgentRuntime._canonical_input_hash(
                    inputs[artifact_id]
                ),
                "revision_id": str(task["revision"]),
                "build_status": "REVIEW_REQUIRED",
            }
            for role, artifact_id in artifact_ids.items()
        }
        revision["status"] = "REVIEW_REQUIRED"
        revision["external_action_authorized"] = False

        bundle = payload.get("canonical_bundle")
        if (
            not isinstance(bundle, dict)
            or bundle.get("contract") != "paperspine5.canonical-artifact-bundle"
        ):
            raise ValueError("J8 canonical artifact bundle is missing")
        subject_stub = {
            "task_id": task["task_id"],
            "revision_id": str(task["revision"]),
            "input_hashes": {"host-rebind-placeholder": "0" * 64},
        }
        bundle["subject"] = copy.deepcopy(subject_stub)
        revision["subject"] = copy.deepcopy(subject_stub)
        receipts = bundle.get("surface_receipts")
        if not isinstance(receipts, list):
            raise ValueError("J8 surface receipts must be an array")
        by_kind = {
            receipt.get("surface_kind"): receipt
            for receipt in receipts
            if isinstance(receipt, dict)
        }
        if set(by_kind) != {"pdf", "word"} or len(receipts) != 2:
            raise ValueError("J8 requires one PDF and one Word surface receipt")
        for role in ("pdf", "word"):
            receipt = by_kind[role]
            pages = receipt.get("pages")
            page_count = receipt.get("page_count")
            if (
                not isinstance(pages, list)
                or not pages
                or isinstance(page_count, bool)
                or not isinstance(page_count, int)
                or page_count != len(pages)
            ):
                raise ValueError(f"J8 {role} page render is incomplete")
            normalized_pages: list[dict[str, Any]] = []
            observed_numbers: set[int] = set()
            for page in pages:
                if not isinstance(page, dict):
                    raise ValueError(f"J8 {role} page entry must be an object")
                number = page.get("page")
                if (
                    isinstance(number, bool)
                    or not isinstance(number, int)
                    or number < 1
                    or number in observed_numbers
                ):
                    raise ValueError(f"J8 {role} page numbers are invalid")
                observed_numbers.add(number)
                page_path = resolve_workspace_file(
                    page.get("path"), label=f"{role} rendered page {number}"
                )
                if isinstance(revision_context, dict) and revision_context.get("status") == "revision_required":
                    old_pages = revision_context["initial_review"].get("review_scope", {}).get("pages", {}).get(role, [])
                    if any(isinstance(old, dict) and old.get("path") and page_path == (workspace_root / old["path"]).resolve() for old in old_pages):
                        raise ValueError(f"J8 {role} revision must render pages to new paths")
                page_bytes = page_path.read_bytes()
                if not page_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError(f"J8 {role} rendered page is not PNG: {number}")
                normalized_pages.append(
                    {
                        "page": number,
                        "path": page_path.relative_to(workspace_root).as_posix(),
                        "sha256": hashlib.sha256(page_bytes).hexdigest(),
                        "size_bytes": len(page_bytes),
                    }
                )
            if observed_numbers != set(range(1, page_count + 1)):
                raise ValueError(f"J8 {role} page coverage is not contiguous")
            receipt["task_id"] = task["task_id"]
            receipt["revision_id"] = str(task["revision"])
            receipt["source"] = {
                "path": resolved[role].relative_to(workspace_root).as_posix(),
                "sha256": binary_sha256[role],
                "size_bytes": len(file_bytes[role]),
            }
            receipt["pages"] = sorted(normalized_pages, key=lambda item: item["page"])
            receipt["review"] = None
            receipt["status"] = "REVIEW_REQUIRED"
            receipt["blockers"] = []
            receipt["external_action_authorized"] = False
            # Always persist a self-hash for the materialized surface.  J9
            # treats a PASS surface without this receipt hash as stale.
            receipt["receipt_sha256"] = _self_hashed(receipt, "receipt_sha256")

        if expected_figures:
            if (
                not isinstance(word_figure_media_transport, dict)
                or word_figure_media_transport.get("contract")
                != "paperspine5.word-figure-media-transport"
                or word_figure_media_transport.get("schema_version") != "1.0"
            ):
                raise ValueError("J8 Word figure media transport is missing or invalid")
            producer_media_items = word_figure_media_transport.get("items")
            if not isinstance(producer_media_items, list):
                raise ValueError("J8 Word figure media transport items must be an array")
        else:
            producer_media_items = []
        if len(producer_media_items) != len(expected_figures):
            raise ValueError(
                "J8 Word image-complete surface does not map every selected figure "
                f"({len(producer_media_items)}/{len(expected_figures)})"
            )
        visible_by_path = {
            item["path"]: item for item in word_media_inventory["visible_media"]
        }
        expected_sources: dict[str, dict[str, Any]] = {}
        if final_mappings is not None:
            artifacts = snapshot.get("academic_artifacts")
            artifacts = artifacts if isinstance(artifacts, dict) else {}
            accepted_intent = load_pointer(
                artifacts.get("publication.figure-intent"),
                label="accepted figure intent",
            )
            accepted_figures = accepted_intent.get("figures")
            if (
                accepted_intent.get("contract") != "paperspine5.figure-intent"
                or accepted_intent.get("status") != "PASS"
                or accepted_intent.get("external_action_authorized") is not False
                or not isinstance(accepted_figures, list)
            ):
                raise ValueError("J8 accepted figure intent is invalid")
            accepted_by_figure = {
                figure.get("figure_id"): figure
                for figure in accepted_figures
                if isinstance(figure, dict)
                and isinstance(figure.get("figure_id"), str)
            }
            mapping_by_figure: dict[str, dict[str, Any]] = {}
            for item in final_mappings:
                envelope = item.get("envelope") if isinstance(item, dict) else None
                mapping = envelope.get("mapping") if isinstance(envelope, dict) else None
                figure = mapping.get("figure") if isinstance(mapping, dict) else None
                figure_id = figure.get("figure_id") if isinstance(figure, dict) else None
                if not isinstance(figure_id, str) or figure_id in mapping_by_figure:
                    raise ValueError("J8 final figure mappings are incomplete or ambiguous")
                mapping_by_figure[figure_id] = item
            raw_figure_ids = {
                figure.get("figure_id")
                for figure in expected_figures
                if isinstance(figure, dict)
                and isinstance(figure.get("figure_id"), str)
            }
            if (
                len(raw_figure_ids) != len(expected_figures)
                or len(accepted_by_figure) != len(accepted_figures)
                or set(accepted_by_figure) != raw_figure_ids
                or set(mapping_by_figure) != raw_figure_ids
            ):
                raise ValueError("J8 accepted figure selection does not cover the prior intent")
            for figure_id in sorted(raw_figure_ids):
                accepted = accepted_by_figure[figure_id]
                selected = accepted.get("selected_asset")
                item = mapping_by_figure[figure_id]
                envelope = item["envelope"]
                mapping = envelope["mapping"]
                publication = mapping.get("assets", {}).get("publication")
                bridge = envelope.get("accepted_j7")
                binaries = item.get("binaries")
                if (
                    not isinstance(selected, dict)
                    or not isinstance(selected.get("artifact_id"), str)
                    or not isinstance(selected.get("sha256"), str)
                    or not isinstance(publication, dict)
                    or not isinstance(publication.get("sha256"), str)
                    or not isinstance(bridge, dict)
                    or not isinstance(binaries, list)
                    or bridge.get("figure_id") != figure_id
                    or selected.get("artifact_id") != publication.get("artifact_id")
                    or selected.get("sha256")
                    != bridge.get("accepted_candidate_manifest_sha256")
                    or publication.get("sha256")
                    != bridge.get("publication_binary_sha256")
                ):
                    raise ValueError("J8 selected figure media authority is incomplete")
                selected_binaries = [
                    receipt
                    for receipt in binaries
                    if isinstance(receipt, dict)
                    and receipt.get("artifact_id") == selected.get("artifact_id")
                    and receipt.get("sha256") == publication.get("sha256")
                ]
                if len(selected_binaries) != 1:
                    raise ValueError("J8 selected figure binary receipt is missing or ambiguous")
                binary = selected_binaries[0]
                if (
                    not isinstance(binary.get("path"), str)
                    or not binary.get("path")
                    or isinstance(binary.get("size_bytes"), bool)
                    or not isinstance(binary.get("size_bytes"), int)
                    or binary.get("size_bytes") <= 0
                ):
                    raise ValueError("J8 selected figure binary receipt is invalid")
                expected_sources[figure_id] = {
                    "artifact_id": selected["artifact_id"],
                    "entry": {
                        "source_id": selected["artifact_id"],
                        "relative_path": binary["path"],
                        "sha256": binary["sha256"],
                        "size_bytes": binary["size_bytes"],
                    },
                }
        else:
            # Direct legacy callers without current final-map evidence retain
            # the material-ledger path. ProductWeb always supplies mappings at J8.
            for figure in expected_figures:
                figure_id = figure.get("figure_id") if isinstance(figure, dict) else None
                current_asset = (
                    figure.get("current_asset") if isinstance(figure, dict) else None
                )
                artifact_id = (
                    current_asset.get("artifact_id")
                    if isinstance(current_asset, dict)
                    else None
                )
                entry = material_entries.get(artifact_id)
                if (
                    not isinstance(figure_id, str)
                    or not figure_id
                    or not isinstance(artifact_id, str)
                    or not isinstance(entry, dict)
                ):
                    raise ValueError("J8 selected figure media authority is incomplete")
                expected_sources[figure_id] = {
                    "artifact_id": artifact_id,
                    "entry": entry,
                }
        normalized_media_mappings: list[dict[str, Any]] = []
        observed_figure_ids: set[str] = set()
        observed_media_paths: set[str] = set()
        for producer_item in producer_media_items:
            if not isinstance(producer_item, dict):
                raise ValueError("J8 Word figure media mapping must be an object")
            figure_id = producer_item.get("figure_id")
            source_artifact_id = producer_item.get("source_artifact_id")
            word_media_path = producer_item.get("word_media_path")
            conversion_method = producer_item.get("conversion_method")
            expected_source = expected_sources.get(figure_id)
            if (
                not isinstance(expected_source, dict)
                or source_artifact_id != expected_source["artifact_id"]
                or not isinstance(word_media_path, str)
            ):
                raise ValueError("J8 Word figure media mapping changes figure identity")
            if figure_id in observed_figure_ids or word_media_path in observed_media_paths:
                raise ValueError("J8 Word figure media mapping is not one-to-one")
            word_media = visible_by_path.get(word_media_path)
            if not isinstance(word_media, dict):
                raise ValueError(
                    f"J8 Word figure media is not reader-visible: {word_media_path}"
                )
            if word_media.get("suffix") != ".png" or word_media.get("media_type") != "image/png":
                raise ValueError(
                    f"J8 Word selected figure must be visible PNG media: {word_media_path}"
                )
            source_entry = expected_source["entry"]
            source_suffix = PurePosixPath(
                str(source_entry.get("relative_path") or "")
            ).suffix.lower()
            required_method = "pdf-to-png" if source_suffix == ".pdf" else "source-to-png"
            if conversion_method != required_method:
                raise ValueError(
                    f"J8 Word figure conversion method must be {required_method}: {figure_id}"
                )
            observed_figure_ids.add(figure_id)
            observed_media_paths.add(word_media_path)
            normalized_media_mappings.append(
                {
                    "figure_id": figure_id,
                    "source_artifact": {
                        "artifact_id": source_artifact_id,
                        "relative_path": source_entry.get("relative_path"),
                        "sha256": source_entry.get("sha256"),
                        "size_bytes": source_entry.get("size_bytes"),
                    },
                    "word_media": copy.deepcopy(word_media),
                    "conversion": {
                        "method": required_method,
                        "scope": "word-delivery-surface-only",
                        "canonical_source_preserved": True,
                    },
                }
            )
        if observed_figure_ids != set(expected_sources):
            raise ValueError("J8 Word figure media mapping omits a selected figure")
        word_receipt = by_kind["word"]
        word_figure_media_receipt = {
            "contract": "paperspine5.word-figure-media-receipt",
            "contract_version": "1.0",
            "task_id": task["task_id"],
            "revision_id": str(task["revision"]),
            "word_source": copy.deepcopy(word_receipt["source"]),
            "selected_figure_count": len(expected_figures),
            "visible_supported_media_count": len(normalized_media_mappings),
            "mappings": normalized_media_mappings,
            "render_evidence": {
                "surface_kind": "word",
                "page_count": word_receipt["page_count"],
                "pages": copy.deepcopy(word_receipt["pages"]),
            },
            "unsupported_media": [],
            "status": "PASS",
            "external_action_authorized": False,
        }
        word_figure_media_receipt["receipt_sha256"] = hashlib.sha256(
            json.dumps(
                word_figure_media_receipt,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        word_receipt["figure_media"] = word_figure_media_receipt

        figure_receipts = bundle.get("figure_intent_receipts")
        if not isinstance(figure_receipts, list):
            raise ValueError("J8 figure binding receipts must be an array")
        producer_by_figure = {
            receipt.get("figure_id"): receipt
            for receipt in figure_receipts
            if isinstance(receipt, dict)
            and isinstance(receipt.get("figure_id"), str)
        }
        def source_span(start: int, end: int) -> dict[str, Any]:
            return {
                "artifact_id": "manuscript_source",
                "start_byte": start,
                "end_byte": end,
                "sha256": hashlib.sha256(source_bytes[start:end]).hexdigest(),
            }

        normalized_figure_receipts: list[dict[str, Any]] = []
        claim_argument_span: dict[str, Any] | None = None
        for figure in expected_figures:
            if not isinstance(figure, dict):
                raise ValueError("J8 prior figure intent contains an invalid figure")
            figure_id = figure.get("figure_id")
            panels = figure.get("panels")
            if (
                not isinstance(figure_id, str)
                or not isinstance(panels, list)
            ):
                raise ValueError("J8 prior figure intent is incomplete")
            selected_source = expected_sources.get(figure_id)
            if not isinstance(selected_source, dict):
                raise ValueError(f"J8 selected figure source is unavailable: {figure_id}")
            artifact_id = selected_source["artifact_id"]
            entry = selected_source["entry"]
            matching_blocks = [
                block
                for block in figure_blocks
                if block.get("sha256") == entry.get("sha256")
                and block.get("size_bytes") == entry.get("size_bytes")
            ]
            if len(matching_blocks) != 1:
                raise ValueError(
                    f"J8 source must include the exact selected figure bytes once: {figure_id}"
                )
            matched_block = matching_blocks[0]
            producer_receipt = producer_by_figure.get(figure_id)
            producer_binding = (
                producer_receipt.get("body_binding")
                if isinstance(producer_receipt, dict)
                else None
            )
            label = (
                producer_binding.get("figure_label")
                if isinstance(producer_binding, dict)
                else None
            )
            bound_label = matched_block.get("label")
            if isinstance(label, str) and label and label != bound_label:
                raise ValueError(
                    f"J8 figure label does not match the included asset block: {figure_id}"
                )
            if not isinstance(bound_label, str) or not bound_label:
                raise ValueError(f"J8 included figure has no LaTeX label: {figure_id}")
            escaped_label = re.escape(bound_label.encode("utf-8"))
            reference_match = re.search(
                rb"(?:"
                rb"\\(?:ref|autoref|cref|Cref)\*?\s*\{\s*"
                + escaped_label
                + rb"\s*\}"
                + rb"|\\hyperref\s*\[\s*"
                + escaped_label
                + rb"\s*\]"
                + rb"|\\(?:figrefwhole|figpanelref)\s*\{\s*"
                + escaped_label
                + rb"\s*\}"
                + rb")",
                source_bytes,
            )
            if reference_match is None:
                raise ValueError(f"J8 body never references the selected figure: {figure_id}")
            line_start = source_bytes.rfind(b"\n", 0, reference_match.start()) + 1
            line_end = source_bytes.find(b"\n", reference_match.end())
            if line_end < 0:
                line_end = len(source_bytes)
            argument_span = source_span(line_start, line_end)
            evidence_span = source_span(line_start, reference_match.end())
            reference_span = source_span(reference_match.start(), reference_match.end())
            if claim_argument_span is None:
                claim_argument_span = copy.deepcopy(argument_span)
            normalized_panels = []
            for panel in panels:
                panel_id = panel.get("panel_id") if isinstance(panel, dict) else None
                if not isinstance(panel_id, str) or not panel_id:
                    raise ValueError(f"J8 figure panel is invalid: {figure_id}")
                normalized_panels.append(
                    {
                        "binding_id": f"{figure_id}:{panel_id}:body",
                        "panel_id": panel_id,
                        "argument_role": "explains_evidence",
                        "result_span": {
                            "artifact_id": artifact_id,
                            "start_byte": 0,
                            "end_byte": entry.get("size_bytes"),
                            "sha256": entry.get("sha256"),
                        },
                        "argument_span": copy.deepcopy(argument_span),
                        "evidence_phrase_span": copy.deepcopy(evidence_span),
                        "reference_span": copy.deepcopy(reference_span),
                    }
                )
            normalized_figure_receipts.append(
                {
                    "contract": "paperspine5.figure-intent-receipt",
                    "contract_version": "1.0",
                    "subject": copy.deepcopy(subject_stub),
                    "figure_id": figure_id,
                    "figure_role": (
                        producer_receipt.get("figure_role")
                        if isinstance(producer_receipt, dict)
                        and isinstance(producer_receipt.get("figure_role"), str)
                        else "scientific_evidence"
                    ),
                    "label": bound_label,
                    "final_asset": {
                        "artifact_id": artifact_id,
                        "sha256": entry.get("sha256"),
                    },
                    "panels": normalized_panels,
                    "status": "REVIEW_REQUIRED",
                    "quality_claim": "host-verified byte/span binding pending independent page review",
                    "external_action_authorized": False,
                    "receipt_sha256": "0" * 64,
                }
            )
        bundle["figure_intent_receipts"] = normalized_figure_receipts

        if claim_argument_span is None:
            body_match = re.search(rb"\\begin\{document\}\s*(.{40,400})", source_bytes, re.DOTALL)
            if body_match is None:
                raise ValueError("J8 source has no substantive reader-body span")
            claim_argument_span = source_span(body_match.start(1), body_match.end(1))

        material_coverage = {
            "contract": "paperspine5.material-coverage-receipt",
            "contract_version": "1.0",
            "subject": copy.deepcopy(subject_stub),
            "profile_sha256": material_profile.get("profile_sha256"),
            "material_snapshot_sha256": material_profile.get(
                "material_snapshot_sha256"
            ),
            "primary_manuscript_source_id": (
                primary.get("source_id") if isinstance(primary, dict) else None
            ),
            "primary_manuscript_relative_path": (
                primary.get("relative_path") if isinstance(primary, dict) else None
            ),
            "canonical_source_sha256": binary_sha256["source"],
            "source_word_coverage_ratio": coverage_ratio,
            "canonical_sections": canonical_sections,
            "selected_figure_source_ids": [
                receipt["final_asset"]["artifact_id"]
                for receipt in normalized_figure_receipts
            ],
            "included_figure_binary_sha256": sorted(
                receipt["final_asset"]["sha256"]
                for receipt in normalized_figure_receipts
            ),
            "word_figure_media_receipt_sha256": word_figure_media_receipt[
                "receipt_sha256"
            ],
            "readiness_contradictions": contradictions,
            "status": "PASS",
            "external_action_authorized": False,
        }
        material_coverage["receipt_sha256"] = hashlib.sha256(
            json.dumps(
                material_coverage,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        bundle["material_coverage"] = material_coverage

        core_claim_ids = [
            node.get("node_id")
            for node in claim_nodes
            if isinstance(node, dict)
            and node.get("node_type") == "claim"
            and node.get("core") is True
            and isinstance(node.get("node_id"), str)
        ]
        if not core_claim_ids:
            raise ValueError("J8 claim graph has no retained core claim")
        final_claim_index = {
            "contract": "paperspine5.final-claim-index",
            "contract_version": "1.0",
            "subject": copy.deepcopy(subject_stub),
            "claims": [
                {
                    "claim_id": claim_id,
                    "disposition": "retained",
                    "reader_surfaces": [
                        {
                            "surface": "body",
                            "span": copy.deepcopy(claim_argument_span),
                        }
                    ],
                }
                for claim_id in core_claim_ids
            ],
            "reader_inventory": [
                {
                    "claim_id": claim_id,
                    "surface": "body",
                    "span": copy.deepcopy(claim_argument_span),
                }
                for claim_id in core_claim_ids
            ],
            "retention_omission": [
                {
                    "claim_id": claim_id,
                    "disposition": "retained",
                    "omission_allowed": False,
                    "omission_reason": None,
                }
                for claim_id in core_claim_ids
            ],
            "status": "REVIEW_REQUIRED",
            "quality_claim": "host-derived retained-claim inventory pending independent page review",
            "external_action_authorized": False,
            "receipt_sha256": "0" * 64,
        }
        bundle["final_claim_index"] = final_claim_index
        bundle["status"] = "REVIEW_REQUIRED"
        bundle["blockers"] = []
        bundle["external_action_authorized"] = False
        payload["input_artifacts"] = inputs
        payload["canonical_bundle"] = ProductWebAgentRuntime._rehash_known_contracts(
            bundle
        )
        payload["manuscript_revision"] = (
            ProductWebAgentRuntime._rehash_known_contracts(revision)
        )
        return payload

    @staticmethod
    def _current_canonical_inputs(
        *, task: dict[str, Any], snapshot: dict[str, Any], load_pointer: Any
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Resolve persisted J8 roles, never caller aliases or unbound filenames."""
        academic = snapshot.get("academic_artifacts", {})
        base = snapshot.get("academic_base_artifacts", {})
        head = load_pointer(academic.get("publication.manuscript-head"), label="manuscript head")
        subject = head.get("subject", {})
        current_revision = str(snapshot.get("revision", task["revision"]))
        retained_state = task.get("state", {}).get("runner", {})
        retained_head = (
            isinstance(subject, dict)
            and isinstance(subject.get("revision_id"), str)
            and subject["revision_id"].isdigit()
            and int(subject["revision_id"]) < int(current_revision)
            and snapshot.get("stage") == retained_state.get("stage") == "awaiting_package"
            and (retained_state.get("academic_artifacts") or {}).get("publication.manuscript-head")
            == academic.get("publication.manuscript-head")
        )
        if (
            head.get("contract") != "paperspine5.manuscript-head"
            or head.get("status") != "PASS"
            or head.get("external_action_authorized") is not False
            or _self_hashed(head, "head_sha256") != head
            or not isinstance(subject, dict)
            or subject.get("task_id") != task["task_id"]
            or (subject.get("revision_id") != current_revision and not retained_head)
        ):
            raise ValueError("Current manuscript head hash, task, revision or status is invalid")
        cumulative = load_pointer(snapshot.get("academic_inputs"), label="academic cumulative inputs")
        canonical = cumulative.get("inputs", cumulative).get("stage_inputs", {}).get("awaiting_canonical")
        bundle = canonical.get("canonical_bundle") if isinstance(canonical, dict) else None
        if not isinstance(bundle, dict) or _self_hashed(bundle, "bundle_sha256") != bundle:
            raise ValueError("Current canonical bundle is missing or has an invalid hash")
        if bundle.get("bundle_sha256") != head.get("canonical_bundle_sha256"):
            from paperspine_figure_integration.academic_stage_orchestrator import rebind_canonical_bundle_to_head

            bundle = rebind_canonical_bundle_to_head(bundle, head)
        revision = canonical.get("manuscript_revision")
        if retained_head and isinstance(revision, dict):
            # Failed J10 replay may have rebound its cumulative input to the
            # attempt revision without accepting a new head. Recover only the
            # state-selected head's subject; the exact bundle hash above and
            # role/manifest/byte checks below still bind all scientific inputs.
            from paperspine_figure_integration.academic_stage_orchestrator import _rebind_current, QualitySubject

            if (_self_hashed(revision, "revision_sha256") != revision
                    or revision.get("subject", {}).get("task_id") != task["task_id"]
                    or revision.get("subject", {}).get("revision_id") not in {subject["revision_id"], current_revision}):
                raise ValueError("Retained canonical revision input is invalid or stale")
            revision = _rebind_current(revision, QualitySubject.from_mapping(subject))
        if revision is not None and (
            not isinstance(revision, dict)
            or revision.get("contract") != "paperspine5.canonical-manuscript-revision"
            or revision.get("status") != "PASS"
            or revision.get("external_action_authorized") is not False
            or _self_hashed(revision, "revision_sha256") != revision
            or revision.get("subject") != subject
        ):
            raise ValueError("Current canonical revision is invalid or stale")
        manifests = {}
        for role in ("source", "pdf", "word"):
            # Older accepted inputs without a typed revision may use the fixed
            # ID only when its exact registered payload is bound to this head.
            ref = revision.get("artifacts", {}).get(role) if revision is not None else None
            if revision is not None and (
                not isinstance(ref, dict)
                or not isinstance(ref.get("artifact_id"), str)
                or not ref["artifact_id"]
                or ref.get("sha256") != head.get(f"{role}_sha256")
                or ref.get("revision_id") != subject.get("revision_id")
                or ref.get("build_status") != "PASS"
            ):
                raise ValueError(f"Current canonical {role} reference is invalid")
            artifact_id = ref["artifact_id"] if ref is not None else f"manuscript_{role}"
            pointer = base.get(artifact_id)
            manifest = load_pointer(pointer, label=f"manuscript {role}")
            byte_evidence = manifest.get("contract") == "paperspine5.local-file-byte-evidence"
            expected_media = {"source": "application/x-tex", "pdf": "application/pdf", "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}[role]
            if (
                manifest.get("contract") not in {"paperspine5.local-file-artifact", "paperspine5.local-file-byte-evidence"}
                or manifest.get("artifact_id") != artifact_id
                or manifest.get("schema_version") != "1.0"
                or manifest.get("external_action_authorized") is not False
                or (not byte_evidence and manifest.get("role") != role)
                or (manifest.get("media_type") is not None and manifest["media_type"] != expected_media)
                or (byte_evidence and (
                    manifest.get("media_type") != expected_media
                    or manifest.get("build_status") != "PASS"
                    or manifest.get("byte_state") != "present-and-hashed"
                    or not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("source_bytes_sha256") or ""))
                ))
            ):
                raise ValueError(f"Current canonical {role} manifest is invalid")
            input_hash = ProductWebAgentRuntime._canonical_input_hash(manifest)
            if input_hash != head.get(f"{role}_sha256") or pointer.get("sha256") != input_hash:
                raise ValueError(f"Current canonical {role} manifest is not bound to the current head")
            if ref is not None and subject.get("input_hashes", {}).get(artifact_id) != input_hash:
                raise ValueError(f"Current canonical {role} input is absent from the head subject")
            binary_hash = manifest.get("source_bytes_sha256") if byte_evidence else manifest.get("sha256")
            if ref is not None and ref.get("source_bytes_sha256", binary_hash) != binary_hash:
                raise ValueError(f"Current canonical {role} reference binary hash differs")
            manifests[role] = manifest
        if len({m["artifact_id"] for m in manifests.values()}) != 3:
            raise ValueError("Current canonical roles repeat an artifact identity")
        return head, canonical, bundle, manifests

    @staticmethod
    def _materialize_publication_review_inputs(
        *,
        task: dict[str, Any],
        snapshot: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Bind J9 to the current J8 head, actual files, and rendered pages."""

        workspace_root = Path(task["workspace_root"]).resolve()
        run_root = Path(task["run_root"]).resolve()

        def load_pointer(pointer: Any, *, label: str) -> dict[str, Any]:
            if not isinstance(pointer, dict):
                raise ValueError(f"J9 {label} pointer is missing")
            raw_path = pointer.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError(f"J9 {label} pointer path is missing")
            candidate = (run_root / raw_path).resolve()
            try:
                candidate.relative_to(run_root)
            except ValueError as exc:
                raise ValueError(f"J9 {label} pointer escapes the run root") from exc
            if not candidate.is_file():
                raise ValueError(f"J9 {label} pointer target does not exist")
            encoded = candidate.read_bytes()
            if (
                pointer.get("sha256") != hashlib.sha256(encoded).hexdigest()
                or pointer.get("size_bytes") != len(encoded)
            ):
                raise ValueError(f"J9 {label} pointer bytes changed")
            try:
                value = json.loads(encoded.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"J9 {label} pointer is not UTF-8 JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"J9 {label} pointer must contain an object")
            return value

        base_pointers = snapshot.get("academic_base_artifacts")
        academic_pointers = snapshot.get("academic_artifacts")
        if not isinstance(base_pointers, dict) or not isinstance(
            academic_pointers, dict
        ):
            raise ValueError("J9 Runner artifact ledgers are missing")
        head, canonical_input, canonical_bundle, manifests = ProductWebAgentRuntime._current_canonical_inputs(
            task=task, snapshot=snapshot, load_pointer=load_pointer
        )

        target_pointer = academic_pointers.get("target_authority")
        target_authority = load_pointer(
            target_pointer,
            label="target authority",
        )
        target_authority_sha256 = (
            target_pointer.get("sha256") if isinstance(target_pointer, dict) else None
        )
        if not isinstance(target_authority_sha256, str):
            raise ValueError("J9 target authority pointer hash is missing")
        target_obligation_ledger = _derive_target_obligation_ledger(
            target_authority,
            target_authority_sha256,
        )

        surface_by_kind = {
            str(item.get("surface_kind")): item
            for item in canonical_bundle.get("surface_receipts", [])
            if isinstance(item, dict)
        }
        review_surface = surface_by_kind.get("pdf")
        if (
            not isinstance(review_surface, dict)
            or review_surface.get("status") != "PASS"
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(review_surface.get("receipt_sha256") or "")
            )
        ):
            raise ValueError("J9 current PDF review surface is not hash-bound PASS")

        verified_files: dict[str, dict[str, Any]] = {}
        for role, manifest in manifests.items():
            legacy = manifest.get("contract") == "paperspine5.local-file-byte-evidence"
            raw_path = manifest.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError(f"J9 {role} manifest path is missing")
            candidate = (workspace_root / raw_path).resolve()
            try:
                candidate.relative_to(workspace_root)
            except ValueError as exc:
                raise ValueError(f"J9 {role} file escapes the task workspace") from exc
            if not candidate.is_file() or candidate.suffix.lower() != {"source": ".tex", "pdf": ".pdf", "word": ".docx"}[role]:
                raise ValueError(f"J9 {role} file does not exist or has the wrong suffix")
            encoded = candidate.read_bytes()
            binary_hash = manifest.get("source_bytes_sha256") if legacy else manifest.get("sha256")
            if (
                binary_hash != hashlib.sha256(encoded).hexdigest()
                or manifest.get("size_bytes") != len(encoded)
            ):
                raise ValueError(f"J9 {role} file differs from the J8 manifest")
            if role == "source":
                try:
                    encoded.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ValueError("J9 source file is not UTF-8") from exc
            elif role == "pdf" and not encoded.startswith(b"%PDF-"):
                raise ValueError("J9 PDF file does not contain PDF bytes")
            elif role == "word" and not encoded.startswith(b"PK\x03\x04"):
                raise ValueError("J9 Word file does not contain DOCX/ZIP bytes")
            expected_input_hash = ProductWebAgentRuntime._canonical_input_hash(manifest)
            if head.get(f"{role}_sha256") != expected_input_hash:
                raise ValueError(f"J9 {role} manifest is not bound to the current head")
            verified_files[role] = {
                "artifact_id": manifest["artifact_id"],
                "path": candidate.relative_to(workspace_root).as_posix(),
                "binary_sha256": binary_hash,
                "size_bytes": len(encoded),
                "runner_input_sha256": expected_input_hash,
            }

        transport = payload.pop("host_review_pages")
        pages: dict[str, list[dict[str, Any]]] = {}
        total_pages = 0
        for surface in ("pdf", "word"):
            # Two independently bound surfaces may legitimately share an exact
            # render (for example a DOCX export used as the canonical PDF).
            # Repeated pages within one surface are still forbidden.
            seen_paths: set[Path] = set()
            raw_pages = transport.get(surface) if isinstance(transport, dict) else None
            if not isinstance(raw_pages, list) or not raw_pages:
                raise ValueError(f"J9 {surface} review pages are missing")
            canonical_pages = surface_by_kind.get(surface, {}).get("pages")
            if not isinstance(canonical_pages, list) or len(canonical_pages) != len(raw_pages):
                raise ValueError(f"J9 {surface} review pages differ from canonical page coverage")
            normalized: list[dict[str, Any]] = []
            for number, raw_path in enumerate(raw_pages, start=1):
                if not isinstance(raw_path, str) or not raw_path.strip():
                    raise ValueError(f"J9 {surface} review page path is missing")
                candidate = (workspace_root / raw_path).resolve()
                try:
                    candidate.relative_to(workspace_root)
                except ValueError as exc:
                    raise ValueError(
                        f"J9 {surface} review page escapes the task workspace"
                    ) from exc
                if not candidate.is_file():
                    raise ValueError(f"J9 {surface} review page does not exist")
                encoded = candidate.read_bytes()
                if not encoded.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError(f"J9 {surface} review page is not PNG")
                canonical_page = canonical_pages[number - 1]
                if not isinstance(canonical_page, dict) or canonical_page.get("page") != number or canonical_page.get("sha256") != hashlib.sha256(encoded).hexdigest():
                    raise ValueError(f"J9 {surface} review page differs from the current canonical render")
                if candidate in seen_paths:
                    raise ValueError(f"J9 {surface} review page is duplicated")
                seen_paths.add(candidate)
                normalized.append(
                    {
                        "page": number,
                        "path": candidate.relative_to(workspace_root).as_posix(),
                        "sha256": hashlib.sha256(encoded).hexdigest(),
                        "size_bytes": len(encoded),
                    }
                )
            pages[surface] = normalized
            total_pages += len(normalized)
        # Review transport must cover every page of both canonical surfaces.
        # A fixed 40-page cap rejected a valid 20-page PDF + 21-page DOCX
        # manuscript (41 images) before the reviewer could inspect it. Keep a
        # bounded transport guard while allowing ordinary long manuscripts.
        if total_pages > 60:
            raise ValueError("J9 independent review exceeds the 60-page image limit")

        bound = copy.deepcopy(payload)
        for field in ("initial_review", "revision_diff", "re_review", "closure_revisions"):
            bound.pop(field, None)
        bound["producer_ids"] = ["paperspine-web-producer"]
        bound["_host_j9_review"] = {
            "contract": "paperspine5.host-j9-review-materialization",
            "schema_version": "1.0",
            "manuscript_head_sha256": head.get("head_sha256"),
            "subject": copy.deepcopy(head.get("subject")),
            "manuscript_head": copy.deepcopy(head),
            "canonical_bundle_sha256": head.get("canonical_bundle_sha256"),
            "files": verified_files,
            "pages": pages,
            "target_obligation_ledger": target_obligation_ledger,
            "target_review_artifact": {
                "artifact_id": "surface_pdf",
                "artifact_sha256": review_surface["receipt_sha256"],
            },
            "revision_context": ProductWebAgentRuntime._persisted_revision_context(task, snapshot),
            "revision_response": copy.deepcopy(canonical_input.get("revision_response")),
            "external_action_authorized": False,
        }
        return bound

    @staticmethod
    def _validate_package_request(payload: dict[str, Any]) -> None:
        """Reject malformed explicit legacy payloads before any package write."""
        from paperspine_figure_integration.quality_readiness import REQUIRED_PREDICATES

        required = {"surface_receipts", "target_obligations", "package_mapping", "author_close",
            "package_manifest", "predicates", "readiness_obligation_manifest", "cycle"}
        allowed = required | {"requested_scope", "input_artifacts", "current_artifacts"}
        if not required.issubset(payload) or set(payload) - allowed:
            raise ValueError("J10 use exact {requested_scope: local_delivery} or a complete explicit package payload")
        if payload.get("requested_scope", "submission_package") not in {"manuscript", "local_delivery", "submission_package"}:
            raise ValueError("J10 requested_scope is invalid")
        for field, contract in (("target_obligations", "paperspine5.target-obligation-ledger"),
            ("package_manifest", "paperspine5.target-package-manifest"),
            ("readiness_obligation_manifest", "paperspine5.readiness-obligation-manifest")):
            item = payload[field]
            if not isinstance(item, dict) or item.get("contract") != contract or item.get("contract_version") != "1.0":
                raise ValueError(f"J10 explicit {field} is missing or invalid")
        if payload["package_manifest"].get("status") not in {"PASS", "BLOCKED"} or payload["package_manifest"].get("external_action_authorized") is not False:
            raise ValueError("J10 explicit package manifest is invalid")
        if payload["package_manifest"].get("archive_artifact_id") not in {None, "", "bundle_archive"}:
            raise ValueError("J10 package manifest uses an unsupported archive artifact")
        manifest = payload["readiness_obligation_manifest"]
        if manifest.get("required_predicates_by_tier") != {tier.value: sorted(names) for tier, names in REQUIRED_PREDICATES.items()}:
            raise ValueError("J10 readiness obligation set is invalid")
        predicates = payload["predicates"]
        expected = {name: tier.value for tier, names in REQUIRED_PREDICATES.items() for name in names}
        if not isinstance(predicates, list) or len(predicates) != len(expected):
            raise ValueError("J10 readiness predicate set is incomplete")
        observed = set()
        for item in predicates:
            if (not isinstance(item, dict) or item.get("predicate_id") not in expected
                or item["predicate_id"] in observed or item.get("tier") != expected[item["predicate_id"]]
                or item.get("contract") != "paperspine5.readiness-predicate" or item.get("contract_version") != "1.0"
                or item.get("status") not in {"true", "false", "unknown", "stale"}
                or item.get("hard_blocker") is not True or not isinstance(item.get("reason"), str) or not item["reason"].strip()):
                raise ValueError("J10 explicit readiness predicate is invalid")
            observed.add(item["predicate_id"])
        if not isinstance(payload["input_artifacts"] if "input_artifacts" in payload else {}, dict):
            raise ValueError("J10 input_artifacts must be an object")
        if not isinstance(payload["author_close"], list):
            raise ValueError("J10 author_close must be an array")
        if not isinstance(payload["surface_receipts"], list) or not payload["surface_receipts"] or any(not isinstance(item, dict) or item.get("contract") != "paperspine5.surface-receipt" for item in payload["surface_receipts"]):
            raise ValueError("J10 explicit surface receipts are invalid")
        if not isinstance(payload["package_mapping"], list) or not payload["package_mapping"] or any(not isinstance(item, dict) or not item.get("obligation_id") or not item.get("artifact_id") or not isinstance(item.get("status"), bool) for item in payload["package_mapping"]):
            raise ValueError("J10 explicit package mapping is invalid")
        from paperspine_figure_integration.publication_pipeline import _cycle_invalidation

        if _cycle_invalidation(payload["cycle"])[1]:
            raise ValueError("J10 explicit package cycle is invalid")

    @staticmethod
    def _materialize_target_package_inputs(
        *,
        task: dict[str, Any],
        snapshot: dict[str, Any],
        payload: dict[str, Any],
        user_message: str | None = None,
        final_mappings: list | None = None,
    ) -> dict[str, Any]:
        workspace_root = Path(task["workspace_root"]).resolve()
        try:
            return ProductWebAgentRuntime._materialize_target_package_inputs_impl(
                task=task,
                snapshot=snapshot,
                payload=payload,
                user_message=user_message,
                final_mappings=final_mappings,
            )
        finally:
            _cleanup_portable_render_temporary_roots(workspace_root)

    @staticmethod
    def _materialize_target_package_inputs_impl(
        *,
        task: dict[str, Any],
        snapshot: dict[str, Any],
        payload: dict[str, Any],
        user_message: str | None = None,
        final_mappings: list | None = None,
    ) -> dict[str, Any]:
        """Create and register the current local-only J10/J11 package archive.

        The producer is allowed to describe target obligations and author-close
        facts, but it is not a trusted file packager.  The host therefore
        reloads the current Runner-bound J8 file manifests, verifies the actual
        workspace bytes, resolves source dependencies inside the task
        workspace, builds a deterministic ZIP, and registers a JSON descriptor
        for those ZIP bytes as the ``bundle_archive`` Runner input.  The
        package manifest's archive hash is always replaced with the canonical
        hash of that descriptor; a producer-supplied archive hash is never
        trusted.
        """

        workspace_root = Path(task["workspace_root"]).resolve()
        run_root = Path(task["run_root"]).resolve()

        def load_pointer(pointer: Any, *, label: str) -> dict[str, Any]:
            if not isinstance(pointer, dict):
                raise ValueError(f"J10 {label} pointer is missing")
            raw_path = pointer.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError(f"J10 {label} pointer path is missing")
            from local_package_files import bounded_path

            candidate = bounded_path(run_root, raw_path)
            try:
                candidate.relative_to(run_root)
            except ValueError as exc:
                raise ValueError(f"J10 {label} pointer escapes the run root") from exc
            if not candidate.is_file():
                raise ValueError(f"J10 {label} pointer target does not exist")
            encoded = candidate.read_bytes()
            if (
                pointer.get("sha256") != hashlib.sha256(encoded).hexdigest()
                or pointer.get("size_bytes") != len(encoded)
            ):
                raise ValueError(f"J10 {label} pointer bytes changed")
            try:
                value = json.loads(encoded.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"J10 {label} pointer is not UTF-8 JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"J10 {label} pointer must contain an object")
            return value

        from local_package_files import bounded_path, collect_package_files, verify_inventory_bytes
        from paperspine_figure_integration.local_package_preparation import prepare_local_package_inputs

        bounded_path(Path(task["workspace_root"]), Path(task["workspace_root"]), must_exist=False)
        bounded_path(Path(task["run_root"]), Path(task["run_root"]), must_exist=False)
        minimal_request = payload == {"requested_scope": "local_delivery"}
        if not minimal_request:
            ProductWebAgentRuntime._validate_package_request(payload)
        base_pointers = snapshot.get("academic_base_artifacts")
        if not isinstance(base_pointers, dict):
            raise ValueError("J10 Runner base artifact ledger is missing")
        academic_pointers = snapshot.get("academic_artifacts")
        if not isinstance(academic_pointers, dict):
            raise ValueError("J10 Runner academic artifact ledger is missing")
        target_pointer = academic_pointers.get("target_authority")
        target_authority = load_pointer(
            target_pointer,
            label="target authority",
        )
        target_authority_sha256 = (
            target_pointer.get("sha256") if isinstance(target_pointer, dict) else None
        )
        if not isinstance(target_authority_sha256, str):
            raise ValueError("J10 target authority pointer hash is missing")
        host_target_obligations = _derive_target_obligation_ledger(
            target_authority,
            target_authority_sha256,
        )
        head, _, canonical_bundle, manifests = ProductWebAgentRuntime._current_canonical_inputs(
            task=task, snapshot=snapshot, load_pointer=load_pointer
        )
        if minimal_request:
            review = load_pointer(academic_pointers.get("publication.review-closure"), label="review closure")
            graph_pointer = academic_pointers.get("claim_evidence")
            graph = load_pointer(graph_pointer, label="claim evidence") if graph_pointer else None
            if graph_pointer and graph_pointer.get("sha256") != head["subject"]["input_hashes"].get("claim_evidence"):
                raise ValueError("J10 claim evidence pointer is not bound to the current head")
            payload = prepare_local_package_inputs(head=head, bundle=canonical_bundle, review=review, graph=graph,
                obligations=host_target_obligations, target_sha256=target_authority_sha256)
        if canonical_bundle.get("figure_intent_receipts") and final_mappings is None:
            raise ValueError("J10 figure package needs the current accepted final-mapping registry")

        verified: dict[str, tuple[Path, bytes]] = {}
        expected_suffixes = {"source": ".tex", "pdf": ".pdf", "word": ".docx"}
        for role, manifest in manifests.items():
            raw_path = manifest.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError(f"J10 {role} manifest path is missing")
            candidate = bounded_path(workspace_root, raw_path)
            try:
                candidate.relative_to(workspace_root)
            except ValueError as exc:
                raise ValueError(f"J10 {role} file escapes the task workspace") from exc
            if not candidate.is_file() or candidate.suffix.lower() != expected_suffixes[role]:
                raise ValueError(f"J10 {role} file is missing or has the wrong suffix")
            encoded = candidate.read_bytes()
            binary_hash = manifest.get("source_bytes_sha256") if manifest.get("contract") == "paperspine5.local-file-byte-evidence" else manifest.get("sha256")
            if (
                binary_hash != hashlib.sha256(encoded).hexdigest()
                or manifest.get("size_bytes") != len(encoded)
            ):
                raise ValueError(f"J10 {role} file differs from the J8 manifest")
            if role == "source":
                try:
                    encoded.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ValueError("J10 source file is not UTF-8") from exc
            elif role == "pdf" and not encoded.startswith(b"%PDF-"):
                raise ValueError("J10 PDF file does not contain PDF bytes")
            elif role == "word" and not encoded.startswith(b"PK\x03\x04"):
                raise ValueError("J10 Word file does not contain DOCX/ZIP bytes")
            verified[role] = (candidate, encoded)

        if minimal_request:
            for surface in canonical_bundle.get("surface_receipts", []):
                for page in surface.get("pages", []):
                    if not isinstance(page, dict) or not isinstance(page.get("path"), str):
                        raise ValueError("J10 accepted surface page path is missing")
                    content = bounded_path(workspace_root, page["path"]).read_bytes()
                    if not content.startswith(b"\x89PNG\r\n\x1a\n") or hashlib.sha256(content).hexdigest() != page.get("sha256"):
                        raise ValueError("J10 accepted surface page bytes changed")
        author_close = payload.get("author_close")
        if isinstance(author_close, list) and author_close:
            if not isinstance(user_message, str) or not user_message.strip():
                raise ValueError(
                    "J10 author close is not bound to a current Web user answer"
                )
            normalized_answer = user_message.strip()
            answer_lower = normalized_answer.lower()
            synthetic_markers = (
                "synthetic",
                "local acceptance",
                "dummy",
                "placeholder",
                "测试",
                "模拟",
                "随便填",
                "自动填写",
            )
            if any(marker in answer_lower for marker in synthetic_markers):
                raise ValueError(
                    "J10 synthetic/local-test user text cannot close real author facts"
                )
            confirmation_sha256 = hashlib.sha256(
                normalized_answer.encode("utf-8")
            ).hexdigest()
            for index, item in enumerate(author_close):
                if not isinstance(item, dict):
                    raise ValueError(f"J10 author close item is invalid: {index}")
                if (
                    item.get("synthetic") is not False
                    or item.get("confirmation_scope") != "real_author_fact"
                    or item.get("user_confirmation_sha256")
                    != confirmation_sha256
                ):
                    raise ValueError(
                        f"J10 author close item is not bound to the real current user answer: {index}"
                    )
        archive_inputs = collect_package_files(workspace=workspace_root, run_root=run_root,
            verified=verified, final_mappings=final_mappings or [])

        def bind_host_inputs(descriptor: dict[str, Any]) -> dict[str, Any]:
            bound = copy.deepcopy(payload)
            # J4 freezes typed target-rule layers and the host deterministically
            # derives this ledger.  A J10 producer can map the stable IDs but
            # cannot invent, omit, or reclassify obligations.
            bound["target_obligations"] = copy.deepcopy(host_target_obligations)
            raw_inputs = bound.get("input_artifacts")
            if raw_inputs is None:
                raw_inputs = {}
                bound["input_artifacts"] = raw_inputs
            if not isinstance(raw_inputs, dict):
                raise ValueError("J10 input_artifacts must be an object")
            raw_inputs["bundle_archive"] = copy.deepcopy(descriptor)

            obligation_manifest = bound.get("readiness_obligation_manifest")
            if (
                not isinstance(obligation_manifest, dict)
                or obligation_manifest.get("contract")
                != "paperspine5.readiness-obligation-manifest"
                or obligation_manifest.get("contract_version") != "1.0"
            ):
                raise ValueError("J10 readiness obligation manifest is missing or invalid")
            unsigned = {
                key: value
                for key, value in obligation_manifest.items()
                if key != "manifest_sha256"
            }
            manifest_sha256 = hashlib.sha256(
                json.dumps(
                    unsigned,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            # The producer describes the obligation set, but its digest is a
            # host-authoritative transport field just like the package and
            # archive hashes below.  Recompute it from the exact received
            # manifest instead of requiring an LLM (or a shell JSON encoder)
            # to reproduce Python's canonical-key ordering.  The Runner still
            # validates this freshly bound digest and the exact five-tier
            # obligation contract before readiness can pass.
            obligation_manifest["manifest_sha256"] = manifest_sha256
            raw_inputs["readiness_obligations"] = copy.deepcopy(
                obligation_manifest
            )

            package = bound.get("package_manifest")
            if (
                not isinstance(package, dict)
                or package.get("contract") != "paperspine5.target-package-manifest"
                or package.get("contract_version") != "1.0"
                or package.get("status") not in {"PASS", "BLOCKED"}
                or package.get("external_action_authorized") is not False
            ):
                raise ValueError("J10 package manifest is missing or invalid")
            # Reached only after actual CRC/member/byte verification. This is
            # a local archive status, not a newly generated scientific review.
            package["status"] = "PASS"
            if minimal_request:
                for predicate in bound["predicates"]:
                    if predicate["predicate_id"] == "target_bundle_fresh":
                        predicate["status"] = "true"
                        predicate["reason"] = "Host verified exact current ZIP entries, bytes and CRC; local archive only."
            archive_artifact_id = package.get("archive_artifact_id")
            if archive_artifact_id not in {None, "", "bundle_archive"}:
                raise ValueError(
                    "J10 package manifest uses an unsupported archive artifact"
                )
            package["archive_artifact_id"] = "bundle_archive"
            package["archive_sha256"] = (
                ProductWebAgentRuntime._canonical_input_hash(descriptor)
            )
            package["subject"] = {
                "task_id": task["task_id"],
                "revision_id": str(snapshot.get("revision", task["revision"])),
                # AcademicStageOrchestrator replaces this placeholder with the
                # authoritative post-input base snapshot before compilation.
                "input_hashes": {"host-rebind-sentinel": "0" * 64},
            }
            descriptor_entries = descriptor.get("entries")
            if not isinstance(descriptor_entries, list):
                raise ValueError("J10 package archive descriptor entries are missing")
            role_to_artifact = {
                role: manifest["artifact_id"] for role, manifest in manifests.items()
            }
            package_entries: list[dict[str, Any]] = []
            for role, artifact_id in role_to_artifact.items():
                matches = [
                    entry
                    for entry in descriptor_entries
                    if isinstance(entry, dict) and entry.get("role") == role
                ]
                if len(matches) != 1:
                    raise ValueError(f"J10 package archive must contain one {role} entry")
                package_entries.append(
                    {
                        "package_path": matches[0]["archive_path"],
                        "artifact_id": artifact_id,
                        "sha256": "0" * 64,
                        "revision_id": str(snapshot.get("revision", task["revision"])),
                    }
                )
            package["entries"] = package_entries
            package["target_authority_sha256"] = target_authority_sha256
            package.update(_self_hashed(package, "manifest_sha256"))

            predicate_inputs = {
                "canonical_artifacts_bound": ("canonical_head",),
                "final_claim_inventory_valid": ("final_claim_index",),
                "evidence_verification_valid": (
                    "canonical_head",
                    "final_claim_index",
                    "claim_evidence",
                ),
                "independent_review_valid": ("review_closure",),
                "quality_objections_closed": ("review_closure",),
                "final_render_bound": ("surface_pdf", "surface_word"),
                "surface_semantics_valid": ("surface_pdf", "surface_word"),
                "visual_accessibility_valid": ("surface_pdf", "surface_word"),
                "target_research_valid": ("target_authority",),
                "target_compliance_valid": (
                    "target_obligations",
                    manifests["source"]["artifact_id"],
                ),
                "target_bundle_fresh": ("target_package", "bundle_archive"),
                "author_items_closed": ("author_close",),
                "author_confirmed_current_revision": ("author_close",),
            }
            predicates = bound.get("predicates")
            if isinstance(predicates, list):
                observed: set[str] = set()
                for predicate in predicates:
                    if not isinstance(predicate, dict):
                        raise ValueError("J10 readiness predicate is invalid")
                    predicate_id = predicate.get("predicate_id")
                    if predicate_id not in predicate_inputs or predicate_id in observed:
                        raise ValueError("J10 readiness predicate set is invalid")
                    observed.add(predicate_id)
                    predicate["artifact_inputs"] = {
                        artifact_id: "0" * 64
                        for artifact_id in predicate_inputs[predicate_id]
                    }
            return bound

        expected_workspace_entries: dict[str, dict[str, Any]] = {
            path.relative_to(workspace_root).as_posix(): {
                "role": role,
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "size_bytes": len(encoded),
            }
            for path, encoded, role in archive_inputs.values()
        }

        existing_pointer = base_pointers.get("bundle_archive")
        if isinstance(existing_pointer, dict):
            existing = load_pointer(existing_pointer, label="package archive")
            if existing.get("contract") == "paperspine5.local-package-archive":
                if (
                    existing.get("artifact_id") != "bundle_archive"
                    or existing.get("task_id") != task["task_id"]
                    or existing.get("local_only") is not True
                    or existing.get("external_action_authorized") is not False
                ):
                    raise ValueError("J10 existing package archive descriptor is invalid")
                raw_archive_path = existing.get("path")
                if not isinstance(raw_archive_path, str) or not raw_archive_path.strip():
                    raise ValueError("J10 existing package archive path is missing")
                existing_archive = bounded_path(workspace_root, raw_archive_path)
                try:
                    existing_archive.relative_to(workspace_root)
                except ValueError as exc:
                    raise ValueError(
                        "J10 existing package archive escapes the task workspace"
                    ) from exc
                if not existing_archive.is_file():
                    raise ValueError("J10 existing package archive does not exist")
                existing_archive_bytes = existing_archive.read_bytes()
                if (
                    existing.get("sha256")
                    != hashlib.sha256(existing_archive_bytes).hexdigest()
                    or existing.get("size_bytes") != len(existing_archive_bytes)
                ):
                    raise ValueError("J10 existing package archive bytes changed")
                raw_entries = existing.get("entries")
                if not isinstance(raw_entries, list) or not raw_entries:
                    raise ValueError("J10 existing package archive entries are missing")
                entry_by_archive_path: dict[str, dict[str, Any]] = {}
                observed_workspace_entries: dict[str, dict[str, Any]] = {}
                for raw_entry in raw_entries:
                    if not isinstance(raw_entry, dict):
                        raise ValueError("J10 existing package archive entry is invalid")
                    archive_name = raw_entry.get("archive_path")
                    workspace_name = raw_entry.get("workspace_path")
                    if (
                        not isinstance(archive_name, str)
                        or not archive_name
                        or archive_name in entry_by_archive_path
                        or not isinstance(workspace_name, str)
                        or not workspace_name
                    ):
                        raise ValueError(
                            "J10 existing package archive entry identity is invalid"
                        )
                    entry_by_archive_path[archive_name] = raw_entry
                    if raw_entry.get("role") != "local-readme":
                        candidate = bounded_path(workspace_root, workspace_name)
                        try:
                            candidate.relative_to(workspace_root)
                        except ValueError as exc:
                            raise ValueError(
                                "J10 existing package entry escapes the task workspace"
                            ) from exc
                        if not candidate.is_file():
                            raise ValueError("J10 existing package entry file is missing")
                        encoded = candidate.read_bytes()
                        if (
                            raw_entry.get("sha256")
                            != hashlib.sha256(encoded).hexdigest()
                            or raw_entry.get("size_bytes") != len(encoded)
                        ):
                            raise ValueError("J10 existing package entry bytes changed")
                        if workspace_name in observed_workspace_entries:
                            raise ValueError(
                                "J10 existing package repeats a workspace entry"
                            )
                        observed_workspace_entries[workspace_name] = {
                            "role": raw_entry.get("role"),
                            "sha256": raw_entry.get("sha256"),
                            "size_bytes": raw_entry.get("size_bytes"),
                        }
                if observed_workspace_entries != expected_workspace_entries:
                    raise ValueError(
                        "J10 existing package no longer matches current manuscript inputs"
                    )
                with zipfile.ZipFile(existing_archive, "r") as bundle:
                    if bundle.testzip() is not None:
                        raise ValueError("J10 existing package failed CRC verification")
                    if sorted(bundle.namelist()) != sorted(entry_by_archive_path):
                        raise ValueError(
                            "J10 existing package entries differ from its descriptor"
                        )
                    for archive_name, entry in entry_by_archive_path.items():
                        encoded = bundle.read(archive_name)
                        if (
                            entry.get("sha256")
                            != hashlib.sha256(encoded).hexdigest()
                            or entry.get("size_bytes") != len(encoded)
                        ):
                            raise ValueError(
                                "J10 existing package member bytes changed"
                            )
                return bind_host_inputs(existing)

        package_dir = bounded_path(workspace_root, (
            workspace_root
            / "publication-package"
            / f"revision-{task['revision']}"
        ), must_exist=False)
        verify_inventory_bytes(workspace_root, archive_inputs)
        package_dir.mkdir(parents=True, exist_ok=True)
        archive_path = bounded_path(workspace_root, package_dir / "paperspine5-local-target-package.zip", must_exist=False)
        readme_path = bounded_path(workspace_root, package_dir / "README.md", must_exist=False)
        readme_text = (
            "# PaperSpine local target package\n\n"
            f"- Task: {task['task_id']}\n"
            f"- Revision: {task['revision']}\n"
            "- Scope: local paper files only; not a new scientific/citation/visual review\n"
            "- External submission, upload, and sending: not authorized\n"
            "- Real author facts must be re-confirmed before any external use\n"
        )
        readme_path.write_text(readme_text, encoding="utf-8")

        archive_inputs["README.md"] = (readme_path, readme_text.encode("utf-8"), "local-readme")

        temporary = archive_path.with_name(
            f".{archive_path.name}.{uuid.uuid4().hex}.tmp"
        )
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as bundle:
            for archive_name, (_, encoded, _) in sorted(archive_inputs.items()):
                info = zipfile.ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o644 & 0xFFFF) << 16
                bundle.writestr(info, encoded)
        os.replace(temporary, archive_path)
        with zipfile.ZipFile(archive_path, "r") as bundle:
            if bundle.testzip() is not None:
                raise ValueError("J10 package archive failed CRC verification")
            if sorted(bundle.namelist()) != sorted(archive_inputs):
                raise ValueError("J10 package archive entries differ from the host manifest")
            for name, (_, encoded, _) in archive_inputs.items():
                if bundle.read(name) != encoded:
                    raise ValueError("J10 package archive member bytes differ from the host inventory")

        archive_bytes = archive_path.read_bytes()
        descriptor = {
            "contract": "paperspine5.local-package-archive",
            "schema_version": "1.0",
            "artifact_id": "bundle_archive",
            "task_id": task["task_id"],
            "revision_id": str(task["revision"]),
            "path": archive_path.relative_to(workspace_root).as_posix(),
            "sha256": hashlib.sha256(archive_bytes).hexdigest(),
            "size_bytes": len(archive_bytes),
            "entries": [
                {
                    "archive_path": archive_name,
                    "workspace_path": path.relative_to(workspace_root).as_posix(),
                    "role": role,
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                    "size_bytes": len(encoded),
                }
                for archive_name, (path, encoded, role) in sorted(archive_inputs.items())
            ],
            "local_only": True,
            "external_action_authorized": False,
        }

        return bind_host_inputs(descriptor)

    @staticmethod
    def _canonical_input_hash(value: dict[str, Any]) -> str:
        encoded = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _rehash_known_contracts(value: Any) -> Any:
        if isinstance(value, list):
            return [ProductWebAgentRuntime._rehash_known_contracts(item) for item in value]
        if not isinstance(value, dict):
            return copy.deepcopy(value)
        result = {
            key: ProductWebAgentRuntime._rehash_known_contracts(item)
            for key, item in value.items()
        }
        for field in ("receipt_sha256", "bundle_sha256", "revision_sha256"):
            if field in result:
                unsigned = {key: item for key, item in result.items() if key != field}
                canonical = json.dumps(
                    unsigned,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                result[field] = hashlib.sha256(canonical).hexdigest()
        return result

    @staticmethod
    def _finalize_canonical_review(
        *, payload: dict[str, Any], job: dict[str, Any], review: dict[str, Any] | None
    ) -> dict[str, Any]:
        if not isinstance(review, dict) or review.get("decision") != "pass":
            raise ValueError("J8 canonical review did not pass")
        bound = copy.deepcopy(payload)
        bundle = bound.get("canonical_bundle")
        revision = bound.get("manuscript_revision")
        if not isinstance(bundle, dict) or not isinstance(revision, dict):
            raise ValueError("J8 canonical candidate disappeared before review finalization")
        producer = _host_identity(job, "producer")
        reviewer = _host_identity(job, "reviewer")
        for receipt in bundle.get("surface_receipts", []):
            if not isinstance(receipt, dict):
                continue
            receipt["review"] = {
                "reviewer_id": reviewer["principal_id"],
                "reviewer_attestation_input_id": reviewer["attestation_input_id"],
                "producer_ids": [producer["principal_id"]],
                "producer_attestation_input_ids": [producer["attestation_input_id"]],
                "final_decision": "pass",
                "objections": [],
                "reviewed_pages": [
                    {"page": page.get("page"), "render_sha256": page.get("sha256")}
                    for page in receipt.get("pages", [])
                    if isinstance(page, dict)
                ],
            }
            receipt["status"] = "PASS"
            # J9 requires a hash-bound PASS surface.  Host materialization
            # must create the receipt hash even when a producer supplied a
            # minimal placeholder without that optional field.
            unsigned_receipt = {
                key: value for key, value in receipt.items()
                if key != "receipt_sha256"
            }
            receipt["receipt_sha256"] = hashlib.sha256(
                json.dumps(
                    unsigned_receipt,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        for receipt in bundle.get("figure_intent_receipts", []):
            if isinstance(receipt, dict):
                receipt["status"] = "PASS"
        final_claim_index = bundle.get("final_claim_index")
        if isinstance(final_claim_index, dict):
            final_claim_index["status"] = "PASS"
        bundle["status"] = "PASS"
        bundle["blockers"] = []
        for artifact in revision.get("artifacts", {}).values():
            if isinstance(artifact, dict):
                artifact["build_status"] = "PASS"
        revision["status"] = "PASS"
        bound["canonical_bundle"] = ProductWebAgentRuntime._rehash_known_contracts(
            bundle
        )
        bound["manuscript_revision"] = (
            ProductWebAgentRuntime._rehash_known_contracts(revision)
        )
        return bound

    @staticmethod
    def _finalize_publication_review(
        *, payload: dict[str, Any], job: dict[str, Any], review: dict[str, Any] | None
    ) -> dict[str, Any]:
        if not isinstance(review, dict) or review.get("decision") not in {"pass", "block"}:
            raise ValueError("J9 independent publication review is missing")
        if review.get("decision") == "block" and not review.get("objections"):
            raise ValueError("J9 blocked review must retain its actual objections")
        bound = copy.deepcopy(payload)
        materialization = bound.pop("_host_j9_review", None)
        if not isinstance(materialization, dict):
            raise ValueError("J9 host review materialization disappeared")
        reviewer = _host_identity(job, "reviewer")
        ledger = materialization.get("target_obligation_ledger")
        review_artifact = materialization.get("target_review_artifact")
        if not isinstance(ledger, dict) or not isinstance(review_artifact, dict):
            raise ValueError("J9 host target review materialization disappeared")
        raw_findings = review.get("target_rule_findings")
        if not isinstance(raw_findings, list):
            raise ValueError("J9 independent target findings are missing")
        finding_by_rule = {
            str(item.get("authority_rule_id")): item
            for item in raw_findings
            if isinstance(item, dict)
        }
        target_findings: list[dict[str, Any]] = []
        for obligation in ledger.get("obligations", []):
            if (
                not isinstance(obligation, dict)
                or obligation.get("readiness_scope") != "local_delivery"
            ):
                continue
            rule_id = str(obligation.get("authority_rule_id") or "")
            raw_finding = finding_by_rule.get(rule_id)
            if not isinstance(raw_finding, dict):
                raise ValueError(f"J9 independent target finding is missing: {rule_id}")
            target_findings.append(
                _self_hashed(
                    {
                        "contract": "paperspine5.target-obligation-finding",
                        "contract_version": "1.0",
                        "obligation_id": obligation["obligation_id"],
                        "authority_rule_id": rule_id,
                        "target_authority_sha256": ledger[
                            "target_authority_sha256"
                        ],
                        "status": raw_finding["status"],
                        "artifact_id": review_artifact["artifact_id"],
                        "artifact_sha256": review_artifact["artifact_sha256"],
                        "evidence_locator": raw_finding["evidence_locator"],
                        "external_action_authorized": False,
                        "finding_sha256": "0" * 64,
                    },
                    "finding_sha256",
                )
            )
        bound["producer_ids"] = ["paperspine-web-producer"]
        passed = review["decision"] == "pass"
        objections = [
            {
                "objection_id": f"j9-objection-{index:03d}-{hashlib.sha256(message.encode('utf-8')).hexdigest()[:12]}",
                "severity": "major",
                "status": "open",
                "message": message,
                "evidence_locator": f"independent-review:objections/{index}",
            }
            for index, message in enumerate(review.get("objections", []), start=1)
        ]
        current_review = {
            "contract": "paperspine5.publication-review",
            "contract_version": "1.0",
            "subject": copy.deepcopy(materialization.get("subject")) or {
                "task_id": job["task_id"],
                "revision_id": str(job["revision"]),
                "input_hashes": {"host-rebind-placeholder": "0" * 64},
            },
            "manuscript_head_sha256": materialization.get(
                "manuscript_head_sha256"
            ),
            "reviewer_id": reviewer["principal_id"],
            "reviewer_attestation_input_id": reviewer["attestation_input_id"],
            "status": "PASS" if passed else "REVISION_REQUIRED",
            "final_decision": "pass" if passed else "revise",
            "objections": objections,
            "target_obligation_findings": target_findings,
            "review_scope": {
                "observed_manuscript_head_sha256": materialization.get("manuscript_head_sha256"),
                "observed_revision_id": (materialization.get("subject") or {}).get("revision_id"),
                "observed_canonical_bundle_sha256": materialization.get("canonical_bundle_sha256"),
                "canonical_bundle_sha256": materialization.get(
                    "canonical_bundle_sha256"
                ),
                "files": materialization.get("files"),
                "pages": materialization.get("pages"),
                "summary": review.get("summary"),
            },
            "external_action_authorized": False,
            "review_sha256": "0" * 64,
        }
        context = materialization.get("revision_context")
        if isinstance(context, dict) and context.get("status") == "revision_required":
            initial = copy.deepcopy(context["initial_review"])
            bound["producer_ids"] = sorted(set(bound["producer_ids"]) | set(context.get("producer_ids", [])))
            objection_ids = [str(item["objection_id"]) for item in initial["objections"]]
            response = materialization.get("revision_response")
            response_ids = [str(item.get("objection_id")) for item in response if isinstance(item, dict)] if isinstance(response, list) else []
            if len(response_ids) != len(objection_ids) or set(response_ids) != set(objection_ids):
                raise ValueError("J9 revised canonical must carry every prior objection response")
            prior_ids = {}
            for role in ("source", "pdf", "word"):
                old_file = initial.get("review_scope", {}).get("files", {}).get(role, {})
                old_id = old_file.get("artifact_id")
                if not old_id:
                    # Legacy reviews did not record role IDs; recover only an
                    # unambiguous ID already bound to the prior immutable head.
                    old_hash = context["manuscript_head"][f"{role}_sha256"]
                    matches = [key for key, sha in context["manuscript_head"].get("subject", {}).get("input_hashes", {}).items() if sha == old_hash]
                    if len(matches) != 1:
                        raise ValueError(f"J9 prior {role} artifact identity is missing or ambiguous")
                    old_id = matches[0]
                prior_ids[role] = old_id
            diff = _self_hashed({
                "contract": "paperspine5.revision-diff", "contract_version": "1.0",
                "from_revision_id": initial["subject"]["revision_id"],
                "from_head_sha256": initial["manuscript_head_sha256"],
                "to_revision_id": "0", "to_head_sha256": "0" * 64,
                "addressed_objection_ids": objection_ids,
                "changes": copy.deepcopy(response),
                "artifact_changes": [
                    {"role": role, "from_artifact_id": prior_ids[role], "to_artifact_id": materialization["files"][role]["artifact_id"],
                     "from_sha256": context["manuscript_head"][f"{role}_sha256"],
                     "to_sha256": materialization["files"][role]["runner_input_sha256"]}
                    for role in ("source", "pdf", "word")
                ],
                "external_action_authorized": False,
            }, "diff_sha256")
            current_review.update({
                "contract": "paperspine5.publication-re-review",
                "manuscript_head_sha256": "0" * 64,
                "revision_diff_sha256": diff["diff_sha256"],
                "resolved_objection_ids": objection_ids if passed else [],
            })
            bound.update({"initial_review": initial, "revision_diff": diff, "re_review": _self_hashed(current_review, "review_sha256")})
        else:
            bound["initial_review"] = _self_hashed(current_review, "review_sha256")
        return bound

    @staticmethod
    def _extract_stage_payload(raw_payload: str, job: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(raw_payload)
        if not isinstance(payload, dict):
            raise ValueError("Agent stage payload must be an object")
        if payload.get("contract") != "paperspine5.academic-stage-answer":
            return payload
        wrapper_bindings = {
            "task_id": job["task_id"],
            "expected_revision": job["revision"],
            "issue_id": job["issue_id"],
            "stage": job["stage"],
            "external_action_authorized": False,
        }
        for key, value in wrapper_bindings.items():
            if payload.get(key) != value:
                raise ValueError(f"Agent answer wrapper binding mismatch: {key}")
        nested = payload.get("payload")
        if not isinstance(nested, dict):
            raise ValueError("Agent answer wrapper payload must be an object")
        return copy.deepcopy(nested)

    def _run_independent_review(
        self,
        *,
        task: dict[str, Any],
        snapshot: dict[str, Any],
        context_path: Path,
        job: dict[str, Any],
        job_dir: Path,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        candidate_path = job_dir / "candidate-stage-payload.json"
        hash_preflight_path = job_dir / "candidate-hash-preflight.json"
        schema_path = job_dir / "review-result.schema.json"
        result_path = job_dir / "review-result.json"
        stdout_path = job_dir / "reviewer.log"
        _atomic_json(candidate_path, payload)
        _atomic_json(
            hash_preflight_path,
            self._candidate_hash_preflight(payload=payload, job=job),
        )
        _atomic_json(schema_path, REVIEW_RESULT_SCHEMA)
        job.update(summary="正在执行独立关卡复核。", updated_at=_now())
        self._write_job(job)
        review_images = self._canonical_review_images(task=task, payload=payload)
        command = self._review_command(
            task, schema_path, result_path, image_paths=review_images
        )
        prompt = self._review_prompt(
            context_path=context_path,
            candidate_path=candidate_path,
            hash_preflight_path=hash_preflight_path,
            result_path=result_path,
            job=job,
        )
        process_options = {
            "input": prompt,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "cwd": task["workspace_root"],
            "env": self._child_environment(task, snapshot),
            "stderr": subprocess.STDOUT,
            "creationflags": _creation_flags(),
            "timeout": 60 * 20,
            "check": False,
        }
        completed = self._run_codex_process(
            command=command,
            stdout_path=stdout_path,
            process_options=process_options,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"独立复核 Agent 退出码为 {completed.returncode}。")
        if not result_path.is_file():
            raise RuntimeError("独立复核 Agent 未返回结构化结果。")
        review = self._load_agent_json(result_path)
        self._validate_review_result(review, job, payload=payload)
        return review

    @staticmethod
    def _candidate_hash_preflight(
        *, payload: dict[str, Any], job: dict[str, Any]
    ) -> dict[str, Any]:
        inputs = payload.get("input_artifacts")
        if not isinstance(inputs, dict):
            inputs = {}
        entries: list[dict[str, Any]] = []
        sources = payload.get("sources")
        if isinstance(sources, list):
            for source in sources:
                if not isinstance(source, dict):
                    continue
                source_id = source.get("source_id")
                artifact_id = f"source:{source_id}"
                artifact = inputs.get(artifact_id)
                if not isinstance(source_id, str) or not isinstance(artifact, dict):
                    continue
                canonical = json.dumps(
                    artifact,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8") + bytes([10])
                computed = hashlib.sha256(canonical).hexdigest()
                declared = source.get("content_sha256")
                entries.append(
                    {
                        "artifact_id": artifact_id,
                        "declared_sha256": declared,
                        "computed_sha256": computed,
                        "canonical_size_bytes": len(canonical),
                        "match": declared == computed,
                    }
                )
        return {
            "contract": "paperspine5.web-agent-hash-preflight",
            "schema_version": "1.0",
            "task_id": job["task_id"],
            "revision": job["revision"],
            "issue_id": job["issue_id"],
            "stage": job["stage"],
            "canonicalization": (
                "UTF-8 of sorted compact JSON with ensure_ascii=false, followed "
                "by exactly one LF byte 0x0A"
            ),
            "entries": entries,
            "all_match": all(entry["match"] for entry in entries),
            "external_action_authorized": False,
        }

    @staticmethod
    def _canonical_review_images(
        *, task: dict[str, Any], payload: dict[str, Any]
    ) -> list[Path]:
        j9 = payload.get("_host_j9_review")
        if isinstance(j9, dict):
            workspace_root = Path(task["workspace_root"]).resolve()
            images: list[Path] = []
            for surface in ("pdf", "word"):
                raw_pages = j9.get("pages", {}).get(surface, [])
                for page in raw_pages:
                    candidate = (
                        workspace_root / str(page.get("path") or "")
                    ).resolve()
                    try:
                        candidate.relative_to(workspace_root)
                    except ValueError as exc:
                        raise ValueError(
                            "J9 reviewer image escapes the task workspace"
                        ) from exc
                    if not candidate.is_file():
                        raise ValueError("J9 reviewer image does not exist")
                    images.append(candidate)
            if not images:
                raise ValueError("J9 independent review has no rendered page images")
            return images

        bundle = payload.get("canonical_bundle")
        if not isinstance(bundle, dict) or bundle.get("status") != "REVIEW_REQUIRED":
            return []
        workspace_root = Path(task["workspace_root"]).resolve()
        images: list[Path] = []
        observed: set[Path] = set()
        for receipt in bundle.get("surface_receipts", []):
            if not isinstance(receipt, dict):
                continue
            for page in receipt.get("pages", []):
                if not isinstance(page, dict):
                    continue
                raw_path = page.get("path")
                if not isinstance(raw_path, str) or not raw_path.strip():
                    raise ValueError("J8 reviewer image path is missing")
                candidate = (workspace_root / raw_path).resolve()
                try:
                    candidate.relative_to(workspace_root)
                except ValueError as exc:
                    raise ValueError("J8 reviewer image escapes the task workspace") from exc
                if not candidate.is_file():
                    raise ValueError("J8 reviewer image does not exist")
                if candidate not in observed:
                    images.append(candidate)
                    observed.add(candidate)
        if not images:
            raise ValueError("J8 independent review has no rendered page images")
        # J8 has the same two-surface coverage requirement as J9. Keep the
        # bound high enough for a normal long manuscript while retaining a
        # denial-of-service guard.
        if len(images) > 60:
            raise ValueError("J8 independent review exceeds the 60-page image limit")
        return images

    def _run_codex_process(
        self,
        *,
        command: list[str],
        stdout_path: Path,
        process_options: dict[str, Any],
    ) -> subprocess.CompletedProcess[str]:
        result_path = Path(command[command.index("--output-last-message") + 1])
        completed: subprocess.CompletedProcess[str] | None = None
        for transport_attempt in range(1, 4):
            if result_path.is_file():
                result_path.unlink()
            if transport_attempt > 1:
                with stdout_path.open("a", encoding="utf-8") as stream:
                    stream.write(
                        f"\n--- paperspine host transport retry {transport_attempt}/3 ---\n"
                    )
            if self._stream_process_output:
                mode = "w" if transport_attempt == 1 else "a"
                completed = self._run_bounded_streaming_process(
                    command=command,
                    stdout_path=stdout_path,
                    mode=mode,
                    process_options=process_options,
                )
            else:
                completed = self.process_runner(
                    command,
                    stdout=subprocess.PIPE,
                    **process_options,
                )
                self._write_bounded_captured_output(
                    stdout_path=stdout_path,
                    mode="w" if transport_attempt == 1 else "a",
                    output=completed.stdout or "",
                )
            if completed.returncode == 0:
                return completed
            if self._profile_isolation_auth_failure(stdout_path):
                raise AgentProfileIsolationUnavailableError(
                    detail=(
                        "empty task-local CODEX_HOME with OS-keyring-only authentication "
                        "was rejected because no usable keyring login is available; "
                        "parent CODEX_HOME and auth.json fallback are forbidden because "
                        "they expose credentials or reintroduce rollout history"
                    ),
                    evidence_path=stdout_path,
                )
            if (
                transport_attempt == 3
                or result_path.is_file()
                or not self._retryable_transport_failure(stdout_path)
            ):
                return completed
            time.sleep(transport_attempt * 2)
        if completed is None:  # Defensive; the fixed loop always executes.
            raise RuntimeError("Codex worker did not start")
        return completed

    @staticmethod
    def _load_agent_json(path: Path) -> dict[str, Any]:
        size = path.stat().st_size
        if size > AGENT_RESULT_LIMIT_BYTES:
            raise AgentResourceLimitError(
                "AGENT_RESULT_LIMIT",
                limit_bytes=AGENT_RESULT_LIMIT_BYTES,
                observed_bytes_at_least=size,
                detail="child structured result exceeded the bounded JSON budget",
            )
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Agent structured result must be an object")
        return value

    def _run_bounded_streaming_process(
        self,
        *,
        command: list[str],
        stdout_path: Path,
        mode: str,
        process_options: dict[str, Any],
    ) -> subprocess.CompletedProcess[str]:
        options = dict(process_options)
        prompt = options.pop("input", None)
        timeout = float(options.pop("timeout", 60 * 45))
        options.pop("check", None)
        started = time.monotonic()
        with stdout_path.open(mode, encoding="utf-8") as stream:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=stream,
                **options,
            )
            try:
                if process.stdin is not None:
                    if prompt:
                        process.stdin.write(prompt)
                    process.stdin.close()
                while process.poll() is None:
                    if time.monotonic() - started > timeout:
                        self._stop_child_process(process)
                        raise subprocess.TimeoutExpired(command, timeout)
                    stream.flush()
                    observed = stdout_path.stat().st_size
                    parse_failure = self._log_tail_contains_parse_failure(stdout_path)
                    if observed > AGENT_LOG_LIMIT_BYTES or parse_failure:
                        self._stop_child_process(process)
                        stream.flush()
                        final_observed = max(observed, stdout_path.stat().st_size)
                        self._cap_agent_log(stdout_path)
                        raise AgentResourceLimitError(
                            "AGENT_OUTPUT_LIMIT",
                            limit_bytes=AGENT_LOG_LIMIT_BYTES,
                            observed_bytes_at_least=final_observed,
                            detail=(
                                "child output contained a repeated-session JSON parse boundary"
                                if parse_failure
                                else "child output exceeded the bounded local log budget"
                            ),
                        )
                    time.sleep(0.05)
                stream.flush()
                observed = stdout_path.stat().st_size
                parse_failure = self._log_tail_contains_parse_failure(stdout_path)
                if observed > AGENT_LOG_LIMIT_BYTES or parse_failure:
                    self._cap_agent_log(stdout_path)
                    raise AgentResourceLimitError(
                        "AGENT_OUTPUT_LIMIT",
                        limit_bytes=AGENT_LOG_LIMIT_BYTES,
                        observed_bytes_at_least=observed,
                        detail=(
                            "child output contained a repeated-session JSON parse boundary"
                            if parse_failure
                            else "child output exceeded the bounded local log budget"
                        ),
                    )
                return subprocess.CompletedProcess(command, int(process.returncode or 0))
            finally:
                if process.poll() is None:
                    self._stop_child_process(process)

    @staticmethod
    def _stop_child_process(process: subprocess.Popen[str]) -> None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    @staticmethod
    def _log_tail_contains_parse_failure(stdout_path: Path) -> bool:
        try:
            with stdout_path.open("rb") as stream:
                stream.seek(max(0, stdout_path.stat().st_size - 131_072))
                return ROLLOUT_PARSE_FAILURE_MARKER in stream.read()
        except OSError:
            return False

    @staticmethod
    def _cap_agent_log(stdout_path: Path) -> None:
        with stdout_path.open("rb") as stream:
            bounded = stream.read(AGENT_LOG_LIMIT_BYTES)
        marker = re.search(
            re.escape(ROLLOUT_PARSE_FAILURE_MARKER) + rb"\s+\d+",
            bounded,
        )
        if marker is not None:
            bounded = bounded[: marker.end()]
        sentinel = (
            b"\n--- paperspine host resource blocker: child output capped; "
            b"no retry or Runner submission ---\n"
        )
        stdout_path.write_bytes(bounded + sentinel)

    def _write_bounded_captured_output(
        self,
        *,
        stdout_path: Path,
        mode: str,
        output: str,
    ) -> None:
        encoded = output.encode("utf-8", errors="replace")
        existing_size = stdout_path.stat().st_size if mode == "a" and stdout_path.exists() else 0
        parse_match = re.search(
            re.escape(ROLLOUT_PARSE_FAILURE_MARKER) + rb"\s+\d+",
            encoded,
        )
        exceeds = existing_size + len(encoded) > AGENT_LOG_LIMIT_BYTES
        if parse_match is None and not exceeds:
            with stdout_path.open(mode, encoding="utf-8") as stream:
                stream.write(output)
            return
        allowed = max(0, AGENT_LOG_LIMIT_BYTES - existing_size)
        if parse_match is not None:
            allowed = min(allowed, parse_match.end())
        binary_mode = "ab" if mode == "a" else "wb"
        with stdout_path.open(binary_mode) as stream:
            stream.write(encoded[:allowed])
        self._cap_agent_log(stdout_path)
        raise AgentResourceLimitError(
            "AGENT_OUTPUT_LIMIT",
            limit_bytes=AGENT_LOG_LIMIT_BYTES,
            observed_bytes_at_least=existing_size + len(encoded),
            detail=(
                "child output contained a repeated-session JSON parse boundary"
                if parse_match is not None
                else "child output exceeded the bounded local log budget"
            ),
        )

    @staticmethod
    def _retryable_transport_failure(stdout_path: Path) -> bool:
        try:
            with stdout_path.open("rb") as stream:
                stream.seek(max(0, stdout_path.stat().st_size - 131_072))
                tail = stream.read().decode("utf-8", errors="replace").lower()
        except OSError:
            return False
        markers = (
            "stream disconnected before completion",
            "tls handshake eof",
            "unexpected eof during handshake",
            "error sending request for url",
            "failed to connect to websocket",
        )
        return any(marker in tail for marker in markers)

    @staticmethod
    def _profile_isolation_auth_failure(stdout_path: Path) -> bool:
        try:
            with stdout_path.open("rb") as stream:
                stream.seek(max(0, stdout_path.stat().st_size - 131_072))
                tail = stream.read().decode("utf-8", errors="replace").lower()
        except OSError:
            return False
        return (
            "401 unauthorized" in tail
            and "missing bearer or basic authentication in header" in tail
        )

    @staticmethod
    def _bind_host_identities(
        payload: dict[str, Any],
        job: dict[str, Any],
        *,
        review: dict[str, Any] | None,
        delegated_contribution: bool = False,
    ) -> dict[str, Any]:
        bound = copy.deepcopy(payload)
        raw_inputs = bound.get("input_artifacts")
        if raw_inputs is None:
            raw_inputs = {}
            bound["input_artifacts"] = raw_inputs
        if not isinstance(raw_inputs, dict):
            raise ValueError("Agent stage payload input_artifacts must be an object")
        identities = {
            role: _host_identity(job, role)
            for role in ("producer", "reviewer", "author")
        }

        def attest(role: str) -> dict[str, str]:
            identity = identities[role]
            raw_inputs[identity["attestation_input_id"]] = copy.deepcopy(identity)
            return copy.deepcopy(identity)

        if job["stage"] == "awaiting_research":
            bound["producer"] = attest("producer")
            bound["challenger"] = {
                "reviewer": attest("reviewer"),
                "research_snapshot_sha256": "0" * 64,
                "status": "pass",
                "objections": [],
            }
        elif job["stage"] == "awaiting_contribution":
            bound.pop("author_identity", None)
        elif job["stage"] == "awaiting_claim_graph":
            bound["producer"] = attest("producer")
            bound["challenger"] = {
                "reviewer": attest("reviewer"),
                "graph_snapshot_sha256": "0" * 64,
                "status": "pass",
                "objections": [],
            }
        elif job["stage"] == "awaiting_canonical":
            attest("producer")
            attest("reviewer")
        elif job["stage"] == "awaiting_review":
            reviewer = attest("reviewer")
            current_review = bound.get("re_review") if "revision_diff" in bound else bound.get("initial_review")
            if not isinstance(current_review, dict):
                raise ValueError("J9 independent review receipt is missing")
            current_review["reviewer_id"] = reviewer["principal_id"]
            current_review["reviewer_attestation_input_id"] = reviewer[
                "attestation_input_id"
            ]
            bound["re_review" if "revision_diff" in bound else "initial_review"] = _self_hashed(current_review, "review_sha256")
        return bound

    @staticmethod
    def _validate_review_result(
        review: dict[str, Any],
        job: dict[str, Any],
        *,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(review, dict):
            raise ValueError("Independent review result must be an object")
        expected = {
            "contract": "paperspine5.web-agent-independent-review",
            "schema_version": "1.0",
            "task_id": job["task_id"],
            "revision": job["revision"],
            "issue_id": job["issue_id"],
            "stage": job["stage"],
            "external_action_authorized": False,
        }
        for key, value in expected.items():
            if review.get(key) != value:
                raise ValueError(f"Independent review binding mismatch: {key}")
        if review.get("decision") not in {"pass", "block"}:
            raise ValueError("Independent review decision is invalid")
        objections = review.get("objections")
        if not isinstance(objections, list) or any(
            not isinstance(item, str) for item in objections
        ):
            raise ValueError("Independent review objections must be strings")
        if review["decision"] == "pass" and objections:
            raise ValueError("Passing independent review cannot retain objections")
        if job.get("stage") == "awaiting_review" and review["decision"] == "block" and not any(item.strip() for item in objections):
            raise ValueError("Blocked J9 independent review must retain objections")
        raw_target_findings = review.get("target_rule_findings")
        if job.get("stage") != "awaiting_review":
            if raw_target_findings is not None:
                raise ValueError(
                    "Target rule findings are only valid for J9 independent review"
                )
            return
        materialization = (
            payload.get("_host_j9_review") if isinstance(payload, dict) else None
        )
        ledger = (
            materialization.get("target_obligation_ledger")
            if isinstance(materialization, dict)
            else None
        )
        if not isinstance(ledger, dict):
            raise ValueError("J9 host target obligation ledger is missing")
        expected_rules = {
            str(item.get("authority_rule_id"))
            for item in ledger.get("obligations", [])
            if isinstance(item, dict)
            and item.get("readiness_scope") == "local_delivery"
        }
        if not isinstance(raw_target_findings, list):
            raise ValueError("J9 independent target rule findings are missing")
        observed: set[str] = set()
        for index, finding in enumerate(raw_target_findings):
            if not isinstance(finding, dict):
                raise ValueError(f"J9 independent target finding is invalid: {index}")
            if set(finding) != {
                "authority_rule_id",
                "status",
                "evidence_locator",
            }:
                raise ValueError(
                    f"J9 independent target finding fields are invalid: {index}"
                )
            rule_id = str(finding.get("authority_rule_id") or "").strip()
            if not rule_id or rule_id in observed:
                raise ValueError(
                    f"J9 independent target finding rule is missing or duplicated: {index}"
                )
            observed.add(rule_id)
            if finding.get("status") not in {"satisfied", "unsatisfied"}:
                raise ValueError(
                    f"J9 independent target finding status is invalid: {rule_id}"
                )
            if not str(finding.get("evidence_locator") or "").strip():
                raise ValueError(
                    f"J9 independent target finding evidence is missing: {rule_id}"
                )
        if observed != expected_rules:
            raise ValueError(
                "J9 independent target finding coverage differs from frozen local rules"
            )

    def _submit_result(
        self, job: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        raw_payload = result.get("stage_payload_json")
        try:
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) else None
        except json.JSONDecodeError as exc:
            raise ValueError("Agent submit_stage 结果的 stage_payload_json 无效。") from exc
        if not isinstance(payload, dict):
            raise ValueError("Agent submit_stage 结果缺少 JSON object payload。")
        task_id = job["task_id"]
        writer_id = self.runner_writer_owner(task_id)
        if not isinstance(writer_id, str) or not writer_id:
            raise RuntimeError("runtime writer owner is unavailable")
        answer = {
            "contract": "paperspine5.academic-stage-answer",
            "schema_version": "1.0",
            "answer_id": f"web-agent-answer-{job['job_id']}",
            "issue_id": job["issue_id"],
            "task_id": task_id,
            "expected_revision": job["revision"],
            "stage": job["stage"],
            "payload": payload,
            "external_action_authorized": False,
        }
        outcome = self.runner.answer_issue(
            task_id,
            job["issue_id"],
            job["private"]["resume_token"],
            answer,
            command_id=f"web-agent-submit-{job['job_id']}",
            expected_revision=job["revision"],
            writer_id=writer_id,
            actor={"actor_id": "paperspine-web-agent", "surface": "web"},
        )
        self.runner_writer_used(task_id, writer_id)
        command_output = outcome.get("command_result", {}).get("output", {})
        if command_output.get("status") == "BLOCKED" or command_output.get("blockers"):
            blockers = command_output.get("blockers") or []
            resulting_snapshot = outcome.get("snapshot")
            transition_committed = isinstance(resulting_snapshot, dict) and (
                resulting_snapshot.get("revision") != job["revision"]
                or resulting_snapshot.get("stage") != job["stage"]
                or not any(
                    isinstance(item, dict)
                    and item.get("issue_id") == job["issue_id"]
                    for item in resulting_snapshot.get("open_issues", [])
                )
            )
            if transition_committed:
                next_stage = resulting_snapshot.get("stage") or "新的协作关卡"
                blocker_text = "; ".join(
                    f"{item.get('code')}: {item.get('message')}"
                    for item in blockers
                    if isinstance(item, dict)
                )
                return {
                    "outcome": outcome,
                    "committed_blocked": True,
                    "summary": (
                        f"Runner 已保存本次阻断结果并转入 {next_stage}。"
                        + (f" {blocker_text}" if blocker_text else "")
                    ),
                }
            raise RuntimeError(
                "Runner 拒绝 Agent 阶段结果："
                + "; ".join(
                    f"{item.get('code')}: {item.get('message')}"
                    for item in blockers
                    if isinstance(item, dict)
                )
            )
        return {"outcome": outcome, "committed_blocked": False}

    def _context(
        self, task: dict[str, Any], snapshot: dict[str, Any], job: dict[str, Any]
    ) -> dict[str, Any]:
        safe_snapshot = copy.deepcopy(snapshot)
        for issue in safe_snapshot.get("open_issues", []):
            issue.pop("resume_token", None)
        grants = [
            {
                "root": item.get("canonical_target") or item.get("root"),
                "read_only": True,
            }
            for item in task.get("material_grants", [])
        ]
        if isinstance(safe_snapshot.get("material_inventory"), dict):
            try:
                material_profile = build_material_profile(task, safe_snapshot)
            except ValueError as exc:
                material_profile = {
                    "contract": "paperspine5.host-material-profile",
                    "schema_version": "1.0",
                    "available": False,
                    "error": str(exc),
                    "fail_closed": True,
                    "external_action_authorized": False,
                }
        else:
            material_profile = {
                "contract": "paperspine5.host-material-profile",
                "schema_version": "1.0",
                "available": False,
                "error": "current Runner snapshot has no material inventory pointer",
                "fail_closed": True,
                "external_action_authorized": False,
            }
        binary_references: list[dict[str, Any]] = []
        if material_profile.get("available", True) is not False:
            candidates = list(material_profile.get("scientific_figures") or [])
            candidates.extend(
                item
                for item in material_profile.get("other_materials") or []
                if Path(str(item.get("relative_path") or "")).suffix.lower()
                in {".pdf", ".png", ".jpg", ".jpeg", ".svg", ".eps", ".docx"}
            )
            seen: set[str] = set()
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                source_id = item.get("source_id")
                if not isinstance(source_id, str) or source_id in seen:
                    continue
                seen.add(source_id)
                binary_references.append(
                    {
                        key: copy.deepcopy(item.get(key))
                        for key in (
                            "source_id",
                            "relative_path",
                            "sha256",
                            "size_bytes",
                            "semantic_role",
                        )
                    }
                )
        revision_context = self._persisted_revision_context(task, snapshot)
        prior_review = copy.deepcopy(job["private"].get("prior_review"))
        if isinstance(revision_context, dict) and revision_context.get("status") == "revision_required":
            prior_review = {
                "decision": "block",
                "summary": "独立终稿审查要求修订当前规范稿。",
                "objections": copy.deepcopy(revision_context["initial_review"]["objections"]),
                "review_sha256": revision_context["initial_review"]["review_sha256"],
                "manuscript_head_sha256": revision_context["manuscript_head"]["head_sha256"],
            }
        return {
            "contract": "paperspine5.web-agent-context",
            "schema_version": "1.0",
            "task": {
                "task_id": task["task_id"],
                "title": task.get("title"),
                "revision": task["revision"],
                "workspace_root": task["workspace_root"],
                "run_root": task["run_root"],
                "core_root": task["core_root"],
                "material_grants": grants,
                "product_manifest": task["product_manifest"],
            },
            "runner_snapshot": safe_snapshot,
            "skill_path": str(self.standalone_skill_path),
            "orchestrator_contract": str(
                self.project_root / "03_联合开发" / "ACADEMIC_STAGE_ORCHESTRATOR.md"
            ),
            "user_message": job["private"].get("user_message"),
            "prior_question": job["private"].get("prior_question"),
            "prior_review": prior_review,
            "revision_context": revision_context,
            "user_revision_request": copy.deepcopy(snapshot.get("user_revision_request")),
            "material_profile": material_profile,
            "material_transport": {
                "contract": "paperspine5.agent-material-reference-boundary",
                "schema_version": "1.0",
                "mode": "reference_only",
                "inventory_pointer": copy.deepcopy(
                    safe_snapshot.get("material_inventory")
                ),
                "binary_references": binary_references,
                "inline_binary_allowed": False,
                "inline_base64_allowed": False,
                "image_coverage_preserved": True,
                "fail_closed": True,
                "external_action_authorized": False,
            },
            "host_identities": {
                role: _host_identity(job, role)
                for role in ("producer", "reviewer", "author")
            },
            "host_materialization": {
                "j7_material_figure_sources": {
                    "enabled": True,
                    "inventory_pointer": copy.deepcopy(
                        safe_snapshot.get("material_inventory")
                    ),
                    "descriptor_artifact_id": "material ledger entries[].source_id",
                    "producer_sha_semantics": "material file SHA-256 transport assertion",
                    "runner_sha_semantics": "host-derived canonical JSON input SHA-256",
                    "fails_closed": True,
                },
                "j8_canonical_files": {
                    "enabled": True,
                    "required_files": {
                        "source": ".tex",
                        "pdf": ".pdf",
                        "word": ".docx",
                    },
                    "required_surface_page_format": "png",
                    "producer_status": "REVIEW_REQUIRED",
                    "independent_review": True,
                    "native_word_layout_verified": False,
                    "required_word_figure_media": {
                        "contract": "paperspine5.word-figure-media-transport",
                        "schema_version": "1.0",
                        "selected_figure_format": "png",
                        "embedded_pdf_allowed": False,
                        "mapping_fields": [
                            "figure_id",
                            "source_artifact_id",
                            "word_media_path",
                            "conversion_method",
                        ],
                        "conversion_scope": "word-delivery-surface-only",
                        "host_recomputes_source_and_media_hashes": True,
                    },
                    "word_surface_repair_script": str(
                        self.standalone_skill_path.parent
                        / "scripts"
                        / "word_surface_repair.py"
                    ),
                    "binding_spec_path": None,
                    "binding_spec_contract": "paperspine5.canonical-binding-spec/1.0",
                    "binding_spec_compiler": "paperspine_figure_integration.compile_canonical_artifacts",
                    "fails_closed": True,
                },
                "j9_independent_review": {
                    "enabled": True,
                    "producer_transport": "host_review_pages",
                    "runner_manuscript_head_required": True,
                    "runner_base_file_manifests_required": True,
                    "independent_review": True,
                    "producer_self_review_allowed": False,
                    "fails_closed": True,
                },
                "j10_target_package": {
                    "enabled": True,
                    "archive_artifact_id": "bundle_archive",
                    "target_obligation_authority": "host-derived-from-typed-j4-hard-rules",
                    "target_obligation_id_scheme": "target-rule:<authority_rule_id>",
                    "runner_base_file_manifests_required": True,
                    "minimal_payload": {"requested_scope": "local_delivery"},
                    "review": None,
                    "includes": ["pdf", "word", "source", "recursive_active_source_dependencies", "registered_editable_figure_sources_and_dependencies"],
                    "archive_hash_authority": "host-derived canonical JSON input SHA-256",
                    "local_only": True,
                    "external_action_authorized": False,
                    "fails_closed": True,
                },
            },
            "external_action_authorized": False,
        }

    def _codex_sqlite_home_config(self, task: dict[str, Any]) -> str:
        """Keep resumable Codex state inside the task's writable workspace."""

        workspace_root = Path(task["workspace_root"]).resolve()
        sqlite_home = (workspace_root / ".paperspine5-agent-state" / "sqlite").resolve()
        try:
            sqlite_home.relative_to(workspace_root)
        except ValueError as exc:
            raise RuntimeError("Codex SQLite state escaped the task workspace") from exc
        sqlite_home.mkdir(parents=True, exist_ok=True)
        return f"sqlite_home={json.dumps(str(sqlite_home), ensure_ascii=False)}"

    @staticmethod
    def _isolated_codex_home(task: dict[str, Any]) -> Path:
        """Return an empty task-local profile or fail closed before parent history use."""

        workspace_root = Path(task["workspace_root"]).resolve()
        codex_home = (
            workspace_root / ".paperspine5-agent-state" / "codex-home"
        ).resolve()
        try:
            codex_home.relative_to(workspace_root)
        except ValueError as exc:
            raise RuntimeError("Codex child profile escaped the task workspace") from exc
        codex_home.mkdir(parents=True, exist_ok=True)
        if (codex_home / "auth.json").exists():
            raise RuntimeError("Codex child profile must not contain copied credentials")
        return codex_home

    def _command(self, task: dict[str, Any], schema_path: Path, result_path: Path) -> list[str]:
        return [
            self.codex_executable,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--strict-config",
            "--skip-git-repo-check",
            "-c",
            'cli_auth_credentials_store="keyring"',
            "-c",
            self._codex_sqlite_home_config(task),
            "-c",
            'mcp_servers={}',
            "-c",
            'features.plugins=false',
            "-c",
            'features.multi_agent=false',
            "-c",
            'history.persistence="none"',
            "-m",
            "gpt-5.6-terra",
            "-c",
            'model_reasoning_effort="low"',
            "-s",
            "workspace-write",
            "-C",
            task["workspace_root"],
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(result_path),
            "-",
        ]

    def _review_command(
        self,
        task: dict[str, Any],
        schema_path: Path,
        result_path: Path,
        *,
        image_paths: list[Path] | None = None,
    ) -> list[str]:
        command = [
            self.codex_executable,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--strict-config",
            "--skip-git-repo-check",
            "-c",
            'cli_auth_credentials_store="keyring"',
            "-c",
            self._codex_sqlite_home_config(task),
            "-c",
            "mcp_servers={}",
            "-c",
            "features.plugins=false",
            "-c",
            "features.multi_agent=false",
            "-c",
            'history.persistence="none"',
            "-m",
            "gpt-5.6-terra",
            "-c",
            'model_reasoning_effort="low"',
            "-s",
            "workspace-write",
            "-C",
            task["workspace_root"],
        ]
        for image_path in image_paths or []:
            command.extend(["--image", str(image_path)])
        command.extend(
            [
                "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(result_path),
            "-",
            ]
        )
        return command

    def _child_environment(
        self, task: dict[str, Any], snapshot: dict[str, Any]
    ) -> dict[str, str]:
        environment = dict(self.base_environment)
        # Agent/reviewer/repair workers may execute Python helpers from the
        # installed suite.  Their isolated environment must preserve the same
        # no-bytecode guarantee as the Product Web runtime.
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        for name in (
            "CODEX_CI",
            "CODEX_SESSION_ID",
            "CODEX_THREAD_ID",
            "CODEX_APP_TOOLS_PIPE_PATH",
            "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
        ):
            environment.pop(name, None)
        environment["CODEX_HOME"] = str(self._isolated_codex_home(task))
        run_contract = snapshot.get("run_contract")
        if not isinstance(run_contract, dict):
            run_contract = {}
        configuration = run_contract.get("configuration")
        if not isinstance(configuration, dict):
            configuration = {}
        network_policy = configuration.get("network_policy")
        if not isinstance(network_policy, dict):
            network_policy = run_contract.get("network_policy")
        if isinstance(network_policy, dict) and network_policy.get("allow_network") is True:
            environment.pop("CODEX_SANDBOX_NETWORK_DISABLED", None)
        return environment

    def _prompt(self, context_path: Path, result_path: Path, job: dict[str, Any]) -> str:
        return f"""你是 PaperSpine5 Product Web 内部的本地学术 Agent，不是用户界面。

强制边界：
1. 只使用 standalone paper-spine Skill：{self.standalone_skill_path.parent}。完整读取 SKILL.md 和当前阶段所需 playbook。禁止调用 paperspine5 插件 Skill、任何 paperspine5_* MCP 工具或隐式更新器。
2. 读取绑定上下文：{context_path}。只读其中列出的材料根；所有新产物只能写入 task.workspace_root。不得删除、覆盖材料源或执行外部投稿/上传/发送。context.material_transport 是强制边界：二进制/图像只能以 source_id、CAS/相对路径、SHA-256、大小和角色元数据引用；禁止把二进制读成文本、data URL 或 base64，禁止把编码字节写入 stdout、JSON、prompt 或学术 payload。需要观察图像时只能调用接收文件路径的图像/PDF工具，且结果仍只引用原路径与哈希，不能回显编码数据。
3. 当前工作必须绑定 task_id={job['task_id']}、revision={job['revision']}、issue_id={job['issue_id']}、stage={job['stage']}。读取当前 ProductRunner/AcademicStageOrchestrator 合同，生成真实、可验证、领域动态研究得到的阶段 payload；不要复制测试夹具事实、伪造来源/作者/审阅者/图件/数字或用审计 memo 冒充正文。
4. J5 contribution/motivation 必须严格两阶段：当前 Agent 只提交 `paperspine5.contribution-candidate-preparation` 的候选项、证据边界与 authority bindings，绝不能填写 decisions、author_identity、confirmed_at 或 override_blockers；宿主会在提交后把候选显示到普通 Product Web，由真实用户逐项确认。figure choice 与非作者本地 target adaptation 仍按精确 delegation grant 边界处理。作者事实、submission scope、licence/fee 与 external action 永远不能由 grant 代替用户确认。
5. 非人类门禁阶段应真实完成材料盘点、动态方向/目标研究、证据绑定、正文/图件/审阅/本地包工作，并把可审计产物写入 task.workspace_root。任何无法核验的必需事实返回 blocked；不得用占位符制造 PASS。
6. external_action_authorized 永远为 false。最终只输出 result schema 允许的 JSON；submit_stage 时把完整阶段 object 序列化到 stage_payload_json 字符串，awaiting_user/blocked 时该字段必须为 null。不要在最终 JSON 外输出解释。`--output-last-message` 会由宿主把你的最终消息原子写入结果路径；禁止直接创建、修改、apply_patch 或用命令写入该路径。结构化 JSON 一旦准备好，立即把它作为最终消息返回并结束进程，不要再调用工具。
6a. payload 顶层不得提供 Runner 保留的信任控制字段 subject、trusted_artifacts、frozen_authority、artifact_descriptors；它们只能由 Runner 根据当前任务注册工件派生，宿主会在独立复核和提交前剥离任何此类字段。
7. 本次只完成当前 stage，不提前执行后续 stage。优先复用 task.workspace_root 中已有盘点/研究证据；只生成当前 Runner 合同所需的最小充分产物与 payload。不要在已经形成结构化结果后继续调用工具。若 Windows 补丁工具因沙箱能力失败，可使用仍受 workspace-write 沙箱约束的本地写入命令，但目标必须保持在 task.workspace_root 内。
8. 必须由当前 Agent 独立完成本 stage。不得派生、委托、等待或调用任何子 Agent、协作代理、后台任务或新线程；不要使用 collaboration/multi-agent 工具。
9. context.host_identities 是宿主签发的当前 job 身份。awaiting_research、awaiting_claim_graph 与 awaiting_review 只负责形成 producer 候选；宿主会在你返回 submit_stage 后启动一个独立、隔离、顺序执行的 reviewer worker，并覆盖 challenger/J9 review 身份与结论，所以不得因“当前进程无法自审”而 blocked。awaiting_contribution 不得读取或使用 host_identities.author 来冒充用户；即使已有 user_message 或 delegation，也只形成候选准备，用户 identity 和 confirmed_at 由后续 Product Web confirmation issue 在 loopback session 边界记录。
10. J4 的 content-bound source artifact 可以是真实、可审计的本地冻结检索记录（至少含 URL/locator、retrieved_at、实际取得的 supported excerpt、访问通道与局限），不要求伪装成无法取得的整页镜像。对自动化挑战或只取得索引快照的页面，要使用 availability=lawful_frozen_cache、access_basis=lawful_cache，并在 input artifact 中如实记录其公开来源、取得通道与覆盖边界；不得写成当前 accessible。as_of_date 必须是 YYYY-MM-DD 日历日期，不能是时间戳。每个 sources[] 候选可临时携带 task.workspace_root 内的 artifact_path 供宿主读取实际 JSON；宿主会把实际对象写入 input_artifacts["source:<source_id>"]、派生 canonical content_sha256，并在送交 reviewer/Runner 前移除 artifact_path 及其他非 schema 搬运字段。只在实际摘录支持相应规则时纳入 covered_topics。
11. Web 阶段采用最小充分预算：J4 最多使用 4 个来源，每个来源最多 3 个必要 supported spans，required_topics 只保留合同与当前目标真正需要的最小集合。开始研究前必须读取 context.material_profile，并实际检查其中最高分 primary_manuscript_candidates、supplementary_manuscript_candidates、reference_libraries、主稿/补充稿图件依赖和 placeholder_categories；J4 对 `.tex`/`.bib` 使用有界文本读取，对全部图件只消费 context.material_transport.binary_references 的路径/哈希/大小/角色，不读取或回显其二进制字节。已有填充主稿时，方向陈述必须覆盖它真实存在的 Methods、Results、全部主稿图和参考库，不能把它降格为“只有模板/架构图”，也不能只凭文件名判断内容。material_profile 不可用或有未解析的关键主稿依赖时必须 blocked。目标已知且 network_status=online 时，最小充分集合必须同时含至少 1 个 official/official_hard 目标来源和 1 个与当前材料方向最接近、单独标为 exemplar_style/advisory 的合法公开领域邻居；advisory 不能冒充目标规则。official_hard 通道必须实际抽取至少 1 条 `kind=hard` 且 `enforcement=hard` 的规则，并绑定到含明确强制要求的官方 supported span。每个 hard rule 还必须从冻结证据显式给出 `readiness_scope=local_delivery|author_only_submission` 与 `evidence_locator`；只有固定作者事实可用后者且必须有 `author_fact_key`，不得从 statement/reason 猜层。仅能取得开放获取背景、索引摘要、recommended/建议措辞或其他上下文时，即使网页属于目标官网，也不能据此声称硬规则完成，必须按 advisory 如实登记并在没有别的真实硬规则来源时返回 blocked。每个 required_topics/covered_topics 项都必须形成“冻结摘录 → sources.source_id → rules.source_ids → rule enforcement”的闭环；若摘录写的是 recommended/建议，即使来源是官方页也必须作为 advisory，而不能提升成 hard。sources[] 必须具备当前 runtime-research-bundle schema 的全部必填字段；宿主只会把缺失的 valid_until 最保守地归一为 as_of_date，不会替 producer 补写学术规则。确实无法取得任一通道时返回 blocked，不能把单通道伪装成研究完成。research_scope_sha256、research_snapshot_sha256 及 challenger.research_snapshot_sha256 是 reviewer 通过后由 Runner 从实际 input_artifacts/覆盖集合派生的字段，producer 可省略或使用全零哨兵，不得自行伪造非零值。不要在 J4 预做贡献决定、正文、图件或后续关卡，也不要为重复验证临时编写大型辅助程序；形成可由 Runner 接受的当前 payload 后立即返回。
11b. J5 只准备候选，合同必须是 `paperspine5.contribution-candidate-preparation/1.0`，顶层只含 authority_bindings、candidates、可选 input_artifacts 与 external_action_authorized=false；不得输出决定或确认元数据。必须区分比较性贡献与非比较描述。仅作结构/流程描述或读者可核查的写作动机，并明确不主张新颖性、优越性、既有方法缺陷或性能时，相应 contribution/motivation candidate 应设置 `comparative_claim=false`；此时 `direct_competitor_source_ids` 可以为空，不得为过门禁把 exemplar_style/advisory 冒充竞争者。候选仍必须绑定正面材料、counterevidence 或缺失证据记录、limitation_ids 和可证伪 boundary_statement。任何比较性主张或未明确 `comparative_claim=false` 的旧候选仍必须绑定真实直接竞争来源。宿主会覆盖 authority_bindings 为当前 Runner 的 direction_authority、target_authority 与 materials.source-ledger 哈希，然后创建普通 Web 用户确认 issue。
11a. J6 必须把当前合同要求的完整主张—证据图直接序列化进 stage_payload_json；不得返回 `see result.json`、仅文件路径或其他未被宿主哈希绑定的间接指针。每条边的 wire object 必须且只能是 `{{"from":"<node_id>","relation":"<licensed relation>","to":"<node_id>"}}`；`from_node_id` / `edge_type` / `to_node_id` 等别名不受支持。每个 core claim 都必须同时提供七组类型与方向精确的互反边：`claim-supported_by->evidence` / `evidence-supports->claim`，`claim-grounded_in->result` / `result-grounds->claim`，`claim-cited_context|cited_support->citation` / `citation-supports_context->claim`，`claim-limited_by->limitation` / `limitation-limits->claim`，`claim-warranted_by->warrant` / `warrant-warrants->claim`，`claim-bounded_by->boundary` / `boundary-bounds->claim`，`claim-challenged_by->counterevidence` / `counterevidence-challenges->claim`。若某个 result/evidence 节点描述从图表直接观察到的结构或输出，它必须定位到 materials.source-ledger 中的实际图表工件及具体锚点，不能用作者确认的 contribution 文本充当结果证据。目标已知且 J4 冻结了 official_hard 与 exemplar_style/advisory 时，必须为二者建立不同的 citation 节点，分别绑定各自 `source:<source_id>` 的实际哈希与冻结 locator；它们与核心主张只使用 `cited_context` / `supports_context` 语境边，不得使用 `cited_support` 冒充科学证据。只有真实科学引用直接支持相应主张时才可使用兼容关系 `cited_support`。若 context.prior_review 已列出异议，必须逐条修正实际完整图后再提交。
11c. J6 的 subject、contribution_decision.sha256、引用 `direction_authority` / `target_authority` / `contribution_boundary_decision` 的 node.source_sha256、graph_snapshot_sha256 与 challenger.graph_snapshot_sha256 是 AcademicStageOrchestrator 的权威派生字段。producer 候选应为这些尚不可知的字段保留全零哨兵，不能猜测前一 revision 的哈希；独立 reviewer 只复核完整语义图，随后宿主按当前 revision 累计重放并覆盖派生哈希、重算图快照，Runner 再做最终合同验证。全零哨兵只允许用于这些派生字段；材料与冻结外部来源的 source_sha256 仍必须使用 context 中当前真实值，所有 statement_sha256、locator、互反边和语义角色都必须完整。
12. J7 必须区分“作者选择”和“候选已经存在”。先以 context.material_profile 的最高分主稿为权威盘点基线；主稿引用的每张科学图都必须进入一个完整决策，不得只展示或选择第一张图。intent.material_coverage 必须绑定 primary_manuscript_source_id，并用 figure_dispositions 覆盖全部 main_manuscript_figure_source_ids：有效 `figure_keep_or_transform` grant 可采用全部 `selected` 的保守保留/可逆转换路径并逐图留 decision receipt；任何 `supplementary` 或 `omit` 只有在精确 `figure_supplement` / `figure_omit` class 已授权时才可代决策，否则必须在网页提出一个列明图号、原稿用途与后果的精确问题并绑定当前用户回答。不得用 keep/transform class 静默扩大为 omit/supplement。redesign/create 只有真实候选资产及合同要求的独立比较已经形成时才可 submit_stage；不得把图件审计 memo 当候选。如果当前运行无法生成候选，返回 awaiting_user，并提供“保留已核验原图（说明局限）”或“暂停等待候选”的诚实选择。每个公开 asset 最终都必须只有 artifact_id、sha256、revision_id；redesign/create 还必须提供 candidate_assets 与只含 reviewer_id、producer_ids、status=PASS、reviewed_asset_hashes、decision、selected_sha256 的 independent_comparison，禁止 winner、candidate_artifact_ids 等别名。keep 按当前 revision 的 material_inventory 账本中精确原图构造：current_asset.artifact_id 使用账本 entries[].source_id，sha256 可使用该 entry 的原文件 SHA-256 作为搬运断言。宿主会验证画像、授权/用户回答、账本指针、原文件对象哈希与大小，把 asset revision_id 绑定当前 issue revision，并把 descriptor.sha256、reviewed_asset_hashes 与 selected_sha256 一起改写为 Runner canonical input hash；material_coverage 只是 producer→host 搬运字段，不会泄漏到 exact public answer。不得因为 source_id 尚未出现在提交前 subject.input_hashes 而 blocked，也不得漏图或伪造比较。
13. J8 的职责是从冻结的 contribution/claim graph/figure intent 与只读材料中真正形成当前规范主稿。必须优先以 context.material_profile 中最高分、已填充的 primary_manuscript_candidate 为内容基线，读取其 Methods、Results、图件、参考库及补充稿，保留所有受证据支持且未被用户明确处置的科学内容；禁止把完整原稿改写成更小的流程说明、审计 memo 或“本地验收稿”。只有画像确认没有预存主稿时，才从材料构建新稿。必须在 task.workspace_root 内生成 UTF-8 LaTeX source、真实 PDF、真实 DOCX，把 J7 选择的每张图以精确字节依赖嵌入、分别 `\\label` 并在正文逐图引用；不得用一个 `\\ref` 冒充全部图的绑定。目标为 Original Paper 且材料含 Methods/Results 时，规范稿也必须保留对应科学章节和目标模板；不得在稿件表面写入 `not submission-ready`、`NOT FOR SUBMISSION`、`local acceptance manuscript` 等内部状态语句。证据不足的主张应收缩或列为限制，但不能删除材料中已经存在且可核验的结果。若 context.prior_review.decision=block，必须逐条解决属于 J8 页面、正文、图件、规范主稿或文件绑定范围内的 objections，修改真实源文件并重新生成受影响的 PDF、DOCX 与全部逐页 PNG，不得原样重交。图件应放在首次解释其结果的位置附近。可用当前 PATH 中的 pdflatex/pandoc/pdfinfo/pdftoppm；Word 表面若无 LibreOffice，允许用 `pandoc manuscript.docx -o word-render.pdf --pdf-engine=xelatex` 做真实 DOCX 内容往返渲染，但必须在 bundle.limitations 声明这不是 Microsoft Word 原生布局验证。PDF 与 Word 往返 PDF 都要逐页生成 PNG。payload 必须包含 canonical_bundle、manuscript_revision、两个 REVIEW_REQUIRED surface receipt 及 `host_canonical_files={{"files":{{"source":"task-relative .tex","pdf":"task-relative .pdf","word":"task-relative .docx"}}}}`；宿主会重验材料覆盖、章节、模板、逐图字节/label/ref、文件和页面后再启动独立 reviewer。不得自行捏造 PASS reviewer。
13a. 当 `context.host_materialization.j8_canonical_files.binding_spec_path` 指向 task workspace 内的真实 canonical binding spec file 时，先以 `compile_canonical_artifacts(project_root, binding_spec_path, ...)` 从该绑定规范派生 canonical bundle，再继续使用同一任务的真实字节与受限表面；不得把 schema 文件、手写 JSON 或旧 bundle 冒充 binding spec，也不得跳过真实文件校验。
13b. Word 是独立的读者表面，不能把原始 main.tex 直接丢给 Pandoc 后忽略警告。应从当前规范稿生成 task 内的 Word 专用中间源，展开或替换自定义 citation、figure-reference 与其他 `\\newcommand` 宏；把所有引文改成 Pandoc 可识别且与实际 bibliography key 绑定的形式，使用实际 `.bib` 调用 `--citeproc --bibliography=... --metadata reference-section-title=References --metadata nocite=@*`，按唯一 BibTeX key 保留完整参考库，并披露材料画像中的重复 key；移除 Word 中不需要的 equation label，并把 Pandoc 不支持的公式改写为可转换的等价 TeXMath、清晰的线性公式或真正渲染的公式图。禁止出现原始 `$$\\begin{{equation}}`、空引文标点或未展开 `\\cite...`。Word 不能直接嵌入规范 PDF 图件：必须保留六张 canonical PDF 原字节，仅在 Word 专用中间源中确定性转换为 PNG；`word/media/*.pdf` 即使数量正确也不能满足 image-complete。`host_canonical_files.word_figure_media` 必须使用 `paperspine5.word-figure-media-transport/1.0`，逐图给出 figure_id、source_artifact_id、真实 DOCX 内部 `word/media/*.png` 路径和 `pdf-to-png`，宿主会解包核对正文关系、PNG magic、源/输出 SHA-256、六图一对一覆盖和相同 Word 逐页渲染证据。若 Pandoc 生成的 DOCX 仍有 raw display math 或 Word→PDF 报内部图件超链接未解析，不得 blocked 或自行编写一次性修补器；必须调用 context.host_materialization.j8_canonical_files.word_surface_repair_script，把原始公式渲染为真正图片、解开内部链接但保留可见图号，再以修复后的 DOCX 作为当前 Word artifact。转换后必须把 DOCX 往返为 plain text 与 PDF，自查 References 标题及全部唯一材料参考条目数量、非空正文引文、所有公式无 raw TeX，再生成全部 Word PNG；修复后仍有 math/citation warning 时才可 blocked。宿主会解包重验 DOCX 的参考库、引文、公式和图像媒体，失败时不会启动独立 reviewer。
14. J9 awaiting_review 不由当前 producer 自审。读取当前 task.workspace_root 中已由 J8 生成并通过的逐页 PNG，只提交最小 transport：`host_review_pages={{"pdf":["task-relative page PNG"],"word":[...]}}`；可以省略 initial_review，且不得捏造 reviewer、review_sha256、PASS、异议关闭、target finding 或 claim-retention 结论。宿主会从 Runner 当前 academic_base_artifacts、publication.manuscript-head、冻结 target authority 和 J8 canonical bundle 重新核对 source/PDF/DOCX 清单及实际文件字节，确定性派生 `target-rule:<authority_rule_id>` 义务清单，把页面及全部 hard non-author rules 交给新的隔离 reviewer，并在其返回逐规则 satisfied/unsatisfied typed finding 后绑定当前 target/surface hash、重哈希进 initial_review。缺一条、额外 rule、ID 漂移或无 evidence locator 都 fail closed。若页面文件确实缺失才 blocked；不能仅因当前进程不能独立自审而 blocked。
15. J10/J11 awaiting_package 的普通本地交付默认仅提交原 answer.payload={{"requested_scope":"local_delivery"}}，review=null。这一个精确 compact 请求由宿主从当前已接受 canonical head、E6 claim scope、J8 surfaces、J9 review closure 与 J4 target 自动组成原 J10 输入；未知证据保持 unknown，原始独立审查的狭窄范围不扩大，不声称新的引用/科学/视觉 PASS。完整显式 payload 仅为兼容路线，必须完整且先验证，不能用空对象或预填 PASS 代替证据；不得给宿主派生字段手填哨兵。target obligation ledger 由宿主从 J4 typed hard rules 确定性派生，稳定 ID 为 `target-rule:<authority_rule_id>`，不能制造、遗漏或重分类 obligation；分层使用 readiness_scope=local_delivery|author_only_submission，不得从 statement/reason 猜层。每个本地义务须由当前独立 closure 中同 rule、同 artifact/hash 的 `paperspine5.target-obligation-finding/1.0 status=satisfied` 支持，mapping.status 或 readiness predicate 自报不能补偿 unsatisfied；有未满足规则时 `target_compliance_valid` 也必须为 false。若所有本地要求实际成立，未知作者事实不阻止本地交付，不得停在 awaiting_package；不得把这种局部完成升级为 submission_ready。作者事实只可由真实当前用户事实确认，完整兼容路线中的 author_close 要求 synthetic=false、confirmation_scope=real_author_fact 和真实 user_confirmation_sha256；compact 请求保留 author_close=[]，绝不自动补作者。`context.host_materialization.j10_target_package.enabled=true` 表示宿主重读当前 J8 source/PDF/DOCX 和页面 bytes，递归解析**去除 TeX 注释后的 active dependencies**（含本地 cls/sty/bst），仅纳入已登记 editable 图源及其明确登记依赖，保留相对路径。未知动态依赖、越界、冲突、symlink、hash 改动必须报错，不扫描原始私有材料。不得自行伪造 ZIP/哈希，或复制注释中不存在的 bibliography 兼容副本。只有真实 ZIP member bytes/CRC 校验后 manifest 才标 PASS；该 PASS 仅指本地包，不是投稿或新的学术通过。实际请求 scope 不得暗中下调，对外权限始终 false。

修订回路：若 context.revision_context.status=revision_required，当前 J8 必须保留旧审查、旧源稿、PDF、DOCX 和 PNG，不得覆盖它们；在新的 revision 子目录生成 .tex/PDF/DOCX 及全部页图。payload.revision_response 必须逐一使用 prior_review.objections 中的原始 objection_id，并只填写 evidence_locator 与 change_summary，说明实际改了什么；不得自报异议已关闭。随后的 J9 仍只提供当前 host_review_pages，宿主从 Runner 持久化旧审查和 J8 response 构造顶层 initial_review、revision_diff、re_review，并让新的独立 reviewer 决定 pass/block。J9 block 是真实 REVISION_REQUIRED 审查结果，会提交 Runner 后返回 J8，不得改写成 PASS 或重复原样提交。

用户反馈返修：context.user_revision_request.origin=user_feedback 仅是用户修改意图，不是 prior_review 或 PASS。按其 scope 从当前 J6/J7/J8 继续正常研究/图选择/主稿流程；保留上次已完成稿和包，在新目录写 .tex/PDF/DOCX/页图。新稿必须重新进入正常独立 J9，不能复制旧独立结论或把用户反馈转换成 reviewer objection。

宿主最终消息落盘路径（只用于识别，禁止由 Agent 直接写入）：{result_path}
"""

    def _format_repair_prompt(
        self,
        *,
        context_path: Path,
        invalid_result_path: Path,
        result_path: Path,
        job: dict[str, Any],
    ) -> str:
        return f"""你是 PaperSpine5 Product Web 宿主启动的结构化结果修复进程，不是新的研究 Agent。

只使用 standalone paper-spine Skill：{self.standalone_skill_path.parent}；禁止插件 Skill、paperspine5_* MCP、更新器、子 Agent、网络检索和外部操作。
读取绑定上下文 {context_path} 与格式损坏的外层结果 {invalid_result_path}。当前绑定必须保持 task_id={job['task_id']}、revision={job['revision']}、issue_id={job['issue_id']}、stage={job['stage']}、external_action_authorized=false。
唯一任务是恢复原候选的 JSON 序列化；不得重新研究、改写科学内容、提升状态、补造来源、作者事实、审阅结论或权限。优先读取 task.workspace_root 中由原 Agent 已写出的 payload candidate JSON；必须实际 json.loads 验证 payload 是 object，再用标准 JSON serializer 生成 stage_payload_json，禁止手工复制或编辑巨型转义字符串。
最终仅把 result schema 允许的 JSON 作为最终消息返回；`--output-last-message` 会由宿主写入 {result_path}，禁止直接创建、修改、apply_patch 或用命令写入该路径。submit_stage 必须含可被 json.loads 的完整 stage_payload_json；如原候选无法无歧义恢复，则返回 blocked 且 stage_payload_json=null，并在 summary 说明精确原因。不要输出额外解释；JSON 准备好后立即结束进程。
"""

    def _review_prompt(
        self,
        *,
        context_path: Path,
        candidate_path: Path,
        hash_preflight_path: Path,
        result_path: Path,
        job: dict[str, Any],
    ) -> str:
        return f"""你是 PaperSpine5 Product Web 宿主按顺序启动的独立关卡复核者。你与 producer 是不同的本地 Codex 进程，身份由宿主签发；你不是用户界面。

强制边界：
1. 只使用 standalone paper-spine Skill：{self.standalone_skill_path.parent}。完整读取 SKILL.md 和当前 stage 所需 playbook。禁止 paperspine5 插件 Skill、任何 paperspine5_* MCP 工具、隐式更新器、子 Agent、协作代理、后台任务或新线程。
2. 读取绑定上下文 {context_path}、候选 payload {candidate_path} 与宿主哈希预检 {hash_preflight_path}。只读材料根；不得修改候选、任务产物或材料源，不得投稿、上传或发送。
3. 只复核 task_id={job['task_id']}、revision={job['revision']}、issue_id={job['issue_id']}、stage={job['stage']}。独立检查候选是否受到真实材料、动态目标研究、冻结来源记录和当前合同支持；官方硬规则与 advisory exemplar 必须分离。不要因为 producer 声称完成就通过。
4. decision=pass 仅在当前 stage 的候选完整、来源可追溯、边界诚实且没有未解决异议时使用，此时 objections 必须为空。否则 decision=block，并给出精确、可操作的字符串异议。不得伪造来源、身份、用户决定、图件或数字。
5. external_action_authorized 永远为 false。最终只输出 review schema 允许的 JSON，不要输出额外解释。`--output-last-message` 会由宿主原子写入结果路径；禁止直接创建、修改、apply_patch 或用命令写入该路径。JSON 准备好后立即作为最终消息返回并结束进程。
6. 这是一次限定范围的关卡复核，不是第二次重做研究。抽查候选绑定的官方来源、领域邻居、覆盖集合和材料边界即可；不要扩展新的文献综述、生成论文产物或检查后续 stage。形成 decision 后立即返回。
7. sources[].content_sha256 的合同含义是对应 input_artifacts["source:<source_id>"] 的规范 JSON 字节后追加恰好一个 LF 字节 0x0A 的 SHA-256，不是原始网页或本地文件字节哈希。宿主预检按 `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + bytes([10])` 生成；复算也必须用 `bytes([10])`，不要在 PowerShell/Python 多层引号中使用可能变成两个字符的 `\\n`。若预检 match=true 且候选未变，不得用转义口径不同的手算结果否定它。网络记录若明确为 lawful_frozen_cache，原 URL 在复核时无法重开不能单独构成 blocker；应检查冻结摘录、检索通道、局限与规则是否一致。原始冻结文件的字节哈希/大小由每个 source input artifact 的 host_file_attestation 记录；不要拿规范记录哈希与原始文件哈希直接比较。
8. J4 producer 候选中的 research_scope_sha256、research_snapshot_sha256 与 challenger.research_snapshot_sha256 允许缺失或为全零哨兵：独立复核通过是 Runner 根据实际 input_artifacts、direction/target/coverage 计算并绑定这些值的前置条件。不得仅因这些 Runner 派生字段在候选阶段尚未生成而 block；应复核其输入是否足以让 Runner 确定性派生。目标已知且 network_status=online 时，仍必须检查至少一个 official_hard 目标来源与一个分离的 exemplar_style/advisory 直接领域邻居，缺少任一真实通道应 block。
8a. J6 中每条边必须且只能使用 `from` / `relation` / `to`，并按 producer 同一份七组精确词表检查节点类型、方向与互反边；不得接受 `from_node_id` / `edge_type` / `to_node_id` 别名。`cited_context` / `supports_context` 是目标规则、exemplar_style/advisory 等非科学支持语境的合规双向关系；不得要求这类节点改成 `cited_support`。目标已知且 J4 同时冻结 official_hard 与 exemplar_style/advisory 时，两者必须是来源、哈希、locator 和角色均分离的 citation 节点。`cited_support` 只适用于真正直接支持科学主张的引用。
8b. J6 producer 候选中的 subject、contribution_decision.sha256、引用 `direction_authority` / `target_authority` / `contribution_boundary_decision` 的 node.source_sha256、graph_snapshot_sha256 与 challenger.graph_snapshot_sha256 是 AcademicStageOrchestrator 的权威派生字段。候选阶段允许缺失或使用全零哨兵；宿主只有在你的独立语义复核通过后，才会按当前 revision 累计重放 J4/J5、覆盖这些派生哈希并重算图快照，随后由 Runner 合同再次验证。不得仅因这些派生字段尚未绑定而 block，也不得要求 producer 猜测前一 revision 的哈希。你仍必须检查每个 node 的 source_artifact_id、statement_sha256、locator、status、互反边和语义角色是否完整；非派生材料/来源哈希必须与当前冻结输入一致，贡献、动机、限制、边界及 counterevidence locator 必须确实能定位到其声明的冻结工件。
9. J8 producer 候选的 canonical_bundle、manuscript_revision、figure/surface receipts 在送达 reviewer 时应为 REVIEW_REQUIRED；这是宿主尚未绑定你的独立结论，不是 blocker。宿主已通过 Codex `--image` 附加 PDF 与 Word 的每一页 PNG；必须真正逐页观察。先读取 context.material_profile 与 candidate.canonical_bundle.material_coverage，核对最高分原始主稿的题目、Methods、Results、主稿图、补充图、参考库和 placeholder 边界是否在规范稿中得到保存或有当前用户明确处置；逐张检查 J7 选择的所有图都真实出现、图注正确、正文分别引用，禁止只检查 Figure 1。若原始主稿是完整 Original Paper，3 页流程说明、通用 article 模板、单图/单参考文献、巨大空白、内部“not submission-ready/local acceptance”措辞或无理由丢失 Results/图件均必须 block。还要核对 LaTeX/PDF/DOCX 三个 host-derived manifest 指向真实当前文件。只有科学内容覆盖、目标适配、页面可读性和证据边界全部通过才 decision=pass；schema/哈希通过不能替代稿件质量。Pandoc DOCX 往返渲染不是 Microsoft Word 原生布局验证，应保留为后续 readiness 限制，但页面真实、可读、内容一致时不单独阻断本地 J8 候选。
10. J8 复核只裁定当前页面、正文、图件、规范主稿和 host-derived 文件绑定，不重新裁定 J4 的目标来源/官方硬规则是否充分，也不得要求在 J8 payload 中重复上游原始来源。上游权威由 Runner 在本次提交后的累计门禁重放中检查；如果 J4 权威不足，Runner 必须审计回退到 J4，而不是由 J8 reviewer 越权阻断一份本身合格的页面候选。
11. J9 reviewer 必须独立逐页观察宿主附加的当前 PDF 与 Word 页面，并检查 candidate 中 `_host_j9_review` 的 current-head、文件清单、页面哈希、宿主派生 target obligation ledger 与当前 review artifact 绑定。以 context.material_profile、冻结 claim graph、全部 figure intent 和 target authority 反向核对：原稿可核验的科学结果、所有已选图、核心主张、参考文献与目标稿件结构都必须保留，未证实内容必须有边界，内部测试/就绪措辞不得泄漏到论文。任何“内部一致但相对材料严重缩水”的稿件都必须 block。对 ledger 中每个 `readiness_scope=local_delivery` hard rule，`target_rule_findings` 必须恰好返回一项相同 authority_rule_id、`satisfied|unsatisfied` 与可定位当前页面/工件的 evidence_locator；不能省略、添加、改名或替 producer 自报 satisfied。hard rule 未满足时如实写 unsatisfied；它会阻断 delivery 而不必把内容完整的 manuscript 判为 block。J9 reviewer 不生成或修改稿件，也不接受 producer 自签的审阅结论。

宿主最终消息落盘路径（只用于识别，禁止由 reviewer 直接写入）：{result_path}
"""

    @staticmethod
    def _validate_result(result: dict[str, Any], job: dict[str, Any]) -> None:
        if not isinstance(result, dict):
            raise ValueError("Agent result must be an object")
        expected = {
            "contract": "paperspine5.web-agent-result",
            "schema_version": "1.0",
            "task_id": job["task_id"],
            "revision": job["revision"],
            "issue_id": job["issue_id"],
            "stage": job["stage"],
            "external_action_authorized": False,
        }
        for key, value in expected.items():
            if result.get(key) != value:
                raise ValueError(f"Agent result binding mismatch: {key}")
        status = result.get("status")
        if status not in {"submit_stage", "awaiting_user", "blocked"}:
            raise ValueError("Agent result status is invalid")
        if status == "submit_stage":
            raw_payload = result.get("stage_payload_json")
            if not isinstance(raw_payload, str):
                raise ValueError("submit_stage requires stage_payload_json")
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError as exc:
                raise ValueError("stage_payload_json must contain valid JSON") from exc
            if not isinstance(payload, dict):
                raise ValueError("stage_payload_json must contain an object")
        elif result.get("stage_payload_json") is not None:
            raise ValueError("non-submit result cannot carry stage_payload_json")
        if status == "awaiting_user" and not str(result.get("question") or "").strip():
            raise ValueError("awaiting_user requires one question")

    def _job_dir(self, task_id: str, job_id: str) -> Path:
        return self.control_root / "jobs" / task_id / job_id

    def _job_path(self, task_id: str, job_id: str) -> Path:
        return self._job_dir(task_id, job_id) / "job.json"

    def _latest_path(self, task_id: str) -> Path:
        return self.control_root / "jobs" / task_id / "latest.json"

    def _write_job(self, job: dict[str, Any]) -> None:
        with self._lock:
            job["updated_at"] = _now()
            _atomic_json(self._job_path(job["task_id"], job["job_id"]), job)
            _atomic_json(self._latest_path(job["task_id"]), job)

    def _read_job(self, task_id: str, job_id: str) -> dict[str, Any]:
        return json.loads(self._job_path(task_id, job_id).read_text(encoding="utf-8"))

    def _task_id_for_job(self, job_id: str) -> str:
        with self._lock:
            for task_id, active_id in self._active.items():
                if active_id == job_id:
                    return task_id
        raise RuntimeError("Agent job is no longer active")


__all__ = ["ProductWebAgentRuntime", "RESULT_SCHEMA"]
