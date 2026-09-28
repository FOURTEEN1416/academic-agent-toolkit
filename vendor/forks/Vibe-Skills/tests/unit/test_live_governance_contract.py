from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SRC = REPO_ROOT / "packages" / "contracts" / "src"
if str(CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_SRC))

import vgo_contracts  # noqa: E402
from vgo_contracts.live_governance_contract import (  # noqa: E402
    LiveGovernanceContract,
    build_live_document_census,
    load_live_governance_contract,
    validate_live_document_changes,
    validate_live_document_registry_transition,
    validate_live_document_workspace,
    validate_run_artifact_workspace,
)


def _write(path: Path, text: str = "# Contract\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _contract_payload(
    *,
    documents: list[dict[str, str]] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "max_live_documents": 30,
        "governed_roots": [".", "docs", "references"],
        "excluded_paths": ["THIRD_PARTY_LICENSES.md"],
        "excluded_prefixes": ["references/provenance/"],
        "documents": documents
        if documents is not None
        else [
            {
                "id": "project-entry",
                "path": "README.md",
                "owner": "project-entry",
                "lifecycle": "live",
            },
            {
                "id": "runtime-contract",
                "path": "docs/runtime-contract.md",
                "owner": "runtime-contracts",
                "lifecycle": "live",
            },
            {
                "id": "proof-policy",
                "path": "references/proof-policy.md",
                "owner": "verification",
                "lifecycle": "live",
            },
        ],
        "stable_entry_links": [
            {
                "source": "README.md",
                "targets": [
                    "docs/runtime-contract.md",
                    "references/proof-policy.md",
                ],
            }
        ],
        "proof_retention": {
            "pull_request_days": 30,
            "main_and_scheduled_days": 90,
            "formal_release": "github_release",
        },
        "artifact_sink": {
            "schema_version": 1,
            "root": ".vibeskills/runs",
            "required_artifacts": ["requirement", "plan", "status", "proof"],
            "required_metadata": ["commit_sha", "execution_environment"],
            "artifact_paths": {
                "requirement": "requirement.json",
                "plan": "plan.json",
                "status": "status.json",
                "proof": "proof.json",
            },
            "primary_document_paths": {
                "requirement": "requirement.md",
                "plan": "plan.md",
            },
            "manifest_path": "manifest.json",
            "legacy_compatibility_path": "legacy-compatibility.json",
            "session_receipts": {
                "root": "outputs/runtime/vibe-sessions",
                "owner": "runtime",
                "retention": "workspace_local",
                "copy_to_artifact_sink": True,
            },
            "legacy_projection_root": "vibe/runs",
            "legacy_documentation_roots": ["docs/requirements", "docs/plans"],
            "legacy_removal_release": "4.1.0",
            "legacy_write_mode": "dual_write",
        },
    }


def _run_manifest_payload() -> dict:
    return {
        "schema_version": 1,
        "run_id": "run-001",
        "artifact_root": ".vibeskills/runs/run-001",
        "artifacts": {
            "requirement": "requirement.json",
            "plan": "plan.json",
            "status": "status.json",
            "proof": "proof.json",
        },
        "commit_sha": "0123456789abcdef",
        "execution_environment": {
            "os": "windows",
            "python": "3.10",
        },
        "legacy_compatibility": {
            "mode": "dual_write",
            "removal_release": "4.1.0",
            "documentation_roots": ["docs/requirements", "docs/plans"],
            "writes": [],
            "write_records": [],
            "observable": True,
        },
    }


