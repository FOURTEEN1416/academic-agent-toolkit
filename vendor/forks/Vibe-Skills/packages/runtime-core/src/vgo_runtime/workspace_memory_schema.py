from __future__ import annotations

from dataclasses import asdict, dataclass


WORKSPACE_MEMORY_IDENTITY_ROOT = '.vibeskills/project.json'
WORKSPACE_MEMORY_IDENTITY_SCOPE = 'workspace'
WORKSPACE_MEMORY_DRIVER_CONTRACT = 'workspace_shared_memory_v1'
WORKSPACE_MEMORY_LOGICAL_OWNERS = ('state_store', 'serena', 'ruflo', 'cognee')


@dataclass(frozen=True, slots=True)
class WorkspaceMemorySchema:
    schema_version: int
    identity_root: str
    identity_scope: str
    driver_contract: str
    logical_owners: tuple[str, ...]

    def model_dump(self) -> dict[str, object]:
        payload = asdict(self)
        payload['logical_owners'] = list(self.logical_owners)
        return payload


def build_workspace_memory_schema() -> WorkspaceMemorySchema:
    return WorkspaceMemorySchema(
        schema_version=1,
        identity_root=WORKSPACE_MEMORY_IDENTITY_ROOT,
        identity_scope=WORKSPACE_MEMORY_IDENTITY_SCOPE,
        driver_contract=WORKSPACE_MEMORY_DRIVER_CONTRACT,
        logical_owners=WORKSPACE_MEMORY_LOGICAL_OWNERS,
    )
