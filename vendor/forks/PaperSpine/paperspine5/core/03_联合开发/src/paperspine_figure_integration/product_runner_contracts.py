"""Typed contracts for the version-locked PaperSpine5 Product Runner."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from .contracts import ContractError
from .product_contracts import PRODUCT_SCHEMA_VERSION, SHA256


RUNNER_VERSION = "0.2.0"
RUNNER_PROTOCOL_VERSION = "1.0"
READABLE_RUNNER_VERSIONS = {"0.1.0", RUNNER_VERSION}
RUNNER_STAGES = {
    "uninitialized",
    "awaiting_materials",
    "awaiting_configuration",
    "configured",
    "awaiting_research",
    "awaiting_contribution",
    "awaiting_claim_graph",
    "awaiting_figure_intent",
    "awaiting_canonical",
    "awaiting_review",
    "awaiting_package",
    "target_package_ready",
    # Read-only compatibility with the W3 writer.  The 0.2 writer converts
    # this boundary to awaiting_research on the next resume command.
    "blocked_j4",
}
WORKFLOWS = {
    "build_from_materials",
    "rewrite_existing",
    "audit",
    "review",
    "revise",
    "transfer",
}
SCENES = {"journal", "conference", "report", "review", "competition", "other"}
DELIVERABLES = {"latex", "pdf", "word"}
LANGUAGES = {"en", "zh", "multilingual", "other"}
ISSUE_CODE = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")
MANUSCRIPT_WORKFLOWS = {"rewrite_existing", "audit", "review", "revise", "transfer"}
MANUSCRIPT_SUFFIXES = {".tex", ".docx", ".doc", ".odt", ".rtf", ".md", ".pdf", ".txt"}
NON_MANUSCRIPT_MARKERS = {
    "readme",
    "license",
    "template",
    "guideline",
    "instructions",
    "requirements",
    "checklist",
}
REQUESTED_SCOPES = {"manuscript", "local_delivery", "submission_package"}
INTERACTION_MODES = {"guided", "delegated_local_test"}
LOCAL_DELEGATION_DECISION_CLASSES = {
    "contribution_selection",
    "motivation_selection",
    "non_author_local_target_adaptation",
    "figure_keep_or_transform",
    "figure_omit",
    "figure_supplement",
}
RUN_CONFIGURATION_FIELDS = {
    "workflow",
    "scene",
    "target",
    "output_language",
    "deliverables",
    "network_policy",
    "privacy",
    "budget",
    "author_voice_restoration",
    "requested_scope",
    "interaction",
    "research_mode",
}
LOCAL_DELEGATION_GRANT_FIELDS = {
    "contract",
    "schema_version",
    "grant_id",
    "task_id",
    "material_snapshot_sha256",
    "requested_scope",
    "decision_classes",
    "granted_at",
    "expires_at",
    "reversible",
    "explicit_user_grant",
    "confirmation_scope",
    "user_confirmation_sha256",
    "granting_actor",
    "authority_attestation_sha256",
    "external_action_authorized",
    "grant_sha256",
}


PUBLIC_RUN_CONFIGURATION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://paperspine5.local/contracts/run-configuration.schema.json",
    "title": "PaperSpine5 J3 run configuration answer",
    "description": (
        "Complete public input contract for a configuration.required Runner issue. "
        "Fields with defaults are optional, but the published example supplies every field."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "workflow",
        "scene",
        "target",
        "output_language",
        "deliverables",
        "network_policy",
        "privacy",
        "budget",
    ],
    "properties": {
        "workflow": {
            "enum": [
                "build_from_materials",
                "rewrite_existing",
                "audit",
                "review",
                "revise",
                "transfer",
            ]
        },
        "scene": {
            "enum": [
                "journal",
                "conference",
                "report",
                "review",
                "competition",
                "other",
            ]
        },
        "target": {
            "description": (
                "Use status=unknown with name=null when runtime research must determine the target."
            ),
            "oneOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["status", "name"],
                    "properties": {
                        "status": {"const": "known"},
                        "name": {"type": "string", "pattern": ".*\\S.*"},
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["status"],
                    "properties": {
                        "status": {"const": "unknown"},
                        "name": {"type": "null"},
                    },
                },
            ],
        },
        "output_language": {"enum": ["en", "zh", "multilingual", "other"]},
        "author_voice_restoration": {
            "enum": ["off", "standard", "strict"],
            "default": "off",
        },
        "requested_scope": {
            "enum": ["manuscript", "local_delivery", "submission_package"],
            "default": "local_delivery",
        },
        "interaction": {
            "default": {"mode": "guided", "grant": None},
            "oneOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["mode"],
                    "properties": {
                        "mode": {"const": "guided"},
                        "grant": {"type": "null"},
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["mode", "grant"],
                    "properties": {
                        "mode": {"const": "delegated_local_test"},
                        "grant": {"$ref": "#/$defs/local_delegation_grant"},
                    },
                },
            ],
        },
        "deliverables": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"enum": ["latex", "pdf", "word"]},
        },
        "network_policy": {
            "type": "object",
            "additionalProperties": False,
            "required": ["allow_network", "allow_external_upload"],
            "properties": {
                "allow_network": {"type": "boolean"},
                "allow_external_upload": {
                    "const": False,
                    "description": "J3 can never authorize uploading material.",
                },
            },
        },
        "privacy": {
            "type": "object",
            "additionalProperties": False,
            "required": ["allow_external_processing"],
            "properties": {"allow_external_processing": {"type": "boolean"}},
        },
        "budget": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "time_minutes": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "default": None,
                },
                "token_limit": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "default": None,
                },
                "cost_limit": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "default": None,
                },
            },
        },
        "research_mode": {
            "enum": ["agent_decide", "required", "materials_only"],
            "default": "agent_decide",
            "description": (
                "J4 policy. agent_decide lets the host Agent decide and record why; required "
                "runs the requested literature and/or data analysis; materials_only proceeds "
                "from the current authorized files and supplied results without a new search "
                "or data-mining pass."
            ),
        },
    },
    "allOf": [
        {
            "if": {
                "required": ["interaction"],
                "properties": {
                    "interaction": {
                        "required": ["mode"],
                        "properties": {"mode": {"const": "delegated_local_test"}},
                    }
                },
            },
            "then": {
                "required": ["requested_scope"],
                "properties": {
                    "requested_scope": {"enum": ["manuscript", "local_delivery"]}
                },
            },
        }
    ],
    "$defs": {
        "local_delegation_grant": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "contract",
                "schema_version",
                "grant_id",
                "task_id",
                "material_snapshot_sha256",
                "requested_scope",
                "decision_classes",
                "granted_at",
                "expires_at",
                "reversible",
                "explicit_user_grant",
                "confirmation_scope",
                "user_confirmation_sha256",
                "granting_actor",
                "authority_attestation_sha256",
                "external_action_authorized",
            ],
            "properties": {
                "contract": {"const": "paperspine5.local-delegation-grant"},
                "schema_version": {"const": PRODUCT_SCHEMA_VERSION},
                "grant_id": {"type": "string", "pattern": ".*\\S.*"},
                "task_id": {"type": "string", "pattern": ".*\\S.*"},
                "material_snapshot_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "requested_scope": {"enum": ["manuscript", "local_delivery"]},
                "decision_classes": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {
                        "enum": [
                            "contribution_selection",
                            "motivation_selection",
                            "non_author_local_target_adaptation",
                            "figure_keep_or_transform",
                            "figure_omit",
                            "figure_supplement",
                        ]
                    },
                },
                "granted_at": {"type": "string", "format": "date-time"},
                "expires_at": {"type": "string", "format": "date-time"},
                "reversible": {"const": True},
                "explicit_user_grant": {"const": True},
                "confirmation_scope": {"const": "delegated_local_test.initial"},
                "user_confirmation_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "granting_actor": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["actor_id", "surface", "authority_kind"],
                    "properties": {
                        "actor_id": {"type": "string", "pattern": ".*\\S.*"},
                        "surface": {
                            "enum": ["web", "codex", "standalone-skill", "mcp", "cli"]
                        },
                        "authority_kind": {
                            "enum": [
                                "authenticated_local_user_session",
                                "host_user_message",
                            ]
                        },
                    },
                },
                "authority_attestation_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "external_action_authorized": {"const": False},
                "grant_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                    "description": "Optional on input; the validator recomputes it.",
                },
            },
        }
    },
}

GUIDED_RUN_CONFIGURATION_EXAMPLE: dict[str, Any] = {
    "workflow": "build_from_materials",
    "scene": "journal",
    "target": {"status": "unknown", "name": None},
    "output_language": "en",
    "research_mode": "agent_decide",
    "author_voice_restoration": "off",
    "requested_scope": "local_delivery",
    "interaction": {"mode": "guided", "grant": None},
    "deliverables": ["latex", "pdf", "word"],
    "network_policy": {
        "allow_network": False,
        "allow_external_upload": False,
    },
    "privacy": {"allow_external_processing": False},
    "budget": {
        "time_minutes": None,
        "token_limit": None,
        "cost_limit": None,
    },
}


def public_run_configuration_schema() -> dict[str, Any]:
    return deepcopy(PUBLIC_RUN_CONFIGURATION_SCHEMA)


def guided_run_configuration_example() -> dict[str, Any]:
    return deepcopy(GUIDED_RUN_CONFIGURATION_EXAMPLE)


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{field} must be an object")
    return deepcopy(value)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")
    return value.strip()


def _digest(value: Any, field: str) -> str:
    result = _text(value, field).lower()
    if not SHA256.fullmatch(result):
        raise ContractError(f"{field} must be a lower-case SHA-256 digest")
    return result


def _canonical_sha256(value: Any) -> str:
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _timestamp(value: Any, field: str) -> dt.datetime:
    raw = _text(value, field)
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{field} must be an RFC 3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{field} must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def _validate_interaction(raw: Any, *, requested_scope: str) -> dict[str, Any]:
    interaction = _object(raw, "run_configuration.interaction")
    unknown = set(interaction) - {"mode", "grant"}
    if unknown:
        raise ContractError(
            "run_configuration.interaction contains unknown fields: "
            + ", ".join(sorted(unknown))
        )
    mode = interaction.get("mode")
    if mode not in INTERACTION_MODES:
        raise ContractError(
            "run_configuration.interaction.mode must be guided or delegated_local_test"
        )
    if mode == "guided":
        if interaction.get("grant") is not None:
            raise ContractError("guided interaction cannot carry a delegation grant")
        return {"mode": "guided", "grant": None}
    if requested_scope not in {"manuscript", "local_delivery"}:
        raise ContractError(
            "delegated_local_test is limited to manuscript or local_delivery scope"
        )
    grant = _object(interaction.get("grant"), "run_configuration.interaction.grant")
    unknown_grant = set(grant) - LOCAL_DELEGATION_GRANT_FIELDS
    missing_grant = (LOCAL_DELEGATION_GRANT_FIELDS - {"grant_sha256"}) - set(grant)
    if unknown_grant or missing_grant:
        details = []
        if unknown_grant:
            details.append("unknown=" + ",".join(sorted(unknown_grant)))
        if missing_grant:
            details.append("missing=" + ",".join(sorted(missing_grant)))
        raise ContractError("local delegation grant fields are invalid: " + "; ".join(details))
    if (
        grant.get("contract") != "paperspine5.local-delegation-grant"
        or grant.get("schema_version") != PRODUCT_SCHEMA_VERSION
    ):
        raise ContractError("local delegation grant contract/version is invalid")
    grant["grant_id"] = _text(grant.get("grant_id"), "local_delegation_grant.grant_id")
    grant["task_id"] = _text(grant.get("task_id"), "local_delegation_grant.task_id")
    grant["material_snapshot_sha256"] = _digest(
        grant.get("material_snapshot_sha256"),
        "local_delegation_grant.material_snapshot_sha256",
    )
    if grant.get("requested_scope") != requested_scope:
        raise ContractError("local delegation grant requested_scope differs from the run scope")
    decision_classes = grant.get("decision_classes")
    if (
        not isinstance(decision_classes, list)
        or not decision_classes
        or len(decision_classes) != len(set(decision_classes))
        or any(item not in LOCAL_DELEGATION_DECISION_CLASSES for item in decision_classes)
    ):
        raise ContractError(
            "local delegation decision_classes must be a non-empty unique supported subset"
        )
    grant["decision_classes"] = sorted(decision_classes)
    granted_at = _timestamp(grant.get("granted_at"), "local_delegation_grant.granted_at")
    expires_at = _timestamp(grant.get("expires_at"), "local_delegation_grant.expires_at")
    if expires_at <= granted_at:
        raise ContractError("local delegation grant must expire after it is granted")
    if grant.get("reversible") is not True or grant.get("explicit_user_grant") is not True:
        raise ContractError("local delegation requires an explicit reversible initial grant")
    if grant.get("external_action_authorized") is not False:
        raise ContractError("local delegation cannot authorize an external action")
    if grant.get("confirmation_scope") != "delegated_local_test.initial":
        raise ContractError("local delegation confirmation_scope is invalid")
    granting_actor = _object(
        grant.get("granting_actor"), "local_delegation_grant.granting_actor"
    )
    if set(granting_actor) != {"actor_id", "surface", "authority_kind"}:
        raise ContractError("local delegation granting_actor fields are invalid")
    granting_actor["actor_id"] = _text(
        granting_actor.get("actor_id"), "local_delegation_grant.granting_actor.actor_id"
    )
    if granting_actor.get("surface") not in {
        "web",
        "codex",
        "standalone-skill",
        "mcp",
        "cli",
    }:
        raise ContractError("local delegation must originate from a user-facing host surface")
    if granting_actor.get("authority_kind") not in {
        "authenticated_local_user_session",
        "host_user_message",
    }:
        raise ContractError("local delegation granting actor is not user-originated")
    grant["granting_actor"] = granting_actor
    confirmation_subject = {
        "confirmation_scope": grant["confirmation_scope"],
        "task_id": grant["task_id"],
        "material_snapshot_sha256": grant["material_snapshot_sha256"],
        "requested_scope": grant["requested_scope"],
        "decision_classes": grant["decision_classes"],
        "expires_at": grant["expires_at"],
        "reversible": True,
        "external_action_authorized": False,
    }
    expected_confirmation = _canonical_sha256(confirmation_subject)
    if grant.get("user_confirmation_sha256") != expected_confirmation:
        raise ContractError(
            "local delegation user_confirmation_sha256 does not bind the exact scoped authorization"
        )
    attestation_subject = {
        "granting_actor": granting_actor,
        "confirmation_scope": grant["confirmation_scope"],
        "user_confirmation_sha256": expected_confirmation,
    }
    if grant.get("authority_attestation_sha256") != _canonical_sha256(
        attestation_subject
    ):
        raise ContractError("local delegation host/user attestation does not recompute")
    supplied_hash = grant.pop("grant_sha256", None)
    expected_hash = _canonical_sha256(grant)
    if supplied_hash is not None and supplied_hash != expected_hash:
        raise ContractError("local delegation grant_sha256 does not bind the grant")
    grant["grant_sha256"] = expected_hash
    return {"mode": mode, "grant": grant}


def validate_delegation_user_authority(
    configuration: dict[str, Any], actor: dict[str, Any]
) -> None:
    """Require the J3 host actor that actually carried the user's scoped grant."""

    interaction = configuration.get("interaction")
    if not isinstance(interaction, dict) or interaction.get("mode") != "delegated_local_test":
        return
    grant = interaction.get("grant")
    if not isinstance(grant, dict):
        raise ContractError("local delegation grant is missing")
    actual = {
        "actor_id": actor.get("actor_id"),
        "surface": actor.get("surface"),
        "authority_kind": actor.get("authority_kind"),
    }
    if actual != grant.get("granting_actor"):
        raise ContractError(
            "local delegation requires the exact user-originated host actor from the J3 command"
        )


