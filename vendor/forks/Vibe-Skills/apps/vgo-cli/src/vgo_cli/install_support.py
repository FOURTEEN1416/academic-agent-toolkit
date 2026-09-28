from __future__ import annotations

import os
from pathlib import Path

from .external import report_external_fallback_usage
from .install_gates import run_offline_gate, run_runtime_freshness_gate
from .installer_bridge import refresh_install_ledger_payload
from .repo import get_local_release_metadata, get_official_self_repo_metadata, get_repo_head_commit
from .skill_surface import quarantine_codex_duplicate_skill_surface
from .upgrade_state import load_upgrade_status, merge_upgrade_status, save_upgrade_status


def print_install_completion_report(
    frontend: str,
    *,
    host_id: str,
    profile: str,
    target_root: Path,
    install_receipt: dict[str, object],
) -> None:
    host_runtime = install_receipt.get('host_runtime') if isinstance(install_receipt, dict) else {}
    vibe_host_ready = 'unknown'
    if isinstance(host_runtime, dict) and 'vibe_host_ready' in host_runtime:
        vibe_host_ready = bool(host_runtime.get('vibe_host_ready'))
    print('')
    print('Install completion summary')
    print(f'- host: {host_id}')
    print(f'- profile: {profile}')
    print(f'- target_root: {target_root}')
    if isinstance(install_receipt, dict):
        runtime_root = install_receipt.get('runtime_root')
        bridge_root = install_receipt.get('host_bridge_root')
        layout_mode = install_receipt.get('runtime_layout_mode')
        if runtime_root:
            print(f'- runtime_root: {runtime_root}')
        if bridge_root:
            print(f'- host_bridge_root: {bridge_root}')
        if layout_mode:
            print(f'- runtime_layout_mode: {layout_mode}')
    print('- installed_locally: True')
    print(f'- vibe_host_ready: {vibe_host_ready}')
    print('- completed_parts: runtime payload installed; post-install gates reconciled')
    print(f'- online_ready: verify separately with the router connectivity probe for {target_root}')
    print('- manual_follow_up: none')


def reconcile_install_postconditions(
    repo_root: Path,
    target_root: Path,
    host_id: str,
    *,
    profile: str,
    install_external: bool,
    frontend: str,
    external_fallback_used: list[str],
    strict_offline: bool,
    skip_runtime_freshness_gate: bool,
    include_frontmatter: bool,
) -> dict[str, object]:
    if strict_offline:
        run_offline_gate(repo_root, target_root)
    report_external_fallback_usage(external_fallback_used, strict_offline=strict_offline)
    quarantine_codex_duplicate_skill_surface(target_root, host_id)
    run_runtime_freshness_gate(
        repo_root,
        target_root,
        skip_gate=skip_runtime_freshness_gate,
        include_frontmatter=include_frontmatter,
    )
    official_repo = get_official_self_repo_metadata(repo_root)
    release = get_local_release_metadata(repo_root)
    save_upgrade_status(
        target_root,
        merge_upgrade_status(
            load_upgrade_status(target_root),
            installed={
                'host_id': host_id,
                'target_root': target_root,
                'repo_remote': official_repo.get('repo_url'),
                'repo_default_branch': official_repo.get('default_branch'),
                'installed_version': release.get('version'),
                'installed_commit': get_repo_head_commit(repo_root),
                'installed_recorded_at': None,
            },
        ),
    )
    install_receipt = refresh_install_ledger_payload(repo_root, target_root)
    if os.environ.get('VGO_SUPPRESS_INSTALL_COMPLETION_REPORT', '').strip() != '1':
        print_install_completion_report(
            frontend,
            host_id=host_id,
            profile=profile,
            target_root=target_root,
            install_receipt=install_receipt,
        )
    return {
        'install_receipt': install_receipt,
    }