def test_minimal_live_contract_workspace_emits_a_complete_run_artifact_manifest(tmp_path: Path) -> None:
    contract_payload = _contract_payload()
    _write(
        tmp_path / "config" / "live-document-contract.json",
        json.dumps(contract_payload, indent=2) + "\n",
    )
    for document in contract_payload["documents"]:
        text = "# Contract\n"
        if document["path"] == "README.md":
            text += "\n- [Runtime](docs/runtime-contract.md)\n"
            text += "- [Proof](references/proof-policy.md)\n"
        _write(tmp_path / document["path"], text)

    contract = load_live_governance_contract(tmp_path / "docs")
    validated_paths = validate_live_document_workspace(contract, tmp_path)
    manifest = contract.validate_run_artifact_manifest(_run_manifest_payload())
    artifact_paths = manifest.resolve_artifact_paths(tmp_path)
    for artifact_kind, artifact_path in artifact_paths.items():
        _write(
            artifact_path,
            json.dumps({"artifact_kind": artifact_kind}) + "\n",
        )
    validated_artifact_paths = validate_run_artifact_workspace(
        manifest,
        tmp_path,
    )

    assert validated_paths == [
        tmp_path / "README.md",
        tmp_path / "docs" / "runtime-contract.md",
        tmp_path / "references" / "proof-policy.md",
    ]
    assert manifest.artifacts["proof"] == "proof.json"
    assert manifest.commit_sha == "0123456789abcdef"
    assert manifest.execution_environment == {"os": "windows", "python": "3.10"}
    assert validated_artifact_paths == artifact_paths
    assert all(path.is_file() for path in validated_artifact_paths.values())
    assert artifact_paths["proof"] == (
        tmp_path / ".vibeskills" / "runs" / "run-001" / "proof.json"
    )
    assert not (tmp_path / "docs" / "requirements").exists()
    assert not (tmp_path / "docs" / "plans").exists()


def test_live_document_changes_reject_new_unregistered_markdown() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())

    with pytest.raises(ValueError, match="not registered"):
        validate_live_document_changes(contract, ["docs/new-live-guide.md"])


def test_live_document_changes_allow_registered_and_narrowly_excluded_markdown() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())

    assert validate_live_document_changes(
        contract,
        [
            "README.md",
            "THIRD_PARTY_LICENSES.md",
            "references/provenance/source-record.md",
            "bundled/skills/example/SKILL.md",
        ],
    ) == ["README.md"]


def test_live_document_census_classifies_the_complete_governed_surface() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())

    census = build_live_document_census(
        contract,
        [
            "README.md",
            "docs/runtime-contract.md",
            "references/proof-policy.md",
            "THIRD_PARTY_LICENSES.md",
            "references/provenance/source-record.md",
            "docs/archive/retired-plan.md",
            "docs/New Guide.MD",
            "bundled/skills/example/SKILL.md",
            "scripts/README.md",
        ],
    )

    assert census.governed_markdown_count == 7
    assert census.registered_count == 3
    assert census.excluded_count == 2
    assert census.unregistered_count == 2
    assert [entry.path for entry in census.documents] == sorted(
        (entry.path for entry in census.documents),
        key=lambda path: (path.casefold(), path),
    )
    entries = {entry.path: entry for entry in census.documents}
    assert entries["README.md"].registry_status == "registered"
    assert entries["README.md"].document_id == "project-entry"
    assert entries["THIRD_PARTY_LICENSES.md"].registry_status == "excluded"
    assert entries["THIRD_PARTY_LICENSES.md"].exclusion_rule == (
        "path:THIRD_PARTY_LICENSES.md"
    )
    assert entries["references/provenance/source-record.md"].exclusion_rule == (
        "prefix:references/provenance/"
    )
    assert entries["docs/archive/retired-plan.md"].registry_status == (
        "unregistered"
    )
    assert entries["docs/archive/retired-plan.md"].migration_bucket == "docs/archive"
    assert "bundled/skills/example/SKILL.md" not in entries
    assert "scripts/README.md" not in entries


def test_live_document_census_rejects_case_ambiguous_tracked_paths() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())

    with pytest.raises(ValueError, match="case-ambiguous"):
        build_live_document_census(
            contract,
            ["docs/Guide.md", "docs/guide.md"],
        )