def validate_local_delegation_context(
    configuration: dict[str, Any],
    material_source_ledger: dict[str, Any],
    *,
    evaluation_time: str | None = None,
) -> None:
    """Bind a delegated grant to the real task, material snapshot, scope and time."""

    interaction = configuration.get("interaction")
    if not isinstance(interaction, dict) or interaction.get("mode") != "delegated_local_test":
        return
    grant = _object(interaction.get("grant"), "run_configuration.interaction.grant")
    if grant.get("task_id") != material_source_ledger.get("task_id"):
        raise ContractError("local delegation grant task_id does not match the Runner task")
    if grant.get("material_snapshot_sha256") != material_source_ledger.get(
        "snapshot_sha256"
    ):
        raise ContractError("local delegation grant material snapshot is stale")
    if grant.get("requested_scope") != configuration.get("requested_scope"):
        raise ContractError("local delegation grant scope is stale")
    now = (
        _timestamp(evaluation_time, "delegation_evaluation_time")
        if evaluation_time is not None
        else dt.datetime.now(dt.timezone.utc)
    )
    if _timestamp(grant.get("expires_at"), "local_delegation_grant.expires_at") <= now:
        raise ContractError("local delegation grant has expired")


def validate_material_source_ledger(
    raw: dict[str, Any], *, task_id: str, revision: int, build_id: str
) -> dict[str, Any]:
    value = _object(raw, "material_source_ledger")
    if value.get("contract") != "paperspine5.material-source-ledger":
        raise ContractError(
            "material_source_ledger.contract must be paperspine5.material-source-ledger"
        )
    if value.get("schema_version") != PRODUCT_SCHEMA_VERSION:
        raise ContractError(
            f"material_source_ledger.schema_version must be {PRODUCT_SCHEMA_VERSION}"
        )
    if value.get("task_id") != task_id or str(value.get("revision_id")) != str(revision):
        raise ContractError("material_source_ledger subject does not match task revision")
    if value.get("product_build_id") != build_id:
        raise ContractError("material_source_ledger product build does not match task")
    grants = value.get("grants")
    entries = value.get("entries")
    issues = value.get("scan_issues", [])
    if not isinstance(grants, list) or not isinstance(entries, list) or not isinstance(issues, list):
        raise ContractError("material_source_ledger grants, entries and scan_issues must be arrays")
    grant_ids: set[str] = set()
    for grant in grants:
        if not isinstance(grant, dict):
            raise ContractError("material_source_ledger grant must be an object")
        grant_id = _text(grant.get("grant_id"), "material_source_ledger.grant_id")
        if grant_id in grant_ids or grant.get("read_only") is not True:
            raise ContractError("material_source_ledger grants must be unique and read-only")
        grant_ids.add(grant_id)
        _digest(grant.get("snapshot_sha256"), "material_source_ledger.grant.snapshot_sha256")
    total_size = 0
    entry_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ContractError("material_source_ledger entry must be an object")
        source_id = _text(entry.get("source_id"), "material_source_ledger.entry.source_id")
        if source_id in entry_ids or entry.get("grant_id") not in grant_ids:
            raise ContractError("material_source_ledger source ids must be unique and grant-bound")
        entry_ids.add(source_id)
        relative_path = _text(
            entry.get("relative_path"), "material_source_ledger.entry.relative_path"
        )
        object_path = _text(
            entry.get("object_path"), "material_source_ledger.entry.object_path"
        )
        if relative_path.startswith(("/", "\\")) or ".." in relative_path.replace("\\", "/").split("/"):
            raise ContractError("material_source_ledger relative_path must remain within its grant")
        if not object_path.startswith("runner/materials/objects/"):
            raise ContractError("material_source_ledger object_path must use the immutable run store")
        _digest(entry.get("sha256"), "material_source_ledger.entry.sha256")
        size = entry.get("size_bytes")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ContractError("material_source_ledger entry size_bytes must be non-negative")
        total_size += size
    if value.get("source_count") != len(entries) or value.get("total_size_bytes") != total_size:
        raise ContractError("material_source_ledger totals do not match entries")
    _digest(value.get("snapshot_sha256"), "material_source_ledger.snapshot_sha256")
    privacy = _object(value.get("privacy"), "material_source_ledger.privacy")
    if privacy.get("external_transfer_authorized") is not False:
        raise ContractError("material_source_ledger cannot authorize external transfer")
    return value


