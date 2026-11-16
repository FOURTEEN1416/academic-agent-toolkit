"""Real-byte canonical artifact adapter for the PaperSpine5 W5 candidate.

The adapter is deliberately narrower than a manuscript generator or a quality
oracle.  It consumes frozen W4 authority plus files that already exist in one
task run root, verifies exact byte spans and rendered pages, and emits typed
receipts.  It never infers a scientific claim from a filename, accepts a bare
LaTeX reference as figure integration, or treats schema validity as visual or
scientific quality.
"""

from __future__ import annotations

import copy
import hashlib
import json
import multiprocessing
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .contracts import ContractError, write_json_atomic
from .product_contracts import task_scoped_artifact_receipt_id
from .quality_readiness import QualitySubject, canonical_sha256, dependency_closure


CANONICAL_CONTRACT_VERSION = "1.0"
SAFE_ARTIFACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WORD_NATIVE_LAUNCH_ARGS = ("/w",)
WORD_NATIVE_COM_MAX_PATH = 259
REFERENCE_RE = re.compile(rb"\\(?:ref|autoref|cref|Cref)\{[^{}]+\}")
ARGUMENT_ROLES = frozenset(
    {
        "supports_claim",
        "qualifies_claim",
        "compares_claim",
        "explains_evidence",
        "limits_claim",
    }
)
READER_SURFACES = frozenset({"title", "abstract", "conclusion", "caption", "body"})
REQUIRED_PREEXISTING_AUTHORITY_IDS = frozenset(
    {"claim_scope_authority", "final_reader_review"}
)


@dataclass(frozen=True)
class _OwnedWordNativeBinding:
    """Keep the PID-bound Word Window and its Application alive together."""

    native_window: Any
    application: Any
    window_handle: int
    process_id: int


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_identity(path: Path) -> dict[str, Any]:
    info = path.stat()
    return {
        "path": str(path.resolve()),
        "sha256": _sha256_file(path),
        "size_bytes": int(info.st_size),
        "mtime_ns": int(info.st_mtime_ns),
    }


def _path_is_read_only(path: Path) -> bool:
    info = path.stat()
    file_attributes = getattr(info, "st_file_attributes", None)
    readonly_attribute = getattr(stat, "FILE_ATTRIBUTE_READONLY", None)
    if file_attributes is not None and readonly_attribute is not None:
        return bool(int(file_attributes) & int(readonly_attribute))
    return not bool(info.st_mode & stat.S_IWUSR)


def _path_is_reparse_point(path: Path) -> bool:
    """Return whether a staging boundary can redirect outside its task root."""

    if path.is_symlink():
        return True
    file_attributes = getattr(path.stat(), "st_file_attributes", None)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", None)
    return bool(
        file_attributes is not None
        and reparse_attribute is not None
        and int(file_attributes) & int(reparse_attribute)
    )


def _prepare_read_only_word_stage(source: Path, staged_source: Path) -> dict[str, Any]:
    """Copy exact DOCX bytes into the allowlisted stage before Word starts."""

    original_before = _file_identity(source)
    staged_source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, staged_source)
    os.chmod(staged_source, stat.S_IREAD)
    staged_before = _file_identity(staged_source)
    read_only = _path_is_read_only(staged_source)
    copy_verified = bool(
        staged_before["sha256"] == original_before["sha256"]
        and staged_before["size_bytes"] == original_before["size_bytes"]
    )
    if not copy_verified:
        raise RuntimeError("native Word staged DOCX bytes do not match the original")
    if not read_only:
        raise RuntimeError("native Word staged DOCX is writable")
    return {
        "original_before": original_before,
        "original_after": None,
        "staged_before": staged_before,
        "staged_after": None,
        "staged_read_only_before": True,
        "staged_read_only_after": None,
        "copy_verified": True,
        "original_unchanged": None,
        "original_opened_by_word": False,
    }


def _create_task_local_word_stage(root: Path, source_sha256: str) -> tuple[Path, Path]:
    """Create a process-private, shallow Word workspace inside the task run.

    Word's native COM document and PDF APIs still reject or ambiguously fail on
    paths beyond their legacy path ceiling, even when Python can create those
    paths.  Surface output directories can be deeply nested, so using the
    render directory itself as Word's workspace turns valid DOCX files into
    false renderer failures.  A randomized child under the run-root staging
    container keeps every byte task-local while making both paths short enough
    for Word.  Only that operation's child is removed, preserving concurrent
    renders owned by the same task.
    """

    resolved_root = root.resolve()
    container = resolved_root / ".word-native-stage"
    if container.exists() and _path_is_reparse_point(container):
        raise RuntimeError("task-local Word staging container is a reparse point")
    container.mkdir(parents=True, exist_ok=True)
    if _path_is_reparse_point(container):
        raise RuntimeError("task-local Word staging container is a reparse point")
    resolved_container = container.resolve(strict=True)
    if resolved_container.parent != resolved_root:
        raise RuntimeError("task-local Word staging container escaped the run root")
    operation_root = Path(
        tempfile.mkdtemp(prefix=f"{source_sha256[:8]}-", dir=resolved_container)
    ).resolve()
    if (
        operation_root.parent != resolved_container
        or _path_is_reparse_point(operation_root)
    ):
        shutil.rmtree(operation_root, ignore_errors=True)
        raise RuntimeError("task-local Word staging operation escaped its container")
    staged_source = operation_root / "source.docx"
    staged_pdf = operation_root / "output.pdf"
    if max(len(str(staged_source)), len(str(staged_pdf))) > WORD_NATIVE_COM_MAX_PATH:
        shutil.rmtree(operation_root, ignore_errors=True)
        try:
            resolved_container.rmdir()
        except OSError:
            pass
        raise RuntimeError(
            "task-local Word staging path exceeds the native COM path ceiling"
        )
    return operation_root, resolved_container


def _finalize_read_only_word_stage(
    source: Path, staged_source: Path, stage_record: dict[str, Any]
) -> tuple[bool, str]:
    """Recheck source/stage identities after Word and before stage cleanup."""

    try:
        original_after = _file_identity(source)
        staged_after = _file_identity(staged_source)
        staged_read_only_after = _path_is_read_only(staged_source)
    except OSError as exc:
        return False, f"native Word stage identity recheck failed: {exc}"
    stage_record["original_after"] = original_after
    stage_record["staged_after"] = staged_after
    stage_record["staged_read_only_after"] = staged_read_only_after
    original_unchanged = original_after == stage_record.get("original_before")
    staged_unchanged = bool(
        staged_after["sha256"]
        == stage_record.get("staged_before", {}).get("sha256")
        and staged_after["size_bytes"]
        == stage_record.get("staged_before", {}).get("size_bytes")
    )
    stage_record["original_unchanged"] = original_unchanged
    if not original_unchanged:
        return False, "original DOCX identity changed during native Word export"
    if not staged_unchanged:
        return False, "native Word staged DOCX identity changed during export"
    if not staged_read_only_after:
        return False, "native Word staged DOCX became writable during export"
    return True, ""


def _finding(code: str, message: str, path: str = "") -> dict[str, str]:
    finding = {"code": code, "message": message}
    if path:
        finding["path"] = path
    return finding


def _hashed(payload: dict[str, Any], field: str) -> dict[str, Any]:
    unsigned = {key: value for key, value in payload.items() if key != field}
    return {**unsigned, field: canonical_sha256(unsigned)}


def _read_json(path: Path) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, _finding("JSON_INVALID", f"cannot read valid JSON: {exc}", str(path))
    if not isinstance(raw, dict):
        return None, _finding("JSON_OBJECT_REQUIRED", "JSON artifact must be an object", str(path))
    return raw, None


def _resolve_in_root(root: Path, raw_path: str, field: str, *, must_exist: bool = True) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ContractError(f"{field} must be a non-empty project-relative path")
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"{field} escapes the task run root: {candidate}") from exc
    if must_exist and not candidate.is_file():
        raise ContractError(f"{field} is missing: {candidate}")
    return candidate


def _portable_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _tool_path(name: str, overrides: Mapping[str, str] | None) -> str | None:
    raw = (overrides or {}).get(name)
    if raw:
        candidate = Path(raw).resolve()
        return str(candidate) if candidate.is_file() else None
    return shutil.which(name)


