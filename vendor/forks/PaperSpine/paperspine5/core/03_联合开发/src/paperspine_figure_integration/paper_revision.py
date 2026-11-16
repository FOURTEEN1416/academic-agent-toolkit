"""A user's explicit modification request, not a publication review verdict."""

from copy import deepcopy
import hashlib
from pathlib import Path
from typing import Any

from .contracts import ContractError


REVISION_STAGES = {
    "manuscript": "awaiting_canonical",
    "figures": "awaiting_figure_intent",
    "figure_mapping": "awaiting_claim_graph",
}


def validate_request(feedback: Any, scope: Any) -> tuple[str, str]:
    if not isinstance(feedback, str) or not feedback.strip() or len(feedback) > 8000:
        raise ContractError("revision feedback must contain 1..8000 characters")
    if not isinstance(scope, str) or scope not in REVISION_STAGES:
        raise ContractError("revision scope must be manuscript, figures or figure_mapping")
    return feedback.strip(), scope


def user_revision_projection(task: dict[str, Any]) -> dict[str, Any] | None:
    value = task.get("state", {}).get("user_revision_request")
    if not isinstance(value, dict):
        return None
    return {key: deepcopy(value[key]) for key in (
        "origin", "feedback", "scope", "requested_revision", "previous_completed_revision"
    )}


def retained_pointer(task: dict[str, Any], group: str, artifact_id: str) -> bool:
    """Only the exact user-selected previous delivery, never an arbitrary PASS."""
    state = task.get("state", {})
    request = state.get("user_revision_request", {})
    if request.get("origin") != "user_feedback" or request.get("scope") not in {"manuscript", "figures"}:
        return False
    previous = request.get("previous_delivery", {})
    current = state.get("runner", {}).get(group, {}).get(artifact_id)
    return (previous.get("active_run_id") == task.get("active_run_id")
            and isinstance(previous.get("revision"), int) and previous["revision"] < task["revision"]
            and isinstance(current, dict) and current == previous.get(group, {}).get(artifact_id))


def validate_revised_canonical(runner: Any, task: dict[str, Any], payload: dict[str, Any],
                               base: dict[str, Any]) -> None:
    """Keep delivered bytes; this is persistence validation, not academic review."""

    def binary_sha256(value: dict[str, Any]) -> Any:
        if value.get("contract") == "paperspine5.local-file-byte-evidence":
            return value.get("source_bytes_sha256")
        # Legacy canonical base manifests stored the actual file digest as
        # ``content_sha256`` while their receipt ``sha256`` was the canonical
        # JSON-object hash.  Revision preservation must compare bytes to the
        # former; otherwise every legitimate figure-only revision is rejected
        # as if the last delivered manuscript had been overwritten.
        if isinstance(value.get("content_sha256"), str):
            return value.get("content_sha256")
        return value.get("sha256")

    request = task.get("state", {}).get("user_revision_request")
    if not isinstance(request, dict):
        return
    previous = request["previous_delivery"]
    old_inputs = runner._read_academic_inputs(task, previous["academic_inputs"])
    old = old_inputs["stage_inputs"]["awaiting_canonical"]
    old_base = runner._read_academic_base_artifacts(task, previous["academic_base_artifacts"])
    root = Path(task["workspace_root"]).resolve()
    changed = []
    for role in ("source", "pdf", "word"):
        old_id = old["manuscript_revision"]["artifacts"][role]["artifact_id"]
        new_id = payload.get("manuscript_revision", {}).get("artifacts", {}).get(role, {}).get("artifact_id")
        prior = old_base[old_id]
        current = base.get(new_id, {})
        # Some callers keep the byte-evidence path on the supplied base
        # manifest, while others repeat it on the canonical artifact binding.
        # Accept both equivalent representations when checking a new-path
        # revision; the subsequent publication validator still requires the
        # resolved path and byte hash.
        if not current.get("path"):
            bound = payload.get("manuscript_revision", {}).get("artifacts", {}).get(role, {})
            if isinstance(bound, dict):
                current = {**current, **bound}
        prior_path = (root / prior["path"]).resolve()
        prior_sha256 = binary_sha256(prior)
        if (not isinstance(prior_sha256, str) or not prior_path.is_relative_to(root)
            or not prior_path.is_file()
            or hashlib.sha256(prior_path.read_bytes()).hexdigest() != prior_sha256):
            observed = hashlib.sha256(prior_path.read_bytes()).hexdigest() if prior_path.is_file() else "missing"
            raise ContractError(f"last delivered {role} bytes changed; preserve the original paper (path={prior_path.as_posix()}, expected={prior_sha256}, observed={observed})")
        if not current.get("path") or (root / current["path"]).resolve() == (root / prior["path"]).resolve():
            raise ContractError(f"user revision {role} must use a new path; keep the last delivered file (prior={prior.get('path')}, current={current.get('path')})")
        if binary_sha256(current) != prior_sha256:
            changed.append(role)
    if not changed:
        raise ContractError("user revision canonical bytes unchanged; provide the actual revised paper")
    old_pages = set()
    for surface in old["canonical_bundle"]["surface_receipts"]:
        for page in surface["pages"]:
            # Legacy surface receipts recorded page hashes but no local page
            # paths.  Preserve those receipts as historical evidence; a new
            # J8 payload still supplies path-bound page renders below.
            if not page.get("path"):
                continue
            path = (root / page["path"]).resolve()
            if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != page["sha256"]:
                raise ContractError("last delivered page bytes changed; preserve the original render")
            old_pages.add(path)
    for surface in payload.get("canonical_bundle", {}).get("surface_receipts", []):
        for page in surface.get("pages", []):
            if (root / page["path"]).resolve() in old_pages:
                raise ContractError("user revision pages must use new paths; keep the last delivered render")


