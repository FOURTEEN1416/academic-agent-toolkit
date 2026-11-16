"""Reuse Kernel material capabilities and Runner file ingestion, without stages."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from .product_kernel import ContractError, _build_material_grant, _validate_grant_root
from .product_runner import ProductRunner


class HostMaterialFiles:
    # These routines only enumerate/copy authorized files; no Runner is bootstrapped.
    _scan_materials = ProductRunner._scan_materials
    _ingest_object = ProductRunner._ingest_object
    _file_digest = staticmethod(ProductRunner._file_digest)

    def __init__(self, kernel):
        self.kernel = kernel
        self.expected_build_id = kernel.product_manifest['build_id']
        self.max_files = 4096
        self.max_total_bytes = 512 * 1024 * 1024
        self.registration = kernel.register_command_handler(
            'host.materials.authorize', handler_id='p1-material-files',
            product_build_id=self.expected_build_id, handler=self._accept)

    def _accept(self, task, command, prepared):
        grants = self.kernel._validate_material_grants(prepared['grants'])
        state = dict(task['state'])
        state['host_material_inventory'] = prepared['inventory']
        state['host_material_selection'] = prepared['selection']
        return {'state': state, 'material_grants': grants,
                'status': 'active' if task['status'] == 'completed' else task['status'],
                'result': {}, 'event_payload': {'material_snapshot_sha256': prepared['inventory']['snapshot_sha256']}}

    def authorize(self, command):
        task_id = command['task_id']
        command_id = 'host-materials-' + hashlib.sha256(command['command_id'].encode()).hexdigest()
        if self.kernel.get_command(task_id, command_id):
            return self.kernel.get_task(task_id)
        task = self.kernel.get_task(task_id)
        grants, roots = [], set()
        replace = command['payload'].get('replace', False)
        selection = {} if replace else dict(task['state'].get('host_material_selection', {}))
        # Retain valid existing capabilities. Explicit new grants repair a moved folder.
        for grant in ([] if replace else task['material_grants']):
            try:
                root = _validate_grant_root(grant)
            except (ContractError, OSError):
                continue
            grants.append(grant)
            roots.add(root)
        for requested in command['payload']['grants']:
            grant = _build_material_grant(requested['uri'], len(grants) + 1, task['created_at'])
            if Path(grant['canonical_target']) not in roots:
                grants.append(grant)
                roots.add(Path(grant['canonical_target']))
            actual = next(item for item in grants if item['canonical_target'] == grant['canonical_target'])
            if 'include_paths' in requested:
                paths = []
                for value in requested['include_paths']:
                    relative = PurePosixPath(value)
                    if (relative.is_absolute() or not relative.parts or '..' in relative.parts
                            or '\\' in value or ':' in value or relative.as_posix() != value):
                        raise ContractError('include_paths must contain exact safe relative file paths: ' + value)
                    paths.append(value)
                selection[actual['grant_id']] = paths
        grants = self.kernel._validate_material_grants(grants)
        selection = {key: value for key, value in selection.items() if key in {g['grant_id'] for g in grants}}
        inventory = self._scan_materials(
            {**task, 'material_grants': grants}, revision=task['revision'] + 1, command_id=command_id,
            selected_paths=selection, partial=True)
        errors = [item for item in inventory['scan_issues'] if item.get('severity') == 'blocker']
        if errors:
            issue = errors[0]
            message = 'Material scan could not complete: ' + issue['code']
            if issue.get('details'):
                message += '. ' + issue['details']
            raise ContractError(message)
        envelope = {'contract': 'paperspine5.command-envelope', 'schema_version': '1.0',
                    'task_id': task_id, 'command_id': command_id, 'expected_revision': task['revision'],
                    'writer_id': 'p1-material-files', 'command_type': 'host.materials.authorize',
                    'payload': {'roots': sorted(str(root) for root in roots)},
                    'actor': {'actor_id': command['actor']['actor_id'], 'surface': 'system'}}
        try:
            self.kernel._submit_registered_command(task_id, envelope, registration=self.registration,
                                                   prepared={'grants': grants, 'inventory': inventory, 'selection': selection})
        finally:
            self.kernel.release_writer_lease(task_id, 'p1-material-files')
        return self.kernel.get_task(task_id)