def validate_run_configuration(raw: dict[str, Any]) -> dict[str, Any]:
    value = _object(raw, "run_configuration")
    unknown = set(value) - RUN_CONFIGURATION_FIELDS
    if unknown:
        raise ContractError(
            "run_configuration contains unknown fields: " + ", ".join(sorted(unknown))
        )
    workflow = value.get("workflow")
    scene = value.get("scene")
    language = value.get("output_language")
    if workflow not in WORKFLOWS:
        raise ContractError(f"run_configuration.workflow must be one of {sorted(WORKFLOWS)}")
    if scene not in SCENES:
        raise ContractError(f"run_configuration.scene must be one of {sorted(SCENES)}")
    if language not in LANGUAGES:
        raise ContractError(f"run_configuration.output_language must be one of {sorted(LANGUAGES)}")
    target = _object(value.get("target"), "run_configuration.target")
    unknown_target = set(target) - {"status", "name"}
    if unknown_target:
        raise ContractError(
            "run_configuration.target contains unknown fields: "
            + ", ".join(sorted(unknown_target))
        )
    target_status = target.get("status")
    if target_status not in {"known", "unknown"}:
        raise ContractError("run_configuration.target.status must be known or unknown")
    target_name = target.get("name")
    if target_status == "known":
        target["name"] = _text(target_name, "run_configuration.target.name")
    elif target_name is not None:
        raise ContractError("unknown target cannot carry a static target name")
    else:
        target["name"] = None
    deliverables = value.get("deliverables")
    if (
        not isinstance(deliverables, list)
        or not deliverables
        or len(deliverables) != len(set(deliverables))
        or any(item not in DELIVERABLES for item in deliverables)
    ):
        raise ContractError(
            "run_configuration.deliverables must be a non-empty unique subset of latex/pdf/word"
        )
    network = _object(value.get("network_policy"), "run_configuration.network_policy")
    privacy = _object(value.get("privacy"), "run_configuration.privacy")
    unknown_network = set(network) - {"allow_network", "allow_external_upload"}
    if unknown_network:
        raise ContractError(
            "run_configuration.network_policy contains unknown fields: "
            + ", ".join(sorted(unknown_network))
        )
    unknown_privacy = set(privacy) - {"allow_external_processing"}
    if unknown_privacy:
        raise ContractError(
            "run_configuration.privacy contains unknown fields: "
            + ", ".join(sorted(unknown_privacy))
        )
    if not isinstance(network.get("allow_network"), bool):
        raise ContractError("run_configuration.network_policy.allow_network must be Boolean")
    if network.get("allow_external_upload") is not False:
        raise ContractError("W3 run_configuration cannot authorize external upload")
    if not isinstance(privacy.get("allow_external_processing"), bool):
        raise ContractError("run_configuration.privacy.allow_external_processing must be Boolean")
    budget = _object(value.get("budget"), "run_configuration.budget")
    unknown_budget = set(budget) - {"time_minutes", "token_limit", "cost_limit"}
    if unknown_budget:
        raise ContractError(
            "run_configuration.budget contains unknown fields: "
            + ", ".join(sorted(unknown_budget))
        )
    for field in ("time_minutes", "token_limit", "cost_limit"):
        item = budget.get(field)
        if item is not None and (
            isinstance(item, bool) or not isinstance(item, (int, float)) or item < 0
        ):
            raise ContractError(f"run_configuration.budget.{field} must be null or non-negative")
    budget = {
        field: budget.get(field)
        for field in ("time_minutes", "token_limit", "cost_limit")
    }
    author_voice_restoration = value.get("author_voice_restoration", "off")
    if author_voice_restoration not in {"off", "standard", "strict"}:
        raise ContractError(
            "run_configuration.author_voice_restoration must be off, standard, or strict"
        )
    requested_scope = value.get("requested_scope", "local_delivery")
    if requested_scope not in REQUESTED_SCOPES:
        raise ContractError(
            "run_configuration.requested_scope must be manuscript, local_delivery, or submission_package"
        )
    interaction = _validate_interaction(
        value.get("interaction", {"mode": "guided", "grant": None}),
        requested_scope=requested_scope,
    )
    normalized = {
        "workflow": workflow,
        "scene": scene,
        "target": target,
        "output_language": language,
        "deliverables": list(deliverables),
        "network_policy": network,
        "privacy": privacy,
        "budget": budget,
        "author_voice_restoration": author_voice_restoration,
        "requested_scope": requested_scope,
        "interaction": interaction,
    }
    # Older persisted tasks may omit this additive policy. Project the safe,
    # explainable default for every reader so J3 and J4 expose one canonical
    # configuration without mutating the historical source bytes.
    research_mode = value.get("research_mode", "agent_decide")
    if research_mode not in {"agent_decide", "required", "materials_only"}:
        raise ContractError(
            "run_configuration.research_mode must be agent_decide, required, or materials_only"
        )
    normalized["research_mode"] = research_mode
    return normalized


