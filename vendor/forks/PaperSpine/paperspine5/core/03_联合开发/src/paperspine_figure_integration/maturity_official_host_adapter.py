"""Executable Codex app-server adapter for PS-GAP-014 public-entry runs.

Official use always spawns the hash-bound ``codex app-server --stdio`` binary.
An injected transport exists only for unit tests; its receipt is permanently
marked test-only and is ineligible for the official controller.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import queue
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


MAX_TRANSCRIPT_BYTES = 2 * 1024 * 1024
MAX_STDERR_BYTES = 256 * 1024
CANONICAL_ARGV_SUFFIX = ("app-server", "--stdio")
ENV_ALLOWLIST = (
    "APPDATA",
    "COMSPEC",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SystemRoot",
    "TEMP",
    "TMP",
    "WINDIR",
)


class AppServerProtocolError(RuntimeError):
    """Raised when the executable, protocol transcript or selected Skill drifts."""


class AppServerTransport(Protocol):
    pid: int

    def send(self, message: dict[str, Any]) -> None: ...

    def receive(self, timeout_seconds: float) -> dict[str, Any]: ...

    def close(self) -> int: ...

    def stderr_bytes(self) -> bytes: ...


def canonical_sha256(value: Any, *, self_hash: str | None = None) -> str:
    subject = copy.deepcopy(value)
    if self_hash and isinstance(subject, dict):
        subject.pop(self_hash, None)
    data = (
        json.dumps(subject, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise AppServerProtocolError(f"adapter output collision: {path}")
    stage = path.with_name(f".{path.name}.stage")
    if stage.exists():
        raise AppServerProtocolError(f"adapter stage collision: {stage}")
    owned = False
    try:
        encoded = (
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        with stage.open("xb") as handle:
            owned = True
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, path)
    except Exception:
        if owned and stage.exists():
            stage.unlink()
        raise


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise AppServerProtocolError(f"adapter output collision: {path}")
    stage = path.with_name(f".{path.name}.stage")
    if stage.exists():
        raise AppServerProtocolError(f"adapter stage collision: {stage}")
    owned = False
    try:
        with stage.open("xb") as handle:
            owned = True
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, path)
    except Exception:
        if owned and stage.exists():
            stage.unlink()
        raise


def _read_json(path: str | Path, label: str) -> dict[str, Any]:
    target = Path(path).resolve()
    if not target.is_file():
        raise AppServerProtocolError(f"{label} is missing")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AppServerProtocolError(f"{label} is not UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise AppServerProtocolError(f"{label} must be an object")
    return value


def _request_template(request: dict[str, Any]) -> list[dict[str, Any]]:
    prompt_path = Path(request["prompt_path"]).resolve()
    if not prompt_path.is_file() or file_sha256(prompt_path) != request["prompt_sha256"]:
        raise AppServerProtocolError("public-entry prompt bytes/hash drift")
    prompt = prompt_path.read_text(encoding="utf-8")
    if request["entry_mode"] == "natural_language":
        if "paper-spine" in prompt.lower():
            raise AppServerProtocolError("natural-language public entry names the Skill")
        inputs: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    elif request["entry_mode"] == "explicit_paper_spine":
        if not prompt.startswith("$paper-spine "):
            raise AppServerProtocolError("explicit public entry must start with $paper-spine")
        inputs = [
            {"type": "skill", "name": "paper-spine", "path": "$SKILL_PATH"},
            {"type": "text", "text": prompt},
        ]
    else:
        raise AppServerProtocolError("public-entry mode is not registered")
    cwd = str(Path(request["cwd"]).resolve())
    runtime_roots = [str(Path(item).resolve()) for item in request["runtime_workspace_roots"]]
    return [
        {
            "id": "initialize",
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "paperspine5-maturity-official-host-adapter",
                    "title": "PaperSpine maturity official host adapter",
                    "version": "2.0",
                }
            },
        },
        {
            "id": "skills-list",
            "method": "skills/list",
            "params": {"cwds": [cwd], "forceReload": True},
        },
        {
            "id": "thread-start",
            "method": "thread/start",
            "params": {
                "cwd": cwd,
                "runtimeWorkspaceRoots": runtime_roots,
                "ephemeral": True,
                "approvalPolicy": "never",
                "sandbox": "workspace-write",
                "threadSource": "paperspine5-maturity-official-run",
            },
        },
        {
            "id": "turn-start",
            "method": "turn/start",
            "params": {
                "threadId": "$THREAD_ID",
                "cwd": cwd,
                "runtimeWorkspaceRoots": runtime_roots,
                "approvalPolicy": "never",
                "input": inputs,
            },
        },
    ]


def build_app_server_requests(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the exact request sequence with typed runtime placeholders."""

    return _request_template(request)