def test_live_document_registry_removal_requires_file_removal(tmp_path: Path) -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    retired_path = tmp_path / "docs" / "retired-live.md"
    _write(retired_path)
    previous_paths = [
        *(document.path for document in contract.documents),
        "docs/retired-live.md",
    ]

    with pytest.raises(ValueError, match="removed from the registry still exists"):
        validate_live_document_registry_transition(
            contract,
            previous_paths,
            tmp_path,
        )

    retired_path.unlink()
    assert validate_live_document_registry_transition(
        contract,
        previous_paths,
        tmp_path,
    ) == ["docs/retired-live.md"]


def test_live_document_workspace_rejects_missing_declared_stable_link(
    tmp_path: Path,
) -> None:
    payload = _contract_payload()
    for document in payload["documents"]:
        _write(tmp_path / document["path"])
    contract = LiveGovernanceContract.model_validate(payload)

    with pytest.raises(ValueError, match="stable entry link is missing"):
        validate_live_document_workspace(contract, tmp_path)


def test_live_document_workspace_treats_whitespace_links_as_missing(
    tmp_path: Path,
) -> None:
    payload = _contract_payload()
    for document in payload["documents"]:
        text = "# Contract\n"
        if document["path"] == "README.md":
            text += "\n[Empty markdown link]( )\n<a href=\" \">Empty HTML link</a>\n"
        _write(tmp_path / document["path"], text)
    contract = LiveGovernanceContract.model_validate(payload)

    with pytest.raises(ValueError, match="stable entry link is missing"):
        validate_live_document_workspace(contract, tmp_path)


def test_live_governance_contract_rejects_broad_document_exclusions() -> None:
    payload = _contract_payload()
    payload["excluded_prefixes"].append("docs/archive/")

    with pytest.raises(ValueError, match="unsupported excluded prefix"):
        LiveGovernanceContract.model_validate(payload)


def test_live_governance_contract_requires_registered_stable_link_targets() -> None:
    payload = _contract_payload()
    payload["stable_entry_links"][0]["targets"].append("docs/unregistered.md")

    with pytest.raises(ValueError, match="stable entry target must be registered"):
        LiveGovernanceContract.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pull_request_days", 29),
        ("main_and_scheduled_days", 89),
        ("formal_release", "workflow_artifact"),
    ],
)
def test_live_governance_contract_enforces_proof_retention_classes(
    field: str,
    value: object,
) -> None:
    payload = _contract_payload()
    payload["proof_retention"][field] = value

    with pytest.raises(ValueError, match="proof retention"):
        LiveGovernanceContract.model_validate(payload)


def test_repo_ships_a_valid_live_governance_contract() -> None:
    contract = load_live_governance_contract(REPO_ROOT)

    validated_paths = validate_live_document_workspace(contract, REPO_ROOT)

    assert len(validated_paths) <= 30
    assert validated_paths
    assert all(path.suffix.casefold() == ".md" for path in validated_paths)
    assert contract.artifact_sink.required_artifacts == (
        "requirement",
        "plan",
        "status",
        "proof",
    )
    assert contract.artifact_sink.required_metadata == (
        "commit_sha",
        "execution_environment",
    )
    assert contract.artifact_sink.primary_document_path_map == {
        "requirement": "requirement.md",
        "plan": "plan.md",
    }