def validate_configuration_material_semantics(
    configuration: dict[str, Any], material_source_ledger: dict[str, Any]
) -> None:
    """Reject workflows that claim an existing manuscript when none was inventoried."""
    validate_local_delegation_context(configuration, material_source_ledger)
    workflow = configuration.get("workflow")
    if workflow not in MANUSCRIPT_WORKFLOWS:
        return
    candidates: list[str] = []
    for entry in material_source_ledger.get("entries", []):
        if not isinstance(entry, dict) or not entry.get("size_bytes"):
            continue
        relative_path = entry.get("relative_path")
        if not isinstance(relative_path, str):
            continue
        path = relative_path.replace("\\", "/")
        name = path.rsplit("/", 1)[-1].lower()
        suffix = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        if suffix not in MANUSCRIPT_SUFFIXES:
            continue
        stem = name[: -len(suffix)] if suffix else name
        if any(marker in stem for marker in NON_MANUSCRIPT_MARKERS):
            continue
        candidates.append(path)
    if not candidates:
        raise ContractError(
            f"run_configuration.workflow={workflow} requires at least one non-empty "
            "manuscript-like material; templates, guidelines, README files, and empty "
            "directories cannot satisfy the intake gate"
        )


def validate_run_contract(
    raw: dict[str, Any], *, task_id: str, revision: int, build_id: str
) -> dict[str, Any]:
    value = _object(raw, "run_contract")
    if value.get("contract") != "paperspine5.run-contract":
        raise ContractError("run_contract.contract must be paperspine5.run-contract")
    if value.get("schema_version") != PRODUCT_SCHEMA_VERSION:
        raise ContractError(f"run_contract.schema_version must be {PRODUCT_SCHEMA_VERSION}")
    if value.get("task_id") != task_id or str(value.get("revision_id")) != str(revision):
        raise ContractError("run_contract subject does not match task revision")
    if value.get("product_build_id") != build_id:
        raise ContractError("run_contract product build does not match task")
    _digest(value.get("material_snapshot_sha256"), "run_contract.material_snapshot_sha256")
    value["configuration"] = validate_run_configuration(value.get("configuration"))
    if value.get("external_action_authorized") is not False:
        raise ContractError("run_contract cannot authorize external action")
    return value