def apply_revision_request(runner: Any, task: dict[str, Any], command: dict[str, Any],
                           prepared: dict[str, Any]) -> dict[str, Any]:
    from .academic_stage_orchestrator import ACTIVE_STAGES, INVALIDATE_ALL

    feedback, scope = validate_request(command["payload"].get("feedback"), command["payload"].get("scope"))
    previous = runner._runner_state(task)
    existing_request = task.get("state", {}).get("user_revision_request")
    recovery_scope = (
        scope == "figures"
        and task.get("status") != "completed"
        and previous.get("stage") in {"awaiting_canonical", "awaiting_review", "awaiting_package"}
        and isinstance(existing_request, dict)
        and existing_request.get("origin") == "user_feedback"
        and isinstance(existing_request.get("previous_completed_revision"), int)
        and isinstance(existing_request.get("previous_delivery"), dict)
    )
    if recovery_scope:
        return _apply_downstream_figure_recovery(
            runner, task, command, prepared, feedback=feedback
        )
    readiness = runner.kernel.get_readiness(task["task_id"])
    if (task["status"] != "completed" or previous["stage"] != "target_package_ready"
        or readiness.get("status") != "fresh" or readiness.get("delivery_ready") is not True):
        raise ContractError("revision request requires the current completed local package")
    head = runner._accepted_academic_view(task, "publication.manuscript-head")
    package = runner._accepted_academic_view(task, "publication.target-package")
    if head is None or package is None or head["payload"].get("status") != "PASS":
        raise ContractError("revision request requires exact accepted head and package pointers")
    revision = command["expected_revision"] + 1
    stage = REVISION_STAGES[scope]
    promoted = []
    reused_mappings = []
    if scope in {"manuscript", "figures"}:
        from .figure_final_mapping import completed_mappings_for_revision, promote_final_mappings
        # Reuse only currently validated frozen figure bytes; this does not
        # select a new winner or manufacture a new independent review.
        reused_mappings = completed_mappings_for_revision(runner, task)
        if scope == "manuscript":
            promoted = promote_final_mappings(runner, task, reused_mappings,
                revision=revision, command_id=command["command_id"])
    inventory_receipt = prepared["inventory_receipt"]
    inventory = runner._read_inventory_receipt(task, inventory_receipt, revision)
    if inventory["snapshot_sha256"] != previous["material_inventory"]["snapshot_sha256"]:
        raise ContractError("materials changed; a user revision cannot relabel the prior evidence")
    contract_receipt = prepared["run_contract_receipt"]
    contract = runner._read_run_contract_receipt(task, contract_receipt, revision, inventory=inventory)
    cumulative = deepcopy(runner._read_academic_inputs(task, previous["academic_inputs"]))
    base = runner._read_academic_base_artifacts(task, previous["academic_base_artifacts"])
    remove = {"bundle_archive"}
    canonical = cumulative.get("stage_inputs", {}).get("awaiting_canonical", {})
    for artifact in canonical.get("manuscript_revision", {}).get("artifacts", {}).values():
        if isinstance(artifact, dict):
            remove.add(artifact.get("artifact_id"))
    for surface in canonical.get("canonical_bundle", {}).get("surface_receipts", []):
        for page in surface.get("pages", []):
            if isinstance(page, dict):
                remove.add(page.get("artifact_id"))
    if scope != "manuscript":
        remove.update(key for key, value in base.items()
                      if value.get("contract") == "paperspine5.figure-candidate-asset")
    if scope == "figure_mapping":
        plans = [value for value in base.values()
                 if value.get("contract") == "paperspine5.figure-reference-plan"]
        remove.update(key for key, value in base.items()
                      if value.get("contract") == "paperspine5.figure-reference-plan")
        remove.add("figure-master-authority")
        remove.update(plan.get("mapping_authority", {}).get("attestation_input_id") for plan in plans)
    remove.discard(None)
    kept_base = {key: deepcopy(pointer) for key, pointer in previous["academic_base_artifacts"].items()
                 if key not in remove}
    cumulative["base_snapshot"] = {key: value for key, value in cumulative["base_snapshot"].items()
                                   if key not in remove}
    cumulative["stage_inputs"] = {key: value for key, value in cumulative["stage_inputs"].items()
                                  if ACTIVE_STAGES.index(key) < ACTIVE_STAGES.index(stage)}
    # User preferences are never converted into an independent review/objection.
    cumulative.pop("revision_context", None)
    input_receipt = runner._publish_artifact(
        task, value={"contract": "paperspine5.academic-cumulative-inputs", "schema_version": "1.0",
                     "task_id": task["task_id"], "revision_id": str(revision), "stage": stage,
                     "inputs": cumulative, "external_action_authorized": False},
        revision=revision, command_id=command["command_id"], artifact_id="runner.academic-inputs",
        artifact_type="runner.academic-inputs", input_hashes={
            "materials.source-ledger": inventory_receipt["sha256"],
            "runner.run-contract": contract_receipt["sha256"],
        }, metadata={"academic_stage": stage, "origin": "user_feedback"},
    )
    invalidated = set(INVALIDATE_ALL[3 if scope == "figure_mapping" else 4 if scope == "figures" else 5:])
    kept_artifacts = {key: deepcopy(pointer) for key, pointer in previous["academic_artifacts"].items()
                      if key not in invalidated}
    request = {
        "origin": "user_feedback", "feedback": feedback, "scope": scope,
        "requested_revision": revision, "previous_completed_revision": task["revision"],
        "retained_figure_history": [deepcopy(item["envelope"]) for item in reused_mappings],
        "previous_delivery": {
            "revision": task["revision"], "active_run_id": task["active_run_id"],
            "academic_artifacts": deepcopy(previous["academic_artifacts"]),
            "academic_base_artifacts": deepcopy(previous["academic_base_artifacts"]),
            "academic_inputs": deepcopy(previous["academic_inputs"]),
            "readiness_receipt": deepcopy(readiness["receipt"]),
        },
    }
    issue = runner._issue(
        task, revision=revision, issue_id=f"academic:{task['task_id']}:{revision}:{stage}",
        code="academic.input.required", stage=runner._academic_journey_stage(stage),
        details="User requested changes to the previous local paper: " + feedback,
        allowed_actions=["runner.issue.answer"], nonce=stage,
        public_context={"user_revision_request": user_revision_projection({"state": {"user_revision_request": request}})},
    )
    state = deepcopy(task["state"])
    state["user_revision_request"] = request
    state["runner"] = runner._state(
        stage=stage, issues=[issue], next_actions=["runner.issue.answer"],
        material_inventory=runner._pointer(inventory_receipt, inventory["snapshot_sha256"]),
        run_contract=runner._pointer(contract_receipt, inventory["snapshot_sha256"]),
        academic_inputs=runner._academic_pointer(input_receipt), academic_artifacts=kept_artifacts,
        academic_base_artifacts=kept_base,
        interaction=runner._interaction_projection(contract["configuration"], kept_artifacts),
    )
    return {"state": state, "status": "blocked",
            "artifacts": [inventory_receipt, contract_receipt, input_receipt, *promoted],
            "event_payload": {"runner_stage": stage, "origin": "user_feedback", "scope": scope,
                              "previous_completed_revision": task["revision"]},
            "result": {"runner_stage": stage, "revision_requested": True,
                       "previous_completed_revision": task["revision"], "external_action_authorized": False}}