def _response_for(
    transcript: list[dict[str, Any]], request_id: str
) -> dict[str, Any]:
    matches = [
        entry["message"]
        for entry in transcript
        if entry.get("direction") == "received"
        and isinstance(entry.get("message"), dict)
        and entry["message"].get("id") == request_id
    ]
    if len(matches) != 1 or "result" not in matches[0] or "error" in matches[0]:
        raise AppServerProtocolError(f"app-server response is missing/failed: {request_id}")
    return matches[0]["result"]


def _skill_selection(skills_result: dict[str, Any]) -> dict[str, str]:
    rows = skills_result.get("data")
    if not isinstance(rows, list) or len(rows) != 1:
        raise AppServerProtocolError("skills/list did not return one cwd entry")
    skills = rows[0].get("skills")
    if not isinstance(skills, list):
        raise AppServerProtocolError("skills/list payload is malformed")
    relevant = [
        item
        for item in skills
        if str(item.get("name", "")).lower()
        in {"paper-spine", "paperfig", "paperspine5-workspace"}
        and item.get("enabled") is True
    ]
    canonical = [item for item in relevant if item.get("name") == "paper-spine"]
    competitors = [item for item in relevant if item.get("name") != "paper-spine"]
    if len(canonical) != 1 or competitors:
        raise AppServerProtocolError("clean-profile suite discovery is not 1/0/0")
    return {"name": "paper-spine", "path": str(Path(canonical[0]["path"]).resolve())}