def validate_runner_issue(raw: dict[str, Any], *, task_id: str) -> dict[str, Any]:
    value = _object(raw, "runner_issue")
    if value.get("contract") != "paperspine5.runner-issue":
        raise ContractError("runner_issue.contract must be paperspine5.runner-issue")
    if value.get("schema_version") != PRODUCT_SCHEMA_VERSION:
        raise ContractError(f"runner_issue.schema_version must be {PRODUCT_SCHEMA_VERSION}")
    if value.get("task_id") != task_id:
        raise ContractError("runner_issue.task_id does not match task")
    issue_id = _text(value.get("issue_id"), "runner_issue.issue_id")
    code = _text(value.get("code"), "runner_issue.code")
    if not ISSUE_CODE.fullmatch(code):
        raise ContractError("runner_issue.code must be a namespaced identifier")
    if value.get("status") not in {"open", "resolved"}:
        raise ContractError("runner_issue.status must be open or resolved")
    if value.get("severity") not in {"blocker", "warning"}:
        raise ContractError("runner_issue.severity must be blocker or warning")
    if value.get("stage") not in {f"J{index}" for index in range(1, 12)}:
        raise ContractError("runner_issue.stage must be between J1 and J11")
    subject = _object(value.get("subject"), "runner_issue.subject")
    if subject.get("task_id") != task_id or subject.get("issue_id") != issue_id:
        raise ContractError("runner_issue.subject must bind task_id and issue_id")
    _text(subject.get("revision_id"), "runner_issue.subject.revision_id")
    _text(value.get("resume_token"), "runner_issue.resume_token")
    if (
        "external_action_authorized" in value
        and value.get("external_action_authorized") is not False
    ):
        raise ContractError("runner_issue cannot authorize external action")
    public_fields = {"answer_tool", "answer_schema", "answer_example"}
    exposes_public_contract = bool(public_fields & set(value))
    if code == "configuration.required" and exposes_public_contract:
        if not public_fields <= set(value):
            raise ContractError("configuration.required public answer contract is incomplete")
        if value.get("answer_tool") != "paperspine5_runner_answer_issue":
            raise ContractError(
                "configuration.required must expose paperspine5_runner_answer_issue"
            )
        # A persisted J3 issue can legitimately predate a compatible additive
        # field in the public configuration contract (for example the
        # research_mode policy).  Same-task recovery must remain readable after
        # a service restart; reject only a non-compatible old contract.  The
        # canonical public schema/example are projected for the current reader
        # and are never treated as a new user decision.
        if value.get("answer_schema") != PUBLIC_RUN_CONFIGURATION_SCHEMA:
            legacy_example = value.get("answer_example")
            if not isinstance(legacy_example, dict) or "research_mode" in legacy_example:
                raise ContractError(
                    "configuration.required answer_schema differs from the public J3 contract"
                )
            try:
                normalized_legacy = validate_run_configuration(legacy_example)
            except ContractError as exc:
                raise ContractError(
                    "configuration.required answer_schema differs from the public J3 contract"
                ) from exc
            current_legacy_example = deepcopy(GUIDED_RUN_CONFIGURATION_EXAMPLE)
            current_legacy_example.pop("research_mode", None)
            if normalized_legacy != validate_run_configuration(current_legacy_example):
                raise ContractError(
                    "configuration.required answer_schema differs from the public J3 contract"
                )
            value["answer_schema"] = deepcopy(PUBLIC_RUN_CONFIGURATION_SCHEMA)
            value["answer_example"] = deepcopy(GUIDED_RUN_CONFIGURATION_EXAMPLE)
        elif value.get("answer_example") != GUIDED_RUN_CONFIGURATION_EXAMPLE:
            raise ContractError(
                "configuration.required answer_example differs from the public guided example"
            )
        validate_run_configuration(value["answer_example"])
    elif code == "academic.input.required" and exposes_public_contract:
        if not public_fields <= set(value):
            raise ContractError("academic.input.required public answer contract is incomplete")
        if value.get("answer_tool") != "paperspine5_runner_answer_academic_stage":
            raise ContractError(
                "academic.input.required must expose the dedicated academic answer tool"
            )
        answer_schema = value.get("answer_schema")
        answer_example = value.get("answer_example")
        if not isinstance(answer_schema, dict) or not isinstance(answer_example, dict):
            raise ContractError("academic.input.required public answer contract is invalid")
        expected_revision = int(subject["revision_id"])
        stage = issue_id.rsplit(":", 1)[-1]
        expected_bindings = {
            "task_id": task_id,
            "issue_id": issue_id,
            "expected_revision": expected_revision,
            "stage": stage,
        }
        for field, expected in expected_bindings.items():
            if (
                answer_schema.get("properties", {}).get(field, {}).get("const")
                != expected
                or answer_example.get(field) != expected
            ):
                raise ContractError(
                    f"academic.input.required public contract does not bind {field}"
                )
        if answer_example.get("external_action_authorized") is not False:
            raise ContractError("academic answer example cannot authorize external action")
    elif code == "contribution.confirmation.required":
        if not public_fields <= set(value):
            raise ContractError(
                "contribution.confirmation.required public answer contract is incomplete"
            )
        if value.get("answer_tool") != "paperspine5_product_web_confirm_contribution":
            raise ContractError(
                "contribution confirmation must be owned by authenticated Product Web"
            )
        preparation = value.get("candidate_preparation")
        answer_schema = value.get("answer_schema")
        answer_example = value.get("answer_example")
        if (
            not isinstance(preparation, dict)
            or preparation.get("contract")
            != "paperspine5.contribution-candidate-preparation"
            or not isinstance(preparation.get("preparation_sha256"), str)
            or not isinstance(answer_schema, dict)
            or not isinstance(answer_example, dict)
        ):
            raise ContractError("contribution confirmation public context is invalid")
        expected_bindings = {
            "task_id": task_id,
            "issue_id": issue_id,
            "expected_revision": int(subject["revision_id"]),
            "preparation_sha256": preparation["preparation_sha256"],
        }
        for field, expected in expected_bindings.items():
            if (
                answer_schema.get("properties", {}).get(field, {}).get("const")
                != expected
                or answer_example.get(field) != expected
            ):
                raise ContractError(
                    f"contribution confirmation public contract does not bind {field}"
                )
        if answer_example.get("external_action_authorized") is not False:
            raise ContractError("contribution confirmation cannot authorize external action")
    return value


