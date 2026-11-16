"""Copy authorized local output into the existing task artifact authority."""
from __future__ import annotations

import hashlib
import io
import os
import stat
import zipfile
import zlib
from pathlib import Path, PureWindowsPath

from .product_kernel import ContractError
from .filesystem_paths import native_path


MAX_SOURCE_BYTES = 128 * 1024 * 1024


class ArtifactCheckError(ContractError):
    """Existing validation failure with read-only diagnostic details."""

    def __init__(self, message: str, details: dict):
        super().__init__(message)
        self.details = details


def checked_path(path: Path) -> None:
    for part in (path, *path.parents):
        info = native_path(part).lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ContractError('links and reparse points are not allowed')


def read_source(kernel, task_id: str, root: str | None, relative: str) -> tuple[bytes, str]:
    value = Path(relative)
    if (not relative or value.is_absolute() or PureWindowsPath(relative).drive
            or '..' in value.parts or ':' in relative or '\\' in relative
            or any(part.endswith((' ', '.')) for part in relative.split('/'))):
        raise ContractError('source must be a plain grant-relative file path')
    task = kernel.get_task(task_id)
    if root is None:
        expected_workspace = kernel.user_data_root / 'tasks' / task_id
        workspace = Path(task['workspace_root'])
        if workspace != expected_workspace or workspace.resolve() != expected_workspace.resolve():
            raise ContractError('task workspace does not match product layout')
        checked_path(workspace)
        supplied = workspace / value
        checked_path(supplied)
        path = supplied.resolve()
        if not path.is_relative_to(workspace.resolve()):
            raise ContractError('output escapes the current task workspace')
    else:
        grant = next((g for g in task['material_grants'] if g['canonical_target'] == root), None)
        if grant is None:
            raise ContractError('source grant is not in this task')
        supplied = Path(root) / value
        checked_path(supplied)
        path = kernel.resolve_material_path(task_id, grant['grant_id'], value)
        if path.is_relative_to(kernel.user_data_root) or path.is_relative_to(kernel.core_root):
            raise ContractError('product data and installation cannot be imported as materials')
    before = native_path(path).stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_SOURCE_BYTES:
        raise ArtifactCheckError('source must be a regular single-link file at most 128 MiB',
                                 {'size_bytes': before.st_size, 'max_size_bytes': MAX_SOURCE_BYTES})
    with native_path(path).open('rb') as stream:
        opened = os.fstat(stream.fileno())
        checked_path(supplied)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ContractError('source changed while opening')
        body = stream.read(MAX_SOURCE_BYTES + 1)
        after = os.fstat(stream.fileno())
    checked_path(supplied)
    if (len(body) != before.st_size or (after.st_size, after.st_mtime_ns) !=
            (before.st_size, before.st_mtime_ns)):
        raise ContractError('source changed while reading')
    return body, path.name