def validate_app_server_transcript(
    transcript: list[dict[str, Any]], *, expected_request: dict[str, Any]
) -> dict[str, Any]:
    if not transcript:
        raise AppServerProtocolError("app-server transcript is empty")
    encoded = (
        json.dumps(transcript, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    if len(encoded) > MAX_TRANSCRIPT_BYTES:
        raise AppServerProtocolError("app-server transcript exceeds the hard cap")
    sent = [
        entry["message"]
        for entry in transcript
        if entry.get("direction") == "sent" and isinstance(entry.get("message"), dict)
    ]
    expected = _request_template(expected_request)
    methods = [item.get("method") for item in sent if "id" in item]
    if methods != ["initialize", "skills/list", "thread/start", "turn/start"] or len(sent) != 4:
        raise AppServerProtocolError("app-server request sequence drift")
    if sent[:3] != expected[:3]:
        raise AppServerProtocolError("app-server initialize/skills/thread request bytes drift")
    skills = _skill_selection(_response_for(transcript, "skills-list"))
    thread_result = _response_for(transcript, "thread-start")
    thread_id = ((thread_result.get("thread") or {}).get("id"))
    if not isinstance(thread_id, str) or not thread_id:
        raise AppServerProtocolError("thread/start did not return a thread identity")
    turn_request = next(item for item in sent if item.get("id") == "turn-start")
    if turn_request.get("params", {}).get("threadId") != thread_id:
        raise AppServerProtocolError("turn/start thread identity drift")
    turn_result = _response_for(transcript, "turn-start")
    turn_id = ((turn_result.get("turn") or {}).get("id"))
    if not isinstance(turn_id, str) or not turn_id:
        raise AppServerProtocolError("turn/start did not return a turn identity")
    expected_turn = copy.deepcopy(expected[3])
    expected_turn["params"]["threadId"] = thread_id
    for user_input in expected_turn["params"]["input"]:
        if user_input.get("type") == "skill":
            user_input["path"] = skills["path"]
    if turn_request != expected_turn:
        raise AppServerProtocolError("turn/start input/cwd/runtime-root bytes drift")
    completed = [
        entry["message"].get("params")
        for entry in transcript
        if entry.get("direction") == "received"
        and isinstance(entry.get("message"), dict)
        and entry["message"].get("method") == "turn/completed"
    ]
    if len(completed) != 1:
        raise AppServerProtocolError("turn/completed notification is missing/duplicate")
    final_turn = completed[0].get("turn") or {}
    if (
        completed[0].get("threadId") != thread_id
        or final_turn.get("id") != turn_id
        or final_turn.get("status") != "completed"
    ):
        raise AppServerProtocolError("app-server turn did not complete on the bound thread")
    return {
        "run_id": expected_request["run_id"],
        "thread_id": thread_id,
        "turn_id": turn_id,
        "selected_skill": skills,
        "transcript_sha256": canonical_sha256(transcript),
    }


def _process_snapshot_windows() -> list[dict[str, Any]]:
    """Return non-secret process identity needed to prove owned-tree cleanup."""

    powershell = _resolve_windows_powershell()
    script = (
        "$ErrorActionPreference='Stop';"
        "@(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,"
        "ExecutablePath,CommandLine,CreationDate) | ConvertTo-Json -Compress -Depth 3"
    )
    completed = subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise AppServerProtocolError("owned process-tree observation is unavailable")
    try:
        raw = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise AppServerProtocolError("owned process-tree observation is not JSON") from exc
    rows = raw if isinstance(raw, list) else [raw]
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "pid": int(row.get("ProcessId") or 0),
                "parent_pid": int(row.get("ParentProcessId") or 0),
                "executable_path": str(row.get("ExecutablePath") or ""),
                "command_line": str(row.get("CommandLine") or ""),
                "creation_date": str(row.get("CreationDate") or ""),
            }
        )
    return normalized