def validate_interaction_projection(raw: Any) -> dict[str, Any]:
    value = _object(raw, "runner_interaction")
    required = {
        "mode",
        "requested_scope",
        "grant_status",
        "grant_id",
        "grant_sha256",
        "decision_classes",
        "decision_receipts",
        "external_action_authorized",
    }
    if set(value) != required:
        raise ContractError("runner interaction projection fields are invalid")
    if value.get("mode") not in INTERACTION_MODES:
        raise ContractError("runner interaction mode is invalid")
    if value.get("requested_scope") not in REQUESTED_SCOPES:
        raise ContractError("runner interaction requested_scope is invalid")
    if value.get("grant_status") not in {
        "not_applicable",
        "valid",
        "expired",
        "stale",
        "invalid",
    }:
        raise ContractError("runner interaction grant_status is invalid")
    decision_classes = value.get("decision_classes")
    receipts = value.get("decision_receipts")
    if (
        not isinstance(decision_classes, list)
        or len(decision_classes) != len(set(decision_classes))
        or any(item not in LOCAL_DELEGATION_DECISION_CLASSES for item in decision_classes)
    ):
        raise ContractError("runner interaction decision_classes are invalid")
    if (
        not isinstance(receipts, list)
        or len(receipts) != len(set(receipts))
        or any(
            not isinstance(item, str) or not item.startswith("delegated-decision.")
            for item in receipts
        )
    ):
        raise ContractError("runner interaction decision_receipts are invalid")
    if value.get("mode") == "guided":
        if any(
            (
                value.get("grant_id") is not None,
                value.get("grant_sha256") is not None,
                bool(decision_classes),
                bool(receipts),
                value.get("grant_status") != "not_applicable",
            )
        ):
            raise ContractError("guided interaction cannot carry delegated authority")
    else:
        _text(value.get("grant_id"), "runner_interaction.grant_id")
        _digest(value.get("grant_sha256"), "runner_interaction.grant_sha256")
        if value.get("grant_status") != "valid" or not decision_classes:
            raise ContractError("delegated interaction requires one valid typed grant")
    if value.get("external_action_authorized") is not False:
        raise ContractError("runner interaction cannot authorize external actions")
    return value