def media_type(body: bytes, name: str, artifact_type: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == '.pdf' and body.startswith(b'%PDF-'):
        return 'application/pdf'
    if suffix in {'.zip', '.docx'}:
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                names = archive.namelist()
                if suffix == '.docx' and {'[Content_Types].xml', 'word/document.xml'}.issubset(names):
                    return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                if suffix == '.zip':
                    return 'application/zip'
        except zipfile.BadZipFile:
            pass
        raise ContractError('file is not the declared archive format')
    if suffix == '.png' and body.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if suffix in {'.jpg', '.jpeg'} and body.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if suffix in {'.md', '.txt', '.tex', '.bib', '.csv', '.json', '.svg'}:
        try:
            text = body.decode('utf-8-sig')
        except UnicodeError as exc:
            raise ContractError('text output must be UTF-8') from exc
        if suffix == '.svg' and '<svg' not in text:
            raise ContractError('not an SVG file')
        return {'.svg':'image/svg+xml','.tex':'text/x-tex','.bib':'application/x-bibtex',
                '.json':'application/json','.csv':'text/csv'}.get(suffix, 'text/plain; charset=utf-8')
    raise ContractError('unsupported local output format')


def import_artifact(kernel, command: dict, source_root: str | None) -> dict:
    payload = command['payload']; task_id = command['task_id']
    body, name = read_source(kernel, task_id, source_root, payload['source']['relative_path'])
    digest = hashlib.sha256(body).hexdigest()
    media = media_type(body, name, payload['artifact_type'])
    expected = {'pdf':'application/pdf', 'docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'delivery_package':'application/zip', 'tex':'text/x-tex', 'bibliography':'application/x-bibtex'}
    if payload['artifact_type'] in expected and expected[payload['artifact_type']] != media:
        raise ContractError('artifact type does not match file format')
    if 'sha256' in payload and payload['sha256'] != digest:
        raise ContractError('supplied digest does not match source')
    if 'media_type' in payload and payload['media_type'] != media:
        raise ContractError('supplied media type does not match source')
    metadata = {**payload, 'sha256':digest, 'media_type':media, 'size_bytes':len(body), 'filename':name}
    task = kernel.get_task(task_id)
    prior = [v for v in kernel.list_artifacts(task_id) if v['receipt']['artifact_id'] == payload['artifact_id']]
    if prior:
        if any(v['receipt']['sha256'] != digest or v['receipt']['artifact_type'] !=
               'paper.'+payload['artifact_type'].replace('_','-') for v in prior):
            raise ContractError('artifact identifier already binds different content')
        if any(v['freshness'] == 'fresh' for v in prior):
            return metadata
        raise ContractError('retained artifact is stale; use a new output identity')
    run = Path(task['run_root'])
    expected_run = kernel.user_data_root / 'tasks' / task_id / 'runs' / task['active_run_id']
    if run != expected_run:
        raise ContractError('task output root does not match product layout')
    checked_path(run)
    output = run / 'public-artifacts'; native_path(output).mkdir(exist_ok=True); checked_path(output)
    # Hash the identifier to avoid filesystem aliases (case, reserved names, colons).
    identity = hashlib.sha256(payload['artifact_id'].encode()).hexdigest()
    target = output / (identity + '-' + digest + Path(name).suffix.lower())
    temporary = output / (identity + '.partial')
    created = False
    try:
        if native_path(target).exists():
            checked_path(target)
            if native_path(target).stat().st_nlink != 1 or native_path(target).read_bytes() != body:
                raise ContractError('retained output bytes differ')
        else:
            if native_path(temporary).exists():
                checked_path(temporary)
                if not native_path(temporary).is_file() or native_path(temporary).stat().st_nlink != 1:
                    raise ContractError('unsafe partial output')
                native_path(temporary).unlink()
            with native_path(temporary).open('xb') as stream:
                stream.write(body); stream.flush(); os.fsync(stream.fileno())
            checked_path(output)
            os.replace(native_path(temporary), native_path(target)); created = True
        receipt = {'contract':'paperspine5.artifact-receipt','schema_version':'1.0',
            'receipt_id':'public-'+hashlib.sha256((task_id+':'+payload['artifact_id']).encode()).hexdigest(),
            'artifact_id':payload['artifact_id'],'artifact_type':'paper.'+payload['artifact_type'].replace('_','-'),
            'path':str(target),'sha256':digest,'size_bytes':len(body),
            'subject':{'task_id':task_id,'revision_id':str(task['revision']),
                       'input_hashes':{'authorized-source':digest}},
            'authority':{'kind':'host_materialized','producer_id':'paperspine-public-import'},
            'metadata':{'product_build_id':task['product_manifest']['build_id'],
                        'source_grant_id':payload['source'].get('grant_id', 'task-workspace'),'filename':name,'media_type':media}}
        kernel.record_artifact(task_id, receipt, expected_revision=task['revision'],
            command_id='public-import-'+hashlib.sha256((task_id+':'+command['command_id']).encode()).hexdigest(),
            writer_id='public-artifact-import')
    except Exception:
        # Keep a fully registered file after a lost acknowledgement; never delete its bytes.
        registered = any(v['receipt']['artifact_id'] == payload['artifact_id'] for v in kernel.list_artifacts(task_id))
        if created and not registered and native_path(target).exists():
            native_path(target).unlink()
        raise
    finally:
        kernel.release_writer_lease(task_id, 'public-artifact-import')
        if native_path(temporary).exists():
            checked_path(temporary); native_path(temporary).unlink()
    return metadata


def verify_delivery_archive(path: Path | io.BytesIO, required: list[dict]) -> dict:
    """Check actual archive bytes against current outputs, without another manifest.

    PrepareDelivery ignores the diagnostic return; the read-only host query uses
    it on already safely read bytes. Nested containers are reported, never opened
    recursively or counted as their contents. Matching remains byte/hash based.
    """
    hashes = set()
    report = {'member_count': 0, 'expanded_size_bytes': 0, 'nested_archives': [],
              'matched_artifact_ids': [], 'missing_artifact_ids': []}
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            report['member_count'] = len(members)
            report['expanded_size_bytes'] = sum(info.file_size for info in members)
            if len(members) > 4096 or sum(info.file_size for info in members) > 512 * 1024 * 1024:
                raise ContractError('delivery archive exceeds safe inspection limits')
            names = set()
            for info in members:
                name = info.orig_filename[:-1] if info.is_dir() else info.orig_filename
                parts = name.split('/')
                if (not name or '\x00' in name or name.startswith('/') or PureWindowsPath(name).drive or '\\' in name
                        or ':' in name or any(part in {'', '.', '..'} or part.endswith((' ', '.'))
                                              or PureWindowsPath(part).is_reserved() for part in parts)
                        or info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16)
                        or name.casefold() in names):
                    raise ContractError('delivery archive has unsafe or duplicate members')
                names.add(name.casefold())
                if info.is_dir():
                    continue
                digest = hashlib.sha256()
                size = 0
                with archive.open(info) as member:
                    while chunk := member.read(1024 * 1024):
                        if size == 0 and (
                            name.lower().endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.tar.xz', '.xz'))
                            or chunk.startswith((b'\xfd7zXZ\x00', b'\x1f\x8b'))
                            or chunk[257:262] == b'ustar'
                            or (chunk.startswith((b'PK\x03\x04', b'PK\x05\x06'))
                                and not name.lower().endswith(('.docx', '.pptx', '.xlsx')))
                        ):
                            report['nested_archives'].append(name)
                        size += len(chunk)
                        if size > info.file_size:
                            raise ContractError('delivery archive member size changed')
                        digest.update(chunk)
                if size != info.file_size:
                    raise ContractError('delivery archive member is incomplete')
                hashes.add(digest.hexdigest())
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError, zlib.error) as exc:
        raise ContractError('delivery archive is damaged or unreadable') from exc
    missing = [item['artifact_id'] for item in required if item['sha256'] not in hashes]
    report['missing_artifact_ids'] = missing
    report['matched_artifact_ids'] = [item['artifact_id'] for item in required if item['sha256'] in hashes]
    if missing:
        raise ArtifactCheckError('delivery archive does not contain current required outputs: ' + ', '.join(missing), report)
    return report