def _winword_path(overrides: Mapping[str, str] | None) -> str | None:
    if overrides is not None and "winword" in overrides:
        return _tool_path("winword", overrides)
    discovered = shutil.which("winword")
    if discovered:
        return discovered
    for candidate in (
        Path(r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"),
        Path(r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE"),
    ):
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def _windows_file_version(path: Path) -> str | None:
    if path.name.casefold() != "winword.exe":
        return None
    try:
        import win32api

        info = win32api.GetFileVersionInfo(str(path), "\\")
        ms = int(info["FileVersionMS"])
        ls = int(info["FileVersionLS"])
        version = (
            f"{ms >> 16}.{ms & 0xffff}.{ls >> 16}.{ls & 0xffff}"
        )
        return f"Microsoft Word {version}"
    except (ImportError, OSError, TypeError, KeyError, ValueError):
        return None


def _tool_receipt(executable: str) -> dict[str, Any]:
    path = Path(executable).resolve()
    version = _windows_file_version(path) or ""
    if not version:
        try:
            result = subprocess.run(
                [str(path), "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
            version = (result.stdout or result.stderr).strip().splitlines()[0][:500]
        except (OSError, subprocess.SubprocessError, IndexError):
            version = "version probe unavailable"
    return {
        "path": str(path),
        "sha256": _sha256_file(path),
        "version": version,
    }


def _word_native_phase(path: Path | None, phase: str, process_id: int | None = None) -> None:
    if path is None:
        return
    write_json_atomic(
        path,
        {
            "contract": "paperspine5.word-native-export-phase",
            "phase": phase,
            "process_id": process_id,
        },
    )


def _word_process_id_from_hwnd(hwnd: int) -> int:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    process_id = wintypes.DWORD()
    thread_id = user32.GetWindowThreadProcessId(
        wintypes.HWND(hwnd), ctypes.byref(process_id)
    )
    if not thread_id or not process_id.value:
        raise OSError(f"cannot resolve process for window handle {hwnd}")
    return int(process_id.value)


def _word_process_created_at(process_id: int) -> float:
    """Resolve the exact creation identity for one owned Word PID."""

    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError("psutil is required to bind the owned Word process") from exc
    try:
        return float(psutil.Process(process_id).create_time())
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError) as exc:
        raise RuntimeError(
            f"cannot verify creation identity for owned Word PID {process_id}"
        ) from exc


def _owned_word_windows(process_id: int) -> list[dict[str, Any]]:
    """Enumerate every top-level/child window owned by one exact Word PID."""

    import ctypes
    from ctypes import wintypes

    observed: dict[int, dict[str, Any]] = {}
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowExW.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
    ]
    user32.FindWindowExW.restype = wintypes.HWND

    def class_name(hwnd: int) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        length = user32.GetClassNameW(wintypes.HWND(hwnd), buffer, len(buffer))
        return buffer.value[:200] if length else ""

    def window_title(hwnd: int) -> str:
        length = max(0, min(int(user32.GetWindowTextLengthW(wintypes.HWND(hwnd))), 500))
        buffer = ctypes.create_unicode_buffer(length + 1)
        if length:
            user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, len(buffer))
        return buffer.value[:500]

    def record(hwnd: int, parent_handle: int) -> None:
        try:
            window_process_id = _word_process_id_from_hwnd(hwnd)
            if window_process_id != process_id:
                return
            observed[int(hwnd)] = {
                "handle": int(hwnd),
                "parent_handle": int(parent_handle),
                "process_id": window_process_id,
                "class_name": class_name(hwnd),
                "title": window_title(hwnd),
                "visible": bool(user32.IsWindowVisible(wintypes.HWND(hwnd))),
            }
        except (OSError, TypeError, ValueError):
            return

    def children(parent: int) -> list[int]:
        handles: list[int] = []
        previous = 0
        for _index in range(10000):
            handle = int(
                user32.FindWindowExW(
                    wintypes.HWND(parent),
                    wintypes.HWND(previous),
                    None,
                    None,
                )
                or 0
            )
            if not handle:
                break
            handles.append(handle)
            previous = handle
        return handles

    top_level = children(0)
    queue: list[int] = []
    for handle in top_level:
        if _word_process_id_from_hwnd(handle) == process_id:
            record(handle, 0)
            queue.append(handle)
    visited = set(queue)
    while queue:
        parent = queue.pop(0)
        for handle in children(parent):
            if handle in visited:
                continue
            visited.add(handle)
            if _word_process_id_from_hwnd(handle) != process_id:
                continue
            record(handle, parent)
            queue.append(handle)
    class_priority = {"_WwG": 0, "_WwB": 1, "_WwF": 2, "OpusApp": 3}
    return sorted(
        observed.values(),
        key=lambda item: (
            class_priority.get(str(item["class_name"]), 99),
            int(item["handle"]),
        ),
    )


def _dispatch_from_accessible_pointer(
    pointer_value: int,
    *,
    object_from_address: Callable[[int, Any], Any] | None = None,
    dispatch_factory: Callable[[Any], Any] | None = None,
):
    """Convert one AddRef'd OBJID_NATIVEOM IDispatch pointer to a COM proxy."""

    if not isinstance(pointer_value, int) or pointer_value <= 0:
        raise ValueError("AccessibleObjectFromWindow returned an invalid pointer")
    import pythoncom
    import win32com.client

    converter = object_from_address or pythoncom.ObjectFromAddress
    dispatcher = dispatch_factory or win32com.client.Dispatch
    return dispatcher(converter(pointer_value, pythoncom.IID_IDispatch))


def _accessible_native_object_from_window(
    hwnd: int,
    *,
    accessible_call: Callable[[int], tuple[int, int | None]] | None = None,
    pointer_converter: Callable[[int], Any] | None = None,
) -> tuple[Any | None, dict[str, Any]]:
    """Resolve OBJID_NATIVEOM and return an unsuppressed typed diagnostic."""

    diagnostic: dict[str, Any] = {
        "window_handle": int(hwnd),
        "objid": "OBJID_NATIVEOM",
        "hresult": None,
        "pointer_present": False,
        "exception_category": None,
        "exception_message": None,
    }
    try:
        if accessible_call is None:
            import ctypes
            import uuid

            import pythoncom

            iid_dispatch = (ctypes.c_ubyte * 16).from_buffer_copy(
                uuid.UUID(str(pythoncom.IID_IDispatch)).bytes_le
            )
            pointer = ctypes.c_void_p()
            accessible = ctypes.OleDLL("oleacc").AccessibleObjectFromWindow
            accessible.argtypes = [
                ctypes.c_void_p,
                ctypes.c_long,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            accessible.restype = ctypes.c_long
            hresult = int(
                accessible(
                    ctypes.c_void_p(hwnd),
                    ctypes.c_long(-16),
                    ctypes.byref(iid_dispatch),
                    ctypes.byref(pointer),
                )
            )
            pointer_value = int(pointer.value) if pointer.value else None
        else:
            hresult, pointer_value = accessible_call(hwnd)
        diagnostic["hresult"] = int(hresult)
        diagnostic["pointer_present"] = bool(pointer_value)
        if hresult != 0 or not pointer_value:
            return None, diagnostic
        converter = pointer_converter or _dispatch_from_accessible_pointer
        return converter(int(pointer_value)), diagnostic
    except Exception as exc:  # pywin32/ctypes expose platform-specific classes.
        diagnostic["exception_category"] = type(exc).__name__
        diagnostic["exception_message"] = str(exc)[:1000]
        return None, diagnostic


def _owned_word_native_binding(
    native_window: Any,
    selected_window_handle: int,
    process_id: int,
    *,
    pid_resolver: Callable[[int], int] | None = None,
) -> _OwnedWordNativeBinding:
    """Bind the OBJID_NATIVEOM Word Window, then retain its Application."""

    resolve_pid = pid_resolver or _word_process_id_from_hwnd
    try:
        native_window_handle = int(native_window.Hwnd)
    except (AttributeError, TypeError):
        # Some late-bound Word Window proxies do not expose Hwnd through IDispatch.
        # The selected _WwG handle was already enumerated and PID-bound.
        native_window_handle = int(selected_window_handle)
    selected_process_id = resolve_pid(int(selected_window_handle))
    if selected_process_id != process_id:
        raise RuntimeError("selected _WwG escaped the owned Word PID")
    native_process_id = resolve_pid(native_window_handle)
    if native_process_id != process_id:
        raise RuntimeError("OBJID_NATIVEOM Word Window escaped the owned Word PID")
    try:
        application = native_window.Application
    except (AttributeError, TypeError) as exc:
        raise RuntimeError(
            "OBJID_NATIVEOM Word Window does not expose its Application"
        ) from exc
    if application is None:
        raise RuntimeError("OBJID_NATIVEOM Word Window returned no Application")
    return _OwnedWordNativeBinding(
        native_window=native_window,
        application=application,
        window_handle=native_window_handle,
        process_id=native_process_id,
    )


def _validate_word_native_launch_args(args: Sequence[str]) -> list[str]:
    normalized = [str(item) for item in args]
    if normalized != list(WORD_NATIVE_LAUNCH_ARGS):
        raise RuntimeError(
            "Microsoft Word native launch requires the single documented /w switch"
        )
    return normalized


def _owned_blank_bootstrap_word_document(
    application: Any,
    process_id: int,
    *,
    native_binding: _OwnedWordNativeBinding,
    expected_process_created_at: float,
) -> tuple[Any, dict[str, Any]]:
    """Bind the blank /w document and reject any window outside the owned PID."""

    documents = application.Documents
    if int(documents.Count) != 1:
        raise RuntimeError("owned /w Word instance did not expose one blank document")
    candidate = documents.Item(1)
    window_handle, window_process_id = _owned_word_document_window(
        candidate,
        process_id,
        native_binding=native_binding,
        expected_process_created_at=expected_process_created_at,
    )
    return candidate, {
        "name": str(candidate.Name)[:500],
        "blank_document": True,
        "window_handle": window_handle,
        "window_process_id": window_process_id,
    }


def _owned_word_document_window(
    document: Any,
    process_id: int,
    *,
    native_binding: _OwnedWordNativeBinding | None = None,
    pid_resolver: Callable[[int], int] | None = None,
    expected_process_created_at: float | None = None,
    process_created_at_resolver: Callable[[int], float] | None = None,
) -> tuple[int, int]:
    """Bind a Word document to the exact owned process/window identity.

    Documents opened with ``Visible=False`` legitimately expose no ActiveWindow.
    That case may reuse only the already PID-bound OBJID_NATIVEOM Word Window;
    it never discovers or attaches to another Word process.
    """

    resolve_pid = pid_resolver or _word_process_id_from_hwnd
    if expected_process_created_at is not None:
        resolve_created_at = process_created_at_resolver or _word_process_created_at
        current_created_at = float(resolve_created_at(process_id))
        if current_created_at != float(expected_process_created_at):
            raise RuntimeError("owned Word process identity changed or was reused")
    active_window = document.ActiveWindow
    if active_window is None:
        if native_binding is None:
            raise RuntimeError(
                "invisible Word document has no ActiveWindow and no owned NativeOM window"
            )
        if native_binding.process_id != process_id:
            raise RuntimeError("owned NativeOM binding PID does not match Word process")
        if native_binding.native_window is None or native_binding.application is None:
            raise RuntimeError("owned NativeOM binding is incomplete")
        window_handle = int(native_binding.window_handle)
    else:
        try:
            window_handle = int(active_window.Hwnd)
        except (AttributeError, TypeError, ValueError) as exc:
            raise RuntimeError("document ActiveWindow has no verifiable HWND") from exc
    if window_handle <= 0:
        raise RuntimeError("document window handle is invalid")
    window_process_id = resolve_pid(window_handle)
    if window_process_id != process_id:
        raise RuntimeError("document window escaped the owned Word PID")
    return window_handle, window_process_id


def _open_word_document_read_only(
    documents: Any,
    source: Path,
    *,
    missing_argument: Any | None = None,
) -> Any:
    """Open a DOCX with positional COM arguments and fail if Word returns null.

    ``AccessibleObjectFromWindow`` supplies a late-bound Word proxy.  On some
    Word builds, keyword optional arguments on that proxy are accepted by
    pywin32 but do not reach ``Documents.Open``.  A writable source then opens
    read/write, while a filesystem-read-only staged source can return ``None``
    after Word suppresses its modal prompt.  Positional arguments preserve the
    documented COM order without relaxing the read-only stage or visibility
    contract.
    """

    if missing_argument is None:
        import pythoncom

        missing_argument = pythoncom.Missing
    document = documents.Open(
        str(source),
        False,  # ConfirmConversions
        True,  # ReadOnly
        False,  # AddToRecentFiles
        missing_argument,  # PasswordDocument
        missing_argument,  # PasswordTemplate
        False,  # Revert
        missing_argument,  # WritePasswordDocument
        missing_argument,  # WritePasswordTemplate
        missing_argument,  # Format
        missing_argument,  # Encoding
        False,  # Visible
    )
    if document is None:
        raise RuntimeError(
            "Documents.Open returned no Document for the read-only staged DOCX"
        )
    return document


def _wait_for_owned_word_application(
    process_id: int,
    *,
    timeout_seconds: float = 30.0,
    poll_seconds: float = 0.25,
    window_enumerator: Callable[[int], list[dict[str, Any]]] | None = None,
    native_loader: Callable[[int], Any] | None = None,
    pid_resolver: Callable[[int], int] | None = None,
) -> tuple[Any | None, dict[str, Any]]:
    """Attach only through OBJID_NATIVEOM on a window of the exact owned PID."""

    enumerate_windows = window_enumerator or _owned_word_windows
    load_native = native_loader or _accessible_native_object_from_window
    resolve_pid = pid_resolver or _word_process_id_from_hwnd
    journal: dict[str, Any] = {
        "method": "AccessibleObjectFromWindow/OBJID_NATIVEOM",
        "owned_process_id": process_id,
        "windows_observed": [],
        "selected_window_handle": None,
        "native_window_handle": None,
        "application_acquired": False,
        "native_object_attached": False,
        "native_loader_attempts": [],
        "binding_failures": [],
    }
    observed_handles: set[int] = set()
    loader_attempts: dict[tuple[Any, ...], dict[str, Any]] = {}
    binding_failures: dict[tuple[Any, ...], dict[str, Any]] = {}

    def record_binding_failure(failure: dict[str, Any]) -> None:
        signature = tuple(
            (key, json.dumps(value, ensure_ascii=False, sort_keys=True))
            for key, value in sorted(failure.items())
        )
        if signature not in binding_failures:
            binding_failures[signature] = {**copy.deepcopy(failure), "attempt_count": 0}
        binding_failures[signature]["attempt_count"] += 1

    def finalize_attempts() -> None:
        journal["native_loader_attempts"] = list(loader_attempts.values())
        journal["binding_failures"] = list(binding_failures.values())

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            windows = enumerate_windows(process_id)
        except (ImportError, OSError, RuntimeError):
            windows = []
        for window in windows:
            handle = window.get("handle")
            if not isinstance(handle, int):
                continue
            if handle not in observed_handles:
                journal["windows_observed"].append(copy.deepcopy(window))
                observed_handles.add(handle)
            if window.get("class_name") != "_WwG":
                continue
            try:
                if resolve_pid(handle) != process_id:
                    continue
                loaded = load_native(handle)
                if (
                    isinstance(loaded, tuple)
                    and len(loaded) == 2
                    and isinstance(loaded[1], dict)
                ):
                    native_object, loader_diagnostic = loaded
                else:
                    native_object = loaded
                    loader_diagnostic = {
                        "window_handle": handle,
                        "objid": "OBJID_NATIVEOM",
                        "hresult": None,
                        "pointer_present": native_object is not None,
                        "exception_category": None,
                        "exception_message": None,
                    }
                signature = (
                    loader_diagnostic.get("window_handle"),
                    loader_diagnostic.get("hresult"),
                    loader_diagnostic.get("pointer_present"),
                    loader_diagnostic.get("exception_category"),
                    loader_diagnostic.get("exception_message"),
                )
                if signature not in loader_attempts:
                    loader_attempts[signature] = {
                        **copy.deepcopy(loader_diagnostic),
                        "attempt_count": 0,
                    }
                loader_attempts[signature]["attempt_count"] += 1
                if native_object is None:
                    continue
                binding = _owned_word_native_binding(
                    native_object,
                    handle,
                    process_id,
                    pid_resolver=resolve_pid,
                )
                journal.update(
                    {
                        "selected_window_handle": handle,
                        "native_window_handle": binding.window_handle,
                        "application_acquired": True,
                        "native_object_attached": True,
                    }
                )
                finalize_attempts()
                return binding, journal
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                record_binding_failure(
                    {
                        "window_handle": handle,
                        "category": type(exc).__name__,
                        "message": str(exc)[:1000],
                    }
                )
                continue
        time.sleep(poll_seconds)
    finalize_attempts()
    return None, journal


def _export_docx_with_word_native_in_process(
    source: Path,
    output_pdf: Path,
    *,
    phase_path: Path | None = None,
    preflight_only: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    """Export one task-local DOCX through a fresh hidden Word COM process."""

    document = None
    application = None
    process_id: int | None = None
    process_created_at: float | None = None
    launched_process: subprocess.Popen[str] | None = None
    com_initialized = False
    process_launch_args = _validate_word_native_launch_args(
        WORD_NATIVE_LAUNCH_ARGS
    )
    attach_journal: dict[str, Any] = {
        "method": "AccessibleObjectFromWindow/OBJID_NATIVEOM",
        "owned_process_id": None,
        "windows_observed": [],
        "selected_window_handle": None,
        "native_window_handle": None,
        "application_acquired": False,
        "native_object_attached": False,
        "native_loader_attempts": [],
        "binding_failures": [],
    }
    cleanup = {
        "document_closed": preflight_only,
        "bootstrap_document_closed": False,
        "application_quit": False,
        "process_exited": False,
    }
    recent_files = {
        "before_count": None,
        "after_count": None,
        "unchanged": False,
    }
    error = ""
    try:
        _word_native_phase(phase_path, "starting")
        import pythoncom

        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        com_initialized = True
        _word_native_phase(phase_path, "com_initialized")
        winword = _winword_path(None)
        if not winword:
            raise RuntimeError("WINWORD.EXE is unavailable")
        launched_process = subprocess.Popen(
            [winword, *process_launch_args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            startupinfo=(
                subprocess.STARTUPINFO(
                    dwFlags=subprocess.STARTF_USESHOWWINDOW,
                    wShowWindow=0,
                )
                if os.name == "nt"
                else None
            ),
        )
        process_id = int(launched_process.pid)
        process_created_at = _word_process_created_at(process_id)
        _word_native_phase(phase_path, "application_launched", process_id)
        binding, attach_journal = _wait_for_owned_word_application(process_id)
        if binding is None:
            raise RuntimeError(
                "new Microsoft Word instance did not expose an exact PID-bound "
                "AccessibleObjectFromWindow/OBJID_NATIVEOM object"
            )
        application = binding.application
        _word_native_phase(phase_path, "native_object_attached", process_id)
        application.Visible = False
        application.DisplayAlerts = 0
        application.AutomationSecurity = 3
        _word_native_phase(phase_path, "application_configured", process_id)
        bootstrap_document, bootstrap_journal = _owned_blank_bootstrap_word_document(
            application,
            process_id,
            native_binding=binding,
            expected_process_created_at=process_created_at,
        )
        attach_journal["bootstrap_document"] = bootstrap_journal
        bootstrap_document.Close(False)
        cleanup["bootstrap_document_closed"] = True
        _word_native_phase(phase_path, "bootstrap_document_closed", process_id)
        if not preflight_only:
            recent_files["before_count"] = int(application.RecentFiles.Count)
            document = _open_word_document_read_only(
                application.Documents,
                source,
            )
            reopened_window, reopened_process_id = _owned_word_document_window(
                document,
                process_id,
                native_binding=binding,
                expected_process_created_at=process_created_at,
            )
            attach_journal["export_document"] = {
                "path": str(source.resolve()),
                "read_only": bool(document.ReadOnly),
                "window_handle": reopened_window,
                "window_process_id": reopened_process_id,
                "open_api": (
                    "Documents.Open(ReadOnly=True,AddToRecentFiles=False,Visible=False)"
                ),
            }
            if not bool(document.ReadOnly):
                raise RuntimeError("explicit DOCX reopen is not read-only")
            _word_native_phase(phase_path, "document_opened", process_id)
            document.ExportAsFixedFormat(
                str(output_pdf),
                17,
                OpenAfterExport=False,
                OptimizeFor=0,
                Range=0,
                Item=0,
                IncludeDocProps=True,
                KeepIRM=True,
                CreateBookmarks=1,
                DocStructureTags=True,
                BitmapMissingFonts=True,
                UseISO19005_1=False,
            )
            _word_native_phase(phase_path, "pdf_exported", process_id)
            if not output_pdf.is_file() or output_pdf.stat().st_size <= 0:
                error = "Microsoft Word did not create a non-empty PDF"
            recent_files["after_count"] = int(application.RecentFiles.Count)
            recent_files["unchanged"] = bool(
                recent_files["after_count"] == recent_files["before_count"]
            )
            if not recent_files["unchanged"]:
                raise RuntimeError("native Word added the staged DOCX to RecentFiles")
    except (ImportError, OSError, RuntimeError) as exc:
        error = f"{type(exc).__name__}: {str(exc)[:1000]}"
    except Exception as exc:  # COM errors are pywin32 runtime types.
        error = f"{type(exc).__name__}: {str(exc)[:1000]}"
    finally:
        if document is not None:
            try:
                document.Close(False)
                cleanup["document_closed"] = True
            except Exception:
                pass
        if application is not None:
            try:
                application.Quit(False)
                cleanup["application_quit"] = True
            except Exception:
                pass
        elif launched_process is not None and launched_process.poll() is None:
            try:
                launched_process.terminate()
                launched_process.wait(timeout=10)
                cleanup["application_quit"] = True
            except (OSError, subprocess.SubprocessError):
                pass
        document = None
        application = None
        try:
            import gc

            gc.collect()
        except RuntimeError:
            pass
        if process_id is None:
            cleanup["process_exited"] = application is None
        else:
            try:
                import win32api
                import win32con
                import win32event

                handle = win32api.OpenProcess(win32con.SYNCHRONIZE, False, process_id)
                try:
                    cleanup["process_exited"] = (
                        win32event.WaitForSingleObject(handle, 10000)
                        == win32con.WAIT_OBJECT_0
                    )
                finally:
                    win32api.CloseHandle(handle)
            except (ImportError, OSError):
                cleanup["process_exited"] = False
        if com_initialized:
            try:
                import pythoncom

                pythoncom.CoUninitialize()
            except (ImportError, RuntimeError):
                pass
    if not all(cleanup.values()) and not error:
        error = "Microsoft Word native export did not close its document/application/process"
    journal = {
        "api": "Word.Application.ExportAsFixedFormat",
        "process_launch_args": process_launch_args,
        "native_object_attachment": attach_journal,
        "owned_process": {
            "process_id": process_id,
            "created_at": process_created_at,
            "exit_code": (
                launched_process.poll() if launched_process is not None else None
            ),
        },
        "preflight_only": preflight_only,
        "open_read_only": True,
        "add_to_recent_files": False,
        "application_visible": False,
        "display_alerts": 0,
        "automation_security": "msoAutomationSecurityForceDisable",
        "export_format": "wdExportFormatPDF",
        "recent_files": recent_files,
        "cleanup": cleanup,
    }
    return not error and (preflight_only or output_pdf.is_file()), error, journal


def _word_native_export_child(
    source: str,
    output_pdf: str,
    result_path: str,
    phase_path: str,
    preflight_only: bool,
) -> None:
    ok, detail, journal = _export_docx_with_word_native_in_process(
        Path(source),
        Path(output_pdf),
        phase_path=Path(phase_path),
        preflight_only=preflight_only,
    )
    write_json_atomic(
        Path(result_path),
        {"ok": ok, "detail": detail, "journal": journal},
    )


def _word_processes(executable: Path) -> dict[int, float]:
    try:
        import psutil
    except ImportError:
        return {}
    expected = str(executable.resolve()).casefold()
    observed: dict[int, float] = {}
    for process in psutil.process_iter(["pid", "exe", "create_time"]):
        try:
            if str(process.info.get("exe") or "").casefold() == expected:
                observed[int(process.info["pid"])] = float(process.info["create_time"])
        except (psutil.AccessDenied, psutil.NoSuchProcess, TypeError, ValueError):
            continue
    return observed


def _word_document_redirection_observation(
    source: Path,
    *,
    owned_process_id: int | None,
    preexisting_process_ids: set[int],
    owned_windows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Report, without attachment, whether the DOCX title appeared on another PID."""

    expected_tokens = {source.name.casefold(), source.stem.casefold()}
    windows_by_process: dict[str, list[dict[str, Any]]] = {}
    if owned_process_id is not None:
        windows_by_process[str(owned_process_id)] = copy.deepcopy(owned_windows)
    for process_id in sorted(preexisting_process_ids):
        try:
            windows_by_process[str(process_id)] = _owned_word_windows(process_id)
        except (ImportError, OSError, RuntimeError):
            windows_by_process[str(process_id)] = []
    matches = []
    for process_id_text, windows in windows_by_process.items():
        process_id = int(process_id_text)
        for window in windows:
            title = str(window.get("title") or "").casefold()
            if title and any(token in title for token in expected_tokens):
                matches.append(
                    {
                        **copy.deepcopy(window),
                        "process_id": process_id,
                        "owned_process": process_id == owned_process_id,
                    }
                )
    redirected = any(
        item["process_id"] in preexisting_process_ids for item in matches
    )
    return {
        "source_path": str(source.resolve()),
        "checked_preexisting_process_ids": sorted(preexisting_process_ids),
        "owned_process_id": owned_process_id,
        "windows_by_process": windows_by_process,
        "matching_document_windows": matches,
        "redirected_to_preexisting_process": redirected,
        "status": "REDIRECTED" if redirected else "NOT_OBSERVED",
    }


def _terminate_owned_word_processes(
    executable: Path, *, preexisting: set[int], phase_process_id: int | None
) -> list[int]:
    try:
        import psutil
    except ImportError:
        return []
    candidates = set(_word_processes(executable)) - preexisting
    if phase_process_id is not None and phase_process_id not in preexisting:
        candidates.add(phase_process_id)
    terminated: list[int] = []
    expected = str(executable.resolve()).casefold()
    for process_id in sorted(candidates):
        try:
            process = psutil.Process(process_id)
            if str(process.exe()).casefold() != expected:
                continue
            process.terminate()
            process.wait(timeout=10)
            terminated.append(process_id)
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.TimeoutExpired, OSError):
            continue
    return terminated


def _export_docx_with_word_native(
    source: Path,
    output_pdf: Path,
    *,
    timeout_seconds: int = 90,
    preflight_only: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    """Run native Word export out-of-process with a hard cap and owned cleanup."""

    operation_root = output_pdf.parent
    result_path = operation_root / ".word-native-result.json"
    phase_path = operation_root / ".word-native-phase.json"
    winword = Path(_winword_path(None) or "")
    preexisting_processes = _word_processes(winword) if winword.is_file() else {}
    preexisting = set(preexisting_processes)
    context = multiprocessing.get_context("spawn")
    child = context.Process(
        target=_word_native_export_child,
        args=(
            str(source),
            str(output_pdf),
            str(result_path),
            str(phase_path),
            preflight_only,
        ),
        name="paperspine-word-native-export",
    )
    child.start()
    child.join(timeout_seconds)
    timed_out = child.is_alive()
    if timed_out:
        child.terminate()
        child.join(10)
    phase: dict[str, Any] = {}
    if phase_path.is_file():
        phase, _issue = _read_json(phase_path)
        phase = phase or {}
    owned_word_process_id = phase.get("process_id")
    processes_before_cleanup = (
        _word_processes(winword) if winword.is_file() else {}
    )
    terminated = _terminate_owned_word_processes(
        winword,
        preexisting=preexisting,
        phase_process_id=(
            int(owned_word_process_id)
            if isinstance(owned_word_process_id, int)
            else None
        ),
    ) if winword.is_file() else []
    result: dict[str, Any] = {}
    if result_path.is_file():
        result, _issue = _read_json(result_path)
        result = result or {}
    for transient in (result_path, phase_path):
        transient.unlink(missing_ok=True)
    post_processes = _word_processes(winword) if winword.is_file() else {}
    owned_process_id = (
        int(owned_word_process_id)
        if isinstance(owned_word_process_id, int)
        else None
    )
    if timed_out:
        return (
            False,
            f"Microsoft Word native export exceeded {timeout_seconds}s at phase {phase.get('phase', 'unknown')}",
            {
                "api": "Word.Application.ExportAsFixedFormat",
                "last_phase": phase.get("phase", "unknown"),
                "child_exit_code": child.exitcode,
                "owned_process": {
                    "process_id": owned_process_id,
                    "created_at": processes_before_cleanup.get(owned_process_id),
                    "exit_code": None,
                },
                "preexisting_processes": [
                    {"process_id": process_id, "created_at": created_at}
                    for process_id, created_at in sorted(preexisting_processes.items())
                ],
                "post_word_processes": [
                    {"process_id": process_id, "created_at": created_at}
                    for process_id, created_at in sorted(post_processes.items())
                ],
                "cleanup": {
                    "document_closed": False,
                    "bootstrap_document_closed": False,
                    "application_quit": False,
                    "process_exited": not bool(set(post_processes) - preexisting),
                },
                "owned_processes_terminated": terminated,
                "document_redirection": _word_document_redirection_observation(
                    source,
                    owned_process_id=owned_process_id,
                    preexisting_process_ids=preexisting,
                    owned_windows=[],
                ),
            },
        )
    if child.exitcode != 0 or not result:
        return (
            False,
            f"Microsoft Word native export child failed with exit {child.exitcode}",
            {
                "api": "Word.Application.ExportAsFixedFormat",
                "last_phase": phase.get("phase", "unknown"),
                "child_exit_code": child.exitcode,
                "owned_process": {
                    "process_id": owned_process_id,
                    "created_at": processes_before_cleanup.get(owned_process_id),
                    "exit_code": None,
                },
                "preexisting_processes": [
                    {"process_id": process_id, "created_at": created_at}
                    for process_id, created_at in sorted(preexisting_processes.items())
                ],
                "post_word_processes": [
                    {"process_id": process_id, "created_at": created_at}
                    for process_id, created_at in sorted(post_processes.items())
                ],
                "cleanup": {
                    "document_closed": False,
                    "bootstrap_document_closed": False,
                    "application_quit": False,
                    "process_exited": not bool(set(post_processes) - preexisting),
                },
                "owned_processes_terminated": terminated,
                "document_redirection": _word_document_redirection_observation(
                    source,
                    owned_process_id=owned_process_id,
                    preexisting_process_ids=preexisting,
                    owned_windows=[],
                ),
            },
        )
    journal = result.get("journal") if isinstance(result.get("journal"), dict) else {}
    attachment = journal.get("native_object_attachment")
    owned_windows = (
        attachment.get("windows_observed")
        if isinstance(attachment, Mapping)
        and isinstance(attachment.get("windows_observed"), list)
        else []
    )
    journal["preexisting_processes"] = [
        {"process_id": process_id, "created_at": created_at}
        for process_id, created_at in sorted(preexisting_processes.items())
    ]
    journal["preexisting_processes_unchanged"] = all(
        post_processes.get(process_id) == created_at
        for process_id, created_at in preexisting_processes.items()
    )
    journal["owned_processes_terminated"] = terminated
    journal["child_exit_code"] = child.exitcode
    journal["post_word_processes"] = [
        {"process_id": process_id, "created_at": created_at}
        for process_id, created_at in sorted(post_processes.items())
    ]
    journal["document_redirection"] = _word_document_redirection_observation(
        source,
        owned_process_id=owned_process_id,
        preexisting_process_ids=preexisting,
        owned_windows=owned_windows,
    )
    return bool(result.get("ok")), str(result.get("detail") or ""), journal


def _run_renderer(command: Sequence[str], *, timeout: int = 120) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    detail = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    return result.returncode == 0, detail


def _pdf_page_count(pdfinfo: str, pdf_path: Path) -> tuple[int, str]:
    ok, output = _run_renderer([pdfinfo, str(pdf_path)])
    if not ok:
        return 0, output or "pdfinfo failed"
    match = re.search(r"(?mi)^Pages:\s+(\d+)\s*$", output)
    if match is None:
        return 0, "pdfinfo did not report a page count"
    return int(match.group(1)), ""


def _render_pdf_pages(
    root: Path,
    pdf_path: Path,
    output_dir: Path,
    *,
    tools: Mapping[str, str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    pdfinfo = _tool_path("pdfinfo", tools)
    pdftoppm = _tool_path("pdftoppm", tools)
    if not pdfinfo:
        blockers.append(
            _finding("PDFINFO_UNAVAILABLE", "pdfinfo is required for complete page coverage")
        )
    if not pdftoppm:
        blockers.append(
            _finding("PDF_RENDERER_UNAVAILABLE", "pdftoppm is required for PDF page rendering")
        )
    if blockers:
        return [], {}, blockers

    assert pdfinfo is not None and pdftoppm is not None
    page_count, error = _pdf_page_count(pdfinfo, pdf_path)
    if page_count <= 0:
        return [], {}, [_finding("PDF_PAGE_COUNT_BLOCKED", error, str(pdf_path))]

    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "page"
    command = [pdftoppm, "-png", "-r", "144", str(pdf_path), str(prefix)]
    ok, detail = _run_renderer(command)
    pages = sorted(
        output_dir.glob("page-*.png"),
        key=lambda path: int(re.search(r"(\d+)$", path.stem).group(1)),  # type: ignore[union-attr]
    )
    if not ok or len(pages) != page_count:
        return [], {}, [
            _finding(
                "PDF_RENDER_BLOCKED",
                detail or f"renderer produced {len(pages)} of {page_count} pages",
                str(pdf_path),
            )
        ]
    records = [
        {
            "page": index,
            "path": _portable_path(root, path),
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for index, path in enumerate(pages, 1)
    ]
    renderer = {
        "page_count_probe": _tool_receipt(pdfinfo),
        "page_renderer": _tool_receipt(pdftoppm),
        "dpi": 144,
        "page_render": {
            "authority": "paperspine5-canonical-artifact-adapter",
            "command": command,
            "input_pdf_path": _portable_path(root, pdf_path),
            "input_pdf_sha256": _sha256_file(pdf_path),
            "output_pages": [
                {
                    "page": item["page"],
                    "path": item["path"],
                    "sha256": item["sha256"],
                }
                for item in records
            ],
            "exit_code": 0,
            "status": "committed",
        },
    }
    return records, renderer, []


def prepare_surface_receipt(
    project_root: str | Path,
    source_path: str | Path,
    surface_kind: str,
    output_dir: str | Path,
    *,
    task_id: str,
    revision_id: str,
    producer_id: str,
    tools: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Render a real PDF/DOCX into per-page PNGs or return typed BLOCKED.

    Successful rendering is only ``REVIEW_REQUIRED``.  PASS is impossible
    until :func:`finalize_surface_receipt` verifies an independent review of
    every rendered page.
    """

    root = Path(project_root).resolve()
    source = Path(source_path).resolve()
    output = Path(output_dir).resolve()
    blockers: list[dict[str, str]] = []
    try:
        source.relative_to(root)
        output.relative_to(root)
    except ValueError:
        blockers.append(
            _finding("SURFACE_PATH_OUTSIDE_RUN_ROOT", "source and output must stay in task run root")
        )
    if not source.is_file():
        blockers.append(_finding("SURFACE_SOURCE_MISSING", "surface source file is missing", str(source)))
    if surface_kind not in {"pdf", "word"}:
        blockers.append(_finding("SURFACE_KIND_INVALID", "surface_kind must be pdf or word"))
    expected_suffix = ".pdf" if surface_kind == "pdf" else ".docx"
    if source.suffix.lower() != expected_suffix:
        blockers.append(
            _finding("SURFACE_FORMAT_MISMATCH", f"{surface_kind} source must end with {expected_suffix}")
        )

    source_sha = _sha256_file(source) if source.is_file() else ""
    pages: list[dict[str, Any]] = []
    renderer: dict[str, Any] = {}
    rendered_pdf: Path | None = None
    render_root = output / f"{surface_kind}-{source_sha[:12] or 'missing'}"
    if not blockers and surface_kind == "word":
        winword = _winword_path(tools)
        soffice = _tool_path("soffice", tools) or _tool_path("libreoffice", tools)
        if not winword and not soffice:
            blockers.append(
                _finding(
                    "WORD_RENDERER_UNAVAILABLE",
                    "Microsoft Word native export or LibreOffice/soffice is required; DOCX structure cannot substitute for rendered pages",
                )
            )
        elif winword:
            render_root.mkdir(parents=True, exist_ok=True)
            native_stage: Path | None = None
            native_stage_container: Path | None = None
            staged_source: Path | None = None
            staged_pdf: Path | None = None
            pending_pdf = render_root / f".{source.stem}.word-native-pending.pdf"
            rendered_pdf = render_root / f"{source.stem}.pdf"
            ok = False
            detail = ""
            journal: dict[str, Any] = {}
            stage_record: dict[str, Any] | None = None
            try:
                native_stage, native_stage_container = _create_task_local_word_stage(
                    root, source_sha
                )
                staged_source = native_stage / "source.docx"
                staged_pdf = native_stage / "output.pdf"
                stage_record = _prepare_read_only_word_stage(source, staged_source)
                ok, detail, journal = _export_docx_with_word_native(
                    staged_source, staged_pdf
                )
                stage_valid, stage_detail = _finalize_read_only_word_stage(
                    source, staged_source, stage_record
                )
                journal["source_stage"] = copy.deepcopy(stage_record)
                if not stage_valid:
                    ok = False
                    detail = stage_detail
                if ok:
                    shutil.copyfile(staged_pdf, pending_pdf)
            except (OSError, RuntimeError) as exc:
                ok = False
                detail = f"{type(exc).__name__}: {str(exc)[:1000]}"
            finally:
                if stage_record is not None and "source_stage" not in journal:
                    journal["source_stage"] = copy.deepcopy(stage_record)
                if staged_source is not None and staged_source.exists():
                    try:
                        os.chmod(staged_source, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        pass
                if native_stage is not None:
                    shutil.rmtree(native_stage, ignore_errors=True)
                journal["staging_root_removed"] = bool(
                    native_stage is not None and not native_stage.exists()
                )
                if native_stage_container is not None:
                    try:
                        native_stage_container.rmdir()
                    except OSError:
                        pass
                if not journal["staging_root_removed"]:
                    ok = False
                    detail = "native Word staging root cleanup failed"
            try:
                if ok:
                    os.replace(pending_pdf, rendered_pdf)
                else:
                    pending_pdf.unlink(missing_ok=True)
            except OSError as exc:
                ok = False
                detail = f"{type(exc).__name__}: {str(exc)[:1000]}"
                pending_pdf.unlink(missing_ok=True)
            if (
                not ok
                or not rendered_pdf.is_file()
                or not all(journal.get("cleanup", {}).values())
            ):
                blockers.append(
                    _finding(
                        "WORD_RENDER_BLOCKED",
                        detail or "Microsoft Word native export did not commit a clean PDF",
                        str(source),
                    )
                )
            else:
                command = [
                    winword,
                    *journal["process_launch_args"],
                    "AccessibleObjectFromWindow/OBJID_NATIVEOM",
                    "Visible=False",
                    "DisplayAlerts=0",
                    "AutomationSecurity=msoAutomationSecurityForceDisable",
                    "Documents.Open(ReadOnly=True,AddToRecentFiles=False,Visible=False)",
                    "ExportAsFixedFormat(wdExportFormatPDF)",
                    str(staged_source),
                    str(rendered_pdf),
                ]
                renderer["word_backend"] = "microsoft-word-native"
                renderer["word_renderer"] = _tool_receipt(winword)
                renderer["intermediate_pdf"] = {
                    "path": _portable_path(root, rendered_pdf),
                    "sha256": _sha256_file(rendered_pdf),
                }
                renderer["word_conversion"] = {
                    "authority": "paperspine5-canonical-artifact-adapter",
                    "backend": "microsoft-word-native",
                    "operation_id": f"word-native-export:{source_sha[:24]}",
                    "command": command,
                    "operation": journal,
                    "source_path": _portable_path(root, source),
                    "source_sha256": source_sha,
                    "output_pdf_path": _portable_path(root, rendered_pdf),
                    "output_pdf_sha256": _sha256_file(rendered_pdf),
                    "exit_code": 0,
                    "status": "committed",
                    "external_action_authorized": False,
                }
        else:
            assert soffice is not None
            render_root.mkdir(parents=True, exist_ok=True)
            profile = render_root / "lo-profile"
            profile.mkdir(parents=True, exist_ok=True)
            command = [
                soffice,
                "--headless",
                f"-env:UserInstallation={profile.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(render_root),
                str(source),
            ]
            ok, detail = _run_renderer(command)
            rendered_pdf = render_root / f"{source.stem}.pdf"
            if not ok or not rendered_pdf.is_file():
                blockers.append(
                    _finding(
                        "WORD_RENDER_BLOCKED",
                        detail or "LibreOffice did not create a PDF",
                        str(source),
                    )
                )
            else:
                renderer["word_backend"] = "libreoffice-soffice"
                renderer["word_renderer"] = _tool_receipt(soffice)
                renderer["intermediate_pdf"] = {
                    "path": _portable_path(root, rendered_pdf),
                    "sha256": _sha256_file(rendered_pdf),
                }
                renderer["word_conversion"] = {
                    "authority": "paperspine5-canonical-artifact-adapter",
                    "backend": "libreoffice-soffice",
                    "operation_id": f"word-soffice-export:{source_sha[:24]}",
                    "command": command,
                    "source_path": _portable_path(root, source),
                    "source_sha256": source_sha,
                    "output_pdf_path": _portable_path(root, rendered_pdf),
                    "output_pdf_sha256": _sha256_file(rendered_pdf),
                    "exit_code": 0,
                    "status": "committed",
                    "external_action_authorized": False,
                }
    elif not blockers:
        rendered_pdf = source

    if not blockers and rendered_pdf is not None:
        page_records, pdf_renderer, page_blockers = _render_pdf_pages(
            root,
            rendered_pdf,
            render_root / "pages",
            tools=tools,
        )
        pages = page_records
        renderer.update(pdf_renderer)
        blockers.extend(page_blockers)

    result = {
        "contract": "paperspine5.surface-receipt",
        "contract_version": CANONICAL_CONTRACT_VERSION,
        "task_id": task_id,
        "revision_id": str(revision_id),
        "surface_kind": surface_kind,
        "source": {
            "path": _portable_path(root, source) if source.is_file() and source.is_relative_to(root) else str(source),
            "sha256": source_sha,
            "size_bytes": source.stat().st_size if source.is_file() else 0,
        },
        "producer_id": producer_id,
        "renderer": renderer,
        "pages": pages,
        "page_count": len(pages),
        "review": None,
        "status": "BLOCKED" if blockers else "REVIEW_REQUIRED",
        "blockers": blockers,
        "external_action_authorized": False,
    }
    return _hashed(result, "receipt_sha256")


def finalize_surface_receipt(
    project_root: str | Path,
    prepared: Mapping[str, Any],
    review_path: str | Path,
    *,
    producer_ids: Iterable[str],
) -> dict[str, Any]:
    """Bind a page-complete independent review to a prepared surface."""

    root = Path(project_root).resolve()
    result = dict(prepared)
    blockers = list(result.get("blockers", []))
    supplied_hash = result.get("receipt_sha256")
    unsigned = {key: value for key, value in result.items() if key != "receipt_sha256"}
    if supplied_hash != canonical_sha256(unsigned):
        blockers.append(_finding("SURFACE_PREPARED_HASH_INVALID", "prepared receipt hash is invalid"))
    review_file = Path(review_path).resolve()
    try:
        review_portable_path = _portable_path(root, review_file)
    except ValueError:
        blockers.append(
            _finding("SURFACE_REVIEW_OUTSIDE_RUN_ROOT", "surface review must stay in task run root")
        )
        review_portable_path = str(review_file)
    review, issue = _read_json(review_file)
    if issue:
        blockers.append(issue)
        review = {}
    producers = {str(item).strip().casefold() for item in producer_ids if str(item).strip()}
    reviewer = str((review or {}).get("reviewer_id") or "").strip()
    if not reviewer:
        blockers.append(_finding("SURFACE_REVIEWER_MISSING", "reviewer_id is required"))
    elif reviewer.casefold() in producers:
        blockers.append(_finding("SURFACE_REVIEW_SELF_SIGNED", "surface reviewer is a producer"))
    if (review or {}).get("self_signed_final") is not False:
        blockers.append(_finding("SURFACE_SELF_SIGNED_FINAL", "self_signed_final must be false"))
    if (review or {}).get("final_decision") != "pass":
        blockers.append(_finding("SURFACE_REVIEW_BLOCKED", "final_decision must be pass"))
    if (review or {}).get("surface_kind") != result.get("surface_kind"):
        blockers.append(_finding("SURFACE_REVIEW_KIND_MISMATCH", "reviewed surface kind changed"))
    if (review or {}).get("source_sha256") != (result.get("source") or {}).get("sha256"):
        blockers.append(_finding("SURFACE_REVIEW_SOURCE_STALE", "review does not bind source bytes"))
    if (review or {}).get("contract") != "paperspine5.surface-review-receipt":
        blockers.append(_finding("SURFACE_REVIEW_CONTRACT_INVALID", "surface review contract is invalid"))
    if (review or {}).get("contract_version") != CANONICAL_CONTRACT_VERSION:
        blockers.append(_finding("SURFACE_REVIEW_VERSION_INVALID", "surface review version is invalid"))
    if str((review or {}).get("task_id") or "") != str(result.get("task_id") or "") or str(
        (review or {}).get("revision_id") or ""
    ) != str(result.get("revision_id") or ""):
        blockers.append(_finding("SURFACE_REVIEW_SUBJECT_MISMATCH", "surface review changed task/revision"))
    if (review or {}).get("prepared_receipt_sha256") != supplied_hash:
        blockers.append(
            _finding("SURFACE_REVIEW_PREPARED_STALE", "review does not bind the prepared receipt")
        )

    expected_pages = {
        (item.get("page"), item.get("sha256"))
        for item in result.get("pages", [])
        if isinstance(item, Mapping)
    }
    reviewed_pages_raw = (review or {}).get("pages")
    reviewed_pages = reviewed_pages_raw if isinstance(reviewed_pages_raw, list) else []
    observed_pages = {
        (item.get("page"), item.get("render_sha256"))
        for item in reviewed_pages
        if isinstance(item, Mapping) and item.get("status") == "pass"
    }
    if not expected_pages or observed_pages != expected_pages or len(reviewed_pages) != len(expected_pages):
        blockers.append(
            _finding(
                "SURFACE_PAGE_REVIEW_INCOMPLETE",
                "every rendered page must have one hash-bound PASS review",
            )
        )

    result["review"] = {
        "path": review_portable_path,
        "sha256": _sha256_file(review_file) if review_file.is_file() else "",
        "reviewer_id": reviewer,
        "producer_ids": sorted(producers),
        "self_signed_final": (review or {}).get("self_signed_final"),
        "reviewed_at": (review or {}).get("reviewed_at"),
        "final_decision": (review or {}).get("final_decision"),
    }
    result["prepared_receipt_sha256"] = supplied_hash
    result["status"] = "BLOCKED" if blockers else "PASS"
    result["blockers"] = blockers
    return _hashed(result, "receipt_sha256")


def _verify_span(
    span: Any,
    inputs: Mapping[str, dict[str, Any]],
    blockers: list[dict[str, str]],
    path: str,
) -> dict[str, Any] | None:
    if not isinstance(span, Mapping):
        blockers.append(_finding("SPAN_INVALID", "exact byte span must be an object", path))
        return None
    artifact_id = str(span.get("artifact_id") or "")
    record = inputs.get(artifact_id)
    if record is None:
        blockers.append(_finding("SPAN_ARTIFACT_UNKNOWN", f"unknown artifact {artifact_id}", path))
        return None
    start = span.get("start_byte")
    end = span.get("end_byte")
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int):
        blockers.append(_finding("SPAN_OFFSETS_INVALID", "span offsets must be integers", path))
        return None
    payload = record["bytes"]
    if start < 0 or end <= start or end > len(payload):
        blockers.append(_finding("SPAN_OUT_OF_RANGE", "span is outside the current artifact bytes", path))
        return None
    excerpt = payload[start:end]
    supplied = span.get("sha256")
    actual = _sha256_bytes(excerpt)
    if supplied != actual:
        blockers.append(_finding("SPAN_HASH_MISMATCH", "span hash does not match exact current bytes", path))
        return None
    try:
        text = excerpt.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    return {
        "artifact_id": artifact_id,
        "start_byte": start,
        "end_byte": end,
        "sha256": actual,
        "text": text,
    }


def _reference_is_reader_body(manuscript: bytes, start: int, end: int) -> bool:
    excerpt = manuscript[start:end]
    if REFERENCE_RE.fullmatch(excerpt) is None:
        return False
    line_start = manuscript.rfind(b"\n", 0, start) + 1
    prefix = manuscript[line_start:start]
    for match in re.finditer(rb"%", prefix):
        slash_count = 0
        cursor = match.start() - 1
        while cursor >= 0 and prefix[cursor : cursor + 1] == b"\\":
            slash_count += 1
            cursor -= 1
        if slash_count % 2 == 0:
            return False
    for match in re.finditer(rb"\\begin\{figure\*?\}", manuscript):
        close = re.search(rb"\\end\{figure\*?\}", manuscript[match.end() :])
        stop = len(manuscript) if close is None else match.end() + close.end()
        if match.start() <= start < stop:
            return False
    return True


def _load_inputs(
    root: Path,
    spec_path: Path,
    spec: Mapping[str, Any],
    blockers: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if spec_path.is_file():
        spec_bytes = spec_path.read_bytes()
        records["canonical_binding_spec"] = {
            "artifact_id": "canonical_binding_spec",
            "role": "binding_spec",
            "path": spec_path,
            "portable_path": _portable_path(root, spec_path),
            "sha256": _sha256_bytes(spec_bytes),
            "size_bytes": len(spec_bytes),
            "bytes": spec_bytes,
        }
    artifacts = spec.get("artifacts")
    if not isinstance(artifacts, Mapping) or not artifacts:
        blockers.append(_finding("CANONICAL_ARTIFACTS_MISSING", "spec.artifacts must be non-empty"))
        return records
    for artifact_id, raw in artifacts.items():
        field = f"artifacts.{artifact_id}"
        if not isinstance(artifact_id, str) or SAFE_ARTIFACT_ID.fullmatch(artifact_id) is None:
            blockers.append(_finding("CANONICAL_ARTIFACT_ID_INVALID", "artifact ID is unsafe", field))
            continue
        if artifact_id in records:
            blockers.append(_finding("CANONICAL_ARTIFACT_ID_DUPLICATE", "artifact ID is reserved", field))
            continue
        if not isinstance(raw, Mapping):
            blockers.append(_finding("CANONICAL_ARTIFACT_INVALID", "artifact record must be an object", field))
            continue
        try:
            path = _resolve_in_root(root, str(raw.get("path") or ""), f"{field}.path")
        except ContractError as exc:
            blockers.append(_finding("CANONICAL_ARTIFACT_PATH_INVALID", str(exc), field))
            continue
        payload = path.read_bytes()
        actual_sha = _sha256_bytes(payload)
        if raw.get("sha256") != actual_sha:
            blockers.append(
                _finding("CANONICAL_ARTIFACT_HASH_MISMATCH", "declared hash differs from file bytes", field)
            )
        records[artifact_id] = {
            "artifact_id": artifact_id,
            "role": str(raw.get("role") or ""),
            "path": path,
            "portable_path": _portable_path(root, path),
            "sha256": actual_sha,
            "size_bytes": len(payload),
            "bytes": payload,
        }
    return records


def _validate_scope_authority(
    scope: Mapping[str, Any],
    inputs: Mapping[str, dict[str, Any]],
    blockers: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    if scope.get("contract") != "paperspine5.claim-scope-authority":
        blockers.append(_finding("CLAIM_SCOPE_CONTRACT_INVALID", "W4 claim scope authority is required"))
    if scope.get("contract_version") != CANONICAL_CONTRACT_VERSION:
        blockers.append(_finding("CLAIM_SCOPE_VERSION_INVALID", "claim scope version is invalid"))
    reviewer = str(scope.get("reviewer_id") or "").strip()
    producers = {str(item).strip().casefold() for item in scope.get("producer_ids", []) if str(item).strip()}
    if not reviewer or reviewer.casefold() in producers:
        blockers.append(_finding("CLAIM_SCOPE_NOT_INDEPENDENT", "scope reviewer must differ from producers"))
    if scope.get("self_signed_final") is not False or scope.get("final_decision") != "pass":
        blockers.append(_finding("CLAIM_SCOPE_BLOCKED", "scope authority must be independently passing"))
    claim_graph = inputs.get("claim_graph")
    if claim_graph is None or scope.get("claim_graph_sha256") != claim_graph["sha256"]:
        blockers.append(_finding("CLAIM_SCOPE_STALE", "scope does not bind the current claim graph"))
    claims_raw = scope.get("claims")
    claims = claims_raw if isinstance(claims_raw, list) else []
    by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(claims):
        if not isinstance(item, Mapping):
            blockers.append(_finding("CLAIM_SCOPE_ITEM_INVALID", "scope claim must be an object"))
            continue
        claim_id = str(item.get("claim_id") or "").strip()
        if not claim_id or claim_id in by_id:
            blockers.append(_finding("CLAIM_SCOPE_ID_INVALID", "claim IDs must be non-empty and unique"))
            continue
        surfaces = item.get("required_surfaces")
        if not isinstance(surfaces, list) or any(surface not in READER_SURFACES for surface in surfaces):
            blockers.append(
                _finding("CLAIM_SCOPE_SURFACE_INVALID", "required surfaces use unsupported values", f"claims[{index}]")
            )
        by_id[claim_id] = dict(item)
    if not by_id:
        blockers.append(_finding("CLAIM_SCOPE_EMPTY", "scope authority must enumerate source claims"))
    return by_id


def _span_key(span: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        span.get("artifact_id"),
        span.get("start_byte"),
        span.get("end_byte"),
        span.get("sha256"),
    )


def _validate_surface_receipt(
    root: Path,
    receipt: Mapping[str, Any],
    blockers: list[dict[str, str]],
    path: str,
    *,
    task_id: str,
    revision_id: str,
) -> dict[str, Any]:
    supplied = receipt.get("receipt_sha256")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if supplied != canonical_sha256(unsigned):
        blockers.append(_finding("SURFACE_RECEIPT_HASH_INVALID", "surface receipt hash is invalid", path))
    if receipt.get("contract") != "paperspine5.surface-receipt" or receipt.get("status") != "PASS":
        blockers.append(_finding("SURFACE_RECEIPT_BLOCKED", "surface receipt is not PASS", path))
    if receipt.get("external_action_authorized") is not False:
        blockers.append(_finding("SURFACE_EXTERNAL_AUTHORITY_FORBIDDEN", "surface receipt cannot authorize actions", path))
    if str(receipt.get("task_id") or "") != task_id or str(receipt.get("revision_id") or "") != revision_id:
        blockers.append(_finding("SURFACE_SUBJECT_MISMATCH", "surface receipt changed task/revision", path))
    renderer = receipt.get("renderer")
    tool_paths: dict[str, Path] = {}
    if not isinstance(renderer, Mapping):
        blockers.append(_finding("SURFACE_RENDERER_INVALID", "renderer provenance is missing", path))
    else:
        required_tools = ["page_count_probe", "page_renderer"]
        if receipt.get("surface_kind") == "word":
            required_tools.append("word_renderer")
        for key in required_tools:
            tool = renderer.get(key)
            if not isinstance(tool, Mapping):
                blockers.append(_finding("SURFACE_RENDERER_INVALID", f"missing {key}", path))
                continue
            tool_path = Path(str(tool.get("path") or "")).resolve()
            if not tool_path.is_file() or _sha256_file(tool_path) != tool.get("sha256"):
                blockers.append(
                    _finding("SURFACE_RENDERER_STALE", f"{key} executable is missing or changed", path)
                )
            else:
                tool_paths[key] = tool_path
            if not isinstance(tool.get("version"), str) or not str(tool.get("version")).strip():
                blockers.append(
                    _finding("SURFACE_RENDERER_VERSION_MISSING", f"{key} version is missing", path)
                )
    source = receipt.get("source")
    resolved_source: Path | None = None
    if not isinstance(source, Mapping):
        blockers.append(_finding("SURFACE_SOURCE_INVALID", "surface source is missing", path))
    else:
        try:
            source_path = _resolve_in_root(root, str(source.get("path") or ""), f"{path}.source")
        except ContractError as exc:
            blockers.append(_finding("SURFACE_SOURCE_INVALID", str(exc), path))
        else:
            resolved_source = source_path
            if _sha256_file(source_path) != source.get("sha256"):
                blockers.append(_finding("SURFACE_SOURCE_STALE", "surface source bytes changed", path))

    resolved_intermediate: Path | None = None
    if isinstance(renderer, Mapping) and receipt.get("surface_kind") == "word":
        word_tool = renderer.get("word_renderer")
        word_tool_path = tool_paths.get("word_renderer")
        word_backend = renderer.get("word_backend")
        word_version = str(word_tool.get("version") or "") if isinstance(word_tool, Mapping) else ""
        if (
            isinstance(word_tool, Mapping)
            and (
                (word_backend == "microsoft-word-native" and "microsoft word" not in word_version.casefold())
                or (word_backend == "libreoffice-soffice" and "libreoffice" not in word_version.casefold())
                or word_backend not in {"microsoft-word-native", "libreoffice-soffice"}
            )
        ):
            blockers.append(
                _finding(
                    "WORD_RENDERER_IDENTITY_INVALID",
                    "Word renderer version does not identify LibreOffice",
                    path,
                )
            )
        intermediate = renderer.get("intermediate_pdf")
        conversion = renderer.get("word_conversion")
        if not isinstance(intermediate, Mapping) or not isinstance(conversion, Mapping):
            blockers.append(
                _finding(
                    "WORD_CONVERSION_JOURNAL_MISSING",
                    "Word surface requires the canonical DOCX-to-PDF journal",
                    path,
                )
            )
        else:
            try:
                resolved_intermediate = _resolve_in_root(
                    root,
                    str(intermediate.get("path") or ""),
                    f"{path}.renderer.intermediate_pdf",
                )
                conversion_source = _resolve_in_root(
                    root,
                    str(conversion.get("source_path") or ""),
                    f"{path}.renderer.word_conversion.source_path",
                )
                conversion_output = _resolve_in_root(
                    root,
                    str(conversion.get("output_pdf_path") or ""),
                    f"{path}.renderer.word_conversion.output_pdf_path",
                )
            except ContractError as exc:
                blockers.append(_finding("WORD_CONVERSION_JOURNAL_INVALID", str(exc), path))
            else:
                command = conversion.get("command")
                command_values = command if isinstance(command, list) else []
                operation = conversion.get("operation")
                owned_process = (
                    operation.get("owned_process")
                    if isinstance(operation, Mapping)
                    else None
                )
                native_attachment = (
                    operation.get("native_object_attachment")
                    if isinstance(operation, Mapping)
                    else None
                )
                observed_windows = (
                    native_attachment.get("windows_observed")
                    if isinstance(native_attachment, Mapping)
                    else None
                )
                observed_handles = {
                    item.get("handle")
                    for item in observed_windows or []
                    if isinstance(item, Mapping)
                }
                selected_windows = [
                    item
                    for item in observed_windows or []
                    if isinstance(item, Mapping)
                    and item.get("handle")
                    == (
                        native_attachment.get("selected_window_handle")
                        if isinstance(native_attachment, Mapping)
                        else None
                    )
                ]
                native_windows = [
                    item
                    for item in observed_windows or []
                    if isinstance(item, Mapping)
                    and item.get("handle")
                    == (
                        native_attachment.get("native_window_handle")
                        if isinstance(native_attachment, Mapping)
                        else None
                    )
                ]
                native_loader_attempts = (
                    native_attachment.get("native_loader_attempts")
                    if isinstance(native_attachment, Mapping)
                    else None
                )
                bootstrap_document = (
                    native_attachment.get("bootstrap_document")
                    if isinstance(native_attachment, Mapping)
                    else None
                )
                export_document = (
                    native_attachment.get("export_document")
                    if isinstance(native_attachment, Mapping)
                    else None
                )
                export_windows = [
                    item
                    for item in observed_windows or []
                    if isinstance(item, Mapping)
                    and isinstance(export_document, Mapping)
                    and item.get("handle") == export_document.get("window_handle")
                ]
                document_redirection = (
                    operation.get("document_redirection")
                    if isinstance(operation, Mapping)
                    else None
                )
                source_stage = (
                    operation.get("source_stage")
                    if isinstance(operation, Mapping)
                    else None
                )
                recent_files = (
                    operation.get("recent_files")
                    if isinstance(operation, Mapping)
                    else None
                )
                staged_source_path: Path | None = None
                source_stage_valid = False
                if isinstance(source_stage, Mapping) and resolved_source is not None:
                    original_before = source_stage.get("original_before")
                    original_after = source_stage.get("original_after")
                    staged_before = source_stage.get("staged_before")
                    staged_after = source_stage.get("staged_after")
                    if all(
                        isinstance(item, Mapping)
                        for item in (
                            original_before,
                            original_after,
                            staged_before,
                            staged_after,
                        )
                    ):
                        try:
                            staged_source_path = Path(
                                str(staged_before.get("path") or "")
                            ).resolve()
                            staged_relative = staged_source_path.relative_to(root)
                            original_before_path = Path(
                                str(original_before.get("path") or "")
                            ).resolve()
                            original_after_path = Path(
                                str(original_after.get("path") or "")
                            ).resolve()
                            staged_after_path = Path(
                                str(staged_after.get("path") or "")
                            ).resolve()
                        except (OSError, ValueError):
                            staged_source_path = None
                        else:
                            source_identity = _file_identity(resolved_source)
                            source_stage_valid = bool(
                                original_before_path == resolved_source
                                and original_after_path == resolved_source
                                and staged_after_path == staged_source_path
                                and len(staged_relative.parts) == 3
                                and staged_relative.parts[0]
                                == ".word-native-stage"
                                and staged_relative.parts[2] == "source.docx"
                                and len(str(staged_source_path))
                                <= WORD_NATIVE_COM_MAX_PATH
                                and dict(original_before) == dict(original_after)
                                and dict(original_after) == source_identity
                                and original_before.get("sha256")
                                == source.get("sha256")
                                and original_before.get("size_bytes")
                                == source.get("size_bytes")
                                and staged_before.get("sha256")
                                == original_before.get("sha256")
                                and staged_before.get("size_bytes")
                                == original_before.get("size_bytes")
                                and staged_after.get("sha256")
                                == staged_before.get("sha256")
                                and staged_after.get("size_bytes")
                                == staged_before.get("size_bytes")
                                and source_stage.get("staged_read_only_before")
                                is True
                                and source_stage.get("staged_read_only_after")
                                is True
                                and source_stage.get("copy_verified") is True
                                and source_stage.get("original_unchanged") is True
                                and source_stage.get("original_opened_by_word")
                                is False
                            )
                native_operation_valid = bool(
                    word_backend == "microsoft-word-native"
                    and isinstance(operation, Mapping)
                    and operation.get("api") == "Word.Application.ExportAsFixedFormat"
                    and operation.get("process_launch_args") == ["/w"]
                    and isinstance(native_attachment, Mapping)
                    and isinstance(owned_process, Mapping)
                    and owned_process.get("exit_code") == 0
                    and native_attachment.get("method")
                    == "AccessibleObjectFromWindow/OBJID_NATIVEOM"
                    and native_attachment.get("native_object_attached") is True
                    and native_attachment.get("owned_process_id")
                    == owned_process.get("process_id")
                    and native_attachment.get("selected_window_handle")
                    in observed_handles
                    and native_attachment.get("native_window_handle")
                    in observed_handles
                    and native_attachment.get("application_acquired") is True
                    and len(selected_windows) == 1
                    and selected_windows[0].get("class_name") == "_WwG"
                    and selected_windows[0].get("process_id")
                    == owned_process.get("process_id")
                    and len(native_windows) == 1
                    and native_windows[0].get("process_id")
                    == owned_process.get("process_id")
                    and isinstance(native_loader_attempts, list)
                    and any(
                        isinstance(item, Mapping)
                        and item.get("window_handle")
                        == native_attachment.get("selected_window_handle")
                        and item.get("hresult") == 0
                        and item.get("pointer_present") is True
                        and item.get("exception_category") is None
                        for item in native_loader_attempts
                    )
                    and isinstance(bootstrap_document, Mapping)
                    and isinstance(export_document, Mapping)
                    and bootstrap_document.get("blank_document") is True
                    and isinstance(bootstrap_document.get("name"), str)
                    and bool(bootstrap_document.get("name"))
                    and bootstrap_document.get("window_process_id")
                    == owned_process.get("process_id")
                    and source_stage_valid
                    and staged_source_path is not None
                    and Path(str(export_document.get("path") or "")).resolve()
                    == staged_source_path
                    and export_document.get("read_only") is True
                    and export_document.get("window_process_id")
                    == owned_process.get("process_id")
                    and export_document.get("window_handle")
                    in {
                        native_attachment.get("selected_window_handle"),
                        native_attachment.get("native_window_handle"),
                    }
                    and len(export_windows) == 1
                    and export_windows[0].get("process_id")
                    == owned_process.get("process_id")
                    and export_document.get("open_api")
                    == "Documents.Open(ReadOnly=True,AddToRecentFiles=False,Visible=False)"
                    and operation.get("preflight_only") is False
                    and operation.get("preexisting_processes_unchanged") is True
                    and isinstance(operation.get("preexisting_processes"), list)
                    and operation.get("child_exit_code") == 0
                    and isinstance(operation.get("post_word_processes"), list)
                    and isinstance(document_redirection, Mapping)
                    and Path(
                        str(document_redirection.get("source_path") or "")
                    ).resolve()
                    == staged_source_path
                    and document_redirection.get(
                        "redirected_to_preexisting_process"
                    )
                    is False
                    and document_redirection.get("status") == "NOT_OBSERVED"
                    and operation.get("open_read_only") is True
                    and operation.get("add_to_recent_files") is False
                    and isinstance(recent_files, Mapping)
                    and isinstance(recent_files.get("before_count"), int)
                    and recent_files.get("before_count") >= 0
                    and recent_files.get("after_count")
                    == recent_files.get("before_count")
                    and recent_files.get("unchanged") is True
                    and operation.get("application_visible") is False
                    and operation.get("display_alerts") == 0
                    and operation.get("automation_security")
                    == "msoAutomationSecurityForceDisable"
                    and operation.get("export_format") == "wdExportFormatPDF"
                    and operation.get("cleanup")
                    == {
                        "document_closed": True,
                        "bootstrap_document_closed": True,
                        "application_quit": True,
                        "process_exited": True,
                    }
                    and operation.get("staging_root_removed") is True
                )
                command_valid = bool(
                    command_values
                    and word_tool_path is not None
                    and Path(str(command_values[0])).resolve() == word_tool_path
                    and (
                        (
                            word_backend == "microsoft-word-native"
                            and command_values[1:2] == ["/w"]
                            and command_values[2:8]
                            == [
                                "AccessibleObjectFromWindow/OBJID_NATIVEOM",
                                "Visible=False",
                                "DisplayAlerts=0",
                                "AutomationSecurity=msoAutomationSecurityForceDisable",
                                "Documents.Open(ReadOnly=True,AddToRecentFiles=False,Visible=False)",
                                "ExportAsFixedFormat(wdExportFormatPDF)",
                            ]
                            and len(command_values) == 10
                            and staged_source_path is not None
                            and Path(str(command_values[8])).resolve()
                            == staged_source_path
                            and Path(str(command_values[9])).resolve()
                            == resolved_intermediate
                            and native_operation_valid
                        )
                        or (
                            word_backend == "libreoffice-soffice"
                            and "--headless" in command_values
                            and "--convert-to" in command_values
                            and "pdf" in command_values
                            and "--outdir" in command_values
                            and resolved_source is not None
                            and Path(str(command_values[-1])).resolve()
                            == resolved_source
                            and operation is None
                        )
                    )
                )
                if (
                    conversion.get("authority")
                    != "paperspine5-canonical-artifact-adapter"
                    or conversion.get("backend") != word_backend
                    or not isinstance(conversion.get("operation_id"), str)
                    or not conversion.get("operation_id")
                    or conversion.get("external_action_authorized") is not False
                    or conversion.get("status") != "committed"
                    or conversion.get("exit_code") != 0
                    or not command_valid
                    or resolved_source is None
                    or conversion_source != resolved_source
                    or conversion.get("source_sha256")
                    != (source.get("sha256") if isinstance(source, Mapping) else None)
                    or conversion_output != resolved_intermediate
                    or conversion.get("output_pdf_sha256")
                    != intermediate.get("sha256")
                    or _sha256_file(resolved_intermediate) != intermediate.get("sha256")
                ):
                    blockers.append(
                        _finding(
                            "WORD_CONVERSION_JOURNAL_INVALID",
                            "Word conversion journal is stale, forged, or not canonical",
                            path,
                        )
                    )
    pages_raw = receipt.get("pages")
    pages = pages_raw if isinstance(pages_raw, list) else []
    if not pages or receipt.get("page_count") != len(pages):
        blockers.append(_finding("SURFACE_UNPAGED", "surface must contain every rendered page", path))
    expected_numbers = list(range(1, len(pages) + 1))
    if [item.get("page") for item in pages if isinstance(item, Mapping)] != expected_numbers:
        blockers.append(_finding("SURFACE_PAGE_SEQUENCE_INVALID", "surface page numbers must be contiguous", path))
    for index, page in enumerate(pages):
        if not isinstance(page, Mapping):
            blockers.append(_finding("SURFACE_PAGE_INVALID", "page record must be an object", path))
            continue
        try:
            render_path = _resolve_in_root(root, str(page.get("path") or ""), f"{path}.pages[{index}]")
        except ContractError as exc:
            blockers.append(_finding("SURFACE_PAGE_INVALID", str(exc), path))
            continue
        if _sha256_file(render_path) != page.get("sha256"):
            blockers.append(_finding("SURFACE_PAGE_STALE", "rendered page bytes changed", path))
    if isinstance(renderer, Mapping):
        page_render = renderer.get("page_render")
        expected_input = resolved_intermediate if receipt.get("surface_kind") == "word" else resolved_source
        if not isinstance(page_render, Mapping):
            blockers.append(
                _finding(
                    "SURFACE_PAGE_RENDER_JOURNAL_MISSING",
                    "page render command and outputs are not bound",
                    path,
                )
            )
        else:
            try:
                rendered_input = _resolve_in_root(
                    root,
                    str(page_render.get("input_pdf_path") or ""),
                    f"{path}.renderer.page_render.input_pdf_path",
                )
            except ContractError as exc:
                blockers.append(_finding("SURFACE_PAGE_RENDER_JOURNAL_INVALID", str(exc), path))
            else:
                command = page_render.get("command")
                command_values = command if isinstance(command, list) else []
                expected_outputs = [
                    {
                        "page": item.get("page"),
                        "path": item.get("path"),
                        "sha256": item.get("sha256"),
                    }
                    for item in pages
                    if isinstance(item, Mapping)
                ]
                if (
                    page_render.get("authority")
                    != "paperspine5-canonical-artifact-adapter"
                    or page_render.get("status") != "committed"
                    or page_render.get("exit_code") != 0
                    or not command_values
                    or tool_paths.get("page_renderer") is None
                    or Path(str(command_values[0])).resolve()
                    != tool_paths["page_renderer"]
                    or expected_input is None
                    or rendered_input != expected_input
                    or page_render.get("input_pdf_sha256")
                    != _sha256_file(expected_input)
                    or page_render.get("output_pages") != expected_outputs
                ):
                    blockers.append(
                        _finding(
                            "SURFACE_PAGE_RENDER_JOURNAL_INVALID",
                            "page render journal is stale, forged, or does not bind all pages",
                            path,
                        )
                    )
    review = receipt.get("review")
    resolved_review: Path | None = None
    review_payload: dict[str, Any] = {}
    if not isinstance(review, Mapping) or review.get("final_decision") != "pass" or not review.get("reviewer_id"):
        blockers.append(_finding("SURFACE_REVIEW_INVALID", "surface review is not independently PASS", path))
    else:
        producers = {
            str(item).strip().casefold()
            for item in review.get("producer_ids", [])
            if str(item).strip()
        }
        reviewer = str(review.get("reviewer_id") or "").strip()
        if reviewer.casefold() in producers or review.get("self_signed_final") is not False:
            blockers.append(
                _finding("SURFACE_REVIEW_SELF_SIGNED", "surface reviewer is a producer", path)
            )
        try:
            resolved_review = _resolve_in_root(root, str(review.get("path") or ""), f"{path}.review")
        except ContractError as exc:
            blockers.append(_finding("SURFACE_REVIEW_INVALID", str(exc), path))
        else:
            if _sha256_file(resolved_review) != review.get("sha256"):
                blockers.append(_finding("SURFACE_REVIEW_STALE", "surface review bytes changed", path))
            raw_review, review_issue = _read_json(resolved_review)
            if review_issue:
                blockers.append(review_issue)
            else:
                review_payload = raw_review or {}
                if (
                    review_payload.get("contract") != "paperspine5.surface-review-receipt"
                    or review_payload.get("contract_version") != CANONICAL_CONTRACT_VERSION
                    or review_payload.get("final_decision") != "pass"
                    or review_payload.get("self_signed_final") is not False
                    or review_payload.get("reviewer_id") != reviewer
                    or review_payload.get("surface_kind") != receipt.get("surface_kind")
                    or review_payload.get("source_sha256") != (source or {}).get("sha256")
                    or review_payload.get("prepared_receipt_sha256")
                    != receipt.get("prepared_receipt_sha256")
                    or {
                        str(item).strip().casefold()
                        for item in review_payload.get("producer_ids", [])
                        if str(item).strip()
                    }
                    != producers
                    or str(review_payload.get("task_id") or "")
                    != str(receipt.get("task_id") or "")
                    or str(review_payload.get("revision_id") or "")
                    != str(receipt.get("revision_id") or "")
                ):
                    blockers.append(
                        _finding("SURFACE_REVIEW_PAYLOAD_INVALID", "review payload does not match receipt", path)
                    )
                reviewed_pages = review_payload.get("pages")
                reviewed_pages = reviewed_pages if isinstance(reviewed_pages, list) else []
                expected = {
                    (item.get("page"), item.get("sha256"))
                    for item in pages
                    if isinstance(item, Mapping)
                }
                observed = {
                    (item.get("page"), item.get("render_sha256"))
                    for item in reviewed_pages
                    if isinstance(item, Mapping) and item.get("status") == "pass"
                }
                if not expected or expected != observed or len(reviewed_pages) != len(expected):
                    blockers.append(
                        _finding("SURFACE_PAGE_REVIEW_INCOMPLETE", "review is not page-complete", path)
                    )
    return {
        "pages": [dict(item) for item in pages if isinstance(item, Mapping)],
        "source_path": resolved_source,
        "review_path": resolved_review,
        "review": review_payload,
    }


def validate_surface_receipt(
    project_root: str | Path,
    receipt: Mapping[str, Any],
    *,
    task_id: str,
    revision_id: str,
) -> dict[str, Any]:
    """Validate one finalized canonical surface receipt without re-rendering it."""

    root = Path(project_root).resolve()
    blockers: list[dict[str, str]] = []
    resolved = _validate_surface_receipt(
        root,
        receipt,
        blockers,
        "surface_receipt",
        task_id=task_id,
        revision_id=str(revision_id),
    )
    pages: list[Path] = []
    for item in resolved["pages"]:
        try:
            pages.append(
                _resolve_in_root(root, str(item.get("path") or ""), "surface_receipt.pages")
            )
        except ContractError:
            continue
    return {
        "status": "PASS" if not blockers else "BLOCKED",
        "blockers": blockers,
        "surface_kind": receipt.get("surface_kind"),
        "source_path": resolved.get("source_path"),
        "page_paths": pages,
        "review_path": resolved.get("review_path"),
    }


def compile_canonical_artifacts(
    project_root: str | Path,
    binding_spec_path: str | Path,
    *,
    task_id: str,
    revision_id: str,
    previous_input_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Compile real files into W5 candidate receipts without claiming quality."""

    root = Path(project_root).resolve()
    spec_path = Path(binding_spec_path).resolve()
    blockers: list[dict[str, str]] = []
    try:
        spec_path.relative_to(root)
    except ValueError:
        blockers.append(_finding("BINDING_SPEC_OUTSIDE_RUN_ROOT", "binding spec escapes task run root"))
    spec, issue = _read_json(spec_path)
    if issue:
        blockers.append(issue)
        spec = {}
    if spec.get("contract") != "paperspine5.canonical-binding-spec" or spec.get(
        "contract_version"
    ) != CANONICAL_CONTRACT_VERSION:
        blockers.append(_finding("BINDING_SPEC_CONTRACT_INVALID", "canonical binding spec/version is invalid"))

    inputs = _load_inputs(root, spec_path, spec, blockers)
    required_ids = {"canonical_manuscript", "claim_graph", *REQUIRED_PREEXISTING_AUTHORITY_IDS}
    figure_mode = spec.get("figure_mode")
    if figure_mode not in {"none", "present"}:
        blockers.append(_finding("FIGURE_MODE_INVALID", "figure_mode must be none or present"))
    if figure_mode == "present":
        required_ids.add("figure_body_contract")
    missing = sorted(required_ids - set(inputs))
    if missing:
        blockers.append(_finding("CANONICAL_REQUIRED_INPUT_MISSING", f"missing inputs: {missing}"))

    surface_receipts: list[dict[str, Any]] = []
    for artifact_id, record in list(inputs.items()):
        if record["role"] != "surface_receipt":
            continue
        receipt, receipt_issue = _read_json(record["path"])
        if receipt_issue:
            blockers.append(receipt_issue)
            continue
        assert receipt is not None
        surface = _validate_surface_receipt(
            root,
            receipt,
            blockers,
            f"artifacts.{artifact_id}",
            task_id=task_id,
            revision_id=str(revision_id),
        )
        surface_receipts.append(receipt)
        surface_kind = str(receipt.get("surface_kind") or "unknown")
        for dynamic_role, dynamic_path in (
            ("surface_source", surface.get("source_path")),
            ("surface_review", surface.get("review_path")),
        ):
            if not isinstance(dynamic_path, Path):
                continue
            dynamic_id = f"surface:{surface_kind}:{dynamic_role}"
            if dynamic_id in inputs:
                blockers.append(
                    _finding("SURFACE_DYNAMIC_ID_COLLISION", f"duplicate surface artifact {dynamic_id}")
                )
                continue
            payload = dynamic_path.read_bytes()
            inputs[dynamic_id] = {
                "artifact_id": dynamic_id,
                "role": dynamic_role,
                "path": dynamic_path,
                "portable_path": _portable_path(root, dynamic_path),
                "sha256": _sha256_bytes(payload),
                "size_bytes": len(payload),
                "bytes": payload,
            }
        for page in surface["pages"]:
            page_id = f"surface:{receipt.get('surface_kind')}:page:{page.get('page')}"
            if page_id in inputs:
                blockers.append(_finding("SURFACE_DYNAMIC_ID_COLLISION", f"duplicate page {page_id}"))
                continue
            try:
                page_path = _resolve_in_root(root, str(page.get("path") or ""), page_id)
            except ContractError as exc:
                blockers.append(_finding("SURFACE_PAGE_INVALID", str(exc), page_id))
                continue
            payload = page_path.read_bytes()
            inputs[page_id] = {
                "artifact_id": page_id,
                "role": "surface_page",
                "path": page_path,
                "portable_path": _portable_path(root, page_path),
                "sha256": _sha256_bytes(payload),
                "size_bytes": len(payload),
                "bytes": payload,
            }

    input_hashes = {artifact_id: record["sha256"] for artifact_id, record in inputs.items()}
    try:
        subject = QualitySubject(task_id, str(revision_id), input_hashes)
    except Exception as exc:
        fallback_hash = _sha256_file(spec_path) if spec_path.is_file() else hashlib.sha256(b"missing").hexdigest()
        subject = QualitySubject(task_id or "invalid-task", str(revision_id) or "invalid-revision", {"canonical_binding_spec": fallback_hash})
        blockers.append(_finding("CANONICAL_SUBJECT_INVALID", str(exc)))

    scope: dict[str, Any] = {}
    scope_record = inputs.get("claim_scope_authority")
    if scope_record:
        raw_scope, scope_issue = _read_json(scope_record["path"])
        if scope_issue:
            blockers.append(scope_issue)
        else:
            scope = raw_scope or {}
    scope_claims = _validate_scope_authority(scope, inputs, blockers)

    review: dict[str, Any] = {}
    review_record = inputs.get("final_reader_review")
    if review_record:
        raw_review, review_issue = _read_json(review_record["path"])
        if review_issue:
            blockers.append(review_issue)
        else:
            review = raw_review or {}
    producers = {str(item).strip().casefold() for item in review.get("producer_ids", []) if str(item).strip()}
    reviewer = str(review.get("reviewer_id") or "").strip()
    if review.get("contract") != "paperspine5.final-reader-review-receipt":
        blockers.append(_finding("FINAL_REVIEW_CONTRACT_INVALID", "independent final-reader review is required"))
    if review.get("contract_version") != CANONICAL_CONTRACT_VERSION:
        blockers.append(_finding("FINAL_REVIEW_VERSION_INVALID", "final-reader review version is invalid"))
    if not reviewer or reviewer.casefold() in producers:
        blockers.append(_finding("FINAL_REVIEW_NOT_INDEPENDENT", "reviewer must differ from producers"))
    if review.get("self_signed_final") is not False or review.get("final_decision") != "pass":
        blockers.append(_finding("FINAL_REVIEW_BLOCKED", "final-reader review must independently pass"))
    reviewed_hashes = review.get("reviewed_artifact_hashes")
    required_review_ids = set(spec.get("review_required_artifact_ids", []))
    if not isinstance(reviewed_hashes, Mapping):
        blockers.append(_finding("FINAL_REVIEW_INPUTS_MISSING", "reviewed_artifact_hashes must be a mapping"))
    else:
        for artifact_id in sorted(required_review_ids):
            record = inputs.get(str(artifact_id))
            if record is None or reviewed_hashes.get(artifact_id) != record["sha256"]:
                blockers.append(
                    _finding("FINAL_REVIEW_STALE", f"review did not freeze current artifact {artifact_id}")
                )

    body: dict[str, Any] = {}
    body_figures: dict[str, dict[str, Any]] = {}
    if figure_mode == "present" and "figure_body_contract" in inputs:
        raw_body, body_issue = _read_json(inputs["figure_body_contract"]["path"])
        if body_issue:
            blockers.append(body_issue)
        else:
            body = raw_body or {}
        if body.get("schema_version") != "1.1" or body.get("contract_type") != "paperspine.figure.body" or body.get("status") != "PASS":
            blockers.append(_finding("FIGURE_BODY_CONTRACT_INVALID", "current PASS body contract 1.1 is required"))
        figures_raw = body.get("figures")
        for item in figures_raw if isinstance(figures_raw, list) else []:
            if not isinstance(item, Mapping) or not str(item.get("figure_id") or ""):
                blockers.append(_finding("FIGURE_BODY_RECORD_INVALID", "figure body record is invalid"))
                continue
            figure_id = str(item["figure_id"])
            if SAFE_ARTIFACT_ID.fullmatch(figure_id) is None:
                blockers.append(_finding("FIGURE_ID_INVALID", f"unsafe figure ID {figure_id}"))
                continue
            if figure_id in body_figures:
                blockers.append(_finding("FIGURE_BODY_DUPLICATE", f"duplicate figure {figure_id}"))
            body_figures[figure_id] = dict(item)

    bindings_raw = spec.get("figure_bindings")
    bindings = bindings_raw if isinstance(bindings_raw, list) else []
    binding_by_figure = {
        str(item.get("figure_id")): item
        for item in bindings
        if isinstance(item, Mapping) and str(item.get("figure_id") or "")
    }
    if figure_mode == "none" and bindings:
        blockers.append(_finding("ZERO_FIGURE_BINDINGS_FORBIDDEN", "zero-figure tasks cannot carry figure bindings"))
    if figure_mode == "present" and set(binding_by_figure) != set(body_figures):
        blockers.append(_finding("FIGURE_BINDING_COVERAGE_MISMATCH", "bindings must cover every body-contract figure exactly"))

    reviewed_binding_ids = {str(item) for item in review.get("reviewed_binding_ids", [])}
    observed_binding_ids: set[str] = set()
    bound_reference_spans: set[tuple[int, int]] = set()
    figure_receipts: list[dict[str, Any]] = []
    manuscript = inputs.get("canonical_manuscript", {}).get("bytes", b"")
    for figure_id, figure in body_figures.items():
        binding = binding_by_figure.get(figure_id)
        if not isinstance(binding, Mapping):
            continue
        asset_id = str(binding.get("asset_artifact_id") or "")
        asset = inputs.get(asset_id)
        body_asset = figure.get("publication_asset")
        if asset is None or not isinstance(body_asset, Mapping) or body_asset.get("sha256") != asset["sha256"]:
            blockers.append(_finding("FIGURE_ASSET_STALE", f"{figure_id} final asset is absent or changed"))
        expected_panels = {
            str(item.get("panel_id"))
            for item in figure.get("panels", [])
            if isinstance(item, Mapping)
        }
        panel_bindings = binding.get("panels")
        panel_bindings = panel_bindings if isinstance(panel_bindings, list) else []
        observed_panels = {
            str(item.get("panel_id"))
            for item in panel_bindings
            if isinstance(item, Mapping)
        }
        if expected_panels != observed_panels or len(panel_bindings) != len(expected_panels):
            blockers.append(_finding("PANEL_BINDING_COVERAGE_MISMATCH", f"{figure_id} panels are not exactly covered"))
        normalized_panels: list[dict[str, Any]] = []
        for panel_index, panel in enumerate(panel_bindings):
            if not isinstance(panel, Mapping):
                blockers.append(_finding("PANEL_BINDING_INVALID", "panel binding must be an object"))
                continue
            binding_id = str(panel.get("binding_id") or "")
            if not binding_id or binding_id in observed_binding_ids:
                blockers.append(_finding("PANEL_BINDING_ID_INVALID", "binding IDs must be unique"))
            observed_binding_ids.add(binding_id)
            role = str(panel.get("argument_role") or "")
            if role not in ARGUMENT_ROLES:
                blockers.append(_finding("ARGUMENT_ROLE_INVALID", f"unsupported role {role}"))
            result_span = _verify_span(panel.get("result_span"), inputs, blockers, f"{figure_id}.panels[{panel_index}].result_span")
            argument_span = _verify_span(panel.get("argument_span"), inputs, blockers, f"{figure_id}.panels[{panel_index}].argument_span")
            evidence_span = _verify_span(panel.get("evidence_phrase_span"), inputs, blockers, f"{figure_id}.panels[{panel_index}].evidence_phrase_span")
            reference_span = _verify_span(panel.get("reference_span"), inputs, blockers, f"{figure_id}.panels[{panel_index}].reference_span")
            if result_span and inputs[result_span["artifact_id"]]["role"] != "exact_result":
                blockers.append(_finding("RESULT_SPAN_ROLE_INVALID", "result span must consume exact_result bytes"))
            for name, span in (("argument", argument_span), ("evidence", evidence_span), ("reference", reference_span)):
                if span and span["artifact_id"] != "canonical_manuscript":
                    blockers.append(_finding("MANUSCRIPT_SPAN_ARTIFACT_INVALID", f"{name} span must bind canonical manuscript"))
            if argument_span and evidence_span and not (
                argument_span["start_byte"] <= evidence_span["start_byte"] < evidence_span["end_byte"] <= argument_span["end_byte"]
            ):
                blockers.append(_finding("EVIDENCE_NOT_IN_ARGUMENT", "evidence phrase is outside the argument role span"))
            if argument_span and reference_span and not (
                argument_span["start_byte"] <= reference_span["start_byte"] < reference_span["end_byte"] <= argument_span["end_byte"]
            ):
                blockers.append(_finding("ARBITRARY_FIGURE_REFERENCE", "figure reference is outside the evidence-bearing argument span"))
            label = str(figure.get("label") or "")
            expected_refs = {
                f"\\ref{{{label}}}".encode(),
                f"\\autoref{{{label}}}".encode(),
                f"\\cref{{{label}}}".encode(),
                f"\\Cref{{{label}}}".encode(),
            }
            if reference_span:
                raw_reference = manuscript[reference_span["start_byte"] : reference_span["end_byte"]]
                if raw_reference not in expected_refs or not _reference_is_reader_body(
                    manuscript, reference_span["start_byte"], reference_span["end_byte"]
                ):
                    blockers.append(_finding("ARBITRARY_FIGURE_REFERENCE", "reference is not a reader-body reference to this figure"))
                else:
                    bound_reference_spans.add(
                        (reference_span["start_byte"], reference_span["end_byte"])
                    )
            normalized_panels.append(
                {
                    "binding_id": binding_id,
                    "panel_id": str(panel.get("panel_id") or ""),
                    "argument_role": role,
                    "result_span": result_span,
                    "argument_span": argument_span,
                    "evidence_phrase_span": evidence_span,
                    "reference_span": reference_span,
                }
            )
        receipt = {
            "contract": "paperspine5.figure-intent-receipt",
            "contract_version": CANONICAL_CONTRACT_VERSION,
            "subject": subject.as_dict(),
            "figure_id": figure_id,
            "figure_role": figure.get("figure_role"),
            "label": figure.get("label"),
            "body_contract_sha256": inputs.get("figure_body_contract", {}).get("sha256"),
            "final_asset": {
                "artifact_id": asset_id,
                "sha256": asset.get("sha256") if asset else None,
            },
            "panels": normalized_panels,
            "status": "PASS",
            "quality_claim": "byte/provenance binding only; scientific and visual quality require independent review",
            "external_action_authorized": False,
        }
        figure_receipts.append(_hashed(receipt, "receipt_sha256"))
    known_reference_bytes = {
        f"\\{command}{{{figure.get('label')}}}".encode()
        for figure in body_figures.values()
        for command in ("ref", "autoref", "cref", "Cref")
    }
    for match in REFERENCE_RE.finditer(manuscript):
        if (
            match.group(0) in known_reference_bytes
            and _reference_is_reader_body(manuscript, match.start(), match.end())
            and (match.start(), match.end()) not in bound_reference_spans
        ):
            blockers.append(
                _finding(
                    "UNBOUND_FIGURE_REFERENCE",
                    "reader-body figure reference lacks an exact result/argument-role binding",
                )
            )
    if observed_binding_ids != reviewed_binding_ids:
        blockers.append(
            _finding("PANEL_BINDINGS_NOT_INDEPENDENTLY_REVIEWED", "review must cover the exact current binding IDs")
        )

    claims_raw = spec.get("claims")
    claims = claims_raw if isinstance(claims_raw, list) else []
    claim_by_id = {
        str(item.get("claim_id")): item
        for item in claims
        if isinstance(item, Mapping) and str(item.get("claim_id") or "")
    }
    if set(claim_by_id) != set(scope_claims) or len(claims) != len(scope_claims):
        blockers.append(_finding("FINAL_CLAIM_SCOPE_MISMATCH", "FinalClaimIndex must cover the independent scope exactly"))
    normalized_claims: list[dict[str, Any]] = []
    reader_inventory: list[dict[str, Any]] = []
    retention_omission: list[dict[str, Any]] = []
    for claim_id, scope_claim in scope_claims.items():
        claim = claim_by_id.get(claim_id)
        if not isinstance(claim, Mapping):
            continue
        disposition = claim.get("disposition")
        source_span = _verify_span(claim.get("source_span"), inputs, blockers, f"claims.{claim_id}.source_span")
        if source_span and inputs[source_span["artifact_id"]]["role"] not in {
            "claim_graph",
            "source_claim",
            "exact_result",
        }:
            blockers.append(
                _finding(
                    "CLAIM_SOURCE_ROLE_INVALID",
                    f"{claim_id} source span must bind a claim graph, source claim, or exact result",
                )
            )
        surfaces_raw = claim.get("reader_surfaces")
        surfaces = surfaces_raw if isinstance(surfaces_raw, list) else []
        required_surfaces = set(scope_claim.get("required_surfaces", []))
        if disposition == "omitted":
            if scope_claim.get("omission_allowed") is not True or not str(claim.get("omission_reason") or "").strip():
                blockers.append(_finding("CLAIM_OMISSION_UNAUTHORIZED", f"{claim_id} omission lacks independent authority"))
            if surfaces:
                blockers.append(_finding("OMITTED_CLAIM_STILL_READER_FACING", f"{claim_id} is omitted but still mapped"))
        elif disposition == "retained":
            observed_surfaces = {
                str(item.get("surface"))
                for item in surfaces
                if isinstance(item, Mapping)
            }
            if not required_surfaces.issubset(observed_surfaces):
                blockers.append(
                    _finding("REQUIRED_READER_SURFACE_MISSING", f"{claim_id} lacks {sorted(required_surfaces - observed_surfaces)}")
                )
        else:
            blockers.append(_finding("CLAIM_DISPOSITION_INVALID", f"{claim_id} disposition is invalid"))
        normalized_surfaces: list[dict[str, Any]] = []
        for index, surface in enumerate(surfaces):
            if not isinstance(surface, Mapping) or surface.get("surface") not in READER_SURFACES:
                blockers.append(_finding("READER_SURFACE_INVALID", f"{claim_id} surface is invalid"))
                continue
            span = _verify_span(surface.get("span"), inputs, blockers, f"claims.{claim_id}.reader_surfaces[{index}]")
            if span:
                if span["artifact_id"] != "canonical_manuscript":
                    blockers.append(
                        _finding(
                            "READER_SURFACE_ARTIFACT_INVALID",
                            f"{claim_id} reader surface must bind canonical manuscript bytes",
                        )
                    )
                record = {"claim_id": claim_id, "surface": surface.get("surface"), "span": span}
                normalized_surfaces.append(record)
                reader_inventory.append(record)
        normalized_claims.append(
            {
                "claim_id": claim_id,
                "required": scope_claim.get("required") is True,
                "disposition": disposition,
                "source_span": source_span,
                "reader_surfaces": normalized_surfaces,
            }
        )
        retention_omission.append(
            {
                "claim_id": claim_id,
                "disposition": disposition,
                "omission_allowed": scope_claim.get("omission_allowed") is True,
                "omission_reason": claim.get("omission_reason") if disposition == "omitted" else None,
            }
        )

    extracted_raw = review.get("reader_claims")
    extracted = extracted_raw if isinstance(extracted_raw, list) else []
    expected_reader = {
        (item["claim_id"], item["surface"], *_span_key(item["span"]))
        for item in reader_inventory
    }
    observed_reader: set[tuple[Any, ...]] = set()
    for item in extracted:
        if not isinstance(item, Mapping):
            continue
        span = item.get("span")
        if isinstance(span, Mapping):
            observed_reader.add(
                (item.get("claim_id"), item.get("surface"), *_span_key(span))
            )
    if observed_reader != expected_reader or len(extracted) != len(expected_reader):
        blockers.append(
            _finding(
                "FINAL_READER_EXTRACTION_MISMATCH",
                "independent reverse extraction and producer index differ",
            )
        )

    final_claim_index = {
        "contract": "paperspine5.final-claim-index",
        "contract_version": CANONICAL_CONTRACT_VERSION,
        "subject": subject.as_dict(),
        "claim_scope_authority_sha256": scope_record["sha256"] if scope_record else None,
        "final_reader_review_sha256": review_record["sha256"] if review_record else None,
        "claims": normalized_claims,
        "reader_inventory": reader_inventory,
        "retention_omission": retention_omission,
        "status": "PASS",
        "quality_claim": "exact reverse mapping only; extractor independence/semantic accuracy require trusted review infrastructure",
        "external_action_authorized": False,
    }
    final_claim_index = _hashed(final_claim_index, "receipt_sha256")

    previous = dict(previous_input_hashes or {})
    changed = sorted(
        artifact_id
        for artifact_id in set(previous) | set(input_hashes)
        if previous.get(artifact_id) != input_hashes.get(artifact_id)
    )
    dependency_graph: dict[str, set[str]] = {
        "figure_intent_receipts": {"figure_body_contract", "canonical_manuscript"}
        | {artifact_id for artifact_id, record in inputs.items() if record["role"] in {"figure_asset", "exact_result"}},
        "final_claim_index": {"canonical_manuscript", "claim_graph", "claim_scope_authority", "final_reader_review"},
        "final_render": {
            artifact_id
            for artifact_id, record in inputs.items()
            if record["role"]
            in {"surface_receipt", "surface_page", "surface_source", "surface_review"}
        },
        "independent_review": {
            "canonical_manuscript",
            "figure_body_contract",
            "claim_graph",
            "final_reader_review",
        },
        "canonical_artifact_bundle": {"figure_intent_receipts", "final_claim_index", "final_render", "independent_review"},
    }
    invalidated = sorted(dependency_closure(dependency_graph, changed))

    status = "BLOCKED" if blockers else "PASS"
    if blockers:
        for receipt in figure_receipts:
            receipt["status"] = "BLOCKED"
            receipt["receipt_sha256"] = canonical_sha256(
                {key: value for key, value in receipt.items() if key != "receipt_sha256"}
            )
        final_claim_index["status"] = "BLOCKED"
        final_claim_index["receipt_sha256"] = canonical_sha256(
            {key: value for key, value in final_claim_index.items() if key != "receipt_sha256"}
        )

    bundle = {
        "contract": "paperspine5.canonical-artifact-bundle",
        "contract_version": CANONICAL_CONTRACT_VERSION,
        "subject": subject.as_dict(),
        "status": status,
        "blockers": blockers,
        "input_artifacts": {
            artifact_id: {
                "role": record["role"],
                "path": record["portable_path"],
                "sha256": record["sha256"],
                "size_bytes": record["size_bytes"],
            }
            for artifact_id, record in sorted(inputs.items())
        },
        "figure_intent_receipts": figure_receipts,
        "final_claim_index": final_claim_index,
        "surface_receipts": surface_receipts,
        "changed_artifact_ids": changed,
        "invalidated_artifacts": invalidated,
        "dependency_graph": {key: sorted(value) for key, value in dependency_graph.items()},
        "limitations": [
            "Byte/span/hash checks do not prove scientific truth or visual quality.",
            "Reviewer independence is structural until Kernel-issued identity attestations exist.",
            "PASS is W5 candidate evidence, not readiness, target-package readiness, M3, or external authorization.",
        ],
        "external_action_authorized": False,
    }
    return _hashed(bundle, "bundle_sha256")


def materialize_canonical_artifacts(
    bundle: Mapping[str, Any], output_dir: str | Path
) -> dict[str, str]:
    """Write derived receipts under the task run root for Kernel recording."""

    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for receipt in bundle.get("figure_intent_receipts", []):
        if not isinstance(receipt, Mapping):
            continue
        figure_id = str(receipt.get("figure_id") or "")
        path = output / f"figure-intent-{figure_id}.json"
        write_json_atomic(path, dict(receipt))
        paths[f"figure_intent:{figure_id}"] = str(path)
    claim_path = output / "final-claim-index.json"
    write_json_atomic(claim_path, dict(bundle.get("final_claim_index", {})))
    paths["final_claim_index"] = str(claim_path)
    bundle_path = output / "canonical-artifact-bundle.json"
    write_json_atomic(bundle_path, dict(bundle))
    paths["canonical_artifact_bundle"] = str(bundle_path)
    return paths


def _artifact_receipt(
    *,
    artifact_id: str,
    artifact_type: str,
    path: Path,
    subject: Mapping[str, Any],
    producer_id: str,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = path.read_bytes()
    payload_sha256 = _sha256_bytes(payload)
    return {
        "contract": "paperspine5.artifact-receipt",
        "schema_version": "1.0",
        "receipt_id": task_scoped_artifact_receipt_id(
            task_id=str(subject["task_id"]),
            revision_id=str(subject["revision_id"]),
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_sha256=payload_sha256,
        ),
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "path": str(path.resolve()),
        "sha256": payload_sha256,
        "size_bytes": len(payload),
        "subject": dict(subject),
        "authority": {"kind": "canonical.artifact-adapter", "producer_id": producer_id},
        "metadata": dict(metadata or {}),
        "external_action_authorized": False,
    }


def record_canonical_artifacts(
    kernel: Any,
    task_id: str,
    bundle: Mapping[str, Any],
    materialized_paths: Mapping[str, str],
    *,
    expected_revision: int,
    writer_id: str,
    command_prefix: str,
    producer_id: str = "canonical-artifact-adapter",
) -> dict[str, Any]:
    """Record raw and derived W5 artifacts without minting W4 authority.

    ``claim_scope_authority`` and ``final_reader_review`` must already be fresh
    in the Kernel ledger.  This is the executable W4→W5 boundary.
    """

    if bundle.get("status") != "PASS":
        raise ContractError("BLOCKED canonical bundle cannot be recorded as passing W5 evidence")
    subject = bundle.get("subject")
    if not isinstance(subject, Mapping) or str(subject.get("revision_id")) != str(expected_revision):
        raise ContractError("canonical bundle subject does not match expected revision")
    views = kernel.list_artifacts(task_id, subject_revision=expected_revision)
    fresh = {
        view["receipt"]["artifact_id"]: view
        for view in views
        if view.get("freshness") == "fresh"
    }
    input_artifacts = bundle.get("input_artifacts")
    if not isinstance(input_artifacts, Mapping):
        raise ContractError("canonical bundle input_artifacts is invalid")
    for artifact_id in REQUIRED_PREEXISTING_AUTHORITY_IDS:
        view = fresh.get(artifact_id)
        expected = subject["input_hashes"].get(artifact_id)
        if view is None or view["receipt"].get("sha256") != expected:
            raise ContractError(f"W4 authority artifact is not fresh in Kernel ledger: {artifact_id}")

    recorded: list[dict[str, Any]] = []
    sequence = 0
    for artifact_id, raw in sorted(input_artifacts.items()):
        if artifact_id in REQUIRED_PREEXISTING_AUTHORITY_IDS:
            continue
        if artifact_id in fresh and fresh[artifact_id]["receipt"].get("sha256") == raw.get("sha256"):
            continue
        path = Path(str(raw.get("path") or ""))
        task = kernel.get_task(task_id)
        path = (Path(task["run_root"]) / path).resolve()
        role = str(raw.get("role") or "")
        if role == "surface_page":
            artifact_type = "quality.surface-page"
        elif role == "surface_receipt":
            artifact_type = "quality.surface-receipt"
        else:
            artifact_type = "canonical.source-artifact"
        sequence += 1
        receipt = _artifact_receipt(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            path=path,
            subject=subject,
            producer_id=producer_id,
            metadata={"role": role},
        )
        recorded.append(
            kernel.record_artifact(
                task_id,
                receipt,
                expected_revision=expected_revision,
                command_id=f"{command_prefix}:input:{sequence}",
                writer_id=writer_id,
            )
        )

    derived_types = {
        "final_claim_index": "quality.final-claim-index",
        "canonical_artifact_bundle": "quality.canonical-artifact-bundle",
    }
    for artifact_id, raw_path in sorted(materialized_paths.items()):
        path = Path(raw_path).resolve()
        artifact_type = (
            "quality.figure-intent-receipt"
            if artifact_id.startswith("figure_intent:")
            else derived_types[artifact_id]
        )
        sequence += 1
        receipt = _artifact_receipt(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            path=path,
            subject=subject,
            producer_id=producer_id,
            metadata={
                "bundle_sha256": bundle.get("bundle_sha256"),
                "changed_artifact_ids": bundle.get("changed_artifact_ids", []),
                "invalidated_artifacts": bundle.get("invalidated_artifacts", []),
            },
        )
        recorded.append(
            kernel.record_artifact(
                task_id,
                receipt,
                expected_revision=expected_revision,
                command_id=f"{command_prefix}:derived:{sequence}",
                writer_id=writer_id,
            )
        )
    return {
        "contract": "paperspine5.canonical-artifact-ledger-result",
        "contract_version": CANONICAL_CONTRACT_VERSION,
        "task_id": task_id,
        "revision_id": str(expected_revision),
        "recorded_count": len(recorded),
        "changed_artifact_ids": list(bundle.get("changed_artifact_ids", [])),
        "invalidated_artifacts": list(bundle.get("invalidated_artifacts", [])),
        "external_action_authorized": False,
    }