def validate_runner_state(raw: dict[str, Any], *, task_id: str, build_id: str) -> dict[str, Any]:
    value = _object(raw, "runner_state")
    if value.get("contract") != "paperspine5.runner-state":
        raise ContractError("runner_state.contract must be paperspine5.runner-state")
    if value.get("schema_version") != PRODUCT_SCHEMA_VERSION:
        raise ContractError(f"runner_state.schema_version must be {PRODUCT_SCHEMA_VERSION}")
    if (
        value.get("runner_version") not in READABLE_RUNNER_VERSIONS
        or value.get("product_build_id") != build_id
    ):
        raise ContractError("runner_state version/build binding does not match this runner")
    if value.get("stage") not in RUNNER_STAGES:
        raise ContractError("runner_state.stage is unsupported")
    issues = value.get("issues", [])
    if not isinstance(issues, list):
        raise ContractError("runner_state.issues must be an array")
    value["issues"] = [validate_runner_issue(item, task_id=task_id) for item in issues]
    value["interaction"] = validate_interaction_projection(value.get("interaction"))
    for field in (
        "academic_inputs",
        "academic_artifacts",
        "academic_base_artifacts",
        "figure_quality",
    ):
        if field in value and value[field] is not None and not isinstance(value[field], dict):
            raise ContractError(f"runner_state.{field} must be an object or null")
    successor = value.get("successor_migration")
    if successor is not None:
        required = {
            "contract",
            "schema_version",
            "migration_id",
            "source_build_id",
            "target_build_id",
            "authority_sha256",
            "source_identity_sha256",
            "external_action_authorized",
        }
        if (
            not isinstance(successor, dict)
            or set(successor) != required
            or successor.get("contract") != "paperspine5.runner-successor-link"
            or successor.get("schema_version") != "1.0"
            or successor.get("target_build_id") != build_id
            or successor.get("source_build_id") == build_id
            or successor.get("external_action_authorized") is not False
        ):
            raise ContractError("runner_state.successor_migration binding is invalid")
        for field in ("migration_id", "source_build_id", "target_build_id"):
            _text(successor.get(field), f"runner_state.successor_migration.{field}")
        _digest(
            successor.get("authority_sha256"),
            "runner_state.successor_migration.authority_sha256",
        )
        _digest(
            successor.get("source_identity_sha256"),
            "runner_state.successor_migration.source_identity_sha256",
        )
    return value
