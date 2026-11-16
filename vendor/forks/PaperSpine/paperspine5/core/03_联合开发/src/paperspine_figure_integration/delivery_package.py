"""Safe local delivery-package assembly for PaperSpine.

This module is deliberately pure: it never uploads, publishes, or changes task state.
The caller supplies already-authoritative fresh artifact receipts and a byte reader.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from collections.abc import Callable, Iterable, Mapping

_MAX_FILE = 128 * 1024 * 1024
_MAX_TOTAL = 512 * 1024 * 1024
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

def assemble_delivery_package(
    artifacts: Iterable[Mapping[str, object]],
    read_bytes: Callable[[str], bytes],
    *,
    required_types: set[str] | None = None,
) -> tuple[bytes, dict[str, object]]:
    """Build a deterministic ZIP from fresh receipts, or raise ValueError.

    Only fresh receipts are accepted; receipt sha256 and size are rechecked against
    bytes read by the host.  This is a local preparation operation, not readiness
    approval or external submission.
    """
    required = set(required_types or ())
    selected: list[tuple[str, bytes, Mapping[str, object]]] = []
    seen: set[str] = set()
    total = 0
    for receipt in artifacts:
        if not isinstance(receipt, Mapping) or receipt.get("freshness", "fresh") != "fresh":
            continue
        r = receipt.get("receipt") if isinstance(receipt.get("receipt"), Mapping) else receipt
        aid, typ = r.get("artifact_id"), r.get("artifact_type")
        if not isinstance(aid, str) or not isinstance(typ, str) or typ == "paper.delivery-package":
            continue
        name = r.get("filename") or f"{aid}.bin"
        if not isinstance(name, str) or "/" in name or "\\" in name or not _NAME.fullmatch(name):
            raise ValueError("artifact filename is unsafe")
        if name in seen:
            raise ValueError("duplicate artifact filename")
        digest, size = r.get("sha256"), r.get("size_bytes")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or type(size) is not int or size < 0 or size > _MAX_FILE:
            raise ValueError("artifact receipt byte binding is invalid")
        body = read_bytes(str(aid))
        if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("artifact bytes do not match receipt")
        total += len(body)
        if total > _MAX_TOTAL:
            raise ValueError("delivery package is too large")
        seen.add(name); selected.append((name, body, r))
        required.discard(str(typ).removeprefix("paper."))
    if required:
        raise ValueError(f"required artifact types missing: {sorted(required)}")
    if not selected:
        raise ValueError("no fresh artifacts available for local package")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, body, _ in sorted(selected):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, body)
    package = output.getvalue()
    manifest = {"contract": "paperspine5.local-delivery-package", "status": "prepared",
                "artifact_count": len(selected), "sha256": hashlib.sha256(package).hexdigest(),
                "size_bytes": len(package), "external_action_authorized": False,
                "submission_ready": False}
    return package, manifest
