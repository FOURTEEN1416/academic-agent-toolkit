from __future__ import annotations

from dataclasses import dataclass, asdict

from .workspace_memory_schema import build_workspace_memory_schema


@dataclass(frozen=True, slots=True)
class RuntimeMemoryPolicy:
    backend: str
    enabled: bool
    stage_count: int
    workspace_identity_root: str
    shared_memory_driver_contract: str
    logical_memory_owners: tuple[str, ...]

    def model_dump(self) -> dict[str, object]:
        payload = asdict(self)
        payload['logical_memory_owners'] = list(self.logical_memory_owners)
        return payload


def build_memory_policy(stage_count: int) -> RuntimeMemoryPolicy:
    workspace_schema = build_workspace_memory_schema()
    return RuntimeMemoryPolicy(
        backend='runtime-neutral',
        enabled=False,
        stage_count=stage_count,
        workspace_identity_root=workspace_schema.identity_root,
        shared_memory_driver_contract=workspace_schema.driver_contract,
        logical_memory_owners=workspace_schema.logical_owners,
    )
