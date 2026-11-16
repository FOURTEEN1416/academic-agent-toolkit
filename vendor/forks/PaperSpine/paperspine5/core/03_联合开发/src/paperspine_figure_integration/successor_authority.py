"""Fail-closed installed-suite authority for same-task runner succession.

The independent Plugin and Standalone Skill updaters remain the authority for
which local build succeeded which predecessor.  This module only consumes their
immutable history, receipts, backup trees, projections/pointers, and active suite
identity.  It never installs, rolls back, or mutates an update control root.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import marshal
import re
import sys
import types
from pathlib import Path
from typing import Any, Callable

from .contracts import ContractError


SuiteVerifier = Callable[[str | Path], dict[str, Any]]
DEVELOPMENT_BUILD_ID = "local-dev-unverified"
RUNTIME_PYC_NAME = re.compile(
    r"^(?P<stem>.+)\.(?P<tag>[A-Za-z0-9_]+-\d+)(?:\.opt-(?P<opt>\d+))?\.pyc$"
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _tree_identity(root: Path) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise ContractError("successor suite evidence requires a plain directory")
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if path.is_symlink():
            raise ContractError("successor suite evidence contains a link")
        if not path.is_file():
            continue
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return {
        "file_count": len(files),
        "total_bytes": sum(int(item["size_bytes"]) for item in files),
        "tree_sha256": _sha256_bytes(
            (
                json.dumps(
                    files, ensure_ascii=False, sort_keys=True, indent=2
                )
                + "\n"
            ).encode("utf-8")
        ),
    }


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} must contain one JSON object")
    return value


def _verified_suite(
    root: Path,
    *,
    expected_build_id: str,
    expected_content_index_sha256: str | None,
    suite_verifier: SuiteVerifier,
) -> dict[str, Any]:
    try:
        value = suite_verifier(root)
    except Exception as exc:
        raise ContractError(f"installed successor suite verification failed: {exc}") from exc
    if (
        not isinstance(value, dict)
        or value.get("status") != "PASS"
        or value.get("build_id") != expected_build_id
        or value.get("external_action_authorized") is not False
    ):
        raise ContractError("installed successor suite identity is invalid")
    if (
        expected_content_index_sha256 is not None
        and value.get("content_index_sha256") != expected_content_index_sha256
    ):
        raise ContractError("installed successor suite content index drifted")
    manifest = value.get("manifest")
    api = manifest.get("api") if isinstance(manifest, dict) else None
    runner_api = api.get("product_runner") if isinstance(api, dict) else None
    if not isinstance(runner_api, str) or "/" not in runner_api:
        raise ContractError("installed successor suite runner API identity is missing")
    return {
        "root": str(root),
        "build_id": expected_build_id,
        "runner_version": runner_api.rsplit("/", 1)[-1],
        "manifest_sha256": value.get("manifest_sha256"),
        "content_index_sha256": value.get("content_index_sha256"),
        "file_count": value.get("file_count"),
    }


def _normalized_runtime_code(
    code: types.CodeType,
    *,
    source_relative: str,
    depth: int = 0,
) -> types.CodeType:
    if depth > 256:
        raise ContractError("runtime bytecode nesting exceeds the safe limit")
    constants = tuple(
        _normalized_runtime_code(
            value,
            source_relative=source_relative,
            depth=depth + 1,
        )
        if isinstance(value, types.CodeType)
        else value
        for value in code.co_consts
    )
    return code.replace(
        co_filename=f"<managed-source>/{source_relative}",
        co_consts=constants,
    )


def _verified_runtime_pyc(
    root: Path,
    path: Path,
    *,
    indexed_records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Bind one unindexed pyc to exact indexed source bytes and semantics."""

    relative = path.relative_to(root)
    match = RUNTIME_PYC_NAME.fullmatch(path.name)
    if (
        relative.parent.name != "__pycache__"
        or path.suffix != ".pyc"
        or match is None
        or match.group("tag") != str(sys.implementation.cache_tag)
    ):
        raise ContractError("runtime suite bytecode residue path is invalid")
    source_relative = (
        relative.parent.parent / f"{match.group('stem')}.py"
    ).as_posix()
    source_record = indexed_records.get(source_relative)
    if source_record is None:
        raise ContractError("runtime suite bytecode residue source is not indexed")
    source_path = (root / Path(source_relative)).resolve()
    try:
        payload = path.read_bytes()
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise ContractError("runtime suite bytecode residue is unreadable") from exc
    if len(payload) < 16 or payload[:4] != importlib.util.MAGIC_NUMBER:
        raise ContractError("runtime suite bytecode residue header is invalid")
    flags = int.from_bytes(payload[4:8], "little")
    if flags not in {0, 1, 3}:
        raise ContractError("runtime suite bytecode residue flags are invalid")
    if flags == 0:
        expected_header = (
            importlib.util.MAGIC_NUMBER
            + (0).to_bytes(4, "little")
            + (int(source_path.stat().st_mtime) & 0xFFFFFFFF).to_bytes(4, "little")
            + (len(source_bytes) & 0xFFFFFFFF).to_bytes(4, "little")
        )
    else:
        expected_header = (
            importlib.util.MAGIC_NUMBER
            + flags.to_bytes(4, "little")
            + importlib.util.source_hash(source_bytes)
        )
    if payload[:16] != expected_header:
        raise ContractError("runtime suite bytecode residue header is not source-bound")
    try:
        stream = io.BytesIO(payload[16:])
        actual_code = marshal.load(stream)
        if stream.read(1) or not isinstance(actual_code, types.CodeType):
            raise ValueError("pyc body is not one exact CodeType")
        optimize = int(match.group("opt") or 0)
        expected_code = compile(
            source_bytes,
            str(source_path),
            "exec",
            dont_inherit=True,
            optimize=optimize,
        )
        actual_normalized = _normalized_runtime_code(
            actual_code,
            source_relative=source_relative,
        )
        expected_normalized = _normalized_runtime_code(
            expected_code,
            source_relative=source_relative,
        )
    except (EOFError, TypeError, ValueError, RecursionError) as exc:
        raise ContractError("runtime suite bytecode residue payload is invalid") from exc
    if actual_normalized != expected_normalized:
        raise ContractError(
            "runtime suite bytecode residue compiled code differs from source"
        )
    return {
        "path": relative.as_posix(),
        "sha256": _sha256_file(path),
        "size_bytes": path.stat().st_size,
        "source_path": source_relative,
        "source_sha256": source_record["sha256"],
    }