def _apply_downstream_figure_recovery(
    runner: Any,
    task: dict[str, Any],
    command: dict[str, Any],
    prepared: dict[str, Any],
    *,
    feedback: str,
) -> dict[str, Any]:
    """Atomically reopen J7 for a blocked same-task downstream run."""
    from .academic_stage_orchestrator import ACTIVE_STAGES, INVALIDATE_ALL

    previous = runner._runner_state(task)
    revision = command["expected_revision"] + 1
    inventory_receipt = prepared["inventory_receipt"]
    inventory = runner._read_inventory_receipt(task, inventory_receipt, revision)
    if inventory["snapshot_sha256"] != previous["material_inventory"]["snapshot_sha256"]:
        raise ContractError("materials changed; downstream figure recovery requires the original snapshot")
    contract_receipt = prepared["run_contract_receipt"]
    contract = runner._read_run_contract_receipt(task, contract_receipt, revision, inventory=inventory)
    cumulative = deepcopy(runner._read_academic_inputs(task, previous["academic_inputs"]))
    base = runner._read_academic_base_artifacts(task, previous["academic_base_artifacts"])
    j7_index = ACTIVE_STAGES.index("awaiting_figure_intent")
    cumulative["stage_inputs"] = {
        key: value for key, value in cumulative.get("stage_inputs", {}).items()
        if key in ACTIVE_STAGES and ACTIVE_STAGES.index(key) < j7_index
    }
    remove = {
        "bundle_archive", "manuscript_source", "manuscript_pdf", "manuscript_word",
        "canonical_manuscript", "final_render", "target_bundle", "readiness_verdict",
        "figure-master-authority",
    }
    for artifact_id, value in base.items():
        if (artifact_id.startswith("figure-candidate")
                or artifact_id.startswith("reference-plan:")
                or value.get("contract") in {"paperspine5.figure-candidate-asset", "paperspine5.figure-reference-plan"}):
            remove.add(artifact_id)
    kept_base = {key: deepcopy(value) for key, value in base.items() if key not in remove}
    cumulative["base_snapshot"] = {
        key: value for key, value in cumulative.get("base_snapshot", {}).items() if key not in remove
    }
    input_receipt = runner._publish_artifact(
        task,
        value={"contract": "paperspine5.academic-cumulative-inputs", "schema_version": "1.0",
               "task_id": task["task_id"], "revision_id": str(revision),
               "stage": "awaiting_figure_intent", "inputs": cumulative,
               "external_action_authorized": False},
        revision=revision, command_id=command["command_id"], artifact_id="runner.academic-inputs",
        artifact_type="runner.academic-inputs",
        input_hashes={"materials.source-ledger": inventory_receipt["sha256"],
                      "runner.run-contract": contract_receipt["sha256"]},
        metadata={"academic_stage": "awaiting_figure_intent", "origin": "downstream_recovery"},
    )
    invalidated = set(INVALIDATE_ALL[4:]) | {"surface_pdf", "surface_word", "publication.manuscript-head"}
    kept_artifacts = {key: deepcopy(value) for key, value in previous.get("academic_artifacts", {}).items()
                      if key not in invalidated}
    issue = runner._issue(
        task, revision=revision,
        issue_id=f"academic:{task['task_id']}:{revision}:awaiting_figure_intent",
        code="academic.input.required", stage="J7",
        details="Same-task downstream recovery reopened J7; provide a real Figure intent and explicit user choice.",
        allowed_actions=["runner.issue.answer"], nonce="downstream-figure-recovery",
    )
    request = deepcopy(task.get("state", {}).get("user_revision_request", {}))
    request.update({"feedback": feedback, "scope": "figures", "requested_revision": revision,
                    "reopened_from_revision": task["revision"], "recovery_origin": "downstream_same_task"})
    state = deepcopy(task["state"])
    state["user_revision_request"] = request
    state["runner"] = runner._state(
        stage="awaiting_figure_intent", issues=[issue],
        material_inventory=runner._pointer(inventory_receipt, inventory["snapshot_sha256"]),
        run_contract=runner._pointer(contract_receipt, inventory["snapshot_sha256"]),
        next_actions=["runner.issue.answer"], academic_inputs=runner._academic_pointer(input_receipt),
        academic_artifacts=kept_artifacts, academic_base_artifacts=kept_base,
        interaction=runner._interaction_projection(contract["configuration"], kept_artifacts),
    )
    return {"state": state, "status": "blocked", "artifacts": [inventory_receipt, contract_receipt, input_receipt],
            "event_payload": {"runner_stage": "awaiting_figure_intent", "origin": "downstream_same_task",
                              "scope": "figures", "reopened_from_revision": task["revision"]},
            "result": {"runner_stage": "awaiting_figure_intent", "revision_requested": True,
                       "reopened_from_revision": task["revision"], "external_action_authorized": False}}
