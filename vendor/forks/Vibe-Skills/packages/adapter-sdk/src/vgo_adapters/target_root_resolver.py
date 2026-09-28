from vgo_contracts.target_root_contract import resolve_target_root_text


def resolve_default_target_root(descriptor, *, env: dict[str, str] | None = None, home: str | None = None) -> str:
    return resolve_target_root_text(
        default_target_root=getattr(descriptor, "default_target_root", ""),
        default_target_root_env=getattr(descriptor, "default_target_root_env", ""),
        env=env,
        home=home,
        descriptor_id=getattr(descriptor, "id", "adapter"),
    )