def _verified_runtime_suite(
    root: Path,
    *,
    expected_build_id: str,
    expected_content_index_sha256: str,
) -> dict[str, Any]:
    """Verify exact manifest-indexed runtime bytes without future release policy.

    Historical managed Skill suites remain authoritative through their own
    committed manifest and content index.  A verifier shipped by a later build
    may require release markers that did not exist when the predecessor was
    published, so it must not be applied retroactively here.
    """

    manifest_path = root / "suite-manifest.json"
    manifest = _read_json(manifest_path, "active runtime suite manifest")
    if (
        manifest.get("contract") != "paperspine5.suite-manifest"
        or manifest.get("schema_version") != "1.0"
        or manifest.get("suite", {}).get("build_id") != expected_build_id
    ):
        raise ContractError("active runtime suite manifest identity is invalid")
    content = manifest.get("content")
    records = content.get("files") if isinstance(content, dict) else None
    if not isinstance(records, list):
        raise ContractError("active runtime suite content index is missing")
    rebuilt: list[dict[str, Any]] = []
    indexed: set[str] = set()
    indexed_records: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ContractError("active runtime suite content record is invalid")
        relative = str(record.get("path", ""))
        relative_path = Path(relative)
        if (
            not relative
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative in indexed
        ):
            raise ContractError("active runtime suite content path is unsafe")
        path = (root / relative_path).resolve()
        if not _is_relative_to(path, root) or not path.is_file() or path.is_symlink():
            raise ContractError("active runtime suite lost an indexed file")
        observed = {
            "path": relative_path.as_posix(),
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        if observed != record:
            raise ContractError("active runtime suite indexed bytes were tampered")
        rebuilt.append(observed)
        normalized_relative = relative_path.as_posix()
        indexed.add(normalized_relative)
        indexed_records[normalized_relative] = observed
    rebuilt.sort(key=lambda item: item["path"])
    index_sha = _sha256_bytes(
        (
            json.dumps(rebuilt, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        ).encode("utf-8")
    )
    if (
        index_sha != content.get("index_sha256")
        or index_sha != expected_content_index_sha256
    ):
        raise ContractError("active runtime suite content index hash is invalid")
    runtime_residue: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ContractError("active runtime suite contains a link")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "suite-manifest.json" or relative in indexed:
            continue
        try:
            runtime_residue.append(
                _verified_runtime_pyc(
                    root,
                    path,
                    indexed_records=indexed_records,
                )
            )
        except ContractError as exc:
            raise ContractError(
                "active runtime suite contains foreign unindexed residue"
            ) from exc
    api = manifest.get("api")
    runner_api = api.get("product_runner") if isinstance(api, dict) else None
    if not isinstance(runner_api, str) or "/" not in runner_api:
        raise ContractError("active runtime suite runner API identity is missing")
    return {
        "root": str(root),
        "build_id": expected_build_id,
        "runner_version": runner_api.rsplit("/", 1)[-1],
        "manifest_sha256": _sha256_file(manifest_path),
        "content_index_sha256": index_sha,
        "file_count": len(rebuilt),
        "runtime_residue_policy": "indexed-bytes-exact-source-bound-pyc",
        "runtime_residue": runtime_residue,
    }


def _verified_skill_projection(
    projection_root: Path,
    *,
    control_root: Path,
    expected_build_id: str,
    expected_content_index_sha256: str,
    expected_suite_root: Path | None = None,
) -> dict[str, Any]:
    """Verify one updater-owned Skill projection and its managed-suite pointer."""

    if not projection_root.is_dir() or projection_root.is_symlink():
        raise ContractError("active Skill projection requires a plain directory")
    pointer_path = projection_root / "references" / "installed-suite.json"
    pointer = _read_json(pointer_path, "managed Skill installed-suite pointer")
    if set(pointer) != {
        "contract",
        "schema_version",
        "product_id",
        "build_id",
        "content_index_sha256",
        "suite_root",
    }:
        raise ContractError("managed Skill installed-suite pointer fields are not exact")
    suite_root = Path(str(pointer.get("suite_root", ""))).expanduser().resolve()
    installs_root = (control_root / "installs").resolve()
    canonical_suite_root = (installs_root / expected_build_id).resolve()
    if (
        pointer.get("contract") != "paperspine5.installed-suite-pointer"
        or pointer.get("schema_version") != "1.0"
        or pointer.get("product_id") != "paperspine5"
        or pointer.get("build_id") != expected_build_id
        or pointer.get("content_index_sha256") != expected_content_index_sha256
        or suite_root != canonical_suite_root
        or not _is_relative_to(suite_root, installs_root)
        # A Skill has two distinct roots: the Codex projection and the
        # updater-managed suite it points at.  The pointer's canonical
        # installs-root/build/index checks above bind those roots already;
        # requiring the managed suite root to equal the projection root
        # rejects every valid installed Skill projection.
    ):
        raise ContractError("managed Skill installed-suite pointer binding is invalid")
    return {
        "root": str(projection_root),
        "source_tree": _tree_identity(projection_root),
        "installed_suite_pointer": {
            "path": str(pointer_path.resolve()),
            "sha256": _sha256_file(pointer_path),
        },
        "suite_root": str(suite_root),
    }


def resolve_installed_successor_authority(
    *,
    install_kind: str,
    control_root: str | Path,
    current_suite_root: str | Path,
    source_build_id: str,
    target_build_id: str,
    suite_verifier: SuiteVerifier,
) -> dict[str, Any]:
    """Resolve one forward-only Plugin or Skill updater chain.

    Every predecessor is required as the exact controlled backup made by the
    selected committed edge.  For Plugin, the final runtime must be the exact
    updater-activated cache.  For Skill, the active projection pointer must bind
    the exact managed suite used as ``current_suite_root``.  Rolled-back,
    ambiguous, missing, or partially recorded edges are not authority.
    """

    if install_kind not in {"plugin", "skill"}:
        raise ContractError("successor install kind must be plugin or skill")
    if not all(
        isinstance(item, str) and item
        for item in (source_build_id, target_build_id)
    ):
        raise ContractError("successor source and target build IDs are required")
    if source_build_id == target_build_id:
        raise ContractError("successor authority cannot authorize a no-op build")
    control = Path(control_root).expanduser().resolve()
    current = Path(current_suite_root).expanduser().resolve()
    state_path = control / "user-update-state.json"
    receipts_root = (control / "receipts").resolve()
    backups_root = (control / "backups").resolve()
    if not state_path.is_file() or not receipts_root.is_dir() or not backups_root.is_dir():
        raise ContractError(f"{install_kind} updater state, receipts, or backups are missing")
    state = _read_json(state_path, f"{install_kind} updater state")
    state_contract = f"paperspine5.{install_kind}-update-state"
    if (
        state.get("contract") != state_contract
        or state.get("schema_version") != "1.0"
        or state.get("product_id") != "paperspine5"
        or state.get("install_kind") != install_kind
    ):
        raise ContractError(f"{install_kind} updater state contract is invalid")
    active = state.get("active_installations")
    if not isinstance(active, list) or len(active) != 1 or not isinstance(active[0], dict):
        raise ContractError(f"{install_kind} updater must identify exactly one active installation")
    active_item = active[0]
    active_source = Path(str(active_item.get("target_root", ""))).resolve()
    if (
        active_item.get("kind") != install_kind
        or not active_source.is_dir()
        or active_item.get("build_id") != target_build_id
    ):
        raise ContractError(f"active {install_kind} installation is not the requested successor")

    history = state.get("history")
    if not isinstance(history, list):
        raise ContractError(f"{install_kind} updater history is invalid")
    selected_reverse: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    cursor = target_build_id
    before_index = len(history)
    seen = {target_build_id}
    while cursor != source_build_id:
        candidates: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
        for index, item in enumerate(history[:before_index]):
            if not isinstance(item, dict) or item.get("rolled_back") is True:
                continue
            if item.get("candidate_build_id") != cursor:
                continue
            placements = item.get("placements")
            if not isinstance(placements, list):
                continue
            matching_placements = [
                placement
                for placement in placements
                if isinstance(placement, dict) and placement.get("kind") == install_kind
            ]
            if len(matching_placements) == 1:
                candidates.append((index, item, matching_placements[0]))
        if not candidates:
            raise ContractError(
                f"no committed forward {install_kind} update chain reaches this task build"
            )
        index, item, placement = candidates[-1]
        previous = placement.get("previous")
        previous_build = previous.get("build_id") if isinstance(previous, dict) else None
        if not isinstance(previous_build, str) or not previous_build or previous_build in seen:
            raise ContractError(
                f"{install_kind} update chain is cyclic, downgraded, or missing its predecessor"
            )
        if (
            placement.get("candidate_placed") is not True
            or placement.get("previous_moved") is not True
            or Path(str(placement.get("target_root", ""))).resolve() != active_source
        ):
            raise ContractError(f"{install_kind} update edge was not completely committed")
        selected_reverse.append((index, item, placement))
        seen.add(previous_build)
        cursor = previous_build
        before_index = index
    selected = list(reversed(selected_reverse))
    if not selected:
        raise ContractError("successor authority chain is empty")

    receipt_files = list(receipts_root.glob("*.json"))
    chain: list[dict[str, Any]] = []
    expected_source = source_build_id
    for index, item, placement in selected:
        previous = placement["previous"]
        edge_source = previous.get("build_id")
        edge_target = item.get("candidate_build_id")
        if edge_source != expected_source or edge_target == edge_source:
            raise ContractError(f"{install_kind} update chain is discontinuous or downgraded")
        operation_id = item.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            raise ContractError(f"{install_kind} update edge operation identity is missing")
        matching_receipts: list[tuple[Path, dict[str, Any]]] = []
        for path in receipt_files:
            receipt = _read_json(path, f"{install_kind} update receipt")
            if receipt.get("operation_id") == operation_id:
                matching_receipts.append((path.resolve(), receipt))
        if len(matching_receipts) != 1:
            raise ContractError(
                f"{install_kind} update edge does not have one exact outer receipt"
            )
        receipt_path, receipt = matching_receipts[0]
        if not _is_relative_to(receipt_path, receipts_root):
            raise ContractError(f"{install_kind} update receipt escaped its control root")
        installations = receipt.get("installations")
        expected_receipt_contract = f"paperspine5.{install_kind}-update-receipt"
        if (
            receipt.get("contract") != expected_receipt_contract
            or receipt.get("schema_version") != "1.0"
            or receipt.get("install_kind") != install_kind
            or receipt.get("operation") != "upgrade"
            or receipt.get("status") != "committed"
            or receipt.get("candidate_build_id") != edge_target
            or receipt.get("rollback_performed") is not False
            or receipt.get("requested_target_applied") is not True
            or receipt.get("compensation_performed") is not False
            or receipt.get("external_action_authorized") is not False
            or not isinstance(installations, list)
            or len(installations) != 1
            or installations[0].get("kind") != install_kind
            or Path(str(installations[0].get("target_root", ""))).resolve()
            != active_source
        ):
            raise ContractError(
                f"{install_kind} update outer receipt is incomplete or mismatched"
            )
        if install_kind == "skill" and (
            receipt.get("activation") not in (None, [])
            or receipt.get("activation_phases") not in (None, [])
        ):
            raise ContractError("Skill update receipt cannot claim Plugin activation")
        backup = Path(str(placement.get("backup_root", ""))).resolve()
        if not _is_relative_to(backup, backups_root):
            raise ContractError(
                f"{install_kind} predecessor backup escaped the updater control root"
            )
        recorded_tree = placement.get("previous_tree")
        if not isinstance(recorded_tree, dict) or _tree_identity(backup) != recorded_tree:
            raise ContractError(
                f"{install_kind} predecessor backup tree is missing or tampered"
            )
        if install_kind == "plugin":
            source_suite_root = backup
        else:
            previous_suite_root = Path(str(previous.get("suite_root", ""))).resolve()
            expected_previous_root = (control / "installs" / str(edge_source)).resolve()
            previous_content_index = previous.get("content_index_sha256")
            if (
                previous_suite_root != expected_previous_root
                or not _is_relative_to(previous_suite_root, (control / "installs").resolve())
            ):
                raise ContractError("Skill predecessor managed suite escaped its control root")
            if not isinstance(previous_content_index, str) or not previous_content_index:
                raise ContractError("Skill predecessor managed suite content index is missing")
            _verified_skill_projection(
                backup,
                control_root=control,
                expected_build_id=str(edge_source),
                expected_content_index_sha256=previous_content_index,
                expected_suite_root=previous_suite_root,
            )
            source_suite_root = previous_suite_root
        if install_kind == "skill":
            source_suite = _verified_runtime_suite(
                source_suite_root,
                expected_build_id=str(edge_source),
                expected_content_index_sha256=previous_content_index,
            )
        else:
            source_suite = _verified_suite(
                source_suite_root,
                expected_build_id=edge_source,
                expected_content_index_sha256=previous.get("content_index_sha256"),
                suite_verifier=suite_verifier,
            )
        chain.append(
            {
                "history_index": index,
                "operation_id": operation_id,
                "source_build_id": edge_source,
                "target_build_id": edge_target,
                "source_suite": source_suite,
                "source_tree": recorded_tree,
                "target_tree": placement.get("candidate_tree"),
                "outer_receipt": {
                    "path": str(receipt_path),
                    "sha256": _sha256_file(receipt_path),
                },
            }
        )
        expected_source = str(edge_target)
    if expected_source != target_build_id:
        raise ContractError(f"{install_kind} update chain does not end at the active successor")
    if install_kind == "skill":
        # A Skill placement's ``candidate_tree`` is the user-facing
        # projection.  It may legitimately contain runtime residue (for
        # example source-bound ``__pycache__`` files) that differs from the
        # projection tree recorded as the next edge's prestate.  Verify every
        # immutable managed target suite and compare its build/content-index/
        # root identity with the following edge's verified source suite.
        target_suites: list[dict[str, Any]] = []
        installs_root = (control / "installs").resolve()
        for edge_index, edge in enumerate(chain):
            edge_target = str(edge["target_build_id"])
            target_root = (installs_root / edge_target).resolve()
            if not _is_relative_to(target_root, installs_root) or not target_root.is_dir():
                raise ContractError("Skill successor managed suite is missing")
            if edge_index + 1 < len(chain):
                next_previous = selected[edge_index + 1][2].get("previous")
                expected_index = (
                    next_previous.get("content_index_sha256")
                    if isinstance(next_previous, dict)
                    else None
                )
            else:
                expected_index = active_item.get("content_index_sha256")
            if not isinstance(expected_index, str) or not expected_index:
                raise ContractError("Skill successor managed suite content index is missing")
            target_suites.append(
                _verified_runtime_suite(
                    target_root,
                    expected_build_id=edge_target,
                    expected_content_index_sha256=expected_index,
                )
            )
        for edge_index, next_edge in enumerate(chain[1:]):
            previous_target = target_suites[edge_index]
            next_source = next_edge.get("source_suite")
            if (
                not isinstance(next_source, dict)
                or previous_target.get("build_id") != next_source.get("build_id")
                or previous_target.get("content_index_sha256")
                != next_source.get("content_index_sha256")
                or Path(str(previous_target.get("root", ""))).resolve()
                != Path(str(next_source.get("root", ""))).resolve()
            ):
                raise ContractError(
                    "Skill update chain intermediate managed suite identity is discontinuous"
                )
    else:
        for previous_edge, next_edge in zip(chain, chain[1:]):
            if previous_edge.get("target_tree") != next_edge.get("source_tree"):
                raise ContractError(
                    "plugin update chain intermediate suite identity is discontinuous"
                )

    source_installation_suite: dict[str, Any] | None = None
    skill_projection: dict[str, Any] | None = None
    if install_kind == "plugin":
        source_installation_suite = _verified_suite(
            active_source,
            expected_build_id=target_build_id,
            expected_content_index_sha256=active_item.get("content_index_sha256"),
            suite_verifier=suite_verifier,
        )
    else:
        skill_projection = _verified_skill_projection(
            active_source,
            control_root=control,
            expected_build_id=target_build_id,
            expected_content_index_sha256=str(active_item.get("content_index_sha256", "")),
            expected_suite_root=current,
        )
    final_receipt_path = Path(chain[-1]["outer_receipt"]["path"])
    final_receipt = _read_json(final_receipt_path, f"final {install_kind} update receipt")
    if install_kind == "plugin":
        activation = final_receipt.get("activation")
        activation_items = (
            activation
            if isinstance(activation, list)
            else [activation]
            if isinstance(activation, dict)
            else []
        )
        committed_activations = [
            item
            for item in activation_items
            if isinstance(item, dict)
            and item.get("phase") == "activate_candidate"
            and item.get("status") == "passed"
            and item.get("returncode") in {None, 0}
        ]
        activation_result = (
            committed_activations[0].get("result_json")
            if len(committed_activations) == 1
            else None
        )
        if (
            not isinstance(activation_result, dict)
            or Path(str(activation_result.get("installedPath", ""))).resolve() != current
            or activation_result.get("version") is None
        ):
            raise ContractError("active runtime core is not the updater-activated successor cache")
    target_suite = _verified_runtime_suite(
        current,
        expected_build_id=target_build_id,
        expected_content_index_sha256=str(active_item.get("content_index_sha256")),
    )
    final_tree = _tree_identity(active_source)
    if chain[-1].get("target_tree") != final_tree:
        raise ContractError("active successor tree differs from its committed update edge")
    authority = {
        "contract": "paperspine5.installed-successor-authority",
        "schema_version": "1.0",
        "install_kind": install_kind,
        "source_build_id": source_build_id,
        "target_build_id": target_build_id,
        "source_runner_version": chain[0]["source_suite"]["runner_version"],
        "target_runner_version": target_suite["runner_version"],
        "control_state": {
            "path": str(state_path.resolve()),
            "sha256": _sha256_file(state_path),
        },
        "active_suite": {
            **target_suite,
            "source_tree": final_tree,
            **(
                {"source_installation": source_installation_suite}
                if source_installation_suite is not None
                else {"skill_projection": skill_projection}
            ),
        },
        "chain": chain,
        "external_action_authorized": False,
    }
    authority["authority_sha256"] = _sha256_bytes(
        _canonical_json(authority).encode("utf-8")
    )
    return authority


def resolve_development_bootstrap_authority(
    *,
    development_source_root: str | Path,
    current_suite_root: str | Path,
    source_build_id: str,
    target_build_id: str,
    source_runner_version: str,
    suite_verifier: SuiteVerifier,
) -> dict[str, Any]:
    """Bind a first installed successor to the explicit development source.

    ``local-dev-unverified`` is the product's deliberate pre-release identity.
    It has no updater history by design, so a normal updater-chain resolver can
    never reach it.  This route is intentionally narrower than the installed
    resolver: callers must explicitly provide the source worktree, the source
    runtime marker is checked byte-for-byte, and the target is still verified by
    the release verifier.  No task or updater state is written here; the sealed
    same-task ``runner.successor.resume`` transaction remains the only mutation.
    """

    if source_build_id != DEVELOPMENT_BUILD_ID:
        raise ContractError("development bootstrap only accepts local-dev-unverified")
    if not isinstance(source_runner_version, str) or not source_runner_version:
        raise ContractError("development bootstrap source runner version is required")
    source_root = Path(development_source_root).expanduser().resolve()
    target_root = Path(current_suite_root).expanduser().resolve()
    if source_root == target_root or not source_root.is_dir() or source_root.is_symlink():
        raise ContractError("development bootstrap source root is invalid")

    runtime_path = source_root / "06_插件化" / "runtime" / "paperspine5_runtime.py"
    runner_path = (
        source_root
        / "03_联合开发"
        / "src"
        / "paperspine_figure_integration"
        / "product_runner.py"
    )
    if not runtime_path.is_file() or not runner_path.is_file():
        raise ContractError("development bootstrap source tree is incomplete")
    runtime_text = runtime_path.read_text(encoding="utf-8")
    if runtime_text.count(f'PRODUCT_BUILD_ID = "{DEVELOPMENT_BUILD_ID}"') != 1:
        raise ContractError("development bootstrap source runtime marker is invalid")
    # Do not recursively hash a workspace (it may contain user materials and
    # generated artifacts).  The bootstrap anchor binds the executable source
    # surfaces that define the runtime identity and runner protocol only.
    source_records: list[dict[str, Any]] = []
    for path in (runtime_path, runner_path):
        source_records.append(
            {
                "path": path.relative_to(source_root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    source_tree = {
        "file_count": len(source_records),
        "total_bytes": sum(item["size_bytes"] for item in source_records),
        "tree_sha256": _sha256_bytes(
            (json.dumps(source_records, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        ),
        "scope": "runtime-and-runner-source",
    }
    target_verified = suite_verifier(target_root)
    if (
        not isinstance(target_verified, dict)
        or target_verified.get("status") != "PASS"
        or target_verified.get("build_id") != target_build_id
        or target_verified.get("external_action_authorized") is not False
    ):
        raise ContractError("development bootstrap target suite is not verified")
    target_index = target_verified.get("content_index_sha256")
    if not isinstance(target_index, str) or not target_index:
        raise ContractError("development bootstrap target content index is missing")
    target_suite = _verified_runtime_suite(
        target_root,
        expected_build_id=target_build_id,
        expected_content_index_sha256=target_index,
    )
    target_tree = _tree_identity(target_root)
    source_suite = {
        "root": str(source_root),
        "build_id": source_build_id,
        "runner_version": source_runner_version,
        "development_source_tree": source_tree,
    }
    authority = {
        "contract": "paperspine5.installed-successor-authority",
        "schema_version": "1.0",
        "install_kind": "development-bootstrap",
        "source_build_id": source_build_id,
        "target_build_id": target_build_id,
        "source_runner_version": source_runner_version,
        "target_runner_version": target_suite["runner_version"],
        "control_state": {
            "mode": "explicit-development-source",
            "source_root": str(source_root),
            "source_tree": source_tree,
        },
        "active_suite": {
            **target_suite,
            "source_tree": target_tree,
        },
        "chain": [
            {
                "history_index": None,
                "operation_id": "development-bootstrap",
                "source_build_id": source_build_id,
                "target_build_id": target_build_id,
                "source_suite": source_suite,
                "target_tree": target_tree,
                "bootstrap": {
                    "contract": "paperspine5.development-bootstrap-authority",
                    "source_root": str(source_root),
                    "source_tree_sha256": source_tree["tree_sha256"],
                    "target_root": str(target_root),
                    "target_tree_sha256": target_tree["tree_sha256"],
                },
            }
        ],
        "external_action_authorized": False,
    }
    authority["authority_sha256"] = _sha256_bytes(
        _canonical_json(authority).encode("utf-8")
    )
    return authority


def resolve_plugin_successor_authority(
    *,
    control_root: str | Path,
    current_suite_root: str | Path,
    source_build_id: str,
    target_build_id: str,
    suite_verifier: SuiteVerifier,
) -> dict[str, Any]:
    """Backward-compatible strict Plugin authority wrapper."""

    return resolve_installed_successor_authority(
        install_kind="plugin",
        control_root=control_root,
        current_suite_root=current_suite_root,
        source_build_id=source_build_id,
        target_build_id=target_build_id,
        suite_verifier=suite_verifier,
    )


def resolve_skill_successor_authority(
    *,
    control_root: str | Path,
    current_suite_root: str | Path,
    source_build_id: str,
    target_build_id: str,
    suite_verifier: SuiteVerifier,
) -> dict[str, Any]:
    """Strict managed Standalone Skill authority wrapper."""

    return resolve_installed_successor_authority(
        install_kind="skill",
        control_root=control_root,
        current_suite_root=current_suite_root,
        source_build_id=source_build_id,
        target_build_id=target_build_id,
        suite_verifier=suite_verifier,
    )


def validate_successor_authority(
    value: Any,
    *,
    source_build_id: str,
    target_build_id: str,
    source_runner_version: str,
    target_runner_version: str,
    target_core_root: str | Path,
) -> dict[str, Any]:
    """Validate the normalized updater authority at the Runner boundary."""

    if not isinstance(value, dict):
        raise ContractError("installed successor authority must be an object")
    required = {
        "contract",
        "schema_version",
        "install_kind",
        "source_build_id",
        "target_build_id",
        "source_runner_version",
        "target_runner_version",
        "control_state",
        "active_suite",
        "chain",
        "external_action_authorized",
        "authority_sha256",
    }
    if set(value) != required:
        raise ContractError("installed successor authority fields are not exact")
    unsigned = {key: item for key, item in value.items() if key != "authority_sha256"}
    if value.get("authority_sha256") != _sha256_bytes(
        _canonical_json(unsigned).encode("utf-8")
    ):
        raise ContractError("installed successor authority hash is invalid")
    active = value.get("active_suite")
    chain = value.get("chain")
    if (
        value.get("contract") != "paperspine5.installed-successor-authority"
        or value.get("schema_version") != "1.0"
        or value.get("install_kind") not in {"plugin", "skill", "development-bootstrap"}
        or value.get("source_build_id") != source_build_id
        or value.get("target_build_id") != target_build_id
        or value.get("source_runner_version") != source_runner_version
        or value.get("target_runner_version") != target_runner_version
        or value.get("external_action_authorized") is not False
        or not isinstance(active, dict)
        or Path(str(active.get("root", ""))).resolve()
        != Path(target_core_root).resolve()
        or active.get("build_id") != target_build_id
        or not isinstance(chain, list)
        or not chain
    ):
        raise ContractError("installed successor authority binding is invalid")
    cursor = source_build_id
    seen = {cursor}
    for edge in chain:
        if (
            not isinstance(edge, dict)
            or edge.get("source_build_id") != cursor
            or not isinstance(edge.get("target_build_id"), str)
            or edge.get("target_build_id") in seen
        ):
            raise ContractError("installed successor authority chain is invalid")
        source_suite = edge.get("source_suite")
        if (
            not isinstance(source_suite, dict)
            or source_suite.get("build_id") != cursor
            or not Path(str(source_suite.get("root", ""))).is_dir()
        ):
            raise ContractError("installed successor authority lost a predecessor suite")
        cursor = edge["target_build_id"]
        seen.add(cursor)
    if cursor != target_build_id:
        raise ContractError("installed successor authority chain ends at another build")
    return json.loads(_canonical_json(value))