def _resolve_windows_powershell(
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Resolve Windows PowerShell only from the authoritative Windows root.

    ``SystemRoot`` is primary and ``WINDIR`` is an equivalent fallback only
    when ``SystemRoot`` is absent.  When both exist they must identify the same
    absolute root.  No PATH, COMSPEC, current-directory, or drive-literal
    fallback is permitted for the process-audit authority.
    """

    values = os.environ if environment is None else environment
    system_root_raw = values.get("SystemRoot")
    windir_raw = values.get("WINDIR")
    if system_root_raw is not None and not system_root_raw.strip():
        raise AppServerProtocolError("SystemRoot is empty")
    if windir_raw is not None and not windir_raw.strip():
        raise AppServerProtocolError("WINDIR is empty")
    if system_root_raw is None and windir_raw is None:
        raise AppServerProtocolError("Windows root environment is unavailable")

    roots = [
        (name, Path(raw.strip()))
        for name, raw in (("SystemRoot", system_root_raw), ("WINDIR", windir_raw))
        if raw is not None
    ]
    for name, root in roots:
        if not root.is_absolute():
            raise AppServerProtocolError(f"{name} must be an absolute path")
    if len(roots) == 2 and roots[0][1].resolve() != roots[1][1].resolve():
        raise AppServerProtocolError("SystemRoot and WINDIR disagree")

    root = roots[0][1]
    target = (
        root
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    if not target.is_file():
        raise AppServerProtocolError("Windows PowerShell executable is unavailable")
    return target.resolve()


def _owned_process_tree(rows: list[dict[str, Any]], root_pid: int) -> list[dict[str, Any]]:
    by_parent: dict[int, list[dict[str, Any]]] = {}
    by_pid = {int(row["pid"]): row for row in rows}
    for row in rows:
        by_parent.setdefault(int(row["parent_pid"]), []).append(row)
    if root_pid not in by_pid:
        return []
    owned = []
    pending = [root_pid]
    seen: set[int] = set()
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        row = by_pid.get(pid)
        if row is not None:
            owned.append(copy.deepcopy(row))
        pending.extend(int(child["pid"]) for child in by_parent.get(pid, []))
    return sorted(owned, key=lambda item: int(item["pid"]))


def _same_process_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(
        left.get(key) == right.get(key)
        for key in ("pid", "creation_date", "executable_path", "command_line")
    )


def _surviving_owned_processes(
    owned_pre: list[dict[str, Any]], rows_post: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return exact pre-close identities still alive, even if they were reparented."""

    post_by_pid = {int(item["pid"]): item for item in rows_post}
    return sorted(
        [
            copy.deepcopy(item)
            for item in owned_pre
            if int(item["pid"]) in post_by_pid
            and _same_process_identity(item, post_by_pid[int(item["pid"])])
        ],
        key=lambda item: int(item["pid"]),
    )


class _SubprocessTransport:
    def __init__(
        self, executable: Path, *, env: dict[str, str], cwd: Path
    ) -> None:
        self._process = subprocess.Popen(
            [str(executable), *CANONICAL_ARGV_SUFFIX],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
            cwd=str(cwd),
            env=env,
            bufsize=1,
        )
        self.pid = self._process.pid
        self._stdout: queue.Queue[str | BaseException] = queue.Queue()
        self._stderr = bytearray()
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                self._stdout.put(line)
        except BaseException as exc:  # pragma: no cover - OS pipe failure
            self._stdout.put(exc)

    def _read_stderr(self) -> None:
        assert self._process.stderr is not None
        data = self._process.stderr.buffer.read(MAX_STDERR_BYTES + 1)
        self._stderr.extend(data)

    def send(self, message: dict[str, Any]) -> None:
        if self._process.poll() is not None:
            raise AppServerProtocolError("app-server exited before request dispatch")
        assert self._process.stdin is not None
        self._process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def receive(self, timeout_seconds: float) -> dict[str, Any]:
        try:
            item = self._stdout.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise AppServerProtocolError("app-server response timed out") from exc
        if isinstance(item, BaseException):
            raise AppServerProtocolError("app-server stdout failed") from item
        try:
            value = json.loads(item)
        except json.JSONDecodeError as exc:
            raise AppServerProtocolError("app-server emitted non-JSON stdout") from exc
        if not isinstance(value, dict):
            raise AppServerProtocolError("app-server emitted non-object JSON")
        return value

    def close(self) -> int:
        if self._process.stdin is not None:
            self._process.stdin.close()
        try:
            return self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                return self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                return self._process.wait(timeout=5)

    def stderr_bytes(self) -> bytes:
        return bytes(self._stderr)


def _bounded_env(request: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    env = {name: os.environ[name] for name in ENV_ALLOWLIST if name in os.environ}
    env["CODEX_HOME"] = str(Path(request["profile_root"]).resolve())
    env["PAPERSPINE5_USER_DATA_ROOT"] = str(Path(request["user_data_root"]).resolve())
    user_home = str(Path(request["user_home_root"]).resolve())
    env["HOME"] = user_home
    env["USERPROFILE"] = user_home
    drive, tail = os.path.splitdrive(user_home)
    if drive:
        env["HOMEDRIVE"] = drive
        env["HOMEPATH"] = tail
    hashes = {
        name: hashlib.sha256(value.encode("utf-8")).hexdigest()
        for name, value in sorted(env.items())
    }
    return env, hashes


def execute_host_entry(
    request_path: str | Path,
    receipt_path: str | Path,
    *,
    transport_factory: Callable[[Path, dict[str, str], Path], AppServerTransport]
    | None = None,
    process_observer: Callable[[], list[dict[str, Any]]] | None = None,
    test_mode: bool = False,
    timeout_seconds: float = 600.0,
    cleanup_timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    request_file = Path(request_path).resolve()
    request = _read_json(request_file, "host adapter request")
    if request.get("request_sha256") != canonical_sha256(
        request, self_hash="request_sha256"
    ):
        raise AppServerProtocolError("host adapter request self-hash drift")
    executable = Path(request["codex_executable"]).resolve()
    if not executable.is_file() or file_sha256(executable) != request["codex_executable_sha256"]:
        raise AppServerProtocolError("Codex executable path/hash drift")
    if (transport_factory is not None or process_observer is not None) and not test_mode:
        raise AppServerProtocolError("injected transport is forbidden in official mode")
    env, env_hashes = _bounded_env(request)
    cwd = Path(request["cwd"]).resolve()
    factory = transport_factory or (
        lambda exe, values, workdir: _SubprocessTransport(exe, env=values, cwd=workdir)
    )
    observer = process_observer or _process_snapshot_windows
    started_at = datetime.now().astimezone()
    transport = factory(executable, env, cwd)
    templates = _request_template(request)
    transcript: list[dict[str, Any]] = []
    started = time.monotonic()

    def record(direction: str, message: dict[str, Any]) -> None:
        transcript.append({"direction": direction, "message": copy.deepcopy(message)})
        if len(json.dumps(transcript, ensure_ascii=False).encode("utf-8")) > MAX_TRANSCRIPT_BYTES:
            raise AppServerProtocolError("app-server transcript exceeded the hard cap")

    def send(message: dict[str, Any]) -> None:
        transport.send(message)
        record("sent", message)

    def receive_until(predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        while True:
            remaining = timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise AppServerProtocolError("app-server official entry timed out")
            message = transport.receive(remaining)
            record("received", message)
            if predicate(message):
                return message

    exit_code: int | None = None
    owned_pre: list[dict[str, Any]] = []
    process_post: list[dict[str, Any]] = []
    owned_post: list[dict[str, Any]] = []
    validated: dict[str, Any] | None = None
    failure: BaseException | None = None
    try:
        send(templates[0])
        receive_until(lambda item: item.get("id") == "initialize")
        initialized = {"method": "initialized"}
        transport.send(initialized)
        # Initialization notification is protocol setup, not one of the four requests.
        record("sent_notification", initialized)
        send(templates[1])
        skills_response = receive_until(lambda item: item.get("id") == "skills-list")
        skills = _skill_selection(skills_response.get("result") or {})
        expected_skill_root = Path(request["expected_skill_root"]).resolve()
        if Path(skills["path"]).resolve() != expected_skill_root / "SKILL.md":
            raise AppServerProtocolError("skills/list selected a non-candidate canonical Skill")
        send(templates[2])
        thread_response = receive_until(lambda item: item.get("id") == "thread-start")
        thread_id = (((thread_response.get("result") or {}).get("thread") or {}).get("id"))
        if not thread_id:
            raise AppServerProtocolError("thread/start returned no thread id")
        turn = copy.deepcopy(templates[3])
        turn["params"]["threadId"] = thread_id
        for user_input in turn["params"]["input"]:
            if user_input.get("type") == "skill":
                user_input["path"] = skills["path"]
        send(turn)
        receive_until(lambda item: item.get("id") == "turn-start")
        receive_until(lambda item: item.get("method") == "turn/completed")
        validated = validate_app_server_transcript(
            transcript, expected_request=request
        )
        process_pre = observer()
        owned_pre = _owned_process_tree(process_pre, transport.pid)
        if not owned_pre or owned_pre[0]["pid"] != transport.pid:
            raise AppServerProtocolError("owned app-server process was not observable")
    except BaseException as exc:
        failure = exc
    finally:
        try:
            exit_code = transport.close()
        except BaseException as exc:
            if failure is None:
                failure = exc
    deadline = time.monotonic() + cleanup_timeout_seconds
    try:
        process_post = observer()
    except BaseException as exc:
        failure = failure or exc
        process_post = []
    owned_post = _surviving_owned_processes(owned_pre, process_post)
    while owned_post and time.monotonic() < deadline:
        time.sleep(0.1)
        try:
            process_post = observer()
        except BaseException as exc:
            failure = failure or exc
            break
        owned_post = _surviving_owned_processes(owned_pre, process_post)
    if owned_post:
        failure = failure or AppServerProtocolError(
            "owned app-server/PaperSpine process identities did not exit"
        )
    completed_at = datetime.now().astimezone()
    stderr = transport.stderr_bytes()
    if len(stderr) > MAX_STDERR_BYTES:
        failure = failure or AppServerProtocolError(
            "app-server stderr exceeded the hard cap"
        )
    transcript_path = Path(receipt_path).resolve().with_suffix(".events.json")
    _write_json(transcript_path, {"events": transcript})
    process_tree_path = Path(receipt_path).resolve().with_suffix(".process-tree.json")
    process_tree = {
        "root_pid": transport.pid,
        "owned_pre_close": owned_pre,
        "owned_post_close": owned_post,
        "post_snapshot_sha256": canonical_sha256(process_post),
    }
    _write_json(process_tree_path, process_tree)
    stderr_path = Path(receipt_path).resolve().with_suffix(".stderr.log")
    _write_bytes(stderr_path, stderr)
    receipt = {
        "contract": "paperspine5.public-host-entry-receipt-v2",
        "contract_version": "2.0",
        "run_id": request["run_id"],
        "adapter_path": str(Path(__file__).resolve()),
        "adapter_sha256": file_sha256(Path(__file__).resolve()),
        "codex_executable": str(executable),
        "codex_executable_sha256": request["codex_executable_sha256"],
        "argv": [str(executable), *CANONICAL_ARGV_SUFFIX],
        "environment_keys": sorted(env_hashes),
        "environment_value_sha256": env_hashes,
        "profile_root": str(Path(request["profile_root"]).resolve()),
        "request_path": str(request_file),
        "request_file_sha256": file_sha256(request_file),
        "pid": transport.pid,
        "exit_code": exit_code,
        "started_at": started_at.isoformat(timespec="milliseconds"),
        "completed_at": completed_at.isoformat(timespec="milliseconds"),
        "thread_id": validated["thread_id"] if validated else None,
        "turn_id": validated["turn_id"] if validated else None,
        "selected_skill": validated["selected_skill"] if validated else None,
        "transcript_path": str(transcript_path),
        "transcript_file_sha256": file_sha256(transcript_path),
        "process_tree_path": str(process_tree_path),
        "process_tree_file_sha256": file_sha256(process_tree_path),
        "owned_process_count_pre_close": len(owned_pre),
        "owned_process_count_post_close": len(owned_post),
        "stderr_path": str(stderr_path),
        "stderr_file_sha256": file_sha256(stderr_path),
        "test_only": test_mode,
        "external_action_authorized": False,
        "status": "completed"
        if failure is None and exit_code == 0 and not owned_post
        else "blocked",
        "error": None
        if failure is None
        else {
            "code": "PUBLIC_HOST_ENTRY_BLOCKED",
            "type": type(failure).__name__,
            "message": str(failure),
        },
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    _write_json(Path(receipt_path).resolve(), receipt)
    if failure is not None:
        if isinstance(failure, AppServerProtocolError):
            raise failure
        raise AppServerProtocolError(
            f"public host adapter failed: {type(failure).__name__}: {failure}"
        ) from failure
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    args = parser.parse_args(argv)
    execute_host_entry(
        args.request, args.receipt, timeout_seconds=args.timeout_seconds
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
