from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from .workspace_memory_schema import (
    WORKSPACE_MEMORY_DRIVER_CONTRACT,
    WORKSPACE_MEMORY_IDENTITY_ROOT,
    WORKSPACE_MEMORY_IDENTITY_SCOPE,
)


def _normalize_identity_input(value: str) -> str:
    return value.replace('\\', '/').rstrip('/').lower()


@dataclass(frozen=True, slots=True)
class WorkspaceMemoryIdentity:
    workspace_id: str
    workspace_root: str
    identity_root: str
    identity_scope: str
    driver_contract: str

    def model_dump(self) -> dict[str, object]:
        return asdict(self)


def build_workspace_memory_identity(
    workspace_root: str | Path,
    *,
    host_id: str | None = None,
) -> WorkspaceMemoryIdentity:
    del host_id
    workspace_root_path = Path(workspace_root).resolve()
    identity_root_path = (workspace_root_path / WORKSPACE_MEMORY_IDENTITY_ROOT).resolve()
    identity_key = _normalize_identity_input(str(identity_root_path))
    workspace_id = f"ws:{sha256(identity_key.encode('utf-8')).hexdigest()[:24]}"

    return WorkspaceMemoryIdentity(
        workspace_id=workspace_id,
        workspace_root=str(workspace_root_path),
        identity_root=str(identity_root_path),
        identity_scope=WORKSPACE_MEMORY_IDENTITY_SCOPE,
        driver_contract=WORKSPACE_MEMORY_DRIVER_CONTRACT,
    )