def test_runtime_config_manifest_packages_live_governance_contract() -> None:
    manifest = json.loads(
        (REPO_ROOT / "config" / "runtime-config-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    relpath = vgo_contracts.LIVE_GOVERNANCE_CONTRACT_RELPATH.as_posix()

    assert relpath in manifest["files"]
    assert relpath in manifest["role_groups"]["files"]["runtime_governance_files"]


def test_live_governance_contract_is_a_public_package_interface() -> None:
    assert (
        vgo_contracts.LIVE_GOVERNANCE_CONTRACT_RELPATH.as_posix()
        == "config/live-document-contract.json"
    )
    assert vgo_contracts.load_live_governance_contract is load_live_governance_contract
    assert (
        vgo_contracts.validate_live_document_workspace
        is validate_live_document_workspace
    )
    assert (
        vgo_contracts.validate_live_document_registry_transition
        is validate_live_document_registry_transition
    )
    assert (
        vgo_contracts.validate_run_artifact_workspace
        is validate_run_artifact_workspace
    )


@pytest.mark.parametrize(
    "document_path",
    [
        "/docs/runtime-contract.md",
        "C:/docs/runtime-contract.md",
        "C:docs/runtime-contract.md",
    ],
)
def test_live_governance_contract_rejects_non_relative_document_paths(
    document_path: str,
) -> None:
    payload = _contract_payload(
        documents=[
            {
                "id": "runtime-contract",
                "path": document_path,
                "owner": "runtime-contracts",
                "lifecycle": "live",
            }
        ]
    )

    with pytest.raises(ValueError, match="relative"):
        LiveGovernanceContract.model_validate(payload)


def test_live_governance_contract_requires_all_governed_document_roots() -> None:
    payload = _contract_payload()
    payload["governed_roots"] = ["docs", "references"]

    with pytest.raises(ValueError, match="missing required governed roots"):
        LiveGovernanceContract.model_validate(payload)


def test_live_governance_contract_rejects_more_than_thirty_registered_documents() -> None:
    documents = [
        {
            "id": f"document-{index}",
            "path": f"docs/document-{index}.md",
            "owner": "governance",
            "lifecycle": "live",
        }
        for index in range(31)
    ]

    with pytest.raises(ValueError, match="configured budget is 30"):
        LiveGovernanceContract.model_validate(_contract_payload(documents=documents))


def test_live_document_budget_counts_every_maintained_registry_entry() -> None:
    documents = [
        {
            "id": f"document-{index}",
            "path": f"docs/document-{index}.md",
            "owner": "governance",
            "lifecycle": "live",
        }
        for index in range(30)
    ]
    documents.append(
        {
            "id": "retained-decision",
            "path": "docs/adr/retained-decision.md",
            "owner": "governance",
            "lifecycle": "retained",
        }
    )

    with pytest.raises(ValueError, match="configured budget is 30"):
        LiveGovernanceContract.model_validate(_contract_payload(documents=documents))


@pytest.mark.parametrize("field", ["owner", "lifecycle"])
def test_live_governance_contract_requires_document_metadata(field: str) -> None:
    document = {
        "id": "runtime-contract",
        "path": "docs/runtime-contract.md",
        "owner": "runtime-contracts",
        "lifecycle": "live",
    }
    document.pop(field)

    with pytest.raises(ValueError, match=field):
        LiveGovernanceContract.model_validate(
            _contract_payload(documents=[document])
        )


def test_live_governance_contract_rejects_an_empty_registry() -> None:
    with pytest.raises(ValueError, match="at least one"):
        LiveGovernanceContract.model_validate(_contract_payload(documents=[]))


def test_run_artifact_manifest_requires_complete_artifact_set() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["artifacts"].pop("proof")

    with pytest.raises(ValueError, match="proof"):
        contract.validate_run_artifact_manifest(manifest_payload)


@pytest.mark.parametrize(
    "field",
    [
        "artifact_paths",
        "primary_document_paths",
        "manifest_path",
        "legacy_compatibility_path",
        "legacy_projection_root",
        "legacy_documentation_roots",
        "legacy_removal_release",
        "legacy_write_mode",
    ],
)
def test_artifact_sink_rejects_missing_cutover_fields(field: str) -> None:
    payload = _contract_payload()
    payload["artifact_sink"].pop(field)

    with pytest.raises(ValueError, match=field):
        LiveGovernanceContract.model_validate(payload)


def test_artifact_sink_requires_an_explicit_session_receipt_boundary() -> None:
    payload = _contract_payload()
    payload["artifact_sink"].pop("session_receipts")

    with pytest.raises(ValueError, match="session_receipts"):
        LiveGovernanceContract.model_validate(payload)


def test_session_receipt_contract_is_publicly_exported() -> None:
    assert vgo_contracts.SessionReceiptContract is not None
    assert vgo_contracts.SESSION_RECEIPT_OWNER == "runtime"
    assert vgo_contracts.SESSION_RECEIPT_RETENTION == "workspace_local"


def test_session_receipt_contract_resolves_the_declared_run_root(
    tmp_path: Path,
) -> None:
    payload = _contract_payload()
    payload["artifact_sink"]["session_receipts"]["root"] = (
        "runtime/session-receipts"
    )
    contract = LiveGovernanceContract.model_validate(payload)

    assert contract.artifact_sink.session_receipts.resolve_run_root(
        tmp_path,
        "run-001",
    ) == (tmp_path / "runtime" / "session-receipts" / "run-001").resolve()


@pytest.mark.parametrize(
    "artifact_root",
    [
        "docs/requirements",
        "docs/requirements/runs",
        "docs/plans/archive",
    ],
)
def test_artifact_sink_rejects_historical_documentation_roots(
    artifact_root: str,
) -> None:
    payload = _contract_payload()
    payload["artifact_sink"]["root"] = artifact_root

    with pytest.raises(ValueError, match="historical documentation roots"):
        LiveGovernanceContract.model_validate(payload)


def test_run_artifact_manifest_paths_must_match_the_contract() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["artifacts"]["proof"] = "other-proof.json"

    with pytest.raises(ValueError, match="must match"):
        contract.validate_run_artifact_manifest(manifest_payload)


def test_run_artifact_manifest_requires_explicit_legacy_compatibility() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload.pop("legacy_compatibility")

    with pytest.raises(ValueError, match="legacy_compatibility"):
        contract.validate_run_artifact_manifest(manifest_payload)


def test_disabled_legacy_compatibility_rejects_declared_writes() -> None:
    contract_payload = _contract_payload()
    contract_payload["artifact_sink"]["legacy_write_mode"] = "disabled"
    contract = LiveGovernanceContract.model_validate(contract_payload)
    manifest_payload = _run_manifest_payload()
    manifest_payload["legacy_compatibility"]["mode"] = "disabled"
    manifest_payload["legacy_compatibility"]["writes"] = [
        "docs/requirements/legacy.md"
    ]

    with pytest.raises(ValueError, match="disabled"):
        contract.validate_run_artifact_manifest(manifest_payload)


def test_legacy_compatibility_rejects_writes_outside_declared_roots() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["legacy_compatibility"]["writes"] = ["outputs/random.md"]

    with pytest.raises(ValueError, match="declared legacy compatibility roots"):
        contract.validate_run_artifact_manifest(manifest_payload)


def test_legacy_compatibility_requires_a_record_for_every_write() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["legacy_compatibility"]["writes"] = [
        "docs/requirements/legacy.md"
    ]
    manifest_payload["legacy_compatibility"].pop("write_records")

    with pytest.raises(ValueError, match="write_records"):
        contract.validate_run_artifact_manifest(manifest_payload)


def test_run_artifact_manifest_requires_distinct_artifact_paths() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["artifacts"]["proof"] = "status.json"

    with pytest.raises(ValueError, match="unique"):
        contract.validate_run_artifact_manifest(manifest_payload)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("commit_sha", "commit_sha"),
        ("execution_environment", "execution_environment"),
    ],
)
def test_run_artifact_manifest_requires_attribution_metadata(
    field: str,
    message: str,
) -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload.pop(field)

    with pytest.raises(ValueError, match=message):
        contract.validate_run_artifact_manifest(manifest_payload)


def test_run_artifact_manifest_must_use_the_declared_artifact_sink() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["artifact_root"] = "outputs/runtime/run-001"

    with pytest.raises(ValueError, match="artifact sink root"):
        contract.validate_run_artifact_manifest(manifest_payload)


@pytest.mark.parametrize(
    "artifact_path",
    ["/tmp/proof.json", "../proof.json", "C:proof.json", "."],
)
def test_run_artifact_manifest_rejects_artifacts_outside_the_run_root(
    artifact_path: str,
) -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["artifacts"]["proof"] = artifact_path

    with pytest.raises(ValueError, match="relative"):
        contract.validate_run_artifact_manifest(manifest_payload)
